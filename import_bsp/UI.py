# ----------------------------------------------------------------------------#
# TODO:  refactor loading bsp files and md3 files, right now its a mess o.O
# TODO:  Fix reimporting model when only the zoffset is different
#       check if model already loaded, make a copy of it, replace all the
#       material names with new zoffset
# ----------------------------------------------------------------------------#

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from bpy.types import PropertyGroup

import os
import uuid

from . import BlenderBSP, BlenderEntities
from . import MD3, TAN
from . import QuakeShader, QuakeSky, QuakeLight, ShaderNodes

from .idtech3lib import Helpers, Parsing, GamePacks
from .idtech3lib.ID3VFS import Q3VFS
from .idtech3lib.ImportSettings import *


def get_base_paths(context, import_file_path = None):
    addon_name = __name__.split('.')[0]
    prefs = context.preferences.addons[addon_name].preferences

    paths = []
    # mod paths overwrite files in base, so are higher priority
    for path in [prefs.mod_path_1, prefs.mod_path_0, prefs.base_path]:
        if path.strip() == "":
            continue
        fixed_base_path = path.replace("\\", "/")
        if not fixed_base_path.endswith('/'):
            fixed_base_path = fixed_base_path + '/'
        paths.append(fixed_base_path)
    # no path found, so make a guess?
    if len(paths) == 0 and import_file_path is not None:
        fixed_file_path = import_file_path.replace("\\", "/")
        split_folder = "/maps/"
        if fixed_file_path.endswith(".md3") or fixed_file_path.endswith(".tik"):
            split_folder = "/models/"
        split = fixed_file_path.split(split_folder)
        if len(split) > 1:
            paths = [split[0] + '/']
            print("Guessed base path:" + paths[0])

    return paths

def get_current_entity_dict(context):
    addon_name = __name__.split('.')[0]
    prefs = context.preferences.addons[addon_name].preferences

    dict_path = bpy.utils.script_paths(
            subdir="addons/import_bsp/gamepacks/")[0]
    gamepack = prefs.gamepack
    entity_dict = GamePacks.get_gamepack(dict_path, gamepack)
    return entity_dict
    

