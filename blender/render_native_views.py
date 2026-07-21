import bpy
from mathutils import Vector

OUT_DIR = "/Users/erneststrauhal/GitHub/strauh.al4/assets"
collection = bpy.data.collections["Head (Sculpting) - Realistic"]
objects = [o for o in collection.all_objects if o.type == 'MESH']
keep = set(objects)
for obj in bpy.data.objects:
    obj.hide_render = obj not in keep

mins = Vector((1e9, 1e9, 1e9)); maxs = Vector((-1e9, -1e9, -1e9))
for obj in objects:
    for corner in obj.bound_box:
        p = obj.matrix_world @ Vector(corner)
        for i in range(3):
            mins[i] = min(mins[i], p[i]); maxs[i] = max(maxs[i], p[i])
center = (mins + maxs) * .5
span = max(maxs.x-mins.x, maxs.y-mins.y, maxs.z-mins.z)

mat = bpy.data.materials.get('DiagnosticSkin') or bpy.data.materials.new('DiagnosticSkin')
mat.diffuse_color = (0.53, 0.28, 0.19, 1)
for obj in objects:
    obj.data.materials.clear(); obj.data.materials.append(mat)
    for poly in obj.data.polygons: poly.use_smooth = True
    for mod in obj.modifiers:
        if mod.type == 'MULTIRES':
            mod.levels = min(1, mod.total_levels); mod.render_levels = min(1, mod.total_levels)

def aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()

camera_data = bpy.data.cameras.new('DiagnosticCamera')
camera = bpy.data.objects.new('DiagnosticCamera', camera_data)
bpy.context.scene.collection.objects.link(camera)
camera.data.type = 'ORTHO'; camera.data.ortho_scale = span * 1.18
bpy.context.scene.camera = camera

light_data = bpy.data.lights.new('DiagnosticLight', 'AREA')
light = bpy.data.objects.new('DiagnosticLight', light_data)
bpy.context.scene.collection.objects.link(light)
light.data.energy = 1400; light.data.shape = 'DISK'; light.data.size = span * .8

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 500; scene.render.resolution_y = 500; scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.world.color = (.025, .025, .025)

views = {
    'native_pos_x': Vector((1,0,0)), 'native_neg_x': Vector((-1,0,0)),
    'native_pos_y': Vector((0,1,0)), 'native_neg_y': Vector((0,-1,0)),
    'native_pos_z': Vector((0,0,1)), 'native_neg_z': Vector((0,0,-1)),
}
for name, direction in views.items():
    camera.location = center + direction * span * 2.0; aim(camera, center)
    light.location = camera.location + Vector((span*.18, -span*.12, span*.22)); aim(light, center)
    scene.render.filepath = f"{OUT_DIR}/{name}.png"
    bpy.ops.render.render(write_still=True)
print('NATIVE_VIEWS_COMPLETE', tuple(round(v,3) for v in mins), tuple(round(v,3) for v in maxs))
