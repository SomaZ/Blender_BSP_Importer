import bpy

def create_static_node(shader, name):
    node = None
    if name == "tcNormal":
        node = shader.nodes.new(type='ShaderNodeUVMap')
        node.uv_map = "UVMap"
    elif name == "tcLightmap":
        node = shader.nodes.new(type='ShaderNodeUVMap')
        node.uv_map = "LightmapUV"
    elif name == "tcEnvironment":
        node = shader.nodes.new(type="ShaderNodeGroup")
        node.node_tree = TcGen_Env_Node.get_node_tree(None)
    elif name == "vertexColor":
        node = shader.nodes.new(type="ShaderNodeAttribute")
        node.attribute_name = "Color"
    elif name == "vertexAlpha":
        node = shader.nodes.new(type="ShaderNodeAttribute")
        node.attribute_name = "Alpha"
    elif name == "specularAlpha":
        node = shader.nodes.new(type="ShaderNodeGroup")
        node.node_tree = AlphaGen_Spec_Node.get_node_tree(None)
    elif name == "gridColor":
        node_BSP = shader.nodes.new(type="ShaderNodeGroup")
        node_BSP.name = "BspInfo"
        node_BSP.node_tree = Bsp_Node.get_node_tree(None)
        node_BSP.location = (shader.static_nodes[name][0] - 400, shader.static_nodes[name][1])
        node = shader.nodes.new(type="ShaderNodeGroup")
        node.node_tree = Lightgrid_Node.get_node_tree(None)
        if not (shader.zoffset == 0):
            node.inputs['ZOffset'].default_value = float(shader.zoffset)
        shader.links.new(node_BSP.outputs["LightGridOrigin"], node.inputs['LightGridOrigin'])
        shader.links.new(node_BSP.outputs["LightGridInverseSize"], node.inputs['LightGridInverseSize'])
        shader.links.new(node_BSP.outputs["LightGridInverseDimension"], node.inputs['LightGridInverseDimension'])    
    elif name == "shaderTime":
        node = shader.nodes.new(type="ShaderNodeGroup")
        node.node_tree = Shader_Time_Node.get_node_tree(None)
    elif name == "BaseReflectionVector":
        node = shader.nodes.new(type="ShaderNodeGroup")
        node.node_tree = Base_Light_Vector_Node.get_node_tree(None)
    elif name == "EmissionScaleNode":
        node = shader.nodes.new(type="ShaderNodeGroup")
        node.node_tree = Emission_Node.get_node_tree(None)
    else:
        print("unrecognized static node: ", name)
        return None
    
    node.name = name
    node.location = shader.static_nodes[name]
    return node

class Generic_Node_Group():
    name = ""
    @classmethod
    def get_node_tree(self, variable):
        if self.name == "":
            node_tree = bpy.data.node_groups.get(variable)
        else:
            node_tree = bpy.data.node_groups.get(self.name)
            
        if node_tree is None:
            return self.create_node_tree(variable)
        else:
            return node_tree
    @classmethod
    def create_node_tree(self, variable):
        raise NotImplementedError

class Bsp_Node(Generic_Node_Group):
    name = 'BspInfo'
    @classmethod
    def create_node_tree(self, bsp):
        bsp_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        group_outputs = bsp_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300,0)
        bsp_group.outputs.new('NodeSocketVector','LightGridOrigin')
        bsp_group.outputs.new('NodeSocketVector','LightGridInverseSize')
        bsp_group.outputs.new('NodeSocketVector','LightGridInverseDimension')
        
        node_grid_origin = bsp_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_grid_origin.name = "GridOrigin"
        node_grid_origin.location = (-1400,0)
        if bsp != None:
            node_grid_origin.inputs[0].default_value = bsp.lightgrid_origin[0]
            node_grid_origin.inputs[1].default_value = bsp.lightgrid_origin[1]
            node_grid_origin.inputs[2].default_value = bsp.lightgrid_origin[2]
        else:
            node_grid_origin.inputs[0].default_value = 0.0
            node_grid_origin.inputs[1].default_value = 0.0
            node_grid_origin.inputs[2].default_value = 0.0
        
        node_grid_size = bsp_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_grid_size.name = "GridSize"
        node_grid_size.location = (-1400,-200)
        if bsp != None:
            node_grid_size.inputs[0].default_value = bsp.lightgrid_size[0]
            node_grid_size.inputs[1].default_value = bsp.lightgrid_size[1]
            node_grid_size.inputs[2].default_value = bsp.lightgrid_size[2]
        else:
            node_grid_size.inputs[0].default_value = 1.0
            node_grid_size.inputs[1].default_value = 1.0
            node_grid_size.inputs[2].default_value = 1.0
            
        node_grid_inv_size = bsp_group.nodes.new(type="ShaderNodeVectorMath")
        node_grid_inv_size.name = "GridInvSize"
        node_grid_inv_size.location = (-900,-200)
        node_grid_inv_size.operation = "DIVIDE"
        node_grid_inv_size.inputs[0].default_value = [1.0, 1.0, 1.0]
        bsp_group.links.new(node_grid_size.outputs["Vector"], node_grid_inv_size.inputs[1])
        
        node_grid_dim = bsp_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_grid_dim.name = "GridDimensions"
        node_grid_dim.location = (-1400,-400)
        if bsp != None:
            node_grid_dim.inputs[0].default_value = bsp.lightgrid_dim[0]
            node_grid_dim.inputs[1].default_value = bsp.lightgrid_dim[1]*bsp.lightgrid_dim[2]
            node_grid_dim.inputs[2].default_value = bsp.lightgrid_dim[2]
        else:
            node_grid_dim.inputs[0].default_value = 1.0
            node_grid_dim.inputs[1].default_value = 1.0
            node_grid_dim.inputs[2].default_value = 1.0
            
        node_grid_inv_dim = bsp_group.nodes.new(type="ShaderNodeVectorMath")
        node_grid_inv_dim.name = "GridInvDim"
        node_grid_inv_dim.location = (-900,-400)
        node_grid_inv_dim.operation = "DIVIDE"
        node_grid_inv_dim.inputs[0].default_value = [1.0, 1.0, 1.0]
        bsp_group.links.new(node_grid_dim.outputs["Vector"], node_grid_inv_dim.inputs[1])
        
        bsp_group.links.new(node_grid_origin.outputs["Vector"], group_outputs.inputs['LightGridOrigin'])
        bsp_group.links.new(node_grid_inv_size.outputs["Vector"], group_outputs.inputs['LightGridInverseSize'])
        bsp_group.links.new(node_grid_inv_dim.outputs["Vector"], group_outputs.inputs['LightGridInverseDimension'])
        return bsp_group
    
