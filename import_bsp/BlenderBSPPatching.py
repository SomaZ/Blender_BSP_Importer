# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import numpy
import os
from .idtech3lib import Helpers
from . import QuakeLight

class Patch_settings():
    def __init__(self):
        self.patch_normals = False
        self.patch_vertex_colors = False
        self.patch_static_lighting = False
        self.patch_lightmaps = False
        self.patch_lightgrid = False
        self.patch_tcs = False
        self.external_lighting = False
        self.hdr_lighting = False

class Light_settings():
    def __init__(self):
        self.gamma = 1.0
        self.exposure = 0.0
        self.sRGB_transform = True
        self.overbright_bits = 0
        self.deluxe_mapping = False

def unpack_bsp_vert_lm_tc(bsp_vert, lightmap_size, packed_lightmap_size, n_lightmaps):
    Helpers.unpack_lm_tc(bsp_vert.lm1coord,
                         lightmap_size,
                         packed_lightmap_size)
    bsp_vert.lm1coord[1] = 1.0 - bsp_vert.lm1coord[1]
    if n_lightmaps == 4:
        Helpers.unpack_lm_tc(
            bsp_vert.lm2coord,
            lightmap_size,
            packed_lightmap_size)
        bsp_vert.lm2coord[1] = 1.0 - bsp_vert.lm2coord[1]
        Helpers.unpack_lm_tc(
            bsp_vert.lm3coord,
            lightmap_size,
            packed_lightmap_size)
        bsp_vert.lm3coord[1] = 1.0 - bsp_vert.lm3coord[1]
        Helpers.unpack_lm_tc(
            bsp_vert.lm4coord,
            lightmap_size,
            packed_lightmap_size)
        bsp_vert.lm4coord[1] = 1.0 - bsp_vert.lm4coord[1]

