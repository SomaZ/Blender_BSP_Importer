from dataclasses import dataclass, field
from .Parsing import guess_map_name
from enum import Enum, IntFlag


class Preset(Enum):
    PREVIEW = "PREVIEW"
    EDITIING = "EDITIING"
    RENDERING = "RENDERING"
    BRUSHES = "BRUSHES"
    SHADOW_BRUSHES = "SHADOW_BRUSHES"


class Surface_Type(IntFlag):
    BAD = 0
    PLANAR = 1
    PATCH = 2
    TRISOUP = 4
    FLARE = 8
    FAKK_TERRAIN = 16
    BRUSH = 32

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


@dataclass
class Import_Settings:

    file: str = ""
    bsp_name: str = ""
    base_paths: list[str] = field(default_factory=list)
    shader_dirs: tuple[str] = "shaders/", "scripts/"
    preset: Preset = Preset.PREVIEW
    min_atlas_size: tuple[int, int] = 128, 128
    subdivisions: int = 2
    log: list[str] = field(default_factory=list)
    front_culling: bool = True
    surface_types: Surface_Type = Surface_Type.BAD
    entity_dict: dict = field(default_factory=dict)

    def __post_init__(self):
        self.bsp_name = guess_map_name(self.file)
