#!/usr/bin/env python3
"""
次の展開を作る（OpenAI）

いちばんいいねが多かった Prompt を受け取って、

  - 背景画像（assets/Prompt/001.txt のルール）
  - 二人の会話 8ラリー + 親密度 + BGM（assets/Prompt/002.txt のルール）

を作る。**指示文は assets/Prompt/ の txt をそのまま使う**ので、
文面を変えたければあちらを直せばここは触らなくていい。

【鍵はサーバーにしか置かない】
プロジェクト直下の .env（.gitignore 済み）の OPENAI_API_KEY を読む。
ブラウザ側に置くと、ページを開いた全員に見えてしまうため。

【画像と会話は同時に投げる】
会話 3秒 / 画像 13秒 くらいなので、直列だと待ち時間がそのまま足し算になる。
別スレッドで同時に投げて、遅いほう（画像）の時間で済ませる。
待っているあいだは、クライアント側がシーン切り替えの渦を回している。
"""

import base64
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_DIR = os.path.join(ROOT, "assets", "Prompt")

#: 生成した背景の置き場。そのまま静的配信に乗る（.gitignore 済み）
OUT_DIR = os.path.join(ROOT, "assets", "generated")
OUT_URL = "assets/generated"

API = "https://api.openai.com/v1"

#: 会話。速さ優先。gpt-5 系は推論に 40 秒使って待たせすぎる
TEXT_MODEL = "gpt-4.1-mini"

#: 背景。flare が速い（実測 13 秒前後）
IMAGE_MODEL = "gpt-image-2.5-flare"

#: 16:9 にいちばん近い対応サイズ。ステージは cover で敷くので端は少し切れる
IMAGE_SIZE = "1792x1024"

#: 001.txt の「ピクセル幅3〜4px」だけは指示が通りにくいので英語で補強する。
#: これを外すと実写のような絵が返ってくる（実測）
IMAGE_STYLE = (
    "Pixel art background, 2D game background illustration. "
    "Chunky uniform pixels (about 3-4 screen pixels per art pixel), hard edges, "
    "limited palette, no anti-aliasing, no photo realism, no blur, no depth of field. "
    "Anime pixel-art scenery. No people in the foreground, no main characters. "
    "16:9 landscape, no text overlay, no UI, no frame or border."
)

#: 002.txt が選ばせる BGM。assets/BGM/ の実ファイル名と一致していること
BGM_CHOICES = ("Excited", "Funny", "Romantic", "Tense", "Bittersweet")

#: develop に用意があるクリップ名と同じ並び
EMOTIONS = ("joy", "anger", "sadness", "pleasure", "surprised")

_key_cache = None


