import bpy
import os
import struct
from math import pi, sin, cos, atan2, acos, sqrt
from mathutils import Matrix
from bpy_extras.io_utils import unpack_list
from .idtech3lib.Parsing import guess_model_name, fillName, parse


FLOAT = 4
HALF = 2
INT = 4
UBYTE = 1
STRING = 64


class vertex_map:
    def __init__(self, object_id, mesh, vertex_id, loop_id):
        self.mesh = mesh
        self.obj_id = object_id
        self.vert = vertex_id
        self.loop = loop_id
        self.position = mesh.vertices[vertex_id].co.copy()
        self.normal = mesh.vertices[vertex_id].normal.copy()
        if mesh.has_custom_normals:
            self.normal = mesh.loops[loop_id].normal.copy()
        self.tc = mesh.uv_layers.active.data[loop_id].uv.copy()

    def set_mesh(self, mesh):
        self.mesh = mesh


class surface_descriptor:
    def __init__(self, material, obj_name):
        self.current_index = 0
        self.vertex_mapping = []
        self.triangles = []
        self.material = material
        self.obj_name = obj_name

    # always make sure that you pack the same material in
    # one surface descriptor!
    def add_triangle(self, in_obj_id, in_mesh, in_triangle):
        # Quake 3 limit from sourcecode
        SHADER_MAX_VERTEXES = 1200

        if len(self.triangles) * 3 >= 6 * SHADER_MAX_VERTEXES:
            return False

        new_triangle = [None, None, None]
        new_map = None

        reused_vertices = 0

        triangle_descriptor = []
        for index, zipped in enumerate(zip(in_triangle.vertices,
                                           in_triangle.loops)):
            tri = zipped[0]
            loo = zipped[1]
            vert_pos = in_mesh.vertices[tri].co.copy()
            vert_nor = in_mesh.vertices[tri].normal.copy()
            if in_mesh.has_custom_normals:
                vert_nor = in_mesh.loops[loo].normal.copy()
            vert_tc = in_mesh.uv_layers.active.data[loo].uv.copy()
            triangle_descriptor.append((vert_pos, vert_nor, vert_tc))

        # check for duplicates
        for id, map in enumerate(self.vertex_mapping):
            for index, tri_vert in enumerate(triangle_descriptor):
                if (tri_vert[0] == map.position) and (
                        tri_vert[1] == map.normal) and (
                        tri_vert[2] == map.tc):
                    # vertex already in the surface
                    if new_triangle[index] is None:
                        new_triangle[index] = id
                        reused_vertices += 1
                        break

        if 3-reused_vertices + len(self.vertex_mapping) >= SHADER_MAX_VERTEXES:
            return False

        # add new vertices
        for id, index in enumerate(new_triangle):
            if index is None:
                new_vert = in_triangle.vertices[id]
                new_loop = in_triangle.loops[id]
                new_mesh = in_mesh
                new_map = vertex_map(in_obj_id, new_mesh, new_vert, new_loop)
                self.vertex_mapping.append(new_map)
                new_triangle[id] = self.current_index
                self.current_index += 1

        # add new triangle
        self.triangles.append(new_triangle)
        return True


class surface_factory:
    valid = False
    status = "Unknown Error"

    def __init__(self,
                 objects,
                 individual,
                 material_mapping=None,
                 material_merge=True):
        self.individual = individual
        surfaces = {}
        self.surface_descriptors = []
        self.num_surfaces = 0
        self.objects = objects

        material_count = 1
        # create a list for every material
        for obj in objects:
            if material_merge:
                if len(obj.data.materials) == 0:
                    surfaces["NoShader"] = [surface_descriptor(
                        "NoShader", "material"+str(material_count))]
                    if material_mapping is not None:
                        material_mapping["material" +
                                         str(material_count)] = "NoShader"
                    material_count += 1
                for mat in obj.data.materials:
                    mat_name = mat.name.split(".")[0]
                    if mat_name not in surfaces:
                        surfaces[mat_name] = [surface_descriptor(
                            mat_name, "material"+str(material_count))]
                        if material_mapping is not None:
                            material_mapping["material" +
                                             str(material_count)] = mat_name
                        material_count += 1
                        self.num_surfaces += 1
            else:
                if len(obj.data.materials) == 0:
                    mat_name = "NoShader"
                else:
                    mat_name = obj.data.materials[0].name.split(".")[0]

                surfaces[obj.name] = [surface_descriptor(
                    mat_name, "material"+str(material_count))]
                if material_mapping is not None:
                    material_mapping["material"+str(material_count)] = mat_name
                material_count += 1

                self.num_surfaces += 1

        for obj_id, obj in enumerate(objects):
            mesh = obj.to_mesh()
            if not self.individual:
                mesh.transform(obj.matrix_world)

            if bpy.app.version < (4, 1, 0):
                mesh.calc_normals_split()

            mesh.calc_loop_triangles()

            for triangle in mesh.loop_triangles:
                if material_merge:
                    if len(mesh.materials) == 0:
                        mat = "NoShader"
                    else:
                        mat = mesh.materials[triangle.material_index].name
                        mat = mat.split(".")[0]

                    if mat in surfaces:
                        surface_descr = surfaces[mat][len(surfaces[mat])-1]
                        succeeded = surface_descr.add_triangle(
                            obj_id, mesh, triangle)
                        if not succeeded:
                            new_surface_descr = surface_descriptor(
                                mat, "material"+str(material_count))
                            material_count += 1
                            new_surface_descr.add_triangle(
                                obj_id, mesh, triangle)
                            surfaces[mat].append(new_surface_descr)
                            self.num_surfaces += 1
                            if self.num_surfaces > 32:
                                self.valid = False
                                self.status = "Exported object(s) exceed "
                                "max surfaces. Reduce model complexity."
                                return
                            self.status = (
                                self.status + "Added additional surface for " +
                                mat + " because there were too many "
                                "vertices or triangles\n")
                else:
                    surface_descr = surfaces[obj.name][len(
                        surfaces[obj.name])-1]
                    succeeded = surface_descr.add_triangle(
                        obj_id, mesh, triangle)
                    # TODO: Split model, add numeric suffix to model names
                    if not succeeded:
                        self.valid = False
                        self.status = (
                            "Object exceeds vertex or indices limit: " +
                            obj.name)
                        return

        for mat in surfaces:
            for i in range(len(surfaces[mat])):
                self.surface_descriptors.append(surfaces[mat][i])

        self.valid = True
        self.status = "Added object(s) successfully to surface factory."
        return

    def clear_meshes(self):
        for obj in self.objects:
            obj.to_mesh_clear()

    def update_meshes(self):
        meshes = []
        for obj_id, obj in enumerate(self.objects):
            mesh = obj.to_mesh()
            if not self.individual:
                mesh.transform(obj.matrix_world)

            if bpy.app.version < (4, 1, 0):
                mesh.calc_normals_split()

            meshes.append(mesh)
        for surface_descriptor in self.surface_descriptors:
            for map in surface_descriptor.vertex_mapping:
                map.set_mesh(meshes[map.obj_id])


