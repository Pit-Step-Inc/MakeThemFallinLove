# -*- coding: utf-8 -*-
"""Character-agnostic pieces of the Martin/Catherine sprite pipeline.

Every clip is built the same way: fit each separate drawing onto the first one
on a rigid band of the face, render them all into one canvas, then emit each
frame as one base drawing with only a patch of it taken from its own drawing.
The fitting and the patch mask are the same code whoever is being drawn, so
they live here rather than in any one clip's prep.

  order / gray / ssd_map / fit_all / aligned   the fit
  ramp_mask / patch_mask                       the patch

Clip-specific constants (the template box, the polygons, the base) stay in the
clip's own <clip>_prep.py.
"""
import os
import re
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def ramp_mask(shape, pts, width):
    """1.0 inside, a `width` px linear ramp, exactly 0 outside the polygon

    A Gaussian would leave a 5% tail, and a 5% tail over a 250 level edge is a
    visible 12 level shimmer; eroding the polygon keeps the mask exactly zero
    outside it.
    """
    h, w = shape
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    acc = np.zeros((h, w), np.float32)
    cur = m
    for _ in range(width):
        acc += np.asarray(cur).astype(np.float32) / 255.0
        cur = cur.filter(ImageFilter.MinFilter(3))
    return acc / width


def patch_mask(shape, polys, ramp, pad):
    """union of several polygons' ramp masks, in padded canvas coordinates"""
    m = np.zeros(shape, np.float32)
    for p in polys:
        m = np.maximum(m, ramp_mask(shape, [(x + pad, y + pad) for x, y in p], ramp))
    return m


def components(mask):
    """8-connected labelling"""
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



def order(paths):
    """ChatGPT's ' (n)' suffix sorts as text; sort it as a number"""
    def k(p):
        m = re.search(r"\((\d+)\)", os.path.basename(p))
        return int(m.group(1)) if m else 0
    return sorted(paths, key=k)

def gray(rgba):
    """premultiplied luma - background is alpha 0, so it must not read as white"""
    f = rgba.astype(np.float32)
    a = f[..., 3] / 255.0
    return (0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]) * a

def ssd_map(img, tpl):
    """sum of squared differences of `tpl` against every position of `img`

    Σ(I-T)² = ΣI² - 2ΣI·T + ΣT²; the two windowed sums are correlations, so
    both come out of one pair of FFTs instead of a 140x290x141x141 loop.
    """
    H, W = img.shape
    th, tw = tpl.shape
    fh, fw = H, W
    F = np.fft.rfft2(img, s=(fh, fw))
    F2 = np.fft.rfft2(img * img, s=(fh, fw))
    T = np.fft.rfft2(tpl[::-1, ::-1], s=(fh, fw))
    ones = np.fft.rfft2(np.ones((th, tw), np.float32), s=(fh, fw))
    corr = np.fft.irfft2(F * T, s=(fh, fw))
    sq = np.fft.irfft2(F2 * ones, s=(fh, fw))
    # correlation with the flipped kernel lands the (0,0) window at (th-1,tw-1)
    corr = corr[th - 1:, tw - 1:]
    sq = sq[th - 1:, tw - 1:]
    return sq - 2.0 * corr + float((tpl * tpl).sum()), corr.shape

def fit_all(paths, tpl_box, scales, search, verbose=True):
    """scale + integer shift of every drawing onto drawing 0, on the face band"""
    ref = np.asarray(Image.open(paths[0]).convert("RGBA"))
    H, W = ref.shape[:2]
    g0 = gray(ref)
    x0, y0, x1, y1 = tpl_box
    tpl = g0[y0:y1, x0:x1]
    th, tw = tpl.shape
    fits = [(1.0, 0.0, 0.0)]
    for k, p in enumerate(paths[1:], 1):
        im = Image.open(p).convert("RGBA")
        best = None
        for s in scales:
            r = np.asarray(im.resize((int(round(W * s)), int(round(H * s))),
                                     Image.LANCZOS).convert("RGBA"))
            gi = gray(r)
            # where the template would sit if the drawing were unscaled
            cy, cx = int(round(y0 * s)), int(round(x0 * s))
            pad = np.zeros((gi.shape[0] + 2 * search, gi.shape[1] + 2 * search),
                           np.float32)
            pad[search:search + gi.shape[0], search:search + gi.shape[1]] = gi
            win = pad[cy:cy + th + 2 * search, cx:cx + tw + 2 * search]
            m, shape = ssd_map(win, tpl)
            m = m[:2 * search + 1, :2 * search + 1]
            i = int(np.argmin(m))
            oy, ox = divmod(i, m.shape[1])
            err = float(m[oy, ox]) / (th * tw)
            # position of the template in the scaled drawing
            py, px = cy + oy - search, cx + ox - search
            # shift that brings the scaled drawing onto the reference
            dy, dx = y0 - py, x0 - px
            if best is None or err < best[0]:
                best = (err, float(s), float(dx), float(dy))
        fits.append(best[1:])
        if verbose:
            print("  drawing %2d: scale %.3f  shift (%+.0f,%+.0f)  rms %.2f"
                  % (k, best[1], best[2], best[3], np.sqrt(best[0])))
    return fits


