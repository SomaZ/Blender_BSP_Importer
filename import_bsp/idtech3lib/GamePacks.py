import json

TYPE_MATCHING = {"STRING": "NONE",
                 "COLOR": "COLOR_GAMMA",
                 "COLOR255": "COLOR_GAMMA",
                 "INT": "NONE",
                 "FLOAT": "NONE",
                 }


def get_gamepack(path, name):
    try:
        with open(path + name) as file:
            return json.load(file)
    except Exception():
        return {}


def save_gamepack(dict, path, name):
    try:
        with open(path + name, 'w') as file:
            json.dump(dict, file, indent=4,)
    except Exception():
        print("Failed writing gamepack")
