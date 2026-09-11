# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for the Martin 'surprised02' clip.

The work is in publish.py; this file is just surprised02's arguments.

Run:  python surprised02_publish.py      (after surprised02_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish                     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")

LABELS = ["o_3", "open_s", "open_m", "open_s2", "gasp",
          "gasp_big", "o_5", "o_4", "o_2", "o_1"]

NOTE = (u"驚き（10コマ版）。既存の martin_surprised（6コマ・362x724・初回パスの"
        u"重心合わせ／凍結なし）とは**別クリップ**で、置き換えではありません。"
        u"10枚は「同じポーズ（両手ポケット）の別テイク」で、変わるのは顔だけ。"
        u"口以外を1枚のベースに固定してあるので動くのは口だけ（1428px）。"
        u"**目は差し替えられません**: コマ3/4/5は目を見開いていますが眼鏡ごと"
        u"描き直されていて、縁の重なりが 0.67〜0.75（他コマは0.81〜0.87）。"
        u"talk/talkhand のまばたきは継ぎ目が両者同一の眼鏡のフチに来るから見えないので、"
        u"ここでは成立しません。そこで**見開いた目のコマ4をベースに固定**しました"
        u"（medoid ならコマ0＝普通の目）。クリップ全体が目を見開いたまま口だけが動きます。"
        u"継ぎ目の品質はベースの選び方に依存しないことを確認済み"
        u"（どのコマをベースにしてもリング上の差は最大11〜16/255、40超えゼロ）。"
        u"開き順は 9 8 0 7 6 1 3 2 4 5。驚きに予備動作は無いので、"
        u"タイムラインは小さい口から**いきなり最大へ跳ね**、そこで揺れてから順に下ります。")

if __name__ == "__main__":
    publish.publish(
        name="martin_surprised02",
        frames_dir=os.path.join(OUT, "frames_surprised02"),
        prefix="s2",
        sheet_name="martin_surprised02_sheet.png",
        json_path=os.path.join(OUT, "martin_surprised02.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "martin_surprised02.gif"),
        anim_path=os.path.join(HERE, "martin_surprised02_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=4,
    )
