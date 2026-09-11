# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for the Martin 'talk03' clip.

The work is in publish.py; this file is just talk03's arguments.

Run:  python talk03_publish.py      (after talk03_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish                     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")

LABELS = ["closed", "open_s2", "open_m2", "open_l2", "open_xl",
          "open_l", "open_m", "open_s", "closed_xs", "closed_2"]

NOTE = (u"喋る（10コマ版・両手ポケット）。既存の martin_talk01（6コマ・初回パス）とは"
        u"**別クリップで、置き換えではありません**。talk / talk01 / talk02 / talkhand の"
        u"番号を継いで talk03 としています（素材フォルダ名と clip 名は元々一致していません — "
        u"talkhand の素材は Martin/talk_02 です）。"
        u"10枚は「同じポーズの別テイク」で、口以外を1枚のベース（コマ3＝medoid）に"
        u"固定してあるため動くのは口だけ（1446px）。"
        u"一連の10枚組の中で**いちばん継ぎ目が楽な素材**で、パッチの外周はどの向きにも"
        u"平らな頬が6px以上あり、リング上のコマ間差は最大11/255・40超えゼロ。"
        u"開き順は 8 9 0 / 7 1 6 2 / 5 3 4。口が10種類あるので本物のリップシンクが組めます: "
        u"タイムラインは3つのフレーズに分け、各フレーズは保持2フレーム（毎秒12枚＝早口）で"
        u"形を混ぜて回し、区切りで閉じた口に着地します。"
        u"落ち着いたテンポにしたい場合は timeline の保持を全部 2→3 にしてください"
        u"（毎秒8枚／martin_talk の hold と同じつまみ）。")

if __name__ == "__main__":
    publish.publish(
        name="martin_talk03",
        frames_dir=os.path.join(OUT, "frames_talk03"),
        prefix="t3",
        sheet_name="martin_talk03_sheet.png",
        json_path=os.path.join(OUT, "martin_talk03.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "martin_talk03.gif"),
        anim_path=os.path.join(HERE, "martin_talk03_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=3,
        extra={"hold": 2},
    )
