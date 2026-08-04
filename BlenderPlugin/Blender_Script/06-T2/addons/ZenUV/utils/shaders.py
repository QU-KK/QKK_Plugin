# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2023-2025, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy
import gpu
import ctypes

from .blender_zen_utils import ZenPolls


def get_dashed_shader_line():
    shader_line = None

    # NOTE: usage shaders in background mode causes an error !!!
    if not bpy.app.background:
        if ZenPolls.version_since_3_2_0:
            vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
            vert_out.smooth('FLOAT', "v_ArcLength")

            shader_info = gpu.types.GPUShaderCreateInfo()
            shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
            shader_info.push_constant('FLOAT', "u_Scale")
            shader_info.push_constant('VEC4', "color")
            shader_info.vertex_in(0, 'VEC2', "pos")
            shader_info.vertex_in(1, 'FLOAT', "arcLength")
            shader_info.vertex_out(vert_out)
            shader_info.fragment_out(0, 'VEC4', "fragColor")

            shader_info.vertex_source(
                "void main()"
                "{"
                "  v_ArcLength = arcLength;"
                "  gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0f, 1.0f);"
                "}"
            )

            shader_info.fragment_source(
                "void main()"
                "{"
                "  if (step(sin(v_ArcLength * u_Scale), 0.5) == 1) { fragColor = color; }"
                "  else"
                "  discard;"
                "}"
            )

            shader_line = gpu.shader.create_from_info(shader_info)
            del vert_out
            del shader_info
        else:
            shader_line = gpu.shader.from_builtin('2D_UNIFORM_COLOR')

    return shader_line


class Dash_UBO_struct(ctypes.Structure):
    _pack_ = 16
    _fields_ = [
        ("dash_width", ctypes.c_float),
        ("udash_factor", ctypes.c_float),
        ("colors_len", ctypes.c_int),
    ]


def get_dashed_shader_line_2():
    shader_line = None

    """
    w, h = gpu.state.viewport_get()[2:]
    gpu.state.line_width_set(1.0)
    shader.uniform_float("viewport_size", (w, h))

    UBO_data = Dash_UBO_struct()
    UBO_data.colors_len = 1
    UBO_data.dash_width = 10.0
    UBO_data.udash_factor = 0.5

    UBO = gpu.types.GPUUniformBuf(
        gpu.types.Buffer("UINT", ctypes.sizeof(UBO_data), UBO_data)
    )

    shader.uniform_block("g_data", UBO)
    shader.uniform_float("color", (*ZUV_GGT_UVTransformGizmo.INACTIVE_COLOR[:], 0.5))
    shader.uniform_float("color2", (0, 0, 0, 0.5))
    """

    # NOTE: usage shaders in background mode causes an error !!!
    if not bpy.app.background:
        if ZenPolls.version_since_3_2_0:
            # NOTE: https://blender.stackexchange.com/questions/327274/how-to-draw-consistent-dotted-line-similar-to-default-blender-measure-tool

            # https://github.com/blender/blender/blob/blender-v4.3-release/source/blender/gpu/shaders/infos/gpu_shader_line_dashed_uniform_color_info.hh
            vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
            vert_out.no_perspective("VEC2", "stipple_start")
            vert_out.flat("VEC2", "stipple_pos")

            shader_info = gpu.types.GPUShaderCreateInfo()

            shader_info.typedef_source(
                "struct Data {\n"
                "  float dash_width;\n"
                "  float udash_factor;\n"
                "  int colors_len;\n"
                "};\n"
            )

            shader_info.vertex_in(0, "VEC2", "pos")

            shader_info.push_constant("MAT4", "ModelViewProjectionMatrix")
            shader_info.push_constant("VEC2", "viewport_size")

            shader_info.uniform_buf(0, "Data", "g_data")

            shader_info.push_constant("VEC4", "color")
            shader_info.push_constant("VEC4", "color2")
            shader_info.vertex_out(vert_out)
            shader_info.fragment_out(0, "VEC4", "fragColor")

            # https://github.com/blender/blender/blob/blender-v4.3-release/source/blender/gpu/shaders/gpu_shader_3D_line_dashed_uniform_color_vert.glsl
            shader_info.vertex_source("""
            void main()
            {
                vec4 pos_4d = vec4(pos, 1.0, 1.0);
                gl_Position = ModelViewProjectionMatrix * pos_4d;
                stipple_start = stipple_pos = viewport_size * 0.5 * (gl_Position.xy / gl_Position.w);
            }
            """)

            # https://github.com/blender/blender/blob/blender-v4.3-release/source/blender/gpu/shaders/gpu_shader_2D_line_dashed_frag.glsl
            shader_info.fragment_source("""
            void main()
            {
                float distance_along_line = distance(stipple_pos, stipple_start);
                /* Solid line case, simple. */
                if (g_data.udash_factor >= 1.0f) {
                    fragColor = color;
                }
                /* Actually dashed line... */
                else {
                    float normalized_distance = fract(distance_along_line / g_data.dash_width);
                    if (normalized_distance <= g_data.udash_factor) {
                    fragColor = color;
                    }
                    else if (g_data.colors_len > 0) {
                    fragColor = color2;
                    }
                    else {
                    discard;
                    }
                }
            }
            """)

            shader_line = gpu.shader.create_from_info(shader_info)
            del vert_out
            del shader_info
        else:
            shader_line = gpu.shader.from_builtin('2D_UNIFORM_COLOR')

    return shader_line
