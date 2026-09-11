# -*- coding: utf-8 -*-
"""Emit the game data (JSON) and the share GIF for one Martin clip.

Shared by anger_publish.py / joy_publish.py.  The timeline is never repeated
in the publish script: it is read out of the clip's martin_*_anim.py, so the
Blender scene, the JSON and the GIF cannot drift apart.

The GIF carries one image per *cut* with that cut's own duration, rather than
one image per 24fps frame: outside the patch every frame is byte identical, so
a held cut would only pad the file.
"""
import ast
import json
import os

from PIL import Image

FPS = 24
BG = (238, 240, 245)           # the world grey the Blender preview renders on


def timeline(anim_path):
    """the TL out of a <clip>_anim.py, so Blender, the JSON and the GIF cannot drift

    The TL is read, never re-typed.  It is usually a plain literal, but a clip
    whose whole tempo is one number writes that number once and uses the name
    in every cut (walk's HOLD), so module level `NAME = <int>` assignments in
    the same file are resolved first.  Anything else in the TL is still an
    error - the point is that this reads the file rather than trusting a copy.
    """
    tree = ast.parse(open(anim_path, encoding="utf-8").read())
    consts, tl = {}, None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        name = getattr(node.targets[0], "id", "")
        if name == "TL":
            tl = node.value
        elif isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
            consts[name] = node.value.value
    if tl is None:
        raise SystemExit("no TL in " + anim_path)

    def value(node):
        if isinstance(node, ast.Name):
            if node.id not in consts:
                raise SystemExit("TL uses %r, which is not an int constant in %s"
                                 % (node.id, anim_path))
            return consts[node.id]
        return ast.literal_eval(node)

    return [tuple(value(v) for v in cut.elts) for cut in tl.elts]


def publish(name, frames_dir, prefix, sheet_name, json_path, gif_path, anim_path,
            labels, note, base_frame=None, fps=FPS, extra=None):
    TL = timeline(anim_path)
    n = len([f for f in os.listdir(frames_dir)
             if f.startswith(prefix + "_") and f.endswith(".png")])
    ims = [Image.open(os.path.join(frames_dir, "%s_%02d.png" % (prefix, i))).convert("RGBA")
           for i in range(n)]
    fw, fh = ims[0].size
    if len(labels) != n:
        raise SystemExit("%d labels for %d frames" % (len(labels), n))

    frames = []
    for idx, hold in TL:
        frames += [idx] * hold

    data = {"name": name, "sheet": sheet_name, "frameWidth": fw, "frameHeight": fh,
            "frameCount": n, "fps": fps, "loop": True}
    if base_frame is not None:
        data["baseFrame"] = base_frame
    data.update(extra or {})
    data.update({"labels": labels, "note": note,
                 "timeline": [list(t) for t in TL], "frames": frames,
                 "durationSec": round(len(frames) / float(fps), 3)})
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("json: %d cuts, %d frames (%.2fs) -> %s"
          % (len(TL), len(frames), data["durationSec"], json_path))

    # GIF: flatten onto the preview grey - GIF transparency is 1 bit and would
    # tear the antialiased outline apart (see README).
    flat = []
    for im in ims:
        bg = Image.new("RGBA", im.size, BG + (255,))
        bg.alpha_composite(im)
        flat.append(bg.convert("RGB"))
    seq = [flat[i] for i, _ in TL]
    # GIF durations are 10ms quantised; round half *up* - Python's round()
    # is banker's, and a 3 frame hold (125ms) would go down to 120.
    durs = [int(hold / float(fps) * 100 + 0.5) * 10 for _, hold in TL]
    pal = seq[0].quantize(colors=255, method=Image.MEDIANCUT)
    seq = [f.quantize(palette=pal, dither=Image.NONE) for f in seq]
    os.makedirs(os.path.dirname(gif_path), exist_ok=True)
    seq[0].save(gif_path, save_all=True, append_images=seq[1:], duration=durs,
                loop=0, optimize=True, disposal=1)
    print("gif: %d images, %d ms total, %d KB -> %s"
          % (len(seq), sum(durs), os.path.getsize(gif_path) // 1024, gif_path))
    return data
