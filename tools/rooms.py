#!/usr/bin/env python3
"""
Prompt を共有するための最小のルームサーバー

**ホストが部屋を建て、ほかの人はコードで入る。**

  - 名前を決めたあと、ホストは POST /api/host で部屋を建てる。4文字のコードが返る
  - ほかの人は POST /api/join にそのコードを添えて入る
  - **Prompt は1人1つまで**（POST /api/prompt）
  - **カウントダウンは全員が揃ってから**。会話を読み終えて Prompt 画面に着いた人が
    POST /api/ready を打ち、部屋の全員が ready になった瞬間に ROUND_SECONDS 秒が始まる。
    揃わないときは**ホストだけ** POST /api/force-start で先に始められる
  - 誰かが来た / 抜けたは events に積んで、各自がポーリングで拾って通知する
  - 時間切れのあと POST /api/story で、**いちばんいいねが多かった Prompt だけ**を
    OpenAI に投げて次の展開（背景・会話・BGM・親密度の増減）を作る。作るのは1回だけで、
    結果は部屋に貯めて全員が同じものを見る（tools/story.py）
  - 親密度は部屋に貯めて回ごとに足していく。回をまたいでも消えない
  - **1日1回**。MAX_DAYS 日ぶん終わると allDaysDone が立ち、そこから
    POST /api/finale で assets/Prompt/003.txt を投げて Catherine の独り言を作る

ホストが抜けたら、いちばん古くから居る人が繰り上がる。部屋の主が居なくなって
誰も先に進められない部屋ができるのを防ぐため。

状態はメモリだけに持つ。サーバーを落とせば消えるし、プロセスを分けて
動かすと共有されない。作っている最中に手元で遊ぶためのもので、
本番で使うならここを外部のストア（Redis など）に差し替えることになる。

HTTP の口は tools/serve.py が持っていて、このモジュールは
handle(method, path, query, body) -> (status, obj) だけを公開する。
"""

import os
import random
import secrets
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story  # noqa: E402  同じフォルダに置いてある

#: 1ラウンドの長さ 秒（src/promptScene.js の TIME_LIMIT と揃える）
ROUND_SECONDS = 60

#: Prompt の長さ。言語ごとに違う（src/promptScene.js の MAX_LENGTH と揃える）。
#: 英語は語と語の空白ぶん字数が要るので長め
MAX_TEXT = {"ja": 40, "en": 50}

#: 名前の長さ（src/nickname.js の MAX_LENGTH と揃える）
MAX_NAME = 7

#: 終わったラウンドをこれだけ放っておくと、次の ready で新しい回が始まる。
#: 短くできるのは、**生成中は別途はじいている**から（_is_stale 参照）。
#: この待ち時間だけで生成を守ろうとすると、生成にかかる十数秒より
#: 長く取らざるを得なくなる
STALE_SECONDS = 5

#: これだけ顔を見せない人は抜けたものとして数から外す。
#: クライアントは参加した時点から定期的に state を見に来るので、
#: 会話を読んでいる最中の人は生きたままになる（src/room.js の heartbeat）。
#:
#: **ブラウザは裏に回ったタブの setInterval を最大1分まで間引く。**
#: 心拍が 2.5 秒でも、他のタブを見ている人は1分に1回しか顔を出せないので、
#: それより短くすると「見ていただけで部屋から外れる」ことになる。
#: 揃わないときはホストが force-start で先へ進められる。
IDLE_SECONDS = 90

#: 持っておく通知の数
EVENT_KEEP = 50

#: 誰も居なくなった部屋をこれだけで畳む 秒
EMPTY_SECONDS = 300

#: コードに使う文字。読み上げと打ち間違いを避けて 0/O/1/I/L を抜いてある
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4

#: 親密度の下限と上限。参照画像のゲージは空から始まる
AFFINITY_MIN = 0
AFFINITY_MAX = 100

#: エンディングで名前を出す人数（assets/reference_image/Ending_001.png）
TOP_PLAYERS = 3

#: 何日ぶん遊ぶか。これを終えると最後のシーンへ
MAX_DAYS = 3

ROOMS = {}
LOCK = threading.RLock()
STORY_SEQ = 0


