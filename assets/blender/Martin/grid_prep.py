# -*- coding: utf-8 -*-
"""Separate a grid sprite sheet (columns x rows) into aligned frames.

Cells are found from the fully transparent bands between them.  Inside each
cell only the pixels connected to that drawing are kept.

Alignment runs in two passes, because a centroid anchor is not accurate
enough: the hair silhouette and the shoulders are redrawn on every cell, so a
centroid wanders by a few pixels and the character visibly wobbles.

  A. coarse  - torso centroid in x, bottom cut in y, into an oversized canvas
  B. refine  - integer cross correlation of the FACE band against frame 0.
               The face (glasses + eyes) is the rigid, high contrast part of
               the drawing and the part a viewer actually watches, so locking
               it holds the character still.

Every frame is then cropped with the same window.  The bottom edge uses the
intersection of the frames, so no frame ends up with a transparent notch along
the bottom cut.

Usage: python grid_prep.py <source.png> <frames_dir> <sheet_out.png> [prefix]
"""
from PIL import Image
import numpy as np
import os
import sys
from collections import deque

MARGIN = 6
PAD = 24          # slack around the coarse placement, so refining cannot clip
SEARCH = 8        # pixels searched either way when refining
FACE_LO = 0.18    # face band, as a fraction of the figure height
FACE_HI = 0.50


def bands(profile):
    """ranges of consecutive non-empty entries"""
    nz = np.nonzero(profile > 0)[0]
    out, s = [], nz[0]
    for i in range(1, len(nz)):
        if nz[i] != nz[i - 1] + 1:
            out.append((int(s), int(nz[i - 1]))); s = nz[i]
    out.append((int(s), int(nz[-1])))
    return out


def biggest_component(mask):
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
    main = max(sizes, key=sizes.get)
    return lab == main, len(sizes), int(mask.sum() - (lab == main).sum())


def premul(canvas):
    """RGBA uint8 -> RGB premultiplied by alpha plus alpha, so transparent
    pixels cannot feed junk colours into the match score"""
    f = canvas.astype(np.float32)
    al = f[..., 3:4] / 255.0
    return np.concatenate([f[..., :3] * al, f[..., 3:4]], axis=2)


def refine(ref, cur, y0, y1, r=SEARCH):
    """integer (dx, dy) that best lines cur up with ref over rows y0:y1"""
    best = None
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            b = np.roll(np.roll(cur, dy, axis=0), dx, axis=1)[y0:y1]
            e = float(np.abs(ref[y0:y1] - b).mean())
            if best is None or e < best[0]:
                best = (e, dx, dy)
    return best


