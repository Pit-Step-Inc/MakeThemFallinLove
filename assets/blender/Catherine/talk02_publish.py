# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'talk02' clip.

The work is in blender/lib/clip_publish.py; this file is just talk02's
arguments.

Run:  python talk02_publish.py      (after talk02_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

LABELS = ["closed", "open_m2", "open_m3", "open_m4", "open_xl",
          "open_l", "open_l2", "open_s", "closed_xs"]

NOTE = (u"喬る（手を差し出したポーズ／9コマ）。"
        u"talk01 とは**別ポーズ**で、右手を手のひらを上に差し出しています。"
        u"手はベース（コマ0＝medoid）の位置で固定され、動くのは口だけ（1290px）。"
        u"顔の位置は talk01 と同じなので基準の帯も口の多角形も同じものを使っています"
        u"（仮定せずこの9枚で検証済み: 口の画素は全コママスクの実部に入り、"
        u"リング上のコマ間差は最大15/255・40超えゼロ）。"
        u"開き順は 8 0 / 7 1 2 3 / 6 5 4（4が最大）。"
        u"タイムラインは3フレーズ構成で、保持2フレーム（毎秒12枚）。"
        u"落ち着いたテンポにしたい場合は timeline の保持を全部 2→3 に。"
        u"コマは 582x728 で talk01（574x738）と違うので、"
        u"描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    clip_publish.publish(
        name="catherine_talk02",
        frames_dir=os.path.join(OUT, "frames_talk02"),
        prefix="c2",
        sheet_name="catherine_talk02_sheet.png",
        json_path=os.path.join(OUT, "catherine_talk02.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_talk02.gif"),
        anim_path=os.path.join(HERE, "catherine_talk02_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=0,
        extra={"hold": 2},
    )
