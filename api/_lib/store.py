"""
部屋の置き場

**同じコードを Render でも Vercel でも動かすための層。**

  - Render / 手元 … プロセス内のメモリ（今までどおり）。外部サービスは要らない
  - Vercel        … Redis。環境変数が入っていればこちらに切り替わる

Vercel はリクエストごとに別のインスタンスになりうるので、部屋をメモリに
持てない（公式ドキュメントも "Store durable state, presence, counters,
rooms ... in an external data store" と名指ししている）。かといって
Render 用のコードを別に持つと中身がずれていくので、置き場だけを
ここに隔離して、どちらでも同じ rooms.py が動くようにする。

**部屋まるごとを1つの JSON として読み書きする。** 項目ごとに触らないのは、
rooms.py 側が `room["prompts"].append(...)` のような素直な書き方をしていて、
その111か所に手を入れずに済ませるため。1部屋のデータは数KBなので、
まるごと読み書きしても問題にならない。

使い方は今までの `with LOCK:` とほぼ同じ。

    with store.room_tx(code) as room:      # 読む → 触る → 書く
        if room is None:
            return
        room["affinity"] += 10

Redis を使うときだけ、この範囲が**部屋ごとの排他**になる。メモリのときは
プロセス内のロックがそのまま効く。
"""

import contextlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request

#: 部屋の鍵の頭。Redis を他の用途と共有しても混ざらないように
PREFIX = "mtfil:room:"

#: 部屋ごとの排他の鍵
LOCK_PREFIX = "mtfil:lock:"

#: 部屋を置いておく時間 秒。遊び終えた部屋を残し続けない。
#: 1回の通しプレイは15分ほどなので、その4倍を見ておく
TTL_SECONDS = 3600

#: 排他を握れる最大時間 ms。生成は同期で20〜40秒かかるが、
#: **生成中はロックを持たない**作りにしてあるので、これで足りる
LOCK_TTL_MS = 15000

#: 排他が空くのを待つ最大時間 秒
LOCK_WAIT_SECONDS = 10


def _env(*names):
    """最初に見つかった環境変数を返す。名前は入れ物によって違う"""
    for n in names:
        v = str(os.environ.get(n) or "").strip()
        if v:
            return v
    return ""


#: 繋ぎ方は2通りあり、**入っている環境変数で自動的に決まる。**
#:
#:   1. 接続 URL（redis://…）… Vercel の Marketplace の Redis がこれ。
#:      普通の Redis 接続なので redis パッケージを使う
#:   2. REST（URL + トークン）… Upstash を直接使うときはこれ。
#:      HTTP なので urllib だけで足り、パッケージが要らない
#:
#: どちらでも動くようにしてあるのは、途中で乗り換えても
#: コードを書き直さずに済ませるため
REDIS_CONN_URL = _env("REDIS_URL", "REDIS_CLOUD_URL", "KV_URL")
REDIS_REST_URL = _env("KV_REST_API_URL", "UPSTASH_REDIS_REST_URL", "REDIS_REST_URL")
REDIS_REST_TOKEN = _env("KV_REST_API_TOKEN", "UPSTASH_REDIS_REST_TOKEN", "REDIS_REST_TOKEN")

#: どれを使うか。**環境変数が揃っているときだけ Redis。**
#: 揃っていなければ今までどおりメモリで動く（Render と手元がこちら）
if REDIS_CONN_URL:
    MODE = "redis"
elif REDIS_REST_URL and REDIS_REST_TOKEN:
    MODE = "redis-rest"
else:
    MODE = "memory"

USE_REDIS = MODE != "memory"


# ---------------------------------------------------------------
#  メモリ（Render / 手元）
# ---------------------------------------------------------------

_ROOMS = {}
_LOCK = threading.RLock()


class _Memory:
    """今までどおり。**dict をそのまま返す**ので、触ればそのまま残る"""

    def load(self, code):
        return _ROOMS.get(code)

    def save(self, code, room):
        _ROOMS[code] = room          # 同じ物なので実質何もしていない

    def create(self, code, room):
        with _LOCK:
            if code in _ROOMS:
                return False
            _ROOMS[code] = room
            return True

    def delete(self, code):
        _ROOMS.pop(code, None)

    def codes(self):
        return list(_ROOMS)

    @contextlib.contextmanager
    def lock(self, code):
        with _LOCK:                  # 1プロセルなので部屋ごとに分ける必要が無い
            yield


# ---------------------------------------------------------------
#  Redis（Vercel）
# ---------------------------------------------------------------

def _ok(reply):
    """
    SET が通ったか。

    **繋ぎ方で返り方が違う。** REST は文字列 "OK"、redis パッケージは True を返す
    （NX で弾かれたときはどちらも None）。ここを "OK" だけで見ていて、
    Marketplace の Redis に繋いだ瞬間に部屋が1つも建てられなくなった。
    """
    return reply is True or reply == "OK" or reply == b"OK"


