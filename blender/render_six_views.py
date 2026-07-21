import bpy
from mathutils import Vector

SOURCE = "/tmp/ernest-basemesh2.VZlx8w/unpacked/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend"
OUT_DIR = "/Users/erneststrauhal/GitHub/strauh.al4/assets"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for child in list(bpy.context.scene.collection.children):
    bpy.context.scene.collection.children.unlink(child)
for collection in list(bpy.data.collections):
    bpy.data.collections.remove(collection)
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

with bpy.data.libraries.load(SOURCE, link=False, assets_only=False) as (source, target):
    target.collections = ["Head (Sculpting) - Realistic"]
collection = target.collections[0]
bpy.context.scene.collection.children.link(collection)
objects = [o for o in collection.all_objects if o.type == 'MESH']

mins = Vector((1e9, 1e9, 1e9)); maxs = Vector((-1e9, -1e9, -1e9))
for obj in objects:
    for corner in obj.bound_box:
        p = obj.matrix_world @ Vector(corner)
        for i in range(3):
            mins[i] = min(mins[i], p[i]); maxs[i] = max(maxs[i], p[i])
center = (mins + maxs) * .5
span = max(maxs - mins)

mat = bpy.data.materials.new('DiagnosticSkin')
mat.diffuse_color = (0.53, 0.28, 0.19, 1)
for obj in objects:
    obj.data.materials.clear(); obj.data.materials.append(mat)
    for poly in obj.data.polygons: poly.use_smooth = True

def aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()

bpy.ops.object.camera_add()
camera = bpy.context.object
camera.data.type = 'ORTHO'; camera.data.ortho_scale = span * 1.15
bpy.context.scene.camera = camera

bpy.ops.object.light_add(type='AREA')
light = bpy.context.object
light.data.energy = 1200; light.data.size = span * .7

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 500; scene.render.resolution_y = 500; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.world.color = (.025, .025, .025)

views = {
    'pos_x': Vector((1,0,0)), 'neg_x': Vector((-1,0,0)),
    'pos_y': Vector((0,1,0)), 'neg_y': Vector((0,-1,0)),
    'pos_z': Vector((0,0,1)), 'neg_z': Vector((0,0,-1)),
}
for name, direction in views.items():
    camera.location = center + direction * span * 2.0
    aim(camera, center)
    light.location = camera.location + Vector((-span*.2, -span*.15, span*.25))
    aim(light, center)
    scene.render.filepath = f"{OUT_DIR}/official_{name}.png"
    bpy.ops.render.render(write_still=True)

print('SIX_VIEWS_COMPLETE', tuple(mins), tuple(maxs))
