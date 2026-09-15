"""
生成した背景の置き場

**同じコードを Render でも Vercel でも動かすための層**（store.py と同じ趣旨）。

  - Render / 手元 … assets/generated/ にファイルとして置く（今までどおり）
  - Vercel        … Vercel Blob。環境変数が入っていればこちらに切り替わる

Vercel のファイルシステムは読み取り専用で、書けるのは /tmp だけ。しかも
インスタンス間で共有されず消えるので、絵を置いておけない。

**Render 側にも利点がある。** いまは assets/generated/ に置いていて、
再デプロイでプロセスが替わると `_trim_images()` が「生きていない部屋の絵」と
判定して全部消してしまう。Blob に出せば置き場がプロセスの寿命と無関係になる。
"""

import io
import json
import os
import urllib.error
import urllib.request

#: api/_lib/ から見て2つ上がプロジェクト直下
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: ファイルとして置くときの場所と、そこを指す URL
OUT_DIR = os.path.join(ROOT, "assets", "generated")
OUT_URL = "assets/generated"

#: Blob に置くときの鍵。Vercel の Storage で作ると自動で入る
BLOB_TOKEN = str(os.environ.get("BLOB_READ_WRITE_TOKEN") or "").strip()

#: Blob を使うか。**環境変数があるときだけ。**
USE_BLOB = bool(BLOB_TOKEN)

#: Blob の投入口
BLOB_API = "https://blob.vercel-storage.com"


def where():
    """いまどちらで動いているか。起動時のログ用"""
    return "blob" if USE_BLOB else "disk"


def _put_disk(name, data):
    os.makedirs(OUT_DIR, exist_ok=True)
    with io.open(os.path.join(OUT_DIR, name), "wb") as f:
        f.write(data)
    # クライアントは index.html からの相対で読む
    return f"{OUT_URL}/{name}"


def _put_blob(name, data):
    """
    Blob に上げて、公開 URL を返す。

    **addRandomSuffix は使わない。** 名前は `<部屋コード>_<乱数>.png` で
    こちらが既に一意にしているし、付けられると返る URL が読みにくくなる。
    """
    req = urllib.request.Request(
        f"{BLOB_API}/{name}",
        data=data,
        headers={
            "Authorization": f"Bearer {BLOB_TOKEN}",
            "Content-Type": "image/png",
            "x-api-version": "7",
            "x-content-type": "image/png",
            "x-add-random-suffix": "0",
            # 絵は一度作ったら変わらない。長く持たせて配信を軽くする
            "x-cache-control-max-age": "31536000",
        },
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.load(res)["url"]


def put(name, data):
    """
    絵を1枚置いて、**クライアントがそのまま <img src> に入れられる文字列**を返す。

    ディスクのときは相対パス、Blob のときは絶対 URL。どちらでも
    ブラウザからは同じように読めるので、呼び出し側は区別しなくてよい。

    @param name `ABCD_1a2b3c.png` のような一意な名前
    @param data PNG のバイト列
    """
    return _put_blob(name, data) if USE_BLOB else _put_disk(name, data)


def trim(live_codes):
    """
    使われなくなった絵を片付ける。**ディスクのときだけ。**

    Blob は容量課金で、消さなくても困らない。むしろ「生きている部屋」の
    判定はプロセスの記憶に依存していて、Vercel では当てにならないので、
    消しにいくほうが危ない（他の人が遊んでいる最中の絵を消しかねない）。
    """
    if USE_BLOB:
        return
    try:
        names = [n for n in os.listdir(OUT_DIR) if n.endswith(".png")]
    except OSError:
        return
    live = set(live_codes)
    for name in names:
        if name.split("_", 1)[0] in live:
            continue
        try:
            os.remove(os.path.join(OUT_DIR, name))
        except OSError:
            pass
