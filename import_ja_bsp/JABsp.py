#----------------------------------------------------------------------------#
#TODO:  refactor loading bsp files and md3 files, right now its a mess o.O
#----------------------------------------------------------------------------#

if "BspGeneric" in locals():
    import imp
    imp.reload( BspGeneric )
else:
    from . import BspGeneric
    
if "BspClasses" in locals():
    import imp
    imp.reload( BspClasses )
else:
    from . import BspClasses as BSP
    
from math import pi, sin, cos, atan2, acos
    
FLOAT = 4
HALF = 2
INT = 4
UBYTE = 1
STRING = 64
   
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
    
    def __init__(self, file_name, magic, version):
        self.file_name = file_name
        self.valid = magic == self.BSP_MAGIC and version == self.BSP_VERSION
        self.lumps = {
                "entities":         BspGeneric.lump( BSP.entity ),
                "shaders":          BspGeneric.lump( BSP.texture ),
                "planes":           BspGeneric.lump( BSP.plane ),
                "nodes":            BspGeneric.lump( BSP.node ),
                "leafs":            BspGeneric.lump( BSP.leaf ),
                "leaffaces":        BspGeneric.lump( BSP.leafface ),
                "leafbrushes":      BspGeneric.lump( BSP.leafbrush ),
                "models":           BspGeneric.lump( BSP.model ),
                "brushes":          BspGeneric.lump( BSP.brush ),
                "brushsides":       BspGeneric.lump( BSP.brushside ),
                "drawverts":        BspGeneric.lump( BSP.vertex ),
                "drawindexes":      BspGeneric.lump( BSP.meshvert ),
                "fogs":             BspGeneric.lump( BSP.effect ),
                "surfaces":         BspGeneric.lump( BSP.face ),
                "lightmaps":        BspGeneric.lump( BSP.lightmap ),
                "lightgrid":        BspGeneric.lump( BSP.lightgrid ),
                "visdata":          BspGeneric.lump( BSP.visdata ),
                "lightgridarray":   BspGeneric.lump( BSP.lightgridarray )
                }
            
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
            
            self.vertices =     BspGeneric.md3_array(self.vertex,[self.off_verts, self.n_verts])
            self.tcs =          BspGeneric.md3_array(self.tc,[self.off_tcs, self.n_verts])
            self.shaders =      BspGeneric.md3_array(self.shader,[self.off_shaders, self.n_shaders])
            self.triangles =    BspGeneric.md3_array(self.triangle,[self.off_tris, self.n_tris])
            
        class shader:
            size = STRING + INT
            encoding = "<64si"
            
            def remove_file_extention(self, file_path):
                extensions = [".jpg", ".jpeg", ".tga", ".png"]
                for extension in extensions:
                    if file_path.endswith(extension):
                        return file_path.replace(extension, "")
                return file_path
                    
            def __init__(self, array):
                self.name =     self.remove_file_extention(array[0].decode("utf-8", errors="ignore").strip("\0"))
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