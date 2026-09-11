# -*- coding: utf-8 -*-
"""Build the Catherine 'walk' frames (front view, walking toward the camera).

Source: E:\\001_MAKETHEMFALLinlove素材庫\\Catherine\\walk\\*.png - ten separate
1122x1402 drawings.  This is the only **full body** clip, and it does not work
the way the face clips do.

Those freeze everything onto one base drawing and patch in the one thing that
should move.  That is only possible when most of the picture is allowed to hold
still.  A walk is the opposite: the legs swing, the hips turn, the jacket
swings, and there is no quiet region to freeze onto.  Measured on these ten -
the largest per-pixel difference against drawing 0, averaged over 40px blocks -
the head band averages 79 of 255, the torso 103 and the legs 59, and the block
means run from 40 to 235.  Nothing is quiet anywhere.

Two freezes were built and measured on the first version of this clip, which
had four drawings of the same walk, and both were thrown away:

  * a horizontal seam across the upper thighs, on the only rows where every
    silhouette agreed.  A local refit takes the outer edges from 4-5px apart to
    0-3, but the *inner* edges do not follow - the thighs are in different
    places by then - so the shading between the legs steps at the seam.
    Visible in a still.
  * a diff-shaped patch of the whole lower body.  The legs move so far that the
    "already agrees" border the mask needs does not exist: 271-468 px over 40
    across the ring, against 24 for pleasure's wink.

So this clip is **fitted and played**, all ten drawings whole.  What the fit
has to buy, then, is that the head does not move, because that is what the eye
tracks; the boil that is left is on the hair and the jacket and is the honest
cost of ten separately generated drawings.

**The scale is measured, not scored** (`spriteprep.fit_baseline`), and on a
full figure it has to be.  Scoring one box does not pin it.  The face alone is
hopeless - the hair falls across it differently in every drawing, so the match
is soft and the scale runs away to the top of whatever range it is given.  The
midriff alone - x 535..625 y 430..560, the one strip the open jacket never
covers in any of the ten - looked fine on a four drawing set and then failed
here: its error curve is flat, 23-24 of 255 all the way from scale 1.11 to
1.19, because a strip of flat skin and a horizontal waistband goes on matching
while it is scaled and slid together.  Scoring both boxes at once with one
shared shift (`fit_boxes`) is better but still weighted by contrast, and it
came out 3-5% large on several drawings.

So each box is located on its own and the **distance between them** - 290px of
baseline, the face to the waist - is compared with the same distance in drawing
0.  That ratio is the scale, and how well either box matched does not enter
into it.  The translation then comes from the face box, because the head is
what must not move.

The check is landmarks the fit never saw, and it is what chose the method:

                        scored (fit_boxes)   measured (fit_baseline)
    eye -> waistband         9.4px (5.0%)          3.9px (2.1%)
    eye -> shorts hem       16.7px (6.0%)          8.9px (3.2%)
    lowest sole              64px                   42px

with the head just as steady either way (the ten irises land within 3.7px in x
and 1.7px in y).  The ten are drawn between 1.00 and 1.11 of each other's size,
drawing 0 the smallest.

**Registering the head is not enough, because it is not a similarity.**  With
the fit done, the torso (eye to hem) varies 3.3% but the leg (hem to sole)
varies 11.6%, and the lowest sole wanders 42 rows.  Worse, the two halves of the
cycle - which have to be the *same* motion - do not match: leg lengths run
354 349 363 377 391 through one half and 374 359 353 354 355 through the other.
That is the wobble, and no scale-and-shift removes it: the drawings are drawn
with different proportions.

So the vertical scale is allowed to change at two rows (`aligned_warp`).  Above
the eyes nothing changes; the torso is stretched so every drawing's eye-to-hem
is the mean; the legs are stretched so position k of one half gets the same
hem-to-sole as position k of the other.  The map is continuous at both rows, so
there is no seam, and it folds into the one resample that was happening anyway
- measured, it costs nothing in sharpness (the share of soft vertical edges goes
17.0-18.1% to 16.9-18.2%), because a 5% change to a 0.516 downscale is nothing.

    torso spread   3.3%  ->  0.5%
    leg spread    11.6%  ->  5.5%   (what is left is the stride, and the two
    lowest sole     42px ->   21px   halves now agree to within 1 row)

The gains stay inside 0.985-1.018 on the torso and 0.954-1.051 on the legs.

Then one whole-pixel nudge per frame, refined on the eyes and nose with no hair
in the box: the fit's own translation came from a box that has hair in it, and
the hair is different every time.  Irises 3.8px of scatter -> 2.9 in x, 1.5 in y.

What is left after all that is the hair and the jacket, redrawn every time.
That cannot be fitted away.

Run:  python walk_prep.py
"""
import glob
import itertools
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
SRC_DIR = os.path.join(BASE_DIR, CHAR, "walk")
OUT = os.path.join(BASE_DIR, "blender", "develop", CHAR)
FRAMES = os.path.join(OUT, "frames_walk")
SHEET = os.path.join(OUT, "catherine_walk_sheet.png")
FITJSON = os.path.join(HERE, "walk_fit.json")
CYCLEJSON = os.path.join(HERE, "walk_cycle.json")   # checked by walk_publish
PREFIX = "wk"

