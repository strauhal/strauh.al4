import bpy


SOURCE = "/Users/erneststrauhal/Downloads/adult male portrait 3d model.glb"
OUTPUT = "/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_tripo_face.glb"
DECIMATE_RATIO = 0.18


# Start from an empty scene so cameras, lights, and Blender's default cube do
# not become part of the web asset.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.gltf(filepath=SOURCE)

meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if not meshes:
    raise RuntimeError("The downloaded GLB did not contain a mesh")

for index, obj in enumerate(meshes):
    obj.name = "Ernest_Face" if index == 0 else f"Ernest_Face_{index:02d}"
    obj.data.name = obj.name + "_Mesh"

    # The Tripo export is roughly 1.9M triangles. This retains the silhouette,
    # facial features, UVs, and material while making the asset practical for
    # a full-screen browser viewer.
    modifier = obj.modifiers.new(name="Browser_Decimate", type="DECIMATE")
    modifier.decimate_type = "COLLAPSE"
    modifier.ratio = DECIMATE_RATIO
    modifier.use_collapse_triangulate = True

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier.name)

    for polygon in obj.data.polygons:
        polygon.use_smooth = True

bpy.ops.export_scene.gltf(
    filepath=OUTPUT,
    export_format="GLB",
    export_cameras=False,
    export_lights=False,
    export_materials="EXPORT",
    export_texcoords=True,
    export_normals=True,
    export_yup=True,
)

print("WEB_FACE", OUTPUT)
for obj in meshes:
    print("MESH", obj.name, len(obj.data.vertices), len(obj.data.polygons))