# ---------------------------------------------------------------
#  部屋
# ---------------------------------------------------------------

def _new_code():
    """空いているコードを1つ。LOCK の中で呼ぶこと"""
    for _ in range(100):
        code = "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if code not in ROOMS:
            return code
    # ここまで来るのは部屋が埋まりきったとき。桁を足して逃がす
    return "".join(random.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH + 2))


def _clean_code(value):
    """入力されたコードをそろえる。小文字で打たれても通す"""
    code = str(value or "").strip().upper().replace(" ", "")
    if not code or len(code) > CODE_LENGTH + 2:
        return None
    return code if all(c in CODE_ALPHABET for c in code) else None


def _clean_name(value):
    return str(value or "").strip()[:MAX_NAME]


def _clean_lang(value):
    """生成に使う言語。知らない値が来たら英語に倒す"""
    return "ja" if str(value or "").lower().startswith("ja") else "en"


def _event(room, kind, name):
    """通知を1つ積む。各自が since より新しいぶんだけ拾っていく"""
    room["eventSeq"] += 1
    room["events"].append({"seq": room["eventSeq"], "type": kind, "name": name})
    del room["events"][:-EVENT_KEEP]


def _touch(room, player_id):
    player = room["players"].get(player_id)
    if player:
        player["seen"] = time.time()
    return player


def _maybe_start(room):
    """**全員が ready になった瞬間**に締め切りを決める。始まっていれば何もしない"""
    if room["deadline"] is not None:
        return
    players = room["players"].values()
    if not players or not all(p["ready"] for p in players):
        return
    room["deadline"] = time.time() + ROUND_SECONDS


def _is_stale(room):
    """
    前の回として片付けてよいか。

    **生成中は片付けない。** 切り替え画面で次の展開を待っている人が居る最中に
    story を消すと、その人だけ「作れませんでした」で止まってしまう。
    生成が終わっていれば、もう各自の手元に絵と台詞が渡っているので消してよい。
    """
    if room["deadline"] is None:
        return False
    if (room["story"] or {}).get("status") == "working":
        return False
    return time.time() > room["deadline"] + STALE_SECONDS


def _prune(room):
    """居なくなった人を外す。待っている相手が消えたら、その場で始める"""
    now = time.time()
    gone = False
    for pid, player in list(room["players"].items()):
        if now - player["seen"] <= IDLE_SECONDS:
            continue
        del room["players"][pid]
        _event(room, "leave", player["name"])
        gone = True

    if not gone:
        return

    # 部屋の主が居なくなったら、いちばん古くから居る人に譲る
    if room["hostId"] not in room["players"] and room["players"]:
        room["hostId"] = min(room["players"], key=lambda pid: room["players"][pid]["joined"])
    _maybe_start(room)


def _sweep():
    """空になった部屋を畳む。LOCK の中で呼ぶこと"""
    now = time.time()
    for code, room in list(ROOMS.items()):
        if room["players"]:
            room["emptyAt"] = None
        elif room["emptyAt"] is None:
            room["emptyAt"] = now
        elif now - room["emptyAt"] > EMPTY_SECONDS:
            del ROOMS[code]


def _remaining_ms(room):
    """残り ms。まだ始まっていなければ None"""
    if room["deadline"] is None:
        return None
    return max(0, int((room["deadline"] - time.time()) * 1000))


def _ranked(room):
    """いいねの多い順。同数は投稿が早いほう（sorted は安定）"""
    return sorted(room["prompts"], key=lambda p: -p["likes"])


def _top_players(room):
    """
    もらったいいねの合計が多い順に TOP_PLAYERS 人。
    **回ごとに room["prompts"] は捨てられる**ので、集計は
    その回が締まった時点（_story）で room["likes"] に足しておく。
    """
    ranked = sorted(room["likes"].items(), key=lambda kv: -kv[1])
    return [{"name": name, "likes": likes} for name, likes in ranked[:TOP_PLAYERS]]