class Emission_Node(Generic_Node_Group):
    name = 'EmissionScaleNode'
    @classmethod
    def create_node_tree(self, empty):
        emission_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_inputs = emission_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-1600,0)
        emission_group.inputs.new('NodeSocketColor','Color')
        emission_group.inputs.new('NodeSocketFloat','Light')
        emission_group.inputs['Light'].default_value = 1.0
        
        group_outputs = emission_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300,0)
        emission_group.outputs.new('NodeSocketColor','OutColor')
        
        shader_emission = emission_group.nodes.new(type="ShaderNodeVectorMath")
        shader_emission.operation = "SCALE"
        emission_group.links.new(group_inputs.outputs["Color"], shader_emission.inputs["Vector"])
        emission_group.links.new(group_inputs.outputs["Light"], shader_emission.inputs["Scale"])
        
        scale = emission_group.nodes.new(type="ShaderNodeValue")
        scale.outputs[0].default_value = 1.0
        scale.name = "Emission scale"
        
        out_emission = emission_group.nodes.new(type="ShaderNodeVectorMath")
        out_emission.operation = "SCALE"
        emission_group.links.new(shader_emission.outputs[0], out_emission.inputs["Vector"])
        emission_group.links.new(scale.outputs[0], out_emission.inputs["Scale"])
        
        emission_group.links.new(out_emission.outputs["Vector"], group_outputs.inputs['OutColor'])
        return emission_group
    
class Color_Normalize_Node(Generic_Node_Group):
    name = 'ColorNormalize'
    @classmethod
    def create_node_tree(self, empty):
        light_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_inputs = light_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-1600,0)
        light_group.inputs.new('NodeSocketColor','Color')
        light_group.inputs.new('NodeSocketFloat','HDR')
        light_group.inputs['HDR'].default_value = 0.0
        
        group_outputs = light_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300,0)
        light_group.outputs.new('NodeSocketColor','OutColor')
        
        rgb_node = light_group.nodes.new(type="ShaderNodeSeparateRGB")
        light_group.links.new(group_inputs.outputs["Color"], rgb_node.inputs["Image"])
        
        max1 = light_group.nodes.new(type="ShaderNodeMath")
        max1.operation = "MAXIMUM"
        max2 = light_group.nodes.new(type="ShaderNodeMath")
        max2.operation = "MAXIMUM"
        
        light_group.links.new(rgb_node.outputs[0], max1.inputs[0])
        light_group.links.new(rgb_node.outputs[1], max1.inputs[1])
        light_group.links.new(max1.outputs[0], max2.inputs[0])
        light_group.links.new(rgb_node.outputs[2], max2.inputs[1])
        
        bigger = light_group.nodes.new(type="ShaderNodeMath")
        bigger.operation = "GREATER_THAN"
        bigger.inputs[1].default_value = 1
        light_group.links.new(max2.outputs[0], bigger.inputs[0])
        
        color_normalized = light_group.nodes.new(type="ShaderNodeVectorMath")
        color_normalized.operation = 'DIVIDE'
        light_group.links.new(group_inputs.outputs["Color"], color_normalized.inputs[0])
        light_group.links.new(max2.outputs[0], color_normalized.inputs[1])
        
        mix = light_group.nodes.new(type="ShaderNodeMixRGB")
        light_group.links.new(bigger.outputs[0], mix.inputs[0])
        light_group.links.new(group_inputs.outputs["Color"], mix.inputs[1])
        light_group.links.new(color_normalized.outputs[0], mix.inputs[2])
        
        light_group.links.new(mix.outputs[0], group_outputs.inputs['OutColor'])
        return light_group
    
class Base_Light_Vector_Node(Generic_Node_Group):
    name = "BaseReflectionVector"
    @classmethod
    def create_node_tree(self, empty):
        vector_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_outputs = vector_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300,0)
        vector_group.outputs.new('NodeSocketVector','Vector')
        
        node_geometry = vector_group.nodes.new(type="ShaderNodeNewGeometry")
        node_geometry.location = (0,0)
        
        node_light_origin = vector_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_light_origin.name = "LightOrigin"
        node_light_origin.location = (0,-400)
        node_light_origin.inputs[0].default_value = -960.0
        node_light_origin.inputs[1].default_value = 1980.0
        node_light_origin.inputs[2].default_value = 96.0
        
        node_vector = vector_group.nodes.new(type="ShaderNodeVectorMath")
        node_vector.operation = "SUBTRACT"
        node_vector.location = (400,0)
        vector_group.links.new(node_geometry.outputs["Position"], node_vector.inputs[1])
        vector_group.links.new(node_light_origin.outputs["Vector"], node_vector.inputs[0])
        
        node_normalized_vector = vector_group.nodes.new(type="ShaderNodeVectorMath")
        node_normalized_vector.operation = "NORMALIZE"
        node_normalized_vector.location = (400,0)
        vector_group.links.new(node_vector.outputs["Vector"], node_normalized_vector.inputs[0])
        
        vector_group.links.new(node_normalized_vector.outputs["Vector"], group_outputs.inputs['Vector'])
        return vector_group

