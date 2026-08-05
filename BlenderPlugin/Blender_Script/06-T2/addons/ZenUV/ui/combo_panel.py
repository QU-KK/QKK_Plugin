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

# Copyright 2023, Alex Zhornyak

""" Zen UV Combo UI module """

import bpy

from collections import namedtuple
from typing import List, Tuple

from ZenUV.utils.generic import ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE, ZUV_SPACE_TYPE
from ZenUV.utils.vlog import Log
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.prop.common import uv_enblr
from ZenUV.utils.blender_zen_utils import ZenPolls


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


ComboPanel = namedtuple('ComboPanel', [
    's_type',
    'p_type',
    'enabled',
    'selected',
    'expanded',
    'sel_idx',
    'b_poll',
    'mode_idx',
    'pinned',
    'poll_reason'])


class ZuvComboBase:

    column_align = 'LEFT'

    @classmethod
    def get_panels_in_mode(cls, panel_mode, context: bpy.types.Context) -> Tuple[List[ComboPanel], int, int]:
        p_panels = []

        addon_prefs = get_prefs()
        p_prop_path = f'combo_{panel_mode}_edit_mode'
        p_enum_set = set(getattr(addon_prefs.combo_panel, p_prop_path, ''))
        t_expanded_panels = {}
        if addon_prefs.combo_panel.expanded:
            t_expanded_panels = eval(addon_prefs.combo_panel.expanded)

        t_pinned_panels = {}
        if addon_prefs.combo_panel.pinned:
            t_pinned_panels = eval(addon_prefs.combo_panel.pinned)

        p_panel_enum_items = addon_prefs.combo_panel.bl_rna.properties[p_prop_path].enum_items

        idx_panel = 0

        n_selected_panel_count = len(p_enum_set)
        n_in_mode = 0

        for p_enum_item in p_panel_enum_items:
            pan = p_enum_item.identifier
            p_type = getattr(bpy.types, pan, None)
            if p_type:
                b_enabled = True
                for k, v in uv_enblr.items():
                    if v.get(panel_mode, None) == pan:
                        p_dock_prop = getattr(addon_prefs, f'dock_{panel_mode}_panels')
                        if not getattr(p_dock_prop, k, False):
                            b_enabled = False
                        break

                b_poll = True
                s_reason = ''
                if b_enabled:
                    if hasattr(p_type, 'combo_poll'):
                        b_poll = bool(p_type.combo_poll(context))
                        if not b_poll:
                            if hasattr(p_type, 'poll_reason'):
                                s_reason = p_type.poll_reason(context)

                b_selected = b_enabled and pan in p_enum_set

                is_main_expanded = t_expanded_panels.get(pan, True)
                b_pinned = t_pinned_panels.get(pan, False)

                sel_idx = -1
                mode_idx = -1

                if b_selected:
                    sel_idx = idx_panel
                    idx_panel += 1

                    if b_poll:
                        mode_idx = n_in_mode
                        n_in_mode += 1

                p_panels.append(
                    ComboPanel(
                        pan, p_type, b_enabled, b_selected, is_main_expanded,
                        sel_idx, b_poll, mode_idx, b_pinned, s_reason))

        return (p_panels, n_selected_panel_count, n_in_mode)

    def draw_header_preset(self, context: bpy.types.Context):
        addon_prefs = get_prefs()
        panel_mode = addon_prefs.t_CONTEXT_PANEL_MAP.get(self.bl_space_type)

        p_docked_panels, _, n_in_mode = self.get_panels_in_mode(panel_mode, context)
        if n_in_mode > 1:
            b_is_any_expanded = any(it_pan.expanded and it_pan.mode_idx != -1 for it_pan in p_docked_panels)

            layout = self.layout
            row = layout.row(align=True)
            op = row.operator(
                'wm.zuv_expand_combo_panel', text='',
                icon='DISCLOSURE_TRI_DOWN' if b_is_any_expanded else 'DISCLOSURE_TRI_RIGHT')
            op.panel_name = ''
            op.expanded = b_is_any_expanded
            op.mode = panel_mode
            layout.separator()

    def draw(self, context: bpy.types.Context):
        layout = self.layout  # type: bpy.types.UILayout

        addon_prefs = get_prefs()
        panel_mode = addon_prefs.t_CONTEXT_PANEL_MAP.get(self.bl_space_type)
        t_expanded_panels = {}
        if addon_prefs.combo_panel.expanded:
            t_expanded_panels = eval(addon_prefs.combo_panel.expanded)

        p_fav_props = getattr(addon_prefs, f'favourite_props_{panel_mode}')
        if p_fav_props.enabled_on_top:
            p_fav_props.draw_ui(panel_mode, layout, context, p_fav_props.show_header)

        s_selector_orientation = addon_prefs.combo_panel.selector_orientation
        b_is_vertical_selector = s_selector_orientation == 'VERT'
        b_is_horizontal_mix_selector = s_selector_orientation == 'HOR_MIX'
        row = (
            layout.row(align=False)
            if b_is_vertical_selector
            else layout.column(align=False))

        if b_is_vertical_selector:
            if self.column_align == 'LEFT':
                raw_col1 = row.column(align=True)
                col2 = row.column(align=True)
            else:
                col2 = row.column(align=True)
                raw_col1 = row.column(align=True)
        else:
            raw_col1 = row.grid_flow(align=True) if addon_prefs.combo_panel.selector_header == 'AUTO' else row.row(align=True)
            col2 = (
                row.column(align=True)
                if b_is_horizontal_mix_selector
                else row.row(align=True))

        p_docked_panels, _, n_in_mode = self.get_panels_in_mode(panel_mode, context)

        b_is_box = False

        col1 = raw_col1

        # NOTE: Blender Style is available only for vertical layout
        b_is_blender_style = (
            b_is_vertical_selector and
            (addon_prefs.combo_panel.selector_style not in {'NO_BACK', 'NO_BACK_2'}))
        b_is_inverted = addon_prefs.combo_panel.selector_style in {'BL_INV_1', 'BL_INV_2'}
        b_emboss = addon_prefs.combo_panel.selector_style in {'NO_BACK', 'BL_1', 'BL_INV_1'}
        b_always_emboss = addon_prefs.combo_panel.selector_style == 'NO_BACK_2'

        for p_combo_panel in p_docked_panels:
            p_type = p_combo_panel.p_type
            s_type = p_combo_panel.s_type
            b_selected = p_combo_panel.selected

            p_icon = p_type.get_icon()

            b_enabled = p_combo_panel.enabled

            if b_enabled:

                if b_is_blender_style:
                    b_is_sel = b_selected if not b_is_inverted else not b_selected
                    if b_is_sel:
                        if b_is_box:
                            b_is_box = False
                        col1 = raw_col1
                    else:
                        if not b_is_box:
                            col1 = raw_col1.box()
                            b_is_box = True

                r_op = col1.row(align=True)
                if b_is_blender_style:
                    r_op.alignment = 'CENTER'
                    if col1 == raw_col1:
                        r_op = r_op.column(align=True)
                        r_op.separator()

                r_op.alert = p_combo_panel.pinned
                op = r_op.operator(
                    ZUV_OT_SetComboPanel.bl_idname,
                    icon=p_icon if isinstance(p_icon, str) else 'NONE',
                    icon_value=p_icon if isinstance(p_icon, int) else 0,
                    depress=b_selected,
                    emboss=b_always_emboss or (b_selected and b_emboss),
                    text="")
                op.data_path = f'combo_{panel_mode}_edit_mode'
                op.data_value = s_type
                op.multiselect_with_shift = addon_prefs.combo_panel.use_shift_select

                if b_is_blender_style:
                    if col1 == raw_col1:
                        r_op.separator(factor=0.5)
                else:
                    raw_col1.separator()

                b_poll = p_combo_panel.b_poll

                r_op.active = b_poll

                if b_selected:
                    if p_combo_panel.sel_idx > 0:
                        col2.separator()

                    box = col2.box()
                    box.active = b_poll

                    row_main_header = box.row(align=True)

                    if b_poll:

                        if n_in_mode > 1:
                            is_main_expanded = p_combo_panel.expanded

                            row_op = row_main_header.row(align=True)
                            row_op.alignment = 'EXPAND'
                            op = row_op.operator(
                                'wm.zuv_expand_combo_panel', text=p_type.bl_label,
                                icon='TRIA_DOWN' if is_main_expanded else 'TRIA_RIGHT',
                                emboss=False)
                            op.panel_name = s_type
                            op.expanded = is_main_expanded
                        else:
                            is_main_expanded = True
                            row_op = row_main_header.row(align=False)
                            row_op.alignment = 'CENTER'
                            row_op.separator()
                            row_op.separator()
                            row_op.label(text=p_type.bl_label)

                        if hasattr(p_type, 'draw_header'):
                            r_header = row_main_header.row(align=True)
                            r_header.alignment = 'RIGHT'
                            p_type.layout = r_header
                            p_type.draw_header(p_type, context)

                        if is_main_expanded:
                            if hasattr(p_type, 'combo_draw'):
                                p_type.combo_draw(box, context)
                            else:
                                p_type.layout = box
                                p_type.draw(p_type, context)

                            t_panels = {}
                            t_panels[s_type] = [box, 0]

                            from ZenUV.ui import parented_groups
                            for group in parented_groups:
                                for panel in group:
                                    p_parent_pair = t_panels.get(panel.bl_parent_id, None)  # type: bpy.types.UILayout
                                    if p_parent_pair is not None:
                                        p_child_layout, idx = p_parent_pair

                                        b_subpanel_poll = True
                                        if hasattr(panel, 'poll'):
                                            b_subpanel_poll = bool(panel.poll(context))

                                        p_class_name = panel.__name__
                                        is_expanded = t_expanded_panels.get(
                                            p_class_name, 'DEFAULT_CLOSED' not in getattr(panel, 'bl_options', {}))
                                        row_sub_header = p_child_layout.row(align=True)
                                        row_op = row_sub_header.row(align=True)
                                        for _ in range(idx + 1):
                                            row_op.separator()

                                        s_reason = ''
                                        if not b_subpanel_poll:
                                            if hasattr(panel, 'poll_reason'):
                                                s_reason = panel.poll_reason(context)

                                        row_op.enabled = b_subpanel_poll or s_reason != ''
                                        row_op.active = b_subpanel_poll
                                        row_op.alignment = 'LEFT'

                                        p_icon = None
                                        if hasattr(panel, 'get_icon'):
                                            p_icon = panel.get_icon()

                                        s_icon = ''
                                        n_icon_value = 0

                                        if p_icon is not None:
                                            if isinstance(p_icon, int):
                                                n_icon_value = p_icon
                                            elif isinstance(p_icon, str):
                                                s_icon = p_icon

                                        t_icon = [
                                            ('TRIA_DOWN' if is_expanded else 'TRIA_RIGHT', 0)
                                        ]

                                        b_panel_icon_present = s_icon and s_icon != 'NONE' or n_icon_value != 0
                                        if b_panel_icon_present:
                                            t_icon.append((s_icon, n_icon_value))

                                        n_element_count = len(t_icon)
                                        for it in range(n_element_count):
                                            it_icon = t_icon[it][0]
                                            it_icon_value = t_icon[it][1]

                                            s_text = panel.bl_label if n_element_count == 1 or it == 1 else ''

                                            op = row_op.operator(
                                                'wm.zuv_expand_combo_panel', text=s_text,
                                                icon=it_icon,
                                                icon_value=it_icon_value,
                                                emboss=False)
                                            op.panel_name = p_class_name
                                            op.expanded = row_op.enabled and is_expanded

                                        if hasattr(panel, 'draw_header'):
                                            r_header = row_sub_header.row(align=True)
                                            r_header.alignment = 'RIGHT'
                                            panel.layout = r_header
                                            panel.draw_header(panel, context)

                                        if b_subpanel_poll:
                                            if is_expanded:
                                                if hasattr(panel, 'combo_draw'):
                                                    panel.combo_draw(p_child_layout, context)
                                                else:
                                                    panel.layout = p_child_layout
                                                    panel.draw(panel, context)
                                                t_panels[p_class_name] = (p_child_layout, idx + 1)
                                        else:
                                            if is_expanded and s_reason != '':
                                                t_lines = s_reason.split('\n')
                                                for line_no, line in enumerate(t_lines):
                                                    row = p_child_layout.row(align=True)
                                                    row.active = False
                                                    row.alignment = 'CENTER'
                                                    row.label(text=line, icon='INFO' if line_no == 0 else 'NONE')
                    else:
                        row_op = row_main_header.row(align=True)
                        row_op.alignment = 'EXPAND'
                        row_op.label(text=p_type.bl_label)
                        t_lines = p_combo_panel.poll_reason.split('\n')
                        for idx, line in enumerate(t_lines):
                            row = box.row(align=True)
                            row.active = False
                            row.label(text=line, icon='INFO' if idx == 0 else 'NONE')

                    r2 = row_main_header.row(align=True)
                    r2.alignment = 'RIGHT'
                    op_pin = r2.operator(
                        'wm.zuv_pin_combo_panel', text='', emboss=False,
                        icon='PINNED' if p_combo_panel.pinned else 'UNPINNED')
                    op_pin.panel_name = s_type
                    op_pin.pinned = p_combo_panel.pinned
                    op_pin.mode = panel_mode


