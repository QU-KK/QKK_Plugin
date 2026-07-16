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

# Copyright 2023, Valeriy Yatsenko


import bpy

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps

from .unwrap_processor import (
    ZuvUnwrapTemplate,
    UnwrapProcessorProps,
    UnwrapProcessor
)


class ZUV_OT_UnwrapForTool(bpy.types.Operator, ZuvUnwrapTemplate):

    bl_idname = "uv.zenuv_unwrap_for_tool"
    bl_label = 'UWRP Processor'
    bl_description = 'UWRP Processor'
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: TransformSysOpsProps.influence_scene_mode

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "influence_mode")

        # self.draw_uwrp_processor_props(layout)

        self.draw_bl_uwrp_props(layout)

    def execute(self, context):
        UP = UnwrapProcessor(context, self.delegate_properties(UnwrapProcessorProps))
        UP.preset_unwrap_in_place(context)
        return {'FINISHED'}


classes = (
    ZUV_OT_UnwrapForTool,
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
