# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for the Martin 'anger' clip.

The work is in publish.py; this file is just anger's arguments.

Run:  python anger_publish.py      (after anger_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish                     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")

LABELS = ["scowl", "scowl_2", "scowl_3", "grit_xs", "grit_m",
          "shout", "grit_l", "grit_s", "scowl_4", "scowl_5"]

NOTE = (u"怒り。10枚は「同じポーズ（両手ポケット）の別テイク」で、変わるのは顔だけ。"
        u"眼鏡と目の帯で拡大縮小＋平行移動を合わせたうえで、口以外を1枚のベース"
        u"（コマ0）に固定してあるため、髪・眼鏡・上着・手は全コマ完全に同一画素で、"
        u"動くのは口だけ（2248px）。描き順の口パクではないのでタイムラインはこちらで"
        u"組んでいます: しかめ面を保持→顎を噛みしめる→4コマで振りかぶる→怒鳴る→"
        u"2回どなる→閉じて元のしかめ面へ。まばたきは元素材に閉じ目が1枚も無いため無し。")

if __name__ == "__main__":
    publish.publish(
        name="martin_anger",
        frames_dir=os.path.join(OUT, "frames_anger"),
        prefix="a",
        sheet_name="martin_anger_sheet.png",
        json_path=os.path.join(OUT, "martin_anger.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "martin_anger.gif"),
        anim_path=os.path.join(HERE, "martin_anger_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=0,
    )
