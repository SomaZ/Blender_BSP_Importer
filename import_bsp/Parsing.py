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
    split_name = file_path.split("/models/")
    if len(split_name) > 1:
        model_name = "models/" + (split_name[len(split_name)-1])
    else:
        split_name = split_name[0].split("/")
        model_name = "models/" + split_name[len(split_name)-1]
    return model_name