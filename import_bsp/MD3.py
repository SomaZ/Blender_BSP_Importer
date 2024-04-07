import bpy
import struct
from math import pi, sin, cos, atan2, acos, sqrt
from mathutils import Matrix
from bpy_extras.io_utils import unpack_list

from . import BlenderImage
from .BlenderSurfaceFactory import Surface_factory
from .idtech3lib.Parsing import guess_model_name, fillName


FLOAT = 4
HALF = 2
INT = 4
UBYTE = 1
STRING = 64

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


class md3_array:
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


class MD3:
    MD3_MAGIC = b'IDP3'
    MD3_VERSION = 15

    def __init__(self, magic, version):
        self.valid = magic == self.MD3_MAGIC and version == self.MD3_VERSION

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
        encoding = "<4s64siiiiiiiiii"
        size = struct.calcsize(encoding)

        def __init__(self, array):

            first_0 = 64
            for pos, i in enumerate(array[1]):
                if i == 0:
                    first_0 = pos
                    break
            reverse = 64-first_0
            self.magic = array[0]
            self.name = array[1][:-reverse].decode("utf-8", errors="ignore")
            self.flags = array[2]
            self.n_frames = array[3]
            self.n_shaders = array[4]
            self.n_verts = array[5]
            self.n_tris = array[6]
            self.off_tris = array[7]
            self.off_shaders = array[8]
            self.off_tcs = array[9]
            self.off_verts = array[10]
            self.off_end = array[11]

            self.vertices = md3_array(
                self.vertex, [self.off_verts, self.n_verts])
            self.tcs = md3_array(
                self.tc, [self.off_tcs, self.n_verts])
            self.shaders = md3_array(
                self.shader, [self.off_shaders, self.n_shaders])
            self.triangles = md3_array(
                self.triangle, [self.off_tris, self.n_tris])

        def get_frame_vertex_lump(self, frame):
            if frame > self.n_frames:
                return None
            return md3_array(
                self.vertex,
                [self.off_verts + frame*self.n_verts*self.vertex.size,
                 self.n_verts])

        @classmethod
        def from_surface_descriptor(cls, sd):
            array = [None for i in range(12)]
            array[0] = b'IDP3'
            array[1] = bytes(fillName(sd.obj_name, 64), "ascii")
            array[2] = 0  # flags
            array[3] = 1  # n_frames
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

            new_shader = cls.shader(
                [bytes(fillName(sd.material, 64), "ascii"), 0])
            surface.shaders.data.append(new_shader)
            return surface

        def add_current_frame(self, sd):
            self.n_frames += 1
            for map in sd.vertex_mapping:
                mesh = map.mesh
                new_vertex = self.vertex.from_vertex(mesh.vertices[map.vert])
                if mesh.has_custom_normals:
                    new_vertex.normal = mesh.loops[map.loop].normal.copy()

                self.vertices.data.append(new_vertex)

        def to_bytes(self):
            new_bytes = bytearray()
            new_bytes += (self.magic)
            new_bytes += bytes(fillName(self.name, 64), "ascii")
            new_bytes += (struct.pack("<i", self.flags))
            new_bytes += (struct.pack("<i", self.n_frames))

            shaders = self.shaders.to_bytes()
            # n_shaders
            new_bytes += (struct.pack("<i", self.shaders.count))

            vertices = self.vertices.to_bytes()
            # n_verts
            n_verts = self.vertices.count / self.n_frames
            if n_verts.is_integer():
                n_verts = int(n_verts)
            new_bytes += (struct.pack("<i", n_verts))

            triangles = self.triangles.to_bytes()
            # n_tris
            new_bytes += (struct.pack("<i", self.triangles.count))

            tcs = self.tcs.to_bytes()

            # shaders need to be the first as the offset determined as
            # header offset in md3 view...
            header_offset = self.size
            shaders_offset = header_offset

            tris_offset = shaders_offset + self.shaders.size
            tcs_offset = tris_offset + self.triangles.size
            vert_offset = tcs_offset + self.tcs.size
            end_offset = vert_offset + self.vertices.size

            # shader offset still second in the cue -.-
            new_bytes += (struct.pack("<i", tris_offset))
            new_bytes += (struct.pack("<i", shaders_offset))
            new_bytes += (struct.pack("<i", tcs_offset))
            new_bytes += (struct.pack("<i", vert_offset))
            new_bytes += (struct.pack("<i", end_offset))

            new_bytes += shaders
            new_bytes += triangles
            new_bytes += tcs
            new_bytes += vertices

            return new_bytes

        class shader:
            encoding = "<64si"
            size = struct.calcsize(encoding)

            def __init__(self, array):

                first_0 = 64
                for pos, i in enumerate(array[0]):
                    if i == 0:
                        first_0 = pos
                        break
                reverse = 64-first_0

                self.name = BlenderImage.remove_file_extension(
                    array[0][:-reverse].decode("utf-8", errors="ignore"))
                self.index = array[1]

            def to_array(self):
                array = [None for i in range(2)]
                name = self.name.split(".")[0]
                array[0] = bytes(fillName(name, 64), "ascii")
                array[1] = self.index
                return array

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
            encoding = "<3h2s"
            size = struct.calcsize(encoding)

            def __init__(self, array):
                self.position = [array[0]/64.0, array[1]/64.0, array[2]/64.0]
                self.normal = MD3.decode_normal(array[3])

            @classmethod
            def from_vertex(cls, vertex):
                vert = cls([0.0, 0.0, 0.0, [0, 0]])
                vert.position = vertex.co.copy()
                vert.normal = vertex.normal.copy()
                return vert

            def to_array(self):
                array = [None for i in range(4)]
                array[0] = int(self.position[0] * 64.0)
                array[1] = int(self.position[1] * 64.0)
                array[2] = int(self.position[2] * 64.0)
                array[3] = MD3.encode_normal(self.normal)
                return array

    class frame:
        encoding = "<3f3f3ff16s"
        size = struct.calcsize(encoding)

        def __init__(self, array):
            self.min_bounds = [array[0], array[1], array[2]]
            self.max_bounds = [array[3], array[4], array[5]]
            self.local_origin = [array[6], array[7], array[8]]
            self.radius = array[9]

            first_0 = 64
            for pos, i in enumerate(array[10]):
                if i == 0:
                    first_0 = pos
                    break
            reverse = 64-first_0

            self.name = array[10][:-reverse].decode("ascii", errors="ignore")

        @classmethod
        def from_objects(cls, objects, individual):
            array = [0.0 for i in range(10)]
            array.append(bytes(fillName("test", 16), "ascii"))
            frame = cls(array)

            frame.min_bounds = [512, 512, 512]
            frame.max_bounds = [-512, -512, -512]

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

            x = frame.min_bounds[0] + \
                (frame.max_bounds[0] - frame.min_bounds[0]) / 2
            y = frame.min_bounds[1] + \
                (frame.max_bounds[1] - frame.min_bounds[1]) / 2
            z = frame.min_bounds[2] + \
                (frame.max_bounds[2] - frame.min_bounds[2]) / 2
            frame.local_origin = x, y, z
            r1 = frame.max_bounds[0] - x
            r2 = frame.max_bounds[1] - y
            r3 = frame.max_bounds[2] - z
            frame.radius = sqrt(r1*r1 + r2*r2 + r3*r3)
            return frame

        def to_bytes(self):
            new_bytes = bytearray()
            new_bytes += (struct.pack("<3f", *self.min_bounds))
            new_bytes += (struct.pack("<3f", *self.max_bounds))
            new_bytes += (struct.pack("<3f", *self.local_origin))
            new_bytes += (struct.pack("<f", self.radius))
            new_bytes += bytes(fillName(self.name, 16), "ascii")
            return new_bytes

    class tag:
        encoding = "<64s3f3f3f3f"
        size = struct.calcsize(encoding)

        def __init__(self, array):
            first_0 = 64
            for pos, i in enumerate(array[0]):
                if i == 0:
                    first_0 = pos
                    break
            reverse = 64-first_0

            self.name = array[0][:-reverse].decode("utf-8", errors="ignore")
            self.origin = [array[1], array[2], array[3]]
            self.axis_1 = [array[4], array[5], array[6]]
            self.axis_2 = [array[7], array[8], array[9]]
            self.axis_3 = [array[10], array[11], array[12]]

        @classmethod
        def from_empty(cls, empty):
            array = [bytes(fillName(empty.name, 64), "ascii")]
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
            new_bytes += bytes(fillName(self.name, 64), "ascii")
            new_bytes += (struct.pack("<3f", *self.origin))
            new_bytes += (struct.pack("<3f", *self.axis_1))
            new_bytes += (struct.pack("<3f", *self.axis_2))
            new_bytes += (struct.pack("<3f", *self.axis_3))
            return new_bytes


