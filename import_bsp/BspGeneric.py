#----------------------------------------------------------------------------#
#TODO:  refactor loading bsp files and md3 files, right now its a mess o.O
#TODO:  build patches via c library for speed?
#----------------------------------------------------------------------------#

if "struct" not in locals():
    import struct

import imp
if "BspClasses" in locals():
    imp.reload( BspClasses )
else:
    from . import BspClasses as BSP
    
if "os" not in locals():
    import os
    
import bpy
import bmesh
from math import floor, ceil, pi, sin, cos
import mathutils

#prevents overwriting of old images
def create_new_image(name, width, height, float_buffer=False):
    old_image = bpy.data.images.get(name)
    if old_image != None:
        old_image.name = name + "_previous.000"
        
    if float_buffer:
        image = bpy.data.images.new(name, width=width, height=height, float_buffer=True)
    else:
        image = bpy.data.images.new(name, width=width, height=height)
        
    image.use_fake_user=True
    return image
            
def create_white_image():
    image = bpy.data.images.get("$whiteimage")
    if image == None:
        image = bpy.data.images.new("$whiteimage", width=8, height=8)
    pixels = []
    for pixel in range(64):
        pixels.append(1.0)
        pixels.append(1.0)
        pixels.append(1.0)
        pixels.append(1.0)
    image.pixels = pixels
    image.use_fake_user=True

def pack_lightmaps(bsp, import_settings):
    use_internal_lightmaps = True
    lightmaps = []
    n_lightmaps = 0
    color_scale = 1.0
    color_components = 4
    try:
        path = bsp.bsp_path[:-len(".bsp")] + "/"
        lm_files = os.listdir(path)
        lm_list = [path + file_name
                    for file_name in lm_files
                    if file_name.lower().startswith('lm_') and (file_name.lower().endswith('.tga') or file_name.lower().endswith('.jpg'))]
        lightmap_size = 0
        for lm in lm_list:
            image = bpy.data.images.load(lm, check_existing=True)
            working_pixels = list(image.pixels[:])
            pixels = []
            for y in range(image.size[1]):
                for x in range(image.size[0]):
                    id = floor(x + (image.size[1] * (image.size[1]-1))- (y * (image.size[1])))
                    pixels.append(working_pixels[id * 4 + 0])
                    pixels.append(working_pixels[id * 4 + 1])
                    pixels.append(working_pixels[id * 4 + 2])
                    pixels.append(working_pixels[id * 4 + 3])
                    
            lightmaps.append(pixels)
            #assume square lightmaps
            if lightmap_size != 0 and lightmap_size != image.size[0]:
                use_internal_lightmaps = True
                break
            lightmap_size = image.size[0]
            bsp.lightmap_size = image.size
            n_lightmaps += 1
            use_internal_lightmaps = False
    except:
        use_internal_lightmaps = True      
    
    if use_internal_lightmaps:
        print("Using internal lightmaps")
        lightmaps = []
        #assume square lightmaps
        lightmap_size = bsp.internal_lightmap_size[0]
        for lm in bsp.lumps["lightmaps"].data:
            lightmaps.append(lm.map)
        n_lightmaps = bsp.lumps["lightmaps"].count
        color_scale = 255.0
        color_components = 3
    
    force_vertex_lighting = False
    if n_lightmaps == 0:
        print("Using vertex light only")
        force_vertex_lighting = True
        lightmap_size = 128
    
    num_rows_colums = import_settings.packed_lightmap_size / lightmap_size
    max_lightmaps = num_rows_colums * num_rows_colums
    
    #grow lightmap atlas if needed
    for i in range(6):
        if (float(n_lightmaps) > max_lightmaps):
            import_settings.packed_lightmap_size *= 2
            num_rows_colums = import_settings.packed_lightmap_size / lightmap_size
            max_lightmaps = num_rows_colums * num_rows_colums
        else:
            import_settings.log.append("found best packed lightmap size: " + str(import_settings.packed_lightmap_size))
            break
        
    bpy.context.scene.id_tech_3_lightmaps_per_row = num_rows_colums
        
    if force_vertex_lighting == True:
        return
        
    packed_lm_size = import_settings.packed_lightmap_size
    
    numPixels = packed_lm_size*packed_lm_size*4
    #max_colum = ceil((lightmaps_lump.count-1) / PACKED_LM_SIZE)
    pixels = [0]*numPixels
    
    for pixel in range(packed_lm_size*packed_lm_size):
        #pixel position in packed texture
        row = pixel%packed_lm_size
        colum = floor(pixel/packed_lm_size)
        
        #lightmap quadrant
        quadrant_x = floor(row/lightmap_size)
        quadrant_y = floor(colum/lightmap_size)
        lightmap_id = floor(quadrant_x + (num_rows_colums * quadrant_y))
        
        #if quadrant_y > max_colum:
            #break
        
        if (lightmap_id > n_lightmaps-1) or (lightmap_id<0):
            continue
        else:
            #pixel id in lightmap
            lm_x = row%lightmap_size
            lm_y = colum%lightmap_size
            pixel_id = floor(lm_x + (lm_y * lightmap_size))
            pixels[4 * pixel + 0] = (float(lightmaps[lightmap_id][pixel_id*color_components + 0])/color_scale)
            pixels[4 * pixel + 1] = (float(lightmaps[lightmap_id][pixel_id*color_components + 1])/color_scale)
            pixels[4 * pixel + 2] = (float(lightmaps[lightmap_id][pixel_id*color_components + 2])/color_scale)
            pixels[4 * pixel + 3] = (float(1.0))
            
    image = create_new_image("$lightmap", packed_lm_size, packed_lm_size)
    image.pixels = pixels
    image.pack()
    
