#----------------------------------------------------------------------------#
#TODO:  refactor loading bsp files and md3 files, right now its a mess o.O
#----------------------------------------------------------------------------#
import imp

if "struct" not in locals():
    import struct
    
if "bpy" not in locals():
    import bpy
    
if "Image" in locals():
    imp.reload( Image )
else:
    from . import Image
    
from .Parsing import guess_model_name

from math import pi, sin, cos, atan2, acos
from mathutils import Matrix
from bpy_extras.io_utils import unpack_list
    
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
        
    def readFrom(self, file):
        
        if self.count == 0:
            self.count = self.size / self.data_class.size
            
        file.seek(self.offset)
        for i in range(int(self.count)):
            self.data.append(self.data_class(struct.unpack(self.data_class.encoding, file.read(self.data_class.size))))

class md3_array:
    def __init__(self, data_class, offset_count):
        self.data_class = data_class
        self.data = []
        self.offset = offset_count[0]
        self.count = offset_count[1]
    def readFrom(self, file, offset):
        file.seek(self.offset + offset)
        for i in range(int(self.count)):
            self.data.append(self.data_class(struct.unpack(self.data_class.encoding, file.read(self.data_class.size))))
    def to_bytes(self):
        self.count = len(self.data)
        self.size = self.count * self.data_class.size
        bytes = bytearray()
        print(self.data_class)
        for i in range(self.count):
            bytes+=(struct.pack(self.data_class.encoding, *self.data[i].to_array()))
        return bytes

def fillName(string, length):
    new_str = string[:length]
    while len(new_str) < length:
        new_str += "\0"
    return new_str
           
