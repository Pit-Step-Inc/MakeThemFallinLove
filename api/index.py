"""
Vercel の入口

**`/api/*` を受ける Vercel Function（Python / WSGI）。**
中身は api/_lib/rooms.py に渡すだけ。画面と素材は Vercel が静的配信するので、
このファイルは通らない。

**api/ の下に置いてあるのが要点。** Vercel は api/ 以外を丸ごと静的配信するので、
サーバーのコードとお題の指示文を assets/ や tools/ に置くと中身が読めてしまう。
api/ の下は関数の一部として扱われ、静的配信の対象にならない。さらに
vercel.json で `/api/(.*)` を全部この関数に向けてあるので、
`/api/_lib/rooms.py` のような URL も**ここに来て 404 になる**（素通りしない）。

`_lib` と `_prompts` の頭に `_` を付けているのは、api/ 直下の .py が
1つずつ別の関数になる決まりを避けるため。

Render 版は別ブランチ（develop / main）にあり、tools/serve.py が
静的配信と API の両方を受け持つ。読むのは同じ api/_lib で、
置き場（store.py / images.py）を環境変数で切り替えているので、
**両方で同じコードが動く。**

フレームワークは使わない。素の WSGI 関数で足りるし、依存を足すと
関数の大きさにも起動の速さにも効いてくる。
"""

import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lib"))
import rooms  # noqa: E402

#: 読み込む本文の上限。Prompt も名前も短いので、これで十分すぎる
MAX_BODY = 64 * 1024

#: 書き換え（vercel.json の rewrites）が元のパスを渡すときの入れ物。
#: この関数は本来 `/api` だけを受け持つので、`/api/host` のような
#: 行き先を見失わないように、query にも入れて二重に持たせてある
PATH_PARAM = "__p"


def _json(start_response, status, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    start_response(f"{status} ", [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        # 部屋の様子は毎回変わる。挟まれると待ち合わせが狂う
        ("Cache-Control", "no-store"),
    ])
    return [body]


def _path(environ, query):
    """
    どのエンドポイントを呼ばれたのかを決める。

    PATH_INFO がそのまま `/api/host` なら素直にそれを使う。書き換えの
    仕方によっては `/api` までしか来ないことがあるので、そのときは
    query に入れておいた行き先で補う。
    """
    path = environ.get("PATH_INFO") or "/"
    if path.startswith("/api/") and len(path) > len("/api/"):
        return path
    hint = (query.get(PATH_PARAM) or [""])[0].strip("/")
    return f"/api/{hint}" if hint else path


def app(environ, start_response):
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    query = urllib.parse.parse_qs(environ.get("QUERY_STRING") or "")
    path = _path(environ, query)

    body = None
    if method == "POST":
        try:
            length = min(int(environ.get("CONTENT_LENGTH") or 0), MAX_BODY)
        except ValueError:
            length = 0
        raw = environ["wsgi.input"].read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (ValueError, UnicodeDecodeError):
            return _json(start_response, 400, {"error": "bad json"})

    status, obj = rooms.handle(method, path, query, body)
    return _json(start_response, status, obj)