def fit_boxes(paths, boxes, scales, search, verbose=True):
    """scale + integer shift onto drawing 0, matching several boxes at once

    fit_all matches one box.  That is enough for a bust shot, where the face
    fills the frame, but on a full figure one box does not pin the scale: a
    strip of midriff is mostly flat skin and a horizontal waistband, so it goes
    on matching while it is scaled and slid together, and the error curve comes
    out flat (measured on Catherine's walk: 23-24 of 255 everywhere from scale
    1.11 to 1.19, and the drawings that landed in that flat stretch disagreed
    with every independent measure of their size).

    Two boxes far apart in y fix it.  The shift is shared, so a wrong scale
    cannot line both of them up at once, and the long baseline between them
    turns a small scale error into a large residual.  Pass the boxes as
    (x0, y0, x1, y1) in drawing 0's pixels - the face and the waist, say - and
    keep each of them off the parts that are redrawn every take.

    Returns [(scale, dx, dy), ...] like fit_all, drawing 0 first and identity.
    """
    ref = np.asarray(Image.open(paths[0]).convert("RGBA"))
    H, W = ref.shape[:2]
    g0 = gray(ref)
    tpls = [(b, g0[b[1]:b[3], b[0]:b[2]]) for b in boxes]
    ax, ay = boxes[0][0], boxes[0][1]

    fits = [(1.0, 0.0, 0.0)]
    for k, p in enumerate(paths[1:], 1):
        im = Image.open(p).convert("RGBA")
        best = None
        for s in scales:
            gi = gray(np.asarray(im.resize((int(round(W * s)), int(round(H * s))),
                                           Image.LANCZOS).convert("RGBA")))
            pad = np.zeros((gi.shape[0] + 2 * search, gi.shape[1] + 2 * search),
                           np.float32)
            pad[search:search + gi.shape[0], search:search + gi.shape[1]] = gi
            tot = None
            for (x0, y0, x1, y1), tpl in tpls:
                th, tw = tpl.shape
                cy, cx = int(round(y0 * s)), int(round(x0 * s))
                win = pad[cy:cy + th + 2 * search, cx:cx + tw + 2 * search]
                m, _ = ssd_map(win, tpl)
                m = m[:2 * search + 1, :2 * search + 1] / float(th * tw)
                tot = m if tot is None else tot + m
            i = int(np.argmin(tot))
            oy, ox = divmod(i, tot.shape[1])
            err = float(tot[oy, ox])
            dx = ax - (int(round(ax * s)) + ox - search)
            dy = ay - (int(round(ay * s)) + oy - search)
            if best is None or err < best[0]:
                best = (err, float(s), float(dx), float(dy))
        fits.append(best[1:])
        if verbose:
            print("  drawing %2d: scale %.3f  shift (%+.0f,%+.0f)  err %.0f"
                  % (k, best[1], best[2], best[3], best[0]))
    return fits