def patch_static_lighting(bsp, bsp_indices, mesh, lightmapped_vertices, light_settings) -> bool:

    deluxemapping = light_settings.deluxe_mapping and bpy.data.images.get("$deluxemap_bake")
    lm_id_mul = 2 if deluxemapping else 1

    # Set lightmap tcs
    patched_tcs = set()
    for poly in mesh.polygons:
        for vertex, loop in zip(poly.vertices, poly.loop_indices):
            bsp_vert_index = bsp_indices.data[vertex].value
            if bsp_vert_index < 0:
                continue
            patched_tcs.add(bsp_vert_index)
            bsp_vert = bsp.lumps["drawverts"][bsp_vert_index]
            bsp_vert.lm1coord[:] = (mesh.uv_layers["LightmapUV"].data[loop].uv)
            bsp_vert.lm1coord[0] = min(1.0, max(0.0, bsp_vert.lm1coord[0]))
            bsp_vert.lm1coord[1] = min(1.0, max(0.0, bsp_vert.lm1coord[1]))
            if bsp.lightmaps != 4:
                if bsp.lightmaps != 1:
                    raise Exception("BSP Format is not supported for patching. "
                                    "Lightstyles is assumed to have 4 channels.")
                continue
            bsp_vert.lm2coord[:] = (mesh.uv_layers["LightmapUV2"].data[loop].uv)
            bsp_vert.lm2coord[0] = min(1.0, max(0.0, bsp_vert.lm2coord[0]))
            bsp_vert.lm2coord[1] = min(1.0, max(0.0, bsp_vert.lm2coord[1]))
            bsp_vert.lm3coord[:] = (mesh.uv_layers["LightmapUV3"].data[loop].uv)
            bsp_vert.lm3coord[0] = min(1.0, max(0.0, bsp_vert.lm3coord[0]))
            bsp_vert.lm3coord[1] = min(1.0, max(0.0, bsp_vert.lm3coord[1]))
            bsp_vert.lm4coord[:] = (mesh.uv_layers["LightmapUV4"].data[loop].uv)
            bsp_vert.lm4coord[0] = min(1.0, max(0.0, bsp_vert.lm4coord[0]))
            bsp_vert.lm4coord[1] = min(1.0, max(0.0, bsp_vert.lm4coord[1]))

    # Fixup patch lightmap tcs on patches and find patched surfaces
    patched_surfaces = []
    for bsp_surf in bsp.lumps["surfaces"]:
        if bsp_surf.type != 2:
            bsp_vert_index = (
                bsp_surf.vertex + bsp.lumps["drawindexes"][bsp_surf.index].offset)
            if bsp_vert_index in patched_tcs:
                patched_surfaces.append(bsp_surf)
            continue

        if bsp_surf.vertex not in patched_tcs:
            continue

        patched_surfaces.append(bsp_surf)

        width = int(bsp_surf.patch_width-1)
        height = int(bsp_surf.patch_height-1)
        ctrlPoints = [
            [0 for x in range(bsp_surf.patch_width)]
            for y in range(bsp_surf.patch_height)]
        for i in range(bsp_surf.patch_width):
            for j in range(bsp_surf.patch_height):
                bsp_vert_index = bsp_surf.vertex + j * bsp_surf.patch_width + i
                ctrlPoints[j][i] = (bsp.lumps["drawverts"][bsp_vert_index])
        for i in range(width+1):
            for j in range(1, height, 2):
                ctrlPoints[j][i].lm1coord[0] = (
                    4.0 * ctrlPoints[j][i].lm1coord[0]
                    - ctrlPoints[j+1][i].lm1coord[0]
                    - ctrlPoints[j-1][i].lm1coord[0]) * 0.5
                ctrlPoints[j][i].lm1coord[1] = (
                    4.0 * ctrlPoints[j][i].lm1coord[1]
                    - ctrlPoints[j+1][i].lm1coord[1]
                    - ctrlPoints[j-1][i].lm1coord[1]) * 0.5
                if bsp.lightmaps == 4:
                    ctrlPoints[j][i].lm2coord[0] = (
                        4.0 * ctrlPoints[j][i].lm2coord[0]
                        - ctrlPoints[j+1][i].lm2coord[0]
                        - ctrlPoints[j-1][i].lm2coord[0]) * 0.5
                    ctrlPoints[j][i].lm2coord[1] = (
                        4.0 * ctrlPoints[j][i].lm2coord[1]
                        - ctrlPoints[j+1][i].lm2coord[1]
                        - ctrlPoints[j-1][i].lm2coord[1]) * 0.5
                    ctrlPoints[j][i].lm3coord[0] = (
                        4.0 * ctrlPoints[j][i].lm3coord[0]
                        - ctrlPoints[j+1][i].lm3coord[0]
                        - ctrlPoints[j-1][i].lm3coord[0]) * 0.5
                    ctrlPoints[j][i].lm3coord[1] = (
                        4.0 * ctrlPoints[j][i].lm3coord[1]
                        - ctrlPoints[j+1][i].lm3coord[1]
                        - ctrlPoints[j-1][i].lm3coord[1]) * 0.5
                    ctrlPoints[j][i].lm4coord[0] = (
                        4.0 * ctrlPoints[j][i].lm4coord[0]
                        - ctrlPoints[j+1][i].lm4coord[0]
                        - ctrlPoints[j-1][i].lm4coord[0]) * 0.5
                    ctrlPoints[j][i].lm4coord[1] = (
                        4.0 * ctrlPoints[j][i].lm4coord[1]
                        - ctrlPoints[j+1][i].lm4coord[1]
                        - ctrlPoints[j-1][i].lm4coord[1]) * 0.5
        for j in range(height+1):
            for i in range(1, width, 2):
                ctrlPoints[j][i].lm1coord[0] = (
                    4.0 * ctrlPoints[j][i].lm1coord[0]
                    - ctrlPoints[j][i+1].lm1coord[0]
                    - ctrlPoints[j][i-1].lm1coord[0]) * 0.5
                ctrlPoints[j][i].lm1coord[1] = (
                    4.0 * ctrlPoints[j][i].lm1coord[1]
                    - ctrlPoints[j][i+1].lm1coord[1]
                    - ctrlPoints[j][i-1].lm1coord[1]) * 0.5
                if bsp.lightmaps == 4:
                    ctrlPoints[j][i].lm2coord[0] = (
                        4.0 * ctrlPoints[j][i].lm2coord[0]
                        - ctrlPoints[j][i+1].lm2coord[0]
                        - ctrlPoints[j][i-1].lm2coord[0]) * 0.5
                    ctrlPoints[j][i].lm2coord[1] = (
                        4.0 * ctrlPoints[j][i].lm2coord[1]
                        - ctrlPoints[j][i+1].lm2coord[1]
                        - ctrlPoints[j][i-1].lm2coord[1]) * 0.5
                    ctrlPoints[j][i].lm3coord[0] = (
                        4.0 * ctrlPoints[j][i].lm3coord[0]
                        - ctrlPoints[j][i+1].lm3coord[0]
                        - ctrlPoints[j][i-1].lm3coord[0]) * 0.5
                    ctrlPoints[j][i].lm3coord[1] = (
                        4.0 * ctrlPoints[j][i].lm3coord[1]
                        - ctrlPoints[j][i+1].lm3coord[1]
                        - ctrlPoints[j][i-1].lm3coord[1]) * 0.5
                    ctrlPoints[j][i].lm4coord[0] = (
                        4.0 * ctrlPoints[j][i].lm4coord[0]
                        - ctrlPoints[j][i+1].lm4coord[0]
                        - ctrlPoints[j][i-1].lm4coord[0]) * 0.5
                    ctrlPoints[j][i].lm4coord[1] = (
                        4.0 * ctrlPoints[j][i].lm4coord[1]
                        - ctrlPoints[j][i+1].lm4coord[1]
                        - ctrlPoints[j][i-1].lm4coord[1]) * 0.5

    # Bring back tcs back to 0-1 range instead of the atlas coordinates
    lightmap_size = bsp.lightmap_size
    packed_lightmap_size = [
        lightmap_size[0] *
        bpy.context.scene.id_tech_3_lightmaps_per_column,
        lightmap_size[1] *
        bpy.context.scene.id_tech_3_lightmaps_per_row]
    
    # Find the lightmap ids from patched tcs
    # then set the surfaces lightmap ids
    # and finally unpack the tcs if atlased
    unpacked_vertices = set()
    for bsp_surf in patched_surfaces:
        lm_id = -3
        lm2_id = -3
        lm3_id = -3
        lm4_id = -3
        if bsp_surf.type != 2:
            for i in range(int(bsp_surf.n_indexes)):
                bsp_vert_index = (
                    bsp_surf.vertex +
                    bsp.lumps["drawindexes"]
                    [bsp_surf.index + i].offset)
                bsp_vert = (bsp.lumps["drawverts"][bsp_vert_index])
                
                if not lightmapped_vertices[bsp_vert_index]:
                    c_lm_id = -3
                else:
                    c_lm_id = Helpers.get_lm_id(bsp_vert.lm1coord,
                                                lightmap_size,
                                                packed_lightmap_size)
                if i == 0:
                    lm_id = c_lm_id
                if lm_id != c_lm_id:
                    lm_id = -3
                    if bsp.lightmaps == 4:
                        lm2_id = -3
                        lm3_id = -3
                        lm4_id = -3
                    print("Warning: Surface found "
                          "with multiple lightmap assignments "
                          "which is not supported! Surface will "
                          "be stored as vertex lit!")
                    break
                if bsp.lightmaps == 4 and lm_id != -3:
                    c_lm2_id = Helpers.get_lm_id(bsp_vert.lm2coord,
                                                 lightmap_size,
                                                 packed_lightmap_size)
                    c_lm3_id = Helpers.get_lm_id(bsp_vert.lm3coord,
                                                 lightmap_size,
                                                 packed_lightmap_size)
                    c_lm4_id = Helpers.get_lm_id(bsp_vert.lm4coord,
                                                 lightmap_size,
                                                 packed_lightmap_size)
                    if i == 0:
                        lm2_id = c_lm2_id
                        lm3_id = c_lm3_id
                        lm4_id = c_lm4_id
                    if lm2_id != c_lm2_id:
                        lm2_id = -3
                    if lm3_id != c_lm3_id:
                        lm3_id = -3
                    if lm4_id != c_lm4_id:
                        lm4_id = -3
        else:
            for i in range(bsp_surf.patch_width):
                for j in range(bsp_surf.patch_height):
                    bsp_vert_index = (
                        bsp_surf.vertex+j*bsp_surf.patch_width+i)
                    bsp_vert = (bsp.lumps["drawverts"][bsp_vert_index])

                    if not lightmapped_vertices[bsp_vert_index]:
                        c_lm_id = -3
                    else:
                        c_lm_id = Helpers.get_lm_id(bsp_vert.lm1coord,
                                                    lightmap_size,
                                                    packed_lightmap_size)
                    if i == 0 and j == 0:
                        lm_id = c_lm_id
                    if lm_id != c_lm_id:
                        lm_id = -3
                        if bsp.lightmaps == 4:
                            lm2_id = -3
                            lm3_id = -3
                            lm4_id = -3
                        print("Warning: Surface found "
                            "with multiple lightmap assignments "
                            "which is not supported! Surface will "
                            "be stored as vertex lit!")
                        break
                    if bsp.lightmaps == 4 and lm_id != -3:
                        c_lm2_id = Helpers.get_lm_id(bsp_vert.lm2coord,
                                                    lightmap_size,
                                                    packed_lightmap_size)
                        c_lm3_id = Helpers.get_lm_id(bsp_vert.lm3coord,
                                                    lightmap_size,
                                                    packed_lightmap_size)
                        c_lm4_id = Helpers.get_lm_id(bsp_vert.lm4coord,
                                                    lightmap_size,
                                                    packed_lightmap_size)
                        if i == 0 and j == 0:
                            lm2_id = c_lm2_id
                            lm3_id = c_lm3_id
                            lm4_id = c_lm4_id
                        if lm2_id != c_lm2_id:
                            lm2_id = -3
                        if lm3_id != c_lm3_id:
                            lm3_id = -3
                        if lm4_id != c_lm4_id:
                            lm4_id = -3

        # Set the surfaces lightmap indices
        if bsp.lightmaps == 4:
            bsp_surf.lm_indexes[0] = max(-3, lm_id * lm_id_mul)
            bsp_surf.lm_indexes[1] = max(-3, lm2_id * lm_id_mul)
            bsp_surf.lm_indexes[2] = max(-3, lm3_id * lm_id_mul)
            bsp_surf.lm_indexes[3] = max(-3, lm4_id * lm_id_mul)
        else:
            bsp_surf.lm_indexes = max(-3, lm_id * lm_id_mul)
        
        # Finally unpack the tcs
        if bsp.lightmaps == 4 and bsp_surf.lm_indexes[0] == -3:
            continue
        elif bsp.lightmaps == 1 and bsp_surf.lm_indexes == -3:
            continue
        if bsp_surf.type != 2:
            for i in range(int(bsp_surf.n_indexes)):
                bsp_vert_index = (
                    bsp_surf.vertex +
                    bsp.lumps["drawindexes"]
                    [bsp_surf.index + i].offset)
                if bsp_vert_index in unpacked_vertices:
                    continue
                bsp_vert = (bsp.lumps["drawverts"][bsp_vert_index])
                unpack_bsp_vert_lm_tc(bsp_vert,
                                      lightmap_size,
                                      packed_lightmap_size,
                                      bsp.lightmaps)
                unpacked_vertices.add(bsp_vert_index)
        else:
            for i in range(bsp_surf.patch_width):
                for j in range(bsp_surf.patch_height):
                    bsp_vert_index = (
                        bsp_surf.vertex+j*bsp_surf.patch_width+i)
                    if bsp_vert_index in unpacked_vertices:
                        continue
                    bsp_vert = (bsp.lumps["drawverts"][bsp_vert_index])
                    unpack_bsp_vert_lm_tc(bsp_vert,
                                          lightmap_size,
                                          packed_lightmap_size,
                                          bsp.lightmaps)
                    unpacked_vertices.add(bsp_vert_index)

    return True

