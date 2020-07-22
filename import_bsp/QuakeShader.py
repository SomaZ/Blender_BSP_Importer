#----------------------------------------------------------------------------#
#TODO:  add fog support
#TODO:  fix transparent shaders as good as possible. I think its not possible 
#       to support all transparent shaders though :/
#TODO:  add last remaining rgbGens and tcMods
#TODO:  animmap support? Not sure if I want to add this
#TODO:  check if the game loads the shaders in the same order
#TODO:  add portals support
#TODO:  fix tcGen Environment cause right now the reflection vector is not correct
#----------------------------------------------------------------------------#

import imp

if "bpy" not in locals():
    import bpy

if "os" not in locals():
    import os

if "ShaderNodes" in locals():
    imp.reload( ShaderNodes )
else:
    from . import ShaderNodes
    
if "QuakeSky" in locals():
    imp.reload( QuakeSky )
else:
    from . import QuakeSky
    
if "Image" in locals():
    imp.reload( Image )
else:
    from . import Image
    
if "Parsing" in locals():
    imp.reload( Parsing )
else:
    from .Parsing import *

from math import radians

LIGHTING_IDENTITY = 0
LIGHTING_VERTEX = 1
LIGHTING_LIGHTGRID = 3
LIGHTING_CONST = 4

ALPHA_UNDEFINED = 0
ALPHA_CONST = 1
ALPHA_VERTEX = 2
ALPHA_ENT = 3
ALPHA_SPEC = 4

BLEND_NONE = "gl_one gl_zero"

TCGEN_NONE = 0
TCGEN_LM = 1
TCGEN_ENV = 2

ACLIP_NONE = 0
ACLIP_GT0 = 1
ACLIP_LT128 = 2
ACLIP_GE128 = 3
ACLIP_GE192 = 4

CULL_FRONT = 0
CULL_TWO = 1

class vanilla_shader_stage:                        
    def __init__(stage):
        stage.diffuse = ""
        stage.clamp = False
        stage.blend = BLEND_NONE
        stage.lighting = LIGHTING_IDENTITY
        stage.color = [1.0, 1.0, 1.0]
        stage.alpha = ALPHA_UNDEFINED
        stage.alpha_value = 1.0
        stage.alpha_clip = ACLIP_NONE
        stage.depthwrite = False
        stage.tcGen = TCGEN_NONE
        stage.tcMods = []
        stage.tcMods_arguments = []
        stage.glow = False
        stage.lightmap = False
        stage.valid = False
        stage.is_surface_sprite = False
        stage.detail = False
        stage.skip_alpha = False
    
        stage.stage_functions = {   "map": stage.setDiffuse,
                                    "animmap": stage.setAnimmap,
                                    "clampmap" : stage.setClampDiffuse,
                                    "blendfunc": stage.setBlend,
                                    "alphafunc": stage.setAlphaClip,
                                    "tcgen": stage.setTcGen,
                                    "tcmod" : stage.setTcMod,
                                    "glow": stage.setGlow,
                                    "alphagen": stage.setAlpha,
                                    "rgbgen": stage.setLighting,
                                    "surfacesprites": stage.setSurfaceSprite,
                                    "depthwrite": stage.setDepthwrite,
                                    "detail" : stage.setDetail,
                                    "depthfunc" : stage.setDepthFunc
                                }
                        
    def setDiffuse(stage, diffuse):
        stage_diffuse = diffuse.split(" ", 1)[0] 
        if stage_diffuse == "$lightmap":
            stage.lightmap = True
            stage.tcGen = TCGEN_LM
        stage.diffuse = stage_diffuse
        
    def setClampDiffuse(stage, diffuse):
        stage_diffuse = diffuse.split(" ", 1)[0] 
        if stage_diffuse == "$lightmap":
            stage.lightmap = True
            stage.tcGen = TCGEN_LM
        stage.diffuse = stage_diffuse
        stage.clamp = True
        
    def setAnimmap(stage, diffuse):
        array = diffuse.split(" ")
        #try getting first image of the array
        try:
            stage_diffuse = array[1]
        except:
            print("Could not parse animmap.")
        #I think using the lightmap here is BS so dont check it
        stage.diffuse = stage_diffuse
        
    def setDepthFunc(stage, depthFunc):
        if depthFunc.startswith("equal"):
            stage.skip_alpha = True
        
    def setDepthwrite(stage, empty):
        stage.depthwrite = True
        
    def setDetail(stage, empty):
        stage.detail = True
        
    def setTcGen(stage, tcgen):
        if tcgen.startswith("environment"):
            stage.tcGen = TCGEN_ENV
        elif tcgen.startswith("lightmap"):
            stage.tcGen = TCGEN_LM
        else:
            print("didn't parse tcGen: ", tcgen)
            
    def setTcMod(stage, tcmod):
        if tcmod.startswith("scale"):
            stage.tcMods.append("scale")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1].strip("\r\n\t "))
        elif tcmod.startswith("scroll"):
            stage.tcMods.append("scroll")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1].strip("\r\n\t "))
        elif tcmod.startswith("turb"):
            stage.tcMods.append("turb")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1].strip("\r\n\t "))
        elif tcmod.startswith("rotate"):
            stage.tcMods.append("rotate")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1].strip("\r\n\t "))
        else:
            print("didn't parse tcMod: ", tcmod)
        
    def setLighting(stage, lighting):
        if (lighting.startswith("vertex") or lighting.startswith("exactvertex")):
            stage.lighting = LIGHTING_VERTEX
        elif (lighting.startswith("oneminusvertex")):
            stage.lighting = -LIGHTING_VERTEX
        elif (lighting.startswith("lightingdiffuse")):
            stage.lighting = LIGHTING_LIGHTGRID
        elif (lighting.startswith("identity")):
            stage.lighting = LIGHTING_IDENTITY
        elif (lighting.startswith("const ")):
            stage.lighting = LIGHTING_CONST
            color = filter(None, lighting.strip("\r\n\t").replace("(","").replace(")","").replace("const ","").split(" "))
            stage.color = [float(component) for component in color]
        else:
            stage.lighting = LIGHTING_IDENTITY
            print("didn't parse rgbGen: ", lighting)
            
    def setAlphaClip(stage, compare):
        if compare.startswith("gt0"):
            stage.alpha_clip = ACLIP_GT0
        elif compare.startswith("lt128"):
            stage.alpha_clip = ACLIP_LT128
        elif compare.startswith("ge128"):
            stage.alpha_clip = ACLIP_GE128
        elif compare.startswith("ge192"):
            stage.alpha_clip = ACLIP_GE192
        else:
            stage.alpha_clip = ACLIP_NONE
            print("didn't parse alphaFunc: ", compare)
            
    def setBlend(stage, blend):
        blends = blend.split()
        if len(blends) > 1:
            safe_blend = blends[0] + " " + blends[1]
        else:
            safe_blend = blends[0]
            
        if (safe_blend.startswith("add")):
            stage.blend = "gl_one gl_one"
        elif (safe_blend.startswith("filter")):
            stage.blend = "gl_dst_color gl_zero"
        elif (safe_blend.startswith("blend")):
            stage.blend = "gl_src_alpha gl_one_minus_src_alpha"
        elif (safe_blend.startswith("gl_one gl_zero")):
            stage.blend = BLEND_NONE
        else:
            stage.blend = safe_blend
    
    def setAlpha(stage, alpha):
        if (alpha.startswith("const")):
            stage.alpha = ALPHA_CONST
            try:
                stage.alpha_value = float(alpha.split(' ', 1)[1].strip("\r\n\t "))
            except:
                print("alphaGen const with no value found")
                stage.alpha_value = 0.5
        elif (alpha.startswith("identity")):
            stage.alpha = ALPHA_CONST
            stage.alpha_value = 1.0
        elif (alpha.startswith("vertex")):
            stage.alpha = ALPHA_VERTEX
        elif (alpha.startswith("oneminusvertex")):
            stage.alpha = -ALPHA_VERTEX
        elif (alpha.startswith("lightingspecular")):
            stage.alpha = ALPHA_SPEC
        else:
            stage.alpha = ALPHA_CONST
            stage.alpha_value = 0.5
            print("didn't parse alphaGen: ", alpha)
            
    def setGlow(stage, empty):
        stage.glow = True
        
    def setSurfaceSprite(stage, surface_sprite):
        stage.is_surface_sprite = True
        
    def finish_stage(stage):
        valid = True
        if (stage.diffuse == ""):
            valid = False
        elif (stage.blend == "gl_zero gl_one"): #who writes something like this Raven?
            print("gl_zero gl_one blend found, useless stage")
            valid = False
        elif (stage.is_surface_sprite):
            valid = False
        stage.valid = valid
        
