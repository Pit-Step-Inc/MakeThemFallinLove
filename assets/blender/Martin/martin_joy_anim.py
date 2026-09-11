# -*- coding: utf-8 -*-
"""Frame-by-frame 2D animation: Martin 'joy' (a smile that turns into a laugh).

joy_prep.py has already fitted the ten drawings onto one another on the
glasses/eye band and frozen everything but one patch on the cheek, so all ten
frames are pixel identical outside 3635 px: the picture does not boil, and the
only things that move are the mouth and the blush that comes with the laugh.

The ten drawings are ten separate takes, not a drawn cycle, so the timeline is
authored.  Sorted by how far the mouth is open they are

  9 0 8 1 2 3   shut - a smile, each drawn a little wider
  4 7           teeth showing
  6             open laugh, with blush
  5             the widest laugh, with blush

which gives: hold the smile, let it widen, open up over three frames, laugh,
rock the laugh twice, then close back down and hold.  Nothing is held longer
than 3 frames except the two ends: at 24fps a 2 frame cut is 12 drawings per
second, which is as fast as a mouth can be cut without reading as a flicker,
so the tempo is set by trimming the holds, not by raising the fps (the rest of
the Martin set is 24fps and the game reads that out of the JSON).

Drawing 5 also laughs with its eyes shut, but its glasses are redrawn with it,
so there is no seam to hide a blink patch behind - see joy_prep.py.
"""
import bpy, os, math, glob

SRC = r"E:/001_MAKETHEMFALLinlove素材庫/blender/develop/Martin/frames_joy/j_%02d.png"
NF = len(glob.glob(os.path.dirname(SRC) + "/j_*.png"))
PLANE_H = 4.40
PLANE_Y = 0.50
FPS = 24
PREFIX = "MartinJoy_"

TL = [
    (0, 5),                                     # a gentle smile
    (8, 3), (2, 3),                             # it widens
    (3, 3),
    (7, 2), (4, 2), (6, 2),                     # opening up
    (5, 3),                                     # the laugh
    (6, 2), (5, 2), (6, 2), (5, 2),             # laughing
    (4, 2), (6, 2), (5, 3),
    (7, 2), (4, 2),
    (3, 2), (1, 2), (9, 3),                     # settling
    (0, 6),                                     # back to the smile
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
print("joy: %d drawings, %d cuts, %d frames (%.2fs)"
      % (NF, len(TL), LAST, LAST / float(FPS)))
