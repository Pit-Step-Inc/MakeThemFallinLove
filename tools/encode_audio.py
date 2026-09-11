#!/usr/bin/env python3
"""
配信用オーディオの書き出し

assets/ 以下の wav（制作マスター）から、Web 配信用の圧縮版を作る。

  - .ogg (Opus)  … 最も軽い。Chrome / Firefox / Edge 向けの本命。
                    Ogg の pre-skip が正しく扱われるためループが継ぎ目なく繋がる。
  - .m4a (AAC)   … Safari / iOS 用のフォールバック。全ブラウザで再生できる。

wav マスターは消さずに残す。差分がなければ再エンコードはスキップする。

    python tools/encode_audio.py           # 更新分だけ
    python tools/encode_audio.py --force   # 全部やり直す
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (ディレクトリ, Opus ビットレート, AAC ビットレート)
TARGETS = [
    ("assets/BGM", "96k", "128k"),   # 楽曲。長いので音質優先
    ("assets/SE", "64k", "96k"),     # 効果音。短いので軽さ優先
]


def find_ffmpeg():
    """PATH → winget のインストール先 の順に探す"""
    from shutil import which

    exe = which("ffmpeg")
    if exe:
        return exe

    # winget でインストール直後は PATH がまだ通っていないことがある
    base = os.path.join(
        os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages"
    )
    if os.path.isdir(base):
        for dirpath, _dirnames, filenames in os.walk(base):
            if "ffmpeg.exe" in filenames:
                return os.path.join(dirpath, "ffmpeg.exe")

    return None


def mb(path):
    return os.path.getsize(path) / (1024 * 1024)


def needs_rebuild(src, dst, force):
    if force or not os.path.exists(dst):
        return True
    return os.path.getmtime(src) > os.path.getmtime(dst)


def run(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr[-2000:] + "\n")
        raise SystemExit(f"ffmpeg failed: {' '.join(cmd[:2])} ...")


def main():
    force = "--force" in sys.argv

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise SystemExit(
            "ffmpeg が見つかりません。\n"
            "  winget install Gyan.FFmpeg\n"
            "を実行してから、シェルを開き直してください。"
        )
    print(f"ffmpeg: {ffmpeg}\n")

    rows = []
    for rel_dir, opus_br, aac_br in TARGETS:
        d = os.path.join(ROOT, rel_dir)
        if not os.path.isdir(d):
            continue

        for name in sorted(os.listdir(d)):
            if not name.lower().endswith(".wav"):
                continue

            src = os.path.join(d, name)
            stem = os.path.splitext(src)[0]
            ogg, m4a = stem + ".ogg", stem + ".m4a"

            if needs_rebuild(src, ogg, force):
                print(f"  opus  {rel_dir}/{name}")
                run([ffmpeg, "-y", "-loglevel", "error", "-i", src,
                     "-c:a", "libopus", "-b:a", opus_br, "-vbr", "on",
                     "-compression_level", "10", "-application", "audio", ogg])

            if needs_rebuild(src, m4a, force):
                print(f"  aac   {rel_dir}/{name}")
                run([ffmpeg, "-y", "-loglevel", "error", "-i", src,
                     "-c:a", "aac", "-b:a", aac_br,
                     "-movflags", "+faststart", m4a])

            rows.append((f"{rel_dir}/{os.path.splitext(name)[0]}",
                         mb(src), mb(ogg), mb(m4a)))

    if not rows:
        print("no wav files to encode")
        return

    print()
    print(f"{'':44} {'wav':>9} {'ogg':>9} {'m4a':>9}   {'saved(ogg)':>11}")
    print("-" * 90)
    tw = to = tm = 0.0
    for name, w, o, m in rows:
        tw, to, tm = tw + w, to + o, tm + m
        print(f"{name:44} {w:8.2f}M {o:8.2f}M {m:8.2f}M   {100 * (1 - o / w):9.1f}%")
    print("-" * 90)
    print(f"{'TOTAL':44} {tw:8.2f}M {to:8.2f}M {tm:8.2f}M   {100 * (1 - to / tw):9.1f}%")


if __name__ == "__main__":
    main()
