import bpy
import math
from mathutils import Vector

ROOT = "/Users/erneststrauhal/GitHub/strauh.al4"
BLEND = ROOT + "/assets/ernest_head_browser.blend"
GLB = ROOT + "/assets/ernest_head_browser.glb"
PREVIEW = ROOT + "/assets/ernest_head_browser_preview.png"

source_collection = bpy.data.collections["Head (Sculpting) - Realistic"]
source_objects = [o for o in source_collection.all_objects if o.type == 'MESH']
keep = set(source_objects)
for obj in bpy.data.objects:
    obj.hide_render = obj not in keep
    obj.hide_set(obj not in keep)

head = bpy.data.objects["GEO-head_sculpting_realistic"]
head.name = "Ernest_Head_Sculpt"
sclera_objects = [o for o in source_objects if 'sclera' in o.name.lower()]
iris_objects = [o for o in source_objects if 'iris' in o.name.lower()]

eye_guides=[]
for sclera_obj in sclera_objects:
    corners=[sclera_obj.matrix_world @ Vector(c) for c in sclera_obj.bound_box]
    lo=Vector((min(p.x for p in corners),min(p.y for p in corners),min(p.z for p in corners)))
    hi=Vector((max(p.x for p in corners),max(p.y for p in corners),max(p.z for p in corners)))
    eye_guides.append({'center':(lo+hi)*.5,'lo':lo,'hi':hi})
eye_line=sum(g['center'].z for g in eye_guides)/len(eye_guides)

def material(name, color, rough=.5, metallic=0, transmission=0, alpha=1, subsurface=0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*color, alpha)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metallic
    if 'Transmission Weight' in b.inputs: b.inputs['Transmission Weight'].default_value = transmission
    if 'Subsurface Weight' in b.inputs: b.inputs['Subsurface Weight'].default_value = subsurface
    if 'Alpha' in b.inputs: b.inputs['Alpha'].default_value = alpha
    return m

skin = material('Ernest_Skin', (0.47, 0.225, 0.145), .64, subsurface=.012)
sclera = material('Ernest_Sclera', (.48, .455, .425), .36)
iris = material('Ernest_Iris', (.060, .019, .007), .28)
pupil = material('Ernest_Pupil', (.003, .002, .001), .18)
catchlight = material('Ernest_Eye_Catchlight', (.92, .95, .98), .08)
hair = material('Ernest_Hair', (.004, .005, .008), .44)
hair_hi = material('Ernest_Hair_Highlight', (.018, .024, .035), .34)
brow = material('Ernest_Brows', (.008, .006, .005), .52)
frame = material('Ernest_Clear_Frames', (.86, .88, .84), .10, transmission=.94, alpha=.28)

for obj in source_objects:
    obj.data.materials.clear()
    obj.data.materials.append(sclera if obj in sclera_objects else iris if obj in iris_objects else skin)
    for p in obj.data.polygons: p.use_smooth = True
    for mod in obj.modifiers:
        if mod.type == 'MULTIRES':
            mod.levels = min(1, mod.total_levels)
            mod.render_levels = min(1, mod.total_levels)

# Smooth, low-frequency likeness shaping. No image projection or photo texture is used.
mins = Vector((1e9,1e9,1e9)); maxs = Vector((-1e9,-1e9,-1e9))
for corner in head.bound_box:
    p = head.matrix_world @ Vector(corner)
    for i in range(3): mins[i]=min(mins[i],p[i]); maxs[i]=max(maxs[i],p[i])