class Blend_Node(Generic_Node_Group):
    @classmethod
    def create_node_tree(self, blend_mode):
        blend_group = bpy.data.node_groups.new(blend_mode, 'ShaderNodeTree')
        
        group_inputs = blend_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-1600,0)
        blend_group.inputs.new('NodeSocketColor','DestinationColor')
        blend_group.inputs.new('NodeSocketFloat','DestinationAlpha')
        blend_group.inputs.new('NodeSocketColor','SourceColor')
        blend_group.inputs.new('NodeSocketFloat','SourceAlpha')
        blend_group.inputs.new('NodeSocketColor','rgbGen')
        
        group_outputs = blend_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300,0)
        blend_group.outputs.new('NodeSocketColor','OutColor')
        blend_group.outputs.new('NodeSocketFloat','OutAlpha')
        
        node_term_dest = blend_group.nodes.new(type="ShaderNodeMixRGB")
        node_term_dest.name = "DestinationColorTerm"
        node_term_dest.blend_type = "MULTIPLY"
        node_term_dest.use_clamp = True
        node_term_dest.inputs[0].default_value = 1.0
        node_term_dest.location = (-1000,0)
        blend_group.links.new(group_inputs.outputs["DestinationColor"], node_term_dest.inputs["Color1"])
        
        node_term_dest_a = blend_group.nodes.new(type="ShaderNodeMath")
        node_term_dest_a.name = "DestinationAlphaTerm"
        node_term_dest_a.operation = "MULTIPLY"
        node_term_dest_a.use_clamp = True
        node_term_dest_a.location = (-1000,-200)
        blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_dest_a.inputs[0])
        
        node_rgb_blend = blend_group.nodes.new(type="ShaderNodeMixRGB")
        node_rgb_blend.name = "rgbGenBlend"
        node_rgb_blend.blend_type = "MULTIPLY"
        node_rgb_blend.use_clamp = True
        node_rgb_blend.inputs[0].default_value = 1.0
        node_rgb_blend.location = (-1300, -800)
        blend_group.links.new(group_inputs.outputs["SourceColor"], node_rgb_blend.inputs['Color1'])
        blend_group.links.new(group_inputs.outputs["rgbGen"], node_rgb_blend.inputs['Color2'])
        
        node_term_src = blend_group.nodes.new(type="ShaderNodeMixRGB")
        node_term_src.name = "SourceColorTerm"
        node_term_src.blend_type = "MULTIPLY"
        node_term_src.use_clamp = True
        node_term_src.inputs[0].default_value = 1.0
        node_term_src.location = (-1000,-800)
        blend_group.links.new(node_rgb_blend.outputs["Color"], node_term_src.inputs["Color1"])
        
        node_term_src_a = blend_group.nodes.new(type="ShaderNodeMath")
        node_term_src_a.name = "SourceAlphaTerm"
        node_term_src_a.operation = "MULTIPLY"
        node_term_src_a.use_clamp = True
        node_term_src_a.location = (-1000,-1000)
        blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_src_a.inputs[0])
        
        node_term_src_a_gt = blend_group.nodes.new(type="ShaderNodeMath")
        node_term_src_a_gt.name = "SourceAlphaGreaterThan1"
        node_term_src_a_gt.operation = "GREATER_THAN"
        node_term_src_a_gt.location = (-1000,-1200)
        node_term_src_a_gt.inputs[1].default_value = 0.997
        
        node_term_src_a_fixed = blend_group.nodes.new(type="ShaderNodeMath")
        node_term_src_a_fixed.name = "SourceAlphaTermFixed"
        node_term_src_a_fixed.operation = "ADD"
        node_term_src_a_fixed.use_clamp = True
        node_term_src_a_fixed.location = (-500,-1000)
        blend_group.links.new(node_term_src_a.outputs[0], node_term_src_a_fixed.inputs[0])
        blend_group.links.new(node_term_src_a_gt.outputs[0], node_term_src_a_fixed.inputs[1])
        
        node_output = blend_group.nodes.new(type="ShaderNodeVectorMath")
        node_output.name = "BlendedOutputColor"
        node_output.operation = "ADD"
        node_output.location = (1000,0)
        blend_group.links.new(node_term_dest.outputs["Color"], node_output.inputs[0])
        blend_group.links.new(node_term_src.outputs["Color"], node_output.inputs[1])
        
        node_output_a = blend_group.nodes.new(type="ShaderNodeMath")
        node_output_a.name = "BlendedOutputAlpha"
        node_output_a.operation = "ADD"
        node_output_a.use_clamp = True
        node_output_a.location = (1000,-200)
        blend_group.links.new(node_term_dest_a.outputs["Value"], node_output_a.inputs[0])
        blend_group.links.new(node_term_src_a.outputs["Value"], node_output_a.inputs[1])
        
        source, dest = blend_mode.split(" ")
        if source == "gl_one":#"glow":
            node_term_src.inputs["Color2"].default_value = [1.0, 1.0, 1.0, 1.0]
            node_bw = blend_group.nodes.new(type="ShaderNodeVectorMath")
            node_bw.inputs[1].default_value = [0.299, 0.587, 0.114]
            node_bw.operation = "DOT_PRODUCT"
            node_bw.location = (-1000,-1300)
            blend_group.links.new(node_rgb_blend.outputs["Color"], node_bw.inputs[0])
            blend_group.links.new(node_bw.outputs["Value"], node_term_src_a.inputs[1])
            blend_group.links.new(node_bw.outputs["Value"], node_term_src_a_gt.inputs[0])
        #elif source == "gl_one":
            #node_term_src.inputs["Color2"].default_value = [1.0, 1.0, 1.0, 1.0]
            #node_term_src_a.inputs[1].default_value = 1.0
            #node_term_src_a_gt.inputs[0].default_value = 1.0   
        elif source == "gl_zero":
            node_term_src.inputs["Color2"].default_value = [0.0, 0.0, 0.0, 0.0]
            node_term_src_a.inputs[1].default_value = 0.0
            node_term_src_a_gt.inputs[0].default_value = 0.0
        elif source == "gl_src_color":
            blend_group.links.new(group_inputs.outputs["SourceColor"], node_term_src.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_src_a.inputs[1])
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_src_a_gt.inputs[0])
        elif source == "gl_src_alpha":
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_src.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_src_a.inputs[1])
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_src_a_gt.inputs[0])
            #special case?
            blend_group.links.new(node_term_src_a_fixed.outputs["Value"], node_output_a.inputs[1])
        elif source == "gl_dst_color":
            blend_group.links.new(group_inputs.outputs["DestinationColor"], node_term_src.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_src_a.inputs[1])
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_src_a_gt.inputs[0])
        elif source == "gl_dst_alpha":    
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_src.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_src_a.inputs[1])
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_src_a_gt.inputs[0])
            #special case?
            blend_group.links.new(node_term_src_a_fixed.outputs["Value"], node_output_a.inputs[1])
        elif source == "gl_one_minus_src_color":
            node_one_minus_src_color = blend_group.nodes.new(type="ShaderNodeVectorMath")
            node_one_minus_src_color.operation = "SUBTRACT"
            node_one_minus_src_color.location = (-1300,0)
            node_one_minus_src_color.inputs[0].default_value = [1.0,1.0,1.0]
            blend_group.links.new(group_inputs.outputs["SourceColor"], node_one_minus_src_color.inputs[1])
            node_one_minus_src_color_a = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_src_color_a.operation = "SUBTRACT"
            node_one_minus_src_color_a.location = (-1300,-100)
            node_one_minus_src_color_a.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_one_minus_src_color_a.inputs[1])
            blend_group.links.new(node_one_minus_src_color.outputs["Vector"], node_term_src.inputs["Color2"])
            blend_group.links.new(node_one_minus_src_color_a.outputs["Value"], node_term_src_a.inputs[1])
            blend_group.links.new(node_one_minus_src_color_a.outputs["Value"], node_term_src_a_gt.inputs[0])
        elif source == "gl_one_minus_dst_color":
            node_one_minus_dst_color = blend_group.nodes.new(type="ShaderNodeVectorMath")
            node_one_minus_dst_color.operation = "SUBTRACT"
            node_one_minus_dst_color.location = (-1300,0)
            node_one_minus_dst_color.inputs[0].default_value = [1.0,1.0,1.0]
            blend_group.links.new(group_inputs.outputs["DestinationColor"], node_one_minus_dst_color.inputs[1])
            node_one_minus_dst_color_a = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_dst_color_a.operation = "SUBTRACT"
            node_one_minus_dst_color_a.location = (-1300,-100)
            node_one_minus_dst_color_a.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_one_minus_dst_color_a.inputs[1])
            blend_group.links.new(node_one_minus_dst_color.outputs["Vector"], node_term_src.inputs["Color2"])
            blend_group.links.new(node_one_minus_dst_color_a.outputs["Value"], node_term_src_a.inputs[1])
            blend_group.links.new(node_one_minus_dst_color_a.outputs["Value"], node_term_src_a_gt.inputs[0])
        elif source == "gl_one_minus_src_alpha":
            node_one_minus_src_alpha = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_src_alpha.operation = "SUBTRACT"
            node_one_minus_src_alpha.location = (-1300,0)
            node_one_minus_src_alpha.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_one_minus_src_alpha.inputs[1])
            blend_group.links.new(node_one_minus_src_alpha.outputs["Value"], node_term_src.inputs["Color2"])
            blend_group.links.new(node_one_minus_src_alpha.outputs["Value"], node_term_src_a.inputs[1])
            blend_group.links.new(node_one_minus_src_alpha.outputs["Value"], node_term_src_a_gt.inputs[0])
            #special case?
            blend_group.links.new(node_term_src_a_fixed.outputs["Value"], node_output_a.inputs[1])
        elif source == "gl_one_minus_dst_alpha":
            node_one_minus_dst_alpha = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_dst_alpha.operation = "SUBTRACT"
            node_one_minus_dst_alpha.location = (-1300,0)
            node_one_minus_dst_alpha.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_one_minus_dst_alpha.inputs[1])
            blend_group.links.new(node_one_minus_dst_alpha.outputs["Value"], node_term_src.inputs["Color2"])
            blend_group.links.new(node_one_minus_dst_alpha.outputs["Value"], node_term_src_a.inputs[1])
            blend_group.links.new(node_one_minus_dst_alpha.outputs["Value"], node_term_src_a_gt.inputs[0])
            #special case?
            blend_group.links.new(node_term_src_a_fixed.outputs["Value"], node_output_a.inputs[1])
        else:
            print("unknown src blend ", source)
            
        if dest == "gl_one":#"glow":
            node_term_dest.inputs["Color2"].default_value = [1.0, 1.0, 1.0, 1.0]
            node_term_dest_a.inputs[1].default_value = 1.0
        #elif dest == "gl_one":
            #node_term_dest.inputs["Color2"].default_value = [1.0, 1.0, 1.0, 1.0]
            #node_term_dest_a.inputs[1].default_value = 1.0
        elif dest == "gl_zero":
            node_term_dest.inputs["Color2"].default_value = [0.0, 0.0, 0.0, 0.0]
            node_term_dest_a.inputs[1].default_value = 0.0
        elif dest == "gl_src_color":
            blend_group.links.new(group_inputs.outputs["SourceColor"], node_term_dest.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_dest_a.inputs[1])
        elif dest == "gl_src_alpha":
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_dest.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_term_dest_a.inputs[1])
        elif dest == "gl_dst_color":
            blend_group.links.new(group_inputs.outputs["DestinationColor"], node_term_dest.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_dest_a.inputs[1])
        elif dest == "gl_dst_alpha":    
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_dest.inputs["Color2"])
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_term_dest_a.inputs[1])
        elif dest == "gl_one_minus_src_color":
            node_one_minus_src_color = blend_group.nodes.new(type="ShaderNodeVectorMath")
            node_one_minus_src_color.operation = "SUBTRACT"
            node_one_minus_src_color.location = (-1300,-400)
            node_one_minus_src_color.inputs[0].default_value = [1.0,1.0,1.0]
            blend_group.links.new(group_inputs.outputs["SourceColor"], node_one_minus_src_color.inputs[1])
            node_one_minus_src_color_a = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_src_color_a.operation = "SUBTRACT"
            node_one_minus_src_color_a.location = (-1300,-700)
            node_one_minus_src_color_a.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_one_minus_src_color_a.inputs[1])
            blend_group.links.new(node_one_minus_src_color.outputs["Vector"], node_term_dest.inputs["Color2"])
            blend_group.links.new(node_one_minus_src_color_a.outputs["Value"], node_term_dest_a.inputs[1])
        elif dest == "gl_one_minus_dst_color":
            node_one_minus_dst_color = blend_group.nodes.new(type="ShaderNodeVectorMath")
            node_one_minus_dst_color.operation = "SUBTRACT"
            node_one_minus_dst_color.location = (-1300,-400)
            node_one_minus_dst_color.inputs[0].default_value = [1.0,1.0,1.0]
            blend_group.links.new(group_inputs.outputs["DestinationColor"], node_one_minus_dst_color.inputs[1])
            node_one_minus_dst_color_a = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_dst_color_a.operation = "SUBTRACT"
            node_one_minus_dst_color_a.location = (-1300,-700)
            node_one_minus_dst_color_a.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_one_minus_dst_color_a.inputs[1])
            blend_group.links.new(node_one_minus_dst_color.outputs["Vector"], node_term_dest.inputs["Color2"])
            blend_group.links.new(node_one_minus_dst_color_a.outputs["Value"], node_term_dest_a.inputs[1])
        elif dest == "gl_one_minus_src_alpha":
            node_one_minus_src_alpha = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_src_alpha.operation = "SUBTRACT"
            node_one_minus_src_alpha.location = (-1300,-400)
            node_one_minus_src_alpha.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["SourceAlpha"], node_one_minus_src_alpha.inputs[1])
            blend_group.links.new(node_one_minus_src_alpha.outputs["Value"], node_term_dest.inputs["Color2"])
            blend_group.links.new(node_one_minus_src_alpha.outputs["Value"], node_term_dest_a.inputs[1])
        elif dest == "gl_one_minus_dst_alpha":
            node_one_minus_dst_alpha = blend_group.nodes.new(type="ShaderNodeMath")
            node_one_minus_dst_alpha.operation = "SUBTRACT"
            node_one_minus_dst_alpha.location = (-1300,-400)
            node_one_minus_dst_alpha.inputs[0].default_value = 1.0
            blend_group.links.new(group_inputs.outputs["DestinationAlpha"], node_one_minus_dst_alpha.inputs[1])
            blend_group.links.new(node_one_minus_dst_alpha.outputs["Value"], node_term_dest.inputs["Color2"])
            blend_group.links.new(node_one_minus_dst_alpha.outputs["Value"], node_term_dest_a.inputs[1])
        else:
            print("unknown dst blend ", dest)
        
        blend_group.links.new(node_output.outputs["Vector"], group_outputs.inputs['OutColor'])
        blend_group.links.new(node_output_a.outputs["Value"], group_outputs.inputs['OutAlpha'])
        
        blend_group.inputs["DestinationAlpha"].default_value = 0.0
        blend_group.inputs["rgbGen"].default_value = [1.0, 1.0, 1.0, 1.0]
        return blend_group
    

