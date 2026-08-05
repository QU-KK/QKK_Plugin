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

# Copyright 2024, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy
import idprop

from bl_operators.presets import AddPresetBase, ExecutePreset
from bpy_extras.io_utils import ImportHelper
from bl_operators.wm import context_path_validate
from bpy.app.translations import (
    pgettext_tip as tip_,
)

from pathlib import Path
import os
from collections import defaultdict
import ast

from ZenUV.utils.adv_generic_ui_list import zenuv_draw_ui_list, _set_context_attr, _get_context_attr
from ZenUV.utils.blender_zen_utils import ZuvPresets, update_areas_in_all_screens, get_command_props
from ZenUV.utils.vlog import Log
from ZenUV.prop.common import update_addon_prop


FAV_PRESET_SUBDIR = "favourite_presets_"


FAV_CONTEXT_SUFFIX = {
    'UV': 'UV',
    'VIEW_3D': '3D'
}


class ZUV_FavItem(bpy.types.PropertyGroup):
    def update_ui(self, context: bpy.types.Context):
        update_areas_in_all_screens(context)

    category: bpy.props.StringProperty(
        name="Category",
        default='',
        update=update_ui
    )

    def get_command(self):
        return self.get('command', '')

    t_skip_values = {
            "ZUV_PT_3DV_ComboPanel",
            "ZUV_PT_UVL_ComboPanel",
            "ZUV_PT_3DV_Favourites",
            "ZUV_PT_UVL_Favourites",
        }

    def set_command(self, value):
        if value not in ZUV_FavItem.t_skip_values:
            self['command'] = value

    display_text: bpy.props.BoolProperty(
        name="Display Text",
        description="Display layout text when it is possible",
        default=True,
        update=update_ui
    )

    command: bpy.props.StringProperty(
        name="Command",
        get=get_command,
        set=set_command,
        default="",
        update=update_ui
    )

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('OPERATOR', 'Operator', '', 'MOUSE_LMB', 0),
            ('PANEL', 'Panel', '', 'TOPBAR', 1),
            ('PROPERTY', 'Property', '', 'PROPERTIES', 2),
            ('LABEL', 'Label', '', 'FILE_TEXT', 3),
            ('SCRIPT', 'Script', '', 'FILE_SCRIPT', 4),
        ],
        default='OPERATOR',
        update=update_ui
    )

    layout: bpy.props.EnumProperty(
        name='Layout',
        items=[
            ('AUTO', 'Auto', 'Automatic layout'),
            ('ROW', 'Row', 'Row layout'),
            ('COL', 'Column', 'Column layout'),
            ('GRID', 'Flow Grid', 'Flow grid layout'),
        ],
        default='AUTO',
        update=update_ui
    )

    layout_group: bpy.props.EnumProperty(
        name='Layout Group',
        description="Option to open, close or ignore layout group",
        items=[
            ('NONE', 'None', "Do not change current group"),
            ('OPEN', 'Open', "Open active layout group, where all elements will be placed without separators"),
            ('CLOSE', 'Close', "Close active layout group"),
        ],
        default='NONE',
        update=update_ui
    )

    icon_only: bpy.props.BoolProperty(
        name="Icon Only",
        default=False,
        update=update_ui
    )

    def get_ui_icon_only(self):
        return self.icon_only

    def set_ui_icon_only(self, value):
        if self.icon_only != value:
            self.icon_only = value

            if self.icon_only:
                if self.mode == 'OPERATOR':
                    if not self.icon:
                        self.icon = 'QUESTION'
                        self.is_icon_value = False

    ui_icon_only: bpy.props.BoolProperty(
        name='Icon Only',
        get=get_ui_icon_only,
        set=set_ui_icon_only,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    is_icon_value: bpy.props.BoolProperty(
        name="Is Icon Value",
        default=False
    )

    def get_ui_icon_value_type(self):
        return 1 if self.is_icon_value else 0

    def set_ui_icon_value_type(self, value):
        self.is_icon_value = True if value == 1 else False

    ui_icon_value_type: bpy.props.EnumProperty(
        name="Icon Type",
        description="Standard Blender icons or custom ZenUV icons",
        items=(
            ('STANDARD', 'Standard', 'Standard Blender icons'),
            ('CUSTOM', 'Custom', 'Custom ZenUV icons'),
        ),
        get=get_ui_icon_value_type,
        set=set_ui_icon_value_type,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    icon: bpy.props.StringProperty(
        name="Icon",
        default="",
        update=update_ui
    )

    def get_icon_data(self):
        from ZenUV.ico import ZENUV_ICONS, is_blender_icon_valid
        s_icon = self.icon
        n_icon_value = 0
        if not s_icon:
            s_icon = 'NONE'
        else:
            if self.is_icon_value:
                p_icon_preview = ZENUV_ICONS.get(s_icon, None)
                if p_icon_preview:
                    n_icon_value = p_icon_preview.icon_id
                    s_icon = 'NONE'
                else:
                    s_icon = 'ERROR'
            else:
                if not is_blender_icon_valid(s_icon):
                    s_icon = 'ERROR'
        return s_icon, n_icon_value

    def check_has_cmd_error(self, context: bpy.types.Context):
        b_command_alert = False
        s_alert_description = ''
        if self.command:
            if self.mode == 'PANEL':
                b_command_alert = getattr(bpy.types, self.command, None) is None
            elif self.mode == 'OPERATOR':
                try:
                    p_op_props = get_command_props(self.command)
                    b_command_alert = p_op_props.bl_op_cls.get_rna_type() is None
                    if b_command_alert:
                        s_alert_description = 'Operator not found'
                except Exception as e:
                    print(e)
                    b_command_alert = True
                    s_alert_description = str(e)
            elif self.mode == 'PROPERTY':
                b_command_alert = True
                try:
                    s_instance, s_attr = self.command.rsplit(".", 1)
                    p_instance = context_path_validate(context, s_instance)
                    if hasattr(p_instance, 'bl_rna'):
                        if s_attr in p_instance.bl_rna.properties:
                            b_command_alert = False
                except Exception as e:
                    s_alert_description = str(e)
            elif self.mode == 'SCRIPT':
                try:
                    ast.parse(self.command)
                except Exception as e:
                    b_command_alert = True
                    s_alert_description = str(e)
        return b_command_alert, s_alert_description

    @staticmethod
    def get_auto_icon(s_mode, s_cmd, context: bpy.types.Context):
        p_icon = None

        out_icon = ''
        out_is_icon_value = False

        p_panel = None

        if s_mode == 'PANEL':
            p_panel = getattr(bpy.types, s_cmd, None)
            if p_panel and hasattr(p_panel, 'get_icon'):
                p_icon = p_panel.get_icon()
        elif s_mode == 'PROPERTY':
            try:
                s_instance, s_attr = s_cmd.rsplit(".", 1)
                p_instance = context_path_validate(context, s_instance)
                if hasattr(p_instance, 'bl_rna'):
                    if s_attr in p_instance.bl_rna.properties:
                        p_prop = p_instance.bl_rna.properties[s_attr]
                        if p_prop.icon:
                            p_icon = p_prop.icon
            except Exception:
                pass

        if p_icon is not None:
            if isinstance(p_icon, int):
                if p_panel:
                    if hasattr(p_panel, 'zen_icon_value'):
                        out_icon = p_panel.zen_icon_value
                        out_is_icon_value = True
            elif isinstance(p_icon, str):
                out_icon = p_icon

        return out_icon, out_is_icon_value

    @staticmethod
    def get_auto_name(s_mode, s_cmd, context: bpy.types.Context):
        s_panel_id = ''
        try:
            if s_mode == 'OPERATOR':
                op_cmd = get_command_props(s_cmd)
                if "wm.zuv_expand_combo_panel" in s_cmd or "wm_ot_zuv_pin_combo_panel" in s_cmd:
                    s_panel_id = op_cmd.kwargs.panel_name
                    raise GeneratorExit
                if 'wm.zuv_set_combo_panel' in s_cmd:
                    s_panel_id = op_cmd.kwargs.data_value
                    raise GeneratorExit
                if op_cmd.bl_label:
                    return op_cmd.bl_label
                if op_cmd.bl_desc:
                    return op_cmd.bl_desc
        except GeneratorExit:
            pass

        if s_mode == 'PANEL':
            s_panel_id = s_cmd

        if s_panel_id:
            p_panel_class = getattr(bpy.types, s_panel_id, None)
            if p_panel_class and p_panel_class.bl_label:
                return p_panel_class.bl_label

        if s_mode == 'PROPERTY':
            try:
                s_instance, s_attr = s_cmd.rsplit(".", 1)
                p_instance = context_path_validate(context, s_instance)
                if hasattr(p_instance, 'bl_rna'):
                    if s_attr in p_instance.bl_rna.properties:
                        p_prop = p_instance.bl_rna.properties[s_attr]
                        if p_prop.name:
                            return p_prop.name
                        if p_prop.description:
                            return p_prop.description
                        if p_prop.identifier:
                            return p_prop.identifier
                        return s_attr
            except Exception:
                pass
        return ''

    def has_icon(self):
        s_icon, n_icon_value = self.get_icon_data()
        return (s_icon and s_icon not in {'NONE', 'BLANK1'}) or (n_icon_value != 0)


class ZUV_FavProps(bpy.types.PropertyGroup):

    enabled_on_top: bpy.props.BoolProperty(
        name='Enabled On Top',
        description='Favourites panel enabled on top of N-Panel',
        default=True,
        update=update_addon_prop
    )

    favourites: bpy.props.CollectionProperty(
        name='Zen UV Favourites',
        type=ZUV_FavItem
    )

    favourite_index: bpy.props.IntProperty(
        name='Active Favourite Index',
        description='Active index of the current favourite item',
        default=-1,
        min=-1,
        update=update_addon_prop
    )

    expanded: bpy.props.StringProperty(
        name='Expanded Favourite Categories',
        default='',
        update=update_addon_prop
    )

    show_header: bpy.props.BoolProperty(
        name='Show Header',
        default=True,
        update=update_addon_prop
    )

    header_expanded: bpy.props.BoolProperty(
        name='Header Expanded',
        default=True,
        update=update_addon_prop
    )

    def get_display_mode(self):
        t_res = 0b000

        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        for k in FAV_CONTEXT_SUFFIX.keys():
            if self == getattr(addon_prefs, f'favourite_props_{k}'):

                if self.enabled_on_top:
                    t_res |= 1 << 0

                p_dock_props = getattr(addon_prefs, f'dock_{k}_panels')
                if p_dock_props.enable_pt_favourites:
                    t_res |= 1 << 1

                p_float_props = getattr(addon_prefs, f'float_{k}_panels')
                if p_float_props.enable_pt_favourites:
                    t_res |= 1 << 2
                break

        return t_res

    def set_display_mode(self, value):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        for k in FAV_CONTEXT_SUFFIX.keys():
            if self == getattr(addon_prefs, f'favourite_props_{k}'):

                self.enabled_on_top = bool(value & (1 << 0))

                p_dock_props = getattr(addon_prefs, f'dock_{k}_panels')
                p_dock_props.enable_pt_favourites = bool(value & (1 << 1))

                p_float_props = getattr(addon_prefs, f'float_{k}_panels')
                p_float_props.enable_pt_favourites = bool(value & (1 << 2))

                break

    display_mode: bpy.props.EnumProperty(
        name='Display',
        description='Display mode of the favourites panel',
        items=[
            ('TOP', 'Top', 'Favourites will be place at the top of N-Panel', 'TOPBAR', 0b001),
            ('TAB', 'Tab', 'Favourites will be represented as the tab page of N-Panel', 'MENU_PANEL', 0b010),
            ('FLOAT', 'Floating', 'Favourites will be represented as the separate floating panel', 'WORKSPACE', 0b100),
        ],
        get=get_display_mode,
        set=set_display_mode,
        options={'ENUM_FLAG', 'SKIP_SAVE'},
        update=update_addon_prop
    )

    @staticmethod
    def get_fav_props(s_panel_mode: str):
        from ZenUV.prop.zuv_preferences import get_prefs

        addon_prefs = get_prefs()
        p_fav_props: ZUV_FavProps = getattr(addon_prefs, f'favourite_props_{s_panel_mode}')
        return p_fav_props

    def draw(self, s_panel_mode: str, layout: bpy.types.UILayout, context: bpy.types.Context):
        col_main = layout.column()
        col_main.active = len(self.display_mode) > 0

        box = col_main.box()
        box.use_property_split = True
        box.prop(self, 'display_mode')

        if self.enabled_on_top:
            row = box.row(align=True)
            row.active = len(self.favourites) > 0
            row.prop(self, 'show_header')

        row = col_main.row(align=True)

        p_fav_item: ZUV_FavItem = (
            self.favourites[self.favourite_index]
            if self.favourite_index in range(len(self.favourites))
            else None)

        s_menu = 'ZUV_MT_StoreFavPresets' + FAV_CONTEXT_SUFFIX[s_panel_mode]
        preset_menu_class = getattr(bpy.types, s_menu)

        s_preset_name = preset_menu_class.bl_label

        row.menu(s_menu, text=s_preset_name)

        op = row.operator("wm.zuv_fav_add_preset", text="", icon="ADD")
        if s_preset_name and s_preset_name != preset_menu_class.default_label:
            op.name = s_preset_name
        op.remove_active = False
        op.panel_mode = s_panel_mode

        op = row.operator("wm.zuv_fav_add_preset", text="", icon="REMOVE")
        op.remove_active = True
        op.panel_mode = s_panel_mode

        s_preset_folder_name = FAV_PRESET_SUBDIR + s_panel_mode.lower()
        target_path = os.path.join("presets", ZuvPresets.get_preset_path(s_preset_folder_name))
        target_path = bpy.utils.user_resource('SCRIPTS', path=target_path, create=True)

        row.operator(
            'wm.path_open',
            icon='FILEBROWSER',
            text='').filepath = target_path

        row.separator()

        op = row.operator("wm.zenuv_presets_load_default", text='', icon='IMPORT')
        op.preset_folder = s_preset_folder_name

        # NOTE: we detect is there any icon once, to have better performance by not doing it on every row
        b_has_any_category = any(item.category != "" for item in self.favourites)
        bpy.app.driver_namespace[f"ZUV_UL_FavouritesList.{self.as_pointer()}.has_categories"] = b_has_any_category

        b_has_any_icon = any(item.has_icon() for item in self.favourites)
        bpy.app.driver_namespace[f"ZUV_UL_FavouritesList.{self.as_pointer()}.has_icons"] = b_has_any_icon

        right_col = zenuv_draw_ui_list(
            col_main,
            context,
            class_name="ZUV_UL_FavouritesList",
            list_path=f"preferences.addons['ZenUV'].preferences.favourite_props_{s_panel_mode}.favourites",
            active_index_path=f"preferences.addons['ZenUV'].preferences.favourite_props_{s_panel_mode}.favourite_index",
            unique_id="name",
            new_name_attr="name",
            new_name_val="Item"
        )

        s_module = s_panel_mode.replace('_', '').lower()
        right_col.separator()
        right_col.operator(f"{s_module}.zuv_fav_duplicate_item", text="", icon='DUPLICATE')

        if p_fav_item:
            b_is_label = p_fav_item.mode == 'LABEL'
            b_is_operator = p_fav_item.mode == 'OPERATOR'
            b_is_script = p_fav_item.mode == 'SCRIPT'

            box = col_main.box()
            box.use_property_split = True

            b_command_alert, _ = p_fav_item.check_has_cmd_error(context)

            s_icon, _ = p_fav_item.get_icon_data()

            r_name = box.row(align=True)
            r_name.active = p_fav_item.display_text
            r_name.prop(p_fav_item, 'name')
            r_name.prop(p_fav_item, "display_text", text="")
            if not b_is_label and p_fav_item.command:
                op_name = r_name.operator('wm.zuv_fav_update_name', text='', icon='FILE_REFRESH')
                op_name.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{self.favourite_index}].name'
                op_name.mode = p_fav_item.mode
                op_name.cmd = p_fav_item.command

            for k in p_fav_item.__annotations__.keys():
                row = box.row(align=True)
                if k == 'icon':
                    row.alert = (s_icon == 'ERROR') or (p_fav_item.icon_only and p_fav_item.icon in {'', 'NONE', 'BLANK1'})
                    row.prop(p_fav_item, k)
                    op_sel = row.operator('wm.zuv_fav_select_icon')
                    op_sel.is_icon_value = p_fav_item.is_icon_value
                    op_sel.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{self.favourite_index}].icon'
                elif k == 'command':
                    row.alert = b_command_alert
                    row.active = not b_is_label
                    row.prop(p_fav_item, k)
                    row.separator()

                    if b_is_operator:
                        r_edit_op = row.row(align=True)
                        r_edit_op.enabled = not b_command_alert and p_fav_item.command != ""
                        op = r_edit_op.operator("wm.zuv_fav_edit_operator", text="", icon="PRESET")
                        op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{self.favourite_index}].command'

                    if not b_is_label and not b_is_script:
                        row.separator()
                        row.menu(menu=f'ZUV_MT_FavCommandMenu{FAV_CONTEXT_SUFFIX[s_panel_mode]}', icon='DOWNARROW_HLT', text='')
                elif k in {'icon_only', 'display_text', 'is_icon_value'}:
                    continue
                elif k == 'ui_icon_value_type':
                    row.prop(p_fav_item, k, expand=True)
                else:
                    row.prop(p_fav_item, k)

    def draw_panel_header(self, s_panel_mode: str, layout: bpy.types.UILayout, context: bpy.types.Context):
        row = layout.row(align=True)

        s_menu = 'ZUV_MT_StoreFavPresets' + FAV_CONTEXT_SUFFIX[s_panel_mode]
        preset_menu_class = getattr(bpy.types, s_menu)
        row.menu(s_menu, text=preset_menu_class.bl_label)
        row.separator()

    def draw_ui(self, s_panel_mode: str, layout: bpy.types.UILayout, context: bpy.types.Context, b_show_header):
        try:
            from ZenUV.prop.zuv_preferences import get_prefs
            addon_prefs = get_prefs()
            t_expanded_panels = {}
            if addon_prefs.combo_panel.expanded:
                t_expanded_panels = eval(addon_prefs.combo_panel.expanded)
            if self.favourites:
                p_fav_layout = layout.box()
                p_fav_current = p_fav_layout

                if b_show_header:
                    r_fav = p_fav_layout.row(align=True)
                    row = r_fav.row(align=True)
                    row.alignment = 'LEFT'
                    row.prop(
                        self, 'header_expanded', text='',
                        icon='TRIA_DOWN' if self.header_expanded else 'TRIA_RIGHT',
                        emboss=False)

                    row = r_fav.row(align=True)
                    row.alignment = 'LEFT'
                    row.label(text="Favourites", icon='FUND')

                    row = r_fav.row(align=True)
                    row.alignment = 'RIGHT'

                    s_menu = 'ZUV_MT_StoreFavPresets' + FAV_CONTEXT_SUFFIX[s_panel_mode]
                    preset_menu_class = getattr(bpy.types, s_menu)
                    row.menu(s_menu, text=preset_menu_class.bl_label)

                    if not self.header_expanded:
                        raise GeneratorExit

                t_favs = defaultdict(list)
                for p_item in self.favourites:
                    t_favs[p_item.category].append(p_item)

                t_expanded_fav_cats = {}
                if self.expanded:
                    t_expanded_fav_cats = eval(self.expanded)

                for k, v in t_favs.items():
                    b_are_all_icons = all(p_item.icon_only for p_item in v if p_item.mode != 'PANEL')
                    is_expanded = True
                    if k:
                        is_expanded = t_expanded_fav_cats.get(k, False)

                        row_op = p_fav_layout.row(align=True)
                        row_op.alignment = 'LEFT'
                        op = row_op.operator(
                            'wm.zuv_expand_fav_category', text=k,
                            icon='TRIA_DOWN' if is_expanded else 'TRIA_RIGHT',
                            emboss=False)
                        op.mode = s_panel_mode
                        op.category_name = k
                        op.expanded = is_expanded
                        p_fav_current = p_fav_layout
                    if is_expanded:

                        op_row = None

                        def create_item_layout(p_item: ZUV_FavItem, p_layout):
                            nonlocal p_fav_current
                            if p_item.layout_group == 'OPEN':
                                p_fav_current = p_fav_layout.column(align=True)
                            elif p_item.layout_group == 'CLOSE':
                                p_fav_current = p_fav_layout

                            if p_layout is None:
                                if p_item.layout == 'AUTO':
                                    if b_are_all_icons and not p_item.mode == 'PANEL':
                                        p_layout = p_fav_current.row(align=True)

                            if p_item.layout == 'ROW':
                                p_layout = p_fav_current.row(align=True)
                            elif p_item.layout == 'COL':
                                p_layout = p_fav_current.column(align=True)

                            if p_layout is None or p_item.layout == 'GRID':
                                p_layout = p_fav_current.grid_flow(align=True)

                            return p_layout

                        p_item: ZUV_FavItem
                        for p_item in v:
                            if not p_item.command and p_item.mode != 'LABEL':
                                continue
                            try:
                                s_icon, n_icon_value = p_item.get_icon_data()
                                if p_item.icon_only:
                                    if n_icon_value == 0 and s_icon in {'', 'NONE', 'BLANK1'}:
                                        s_icon = 'QUESTION'

                                if p_item.mode == 'OPERATOR':
                                    op_props = get_command_props(p_item.command, use_last_properties=False)

                                    s_id = op_props.bl_op_cls.idname()
                                    if op_props.bl_op_cls.get_rna_type() is not None:
                                        op_row = create_item_layout(p_item, op_row)

                                        op_layout = op_row.operator(
                                            s_id,
                                            icon=s_icon,
                                            icon_value=n_icon_value,
                                            text="" if (p_item.icon_only or not p_item.display_text) else p_item.name)
                                        for op_arg, op_val in op_props.kwargs.items():
                                            setattr(op_layout, op_arg, op_val)

                                elif p_item.mode == 'PANEL':
                                    # NOTE: Do not use 'op_row' inside 'PANEL' mode !!!

                                    s_type = p_item.command
                                    panel = getattr(bpy.types, s_type, None)
                                    if panel is None:
                                        raise RuntimeError(f'Panel: {s_type} - not found')

                                    t_panels = {}
                                    t_panels[s_type] = [p_fav_layout, 0]
                                    idx = 0

                                    b_subpanel_poll = True
                                    s_reason = ''

                                    overrided_context = context

                                    try:
                                        from ZenUV.ops.context_utils import FakeContext

                                        from bl_ui.properties_data_mesh import MeshButtonsPanel
                                        from bl_ui.properties_material import MaterialButtonsPanel

                                        overrided_dict = None

                                        p_act_obj = context.active_object

                                        # NOTE: 'context.mesh' is required
                                        if p_act_obj and not hasattr(context, "mesh") and issubclass(panel, MeshButtonsPanel):
                                            if p_act_obj.type == 'MESH':
                                                if overrided_dict is None:
                                                    overrided_dict = context.copy()
                                                overrided_dict['mesh'] = context.active_object.data

                                        # NOTE: 'context.material' is required
                                        if p_act_obj and not hasattr(context, "material") and issubclass(panel, MaterialButtonsPanel):
                                            if p_act_obj.active_material_index in range(len(p_act_obj.material_slots)):
                                                p_mat_slot = p_act_obj.material_slots[p_act_obj.active_material_index]
                                                if overrided_dict is None:
                                                    overrided_dict = context.copy()
                                                overrided_dict['material'] = p_mat_slot.material
                                                overrided_dict['material_slot'] = p_mat_slot

                                        if overrided_dict:
                                            overrided_context = FakeContext(overrided_dict)
                                    except Exception as e:
                                        Log.error("OVERRIDE CONTEXT:", e)

                                    try:
                                        if hasattr(panel, 'combo_poll'):
                                            b_subpanel_poll = bool(panel.combo_poll(overrided_context))
                                        elif hasattr(panel, 'poll'):
                                            b_subpanel_poll = bool(panel.poll(overrided_context))
                                    except Exception as e:
                                        b_subpanel_poll = False
                                        s_reason = str(e)

                                    p_child_layout = create_item_layout(p_item, p_fav_layout)

                                    b_display_header = p_item.display_text

                                    p_class_name = panel.__name__
                                    if not b_subpanel_poll and not s_reason:
                                        if hasattr(panel, 'poll_reason'):
                                            s_reason = panel.poll_reason(overrided_context)

                                    is_expanded = True

                                    if b_display_header:
                                        is_expanded = t_expanded_panels.get(
                                            p_class_name, 'DEFAULT_CLOSED' not in getattr(panel, 'bl_options', {}))

                                        row_sub_header = p_child_layout.row(align=True)
                                        row_op = row_sub_header.row(align=True)
                                        for _ in range(idx + 1):
                                            row_op.separator()

                                        row_op.enabled = b_subpanel_poll or s_reason != ''
                                        row_op.active = b_subpanel_poll
                                        row_op.alignment = 'LEFT'

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

                                            s_text = p_item.name if n_element_count == 1 or it == 1 else ''

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
                                            panel.draw_header(panel, overrided_context)

                                    if b_subpanel_poll:
                                        if is_expanded:
                                            if hasattr(panel, 'combo_draw'):
                                                panel.combo_draw(p_child_layout, overrided_context)
                                            else:
                                                panel.layout = p_child_layout
                                                panel.draw(panel, overrided_context)

                                            # NOTE: It was detected that operator context can be changed inside
                                            #       and then affects on the next layouts
                                            p_child_layout.operator_context = 'INVOKE_DEFAULT'

                                            t_panels[p_class_name] = (p_child_layout, idx + 1)
                                    else:
                                        if is_expanded and s_reason != '':
                                            t_lines = s_reason.split('\n')
                                            for line_no, line in enumerate(t_lines):
                                                row = p_child_layout.row(align=True)
                                                row.active = False
                                                row.alignment = 'CENTER'
                                                row.label(text=line, icon='INFO' if line_no == 0 else 'NONE')
                                elif p_item.mode == 'PROPERTY':
                                    s_instance, s_attr = p_item.command.rsplit(".", 1)
                                    p_instance = context_path_validate(context, s_instance)
                                    if hasattr(p_instance, 'bl_rna'):
                                        if s_attr in p_instance.bl_rna.properties:

                                            op_row = create_item_layout(p_item, op_row)

                                            op_row.prop(
                                                p_instance, s_attr,
                                                text="" if (p_item.icon_only or not p_item.display_text) else p_item.name,
                                                icon=s_icon, icon_value=n_icon_value)
                                elif p_item.mode == 'LABEL':
                                    op_row = create_item_layout(p_item, op_row)
                                    op_row.label(
                                        text="" if (p_item.icon_only or not p_item.display_text) else p_item.name,
                                        icon=s_icon, icon_value=n_icon_value)
                                elif p_item.mode == 'SCRIPT':
                                    op_row = create_item_layout(p_item, op_row)
                                    exec(p_item.command)

                            except Exception as e:
                                Log.error('FAVOURITE ITEM DRAW:', p_item.command, e)
        except GeneratorExit:
            pass
        except Exception as e:
            Log.error('FAVOURITES DRAW:', e)