def patch_tcs(bsp, bsp_indices, mesh) -> bool:
    # Set tcs
    patched_tcs = set()
    for poly in mesh.polygons:
        for vertex, loop in zip(poly.vertices, poly.loop_indices):
            bsp_vert_index = bsp_indices.data[vertex].value
            if bsp_vert_index < 0:
                continue
            patched_tcs.add(bsp_vert_index)
            bsp_vert = bsp.lumps["drawverts"][bsp_vert_index]
            bsp_vert.texcoord[:] = (mesh.uv_layers["UVMap"].data[loop].uv)
            bsp_vert.texcoord[1] = 1.0 - bsp_vert.texcoord[1]
    # Fix smoothing of patch mesh tcs
    for bsp_surf in bsp.lumps["surfaces"]:
        if bsp_surf.type != 2:
            continue
        if bsp_surf.vertex not in patched_tcs:
            continue
        width = int(bsp_surf.patch_width-1)
        height = int(bsp_surf.patch_height-1)
        ctrlPoints = [
            [0 for x in range(bsp_surf.patch_width)]
            for y in range(bsp_surf.patch_height)]
        for i in range(bsp_surf.patch_width):
            for j in range(bsp_surf.patch_height):
                bsp_vert_index = bsp_surf.vertex + j * bsp_surf.patch_width + i
                ctrlPoints[j][i] = (bsp.lumps["drawverts"][bsp_vert_index])
        for i in range(width+1):
            for j in range(1, height, 2):
                ctrlPoints[j][i].texcoord[0] = (
                    4.0 * ctrlPoints[j][i].texcoord[0]
                    - ctrlPoints[j+1][i].texcoord[0]
                    - ctrlPoints[j-1][i].texcoord[0]) * 0.5
                ctrlPoints[j][i].texcoord[1] = (
                    4.0 * ctrlPoints[j][i].texcoord[1]
                    - ctrlPoints[j+1][i].texcoord[1]
                    - ctrlPoints[j-1][i].texcoord[1]) * 0.5
        for j in range(height+1):
            for i in range(1, width, 2):
                ctrlPoints[j][i].texcoord[0] = (
                    4.0 * ctrlPoints[j][i].texcoord[0]
                    - ctrlPoints[j][i+1].texcoord[0]
                    - ctrlPoints[j][i-1].texcoord[0]) * 0.5
                ctrlPoints[j][i].texcoord[1] = (
                    4.0 * ctrlPoints[j][i].texcoord[1]
                    - ctrlPoints[j][i+1].texcoord[1]
                    - ctrlPoints[j][i-1].texcoord[1]) * 0.5
    return True