class Lightgrid_Node(Generic_Node_Group):
    name = 'LightGrid'
    @classmethod
    def create_node_tree(self, empty):
        lightgrid_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_inputs = lightgrid_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-1600,0)
        lightgrid_group.inputs.new('NodeSocketFloat','ZOffset')
        group_inputs.outputs["ZOffset"].default_value = 0.0
        lightgrid_group.inputs.new('NodeSocketVector','LightGridOrigin')
        lightgrid_group.inputs.new('NodeSocketVector','LightGridInverseSize')
        lightgrid_group.inputs.new('NodeSocketVector','LightGridInverseDimension')
        
        group_outputs = lightgrid_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300,0)
        lightgrid_group.outputs.new('NodeSocketVector','LightGridLight')
        lightgrid_group.outputs.new('NodeSocketVector','LightGridVector')
                
        node_object = lightgrid_group.nodes.new(type="ShaderNodeObjectInfo")
        node_object.name = "Object"
        node_object.location = (-1600,100)
        
        node_off_vec = lightgrid_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_off_vec.name = "OffsetVector"
        node_off_vec.location = (-1600,300)
        lightgrid_group.links.new(group_inputs.outputs["ZOffset"], node_off_vec.inputs[2])
        node_off_vec.inputs[0].default_value = 0.0
        node_off_vec.inputs[1].default_value = 0.0
        
        node_z_pos = lightgrid_group.nodes.new(type="ShaderNodeVectorMath")
        node_z_pos.name = "ObjectZOffset"
        node_z_pos.operation = "ADD"
        node_z_pos.location = (-1400,100)
        lightgrid_group.links.new(node_object.outputs["Location"], node_z_pos.inputs[0])
        lightgrid_group.links.new(node_off_vec.outputs["Vector"], node_z_pos.inputs[1])
                
        node_local_pos = lightgrid_group.nodes.new(type="ShaderNodeVectorMath")
        node_local_pos.name = "LocalPos"
        node_local_pos.operation = "SUBTRACT"
        node_local_pos.location = (-1200,100)
        lightgrid_group.links.new(node_z_pos.outputs["Vector"], node_local_pos.inputs[0])
        lightgrid_group.links.new(group_inputs.outputs["LightGridOrigin"], node_local_pos.inputs[1])
            
        node_cell_id = lightgrid_group.nodes.new(type="ShaderNodeMixRGB")
        node_cell_id.name = "CellId"
        node_cell_id.blend_type = "MULTIPLY"
        node_cell_id.inputs[0].default_value = 1.0
        node_cell_id.location = (-1000,100)
        lightgrid_group.links.new(node_local_pos.outputs["Vector"], node_cell_id.inputs["Color1"])
        lightgrid_group.links.new(group_inputs.outputs["LightGridInverseSize"], node_cell_id.inputs["Color2"])
        
        node_seperate_id = lightgrid_group.nodes.new(type="ShaderNodeSeparateXYZ")
        node_seperate_id.name = "CellIdSeperated"
        node_seperate_id.location = (-800,100)
        lightgrid_group.links.new(node_cell_id.outputs["Color"], node_seperate_id.inputs["Vector"])
        
        node_seperate_inv_dim = lightgrid_group.nodes.new(type="ShaderNodeSeparateXYZ")
        node_seperate_inv_dim.name = "InverseDimensionSeperated"
        node_seperate_inv_dim.location = (-1000,-400)
        lightgrid_group.links.new(group_inputs.outputs["LightGridInverseDimension"], node_seperate_inv_dim.inputs["Vector"])
                
        node_math_ceil = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_ceil.operation = "CEIL"
        node_math_ceil.name = "Ceil"
        node_math_ceil.location = (-600,-200)
        node_math_floor = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_floor.operation = "FLOOR"
        node_math_floor.name = "Floor"
        node_math_floor.location = (-600,-400)
        lightgrid_group.links.new(node_seperate_id.outputs["Z"], node_math_ceil.inputs[0])
        lightgrid_group.links.new(node_seperate_id.outputs["Z"], node_math_floor.inputs[0])
                
        node_math_mult1 = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_mult1.operation = "MULTIPLY"
        node_math_mult1.name = "MULTIPLY1"
        node_math_mult1.location = (-400,200)
        lightgrid_group.links.new(node_seperate_id.outputs["X"], node_math_mult1.inputs[0])
        lightgrid_group.links.new(node_seperate_inv_dim.outputs["X"], node_math_mult1.inputs[1])
        node_math_mult2 = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_mult2.operation = "MULTIPLY"
        node_math_mult2.name = "MULTIPLY2"
        lightgrid_group.links.new(node_seperate_id.outputs["Y"], node_math_mult2.inputs[0])
        lightgrid_group.links.new(node_seperate_inv_dim.outputs["Y"], node_math_mult2.inputs[1])
        node_math_mult2.location = (-400,0)
        node_math_mult3 = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_mult3.operation = "MULTIPLY"
        node_math_mult3.name = "MULTIPLY3"
        lightgrid_group.links.new(node_math_ceil.outputs[0], node_math_mult3.inputs[0])
        lightgrid_group.links.new(node_seperate_inv_dim.outputs["Z"], node_math_mult3.inputs[1])
        node_math_mult3.location = (-400,-200)
        node_math_mult4 = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_mult4.operation = "MULTIPLY"
        node_math_mult4.name = "MULTIPLY4"
        node_math_mult4.location = (-400,-400)
        lightgrid_group.links.new(node_math_floor.outputs[0], node_math_mult4.inputs[0])
        lightgrid_group.links.new(node_seperate_inv_dim.outputs["Z"], node_math_mult4.inputs[1])
                
        node_math_add1 = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_add1.operation = "ADD"
        node_math_add1.name = "ADD1"
        node_math_add1.location = (-200,-200)
        lightgrid_group.links.new(node_math_mult2.outputs[0], node_math_add1.inputs[0])
        lightgrid_group.links.new(node_math_mult3.outputs[0], node_math_add1.inputs[1])
        node_math_add2 = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_add2.operation = "ADD"
        node_math_add2.name = "ADD2"
        node_math_add2.location = (-200,-400)
        lightgrid_group.links.new(node_math_mult2.outputs[0], node_math_add2.inputs[0])
        lightgrid_group.links.new(node_math_mult4.outputs[0], node_math_add2.inputs[1])
                
        node_upper_tc = lightgrid_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_upper_tc.name = "GridHighTC"
        node_upper_tc.location = (0,-200)
        lightgrid_group.links.new(node_math_mult1.outputs[0], node_upper_tc.inputs["X"])
        lightgrid_group.links.new(node_math_add1.outputs[0], node_upper_tc.inputs["Y"])
        node_lower_tc = lightgrid_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_lower_tc.name = "GridLowTC"
        node_lower_tc.location = (0,-400)
        lightgrid_group.links.new(node_math_mult1.outputs[0], node_lower_tc.inputs["X"])
        lightgrid_group.links.new(node_math_add2.outputs[0], node_lower_tc.inputs["Y"])
        
        image_a1 = bpy.data.images.get("$lightgrid_ambient1")
        if image_a1 != None:
            node_a1_up = lightgrid_group.nodes.new(type='ShaderNodeTexImage')
            node_a1_up.image = image_a1
            node_a1_up.location = (200,0)
            lightgrid_group.links.new(node_upper_tc.outputs[0], node_a1_up.inputs["Vector"])
            
            node_a1_low = lightgrid_group.nodes.new(type='ShaderNodeTexImage')
            node_a1_low.image = image_a1
            node_a1_low.location = (200,-200)
            lightgrid_group.links.new(node_lower_tc.outputs[0], node_a1_low.inputs["Vector"])
        else:
            node_a1_up = lightgrid_group.nodes.new(type='ShaderNodeRGB')
            node_a1_up.name = "Ambient light helper"
            node_a1_up.outputs[0].default_value = (0.3, 0.123, 0.0, 1.0)
            node_a1_low = node_a1_up
        
        image_d1 = bpy.data.images.get("$lightgrid_direct1")
        if image_d1 != None:
            node_d1_up = lightgrid_group.nodes.new(type='ShaderNodeTexImage')
            node_d1_up.image = image_d1
            node_d1_up.location = (200,-400)
            lightgrid_group.links.new(node_upper_tc.outputs[0], node_d1_up.inputs["Vector"])
            
            node_d1_low = lightgrid_group.nodes.new(type='ShaderNodeTexImage')
            node_d1_low.image = image_d1
            node_d1_low.location = (200,-600)
            lightgrid_group.links.new(node_lower_tc.outputs[0], node_d1_low.inputs["Vector"])
        else:
            node_d1_up = lightgrid_group.nodes.new(type='ShaderNodeRGB')
            node_d1_up.name = "Direct light helper"
            node_d1_up.outputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
            node_d1_low = node_d1_up
            
        image_vec = bpy.data.images.get("$lightgrid_vector")
        if image_vec != None:
            node_vec_up = lightgrid_group.nodes.new(type='ShaderNodeTexImage')
            node_vec_up.image = image_vec
            node_vec_up.location = (200,-800)
            lightgrid_group.links.new(node_upper_tc.outputs[0], node_vec_up.inputs["Vector"])
                    
            node_vec_low = lightgrid_group.nodes.new(type='ShaderNodeTexImage')
            node_vec_low.image = image_vec
            node_vec_low.location = (200,-1000)
            lightgrid_group.links.new(node_lower_tc.outputs[0], node_vec_low.inputs["Vector"])
        else:
            node_vec_up = lightgrid_group.nodes.new(type='ShaderNodeNormal')
            node_vec_up.name = "Light direction helper"
            node_vec_up.outputs[0].default_value = (0.5, 0.3, 0.2)
            node_vec_low = node_vec_up
                
        node_math_fract = lightgrid_group.nodes.new(type="ShaderNodeMath")
        node_math_fract.operation = "FRACT"
        node_math_fract.name = "Fract"
        node_math_fract.location = (200,200)
        lightgrid_group.links.new(node_seperate_id.outputs["Z"], node_math_fract.inputs[0])
            
        node_out_ambient = lightgrid_group.nodes.new(type="ShaderNodeMixRGB")
        node_out_ambient.name = "Ambient"
        node_out_ambient.location = (600,-200)
        lightgrid_group.links.new(node_a1_low.outputs["Color"], node_out_ambient.inputs["Color1"])
        lightgrid_group.links.new(node_a1_up.outputs["Color"], node_out_ambient.inputs["Color2"])
        lightgrid_group.links.new(node_math_fract.outputs[0], node_out_ambient.inputs["Fac"])
                
        node_out_direct = lightgrid_group.nodes.new(type="ShaderNodeMixRGB")
        node_out_direct.name = "Direct"
        node_out_direct.location = (600,-600)
        lightgrid_group.links.new(node_d1_low.outputs["Color"], node_out_direct.inputs["Color1"])
        lightgrid_group.links.new(node_d1_up.outputs["Color"], node_out_direct.inputs["Color2"])
        lightgrid_group.links.new(node_math_fract.outputs[0], node_out_direct.inputs["Fac"])
        
        node_geometry = lightgrid_group.nodes.new(type="ShaderNodeNewGeometry")
        node_geometry.name = "Geometry"
        node_geometry.location = (600,-750)     
          
        node_out_vector = lightgrid_group.nodes.new(type="ShaderNodeMixRGB")
        node_out_vector.name = "Vector"
        node_out_vector.location = (600,-1000)
        lightgrid_group.links.new(node_vec_low.outputs[0], node_out_vector.inputs["Color1"])
        lightgrid_group.links.new(node_vec_up.outputs[0], node_out_vector.inputs["Color2"])
        lightgrid_group.links.new(node_math_fract.outputs[0], node_out_vector.inputs["Fac"])
        
        node_out_vector_normalized = lightgrid_group.nodes.new(type="ShaderNodeVectorMath")
        node_out_vector_normalized.name = "NormalizedVector"
        node_out_vector_normalized.location = (900,-1000)
        node_out_vector_normalized.operation = "NORMALIZE"
        lightgrid_group.links.new(node_out_vector.outputs["Color"], node_out_vector_normalized.inputs["Vector"])
        
        node_attenuation = lightgrid_group.nodes.new(type="ShaderNodeVectorMath")
        node_attenuation.name = "DirectAttenuation"
        node_attenuation.operation = "DOT_PRODUCT"
        node_attenuation.location = (1200,-1000)
        lightgrid_group.links.new(node_geometry.outputs["Normal"], node_attenuation.inputs[0])
        lightgrid_group.links.new(node_out_vector_normalized.outputs["Vector"], node_attenuation.inputs[1])
        
        node_direct_light = lightgrid_group.nodes.new(type="ShaderNodeMixRGB")
        node_direct_light.name = "DirectLight"
        node_direct_light.blend_type = "MULTIPLY"
        node_direct_light.use_clamp = True
        node_direct_light.inputs[0].default_value = 1.0
        node_direct_light.location = (1200,-300)
        lightgrid_group.links.new(node_out_direct.outputs["Color"], node_direct_light.inputs["Color1"])
        lightgrid_group.links.new(node_attenuation.outputs["Value"], node_direct_light.inputs["Color2"])
        
        node_grid_light = lightgrid_group.nodes.new(type="ShaderNodeVectorMath")
        node_grid_light.name = "GridLight"
        node_grid_light.operation = "ADD"
        node_grid_light.location = (1500,-300)
        lightgrid_group.links.new(node_direct_light.outputs["Color"], node_grid_light.inputs[0])
        lightgrid_group.links.new(node_out_ambient.outputs["Color"], node_grid_light.inputs[1])
        
        lightgrid_group.links.new(node_grid_light.outputs["Vector"], group_outputs.inputs['LightGridLight'])
        lightgrid_group.links.new(node_out_vector_normalized.outputs["Vector"], group_outputs.inputs['LightGridVector'])
        return lightgrid_group

