from ctypes import (LittleEndianStructure, c_ubyte)
from numpy import array
from .Helpers import normalize
from .RBSP import BSP_INFO as RBSP
from .RBSP import BSP_VERTEX


class BSP_LIGHTMAP(LittleEndianStructure):
    _fields_ = [
        ("map", c_ubyte * (512 * 512 * 3)),
    ]


class BSP_INFO:
    bsp_magic = b'FBSP'
    bsp_version = 0

    lightgrid_size = [64, 64, 128]
    lightgrid_inverse_size = [1.0 / float(lightgrid_size[0]),
                              1.0 / float(lightgrid_size[1]),
                              1.0 / float(lightgrid_size[2])]

    lightmap_size = [512, 512]
    lightmaps = 4
    lightstyles = 4
    use_lightgridarray = True

    lumps = RBSP.lumps.copy()
    lumps["lightmaps"] = BSP_LIGHTMAP

    header = RBSP.header
    header_size = RBSP.header_size

    lightmap_lumps = ("lightmaps",)

    @staticmethod
    def lerp_vec(vec1, vec2, vec_out):
        for i in range(len(vec1)):
            vec_out[i] = (vec1[i] + vec2[i]) / 2.0

    @staticmethod
    def lerp_ivec(vec1, vec2, vec_out):
        for i in range(len(vec1)):
            vec_out[i] = int((vec1[i] + vec2[i]) / 2)

    @classmethod
    def lerp_vertices(
            cls,
            vertex1: BSP_VERTEX,
            vertex2: BSP_VERTEX
            ) -> BSP_VERTEX:

        lerped_vert = BSP_VERTEX()

        vec = normalize(array(vertex1.normal) + array(vertex2.normal))
        lerped_vert.normal[0] = vec[0]
        lerped_vert.normal[1] = vec[1]
        lerped_vert.normal[2] = vec[2]
        cls.lerp_vec(vertex1.position, vertex2.position, lerped_vert.position)
        cls.lerp_vec(vertex1.texcoord, vertex2.texcoord, lerped_vert.texcoord)
        cls.lerp_vec(vertex1.lm1coord, vertex2.lm1coord, lerped_vert.lm1coord)
        cls.lerp_vec(vertex1.lm2coord, vertex2.lm2coord, lerped_vert.lm2coord)
        cls.lerp_vec(vertex1.lm3coord, vertex2.lm3coord, lerped_vert.lm3coord)
        cls.lerp_vec(vertex1.lm4coord, vertex2.lm4coord, lerped_vert.lm4coord)
        cls.lerp_ivec(vertex1.color1, vertex2.color1, lerped_vert.color1)
        cls.lerp_ivec(vertex1.color2, vertex2.color2, lerped_vert.color2)
        cls.lerp_ivec(vertex1.color3, vertex2.color3, lerped_vert.color3)
        cls.lerp_ivec(vertex1.color4, vertex2.color4, lerped_vert.color4)
        return lerped_vert