def fit_baseline(paths, boxes, search, iters=4, verbose=True):
    """scale from the distance between two landmarks, translation from the first

    fit_boxes matches two boxes with one shared shift and picks the scale with
    the lowest summed error.  That is better than one box, but the sum is still
    weighted by contrast, so a box whose match is soft and biased - the face,
    with different hair falling across it every time - can drag the scale up.
    Measured on Catherine's walk, fit_boxes came out 3-5% large on several
    drawings, against every independent measure of their size.

    This measures the scale instead of scoring it.  Locate each box on its own,
    take the vertical distance between where the two landed, and compare it with
    the same distance in drawing 0: that ratio *is* the scale, and nothing about
    how well either box matched enters into it.  A mis-scaled template still
    centres on the right feature, so two or three iterations converge (the
    scale is re-measured on the rescaled drawing each time).

    `boxes` is ((x0,y0,x1,y1), (x0,y0,x1,y1)), far apart in y; the first one is
    also what the translation is taken from, so put it on whatever must not
    move - for a walk, the face.

    Returns [(scale, dx, dy), ...] like fit_all.
    """
    (ax, ay, _, _), (_, by, _, _) = boxes
    base0 = float(by - ay)
    ref = np.asarray(Image.open(paths[0]).convert("RGBA"))
    H, W = ref.shape[:2]
    g0 = gray(ref)
    tpls = [(b, g0[b[1]:b[3], b[0]:b[2]]) for b in boxes]

    def locate(gi, s, box, tpl):
        th, tw = tpl.shape
        cy, cx = int(round(box[1] * s)), int(round(box[0] * s))
        pad = np.zeros((gi.shape[0] + 2 * search, gi.shape[1] + 2 * search), np.float32)
        pad[search:search + gi.shape[0], search:search + gi.shape[1]] = gi
        win = pad[cy:cy + th + 2 * search, cx:cx + tw + 2 * search]
        m, _ = ssd_map(win, tpl)
        m = m[:2 * search + 1, :2 * search + 1]
        i = int(np.argmin(m))
        oy, ox = divmod(i, m.shape[1])
        return cy + oy - search, cx + ox - search

    fits = [(1.0, 0.0, 0.0)]
    for k, p in enumerate(paths[1:], 1):
        im = Image.open(p).convert("RGBA")
        s = 1.0
        for _ in range(iters):
            gi = gray(np.asarray(im.resize((int(round(W * s)), int(round(H * s))),
                                           Image.LANCZOS).convert("RGBA")))
            (fy, fx), (my, _) = (locate(gi, s, *tpls[0]), locate(gi, s, *tpls[1]))
            s = base0 / ((my - fy) / s)
        fits.append((float(s), float(ax - fx), float(ay - fy)))
        if verbose:
            print("  drawing %2d: scale %.3f  shift (%+.0f,%+.0f)"
                  % (k, fits[-1][0], fits[-1][1], fits[-1][2]))
    return fits


def aligned(paths, fits, target_h, pad):
    """the drawings, scaled and shifted onto one padded canvas at target_h"""
    W, H = Image.open(paths[0]).size
    R = float(target_h) / H
    CW = int(np.ceil(W * R)) + 2 * pad
    CH = target_h + 2 * pad
    out = []
    for p, (s, dx, dy) in zip(paths, fits):
        im = Image.open(p).convert("RGBA")
        # one resample: source -> reference frame -> output resolution
        rs = s * R
        r = im.resize((int(round(W * rs)), int(round(H * rs))), Image.LANCZOS)
        c = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        c.paste(r, (pad + int(round(dx * R)), pad + int(round(dy * R))))
        out.append(np.asarray(c).astype(np.float32))
    print("output scale %.4f, canvas %dx%d" % (R, CW, CH))
    return np.stack(out)



def _lanczos_rows(a, pos, scale, taps=3):
    """resample the rows of `a` at source positions `pos`, Lanczos-`taps`

    `scale` is the local source-rows-per-output-row at each position, so the
    kernel widens where the image is being shrunk and does not alias.
    """
    H = a.shape[0]
    out = np.zeros((len(pos),) + a.shape[1:], np.float32)
    for j, (p, sc) in enumerate(zip(pos, scale)):
        r = max(1.0, float(sc))
        lo = int(np.floor(p - taps * r))
        hi = int(np.ceil(p + taps * r))
        k = np.arange(lo, hi + 1)
        x = (k - p) / r
        w = np.sinc(x) * np.sinc(x / taps)
        w[np.abs(x) >= taps] = 0.0
        if w.sum() == 0:
            w[np.argmin(np.abs(x))] = 1.0
        w /= w.sum()
        out[j] = np.tensordot(w, a[np.clip(k, 0, H - 1)], axes=(0, 0))
    return out


