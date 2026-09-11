# -*- coding: utf-8 -*-
"""Build the 'sadness' frames (Martin's face falls, and one drawing cries).

Source: E:\\001_MAKETHEMFALLinlove素材庫\\Martin\\sadness\\*.png - ten separate
1122x1402 drawings.  Same shape as anger / joy: one pose (hands in the jacket
pockets), ten takes, only the face differs.  This reuses anger_prep's FFT fit
with sadness's own template; the heads run from 1.000 to 1.060 here, the widest
spread of the three sets.

Two patches, not one, because the two things that move are far apart:

  mouth  a small downturned line, x 301..326 / y 229..240 over all ten - the
         whole range is barely 26x12 px, so the frown only trembles.
  tear   drawing 5 alone cries: a drop on the left cheek, x 262..271 /
         y 205..221.  It is its own polygon rather than part of the mouth's -
         joining them would drag the patch across the nose, which is redrawn
         on every take.

The tear costs one compromise.  It is drawn running *through* the glasses rim
and out onto the cheek, and the rim's bottom row is not the same on every take
(y 202 on drawing 4, y 205 on drawing 9), so a patch that reached up to the rim
would swap a redrawn rim in with the tear.  The patch therefore starts at
y 206, one row below the lowest rim, and the drop reads as starting just under
the lens instead of at the eyelid - 12 px of a 127 px tear.

Measured over the ramp ring the ten drawings differ by at most 13/255 (mean
2-3); the only pixels above that are those five on the tear's top row, which is
the compromise above and not a seam.

Run:  python sadness_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, "Martin", "sadness")
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_sadness")
SHEET = os.path.join(OUT, "martin_sadness_sheet.png")
FITJSON = os.path.join(HERE, "sadness_fit.json")
PREFIX = "s"

TARGET_H = 724
MARGIN = 6
PAD = 48

TPL = (455, 315, 715, 400)     # source px of drawing 1: both lenses and the eyes
SCALES = np.arange(0.900, 1.1201, 0.004)
SEARCH = 90

BASE = None                    # None -> medoid over the aligned face band

# traced on the unpadded output canvas; see the docstring for the clearances
MOUTH_POLY = [(296, 222), (334, 222), (334, 238), (330, 243), (322, 248),
              (306, 248), (297, 243), (295, 232)]
TEAR_POLY = [(258, 206), (280, 206), (280, 230), (258, 230)]
PATCH_POLYS = [MOUTH_POLY, TEAR_POLY]
PATCH_RAMP = 2

ALPHA_SNAP = 240               # the PNGs top out at alpha 253; snap the body
                               # opaque and keep the real antialiased outline


def patch_mask(shape, polys, ramp, pad):
    """union of the polygons' ramp masks"""
    m = np.zeros(shape, np.float32)
    for p in polys:
        m = np.maximum(m, FZ.ramp_mask(shape, [(x + pad, y + pad) for x, y in p], ramp))
    return m


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

    mm = patch_mask((CH, CW), PATCH_POLYS, PATCH_RAMP, PAD)[..., None]
    print("patch %d px (%d solid) in %d polygons"
          % (int((mm > 0).sum()), int((mm > 0.999).sum()), len(PATCH_POLYS)))

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
