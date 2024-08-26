import importlib
if "ID3VFS" in locals():
    importlib.reload(ID3VFS)
if "Parsing" in locals():
    importlib.reload(Parsing)
if "ImportSettings" in locals():
    importlib.reload(ImportSettings)
if "GamePacks" in locals():
    importlib.reload(GamePacks)
if "IBSP" in locals():
    importlib.reload(IBSP)
if "EF2BSP" in locals():
    importlib.reload(EF2BSP)
if "FAKK" in locals():
    importlib.reload(FAKK)
if "RBSP" in locals():
    importlib.reload(RBSP)
if "FBSP" in locals():
    importlib.reload(FBSP)
if "ID3Image" in locals():
    importlib.reload(ID3Image)
if "Helpers" in locals():
    importlib.reload(Helpers)
if "ID3Brushes" in locals():
    importlib.reload(ID3Brushes)
if "ID3Object" in locals():
    importlib.reload(ID3Object)
if "ID3Model" in locals():
    importlib.reload(ID3Model)
if "ID3Shader" in locals():
    importlib.reload(ID3Shader)
if "MAP" in locals():
    importlib.reload(MAP)
if "BSP" in locals():
    importlib.reload(BSP)

from . import BSP, EF2BSP, FAKK, FBSP, IBSP, RBSP, MAP
from . import GamePacks, Helpers, ID3Brushes, ID3Image
from . import ID3Model, ID3Object, ID3Shader, ID3VFS
from . import ImportSettings, Parsing