def aligned_warp(paths, fits, target_h, pad, warps):
    """aligned(), but each drawing may be stretched vertically below a landmark

    A walk built from separately generated drawings comes out with the head
    registered and the *legs* still disagreeing: on Catherine's ten the torso
    (eye to hem) varies 3.3% but the leg (hem to sole) varies 11.6%, and the two
    halves of the cycle - which have to be the same motion - do not match at
    all.  No similarity transform fixes that, because it is not a similarity:
    the drawings are drawn with different proportions.

    So the vertical scale is allowed to change at two landmark rows.  `warps[i]`
    is ((y1, g1), (y2, g2)) in drawing i's own pixels: everything above y1 keeps
    the ordinary scale, y1..y2 is stretched by g1 and below y2 by g2, with the
    map continuous at both rows so there is no seam - at y1 the gain changes but
    the position does not.  Anchoring at y1 (the eyes) is what keeps the head
    where the fit put it.

    Horizontally nothing changes, and the whole thing is still **one** resample:
    x through PIL, y through a Lanczos kernel that widens where the image is
    being shrunk.  Do not follow this with another resize.
    """
    W, H = Image.open(paths[0]).size
    R = float(target_h) / H
    CW = int(np.ceil(W * R)) + 2 * pad
    CH = target_h + 2 * pad
    out = []
    for p, (s, dx, dy), ((y1, g1), (y2, g2)) in zip(paths, fits, warps):
        im = Image.open(p).convert("RGBA")
        rs = s * R
        # x only; the rows stay in the drawing's own resolution for the y pass
        wide = np.asarray(im.resize((int(round(W * rs)), H), Image.LANCZOS),
                          dtype=np.float32)
        # source row -> canvas row, piecewise linear and continuous
        o1 = y1 * rs + dy * R + pad
        o2 = o1 + (y2 - y1) * rs * g1

        def src_of(o):
            if o <= o1:
                return y1 + (o - o1) / rs
            if o <= o2:
                return y1 + (o - o1) / (rs * g1)
            return y2 + (o - o2) / (rs * g2)

        rows = np.arange(CH, dtype=np.float64)
        pos = np.array([src_of(o) for o in rows])
        step = np.array([1.0 / rs if o <= o1 else
                         (1.0 / (rs * g1) if o <= o2 else 1.0 / (rs * g2))
                         for o in rows])
        tall = _lanczos_rows(wide, pos, step)
        c = np.zeros((CH, CW, 4), np.float32)
        x0 = pad + int(round(dx * R))
        xs = slice(max(0, x0), min(CW, x0 + tall.shape[1]))
        c[:, xs] = tall[:, max(0, -x0):xs.stop - x0]
        out.append(np.clip(c, 0, 255))
    print("output scale %.4f, canvas %dx%d (vertically warped)" % (R, CW, CH))
    return np.stack(out)


