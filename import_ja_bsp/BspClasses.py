FLOAT = 4
HALF = 2
INT = 4
UBYTE = 1
STRING = 64

class entity:
    size = 1
    encoding = "<c"
    def __init__( self , array):
        self.char = array[0]

class texture:
    size = STRING + INT + INT
    encoding = "<64sii"
    def __init__( self , array):
        self.name = array[0].decode("utf-8").strip("\0")
        self.flags = array[1]
        self.contents = array[2]

class plane:
    size = 3*FLOAT + FLOAT
    encoding = "<ffff"
    def __init__ (self, array):
        self.normal = [array[0],array[1],array[2]]
        self.distance = array[3]

class node:
    size = INT + 2*INT + 3*INT + 3*INT
    encoding = "<iiiiiiiii"
    def __init__ (self, array):
        self.plane = array[0]
        self.children = [array[1],array[2]]
        self.mins = [array[3],array[4],array[5]]
        self.maxs = [array[6],array[7],array[8]]
        
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
            
class leafface:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.face = array[0]
            
class leafbrush:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.brush = array[0]
            
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
            
class brush:
    size = INT + INT + INT
    encoding = "<iii"
    def __init__ (self, array):
        self.brushside = array[0]
        self.n_brushsides = array[1]
        self.texture = array[2]
        
class brushside:
    size = INT + INT + INT
    encoding = "<iii"
    def __init__ (self, array):
        self.plane = array[0]
        self.texture = array[1]
        self.face = array[2]
            
class vertex:
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
            
class meshvert:
    size = INT
    encoding = "<i"
    def __init__ (self, array):
        self.offset = array[0]

class effect:
    size = STRING + INT + INT
    encoding = "<64sii"
    def __init__( self , array):
        self.name = array[0].decode("utf-8").strip("\0")
        self.brush = array[1]
        self.visibleSide = array[2]
            
class face:
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
            
class lightmap:
    size = 128*128*3*UBYTE
    encoding = "<49152B"
    def __init__( self , array):
        self.map = array
        
class lightgrid:
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
            
class visdata:
    size = INT + INT
    encoding = "<ii"
    def __init__(self, array):
        self.n_clusters = array[0]
        self.cluster = array[1]
        
class lightgridarray:
    size = HALF
    encoding = "<H"
    def __init__(self, array):
        self.data = array[0]