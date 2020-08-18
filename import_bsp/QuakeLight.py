import bpy
from math import floor, ceil, pi, sin, cos, pow, atan2, sqrt, acos

if "GridIcoSphere" in locals():
    import imp
    imp.reload( GridIcoSphere )
else:
    from . import GridIcoSphere
    
if "struct" not in locals():
    import struct

import bgl
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
import os

def toSRGB(value):
    if value <= 0.0031308:
        return value * 12.92
    else:
        return 1.055*pow(value, 1/2.4) - 0.055
    
def toLinear(value):
    if value <= 0.0404482362771082:
        return value / 12.92
    else:
        return pow(((value + 0.055) / 1.055), 2.4)

def linearToSRGB(color):
    return toSRGB(color[0]), toSRGB(color[1]), toSRGB(color[2])

def SRGBToLinear(color):
    return toLinear(color[0]), toLinear(color[1]), toLinear(color[2])

def colorNormalize(color, scale, srgb = True):
    outColor = [0.0, 0.0, 0.0]
    outColor[0] = color[0] * scale
    outColor[1] = color[1] * scale
    outColor[2] = color[2] * scale
    
    color_max = max(outColor)
    
    #color normalize
    if color_max > 1.0:
        outColor[0] /= color_max
        outColor[1] /= color_max
        outColor[2] /= color_max
    
    return linearToSRGB(outColor) if srgb else outColor

def color_to_bytes(color):
    out_color = [0 for i in range(len(color))]
    for i in range(len(color)):
        out_color[i] = int(color[i] * 255) & 0xff
    return out_color

def append_color_as_bytes(array, color):
    byte_color = color_to_bytes(color)
    for i in range(len(color)):
        array.append(byte_color[i])

def add_light(name, type, intensity, color, vector, angle):
    out_color = SRGBToLinear(color)
    
    if type == "SUN":
        light = bpy.data.lights.get(name)
        if light == None:
            light = bpy.data.lights.new(name=name, type='SUN')
            light.energy = intensity 
            light.shadow_cascade_max_distance = 12000
            light.color = out_color
            light.angle = angle
    elif type == "SPOT":
        light = bpy.data.lights.get(name)
        if light == None:
            light = bpy.data.lights.new(name=name, type='SPOT')
            light.energy = intensity * 750.0
            light.shadow_buffer_clip_start = 4
            light.color = out_color
            light.spot_size = angle
    else:
        light = bpy.data.lights.get(name)
        if light == None:
            light = bpy.data.lights.new(name=name, type='POINT')
            light.energy = intensity * 750.0
            light.shadow_buffer_clip_start = 4
            light.color = out_color
            light.shadow_soft_size = angle
    
    obj_vec = Vector((0.0, 0.0, -1.0))
    rotation_vec = Vector((vector[0], vector[1], vector[2]))
    obj = bpy.data.objects.get(name)
    if obj == None:
        obj = bpy.data.objects.new(name=name, object_data=light)
        bpy.context.collection.objects.link(obj)
        obj.rotation_euler = obj_vec.rotation_difference( rotation_vec ).to_euler()
        
    return obj

