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

# Copyright 2023, Alex Zhornyak, Valeriy Yatsenko

import bpy

import gpu
from gpu_extras.batch import batch_for_shader

from mathutils import Vector
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.blender_zen_utils import ZenPolls


if not bpy.app.background:
    if ZenPolls.version_since_3_2_0:
        vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
        vert_out.smooth('VEC2', "texCoord_interp")

        shader_info = gpu.types.GPUShaderCreateInfo()
        shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
        shader_info.push_constant('VEC4', "color")
        shader_info.sampler(0, 'FLOAT_2D', "image")
        shader_info.vertex_in(0, 'VEC3', "pos")
        shader_info.vertex_in(1, 'VEC2', "texCoord")
        shader_info.vertex_out(vert_out)
        shader_info.fragment_out(0, 'VEC4', "fragColor")

        shader_info.vertex_source(
            """
            void main()
            {
                gl_Position = ModelViewProjectionMatrix * vec4(pos.xyz, 1.0f);
                texCoord_interp = texCoord;
            }
            """
        )

        shader_info.fragment_source(
            """
            void main()
            {
                fragColor = texture(image, texCoord_interp) * color;
            }
            """
        )

        shader_texture = gpu.shader.create_from_info(shader_info)
        del vert_out
        del shader_info
    else:
        vertex_shader = '''

            uniform mat4 ModelViewProjectionMatrix;

            in vec3 pos;
            in vec2 texCoord;
            out vec2 texCoord_interp;

            void main()
            {
                gl_Position = ModelViewProjectionMatrix * vec4(pos.xyz, 1.0f);
                texCoord_interp = texCoord;
            }

        '''

        fragment_shader = '''
            in vec2 texCoord_interp;
            out vec4 fragColor;

            uniform sampler2D image;
            uniform vec4 color;

            void main()
            {
                fragColor = texture(image, texCoord_interp) * color;
            }

        '''
        shader_texture = gpu.types.GPUShader(vertex_shader, fragment_shader)


class ZuvTextureGizmo(bpy.types.Gizmo):
    bl_idname = "VIEW3D_GT_zenuv_texture"
    bl_target_properties = (
        {
            "id": "offset",
            "type": 'FLOAT',
            "array_length": 1
        },
    )

    __slots__ = (
        "custom_shape",
        "shader",
        "batch",
        "dimensions"
    )

    def do_draw(self, context: bpy.types.Context):
        if hasattr(self, 'custom_shape') and self.custom_shape:
            p_mtx = self.matrix_world
            gpu.state.blend_set('ALPHA')

            self.shader.bind()

            self.shader.uniform_sampler("image", self.custom_shape)
            color = (*self.color, self.alpha)
            self.shader.uniform_float('color', color)

            with gpu.matrix.push_pop():
                gpu.matrix.multiply_matrix(p_mtx)

                self.batch.draw(self.shader)

            gpu.state.blend_set('NONE')

    def draw(self, context):
        self.do_draw(context)

    def draw_select(self, context, select_id):
        self.do_draw(context)

    def setup(self):
        if hasattr(self, 'dimensions'):
            self.custom_shape = None
            p_image = ZuvTrimsheetUtils.getActiveImage(bpy.context)
            if p_image:

                self.shader = shader_texture
                v_co = (
                    (-0.5, -0.5, -0.5), (-0.5, 0.5, 0.5), (0.5, 0.5, 0.5),
                    (0.5, 0.5, 0.5), (0.5, -0.5, -0.5), (-0.5, -0.5, -0.5)
                )

                v_co = [Vector(co) * Vector(self.dimensions) for co in v_co]

                self.batch = batch_for_shader(
                    self.shader, 'TRIS',
                    {
                        "pos": v_co,
                        "texCoord": ((0, 0), (0, 1), (1, 1), (1, 1), (1, 0), (0, 0)),
                    },
                )
                self.custom_shape = gpu.texture.from_image(p_image)
                self.use_select_background = False

    def exit(self, context, cancel):
        context.area.header_text_set(None)