class MD3:
    MD3_MAGIC         = b'IDP3'
    MD3_VERSION       = 15
    
    def __init__(self, file, magic, version):
        self.file = file
        self.valid = magic == self.MD3_MAGIC and version == self.MD3_VERSION
    
    def decode_normal(packed):
        lat = packed[1] * ( 2 * pi / 255 )
        long = packed[0] * ( 2 * pi / 255 )
        x = cos(lat) * sin(long)
        y = sin(lat) * sin(long)
        z = cos(long)
        return [x, y, z]
    
    def encode_normal(normal):
        x, y, z = normal
        l = sqrt( ( x * x ) + ( y * y ) + ( z * z ) )
        if l == 0:
            print("zero length found!")
            return bytes((0, 0))
        x = x/l
        y = y/l
        z = z/l
        if x == 0 and y == 0:
            return bytes((0, 0)) if z > 0 else bytes((128, 0))
        long = int(round(atan2(y, x) * 255 / (2.0 * pi))) & 0xff
        lat  = int(round(acos(z) * 255 / (2.0 * pi))) & 0xff
        return bytes((lat, long))
    
    class surface:
        size = INT + STRING + INT + INT + INT + INT + INT + INT + INT + INT + INT + INT
        encoding = "<4s64siiiiiiiiii"
        def __init__(self, array):
            self.magic =        array[0]
            self.name =         array[1].decode("utf-8", errors="ignore").strip("\0")
            self.flags =        array[2]
            self.n_frames =     array[3]
            self.n_shaders =    array[4]
            self.n_verts =      array[5]
            self.n_tris =       array[6]
            self.off_tris =     array[7]
            self.off_shaders =  array[8]
            self.off_tcs =      array[9]
            self.off_verts =    array[10]
            self.off_end =      array[11]
            
            self.vertices =     md3_array(self.vertex,[self.off_verts, self.n_verts])
            self.tcs =          md3_array(self.tc,[self.off_tcs, self.n_verts])
            self.shaders =      md3_array(self.shader,[self.off_shaders, self.n_shaders])
            self.triangles =    md3_array(self.triangle,[self.off_tris, self.n_tris])
        
        @classmethod
        def from_mesh(cls, mesh):
            array = [None for i in range(12)]
            array[0] = b'IDP3'
            array[1] = bytes(fillName(mesh.name, 64),"ascii")
            array[2] = 0 #flags
            array[3] = 1 #n_frames
            surface = cls(array)
            
            surface.vertices.data = [None for i in range(len(mesh.vertices))]
            surface.tcs.data = [None for i in range(len(mesh.vertices))]
            
            for polygon in mesh.polygons:
                for vertex, loop in zip(polygon.vertices, polygon.loop_indices):
                    new_vertex = cls.vertex.from_vertex(mesh.vertices[vertex])
                    new_tc = cls.tc.from_loop(mesh.uv_layers.active.data[loop])
                    if mesh.has_custom_normals:
                        new_vertex.normal = mesh.loops[loop].normal 
                    surface.vertices.data[vertex] = new_vertex
                    surface.tcs.data[vertex] = new_tc
                
            for triangle in mesh.loop_triangles:
                new_triangle = cls.triangle.from_triangle(triangle)
                surface.triangles.data.append(new_triangle)
            
            new_shader = cls.shader([bytes(fillName(mesh.materials[0].name, 64),"ascii"), 0])
            surface.shaders.data.append(new_shader)
            
            return surface
            
        def to_bytes(self):
            new_bytes = bytearray()
            new_bytes+=(self.magic)
            new_bytes+= bytes(fillName(self.name, 64),"ascii")
            new_bytes+=(struct.pack("<i", self.flags))
            new_bytes+=(struct.pack("<i", self.n_frames))
            
            shaders = self.shaders.to_bytes()
            #n_shaders
            new_bytes+=(struct.pack("<i", self.shaders.count))
            
            vertices = self.vertices.to_bytes()
            #n_verts
            new_bytes+=(struct.pack("<i", self.vertices.count))
            
            triangles = self.triangles.to_bytes()
            #n_tris
            new_bytes+=(struct.pack("<i", self.triangles.count))
            
            tcs = self.tcs.to_bytes()
            
            #shaders need to be the first as the offset determined as header offset in md3 view...
            header_offset = self.size
            shaders_offset = header_offset
            
            tris_offset = shaders_offset + self.shaders.size
            tcs_offset = tris_offset + self.triangles.size
            vert_offset = tcs_offset + self.tcs.size
            end_offset = vert_offset + self.vertices.size
            
            #shader offset still second in the cue -.-
            new_bytes+=(struct.pack("<i", tris_offset))
            new_bytes+=(struct.pack("<i", shaders_offset)) 
            new_bytes+=(struct.pack("<i", tcs_offset))
            new_bytes+=(struct.pack("<i", vert_offset))
            new_bytes+=(struct.pack("<i", end_offset))
            
            new_bytes+=shaders
            new_bytes+=triangles
            new_bytes+=tcs
            new_bytes+=vertices
        
            return new_bytes

        class shader:
            size = STRING + INT
            encoding = "<64si"
            def __init__(self, array):
                self.name =     Image.remove_file_extension(array[0].decode("utf-8", errors="ignore").strip("\0"))
                self.index =    array[1]
            def to_array(self):
                array = [None for i in range(2)]
                name = self.name.split(".")[0]
                array[0] = bytes(fillName(name, 64),"ascii")
                array[1] = self.index
                return array
                
        class triangle:
            size = 3*INT
            encoding = "<3i"
            def __init__(self, array):
                self.indices = [array[0],array[2],array[1]]
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
            size = 2*FLOAT
            encoding = "<2f"
            def __init__(self, array):
                self.tc = [array[0], 1.0 - array[1]]
            @classmethod
            def from_loop(cls, loop):
                tcs = loop.uv
                return cls([tcs[0], 1.0 - tcs[1]])
            def to_array(self):
                array = [None for i in range(2)]
                array[0] = self.tc[0]
                array[1] = 1.0 - self.tc[1]
                return array
            
        class vertex:
            size = 3*HALF + HALF
            encoding = "<3h2s"
            def __init__(self, array):
                self.position = [array[0]/64.0,array[1]/64.0,array[2]/64.0]
                self.normal = MD3.decode_normal(array[3])
            @classmethod
            def from_vertex(cls, vertex):
                vert = cls([0.0, 0.0, 0.0, [0,0]])
                vert.position = vertex.co
                vert.normal = vertex.normal
                return vert
            def to_array(self):
                array = [None for i in range(4)]
                array[0] = int(self.position[0] * 64.0)
                array[1] = int(self.position[1] * 64.0)
                array[2] = int(self.position[2] * 64.0)
                array[3] = MD3.encode_normal(self.normal)
                return array
            
    class frame:
        size = 3*FLOAT + 3*FLOAT + 3*FLOAT + FLOAT + 16
        encoding = "<3f3f3ff16s"
        def __init__(self, array):
            self.min_bounds = [array[0],array[1],array[2]]
            self.max_bounds = [array[3],array[4],array[5]]
            self.local_origin = [array[6],array[7],array[8]]
            self.radius = array[9]
            self.name = array[10].decode("utf-8", errors="ignore").strip("\0")
        @classmethod
        def from_object(cls, object):
            array = [0.0 for i in range(10)]
            array.append(bytes(fillName("test", 16),"ascii"))
            return cls(array)
        
        def to_bytes(self):
            new_bytes = bytearray()
            new_bytes+=(struct.pack("<3f", *self.min_bounds))
            new_bytes+=(struct.pack("<3f", *self.max_bounds))
            new_bytes+=(struct.pack("<3f", *self.local_origin))
            new_bytes+=(struct.pack("<f", self.radius))
            new_bytes+= bytes(fillName(self.name, 16),"ascii")
            return new_bytes
            
    class tag:
        size = STRING + 3*FLOAT + 9*FLOAT
        encoding = "<64s3f3f3f3f"
        def __init__(self, array):
            self.name = array[0].decode("utf-8", errors="ignore").strip("\0")
            self.origin = [array[1],array[2],array[3]]
            self.axis_1 = [array[4],array[5],array[6]]
            self.axis_2 = [array[7],array[8],array[9]]
            self.axis_3 = [array[10],array[11],array[12]]
            