class lump:
    def __init__(self, data_class):
        self.data_class = data_class
        self.data = []
        self.offset = 0
        self.size = 0
        self.count = 0

    def set_offset_size(self, offset_size):
        self.offset = offset_size[0]
        self.size = offset_size[1]

    def set_offset_count(self, offset_count):
        self.offset = offset_count[0]
        self.count = offset_count[1]

    def read_from_bytearray(self, bsp_bytearray):
        if self.count == 0:
            self.count = self.size / self.data_class.size

        for i in range(int(self.count)):
            offset = self.offset + i * self.data_class.size
            self.data.append(self.data_class(struct.unpack(
                self.data_class.encoding,
                bsp_bytearray[offset:offset+self.data_class.size])))


class tan_array:
    def __init__(self, data_class, offset_count):
        self.data_class = data_class
        self.data = []
        self.offset = offset_count[0]
        self.count = offset_count[1]

    def to_bytes(self):
        self.count = len(self.data)
        self.size = self.count * self.data_class.size
        bytes = bytearray()
        for i in range(self.count):
            bytes += (struct.pack(self.data_class.encoding,
                      *self.data[i].to_array()))
        return bytes

    def read_from_bytearray(self, bsp_bytearray, array_offset):
        for i in range(int(self.count)):
            offset = self.offset + array_offset + i * self.data_class.size
            self.data.append(self.data_class(struct.unpack(
                self.data_class.encoding,
                bsp_bytearray[offset:offset+self.data_class.size])))