def patch_normals(bsp, bsp_indices, mesh) -> bool:
    for poly in mesh.polygons:
        for vertex, loop in zip(poly.vertices, poly.loop_indices):
            bsp_vert_index = bsp_indices.data[vertex].value
            if bsp_vert_index < 0:
                continue
            bsp_vert = bsp.lumps["drawverts"][bsp_vert_index]
            bsp_vert.normal[:] = mesh.loops[loop].normal.copy()
    return True


def save_image_file(file_name, lm_size, pixels, hdr: bool) -> bool:
    file_type = "HDR" if hdr else "TARGA_RAW"
    file_ext = ".hdr" if hdr else ".tga"
    color_space = 'Non-Color' if hdr else "sRGB"
    image_settings = bpy.context.scene.render.image_settings
    image_settings.file_format = file_type
    image_settings.color_depth = '32' if hdr else '8'
    image_settings.color_mode = 'RGB'
    img_name = "lm_export_buffer"
    image = bpy.data.images.get(img_name)
    if image is None:
        image = bpy.data.images.new(
            img_name,
            width=lm_size[0],
            height=lm_size[1],
            float_buffer=True)
        image.colorspace_settings.name = color_space
        image.file_format = file_type
    elif image.size[0] != lm_size[0] or image.size[1] != lm_size[1]:
        image.scale(lm_size[0], lm_size[1])
    
    image.filepath_raw = file_name + file_ext
    image.pixels = pixels
    image.save_render(image.filepath_raw, scene=bpy.context.scene)
    return True


