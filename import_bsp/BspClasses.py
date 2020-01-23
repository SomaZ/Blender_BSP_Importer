if "struct" not in locals():
    import struct
    
import copy

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

#rbsp and ibsp
class entity:
    size = 1
    encoding = "<c"
    def __init__( self , array):
        self.char = array[0]

#rbsp and ibsp
class texture:
    size = STRING + INT + INT
    encoding = "<64sii"
    def __init__( self , array):
        self.name = array[0].decode("latin-1").strip("\0")
        self.flags = array[1]
        self.contents = array[2]

#rbsp and ibsp
class plane:
    size = 3*FLOAT + FLOAT
    encoding = "<ffff"
    def __init__ (self, array):
        self.normal = [array[0],array[1],array[2]]
        self.distance = array[3]

#rbsp and ibsp
class node:
    size = INT + 2*INT + 3*INT + 3*INT
    encoding = "<iiiiiiiii"
    def __init__ (self, array):
        self.plane = array[0]
        self.children = [array[1],array[2]]
        self.mins = [array[3],array[4],array[5]]
        self.maxs = [array[6],array[7],array[8]]
        
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

#rbsp and ibsp
class leafface:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.face = array[0]

#rbsp and ibsp    
class leafbrush:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.brush = array[0]

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

#rbsp and ibsp
class brush:
    size = INT + INT + INT
    encoding = "<iii"
    def __init__ (self, array):
        self.brushside = array[0]
        self.n_brushsides = array[1]
        self.texture = array[2]

#rbsp
class brushside_rbsp:
    size = INT + INT + INT
    encoding = "<iii"
    def __init__ (self, array):
        self.plane = array[0]
        self.texture = array[1]
        self.face = array[2]
        
#ibsp
class brushside_ibsp:
    size = INT + INT
    encoding = "<ii"
    def __init__ (self, array):
        self.plane = array[0]
        self.texture = array[1]

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
        
#rbsp and ibsp
class meshvert:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.offset = array[0]

#rbsp and ibsp
class effect:
    size = STRING + INT + INT
    encoding = "<64sii"
    def __init__( self , array):
        self.name = array[0].decode("utf-8").strip("\0")
        self.brush = array[1]
        self.visibleSide = array[2]

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
        
#ibsp
class face_ibsp:
    size = 14*INT + 12*FLOAT
    encoding = "<iiiiiiiiiiiiffffffffffffii"
    def __init__( self , array):
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

#rbsp and ibsp
class lightmap:
    size = 128*128*3*UBYTE
    encoding = "<49152B"
    def __init__( self , array):
        self.map = array
        
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
        if (    array[0] == 0 and
                array[1] == 0 and
                array[2] == 0 and
                array[12] == 0 and
                array[13] == 0 and
                array[14] == 0 ):
            self.styles[0] = 255
        #min lighting
        self.ambient1[0] = self.ambient1[0] + 32
        self.ambient1[1] = self.ambient1[1] + 32
        self.ambient1[2] = self.ambient1[2] + 32
        self.ambient2[0] = self.ambient2[0] + 32
        self.ambient2[1] = self.ambient2[1] + 32
        self.ambient2[2] = self.ambient2[2] + 32
        self.ambient3[0] = self.ambient3[0] + 32
        self.ambient3[1] = self.ambient3[1] + 32
        self.ambient3[2] = self.ambient3[2] + 32
        self.ambient4[0] = self.ambient4[0] + 32
        self.ambient4[1] = self.ambient4[1] + 32
        self.ambient4[2] = self.ambient4[2] + 32
        
#ibsp
class lightgrid_ibsp:
    size = 8*UBYTE
    encoding = "<8B"
    def __init__(self, array):
        self.ambient1 = [array[0],array[1],array[2]]
        self.direct1 = [array[3],array[4],array[5]]
        self.lat_long = [array[6], array[7]]
        #min lighting
        self.ambient1[0] = self.ambient1[0] + 32
        self.ambient1[1] = self.ambient1[1] + 32
        self.ambient1[2] = self.ambient1[2] + 32

#rbsp and ibsp?
class visdata:
    size = UBYTE
    encoding = "<B"
    def __init__(self, array):
        self.bit_set = array[0]

#rbsp
class lightgridarray:
    size = HALF
    encoding = "<H"
    def __init__(self, array):
        self.data = array[0]

   
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
                self.lumps = copy.deepcopy(format.lumps)
                self.lightgrid_size = format.lightgrid_size
                self.lightgrid_inverse_size = format.lightgrid_inverse_size
                self.lightgrid_origin = format.lightgrid_origin
                self.lightgrid_z_step = format.lightgrid_z_step
                self.lightgrid_inverse_dim = format.lightgrid_inverse_dim
                self.lightmap_size = format.lightmap_size
                self.lightmaps = format.lightmaps
                self.lightstyles = format.lightstyles
                self.use_lightgridarray = format.use_lightgridarray
                self.bsp_path = file_name
                
        if self.valid:
            for lump in self.lumps:
                self.lumps[lump].set_offset_size(struct.unpack("<ii", file.read(8)))
            for lump in self.lumps:
                self.lumps[lump].readFrom(file)
        else:
            print("Could not import the bsp. Bsp Version: " + str(magic_nr) + " " + str(version_nr))
                
        file.close