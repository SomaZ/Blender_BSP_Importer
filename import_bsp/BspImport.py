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

### The new operator ###
class Operator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id3_bsp"
    bl_label = "Import ID3 engine BSP (.bsp)"
    filename_ext = ".bsp"
    filter_glob : StringProperty(default="*.bsp", options={'HIDDEN'})

    filepath : StringProperty(name="File Path", description="File path used for importing the BSP file", maxlen= 1024, default="")
    preset : EnumProperty(name="Import preset", description="You can select wether you want to import a bsp for editing, rendering, or previewing.", default='PREVIEW', items=[
            ('PREVIEW', "Preview", "Trys to build eevee shaders, imports all misc_model_statics when available", 0),
            ('EDITING', "Editing", "Trys to build eevee shaders, imports all entitys", 1),
            #('RENDERING', "Rendering", "Trys to build fitting cycles shaders, only imports visable enities", 2),
        ])
    subdivisions : IntProperty(name="Patch subdivisions", description="How often a patch is subdivided at import", default=2)

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
        import_settings.packed_lightmap_size = 128
        import_settings.log = []
        import_settings.log.append("----import_scene.ja_bsp----")
        import_settings.filepath = self.filepath
        
        #scene information
        context.scene.id_tech_3_importer_preset = self.preset
        
        BspClasses.ImportBSP(import_settings)
        
        #set world color to black to remove additional lighting
        background = context.scene.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs[0].default_value = 0,0,0,1
        else:
            import_settings.log.append("WARNING: Could not set world color to black.")
        
        #for line in import_settings.log:
        #    print(line)
            
        return {'FINISHED'}
        
def menu_func(self, context):
    self.layout.operator(Operator.bl_idname, text="ID3 BSP (.bsp)")
    
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
        obj["model2"] = obj.q3_dynamic_props.model.split(".")[0]
        model_name = obj["model2"]
    elif "model" in obj:
        obj["model"] = obj.q3_dynamic_props.model.split(".")[0]
        model_name = obj["model"]
        
    if obj.data.name == obj.q3_dynamic_props.model:
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
            
        obj.data = MD3.ImportMD3(model_name + ".md3", zoffset)
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
        row.operator("q3mapping.reload_shader")
        layout.separator()
        
class Q3_PT_EntityPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_entity_panel"
    bl_label = "Selected Entity"
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
        obj = bpy.context.active_object
        
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
            name = name.replace(".bsp","") + "_patched.bsp"
        
        f = open(name, "wb")
        try:
            f.write(bsp_bytes)
        except:
            print("Failed writing: " + name)
            
        f.close()
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
        op = layout.operator("q3.patch_bsp_ents", text="Patch .bsp")

class Reload_shader(bpy.types.Operator):
    """Reload Shaders"""
    bl_idname = "q3mapping.reload_shader"
    bl_label = "Reload Shaders"
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
            
        objs = [bpy.context.view_layer.objects.active]
        
        for obj in objs:
            vg = obj.vertex_groups.get("Decals")
            if vg is not None:
                obj.vertex_groups.remove(vg)
        
        QuakeShader.build_quake_shaders(import_settings, objs)
        
        for obj in objs:
            vg = obj.vertex_groups.get("Decals")
            if vg is not None:
                modifier = obj.modifiers.new("polygonOffset", type = "DISPLACE")
                modifier.vertex_group = "Decals"
                modifier.strength = 0.1
                modifier.name = "polygonOffset"
            
        return {'FINISHED'} 