class TAN:
    TAN_MAGIC = b'TAN '
    TAN_VERSION = 2

    def __init__(self, magic, version):
        self.valid = magic == self.TAN_MAGIC and version == self.TAN_VERSION

    def decode_normal(packed):
        lat = packed[1] * (2 * pi / 255)
        long = packed[0] * (2 * pi / 255)
        x = cos(lat) * sin(long)
        y = sin(lat) * sin(long)
        z = cos(long)
        return [x, y, z]

    def encode_normal(normal):
        x, y, z = normal
        l_vec = sqrt((x * x) + (y * y) + (z * z))
        if l_vec == 0:
            print("zero length found!")
            return bytes((0, 0))
        x = x/l_vec
        y = y/l_vec
        z = z/l_vec
        if x == 0 and y == 0:
            return bytes((0, 0)) if z > 0 else bytes((128, 0))
        long = int(round(atan2(y, x) * 255 / (2.0 * pi))) & 0xff
        lat = int(round(acos(z) * 255 / (2.0 * pi))) & 0xff
        return bytes((lat, long))

    class surface:
        encoding = "<i64siiiiiiiii"
        size = struct.calcsize(encoding)

        def __init__(self, array):

            first_0 = 64
            for pos, i in enumerate(array[1]):
                if i == 0:
                    first_0 = pos
                    break
            reverse = 64-first_0
            self.ident = array[0]
            self.name = array[1][:-reverse].decode("utf-8", errors="ignore")

            self.n_frames = array[2]
            self.n_verts = array[3]
            self.n_model_verts = array[4]

            self.n_tris = array[5]
            self.off_tris = array[6]

            self.off_collapse = array[7]

            self.off_tcs = array[8]
            self.off_verts = array[9]
            self.off_end = array[10]

            debug = False
            if debug is True:
                print("\tname " + str(self.name))
                print("\t\tn_frames " + str(self.n_frames))
                print("\t\tn_verts " + str(self.n_verts))
                print("\t\tn_model_verts " + str(self.n_model_verts))
                print("\t\tn_tris " + str(self.n_tris))
                print("\t\toff_tris " + str(self.off_tris))
                print("\t\toff_collapse " + str(self.off_collapse))
                print("\t\toff_tcs " + str(self.off_tcs))
                print("\t\toff_verts " + str(self.off_verts))
                print("\t\toff_end " + str(self.off_end))

            self.triangles = tan_array(
                self.triangle, [self.off_tris, self.n_tris])
            self.vertices = tan_array(
                self.vertex, [self.off_verts, self.n_verts])
            self.tcs = tan_array(self.tc, [self.off_tcs, self.n_verts])
            self.collapse_map = tan_array(
                self.collapse_map, [self.off_collapse, self.n_verts])

        def get_frame_vertex_lump(self, frame):
            if frame > self.n_frames:
                return None
            return tan_array(self.vertex,
                             [self.off_verts +
                              frame*self.n_verts*self.vertex.size,
                              self.n_verts])

        @classmethod
        def from_surface_descriptor(cls, sd):
            array = [None for i in range(12)]
            array[0] = b'TAN '
            array[1] = bytes(fillName(sd.obj_name, 64), "ascii")
            array[2] = 1  # n_frames
            surface = cls(array)

            for map in sd.vertex_mapping:
                mesh = map.mesh
                new_vertex = cls.vertex.from_vertex(mesh.vertices[map.vert])
                new_tc = cls.tc.from_loop(mesh.uv_layers.active.data[map.loop])
                if mesh.has_custom_normals:
                    new_vertex.normal = mesh.loops[map.loop].normal.copy()

                surface.vertices.data.append(new_vertex)
                surface.tcs.data.append(new_tc)

            for triangle in sd.triangles:
                surface.triangles.data.append(cls.triangle(triangle))
                surface.collapse_map.data.append(
                    cls.collapse_map([cls.triangle(triangle).indices[0]]))

            return surface

        def add_current_frame(self, sd, scale, offset):
            self.n_frames += 1
            for map in sd.vertex_mapping:
                mesh = map.mesh
                new_vertex = self.vertex.from_vertex(mesh.vertices[map.vert])
                new_vertex.apply_scale_offset(scale, offset)
                if mesh.has_custom_normals:
                    new_vertex.normal = mesh.loops[map.loop].normal.copy()

                self.vertices.data.append(new_vertex)

        def apply_scale_offset(self, scale, offset):
            for vertex in self.vertices.data:
                vertex.apply_scale_offset(scale, offset)

        def to_bytes(self):
            triangles = self.triangles.to_bytes()
            collapse_map = self.collapse_map.to_bytes()
            tcs = self.tcs.to_bytes()
            vertices = self.vertices.to_bytes()
            n_verts = int(self.vertices.count / self.n_frames)

            new_bytes = bytearray()
            new_bytes += (self.ident)
            new_bytes += bytes(fillName(self.name, 64), "ascii")
            new_bytes += (struct.pack("<i", self.n_frames))
            new_bytes += (struct.pack("<i", n_verts))  # n_verts
            new_bytes += (struct.pack("<i", n_verts))  # n_model_verts
            new_bytes += (struct.pack("<i", self.triangles.count))

            header_offset = self.size
            tris_offset = header_offset
            collapse_offset = tris_offset + self.triangles.size
            tcs_offset = collapse_offset + self.collapse_map.size
            vert_offset = tcs_offset + self.tcs.size
            end_offset = vert_offset + self.vertices.size

            new_bytes += (struct.pack("<i", tris_offset))
            new_bytes += (struct.pack("<i", collapse_offset))
            new_bytes += (struct.pack("<i", tcs_offset))
            new_bytes += (struct.pack("<i", vert_offset))
            new_bytes += (struct.pack("<i", end_offset))

            new_bytes += triangles
            new_bytes += collapse_map
            new_bytes += tcs
            new_bytes += vertices

            return new_bytes

        class triangle:
            encoding = "<3i"
            size = struct.calcsize(encoding)

            def __init__(self, array):
                self.indices = [array[0], array[2], array[1]]

            @classmethod
            def from_triangle(cls, triangle):
                return cls(triangle.vertices)

            def to_array(self):
                array = [None for i in range(3)]
                array[0] = self.indices[0]
                array[1] = self.indices[1]
                array[2] = self.indices[2]
                return array

        class collapse_map:
            encoding = "<i"
            size = struct.calcsize(encoding)

            def __init__(self, array):
                self.id = array[0]

            @classmethod
            def from_triangle(cls, triangle):
                return cls(triangle.vertices)

            def to_array(self):
                array = [None]
                array[0] = self.id
                return array

        class tc:
            encoding = "<2f"
            size = struct.calcsize(encoding)

            def __init__(self, array):
                self.tc = [array[0], 1.0 - array[1]]

            @classmethod
            def from_loop(cls, loop):
                tcs = loop.uv.copy()
                return cls([tcs[0], 1.0 - tcs[1]])

            def to_array(self):
                array = [None for i in range(2)]
                array[0] = self.tc[0]
                array[1] = 1.0 - self.tc[1]
                return array

        class vertex:
            encoding = "<3H2s"
            size = struct.calcsize(encoding)

            def __init__(self, array):
                self.position = [array[0], array[1], array[2]]
                self.normal = TAN.decode_normal(array[3])

            @classmethod
            def from_vertex(cls, vertex):
                vert = cls([0.0, 0.0, 0.0, [0, 0]])
                vert.position = vertex.co.copy()
                vert.normal = vertex.normal.copy()
                return vert

            def apply_scale_offset(self, scale, offset):
                self.position[0] = (self.position[0] - offset[0]) / scale[0]
                self.position[1] = (self.position[1] - offset[1]) / scale[1]
                self.position[2] = (self.position[2] - offset[2]) / scale[2]

            def to_array(self):
                array = [None for i in range(4)]
                array[0] = int(self.position[0])
                array[1] = int(self.position[1])
                array[2] = int(self.position[2])
                array[3] = TAN.encode_normal(self.normal)
                return array

    class frame:
        encoding = "<3f3f3f3f3fff"
        size = struct.calcsize(encoding)

        def __init__(self, array):
            self.min_bounds = [array[0], array[1], array[2]]
            self.max_bounds = [array[3], array[4], array[5]]
            self.scale = [array[6]*1, array[7]*1, array[8]*1]
            self.offset = [array[9], array[10], array[11]]
            self.delta = [array[12], array[13], array[14]]
            self.radius = array[15]
            self.frame_time = array[16]

        @classmethod
        def from_objects(cls, objects, individual, previous_frame=None):
            array = [0.0 for i in range(17)]
            frame = cls(array)

            frame.min_bounds = [65535, 65535, 65535]
            frame.max_bounds = [-65535, -65535, -65535]

            for obj in objects:
                mesh = obj.data.copy()
                if not individual:
                    mesh.transform(obj.matrix_world)
                for vert in mesh.vertices:
                    frame.min_bounds = [min(frame.min_bounds[0], vert.co[0]),
                                        min(frame.min_bounds[1], vert.co[1]),
                                        min(frame.min_bounds[2], vert.co[2])]
                    frame.max_bounds = [max(frame.max_bounds[0], vert.co[0]),
                                        max(frame.max_bounds[1], vert.co[1]),
                                        max(frame.max_bounds[2], vert.co[2])]

            frame.scale[0] = (frame.max_bounds[0] -
                              frame.min_bounds[0]) / 65535
            frame.scale[1] = (frame.max_bounds[1] -
                              frame.min_bounds[1]) / 65535
            frame.scale[2] = (frame.max_bounds[2] -
                              frame.min_bounds[2]) / 65535

            x = frame.min_bounds[0] + \
                (frame.max_bounds[0] - frame.min_bounds[0]) / 2
            y = frame.min_bounds[1] + \
                (frame.max_bounds[1] - frame.min_bounds[1]) / 2
            z = frame.min_bounds[2] + \
                (frame.max_bounds[2] - frame.min_bounds[2]) / 2
            frame.offset = frame.min_bounds
            r1 = frame.max_bounds[0] - x
            r2 = frame.max_bounds[1] - y
            r3 = frame.max_bounds[2] - z
            frame.radius = sqrt(r1*r1 + r2*r2 + r3*r3)
            frame.frame_time = 1.0 / 20.0
            if previous_frame is not None:
                frame.delta[0] = previous_frame.offset[0] - x
                frame.delta[1] = previous_frame.offset[1] - y
                frame.delta[2] = previous_frame.offset[2] - z
            else:
                frame.delta = [0.0, 0.0, 0.0]
            return frame

        def to_bytes(self):
            new_bytes = bytearray()
            new_bytes += (struct.pack("<3f", *self.min_bounds))
            new_bytes += (struct.pack("<3f", *self.max_bounds))
            new_bytes += (struct.pack("<3f", *self.scale))
            new_bytes += (struct.pack("<3f", *self.offset))
            new_bytes += (struct.pack("<3f", *self.delta))
            new_bytes += (struct.pack("<f", self.radius))
            new_bytes += (struct.pack("<f", self.frame_time))
            return new_bytes

    class tag_data:
        encoding = "<3f3f3f3f"
        size = struct.calcsize(encoding)

        def __init__(self, array):
            self.origin = [array[0], array[1], array[2]]
            self.axis_1 = [array[3], array[4], array[5]]
            self.axis_2 = [array[6], array[7], array[8]]
            self.axis_3 = [array[9], array[10], array[11]]

        @classmethod
        def from_empty(cls, empty):
            array = []
            for i in range(12):
                array.append(0.0)
            tag = cls(array)
            tag.origin = empty.location.copy()
            matrix = empty.matrix_world.copy()
            matrix.transpose()
            tag.axis_1 = matrix[0].xyz
            tag.axis_2 = matrix[1].xyz
            tag.axis_3 = matrix[2].xyz
            return tag

        def to_bytes(self):
            new_bytes = bytearray()
            new_bytes += (struct.pack("<3f", *self.origin))
            new_bytes += (struct.pack("<3f", *self.axis_1))
            new_bytes += (struct.pack("<3f", *self.axis_2))
            new_bytes += (struct.pack("<3f", *self.axis_3))
            return new_bytes

    class tag:
        encoding = "<64s"
        size = struct.calcsize(encoding)

        def __init__(self, array):
            first_0 = 64
            for pos, i in enumerate(array[0]):
                if i == 0:
                    first_0 = pos
                    break
            reverse = 64-first_0

            self.name = array[0][:-reverse].decode("utf-8", errors="ignore")

        @classmethod
        def from_empty(cls, empty):
            array = [bytes(fillName(empty.name, 64), "ascii")]
            tag = cls(array)
            return tag

        def to_bytes(self):
            new_bytes = bytearray()
            new_bytes += bytes(fillName(self.name, 64), "ascii")
            return new_bytes