def separate(src, frames_dir, sheet_out, prefix="g", cols_per_row=None,
             check_png=None):
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(os.path.dirname(sheet_out), exist_ok=True)
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    a = np.asarray(im)
    al = a[..., 3] > 32

    rows = bands(al.sum(axis=1))
    print("rows:", rows)
    cells = []
    for (y0, y1) in rows:
        strip = al[y0:y1 + 1]
        cols = bands(strip.sum(axis=0))
        print("  row %4d-%4d -> %d cols %s" % (y0, y1, len(cols), cols))
        for (x0, x1) in cols:
            cells.append((x0, y0, x1, y1))

    infos = []
    for (x0, y0, x1, y1) in cells:
        sub = al[y0:y1 + 1, x0:x1 + 1]
        keep, parts, dropped = biggest_component(sub)
        ys, xs = np.nonzero(keep)
        top, bot = int(ys.min()), int(ys.max())
        band = ys > top + (bot - top) * 0.45
        hx = float(xs[band].mean())
        infos.append(dict(box=(x0, y0, x1, y1), keep=keep, hx=hx, top=top,
                          left=int(xs.min()), right=int(xs.max()),
                          bottom=bot, parts=parts, dropped=dropped))

    # ---------------------------------------------- A. coarse placement
    fw = 2 * int(np.ceil(max(max(i["hx"] - i["left"], i["right"] - i["hx"])
                            for i in infos) + MARGIN))
    fh = max(i["bottom"] - i["top"] for i in infos) + 2 * MARGIN
    fw += fw % 2
    fh += fh % 2
    cw, ch = fw + 2 * PAD, fh + 2 * PAD
    half = cw // 2

    work = []
    for k, inf in enumerate(infos):
        x0, y0, x1, y1 = inf["box"]
        cell = a[y0:y1 + 1, x0:x1 + 1].copy()
        cell[~inf["keep"]] = 0
        canvas = np.zeros((ch, cw, 4), np.uint8)
        dx = int(round(half - inf["hx"]))
        dy = int(round(ch - PAD - MARGIN - 1 - inf["bottom"]))
        sy0, sy1 = max(0, -dy), min(cell.shape[0], ch - dy)
        sx0, sx1 = max(0, -dx), min(cell.shape[1], cw - dx)
        canvas[sy0 + dy:sy1 + dy, sx0 + dx:sx1 + dx] = cell[sy0:sy1, sx0:sx1]
        work.append(canvas)
        if inf["dropped"]:
            print("  cell %2d: dropped %d stray px (%d parts)"
                  % (k, inf["dropped"], inf["parts"]))

    # ---------------------------------------------- B. refine on the face
    ref = premul(work[0])
    ys = np.nonzero((work[0][..., 3] > 32).sum(axis=1))[0]
    t0, b0 = int(ys.min()), int(ys.max())
    fy0 = t0 + int((b0 - t0) * FACE_LO)
    fy1 = t0 + int((b0 - t0) * FACE_HI)
    print("face band rows %d-%d" % (fy0, fy1))
    offs = []
    for k, canvas in enumerate(work):
        if k == 0:
            offs.append((0, 0))
            continue
        e, dx, dy = refine(ref, premul(canvas), fy0, fy1)
        work[k] = np.roll(np.roll(canvas, dy, axis=0), dx, axis=1)
        offs.append((dx, dy))
        print("  cell %2d: refine (%+d,%+d) err %.2f" % (k, dx, dy, e))
    print("refine dx %d..%d  dy %d..%d"
          % (min(o[0] for o in offs), max(o[0] for o in offs),
             min(o[1] for o in offs), max(o[1] for o in offs)))

    # ---------------------------------------------- C. common crop window
    boxes = []
    for canvas in work:
        m = canvas[..., 3] > 32
        yy = np.nonzero(m.sum(axis=1))[0]
        xx = np.nonzero(m.sum(axis=0))[0]
        boxes.append((int(xx.min()), int(yy.min()),
                      int(xx.max()), int(yy.max())))
    cx0 = max(0, min(b[0] for b in boxes) - MARGIN)
    cy0 = max(0, min(b[1] for b in boxes) - MARGIN)
    cx1 = min(cw - 1, max(b[2] for b in boxes) + MARGIN)
    cy1 = min(b[3] for b in boxes)          # intersection: never a notch
    ow, oh = cx1 - cx0 + 1, cy1 - cy0 + 1
    ow += ow % 2
    oh += oh % 2
    cx1, cy1 = cx0 + ow - 1, cy0 + oh - 1
    print("frame size: %d x %d  (%d cells)" % (ow, oh, len(work)))

    n = len(work)
    sheet = Image.new("RGBA", (ow * n, oh), (0, 0, 0, 0))
    for k, canvas in enumerate(work):
        out = np.zeros((oh, ow, 4), np.uint8)
        sy1 = min(ch, cy1 + 1)
        sx1 = min(cw, cx1 + 1)
        out[:sy1 - cy0, :sx1 - cx0] = canvas[cy0:sy1, cx0:sx1]
        img = Image.fromarray(out)
        img.save(os.path.join(frames_dir, "%s_%02d.png" % (prefix, k)))
        sheet.paste(img, (k * ow, 0))
    sheet.save(sheet_out)
    print("sheet:", sheet.size, "->", sheet_out)

    if check_png:
        tw = 150
        th = int(oh * tw / ow)
        per = 10
        rows_n = (n + per - 1) // per
        chk = Image.new("RGB", (per * tw, rows_n * th), (245, 246, 250))
        for k in range(n):
            f = Image.open(os.path.join(frames_dir, "%s_%02d.png" % (prefix, k)))
            bgim = Image.new("RGB", f.size, (245, 246, 250))
            bgim.paste(f, (0, 0), f)
            chk.paste(bgim.resize((tw, th), Image.NEAREST),
                      ((k % per) * tw, (k // per) * th))
        chk.save(check_png)
    return ow, oh, n


if __name__ == "__main__":
    src, frames_dir, sheet_out = sys.argv[1:4]
    prefix = sys.argv[4] if len(sys.argv) > 4 else "g"
    separate(src, frames_dir, sheet_out, prefix,
             check_png=r"E:\americanwomen\renders\grid_check.png")
