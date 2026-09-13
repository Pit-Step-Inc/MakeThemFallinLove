#!/usr/bin/env python3
"""
開発用の静的サーバー（Range リクエスト対応 + ルーム API）

`python -m http.server` は Range を無視して常に 200 + 全体を返すため、
Chrome のメディアパイプラインが <audio> / <video> のロードを開始せず、
readyState=0 のまま固まる（BGM が鳴らない）。
本番ホスト（GitHub Pages / Netlify / Vercel / nginx）は Range 対応なので、
開発時だけこのサーバーを使えば挙動が揃う。

`/api/` 以下は tools/rooms.py に回して、同じ部屋に居る人どうしで
Prompt とカウントダウンを共有する。静的配信と同じプロセスに相乗りさせて
あるので、これ1つ立てれば複数人で遊べる。

    python tools/serve.py [port]
"""

import json
import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rooms  # noqa: E402  同じフォルダに置いてある

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")

#: この下に来たリクエストは静的ファイルではなくルーム API に回す
API_PREFIX = "/api/"

#: 公開時だけキャッシュを許す拡張子。中身が変わらないものだけ
CACHEABLE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp",
                 ".ogg", ".m4a", ".wav", ".mp3", ".ttf", ".woff", ".woff2"}

#: Render などに載せたときは 1 になる。開発中と挙動を分けるのはキャッシュだけ
PRODUCTION = bool(os.environ.get("MTFIL_PRODUCTION") or os.environ.get("RENDER"))


class RangeRequestHandler(SimpleHTTPRequestHandler):
    """206 Partial Content を返せる SimpleHTTPRequestHandler"""

    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        # _json は自前で no-store を付けるので、二重に出さない
        if not getattr(self, "_cache_sent", False):
            self.send_header("Cache-Control", self._cache_control())
        super().end_headers()

    def _cache_control(self):
        """
        素材をキャッシュさせるかどうか。

        開発中は差し替えを即反映させたいので常に no-cache。
        公開時は**素材が 380MB 近くある**ので、毎回問い合わせに行かせると
        読み込みが重くなる。中身が変わらないものだけ抱えさせて、
        入れ物（html / js / css）は毎回確かめさせる。
        """
        if not PRODUCTION:
            return "no-cache"
        path = urlsplit(self.path).path
        ext = os.path.splitext(path)[1].lower()
        if path.startswith("/assets/generated/"):
            # 部屋ごとに作られて部屋と一緒に消える。抱え込ませない
            return "no-cache"
        if ext in CACHEABLE_EXT:
            return "public, max-age=3600"
        return "no-cache"

    # -----------------------------------------------------------
    #  ルーム API（tools/rooms.py）
    #
    #  同じ部屋に居る人どうしで Prompt とカウントダウンを共有する。
    #  静的配信と同じプロセスに相乗りさせてあるので、
    #  `python tools/serve.py` だけで複数人で遊べる。
    # -----------------------------------------------------------

    def do_GET(self):
        if self.path.startswith(API_PREFIX):
            return self._api("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith(API_PREFIX):
            return self._api("POST")
        self.send_error(405, "Method Not Allowed")

    def _api(self, method):
        parts = urlsplit(self.path)
        body = None
        if method == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                return self._json(400, {"error": "invalid json"})

        status, obj = rooms.handle(method, parts.path, parse_qs(parts.query), body)
        self._json(status, obj)

    def _json(self, status, obj):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        # 状態はポーリングで取りに来るので、絶対にキャッシュさせない
        self.send_header("Cache-Control", "no-store")
        self._cache_sent = True
        self.end_headers()
        self.wfile.write(payload)

    def send_head(self):
        range_header = self.headers.get("Range")
        if not range_header:
            return super().send_head()

        m = RANGE_RE.match(range_header.strip())
        if not m:
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()

        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        size = os.fstat(f.fileno()).st_size
        start_s, end_s = m.group(1), m.group(2)

        if start_s == "":
            # bytes=-N … 末尾 N バイト
            if end_s == "":
                f.close()
                self.send_error(400, "Invalid Range")
                return None
            length = min(int(end_s), size)
            start = size - length
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
            end = min(end, size - 1)

        if start >= size or start > end:
            f.close()
            self.send_response(416, "Requested Range Not Satisfiable")
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None

        length = end - start + 1
        self.send_response(206, "Partial Content")
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        f.seek(start)
        self._remaining = length
        return _LimitedReader(f, length)


class _LimitedReader:
    """copyfile() に渡すための、length バイトで止まる読み出し口"""

    def __init__(self, fp, length):
        self.fp = fp
        self.remaining = length

    def read(self, n=-1):
        if self.remaining <= 0:
            return b""
        if n is None or n < 0 or n > self.remaining:
            n = self.remaining
        data = self.fp.read(n)
        self.remaining -= len(data)
        return data

    def close(self):
        self.fp.close()


def main():
    # Render などは待ち受けポートを $PORT で渡してくる
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT") or 5173)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    handler = partial(RangeRequestHandler, directory=root)
    # 同じ LAN の別の端末からも入れるように 0.0.0.0 で待つ。
    # 一人で遊ぶぶんには 127.0.0.1 のままで構わない
    host = os.environ.get("MTFIL_HOST", "0.0.0.0")
    with ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"serving {root}")
        print(f"  http://127.0.0.1:{port}/")
        if host == "0.0.0.0":
            print(f"  （同じ LAN の他の端末からは http://<このPCのIP>:{port}/ ）")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