def storeLighmaps(bsp, image, n_lightmaps, internal=True, hdr=False, flip=False):
    lm_size = bsp.lightmap_size[0]
    color_components = 4
    color_scale = 1.0

    if image == None:
        return False, "No image found for patching"
    
    local_pixels = list(image.pixels[:])
    
    packed_width, packed_height = image.size
    blender_lm_size = packed_width / bpy.context.scene.id_tech_3_lightmaps_per_row
    
    if internal:
        if blender_lm_size != lm_size:
            return False, "Rescale the lightmap texture atlas to the right resolution"
    else:
        lm_size = int(blender_lm_size)
        
    num_rows_colums = packed_width / lm_size
    numPixels = lm_size * lm_size * color_components
    lightmaps = [[0] * numPixels for i in range(n_lightmaps)]
    
    for pixel in range(packed_width*packed_height):
        #pixel position in packed texture
        row = pixel%packed_width
        colum = floor(pixel/packed_width)
        
        #lightmap quadrant
        quadrant_x = floor(row/lm_size)
        quadrant_y = floor(colum/lm_size)
        lightmap_id = floor(quadrant_x + (num_rows_colums * quadrant_y))
        
        if (lightmap_id > n_lightmaps-1) or (lightmap_id<0):
            continue
        else:
            #pixel id in lightmap
            lm_x = row%lm_size
            lm_y = colum%lm_size
            
            if not internal and flip:
                lm_y = lm_size-1 - lm_y
                
            pixel_id = int(lm_x + (lm_y * lm_size))
            
            lightmaps[lightmap_id][pixel_id*color_components    ] = local_pixels[4 * pixel + 0]
            lightmaps[lightmap_id][pixel_id*color_components + 1] = local_pixels[4 * pixel + 1]
            lightmaps[lightmap_id][pixel_id*color_components + 2] = local_pixels[4 * pixel + 2]
            lightmaps[lightmap_id][pixel_id*color_components + 3] = 1.0
            
    if internal:
        #clear lightmap lump
        bsp.lumps["lightmaps"].clear()
        
        #fill lightmap lump
        for i in range(n_lightmaps):
            internal_lightmap = [[0] * (lm_size * lm_size * 3)]
            for pixel in range(lm_size * lm_size):
                outColor = color_to_bytes(colorNormalize([  lightmaps[i][pixel * color_components    ],
                                                            lightmaps[i][pixel * color_components + 1],
                                                            lightmaps[i][pixel * color_components + 2]],
                                                            color_scale,
                                                            True))
                                            
                internal_lightmap[pixel * 3    ] = outColor[0]
                internal_lightmap[pixel * 3 + 1] = outColor[1]
                internal_lightmap[pixel * 3 + 2] = outColor[2]
            bsp.lumps["lightmaps"].add(internal_lightmap)
        
    if not internal or hdr:
        bsp_path = bsp.bsp_path.replace("\\","/").split(".")[0] + "/"
        if not os.path.exists(bsp_path):
            os.makedirs(bsp_path)
        file_type = "HDR" if hdr else "TARGA_RAW"
        file_ext = ".hdr" if hdr else ".tga"
        color_space = 'Linear' if hdr else "sRGB"
        
        image_settings = bpy.context.scene.render.image_settings
        image_settings.file_format = file_type
        image_settings.color_depth = '32' if hdr else '8'
        image_settings.color_mode = 'RGB'
        
        for lightmap in range(n_lightmaps):
            img_name = "lm_"+str(lightmap).zfill(4)
            image = bpy.data.images.get(img_name)
            if image == None:
                image = bpy.data.images.new("lm_"+str(lightmap).zfill(4), width = lm_size, height = lm_size, float_buffer=True)
                image.filepath_raw = bsp_path + img_name + file_ext.lower()
                image.colorspace_settings.name = color_space
                image.file_format = file_type
                
            image.pixels = lightmaps[lightmap]
            image.save_render(image.filepath_raw, scene=bpy.context.scene)
    
    if internal:
        return True, "Lightmaps succesfully added to BSP"
    else:
        return True, "Lightmap images succesfully created"
        
def create_lightgrid():
    
    bsp_group = bpy.data.node_groups.get("BspInfo")
    if bsp_group == None:
        return False
    
    lightgrid_origin = []
    lightgrid_origin.append(bsp_group.nodes["GridOrigin"].inputs[0].default_value)
    lightgrid_origin.append(bsp_group.nodes["GridOrigin"].inputs[1].default_value)
    lightgrid_origin.append(bsp_group.nodes["GridOrigin"].inputs[2].default_value)
    
    lightgrid_size = []
    lightgrid_size.append(bsp_group.nodes["GridSize"].inputs[0].default_value)
    lightgrid_size.append(bsp_group.nodes["GridSize"].inputs[1].default_value)
    lightgrid_size.append(bsp_group.nodes["GridSize"].inputs[2].default_value)
    
    lightgrid_dimensions = []
    lightgrid_dimensions.append(bsp_group.nodes["GridDimensions"].inputs[0].default_value)
    lightgrid_dimensions.append(bsp_group.nodes["GridDimensions"].inputs[1].default_value)
    lightgrid_dimensions.append(bsp_group.nodes["GridDimensions"].inputs[2].default_value)
    lightgrid_dimensions[1] /= lightgrid_dimensions[2]
                             
    lightgrid_inverse_dim = [   1.0 / lightgrid_dimensions[0],
                                1.0 / (lightgrid_dimensions[1]*lightgrid_dimensions[2]),
                                1.0 / lightgrid_dimensions[2] ]
    
    obj = GridIcoSphere.createGridIcoSphere()
    
    obj.location = lightgrid_origin
    obj.cycles_visibility.shadow = False
    
    #create the lightgrid points via arrays
    obj.modifiers.new("X_Array", type='ARRAY')
    obj.modifiers['X_Array'].use_constant_offset = True
    obj.modifiers['X_Array'].constant_offset_displace[0] = lightgrid_size[0]
    obj.modifiers['X_Array'].use_relative_offset = False
    obj.modifiers['X_Array'].count = lightgrid_dimensions[0]
    obj.modifiers['X_Array'].offset_u = lightgrid_inverse_dim[0]
    
    obj.modifiers.new("Y_Array", type='ARRAY')
    obj.modifiers['Y_Array'].use_constant_offset = True
    obj.modifiers['Y_Array'].constant_offset_displace[1] = lightgrid_size[1]
    obj.modifiers['Y_Array'].use_relative_offset = False
    obj.modifiers['Y_Array'].count = lightgrid_dimensions[1]
    obj.modifiers['Y_Array'].offset_v = lightgrid_inverse_dim[1]
    
    obj.modifiers.new("Z_Array", type='ARRAY')
    obj.modifiers['Z_Array'].use_constant_offset = True
    obj.modifiers['Z_Array'].constant_offset_displace[2] = lightgrid_size[2]
    obj.modifiers['Z_Array'].use_relative_offset = False
    obj.modifiers['Z_Array'].count = lightgrid_dimensions[2]
    obj.modifiers['Z_Array'].offset_v = lightgrid_inverse_dim[2]
    
    #scale the uv coordinates so it fits the lightgrid textures
    me = obj.data
    for loop in me.loops:
        me.uv_layers['UVMap'].data[loop.index].uv[0] *= lightgrid_inverse_dim[0]
        me.uv_layers['UVMap'].data[loop.index].uv[1] *= lightgrid_inverse_dim[1]
        
    for mat in me.materials:
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        
        node_image = nodes.new(type='ShaderNodeTexImage')
        node_image.location = -200,0
        image = bpy.data.images.get("$"+mat.name)
        if image == None:
            image = bpy.data.images.new("$"+mat.name, 
                                            width=lightgrid_dimensions[0], 
                                            height=lightgrid_dimensions[1]*lightgrid_dimensions[2],
                                            float_buffer=True)
            image.use_fake_user = True
        node_image.image = image
    return True
        