def ImportTAN(VFS,
              model_name,
              material_mapping,
              import_tags=False,
              animations=None,
              per_object_import=False,
              tiki_scale=1.0):
    """ Returns a list of meshes from tan surfaces.
    If per_object_import is false, all surfaces are
    merged together and a list with one mesh is returned.
    Animations is either None or an empty list. This list
    is filled on import with animation frames."""

    mesh = None
    skip = False

    if not VFS:
        try:
            file = open(model_name, "rb")
        except Exception:
            print("Couldn't open " + model_name + " \n")
            return [mesh]

        byte_array = bytearray(file.read())
        file.close()
    else:
        byte_array = VFS.get(model_name)
        if not byte_array:
            return [mesh]

    offset = 0
    magic_nr = byte_array[offset:offset + 4]
    offset += 4
    version_nr = struct.unpack("<i", byte_array[offset:offset + 4])[0]
    offset += 4

    tan = TAN(magic_nr, version_nr)
    if (not tan.valid):
        print("this tan version is not supported\n")
        skip = True

    if (not skip):
        name = byte_array[offset:offset+64].decode(
            "utf-8",
            errors="ignore").strip("\0")
        offset += 64
        print("Import TAN: " + name)
        numFrames = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        numTags = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        numSurfaces = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        total_time = struct.unpack("<f", byte_array[offset:offset+4])[0]
        offset += 4
        total_delta = struct.unpack("<fff", byte_array[offset:offset+12])
        offset += 12
        ofsFrames = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        ofsSurfaces = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        ofsTags = struct.unpack("<16i", byte_array[offset:offset+(16*4)])
        offset += 16*4
        ofsEnd = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4

        debug = False
        if debug is True:
            print("numFrames: " + str(numFrames))
            print("numTags: " + str(numTags))
            print("numSurfaces: " + str(numSurfaces))
            print("total_time: " + str(total_time))
            print("total_delta: " + str(total_delta))

            print("ofsFrames: " + str(ofsFrames))
            for i in range(16):
                print("ofsTags" + str(i) + ": " + str(ofsTags[i]))
            print("ofsSurfaces: " + str(ofsSurfaces))
            print("ofsEnd: " + str(ofsEnd))

        frames = lump(tan.frame)
        frames.set_offset_count([ofsFrames, numFrames])
        frames.read_from_bytearray(byte_array)
        if debug is True:
            for frame_id, frame in enumerate(frames.data):
                print("\tFrame Nr " + str(frame_id))
                print("\t\tMINs: " + str(frame.min_bounds))
                print("\t\tMAXs: " + str(frame.max_bounds))
                print("\t\tOrigin: " + str(frame.offset))
                print("\t\tRadius: " + str(frame.radius))
                print("\t\tScale: " + str(frame.scale))

        surface_lumps = []
        for surface_lump in range(numSurfaces):
            surface = lump(tan.surface)
            surface.set_offset_count([ofsSurfaces, 1])
            surface.read_from_bytearray(byte_array)

            surface.data[0].vertices.read_from_bytearray(
                byte_array, ofsSurfaces)
            # decode vertex positions
            for vertex in surface.data[0].vertices.data:
                vertex.position[0] = vertex.position[0] * \
                    frames.data[0].scale[0] + frames.data[0].offset[0]
                vertex.position[1] = vertex.position[1] * \
                    frames.data[0].scale[1] + frames.data[0].offset[1]
                vertex.position[2] = vertex.position[2] * \
                    frames.data[0].scale[2] + frames.data[0].offset[2]

            surface.data[0].tcs.read_from_bytearray(
                byte_array, ofsSurfaces)
            # surface.data[0].collapse_map.read_from_bytearray(
            #   file,ofsSurfaces)
            surface.data[0].triangles.read_from_bytearray(
                byte_array, ofsSurfaces)

            if animations is not None:
                if per_object_import:
                    animations.append([[0, surface.data[0].vertices.data]])
                else:
                    if len(animations) == 0:
                        animations.append([[0, surface.data[0].vertices.data]])
                    else:
                        animations[0][0][1] += surface.data[0].vertices.data

                for frame in range(1, surface.data[0].n_frames):
                    current_frame_vertices = (
                        surface.data[0].get_frame_vertex_lump(frame))
                    current_frame_vertices.read_from_bytearray(
                        byte_array, ofsSurfaces)
                    # decode vertex positions
                    for vertex in current_frame_vertices.data:
                        vertex.position[0] = vertex.position[0] * \
                            frames.data[0].scale[0] + frames.data[0].offset[0]
                        vertex.position[1] = vertex.position[1] * \
                            frames.data[0].scale[1] + frames.data[0].offset[1]
                        vertex.position[2] = vertex.position[2] * \
                            frames.data[0].scale[2] + frames.data[0].offset[2]

                    if per_object_import:
                        animations[surface_lump].append(
                            [frame, current_frame_vertices.data])
                    else:
                        if frame >= len(animations[0]):
                            animations[0].append(
                                [frame, current_frame_vertices.data])
                        else:
                            animations[0][frame][1] += (
                                current_frame_vertices.data)

            surface_lumps.append(surface)
            ofsSurfaces += surface.data[0].off_end

        if import_tags:
            for tag_id in range(numTags):
                tag_lump = lump(tan.tag)
                tag_lump.set_offset_count([ofsTags[tag_id], 1])
                tag_lump.read_from_bytearray(byte_array)

                tag_data_lump = lump(tan.tag_data)
                tag_data_lump.set_offset_count(
                    [ofsTags[tag_id] + tan.tag.size, numFrames])
                tag_data_lump.read_from_bytearray(byte_array)

                bpy.ops.object.empty_add(type="ARROWS")
                tag_obj = bpy.context.object
                tag_obj.name = tag_lump.data[0].name
                matrix = Matrix.Identity(4)
                matrix[0] = [*tag_data_lump.data[0].axis_1, 0.0]
                matrix[1] = [*tag_data_lump.data[0].axis_2, 0.0]
                matrix[2] = [*tag_data_lump.data[0].axis_3, 0.0]
                matrix.transpose()
                matrix.translation = tag_data_lump.data[0].origin
                tag_obj.matrix_world = matrix
                if animations is not None:
                    tag_obj.keyframe_insert(
                        'location', frame=0, group='LocRot')
                    tag_obj.keyframe_insert(
                        'rotation_euler', frame=0, group='LocRot')
                    for frame in range(1, numFrames):
                        matrix = Matrix.Identity(4)
                        matrix[0] = [*tag_data_lump.data[frame].axis_1, 0.0]
                        matrix[1] = [*tag_data_lump.data[frame].axis_2, 0.0]
                        matrix[2] = [*tag_data_lump.data[frame].axis_3, 0.0]
                        matrix.transpose()
                        matrix.translation = tag_data_lump.data[frame].origin
                        tag_obj.matrix_world = matrix
                        tag_obj.keyframe_insert(
                            'location', frame=frame, group='LocRot')
                        tag_obj.keyframe_insert(
                            'rotation_euler', frame=frame, group='LocRot')

        vertex_pos = []
        vertex_nor = []
        vertex_tc = []
        face_indices = []
        face_tcs = []
        face_shaders = []
        shaderindex = 0
        face_index_offset = 0
        face_material_index = []
        meshes = []

        # vertex groups
        surfaces = {}
        for surface_id, surface in enumerate(surface_lumps):
            if debug is True:
                print("\tSurface Nr " + str(surface_id))
            n_indices = 0
            surface_indices = []
            for vertex, tc in zip(surface.data[0].vertices.data,
                                  surface.data[0].tcs.data):
                vertex_pos.append(vertex.position)
                vertex_nor.append(vertex.normal)
                vertex_tc.append(tc.tc)
                n_indices += 1

            for triangle in surface.data[0].triangles.data:
                triangle_indices = [triangle.indices[0] + face_index_offset,
                                    triangle.indices[1] + face_index_offset,
                                    triangle.indices[2] + face_index_offset]
                
                if (triangle_indices[0] == triangle_indices[1] or
                    triangle_indices[0] == triangle_indices[2] or
                    triangle_indices[1] == triangle_indices[2]):
                    continue

                surface_indices.append(triangle_indices)
                face_indices.append(triangle_indices)

                face_tcs.append(vertex_tc[triangle_indices[0]])
                face_tcs.append(vertex_tc[triangle_indices[1]])
                face_tcs.append(vertex_tc[triangle_indices[2]])
                face_material_index.append(shaderindex)

            if debug is True:
                print("\t\tnumTriangles: " +
                    str(len(surface.data[0].triangles.data)))

            if material_mapping is not None and (
                    surface.data[0].name.lower() in material_mapping):
                mat_name = material_mapping[surface.data[0].name.lower()]
            else:
                mat_name = surface.data[0].name

            face_shaders.append(mat_name)
            shaderindex += 1
            face_index_offset += n_indices

            if per_object_import:
                mesh = bpy.data.meshes.new(surface.data[0].name)
                mesh.from_pydata(vertex_pos, [], face_indices)

                mat = bpy.data.materials.get(mat_name)
                if (mat is None):
                    mat = bpy.data.materials.new(name=mat_name)
                mesh.materials.append(mat)
                mesh.polygons.foreach_set(
                    "material_index", face_material_index)

                if bpy.app.version < (4, 1, 0):
                    mesh.use_auto_smooth = True

                for poly in mesh.polygons:
                    poly.use_smooth = True
                mesh.vertices.foreach_set("normal", unpack_list(vertex_nor))
                mesh.normals_split_custom_set_from_vertices(vertex_nor)

                mesh.uv_layers.new(do_init=False, name="UVMap")
                mesh.uv_layers["UVMap"].data.foreach_set(
                    "uv", unpack_list(face_tcs))

                mesh.validate()
                mesh.update()
                mesh["Tiki_Scale"] = tiki_scale
                meshes.append(mesh)

                vertex_pos = []
                vertex_nor = []
                vertex_tc = []
                face_indices = []
                face_tcs = []
                face_shaders = []
                shaderindex = 0
                face_index_offset = 0
                face_material_index = []

        if per_object_import:
            return meshes
        
        if len(vertex_pos) == 0:
            return [mesh]

        guessed_name = guess_model_name(model_name.lower()).lower()
        if guessed_name.endswith(".tan"):
            guessed_name = guessed_name[:-len(".tan")]

        mesh = bpy.data.meshes.new(guessed_name)
        mesh.from_pydata(vertex_pos, [], face_indices)

        for texture_instance in face_shaders:
            mat = bpy.data.materials.get(texture_instance)
            if (mat is None):
                mat = bpy.data.materials.new(name=texture_instance)
            mesh.materials.append(mat)

        mesh.polygons.foreach_set("material_index", face_material_index)

        if bpy.app.version < (4, 1, 0):
            mesh.use_auto_smooth = True

        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.vertices.foreach_set("normal", unpack_list(vertex_nor))
        mesh.normals_split_custom_set_from_vertices(vertex_nor)

        mesh.uv_layers.new(do_init=False, name="UVMap")
        mesh.uv_layers["UVMap"].data.foreach_set("uv", unpack_list(face_tcs))

        mesh.validate()
        mesh.update()
        mesh["Tiki_Scale"] = tiki_scale

    return [mesh]


