def l_format(line):
    return line.lower().strip(" \t\r\n").replace("\t"," ")

def l_empty(line):
    return line.strip(" \t\r\n") == ''

def l_comment(line):
    return l_format(line).startswith('/')

def l_open(line):
    return line.startswith('{')

def l_close(line):
    return line.startswith('}')

def parse(line):
    try:
        key, value = line.split(' ', 1)
        key = key.strip("\t ")
        value = value.strip("\t ")
    except:
        key = line
        value = ""
    return [key, value]

def guess_model_name(file_path):
    split_name = file_path.replace("\\", "/")
    split_name = split_name.split("/models/")
    if len(split_name) > 1:
        model_name = "models/" + (split_name[len(split_name)-1])
    else:
        split_name = split_name[0].split("/")
        model_name = "models/" + split_name[len(split_name)-1]
    return model_name

def guess_base_path_and_mapname_from_map(file_path):
    split_name = file_path.replace("\\", "/")
    split_name = split_name.split("/maps/")
    if len(split_name) > 1:
        base_path = split_name[0] + "/"
        map_name = split_name[1]
    else:
        return None, None
        
    if map_name.endswith(".map"):
        map_name = map_name[:-len(".map")]
        
    return base_path, map_name

def fillName(string, length):
    new_str = string[:length]
    while len(new_str) < length:
        new_str += "\0"
    return new_str