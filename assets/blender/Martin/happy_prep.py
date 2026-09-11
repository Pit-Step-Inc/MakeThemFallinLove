# -*- coding: utf-8 -*-
"""Separate and align the 15 cells of the 'happy' cheer sheet.

Source: Martin/ChatGPT Image 2026年9月10日 02_13_29.png - a 5x3 grid, already
carrying an alpha channel (the dark red wash is alpha 0, so no keying needed).

Unlike talk / talkhand this one really is a pose progression - gesture, then
fists up, then arms thrown wide - so the body has to animate.  Only the
*placement* is corrected here:

  * rows come from the alpha row profile
  * inside a row the figures are found as connected components, NOT by cutting
    columns.  On the bottom row the spread arms reach past the middle of the
    gap - figure 12's right hand sits at x 903..958 while its "cell" ends at
    903 - so any vertical cut lops a hand off.  The five figures are five
    separate blobs whose x ranges simply interleave, so labelling finds them
    whole.
  * each blob is then grown into the soft alpha edge, claiming exclusively, so
    the antialiased outline comes along but a neighbour's does not
  * the figures are anchored on the head: the arms are the animation and the
    waist is redrawn on every cell

Usage: python happy_prep.py
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(BASE, "Martin", "ChatGPT Image 2026年9月10日 02_13_29.png")
OUT = os.path.join(BASE, "blender", "develop", "Martin")
FRAMES = os.path.join(OUT, "frames_happy")
SHEET = os.path.join(OUT, "martin_happy_sheet.png")
PREFIX = "p"

COLS = 5
MARGIN = 8
COMP_THR = 96          # alpha above this is "solid": at this level each figure
                       # is exactly one connected blob, even where two of them
                       # interleave in x
GROW = 4               # rounds of exclusive growth into the soft alpha edge
ALPHA_SNAP = 240       # the source never reaches alpha 255 - the body sits at
                       # 250-253 - so the whole figure would composite slightly
                       # translucent.  Snap the body opaque, keep the real edge.
PAD = 64
SEARCH = 45            # the three rows crop the figure at different heights and
                       # sit the figure differently, so the coarse placement can
                       # be 30 px out
TORSO_LO = 0.62        # torso centroid band, as a fraction of the figure height
HEAD = (150, 130)      # template used to refine: width, height, taken from the
                       # top of the reference figure.  The head is the only
                       # rigid landmark - the arms are the animation and the
                       # waist is redrawn with every jacket fold, so correlating
                       # on it wanders by up to 30 px.


def bands(profile, thr=0):
    nz = np.nonzero(profile > thr)[0]
    out, s = [], nz[0]
    for i in range(1, len(nz)):
        if nz[i] != nz[i - 1] + 1:
            out.append((int(s), int(nz[i - 1]))); s = nz[i]
    out.append((int(s), int(nz[-1])))
    return out


def label(mask):
    lab = np.zeros(mask.shape, np.int32)
    cur, sizes = 0, {}
    for y0, x0 in zip(*np.nonzero(mask)):
        if lab[y0, x0]:
            continue
        cur += 1
        n = 0
        q = deque([(y0, x0)])
        lab[y0, x0] = cur
        while q:
            y, x = q.popleft()
            n += 1
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)):
                v, u = y + dy, x + dx
                if (0 <= v < mask.shape[0] and 0 <= u < mask.shape[1]
                        and mask[v, u] and not lab[v, u]):
                    lab[v, u] = cur
                    q.append((v, u))
        sizes[cur] = n
    return lab, sizes


def grow(lab, soft, rounds):
    """expand every label into `soft`, first come first served"""
    out = lab.copy()
    h, w = out.shape
    for _ in range(rounds):
        frontier = []
        ys, xs = np.nonzero(out > 0)
        for y, x in zip(ys, xs):
            c = out[y, x]
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                v, u = y + dy, x + dx
                if 0 <= v < h and 0 <= u < w and soft[v, u] and out[v, u] == 0:
                    frontier.append((v, u, c))
        if not frontier:
            break
        for v, u, c in frontier:
            if out[v, u] == 0:
                out[v, u] = c
    return out


def premul(c):
    f = c.astype(np.float32)
    al = f[..., 3:4] / 255.0
    return np.concatenate([f[..., :3] * al, f[..., 3:4]], axis=2)


def main():
    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        if f.startswith(PREFIX + "_") and f.endswith(".png"):
            os.remove(os.path.join(FRAMES, f))

    a = np.asarray(Image.open(SRC).convert("RGBA"))
    H, W = a.shape[:2]
    al = a[..., 3] > 32
    rows = bands(al.sum(axis=1))
    print("rows:", rows)

    infos = []
    for (y0, y1) in rows:
        core = a[y0:y1 + 1, :, 3] > COMP_THR
        soft = a[y0:y1 + 1, :, 3] > 32
        lab, sizes = label(core)
        keep_ids = [c for c, _ in sorted(sizes.items(), key=lambda kv: -kv[1])[:COLS]]
        if len(keep_ids) < COLS:
            raise SystemExit("row %d-%d: only %d blobs" % (y0, y1, len(sizes)))
        drop = sum(n for c, n in sizes.items() if c not in keep_ids)
        lab[~np.isin(lab, keep_ids)] = 0
        lab = grow(lab, soft, GROW)
        print("  row %4d-%4d: %d blobs, kept %d, dropped %d specks"
              % (y0, y1, len(sizes), COLS, drop))
        order = []
        for c in keep_ids:
            m = lab == c
            ys, xs = np.nonzero(m)
            top, bot = int(ys.min()), int(ys.max())
            band = ys > top + (bot - top) * TORSO_LO
            order.append((float(xs[band].mean()), c, m, top, bot,
                          int(xs.min()), int(xs.max())))
        order.sort()                       # left to right by torso, not by bbox
        for hx, c, m, top, bot, left, right in order:
            infos.append(dict(row=(y0, y1), keep=m, hx=hx, top=top, bottom=bot,
                              left=left, right=right))
            print("     figure %2d: torso x %6.1f  bbox x %4d..%4d y %3d..%3d"
                  % (len(infos) - 1, hx, left, right, top, bot))

    fw = 2 * int(np.ceil(max(max(i["hx"] - i["left"], i["right"] - i["hx"])
                             for i in infos) + MARGIN))
    fh = max(i["bottom"] - i["top"] for i in infos) + 2 * MARGIN
    fw += fw % 2
    fh += fh % 2
    cw, ch = fw + 2 * PAD, fh + 2 * PAD
    half = cw // 2

    work = []
    for inf in infos:
        y0, y1 = inf["row"]
        strip = a[y0:y1 + 1].copy()
        strip[~inf["keep"]] = 0
        cell = strip[:, inf["left"]:inf["right"] + 1]
        canvas = np.zeros((ch, cw, 4), np.uint8)
        dx = int(round(half - (inf["hx"] - inf["left"])))
        dy = int(round(ch - PAD - MARGIN - 1 - inf["bottom"]))
        sy0, sy1 = max(0, -dy), min(cell.shape[0], ch - dy)
        sx0, sx1 = max(0, -dx), min(cell.shape[1], cw - dx)
        canvas[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] = cell[sy0:sy1, sx0:sx1]
        work.append(canvas)

    # refine on the lower torso: the hips are the part that should not move
    ref = premul(work[0])
    ys = np.nonzero((work[0][..., 3] > 32).sum(axis=1))[0]
    hy0 = int(ys.min()) + 4
    hx0 = half - HEAD[0] // 2
    tmpl = ref[hy0:hy0 + HEAD[1], hx0:hx0 + HEAD[0]]
    print("head template %dx%d at (%d,%d)" % (HEAD[0], HEAD[1], hx0, hy0))
    for k in range(1, len(work)):
        cur = premul(work[k])
        best = None
        for dy in range(-SEARCH, SEARCH + 1):
            for dx in range(-SEARCH, SEARCH + 1):
                y, x = hy0 - dy, hx0 - dx
                if y < 0 or x < 0 or y + HEAD[1] > ch or x + HEAD[0] > cw:
                    continue
                e = float(np.abs(tmpl - cur[y:y + HEAD[1], x:x + HEAD[0]]).mean())
                if best is None or e < best[0]:
                    best = (e, dx, dy)
        work[k] = np.roll(np.roll(work[k], best[2], axis=0), best[1], axis=1)
        print("  cell %2d: refine (%+d,%+d) err %.2f" % (k, best[1], best[2], best[0]))

    boxes = []
    for c in work:
        m = c[..., 3] > 32
        yy = np.nonzero(m.sum(axis=1))[0]
        xx = np.nonzero(m.sum(axis=0))[0]
        boxes.append((int(xx.min()), int(yy.min()), int(xx.max()), int(yy.max())))
    cx0 = max(0, min(b[0] for b in boxes) - MARGIN)
    cy0 = max(0, min(b[1] for b in boxes) - MARGIN)
    cx1 = min(cw - 1, max(b[2] for b in boxes) + MARGIN)
    cy1 = min(b[3] for b in boxes)                 # bottom cut: never a notch
    ow, oh = cx1 - cx0 + 1, cy1 - cy0 + 1
    ow += ow % 2
    oh += oh % 2
    cx1, cy1 = cx0 + ow - 1, cy0 + oh - 1
    print("frame %dx%d (%d cells)" % (ow, oh, len(work)))

    sheet = Image.new("RGBA", (ow * len(work), oh), (0, 0, 0, 0))
    for k, c in enumerate(work):
        out = np.zeros((oh, ow, 4), np.uint8)
        sy, sx = min(ch, cy1 + 1), min(cw, cx1 + 1)
        out[:sy - cy0, :sx - cx0] = c[cy0:sy, cx0:sx]
        out[..., 3] = np.where(out[..., 3] >= ALPHA_SNAP, 255, out[..., 3])
        img = Image.fromarray(out)
        img.save(os.path.join(FRAMES, "%s_%02d.png" % (PREFIX, k)))
        sheet.paste(img, (k * ow, 0))
    sheet.save(SHEET)
    print("sheet:", sheet.size, "->", SHEET)
    return ow, oh, len(work)


if __name__ == "__main__":
    main()
