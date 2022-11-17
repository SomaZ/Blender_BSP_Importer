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

import importlib
import os

import cProfile

if "bpy" not in locals():
    import bpy

from .idtech3lib.BSP import BSP_READER as BSP
from .idtech3lib import MAP
from .idtech3lib.ID3VFS import Q3VFS
from .idtech3lib import GamePacks
from math import floor, atan, radians
from numpy import dot, sqrt

if "Entities" in locals():
    importlib.reload(Entities)
else:
    from . import Entities

if "QuakeShader" in locals():
    importlib.reload(QuakeShader)
else:
    from . import QuakeShader

if "MD3" in locals():
    importlib.reload(MD3)
else:
    from . import MD3

if "TAN" in locals():
    importlib.reload(TAN)
else:
    from . import TAN

if "QuakeLight" in locals():
    importlib.reload(QuakeLight)
else:
    from . import QuakeLight


def create_meshes_from_models(models):
    return_meshes = {}
    for model in models:
        name = model.name
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(
            model.positions.get_indexed(),
            [],
            model.indices)
        for texture_instance in model.material_names:
            mat = bpy.data.materials.get(texture_instance)
            if (mat is None):
                mat = bpy.data.materials.new(name=texture_instance)
            mesh.materials.append(mat)
        mesh.polygons.foreach_set("material_index", model.material_id)

        for poly, smooth in zip(mesh.polygons, model.face_smooth):
            poly.use_smooth = smooth

        unindexed_normals = model.vertex_normals.get_unindexed()
        if len(unindexed_normals) > 0:
            mesh.normals_split_custom_set(unindexed_normals)

        for uv_layer in model.uv_layers:
            uvs = []
            if uv_layer.startswith("Lightmap"):
                for uv in model.uv_layers[uv_layer].get_unindexed(tuple):
                    uvs.append(uv[0])
                    uvs.append(uv[1])
            else:
                for uv in model.uv_layers[uv_layer].get_unindexed(tuple):
                    uvs.append(uv[0])
                    uvs.append(1.0 - uv[1])
            mesh.uv_layers.new(do_init=False, name=uv_layer)
            mesh.uv_layers[uv_layer].data.foreach_set(
                "uv", uvs)
        for vert_color in model.vertex_colors:
            colors = []
            for color in model.vertex_colors[vert_color].get_unindexed():
                colors.append(color[0] / 255.0)
                colors.append(color[1] / 255.0)
                colors.append(color[2] / 255.0)
                colors.append(color[3] / 255.0)
            mesh.vertex_colors.new(name=vert_color)
            mesh.vertex_colors[vert_color].data.foreach_set(
                "color", colors)
        if bpy.app.version >= (2, 92, 0):
            for vert_att in model.vertex_data_layers:
                mesh.attributes.new(name=vert_att,
                                    type='INT',
                                    domain='POINT')
                mesh.attributes[vert_att].data.foreach_set(
                    "value",
                    model.vertex_data_layers[vert_att].get_indexed(int))
        elif bpy.app.version >= (2, 91, 0):
            for vert_att in model.vertex_data_layers:
                mesh.attributes.new(name=vert_att,
                                    type='INT', domain='VERTEX')
                mesh.attributes[vert_att].data.foreach_set(
                        "value",
                        model.vertex_data_layers[vert_att].get_indexed(
                            int))
        else:
            for vert_att in model.vertex_data_layers:
                mesh.vertex_layers_int.new(name=vert_att)
                mesh.vertex_layers_int[vert_att].data.foreach_set(
                    "value",
                    model.vertex_data_layers[vert_att].get_indexed(int))
        mesh.use_auto_smooth = True
        mesh.update()
        mesh.validate()
        if name in return_meshes:
            print("Double mesh name found! Mesh did not get added: " + name)
            continue
        return_meshes[name] = mesh
    return return_meshes


