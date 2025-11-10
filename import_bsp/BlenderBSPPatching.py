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
from .idtech3lib import Helpers
from . import QuakeLight

class Patch_settings():
    def __init__(self):
        self.patch_normals = False
        self.patch_static_lighting = False
        self.patch_lightgrid = False
        self.patch_tcs = False
        self.hdr_export = False

class Light_settings():
    def __init__(self):
        self.gamma = "1.0"
        self.overbright_bits = 0
        self.compensate = False
        self.hdr_export = False

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

def patch_static_lighting(bsp, bsp_indices, mesh, lightmapped_vertices) -> bool:
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
    patched_surfaces = set()
    for bsp_surf in bsp.lumps["surfaces"]:
        if bsp_surf.type != 2:
            bsp_vert_index = (
                bsp_surf.vertex + bsp.lumps["drawindexes"][bsp_surf.index].offset)
            if bsp_vert_index in patched_tcs:
                patched_surfaces.add(bsp_surf)
            continue

        if bsp_surf.vertex not in patched_tcs:
            continue

        patched_surfaces.add(bsp_surf)

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
                
                if bsp_vert_index not in lightmapped_vertices:
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
        else:
            for i in range(bsp_surf.patch_width):
                for j in range(bsp_surf.patch_height):
                    bsp_vert_index = (
                        bsp_surf.vertex+j*bsp_surf.patch_width+i)
                    bsp_vert = (bsp.lumps["drawverts"][bsp_vert_index])

                    if bsp_vert_index not in lightmapped_vertices:
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
            bsp_surf.lm_indexes[0] = lm_id
            bsp_surf.lm_indexes[1] = lm2_id
            bsp_surf.lm_indexes[2] = lm3_id
            bsp_surf.lm_indexes[3] = lm4_id
        else:
            bsp_surf.lm_indexes = lm_id
        
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
                bsp_vert = (bsp.lumps["drawverts"][bsp_vert_index])
                unpack_bsp_vert_lm_tc(bsp_vert,
                                      lightmap_size,
                                      packed_lightmap_size,
                                      bsp.lightmaps)
        else:
            for i in range(bsp_surf.patch_width):
                for j in range(bsp_surf.patch_height):
                    bsp_vert_index = (
                        bsp_surf.vertex+j*bsp_surf.patch_width+i)
                    bsp_vert = (bsp.lumps["drawverts"][bsp_vert_index])
                    unpack_bsp_vert_lm_tc(bsp_vert,
                                          lightmap_size,
                                          packed_lightmap_size,
                                          bsp.lightmaps)

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

def patch_bsp(bsp, objs, patch_settings : Patch_settings, light_settings : Light_settings) -> bool:

    meshes = [obj.to_mesh() for obj in objs]
    if bpy.app.version < (4, 1, 0):
        for mesh in meshes:
            mesh.calc_normals_split()

    num_bsp_verts = len(bsp.lumps["drawverts"])
    lightmapped_vertices = {id: False for id in range(num_bsp_verts)}

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
                bsp, bsp_indices, mesh, lightmapped_vertices)
            success, message = QuakeLight.storeVertexColors(
                bsp, objs, light_settings)
            success, message = QuakeLight.storeLighmaps(
                bsp,
                lightmap_image,
                n_lightmaps + 1,
                light_settings,
                not self.patch_external,
                self.patch_external_flip)
        if patch_settings.patch_normals:
            succ = patch_normals(bsp, bsp_indices, mesh)
        if patch_settings.patch_tcs:
            succ = patch_tcs(bsp, bsp_indices, mesh)
        if patch_settings.patch_lightgrid:
            success, message = QuakeLight.storeLightgrid(bsp, light_settings)


    return True