def api_key():
    """.env の OPENAI_API_KEY。無ければ None"""
    global _key_cache
    if _key_cache is not None:
        return _key_cache or None

    _key_cache = os.environ.get("OPENAI_API_KEY", "")
    path = os.path.join(ROOT, ".env")
    if not _key_cache and os.path.exists(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                _key_cache = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return _key_cache or None


def rules(name):
    """assets/Prompt/<name>.txt をそのまま読む"""
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def _post(path, payload, timeout):
    req = urllib.request.Request(
        f"{API}/{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


# ---------------------------------------------------------------
#  会話
# ---------------------------------------------------------------

#: 「Martin_conversation_01: ...」を拾う。モデルが鉤括弧や ** を付けてくることが
#: あるので、値側は後で剥がす
LINE_RE = re.compile(
    r"^\s*\**\s*(Martin|Catherine)_(conversation|emotion)_(\d+)\s*\**\s*[:：]\s*(.*)$",
    re.IGNORECASE,
)
AFFINITY_RE = re.compile(r"Affinity\s*[:：]\s*([+\-]?\d+)", re.IGNORECASE)
BGM_RE = re.compile(r"bgm\s*[:：]\s*([A-Za-z]+)", re.IGNORECASE)


def _clean(value):
    """前後の飾りを落とす。値が次の行に来ることもあるので空も許す"""
    value = value.strip().strip("*").strip()
    value = value.strip("「」\"'“”").strip()
    return value


def parse_script(text):
    """
    002.txt の形式を読み取る。行の順番ではなく **番号** で組み直すので、
    多少並びが乱れていても壊れない。
    """
    slots = {}
    pending = None          # 値が次の行に置かれたとき用

    for raw in text.splitlines():
        m = LINE_RE.match(raw)
        if m:
            who, kind, num, value = m.group(1).title(), m.group(2).lower(), int(m.group(3)), _clean(m.group(4))
            slot = slots.setdefault((num, who), {})
            if value:
                slot[kind] = value
                pending = None
            else:
                pending = (slot, kind)
            continue

        if pending and raw.strip():
            slot, kind = pending
            slot[kind] = _clean(raw)
            pending = None

    lines = []
    for (num, who) in sorted(slots, key=lambda k: (k[0], 0 if k[1] == "Martin" else 1)):
        slot = slots[(num, who)]
        text_value = slot.get("conversation", "")
        if not text_value:
            continue
        emotion = slot.get("emotion", "").lower()
        lines.append({
            "who": who.lower(),
            "text": text_value,
            "emotion": emotion if emotion in EMOTIONS else "",
        })

    affinity = AFFINITY_RE.search(text)
    bgm = BGM_RE.search(text)
    bgm_name = ""
    if bgm:
        wanted = bgm.group(1).lower()
        bgm_name = next((b for b in BGM_CHOICES if b.lower() == wanted), "")

    return {
        "lines": lines,
        "affinity": int(affinity.group(1)) if affinity else 0,
        "bgm": bgm_name,
        "raw": text,
    }


def make_finale(history, affinity):
    """
    最終指示（003.txt）。これまでの会話と親密度を渡して、
    Catherine の独り言5文を作らせる。
    """
    lines = []
    for day, turns in enumerate(history, 1):
        lines.append(f"【{day}日目】")
        for turn in turns:
            who = "Martin" if turn["who"] == "martin" else "Catherine"
            lines.append(f"{who}: {turn['text']}")
    recap = "\n".join(lines) or "（会話なし）"

    data = _post("chat/completions", {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": rules("003")},
            {"role": "user",
             "content": f"これまでの会話:\n{{recap}}\n\n最終的な親密度: {{affinity}}"},
        ],
    }, timeout=90)
    return parse_script(data["choices"][0]["message"]["content"])


def finale(history, affinity):
    """
    @return {"lines": [...], "error": str|None}
    """
    if not api_key():
        return {"error": "no api key (.env の OPENAI_API_KEY が空です)"}
    try:
        script = make_finale(history, affinity)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")[:300]
        return {"error": f"HTTP {err.code}: {body}", "lines": []}
    except Exception as err:                      # noqa: BLE001 落とさず理由を返す
        return {"error": f"{type(err).__name__}: {err}", "lines": []}

    # 003.txt は Catherine の独り言だけ。ほかが混ざっていたら落とす
    lines = [l for l in script["lines"] if l["who"] == "catherine"]
    return {"lines": lines, "error": None if lines else "no lines"}


def make_script(winner):
    data = _post("chat/completions", {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": rules("002")},
            {"role": "user", "content": f"次の展開のPrompt: {winner}"},
        ],
    }, timeout=90)
    return parse_script(data["choices"][0]["message"]["content"])


# ---------------------------------------------------------------
#  背景
# ---------------------------------------------------------------

def make_background(winner, stem):
    data = _post("images/generations", {
        "model": IMAGE_MODEL,
        "prompt": f"{rules('001')}\n\n{IMAGE_STYLE}\n\n次の展開のPrompt: {winner}",
        "size": IMAGE_SIZE,
        "n": 1,
    }, timeout=180)

    os.makedirs(OUT_DIR, exist_ok=True)
    name = f"{stem}.png"
    with open(os.path.join(OUT_DIR, name), "wb") as f:
        f.write(base64.b64decode(data["data"][0]["b64_json"]))
    return f"{OUT_URL}/{name}"


# ---------------------------------------------------------------
#  まとめて
# ---------------------------------------------------------------

def generate(winner, stem):
    """
    @param winner いちばんいいねが多かった Prompt の本文
    @param stem   画像のファイル名に使う識別子
    @return {"lines": [...], "affinity": int, "bgm": str, "image": str|None, "error": str|None}
    """
    if not api_key():
        return {"error": "no api key (.env の OPENAI_API_KEY が空です)"}

    out = {}

    def run(name, fn):
        t0 = time.time()
        try:
            out[name] = fn()
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", "replace")[:300]
            out[name + "_error"] = f"HTTP {err.code}: {body}"
        except Exception as err:                      # noqa: BLE001 落とさず理由を返す
            out[name + "_error"] = f"{type(err).__name__}: {err}"
        out[name + "_sec"] = round(time.time() - t0, 1)

    # 会話と画像は独立なので同時に投げる。遅いほう（画像）の時間で終わる
    threads = [
        threading.Thread(target=run, args=("script", lambda: make_script(winner)), daemon=True),
        threading.Thread(target=run, args=("image", lambda: make_background(winner, stem)), daemon=True),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=200)

    script = out.get("script") or {"lines": [], "affinity": 0, "bgm": ""}
    result = {
        "lines": script["lines"],
        "affinity": script["affinity"],
        "bgm": script["bgm"],
        "image": out.get("image"),
        "took": {"script": out.get("script_sec"), "image": out.get("image_sec")},
    }

    # 片方だけ落ちても、取れたほうは返す
    errors = [out[k] for k in ("script_error", "image_error") if k in out]
    if errors:
        result["error"] = " / ".join(errors)
    if not result["lines"] and not result["image"]:
        result.setdefault("error", "nothing generated")
    return result
