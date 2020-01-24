#----------------------------------------------------------------------------#
#TODO:  refactor loading bsp files and md3 files, right now its a mess o.O
#TODO:  build patches via c library for speed?
#----------------------------------------------------------------------------#

if "struct" not in locals():
    import struct
    
if "BspClasses" in locals():
    import imp
    imp.reload( BspClasses )
else:
    from . import BspClasses as BSP
    
if "os" not in locals():
    import os
    
import bpy
from math import floor, ceil, pi, sin, cos
import mathutils
            
def create_white_image():
    image = bpy.data.images.new("$whiteimage", width=8, height=8)
    pixels = []
    for pixel in range(64):
        pixels.append(1.0)
        pixels.append(1.0)
        pixels.append(1.0)
        pixels.append(1.0)
    image.pixels = pixels

def pack_lightmaps(bsp, import_settings):
    use_internal_lightmaps = True
    lightmaps = []
    n_lightmaps = 0
    color_scale = 1.0
    color_components = 4
    try:
        path = bsp.bsp_path[:-len(".bsp")] + "\\"
        lm_files = os.listdir(path)
        lm_list = [path + file_name
                    for file_name in lm_files
                    if file_name.lower().startswith('lm_') and file_name.lower().endswith('.tga')]
        lightmap_size = 0
        for lm in lm_list:
            image = bpy.data.images.load(lm, check_existing=True)
            working_pixels = list(image.pixels[:])
            pixels = []
            for y in range(image.size[1]):
                for x in range(image.size[0]):
                    id = floor(x + image.size[1] - (y * image.size[1]))
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
        lightmaps = []
        #assume square lightmaps
        lightmap_size = bsp.lightmap_size[0]
        for lm in bsp.lumps["lightmaps"].data:
            lightmaps.append(lm.map)
        n_lightmaps = bsp.lumps["lightmaps"].count
        color_scale = 255.0
        color_components = 3
    
    force_vertex_lighting = False
    if lightmap_size == 0:
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
        
    if force_vertex_lighting == True:
        return
        
    packed_lm_size = import_settings.packed_lightmap_size
        
    #create dummy image
    image = bpy.data.images.new("$lightmap", width=packed_lm_size, height=packed_lm_size)
    
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
    image.pixels = pixels
    
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
                
    lightgrid_dimensions = [ floor((maxs[0] - lightgrid_origin[0]) / bsp.lightgrid_size[0] + 1),
                             floor((maxs[1] - lightgrid_origin[1]) / bsp.lightgrid_size[1] + 1),
                             floor((maxs[2] - lightgrid_origin[2]) / bsp.lightgrid_size[2] + 1) ]
                             
    bsp.lightgrid_inverse_dim = [   1.0 / lightgrid_dimensions[0],
                                    1.0 / (lightgrid_dimensions[1]*lightgrid_dimensions[2]),
                                    1.0 / lightgrid_dimensions[2] ]
                                    
    bsp.lightgrid_z_step = 1.0 / lightgrid_dimensions[2]
    
    a1_pixels = []
    a2_pixels = []
    a3_pixels = []
    a4_pixels = []
    d1_pixels = []
    d2_pixels = []
    d3_pixels = []
    d4_pixels = []
    l_pixels = []
    
    num_elements = lightgrid_dimensions[0] * lightgrid_dimensions[1] * lightgrid_dimensions[2]
    
    for pixel in range(int(lightgrid_dimensions[0]*lightgrid_dimensions[1]*lightgrid_dimensions[2])):
        
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
    
    ambient1 = bpy.data.images.new("$lightgrid_ambient1", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
    ambient1.pixels = a1_pixels
    
    direct1 = bpy.data.images.new("$lightgrid_direct1", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
    direct1.pixels = d1_pixels
    
    if bsp.lightmaps > 1:
        ambient2 = bpy.data.images.new("$lightgrid_ambient2", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
        ambient3 = bpy.data.images.new("$lightgrid_ambient3", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
        ambient4 = bpy.data.images.new("$lightgrid_ambient4", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
        ambient2.pixels = a2_pixels
        ambient3.pixels = a3_pixels
        ambient4.pixels = a4_pixels
        direct2 = bpy.data.images.new("$lightgrid_direct2", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
        direct3 = bpy.data.images.new("$lightgrid_direct3", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
        direct4 = bpy.data.images.new("$lightgrid_direct4", width=lightgrid_dimensions[0], height=lightgrid_dimensions[1]*lightgrid_dimensions[2])
        direct2.pixels = d2_pixels
        direct3.pixels = d3_pixels
        direct4.pixels = d4_pixels
    
    lightvec = bpy.data.images.new( "$lightgrid_vector", 
                                    width=lightgrid_dimensions[0], 
                                    height=lightgrid_dimensions[1]*lightgrid_dimensions[2],
                                    float_buffer=True)
    lightvec.colorspace_settings.name = "Non-Color"
    
    lightvec.pixels = l_pixels
        
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
    
    vertexArray.append((vertex1.normal[0] + vertex2.normal[0])/2.0)
    vertexArray.append((vertex1.normal[1] + vertex2.normal[1])/2.0)
    vertexArray.append((vertex1.normal[2] + vertex2.normal[2])/2.0)
    
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
        model.patch_vertices = set()
        model.material_names = []
        model.vertex_class = BSP.vertex_rbsp
        model.lightmaps = 4
        model.lightmap_size = 128
        
    def parse_bsp_surface(model, drawverts_lump, face, model_indices, shaders_lump, import_settings):
        index = face.index
        #bsp only stores triangles, so there are n_indexes/3 trinangles in this face
        for i in range(int(face.n_indexes / 3)):
            indices = []
            indices.append(face.vertex + model_indices[index + 0])
            indices.append(face.vertex + model_indices[index + 1])
            indices.append(face.vertex + model_indices[index + 2])
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
            for face_index in indices:
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
            
    def parse_patch_surface(model, drawverts_lump, face, model_indices, shaders_lump, index, import_settings):
        width = int(face.patch_width-1)
        height = int(face.patch_height-1)
                
        MAX_GRID_SIZE = 65
        
        ctrlPoints = [[0 for x in range(MAX_GRID_SIZE)] for y in range(MAX_GRID_SIZE)]
        indicesPoints = [[0 for x in range(MAX_GRID_SIZE)] for y in range(MAX_GRID_SIZE)]
        for i in range(face.patch_width):
            for j in range(face.patch_height):
                vertex = drawverts_lump[face.vertex + j*face.patch_width + i]
                ctrlPoints[j][i] = vertex
                indicesPoints[j][i] = face.vertex + j*face.patch_width + i
                
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
        
        #now smooth the rest of the points
        for i in range(width+1):
            for j in range(1, height, 2):
                prev = lerpVertices(ctrlPoints[j][i], ctrlPoints[j+1][i], model.vertex_class, model.lightmaps)
                next = lerpVertices(ctrlPoints[j][i], ctrlPoints[j-1][i], model.vertex_class, model.lightmaps)
                ctrlPoints[j][i] = lerpVertices(prev, next, model.vertex_class, model.lightmaps)
                indicesPoints[j][i] = -4;
                
        for j in range(height+1):
            for i in range(1, width, 2):
                prev = lerpVertices(ctrlPoints[j][i], ctrlPoints[j][i+1], model.vertex_class, model.lightmaps)
                next = lerpVertices(ctrlPoints[j][i], ctrlPoints[j][i-1], model.vertex_class, model.lightmaps)
                ctrlPoints[j][i] = lerpVertices(prev, next, model.vertex_class, model.lightmaps)
                indicesPoints[j][i] = -4;       
        
        indicesPoints2 = []
        patch = []
        for j in range(height+1):
            for i in range(width+1):
                patch.append(ctrlPoints[j][i])
                indicesPoints2.append(indicesPoints[j][i])
        
        for patch_face_index in range(width*height + height - 1):
            #end of row?
            if ((patch_face_index+1)%(width+1) == 0):
                continue
            i1 = patch_face_index + 1
            i2 = patch_face_index
            i3 = patch_face_index + width + 1
            i4 = patch_face_index + width + 2
            
            v1 = indicesPoints2[i1]
            v2 = indicesPoints2[i2]
            v3 = indicesPoints2[i3]
            v4 = indicesPoints2[i4]
            
            if (v1 < 0):
                model.vertices.append(patch[i1].position)
                model.normals.append(patch[i1].normal)
                model.vertex_bsp_indices.append(-1)
                indicesPoints2[i1] = index
                index+=1
                
            if (v2 < 0):
                model.vertices.append(patch[i2].position)
                model.normals.append(patch[i2].normal)
                model.vertex_bsp_indices.append(-1)
                indicesPoints2[i2] = index
                index+=1
                
            if (v3 < 0):
                model.vertices.append(patch[i3].position)
                model.normals.append(patch[i3].normal)
                model.vertex_bsp_indices.append(-1)
                indicesPoints2[i3] = index
                index+=1
                
            if (v4 < 0):
                model.vertices.append(patch[i4].position)
                model.normals.append(patch[i4].normal)
                model.vertex_bsp_indices.append(-1)
                indicesPoints2[i4] = index
                index+=1
                
            material_suffix = ""
            if face.lm_indexes[0] < 0:
                material_suffix = ".vertex"
            material_name = shaders_lump[face.texture].name + material_suffix
            
            if not (material_name in model.material_names):
                model.material_names.append(material_name)
            model.face_materials.append(model.material_names.index(material_name))
            
            model.face_vertices.append([indicesPoints2[i1], indicesPoints2[i2], indicesPoints2[i3], indicesPoints2[i4]])
            model.patch_vertices.add(indicesPoints2[i1])
            model.patch_vertices.add(indicesPoints2[i2])
            model.patch_vertices.add(indicesPoints2[i3])
            model.patch_vertices.add(indicesPoints2[i4])
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
                pack_lm_tc(patch[i1].lm2coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i2].lm2coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i3].lm2coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i4].lm2coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size)
                ])
                
                model.face_lm3_tcs.append([
                pack_lm_tc(patch[i1].lm3coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i2].lm3coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i3].lm3coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i4].lm3coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size)
                ])
                        
                model.face_lm4_tcs.append([
                pack_lm_tc(patch[i1].lm4coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i2].lm4coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i3].lm4coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size),
                pack_lm_tc(patch[i4].lm4coord, face.lm_indexes[0], model.lightmap_size, import_settings.packed_lightmap_size)
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
            
        return index
            
    def fill_bsp_data(model, bsp, import_settings):
        
        #meh.... ugly fuck
        if bsp.lightmaps != model.lightmaps:
            model.lightmaps = bsp.lightmaps
            model.lightmap_size = bsp.lightmap_size[0]
            model.vertex_class = BSP.vertex_ibsp
        
        index = 0
        for vertex_instance in bsp.lumps["drawverts"].data:
            model.vertices.append(vertex_instance.position)
            model.normals.append(vertex_instance.normal)
            model.vertex_bsp_indices.append(index)
            index+=1
            
        for index_instance in bsp.lumps["drawindexes"].data:
            model.indices.append(index_instance.offset)
            
        for face_instance in bsp.lumps["surfaces"].data:
            #surface or mesh
            if (face_instance.type == 1 or face_instance.type == 3):
                model.parse_bsp_surface(bsp.lumps["drawverts"].data, face_instance, model.indices, bsp.lumps["shaders"].data, import_settings)
                
            #patches
            if (face_instance.type == 2):
                index = model.parse_patch_surface(bsp.lumps["drawverts"].data, face_instance, model.indices, bsp.lumps["shaders"].data, index, import_settings)
