#-*- coding: UTF-8 -*-

if "bpy" not in locals():
    import bpy
    
if "struct" not in locals():
    import struct

# move file extension from first array to second one
# when the format is supported
unsupported_extensions = [ ".bmp", ".webp", ".ktx", ".crn", ".ftx" ]
extensions = [ ".tga", ".png", ".dds", ".jpg", ".jpeg" ]

def loadFtx(file_path):
    path_list = file_path.split("/")
    filename = path_list[len(path_list)-1]
    image = bpy.data.images.get(filename)
    if image != None:
        return image
    
    try:
        file = open(file_path, "rb")
    except:
        return None
    
    width, height, has_alpha = struct.unpack("<iii", file.read(12))
    image = bpy.data.images.new(filename, width=width, height=height, alpha=has_alpha==1)
    
    pixels = [ 0.0 for i in range(width*height*4)] 
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
            return bpy.data.images.load(file_path_without_ext + extension, check_existing=True)
        except:
            continue
    
    image = loadFtx(file_path_without_ext + ".ftx")
    if image == None:
        print("Couldn't load texture: ", file_path)
    return image