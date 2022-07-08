# -*- coding: UTF-8 -*-

if "bpy" not in locals():
    import bpy

from .IDTech3Lib.ID3Image import loadFtx_from_bytearray

# move file extension from first array to second one
# when the format is supported
unsupported_extensions = [".bmp", ".webp", ".ktx", ".crn", ".ftx"]
extensions = [".tga", ".png", ".dds", ".jpg", ".jpeg"]


def remove_file_extension(file_path):
    for extension in extensions + unsupported_extensions:
        if file_path.lower().endswith(extension):
            return file_path[:-len(extension)]
    return file_path


def load_file(file_path):
    file_path_without_ext = remove_file_extension(file_path)

    for extension in extensions:
        try:
            return bpy.data.images.load(
                file_path_without_ext + extension, check_existing=True)
        except Exception:
            continue

    # image = loadFtx(file_path_without_ext + ".ftx")
    # if image is None:
    #     print("Couldn't load texture: ", file_path)
    # return image
    return None
