# -*- coding: utf-8 -*-
"""Build the 'talk_hand' frames (Martin talking with his hand raised).

Source: E:\\001_MAKETHEMFALLinlove素材庫\\Martin\\talk_02\\*.png - eight separate
1122x1402 drawings, not a sheet.  Being separate generations they differ in
*scale* as well as position (up to 8%), and every outline is redrawn, so they
boil far harder than the hand-drawn talk grid did.

  1. fit scale + translation of each drawing to drawing 1, on the head, and
     render them all into one 579x724 canvas (a single resample per drawing)
  2. freeze: emit every frame as one base drawing with only its own mouth
     patched in, plus the one drawing whose eyes are shut, so the picture is
     completely still except the mouth and a single blink
  3. crop to the base's bounding box and write the frames + the sheet

The hand stays in the base's raised pose.  The eight drawings do put the hand
in slightly different places, but their arms differ in *shape* at any seam one
could cut (at x=450 the arm's top edge moves 32 px between drawings), so the
arm cannot be swapped without a visible step in its outline - and swapping the
whole right side would bring the jacket's boil back with it.

Run:  python talkhand_prep.py
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import freeze_talk as FZ           # noqa: E402  (ramp_mask / components / eye mask)

BASE_DIR = os.path.dirname(os.path.dirname(HERE))            # ...素材庫
SRC_DIR = os.path.join(BASE_DIR, "Martin", "talk_02")
OUT = os.path.join(BASE_DIR, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_talkhand")
SHEET = os.path.join(OUT, "martin_talkhand_sheet.png")
PREFIX = "h"

TARGET_H = 724                 # the source frame, scaled; the figure is drawn
MARGIN = 6                     # larger than it, so the crop comes out ~755 tall

# scale + quarter-res shift of each drawing onto drawing 1, then a whole-pixel
# tweak at the output resolution.  Found by L1 search on the head; kept here so
# the build is reproducible without re-running the search.
FIT = [
    # scale, coarse dx, coarse dy, fine dx, fine dy
    (1.0000, 0, 0, 0, 0),
    (1.0540, 3, 0, -1, -1),
    (1.0240, 6, 1, 0, 0),
    (1.0180, 2, 0, -2, 0),
    (1.0760, -5, -1, 1, 1),
    (1.0600, 5, 1, 0, 1),
    (1.0060, 1, 0, 1, 0),
    (1.0380, 6, 0, 0, 0),
]

BASE = 7          # drawing 8: lowest medoid cost among the raised-hand poses
BLINK = 4         # drawing 5: the only one with its eyes shut

# Traced on the unpadded 579x724 canvas: inside the cheek, below the nose,
# above the chin line, left of the jaw contour.  PAD is added below, so these
# stay readable against a screenshot of that canvas.
MOUTH_POLY = [(282, 218), (320, 216), (329, 226), (325, 239),
              (315, 250), (297, 253), (283, 247), (277, 231)]
MOUTH_RAMP = 3

EYE_RECT = (250, 150, 366, 210)     # both lenses; the irises sit at x 277..343
EYE_CORE = (270, 164, 350, 198)


PAD = 24          # slack so an up-scaled drawing is never clipped


def aligned():
    """the eight drawings, scaled and shifted onto one canvas.

    The output scale R is chosen so the base drawing's figure comes out
    TARGET_H px tall once cropped; the canvas is padded because the fitted
    scales are all > 1 and would otherwise push the raised hand off its right
    edge (the drawings already have it within 15 px of the source border).
    """
    src = sorted(glob.glob(os.path.join(SRC_DIR, "*.png")))
    if len(src) != len(FIT):
        raise SystemExit("expected %d drawings, found %d" % (len(FIT), len(src)))
    W, H = Image.open(src[0]).size
    R = float(TARGET_H) / H
    smax = max(f[0] for f in FIT)
    CW = int(np.ceil(W * smax * R)) + 2 * PAD
    CH = int(np.ceil(H * smax * R)) + 2 * PAD
    out = []
    for path, (s, dx, dy, ex, ey) in zip(src, FIT):
        im = Image.open(path).convert("RGBA")
        r = im.resize((int(round(W * s * R)), int(round(H * s * R))), Image.LANCZOS)
        c = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        c.paste(r, (PAD + int(round(dx * 4 * R)), PAD + int(round(dy * 4 * R))))
        arr = np.asarray(c)
        out.append(np.roll(np.roll(arr, ey, axis=0), ex, axis=1))
    print("output scale %.4f, canvas %dx%d" % (R, CW, CH))
    return np.stack(out).astype(np.float32)


def eye_mask(base, frame):
    er = [v + PAD for v in EYE_RECT]
    ec = [v + PAD for v in EYE_CORE]
    d = np.abs(base.astype(np.int16) - frame.astype(np.int16)).max(axis=2) > 8
    box = np.zeros(d.shape, bool)
    box[er[1]:er[3] + 1, er[0]:er[2] + 1] = True
    d &= box
    lab, n = FZ.components(d)
    core = np.zeros(d.shape, bool)
    core[ec[1]:ec[3] + 1, ec[0]:ec[2] + 1] = True
    keep = np.zeros(d.shape, bool)
    for c in range(1, n + 1):
        m = lab == c
        if (m & core).any():
            keep |= m
    from PIL import ImageFilter
    m = Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    acc = np.zeros(keep.shape, np.float32)
    cur = m
    for _ in range(2):
        acc += np.asarray(cur).astype(np.float32) / 255.0
        cur = cur.filter(ImageFilter.MinFilter(3))
    return (acc / 2.0) * box


def main():
    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        if f.startswith(PREFIX + "_") and f.endswith(".png"):
            os.remove(os.path.join(FRAMES, f))

    A = aligned()
    n, CH, CW = A.shape[:3]
    print("aligned %d drawings onto %dx%d" % (n, CW, CH))

    base = A[BASE]
    poly = [(x + PAD, y + PAD) for x, y in MOUTH_POLY]
    mm = FZ.ramp_mask((CH, CW), poly, MOUTH_RAMP)[..., None]
    em = eye_mask(base.astype(np.uint8), A[BLINK].astype(np.uint8))[..., None]
    print("mouth patch %d px, eye patch %d px"
          % (int((mm > 0).sum()), int((em > 0).sum())))

    frames = []
    for i in range(n):
        out = base * (1.0 - mm) + A[i] * mm
        if i == BLINK:
            out = out * (1.0 - em) + A[i] * em
        frames.append(np.clip(out + 0.5, 0, 255).astype(np.uint8))

    m = frames[BASE][..., 3] > 32
    ys = np.nonzero(m.sum(1))[0]
    xs = np.nonzero(m.sum(0))[0]
    x0 = max(0, int(xs.min()) - MARGIN)
    x1 = min(CW - 1, int(xs.max()) + MARGIN)
    y0 = max(0, int(ys.min()) - MARGIN)
    y1 = min(CH - 1, int(ys.max()) + MARGIN)
    fw, fh = x1 - x0 + 1, y1 - y0 + 1
    fw += fw % 2
    fh += fh % 2
    x1, y1 = x0 + fw - 1, y0 + fh - 1
    print("frame %dx%d  crop x %d..%d y %d..%d" % (fw, fh, x0, x1, y0, y1))

    sheet = Image.new("RGBA", (fw * n, fh), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        c = np.zeros((fh, fw, 4), np.uint8)
        sy, sx = min(CH, y1 + 1), min(CW, x1 + 1)
        c[:sy - y0, :sx - x0] = f[y0:sy, x0:sx]
        img = Image.fromarray(c)
        img.save(os.path.join(FRAMES, "%s_%02d.png" % (PREFIX, i)))
        sheet.paste(img, (i * fw, 0))
    sheet.save(SHEET)
    print("sheet:", sheet.size, "->", SHEET)
    return fw, fh, n


if __name__ == "__main__":
    main()
