# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for the Martin 'sadness' clip.

The work is in publish.py; this file is just sadness's arguments.

Run:  python sadness_publish.py      (after sadness_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish                     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")

LABELS = ["frown", "frown_5", "frown_4", "quiver", "open_s",
          "cry", "open_m", "frown_xs", "frown_3", "frown_2"]

NOTE = (u"悲しみ。10枚は「同じポーズ（両手ポケット）の別テイク」で、変わるのは顔だけ。"
        u"眼鏡と目の帯で拡大縮小＋平行移動を合わせたうえで、2枚のパッチ以外を1枚のベース"
        u"（コマ0）に固定してあるため、髪・眼鏡・上着・手は全コマ完全に同一画素で、"
        u"動くのは口と、コマ5だけに付く涙だけ（1544px）。"
        u"**涙はコマ5にしか無い**ので、joy の笑いのように 5↔6 を往復させると涙が点滅します。"
        u"タイムラインではコマ5を10フレームの連続ブロックで1回だけ出しています: "
        u"しかめ面→口が震える→涙→顔を戻す。"
        u"涙は眼鏡のフチを貫いて描かれていますが、フチの下端がコマごとに違う"
        u"（コマ4は y202、コマ9は y205）ため、パッチはフチの1行下（y206）から始めています。"
        u"涙は目尻からではなくレンズのすぐ下から始まって見えます（127px中12px分）。")

if __name__ == "__main__":
    publish.publish(
        name="martin_sadness",
        frames_dir=os.path.join(OUT, "frames_sadness"),
        prefix="s",
        sheet_name="martin_sadness_sheet.png",
        json_path=os.path.join(OUT, "martin_sadness.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "martin_sadness.gif"),
        anim_path=os.path.join(HERE, "martin_sadness_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=0,
        extra={"tearFrame": 5},
    )