TARGET_H = 724                 # the same pixel scale as every other Catherine
                               # clip, so one art pixel is one art pixel
MARGIN = 6
PAD = 60                       # the fit pushes the taller drawings down;
                               # 40 was not enough to keep the feet inside

# the two boxes, matched together with one shift: the eyes and nose, and the
# strip of midriff the open jacket never covers in any of the ten
BOXES = ((498, 140, 616, 235), (535, 430, 625, 560))
SEARCH = 140

ALPHA_SNAP = 240               # snap the body opaque, keep the drawn edge


def fit(paths):
    """scale from the face-to-waist baseline, translation from the face"""
    return SP.fit_baseline(paths, BOXES, SEARCH)


def irises(a):
    """the two blue irises, as (cx, cy) - the check that the head holds still"""
    op = a[..., 3] > 128
    r, b = a[..., 0].astype(int), a[..., 2].astype(int)
    m = op & (b - r > 30)
    m[:PAD] = False
    m[200:] = False
    lab, n = SP.components(m)
    out = []
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(ys) < 40:
            continue
        out.append((float(xs.mean()), float(ys.mean())))
    return sorted(out)


def landmarks(a, pad):
    """(eye row, shorts-hem row, lowest-sole row) of one aligned frame"""
    op = a[..., 3] > 128
    r, g, b = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    iris = op & (b - r > 30)
    iris[:pad] = False
    iris[pad + 160:] = False
    lab, n = SP.components(iris)
    ys = sorted([np.nonzero(lab == t)[0].mean() for t in range(1, n + 1)
                 if (lab == t).sum() >= 40])
    eye = float(np.mean(ys[:2]))
    den = op & (b - r > 40) & (b > 90) & (b < 220)
    lab2, n2 = SP.components(den)
    k2 = max(range(1, n2 + 1), key=lambda t: (lab2 == t).sum())
    hem = float(np.nonzero(lab2 == k2)[0].max())
    sole = float(np.nonzero(op.sum(1))[0].max())
    return eye, hem, sole


