# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for Catherine's 'walk' clip.

The work is in blender/lib/clip_publish.py; this file is just walk's arguments.

Run:  python walk_publish.py      (after walk_prep.py)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import clip_publish                # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(BASE_DIR, "blender", "develop", "Catherine")

# by drawing number, not by play order: where each drawing sits in its half,
# counting from that half's footfall (see the cycle 9 8 3 4 5 / 6 2 7 0 1)
LABELS = ["down_R4", "pass_R", "down_R2", "down_L3", "down_L4",
          "pass_L", "down_R1", "down_R3", "down_L2", "down_L1"]

NOTE = (u"歩き（正面・10コマ・ループ）。**顔クリップとは作りが違います**。"
        u"顔クリップは1枚のベースに凍結して動く所だけパッチしますが、歩きは"
        u"脚も腰も上着も全部動くので**凍結できる場所がありません**"
        u"（10枚の差分を40pxブロックで測ると 頭79／胴103／脚59・ブロック平均40〜235で"
        u"静かな所が無い）。太ももを横一直線で切る案と下半身の差分パッチ案は"
        u"4枚版のときに作って計測し、どちらも破棄しました（前者は太ももの内側の陰影が"
        u"段になる、後者はリング40超えが271〜468px）。**10枚をそのまま回します**。"
        u"そのぶんフィットを詰めてあり、**スケールは点数付けでなく実測**です: "
        u"顔と腰の枠を別々に位置決めして、その**間隔（290px）とコマ0の間隔の比**を"
        u"スケールにします（どちらの枠がよく一致したかは効きません）。平行移動は顔から。"
        u"枠を採点する方式より全指標で良く、目→腰の距離のばらつきが 5.0%→**2.1%**、"
        u"目→ショーツ裾が 6.0%→**3.2%**、最下点の幅が 64→**42px**。"
        u"頭は動きません（**10枚の虹彩が x 3.7px・y 1.7px 以内**）。"
        u"**再生順は素材の並び順ではなく実測した歩行位相です**。"
        u"前足＝靴底が低い方（正面なので手前の足）、"
        u"前後の距離＝**前後の靴の面積比**（手前の靴が大きく描かれる／スケールに依らない）。"
        u"これで5枚ずつ2つの半周期に分かれ、各半周期は接地→すれ違いへ進みます: "
        u"左が前 9(1.84) 8(1.76) 3(1.78) 4(1.68) 5(1.36) ／ "
        u"右が前 6(1.81) 2(1.78) 7(1.63) 0(1.61) 1(1.31)。"
        u"半周期を連続に保つ28800通りの巡回路を脚領域の画素差で全探索した結果、"
        u"**接地→すれ違いを守る中での最小が この順（203.0）**で、"
        u"全体最小（200.0／1.5%だけ小さい）は片方の半周期を逆走するので歩きになりません。"
        u"コスト40と34の2ステップが2回の足の着地（後ろ足が地面を離れて振り出される所）で、"
        u"残り8ステップは11〜23です。"
        u"**テンポは保持フレーム数で決まります**。10コマ＝1周期＝2歩。均一な保持だと 288/保持 歩/分で、"
        u"保持2＝毎分144歩（急いで見える）・保持3＝毎分96歩（のんびり）の**2択しかありません**"
        u"（保持は整数フレームのため）。そこで**不均等にしています**: "
        u"接地直後の2カットを3フレーム（体重が乗る＝両足接地でゆっくり）、"
        u"振り出しの3カットを2フレーム。半周期12F・1周期**24F＝ちょうど1.00秒＝毎分120歩**で、"
        u"普通に歩く速さです。接地を長く持つのは妥協ではなく歩きのタイミングそのものです。"
        u"**規則は1つだけ: 左右の半周期に同じパターンを入れること**（違えると足を引きずって見えます／"
        u"anim 側で assert しています）。速くするなら両方2（0.83秒・毎分144歩）、"
        u"遅くするなら両方3（1.25秒・毎分96歩）。"
        u"**縦のぶれは相似変換では取れないので、縦だけ区分的に伸縮しています**。"
        u"フィット後でも 胴（目→裾）は3.3%しかぶれないのに **脚（裾→靴底）は11.6%** ぶれ、"
        u"しかも同じ動きであるはずの左右の半周期が食い違っていました"
        u"（脚長 354 349 363 377 391 対 374 359 353 354 355）。"
        u"そこで縦スケールを2つの行で切り替えます: 目より上は素のまま、"
        u"胴は目→裾が全コマ平均になるように、脚は**半周期の同じ位置どうしが同じ脚長になる**ように。"
        u"写像は両方の行で連続なので継ぎ目は出ません。結果は "
        u"**胴 3.3%→0.5% ／ 脚 11.6%→5.5%（残りは歩幅そのもの・左右の半周期が1行以内で一致）"
        u"／ 靴底のばらつき 42px→21px**。倍率は胴 0.985〜1.018・脚 0.954〜1.051 に収まります。"
        u"元々あった1回のリサンプルに畳み込んでいるので**鮮鋭度は変わりません**"
        u"（縦のソフトエッジ率 17.0〜18.1% → 16.9〜18.2%）。"
        u"仕上げに、髪を含まない目と鼻の枠で**整数1px単位の微調整**を掛けています"
        u"（フィットの平行移動は髪入りの枠から来ていて1〜2pxずれるため／虹彩のばらつき 3.8px→2.9px）。"
        u"**残るのは髪と上着のボイリングだけ**で、これは10枚が別々に生成されている以上、"
        u"位置合わせでは消せません。"
        u"コマは 326x762。描画時は必ず JSON の frameWidth/frameHeight を参照してください。")

if __name__ == "__main__":
    # the prep measures the walk phase from the drawings and writes the order it
    # found; the anim has to be playing that order, so check rather than trust
    measured = json.load(open(os.path.join(HERE, "walk_cycle.json")))
    played = [i for i, _ in clip_publish.timeline(
        os.path.join(HERE, "catherine_walk_anim.py"))]
    if played != measured:
        raise SystemExit("the anim plays %s but walk_prep measured %s"
                         % (played, measured))

    clip_publish.publish(
        name="catherine_walk",
        frames_dir=os.path.join(OUT, "frames_walk"),
        prefix="wk",
        sheet_name="catherine_walk_sheet.png",
        json_path=os.path.join(OUT, "catherine_walk.json"),
        gif_path=os.path.join(BASE_DIR, "blender", "gifまとめ", "catherine_walk.gif"),
        anim_path=os.path.join(HERE, "catherine_walk_anim.py"),
        labels=LABELS,
        note=NOTE,
        extra={"holds": {"slow": 3, "fast": 2}, "stepsPerMin": 120,
               "leftForward": [9, 8, 3, 4, 5], "rightForward": [6, 2, 7, 0, 1],
               "footfallFrames": [9, 6], "passFrames": [5, 1]},
    )
