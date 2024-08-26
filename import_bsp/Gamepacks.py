import bpy, bpy_extras
import os
import re
from enum import Enum


class Open_gamepack(bpy.types.Operator):
    bl_idname = "q3.open_gamepack"
    bl_label = "Open Gamepack as Blender text"
    name: bpy.props.StringProperty()

    def execute(self, context):
        if self.name == "":
            return {'CANCELLED'}
        file_path = bpy.utils.script_paths(
            subdir="addons/import_bsp/gamepacks/")[0].replace("\\", "/") + self.name
        
        bpy.ops.text.open(filepath = file_path)
        return {'FINISHED'}


class Add_new_gamepack(bpy.types.Operator):
    bl_idname = "q3.add_new_gamepack"
    bl_label = "Add new Gamepack"
    name: bpy.props.StringProperty()

    def execute(self, context):
        if self.name != "":
            file_path = bpy.utils.script_paths(
                subdir="addons/import_bsp/gamepacks/")[0].replace("\\", "/")
            with open(file_path + self.name + ".json", "w") as f:
                f.write("{\n}\n")
        return {'FINISHED'}


class Delete_gamepack(bpy.types.Operator):
    bl_idname = "q3.delete_gamepack"
    bl_label = "Delete currently selected Gamepack"
    name: bpy.props.StringProperty()

    def execute(self, context):
        if self.name != "":
            file_path = bpy.utils.script_paths(
                subdir="addons/import_bsp/gamepacks/")[0].replace("\\", "/")
            try:
                os.remove(file_path + self.name)
            except Exception:
                self.report({"ERROR"}, "Could not delete Gamepack")
                return {'CANCELLED'}
        return {'FINISHED'}


class Import_from_def(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "q3.import_def_gamepack"
    bl_label = "Import from .def"
    filename_ext = ".def"
    filter_glob: bpy.props.StringProperty(default="*.def", options={'HIDDEN'})

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="File path used for importing the .def file",
        maxlen=1024,
        default="")
    name: bpy.props.StringProperty()

    def execute(self, context):
        if self.name == "":
            return {'CANCELLED'}
        
        entities = build_ent_dict([self.filepath])

        file_path = bpy.utils.script_paths(
            subdir="addons/import_bsp/gamepacks/")[0].replace("\\", "/") + self.name + ".json"
        save_json(file_path, entities)
        return {'FINISHED'}


regex = re.compile(r"\s+", re.IGNORECASE)
def l_format(line):
    line = line.replace("\t"," ").replace("(", " ").replace(")", " ").strip(" \t\r\n").lower()
    return regex.sub(" ", line)
def l_empty(line):
    return line.strip(" \t\r\n") == ''

def get_files(dir, files, suffix):
    found_files = []
    sub_files = []
    for file in files:
        full_path = dir + file
        if os.path.isdir(full_path):
            current_files = get_files(full_path + "/", os.listdir(full_path), suffix)
            for i in current_files:
                found_files.append(i)
        elif file.lower().endswith(suffix.lower()):
            found_files.append(full_path)
    return found_files

#source_files = get_files(base_path, os.listdir(base_path), suffix)

class Key_types(Enum):
    STRING = 0
    INT = 1
    FLOAT = 2
    VECTOR = 3
    COLOR = 4
    DESCR = 5
    
class Spawn_flag(object):
    description = "NOT DOCUMENTED YET"
    bit = 1
    def __init__(flag, bit, description = ""):
        flag.description = description
        flag.bit = bit

class Key(object):
    description = "NOT DOCUMENTED YET"
    type = "STRING"
    min = 0.0
    max = 1.0
    default = 0.0
    
    def __init__(key, description, type = "STRING", default = 0.0, min = 0.0, max = 1.0):
        key.description = description
        key.type = type
        key.default = default
        key.min = min
        key.max = max

