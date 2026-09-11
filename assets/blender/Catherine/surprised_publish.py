# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'surprised' clip.

The work is in blender/lib/clip_publish.py; this file is just surprised's
arguments.

Run:  python surprised_publish.py      (after surprised_prep.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

LABELS = ["line_2", "open_s", "o_1", "o_2", "gasp",
          "open_m", "open_s2", "line_3", "line_1"]

NOTE = (u"驚き（9コマ）。9枚は「同じポーズの別テイク」で、変わるのは顔だけ。"
        u"**見開いた目のコマ4をベースに固定**してあります（medoid ならコマ1＝普通の目）。"
        u"クリップ全体が目を見開いたまま、動くのは口だけ（1561px）。"
        u"Martin の surprised02 と同じ作りです。"
        u"継ぎ目の品質はベースの選び方に依存しないことを確認済み"
        u"（どのコマをベースにしてもリング上の差は 6〜8/255、40超えゼロ）ので、"
        u"ベースは表情だけで選べます。"
        u"※「通常の表情から驚く」版（コマ2/3/4 に目のパッチ、前髪は色キーで凍結）も"
        u"作って計測しましたが、**この見開き固定版を採用**しました"
        u"（戻し方は surprised_prep.py の docstring に記録してあります）。"
        u"開き順は 8 0 7 / 1 6 5 / 2 3 / 4（最大）。"
        u"驚きに予備動作は無いので、2カットのあと**いきなりコマ4へ跳ね**、"
        u"揺れてから順に戻ります。"
        u"コマは 598x756。描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    clip_publish.publish(
        name="catherine_surprised",
        frames_dir=os.path.join(OUT, "frames_surprised"),
        prefix="cu",
        sheet_name="catherine_surprised_sheet.png",
        json_path=os.path.join(OUT, "catherine_surprised.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_surprised.gif"),
        anim_path=os.path.join(HERE, "catherine_surprised_anim.py"),
        labels=LABELS,
        note=NOTE,
        base_frame=4,
        extra={"gaspFrame": 4},
    )
