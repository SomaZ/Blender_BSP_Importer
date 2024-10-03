import bpy
from ctypes import (LittleEndianStructure,
                    c_char, c_float, c_int, c_ushort, sizeof)
import mathutils
from .idtech3lib.Parsing import guess_model_name

def read_skin(file_lines):
    out = {}
    for line in file_lines:
        try:
            name, shader = line.split(",")
            out[name] = shader.strip()
        except Exception:
            print("Couldnt parse line:", line)
    return out

class MDR_HEADER(LittleEndianStructure):
    _fields_ = [
        ("magic_nr", c_char*4),
        ("version_nr", c_int),
        ("name", c_char*64),
        
        ("numFrames", c_int),
        ("numBones", c_int),
        ("ofsFrames", c_int),
        
        ("numLODs", c_int),
        ("ofsLODs", c_int),
        
        ("numTags", c_int),
        ("ofsTags", c_int),
        
        ("ofsEnd", c_int),
    ]
    
class MDR_COMPRESSED_FRAME(LittleEndianStructure):
    _fields_ = [
        ("min_bounds", c_float*3),
        ("max_bounds", c_float*3),
        ("localOrigin", c_float*3),
        ("radius", c_float),
        #compressed bones
    ]
    
class MDR_COMPRESSED_BONE(LittleEndianStructure):
    _fields_ = [
        ("values", c_ushort*12)
    ]
    
class MDR_LOD(LittleEndianStructure):
    _fields_ = [
        ("numSurfaces", c_int),
        ("ofsSurfaces", c_int),
        ("ofsEnd", c_int),
    ]
    
class MDR_SURFACE(LittleEndianStructure):
    _fields_ = [
        ("ident", c_int),
        ("name", c_char*64),
        ("shader", c_char*64),
        ("shaderIndex", c_int),
        
        ("ofsHeader", c_int),
        
        ("numVerts", c_int),
        ("ofsVerts", c_int),
        ("numTriangles", c_int),
        ("ofsTriangles", c_int),
        
        ("numBoneReferences", c_int),
        ("ofsBoneReferences", c_int),
        
        ("ofsEnd", c_int),
    ]
    
class MDR_BONE_REF(LittleEndianStructure):
    _fields_ = [
        ("boneIndex", c_int)
    ]
    
class MDR_VERT(LittleEndianStructure):
    _fields_ = [
        ("normal", c_float*3),
        ("texCoords", c_float*2),
        ("numWeights", c_int),
        # weights
    ]
    
class MDR_WEIGHT(LittleEndianStructure):
    _fields_ = [
        ("boneIndex", c_int),
        ("boneWeight", c_float),
        ("offset", c_float*3),
    ]
    
class MDR_TRIANGLE(LittleEndianStructure):
    _fields_ = [
        ("indices", c_int*3),
    ]

class MDR_TAG(LittleEndianStructure):
    _fields_ = [
        ("boneIndex", c_int),
        ("name", c_char*32),
    ]

scale_vec = 1.0 / 32767.0
scale_pos = 1.0 / 64.0

def get_correction_mats(header, byte_array):
    offset = header.ofsLODs
    lod = MDR_LOD.from_buffer_copy(byte_array, offset)
    
    normalizing_mats = [mathutils.Matrix() for i in range(header.numBones)]
    normalizing_weights = [0.0 for i in range(header.numBones)]
    
    surf_ofs = offset + lod.ofsSurfaces
    for surf_index in range(lod.numSurfaces):
        surface = MDR_SURFACE.from_buffer_copy(byte_array, surf_ofs)
        vert_offset = surf_ofs + surface.ofsVerts
        for vertex_id in range(surface.numVerts):
            vertex = MDR_VERT.from_buffer_copy(byte_array, vert_offset)
            vert_offset += sizeof(MDR_VERT)
            for weight_id in range(vertex.numWeights):
                weight = MDR_WEIGHT.from_buffer_copy(byte_array, vert_offset)
                vert_offset += sizeof(MDR_WEIGHT)
                normalizing_mats[weight.boneIndex].translation += mathutils.Vector(weight.offset)
                normalizing_weights[weight.boneIndex] += 1.0
        surf_ofs += surface.ofsEnd
    
    for i in range(header.numBones):
        if normalizing_weights[i] != 0.0:
            normalizing_mats[i].translation /= normalizing_weights[i]
    return normalizing_mats
        

