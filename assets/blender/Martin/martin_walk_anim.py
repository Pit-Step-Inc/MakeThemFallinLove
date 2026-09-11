# -*- coding: utf-8 -*-
"""Frame-by-frame 2D animation: Martin 'walk' (front view, one loop).

**Four poses out of nine drawings.**  walk_prep.py has the measurements; the
short version is that seven of the nine are the same pose - right foot forward,
and no further apart from one another than 10-18 of 255 over the legs, against
27-34 between the two groups - so the set contains two positions of a walk, not
nine.  Playing all nine would give one half of the cycle seven images and the
other two, which is a limp.

  drawing 2   left foot down          drawing 6   right foot down
  drawing 7   the right leg passes    drawing 8   the left leg passes

The right-hand pair was matched to the left-hand one by **mirroring**: flip a
left-forward drawing's legs and see which right-forward drawing it becomes.
2 mirrored is nearest 6, 7 mirrored is nearest 8, and 6 and 8 are also the
furthest apart of the seven, so the right half moves rather than sitting still.

**Tempo.**  Four poses is a whole cycle, two steps.  SLOW 7 and FAST 5 make 12
frames a half and 24 for the cycle - exactly 1.00s and **120 steps a minute**,
the same cadence as Catherine's walk, so the two of them walk together.  The
footfall is held longer than the pass for the same reason as hers: the weight
comes down and the body is in double support, then the swing is quick.

Both halves must keep the same pattern or it limps; the assert at the bottom
says so.  With only two poses a side the holds are long (292ms and 208ms), and
that is the source's doing, not the timing's - ten poses would fix it.
"""
import bpy, os, math, glob

SRC = r"E:/001_MAKETHEMFALLinlove素材庫/blender/develop/Martin/frames_walk/wk_%02d.png"
NF = len(glob.glob(os.path.dirname(SRC) + "/wk_*.png"))
PLANE_H = 4.40
PLANE_Y = 0.50
FPS = 24
PREFIX = "MartinWalk_"

SLOW = 7                                   # the weight coming down
FAST = 5                                   # the swing through
TL = [
    (2, SLOW), (7, FAST),                  # left foot down, the right passes
    (6, SLOW), (8, FAST),                  # right foot down, the left passes
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
assert [h for _, h in TL[:2]] == [h for _, h in TL[2:]], "the halves must match"
print("martin walk: %d drawings, %d cuts, %d frames (%.2fs, %.0f steps/min)"
      % (NF, len(TL), LAST, LAST / float(FPS), 120.0 * FPS / float(LAST)))
