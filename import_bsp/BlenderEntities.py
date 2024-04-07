import bpy
from math import degrees
from mathutils import Vector


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

            if not obj.data.name.startswith("*"):
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
