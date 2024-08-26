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


bl_info = {
    "name": "Import id Tech 3 BSP",
    "author": "SomaZ",
    "version": (0, 9, 96),
    "description": "Importer for id Tech 3 BSP maps",
    "blender": (3, 3, 0),
    "location": "File > Import-Export",
    "warning": "",
    "category": "Import-Export"
}


if "bpy" in locals():
    # Just do all the reloading here
    import importlib
    from . import idtech3lib
    importlib.reload(idtech3lib)
    from . import BlenderImage, Gamepacks, GridIcoSphere, ShaderNodes
    importlib.reload(BlenderImage)
    importlib.reload(Gamepacks)
    importlib.reload(GridIcoSphere)
    importlib.reload(ShaderNodes)
    from . import BlenderEntities, BlenderSurfaceFactory
    importlib.reload(BlenderEntities)
    importlib.reload(BlenderSurfaceFactory)
    from . import QuakeLight, MD3, TAN
    importlib.reload(QuakeLight)
    importlib.reload(MD3)
    importlib.reload(TAN)
    from . import QuakeSky
    importlib.reload(QuakeSky)
    from . import QuakeShader
    importlib.reload(QuakeShader)
    from . import BlenderBSP
    importlib.reload(BlenderBSP)
    from . import UI
    importlib.reload(UI)
else:
    import bpy
    from . import Gamepacks
    from . import idtech3lib
    from . import UI
import os


panel_cls = [
    (UI.Q3_PT_ShaderPanel, "ID3 Shaders"),
    (UI.Q3_PT_EntityPanel, "ID3 Entities"),
    (UI.Q3_PT_EntExportPanel, "ID3 Entities"),
    (UI.Q3_PT_PropertiesEntityPanel, "ID3 Entities"),
    (UI.Q3_PT_DescriptionEntityPanel, "ID3 Entities"),
    (UI.Q3_PT_EditEntityPanel, "ID3 Entities"),
    (UI.Q3_PT_DataExportPanel, "ID3 Data"),
]


def update_panels(self, context):
    for cls, catergory in panel_cls:
        if cls.is_registered:
            bpy.utils.unregister_class(cls)
            cls.bl_category = "ID3 Editing" if self.merge_id3_panels else catergory
            bpy.utils.register_class(cls)

    return True


# ------------------------------------------------------------------------
#    store properties in the user preferences
# ------------------------------------------------------------------------
class BspImportAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    base_path: bpy.props.StringProperty(
        name="Base path",
        description="Path to base folder",
        default="",
        subtype="DIR_PATH",
        maxlen=2048,
    )

    mod_path_0: bpy.props.StringProperty(
        name="Mod path",
        description="Path to a mod folder",
        default="",
        subtype="DIR_PATH",
        maxlen=2048,
    )

    mod_path_1: bpy.props.StringProperty(
        name="Additional mod path",
        description="Path to an addtional mod folder",
        default="",
        subtype="DIR_PATH",
        maxlen=2048,
    )

    merge_id3_panels: bpy.props.BoolProperty(
        name="Merge UI panels as 'ID3 Editing'",
        description="Merges the shader, data and patching panels into one panel instead",
        default=True,
        update=update_panels
    )

    default_classname: bpy.props.StringProperty(
        name="Asset classname",
        description="classname that is assigned to the imported assets per default",
        default="misc_model",
        maxlen=2048,
    )

    default_spawnflags: bpy.props.StringProperty(
        name="Asset spawnflags",
        description="spawnflags that are assigned to the imported assets per default",
        default="0",
        maxlen=2048,
    )

    normal_map_option: bpy.props.EnumProperty(
        name="Normal Map Import",
        description="Choose whether to import normal maps from shaders that use the "
                    "q3map_normalimage directive, and which normal format to be used "
                    "(by default, q3map2 uses the DirectX format)",
        default=idtech3lib.ImportSettings.NormalMapOption.DIRECTX.value,
        items=[
            (idtech3lib.ImportSettings.NormalMapOption.OPENGL.value, "OpenGL",
             "Import normal maps in OpenGL format", 0),
            (idtech3lib.ImportSettings.NormalMapOption.DIRECTX.value, "DirectX",
             "Import normal maps in DirectX format", 1),
            (idtech3lib.ImportSettings.NormalMapOption.SKIP.value, "Skip",
             "Skip normal map import", 2)
        ]
    )

    def gamepack_list_cb(self, context):
        file_path = bpy.utils.script_paths(
            subdir="addons/import_bsp/gamepacks/")[0]
        gamepack_files = []

        try:
            gamepack_files = sorted(f for f in os.listdir(file_path)
                                    if f.endswith(".json"))
        except Exception as e:
            print('Could not open gamepack files ' + ", error: " + str(e))

        gamepack_list = [(gamepack, gamepack.split(".")[0], "")
                         for gamepack in sorted(gamepack_files)]

        return gamepack_list

    def assetslibs_list_cb(self, context):
        if bpy.app.version >= (3, 0, 0):
            libs = context.preferences.filepaths.asset_libraries
            return [(lib.path, lib.name, "")
                    for lib in libs]
        else:
            return []

    assetlibrary: bpy.props.EnumProperty(
        items=assetslibs_list_cb,
        name="Asset Library",
        description="Asset library to use for packing models"
    )

    gamepack: bpy.props.EnumProperty(
        items=gamepack_list_cb,
        name="Gamepack",
        description="List of available gamepacks"
    )

    gamepack_name: bpy.props.StringProperty(
        name="New Gamepack",
        description="Name of the new empty gamepack",
        default="Empty",
        maxlen=2048,
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "base_path")
        row = layout.row()
        row.prop(self, "mod_path_0")
        row = layout.row()
        row.prop(self, "mod_path_1")
        layout.separator()
        row = layout.row()
        row.prop(self, "normal_map_option")
        row = layout.row()
        row.prop(self, "merge_id3_panels")
        layout.separator()
        row = layout.row()
        row.prop(self, "gamepack")
        row.operator("q3.open_gamepack", text="", icon="TEXT").name = self.gamepack
        row.operator("q3.delete_gamepack", text="", icon="X").name = self.gamepack
        row = layout.row()
        row.prop(self, "gamepack_name")
        row.operator("q3.add_new_gamepack", text="", icon="PLUS").name = self.gamepack_name
        row = layout.row()
        row.operator("q3.import_def_gamepack").name = self.gamepack_name
        row = layout.row()
        
        if bpy.app.version >= (3, 0, 0):
            layout.separator()
            row = layout.row()
            row.prop(self, "default_classname")
            row = layout.row()
            row.prop(self, "default_spawnflags")
            row = layout.row()
            row.prop(self, "assetlibrary")
            row = layout.row()
            row.operator("q3.fill_asset_lib", text="Fill with models")
            row.operator("q3.fill_asset_lib_entities", text="Fill with entities")


