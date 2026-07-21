import bpy
import math
from mathutils import Vector

SOURCE = "/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_tripo_face.glb"
OUTPUT = "/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_performance_rig.glb"


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def material(name, color, roughness=.55, metallic=0.0, alpha=1.0, transmission=0.0, ior=1.45):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, alpha)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["IOR"].default_value = ior
    if alpha < 1:
        m.surface_render_method = "DITHERED"
        m.use_transparency_overlap = False
    return m


def tune_scan_material(obj):
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if not bsdf:
            continue
        # The source's packed roughness and full-strength normal map produce a
        # wet, plastic highlight in a browser. Human skin keeps a soft broad
        # highlight, but not a mirror-like coat.
        for link in list(mat.node_tree.links):
            if link.to_node == bsdf and link.to_socket.name in {"Roughness", "Metallic"}:
                mat.node_tree.links.remove(link)
        bsdf.inputs["Roughness"].default_value = .63
        bsdf.inputs["Metallic"].default_value = 0.0
        bsdf.inputs["Specular IOR Level"].default_value = .28
        bsdf.inputs["Coat Weight"].default_value = 0.0
        bsdf.inputs["Subsurface Weight"].default_value = .035
        for node in mat.node_tree.nodes:
            if node.type == "NORMAL_MAP":
                node.inputs["Strength"].default_value = .22


def prepare_low_poly_wireframe(obj):
    # The source is a 342k-triangle browser scan. A ~1.2% collapse preserves the
    # likeness and facial silhouette while making individual triangular
    # connections readable at portrait scale instead of looking like scales.
    mod=obj.modifiers.new("Readable_Wireframe_Decimation","DECIMATE")
    mod.decimate_type="COLLAPSE";mod.ratio=.012;mod.use_collapse_triangulate=True
    bpy.context.view_layer.objects.active=obj;obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.clear()
    obj.data.materials.append(material("BrainGraph_Black_Wire",(.003,.003,.003),1.0))
    for p in obj.data.polygons:p.use_smooth=False
    print("WIRE_MESH",len(obj.data.vertices),len(obj.data.polygons))


def prepare_likeness_detail(obj):
    # A second shell retains enough of the original scan to recover Ernest's
    # eyelids, nose, lips, jaw and hair silhouette as conversation progresses.
    # It is still only a small fraction of the 342k-triangle source.
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new("Progressive_Likeness_Decimation","DECIMATE")
    mod.decimate_type="COLLAPSE";mod.ratio=.055;mod.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.data.materials.clear()
    obj.data.materials.append(material("Progressive_Likeness_Surface",(.72,.45,.34),.82))
    for p in obj.data.polygons:p.use_smooth=True
    print("DETAIL_MESH",len(obj.data.vertices),len(obj.data.polygons))


def neutralize_baked_lenses(obj):
    # Tripo baked the photographed refraction into opaque white geometry.
    # Repaint only those two frontal lens interiors to a matte socket tone;
    # the controllable sclera/lids are layered a few millimetres in front.
    socket=material("EyeSocket_Matte",(.43,.20,.125),.76)
    obj.data.materials.append(socket);slot=len(obj.data.materials)-1;changed=0
    for poly in obj.data.polygons:
        c=sum((obj.data.vertices[i].co for i in poly.vertices),Vector())/len(poly.vertices)
        in_lens=any(((c.x-cx)/.101)**2+((c.z-.615)/.063)**2<.94 for cx in (.118,-.118))
        if in_lens:poly.material_index=slot;changed+=1
    print("REPAINTED_BAKED_LENS_FACES",changed)


