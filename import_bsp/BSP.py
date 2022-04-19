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

from ctypes import LittleEndianStructure, c_char, c_int, sizeof
from typing import List
from .RBSP import BSP_INFO as RBSP
from .IBSP import BSP_INFO as IBSP
from .EF2BSP import BSP_INFO as EF2BSP
from .FAKK import BSP_INFO as FAKK
from .Model import ID3Model as MODEL
from .Image import ID3Image as IMAGE
from math import floor, ceil, pi, sin, cos


class BSP_HEADER(LittleEndianStructure):
    _fields_ = [
        ("magic_nr", c_char*4),
        ("version_nr", c_int),
    ]


class BSP_LUMP_HEADER(LittleEndianStructure):
    _fields_ = [
        ("offset", c_int),
        ("size", c_int),
    ]


class BSP_LUMP_READER:
    def __init__(self, header, data_class):
        self.data_class = data_class
        self.class_size = sizeof(self.data_class)
        self.offset = header.offset
        self.size = header.size

    def readFrom(self, bsp_bytearray) -> list:
        data = []
        count = int(self.size / self.class_size)
        for i in range(count):
            data.append(
                self.data_class.from_buffer_copy(
                    bsp_bytearray,
                    self.offset + (i * self.class_size)))
        return data


LIGHTMAP_FORMATS = (".tga", ".png", ".jpg", ".hdr")


