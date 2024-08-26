# ----------------------------------------------------------------------------#
# TODO:  add fog support
# TODO:  fix transparent shaders as good as possible. I think its not possible
#       to support all transparent shaders though :/
# TODO:  add last remaining rgbGens and tcMods
# TODO:  animmap support? Not sure if I want to add this
# TODO:  check if the game loads the shaders in the same order
# TODO:  add portals support
# TODO:  fix tcGen Environment cause right now the
# reflection vector is not correct
# ----------------------------------------------------------------------------#
import bpy
from math import sqrt, log

from . import BlenderImage, ShaderNodes, QuakeLight, QuakeSky
from .idtech3lib import ID3Shader
from .idtech3lib.Parsing import *
from .idtech3lib.ImportSettings import NormalMapOption


if bpy.app.version >= (4, 0, 0):
    EMISSION_KEY = "Emission Color"
else:
    EMISSION_KEY = "Emission"

LIGHTING_NONE = -1
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
        stage.lighting = LIGHTING_NONE
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

        stage.stage_functions = {"map": stage.setDiffuse,
                                 "animmap": stage.setAnimmap,
                                 "clampmap": stage.setClampDiffuse,
                                 "blendfunc": stage.setBlend,
                                 "alphafunc": stage.setAlphaClip,
                                 "tcgen": stage.setTcGen,
                                 "tcmod": stage.setTcMod,
                                 "glow": stage.setGlow,
                                 "alphagen": stage.setAlpha,
                                 "rgbgen": stage.setLighting,
                                 "surfacesprites": stage.setSurfaceSprite,
                                 "depthwrite": stage.setDepthwrite,
                                 "detail": stage.setDetail,
                                 "depthfunc": stage.setDepthFunc
                                 }

    def setDiffuse(stage, diffuse):
        stage_diffuse = diffuse.split()[0]
        if stage_diffuse == "$lightmap":
            stage.lightmap = True
            stage.tcGen = TCGEN_LM
        stage.diffuse = stage_diffuse

    def setClampDiffuse(stage, diffuse):
        stage_diffuse = diffuse.split()[0]
        if stage_diffuse == "$lightmap":
            stage.lightmap = True
            stage.tcGen = TCGEN_LM
        stage.diffuse = stage_diffuse
        stage.clamp = True

    def setAnimmap(stage, diffuse):
        array = diffuse.split()
        # try getting first image of the array
        try:
            stage_diffuse = array[1]
        except Exception:
            print("Could not parse animmap.")
        # I think using the lightmap here is BS so dont check it
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
            arguments = tcmod.split(" ", 1)[1].strip(
                "\r\n\t ").replace("'", "").replace("`", "")
            try:
                arguments = [float(arg) for arg in arguments.split(" ")]
            except Exception as e:
                arguments = [0.0 for arg in arguments.split(" ")]
                print("Error parsing tcMod: ", tcmod, e)
            stage.tcMods_arguments.append(arguments)
        elif tcmod.startswith("scroll"):
            stage.tcMods.append("scroll")
            arguments = tcmod.split(" ", 1)[1].strip(
                "\r\n\t ").replace("'", "").replace("`", "")
            try:
                arguments = [float(arg) for arg in arguments.split(" ")]
            except Exception as e:
                arguments = [0.0 for arg in arguments.split(" ")]
                print("Error parsing tcMod: ", tcmod, e)
            stage.tcMods_arguments.append(arguments)
        elif tcmod.startswith("turb"):
            stage.tcMods.append("turb")
            arguments = tcmod.split(" ", 1)[1].strip(
                "\r\n\t ").replace("'", "").replace("`", "")
            try:
                arguments = [float(arg) for arg in arguments.split(" ")]
            except Exception as e:
                arguments = [0.0 for arg in arguments.split(" ")]
                print("Error parsing tcMod: ", tcmod, e)
            stage.tcMods_arguments.append(arguments)
        elif tcmod.startswith("rotate"):
            stage.tcMods.append("rotate")
            arguments = tcmod.split(" ", 1)[1].strip(
                "\r\n\t ").replace("'", "").replace("`", "")
            try:
                arguments = [float(arg) for arg in arguments.split(" ")]
            except Exception as e:
                arguments = [0.0 for arg in arguments.split(" ")]
                print("Error parsing tcMod: ", tcmod, e)
            stage.tcMods_arguments.append(arguments)
        else:
            print("didn't parse tcMod: ", tcmod)

    def setLighting(stage, lighting):
        if (lighting.startswith("vertex") or
           lighting.startswith("exactvertex")):
            stage.lighting = LIGHTING_VERTEX
        elif (lighting.startswith("oneminusvertex")):
            stage.lighting = -LIGHTING_VERTEX
        elif (lighting.startswith("lightingdiffuse")):
            stage.lighting = LIGHTING_LIGHTGRID
        elif (lighting.startswith("identity")):
            stage.lighting = LIGHTING_IDENTITY
        elif (lighting.startswith("const ")):
            stage.lighting = LIGHTING_CONST
            color = filter(None, lighting.strip("`'\r\n\t").replace(
                "(", "").replace(")", "").replace("const ", "").split())
            try:
                stage.color = [float(component) for component in color]
            except Exception:
                stage.color = [1.0, 1.0, 1.0]
                print("rgbGen const with no proper values found")
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
                stage.alpha_value = float(alpha.split()[1].strip(
                    "\r\n\t ").replace("'", "").replace("`", ""))
            except Exception:
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
        elif (stage.blend == "gl_zero gl_one"):
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
        shader.is_fog = False
        shader.name = name
        shader.texture = name
        shader.mat = material
        shader.mat.use_nodes = True
        shader.nodes = shader.mat.node_tree.nodes
        shader.nodes.clear()
        shader.links = shader.mat.node_tree.links
        #   "name"          : Position
        shader.static_nodes = {"tcNormal": [-400.0, 10.0],
                               "tcLightmap": [-400.0, -100.0],
                               "tcEnvironment": [-400.0, -200.0],
                               "vertexColor": [-400.0, 400.0],
                               "vertexAlpha": [-400.0, 200.0],
                               "specularAlpha": [-400.0, -800.0],
                               "gridColor": [-400.0, 600.0],
                               "shaderTime": [-800.0, 0.0],
                               "BaseReflectionVector": [-400.0, 600.0],
                               "EmissionScaleNode": [2600.0, -600.0],
                               }

        shader.zoffset = 0
        shader.last_blend = None

        shader.is_explicit = False
        shader.is_system_shader = True if name.startswith(
            "noshader") else False

        shader.stages = []
        shader.attributes = {}

        shader.current_x_location = 200
        shader.current_y_location = 800

        index = name.rfind('.')
        if not (index == -1):
            split_name = shader.name.split(".")
            shader.texture = split_name[0]
            
            if name.endswith(".fog"):
                shader.texture = shader.name[:-len(".fog")]
                shader.is_fog = True

            if name.endswith(".vertex"):
                shader.is_vertex_lit = True

            if split_name[1].endswith("grid"):
                shader.is_grid_lit = True

                split_name[1] = split_name[1].replace("grid", "")
                if (len(split_name) > 1) and not (split_name[1] == ""):
                    shader.zoffset = split_name[1]

            if name.endswith(".brush"):
                shader.is_brush = True

            if name.endswith(".nodraw"):
                shader.is_system_shader = True

        node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
        node_output.name = "Output"
        node_output.location = (4200, 0)

    def set_vertex_lit(shader):
        shader.is_vertex_lit = True
        shader.is_grid_lit = False

    def set_grid_lit(shader):
        shader.is_vertex_lit = False
        shader.is_grid_lit = True

    def get_node_by_name(shader, name):
        node = shader.nodes.get(name)
        if node is None:
            return ShaderNodes.create_static_node(shader, name)
        return node

    def get_rgbGen_node(shader, rgbGen):
        if rgbGen == LIGHTING_IDENTITY or rgbGen == LIGHTING_NONE:
            return None
        if rgbGen == LIGHTING_VERTEX:
            return shader.get_node_by_name("vertexColor")
        elif rgbGen == LIGHTING_LIGHTGRID:
            return shader.get_node_by_name("gridColor")
        elif rgbGen == LIGHTING_CONST:
            color_node = shader.nodes.new(type='ShaderNodeRGB')
            color_node.location = (
                shader.current_x_location + 200,
                shader.current_y_location - 500)
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
            node.location = (shader.current_x_location + 200,
                             shader.current_y_location - 300)
            return node
        elif alphaGen == ALPHA_VERTEX:
            return shader.get_node_by_name("vertexAlpha")
        elif alphaGen == ALPHA_SPEC:
            spec_node = shader.get_node_by_name("specularAlpha")
            if shader.is_grid_lit:
                shader.links.new(shader.get_rgbGen_node(
                    LIGHTING_LIGHTGRID).outputs["LightGridVector"],
                    spec_node.inputs["LightVector"])
            else:
                shader.links.new(shader.get_node_by_name(
                    "BaseReflectionVector").outputs["Vector"],
                    spec_node.inputs["LightVector"])
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
                new_out_node.location = (0, 0)
                if out_node is not None:
                    shader.links.new(
                        out_node.outputs[0],
                        new_out_node.inputs["Vector"])
                out_node = new_out_node

                ags = arguments
                if ags[0] == "fromentity":
                    print("tcMod scale fromentity is not supported")
                elif len(ags) > 1:
                    out_node.inputs["Scale"].default_value[0] = float(ags[0])
                    out_node.inputs["Scale"].default_value[1] = float(ags[1])
                    out_node.inputs["Location"].default_value[1] = -float(ags[1])
                elif len(ags) == 1:
                    print("tcMod scale with too few arguments")
                    out_node.inputs["Scale"].default_value[0] = float(ags[0])
                    out_node.inputs["Scale"].default_value[1] = float(ags[0])
                    out_node.inputs["Location"].default_value[1] = -float(ags[0])
                else:
                    print("tcMod scale with no arguments")
                
            elif tcMod == "rotate":
                time_node = shader.get_node_by_name("shaderTime")
                new_out_node = shader.nodes.new(type="ShaderNodeGroup")
                new_out_node.name = "tcMod"
                new_out_node.node_tree = (
                    ShaderNodes.Shader_Rotate_Node.get_node_tree(None))
                new_out_node.location = (
                    shader.current_x_location - 200,
                    shader.current_y_location)
                ags = arguments
                if ags[0] == "fromentity":
                    print("tcMod rotate fromentity is not supported")
                elif len(ags) >= 1:
                    new_out_node.inputs["Degrees"].default_value = float(ags[0])
                else:
                    print("tcMod rotate with no arguments")
                shader.links.new(
                    time_node.outputs["Time"],
                    new_out_node.inputs["Time"])
                if out_node is not None:
                    shader.links.new(
                        out_node.outputs[0],
                        new_out_node.inputs["Vector"])
                out_node = new_out_node

            elif tcMod == "scroll":
                time_node = shader.get_node_by_name("shaderTime")
                new_out_node = shader.nodes.new(type="ShaderNodeGroup")
                new_out_node.name = "tcMod"
                new_out_node.node_tree = (
                    ShaderNodes.Shader_Scroll_Node.get_node_tree(None))
                new_out_node.location = (
                    shader.current_x_location - 200,
                    shader.current_y_location)
                ags = arguments
                if ags[0] == "fromentity":
                    print("tcMod scroll fromentity is not supported")
                elif len(ags) > 1:
                    new_out_node.inputs["Arguments"].default_value = [
                        float(ags[0]), float(ags[1]), 0.0]
                elif len(ags) == 1:
                    print("tcMod scroll with too few arguments")
                    new_out_node.inputs["Arguments"].default_value = [
                        float(ags[0]), float(ags[0]), 0.0]
                else:
                    print("tcMod scroll with no arguments")
                shader.links.new(
                    time_node.outputs["Time"],
                    new_out_node.inputs["Time"])
                if out_node is not None:
                    shader.links.new(
                        out_node.outputs[0],
                        new_out_node.inputs["Vector"])
                out_node = new_out_node
            else:
                print("unsupported tcMod: ", tcMod, " ", arguments)
        return out_node

    def build_stage_nodes(shader, VFS, stage, color_out, alpha_out):
        loc_x = shader.current_x_location
        loc_y = shader.current_y_location
        new_color_out = color_out
        new_alpha_out = alpha_out
        node_blend = None
        if stage.valid:
            img = bpy.data.images.get(stage.diffuse)
            if img is None:
                img = BlenderImage.load_file(stage.diffuse, VFS)

            if img is not None:
                node_color = shader.nodes.new(type='ShaderNodeTexImage')
                node_color.image = img
                if stage.clamp:
                    node_color.extension = 'EXTEND'
                node_color.location = loc_x + 200, loc_y
                tc_gen = shader.get_tcGen_node(stage.tcGen)
                if tc_gen is not None:
                    tc_mod = shader.get_tcMod_node(
                        stage.tcMods, stage.tcMods_arguments)
                    if tc_mod is None:
                        shader.links.new(
                            tc_gen.outputs["UV"],
                            node_color.inputs["Vector"])
                    else:
                        shader.links.new(
                            tc_gen.outputs["UV"],
                            tc_mod.inputs["Vector"])
                        shader.links.new(
                            tc_mod.outputs[0],
                            node_color.inputs["Vector"])

                lighting = shader.get_rgbGen_node(stage.lighting)
                if stage.lighting == LIGHTING_CONST:
                    lighting.outputs[0].default_value = (
                        stage.color[0], stage.color[1], stage.color[2], 1.0)

                new_color_out = node_color.outputs["Color"]
                new_alpha_out = node_color.outputs["Alpha"]

                # clamp alpha if needed
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

                # handle blends
                if stage.blend != BLEND_NONE:
                    node_blend = shader.nodes.new(type="ShaderNodeGroup")

                    node_blend.name = stage.blend
                    node_blend.node_tree = (
                        ShaderNodes.Blend_Node.get_node_tree(stage.blend))
                    node_blend.location = loc_x + 800, loc_y - 200
                    shader.last_blend = node_blend
                    if color_out is not None:
                        shader.links.new(
                            color_out, node_blend.inputs["DestinationColor"])
                    if alpha_out is not None:
                        shader.links.new(
                            alpha_out, node_blend.inputs["DestinationAlpha"])

                    shader.links.new(
                        new_color_out, node_blend.inputs["SourceColor"])

                    # handle stage alpha
                    alpha_node = shader.get_alphaGen_node(
                        stage.alpha, stage.alpha_value)
                    if alpha_node is None:
                        shader.links.new(
                            new_alpha_out, node_blend.inputs["SourceAlpha"])
                    else:
                        shader.links.new(
                            alpha_node.outputs[0],
                            node_blend.inputs["SourceAlpha"])

                    new_color_out = node_blend.outputs["OutColor"]
                    new_alpha_out = node_blend.outputs["OutAlpha"]

                # handle rgbGens
                if lighting is not None:
                    if node_blend is not None:
                        shader.links.new(
                            lighting.outputs[0], node_blend.inputs["rgbGen"])
                    else:
                        node_rgbGen = shader.nodes.new(type='ShaderNodeMixRGB')
                        node_rgbGen.name = "rgbGen"
                        node_rgbGen.location = (loc_x+800, loc_y-200)
                        node_rgbGen.blend_type = 'MULTIPLY'
                        node_rgbGen.inputs[0].default_value = 1.0
                        shader.links.new(
                            new_color_out, node_rgbGen.inputs["Color1"])
                        shader.links.new(
                            lighting.outputs[0], node_rgbGen.inputs["Color2"])
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

    def finish_rendering_shader(shader, VFS, import_settings):
        out_Color = None
        out_Alpha = None
        out_Glow = None
        out_Normal = None
        out_None = None
        shader_atts = shader.attributes
        # we dont want the system shaders and "those" skys
        if (shader.is_system_shader or 
            "skyparms" in shader_atts or 
            "fogparms" in shader_atts):
            shader.nodes.clear()
            node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
            node_output.name = "Output"
            node_output.location = (3400, 0)
            node_BSDF = shader.nodes.new(type="ShaderNodeBsdfTransparent")
            node_BSDF.name = "Out_BSDF"
            node_BSDF.location = (3000, 0)
            shader.links.new(node_BSDF.outputs["BSDF"], node_output.inputs[0])
            shader.mat.blend_method = "BLEND"

            if "skyparms" in shader_atts:
                skyname = shader_atts["skyparms"][0].split()[0]
                image = bpy.data.images.get(skyname)
                if image is None:
                    image = QuakeSky.make_equirectangular_from_sky(
                        VFS, skyname)

                bg_node = bpy.context.scene.world.node_tree.nodes.get(
                    "Background")
                im_node = bpy.context.scene.world.node_tree.nodes.get("SkyTex")
                if im_node is None:
                    im_node = bpy.context.scene.world.node_tree.nodes.new(
                        type="ShaderNodeTexEnvironment")
                    im_node.name = "SkyTex"
                    im_node.location = im_node.location[0] - \
                        800, im_node.location[1]
                im_node.image = image

                lp_node = bpy.context.scene.world.node_tree.nodes.get(
                    "LightPath")
                if lp_node is None:
                    lp_node = bpy.context.scene.world.node_tree.nodes.new(
                        type="ShaderNodeLightPath")
                    lp_node.name = "LightPath"
                    lp_node.location = (im_node.location[0],
                                        im_node.location[1] + 600)

                lt_node = bpy.context.scene.world.node_tree.nodes.get(
                    "LessThan")
                if lt_node is None:
                    lt_node = bpy.context.scene.world.node_tree.nodes.new(
                        type="ShaderNodeMath")
                    lt_node.name = "LessThan"
                    lt_node.operation = "LESS_THAN"
                    lt_node.inputs[1].default_value = 1.0
                    lt_node.location = im_node.location[0] + \
                        200, im_node.location[1] + 400

                mx_node = bpy.context.scene.world.node_tree.nodes.get("Mix")
                if mx_node is None:
                    mx_node = bpy.context.scene.world.node_tree.nodes.new(
                        type="ShaderNodeMixRGB")
                    mx_node.name = "Mix"
                    mx_node.inputs[2].default_value = (0.0, 0.0, 0.0, 1.0)
                    mx_node.location = im_node.location[0] + \
                        600, im_node.location[1] + 300

                bpy.context.scene.world.node_tree.links.new(
                    lp_node.outputs["Transparent Depth"], lt_node.inputs[0])
                bpy.context.scene.world.node_tree.links.new(
                    lt_node.outputs[0], mx_node.inputs["Fac"])
                bpy.context.scene.world.node_tree.links.new(
                    im_node.outputs["Color"], mx_node.inputs[1])
                bpy.context.scene.world.node_tree.links.new(
                    mx_node.outputs["Color"], bg_node.inputs["Color"])

            if "sun" in shader_atts:
                for i, sun_parms in enumerate(shader_atts["sun"]):
                    QuakeSky.add_sun(shader.name, "sun", sun_parms, i)
            if "q3map_sun" in shader_atts:
                for i, sun_parms in enumerate(shader_atts["q3map_sun"]):
                    QuakeSky.add_sun(shader.name, "q3map_sun", sun_parms, i)
            if "q3map_sunext" in shader_atts:
                for i, sun_parms in enumerate(shader_atts["q3map_sunext"]):
                    QuakeSky.add_sun(shader.name, "q3map_sunext", sun_parms, i)
            if "q3gl2_sun" in shader_atts:
                for i, sun_parms in enumerate(shader_atts["q3gl2_sun"]):
                    QuakeSky.add_sun(shader.name, "q3gl2_sun", sun_parms, i)

            node_lm = shader.nodes.new(type='ShaderNodeTexImage')
            node_lm.location = 700, 0

            vertmap = bpy.data.images.get("$vertmap_bake")
            if vertmap is None:
                vertmap = bpy.data.images.new(
                    "$vertmap_bake", width=2048, height=2048)
            node_lm.image = vertmap

            tc_gen = shader.get_tcGen_node(TCGEN_LM)
            if tc_gen is not None:
                shader.links.new(
                    tc_gen.outputs["UV"], node_lm.inputs["Vector"])

            node_lm.select = True
            shader.nodes.active = node_lm
            shader.mat.shadow_method = 'NONE'
            return

        elif shader.is_explicit:
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
                        shader_type = "CLIP"
                        shader.mat.blend_method = "CLIP"
                    if stage.blend != BLEND_NONE:
                        shader_type = "ADD"
                        shader.mat.blend_method = "BLEND"
                else:
                    if (stage.blend.endswith("gl_one_minus_src_alpha") and
                       shader_type == "ADD"):
                        shader_type = "BLEND"
                        shader.mat.blend_method = "BLEND"
                    if (stage.blend.endswith("gl_src_alpha") and
                       shader_type == "ADD"):
                        shader_type = "BLEND"
                        shader.mat.blend_method = "BLEND"
                    if (stage.blend.endswith("gl_src_color") and
                       shader_type == "ADD" and not stage.lightmap):
                        shader_type = "MULTIPLY"
                        shader.mat.blend_method = "BLEND"
                    if (stage.blend.startswith("gl_dst_color") and
                       shader_type == "ADD" and not stage.lightmap):
                        shader_type = "MULTIPLY"
                        shader.mat.blend_method = "BLEND"

                if stage.blend.endswith("gl_zero") and not stage.skip_alpha:
                    shader_type = "OPAQUE" if shader_type != "CLIP" else "CLIP"
                    shader.mat.blend_method = (
                        "OPAQUE"
                        if shader.mat.blend_method != "CLIP"
                        else "CLIP"
                    )

                stage_index += 1

                if stage.lightmap:
                    continue
                if (stage.tcGen == TCGEN_LM and
                   stage.diffuse.startswith("maps/")):
                    continue
                if stage.tcGen == TCGEN_ENV:
                    continue
                if stage.alpha == ALPHA_SPEC:
                    continue

                if (stage.lighting == LIGHTING_VERTEX or
                   stage.lighting == LIGHTING_LIGHTGRID):
                    stage.lighting = 0

                if added_stages == 0:
                    if shader_type == "OPAQUE":
                        stage.blend = "gl_one gl_zero"
                    if "portal" in shader.attributes:
                        stage.blend = "gl_one gl_zero"

                if stage.glow or stage.blend == "gl_one gl_one":
                    out_Glow, out_None = shader.build_stage_nodes(VFS,
                                                                  stage,
                                                                  out_Glow,
                                                                  out_Alpha)
                else:
                    out_Color, out_Alpha = shader.build_stage_nodes(VFS,
                                                                    stage,
                                                                    out_Color,
                                                                    out_Alpha)
                shader.current_x_location += 300
                shader.current_y_location -= 600
                added_stages += 1

            node_light = None
            if "q3map_lightimage" in shader.attributes:
                img = BlenderImage.load_file(
                    shader.attributes["q3map_lightimage"][0], VFS)
                if img is not None:
                    node_light = shader.nodes.new(type='ShaderNodeTexImage')
                    node_light.image = img
                    node_light.location = 2600, 0
            elif "q3map_lightrgb" in shader.attributes:
                color = shader.attributes["q3map_lightrgb"][0].split()
                if len(color) >= 2:
                    try:
                        color = QuakeLight.SRGBToLinear(
                            (float(color[0]), float(color[1]), float(color[2])))
                    except Exception:
                        print("q3map_lightrgb with no proper values found")
                        color = [1.0, 1.0, 1.0]
                    node_light = shader.nodes.new(type='ShaderNodeRGB')
                    node_light.outputs[0].default_value = (
                        color[0], color[1], color[2], 1.0)
            if ("q3map_normalimage" in shader.attributes and 
                 import_settings.normal_map_option != NormalMapOption.SKIP.value):
                normal_img = BlenderImage.load_file(
                    shader.attributes["q3map_normalimage"][0], VFS)
                if normal_img is not None:
                    normal_img.colorspace_settings.name = "Non-Color"
                    node_normalimage = shader.nodes.new(type='ShaderNodeTexImage')
                    node_normalimage.image = normal_img
                    node_normalimage.location = 1500, 0

                    node_channelflip = shader.nodes.new(type="ShaderNodeMapping")
                    node_channelflip.inputs[1].default_value[1] = 1
                    node_channelflip.inputs[3].default_value[1] = -1
                    node_channelflip.location = 1800, 0
                    node_channelflip.width = 300
                    node_channelflip.label = "Green Channel Flip"
                    shader.links.new(
                        node_normalimage.outputs["Color"], node_channelflip.inputs[0])
                    node_channelflip.mute = (
                        import_settings.normal_map_option != NormalMapOption.DIRECTX.value)

                    node_normalmap = shader.nodes.new(type='ShaderNodeNormalMap')
                    node_normalmap.uv_map = "UVMap"
                    node_normalmap.location = 2200, 0
                    node_normalmap.name = "q3map_normalimage output"
                    shader.links.new(
                        node_channelflip.outputs[0], node_normalmap.inputs["Color"])
                    out_Normal = node_normalmap.outputs["Normal"]

            if out_Color is not None:
                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
                node_BSDF.location = (3000, 0)
                node_BSDF.inputs["Roughness"].default_value = 0.9999
                shader.links.new(out_Color, node_BSDF.inputs["Base Color"])
                if out_Glow is not None or node_light is not None:
                    new_node = shader.get_node_by_name("EmissionScaleNode")
                    shader.links.new(
                        new_node.outputs[0], node_BSDF.inputs[EMISSION_KEY])
                    if out_Glow is not None:
                        shader.links.new(out_Glow, new_node.inputs[2])
                    if node_light is not None:
                        shader.links.new(
                            node_light.outputs[0], new_node.inputs[0])
                    if "q3map_surfacelight" in shader.attributes:
                        try:
                            new_node.inputs[1].default_value = (
                                float(shader.attributes["q3map_surfacelight"][0]) /
                                1000.0)
                        except Exception:
                            print("Could not set q3map_surfacelight to",
                                  shader.attributes["q3map_surfacelight"][0],
                                  "\nq3map_surfacelight assumes a float input")
                    if bpy.app.version >= (4, 0, 0):
                        node_BSDF.inputs["Emission Strength"].default_value = 1.0
                if (shader_type != "OPAQUE" and
                   out_Alpha is not None and
                   "portal" not in shader.attributes):
                    shader.links.new(out_Alpha, node_BSDF.inputs["Alpha"])
                shader.links.new(
                    node_BSDF.outputs["BSDF"],
                    shader.nodes["Output"].inputs[0])
                if out_Normal is not None:
                    shader.links.new(out_Normal, node_BSDF.inputs["Normal"])
            else:
                shader.mat.blend_method = "BLEND"
                node_Emiss = shader.nodes.new(type="ShaderNodeEmission")
                node_Emiss.location = (3000, 0)
                if out_Glow is not None or node_light is not None:
                    new_node = shader.get_node_by_name("EmissionScaleNode")
                    shader.links.new(
                        new_node.outputs[0], node_Emiss.inputs["Color"])
                    if out_Glow is not None:
                        shader.links.new(out_Glow, new_node.inputs[2])
                    if node_light is not None:
                        shader.links.new(
                            node_light.outputs[0], new_node.inputs[0])
                    if "q3map_surfacelight" in shader.attributes:
                        try:
                            new_node.inputs[1].default_value = (
                                float(shader.attributes["q3map_surfacelight"][0]) /
                                1000.0)
                        except Exception:
                            print("Could not set q3map_surfacelight to",
                                  shader.attributes["q3map_surfacelight"][0],
                                  "\nq3map_surfacelight assumes a float input")
                else:
                    node_Emiss.inputs["Color"].default_value = (
                        0.0, 0.0, 0.0, 1.0)

                node_transparent = shader.nodes.new(
                    type="ShaderNodeBsdfTransparent")
                node_transparent.location = (3000, -300)

                node_BSDF = shader.nodes.new(type="ShaderNodeAddShader")
                node_BSDF.location = (3300, 0)
                shader.links.new(
                    node_Emiss.outputs["Emission"], node_BSDF.inputs[0])
                shader.links.new(
                    node_transparent.outputs[0], node_BSDF.inputs[1])
                shader.links.new(
                    node_BSDF.outputs[0], shader.nodes["Output"].inputs[0])

        else:
            img = BlenderImage.load_file(shader.texture, VFS)
            if img is not None:
                img.alpha_mode = "CHANNEL_PACKED"
                node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                node_texture.image = img
                node_texture.location = 1200, 0

                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
                node_BSDF.location = (3000, 0)
                node_BSDF.inputs["Roughness"].default_value = 0.9999
                shader.links.new(
                    node_texture.outputs["Color"],
                    node_BSDF.inputs["Base Color"])
                shader.links.new(
                    node_BSDF.outputs["BSDF"],
                    shader.nodes["Output"].inputs[0])
            else:
                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
                node_BSDF.location = (3000, 0)
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
            if out_Alpha is not None:
                shader.links.new(out_Alpha, node_mix.inputs[0])
            shader.links.new(
                node_mix.outputs[0], shader.nodes["Output"].inputs[0])
            shader.mat.blend_method = "OPAQUE"

        # max size for internal lightmaps (256 Lightmaps at 128x128)
        lm_size = 2048
        orig_lm = bpy.data.images.get("$lightmap")
        if orig_lm is not None:
            lm_size = orig_lm.size[0]

        lm_image = bpy.data.images.get("$lightmap_bake")
        if lm_image is None:
            lm_image = bpy.data.images.new(
                "$lightmap_bake",
                width=lm_size,
                height=lm_size,
                float_buffer=True)
        vt_image = bpy.data.images.get("$vertmap_bake")
        if vt_image is None:
            vt_image = bpy.data.images.new(
                "$vertmap_bake",
                width=2048,
                height=2048,
                float_buffer=True)

        node_lm = shader.nodes.new(type='ShaderNodeTexImage')
        node_lm.location = 0, -400
        node_lm.name = "Baking Image"
        if shader.is_vertex_lit:
            node_lm.image = vt_image
            for stage in shader.stages:
                if (stage.tcGen == TCGEN_LM and
                   stage.diffuse.startswith("maps/")):
                    image = BlenderImage.load_file(stage.diffuse, VFS)
                    if image is not None:
                        node_lm.image = image
        else:
            node_lm.image = lm_image

        if node_BSDF is None and node_BSDF.inputs.get("Normal"):
            normal_node = shader.get_node_by_name("NormalSetNode")
            normal_node.location = 700, -500
            shader.links.new(
                normal_node.outputs[0], node_BSDF.inputs["Normal"])

        tc_gen = shader.get_tcGen_node(TCGEN_LM)
        if tc_gen is not None:
            shader.links.new(tc_gen.outputs["UV"], node_lm.inputs["Vector"])

        shader.mat.use_backface_culling = True
        if "cull" in shader.attributes:
            if (shader.attributes["cull"][0] == "twosided" or
               shader.attributes["cull"][0] == "none"):
                shader.mat.use_backface_culling = False

        if shader.mat.use_backface_culling:
            mx_node = shader.nodes.new(type="ShaderNodeMixShader")
            mx_node.location = 3800, 0
            tp_node = shader.nodes.new(type="ShaderNodeBsdfTransparent")
            tp_node.location = 3300, -400
            gm_node = shader.nodes.new(type="ShaderNodeNewGeometry")
            gm_node.location = 3300, 600
            shader.links.new(gm_node.outputs["Backfacing"], mx_node.inputs[0])
            shader.links.new(node_BSDF.outputs[0], mx_node.inputs[1])
            shader.links.new(tp_node.outputs["BSDF"], mx_node.inputs[2])
            shader.links.new(
                mx_node.outputs[0], shader.nodes["Output"].inputs[0])
            shader.nodes["Output"].target = "CYCLES"

            eevee_out = shader.nodes.new(type="ShaderNodeOutputMaterial")
            eevee_out.location = 4200, -300
            eevee_out.name = "EeveeOut"
            eevee_out.target = "EEVEE"
            shader.links.new(node_BSDF.outputs[0], eevee_out.inputs[0])

        shader.mat.shadow_method = 'CLIP'

        node_lm.select = True
        shader.nodes.active = node_lm

    def finish_preview_shader(shader, VFS, import_settings):

        color_out = None
        alpha_out = None
        normal_out = None
        shader_type = "BLEND"

        if (shader.is_system_shader or 
            "fogparms" in shader.attributes):
            if import_settings.preset != 'EDITING' or "fogparms" in shader.attributes:
                shader.nodes.clear()
                node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
                node_output.name = "Output"
                node_output.location = (3400, 0)
                node_BSDF = shader.nodes.new(type="ShaderNodeBsdfTransparent")
                node_BSDF.name = "Out_BSDF"
                node_BSDF.location = (3000, 0)
                shader.links.new(
                    node_BSDF.outputs["BSDF"], node_output.inputs[0])
                shader.mat.blend_method = "BLEND"
                return
            else:
                shader.is_explicit = False
                shader.mat.blend_method = "BLEND"

        if "skyparms" in shader.attributes:
            shader.nodes.clear()
            node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
            node_output.name = "Output"
            node_output.location = (3400, 0)
            node_BSDF = shader.nodes.new(type="ShaderNodeEmission")
            node_BSDF.name = "Out_BSDF"
            node_BSDF.location = (3000, 0)

            node_image = shader.nodes.new(type="ShaderNodeTexEnvironment")
            node_image.location = (2800, 0)
            skyname = shader.attributes["skyparms"][0].split()[0]
            image = bpy.data.images.get(skyname)
            if image is None:
                image = QuakeSky.make_equirectangular_from_sky(
                    VFS, skyname)
            node_image.image = image

            node_geometry = shader.nodes.new(type="ShaderNodeNewGeometry")
            node_geometry.location = (2000, 0)

            node_scale = shader.nodes.new(type="ShaderNodeVectorMath")
            node_scale.location = (2400, 0)
            node_scale.operation = "SCALE"
            node_scale.inputs["Scale"].default_value = -1.0

            shader.links.new(
                node_geometry.outputs["Incoming"], node_scale.inputs[0])
            shader.links.new(
                node_scale.outputs["Vector"], node_image.inputs["Vector"])

            shader.links.new(
                node_image.outputs["Color"], node_BSDF.inputs["Color"])
            shader.links.new(node_BSDF.outputs[0], node_output.inputs[0])
            shader.mat.use_backface_culling = True
            return

        elif shader.is_explicit:
            stage_index = 0
            n_stages = 0

            explicitly_depthwritten = False
            lightmap_available = bpy.data.images.get("$lightmap") is not None

            for stage in shader.stages:

                if stage_index == 0:
                    if stage.blend == "gl_one gl_src_alpha":
                        stage.blend = "gl_one_minus_src_alpha gl_zero"
                    if stage.blend == "gl_one gl_one_minus_src_alpha":
                        stage.blend = "gl_src_alpha gl_zero"
                    if stage.alpha_clip != ACLIP_NONE:
                        shader_type = "CLIP"
                        shader.mat.blend_method = "CLIP"
                    if stage.blend != BLEND_NONE:
                        shader_type = "ADD"
                        shader.mat.blend_method = "BLEND"
                    if (shader.is_vertex_lit and
                       stage.lighting is LIGHTING_NONE):
                        stage.lighting = LIGHTING_VERTEX
                    if (shader.is_grid_lit and
                       stage.lighting is LIGHTING_NONE):
                        stage.lighting = LIGHTING_LIGHTGRID

                if stage.blend.endswith("gl_zero") and not stage.skip_alpha:
                    shader_type = "OPAQUE" if shader_type != "CLIP" else "CLIP"
                    shader.mat.blend_method = (
                        "OPAQUE"
                        if shader.mat.blend_method != "CLIP"
                        else "CLIP"
                    )

                if (not shader.is_grid_lit and
                   stage.lighting is LIGHTING_LIGHTGRID):
                    stage.lighting = LIGHTING_VERTEX

                if stage.lightmap and not lightmap_available:
                    stage.diffuse = "$whiteimage"
                    stage.lighting = LIGHTING_VERTEX

                # TODO: proper handling of additive and multiplicative shaders
                if (stage.blend.endswith("gl_one_minus_src_alpha") and
                   shader_type == "ADD"):
                    shader_type = "BLEND"
                    shader.mat.blend_method = "BLEND"

                if (stage.blend.endswith("gl_src_alpha") and
                   shader_type == "ADD"):
                    shader_type = "BLEND"
                    shader.mat.blend_method = "BLEND"

                if (stage.blend.endswith("gl_src_color") and
                   shader_type == "ADD" and not stage.lightmap):
                    shader_type = "MULTIPLY"
                    shader.mat.blend_method = "BLEND"

                if (stage.blend.startswith("gl_dst_color") and
                   shader_type == "ADD" and not stage.lightmap):
                    shader_type = "MULTIPLY"
                    shader.mat.blend_method = "BLEND"

                if shader_type == "MULTIPLY" and color_out is None:
                    node_color = shader.nodes.new(type='ShaderNodeRGB')
                    node_color.location = (shader.current_x_location,
                                           shader.current_y_location + 400)
                    node_color.outputs[0].default_value = (1, 1, 1, 1)
                    node_value = shader.nodes.new(type="ShaderNodeValue")
                    node_value.location = (shader.current_x_location,
                                           shader.current_y_location + 200)
                    node_value.outputs[0].default_value = 1.0
                    color_out = node_color.outputs[0]
                    alpha_out = node_value.outputs[0]

                if stage.depthwrite:
                    if stage.blend != BLEND_NONE and shader_type == "ADD":
                        shader.mat.blend_method = "BLEND"
                    if (stage.alpha_clip != ACLIP_NONE and
                       shader.mat.blend_method != "OPAQUE"):
                        shader_type = "CLIP"
                        shader.mat.blend_method = "CLIP"

                stage_index += 1

                if shader.is_vertex_lit and stage.lightmap:
                    if color_out is None:
                        color_out = shader.get_rgbGen_node(
                            LIGHTING_VERTEX).outputs[0]
                    elif shader.last_blend is not None:
                        shader.links.new(
                            shader.get_rgbGen_node(LIGHTING_VERTEX).outputs[0],
                            shader.last_blend.inputs['rgbGen'])
                elif shader.is_grid_lit and stage.lightmap:
                    if color_out is None:
                        color_out = shader.get_rgbGen_node(
                            LIGHTING_LIGHTGRID).outputs[0]
                    elif shader.last_blend is not None:
                        shader.links.new(
                            shader.get_rgbGen_node(
                                LIGHTING_LIGHTGRID).outputs[0],
                            shader.last_blend.inputs['rgbGen'])
                else:
                    if stage.skip_alpha:
                        color_out, none_out = (
                            shader.build_stage_nodes(
                                VFS,
                                stage,
                                color_out,
                                alpha_out))
                    else:
                        color_out, alpha_out = (
                            shader.build_stage_nodes(
                                VFS,
                                stage,
                                color_out,
                                alpha_out))

                shader.current_x_location += 300
                shader.current_y_location -= 600
                n_stages += 1

            if ("q3map_normalimage" in shader.attributes and 
                 import_settings.normal_map_option != NormalMapOption.SKIP.value):
                normal_img = BlenderImage.load_file(
                    shader.attributes["q3map_normalimage"][0], VFS)
                if normal_img is not None:
                    normal_img.colorspace_settings.name = "Non-Color"
                    node_normalimage = shader.nodes.new(type='ShaderNodeTexImage')
                    node_normalimage.image = normal_img
                    node_normalimage.location = 1500, 400

                    node_channelflip = shader.nodes.new(type="ShaderNodeMapping")
                    node_channelflip.inputs[1].default_value[1] = 1
                    node_channelflip.inputs[3].default_value[1] = -1
                    node_channelflip.location = 1800, 400
                    node_channelflip.width = 300
                    node_channelflip.label = "Green Channel Flip"
                    shader.links.new(
                        node_normalimage.outputs["Color"], node_channelflip.inputs[0])
                    node_channelflip.mute = (
                        import_settings.normal_map_option != NormalMapOption.DIRECTX.value)

                    node_normalmap = shader.nodes.new(type='ShaderNodeNormalMap')
                    node_normalmap.uv_map = "UVMap"
                    node_normalmap.location = 2200, 400
                    node_normalmap.name = "q3map_normalimage output"
                    shader.links.new(
                        node_channelflip.outputs[0], node_normalmap.inputs["Color"])
                    normal_out = node_normalmap.outputs["Normal"]

            if color_out is None:
                print(shader.name + " shader is not supported right now")

        else:
            img = BlenderImage.load_file(shader.texture, VFS)
            if img is not None:
                img.alpha_mode = "CHANNEL_PACKED"
                if shader.is_vertex_lit:
                    node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                    node_texture.image = img
                    node_texture.location = 1200, 0
                    node_blend = shader.nodes.new(type='ShaderNodeMixRGB')
                    node_blend.blend_type = 'MULTIPLY'
                    node_blend.inputs[0].default_value = 1.0
                    node_blend.location = 1600, -200
                    shader.links.new(
                        node_texture.outputs["Color"],
                        node_blend.inputs['Color1'])
                    shader.links.new(shader.get_rgbGen_node(
                        LIGHTING_VERTEX).outputs[0],
                        node_blend.inputs['Color2'])
                    color_out = node_blend.outputs["Color"]
                elif shader.is_grid_lit:
                    node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                    node_texture.image = img
                    node_texture.location = 1200, 0
                    node_blend = shader.nodes.new(type='ShaderNodeMixRGB')
                    node_blend.blend_type = 'MULTIPLY'
                    node_blend.inputs[0].default_value = 1.0
                    node_blend.location = 1600, -200
                    shader.links.new(
                        node_texture.outputs["Color"],
                        node_blend.inputs["Color1"])
                    shader.links.new(shader.get_rgbGen_node(
                        LIGHTING_LIGHTGRID).outputs[0],
                        node_blend.inputs["Color2"])
                    color_out = node_blend.outputs["Color"]
                else:
                    node_texture = shader.nodes.new(type='ShaderNodeTexImage')
                    node_texture.image = img

                    node_texture.location = 1200, 0

                    lightmap = bpy.data.images.get("$lightmap")
                    if lightmap is None:
                        node_lm = shader.get_rgbGen_node(LIGHTING_VERTEX)
                        node_lm.location = 1200, -800
                    else:
                        node_lm = shader.nodes.new(type='ShaderNodeTexImage')
                        node_lm.image = lightmap
                        node_lm.location = 1200, -800

                    tc_gen = shader.get_tcGen_node(TCGEN_LM)
                    if tc_gen is not None and lightmap is not None:
                        shader.links.new(
                            tc_gen.outputs["UV"], node_lm.inputs["Vector"])

                    node_blend = shader.nodes.new(type='ShaderNodeMixRGB')
                    node_blend.blend_type = 'MULTIPLY'
                    node_blend.inputs[0].default_value = 1.0
                    node_blend.location = 1600, -200

                    shader.links.new(
                        node_texture.outputs["Color"],
                        node_blend.inputs["Color1"])
                    shader.links.new(
                        node_lm.outputs["Color"], node_blend.inputs["Color2"])
                    color_out = node_blend.outputs["Color"]

        shader.mat.use_backface_culling = True
        if "cull" in shader.attributes:
            if (shader.attributes["cull"][0] == "twosided" or
               shader.attributes["cull"][0] == "none"):
                shader.mat.use_backface_culling = False
        shader.mat.shadow_method = 'CLIP'

        if import_settings.preset == 'EDITING' and shader.is_system_shader:
            shader_type = "BLEND"
            node_val = shader.nodes.new(type="ShaderNodeValue")
            if "qer_trans" in shader.attributes:
                try:
                    node_val.outputs[0].default_value = float(
                        shader.attributes["qer_trans"][0])
                except Exception:
                    print("qer_trans with no proper value found")
                    node_val.outputs[0].default_value = 0.5
            else:
                node_val.outputs[0].default_value = 0.8
            alpha_out = node_val.outputs[0]

        shader_out = None
        if shader_type == "ADD":
            node_BSDF = shader.nodes.new(type="ShaderNodeEmission")
            node_BSDF.location = (3000, 0)

            node_transp = shader.nodes.new(type="ShaderNodeBsdfTransparent")
            node_transp.location = (3000, -400)

            node_add = shader.nodes.new(type="ShaderNodeAddShader")
            node_add.location = (3600, 0)

            shader.links.new(node_BSDF.outputs[0], node_add.inputs[0])
            shader.links.new(node_transp.outputs[0], node_add.inputs[1])
            if color_out is not None:
                shader.links.new(color_out, node_BSDF.inputs["Color"])
            shader_out = node_add.outputs["Shader"]
        elif shader_type == "MULTIPLY":
            node_BSDF = shader.nodes.new(type="ShaderNodeBsdfTransparent")
            node_BSDF.location = (3000, 0)
            if color_out is not None:
                node_mix = shader.nodes.new(type="ShaderNodeMixRGB")
                node_mix.location = (3000, -400)
                node_rgb = shader.nodes.new(type="ShaderNodeRGB")
                node_rgb.outputs[0].default_value = (1, 1, 1, 1)
                node_rgb.location = (2600, -400)
                shader.links.new(color_out, node_mix.inputs["Color2"])
                shader.links.new(alpha_out, node_mix.inputs["Fac"])
                shader.links.new(
                    node_rgb.outputs[0], node_mix.inputs["Color1"])
                shader.links.new(
                    node_mix.outputs[0], node_BSDF.inputs["Color"])

            shader_out = node_BSDF.outputs["BSDF"]
        else:  # shader_type == "BLEND":
            node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
            node_BSDF.location = (3000, 0)
            node_BSDF.inputs["Roughness"].default_value = 0.9999

            if color_out is not None:
                shader.links.new(color_out, node_BSDF.inputs["Base Color"])
                shader.links.new(color_out, node_BSDF.inputs[EMISSION_KEY])
                if bpy.app.version >= (4, 0, 0):
                        node_BSDF.inputs["Emission Strength"].default_value = 1.0
            if shader_type != "OPAQUE" and alpha_out is not None:
                shader.links.new(alpha_out, node_BSDF.inputs["Alpha"])
            if normal_out is not None:
                shader.links.new(normal_out, node_BSDF.inputs["Normal"])
            shader_out = node_BSDF.outputs["BSDF"]

        shader.links.new(shader_out, shader.nodes["Output"].inputs[0])

    def finish_brush_shader(shader, VFS, import_settings):
        node_BSDF = shader.nodes.new(type="ShaderNodeBsdfPrincipled")
        node_BSDF.location = (3000, 0)
        node_BSDF.name = "Out_BSDF"
        node_BSDF.inputs["Roughness"].default_value = 0.9999
        node_BSDF.inputs["Alpha"].default_value = 0.5
        is_sky = False
        if "qer_editorimage" in shader.attributes:
            image = BlenderImage.load_file(
                shader.attributes["qer_editorimage"][0], VFS)
        else:
            image = BlenderImage.load_file(shader.texture, VFS)

        if image is not None:
            node_img = shader.nodes.new(type='ShaderNodeTexImage')
            node_img.image = image
            node_img.location = 1200, -800
            shader.links.new(
                node_img.outputs["Color"], node_BSDF.inputs["Base Color"])

        if "qer_trans" in shader.attributes:
            try:
                node_BSDF.inputs["Alpha"].default_value = float(
                    shader.attributes["qer_trans"][0])
            except Exception:
                print("qer_trans with no proper value found")
                node_BSDF.inputs["Alpha"].default_value = 0.5

        if (import_settings.preset == 'RENDERING' or
           import_settings.preset == "SHADOW_BRUSHES"):
            transparent = False

            if "skyparms" in shader.attributes:
                transparent = True
                is_sky = True
            if "surfaceparm" in shader.attributes:
                if "trans" in shader.attributes["surfaceparm"]:
                    transparent = True
                if "nonopaque" in shader.attributes["surfaceparm"]:
                    transparent = True
            if "cull" in shader.attributes:
                if (shader.attributes["cull"][0] == "twosided" or
                    shader.attributes["cull"][0] == "none"):
                    transparent = True

            if transparent:
                node_BSDF.inputs["Alpha"].default_value = 0.0
                node_BSDF.name = "Sky" if is_sky else "Transparent"
                shader.links.new(
                    node_BSDF.outputs[0], shader.nodes["Output"].inputs[0])
                shader.mat.shadow_method = 'NONE'
            else:
                solid_BSDF = shader.nodes.new(type="ShaderNodeBsdfDiffuse")
                solid_BSDF.location = 4200, 0
                shader.links.new(
                    solid_BSDF.outputs[0], shader.nodes["Output"].inputs[0])
                shader.nodes["Output"].target = "CYCLES"

                eevee_out = shader.nodes.new(type="ShaderNodeOutputMaterial")
                eevee_out.location = 4200, -300
                eevee_out.name = "EeveeOut"
                eevee_out.target = "EEVEE"
                shader.links.new(node_BSDF.outputs[0], eevee_out.inputs[0])

            shader.mat.blend_method = "BLEND"
        else:
            shader.links.new(
                node_BSDF.outputs[0], shader.nodes["Output"].inputs[0])
            shader.mat.shadow_method = 'NONE'
            shader.mat.blend_method = "BLEND"

    def finish_fog_shader(shader, VFS, import_settings):
        shader.nodes.clear()
        node_output = shader.nodes.new(type='ShaderNodeOutputMaterial')
        node_output.name = "Output"
        node_output.location = (3400, 0)
        color = [1.0, 1.0, 1.0]
        depth = 16384.0
        density_scale = 1.0
        if "fogparms" not in shader.attributes:
            split_name = shader.texture.replace("'", "").replace('"', "").split()
            if len(split_name) == 1:
                density_scale = split_name[0]
            elif len(split_name) == 2:
                density_scale = split_name[0]
                color[0] = split_name[1]
            elif len(split_name) == 3:
                density_scale = split_name[0]
                color[0] = split_name[1]
                color[1] = split_name[2]
            elif len(split_name) == 4:
                density_scale = split_name[0]
                color[:] = split_name[1:]
            elif len(split_name) > 4:
                density_scale = split_name[0]
                color[:] = split_name[1:-1]
        else:
            ags = shader.attributes["fogparms"][0].replace("(", "").replace(")", "").strip().split()
            if len(ags) < 4:
                print("Fogparms not parsed:", shader.attributes["fogparms"])
                return
            color = ags[:3]
            depth = ags[3]

        try:
            color = QuakeLight.SRGBToLinear(
                (float(color[0]), float(color[1]), float(color[2])))
            density = float(density_scale) * (sqrt(-log(1.0 / 255.0)) / float(depth))
        except Exception:
            print("Fogparms with no proper values found")
            color = [1.0, 1.0, 1.0]
            density = 0.000011
        node_Voulme = shader.nodes.new(type="ShaderNodeVolumePrincipled")

        node_Voulme.inputs["Color"].default_value = [*color, 1.0]
        node_Voulme.inputs["Density"].default_value = density

        node_Voulme.inputs["Emission Strength"].default_value = density
        node_Voulme.inputs["Emission Color"].default_value = [*color, 1.0]

        node_Voulme.name = "Out_Volume"
        node_Voulme.location = (3000, 0)
        shader.links.new(
            node_Voulme.outputs["Volume"], node_output.inputs[1])

    def finish_shader(shader, VFS, import_settings):
        if shader.is_fog:
            shader.finish_fog_shader(VFS, import_settings)
        elif shader.is_brush:
            shader.finish_brush_shader(VFS, import_settings)
        elif (import_settings.preset != 'RENDERING' and
              import_settings.preset != 'BRUSHES'):
            shader.finish_preview_shader(VFS, import_settings)
        else:
            shader.finish_rendering_shader(VFS, import_settings)

