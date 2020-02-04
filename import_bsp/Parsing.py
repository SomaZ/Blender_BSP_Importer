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