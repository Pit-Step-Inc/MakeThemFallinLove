# -*- coding: utf-8 -*-
"""Build the 'pleasure' frames (Martin quietly pleased with himself).

Source: E:\001_MAKETHEMFALLinlove素材庫\Martin\pleasure\*.png - ten separate
1122x1402 drawings.  Same shape as anger / joy / sadness: one pose (hands in
the jacket pockets), ten takes, only the face differs.  This reuses anger_prep's
FFT fit with pleasure's own template.

This is the most tightly generated of the four sets - nine of the ten come back
at scale 1.000 and eight of them at zero shift - and also the subtlest: every
drawing is a shut, contented smile, and the whole range of them is 37x9 px
(x 299..335 / y 228..236).  Nothing here is a mouth *shape*; it is the same
smile drawn ten times a little differently, which is exactly the boil that the
freeze removes - so what is left after freezing reads as the smile breathing
rather than as the picture shaking.

One drawing (6) also carries a faint blush: four diagonal strokes at
x 270..295 / y 207..217, barely 10-25 levels off the skin.  It sits well clear
of the mouth, but the flat cheek between the two agrees to within 6 levels
across all ten drawings, so the two are held in a *single* polygon rather than
two - copying the cheek in between costs nothing and keeps the patch simple.

The outline still has to clear four things that are redrawn on every take:

    glasses  bottom rim at y 203..204   -> top edge at y 206
    nose     left edge x 328, bottom y 218
                                        -> notch: drop at x 326 to y 222
    jaw      rises to the left: y 247 at x 265, y 262 at x 302
    contour  right edge x 347 at y 236, x 339 at y 248

Measured over the ramp ring the ten drawings differ by at most 22/255 (mean 2),
with no pixel above 40 in any frame, and every drawn mouth pixel and every
blush stroke lands in the solid part of the mask.

Run:  python pleasure_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, "Martin", "pleasure")
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_pleasure")
SHEET = os.path.join(OUT, "martin_pleasure_sheet.png")
FITJSON = os.path.join(HERE, "pleasure_fit.json")
PREFIX = "pl"

TARGET_H = 724
MARGIN = 6
PAD = 48

TPL = (495, 315, 745, 400)     # source px of drawing 1: both lenses and the eyes
SCALES = np.arange(0.900, 1.1201, 0.004)
SEARCH = 90

BASE = None                    # None -> medoid over the aligned face band

# mouth + blush, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(265, 206), (326, 206), (326, 222), (341, 222), (341, 238),
              (336, 244), (326, 248), (302, 248), (288, 244), (274, 242),
              (265, 238)]
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
