import bpy
import math
from mathutils import Vector

ROOT = "/Users/erneststrauhal/GitHub/strauh.al4"
BLEND_PATH = ROOT + "/assets/ernest_bust.blend"
GLB_PATH = ROOT + "/assets/ernest_bust.glb"


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        pass


def material(name, color, metallic=0.0, roughness=0.5, transmission=0.0, alpha=1.0, subsurface=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, alpha)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if 'Transmission Weight' in bsdf.inputs:
        bsdf.inputs['Transmission Weight'].default_value = transmission
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = 0.18 if transmission else 0.05
    if 'Subsurface Weight' in bsdf.inputs:
        bsdf.inputs['Subsurface Weight'].default_value = subsurface
    if 'Alpha' in bsdf.inputs:
        bsdf.inputs['Alpha'].default_value = alpha
    if alpha < 1.0:
        mat.surface_render_method = 'DITHERED'
    return mat


def smooth(obj):
    if obj.type == 'MESH':
        for p in obj.data.polygons:
            p.use_smooth = True
        tri = obj.modifiers.new('Web_Triangulate', 'TRIANGULATE')
        tri.keep_custom_normals = True


def uv_sphere(name, loc, scale, mat, seg=48, rings=32):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    smooth(obj)
    return obj


def curve_object(name, points, bevel, mat, cyclic=False, resolution=2):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = resolution
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    spl = cu.splines.new('BEZIER')
    spl.bezier_points.add(len(points) - 1)
    for bp, co in zip(spl.bezier_points, points):
        bp.co = co
        bp.handle_left_type = 'AUTO'
        bp.handle_right_type = 'AUTO'
    spl.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def build_head(mat):
    rows, cols = 72, 112
    verts, faces, grid = [], [], []
    for iy in range(rows + 1):
        lat = -math.pi / 2 + math.pi * iy / rows
        z = 0.21 + 1.30 * math.sin(lat)
        rad = max(0.0, math.cos(lat))
        if lat < 0:
            rad = rad ** 0.72
        row = []
        for ix in range(cols):
            lon = -math.pi + math.tau * ix / cols
            front = max(0.0, math.cos(lon))
            jaw = 1.0 - 0.13 * math.exp(-((z + 0.73) / 0.52) ** 2)
            temple = 1.0 - 0.025 * math.exp(-((z - 0.62) / 0.38) ** 2)
            x = 0.94 * rad * math.sin(lon) * jaw * temple
            y = -0.78 * rad * math.cos(lon)

            def bell(cx, cz, wx, wz):
                return math.exp(-2.5 * (((x - cx) / wx) ** 2 + ((z - cz) / wz) ** 2))

            if front > 0:
                # Eye sockets, brow shelf, cheekbones and chin.
                y += 0.09 * bell(-0.34, 0.38, 0.24, 0.16) * front
                y += 0.09 * bell(0.34, 0.38, 0.24, 0.16) * front
                y -= 0.055 * bell(0.0, 0.63, 0.62, 0.18) * front
                y -= 0.09 * bell(-0.43, -0.02, 0.30, 0.34) * front
                y -= 0.09 * bell(0.43, -0.02, 0.30, 0.34) * front
                # Long narrow bridge, projecting tip, philtrum and mouth mound.
                y -= 0.22 * bell(0.0, 0.11, 0.11, 0.52) * front
                y -= 0.34 * bell(0.0, -0.18, 0.20, 0.15) * front
                y -= 0.055 * bell(0.0, -0.48, 0.32, 0.18) * front
                y -= 0.055 * bell(0.0, -1.18, 0.34, 0.30) * front
            row.append(len(verts))
            verts.append((x, y, z))
        grid.append(row)

    for iy in range(rows):
        for ix in range(cols):
            nx = (ix + 1) % cols
            a, b = grid[iy][ix], grid[iy][nx]
            c, d = grid[iy + 1][ix], grid[iy + 1][nx]
            faces.append((a, c, b))
            faces.append((b, c, d))
    mesh = bpy.data.meshes.new('Ernest_Head_Mesh')
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new('Ernest_Head', mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    smooth(obj)
    return obj


def rounded_rect_points(cx, zc, width, height, y, steps=10):
    pts = []
    r = min(width, height) * 0.24
    corners = [
        (cx - width / 2 + r, zc + height / 2 - r, math.pi, math.pi / 2),
        (cx + width / 2 - r, zc + height / 2 - r, math.pi / 2, 0),
        (cx + width / 2 - r, zc - height / 2 + r, 0, -math.pi / 2),
        (cx - width / 2 + r, zc - height / 2 + r, -math.pi / 2, -math.pi),
    ]
    for ox, oz, a0, a1 in corners:
        for i in range(steps):
            a = a0 + (a1 - a0) * i / (steps - 1)
            pts.append((ox + r * math.cos(a), y, oz + r * math.sin(a)))
    return pts


def aim(obj, target=(0, 0, 0)):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


clear_scene()

skin = material('Skin', (0.55, 0.30, 0.215), roughness=0.62, subsurface=0.055)
skin_soft = material('Skin_Soft', (0.59, 0.33, 0.24), roughness=0.64, subsurface=0.045)
lip = material('Lips', (0.28, 0.085, 0.075), roughness=0.58)
hair = material('Hair', (0.010, 0.012, 0.016), roughness=0.52)
hair_hi = material('Hair_Highlight', (0.040, 0.045, 0.055), roughness=0.42)
eye_white = material('Sclera', (0.72, 0.69, 0.64), roughness=0.28)
iris = material('Iris_Brown', (0.16, 0.07, 0.025), roughness=0.20)
pupil = material('Pupil', (0.004, 0.003, 0.002), roughness=0.18)
brow_mat = material('Brows', (0.018, 0.014, 0.012), roughness=0.42)
frame_mat = material('Clear_Frames', (0.73, 0.77, 0.73), roughness=0.12, transmission=0.86, alpha=0.38)
shirt = material('Black_Shirt', (0.006, 0.008, 0.012), roughness=0.76)

head = build_head(skin)

# Ears and neck/bust.
uv_sphere('Ear_L', (-0.91, -0.01, 0.05), (0.135, 0.11, 0.285), skin_soft, 36, 24)
uv_sphere('Ear_R', (0.91, -0.01, 0.05), (0.135, 0.11, 0.285), skin_soft, 36, 24)
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.40, depth=0.78, location=(0, 0.06, -1.49))
neck = bpy.context.object
neck.name = 'Neck'
neck.scale.y = 0.80
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
neck.data.materials.append(skin)
smooth(neck)
uv_sphere('Shoulders_Shirt', (0, 0.16, -2.45), (1.72, 0.68, 0.68), shirt, 64, 32)

