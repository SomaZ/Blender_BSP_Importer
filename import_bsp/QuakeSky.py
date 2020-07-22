import imp

if "bpy" not in locals():
    import bpy

if "Image" in locals():
    imp.reload( Image )
else:
    from . import Image
    
if "QuakeLight" in locals():
    imp.reload( QuakeLight )
else:
    from . import QuakeLight

import math
import bgl
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

vertex_shader = '''
    in int vertex_id;
    out vec2 tc;

    void main()
    {
        const vec2 positions[] = vec2[3](
            vec2(-1.0f, -1.0f),
            vec2(-1.0f,  3.0f),
            vec2( 3.0f, -1.0f)
        );

        const vec2 texcoords[] = vec2[3](
            vec2( 0.0f,  0.0f),
            vec2( 0.0f,  2.0f),
            vec2( 2.0f,  0.0f)
        );

        gl_Position = vec4(positions[vertex_id], 0.0, 1.0);
        tc = texcoords[vertex_id];
    }
'''

fragment_shader = '''
    uniform sampler2D tex_up;
    uniform sampler2D tex_dn;
    uniform sampler2D tex_ft;
    uniform sampler2D tex_bk;
    uniform sampler2D tex_lf;
    uniform sampler2D tex_rt;
    uniform float clamp_value;
    
    in vec2 tc;
    #define PI 3.14159265358979323846
    #define UP 0
    #define DN 1
    #define FT 2
    #define BK 3
    #define LF 4
    #define RT 5

    void main()
    {
        vec2 thetaphi = ((tc * 2.0) - vec2(1.0)) * vec2(PI, PI / 2.0) - vec2(PI / 2.0, 0.0); 
        vec3 rayDirection = vec3(cos(thetaphi.y) * cos(thetaphi.x), sin(thetaphi.y), cos(thetaphi.y) * sin(thetaphi.x));
        vec3 absDirection = abs(rayDirection);
        int read_texture = 0;
        vec2 read_tc = vec2(0.0);
        
        if (absDirection.y > absDirection.x && absDirection.y > absDirection.z)
        {
            if (absDirection.y > 0.0)
            {
                rayDirection.z /= absDirection.y;
                rayDirection.x /= absDirection.y;
            }
            if (rayDirection.y < 0.0)
            {
                read_texture = DN;
                rayDirection.z = -rayDirection.z;
            }
            read_tc = vec2(rayDirection.x, rayDirection.z) * 0.5 + 0.5;
        }
        else if (absDirection.x > absDirection.y && absDirection.x > absDirection.z)
        {
            if (absDirection.x > 0.0)
            {
                rayDirection.z /= absDirection.x;
                rayDirection.y /= absDirection.x;
            }
            if (rayDirection.x < 0.0)
            {
                read_texture = BK;
                rayDirection.z = -rayDirection.z;
            }
            else
            {
                read_texture = FT;
            }
            read_tc = vec2(rayDirection.z, rayDirection.y) * 0.5 + 0.5;
        }
        else
        {
            if (absDirection.z > 0.0)
            {
                rayDirection.y /= absDirection.z;
                rayDirection.x /= absDirection.z;
            }
            if (rayDirection.z < 0.0)
            {
                read_texture = RT;
            }
            else
            {
                read_texture = LF;
                rayDirection.x = -rayDirection.x;
            }
            read_tc = vec2(rayDirection.x, rayDirection.y) * 0.5 + 0.5;
        }
        
        vec4 color = vec4(0.0);
        read_tc = clamp(read_tc, vec2(clamp_value), vec2(1.0 - clamp_value));
        
        switch (read_texture)
        {
            case UP:
                color = texture(tex_up, read_tc);
                break;
            case DN:
                color = texture(tex_dn, read_tc);
                break;
            case FT:
                color = texture(tex_ft, read_tc);
                break;
            case BK:
                color = texture(tex_bk, read_tc);
                break;
            case LF:
                color = texture(tex_lf, read_tc);
                break;
            case RT:
                color = texture(tex_rt, read_tc);
                break;
            default:
                break;  
        }
        // TODO: Check color space?
        gl_FragColor = color;
    }
'''

shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
batch = batch_for_shader(shader, 'TRIS', {"vertex_id" : (0, 1, 2)})

