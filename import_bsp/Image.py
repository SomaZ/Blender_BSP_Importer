#-*- coding: UTF-8 -*-

if "bpy" not in locals():
    import bpy

extensions = [ ".png", ".tga", ".jpg", ".jpeg" ]

def remove_file_extension(file_path):
    for extension in extensions:
        if file_path.endswith(extension):
            return file_path.replace(extension, "")
    return file_path

def load_file(base_path, file_path):
    file_path_without_ext = remove_file_extension(file_path)

    for extension in extensions:
        try:
            return bpy.data.images.load(base_path + "/" + file_path_without_ext + extension, check_existing=True)
        except:
            continue
    print("couldn't load texture: ", file_path)
    return None