def add_shape_keys(obj):
    basis = obj.shape_key_add(name="Basis")
    keys = {}
    for name in ("JawOpen", "MouthWide", "MouthFunnel", "Smile", "CheekRaise", "BrowUp", "Blink_L", "Blink_R"):
        keys[name] = obj.shape_key_add(name=name)

    for i, base in enumerate(basis.data):
        x, y, z = base.co
        front = max(0.0, min(1.0, (-y - .10) / .23))

        # Jaw/chin: a broad falloff keeps the deformation anatomical instead
        # of pulling a narrow rubber strip around the lips.
        jaw = front * max(0.0, 1.0 - abs(x) / .27) * max(0.0, min(1.0, (.57 - z) / .16))
        if jaw:
            keys["JawOpen"].data[i].co += Vector((0, -.010 * jaw, -.060 * jaw))

        mouth = front * max(0.0, 1.0 - abs(x) / .18) * max(0.0, 1.0 - abs(z - .455) / .070)
        if mouth:
            side = 1 if x >= 0 else -1
            keys["MouthWide"].data[i].co.x += side * .024 * mouth
            keys["MouthFunnel"].data[i].co.x -= side * .025 * mouth
            keys["MouthFunnel"].data[i].co.y -= .020 * mouth
            keys["Smile"].data[i].co.x += side * .018 * mouth
            keys["Smile"].data[i].co.z += .018 * mouth * (abs(x) / .18)

        cheek = front * max(0.0, 1.0 - abs(abs(x) - .20) / .13) * max(0.0, 1.0 - abs(z - .55) / .12)
        if cheek:
            keys["CheekRaise"].data[i].co += Vector((0, -.010 * cheek, .012 * cheek))

        brow = front * max(0.0, 1.0 - abs(x) / .29) * max(0.0, 1.0 - abs(z - .69) / .075)
        if brow:
            keys["BrowUp"].data[i].co.z += .020 * brow

        # The source scan has no separate eyelid topology. These very local,
        # short-lived morphs compress only the photographed eye opening toward
        # its centre line, avoiding the floating replacement eyeballs that
        # made the previous version look artificial.
        for side,cx in (("L",.118),("R",-.118)):
            eye=front*max(0.0,1.0-abs(x-cx)/.075)*max(0.0,1.0-abs(z-.615)/.038)
            if eye:
                keys["Blink_"+side].data[i].co.z += (.615-z)*.72*eye


