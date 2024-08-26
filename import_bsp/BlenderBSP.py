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

import bpy

from .idtech3lib.ID3VFS import Q3VFS
from .idtech3lib.BSP import BSP_READER as BSP
from .idtech3lib import GamePacks, MAP
from math import atan, radians
from numpy import dot, sqrt

from . import BlenderImage, QuakeShader, QuakeLight
from . import MD3, TAN

#import cProfile


def create_meshes_from_models(models):
    if models is None:
        return None
    return_meshes = {}
    for model in models:
        if model is None:
            continue
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

        if bpy.app.version < (4, 1, 0):
            mesh.use_auto_smooth = True

        for poly, smooth in zip(mesh.polygons, model.face_smooth):
            poly.use_smooth = smooth
        unindexed_normals = model.vertex_normals.get_unindexed()
        if unindexed_normals is not None and len(unindexed_normals) > 0:
            mesh.normals_split_custom_set(unindexed_normals)

        for uv_layer in model.uv_layers:
            uvs = []
            for uv in model.uv_layers[uv_layer].get_unindexed(tuple):
                uvs.append(uv[0])
                uvs.append(uv[1])
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
        
        mesh.validate()
        mesh.update()
        
        if name in return_meshes:
            print("Double mesh name found! Mesh did not get added: " + name)
            continue
        return_meshes[name] = mesh, model.vertex_groups
    if len(return_meshes) > 0:
        return return_meshes
    return None


def load_mesh(VFS, mesh_name, zoffset, bsp):
    blender_mesh = None
    vertex_groups = {}
    if mesh_name.endswith(".md3"):
        try:
            blender_mesh = MD3.ImportMD3(
                VFS,
                mesh_name,
                zoffset)[0]
        except Exception as e:
            print("Could not get model for mesh ", mesh_name, e)
            return blender_mesh, vertex_groups
    elif mesh_name.endswith(".tik"):
        try:
            blender_mesh = TAN.ImportTIK(
                VFS,
                "models/{}".format(mesh_name),
                zoffset)[0]
        except Exception as e:
            print("Could not get model for mesh ", mesh_name, e)
            return blender_mesh, vertex_groups
    elif mesh_name.startswith("*") and bsp is not None:
        model_id = None

        mesh = bpy.data.meshes.get(mesh_name)
        if mesh != None:
            mesh.name = mesh_name+"_prev.000"

        try:
            model_id = int(mesh_name[1:])
            new_blender_mesh = create_meshes_from_models([
                bsp.get_bsp_model(model_id)])
            blender_mesh, vertex_groups = next(iter(new_blender_mesh.values()))
        except Exception as e:
            print("Could not get model for mesh ", mesh_name, e)
            return blender_mesh, vertex_groups
    elif mesh_name == "box":
        blender_mesh = bpy.data.meshes.get("box")
        if blender_mesh is None:
            ent_object = bpy.ops.mesh.primitive_cube_add(
                                size=8.0, location=([0, 0, 0]))
            ent_object = bpy.context.object
            ent_object.name = "box"

            material_name = "Object Color"
            mat = bpy.data.materials.get(material_name)
            if (mat == None):
                mat = bpy.data.materials.new(name=material_name)
                mat.use_nodes = True
                node = mat.node_tree.nodes["Principled BSDF"]
                object_node = mat.node_tree.nodes.new(type="ShaderNodeObjectInfo")
                object_node.location = (node.location[0] - 400, node.location[1])
                mat.node_tree.links.new(object_node.outputs["Color"], node.inputs["Base Color"])
                if bpy.app.version >= (4, 0, 0):
                    mat.node_tree.links.new(object_node.outputs["Color"], node.inputs["Emission Color"])
                    node.inputs["Emission Strength"].default_value = 1.0
                else:
                    mat.node_tree.links.new(object_node.outputs["Color"], node.inputs["Emission"])
            ent_object.data.materials.append(mat)
            
            blender_mesh = ent_object.data
            blender_mesh.name = "box"
            bpy.data.objects.remove(ent_object, do_unlink=True)

    return blender_mesh, vertex_groups


