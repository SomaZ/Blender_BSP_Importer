import imp

if "bpy" not in locals():
    import bpy

if "struct" not in locals():
    import struct
    
if "BspGeneric" in locals():
    imp.reload( BspGeneric )
else:
    from . import BspGeneric
    
if "QuakeShader" in locals():
    imp.reload( QuakeShader )
else:
    from . import QuakeShader
    
if "Entities" in locals():
    imp.reload( Entities )
else:
    from . import Entities
    
import copy
from time import perf_counter
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
        self.count = int(offset_count[1])
        
    def readFrom(self, file):
        
        if self.count == 0:
            self.count = int(self.size / self.data_class.size)
            
        file.seek(self.offset)
        for i in range(self.count):
            self.data.append(self.data_class(struct.unpack(self.data_class.encoding, file.read(self.data_class.size))))
    
    def clear(self):
        self.data = []
        self.count = 0
        self.size = 0
        
    def add(self, array):
        self.data.append(self.data_class(array))
        self.count += 1
        self.size = self.count * self.data_class.size
        
    def to_bytes(self):
        self.count = len(self.data)
        self.size = self.count * self.data_class.size
        bytes = bytearray()
        for i in range(self.count):
            bytes+=(struct.pack(self.data_class.encoding, *self.data[i].to_array()))
        return bytes

def fillName(string, length):
    new_str = string
    while len(new_str) < length:
        new_str += "\0"
    return new_str

#rbsp and ibsp
class entity:
    size = 1
    encoding = "<c"
    def __init__(self, array):
        self.char = array[0]
    def to_array(self):
        return [bytes(self.char)]
    
#rbsp and ibsp
class texture:
    size = STRING + INT + INT
    encoding = "<64sii"
    def __init__(self, array):
        self.name = array[0].decode("latin-1").strip("\0")
        self.flags = array[1]
        self.contents = array[2]
    def to_array(self):
        #TODO: Check encoding?
        array = [None for i in range(3)]
        array[0] = bytes(fillName(self.name, 64),"ascii")
        array[1] = self.flags
        array[2] = self.contents
        return array
    
#string = fillName("testingaiowdjiooiaw3898127z3", 64)
#print(bytes(string, 'ASCII'))
#print(len(string))

#rbsp and ibsp
class plane:
    size = 3*FLOAT + FLOAT
    encoding = "<ffff"
    def __init__ (self, array):
        self.normal = [array[0],array[1],array[2]]
        self.distance = array[3]
    def to_array(self):
        array = [None for i in range(4)]
        array[0], array[1], array[2] = self.normal
        array[3] = self.distance
        return array

#rbsp and ibsp
class node:
    size = INT + 2*INT + 3*INT + 3*INT
    encoding = "<iiiiiiiii"
    def __init__ (self, array):
        self.plane = array[0]
        self.children = [array[1],array[2]]
        self.mins = [array[3],array[4],array[5]]
        self.maxs = [array[6],array[7],array[8]]
    def to_array(self):
        array = [None for i in range(9)]
        array[0] = self.plane
        array[1], array[2] = self.children
        array[3], array[4], array[5] = self.mins
        array[6], array[7], array[8] = self.maxs
        return array
        
#rbsp and ibsp
class leaf:
    size = INT + INT + 3*INT + 3*INT + INT + INT + INT + INT
    encoding = "<iiiiiiiiiiii"
    def __init__ (self, array):
        self.cluster = array[0]
        self.area = array[1]
        self.mins = [array[2],array[3],array[4]]
        self.maxs = [array[5],array[6],array[7]]
        self.leafface = array[8]
        self.n_leaffaces = array[9]
        self.leafbrush = array[10]
        self.n_leafbrushes = array[11]
    def to_array(self):
        array = [None for i in range(12)]
        array[0] = self.cluster
        array[1] = self.area
        array[2], array[3], array[4] = self.mins
        array[5], array[6], array[7] = self.maxs
        array[8] = self.leafface
        array[9] = self.n_leaffaces
        array[10] = self.leafbrush
        array[11] = self.n_leafbrushes
        return array

#rbsp and ibsp
class leafface:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.face = array[0]
    def to_array(self):
        array = [None for i in range(1)]
        array[0] = self.face
        return array

