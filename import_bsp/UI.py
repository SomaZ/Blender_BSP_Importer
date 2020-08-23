#----------------------------------------------------------------------------#
#TODO:  refactor loading bsp files and md3 files, right now its a mess o.O
#TODO:  Fix reimporting model when only the zoffset is different
#       check if model already loaded, make a copy of it, replace all the 
#       material names with new zoffset
#----------------------------------------------------------------------------#

import imp

if "bpy" not in locals():
    import bpy
    
if "ImportHelper" not in locals():
    from bpy_extras.io_utils import ImportHelper
if "ExportHelper" not in locals():
    from bpy_extras.io_utils import ExportHelper
    
if "BspClasses" in locals():
    imp.reload( BspClasses )
else:
    from . import BspClasses
    
if "BspGeneric" in locals():
    imp.reload( BspGeneric )
else:
    from . import BspGeneric
    
if "Entities" in locals():
    imp.reload( Entities )
else:
    from . import Entities
    
if "MD3" in locals():
    imp.reload( MD3 )
else:
    from . import MD3
    
if "QuakeShader" in locals():
    imp.reload( QuakeShader )
else:
    from . import QuakeShader
    
if "QuakeLight" in locals():
    imp.reload( QuakeLight )
else:
    from . import QuakeLight
    
if "StringProperty" not in locals():
    from bpy.props import StringProperty
    
if "BoolProperty" not in locals():
    from bpy.props import BoolProperty
    
if "EnumProperty" not in locals():
    from bpy.props import EnumProperty
    
if "IntProperty" not in locals():
    from bpy.props import IntProperty
    
if "PropertyGroup" not in locals():
    from bpy.types import PropertyGroup
    
if "struct" not in locals():
    import struct
    
if "os" not in locals():
    import os
    
if "Parsing" in locals():
    imp.reload( Parsing )
else:
    from .Parsing import *
    
from mathutils import Vector
    
#empty class for now, we will see what to do with it
class ImportSettings:
    pass

