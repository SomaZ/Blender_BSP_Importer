from numpy import array, deg2rad
from .Parsing import *

def is_float(value):
    try:
        float(value)
        return True
    except Exception:
        return False

def ImportEntitiesText(entities_string):
    ent = {}
    entities = []
    n_ent = 0
    obj_dict = {}
    targets = {}

    for line_num, line in enumerate(entities_string.splitlines()):
        if l_open(line):
            ent = {}
            ent["first_line"] = line_num
        elif l_close(line):
            entities.append(ent)
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
                           "modelangles",
                           "_color")
            if key in vector_keys:
                value = value.strip(" \"\t\n\r")
                value = value.split(" ")
                # oh man.... Problem in t1_rail
                try:
                    if len(value) < 3:
                        raise Exception("Not enought values for vector input")
                    value = tuple(map(float, value))
                except Exception:
                    if is_float(value[0]):
                        value = [float(value[0]), float(value[0]), float(value[0])]
                    else:
                        value = [0.0, 0.0, 0.0]
                        print("Could not parse value for key:", key, value)
            parsing_keys = (
                "classname",
                "model",
                "modelscale",
                "angle",
                "spawnflags"
            )
            if key in parsing_keys:
                value = value.strip(" \'\"\t\n\r").replace("\\", "/")
            elif is_float(value):
                value = float(value)

            default_one_keys = (
                "modelscale",
                "scale",
                "light"
            )
            if (key in default_one_keys):
                try:
                    value = float(value)
                except Exception:
                    try:
                        value = float(value.split(" ")[0])
                    except Exception:
                        value = 1.0
                        print("Could not parse", key, value)

            if (key == "angle"):
                try:
                    value = float(value)
                except Exception:
                    try:
                        value = float(value.split(" ")[0])
                    except Exception:
                        value = 0.0
                        print("Could not parse angle:", value)

            if (key == "spawnflags"):
                try:
                    value = int(value)
                except Exception:
                    try:
                        value = int(float(value.split(" ")[0]))
                    except Exception:
                        value = 0
                        print("Could not parse spawnflags:", value)

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
        if "targetname" in ent and ent["targetname"] not in obj_dict:
            obj_dict[ent["targetname"]] = new_object
        else:
            obj_dict[name] = new_object

    return obj_dict

class ID3Object:

    def __init__(self, name="EmptyObject", mesh_name=None):
        self.name = name
        self.position = array((0.0, 0.0, 0.0))
        self.rotation = array((0.0, 0.0, 0.0))
        self.scale = array((1.0, 1.0, 1.0))
        self.mesh_name = mesh_name
        self.model2 = ""
        self.parent_object_name = ""
        self.custom_parameters = {}
        self.spawnflags = 0
        self.zoffset = 0

    @classmethod
    def from_entity_dict(self, ent_dict, name="EmptyObject", mesh_name=None):
        new_object = self(name, mesh_name)
        for key in ent_dict:
            new_object.parse_entity_def(key, ent_dict[key])
        return new_object

    def set_angle(self, angle):
        self.custom_parameters["angle"] = str(angle)
        self.rotation = array((0.0, 0.0, deg2rad(angle)))

    def set_angles(self, angles):
        self.custom_parameters["angles"] = '{} {} {}'.format(*angles)
        self.rotation = array((deg2rad(angles[2]),
                               deg2rad(angles[0]),
                               deg2rad(angles[1])))

    def set_scale(self, scale):
        self.scale = array((scale, scale, scale))

    def set_scale_vec(self, scale_vec):
        self.scale = array((scale_vec[0],
                            scale_vec[1],
                            scale_vec[2]))

    def set_origin(self, origin):
        self.position = array(origin)

    def set_spawnflags(self, spawnflags):
        self.spawnflags = int(spawnflags)

    def set_mesh_name(self, mesh_name):
        if not self.name == "worldspawn":
            self.mesh_name = str(mesh_name)

    def set_model2(self, mesh_name):
        self.model2 = str(mesh_name)

    def set_name(self, target_name):
        self.name = str(target_name)

    def set_zoffset(self, zoffset):
        self.zoffset = int(zoffset)

    def parse_entity_def(self, key, value):
        key_loopup = {
            "origin": self.set_origin,
            "angle": self.set_angle,
            "angles": self.set_angles,
            "modelscale_vec": self.set_scale_vec,
            "modelscale": self.set_scale,
            "spawnflags": self.set_spawnflags,
            "model": self.set_mesh_name,
            "model2": self.set_model2,
            "target_name": self.set_name,
            "zoffset": self.set_zoffset,
        }
        if key not in key_loopup:
            self.custom_parameters[key] = value
            return

        key_loopup[key](value)

    @staticmethod
    def get_entity_objects_from_bsp(bsp):
        lump = bsp.lumps["entities"]
        stringdata = []
        for i in lump:
            stringdata.append(i.char.decode("latin-1"))

        entities_string = "".join(stringdata)
        return ImportEntitiesText(entities_string)