def load_map_entity_surfaces(VFS, obj, import_settings):
    materials = []
    surfaces = obj.custom_parameters.get("surfaces")
    if surfaces is None:
        return None, None
    for surf in surfaces:
        if surf.type == "BRUSH":
            for plane in surf.planes:
                mat = plane.material
                if mat not in materials:
                    materials.append(mat)
    material_sizes = (
        QuakeShader.get_shader_image_sizes(
            VFS,
            import_settings,
            materials))
    new_blender_mesh = create_meshes_from_models([
        MAP.get_entity_brushes(obj, material_sizes, import_settings)])
    if new_blender_mesh is None:
        return None, None
    blender_mesh, vertex_groups = next(iter(new_blender_mesh.values()))
    return blender_mesh, vertex_groups


def set_custom_properties(import_settings, blender_obj, bsp_obj):
    if bpy.app.version < (3, 0, 0):
        # needed for custom descriptions and data types prior 3.0
        rna_ui = blender_obj.get('_RNA_UI')
        if rna_ui is None:
            blender_obj['_RNA_UI'] = {}
            rna_ui = blender_obj['_RNA_UI']

    class_dict_keys = {}
    class_model_forced = False
    classname = bsp_obj.custom_parameters.get("classname").lower()
    if classname in import_settings.entity_dict:
        class_dict_keys = import_settings.entity_dict[classname]["Keys"]
        if "Color" in import_settings.entity_dict[classname]:
            color_info = [*import_settings.entity_dict[classname]["Color"], 1.0]
            blender_obj.color = (
                pow(color_info[0], 2.2),
                pow(color_info[1], 2.2),
                pow(color_info[2], 2.2),
                pow(color_info[3], 2.2))
        if "Model" in import_settings.entity_dict[classname]:
            class_model_forced = import_settings.entity_dict[classname]["Model"] != "box"
        if bsp_obj.mesh_name == "box" and import_settings.entity_dict[classname]["Model"] == "box":
            maxs = import_settings.entity_dict[classname]["Maxs"]
            mins = import_settings.entity_dict[classname]["Mins"]
            blender_obj.delta_scale[0] = (maxs[0] - mins[0]) / 8.0
            if blender_obj.delta_scale[0] == 0:
                blender_obj.delta_scale[0] = 1.0
            else:
                blender_obj.delta_scale[1] = (maxs[1] - mins[1]) / 8.0
                blender_obj.delta_scale[2] = (maxs[2] - mins[2]) / 8.0
                blender_obj.delta_location[0] = (maxs[0] + mins[0]) * 0.5
                blender_obj.delta_location[1] = (maxs[1] + mins[1]) * 0.5
                blender_obj.delta_location[2] = (maxs[2] + mins[2]) * 0.5

    skip_properties = ("surfaces", "first_line")
    for property in bsp_obj.custom_parameters:
        if property in skip_properties:
            continue
        blender_obj[property] = bsp_obj.custom_parameters[property]

        if property not in class_dict_keys:
            continue
        property_dict = class_dict_keys[property]
        property_subtype = "NONE"
        property_desc = ""
        key_type = "STRING"
        if "Description" in property_dict:
            property_desc = property_dict["Description"]
        if "Type" in property_dict:
            key_type = property_dict["Type"]
            if key_type in GamePacks.TYPE_MATCHING:
                property_subtype = GamePacks.TYPE_MATCHING[key_type]
        if bpy.app.version < (3, 0, 0):
            descr_dict = {}
            descr_dict["description"] = property_desc
            if property_subtype != "NONE":
                descr_dict["subtype"] = property_subtype
            rna_ui[property] = descr_dict
        else:
            id_props = blender_obj.id_properties_ui(property)
            if id_props is None:
                continue
            if property_desc != "":
                id_props.update(description=str(property_desc))
            if property_subtype != "NONE":
                id_props.update(subtype=property_subtype)

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

    if bsp_obj.mesh_name is not None and bsp_obj.mesh_name != "box" and not class_model_forced:
        blender_obj.q3_dynamic_props.model = bsp_obj.mesh_name
        blender_obj["model"] = bsp_obj.mesh_name
    if bsp_obj.model2 != "":
        blender_obj.q3_dynamic_props.model2 = bsp_obj.model2
        blender_obj["model2"] = bsp_obj.model2