cx=(mins.x+maxs.x)*.5; cy=(mins.y+maxs.y)*.5
width=maxs.x-mins.x; height=maxs.z-mins.z
inv=head.matrix_world.inverted()
for v in head.data.vertices:
    p=head.matrix_world @ v.co
    nx=(p.x-cx)/(width*.5); nz=(p.z-mins.z)/height
    # Ernest's slim oval face, straight lower jaw, and slightly longer mid-face.
    if nz < .22: sx=.83
    elif nz < .42: sx=.88
    elif nz < .62: sx=.935
    elif nz < .78: sx=.975
    else: sx=.99
    p.x = cx + (p.x-cx)*sx
    if p.z < eye_line: p.z -= (eye_line-p.z)*.048
    # Narrower, longer bridge and modestly projecting rounded tip.
    front = max(0.0, min(1.0, (cy-p.y)/(cy-mins.y)))
    bridge = math.exp(-((nx/.16)**2)) * math.exp(-(((nz-.57)/.19)**2)) * front
    tip = math.exp(-((nx/.22)**2)) * math.exp(-(((nz-.43)/.085)**2)) * front
    p.y -= .0045*bridge + .0075*tip
    if bridge > .12: p.x = cx + (p.x-cx)*(.96 + .04*(1-bridge))
    nose_narrow=math.exp(-((nx/.24)**2))*math.exp(-(((p.z-(eye_line-height*.22))/(height*.22))**2))*front
    if nose_narrow>.08: p.x=cx+(p.x-cx)*(1-.17*nose_narrow)
    # Open the real eyelid rims around the fitted sclera. Upper movement is
    # stronger than lower movement, producing a narrow hooded almond rather
    # than the stock mesh's pinched horizontal shelf.
    for guide in eye_guides:
        ec=guide['center']; ex=(p.x-ec.x)/.0275; dz=p.z-ec.z
        if abs(ex)<1 and abs(dz)<.016 and p.y<ec.y-.003:
            # Flatten the stock round aperture into Ernest's hooded almond.
            # The upper lid sits low over the iris; the lower lid rises more
            # gently and keeps a slight outside-upward cant.
            arch=(1-ex*ex)**1.35
            cant=.00020*ex*(-1 if ec.x<cx else 1)
            if dz>=0:
                p.z -= .00435*arch*max(0,1-dz/.016)
                p.z += cant
            else:
                p.z += .00185*arch*max(0,1+dz/.016)
                p.z += cant*.55
    v.co = inv @ p

# Carry the deliberate early-2000s polygon language into the face.  The base
# mesh is retained around the eyelids/nose, then reduced enough for readable
# triangular planes without turning the likeness into a coarse mask.
for mod in head.modifiers:
    if mod.type == 'MULTIRES':
        mod.levels = 0
        mod.render_levels = 0
face_decimate=head.modifiers.get('PS2_Facial_Planes') or head.modifiers.new('PS2_Facial_Planes','DECIMATE')
face_decimate.decimate_type='COLLAPSE'; face_decimate.ratio=.64
if hasattr(face_decimate,'use_collapse_triangulate'): face_decimate.use_collapse_triangulate=True
for poly in head.data.polygons: poly.use_smooth=False

def curve_object(name, points, bevel, mat, cyclic=False):
    cu=bpy.data.curves.new(name,'CURVE'); cu.dimensions='3D'; cu.resolution_u=2
    cu.bevel_depth=bevel; cu.bevel_resolution=2
    sp=cu.splines.new('BEZIER'); sp.bezier_points.add(len(points)-1)
    for bp,co in zip(sp.bezier_points,points):
        bp.co=co; bp.handle_left_type='AUTO'; bp.handle_right_type='AUTO'
    sp.use_cyclic_u=cyclic
    ob=bpy.data.objects.new(name,cu); bpy.context.scene.collection.objects.link(ob); ob.data.materials.append(mat)
    if mat == frame: ob.visible_shadow = False
    return ob

def rounded_rect(cx0,zc,w,h,y,steps=7):
    pts=[]; r=min(w,h)*.37
    for ox,oz,a0,a1 in ((cx0-w/2+r,zc+h/2-r,math.pi,math.pi/2),(cx0+w/2-r,zc+h/2-r,math.pi/2,0),(cx0+w/2-r,zc-h/2+r,0,-math.pi/2),(cx0-w/2+r,zc-h/2+r,-math.pi/2,-math.pi)):
        for i in range(steps):
            a=a0+(a1-a0)*i/(steps-1); pts.append((ox+r*math.cos(a),y,oz+r*math.sin(a)))
    return pts

# Clear rounded-square frames measured directly from the anatomical eye centers.
ordered_eyes=sorted(eye_guides,key=lambda g:g['center'].x)
eye_z=sum(g['center'].z for g in ordered_eyes)/2
# Sit the frames fully in front of the nose/cheek planes.  The previous depth
# intersected the decimated face, deleting the top/inner portions on render.
frame_y=mins.y-height*.014
lens_w=.057; lens_h=.044; lens_z=eye_z-.0022
for i,g in enumerate(ordered_eyes):
    curve_object('Glasses_L' if i==0 else 'Glasses_R',rounded_rect(g['center'].x,lens_z,lens_w,lens_h,frame_y),.0020,frame,True)
