# -*- coding: utf-8 -*-
"""Build the Catherine 'talk01' frames (talking, jacket off the shoulders).

Source: E:\\001_MAKETHEMFALLinlove素材庫\\Catherine\\talk_01\\*.png - nine separate
1122x1402 drawings.  First clip for this character; the pipeline is the one the
Martin clips use, and the character-agnostic half of it now lives in
blender/lib/spriteprep.py rather than in any one clip's prep.

  1. fit scale + translation of each drawing onto drawing 1, measured on the
     eyes (Catherine has no glasses, so the eyes and the bridge of the nose are
     the rigid landmark - the hair is enormous here and redrawn every take)
  2. freeze: emit every frame as one base drawing with only its own mouth
     patched in
  3. crop to the base's bounding box and write the frames + the sheet

Catherine sits differently in frame from Martin: the figure fills nearly the
whole width (x 0..1116 in the widest drawing) and the face is larger, so the
mouths are bigger too - x 271..302 / y 237..263 over all nine.

The patch outline clears four redrawn things:

    nose     bottom y 233, right edge x 268  -> top edge at y 234, left at 269
    jaw L    rises from the left: x 249 at y 258, x 274 at y 271
    jaw R    comes in from the right: x 316 at y 262, x 307 at y 271
    chin     the crease under a wide mouth (drawings 2 and 4) is *inside* the
             patch on purpose - it belongs to the mouth shape

Over the ramp ring the nine drawings differ by at most 10/255 (mean 2-4), with
nothing above 40 in any frame, and every drawn mouth pixel lands in the solid
part of the mask.

Run:  python talk01_prep.py
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import spriteprep as SP            # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(HERE))            # ...素材庫
CHAR = "Catherine"
SRC_DIR = os.path.join(BASE_DIR, CHAR, "talk_01")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_talk01")
SHEET = os.path.join(OUT, "catherine_talk01_sheet.png")
FITJSON = os.path.join(HERE, "talk01_fit.json")
PREFIX = "c1"

TARGET_H = 724                 # the same output height as the Martin set
MARGIN = 6
PAD = 48

TPL = (375, 300, 665, 430)     # source px of drawing 1: both eyes, no hair
SCALES = np.arange(0.900, 1.1201, 0.004)
SEARCH = 90

BASE = None                    # None -> medoid over the aligned face band

# the mouth, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(269, 234), (306, 234), (306, 262), (302, 268), (294, 272),
              (284, 271), (277, 266), (272, 259), (269, 250)]
PATCH_RAMP = 2

# No SP.hide_teeth here: neither talk clip draws teeth (the brightest thing in
# these mouths is the lower lip highlight, which is meant to stay).  joy_prep
# does need it - see there.

ALPHA_SNAP = 240               # the PNGs top out at alpha 253; snap the body
                               # opaque and keep the real antialiased outline


def main(write=True):
    paths = SP.order(glob.glob(os.path.join(SRC_DIR, "*.png")))
    print("%d drawings" % len(paths))

    if os.path.exists(FITJSON):
        fits = [tuple(f) for f in json.load(open(FITJSON))]
        print("fit: reusing", os.path.basename(FITJSON))
        for k, (s, dx, dy) in enumerate(fits):
            print("  drawing %2d: scale %.3f  shift (%+.0f,%+.0f)" % (k, s, dx, dy))
    else:
        print("fit (the eyes):")
        fits = SP.fit_all(paths, TPL, SCALES, SEARCH)
        json.dump(fits, open(FITJSON, "w"), indent=1)

    A = SP.aligned(paths, fits, TARGET_H, PAD)
    n, CH, CW = A.shape[:3]

    base = BASE
    if base is None:
        R = float(TARGET_H) / 1402.0
        x0, y0, x1, y1 = [int(round(v * R)) + PAD for v in TPL]
        band = A[:, y0:y1, x0:x1, :3].reshape(n, -1)
        cost = [float(np.abs(band - band[i]).mean()) for i in range(n)]
        base = int(np.argmin(cost))
        print("base drawing %d (face medoid, cost %.2f)" % (base, cost[base]))
    B = A[base]

    mm = SP.patch_mask((CH, CW), [PATCH_POLY], PATCH_RAMP, PAD)[..., None]
    print("patch %d px (%d solid)" % (int((mm > 0).sum()), int((mm > 0.999).sum())))

    frames = [np.clip(B * (1.0 - mm) + A[i] * mm + 0.5, 0, 255).astype(np.uint8)
              for i in range(n)]

    m = frames[base][..., 3] > 32
    ys = np.nonzero(m.sum(1))[0]
    xs = np.nonzero(m.sum(0))[0]
    cx0 = max(0, int(xs.min()) - MARGIN)
    cx1 = min(CW - 1, int(xs.max()) + MARGIN)
    cy0 = max(0, int(ys.min()) - MARGIN)
    cy1 = int(ys.max())                     # bottom is a cut, not a silhouette
    fw, fh = cx1 - cx0 + 1, cy1 - cy0 + 1
    fw += fw % 2
    fh += fh % 2
    cx1, cy1 = cx0 + fw - 1, cy0 + fh - 1
    print("frame %dx%d  crop x %d..%d y %d..%d" % (fw, fh, cx0, cx1, cy0, cy1))

    if not write:
        return fw, fh, n, base, A, frames

    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        if f.startswith(PREFIX + "_") and f.endswith(".png"):
            os.remove(os.path.join(FRAMES, f))
    sheet = Image.new("RGBA", (fw * n, fh), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        c = np.zeros((fh, fw, 4), np.uint8)
        sy, sx = min(CH, cy1 + 1), min(CW, cx1 + 1)
        c[:sy - cy0, :sx - cx0] = f[cy0:sy, cx0:sx]
        c[..., 3] = np.where(c[..., 3] >= ALPHA_SNAP, 255, c[..., 3])
        img = Image.fromarray(c)
        img.save(os.path.join(FRAMES, "%s_%02d.png" % (PREFIX, i)))
        sheet.paste(img, (i * fw, 0))
    sheet.save(SHEET)
    print("sheet:", sheet.size, "->", SHEET)
    return fw, fh, n, base


if __name__ == "__main__":
    main()
