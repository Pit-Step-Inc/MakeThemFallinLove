# -*- coding: utf-8 -*-
"""Build the Catherine 'anger' frames (a glare that becomes a shout).

Source: E:\001_MAKETHEMFALLinlove素材庫\Catherine\anger\*.png - ten separate
1122x1402 drawings.  Same standing pose as talk01 and joy; the mouth runs from
a flat frown through gritted teeth to a wide open shout.

The fit is on the nose and cheeks, as joy's is - not because the eyes are shut
here (they are not) but because that band sits next to the patch, and it gives
the quieter seam of the two: over the mouth patch's ring the nose band measures
4-6 of 255 against the eye band's 8-27.

**Only the mouth is patched.**  The brows do sharpen on drawings 4 and 5 (the
two shouts differ from the base by 5500 px around the eyes, against 2400-3800
for the rest) and joy's diff-shaped eye patch would be the tool for it - but
not on this set.  Here the whole upper head is redrawn take to take: every hair
strand outline moves, so the changed region has no quiet edge to seam against
and diff_patch fills its whole box.  Measured across that ring: 97-209 px above
40 with a max of 214-221, against joy's 5-25 and 101-133.  Aligning on the eye
band instead does not rescue it (97-140).  So the glare is left frozen.

The mouth outline, on flat cheek all the way round:

    nose   bottom y 235 at x 246..268 - and drawing 5's shout starts at y 236
           there, one row below, so the outline runs under the nose and rounds
           off that corner of the shout (22 px of a 1578 px mouth)
    jaw L  y 265 at x 260, y 270 at x 272
    jaw R  y 276 at x 284, y 272 at x 308
    cheek  right contour x 332 at y 248, x 315 at y 264

Every drawn mouth blob lands in the solid part of the mask.  Over the ramp ring
nine of the ten drawings measure at most 14/255 with nothing above 40; drawing
5 - whose shout reaches the outline on three sides - has 11 px above 40, six at
the mouth's top left tip and five on the chin crease, none of them findable at
1:1.

Run:  python anger_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, CHAR, "anger")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_anger")
SHEET = os.path.join(OUT, "catherine_anger_sheet.png")
FITJSON = os.path.join(HERE, "anger_fit.json")
PREFIX = "ca"

TARGET_H = 724                 # the same output height as the Martin set
MARGIN = 6
PAD = 48

TPL = (430, 400, 700, 560)     # source px: the nose and cheeks - NOT the eyes,
                               # two drawings shut them (see the docstring)
SCALES = np.arange(0.940, 1.0601, 0.004)
SEARCH = 60

BASE = None                    # None -> medoid over the aligned face band

# the mouth, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(263, 237), (271, 232), (281, 226), (292, 221), (319, 221),
              (322, 240), (319, 256), (314, 264), (306, 271), (292, 274),
              (284, 273), (274, 269), (266, 262), (262, 250)]
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

    # The teeth are NOT painted out here.  In joy they flashed - two drawings
    # of nine had them at an opening where the others did not.  In anger they
    # are the expression: 2 and 6 are a gritted grimace and 5 is a shout, and
    # the timeline plays those as blocks rather than cutting them against a
    # teeth-free mouth of the same opening.  To drop them anyway, call
    # SP.hide_teeth here the way joy_prep does.

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
