# -*- coding: utf-8 -*-
"""Rebuild the Martin 'talk' frames from the drawn 5x4 sheet.

  1. grid_prep    - cut the 20 cells and lock every one of them on the face
  2. freeze_talk  - emit each frame as one base drawing with only its own mouth
                    patched in, plus a single blink
  3. re-emit the sprite sheet

Why step 2 exists: the 20 cells are 20 separate hand drawings, so registering
them stops the figure *travelling* but not the outlines being redrawn a pixel
off every cell - the picture boils.  Freezing everything except the mouth keeps
all 20 drawn mouth shapes and stops everything else dead.

Run:  python talk_pipeline.py
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import grid_prep          # noqa: E402
import freeze_talk        # noqa: E402

BASE = os.path.dirname(os.path.dirname(HERE))          # ...素材庫
SRC = os.path.join(BASE, "Martin", "001_talk.png")
OUT = os.path.join(BASE, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_talk")
SHEET = os.path.join(OUT, "martin_talk_sheet.png")
PREFIX = "t"


def main():
    for f in os.listdir(FRAMES) if os.path.isdir(FRAMES) else []:
        if f.startswith(PREFIX + "_") and f.endswith(".png"):
            os.remove(os.path.join(FRAMES, f))

    fw, fh, n = grid_prep.separate(
        SRC, FRAMES, SHEET, PREFIX,
        check_png=r"E:\americanwomen\renders\grid_check.png")
    print("freeze:")
    base = freeze_talk.freeze(FRAMES, PREFIX)

    sheet = Image.new("RGBA", (fw * n, fh), (0, 0, 0, 0))
    for k in range(n):
        sheet.paste(Image.open(os.path.join(FRAMES, "%s_%02d.png" % (PREFIX, k))),
                    (k * fw, 0))
    sheet.save(SHEET)
    print("sheet rebuilt:", sheet.size, "->", SHEET)
    return fw, fh, n, base


if __name__ == "__main__":
    main()
