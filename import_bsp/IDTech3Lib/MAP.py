from dataclasses import dataclass, field
from .ID3Brushes import Plane


def is_float(value):
    try:
        float(value)
        return True
    except Exception:
        return False


class Vertex:
    position = [0.0, 0.0, 0.0]
    tcs = [0.0, 0.0]

    def __init__(self, array):
        if len(array) < 5:
            raise Exception("Not enough data to parse for control point")
        self.position[0] = array[0]
        self.position[1] = array[1]
        self.position[2] = array[2]
        self.tcs[0] = array[3]
        self.tcs[1] = array[4]


@dataclass
class Map_surface:
    materials: list[str] = field(default_factory=list)
    type: str = "BRUSH"

    planes: list[Plane] = field(default_factory=list)
    uv_vecs: list[list] = field(default_factory=list)

    patch_layout: tuple = (0, 0)
    ctrl_points: list[Vertex] = field(default_factory=list)


def parse_surface_data(surface_info_lines):
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


def read_map_file(byte_array):
    lines = byte_array.decode(encoding="latin-1").splitlines()
    entities = []
    is_open = False
    nested_open = 0
    current_ent = {}
    obj_info = []
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
                current_ent["surfaces"].append(parse_surface_data(obj_info))
                obj_info = []
                continue
            # only add entities with data
            if len(current_ent) > 0:
                entities.append(current_ent)
                current_ent = {}
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
                values = splitted_line[1].replace("\"", "")
                fixed_values = [
                    float(new) for new in values.split() if is_float(new)]
                if (len(values.split()) != len(fixed_values) and
                   len(fixed_values)):
                    print("Error parsing line: " + line)
                if len(fixed_values):
                    values = fixed_values
                if len(values) == 1:
                    values = values[0]
                current_ent[splitted_line[0].replace("\"", "")] = values
            # brush or patch mesh info
            else:
                obj_info.append(line)
                continue
    return entities
