# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'talk01' clip.

The work is in blender/lib/clip_publish.py; this file is just talk01's
arguments.

Run:  python talk01_publish.py      (after talk01_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

LABELS = ["closed", "open_s2", "open_m2", "open_l", "open_xl",
          "open_l2", "open_m", "open_s", "closed_2"]

NOTE = (u"喋る（Catherine 初のクリップ／9コマ）。9枚は「同じポーズの別テイク」で、"
        u"変わるのは口だけ。眼鏡が無いので**目と鼻梁の帯**を基準に拡大縮小＋平行移動を"
        u"合わせ（髪は巨大で毎コマ描き直されるため使えない）、口以外を1枚のベース"
        u"（コマ5＝medoid）に固定してあります。動くのは口だけ（1290px）。"
        u"リング上のコマ間差は最大10/255・40超えゼロ。"
        u"開き順は 0 8 / 7 1 6 2 / 3 5 4（4が最大）。"
        u"タイムラインは3フレーズ構成で、各フレーズは保持2フレーム（毎秒12枚）で形を混ぜ、"
        u"区切りで閉じた口に着地します。落ち着いたテンポにしたい場合は"
        u"timeline の保持を全部 2→3 に（毎秒8枚）。"
        u"Catherine は Martin より画面いっぱいに描かれているため、"
        u"コマは 574x738 と Martin（約500x724）より大きい点に注意。")

if __name__ == "__main__":
    clip_publish.publish(
        name="catherine_talk01",
        frames_dir=os.path.join(OUT, "frames_talk01"),
        prefix="c1",
        sheet_name="catherine_talk01_sheet.png",
        json_path=os.path.join(OUT, "catherine_talk01.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_talk01.gif"),
        anim_path=os.path.join(HERE, "catherine_talk01_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=5,
        extra={"hold": 2},
    )