class ZUV_UL_FavouritesList(bpy.types.UIList):

    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data: ZUV_FavProps, item: ZUV_FavItem, icon, active_data, active_propname, index):

        b_has_cmd_error = False
        if item.command:
            b_has_cmd_error, _ = item.check_has_cmd_error(context)

        b_is_sub_layout_item = False
        if index > 0:
            if item.layout == 'AUTO' and item.mode != 'PANEL':

                for idx in range(index - 1, -1, -1):
                    p_prev_item = data.favourites[idx]
                    if p_prev_item.category == item.category:
                        if p_prev_item.mode == 'PANEL':
                            break
                        else:
                            if p_prev_item.layout != 'AUTO':
                                b_is_sub_layout_item = True
                                break

        main_row = layout.row(align=False)
        main_row.active = item.command != '' or item.mode == 'LABEL'
        main_row.alert = b_has_cmd_error

        row_grid = main_row.split(factor=0.5, align=True)

        row_left = row_grid.row(align=True)

        if b_is_sub_layout_item:
            row_left.label(text='', icon='DOT')

        b_has_any_icon = bpy.app.driver_namespace.get(f"ZUV_UL_FavouritesList.{data.as_pointer()}.has_icons", False)
        if b_has_any_icon:
            s_icon, n_icon_value = item.get_icon_data()
            if n_icon_value == 0 and s_icon == 'NONE' or s_icon == '':
                s_icon = 'BLANK1'
            r_icon = row_left.row(align=True)
            r_icon.label(text='', icon=s_icon, icon_value=n_icon_value)
            r_icon.alert = s_icon == 'ERROR'

        row_left.prop(item, 'name', text='', emboss=False)

        row_right = row_grid.row(align=True)

        b_has_any_category = bpy.app.driver_namespace.get(f"ZUV_UL_FavouritesList.{data.as_pointer()}.has_categories", False)
        if b_has_any_category:
            r_cat = row_right.row(align=True)
            r_cat.prop(item, 'category', text='', emboss=False)

        r_layout = row_right.row(align=True)
        r_layout.prop(item, 'layout', text='', emboss=False)

        row_right.prop(item, 'mode', text='', emboss=False, icon_only=True)

        r_icon_only = row_right.row(align=True)
        r_icon_only.alert = item.icon_only and item.icon in {'', 'NONE', 'BLANK1'}
        r_icon_only.prop(item, 'ui_icon_only', icon_only=True, icon='IMAGE_PLANE', emboss=True)