curve_object('Glasses_Bridge',[(ordered_eyes[0]['center'].x+lens_w*.5,frame_y,lens_z+.006),(cx,frame_y-.0008,lens_z+.008),(ordered_eyes[1]['center'].x-lens_w*.5,frame_y,lens_z+.006)],.0021,frame)
curve_object('Temple_L',[(ordered_eyes[0]['center'].x-lens_w*.5,frame_y,lens_z+.006),(cx-width*.50,frame_y+height*.018,lens_z+.009)],.0018,frame)
curve_object('Temple_R',[(ordered_eyes[1]['center'].x+lens_w*.5,frame_y,lens_z+.006),(cx+width*.50,frame_y+height*.018,lens_z+.009)],.0018,frame)

# Thick but natural brows as directional curves, avoiding a polygon/scale surface.
for side in (-1,1):
    pts=[]
    for i in range(9):
        t=i/8; x=cx+side*width*(.065+.27*t); z=eye_z+height*(.075+.016*math.sin(math.pi*t)-.010*t)
        pts.append((x,mins.y-.005,z))
    curve_object('Brow_L' if side<0 else 'Brow_R',pts,.0032,brow)

# Rebuild each eye as a shallow almond surface. This replaces the pinched stock
# lids with Ernest's narrow, slightly hooded opening while preserving a smooth face.
def almond_eye(name, ec, side):
    seg=40; verts=[(ec.x,ec.y,ec.z)]; faces=[]
    boundary=[]
    for i in range(seg+1):
        u=i/seg; x=-1+2*u
        lift=(.0007*x*side)
        z=ec.z + math.sin(math.pi*u)*.0041 + lift
        y=ec.y-.0104 - math.sin(math.pi*u)*.0006
        boundary.append(len(verts)); verts.append((ec.x+x*.0255,y,z))
    for i in range(seg,-1,-1):
        u=i/seg; x=-1+2*u
        lift=(.0007*x*side)
        z=ec.z - math.sin(math.pi*u)*.0028 + lift
        y=ec.y-.0103 - math.sin(math.pi*u)*.0005
        boundary.append(len(verts)); verts.append((ec.x+x*.0255,y,z))
    for i in range(len(boundary)):
        faces.append((0,boundary[i],boundary[(i+1)%len(boundary)]))
    mesh=bpy.data.meshes.new(name+'_Mesh'); mesh.from_pydata(verts,[],faces); mesh.update()
    ob=bpy.data.objects.new(name,mesh); bpy.context.scene.collection.objects.link(ob); ob.data.materials.append(sclera)
    return ob

for guide in eye_guides:
    ec=guide['center']; side=-1 if ec.x<cx else 1; side_name='L' if side<0 else 'R'
    almond_eye('EyeWhite_'+side_name,ec,side)
    # Recessed faceted discs instead of squashed UV spheres.  This removes the
    # protruding marble look while retaining the dark brown irises in the refs.
    # Anchor to the measured front of the original fitted eyeball.  Keeping
    # these surfaces only fractions of a millimeter forward lets the sculpted
    # lids occlude them instead of allowing them to sit on top of the face.
    eye_y=guide['lo'].y-.00145; iris_r=.00485; iris_z=ec.z-.00035
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=iris_r, depth=.00030,
        location=(ec.x,eye_y,iris_z), rotation=(math.pi*.5,0,0))
    eye=bpy.context.object; eye.name='Iris_'+side_name; eye.data.materials.append(iris)
    bpy.ops.mesh.primitive_cylinder_add(vertices=18, radius=iris_r*.35, depth=.00022,
        location=(ec.x,eye_y-.00022,iris_z), rotation=(math.pi*.5,0,0))
    dot=bpy.context.object; dot.name='Pupil_'+side_name; dot.data.materials.append(pupil)
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=.00055, depth=.00016,
        location=(ec.x-.00105,eye_y-.00035,iris_z+.00110), rotation=(math.pi*.5,0,0))
    glint=bpy.context.object; glint.name='Catchlight_'+side_name; glint.data.materials.append(catchlight)
    # Hooded crease: strongest above the outer half and tapered near the nose.
    crease=[]
    for i in range(10):
        u=i/9; x=-1+2*u
        crease.append((ec.x+x*.0265,ec.y-.0152,ec.z+.0105+math.sin(math.pi*u)*.0022+.0005*x*side))
    curve_object('Lid_Crease_'+side_name,crease,.00075,brow)

    # A tapered flat brow, following the slightly straighter shape in the references.
    inner_x=ec.x-side*.018; outer_x=ec.x+side*.031
    verts=[]; faces=[]
    for i in range(9):
        u=i/8; bx=inner_x+(outer_x-inner_x)*u
        bz=ec.z+.0265+math.sin(math.pi*u)*.0022-.0010*u
        thick=.0034*(1-.58*u)
        verts.extend([(bx,ec.y-.0105,bz+thick*.5),(bx,ec.y-.0105,bz-thick*.5)])
    for i in range(8): faces.append((i*2,i*2+1,i*2+3,i*2+2))
    bm=bpy.data.meshes.new('BrowMesh_'+side_name); bm.from_pydata(verts,[],faces); bm.update()
    bo=bpy.data.objects.new('BrowMesh_'+side_name,bm); bpy.context.scene.collection.objects.link(bo); bo.data.materials.append(brow)

