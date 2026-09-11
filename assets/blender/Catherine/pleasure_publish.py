# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'pleasure' clip.

The work is in blender/lib/clip_publish.py; this file is just pleasure's
arguments.

Run:  python pleasure_publish.py      (after pleasure_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

LABELS = ["smile_4", "smile_7", "smile_3", "smile_6", "open_xl",
          "smile_5", "open_l", "open_m", "smile_2", "smile_1"]

NOTE = (u"上機嫌（10コマ）。talk01/joy/anger/sadness と同じ立ちポーズ。"
        u"**10枚とも頬に赤み**なので赤みはベース（コマ9＝medoid）に凍結して出しっぱなし。"
        u"パッチは2種類: 全コマの**口**（1752px）と、**コマ5のウインク**（7348px / JSON の winkFrame）。"
        u"開き順は 9 8 2 0 5 3 1（閉じた笑み）/ 7 6（開く）/ 4（最大）。"
        u"**歯は残してあります**: joy と違って開き具合に比例して増えるので"
        u"（5〜24px（閉じた7枚）→ 42 → 66 → 92）、点滅しません（teethFrames）。"
        u"ウインクは joy の差分マスクをそのまま当てると失敗します（リングの40超え 116〜258px）。"
        u"**パッチを取る直前に局所で合わせ直す**（ウインクしていない側の目と鼻梁で整合を取る）と"
        u"コマ5は 24px まで下がり（joy 並み）、変化は目とまぶたに集中します"
        u"（変化 2132px のうち髪の帯は 250px のみ）。"
        u"コマ3もウインクしますが継ぎ目が3〜4倍悪い（90〜104px）ので口だけ使用。"
        u"コマは 594x754。描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    clip_publish.publish(
        name="catherine_pleasure",
        frames_dir=os.path.join(OUT, "frames_pleasure"),
        prefix="cp",
        sheet_name="catherine_pleasure_sheet.png",
        json_path=os.path.join(OUT, "catherine_pleasure.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_pleasure.gif"),
        anim_path=os.path.join(HERE, "catherine_pleasure_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=9,
        extra={"blushAlways": True, "teethFrames": [4, 6, 7], "winkFrame": 5},
    )
