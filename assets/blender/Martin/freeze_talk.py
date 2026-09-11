# -*- coding: utf-8 -*-
"""Hold the drawing still and let only the mouth (and one blink) move.

The 20 cells of the talk sheet are twenty separate hand drawings, so every
outline - hair, jaw, collar, jacket folds - is redrawn a pixel or two off on
every cell.  Registering the cells fixes the *placement*, not that: played
back, the whole figure boils, and that is what still reads as the picture
shaking after the alignment work.  A talking portrait is not supposed to do it.

So one drawing is chosen as the base (the medoid - the cell closest to all the
others) and every frame is emitted as that base with only the mouth taken from
its own drawing.  The twenty drawn mouth shapes are kept exactly; everything
else stops moving.  One drawing also gets its closed eyes back, so the cycle
still blinks once.

Two things matter for the seams:

  * the mouth patch is a polygon traced inside the cheek, clear of the jaw
    outline below it and of the cheek contour to its right - those are the
    high contrast edges, and a blend that straddles one of them ghosts.
  * its soft edge is a linear ramp built by eroding the polygon, so the mask
    is exactly zero outside it.  A Gaussian would leave a tail, and a 5% tail
    over a 250-level edge is still a visible 12-level shimmer.

The eye patch instead uses "the pixels that differ from the base inside the
lenses", so its seam sits on the glasses rim, which is identical in both.

Usage: python freeze_talk.py <frames_dir> [prefix]
"""
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import os
import sys
from collections import deque

# Traced on the 234x334 frames grid_prep emits; inside the cheek, above the
# jaw line, left of the cheek contour, and wide enough for the widest drawn
# mouth (drawings 3, 12, 13, 18).
MOUTH_POLY = [(114, 101), (147, 101), (150, 108), (148, 118),
              (143, 127), (128, 130), (115, 124)]
MOUTH_RAMP = 3                    # px of linear falloff, inside the polygon

BLINK = 7                         # the one drawing that keeps its closed eyes
EYE_RECT = (96, 76, 164, 114)
EYE_CORE = (103, 85, 156, 106)
EYE_TOL = 8


def ramp_mask(shape, pts, width):
    """1.0 inside, a `width` px linear ramp, exactly 0 outside the polygon"""
    h, w = shape
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    acc = np.zeros((h, w), np.float32)
    cur = m
    for _ in range(width):
        acc += np.asarray(cur).astype(np.float32) / 255.0
        cur = cur.filter(ImageFilter.MinFilter(3))
    return acc / width


def components(mask):
    lab = np.zeros(mask.shape, np.int32)
    cur = 0
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        cur += 1
        q = deque([(y0, x0)])
        lab[y0, x0] = cur
        while q:
            y, x = q.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                v, u = y + dy, x + dx
                if (0 <= v < mask.shape[0] and 0 <= u < mask.shape[1]
                        and mask[v, u] and not lab[v, u]):
                    lab[v, u] = cur
                    q.append((v, u))
    return lab, cur


def eye_mask(base, frame):
    """where `frame` differs from `base` inside the lenses"""
    diff = np.abs(base.astype(np.int16) - frame.astype(np.int16)).max(axis=2) > EYE_TOL
    box = np.zeros(diff.shape, bool)
    box[EYE_RECT[1]:EYE_RECT[3] + 1, EYE_RECT[0]:EYE_RECT[2] + 1] = True
    diff &= box
    lab, n = components(diff)
    core = np.zeros(diff.shape, bool)
    core[EYE_CORE[1]:EYE_CORE[3] + 1, EYE_CORE[0]:EYE_CORE[2] + 1] = True
    keep = np.zeros(diff.shape, bool)
    for c in range(1, n + 1):
        m = lab == c
        if (m & core).any():
            keep |= m
    m = Image.fromarray((keep * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    acc = np.zeros(keep.shape, np.float32)
    cur = m
    for _ in range(2):
        acc += np.asarray(cur).astype(np.float32) / 255.0
        cur = cur.filter(ImageFilter.MinFilter(3))
    return (acc / 2.0) * box


def medoid(A):
    flat = A.reshape(len(A), -1).astype(np.float32)
    cost = [float(np.abs(flat - flat[i]).mean()) for i in range(len(A))]
    return int(np.argmin(cost)), cost


def freeze(frames_dir, prefix="t", blink=BLINK, base_index=None):
    path = lambda i: os.path.join(frames_dir, "%s_%02d.png" % (prefix, i))
    n = len([f for f in os.listdir(frames_dir)
             if f.startswith(prefix + "_") and f.endswith(".png")])
    A = np.stack([np.asarray(Image.open(path(i)).convert("RGBA")).astype(np.float32)
                  for i in range(n)])
    if base_index is None:
        base_index, cost = medoid(A)
        print("  base drawing %d (medoid, cost %.2f)" % (base_index, cost[base_index]))
    base = A[base_index]

    mm = ramp_mask(base.shape[:2], MOUTH_POLY, MOUTH_RAMP)[..., None]
    em = eye_mask(base.astype(np.uint8), A[blink].astype(np.uint8))[..., None]

    for i in range(n):
        out = base * (1.0 - mm) + A[i] * mm
        if i == blink:
            out = out * (1.0 - em) + A[i] * em
        Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8)).save(path(i))
    print("  froze %d frames on base %d: mouth from each drawing, one blink on %d"
          % (n, base_index, blink))
    return base_index


if __name__ == "__main__":
    d = sys.argv[1]
    p = sys.argv[2] if len(sys.argv) > 2 else "t"
    freeze(d, p)