def encode_normal(normal):
    x, y, z = normal
    l = sqrt( ( x * x ) + ( y * y ) + ( z * z ) )
    if l == 0:
        return (0, 0)
    x = x/l
    y = y/l
    z = z/l
    if x == 0 and y == 0:
        return (0, 0) if z > 0 else (128, 0)
    long = int(round(atan2(y, x) * 255 / (2.0 * pi))) & 0xff
    lat  = int(round(acos(z) * 255 / (2.0 * pi))) & 0xff
    return (lat, long)

def packLightgridData(  bsp, 
                        void_pixels, 
                        amb_pixels, 
                        amb_pixels2, 
                        amb_pixels3, 
                        amb_pixels4, 
                        dir_pixels, 
                        dir_pixels2, 
                        dir_pixels3, 
                        dir_pixels4, 
                        vec_pixels, 
                        lightgrid_origin, 
                        lightgrid_dimensions, 
                        lightgrid_size, 
                        compression_level
                        ):
    #clear lightgrid data
    bsp.lumps["lightgrid"].clear()
    if bsp.use_lightgridarray:
        bsp.lumps["lightgridarray"].clear()
    
    current_pixel_mapping = 0
    hash_table = {}
    hash_table_diff = {}
    hash_table_count = {}
    num_pixels = int(lightgrid_dimensions[0] * lightgrid_dimensions[1] * lightgrid_dimensions[2])
    
    for pixel in range(num_pixels):
        if void_pixels[pixel]:
            lat, lon = encode_normal([0,0,0])
            amb = [0.0, 0.0, 0.0]
            dir = [0.0, 0.0, 0.0]
            amb2 = [0.0, 0.0, 0.0]
            dir2 = [0.0, 0.0, 0.0]
            amb3 = [0.0, 0.0, 0.0]
            dir3 = [0.0, 0.0, 0.0]
            amb4 = [0.0, 0.0, 0.0]
            dir4 = [0.0, 0.0, 0.0]
        else:   
            x = vec_pixels[pixel * 4 + 0]
            y = vec_pixels[pixel * 4 + 1]
            z = vec_pixels[pixel * 4 + 2]
            
            lat, lon = encode_normal([x,y,z])
            
            amb = colorNormalize([  amb_pixels[4 * pixel + 0],
                                    amb_pixels[4 * pixel + 1],
                                    amb_pixels[4 * pixel + 2]],
                                    1.0)
                                    
            dir = colorNormalize([  dir_pixels[4 * pixel + 0],
                                    dir_pixels[4 * pixel + 1],
                                    dir_pixels[4 * pixel + 2]],
                                    1.0)
            
            if dir_pixels2 != None and amb_pixels2 != None:
                amb2 = colorNormalize([ amb_pixels2[4 * pixel + 0],
                                        amb_pixels2[4 * pixel + 1],
                                        amb_pixels2[4 * pixel + 2]],
                                        1.0)
                dir2 = colorNormalize([ dir_pixels2[4 * pixel + 0],
                                        dir_pixels2[4 * pixel + 1],
                                        dir_pixels2[4 * pixel + 2]],
                                        1.0)
            else:
                amb2 = amb
                dir2 = dir
                
            if dir_pixels3 != None and amb_pixels3 != None:
                amb3 = colorNormalize([ amb_pixels3[4 * pixel + 0],
                                        amb_pixels3[4 * pixel + 1],
                                        amb_pixels3[4 * pixel + 2]],
                                        1.0)
                dir3 = colorNormalize([ dir_pixels3[4 * pixel + 0],
                                        dir_pixels3[4 * pixel + 1],
                                        dir_pixels3[4 * pixel + 2]],
                                        1.0)
            else:
                amb3 = amb
                dir3 = dir
                
            if dir_pixels4 != None and amb_pixels4 != None:
                amb4 = colorNormalize([ amb_pixels4[4 * pixel + 0],
                                        amb_pixels4[4 * pixel + 1],
                                        amb_pixels4[4 * pixel + 2]],
                                        1.0)
                dir4 = colorNormalize([ dir_pixels4[4 * pixel + 0],
                                        dir_pixels4[4 * pixel + 1],
                                        dir_pixels4[4 * pixel + 2]],
                                        1.0)
            else:
                amb4 = amb
                dir4 = dir
                
        array = []
        if bsp.lightmaps == 4:
            append_color_as_bytes(array, amb)
            append_color_as_bytes(array, amb2)
            append_color_as_bytes(array, amb3)
            append_color_as_bytes(array, amb4)
            append_color_as_bytes(array, dir)
            append_color_as_bytes(array, dir2)
            append_color_as_bytes(array, dir3)
            append_color_as_bytes(array, dir4)
            array.append(0)
            array.append(0)
            array.append(0)
            array.append(0)
            array.append(lat)
            array.append(lon)
        else:
            append_color_as_bytes(array, amb)
            append_color_as_bytes(array, dir)
            array.append(lat)
            array.append(lon)
        
        hashing_array = []
        hashing_diff = []
        for i in range(len(array)):
            hashing_array.append(array[i] - array[i]%compression_level)
            hashing_diff.append(array[i]%compression_level)
            
        if bsp.use_lightgridarray:
            current_hash = hash(tuple(hashing_array))
            found_twin = -1
            if current_hash in hash_table:
                found_twin = hash_table[current_hash]
            if found_twin == -1:
                bsp.lumps["lightgrid"].add(hashing_array)
                bsp.lumps["lightgridarray"].add([current_pixel_mapping])
                hash_table[current_hash] = current_pixel_mapping
                hash_table_diff[current_hash] = hashing_diff
                hash_table_count[current_hash] = 1
                current_pixel_mapping += 1
            else:
                bsp.lumps["lightgridarray"].add([found_twin])
                for index, diff in enumerate(hash_table_diff[current_hash]):
                    diff += hashing_diff[index]
                hash_table_count[current_hash] += 1
                
        else:
            bsp.lumps["lightgrid"].add(array)
            
    max_add = compression_level-1
    if compression_level > 1:
        for grid_point in bsp.lumps["lightgrid"].data:
            grid_array = grid_point.to_array()
            hashing_array = []
            for i in range(len(array)):
                hashing_array.append(grid_array[i] - grid_array[i]%compression_level)
            current_hash = hash(tuple(hashing_array))
            diff_array = hash_table_diff[current_hash]
            divisor = hash_table_count[current_hash]
            for i in range(len(diff_array)):
                diff_array[i] = min(int(round(diff_array[i] / divisor)), max_add)
                
            if bsp.lightmaps == 4:
                grid_point.ambient1[0] += diff_array[0]
                grid_point.ambient1[1] += diff_array[1]
                grid_point.ambient1[2] += diff_array[2]
                grid_point.ambient2[0] += diff_array[3]
                grid_point.ambient2[1] += diff_array[4]
                grid_point.ambient2[2] += diff_array[5]
                grid_point.ambient3[0] += diff_array[6]
                grid_point.ambient3[1] += diff_array[7]
                grid_point.ambient3[2] += diff_array[8]
                grid_point.ambient4[0] += diff_array[9]
                grid_point.ambient4[1] += diff_array[10]
                grid_point.ambient4[2] += diff_array[11]
                grid_point.direct1[0] += diff_array[12]
                grid_point.direct1[1] += diff_array[13]
                grid_point.direct1[2] += diff_array[14]
                grid_point.direct2[0] += diff_array[15]
                grid_point.direct2[1] += diff_array[16]
                grid_point.direct2[2] += diff_array[17]
                grid_point.direct3[0] += diff_array[18]
                grid_point.direct3[1] += diff_array[19]
                grid_point.direct3[2] += diff_array[20]
                grid_point.direct4[0] += diff_array[21]
                grid_point.direct4[1] += diff_array[22]
                grid_point.direct4[2] += diff_array[23]
                grid_point.styles[0] += diff_array[24]
                grid_point.styles[1] += diff_array[25]
                grid_point.styles[2] += diff_array[26]
                grid_point.styles[3] += diff_array[27]
                grid_point.lat_long[0] += diff_array[28]
                grid_point.lat_long[1] += diff_array[29]
            else:
                grid_point.ambient1[0] += diff_array[0]
                grid_point.ambient1[1] += diff_array[1]
                grid_point.ambient1[2] += diff_array[2]
                grid_point.direct1[0] += diff_array[3]
                grid_point.direct1[1] += diff_array[4]
                grid_point.direct1[2] += diff_array[5]
                grid_point.lat_long[0] += diff_array[6]
                grid_point.lat_long[1] += diff_array[7]
            
    return current_pixel_mapping
    
