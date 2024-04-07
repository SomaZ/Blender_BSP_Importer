import bpy
from . import BlenderImage, QuakeLight

import math
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector

vertex_header = '''
    in int vertex_id;
    out vec2 tc;
'''

vertex_shader = '''
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

fragment_header = '''
    uniform sampler2D tex_up;
    uniform sampler2D tex_dn;
    uniform sampler2D tex_ft;
    uniform sampler2D tex_bk;
    uniform sampler2D tex_lf;
    uniform sampler2D tex_rt;
    uniform float clamp_value;

    in vec2 tc;
    out vec4 FragColor;
'''

fragment_shader = '''
    #define PI 3.14159265358979323846
    #define UP 0
    #define DN 1
    #define FT 2
    #define BK 3
    #define LF 4
    #define RT 5

    void main()
    {
        vec3 pi_hpi_z = vec3(PI, PI / 2.0, 0.0);
        vec2 thetaphi = ((tc * 2.0) - vec2(1.0)) * pi_hpi_z.xy - pi_hpi_z.yz;
        vec3 rayDirection = vec3(
            cos(thetaphi.y) * cos(thetaphi.x),
            sin(thetaphi.y),
            cos(thetaphi.y) * sin(thetaphi.x));
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
        else if (absDirection.x > absDirection.y &&
                 absDirection.x > absDirection.z)
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

        FragColor = color;
    }
