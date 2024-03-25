def l_format(line):
    return line.lower().strip(" \t\r\n").replace("\t", " ")


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
        value = value.strip("\t ").split("//")[0]
    except Exception:
        key = line
        value = ""
    return [key, value]


def guess_name(literal, file_path):
    if file_path == "":
        return ""
    split_name = file_path.replace("\\", "/")
    split_name = split_name.split("/" + literal)
    if len(split_name) > 1:
        model_name = literal + (split_name[len(split_name)-1])
    else:
        split_name = split_name[0].split("/")
        model_name = literal + split_name[len(split_name)-1]
    return model_name


def guess_model_name(file_path):
    if file_path.startswith("models/"):
        return file_path
    return guess_name("models/", file_path)


def guess_map_name(file_path):
    if file_path.startswith("maps/"):
        return file_path
    return guess_name("maps/", file_path)


def fillName(string, length):
    new_str = string[:length]
    while len(new_str) < length:
        new_str += "\0"
    return new_str
