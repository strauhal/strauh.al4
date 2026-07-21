import bpy
from collections import defaultdict
from mathutils import Vector
import numpy as np


SOURCE = "/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_tripo_face.glb"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=SOURCE)
obj = next(obj for obj in bpy.context.scene.objects if obj.type == "MESH")
mesh = obj.data

parent = list(range(len(mesh.vertices)))
rank = [0] * len(parent)


def find(index):
    while parent[index] != index:
        parent[index] = parent[parent[index]]
        index = parent[index]
    return index


def union(left, right):
    left = find(left)
    right = find(right)
    if left == right:
        return
    if rank[left] < rank[right]:
        left, right = right, left
    parent[right] = left
    if rank[left] == rank[right]:
        rank[left] += 1


for edge in mesh.edges:
    union(edge.vertices[0], edge.vertices[1])

groups = defaultdict(list)
for polygon in mesh.polygons:
    groups[find(polygon.vertices[0])].append(polygon)

base_color_image = next((image for image in bpy.data.images if "basecolor" in image.name.lower()), None)
image_pixels = None
image_width = image_height = 0
if base_color_image:
    image_width, image_height = base_color_image.size
    image_pixels = np.empty(image_width * image_height * 4, dtype=np.float32)
    base_color_image.pixels.foreach_get(image_pixels)
    image_pixels = image_pixels.reshape((image_height, image_width, 4))
uv_data = mesh.uv_layers.active.data if mesh.uv_layers.active else None

records = []
for root, polygons in groups.items():
    vertex_ids = {vertex for polygon in polygons for vertex in polygon.vertices}
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for vertex_id in vertex_ids:
        coordinate = mesh.vertices[vertex_id].co
        for axis in range(3):
            mins[axis] = min(mins[axis], coordinate[axis])
            maxs[axis] = max(maxs[axis], coordinate[axis])
    color_sum = np.zeros(3, dtype=np.float64)
    color_samples = 0
    if image_pixels is not None and uv_data is not None:
        for polygon in polygons[:: max(1, len(polygons) // 160)]:
            u = sum(uv_data[loop_index].uv.x for loop_index in polygon.loop_indices) / len(polygon.loop_indices)
            v = sum(uv_data[loop_index].uv.y for loop_index in polygon.loop_indices) / len(polygon.loop_indices)
            px = min(image_width - 1, max(0, int((u % 1.0) * image_width)))
            py = min(image_height - 1, max(0, int((v % 1.0) * image_height)))
            color_sum += image_pixels[py, px, :3]
            color_samples += 1
    average_color = color_sum / max(1, color_samples)
    records.append((len(polygons), len(vertex_ids), mins, maxs, root, average_color))

records.sort(reverse=True, key=lambda record: record[0])
print("COMPONENT_COUNT", len(records))
for index, (face_count, vertex_count, mins, maxs, root, average_color) in enumerate(records[:140]):
    print(
        "COMP",
        index,
        "faces",
        face_count,
        "verts",
        vertex_count,
        "min",
        tuple(round(value, 4) for value in mins),
        "max",
        tuple(round(value, 4) for value in maxs),
        "root",
        root,
        "rgb",
        tuple(round(float(value), 3) for value in average_color),
    )