'''

if bpy.app.version < (3, 5, 0):
    shader = gpu.types.GPUShader(
        vertex_header+vertex_shader,
        fragment_header+fragment_shader)
else:
    shader_sky_info = gpu.types.GPUShaderCreateInfo()
    shader_sky_info.vertex_in(0, 'INT', "vertex_id")
    shader_sky_info.sampler(0, 'FLOAT_2D', "tex_up")
    shader_sky_info.sampler(1, 'FLOAT_2D', "tex_dn")
    shader_sky_info.sampler(2, 'FLOAT_2D', "tex_ft")
    shader_sky_info.sampler(3, 'FLOAT_2D', "tex_bk")
    shader_sky_info.sampler(4, 'FLOAT_2D', "tex_lf")
    shader_sky_info.sampler(5, 'FLOAT_2D', "tex_rt")
    shader_sky_info.push_constant('FLOAT', "clamp_value")

    shader_sky_interface = gpu.types.GPUStageInterfaceInfo("shader_sky_interface")    
    shader_sky_interface.smooth('VEC2', "tc")
    shader_sky_info.vertex_out(shader_sky_interface)

    shader_sky_info.fragment_out(0, 'VEC4', 'FragColor')
    shader_sky_info.vertex_source(vertex_shader)
    shader_sky_info.fragment_source(fragment_shader)

    shader = gpu.shader.create_from_info(shader_sky_info)

batch = batch_for_shader(shader, 'TRIS', {"vertex_id": (0, 1, 2)})


def make_equirectangular_from_sky(VFS, sky_name):
    textures = [sky_name + "_up",
                sky_name + "_dn",
                sky_name + "_ft",
                sky_name + "_bk",
                sky_name + "_lf",
                sky_name + "_rt"]
    cube = [None for x in range(6)]

    biggest_h = 1
    biggest_w = 1

    for index, tex in enumerate(textures):
        image = BlenderImage.load_file(tex, VFS)

        if image is not None:
            cube[index] = image
            image.colorspace_settings.name = "Non-Color"
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
        if bpy.app.version < (3, 0, 0):
            import bgl
            bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
        else:
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=(0.0, 0.0, 0.0, 0.0))

        with gpu.matrix.push_pop():
            # reset matrices -> use normalized device coordinates [-1, 1]
            gpu.matrix.load_matrix(Matrix.Identity(4))
            gpu.matrix.load_projection_matrix(Matrix.Identity(4))

            # now draw
            shader.bind()
            if bpy.app.version < (3, 0, 0):
                if cube[0] is not None:
                    bgl.glActiveTexture(bgl.GL_TEXTURE0)
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[0].bindcode)
                if cube[1] is not None:
                    bgl.glActiveTexture(bgl.GL_TEXTURE1)
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[1].bindcode)
                if cube[2] is not None:
                    bgl.glActiveTexture(bgl.GL_TEXTURE2)
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[2].bindcode)
                if cube[3] is not None:
                    bgl.glActiveTexture(bgl.GL_TEXTURE3)
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[3].bindcode)
                if cube[4] is not None:
                    bgl.glActiveTexture(bgl.GL_TEXTURE4)
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[4].bindcode)
                if cube[5] is not None:
                    bgl.glActiveTexture(bgl.GL_TEXTURE5)
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, cube[5].bindcode)
                shader.uniform_int("tex_up", 0)
                shader.uniform_int("tex_dn", 1)
                shader.uniform_int("tex_ft", 2)
                shader.uniform_int("tex_bk", 3)
                shader.uniform_int("tex_lf", 4)
                shader.uniform_int("tex_rt", 5)
            else:
                if cube[0] is not None:
                    shader.uniform_sampler("tex_up", gpu.texture.from_image(cube[0]))
                if cube[1] is not None:
                    shader.uniform_sampler("tex_dn", gpu.texture.from_image(cube[1]))
                if cube[2] is not None:
                    shader.uniform_sampler("tex_ft", gpu.texture.from_image(cube[2]))
                if cube[3] is not None:
                    shader.uniform_sampler("tex_bk", gpu.texture.from_image(cube[3]))
                if cube[4] is not None:
                    shader.uniform_sampler("tex_lf", gpu.texture.from_image(cube[4]))
                if cube[5] is not None:
                    shader.uniform_sampler("tex_rt", gpu.texture.from_image(cube[5]))
            shader.uniform_float("clamp_value", 1.0 / biggest_h)
            batch.draw(shader)

        if bpy.app.version < (3, 0, 0):
            buffer = bgl.Buffer(bgl.GL_FLOAT, equi_w * equi_h * 4)
            bgl.glReadBuffer(bgl.GL_BACK)
            bgl.glReadPixels(0, 0, equi_w, equi_h,
                            bgl.GL_RGBA, bgl.GL_FLOAT, buffer)
        else:
            buffer = fb.read_color(0, 0, equi_w, equi_h, 4, 0, 'FLOAT')

    offscreen.free()

    image = bpy.data.images.get(sky_name)
    if image is None:
        image = bpy.data.images.new(sky_name, width=equi_w, height=equi_h)
    image.scale(equi_w, equi_h)

    if bpy.app.version >= (3, 0, 0):
        buffer.dimensions = equi_w * equi_h * 4
    image.pixels = [v for v in buffer]
    image.pack()

    for side in cube:
        if side is None:
            continue
        side.colorspace_settings.name = "sRGB"

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
    intensity = float(parms[3])
    rotation = [float(parms[4]), float(parms[5])]

    light_vec = [0.0, 0.0, 0.0]
    rotation[0] = rotation[0] / 180.0 * math.pi
    rotation[1] = rotation[1] / 180.0 * math.pi
    light_vec[0] = math.cos(rotation[0]) * math.cos(rotation[1])
    light_vec[1] = math.sin(rotation[0]) * math.cos(rotation[1])
    light_vec[2] = math.sin(rotation[1])
    angle = math.radians(1.5)

    QuakeLight.add_light(name, "SUN", intensity, color, light_vec, angle)

    return True

ets_vertex_header = '''
    in int vertex_id;
    out vec2 tc;
'''
ets_vertex_shader = '''
    void main()
    {
        vec2 position = vec2(2.0 * float(vertex_id & 2) - 1.0, 4.0 * float(vertex_id & 1) - 1.0);
	    gl_Position = vec4(position, 0.0, 1.0);
        tc = gl_Position.xy;
    }
'''

ets_fragment_header = '''
    uniform sampler2D equirect;
    uniform int side;
    in vec2 tc;
    out vec4 FragColor;
