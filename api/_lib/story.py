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
import random
import re
import threading
import time
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import images  # noqa: E402  同じフォルダに置いてある

#: api/_lib/ から見て2つ上がプロジェクト直下
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: お題の指示文。**api/ の下に置いてある。**
#: Vercel は api/ 以外を静的配信するので、assets/ に置くと中身が読めてしまう
#: （ゲームの中身そのもの）。関数からはファイルとして読むので位置は自由
PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_prompts")

#: 生成した背景の置き場は tools/images.py が持つ。
#: ディスクか Vercel Blob かを環境変数で切り替えるので、ここでは扱わない。
#: 外から story.OUT_DIR を見ている箇所のために名前だけ残してある
OUT_DIR = images.OUT_DIR
OUT_URL = images.OUT_URL

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

#: f-string の中で改行を書くための逃げ道
NL_CHAR = chr(10)


def _clean_key(value):
    """前後の空白・改行と、囲みの引用符を落とす"""
    return str(value or "").strip().strip('"').strip("'").strip()


def api_key():
    """
    OPENAI_API_KEY。環境変数が先で、無ければ .env を見る。無ければ None。

    **貼り付けの前後の空白と引用符は落とす。** Render の入力欄に改行や
    空白が紛れ込むと、そのまま Authorization ヘッダに乗って 401 になり、
    原因が分かりにくい。
    """
    global _key_cache
    if _key_cache is not None:
        return _key_cache or None

    _key_cache = _clean_key(os.environ.get("OPENAI_API_KEY", ""))
    path = os.path.join(ROOT, ".env")
    if not _key_cache and os.path.exists(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                _key_cache = _clean_key(line.split("=", 1)[1])
                break
    return _key_cache or None


def rules(name):
    """assets/Prompt/<name>.txt をそのまま読む"""
    path = os.path.join(PROMPT_DIR, f"{name}.txt")
    return io.open(path, encoding="utf-8").read() if os.path.exists(path) else ""


#: 出力の言語を指示する一文。**指示文（002/003.txt）は日本語のまま1本で持ち、
#: 出力の言語だけをここで切り替える。** 訳した指示文をもう1組置くと、
#: 人物設定や書式をどちらかだけ直して食い違うため。
#:
#: 長さの上限を言語ごとに変えているのは、吹き出しの幅が全角19文字ぶんで、
#: 半角なら倍入るから（style.css の .bubble-text）。
LANG_RULES = {
    "ja": "",
    "en": """

---
IMPORTANT - OUTPUT LANGUAGE
Write every conversation line in natural, colloquial ENGLISH, not Japanese.
Keep the label names exactly as specified (Martin_conversation_01 etc.) and keep
the emotion values EXACTLY as one of these five words, lowercase, nothing else:
joy / anger / sadness / pleasure / surprised
Keep each line within 60 characters.
Martin speaks politely and awkwardly, unsure of himself.
Catherine speaks in blunt, casual slang - she is guarded and never compliments
anyone straightforwardly.
""",
}


def lang_rules(name, lang):
    """指示文に、出力言語の指定を足して返す"""
    return rules(name) + LANG_RULES.get(lang, LANG_RULES["en"])


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

#: 1回ぶんの親密度の増減の幅。assets/Prompt/002.txt で同じ範囲を指示しているが、
#: 外れた値が返ってくることがあるのでこちらでも収める。
#: 0（Affinity 行が無かった＝増減なし）はそのまま通す
AFFINITY_UP = (10, 40)
AFFINITY_DOWN = (10, 20)

#: イベントでの増減の幅。**1日ぶんの展開より小さく取る。**
#: イベントは日の途中の一幕で、Prompt で選ばれた展開のほうが主役だから。
#: 同じ幅にすると、3日ぶんの上限100にイベントだけで届いてしまう
EVENT_AFFINITY_UP = (5, 20)
EVENT_AFFINITY_DOWN = (5, 10)


#: 鍵らしき文字列。OpenAI は 401 のときエラー本文に鍵の一部を混ぜて返すことがあり、
#: その本文は部屋に入って**全員のポーリングに乗る**（rooms.py の story.error）。
KEY_LIKE_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")

#: 絵が**安全側で弾かれた**ときの文言。OpenAI は 400 でこれを返す。
#: 例: `safety_violations=[sexual]` / `Your request was rejected by the safety system.`
#: 会話のほうは通ってしまうので、そのまま進むと背景だけ前の回のまま残る
BLOCKED_RE = re.compile(
    r"safety[ _]system|safety_violations|moderation_blocked|content[ _]policy",
    re.IGNORECASE,
)


def is_blocked(error):
    """絵が安全側で弾かれたか。**お題そのものが描けない**ので、作り直すしかない"""
    return bool(error) and bool(BLOCKED_RE.search(str(error)))


def _safe_error(text):
    """外へ出すエラー文から鍵らしきものを伏せる"""
    return KEY_LIKE_RE.sub("sk-***", str(text))


def _clamp_affinity(value, up=AFFINITY_UP, down=AFFINITY_DOWN):
    """増減を指示した幅に収める。0 は「増減なし」としてそのまま"""
    if value > 0:
        return min(max(value, up[0]), up[1])
    if value < 0:
        return -min(max(-value, down[0]), down[1])
    return 0


#: 台詞に混ざってくる感情の書き置き。`うわっ…最悪だ(sadness)` のように
#: emotion を会話の側にも付けてくることがあるので、吹き出しに出す前に落とす。
#: 丸括弧・角括弧・隅付き括弧の全角半角と、前に付く「emotion:」まで拾う
EMOTION_TAG_RE = re.compile(
    r"[\(（\[［【]\s*(?:emotion\s*[:：]\s*)?(?:%s)\s*[\)）\]］】]" % "|".join(EMOTIONS),
    re.IGNORECASE,
)


def _strip_emotion(text):
    """会話文から感情の書き置きを取り除く。空白の潰れも直す"""
    return re.sub(r"\s{2,}", " ", EMOTION_TAG_RE.sub("", text)).strip()


#: emotion の揺れを5種類に寄せる表。
#:
#: **表情はこの5つのクリップしか無い**（assets/blender/develop/）ので、
#: 外れた語はそのままだと捨てられ、表情が既定の口パクのまま動かなくなる。
#: モデルは英語で書かせると nervous / embarrassed のような語を返しやすく、
#: 日本語でも「Joy.」のように句点を付けてくることがある。
EMOTION_ALIASES = {
    "joy": ("happy", "happiness", "glad", "cheerful", "delighted", "excited",
            "joyful", "laugh", "smile", "喜び", "嬉しい", "笑顔"),
    "anger": ("angry", "annoyed", "annoyance", "irritated", "mad", "upset",
              "frustrated", "disgust", "怒り", "苛立ち"),
    "sadness": ("sad", "sorrow", "sorrowful", "disappointed", "down", "depressed",
                "gloomy", "lonely", "悲しみ", "悲しい"),
    "pleasure": ("pleased", "content", "satisfied", "relaxed", "calm", "amused",
                 "fond", "warm", "affectionate", "楽しい", "満足"),
    "surprised": ("surprise", "shocked", "astonished", "startled", "nervous",
                  "flustered", "embarrassed", "confused", "驚き", "動揺"),
}

#: 別名 -> 正式名。起動時に1度だけ組む
_EMOTION_LOOKUP = {name: name for name in EMOTIONS}
for _canon, _aliases in EMOTION_ALIASES.items():
    for _a in _aliases:
        _EMOTION_LOOKUP[_a] = _canon


def _normalize_emotion(value):
    """句読点や大文字を落として5種類に寄せる。寄せられなければ空"""
    word = str(value or "").strip().strip(".。,、!！?？:：'\"").strip().lower()
    return _EMOTION_LOOKUP.get(word, "")


def _clean(value):
    """前後の飾りを落とす。値が次の行に来ることもあるので空も許す"""
    value = value.strip().strip("*").strip()
    value = value.strip("「」\"'“”").strip()
    return value


def parse_script(text, up=AFFINITY_UP, down=AFFINITY_DOWN):
    """
    002.txt の形式を読み取る。行の順番ではなく **番号** で組み直すので、
    多少並びが乱れていても壊れない。

    @param up/down 親密度の増減を収める幅。イベントだけ小さめを渡す
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
        # emotion は表情の切り替えにだけ使う。吹き出しには出さない
        text_value = _strip_emotion(slot.get("conversation", ""))
        if not text_value:
            continue
        lines.append({
            "who": who.lower(),
            "text": text_value,
            "emotion": _normalize_emotion(slot.get("emotion", "")),
        })

    affinity = AFFINITY_RE.search(text)
    bgm = BGM_RE.search(text)
    bgm_name = ""
    if bgm:
        wanted = bgm.group(1).lower()
        bgm_name = next((b for b in BGM_CHOICES if b.lower() == wanted), "")

    return {
        "lines": lines,
        "affinity": _clamp_affinity(int(affinity.group(1)), up, down) if affinity else 0,
        "bgm": bgm_name,
        "raw": text,
    }


def make_finale(history, affinity, lang):
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
            {"role": "system", "content": lang_rules("003", lang)},
            {"role": "user",
             "content": f"これまでの会話:\n{recap}\n\n最終的な親密度: {affinity}"},
        ],
    }, timeout=90)
    return parse_script(data["choices"][0]["message"]["content"])


def finale(history, affinity, lang="ja"):
    """
    @return {"lines": [...], "error": str|None}
    """
    if not api_key():
        return {"error": "no api key (.env の OPENAI_API_KEY が空です)"}
    try:
        script = make_finale(history, affinity, lang)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")[:300]
        return {"error": _safe_error(f"HTTP {err.code}: {body}"), "lines": []}
    except Exception as err:                      # noqa: BLE001 落とさず理由を返す
        return {"error": _safe_error(f"{type(err).__name__}: {err}"), "lines": []}

    # 003.txt は Catherine の独り言だけ。ほかが混ざっていたら落とす
    lines = [l for l in script["lines"] if l["who"] == "catherine"]
    return {"lines": lines, "error": None if lines else "no lines"}


#: 親密度の行が無いときに投げ直す回数。
#: モデルは会話と bgm だけ返して `Affinity:` を落とすことが1〜2割ある。
#: そのまま 0 にすると**その日はまったく増えず**、原因も画面に出ない。
#: 画像（13秒）と並行して走っているので、1回投げ直しても待ち時間は増えない
SCRIPT_RETRIES = 2


def make_script(winner, lang):
    result = None
    for _ in range(SCRIPT_RETRIES):
        data = _post("chat/completions", {
            "model": TEXT_MODEL,
            "messages": [
                {"role": "system", "content": lang_rules("002", lang)},
                {"role": "user", "content": f"次の展開のPrompt: {winner}"},
            ],
        }, timeout=90)
        result = parse_script(data["choices"][0]["message"]["content"])
        # 会話は出たのに親密度だけ落ちている回。もう一度だけ投げ直す
        if result["lines"] and not result["affinity"]:
            continue
        return result
    return result


# ---------------------------------------------------------------
#  ランダムイベント（004.txt）
# ---------------------------------------------------------------

#: 出来事の傾向。**毎回ひとつ引いてお題として渡す。**
#: 指示文だけだと「急に雨が降る」ばかりになるので、振れ幅をこちらで作る。
#: どれも現実では起こりえない方向に倒してある（004.txt も同じ方針）
EVENT_THEMES = (
    "空から現実にはありえないものが大量に降ってくる",
    "巨大な生き物や物体が街に現れる",
    "重力がおかしくなって物が浮かび上がる",
    "動物や身の回りの物が突然しゃべりだす",
    "空間が裂けて別の世界が覗く",
    "街並みが一瞬で見たこともない風景に変わる",
    "空に巨大な何かが浮かんで街を見下ろす",
    "建物や道路が動き出して並び替わる",
    "季節や昼夜が数秒ごとに入れ替わる",
    "時間が巻き戻ったり止まったりする",
    "そこらじゅうの物が一斉に増殖する",
    "色や光が現実ではありえない見え方をする",
)

#: 今回の Martin の出方。**これも毎回ひとつ引いて渡す。**
#: お題だけ渡してモデルに任せると、毎回「Martin が役に立って Catherine が
#: 見直す」話に落ち着いて、親密度が同じ値に張り付く（実測で6回とも +15）。
#: 結末のほうも振れさせないと、イベントでの増減が意味を持たない
#: **上げ4 / 下げ2 で引く。** 半々にすると、プレイヤーにはどうにもできない
#: 引きだけで 3日ぶんの上限100から10近く削られ、届かない回ができてしまう
EVENT_OUTCOMES = (
    "Martinが機転を利かせてCatherineを助ける。親密度は上がる",
    "Martinが身を挺してCatherineをかばう。親密度は大きく上がる",
    "Martinが落ち着いてCatherineを先に逃がす。親密度は大きく上がる",
    "Martinは何もできないが、Catherineを気づかう言葉はかける。親密度は少しだけ上がる",
    "Martinはうろたえるばかりで何の役にも立たない。親密度は下がる",
    "Martinが良かれと思ってしたことが裏目に出る。親密度は下がる",
)
#: 「Event: ...」の一行を拾う
EVENT_RE = re.compile(r"^\s*\**\s*Event\s*\**\s*[:：]\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def make_event(lang):
    """お題と結末をひとつずつ引いて、出来事とそれに対する会話を作らせる"""
    theme = random.choice(EVENT_THEMES)
    outcome = random.choice(EVENT_OUTCOMES)
    data = _post("chat/completions", {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": lang_rules("004", lang)},
            {"role": "user",
             "content": f"今回のお題の傾向: {theme}\n今回のMartinの出方: {outcome}"},
        ],
    }, timeout=90)
    text = data["choices"][0]["message"]["content"]

    script = parse_script(text, EVENT_AFFINITY_UP, EVENT_AFFINITY_DOWN)
    found = EVENT_RE.search(text)
    # Event 行が無いときは会話だけでも出す。見出しは呼び出し側が補う
    return {"text": _clean(found.group(1)) if found else "",
            "lines": script["lines"], "affinity": script["affinity"],
            "theme": theme, "outcome": outcome}


def invent_event(lang="ja"):
    """
    出来事の一文だけを作る。

    **誰も Prompt を出さなかった回のお題として使う。** わざわざ別の指示文を
    置かず 004.txt を使い回すのは、「奇想天外さ」の基準を1か所に保つため。
    会話も一緒に返ってくるが、ここでは捨てる（テキスト1回ぶんなので安い）。

    @return 出来事の一文。作れなければ None
    """
    try:
        return make_event(lang)["text"] or None
    except Exception as err:                      # noqa: BLE001 ここで止めない
        print("[story] invent_event failed:", _safe_error(err))
        return None


def event_text(lang="ja"):
    """
    出来事と、それに対する会話を作る。**絵はまだ描かない。**

    文章は3秒ほど、絵は13秒ほどかかる。ひとまとめにすると、
    出来事が決まっているのに何も出せない時間が十数秒できてしまう。
    先に文章だけ返して、待っているあいだ渦の画面にお題として出す。

    @return {"text": str, "lines": [...], "affinity": int, "error": str|None}
    """
    if not api_key():
        return {"error": "no api key (.env の OPENAI_API_KEY が空です)", "lines": []}
    try:
        made = make_event(lang)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")[:300]
        return {"error": _safe_error(f"HTTP {err.code}: {body}"), "lines": []}
    except Exception as err:                      # noqa: BLE001 落とさず理由を返す
        return {"error": _safe_error(f"{type(err).__name__}: {err}"), "lines": []}

    if not made["lines"]:
        return {**made, "error": "no lines"}
    return {**made, "error": None}


def event_image(text, stem):
    """
    出来事を題材に背景を描く。**描けなくても会話だけで進める**ので、
    失敗は理由を返すだけにする（ここで止めるとその日が進まなくなる）。

    @return {"image": str|None, "error": str|None}
    """
    try:
        return {"image": make_background(text, stem), "error": None}
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")[:300]
        return {"image": None, "error": _safe_error(f"HTTP {err.code}: {body}")}
    except Exception as err:                      # noqa: BLE001
        return {"image": None, "error": _safe_error(f"{type(err).__name__}: {err}")}

# ---------------------------------------------------------------
#  未来（005.txt）— 親密度が満タンになったときだけ作る
# ---------------------------------------------------------------

#: 何年後を描くか。scenes の並びと同じ
FUTURE_YEARS = (10, 20, 30)

#: 「Future_01: ...」を拾う
FUTURE_RE = re.compile(
    r"^\s*\**\s*Future_(\d+)\s*\**\s*[:：]\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


def make_future(history, lang):
    """3日間の会話を渡して、10年後・20年後・30年後の情景と会話を作らせる"""
    lines = []
    for day, turns in enumerate(history, 1):
        lines.append(f"【{day}日目】")
        for turn in turns:
            who = "Martin" if turn["who"] == "martin" else "Catherine"
            lines.append(f"{who}: {turn['text']}")
    recap = NL_CHAR.join(lines) or "（会話なし）"

    data = _post("chat/completions", {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": lang_rules("005", lang)},
            {"role": "user", "content": f"これまでの会話:{NL_CHAR}{recap}"},
        ],
    }, timeout=120)
    text = data["choices"][0]["message"]["content"]

    script = parse_script(text)
    scenery = {int(m.group(1)): _clean(m.group(2)) for m in FUTURE_RE.finditer(text)}

    scenes = []
    for i, year in enumerate(FUTURE_YEARS, 1):
        # parse_script は番号順に martin -> catherine で並ぶので、1場面につき2行
        pair = [l for l in script["lines"]][(i - 1) * 2:(i - 1) * 2 + 2]
        scenes.append({
            "year": year,
            "text": scenery.get(i, ""),
            "lines": pair,
            "image": None,
        })
    return scenes


def future_text(history, lang="ja"):
    """
    未来の3場面（情景と会話）。**絵はまだ描かない。**
    @return {"scenes": [...], "error": str|None}
    """
    if not api_key():
        return {"scenes": [], "error": "no api key (.env の OPENAI_API_KEY が空です)"}
    try:
        scenes = make_future(history, lang)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")[:300]
        return {"scenes": [], "error": _safe_error(f"HTTP {err.code}: {body}")}
    except Exception as err:                      # noqa: BLE001
        return {"scenes": [], "error": _safe_error(f"{type(err).__name__}: {err}")}

    if not any(s["lines"] for s in scenes):
        return {"scenes": scenes, "error": "no lines"}
    return {"scenes": scenes, "error": None}


def future_images(scenes, stem):
    """
    3場面の背景をまとめて描く。**同時に投げる**（1枚13秒なので直列だと40秒かかる）。
    描けなかった場面は image が None のまま。会話だけでも流せる。
    """
    def draw(i, scene):
        if not scene.get("text"):
            return
        try:
            scene["image"] = make_background(scene["text"], f"{stem}_f{i}")
        except Exception as err:                  # noqa: BLE001 1枚落ちても止めない
            print("[story] future image failed:", _safe_error(err))

    threads = [threading.Thread(target=draw, args=(i, s), daemon=True)
               for i, s in enumerate(scenes, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=200)
    return scenes

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

    # 置き先はディスクか Vercel Blob。返る文字列は
    # そのまま <img src> に入れられる形になっている（tools/images.py）
    return images.put(f"{stem}.png", base64.b64decode(data["data"][0]["b64_json"]))


# ---------------------------------------------------------------
#  まとめて
# ---------------------------------------------------------------

def generate(winner, stem, lang="ja"):
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
            out[name + "_error"] = _safe_error(f"HTTP {err.code}: {body}")
        except Exception as err:                      # noqa: BLE001 落とさず理由を返す
            out[name + "_error"] = _safe_error(f"{type(err).__name__}: {err}")
        out[name + "_sec"] = round(time.time() - t0, 1)

    # 会話と画像は独立なので同時に投げる。遅いほう（画像）の時間で終わる
    threads = [
        threading.Thread(target=run, args=("script", lambda: make_script(winner, lang)), daemon=True),
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

    # 絵だけ安全側で弾かれた回。呼び出し側（rooms.py の _run_story）が
    # お題ごと作り直せるように、理由を分けて知らせる
    result["blocked"] = not result["image"] and is_blocked(out.get("image_error"))

    # 片方だけ落ちても、取れたほうは返す
    errors = [out[k] for k in ("script_error", "image_error") if k in out]
    if errors:
        result["error"] = " / ".join(errors)
    if not result["lines"] and not result["image"]:
        result.setdefault("error", "nothing generated")
    return result
