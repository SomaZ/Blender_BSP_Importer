from dataclasses import dataclass, field
from .ID3Brushes import Plane
from .ID3Object import ID3Object
from .ID3Model import ID3Model as MODEL
from .ID3Model import Map_Vertex as Vertex
from typing import List, Tuple


PROP_LEN = {
    "origin": 3,
    "angle": 1,
    "angles": 3,
    "modelscale_vec": 3,
    "modelscale": 1,
    "spawnflags": 1,
    "zoffset": 1,
    "light": 1,
    "scale": 1,
    "_color": 3,
}


def is_float(value):
    try:
        float(value)
        return True
    except Exception:
        return False


@dataclass
class Map_surface:
    materials: List[str] = field(default_factory=list)
    type: str = "BRUSH"

    planes: List[Plane] = field(default_factory=list)

    patch_layout: Tuple[int, int] = (0, 0)
    ctrl_points: List[Vertex] = field(default_factory=list)


def get_entity_brushes(entity, material_sizes, import_settings) -> MODEL:
    modelname = entity.custom_parameters.get("classname")
    if modelname is None:
        return None
    model = MODEL(modelname)
    model.add_map_entity_brushes(entity, material_sizes, import_settings)
    if model.current_index > 0:
        return model
    return None


def parse_surface_data(surface_info_lines) -> Map_surface:
    surface = Map_surface()
    if "patchdef2" in surface_info_lines:
        surface.type = "PATCH"
        is_open = False
        for line in surface_info_lines:
            if line == "(":
                is_open = True
                continue
            if line == ")":
                is_open = False
                continue
            if line == "patchdef2":
                continue

            if not is_open and not line.startswith("("):
                if line not in surface.materials:
                    surface.materials.append(line)

            if not is_open and line.startswith("("):
                patch_info = [
                    int(value) for value in line[1:-1].strip().split(" ")]
                surface.patch_layout = (patch_info[0], patch_info[1])

            if is_open and line.startswith("("):
                line = line[1:-1].strip()
                vertex_info = [
                    list(map(float, values.strip("() \t\n\r").strip(
                        ).split())) for values in line.split(") (")]
                for info in vertex_info:
                    surface.ctrl_points.append(Vertex(info))
    else:
        is_open = False
        for line in surface_info_lines:
            data = line.replace("(", "").strip().split(")")
            if len(data) != 4:
                print("Error parsing line " + line)
                continue
            for p in range(3):
                data[p] = list(map(float, data[p].strip().split(" ")))
            plane = Plane.from_quake_map_def(data)
            surface.planes.append(plane)
            # TODO: parse the rest
    return surface


def read_map_file(byte_array, import_settings) -> dict:
    lines = byte_array.decode(encoding="latin-1").splitlines()
    entities = {}
    is_open = False
    nested_open = 0
    current_ent = {}
    obj_info = []
    n_ent = 0
    for line in lines:
        line = line.strip().lower()
        # skip empty lines
        if line == "":
            continue
        # skip comments
        if line.startswith("//"):
            continue
        # close marker
        if is_open and line.startswith("}"):
            # reduce nesting layer
            if nested_open > 1:
                nested_open -= 1
                continue
            # close nested open
            if nested_open == 1:
                nested_open = 0
                if "surfaces" not in current_ent:
                    current_ent["surfaces"] = []
                if import_settings.preset != "ONLY_LIGHTS":
                    current_ent["surfaces"].append(parse_surface_data(obj_info))
                obj_info = []
                continue

            if n_ent == 0:
                name = "worldspawn"
            elif "classname" in current_ent:
                name = current_ent["classname"] + "_" + str(n_ent).zfill(4)
            else:
                name = "unknown_" + str(n_ent).zfill(4)

            # only add entities with data
            if len(current_ent) > 0:
                id3_obj = ID3Object.from_entity_dict(current_ent, name)
                if ("surfaces" in current_ent and len(current_ent["surfaces"]) > 0):
                    id3_obj.mesh_name = "*" + name
                if "targetname" in current_ent:
                    entities[current_ent["targetname"]] = id3_obj
                else:
                    entities[name] = id3_obj
                current_ent = {}
            n_ent += 1
            is_open = False
            nested_open = False
            continue
        # open marker
        if line.startswith("{"):
            if is_open:
                nested_open += 1
            is_open = True
            continue
        # parse data
        if is_open:
            splitted_line = line.split("\" \"")
            # entity key value pair
            if len(splitted_line) == 2:
                key = splitted_line[0].replace("\"", "")
                values = splitted_line[1].replace("\"", "").replace("\\\\", " ")
                fixed_values = [
                    float(new) for new in values.split() if is_float(new)]
                if (len(values.split()) != len(fixed_values) and
                   len(fixed_values)):
                    print("Error parsing line: " + line)
                if len(fixed_values):
                    values = fixed_values
                if key in PROP_LEN:
                    if PROP_LEN[key] == 1:
                        values = values[0]
                    elif len(values) == 1 and PROP_LEN[key] == 3:
                        values = (values[0],
                                  values[0],
                                  values[0])
                else:
                    if len(values) == 1:
                        values = values[0]
                current_ent[key] = values
            # brush or patch mesh info
            else:
                obj_info.append(line)
                continue
    return entities