# Eyes seated inside the orbital depressions.
for side in (-1, 1):
    x = side * 0.34
    uv_sphere('Eye_L' if side < 0 else 'Eye_R', (x, -0.748, 0.29), (0.172, 0.072, 0.048), eye_white, 48, 28)
    uv_sphere('Iris_L' if side < 0 else 'Iris_R', (x, -0.816, 0.29), (0.041, 0.013, 0.041), iris, 40, 24)
    uv_sphere('Pupil_L' if side < 0 else 'Pupil_R', (x, -0.828, 0.29), (0.017, 0.006, 0.017), pupil, 32, 18)
    uv_sphere('Eye_Glint_L' if side < 0 else 'Eye_Glint_R', (x - 0.011, -0.836, 0.303), (0.0055, 0.003, 0.0055), eye_white, 20, 12)

# Thin three-dimensional lips; the head mesh supplies the surrounding muzzle.
uv_sphere('Upper_Lip', (0, -0.805, -0.39), (0.205, 0.038, 0.018), lip, 48, 20)
uv_sphere('Lower_Lip', (0, -0.812, -0.425), (0.198, 0.040, 0.024), lip, 48, 20)

# Continuous nose volumes refined from the three-quarter and profile references.
uv_sphere('Nose_Bridge', (0, -0.795, 0.03), (0.070, 0.105, 0.34), skin_soft, 48, 30)
uv_sphere('Nose_Tip', (0, -0.930, -0.18), (0.135, 0.115, 0.105), skin_soft, 48, 30)
uv_sphere('Nose_Alar_L', (-0.085, -0.885, -0.20), (0.060, 0.065, 0.050), skin, 36, 22)
uv_sphere('Nose_Alar_R', (0.085, -0.885, -0.20), (0.060, 0.065, 0.050), skin, 36, 22)

# Brows and restrained eyelid lines.
for side in (-1, 1):
    brow_pts = []
    lid_pts = []
    for i in range(8):
        u = i / 7
        x = side * (0.14 + 0.38 * u)
        brow_pts.append((x, -0.855, 0.455 + 0.050 * math.sin(math.pi * u) - 0.012 * u))
        lid_pts.append((x, -0.842, 0.305 + 0.028 * math.sin(math.pi * u)))
    curve_object(('Brow_L' if side < 0 else 'Brow_R'), brow_pts, 0.019, brow_mat)
    curve_object(('Lid_L' if side < 0 else 'Lid_R'), lid_pts, 0.005, brow_mat)