def _ending(room):
    """
    エンディングで使う材料。3日ぶん終わるまでは None。
    毎回のポーリングに載せたくないので、それまでは何も出さない。

    未来の場面（room["future"]）は別に持つ。**親密度が満タンのときしか
    作らない**ので、ここにまとめると届かなかった部屋でも作りに行ってしまう。
    """
    if not room["allDaysDone"]:
        return None
    return {"topPlayers": _top_players(room)}


def _state(room, player_id=None, since_event=0):
    _prune(room)
    remaining = _remaining_ms(room)
    mine = next((p for p in room["prompts"] if p["playerId"] == player_id), None)
    host = room["players"].get(room["hostId"])
    return {
        "code": room["code"],
        "isHost": player_id == room["hostId"],
        "hostName": host["name"] if host else "",
        "players": len(room["players"]),
        "ready": sum(1 for p in room["players"].values() if p["ready"]),
        "names": [p["name"] for p in room["players"].values()],
        "prompts": [
            {"id": p["id"], "author": p["author"], "text": p["text"], "likes": p["likes"]}
            for p in _ranked(room)
        ],
        "remainingMs": remaining,
        "started": room["deadline"] is not None,
        "roundOver": remaining == 0,
        "myPromptId": mine["id"] if mine else None,
        "story": room["story"],
        "event": room["event"],
        "future": room["future"],
        "affinity": room["affinity"],
        "day": room["day"],
        "lastDay": MAX_DAYS,
        "allDaysDone": room["allDaysDone"],
        "finale": room["finale"],
        "ending": _ending(room),
        "eventSeq": room["eventSeq"],
        "events": [e for e in room["events"] if e["seq"] > since_event],
    }


def _add_player(room, player_id, name):
    """入れる。既に居れば名前だけ差し替える"""
    known = room["players"].get(player_id)
    room["players"][player_id] = {
        "name": name,
        "seen": time.time(),
        "joined": known["joined"] if known else time.time(),
        # 会話を読んでいる最中はまだ ready ではない。Prompt 画面で ready になる
        "ready": bool(known and known["ready"]),
    }

    # 自分の Prompt に出る名前は、あとから変えても追従させる
    for prompt in room["prompts"]:
        if prompt["playerId"] == player_id:
            prompt["author"] = name

    if not known:
        _event(room, "join", name)


def _find(code, player_id=None):
    """部屋を引く。無ければ (None, エラー応答)"""
    if not code:
        return None, (400, {"error": "bad code"})
    room = ROOMS.get(code)
    if not room:
        return None, (404, {"error": "no such room", "code": code})
    if player_id is not None and player_id not in room["players"]:
        return None, (403, {"error": "not joined"})
    return room, None


# ---------------------------------------------------------------
#  各エンドポイント
# ---------------------------------------------------------------

def _host(body):
    """部屋を建てる。建てた人がホストになる"""
    name = _clean_name(body.get("name"))
    if not name:
        return 400, {"error": "name required"}

    with LOCK:
        _sweep()
        code = _new_code()
        player_id = secrets.token_urlsafe(9)
        room = {
            "code": code, "hostId": player_id, "players": {}, "prompts": [],
            "deadline": None, "seq": 0, "events": [], "eventSeq": 0, "emptyAt": None,
            "story": None, "affinity": 0, "event": None,
            "day": 1, "allDaysDone": False, "history": [], "finale": None,
            # エンディングの回想と TOP PLAYERS 用。回ごとに prompts は捨てられるので、
            # 締まった時点でここに写しておく
            "likes": {}, "future": None,
            # 生成される会話をどちらで書かせるか。建てた人の言語に揃える
            "lang": _clean_lang(body.get("lang")),
        }
        ROOMS[code] = room
        _add_player(room, player_id, name)

        state = _state(room, player_id)
        state["events"] = []            # 建てた本人に自分の参加は流さない
        return 200, {"playerId": player_id, **state}


def _join(body):
    """コードで入る"""
    code = _clean_code(body.get("code"))
    name = _clean_name(body.get("name"))
    if not name:
        return 400, {"error": "name required"}

    with LOCK:
        room, err = _find(code)
        if err:
            return err

        player_id = str(body.get("playerId") or "")
        if player_id not in room["players"]:
            player_id = secrets.token_urlsafe(9)
        _add_player(room, player_id, name)

        state = _state(room, player_id)
        state["events"] = []            # 入った本人にそれまでの通知は流さない
        return 200, {"playerId": player_id, **state}