#rbsp and ibsp    
class leafbrush:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.brush = array[0]
    def to_array(self):
        array = [None for i in range(1)]
        array[0] = self.brush
        return array

#rbsp and ibsp
class model:
    size = 3*FLOAT + 3*FLOAT + INT + INT + INT + INT
    encoding = "<ffffffiiii"
    def __init__ (self, array):
        self.mins = [array[0],array[1],array[2]]
        self.maxs = [array[3],array[4],array[5]]
        self.face = array[6]
        self.n_faces = array[7]
        self.brush = array[8]
        self.n_brushes = array[9]
    def to_array(self):
        array = [None for i in range(10)]
        array[0], array[1], array[2] = self.mins
        array[3], array[4], array[5] = self.maxs
        array[6] = self.face
        array[7] = self.n_faces
        array[8] = self.brush
        array[9] = self.n_brushes
        return array

#rbsp and ibsp
class brush:
    size = INT + INT + INT
    encoding = "<iii"
    def __init__ (self, array):
        self.brushside = array[0]
        self.n_brushsides = array[1]
        self.texture = array[2]
    def to_array(self):
        array = [None for i in range(3)]
        array[0] = self.brushside
        array[1] = self.n_brushsides
        array[2] = self.texture
        return array

#rbsp
class brushside_rbsp:
    size = INT + INT + INT
    encoding = "<iii"
    def __init__ (self, array):
        self.plane = array[0]
        self.texture = array[1]
        self.face = array[2]
    def to_array(self):
        array = [None for i in range(3)]
        array[0] = self.plane
        array[1] = self.texture
        array[2] = self.face
        return array
        
#ibsp
class brushside_ibsp:
    size = INT + INT
    encoding = "<ii"
    def __init__ (self, array):
        self.plane = array[0]
        self.texture = array[1]
    def to_array(self):
        array = [None for i in range(2)]
        array[0] = self.plane
        array[1] = self.texture
        return array

#rbsp
class vertex_rbsp:
    size = 3*FLOAT + 2*FLOAT + 4*2*FLOAT + 3*FLOAT + 4*4*UBYTE
    encoding = "<ffffffffffffffffBBBBBBBBBBBBBBBB"
    def __init__ (self, array):
        self.position = [array[0],array[1],array[2]]
        self.texcoord = [array[3], 1.0 - array[4]]
        self.lm1coord = [array[5],array[6]]
        self.lm2coord = [array[7],array[8]]
        self.lm3coord = [array[9],array[10]]
        self.lm4coord = [array[11],array[12]]
        self.normal = [array[13],array[14],array[15]]
        self.color1  = [float(array[16]/255.0),float(array[17]/255.0),float(array[18]/255.0),float(array[19]/255.0)]
        self.color2  = [float(array[20]/255.0),float(array[21]/255.0),float(array[22]/255.0),float(array[23]/255.0)]
        self.color3  = [float(array[24]/255.0),float(array[25]/255.0),float(array[26]/255.0),float(array[27]/255.0)]
        self.color4  = [float(array[28]/255.0),float(array[29]/255.0),float(array[30]/255.0),float(array[31]/255.0)]
    def to_array(self):
        array = [None for i in range(32)]
        array[0], array[1], array[2] = self.position
        array[3] = self.texcoord[0]
        array[4] = 1.0 - self.texcoord[1]
        array[5], array[6] = self.lm1coord
        array[7], array[8] = self.lm2coord
        array[9], array[10] = self.lm3coord
        array[11], array[12] = self.lm4coord
        array[13], array[14], array[15] = self.normal
        array[16] = int(self.color1[0] * 255.0)
        array[17] = int(self.color1[1] * 255.0)
        array[18] = int(self.color1[2] * 255.0)
        array[19] = int(self.color1[3] * 255.0)
        array[20] = int(self.color2[0] * 255.0)
        array[21] = int(self.color2[1] * 255.0)
        array[22] = int(self.color2[2] * 255.0)
        array[23] = int(self.color2[3] * 255.0)
        array[24] = int(self.color3[0] * 255.0)
        array[25] = int(self.color3[1] * 255.0)
        array[26] = int(self.color3[2] * 255.0)
        array[27] = int(self.color3[3] * 255.0)
        array[28] = int(self.color4[0] * 255.0)
        array[29] = int(self.color4[1] * 255.0)
        array[30] = int(self.color4[2] * 255.0)
        array[31] = int(self.color4[3] * 255.0)
        return array