classes = (Gamepacks.Open_gamepack,
           Gamepacks.Add_new_gamepack,
           Gamepacks.Import_from_def,
           Gamepacks.Delete_gamepack,
           BspImportAddonPreferences,
           UI.Import_ID3_BSP,
           UI.Import_MAP,
           UI.Import_ID3_MD3,
           UI.Import_ID3_TIK,
           UI.Export_ID3_MD3,
           UI.Export_ID3_TIK,
           UI.Reload_preview_shader,
           UI.Reload_render_shader,
           UI.DynamicProperties,
           UI.Add_property,
           UI.Del_property,
           UI.Add_entity_definition,
           UI.Add_key_definition,
           UI.Update_entity_definition,
           UI.ExportEnt,
           UI.PatchBspEntities,
           UI.PatchBspData,
           UI.Prepare_Lightmap_Baking,
           UI.Store_Vertex_Colors,
           UI.Create_Lightgrid,
           UI.Convert_Baked_Lightgrid,
           UI.Pack_Lightmap_Images,
           UI.FillAssetLibrary,
           UI.FillAssetLibraryEntities,
           UI.Q3_OP_Equi_to_box,
           UI.Q3_PT_Imagepanel,
           UI.Q3_OP_Quick_emission_mat,
           UI.Q3_OP_Quick_simple_mat,
           UI.Q3_OP_Quick_transparent_mat,
           UI.Q3_PT_Materialpanel,
           )


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(UI.menu_func_map_import)
    bpy.types.TOPBAR_MT_file_import.append(UI.menu_func_bsp_import)
    bpy.types.TOPBAR_MT_file_import.append(UI.menu_func_md3_import)
    bpy.types.TOPBAR_MT_file_import.append(UI.menu_func_tik_import)
    bpy.types.TOPBAR_MT_file_export.append(UI.menu_func_md3_export)
    bpy.types.TOPBAR_MT_file_export.append(UI.menu_func_tik_export)
    bpy.types.Object.q3_dynamic_props = bpy.props.PointerProperty(
        type=UI.DynamicProperties)
    bpy.types.Scene.id_tech_3_importer_preset = bpy.props.StringProperty(
        name="id3 importer preset",
        description="Last used importer preset")
    bpy.types.Scene.id_tech_3_file_path = bpy.props.StringProperty(
        name="ID3 file path",
        description="Full path to the last imported id tech 3 File")
    bpy.types.Scene.id_tech_3_lightmaps_per_row = bpy.props.IntProperty(
        name="Lightmaps per row",
        description=(
            "How many lightmaps are packed in one row of the lightmap atlas"
            ))
    bpy.types.Scene.id_tech_3_lightmaps_per_column = bpy.props.IntProperty(
        name="Lightmaps per column",
        description=(
            "How many lightmaps are packed in one column of the lightmap atlas"
            ))
    bpy.types.Scene.new_id_tech_3_prop_name = bpy.props.StringProperty(
        name="New Property",
        default="",
        description=(
            "Name for a new custom property"
            ))
    
    addon_name = __name__.split('.')[0]
    prefs = bpy.context.preferences.addons[addon_name].preferences
    for cls, catergory in panel_cls:
        if cls.is_registered:
            bpy.utils.unregister_class(cls)
        cls.bl_category = "ID3 Editing" if prefs.merge_id3_panels else catergory
        bpy.utils.register_class(cls)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(UI.menu_func_map_import)
    bpy.types.TOPBAR_MT_file_import.remove(UI.menu_func_bsp_import)
    bpy.types.TOPBAR_MT_file_import.remove(UI.menu_func_md3_import)
    bpy.types.TOPBAR_MT_file_import.remove(UI.menu_func_tik_import)
    bpy.types.TOPBAR_MT_file_export.remove(UI.menu_func_md3_export)
    bpy.types.TOPBAR_MT_file_export.remove(UI.menu_func_tik_export)
    for cls in classes:
        bpy.utils.unregister_class(cls)
    for cls, catergory in panel_cls:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()