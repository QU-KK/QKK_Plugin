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
from mathutils import Color

import math
import random


from ZenUV.utils.blender_zen_utils import (
    ZenModeSwitcher,
    update_areas_in_all_screens)
from ZenUV.utils.generic import (
    ZUV_PANEL_CATEGORY,
    ZUV_REGION_TYPE,
    ZUV_SPACE_TYPE)
from ZenUV.utils.register_util import RegisterUtils

_rnd = random.Random()


class ColorLabels:
    # Palette
    OT_PALETTE_SELECT_COLOR_DESC = 'Select this color'

    OT_PALETTE_ADD_NEW_PALETTE_LABEL = "Add New Palette"
    OT_PALETTE_ADD_NEW_PALETTE_DESC = "Adds New Palette and sets as Active"

    OT_PALETTE_COLOR_ADD_LABEL = "Palette Color Add"
    OT_PALETTE_COLOR_ADD_DESC = "Adds color to active Palette"

    OT_PALETTE_COLOR_REMOVE_LABEL = "Palette Color Remove"
    OT_PALETTE_COLOR_REMOVE_DESC = "Removes active color from the active Palette"

    OT_PALETTE_COLOR_MOVE_LABEL = "Palette Color Move"
    OT_PALETTE_COLOR_MOVE_DESC = "Moves active color up|down in the active Palette"

    OT_PALETTE_COLOR_SORT_LABEL = "Palette Color Sort"
    OT_PALETTE_COLOR_SORT_DESC = 'Sort Palette Colors By: Hue, Saturation, Value, Luminance'

    OT_PALETTE_ASSIGN_COLOR_TO_GROUP_LABEL = "Assign Color from Palette"
    OT_PALETTE_ASSIGN_COLOR_TO_GROUP_DESC = 'Assign Palette Color to active or all Group(s)'

    OT_PALETTE_ASSIGN_COLOR_FROM_WEIGHT_LABEL = "Assign Color from Weight"
    OT_PALETTE_ASSIGN_COLOR_FROM_WEIGHT_DESC = 'Assign Color from average Vertex Weight of Group to active or all Group(s)'

    OT_PALETTE_EXPORT_GROUP_COLORS_LABEL = 'Export Group Colors to Palette'
    OT_PALETTE_EXPORT_GROUP_COLORS_DESC = 'Export Group Colors to active or new Palette'


class ColorUtils:

    @classmethod
    def _gen_new_color(self, p_items, attr='color'):

        def is_color_present(p_items, p_hue):
            i_count = 0
            for v in reversed(p_items):

                # five items - because of 1 / -0.05 +0.05
                if i_count > 5:
                    break

                f_hue = getattr(v, attr).h
                f_diff = math.fabs(p_hue - f_hue)

                i_count += 1
                f_template_diff = 0.1

                if f_diff < f_template_diff:
                    return True
            return False

        c = Color()
        hue = _rnd.random()
        i_limit = 0
        while is_color_present(p_items, hue) and i_limit < 40:
            hue -= 0.025
            if hue < 0:
                hue += 1.0
            i_limit = i_limit + 1

        c.hsv = hue, 0.7, 0.8
        return c

    @classmethod
    def _gen_new_color_seq(self, p_list, colors):
        if len(colors) == 0:
            return Color()

        i_color_index = -1
        for i, v in reversed(list(enumerate(p_list))):
            if i_color_index == -1:
                for k, v2 in enumerate(colors):
                    if v.color == v2.color:
                        i_color_index = k + 1
                        break
            else:
                break

        if i_color_index == -1 or i_color_index >= len(colors):
            i_color_index = 0

        return colors[i_color_index].color

    @classmethod
    def _gen_new_color_rnd(self, p_list, colors):
        if len(colors) == 0:
            return Color()

        i_color_count = len(colors)
        idx = _rnd.randrange(0, i_color_count)
        if len(p_list) > 1 and i_color_count > 1:
            i_iteration = 0
            while p_list[-1].color == colors[idx].color and i_iteration < 10:
                idx = _rnd.randrange(0, i_color_count)
                i_iteration += 1

        return colors[idx].color

    @classmethod
    def new_color(self, p_list):
        p_scene = bpy.context.scene
        pal = p_scene.zenuv_trim_color_palette.palette
        if pal:
            if len(pal.colors):
                if p_scene.zenuv_trim_color_palette.mode == 'PAL_SEQ':
                    return self._gen_new_color_seq(p_list, pal.colors)
                elif p_scene.zenuv_trim_color_palette.mode == 'PAL_RND':
                    return self._gen_new_color_rnd(p_list, pal.colors)

        return self._gen_new_color(p_list)


def _gen_palette_color(colors):
    return ColorUtils._gen_new_color(colors, 'color')