#ibsp
class vertex_ibsp:
    size = 3*FLOAT + 2*FLOAT + 2*FLOAT + 3*FLOAT + 4*UBYTE
    encoding = "<ffffffffffBBBB"
    def __init__ (self, array):
        self.position = [array[0],array[1],array[2]]
        self.texcoord = [array[3], 1.0 - array[4]]
        self.lm1coord = [array[5],array[6]]
        self.normal = [array[7],array[8],array[9]]
        self.color1  = [float(array[10]/255.0),float(array[11]/255.0),float(array[12]/255.0),float(array[13]/255.0)]
    def to_array(self):
        array = [None for i in range(14)]
        array[0], array[1], array[2] = self.position
        array[3] = self.texcoord[0]
        array[4] = 1.0 - self.texcoord[1]
        array[5], array[6] = self.lm1coord
        array[7], array[8], array[9] = self.normal
        array[10] = int(self.color1[0] * 255.0)
        array[11] = int(self.color1[1] * 255.0)
        array[12] = int(self.color1[2] * 255.0)
        array[13] = int(self.color1[3] * 255.0)
        return array
        
#rbsp and ibsp
class meshvert:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.offset = array[0]
    def to_array(self):
        array = [None for i in range(1)]
        array[0] = self.offset
        return array

#rbsp and ibsp
class effect:
    size = STRING + INT + INT
    encoding = "<64sii"
    def __init__( self , array):
        self.name = array[0].decode("utf-8").strip("\0")
        self.brush = array[1]
        self.visibleSide = array[2]
    def to_array(self):
        array = [None for i in range(3)]
        array[0] = bytes(fillName(self.name, 64),"ascii")
        array[1] = self.brush
        array[2] = self.visibleSide
        return array

#rbsp
class face_rbsp:
    size = INT + INT + INT + INT + INT + INT + INT + 4*UBYTE + 4*UBYTE + 4*INT + 4*INT + 4*INT + INT + INT + 3*FLOAT + 3*3*FLOAT + INT + INT
    encoding = "<iiiiiiiBBBBBBBBiiiiiiiiiiiiiiffffffffffffii"
    def __init__( self , array):
        self.texture = array[0]
        self.effect = array[1]
        self.type = array[2]
        self.vertex = array[3]
        self.n_vertexes = array[4]
        self.index = array[5]
        self.n_indexes = array[6]
        self.lm_styles = [array[7],array[8],array[9],array[10]]
        self.vertex_styles = [array[11],array[12],array[13],array[14]]
        self.lm_indexes = [array[15],array[16],array[17],array[18]]
        self.lm_x = [array[19],array[20],array[21],array[22]]
        self.lm_y = [array[23],array[24],array[25],array[26]]
        self.lm_width = array[27]
        self.lm_height = array[28]
        self.lm_origin = [array[29],array[30],array[31]]
        self.lm_vecs = [array[32],array[33],array[34],array[35],array[36],array[37],array[38],array[39],array[40]]
        self.patch_width = array[41]
        self.patch_height = array[42]
    def to_array(self):
        array = [None for i in range(43)]
        array[0] = self.texture
        array[1] = self.effect
        array[2] = self.type
        array[3] = self.vertex
        array[4] = self.n_vertexes
        array[5] = self.index
        array[6] = self.n_indexes
        array[7] = self.lm_styles[0]
        array[8] = self.lm_styles[1]
        array[9] = self.lm_styles[2]
        array[10] = self.lm_styles[3]
        array[11] = self.vertex_styles[0]
        array[12] = self.vertex_styles[1]
        array[13] = self.vertex_styles[2]
        array[14] = self.vertex_styles[3]
        array[15] = self.lm_indexes[0]
        array[16] = self.lm_indexes[1]
        array[17] = self.lm_indexes[2]
        array[18] = self.lm_indexes[3]
        array[19] = self.lm_x[0]
        array[20] = self.lm_x[1]
        array[21] = self.lm_x[2]
        array[22] = self.lm_x[3]
        array[23] = self.lm_y[0]
        array[24] = self.lm_y[1]
        array[25] = self.lm_y[2]
        array[26] = self.lm_y[3]
        array[27] = self.lm_width
        array[28] = self.lm_height
        array[29] = self.lm_origin[0]
        array[30] = self.lm_origin[1]
        array[31] = self.lm_origin[2]
        array[32] = self.lm_vecs[0]
        array[33] = self.lm_vecs[1]
        array[34] = self.lm_vecs[2]
        array[35] = self.lm_vecs[3]
        array[36] = self.lm_vecs[4]
        array[37] = self.lm_vecs[5]
        array[38] = self.lm_vecs[6]
        array[39] = self.lm_vecs[7]
        array[40] = self.lm_vecs[8]
        array[41] = self.patch_width
        array[42] = self.patch_height
        return array
        
