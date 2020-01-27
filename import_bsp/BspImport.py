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

if "math" not in locals():
    import math
    
if "BspClasses" in locals():
    imp.reload( BspClasses )
else:
    from . import BspClasses
    
if "MD3" in locals():
    imp.reload( MD3 )
else:
    from . import MD3
    
if "BspGeneric" in locals():
    imp.reload( BspGeneric )
else:
    from . import BspGeneric
    
if "QuakeShader" in locals():
    imp.reload( QuakeShader )
else:
    from . import QuakeShader

if "struct" not in locals():
    import struct
    
if "StringProperty" not in locals():
    from bpy.props import StringProperty
    
from time import perf_counter

from bpy_extras.io_utils import unpack_list
from math import radians

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

#empty class for now, we will see what to do with it
class ImportSettings:
    pass

### The new operator ###
class Operator(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.id3_bsp"
    bl_label = "Import ID3 engine BSP (.bsp)"
    filename_ext = ".bsp"
    filter_glob : StringProperty(default="*.bsp", options={'HIDDEN'})

    filepath : bpy.props.StringProperty(name="File Path", description="File path used for importing the BSP file", maxlen= 1024, default="")
    preset : bpy.props.EnumProperty(name="Import preset", description="You can select wether you want to import a bsp for editing, rendering, or previewing.", default='PREVIEW', items=[
            ('PREVIEW', "Preview", "Trys to build eevee shaders, imports all misc_model_statics when available", 0),
            ('EDITING', "Editing", "Trys to build eevee shaders, imports all entitys", 1),
            #('RENDERING', "Rendering", "Trys to build fitting cycles shaders, only imports visable enities", 2),
        ])
    subdivisions : bpy.props.IntProperty(name="Patch subdivisions", description="How often a patch is subdivided at import", default=2)

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
        
        self.ImportBSP(import_settings)
        
        #set world color to black to remove additional lighting
        background = context.scene.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs[0].default_value = 0,0,0,1
        else:
            import_settings.log.append("WARNING: Could not set world color to black.")
        
        #for line in import_settings.log:
        #    print(line)
            
        return {'FINISHED'}
    
    def ImportEntities(self, bsp, import_settings):        
        clip_end = 12000
        
        lump = bsp.lumps["entities"]
        stringdata = []
        for i in lump.data:
            stringdata.append(i.char.decode("ascii"))
    
        entities_string = "".join(stringdata)
        ent = {}
        n_ent = 0
        ent_object = None
        md3_objects = []
        obj_list = []
        for line in entities_string.splitlines():
            if l_open(line):
                ent.clear()
            elif l_close(line):
                if "distancecull" in ent:
                    clip_end = float(ent["distancecull"].replace('"',''))
                    
                if "gridsize" in ent:
                    bsp.lightgrid_size = ent["gridsize"]
                    bsp.lightgrid_inverse_size = [  1.0 / float(bsp.lightgrid_size[0]),
                                                    1.0 / float(bsp.lightgrid_size[1]),
                                                    1.0 / float(bsp.lightgrid_size[2]) ]
                if "origin" in ent and self.properties.preset == "EDITING":
                    if (ent_object == None):
                        ent_object = bpy.ops.mesh.primitive_cube_add(size = 32.0, location=([0,0,0]))
                        ent_object = bpy.context.object
                        ent_object.name = "EntityBox"
                        mesh = ent_object.data
                        mesh.name = "EntityMesh"

                    cube = bpy.data.objects.new(name="Entity " + (str(n_ent).zfill(4)), object_data=mesh.copy())
                    cube.location = ent["origin"]
                    for key in ent:
                        cube.data[key] = ent[key]
                    bpy.context.collection.objects.link(cube)
                
                if "model" in ent and (ent["classname"] == "misc_model_static" or ent["classname"] == "misc_model_breakable"):
                    # FIXME: what if the model is not md3?
                    mesh_name = ent["model"][:-len(".md3")]
                    zoffset = 0
                    if "zoffset" in ent:
                        zoffset = int(ent["zoffset"].replace('"','')) + 1
                        mesh_name = mesh_name+".z"+str(zoffset)
                    
                    if mesh_name in md3_objects:
                        me = bpy.data.objects[mesh_name].data
                        ob = bpy.data.objects.new(mesh_name, me)
                    else:
                        #TODO: Fix reimporting model when only the zoffset is different
                        #check if model already loaded, make a copy of it, replace all the material names with new zoffset
                        me = MD3.ImportMD3(ent["model"], import_settings, zoffset)
                        ob = bpy.data.objects.new(mesh_name, me)
                        md3_objects.append(mesh_name)
                        obj_list.append(ob)
                    bpy.context.collection.objects.link(ob)
                    
                    ob.location = ent["origin"]
                    if "modelscale" in ent:
                        scale = (float(ent["modelscale"]),float(ent["modelscale"]),float(ent["modelscale"]))
                        ob.scale = scale
                    if "modelscale_vec" in ent:
                        ob.scale = ent["modelscale_vec"]
                    if "angle" in ent:
                        ob.rotation_euler = (0.0,0.0,radians(float(ent["angle"])))
                    if "angles" in ent:
                        ob.rotation_euler = (radians(ent["angles"][2]),radians(ent["angles"][0]),radians(ent["angles"][1]))                    
                    
                n_ent += 1
            elif line != " ":
                key,value = parse(line)
                key = key.strip(" \"\t\n\r")
                if (key == "origin") or (key == "modelscale_vec") or (key == "angles") or (key == "gridsize"):
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
                
        #set clip data
        for a in bpy.context.screen.areas:
            if a.type == 'VIEW_3D':
                for s in a.spaces:
                    if s.type == 'VIEW_3D':
                        s.clip_start = 4
                        s.clip_end = clip_end
                        
        
        return obj_list

    def ImportBSP(self, import_settings):
        
        dataPath = self.properties.filepath
        import_settings.log.append("----ImportBSP----")
        import_settings.log.append("bsp: " + dataPath)

        bsp = BspClasses.BSP(dataPath)

        if bsp.valid:
            #import lightmaps before packing vertex data 
            #because of varying packed lightmap size
            import_settings.log.append("----pack_lightmaps----")
            time_start = perf_counter()
            BspGeneric.pack_lightmaps(bsp, import_settings)
            import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
            
            import_settings.log.append("----fill_bsp_data----")
            time_start = perf_counter()
            model = BspGeneric.blender_model_data()
            model.fill_bsp_data(bsp, import_settings)
            import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")

            mesh = bpy.data.meshes.new( dataPath )
            mesh.from_pydata(model.vertices, [], model.face_vertices)

            for texture_instance in model.material_names:
                mat = bpy.data.materials.get(texture_instance)
                if (mat == None):
                    mat = bpy.data.materials.new(name=texture_instance)
                mesh.materials.append(mat)
                
            mesh.polygons.foreach_set("material_index", model.face_materials)
            
            for poly in mesh.polygons:
                poly.use_smooth = True
            
            mesh.vertices.foreach_set("normal", unpack_list(model.normals))

            mesh.vertex_layers_int.new(name="BSP_VERT_INDEX")
            mesh.vertex_layers_int["BSP_VERT_INDEX"].data.foreach_set("value", model.vertex_bsp_indices)

            mesh.uv_layers.new(do_init=False,name="UVMap")
            mesh.uv_layers["UVMap"].data.foreach_set("uv", unpack_list(unpack_list(model.face_tcs)))

            mesh.uv_layers.new(do_init=False,name="LightmapUV")
            mesh.uv_layers["LightmapUV"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm1_tcs)))
            
            mesh.vertex_colors.new(name = "Color")
            mesh.vertex_colors["Color"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color)))
            
            if bsp.lightmaps > 1:
                mesh.uv_layers.new(do_init=False,name="LightmapUV2")
                mesh.uv_layers["LightmapUV2"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm2_tcs)))

                mesh.uv_layers.new(do_init=False,name="LightmapUV3")
                mesh.uv_layers["LightmapUV3"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm3_tcs)))

                mesh.uv_layers.new(do_init=False,name="LightmapUV4")
                mesh.uv_layers["LightmapUV4"].data.foreach_set("uv", unpack_list(unpack_list(model.face_lm4_tcs)))

                mesh.vertex_colors.new(name = "Color2")
                mesh.vertex_colors["Color2"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color2)))

                mesh.vertex_colors.new(name = "Color3")
                mesh.vertex_colors["Color3"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color3)))

                mesh.vertex_colors.new(name = "Color4")
                mesh.vertex_colors["Color4"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_color4)))
            
            #ugly hack to get the vertex alpha.....
            mesh.vertex_colors.new(name = "Alpha")
            mesh.vertex_colors["Alpha"].data.foreach_set("color", unpack_list(unpack_list(model.face_vert_alpha)))    
            
            #q3 renders with front culling as default
            mesh.flip_normals()
            
            mesh.update()
            mesh.validate()

            bsp_obj = bpy.data.objects.new("BSP_Data", mesh)
            
            #import entities and get object list
            import_settings.log.append("----ImportEntities----")
            time_start = perf_counter()
            obj_list = self.ImportEntities(bsp, import_settings)
            obj_list.append(bsp_obj)
            import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
            
            #import lightgrid after entitys because the grid size can change
            import_settings.log.append("----pack_lightgrid----")
            time_start = perf_counter()
            BspGeneric.pack_lightgrid(bsp)
            import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
            
            #create whiteimage before parsing shaders
            BspGeneric.create_white_image()
            
            #init shader system
            QuakeShader.init_shader_system(bsp)
            
            #build shaders
            import_settings.log.append("----build_quake_shaders----")
            time_start = perf_counter()
            QuakeShader.build_quake_shaders(import_settings, obj_list)
            import_settings.log.append("took:" + str(perf_counter() - time_start) + " seconds")
            
            vg = bsp_obj.vertex_groups.get("Decals")
            if vg is not None:
                modifier = bsp_obj.modifiers.new("polygonOffset", type = "DISPLACE")
                modifier.vertex_group = "Decals"
                modifier.strength = 0.2
                modifier.name = "polygonOffset"
            
            bsp_obj.vertex_groups.new(name = "Patches")
            bsp_obj.vertex_groups["Patches"].add(list(model.patch_vertices), 1.0, "ADD")
            scene = bpy.context.scene
            scene.collection.objects.link(bsp_obj)
        
def menu_func(self, context):
    self.layout.operator(Operator.bl_idname, text="ID3 BSP (.bsp)")
    
#Panels
class Q3_PT_MappingPanel(bpy.types.Panel):
    bl_idname = "Q3_PT_shader_panel"
    bl_label = "Shaders"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Q3 Mapping"
    def draw(self, context):
        layout = self.layout
        
        scene = context.scene
        
        row = layout.row()
        row.scale_y = 1.0
        row.operator("q3mapping.reload_shader")
        layout.separator()
       
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