def storeLightgrid(bsp, hdr_export):
    vec_image = bpy.data.images.get("$Vector")
    dir_image = bpy.data.images.get("$Direct")
    amb_image = bpy.data.images.get("$Ambient")
    
    dir_image2 = bpy.data.images.get("$Direct2")
    amb_image2 = bpy.data.images.get("$Ambient2")
    
    dir_image3 = bpy.data.images.get("$Direct3")
    amb_image3 = bpy.data.images.get("$Ambient3")
    
    dir_image4 = bpy.data.images.get("$Direct4")
    amb_image4 = bpy.data.images.get("$Ambient4")
    
    if vec_image == None or dir_image == None or amb_image == None:
        return False, "Images not properly baked for patching the bsp"
    
    vec_pixels = vec_image.pixels[:]
    dir_pixels = dir_image.pixels[:]
    amb_pixels = amb_image.pixels[:]
    
    if dir_image2 != None and amb_image2 != None:
        dir_pixels2 = dir_image2.pixels[:]
        amb_pixels2 = amb_image2.pixels[:]
    else:
        dir_pixels2 = dir_pixels
        amb_pixels2 = amb_pixels
    
    if dir_image3 != None and amb_image3 != None:
        dir_pixels3 = dir_image3.pixels[:]
        amb_pixels3 = amb_image3.pixels[:]
    else:
        dir_pixels3 = dir_pixels
        amb_pixels3 = amb_pixels
    
    if dir_image4 != None and amb_image4 != None:
        dir_pixels4 = dir_image4.pixels[:]
        amb_pixels4 = amb_image4.pixels[:]
    else:
        dir_pixels4 = dir_pixels
        amb_pixels4 = amb_pixels
    
    bsp_group = bpy.data.node_groups.get("BspInfo")
    if bsp_group == None:
        return False, "Could not find BspInfo NodeGroup"
    
    lightgrid_origin = []
    lightgrid_origin.append(bsp_group.nodes["GridOrigin"].inputs[0].default_value)
    lightgrid_origin.append(bsp_group.nodes["GridOrigin"].inputs[1].default_value)
    lightgrid_origin.append(bsp_group.nodes["GridOrigin"].inputs[2].default_value)
    
    lightgrid_size = []
    lightgrid_size.append(bsp_group.nodes["GridSize"].inputs[0].default_value)
    lightgrid_size.append(bsp_group.nodes["GridSize"].inputs[1].default_value)
    lightgrid_size.append(bsp_group.nodes["GridSize"].inputs[2].default_value)
    
    lightgrid_dimensions = []
    lightgrid_dimensions.append(bsp_group.nodes["GridDimensions"].inputs[0].default_value)
    lightgrid_dimensions.append(bsp_group.nodes["GridDimensions"].inputs[1].default_value)
    lightgrid_dimensions.append(bsp_group.nodes["GridDimensions"].inputs[2].default_value)
    lightgrid_dimensions[1] /= lightgrid_dimensions[2]
                             
    num_elements_lightgrid = int(lightgrid_dimensions[0] * lightgrid_dimensions[1] * lightgrid_dimensions[2])
    
    #get all lightgrid points that are in the void
    void_pixels = [True for i in range(num_elements_lightgrid)]
    for index, leaf in enumerate(bsp.lumps["leafs"].data):
        if leaf.area == -1:
            continue
        
        start = [-lightgrid_origin[0], -lightgrid_origin[1], -lightgrid_origin[2]]
        start[0] += leaf.mins[0]
        start[1] += leaf.mins[1]
        start[2] += leaf.mins[2]
        start[0] = floor(start[0] / lightgrid_size[0])
        start[1] = floor(start[1] / lightgrid_size[1])
        start[2] = floor(start[2] / lightgrid_size[2])
        steps = [leaf.maxs[0]-leaf.mins[0], leaf.maxs[1]-leaf.mins[1], leaf.maxs[2]-leaf.mins[2]]
        steps[0] = int(ceil(steps[0] / lightgrid_size[0]))+1
        steps[1] = int(ceil(steps[1] / lightgrid_size[1]))+1
        steps[2] = int(ceil(steps[2] / lightgrid_size[2]))+1
        
        for z in range(steps[2]):
            for y in range(steps[1]):
                for x in range(steps[0]):
                    min_x = x+start[0]
                    min_y = y+start[1]
                    min_z = z+start[2]
                    if min_x >= 0 and min_y >= 0 and min_z >= 0:
                        id = (min_z)*lightgrid_dimensions[0]*lightgrid_dimensions[1]
                        id += (min_y)*lightgrid_dimensions[0]
                        id += (min_x)
                        id = int(id)
                        if id < 0 or id > num_elements_lightgrid:
                            continue
                        
                        void_pixels[id] = False
                        
    if bsp.use_lightgridarray:
        num_elements = 65535
        compression_pow = 0
        while num_elements > 65534:
            compression_level = int(pow(2, compression_pow))
            num_elements = packLightgridData(  bsp, 
                                void_pixels, 
                                amb_pixels, 
                                amb_pixels2, 
                                amb_pixels3, 
                                amb_pixels4, 
                                dir_pixels, 
                                dir_pixels2, 
                                dir_pixels3, 
                                dir_pixels4, 
                                vec_pixels, 
                                lightgrid_origin, 
                                lightgrid_dimensions, 
                                lightgrid_size, 
                                compression_level
                                )
            print("Current lightgrid compression level: " + str(compression_pow))
            compression_pow += 1
        
    else:
        packLightgridData(  bsp, 
                            void_pixels, 
                            amb_pixels, 
                            amb_pixels2, 
                            amb_pixels3, 
                            amb_pixels4, 
                            dir_pixels, 
                            dir_pixels2, 
                            dir_pixels3, 
                            dir_pixels4, 
                            vec_pixels, 
                            lightgrid_origin, 
                            lightgrid_dimensions, 
                            lightgrid_size, 
                            1
                            )
    
    if hdr_export:
        hdr_bytes = bytearray()
        for pixel in range(num_elements_lightgrid):
            if void_pixels[pixel]:
                for i in range(6):
                    hdr_bytes += struct.pack("<f", 0.0)
            else:
                hdr_bytes += struct.pack("<f", amb_pixels[4 * pixel + 0])
                hdr_bytes += struct.pack("<f", amb_pixels[4 * pixel + 1])
                hdr_bytes += struct.pack("<f", amb_pixels[4 * pixel + 2])
                hdr_bytes += struct.pack("<f", dir_pixels[4 * pixel + 0])
                hdr_bytes += struct.pack("<f", dir_pixels[4 * pixel + 1])
                hdr_bytes += struct.pack("<f", dir_pixels[4 * pixel + 2])
        
        bsp_path = bsp.bsp_path.replace("\\","/").split(".")[0] + "/"
        if not os.path.exists(bsp_path):
            os.makedirs(bsp_path)
        
        f = open(bsp_path+"lightgrid.raw", "wb")
        try:
            f.write(hdr_bytes)
        except:
            print("Failed writing: " + name)
        f.close()
    
    if bsp.use_lightgridarray:
        return True, "Lightgrid compression level: " + str(compression_pow-1)
    return True, "Did not compress the lightgrid"