def load_mesh(VFS, mesh_name, zoffset, bsp):
    blender_mesh = None
    if mesh_name.endswith(".md3"):
        blender_mesh = MD3.ImportMD3(
            VFS,
            mesh_name,
            zoffset)[0]
    elif mesh_name.endswith(".tik"):
        blender_mesh = TAN.ImportTIK(
            VFS,
            mesh_name,
            zoffset)[0]
    elif mesh_name.startswith("*") and bsp is not None:
        model_id = None
        try:
            model_id = int(mesh_name[1:])
            new_blender_mesh = create_meshes_from_models([
                bsp.get_bsp_model(model_id)])
            blender_mesh = next(iter(new_blender_mesh.values()))
        except Exception:
            print("Could not get model for mesh ", mesh_name)
            return None
    elif mesh_name == "box":
        blender_mesh = bpy.data.meshes.get("box")
        if blender_mesh is None:
            ent_object = bpy.ops.mesh.primitive_cube_add(
                                size=8.0, location=([0, 0, 0]))
            ent_object = bpy.context.object
            ent_object.name = "box"
            blender_mesh = ent_object.data
            blender_mesh.name = "box"
            bpy.data.objects.remove(ent_object, do_unlink=True)

    return blender_mesh


def set_custom_properties(import_settings, blender_obj, bsp_obj):
    # needed for custom descriptions and data types
    rna_ui = blender_obj.get('_RNA_UI')
    if rna_ui is None:
        blender_obj['_RNA_UI'] = {}
        rna_ui = blender_obj['_RNA_UI']

    class_dict_keys = {}
    classname = bsp_obj.custom_parameters.get("classname")
    if classname in import_settings.entity_dict:
        class_dict_keys = import_settings.entity_dict[classname]["Keys"]

    for property in bsp_obj.custom_parameters:
        blender_obj[property] = bsp_obj.custom_parameters[property]

        if property not in class_dict_keys:
            continue
        property_dict = class_dict_keys[property]
        descr_dict = {}
        if "Description" in property_dict:
            descr_dict["description"] = property_dict["Description"]
        if "Type" in property_dict:
            key_type = property_dict["Type"]
            if key_type in GamePacks.TYPE_MATCHING:
                descr_dict["subtype"] = GamePacks.TYPE_MATCHING[key_type]
        rna_ui[property] = descr_dict

    spawnflag = bsp_obj.spawnflags
    if spawnflag % 2 == 1:
        blender_obj.q3_dynamic_props.b1 = True
    if spawnflag & 2 > 1:
        blender_obj.q3_dynamic_props.b2 = True
    if spawnflag & 4 > 1:
        blender_obj.q3_dynamic_props.b4 = True
    if spawnflag & 8 > 1:
        blender_obj.q3_dynamic_props.b8 = True
    if spawnflag & 16 > 1:
        blender_obj.q3_dynamic_props.b16 = True
    if spawnflag & 32 > 1:
        blender_obj.q3_dynamic_props.b32 = True
    if spawnflag & 64 > 1:
        blender_obj.q3_dynamic_props.b64 = True
    if spawnflag & 128 > 1:
        blender_obj.q3_dynamic_props.b128 = True
    if spawnflag & 256 > 1:
        blender_obj.q3_dynamic_props.b256 = True
    if spawnflag & 512 > 1:
        blender_obj.q3_dynamic_props.b512 = True

    # TODO: really needed? need to check that
    blender_obj.q3_dynamic_props.model = bsp_obj.mesh_name
    blender_obj.q3_dynamic_props.model2 = bsp_obj.model2


