import bpy

SOURCE="/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_performance_rig.glb"
bpy.ops.object.select_all(action="SELECT");bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=SOURCE)
print("BONES",sorted({b.name for o in bpy.context.scene.objects if o.type=="ARMATURE" for b in o.data.bones}))
for o in bpy.context.scene.objects:
    if o.type=="MESH" and o.data.shape_keys:
        print("MORPHS",o.name,[k.name for k in o.data.shape_keys.key_blocks])
print("CONTROLS",sorted(o.name for o in bpy.context.scene.objects if any(s in o.name for s in ("Blink","Iris","Pupil","Eye_"))))