class ZUV_OT_FavExecutePresetBase(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}

    bl_label = 'Load Favourite Preset'
    bl_description = "Load favourite preset from file"

    filepath: bpy.props.StringProperty(
        subtype='FILE_PATH',
        options={'SKIP_SAVE', 'HIDDEN'},
    )

    def get_preset_name(self):
        return Path(self.filepath).stem

    preset_name: bpy.props.StringProperty(
        name='Preset Name',
        get=get_preset_name
    )

    enable_confirmation: bpy.props.BoolProperty(
        name='Enable Confirmation',
        default=True
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self.enable_confirmation:
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
        return self.execute(context)

    def execute(self, context):
        # Use this method because if it is inherited, can not change Blender theme !
        res = ExecutePreset.execute(self, context)

        update_areas_in_all_screens(context)

        return res


class ZUV_OT_FavExecutePresetUV(ZUV_OT_FavExecutePresetBase):
    bl_idname = "wm.zuv_fav_execute_preset_uv"

    # we need this to prevent 'getattr()' is None
    menu_idname: bpy.props.StringProperty(
        name="Menu ID Name",
        description="ID name of the menu this was called from",
        options={'SKIP_SAVE', 'HIDDEN'},
        default='ZUV_MT_StoreFavPresetsUV'
    )


class ZUV_OT_FavExecutePreset3D(ZUV_OT_FavExecutePresetBase):
    bl_idname = "wm.zuv_fav_execute_preset_3d"

    # we need this to prevent 'getattr()' is None
    menu_idname: bpy.props.StringProperty(
        name="Menu ID Name",
        description="ID name of the menu this was called from",
        options={'SKIP_SAVE', 'HIDDEN'},
        default='ZUV_MT_StoreFavPresets3D'
    )


def zenuv_draw_favourite_presets(self: bpy.types.Menu, s_panel_mode: str, context: bpy.types.Context):
    layout = self.layout

    row = layout.row(align=True)
    op = row.operator("wm.zenuv_presets_load_default", icon='IMPORT')
    op.preset_folder = FAV_PRESET_SUBDIR + s_panel_mode

    layout.separator()

    bpy.types.Menu.draw_preset(self, context)


class ZUV_MT_StoreFavPresets3D(bpy.types.Menu):
    bl_label = 'Favourite Presets 3D *'
    bl_description = "A list of available presets. Selected preset will override the included properties"

    default_label = 'Favourite Presets 3D *'

    preset_subdir = ZuvPresets.get_preset_path(FAV_PRESET_SUBDIR + 'view_3d')
    preset_operator = 'wm.zuv_fav_execute_preset_3d'

    def draw(self, context: bpy.types.Context):
        zenuv_draw_favourite_presets(self, "view_3d", context)


class ZUV_MT_StoreFavPresetsUV(bpy.types.Menu):
    bl_label = 'Favourite Presets UV *'
    bl_description = "A list of available presets. Selected preset will override the included properties"

    default_label = 'Favourite Presets UV *'

    preset_subdir = ZuvPresets.get_preset_path(FAV_PRESET_SUBDIR + 'uv')
    preset_operator = 'wm.zuv_fav_execute_preset_uv'

    def draw(self, context: bpy.types.Context):
        zenuv_draw_favourite_presets(self, "uv", context)


class ZUV_OT_FavAddPreset(AddPresetBase, bpy.types.Operator):
    bl_idname = 'wm.zuv_fav_add_preset'
    bl_label = 'Add|Remove Preset'
    preset_menu = 'ZUV_MT_StoreFavPresets'

    @classmethod
    def description(cls, context, properties):
        if properties:
            return ('Remove' if properties.remove_active else 'Add') + ' favourite preset'
        else:
            return cls.bl_description

    panel_mode: bpy.props.EnumProperty(
        name='Panel Mode',
        items=[
            ('UV', 'UV', 'UV Editor'),
            ('VIEW_3D', 'VIEW_3D', 'View 3D'),
        ],
        default='UV',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def get_panel_mode_ui(self):
        return self.panel_mode

    panel_mode_ui: bpy.props.StringProperty(
        name='Panel Mode',
        get=get_panel_mode_ui,
        options={'SKIP_SAVE'}
    )

    # Common variable used for all preset values
    preset_defines = [
        'prefs = bpy.context.preferences.addons["ZenUV"].preferences.favourite_props_'
    ]

    # Properties to store in the preset
    preset_values = [
        'prefs.favourites',
        'prefs.favourite_index',
        'prefs.expanded',
        'prefs.show_header',
        'prefs.header_expanded',
    ]

    # Directory to store the presets
    preset_subdir = ZuvPresets.get_preset_path(FAV_PRESET_SUBDIR)

    def execute(self, context: bpy.types.Context):
        import os
        from bpy.utils import is_path_builtin

        if hasattr(self, "pre_cb"):
            self.pre_cb(context)

        s_menu = self.preset_menu + ('UV' if self.panel_mode == 'UV' else '3D')

        preset_menu_class = getattr(bpy.types, s_menu)

        is_xml = getattr(preset_menu_class, "preset_type", None) == 'XML'
        is_preset_add = not (self.remove_name or self.remove_active)

        if is_xml:
            ext = ".xml"
        else:
            ext = ".py"

        name = self.name.strip() if is_preset_add else self.name

        if is_preset_add:
            if not name:
                self.report({'WARNING'}, 'Preset name is empty!')
                return {'FINISHED'}

            # Reset preset name
            wm = bpy.data.window_managers[0]
            if name == wm.preset_name:
                wm.preset_name = 'New Preset'

            filename = self.as_filename(name)

            target_path = os.path.join("presets", self.preset_subdir + self.panel_mode.lower())
            target_path = bpy.utils.user_resource('SCRIPTS', path=target_path, create=True)

            if not target_path:
                self.report({'WARNING'}, "Failed to create presets path")
                return {'CANCELLED'}

            filepath = os.path.join(target_path, filename) + ext

            if hasattr(self, "add"):
                self.add(context, filepath)
            else:
                print("Writing Preset: %r" % filepath)

                if is_xml:
                    import rna_xml
                    rna_xml.xml_file_write(context,
                                           filepath,
                                           preset_menu_class.preset_xml_map)
                else:

                    def rna_recursive_attr_expand(value, rna_path_step, level):
                        if isinstance(value, bpy.types.PropertyGroup):
                            for sub_value_attr, sub_value_prop in value.bl_rna.properties.items():
                                if sub_value_attr == "rna_type":
                                    continue
                                if sub_value_prop.is_skip_save:
                                    continue
                                sub_value = getattr(value, sub_value_attr)
                                rna_recursive_attr_expand(sub_value, "%s.%s" % (rna_path_step, sub_value_attr), level)
                        elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
                            file_preset.write("%s.clear()\n" % rna_path_step)
                            for sub_value in value:
                                file_preset.write("\n")
                                file_preset.write("item_sub_%d = %s.add()\n" % (level, rna_path_step))
                                rna_recursive_attr_expand(sub_value, "item_sub_%d" % level, level + 1)
                            if len(value) > 0:
                                file_preset.write("\n")
                        else:
                            # convert thin wrapped sequences
                            # to simple lists to repr()
                            try:
                                value = value[:]
                            except Exception:
                                pass

                            file_preset.write("%s = %r\n" % (rna_path_step, value))

                    file_preset = open(filepath, 'w', encoding="utf-8")
                    file_preset.write("import bpy\n")

                    if hasattr(self, "preset_defines"):
                        for prefix_rna_path in self.preset_defines:
                            rna_path = prefix_rna_path + self.panel_mode
                            exec(rna_path)
                            file_preset.write("%s\n" % rna_path)
                        file_preset.write("\n")

                    for rna_path in self.preset_values:
                        value = eval(rna_path)
                        rna_recursive_attr_expand(value, rna_path, 1)

                    file_preset.close()

            preset_menu_class.bl_label = Path(filename).stem

        else:
            if self.remove_active:
                name = preset_menu_class.bl_label

            # fairly sloppy but convenient.
            filepath = bpy.utils.preset_find(name,
                                             self.preset_subdir + self.panel_mode.lower(),
                                             ext=ext)

            if not filepath:
                filepath = bpy.utils.preset_find(name,
                                                 self.preset_subdir + self.panel_mode.lower(),
                                                 display_name=True,
                                                 ext=ext)

            if not filepath:
                self.report({'WARNING'}, f'Preset: {name} - not found!')
                return {'CANCELLED'}

            # Do not remove bundled presets
            if is_path_builtin(filepath):
                self.report({'WARNING'}, "Unable to remove default presets")
                return {'CANCELLED'}

            try:
                if hasattr(self, "remove"):
                    self.remove(context, filepath)
                else:
                    os.remove(filepath)
            except Exception as e:
                self.report({'ERROR'}, tip_("Unable to remove preset: %r") % e)
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

            preset_menu_class.bl_label = preset_menu_class.default_label

        if hasattr(self, "post_cb"):
            self.post_cb(context)

        context.area.tag_redraw()

        return {'FINISHED'}


class ZUV_OT_FavSelectIcon(bpy.types.Operator):
    bl_idname = 'wm.zuv_fav_select_icon'
    bl_label = 'Select Icon'
    bl_description = "Select icon from the list of available icons"
    bl_options = {'INTERNAL'}
    bl_property = 'icons'

    def get_icons(self, context: bpy.types.Context):

        p_items = []

        if self.is_icon_value:
            from ZenUV.ico import ZENUV_ICONS
            idx = 0
            for icon_key, icon_value in ZENUV_ICONS.items():
                p_items.append((icon_key, icon_key, '', icon_value.icon_id, idx))
                idx += 1
        else:
            icons = bpy.types.UILayout.bl_rna.functions[
                    "prop"].parameters["icon"].enum_items.keys()
            for idx, icon in enumerate(icons):
                p_items.append((icon, icon, '', icon, idx))

        s_id = "ZUV_OT_FavSelectIcon_ICONS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])
        if p_was_items != p_items:
            bpy.app.driver_namespace[s_id] = p_items

        return bpy.app.driver_namespace.get(s_id, [])

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default=''
    )

    icons: bpy.props.EnumProperty(
        name='Icons',
        items=get_icons,
    )

    is_icon_value: bpy.props.BoolProperty(
        name='Is Icon Value',
        default=False
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context: bpy.types.Context):
        try:
            _set_context_attr(context, self.data_path, self.icons)
            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_FavUpdateName(bpy.types.Operator):
    bl_idname = 'wm.zuv_fav_update_name'
    bl_label = 'Update Name'
    bl_description = "Update name by command value"
    bl_options = {'INTERNAL'}

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    mode: bpy.props.StringProperty(
        name='Mode',
        default=''
    )

    cmd: bpy.props.StringProperty(
        name='Command',
        default=''
    )

    def execute(self, context: bpy.types.Context):
        try:
            b_need_update = False
            s_name = ZUV_FavItem.get_auto_name(self.mode, self.cmd, context)
            if s_name:
                _set_context_attr(context, self.data_path, s_name)
                b_need_update = True

            s_icon, is_icon_value = ZUV_FavItem.get_auto_icon(self.mode, self.cmd, context)
            if s_icon:
                _set_context_attr(context, self.data_path.replace('.name', '.icon'), s_icon)
                _set_context_attr(context, self.data_path.replace('.name', '.is_icon_value'), is_icon_value)

                b_need_update = True

            if b_need_update:
                update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_FavScriptSelect(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.zuv_fav_script_select"
    bl_label = "Select Script"
    bl_description = """Select user script which will be loaded and executed"""
    bl_options = {'INTERNAL'}

    filename_ext = ".py"
    filter_glob: bpy.props.StringProperty(default="*.py", options={'HIDDEN'})

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    def execute(self, context: bpy.types.Context):
        try:
            s_command = f'bpy.ops.script.python_file_run(filepath=r"{self.filepath}")'

            _set_context_attr(context, self.data_path, s_command)
            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_FavEditOperator(bpy.types.Operator):
    bl_idname = 'wm.zuv_fav_edit_operator'
    bl_label = 'Edit Operator'
    bl_description = "Call operator editor menu and edit its props in UI"
    bl_options = {'INTERNAL'}

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    def get_python_command(self):
        s_cmd = ""
        try:
            from ZenUV.ui.keymap_manager import AddonKmiExt
            p_kmi = AddonKmiExt.get_kmi(bpy.context, "ZUV_OT_FavEditOperator")
            s_cmd = p_kmi.idname
            if s_cmd:
                t_values = []
                bl_rna_props = p_kmi.properties.bl_rna.properties
                for k, v in p_kmi.properties.items():
                    p_prop: bpy.types.Property = bl_rna_props[k]
                    if not p_prop.is_skip_save:
                        if isinstance(v, idprop.types.IDPropertyArray):
                            t_values.append(f"{k}={repr(tuple(v.to_list()))}")
                        elif isinstance(v, idprop.types.IDPropertyGroup):
                            t_values.append(f"{k}={repr(v.to_dict())}")
                        else:
                            if isinstance(v, float):
                                t_values.append(f"{k}={v:.6g}")
                            else:
                                t_values.append(f"{k}={repr(getattr(p_kmi.properties, k))}")

                if len(t_values):
                    s_args = ",".join(t_values)
                    s_cmd += f"({s_args})"
        except Exception as e:
            Log.error("Get CMD Fav Edit:", e)
        return s_cmd

    display_cmd: bpy.props.StringProperty(
        name="Python Operator Command",
        description="Python command that will call an operator for execution",
        get=get_python_command
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        from ZenUV.ui.keymap_manager import AddonKmiExt

        row = layout.row(align=True)
        row.use_property_split = True
        row.prop(self, "display_cmd")

        p_kmi = AddonKmiExt.get_kmi(context, "ZUV_OT_FavEditOperator")
        box = layout.box()
        box.template_keymap_item_properties(p_kmi)

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager

        from ZenUV.ui.keymap_manager import AddonKmiExt
        p_kmi = AddonKmiExt.get_kmi(bpy.context, "ZUV_OT_FavEditOperator", is_new=True)
        try:
            from ZenUV.ui.keymap_manager import AddonKmiExt

            cmd = _get_context_attr(context, self.data_path)

            p_kmi = AddonKmiExt.get_kmi(bpy.context, "ZUV_OT_FavEditOperator")
            cmd_props = get_command_props(cmd, use_last_properties=False)
            if cmd_props:
                p_kmi.idname = cmd_props.bl_op_cls.idname() if cmd_props.bl_op_cls else ''
                for k, v in cmd_props.kwargs.items():
                    setattr(p_kmi.properties, k, v)
        except Exception as e:
            Log.error("Set CMD Fav Edit:", e)

        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context: bpy.types.Context):
        try:
            cmd = self.get_python_command()
            _set_context_attr(context, self.data_path, cmd)
            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_FavTextSelect(bpy.types.Operator):
    bl_idname = "wm.zuv_fav_text_select"
    bl_label = "Select Text Block"
    bl_description = """Select user text datablock which will be loaded and executed"""
    bl_options = {'INTERNAL'}

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    def get_script_text_items(self, context: bpy.types.Context):
        items = []
        for text in bpy.data.texts:
            items.append((text.name, text.name, text.name_full))
        return items

    script_text: bpy.props.EnumProperty(
        name='Script Text',
        items=get_script_text_items,
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            s_command = f'bpy.ops.wm.zenuv_text_exec(script="{self.script_text}")'

            _set_context_attr(context, self.data_path, s_command)
            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_FavPanelSelect(bpy.types.Operator):
    bl_idname = "wm.zuv_fav_panel_select"
    bl_label = "Select Panel"
    bl_description = """Select panel which will be added to the favourites"""
    bl_options = {'INTERNAL'}
    bl_property = 'panel_name'

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    panel_space: bpy.props.StringProperty(
        name='Panel Space',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    def get_items(self, context: bpy.types.Context):
        p_items = {}
        for panel in bpy.types.Panel.__subclasses__():
            if self.panel_space:
                s_panel_space = getattr(panel, 'bl_space_type', '')
                if s_panel_space != self.panel_space:
                    continue

            s_panel_class = panel.__name__
            if hasattr(panel, "bl_idname") and panel.bl_idname:
                s_panel_class = panel.bl_idname

            t_caption = [
                s_panel_class
            ]
            if panel.bl_label:
                t_caption.insert(0, panel.bl_label)

            s_caption = ' - '.join(t_caption)
            p_items[s_panel_class] = (s_panel_class, s_caption, panel.bl_label)

        s_id = "ZUV_OT_FavPanelSelect_PANEL"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])
        p_new_items = list(p_items.values())
        if p_was_items != p_new_items:
            bpy.app.driver_namespace[s_id] = p_new_items

        return bpy.app.driver_namespace.get(s_id, [])

    panel_name: bpy.props.EnumProperty(
        name='Panel Name',
        items=get_items,
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context: bpy.types.Context):
        try:
            _set_context_attr(context, self.data_path, self.panel_name)

            s_name_path = self.data_path.replace('.command', '.name')
            bpy.ops.wm.zuv_fav_update_name(data_path=s_name_path, mode='PANEL', cmd=self.panel_name)

            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_FavMenuSelect(bpy.types.Operator):
    bl_idname = "wm.zuv_fav_menu_select"
    bl_label = "Select Menu"
    bl_description = """Select menu which will be added to the favourites"""
    bl_options = {'INTERNAL'}
    bl_property = 'menu_name'

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    menu_space: bpy.props.StringProperty(
        name='Menu Space',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    def get_items(self, context: bpy.types.Context):
        p_items = {}
        for menu in bpy.types.Menu.__subclasses__():

            s_menu_class = menu.__name__
            if hasattr(menu, "bl_idname") and menu.bl_idname:
                s_menu_class = menu.bl_idname

            if self.menu_space:
                if not s_menu_class.startswith(f'{self.menu_space}_MT_'):
                    continue

            t_caption = [
                s_menu_class
            ]
            if menu.bl_label:
                t_caption.insert(0, menu.bl_label)

            s_caption = ' - '.join(t_caption)
            p_items[s_menu_class] = (s_menu_class, s_caption, menu.bl_label)

        s_id = "ZUV_OT_FavMenuSelect_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])
        p_new_items = list(p_items.values())
        if p_was_items != p_new_items:
            bpy.app.driver_namespace[s_id] = p_new_items

        return bpy.app.driver_namespace.get(s_id, [])

    menu_name: bpy.props.EnumProperty(
        name='Panel Name',
        items=get_items,
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context: bpy.types.Context):
        try:
            _set_context_attr(context, self.data_path, self.menu_name)

            s_name_path = self.data_path.replace('.command', '.name')
            bpy.ops.wm.zuv_fav_update_name(data_path=s_name_path, mode='PANEL', cmd=self.menu_name)

            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_FavOperatorSelect(bpy.types.Operator):
    bl_idname = "wm.zuv_fav_operator_select"
    bl_label = "Select Operator"
    bl_description = """Select operator which will be added to the favourites"""
    bl_options = {'INTERNAL'}
    bl_property = 'operator_name'

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    operator_space: bpy.props.StringProperty(
        name='Operator Space',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    def get_items(self, context: bpy.types.Context):
        # NOTE: update only once per session
        s_id = "ZUV_OT_FavOperatorSelect_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])

        if len(p_was_items) == 0:
            p_items = {}

            for operator in dir(bpy.ops):
                submodule = getattr(bpy.ops, operator)
                for sub_operator in dir(submodule):
                    try:
                        op_func = getattr(submodule, sub_operator)

                        p_rna_type = op_func.get_rna_type()

                        s_label = p_rna_type.name
                        bl_id = f"{operator}.{sub_operator}"

                        s_caption = f"{s_label} - {bl_id}"

                        p_items[bl_id] = (bl_id, s_caption, s_label)
                    except Exception:
                        pass

            bpy.app.driver_namespace[s_id] = list(p_items.values())

        return bpy.app.driver_namespace.get(s_id, [])

    operator_name: bpy.props.EnumProperty(
        name='Panel Name',
        items=get_items,
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context: bpy.types.Context):
        try:
            _set_context_attr(context, self.data_path, self.operator_name)

            s_name_path = self.data_path.replace('.command', '.name')
            bpy.ops.wm.zuv_fav_update_name(data_path=s_name_path, mode='OPERATOR', cmd=self.operator_name)

            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_FavPropertySelect(bpy.types.Operator):
    bl_idname = "wm.zuv_fav_property_select"
    bl_label = "Select Property"
    bl_description = """Select property which will be added to the favourites"""
    bl_options = {'INTERNAL'}

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'SKIP_SAVE', 'HIDDEN'}
    )

    context_items = [
        ("active_action", "Action", ""),
        ("active_annotation_layer", "GPencilLayer", ""),
        ("active_bone", "Active Bone", ""),
        ("active_file", "Active File", ""),
        ("active_gpencil_frame", "GPencil Frame", ""),
        ("active_gpencil_layer", "GPencil Layer", ""),
        ("active_node", "Active Node", ""),
        ("active_object", "Active Object", ""),
        ("active_operator", "Active Operator", ""),
        ("active_pose_bone", "Active Pose Bone", ""),
        ("active_sequence_strip", "Sequence", ""),
        ("active_editable_fcurve", "Active FCurve", ""),
        ("active_nla_strip", "NlaStrip", ""),
        ("active_nla_track", "NlaTrack", ""),
        ("annotation_data", "Grease Pencil", ""),
        ("annotation_data_owner", "Annotation Owner", ""),
        ("armature", "Armature", ""),
        ("asset_library_ref", "Asset Library Reference", ""),
        ("bone", "Bone", ""),
        ("brush", "Brush", ""),
        ("camera", "Camera", ""),
        ("cloth", "Cloth Modifier", ""),
        ("collection", "Layer Collection", ""),
        ("collision", "Collision Modifier", ""),
        ("curve", "Curve", ""),
        ("dynamic_paint", "Dynamic Paint Modifier", ""),
        ("edit_bone", "Edit Bone", ""),
        ("edit_image", "Image", ""),
        ("edit_mask", "Mask", ""),
        ("edit_movieclip", "Movie Clip", ""),
        ("edit_object", "Edit Object", ""),
        ("edit_text", "Text", ""),
        ("editable_bones", "Editable Bones", ""),
        ("editable_gpencil_layers", "Editable GPencil Layers", ""),
        ("editable_gpencil_strokes", "Editable GPencil Strokes", ""),
        ("editable_objects", "Editable Objects", ""),
        ("editable_fcurves", "Editable FCurves", ""),
        ("fluid", "Fluid Simulation Modifier", ""),
        ("gpencil", "Grease Pencil", ""),
        ("gpencil_data", "Grease Pencil Data", ""),
        ("grease_pencil", "Grease Pencil V3", ""),
        ("gpencil_data_owner", "Gpencil Data Owner", ""),
        ("curves", "Hair Curves", ""),
        ("id", "ID", ""),
        ("image_paint_object", "Image Paint Object", ""),
        ("lattice", "Lattice", ""),
        ("light", "Light", ""),
        ("lightprobe", "Light Probe", ""),
        ("line_style", "Freestyle Line Style", ""),
        ("material", "Material", ""),
        ("material_slot", "MaterialSlot", ""),
        ("mesh", "Mesh", ""),
        ("meta_ball", "MetaBall", ""),
        ("object", "Object", ""),
        ("objects_in_mode", "Objects In Mode", ""),
        ("objects_in_mode_unique_data", "Object In Mode Unique Data", ""),
        ("particle_edit_object", "Particle Object", ""),
        ("particle_settings", "Particle Settings", ""),
        ("particle_system", "Particle System", ""),
        ("particle_system_editable", "Particle Editable System", ""),
        ("pointcloud", "Point Cloud", ""),
        ("pose_bone", "Pose Bone", ""),
        ("pose_object", "Pose Object", ""),
        ("scene", "Scene", ""),
        ("sculpt_object", "Sculpt Object", ""),
        ("selectable_objects", "Selectable Objects", ""),
        ("selected_asset_files", "Selected Asset Files", ""),
        ("selected_bones", "Selected Bones", ""),
        ("selected_editable_actions", "Selected Editable Actions", ""),
        ("selected_editable_bones", "Selected Editable Bones", ""),
        ("selected_editable_fcurves", "Selected Editable Curves", ""),
        ("selected_editable_keyframes", "Selected Editable Keyframes", ""),
        ("selected_editable_objects", "Selected Editable Objects", ""),
        ("selected_editable_sequences", "Selected Editable Sequences", ""),
        ("selected_files", "Selected Files", ""),
        ("selected_ids", "Selected IDs", ""),
        ("selected_nla_strips", "Selected Nla Strips", ""),
        ("selected_movieclip_tracks", "Selected Movie Tracking Tracks", ""),
        ("selected_nodes", "Selected Nodes", ""),
        ("selected_objects", "Selected Objects", ""),
        ("selected_pose_bones", "Selected Pose Bones", ""),
        ("selected_pose_bones_from_active_object", "Selected Pose Bones from Active Object", ""),
        ("selected_sequences", "Selected Sequences", ""),
        ("selected_visible_actions", "Selected Visible Actions", ""),
        ("selected_visible_fcurves", "Selected Visible Curves", ""),
        ("sequences", "Sequences", ""),
        ("soft_body", "Soft Body Modifier", ""),
        ("speaker", "Speaker", ""),
        ("region_data", "Region Data", ""),
        ("space_data", "Space Data", ""),
        ("texture", "Texture", ""),
        ("texture_slot", "Texture Slot", ""),
        ("texture_user", "Texture User", ""),
        ("texture_user_property", "Texture User Property", ""),
        ("tool_settings", "Tool Settings", ""),
        ("ui_list", "UIList", ""),
        ("vertex_paint_object", "Vertex Paint Object", ""),
        ("view_layer", "View Layer", ""),
        ("visible_bones", "Visible Bones", ""),
        ("visible_gpencil_layers", "Visible GPencil Layers", ""),
        ("visible_objects", "Visible Objects", ""),
        ("visible_pose_bones", "Visible Pose Bones", ""),
        ("visible_fcurves", "Visible Curves", ""),
        ("weight_paint_object", "Weight Paint Object", ""),
        ("volume", "Volume", ""),
        ("world", "World", ""),
        ("workspace", "Workspace", ""),
        ("window", "Window", ""),
        ("window_manager", "Window Manager", ""),
    ]

    def get_prop_instance_items(self, context):
        p_items = [
            ('ZENUV', 'Zen UV Properties', "")
        ]

        for p_item in ZUV_OT_FavPropertySelect.context_items:
            if hasattr(context, p_item[0]):
                p_instance = getattr(context, p_item[0])
                if p_instance:
                    if hasattr(p_instance, 'bl_rna'):
                        p_items.append((p_item[0], p_item[0], p_item[1]))

        s_id = "ZUV_OT_FavPropertySelect_PROP_INSTANCE_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])

        if p_was_items != p_items:
            bpy.app.driver_namespace[s_id] = p_items

        return bpy.app.driver_namespace.get(s_id, [])

    property_instance: bpy.props.EnumProperty(
        name='Property Instance',
        items=get_prop_instance_items
    )

    def get_items(self, context: bpy.types.Context):
        p_items = []
        if self.property_instance == 'ZENUV':
            from ZenUV.prop.zuv_preferences import get_prefs
            p_instance = get_prefs()
        else:
            p_instance = getattr(context, self.property_instance, None)
        if p_instance:
            if hasattr(p_instance, 'bl_rna'):
                for k, v in p_instance.bl_rna.properties.items():
                    if k != 'rna_type' and not v.is_hidden:
                        p_items.append((k, v.name if v.name else k, ""))

        s_id = "ZUV_OT_FavPropertySelect_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])

        if p_was_items != p_items:
            bpy.app.driver_namespace[s_id] = p_items

        return bpy.app.driver_namespace.get(s_id, [])

    property_list: bpy.props.EnumProperty(
        name='Property List',
        items=get_items,
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            s_prop_instance = self.property_instance
            if s_prop_instance == 'ZENUV':
                s_prop_instance = 'preferences.addons["ZenUV"].preferences'

            s_command = f'{s_prop_instance}.{self.property_list}'
            _set_context_attr(context, self.data_path, s_command)

            s_name_path = self.data_path.replace('.command', '.name')
            bpy.ops.wm.zuv_fav_update_name(data_path=s_name_path, mode='PROPERTY', cmd=s_command)

            update_areas_in_all_screens(context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_FavDuplicateItem3D(bpy.types.Operator):
    bl_idname = "view3d.zuv_fav_duplicate_item"
    bl_label = 'Duplicate'
    bl_description = 'Duplicate active favourite item'
    bl_options = {'REGISTER'}

    panel_mode = 'VIEW_3D'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_fav_props = ZUV_FavProps.get_fav_props(cls.panel_mode)
        return p_fav_props.favourite_index in range(len(p_fav_props.favourites))

    def execute(self, context: bpy.types.Context):
        p_fav_props = ZUV_FavProps.get_fav_props(self.panel_mode)
        if p_fav_props.favourite_index in range(len(p_fav_props.favourites)):
            p_was_fav_item: ZUV_FavItem = p_fav_props.favourites[p_fav_props.favourite_index]
            bpy.ops.zenuvlist.entry_add(
                list_path=f"preferences.addons['ZenUV'].preferences.favourite_props_{self.panel_mode}.favourites",
                active_index_path=f"preferences.addons['ZenUV'].preferences.favourite_props_{self.panel_mode}.favourite_index",
                new_name_attr="name", new_name_val="Item")

            p_new_fav_item: ZUV_FavItem = p_fav_props.favourites[p_fav_props.favourite_index]

            for k, v in p_new_fav_item.bl_rna.properties.items():
                if not v.is_skip_save:
                    p_val = getattr(p_new_fav_item, k)
                    p_dupli_val = getattr(p_was_fav_item, k)
                    if p_val != p_dupli_val:
                        setattr(p_new_fav_item, k, p_dupli_val)

        context.preferences.is_dirty = True

        update_areas_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OT_FavDuplicateItemUV(bpy.types.Operator):
    bl_idname = "uv.zuv_fav_duplicate_item"
    bl_label = ZUV_OT_FavDuplicateItem3D.bl_label
    bl_description = ZUV_OT_FavDuplicateItem3D.bl_description
    bl_options = {'REGISTER'}

    panel_mode = 'UV'

    poll = ZUV_OT_FavDuplicateItem3D.poll

    execute = ZUV_OT_FavDuplicateItem3D.execute


class ZUV_MT_FavCommandMenu3D(bpy.types.Menu):
    bl_label = 'Command Menu 3D'

    def draw(self, context: bpy.types.Context):

        s_panel_mode = 'UV' if self.bl_idname == 'ZUV_MT_FavCommandMenuUV' else 'VIEW_3D'
        s_panel_space = 'IMAGE_EDITOR' if self.bl_idname == 'ZUV_MT_FavCommandMenuUV' else 'VIEW_3D'
        s_panel_mode_decorative = 'UV' if self.bl_idname == 'ZUV_MT_FavCommandMenuUV' else 'View 3D'
        s_menu_space = 'IMAGE' if self.bl_idname == 'ZUV_MT_FavCommandMenuUV' else 'VIEW3D'

        from ZenUV.prop.zuv_preferences import get_prefs

        addon_prefs = get_prefs()
        p_fav_props: ZUV_FavProps = getattr(addon_prefs, f'favourite_props_{s_panel_mode}')
        if p_fav_props.favourite_index in range(len(p_fav_props.favourites)):
            layout = self.layout

            p_fav_item: ZUV_FavItem = p_fav_props.favourites[p_fav_props.favourite_index]
            if p_fav_item.mode == 'OPERATOR':
                op = layout.operator("wm.zuv_fav_operator_select", text='Select Operator')
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'
                op.operator_space = ''

                layout.separator()

                op = layout.operator("wm.zuv_fav_script_select")
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'

                op = layout.operator("wm.zuv_fav_text_select")
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'
            elif p_fav_item.mode == 'PANEL':
                op = layout.operator("wm.zuv_fav_panel_select", text=f'Select Panel - {s_panel_mode_decorative}')
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'
                op.panel_space = s_panel_space

                op = layout.operator("wm.zuv_fav_panel_select", text='Select Panel - ALL')
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'
                op.panel_space = ''

                layout.separator()

                op = layout.operator("wm.zuv_fav_menu_select", text=f'Select Menu - {s_panel_mode_decorative}')
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'
                op.menu_space = s_menu_space

                op = layout.operator("wm.zuv_fav_menu_select", text='Select Menu - ALL')
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'
                op.menu_space = ''
            elif p_fav_item.mode == 'PROPERTY':
                op = layout.operator("wm.zuv_fav_property_select")
                op.data_path = f'preferences.addons["ZenUV"].preferences.favourite_props_{s_panel_mode}.favourites[{p_fav_props.favourite_index}].command'


class ZUV_MT_FavCommandMenuUV(bpy.types.Menu):
    bl_label = 'Command Menu UV'

    draw = ZUV_MT_FavCommandMenu3D.draw
