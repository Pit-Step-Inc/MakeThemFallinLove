# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'sadness' clip.

The work is in blender/lib/clip_publish.py; this file is just sadness's
arguments.

Run:  python sadness_publish.py      (after sadness_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

LABELS = ["dry_6", "dry_5", "dry_1", "dry_3", "dry_4",
          "tear_bead", "tear_run", "tear_fall", "tear_swell", "dry_2"]

NOTE = (u"悲しみ（10コマ）。乾いた悲しい顔から始まり、**途中で涙が徐々に出ます**。"
        u"ベースは乾いた medoid（コマ2）で、パッチは2種類: 全コマの**口**と、"
        u"涙のある4枚だけの**涙**です。"
        u"涙の進行は 5（まつ毛の端に玉 15px）→ 8（ふくらむ 45px）→ "
        u"6（頬を伝う 111px）→ 7（滴が離れて落ちる 62px）。"
        u"残り6枚（0/1/2/3/4/9）は完全に乾いています。"
        u"涙のマスクは**輪郭でも差分でもなく「色」で抜いています**"
        u"（spriteprep.colour_patch）。涙は下まぶたに密着していて多角形の置き場が無く、"
        u"差分マスクもまぶた・まつ毛・髪が毎コマ描き直されるため使えません"
        u"（リングの40超え 47〜219px / joy は 5〜25）。"
        u"でも**顔の中で青いのは涙だけ**なので、色で抜けば継ぎ目は涙自身の輪郭だけになり、"
        u"それは平らな頬の上に乗ります（まぶたはベースのまま＝涙がまつ毛に重なった状態）。"
        u"ベースの差し替えで涙を出す手は使えません（コマ2→コマ7 で図の15%が跳ねる）。"
        u"タイムラインは「乾いた悲しい顔→玉→ふくらむ→伝う→**落ちる（8フレーム保持）**"
        u"→涙は落ちて消え、ループ」。"
        u"コマは 584x730。描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    clip_publish.publish(
        name="catherine_sadness",
        frames_dir=os.path.join(OUT, "frames_sadness"),
        prefix="cs",
        sheet_name="catherine_sadness_sheet.png",
        json_path=os.path.join(OUT, "catherine_sadness.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_sadness.gif"),
        anim_path=os.path.join(HERE, "catherine_sadness_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=2,
        extra={"tearFrames": [5, 8, 6, 7], "dryFrames": [0, 1, 2, 3, 4, 9], "sobFrame": 7},
    )