# Clear rounded-square acetate glasses.
curve_object('Frame_L', rounded_rect_points(-0.34, 0.30, 0.54, 0.32, -0.955), 0.009, frame_mat, cyclic=True)
curve_object('Frame_R', rounded_rect_points(0.34, 0.30, 0.54, 0.32, -0.955), 0.009, frame_mat, cyclic=True)
curve_object('Frame_Bridge', [(-0.065, -0.968, 0.31), (0, -0.988, 0.33), (0.065, -0.968, 0.31)], 0.009, frame_mat)
curve_object('Temple_L', [(-0.61, -0.94, 0.36), (-0.82, -0.61, 0.39), (-0.94, -0.10, 0.35)], 0.010, frame_mat)
curve_object('Temple_R', [(0.61, -0.94, 0.36), (0.82, -0.61, 0.39), (0.94, -0.10, 0.35)], 0.010, frame_mat)

# Asymmetric, high-volume wavy hair built from a smooth cap plus curves.
# A restrained matte under-volume prevents visible scalp gaps; swept strands
# provide the actual silhouette and direction.
uv_sphere('Hair_Base', (0, 0.04, 1.34), (1.00, 0.79, 0.46), hair, 64, 36)
# Hide the lower half of the cap inside the head; its visible silhouette remains closed.
for i in range(86):
    q = i / 85
    side = -1 if q < 0.47 else 1
    u = q / 0.47 if side < 0 else (q - 0.47) / 0.53
    end_x = side * (0.10 + 0.86 * u)
    end_z = 1.18 - 0.62 * (u ** 0.72)
    pts = []
    phase = i * 0.67
    for j in range(7):
        t = j / 6
        ease = t * t * (3 - 2 * t)
        x = (side * 0.03) * (1 - ease) + end_x * ease + math.sin(t * math.tau * 1.8 + phase) * (0.018 + 0.035 * t)
        z = 1.74 * (1 - ease) + end_z * ease + math.sin(math.pi * t) * (0.15 + 0.05 * math.sin(phase))
        y = -0.15 * (1 - ease) - 0.79 * ease - 0.020 * math.cos(t * math.tau + phase)
        pts.append((x, y, z))
    curve_object('Hair_Strand_%03d' % i, pts, 0.007 if i % 8 else 0.010, hair_hi if i % 8 == 0 else hair)

# A few falling and side curls carry the recognizable loose wave beyond the cap.
for side in (-1, 1):
    for i in range(8):
        pts = []
        for j in range(8):
            t = j / 7
            pts.append((
                side * (0.55 + 0.38 * t) + math.sin(t * 7.0 + i) * 0.045,
                -0.65 - 0.10 * math.cos(t * 5.0 + i),
                1.58 - 1.18 * t + math.sin(t * 6.0 + i * 0.6) * 0.06,
            ))
        curve_object('Side_Curl_%s_%02d' % ('L' if side < 0 else 'R', i), pts, 0.007, hair_hi if i % 3 == 0 else hair)

# Ground scene and presentation lighting for inspection; lights/camera are not exported.
bpy.ops.object.camera_add(location=(0, -8.8, 0.15))
camera = bpy.context.object
camera.name = 'Portrait_Camera'
camera.data.lens = 68
aim(camera, (0, 0, -0.15))
bpy.context.scene.camera = camera

for name, loc, energy, size, color in (
    ('Key', (-4.2, -5.0, 5.5), 680, 4.0, (1.0, 0.80, 0.68)),
    ('Fill', (4.0, -3.0, 2.0), 430, 3.5, (0.56, 0.68, 1.0)),
    ('Rim', (1.0, 2.2, 4.0), 700, 2.5, (0.72, 0.82, 1.0)),
):
    bpy.ops.object.light_add(type='AREA', location=loc)
    light_obj = bpy.context.object
    light_obj.name = name
    light_obj.data.energy = energy
    light_obj.data.shape = 'DISK'
    light_obj.data.size = size
    light_obj.data.color = color
    aim(light_obj, (0, 0, 0.15))

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = ROOT + '/assets/ernest_bust_preview.png'
scene.world.color = (0.015, 0.018, 0.030)

# Apply triangulation before export while retaining the editable modifiers in .blend.
bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    export_apply=True,
    export_yup=True,
    export_materials='EXPORT',
    export_cameras=False,
    export_lights=False,
)

# Return to the head and render an inspection image.
bpy.context.view_layer.objects.active = head
head.select_set(True)
bpy.ops.render.render(write_still=True)
print('ERNEST_BUST_COMPLETE', BLEND_PATH, GLB_PATH)