def pack_lm_tc(tc, lightmap_id, lightmap_size, packed_lm_size):
    
    #maybe handle lightmap_ids better?
    if (lightmap_id < 0):
        return [0.0, 0.0]
    
    num_rows_colums = packed_lm_size / lightmap_size
    scale_value = lightmap_size / packed_lm_size
    
    x = (lightmap_id%num_rows_colums) * scale_value
    y = floor(lightmap_id/num_rows_colums) * scale_value
    
    packed_tc = [tc[0]*scale_value+x,tc[1]*scale_value+y]
    return packed_tc

def get_lm_id(tc, lightmap_size, packed_lm_size):
    row = tc[0]*packed_lm_size
    colum = tc[1]*packed_lm_size
    quadrant_x = floor(row/lightmap_size)
    quadrant_y = floor(colum/lightmap_size)
    
    scale = packed_lm_size / lightmap_size
    return floor(quadrant_x + (scale * quadrant_y))

def unpack_lm_tc(tc, lightmap_size, packed_lm_size):
    row = tc[0]*packed_lm_size
    colum = tc[1]*packed_lm_size
    quadrant_x = floor(row/lightmap_size)
    quadrant_y = floor(colum/lightmap_size)
    
    scale = packed_lm_size / lightmap_size
    lightmap_id = floor(quadrant_x + (scale * quadrant_y))
    
    quadrant_scale = lightmap_size / packed_lm_size
    
    tc[0] = (tc[0] - (quadrant_x * quadrant_scale)) * scale
    tc[1] = (tc[1] - (quadrant_y * quadrant_scale)) * scale
    return lightmap_id

#appends a 3 component byte color to a pixel list
def append_byte_to_color_list(byte_color, list, scale):
    list.append(byte_color[0]*scale)
    list.append(byte_color[1]*scale)
    list.append(byte_color[2]*scale)
    list.append(1.0)