def patch_lightmaps(bsp, patch_settings: Patch_settings, light_settings: Light_settings) -> bool:

    color_scale = 1.0 / (pow(2.0, float(light_settings.overbright_bits)))
    color_scale *= pow(2.0, light_settings.exposure)

    image = bpy.data.images.get("$lightmap_bake")
    if image is None:
        print("Could not find lightmap atlas")
        return False
    
    deluxemap_atlas = None
    deluxemap_pixels = None
    if light_settings.deluxe_mapping:
        deluxemap_atlas = bpy.data.images.get("$deluxemap_bake")
        if deluxemap_atlas:
            deluxemap_atlas.scale(image.size[0], image.size[1])
            deluxemap_pixels = numpy.array(deluxemap_atlas.pixels[:]).reshape(
                (image.size[0], image.size[1], 4))
    
    bsp_path = bsp.import_settings.file.replace("\\", "/").split(".")[0] + "/"
    if not os.path.exists(bsp_path):
        os.makedirs(bsp_path)

    if not patch_settings.external_lighting:
        bsp.lumps["lightmaps"].clear()

    num_rows = bpy.context.scene.id_tech_3_lightmaps_per_row
    num_columns = bpy.context.scene.id_tech_3_lightmaps_per_column

    export_width = image.size[0] // bpy.context.scene.id_tech_3_lightmaps_per_column
    export_height = image.size[1] // bpy.context.scene.id_tech_3_lightmaps_per_row
    export_length = export_width * export_height * 4
    atlas_pixels = numpy.array(image.pixels[:]).reshape(
        (image.size[0], image.size[1], 4))
    lightmap = 0

    for y in range(num_rows):
        for x in range(num_columns):
            start = (x * export_width, y * export_height)
            end = (start[0] + export_width, start[1] + export_height)
            cropped = atlas_pixels[start[1]:end[1], start[0]:end[0]]
            cropped_dlxm = None
            if deluxemap_pixels:
                cropped_dlxm = deluxemap_pixels[start[1]:end[1], start[0]:end[0]]

            # apply exposure and obb
            cropped *= color_scale
            cropped[:,:,3] = 1.0
            
            # write hdr version or hdrbspext
            if patch_settings.hdr_lighting:
                save_image_file(
                    "{}lm_{}".format(bsp_path, str(lightmap).zfill(4)),
                    [export_width, export_height],
                    cropped.reshape(export_length),
                    True)
                if deluxemap_pixels:
                    save_image_file(
                        "{}dm_{}".format(bsp_path, str(lightmap).zfill(4)),
                        [export_width, export_height],
                        cropped_dlxm.reshape(export_length),
                        False)
            
            # make sdr
            max_vs = numpy.max(cropped, axis=2, keepdims=True)
            sdr = numpy.where(max_vs > 1.0, cropped / max_vs, cropped)
            sdr[:, :, 3] = 1.0
            
            # apply gamma
            sdr = numpy.power(sdr, 1.0 / light_settings.gamma)
            
            # srgb transform
            if light_settings.sRGB_transform:
                sdr = numpy.where(
                    sdr <= 0.0031308,
                    sdr * 12.92,
                    1.055 * numpy.power(sdr, 1.0/2.4) - 0.055)

            # write external file
            if patch_settings.external_lighting:
                save_image_file(
                    "{}lm_{}".format(bsp_path, str(lightmap).zfill(4)),
                    [export_width, export_height],
                    sdr.reshape(export_length),
                    False)
                if deluxemap_pixels:
                    save_image_file(
                        "{}dm_{}".format(bsp_path, str(lightmap).zfill(4)),
                        [export_width, export_height],
                        cropped_dlxm.reshape(export_length),
                        False)
            # write to bsp
            else:
                bsp_lightmap = bsp.lump_info["lightmaps"]()
                bsp_lightmap.map[:] = (sdr[:, :, :3] * 255).astype(numpy.uint8).reshape(
                    export_width * export_height * 3)
                bsp.lumps["lightmaps"].append(bsp_lightmap)
                if deluxemap_pixels:
                    bsp_lightmap = bsp.lump_info["lightmaps"]()
                    bsp_lightmap.map[:] = (deluxemap_pixels[:, :, :3] * 255).astype(numpy.uint8).reshape(
                        export_width * export_height * 3)
                    bsp.lumps["lightmaps"].append(bsp_lightmap)

            lightmap += 1

    return True