#ibsp
class face_ibsp:
    size = 14*INT + 12*FLOAT
    encoding = "<iiiiiiiiiiiiffffffffffffii"
    def __init__(self, array):
        self.texture = array[0]
        self.effect = array[1]
        self.type = array[2]
        self.vertex = array[3]
        self.n_vertexes = array[4]
        self.index = array[5]
        self.n_indexes = array[6]
        self.lm_indexes = [array[7]]
        self.lm_x = [array[8]]
        self.lm_y = [array[9]]
        self.lm_width = array[10]
        self.lm_height = array[11]
        self.lm_origin = [array[12],array[13],array[14]]
        self.lm_vecs = [array[15],array[16],array[17],array[18],array[19],array[20],array[21],array[22],array[23]]
        self.patch_width = array[24]
        self.patch_height = array[25]
    def to_array(self):
        array = [None for i in range(26)]
        array[0] = self.texture
        array[1] = self.effect
        array[2] = self.type
        array[3] = self.vertex
        array[4] = self.n_vertexes
        array[5] = self.index
        array[6] = self.n_indexes
        array[7] = self.lm_indexes[0]
        array[8] = self.lm_x[0]
        array[9] = self.lm_y[0]
        array[10] = self.lm_width
        array[11] = self.lm_height
        array[12] = self.lm_origin[0]
        array[13] = self.lm_origin[1]
        array[14] = self.lm_origin[2]
        array[15] = self.lm_vecs[0]
        array[16] = self.lm_vecs[1]
        array[17] = self.lm_vecs[2]
        array[18] = self.lm_vecs[3]
        array[19] = self.lm_vecs[4]
        array[20] = self.lm_vecs[5]
        array[21] = self.lm_vecs[6]
        array[22] = self.lm_vecs[7]
        array[23] = self.lm_vecs[8]
        array[24] = self.patch_width
        array[25] = self.patch_height
        return array

#rbsp and ibsp
class lightmap:
    size = 128*128*3*UBYTE
    encoding = "<49152B"
    def __init__(self, array):
        self.map = array
    def to_array(self):
        return self.map
        
#rbsp
class lightgrid_rbsp:
    size = 3*4*UBYTE + 3*4*UBYTE + 4*UBYTE + 2*UBYTE
    encoding = "<30B"
    def __init__(self, array):
        self.ambient1 = [array[0],array[1],array[2]]
        self.ambient2 = [array[3],array[4],array[5]]
        self.ambient3 = [array[6],array[7],array[8]]
        self.ambient4 = [array[9],array[10],array[11]]
        self.direct1 = [array[12],array[13],array[14]]
        self.direct2 = [array[15],array[16],array[17]]
        self.direct3 = [array[18],array[19],array[20]]
        self.direct4 = [array[21],array[22],array[23]]
        self.styles = [array[24],array[25],array[26],array[27]]
        self.lat_long = [array[28], array[29]]
        self.hash = hash(tuple(array))
    def to_array(self):
        array = [None for i in range(30)]
        array[0],array[1],array[2] = self.ambient1
        array[3],array[4],array[5] = self.ambient2
        array[6],array[7],array[8] = self.ambient3
        array[9],array[10],array[11] = self.ambient4
        array[12],array[13],array[14] = self.direct1
        array[15],array[16],array[17] = self.direct2
        array[18],array[19],array[20] = self.direct3
        array[21],array[22],array[23] = self.direct4
        array[24],array[25],array[26],array[27] = self.styles
        array[28],array[29] = self.lat_long
        return array
        