def ImportMD3(VFS,
              model_name,
              zoffset,
              import_tags=False,
              animations=None,
              per_object_import=False):
    """ Returns a list of meshes from md3 surfaces.
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

    md3 = MD3(magic_nr, version_nr)
    if (not md3.valid):
        print("this md3 version is not supported\n")
        skip = True

    if (not skip):
        name = byte_array[offset:offset+64].decode(
            "utf-8",
            errors="ignore").strip("\0")
        offset += 64
        print("Import MD3: " + name)
        flags = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        numFrames = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        numTags = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        numSurfaces = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        numSkins = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        ofsFrames = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        ofsTags = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        ofsSurfaces = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4
        ofsEnd = struct.unpack("<i", byte_array[offset:offset+4])[0]
        offset += 4

        debug = False
        if debug is True:
            print("flags: " + str(flags))
            print("numFrames: " + str(numFrames))
            print("numTags: " + str(numTags))
            print("numSurfaces: " + str(numSurfaces))
            print("numSkins: " + str(numSkins))

            print("ofsFrames: " + str(ofsFrames))
            print("ofsTags: " + str(ofsTags))
            print("ofsSurfaces: " + str(ofsSurfaces))
            print("ofsEnd: " + str(ofsEnd))

        surface_lumps = []
        for surface_lump in range(numSurfaces):
            surface = lump(md3.surface)
            surface.set_offset_count([ofsSurfaces, 1])
            surface.read_from_bytearray(byte_array)
            surface.data[0].vertices.read_from_bytearray(
                byte_array,
                ofsSurfaces)
            surface.data[0].tcs.read_from_bytearray(
                byte_array,
                ofsSurfaces)
            surface.data[0].shaders.read_from_bytearray(
                byte_array,
                ofsSurfaces)
            surface.data[0].triangles.read_from_bytearray(
                byte_array,
                ofsSurfaces)

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
                        byte_array,
                        ofsSurfaces)
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

        frames = lump(md3.frame)
        frames.set_offset_count([ofsFrames, numFrames])
        frames.read_from_bytearray(byte_array)
        if debug is True:
            for frame_id, frame in enumerate(frames.data):
                print("\tFrame Nr " + str(frame_id))
                print("\t\tName: " + str(frame.name))
                print("\t\tLocal Origin: " + str(frame.local_origin))
                print("\t\tRadius: " + str(frame.radius))

        if import_tags:
            tag_lump = lump(md3.tag)
            tag_lump.set_offset_count([ofsTags, numTags*numFrames])
            tag_lump.read_from_bytearray(byte_array)

            for tag in range(numTags):
                bpy.ops.object.empty_add(type="ARROWS")
                tag_obj = bpy.context.object
                tag_obj.name = tag_lump.data[tag].name
                matrix = Matrix.Identity(4)
                matrix[0] = [*tag_lump.data[tag].axis_1, 0.0]
                matrix[1] = [*tag_lump.data[tag].axis_2, 0.0]
                matrix[2] = [*tag_lump.data[tag].axis_3, 0.0]
                matrix.transpose()
                matrix.translation = tag_lump.data[tag].origin
                tag_obj.matrix_world = matrix
                if animations is not None:
                    tag_obj.keyframe_insert(
                        'location', frame=0, group='LocRot')
                    tag_obj.keyframe_insert(
                        'rotation_euler', frame=0, group='LocRot')
                    for frame in range(1, numFrames):
                        tag_id = tag + frame * numTags
                        matrix = Matrix.Identity(4)
                        matrix[0] = [*tag_lump.data[tag_id].axis_1, 0.0]
                        matrix[1] = [*tag_lump.data[tag_id].axis_2, 0.0]
                        matrix[2] = [*tag_lump.data[tag_id].axis_3, 0.0]
                        matrix.transpose()
                        matrix.translation = tag_lump.data[tag_id].origin
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
                print("\t\tnumShaders: " + str(len(surface.data[0].shaders.data)))
                for shader_id, shader in enumerate(surface.data[0].shaders.data):
                    print("\t\t\t" + str(shader_id) + ": " + str(shader.name))

            surfaces[surface.data[0].name] = unpack_list(surface_indices)
            face_shaders.append(surface.data[0].shaders.data[0])
            shaderindex += 1
            face_index_offset += n_indices

            if per_object_import:
                mesh = bpy.data.meshes.new(surface.data[0].name)
                mesh.from_pydata(vertex_pos, [], face_indices)

                mat = bpy.data.materials.get(
                    surface.data[0].shaders.data[0].name)
                if (mat is None):
                    mat = bpy.data.materials.new(
                        name=surface.data[0].shaders.data[0].name)
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
        if guessed_name.endswith(".md3"):
            guessed_name = guessed_name[:-len(".md3")]

        mesh = bpy.data.meshes.new(guessed_name)
        mesh.from_pydata(vertex_pos, [], face_indices)

        # oh man...
        if zoffset == 0:
            material_suffix = ".grid"
        else:
            material_suffix = "." + str(zoffset) + "grid"

        for texture_instance in face_shaders:
            mat = bpy.data.materials.get(
                texture_instance.name + material_suffix)
            if (mat is None):
                mat = bpy.data.materials.new(
                    name=texture_instance.name + material_suffix)
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

    return [mesh]


def ImportMD3Object(VFS, file_path, import_tags, per_object_import=False, import_animations=True):
    animations = []
    meshes = ImportMD3(VFS,
                       file_path,
                       0,
                       import_tags,
                       animations if import_animations else None,
                       per_object_import)
    objs = []
    for id, mesh in enumerate(meshes):
        if mesh is not None:
            ob = bpy.data.objects.new(mesh.name, mesh)
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
                    ob.data.shape_keys.eval_time = (animations[id][frame][0] *
                                                    10.0)
                    ob.data.shape_keys.keyframe_insert(
                        'eval_time', frame=animations[id][frame][0])

            objs.append(ob)
    return objs


def ExportMD3(file_path,
              objects,
              frame_list,
              individual,
              material_merge=True,
              MD3_SHADER_MAX_VERTEXES=1000,
              MAX_SURFACES=32):
    return_status = [False, "Unknown Error"]
    model_name = guess_model_name(file_path)

    if frame_list:
        bpy.context.scene.frame_set(frame_list[0])

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_objects = [obj.evaluated_get(depsgraph) for obj in objects]

    eval_mesh_objects = [obj for obj in eval_objects if obj.type == "MESH"]
    eval_tag_objects = [obj for obj in eval_objects if obj.type == "EMPTY"]

    sf = Surface_factory(
        eval_mesh_objects,
        individual,
        material_merge,
        MD3_SHADER_MAX_VERTEXES,
        MAX_SURFACES)

    if not sf.valid:
        return_status[1] = sf.status
        return return_status

    surface_descriptors = sf.surface_descriptors

    if sf.num_surfaces > MAX_SURFACES:
        return_status[1] = "Can't export this model because it's too detailed for the chosen limits"
        return return_status

    # check for vertices lying outside of md3 position range
    for surf in surface_descriptors:
        for map in surf.vertex_mapping:
            mesh = map.mesh
            if max(mesh.vertices[map.vert].co) >= 512.0 or (
                    min(mesh.vertices[map.vert].co) < -512.0):
                return_status[1] = "Model exceeds MD3 bounds of 511.99 "
                "to -512.0 units per axis. Reposition model to fit into "
                "the bounds or scale down the model."
                return return_status

    surface_bytes = bytearray()
    frame_bytes = MD3.frame.from_objects(
        eval_mesh_objects, individual).to_bytes()
    tags_bytes = bytearray()

    surface_size = 0
    surfaces = []
    tags = []
    for surf in surface_descriptors:
        new_surface = MD3.surface.from_surface_descriptor(surf)
        surfaces.append(new_surface)

    for empty in eval_tag_objects:
        new_tag = MD3.tag.from_empty(empty)
        tags.append([new_tag])

    for frame in frame_list[1:]:
        sf.clear_meshes()
        bpy.context.scene.frame_set(frame)
        depsgraph.update()
        sf.update_meshes()

        for surf_id, surf in enumerate(surface_descriptors):
            surfaces[surf_id].add_current_frame(surf)

        for tag_id, empty in enumerate(eval_tag_objects):
            tags[tag_id].append(MD3.tag.from_empty(empty))

        frame_bytes += MD3.frame.from_objects(
            eval_mesh_objects, individual).to_bytes()

    for new_surface in surfaces:
        surface_bytes += new_surface.to_bytes()
        surface_size += new_surface.size
        surface_size += new_surface.vertices.size
        surface_size += new_surface.triangles.size
        surface_size += new_surface.tcs.size
        surface_size += new_surface.shaders.size

    for frame in range(len(frame_list)):
        for new_tag in tags:
            tags_bytes += new_tag[frame].to_bytes()

    md3_bytes = bytearray()
    md3_bytes += (b'IDP3')
    md3_bytes += (struct.pack("<i", 15))
    md3_bytes += bytes(fillName(model_name, 64), "utf-8")
    md3_bytes += (struct.pack("<i", 0))  # flags
    md3_bytes += (struct.pack("<i", len(frame_list)))  # n_frames
    md3_bytes += (struct.pack("<i", len(tags)))  # n_tags
    md3_bytes += (struct.pack("<i", len(surface_descriptors)))  # n_surfaces
    md3_bytes += (struct.pack("<i", 0))  # n_skins

    ofsFrames = INT + INT + STRING + INT + INT + \
        INT + INT + INT + INT + INT + INT + INT
    md3_bytes += (struct.pack("<i", ofsFrames))

    ofsTags = ofsFrames + MD3.frame.size * len(frame_list)  # n_frames
    md3_bytes += (struct.pack("<i", ofsTags))

    ofsSurfaces = ofsTags + MD3.tag.size * \
        len(tags) * len(frame_list)  # n_tags
    md3_bytes += (struct.pack("<i", ofsSurfaces))

    ofsEof = ofsSurfaces + surface_size
    md3_bytes += (struct.pack("<i", ofsEof))

    md3_bytes += frame_bytes
    md3_bytes += tags_bytes
    md3_bytes += surface_bytes

    f = open(file_path, "wb")
    try:
        f.write(md3_bytes)
    except Exception:
        return_status[1] = "Couldn't write file"
        return return_status
    f.close()

    return (True, "Everything is fine")