def add_armature(obj):
    arm_data = bpy.data.armatures.new("Ernest_Performance_Skeleton")
    arm = bpy.data.objects.new("Ernest_Performance_Rig", arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    def bone(name, head, tail, parent=None):
        b = arm_data.edit_bones.new(name)
        b.head, b.tail = head, tail
        b.parent = parent
        return b

    root = bone("Root", (0, 0, .05), (0, 0, .18))
    chest = bone("Chest", (0, 0, .16), (0, 0, .34), root)
    neck = bone("Neck", (0, 0, .31), (0, 0, .47), chest)
    head = bone("Head", (0, 0, .45), (0, 0, .72), neck)
    shoulder_l = bone("Shoulder_L", (0, 0, .28), (.37, 0, .28), chest)
    shoulder_r = bone("Shoulder_R", (0, 0, .28), (-.37, 0, .28), chest)
    jaw = bone("Jaw", (0, -.08, .49), (0, -.16, .40), head)
    bpy.ops.object.mode_set(mode="OBJECT")

    groups = {name: obj.vertex_groups.new(name=name) for name in
              ("Root", "Chest", "Neck", "Head", "Shoulder_L", "Shoulder_R", "Jaw")}
    for v in obj.data.vertices:
        x, y, z = v.co
        weights = {}
        if z >= .43:
            weights["Head"] = 1.0
            if z < .57 and y < -.12 and abs(x) < .27:
                w = min(.45, (.57-z)/.18)
                weights["Head"] -= w
                weights["Jaw"] = w
        elif z >= .30:
            p = (z - .30) / .13
            weights["Neck"] = .62 + .38*p
            weights["Chest"] = .38*(1-p)
        else:
            side = min(1.0, max(0.0, (abs(x)-.16)/.25))
            weights["Chest"] = 1.0-side*.72
            weights["Shoulder_L" if x >= 0 else "Shoulder_R"] = side*.72
        total = sum(weights.values()) or 1
        for name, weight in weights.items():
            groups[name].add([v.index], weight/total, "REPLACE")

    mod = obj.modifiers.new("Ernest_Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm
    return arm


def bind_detail_to_armature(obj, arm):
    groups = {name: obj.vertex_groups.new(name=name) for name in
              ("Root", "Chest", "Neck", "Head", "Shoulder_L", "Shoulder_R", "Jaw")}
    for v in obj.data.vertices:
        x, y, z = v.co
        weights = {}
        if z >= .43:
            weights["Head"] = 1.0
            if z < .57 and y < -.12 and abs(x) < .27:
                w = min(.45, (.57-z)/.18)
                weights["Head"] -= w
                weights["Jaw"] = w
        elif z >= .30:
            p = (z - .30) / .13
            weights["Neck"] = .62 + .38*p
            weights["Chest"] = .38*(1-p)
        else:
            side = min(1.0, max(0.0, (abs(x)-.16)/.25))
            weights["Chest"] = 1.0-side*.72
            weights["Shoulder_L" if x >= 0 else "Shoulder_R"] = side*.72
        total = sum(weights.values()) or 1
        for name, weight in weights.items():
            groups[name].add([v.index], weight/total, "REPLACE")
    mod = obj.modifiers.new("Progressive_Likeness_Armature", "ARMATURE")
    mod.object = arm
    obj.parent = arm


def mesh_disc(name, cx, zc, rx, rz, depth, mat, segments=32):
    # A gently convex frontal disc; camera-front is negative Y.
    verts = [(cx, depth-.006, zc)]
    for i in range(segments):
        a = math.tau*i/segments
        x = cx + math.cos(a)*rx
        z = zc + math.sin(a)*rz
        y = depth + .006*(math.cos(a)**2)
        verts.append((x, y, z))
    faces = []
    for i in range(segments):
        faces.append((0, 1+i, 1+((i+1)%segments)))
    me = bpy.data.meshes.new(name+"_Mesh")
    me.from_pydata(verts, [], faces)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def mesh_almond(name, cx, zc, rx, top_rise, lower_fall, depth, mat, segments=24):
    verts = [(cx, depth-.004, zc)]
    boundary = []
    # Upper lid from outer to inner, lower lid back to outer. The sine profile
    # creates tapered canthi instead of the circular stare of an ellipse.
    for i in range(segments+1):
        p=i/segments
        boundary.append((cx-rx+2*rx*p, depth, zc+top_rise*math.sin(math.pi*p)))
    for i in range(segments, -1, -1):
        p=i/segments
        boundary.append((cx-rx+2*rx*p, depth, zc-lower_fall*math.sin(math.pi*p)))
    verts.extend(boundary)
    faces=[]
    for i in range(len(boundary)):
        faces.append((0, 1+i, 1+((i+1)%len(boundary))))
    me=bpy.data.meshes.new(name+"_Mesh")
    me.from_pydata(verts, [], faces)
    ob=bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def add_curve(name, points, bevel, mat, cyclic=False):
    cu = bpy.data.curves.new(name+"_Curve", "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 1
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    spline = cu.splines.new("POLY")
    spline.points.add(len(points)-1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1)
    spline.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def eye_boundary(cx, zc, rx, rz, top=True, n=12, depth=-.365):
    pts=[]
    for i in range(n+1):
        p=i/n
        x=cx-rx+2*rx*p
        curve=math.sin(math.pi*p)
        z=zc+(rz*curve if top else -rz*.72*curve)
        pts.append((x, depth, z))
    return pts


def add_eyes_and_glasses(arm,body):
    white = material("Eye_Sclera", (.84, .82, .77), .42)
    iris = material("Iris_Warm_Brown", (.16, .075, .038), .34)
    pupil = material("Pupil", (.008, .006, .005), .28)
    catch = material("Eye_Catchlight", (1, 1, 1), .18)

    for side, cx in (("L", .118), ("R", -.118)):
        eye = mesh_almond("Eye_"+side, cx, .615, .052, .0105, .0075, -.372, white, 24)
        eye.parent = arm
        ir = mesh_disc("Iris_"+side, cx, .614, .0115, .0115, -.378, iris, 28)
        pu = mesh_disc("Pupil_"+side, cx, .614, .0045, .0045, -.384, pupil, 22)
        hi = mesh_disc("Catchlight_"+side, cx-.003, .618, .0018, .0018, -.389, catch, 12)
        for ob in (ir, pu, hi):
            ob.parent = eye

        # Blink plates sit collapsed just above/below the opening. JS expands
        # their Z scale toward the iris for a full, soft blink.
        up = mesh_almond("BlinkUpper_"+side, cx, .622, .054, .009, .007, -.392, material("BlinkSkin_"+side, (.72,.49,.40), .68), 24)
        low = mesh_almond("BlinkLower_"+side, cx, .608, .054, .007, .007, -.391, up.data.materials[0], 24)
        up.scale.z = .02
        low.scale.z = .02
        up.parent = low.parent = arm

    # The scan already has Ernest's Carlton frame silhouette. A second lens
    # pane turns milky in some WebGL transparency modes, so the clear opening
    # is intentionally empty geometry; the controllable eyes remain visible.
    rim=material("Carlton_Clear_Rim",(.72,.78,.78),.34,alpha=.70,transmission=.12,ior=1.46)
    for side,cx in (("L",.118),("R",-.118)):
        pts=[]
        for i in range(48):
            a=math.tau*i/48
            pts.append((cx+.102*math.cos(a),-.399,.615+.064*math.sin(a)))
        add_curve("CarltonRim_"+side,pts,.0054,rim,True).parent=arm
    add_curve("CarltonBridge",((.012,-.400,.625),(-.012,-.400,.625)),.0048,rim).parent=arm


def bind_mesh_to_bone(ob,arm,bone_name):
    group=ob.vertex_groups.new(name=bone_name)
    group.add(list(range(len(ob.data.vertices))),1.0,"REPLACE")
    mod=ob.modifiers.new("Performance_Armature","ARMATURE");mod.object=arm
    ob.parent=arm


def add_mouth_aperture(arm):
    # The generated scan's upper and lower lips share a sealed surface. A dark
    # aperture layered exactly on that seam supplies the topology that is
    # missing from the scan; it expands vertically only while speech is live.
    cavity_mat=material("Mouth_Interior",(.055,.012,.014),.78)
    teeth_mat=material("Teeth_Subtle",(.72,.66,.56),.62)
    cavity=mesh_almond("MouthCavity",0,.455,.064,.010,.015,-.357,cavity_mat,32)
    cavity.scale.z=.015
    bind_mesh_to_bone(cavity,arm,"Head")
    teeth=mesh_almond("TeethUpper",0,.461,.043,.0035,.002,-.362,teeth_mat,24)
    teeth.scale.z=.015
    bind_mesh_to_bone(teeth,arm,"Head")


clear_scene()
bpy.ops.import_scene.gltf(filepath=SOURCE)
meshes=[o for o in bpy.context.scene.objects if o.type=="MESH"]
body = max(meshes,key=lambda o:len(o.data.vertices))
for ob in meshes:
    if ob is not body:
        bpy.data.objects.remove(ob,do_unlink=True)
body.name = "Ernest_Scan_Body"
detail = body.copy()
detail.data = body.data.copy()
detail.name = "Ernest_Likeness_Detail"
bpy.context.collection.objects.link(detail)
prepare_likeness_detail(detail)
add_shape_keys(detail)
prepare_low_poly_wireframe(body)
add_shape_keys(body)
rig = add_armature(body)
bind_detail_to_armature(detail,rig)
add_mouth_aperture(rig)

# Curves are converted before GLB export for broad browser compatibility.
for ob in list(bpy.context.scene.objects):
    if ob.type == "CURVE":
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.convert(target="MESH")
        ob.select_set(False)

for ob in bpy.context.scene.objects:
    ob.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=OUTPUT,
    export_format="GLB",
    export_cameras=False,
    export_lights=False,
    export_materials="EXPORT",
    export_morph=True,
    export_skins=True,
    export_animations=False,
    export_yup=True,
)
print("PERFORMANCE_RIG", OUTPUT)
print("OBJECTS", [(o.name, o.type) for o in bpy.context.scene.objects])