def pack_lightgrid(bsp):
    world_mins = bsp.lumps["models"].data[0].mins
    world_maxs = bsp.lumps["models"].data[0].maxs
    
    lightgrid_origin = [    bsp.lightgrid_size[0] * ceil( world_mins[0] / bsp.lightgrid_size[0]),
                            bsp.lightgrid_size[1] * ceil( world_mins[1] / bsp.lightgrid_size[1]),
                            bsp.lightgrid_size[2] * ceil( world_mins[2] / bsp.lightgrid_size[2]) ]
                            
    bsp.lightgrid_origin = lightgrid_origin
                            
    maxs = [    bsp.lightgrid_size[0] * floor( world_maxs[0] / bsp.lightgrid_size[0]),
                bsp.lightgrid_size[1] * floor( world_maxs[1] / bsp.lightgrid_size[1]),
                bsp.lightgrid_size[2] * floor( world_maxs[2] / bsp.lightgrid_size[2]) ]
                
    lightgrid_dimensions = [ (maxs[0] - lightgrid_origin[0]) / bsp.lightgrid_size[0] + 1,
                             (maxs[1] - lightgrid_origin[1]) / bsp.lightgrid_size[1] + 1,
                             (maxs[2] - lightgrid_origin[2]) / bsp.lightgrid_size[2] + 1 ]
                             
    bsp.lightgrid_inverse_dim = [   1.0 / lightgrid_dimensions[0],
                                    1.0 / (lightgrid_dimensions[1]*lightgrid_dimensions[2]),
                                    1.0 / lightgrid_dimensions[2] ]
                                    
    bsp.lightgrid_z_step = 1.0 / lightgrid_dimensions[2]
    bsp.lightgrid_dim = lightgrid_dimensions
    
    a1_pixels = []
    a2_pixels = []
    a3_pixels = []
    a4_pixels = []
    d1_pixels = []
    d2_pixels = []
    d3_pixels = []
    d4_pixels = []
    l_pixels = []
    
    num_elements = int(lightgrid_dimensions[0]*lightgrid_dimensions[1]*lightgrid_dimensions[2])
    num_elements_bsp = bsp.lumps["lightgridarray"].count if bsp.use_lightgridarray else bsp.lumps["lightgrid"].count
    
    if num_elements == num_elements_bsp:
        for pixel in range(num_elements):
            
            if bsp.use_lightgridarray:
                index = bsp.lumps["lightgridarray"].data[pixel].data
            else:
                index = pixel
            
            ambient1 = mathutils.Vector((0,0,0))
            ambient2 = mathutils.Vector((0,0,0))
            ambient3 = mathutils.Vector((0,0,0))
            ambient4 = mathutils.Vector((0,0,0))
            direct1 = mathutils.Vector((0,0,0))
            direct2 = mathutils.Vector((0,0,0))
            direct3 = mathutils.Vector((0,0,0))
            direct4 = mathutils.Vector((0,0,0))
            l = mathutils.Vector((0,0,0))
            
            ambient1 = bsp.lumps["lightgrid"].data[index].ambient1
            direct1 = bsp.lumps["lightgrid"].data[index].direct1
            if bsp.lightmaps > 1:
                ambient2 = bsp.lumps["lightgrid"].data[index].ambient2
                ambient3 = bsp.lumps["lightgrid"].data[index].ambient3
                ambient4 = bsp.lumps["lightgrid"].data[index].ambient4
                direct2 = bsp.lumps["lightgrid"].data[index].direct2
                direct3 = bsp.lumps["lightgrid"].data[index].direct3
                direct4 = bsp.lumps["lightgrid"].data[index].direct4
                
            lat = (bsp.lumps["lightgrid"].data[index].lat_long[0]/255.0) * 2.0 * pi
            long = (bsp.lumps["lightgrid"].data[index].lat_long[1]/255.0) * 2.0 * pi
                
            slat = sin(lat)
            clat = cos(lat)
            slong = sin(long)
            clong = cos(long)
                
            l = mathutils.Vector((clat * slong, slat * slong, clong)).normalized()
            
            color_scale = 1.0/255.0
            append_byte_to_color_list(ambient1, a1_pixels, color_scale)
            append_byte_to_color_list(direct1, d1_pixels, color_scale)
            if bsp.lightmaps > 1:
                append_byte_to_color_list(ambient2, a2_pixels, color_scale)
                append_byte_to_color_list(ambient3, a3_pixels, color_scale)
                append_byte_to_color_list(ambient4, a4_pixels, color_scale)
                append_byte_to_color_list(direct2, d2_pixels, color_scale)
                append_byte_to_color_list(direct3, d3_pixels, color_scale)
                append_byte_to_color_list(direct4, d4_pixels, color_scale)
                
            append_byte_to_color_list(l, l_pixels, 1.0)
    else:
        a1_pixels = [0.0 for i in range(num_elements*4)]
        a2_pixels = [0.0 for i in range(num_elements*4)]
        a3_pixels = [0.0 for i in range(num_elements*4)]
        a4_pixels = [0.0 for i in range(num_elements*4)]
        d1_pixels = [0.0 for i in range(num_elements*4)]
        d2_pixels = [0.0 for i in range(num_elements*4)]
        d3_pixels = [0.0 for i in range(num_elements*4)]
        d4_pixels = [0.0 for i in range(num_elements*4)]
        l_pixels = [0.0 for i in range(num_elements*4)]
        print("Lightgridarray mismatch!")
        print(str(num_elements) + " != " + str(num_elements_bsp))
    
    ambient1 = create_new_image("$lightgrid_ambient1", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
    ambient1.pixels = a1_pixels
    ambient1.pack()
    
    direct1 = create_new_image("$lightgrid_direct1", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
    direct1.pixels = d1_pixels
    direct1.pack()
    
    if bsp.lightmaps > 1:
        ambient2 = create_new_image("$lightgrid_ambient2", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
        ambient3 = create_new_image("$lightgrid_ambient3", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
        ambient4 = create_new_image("$lightgrid_ambient4", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
        ambient2.pixels = a2_pixels
        ambient3.pixels = a3_pixels
        ambient4.pixels = a4_pixels
        ambient2.pack() 
        ambient3.pack() 
        ambient4.pack() 
        direct2 = create_new_image("$lightgrid_direct2", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
        direct3 = create_new_image("$lightgrid_direct3", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
        direct4 = create_new_image("$lightgrid_direct4", lightgrid_dimensions[0], lightgrid_dimensions[1]*lightgrid_dimensions[2])
        direct2.pixels = d2_pixels
        direct3.pixels = d3_pixels
        direct4.pixels = d4_pixels
        direct2.pack() 
        direct3.pack() 
        direct4.pack() 
    lightvec = create_new_image( "$lightgrid_vector", 
                                    lightgrid_dimensions[0], 
                                    lightgrid_dimensions[1]*lightgrid_dimensions[2],
                                    True)
    lightvec.colorspace_settings.name = "Non-Color"
    lightvec.pixels = l_pixels      
    lightvec.pack()  
            
def lerpVertices(vertex1, vertex2, vertex_class, lightmaps):
    vertexArray = []
    vertexArray.append((vertex1.position[0] + vertex2.position[0])/2.0)
    vertexArray.append((vertex1.position[1] + vertex2.position[1])/2.0)
    vertexArray.append((vertex1.position[2] + vertex2.position[2])/2.0)
    
    vertexArray.append((vertex1.texcoord[0] + vertex2.texcoord[0])/2.0)
    vertexArray.append(1.0 - (vertex1.texcoord[1] + vertex2.texcoord[1])/2.0)
    vertexArray.append((vertex1.lm1coord[0] + vertex2.lm1coord[0])/2.0)
    vertexArray.append((vertex1.lm1coord[1] + vertex2.lm1coord[1])/2.0)
    
    if lightmaps > 1:
        vertexArray.append((vertex1.lm2coord[0] + vertex2.lm2coord[0])/2.0)
        vertexArray.append((vertex1.lm2coord[1] + vertex2.lm2coord[1])/2.0)
        vertexArray.append((vertex1.lm3coord[0] + vertex2.lm3coord[0])/2.0)
        vertexArray.append((vertex1.lm3coord[1] + vertex2.lm3coord[1])/2.0)
        vertexArray.append((vertex1.lm4coord[0] + vertex2.lm4coord[0])/2.0)
        vertexArray.append((vertex1.lm4coord[1] + vertex2.lm4coord[1])/2.0)
    
    vec = mathutils.Vector(vertex1.normal) + mathutils.Vector(vertex2.normal)
    vec.normalize()
    
    vertexArray.append(vec[0])
    vertexArray.append(vec[1])
    vertexArray.append(vec[2])
    
    vertexArray.append(((vertex1.color1[0] + vertex2.color1[0])/2.0)*255.0)
    vertexArray.append(((vertex1.color1[1] + vertex2.color1[1])/2.0)*255.0)
    vertexArray.append(((vertex1.color1[2] + vertex2.color1[2])/2.0)*255.0)
    vertexArray.append(((vertex1.color1[3] + vertex2.color1[3])/2.0)*255.0)
    
    if lightmaps > 1:
        vertexArray.append(((vertex1.color2[0] + vertex2.color2[0])/2.0)*255.0)
        vertexArray.append(((vertex1.color2[1] + vertex2.color2[1])/2.0)*255.0)
        vertexArray.append(((vertex1.color2[2] + vertex2.color2[2])/2.0)*255.0)
        vertexArray.append(((vertex1.color2[3] + vertex2.color2[3])/2.0)*255.0)
        
        vertexArray.append(((vertex1.color3[0] + vertex2.color3[0])/2.0)*255.0)
        vertexArray.append(((vertex1.color3[1] + vertex2.color3[1])/2.0)*255.0)
        vertexArray.append(((vertex1.color3[2] + vertex2.color3[2])/2.0)*255.0)
        vertexArray.append(((vertex1.color3[3] + vertex2.color3[3])/2.0)*255.0)
        
        vertexArray.append(((vertex1.color4[0] + vertex2.color4[0])/2.0)*255.0)
        vertexArray.append(((vertex1.color4[1] + vertex2.color4[1])/2.0)*255.0)
        vertexArray.append(((vertex1.color4[2] + vertex2.color4[2])/2.0)*255.0)
        vertexArray.append(((vertex1.color4[3] + vertex2.color4[3])/2.0)*255.0)
    
    return vertex_class(vertexArray)
            
class blender_model_data:
    def __init__(model):
        model.vertices = []
        model.vertex_bsp_indices = []
        model.normals = []
        model.indices = []
        model.face_vertices = []
        model.face_materials = []
        model.face_tcs = []
        model.face_lm1_tcs = []
        model.face_lm2_tcs = []
        model.face_lm3_tcs = []
        model.face_lm4_tcs = []
        model.face_vert_color = []
        model.face_vert_color2 = []
        model.face_vert_color3 = []
        model.face_vert_color4 = []
        model.face_vert_alpha = []
        model.vertex_groups = { #"Patches" : set(),
                                "Lightmapped": set()}
        model.material_names = []
        model.vertex_class = BSP.vertex_rbsp
        model.lightmaps = 4
        model.lightmap_size = 128
        model.current_index = 0
        model.current_sub_model = 0
        model.index_mapping = []
        
    def parse_bsp_surface(model, bsp, face, shaders_lump, import_settings):
        drawverts_lump = bsp.lumps["drawverts"].data
        index = face.index
        #bsp only stores triangles, so there are n_indexes/3 trinangles in this face
        for i in range(int(face.n_indexes / 3)):
            
            index_0 = face.vertex + bsp.lumps["drawindexes"].data[index + 0].offset
            index_1 = face.vertex + bsp.lumps["drawindexes"].data[index + 2].offset
            index_2 = face.vertex + bsp.lumps["drawindexes"].data[index + 1].offset
            
            if model.index_mapping[index_0] < 0:
                model.index_mapping[index_0] = model.current_index
                model.vertices.append(drawverts_lump[index_0].position)
                model.normals.append(drawverts_lump[index_0].normal)
                model.vertex_bsp_indices.append(index_0)
                model.current_index += 1
            if model.index_mapping[index_1] < 0:
                model.index_mapping[index_1] = model.current_index
                model.vertices.append(drawverts_lump[index_1].position)
                model.normals.append(drawverts_lump[index_1].normal)
                model.vertex_bsp_indices.append(index_1)
                model.current_index += 1
            if model.index_mapping[index_2] < 0:
                model.index_mapping[index_2] = model.current_index
                model.vertices.append(drawverts_lump[index_2].position)
                model.normals.append(drawverts_lump[index_2].normal)
                model.vertex_bsp_indices.append(index_2)
                model.current_index += 1
            
            indices = []
            indices.append(model.index_mapping[index_0])
            indices.append(model.index_mapping[index_1])
            indices.append(model.index_mapping[index_2])
            tcs = []
            lm1_tcs = []
            colors = []
            if model.lightmaps > 1:
                lm2_tcs = []
                lm3_tcs = []
                lm4_tcs = []
                colors2 = []
                colors3 = []
                colors4 = []
            alphas = []
            for face_index in [index_0, index_1, index_2]:
                tcs.append(drawverts_lump[face_index].texcoord)
                
                #packed lightmap tcs
                lm1_tcs.append(pack_lm_tc(  drawverts_lump[face_index].lm1coord, 
                                            face.lm_indexes[0], 
                                            model.lightmap_size, 
                                            import_settings.packed_lightmap_size))
                colors.append(drawverts_lump[face_index].color1)
                
                if model.lightmaps > 1:
                    lm2_tcs.append(pack_lm_tc(  drawverts_lump[face_index].lm2coord, 
                                                face.lm_indexes[1], 
                                                model.lightmap_size, 
                                                import_settings.packed_lightmap_size))
                    lm3_tcs.append(pack_lm_tc(  drawverts_lump[face_index].lm3coord, 
                                                face.lm_indexes[2], 
                                                model.lightmap_size, 
                                                import_settings.packed_lightmap_size))
                    lm4_tcs.append(pack_lm_tc(  drawverts_lump[face_index].lm4coord, 
                                                face.lm_indexes[3], 
                                                model.lightmap_size, 
                                                import_settings.packed_lightmap_size))
                    colors2.append(drawverts_lump[face_index].color2)
                    colors3.append(drawverts_lump[face_index].color3)
                    colors4.append(drawverts_lump[face_index].color4)
                
                alphas.append([drawverts_lump[face_index].color1[3],drawverts_lump[face_index].color1[3],drawverts_lump[face_index].color1[3],drawverts_lump[face_index].color1[3]])
                index += 1
            model.face_vertices.append(indices)
            
            material_suffix = ""
            if face.lm_indexes[0] < 0:
                material_suffix = ".vertex"
            else:
                model.vertex_groups["Lightmapped"].add(indices[0])
                model.vertex_groups["Lightmapped"].add(indices[1])
                model.vertex_groups["Lightmapped"].add(indices[2])
            material_name = shaders_lump[face.texture].name + material_suffix
            
            if not (material_name in model.material_names):
                model.material_names.append(material_name)
            model.face_materials.append(model.material_names.index(material_name))
            
            model.face_tcs.append(tcs)
            model.face_lm1_tcs.append(lm1_tcs)
            model.face_vert_color.append(colors)
            
            if model.lightmaps > 1:
                model.face_lm2_tcs.append(lm2_tcs)
                model.face_lm3_tcs.append(lm3_tcs)
                model.face_lm4_tcs.append(lm4_tcs)
                model.face_vert_color2.append(colors2)
                model.face_vert_color3.append(colors3)
                model.face_vert_color4.append(colors4)
                
            model.face_vert_alpha.append(alphas)
            
    def parse_patch_surface(model, bsp, face, shaders_lump, import_settings):
        drawverts_lump = bsp.lumps["drawverts"].data
        
        width = int(face.patch_width-1)
        height = int(face.patch_height-1)
                
        MAX_GRID_SIZE = 65
        
        ctrlPoints = [[0 for x in range(MAX_GRID_SIZE)] for y in range(MAX_GRID_SIZE)]
        indicesPoints = [[0 for x in range(MAX_GRID_SIZE)] for y in range(MAX_GRID_SIZE)]
        bspPoints = [[-1 for x in range(MAX_GRID_SIZE)] for y in range(MAX_GRID_SIZE)]
        for i in range(face.patch_width):
            for j in range(face.patch_height):
                vertex = drawverts_lump[face.vertex + j*face.patch_width + i]
                ctrlPoints[j][i] = vertex
                bspPoints[j][i] = face.vertex + j*face.patch_width + i
                indicesPoints[j][i] = model.index_mapping[face.vertex + j*face.patch_width + i]
                
        if import_settings.subdivisions > 0:
            for subd in range(import_settings.subdivisions):
                pos_w = 0
                pos_h = 0
                added_width = 0
                added_height = 0
                #add new colums
                for i in range(width//2):
                    if ((width + 2) > MAX_GRID_SIZE):
                        break
                    pos_w = i * 2 + added_width
                    width += 2
                    added_width +=2
                    #build new vertices
                    for j in range(height+1):
                        prev = lerpVertices(ctrlPoints[j][pos_w], ctrlPoints[j][pos_w+1], model.vertex_class, model.lightmaps)
                        next = lerpVertices(ctrlPoints[j][pos_w+1], ctrlPoints[j][pos_w+2], model.vertex_class, model.lightmaps)
                        midl = lerpVertices(prev, next, model.vertex_class, model.lightmaps)
                    
                        #replace peak
                        for x in range(width):
                            k = width - x
                            if (k <= pos_w+3):
                                break
                            ctrlPoints[j][k] = ctrlPoints[j][k-2]
                            indicesPoints[j][k] = indicesPoints[j][k-2]
                            
                        ctrlPoints[j][pos_w + 1] = prev;
                        ctrlPoints[j][pos_w + 2] = midl;
                        ctrlPoints[j][pos_w + 3] = next;
                        indicesPoints[j][pos_w + 1] = -2;
                        indicesPoints[j][pos_w + 2] = -2;
                        indicesPoints[j][pos_w + 3] = -2;
                        
                #add new rows
                for j in range(height//2):
                    if ((height + 2) > MAX_GRID_SIZE):
                        break
                    pos_h = j * 2 + added_height
                    height += 2
                    added_height +=2
                    #build new vertices
                    for i in range(width+1):
                        prev = lerpVertices(ctrlPoints[pos_h][i], ctrlPoints[pos_h+1][i], model.vertex_class, model.lightmaps)
                        next = lerpVertices(ctrlPoints[pos_h+1][i], ctrlPoints[pos_h+2][i], model.vertex_class, model.lightmaps)
                        midl = lerpVertices(prev, next, model.vertex_class, model.lightmaps)
                    
                        #replace peak
                        for x in range(height):
                            k = height - x
                            if (k <= pos_h+3):
                                break
                            ctrlPoints[k][i] = ctrlPoints[k-2][i]
                            indicesPoints[k][i] = indicesPoints[k-2][i]
                            
                        ctrlPoints[pos_h + 1][i] = prev;
                        ctrlPoints[pos_h + 2][i] = midl;
                        ctrlPoints[pos_h + 3][i] = next;
                        indicesPoints[pos_h + 1][i] = -2;
                        indicesPoints[pos_h + 2][i] = -2;
                        indicesPoints[pos_h + 3][i] = -2;
        
        if import_settings.subdivisions > -1:
            #now smooth the rest of the points
            for i in range(width+1):
                for j in range(1, height, 2):
                    prev = lerpVertices(ctrlPoints[j][i], ctrlPoints[j+1][i], model.vertex_class, model.lightmaps)
                    next = lerpVertices(ctrlPoints[j][i], ctrlPoints[j-1][i], model.vertex_class, model.lightmaps)
                    midl = lerpVertices(prev, next, model.vertex_class, model.lightmaps)
                    
                    ctrlPoints[j][i] = midl
                    if (indicesPoints[j][i] < 0):
                        indicesPoints[j][i] = -4;
                        
            for j in range(height+1):
                for i in range(1, width, 2):
                    prev = lerpVertices(ctrlPoints[j][i], ctrlPoints[j][i+1], model.vertex_class, model.lightmaps)
                    next = lerpVertices(ctrlPoints[j][i], ctrlPoints[j][i-1], model.vertex_class, model.lightmaps)
                    midl = lerpVertices(prev, next, model.vertex_class, model.lightmaps)
                    
                    ctrlPoints[j][i] = midl
                    if (indicesPoints[j][i] < 0):
                        indicesPoints[j][i] = -4;
                        
        #fix bsp indices
        fixed_bsp_indices = [[-1 for x in range(width+1)] for y in range(height+1)]
        step_w = int((width+1)/(face.patch_width-1))
        step_h = int((height+1)/(face.patch_height-1))
        for w, i in enumerate(range(0, width+1, step_w)):
            for h, j in enumerate(range(0, height+1, step_h)):
                fixed_bsp_indices[j][i] = bspPoints[h][w]
            
        indicesPoints2 = []
        bspPoints2 = []
        patch = []
        for j in range(height+1):
            for i in range(width+1):
                patch.append(ctrlPoints[j][i])
                indicesPoints2.append(indicesPoints[j][i])
                bspPoints2.append(fixed_bsp_indices[j][i])
        
        for patch_face_index in range(width*height + height - 1):
            #end of row?
            if ((patch_face_index+1)%(width+1) == 0):
                continue
            i1 = patch_face_index + 1
            i2 = patch_face_index + width + 2
            i3 = patch_face_index + width + 1
            i4 = patch_face_index
            
            v1 = indicesPoints2[i1]
            v2 = indicesPoints2[i2]
            v3 = indicesPoints2[i3]
            v4 = indicesPoints2[i4]
            
            if (v1 < 0):
                model.vertices.append(patch[i1].position)
                model.normals.append(patch[i1].normal)
                model.vertex_bsp_indices.append(bspPoints2[i1])
                indicesPoints2[i1] = model.current_index
                model.current_index +=1
                
            if (v2 < 0):
                model.vertices.append(patch[i2].position)
                model.normals.append(patch[i2].normal)
                model.vertex_bsp_indices.append(bspPoints2[i2])
                indicesPoints2[i2] = model.current_index
                model.current_index +=1
                
            if (v3 < 0):
                model.vertices.append(patch[i3].position)
                model.normals.append(patch[i3].normal)
                model.vertex_bsp_indices.append(bspPoints2[i3])
                indicesPoints2[i3] = model.current_index
                model.current_index +=1
                
            if (v4 < 0):
                model.vertices.append(patch[i4].position)
                model.normals.append(patch[i4].normal)
                model.vertex_bsp_indices.append(bspPoints2[i4])
                indicesPoints2[i4] = model.current_index
                model.current_index +=1
                
            material_suffix = ""
            if face.lm_indexes[0] < 0:
                material_suffix = ".vertex"
            else:
                model.vertex_groups["Lightmapped"].add(indicesPoints2[i1])
                model.vertex_groups["Lightmapped"].add(indicesPoints2[i2])
                model.vertex_groups["Lightmapped"].add(indicesPoints2[i3])
                model.vertex_groups["Lightmapped"].add(indicesPoints2[i4])
            material_name = shaders_lump[face.texture].name + material_suffix
            
            if not (material_name in model.material_names):
                model.material_names.append(material_name)
            model.face_materials.append(model.material_names.index(material_name))
            
            model.face_vertices.append([indicesPoints2[i1], indicesPoints2[i2], indicesPoints2[i3], indicesPoints2[i4]])
            #model.vertex_groups["Patches"].add(indicesPoints2[i1])
            #model.vertex_groups["Patches"].add(indicesPoints2[i2])
            #model.vertex_groups["Patches"].add(indicesPoints2[i3])
            #model.vertex_groups["Patches"].add(indicesPoints2[i4])
            model.face_tcs.append([patch[i1].texcoord, patch[i2].texcoord, patch[i3].texcoord, patch[i4].texcoord])
            
            model.face_lm1_tcs.append([
            pack_lm_tc(patch[i1].lm1coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
            pack_lm_tc(patch[i2].lm1coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
            pack_lm_tc(patch[i3].lm1coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
            pack_lm_tc(patch[i4].lm1coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size)
            ])
            model.face_vert_color.append([patch[i1].color1, patch[i2].color1, patch[i3].color1, patch[i4].color1])
            
            if model.lightmaps > 1:
                model.face_lm2_tcs.append([
                pack_lm_tc(patch[i1].lm2coord, face.lm_indexes[1], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i2].lm2coord, face.lm_indexes[1], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i3].lm2coord, face.lm_indexes[1], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i4].lm2coord, face.lm_indexes[1], model.lightmap_size, import_settings.packed_lightmap_size)
                ])
                
                model.face_lm3_tcs.append([
                pack_lm_tc(patch[i1].lm3coord, face.lm_indexes[2], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i2].lm3coord, face.lm_indexes[2], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i3].lm3coord, face.lm_indexes[2], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i4].lm3coord, face.lm_indexes[2], model.lightmap_size, import_settings.packed_lightmap_size)
                ])
                        
                model.face_lm4_tcs.append([
                pack_lm_tc(patch[i1].lm4coord, face.lm_indexes[3], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i2].lm4coord, face.lm_indexes[3], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i3].lm4coord, face.lm_indexes[3], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i4].lm4coord, face.lm_indexes[3], model.lightmap_size, import_settings.packed_lightmap_size)
                ])
                    
                model.face_vert_color2.append([patch[i1].color2, patch[i2].color2, patch[i3].color2, patch[i4].color2])
                model.face_vert_color3.append([patch[i1].color3, patch[i2].color3, patch[i3].color3, patch[i4].color3])
                model.face_vert_color4.append([patch[i1].color4, patch[i2].color4, patch[i3].color4, patch[i4].color4])
            
            alphas = []
            alphas.append([patch[i1].color1[3],patch[i1].color1[3],patch[i1].color1[3],patch[i1].color1[3]])
            alphas.append([patch[i2].color1[3],patch[i2].color1[3],patch[i2].color1[3],patch[i2].color1[3]])
            alphas.append([patch[i3].color1[3],patch[i3].color1[3],patch[i3].color1[3],patch[i3].color1[3]])
            alphas.append([patch[i4].color1[3],patch[i4].color1[3],patch[i4].color1[3],patch[i4].color1[3]])
                    
            model.face_vert_alpha.append(alphas)
            
    def parse_brush(model, bsp, brush_id, import_settings):
        brush = bsp.lumps["brushes"].data[brush_id]
        shader = bsp.lumps["shaders"].data[brush.texture].name + ".brush"
        if not (shader in model.material_names):
            model.material_names.append(shader)
            
        brush_shader_id = model.material_names.index(shader)
            
        planes = []
        brush_materials = []
        for side in range(brush.n_brushsides):
            brushside = bsp.lumps["brushsides"].data[brush.brushside + side]
            plane = bsp.lumps["planes"].data[brushside.plane]
            
            normal = mathutils.Vector(plane.normal)
            position = normal * plane.distance
            shader = bsp.lumps["shaders"].data[brushside.texture].name + ".brush"
            
            if not (shader in model.material_names):
                model.material_names.append(shader)
            
            if not (shader in brush_materials):
                brush_materials.append(shader)
                
            mat_id = brush_materials.index(shader)
            planes.append([position, normal, mat_id])
            
        me = bpy.data.meshes.new("Brush " + str(brush_id).zfill(4))
        for texture_instance in brush_materials:
            mat = bpy.data.materials.get(texture_instance)
            if (mat == None):
                mat = bpy.data.materials.new(name=texture_instance)
            me.materials.append(mat)
            
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.create_cube(bm, size=65536, calc_uvs=True)
        uv_layer = bm.loops.layers.uv.verify()
        #bmesh bisect
        #face from bisect + assign shader
        for plane in planes:
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            vert_dict = bmesh.ops.bisect_plane(bm, geom = geom, dist = 0.1, plane_co = plane[0], plane_no = plane[1], clear_outer = True)
            bm_faces = bmesh.ops.contextual_create(bm, geom=vert_dict["geom_cut"], mat_nr=plane[2], use_smooth=False)["faces"]
            #if mat_nr would actually work, this wouldnt be needed :/
            for f in bm_faces:
                f.material_index = plane[2]
        
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        bm.verts.sort()
        
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        bm.faces.sort()
        bm.to_mesh(me)
        
        if import_settings.preset == "BRUSHES":
            collection = bpy.data.collections.get("Brushes")
            if collection == None:
                collection = bpy.data.collections.new("Brushes")
                bpy.context.scene.collection.children.link(collection)
            
            obj = bpy.data.objects.new("Brush " + str(brush_id).zfill(4), me)
            obj.cycles_visibility.camera = False
            #obj.cycles_visibility.diffuse = False
            obj.cycles_visibility.glossy = False
            obj.cycles_visibility.transmission = False
            obj.cycles_visibility.scatter = False
            bpy.data.collections["Brushes"].objects.link(obj)
            return
        
        vert_mapping = [-2 for i in range(len(bm.verts))]
        for vert in bm.verts:
            vert_mapping[vert.index] = model.current_index
            model.vertices.append(vert.co.copy())
            model.normals.append(vert.normal.copy())
            model.vertex_bsp_indices.append(-999)
            model.current_index += 1
        
        for face in bm.faces:
            indices = []
            tcs = []
            lmtcs = []
            colors = []
        
            for vert, loop in zip(face.verts, face.loops):
                indices.append(vert_mapping[vert.index])
                tcs.append(loop[uv_layer].uv.copy())
                lmtcs.append([0.0, 0.0])
                colors.append([0.4, 0.4, 0.4, 1.0])
                
            material_index = brush_shader_id
                
            model.face_materials.append(material_index)
            model.face_vertices.append(indices)
            model.face_tcs.append(tcs)
            model.face_lm1_tcs.append(lmtcs)
            model.face_vert_color.append(colors)
            model.face_vert_alpha.append(colors)
            if model.lightmaps > 1:
                model.face_lm2_tcs.append(lmtcs)
                model.face_lm3_tcs.append(lmtcs)
                model.face_lm4_tcs.append(lmtcs)
                model.face_vert_color2.append(colors)
                model.face_vert_color3.append(colors)
                model.face_vert_color4.append(colors)
        bm.free()
            
    def get_bsp_model(model, bsp, id, import_settings):
        #meh.... ugly fuck
        if bsp.lightmaps != model.lightmaps:
            model.lightmaps = bsp.lightmaps
            model.vertex_class = BSP.vertex_ibsp
        
        model.lightmap_size = bsp.lightmap_size[0]
        model.index_mapping = [-2 for i in range(int(bsp.lumps["drawverts"].count))]
            
        current_model = bsp.lumps["models"].data[id]
                    
        if import_settings.preset == "BRUSHES":
            model_brush = current_model.brush
            for index in range(current_model.n_brushes):
                brush_id = model_brush + index
                model.parse_brush(bsp, brush_id, import_settings)
        else:
            model_face = current_model.face
            for index in range(current_model.n_faces):
                face = bsp.lumps["surfaces"].data[model_face + index]
                #surface or mesh
                if (face.type == 1 or face.type == 3):
                    model.parse_bsp_surface(bsp, face, bsp.lumps["shaders"].data, import_settings)
                #patches
                if (face.type == 2):
                    model.parse_patch_surface(bsp, face, bsp.lumps["shaders"].data, import_settings)
                    
            if import_settings.preset == 'EDITING':
                if current_model.n_faces < 1:
                    model_brush = current_model.brush
                    for index in range(current_model.n_brushes):
                        brush_id = model_brush + index
                        model.parse_brush(bsp, brush_id, import_settings)

    def fill_bsp_data(model, bsp, import_settings):
        #meh.... ugly fuck
        if bsp.lightmaps != model.lightmaps:
            model.lightmaps = bsp.lightmaps
            model.vertex_class = BSP.vertex_ibsp
            
        model.lightmap_size = bsp.lightmap_size[0]
        
        for vertex_instance in bsp.lumps["drawverts"].data:
            model.vertices.append(vertex_instance.position)
            model.normals.append(vertex_instance.normal)
            model.vertex_bsp_indices.append(model.current_index)
            model.current_index+=1
            
        for index_instance in bsp.lumps["drawindexes"].data:
            model.indices.append(index_instance.offset)
            
        for model_instance in bsp.lumps["models"].data:
            if model.current_sub_model == 0:
                model.current_sub_model += 1
                continue
            
            model_face = model_instance.face
            indices = set()
            for index in range(model_instance.n_faces):
                face = bsp.lumps["surfaces"].data[model_face + index]
                face_index = face.index
                for i in range(int(face.n_indexes)):
                    indices.add(face.vertex + model.indices[face_index + i])
            if len(indices) > 0:
                model.vertex_groups["*"+str(model.current_sub_model)] = indices
            model.current_sub_model += 1
            
        for face_instance in bsp.lumps["surfaces"].data:
            #surface or mesh
            if (face_instance.type == 1 or face_instance.type == 3):
                model.parse_bsp_surface(bsp.lumps["drawverts"].data, face_instance, bsp.lumps["shaders"].data, import_settings)
                
            #patches
            if (face_instance.type == 2):
                model.parse_patch_surface(bsp.lumps["drawverts"].data, face_instance, bsp.lumps["shaders"].data, import_settings)