#ibsp
class lightgrid_ibsp:
    size = 8*UBYTE
    encoding = "<8B"
    def __init__(self, array):
        self.ambient1 = [array[0],array[1],array[2]]
        self.direct1 = [array[3],array[4],array[5]]
        self.lat_long = [array[6], array[7]]
        self.hash = hash(tuple(array))
    def to_array(self):
        array = [None for i in range(8)]
        array[0],array[1],array[2] = self.ambient1
        array[3],array[4],array[5] = self.direct1
        array[6], array[7] = self.lat_long
        return array

#rbsp and ibsp?
class visdata:
    size = UBYTE
    encoding = "<B"
    def __init__(self, array):
        self.bit_set = array[0]
    def to_array(self):
        return [self.bit_set]

#rbsp
class lightgridarray:
    size = HALF
    encoding = "<H"
    def __init__(self, array):
        self.data = array[0]
    def to_array(self):
        return [self.data]
   
class RBSP:
    BSP_MAGIC = b'RBSP'
    BSP_VERSION = 0x1
    
    lightgrid_size = [64,64,128]
    lightgrid_inverse_size = [  1.0 / float(lightgrid_size[0]),
                                1.0 / float(lightgrid_size[1]),
                                1.0 / float(lightgrid_size[2]) ]
    lightgrid_origin = [0.0,0.0,0.0]
    lightgrid_z_step = 0.0
    lightgrid_inverse_dim = [0.0,0.0,0.0]
    lightgrid_dim = [0.0,0.0,0.0]
    
    lightmap_size = [128,128]
    lightmaps = 4
    lightstyles = 4
    use_lightgridarray = True

    lumps = {   "entities":         lump( entity ),
                "shaders":          lump( texture ),
                "planes":           lump( plane ),
                "nodes":            lump( node ),
                "leafs":            lump( leaf ),
                "leaffaces":        lump( leafface ),
                "leafbrushes":      lump( leafbrush ),
                "models":           lump( model ),
                "brushes":          lump( brush ),
                "brushsides":       lump( brushside_rbsp ),
                "drawverts":        lump( vertex_rbsp ),
                "drawindexes":      lump( meshvert ),
                "fogs":             lump( effect ),
                "surfaces":         lump( face_rbsp ),
                "lightmaps":        lump( lightmap ),
                "lightgrid":        lump( lightgrid_rbsp ),
                "visdata":          lump( visdata ),
                "lightgridarray":   lump( lightgridarray )
                }
                
class IBSP:
    BSP_MAGIC = b'IBSP'
    BSP_VERSION = 0x1 #not used right now
    
    lightgrid_size = [64,64,128]
    lightgrid_inverse_size = [  1.0 / float(lightgrid_size[0]),
                                1.0 / float(lightgrid_size[1]),
                                1.0 / float(lightgrid_size[2]) ]
    lightgrid_origin = [0.0,0.0,0.0]
    lightgrid_z_step = 0.0
    lightgrid_inverse_dim = [0.0,0.0,0.0]
    lightgrid_dim = [0.0,0.0,0.0]
    
    lightmap_size = [128,128]
    lightmaps = 1
    lightstyles = 0
    use_lightgridarray = False

    lumps = {   "entities":         lump( entity ),
                "shaders":          lump( texture ),
                "planes":           lump( plane ),
                "nodes":            lump( node ),
                "leafs":            lump( leaf ),
                "leaffaces":        lump( leafface ),
                "leafbrushes":      lump( leafbrush ),
                "models":           lump( model ),
                "brushes":          lump( brush ),
                "brushsides":       lump( brushside_ibsp ),
                "drawverts":        lump( vertex_ibsp ),
                "drawindexes":      lump( meshvert ),
                "fogs":             lump( effect ),
                "surfaces":         lump( face_ibsp ),
                "lightmaps":        lump( lightmap ),
                "lightgrid":        lump( lightgrid_ibsp ),
                "visdata":          lump( visdata )
                }