class Import_ID3_BSP(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id3_bsp"
    bl_label = "Import ID3 engine BSP (.bsp)"
    filename_ext = ".bsp"
    filter_glob : StringProperty(default="*.bsp", options={'HIDDEN'})

    filepath : StringProperty(name="File Path", description="File path used for importing the BSP file", maxlen= 1024, default="")
    preset : EnumProperty(name="Import preset", description="You can select wether you want to import a bsp for editing, rendering, or previewing.", default='PREVIEW', items=[
            ('PREVIEW', "Preview", "Trys to build eevee shaders, imports all misc_model_statics when available", 0),
            ('EDITING', "Entity Editing", "Trys to build eevee shaders, imports all entitys", 1),
            ('RENDERING', "Rendering", "Trys to build fitting cycles shaders, only imports visable enities", 2),
            ('BRUSHES', "Shadow Brushes", "Imports Brushes as shadow casters", 3),
        ])
    subdivisions : IntProperty(name="Patch subdivisions", description="How often a patch is subdivided at import", default=2)
    min_atlas_size : EnumProperty(name="Minimum Lightmap atlas size", description="Sets the minimum lightmap atlas size", default='128', items=[
            ('128', "128", "128x128", 0),
            ('256', "256", "256x256", 1),
            ('512', "512", "512x512", 2),
            ('1024', "1024", "1024x1024", 3),
            ('2048', "2048", "2048x2048", 4),
        ])

    def execute(self, context):
        addon_name = __name__.split('.')[0]
        self.prefs = context.preferences.addons[addon_name].preferences
        
        fixed_base_path = self.prefs.base_path
        if not fixed_base_path.endswith('/'):
            fixed_base_path = fixed_base_path + '/'
        
        #trace some things like paths and lightmap size
        import_settings = ImportSettings()
        import_settings.base_path = fixed_base_path
        import_settings.shader_dirs = "shaders/", "scripts/"
        import_settings.bsp_name = ""
        import_settings.preset = self.properties.preset
        import_settings.subdivisions = self.properties.subdivisions
        import_settings.packed_lightmap_size = int(self.min_atlas_size)
        import_settings.log = []
        import_settings.log.append("----import_scene.ja_bsp----")
        import_settings.filepath = self.filepath
        
        #scene information
        context.scene.id_tech_3_importer_preset = self.preset
        if self.preset != "BRUSHES":
            context.scene.id_tech_3_bsp_path = self.filepath
        
        BspClasses.ImportBSP(import_settings)
        
        #set world color to black to remove additional lighting
        background = context.scene.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs[0].default_value = 0,0,0,1
        else:
            import_settings.log.append("WARNING: Could not set world color to black.")
        
        if self.properties.preset == "BRUSHES":
            context.scene.cycles.transparent_max_bounces = 32
        if self.properties.preset == "RENDERING":
            context.scene.render.engine = "CYCLES"
            
        #for line in import_settings.log:
        #    print(line)
            
        return {'FINISHED'}
    
class Import_ID3_MD3(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id3_md3"
    bl_label = "Import ID3 engine MD3 (.md3)"
    filename_ext = ".md3"
    filter_glob : StringProperty(default="*.md3", options={'HIDDEN'})

    filepath : StringProperty(name="File Path", description="File path used for importing the BSP file", maxlen= 1024, default="")
    import_tags : BoolProperty(name="Import Tags", description="Whether to import the md3 tags or not", default = True )
    def execute(self, context):
        addon_name = __name__.split('.')[0]
        self.prefs = context.preferences.addons[addon_name].preferences
        
        fixed_base_path = self.prefs.base_path
        if not fixed_base_path.endswith('/'):
            fixed_base_path = fixed_base_path + '/'
        
        #trace some things like paths and lightmap size
        import_settings = ImportSettings()
        import_settings.base_path = fixed_base_path
        import_settings.shader_dirs = "shaders/", "scripts/"
        import_settings.bsp_name = ""
        import_settings.preset = "PREVIEW"
        import_settings.filepath = self.filepath
        
        fixed_filepath = self.filepath.replace("\\", "/")
        
        objs = MD3.ImportMD3Object(fixed_filepath, self.import_tags)
        QuakeShader.build_quake_shaders(import_settings, objs)
        
        return {'FINISHED'}
    
class Export_ID3_MD3(bpy.types.Operator, ExportHelper):
    bl_idname = "export_scene.id3_md3"
    bl_label = "Export ID3 engine MD3 (.md3)"
    filename_ext = ".md3"
    filter_glob : StringProperty(default="*.md3", options={'HIDDEN'})

    filepath : StringProperty(name="File Path", description="File path used for importing the BSP file", maxlen= 1024, default="")
    only_selected : BoolProperty(name = "Export only selected", description="Exports only selected Objects", default=False)
    individual : BoolProperty(name="Local space coordinates", description="Uses every models local space coordinates instead of the world space")
    start_frame : IntProperty(name="Start Frame", description="First frame to export", default = 0, min = 0)
    end_frame : IntProperty(name="End Frame", description="Last frame to export", default = 1, min = 1)
    def execute(self, context):
        objects = context.scene.objects
        if self.only_selected:
            objects = context.selected_objects
            
        frame_list = range(self.start_frame, max(self.end_frame, self.start_frame) + 1)
        status = MD3.ExportMD3(self.filepath, objects, frame_list, self.individual)
        if status[0]:
            return {'FINISHED'}
        else:
            self.report({"ERROR"}, status[1])
            return {'CANCELLED'}
        
def menu_func_bsp_import(self, context):
    self.layout.operator(Import_ID3_BSP.bl_idname, text="ID3 BSP (.bsp)")
    
def menu_func_md3_import(self, context):
    self.layout.operator(Import_ID3_MD3.bl_idname, text="ID3 MD3 (.md3)")
    
def menu_func_md3_export(self, context):
    self.layout.operator(Export_ID3_MD3.bl_idname, text="ID3 MD3 (.md3)")
    
flag_mapping = {
    1 : "b1",
    2 : "b2",
    4 : "b4",
    8 : "b8",
    16 : "b16",
    32 : "b32",
    64 : "b64",
    128 : "b128",
    256 : "b256",
    512 : "b512",
}

class Del_property(bpy.types.Operator):
    bl_idname = "q3.del_property"
    bl_label = "Remove custom property"
    bl_options = {"UNDO","INTERNAL","REGISTER"}
    name : StringProperty()
    def execute(self, context):
        obj = bpy.context.active_object
        if self.name in obj:
            del obj[self.name]
            rna_ui = obj.get('_RNA_UI')
            if rna_ui is not None:
                del rna_ui[self.name]
        return {'FINISHED'}

type_matching = {   "STRING"    : "NONE",
                    "COLOR"     : "COLOR_GAMMA",
                    "COLOR255"  : "COLOR_GAMMA",
                    "INT"       : "NONE",
                    "FLOAT"     : "NONE",
}
default_values = {  "STRING" : "",
                    "COLOR"  : [0.0, 0.0, 0.0],
                    "COLOR255"  : [0.0, 0.0, 0.0],
                    "INT"  : 0,
                    "FLOAT"  : 0.0,
}

class Add_property(bpy.types.Operator):
    bl_idname = "q3.add_property"
    bl_label = "Add custom property"
    bl_options = {"UNDO","INTERNAL","REGISTER"}
    name : StringProperty()
    def execute(self, context):
        ob = bpy.context.active_object
        key = self.name
        
        if key == "classname":
            ob["classname"] = ""
            return {'FINISHED'}
        
        Dict = Entities.Dict
        if self.name not in ob:
            default = ""
            
            rna_ui = ob.get('_RNA_UI')
            if rna_ui is None:
                ob['_RNA_UI'] = {}
                rna_ui = ob['_RNA_UI']
            
            descr_dict = {}
            if ob["classname"].lower() in Dict:
                if key.lower() in Dict[ob["classname"].lower()]["Keys"]:
                    if "Description" in Dict[ob["classname"].lower()]["Keys"][key.lower()]:
                        descr_dict["description"] = Dict[ob["classname"].lower()]["Keys"][key.lower()]["Description"]
                    if "Type" in Dict[ob["classname"].lower()]["Keys"][key.lower()]:
                        descr_dict["subtype"] = type_matching[Dict[ob["classname"].lower()]["Keys"][key.lower()]["Type"].upper()]
                        default = default_values[Dict[ob["classname"].lower()]["Keys"][key.lower()]["Type"].upper()]
            
            ob[self.name] = default
            rna_ui[key.lower()] = descr_dict
        return {'FINISHED'}
    
class Add_entity_definition(bpy.types.Operator):
    bl_idname = "q3.add_entity_definition"
    bl_label = "Update entity definition"
    bl_options = {"INTERNAL","REGISTER"}
    name : StringProperty()
    
    def execute(self, context):
        obj = bpy.context.active_object
        new_entry = {   "Color" : [0.0, 0.5, 0.0],
                        "Mins": [-8, -8, -8],
                        "Maxs": [8, 8, 8],
                        "Model": "box",
                        "Describtion" : "NOT DOCUMENTED YET",
                        "Spawnflags": {},
                        "Keys": {},
                    }

        Entities.Dict[self.name] = new_entry
        Entities.save_gamepack(Entities.Dict, context.scene.id_tech_3_settings.gamepack)
        return {'FINISHED'}
    
class Add_key_definition(bpy.types.Operator):
    bl_idname = "q3.add_key_definition"
    bl_label = "Update entity definition"
    bl_options = {"INTERNAL","REGISTER"}
    name : StringProperty()
    
    def execute(self, context):
        obj = bpy.context.active_object
        
        if self.name != "":
            key = self.name
        else:
            scene = context.scene
            if "id_tech_3_settings" in scene:
                key = scene.id_tech_3_settings.new_prop_name
            else:
                print("Couldn't find new property name :(\n")
                return
            
        if "classname" in obj:
            classname = obj["classname"]
            if classname.lower() in Entities.Dict:
                if key not in Entities.Dict[classname.lower()]["Keys"]:
                    Entities.Dict[classname.lower()]["Keys"][key] = { "Type" : "STRING",
                                                                            "Description": "NOT DOCUMENTED YET"}
                    Entities.save_gamepack(Entities.Dict, context.scene.id_tech_3_settings.gamepack)
        return {'FINISHED'}

type_save_matching = {  "NONE"    : "STRING",
                        "COLOR_GAMMA" : "COLOR",
                        "COLOR" : "COLOR",
}

class Update_entity_definition(bpy.types.Operator):
    bl_idname = "q3.update_entity_definition"
    bl_label = "Update entity definition"
    bl_options = {"INTERNAL","REGISTER"}
    name : StringProperty()
    
    def execute(self, context):
        obj = bpy.context.active_object
        
        rna_ui = obj.get('_RNA_UI')
        if rna_ui is None:
            obj['_RNA_UI'] = {}
            rna_ui = obj['_RNA_UI']

        if self.name in Entities.Dict:
            ent = Entities.Dict[self.name]
            for key in rna_ui.to_dict():
                if key in ent["Keys"] and key in rna_ui:
                    if "description" in rna_ui[key]:
                        ent["Keys"][key]["Description"] = rna_ui[key]["description"]
                    if "subtype" in rna_ui[key]:
                        ent["Keys"][key]["Type"] = type_save_matching[rna_ui[key]["subtype"]]
                        
            Entities.save_gamepack(Entities.Dict, context.scene.id_tech_3_settings.gamepack)

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
        
def update_model(self, context):
    obj = bpy.context.active_object
    if obj is None:
        return
    
    if "model2" in obj:
        obj["model2"] = obj.q3_dynamic_props.model.split(".")[0] + ".md3"
        model_name = obj["model2"]
    elif "model" in obj:
        obj["model"] = obj.q3_dynamic_props.model.split(".")[0] + ".md3"
        model_name = obj["model"]
    else:
        return
        
    if obj.data.name == obj.q3_dynamic_props.model.split(".")[0]:
        return
    
    model_name = model_name.replace("\\", "/").lower()
    if model_name.endswith(".md3"):
        model_name = model_name[:-len(".md3")]
    
    mesh_name = guess_model_name(model_name)
    
    if mesh_name in bpy.data.meshes:
        obj.data = bpy.data.meshes[mesh_name]
        obj.q3_dynamic_props.model = obj.data.name
    else:
        zoffset = 0
        if "zoffset" in obj:
            zoffset = int(obj["zoffset"])
        
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        
        import_settings = ImportSettings()
        import_settings.base_path = prefs.base_path
        if not import_settings.base_path.endswith('/'):
            import_settings.base_path = import_settings.base_path + '/'
        import_settings.shader_dirs = "shaders/", "scripts/"
        import_settings.preset = 'PREVIEW'
        
        if model_name.startswith("models/"):
            model_name = import_settings.base_path + model_name
            
        obj.data = MD3.ImportMD3(model_name + ".md3", zoffset, False)
        if obj.data != None:
            obj.q3_dynamic_props.model = obj.data.name
            
            QuakeShader.build_quake_shaders(import_settings, [obj])
        
        
#Properties like spawnflags and model 
class DynamicProperties(PropertyGroup):
    b1 : BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b2 : BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b4 : BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b8 : BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b16: BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b32: BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b64: BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b128:BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b256:BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    b512:BoolProperty(
         name = "",
         default = False,
         update=update_spawn_flag
         )
    model:StringProperty(
        name = "Model",
        default = "EntityBox",
        update=update_model,
        subtype= "FILE_PATH"
        )
        
#Properties like spawnflags and model 
class SceneProperties(PropertyGroup):
    
    def gamepack_list_cb(self, context):
        file_path = bpy.utils.script_paths("addons/import_bsp/gamepacks/")[0]
        gamepack_files = []
        
        try:
            gamepack_files = sorted(f for f in os.listdir(file_path)
                                    if f.endswith(".json"))
        except Exception as e:
            print('Could not open gamepack files ' + ", error: " + str(e))
            
        gamepack_list = [(gamepack, gamepack.split(".")[0], "")
                       for gamepack in sorted(gamepack_files)]
        
        return gamepack_list
    
    new_prop_name: StringProperty(
        name = "New Property",
        default = "",
        )
    gamepack: EnumProperty(
        items=gamepack_list_cb,
        name="Gamepack",
        description="List of available gamepacks"
        )
    
#Panels
class Q3_PT_ShaderPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_shader_panel"
    bl_label = "Shaders"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Shaders"
    def draw(self, context):
        layout = self.layout
        
        scene = context.scene
        
        row = layout.row()
        row.scale_y = 1.0
        row.operator("q3mapping.reload_preview_shader")
        row = layout.row()
        row.operator("q3mapping.reload_render_shader")
        layout.separator()
        
        lg_group = bpy.data.node_groups.get("LightGrid")
        if lg_group != None:
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
        if emission_group != None:
            col = layout.column()
            if "Emission scale" in emission_group.nodes:
                scale = emission_group.nodes["Emission scale"].outputs[0]
                col.prop(scale, "default_value", text="Shader Emission Scale")
        
        
class Q3_PT_EntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_entity_panel"
    bl_label = "Selected Entity"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Entities"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = bpy.context.active_object
        
        if obj == None:
            return
        
        #layout.prop(context.scene.id_tech_3_settings,"gamepack")
        layout.label(text=context.scene.id_tech_3_settings.gamepack.split(".")[0])
        
        if "classname" in obj:
            classname = obj["classname"].lower()
            layout.prop(obj, '["classname"]')
        else:
            op = layout.operator("q3.add_property", text="Add classname").name = "classname"
            
class Q3_PT_PropertiesEntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_properties_entity_panel"
    bl_parent_id = "Q3_PT_entity_panel"
    bl_label = "Entity Properties"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Entities"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = bpy.context.active_object
        
        if obj == None:
            return
        
        filtered_keys = ["classname", "spawnflags", "origin", "angles", "angle"]
        
        if "classname" in obj:
            classname = obj["classname"].lower()
            if classname in Entities.Dict:
                ent = Entities.Dict[classname]
                
                box = None
                #check all the flags
                for flag in ent["Spawnflags"].items():
                    if box == None:
                        box = layout.box()
                    box.prop(obj.q3_dynamic_props, flag_mapping[flag[1]["Bit"]], text = flag[0])
                    
                #now check all the keys
                supported = None
                unsupported = None
                keys = ent["Keys"]
                for prop in obj.keys():
                    # only show generic properties and filter 
                    if prop.lower() not in filtered_keys and not hasattr(obj[prop], "to_dict"):
                        if prop.lower() == "model" and "model2" not in obj:
                            if supported == None:
                                supported = layout.box()
                            row = supported.row()
                            row.prop(obj.q3_dynamic_props, "model", text="model")
                            row.operator("q3.del_property", text="", icon="X").name = prop
                            continue
                        if prop.lower() == "model2":
                            if supported == None:
                                supported = layout.box()
                            row = supported.row()
                            row.prop(obj.q3_dynamic_props, "model", text="model2")
                            row.operator("q3.del_property", text="", icon="X").name = prop
                            continue
                        
                        if prop.lower() in keys:
                            if supported == None:
                                supported = layout.box()
                            row = supported.row()
                            row.prop(obj, '["' + prop + '"]')
                            row.operator("q3.del_property", text="", icon="X").name = prop
                        else:
                            if unsupported == None:
                                unsupported = layout.box()
                                unsupported.label(text = "Unknown Properties:")
                            row = unsupported.row()
                            row.prop(obj, '["' + prop + '"]')
                            row.operator("q3.del_property", text="", icon="X").name = prop
                for key in keys:
                    test_key = obj.get(key.lower())
                    if test_key == None:
                        if supported == None:
                            supported = layout.box()
                        row = supported.row()
                        op = row.operator("q3.add_property", text="Add " + str(key)).name = key
            else:
                layout.label(text = "Unknown entity")
                layout.label(text = 'You can add it via "Edit Entity Definitions"')
            
class Q3_PT_DescribtionEntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_describtion_entity_panel"
    bl_parent_id = "Q3_PT_entity_panel"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Entity Describtion"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Entities"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = bpy.context.active_object
        
        if obj == None:
            return
        
        if "classname" in obj:
            classname = obj["classname"].lower()
            if classname in Entities.Dict:
                ent = Entities.Dict[classname]
                for line in ent["Describtion"]:
                    layout.label(text= line)
            else:
                layout.label(text = "Unknown entity")
                layout.label(text = 'You can add it via "Edit Entity Definitions"')
                
class Q3_PT_EditEntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_edit_entity_panel"
    bl_parent_id = "Q3_PT_entity_panel"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Edit Entity Definitions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Entities"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = bpy.context.active_object
        
        if obj == None:
            return
        
        filtered_keys = ["classname", "spawnflags", "origin", "angles", "angle"]
        
        if "classname" in obj:
            classname = obj["classname"].lower()
            # classname in dictionary?
            if classname not in Entities.Dict:
                layout.operator("q3.add_entity_definition", text="Add " + obj["classname"].lower() + " to current Gamepack").name = obj["classname"].lower()
            else:
                ent = Entities.Dict[classname]
                keys = ent["Keys"]
                for prop in obj.keys():
                    if prop.lower() not in filtered_keys and not hasattr(obj[prop], "to_dict"):
                        if prop.lower() not in keys:
                            op = layout.operator("q3.add_key_definition", text="Add " + str(prop.lower()) + " to entity definition").name = prop.lower()
                            
                row = layout.row()
                row.prop(context.scene.id_tech_3_settings, 'new_prop_name')
                row.operator("q3.add_key_definition", text="" , icon="PLUS").name = ""
                
                layout.separator()
                layout.operator("q3.update_entity_definition").name = classname
                
                
def GetEntityStringFromScene():
    filtered_keys = ["_rna_ui", "q3_dynamic_props"]
    worldspawn = []
    entities = []
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and "classname" in obj:
            
            #only update position for now, I have no idea how rotations are handled ingame
            zero_origin = Vector([0.0, 0.0, 0.0])
            if obj.location != zero_origin:
                if obj.location[0].is_integer() and obj.location[1].is_integer() and obj.location[2].is_integer():
                    obj["origin"] = [int(obj.location[0]), int(obj.location[1]), int(obj.location[2])]
                else:
                    obj["origin"] = [obj.location[0], obj.location[1], obj.location[2]]
            
            lines = []
            lines.append("{")
            for key in obj.keys():
                if key.lower() not in filtered_keys and not hasattr(obj[key], "to_dict"):
                    string = ""
                    string = str(obj[key])
                    #meeeeh nooooo, find better way!
                    if string.startswith("<bpy id property array"):
                        string = ""
                        for i in obj[key].to_list():
                            string += str(i) + " "
                    lines.append("\"" + str(key) + "\" \"" + string.strip() + "\"")
            lines.append("}")
            
            if obj["classname"] == "worldspawn":
                worldspawn = lines
            else:
                entities.append(lines)
    
    out_str = ""
    for line in worldspawn:
        out_str += line + "\n"
    for entity in entities:
        for line in entity:
            out_str += line + "\n"
    out_str += "\0"
    return out_str


class ExportEnt(bpy.types.Operator, ExportHelper):
    bl_idname = "q3.export_ent"
    bl_label = "Export to .ent file"
    bl_options = {"INTERNAL","REGISTER"}
    filename_ext = ".ent"
    filter_glob : StringProperty(default="*.ent", options={'HIDDEN'})
    filepath : bpy.props.StringProperty(name="File", description="Where to write the .ent file", maxlen= 1024, default="")
    
    def execute(self, context):
        entities = GetEntityStringFromScene()
        
        f = open(self.filepath, "w")
        try:
            f.write(entities)
        except:
            print("Failed writing: " + self.filepath)
            
        f.close()
        return {'FINISHED'}

class PatchBspEntities(bpy.types.Operator, ExportHelper):
    bl_idname = "q3.patch_bsp_ents"
    bl_label = "Patch entities in existing .bsp"
    bl_options = {"INTERNAL","REGISTER"}
    filename_ext = ".bsp"
    filter_glob : StringProperty(default="*.bsp", options={'HIDDEN'})
    filepath : StringProperty(name="File", description="Which .bsp file to patch", maxlen= 1024, default="")
    create_backup : BoolProperty(name="Append a suffix to the output file (don't overwrite original file)", default = True)
    def execute(self, context):
        
        bsp = BspClasses.BSP(self.filepath)
        
        #exchange entity lump
        entities = GetEntityStringFromScene()
        bsp.lumps["entities"].data = [BspClasses.entity([bytes(c, "ascii")]) for c in entities]
        
        #write bsp
        bsp_bytes = bsp.to_bytes()
        
        name = self.filepath
        if self.create_backup == True:
            name = name.replace(".bsp","") + "_ent_patched.bsp"
        
        f = open(name, "wb")
        try:
            f.write(bsp_bytes)
        except:
            print("Failed writing: " + name)
            
        f.close()
        return {'FINISHED'}
    
class PatchBspData(bpy.types.Operator, ExportHelper):
    bl_idname = "q3.patch_bsp_data"
    bl_label = "Patch data in existing .bsp"
    bl_options = {"INTERNAL","REGISTER"}
    filename_ext = ".bsp"
    filter_glob : StringProperty(default="*.bsp", options={'HIDDEN'})
    filepath : StringProperty(name="File", description="Which .bsp file to patch", maxlen= 1024, default="")
    only_selected : BoolProperty(name="Only selected objects", default = False)
    create_backup : BoolProperty(name="Append a suffix to the output file (don't overwrite original file)", default = True)
    patch_lm_tcs : BoolProperty(name="Lightmap texture coordinates", default = True)
    patch_tcs : BoolProperty(name="Texture coordinates", default = False)
    patch_normals : BoolProperty(name="Normals", default = False)
    
    patch_colors : BoolProperty(name="Vertex Colors", default = False)
    patch_lightgrid : BoolProperty(name = "Light Grid", default = False)
    patch_lightmaps : BoolProperty(name="Lightmaps", default = True)
    lightmap_to_use : EnumProperty(name="Lightmap Atlas", description="Lightmap Atlas that will be used for patching", default='$lightmap_bake', items=[
            ('$lightmap_bake', "$lightmap_bake", "$lightmap_bake", 0),
            ('$lightmap', "$lightmap", "$lightmap", 1)])
    patch_external : BoolProperty(name="Save External Lightmaps", default = False)
    patch_external_flip : BoolProperty(name="Flip External Lightmaps", default = False)
    patch_empty_lm_lump : BoolProperty(name="Remove Lightmaps in BSP", default = False)
    patch_hdr : BoolProperty(name="HDR Lighting Export", default = False)
    
    #TODO Shader lump + shader assignments
    def execute(self, context):
        bsp = BspClasses.BSP(self.filepath)
        
        if self.only_selected:
            objs = [obj for obj in context.selected_objects if obj.type=="MESH"]
        else:
            objs = [obj for obj in context.scene.objects if obj.type=="MESH" and obj.data.vertex_layers_int.get("BSP_VERT_INDEX") is not None]
        
        meshes = [obj.to_mesh() for obj in objs]
        for mesh in meshes:
            mesh.calc_normals_split()
        
        if self.patch_colors or self.patch_normals or self.patch_lm_tcs or self.patch_tcs:
            self.report({"INFO"}, "Storing Vertex Data...")
            #stores bsp vertex indices
            patched_vertices = {id: False for id in range(int(bsp.lumps["drawverts"].count))}
            lightmapped_vertices = {id: False for id in range(int(bsp.lumps["drawverts"].count))}
            patch_lighting_type = True
            for obj,mesh in zip(objs,meshes):
                if self.patch_lm_tcs:
                    group_map = {group.name: group.index for group in obj.vertex_groups}
                    if not "Lightmapped" in group_map:
                        patch_lighting_type = False
                
                #check if its an imported bsp data set
                if mesh.vertex_layers_int.get("BSP_VERT_INDEX") is not None:
                    bsp_indices = mesh.vertex_layers_int["BSP_VERT_INDEX"]
                    
                    if self.patch_lm_tcs and patch_lighting_type:
                        #store all vertices that are lightmapped
                        for index in [ bsp_indices.data[vertex.index].value 
                                                        for vertex in mesh.vertices 
                                                            if group_map["Lightmapped"] in 
                                                                [ vg.group for vg in vertex.groups ] ]:
                            if index >= 0:
                                lightmapped_vertices[index] = True
                    
                    #patch all vertices of this mesh
                    for poly in mesh.polygons:
                        for vertex, loop in zip(poly.vertices, poly.loop_indices):
                            #get the vertex position in the bsp file
                            bsp_vert_index = bsp_indices.data[vertex].value
                            if bsp_vert_index < 0:
                                continue
                            patched_vertices[bsp_vert_index] = True
                            bsp_vert = bsp.lumps["drawverts"].data[bsp_vert_index]
                            if self.patch_tcs:
                                bsp_vert.texcoord = mesh.uv_layers["UVMap"].data[loop].uv
                            if self.patch_lm_tcs:
                                bsp_vert.lm1coord = mesh.uv_layers["LightmapUV"].data[loop].uv
                                bsp_vert.lm1coord[0] = min(1.0, max(0.0, bsp_vert.lm1coord[0]))
                                bsp_vert.lm1coord[1] = min(1.0, max(0.0, bsp_vert.lm1coord[1]))
                                if bsp.lightmaps == 4:
                                    bsp_vert.lm2coord = mesh.uv_layers["LightmapUV2"].data[loop].uv
                                    bsp_vert.lm2coord[0] = min(1.0, max(0.0, bsp_vert.lm2coord[0]))
                                    bsp_vert.lm2coord[1] = min(1.0, max(0.0, bsp_vert.lm2coord[1]))
                                    bsp_vert.lm3coord = mesh.uv_layers["LightmapUV3"].data[loop].uv
                                    bsp_vert.lm3coord[0] = min(1.0, max(0.0, bsp_vert.lm3coord[0]))
                                    bsp_vert.lm3coord[1] = min(1.0, max(0.0, bsp_vert.lm3coord[1]))
                                    bsp_vert.lm4coord = mesh.uv_layers["LightmapUV4"].data[loop].uv
                                    bsp_vert.lm4coord[0] = min(1.0, max(0.0, bsp_vert.lm4coord[0]))
                                    bsp_vert.lm4coord[1] = min(1.0, max(0.0, bsp_vert.lm4coord[1]))
                            if self.patch_normals:
                                bsp_vert.normal = mesh.vertices[vertex].normal.copy()
                                if mesh.has_custom_normals:
                                    bsp_vert.normal = mesh.loops[loop].normal.copy()
                            if self.patch_colors:
                                bsp_vert.color1 = mesh.vertex_colors["Color"].data[loop].color
                                bsp_vert.color1[3] = mesh.vertex_colors["Alpha"].data[loop].color[0]
                                if bsp.lightmaps == 4:
                                    bsp_vert.color2 = mesh.vertex_colors["Color2"].data[loop].color
                                    bsp_vert.color2[3] = mesh.vertex_colors["Alpha"].data[loop].color[1]
                                    bsp_vert.color3 = mesh.vertex_colors["Color3"].data[loop].color
                                    bsp_vert.color3[3] = mesh.vertex_colors["Alpha"].data[loop].color[2]
                                    bsp_vert.color4 = mesh.vertex_colors["Color4"].data[loop].color
                                    bsp_vert.color4[3] = mesh.vertex_colors["Alpha"].data[loop].color[3]
                else:
                    self.report({"ERROR"}, "Not a valid mesh for patching")
                    return {'CANCELLED'}
                
            self.report({"INFO"}, "Successful")
        
        if self.patch_lm_tcs or self.patch_tcs:
            self.report({"INFO"}, "Storing Texture Coordinates...")
            lightmap_size = bsp.lightmap_size[0]
            packed_lightmap_size = lightmap_size * bpy.context.scene.id_tech_3_lightmaps_per_row
                
            fixed_vertices = []
            #fix lightmap tcs and tcs, set lightmap ids
            for bsp_surf in bsp.lumps["surfaces"].data:
                #fix lightmap tcs and tcs for patches
                #unsmoothes tcs, so the game creates the same tcs we see here in blender
                if bsp_surf.type == 2:
                    width = int(bsp_surf.patch_width-1)
                    height = int(bsp_surf.patch_height-1)
                    ctrlPoints = [[0 for x in range(bsp_surf.patch_width)] for y in range(bsp_surf.patch_height)]
                    for i in range(bsp_surf.patch_width):
                        for j in range(bsp_surf.patch_height):
                            ctrlPoints[j][i] = bsp.lumps["drawverts"].data[bsp_surf.vertex + j*bsp_surf.patch_width + i]
                            
                    for i in range(width+1):
                        for j in range(1, height, 2):
                            if self.patch_lm_tcs:
                                ctrlPoints[j][i].lm1coord[0] = (4.0 * ctrlPoints[j][i].lm1coord[0] - ctrlPoints[j+1][i].lm1coord[0] - ctrlPoints[j-1][i].lm1coord[0]) * 0.5
                                ctrlPoints[j][i].lm1coord[1] = (4.0 * ctrlPoints[j][i].lm1coord[1] - ctrlPoints[j+1][i].lm1coord[1] - ctrlPoints[j-1][i].lm1coord[1]) * 0.5
                                if bsp.lightmaps == 4:
                                    ctrlPoints[j][i].lm2coord[0] = (4.0 * ctrlPoints[j][i].lm2coord[0] - ctrlPoints[j+1][i].lm2coord[0] - ctrlPoints[j-1][i].lm2coord[0]) * 0.5
                                    ctrlPoints[j][i].lm2coord[1] = (4.0 * ctrlPoints[j][i].lm2coord[1] - ctrlPoints[j+1][i].lm2coord[1] - ctrlPoints[j-1][i].lm2coord[1]) * 0.5
                                    ctrlPoints[j][i].lm3coord[0] = (4.0 * ctrlPoints[j][i].lm3coord[0] - ctrlPoints[j+1][i].lm3coord[0] - ctrlPoints[j-1][i].lm3coord[0]) * 0.5
                                    ctrlPoints[j][i].lm3coord[1] = (4.0 * ctrlPoints[j][i].lm3coord[1] - ctrlPoints[j+1][i].lm3coord[1] - ctrlPoints[j-1][i].lm3coord[1]) * 0.5
                                    ctrlPoints[j][i].lm4coord[0] = (4.0 * ctrlPoints[j][i].lm4coord[0] - ctrlPoints[j+1][i].lm4coord[0] - ctrlPoints[j-1][i].lm4coord[0]) * 0.5
                                    ctrlPoints[j][i].lm4coord[1] = (4.0 * ctrlPoints[j][i].lm4coord[1] - ctrlPoints[j+1][i].lm4coord[1] - ctrlPoints[j-1][i].lm4coord[1]) * 0.5
                            if self.patch_tcs:
                                ctrlPoints[j][i].texcoord[0] = (4.0 * ctrlPoints[j][i].texcoord[0] - ctrlPoints[j+1][i].texcoord[0] - ctrlPoints[j-1][i].texcoord[0]) * 0.5
                                ctrlPoints[j][i].texcoord[1] = (4.0 * ctrlPoints[j][i].texcoord[1] - ctrlPoints[j+1][i].texcoord[1] - ctrlPoints[j-1][i].texcoord[1]) * 0.5
                    for j in range(height+1):
                        for i in range(1, width, 2):
                            if self.patch_lm_tcs:
                                ctrlPoints[j][i].lm1coord[0] = (4.0 * ctrlPoints[j][i].lm1coord[0] - ctrlPoints[j][i+1].lm1coord[0] - ctrlPoints[j][i-1].lm1coord[0]) * 0.5
                                ctrlPoints[j][i].lm1coord[1] = (4.0 * ctrlPoints[j][i].lm1coord[1] - ctrlPoints[j][i+1].lm1coord[1] - ctrlPoints[j][i-1].lm1coord[1]) * 0.5
                                if bsp.lightmaps == 4:
                                    ctrlPoints[j][i].lm2coord[0] = (4.0 * ctrlPoints[j][i].lm2coord[0] - ctrlPoints[j][i+1].lm2coord[0] - ctrlPoints[j][i-1].lm2coord[0]) * 0.5
                                    ctrlPoints[j][i].lm2coord[1] = (4.0 * ctrlPoints[j][i].lm2coord[1] - ctrlPoints[j][i+1].lm2coord[1] - ctrlPoints[j][i-1].lm2coord[1]) * 0.5
                                    ctrlPoints[j][i].lm3coord[0] = (4.0 * ctrlPoints[j][i].lm3coord[0] - ctrlPoints[j][i+1].lm3coord[0] - ctrlPoints[j][i-1].lm3coord[0]) * 0.5
                                    ctrlPoints[j][i].lm3coord[1] = (4.0 * ctrlPoints[j][i].lm3coord[1] - ctrlPoints[j][i+1].lm3coord[1] - ctrlPoints[j][i-1].lm3coord[1]) * 0.5
                                    ctrlPoints[j][i].lm4coord[0] = (4.0 * ctrlPoints[j][i].lm4coord[0] - ctrlPoints[j][i+1].lm4coord[0] - ctrlPoints[j][i-1].lm4coord[0]) * 0.5
                                    ctrlPoints[j][i].lm4coord[1] = (4.0 * ctrlPoints[j][i].lm4coord[1] - ctrlPoints[j][i+1].lm4coord[1] - ctrlPoints[j][i-1].lm4coord[1]) * 0.5
                            if self.patch_tcs:
                                ctrlPoints[j][i].texcoord[0] = (4.0 * ctrlPoints[j][i].texcoord[0] - ctrlPoints[j][i+1].texcoord[0] - ctrlPoints[j][i-1].texcoord[0]) * 0.5
                                ctrlPoints[j][i].texcoord[1] = (4.0 * ctrlPoints[j][i].texcoord[1] - ctrlPoints[j][i+1].texcoord[1] - ctrlPoints[j][i-1].texcoord[1]) * 0.5
                
                if self.patch_lm_tcs:               
                    #set new lightmap ids
                    vertices = set()
                    lightmap_id = []
                    lightmap_id2 = []
                    lightmap_id3 = []
                    lightmap_id4 = []
                    if bsp_surf.type != 2:
                        for i in range(int(bsp_surf.n_indexes)):
                            bsp_vert_index = bsp_surf.vertex + bsp.lumps["drawindexes"].data[bsp_surf.index + i].offset
                            #only alter selected vertices
                            if patched_vertices[bsp_vert_index]:
                                vertices.add(bsp_vert_index)
                                bsp_vert = bsp.lumps["drawverts"].data[bsp_vert_index]
                                if lightmapped_vertices[bsp_vert_index] or not patch_lighting_type:
                                    
                                    lightmap_id.append(BspGeneric.get_lm_id(bsp_vert.lm1coord, lightmap_size, packed_lightmap_size))
                                    if bsp.lightmaps == 4:
                                        lightmap_id2.append(BspGeneric.get_lm_id(bsp_vert.lm2coord, lightmap_size, packed_lightmap_size))
                                        lightmap_id3.append(BspGeneric.get_lm_id(bsp_vert.lm3coord, lightmap_size, packed_lightmap_size))
                                        lightmap_id4.append(BspGeneric.get_lm_id(bsp_vert.lm4coord, lightmap_size, packed_lightmap_size))
                    else:
                        for i in range(bsp_surf.patch_width):
                            for j in range(bsp_surf.patch_height):
                                bsp_vert_index = bsp_surf.vertex + j*bsp_surf.patch_width + i
                                if patched_vertices[bsp_vert_index]:
                                    vertices.add(bsp_vert_index)
                                    bsp_vert = bsp.lumps["drawverts"].data[bsp_vert_index]
                                    if lightmapped_vertices[bsp_vert_index] or not patch_lighting_type:
                                        lightmap_id.append(BspGeneric.get_lm_id(bsp_vert.lm1coord, lightmap_size, packed_lightmap_size))
                                        if bsp.lightmaps == 4:
                                            lightmap_id2.append(BspGeneric.get_lm_id(bsp_vert.lm2coord, lightmap_size, packed_lightmap_size))
                                            lightmap_id3.append(BspGeneric.get_lm_id(bsp_vert.lm3coord, lightmap_size, packed_lightmap_size))
                                            lightmap_id4.append(BspGeneric.get_lm_id(bsp_vert.lm4coord, lightmap_size, packed_lightmap_size))
                    
                    if len(vertices) > 0:
                        if len(lightmap_id) > 0:
                            current_lm_id = lightmap_id[0]
                            for i in lightmap_id:
                                if i != current_lm_id:
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
                                
                            if patch_lighting_type or bsp_surf.lm_indexes[0] >= 0:
                                bsp_surf.lm_indexes[0] = lightmap_id[0]
                                if bsp.lightmaps == 4:
                                    bsp_surf.lm_indexes[1] = lightmap_id2[0]
                                    bsp_surf.lm_indexes[2] = lightmap_id3[0]
                                    bsp_surf.lm_indexes[3] = lightmap_id4[0]
                            
                        #unpack lightmap tcs
                        for i in vertices:
                            bsp_vert = bsp.lumps["drawverts"].data[i]
                            BspGeneric.unpack_lm_tc(bsp_vert.lm1coord, lightmap_size, packed_lightmap_size)
                            if bsp.lightmaps == 4:
                                BspGeneric.unpack_lm_tc(bsp_vert.lm2coord, lightmap_size, packed_lightmap_size)
                                BspGeneric.unpack_lm_tc(bsp_vert.lm3coord, lightmap_size, packed_lightmap_size)
                                BspGeneric.unpack_lm_tc(bsp_vert.lm4coord, lightmap_size, packed_lightmap_size)
            self.report({"INFO"}, "Successful")
        #get number of lightmaps
        n_lightmaps = 0
        for bsp_surf in bsp.lumps["surfaces"].data:
            #handle lightmap ids with lightstyles
            for i in range(bsp.lightmaps):
                if bsp_surf.lm_indexes[i] > n_lightmaps:
                    n_lightmaps = bsp_surf.lm_indexes[i]
            
        #store lightmap
        if self.patch_lightmaps:
            lightmap_image = bpy.data.images.get(self.lightmap_to_use)
            if lightmap_image == None:
                self.report({"ERROR"}, "Could not find selected lightmap atlas")
                return {'CANCELLED'}
            self.report({"INFO"}, "Storing Lightmaps...")
            success, message = QuakeLight.storeLighmaps(bsp, lightmap_image, n_lightmaps + 1, not self.patch_external, self.patch_hdr, self.patch_external_flip )
            self.report({"INFO"} if success else {"ERROR"}, message)
        
        #clear lightmap lump        
        if self.patch_empty_lm_lump:
            bsp.lumps["lightmaps"].clear()
        
        #store lightgrid
        if self.patch_lightgrid:
            self.report({"INFO"}, "Storing Lightgrid...")
            success, message = QuakeLight.storeLightgrid(bsp, self.patch_hdr)
            self.report({"INFO"} if success else {"ERROR"}, message)

        #save hdr vertex colors    
        if self.patch_hdr:
            self.report({"INFO"}, "Storing HDR Vertex Colors...")
            success, message = QuakeLight.storeHDRVertexColors(bsp, meshes)
            self.report({"INFO"} if success else {"ERROR"}, message)
        
        #write bsp
        bsp_bytes = bsp.to_bytes()
        
        name = self.filepath
        if self.create_backup == True:
            name = name.replace(".bsp","") + "_data_patched.bsp"
        
        f = open(name, "wb")
        try:
            f.write(bsp_bytes)
        except:
            self.report({"ERROR"}, "Failed writing: " + name)
            return {'CANCELLED'}
        f.close()
        
        return {'FINISHED'}
    
class Prepare_Lightmap_Baking(bpy.types.Operator):
    bl_idname = "q3.prepare_lm_baking"
    bl_label = "Prepare Lightmap Baking"
    bl_options = {"INTERNAL","REGISTER"}
    
    def execute(self, context):
        bpy.context.view_layer.objects.active = None
        for obj in bpy.context.scene.objects:
            if obj.type=="MESH":
                obj.select_set(False)
                mesh = obj.data
                if mesh.name.startswith("*"):
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)
                    if "LightmapUV" in mesh.uv_layers:
                        mesh.uv_layers["LightmapUV"].active = True
                        
        for mat in bpy.data.materials:
            node_tree = mat.node_tree
            if node_tree == None:
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
    bl_options = {"INTERNAL","REGISTER"}
    
    def execute(self, context):
        objs = [obj for obj in context.selected_objects if obj.type=="MESH"]
        for obj in objs:
            mesh = obj.data
            #TODO: handle lightsyles
            success, message = QuakeLight.bake_uv_to_vc(mesh, "LightmapUV", "Color")
            if not success:
                self.report({"ERROR"}, message)
                return {'CANCELLED'}
        
        return {'FINISHED'}
    
class Create_Lightgrid(bpy.types.Operator):
    bl_idname = "q3.create_lightgrid"
    bl_label = "Create Lightgrid"
    bl_options = {"INTERNAL","REGISTER"}
    
    def execute(self, context):
        if QuakeLight.create_lightgrid() == False:
            self.report({"ERROR"}, "BspInfo Node Group not found")
            return {'CANCELLED'}
        
        return {'FINISHED'}

class Convert_Baked_Lightgrid(bpy.types.Operator):
    bl_idname = "q3.convert_baked_lightgrid"
    bl_label = "Convert Baked Lightgrid"
    bl_options = {"INTERNAL","REGISTER"}
    
    def execute(self, context):
        if QuakeLight.createLightGridTextures() == False:
            self.report({"ERROR"}, "Couldn't convert baked lightgrid textures")
            return {'CANCELLED'}
        
        return {'FINISHED'}
    
    
class Q3_PT_EntExportPanel(bpy.types.Panel):
    bl_name = "Q3_PT_ent_panel"
    bl_label = "Export"
    bl_options = {"DEFAULT_CLOSED"}
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Entities"

    @classmethod
    def poll(self, context):
        if "id_tech_3_importer_preset" in context.scene:
            return (context.object is not None and context.scene.id_tech_3_importer_preset == "EDITING")
        return False
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text = "Here you can export all the entities in the scene to different filetypes")
        op = layout.operator("q3.export_ent", text="Export .ent")
        #op = layout.operator("q3.export_map", text="Export .map") is it any different to .ent?
        op = layout.operator("q3.patch_bsp_ents", text="Patch .bsp Entities")
        
        