def ImportTANObject(VFS,
                    file_path,
                    material_mapping,
                    import_tags,
                    per_object_import=False,
                    import_animations=True,
                    tiki_scale=1.0):
    animations = []
    meshes = ImportTAN(VFS,
                       file_path,
                       material_mapping,
                       import_tags,
                       animations if import_animations else None,
                       per_object_import,
                       tiki_scale)
    objs = []
    for id, mesh in enumerate(meshes):
        if mesh is not None:
            ob = bpy.data.objects.new(mesh.name, mesh)
            if "Tiki_Scale" in mesh:
                ob.scale = (mesh["Tiki_Scale"], mesh["Tiki_Scale"], mesh["Tiki_Scale"])
            bpy.context.collection.objects.link(ob)
            if import_animations and animations[id] is not None:
                ob.shape_key_add(name=str(0))
                ob.data.shape_keys.use_relative = False
                ob.data.shape_keys.eval_time = 0
                ob.data.shape_keys.keyframe_insert('eval_time', frame=0)
                # Set vertex data
                for frame in range(1, len(animations[id])):
                    shape_key = ob.shape_key_add(name=str(frame))
                    vertices = shape_key.data
                    for index, vertex in enumerate(vertices):
                        vertex.co = animations[id][frame][1][index].position
                # Set animation data
                for frame in range(1, len(animations[id])):
                    # Why blender, why 10?
                    ob.data.shape_keys.eval_time = (
                        animations[id][frame][0] * 10.0)
                    ob.data.shape_keys.keyframe_insert(
                        'eval_time', frame=animations[id][frame][0])

            objs.append(ob)
    return objs