class TcGen_Env_Node(Generic_Node_Group):
    name = 'tcgen environment'
    @classmethod
    def create_node_tree(self, variable):
        tc_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_outputs = tc_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1100,0)
        tc_group.outputs.new('NodeSocketVector','UV')
        
        node_geometry = tc_group.nodes.new(type="ShaderNodeNewGeometry")
        node_geometry.location = (0,0)
        
        node_dot = tc_group.nodes.new(type="ShaderNodeVectorMath")
        node_dot.name = "Dot"
        node_dot.operation = "DOT_PRODUCT"
        node_dot.location = (200, 0)
        tc_group.links.new(node_geometry.outputs["Normal"], node_dot.inputs[0])
        tc_group.links.new(node_geometry.outputs["Incoming"], node_dot.inputs[1])
        
        node_mult = tc_group.nodes.new(type="ShaderNodeMixRGB")
        node_mult.name = "Term1"
        node_mult.blend_type = "MULTIPLY"
        node_mult.inputs[0].default_value = 1.0
        node_mult.location = (500, 0)
        tc_group.links.new(node_geometry.outputs["Normal"], node_mult.inputs["Color1"])
        tc_group.links.new(node_dot.outputs["Value"], node_mult.inputs["Color2"])
        
        node_mult2 = tc_group.nodes.new(type="ShaderNodeMixRGB")
        node_mult2.name = "Term1"
        node_mult2.blend_type = "MULTIPLY"
        node_mult2.inputs[0].default_value = 1.0
        node_mult2.location = (500,-300)
        tc_group.links.new(node_geometry.outputs["Incoming"], node_mult2.inputs["Color1"])
        node_mult2.inputs["Color2"].default_value = [0.5, 0.5, 0.0, 0.0]
        
        node_sub = tc_group.nodes.new(type="ShaderNodeVectorMath")
        node_sub.name = "Subtract"
        node_sub.operation = "SUBTRACT"
        node_sub.location = (800, 0)
        tc_group.links.new(node_mult.outputs["Color"], node_sub.inputs[0])
        tc_group.links.new(node_mult2.outputs["Color"], node_sub.inputs[1])
        
        tc_group.links.new(node_sub.outputs["Vector"], group_outputs.inputs['UV'])
        return tc_group
    
