# -*- coding: UTF-8 -*-
import bpy
import os
from .idtech3lib.ID3Image import loadFtx_from_bytearray


# move file extension from first array to second one
# when the format is supported
unsupported_extensions = [".bmp", ".webp", ".ktx", ".crn", ".ftx"]
extensions = [".tga", ".png", ".dds", ".jpg", ".jpeg"]


def remove_file_extension(file_path):
    for extension in extensions + unsupported_extensions:
        if file_path.lower().endswith(extension):
            return file_path[:-len(extension)]
    return file_path


def load_file(file_path, VFS):
    file_path_without_ext = remove_file_extension(file_path)
    if VFS is not None:
        file_paths = [basepath + file_path_without_ext for basepath in VFS.basepaths]
        file_paths.append(bpy.app.tempdir + file_path_without_ext)
    else:
        file_paths = [file_path_without_ext]

    #try loading images directly
    for fp in file_paths:
        for extension in extensions:
            try:
                return bpy.data.images.load(
                    fp + extension, check_existing=True)
            except Exception:
                continue

    # try loading image from vfs instead
    for extension in extensions:
        try:
            image_bytearray = VFS.get(file_path_without_ext + extension)
            if image_bytearray is None:
                continue
            temp_filename = bpy.app.tempdir + file_path_without_ext + extension

            os.makedirs(os.path.dirname(temp_filename), exist_ok=True)

            temp_file = open(temp_filename, "wb")
            temp_file.write(image_bytearray)
            temp_file.close()

            b_image = bpy.data.images.load(
                temp_filename, check_existing=True)
            b_image.pack()
            return b_image
        except Exception:
            continue

    # try loading ftx image
    try:
        image_bytearray = VFS.get(file_path_without_ext + ".ftx")
        if image_bytearray is not None:
            image = loadFtx_from_bytearray(file_path_without_ext, image_bytearray)
            new_image = bpy.data.images.new(
                image.name,
                width=image.width,
                height=image.height,
                alpha=True)
            new_image.pixels = image.get_rgba()
            new_image.alpha_mode = 'CHANNEL_PACKED'
            new_image.pack()
            return new_image
    except Exception:
        pass

    # try loading DDS folder dds files
    try:
        image_bytearray = VFS.get("DDS/" + file_path_without_ext + ".dds")
        if image_bytearray is not None:
            temp_filename = bpy.app.tempdir + "DDS/" + file_path_without_ext + extension

            os.makedirs(os.path.dirname(temp_filename), exist_ok=True)

            temp_file = open(temp_filename, "wb")
            temp_file.write(image_bytearray)
            temp_file.close()

            b_image = bpy.data.images.load(
                temp_filename, check_existing=True)
            b_image.pack()
            return b_image
    except Exception:
        pass

    print("Couldn't load texture: ", file_path)
    return None
