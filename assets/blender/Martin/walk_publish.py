# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Martin's 'walk' clip.

The work is in blender/lib/clip_publish.py; this file is just walk's arguments.

Run:  python walk_publish.py      (after walk_prep.py)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import publish                     # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")

# by drawing number.  Nine are written out but only four are played - the other
# five are spare takes of the same right-foot-forward pose (see walk_prep.py).
LABELS = ["spare_R3", "spare_R4", "contact_L", "spare_R1", "spare_R5",
          "spare_R2", "contact_R", "pass_L", "pass_R"]

NOTE = (u"歩き（正面・ループ）。**9枚のうち4枚だけを再生しています**。理由は素材で、"
        u"はっきり書いておきます。"
        u"どちらの足が前かをシルエットの下端（正面なので手前の足が低い）で判定し、"
        u"腕の振り（脚と逆に振れる）で裏を取ると、"
        u"**右足前が7枚・左足前が2枚**でした（右足前の7枚では左手が大きく832〜982px、"
        u"右手は586〜653px。左足前の2枚では逆）。歩行サイクルは半周期ずつ均等な枚数が要ります。"
        u"さらに、**右足前の7枚は互いにほとんど同じポーズ**です。脚の領域の平均絶対差は"
        u"7枚どうしで10.3〜18.1（/255・中央値13.9）しかないのに、左右グループ間は26.9〜33.9。"
        u"つまりこの9枚は「歩きの9姿勢」ではなく「1姿勢の7テイク＋別姿勢の2テイク」で、"
        u"**すれ違い（passing）の姿勢がどこにもありません**。"
        u"そこで4ポーズにしました。左足前の2枚（コマ2と7・互いの差21.4）を半周期に使い、"
        u"相方は**左右反転で対応付け**て選んでいます（コマ2を反転するとコマ6に最も近い19.2、"
        u"コマ7を反転するとコマ8に最も近い23.0）。コマ6と8は7枚の中で最も離れた組（18.1）でもあるので、"
        u"右の半周期がちゃんと動きます。"
        u"再生順は **2（左接地）→ 7（右足が振り出される）→ 6（右接地）→ 8（左足が振り出される）**。"
        u"作りは Catherine の walk と同じです: 凍結はできないので**フィットを詰めて全コマ再生**、"
        u"スケールは**眼鏡と腰の2枠を別々に位置決めしてその間隔の比**で実測（眼鏡はこの素材で"
        u"いちばん確実なランドマークです）、そのうえで**縦だけ区分的に伸縮**して"
        u"胴と脚の長さを揃えています（胴 1.7%→**0.6%**、靴底のばらつき 27→**22px**）。"
        u"頭は止まっています（**目のばらつき x 2.2px・y 1.3px**）。"
        u"テンポは接地7フレーム・振り出し5フレームで **24F＝1.00秒＝毎分120歩**、"
        u"Catherine の walk と同じ歩調です（並んで歩かせても合います）。"
        u"ただし4ポーズなので1枚あたり292ms／208msと長く、Catherine の10ポーズより粗く見えます。"
        u"**なめらかにするには素材が要ります**: 左足前をあと3枚ほどと、"
        u"すれ違いの姿勢（両足が前後に近い瞬間）を数枚足せば、Catherine と同じ10ポーズに組めます。"
        u"9枚とも書き出してあるので、予備テイクは walk_prep.py の CYCLE を書き換えれば差し替えられます。"
        u"コマは 268x656。描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    # walk_prep measures the sides and writes the order it played; the anim has
    # to agree, so check rather than trust
    measured = json.load(open(os.path.join(HERE, "walk_cycle.json")))
    played = [i for i, _ in publish.timeline(
        os.path.join(HERE, "martin_walk_anim.py"))]
    if played != measured:
        raise SystemExit("the anim plays %s but walk_prep measured %s"
                         % (played, measured))

    publish.publish(
        name="martin_walk",
        frames_dir=os.path.join(OUT, "frames_walk"),
        prefix="wk",
        sheet_name="martin_walk_sheet.png",
        json_path=os.path.join(OUT, "martin_walk.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "martin_walk.gif"),
        anim_path=os.path.join(HERE, "martin_walk_anim.py"),
        labels=LABELS,
        note=NOTE,
        extra={"holds": {"slow": 7, "fast": 5}, "stepsPerMin": 120,
               "played": [2, 7, 6, 8], "spare": [0, 1, 3, 4, 5],
               "leftForward": [2, 7], "rightForward": [6, 8]},
    )
