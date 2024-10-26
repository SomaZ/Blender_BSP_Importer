import bpy
from ctypes import (LittleEndianStructure,
                    c_char, c_float, c_int, c_ushort, sizeof)
import mathutils
from .BlenderSurfaceFactory import Surface_factory
from .idtech3lib.Parsing import guess_model_name
from .idtech3lib.Helpers import normalize
from numpy import dot, sqrt

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

    @classmethod
    def bytes_from_objects(cls, objects, bones, correction_mats, rotate_y_minus):
        frame = cls()
        frame.min_bounds[:] = [512, 512, 512]
        frame.max_bounds[:] = [-512, -512, -512]
        for obj in objects:
            mesh = obj.data.copy()
            mesh.transform(obj.matrix_world)
            for vert in mesh.vertices:
                frame.min_bounds[:] = [min(frame.min_bounds[0], vert.co[0]),
                                    min(frame.min_bounds[1], vert.co[1]),
                                    min(frame.min_bounds[2], vert.co[2])]
                frame.max_bounds[:] = [max(frame.max_bounds[0], vert.co[0]),
                                    max(frame.max_bounds[1], vert.co[1]),
                                    max(frame.max_bounds[2], vert.co[2])]
        x = frame.min_bounds[0] + \
            (frame.max_bounds[0] - frame.min_bounds[0]) / 2
        y = frame.min_bounds[1] + \
            (frame.max_bounds[1] - frame.min_bounds[1]) / 2
        z = frame.min_bounds[2] + \
            (frame.max_bounds[2] - frame.min_bounds[2]) / 2
        frame.local_origin = x, y, z
        r1 = frame.max_bounds[0] - x
        r2 = frame.max_bounds[1] - y
        r3 = frame.max_bounds[2] - z
        frame.radius = sqrt(r1*r1 + r2*r2 + r3*r3)

        frame_bytes = bytearray()
        frame_bytes += bytes(frame)
        for i, bone in enumerate(bones):
            if rotate_y_minus:
                matrix = inverse_rot_mat @ bone.matrix
            else:
                matrix = bone.matrix
            matrix = matrix @ correction_mats[i].inverted()
            frame_bytes += MDR_COMPRESSED_BONE.bytes_from_matrix(matrix)

        return frame_bytes

class MDR_COMPRESSED_BONE(LittleEndianStructure):
    _fields_ = [
        ("values", c_ushort*12)
    ]

    @classmethod
    def bytes_from_matrix(cls, matrix):
        new_bone = cls()
        new_bone.values[0] = int((matrix[0][3] / scale_pos) + 32767)
        new_bone.values[1] = int((matrix[1][3] / scale_pos) + 32767)
        new_bone.values[2] = int((matrix[2][3] / scale_pos) + 32767)

        new_bone.values[3] = int((matrix[0][0] / scale_vec) + 32767)
        new_bone.values[4] = int((matrix[0][1] / scale_vec) + 32767)
        new_bone.values[5] = int((matrix[0][2] / scale_vec) + 32767)
        new_bone.values[6] = int((matrix[1][0] / scale_vec) + 32767)
        new_bone.values[7] = int((matrix[1][1] / scale_vec) + 32767)
        new_bone.values[8] = int((matrix[1][2] / scale_vec) + 32767)
        new_bone.values[9] = int((matrix[2][0] / scale_vec) + 32767)
        new_bone.values[10] = int((matrix[2][1] / scale_vec) + 32767)
        new_bone.values[11] = int((matrix[2][2] / scale_vec) + 32767)

        return bytes(new_bone)