def create_blender_light(import_settings, bsp_object, objects):
    intensity = 300.0
    color = [1.0, 1.0, 1.0]
    vector = [0.0, 0.0, -1.0]
    angle = 3.141592/2.0
    properties = bsp_object.custom_parameters
    if "light" in properties:
        intensity = float(properties["light"])
    if "_color" in properties:
        color = properties["_color"]
    if "target" in properties:
        if properties["target"] in objects:
            target_origin = objects[properties["target"]].position
            vector = bsp_object.position - target_origin
            sqr_length = dot(vector, vector)
            radius = 64.0
            if "radius" in properties:
                radius = float(properties["radius"])
            angle = 2*(atan(radius/sqrt(sqr_length)))
        if "_sun" in properties and properties["_sun"] == 1:
            light = QuakeLight.add_light(
                bsp_object.name,
                "SUN",
                intensity,
                color,
                vector,
                radians(1.5))
        else:
            light = QuakeLight.add_light(
                bsp_object.name,
                "SPOT",
                intensity,
                color,
                vector,
                angle)
    else:
        light = QuakeLight.add_light(
            bsp_object.name,
            "POINT",
            intensity,
            color,
            vector,
            angle)
    light.location = bsp_object.position


def create_blender_objects(VFS, import_settings, objects, meshes, bsp):
    if len(objects) <= 0:
        return None
    object_list = []
    for obj_name in objects:
        obj = objects[obj_name]
        if obj.mesh_name is None:
            classname = obj.custom_parameters.get("classname")
            if (classname is not None and
               classname == "light"):
                create_blender_light(import_settings, obj, objects)
                continue
            else:
                class_dict = {}
                if classname in import_settings.entity_dict:
                    class_dict = import_settings.entity_dict[classname]
                obj.mesh_name = "box"
                if "Model" in class_dict:
                    obj.mesh_name = class_dict["Model"]

        mesh_z_name = obj.mesh_name
        if obj.zoffset != 0:
            mesh_z_name = mesh_z_name + ".{}".format(obj.zoffset)

        if meshes is None:
            print("Didnt add object: " + str(obj.name))
            continue

        if mesh_z_name not in meshes:
            blender_mesh = load_mesh(VFS, obj.mesh_name, obj.zoffset, bsp)
            if blender_mesh is not None:
                blender_mesh.name = mesh_z_name
                meshes[mesh_z_name] = blender_mesh
        else:
            blender_mesh = meshes[mesh_z_name]

        if blender_mesh is None:
            print("Didnt find mesh in meshes: " +
                  str(obj.mesh_name) +
                  " in object " +
                  str(obj.name))
            continue

        blender_obj = bpy.data.objects.new(obj.name, blender_mesh)
        blender_obj.location = obj.position

        if not blender_mesh.name.startswith("*"):
            blender_obj.rotation_euler = obj.rotation
            blender_obj.scale = obj.scale

        bpy.context.collection.objects.link(blender_obj)
        object_list.append(blender_obj)

        set_custom_properties(import_settings, blender_obj, obj)
    return object_list


def get_bsp_file(VFS, import_settings):
    return BSP(VFS, import_settings)