def luma (color):
    return Vector.dot(color, Vector((0.299, 0.587, 0.114)))

def createLightGridTextures():
    image_names = [
        "Grid_00",
        "Grid_01",
        "Grid_02",
        "Grid_03",
        "Grid_04",
        "Grid_05",
        "Grid_06",
        "Grid_07",
        "Grid_08",
        "Grid_09",
        "Grid_10",
        "Grid_11",
        "Grid_12",
        "Grid_13",
        "Grid_14",
        "Grid_15",
        "Grid_16",
        "Grid_17",
        "Grid_18",
        "Grid_19",
        ]
    textures = [bpy.data.images.get("$"+img) for img in image_names]
    for tex in textures:
        if tex == None:
            return False
    
    width, height = textures[0].size
    
    buffer_names = [    "$Vector",
                        "$Direct",
                        "$Ambient"]
                        
    buffers = [bpy.data.images.get(img) for img in buffer_names]
    for i, buf in enumerate(buffers):
        if buf == None:
            buffers[i] = bpy.data.images.new(buffer_names[i], width=width, height=height, float_buffer=True)
            buffers[i].use_fake_user = True
    
    normals = [ Vector((-0.1876, 0.5773, 0.7947)),      # Grid_00
                Vector((-0.6071, 0.0000, 0.7947)),      # Grid_01
                Vector((-0.1876, -0.5773, 0.7947)),     # Grid_02
                Vector((0.4911, -0.3568, 0.7947)),      # Grid_03
                Vector((0.4911, 0.3568, 0.7947)),       # Grid_04
                Vector((0.7946, 0.5774, 0.1876)),       # Grid_05
                Vector((0.3035, 0.9342, -0.1876)),      # Grid_06
                Vector((-0.3035, 0.9342, 0.1876)),      # Grid_07
                Vector((-0.7947, 0.5774, -0.1876)),     # Grid_08
                Vector((-0.9822, 0.0000, 0.1876)),      # Grid_09
                Vector((-0.7947, -0.5774, -0.1876)),    # Grid_10
                Vector((-0.3035, -0.9342, 0.1876)),     # Grid_11
                Vector((0.3035, -0.9342, -0.1876)),     # Grid_12
                Vector((0.7947, -0.5774, 0.1876)),      # Grid_13
                Vector((0.9822, 0.0000, -0.1876)),      # Grid_14
                Vector((0.1876, -0.5774, -0.7947)),     # Grid_15
                Vector((0.6071, 0.0000, -0.7947)),      # Grid_16
                Vector((0.1876, 0.5774, -0.7947)),      # Grid_17
                Vector((-0.4911, 0.3568, -0.7947)),     # Grid_18
                Vector((-0.4911, -0.3568, -0.7947))     # Grid_19
                ]
    pixels = [  textures[0].pixels[:],
                textures[1].pixels[:],
                textures[2].pixels[:],
                textures[3].pixels[:],
                textures[4].pixels[:],
                textures[5].pixels[:],
                textures[6].pixels[:],
                textures[7].pixels[:],
                textures[8].pixels[:],
                textures[9].pixels[:],
                textures[10].pixels[:],
                textures[11].pixels[:],
                textures[12].pixels[:],
                textures[13].pixels[:],
                textures[14].pixels[:],
                textures[15].pixels[:],
                textures[16].pixels[:],
                textures[17].pixels[:],
                textures[18].pixels[:],
                textures[19].pixels[:]
                ]
                
    ambient_pixels = []
    direct_pixels = []
    vector_pixels = []
    
    for pixel in range(width*height):
        color_samples = [Vector((0.0, 0.0, 0.0)) for i in range(20)]
        for i, samples in enumerate(pixels):
            color_samples[i][0] = samples[pixel*4 + 0]
            color_samples[i][1] = samples[pixel*4 + 1]
            color_samples[i][2] = samples[pixel*4 + 2]
            
        avg_vec = Vector((0.0, 0.0, 0.0))
        for i in range(20):
            avg_vec += luma(color_samples[i]) * normals[i]
            
        Vector.normalize(avg_vec)
        
        direct_color = Vector((0.0, 0.0, 0.0))
        weight = 0.0
        for i in range(20):
            dot = max(0.0, Vector.dot(normals[i], avg_vec))
            if dot > 0.0:
                dot = sqrt(sqrt(dot))
            direct_color += color_samples[i] * dot
            weight += max(0.0, Vector.dot(normals[i], avg_vec))
            
        if weight != 0.0:
            direct_color /= weight
            
        ambient_color = Vector((0.0, 0.0, 0.0))
        for i in range(20):
            dot = max(0.0, Vector.dot(normals[i], avg_vec))
            if dot > 0.0:
                dot = sqrt(sqrt(dot))
            ambient_color += color_samples[i]
            ambient_color -= color_samples[i] * dot
        ambient_color /= 20.0;
        
        ambient_pixels.append(ambient_color[0])
        ambient_pixels.append(ambient_color[1])
        ambient_pixels.append(ambient_color[2])
        ambient_pixels.append(1.0)
        
        direct_pixels.append(direct_color[0])
        direct_pixels.append(direct_color[1])
        direct_pixels.append(direct_color[2])
        direct_pixels.append(1.0)
        
        vector_pixels.append(avg_vec[0])
        vector_pixels.append(avg_vec[1])
        vector_pixels.append(avg_vec[2])
        vector_pixels.append(1.0)
    
    buffers[0].pixels = vector_pixels
    buffers[1].pixels = direct_pixels
    buffers[2].pixels = ambient_pixels