def ImportMD3(model_name, zoffset):
    
    mesh = None
    skip = False
    try:
        file = open(model_name, "rb")
    except:
        return mesh

    if (not skip):
        magic_nr = file.read(4)
        version_nr = struct.unpack("<i", file.read(4))[0]
                    
        md3 = MD3(file, magic_nr, version_nr)
        if (not md3.valid):
            print("this md3 version is not supported\n")
            skip = True
        
    if (not skip):
        name        = file.read(64).decode("utf-8", errors="ignore").strip("\0")
        flags       = struct.unpack("<i", file.read(4))[0]
        numFrames   = struct.unpack("<i", file.read(4))[0]
        numTags     = struct.unpack("<i", file.read(4))[0]
        numSurfaces = struct.unpack("<i", file.read(4))[0]
        numSkins    = struct.unpack("<i", file.read(4))[0]
        ofsFrames   = struct.unpack("<i", file.read(4))[0]
        ofsTags     = struct.unpack("<i", file.read(4))[0]
        ofsSurfaces = struct.unpack("<i", file.read(4))[0]
        ofsEnd      = struct.unpack("<i", file.read(4))[0]
        
        print(name + " name")
        print("\t" + str(ofsFrames) + " offset Frames")
        print("\t" + str(ofsTags) + " offset Tags")
        print("\t" + str(ofsSurfaces) + " offset Surfaces")
        print("\t" + str(ofsEnd) + " offset End")
        print("\t" + str(numFrames) + " frames")
        print("\t" + str(ofsFrames) + " ofsFrames")
        print("\t" + str(numTags) + " tags")
        print("\t" + str(ofsTags) + " ofsTags")
        print("\t" + str(numSurfaces) + " surfaces")
        print("\t" + str(ofsSurfaces) + " ofsSurfaces")
        print("\t" + str(numSkins) + " skins")
        print("\t" + str(ofsEnd) + " ofsEnd")
        print("\t" + "flag " + str(flags))
        
        surface_lumps = []
        for surface_lump in range(numSurfaces):
            surface = lump(md3.surface)
            surface.set_offset_count([ofsSurfaces,1])
            surface.readFrom(file)
            surface.data[0].vertices.readFrom(file,ofsSurfaces)
            surface.data[0].tcs.readFrom(file,ofsSurfaces)
            surface.data[0].shaders.readFrom(file,ofsSurfaces)
            surface.data[0].triangles.readFrom(file,ofsSurfaces)
            
            
            print("Surface " + str(surface.data[0].name) + " has:")
            print("\t" + str(surface.data[0].n_frames) + " frames")
            print("\t" + str(surface.data[0].n_shaders) + " shaders")
            if surface.data[0].n_shaders > 1:
                for i in range(surface.data[0].n_shaders):
                    print("\t\t" + surface.data[0].shaders.data[i].name)
            print("\t" + str(surface.data[0].n_verts) + " verts")
            print("\t" + str(surface.data[0].n_tris) + " tris")
            print("\t" + "flag " + str(surface.data[0].flags))
            
            print("\t" + "off_tris " + str(surface.data[0].off_tris))
            print("\t" + "off_shaders " + str(surface.data[0].off_shaders))
            print("\t" + "off_tcs " + str(surface.data[0].off_tcs))
            print("\t" + "off_verts " + str(surface.data[0].off_verts))
            
            surface_lumps.append(surface)
            ofsSurfaces += surface.data[0].off_end
            
        vertex_pos = []
        vertex_nor = []
        vertex_tc = []
        face_indices = []
        face_tcs = []
        face_shaders = []
        shaderindex = 0
        face_index_offset = 0
        face_material_index = []
        
        #vertex groups
        surfaces = {}
        for surface in surface_lumps:
            n_indices = 0
            surface_indices = []
            for vertex, tc in zip(surface.data[0].vertices.data, surface.data[0].tcs.data):
                vertex_pos.append(vertex.position)
                vertex_nor.append(vertex.normal)
                vertex_tc.append(tc.tc)
                n_indices += 1
                
            for triangle in surface.data[0].triangles.data:
                triangle_indices = [ triangle.indices[0] + face_index_offset,
                                     triangle.indices[1] + face_index_offset,
                                     triangle.indices[2] + face_index_offset]
                surface_indices.append(triangle_indices)
                face_indices.append(triangle_indices)
                    
                face_tcs.append(vertex_tc[triangle_indices[0]])
                face_tcs.append(vertex_tc[triangle_indices[1]])
                face_tcs.append(vertex_tc[triangle_indices[2]])
                face_material_index.append(shaderindex)
                    
            surfaces[surface.data[0].name] = unpack_list(surface_indices)
            face_shaders.append(surface.data[0].shaders.data[0])
            shaderindex += 1
            face_index_offset += n_indices
        
        guessed_name = guess_model_name( model_name.lower() ).lower()
        if guessed_name.endswith(".md3"):
            guessed_name = guessed_name[:-len(".md3")]
        
        mesh = bpy.data.meshes.new( guessed_name )
        mesh.from_pydata(vertex_pos, [], face_indices)
            
        #oh man...
        if zoffset == 0:
            material_suffix = ".grid"
        else:
            material_suffix = "." + str(zoffset) + "grid"
            
        for texture_instance in face_shaders:
            mat = bpy.data.materials.get(texture_instance.name + material_suffix)
            if (mat == None):
                mat = bpy.data.materials.new(name=texture_instance.name + material_suffix)
            mesh.materials.append(mat)
                        
        mesh.polygons.foreach_set("material_index", face_material_index)
            
        for poly in mesh.polygons:
            poly.use_smooth = True
                        
        mesh.vertices.foreach_set("normal", unpack_list(vertex_nor))
        mesh.normals_split_custom_set_from_vertices(vertex_nor)
        
        mesh.uv_layers.new(do_init=False,name="UVMap")
        mesh.uv_layers["UVMap"].data.foreach_set("uv", unpack_list(face_tcs))
        
        mesh.use_auto_smooth = True
                    
        mesh.update()
            
    file.close
    return mesh

