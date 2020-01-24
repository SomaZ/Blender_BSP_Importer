#----------------------------------------------------------------------------#
#TODO: replace all of this with c libary to get more performance out of it
#TODO: refactor image loading here and in QuakeShader
#----------------------------------------------------------------------------#

if "bpy" not in locals():
    import bpy

if "Image" in locals():
    imp.reload( Image )
else:
    from . import Image

import math

def make_equirectangular_from_sky(base_path, sky_name):
    textures = [sky_name + "_up", 
                sky_name + "_dn",
                sky_name + "_ft",
                sky_name + "_bk",
                sky_name + "_lf",
                sky_name + "_rt" ]
    cube = [None for x in range(6)]
    cube_size = [None for x in range(6)]
    
    biggest_h = 512
    biggest_w = 512
                 
    for index,tex in enumerate(textures):
        image = Image.load_file(base_path, tex)
        
        if image == None:
            cube[index] = []
            cube_size[index] = 0,0
        else:
            cube[index] = list(image.pixels[:])
            cube_size[index] = image.size
        
        if biggest_h < cube_size[index][1]:
            biggest_h = cube_size[index][1]
        if biggest_w < cube_size[index][0]:
            biggest_w = cube_size[index][0]
    
    equi_w = biggest_w*4
    equi_h = biggest_h*2
    pixels = [0.0 for x in range(equi_h * equi_w * 4)]
    
    for j in range(equi_h):
        for i in range(equi_w):
            u = 2 * i / equi_w -1
            v = 2 * j / equi_h -1
            
            theta = u * math.pi
            phi = v * math.pi/2.0
            
            x = math.cos(phi) * math.cos(theta)
            y = math.sin(phi)
            z = math.cos(phi) * math.sin(theta)
            
            #choose correct image
            if (x < 0):
                abs_x = -x
            else:
                abs_x = x
            if y < 0:
                abs_y = -y
            else:
                abs_y = y
            if z < 0:
                abs_z = -z
            else:
                abs_z = z
                
            read_img = cube[0]
            read_size = cube_size[0]
            read_x = 0
            read_y = 0
            
            #top bottom
            if abs_y >= abs_x and abs_y >= abs_z:
                if abs_y > 0.0:
                    z /= abs_y
                    x /= abs_y
                if y < 0:
                    read_img = cube[1]
                    read_size = cube_size[1]
                    z = -z
                else:
                    read_img = cube[0]
                    read_size = cube_size[0]
                read_x = int((x + 1.0) * read_size[0] / 2.0)
                read_y = int((z + 1.0) * read_size[1] / 2.0)
                
            #front back
            elif abs_x >= abs_y and abs_x >= abs_z:
                if abs_x > 0.0:
                    z /= abs_x
                    y /= abs_x
                if x < 0:
                    read_img = cube[3]
                    read_size = cube_size[3]
                    z = -z
                else:
                    read_img = cube[2]
                    read_size = cube_size[2]
                read_x = int((z + 1.0) * read_size[0] / 2.0)
                read_y = int((y + 1.0) * read_size[1] / 2.0)
            #left right
            else:
                if abs_z > 0.0:
                    y /= abs_z
                    x /= abs_z
                if z < 0:
                    read_img = cube[5]
                    read_size = cube_size[5]
                else:
                    read_img = cube[4]
                    read_size = cube_size[4]
                    x = -x
                read_x = int((x + 1.0) * read_size[0] / 2.0)
                read_y = int((y + 1.0) * read_size[1] / 2.0)
                
            if read_x > read_size[0] - 1:
                read_x = read_size[0] - 1
            if read_y > read_size[1] - 1:
                read_y = read_size[1] - 1
                
            read_id = (read_x + read_y * read_size[0]) * 4
            pixel_id = math.floor(i + (j * equi_w)) * 4
            
            if read_size[0] != 0.0 and read_size[1] != 0.0:
                pixels[pixel_id + 0] = read_img[read_id + 0]
                pixels[pixel_id + 1] = read_img[read_id + 1]
                pixels[pixel_id + 2] = read_img[read_id + 2]
                pixels[pixel_id + 3] = 1.0
    
    image = bpy.data.images.get(sky_name)
    if image == None:
        image = bpy.data.images.new(sky_name, width=equi_w, height=equi_h)
    if image.size[0] != equi_w or image.size[1] != equi_h:
        image.scale(equi_w, equi_h)
    image.pixels = pixels
    
    return image