def add_light_drivers(light):

    light_data = light.data
    light_value = light.get("light")
    scale_value = light.get("scale")
    color_value = light.get("_color")

    if light_value is None and color_value is None:
        return

    if light_value is not None:
        driver = light.data.driver_add('energy')

        new_var = driver.driver.variables.get("light")
        if new_var is None:
            new_var = driver.driver.variables.new()
            new_var.name = "light"
        new_var.type = 'SINGLE_PROP'
        new_var.targets[0].id = light
        new_var.targets[0].data_path = '["light"]'
        if scale_value != None:
            new_var = driver.driver.variables.get("scale")
            if new_var is None:
                new_var = driver.driver.variables.new()
                new_var.name = "scale"
            new_var.type = 'SINGLE_PROP'
            new_var.targets[0].id = light
            new_var.targets[0].data_path = '["scale"]'

        light_type_scale = {
            "SUN" : 0.1,
            "SPOT" : 750.0,
            "POINT" : 750.0,
            "AREA" : 0.1 # should not be used by the addon
        }

        if scale_value != None:
            expression = "float(light) * float(scale) * {}"
        else:
            expression = "float(light) * {}"

        driver.driver.expression = expression.format(light_type_scale[light_data.type])

    if color_value is not None:
        driver = light.data.driver_add('color')

        new_var = driver[0].driver.variables.get("color")
        if new_var is None:
            new_var = driver[0].driver.variables.new()
            new_var.name = "color"
        new_var.type = 'SINGLE_PROP'
        new_var.targets[0].id = light
        new_var.targets[0].data_path = '["_color"]'
        driver[0].driver.expression = "color[0]"

        new_var = driver[1].driver.variables.get("color")
        if new_var is None:
            new_var = driver[1].driver.variables.new()
            new_var.name = "color"
        new_var.type = 'SINGLE_PROP'
        new_var.targets[0].id = light
        new_var.targets[0].data_path = '["_color"]'
        driver[1].driver.expression = "color[1]"

        new_var = driver[2].driver.variables.get("color")
        if new_var is None:
            new_var = driver[2].driver.variables.new()
            new_var.name = "color"
        new_var.type = 'SINGLE_PROP'
        new_var.targets[0].id = light
        new_var.targets[0].data_path = '["_color"]'
        driver[2].driver.expression = "color[2]"


def create_blender_light(import_settings, bsp_object, objects):
    intensity = 300.0
    color = [1.0, 1.0, 1.0]
    vector = [0.0, 0.0, -1.0]
    angle = 3.141592/2.0
    properties = bsp_object.custom_parameters
    if "light" in properties:
        intensity = float(properties["light"])
    if "scale" in properties:
        intensity *= float(properties["scale"])
    if "_color" in properties:
        color = properties["_color"]
    if "target" in properties:
        if properties["target"] in objects:
            target_origin = objects[properties["target"]].position
            vector = bsp_object.position - target_origin
            sqr_length = dot(vector, vector)
            if (sqr_length == 0.0):
                sqr_length = 1.0
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

    set_custom_properties(import_settings, light, bsp_object)
    # Add driver for the blender light intensity based on the entity data
    add_light_drivers(light)


def is_object_valid_for_preset(bsp_object, import_settings):
    # import every entity in editing preset
    preset = import_settings.preset
    if preset == "EDITING":
        return True

    classname = bsp_object.custom_parameters.get("classname")
    mesh_name = bsp_object.mesh_name

    if classname is not None:
        if preset == "ONLY_LIGHTS":
            return classname == "light"
        if preset == "RENDERING" and classname == "light":
            return True
        if preset == "RENDERING" and classname == "misc_model":
            return False

    class_dict = {}
    if classname in import_settings.entity_dict:
        class_dict = import_settings.entity_dict[classname]

    if "Model" in class_dict and mesh_name is None:
        mesh_name = class_dict["Model"]
    elif mesh_name is None:
        mesh_name = "box"

    if mesh_name == "box":
        return bsp_object.model2 != ""

    if classname is None:
        return False

    static_property = bsp_object.custom_parameters.get("make_static")
    if static_property is not None and preset == "RENDERING":
        return static_property == 0

    return True