def ImportMD3Object(file_path):
    mesh = ImportMD3(file_path, 0)
    ob = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(ob)

def ExportMD3(file_path):
    objs = bpy.context.selected_objects
    
    model_name = guess_model_name(file_path)
    
    md3_bytes = bytearray()
    md3_bytes+=(b'IDP3')
    md3_bytes+=(struct.pack("<i", 15))
    md3_bytes+=bytes(fillName(model_name, 64),"utf-8")
    md3_bytes+=(struct.pack("<i", 0)) #flags
    md3_bytes+=(struct.pack("<i", 1)) #n_frames
    md3_bytes+=(struct.pack("<i", 0)) #n_tags
    md3_bytes+=(struct.pack("<i", len(objs))) #n_surfaces
    md3_bytes+=(struct.pack("<i", 0)) #n_skins
    
    ofsFrames = INT + INT + STRING + INT + INT + INT + INT + INT + INT + INT + INT + INT
    md3_bytes+=(struct.pack("<i", ofsFrames))
    
    ofsTags = ofsFrames + MD3.frame.size * 1 # n_frames
    md3_bytes+=(struct.pack("<i", ofsTags))
    
    ofsSurfaces = ofsTags + MD3.tag.size * 0 # n_tags
    md3_bytes+=(struct.pack("<i", ofsSurfaces))
    
    surface_bytes = bytearray()
    surface_size = 0
    for obj in objs:
        mesh = obj.to_mesh()
        
        #Move origin of the object to 0.0, 0.0, 0.0 when exporting
        #multiple objects, because else they would loose their relative
        #positioning
        #TODO: maybe option for the import dialog?
        if len(objs) > 1:
            mesh.transform(Matrix.Translation(obj.location))
        
        mesh.calc_normals_split()
        mesh.calc_loop_triangles()
        
        new_surface = MD3.surface.from_mesh(mesh)
        
        surface_bytes+= new_surface.to_bytes()
        surface_size += new_surface.size
        surface_size += new_surface.vertices.size
        surface_size += new_surface.triangles.size
        surface_size += new_surface.tcs.size
        surface_size += new_surface.shaders.size
        
        obj.to_mesh_clear()
    
    ofsEof = ofsSurfaces + surface_size
    
    md3_bytes+=(struct.pack("<i", ofsEof))
    
    new_frame = MD3.frame.from_object(obj).to_bytes()
    md3_bytes+=new_frame
    md3_bytes+=surface_bytes
    
    f = open(file_path, "wb")
    try:
        f.write(md3_bytes)
    except:
        print("Failed writing: " + name)        
    f.close()