class Entity(object):
    descripton = ["NOT DOCUMENTED YET"]
    spawnflags = {}
    keys = {}
    mins = [0, 0, 0]
    maxs = [0, 0, 0]
    color = [0.0, 0.0, 0.0]
    preview_material = "/textures/colors/green.grid"
    default_model = "box"
    def __init__(ent, description, spawnflags = {}, keys = {}, preview_material = None):
        ent.description = description
        ent.spawnflags = spawnflags
        ent.keys = keys
        if preview_material != None:
            ent.preview_material = preview_material


def build_ent_dict(source_files):
    full_text = []
    for file in source_files:
        with open(file, encoding="latin-1") as lines:
            text = []
            is_open = False
            for line in lines:
                line = l_format(line)
                if line.lower().startswith("/*quaked "):
                    is_open = True
                if is_open and not l_empty(line):
                    text.append(line)
                    if line.lower().endswith("*/"):
                        is_open = False
                        full_text.append(text)
                        text = []

    n_entities = 0
    entities = {}
    for entity in full_text:
        ent = Entity("")
        ent.spawnflags = {}
        ent.keys = {}
        name = "unknown entity?_?"
        described = False
        for line in entity:
            if line.lower().startswith("/*quaked "):
                splitted = line.lower().replace("\"","").strip("\t\n\r ").split()
                skip = 0
                if len(splitted) > 1:
                    name = splitted[1]
                if len(splitted) > 4:
                    if splitted[2] == "?":
                        skip = 8
                    else:
                        ent.color = [float(splitted[2]), float(splitted[3]), float(splitted[4])]
                if len(splitted) > 7 and skip == 0:
                    if splitted[5] == "?":
                        skip = 5
                    else:
                        ent.mins = [int(splitted[5 - skip]), int(splitted[6 - skip]), int(splitted[7 - skip])]
                if len(splitted) > 10 and skip == 0:
                    if splitted[8] == "?":
                        skip = 2
                    else:
                        ent.maxs = [int(splitted[8 - skip]), int(splitted[9 - skip]), int(splitted[10 - skip])]
                if len(splitted) > 11 - skip:
                    if splitted[11 - skip].upper() != "X":
                        ent.spawnflags[splitted[11 - skip].upper()] = Spawn_flag(1, "NOT DOCUMENTED YET")
                if len(splitted) > 12 - skip:
                    if splitted[12 - skip].upper() != "X":
                        ent.spawnflags[splitted[12 - skip].upper()] = Spawn_flag(2, "NOT DOCUMENTED YET")
                if len(splitted) > 13 - skip:
                    if splitted[13 - skip].upper() != "X":
                        ent.spawnflags[splitted[13 - skip].upper()] = Spawn_flag(4, "NOT DOCUMENTED YET")
                if len(splitted) > 14 - skip:
                    if splitted[14 - skip].upper() != "X":
                        ent.spawnflags[splitted[14 - skip].upper()] = Spawn_flag(8, "NOT DOCUMENTED YET")
                if len(splitted) > 15 - skip:
                    if splitted[15 - skip].upper() != "X":
                        ent.spawnflags[splitted[15 - skip].upper()] = Spawn_flag(16, "NOT DOCUMENTED YET")
                if len(splitted) > 16 - skip:
                    if splitted[16 - skip].upper() != "X":
                        ent.spawnflags[splitted[16 - skip].upper()] = Spawn_flag(32, "NOT DOCUMENTED YET")
                if len(splitted) > 17 - skip:
                    if splitted[17 - skip].upper() != "X":
                        ent.spawnflags[splitted[17 - skip].upper()] = Spawn_flag(64, "NOT DOCUMENTED YET")
                if len(splitted) > 18 - skip:
                    if splitted[18 - skip].upper() != "X":
                        ent.spawnflags[splitted[18 - skip].upper()] = Spawn_flag(128, "NOT DOCUMENTED YET")
                if len(splitted) > 19 - skip:
                    if splitted[19 - skip].upper() != "X":
                        ent.spawnflags[splitted[19 - skip].upper()] = Spawn_flag(256, "NOT DOCUMENTED YET")
                if len(splitted) > 20 - skip:
                    if splitted[20 - skip].upper() != "X":
                        ent.spawnflags[splitted[20 - skip].upper()] = Spawn_flag(512, "NOT DOCUMENTED YET")
            elif line.lower() == "*/":
                continue
            elif line.lower().startswith("model="):
                splitted=line.split("=")
                if len(splitted) > 1:
                    ent.default_model = splitted[1].replace("\"", "")
            else:
                if described:
                    ent.descripton.append(line.replace("\t", "").strip("\t\n\r ").replace("\\", "/").replace("\"", "'"))
                else:
                    ent.descripton = [line.replace("\t", "").strip("\t\n\r ").replace("\\", "/").replace("\"", "'")]
                    described = True

                splitted = line.replace("\"","").replace("\t", "").strip("\t\n\r ").split(" ", 1)
                if len(splitted) < 2:
                    continue
                ident = splitted[0].strip(" ")
                if ident.upper() in ent.spawnflags:
                    for key in ent.spawnflags:
                        if ident.upper() == key:
                            ent.spawnflags[key].description = str(splitted[1].strip(" -"))
                elif splitted[1].startswith("-"): # Only seen this in the jedi knight def files, but I have no other way right now
                    if ident.lower() == "x":
                        continue
                    if ident.lower() in ent.keys:
                        ent.keys[ident.lower()].description += splitted[1].strip(" -").replace("/", "\\")
                    else:
                        ent.keys[ident.lower()] = Key(splitted[1].strip(" -").replace("\\", "/"))
                
        entities[name] = ent
        n_entities += 1
    return entities
    