class Q3_PT_DataExportPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_data_export_panel"
    bl_label = "Patch BSP Data"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Data"
    
    def draw(self, context):
        layout = self.layout
        layout.label(text = "1. Prepare your scene for baking")
        layout.label(text = "Additionally, you need to unwrap all vertex lit")
        layout.label(text = "surfaces else you can't bake vertex colors properly.")
        layout.separator()
        layout.label(text = '2. Press "Prepare Lightmap Baking"')
        op = layout.operator("q3.prepare_lm_baking", text="Prepare Lightmap Baking")
        layout.separator()
        layout.label(text = '3. Keep the selection of objects and bake light:')
        layout.label(text = 'Bake Type: Diffuse only Direct and Indirect')
        layout.label(text = 'Margin: 1 px')
        layout.label(text = 'Make sure you save or pack these images afterwards')
        layout.label(text = '$lightmap_bake and $vertmap_bake')
        layout.separator()
        layout.label(text = '4. Denoise $lightmap_bake and $vertmap_bake (optional)')
        layout.label(text = 'Make sure your Images you want to be baked are named')
        layout.label(text = '$lightmap_bake and $vertmap_bake')
        layout.separator()
        layout.label(text = "5. Copy colors from the images to the vertex colors")
        op = layout.operator("q3.store_vertex_colors", text="Images to Vertex Colors")
        layout.separator()
        layout.label(text = "6. Create the LightGrid object with:")
        op = layout.operator("q3.create_lightgrid", text="Create Lightgrid")
        layout.separator()
        layout.label(text = "7. Select the LightGrid object and bake light:")
        layout.label(text = 'Bake Type: Diffuse only Direct and Indirect')
        layout.label(text = 'Margin: 0 px!')
        layout.separator()
        layout.label(text = "8. Create the lightgrid images that can be stored")
        layout.label(text = "in the BSP file:")
        op = layout.operator("q3.convert_baked_lightgrid", text="Convert Baked Lightgrid")
        layout.label(text = 'Make sure you save or pack these images afterwards')
        layout.label(text = '$Direct, $Vector, $Ambient')
        layout.separator()
        op = layout.operator("q3.patch_bsp_data", text="Patch .bsp Data")

