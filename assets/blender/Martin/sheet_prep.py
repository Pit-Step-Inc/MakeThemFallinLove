# -*- coding: utf-8 -*-
"""Generic sprite-sheet separator.

Cuts a 6-up character sheet into individual frames without letting a
neighbouring drawing bleed in:

  1. find each figure's head in the top band -> that x is the anchor
  2. cut at the thinnest column between two heads (usually fully transparent,
     but a few touching pixels are fine)
  3. inside each slice keep only the pixels connected to that figure, so any
     stray sliver from the neighbour is dropped
  4. paste every figure into a uniform canvas, aligned on its head

Usage:  python sheet_prep.py <source.png> <frames_dir> <sheet_out.png> [prefix]
"""
from PIL import Image
import numpy as np
import os
import sys
from collections import deque

NF = 6
TOP_BAND = 120
MARGIN = 8


def separate(src, frames_dir, sheet_out, prefix="f", check_png=None):
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(os.path.dirname(sheet_out), exist_ok=True)
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    a = np.asarray(im)
    al = a[..., 3] > 32
    prof = al.sum(axis=0)

    top = np.nonzero(al.sum(axis=1))[0].min()
    band = al[top:top + TOP_BAND]
    cols = np.nonzero(band.sum(axis=0) > 3)[0]
    groups, s = [], cols[0]
    for i in range(1, len(cols)):
        if cols[i] != cols[i - 1] + 1:
            groups.append((int(s), int(cols[i - 1]))); s = cols[i]
    groups.append((int(s), int(cols[-1])))
    if len(groups) != NF:
        raise SystemExit("found %d heads, expected %d: %s" % (len(groups), NF, groups))
    heads = [(g[0] + g[1]) // 2 for g in groups]

    cuts = [0]
    for i in range(NF - 1):
        seg = prof[heads[i]:heads[i + 1]]
        cuts.append(heads[i] + int(np.argmin(seg)))
    cuts.append(W)

    # ---- keep only pixels connected to this figure -----------------------
    masks, reach = [], 0
    for i in range(NF):
        x0, x1 = cuts[i], cuts[i + 1]
        sub = al[:, x0:x1]
        lab = np.zeros(sub.shape, np.int32)
        cur, sizes = 0, {}
        for y0, xx in zip(*np.nonzero(sub)):
            if lab[y0, xx]:
                continue
            cur += 1
            n = 0
            q = deque([(y0, xx)])
            lab[y0, xx] = cur
            while q:
                y, x = q.popleft()
                n += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1),
                               (1, 1), (1, -1), (-1, 1), (-1, -1)):
                    v, u = y + dy, x + dx
                    if (0 <= v < sub.shape[0] and 0 <= u < sub.shape[1]
                            and sub[v, u] and not lab[v, u]):
                        lab[v, u] = cur
                        q.append((v, u))
            sizes[cur] = n
        main = max(sizes, key=sizes.get)
        keep = lab == main
        dropped = int(sub.sum() - keep.sum())
        m = np.zeros((H, W), bool)
        m[:, x0:x1] = keep
        masks.append(m)
        # anchor on the torso: the hair silhouette changes every drawing and
        # using it as the anchor makes the character wobble sideways
        ys, xs = np.nonzero(m)
        t0, b0 = ys.min(), ys.max()
        torso = ys > t0 + (b0 - t0) * 0.45
        heads[i] = int(round(xs[torso].mean()))
        c = np.nonzero(m.sum(axis=0))[0]
        reach = max(reach, heads[i] - c.min(), c.max() - heads[i])
        print("  frame %d: slice %4d-%4d  parts %d  dropped %d px"
              % (i, x0, x1, len(sizes), dropped))

    fw = 2 * (reach + MARGIN)
    fw += fw % 2
    half = fw // 2
    print("  reach %d -> frame width %d" % (reach, fw))

    sheet = Image.new("RGBA", (fw * NF, H), (0, 0, 0, 0))
    for i in range(NF):
        canvas = np.zeros((H, fw, 4), np.uint8)
        src_x = np.arange(fw) + heads[i] - half
        ok = (src_x >= 0) & (src_x < W)
        take = a[:, src_x[ok]].copy()
        keep = masks[i][:, src_x[ok]]
        take[~keep] = 0
        canvas[:, np.nonzero(ok)[0]] = take
        img = Image.fromarray(canvas)
        img.save(os.path.join(frames_dir, "%s_%02d.png" % (prefix, i)))
        sheet.paste(img, (i * fw, 0))
    sheet.save(sheet_out)
    print("  sheet:", sheet.size, "->", sheet_out)

    if check_png:
        chk = Image.new("RGB", (NF * 185, 370), (245, 246, 250))
        for i in range(NF):
            f = Image.open(os.path.join(frames_dir, "%s_%02d.png" % (prefix, i)))
            bgim = Image.new("RGB", f.size, (245, 246, 250))
            bgim.paste(f, (0, 0), f)
            chk.paste(bgim.resize((185, 370), Image.NEAREST), (i * 185, 0))
        chk.save(check_png)
    return fw, H


if __name__ == "__main__":
    src, frames_dir, sheet_out = sys.argv[1:4]
    prefix = sys.argv[4] if len(sys.argv) > 4 else "f"
    separate(src, frames_dir, sheet_out, prefix,
             r"E:\americanwomen\renders\prep_check.png")
