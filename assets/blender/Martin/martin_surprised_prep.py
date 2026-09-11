# -*- coding: utf-8 -*-
"""Prepare the 'surprised' sheet.

That sheet ships on a solid black background (no alpha), so the background is
flood-filled from the border - a plain colour key would eat the character's own
black outlines.  Edge pixels were composited over black, so their alpha is
estimated back out to avoid a dark fringe on light backgrounds.
"""
from PIL import Image
import numpy as np
import os
from collections import deque

ROOT = r"E:\001_MAKETHEMFALLinlove素材庫"
SRC = os.path.join(ROOT, "Martin", "001_martin_surprised.png")
FRAMES = os.path.join(ROOT, "Martin", "frames_surprised")
SHEET_OUT = os.path.join(ROOT, "blender", "develop", "Martin",
                         "martin_surprised_sheet.png")
os.makedirs(FRAMES, exist_ok=True)
os.makedirs(os.path.dirname(SHEET_OUT), exist_ok=True)

a = np.asarray(Image.open(SRC).convert("RGB")).astype(np.int16)
H, W = a.shape[:2]
NF = 6
FW = W // NF

# ---------------------------------------------------------------- background
blackish = a.max(axis=2) <= 10
bg = np.zeros((H, W), bool)
q = deque()
for x in range(W):
    for y in (0, H - 1):
        if blackish[y, x] and not bg[y, x]:
            bg[y, x] = True; q.append((y, x))
for y in range(H):
    for x in (0, W - 1):
        if blackish[y, x] and not bg[y, x]:
            bg[y, x] = True; q.append((y, x))
while q:
    y, x = q.popleft()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        v, u = y + dy, x + dx
        if 0 <= v < H and 0 <= u < W and blackish[v, u] and not bg[v, u]:
            bg[v, u] = True
            q.append((v, u))

alpha = np.where(bg, 0, 255).astype(np.int16)
rgb = a.copy()

# ---------------------------------------------------------------- soft edges
# pixels touching the background: they were drawn over black, so
# observed = true_colour * coverage.  Estimate the coverage from a neighbour.
border = np.zeros((H, W), bool)
border[1:] |= bg[:-1]; border[:-1] |= bg[1:]
border[:, 1:] |= bg[:, :-1]; border[:, :-1] |= bg[:, 1:]
border &= ~bg
inner = ~bg & ~border
fixed = 0
ys, xs = np.nonzero(border)
for y, x in zip(ys, xs):
    y0, y1 = max(0, y - 1), min(H, y + 2)
    x0, x1 = max(0, x - 1), min(W, x + 2)
    sel = inner[y0:y1, x0:x1]
    if not sel.any():
        continue
    ref = a[y0:y1, x0:x1][sel].mean(axis=0)
    rmax = ref.max()
    if rmax < 12:
        continue                                    # neighbour is dark too: real outline
    cov = float(a[y, x].max()) / float(rmax)
    if cov < 0.92:
        alpha[y, x] = int(round(np.clip(cov, 0.0, 1.0) * 255))
        rgb[y, x] = np.round(ref)
        fixed += 1

rgba = np.dstack([rgb.astype(np.uint8), alpha.astype(np.uint8)])
print("background %.1f%%, outline px kept %d, soft edges recovered %d"
      % (100 * bg.mean(), int((blackish & ~bg).sum()), fixed))

Image.fromarray(rgba).save(SHEET_OUT)
for i in range(NF):
    Image.fromarray(rgba[:, i * FW:(i + 1) * FW]).save(
        os.path.join(FRAMES, "s_%02d.png" % i))

# contact sheet for checking
sheet = Image.new("RGB", (NF * 181, 362), (245, 246, 250))
for i in range(NF):
    f = Image.open(os.path.join(FRAMES, "s_%02d.png" % i))
    bgim = Image.new("RGB", f.size, (245, 246, 250))
    bgim.paste(f, (0, 0), f)
    sheet.paste(bgim.resize((181, 362), Image.NEAREST), (i * 181, 0))
sheet.save(r"E:\americanwomen\renders\sp_frames.png")
print("frames ->", FRAMES)
print("sheet  ->", SHEET_OUT)