# One connected polygon hair shell: a low hairline, off-center crown, and swept
# asymmetric volume matching the front and three-quarter photo silhouettes.
# Coarse under-cap only: enough coverage to avoid bald gaps, with deliberately
# visible planes matching the rest of the PS2-era model.  No smooth shell.
rows=7; cols=24; hv=[]; hf=[]; grid=[]
for r in range(rows+1):
    lat=(math.pi*.5)*r/rows; t=math.sin(lat); ring=[]
    for j in range(cols):
        a=math.tau*j/cols; front=max(0,-math.cos(a)); sidewave=math.sin(a*3+.55)
        part=math.exp(-((math.sin(a)/.18)**2))*front
        base=maxs.z-height*(.205-.035*front-.050*part)+height*.012*sidewave*front
        radial=math.cos(lat)
        x=cx-width*.070*t+width*.485*radial*math.sin(a)*(1+.08*sidewave*(1-t))
        y=cy+(maxs.y-mins.y)*.51*radial*math.cos(a)
        z=base*(1-t)+(maxs.z+height*.085)*t+height*.045*math.sin(a*3+lat*2.1)*(1-t)*radial
        ring.append(len(hv)); hv.append((x,y,z))
    grid.append(ring)
for r in range(rows):
    for j in range(cols):
        n=(j+1)%cols; hf.append((grid[r][j],grid[r][n],grid[r+1][n],grid[r+1][j]))
hm=bpy.data.meshes.new('Hair_FacetedCap_Mesh'); hm.from_pydata(hv,[],hf); hm.update()
ho=bpy.data.objects.new('Hair_FacetedCap',hm); bpy.context.scene.collection.objects.link(ho); ho.data.materials.append(hair)
for p in hm.polygons:p.use_smooth=False

# A few broad, tapered polygon ribbons break the cap silhouette into the large
# wavy locks seen in the references.  These are sparse connected surfaces—not
# hair cards with image textures and not dense tube/scales.
def hair_ribbon(name, controls, start_width, end_width):
    verts=[]; faces=[]
    for i,(x,y,z) in enumerate(controls):
        t=i/(len(controls)-1); half=(start_width*(1-t)+end_width*t)*.5
        verts.extend([(x-half,y,z),(x+half,y,z)])
    for i in range(len(controls)-1): faces.append((i*2,i*2+1,i*2+3,i*2+2))
    mesh=bpy.data.meshes.new(name+'_Mesh'); mesh.from_pydata(verts,[],faces); mesh.update()
    ob=bpy.data.objects.new(name,mesh); bpy.context.scene.collection.objects.link(ob); ob.data.materials.append(hair)
    return ob

hair_front=mins.y+height*.032
lock_specs=(
    (-.04, .045, -.30, -.135, .070, .025),
    (.05, .075, -.16, -.155, .064, .022),
    (.12, .090, .015, -.165, .058, .019),
    (.18, .065, .19, -.140, .054, .020),
    (.20, .040, .31, -.115, .050, .021),
)
for i,(sx,sz,ex,ez,sw,ew) in enumerate(lock_specs):
    controls=[]
    for j in range(7):
        t=j/6; ease=t*t*(3-2*t)
        x=cx+width*(sx*(1-ease)+ex*ease)+width*.025*math.sin(math.pi*t+i*.7)
        z=maxs.z+height*(sz*(1-ease)+ez*ease)+height*.035*math.sin(math.pi*t)
        controls.append((x,hair_front-height*.004*math.sin(math.pi*t),z))
    hair_ribbon(f'Hair_Ribbon_{i:02d}',controls,width*sw,width*ew)

