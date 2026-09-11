# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'anger' clip.

The work is in blender/lib/clip_publish.py; this file is just anger's
arguments.

Run:  python anger_publish.py      (after anger_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

LABELS = ["frown_2", "frown_5", "grit_s", "open_m", "open_l",
          "shout", "grit_l", "frown_4", "frown_1", "frown_3"]

NOTE = (u"怒り（10コマ）。talk01/joy と同じ立ちポーズ。"
        u"口以外をベース（コマ9＝medoid）に固定してあり、動くのは口だけ（2584px）。"
        u"開き順は 8 0 9 7 1（への字）/ 2 6（**歯を食いしばる**）/ 3 4（開く）/ 5（怒鳴る）。"
        u"**歯は残してあります**: joy では同じ開き具合のコマに歯があったり"
        u"無かったりで点滅しましたが、anger では歯そのものが表情です。"
        u"タイムラインでは **2→6 を連続ブロック**、**5 は 3→4 を経て到達**させていて、"
        u"歯は2回だけ「保持される拍」として現れ、同じ開きの歯無し口と交互になりません。"
        u"歯を消したい場合は anger_prep.py で SP.hide_teeth を呼べばすぐに変えられます。"
        u"**目・眉は固定**です: コマ4/5 で眉が鋭くなるので joy と同じ差分マスクを"
        u"試しましたが、この素材は**上半身全体が描き直されていて**（髪の輪郭が全部ずれる）"
        u"継ぎ目を置ける静かな場所がありません（40超え 97〜209px、joy は 5〜25px）。"
        u"コマは 578x726。描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    clip_publish.publish(
        name="catherine_anger",
        frames_dir=os.path.join(OUT, "frames_anger"),
        prefix="ca",
        sheet_name="catherine_anger_sheet.png",
        json_path=os.path.join(OUT, "catherine_anger.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_anger.gif"),
        anim_path=os.path.join(HERE, "catherine_anger_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=9,
        extra={"teethFrames": [2, 5, 6]},
    )
