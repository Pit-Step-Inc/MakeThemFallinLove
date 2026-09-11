# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for the Martin 'joy' clip.

The work is in publish.py; this file is just joy's arguments.

Run:  python joy_publish.py      (after joy_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish                     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")

LABELS = ["smile", "smile_3", "smile_4", "smile_5", "teeth_s",
          "laugh_xl", "laugh_l", "teeth_m", "smile_2", "smile_xs"]

NOTE = (u"喜び。10枚は「同じポーズ（両手ポケット）の別テイク」で、変わるのは顔だけ。"
        u"眼鏡と目の帯で拡大縮小＋平行移動を合わせたうえで、頬のパッチ以外を1枚のベース"
        u"（コマ0）に固定してあるため、髪・眼鏡・上着・手は全コマ完全に同一画素で、"
        u"動くのは口と、笑い2枚（コマ5/6）に付く頬の赤みだけ（3635px）。"
        u"描き順の口パクではないのでタイムラインはこちらで組んでいます: "
        u"微笑み→広がる→3コマで開く→笑う→2回ゆらす→閉じて元の微笑みへ。"
        u"コマ5は目を閉じて笑っているが、眼鏡ごと描き直されていて"
        u"（縁の重なりが他コマ0.84〜0.90に対し0.58）継ぎ目を隠せないため、"
        u"まばたきは入れていない。")

if __name__ == "__main__":
    publish.publish(
        name="martin_joy",
        frames_dir=os.path.join(OUT, "frames_joy"),
        prefix="j",
        sheet_name="martin_joy_sheet.png",
        json_path=os.path.join(OUT, "martin_joy.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "martin_joy.gif"),
        anim_path=os.path.join(HERE, "martin_joy_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=0,
        extra={"blushFrames": [5, 6]},
    )