def import_bsp_file(import_settings):

    # initialize virtual file system
    VFS = Q3VFS()
    for base_path in import_settings.base_paths:
        VFS.add_base(base_path)
    VFS.build_index()

    # read bsp data
    bsp_file = BSP(VFS, import_settings)

    # prepare for packing internal lightmaps
    bsp_file.lightmap_size = bsp_file.compute_packed_lightmap_size()

    # profiler = cProfile.Profile()
    # profiler.enable()
    # bsp_models = bsp_file.get_bsp_models()
    # profiler.disable()
    # profiler.print_stats()

    # convert bsp data to blender data
    # blender_meshes = create_meshes_from_models(bsp_models)

    # create blender objects
    blender_objects = []
    bsp_objects = None
    BRUSH_IMPORTS = ["BRUSHES", "SHADOW_BRUSHES"]
    if import_settings.preset in BRUSH_IMPORTS:
        bsp_models = bsp_file.get_bsp_models()
        blender_meshes = create_meshes_from_models(bsp_models)
        for mesh_name in blender_meshes:
            mesh = blender_meshes[mesh_name]
            if mesh is None:
                mesh = bpy.data.meshes.new(mesh_name)
            ob = bpy.data.objects.new(
                    name=mesh_name,
                    object_data=mesh)
            blender_objects.append(ob)
            bpy.context.collection.objects.link(ob)
    else:
        bsp_objects = Entities.ImportEntities(VFS, import_settings, bsp_file)
        blender_objects = create_blender_objects(
            VFS,
            import_settings,
            bsp_objects,
            {},  # blender_meshes,
            bsp_file)

    # get clip data and gridsize
    clip_end = 40000
    if bsp_objects is not None and "worldspawn" in bsp_objects:
        worldspawn_object = bsp_objects["worldspawn"]
        custom_parameters = worldspawn_object.custom_parameters

        if ("distancecull" in custom_parameters and
           import_settings.preset == "PREVIEW"):
            clip_end = float(custom_parameters["distancecull"])
        if "gridsize" in custom_parameters:
            grid_size = custom_parameters["gridsize"]
            bsp_file.lightgrid_size = grid_size
            bsp_file.lightgrid_inverse_size = [1.0 / float(grid_size[0]),
                                               1.0 / float(grid_size[1]),
                                               1.0 / float(grid_size[2])]
    # apply clip data
    for a in bpy.context.screen.areas:
        if a.type == 'VIEW_3D':
            for s in a.spaces:
                if s.type == 'VIEW_3D':
                    s.clip_start = 4
                    s.clip_end = clip_end

    bsp_images = bsp_file.get_bsp_images()
    for image in bsp_images:
        new_image = bpy.data.images.new(
            image.name,
            width=image.width,
            height=image.height,
            alpha=image.num_components == 4)
        new_image.pixels = image.get_rgba()
        new_image.alpha_mode = 'CHANNEL_PACKED'

    # handle external lightmaps
    if bsp_file.num_internal_lm_ids >= 0 and bsp_file.external_lm_files:
        tmp_folder = bpy.app.tempdir.replace("\\", "/")
        external_lm_lump = []
        width, height = None, None
        for file_name in bsp_file.external_lm_files:
            os.makedirs(tmp_folder + os.path.dirname(file_name), exist_ok=True)
            f = open(tmp_folder + file_name, "wb")
            try:
                f.write(VFS.get(file_name))
            except Exception:
                print("Couldn't write temp file: " + file_name)
            f.close()

            tmp_image = bpy.data.images.load(tmp_folder + file_name)
            if not width:
                width = tmp_image.size[0]
            if not height:
                height = tmp_image.size[1]

            if width != tmp_image.size[0] or height != tmp_image.size[1]:
                print("External lightmaps all need to be the same size")
                break

            external_lm_lump.append(list(tmp_image.pixels[:]))

        # compute new sized atlas
        num_colums = (bsp_file.lightmap_size[0] //
                      bsp_file.internal_lightmap_size[0])
        num_rows = (bsp_file.lightmap_size[1] //
                    bsp_file.internal_lightmap_size[1])
        bsp_file.internal_lightmap_size = (width, height)
        bsp_file.lightmap_size = (width * num_colums, height * num_rows)

        atlas_pixels = bsp_file.pack_lightmap(
            external_lm_lump,
            bsp_file.deluxemapping,
            False,
            False,
            4)

        new_image = bpy.data.images.new(
            "$lightmap",
            width=bsp_file.lightmap_size[0],
            height=bsp_file.lightmap_size[1])
        new_image.pixels = atlas_pixels
        new_image.alpha_mode = 'CHANNEL_PACKED'

    # bpy.context.scene.id_tech_3_lightmaps_per_row = num_rows
    # bpy.context.scene.id_tech_3_lightmaps_per_column = num_columns

    QuakeShader.init_shader_system(bsp_file)
    QuakeShader.build_quake_shaders(VFS, import_settings, blender_objects)


def import_map_file(import_settings):

    # initialize virtual file system
    VFS = Q3VFS()
    for base_path in import_settings.base_paths:
        VFS.add_base(base_path)
    VFS.build_index()

    byte_array = VFS.get(import_settings.file)

    entities = MAP.read_map_file(byte_array)
    objects = create_blender_objects(
        VFS,
        import_settings,
        entities,
        {},
        None)

    QuakeShader.init_shader_system(None)
    QuakeShader.build_quake_shaders(VFS, import_settings, objects)