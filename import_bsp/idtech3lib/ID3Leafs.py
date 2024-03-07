from .ID3Brushes import *
import bpy

class plane():
    def __init__(self, normal, distance):
        self.normal = normal
        self.distance = distance

    def invert(self):
        normal = (
            -self.normal[0],
            -self.normal[1],
            -self.normal[2])
        return plane(normal, -self.distance)

def parse_brush(planes):
    final_points = []
    faces = []
    final_planes = []
    test_planes = [(*cull_plane.normal, -cull_plane.distance)
                   for cull_plane in planes]

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

    for plane, actual_plane in zip(test_planes, planes):
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

        face_indices = []
        for point_angle in sorted_points:
            point = point_angle[0]
            final_points.append(point)
            face_indices.append(final_points.index(point))

        faces.append(face_indices)
        final_planes.append(actual_plane)

    return final_points, faces, final_planes

class node():
    def __init__(self, plane, children):
        self.plane = plane
        self.children = children
        self.parent = None

def build_leaf(leaf, planes, name):
    positions, faces, new_planes = parse_brush(planes)
    mesh = bpy.data.meshes.new("Leaf_" + str(name))
    mesh.from_pydata(
        positions,
        [],
        faces)
    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def build_nodes(node, planes, name, static_planes, static_nodes, static_leafs):
    positions, faces, new_planes = parse_brush(planes)
    mesh = bpy.data.meshes.new("Node_" + str(name))
    mesh.from_pydata(
        positions,
        [],
        faces)
    obj = bpy.data.objects.new(mesh.name, mesh)
    obj.display_type = 'WIRE'
    bpy.context.collection.objects.link(obj)

    split_plane = static_planes[node.plane]

    if node.children[0] >= 0:
        left_node = static_nodes[node.children[0]]
        left_planes = new_planes.copy()
        left_planes.append(split_plane.invert())
        left = build_nodes(
            left_node,
            left_planes,
            node.children[0],
            static_planes,
            static_nodes,
            static_leafs)
        left.parent = obj
    else:
        leaf_index = -node.children[0] - 1
        left_leaf = static_leafs[leaf_index]
        left_planes = new_planes.copy()
        left_planes.append(split_plane.invert())
        left = build_leaf(
            left_leaf,
            left_planes,
            leaf_index)
        left.parent = obj
        left["classname"] = "info_notnull"
        left["cluster"] = left_leaf.cluster
        if left_leaf.cluster == -1:
            left.display_type = 'WIRE'
        left["area"] = left_leaf.area
        left["mins"] = left_leaf.mins
        left["maxs"] = left_leaf.maxs

    if node.children[1] >= 0:
        right_node = static_nodes[node.children[1]]
        right_planes = new_planes.copy()
        right_planes.append(split_plane)
        right = build_nodes(
            right_node,
            right_planes,
            node.children[1],
            static_planes,
            static_nodes,
            static_leafs)
        right.parent = obj
    else:
        leaf_index = -node.children[1] - 1
        right_leaf = static_leafs[leaf_index]
        right_planes = new_planes.copy()
        right_planes.append(split_plane)
        right = build_leaf(
            right_leaf,
            right_planes,
            leaf_index)
        right.parent = obj
        right["classname"] = "info_notnull"
        right["cluster"] = right_leaf.cluster
        if right_leaf.cluster == -1:
            right.display_type = 'WIRE'
        right["area"] = right_leaf.area
        right["mins"] = right_leaf.mins
        right["maxs"] = right_leaf.maxs
        
    return obj

def build_tree(bsp):

    world_model = bsp.lumps["models"][0]
    world_mins = world_model.mins
    world_maxs = world_model.maxs

    brush = [
        plane((-1.0, 0.0, 0.0), -world_mins[0]),
        plane((1.0, 0.0, 0.0), world_maxs[0]),
        plane((0.0, -1.0, 0.0), -world_mins[1]),
        plane((0.0, 1.0, 0.0), world_maxs[1]),
        plane((0.0, 0.0, -1.0), -world_mins[2]),
        plane((0.0, 0.0, 1.0), world_maxs[2])]
    
    planes = [plane(p.normal, p.distance) for p in bsp.lumps["planes"]]
    
    build_nodes(
        bsp.lumps["nodes"][0],
        brush,
        "root",
        planes,
        bsp.lumps["nodes"],
        bsp.lumps["leafs"]
    )
