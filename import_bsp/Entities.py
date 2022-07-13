import bpy
import importlib
from math import radians, pow, sqrt, atan, degrees
from mathutils import Vector

from .idtech3lib.Parsing import *

if "MD3" in locals():
    importlib.reload(MD3)
else:
    from . import MD3

if "TAN" in locals():
    importlib.reload(TAN)
else:
    from . import TAN

from .idtech3lib.ID3Object import ID3Object


def ImportEntities(VFS, import_settings, bsp):
    lump = bsp.lumps["entities"]
    stringdata = []
    for i in lump:
        stringdata.append(i.char.decode("ascii"))

    entities_string = "".join(stringdata)
    return ImportEntitiesText(VFS, entities_string, import_settings, bsp)


def ImportEntitiesText(VFS,
                       entities_string,
                       import_settings,
                       bsp=None,
                       only_lights=False):
    ent = {}
    entities = []
    n_ent = 0
    mesh = None
    num_models = (int(len(bsp.lumps["models"]))
                  if bsp is not None else 0)
    map_objects = ["*"+str(n) for n in range(num_models)]
    md3_objects = []
    obj_dict = {}
    ob = None
    targets = {}

    for line in entities_string.splitlines():
        if l_open(line):
            ent = {}
        elif l_close(line):
            entities.append(ent)
            ob = None
            if "targetname" in ent:
                targets[ent["targetname"]] = entities.index(ent)
        elif line != " ":
            key, value = parse(line)
            key = key.strip(" \"\t\n\r").lower()
            value = value.replace("\"", "")
            vector_keys = ("modelscale_vec",
                           "angles",
                           "gridsize",
                           "origin",
                           "modelangles")
            if key in vector_keys:
                value = value.strip(" \"\t\n\r")
                value = value.split(" ")
                # oh man.... Problem in t1_rail
                try:
                    value[0] = float(value[0])
                    value[1] = float(value[1])
                    value[2] = float(value[2])
                except Exception:
                    value = [float(value[0]), float(value[0]), float(value[0])]
            parsing_keys = (
                "classname",
                "model",
                "modelscale",
                "angle"
            )
            if key in parsing_keys:
                value = value.strip(" \"\t\n\r").replace("\\", "/")

            # oh man.... Problem in hoth2
            if (key == "modelscale"):
                try:
                    value = float(value)
                except Exception:
                    value = float(value.split(" ")[0])

            if (key == "angle"):
                try:
                    value = float(value)
                except Exception:
                    value = float(value.split(" ")[0])

            ent[key] = value

    for n_ent, ent in enumerate(entities):

        if "classname" not in ent:
            print("Entity not parsed: " + str(ent))
            continue

        if n_ent == 0:
            new_object = ID3Object.from_entity_dict(ent, "worldspawn", "*0")
            obj_dict["worldspawn"] = new_object
            continue

        name = ent["classname"] + "_" + str(n_ent).zfill(4)
        new_object = ID3Object.from_entity_dict(ent, name)
        if "targetname" in ent:
            obj_dict[ent["targetname"]] = new_object
        else:
            obj_dict[name] = new_object

    return obj_dict

    for n_ent, ent in enumerate(entities):
        mesh_name = ""
        if "distancecull" in ent:
            clip_end = float(ent["distancecull"].replace('"', ''))

        if "gridsize" in ent and bsp is not None:
            bsp.lightgrid_size = ent["gridsize"]
            bsp.lightgrid_inverse_size = [1.0 / float(bsp.lightgrid_size[0]),
                                          1.0 / float(bsp.lightgrid_size[1]),
                                          1.0 / float(bsp.lightgrid_size[2])]

        if n_ent == 0 and not only_lights:
            me = bpy.data.meshes.get("*0")
            if me is None:
                continue
            ob = bpy.data.objects.new("Entity " + (str(n_ent).zfill(4)), me)
            obj_list.append(ob)
        else:
            has_runtime_model = False
            if "model" in ent and ent["model"].startswith("*"):
                has_runtime_model = True
                if "classname" not in ent:
                    ent["classname"] = "enviro_dynamic"

            if "classname" not in ent:
                print("Entity not parsed: " + str(ent))
                continue

            if not has_runtime_model:
                has_runtime_model = (ent["classname"].lower() in
                                     misc_model_md3s or
                                     ent["classname"].lower().startswith(
                                         "enviro"))
            if "make_static" in ent and ent["make_static"] == "1":
                has_runtime_model = False

            if ent["classname"].lower() in Dict:
                if "Model" in Dict[ent["classname"].lower()]:
                    if (Dict[ent["classname"].lower()]["Model"].lower() !=
                       "box"):
                        ent["model"] = Dict[ent["classname"].lower()
                                            ]["Model"].lower()

            if ("model" in ent and
                    has_runtime_model and not
                    only_lights):
                if "model2" in ent:
                    model_name = ent["model2"]
                else:
                    model_name = ent["model"]

                zoffset = 0
                if ent["classname"] in misc_model_md3s:
                    # FIXME: what if the model is not md3?
                    mesh_name = model_name[:-len(".md3")]
                    # FIXME: make zoffset driver based: create material hash,
                    # link zoffset prop to value in material
                    if "zoffset" in ent:
                        zoffset = int(ent["zoffset"].replace('"', '')) + 1
                        mesh_name = mesh_name+".z"+str(zoffset)
                else:
                    mesh_name = model_name

                if mesh_name in map_objects:
                    if mesh_name not in bpy.data.meshes:
                        continue
                    me = bpy.data.meshes[mesh_name]
                    ob = bpy.data.objects.new(mesh_name, me)
                else:
                    # TODO: Fix reimporting model when the zoffset is different
                    # check if model already loaded, make a copy of it,
                    # replace all the material names with new zoffset
                    if model_name.endswith(".tik"):
                        try:
                            me = TAN.ImportTIK(
                                VFS,
                                import_settings.base_paths[0] +
                                "models/" +
                                model_name,
                                zoffset)
                        except Exception:
                            try:
                                me = TAN.ImportTIK(
                                    VFS,
                                    import_settings.base_paths[0] +
                                    model_name,
                                    zoffset)
                            except Exception:
                                print("Couldn't load " +
                                      import_settings.base_paths[0] +
                                      model_name)
                    else:
                        if VFS:
                            me = MD3.ImportMD3(
                                VFS,
                                model_name,
                                zoffset)
                        else:
                            me = MD3.ImportMD3(
                                None,
                                import_settings.base_paths[0] + model_name,
                                zoffset)

                    if me is None:
                        print("Couldn't load " +
                              import_settings.base_paths[0] + model_name)
                    else:
                        me = me[0]
                        map_objects.append(mesh_name)
                        md3_objects.append(mesh_name)
                        if me is not None:
                            me.name = mesh_name

                    if me is None:
                        if (mesh is None):
                            ent_object = bpy.ops.mesh.primitive_cube_add(
                                size=16.0, location=([0, 0, 0]))
                            ent_object = bpy.context.object
                            ent_object.name = "EntityBox"
                            mesh = ent_object.data
                            mesh.name = "EntityMesh"
                            bpy.data.objects.remove(ent_object, do_unlink=True)
                        me = mesh

                    ob = bpy.data.objects.new(mesh_name, me)

                obj_list.append(ob)

            elif import_settings.preset == "RENDERING" or only_lights:
                if "classname" in ent:
                    # import lights
                    if ent["classname"].lower() == "light":
                        name = "Entity " + (str(n_ent).zfill(4))
                        intensity = 300
                        color = [1.0, 1.0, 1.0]
                        vector = [0.0, 0.0, -1.0]
                        angle = 3.141592/2.0
                        if "light" in ent:
                            intensity = float(ent["light"])
                        if "_color" in ent:
                            color_str = ent["_color"].split()
                            color = [float(color_str[0]), float(
                                color_str[1]), float(color_str[2])]

                        if "target" in ent:
                            if ent["target"] in targets:
                                if entities[targets[ent["target"]]]:
                                    target_ent = entities[
                                        targets[ent["target"]]]
                                    if ("origin") in ent and (
                                            "origin" in target_ent):
                                        vector[0] = (ent["origin"][0] -
                                                     target_ent["origin"][0])
                                        vector[1] = (ent["origin"][1] -
                                                     target_ent["origin"][1])
                                        vector[2] = (ent["origin"][2] -
                                                     target_ent["origin"][2])
                                        length = sqrt(
                                            (vector[0]*vector[0]) +
                                            (vector[1]*vector[1]) +
                                            (vector[2]*vector[2]))
                                        radius = 64.0
                                        if "radius" in ent:
                                            radius = float(ent["radius"])
                                        angle = 2*(atan(radius/length))
                            if "_sun" in ent:
                                if ent["_sun"] == "1":
                                    light = QuakeLight.add_light(
                                        name,
                                        "SUN",
                                        intensity,
                                        color,
                                        vector,
                                        radians(1.5))
                                else:
                                    light = QuakeLight.add_light(
                                        name,
                                        "SPOT",
                                        intensity,
                                        color,
                                        vector,
                                        angle)
                            else:
                                light = QuakeLight.add_light(
                                    name,
                                    "SPOT",
                                    intensity,
                                    color,
                                    vector,
                                    angle)
                        else:
                            light = QuakeLight.add_light(
                                name,
                                "POINT",
                                intensity,
                                color,
                                vector,
                                angle)

                        if "origin" in ent:
                            light.location = ent["origin"]

            elif import_settings.preset == "EDITING":
                if (mesh is None):
                    ent_object = bpy.ops.mesh.primitive_cube_add(
                        size=16.0, location=([0, 0, 0]))
                    ent_object = bpy.context.object
                    ent_object.name = "EntityBox"
                    mesh = ent_object.data
                    mesh.name = "EntityMesh"
                    bpy.data.objects.remove(ent_object, do_unlink=True)

                ob = bpy.data.objects.new(
                    name="Entity " + (str(n_ent).zfill(4)),
                    object_data=mesh.copy())
                if "classname" in ent:
                    if ent["classname"].lower() in Dict:
                        material_name = str(
                            Dict[ent["classname"].lower()]["Color"])
                        if material_name is not None:
                            mat = bpy.data.materials.get(material_name)
                            if (mat is None):
                                mat = bpy.data.materials.new(
                                    name=material_name)
                                mat.use_nodes = True
                                node = mat.node_tree.nodes["Principled BSDF"]
                                color_str = material_name.replace(
                                    "[", "").replace("]", "").split(",")
                                color = (pow(float(color_str[0]), 1.0 / 2.2),
                                         pow(float(color_str[1]), 1.0 / 2.2),
                                         pow(float(color_str[2]), 1.0 / 2.2),
                                         1.0)
                                node.inputs["Base Color"].default_value = color
                                node.inputs["Emission"].default_value = color
                            ob.data.materials.append(mat)

                    else:
                        obj_list.append(ob)

        if ob is not None:
            model2_ob = None
            if "model2" in ent:
                ob.name = "Model2 " + (str(n_ent).zfill(4))
                bpy.context.collection.objects.link(ob)
                mesh_name = ent["model"]
                if mesh_name in map_objects:
                    model2_ob = ob
                    if mesh_name in bpy.data.meshes:
                        me = bpy.data.meshes[mesh_name]
                        ob = bpy.data.objects.new(mesh_name, me)
                        obj_list.append(ob)
                    else:
                        mesh = bpy.data.meshes.get("Empty_BSP_Model")
                        if (mesh is None):
                            ent_object = bpy.ops.mesh.primitive_cube_add(
                                size=16.0, location=([0, 0, 0]))
                            ent_object = bpy.context.object
                            ent_object.name = "EntityBox"
                            mesh = ent_object.data
                            mesh.name = "Empty_BSP_Model"
                            bpy.data.objects.remove(ent_object, do_unlink=True)
                        mat = bpy.data.materials.get("Empty_BSP_Model")
                        if (mat is None):
                            mat = bpy.data.materials.new(
                                name="Empty_BSP_Model")
                            mat.use_nodes = True
                            mat.blend_method = "CLIP"
                            mat.shadow_method = "NONE"
                            node = mat.node_tree.nodes["Principled BSDF"]
                            node.inputs["Alpha"].default_value = 0.0
                        ob = bpy.data.objects.new(
                            name="something", object_data=mesh.copy())
                        ob.data.materials.append(mat)
                    ob.name = "Entity " + (str(n_ent).zfill(4))
                    bpy.context.collection.objects.link(ob)
            else:
                ob.name = "Entity " + (str(n_ent).zfill(4))
                bpy.context.collection.objects.link(ob)

            for key in ent:
                descr_dict = {}
                if ent["classname"].lower() in Dict:
                    if key.lower() in Dict[ent["classname"].lower()]["Keys"]:
                        if "Description" in Dict[ent["classname"].lower()][
                           "Keys"][key.lower()]:
                            descr_dict["description"] = Dict[
                                ent["classname"].lower()][
                                    "Keys"][
                                        key.lower()][
                                        "Description"]
                        if "Type" in Dict[ent["classname"].lower()][
                           "Keys"][key.lower()]:
                            descr_dict["subtype"] = type_matching[Dict[
                                ent["classname"].lower()][
                                "Keys"][key.lower()][
                                "Type"].upper()]

                ob[key.lower()] = ent[key]
                rna_ui[key.lower()] = descr_dict

            if "origin" in ent:
                ob.location = ent["origin"]
            if "angle" in ent:
                ob.rotation_euler = (0.0, 0.0, radians(float(ent["angle"])))
            if "angles" in ent:
                ob.rotation_euler = (radians(ent["angles"][2]), radians(
                    ent["angles"][0]), radians(ent["angles"][1]))

            if mesh_name in md3_objects:
                if "modelscale" in ent:
                    scale = (float(ent["modelscale"]), float(
                        ent["modelscale"]), float(ent["modelscale"]))
                    ob.scale = scale
                if "modelscale_vec" in ent:
                    ob.scale = ent["modelscale_vec"]
            if model2_ob is not None:
                model2_ob.parent = ob
                if "modelangles" in ent:
                    model2_ob.rotation_euler = (radians(ent["modelangles"][2]),
                                                radians(ent["modelangles"][0]),
                                                radians(ent["modelangles"][1]))
                model2_ob.hide_select = True
        ob = None

    return obj_list


