# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

from ctypes import (LittleEndianStructure,
                    c_char, c_float, c_int, c_ubyte, sizeof)
from mathutils import Vector


class BSP_HEADER(LittleEndianStructure):
    _fields_ = [
        ("magic_nr", c_char*4),
        ("version_nr", c_int),
    ]


class BSP_ENTITY(LittleEndianStructure):
    _fields_ = [
            ("char", c_char)
    ]


class BSP_SHADER(LittleEndianStructure):
    _fields_ = [
        ("name", c_char * 64),
        ("flags", c_int),
        ("contents", c_int),
    ]


class BSP_PLANE(LittleEndianStructure):
    _fields_ = [
        ("normal", c_float * 3),
        ("distance", c_float),
    ]


class BSP_NODE(LittleEndianStructure):
    _fields_ = [
        ("plane", c_int),
        ("children", c_int * 2),
        ("mins", c_int * 3),
        ("maxs", c_int * 3),
    ]


class BSP_LEAF(LittleEndianStructure):
    _fields_ = [
        ("cluster", c_int),
        ("area", c_int),
        ("mins", c_int * 3),
        ("maxs", c_int * 3),
        ("leafface", c_int),
        ("n_leaffaces", c_int),
        ("leafbrush", c_int),
        ("n_leafbrushes", c_int),
    ]


class BSP_LEAF_FACE(LittleEndianStructure):
    _fields_ = [
        ("face", c_int),
    ]


class BSP_LEAF_BRUSH(LittleEndianStructure):
    _fields_ = [
        ("brush", c_int),
    ]


class BSP_MODEL(LittleEndianStructure):
    _fields_ = [
        ("mins", c_float * 3),
        ("maxs", c_float * 3),
        ("face", c_int),
        ("n_faces", c_int),
        ("brush", c_int),
        ("n_brushes", c_int),
    ]


class BSP_BRUSH(LittleEndianStructure):
    _fields_ = [
        ("brushside", c_int),
        ("n_brushsides", c_int),
        ("texture", c_int),
    ]


class BSP_BRUSH_SIDE(LittleEndianStructure):
    _fields_ = [
        ("plane", c_int),
        ("texture", c_int)
    ]


class BSP_VERTEX(LittleEndianStructure):
    _fields_ = [
        ("position", c_float * 3),
        ("texcoord", c_float * 2),
        ("lm1coord", c_float * 2),
        ("normal", c_float * 3),
        ("color1", c_ubyte * 4),
    ]


class BSP_INDEX(LittleEndianStructure):
    _fields_ = [
        ("offset", c_int),
    ]


class BSP_FOG(LittleEndianStructure):
    _fields_ = [
        ("name", c_char * 64),
        ("brush", c_int),
        ("visibleSide", c_int),
    ]


class BSP_SURFACE(LittleEndianStructure):
    _fields_ = [
        ("texture", c_int),
        ("effect", c_int),
        ("type", c_int),
        ("vertex", c_int),
        ("n_vertexes", c_int),
        ("index", c_int),
        ("n_indexes", c_int),
        ("lm_indexes", c_int),
        ("lm_x", c_int),
        ("lm_y", c_int),
        ("lm_width", c_int),
        ("lm_height", c_int),
        ("lm_origin", c_float * 3),
        ("lm_vecs", c_float * 9),
        ("patch_width", c_int),
        ("patch_height", c_int),
    ]


class BSP_LIGHTMAP(LittleEndianStructure):
    _fields_ = [
        ("map", c_ubyte * (128 * 128 * 3)),
    ]


class BSP_LIGHTGRID(LittleEndianStructure):
    _fields_ = [
        ("ambient1", c_ubyte * 3),
        ("direct1", c_ubyte * 3),
        ("lat_long", c_ubyte * 2)
    ]


class BSP_VIS(LittleEndianStructure):
    _fields_ = [
        ("bit_set", c_ubyte),
    ]


class BSP_INFO:
    bsp_magic = b'IBSP'
    bsp_version = 0x1

    lightgrid_size = [64, 64, 128]
    lightgrid_inverse_size = [1.0 / float(lightgrid_size[0]),
                              1.0 / float(lightgrid_size[1]),
                              1.0 / float(lightgrid_size[2])]

    lightmap_size = [128, 128]
    lightmaps = 1
    lightstyles = 0
    use_lightgridarray = False

    lumps = {"entities":         BSP_ENTITY,
             "shaders":          BSP_SHADER,
             "planes":           BSP_PLANE,
             "nodes":            BSP_NODE,
             "leafs":            BSP_LEAF,
             "leaffaces":        BSP_LEAF_FACE,
             "leafbrushes":      BSP_LEAF_BRUSH,
             "models":           BSP_MODEL,
             "brushes":          BSP_BRUSH,
             "brushsides":       BSP_BRUSH_SIDE,
             "drawverts":        BSP_VERTEX,
             "drawindexes":      BSP_INDEX,
             "fogs":             BSP_FOG,
             "surfaces":         BSP_SURFACE,
             "lightmaps":        BSP_LIGHTMAP,
             "lightgrid":        BSP_LIGHTGRID,
             "visdata":          BSP_VIS
             }

    header_size = sizeof(BSP_HEADER)

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
        vec = Vector(vertex1.normal) + Vector(vertex2.normal)
        vec.normalize()

        lerped_vert = BSP_VERTEX()
        lerped_vert.normal[0] = vec[0]
        lerped_vert.normal[1] = vec[1]
        lerped_vert.normal[2] = vec[2]
        cls.lerp_vec(vertex1.position, vertex2.position, lerped_vert.position)
        cls.lerp_vec(vertex1.texcoord, vertex2.texcoord, lerped_vert.texcoord)
        cls.lerp_vec(vertex1.lm1coord, vertex2.lm1coord, lerped_vert.lm1coord)
        cls.lerp_ivec(vertex1.color1, vertex2.color1, lerped_vert.color1)
        return lerped_vert