def patch_bsp(bsp, objs, patch_settings: Patch_settings, light_settings: Light_settings) -> bool:

    meshes = [obj.to_mesh() for obj in objs]
    if bpy.app.version < (4, 1, 0):
        for mesh in meshes:
            mesh.calc_normals_split()

    num_bsp_verts = len(bsp.lumps["drawverts"])
    lightmapped_vertices = [False for _ in range(num_bsp_verts)]

    for obj, mesh in zip(objs, meshes):
        group_map = {group.name: group.index for group in obj.vertex_groups}
        if bpy.app.version >= (2, 91, 0):
            bsp_indices = mesh.attributes.get(
                "BSP_VERT_INDEX")
        else:
            bsp_indices = mesh.vertex_layers_int.get(
                "BSP_VERT_INDEX")
            
        if bsp_indices is None:
            continue

        # store all vertices that are lightmapped
        for index in [bsp_indices.data[vertex.index].value
                      for vertex in mesh.vertices
                      if group_map["Lightmapped"] in
                      [vg.group for vg in vertex.groups]]:
            if index >= 0:
                lightmapped_vertices[index] = True
        succ = True
        if patch_settings.patch_static_lighting:
            succ = patch_static_lighting(
                bsp, bsp_indices, mesh, lightmapped_vertices, light_settings)
            if not succ:
                print("Failed patching static_lighting", obj.name)
        if patch_settings.patch_vertex_colors:
            succ, message = QuakeLight.storeVertexColors(
                bsp, objs, patch_settings, light_settings)
            if not succ:
                print("Failed patching vertex colors", obj.name, message)
        if patch_settings.patch_lightmaps:
            succ = patch_lightmaps(bsp, patch_settings, light_settings)
            if not succ:
                print("Failed patching lightmaps", obj.name)
        if patch_settings.patch_lightgrid:
            succ, message = QuakeLight.storeLightgrid(bsp, patch_settings, light_settings)
            if not succ:
                print("Failed patching lightgrid", obj.name, message)
        if patch_settings.patch_normals:
            succ = patch_normals(bsp, bsp_indices, mesh)
            if not succ:
                print("Failed patching normals", obj.name)
        if patch_settings.patch_tcs:
            succ = patch_tcs(bsp, bsp_indices, mesh)
            if not succ:
                print("Failed patching tcs", obj.name)
        
        if not succ:
            print("Failed patching", obj.name)
            return False

    return True