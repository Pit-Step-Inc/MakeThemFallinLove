# -*- coding: utf-8 -*-
"""Frame-by-frame 2D animation: Catherine 'joy' (a smile that turns into a laugh).

Nine drawings; joy_prep.py froze everything outside one patch on the mouth, so
all nine frames are pixel identical outside 1911 px, and the base is the medoid
(drawing 1).  Every drawing carries the blush, so it is simply frozen in and
stays on screen for the whole clip.

Sorted by how far the mouth is open the nine are

  0 5 8 1   a closed smile, each drawn a little wider
  4 6       teeth-free open
  2 3 7     the full laugh, 7 widest

so the timeline is one swell: hold the smile, widen it, open up, laugh, rock
the laugh twice, then come back down through every stage and hold.

Drawings 4 and 5 also close the eyes - 4 half lidded, 5 shut in a contented
squint - and those are patched in too (joy_prep.py; the mask is shaped by the
difference rather than traced, so the seam lands where the drawings agree).

So the clip has two beats, not one: the laugh, and then the eyes closing.  The
squint gets six frames rather than the usual two - it is a held expression,
not a cut in a lip sync - with 4 either side of it as the lid moving.

Every cut but the peak and the two ends is held 2 frames - 12 drawings a
second at 24fps, the floor before a mouth reads as a flicker.
"""
import bpy, os, math, glob

SRC = r"E:/001_MAKETHEMFALLinlove素材庫/blender/develop/Catherine/frames_joy/cj_%02d.png"
NF = len(glob.glob(os.path.dirname(SRC) + "/cj_*.png"))
PLANE_H = 4.40
PLANE_Y = 0.50
FPS = 24
PREFIX = "CatherineJoy_"

TL = [
    (0, 4),                                     # a small closed smile
    (8, 2), (1, 2),                             # it widens
    (6, 2), (2, 2), (3, 2),                     # opening up
    (7, 3),                                     # the laugh
    (3, 2), (7, 2), (3, 2), (7, 2),             # laughing
    (2, 2), (6, 2),                             # coming down
    (4, 3),                                     # the eyes drop to half
    (5, 6),                                     # shut - the contented squint
    (4, 2),                                     # and open again
    (1, 2), (8, 2),
    (0, 4),                                     # back to the smile
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
print("catherine joy: %d drawings, %d cuts, %d frames (%.2fs)"
      % (NF, len(TL), LAST, LAST / float(FPS)))
