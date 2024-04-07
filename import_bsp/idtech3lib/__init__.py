import importlib
if "BSP" in locals():
    importlib.reload(BSP)
if "EF2BSP" in locals():
    importlib.reload(EF2BSP)
if "FAKK" in locals():
    importlib.reload(FAKK)
if "FBSP" in locals():
    importlib.reload(FBSP)
if "IBSP" in locals():
    importlib.reload(IBSP)
if "RBSP" in locals():
    importlib.reload(RBSP)
if "MAP" in locals():
    importlib.reload(MAP)
if "GamePacks" in locals():
    importlib.reload(GamePacks)
if "Helpers" in locals():
    importlib.reload(Helpers)
if "ID3Brushes" in locals():
    importlib.reload(ID3Brushes)
if "ID3Image" in locals():
    importlib.reload(ID3Image)
if "ID3Model" in locals():
    importlib.reload(ID3Model)
if "ID3Object" in locals():
    importlib.reload(ID3Object)
if "ID3Shader" in locals():
    importlib.reload(ID3Shader)
if "ID3VFS" in locals():
    importlib.reload(ID3VFS)
if "ImportSettings" in locals():
    importlib.reload(ImportSettings)
if "Parsing" in locals():
    importlib.reload(Parsing)

from . import BSP, EF2BSP, FAKK, FBSP, IBSP, RBSP, MAP
from . import GamePacks, Helpers, ID3Brushes, ID3Image
from . import ID3Model, ID3Object, ID3Shader, ID3VFS
from . import ImportSettings, Parsing