class AlphaGen_Spec_Node(Generic_Node_Group):
    name = 'AGen_Spec'
    @classmethod
    def create_node_tree(self, variable):
        alpha_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_outputs = alpha_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300,0)
        alpha_group.outputs.new('NodeSocketFloat','Value')
        
        group_inputs = alpha_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-1600,0)
        alpha_group.inputs.new('NodeSocketVector','LightVector')
        
        node_geometry = alpha_group.nodes.new(type="ShaderNodeNewGeometry")
        node_geometry.location = (0,0)
        
        node_dot = alpha_group.nodes.new(type="ShaderNodeVectorMath")
        node_dot.name = "Dot"
        node_dot.operation = "DOT_PRODUCT"
        node_dot.location = (1000,-300)
        alpha_group.links.new(node_geometry.outputs["Normal"], node_dot.inputs[1])
        alpha_group.links.new(group_inputs.outputs["LightVector"], node_dot.inputs[0])
        
        node_mult2 = alpha_group.nodes.new(type="ShaderNodeMath")
        node_mult2.name = "Times2"
        node_mult2.operation = "MULTIPLY"
        node_mult2.inputs[1].default_value = 2.0
        node_mult2.location = (800,-300)
        alpha_group.links.new(node_dot.outputs["Value"], node_mult2.inputs[0])
        
        node_mult = alpha_group.nodes.new(type="ShaderNodeMixRGB")
        node_mult.name = "Term1"
        node_mult.blend_type = "MULTIPLY"
        node_mult.inputs[0].default_value = 1.0
        node_mult.location = (800,-300)
        alpha_group.links.new(node_geometry.outputs["Normal"], node_mult.inputs["Color2"])
        alpha_group.links.new(node_mult2.outputs["Value"], node_mult.inputs["Color1"])
        
        node_sub = alpha_group.nodes.new(type="ShaderNodeVectorMath")
        node_sub.name = "Subtract"
        node_sub.operation = "SUBTRACT"
        node_sub.location = (1000,-300)
        alpha_group.links.new(node_mult.outputs["Color"], node_sub.inputs[0])
        alpha_group.links.new(group_inputs.outputs["LightVector"], node_sub.inputs[1])
        
        node_dot2 = alpha_group.nodes.new(type="ShaderNodeVectorMath")
        node_dot2.name = "Dot"
        node_dot2.operation = "DOT_PRODUCT"
        node_dot2.location = (1000,-300)
        alpha_group.links.new(node_sub.outputs["Vector"], node_dot2.inputs[0])
        alpha_group.links.new(node_geometry.outputs["Incoming"], node_dot2.inputs[1])
        
        node_l = alpha_group.nodes.new(type="ShaderNodeMath")
        node_l.name = "LightFactor"
        node_l.operation = "MAXIMUM"
        node_l.location = (800,-300)
        alpha_group.links.new(node_dot2.outputs["Value"], node_l.inputs[0])
        node_l.inputs[1].default_value = 0.0
        
        node_out = alpha_group.nodes.new(type="ShaderNodeMath")
        node_out.name = "OUT"
        node_out.operation = "POWER"
        node_out.location = (800,-300)
        node_out.use_clamp = True
        alpha_group.links.new(node_l.outputs["Value"], node_out.inputs[0])
        node_out.inputs[1].default_value = 4.0
        
        alpha_group.links.new(node_out.outputs["Value"], group_outputs.inputs['Value'])
        return alpha_group

