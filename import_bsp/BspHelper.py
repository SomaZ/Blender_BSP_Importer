# ----------------------------------------------------------------------------#
# TODO:  refactor loading bsp files and md3 files, right now its a mess o.O
# TODO:  build patches via c library for speed?
# ----------------------------------------------------------------------------#


from .IDTech3Lib.ID3Image import ID3Image as Image
from math import floor, ceil
from numpy import array, dot, sin, cos, sqrt, pi


def normalize(vector):
    sqr_length = dot(vector, vector)
    if sqr_length == 0.0:
        return array((0.0, 0.0, 0.0))
    return vector / sqrt(sqr_length)


def create_white_image():
    image = Image()
    image.name = "$whiteimage"
    image.width = 8
    image.height = 8
    image.num_components = 4
    image.data = [[0.0] * 256]
    return image


def create_new_image(name, width, height, data):
    image = Image()
    image.name = name
    image.width = width
    image.height = height
    image.data = data
    return image


def pack_lightmaps(bsp, lightmap_lump_name, import_settings):
    return
    # bpy.context.scene.id_tech_3_lightmaps_per_row = num_rows
    # bpy.context.scene.id_tech_3_lightmaps_per_column = num_columns


def clamp_shift_tc(tc, min_tc, max_tc, u_shift, v_shift, flip_v):
    u = min(max(tc[0], min_tc), max_tc) + u_shift
    v = min(max(tc[1], min_tc), max_tc) + v_shift
    if flip_v:
        return (u, 1.0-v)
    return (u, v)


