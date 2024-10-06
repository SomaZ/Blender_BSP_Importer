from .idtech3lib.Parsing import parse
from .TAN import ImportTAN, ImportTANObject
from .SKB import ImportSKBs

def load_tiki(VFS, file_name, current_info = None):
    if current_info is None:
        current_info = {}
        current_info["path"] = ""
        current_info["texture_path"] = ""
        current_info["scale"] = 1.0
        current_info["materials"] = {}
        current_info["no_draw"] = []
        current_info["replacement"] = {}

    byte_array = VFS.get(file_name)
    if byte_array is None:
        print("Could not open file", file_name)
        return current_info
    
    is_open = 0
    for line in byte_array.decode().splitlines():
        # remove comments
        line = line.split("//")[0]
        # remove emty things
        line = line.lower().replace("\t", " ").strip(" \t\r\n")
        if len(line) == 0:
            continue
        if line.startswith("{"):
            is_open += 1
            continue
        if line.startswith("}"):
            is_open -= 1
            continue
        if is_open == 0:
            if line.startswith("$include"):
                key, value = parse(line)
                load_tiki(VFS, value, current_info)
            dict_key = line
            continue
        if dict_key == "setup":
            key, value = parse(line)
            if key == "path":
                if not value.endswith("/"):
                    value += "/"
                current_info["path"] = value
                current_info["texture_path"] = value
            elif key == "texturepath":
                if not value.endswith("/"):
                    value += "/"
                current_info["texture_path"] = value
            elif key == "scale":
                current_info["scale"] = float(value)
            elif key == "skelmodel":
                if "model" in current_info:
                    print("Some model already found, error unknown to handle properly")
                    continue
                current_info["model"] = current_info["path"] + value
            elif key == "morphfile":
                if "morphfile" in current_info:
                    print("Some morph file already found, error unknown to handle properly")
                    continue
                current_info["morph_file"] = current_info["path"] + value
            elif key == "surface":
                arguments = value.split()
                if len(arguments) < 3:
                    print("Could not parse surface assignment", line)
                    continue
                arguments = [a.lower() for a in arguments]
                if arguments[1] != "shader":
                    print("Unknown material assignment", line)
                    continue
                if arguments[2].endswith(".tga"):
                    current_info["materials"][arguments[0]] = current_info["texture_path"] + arguments[2]
                else:
                    current_info["materials"][arguments[0]] = arguments[2]
            elif key == "replacesurface":
                arguments = value.split()
                if len(arguments) < 3:
                    print("Could not parse replacesurface", line)
                    continue
                if arguments[2] in current_info["replacement"]:
                    current_info["replacement"][arguments[2]].append(arguments[1])
                else:
                    current_info["replacement"][arguments[2]] = [arguments[1]]
                current_info["no_draw"].append(arguments[0])
        elif dict_key == "animations":
            key, value = parse(line)
            if len(arguments) < 2:
                print("Could not parse animations info", line)
                continue
            if key == "idle":
                if "model" in current_info:
                    print("Some model already found, error unknown to handle properly")
                    continue
                current_info["model"] = current_info["path"] + value
        elif dict_key == "init":
            if line == "server":
                dict_key = "init_server"
        elif dict_key == "init_server":
            key, value = parse(line)
            if key == "surface" and value.endswith("+nodraw"):
                current_info["no_draw"].append(value.split()[0])

    return current_info


def ImportTIK(VFS,
              file_path,
              zoffset,
              import_tags=False,
              animations=None,
              per_object_import=False):
    
    dict = load_tiki(VFS, file_path)
    if not "model" in dict:
        print("Could not find model in .tiki file", file_path)
        return []
    
    if not dict["model"].endswith(".tan"):
        print(dict)
        print("Only .tan models are currently supported. Tried loading: ", dict["model"])
    return ImportTAN(VFS,
                     dict["model"],
                     dict["materials"],
                     import_tags,
                     animations,
                     per_object_import,
                     dict["scale"])


def ImportTIKObject(VFS,
                    file_path,
                    import_tags,
                    per_object_import=False):
    dict = load_tiki(VFS, file_path)
    if not "model" in dict:
        print("Could not find model in .tiki file", file_path)
        return []
    
    if not dict["model"].endswith(".tan"):
        if dict["model"].endswith(".skb"):
            return ImportSKBs(VFS,
                              dict)
        print(dict)
        print("Tried loading unsupported file: ", dict["model"])
    return ImportTANObject(VFS,
                           dict["model"],
                           dict["materials"],
                           import_tags,
                           per_object_import,
                           True,
                           dict["scale"])