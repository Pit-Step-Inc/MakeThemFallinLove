# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'joy' clip.

The work is in blender/lib/clip_publish.py; this file is just joy's
arguments.

Run:  python joy_publish.py      (after joy_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

LABELS = ["smile_1", "smile_4", "laugh_m", "laugh_l", "open_s",
          "smile_2", "open_m", "laugh_xl", "smile_3"]

NOTE = (u"喜び（9コマ）。talk01 と同じ立ちポーズ。"
        u"**9枚とも頬に赤みが入っている**ので、赤みはベース（コマ1＝medoid）に"
        u"凍結してクリップ中出しっぱなし。**歯はどのコマにも描かれていません**。"
        u"パッチは2種類: 全コマの**口**（1911px、手で引いた多角形）と、"
        u"コマ4（半目）とコマ5（**目を閉じてにこっ**）の**目**です。"
        u"目のマスクは**手で引かず差分から作っています**（spriteprep.diff_patch）。"
        u"多角形だとまぶたの折り目かまつ毛か前髪を必ず横切り、"
        u"リング上の差が 237〜252/255 になってゴーストしますが、"
        u"差分から作れば継ぎ目が「一致している場所」に落ち、"
        u"コマ5で 133/5.1（40超えは前髪の25px）、コマ4で 101/3.7 になります。"
        u"位置合わせの基準は**目ではなく鼻と頬の帯**（コマ5は目を閉じていて"
        u"目基準だと scale 1.100・shift -57,-61 に飛ぶため）。"
        u"開き順は 0 5 8 1 / 4 6 / 2 3 7（7が最大）。"
        u"タイムラインは2拍子: 「微笑み→開く→笑う→2回ゆらす」のあとに"
        u"「半目(4)→**目を閉じてにこっ(5)を6フレーム保持**→開く(4)」を置いています"
        u"（表情の保持なので、口パクの2フレームでは短すぎます）。"
        u"コマは 582x728。描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    clip_publish.publish(
        name="catherine_joy",
        frames_dir=os.path.join(OUT, "frames_joy"),
        prefix="cj",
        sheet_name="catherine_joy_sheet.png",
        json_path=os.path.join(OUT, "catherine_joy.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_joy.gif"),
        anim_path=os.path.join(HERE, "catherine_joy_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=1,
        extra={"blushAlways": True, "eyeFrames": [4, 5], "squintFrame": 5},
    )