class BSP:
    def __init__(self, file_name):
        self.valid = False
        
        file = open(file_name, "rb")
        magic_nr = file.read(4)
        version_nr = struct.unpack("<i", file.read(4))[0]
        
        bsp_formats = [RBSP, IBSP]
        for format in bsp_formats:
            if format.BSP_MAGIC == magic_nr:
                self.valid = True
                self.magic_nr = magic_nr
                self.version_nr = version_nr
                self.lumps = copy.deepcopy(format.lumps)
                self.lightgrid_size = format.lightgrid_size
                self.lightgrid_inverse_size = format.lightgrid_inverse_size
                self.lightgrid_origin = format.lightgrid_origin
                self.lightgrid_z_step = format.lightgrid_z_step
                self.lightgrid_inverse_dim = format.lightgrid_inverse_dim
                self.lightgrid_dim =format.lightgrid_dim
                self.lightmap_size = format.lightmap_size
                self.internal_lightmap_size = format.lightmap_size
                self.lightmaps = format.lightmaps
                self.lightstyles = format.lightstyles
                self.use_lightgridarray = format.use_lightgridarray
                self.bsp_path = file_name
                
        if self.valid:
            for lump in self.lumps:
                self.lumps[lump].set_offset_size(struct.unpack("<ii", file.read(8)))
                print(lump + "offset " + str(self.lumps[lump].offset) + " size " + str(self.lumps[lump].size))
            for lump in self.lumps:
                self.lumps[lump].readFrom(file)
        else:
            print("Could not import the bsp. Bsp Version: " + str(magic_nr) + " " + str(version_nr))
                
        file.close
    def to_bytes(self):
        bytes = bytearray()
        bytes+=(self.magic_nr)
        bytes+=(struct.pack("<i", self.version_nr))
        
        #get the bytes for every lump
        #this automatically updates the size of every lump
        lumps = {}
        for lump in self.lumps:
            print("Converting " + lump + " to bytes")
            lumps[lump] = self.lumps[lump].to_bytes()
            
        #finish the header
        offset = 8 + (8 * len(self.lumps))
        for lump in self.lumps:
            bytes+=struct.pack("<ii", offset, self.lumps[lump].size)
            offset += self.lumps[lump].size
        for lump in self.lumps:
            bytes+=lumps[lump]

        return bytes
        