class MDR_LOD(LittleEndianStructure):
    _fields_ = [
        ("numSurfaces", c_int),
        ("ofsSurfaces", c_int),
        ("ofsEnd", c_int),
    ]

    @classmethod
    def bytes_from_surface_factory(cls, sf, bone_group_mapping, object_lod_name_mapping):
        surfaces_bytes = bytearray()
        for i, sd in enumerate(sf.surface_descriptors):
            new_surface = MDR_SURFACE.bytes_from_surface_descriptor(i, sd, sf.objects, bone_group_mapping)
            surfaces_bytes += bytes(new_surface)
        new_lod = MDR_LOD()
        new_lod.ofsSurfaces = sizeof(MDR_LOD)
        new_lod.numSurfaces = sf.num_surfaces
        new_lod.ofsEnd = sizeof(MDR_LOD) + len(surfaces_bytes)
        lod_bytes = bytearray()
        lod_bytes += bytes(new_lod)
        lod_bytes += surfaces_bytes

        return lod_bytes

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

    @classmethod
    def bytes_from_surface_descriptor(cls, ident, sd, objects, bone_group_mapping):
        new_surface = cls()
        new_surface.ident = ident
        new_surface.name = sd.obj_name.encode() # FIX ME: corrected name from object lod mapping
        new_surface.shader = sd.material.encode()
        new_surface.ofsHeader = -0 # FIX ME

        new_surface.ofsBoneReferences = sizeof(cls)
        new_surface.numBoneReferences = 0 # Weird thing, 1 seems to be written non the less in old files

        new_surface.numTriangles = len(sd.triangles)
        new_surface.ofsTriangles = new_surface.ofsBoneReferences + sizeof(MDR_BONE_REF)

        new_surface.numVerts = sd.current_index
        new_surface.ofsVerts = new_surface.ofsTriangles + new_surface.numTriangles * sizeof(MDR_TRIANGLE) 
        
        reference_bytes = bytearray()
        reference_bytes += bytes(MDR_BONE_REF())

        triangle_bytes = bytearray()
        for triangle in sd.triangles:
            triangle_bytes += MDR_TRIANGLE.bytes_from_triangle(triangle)

        vertices_bytes = bytearray()
        for map in sd.vertex_mapping:

            vertices_bytes += MDR_VERT.bytes_from_vertex_map(map, objects, bone_group_mapping)

        new_surface.ofsEnd = new_surface.ofsVerts + len(vertices_bytes)

        surface_bytes = bytearray()
        surface_bytes += bytes(new_surface)
        surface_bytes += reference_bytes
        surface_bytes += triangle_bytes
        surface_bytes += vertices_bytes
        return surface_bytes

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

    @classmethod
    def bytes_from_vertex_map(cls, vertex_map, objects, bone_group_mapping):
        byte_array = bytearray()
        new_vert = cls()
        mesh = vertex_map.mesh
        b_vert = mesh.vertices[vertex_map.vert]
        b_loop = mesh.uv_layers.active.data[vertex_map.loop]

        new_vert.texCoords[0] = b_loop.uv[0]
        new_vert.texCoords[1] = 1.0 - b_loop.uv[1]
        normal = mathutils.Vector()

        new_weights = []
        full_weight = 0
        for group in b_vert.groups:
            name = objects[vertex_map.obj_id].vertex_groups[group.group].name
            if name not in bone_group_mapping:
                print("Skipping group eval because apparently not a bone weight:", name)
                continue
            if group.weight <= 0.0:
                continue
            index, bone = bone_group_mapping[name]
            inverse_bone_matrix = bone.matrix.inverted()
            new_weights.append(MDR_WEIGHT.from_data(index, group.weight, inverse_bone_matrix, b_vert.co))
            full_weight += group.weight
            normal += group.weight * (bone.matrix @ mesh.loops[vertex_map.loop].normal)
        new_vert.normal[:] = normalize(normal)
        new_vert.numWeights = len(new_weights)

        byte_array += bytes(new_vert)
        for weight in new_weights:
            weight.boneWeight /= full_weight
            byte_array += bytes(weight)

        return byte_array

class MDR_WEIGHT(LittleEndianStructure):
    _fields_ = [
        ("boneIndex", c_int),
        ("boneWeight", c_float),
        ("offset", c_float*3),
    ]

    @classmethod
    def from_data(cls, index, weight, inverse_bone_matrix, position):
        new_weight = cls()
        new_weight.boneIndex = index
        new_weight.boneWeight = weight
        new_weight.offset[:] = inverse_bone_matrix @ position
        return new_weight
    
class MDR_TRIANGLE(LittleEndianStructure):
    _fields_ = [
        ("indices", c_int*3),
    ]

    @classmethod
    def bytes_from_triangle(cls, triangle):
        new_triangle = cls()
        triangle[0], triangle[1] = triangle[1], triangle[0]
        for i in range(3):
            new_triangle.indices[i] = triangle[i]
        return bytes(new_triangle)

class MDR_TAG(LittleEndianStructure):
    _fields_ = [
        ("boneIndex", c_int),
        ("name", c_char*32),
    ]

    @classmethod
    def bytes_from_data(cls, index, name):
        new_tag = cls()
        new_tag.boneIndex = index
        new_tag.name = name.encode()
        return bytes(new_tag)

scale_vec = 1.0 / 32767.0
scale_pos = 1.0 / 64.0
# x+ to y- rotation matrix
rotation_mat = mathutils.Matrix((
                [0.0, 1.0,  0.0,  0.0],
                [-1.0, 0.0,  0.0,  0.0],
                [0.0, 0.0,  1.0,  0.0],
                [0.0, 0.0,  0.0,  1.0]
                ))
inverse_rot_mat = rotation_mat.inverted()

