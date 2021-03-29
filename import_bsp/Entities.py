import bpy
import imp
import json
from enum import Enum
from math import radians, degrees, pow, sqrt, atan

if "MD3" in locals():
    imp.reload( MD3 )
else:
    from . import MD3
    
if "Parsing" in locals():
    imp.reload( Parsing )
else:
    from .Parsing import *
    
if "QuakeLight" in locals():
    imp.reload( QuakeLight )
else:
    from . import QuakeLight

def get_gamepack(name):
    file_path = bpy.utils.script_paths("addons/import_bsp/gamepacks/")[0]
    if file_path is not None:
        with open(file_path + name) as file:
            return json.load(file)
    return None

def save_gamepack(dict, name):
    file_path = bpy.utils.script_paths("addons/import_bsp/gamepacks/")[0]
    if file_path is not None:
        with open(file_path + name, 'w') as file:
            json.dump(dict, file, indent=4,)

Dict = get_gamepack("JKA_SP.json")

misc_model_md3s = ["misc_model_static", "misc_model_breakable"]

type_matching = {   "STRING"    : "NONE",
                    "COLOR"     : "COLOR_GAMMA",
                    "COLOR255"  : "COLOR_GAMMA",
                    "INT"       : "NONE",
                    "FLOAT"     : "NONE",
}