def make_equirectangular_from_sky(base_path, sky_name):
    textures = [sky_name + "_up", 
                sky_name + "_dn",
                sky_name + "_ft",
                sky_name + "_bk",
                sky_name + "_lf",
                sky_name + "_rt" ]
    cube = [None for x in range(6)]
    
    biggest_h = 1
    biggest_w = 1
                 
    for index,tex in enumerate(textures):
        image = Image.load_file(base_path, tex)
        
        if image != None:
            cube[index] = image
            if image.gl_load():
                raise Exception()
            if biggest_h < image.size[1]:
                biggest_h = image.size[1]
            if biggest_w < image.size[0]:
                biggest_w = image.size[0]

    equi_w = min(8192, biggest_w*4)
    equi_h = min(4096, biggest_h*2)
    
    offscreen = gpu.types.GPUOffScreen(equi_w, equi_h)
    with offscreen.bind():
        bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
        with gpu.matrix.push_pop():
            # reset matrices -> use normalized device coordinates [-1, 1]
            gpu.matrix.load_matrix(Matrix.Identity(4))
            gpu.matrix.load_projection_matrix(Matrix.Identity(4))
            
            if cube[0] != None:
                bgl.glActiveTexture(bgl.GL_TEXTURE0)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[0].bindcode)
            if cube[1] != None:
                bgl.glActiveTexture(bgl.GL_TEXTURE1)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[1].bindcode)
            if cube[2] != None:
                bgl.glActiveTexture(bgl.GL_TEXTURE2)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[2].bindcode)
            if cube[3] != None:
                bgl.glActiveTexture(bgl.GL_TEXTURE3)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[3].bindcode)
            if cube[4] != None:
                bgl.glActiveTexture(bgl.GL_TEXTURE4)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[4].bindcode)
            if cube[5] != None:
                bgl.glActiveTexture(bgl.GL_TEXTURE5)
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[5].bindcode)
            
            #now draw
            shader.bind()
            shader.uniform_int("tex_up", 0)
            shader.uniform_int("tex_dn", 1)
            shader.uniform_int("tex_ft", 2)
            shader.uniform_int("tex_bk", 3)
            shader.uniform_int("tex_lf", 4)
            shader.uniform_int("tex_rt", 5)
            shader.uniform_float("clamp_value", 1.0 / biggest_h)
            batch.draw(shader)
            
        buffer = bgl.Buffer(bgl.GL_FLOAT, equi_w * equi_h * 4)
        bgl.glReadBuffer(bgl.GL_BACK)
        bgl.glReadPixels(0, 0, equi_w, equi_h, bgl.GL_RGBA, bgl.GL_FLOAT, buffer)
        
    offscreen.free()
    
    image = bpy.data.images.get(sky_name)
    if image == None:
        image = bpy.data.images.new(sky_name, width=equi_w, height=equi_h)
    image.scale(equi_w, equi_h)
    image.pixels = buffer
    image.pack()
    return image

def add_sun(shader, function, sun_parms, i):
    
    color = [0.0, 0.0, 0.0]
    intensity = 1.0
    parms = sun_parms.split()
    rotation = [0.0, 0.0]
    name = shader + "_" + function + "." + str(i)
     
    if function == "sun":
        if len(parms) < 6:
            print("not enogh sun parameters")
    elif function == "q3map_sun":
        if len(parms) < 6:
            print("not enogh q3map_sun parameters")
    elif function == "q3map_sunext":
        if len(parms) < 8:
            print("not enogh q3map_sunext parameters")
    elif function == "q3gl2_sun":
        if len(parms) < 9:
            print("not enogh q3gl2_sun parameters")
        
    color = Vector((float(parms[0]), float(parms[1]), float(parms[2])))
    color.normalize()
    intensity = float(parms[3]) / 10.0
    rotation = [float(parms[4]), float(parms[5])]
    
    light_vec = [0.0, 0.0, 0.0]
    rotation[0] = rotation[0] / 180.0 * math.pi
    rotation[1] = rotation[1] / 180.0 * math.pi
    light_vec[0] = -math.cos(rotation[0]) * math.cos(rotation[1])
    light_vec[1] = -math.sin(rotation[0]) * math.cos(rotation[1])
    light_vec[2] = -math.sin(rotation[1])
    angle = math.radians(1.5)
    
    QuakeLight.add_light(name, "SUN", intensity, color, light_vec, angle)
    
    return True