# Early-2000s character-model hair: a controlled number of large, tapered,
# thick polygon blades.  Their silhouette is inspired by Raiden-era layered
# feathering with a more dramatic spiked crown, while retaining Ernest's dark
# hair and asymmetric part.
def hair_blade(name, controls, widths, depth):
    verts=[]; faces=[]
    for i,c0 in enumerate(controls):
        c=Vector(c0)
        if i==0: tangent=Vector(controls[1])-c
        elif i==len(controls)-1: tangent=c-Vector(controls[i-1])
        else: tangent=Vector(controls[i+1])-Vector(controls[i-1])
        tangent.normalize()
        side=Vector((-tangent.z,0,tangent.x))
        if side.length<1e-5: side=Vector((1,0,0))
        side.normalize(); half=widths[i]*.5
        verts.extend([tuple(c-side*half+Vector((0,-depth*.5,0))),
                      tuple(c+side*half+Vector((0,-depth*.5,0))),
                      tuple(c+side*half+Vector((0, depth*.5,0))),
                      tuple(c-side*half+Vector((0, depth*.5,0)))])
    for i in range(len(controls)-1):
        a=i*4; b=(i+1)*4
        faces.extend([(a,a+1,b+1,b),(a+3,b+3,b+2,a+2),(a,a+3,b+3,b),(a+1,a+2,b+2,b+1)])
    faces.extend([(0,3,2,1),(len(verts)-4,len(verts)-3,len(verts)-2,len(verts)-1)])
    mesh=bpy.data.meshes.new(name+'_Mesh'); mesh.from_pydata(verts,[],faces); mesh.update()
    ob=bpy.data.objects.new(name,mesh); bpy.context.scene.collection.objects.link(ob); ob.data.materials.append(hair)
    return ob

front_y=mins.y+height*.022
blade_specs=[]
# Seven broad swept bangs, biased toward the viewer's left and ending at
# varied heights.  The strong diagonal is what keeps them from reading as a
# row of vertical paper strips.
for i in range(7):
    u=i/6; rootx=cx+width*(-.10+.34*u); tipx=cx+width*(-.42+.56*u)
    rootz=maxs.z+height*(.022+.026*math.sin(math.pi*u))
    tipz=maxs.z-height*(.12+.105*(.30+.70*math.sin(math.pi*u)))
    midx=rootx*.42+tipx*.58-width*(.030+.018*math.sin(i*.8))
    blade_specs.append(([(rootx,front_y+height*.014,rootz),(midx,front_y,rootz-height*.060),(tipx,front_y-height*.004,tipz)],
                        [width*.105,width*.082,width*.010],height*.024))
# Crown spikes fan outward instead of forming a round helmet.
for i in range(7):
    u=i/6; s=-1+2*u
    root=(cx+width*.11*s,cy,maxs.z+height*.005)
    tip=(cx+width*.30*s,cy+height*.012,maxs.z+height*(.115-.030*abs(s)))
    mid=(cx+width*.20*s,cy+height*.004,maxs.z+height*(.085+.012*math.cos(i)))
    blade_specs.append(([root,mid,tip],[width*.125,width*.086,width*.008],height*.032))
# Long cheek and nape pieces create the Raiden-like feathered side/back profile.
for side in (-1,1):
    for i in range(4):
        u=i/3
        root=(cx+side*width*(.24+.07*u),cy+height*.005,maxs.z-height*(.015+.05*u))
        tip=(cx+side*width*(.47+.055*u),cy+height*(.02+.025*u),maxs.z-height*(.28+.105*u))
        mid=(cx+side*width*(.40+.035*u),cy+height*.012,maxs.z-height*(.12+.09*u))
        blade_specs.append(([root,mid,tip],[width*.095,width*.060,width*.010],height*.022))

for i,(controls,widths,depth) in enumerate(blade_specs):
    hair_blade(f'Hair_Blade_{i:02d}',controls,widths,depth)

# Small cheek mole visible in the portrait references.
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=(cx+width*.20,mins.y-.001,mins.z+height*.405))
mole=bpy.context.object; mole.name='Cheek_Mole'; mole.scale=(.0017,.001,.0017); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); mole.data.materials.append(brow)

