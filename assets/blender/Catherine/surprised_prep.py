# -*- coding: utf-8 -*-
"""Build the Catherine 'surprised' frames (caught off guard).

Source: E:\001_MAKETHEMFALLinlove素材庫\Catherine\surprised\*.png - nine separate
1122x1402 drawings.  Same standing pose as the other Catherine clips; the mouth
runs from a small line to a wide gasp.

**The eyes are patched, so the surprise arrives during the clip.**  The base is
the medoid (drawing 1), whose eyes are ordinary, and drawings 2, 3 and 4 - which
widen the eyes and lift the brows - have that patched in on top of their mouths.
The clip therefore opens on a normal face and reacts.

This is pleasure's recipe (refit locally on a band that excludes the eyes, then
shape the mask from the difference) applied per eye rather than to both at once.
It does not measure as cleanly as pleasure's wink did - 129-216 px above 40
across the ring against pleasure's 24 - because a wink is one small change on an
otherwise unchanged face, while here both eyes widen and both brows lift, so
more of the upper face is genuinely different.  Left alone it also drags the bangs in - of the 6900 px drawing 4 changed, 1100
were hair directly above the eyes - and a bang shifting a pixel reads as the
hairstyle twitching, which is worse than the boil it was meant to remove.
Tightening the mask does not help (the share stays 16-20% at every tol/grow),
because those bangs really are drawn differently.

**So the hair is subtracted from the mask.**  Hair here is the one thing on the
face with a strong yellow cast - G-B is 106 on the bangs against 36 on skin -
so keying on that and growing it three pixels (to catch its dark outline) marks
it, and removing it from the patch freezes it: the bangs of both drawings keep
the base's pixels, and the seam falls on the hair edge, where the skin either
side is flat and identical.  Hair pixels changed drops from 1100 to **zero**,
and what is left above the eyes - about 210 px - is the brows, which are
supposed to move.

The mouth outline, on flat cheek all the way round:

    nose   bottom y 231 at x 246..267
    jaw    y 266 at x 260, y 270 at x 272, y 279 at x 290
    cheek  right contour x 333 at y 244, x 314 at y 264

Run:  python surprised_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, CHAR, "surprised")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_surprised")
SHEET = os.path.join(OUT, "catherine_surprised_sheet.png")
FITJSON = os.path.join(HERE, "surprised_fit.json")
PREFIX = "cu"

TARGET_H = 724                 # the same output height as the Martin set
MARGIN = 6
PAD = 48

TPL = (430, 400, 700, 560)     # source px: the nose and cheeks - NOT the eyes,
                               # two drawings shut them (see the docstring)
SCALES = np.arange(0.940, 1.0601, 0.004)
SEARCH = 60

BASE = 4                       # not the medoid: see the docstring - drawing 4
                               # has the widest eyes and the highest brows

# the mouth, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(266, 235), (272, 229), (284, 227), (300, 227), (308, 234),
              (307, 250), (303, 260), (296, 268), (284, 270), (274, 266),
              (268, 260), (265, 248)]
PATCH_RAMP = 2



# Some takes draw a strip of teeth in the open mouth and some do not, at the
# same opening, so cut against each other they flash on and off.  They are
# painted out before the freeze; the box keeps the (also bright and neutral)
# nose highlight out of it.  A no-op on drawings that have no teeth.
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

    # Nothing to hide: none of these mouths draws teeth.

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
