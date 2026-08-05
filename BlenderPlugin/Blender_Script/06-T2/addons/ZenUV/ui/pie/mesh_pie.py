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

""" Zen UV Main Pie Menu """
import bpy
from ZenUV.ui.labels import ZuvLabels
from ZenUV.ui.pie.basic_pie import ZsBasicPieCaller
from ZenUV.utils.blender_zen_utils import get_command_props


class PieOperators:

    s4_left = {
        'Default': 'uv.zenuv_mark_seams(True, action="UNMARK")',
        'CTRL': 'uv.zenuv_untag_finished(True)',
        'ALT': 'uv.zenuv_unmark_all(True)'
    }

    s6_right = {
        'Default': 'uv.zenuv_mark_seams(True, action="MARK")',
        'CTRL': 'uv.zenuv_tag_finished(True)'
    }

    s8_top = {
        'Default': "bpy.ops.uv.zenuv_isolate_island('INVOKE_DEFAULT', True)",
        'CTRL': "bpy.ops.uv.zenuv_isolate_part('INVOKE_DEFAULT', True)",
    }

    s2_bottom = {
        'Default': "bpy.ops.uv.zenuv_unwrap('INVOKE_DEFAULT', True)",
        'ALT': "uv.zenuv_pack(True)",
        'SHIFT': "bpy.ops.uv.zuv_activate_tool(True, mode='ACTIVATE')"
    }

    s7_top_left = {
        'Default': "uv.zenuv_select_island(True)",
        'CTRL': "uv.zenuv_select_flipped(True)",
        'ALT': "uv.zenuv_select_uv_overlap(True)",
        'SHIFT': "uv.zenuv_select_similar(True)"
    }

    s1_bottom_left = {
        'Default': "uv.zenuv_quadrify(True)",
        'CTRL': "uv.zenuv_relax(True)",
        'SHIFT': "uv.zenuv_fit_to_trim_hotspot(True)"
    }

    s3_bottom_right = {
        'Default': "view3d.zenuv_checker_toggle(True, action='TOGGLE')",
        'CTRL': "uv.zenuv_display_finished(True)",
        'ALT': "uv.switch_stretch_map(True)",
    }

    s9_top_right = {
        'Default': "uv.zenuv_auto_mark(True)",
    }


def operator_text(context, input_text):
    """ Detect mode for Pie Menu 4 and 6 sector """
    addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
    if addon_prefs.markSeamEdges:
        input_text += ' Seams'
        if addon_prefs.markSharpEdges:
            input_text += ' /'
    if addon_prefs.markSharpEdges:
        input_text += ' Sharp Edges'
    return input_text


def _get_caller_enum_items(template_items):
    items = []
    for op_id in template_items.values():
        op_props = get_command_props(op_id)
        items.append((op_id, op_props.bl_label, op_props.bl_desc))
    return items


def _get_caller_description(template_items, properties):
    if properties.is_menu:
        for op_id in template_items.values():
            if op_id == properties.cmd_enum:
                op_props = get_command_props(op_id)
                desc = op_id
                if op_props.bl_desc:
                    desc = op_props.bl_desc
                elif op_props.bl_label:
                    desc = op_props.bl_label
                return desc
    else:
        items = []
        for op_key, op_id in template_items.items():
            op_props = get_command_props(op_id)

            desc = op_id
            if op_props.bl_desc:
                desc = op_props.bl_desc
            elif op_props.bl_label:
                desc = op_props.bl_label
            items.append(f'{op_key} - {desc}')
        return '\n'.join(items)
    return ''


# Sector 4 ###########################################################
class ZUV_OT_PieCallerLeft(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_left"
    bl_label = ZuvLabels.OT_UNMARK_LABEL + " | " + ZuvLabels.OT_UNTAG_FINISHED_LABEL
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s4_left

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerLeft.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


# Sector 6 ###########################################################
class ZUV_OT_PieCallerRight(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_right"
    bl_label = ZuvLabels.OT_MARK_LABEL + " | " + ZuvLabels.OT_TAG_FINISHED_LABEL
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s6_right

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerRight.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


# Sector 8 ###########################################################
class ZUV_OT_PieCallerTop(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_top"
    bl_label = "Isolate Island | Part"
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s8_top

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerTop.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


# Sector 2 ###########################################################
class ZUV_OT_PieCallerBottom(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_bottom"
    bl_label = ZuvLabels.ZEN_UNWRAP_LABEL + " | " + "Pack" + " | " + "Edit Mode"
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s2_bottom

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerBottom.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


# Sector 7 ###########################################################
class ZUV_OT_PieCallerTopLeft(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_top_left"
    bl_label = "Select: Island" + " | " + "Overlapped"
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s7_top_left

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerTopLeft.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


# Sector 1 ###########################################################
class ZUV_OT_PieCallerBottomLeft(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_bottom_left"
    bl_label = "Quadrify" + " | " + "Relax" + " | " + "Hotspot"
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s1_bottom_left

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerBottomLeft.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


# Sector 3 ###########################################################
class ZUV_OT_PieCallerBottomRight(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_bottom_right"
    bl_label = "Checker" + " | " + "Finished"
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s3_bottom_right

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerBottomRight.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


# Sector 9 ###########################################################
class ZUV_OT_PieCallerTopRight(ZsBasicPieCaller):
    bl_idname = "zenuv.pie_caller_top_right"
    bl_label = ZuvLabels.AUTO_MARK_LABEL
    bl_options = {'INTERNAL'}

    template_items = PieOperators.s9_top_right

    def _get_cmd_enum(self, context):
        return _get_caller_enum_items(ZUV_OT_PieCallerTopRight.template_items)

    cmd_enum: bpy.props.EnumProperty(items=_get_cmd_enum, options={'HIDDEN', 'SKIP_SAVE'})
    is_menu: bpy.props.BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})


dynamic_pie_classes = (
    ZUV_OT_PieCallerLeft,
    ZUV_OT_PieCallerRight,
    ZUV_OT_PieCallerBottom,
    ZUV_OT_PieCallerTop,

    ZUV_OT_PieCallerTopLeft,
    ZUV_OT_PieCallerTopRight,
    ZUV_OT_PieCallerBottomLeft,
    ZUV_OT_PieCallerBottomRight
)
