import bpy

class Vertex_map:
    def __init__(self, object_id, mesh, vertex_id, loop_id):
        self.mesh = mesh
        self.obj_id = object_id
        self.vert = vertex_id
        self.loop = loop_id
        self.position = mesh.vertices[vertex_id].co.copy().freeze()
        self.normal = mesh.vertices[vertex_id].normal.copy().freeze()
        if mesh.has_custom_normals:
            self.normal = mesh.loops[loop_id].normal.copy().freeze()
        self.tc = mesh.uv_layers.active.data[loop_id].uv.copy().freeze()
        self.hash_tuple = tuple((*self.position, *self.normal, *self.tc))

    def set_mesh(self, mesh):
        self.mesh = mesh


class Surface_descriptor:
    def __init__(self, material, obj_name):
        self.current_index = 0
        self.vertex_mapping = []
        self.vertex_hashes = {}
        self.triangles = []
        self.material = material
        self.obj_name = obj_name

    # always make sure that you pack the same material in
    # one surface descriptor!
    def add_triangle(self, in_obj_id, in_mesh, in_triangle, SHADER_MAX_VERTEXES=1000):
        if len(self.triangles) * 3 >= 6 * SHADER_MAX_VERTEXES:
            return False

        new_triangle = [None, None, None]
        new_map = None

        reused_vertices = 0
        vertices = []
        for index, (tri, loo) in enumerate(zip(in_triangle.vertices,
                                               in_triangle.loops)):
            vert_map = Vertex_map(in_obj_id, in_mesh, tri, loo)
            vertices.append(vert_map)
            if vert_map.hash_tuple not in self.vertex_hashes:
                continue
            # vertex already in the surface
            if new_triangle[index] is None:
                new_triangle[index] = self.vertex_hashes[vert_map.hash_tuple]
                reused_vertices += 1

        if 3-reused_vertices + len(self.vertex_mapping) >= SHADER_MAX_VERTEXES:
            return False

        # add new vertices
        for id, index in enumerate(new_triangle):
            if index is None:
                new_map = vertices[id]
                self.vertex_mapping.append(new_map)
                self.vertex_hashes[new_map.hash_tuple] = self.current_index
                new_triangle[id] = self.current_index
                self.current_index += 1

        # add new triangle
        self.triangles.append(new_triangle)
        return True


class Surface_factory:
    valid = False
    status = "Unknown Error"

    def __init__(self, 
         objects,
         individual,
         material_merge=True,
         SHADER_MAX_VERTEXES=1000,
         MAX_SURFACES=32,
         surfaces_per_object=False):
        self.individual = individual
        surfaces = {}
        self.surface_descriptors = []
        self.num_surfaces = 0
        self.objects = objects
        # create a list for every material
        for obj in objects:
            if material_merge:
                if len(obj.data.materials) == 0:
                    surfaces["NoShader"] = [
                        Surface_descriptor("NoShader", obj.name)]
                for mat in obj.data.materials:
                    mat_name = mat.name.split(".")[0]
                    if mat_name not in surfaces:
                        surfaces[mat_name] = [
                            Surface_descriptor(mat_name, obj.name)]
                        self.num_surfaces += 1
            else:
                if len(obj.data.materials) == 0:
                    mat_name = "NoShader"
                else:
                    mat_name = obj.data.materials[0].name.split(".")[0]
                surfaces[obj.name] = [Surface_descriptor(mat_name, obj.name)]
                self.num_surfaces += 1

        for obj_id, obj in enumerate(objects):
            mesh = obj.to_mesh()
            if not self.individual:
                mesh.transform(obj.matrix_world)

            if bpy.app.version < (4, 1, 0):
                mesh.calc_normals_split()

            mesh.calc_loop_triangles()

            for triangle in mesh.loop_triangles:
                if material_merge:
                    if len(mesh.materials) == 0:
                        mat = "NoShader"
                    else:
                        mat = mesh.materials[triangle.material_index].name
                        mat = mat.split(".")[0]

                    if mat in surfaces:
                        surface_descr = surfaces[mat][len(surfaces[mat])-1]

                        if surfaces_per_object and surface_descr.obj_name != obj.name:
                            succeeded = False
                        else:
                            succeeded = surface_descr.add_triangle(
                                obj_id,
                                mesh,
                                triangle,
                                SHADER_MAX_VERTEXES)

                        if succeeded:
                            continue
                        new_surface_descr = Surface_descriptor(
                            mat, obj.name)
                        new_surface_descr.add_triangle(
                            obj_id,
                            mesh,
                            triangle,
                            SHADER_MAX_VERTEXES)
                        surfaces[mat].append(new_surface_descr)
                        self.num_surfaces += 1
                        if MAX_SURFACES > 0 and self.num_surfaces > MAX_SURFACES:
                            self.valid = False
                            self.status = "Exported object(s) exceed "
                            "max surfaces. Reduce model complexity."
                            return
                        self.status = (
                            self.status + "Added additional surface for " +
                            mat + " because there were too many "
                            "vertices or triangles\n")
                else:
                    surface_descr = surfaces[obj.name][len(
                        surfaces[obj.name])-1]
                    succeeded = surface_descr.add_triangle(
                        obj_id,
                        mesh,
                        triangle,
                        SHADER_MAX_VERTEXES)
                    # TODO: Split model, add numeric suffix to model names
                    if not succeeded:
                        self.valid = False
                        self.status = (
                            "Object exceeds vertex or indices limit: " +
                            obj.name)
                        return

        for mat in surfaces:
            for i in range(len(surfaces[mat])):
                # skip empty surfaces
                if surfaces[mat][i].current_index == 0:
                    self.num_surfaces -= 1
                    continue
                self.surface_descriptors.append(surfaces[mat][i])

        self.valid = True
        self.status = "Added object(s) successfully to surface factory."
        return

    def clear_meshes(self):
        for obj in self.objects:
            obj.to_mesh_clear()

    def update_meshes(self):
        meshes = []
        for obj in self.objects:
            mesh = obj.to_mesh()
            if not self.individual:
                mesh.transform(obj.matrix_world)

            if bpy.app.version < (4, 1, 0):
                mesh.calc_normals_split()

            meshes.append(mesh)
        for surface_descriptor in self.surface_descriptors:
            for map in surface_descriptor.vertex_mapping:
                map.set_mesh(meshes[map.obj_id])