def hide_teeth(img, box, skin, min_px=25, redness=120, luma=110, verbose=True):
    """Paint the teeth out of one drawing's mouth, in place.

    Some takes of an open mouth draw a strip of teeth and some do not, at the
    same mouth opening - so cut against each other they flash on and off.

    The test is "bright but not red".  Everything a mouth is made of is red:
    the pink tongue (242,103,85) and the dark red roof (210,60,58) both score
    ~150 on R-(G+B)/2, and the rim is red too but dark.  Enamel runs from
    255,255,255 down through a 226,130,126 fringe - all bright, all under 120.
    Testing brightness *and* redness rather than chroma is what catches the
    antialiased fringe; leaving it behind is what turns the repaint grey.

    The teeth are then filled by repeatedly averaging each one's non-teeth
    neighbours inside the mouth, so the fill grows in from the dark red above
    and the tongue below - which is what the takes without teeth have there.

    `box` is (x0, y0, x1, y1) around the mouth in img's coordinates; it keeps
    the nose highlight - also bright and not red - out of the test.  Components
    smaller than min_px are left alone, so a lip highlight is not a tooth.
    Returns the number of pixels repainted.
    """
    x0, y0, x1, y1 = box
    sub = img[y0:y1, x0:x1]
    rgb = sub[..., :3].astype(np.float32)
    ns = (np.abs(rgb - np.asarray(skin, np.float32)).sum(2) > 70) & (sub[..., 3] > 128)
    lab, n = components(ns)
    if n == 0:
        return 0
    red = rgb[..., 0] - 0.5 * (rgb[..., 1] + rgb[..., 2])
    seed = red.copy()
    seed[~ns] = -1e9
    mouth = lab == lab[np.unravel_index(np.argmax(seed), seed.shape)]

    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    cand = mouth & (lum > luma) & (red < redness)
    tl, tn = components(cand)
    teeth = np.zeros_like(cand)
    for c in range(1, tn + 1):
        m = tl == c
        if m.sum() >= min_px:
            teeth |= m
    if not teeth.any():
        return 0
    # Grow the strip 2 px into the mouth before filling.  The enamel does not
    # end at the threshold: it fades out through a salmon fringe that scores
    # 112-134 on redness, right up against the tongue's 148, so no threshold
    # separates them.  Repainting a two pixel collar as well erases the fringe;
    # the collar is only ever tongue or roof, both of which the fill would have
    # produced there anyway.  Dark pixels are held back so the rim survives.
    for _ in range(2):
        grown = teeth.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1),
                       (1, 1), (1, -1), (-1, 1), (-1, -1)):
            grown |= np.roll(np.roll(teeth, dy, axis=0), dx, axis=1)
        teeth = grown & mouth & (lum > 70)

    out = rgb.copy()
    todo = teeth.copy()
    while todo.any():
        acc = np.zeros_like(out)
        cnt = np.zeros(todo.shape, np.float32)
        src = mouth & ~todo
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s = np.roll(np.roll(src, dy, axis=0), dx, axis=1)
            v = np.roll(np.roll(out, dy, axis=0), dx, axis=1)
            acc += np.where(s[..., None], v, 0.0)
            cnt += s
        fill = todo & (cnt > 0)
        if not fill.any():
            break
        out[fill] = acc[fill] / cnt[fill][:, None]
        todo &= ~fill
    for _ in range(2):                 # smooth the fill, not its surroundings
        sm = out.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sm += np.roll(np.roll(out, dy, axis=0), dx, axis=1)
        sm /= 5.0
        out[teeth] = sm[teeth]

    sub[..., :3] = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    if verbose:
        print("    teeth: %d px repainted" % int(teeth.sum()))
    return int(teeth.sum())


def diff_patch(img, base, box, core, tol=12, grow=6, ramp=3):
    """A patch shaped by what actually changed, rather than by a traced outline.

    For the mouth a hand traced polygon is right: the drawn mouths differ so
    much that no automatic outline would hold all of them, and the cheek around
    them is flat enough to put a seam anywhere.  For an eye it is the wrong
    tool.  The eye is ringed by the lid crease, the lashes and the bangs, and a
    polygon has to cut *through* one of them - the ramp then straddles an edge
    the two drawings disagree about, and it ghosts (measured: 237-252 of 255
    across the ring, against 11 for the mouth patch).

    So take the mask from the difference instead: the pixels this drawing
    changes, grown by `grow`, with a `ramp` px falloff.  The seam then lands
    exactly where the two drawings already agree, whatever shape that is.
    This is what freeze_talk's blink patch does, generalised.

    `box` bounds the search and `core` says which blobs to keep - a component
    is kept only if it reaches into `core`, so hair boiling elsewhere in the
    box is left frozen.  Give `box` enough margin that the grown mask never
    reaches its edge, or the clip becomes the seam.

    Returns the float mask.
    """
    d = np.abs(img[..., :3].astype(np.float32) - base[..., :3].astype(np.float32)).max(2)
    d = np.maximum(d, np.abs(img[..., 3].astype(np.float32) - base[..., 3].astype(np.float32)))
    m = np.zeros(d.shape, bool)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = d[y0:y1, x0:x1] > tol
    lab, n = components(m)
    cx0, cy0, cx1, cy1 = core
    keep = np.zeros(d.shape, bool)
    for c in range(1, n + 1):
        b = lab == c
        if b[cy0:cy1, cx0:cx1].any():
            keep |= b
    g = Image.fromarray((keep * 255).astype(np.uint8))
    for _ in range(grow):
        g = g.filter(ImageFilter.MaxFilter(3))
    acc = np.zeros(d.shape, np.float32)
    cur = Image.fromarray(np.asarray(g))
    for _ in range(ramp):
        acc += np.asarray(cur).astype(np.float32) / 255.0
        cur = cur.filter(ImageFilter.MinFilter(3))
    return acc / ramp