def _ready(body):
    """Prompt 画面に着いた合図。**全員が揃った瞬間**にカウントダウンが始まる"""
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err

        player = _touch(room, player_id)

        if _is_stale(room):
            # 前の回が終わっている。新しい回として組み直す
            room["prompts"] = []
            room["deadline"] = None
            room["story"] = None
            for p in room["players"].values():
                p["ready"] = False

        player["ready"] = True
        _maybe_start(room)
        return 200, _state(room, player_id, since)


def _force_start(body):
    """揃うのを待たずに始める。**ホストだけ**"""
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err
        if player_id != room["hostId"]:
            return 403, {"error": "host only", **_state(room, player_id, since)}

        _touch(room, player_id)
        if room["deadline"] is None:
            room["deadline"] = time.time() + ROUND_SECONDS
        return 200, _state(room, player_id, since)


def _trim_images():
    """
    畳まれた部屋の背景を消す。**生きている部屋のぶんは残す。**

    枚数で切ると、同時にいくつも部屋が動いているときに進行中の部屋の背景まで
    消えてしまう。1部屋で MAX_DAYS 枚使い、しかもエンディングの回想で
    初日ぶんまで見返すので、消えると回想が虫食いになる。
    生成した絵のファイル名は `<部屋コード>_<連番>.png` なので、頭で見分けられる。
    """
    with LOCK:
        live = set(ROOMS)
    try:
        names = [n for n in os.listdir(story.OUT_DIR) if n.endswith(".png")]
    except OSError:
        return
    for name in names:
        if name.split("_", 1)[0] in live:
            continue
        try:
            os.remove(os.path.join(story.OUT_DIR, name))
        except OSError:
            pass


def _run_story(code, winner, stem, lang):
    """別スレッドで OpenAI を叩く。終わったら部屋に書き戻す（10秒以上かかる）"""
    # 誰も Prompt を出さなかった回。AI に出来事を考えさせて、それをお題にする
    if not winner:
        winner = story.invent_event(lang) or ""
        with LOCK:
            room = ROOMS.get(code)
            if room and room["story"]:
                room["story"]["winner"] = winner

    result = story.generate(winner, stem, lang)
    with LOCK:
        room = ROOMS.get(code)
        if not room or not room["story"]:
            return                       # 部屋が畳まれた / 次の回に入った

        # 親密度は増減ぶんが返ってくる。部屋に貯めて回ごとに足していく
        room["affinity"] = max(
            AFFINITY_MIN, min(AFFINITY_MAX, room["affinity"] + int(result.get("affinity") or 0))
        )

        # その日の会話は最後の独り言（003.txt）で振り返らせるので取っておく
        if result.get("lines"):
            room["history"].append(result["lines"])

        # 1日ぶん終わった。次の日へ進めるか、これで打ち止めか
        if room["day"] >= MAX_DAYS:
            room["allDaysDone"] = True
        else:
            room["day"] += 1

        room["story"] = {
            "status": "error" if result.get("error") and not result.get("lines") else "ready",
            "winner": winner,
            **result,
        }
    _trim_images()


def _story(body):
    """
    いちばんいいねが多かった Prompt から次の展開を作る。
    **作るのは部屋につき1回だけ**で、2人目以降は同じものを受け取る。
    """
    global STORY_SEQ
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err
        _touch(room, player_id)

        if room["story"] is not None:
            return 200, _state(room, player_id, since)   # もう誰かが始めている

        ranked = _ranked(room)

        # **誰も出さなかった回も止めない。** お題は AI に考えさせて、
        # そのまま次の展開を作る（winner は _run_story の中で埋まる）
        winner = ranked[0]["text"] if ranked else ""

        # この回はもう締まっている。いいねの合計を TOP PLAYERS 用に写しておく
        # （room["prompts"] は次の回で捨てられる）
        for p in room["prompts"]:
            room["likes"][p["author"]] = room["likes"].get(p["author"], 0) + p["likes"]

        STORY_SEQ += 1
        stem = f"{code}_{STORY_SEQ}"
        room["story"] = {"status": "working", "winner": winner, "lines": [],
                         "affinity": 0, "bgm": "", "image": None}

        threading.Thread(target=_run_story, args=(code, winner, stem, room["lang"]),
                         daemon=True).start()
        return 200, _state(room, player_id, since)


