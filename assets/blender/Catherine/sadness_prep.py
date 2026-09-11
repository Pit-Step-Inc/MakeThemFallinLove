# -*- coding: utf-8 -*-
"""Build the Catherine 'sadness' frames (welling up, and a sob).

Source: E:\001_MAKETHEMFALLinlove素材庫\Catherine\sadness\*.png - ten separate
1122x1402 drawings.  Same standing pose as the other Catherine clips.  The
mouths barely differ - the whole range is x 272..301 / y 242..259 - so what
carries this one is the eyes: they well up and, on several drawings, spill.

**The tear is lifted by its colour, so it can arrive during the clip.**  The
base is the dry medoid (drawing 2), and the tear is patched in on the four
drawings that have one - so the clip opens on a plain sad face and the tear
builds:

    5   a bead at the outer lash          15 px
    8   the bead swells                   45 px
    6   it runs down the cheek           111 px
    7   the drop has come away            62 px

Neither of the other two kinds of patch works for this.  A traced polygon needs
quiet skin to seam against, and the tear hangs off the lower lid; joy's
diff-shaped patch needs the *change* to have a quiet edge, and here the lid,
the lashes and the whole upper head are redrawn take to take - measured across
that ring, 47-219 px above 40 against joy's 5-25, and neither an eye-band refit
nor a local integer refit before the difference rescues it (the latter moves
the mean from 20.97 to 20.91: the residual is redrawing, not offset).  Nor can
the tear ride in on the base - swapping base 2 for base 7 pops 15% of the
figure.

But a tear is the only *bluish* thing on a face.  Keying on that lifts the tear
and nothing else, so the only seam is the tear's own outline and it lands on
flat cheek; the lid underneath stays the base's, which is what a tear lying
over a lash looks like anyway.  Blobs are kept only if they reach below the
base's lid line, so the sclera highlight shifting inside the eye is not
mistaken for a tear - by that test the other six drawings are dry, exactly as
they look.

The mouth outline, on flat cheek all the way round; the mouths are small enough
that it clears everything easily.

Run:  python sadness_prep.py
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
SRC_DIR = os.path.join(BASE_DIR, CHAR, "sadness")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_sadness")
SHEET = os.path.join(OUT, "catherine_sadness_sheet.png")
FITJSON = os.path.join(HERE, "sadness_fit.json")
PREFIX = "cs"

TARGET_H = 724                 # the same output height as the Martin set
MARGIN = 6
PAD = 48

TPL = (430, 400, 700, 560)     # source px: the nose and cheeks - NOT the eyes,
                               # two drawings shut them (see the docstring)
SCALES = np.arange(0.940, 1.0601, 0.004)
SEARCH = 60

BASE = None                    # None -> medoid over the aligned face band
                               # (drawing 2, the driest - see the docstring)

# the mouth, traced on the unpadded output canvas (see the docstring)
PATCH_POLY = [(266, 238), (276, 234), (290, 232), (308, 234), (312, 244),
              (310, 254), (304, 264), (292, 268), (280, 266), (272, 262),
              (266, 254), (264, 246)]
PATCH_RAMP = 2

# The tear, lifted by colour (SP.colour_patch).  The box covers the outer half
# of the right eye and the cheek under it; TEAR_LID is where the base's eye
# ends, so a blob must reach past it to count as a tear.
TEAR_BOX = (300, 168, 348, 222)
TEAR_LID_BOX = (298, 168, 350, 222)
SKIN = (251, 181, 145)


def is_tear(rgb):
    """the only bluish thing on a face"""
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    return (rgb[..., 2] >= rgb[..., 0] - 6) & (lum > 140)


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

    # Nothing to hide here: the brightest thing in these mouths is the wet lip
    # highlight, and it is present on every drawing rather than two of ten.

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

    lid = SP.lid_line(B, tuple(v + PAD for v in TEAR_LID_BOX), SKIN)
    lid = {x: y for x, y in lid.items()}
    frames = []
    for i in range(n):
        m = mm
        tm = SP.colour_patch(A[i], B, tuple(v + PAD for v in TEAR_BOX), is_tear,
                             below={x: y + 1 for x, y in lid.items()})
        if tm is not None:
            print("  drawing %d: tear %d px" % (i, int((tm > 0.99).sum())))
            m = np.maximum(mm, tm[..., None])
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