def ImportEntities(bsp, import_settings):        
    clip_end = 12000
    
    lump = bsp.lumps["entities"]
    stringdata = []
    for i in lump.data:
        stringdata.append(i.char.decode("ascii"))
    
    entities_string = "".join(stringdata)
    ent = {}
    entities = []
    n_ent = 0
    mesh = None
    map_objects = ["*"+str(n) for n in range(int(bsp.lumps["models"].count))]
    md3_objects = []
    obj_list = []
    ob = None
    targets = {}
    
    for line in entities_string.splitlines():
        if l_open(line):
            ent = {}
        elif l_close(line):
            entities.append(ent)
            ob = None
            if "targetname" in ent:
                targets[ent["targetname"]] = n_ent
            n_ent += 1
        elif line != " ":
            key,value = parse(line)
            key = key.strip(" \"\t\n\r").lower()
            value = value.replace("\"", "")
            vector_keys = ( "modelscale_vec",
                            "angles",
                            "gridsize",
                            "origin",
                            "modelangles")
            if key in vector_keys:
                value = value.strip(" \"\t\n\r")
                value = value.split(" ")
                #oh man.... Problem in t1_rail
                try:
                    value[0] = float(value[0])
                    value[1] = float(value[1])
                    value[2] = float(value[2])
                except:
                    value = [float(value[0]),float(value[0]),float(value[0])]
            if (key == "classname") or (key == "model") or (key == "modelscale") or (key == "angle"):
                value = value.strip(" \"\t\n\r").replace("\\","/")
            
            #oh man.... Problem in hoth2
            if (key == "modelscale"):
                try:
                    value = float(value)
                except:
                    value = float(value.split(" ")[0])
                    
            ent[key] = value
            
    for n_ent, ent in enumerate(entities):
        mesh_name = ""
        if "distancecull" in ent:
            clip_end = float(ent["distancecull"].replace('"',''))
        
        if "gridsize" in ent:
            bsp.lightgrid_size = ent["gridsize"]
            bsp.lightgrid_inverse_size = [  1.0 / float(bsp.lightgrid_size[0]),
                                            1.0 / float(bsp.lightgrid_size[1]),
                                            1.0 / float(bsp.lightgrid_size[2]) ]
                                            
        #force class model to be loaded
        if ent["classname"].lower() in Dict:
            if "Model" in Dict[ent["classname"].lower()]:
                if Dict[ent["classname"].lower()]["Model"].lower() != "box":
                    ent["model"] = Dict[ent["classname"].lower()]["Model"].lower()
        
        if n_ent == 0:
            me = bpy.data.meshes["*0"]
            ob = bpy.data.objects.new("Entity " + (str(n_ent).zfill(4)), me)
            obj_list.append(ob)
        
        elif "model" in ent and ent["classname"].lower() != "misc_model":
            if "model2" in ent:
                model_name = ent["model2"]
            else:
                model_name = ent["model"]
            
            zoffset = 0  
            if ent["classname"] in misc_model_md3s:
                # FIXME: what if the model is not md3?
                mesh_name = model_name[:-len(".md3")]
                # FIXME: make zoffset driver based: create material hash, link zoffset prop to value in material
                if "zoffset" in ent:
                    zoffset = int(ent["zoffset"].replace('"','')) + 1
                    mesh_name = mesh_name+".z"+str(zoffset)
            else:
                mesh_name = model_name
                
            if mesh_name in map_objects:
                if mesh_name not in bpy.data.meshes:
                    continue
                me = bpy.data.meshes[mesh_name]
                ob = bpy.data.objects.new(mesh_name, me)
            else:
                #TODO: Fix reimporting model when only the zoffset is different
                #check if model already loaded, make a copy of it, replace all the material names with new zoffset
                me = MD3.ImportMD3(import_settings.base_path + model_name, zoffset, False)[0]
                if me == None:
                    print("Couldn't load " + import_settings.base_path + model_name)
                else:
                    map_objects.append(mesh_name)
                    md3_objects.append(mesh_name)
                    me.name = mesh_name
                    
                if me == None:
                    if (mesh == None):
                        ent_object = bpy.ops.mesh.primitive_cube_add(size = 32.0, location=([0,0,0]))
                        ent_object = bpy.context.object
                        ent_object.name = "EntityBox"
                        mesh = ent_object.data
                        mesh.name = "EntityMesh"
                        bpy.data.objects.remove(ent_object, do_unlink=True)
                    me = mesh
                    
                ob = bpy.data.objects.new(mesh_name, me)
                
            obj_list.append(ob)
            
        elif import_settings.preset == "RENDERING":
            if "classname" in ent:
                #import lights
                if ent["classname"].lower() == "light":
                    name = "Entity " + (str(n_ent).zfill(4))
                    intensity = 300
                    color = [1.0, 1.0, 1.0]
                    vector = [0.0, 0.0, -1.0]
                    angle = 3.141592/2.0
                    if "light" in ent:
                        intensity = float(ent["light"])
                    if "_color" in ent:
                        color_str = ent["_color"].split()
                        color = [float(color_str[0]), float(color_str[1]), float(color_str[2])]
                        
                    if "target" in ent:
                        if ent["target"] in targets:
                            if entities[targets[ent["target"]]]:
                                target_ent = entities[targets[ent["target"]]]
                                if "origin" in ent and "origin" in target_ent:
                                    vector[0] = ent["origin"][0] - target_ent["origin"][0]
                                    vector[1] = ent["origin"][1] - target_ent["origin"][1]
                                    vector[2] = ent["origin"][2] - target_ent["origin"][2]
                                    length = sqrt((vector[0]*vector[0])+(vector[1]*vector[1])+(vector[2]*vector[2]))
                                    radius = 64.0
                                    if "radius" in ent:
                                        radius = float(ent["radius"])
                                    angle = 2*(atan(radius/length))
                        if "_sun" in ent:
                            if ent["_sun"] == "1":
                                light = QuakeLight.add_light(name, "SUN", intensity, color, vector, radians(1.5))
                            else:
                                light = QuakeLight.add_light(name, "SPOT", intensity, color, vector, angle)
                        else:
                            light = QuakeLight.add_light(name, "SPOT", intensity, color, vector, angle)
                    else:
                        light = QuakeLight.add_light(name, "POINT", intensity, color, vector, angle)
                    
                    if "origin" in ent:
                        light.location = ent["origin"]
            
        elif import_settings.preset == "EDITING":
            if (mesh == None):
                ent_object = bpy.ops.mesh.primitive_cube_add(size = 32.0, location=([0,0,0]))
                ent_object = bpy.context.object
                ent_object.name = "EntityBox"
                mesh = ent_object.data
                mesh.name = "EntityMesh"
                bpy.data.objects.remove(ent_object, do_unlink=True)
                
            ob = bpy.data.objects.new(name="Entity " + (str(n_ent).zfill(4)), object_data=mesh.copy())
            if "classname" in ent:
                if ent["classname"].lower() in Dict:
                    material_name = str(Dict[ent["classname"].lower()]["Color"])
                    if material_name != None:
                        mat = bpy.data.materials.get(material_name)
                        if (mat == None):
                            mat = bpy.data.materials.new(name=material_name)
                            mat.use_nodes = True
                            node = mat.node_tree.nodes["Principled BSDF"]
                            color_str = material_name.replace("[", "").replace("]", "").split(",")
                            color = pow(float(color_str[0]), 1.0 / 2.2), pow(float(color_str[1]), 1.0 / 2.2), pow(float(color_str[2]), 1.0 / 2.2), 1.0
                            node.inputs["Base Color"].default_value = color
                            node.inputs["Emission"].default_value = color
                        ob.data.materials.append(mat)
                        
                else:            
                    obj_list.append(ob)
        
        if ob != None:
            model2_ob = None
            if "model2" in ent:
                ob.name = "Model2 " + (str(n_ent).zfill(4))
                bpy.context.collection.objects.link(ob)
                mesh_name = ent["model"]
                if mesh_name in map_objects:
                    model2_ob = ob
                    if mesh_name in bpy.data.meshes:
                        me = bpy.data.meshes[mesh_name]
                        ob = bpy.data.objects.new(mesh_name, me)
                        obj_list.append(ob)
                    else:
                        mesh = bpy.data.meshes.get("Empty_BSP_Model")
                        if (mesh == None):
                            ent_object = bpy.ops.mesh.primitive_cube_add(size = 32.0, location=([0,0,0]))
                            ent_object = bpy.context.object
                            ent_object.name = "EntityBox"
                            mesh = ent_object.data
                            mesh.name = "Empty_BSP_Model"
                            bpy.data.objects.remove(ent_object, do_unlink=True)
                        mat = bpy.data.materials.get("Empty_BSP_Model")
                        if (mat == None):
                            mat = bpy.data.materials.new(name="Empty_BSP_Model")
                            mat.use_nodes = True
                            mat.blend_method = "CLIP"
                            mat.shadow_method = "NONE"
                            node = mat.node_tree.nodes["Principled BSDF"]
                            node.inputs["Alpha"].default_value = 0.0
                        ob = bpy.data.objects.new(name="something", object_data=mesh.copy())
                        ob.data.materials.append(mat)
                    ob.name = "Entity " + (str(n_ent).zfill(4))
                    bpy.context.collection.objects.link(ob)
            else:
                ob.name = "Entity " + (str(n_ent).zfill(4))
                bpy.context.collection.objects.link(ob)
            
            if "spawnflags" in ent:
                spawnflag = int(ent["spawnflags"])
                if spawnflag % 2 == 1:
                    ob.q3_dynamic_props.b1 = True
                if spawnflag & 2 > 1:
                    ob.q3_dynamic_props.b2 = True
                if spawnflag & 4 > 1:
                    ob.q3_dynamic_props.b4 = True
                if spawnflag & 8 > 1:
                    ob.q3_dynamic_props.b8 = True
                if spawnflag & 16 > 1:
                    ob.q3_dynamic_props.b16 = True
                if spawnflag & 32 > 1:
                    ob.q3_dynamic_props.b32 = True
                if spawnflag & 64 > 1:
                    ob.q3_dynamic_props.b64 = True
                if spawnflag & 128 > 1:
                    ob.q3_dynamic_props.b128 = True
                if spawnflag & 256 > 1:
                    ob.q3_dynamic_props.b256 = True
                if spawnflag & 512 > 1:
                    ob.q3_dynamic_props.b512 = True
            if "model" in ent:
                ob.q3_dynamic_props.model = ent["model"]
            if "model2" in ent:
                ob.q3_dynamic_props.model2 = ent["model2"]
                    
            #needed for custom descriptions and data types
            rna_ui = ob.get('_RNA_UI')
            if rna_ui is None:
                ob['_RNA_UI'] = {}
                rna_ui = ob['_RNA_UI']
                    
            for key in ent:
                descr_dict = {}
                if ent["classname"].lower() in Dict:
                    if key.lower() in Dict[ent["classname"].lower()]["Keys"]:
                        if "Description" in Dict[ent["classname"].lower()]["Keys"][key.lower()]:
                            descr_dict["description"] = Dict[ent["classname"].lower()]["Keys"][key.lower()]["Description"]
                        if "Type" in Dict[ent["classname"].lower()]["Keys"][key.lower()]:
                            descr_dict["subtype"] = type_matching[Dict[ent["classname"].lower()]["Keys"][key.lower()]["Type"].upper()]
                
                ob[key.lower()] = ent[key]
                rna_ui[key.lower()] = descr_dict
                
            if "origin" in ent:
                ob.location = ent["origin"]
            if mesh_name in md3_objects:
                if "modelscale" in ent:
                    scale = (float(ent["modelscale"]),float(ent["modelscale"]),float(ent["modelscale"]))
                    ob.scale = scale
                if "modelscale_vec" in ent:
                    ob.scale = ent["modelscale_vec"]
                if "angle" in ent:
                    ob.rotation_euler = (0.0,0.0,radians(float(ent["angle"])))
                if "angles" in ent:
                    ob.rotation_euler = (radians(ent["angles"][2]),radians(ent["angles"][0]),radians(ent["angles"][1]))
                    
            if model2_ob != None:
                model2_ob.parent = ob
                if "modelangles" in ent:
                    model2_ob.rotation_euler = (radians(ent["modelangles"][2]),radians(ent["modelangles"][0]),radians(ent["modelangles"][1]))
                model2_ob.hide_select = True
        ob = None
                
    #set clip data
    for a in bpy.context.screen.areas:
        if a.type == 'VIEW_3D':
            for s in a.spaces:
                if s.type == 'VIEW_3D':
                    if import_settings.preset == "EDITING":
                        s.clip_start = 4
                        s.clip_end = 40000
                    else:
                        s.clip_start = 4
                        s.clip_end = clip_end                        
    return obj_list