def create_blender_objects(VFS, import_settings, objects, meshes, bsp):
    if len(objects) <= 0:
        return None
    object_list = []
    for obj_name in objects:
        obj = objects[obj_name]

        if not is_object_valid_for_preset(obj, import_settings):
            continue

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
        #TODO: Get rid of this stupid zoffset BS
        if mesh_z_name.endswith(".md3"):
            mesh_z_name = mesh_z_name[:-len(".md3")]
        if mesh_z_name.endswith(".tik"):
            mesh_z_name = mesh_z_name[:-len(".tik")]
        if obj.zoffset != 0:
            mesh_z_name = mesh_z_name + ".z{}".format(obj.zoffset)

        if meshes is None:
            print("Didnt add object: " + str(obj.name))
            continue

        vertex_groups = {}
        if mesh_z_name not in meshes:
            if bsp is None and obj.custom_parameters.get("surfaces") is not None:
                blender_mesh, vertex_groups = load_map_entity_surfaces(VFS, obj, import_settings)
            else:
                blender_mesh, vertex_groups = load_mesh(VFS, obj.mesh_name, obj.zoffset, bsp)
            if blender_mesh is not None:
                blender_mesh.name = mesh_z_name
                meshes[mesh_z_name] = blender_mesh
            elif obj.model2 != "":
                blender_mesh, vertex_groups = load_mesh(VFS, "box", 0, bsp)
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
            if "Tiki_Scale" in blender_mesh:
                new_scale = (blender_mesh["Tiki_Scale"], blender_mesh["Tiki_Scale"], blender_mesh["Tiki_Scale"])
                blender_obj.scale = new_scale
            else:
                blender_obj.scale = obj.scale

        bpy.context.collection.objects.link(blender_obj)
        object_list.append(blender_obj)

        for vert_group in vertex_groups:
            vg = blender_obj.vertex_groups.get(vert_group)
            if vg is None:
                vg = blender_obj.vertex_groups.new(name=vert_group)
            vg.add(list(vertex_groups[vert_group]), 1.0, 'ADD')

        set_custom_properties(import_settings, blender_obj, obj)

        if "model2" not in blender_obj:
            continue
        blender_mesh, vertex_groups = load_mesh(VFS, blender_obj["model2"], obj.zoffset, None)
        if blender_mesh is None:
            continue
        m2_obj = bpy.data.objects.new(obj.name + "_model2", blender_mesh)
        bpy.context.collection.objects.link(m2_obj)
        object_list.append(m2_obj)
        m2_obj.parent = blender_obj
        m2_obj.hide_select = True
        if blender_obj.data.name == "box":
            blender_obj.hide_render = True

    return object_list


def get_bsp_file(VFS, import_settings):
    return BSP(VFS, import_settings)


def set_blender_clip_spaces(clip_start, clip_end):
    for ws in bpy.data.workspaces:
        for screen in ws.screens:
            for a in screen.areas:
                if a.type == 'VIEW_3D':
                    for s in a.spaces:
                        if s.type == 'VIEW_3D':
                            s.clip_start = clip_start
                            s.clip_end = clip_end