class Shader_Time_Node(Generic_Node_Group):
    name = 'Shader_Time'
    @classmethod
    def create_node_tree(self, variable):
        time_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_outputs = time_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300, 0)
        time_group.outputs.new('NodeSocketFloat','Time')
        
        start_end = [bpy.context.scene.frame_start, bpy.context.scene.frame_end]
        
        node_frame = time_group.nodes.new(type="ShaderNodeValue")
        node_frame.name = "FRAME"
        node_frame.location = (600, 0)
        
        newdriver = node_frame.outputs["Value"].driver_add('default_value')
        newdriver.driver.expression = "frame"
        
        node_out = time_group.nodes.new(type="ShaderNodeMath")
        node_out.name = "OUT"
        node_out.operation = "DIVIDE"
        node_out.location = (1000, 0)
        node_out.inputs[1].default_value = 25.0
        time_group.links.new(node_frame.outputs["Value"], node_out.inputs[0])
        
        time_group.links.new(node_out.outputs["Value"], group_outputs.inputs['Time'])
        
        return time_group
    
class Shader_Rotate_Node(Generic_Node_Group):
    name = "tcMod rotate"
    @classmethod
    def create_node_tree(self, variable):
        rotate_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_outputs = rotate_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300, 0 )
        rotate_group.outputs.new('NodeSocketVector','Vector')
        
        group_inputs = rotate_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-1600, 0 )
        rotate_group.inputs.new('NodeSocketVector','Vector')
        rotate_group.inputs.new('NodeSocketFloat','Degrees')
        
        rotate_group.inputs.new('NodeSocketFloat','Time')
        
        node_dps = rotate_group.nodes.new(type="ShaderNodeMath")
        node_dps.name = "Degree per second"
        node_dps.operation = "MULTIPLY"
        node_dps.inputs[0].default_value = 1.0
        node_dps.location = (-800,-300)
        rotate_group.links.new(group_inputs.outputs["Degrees"], node_dps.inputs[0])
        rotate_group.links.new(group_inputs.outputs["Time"], node_dps.inputs[1])
        
        node_rps = rotate_group.nodes.new(type="ShaderNodeMath")
        node_rps.name = "Radians per second"
        node_rps.operation = "MULTIPLY"
        node_rps.inputs[0].default_value = 0.01745
        node_rps.location = (-500,-300)
        rotate_group.links.new(node_dps.outputs[0], node_rps.inputs[1])
        
        node_sine = rotate_group.nodes.new(type="ShaderNodeMath")
        node_sine.name = "Sine"
        node_sine.operation = "SINE"
        node_sine.location = (-400, 0 )
        rotate_group.links.new(node_rps.outputs[0], node_sine.inputs[0])
        
        node_minus_sine = rotate_group.nodes.new(type="ShaderNodeMath")
        node_minus_sine.name = "Minus Sine"
        node_minus_sine.operation = "MULTIPLY"
        node_minus_sine.location = (-400,-300 )
        node_minus_sine.inputs[1].default_value = -1.0
        rotate_group.links.new(node_sine.outputs[0], node_minus_sine.inputs[0])
        
        node_cosine = rotate_group.nodes.new(type="ShaderNodeMath")
        node_cosine.name = "Cosine"
        node_cosine.operation = "COSINE"
        node_cosine.location = (-400,-300 )
        rotate_group.links.new(node_rps.outputs[0], node_cosine.inputs[0])
        
        node_sep = rotate_group.nodes.new(type="ShaderNodeSeparateXYZ")
        node_sep.name = "UV Separated"
        node_sep.location = ( 0,-300 )
        rotate_group.links.new(group_inputs.outputs["Vector"], node_sep.inputs[0])
        
        node_t1 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t1.name = "half Sine"
        node_t1.operation = "MULTIPLY"
        node_t1.location = (-400, 300 )
        node_t1.inputs[1].default_value = 0.5
        rotate_group.links.new(node_sine.outputs[0], node_t1.inputs[0])
        
        node_t2 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t2.name = "half minus Sine"
        node_t2.operation = "MULTIPLY"
        node_t2.location = (-400, 300 )
        node_t2.inputs[1].default_value = -0.5
        rotate_group.links.new(node_sine.outputs[0], node_t2.inputs[0])
        
        node_t3 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t3.name = "half minus Cosine"
        node_t3.operation = "MULTIPLY"
        node_t3.location = (-400, 300 )
        node_t3.inputs[1].default_value = -0.5
        rotate_group.links.new(node_cosine.outputs[0], node_t3.inputs[0])
        
        node_t4 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t4.name = "S1"
        node_t4.operation = "MULTIPLY"
        node_t4.location = (-400,-300 )
        rotate_group.links.new(node_cosine.outputs[0], node_t4.inputs[0])
        rotate_group.links.new(node_sep.outputs["X"], node_t4.inputs[1])
        
        node_t5 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t5.name = "S2"
        node_t5.operation = "MULTIPLY"
        node_t5.location = (-400,-300 )
        rotate_group.links.new(node_minus_sine.outputs[0], node_t5.inputs[0])
        rotate_group.links.new(node_sep.outputs["Y"], node_t5.inputs[1])
        
        node_t6 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t6.name = "T1"
        node_t6.operation = "MULTIPLY"
        node_t6.location = (-400,-300 )
        rotate_group.links.new(node_sine.outputs[0], node_t6.inputs[0])
        rotate_group.links.new(node_sep.outputs["X"], node_t6.inputs[1])
        
        node_t7 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t7.name = "T2"
        node_t7.operation = "MULTIPLY"
        node_t7.location = (-400,-300 )
        rotate_group.links.new(node_cosine.outputs[0], node_t7.inputs[0])
        rotate_group.links.new(node_sep.outputs["Y"], node_t7.inputs[1])
        
        node_t8 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t8.name = "S3"
        node_t8.operation = "ADD"
        node_t8.location = (-400,-300 )
        rotate_group.links.new(node_t1.outputs[0], node_t8.inputs[0])
        rotate_group.links.new(node_t3.outputs[0], node_t8.inputs[1])
        
        node_t9 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t9.name = "T3"
        node_t9.operation = "ADD"
        node_t9.location = (-400,-300 )
        rotate_group.links.new(node_t2.outputs[0], node_t9.inputs[0])
        rotate_group.links.new(node_t3.outputs[0], node_t9.inputs[1])
        
        # combine rotations
        node_t10 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t10.name = "S rotated"
        node_t10.operation = "ADD"
        node_t10.location = (-400,-300 )
        rotate_group.links.new(node_t4.outputs[0], node_t10.inputs[0])
        rotate_group.links.new(node_t5.outputs[0], node_t10.inputs[1])
        
        node_t11 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t11.name = "T rotated"
        node_t11.operation = "ADD"
        node_t11.location = (-400,-300 )
        rotate_group.links.new(node_t6.outputs[0], node_t11.inputs[0])
        rotate_group.links.new(node_t7.outputs[0], node_t11.inputs[1])
        
        #shifting
        node_t12 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t12.name = "S shift"
        node_t12.operation = "ADD"
        node_t12.location = (-400,-300 )
        node_t12.inputs[1].default_value = 0.5
        rotate_group.links.new(node_t8.outputs[0], node_t12.inputs[0])
        
        node_t13 = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t13.name = "T shift"
        node_t13.operation = "ADD"
        node_t13.location = (-400,-300 )
        node_t13.inputs[1].default_value = 0.5
        rotate_group.links.new(node_t9.outputs[0], node_t13.inputs[0])
        
        #final UV
        node_s = rotate_group.nodes.new(type="ShaderNodeMath")
        node_s.name = "S"
        node_s.operation = "ADD"
        node_s.location = (-400,-300 )
        rotate_group.links.new(node_t12.outputs[0], node_s.inputs[0])
        rotate_group.links.new(node_t10.outputs[0], node_s.inputs[1])
        
        node_t = rotate_group.nodes.new(type="ShaderNodeMath")
        node_t.name = "T"
        node_t.operation = "ADD"
        node_t.location = (-400,-300 )
        rotate_group.links.new(node_t13.outputs[0], node_t.inputs[0])
        rotate_group.links.new(node_t11.outputs[0], node_t.inputs[1])
        
        node_uv = rotate_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_uv.name = "UV Out"
        node_uv.location = ( 0,-300 )
        rotate_group.links.new(node_s.outputs[0], node_uv.inputs["X"])
        rotate_group.links.new(node_t.outputs[0], node_uv.inputs["Y"])
        
        rotate_group.links.new(node_uv.outputs["Vector"], group_outputs.inputs["Vector"])
        
        return rotate_group

