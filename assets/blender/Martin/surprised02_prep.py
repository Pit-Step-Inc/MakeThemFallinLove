# -*- coding: utf-8 -*-
"""Build the 'surprised02' frames (Martin caught off guard).

Source: E:\001_MAKETHEMFALLinlove素材庫\Martin\surprised\*.png - ten separate
1122x1402 drawings.  Named 02 because martin_surprised already exists: that one
is the six drawing set from the first pass (362x724, centroid aligned, not
frozen).  This is a separate, longer clip, not a replacement.

Same recipe as anger / joy / sadness / pleasure: one pose (hands in the jacket
pockets), ten takes, only the face differs.  The mouths run from a small "o" to
a wide gasp - x 305..333 / y 223..255 over all ten, the tallest mouth range of
any of the sets.

**The eyes cannot be patched, so the base carries them.**  Three of the ten
(3, 4, 5) draw the eyes wide, which is the other half of a surprise - but they
draw the *glasses* differently with them: at their best offset the rim overlaps
the base's by only 0.67-0.75 IoU, against 0.81-0.87 for the rest.  A blink or
eye patch works in talk / talkhand only because its seam lands on a rim that is
identical in both drawings, and here it is not.

Rather than lose the wide eyes, drawing 4 - the roundest of the three - is
pinned as the base instead of the medoid (which would pick drawing 0, with
ordinary eyes).  The whole clip then stares, and the mouth does the acting.
This costs nothing at the seam: the ramp ring is quiet for *every* choice of
base here (max 11-16 of 255, nothing above 40), so the base is free to be
chosen on expression alone.

The outline clears the four redrawn things as usual:

    glasses  bottom rim at y 206         -> top edge at y 221
    nose     left edge x 327, bottom y 219
    jaw      rises to the left: y 250 at x 270, y 262 at x 303
    contour  right edge x 347 at y 236, x 333 at y 256

Run:  python surprised02_prep.py
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import freeze_talk as FZ           # noqa: E402  (ramp_mask)
import anger_prep as AP            # noqa: E402  (order / fit_all / aligned)

BASE_DIR = os.path.dirname(os.path.dirname(HERE))            # ...素材庫
SRC_DIR = os.path.join(BASE_DIR, "Martin", "surprised")
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_surprised02")
SHEET = os.path.join(OUT, "martin_surprised02_sheet.png")
FITJSON = os.path.join(HERE, "surprised02_fit.json")
PREFIX = "s2"

TARGET_H = 724
MARGIN = 6
PAD = 48

TPL = (500, 305, 745, 400)     # source px of drawing 1: both lenses and the eyes
SCALES = np.arange(0.900, 1.1201, 0.004)
SEARCH = 90

BASE = 4                       # not the medoid: see the docstring - drawing 4
                               # is the one with the widest eyes

# the mouth, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(301, 221), (341, 221), (341, 236), (337, 244), (334, 250),
              (331, 256), (324, 261), (314, 261), (306, 256), (301, 248)]
PATCH_RAMP = 2
                               # between the nose's last row (217) and the top
                               # of drawing 5's laugh (219) is a single row

ALPHA_SNAP = 240               # the PNGs top out at alpha 253; snap the body
                               # opaque and keep the real antialiased outline


def main(write=True):
    paths = AP.order(glob.glob(os.path.join(SRC_DIR, "*.png")))
    print("%d drawings" % len(paths))

    if os.path.exists(FITJSON):
        fits = [tuple(f) for f in json.load(open(FITJSON))]
        print("fit: reusing", os.path.basename(FITJSON))
        for k, (s, dx, dy) in enumerate(fits):
            print("  drawing %2d: scale %.3f  shift (%+.0f,%+.0f)" % (k, s, dx, dy))
    else:
        print("fit (glasses/eye band):")
        fits = AP.fit_all(paths, tpl_box=TPL, scales=SCALES, search=SEARCH)
        json.dump(fits, open(FITJSON, "w"), indent=1)

    A = AP.aligned(paths, fits, target_h=TARGET_H, pad=PAD)
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

    poly = [(x + PAD, y + PAD) for x, y in PATCH_POLY]
    mm = FZ.ramp_mask((CH, CW), poly, PATCH_RAMP)[..., None]
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
