from numpy import array, linalg, cross, dot
from math import sqrt, acos, pi
from itertools import combinations


def length(vec):
    sqr_length = (
        vec[0]*vec[0] +
        vec[1]*vec[1] +
        vec[2]*vec[2]
    )
    length = sqrt(sqr_length)
    return length


def v3_mul(vec, scalar):
    return (vec[0]*scalar,
            vec[1]*scalar,
            vec[2]*scalar)


def normalize(vec):
    sqr_length = (
        vec[0]*vec[0] +
        vec[1]*vec[1] +
        vec[2]*vec[2]
    )
    length = sqrt(sqr_length)
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (
        vec[0]/length,
        vec[1]/length,
        vec[2]/length
        )


class Plane():
    distance: float = 0.0
    normal: tuple[float, float, float] = (0.0, 0.0, 0.0)
    material_id: int = -1

    def __init__(self, distance, normal, material_id):
        self.distance = distance
        self.normal = normal
        self.material_id = material_id


def p3_intersect(plane_one: Plane, plane_two: Plane, plane_three: Plane):
    M = array((plane_one.normal, plane_two.normal, plane_three.normal))
    X = array((plane_one.distance, plane_two.distance, plane_three.distance))
    try:
        return tuple(linalg.solve(M, X))
    except(Exception):
        return None


def parse_brush(planes, uv_data):
    final_points = []
    faces = []
    test_planes = [(*cull_plane.normal, -cull_plane.distance)
                   for cull_plane in planes]

    # find all possible vertices
    all_points = set()
    for combination in combinations(planes, 3):
        point = p3_intersect(*combination)
        if point:
            all_points.add(point)

    # cull vertices that are outside the brush
    for plane in test_planes:
        cull_points = [p for p in all_points
                       if dot(plane, (*p, 1.0)) > 0.00001]
        for point in cull_points:
            all_points.remove(point)

    for plane in test_planes:
        # select points on plane
        cull_points = [p for p in all_points
                       if abs(dot(plane, (*p, 1.0))) > 0.00001]
        culled_points = all_points.copy()
        for point in cull_points:
            culled_points.remove(point)

        # check if valid face
        if len(culled_points) < 3:
            continue

        # create face for the plane
        face = []
        mid_point = [0.0, 0.0, 0.0]
        for point in culled_points:
            mid_point[0] += point[0]
            mid_point[1] += point[1]
            mid_point[2] += point[2]
        mid_point[0] /= len(culled_points)
        mid_point[1] /= len(culled_points)
        mid_point[2] /= len(culled_points)

        first_point = next(iter(culled_points))
        test_vec = [0.0, 0.0, 0.0]
        test_vec[0] = first_point[0] - mid_point[0]
        test_vec[1] = first_point[1] - mid_point[1]
        test_vec[2] = first_point[2] - mid_point[2]
        test_vec = normalize(test_vec)

        cross_vec = cross(plane[:-1], test_vec)

        angles = [acos(1)]
        for point in list(culled_points)[1:]:
            vec = [0.0, 0.0, 0.0]
            vec[0] = point[0] - mid_point[0]
            vec[1] = point[1] - mid_point[1]
            vec[2] = point[2] - mid_point[2]
            vec = normalize(vec)
            dot_product = min(max(dot(test_vec, vec), -1.0), 1.0)
            if (dot(vec, cross_vec) < 0):
                angles.append(pi + (pi - acos(dot_product)))
            else:
                angles.append(acos(dot_product))
        sorted_points = sorted(zip(culled_points, angles), key=lambda x: x[1])

        for point_angle in sorted_points:
            point = point_angle[0]
            if point not in final_points:
                final_points.append(tuple(point))
            face.append(final_points.index(point))
        faces.append(face)

    return final_points, faces
