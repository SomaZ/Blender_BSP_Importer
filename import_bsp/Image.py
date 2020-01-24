#-*- coding: UTF-8 -*-

if "bpy" not in locals():
    import bpy

# move file extension from first array to second one
# when the format is supported
unsupported_extensions = [ ".bmp", ".webp", ".ktx", ".dds", ".crn" ]
extensions = [ ".tga", ".png", ".jpg", ".jpeg" ]

def remove_file_extension(file_path):
    for extension in extensions + unsupported_extensions:
        if file_path.lower().endswith(extension):
            return file_path[:-len(extension)]
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
