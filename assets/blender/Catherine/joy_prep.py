# -*- coding: utf-8 -*-
"""Build the Catherine 'joy' frames (a smile that turns into a laugh).

Source: E:\001_MAKETHEMFALLinlove素材庫\Catherine\joy\*.png - nine separate
1122x1402 drawings.  (This replaces an earlier ten drawing set that used to
live in the same folder; those files are gone.  The earlier set drew teeth on
two of its ten mouths and needed spriteprep.hide_teeth to stop them flashing -
these nine draw no teeth, but drawing 7 keeps a small enamel glint inside
the mouth's left corner - eight pixels, on that drawing only, so it winks on
and off with the cut.  hide_teeth is run with min_px=5 to catch it and reports
zero on the other eight.)

Same standing pose as talk01; the mouth runs from a small closed smile to a
wide open laugh, and every drawing carries the blush, so the blush needs no
patch of its own - freezing it onto the base keeps it on screen throughout.

**The fit is on the nose and cheeks, not the eyes.**  Drawing 5 shuts its eyes
in a happy squint and drawing 4 goes half lidded, and an eye band template
cannot match a shut eye: fitting drawing 5 that way ran the search to the end
of the scale range (1.100, shifted -57,-61, rms 73).  A band under the eyes -
source x 430..700 / y 400..560, the nose, both cheeks and the mouth - fits all
nine, agrees with the eye band to within 5 source px on the eight drawings the
eye band could handle, and is the landmark next to the patch anyway.

Those two expressions ARE kept, with a second patch of a different kind.  A
traced polygon around an eye does not work - it has to cut through the lid
crease, the lashes or the bangs, and the ramp then straddles an edge the two
drawings disagree about (measured: 237-252 of 255 across the ring, against 11
for the mouth).  Shaping the mask from the difference itself instead puts the
seam exactly where the drawings already agree; over that ring drawing 5
measures 133 max / 5.1 mean with 25 px above 40, all of them single strands of
bangs, and drawing 4 measures 101 / 3.7 with 5.  At 1:1 neither is findable.
This is freeze_talk's blink patch, generalised as spriteprep.diff_patch.

The mouth outline, on flat cheek all the way round:

    nose   bottom y 233, right edge x 268
    jaw L  y 267 at x 266, y 271 at x 271
    jaw R  y 273 at x 276, y 278 at x 296
    cheek  right contour x 334 at y 246, x 318 at y 262

Every drawn mouth pixel lands in the solid part of the mask, and over the ramp
ring the nine drawings differ by at most 11/255 (mean 1-3) with nothing above
40 in any frame.

Run:  python joy_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, CHAR, "joy")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_joy")
SHEET = os.path.join(OUT, "catherine_joy_sheet.png")
FITJSON = os.path.join(HERE, "joy_fit.json")
PREFIX = "cj"

TARGET_H = 724                 # the same output height as the Martin set
MARGIN = 6
PAD = 48

TPL = (430, 400, 700, 560)     # source px: the nose and cheeks - NOT the eyes,
                               # two drawings shut them (see the docstring)
SCALES = np.arange(0.940, 1.0601, 0.004)
SEARCH = 60

BASE = None                    # None -> medoid over the aligned face band

# the mouth, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(261, 236), (270, 233), (278, 228), (290, 224), (312, 224),
              (313, 240), (310, 252), (305, 261), (298, 268), (285, 269),
              (274, 266), (266, 261), (262, 252)]
PATCH_RAMP = 2

# The eyes of drawings 4 (half lidded) and 5 (shut, a contented squint) are
# patched in as well.  Their mask is not traced: see SP.diff_patch.  The box
# has to be wide enough that the grown mask never touches its edge, or the clip
# becomes the seam - at 175,124..358,242 the changed region stops at x 182..357
# / y 124..241 and the 6 px growth still fits.
EYE_FRAMES = (4, 5)
EYE_BOX = (175, 124, 358, 242)
EYE_CORE = (185, 150, 340, 220)
EYE_GROW = 6

# Some takes draw a strip of teeth in the open mouth and some do not, at the
# same opening, so cut against each other they flash on and off.  They are
# painted out before the freeze; the box keeps the (also bright and neutral)
# nose highlight out of it.  A no-op on drawings that have no teeth.
HIDE_TEETH_BOX = (258, 222, 318, 272)
SKIN = (251, 182, 146)

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

    box = tuple(v + PAD for v in HIDE_TEETH_BOX)
    hid = 0
    for i in range(n):
        k = SP.hide_teeth(A[i], box, SKIN, min_px=5, verbose=False)
        if k:
            print("  drawing %d: %d teeth px painted out" % (i, k))
        hid += k
    print("teeth hidden: %d px total" % hid)

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
        m = mm
        if i in EYE_FRAMES:
            em = SP.diff_patch(A[i], B,
                               tuple(v + PAD for v in EYE_BOX),
                               tuple(v + PAD for v in EYE_CORE),
                               grow=EYE_GROW)[..., None]
            print("  drawing %d: eye patch %d px" % (i, int((em > 0.999).sum())))
            m = np.maximum(mm, em)
        frames.append(np.clip(B * (1.0 - m) + A[i] * m + 0.5, 0, 255).astype(np.uint8))

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
