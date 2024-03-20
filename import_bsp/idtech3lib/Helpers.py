from .ID3Image import ID3Image as Image
from math import floor, ceil
from numpy import array, dot, sin, cos, sqrt, pi


def avg_vec2(vec1, vec2):
    return ((vec1[0] + vec2[0]) * 0.5,
            (vec1[1] + vec2[1]) * 0.5)


def avg_vec3(vec1, vec2):
    return ((vec1[0] + vec2[0]) * 0.5,
            (vec1[1] + vec2[1]) * 0.5,
            (vec1[2] + vec2[2]) * 0.5)


def avg_ivec2(vec1, vec2):
    return (int((vec1[0] + vec2[0]) * 0.5),
            int((vec1[1] + vec2[1]) * 0.5))


def avg_ivec3(vec1, vec2):
    return (int((vec1[0] + vec2[0]) * 0.5),
            int((vec1[1] + vec2[1]) * 0.5),
            int((vec1[2] + vec2[2]) * 0.5))


def normalize(vector):
    sqr_length = dot(vector, vector)
    if sqr_length == 0.0:
        return array((0.0, 0.0, 0.0))
    return vector / sqrt(sqr_length)


def clamp_shift_tc(tc, min_tc, max_tc, u_shift, v_shift, flip_v):
    u = min(max(tc[0], min_tc), max_tc) + u_shift
    v = min(max(tc[1], min_tc), max_tc) + v_shift
    if flip_v:
        return (u, 1.0-v)
    return (u, v)


def unwrap_vert_map(vert_id, vertmap_size, current_id):
    id = int(current_id/3.0)
    even = id % 2 == 0
    id += int(id / 2)
    current_x = id % (vertmap_size[0] - 1)
    current_y = 2 * int(id / (vertmap_size[0] - 1))

    eps_u = 0.05
    if even:
        eps_small = 0.45
        eps_big = 1.55
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
        eps_small = 0.55
        eps_big = 1.55
        current_x += 1
        if vert_id == 0:
            return ((current_x - eps_small - eps_u) / vertmap_size[0],
                    (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 1:
            return ((current_x + eps_small + eps_u) / vertmap_size[0],
                    (current_y + eps_big) / vertmap_size[1])
        elif vert_id == 2:
            return ((current_x + eps_small + eps_u) / vertmap_size[0],
                    (current_y + 0.45) / vertmap_size[1])
        # special case for patch surfaces
        elif vert_id == 3:
            return ((current_x - eps_small - eps_u) / vertmap_size[0],
                    (current_y + 0.45) / vertmap_size[1])
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
    y = int(lightmap_id/num_columns) * scale_value[1]

    packed_tc = (tc[0]*scale_value[0] + x, tc[1]*scale_value[1]+y)
    return packed_tc


def get_lm_id(tc, lightmap_size, packed_lm_size):
    row = tc[0]*packed_lm_size[0]
    column = tc[1]*packed_lm_size[1]
    quadrant_x = int(row/lightmap_size[0])
    quadrant_y = int(column/lightmap_size[1])

    scale = packed_lm_size[0] / lightmap_size[0]
    return int(quadrant_x + (scale * quadrant_y))


def unpack_lm_tc(tc, lightmap_size, packed_lm_size):
    row = tc[0]*packed_lm_size[0]
    column = tc[1]*packed_lm_size[1]
    quadrant_x = int(row/lightmap_size[0])
    quadrant_y = int(column/lightmap_size[1])

    scale = (packed_lm_size[0] / lightmap_size[0],
             packed_lm_size[1] / lightmap_size[1])
    lightmap_id = int(quadrant_x + (scale[0] * quadrant_y))

    quadrant_scale = [lightmap_size[0] / packed_lm_size[0],
                      lightmap_size[1] / packed_lm_size[1]]

    tc[0] = (tc[0] - (quadrant_x * quadrant_scale[0])) * scale[0]
    tc[1] = (tc[1] - (quadrant_y * quadrant_scale[1])) * scale[1]
    return lightmap_id