class Shader_Scroll_Node(Generic_Node_Group):
    name = "tcMod scroll"
    @classmethod
    def create_node_tree(self, variable):
        scroll_group = bpy.data.node_groups.new(self.name, 'ShaderNodeTree')
        
        group_outputs = scroll_group.nodes.new('NodeGroupOutput')
        group_outputs.location = (1300, 0)
        scroll_group.outputs.new('NodeSocketVector','Vector')
        
        group_inputs = scroll_group.nodes.new('NodeGroupInput')
        group_inputs.location = (-1600,0)
        scroll_group.inputs.new('NodeSocketVector','Vector')
        scroll_group.inputs.new('NodeSocketVector','Arguments')
        
        scroll_group.inputs.new('NodeSocketFloat','Time')
        
        node_mult = scroll_group.nodes.new(type="ShaderNodeMixRGB")
        node_mult.name = "Term1"
        node_mult.blend_type = "MULTIPLY"
        node_mult.inputs[0].default_value = 1.0
        node_mult.location = (-800,-300)
        scroll_group.links.new(group_inputs.outputs["Arguments"], node_mult.inputs["Color1"])
        scroll_group.links.new(group_inputs.outputs["Time"], node_mult.inputs["Color2"])
        
        node_sep = scroll_group.nodes.new(type="ShaderNodeSeparateXYZ")
        node_sep.name = "UV Separated"
        node_sep.location = ( 0, 0 )
        scroll_group.links.new(node_mult.outputs["Color"], node_sep.inputs[0])
        
        node_mult2 = scroll_group.nodes.new(type="ShaderNodeMath")
        node_mult2.name = "Term2"
        node_mult2.operation = "MULTIPLY"
        node_mult2.inputs[1].default_value = -1.0
        node_mult2.location = (-800,-300)
        scroll_group.links.new(node_sep.outputs["X"], node_mult2.inputs[0])
        
        node_uv = scroll_group.nodes.new(type="ShaderNodeCombineXYZ")
        node_uv.name = "UV Out"
        node_uv.location = ( 0,-300 )
        scroll_group.links.new(node_mult2.outputs[0], node_uv.inputs["X"])
        scroll_group.links.new(node_sep.outputs["Y"], node_uv.inputs["Y"])
        
        node_sub = scroll_group.nodes.new(type="ShaderNodeVectorMath")
        node_sub.name = "Term3"
        node_sub.operation = "SUBTRACT"
        node_sub.location = (800,-300)
        scroll_group.links.new(group_inputs.outputs["Vector"], node_sub.inputs[0])
        scroll_group.links.new(node_uv.outputs["Vector"], node_sub.inputs[1])
        
        scroll_group.links.new(node_sub.outputs["Vector"], group_outputs.inputs["Vector"])
        
        return scroll_group