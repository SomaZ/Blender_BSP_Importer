import bpy
from ctypes import (LittleEndianStructure,
                    c_char, c_float, c_int, c_short, sizeof)
import mathutils
from .idtech3lib.Parsing import guess_model_name

class SKB_HEADER(LittleEndianStructure):
    _fields_ = [
        ("ident", c_char*4),
        ("version", c_int),
        ("name", c_char*64),
        
        ("numSurfaces", c_int),
        ("numBones", c_int),
        ("ofsBones", c_int),
        
        ("ofsSurfaces", c_int),
        ("ofsBoneBaseFrame", c_int),
        
        ("ofsEnd", c_int),
    ]
    
class SKB_FRAME(LittleEndianStructure):
    _fields_ = [
        ("min_bounds", c_float*3),
        ("max_bounds", c_float*3),
        ("radius", c_float),
        ("localOrigin", c_float*3),
        # bones
    ]
    
class SKB_BONE(LittleEndianStructure):
    _fields_ = [
        ("quat", c_short*4),
        ("offset", c_short*3),
        ("unused", c_short)
    ]
    
class SKB_BONE_INFO(LittleEndianStructure):
    _fields_ = [
        ("parent", c_int),
        ("flags", c_int),
        ("name", c_char*64)
    ]
    
class SKB_SURFACE(LittleEndianStructure):
    _fields_ = [
        ("ident", c_int),
        ("name", c_char*64),
        
        ("numTriangles", c_int),
        ("numVerts", c_int),
        ("numModelVerts", c_int),
        
        ("ofsTriangles", c_int),
        ("ofsVerts", c_int),
        ("ofsCollapse", c_int),
        
        ("ofsEnd", c_int),
    ]
    
class SKB_VERT(LittleEndianStructure):
    _fields_ = [
        ("normal", c_float*3),
        ("texCoords", c_float*2),
        ("numWeights", c_int),
        # weights
    ]
    
class SKB_WEIGHT(LittleEndianStructure):
    _fields_ = [
        ("boneIndex", c_int),
        ("boneWeight", c_float),
        ("offset", c_float*3),
    ]
    
class SKB_TRIANGLE(LittleEndianStructure):
    _fields_ = [
        ("indices", c_int*3),
    ]

scale_vec = 1.0 / 32767.0
scale_pos = 1.0 / 64.0

