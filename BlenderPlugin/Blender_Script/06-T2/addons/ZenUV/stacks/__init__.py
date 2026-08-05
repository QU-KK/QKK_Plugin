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

import bpy
from bpy.props import IntProperty

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.stacks.copy_paste import (
    ZUV_OT_UV_Copy_Param,
    ZUV_OT_UV_Paste_Param,
    ZUV_OT_Copy_UV,
    ZUV_OT_Paste_UV
)

from ZenUV.stacks.stacks import (
    ZUV_OT_Stack_Similar,
    ZUV_OT_Unstack,
    ZUV_OT_Select_Similar,
    ZUV_OT_Select_Stacked,
    ZUV_OT_Select_Stack
)
from ZenUV.stacks.stacks_ui import ZUV_PT_UVL_DisplayAndSelect, ZUV_PT_3DV_DisplayAndSelect
from ZenUV.stacks.utils import ZMS_OT_ShowSimIndex

from ZenUV.stacks.manual_stacks import (
    ZMSListGroup,
    ZMS_UL_List,
    ZMS_OT_SelectStack,
    ZMS_OT_AssignToStack,
    ZMS_OT_DeleteItem,
    # ZMS_OT_MoveItem,
    ZMS_OT_RemoveAllMstacks,
    ZMS_OT_AnalyzeStack,
    ZMS_OT_NewItem,
    # ZMS_OT_CollectActiveStack,
    # ZMS_OT_ShowSimIndex,
    ZMS_OT_CollectManualStacks,
    ZMS_OT_Unstack_Manual_Stack,

    ZUV_PT_UVL_ZenManualStack,
    ZUV_PT_ZenManualStack
)

stack_classes = (
    ZUV_OT_Stack_Similar,
    ZUV_OT_Unstack,
    ZUV_OT_Select_Similar,
    ZUV_OT_UV_Copy_Param,
    ZUV_OT_UV_Paste_Param,
    ZUV_OT_Copy_UV,
    ZUV_OT_Paste_UV,
    ZMSListGroup,
    ZMS_UL_List,
    ZMS_OT_SelectStack,
    ZMS_OT_AssignToStack,
    ZMS_OT_AnalyzeStack,
    ZMS_OT_DeleteItem,
    ZMS_OT_RemoveAllMstacks,
    # ZMS_OT_MoveItem,
    ZMS_OT_NewItem,
    # ZMS_OT_CollectActiveStack,
    ZMS_OT_CollectManualStacks,
    ZMS_OT_Unstack_Manual_Stack,
    ZUV_OT_Select_Stacked,
    ZUV_OT_Select_Stack
)
# stack_panels = (
#     ZUV_PT_Stack,
#     STACK_PT_Properties,
#     ZUV_PT_ZenManualStack
# )

system_classes = (
    ZMS_OT_ShowSimIndex,
)

m_stacks_parented_panels = [
    ZUV_PT_UVL_DisplayAndSelect,
    ZUV_PT_3DV_DisplayAndSelect,

    ZUV_PT_UVL_ZenManualStack,
    ZUV_PT_ZenManualStack
]


def register():
    """Registering Operators"""

    RegisterUtils.register(stack_classes)

    bpy.types.Object.zen_stack_list = bpy.props.CollectionProperty(type=ZMSListGroup)
    bpy.types.Object.zms_list_index = IntProperty(name="Zen UV Stack", default=0)

    RegisterUtils.register(system_classes)


def unregister():
    """Unegistering Operators"""

    # del bpy.types.Scene.zms_list_index
    del bpy.types.Object.zen_stack_list

    RegisterUtils.unregister(stack_classes + system_classes)


if __name__ == "__main__":
    pass