class _RedisBase:
    """
    Redis を使うときの中身。**繋ぎ方（_call）だけを差し替えて使い回す。**

    扱うのは GET / SET / DEL / KEYS / EVAL の5つだけなので、
    どちらの繋ぎ方でも同じ手順が書ける。
    """

    def _call(self, *command):
        raise NotImplementedError

    def load(self, code):
        raw = self._call("GET", PREFIX + code)
        return json.loads(raw) if raw else None

    def save(self, code, room):
        self._call("SET", PREFIX + code, json.dumps(room, ensure_ascii=False),
                   "EX", TTL_SECONDS)

    def create(self, code, room):
        # NX なので、既にあれば何もせず None が返る
        return _ok(self._call("SET", PREFIX + code, json.dumps(room, ensure_ascii=False),
                              "NX", "EX", TTL_SECONDS))

    def delete(self, code):
        self._call("DEL", PREFIX + code)

    def codes(self):
        # 部屋数はたかが知れているので SCAN まではしない
        keys = self._call("KEYS", PREFIX + "*") or []
        return [k[len(PREFIX):] for k in keys]

    @contextlib.contextmanager
    def lock(self, code):
        key = LOCK_PREFIX + code
        token = secrets.token_hex(8)
        limit = time.time() + LOCK_WAIT_SECONDS
        while True:
            if _ok(self._call("SET", key, token, "NX", "PX", LOCK_TTL_MS)):
                break
            if time.time() > limit:
                # 握れないまま進む。**止めるよりは進めた**ほうがマシ。
                # 15秒で必ず失効するので、握りっぱなしにはならない
                token = None
                break
            time.sleep(0.05)
        try:
            yield
        finally:
            if token:
                # **自分が置いた鍵だけを消す。** 単に DEL すると、失効後に
                # 別の誰かが握った鍵まで消してしまう
                self._call(
                    "EVAL",
                    "if redis.call('get',KEYS[1])==ARGV[1] then "
                    "return redis.call('del',KEYS[1]) else return 0 end",
                    1, key, token,
                )


class _RedisRest(_RedisBase):
    """Upstash の REST API を urllib で叩く。パッケージが要らない"""

    def _call(self, *command):
        body = json.dumps([str(c) for c in command]).encode("utf-8")
        req = urllib.request.Request(
            REDIS_REST_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {REDIS_REST_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.load(res).get("result")


class _RedisConn(_RedisBase):
    """
    普通の Redis 接続。Vercel の Marketplace の Redis がこれ。

    **繋ぎ口はモジュールに1つだけ持つ。** Fluid compute は同じインスタンスで
    続けて呼ばれるので、毎回つなぎ直さずに済み、そのぶん速い。
    """

    def __init__(self):
        import redis  # ここでだけ要る。REST のときは読み込まない
        self._client = redis.Redis.from_url(
            REDIS_CONN_URL,
            decode_responses=True,     # 文字列で受け取る。JSON をそのまま入れるため
            socket_timeout=10,
            socket_connect_timeout=10,
            health_check_interval=30,  # 寝ていた接続を掴んだときに繋ぎ直させる
        )

    def _call(self, *command):
        if command[0] == "EVAL":
            # EVAL は引数の形が特殊（script, 鍵の数, 鍵…, 値…）
            script, numkeys, *rest = command[1:]
            return self._client.eval(script, int(numkeys), *rest)
        return self._client.execute_command(*command)


def _make_backend():
    if MODE == "redis":
        return _RedisConn()
    if MODE == "redis-rest":
        return _RedisRest()
    return _Memory()


_backend = _make_backend()


# ---------------------------------------------------------------
#  外から使うもの
# ---------------------------------------------------------------

def where():
    """いまどれで動いているか。起動時のログ用"""
    return MODE


def load(code):
    """部屋を読む。無ければ None"""
    return _backend.load(code)


def save(code, room):
    """部屋を書く"""
    _backend.save(code, room)


def delete(code):
    """部屋を畳む"""
    _backend.delete(code)


def codes():
    """いま在る部屋コード"""
    return _backend.codes()


def lock(code):
    """部屋ごとの排他。読み書きを挟まずに順番だけ取りたいとき"""
    return _backend.lock(code)


def create(code, room):
    """
    **まだ無いときだけ**建てる。建てられたら True。

    コードは乱数なので衝突はまず起きないが、起きたときに
    他人の部屋を上書きすると目も当てられないので、置く側で弾く。
    """
    return _backend.create(code, room)


@contextlib.contextmanager
def room_tx(code):
    """
    **読む → 触る → 書く** をひとまとめにする。`with LOCK:` の置き換え。

    途中で例外が出たら書き戻さない。`None` が渡ってきたら（部屋が無い）
    呼び出し側が抜けるので、そのときも書かない。
    """
    with _backend.lock(code):
        room = _backend.load(code)
        yield room
        if room is not None:
            _backend.save(code, room)


def seq():
    """
    重ならない短い文字列。生成した絵の名前に使う。

    もとは STORY_SEQ という通し番号だったが、**番号はプロセスの記憶**なので
    Vercel では続かない。名前が重ならなければよいだけなので乱数にする。
    """
    return secrets.token_hex(3)
