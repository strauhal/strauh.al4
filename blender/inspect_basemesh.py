import bpy
import json

path = "/tmp/ernest-basemesh2.VZlx8w/unpacked/human-base-meshes-bundle-v1.4.1/human_base_meshes_bundle.blend"
with bpy.data.libraries.load(path, assets_only=False) as (source, target):
    payload = {
        "objects": list(source.objects),
        "collections": list(source.collections),
        "meshes": list(source.meshes),
    }
with open("/tmp/ernest_basemesh_names.json", "w") as handle:
    json.dump(payload, handle, indent=2)
print("BASEMESH_INSPECT_COMPLETE")