misc_model_format = """{{
    "classname" "misc_model"
    "origin" "{origin[0]:.3f} {origin[1]:.3f} {origin[2]:.3f}"
    "angles" "{rotation[0]:.3f} {rotation[1]:.3f} {rotation[2]:.3f}"
    "modelscale_vec" "{scale[0]:.3f} {scale[1]:.3f} {scale[2]:.3f}"
    "model" "{model_name}"
    "spawnflags" "{spawn_flags}"
}}
"""

def make_misc_model_entity_from_object(obj, model_name):
    origin = [0.0, 0.0, 0.0]
    scale = [1.0, 1.0, 1.0]
    rotation = [0.0, 0.0, 0.0]
    spawnflags = 0
    if obj.type == 'MESH':
        if obj.location[0].is_integer() and obj.location[1].is_integer() and obj.location[2].is_integer():
            origin = (int(obj.location[0]), int(obj.location[1]), int(obj.location[2]))
        else:
            origin = (obj.location[0], obj.location[1], obj.location[2])
        
        rotation = (degrees(obj.rotation_euler[2]), degrees(obj.rotation_euler[0]), degrees(obj.rotation_euler[1]))
        scale = (obj.scale[0], obj.scale[1], obj.scale[2])
        if "spawnflags" in obj:
            spawnflags = int(obj["spawnflags"])
        return misc_model_format.format(origin=origin, rotation=rotation, scale=scale, model_name=model_name, spawn_flags=spawnflags)
    else:
        return None
    
def get_empty_wordspawn():
    return '{\n\t"classname" "worldspawn"\n}\n'