def clamp_uv(val):
    return max(0, min(val, 1))
        
def bake_uv_to_vc(mesh, uv_layer, vertex_layer):

    lightmap = bpy.data.images.get("$lightmap_bake")
    vertexmap = bpy.data.images.get("$vertmap_bake")
    
    if lightmap == None or vertexmap == None:
        return False, "Could not find $lightmap_bake or $vertmap_bake"
    
    lm_width = lightmap.size[0]
    lm_height = lightmap.size[1]
    
    vt_width = vertexmap.size[0]
    vt_height = vertexmap.size[1]

    lm_local_pixels = list(lightmap.pixels[:])
    vt_local_pixels = list(vertexmap.pixels[:])

    for face in mesh.polygons:
        mat_name = mesh.materials[face.material_index].name
        
        if mat_name.endswith(".vertex"):
            local_pixels = vt_local_pixels
            width = vt_width
            height = vt_height
        else:
            local_pixels = lm_local_pixels
            width = lm_width
            height = lm_height
        
        for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
            uv_coords = mesh.uv_layers[uv_layer].data[loop_idx].uv
            # Just sample the closest pixel to the UV coordinate
            # An improved approach might be to implement
            # bilinear sampling here instead
            target = [round(clamp_uv(uv_coords.x) * (width - 1)), round(clamp_uv(uv_coords.y) * (height - 1))]
            index = ( target[1] * width + target[0] ) * 4
            
            color = colorNormalize([local_pixels[index], local_pixels[index + 1], local_pixels[index + 2]], 1.0)

            mesh.vertex_colors[vertex_layer].data[loop_idx].color[0] = color[0]
            mesh.vertex_colors[vertex_layer].data[loop_idx].color[1] = color[1]
            mesh.vertex_colors[vertex_layer].data[loop_idx].color[2] = color[2]
            #mesh.vertex_colors[vertex_layer].data[loop_idx].color[3] = 1.0
    return True, "Vertex colors succesfully added to mesh"