def phase(a):
    """(which side leads, how far apart the feet are) of one aligned frame

    The leading foot is the one whose sole is lower - in a front view it is the
    nearer one - and how far apart the two feet are in depth is the ratio of the
    two shoes' areas, the near one being drawn larger.  The ratio is taken
    inside one drawing, so unlike a row number it does not care what scale that
    drawing came in at, which is the whole point: the leg lengths still differ
    by 11.6% at this stage.
    """
    op = a[..., 3] > 128
    r, b = a[..., 0].astype(int), a[..., 2].astype(int)
    shoe = op & (b >= r) & (b > 120) & (r > 90)
    shoe[:len(shoe) * 2 // 3] = False
    lab, n = SP.components(shoe)
    bl = []
    for t in range(1, n + 1):
        ys, xs = np.nonzero(lab == t)
        if len(ys) < 500:
            continue
        bl.append((float(ys.max()), float(xs.mean()), len(ys)))
    bl.sort(reverse=True)
    (_, fx, fn), (_, bx, bn) = bl[0], bl[1]
    return ("R" if fx > bx else "L"), fn / float(bn)


def cycle_of(A):
    """the play order, measured: two halves, each from the footfall to the pass

    The ratio ranks the halves, but the middle of a half can be a near tie (two
    of these ten are 1.78 and 1.76), so the ends - the footfall and the pass,
    which the ratio separates cleanly - are pinned and the middle is settled by
    the drawings themselves: whichever arrangement makes the smallest total
    change from frame to frame over the legs.
    """
    n = A.shape[0]
    ph = [phase(A[i]) for i in range(n)]
    h, w = A.shape[1:3]
    V = [A[i][h // 2:, w // 5:w * 4 // 5, :3] *
         (A[i][h // 2:, w // 5:w * 4 // 5, 3:4] / 255.0) for i in range(n)]
    D = {(i, j): float(np.abs(V[i] - V[j]).mean()) for i in range(n) for j in range(n)}
    out = []
    for side in ("L", "R"):
        g = sorted([i for i in range(n) if ph[i][0] == side], key=lambda i: -ph[i][1])
        best = None
        for mid in itertools.permutations(g[1:-1]):
            cand = [g[0]] + list(mid) + [g[-1]]
            c = sum(D[cand[k], cand[k + 1]] for k in range(len(cand) - 1))
            if best is None or c < best[0]:
                best = (c, cand)
        out += best[1]
    return out, ph


def main(write=True):
    paths = SP.order(glob.glob(os.path.join(SRC_DIR, "*.png")))
    print("%d drawings" % len(paths))

    # the cache records which files it was measured from, because the source
    # folder does get replaced wholesale and a fit from the old drawings is
    # silently wrong rather than an error
    names = [os.path.basename(p) for p in paths]
    cached = json.load(open(FITJSON)) if os.path.exists(FITJSON) else None
    if cached and cached.get("sources") == names:
        fits = [tuple(f) for f in cached["fits"]]
        print("fit: reusing", os.path.basename(FITJSON))
        for k, (s, dx, dy) in enumerate(fits):
            print("  drawing %d: scale %.3f  shift (%+.0f,%+.0f)" % (k, s, dx, dy))
    else:
        if cached:
            print("fit: %s was measured from different drawings - refitting"
                  % os.path.basename(FITJSON))
        print("fit (scale from the face-to-waist baseline):")
        fits = fit(paths)
        json.dump({"sources": names, "fits": [list(f) for f in fits]},
                  open(FITJSON, "w"), indent=1)

    # pass 1: measure.  The head is registered by now but the legs are not -
    # the torso varies 3.3% and the leg 11.6% - so measure, then warp.
    A0 = SP.aligned(paths, fits, TARGET_H, PAD)
    n = A0.shape[0]
    order, ph = cycle_of(A0)
    half = len(order) // 2
    print("measured cycle: %s" % (order,))
    for k, i in enumerate(order):
        print("   %s %d  drawing %d  shoe ratio %.2f"
              % (ph[i][0], k % half, i, ph[i][1]))

    lm = [landmarks(A0[i], PAD) for i in range(n)]
    torso = np.array([h - e for e, h, _ in lm])
    leg = np.array([s_ - h for _, h, s_ in lm])
    print("torso %.1f-%.1f (%.1f%%)   leg %.1f-%.1f (%.1f%%)"
          % (torso.min(), torso.max(), 100 * np.ptp(torso) / torso.mean(),
             leg.min(), leg.max(), 100 * np.ptp(leg) / leg.mean()))

    # the two halves are the same motion, so give position k in one half the
    # same leg as position k in the other; the torso is simply made equal
    torso_t = float(torso.mean())
    leg_t = {}
    for k in range(half):
        pair = [order[k], order[k + half]]
        leg_t.update({i: float(np.mean([leg[j] for j in pair])) for i in pair})

    R = float(TARGET_H) / Image.open(paths[0]).size[1]
    warps = []
    for i in range(n):
        eye, hem, _ = lm[i]
        s_, dx, dy = fits[i]
        src = lambda c: ((c - PAD) / R - dy) / s_          # canvas row -> drawing row
        warps.append(((src(eye), torso_t / torso[i]),
                      (src(hem), leg_t[i] / leg[i])))
    print("warp gains: " + "  ".join("%d:%.3f/%.3f" % (i, warps[i][0][1], warps[i][1][1])
                                     for i in range(n)))

    A = SP.aligned_warp(paths, fits, TARGET_H, PAD, warps)
    CH, CW = A.shape[1:3]
    frames = [np.clip(A[i] + 0.5, 0, 255).astype(np.uint8) for i in range(n)]

    # last: a whole-pixel nudge so the head sits still.  The fit's translation
    # came from an SSD box that has hair in it, and the hair is different every
    # time, which biases it a pixel or two.  Refining on the eyes and the nose
    # alone - no hair - takes the irises from 3.8px of scatter to 1.7.  It is an
    # integer roll of a finished frame, so nothing is resampled twice.
    ex = float(np.mean([c[0] for c in irises(frames[order[0]])]))
    ey = float(np.mean([c[1] for c in irises(frames[order[0]])]))
    FACEBOX = (int(ex) - 36, int(ey) - 24, int(ex) + 36, int(ey) + 46)
    nudge = []
    for i in range(n):
        d = (0, 0) if i == order[0] else SP.refine_shift(frames[i], frames[order[0]],
                                                         FACEBOX, 6)
        nudge.append(d)
        frames[i] = np.roll(np.roll(frames[i], d[1], 0), d[0], 1)
    print("head nudge: " + "  ".join("%d:(%+d,%+d)" % (i, nudge[i][0], nudge[i][1])
                                     for i in range(n)))

    lm2 = [landmarks(frames[i], PAD) for i in range(n)]
    t2 = np.array([h - e for e, h, _ in lm2])
    l2 = np.array([s_ - h for _, h, s_ in lm2])
    print("after the warp: torso %.1f%%  leg %.1f%%  sole spread %.0f -> %.0f"
          % (100 * np.ptp(t2) / t2.mean(), 100 * np.ptp(l2) / l2.mean(),
             np.ptp([v[2] for v in lm]), np.ptp([v[2] for v in lm2])))

    ir = [irises(f) for f in frames]
    if all(len(v) == 2 for v in ir):
        sx = max(max(v[k][0] for v in ir) - min(v[k][0] for v in ir) for k in (0, 1))
        sy = max(max(v[k][1] for v in ir) - min(v[k][1] for v in ir) for k in (0, 1))
        print("head steadiness: irises within %.1f px in x, %.1f px in y" % (sx, sy))

    json.dump(order, open(CYCLEJSON, "w"))

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
    for i, f in enumerate(frames):
        a = f[..., 3] > 128
        print("  drawing %d: sole y %d (frame row %d)"
              % (i, np.nonzero(a.sum(1))[0].max(), np.nonzero(a.sum(1))[0].max() - cy0))

    if not write:
        return fw, fh, n, A, frames, order

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
    return fw, fh, n, order


if __name__ == "__main__":
    main()