def get_correction_mats(header, byte_array):
    normalizing_mats = [mathutils.Matrix() for i in range(header.numBones)]
    normalizing_weights = [0.0 for i in range(header.numBones)]

    if header.numLODs == 0:
        return normalizing_mats
    
    offset = header.ofsLODs
    lod = MDR_LOD.from_buffer_copy(byte_array, offset)
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
              rotate_y_minus=True,
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
                fcs = armature_obj.driver_add('location')
                for i, fc in enumerate(fcs):
                    driver = fc.driver
                    v = fc.driver.variables.new()
                    v.type = "TRANSFORMS"
                    tar0 = v.targets[0]
                    tar0.id = lower_obj
                    tar0.bone_target = "tag_torso"
                    tar0.transform_type = ('LOC_X', 'LOC_Y', 'LOC_Z')[i]
                    driver.expression = v.name

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
            if rotate_y_minus:
                vanilla_mat = rotation_mat @ vanilla_mat
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
                normal = mathutils.Vector([0.0, 0.0, 0.0])
                for weight_id in range(vertex.numWeights):
                    weight = MDR_WEIGHT.from_buffer_copy(byte_array, vert_offset)
                    vert_offset += sizeof(MDR_WEIGHT)
                    position += weight.boneWeight * (bone_matrices[weight.boneIndex] @ mathutils.Vector(weight.offset))
                    normal[0] += weight.boneWeight * dot(bone_matrices[weight.boneIndex][0][0:3], vertex.normal)
                    normal[1] += weight.boneWeight * dot(bone_matrices[weight.boneIndex][1][0:3], vertex.normal)
                    normal[2] += weight.boneWeight * dot(bone_matrices[weight.boneIndex][2][0:3], vertex.normal)
                    if weight.boneIndex in bone_map:
                        bone_map[weight.boneIndex].append((vertex_id, weight.boneWeight))
                    else:
                        bone_map[weight.boneIndex] = [(vertex_id, weight.boneWeight)]
                vertex_pos.append(position)
                vertex_nor.append(normalize(normal))
            
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


def ExportMDR(file_path,
              armature_obj,
              rotate_y_minus):
    return_status = [False, "Unknown Error"]
    bpy.context.scene.frame_set(bpy.context.scene.frame_start)
    num_frames = bpy.context.scene.frame_end - bpy.context.scene.frame_start + 1
    depsgraph = bpy.context.evaluated_depsgraph_get()

    lods = [e for e in armature_obj.children 
            if e.type == "EMPTY" and e.name.startswith("LOD_")]
    valid_lods = []
    for i, lod in enumerate(sorted(lods, key=lambda lod: lod.name)):
        if lod.name[len("LOD_"):] != str(i):
            if i == 0:
                return_status = [False, "Could not find root LOD: LOD_0"]
                return return_status
            print("Missing LOD:", i)
            break
        valid_lods.append(lod)

    # Find tags and write bone_group_mapping
    bone_group_mapping = {} # Group name -> (bone index, edit bone)
    tags_data = bytearray()
    num_tags = 0
    num_bones = len(armature_obj.data.bones)
    for i, bone in enumerate(armature_obj.data.bones):
        bone_group_mapping[bone.name] = (i, bone)
        if bone.name.startswith("tag_"):
            tags_data += MDR_TAG.bytes_from_data(i, bone.name)
            num_tags += 1

    num_lods = len(valid_lods)
    lods_data = bytearray()
    for lod in valid_lods:
        eval_objects = [obj.evaluated_get(depsgraph) for obj in lod.children if obj.type == "MESH"]
        sf = Surface_factory(
            eval_objects,
            False,
            True,
            1000, # maybe 500 for shadows?
            32)
        lods_data += MDR_LOD.bytes_from_surface_factory(sf, bone_group_mapping, {})

    dummy_header = MDR_HEADER()
    dummy_header.numLODs = 1
    dummy_header.numBones = num_bones
    correction_mats = get_correction_mats(dummy_header, lods_data)

    frames_data = bytearray()
    for frame in range(1, num_frames+1):
        bpy.context.scene.frame_set(frame)
        depsgraph.update()
        eval_objects = [
            obj.evaluated_get(depsgraph) for obj in lod.children if obj.type == "MESH"]

        frames_data += MDR_COMPRESSED_FRAME.bytes_from_objects(
            eval_objects, armature_obj.pose.bones, correction_mats, rotate_y_minus)


    header = MDR_HEADER()
    header.magic_nr = b'RDM5'
    header.version_nr = 2
    header.name = file_path.rsplit("/", 1)[1].encode() + b'\0'
    header.numFrames = num_frames
    header.numBones = num_bones
    header.numLODs = num_lods
    header.numTags = num_tags

    header.ofsTags = sizeof(MDR_HEADER)
    header.ofsFrames = -(header.ofsTags + header.numTags * sizeof(MDR_TAG))
    header.ofsLODs = (-header.ofsFrames +
                      header.numFrames * (
                          sizeof(MDR_COMPRESSED_FRAME) + 
                            header.numBones * sizeof(MDR_COMPRESSED_BONE)))
    header.ofsEnd = header.ofsLODs + len(lods_data)

    byte_array = bytearray()
    byte_array += bytes(header)
    byte_array += tags_data
    byte_array += frames_data
    byte_array += lods_data
    
    opened_file = open(file_path, "wb")
    try:
        opened_file.write(byte_array)
    except Exception:
        return_status[1] = "Couldn't write file"
        return return_status
    opened_file.close()

    return (True, "Everything is fine")