def ExportTAN(file_path,
              objects,
              frame_list,
              individual,
              material_mapping=None,
              material_merge=True):
    return_status = [False, "Unknown Error"]
    splitted_path = file_path.split("/")
    model_name = splitted_path[len(splitted_path)-1]

    if frame_list:
        bpy.context.scene.frame_set(frame_list[0])

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_objects = [obj.evaluated_get(depsgraph) for obj in objects]

    eval_mesh_objects = [obj for obj in eval_objects if obj.type == "MESH"]
    eval_tag_objects = [obj for obj in eval_objects if obj.type == "EMPTY"]

    sf = surface_factory(eval_mesh_objects, individual,
                         material_mapping, material_merge)
    if not sf.valid:
        return_status[1] = sf.status
        return return_status

    surface_descriptors = sf.surface_descriptors

    if sf.num_surfaces > 32:
        return_status[1] = "Can't export this model because it's too detailed"
        return return_status

    surface_bytes = bytearray()
    frame = TAN.frame.from_objects(eval_mesh_objects, individual)
    frame_bytes = frame.to_bytes()
    tags_bytes = bytearray()

    surface_size = 0
    surfaces = []
    tags = []
    tag_data = {}
    for surf in surface_descriptors:
        new_surface = TAN.surface.from_surface_descriptor(surf)
        new_surface.apply_scale_offset(frame.scale, frame.offset)
        surfaces.append(new_surface)

    for empty in eval_tag_objects:
        new_tag = TAN.tag.from_empty(empty)
        tags.append(new_tag)
        tag_data[new_tag.name] = [TAN.tag_data.from_empty(empty)]

    for frame in frame_list[1:]:
        sf.clear_meshes()
        bpy.context.scene.frame_set(frame)
        depsgraph.update()
        sf.update_meshes()

        frame = TAN.frame.from_objects(eval_mesh_objects, individual)

        for surf_id, surf in enumerate(surface_descriptors):
            surfaces[surf_id].add_current_frame(
                surf, frame.scale, frame.offset)

        for tag_id, empty in enumerate(eval_tag_objects):
            tag_data[tags[tag_id].name].append(TAN.tag_data.from_empty(empty))

        frame_bytes += frame.to_bytes()

    for new_surface in surfaces:
        surface_bytes += new_surface.to_bytes()
        surface_size += new_surface.size
        surface_size += new_surface.vertices.size
        surface_size += new_surface.triangles.size
        surface_size += new_surface.tcs.size
        surface_size += new_surface.collapse_map.size

    for tag_id, new_tag in enumerate(tags):
        tags_bytes += new_tag.to_bytes()
        for frame in range(len(frame_list)):
            tags_bytes += tag_data[new_tag.name][frame].to_bytes()

    tan_bytes = bytearray()
    tan_bytes += (b'TAN ')
    tan_bytes += (struct.pack("<i", 2))
    tan_bytes += bytes(fillName(model_name, 64), "utf-8")
    tan_bytes += (struct.pack("<i", len(frame_list)))  # n_frames
    tan_bytes += (struct.pack("<i", len(tags)))  # n_tags
    tan_bytes += (struct.pack("<i", len(surface_descriptors)))  # n_surfaces
    tan_bytes += (struct.pack("<f", len(frame_list) * 1.0/20.0))  # total_time
    tan_bytes += (struct.pack("<fff", 0.0, 0.0, 0.0))  # total_delta

    ofsFrames = INT + INT + STRING + INT + INT + \
        INT + FLOAT + FLOAT + FLOAT + FLOAT + 19*INT
    tan_bytes += (struct.pack("<i", ofsFrames))

    ofsSurfaces = ofsFrames + TAN.frame.size * len(frame_list)
    tan_bytes += (struct.pack("<i", ofsSurfaces))

    # size of one tag in the file
    tag_size = TAN.tag_data.size*len(frame_list) + TAN.tag.size

    ofsTags = ofsSurfaces + surface_size
    for i in range(16):
        if i >= len(tags):
            tan_bytes += (struct.pack("<i", 0))
        else:
            tan_bytes += (struct.pack("<i", ofsTags + i * tag_size))

    ofsEof = ofsTags + len(tags) * tag_size
    tan_bytes += (struct.pack("<i", ofsEof))

    tan_bytes += frame_bytes
    tan_bytes += surface_bytes
    tan_bytes += tags_bytes

    f = open(file_path, "wb")
    try:
        f.write(tan_bytes)
    except Exception:
        return_status[1] = "Couldn't write file"
        return return_status
    f.close()

    return [True, "Everything is fine"]


