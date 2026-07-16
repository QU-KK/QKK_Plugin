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

""" Zen UV draws functions for panels """

import bpy

import platform

from ZenUV.ui.labels import ZuvLabels
from ZenUV.ico import icon_get

from ZenUV.utils.blender_zen_utils import ZenPolls


def draw_progress_bar(self, context):
    ''' @Draw Progress Bar '''
    if context.scene.zenuv_progress >= 0:
        self.layout.separator()
        text = context.scene.zenuv_progress_text
        self.layout.prop(
            context.scene,
            "zenuv_progress",
            text=text,
            slider=True
            )


def draw_smooth_by_sharp_op(layout):
    from ZenUV.ops.operators import ZUV_OT_SmoothBySharp
    if not ZenPolls.version_since_4_1_0:
        p_op_name = ZUV_OT_SmoothBySharp.bl_label + ' (Toggle)'
    else:
        p_op_name = ZUV_OT_SmoothBySharp.bl_label
    layout.operator(ZUV_OT_SmoothBySharp.bl_idname, text=p_op_name)


def draw_unwrap(self, context: bpy.types.Context):
    ''' @Draw Unwrap '''
    layout: bpy.types.UILayout = self.layout

    # Zen Unwrap Section
    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator(
        "uv.zenuv_unwrap",
        icon_value=icon_get(ZuvLabels.ZEN_UNWRAP_ICO)).action = "DEFAULT"
    row.popover(panel="ZENUNWRAP_PT_Properties", text="", icon="PREFERENCES")
    col.operator("uv.zenuv_unwrap_constraint")
    if platform.system() == 'Windows':
        from ZenUV.ops.auto_uv_unwrap import draw_auto_unwrap
        draw_auto_unwrap(layout, context)
    # layout.operator(ZUV_OT_ProjectByScreenCage.bl_idname)

    # Seams Section
    col = layout.column(align=True)
    row = col.row(align=True)
    row.operator("uv.zenuv_auto_mark")
    row.popover(panel="MARK_PT_Properties", text="", icon="PREFERENCES")
    row = col.row(align=True)
    row.operator(
        "uv.zenuv_mark_seams",
        icon_value=icon_get(ZuvLabels.OT_MARK_ICO),
        text='Mark').action = 'MARK'
    row.operator(
        "uv.zenuv_mark_seams",
        icon_value=icon_get(ZuvLabels.OT_UNMARK_ICO),
        text='Unmark').action = 'UNMARK'
    col.operator("uv.zenuv_unmark_all")

    # Seam By Section

    row = col.row(align=True)
    row.prop(context.scene.zen_uv, "sl_convert", text="")
    row.operator("uv.zenuv_unified_mark", icon='KEYFRAME_HLT', text="")

    layout.operator("mesh.zenuv_mirror_seams")

    draw_smooth_by_sharp_op(layout)


def uv_draw_unwrap(self, context):
    ''' @Draw Unwrap UV '''
    # Zen Unwrap Section
    layout: bpy.types.UILayout = self.layout

    col = layout.column(align=True)

    row = col.row(align=True)
    row.operator(
        "uv.zenuv_unwrap",
        icon_value=icon_get(ZuvLabels.ZEN_UNWRAP_ICO)).action = "DEFAULT"
    row.popover(panel="ZENUNWRAP_PT_Properties", text="", icon="PREFERENCES")

    col.operator("uv.zenuv_unwrap_constraint")
    col.operator('uv.zenuv_unwrap_inplace')

    if platform.system() == 'Windows':
        from ZenUV.ops.auto_uv_unwrap import draw_auto_unwrap
        draw_auto_unwrap(layout, context)

    # layout.operator(ZUV_OT_ProjectByScreenCage.bl_idname)