def import_bsp_file(import_settings):

    print("initialize virtual file system")
    VFS = Q3VFS()
    for base_path in import_settings.base_paths:
        VFS.add_base(base_path)
    VFS.build_index()

    print("read bsp data")
    bsp_file = BSP(VFS, import_settings)

    # create blender objects
    blender_objects = []
    bsp_objects = None
    BRUSH_IMPORTS = ["BRUSHES", "SHADOW_BRUSHES"]
    if import_settings.preset in BRUSH_IMPORTS:
        bsp_models = bsp_file.get_bsp_models()
        blender_meshes = create_meshes_from_models(bsp_models)
        for mesh_name in blender_meshes:
            mesh, vertex_groups = blender_meshes[mesh_name]
            if mesh is None:
                mesh = bpy.data.meshes.new(mesh_name)
            ob = bpy.data.objects.new(
                    name=mesh_name,
                    object_data=mesh)
            for vert_group in vertex_groups:
                vg = ob.vertex_groups.get(vert_group)
                if vg is None:
                    vg = ob.vertex_groups.new(name=vert_group)
                vg.add(list(vertex_groups[vert_group]), 1.0, 'ADD')

            if import_settings.preset == "SHADOW_BRUSHES":
                modifier = ob.modifiers.new("Displace", type="DISPLACE")
                modifier.strength = -4.0
            blender_objects.append(ob)
            bpy.context.collection.objects.link(ob)
        QuakeShader.init_shader_system(bsp_file)
        QuakeShader.build_quake_shaders(VFS, import_settings, blender_objects)
        return
    
    print("prepare for packing internal lightmaps")
    bsp_file.lightmap_size = bsp_file.compute_packed_lightmap_size()
    print("get bsp entity objects")
    bsp_objects = bsp_file.get_bsp_entity_objects()
    print("create blender objects")
    blender_objects = create_blender_objects(
        VFS,
        import_settings,
        bsp_objects,
        {},  # blender_meshes,
        bsp_file)
    
    print("handle fog volumes")
    bsp_fogs = bsp_file.get_bsp_fogs()
    fog_meshes = create_meshes_from_models(bsp_fogs)
    if fog_meshes is not None:
        for mesh_name in fog_meshes:
                mesh, vertex_groups = fog_meshes[mesh_name]
                if mesh is None:
                    mesh = bpy.data.meshes.new(mesh_name)
                ob = bpy.data.objects.new(
                        name=mesh_name,
                        object_data=mesh)
                # Give the volume a slight push so cycles doesnt z-fight...
                modifier = ob.modifiers.new("Displace", type="DISPLACE")
                blender_objects.append(ob)
                bpy.context.collection.objects.link(ob)

    print("get clip data and gridsize")
    clip_end = 40000
    if bsp_objects is not None and "worldspawn" in bsp_objects:
        worldspawn_object = bsp_objects["worldspawn"]
        custom_parameters = worldspawn_object.custom_parameters
        #if ("distancecull" in custom_parameters and
        #   import_settings.preset == "PREVIEW"):
        #    clip_end = float(custom_parameters["distancecull"])
        if "gridsize" in custom_parameters:
            grid_size = custom_parameters["gridsize"]
            bsp_file.lightgrid_size = grid_size
            bsp_file.lightgrid_inverse_size = [1.0 / float(grid_size[0]),
                                               1.0 / float(grid_size[1]),
                                               1.0 / float(grid_size[2])]

    print("apply clip data")
    set_blender_clip_spaces(4.0, clip_end)

    print("get bsp images")
    bsp_images = bsp_file.get_bsp_images()
    for image in bsp_images:
        old_image = bpy.data.images.get(image.name)
        if old_image != None:
            old_image.name = image.name + "_prev.000"
        try:
            new_image = bpy.data.images.new(
                image.name,
                width=image.width,
                height=image.height,
                alpha=image.num_components == 4)
            new_image.pixels = image.get_rgba()
            new_image.alpha_mode = 'CHANNEL_PACKED'
            new_image.use_fake_user = True
            new_image.pack()
        except Exception:
            print("Couldn't retreve image from bsp:", image.name)

    print("handle external lightmaps")
    if bsp_file.num_internal_lm_ids >= 0 and bsp_file.external_lm_files:
        tmp_folder = bpy.app.tempdir.replace("\\", "/")
        external_lm_lump = []
        width, height = None, None
        for file_name in bsp_file.external_lm_files:
            tmp_image = BlenderImage.load_file(file_name, VFS)
            if tmp_image is None:
                print("Could not load:", file_name)
                continue
            if not width:
                width = tmp_image.size[0]
            if not height:
                height = tmp_image.size[1]

            if width != tmp_image.size[0] or height != tmp_image.size[1]:
                print("External lightmaps all need to be the same size")
                break

            external_lm_lump.append(list(tmp_image.pixels[:]))

        bsp_file.internal_lightmap_size = (width, height)
        bsp_file.lightmap_size = bsp_file.compute_packed_lightmap_size()

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

        if bsp_file.deluxemapping:
            atlas_pixels = bsp_file.pack_lightmap(
                external_lm_lump,
                bsp_file.deluxemapping,
                True,
                False,
                4)

            new_image = bpy.data.images.new(
                "$deluxemap",
                width=bsp_file.lightmap_size[0],
                height=bsp_file.lightmap_size[1])
            new_image.pixels = atlas_pixels
            new_image.alpha_mode = 'CHANNEL_PACKED'

    bpy.context.scene.id_tech_3_lightmaps_per_row = int(bsp_file.lightmap_size[0] / bsp_file.internal_lightmap_size[0])
    bpy.context.scene.id_tech_3_lightmaps_per_column = int(bsp_file.lightmap_size[1] / bsp_file.internal_lightmap_size[1])

    QuakeShader.init_shader_system(bsp_file)
    QuakeShader.build_quake_shaders(VFS, import_settings, blender_objects)


def import_map_file(import_settings):

    # initialize virtual file system
    VFS = Q3VFS()
    for base_path in import_settings.base_paths:
        VFS.add_base(base_path)
    VFS.build_index()

    byte_array = VFS.get(import_settings.file)

    entities = MAP.read_map_file(byte_array, import_settings)
    objects = create_blender_objects(
        VFS,
        import_settings,
        entities,
        {},
        None)

    set_blender_clip_spaces(4.0, 40000.0)

    QuakeShader.init_shader_system(None)
    QuakeShader.build_quake_shaders(VFS, import_settings, objects)
