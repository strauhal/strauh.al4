import bpy
from collections import Counter

SOURCE = "/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_tripo_face.glb"
bpy.ops.import_scene.gltf(filepath=SOURCE)
print("MESHES",[(o.name,len(o.data.vertices),o.hide_render) for o in bpy.context.scene.objects if o.type=="MESH"])
obj=max((o for o in bpy.context.scene.objects if o.type=="MESH"),key=lambda o:len(o.data.vertices))
print("OBJECT",obj.matrix_world, "BOUNDS", [tuple(v) for v in obj.bound_box])
print("VERT_RANGE", tuple(min(v.co[i] for v in obj.data.vertices) for i in range(3)), tuple(max(v.co[i] for v in obj.data.vertices) for i in range(3)))
print("FIRST", [tuple(round(q,3) for q in v.co) for v in list(obj.data.vertices)[:20]])
vs=[v.co for v in obj.data.vertices if .035<abs(v.co.x)<.245 and .535<v.co.z<.695]
print("REGION_VERTS",len(vs), "SAMPLE", [tuple(round(q,3) for q in v) for v in vs[:20]])
hist=Counter()
rows=[]
for p in obj.data.polygons:
    c=sum((obj.data.vertices[i].co for i in p.vertices), obj.data.vertices[p.vertices[0]].co*0)/len(p.vertices)
    if .035 < abs(c.x) < .245 and .535 < c.z < .695:
        hist[round(c.y,2)] += 1
        rows.append((c.y,c.x,c.z,p.index))
print("HIST", sorted(hist.items()))
print("FRONTMOST", sorted(rows)[:80])
