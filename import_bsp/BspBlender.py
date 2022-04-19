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

import imp
import os

import cProfile

if "bpy" not in locals():
    import bpy

from .BSP import BSP_READER as BSP
from .Quake3VFS import Q3VFS
from math import floor

if "Entities" in locals():
    imp.reload(Entities)
else:
    from . import Entities


def create_meshes_from_models(models):
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
        for poly in mesh.polygons:
            poly.use_smooth = True

        normal_array = []
        indexed_normals = model.vertex_normals.get_indexed()
        for i in indexed_normals:
            normal_array.append(i[0])
            normal_array.append(i[1])
            normal_array.append(i[2])

        if len(indexed_normals) > 0:
            mesh.vertices.foreach_set("normal", normal_array)
            mesh.normals_split_custom_set_from_vertices(indexed_normals)

        for uv_layer in model.uv_layers:
            if uv_layer.startswith("Lightmap"):
                uvs = []
                for uv in model.uv_layers[uv_layer].get_unindexed(tuple):
                    uvs.append(uv[0])
                    uvs.append(uv[1])
            else:
                uvs = []
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
    bsp_models = bsp_file.get_bsp_models()
    # profiler.disable()
    # profiler.print_stats()

    # convert bsp data to blender data
    create_meshes_from_models(bsp_models)

    # create blender objects
    if import_settings.preset == "BRUSHES":
        for model in bsp_models:
            name = model.name
            mesh = bpy.data.meshes.get(name)
            if mesh is None:
                mesh = bpy.data.meshes.new(name)
            ob = bpy.data.objects.new(
                    name=name,
                    object_data=mesh)
            bpy.context.collection.objects.link(ob)
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                for s in a.spaces:
                    if s.type == 'VIEW_3D':
                        s.clip_start = 4
                        s.clip_end = 40000
    else:
        Entities.ImportEntities(VFS, bsp_file, import_settings)

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

            working_pixels = list(tmp_image.pixels[:])
            pixels = []
            for y in range(tmp_image.size[1]):
                for x in range(tmp_image.size[0]):
                    id = floor(
                        x + (tmp_image.size[0] * (tmp_image.size[1]-1)) - (
                            tmp_image.size[0] * y))
                    pixels.append(working_pixels[id * 4 + 0])
                    pixels.append(working_pixels[id * 4 + 1])
                    pixels.append(working_pixels[id * 4 + 2])
                    pixels.append(working_pixels[id * 4 + 3])

            external_lm_lump.append(pixels)

        # compute new sized atlas
        num_colums = (bsp_file.lightmap_size[0] //
                      bsp_file.internal_lightmap_size[0])
        num_rows = (bsp_file.lightmap_size[1] //
                    bsp_file.internal_lightmap_size[1])
        num_colums = 2
        num_rows = 2
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