# Hair is a smooth sculpted mass made from overlapping lobes. There are no dense
# surface triangles or wire marks, so the skin remains uninterrupted and natural.
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=36, location=(cx-width*.025,cy+.006,maxs.z-height*.09))
cap=bpy.context.object; cap.name='Hair_UnderMass'; cap.scale=(width*.51,(maxs.y-mins.y)*.50,height*.20)
bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); cap.data.materials.append(hair)
for p in cap.data.polygons:p.use_smooth=True

def hair_lobe(name, x, y, z, sx, sy, sz, angle=0, highlight=False):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=24, location=(x,y,z), rotation=(0,angle,0))
    ob=bpy.context.object; ob.name=name; ob.scale=(sx,sy,sz)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(hair_hi if highlight else hair)
    for p in ob.data.polygons:p.use_smooth=True
    return ob

for i,(ox,oz,sx,sz,ang) in enumerate(()):
    hair_lobe(f'Hair_Lobe_{i:02d}',cx+width*ox,cy-height*.035,maxs.z+height*oz,width*sx,height*.11,height*sz,ang,i in (1,4,8))

for i in range(0):
    q=i/53; side=-1 if q<.48 else 1; u=q/.48 if side<0 else (q-.48)/.52
    endx=cx+side*width*(.08+.47*u); endz=maxs.z-height*(.04+.24*u**.8)
    pts=[]; phase=i*.61
    for j in range(7):
        t=j/6; ease=t*t*(3-2*t)
        x=cx*(1-ease)+endx*ease+math.sin(t*math.tau*1.35+phase)*width*(.006+.018*t)
        y=cy-height*.04*(1-ease)+(mins.y-height*.025)*ease+math.sin(t*math.tau+phase)*height*.008
        z=(maxs.z+height*.17)*(1-ease)+endz*ease+math.sin(math.pi*t)*height*(.08+.025*math.sin(phase))
        pts.append((x,y,z))
    curve_object(f'Hair_Clump_{i:03d}',pts,.0026 if i%7 else .0035,hair_hi if i%7==0 else hair)

for side in (-1,1):
    for i in range(0):
        pts=[]
        for j in range(7):
            t=j/6
            pts.append((cx+side*width*(.32+.19*t)+math.sin(t*6+i)*width*.015, mins.y+height*(.01+.015*math.cos(t*5+i)), maxs.z-height*(.08+.48*t)+math.sin(t*5+i)*height*.022))
        curve_object(f'Side_Wave_{side}_{i}',pts,.0024,hair_hi if i==0 else hair)

# Select only the deliverable geometry for browser export.
bpy.ops.object.select_all(action='DESELECT')
deliverables=[]
for obj in bpy.context.scene.objects:
    if obj is head or obj in sclera_objects or obj.name.startswith(('Iris_','Pupil_','Catchlight_','BrowMesh_','Hair_FacetedCap','Hair_Blade_','Glasses','Temple_')):
        obj.hide_set(False); obj.hide_render=False; obj.select_set(True); deliverables.append(obj)
    else:
        obj.hide_render=True

# Portrait render from the negative-Y facial side.
center=Vector((cx,cy,mins.z+height*.54)); span=height
def aim(obj,target): obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(cx,mins.y-span*2.75,center.z))
camera=bpy.context.object; camera.data.lens=78; aim(camera,center); bpy.context.scene.camera=camera
for loc,energy,size,color in (((cx-span*.7,mins.y-span*1.1,center.z+span*.75),22,span*.9,(1,.82,.72)),((cx+span*.65,mins.y-span*.6,center.z+span*.15),14,span*.85,(.64,.73,1)),((cx, maxs.y+span*.8,center.z+span*.55),14,span*.7,(.75,.84,1))):
    bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.data.energy=energy; l.data.size=size; l.data.color=color; aim(l,center)

scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE'; scene.render.resolution_x=900; scene.render.resolution_y=900; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.filepath=PREVIEW; scene.world.color=(.012,.014,.022)
scene.view_settings.exposure = -1.35
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.object.select_all(action='DESELECT')
for obj in deliverables: obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=GLB,export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_materials='EXPORT',export_cameras=False,export_lights=False)
bpy.ops.render.render(write_still=True)
print('ERNEST_NATIVE_COMPLETE',BLEND,GLB,PREVIEW,len(deliverables))