def colour_patch(img, base, box, key, below=None, min_px=8, min_below=6, feather=True):
    """A patch shaped by the *feature's own colour*, not by an outline or a diff.

    The third kind of patch, for a feature that has to be lifted onto a frozen
    base but whose surroundings are redrawn every take.  A traced polygon needs
    quiet skin to seam against; diff_patch needs the change to have a quiet
    edge.  A tear has neither - it hangs off the lower lid, and the lid, the
    lashes and the hair all boil - so both of those ghost.

    But a tear is the only bluish thing on a face.  Keying on that lifts the
    tear *and nothing else*, so the only seam is the tear's own outline, and
    that lands on flat cheek.  The lid underneath stays the base's, which is
    what a tear lying over a lash looks like anyway.

    `key(rgb) -> bool` picks the feature's colour.  `below` is a dict
    x -> y giving a line the blob must reach past (the base's lid bottom, so
    the sclera highlight shifting *inside* the eye is not mistaken for a tear);
    a blob is kept only if `min_below` of its pixels are under it.

    Returns the float mask, or None when this drawing has no feature.
    """
    x0, y0, x1, y1 = box
    rgb = img[..., :3].astype(np.float32)
    d = np.abs(rgb - base[..., :3].astype(np.float32)).max(2)
    m = np.zeros(d.shape, bool)
    m[y0:y1, x0:x1] = (key(rgb) & (d > 35))[y0:y1, x0:x1]
    lab, n = components(m)
    keep = np.zeros(d.shape, bool)
    for c in range(1, n + 1):
        b = lab == c
        if b.sum() < min_px:
            continue
        if below is not None:
            ys, xs = np.nonzero(b)
            if sum(1 for y, x in zip(ys, xs) if y > below.get(x, 10 ** 9)) < min_below:
                continue
        keep |= b
    if not keep.any():
        return None
    g = Image.fromarray((keep * 255).astype(np.uint8))
    acc = np.asarray(g).astype(np.float32) / 255.0
    if feather:                        # half a pixel of skirt, no more: the
        wide = np.asarray(g.filter(ImageFilter.MaxFilter(3))).astype(np.float32) / 255.0
        acc = np.maximum(acc, wide * 0.5)
    return acc


def lid_line(base, box, skin, tol=55):
    """x -> the lowest non-skin row of `base` in each column of `box`

    Used as the `below` argument of colour_patch: everything under this line is
    cheek, everything on or above it is eye.
    """
    x0, y0, x1, y1 = box
    ns = (np.abs(base[..., :3].astype(np.float32) - np.asarray(skin, np.float32)).sum(2) > tol)         & (base[..., 3] > 128)
    out = {}
    for x in range(x0, x1):
        nz = np.nonzero(ns[y0:y1, x])[0]
        out[x] = y0 + int(nz[-1]) if len(nz) else y0
    return out


def refine_shift(img, base, box, search=8):
    """the integer shift that best lands `img` on `base` over `box`

    diff_patch works by asking what a drawing changed, so anything the global
    fit left misregistered turns into "change" and drags the patch outward.
    Refitting locally first removes that.  Pick a `box` that does NOT contain
    the thing being patched, or the feature itself drives the fit: to patch a
    winking eye, refine on the other eye and the nose bridge.

    Returns (dx, dy).
    """
    x0, y0, x1, y1 = box
    b = base[y0:y1, x0:x1, :3].astype(np.float32)
    best = None
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            s = np.roll(np.roll(img, dy, axis=0), dx, axis=1)[y0:y1, x0:x1, :3]
            e = float(np.abs(s.astype(np.float32) - b).mean())
            if best is None or e < best[0]:
                best = (e, dx, dy)
    return best[1], best[2]


def colour_region(img, key, grow=0):
    """the pixels of `img` that `key(rgb) -> bool` picks, optionally grown

    Used to *protect* something from a patch rather than to lift it: a patch
    shaped by the difference will always drag in whatever else happens to be
    redrawn near the feature, and the loudest thing on a face is hair - a bang
    shifting a pixel reads as the hairstyle twitching.  Subtracting the hair of
    both drawings from the mask freezes it, and the seam then falls on the hair
    edge, where the skin either side of it is flat and identical.

    Grow it a few pixels so the feature's own dark outline is protected too.
    """
    h = key(img[..., :3].astype(np.float32))
    if grow:
        g = Image.fromarray((h * 255).astype(np.uint8))
        for _ in range(grow):
            g = g.filter(ImageFilter.MaxFilter(3))
        h = np.asarray(g) > 0
    return h