'''

ets_fragment_shader = '''
    #define PI 3.14159265358979323846
    void main()
    {
        vec2 vector = tc;
        // from http://www.codinglabs.net/article_physically_based_rendering.aspx

        vec3 rd = normalize(vec3(vector.x, vector.y, -1.0));
        
        if (side == 0)
            rd = normalize(vec3(1.0, vector.y, vector.x));
        else if (side == 1)
            rd = normalize(vec3(-1.0, vector.y, -vector.x));
        else if (side == 2)
            rd = normalize(vec3(-vector.y, 1.0, vector.x));
        else if (side == 3)
            rd = normalize(vec3(vector.y, -1.0, vector.x));
        else if (side == 4)
            rd = normalize(vec3(-vector.x, vector.y, 1.0));

        vec2 tex = vec2(atan(rd.z, rd.x) + PI, acos(-rd.y)) / vec2(2.0 * PI, PI);
        
        FragColor = textureLod(equirect, tex, 0);
    }
'''

if bpy.app.version < (3, 5, 0):
    ets_shader = gpu.types.GPUShader(
        ets_vertex_header+ets_vertex_shader,
        ets_fragment_header+ets_fragment_shader)
else:
    ets_info = gpu.types.GPUShaderCreateInfo()
    ets_info.vertex_in(0, 'INT', "vertex_id")
    ets_info.sampler(0, 'FLOAT_2D', "equirect")
    ets_info.push_constant('INT', "side")

    ets_interface = gpu.types.GPUStageInterfaceInfo("ets_interface")    
    ets_interface.smooth('VEC2', "tc")
    ets_info.vertex_out(ets_interface)

    ets_info.fragment_out(0, 'VEC4', 'FragColor')
    ets_info.vertex_source(ets_vertex_shader)
    ets_info.fragment_source(ets_fragment_shader)

    ets_shader = gpu.shader.create_from_info(ets_info)

ets_batch = batch_for_shader(ets_shader, 'TRIS', {"vertex_id": (0, 1, 2)})

def make_sky_from_equirect(image):
    if image is None:
        return None

    image_colorspace_setting = image.colorspace_settings.name
    image.colorspace_settings.name = "Non-Color"

    image_names = [image.name + "_rt",
                image.name + "_lf",
                image.name + "_up",
                image.name + "_dn",
                image.name + "_ft",
                image.name + "_bk"]
    cube = [None for x in range(6)]

    image_width = int(image.size[0] / 4)
    image_height = int(image.size[1] / 2)

    internal_format = "RGBA32F" if image.is_float else "RGBA8"

    for i in range(len(cube)):
        offscreen = gpu.types.GPUOffScreen(image_width, image_height, format = internal_format)
        with offscreen.bind():
            if bpy.app.version < (3, 0, 0):
                import bgl
                bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
            else:
                fb = gpu.state.active_framebuffer_get()
                fb.clear(color=(0.0, 0.0, 0.0, 0.0))

            with gpu.matrix.push_pop():
                # reset matrices -> use normalized device coordinates [-1, 1]
                gpu.matrix.load_matrix(Matrix.Identity(4))
                gpu.matrix.load_projection_matrix(Matrix.Identity(4))

                # now draw
                ets_shader.bind()
                if bpy.app.version < (3, 0, 0):
                    bgl.glActiveTexture(bgl.GL_TEXTURE0)
                    bgl.glBindTexture(bgl.GL_TEXTURE_2D, image.bindcode)
                    ets_shader.uniform_int("equirect", 0)
                else:
                    ets_shader.uniform_sampler("equirect", gpu.texture.from_image(image))

                ets_shader.uniform_int("side", i)
                ets_batch.draw(ets_shader)

            if bpy.app.version < (3, 0, 0):
                buffer = bgl.Buffer(bgl.GL_FLOAT, image_width * image_height * 4)
                bgl.glReadBuffer(bgl.GL_BACK)
                bgl.glReadPixels(0, 0, image_width, image_height,
                                bgl.GL_RGBA, bgl.GL_FLOAT, buffer)
            else:
                buffer = fb.read_color(0, 0, image_width, image_height, 4, 0, 'FLOAT')

        offscreen.free()

        out_image = bpy.data.images.get(image_names[i])
        if out_image is None:
            out_image = bpy.data.images.new(
                image_names[i],
                width=image_width,
                height=image_height,
                float_buffer=image.is_float)
        out_image.scale(image_width, image_height)

        if bpy.app.version >= (3, 0, 0):
            buffer.dimensions = image_width * image_height * 4
        out_image.pixels = [v for v in buffer]
        cube[i] = out_image

    image.colorspace_settings.name = image_colorspace_setting
    return cube