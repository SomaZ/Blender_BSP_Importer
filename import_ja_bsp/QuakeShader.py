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
                                    "clampmap" : stage.setDiffuse,
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
        if diffuse == "$lightmap":
            stage.lightmap = True
            stage.tcGen = TCGEN_LM
        stage.diffuse = diffuse
        
    def setDepthFunc(stage, depthFunc):
        if depthFunc == "equal":
            stage.skip_alpha = True
        
    def setDepthwrite(stage, empty):
        stage.depthwrite = True
        
    def setDetail(stage, empty):
        stage.detail = True
        
    def setTcGen(stage, tcgen):
        if tcgen == "environment":
            stage.tcGen = TCGEN_ENV
        elif tcgen == "lightmap":
            stage.tcGen = TCGEN_LM
        else:
            print("didn't parse tcGen: ", tcgen)
            
    def setTcMod(stage, tcmod):
        if tcmod.startswith("scale"):
            stage.tcMods.append("scale")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1])
        elif tcmod.startswith("scroll"):
            stage.tcMods.append("scroll")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1])
        elif tcmod.startswith("turb"):
            stage.tcMods.append("turb")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1])
        elif tcmod.startswith("rotate"):
            stage.tcMods.append("rotate")
            stage.tcMods_arguments.append(tcmod.split(" ",1)[1])
        else:
            print("didn't parse tcMod: ", tcmod)
        
    def setLighting(stage, lighting):
        if (lighting == "vertex" or lighting == "exactvertex"):
            stage.lighting = LIGHTING_VERTEX
        elif (lighting == "oneminusvertex"):
            stage.lighting = -LIGHTING_VERTEX
        elif (lighting == "lightingdiffuse"):
            stage.lighting = LIGHTING_LIGHTGRID
        elif (lighting == "identity"):
            stage.lighting = LIGHTING_IDENTITY
        elif (lighting.startswith("const ")):
            stage.lighting = LIGHTING_CONST
            color = filter(None, lighting.strip("\r\n\t").replace("(","").replace(")","").replace("const ","").split(" "))
            stage.color = [float(component) for component in color]
        else:
            stage.lighting = LIGHTING_IDENTITY
            print("didn't parse rgbGen: ", lighting)
            
    def setAlphaClip(stage, compare):
        if compare == "gt0":
            stage.alpha_clip = ACLIP_GT0
        elif compare == "lt128":
            stage.alpha_clip = ACLIP_LT128
        elif compare == "ge128":
            stage.alpha_clip = ACLIP_GE128
        elif compare == "ge192":
            stage.alpha_clip = ACLIP_GE192
        else:
            stage.alpha_clip = ACLIP_NONE
            print("didn't parse alphaFunc: ", compare)
            
    def setBlend(stage, blend):
        if (blend == "add"):
            stage.blend = "gl_one gl_one"
        elif (blend == "filter"):
            stage.blend = "gl_dst_color gl_zero"
        elif (blend == "blend"):
            stage.blend = "gl_src_alpha gl_one_minus_src_alpha"
        elif (blend == "gl_one gl_zero"):
            stage.blend = BLEND_NONE
        else:
            stage.blend = blend
    
    def setAlpha(stage, alpha):
        if (alpha.startswith("const")):
            stage.alpha = ALPHA_CONST
            stage.alpha_value = float(alpha.split(' ', 1)[1])
        elif (alpha == "identity"):
            stage.alpha = ALPHA_CONST
            stage.alpha_value = 1.0
        elif (alpha == "vertex"):
            stage.alpha = ALPHA_VERTEX
        elif (alpha == "oneminusvertex"):
            stage.alpha = -ALPHA_VERTEX
        elif (alpha == "lightingspecular"):
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
                                    "BaseReflectionVector" : [-400.0, 600.0]
                                }
        shader.zoffset = 0
        shader.last_blend = None
        
        shader.is_explicit = False
        shader.is_system_shader = False
        
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
        
        node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
        node_output.name = "Output"
        node_output.location = (4200,0)
        
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
                img = bpy.data.images[stage.diffuse]
            else:
                img = shader.load_image(base_path, stage.diffuse)
            
            if img is not None:        
                node_color = shader.nodes.new(type='ShaderNodeTexImage')
                node_color.image = img
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
            
    def load_image(shader, base_path, texture_path):
        extensions = [ ".png", ".tga", ".jpg" ]
        for extension in extensions:
            if texture_path.endswith(extension):
                texture_path = texture_path.replace(extension,"")
        for extension in extensions:
            try:
                return bpy.data.images.load(base_path + "/" + texture_path + extension, check_existing=True)
            except:
                continue
        print("couldn't load texture: ", texture_path)
        return None
            
    def finish_shader(shader, base_path):
        
        color_out = None
        alpha_out = None
        shader_type = "BLEND"
        
        if shader.is_system_shader:
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
            skyname = shader.attributes["skyparms"].split(" ")[0]
            image = bpy.data.images.get(skyname)
            if image == None:
                image = QuakeSky.make_equirectangular_from_sky(base_path, skyname)
            node_image.image = image
            
            node_geometry = shader.nodes.new(type="ShaderNodeNewGeometry")
            node_geometry.location = (2000,0)
            
            node_scale = shader.nodes.new(type="ShaderNodeVectorMath")
            node_scale.location = (2400,0)
            node_scale.operation = "SCALE"
            node_scale.inputs[2].default_value = -1.0
            
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
                        
                if not shader.is_grid_lit and stage.lighting is LIGHTING_LIGHTGRID:
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
            img = shader.load_image(base_path, shader.texture)
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
                    
                    node_lm = shader.nodes.new(type='ShaderNodeTexImage')
                    node_lm.image = bpy.data.images["$lightmap"]
                    node_lm.location = 1200,-800
                    
                    tc_gen = shader.get_tcGen_node(TCGEN_LM)
                    if tc_gen is not None:
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
            if shader.attributes["cull"] == "twosided":
                shader.mat.use_backface_culling = False
        shader.mat.shadow_method = 'CLIP'
            
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

def l_format(line):
    return line.lower().strip(" \t\r\n")
def l_empty(line):
    return line.strip("\t\r\n") == ' '
def l_comment(line):
    return l_format(line).startswith('/')
def l_open(line):
    return line.startswith('{')
def l_close(line):
    return line.startswith('}')
def parse(line):
    try:
        try:
            key, value = line.split('\t', 1)
        except:
            key, value = line.split(' ', 1)
    except:
        key = line
        value = 1
    return [key, value]

#TODO: overwrite existing Bsp Node instead of making a new one?
def init_shader_system(bsp):
    ShaderNodes.Bsp_Node.create_node_tree(bsp)

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
        for m in object.material_slots:
            if m.name not in material_names:
                material_names.append(m.name)
                material_list.append(m)
    
    for m in material_list:
        index = m.material.name.find('.')
        if not (index == -1):
            split_name = m.material.name.split(".")
            shader_name = split_name[0]
        else:
            shader_name = m.material.name
            
        if shader_name in shaders:
            shaders[l_format(shader_name)].append(quake_shader(m.material.name, m.material))
        else:
            shaders.setdefault(l_format(shader_name),[]).append(quake_shader(m.material.name, m.material))
            
    for shader_file in shader_list:
        with open(shader_file) as lines:
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
                            current_shader.attributes[key] = value
                        
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
                            shader.finish_shader(base_path)
                            
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
            shader.finish_shader(base_path)
            
    return
            