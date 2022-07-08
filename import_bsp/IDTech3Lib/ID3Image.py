# -*- coding: UTF-8 -*-

import struct

# move file extension from first array to second one
# when the format is supported
unsupported_extensions = [".bmp", ".webp", ".ktx", ".crn", ".ftx"]
extensions = [".tga", ".png", ".dds", ".jpg", ".jpeg"]


def byte_to_float(byte):
    return byte / 255.0


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
                pixels.append(byte_to_float(self.data[p*4]))
                pixels.append(byte_to_float(self.data[p*4+1]))
                pixels.append(byte_to_float(self.data[p*4+2]))
                pixels.append(byte_to_float(self.data[p*4+3]))
        else:
            for p in range(self.width * self.height):
                pixels.append(byte_to_float(self.data[p*3]))
                pixels.append(byte_to_float(self.data[p*3+1]))
                pixels.append(byte_to_float(self.data[p*3+2]))
                pixels.append(1.0)
        return pixels


def loadFtx_from_bytearray(name, byte_array):
    image = ID3Image()
    width, height, has_alpha = struct.unpack("<iii", byte_array[:12])
    pos = 12
    image.name = name
    image.width = width
    image.height = height
    image.num_components = 3 if has_alpha == 0 else 4

    pixels = [0.0 for i in range(width*height*4)]
    for row in range(height):
        for column in range(width):
            r, g, b, a = struct.unpack("<BBBB", byte_array[pos:pos+4])
            pos += 4
            inv_row = height-row-1
            position = ((inv_row*width) + column)*4
            pixels[position + 0] = r
            pixels[position + 1] = g
            pixels[position + 2] = b
            pixels[position + 3] = a

    image.data = pixels
    return image


# based on https://github.com/scardine/image_size
def get_image_dimensions_from_bytearray(byte_array):
    """
    Return (width, height) for a given img file bytearray - no external
    dependencies except the struct module from core
    """
    size = len(byte_array)

    height = -1
    width = -1
    data = byte_array[:24]
    if (size >= 10) and data[:6] in (b'GIF87a', b'GIF89a'):
        # GIFs
        w, h = struct.unpack("<HH", data[6:10])
        width = int(w)
        height = int(h)
    elif ((size >= 24) and data.startswith(b'\211PNG\r\n\032\n')
          and (data[12:16] == b'IHDR')):
        # PNGs
        w, h = struct.unpack(">LL", data[16:24])
        width = int(w)
        height = int(h)
    elif (size >= 16) and data.startswith(b'\211PNG\r\n\032\n'):
        # older PNGs
        w, h = struct.unpack(">LL", data[8:16])
        width = int(w)
        height = int(h)
    elif (size >= 2) and data.startswith(b'\377\330'):
        # JPEGs
        msg = " raised while trying to decode as JPEG."
        b = byte_array[2]
        pos = 2
        try:
            while (b and b != 0xDA):
                while (b != 0xFF):
                    pos += 1
                    b = byte_array[pos]
                while (b == 0xFF):
                    pos += 1
                    b = byte_array[pos]
                if (b >= 0xC0 and b <= 0xC3):
                    h, w = struct.unpack(">HH", byte_array[pos+4:pos+8])
                    break
                else:
                    struct_size = int(
                        struct.unpack(">H", byte_array[pos+1:pos+3])[0])
                    pos += struct_size
                pos += 1
                b = byte_array[pos]
            width = int(w)
            height = int(h)
        except struct.error:
            raise Exception("StructError" + msg)
        except ValueError:
            raise Exception("ValueError" + msg)
        except Exception as e:
            raise Exception(e.__class__.__name__ + msg)
    elif (size >= 18) and byte_array.endswith(b'TRUEVISION-XFILE.\0'):
        # TGAs
        w, h = struct.unpack("<hh", data[12:16])
        width = int(w)
        height = int(h)
    else:
        raise Exception(
            "Sorry, don't know how to get information from this file."
        )

    return float(width), float(height)
