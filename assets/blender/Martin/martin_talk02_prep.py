# -*- coding: utf-8 -*-
"""Prepare the 'talk' sheet - separated, no bleed from neighbouring frames.

The drawings are wider than their 362 px pitch (gestures reach past it), so an
equal 6-way split copies a slice of the neighbour.  Instead the sheet is cut at
the fully transparent columns between the figures, and each character is pasted
into a uniform canvas aligned on its head - only pixels inside that character's
own region are copied, so nothing bleeds in.
"""
from PIL import Image
import numpy as np
import os

ROOT = r"E:\001_MAKETHEMFALLinlove素材庫"
SRC = os.path.join(ROOT, "Martin", "001_talk_02.png")
FRAMES = os.path.join(ROOT, "Martin", "frames_talk02")
DEV = os.path.join(ROOT, "blender", "develop", "Martin")
SHEET_OUT = os.path.join(DEV, "martin_talk02_sheet.png")
NF = 6
FW = 370                     # uniform frame width (widest reach 181 + margin)
os.makedirs(FRAMES, exist_ok=True)
os.makedirs(DEV, exist_ok=True)

im = Image.open(SRC).convert("RGBA")
W, H = im.size
a = np.asarray(im)
al = a[..., 3] > 32
prof = al.sum(axis=0)

# ---- cut where the sheet is completely empty ------------------------------
zero = np.nonzero(prof == 0)[0]
runs, s = [], zero[0]
for i in range(1, len(zero)):
    if zero[i] != zero[i - 1] + 1:
        runs.append((int(s), int(zero[i - 1]))); s = zero[i]
runs.append((int(s), int(zero[-1])))
gaps = [r for r in runs if 20 < r[0] < W - 20]
if len(gaps) != NF - 1:
    raise SystemExit("expected %d separations, found %d: %s" % (NF - 1, len(gaps), gaps))
cuts = [0] + [(r[0] + r[1]) // 2 for r in gaps] + [W]

# ---- head centre of each figure = the anchor ------------------------------
top = np.nonzero(al.sum(axis=1))[0].min()
band = al[top:top + 120]
heads = []
for i in range(NF):
    seg = band[:, cuts[i]:cuts[i + 1]].sum(axis=0)
    xs = np.nonzero(seg > 3)[0]
    heads.append(cuts[i] + int((xs.min() + xs.max()) // 2))

half = FW // 2
sheet = Image.new("RGBA", (FW * NF, H), (0, 0, 0, 0))
for i in range(NF):
    canvas = np.zeros((H, FW, 4), np.uint8)
    x0, x1 = cuts[i], cuts[i + 1]
    for dx in range(FW):
        sx = heads[i] - half + dx
        if x0 <= sx < x1 and 0 <= sx < W:          # only this figure's own columns
            canvas[:, dx] = a[:, sx]
    img = Image.fromarray(canvas)
    img.save(os.path.join(FRAMES, "t_%02d.png" % i))
    sheet.paste(img, (i * FW, 0))
    m = canvas[..., 3] > 32
    cols = np.nonzero(m.sum(axis=0))[0]
    rows = np.nonzero(m.sum(axis=1))[0]
    print("frame %d  src x %4d-%4d  head %4d  ->  canvas x %3d-%3d  y %3d-%3d"
          % (i, x0, x1, heads[i], cols.min(), cols.max(), rows.min(), rows.max()))
sheet.save(SHEET_OUT)
print("cuts:", cuts)
print("sheet ->", SHEET_OUT, sheet.size)

check = Image.new("RGB", (NF * 185, 362), (245, 246, 250))
for i in range(NF):
    f = Image.open(os.path.join(FRAMES, "t_%02d.png" % i))
    bgim = Image.new("RGB", f.size, (245, 246, 250))
    bgim.paste(f, (0, 0), f)
    check.paste(bgim.resize((185, 362), Image.NEAREST), (i * 185, 0))
check.save(r"E:\americanwomen\renders\talk_frames.png")
