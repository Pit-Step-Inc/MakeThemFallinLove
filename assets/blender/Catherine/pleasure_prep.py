# -*- coding: utf-8 -*-
"""Build the Catherine 'pleasure' frames (quietly pleased, a smile that opens).

Source: E:\001_MAKETHEMFALLinlove素材庫\Catherine\pleasure\*.png - ten separate
1122x1402 drawings.  Same standing pose as the other Catherine clips.  Every
drawing carries the blush, so it needs no patch of its own - freezing it onto
the base keeps it on screen throughout.

**The wink is patched in, but it needs a local refit first.**  Drawings 3 and 5
close one eye.  joy's diff-shaped patch applied straight to this set fails -
116-258 px above 40 across the ring, against joy's 5-25 - because the fits here
run to scale 1.036 with 14 px shifts, so the global misregistration reads as
"change" and drags the patch out over the whole upper head.  Refitting the
whole clip on the eye band is worse, not better (rms 33-71 against 19-29, ring
239-412), because a shut eye cannot match the template.

What does work is refining *locally*, just for the patch: shift the drawing by
whole pixels to best match the base over a region that deliberately excludes
the winking eye - the other eye and the nose bridge - and only then take the
difference.  What is left is the wink itself.  Drawing 5 then measures 24 px
above 40 across a 1100 px ring, joy's number, and the change lands on the eye
and lid: of 2132 px changed, only 250 are up in the hair.

Drawing 3 winks too but measures 90-104, three to four times that, so only
drawing 5's wink is used; drawing 3 contributes its mouth like the rest.

**The teeth are kept.**  Unlike joy's, they scale with the opening - 5, 11, 14,
19, 19, 23, 24 px on the seven closed smiles, then 42, 66, 92 on drawings 7, 6
and 4 - so they never appear at an opening where another drawing has none, and
there is nothing to flash.

The mouth outline, on flat cheek all the way round:

    nose   bottom y 234 at x 246..268
    jaw    y 266 at x 260, y 273 at x 278, y 279 at x 290
    cheek  right contour x 334 at y 246, x 316 at y 262

Every drawn mouth blob lands in the solid part of the mask, and over the ramp
ring the ten drawings differ by at most 8/255 (mean 1-4) with nothing above 40.

Run:  python pleasure_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, CHAR, "pleasure")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_pleasure")
SHEET = os.path.join(OUT, "catherine_pleasure_sheet.png")
FITJSON = os.path.join(HERE, "pleasure_fit.json")
PREFIX = "cp"

TARGET_H = 724                 # the same output height as the Martin set
MARGIN = 6
PAD = 48

TPL = (430, 400, 700, 560)     # source px: the nose and cheeks - NOT the eyes,
                               # two drawings shut them (see the docstring)
SCALES = np.arange(0.940, 1.0601, 0.004)
SEARCH = 60

BASE = None                    # None -> medoid over the aligned face band

# the mouth, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(264, 238), (272, 234), (284, 230), (300, 226), (310, 226),
              (314, 236), (312, 250), (307, 258), (302, 268), (288, 270),
              (276, 268), (268, 262), (264, 250)]
PATCH_RAMP = 2

# The wink.  REFINE_BOX is what the local refit is measured on and must not
# contain the winking eye; WINK_CORE is the eye itself, so only blobs reaching
# it are kept.
WINK_FRAMES = (5,)
REFINE_BOX = (170, 120, 300, 240)
WINK_BOX = (262, 132, 358, 224)
WINK_CORE = (276, 152, 348, 214)
WINK_GROW = 6


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

    # Nothing to hide: the teeth here rise with the opening (see the docstring),
    # so they never flash the way joy's did.

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

    frames = []
    for i in range(n):
        out = B * (1.0 - mm) + A[i] * mm
        if i in WINK_FRAMES:
            dx, dy = SP.refine_shift(A[i], B, tuple(v + PAD for v in REFINE_BOX))
            sh = np.roll(np.roll(A[i], dy, axis=0), dx, axis=1)
            wm = SP.diff_patch(sh, B, tuple(v + PAD for v in WINK_BOX),
                               tuple(v + PAD for v in WINK_CORE), grow=WINK_GROW)[..., None]
            print("  drawing %d: wink patch %d px (local refit %+d,%+d)"
                  % (i, int((wm > 0.999).sum()), dx, dy))
            out = out * (1.0 - wm) + sh * wm
        frames.append(np.clip(out + 0.5, 0, 255).astype(np.uint8))

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
