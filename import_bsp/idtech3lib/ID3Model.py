from math import floor, ceil, pi, sin, cos
from .ID3Brushes import Plane, parse_brush
from .ImportSettings import Surface_Type


class Map_Vertex:
    def __init__(self, array):
        if len(array) < 5:
            raise Exception("Not enough data to parse for control point")
        self.position = [array[0], array[1], array[2]]
        self.tcs = [array[3], array[4]]


def map_lerp_vertices(
    vertex1: Map_Vertex,
    vertex2: Map_Vertex
    ):

    lerped_vert = Map_Vertex([0.0, 0.0, 0.0, 0.0, 0.0])

    def lerp_vec(vec1, vec2, vec_out):
        for i in range(len(vec1)):
            vec_out[i] = (vec1[i] + vec2[i]) / 2.0
    
    lerp_vec(vertex1.position, vertex2.position, lerped_vert.position)
    lerp_vec(vertex1.tcs, vertex2.tcs, lerped_vert.tcs)
    
    return lerped_vert


def clamp_shift_tc(tc, min_tc, max_tc, u_shift, v_shift):
    u = min(max(tc[0], min_tc), max_tc) + u_shift
    v = min(max(tc[1], min_tc), max_tc) + v_shift
    return (u, v)


def unwrap_vert_map(vert_id, vertmap_size, current_id):
    id = int(floor(current_id/3.0))
    even = id % 2 == 0
    id += floor(id / 2)
    current_x = id % (vertmap_size[0] - 1)
    current_y = 2 * floor(id / (vertmap_size[0] - 1))
    
    eps_u = 0.005
    if even:
        eps_small = 0.495
        eps_big = 1.505
        if vert_id == 0:
            return ((current_x + eps_small + eps_u) / vertmap_size[0], (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 1:
            return ((current_x + eps_small + eps_u) / vertmap_size[0], (current_y + eps_small) / vertmap_size[1])
        elif vert_id == 2:
            return ((current_x + eps_big + eps_u) / vertmap_size[0], (current_y + eps_small) / vertmap_size[1])
        #special case for patch surfaces
        elif vert_id == 3:
            return ((current_x + eps_big + eps_u) / vertmap_size[0], (current_y + eps_big) / vertmap_size[1])
        else:
            return (0.0, 0.0)
    else:
        eps_small = 0.505
        eps_big = 1.505
        current_x += 1
        if vert_id == 0:
            return ((current_x - eps_small - eps_u) / vertmap_size[0], (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 1:
            return ((current_x + eps_small + eps_u) / vertmap_size[0], (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 2:
            return ((current_x + eps_small + eps_u) / vertmap_size[0], (current_y + 0.49) / vertmap_size[1])
        #special case for patch surfaces
        elif vert_id == 3:
            return ((current_x - eps_small - eps_u) / vertmap_size[0], (current_y + 0.49) / vertmap_size[1])
        else:
            return (0.0, 0.0)


def pack_lm_tc(tc,
               lightmap_id,
               lightmap_size,
               packed_lightmap_size):
    if (lightmap_id < 0):
        return tc

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

        def add_unindexed(self, data):
            if self.unindexed is None:
                self.unindexed = []
            self.unindexed.append(data)

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
            if self.unindexed is None and len(self.indexed) > 0:
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
        self.face_smooth = []

    def init_bsp_face_data(self, bsp):
        self.vertex_groups["Lightmapped"] = set()
        self.vertex_groups["Patch mesh"] = set()
        self.vertex_data_layers["BSP_VERT_INDEX"] = (
            self.VertexAttribute(self.indices))
        self.vertex_data_layers["BSP_SHADER_INDEX"] = (
            self.VertexAttribute(self.indices))
        self.vertex_data_layers["BSP_SURFACE_INDEX"] = (
            self.VertexAttribute(self.indices))
        self.vertex_data_layers["BSP_FOG_INDEX"] = (
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
        self.ext_lm_tc = []

        self.num_bsp_vertices = len(bsp.lumps["drawverts"])
        self.vertex_lightmap_id = self.VertexAttribute(self.indices)

        # data structure for patch meshes
        self.MAX_GRID_SIZE = 65
        self.ctrlPoints = [[0 for x in range(self.MAX_GRID_SIZE)]
                           for y in range(self.MAX_GRID_SIZE)]

    def init_bsp_brush_data(self, bsp):
        self.uv_layers["UVMap"] = (
            self.VertexAttribute(self.indices))
        self.vertex_groups["Patch mesh"] = set()
        self.current_index = 0
        self.index_mapping = [-2 for i in range(len(bsp.lumps["drawverts"]))]
        self.num_bsp_vertices = 0

        self.ext_lm_tc = []

        self.MAX_GRID_SIZE = 65
        self.ctrlPoints = [[0 for x in range(self.MAX_GRID_SIZE)]
                           for y in range(self.MAX_GRID_SIZE)]

    def init_map_brush_data(self):
        self.uv_layers["UVMap"] = (
            self.VertexAttribute(self.indices))
        self.vertex_groups["Patch mesh"] = set()
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

    def add_bsp_vertex_data(self, bsp, bsp_indices, face=None):
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
                if "UVMap" in self.uv_layers:
                    uv = drawverts_lump[index].texcoord[0], 1.0 - drawverts_lump[index].texcoord[1]
                    self.uv_layers["UVMap"].add_indexed(uv)
                if "LightmapUV" in self.uv_layers:
                    uv = drawverts_lump[index].lm1coord[0], 1.0 - drawverts_lump[index].lm1coord[1]
                    self.uv_layers["LightmapUV"].add_indexed(uv)
                alpha = [drawverts_lump[index].color1[3],
                         drawverts_lump[index].color1[3],
                         drawverts_lump[index].color1[3],
                         drawverts_lump[index].color1[3]]
                if "Color" in self.vertex_colors:
                    self.vertex_colors["Color"].add_indexed(
                        drawverts_lump[index].color1)
                if "BSP_VERT_INDEX" in self.vertex_data_layers:
                    if index < self.num_bsp_vertices:
                        self.vertex_data_layers["BSP_VERT_INDEX"].add_indexed(
                            index)
                    else:
                        self.vertex_data_layers["BSP_VERT_INDEX"].add_indexed(
                            -2)
                if "BSP_SURFACE_INDEX" in self.vertex_data_layers:
                    self.vertex_data_layers["BSP_SURFACE_INDEX"].add_indexed(
                        bsp.lumps["surfaces"].index(face))
                if "BSP_SHADER_INDEX" in self.vertex_data_layers:
                    self.vertex_data_layers["BSP_SHADER_INDEX"].add_indexed(
                        face.texture)
                if "BSP_FOG_INDEX" in self.vertex_data_layers:
                    self.vertex_data_layers["BSP_FOG_INDEX"].add_indexed(
                        face.effect)

                for i in range(2, bsp.lightmaps+1):
                    if i <= 4:
                        alpha[i-1] = getattr(
                            drawverts_lump[index], "color" + str(i))[3]
                    if "Color"+str(i) in self.vertex_colors:
                        self.vertex_colors["Color"+str(i)].add_indexed(
                            getattr(
                                drawverts_lump[index],
                                "color" + str(i)))
                    if "LightmapUV"+str(i) in self.uv_layers:
                        bsp_uv = getattr(drawverts_lump[index], "lm"+str(i)+"coord")
                        uv = bsp_uv[0], 1.0 - bsp_uv[1]
                        self.uv_layers["LightmapUV"+str(i)].add_indexed(uv)

                if "Alpha" in self.vertex_colors:
                    self.vertex_colors["Alpha"].add_indexed(alpha)

                # store lightmap ids for atlasing purposes
                if "LightmapUV" in self.uv_layers and face:
                    self.vertex_lightmap_id.add_indexed(face.lm_indexes)
            model_indices.append(self.index_mapping[index])
        self.indices.append(model_indices)

    def add_bsp_face_data(self,
                          bsp,
                          model_indices,
                          face,
                          force_nodraw=False):
        shaders_lump = bsp.lumps["shaders"]
        material_suffix = ""

        first_lm_index = face.lm_indexes if (
            bsp.lightstyles == 0
        ) else face.lm_indexes[0]

        if force_nodraw:
            material_suffix = ".nodraw"
        elif first_lm_index < 0:
            material_suffix = ".vertex"
        elif "Lightmapped" in self.vertex_groups:
            for index in model_indices:
                self.vertex_groups["Lightmapped"].add(index)

        material_name = (
            shaders_lump[face.texture].name.decode("latin-1") +
            material_suffix)
        
        self.ext_lm_tc.append(face.texture in bsp.lightmap_tc_shaders)

        if material_name not in self.material_names:
            self.material_names.append(material_name)
        self.material_id.append(self.material_names.index(material_name))
        self.face_smooth.append(True)

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
            self.add_bsp_vertex_data(bsp, bsp_indices, face)

            model_indices = (
                self.index_mapping[bsp_indices[0]],
                self.index_mapping[bsp_indices[1]],
                self.index_mapping[bsp_indices[2]]
            )
            self.add_bsp_face_data(bsp, model_indices, face)

    def subdivide_patch(self,
                        subdivisions,
                        face_width,
                        face_height,
                        ctrl_points,
                        lerp_func):

        width = face_width
        height = face_height
        if subdivisions > 0:
            for subd in range(subdivisions):
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
                        prev = lerp_func(
                            ctrl_points[j][pos_w],
                            ctrl_points[j][pos_w+1])
                        next = lerp_func(
                            ctrl_points[j][pos_w+1],
                            ctrl_points[j][pos_w+2])
                        midl = lerp_func(
                            prev,
                            next)

                        # replace peak
                        for x in range(width):
                            k = width - x
                            if (k <= pos_w+3):
                                break
                            ctrl_points[j][k] = ctrl_points[j][k-2]

                        ctrl_points[j][pos_w + 1] = prev
                        ctrl_points[j][pos_w + 2] = midl
                        ctrl_points[j][pos_w + 3] = next

                # add new rows
                for j in range(height//2):
                    if ((height + 2) > self.MAX_GRID_SIZE):
                        break
                    pos_h = j * 2 + added_height
                    height += 2
                    added_height += 2
                    # build new vertices
                    for i in range(width+1):
                        prev = lerp_func(
                            ctrl_points[pos_h][i],
                            ctrl_points[pos_h+1][i])
                        next = lerp_func(
                            ctrl_points[pos_h+1][i],
                            ctrl_points[pos_h+2][i])
                        midl = lerp_func(
                            prev,
                            next)

                        # replace peak
                        for x in range(height):
                            k = height - x
                            if (k <= pos_h+3):
                                break
                            ctrl_points[k][i] = ctrl_points[k-2][i]

                        ctrl_points[pos_h + 1][i] = prev
                        ctrl_points[pos_h + 2][i] = midl
                        ctrl_points[pos_h + 3][i] = next

        if subdivisions > -1:
            # now smooth the rest of the points
            for i in range(width+1):
                for j in range(1, height, 2):
                    prev = lerp_func(
                        ctrl_points[j][i],
                        ctrl_points[j+1][i])
                    next = lerp_func(
                        ctrl_points[j][i],
                        ctrl_points[j-1][i])
                    midl = lerp_func(
                        prev,
                        next)
                    ctrl_points[j][i] = midl

            for j in range(height+1):
                for i in range(1, width, 2):
                    prev = lerp_func(
                        ctrl_points[j][i],
                        ctrl_points[j][i+1])
                    next = lerp_func(
                        ctrl_points[j][i],
                        ctrl_points[j][i-1])
                    midl = lerp_func(
                        prev,
                        next)
                    ctrl_points[j][i] = midl
        return width, height

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

        width, height = self.subdivide_patch(import_settings.subdivisions,
                                             width,
                                             height,
                                             self.ctrlPoints,
                                             bsp.lerp_vertices)

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

        force_nodraw = False
        if import_settings.preset not in ["BRUSHES", "SHADOW_BRUSHES"]:
            shaders_lump = bsp.lumps["shaders"]
            force_nodraw = shaders_lump[face.texture].flags == 0x00200000

        for patch_face_index in range(width*height + height - 1):
            # end of row?
            if ((patch_face_index+1) % (width+1) == 0):
                continue
            if import_settings.front_culling:
                bsp_indices = [
                    bsp_index_list[patch_face_index + 1],
                    bsp_index_list[patch_face_index ],
                    bsp_index_list[patch_face_index + width + 1],
                    bsp_index_list[patch_face_index + width + 2]]
            else:
                bsp_indices = [
                    bsp_index_list[patch_face_index + 1],
                    bsp_index_list[patch_face_index + width + 2],
                    bsp_index_list[patch_face_index + width + 1],
                    bsp_index_list[patch_face_index]]

            self.add_bsp_vertex_data(bsp, bsp_indices, face)

            model_indices = (
                self.index_mapping[bsp_indices[0]],
                self.index_mapping[bsp_indices[1]],
                self.index_mapping[bsp_indices[2]],
                self.index_mapping[bsp_indices[3]]
            )
            self.add_bsp_face_data(bsp,
                                   model_indices,
                                   face,
                                   force_nodraw)
            
            # meh ugly hack
            if "Patch mesh" in self.vertex_groups:
                for index in model_indices:
                    self.vertex_groups["Patch mesh"].add(index)
            
    def add_bsp_brush(self, bsp, brush_id, import_settings):
        bsp_brush = bsp.lumps["brushes"][brush_id]
        brush_shader = ""
        planes = []

        if import_settings.preset == "SHADOW_BRUSHES":
            brush_shader = (
                bsp.lumps["shaders"]
                [bsp_brush.texture].name.decode("latin-1"))
            if brush_shader.startswith("noshader"):
                return
            if brush_shader.startswith("models/"):
                return
            if brush_shader.startswith("textures/system/"):
                for side in range(bsp_brush.n_brushsides):
                    brushside = bsp.lumps["brushsides"][
                        bsp_brush.brushside + side]
                    bsp_plane = bsp.lumps["planes"][brushside.plane]
                    shader = (
                        bsp.lumps["shaders"]
                        [brushside.texture].name.decode("latin-1"))
                    if not (shader.startswith("textures/system/") or \
                            shader.startswith("noshader") or \
                            shader.startswith("models/")):
                        brush_shader = shader
                        break
                if brush_shader.startswith("textures/system/"):
                    return

        for side in range(bsp_brush.n_brushsides):
            brushside = bsp.lumps["brushsides"][
                bsp_brush.brushside + side]
            bsp_plane = bsp.lumps["planes"][brushside.plane]

            if import_settings.preset == "SHADOW_BRUSHES":
                shader = brush_shader
            else:
                shader = (
                    bsp.lumps["shaders"]
                    [brushside.texture].name.decode("latin-1"))

            planes.append(Plane(
                tuple(bsp_plane.normal),
                bsp_plane.distance,
                shader))

        points, uvs, faces, mats = parse_brush(planes)

        indices = []
        for i in range(len(points)):
            indices.append(len(self.index_mapping))
            self.index_mapping.append(-2)

        for index, (point, uv) in zip(indices, (zip(points, uvs))):
            self.index_mapping[index] = self.current_index
            self.current_index += 1
            self.positions.add_indexed(point)
            self.vertex_normals.add_indexed((0.0, 0.0, 0.0))
            self.uv_layers["UVMap"].add_unindexed(uv)

        for face, material in zip(faces, mats):
            # add vertices to model
            self.indices.append(
                [self.index_mapping[indices[index]] for index in face])

            if material not in self.material_names:
                self.material_names.append(material)

            self.face_smooth.append(False)
            self.material_id.append(
                self.material_names.index(material))
            
    def add_bsp_bounds_mesh(self, bsp, mins, maxs, material):

        min_max_planes = [
            Plane([-1.0, 0.0, 0.0], -mins[0], material),
            Plane([0.0, -1.0, 0.0], -mins[1], material),
            Plane([0.0, 0.0, -1.0], -mins[2], material),
            Plane([1.0, 0.0, 0.0],  maxs[0], material),
            Plane([0.0, 1.0, 0.0],  maxs[1], material),
            Plane([0.0, 0.0, 1.0],  maxs[2], material)]
        points, uvs, faces, mats  = parse_brush(min_max_planes)

        indices = []
        for i in range(len(points)):
            indices.append(len(self.index_mapping))
            self.index_mapping.append(-2)

        for index, (point, uv) in zip(indices, (zip(points, uvs))):
            self.index_mapping[index] = self.current_index
            self.current_index += 1
            self.positions.add_indexed(point)
            self.vertex_normals.add_indexed((0.0, 0.0, 0.0))
            self.uv_layers["UVMap"].add_unindexed(uv)

        for face, material in zip(faces, mats):
            # add vertices to model
            self.indices.append(
                [self.index_mapping[indices[index]] for index in face])

            if material not in self.material_names:
                self.material_names.append(material)

            self.face_smooth.append(False)
            self.material_id.append(
                self.material_names.index(material))

    def add_bsp_model(self, bsp, model_id, import_settings):

        if bsp is None:
            return
        if model_id < 0:
            return

        self.init_bsp_face_data(bsp)
        bsp_model = bsp.lumps["models"][model_id]
        first_face = bsp_model.face
        bsp_surface_types = (
            Surface_Type.PLANAR,
            Surface_Type.TRISOUP,
            Surface_Type.FAKK_TERRAIN
        )
        for i in range(bsp_model.n_faces):
            face_id = first_face + i
            face = bsp.lumps["surfaces"][face_id]

            surface_type = Surface_Type.bsp_value(face.type)
            if not bool(surface_type & import_settings.surface_types):
                continue

            if surface_type in bsp_surface_types:
                self.add_bsp_surface(bsp, face, import_settings)
            elif surface_type == Surface_Type.PATCH:
                self.add_bsp_patch(bsp, face, import_settings)

    def add_bsp_model_brushes(self, bsp, model_id, import_settings):

        if bsp is None:
            return
        if model_id < 0:
            return
        if not bool(import_settings.surface_types & Surface_Type.BRUSH):
            return

        self.init_bsp_brush_data(bsp)
        bsp_model = bsp.lumps["models"][model_id]
        first_brush = bsp_model.brush
        first_face = bsp_model.face

        for i in range(bsp_model.n_faces):
            face_id = first_face + i
            face = bsp.lumps["surfaces"][face_id]

            surface_type = Surface_Type.bsp_value(face.type)
            if surface_type == Surface_Type.PATCH:
                self.add_bsp_patch(bsp, face, import_settings)

        self.uv_layers["UVMap"].make_unindexed_list()

        for i in range(bsp_model.n_brushes):
            brush_id = first_brush + i
            self.add_bsp_brush(bsp, brush_id, import_settings)

        special_imports = ["SHADOW_BRUSHES", "EDITING"]
        if import_settings.preset in special_imports:
            for index in range(len(self.material_names)):
                self.material_names[index] += ".brush"

    def add_map_patch(self, map_patch_surface, import_settings):
        
        patch_width, patch_height = map_patch_surface.patch_layout
        width = int(patch_width-1)
        height = int(patch_height-1)
        for i in range(patch_width):
            for j in range(patch_height):
                self.ctrlPoints[j][i] = map_patch_surface.ctrl_points[i*patch_height + j]

        width, height = self.subdivide_patch(import_settings.subdivisions,
                                             width,
                                             height,
                                             self.ctrlPoints,
                                             map_lerp_vertices)

        indices = []
        for i in range((width+1)*(height+1)):
            indices.append(len(self.index_mapping))
            self.index_mapping.append(self.current_index)
            self.current_index += 1

        for j in range(height+1):
            for i in range(width+1):
                self.positions.add_indexed(self.ctrlPoints[j][i].position)
                self.uv_layers["UVMap"].add_indexed(self.ctrlPoints[j][i].tcs)

        mat_name = "textures/{}".format(map_patch_surface.materials[0])
        if mat_name not in self.material_names:
            self.material_names.append(mat_name)
                        
        for patch_face_index in range(width*height + height - 1):
            # end of row?
            if ((patch_face_index+1) % (width+1) == 0):
                continue
            face = [
                patch_face_index + 1,
                patch_face_index + width + 2,
                patch_face_index + width + 1,
                patch_face_index]
            self.indices.append(
                [self.index_mapping[indices[index]] for index in face])
            self.face_smooth.append(True)
            self.material_id.append(
                self.material_names.index(mat_name))
            
            # meh ugly hack
            if "Patch mesh" in self.vertex_groups:
                for index in [self.index_mapping[indices[index]] for index in face]:
                    self.vertex_groups["Patch mesh"].add(index)

    def add_map_entity_brushes(self, entity, material_sizes, import_settings):
        if entity is None:
            return

        surfaces = entity.custom_parameters.get("surfaces")

        if surfaces is None:
            return

        self.init_map_brush_data()

        for surf in surfaces:
            if surf.type == "PATCH":
                self.add_map_patch(surf, import_settings)

        self.uv_layers["UVMap"].make_unindexed_list()

        for surf in surfaces:
            if surf.type == "BRUSH":
                points, uvs, faces, mats = parse_brush(surf.planes, material_sizes)

                indices = []
                for i in range(len(points)):
                    indices.append(len(self.index_mapping))
                    self.index_mapping.append(-2)

                for index, (point, uv) in zip(indices, (zip(points, uvs))):
                    self.index_mapping[index] = self.current_index
                    self.current_index += 1
                    self.positions.add_indexed(point)
                    self.uv_layers["UVMap"].add_unindexed(uv)

                for face, material in zip(faces, mats):
                    # add vertices to model
                    self.indices.append(
                        [self.index_mapping[indices[index]] for index in face])

                    if material not in self.material_names:
                        self.material_names.append(material)

                    self.face_smooth.append(False)
                    self.material_id.append(
                        self.material_names.index(material))

    def pack_lightmap_uvs(self, bsp):
        layer_names = ["LightmapUV"]
        for i in range(2, bsp.lightmaps+1):
            layer_names.append("LightmapUV"+str(i))

        for style_index, layer_name in enumerate(layer_names):
            for uv_id, uv_set in enumerate(self.uv_layers[layer_name].indexed):
                lightmap_id = self.vertex_lightmap_id.indexed[uv_id]
                if bsp.lightmaps > 1:
                    lightmap_id = lightmap_id[style_index]

                if bsp.deluxemapping and lightmap_id >= 0:
                    lightmap_id = lightmap_id // 2

                self.uv_layers[layer_name].indexed[uv_id] = pack_lm_tc(
                    uv_set,
                    lightmap_id,
                    bsp.internal_lightmap_size,
                    bsp.lightmap_size
                )

    def pack_vertmap_uvs(self, bsp, import_settings):
        # Breaks indexed uvs
        self.uv_layers["LightmapUV"].make_unindexed_list()
        lightmap_ids = self.vertex_lightmap_id.get_unindexed()
        current_index = 0
        for face, ext_lm_tc in zip(self.indices, self.ext_lm_tc):
            lightmapped = False
            if len(face) > 4 or ext_lm_tc:
                current_index += len(face)
                continue
            for vert_id, index in enumerate(face):
                lm_id = lightmap_ids[current_index]
                if bsp.lightmaps > 1:
                    lm_id = lightmap_ids[current_index][0]

                if lm_id >= 0:
                    lightmapped = True
                    current_index += 1
                    continue

                self.uv_layers["LightmapUV"].unindexed[current_index] = unwrap_vert_map(
                    vert_id,
                    (2048, 2048),
                    import_settings.current_vert_pack_index
                )

                current_index += 1
                if len(face) != 4:
                    import_settings.current_vert_pack_index += 1
            if len(face) == 4 and not lightmapped:
                import_settings.current_vert_pack_index += 6

    def copy_vertmap_uvs_from_diffuse(self, bsp):
        lightmap_ids = self.vertex_lightmap_id.get_indexed()
        for face, ext_lm_tc in zip(self.indices, self.ext_lm_tc):
            if len(face) > 4 or ext_lm_tc:
                continue
            for index in face:
                lm_id = lightmap_ids[index]
                if bsp.lightmaps > 1:
                    lm_id = lightmap_ids[index][0]

                if lm_id >= 0:
                    continue

                self.uv_layers["LightmapUV"].indexed[index] = self.uv_layers["UVMap"].indexed[index]