def _run_finale(code):
    """別スレッドで 003.txt を投げる。終わったら部屋に書き戻す"""
    with LOCK:
        room = ROOMS.get(code)
        if not room:
            return
        history, affinity, lang = list(room["history"]), room["affinity"], room["lang"]

    result = story.finale(history, affinity, lang)
    with LOCK:
        room = ROOMS.get(code)
        if not room or not room["finale"]:
            return
        room["finale"] = {
            "status": "error" if not result.get("lines") else "ready",
            **result,
        }


def _finale(body):
    """
    最後の独り言（003.txt）を作る。
    **作るのは部屋につき1回だけ**で、2人目以降は同じものを受け取る。
    """
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err
        _touch(room, player_id)

        if room["finale"] is not None:
            return 200, _state(room, player_id, since)   # もう誰かが始めている
        if not room["allDaysDone"]:
            return 409, {"error": "days are not finished", **_state(room, player_id, since)}

        room["finale"] = {"status": "working", "lines": []}
        threading.Thread(target=_run_finale, args=(code,), daemon=True).start()
        return 200, _state(room, player_id, since)


def _prompt(body):
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    raw_text = str(body.get("text") or "").strip()
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err

        # 切り詰める長さは部屋の言語で決まるので、部屋を引いてから切る
        text = raw_text[:MAX_TEXT.get(room["lang"], MAX_TEXT["en"])]

        player = _touch(room, player_id)
        if not text:
            return 400, {"error": "text required"}
        if _remaining_ms(room) == 0:
            return 409, {"error": "round is over", **_state(room, player_id, since)}
        if any(p["playerId"] == player_id for p in room["prompts"]):
            return 409, {"error": "one prompt per player", **_state(room, player_id, since)}

        room["seq"] += 1
        room["prompts"].append({
            "id": f"p{room['seq']}",
            "playerId": player_id,
            "author": player["name"],
            "text": text,
            "likes": 0,
        })
        return 200, _state(room, player_id, since)


def _like(body):
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    prompt_id = str(body.get("promptId") or "")
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err
        _touch(room, player_id)

        prompt = next((p for p in room["prompts"] if p["id"] == prompt_id), None)
        if not prompt:
            return 404, {"error": "no such prompt"}
        prompt["likes"] += 1
        return 200, _state(room, player_id, since)


def _get_state(query):
    code = _clean_code(query.get("code", [None])[0])
    player_id = query.get("playerId", [""])[0]
    since = int(query.get("sinceEvent", ["0"])[0] or 0)

    with LOCK:
        room, err = _find(code)
        if err:
            return err
        _touch(room, player_id)
        return 200, _state(room, player_id, since)


def _run_event(code, stem, lang):
    """
    別スレッドで 004.txt を投げる。**2段に分けて部屋に書き戻す。**

      1段目 … 出来事と会話（3秒ほど）。ここで text が埋まる。
               クライアントはこれを渦の画面にお題として出し、絵を待つ
      2段目 … その出来事の背景（13秒ほど）。埋まったら status が ready になる
    """
    made = story.event_text(lang)
    with LOCK:
        room = ROOMS.get(code)
        if not room or not room["event"]:
            return
        if not made.get("lines"):
            room["event"] = {"status": "error", "image": None, **made}
            return

        # イベントでの Martin の対応ぶりでも親密度は動く。
        # 幅は次の展開より小さい（tools/story.py の EVENT_AFFINITY_*）
        room["affinity"] = max(
            AFFINITY_MIN,
            min(AFFINITY_MAX, room["affinity"] + int(made.get("affinity") or 0)),
        )
        # まだ working。text が入ったことでクライアントが渦へ進む
        room["event"] = {"status": "working", "image": None, **made}
        text = made["text"]

    drawn = story.event_image(text, stem)
    with LOCK:
        room = ROOMS.get(code)
        if not room or not room["event"]:
            return
        room["event"].update({
            "status": "ready",
            "image": drawn["image"],
            # 絵が描けなくても会話はあるので、理由だけ残して進ませる
            "error": drawn["error"],
        })
    _trim_images()


