# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for the Martin 'pleasure' clip.

The work is in publish.py; this file is just pleasure's arguments.

Run:  python pleasure_publish.py      (after pleasure_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish                     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")

# the ten are the same shut smile drawn ten times; the labels order them by how
# broad it is, which is the only thing that separates them
LABELS = ["smile_2", "smile_7", "smile_4", "smile_8", "smile_9",
          "smile_10", "blush", "smile_6", "smile_5", "smile_1"]

NOTE = (u"上機嫌。10枚は「同じポーズ（両手ポケット）の別テイク」で、変わるのは顔だけ。"
        u"**口の形が10種類あるのではなく、同じ閉じた笑みが10回描かれている**だけで、"
        u"10枚合わせても 37x9px（x299..335 / y228..236）しかありません。"
        u"眼鏡と目の帯で合わせたうえで1枚のパッチ以外をベース（コマ1）に固定してあるので、"
        u"残るのは笑みの揺れだけ＝「呼吸している」ように見えます（差分2817px）。"
        u"コマ6には**薄い頬の赤み**が付きます（肌との差が10〜25階調しかない淡いもの／"
        u"JSON の blushFrame）。**赤みはコマ6にしか無い**ので、"
        u"sadness の涙と同じく7フレームの連続ブロックで1回だけ出しています。"
        u"広さ順は 9 0 6 2 8 7 1 3 4 5 で、タイムラインは"
        u"「漂う→いちばん広い笑みへ→戻す→赤み→元へ」。"
        u"赤みと両端以外は保持2フレーム＝毎秒12枚（口の切り替えの下限）。")

if __name__ == "__main__":
    publish.publish(
        name="martin_pleasure",
        frames_dir=os.path.join(OUT, "frames_pleasure"),
        prefix="pl",
        sheet_name="martin_pleasure_sheet.png",
        json_path=os.path.join(OUT, "martin_pleasure.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "martin_pleasure.gif"),
        anim_path=os.path.join(HERE, "martin_pleasure_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=1,
        extra={"blushFrame": 6},
    )
