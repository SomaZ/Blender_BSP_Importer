from ctypes import LittleEndianStructure, c_char, c_int, sizeof
from .RBSP import BSP_INFO as RBSP
from .IBSP import BSP_INFO as IBSP
from .EF2BSP import BSP_INFO as EF2BSP
from .FAKK import BSP_INFO as FAKK
from .FBSP import BSP_INFO as FBSP
from .ID3Model import ID3Model as MODEL
from .ID3Object import ID3Object as OBJECT
from .ID3Image import ID3Image as IMAGE
from .ID3Shader import get_material_dicts
from math import floor, ceil
from numpy import array, dot, sin, cos, sqrt, pi
from struct import unpack
from typing import List, Tuple
from .ImportSettings import Vert_lit_handling


def normalize(vector):
    sqr_length = dot(vector, vector)
    if sqr_length == 0.0:
        return array((0.0, 0.0, 0.0))
    return vector / sqrt(sqr_length)


def create_new_image(name, width, height, data):
    image = IMAGE()
    image.name = name
    image.width = int(width)
    image.height = int(height)
    image.data = data
    image.num_components = 4
    return image


# appends a 3 component byte color to a pixel list
def append_byte_to_color_list(byte_color, list, scale):
    list.append(byte_color[0]*scale)
    list.append(byte_color[1]*scale)
    list.append(byte_color[2]*scale)
    list.append(255.0 * scale)


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

    MAGIC_MAPPING = {
        b'RBSP': RBSP,
        b'IBSP': IBSP,
        b'EF2!': EF2BSP,
        b'FAKK': FAKK,
        b'FBSP': FBSP,
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

        header = BSP_HEADER.from_buffer_copy(byte_array, 0)
        if header.magic_nr not in self.MAGIC_MAPPING:
            raise Exception(
                'BSP format not supported')

        bsp_info = self.MAGIC_MAPPING[header.magic_nr]
        self.header = bsp_info.header.from_buffer_copy(byte_array, 0)
        offset = bsp_info.header_size
        for lump in bsp_info.lumps:
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
        self.find_shader_based_external_lightmaps(VFS)

    def set_entity_lump(self, entity_text):
        bsp_info = self.MAGIC_MAPPING[self.header.magic_nr]
        self.lumps["entities"] = [bsp_info.lumps["entities"]
                                  (char=bytes(c, "latin-1"))
                                  for c in entity_text]

    def to_bytes(self):
        byte_array = bytearray()
        offset = 0

        byte_array += bytes(self.header)
        offset += sizeof(self.header)

        lumps = {}
        lump_sizes = {}
        for lump in self.lumps:
            lumps[lump] = bytearray()
            lump_sizes[lump] = 0
            for entry in self.lumps[lump]:
                lumps[lump] += bytes(entry)
                lump_sizes[lump] += sizeof(entry)

        offset += sizeof(BSP_LUMP_HEADER) * len(self.lumps)
        for lump in self.lumps:
            l_header = BSP_LUMP_HEADER(
                offset=offset,
                size=lump_sizes[lump]
            )
            byte_array += bytes(l_header)
            offset += lump_sizes[lump]

        for lump in self.lumps:
            byte_array += lumps[lump]

        return byte_array

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
        num_internal_lm_ids = -1
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

        if num_internal_lm_ids == 0 and len(self.external_lm_files) == 2:
            self.deluxemapping = True
            return

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

    def compute_packed_lightmap_size(self) -> Tuple[int, int]:
        if not self.lm_packable:
            return self.internal_lightmap_size

        packed_lightmap_size = [self.internal_lightmap_size[0],
                                self.internal_lightmap_size[1]]
        max_lightmaps = 1
        n_lightmaps = self.num_internal_lm_ids + 1
        if self.deluxemapping:
            n_lightmaps += 1
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
            packed_lightmap_size[1] = packed_lightmap_size[1] // 2
        return tuple(map(int, packed_lightmap_size))
    
    def find_shader_based_external_lightmaps(self, VFS):
        materials = []
        material_id_matching = {}
        for shader_id, shader in enumerate(self.lumps["shaders"]):
            shader_name = shader.name.decode(encoding="latin-1").lower()
            material_id_matching[shader_name] = shader_id
            materials.append(shader_name)
        material_dicts = get_material_dicts(VFS, self.import_settings, materials)
        self.lightmap_tc_shaders = []
        for material in material_dicts:
            attributes, stages = material_dicts[material]
            for stage in stages:
                if "tcgen" in stage and stage["tcgen"] == "lightmap":
                    self.lightmap_tc_shaders.append(material_id_matching[material])

    def get_bsp_entity_objects(self) -> dict:
        return OBJECT.get_entity_objects_from_bsp(self)

    def get_bsp_model(self, model_id) -> MODEL:
        pack_lightmap_uvs = (
            self.lightmap_size[0] != self.internal_lightmap_size[0] or
            self.lightmap_size[1] != self.internal_lightmap_size[1]
        )
        model = MODEL("*"+str(model_id))
        model.add_bsp_model(self, model_id, self.import_settings)
        if model.current_index > 0:
            if pack_lightmap_uvs:
                model.pack_lightmap_uvs(self)
            if self.import_settings.vert_lit_handling == Vert_lit_handling.PRIMITIVE_PACK:
                model.pack_vertmap_uvs(self, self.import_settings)
            elif self.import_settings.vert_lit_handling == Vert_lit_handling.UV_MAP:
                model.copy_vertmap_uvs_from_diffuse(self)
            return model

        model = MODEL("*"+str(model_id))
        model.add_bsp_model_brushes(self, model_id, self.import_settings)
        if model.current_index > 0:
            return model
        return None

    def get_bsp_models(self) -> List[MODEL]:
        models = []
        for i in range(len(self.lumps["models"])):
            model = self.get_bsp_model(i)
            if model is not None:
                models.append(model)

        return models
    
    def get_bsp_fogs(self) -> List[MODEL]:
        models = []
        for i in range(len(self.lumps["fogs"])):
            current_fog = self.lumps["fogs"][i]
            fog_name = current_fog.name.decode("latin-1")
            model = MODEL("{}_{}".format(fog_name, i))
            model.init_bsp_brush_data(self)

            # global fog
            if current_fog.brush == -1:
                world = self.lumps["models"][0]
                model.add_bsp_bounds_mesh(
                    self, world.mins,
                    world.maxs,
                    fog_name)
            else:
                model.add_bsp_brush(self, current_fog.brush, self.import_settings)

            for i in range(len(model.material_names)):
                model.material_names[i] = model.material_names[i] + ".fog"
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
            ) -> List[float]:
        num_columns = self.lightmap_size[0] / self.internal_lightmap_size[0]

        numPixels = self.lightmap_size[0] * \
            self.lightmap_size[1] * color_components
        pixels = [0.0]*numPixels

        lm_width = self.internal_lightmap_size[0]
        lm_height = self.internal_lightmap_size[1]

        for current_id, lightmap in enumerate(lightmap_lump):
            lm_id = current_id
            if deluxemapped:
                if deluxe and lm_id % 2 == 0:
                    continue
                if not deluxe and lm_id % 2 == 1:
                    continue
                lm_id = int(current_id / 2)

            target_xy = (lm_id % num_columns) * lm_width
            target_xy += ((lm_id // num_columns)
                          * lm_width * lm_height
                          * num_columns)
            lightmap_data = lightmap.map if internal else lightmap
            for lm_pixel in range(int(len(lightmap_data) / color_components)):
                pixel_target = target_xy
                pixel_target += lm_pixel % lm_width
                # flip internal lightmaps
                if internal:
                    pixel_target += (lm_height - 1 - (lm_pixel // lm_width)) * lm_width * num_columns
                else:
                    pixel_target += (lm_pixel // lm_width) * lm_width * num_columns
                pixel_target = int(pixel_target)
                pixels[pixel_target*color_components] = (
                    lightmap_data[lm_pixel*color_components])
                pixels[pixel_target*color_components+1] = (
                    lightmap_data[lm_pixel*color_components+1])
                pixels[pixel_target*color_components+2] = (
                    lightmap_data[lm_pixel*color_components+2])
                if color_components == 4:
                    pixels[pixel_target*color_components+3] = 1.0

        return pixels

    def get_bsp_images(self) -> List[IMAGE]:
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

        images = []
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
                    image.data = bsp_image.map
                    images.append(image)
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
                image.data = pixels
                images.append(image)

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
                    image.data = pixels
                    images.append(image)

        # ------------------------------------------------------ #
        # ------------------LIGHTGRID IMAGES-------------------- #
        # ------------------------------------------------------ #

        world_mins = array(self.lumps["models"][0].mins, dtype='float32')
        world_maxs = array(self.lumps["models"][0].maxs, dtype='float32')

        self.lightgrid_size = array(self.lightgrid_size, dtype='float32')

        if (self.lightgrid_size[0] == 0.0 or
            self.lightgrid_size[1] == 0.0 or
            self.lightgrid_size[2] == 0.0):
            return images

        lightgrid_origin = [self.lightgrid_size[0] *
                            ceil(world_mins[0] / self.lightgrid_size[0]),
                            self.lightgrid_size[1] *
                            ceil(world_mins[1] / self.lightgrid_size[1]),
                            self.lightgrid_size[2] *
                            ceil(world_mins[2] / self.lightgrid_size[2])]
        self.lightgrid_origin = array(lightgrid_origin, dtype='float32')

        maxs = [self.lightgrid_size[0] *
                floor(world_maxs[0] / self.lightgrid_size[0]),
                self.lightgrid_size[1] *
                floor(world_maxs[1] / self.lightgrid_size[1]),
                self.lightgrid_size[2] *
                floor(world_maxs[2] / self.lightgrid_size[2])]
        
        maxs = array(maxs, dtype='float32')
        lightgrid_dimensions = (
            (maxs - self.lightgrid_origin) / self.lightgrid_size) + array((1.0, 1.0, 1.0))
        
        if (lightgrid_dimensions[0] == 0.0 or
            lightgrid_dimensions[1] == 0.0 or
            lightgrid_dimensions[2] == 0.0):
            return images

        self.lightgrid_inverse_dim = [1.0 / lightgrid_dimensions[0],
                                      1.0 /
                                      (lightgrid_dimensions[1]
                                      * lightgrid_dimensions[2]),
                                      1.0 / lightgrid_dimensions[2]]

        self.lightgrid_z_step = 1.0 / lightgrid_dimensions[2]
        self.lightgrid_dim = lightgrid_dimensions

        a1_pixels = []
        a2_pixels = []
        a3_pixels = []
        a4_pixels = []
        d1_pixels = []
        d2_pixels = []
        d3_pixels = []
        d4_pixels = []
        l_pixels = []

        num_elements = (int(lightgrid_dimensions[0]) *
                           int(lightgrid_dimensions[1]) *
                           int(lightgrid_dimensions[2]))
        if "lightgridarray" in self.lumps:
            num_elements_bsp = len(self.lumps["lightgridarray"])
        else:
            num_elements_bsp = len(self.lumps["lightgrid"])

        if num_elements == 0:
            return images

        if num_elements == num_elements_bsp:
            for pixel in range(num_elements):

                if "lightgridarray" in self.lumps:
                    index = unpack(
                        "<H",
                        self.lumps["lightgridarray"][pixel])[0]
                else:
                    index = pixel

                ambient1 = array((0, 0, 0))
                ambient2 = array((0, 0, 0))
                ambient3 = array((0, 0, 0))
                ambient4 = array((0, 0, 0))
                direct1 = array((0, 0, 0))
                direct2 = array((0, 0, 0))
                direct3 = array((0, 0, 0))
                direct4 = array((0, 0, 0))
                l_vec = array((0, 0, 0))

                ambient1 = self.lumps["lightgrid"][index].ambient1
                direct1 = self.lumps["lightgrid"][index].direct1
                if self.lightmaps > 1:
                    ambient2 = self.lumps["lightgrid"][index].ambient2
                    ambient3 = self.lumps["lightgrid"][index].ambient3
                    ambient4 = self.lumps["lightgrid"][index].ambient4
                    direct2 = self.lumps["lightgrid"][index].direct2
                    direct3 = self.lumps["lightgrid"][index].direct3
                    direct4 = self.lumps["lightgrid"][index].direct4

                lat = ((self.lumps["lightgrid"][index].lat_long[0]/255.0) *
                       2.0 * pi)
                long = ((self.lumps["lightgrid"][index].lat_long[1]/255.0) *
                        2.0 * pi)

                slat = sin(lat)
                clat = cos(lat)
                slong = sin(long)
                clong = cos(long)

                l_vec = normalize(array(
                    (clat * slong, slat * slong, clong)))

                color_scale = 1.0
                append_byte_to_color_list(ambient1, a1_pixels, color_scale)
                append_byte_to_color_list(direct1, d1_pixels, color_scale)
                if self.lightmaps == 4:
                    append_byte_to_color_list(ambient2, a2_pixels, color_scale)
                    append_byte_to_color_list(ambient3, a3_pixels, color_scale)
                    append_byte_to_color_list(ambient4, a4_pixels, color_scale)
                    append_byte_to_color_list(direct2, d2_pixels, color_scale)
                    append_byte_to_color_list(direct3, d3_pixels, color_scale)
                    append_byte_to_color_list(direct4, d4_pixels, color_scale)

                append_byte_to_color_list(l_vec, l_pixels, 255.0)
        else:
            a1_pixels = [0.3 for i in range(num_elements*4)]
            a2_pixels = [0.0 for i in range(num_elements*4)]
            a3_pixels = [0.0 for i in range(num_elements*4)]
            a4_pixels = [0.0 for i in range(num_elements*4)]
            d1_pixels = [0.0 for i in range(num_elements*4)]
            d2_pixels = [0.0 for i in range(num_elements*4)]
            d3_pixels = [0.0 for i in range(num_elements*4)]
            d4_pixels = [0.0 for i in range(num_elements*4)]
            l_pixels = [0.0 for i in range(num_elements*4)]
            print("Lightgridarray mismatch!")
            print(str(num_elements) + " != " + str(num_elements_bsp))

        images.append(create_new_image(
            "$lightgrid_ambient1",
            lightgrid_dimensions[0],
            lightgrid_dimensions[1] * lightgrid_dimensions[2],
            a1_pixels))

        images.append(create_new_image(
            "$lightgrid_direct1",
            lightgrid_dimensions[0],
            lightgrid_dimensions[1] * lightgrid_dimensions[2],
            d1_pixels))

        if self.lightmaps > 1:
            images.append(create_new_image(
                "$lightgrid_ambient2",
                lightgrid_dimensions[0],
                lightgrid_dimensions[1] * lightgrid_dimensions[2],
                a2_pixels))
            images.append(create_new_image(
                "$lightgrid_ambient3",
                lightgrid_dimensions[0],
                lightgrid_dimensions[1] * lightgrid_dimensions[2],
                a3_pixels))
            images.append(create_new_image(
                "$lightgrid_ambient4",
                lightgrid_dimensions[0],
                lightgrid_dimensions[1] * lightgrid_dimensions[2],
                a4_pixels))

            images.append(create_new_image(
                "$lightgrid_direct2",
                lightgrid_dimensions[0],
                lightgrid_dimensions[1] * lightgrid_dimensions[2],
                d2_pixels))
            images.append(create_new_image(
                "$lightgrid_direct3",
                lightgrid_dimensions[0],
                lightgrid_dimensions[1] * lightgrid_dimensions[2],
                d3_pixels))
            images.append(create_new_image(
                "$lightgrid_direct4",
                lightgrid_dimensions[0],
                lightgrid_dimensions[1] * lightgrid_dimensions[2],
                d4_pixels))

        images.append(create_new_image(
            "$lightgrid_vector",
            lightgrid_dimensions[0],
            lightgrid_dimensions[1] *
            lightgrid_dimensions[2],
            l_pixels))

        return images
