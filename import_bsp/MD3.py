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

from math import pi, sin, cos, atan2, acos
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
            
class MD3:
    MD3_MAGIC         = b'IDP3'
    MD3_VERSION       = 15
    
    def __init__(self, file, magic, version):
        self.file = file
        self.valid = magic == self.MD3_MAGIC and version == self.MD3_VERSION
    
    def decode_normal(packed):
        lat = packed[0] / 255.0 * 2.0 * pi
        long = packed[1] / 255.0 * 2.0 * pi
        x = cos(lat) * sin(long)
        y = sin(lat) * sin(long)
        z = cos(long)
        return [x, y, z]
    
    class surface:
        size = INT + STRING + INT + INT + INT + INT + INT + INT + INT + INT + INT + INT
        encoding = "<i64siiiiiiiiii"
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
            
        class shader:
            size = STRING + INT
            encoding = "<64si"
            
            def __init__(self, array):
                self.name =     Image.remove_file_extension(array[0].decode("utf-8", errors="ignore").strip("\0"))
                self.index =    array[1]
                
        class triangle:
            size = 3*INT
            encoding = "<3i"
            def __init__(self, array):
                self.indices = [array[0],array[1],array[2]]
            
        class tc:
            size = 2*FLOAT
            encoding = "<2f"
            def __init__(self, array):
                self.tc = [array[0], 1.0-array[1]]
            
        class vertex:
            size = 3*HALF + HALF
            encoding = "<3h2s"
            def __init__(self, array):
                self.position = [array[0]/64.0,array[1]/64.0,array[2]/64.0]
                self.normal = MD3.decode_normal(array[3])
            
    class frame:
        size = 3*FLOAT + 3*FLOAT + 3*FLOAT + FLOAT + 16
        encoding = "<3f3f3ff16s"
        def __init__(self, array):
            self.min_bounds = [array[0],array[1],array[2]]
            self.max_bounds = [array[3],array[4],array[5]]
            self.local_origin = [array[6],array[7],array[8]]
            self.radius = array[9]
            self.name = array[10].decode("utf-8", errors="ignore").strip("\0")
            
    class tag:
        size = STRING + 3*FLOAT + 9*FLOAT
        encoding = "<64s3f3f3f3f"
        def __init__(self, array):
            self.name = array[0].decode("utf-8", errors="ignore").strip("\0")
            self.origin = [array[1],array[2],array[3]]
            self.axis_1 = [array[4],array[5],array[6]]
            self.axis_2 = [array[7],array[8],array[9]]
            self.axis_3 = [array[10],array[11],array[12]]
            
def ImportMD3(model_name, import_settings, zoffset):
    
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
            
        surface_lumps = []
        for surface_lump in range(numSurfaces):
            surface = lump(md3.surface)
            surface.set_offset_count([ofsSurfaces,1])
            surface.readFrom(file)
            surface.data[0].vertices.readFrom(file,ofsSurfaces)
            surface.data[0].tcs.readFrom(file,ofsSurfaces)
            surface.data[0].shaders.readFrom(file,ofsSurfaces)
            surface.data[0].triangles.readFrom(file,ofsSurfaces)
                
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
            
        surfaces = []
            
        class surface_class:
            def __init__(sf, name_in, vertices_in):
                sf.name = name_in
                sf.vertices = vertices_in
            
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
                    
            surfaces.append(surface_class(surface.data[0].name, unpack_list(surface_indices)))
            face_shaders.append(surface.data[0].shaders.data[0])
            shaderindex += 1
            face_index_offset += n_indices
            
        if name.lower().endswith(".md3"):
            name = name[:-len(".md3")]
            
        mesh = bpy.data.meshes.new( name )
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
        
        mesh.uv_layers.new(do_init=False,name="UVMap")
        mesh.uv_layers["UVMap"].data.foreach_set("uv", unpack_list(face_tcs))
            
        #q3 renders with front culling as default
        mesh.flip_normals()
                    
        mesh.update()
        mesh.validate()
            
    file.close
    return mesh
