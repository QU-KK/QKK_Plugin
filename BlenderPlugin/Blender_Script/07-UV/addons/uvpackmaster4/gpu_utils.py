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

import gpu # type: ignore

GPU_API_COMPATIBILITY = True

GPU_STATE_FUNCTIONS = ["depth_test_set", "line_width_set"]

if "state" not in dir(gpu) or not all(f in dir(gpu.state) for f in GPU_STATE_FUNCTIONS):
    GPU_API_COMPATIBILITY = False

if GPU_API_COMPATIBILITY:
    def gpu_state_depth_test_set(mode):
        gpu.state.depth_test_set(mode)

    def gpu_state_line_width_set(width):
        gpu.state.line_width_set(width)
else:
    import bgl # type: ignore

    DEPTH_TEST_MODES = {
        "NONE": bgl.GL_NEVER,
        "ALWAYS": bgl.GL_ALWAYS,
        "LESS": bgl.GL_LESS,
        "LESS_EQUAL": bgl.GL_LEQUAL,
        "EQUAL": bgl.GL_EQUAL,
        "GREATER": bgl.GL_GREATER,
        "GREATER_EQUAL": bgl.GL_GEQUAL
    }

    def gpu_state_depth_test_set(mode):
        bgl_mode = DEPTH_TEST_MODES[mode]
        if mode == "NONE":
            bgl.glDisable(bgl.GL_DEPTH_TEST)
        else:
            bgl.glEnable(bgl.GL_DEPTH_TEST)
            bgl.glDepthFunc(bgl_mode)

    def gpu_state_line_width_set(width):
        bgl.glLineWidth(width)