def _random_event(body):
    """
    ランダムイベントを作る（assets/Prompt/004.txt）。
    （通知を積む _event() とは別物。名前が紛らわしいので分けてある）
    **作るのは部屋につき1回だけ**で、2人目以降は同じものを受け取る。
    """
    global STORY_SEQ
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err
        _touch(room, player_id)

        if room["event"] is not None:
            return 200, _state(room, player_id, since)   # もう誰かが始めている

        # 背景の名前は次の展開と同じ採番にする。_trim_images が
        # 部屋コードで生き死にを見分けるので、頭を揃えておく必要がある
        STORY_SEQ += 1
        stem = f"{code}_{STORY_SEQ}"

        room["event"] = {"status": "working", "text": "", "lines": [], "image": None}
        threading.Thread(target=_run_event, args=(code, stem, room["lang"]),
                         daemon=True).start()
        return 200, _state(room, player_id, since)

def _run_future(code, stem, lang):
    """
    別スレッドで 005.txt を投げる。**2段に分けて書き戻す。**
      1段目 … 3場面の情景と会話（5秒ほど）
      2段目 … 3枚の背景（同時に投げるので15秒ほど）
    """
    with LOCK:
        room = ROOMS.get(code)
        if not room:
            return
        history = list(room["history"])

    made = story.future_text(history, lang)
    with LOCK:
        room = ROOMS.get(code)
        if not room or not room["future"]:
            return
        if not made.get("scenes") or made.get("error"):
            room["future"] = {"status": "error", **made}
            return
        room["future"] = {"status": "working", **made}
        scenes = made["scenes"]

    story.future_images(scenes, stem)
    with LOCK:
        room = ROOMS.get(code)
        if not room or not room["future"]:
            return
        room["future"] = {"status": "ready", "scenes": scenes, "error": None}
    _trim_images()


def _future(body):
    """
    親密度が満タンで迎えた締め用に、10年後・20年後・30年後を作る。
    **作るのは部屋につき1回だけ**で、2人目以降は同じものを受け取る。
    """
    global STORY_SEQ
    code = _clean_code(body.get("code"))
    player_id = str(body.get("playerId") or "")
    since = int(body.get("sinceEvent") or 0)

    with LOCK:
        room, err = _find(code, player_id)
        if err:
            return err
        _touch(room, player_id)

        if room["future"] is not None:
            return 200, _state(room, player_id, since)   # もう誰かが始めている

        STORY_SEQ += 1
        stem = f"{code}_{STORY_SEQ}"
        room["future"] = {"status": "working", "scenes": [], "error": None}
        threading.Thread(target=_run_future, args=(code, stem, room["lang"]),
                         daemon=True).start()
        return 200, _state(room, player_id, since)

ROUTES = {
    ("POST", "/api/host"):        lambda q, b: _host(b),
    ("POST", "/api/join"):        lambda q, b: _join(b),
    ("POST", "/api/ready"):       lambda q, b: _ready(b),
    ("POST", "/api/force-start"): lambda q, b: _force_start(b),
    ("POST", "/api/story"):       lambda q, b: _story(b),
    ("POST", "/api/event"):       lambda q, b: _random_event(b),
    ("POST", "/api/finale"):      lambda q, b: _finale(b),
    ("POST", "/api/future"):      lambda q, b: _future(b),
    ("POST", "/api/prompt"):      lambda q, b: _prompt(b),
    ("POST", "/api/like"):        lambda q, b: _like(b),
    ("GET",  "/api/state"):       lambda q, b: _get_state(q),
}


def handle(method, path, query, body):
    """
    @return (status, obj) — obj はそのまま JSON で返される
    """
    route = ROUTES.get((method, path))
    if not route:
        return 404, {"error": "no such endpoint"}
    try:
        return route(query, body or {})
    except Exception as err:                      # noqa: BLE001 開発用なので握って返す
        return 500, {"error": f"{type(err).__name__}: {err}"}
