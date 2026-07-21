import bpy
import math
from mathutils import Vector, Matrix

SOURCE = "/tmp/ernest-basemesh2.VZlx8w/unpacked/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend"
OUT = "/Users/erneststrauhal/GitHub/strauh.al4/assets/official_head_preview.png"

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
if collection is None:
    raise RuntimeError("Official realistic head collection failed to load")
bpy.context.scene.collection.children.link(collection)
objects = [obj for obj in collection.all_objects if obj.type in {'MESH', 'CURVE'}]
if not objects:
    raise RuntimeError("Official realistic head collection contains no renderable objects")

# Normalize the imported Y-up asset to a 3.2-meter Z-up visual bust.
mins = Vector((1e9, 1e9, 1e9))
maxs = Vector((-1e9, -1e9, -1e9))
for obj in objects:
    for corner in obj.bound_box:
        world = obj.matrix_world @ Vector(corner)
        mins.x = min(mins.x, world.x); mins.y = min(mins.y, world.y); mins.z = min(mins.z, world.z)
        maxs.x = max(maxs.x, world.x); maxs.y = max(maxs.y, world.y); maxs.z = max(maxs.z, world.z)
center = (mins + maxs) * 0.5
height = maxs.y - mins.y
scale = 3.2 / height
root = bpy.data.objects.new('Official_Head_Root', None)
bpy.context.scene.collection.objects.link(root)
for obj in objects:
    if obj.parent is None:
        obj.parent = root
root.matrix_world = Matrix.Scale(scale, 4) @ Matrix.Rotation(math.radians(90), 4, 'X') @ Matrix.Translation(-center)
bpy.context.view_layer.update()
final_mins = Vector((1e9, 1e9, 1e9))
final_maxs = Vector((-1e9, -1e9, -1e9))
for obj in objects:
    for corner in obj.bound_box:
        world = obj.matrix_world @ Vector(corner)
        final_mins.x = min(final_mins.x, world.x); final_mins.y = min(final_mins.y, world.y); final_mins.z = min(final_mins.z, world.z)
        final_maxs.x = max(final_maxs.x, world.x); final_maxs.y = max(final_maxs.y, world.y); final_maxs.z = max(final_maxs.z, world.z)
final_center = (final_mins + final_maxs) * 0.5
span = max(final_maxs.x - final_mins.x, final_maxs.y - final_mins.y, final_maxs.z - final_mins.z)

def mat(name, color, rough=0.55):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    if 'Subsurface Weight' in b.inputs and name == 'Skin':
        b.inputs['Subsurface Weight'].default_value = 0.045
    return m

skin = mat('Skin', (0.54, 0.29, 0.20), 0.60)
sclera = mat('Sclera', (0.72, 0.70, 0.66), 0.30)
iris = mat('Iris', (0.12, 0.045, 0.015), 0.26)
for obj in objects:
    if obj.type != 'MESH':
        continue
    obj.data.materials.clear()
    low = obj.name.lower()
    obj.data.materials.append(sclera if 'sclera' in low else iris if 'iris' in low else skin)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    for mod in obj.modifiers:
        if mod.type == 'MULTIRES':
            mod.levels = min(2, mod.total_levels)
            mod.render_levels = min(2, mod.total_levels)

def aim(obj, target=(0, 0, 0)):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()

bpy.ops.object.camera_add(location=(final_center.x, final_center.y + span * 2.45, final_center.z))
camera = bpy.context.object
camera.data.lens = 70
aim(camera, final_center)
bpy.context.scene.camera = camera

for offset, power, size, color in (
    ((-1.1, -1.4, 1.3), 700, 3.5, (1.0, 0.78, 0.68)),
    ((1.1, -0.9, 0.4), 420, 3.0, (0.58, 0.70, 1.0)),
    ((0.2, 0.8, 1.0), 500, 2.5, (0.75, 0.84, 1.0)),
):
    loc = final_center + Vector(offset) * span
    bpy.ops.object.light_add(type='AREA', location=loc)
    light = bpy.context.object
    light.data.energy = power
    light.data.size = size
    light.data.color = color
    aim(light, final_center)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUT
scene.world.color = (0.012, 0.015, 0.025)
bpy.ops.render.render(write_still=True)
print('OFFICIAL_HEAD_PREVIEW_COMPLETE', tuple(round(v, 3) for v in final_mins), tuple(round(v, 3) for v in final_maxs), [(o.name, tuple(round(v, 3) for v in o.dimensions)) for o in objects])