class Reload_preview_shader(bpy.types.Operator):
    """Reload Shaders"""
    bl_idname = "q3mapping.reload_preview_shader"
    bl_label = "Reload Eevee Shaders"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        
        #TODO: write shader dir to scene and read this
        import_settings = ImportSettings()
        import_settings.base_path = prefs.base_path
        import_settings.shader_dirs = "shaders/", "scripts/"
        import_settings.preset = 'PREVIEW'
            
        if not import_settings.base_path.endswith('/'):
            import_settings.base_path = import_settings.base_path + '/'
            
        objs = [obj for obj in context.selected_objects if obj.type=="MESH"]
        
        for obj in objs:
            vg = obj.vertex_groups.get("Decals")
            if vg is not None:
                obj.vertex_groups.remove(vg)
            mod = obj.modifiers.get("polygonOffset")
            if mod is not None:
                obj.modifiers.remove(mod)
        
        QuakeShader.build_quake_shaders(import_settings, objs)
        
        for obj in objs:
            vg = obj.vertex_groups.get("Decals")
            if vg is not None:
                modifier = obj.modifiers.new("polygonOffset", type = "DISPLACE")
                modifier.vertex_group = "Decals"
                modifier.strength = 0.1
                modifier.name = "polygonOffset"
            
        return {'FINISHED'}
    
