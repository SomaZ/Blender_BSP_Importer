# -*- coding: UTF-8 -*-

if "bpy" not in locals():
    import bpy

if "struct" not in locals():
    import struct

# move file extension from first array to second one
# when the format is supported
unsupported_extensions = [".bmp", ".webp", ".ktx", ".crn", ".ftx"]
extensions = [".tga", ".png", ".dds", ".jpg", ".jpeg"]


def byte_to_float(byte):
    return byte / 255.0


def array_of_bytes_to_floats(array):
    return (byte_to_float(byte) for byte in array)


class ID3Image():
    def __init__(self):
        self.name = ""
        self.width = 0
        self.height = 0
        self.bppc = 0
        self.num_components = 0
        self.data = []
        self.data_type = "byte"  # replace with enum

    def get_rgb(self):
        pixels = []
        for p in self.data:
            pixels.append(byte_to_float(p[0]))
            pixels.append(byte_to_float(p[1]))
            pixels.append(byte_to_float(p[2]))
        return pixels

    def get_rgba(self):
        if (self.num_components != 3) and (
            self.num_components != 4
           ):
            raise Exception("Invalid Image components")
        pixels = []
        if self.num_components == 4:
            for p in range(self.width * self.height):
                pixels.append(byte_to_float(self.data[p*3]))
                pixels.append(byte_to_float(self.data[p*3+1]))
                pixels.append(byte_to_float(self.data[p*3+2]))
                pixels.append(byte_to_float(self.data[p*3+3]))
        else:
            for p in range(self.width * self.height):
                pixels.append(byte_to_float(self.data[p*3]))
                pixels.append(byte_to_float(self.data[p*3+1]))
                pixels.append(byte_to_float(self.data[p*3+2]))
                pixels.append(1.0)
        return pixels


def loadFtx(file_path):
    path_list = file_path.split("/")
    filename = path_list[len(path_list)-1]
    image = bpy.data.images.get(filename)
    if image is not None:
        return image

    try:
        file = open(file_path, "rb")
    except Exception:
        return None

    width, height, has_alpha = struct.unpack("<iii", file.read(12))
    image = bpy.data.images.new(
        filename, width=width, height=height, alpha=has_alpha == 1)

    pixels = [0.0 for i in range(width*height*4)]
    for row in range(height):
        for column in range(width):
            r, g, b, a = struct.unpack("<BBBB", file.read(4))
            inv_row = height-row-1
            position = ((inv_row*width) + column)*4
            pixels[position + 0] = r / 255.0
            pixels[position + 1] = g / 255.0
            pixels[position + 2] = b / 255.0
            pixels[position + 3] = a / 255.0

    image.pixels = pixels
    image.pack()
    image.alpha_mode = 'CHANNEL_PACKED'
    return image


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

    image = loadFtx(file_path_without_ext + ".ftx")
    if image is None:
        print("Couldn't load texture: ", file_path)
    return image
