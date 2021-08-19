import imp

if "bpy" not in locals():
    import bpy
    
if "Image" in locals():
    imp.reload( Image )
else:
    from . import Image
    
from .Parsing import guess_model_name, fillName

from math import pi, sin, cos, atan2, acos, sqrt
from mathutils import Matrix
from bpy_extras.io_utils import unpack_list

model_loaders = {   "md3":load_md3(),
                    "tik":load_tik(),
                    "tan":load_tan(),
                    #"skl":load_skl(),
                    #"glm":load_glm()
                }

def BSP_Load_Model(settings, file_name)