def ImportMDR(VFS,
              model_name,
              skin_path,
              animations=None
              ):
    if not VFS:
        print("Tried importing a mdr without a virtual file system")
        return []
    
    byte_array = VFS.get(model_name)
    if not byte_array:
        print("Couldn't read the mdr file")
        return []
        
    skin_bytearray = VFS.get(skin_path)
    skin_map = None
    if skin_bytearray:
        skin_map = read_skin(
            skin_bytearray.decode().splitlines())
        
    guessed_name = guess_model_name(model_name.lower()).lower()
    if guessed_name.endswith(".mdr"):
        guessed_name = guessed_name[:-len(".mdr")]
    
    offset = 0
    header = MDR_HEADER.from_buffer_copy(byte_array, offset)
    print(
        "Ident:", header.magic_nr.decode(), header.version_nr,
        "\nName:", header.name.decode(),
        "\nNumber of Frames:", header.numFrames,
        "\nNumber of Bones:", header.numBones,
        "\nNumber of LODs:", header.numLODs,
        "\nNumber of Tags:", header.numTags,
        )
    offset += sizeof(MDR_HEADER)

    if header.magic_nr != b"RDM5" or header.version_nr != 2:
        print("Not a valid or supported .mdr file", model_name)
        return []
    
    armature_obj = bpy.data.objects.get(guessed_name)
    if armature_obj is None:
        armature = bpy.data.armatures.new(guessed_name)
        armature_obj = bpy.data.objects.new(guessed_name, armature)
        bpy.context.collection.objects.link(armature_obj)
        if guessed_name.endswith("lower"):
            armature_obj.location = (0.0, 0.0, 24.0)
        elif guessed_name.endswith("upper"):
            lower_obj = bpy.data.objects.get(guessed_name.replace("upper", "lower"))
            torso_bone = None
            if lower_obj:
                torso_bone = lower_obj.pose.bones.get("tag_torso")
            if torso_bone:
                for frame in range(bpy.context.scene.frame_end):
                    bpy.context.scene.frame_set(frame+1)
                    armature_obj.matrix_world = lower_obj.matrix_world @ torso_bone.matrix
                    armature_obj.keyframe_insert("location", frame=frame+1)
                    armature_obj.keyframe_insert("rotation_quaternion", frame=frame+1)

    objects = []
    armature = armature_obj.data
    
    normalizing_mats = get_correction_mats(header, byte_array)
    
    frames = []
    bone_matrices = []

    num_import_frames = header.numFrames if animations != "NONE" else 1
    bpy.context.scene.frame_end = num_import_frames
    bpy.context.view_layer.objects.active = armature_obj
    
    offset = -header.ofsFrames
    for frame_index in range(num_import_frames):
        frame = MDR_COMPRESSED_FRAME.from_buffer_copy(byte_array, offset)
        frames.append(frame)
        offset += sizeof(MDR_COMPRESSED_FRAME)
        
        for bone_index in range(header.numBones):
            c_bone = MDR_COMPRESSED_BONE.from_buffer_copy(byte_array, offset).values
            offset += sizeof(MDR_COMPRESSED_BONE)
            
            c_bone = [float(v) - 32767 for v in c_bone]
            
            c_bone[0] = c_bone[0] * scale_pos
            c_bone[1] = c_bone[1] * scale_pos
            c_bone[2] = c_bone[2] * scale_pos
            
            c_bone[3] = c_bone[3] * scale_vec
            c_bone[4] = c_bone[4] * scale_vec
            c_bone[5] = c_bone[5] * scale_vec
            c_bone[6] = c_bone[6] * scale_vec
            c_bone[7] = c_bone[7] * scale_vec
            c_bone[8] = c_bone[8] * scale_vec
            c_bone[9] = c_bone[9] * scale_vec
            c_bone[10] = c_bone[10] * scale_vec
            c_bone[11] = c_bone[11] * scale_vec

            rows = [
                [c_bone[3], c_bone[4],  c_bone[5],  c_bone[0]],
                [c_bone[6], c_bone[7],  c_bone[8],  c_bone[1]],
                [c_bone[9], c_bone[10], c_bone[11], c_bone[2]],
                [0.0, 0.0, 0.0, 1.0]
                ]
            vanilla_mat = mathutils.Matrix(rows)
            mat = vanilla_mat @ normalizing_mats[bone_index]

            if frame_index == 0:
                bone_matrices.append(vanilla_mat.copy())
                
                bpy.ops.object.mode_set(mode='EDIT')
                bone = armature.edit_bones.get("BONE_{}".format(bone_index))
                if not bone:
                    bone = armature.edit_bones.new("BONE_{}".format(bone_index))
                bone.head = mat @ mathutils.Vector((0.0, 0.0, 0.0))
                bone.tail = mat @ mathutils.Vector((0.0, 5.0, 0.0))
                bone.align_roll(mathutils.Vector(mat.col[2][0:3]))
                bone.parent = armature.edit_bones.get("BONE_{}".format(header.numBones-1))

            bpy.ops.object.mode_set(mode='POSE', toggle=False)
            obj = armature_obj.pose.bones.get("BONE_{}".format(bone_index))
            
            obj.matrix = mat
            
            obj.scale = [1, 1, 1]
            obj.keyframe_insert("location", frame=frame_index+1)
            obj.keyframe_insert("rotation_quaternion", frame=frame_index+1)
            
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    offset = header.ofsLODs
    for lod_index in range(header.numLODs):
        lod = MDR_LOD.from_buffer_copy(byte_array, offset)
        
        bpy.ops.object.empty_add(type="ARROWS")
        lod_obj = bpy.context.object
        lod_obj.name = "LOD_{}".format(lod_index)
        lod_obj.parent = armature_obj
        
        surf_ofs = offset + lod.ofsSurfaces
        for surf_index in range(lod.numSurfaces):
            surface = MDR_SURFACE.from_buffer_copy(byte_array, surf_ofs)
            
            surface_name = surface.name.decode()
            if lod_index > 0:
                surface_name = "{}_{}".format(surface_name, lod_index)
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
            
            #surface_bones = []
            #bone_offset = surf_ofs+ surface.ofsBoneReferences
            #for bone_id in range(surface.numBoneReferences):
            #    surface_bones.append(MDR_BONE_REF.from_buffer_copy(byte_array, bone_offset).boneIndex)
            #    bone_offset += sizeof(MDR_BONE_REF)
            
            vert_offset = surf_ofs + surface.ofsVerts
            for vertex_id in range(surface.numVerts):
                vertex = MDR_VERT.from_buffer_copy(byte_array, vert_offset)
                vert_offset += sizeof(MDR_VERT)
                vertex_tc.append(vertex.texCoords)
                position = mathutils.Vector([0.0, 0.0, 0.0])
                transform_mat = mathutils.Matrix() * 0
                for weight_id in range(vertex.numWeights):
                    weight = MDR_WEIGHT.from_buffer_copy(byte_array, vert_offset)
                    vert_offset += sizeof(MDR_WEIGHT)
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
                triangle = MDR_TRIANGLE.from_buffer_copy(byte_array, index_offset).indices
                triangle[0], triangle[1] = triangle[1], triangle[0]
                index_offset += sizeof(MDR_TRIANGLE)
                face_indices.append(list(triangle))
                for i in triangle:
                    face_tcs.append(vertex_tc[i][0])
                    face_tcs.append(1.0 - vertex_tc[i][1])
                face_material_index.append(0)
            
            surf_ofs += surface.ofsEnd
            
            mesh = bpy.data.meshes.new(surface_name)
            mesh.from_pydata(vertex_pos, [], face_indices)
            
            shader_name = surface.shader.decode()
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

            objects.append(obj)
            
            obj.parent = lod_obj
            
            for bone in bone_map:
                vg = obj.vertex_groups.get("BONE_{}".format(bone))
                if vg is None:
                    vg = obj.vertex_groups.new(name="BONE_{}".format(bone))
                for vert, weight in bone_map[bone]:
                    vg.add([vert], weight, 'ADD')
            armatureModifier = obj.modifiers.new("armature", 'ARMATURE')
            armatureModifier.object = armature_obj
            armatureModifier.use_bone_envelopes = False
            
        offset += lod.ofsEnd

    offset = header.ofsTags
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')
    for tag_index in range(header.numTags):
        tag = MDR_TAG.from_buffer_copy(byte_array, offset)
        offset += sizeof(MDR_TAG)
        bone = armature.edit_bones.get("BONE_{}".format(tag.boneIndex))
        if not bone:
            print("Bone already renamed, this is bad. Addon assumes tags only beeing one bone.")
            continue
        bone.name = tag.name.decode()

    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    return objects