def save_json(file_path, entities):
    f = open(file_path, "w")
    f.write("{\n")

    n_entities = len(entities)-1
    for index, entity in enumerate(entities):
        ent = entities[entity]
        f.write('\t"' + str(entity) + '":\n')
        f.write("\t{\n")
        f.write('\t\t"Color": ' + str(ent.color) + ',\n')
        f.write('\t\t"Mins": ' + str(ent.mins) + ',\n')
        f.write('\t\t"Maxs": ' + str(ent.maxs) + ',\n')
        f.write('\t\t"Model": "' + str(ent.default_model).replace("\\", "/") + '",\n')
        f.write('\t\t"Description": [\n')
        for id, line in enumerate(ent.descripton):
            f.write('\t\t\t"' + str(line) + '"')
            if id == len(ent.descripton)-1:
                f.write("\n")
            else:
                f.write(",\n")
        f.write('\t\t],\n')
        f.write('\t\t"Spawnflags":\n')
        f.write("\t\t{\n")
        n_spawnflags = len(ent.spawnflags)-1
        for index_sf, sf in enumerate(ent.spawnflags):
            if sf.lower() == "x":
                n_spawnflags -= 1
                continue
            spawnflag = ent.spawnflags[sf]
            f.write('\t\t\t"' + str(sf) + '":\n')
            f.write("\t\t\t{\n")
            f.write('\t\t\t\t"Bit": ' + str(spawnflag.bit) + ',\n')
            f.write('\t\t\t\t"Description": "' + spawnflag.description + '"\n')
            f.write("\t\t\t}")
            if index_sf == n_spawnflags:
                f.write("\n")
            else:
                f.write(",\n")
        f.write("\t\t},\n")
        
        f.write('\t\t"Keys":\n')
        f.write("\t\t{\n")       
        n_keys = len(ent.keys)-1
        for index_k, key_name in enumerate(ent.keys):
            print(key_name)
            key = ent.keys[key_name]
            f.write('\t\t\t"' + str(key_name) + '":\n')
            f.write("\t\t\t{\n")
            f.write('\t\t\t\t"Type": "' + str(key.type) + '",\n')
            f.write('\t\t\t\t"Description": "' + key.description + '"\n')
            f.write("\t\t\t}")
            if index_k == n_keys:
                f.write("\n")
            else:
                f.write(",\n")
                
        f.write("\t\t}\n")
        if index < n_entities:
            f.write("\t},\n")
        else:
            f.write("\t}\n")
    f.write("}\n")
    f.close()

    print("Number of entities: " + str(n_entities))