def TIK_TO_DICT(VFS, file_path):
    dict = {}
    tik_bytearray = VFS.get(file_path)
    lines = tik_bytearray.decode(encoding="latin-1").splitlines()
    dict_key = ""
    is_open = 0
    for line in lines:
        line = line.lower().strip(" \t\r\n").replace("\t", " ")
        # comments
        if line.startswith("//"):
            continue
        if line.startswith("{"):
            is_open += 1
            continue
        if line.startswith("}"):
            is_open -= 1
            continue
        if is_open == 0:
            dict[line] = {}
            dict_key = line
        elif is_open == 1:
            key, value = parse(line)
            if dict_key == "setup" and key == "path":
                if not value.endswith("/"):
                    value = value + "/"
            if dict_key == "setup" and key == "surface":
                arguments = value.split()
                if "material_mapping" not in dict[dict_key]:
                    dict[dict_key]["material_mapping"] = {}
                shader_name = arguments[2].lower()
                base_path = ""
                if "path" in dict["setup"]:
                    base_path = dict["setup"]["path"]
                if shader_name.startswith(base_path):
                    base_path = ""
                if not shader_name.endswith(".tga"):
                    dict[dict_key]["material_mapping"][arguments[0].lower()
                                                       ] = shader_name
                else:
                    dict[dict_key]["material_mapping"][arguments[0].lower(
                    )] = base_path + shader_name
            dict[dict_key][key] = value
    return dict