class Reload_render_shader(bpy.types.Operator):
    """Reload Shaders"""
    bl_idname = "q3mapping.reload_render_shader"
    bl_label = "Reload Cycles Shaders"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        addon_name = __name__.split('.')[0]
        prefs = context.preferences.addons[addon_name].preferences
        
        #TODO: write shader dir to scene and read this
        import_settings = ImportSettings()
        import_settings.base_path = prefs.base_path
        import_settings.shader_dirs = "shaders/", "scripts/"
        import_settings.preset = 'RENDERING'
            
        if not import_settings.base_path.endswith('/'):
            import_settings.base_path = import_settings.base_path + '/'
            
        objs = [obj for obj in context.selected_objects if obj.type=="MESH"]
        
        for obj in objs:
            vg = obj.vertex_groups.get("Decals")
            if vg is not None:
                obj.vertex_groups.remove(vg)
            mod = obj.modifiers.get("polygonOffset")
            if mod is not None:
                obj.modifiers.remove(mod)
        
        QuakeShader.build_quake_shaders(import_settings, objs)
        
        for obj in objs:
            vg = obj.vertex_groups.get("Decals")
            if vg is not None:
                modifier = obj.modifiers.new("polygonOffset", type = "DISPLACE")
                modifier.vertex_group = "Decals"
                modifier.strength = 0.1
                modifier.name = "polygonOffset"
            
        return {'FINISHED'} 
