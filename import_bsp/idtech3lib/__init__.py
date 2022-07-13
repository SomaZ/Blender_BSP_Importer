import importlib

if "Parsing" in locals():
    importlib.reload(Parsing)
else:
    from . import Parsing

if "ImportSettings" in locals():
    importlib.reload(ImportSettings)
else:
    from . import ImportSettings

if "BSP" in locals():
    importlib.reload(BSP)
else:
    from . import BSP

if "MAP" in locals():
    importlib.reload(MAP)
else:
    from . import MAP

if "ID3Image" in locals():
    importlib.reload(ID3Image)
else:
    from . import ID3Image

if "ID3VFS" in locals():
    importlib.reload(ID3VFS)
else:
    from . import ID3VFS

if "ID3Shader" in locals():
    importlib.reload(ID3Shader)
else:
    from . import ID3Shader