# TODO: parse scale and other fields


def ImportTIK(VFS,
              file_path,
              zoffset,
              import_tags=False,
              animations=None,
              per_object_import=False):
    
    dict = TIK_TO_DICT(VFS, file_path)
    material_mapping = None
    current_path = ""
    model_to_load = ""
    tiki_scale = 1.0
    if "setup" in dict:
        if "material_mapping" in dict["setup"]:
            material_mapping = dict["setup"]["material_mapping"]
        if "path" in dict["setup"]:
            current_path = dict["setup"]["path"]
        if "scale" in dict["setup"]:
            try:
                tiki_scale = float(dict["setup"]["scale"])
            except Exception:
                tiki_scale = 1.0
    if "animations" in dict:
        if "idle" in dict["animations"]:
            model_to_load = dict["animations"]["idle"]
        else:
            print("Idle animation not found in .tik file", file_path)
            return None
    else:
        print("Animations not found in .tik file", file_path)
        return None

    model_path = current_path + model_to_load
    if not model_path.endswith(".tan"):
        print("Only .tan models are currently supported. Tried loading: " +
              dict["setup"]["path"] + dict["animations"]["idle"])
    return ImportTAN(VFS,
                     model_path,
                     material_mapping,
                     import_tags,
                     animations,
                     per_object_import,
                     tiki_scale)


def ImportTIKObject(VFS,
                    file_path,
                    import_tags,
                    per_object_import=False):
    dict = TIK_TO_DICT(VFS, file_path)
    material_mapping = None
    current_path = ""
    model_to_load = ""
    tiki_scale = 1.0
    if "setup" in dict:
        if "material_mapping" in dict["setup"]:
            material_mapping = dict["setup"]["material_mapping"]
        if "path" in dict["setup"]:
            current_path = dict["setup"]["path"]
        if "scale" in dict["setup"]:
            try:
                tiki_scale = float(dict["setup"]["scale"])
            except Exception:
                tiki_scale = 1.0
    if "animations" in dict:
        if "idle" in dict["animations"]:
            model_to_load = dict["animations"]["idle"]
        else:
            print("Idle animation not found in .tik file", file_path)
            return None
    else:
        print("Animations not found in .tik file", file_path)
        return None
    
    model_path = current_path + model_to_load
    if not model_path.endswith(".tan"):
        print("Only .tan models are currently supported. Tried loading: " +
              dict["setup"]["path"] + dict["animations"]["idle"])
    return ImportTANObject(VFS,
                           model_path,
                           material_mapping,
                           import_tags,
                           per_object_import,
                           True,
                           tiki_scale)


def ExportTIK_TAN(file_path,
                  subpath,
                  objects,
                  frame_list,
                  individual,
                  material_merge=True):
    return_status = [False, "Unknown Error"]

    tik_path, tik_name = file_path.rsplit("/", 1)
    tan_name = tik_name
    if tan_name.endswith(".tik"):
        tan_name = tan_name[:-len(".tik")] + ".tan"

    base_path = "models/" + tik_path.rsplit("/models/", 1)[1]

    print(base_path)
    print(tan_name)
    print(tik_path+subpath+tan_name)

    material_mapping = {}

    # export tan first, so we can get the material mapping correct
    try:
        os.makedirs(tik_path+subpath, exist_ok=True)
        return_status = ExportTAN(tik_path+subpath+tan_name,
                                  objects,
                                  frame_list,
                                  individual,
                                  material_mapping,
                                  material_merge)
    except Exception:
        return_status[1] = "Couldn't write tan file"
        return return_status

    f = open(file_path, "w")
    try:
        f.write("TIKI\n\n")
        f.write("setup\n{\n")
        f.write("\tscale 1\n")
        f.write("\tfade_dist_mod 1\n")
        path_variable = base_path + subpath[:-1]
        print(path_variable)
        f.write("\tpath " + path_variable + "\n")
        for material in material_mapping:
            f.write("\tsurface " + str(material) + " shader " +
                    str(material_mapping[material]) + "\n")
        f.write("}\n\n")
        f.write("init\n{\n")
        f.write("\tserver\n")
        f.write("\t{\n")
        f.write("\t}\n")
        f.write("\tclient\n")
        f.write("\t{\n")
        f.write("\t}\n")
        f.write("}\n\n")
        f.write("animations\n{\n")
        f.write("\tidle\t" + tan_name + "\n")
        f.write("}\n\r")
    except Exception:
        return_status[1] = "Couldn't write tik file"
        return return_status
    f.close()

    return (True, "Everything is fine")
