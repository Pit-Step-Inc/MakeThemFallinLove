# -*- coding: utf-8 -*-
"""Build the Martin 'walk' frames (front view, walking toward the camera).

Source: E:\\001_MAKETHEMFALLinlove素材庫\\Martin\\walk\\*.png - nine separate
1122x1402 drawings.  The method is Catherine's walk (see
blender/Catherine/walk_prep.py for why a walk cannot be frozen the way a face
clip is, and for what the two-landmark fit and the vertical warp are for).
What is different here is the **source**, and it is worth stating plainly.

**Seven of the nine are the same pose.**  Which foot leads is measured from the
bottom of the silhouette - the near foot is the lower one - and confirmed by the
arms, which swing opposite the legs: in all seven right-foot-forward drawings
the left hand is the large one (832-982 px against 586-653 for the right), and
in the two left-foot-forward drawings it is the other way round.  So the split
is **7 right-forward against 2 left-forward**, and a walk needs the two halves
of the cycle covered evenly.

Worse, the seven barely differ from each other.  Over the legs, the mean
absolute difference between any two of the seven runs 10.3 to 18.1 of 255
(median 13.9), while the gap between the two groups is 26.9 to 33.9.  They are
seven takes of one pose, not seven positions of a walk - there is no passing
pose anywhere in the set.

So this clip is **four poses**, and the four were chosen by measurement:

  * the two left-forward drawings are 2 and 7, and they do differ (21.4), so
    they are the half's two positions - 2 the footfall, 7 the pass.
  * their opposite numbers were found by **mirroring**: flip a left-forward
    drawing's legs and ask which right-forward drawing it now looks like.
    2 mirrored is nearest 6 (19.2) and 7 mirrored is nearest 8 (23.0).
    6 and 8 are also the widest-apart pair inside the seven (18.1), so the
    right half actually moves rather than sitting still.

All nine are still written out, so any of the five spare takes can be swapped
in by editing CYCLE - but only four are played, because holding a half of the
cycle on one drawing while the other half gets seven is a limp, not a walk.

**To make this a proper ten-pose walk like Catherine's, the source needs more
left-foot-forward drawings and some passing poses** - about three more of each.

Run:  python walk_prep.py
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
CHAR = "Martin"
SRC_DIR = os.path.join(BASE_DIR, CHAR, "walk")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_walk")
SHEET = os.path.join(OUT, "martin_walk_sheet.png")
FITJSON = os.path.join(HERE, "walk_fit.json")
CYCLEJSON = os.path.join(HERE, "walk_cycle.json")   # checked by walk_publish
PREFIX = "wk"

TARGET_H = 724                 # the same pixel scale as every other Martin clip
MARGIN = 6
PAD = 60

# the two boxes for the fit: the glasses and eyes, and the tee hem meeting the
# jeans.  Martin's glasses are the best landmark either character has.
BOXES = ((490, 190, 600, 270), (530, 615, 620, 712))
SEARCH = 150

# the play order - a constant here, unlike Catherine's, because a 7:2 split has
# no cycle to derive.  See the docstring; main() checks the sides still hold.
CYCLE = [2, 7, 6, 8]           # L footfall, L pass, R footfall, R pass

ALPHA_SNAP = 240


def fit(paths):
    """scale from the glasses-to-waist baseline, translation from the glasses"""
    return SP.fit_baseline(paths, BOXES, SEARCH)


def irises(a):
    """the two eyes behind the glasses - the check that the head holds still"""
    op = a[..., 3] > 128
    r, b = a[..., 0].astype(int), a[..., 2].astype(int)
    m = op & (b - r > 25)
    m[:PAD] = False
    m[PAD + 160:] = False        # the eye band only: below it the jeans key too
    lab, n = SP.components(m)
    out = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(ys) < 40:
            continue
        out.append((float(xs.mean()), float(ys.mean())))
    return sorted(out)


def landmarks(a):
    """(eye row, jeans-top row, lowest-sole row)

    Catherine's middle landmark is the hem of her shorts; Martin's is the top of
    his jeans, where the grey tee ends.  Both are the row that separates what
    the torso does from what the legs do, which is where the warp changes gain.
    """
    op = a[..., 3] > 128
    r, b = a[..., 0].astype(int), a[..., 2].astype(int)
    eye = float(np.mean([c[1] for c in irises(a)[:2]]))
    jean = op & (b - r > 35) & (b > 100) & (b < 210)
    lab, n = SP.components(jean)
    k = max(range(1, n + 1), key=lambda t: (lab == t).sum())
    top = float(np.nonzero(lab == k)[0].min())
    sole = float(np.nonzero(op.sum(1))[0].max())
    return eye, top, sole


def phase(a):
    """(which side leads, how far apart the feet are)

    Catherine's shoes could be keyed by colour and counted.  Martin's cannot -
    his sneakers touch the jeans they come out of and the dark outline joins
    both feet into one blob - so the feet are separated by the **bottom of the
    silhouette** instead: take the lowest opaque row of every column, and the
    largest jump in those values is the step from the near foot to the far one.
    How wide each foot is across is then a stand-in for how near it is, and the
    ratio of the two widths does not care what scale the drawing came in at.
    """
    op = a[..., 3] > 128
    xs = np.nonzero(op.sum(0))[0]
    col, bot = [], []
    for x in range(xs.min(), xs.max() + 1):
        c = np.nonzero(op[:, x])[0]
        if len(c):
            col.append(x)
            bot.append(c.max())
    col, bot = np.array(col), np.array(bot)
    keep = bot > bot.max() - 120                  # the feet, not the arms
    col, bot = col[keep], bot[keep]
    u = np.unique(bot)
    gaps = np.diff(u)
    cut = u[int(np.argmax(gaps))] + gaps.max() / 2.0
    f, b = bot > cut, bot <= cut
    return (("R" if col[f].mean() > col[b].mean() else "L"),
            float(f.sum()) / float(b.sum()))


def main(write=True):
    paths = SP.order(glob.glob(os.path.join(SRC_DIR, "*.png")))
    n = len(paths)
    print("%d drawings" % n)

    names = [os.path.basename(p) for p in paths]
    cached = json.load(open(FITJSON)) if os.path.exists(FITJSON) else None
    if cached and cached.get("sources") == names:
        fits = [tuple(f) for f in cached["fits"]]
        print("fit: reusing", os.path.basename(FITJSON))
    else:
        if cached:
            print("fit: %s was measured from different drawings - refitting"
                  % os.path.basename(FITJSON))
        print("fit (scale from the glasses-to-waist baseline):")
        fits = fit(paths)
        json.dump({"sources": names, "fits": [list(f) for f in fits]},
                  open(FITJSON, "w"), indent=1)

    A0 = SP.aligned(paths, fits, TARGET_H, PAD)
    ph = [phase(A0[i]) for i in range(n)]
    sides = "".join(s for s, _ in ph)
    print("leading foot: %s   (%d right, %d left)"
          % (sides, sides.count("R"), sides.count("L")))
    for i in range(n):
        print("   drawing %d  %s  foot-width ratio %.2f%s"
              % (i, ph[i][0], ph[i][1], "   <- played" if i in CYCLE else ""))
    want = ["L", "L", "R", "R"]
    got = [ph[i][0] for i in CYCLE]
    if got != want:
        raise SystemExit("CYCLE %s leads with %s, expected %s - the source has "
                         "changed, re-measure before trusting the order"
                         % (CYCLE, got, want))

    lm = [landmarks(A0[i]) for i in range(n)]
    torso = np.array([t - e for e, t, _ in lm])
    leg = np.array([s - t for _, t, s in lm])
    print("torso %.1f-%.1f (%.1f%%)   leg %.1f-%.1f (%.1f%%)"
          % (torso.min(), torso.max(), 100 * np.ptp(torso) / torso.mean(),
             leg.min(), leg.max(), 100 * np.ptp(leg) / leg.mean()))

    # the two halves are the same motion, so the played pairs - footfall with
    # footfall, pass with pass - are given the same leg.  A spare take follows
    # whichever played drawing of its own side it looks most like.
    V = [A0[i][A0.shape[1] // 2:, ..., :3] * (A0[i][A0.shape[1] // 2:, ..., 3:4] / 255.0)
         for i in range(n)]
    torso_t = float(torso.mean())
    leg_t = {}
    for k in (0, 1):
        a_, b_ = CYCLE[k], CYCLE[k + 2]
        leg_t[a_] = leg_t[b_] = float(np.mean([leg[a_], leg[b_]]))
    for i in range(n):
        if i in leg_t:
            continue
        same = [c for c in CYCLE if ph[c][0] == ph[i][0]]
        near = min(same, key=lambda c: float(np.abs(V[i] - V[c]).mean()))
        leg_t[i] = leg_t[near]

    R = float(TARGET_H) / Image.open(paths[0]).size[1]
    warps = []
    for i in range(n):
        eye, top, _ = lm[i]
        s_, dx, dy = fits[i]
        src = lambda c: ((c - PAD) / R - dy) / s_
        warps.append(((src(eye), torso_t / torso[i]),
                      (src(top), leg_t[i] / leg[i])))
    print("warp gains: " + "  ".join("%d:%.3f/%.3f" % (i, warps[i][0][1], warps[i][1][1])
                                     for i in range(n)))

    A = SP.aligned_warp(paths, fits, TARGET_H, PAD, warps)
    CH, CW = A.shape[1:3]
    frames = [np.clip(A[i] + 0.5, 0, 255).astype(np.uint8) for i in range(n)]

    ex = float(np.mean([c[0] for c in irises(frames[CYCLE[0]])]))
    ey = float(np.mean([c[1] for c in irises(frames[CYCLE[0]])]))
    FACEBOX = (int(ex) - 36, int(ey) - 26, int(ex) + 36, int(ey) + 44)
    for i in range(n):
        d = (0, 0) if i == CYCLE[0] else SP.refine_shift(frames[i], frames[CYCLE[0]],
                                                        FACEBOX, 6)
        frames[i] = np.roll(np.roll(frames[i], d[1], 0), d[0], 1)

    lm2 = [landmarks(frames[i]) for i in range(n)]
    t2 = np.array([t - e for e, t, _ in lm2])
    l2 = np.array([s - t for _, t, s in lm2])
    print("after the warp: torso %.1f%%  leg %.1f%%  sole spread %.0f -> %.0f"
          % (100 * np.ptp(t2) / t2.mean(), 100 * np.ptp(l2) / l2.mean(),
             np.ptp([v[2] for v in lm]), np.ptp([v[2] for v in lm2])))
    ir = [irises(f) for f in frames]
    if all(len(v) >= 2 for v in ir):
        sx = max(max(v[k][0] for v in ir) - min(v[k][0] for v in ir) for k in (0, 1))
        sy = max(max(v[k][1] for v in ir) - min(v[k][1] for v in ir) for k in (0, 1))
        print("head steadiness: eyes within %.1f px in x, %.1f px in y" % (sx, sy))

    json.dump(CYCLE, open(CYCLEJSON, "w"))

    # every frame shares one size, so crop to the union, not to one drawing
    m = np.any(np.stack([f[..., 3] > 32 for f in frames]), 0)
    ys = np.nonzero(m.sum(1))[0]
    xs = np.nonzero(m.sum(0))[0]
    cx0 = max(0, int(xs.min()) - MARGIN)
    cx1 = min(CW - 1, int(xs.max()) + MARGIN)
    cy0 = max(0, int(ys.min()) - MARGIN)
    cy1 = min(CH - 1, int(ys.max()) + MARGIN)
    fw, fh = cx1 - cx0 + 1, cy1 - cy0 + 1
    fw += fw % 2
    fh += fh % 2
    cx1, cy1 = cx0 + fw - 1, cy0 + fh - 1
    print("frame %dx%d  crop x %d..%d y %d..%d" % (fw, fh, cx0, cx1, cy0, cy1))
    for i in CYCLE:
        a = frames[i][..., 3] > 128
        print("  played %d: sole frame row %d"
              % (i, np.nonzero(a.sum(1))[0].max() - cy0))

    if not write:
        return fw, fh, n, frames

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
    return fw, fh, n


if __name__ == "__main__":
    main()