class ZUV_PT_3DV_ComboPanel(ZuvComboBase, bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = 'Zen UV'
    bl_context = ''
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = 0  # MUST BE ALWAYS '0' !!!

    def draw_header_preset(self, context: bpy.types.Context):
        layout = self.layout
        addon_prefs = get_prefs()
        if addon_prefs.check_for_updates:
            if ZenPolls.new_addon_version:
                s_version = '.'.join(map(str, ZenPolls.new_addon_version))
                op = layout.operator('wm.zenuv_show_addon_version_info', text=f'Ver. {s_version} available!')
                op.is_silent = False
                op.version = s_version

    @classmethod
    def poll(cls, context: bpy.types.Context):
        addon_prefs = get_prefs()
        return addon_prefs.dock_VIEW_3D_panels_enabled


class ZUV_PT_UVL_ComboPanel(ZuvComboBase, bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_label = 'Zen UV'
    bl_context = ''
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = 0  # MUST BE ALWAYS '0' !!!

    draw_header_preset = ZUV_PT_3DV_ComboPanel.draw_header_preset

    @classmethod
    def poll(cls, context: bpy.types.Context):
        addon_prefs = get_prefs()
        return addon_prefs.dock_UV_panels_enabled


class ZUV_OT_SetComboPanel(bpy.types.Operator):
    bl_idname = "wm.zuv_set_combo_panel"
    bl_label = 'Dock Panel Mode'

    data_path: bpy.props.StringProperty(name='Data Path', default='')
    data_value: bpy.props.StringProperty(name='Data Value', default='')
    multiselect_with_shift: bpy.props.BoolProperty(
        name='Multiselect With Shift',
        description='If set multiple docked panels are selected with shift',
        default=True
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            try:
                addon_prefs = get_prefs()
                s_prop_name = bpy.types.UILayout.enum_item_name(addon_prefs.combo_panel, properties.data_path, properties.data_value)
                s_out = 'Mode: ' + s_prop_name
                if properties.multiselect_with_shift:
                    s_out += '\n * Shift+Click to select multiple'
                else:
                    s_out += '\n * Shift+Click to select single'
                s_out += '\n * Ctrl+Click to pin-unpin'
                return s_out
            except Exception as e:
                print(e)
            return ''
        else:
            return cls.bl_description

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        addon_prefs = get_prefs()
        p_set = set(getattr(addon_prefs.combo_panel, self.data_path))

        t_pinned_panels = {}
        if addon_prefs.combo_panel.pinned:
            t_pinned_panels = eval(addon_prefs.combo_panel.pinned)
        was_pinned = t_pinned_panels.get(self.data_value, False)

        if event.ctrl:
            p_mode = addon_prefs.t_CONTEXT_PANEL_MAP.get(context.space_data.type, None)
            if p_mode:
                res = bpy.ops.wm.zuv_pin_combo_panel(
                    'INVOKE_DEFAULT', mode=p_mode, panel_name=self.data_value, pinned=was_pinned)
                if not was_pinned and 'FINISHED' in res:
                    p_set.add(self.data_value)
                else:
                    return res
            else:
                return {'CANCELLED'}
        else:
            b_with_shift = event.shift if addon_prefs.combo_panel.use_shift_select else not event.shift
            if b_with_shift:
                if self.data_value in p_set:
                    if len(p_set) > 1 and not was_pinned:
                        p_set.remove(self.data_value)
                    else:
                        return {'CANCELLED'}
                else:
                    p_set.add(self.data_value)
            else:
                p_was_set = p_set.copy()
                p_set = set(it for it in p_set if t_pinned_panels.get(it, False))
                if self.data_value not in p_was_set or len(p_set) == 0:
                    p_set.add(self.data_value)

        self.data_value = repr(p_set)

        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            addon_prefs = get_prefs()
            p_set = eval(self.data_value)
            setattr(addon_prefs.combo_panel, self.data_path, p_set)
            return {'FINISHED'}
        except Exception as e:
            Log.error(str(e))

        return {'CANCELLED'}


class ZUV_OT_ExpandComboPanel(bpy.types.Operator):
    bl_idname = "wm.zuv_expand_combo_panel"
    bl_label = 'Expand Panel'
    bl_description = 'Click to expand-collapse panel'

    mode: bpy.props.EnumProperty(
        name='Context Mode',
        items=[
            ('NONE', 'None', ''),
            ('VIEW_3D', 'View 3D', ''),
            ('UV', 'UV', ''),
        ],
        default='NONE'
    )
    panel_name: bpy.props.StringProperty(name='Panel Name', default='')
    expanded: bpy.props.BoolProperty(name='Expanded', default=False)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.expanded = not self.expanded
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            addon_prefs = get_prefs()
            t_panels = {}
            if addon_prefs.combo_panel.expanded:
                t_panels = eval(addon_prefs.combo_panel.expanded)

            if self.panel_name:
                t_panels[self.panel_name] = self.expanded
            else:
                p_docked_panels, _, _ = ZuvComboBase.get_panels_in_mode(self.mode, context)
                for it_panel in p_docked_panels:
                    if it_panel.mode_idx != -1:
                        t_panels[it_panel.s_type] = self.expanded

            addon_prefs.combo_panel.expanded = repr(t_panels)

            return {'FINISHED'}
        except Exception as e:
            Log.error(str(e))

        return {'CANCELLED'}


class ZUV_OT_ExpandFavCategory(bpy.types.Operator):
    bl_idname = "wm.zuv_expand_fav_category"
    bl_label = 'Expand Favourite Category'
    bl_description = 'Click to expand-collapse favourite category'

    mode: bpy.props.EnumProperty(
        name='Context Mode',
        items=[
            ('NONE', 'None', ''),
            ('VIEW_3D', 'View 3D', ''),
            ('UV', 'UV', ''),
        ],
        default='NONE'
    )

    category_name: bpy.props.StringProperty(name='Category Name', default='')
    expanded: bpy.props.BoolProperty(name='Expanded', default=False)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.expanded = not self.expanded
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            addon_prefs = get_prefs()
            t_panels = {}
            p_fav_props = getattr(addon_prefs, f'favourite_props_{self.mode}')
            if p_fav_props is None:
                raise RuntimeError(f'Mode - {self.mode} is not defined!')

            if p_fav_props.expanded:
                t_panels = eval(p_fav_props.expanded)

            t_panels[self.category_name] = self.expanded

            p_fav_props.expanded = repr(t_panels)

            return {'FINISHED'}
        except Exception as e:
            Log.error(str(e))

        return {'CANCELLED'}


class ZUV_OT_PinComboPanel(bpy.types.Operator):
    bl_idname = "wm.zuv_pin_combo_panel"
    bl_label = 'Pin Panel'
    bl_description = 'Click to pin-unpin panel'

    mode: bpy.props.EnumProperty(
        name='Context Mode',
        items=[
            ('NONE', 'None', ''),
            ('VIEW_3D', 'View 3D', ''),
            ('UV', 'UV', ''),
        ],
        default='NONE'
    )
    panel_name: bpy.props.StringProperty(name='Panel Name', default='')
    pinned: bpy.props.BoolProperty(name='Pinned', default=False)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.pinned = not self.pinned
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            addon_prefs = get_prefs()
            t_panels = {}
            if addon_prefs.combo_panel.pinned:
                t_panels = eval(addon_prefs.combo_panel.pinned)

            if self.panel_name:
                t_panels[self.panel_name] = self.pinned
            else:
                p_docked_panels, _, _ = ZuvComboBase.get_panels_in_mode(self.mode, context)
                for it_panel in p_docked_panels:
                    if it_panel.mode_idx != -1:
                        t_panels[it_panel.s_type] = self.pinned

            addon_prefs.combo_panel.pinned = repr(t_panels)

            return {'FINISHED'}
        except Exception as e:
            Log.error(str(e))

        return {'CANCELLED'}
