# -*- coding: utf-8 -*-
"""Frame-by-frame 2D animation: Martin 'talk01' (hands in pockets).

The body barely moves here - only the mouth and the head angle - so the holds
can be short (2-3 frames) and it reads as real speech.  Closed-mouth drawings
(0 and 5) are used as breaths between bursts.
"""
import bpy, os, math

SRC = r"E:/001_MAKETHEMFALLinlove素材庫/blender/develop/Martin/frames_talk01/t1_%02d.png"
NF = 6
PLANE_H = 4.40
PLANE_Y = 0.50
FPS = 24
PREFIX = "MartinTalk01_"

# (drawing index, frames held)
#   0 = 口を閉じる / 1 = 少し開く / 2 = 大きく開く
#   3 = 開く（顔の角度違い）/ 4 = 小さく開く / 5 = 口を閉じる（別ポーズ）
TL = [(0, 6),
      (1, 3), (2, 3), (3, 3), (2, 2), (4, 3),          # 1つ目のひとかたまり
      (5, 3),
      (2, 3), (1, 2), (3, 3), (4, 3), (2, 3),          # 2つ目
      (0, 4),
      (3, 3), (2, 2), (1, 3), (4, 3),                  # 3つ目
      (5, 6)]

sc = bpy.context.scene
if bpy.context.screen.is_animation_playing:
    bpy.ops.screen.animation_cancel(restore_frame=False)
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

for ob in list(bpy.data.objects):
    if ob.type in ('MESH', 'GREASEPENCIL'):
        bpy.data.objects.remove(ob, do_unlink=True)

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
    ti.interpolation = 'Closest'
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
cam.data.ortho_scale = PLANE_H      # 1:1 pixels: the plane exactly fills the frame
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
print("talk01: %d drawings, %d frames (%.2fs), %d cuts"
      % (NF, LAST, LAST / float(FPS), len(TL)))