def ImportSKB(VFS,
              model_name,
              skin_map
              ):
    if not VFS:
        print("Tried importing a skb without a virtual file system")
        return []
    
    byte_array = VFS.get(model_name)
    if not byte_array:
        print("Couldn't read the skb file")
        return []
    
    guessed_name = guess_model_name(model_name.lower()).lower()
    if guessed_name.endswith(".skb"):
        guessed_name = guessed_name[:-len(".skb")]

    offset = 0
    header = SKB_HEADER.from_buffer_copy(byte_array, offset)
    print("header: {}, {}, {}\nnumSurf: {}\nnumBones: {}".format(
        header.ident,
        header.version,
        header.name,
        header.numSurfaces,
        header.numBones,
        header.ofsBones,
        header.ofsSurfaces,
        header.ofsBoneBaseFrame,
        header.ofsEnd,
        ))
    offset += sizeof(SKB_HEADER)

    if header.ident != b"SKL " or header.version != 4:
        print("Not a valid or supported .skb file", model_name)
        return []

    armature_obj = bpy.data.objects.get(guessed_name)
    if armature_obj is None:
        armature = bpy.data.armatures.new(guessed_name)
        armature_obj = bpy.data.objects.new(guessed_name, armature)
        bpy.context.collection.objects.link(armature_obj)
    armature = armature_obj.data
    
    bone_names = []
    bone_objects = []
    bone_matrices = []
    objects = []

    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    bone_offset = header.ofsBones
    offset = header.ofsBoneBaseFrame
    for bone_index in range(header.numBones):
        bone_info = SKB_BONE_INFO.from_buffer_copy(byte_array, bone_offset)
        bone_name = bone_info.name.decode()
        bone_names.append(bone_name)
        bone_offset += sizeof(SKB_BONE_INFO)
        
        c_bone = SKB_BONE.from_buffer_copy(byte_array, offset)
        offset += sizeof(SKB_BONE)
        
        quat = mathutils.Quaternion()
        
        quat.x = (c_bone.quat[0] / 32767.0)
        quat.y = (c_bone.quat[1] / 32767.0) 
        quat.z = (c_bone.quat[2] / 32767.0) 
        quat.w = -(c_bone.quat[3] / 32767.0) 
        
        loc = mathutils.Vector([0, 0, 0, 1])
        loc.x = (c_bone.offset[0] / 64.0)
        loc.y = (c_bone.offset[1] / 64.0)
        loc.z = (c_bone.offset[2] / 64.0)
            
        mat = quat.to_matrix()
        mat.resize_4x4()
        mat.col[3] = loc
        
        if bone_info.parent != -1:
            mat = bone_matrices[bone_info.parent] @ mat
        
        bone_matrices.append(mat.copy())
        bone = armature.edit_bones.get(bone_name)
        if not bone:
            bone = armature.edit_bones.new(bone_name)
        bone.head = mat @ mathutils.Vector((0.0, 0.0, 0.0))
        bone.tail = mat @ mathutils.Vector((8.0, 0.0, 0.0))
        bone.align_roll(mathutils.Vector(mat.col[1][0:3]))
        
        bone_objects.append(bone)
        if bone_info.parent != -1:
            bone.parent = bone_objects[bone_info.parent]
            
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
    surf_ofs = header.ofsSurfaces
    for surf_index in range(header.numSurfaces):
        surface = SKB_SURFACE.from_buffer_copy(byte_array, surf_ofs)
            
        surface_name = surface.name.decode()
        vertex_pos = []
        vertex_nor = []
        vertex_tc = []
        face_indices = []
        face_tcs = []
        #face_shaders = []
        #shaderindex = 0
        #face_index_offset = 0
        face_material_index = []
        bone_map = {}
            
        vert_offset = surf_ofs + surface.ofsVerts
        for vertex_id in range(surface.numVerts):
            vertex = SKB_VERT.from_buffer_copy(byte_array, vert_offset)
            vert_offset += sizeof(SKB_VERT)
            vertex_tc.append(vertex.texCoords)
            position = mathutils.Vector([0.0, 0.0, 0.0])
            transform_mat = mathutils.Matrix() * 0
            for weight_id in range(vertex.numWeights):
                weight = SKB_WEIGHT.from_buffer_copy(byte_array, vert_offset)
                vert_offset += sizeof(SKB_WEIGHT)
                position += weight.boneWeight * (bone_matrices[weight.boneIndex] @ mathutils.Vector(weight.offset))
                transform_mat += bone_matrices[weight.boneIndex] * weight.boneWeight
                
                if weight.boneIndex in bone_map:
                    bone_map[weight.boneIndex].append((vertex_id, weight.boneWeight))
                else:
                    bone_map[weight.boneIndex] = [(vertex_id, weight.boneWeight)]
            vertex_pos.append(position)
            transform_mat.invert()
            transform_mat.transpose()
            vertex_nor.append(transform_mat @ mathutils.Vector(vertex.normal))
            
        index_offset = surf_ofs + surface.ofsTriangles
        for index_id in range(surface.numTriangles):
            triangle = SKB_TRIANGLE.from_buffer_copy(byte_array, index_offset).indices
            triangle[0], triangle[1] = triangle[1], triangle[0]
            index_offset += sizeof(SKB_TRIANGLE)
            face_indices.append(list(triangle))
            for i in triangle:
                face_tcs.append(vertex_tc[i][0])
                face_tcs.append(1.0 - vertex_tc[i][1])
            face_material_index.append(0)
            
        surf_ofs += surface.ofsEnd
            
        mesh = bpy.data.meshes.new(surface_name)
        mesh.from_pydata(vertex_pos, [], face_indices)
            
        shader_name = surface_name
        if skin_map is not None and surface.name.decode() in skin_map:
            shader_name = skin_map[surface.name.decode()]
            
        mat = bpy.data.materials.get(shader_name)
        if (mat is None):
            mat = bpy.data.materials.new(name=shader_name)
        mesh.materials.append(mat)
            
        mesh.polygons.foreach_set("material_index", face_material_index)
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.normals_split_custom_set_from_vertices(vertex_nor)

        mesh.uv_layers.new(do_init=False, name="UVMap")
        mesh.uv_layers["UVMap"].data.foreach_set(
            "uv", face_tcs)

        mesh.validate()
        mesh.update()
            
        obj = bpy.data.objects.new(surface_name, mesh)
        bpy.context.collection.objects.link(obj)
        obj.parent = armature_obj
        objects.append(obj)

        for bone in bone_map:
            vg = obj.vertex_groups.get(bone_names[bone])
            if vg is None:
                vg = obj.vertex_groups.new(name=bone_names[bone])
            for vert, weight in bone_map[bone]:
                vg.add([vert], weight, 'ADD')
        armatureModifier = obj.modifiers.new("armature", 'ARMATURE')
        armatureModifier.object = armature_obj
        armatureModifier.use_bone_envelopes = False

    return objects


def ImportSKBs(VFS, tik_dict):
    all_objects = []
    model_name = tik_dict["model"]
    skin_map = tik_dict["materials"]
    objects = ImportSKB(VFS, model_name, skin_map)
    all_objects += objects

    for obj in objects:
        if obj.name in tik_dict["no_draw"]:
            obj.name = obj.name + "_nodraw"
            obj.hide_render = True
            obj.hide_set(True)

    for replacement in tik_dict["replacement"]:
        objects = ImportSKB(VFS, replacement, skin_map)
        for obj in objects:
            if obj.name.split(".")[0] not in tik_dict["replacement"][replacement]:
                obj.hide_render = True
                obj.hide_set(True)
        all_objects += objects

    return all_objects