class quake_shader:
    def __init__(shader, name, material):
        shader.is_vertex_lit = False
        shader.is_grid_lit = False
        shader.is_brush = False
        shader.name = name
        shader.texture = name
        shader.mat = material
        shader.mat.use_nodes = True
        shader.nodes = shader.mat.node_tree.nodes
        shader.nodes.clear()
        shader.links = shader.mat.node_tree.links
                                #   "name"          : Position
        shader.static_nodes =   {   "tcLightmap"    : [-400.0, 0.0],
                                    "tcNormal"      : [-400.0, -100.0],
                                    "tcEnvironment" : [-400.0, -200.0],
                                    "vertexColor"   : [-400.0, 400.0],
                                    "vertexAlpha"   : [-400.0, 200.0],
                                    "specularAlpha" : [-400.0, -800.0],
                                    "gridColor"     : [-400.0, 600.0],
                                    "shaderTime"    : [-800.0, 0.0],
                                    "BaseReflectionVector" : [-400.0, 600.0],
                                    "EmissionScaleNode" : [-400.0, -600.0],
                                }
        
        shader.zoffset = 0
        shader.last_blend = None
        
        shader.is_explicit = False
        shader.is_system_shader = True if name.startswith("noshader") else False
        
        shader.stages = []
        shader.attributes = {}
        
        shader.current_x_location = 200
        shader.current_y_location = 800
        
        index = name.find('.')
        if not (index == -1):
            split_name = shader.name.split(".")
            shader.texture = split_name[0]
            
            if split_name[1].endswith("vertex"):
                shader.is_vertex_lit = True
                
            if split_name[1].endswith("grid"):
                shader.is_grid_lit = True
                
                split_name[1] = split_name[1].replace("grid","")
                if (len(split_name) > 1) and not (split_name[1] == ""):
                    shader.zoffset = split_name[1]
            
            if split_name[1].endswith("brush"):
                shader.is_brush = True
        
        node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
        node_output.name = "Output"
        node_output.location = (4200,0)
    
    def set_vertex_lit(shader):
        shader.is_vertex_lit = True
        shader.is_grid_lit = False
        
    def set_grid_lit(shader):
        shader.is_vertex_lit = False
        shader.is_grid_lit = True
        
    def get_node_by_name(shader, name):
        node = shader.nodes.get(name)
        if node == None:
            return ShaderNodes.create_static_node(shader, name)
        return node
        
    def get_rgbGen_node(shader, rgbGen):
        if rgbGen == 0:
            return None
        if rgbGen == LIGHTING_VERTEX:
            return shader.get_node_by_name("vertexColor")
        elif rgbGen == LIGHTING_LIGHTGRID:
            return shader.get_node_by_name("gridColor")
        elif rgbGen == LIGHTING_CONST:
            color_node = shader.nodes.new(type='ShaderNodeRGB')
            color_node.location = (shader.current_x_location + 200, shader.current_y_location - 500)
            return color_node
        else:
            print("unsupported rgbGen: ", rgbGen)
            return None
        
    def get_alphaGen_node(shader, alphaGen, alpha_value):
        if alphaGen == ALPHA_UNDEFINED:
            return None
        elif alphaGen == ALPHA_CONST:
            node = shader.nodes.new(type="ShaderNodeValue")
            node.outputs["Value"].default_value = alpha_value
            node.location = (shader.current_x_location + 200, shader.current_y_location - 300)
            return node
        elif alphaGen == ALPHA_VERTEX:
            return shader.get_node_by_name("vertexAlpha")
        elif alphaGen == ALPHA_SPEC:
            spec_node = shader.get_node_by_name("specularAlpha")
            if shader.is_grid_lit:
                shader.links.new(shader.get_rgbGen_node(LIGHTING_LIGHTGRID).outputs["LightGridVector"], spec_node.inputs["LightVector"])
            else:
                shader.links.new(shader.get_node_by_name("BaseReflectionVector").outputs["Vector"], spec_node.inputs["LightVector"])
            return spec_node
        else:
            print("unsupported alphaGen: ", alphaGen)
            return None
        
    def get_tcGen_node(shader, tcGen):
        if tcGen == TCGEN_NONE:
            return shader.get_node_by_name("tcNormal")
        if tcGen == TCGEN_LM:
            return shader.get_node_by_name("tcLightmap")
        elif tcGen == TCGEN_ENV:
            return shader.get_node_by_name("tcEnvironment")
        else:
            print("unsupported tcGen: ", tcGen)
            return None
        
    def get_tcMod_node(shader, tcMods, tcMod_arguments):
        out_node = None
        create_new_group = False
        for tcMod, arguments in zip(tcMods, tcMod_arguments):
            if tcMod == "scale":
                new_out_node = shader.nodes.new(type='ShaderNodeMapping')
                new_out_node.name = "tcMod"
                new_out_node.vector_type = "POINT"
                new_out_node.location = (0,0)
                if out_node != None:
                    shader.links.new(out_node.outputs["Vector"],new_out_node.inputs["Vector"])
                out_node = new_out_node

                values = arguments.split(" ")
                out_node.inputs["Scale"].default_value[0] = float(values[0])
                out_node.inputs["Scale"].default_value[1] = float(values[1])
                out_node.inputs["Location"].default_value[1] = -float(values[1])
            elif tcMod == "rotate":
                time_node = shader.get_node_by_name("shaderTime")
                new_out_node = shader.nodes.new(type="ShaderNodeGroup")
                new_out_node.name = "tcMod"
                new_out_node.node_tree = ShaderNodes.Shader_Rotate_Node.get_node_tree(None)
                new_out_node.location = (shader.current_x_location - 200, shader.current_y_location)
                ags = arguments.split(" ",1)
                new_out_node.inputs["Degrees"].default_value = float(ags[0])
                shader.links.new(time_node.outputs["Time"],new_out_node.inputs["Time"])
                if out_node != None:
                    shader.links.new(out_node.outputs["Vector"],new_out_node.inputs["Vector"])
                out_node = new_out_node
                
            elif tcMod == "scroll":
                time_node = shader.get_node_by_name("shaderTime")
                new_out_node = shader.nodes.new(type="ShaderNodeGroup")
                new_out_node.name = "tcMod"
                new_out_node.node_tree = ShaderNodes.Shader_Scroll_Node.get_node_tree(None)
                new_out_node.location = (shader.current_x_location - 200, shader.current_y_location)
                ags = arguments.split(" ",1)
                new_out_node.inputs["Arguments"].default_value = [float(ags[0]),float(ags[1]),0.0]
                shader.links.new(time_node.outputs["Time"],new_out_node.inputs["Time"])
                if out_node != None:
                    shader.links.new(out_node.outputs["Vector"],new_out_node.inputs["Vector"])
                out_node = new_out_node
            else:
                print("unsupported tcMod: ", tcMod, " ", arguments)
        return out_node
            
    def build_stage_nodes(shader, base_path, stage, color_out, alpha_out):
        loc_x = shader.current_x_location
        loc_y = shader.current_y_location
        new_color_out = color_out
        new_alpha_out = alpha_out
        node_blend = None
        if stage.valid:
            if (stage.diffuse == "$whiteimage" or stage.diffuse == "$lightmap"):
                img = bpy.data.images.get(stage.diffuse)
            else:
                img = Image.load_file(base_path, stage.diffuse)
            
            if img is not None:        
                node_color = shader.nodes.new(type='ShaderNodeTexImage')
                node_color.image = img
                if stage.clamp:
                    node_color.extension = 'EXTEND'
                node_color.location = loc_x + 200,loc_y
                tc_gen = shader.get_tcGen_node(stage.tcGen)
                if tc_gen is not None:
                    tc_mod = shader.get_tcMod_node(stage.tcMods, stage.tcMods_arguments)
                    if tc_mod == None:
                        shader.links.new(tc_gen.outputs["UV"],node_color.inputs["Vector"])
                    else:
                        shader.links.new(tc_gen.outputs["UV"],tc_mod.inputs["Vector"])
                        shader.links.new(tc_mod.outputs["Vector"],node_color.inputs["Vector"])
                
                lighting = shader.get_rgbGen_node(stage.lighting)
                if stage.lighting == LIGHTING_CONST:
                    lighting.outputs[0].default_value = (stage.color[0], stage.color[1], stage.color[2], 1.0)
                
                new_color_out = node_color.outputs["Color"]
                new_alpha_out = node_color.outputs["Alpha"]
                
                #clamp alpha if needed
                if not stage.alpha_clip == ACLIP_NONE:
                    clamp_node = shader.nodes.new(type="ShaderNodeMath")
                    clamp_node.location = loc_x + 800, loc_y - 400
                    if stage.alpha_clip == ACLIP_GT0:
                        clamp_node.operation = 'GREATER_THAN'
                        shader.links.new(new_alpha_out, clamp_node.inputs[0])
                        clamp_node.inputs[0].default_value = 0.0
                        new_alpha_out = clamp_node.outputs["Value"]
                    elif stage.alpha_clip == ACLIP_GE128:
                        clamp_node.operation = 'GREATER_THAN'
                        shader.links.new(new_alpha_out, clamp_node.inputs[0])
                        clamp_node.inputs[0].default_value = 127.0/255.0
                        new_alpha_out = clamp_node.outputs["Value"]
                    elif stage.alpha_clip == ACLIP_GE192:
                        clamp_node.operation = 'GREATER_THAN'
                        shader.links.new(new_alpha_out, clamp_node.inputs[0])
                        clamp_node.inputs[0].default_value = 191.0/255.0
                        new_alpha_out = clamp_node.outputs["Value"]
                    elif stage.alpha_clip == ACLIP_LT128:
                        clamp_node.operation = 'LESS_THAN'
                        shader.links.new(new_alpha_out, clamp_node.inputs[0])
                        clamp_node.inputs[0].default_value = 128.0/255.0
                        new_alpha_out = clamp_node.outputs["Value"]
                
                #handle blends
                if stage.blend != BLEND_NONE:
                    node_blend = shader.nodes.new(type="ShaderNodeGroup")
                    
                    node_blend.name = stage.blend
                    node_blend.node_tree = ShaderNodes.Blend_Node.get_node_tree(stage.blend)
                    node_blend.location = loc_x + 800, loc_y - 200
                    shader.last_blend = node_blend
                    if not color_out is None:
                        shader.links.new(color_out, node_blend.inputs["DestinationColor"])
                    if not alpha_out is None:
                        shader.links.new(alpha_out, node_blend.inputs["DestinationAlpha"])
                        
                    shader.links.new(new_color_out, node_blend.inputs["SourceColor"])
                    
                    #handle stage alpha
                    alpha_node = shader.get_alphaGen_node(stage.alpha, stage.alpha_value)
                    if alpha_node == None:
                        shader.links.new(new_alpha_out, node_blend.inputs["SourceAlpha"])
                    else:
                        shader.links.new(alpha_node.outputs[0], node_blend.inputs["SourceAlpha"])
                        
                    new_color_out = node_blend.outputs["OutColor"]
                    new_alpha_out = node_blend.outputs["OutAlpha"]
                
                #handle rgbGens
                if lighting is not None:
                    if node_blend is not None:
                        shader.links.new(lighting.outputs[0], node_blend.inputs["rgbGen"])
                    else:
                        node_rgbGen = shader.nodes.new(type='ShaderNodeMixRGB')
                        node_rgbGen.name = "rgbGen"
                        node_rgbGen.location = (loc_x+800,loc_y-200)
                        node_rgbGen.blend_type = 'MULTIPLY'
                        node_rgbGen.inputs[0].default_value = 1.0
                        shader.links.new(new_color_out, node_rgbGen.inputs["Color1"])
                        shader.links.new(lighting.outputs[0], node_rgbGen.inputs["Color2"])
                        new_color_out = node_rgbGen.outputs["Color"]
        
        return new_color_out, new_alpha_out
        
    def add_stage(shader, stage_dict):
        stage = vanilla_shader_stage()
        for key in stage_dict:
            if key in stage.stage_functions:
                stage.stage_functions[key](stage_dict[key])
            else:
                print("unsupported stage function: ", key)
            
        stage.finish_stage()
        if (stage.valid or stage.lightmap):
            shader.stages.append(stage)
            shader.is_explicit = True
            
    def finish_rendering_shader(shader, base_path, import_settings):
        #we dont want the system shaders and "those" skys
        if shader.is_system_shader or "skyparms" in shader.attributes:
            shader.nodes.clear()
            node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
            node_output.name = "Output"
            node_output.location = (3400,0)
            node_BSDF = shader.nodes.new(type="ShaderNodeBsdfTransparent")
            node_BSDF.name = "Out_BSDF"
            node_BSDF.location = (3000,0)
            shader.links.new(node_BSDF.outputs["BSDF"], node_output.inputs[0])
            shader.mat.blend_method = "BLEND"
            if "skyparms" in shader.attributes:
                skyname = shader.attributes["skyparms"][0].split(" ")[0]
                image = bpy.data.images.get(skyname)
                if image == None:
                    image = QuakeSky.make_equirectangular_from_sky(base_path, skyname)
                
                bg_node = bpy.context.scene.world.node_tree.nodes.get("Background")
                im_node = bpy.context.scene.world.node_tree.nodes.get("SkyTex")
                if im_node == None:
                    im_node = bpy.context.scene.world.node_tree.nodes.new(type="ShaderNodeTexEnvironment")
                    im_node.name = "SkyTex"
                    im_node.location = im_node.location[0] - 800, im_node.location[1]
                im_node.image = image
                
                lp_node = bpy.context.scene.world.node_tree.nodes.get("LightPath")
                if lp_node == None:
                    lp_node = bpy.context.scene.world.node_tree.nodes.new(type="ShaderNodeLightPath")
                    lp_node.name = "LightPath"
                    lp_node.location = im_node.location[0], im_node.location[1] + 600
                    
                lt_node = bpy.context.scene.world.node_tree.nodes.get("LessThan")
                if lt_node == None:
                    lt_node = bpy.context.scene.world.node_tree.nodes.new(type="ShaderNodeMath")
                    lt_node.name = "LessThan"
                    lt_node.operation = "LESS_THAN"
                    lt_node.inputs[1].default_value = 1.0
                    lt_node.location = im_node.location[0] + 200, im_node.location[1] + 400
                
                mx_node = bpy.context.scene.world.node_tree.nodes.get("Mix")
                if mx_node == None:
                    mx_node = bpy.context.scene.world.node_tree.nodes.new(type="ShaderNodeMixRGB")
                    mx_node.name = "Mix"
                    mx_node.inputs[2].default_value = (0.0, 0.0, 0.0, 1.0)
                    mx_node.location = im_node.location[0] + 600, im_node.location[1] + 300
                
                bpy.context.scene.world.node_tree.links.new(lp_node.outputs["Transparent Depth"],lt_node.inputs[0])
                bpy.context.scene.world.node_tree.links.new(lt_node.outputs[0],mx_node.inputs["Fac"])
                bpy.context.scene.world.node_tree.links.new(im_node.outputs["Color"],mx_node.inputs[1])
                bpy.context.scene.world.node_tree.links.new(mx_node.outputs["Color"],bg_node.inputs["Color"])
                
            if "sun" in shader.attributes:
                for i, sun_parms in enumerate(shader.attributes["sun"]):
                    QuakeSky.add_sun(shader.name, "sun", sun_parms, i)
            if "q3map_sun" in shader.attributes:
                for i, sun_parms in enumerate(shader.attributes["q3map_sun"]):
                    QuakeSky.add_sun(shader.name, "q3map_sun", sun_parms, i)
            if "q3map_sunext" in shader.attributes:
                for i, sun_parms in enumerate(shader.attributes["q3map_sunext"]):
                    QuakeSky.add_sun(shader.name, "q3map_sunext", sun_parms, i)
            if "q3gl2_sun" in shader.attributes:
                for i, sun_parms in enumerate(shader.attributes["q3gl2_sun"]):
                    QuakeSky.add_sun(shader.name, "q3gl2_sun", sun_parms, i)
                
            node_lm = shader.nodes.new(type='ShaderNodeTexImage')
            node_lm.location = 700,0
            
            vertmap = bpy.data.images.get("$vertmap_bake")
            if vertmap == None:
                vertmap = bpy.data.images.new("$vertmap_bake", width=2048, height=2048)
            node_lm.image = vertmap
                
            tc_gen = shader.get_tcGen_node(TCGEN_LM)
            if tc_gen is not None:
                shader.links.new(tc_gen.outputs["UV"],node_lm.inputs["Vector"])
                
            node_lm.select = True
            shader.nodes.active = node_lm
            shader.mat.shadow_method = 'NONE'
            return
        
        elif shader.is_explicit:
            out_Color = None
            out_Alpha = None
            out_Glow = None
            out_None = None
            stage_index = 0
            added_stages = 0
            shader_type = "OPAQUE"
            for stage in shader.stages:
                if stage_index == 0:
                    if stage.blend == "gl_one gl_src_alpha":
                        stage.blend = "gl_one_minus_src_alpha gl_zero"
                    if stage.blend == "gl_one gl_one_minus_src_alpha":
                        stage.blend = "gl_src_alpha gl_zero"
                    if stage.alpha_clip != ACLIP_NONE:
                        shader.mat.blend_method = "CLIP"
                    if stage.blend != BLEND_NONE:
                        shader_type = "ADD"
                        shader.mat.blend_method = "BLEND"
                else:
                    if stage.blend.endswith("gl_one_minus_src_alpha") and shader_type == "ADD":
                        shader_type = "BLEND"
                        shader.mat.blend_method = "BLEND"
                    if stage.blend.endswith("gl_src_alpha") and shader_type == "ADD":
                        shader_type = "BLEND"
                        shader.mat.blend_method = "BLEND"
                    if stage.blend.endswith("gl_src_color") and shader_type == "ADD" and not stage.lightmap:
                        shader_type = "MULTIPLY"
                        shader.mat.blend_method = "BLEND"
                    if stage.blend.startswith("gl_dst_color") and shader_type == "ADD" and not stage.lightmap:
                        shader_type = "MULTIPLY"
                        shader.mat.blend_method = "BLEND"
                        
                if stage.blend.endswith("gl_zero"):
                    shader_type = "OPAQUE"
                    shader.mat.blend_method = "OPAQUE" if shader.mat.blend_method != "CLIP" else "CLIP"
                
                stage_index += 1
                
                if stage.lightmap:
                    continue
                if stage.tcGen == TCGEN_ENV:
                    continue
                if stage.alpha == ALPHA_SPEC:
                    continue
                
                if stage.lighting == LIGHTING_VERTEX or stage.lighting == LIGHTING_LIGHTGRID:
                    stage.lighting = 0
                
                if added_stages == 0:
                    if shader_type == "OPAQUE":
                        stage.blend = "gl_one gl_zero"
                    if "portal" in shader.attributes:
                        stage.blend = "gl_one gl_zero"
                
                if stage.glow or stage.blend == "gl_one gl_one":
                    out_Glow, out_None = shader.build_stage_nodes(   base_path, 
                                                        stage, 
                                                        out_Glow, 
                                                        out_Alpha)
                else:
                    out_Color, out_Alpha = shader.build_stage_nodes(   base_path, 
                                                        stage, 
                                                        out_Color, 
                                                        out_Alpha)
                added_stages += 1
                                                        
            if out_Color != None:
                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
                node_BSDF.location = (3000,0)
                node_BSDF.inputs["Roughness"].default_value = 0.9999
                shader.links.new(out_Color, node_BSDF.inputs["Base Color"])
                if out_Glow != None:
                    new_node = shader.get_node_by_name("EmissionScaleNode")
                    shader.links.new(out_Glow, new_node.inputs[0])
                    shader.links.new(new_node.outputs[0], node_BSDF.inputs["Emission"])
                if shader.mat.blend_method != "OPAQUE" and out_Alpha != None and "portal" not in shader.attributes:
                    shader.links.new(out_Alpha, node_BSDF.inputs["Alpha"])
                shader.links.new(node_BSDF.outputs["BSDF"], shader.nodes["Output"].inputs[0])
            else:
                shader.mat.blend_method = "BLEND"
                node_Emiss = shader.nodes.new(type="ShaderNodeEmission")
                node_Emiss.location = (3000,0)
                if out_Glow != None:
                    new_node = shader.get_node_by_name("EmissionScaleNode")
                    shader.links.new(out_Glow, new_node.inputs[0])
                    shader.links.new(new_node.outputs[0], node_Emiss.inputs["Color"])
                else:
                     node_Emiss.inputs["Color"].default_value = 0.0, 0.0, 0.0, 1.0
                     
                node_transparent = shader.nodes.new(type="ShaderNodeBsdfTransparent")
                node_transparent.location = (3000,-300)
                
                node_BSDF = shader.nodes.new(type="ShaderNodeAddShader")
                node_BSDF.location = (3300,0)
                shader.links.new(node_Emiss.outputs["Emission"], node_BSDF.inputs[0])
                shader.links.new(node_transparent.outputs[0], node_BSDF.inputs[1])
                shader.links.new(node_BSDF.outputs[0], shader.nodes["Output"].inputs[0])
            
        else:
            img = Image.load_file(base_path, shader.texture)
            if img is not None:
                img.alpha_mode = "CHANNEL_PACKED"
                node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                node_texture.image = img
                node_texture.location = 1200,0
                        
                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
                node_BSDF.location = (3000,0)
                node_BSDF.inputs["Roughness"].default_value = 0.9999
                shader.links.new(node_texture.outputs["Color"], node_BSDF.inputs["Base Color"])
                shader.links.new(node_BSDF.outputs["BSDF"], shader.nodes["Output"].inputs[0])
            else:
                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
                node_BSDF.location = (3000,0)
                node_BSDF.inputs["Roughness"].default_value = 0.9999
                
        if "portal" in shader.attributes:
            node_gloss = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
            node_gloss.location = (3000, -600)
            node_gloss.inputs["Roughness"].default_value = 0.0
            node_gloss.inputs["Metallic"].default_value = 1.0
            node_mix = shader.nodes.new(type="ShaderNodeMixShader")
            node_mix.location = (3400, 0)

            shader.links.new(node_BSDF.outputs[0], node_mix.inputs[1])
            shader.links.new(node_gloss.outputs[0], node_mix.inputs[2])
            if out_Alpha != None:
                shader.links.new(out_Alpha, node_mix.inputs[0])
            shader.links.new(node_mix.outputs[0], shader.nodes["Output"].inputs[0])
            shader.mat.blend_method = "OPAQUE"
          
        lm_size = 2048 #max size for internal lightmaps (256 Lightmaps at 128x128)  
        orig_lm = bpy.data.images.get("$lightmap")
        if orig_lm != None:
            lm_size = orig_lm.size[0]
            
        lm_image = bpy.data.images.get("$lightmap_bake")
        if lm_image == None:
            lm_image = bpy.data.images.new("$lightmap_bake", width=lm_size, height=lm_size, float_buffer=True)
        vt_image = bpy.data.images.get("$vertmap_bake")
        if vt_image == None:
            vt_image = bpy.data.images.new("$vertmap_bake", width=lm_size, height=lm_size, float_buffer=True)
        
        node_lm = shader.nodes.new(type='ShaderNodeTexImage')
        node_lm.location = 700,0
        node_lm.name = "Baking Image"
        if shader.is_vertex_lit:
            node_lm.image = vt_image
        else:
            node_lm.image = lm_image
            
        tc_gen = shader.get_tcGen_node(TCGEN_LM)
        if tc_gen is not None:
            shader.links.new(tc_gen.outputs["UV"],node_lm.inputs["Vector"])
        
        shader.mat.use_backface_culling = True
        if "cull" in shader.attributes:
            if shader.attributes["cull"][0] == "twosided" or shader.attributes["cull"][0] == "none":
                shader.mat.use_backface_culling = False
                
        if shader.mat.use_backface_culling:
            mx_node = shader.nodes.new(type = "ShaderNodeMixShader")
            mx_node.location = 3800, 0
            tp_node = shader.nodes.new(type = "ShaderNodeBsdfTransparent")
            tp_node.location = 3300, -400
            gm_node = shader.nodes.new(type = "ShaderNodeNewGeometry")
            gm_node.location = 3300, 600
            shader.links.new(gm_node.outputs["Backfacing"], mx_node.inputs[0])
            shader.links.new(node_BSDF.outputs[0], mx_node.inputs[1])
            shader.links.new(tp_node.outputs["BSDF"], mx_node.inputs[2])
            shader.links.new(mx_node.outputs[0], shader.nodes["Output"].inputs[0])
            shader.nodes["Output"].target = "CYCLES"
            
            eevee_out = shader.nodes.new(type = "ShaderNodeOutputMaterial")
            eevee_out.location = 4200, -300
            eevee_out.name = "EeveeOut"
            eevee_out.target = "EEVEE"
            shader.links.new(node_BSDF.outputs[0], eevee_out.inputs[0])
            
        shader.mat.shadow_method = 'CLIP'
        
        node_lm.select = True
        shader.nodes.active = node_lm
            
    def finish_preview_shader(shader, base_path, import_settings):
        
        color_out = None
        alpha_out = None
        shader_type = "BLEND"
        
        if shader.is_system_shader:
            if import_settings.preset != 'EDITING': #not editing preset
                shader.nodes.clear()
                node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
                node_output.name = "Output"
                node_output.location = (3400,0)
                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfTransparent")
                node_BSDF.name = "Out_BSDF"
                node_BSDF.location = (3000,0)
                shader.links.new(node_BSDF.outputs["BSDF"], node_output.inputs[0])
                shader.mat.blend_method = "BLEND"
                return
            else:
                shader.is_explicit = False
                shader.mat.blend_method = "BLEND"
        
        if "skyparms" in shader.attributes:
            shader.nodes.clear()
            node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
            node_output.name = "Output"
            node_output.location = (3400,0)
            node_BSDF = shader.nodes.new(type="ShaderNodeEmission")
            node_BSDF.name = "Out_BSDF"
            node_BSDF.location = (3000,0)
            
            node_image = shader.nodes.new(type="ShaderNodeTexEnvironment")
            node_image.location = (2800,0)
            skyname = shader.attributes["skyparms"][0].split(" ")[0]
            image = bpy.data.images.get(skyname)
            if image == None:
                image = QuakeSky.make_equirectangular_from_sky(base_path, skyname)
            node_image.image = image
            
            node_geometry = shader.nodes.new(type="ShaderNodeNewGeometry")
            node_geometry.location = (2000,0)
            
            node_scale = shader.nodes.new(type="ShaderNodeVectorMath")
            node_scale.location = (2400,0)
            node_scale.operation = "SCALE"
            node_scale.inputs["Scale"].default_value = -1.0
            
            shader.links.new(node_geometry.outputs["Incoming"], node_scale.inputs[0])
            shader.links.new(node_scale.outputs["Vector"], node_image.inputs["Vector"])
            
            shader.links.new(node_image.outputs["Color"], node_BSDF.inputs["Color"])
            shader.links.new(node_BSDF.outputs[0], node_output.inputs[0])
            shader.mat.use_backface_culling = True
            return
        
        elif shader.is_explicit:
            stage_index = 0
            n_stages = 0

            explicitly_depthwritten = False
            lightmap_available = bpy.data.images.get("$lightmap") != None
            
            for stage in shader.stages:
                
                if stage_index == 0:
                    if stage.blend == "gl_one gl_src_alpha":
                        stage.blend = "gl_one_minus_src_alpha gl_zero"
                    if stage.blend == "gl_one gl_one_minus_src_alpha":
                        stage.blend = "gl_src_alpha gl_zero"
                    if stage.alpha_clip != ACLIP_NONE:
                        shader.mat.blend_method = "CLIP"
                    if stage.blend != BLEND_NONE:
                        shader_type = "ADD"
                        shader.mat.blend_method = "BLEND"
                    if shader.is_vertex_lit and stage.lighting is LIGHTING_IDENTITY:
                        stage.lighting = LIGHTING_VERTEX
                    if shader.is_grid_lit and stage.lighting is LIGHTING_IDENTITY:
                        stage.lighting = LIGHTING_LIGHTGRID
                        
                if stage.blend.endswith("gl_zero"):
                    shader_type = "OPAQUE"
                    shader.mat.blend_method = "OPAQUE" if shader.mat.blend_method != "CLIP" else "CLIP"
                        
                if not shader.is_grid_lit and stage.lighting is LIGHTING_LIGHTGRID:
                    stage.lighting = LIGHTING_VERTEX
                    
                if stage.lightmap and not lightmap_available:
                    stage.diffuse = "$whiteimage"
                    stage.lighting = LIGHTING_VERTEX
                        
                #TODO: proper handling of additive and multiplicative shaders
                if stage.blend.endswith("gl_one_minus_src_alpha") and shader_type == "ADD":
                    shader_type = "BLEND"
                    shader.mat.blend_method = "BLEND"
                    
                if stage.blend.endswith("gl_src_alpha") and shader_type == "ADD":
                    shader_type = "BLEND"
                    shader.mat.blend_method = "BLEND"
                        
                if stage.blend.endswith("gl_src_color") and shader_type == "ADD" and not stage.lightmap:
                    shader_type = "MULTIPLY"
                    shader.mat.blend_method = "BLEND"
                    
                if stage.blend.startswith("gl_dst_color") and shader_type == "ADD" and not stage.lightmap:
                    shader_type = "MULTIPLY"
                    shader.mat.blend_method = "BLEND"
                    
                if shader_type == "MULTIPLY" and color_out == None:
                    node_color = shader.nodes.new(type='ShaderNodeRGB')
                    node_color.location = shader.current_x_location, shader.current_y_location + 400
                    node_color.outputs[0].default_value = (1, 1, 1, 1)
                    node_value = shader.nodes.new(type="ShaderNodeValue")
                    node_value.location = shader.current_x_location, shader.current_y_location + 200
                    node_value.outputs[0].default_value = 1.0
                    color_out = node_color.outputs[0]
                    alpha_out = node_value.outputs[0]
                    
                if stage.depthwrite:
                    if stage.blend != BLEND_NONE and shader_type == "ADD":
                        shader.mat.blend_method = "BLEND"
                    if stage.alpha_clip != ACLIP_NONE and shader.mat.blend_method != "OPAQUE":
                        shader.mat.blend_method = "CLIP"
                    
                stage_index += 1
                
                if shader.is_vertex_lit and stage.lightmap:
                    if color_out == None:
                        color_out = shader.get_rgbGen_node(LIGHTING_VERTEX).outputs[0]
                    elif not shader.last_blend == None:
                        shader.links.new(shader.get_rgbGen_node(LIGHTING_VERTEX).outputs[0], shader.last_blend.inputs['rgbGen'])
                elif shader.is_grid_lit and stage.lightmap:
                    if color_out == None:
                        color_out = shader.get_rgbGen_node(LIGHTING_LIGHTGRID).outputs[0]
                    elif not shader.last_blend == None:
                        shader.links.new(shader.get_rgbGen_node(LIGHTING_LIGHTGRID).outputs[0], shader.last_blend.inputs['rgbGen'])
                else:
                    if stage.skip_alpha:
                        color_out, none_out = shader.build_stage_nodes(   base_path, 
                                                    stage, 
                                                    color_out, 
                                                    alpha_out)
                    else:
                        color_out, alpha_out = shader.build_stage_nodes(   base_path, 
                                                    stage, 
                                                    color_out, 
                                                    alpha_out)
                                            
                shader.current_x_location += 300
                shader.current_y_location -= 600
                n_stages += 1
                
            if color_out is None:
                print(shader.name + " shader is not supported right now")
            
        else:
            img = Image.load_file(base_path, shader.texture)
            if img is not None:
                img.alpha_mode = "CHANNEL_PACKED"
                if shader.is_vertex_lit:
                    node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                    node_texture.image = img
                    node_texture.location = 1200,0
                    node_blend = shader.nodes.new(type='ShaderNodeMixRGB')
                    node_blend.blend_type = 'MULTIPLY'
                    node_blend.inputs[0].default_value = 1.0
                    node_blend.location = 1600, -200
                    shader.links.new(node_texture.outputs["Color"], node_blend.inputs['Color1'])
                    shader.links.new(shader.get_rgbGen_node(LIGHTING_VERTEX).outputs[0], node_blend.inputs['Color2'])
                    color_out = node_blend.outputs["Color"]
                elif shader.is_grid_lit:
                    node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                    node_texture.image = img
                    node_texture.location = 1200,0
                    node_blend = shader.nodes.new(type='ShaderNodeMixRGB')
                    node_blend.blend_type = 'MULTIPLY'
                    node_blend.inputs[0].default_value = 1.0
                    node_blend.location = 1600, -200
                    shader.links.new(node_texture.outputs["Color"], node_blend.inputs["Color1"])
                    shader.links.new(shader.get_rgbGen_node(LIGHTING_LIGHTGRID).outputs[0], node_blend.inputs["Color2"])
                    color_out = node_blend.outputs["Color"]
                else:
                    node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                    node_texture.image = img
                    
                    node_texture.location = 1200,0
                    
                    lightmap = bpy.data.images.get("$lightmap")
                    if lightmap == None:
                        node_lm = shader.get_rgbGen_node(LIGHTING_VERTEX)
                        node_lm.location = 1200,-800
                    else:
                        node_lm = shader.nodes.new(type='ShaderNodeTexImage')
                        node_lm.image = lightmap
                        node_lm.location = 1200,-800
                    
                    tc_gen = shader.get_tcGen_node(TCGEN_LM)
                    if tc_gen is not None and lightmap is not None:
                        shader.links.new(tc_gen.outputs["UV"],node_lm.inputs["Vector"])
                        
                    node_blend = shader.nodes.new(type='ShaderNodeMixRGB')
                    node_blend.blend_type = 'MULTIPLY'
                    node_blend.inputs[0].default_value = 1.0
                    node_blend.location = 1600, -200
                    
                    shader.links.new(node_texture.outputs["Color"], node_blend.inputs["Color1"])
                    shader.links.new(node_lm.outputs["Color"], node_blend.inputs["Color2"])
                    color_out = node_blend.outputs["Color"]
        
        shader.mat.use_backface_culling = True
        if "cull" in shader.attributes:
            if shader.attributes["cull"][0] == "twosided" or shader.attributes["cull"][0] == "none":
                shader.mat.use_backface_culling = False
        shader.mat.shadow_method = 'CLIP'
        
        if import_settings.preset == 'EDITING' and shader.is_system_shader:
            shader_type = "BLEND"
            node_val = shader.nodes.new(type="ShaderNodeValue")
            if "qer_trans" in shader.attributes:
                node_val.outputs[0].default_value = float(shader.attributes["qer_trans"][0])
            else:
                node_val.outputs[0].default_value = 0.8
            alpha_out = node_val.outputs[0]
            
        shader_out = None
        if shader_type == "ADD":
            node_BSDF = shader.nodes.new(type="ShaderNodeEmission")
            node_BSDF.location = (3000,0)
            
            node_transp = shader.nodes.new(type="ShaderNodeBsdfTransparent")
            node_transp.location = (3000,-400)
            
            node_add = shader.nodes.new(type="ShaderNodeAddShader")
            node_add.location = (3600,0)
            
            shader.links.new(node_BSDF.outputs[0], node_add.inputs[0])
            shader.links.new(node_transp.outputs[0], node_add.inputs[1])
            if color_out != None:
                shader.links.new(color_out, node_BSDF.inputs["Color"])
            shader_out = node_add.outputs["Shader"]
        elif shader_type == "MULTIPLY":
            node_BSDF = shader.nodes.new(type="ShaderNodeBsdfTransparent")
            node_BSDF.location = (3000,0)
            if color_out != None:
                node_mix = shader.nodes.new(type="ShaderNodeMixRGB")
                node_mix.location = (3000,-400)
                node_rgb = shader.nodes.new(type="ShaderNodeRGB")
                node_rgb.outputs[0].default_value = (1, 1, 1, 1)
                node_rgb.location = (2600,-400)
                shader.links.new(color_out, node_mix.inputs["Color2"])
                shader.links.new(alpha_out, node_mix.inputs["Fac"])
                shader.links.new(node_rgb.outputs[0], node_mix.inputs["Color1"])
                shader.links.new(node_mix.outputs[0], node_BSDF.inputs["Color"])
                
            shader_out = node_BSDF.outputs["BSDF"]
        else: # shader_type == "BLEND":
            node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
            node_BSDF.location = (3000,0)
            node_BSDF.inputs["Roughness"].default_value = 0.9999
            
            if color_out != None:
                shader.links.new(color_out, node_BSDF.inputs["Base Color"])
                shader.links.new(color_out, node_BSDF.inputs["Emission"])
            if shader.mat.blend_method != "OPAQUE" and alpha_out != None:
                shader.links.new(alpha_out, node_BSDF.inputs["Alpha"])
            shader_out = node_BSDF.outputs["BSDF"]
        
        shader.links.new(shader_out, shader.nodes["Output"].inputs[0])
        
    def finish_brush_shader(shader, base_path, import_settings):
        node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
        node_BSDF.location = (3000,0)
        node_BSDF.name = "Out_BSDF"
        node_BSDF.inputs["Roughness"].default_value = 0.9999
        node_BSDF.inputs["Alpha"].default_value = 0.5
        is_sky = False
        if "qer_editorimage" in shader.attributes:
            image = Image.load_file(base_path, shader.attributes["qer_editorimage"][0])
        else:
            image = Image.load_file(base_path, shader.texture)
            
        if image != None:
            node_img = shader.nodes.new(type='ShaderNodeTexImage')
            node_img.image = image
            node_img.location = 1200,-800
            shader.links.new(node_img.outputs["Color"], node_BSDF.inputs["Base Color"])
            
        if "qer_trans" in shader.attributes:
            node_BSDF.inputs["Alpha"].default_value = float(shader.attributes["qer_trans"][0])
            
        if import_settings.preset == 'RENDERING' or import_settings.preset == "BRUSHES":
            transparent = False
            
            if "skyparms" in shader.attributes:
                transparent = True
                is_sky = True
            if "surfaceparm" in shader.attributes:
                if "trans" in shader.attributes["surfaceparm"]:
                    transparent = True
                if "nonopaque" in shader.attributes["surfaceparm"]:
                    transparent = True
                    
            if transparent:
                node_BSDF.inputs["Alpha"].default_value = 0.0
                node_BSDF.name = "Sky" if is_sky else "Transparent"
                shader.links.new(node_BSDF.outputs[0], shader.nodes["Output"].inputs[0])
                shader.mat.shadow_method = 'NONE'
            else:
                solid_BSDF = shader.nodes.new(type="ShaderNodeBsdfDiffuse")
                solid_BSDF.location = 4200, 0
                shader.links.new(solid_BSDF.outputs[0], shader.nodes["Output"].inputs[0])
                shader.nodes["Output"].target = "CYCLES"
                
                eevee_out = shader.nodes.new(type = "ShaderNodeOutputMaterial")
                eevee_out.location = 4200, -300
                eevee_out.name = "EeveeOut"
                eevee_out.target = "EEVEE"
                shader.links.new(node_BSDF.outputs[0], eevee_out.inputs[0])
                
            shader.mat.blend_method = "BLEND"
    
    def finish_shader(shader, base_path, import_settings):
        if shader.is_brush:
            shader.finish_brush_shader(base_path, import_settings)
        elif import_settings.preset != 'RENDERING':
            shader.finish_preview_shader(base_path, import_settings)
        else:
            shader.finish_rendering_shader(base_path, import_settings)

