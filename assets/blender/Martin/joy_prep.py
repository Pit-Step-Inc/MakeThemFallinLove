# -*- coding: utf-8 -*-
"""Build the 'joy' frames (Martin smiling, then laughing).

Source: E:\\001_MAKETHEMFALLinlove素材庫\\Martin\\joy\\*.png - ten separate
1122x1402 drawings.  Same shape of problem as anger: one pose (hands in the
jacket pockets), ten separate takes, and only the face differs - six closed
smiles of slightly different width, then teeth, then two open laughs.

So the anger recipe applies, and this reuses its FFT fit (anger_prep.fit_all /
aligned) with joy's own template and scale range - the heads here are drawn
over a wider range of sizes, up to 1.052.

What is different is the patch itself.  Two of the drawings (5 and 6) put
blush strokes on the cheek beside the mouth, and drawing 5's laugh is wide
enough to reach most of the way to the jaw, so a patch that only covers the
mouth would drop the blush and clip the laugh.  The patch here is therefore
one polygon holding both, threaded between four things that must stay out of
it because all four are redrawn on every take:

    glasses  bottom rim at y 204..205        -> top edge at y 207
    nose     bottom at y 216 (217 at x 333..340), left edge at x 327
                                             -> notch: drop at x 324 to y 218
    jaw      rises to the left: y 246 at x 265, y 258 at x 294
    contour  right edge x 344 at y 240, x 342 below

Measured over the ramp ring, the ten drawings differ by at most 42/255 and by
3-7 on average, and every drawn mouth pixel lands in the solid part of the
mask - so the blend has nothing to ghost.

The one thing not patched is the eyes.  Drawing 5 laughs with its eyes shut,
which would be the blink, but it also has the *glasses* redrawn - the rim
overlaps the base's by only 0.58 IoU even at its best offset, against 0.84-0.90
for every other drawing - and the talk/talkhand blink patch works precisely
because its seam falls on a rim that is identical in both.  Here it is not, so
there is no clean seam and the squint is left out.

Run:  python joy_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, "Martin", "joy")
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_joy")
SHEET = os.path.join(OUT, "martin_joy_sheet.png")
FITJSON = os.path.join(HERE, "joy_fit.json")
PREFIX = "j"

TARGET_H = 724
MARGIN = 6
PAD = 48

TPL = (470, 315, 720, 400)     # source px of drawing 1: both lenses and the eyes
SCALES = np.arange(0.900, 1.1201, 0.004)
SEARCH = 90

BASE = None                    # None -> medoid over the aligned face band

# mouth + blush, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(264, 207), (324, 207), (324, 218), (345, 218), (346, 230),
              (341, 240), (336, 248), (331, 255), (326, 260), (308, 261),
              (294, 257), (284, 254), (276, 250), (270, 245), (264, 240)]
PATCH_RAMP = 2                 # 3 would push the ramp onto the nose: the gap
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
