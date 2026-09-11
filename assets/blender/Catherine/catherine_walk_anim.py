# -*- coding: utf-8 -*-
"""Frame-by-frame 2D animation: Catherine 'walk' (front view, one loop).

Ten drawings, all ten played whole - see walk_prep.py for why nothing is
frozen here.  The order is not the order they arrive in; it is the walk, and it
was measured rather than eyeballed.

**Which foot is forward** is the one whose sole is lower: in a front view the
leading foot is nearer the camera.  **How far forward** is the ratio of the two
shoes' areas - the near shoe is drawn larger - which is the same reading taken
a second way, and unlike the sole rows it does not care what scale the drawing
came in at.  That splits the ten into two halves of five, each running from the
footfall (shoes furthest apart in depth) to the pass (nearest together):

    left forward     9 (1.84)  8 (1.76)  3 (1.78)  4 (1.68)  5 (1.36)
    right forward    6 (1.81)  2 (1.78)  7 (1.63)  0 (1.61)  1 (1.31)

The order within each half was then confirmed against the drawings themselves.
Taking the mean absolute difference over the legs between every pair, and
searching all 28800 cycles that keep the two halves contiguous, the cheapest
one that also runs each half footfall-to-pass is this order, at 203.0; the
cheapest cycle of all is 200.0, 1.5% less, and it gets there by running one of
the halves *backwards*, which is not a walk.  The two expensive steps, 40 and
34, are the two footfalls, where the trailing foot really does leave the ground
and swing back - the other eight steps cost 11 to 23.

**Tempo.**  Ten poses is a whole cycle, two steps.  A uniform hold gives
288/HOLD steps a minute, which is 144 at HOLD 2 and 96 at HOLD 3 and nothing in
between, because a hold is whole frames - and 144 reads as hurrying while 96 is
an amble.

So the hold is uneven: **SLOW on the two cuts after each footfall, FAST on the
three that swing through to the pass.**  3 3 2 2 2 is 12 frames a half, 24 for
the cycle, exactly 1.00s and **120 steps a minute** - a plain walking cadence.
Holding the footfall longer is not a compromise, it is how a walk is timed: the
weight comes down and the body is in double support, then the swing is quick.

The one rule is that **both halves must get the same pattern**.  They do here,
and that is what keeps it a walk rather than a limp - the same reason the leg
lengths are warped to match in walk_prep.  To go faster make both of them 2
(0.83s, 144); slower, both 3 (1.25s, 96).
"""
import bpy, os, math, glob

SRC = r"E:/001_MAKETHEMFALLinlove素材庫/blender/develop/Catherine/frames_walk/wk_%02d.png"
NF = len(glob.glob(os.path.dirname(SRC) + "/wk_*.png"))
PLANE_H = 4.40
PLANE_Y = 0.50
FPS = 24
PREFIX = "CatherineWalk_"

SLOW = 3                                   # the weight coming down
FAST = 2                                   # the swing through
TL = [
    (9, SLOW), (8, SLOW), (3, FAST), (4, FAST), (5, FAST),   # left foot down,
                                                 # the right swings through
    (6, SLOW), (2, SLOW), (7, FAST), (0, FAST), (1, FAST),   # right foot down,
                                                 # the left swings through
]

sc = bpy.context.scene
win = bpy.context.window_manager.windows[0]
if win.screen.is_animation_playing:
    with bpy.context.temp_override(window=win):
        bpy.ops.screen.animation_cancel(restore_frame=False)
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

for ob in list(bpy.data.objects):
    if ob.type in ('MESH', 'GREASEPENCIL'):
        bpy.data.objects.remove(ob, do_unlink=True)
for m in list(bpy.data.materials):
    if m.users == 0:
        bpy.data.materials.remove(m)

img0 = bpy.data.images.load(SRC % 0, check_existing=True)
img0.reload()
W, H = img0.size
PLANE_W = PLANE_H * W / float(H)

planes = []
for i in range(NF):
    pname = PREFIX + "%02d" % i
    me = bpy.data.meshes.new(pname)
    me.from_pydata([(-PLANE_W / 2, 0, -PLANE_H / 2), (PLANE_W / 2, 0, -PLANE_H / 2),
                    (PLANE_W / 2, 0, PLANE_H / 2), (-PLANE_W / 2, 0, PLANE_H / 2)],
                   [], [(0, 1, 2, 3)])
    me.validate()
    uv = me.uv_layers.new(name="UVMap")
    for k, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[k].uv = c
    ob = bpy.data.objects.new(pname, me)
    sc.collection.objects.link(ob)
    ob.location = (0.0, PLANE_Y, 0.0)

    mat = bpy.data.materials.get(pname) or bpy.data.materials.new(pname)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (520, 0)
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.location = (330, 0)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); tr.location = (140, 120)
    em = nt.nodes.new("ShaderNodeEmission"); em.location = (140, -80)
    ti = nt.nodes.new("ShaderNodeTexImage"); ti.location = (-140, 0)
    im = bpy.data.images.load(SRC % i, check_existing=True)
    im.source = 'FILE'
    im.reload()
    ti.image = im
    ti.interpolation = 'Closest'          # pixel art: never smooth the cells
    nt.links.new(ti.outputs["Color"], em.inputs["Color"])
    nt.links.new(ti.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    for attr, val in (("blend_method", 'BLEND'), ("surface_render_method", 'BLENDED')):
        if hasattr(mat, attr):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
    me.materials.append(mat)
    planes.append(ob)

track = []
for idx, hold in TL:
    track += [idx] * hold
LAST = len(track)

for i, ob in enumerate(planes):
    ob.animation_data_clear()
    prev = None
    for fr in range(1, LAST + 1):
        vis = track[fr - 1] == i
        if fr == 1 or vis != prev:
            ob.hide_viewport = not vis
            ob.hide_render = not vis
            ob.keyframe_insert("hide_viewport", frame=fr)
            ob.keyframe_insert("hide_render", frame=fr)
        prev = vis

cam = bpy.data.objects.get("Camera") or bpy.data.objects.get("Cam")
if cam is None:
    cd = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cd)
    sc.collection.objects.link(cam)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = PLANE_W if W > H else PLANE_H   # 1:1 pixels
cam.location = (0.0, -8.0, 0.0)
cam.rotation_euler = (math.radians(90), 0, 0)
sc.camera = cam

w = sc.world or bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.93, 0.94, 0.96, 1)
bg.inputs[1].default_value = 1.0

sc.render.resolution_x, sc.render.resolution_y = W, H
sc.frame_start, sc.frame_end = 1, LAST
sc.render.fps = FPS
sc.render.filter_size = 0.02
sc.view_settings.view_transform = 'Standard'
sc.render.film_transparent = False
sc.frame_set(1)
assert [h for _, h in TL[:5]] == [h for _, h in TL[5:]], "the halves must match"
print("catherine walk: %d drawings, %d cuts, %d frames (%.2fs, %.0f steps/min)"
      % (NF, len(TL), LAST, LAST / float(FPS), 120.0 * FPS / float(LAST)))