def storeHDRVertexColors(bsp, meshes):
    
    lightmap = bpy.data.images.get("$lightmap_bake")
    vertexmap = bpy.data.images.get("$vertmap_bake")
    
    if lightmap == None or vertexmap == None:
        return False, "Could not find $lightmap_bake or $vertmap_bake"
    
    lm_width = lightmap.size[0]
    lm_height = lightmap.size[1]
    vt_width = vertexmap.size[0]
    vt_height = vertexmap.size[1]

    lm_local_pixels = list(lightmap.pixels[:])
    vt_local_pixels = list(vertexmap.pixels[:])
    
    hdr_vertex_colors = [0.0 for i in range(int(bsp.lumps["drawverts"].count*3))]
    for mesh in meshes:
        #check if its an imported bsp data set
        if mesh.vertex_layers_int.get("BSP_VERT_INDEX") is not None:
            bsp_indices = mesh.vertex_layers_int["BSP_VERT_INDEX"]
            for poly in mesh.polygons:
                mat_name = mesh.materials[poly.material_index].name
                
                if mat_name.endswith(".vertex"):
                    local_pixels = vt_local_pixels
                    width = vt_width
                    height = vt_height
                else:
                    local_pixels = lm_local_pixels
                    width = lm_width
                    height = lm_height
                
                for vertex, loop in zip(poly.vertices, poly.loop_indices):
                    #get the vertex position in the bsp file
                    bsp_vert_index = bsp_indices.data[vertex].value
                    if bsp_vert_index < 0:
                        continue
                    uv_coords = mesh.uv_layers["LightmapUV"].data[loop].uv
                    target = [round(clamp_uv(uv_coords.x) * (width - 1)), round(clamp_uv(uv_coords.y) * (height - 1))]
                    index = ( target[1] * width + target[0] ) * 4

                    hdr_vertex_colors[bsp_vert_index * 3    ] = local_pixels[index]
                    hdr_vertex_colors[bsp_vert_index * 3 + 1] = local_pixels[index + 1]
                    hdr_vertex_colors[bsp_vert_index * 3 + 2] = local_pixels[index + 2]
    
    hdr_bytes = bytearray()
    for vert in range(bsp.lumps["drawverts"].count):
        hdr_bytes += struct.pack("<f", hdr_vertex_colors[vert * 3    ])
        hdr_bytes += struct.pack("<f", hdr_vertex_colors[vert * 3 + 1])
        hdr_bytes += struct.pack("<f", hdr_vertex_colors[vert * 3 + 2])
        
    bsp_path = bsp.bsp_path.replace("\\","/").split(".")[0] + "/"
    if not os.path.exists(bsp_path):
        os.makedirs(bsp_path)
        
    file_path = bsp_path+"vertlight.raw"
        
    f = open(file_path, "wb")
    try:
        f.write(hdr_bytes)
    except:
        print("Failed writing: " + file_path)
    f.close()
    
    return True, "HDR Vertex colors succesfully saved"