class BSP_READER:

    magic_mapping = {
        b'RBSP': RBSP,
        b'IBSP': IBSP,
        b'EF2!': EF2BSP,
        b'FAKK': FAKK,
    }

    def __init__(self, VFS, import_settings):
        self.import_settings = import_settings
        self.lumps = {}
        # for tracking some data down the pipeline
        self.lightgrid_origin = [0.0, 0.0, 0.0]
        self.lightgrid_z_step = 0.0
        self.lightgrid_inverse_dim = [0.0, 0.0, 0.0]
        self.lightgrid_dim = [0.0, 0.0, 0.0]

        byte_array = VFS.get(import_settings.file)

        if byte_array is None:
            raise Exception(
                "Could not open BSP file: " + import_settings.file)

        self.header = BSP_HEADER.from_buffer_copy(byte_array, 0)
        if self.header.magic_nr not in self.magic_mapping:
            raise Exception(
                'BSP format not supported')

        bsp_info = self.magic_mapping[self.header.magic_nr]
        offset = bsp_info.header_size
        for lump in bsp_info.lumps:
            print(lump)
            lump_header = BSP_LUMP_HEADER.from_buffer_copy(byte_array, offset)
            lump_reader = BSP_LUMP_READER(lump_header, bsp_info.lumps[lump])
            self.lumps[lump] = lump_reader.readFrom(byte_array)
            offset += sizeof(BSP_LUMP_HEADER)

        self.map_name = import_settings.bsp_name[:-len(".bsp")]
        self.lump_info = bsp_info.lumps
        self.lightgrid_size = bsp_info.lightgrid_size.copy()
        self.lightgrid_inverse_size = (
            bsp_info.lightgrid_inverse_size.copy())
        self.lightmap_size = bsp_info.lightmap_size.copy()
        self.internal_lightmap_size = bsp_info.lightmap_size.copy()
        self.lightmaps = bsp_info.lightmaps
        self.lightstyles = bsp_info.lightstyles
        self.use_lightgridarray = bsp_info.use_lightgridarray
        self.lerp_vertices = bsp_info.lerp_vertices
        self.lightmap_lumps = bsp_info.lightmap_lumps
        self.compute_lightmap_info(VFS)

    def compute_lightmap_info(self, VFS):
        # get external lightmap data
        # assumes that standard lightmaps are in the lightmap_lumps array first
        # also assumes external lightmaps are all the same format
        self.external_lm_files = []
        if len(self.lumps[self.lightmap_lumps[0]]) == 0:
            reg_path = self.map_name + "/lm_[0-9]{4}"
            for format in LIGHTMAP_FORMATS:
                external_lm_files = VFS.search(reg_path + format)
                if external_lm_files:
                    break
            if external_lm_files:
                self.external_lm_files = external_lm_files

        # check if we should pack lightmap tcs or not,
        # packing lightmap tcs is not supported for shader
        # based external lightmaps
        num_internal_lm_ids = 0
        for face in self.lumps["surfaces"]:
            if self.lightmaps > 1:
                current_max = max(face.lm_indexes)
            else:
                current_max = face.lm_indexes
            if current_max == (1 << 30):
                continue
            num_internal_lm_ids = max(current_max, num_internal_lm_ids)
        self.num_internal_lm_ids = num_internal_lm_ids
        self.lm_packable = num_internal_lm_ids > 0

        # check if we can unwrap for vertex map baking
        self.vm_packable = False
        if ((len(self.lumps[self.lightmap_lumps[0]]) > 0 and
             len(self.external_lm_files) == 0) or
            (len(self.lumps[self.lightmap_lumps[0]]) == 0 and
             len(self.external_lm_files) > 0)):
            self.vm_packable = True

        # check if the map utilizes deluxemapping
        if num_internal_lm_ids <= 0:
            self.deluxemapping = False
        else:
            self.deluxemapping = True
            if self.lightmaps > 1:
                for face in self.lumps["surfaces"]:
                    for i in range(self.lightmaps):
                        if (face.lm_indexes[i] % 2 == 1 and
                                face.lm_indexes[i] >= 0):
                            self.deluxemapping = False
                            break
            else:
                for face in self.lumps["surfaces"]:
                    if (face.lm_indexes % 2 == 1 and
                            face.lm_indexes >= 0):
                        self.deluxemapping = False
                        break

    def compute_packed_lightmap_size(self) -> List[float]:
        if not self.lm_packable:
            return self.internal_lightmap_size

        packed_lightmap_size = [self.internal_lightmap_size[0],
                                self.internal_lightmap_size[1]]
        max_lightmaps = 1
        n_lightmaps = self.num_internal_lm_ids + 1
        # grow lightmap atlas if needed
        for i in range(6):
            if (n_lightmaps > int(max_lightmaps)):
                packed_lightmap_size[0] *= 2
                packed_lightmap_size[1] *= 2
                num_columns = packed_lightmap_size[0] / \
                    self.internal_lightmap_size[0]
                num_rows = packed_lightmap_size[1] / \
                    self.internal_lightmap_size[1]
                max_lightmaps = num_columns * num_rows
            else:
                break
        if self.deluxemapping:
            packed_lightmap_size[0] = packed_lightmap_size[0] // 2
            packed_lightmap_size[1] = packed_lightmap_size[1] // 2
        return packed_lightmap_size

    def get_bsp_models(self) -> List[MODEL]:
        pack_lightmap_uvs = (
            self.lightmap_size[0] != self.internal_lightmap_size[0] or
            self.lightmap_size[1] != self.internal_lightmap_size[1]
        )

        models = []
        for i in range(len(self.lumps["models"])):
            model = MODEL("*"+str(i))
            model.add_bsp_model(self, i, self.import_settings)
            if pack_lightmap_uvs:
                model.pack_lightmap_uvs(self)
            if model.current_index > 0:
                models.append(model)

            model = MODEL("*"+str(i)+".BRUSHES")
            model.add_bsp_model_brushes(self, i, self.import_settings)
            if model.current_index > 0:
                models.append(model)
        return models

    def pack_lightmap(
            self,
            lightmap_lump,
            deluxemapped,
            deluxe,
            internal=True,
            color_components=3
            ):
        num_columns = self.lightmap_size[0] / \
            self.internal_lightmap_size[0]
        n_lightmaps = len(lightmap_lump)

        numPixels = self.lightmap_size[0] * \
            self.lightmap_size[1] * color_components
        pixels = [0]*numPixels
        for pixel in range(
                self.lightmap_size[0] * self.lightmap_size[1]):
            # pixel position in packed texture
            row = pixel % self.lightmap_size[0]
            colum = floor(pixel/self.lightmap_size[1])

            # lightmap quadrant
            quadrant_x = floor(row/self.internal_lightmap_size[0])
            quadrant_y = floor(colum/self.internal_lightmap_size[1])
            lightmap_id = floor(
                quadrant_x + (num_columns * quadrant_y))

            if deluxemapped:
                lightmap_id = lightmap_id * 2
                if deluxe:
                    lightmap_id += 1

            if (lightmap_id > n_lightmaps-1) or (lightmap_id < 0):
                continue
            else:
                # pixel id in lightmap
                lm_x = row % self.internal_lightmap_size[0]
                lm_y = colum % self.internal_lightmap_size[1]
                pixel_id = floor(
                    lm_x + (lm_y * self.internal_lightmap_size[0]))
                pixel_id *= color_components
                if internal:
                    lightmap = lightmap_lump[lightmap_id].map
                else:
                    lightmap = lightmap_lump[lightmap_id]
                pixels[color_components*pixel] = lightmap[pixel_id]
                pixels[color_components*pixel+1] = lightmap[pixel_id+1]
                pixels[color_components*pixel+2] = lightmap[pixel_id+2]
                if color_components == 4:
                    pixels[color_components*pixel+3] = 1.0
        return pixels

    def get_bsp_images(self):
        pack_lightmaps = (
            self.lightmap_size[0] != self.internal_lightmap_size[0] or
            self.lightmap_size[1] != self.internal_lightmap_size[1]
        )

        if pack_lightmaps:
            min_lightmap_size = self.compute_packed_lightmap_size()
            if (min_lightmap_size[0] < self.lightmap_size[0] or
                    min_lightmap_size[1] < self.lightmap_size[1]):
                raise Exception("Chosen packed lightmap size is not big "
                                "enough to store all internal lightmaps")

        if len(self.lightmap_lumps) == 0:
            return []

        lightmaps = []
        for lightmap_name in self.lightmap_lumps:
            if not pack_lightmaps:
                for id, bsp_image in enumerate(self.lumps[lightmap_name]):
                    image = IMAGE()
                    image_prefix = lightmap_name
                    if image_prefix == "lightmaps":
                        if self.deluxemapping and id % 2 == 1:
                            image_prefix = "dm_"
                        else:
                            image_prefix = "lm_"

                    lightmap_id = id
                    if self.deluxemapping:
                        lightmap_id = lightmap_id // 2

                    image.name = image_prefix + str(lightmap_id).zfill(4)
                    image.width = self.internal_lightmap_size[0]
                    image.height = self.internal_lightmap_size[1]
                    image.num_components = 3
                    image.bppc = 8
                    image.data_type = "bytes"
                    image.data = bsp_image.map
                    lightmaps.append(image)
            else:
                deluxemapped = (
                    self.deluxemapping and lightmap_name == "lightmaps")
                if len(self.lumps[lightmap_name]) <= 0:
                    continue
                pixels = self.pack_lightmap(
                    self.lumps[lightmap_name],
                    deluxemapped,
                    False)
                image = IMAGE()
                image.name = "$" + lightmap_name
                if lightmap_name == "lightmaps":
                    image.name = "$lightmap"
                image.width = self.lightmap_size[0]
                image.height = self.lightmap_size[1]
                image.num_components = 3
                image.bppc = 8
                image.data_type = "bytes"
                image.data = pixels
                lightmaps.append(image)

                if deluxemapped:
                    pixels = self.pack_lightmap(
                        self.lumps[lightmap_name],
                        deluxemapped,
                        True)
                    image = IMAGE()
                    image.name = "$deluxemap"
                    image.width = self.lightmap_size[0]
                    image.height = self.lightmap_size[1]
                    image.num_components = 3
                    image.bppc = 8
                    image.data_type = "bytes"
                    image.data = pixels
                    lightmaps.append(image)

        return lightmaps
