# -*- coding: utf-8 -*-
"""Build the 'anger' frames (Martin scowling, then shouting).

Source: E:\\001_MAKETHEMFALLinlove素材庫\\Martin\\anger\\*.png - ten separate
1122x1402 drawings, not a sheet.  The pose is the same in all ten (hands in
the jacket pockets); what changes is the face - four shut-mouth scowls, and
six degrees of open mouth up to a full shout.

Being ten separate generations they differ in scale as well as position, and
the head in particular wanders: the mouth of drawing 6 sits 40 px left of the
mouth of drawing 1.  So this is the talkhand case, not the happy case:

  1. fit scale + translation of each drawing onto drawing 1, measured on the
     glasses/eye band (the one rigid landmark - the hair silhouette, the jaw
     and the jacket folds are all redrawn on every take)
  2. freeze: every frame is emitted as one base drawing with only its own
     mouth patched in, so hair, glasses, jacket and hands are pixel identical
     across all ten and only the mouth moves
  3. crop to the base's bounding box and write the frames + the sheet

Aligning on the face rather than on the body is not a compromise here - the
body is *never* taken from anything but the base, so the only thing the fit
has to get right is the patch.

Run:  python anger_prep.py
"""
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
import spriteprep as SP            # noqa: E402  (the fit and the patch mask)
FZ = SP                            # kept: this module used to expose freeze_talk's
                                   # ramp_mask under the name FZ
order = SP.order                   # re-exported: the other clips' preps import
gray = SP.gray                     # these from anger_prep
ssd_map = SP.ssd_map

BASE_DIR = os.path.dirname(os.path.dirname(HERE))            # ...素材庫
SRC_DIR = os.path.join(BASE_DIR, "Martin", "anger")
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_anger")
SHEET = os.path.join(OUT, "martin_anger_sheet.png")
FITJSON = os.path.join(HERE, "anger_fit.json")
PREFIX = "a"

TARGET_H = 724                 # same output height as the rest of the Martin set
MARGIN = 6
PAD = 40                       # slack so an up-scaled drawing is never clipped

# Face template, in *source* pixels of drawing 1: the glasses, both eyes and
# the bridge of the nose.  Deliberately stops above the mouth (that is the
# animation) and inside the hair (that is the boil).
TPL = (455, 295, 745, 415)     # x0, y0, x1, y1
SCALES = np.arange(0.940, 1.0601, 0.004)
SEARCH = 70                    # px, at source resolution

BASE = None                    # None -> medoid over the aligned face band

# Mouth patch, traced on the unpadded output canvas (anger_check.png overlays
# it).  The ten drawn mouths together occupy x 292..337, y 222..249; the patch
# has to hold all of that and still keep its edge in flat cheek, which here is
# a squeeze on three sides:
#
#   nose      bottom at y 217, x 327..347 - and it is redrawn on every take
#             (mean 25/255 off the base), so it must stay *outside*
#   jaw, right the face contour comes in from x 347 at y 238 to x 338 at y 250
#   chin      y 253 at x 280, y 262 at x 300
#
# so the outline runs high and wide over the flat cheek on the left, tucks
# under the nose on the right, and pulls back in below y 240.
MOUTH_POLY = [(288, 210), (322, 208), (331, 219), (341, 223), (341, 239),
              (336, 246), (332, 253), (302, 255), (290, 253), (286, 240),
              (286, 216)]
MOUTH_RAMP = 3

ALPHA_SNAP = 240       # ChatGPT's PNGs never reach alpha 255 - the body sits at
                       # 250-253 - so the whole figure would composite a percent
                       # translucent over a game background.  Snap the body
                       # opaque and keep the real antialiased outline.







def fit_all(paths, tpl_box=None, scales=None, search=None, verbose=True):
    """anger's defaults over spriteprep.fit_all; other clips pass their own"""
    return SP.fit_all(paths,
                      TPL if tpl_box is None else tpl_box,
                      SCALES if scales is None else scales,
                      SEARCH if search is None else search,
                      verbose=verbose)


def aligned(paths, fits, target_h=None, pad=None):
    """anger's defaults over spriteprep.aligned"""
    return SP.aligned(paths, fits,
                      TARGET_H if target_h is None else target_h,
                      PAD if pad is None else pad)


def medoid_face(A):
    """the drawing closest to all the others over the face band"""
    R = float(TARGET_H) / 1402.0
    x0, y0, x1, y1 = [int(round(v * R)) + PAD for v in TPL]
    band = A[:, y0:y1, x0:x1, :3].reshape(len(A), -1)
    cost = [float(np.abs(band - band[i]).mean()) for i in range(len(A))]
    return int(np.argmin(cost)), cost


def main(write=True):
    paths = order(glob.glob(os.path.join(SRC_DIR, "*.png")))
    print("%d drawings" % len(paths))

    if os.path.exists(FITJSON):
        fits = [tuple(f) for f in json.load(open(FITJSON))]
        print("fit: reusing", os.path.basename(FITJSON))
        for k, (s, dx, dy) in enumerate(fits):
            print("  drawing %2d: scale %.3f  shift (%+.0f,%+.0f)" % (k, s, dx, dy))
    else:
        print("fit (glasses/eye band):")
        fits = fit_all(paths)
        json.dump(fits, open(FITJSON, "w"), indent=1)

    A = aligned(paths, fits)
    n, CH, CW = A.shape[:3]

    base = BASE
    if base is None:
        base, cost = medoid_face(A)
        print("base drawing %d (face medoid, cost %.2f)" % (base, cost[base]))
    B = A[base]

    poly = [(x + PAD, y + PAD) for x, y in MOUTH_POLY]
    mm = FZ.ramp_mask((CH, CW), poly, MOUTH_RAMP)[..., None]
    print("mouth patch %d px" % int((mm > 0).sum()))

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