class Import_ID3_BSP(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id3_bsp"
    bl_label = "Import ID3 engine BSP (.bsp)"
    filename_ext = ".bsp"
    filter_glob: StringProperty(default="*.bsp", options={'HIDDEN'})

    filepath: StringProperty(
        name="File Path",
        description="File path used for importing the BSP file",
        maxlen=1024,
        default="")
    preset: EnumProperty(
        name="Import preset",
        description="You can select wether you want to import a bsp for "
        "editing, rendering, or previewing.",
        default=Preset.PREVIEW.value,
        items=[
            (Preset.PREVIEW.value, "Preview",
             "Builds eevee shaders, imports all misc_model_statics "
             "when available", 0),
            (Preset.EDITING.value, "Entity Editing",
             "Builds eevee shaders, imports all entitys, enables "
             "entitiy modding", 1),
            (Preset.RENDERING.value, "Rendering",
             "Builds cycles shaders, only imports visable enities", 2),
            (Preset.BRUSHES.value, "Brushes",
             "Imports all Brushes", 3),
            (Preset.SHADOW_BRUSHES.value, "Shadow Brushes", "Imports "
             "Brushes as shadow casters", 4),
        ])
    subdivisions: IntProperty(
        name="Patch subdivisions",
        description="How often a patch is subdivided at import",
        default=2)
    min_atlas_size: EnumProperty(
        name="Minimum Lightmap atlas size",
        description="Sets the minimum lightmap atlas size",
        default='128',
        items=[
            ('128', "128", "128x128", 128),
            ('256', "256", "256x256", 256),
            ('512', "512", "512x512", 512),
            ('1024', "1024", "1024x1024", 1024),
            ('2048', "2048", "2048x2048", 2048),
        ])
    vert_map_packing: EnumProperty(
        name="Vertex lit unwrap",
        description="Changes uv unwrapping for vertex lit surfaces",
        default='Primitive',
        items=[
            ('Keep', 'Keep', "Do nothing with the vertex lit lightmap texture coordinates", 0),
            ('Primitive', 'Primitive packing', "Tightly pack all vertex lit primitives. Useful for light baking", 1),
            ('UVMap', 'Diffuse UV copy', "Copies the diffuse UVs for the vertex lit surfaces. Useful for patching lightmap uvs", 2),
        ])

    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        brush_imports = (
            Preset.BRUSHES.value,
            Preset.SHADOW_BRUSHES.value
        )
        surface_types = Surface_Type.BAD
        if self.preset in brush_imports:
            surface_types = Surface_Type.BRUSH
        elif self.preset == Preset.EDITING.value:
            surface_types = (Surface_Type.BRUSH |
                             Surface_Type.PLANAR |
                             Surface_Type.PATCH |
                             Surface_Type.TRISOUP |
                             Surface_Type.FAKK_TERRAIN)
        else:
            surface_types = (Surface_Type.PLANAR |
                             Surface_Type.PATCH |
                             Surface_Type.TRISOUP |
                             Surface_Type.FAKK_TERRAIN)

        entity_dict = get_current_entity_dict(context)

        stupid_dict = {
            'Keep' : Vert_lit_handling.KEEP,
            'Primitive' : Vert_lit_handling.PRIMITIVE_PACK,
            'UVMap': Vert_lit_handling.UV_MAP
        }

        # trace some things like paths and lightmap size
        import_settings = Import_Settings(
            file=self.filepath.replace("\\", "/"),
            subdivisions=self.subdivisions,
            min_atlas_size=(
                int(self.min_atlas_size),
                int(self.min_atlas_size)
                ),
            base_paths=get_base_paths(context, self.filepath),
            preset=self.preset,
            front_culling=False,
            surface_types=surface_types,
            entity_dict=entity_dict,
            vert_lit_handling=stupid_dict[self.vert_map_packing],
            normal_map_option=prefs.normal_map_option,
        )

        # scene information
        context.scene.id_tech_3_importer_preset = self.preset
        if self.preset not in brush_imports:
            context.scene.id_tech_3_file_path = self.filepath

        BlenderBSP.import_bsp_file(import_settings)

        # set world color to black to remove additional lighting
        background = context.scene.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs[0].default_value = 0, 0, 0, 1

        if self.preset in brush_imports:
            context.scene.cycles.transparent_max_bounces = 36
        elif self.preset == "RENDERING":
            context.scene.render.engine = "CYCLES"
        else:
            context.scene.render.engine = "BLENDER_EEVEE_NEXT" if bpy.app.version >= (4, 2, 0) else "BLENDER_EEVEE"

        context.scene.eevee.volumetric_start = 4
        context.scene.eevee.volumetric_end = 100000
        context.scene.cycles.volume_preview_step_rate = 128
        context.scene.cycles.volume_step_rate = 64

        for line in import_settings.log:
            print(line)

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences

        row = layout.row()
        row.prop(self, "preset")
        row = layout.row()
        row.prop(self, "subdivisions")
        row = layout.row()
        row.prop(self, "min_atlas_size")
        row = layout.row()
        row.prop(self, "vert_map_packing")
        row = layout.row()
        row.prop(prefs, "normal_map_option")

class Import_MAP(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id_map"
    bl_label = "Import MAP file (.map)"
    filename_ext = ".map"
    filter_glob: StringProperty(default="*.map", options={'HIDDEN'})

    filepath: StringProperty(
        name="File Path",
        description="File path used for importing the MAP file",
        maxlen=1024,
        default="")
    subdivisions: IntProperty(
        name="Patch subdivisions",
        description="How often a patch is subdivided at import",
        default=2)
    only_lights: BoolProperty(
        name="Only lights",
        description="Only import lights from the map file",
        default=False)

    def execute(self, context):
        entity_dict = get_current_entity_dict(context)

        import_preset = Preset.ONLY_LIGHTS.value if self.only_lights else Preset.EDITING.value

        # trace some things like paths and lightmap size
        import_settings = Import_Settings(
            file=self.filepath.replace("\\", "/"),
            subdivisions=self.subdivisions,
            base_paths=get_base_paths(context, self.filepath),
            preset=import_preset,
            front_culling=False,
            surface_types=Surface_Type.BAD, # not used
            entity_dict=entity_dict,
            normal_map_option=NormalMapOption.SKIP.value
        )

        BlenderBSP.import_map_file(import_settings)

        if context.scene.id_tech_3_file_path == "":
            context.scene.id_tech_3_file_path = self.filepath

        return {'FINISHED'}


class Import_ID3_MD3(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id3_md3"
    bl_label = "Import ID3 engine MD3 (.md3)"
    filename_ext = ".md3"
    filter_glob: StringProperty(default="*.md3", options={'HIDDEN'})

    filepath: StringProperty(
        name="File Path",
        description="File path used for importing the MD3 file",
        maxlen=1024,
        default="")
    import_tags: BoolProperty(
        name="Import Tags",
        description="Whether to import the md3 tags or not",
        default=True)
    preset: EnumProperty(
        name="Import preset",
        description="You can select wether you want to import a md3 per "
        "object or merged into one object.",
        default='MERGED',
        items=[
            ('MERGED', "Merged", "Merges all the md3 content into "
             "one object", 0),
            ('OBJECTS', "Objects", "Imports MD3 objects", 1),
        ])

    def execute(self, context):
        # trace some things like paths and lightmap size
        import_settings = Import_Settings()
        import_settings.base_paths = get_base_paths(context, self.filepath)
        import_settings.bsp_name = ""
        import_settings.preset = "PREVIEW"
        import_settings.normal_map_option = NormalMapOption.SKIP.value

        # initialize virtual file system
        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        objs = MD3.ImportMD3Object(
            VFS,
            self.filepath.replace("\\", "/"),
            self.import_tags,
            self.preset == 'OBJECTS')
        QuakeShader.build_quake_shaders(VFS, import_settings, objs)

        if context.scene.id_tech_3_file_path == "":
            context.scene.id_tech_3_file_path = self.filepath

        return {'FINISHED'}


class Import_ID3_TIK(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id3_tik"
    bl_label = "Import ID3 engine TIKK (.tik)"
    filename_ext = ".tik"
    filter_glob: StringProperty(default="*.tik", options={'HIDDEN'})

    filepath: StringProperty(
        name="File Path",
        description="File path used for importing the TIK file",
        maxlen=1024,
        default="")
    import_tags: BoolProperty(
        name="Import Tags",
        description="Whether to import the Tikk tags or not",
        default=True)
    preset: EnumProperty(
        name="Import preset",
        description="You can select wether you want to import a tik per "
        "object or merged into one object.",
        default='MERGED',
        items=[
            ('MERGED', "Merged", "Merges all the tik "
             "content into one object", 0),
            ('OBJECTS', "Objects", "Imports tik objects", 1),
        ])

    def execute(self, context):
        # trace some things like paths and lightmap size
        import_settings = Import_Settings()
        import_settings.base_paths = get_base_paths(context, self.filepath)
        import_settings.bsp_name = ""
        import_settings.preset = "PREVIEW"
        import_settings.normal_map_option = NormalMapOption.SKIP.value

        # initialize virtual file system
        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        objs = TAN.ImportTIKObject(
            VFS,
            self.filepath.replace("\\", "/"),
            self.import_tags,
            self.preset == 'OBJECTS')
        QuakeShader.build_quake_shaders(VFS, import_settings, objs)

        if context.scene.id_tech_3_file_path == "":
            context.scene.id_tech_3_file_path = self.filepath

        return {'FINISHED'}


class Export_ID3_MD3(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.id3_md3"
    bl_label = "Export ID3 engine MD3 (.md3)"
    filename_ext = ".md3"
    filter_glob: StringProperty(default="*.md3", options={'HIDDEN'})

    filepath: StringProperty(
        name="File Path",
        description="File path used for exporting the MD3 file",
        maxlen=1024,
        default="")
    only_selected: BoolProperty(
        name="Export only selected",
        description="Exports only selected Objects",
        default=False)
    individual: BoolProperty(
        name="Local space coordinates",
        description="Uses every models local space coordinates instead of "
        "the world space")
    start_frame: IntProperty(
        name="Start Frame",
        description="First frame to export",
        default=0,
        min=0)
    end_frame: IntProperty(
        name="End Frame",
        description="Last frame to export",
        default=0,
        min=0)
    preset: EnumProperty(
        name="Surfaces",
        description="You can select wether you want to export per object "
        "or merged based on materials.",
        default='MATERIALS',
        items=[
            ('MATERIALS', "From Materials",
             "Merges surfaces based on materials. Supports multi "
             "material objects", 0),
            ('OBJECTS', "From Objects",
             "Simply export objects. There will be no optimization", 1),
        ])
    limits: EnumProperty(
        name="Limits",
        description="Choose limits to enforce on export",
        default='LEGACY',
        items=[
            ('LEGACY', "Legacy",
             "999 vertices per md3 surface, max of 32 surfaces. "
             "Perfect for Quake 3 era engines.", 0),
            ('SPEC', "MD3 Specification",
             "4095 vertices per md3 surface, max of 32 surfaces. "
             "GZDoom and other engines use these.", 1),
            ('RAISED', "Raised",
             "8191 vertices per md3 surface, max of 100 surfaces.", 2),
            ('MODERN', "Modern",
             "65534 vertices per md3 surface, max of 64 surfaces.", 3)
        ])

    def execute(self, context):
        objects = context.scene.objects
        if self.only_selected:
            objects = context.selected_objects

        max_vertices = 1000
        max_surfaces = 32
        if self.limits == "MODERN":
            max_vertices = 65535
            max_surfaces = 64
        elif self.limits == "SPEC":
            max_vertices = 4096
            max_surfaces = 32
        elif self.limits == "RAISED":
            max_vertices = 8192
            max_surfaces = 100

        frame_list = range(self.start_frame, max(
            self.end_frame, self.start_frame) + 1)
        status = MD3.ExportMD3(
            self.filepath.replace("\\", "/"),
            objects,
            frame_list,
            self.individual,
            self.preset == 'MATERIALS',
            max_vertices,
            max_surfaces)
        if status[0]:
            return {'FINISHED'}
        else:
            self.report({"ERROR"}, status[1])
            return {'CANCELLED'}


class Export_ID3_TIK(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.id3_tik"
    bl_label = "Export ID3 engine TIK (.tik)"
    filename_ext = ".tik"
    filter_glob: StringProperty(default="*.tik", options={'HIDDEN'})

    filepath: StringProperty(
        name="File Path",
        description="File path used for exporting the TIK file",
        maxlen=1024,
        default="")
    only_selected: BoolProperty(
        name="Export only selected",
        description="Exports only selected Objects",
        default=False)
    individual: BoolProperty(
        name="Local space coordinates",
        description="Uses every models local space coordinates instead of "
        "the world space")
    start_frame: IntProperty(
        name="Start Frame",
        description="First frame to export",
        default=0,
        min=0)
    end_frame: IntProperty(
        name="End Frame",
        description="Last frame to export",
        default=0,
        min=0)
    type: EnumProperty(
        name="Surface Type",
        description="You can select wether you want to export a tan "
        "model or skb model",
        default='TAN',
        items=[
            ('TAN', ".tan", "Exports a tan model", 0),
            #('SKB', ".skb", "Exports a skb model", 1),
        ])
    preset: EnumProperty(
        name="Surfaces",
        description="You can select wether you want to export per "
        "object or merged based on materials.",
        default='MATERIALS',
        items=[
            ('MATERIALS', "From Materials",
             "Merges surfaces based on materials. Supports "
             "multi material objects",
             0),
            ('OBJECTS', "From Objects",
             "Simply export objects. There will be no optimization",
             1),
        ])
    sub_path: bpy.props.StringProperty(
        name="Tan path",
        description="Where to save the tan file relative to the TIK file",
        default="",
        maxlen=2048,
    )

    def execute(self, context):
        objects = context.scene.objects
        if self.only_selected:
            objects = context.selected_objects

        fixed_subpath = self.sub_path.replace("\\", "/")
        if not fixed_subpath.endswith("/"):
            fixed_subpath += "/"
        if not fixed_subpath.startswith("/"):
            fixed_subpath = "/" + fixed_subpath

        frame_list = range(self.start_frame, max(
            self.end_frame, self.start_frame) + 1)
        if self.type == "TAN":
            status = TAN.ExportTIK_TAN(
                self.filepath.replace("\\", "/"),
                fixed_subpath,
                objects,
                frame_list,
                self.individual,
                self.preset == 'MATERIALS')
        else:
            self.report({"ERROR"}, "SKB exporting is not supported yet. :(")
        if status[0]:
            return {'FINISHED'}
        else:
            self.report({"ERROR"}, status[1])
            return {'CANCELLED'}


def menu_func_bsp_import(self, context):
    self.layout.operator(Import_ID3_BSP.bl_idname, text="ID3 BSP (.bsp)")


def menu_func_map_import(self, context):
    self.layout.operator(Import_MAP.bl_idname, text="ID3 MAP (.map)")


def menu_func_md3_import(self, context):
    self.layout.operator(Import_ID3_MD3.bl_idname, text="ID3 MD3 (.md3)")


def menu_func_tik_import(self, context):
    self.layout.operator(Import_ID3_TIK.bl_idname, text="ID3 TIK (.tik)")


def menu_func_md3_export(self, context):
    self.layout.operator(Export_ID3_MD3.bl_idname, text="ID3 MD3 (.md3)")


def menu_func_tik_export(self, context):
    self.layout.operator(Export_ID3_TIK.bl_idname, text="ID3 TIK (.tik)")


flag_mapping = {
    1: "b1",
    2: "b2",
    4: "b4",
    8: "b8",
    16: "b16",
    32: "b32",
    64: "b64",
    128: "b128",
    256: "b256",
    512: "b512",
}


class Del_property(bpy.types.Operator):
    bl_idname = "q3.del_property"
    bl_label = "Remove custom property"
    bl_options = {"UNDO", "INTERNAL", "REGISTER"}
    name: StringProperty()

    def execute(self, context):
        obj = bpy.context.active_object
        if self.name in obj:
            del obj[self.name]
            rna_ui = obj.get('_RNA_UI')
            if rna_ui is not None:
                del rna_ui[self.name]
        return {'FINISHED'}


type_matching = {"STRING": "NONE",
                 "COLOR": "COLOR_GAMMA",
                 "COLOR255": "COLOR_GAMMA",
                 "INT": "NONE",
                 "FLOAT": "NONE",
                 }
default_values = {"STRING": "",
                  "COLOR": [0.0, 0.0, 0.0],
                  "COLOR255": [0.0, 0.0, 0.0],
                  "INT": 0,
                  "FLOAT": 0.0,
                  }


class Add_property(bpy.types.Operator):
    bl_idname = "q3.add_property"
    bl_label = "Add custom property"
    bl_options = {"UNDO", "INTERNAL", "REGISTER"}
    name: StringProperty()

    def execute(self, context):
        ob = bpy.context.active_object
        key = self.name

        if key == "classname":
            ob["classname"] = ""
            return {'FINISHED'}

        entity_dict = get_current_entity_dict(context)

        Dict = entity_dict
        if self.name not in ob:
            default = ""

            rna_ui = ob.get('_RNA_UI')
            if rna_ui is None:
                ob['_RNA_UI'] = {}
                rna_ui = ob['_RNA_UI']

            descr_dict = {}
            if ob["classname"].lower() in Dict:
                if key.lower() in Dict[ob["classname"].lower()]["Keys"]:
                    if "Description" in Dict[
                            ob["classname"].lower()]["Keys"][key.lower()]:
                        descr_dict["description"] = Dict[ob["classname"].lower(
                        )]["Keys"][key.lower()]["Description"]
                    if "Type" in Dict[
                            ob["classname"].lower()]["Keys"][key.lower()]:
                        descr_dict["subtype"] = (
                            type_matching[Dict[ob["classname"].lower(
                            )]["Keys"][key.lower()]["Type"].upper()])
                        default = default_values[Dict[ob["classname"].lower(
                        )]["Keys"][key.lower()]["Type"].upper()]

            ob[self.name] = default
            rna_ui[key.lower()] = descr_dict
        return {'FINISHED'}


class Add_entity_definition(bpy.types.Operator):
    bl_idname = "q3.add_entity_definition"
    bl_label = "Update entity definition"
    bl_options = {"INTERNAL", "REGISTER"}
    name: StringProperty(
        name="New Property",
        default="",
    )

    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        dict_path = bpy.utils.script_paths(
            subdir="addons/import_bsp/gamepacks/")[0]

        new_entry = {"Color": [0.0, 0.5, 0.0],
                     "Mins": [-8, -8, -8],
                     "Maxs": [8, 8, 8],
                     "Model": "box",
                     "Description": "NOT DOCUMENTED YET",
                     "Spawnflags": {},
                     "Keys": {},
                     }

        entity_dict = get_current_entity_dict(context)

        entity_dict[self.name] = new_entry
        GamePacks.save_gamepack(
            entity_dict, dict_path, prefs.gamepack)
        return {'FINISHED'}


class Add_key_definition(bpy.types.Operator):
    bl_idname = "q3.add_key_definition"
    bl_label = "Update entity definition"
    bl_options = {"INTERNAL", "REGISTER"}
    name: StringProperty(
        name="New Property",
        default="",
    )

    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences

        dict_path = bpy.utils.script_paths(
            subdir="addons/import_bsp/gamepacks/")[0]

        obj = bpy.context.active_object

        if self.name != "":
            key = self.name
        else:
            scene = context.scene
            if "new_id_tech_3_prop_name" in scene:
                key = scene.new_id_tech_3_prop_name
            else:
                print("Couldn't find new property name :(\n")
                return {'CANCELLED'}

        entity_dict = get_current_entity_dict(context)

        if "classname" in obj:
            classname = obj["classname"]
            if classname.lower() in entity_dict:
                if key not in entity_dict[classname.lower()]["Keys"]:
                    entity_dict[classname.lower()]["Keys"][key] = {
                        "Type": "STRING",
                        "Description": "NOT DOCUMENTED YET"}
                    GamePacks.save_gamepack(
                        entity_dict,
                        dict_path,
                        prefs.gamepack)
        return {'FINISHED'}


type_save_matching = {"NONE": "STRING",
                      "COLOR_GAMMA": "COLOR",
                      "COLOR": "COLOR",
                      }


class Update_entity_definition(bpy.types.Operator):
    bl_idname = "q3.update_entity_definition"
    bl_label = "Update entity definition"
    bl_options = {"INTERNAL", "REGISTER"}
    name: StringProperty()

    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences

        dict_path = bpy.utils.script_paths(
            subdir="addons/import_bsp/gamepacks/")[0]

        obj = bpy.context.active_object

        rna_ui = obj.get('_RNA_UI')
        if rna_ui is None:
            obj['_RNA_UI'] = {}
            rna_ui = obj['_RNA_UI']

        entity_dict = get_current_entity_dict(context)

        if self.name in entity_dict:
            ent = entity_dict[self.name]
            for key in rna_ui.to_dict():
                if key in ent["Keys"] and key in rna_ui:
                    if "description" in rna_ui[key]:
                        ent["Keys"][key]["Description"] = (
                            rna_ui[key]["description"])
                    if "subtype" in rna_ui[key]:
                        ent["Keys"][key]["Type"] = (
                            type_save_matching[rna_ui[key]["subtype"]])

            GamePacks.save_gamepack(
                entity_dict,
                dict_path,
                prefs.gamepack)

        return {'FINISHED'}


def update_spawn_flag(self, context):
    obj = bpy.context.active_object
    if obj is None:
        return

    spawnflag = 0
    if obj.q3_dynamic_props.b1:
        spawnflag += 1
    if obj.q3_dynamic_props.b2:
        spawnflag += 2
    if obj.q3_dynamic_props.b4:
        spawnflag += 4
    if obj.q3_dynamic_props.b8:
        spawnflag += 8
    if obj.q3_dynamic_props.b16:
        spawnflag += 16
    if obj.q3_dynamic_props.b32:
        spawnflag += 32
    if obj.q3_dynamic_props.b64:
        spawnflag += 64
    if obj.q3_dynamic_props.b128:
        spawnflag += 128
    if obj.q3_dynamic_props.b256:
        spawnflag += 256
    if obj.q3_dynamic_props.b512:
        spawnflag += 512
    obj["spawnflags"] = spawnflag
    if spawnflag == 0:
        del obj["spawnflags"]


def get_empty_bsp_model_mesh():
    mesh = bpy.data.meshes.get("Empty_BSP_Model")
    if (mesh is None):
        ent_object = bpy.ops.mesh.primitive_cube_add(
            size=32.0, location=([0, 0, 0]))
        ent_object = bpy.context.object
        ent_object.name = "EntityBox"
        mesh = ent_object.data
        mesh.name = "Empty_BSP_Model"
        bpy.data.objects.remove(ent_object, do_unlink=True)
    return mesh


def get_empty_bsp_model_mat():
    mat = bpy.data.materials.get("Empty_BSP_Model")
    if (mat is None):
        mat = bpy.data.materials.new(name="Empty_BSP_Model")
        mat.use_nodes = True
        mat.blend_method = "CLIP"
        mat.shadow_method = "NONE"
        node = mat.node_tree.nodes["Principled BSDF"]
        node.inputs["Alpha"].default_value = 0.0
    return mat


def make_empty_bsp_model(context):
    mesh = get_empty_bsp_model_mesh()
    mat = get_empty_bsp_model_mat()
    ob = bpy.data.objects.new(name="Empty_BSP_Model", object_data=mesh.copy())
    ob.data.materials.append(mat)
    bpy.context.collection.objects.link(ob)
    return ob


def update_model(self, context):
    obj = bpy.context.active_object
    if obj is None:
        return

    dynamic_model = obj.q3_dynamic_props.model.split(".")[0]
    if (dynamic_model.startswith("*") and (
            dynamic_model not in bpy.data.meshes)) or (
            dynamic_model.strip(" \t\r\n") == ""):
        obj.data = get_empty_bsp_model_mesh()
        mat = get_empty_bsp_model_mat()
        obj["model"] = obj.q3_dynamic_props.model
        if mat.name not in obj.data.materials:
            obj.data.materials.append(mat)
        return

    orig_model = None
    if "model" in obj:
        orig_model = obj["model"][:]
        if not dynamic_model.startswith("*"):
            obj["model"] = dynamic_model + ".md3"
        else:
            obj["model"] = dynamic_model
        model_name = obj["model"]
    else:
        return

    if obj.data.name == dynamic_model:
        return

    model_name = model_name.replace("\\", "/").lower()
    if model_name.endswith(".md3"):
        model_name = model_name[:-len(".md3")]

    if not model_name.startswith("*"):
        mesh_name = Parsing.guess_model_name(model_name)
    else:
        mesh_name = model_name
        obj["model"] = model_name

    if mesh_name in bpy.data.meshes:
        obj.data = bpy.data.meshes[mesh_name]
        obj.q3_dynamic_props.model = obj.data.name
    else:
        zoffset = 0
        if "zoffset" in obj:
            zoffset = int(obj["zoffset"])

        import_settings = Import_Settings()
        import_settings.base_paths = get_base_paths(
            context, context.scene.id_tech_3_file_path)
        import_settings.shader_dirs = "shaders/", "scripts/"
        import_settings.preset = 'PREVIEW'

        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        mesh = MD3.ImportMD3(VFS, mesh_name + ".md3", zoffset)[0]
        if mesh is not None:
            obj.data = mesh
            obj.q3_dynamic_props.model = obj.data.name
            QuakeShader.build_quake_shaders(VFS, import_settings, [obj])
        elif orig_model is not None:
            obj["model"] = orig_model


def getChildren(obj):
    children = []
    for ob in bpy.data.objects:
        if ob.parent == obj:
            children.append(ob)
    return children


def update_model2(self, context):
    obj = bpy.context.active_object
    if obj is None:
        return

    if "model2" in obj:
        obj["model2"] = obj.q3_dynamic_props.model2.split(".")[0] + ".md3"
        model_name = obj["model2"]
    else:
        return

    model_name = model_name.replace("\\", "/").lower()
    if model_name.endswith(".md3"):
        model_name = model_name[:-len(".md3")]

    mesh_name = Parsing.guess_model_name(model_name)

    children = getChildren(obj)
    if mesh_name.strip(" \t\r\n") == "" and len(children) > 0:
        for chil in children:
            bpy.data.objects.remove(chil, do_unlink=True)
        return

    if len(children) > 0:
        if children[0].data.name == obj.q3_dynamic_props.model2.split(".")[0]:
            return
    else:
        m2_obj = make_empty_bsp_model(context)
        m2_obj.name = "{}_model2".format(obj.name)
        m2_obj.hide_select = True
        m2_obj.parent = obj
        children = [m2_obj]

    if mesh_name in bpy.data.meshes:
        children[0].data = bpy.data.meshes[mesh_name]
        obj.q3_dynamic_props.model2 = children[0].data.name
    else:
        zoffset = 0
        if "zoffset" in obj:
            zoffset = int(obj["zoffset"])

        import_settings = Import_Settings()
        import_settings.base_paths = get_base_paths(
            context, context.scene.id_tech_3_file_path)
        import_settings.shader_dirs = "shaders/", "scripts/"
        import_settings.preset = 'PREVIEW'

        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        mesh = MD3.ImportMD3(VFS, mesh_name + ".md3", zoffset)[0]
        if mesh is not None:
            children[0].data = mesh
            obj.q3_dynamic_props.model2 = children[0].data.name
            QuakeShader.build_quake_shaders(VFS, import_settings, [children[0]])


# Properties like spawnflags and model
class DynamicProperties(PropertyGroup):
    b1: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b2: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b4: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b8: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b16: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b32: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b64: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b128: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b256: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    b512: BoolProperty(
        name="",
        default=False,
        update=update_spawn_flag
    )
    model: StringProperty(
        name="Model",
        default="EntityBox",
        update=update_model,
        subtype="FILE_PATH"
    )
    model2: StringProperty(
        name="Model2",
        default="EntityBox",
        update=update_model2,
        subtype="FILE_PATH"
    )


# Panels
class Q3_PT_ShaderPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_shader_panel"
    bl_label = "Shaders"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ID3 Shaders"

    def draw(self, context):
        layout = self.layout

        scene = context.scene
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences

        row = layout.row()
        row.scale_y = 1.0
        row.operator("q3mapping.reload_preview_shader")
        row = layout.row()
        row.operator("q3mapping.reload_render_shader")
        row = layout.row()
        row.prop(prefs, "normal_map_option")
        layout.separator()

        lg_group = bpy.data.node_groups.get("LightGrid")
        if lg_group is not None:
            col = layout.column()
            if "Ambient light helper" in lg_group.nodes:
                ambient = lg_group.nodes["Ambient light helper"].outputs[0]
                col.prop(ambient, "default_value", text="Ambient light")
            if "Direct light helper" in lg_group.nodes:
                direct = lg_group.nodes["Direct light helper"].outputs[0]
                col.prop(direct, "default_value", text="Direct light")
            if "Light direction helper" in lg_group.nodes:
                vec = lg_group.nodes["Light direction helper"].outputs[0]
                col.prop(vec, "default_value", text="Light direction")

        emission_group = bpy.data.node_groups.get("EmissionScaleNode")
        if emission_group is not None:
            col = layout.column()
            if "Emission scale" in emission_group.nodes:
                scale = emission_group.nodes["Emission scale"].outputs[0]
                col.prop(scale, "default_value", text="Shader Emission Scale")
            if "Extra emission scale" in emission_group.nodes:
                scale = emission_group.nodes["Extra emission scale"].outputs[0]
                col.prop(scale, "default_value",
                         text="Extra Shader Emission Scale")


class Q3_PT_EntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_entity_panel"
    bl_label = "Selected Entity"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ID3 Entities"

    def draw(self, context):
        layout = self.layout
        obj = bpy.context.active_object

        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences

        if obj is None:
            return

        layout.prop(prefs,"gamepack")

        if "classname" in obj:
            layout.prop(obj, '["classname"]')
        else:
            op = layout.operator(
                "q3.add_property", text="Add classname").name = "classname"


class Q3_PT_PropertiesEntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_properties_entity_panel"
    bl_parent_id = "Q3_PT_entity_panel"
    bl_label = "Entity Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ID3 Entities"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = bpy.context.active_object

        if obj is None:
            return

        filtered_keys = ["classname", "spawnflags",
                         "origin", "angles", "angle"]
        if obj.data.name.startswith("*"):
            filtered_keys = ["classname", "spawnflags", "origin"]

        entity_dict = get_current_entity_dict(context)

        if "classname" in obj:
            classname = obj["classname"].lower()
            if classname in entity_dict:
                ent = entity_dict[classname]

                box = None
                # check all the flags
                for flag in ent["Spawnflags"].items():
                    if box is None:
                        box = layout.box()
                    box.prop(obj.q3_dynamic_props,
                             flag_mapping[flag[1]["Bit"]], text=flag[0])

                # now check all the keys
                supported = None
                unsupported = None
                keys = ent["Keys"]
                for prop in obj.keys():
                    # only show generic properties and filter
                    if prop.lower() not in filtered_keys and (
                            not hasattr(obj[prop], "to_dict")):
                        if prop.lower() == "model":
                            if supported is None:
                                supported = layout.box()
                            row = supported.row()
                            row.prop(obj.q3_dynamic_props,
                                     "model", text="model")
                            row.operator("q3.del_property",
                                         text="", icon="X").name = prop
                            continue
                        if prop.lower() == "model2":
                            if supported is None:
                                supported = layout.box()
                            row = supported.row()
                            row.prop(obj.q3_dynamic_props,
                                     "model2", text="model2")
                            row.operator("q3.del_property",
                                         text="", icon="X").name = prop
                            continue

                        if prop.lower() in keys:
                            if supported is None:
                                supported = layout.box()
                            row = supported.row()
                            row.prop(obj, '["' + prop + '"]')
                            row.operator("q3.del_property",
                                         text="", icon="X").name = prop
                        else:
                            if unsupported is None:
                                unsupported = layout.box()
                                unsupported.label(text="Unknown Properties:")
                            row = unsupported.row()
                            row.prop(obj, '["' + prop + '"]')
                            row.operator("q3.del_property",
                                         text="", icon="X").name = prop
                for key in keys:
                    test_key = obj.get(key.lower())
                    if test_key is None:
                        if supported is None:
                            supported = layout.box()
                        row = supported.row()
                        op = row.operator("q3.add_property",
                                          text="Add " + str(key)).name = key
            else:
                layout.label(text="Unknown entity")
                layout.label(
                    text='You can add it via "Edit Entity Definitions"')


class Q3_PT_DescriptionEntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_description_entity_panel"
    bl_parent_id = "Q3_PT_entity_panel"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Entity Description"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ID3 Entities"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = bpy.context.active_object

        if obj is None:
            return
        
        entity_dict = get_current_entity_dict(context)

        if "classname" in obj:
            classname = obj["classname"].lower()
            if classname in entity_dict:
                ent = entity_dict[classname]
                for line in ent["Description"]:
                    layout.label(text=line)
            else:
                layout.label(text="Unknown entity")
                layout.label(
                    text='You can add it via "Edit Entity Definitions"')


class Q3_PT_EditEntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_edit_entity_panel"
    bl_parent_id = "Q3_PT_entity_panel"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Edit Entity Definitions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ID3 Entities"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = bpy.context.active_object

        if obj is None:
            return

        filtered_keys = ["classname", "spawnflags",
                         "origin", "angles", "angle"]

        entity_dict = get_current_entity_dict(context)

        if "classname" in obj:
            classname = obj["classname"].lower()
            # classname in dictionary?
            if classname not in entity_dict:
                layout.operator(
                    "q3.add_entity_definition",
                    text="Add " + obj["classname"].lower() +
                         " to current Gamepack"
                         ).name = obj["classname"].lower()
            else:
                ent = entity_dict[classname]
                keys = ent["Keys"]
                for prop in obj.keys():
                    if prop.lower() not in filtered_keys and (
                            not hasattr(obj[prop], "to_dict")):
                        if prop.lower() not in keys:
                            op = layout.operator(
                                "q3.add_key_definition",
                                text="Add " + str(prop.lower()) +
                                     " to entity definition"
                                     ).name = prop.lower()

                row = layout.row()
                row.prop(context.scene, 'new_id_tech_3_prop_name')
                row.operator("q3.add_key_definition",
                             text="", icon="PLUS").name = ""

                layout.separator()
                layout.operator("q3.update_entity_definition").name = classname


class ExportEnt(bpy.types.Operator, ExportHelper):
    bl_idname = "q3.export_ent"
    bl_label = "Export to .ent file"
    bl_options = {"INTERNAL", "REGISTER"}
    filename_ext = ".ent"
    filter_glob: StringProperty(default="*.ent", options={'HIDDEN'})
    filepath: bpy.props.StringProperty(
        name="File",
        description="Where to write the .ent file",
        maxlen=1024,
        default="")

    def execute(self, context):
        entities = BlenderEntities.GetEntityStringFromScene()

        f = open(self.filepath, "w")
        try:
            f.write(entities)
        except Exception:
            print("Failed writing: " + self.filepath)

        f.close()
        return {'FINISHED'}


class PatchBspEntities(bpy.types.Operator, ExportHelper):
    bl_idname = "q3.patch_bsp_ents"
    bl_label = "Patch entities in existing .bsp"
    bl_options = {"INTERNAL", "REGISTER"}
    filename_ext = ".bsp"
    filter_glob: StringProperty(default="*.bsp", options={'HIDDEN'})
    filepath: StringProperty(
        name="File",
        description="Which .bsp file to patch",
        maxlen=1024,
        default="")
    create_backup: BoolProperty(
        name="Append a suffix to the output file (don't "
        "overwrite original file)",
        default=True)

    def execute(self, context):
        import_settings = Import_Settings(
            file=self.filepath.replace("\\", "/"),
            base_paths=get_base_paths(context)
        )

        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        bsp = BlenderBSP.get_bsp_file(VFS, import_settings)
   
        # swap entity lump
        entities = BlenderEntities.GetEntityStringFromScene()
        bsp.set_entity_lump(entities)

        # write bsp
        bsp_bytes = bsp.to_bytes()

        name = self.filepath
        if self.create_backup is True:
            name = name.replace(".bsp", "") + "_ent_patched.bsp"

        f = open(name, "wb")
        try:
            f.write(bsp_bytes)
        except Exception:
            print("Failed writing: " + name)

        f.close()
        return {'FINISHED'}


class PatchBspData(bpy.types.Operator, ExportHelper):
    bl_idname = "q3.patch_bsp_data"
    bl_label = "Patch data in existing .bsp"
    bl_options = {"INTERNAL", "REGISTER"}
    filename_ext = ".bsp"
    filter_glob: StringProperty(default="*.bsp", options={'HIDDEN'})
    filepath: StringProperty(
        name="File",
        description="Which .bsp file to patch",
        maxlen=1024,
        default="")
    only_selected: BoolProperty(name="Only selected objects", default=False)
    create_backup: BoolProperty(
        name="Append a suffix to filename (don't overwrite original file)",
        default=True)
    patch_lm_tcs: BoolProperty(name="Lightmap texture coordinates",
                               default=True)
    patch_tcs: BoolProperty(name="Texture coordinates", default=False)
    patch_normals: BoolProperty(name="Normals", default=False)

    patch_colors: BoolProperty(name="Vertex Colors", default=False)
    patch_lightgrid: BoolProperty(name="Light Grid", default=False)
    patch_lightmaps: BoolProperty(name="Lightmaps", default=True)
    lightmap_to_use: EnumProperty(
        name="Lightmap Atlas",
        description="Lightmap Atlas that will be used for patching",
        default='$lightmap_bake',
        items=[
            ('$lightmap_bake', "$lightmap_bake", "$lightmap_bake", 0),
            ('$lightmap', "$lightmap", "$lightmap", 1)])
    patch_external: BoolProperty(name="Save External Lightmaps", default=False)
    patch_external_flip: BoolProperty(
        name="Flip External Lightmaps",
        default=False)
    patch_empty_lm_lump: BoolProperty(
        name="Remove Lightmaps in BSP",
        default=False)
    patch_hdr: BoolProperty(
        name="HDR Lighting Export",
        default=False)
    lightmap_gamma: EnumProperty(
        name="Lightmap Gamma",
        description="Lightmap Gamma Correction",
        default='sRGB',
        items=[
            ('sRGB', "sRGB", "sRGB", 0),
            ('1.0', "1.0", "1.0", 1),
            ('2.0', "2.0", "2.0", 2),
            ('4.0', "4.0", "4.0", 3)
        ])
    overbright_bits: EnumProperty(
        name="Overbright Bits",
        description="Overbright Bits",
        default='0',
        items=[
            ('0', "0", "0", 0),
            ('1', "1", "1", 1),
            ('2', "2", "2", 2)
        ])
    compensate: BoolProperty(name="Compensate", default=False)

    # TODO Shader lump + shader assignments
    def execute(self, context):
        class light_settings:
            pass
        light_settings = light_settings()
        light_settings.gamma = self.lightmap_gamma
        light_settings.overbright_bits = int(self.overbright_bits)
        light_settings.compensate = self.compensate
        light_settings.hdr = self.patch_hdr

        entity_dict = get_current_entity_dict(context)

        import_settings = Import_Settings(
            file=self.filepath.replace("\\", "/"),
            subdivisions=-1,
            min_atlas_size=(
                int(128),
                int(128)
                ),
            base_paths=get_base_paths(context),
            preset="PREVIEW",
            front_culling=False,
            surface_types=Surface_Type.BAD,
            entity_dict=entity_dict
        )

        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        bsp = BlenderBSP.get_bsp_file(VFS, import_settings)

        if self.only_selected:
            objs = [
                obj
                for obj in context.selected_objects
                if obj.type == "MESH"
            ]
        else:
            if bpy.app.version >= (2, 91, 0):
                objs = [obj for obj in context.scene.objects
                        if obj.type == "MESH" and
                        obj.data.attributes.get("BSP_VERT_INDEX") is not None]
            else:
                objs = [obj for obj in context.scene.objects
                        if obj.type == "MESH" and
                        obj.data.vertex_layers_int.get("BSP_VERT_INDEX")
                        is not None]

        meshes = [obj.to_mesh() for obj in objs]

        if bpy.app.version < (4, 1, 0):
            for mesh in meshes:
                mesh.calc_normals_split()

        if (self.patch_colors or
           self.patch_normals or
           self.patch_lm_tcs or
           self.patch_tcs):
            self.report({"INFO"}, "Storing Vertex Data...")
            # stores bsp vertex indices
            patched_vertices = {id: False for id in range(
                len(bsp.lumps["drawverts"]))}
            lightmapped_vertices = {id: False for id in range(
                len(bsp.lumps["drawverts"]))}
            patch_lighting_type = True
            for obj, mesh in zip(objs, meshes):
                if self.patch_lm_tcs:
                    group_map = {
                        group.name: group.index for group in obj.vertex_groups}
                    if "Lightmapped" not in group_map:
                        patch_lighting_type = False

                if bpy.app.version >= (2, 91, 0):
                    msh_bsp_vert_index_layer = mesh.attributes.get(
                        "BSP_VERT_INDEX")
                else:
                    msh_bsp_vert_index_layer = mesh.vertex_layers_int.get(
                        "BSP_VERT_INDEX")

                # check if its an imported bsp data set
                if msh_bsp_vert_index_layer is not None:
                    bsp_indices = msh_bsp_vert_index_layer

                    if self.patch_lm_tcs and patch_lighting_type:
                        # store all vertices that are lightmapped
                        for index in [bsp_indices.data[vertex.index].value
                                      for vertex in mesh.vertices
                                      if group_map["Lightmapped"] in
                                      [vg.group for vg in vertex.groups]]:
                            if index >= 0:
                                lightmapped_vertices[index] = True

                    # patch all vertices of this mesh
                    for poly in mesh.polygons:
                        for vertex, loop in zip(
                             poly.vertices, poly.loop_indices):
                            # get the vertex position in the bsp file
                            bsp_vert_index = bsp_indices.data[vertex].value
                            if bsp_vert_index < 0:
                                continue
                            patched_vertices[bsp_vert_index] = True
                            bsp_vert = bsp.lumps["drawverts"][bsp_vert_index]
                            if self.patch_tcs:
                                bsp_vert.texcoord[:] = (
                                    mesh.uv_layers["UVMap"].data[loop].uv)
                                bsp_vert.texcoord[1] = 1.0 - bsp_vert.texcoord[1]
                            if self.patch_lm_tcs:
                                bsp_vert.lm1coord[:] = (
                                    mesh.uv_layers["LightmapUV"].data[loop].uv)
                                bsp_vert.lm1coord[0] = min(
                                    1.0, max(0.0, bsp_vert.lm1coord[0]))
                                bsp_vert.lm1coord[1] = min(
                                    1.0, max(0.0, bsp_vert.lm1coord[1]))
                                if bsp.lightmaps == 4:
                                    bsp_vert.lm2coord[:] = (
                                        mesh.uv_layers[
                                            "LightmapUV2"].data[loop].uv)
                                    bsp_vert.lm2coord[0] = min(
                                        1.0, max(0.0, bsp_vert.lm2coord[0]))
                                    bsp_vert.lm2coord[1] = min(
                                        1.0, max(0.0, bsp_vert.lm2coord[1]))
                                    bsp_vert.lm3coord[:] = (
                                        mesh.uv_layers[
                                            "LightmapUV3"].data[loop].uv)
                                    bsp_vert.lm3coord[0] = min(
                                        1.0, max(0.0, bsp_vert.lm3coord[0]))
                                    bsp_vert.lm3coord[1] = min(
                                        1.0, max(0.0, bsp_vert.lm3coord[1]))
                                    bsp_vert.lm4coord[:] = (
                                        mesh.uv_layers[
                                            "LightmapUV4"].data[loop].uv)
                                    bsp_vert.lm4coord[0] = min(
                                        1.0, max(0.0, bsp_vert.lm4coord[0]))
                                    bsp_vert.lm4coord[1] = min(
                                        1.0, max(0.0, bsp_vert.lm4coord[1]))
                            if self.patch_normals:
                                bsp_vert.normal[:] = (
                                    mesh.vertices[vertex].normal.copy())
                                if mesh.has_custom_normals:
                                    bsp_vert.normal[:] = (
                                        mesh.loops[loop].normal.copy())
                            if self.patch_colors:
                                vert_colors = mesh.vertex_colors
                                color = [
                                    int(c * 255.0) for c in vert_colors["Color"].data[loop].color]
                                color[3] = int(vert_colors["Alpha"].data[loop].color[0] * 255.0)
                                bsp_vert.color1[:] = color
                                if bsp.lightmaps == 4:
                                    color = [
                                        int(c * 255.0) for c in vert_colors["Color2"].data[loop].color]
                                    color[3] = int(vert_colors["Alpha"].data[loop].color[1] * 255.0)
                                    bsp_vert.color2[:] = color
                                    color = [
                                        int(c * 255.0) for c in vert_colors["Color3"].data[loop].color]
                                    color[3] = int(vert_colors["Alpha"].data[loop].color[2] * 255.0)
                                    bsp_vert.color3[:] = color
                                    color = [
                                        int(c * 255.0) for c in vert_colors["Color4"].data[loop].color]
                                    color[3] = int(vert_colors["Alpha"].data[loop].color[3] * 255.0)
                                    bsp_vert.color4[:] = color

                else:
                    self.report({"ERROR"}, "Not a valid mesh for patching")
                    return {'CANCELLED'}

            self.report({"INFO"}, "Successful")

        if self.patch_lm_tcs or self.patch_tcs:
            self.report({"INFO"}, "Storing Texture Coordinates...")
            lightmap_size = bsp.lightmap_size
            packed_lightmap_size = [
                lightmap_size[0] *
                bpy.context.scene.id_tech_3_lightmaps_per_column,
                lightmap_size[1] *
                bpy.context.scene.id_tech_3_lightmaps_per_row]

            fixed_vertices = []
            # fix lightmap tcs and tcs, set lightmap ids
            for bsp_surf in bsp.lumps["surfaces"]:
                # fix lightmap tcs and tcs for patches
                # unsmoothes tcs, so the game creates the same tcs we see here
                # in blender
                if bsp_surf.type == 2:
                    width = int(bsp_surf.patch_width-1)
                    height = int(bsp_surf.patch_height-1)
                    ctrlPoints = [
                        [0 for x in range(bsp_surf.patch_width)]
                        for y in range(bsp_surf.patch_height)]
                    for i in range(bsp_surf.patch_width):
                        for j in range(bsp_surf.patch_height):
                            ctrlPoints[j][i] = (
                                bsp.lumps["drawverts"][
                                    bsp_surf.vertex +
                                    j*bsp_surf.patch_width + i])

                    for i in range(width+1):
                        for j in range(1, height, 2):
                            if self.patch_lm_tcs:
                                ctrlPoints[j][i].lm1coord[0] = (
                                    4.0 * ctrlPoints[j][i].lm1coord[0]
                                    - ctrlPoints[j+1][i].lm1coord[0]
                                    - ctrlPoints[j-1][i].lm1coord[0]) * 0.5
                                ctrlPoints[j][i].lm1coord[1] = (
                                    4.0 * ctrlPoints[j][i].lm1coord[1]
                                    - ctrlPoints[j+1][i].lm1coord[1]
                                    - ctrlPoints[j-1][i].lm1coord[1]) * 0.5
                                if bsp.lightmaps == 4:
                                    ctrlPoints[j][i].lm2coord[0] = (
                                        4.0 * ctrlPoints[j][i].lm2coord[0]
                                        - ctrlPoints[j+1][i].lm2coord[0]
                                        - ctrlPoints[j-1][i].lm2coord[0]) * 0.5
                                    ctrlPoints[j][i].lm2coord[1] = (
                                        4.0 * ctrlPoints[j][i].lm2coord[1]
                                        - ctrlPoints[j+1][i].lm2coord[1]
                                        - ctrlPoints[j-1][i].lm2coord[1]) * 0.5
                                    ctrlPoints[j][i].lm3coord[0] = (
                                        4.0 * ctrlPoints[j][i].lm3coord[0]
                                        - ctrlPoints[j+1][i].lm3coord[0]
                                        - ctrlPoints[j-1][i].lm3coord[0]) * 0.5
                                    ctrlPoints[j][i].lm3coord[1] = (
                                        4.0 * ctrlPoints[j][i].lm3coord[1]
                                        - ctrlPoints[j+1][i].lm3coord[1]
                                        - ctrlPoints[j-1][i].lm3coord[1]) * 0.5
                                    ctrlPoints[j][i].lm4coord[0] = (
                                        4.0 * ctrlPoints[j][i].lm4coord[0]
                                        - ctrlPoints[j+1][i].lm4coord[0]
                                        - ctrlPoints[j-1][i].lm4coord[0]) * 0.5
                                    ctrlPoints[j][i].lm4coord[1] = (
                                        4.0 * ctrlPoints[j][i].lm4coord[1]
                                        - ctrlPoints[j+1][i].lm4coord[1]
                                        - ctrlPoints[j-1][i].lm4coord[1]) * 0.5
                            if self.patch_tcs:
                                ctrlPoints[j][i].texcoord[0] = (
                                    4.0 * ctrlPoints[j][i].texcoord[0]
                                    - ctrlPoints[j+1][i].texcoord[0]
                                    - ctrlPoints[j-1][i].texcoord[0]) * 0.5
                                ctrlPoints[j][i].texcoord[1] = (
                                    4.0 * ctrlPoints[j][i].texcoord[1]
                                    - ctrlPoints[j+1][i].texcoord[1]
                                    - ctrlPoints[j-1][i].texcoord[1]) * 0.5
                    for j in range(height+1):
                        for i in range(1, width, 2):
                            if self.patch_lm_tcs:
                                ctrlPoints[j][i].lm1coord[0] = (
                                    4.0 * ctrlPoints[j][i].lm1coord[0]
                                    - ctrlPoints[j][i+1].lm1coord[0]
                                    - ctrlPoints[j][i-1].lm1coord[0]) * 0.5
                                ctrlPoints[j][i].lm1coord[1] = (
                                    4.0 * ctrlPoints[j][i].lm1coord[1]
                                    - ctrlPoints[j][i+1].lm1coord[1]
                                    - ctrlPoints[j][i-1].lm1coord[1]) * 0.5
                                if bsp.lightmaps == 4:
                                    ctrlPoints[j][i].lm2coord[0] = (
                                        4.0 * ctrlPoints[j][i].lm2coord[0]
                                        - ctrlPoints[j][i+1].lm2coord[0]
                                        - ctrlPoints[j][i-1].lm2coord[0]) * 0.5
                                    ctrlPoints[j][i].lm2coord[1] = (
                                        4.0 * ctrlPoints[j][i].lm2coord[1]
                                        - ctrlPoints[j][i+1].lm2coord[1]
                                        - ctrlPoints[j][i-1].lm2coord[1]) * 0.5
                                    ctrlPoints[j][i].lm3coord[0] = (
                                        4.0 * ctrlPoints[j][i].lm3coord[0]
                                        - ctrlPoints[j][i+1].lm3coord[0]
                                        - ctrlPoints[j][i-1].lm3coord[0]) * 0.5
                                    ctrlPoints[j][i].lm3coord[1] = (
                                        4.0 * ctrlPoints[j][i].lm3coord[1]
                                        - ctrlPoints[j][i+1].lm3coord[1]
                                        - ctrlPoints[j][i-1].lm3coord[1]) * 0.5
                                    ctrlPoints[j][i].lm4coord[0] = (
                                        4.0 * ctrlPoints[j][i].lm4coord[0]
                                        - ctrlPoints[j][i+1].lm4coord[0]
                                        - ctrlPoints[j][i-1].lm4coord[0]) * 0.5
                                    ctrlPoints[j][i].lm4coord[1] = (
                                        4.0 * ctrlPoints[j][i].lm4coord[1]
                                        - ctrlPoints[j][i+1].lm4coord[1]
                                        - ctrlPoints[j][i-1].lm4coord[1]) * 0.5
                            if self.patch_tcs:
                                ctrlPoints[j][i].texcoord[0] = (
                                    4.0 * ctrlPoints[j][i].texcoord[0]
                                    - ctrlPoints[j][i+1].texcoord[0]
                                    - ctrlPoints[j][i-1].texcoord[0]) * 0.5
                                ctrlPoints[j][i].texcoord[1] = (
                                    4.0 * ctrlPoints[j][i].texcoord[1]
                                    - ctrlPoints[j][i+1].texcoord[1]
                                    - ctrlPoints[j][i-1].texcoord[1]) * 0.5

                if self.patch_lm_tcs:
                    # set new lightmap ids
                    vertices = set()
                    lightmap_id = []
                    lightmap_id2 = []
                    lightmap_id3 = []
                    lightmap_id4 = []
                    if bsp_surf.type != 2:
                        for i in range(int(bsp_surf.n_indexes)):
                            bsp_vert_index = (
                                bsp_surf.vertex +
                                bsp.lumps["drawindexes"]
                                [bsp_surf.index + i].offset)
                            # only alter selected vertices
                            if patched_vertices[bsp_vert_index]:
                                vertices.add(bsp_vert_index)
                                bsp_vert = (
                                    bsp.lumps["drawverts"][bsp_vert_index])
                                if (lightmapped_vertices[bsp_vert_index] and
                                   patch_lighting_type):
                                    lightmap_id.append(
                                        Helpers.get_lm_id(
                                            bsp_vert.lm1coord,
                                            lightmap_size,
                                            packed_lightmap_size))
                                    if bsp.lightmaps == 4:
                                        lightmap_id2.append(
                                            Helpers.get_lm_id(
                                                bsp_vert.lm2coord,
                                                lightmap_size,
                                                packed_lightmap_size))
                                        lightmap_id3.append(
                                            Helpers.get_lm_id(
                                                bsp_vert.lm3coord,
                                                lightmap_size,
                                                packed_lightmap_size))
                                        lightmap_id4.append(
                                            Helpers.get_lm_id(
                                                bsp_vert.lm4coord,
                                                lightmap_size,
                                                packed_lightmap_size))
                    else:
                        for i in range(bsp_surf.patch_width):
                            for j in range(bsp_surf.patch_height):
                                bsp_vert_index = (
                                    bsp_surf.vertex+j*bsp_surf.patch_width+i)
                                if patched_vertices[bsp_vert_index]:
                                    vertices.add(bsp_vert_index)
                                    bsp_vert = (
                                        bsp.lumps["drawverts"][bsp_vert_index])
                                    if (lightmapped_vertices[bsp_vert_index]
                                       and patch_lighting_type):
                                        lightmap_id.append(
                                            Helpers.get_lm_id(
                                                bsp_vert.lm1coord,
                                                lightmap_size,
                                                packed_lightmap_size))
                                        if bsp.lightmaps == 4:
                                            lightmap_id2.append(
                                                Helpers.get_lm_id(
                                                    bsp_vert.lm2coord,
                                                    lightmap_size,
                                                    packed_lightmap_size))
                                            lightmap_id3.append(
                                                Helpers.get_lm_id(
                                                    bsp_vert.lm3coord,
                                                    lightmap_size,
                                                    packed_lightmap_size))
                                            lightmap_id4.append(
                                                Helpers.get_lm_id(
                                                    bsp_vert.lm4coord,
                                                    lightmap_size,
                                                    packed_lightmap_size))

                    if len(vertices) > 0:
                        if len(lightmap_id) > 0:
                            current_lm_id = lightmap_id[0]
                            for i in lightmap_id:
                                if i != current_lm_id:
                                    self.report(
                                        {"WARNING"}, "Warning: Surface found "
                                        "with multiple lightmap assignments "
                                        "which is not supported! Surface will "
                                        "be stored as vertex lit!")
                                    lightmap_id[0] = -3
                                    break
                            if bsp.lightmaps == 4:
                                current_lm_id = lightmap_id2[0]
                                for i in lightmap_id2:
                                    if i != current_lm_id:
                                        lightmap_id2[0] = -3
                                        break
                                current_lm_id = lightmap_id3[0]
                                for i in lightmap_id3:
                                    if i != current_lm_id:
                                        lightmap_id3[0] = -3
                                        break
                                current_lm_id = lightmap_id4[0]
                                for i in lightmap_id4:
                                    if i != current_lm_id:
                                        lightmap_id4[0] = -3
                                        break

                            bsp_lm_index_0 = bsp_surf.lm_indexes
                            if bsp.lightmaps > 1:
                                bsp_lm_index_0 = bsp_surf.lm_indexes[0]

                            if patch_lighting_type or (
                                    bsp_lm_index_0 >= 0):
                                # bsp_surf.type = 1 #force using lightmaps
                                # for surfaces with less than 64 verticies
                                if bsp.lightmaps == 4:
                                    bsp_surf.lm_indexes[0] = lightmap_id[0]
                                    bsp_surf.lm_indexes[1] = lightmap_id2[0]
                                    bsp_surf.lm_indexes[2] = lightmap_id3[0]
                                    bsp_surf.lm_indexes[3] = lightmap_id4[0]
                                else:
                                    bsp_surf.lm_indexes = lightmap_id[0]

                        # unpack lightmap tcs
                        for i in vertices:
                            bsp_vert = bsp.lumps["drawverts"][i]
                            Helpers.unpack_lm_tc(
                                bsp_vert.lm1coord,
                                lightmap_size,
                                packed_lightmap_size)
                            bsp_vert.lm1coord[1] = 1.0 - bsp_vert.lm1coord[1]
                            if bsp.lightmaps == 4:
                                Helpers.unpack_lm_tc(
                                    bsp_vert.lm2coord,
                                    lightmap_size,
                                    packed_lightmap_size)
                                bsp_vert.lm2coord[1] = 1.0 - bsp_vert.lm2coord[1]
                                Helpers.unpack_lm_tc(
                                    bsp_vert.lm3coord,
                                    lightmap_size,
                                    packed_lightmap_size)
                                bsp_vert.lm3coord[1] = 1.0 - bsp_vert.lm3coord[1]
                                Helpers.unpack_lm_tc(
                                    bsp_vert.lm4coord,
                                    lightmap_size,
                                    packed_lightmap_size)
                                bsp_vert.lm4coord[1] = 1.0 - bsp_vert.lm4coord[1]
            self.report({"INFO"}, "Successful")
        # get number of lightmaps
        n_lightmaps = 0
        for bsp_surf in bsp.lumps["surfaces"]:
            if bsp.lightmaps == 1:
                if bsp_surf.lm_indexes > n_lightmaps:
                    n_lightmaps = bsp_surf.lm_indexes
                continue

            # handle lightmap ids with lightstyles
            for i in range(bsp.lightmaps):
                if bsp_surf.lm_indexes[i] > n_lightmaps:
                    n_lightmaps = bsp_surf.lm_indexes[i]

        # store lightmaps
        if self.patch_lightmaps:
            lightmap_image = bpy.data.images.get(self.lightmap_to_use)
            if lightmap_image is None:
                self.report(
                    {"ERROR"}, "Could not find selected lightmap atlas")
                return {'CANCELLED'}
            self.report({"INFO"}, "Storing Lightmaps...")
            success, message = QuakeLight.storeLighmaps(
                bsp,
                lightmap_image,
                n_lightmaps + 1,
                light_settings,
                not self.patch_external,
                self.patch_external_flip)
            self.report({"INFO"} if success else {"ERROR"}, message)

        # clear lightmap lump
        if self.patch_empty_lm_lump:
            bsp.lumps["lightmaps"].clear()

        # store lightgrid
        if self.patch_lightgrid:
            self.report({"INFO"}, "Storing Lightgrid...")
            success, message = QuakeLight.storeLightgrid(bsp, light_settings)
            self.report({"INFO"} if success else {"ERROR"}, message)

        # store vertex colors
        if self.patch_colors:
            self.report({"INFO"}, "Storing Vertex Colors...")
            success, message = QuakeLight.storeVertexColors(
                bsp, objs, light_settings, self.patch_colors)
            self.report({"INFO"} if success else {"ERROR"}, message)

        # write bsp
        bsp_bytes = bsp.to_bytes()

        name = self.filepath
        if self.create_backup is True:
            name = name.replace(".bsp", "") + "_data_patched.bsp"

        f = open(name, "wb")
        try:
            f.write(bsp_bytes)
        except Exception:
            self.report({"ERROR"}, "Failed writing: " + name)
            return {'CANCELLED'}
        f.close()

        return {'FINISHED'}


class Prepare_Lightmap_Baking(bpy.types.Operator):
    bl_idname = "q3.prepare_lm_baking"
    bl_label = "Prepare Lightmap Baking"
    bl_options = {"INTERNAL", "REGISTER"}

    def execute(self, context):

        if context.object.mode == "EDIT":
            bpy.ops.object.mode_set(mode='OBJECT')

        context.view_layer.objects.active = None
        for obj in context.scene.objects:
            obj.select_set(False)
            if obj.type != "MESH":
                continue

            mesh = obj.data
            if not (mesh.name.startswith("*") and (
                    obj.name in context.view_layer.objects)):
                continue

            context.view_layer.objects.active = obj
            obj.select_set(True)
            if "LightmapUV" in mesh.uv_layers:
                mesh.uv_layers["LightmapUV"].active = True

            group_map = {
                group.name: group.index for group in obj.vertex_groups}
            if "Lightmapped" not in group_map:
                continue
            lightmapped_indices = [vertex.index
                                   for vertex in mesh.vertices
                                   if group_map["Lightmapped"] in
                                   [vg.group for vg in vertex.groups]]
            for poly in mesh.polygons:
                lightmapped = False
                if poly.vertices[0] in lightmapped_indices:
                    lightmapped = True
                    for vert in poly.vertices:
                        if vert not in lightmapped_indices:
                            lightmapped = False
                            break
                mat_name = mesh.materials[poly.material_index].name
                if mat_name.endswith(".vertex") == (not lightmapped):
                    continue

                new_mat = None
                if mat_name.endswith(".vertex"):
                    new_mat = bpy.data.materials.get(mat_name[:-len(".vertex")])
                    if new_mat is None:
                        new_mat = mesh.materials[poly.material_index].copy()
                        new_mat.name = mat_name[:-len(".vertex")]
                        if "Baking Image" in new_mat.node_tree.nodes:
                            new_mat.node_tree.nodes["Baking Image"].image = bpy.data.images.get("$lightmap_bake")
                else:
                    new_mat = bpy.data.materials.get(mat_name+".vertex")
                    if new_mat is None:
                        new_mat = mesh.materials[poly.material_index].copy()
                        new_mat.name = mat_name+".vertex"
                        if "Baking Image" in new_mat.node_tree.nodes:
                            new_mat.node_tree.nodes["Baking Image"].image = bpy.data.images.get("$vertmap_bake")
                if new_mat is None:
                    continue
                if new_mat.name not in mesh.materials:
                    mesh.materials.append(new_mat)
                poly.material_index = mesh.materials.find(new_mat.name)

        for mat in bpy.data.materials:
            node_tree = mat.node_tree
            if node_tree is None:
                continue

            nodes = node_tree.nodes
            for node in nodes:
                node.select = False

            if "Baking Image" in nodes:
                nodes["Baking Image"].select = True
                nodes.active = nodes["Baking Image"]

        return {'FINISHED'}


class Store_Vertex_Colors(bpy.types.Operator):
    bl_idname = "q3.store_vertex_colors"
    bl_label = "Store Vertex Colors"
    bl_options = {"INTERNAL", "REGISTER"}

    def execute(self, context):
        objs = [obj for obj in context.selected_objects if obj.type == "MESH"]
        # TODO: handle lightsyles
        success, message = QuakeLight.bake_uv_to_vc(
            objs, "LightmapUV", "Color")
        if not success:
            self.report({"ERROR"}, message)
            return {'CANCELLED'}

        return {'FINISHED'}


def pack_image(name):
    image = bpy.data.images.get(name)
    if image is not None:
        if image.packed_file is None or image.is_dirty:
            image.pack()
        return True
    return False


class Create_Lightgrid(bpy.types.Operator):
    bl_idname = "q3.create_lightgrid"
    bl_label = "Create Lightgrid"
    bl_options = {"INTERNAL", "REGISTER"}

    def execute(self, context):
        if QuakeLight.create_lightgrid() is False:
            self.report({"ERROR"}, "BspInfo Node Group not found")
            return {'CANCELLED'}

        return {'FINISHED'}


class Convert_Baked_Lightgrid(bpy.types.Operator):
    bl_idname = "q3.convert_baked_lightgrid"
    bl_label = "Convert Baked Lightgrid"
    bl_options = {"INTERNAL", "REGISTER"}

    def execute(self, context):
        if QuakeLight.createLightGridTextures() is False:
            self.report({"ERROR"}, "Couldn't convert baked lightgrid textures")
            return {'CANCELLED'}
        images = ["$Vector", "$Ambient", "$Direct"]
        for image in images:
            if not pack_image(image):
                error = "Couldn't pack " + image + " image"
                self.report({"ERROR"}, error)

        return {'FINISHED'}


class Pack_Lightmap_Images(bpy.types.Operator):
    bl_idname = "q3.pack_lightmap_images"
    bl_label = "Pack Lightmap Images"
    bl_options = {"INTERNAL", "REGISTER"}

    def execute(self, context):
        images = ["$lightmap_bake", "$vertmap_bake"]
        for image in images:
            if not pack_image(image):
                error = "Couldn't pack " + image + " image"
                self.report({"ERROR"}, error)
        return {'FINISHED'}


class Q3_PT_EntExportPanel(bpy.types.Panel):
    bl_name = "Q3_PT_ent_panel"
    bl_label = "Export"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ID3 Entities"

    @classmethod
    def poll(self, context):
        if "id_tech_3_importer_preset" in context.scene:
            return (context.object is not None and (
                context.scene.id_tech_3_importer_preset == "EDITING"))
        return False

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(
            text="Here you can export all the entities in "
            "the scene to different filetypes")
        op = layout.operator("q3.export_ent", text="Export .ent")
        # op = layout.operator("q3.export_map", text="Export .map")
        # is it any different to .ent?
        op = layout.operator("q3.patch_bsp_ents", text="Patch .bsp Entities")


class Q3_PT_DataExportPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_data_export_panel"
    bl_label = "Patch BSP Data"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ID3 Data"

    def draw(self, context):
        layout = self.layout
        layout.label(text="1. Prepare your scene for baking")
        layout.separator()
        op = layout.operator("q3.prepare_lm_baking",
                             text="2. Prepare Lightmap Baking")
        layout.separator()
        layout.label(text='3. Keep the selection of objects and bake light:')
        layout.label(text='Bake Type: Diffuse only Direct and Indirect')
        layout.label(text='Margin: 1 px')
        layout.separator()
        op = layout.operator("q3.pack_lightmap_images",
                             text="4. Pack and Save Baked Images")
        layout.separator()
        layout.label(text='5. Denoise $lightmap_bake and $vertmap_bake (opt.)')
        layout.label(
            text='Make sure your Images you want to be baked are named')
        layout.label(text='$lightmap_bake and $vertmap_bake')
        layout.separator()
        op = layout.operator("q3.store_vertex_colors",
                             text="6. Preview Vertex Colors (opt.)")
        layout.separator()
        op = layout.operator("q3.create_lightgrid", text="7. Create Lightgrid")
        layout.separator()
        layout.label(text="8. Select the LightGrid object and bake light:")
        layout.label(text='Bake Type: Diffuse only Direct and Indirect')
        layout.label(text='Margin: 0 px!')
        layout.separator()
        op = layout.operator("q3.convert_baked_lightgrid",
                             text="9. Convert Baked Lightgrid")
        layout.separator()
        op = layout.operator("q3.patch_bsp_data", text="10. Patch .bsp Data")


class Reload_preview_shader(bpy.types.Operator):
    """Reload Shaders"""
    bl_idname = "q3mapping.reload_preview_shader"
    bl_label = "Reload Eevee Shaders"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        import_settings = Import_Settings(
            base_paths=get_base_paths(context, context.scene.id_tech_3_file_path),
            preset=Preset.PREVIEW.value,
            normal_map_option=prefs.normal_map_option,
        )

        # initialize virtual file system
        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        objs = [obj for obj in context.selected_objects if obj.type == "MESH"]
        QuakeShader.build_quake_shaders(VFS, import_settings, objs)

        return {'FINISHED'}


class Reload_render_shader(bpy.types.Operator):
    """Reload Shaders"""
    bl_idname = "q3mapping.reload_render_shader"
    bl_label = "Reload Cycles Shaders"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        import_settings = Import_Settings(
            base_paths=get_base_paths(context, context.scene.id_tech_3_file_path),
            preset=Preset.RENDERING.value,
            normal_map_option=prefs.normal_map_option,
        )

        # initialize virtual file system
        VFS = Q3VFS()
        for base_path in import_settings.base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        objs = [obj for obj in context.selected_objects if obj.type == "MESH"]
        QuakeShader.build_quake_shaders(VFS, import_settings, objs)

        return {'FINISHED'}


class FillAssetLibrary(bpy.types.Operator):
    bl_idname = "q3.fill_asset_lib"
    bl_label = "Fill asset library with models"
    bl_options = {"INTERNAL", "REGISTER"}
    def execute(self, context):
        if bpy.app.version < (3, 0, 0):
            return {'FINISHED'}

        log = []
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences

        asset_library_path = prefs.assetlibrary.replace("\\", "/")

        base_paths = get_base_paths(context)
        if len(base_paths) == 0:
            self.report({"ERROR"}, "No base path configured.")
            return {'CANCELLED'}
        # initialize virtual file system
        VFS = Q3VFS()
        for base_path in base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        reg = r"(.*?).md3$"
        md3_files = VFS.search(reg)
        md3_files = [f[1:] if f.startswith("/") else f for f in md3_files]

        cats_f = "{}/blender_assets.cats.txt".format(asset_library_path)
        os.makedirs(asset_library_path, exist_ok=True)
        a_categorys = {}
        add_version_to_cats = False
        if os.path.isfile(cats_f):
            with open(cats_f, "r") as f:
                for line in f.readlines():
                    if line.startswith(("#", "VERSION", "\n")):
                        continue
                    c_uuid, path, name = line.split(":")
                    a_categorys[path] = c_uuid
        else:
            add_version_to_cats = True

        for md3_file in md3_files:
            game_folder_struct = md3_file.split("/")
            current_path = "/".join(game_folder_struct[:-1])
            if current_path not in a_categorys:
                a_categorys[current_path] = None

        with open(cats_f, "a+") as f:
            if add_version_to_cats:
                f.write("VERSION 1\n")
            for cat in a_categorys:
                if a_categorys[cat] is None:
                    a_categorys[cat] = str(uuid.uuid4())
                    split_cat = cat.split("/")
                    f.write(":".join((a_categorys[cat], cat, split_cat[len(split_cat)-1])))
                    f.write("\n")

        imported_objects = []
        for md3_file in md3_files:
            game_folder_struct = md3_file.split("/")
            len_gfs = len(game_folder_struct)
            current_path = "/".join(game_folder_struct[:-1])

            collection = bpy.data.collections.get(game_folder_struct[len_gfs-2])
            if collection is None:
                collection = bpy.data.collections.new(game_folder_struct[len_gfs-2])
            if collection.name not in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.link(collection)
            layerColl = bpy.context.view_layer.layer_collection.children[collection.name]
            bpy.context.view_layer.active_layer_collection = layerColl
            layerColl.exclude = False

            if current_path not in a_categorys:
                print("Couldn't find category, woot?_?")
                continue

            obj_name = game_folder_struct[len_gfs-1][:-len(".md3")]
            try:
                imported_obj = MD3.ImportMD3Object(
                    VFS,
                    md3_file,
                    False,
                    False,
                    False)[0]
            except Exception:
                log.append("Failed importing {}".format(md3_file))
                continue
            
            if imported_obj is None:
                log.append("is None {}".format(md3_file))
                continue

            imported_objects.append(imported_obj)
            imported_obj.name = obj_name
            imported_obj.asset_mark()
            imported_obj.asset_data.catalog_id = a_categorys[current_path]
            if prefs.default_classname != "":
                imported_obj["classname"] = prefs.default_classname
                imported_obj.q3_dynamic_props.model = md3_file
                imported_obj["model"] = md3_file
            if prefs.default_spawnflags != "":
                spawnflags = int(prefs.default_spawnflags)
                imported_obj["spawnflags"] = spawnflags
                if spawnflags % 2 == 1:
                    imported_obj.q3_dynamic_props.b1 = True
                if spawnflags & 2 > 1:
                    imported_obj.q3_dynamic_props.b2 = True
                if spawnflags & 4 > 1:
                    imported_obj.q3_dynamic_props.b4 = True
                if spawnflags & 8 > 1:
                    imported_obj.q3_dynamic_props.b8 = True
                if spawnflags & 16 > 1:
                    imported_obj.q3_dynamic_props.b16 = True
                if spawnflags & 32 > 1:
                    imported_obj.q3_dynamic_props.b32 = True
                if spawnflags & 64 > 1:
                    imported_obj.q3_dynamic_props.b64 = True
                if spawnflags & 128 > 1:
                    imported_obj.q3_dynamic_props.b128 = True
                if spawnflags & 256 > 1:
                    imported_obj.q3_dynamic_props.b256 = True
                if spawnflags & 512 > 1:
                    imported_obj.q3_dynamic_props.b512 = True

        import_settings = Import_Settings()
        import_settings.base_paths=base_paths
        import_settings.bsp_name = ""
        import_settings.preset = "PREVIEW"

        QuakeShader.init_shader_system(None)
        QuakeShader.build_quake_shaders(
                VFS,
                import_settings,
                imported_objects)

        for imported_obj in imported_objects:
            imported_obj.asset_generate_preview()

        for collection in bpy.data.collections:
            layerColl = bpy.context.view_layer.layer_collection.children[collection.name]
            layerColl.exclude = True

        bpy.ops.wm.save_as_mainfile(filepath=prefs.assetlibrary+"/"+"md3_models.blend")

        for line in log:
            print(line)
        return {'FINISHED'}


class FillAssetLibraryEntities(bpy.types.Operator):
    bl_idname = "q3.fill_asset_lib_entities"
    bl_label = "Fill asset library with entities"
    bl_options = {"INTERNAL", "REGISTER"}
    def execute(self, context):
        if bpy.app.version < (3, 0, 0):
            return {'FINISHED'}

        log = []
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences

        asset_library_path = prefs.assetlibrary.replace("\\", "/")

        base_paths = get_base_paths(context)
        if len(base_paths) == 0:
            self.report({"ERROR"}, "No base path configured.")
            return {'CANCELLED'}
        
        # initialize virtual file system
        VFS = Q3VFS()
        for base_path in base_paths:
            VFS.add_base(base_path)
        VFS.build_index()

        cats_f = "{}/blender_assets.cats.txt".format(asset_library_path)
        os.makedirs(asset_library_path, exist_ok=True)
        a_categorys = {}
        add_version_to_cats = False
        if os.path.isfile(cats_f):
            with open(cats_f, "r") as f:
                for line in f.readlines():
                    if line.startswith(("#", "VERSION", "\n")):
                        continue
                    c_uuid, path, name = line.split(":")
                    a_categorys[path] = c_uuid
        else:
            add_version_to_cats = True

        # categories
        entities = get_current_entity_dict(context)
        if len(entities) == 0:
            self.report({"ERROR"}, "No gamepack found.")
            return {'CANCELLED'}

        for entity in entities:
            game_folder_struct = entity.split("_", 1)
            current_path = "Entities/" + "/".join(game_folder_struct[:-1])
            if current_path not in a_categorys:
                a_categorys[current_path] = None
        
        with open(cats_f, "a+") as f:
            if add_version_to_cats:
                f.write("VERSION 1\n")
            for cat in a_categorys:
                if a_categorys[cat] is None:
                    a_categorys[cat] = str(uuid.uuid4())
                    split_cat = cat.split("/")
                    f.write(":".join((a_categorys[cat], cat, split_cat[len(split_cat)-1])))
                    f.write("\n")

        entity_dict = get_current_entity_dict(context)
        imported_objects = []
        for entity in entities:
            game_folder_struct = entity.split("_", 1)
            len_gfs = len(game_folder_struct)
            current_path = "Entities/" + "/".join(game_folder_struct[:-1])

            collection = bpy.data.collections.get(game_folder_struct[len_gfs-2])
            if collection is None:
                collection = bpy.data.collections.new(game_folder_struct[len_gfs-2])
            if collection.name not in context.scene.collection.children:
                context.scene.collection.children.link(collection)
            layerColl = context.view_layer.layer_collection.children[collection.name]
            context.view_layer.active_layer_collection = layerColl
            layerColl.exclude = False

            if current_path not in a_categorys:
                print("Couldn't find category, woot?_?")
                continue

            mesh, vertex_groups = BlenderBSP.load_mesh(VFS, entities[entity]["Model"], 0, None)
            if mesh is None:
                log.append("is None {} {}".format(entity, entities[entity]["Model"]))
                mesh, vertex_groups = BlenderBSP.load_mesh(VFS, 'box', 0, None)
            imported_obj = bpy.data.objects.new(entity, mesh)
            if imported_obj is None:
                log.append("is None {}".format(entities[entity]))
                continue
            context.collection.objects.link(imported_obj)

            imported_obj["classname"] = entity
            if "Color" in entity_dict[entity]:
                color_info = [*entity_dict[entity]["Color"], 1.0]
                imported_obj.color = (
                    pow(color_info[0], 2.2),
                    pow(color_info[1], 2.2),
                    pow(color_info[2], 2.2),
                    pow(color_info[3], 2.2))
            if mesh.name == "box" and entity_dict[entity]["Model"] == "box":
                maxs = entity_dict[entity]["Maxs"]
                mins = entity_dict[entity]["Mins"]
                imported_obj.delta_scale[0] = (maxs[0] - mins[0]) / 8.0
                if imported_obj.delta_scale[0] == 0:
                    imported_obj.delta_scale[0] = 1.0
                else:
                    imported_obj.delta_scale[1] = (maxs[1] - mins[1]) / 8.0
                    imported_obj.delta_scale[2] = (maxs[2] - mins[2]) / 8.0
                    imported_obj.delta_location[0] = (maxs[0] + mins[0]) * 0.5
                    imported_obj.delta_location[1] = (maxs[1] + mins[1]) * 0.5
                    imported_obj.delta_location[2] = (maxs[2] + mins[2]) * 0.5

            imported_objects.append(imported_obj)
            imported_obj.asset_mark()
            imported_obj.asset_data.catalog_id = a_categorys[current_path]

        import_settings = Import_Settings()
        import_settings.base_paths=base_paths
        import_settings.bsp_name = ""
        import_settings.preset = "PREVIEW"

        QuakeShader.init_shader_system(None)
        QuakeShader.build_quake_shaders(
                VFS,
                import_settings,
                imported_objects)

        for imported_obj in imported_objects:
            imported_obj.asset_generate_preview()

        for collection in bpy.data.collections:
            layerColl = bpy.context.view_layer.layer_collection.children[collection.name]
            layerColl.exclude = True

        bpy.ops.wm.save_as_mainfile(filepath=prefs.assetlibrary+"/"+"entities.blend")

        for line in log:
            print(line)
        return {'FINISHED'}


class Q3_OP_Equi_to_box(bpy.types.Operator):
    bl_idname = "q3.equi_to_box"
    bl_label = "Make skybox from equirectangular"
    def execute(self, context):
        image = context.edit_image
        QuakeSky.make_sky_from_equirect(image)
        return {"FINISHED"}


class Q3_PT_Imagepanel(bpy.types.Panel):
    bl_idname = "Q3_PT_Imagepanel"
    bl_label = "ID3 Image"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "ID3 Mapping"

    def draw(self, context):
        layout = self.layout
        image = context.edit_image
        layout.label(text = image.name)
        lightmap_names = (
            "$lightmap",
            "$lightmap_bake",
        )
        if image.name in lightmap_names:
            layout.prop(context.scene, 'id_tech_3_lightmaps_per_row')
            layout.prop(context.scene, 'id_tech_3_lightmaps_per_column')
        elif image.source == "FILE" or image.source == "GENERATED":
            layout.operator("q3.equi_to_box")


class Q3_OP_Quick_emission_mat(bpy.types.Operator):
    bl_idname = "q3.quick_emission_mat"
    bl_label = "Make material emissive"
    def execute(self, context):
        mat = context.material
        if mat is None:
            return {"CANCELLED"}
        if mat.use_nodes is False:
            return {"CANCELLED"}
        nt = mat.node_tree
        nodes = nt.nodes
        for node in nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            
            if context.blend_data.version < (3, 4, 0):
                mix_node = nodes.new("ShaderNodeMixRGB")
                mix_node.use_clamp = True
                mix_node_keys = ("Color1", "Color2", "Color")
            else:
                mix_node = nt.nodes.new(type="ShaderNodeMix")
                mix_node.data_type = "RGBA"
                mix_node.clamp_result = True
                mix_node_keys = ("A", "B", "Result")
            mix_node.blend_type = 'MULTIPLY'
            mix_node.inputs[0].default_value = 1.0
            mix_node.location[0] += 2400
            mix_node.location[1] -= 300

            vm_node = nt.nodes.new(type="ShaderNodeVectorMath")
            vm_node.operation = "DOT_PRODUCT"
            vm_node.inputs[1].default_value = (0.333, 0.333, 0.333)
            vm_node.location[0] += 2000
            vm_node.location[1] -= 300

            m_node = nt.nodes.new(type="ShaderNodeMath")
            m_node.name = "Threshold Node"
            m_node.operation = "GREATER_THAN"
            m_node.use_clamp = True
            m_node.location[0] += 2200
            m_node.location[1] -= 300

            nt.links.new(vm_node.outputs["Value"], m_node.inputs["Value"])
            nt.links.new(m_node.outputs["Value"], mix_node.inputs[mix_node_keys[1]])

            input = node.inputs["Base Color"]
            for link in input.links:
                nt.links.new(link.from_node.outputs[0], vm_node.inputs[0])
                nt.links.new(link.from_node.outputs[0], mix_node.inputs[mix_node_keys[0]])

            if bpy.app.version >= (4, 0, 0):
                EMISSION_KEY = "Emission Color"
            else:
                EMISSION_KEY = "Emission"

            # emission scale node
            scale_node = nodes.get("EmissionScaleNode")
            if scale_node is None:
                scale_node = nodes.new(type="ShaderNodeGroup")
                scale_node.node_tree = ShaderNodes.Emission_Node.get_node_tree(None)
                scale_node.location[0] += 2700
                scale_node.location[1] -= 300
                scale_node.name = "EmissionScaleNode"
            nt.links.new(mix_node.outputs[mix_node_keys[2]], scale_node.inputs["Color"])
            nt.links.new(scale_node.outputs[0], node.inputs[EMISSION_KEY])
            if bpy.app.version >= (4, 0, 0):
                node.inputs["Emission Strength"].default_value = 1.0

        return {"FINISHED"}


class Q3_OP_Quick_simple_mat(bpy.types.Operator):
    bl_idname = "q3.quick_simple_mat"
    bl_label = "Make simple material"
    def execute(self, context):
        mat = context.material
        if mat is None:
            return {"CANCELLED"}
        if mat.use_nodes is False:
            return {"CANCELLED"}
        nt = mat.node_tree
        nodes = nt.nodes
        for node in nodes:
            if node.type == "BUMP":
                nodes.remove(node)
        skip_bump = False
        if "q3map_normalimage output" in [n.name for n in nodes]:
            skip_bump = True
        for node in nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            node.inputs["Roughness"].default_value = 0.5
            node.name = "Main Material"
            if skip_bump:
                continue
            bump_node = nt.nodes.new(type="ShaderNodeBump")
            bump_node.name = "Bump Node"
            bump_node.location = node.location
            bump_node.location[0] -= 400.0
            
            input = node.inputs["Base Color"]
            for link in input.links:
                nt.links.new(link.from_node.outputs[0], bump_node.inputs["Height"])
                nt.links.new(bump_node.outputs["Normal"], node.inputs["Normal"])
                bump_node.inputs["Distance"].default_value = 8.0
        return {"FINISHED"}


class Q3_OP_Quick_transparent_mat(bpy.types.Operator):
    bl_idname = "q3.quick_transparent_mat"
    bl_label = "Make current material transparent"
    def execute(self, context):
        mat = context.material
        if mat is None:
            return {"CANCELLED"}
        if mat.use_nodes is False:
            return {"CANCELLED"}
        mat.blend_method = 'CLIP'
        mat.shadow_method = 'CLIP'
        nt = mat.node_tree
        # materials can have multiple out nodes for eevee and cycles
        out_nodes = [node for node in nt.nodes if node.type == "OUTPUT_MATERIAL"]
        tp_nodes = [node for node in nt.nodes if node.type == "BSDF_TRANSPARENT"]
        if len(tp_nodes) == 0:
            tp_nodes.append(nt.nodes.new(type="ShaderNodeBsdfTransparent"))
        tp_nodes[0].inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
        for out in out_nodes:
            # link the output of the mix node with the current material output
            nt.links.new(tp_nodes[0].outputs[0], out.inputs[0])
        return {"FINISHED"}


class Q3_PT_Materialpanel(bpy.types.Panel):
    bl_idname = "Q3_PT_Materialpanel"
    bl_label = "ID3 Shader"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    def draw(self, context):
        layout = self.layout
        mat = context.material
        if mat is None:
            return
        layout.label(text = mat.name.split(".")[0])
        if "shader_file" in mat:
            layout.label(
                text = "found in: {} line: {}".format(
                    mat["shader_file"],
                    mat["first_line"]
                )
            )
        else:
            layout.label(
                text = "is not an explicit shader."
            )
        layout.separator()
        layout.operator("q3.quick_transparent_mat")
        layout.separator()
        layout.operator("q3.quick_simple_mat")
        if "Main Material" in mat.node_tree.nodes:
            roughness = mat.node_tree.nodes["Main Material"].inputs["Roughness"]
            layout.prop(roughness, "default_value", text="Roughness")
        if "Bump Node" in mat.node_tree.nodes:
            bump = mat.node_tree.nodes["Bump Node"].inputs["Distance"]
            layout.prop(bump, "default_value", text="Bump Distance")
        layout.separator()
        layout.operator("q3.quick_emission_mat")
        if "Threshold Node" in mat.node_tree.nodes:
            threshold = mat.node_tree.nodes["Threshold Node"].inputs[1]
            layout.prop(threshold, "default_value", text="Emission Threshold")
        if "EmissionScaleNode" in mat.node_tree.nodes:
            light = mat.node_tree.nodes["EmissionScaleNode"].inputs["Light"]
            layout.prop(light, "default_value", text="Light scale")