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

from math import floor, ceil, pi, sin, cos
from .BspBrushes import Plane, parse_brush
from .BspImportSettings import SURFACE_TYPE


def clamp_shift_tc(tc, min_tc, max_tc, u_shift, v_shift):
    u = min(max(tc[0], min_tc), max_tc) + u_shift
    v = min(max(tc[1], min_tc), max_tc) + v_shift
    return (u, v)


def pack_lm_tc(tc,
               lightmap_id,
               lightmap_size,
               packed_lightmap_size):
    if (lightmap_id < 0):
        return clamp_shift_tc(tc, 0.0, 1.0, lightmap_id, 0.0)

    packed_lm_size = packed_lightmap_size
    num_columns = packed_lm_size[0] / lightmap_size[0]
    scale_value = (lightmap_size[0] / packed_lm_size[0],
                   lightmap_size[1] / packed_lm_size[1])

    x = (lightmap_id % num_columns) * scale_value[0]
    y = floor(lightmap_id/num_columns) * scale_value[1]

    packed_tc = (tc[0]*scale_value[0] + x, tc[1]*scale_value[1]+y)
    return packed_tc


class ID3Model:

    class VertexAttribute:
        def __init__(self, indices):
            self.indices = indices
            self.indexed = []
            self.unindexed = None

        def add_indexed(self, data):
            self.indexed.append(data)

        def get_indexed(self, cast=None):
            if cast is None:
                return self.indexed
            else:
                return [cast(i) for i in self.indexed]

        def set_indices(self, indices):
            self.indices = indices

        def make_unindexed_list(self):
            unindexed = []
            for i in range(len(self.indices)):
                for id in self.indices[i]:
                    unindexed.append(self.indexed[id])
            self.unindexed = unindexed

        def get_unindexed(self, cast=None):
            if self.indices is None:
                return None
            if self.unindexed is None:
                self.make_unindexed_list()
            if cast is None:
                return self.unindexed
            else:
                return [cast(i) for i in self.unindexed]

    def __init__(self, name="EmptyModel"):
        # used internally for reindexing
        self.current_index = 0
        self.index_mapping = []

        self.vertex_class = None

        # vertex and face data
        self.name = name
        self.indices = []
        self.positions = self.VertexAttribute(self.indices)
        self.vertex_normals = self.VertexAttribute(self.indices)
        self.uv_layers = {}
        self.vertex_colors = {}
        self.vertex_groups = {}
        self.vertex_data_layers = {}
        self.material_names = []
        self.material_id = []

    def init_bsp_face_data(self, bsp):
        self.vertex_groups["Lightmapped"] = set()
        self.vertex_data_layers["BSP_VERT_INDEX"] = (
            self.VertexAttribute(self.indices))
        self.vertex_colors["Color"] = (
            self.VertexAttribute(self.indices))
        self.vertex_colors["Alpha"] = (
            self.VertexAttribute(self.indices))
        self.uv_layers["UVMap"] = (
            self.VertexAttribute(self.indices))
        self.uv_layers["LightmapUV"] = (
            self.VertexAttribute(self.indices))

        for i in range(2, bsp.lightmaps+1):
            self.vertex_colors["Color"+str(i)] = (
                self.VertexAttribute(self.indices))
            self.uv_layers["LightmapUV"+str(i)] = (
                self.VertexAttribute(self.indices))

        self.current_index = 0
        self.index_mapping = [-2 for i in range(len(bsp.lumps["drawverts"]))]

        self.num_bsp_vertices = len(bsp.lumps["drawverts"])
        self.vertex_lightmap_id = self.VertexAttribute(self.indices)

        # data structure for patch meshes
        self.MAX_GRID_SIZE = 65
        self.ctrlPoints = [[0 for x in range(self.MAX_GRID_SIZE)]
                           for y in range(self.MAX_GRID_SIZE)]

    def init_bsp_brush_data(self, bsp):
        self.uv_layers["UVMap"] = (
            self.VertexAttribute(self.indices))
        self.current_index = 0
        self.index_mapping = []
        self.num_bsp_vertices = 0

        self.MAX_GRID_SIZE = 65
        self.ctrlPoints = [[0 for x in range(self.MAX_GRID_SIZE)]
                           for y in range(self.MAX_GRID_SIZE)]

    def get_bsp_vertex_offset(self, bsp, index):
        return bsp.lumps["drawindexes"][index].offset

    def add_new_vertex_to_bsp(self, bsp, vert):
        drawverts_lump = bsp.lumps["drawverts"]
        self.index_mapping.append(-2)
        new_bsp_index = len(drawverts_lump)
        drawverts_lump.append(vert)
        return new_bsp_index

    def add_bsp_vertex_data(self, bsp, bsp_indices, lm_ids=None):
        drawverts_lump = bsp.lumps["drawverts"]

        model_indices = []
        for index in bsp_indices:
            if self.index_mapping[index] < 0:
                self.index_mapping[index] = self.current_index
                self.current_index += 1
                self.positions.add_indexed(
                    drawverts_lump[index].position)
                self.vertex_normals.add_indexed(
                    drawverts_lump[index].normal)
                self.uv_layers["UVMap"].add_indexed(
                    drawverts_lump[index].texcoord)
                self.uv_layers["LightmapUV"].add_indexed(
                    drawverts_lump[index].lm1coord)
                alpha = [drawverts_lump[index].color1[3],
                         drawverts_lump[index].color1[3],
                         drawverts_lump[index].color1[3],
                         drawverts_lump[index].color1[3]]
                self.vertex_colors["Color"].add_indexed(
                    drawverts_lump[index].color1)
                if index < self.num_bsp_vertices:
                    self.vertex_data_layers["BSP_VERT_INDEX"].add_indexed(
                        index)
                else:
                    self.vertex_data_layers["BSP_VERT_INDEX"].add_indexed(
                        -2)

                for i in range(2, bsp.lightmaps+1):
                    if i <= 4:
                        alpha[i-1] = getattr(
                            drawverts_lump[index], "color" + str(i))[3]
                    self.vertex_colors["Color"+str(i)].add_indexed(
                        getattr(drawverts_lump[index], "color" + str(i)))
                    self.uv_layers["LightmapUV"+str(i)].add_indexed(
                        getattr(drawverts_lump[index], "lm"+str(i)+"coord"))
                self.vertex_colors["Alpha"].add_indexed(alpha)

                # store lightmap ids for atlasing purposes
                self.vertex_lightmap_id.add_indexed(lm_ids)
            model_indices.append(self.index_mapping[index])
        self.indices.append(model_indices)

    def add_bsp_face_data(self, bsp, model_indices, face):
        shaders_lump = bsp.lumps["shaders"]
        material_suffix = ""

        first_lm_index = face.lm_indexes if (
            bsp.lightstyles == 0
        ) else face.lm_indexes[0]

        if first_lm_index < 0:
            material_suffix = ".vertex"
        else:
            for index in model_indices:
                self.vertex_groups["Lightmapped"].add(index)

        material_name = (
            shaders_lump[face.texture].name.decode("latin-1") +
            material_suffix)

        if material_name not in self.material_names:
            self.material_names.append(material_name)
        self.material_id.append(self.material_names.index(material_name))

    def add_bsp_surface(self, bsp, face, import_settings):
        first_index = face.index
        # bsp only stores triangles, so there are n_indexes/3 trinangles
        for i in range(int(face.n_indexes / 3)):
            index = first_index + i * 3
            if import_settings.front_culling:
                bsp_indices = (
                    face.vertex + self.get_bsp_vertex_offset(
                        bsp, index),
                    face.vertex + self.get_bsp_vertex_offset(
                        bsp, index + 1),
                    face.vertex + self.get_bsp_vertex_offset(
                        bsp, index + 2)
                )
            else:
                bsp_indices = (
                    face.vertex + self.get_bsp_vertex_offset(
                        bsp, index),
                    face.vertex + self.get_bsp_vertex_offset(
                        bsp, index + 2),
                    face.vertex + self.get_bsp_vertex_offset(
                        bsp, index + 1)
                )
            self.add_bsp_vertex_data(bsp, bsp_indices, face.lm_indexes)

            model_indices = (
                self.index_mapping[bsp_indices[0]],
                self.index_mapping[bsp_indices[1]],
                self.index_mapping[bsp_indices[2]]
            )
            self.add_bsp_face_data(bsp, model_indices, face)

    def add_bsp_patch(self, bsp, face, import_settings):
        drawverts_lump = bsp.lumps["drawverts"]
        width = int(face.patch_width-1)
        height = int(face.patch_height-1)

        self.bspPoints = [[-1 for x in range(self.MAX_GRID_SIZE)]
                          for y in range(self.MAX_GRID_SIZE)]

        for i in range(face.patch_width):
            for j in range(face.patch_height):
                self.bspPoints[j][i] = face.vertex + j*face.patch_width + i
                vertex = drawverts_lump[self.bspPoints[j][i]]
                self.ctrlPoints[j][i] = vertex

        if import_settings.subdivisions > 0:
            for subd in range(import_settings.subdivisions):
                pos_w = 0
                pos_h = 0
                added_width = 0
                added_height = 0
                # add new colums
                for i in range(width//2):
                    if ((width + 2) > self.MAX_GRID_SIZE):
                        break
                    pos_w = i * 2 + added_width
                    width += 2
                    added_width += 2
                    # build new vertices
                    for j in range(height+1):
                        prev = bsp.lerp_vertices(
                            self.ctrlPoints[j][pos_w],
                            self.ctrlPoints[j][pos_w+1])
                        next = bsp.lerp_vertices(
                            self.ctrlPoints[j][pos_w+1],
                            self.ctrlPoints[j][pos_w+2])
                        midl = bsp.lerp_vertices(
                            prev,
                            next)

                        # replace peak
                        for x in range(width):
                            k = width - x
                            if (k <= pos_w+3):
                                break
                            self.ctrlPoints[j][k] = self.ctrlPoints[j][k-2]

                        self.ctrlPoints[j][pos_w + 1] = prev
                        self.ctrlPoints[j][pos_w + 2] = midl
                        self.ctrlPoints[j][pos_w + 3] = next

                # add new rows
                for j in range(height//2):
                    if ((height + 2) > self.MAX_GRID_SIZE):
                        break
                    pos_h = j * 2 + added_height
                    height += 2
                    added_height += 2
                    # build new vertices
                    for i in range(width+1):
                        prev = bsp.lerp_vertices(
                            self.ctrlPoints[pos_h][i],
                            self.ctrlPoints[pos_h+1][i])
                        next = bsp.lerp_vertices(
                            self.ctrlPoints[pos_h+1][i],
                            self.ctrlPoints[pos_h+2][i])
                        midl = bsp.lerp_vertices(
                            prev,
                            next)

                        # replace peak
                        for x in range(height):
                            k = height - x
                            if (k <= pos_h+3):
                                break
                            self.ctrlPoints[k][i] = self.ctrlPoints[k-2][i]

                        self.ctrlPoints[pos_h + 1][i] = prev
                        self.ctrlPoints[pos_h + 2][i] = midl
                        self.ctrlPoints[pos_h + 3][i] = next

        if import_settings.subdivisions > -1:
            # now smooth the rest of the points
            for i in range(width+1):
                for j in range(1, height, 2):
                    prev = bsp.lerp_vertices(
                        self.ctrlPoints[j][i],
                        self.ctrlPoints[j+1][i])
                    next = bsp.lerp_vertices(
                        self.ctrlPoints[j][i],
                        self.ctrlPoints[j-1][i])
                    midl = bsp.lerp_vertices(
                        prev,
                        next)
                    self.ctrlPoints[j][i] = midl

            for j in range(height+1):
                for i in range(1, width, 2):
                    prev = bsp.lerp_vertices(
                        self.ctrlPoints[j][i],
                        self.ctrlPoints[j][i+1])
                    next = bsp.lerp_vertices(
                        self.ctrlPoints[j][i],
                        self.ctrlPoints[j][i-1])
                    midl = bsp.lerp_vertices(
                        prev,
                        next)
                    self.ctrlPoints[j][i] = midl

        # get the bsp indices aligned with the subdivided patch mesh
        fixed_bsp_indices = [
            [-1 for x in range(width+1)] for y in range(height+1)]
        step_w = int((width+1)/(face.patch_width-1))
        step_h = int((height+1)/(face.patch_height-1))
        for w, i in enumerate(range(0, width+1, step_w)):
            for h, j in enumerate(range(0, height+1, step_h)):
                fixed_bsp_indices[j][i] = self.bspPoints[h][w]

        # build index list and make sure vertices are updated in the lump data
        bsp_index_list = []
        for j in range(height+1):
            for i in range(width+1):
                # if the index is valid, make sure the draw vert is smoothed
                if (fixed_bsp_indices[j][i] >= 0):
                    drawverts_lump[fixed_bsp_indices[j][i]] = (
                        self.ctrlPoints[j][i])
                # if the index is invalid, make sure to add the draw vert
                else:
                    fixed_bsp_indices[j][i] = (
                        self.add_new_vertex_to_bsp(
                            bsp, self.ctrlPoints[j][i]))
                bsp_index_list.append(fixed_bsp_indices[j][i])

        for patch_face_index in range(width*height + height - 1):
            # end of row?
            if ((patch_face_index+1) % (width+1) == 0):
                continue
            bsp_indices = [
                bsp_index_list[patch_face_index + 1],
                bsp_index_list[patch_face_index + width + 2],
                bsp_index_list[patch_face_index + width + 1],
                bsp_index_list[patch_face_index]]

            self.add_bsp_vertex_data(bsp, bsp_indices, face.lm_indexes)

            model_indices = (
                self.index_mapping[bsp_indices[0]],
                self.index_mapping[bsp_indices[1]],
                self.index_mapping[bsp_indices[2]],
                self.index_mapping[bsp_indices[3]]
            )
            self.add_bsp_face_data(bsp, model_indices, face)

    def add_bsp_model(self, bsp, model_id, import_settings):

        if bsp is None:
            return
        if model_id < 0:
            return

        self.init_bsp_face_data(bsp)
        bsp_model = bsp.lumps["models"][model_id]
        first_face = bsp_model.face
        bsp_surface_types = (
            SURFACE_TYPE.PLANAR,
            SURFACE_TYPE.TRISOUP,
            SURFACE_TYPE.FAKK_TERRAIN
        )
        for i in range(bsp_model.n_faces):
            face_id = first_face + i
            face = bsp.lumps["surfaces"][face_id]

            surface_type = SURFACE_TYPE.bsp_value(face.type)
            if not bool(surface_type & import_settings.surface_types):
                continue

            if surface_type in bsp_surface_types:
                self.add_bsp_surface(bsp, face, import_settings)
            elif surface_type == SURFACE_TYPE.PATCH:
                self.add_bsp_patch(bsp, face, import_settings)

        if bool(import_settings.surface_types & SURFACE_TYPE.BRUSH):
            for mat_id in range(len(self.material_names)):
                self.material_names[mat_id] = (self.material_names[mat_id] +
                                               ".brush")

    def add_bsp_model_brushes(self, bsp, model_id, import_settings):

        if bsp is None:
            return
        if model_id < 0:
            return
        if not bool(import_settings.surface_types & SURFACE_TYPE.BRUSH):
            return

        self.init_bsp_brush_data(bsp)
        bsp_model = bsp.lumps["models"][model_id]
        first_brush = bsp_model.brush

        for i in range(bsp_model.n_brushes):
            brush_id = first_brush + i

            bsp_brush = bsp.lumps["brushes"][brush_id]
            shader = (bsp.lumps["shaders"][bsp_brush.texture].name.decode(
                "latin-1") +
                      ".brush")
            if not (shader in self.material_names):
                self.material_names.append(shader)

            brush_shader_id = self.material_names.index(shader)

            planes = []
            brush_materials = []
            for side in range(bsp_brush.n_brushsides):
                brushside = bsp.lumps["brushsides"][
                    bsp_brush.brushside + side]
                bsp_plane = bsp.lumps["planes"][brushside.plane]
                shader = bsp.lumps["shaders"][
                    brushside.texture].name.decode("latin-1") + ".brush"

                if not (shader in self.material_names):
                    self.material_names.append(shader)

                if not (shader in brush_materials):
                    brush_materials.append(shader)

                mat_id = brush_materials.index(shader)
                planes.append(Plane(
                    distance=bsp_plane.distance,
                    normal=tuple(bsp_plane.normal),
                    material_id=mat_id))

            final_points, faces = parse_brush(planes, None)

            self.index_mapping = [-2] * len(final_points)
            for index, point in enumerate(final_points):
                self.index_mapping[index] = self.current_index
                self.current_index += 1
                self.positions.add_indexed(
                    point)

                self.uv_layers["UVMap"].add_indexed(
                    (0.0, 0.0))

            for face in faces:
                # add vertices to model
                model_indices = []
                for index in face:
                    model_indices.append(self.index_mapping[index])
                self.indices.append(model_indices)

                # add faces to model
                shaders_lump = bsp.lumps["shaders"]
                if brush_shader_id <= len(bsp.lumps["shaders"]):
                    material_name = (
                        shaders_lump[brush_shader_id].name.decode("latin-1") +
                        ".brush")
                else:
                    material_name = "noshader"

                if material_name not in self.material_names:
                    self.material_names.append(material_name)
                self.material_id.append(
                    self.material_names.index(material_name))

    def pack_lightmap_uvs(self, bsp):
        layer_name = "LightmapUV"
        for uv_id, uv_set in enumerate(self.uv_layers[layer_name].indexed):
            lightmap_id = self.vertex_lightmap_id.indexed[uv_id]
            if bsp.lightmaps > 1:
                lightmap_id = lightmap_id[0]

            if bsp.deluxemapping and lightmap_id >= 0:
                lightmap_id = lightmap_id // 2

            self.uv_layers[layer_name].indexed[uv_id] = pack_lm_tc(
                uv_set,
                lightmap_id,
                bsp.internal_lightmap_size,
                bsp.lightmap_size
            )
        for i in range(2, bsp.lightmaps+1):
            layer_name = "LightmapUV"+str(i)
            for uv_id, uv_set in enumerate(self.uv_layers[layer_name].indexed):
                lightmap_id = self.vertex_lightmap_id.indexed[uv_id]
                if bsp.lightmaps > 1:
                    lightmap_id = lightmap_id[i-1]

                if bsp.deluxemapping:
                    lightmap_id = lightmap_id // 2

                self.uv_layers[layer_name].indexed[uv_id] = pack_lm_tc(
                    uv_set,
                    lightmap_id,
                    bsp.internal_lightmap_size,
                    bsp.lightmap_size
                )
