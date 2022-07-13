from .ID3Image import ID3Image as Image
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
    image.data = [[255.0] * 256]
    return image


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