class ZUV_OT_PaletteSelectColor(bpy.types.Operator):
    bl_idname = "wm.zenuv_palette_select_color"
    bl_label = ""
    bl_description = ColorLabels.OT_PALETTE_SELECT_COLOR_DESC
    bl_options = {'UNDO'}

    color_index: bpy.props.IntProperty()

    def execute(self, context):
        p_scene = context.scene
        pal = p_scene.zenuv_trim_color_palette.palette
        if pal:
            if self.color_index in range(len(pal.colors)):
                pal.colors.active = pal.colors[self.color_index]

        return {'FINISHED'}


class ZUV_OT_PaletteAddNew(bpy.types.Operator):
    bl_idname = "wm.zenuv_palette_add_new"
    bl_label = ColorLabels.OT_PALETTE_ADD_NEW_PALETTE_LABEL
    bl_description = ColorLabels.OT_PALETTE_ADD_NEW_PALETTE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p_scene = context.scene
        pal = bpy.data.palettes.new('Zen Palette')
        if pal:
            p_scene.zenuv_trim_color_palette.palette = pal
            return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_PaletteColorAdd(bpy.types.Operator):
    bl_idname = "wm.zenuv_palette_color_add"
    bl_label = ColorLabels.OT_PALETTE_COLOR_ADD_LABEL
    bl_description = ColorLabels.OT_PALETTE_COLOR_ADD_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.zenuv_trim_color_palette.palette is not None

    def execute(self, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        if pal:
            color_value = _gen_palette_color(pal.colors)
            new_color = pal.colors.new()
            new_color.color = color_value
            new_color.strength = 1.0
            pal.colors.active = new_color
            return {'FINISHED'}
        else:
            return {'CANCELLED'}


class ZUV_OT_PaletteColorRemove(bpy.types.Operator):
    bl_idname = "wm.zenuv_palette_color_remove"
    bl_label = ColorLabels.OT_PALETTE_COLOR_REMOVE_LABEL
    bl_description = ColorLabels.OT_PALETTE_COLOR_REMOVE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        return True if (pal and pal.colors.active) else False

    def execute(self, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        if pal and pal.colors.active:
            pal.colors.remove(pal.colors.active)
            return {'FINISHED'}
        else:
            return {'CANCELLED'}


class ZUV_OT_PaletteColorMove(bpy.types.Operator):
    bl_idname = "wm.zenuv_palette_color_move"
    bl_label = ColorLabels.OT_PALETTE_COLOR_MOVE_LABEL
    bl_description = ColorLabels.OT_PALETTE_COLOR_MOVE_DESC
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.EnumProperty(
        items=(
            ('UP', 'Up', ''),
            ('DOWN', 'Down', '')
        ))

    @classmethod
    def poll(cls, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        return True if (pal and pal.colors.active) else False

    def execute(self, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        if pal and pal.colors.active:
            try:
                switch = ZenModeSwitcher(mode='VERTEX_PAINT')
                vpaint = context.tool_settings.vertex_paint
                was_palette = vpaint.palette
                vpaint.palette = pal
                if bpy.ops.palette.color_move.poll():
                    bpy.ops.palette.color_move(type=self.type)
                    vpaint.palette = was_palette
                switch.return_to_mode()
            except Exception as e:
                self.report({'WARNING'}, str(e))
            return {'FINISHED'}
        else:
            return {'CANCELLED'}


class ZUV_OT_PaletteColorSort(bpy.types.Operator):
    bl_idname = "wm.zenuv_palette_color_sort"
    bl_label = ColorLabels.OT_PALETTE_COLOR_SORT_LABEL
    bl_description = ColorLabels.OT_PALETTE_COLOR_SORT_DESC
    bl_options = {'REGISTER', 'UNDO'}

    type: bpy.props.EnumProperty(
        name='Sort Palette Colors',
        description='Sort By: Hue, Saturation, Value, Luminance',
        items=(
            ('HSV', 'Hue', ''),
            ('SVH', 'Saturation', ''),
            ('VHS', 'Value', ''),
            ('LUMINANCE', 'Luminance', '')
        ))

    @classmethod
    def poll(cls, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        return pal is not None

    def execute(self, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        if pal:
            try:
                switch = ZenModeSwitcher(mode='VERTEX_PAINT')
                vpaint = context.tool_settings.vertex_paint
                was_palette = vpaint.palette
                vpaint.palette = pal
                if bpy.ops.palette.color_move.poll():
                    bpy.ops.palette.sort(type=self.type)
                    vpaint.palette = was_palette
                switch.return_to_mode()
            except Exception as e:
                self.report({'WARNING'}, str(e))
            return {'FINISHED'}
        else:
            return {'CANCELLED'}


class ZUV_OT_PaletteExportGroupColors(bpy.types.Operator):
    bl_idname = 'wm.zuv_palette_export_group_colors'
    bl_label = ColorLabels.OT_PALETTE_EXPORT_GROUP_COLORS_LABEL
    bl_description = ColorLabels.OT_PALETTE_EXPORT_GROUP_COLORS_DESC
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        from .trimsheet_utils import ZuvTrimsheetUtils
        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet:
            return True
        return False

    def _is_color_present(self, color, colors):
        for v_col in colors.values():
            if v_col.color == color:
                return True
        return False

    def execute(self, context):
        from .trimsheet_utils import ZuvTrimsheetUtils
        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet:
            p_scene = context.scene
            pal = p_scene.zenuv_trim_color_palette.palette
            if pal is None:
                bpy.ops.wm.zenuv_palette_add_new()
            pal = p_scene.zenuv_trim_color_palette.palette
            if pal:
                for p_trim in p_trimsheet:
                    if not self._is_color_present(p_trim.color, pal.colors):
                        new_color = pal.colors.new()
                        new_color.color = p_trim.color
                if p_scene.zenuv_trim_color_palette.mode == 'AUTO':
                    p_scene.zenuv_trim_color_palette.mode = 'PAL_SEQ'

                update_areas_in_all_screens(context)

                return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_PaletteAssignColorToGroup(bpy.types.Operator):
    bl_idname = "wm.zenuv_palette_color_assign_to_group"
    bl_label = ColorLabels.OT_PALETTE_ASSIGN_COLOR_TO_GROUP_LABEL
    bl_description = ColorLabels.OT_PALETTE_ASSIGN_COLOR_TO_GROUP_DESC
    bl_options = {'UNDO'}

    group_layer: bpy.props.StringProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        default='')

    group_mode: bpy.props.EnumProperty(
        name='Trim Mode',
        items=[
            ('ACTIVE', 'Active', 'Active trim'),
            ('SELECTED', 'Selected', 'Selected trims'),
            ('ALL', 'All', 'All trims'),
        ],
        default='ACTIVE')

    palette_mode: bpy.props.EnumProperty(
        name='Palette Mode',
        items=(
            ('PAL_SEQ', 'Sequence', 'Palette Sequence Color'),
            ('PAL_RND', 'Random', 'Palette Random Color')
        ),
        default='PAL_SEQ'
    )

    @classmethod
    def poll(cls, context):
        pal = context.scene.zenuv_trim_color_palette.palette
        from .trimsheet_utils import ZuvTrimsheetUtils
        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet and pal and len(pal.colors):
            return True
        return False

    def draw(self, context):
        p_scene = context.scene
        pal = p_scene.zenuv_trim_color_palette.palette
        if pal:
            layout = self.layout
            row = layout.row(align=True)
            row.label(text='Trims:')
            row = layout.row(align=True)
            row.prop(self, 'group_mode', expand=True)
            if self.group_mode == 'ALL':
                row = layout.row(align=True)
                row.prop(self, 'palette_mode', expand=True)
            box = layout.box()
            box.alignment = 'LEFT'
            col = layout
            cols_per_row = 10
            for i, color in enumerate(pal.colors):
                if i % cols_per_row == 0:
                    flow = box.column_flow(columns=cols_per_row, align=True)

                is_color_active = pal.colors.active == color
                op_icon = "LAYER_ACTIVE" if is_color_active else "LAYER_USED"
                col = flow.column(align=True)
                col.prop(color, 'color', text='', emboss=True)
                col.operator('wm.zenuv_palette_select_color',
                             text='', emboss=is_color_active, icon=op_icon).color_index = i

    def execute(self, context: bpy.types.Context):
        p_scene = context.scene
        pal = p_scene.zenuv_trim_color_palette.palette
        if pal and pal.colors.active:
            from .trimsheet_utils import ZuvTrimsheetUtils
            p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
            if p_trimsheet:
                if self.group_mode == 'ACTIVE':
                    p_trim = p_trimsheet.get(self.group_layer, None)
                    if p_trim:
                        p_trim.color = pal.colors.active.color
                        update_areas_in_all_screens(context)
                        return {'FINISHED'}
                else:
                    p_temp_list = []
                    for p_trim in p_trimsheet:
                        if not p_trim.selected and self.group_mode == 'SELECTED':
                            continue
                        if self.palette_mode == 'PAL_SEQ':
                            p_trim.color = ColorUtils._gen_new_color_seq(p_temp_list, pal.colors)
                        else:
                            p_trim.color = ColorUtils._gen_new_color_rnd(p_temp_list, pal.colors)
                        p_temp_list.append(p_trim)
                    update_areas_in_all_screens(context)
                    return {'FINISHED'}

        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class ZUV_PT_3DV_ColorPresets(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Color Management"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_3DV_Trimsheet"

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout
        layout.alignment = 'CENTER'
        s_mode = layout.enum_item_name(context.scene.zenuv_trim_color_palette, 'mode', context.scene.zenuv_trim_color_palette.mode)
        layout.label(text=s_mode)

    def draw(self, context: bpy.types.Context):
        p_scene = context.scene

        layout = self.layout

        width = context.region.width
        ui_scale = context.preferences.system.ui_scale

        cols_per_row = max(int(width / (30 * ui_scale)), 1)

        row = layout.row(align=True)
        row.prop(p_scene.zenuv_trim_color_palette, 'mode', expand=True)

        col = layout.column(align=True)
        from .trimsheet_utils import ZuvTrimsheetUtils
        p_trim = ZuvTrimsheetUtils.getActiveTrim(context)
        s_trim_name = p_trim.name if p_trim else ''
        col.operator(ZUV_OT_PaletteAssignColorToGroup.bl_idname, icon='EYEDROPPER').group_layer = s_trim_name
        col.operator(ZUV_OT_PaletteExportGroupColors.bl_idname, icon='COLOR')

        if p_scene.zenuv_trim_color_palette.mode != 'AUTO':
            pal_layout = layout
            pal_layout.active = p_scene.zenuv_trim_color_palette.mode != 'AUTO'

            pal_layout.template_ID(p_scene.zenuv_trim_color_palette, 'palette', new=ZUV_OT_PaletteAddNew.bl_idname)
            pal = p_scene.zenuv_trim_color_palette.palette
            if pal:
                row = pal_layout.row(align=True)
                row.alignment = 'LEFT'
                row.operator(ZUV_OT_PaletteColorAdd.bl_idname, text='', icon='ADD')
                row.operator(ZUV_OT_PaletteColorRemove.bl_idname, text='', icon='REMOVE')
                row.operator(ZUV_OT_PaletteColorMove.bl_idname, text='', icon='TRIA_UP').type = 'UP'
                row.operator(ZUV_OT_PaletteColorMove.bl_idname, text='', icon='TRIA_DOWN').type = 'DOWN'
                row.operator_menu_enum(ZUV_OT_PaletteColorSort.bl_idname, 'type', text='', icon='SORTSIZE')

                col = pal_layout

                for i, color in enumerate(pal.colors):
                    if i % cols_per_row == 0:
                        flow = pal_layout.column_flow(columns=cols_per_row, align=True)

                    is_color_active = pal.colors.active == color
                    op_icon = "LAYER_ACTIVE" if is_color_active else "LAYER_USED"
                    col = flow.column(align=True)
                    # col.active = is_color_active
                    col.prop(color, 'color', text='', emboss=True)
                    col.operator('wm.zenuv_palette_select_color',
                                 text='', emboss=is_color_active, icon=op_icon).color_index = i


class ZUV_PT_UV_ColorPresets(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_label = "Color Management"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_options = {'DEFAULT_CLOSED'}
    bl_parent_id = "ZUV_PT_UVL_Trimsheet"

    draw_header = ZUV_PT_3DV_ColorPresets.draw_header

    draw = ZUV_PT_3DV_ColorPresets.draw


class ZuvColorPaletteGroup(bpy.types.PropertyGroup):
    palette: bpy.props.PointerProperty(name='Color Palette', type=bpy.types.Palette)
    mode: bpy.props.EnumProperty(
        name='Generate New Color Mode',
        items=(
            ('AUTO', 'Auto', 'Auto Color'),
            ('PAL_SEQ', 'Sequence', 'Palette Sequence Color'),
            ('PAL_RND', 'Random', 'Palette Random Color')
        ),
        default='AUTO'
    )


class ZuvColorPaletteFactory:
    classes = (
        ZuvColorPaletteGroup,

        ZUV_OT_PaletteSelectColor,
        ZUV_OT_PaletteAddNew,
        ZUV_OT_PaletteColorAdd,
        ZUV_OT_PaletteColorRemove,
        ZUV_OT_PaletteColorMove,
        ZUV_OT_PaletteColorSort,
        ZUV_OT_PaletteExportGroupColors,
        ZUV_OT_PaletteAssignColorToGroup
    )

    @classmethod
    def register(cls):
        RegisterUtils.register(cls.classes)
        bpy.types.Scene.zenuv_trim_color_palette = bpy.props.PointerProperty(type=ZuvColorPaletteGroup)

    @classmethod
    def unregister(cls):
        del bpy.types.Scene.zenuv_trim_color_palette
        RegisterUtils.unregister(cls.classes)