def ImportBSP(import_settings):
        
    dataPath = import_settings.filepath
    import_settings.log.append("----ImportBSP----")
    import_settings.log.append("bsp: " + dataPath)

    bsp = BSP(dataPath)

    if bsp.valid:
        
        if import_settings.preset == "BRUSHES":
            for model_index in range(int(bsp.lumps["models"].count)):
                model = BspGeneric.blender_model_data()
                model.get_bsp_model(bsp, model_index, import_settings)
                
            ent_list = []
            collection = bpy.data.collections.get("Brushes")
            if collection != None:
                QuakeShader.build_quake_shaders(import_settings, bpy.data.collections["Brushes"].objects)
                
                objs = bpy.data.objects
                delete_objects = []
                for obj in bpy.data.collections["Brushes"].objects:
                    delete_obj = True
                    for m in obj.material_slots:
                        if m.material.name.startswith("noshader"):
                            continue
                        #clip brushes for models
                        if m.material.name.startswith("models/"):
                            delete_obj = True
                            break
                        if "Sky" in m.material.node_tree.nodes:
                            delete_obj = True
                            break
                        if not "Transparent" in m.material.node_tree.nodes:
                            delete_obj = False
                    if delete_obj:
                        delete_objects.append(obj)

                for obj in delete_objects:             
                    objs.remove(obj, do_unlink=True)
                    
            return
        
        #import lightmaps before packing vertex data 
        #because of varying packed lightmap size
        import_settings.log.append("----pack_lightmaps----")
        time_start = perf_counter()
        BspGeneric.pack_lightmaps(bsp, import_settings)
        import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
        
        vertex_groups = {}
        
        for model_index in range(int(bsp.lumps["models"].count)):
            model = BspGeneric.blender_model_data()
            model.get_bsp_model(bsp, model_index, import_settings)
            
            if len(model.vertices) <= 0:
                continue
            
            name = "*"+str(model_index)
            
            mesh = bpy.data.meshes.new( name )
            mesh.from_pydata(model.vertices, [], model.face_vertices)
            vertex_groups[name] = model.vertex_groups
            
            for texture_instance in model.material_names:
                mat = bpy.data.materials.get(texture_instance)
                if (mat == None):
                    mat = bpy.data.materials.new(name=texture_instance)
                mesh.materials.append(mat)
                    
            mesh.polygons.foreach_set("material_index", model.face_materials)
                
            for poly in mesh.polygons:
                poly.use_smooth = True
                
            mesh.vertices.foreach_set("normal", unpack_list(model.normals))
            mesh.normals_split_custom_set_from_vertices(model.normals)

            mesh.vertex_layers_int.new(name="BSP_VERT_INDEX")
            mesh.vertex_layers_int["BSP_VERT_INDEX"].data.foreach_set("value", model.vertex_bsp_indices)

            mesh.uv_layers.new(do_init=False,name="UVMap")
            mesh.uv_layers["UVMap"].data.foreach_set("uv", unpack_list(unpack_list(model.face_tcs)))

            mesh.uv_layers.new(do_init=False,name="LightmapUV")
            mesh.uv_layers["LightmapUV"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm1_tcs)))
                
            mesh.vertex_colors.new(name = "Color")
            mesh.vertex_colors["Color"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color)))
                
            if bsp.lightmaps > 1:
                mesh.uv_layers.new(do_init=False,name="LightmapUV2")
                mesh.uv_layers["LightmapUV2"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm2_tcs)))

                mesh.uv_layers.new(do_init=False,name="LightmapUV3")
                mesh.uv_layers["LightmapUV3"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm3_tcs)))

                mesh.uv_layers.new(do_init=False,name="LightmapUV4")
                mesh.uv_layers["LightmapUV4"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm4_tcs)))

                mesh.vertex_colors.new(name = "Color2")
                mesh.vertex_colors["Color2"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color2)))

                mesh.vertex_colors.new(name = "Color3")
                mesh.vertex_colors["Color3"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color3)))

                mesh.vertex_colors.new(name = "Color4")
                mesh.vertex_colors["Color4"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color4)))
                
            #ugly hack to get the vertex alpha.....
            mesh.vertex_colors.new(name = "Alpha")
            mesh.vertex_colors["Alpha"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_alpha)))    
            
            mesh.use_auto_smooth = True
            mesh.update()
            mesh.validate()
            
        #import entities and get object list
        import_settings.log.append("----ImportEntities----")
        time_start = perf_counter()
        ent_list = Entities.ImportEntities(bsp, import_settings)
        
        import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
            
        #import lightgrid after entitys because the grid size can change
        import_settings.log.append("----pack_lightgrid----")
        time_start = perf_counter()
        BspGeneric.pack_lightgrid(bsp)
        import_settings.log.append("BSP Lightgrid Origin: " + str(bsp.lightgrid_origin))
        import_settings.log.append("BSP Lightgrid Size: " + str(bsp.lightgrid_size))
        dimensions =   [1.0 / bsp.lightgrid_inverse_dim[0],
                        1.0 / bsp.lightgrid_inverse_dim[1],
                        1.0 / bsp.lightgrid_inverse_dim[2]]
        import_settings.log.append("BSP Lightgrid Dimensions: " + str(dimensions))
        import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
            
        #create whiteimage before parsing shaders
        BspGeneric.create_white_image()
            
        #init shader system
        QuakeShader.init_shader_system(bsp)
            
        #build shaders
        import_settings.log.append("----build_quake_shaders----")
        time_start = perf_counter()
        QuakeShader.build_quake_shaders(import_settings, ent_list)
        import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
        
        for ent in ent_list:
            if ent.data.name in vertex_groups:
                for vertex_group in vertex_groups[ent.data.name]:
                    ent.vertex_groups.new(name = vertex_group)
                    ent.vertex_groups[vertex_group].add(list(vertex_groups[ent.data.name][vertex_group]), 1.0, "ADD")
            
        vg = ent_list[0].vertex_groups.get("Decals")
        if vg is not None:
            modifier = ent_list[0].modifiers.new("polygonOffset", type = "DISPLACE")
            modifier.vertex_group = "Decals"
            modifier.strength = 0.2
            modifier.name = "polygonOffset"