def GetEntityStringFromScene():
    filtered_keys = ["_rna_ui", "q3_dynamic_props"]
    worldspawn = []
    entities = []
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and "classname" in obj:
            zero_origin = Vector([0.0, 0.0, 0.0])
            if obj.location != zero_origin:
                if (obj.location[0].is_integer() and
                   obj.location[1].is_integer() and
                   obj.location[2].is_integer()):
                    obj["origin"] = [int(obj.location[0]),
                                     int(obj.location[1]),
                                     int(obj.location[2])]
                else:
                    obj["origin"] = [obj.location[0],
                                     obj.location[1],
                                     obj.location[2]]

            if (degrees(obj.rotation_euler[0]) == 0.0 and
               degrees(obj.rotation_euler[1]) == 0.0):
                if degrees(obj.rotation_euler[2]) != 0.0:
                    obj["angle"] = degrees(obj.rotation_euler[2])
                    obj["angles"] = ""
                else:
                    obj["angle"] = ""
                    obj["angles"] = ""
            else:
                obj["angles"] = (degrees(obj.rotation_euler[2]), degrees(
                    obj.rotation_euler[0]), degrees(obj.rotation_euler[1]))
                obj["angle"] = ""

            if (obj.scale[0] != 1.0 or
               obj.scale[1] != 1.0 or
               obj.scale[2] != 1.0):
                if obj.scale[0] == obj.scale[1] == obj.scale[2]:
                    obj["modelscale"] = obj.scale[0]
                    obj["modelscale_vec"] = ""
                else:
                    obj["modelscale_vec"] = (
                        obj.scale[0], obj.scale[1], obj.scale[2])
                    obj["modelscale"] = ""
            else:
                obj["modelscale"] = ""
                obj["modelscale_vec"] = ""

            lines = []
            lines.append("{")
            for key in obj.keys():
                if key.lower() not in filtered_keys and (
                        not hasattr(obj[key], "to_dict")):
                    string = ""
                    string = str(obj[key])
                    # meeeeh nooooo, find better way!
                    if string.startswith("<bpy id property array"):
                        string = ""
                        for i in obj[key].to_list():
                            string += str(i) + " "
                    if str(key) != "" and string.strip() != "":
                        lines.append("\"" + str(key) + "\" \"" +
                                     string.strip() + "\"")
            lines.append("}")

            if obj["classname"] == "worldspawn":
                worldspawn = lines
            else:
                entities.append(lines)

    out_str = ""
    for line in worldspawn:
        out_str += line + "\n"
    for entity in entities:
        for line in entity:
            out_str += line + "\n"
    out_str += "\0"
    return out_str
