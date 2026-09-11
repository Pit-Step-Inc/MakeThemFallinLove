#!/usr/bin/env python3
"""
開発用の静的サーバー（Range リクエスト対応）

`python -m http.server` は Range を無視して常に 200 + 全体を返すため、
Chrome のメディアパイプラインが <audio> / <video> のロードを開始せず、
readyState=0 のまま固まる（BGM が鳴らない）。
本番ホスト（GitHub Pages / Netlify / Vercel / nginx）は Range 対応なので、
開発時だけこのサーバーを使えば挙動が揃う。

    python tools/serve.py [port]
"""

import os
import re
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeRequestHandler(SimpleHTTPRequestHandler):
    """206 Partial Content を返せる SimpleHTTPRequestHandler"""

    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        # 開発中は素材の差し替えを即反映させたい
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5173
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    handler = partial(RangeRequestHandler, directory=root)
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"serving {root}")
        print(f"  http://127.0.0.1:{port}/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
