import bpy
import os
from mathutils import Vector


SOURCE = os.environ.get("ERNEST_INSPECT_SOURCE", "/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_tripo_face.glb")
OUT_DIR = os.environ.get("ERNEST_INSPECT_OUT", "/Users/erneststrauhal/GitHub/strauh.al4/assets/tripo_inspect")
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=SOURCE)
objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]

mins = Vector((1e9, 1e9, 1e9))
maxs = Vector((-1e9, -1e9, -1e9))
for obj in objects:
    for corner in obj.bound_box:
        point = obj.matrix_world @ Vector(corner)
        for axis in range(3):
            mins[axis] = min(mins[axis], point[axis])
            maxs[axis] = max(maxs[axis], point[axis])
center = (mins + maxs) * 0.5
span = max(maxs - mins)


def aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


bpy.ops.object.camera_add()
camera = bpy.context.object
camera.data.type = "ORTHO"
camera.data.ortho_scale = span * 1.14
bpy.context.scene.camera = camera

bpy.ops.object.light_add(type="AREA")
key = bpy.context.object
key.data.energy = 900
key.data.size = span * 0.85

bpy.ops.object.light_add(type="AREA")
fill = bpy.context.object
fill.data.energy = 450
fill.data.size = span * 0.65

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.world.color = (0.025, 0.025, 0.025)

views = {
    "pos_x": Vector((1, 0, 0)),
    "neg_x": Vector((-1, 0, 0)),
    "pos_y": Vector((0, 1, 0)),
    "neg_y": Vector((0, -1, 0)),
    "pos_z": Vector((0, 0, 1)),
    "neg_z": Vector((0, 0, -1)),
}
for name, direction in views.items():
    camera.location = center + direction * span * 2.2
    aim(camera, center)
    key.location = camera.location + Vector((-span * 0.35, -span * 0.15, span * 0.3))
    fill.location = camera.location + Vector((span * 0.45, span * 0.1, -span * 0.05))
    aim(key, center)
    aim(fill, center)
    scene.render.filepath = f"{OUT_DIR}/{name}.png"
    bpy.ops.render.render(write_still=True)

print("TRIPO_VIEWS", tuple(round(v, 4) for v in mins), tuple(round(v, 4) for v in maxs))