#TODO: overwrite existing Bsp Node instead of making a new one?
def init_shader_system(bsp):
    bsp_node = ShaderNodes.Bsp_Node.create_node_tree(bsp)
    bsp_node.use_fake_user = True
    color_normalize_node = ShaderNodes.Color_Normalize_Node.create_node_tree(None)
    color_normalize_node.use_fake_user = True

def build_quake_shaders(import_settings, object_list):
    base_path = import_settings.base_path
    shaders = {}
    shader_list = []
    found_shader_dir = False

    for shader_path in import_settings.shader_dirs:
        try:
            shader_files = os.listdir(base_path + shader_path)
            shader_list = [base_path + shader_path + file_path
                           for file_path in shader_files
                           if file_path.lower().endswith('.shader')]
            found_shader_dir = True
            break
        except:
            continue
    
    if not found_shader_dir:
        return
    
    material_list = []
    material_names = []
    for object in object_list:
        force_vertex = False
        force_grid = False
        if "LightmapUV" not in object.data.uv_layers:
            force_vertex = True
            if "Color" not in object.data.vertex_colors:
                force_grid = True
        
        for m in object.material_slots:
            if m.material.name not in material_names:
                material_list.append([m, force_vertex, force_grid])
                material_names.append(m.material.name)
    
    for m in material_list:
        index = m[0].material.name.find('.')
        if not (index == -1):
            split_name = m[0].material.name.split(".")
            shader_name = split_name[0]
        else:
            shader_name = m[0].material.name
            
        qs = quake_shader(m[0].material.name, m[0].material)
        if m[1]:
            qs.set_vertex_lit()
        if m[2]:
            qs.set_grid_lit()
            
        if shader_name in shaders:
            shaders[l_format(shader_name)].append(qs)
        else:
            shaders.setdefault(l_format(shader_name),[]).append(qs)
            
    for shader_file in shader_list:
        with open(shader_file, encoding="latin-1") as lines:
            current_shaders = []
            dict_key = ""
            stage = {}
            is_open = 0
            for line in lines:
                #skip empty lines or comments
                if (l_empty(line) or l_comment(line)):
                    continue
                
                #trim line
                line = l_format(line)
                
                #content
                if (not l_open(line) and not l_close(line)):
                    #shader names
                    if is_open == 0:
                        if line in shaders and not current_shaders:
                            current_shaders = shaders[line]
                            dict_key = line
                          
                    #shader attributes
                    elif is_open == 1 and current_shaders:
                        key, value = parse(line)
                        
                        #ugly hack
                        if key == "surfaceparm" and value == "nodraw":
                            for current_shader in current_shaders:
                                current_shader.is_system_shader = True
                        
                        for current_shader in current_shaders:
                            if key in current_shader.attributes:
                                current_shader.attributes[key].append(value)
                            else:
                                current_shader.attributes[key] = [value]
                        
                    #stage info
                    elif is_open == 2 and current_shaders:
                        key, value = parse(line)
                        stage[key] = value
                        
                #marker open
                elif l_open(line):
                    is_open = is_open + 1
                    
                #marker close
                elif l_close(line):
                    #close stage
                    if is_open == 2 and current_shaders:
                        for current_shader in current_shaders:
                            current_shader.add_stage(stage)
                        stage = {}
                        
                    #close material
                    elif is_open == 1 and current_shaders:
                        #finish the shaders and delete them from the list
                        #so we dont double parse them by accident
                        for shader in shaders[dict_key]:
                            shader.finish_shader(base_path, import_settings)
                            
                            #polygon offset to vertex group
                            if "polygonoffset" in shader.attributes:
                                for obj in object_list:
                                    for index, m in enumerate(obj.material_slots):
                                        if m.name == shader.name:
                                            verts = [v for f in obj.data.polygons 
                                                    if f.material_index == index for v in f.vertices]
                                            if len(verts):
                                                vg = obj.vertex_groups.get("Decals")
                                                if vg is None: 
                                                    vg = obj.vertex_groups.new(name = "Decals")
                                                vg.add(verts, 1.0, 'ADD')
                                            break
                                                    
                        del shaders[dict_key]
                        dict_key = ""
                        current_shaders = []
                    
                    is_open -= 1
                    
    #finish remaining none explicit shaders         
    for shader_group in shaders:
        for shader in shaders[shader_group]:
            shader.finish_shader(base_path, import_settings)
            
    return
            
