from dataclasses import dataclass, field
from .Parsing import guess_map_name
from enum import Enum, IntFlag
from typing import List, Tuple

class Preset(Enum):
    PREVIEW = "PREVIEW"
    EDITING = "EDITING"
    RENDERING = "RENDERING"
    BRUSHES = "BRUSHES"
    SHADOW_BRUSHES = "SHADOW_BRUSHES"
    ONLY_LIGHTS = "ONLY_LIGHTS"

class NormalMapOption(Enum):
    OPENGL = "OPENGL"
    DIRECTX = "DIRECTX"
    SKIP = "SKIP"

class Surface_Type(IntFlag):
    BAD = 0
    PLANAR = 1
    PATCH = 2
    TRISOUP = 4
    FLARE = 8
    FAKK_TERRAIN = 16
    BRUSH = 32
    ALL = (BRUSH |
           PLANAR |
           PATCH |
           TRISOUP |
           FAKK_TERRAIN |
           FLARE
           )

    @classmethod
    def bsp_value(cls, value):
        values = {
            0: cls.BAD,
            1: cls.PLANAR,
            2: cls.PATCH,
            3: cls.TRISOUP,
            4: cls.FLARE,
            5: cls.FAKK_TERRAIN
        }
        if value in values:
            return values[value]
        else:
            return cls.BAD


class Vert_lit_handling(IntFlag):
    KEEP = 0
    UV_MAP = 1
    PRIMITIVE_PACK = 2

@dataclass
class Import_Settings:

    file: str = ""
    bsp_name: str = ""
    base_paths: List[str] = field(default_factory=list)
    shader_dirs: Tuple[str] = ("shaders/", "scripts/")
    preset: Preset = Preset.PREVIEW
    min_atlas_size: Tuple[int, int] = (128, 128)
    subdivisions: int = 2
    log: List[str] = field(default_factory=list)
    front_culling: bool = True
    surface_types: Surface_Type = Surface_Type.BAD
    entity_dict: dict = field(default_factory=dict)
    vert_lit_handling: Vert_lit_handling = Vert_lit_handling.KEEP
    current_vert_pack_index = 0
    normal_map_option: NormalMapOption = NormalMapOption.DIRECTX

    def __post_init__(self):
        self.bsp_name = guess_map_name(self.file)