# TODO: overwrite existing Bsp Node instead of making a new one?


def init_shader_system(bsp):
    bsp_node = bpy.data.node_groups.get("BspInfo")
    if bsp_node is not None:
        bsp_node.name = bsp_node.name+"_prev.000"

    bsp_node = ShaderNodes.Bsp_Node.create_node_tree(bsp)
    bsp_node.use_fake_user = True
    color_normalize_node = ShaderNodes.Color_Normalize_Node.create_node_tree(
        None)
    color_normalize_node.use_fake_user = True


def get_shader_image_sizes(VFS, import_settings, material_list):
    return ID3Shader.get_shader_image_sizes(
        VFS,
        import_settings,
        material_list)


def create_white_image():
    white_image = bpy.data.images.get("$whiteimage")
    if white_image is not None:
        return
    idtech3_image = ID3Shader.create_white_image()
    new_image = bpy.data.images.new(
        idtech3_image.name,
        width=idtech3_image.width,
        height=idtech3_image.height,
        alpha=idtech3_image.num_components == 4)
    new_image.pixels = idtech3_image.get_rgba()
    new_image.alpha_mode = 'CHANNEL_PACKED'
    new_image.use_fake_user = True


def build_quake_shaders(VFS, import_settings, object_list):

    # make sure the $whiteimage is loaded
    create_white_image()

    shaders = {}
    material_list = []
    material_names = []
    for object in object_list:
        if object.data.name == "box":
            continue
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

        vg = object.vertex_groups.get("ExternalLightmap")
        if vg is not None:
            object.vertex_groups.remove(vg)
        vg = object.vertex_groups.get("Decals")
        if vg is not None:
            object.vertex_groups.remove(vg)
        mod = object.modifiers.get("polygonOffset")
        if mod is not None:
            object.modifiers.remove(mod)

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
            shaders.setdefault(l_format(shader_name), []).append(qs)

    shader_info = ID3Shader.get_material_dicts(VFS,
                                               import_settings,
                                               shaders.keys())

    for shader in shaders:
        current_shaders = shaders[shader]
        if shader == "textures/common/skyportal":
            for portal_shader in current_shaders:
                portal_shader.is_system_shader = True

        if shader not in shader_info:
            continue

        attributes, stages = shader_info[shader]
        if ("surfaceparm" in attributes and
           "nodraw" in attributes["surfaceparm"]):
            for current_shader in current_shaders:
                current_shader.is_system_shader = True

        for current_shader in current_shaders:
            current_shader.attributes = attributes
            if current_shader.mat is None:
                continue
            if "first_line" in attributes:
                current_shader.mat["first_line"] = attributes["first_line"]
            if "shader_file" in attributes:
                current_shader.mat["shader_file"] = attributes["shader_file"]

        for stage in stages:
            for current_shader in current_shaders:
                current_shader.add_stage(stage)

        for current_shader in current_shaders:
            current_shader.finish_shader(VFS, import_settings)
            has_external_lm = False
            for shader_stage in current_shader.stages:
                if (shader_stage.tcGen == TCGEN_LM and
                   shader_stage.diffuse.startswith("maps/")):
                    has_external_lm = True
            # polygon offset to vertex group
            if "polygonoffset" in attributes or has_external_lm:
                for obj in object_list:
                    for index, m in enumerate(obj.material_slots):
                        if m.name == current_shader.name:
                            verts = [v for f in obj.data.polygons
                                     if f.material_index == index
                                     for v in f.vertices]
                            if len(verts):
                                if "polygonoffset" in attributes:
                                    vg = obj.vertex_groups.get(
                                        "Decals")
                                    if vg is None:
                                        vg = obj.vertex_groups.new(
                                            name="Decals")
                                    vg.add(verts, 1.0, 'ADD')
                                if has_external_lm:
                                    vg = obj.vertex_groups.get(
                                        "ExternalLightmap")
                                    if vg is None:
                                        vg = obj.vertex_groups.new(
                                            name="ExternalLightmap")
                                    vg.add(verts, 1.0, 'ADD')
                            break
    for shader in shaders:
        if shader in shader_info:
            continue
        for current_shader in shaders[shader]:
            current_shader.finish_shader(VFS, import_settings)

    for object in object_list:
        vg = object.vertex_groups.get("Decals")
        if vg is not None:
            modifier = object.modifiers.new("polygonOffset", type="DISPLACE")
            modifier.vertex_group = "Decals"
            modifier.strength = 0.1
            modifier.name = "polygonOffset"

    return