def unwrap_vert_map(vert_id, vertmap_size, current_id):
    id = int(floor(current_id/3.0))
    even = id % 2 == 0
    id += floor(id / 2)
    current_x = id % (vertmap_size[0] - 1)
    current_y = 2 * floor(id / (vertmap_size[0] - 1))

    eps_u = 0.005
    if even:
        eps_small = 0.495
        eps_big = 1.505
        if vert_id == 0:
            return ((current_x + eps_small + eps_u) / vertmap_size[0],
                    (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 1:
            return ((current_x + eps_small + eps_u) / vertmap_size[0],
                    (current_y + eps_small) / vertmap_size[1])
        elif vert_id == 2:
            return ((current_x + eps_big + eps_u) / vertmap_size[0],
                    (current_y + eps_small) / vertmap_size[1])
        # special case for patch surfaces
        elif vert_id == 3:
            return ((current_x + eps_big + eps_u) / vertmap_size[0],
                    (current_y + eps_big) / vertmap_size[1])
        else:
            return (0.0, 0.0)
    else:
        eps_small = 0.505
        eps_big = 1.505
        current_x += 1
        if vert_id == 0:
            return ((current_x - eps_small - eps_u) / vertmap_size[0],
                    (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 1:
            return ((current_x + eps_small + eps_u) / vertmap_size[0],
                    (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 2:
            return ((current_x + eps_small + eps_u) / vertmap_size[0],
                    (current_y + 0.49) / vertmap_size[1])
        # special case for patch surfaces
        elif vert_id == 3:
            return ((current_x - eps_small - eps_u) / vertmap_size[0],
                    (current_y + 0.49) / vertmap_size[1])
        else:
            return (0.0, 0.0)


def pack_lm_tc(tc,
               lightmap_id,
               lightmap_size,
               import_settings,
               v_id=0,
               current_v_id=None):
    if (lightmap_id < 0):
        if current_v_id is not None:
            return unwrap_vert_map(v_id, [2048.0, 2048.0], current_v_id)
        else:
            return clamp_shift_tc(tc, 0.0, 1.0, lightmap_id, 0.0, True)

    packed_lm_size = import_settings.packed_lightmap_size
    num_columns = packed_lm_size[0] / lightmap_size[0]
    num_rows = packed_lm_size[1] / lightmap_size[1]
    scale_value = (lightmap_size[0] / packed_lm_size[0],
                   lightmap_size[1] / packed_lm_size[1])

    x = (lightmap_id % num_columns) * scale_value[0]
    y = floor(lightmap_id/num_columns) * scale_value[1]

    packed_tc = (tc[0]*scale_value[0] + x, tc[1]*scale_value[1]+y)
    return packed_tc


def get_lm_id(tc, lightmap_size, packed_lm_size):
    row = tc[0]*packed_lm_size[0]
    column = tc[1]*packed_lm_size[1]
    quadrant_x = floor(row/lightmap_size[0])
    quadrant_y = floor(column/lightmap_size[1])

    scale = packed_lm_size[0] / lightmap_size[0]
    return floor(quadrant_x + (scale * quadrant_y))


def unpack_lm_tc(tc, lightmap_size, packed_lm_size):
    row = tc[0]*packed_lm_size[0]
    column = tc[1]*packed_lm_size[1]
    quadrant_x = floor(row/lightmap_size[0])
    quadrant_y = floor(column/lightmap_size[1])

    scale = (packed_lm_size[0] / lightmap_size[0],
             packed_lm_size[1] / lightmap_size[1])
    lightmap_id = floor(quadrant_x + (scale[0] * quadrant_y))

    quadrant_scale = [lightmap_size[0] / packed_lm_size[0],
                      lightmap_size[1] / packed_lm_size[1]]

    tc[0] = (tc[0] - (quadrant_x * quadrant_scale[0])) * scale[0]
    tc[1] = (tc[1] - (quadrant_y * quadrant_scale[1])) * scale[1]
    return lightmap_id


# appends a 3 component byte color to a pixel list
def append_byte_to_color_list(byte_color, list, scale):
    list.append(byte_color[0]*scale)
    list.append(byte_color[1]*scale)
    list.append(byte_color[2]*scale)
    list.append(1.0)


def pack_lightgrid_images(bsp):
    world_mins = bsp.lumps["models"][0].mins
    world_maxs = bsp.lumps["models"][0].maxs

    lightgrid_origin = [bsp.lightgrid_size[0] *
                        ceil(world_mins[0] / bsp.lightgrid_size[0]),
                        bsp.lightgrid_size[1] *
                        ceil(world_mins[1] / bsp.lightgrid_size[1]),
                        bsp.lightgrid_size[2] *
                        ceil(world_mins[2] / bsp.lightgrid_size[2])]

    bsp.lightgrid_origin = lightgrid_origin

    maxs = [bsp.lightgrid_size[0] *
            floor(world_maxs[0] / bsp.lightgrid_size[0]),
            bsp.lightgrid_size[1] *
            floor(world_maxs[1] / bsp.lightgrid_size[1]),
            bsp.lightgrid_size[2] *
            floor(world_maxs[2] / bsp.lightgrid_size[2])]

    lightgrid_dimensions = [(maxs[0] - lightgrid_origin[0]) /
                            bsp.lightgrid_size[0] + 1,
                            (maxs[1] - lightgrid_origin[1]) /
                            bsp.lightgrid_size[1] + 1,
                            (maxs[2] - lightgrid_origin[2]) /
                            bsp.lightgrid_size[2] + 1]

    bsp.lightgrid_inverse_dim = [1.0 / lightgrid_dimensions[0],
                                 1.0 /
                                 (lightgrid_dimensions[1]
                                  * lightgrid_dimensions[2]),
                                 1.0 / lightgrid_dimensions[2]]

    bsp.lightgrid_z_step = 1.0 / lightgrid_dimensions[2]
    bsp.lightgrid_dim = lightgrid_dimensions

    a1_pixels = []
    a2_pixels = []
    a3_pixels = []
    a4_pixels = []
    d1_pixels = []
    d2_pixels = []
    d3_pixels = []
    d4_pixels = []
    l_pixels = []

    num_elements = int(lightgrid_dimensions[0] *
                       lightgrid_dimensions[1] *
                       lightgrid_dimensions[2])
    if "lightgridarray" in bsp.lumps:
        num_elements_bsp = len(bsp.lumps["lightgridarray"])
    else:
        num_elements_bsp = len(bsp.lumps["lightgrid"])

    if num_elements == num_elements_bsp:
        for pixel in range(num_elements):

            if bsp.use_lightgridarray:
                index = bsp.lumps["lightgridarray"][pixel].data
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

            ambient1 = bsp.lumps["lightgrid"][index].ambient1
            direct1 = bsp.lumps["lightgrid"][index].direct1
            if bsp.lightmaps > 1:
                ambient2 = bsp.lumps["lightgrid"][index].ambient2
                ambient3 = bsp.lumps["lightgrid"][index].ambient3
                ambient4 = bsp.lumps["lightgrid"][index].ambient4
                direct2 = bsp.lumps["lightgrid"][index].direct2
                direct3 = bsp.lumps["lightgrid"][index].direct3
                direct4 = bsp.lumps["lightgrid"][index].direct4

            lat = ((bsp.lumps["lightgrid"][index].lat_long[0]/255.0) *
                   2.0 * pi)
            long = ((bsp.lumps["lightgrid"][index].lat_long[1]/255.0) *
                    2.0 * pi)

            slat = sin(lat)
            clat = cos(lat)
            slong = sin(long)
            clong = cos(long)

            l_vec = normalize(array(
                (clat * slong, slat * slong, clong)))

            color_scale = 1.0/255.0
            append_byte_to_color_list(ambient1, a1_pixels, color_scale)
            append_byte_to_color_list(direct1, d1_pixels, color_scale)
            if bsp.lightmaps > 1:
                append_byte_to_color_list(ambient2, a2_pixels, color_scale)
                append_byte_to_color_list(ambient3, a3_pixels, color_scale)
                append_byte_to_color_list(ambient4, a4_pixels, color_scale)
                append_byte_to_color_list(direct2, d2_pixels, color_scale)
                append_byte_to_color_list(direct3, d3_pixels, color_scale)
                append_byte_to_color_list(direct4, d4_pixels, color_scale)

            append_byte_to_color_list(l_vec, l_pixels, 1.0)
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
    images = []
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

    if bsp.lightmaps > 1:
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
