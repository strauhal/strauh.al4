import bpy

SOURCE = "/Users/erneststrauhal/GitHub/strauh.al4/assets/ernest_tripo_face.glb"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=SOURCE)

for obj in bpy.context.scene.objects:
    if obj.type != "MESH":
        continue
    print("OBJECT", obj.name, "MATERIALS", len(obj.data.materials))
    for material in obj.data.materials:
        print("MATERIAL", material.name, "surface_render_method", getattr(material, "surface_render_method", "n/a"))
        if not material.use_nodes:
            continue
        for node in material.node_tree.nodes:
            print(" NODE", node.name, node.type)
            for socket in node.inputs:
                if hasattr(socket, "default_value") and not socket.is_linked:
                    value = socket.default_value
                    try:
                        value = tuple(round(float(v), 4) for v in value)
                    except (TypeError, ValueError):
                        try:
                            value = round(float(value), 4)
                        except (TypeError, ValueError):
                            pass
                    print("  INPUT", socket.name, value)
        for link in material.node_tree.links:
            print(" LINK", link.from_node.name, link.from_socket.name, "->", link.to_node.name, link.to_socket.name)
