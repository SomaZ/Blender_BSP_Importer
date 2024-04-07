from numpy import (cross,
                   dot,
                   deg2rad,
                   sqrt,
                   array,
                   pi,
                   arccos,
                   linalg,
                   sin,
                   cos,
                   round_)
from itertools import combinations
from dataclasses import field


QUAKE_BASE_AXIS = {
    (0.0, 0.0, 1.0): (0, 1),
    (1.0, 0.0, 0.0): (1, 2),
    (0.0, 1.0, 0.0): (0, 2),
}


def normalize(vector):
    sqr_length = dot(vector, vector)
    if sqr_length == 0.0:
        return array((0.0, 0.0, 0.0))
    return vector / sqrt(sqr_length)


class Plane():
    normal: list = field(default_factory=list)
    distance: float = 0.0
    material: str = "NoShader_wtf"
    tex_info: dict = {}

    @staticmethod
    def direction_from_points(point1, point2, point3):
        vec1 = [point3[0] - point1[0],
                point3[1] - point1[1],
                point3[2] - point1[2]]
        vec2 = [point2[0] - point1[0],
                point2[1] - point1[1],
                point2[2] - point1[2]]
        normal = cross(vec1, vec2)
        distance = dot(normal, point3)
        return normal, distance

    @staticmethod
    def parse_material(material):
        return "textures/" + material

    def parse_quake_tex_info(self,
                             shift_x,
                             shift_y,
                             rotation,
                             scale_x,
                             scale_y):

        normal = normalize(array(self.normal))
        if scale_x == 0.0:
            scale_x = 1.0
        if scale_y == 0.0:
            scale_y = 1.0

        best = 0.0
        best_axis = None
        for axis in QUAKE_BASE_AXIS:
            dot_v = abs(dot(normal, axis))
            if (dot_v > (best + 0.0000001)):
                best = dot_v
                best_axis = QUAKE_BASE_AXIS[axis]

        sin_v = sin(deg2rad(rotation))
        cos_v = cos(deg2rad(rotation))
        if abs(sin_v) <= 1.8369701987210297e-16:
            sin_v = 0.0
        if abs(cos_v) <= 1.8369701987210297e-16:
            cos_v = 0.0

        rotation_matrix = array(((cos_v, -sin_v), (sin_v, cos_v)))

        rotated_2d_vec_x = (rotation_matrix @ array((1.0, 0.0))) / scale_x
        rotated_2d_vec_y = (rotation_matrix @ array((0.0, -1.0))) / scale_y

        quake_vec_x = [0.0, 0.0, 0.0, shift_x]
        quake_vec_x[best_axis[0]] = rotated_2d_vec_x[0]
        quake_vec_x[best_axis[1]] = rotated_2d_vec_x[1]

        quake_vec_y = [0.0, 0.0, 0.0, shift_y]
        quake_vec_y[best_axis[0]] = rotated_2d_vec_y[0]
        quake_vec_y[best_axis[1]] = rotated_2d_vec_y[1]

        self.tex_info["vecs"] = (quake_vec_x, quake_vec_y)

    def __init__(self,
                 normal=(0.0, 0.0, 1.0),
                 distance=0.0,
                 material="NoShader_wtf2",
                 tex_info=([0.0]*5)):
        self.normal = normal
        self.distance = distance
        self.material = material
        self.tex_info = {}
        self.tex_info["vecs"] = None
        self.parse_quake_tex_info(*tex_info)

    @classmethod
    def from_quake_map_def(cls, array):
        if len(array) != 4:
            raise Exception("False data to parse plane")

        data = array[3].split()
        if len(data) != 9:
            raise Exception("Non quake brush format definition found")

        points = (array[0], array[1], array[2])
        normal, distance = cls.direction_from_points(*points)
        material = cls.parse_material(data[0])
        shift_x = float(data[1])
        shift_y = float(data[2])
        rotation = float(data[3])
        scale_x = float(data[4])
        scale_y = float(data[5])
        tex_info = (shift_x,
                    shift_y,
                    rotation,
                    scale_x,
                    scale_y)
        return cls(normal, distance, material, tex_info)


def p3_intersect(plane_one: Plane, plane_two: Plane, plane_three: Plane):
    M = array((plane_one.normal, plane_two.normal, plane_three.normal))
    X = array((plane_one.distance, plane_two.distance, plane_three.distance))
    try:
        return tuple(linalg.solve(M, X))
    except(Exception):
        return None


def parse_brush(planes, material_sizes=None):
    final_points = []
    final_uvs = []
    faces = []
    materials = []
    test_planes = [(*cull_plane.normal, -cull_plane.distance)
                   for cull_plane in planes]
    test_uvs = [(plane.material.lower(), plane.tex_info)
                for plane in planes]

    # find all possible vertices
    all_points = set()
    for combination in combinations(planes, 3):
        point = p3_intersect(*combination)
        if point is not None:
            all_points.add(point)

    # cull vertices that are outside the brush
    for plane in test_planes:
        all_points = [p for p in all_points.copy()
                      if dot(plane, (*p, 1.0)) <= 0.00001]

    for plane, uv_data in zip(test_planes, test_uvs):
        # select points on plane
        culled_points = [p for p in all_points.copy()
                         if abs(dot(plane, (*p, 1.0))) <= 0.00001]

        culled_points_set = set()
        for point in culled_points:
            culled_points_set.add(point)

        # check if valid face
        if len(culled_points_set) < 3:
            continue

        # create face for the plane
        mid_point = array((0.0, 0.0, 0.0))
        for point in culled_points:
            mid_point += point
        mid_point /= len(culled_points)

        first_point = next(iter(culled_points))
        test_vec = first_point - mid_point
        test_vec = normalize(test_vec)

        cross_vec = cross(plane[:-1], test_vec)

        angles = [arccos(1)]
        for point in list(culled_points)[1:]:
            vec = point - mid_point
            vec = normalize(vec)
            dot_product = min(max(dot(test_vec, vec), -1.0), 1.0)
            if (dot(vec, cross_vec) < 0):
                angles.append(pi + (pi - arccos(dot_product)))
            else:
                angles.append(arccos(dot_product))
        sorted_points = sorted(zip(culled_points, angles), key=lambda x: x[1])

        if material_sizes is not None and uv_data[0] in material_sizes:
            mat_size = material_sizes[uv_data[0]]
        else:
            mat_size = 128.0, 128.0

        face_indices = []
        for point_angle in sorted_points:
            point = point_angle[0]
            final_points.append(point)

            uv = [0.0, 0.0]
            if "vecs" in uv_data[1]:
                uv[0] = dot(point, uv_data[1]["vecs"][0][:-1])
                uv[1] = dot(point, uv_data[1]["vecs"][1][:-1])
                uv[0] += uv_data[1]["vecs"][0][3]
                uv[1] += uv_data[1]["vecs"][1][3]

                uv[0] /= mat_size[0]
                uv[1] /= mat_size[1]

            final_uvs.append((uv[0], 1.0 - uv[1]))
            face_indices.append(final_points.index(point))

        materials.append(uv_data[0])
        faces.append(face_indices)

    return final_points, final_uvs, faces, materials
