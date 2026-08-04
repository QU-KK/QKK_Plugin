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

""" Zen UV Main Panel controls """
import bpy

from ZenUV.ico import icon_get
from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.generic import (
    ZUV_PANEL_CATEGORY, ZUV_REGION_TYPE,
    ZUV_SPACE_TYPE, ZenKeyEventSolver)
from ZenUV.prop.zuv_preferences import (
    draw_panels_enabler, get_prefs, get_addon_version)
from ZenUV.prop.common import uv_enblr, get_combo_panel_order
from ZenUV.ui.panel_draws import draw_unwrap

from ZenUV.ops.transform_sys.tr_ui import draw_transform_panel
from ZenUV.utils.clib.lib_init import StackSolver, get_zenlib_version, is_zenlib_present
from ZenUV.utils.blender_zen_utils import ZenPolls


class ZUV_PT_3DV_Transform(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_idname = "ZUV_PT_3DV_Transform"
    bl_label = ZuvLabels.PANEL_TRANSFORM_LABEL
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_3DV_Transform')
    # bl_options = {'DEFAULT_CLOSED'}

    zen_icon_value = 'pn_Transform'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_transform and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit Mode'

    def draw(self, context):
        draw_transform_panel(self, context)


class DATA_PT_Panels_Switch(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Panels"
    bl_parent_id = "ZUV_PT_Preferences"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "DATA_PT_Panels_Switch"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        draw_panels_enabler(context, layout, "VIEW_3D")

    @classmethod
    def combo_draw(cls, layout: bpy.types.UILayout, context: bpy.types.Context):
        draw_panels_enabler(context, layout, "VIEW_3D", is_combo=True)


def draw_display_panel(self, context: bpy.types.Context):
    ''' @Draw Display Panel '''
    addon_prefs = get_prefs()
    layout: bpy.types.UILayout = self.layout

    col = layout.column()
    # NOTE: we need to force disable property split !
    col.use_property_split = False

    box = col.box()
    box.use_property_split = True
    box.prop(addon_prefs, "n_panel_name")

    box = col.box()
    box.prop(addon_prefs, "pie_assist")
    box.prop(addon_prefs, "use_progress_bar")
    box.prop(addon_prefs, "show_ui_button", text="Sticky UV Editor Button")
    box.prop(addon_prefs, 'right_menu_assist')
    box.prop(addon_prefs, "show_uv_zen_sync")

    box = col.box()
    box.prop(addon_prefs, "show_uv_tool_transform_gizmo_button")
    box.prop(addon_prefs, "show_uv_tool_transform_adjust_header")

    box = col.box()
    box.prop(addon_prefs, "hops_uv_activate")
    row = box.row()
    row.enabled = addon_prefs.hops_uv_activate
    row.prop(addon_prefs, "hops_uv_context")

    box = col.box()
    box.prop(addon_prefs, 'autoFitUV')

    box = col.box()
    box.prop(context.scene.zen_uv, 'is_show_ops_annotations')


class DATA_PT_ZDisplay(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Display"
    bl_parent_id = "ZUV_PT_Preferences"
    bl_region_type = ZUV_REGION_TYPE
    bl_idname = "DATA_PT_ZDisplay"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        draw_display_panel(self, context)


class ZUV_PT_3DV_SubFavourites(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_label = "Favourites"
    bl_parent_id = "ZUV_PT_Preferences"
    bl_region_type = ZUV_REGION_TYPE
    bl_options = {'DEFAULT_CLOSED'}
    bl_ui_units_x = 16

    @classmethod
    def get_icon(cls):
        return 'FUND'

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout
        layout.label(text='3D Viewport')
        layout.separator()

    def draw(self, context: bpy.types.Context):
        addon_prefs = get_prefs()
        addon_prefs.favourite_props_VIEW_3D.draw('VIEW_3D', self.layout, context)


class ZUV_PT_ZenCore(bpy.types.Panel):
    """ Internal Popover Zen UV Core """
    """ We suppose this class is used only when lib is not installed """
    bl_idname = "ZUV_PT_ZenCore"
    bl_label = ZuvLabels.PANEL_CLIB_LABEL
    bl_context = "mesh_edit"  # requires Valerii CHECK !
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'

    def draw(self, context):
        # addon_prefs = get_prefs()
        layout = self.layout

        col = layout.column(align=True)

        b_is_zenlib_present = is_zenlib_present()

        row = col.row(align=True)
        row.label(text=ZuvLabels.CLIB_NAME + (": not installed" if not b_is_zenlib_present else ": not registered"))

        row = col.row(align=True)
        s_label = ("Register " if b_is_zenlib_present else "Install ") + ZuvLabels.CLIB_NAME
        row.operator("view3d.zenuv_install_library", text=s_label)


class ZUV_PT_Help(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_idname = "ZUV_PT_Help"
    bl_label = ZuvLabels.PANEL_HELP_LABEL
    bl_context = ""
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_Help')
    # bl_options = {'DEFAULT_CLOSED'}

    zen_icon_value = 'pn_Help'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_help and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context):
        return context.mode in {'EDIT_MESH', 'OBJECT'}

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit and Object Modes'

    def draw(self, context):
        layout = self.layout

        addon_prefs = get_prefs()
        addon_prefs.draw_help_section(layout, context)

        col = layout.column(align=True)

        try:
            row = col.row(align=True)
            # TODO: decide what is better
            if True:
                row.label(text='Version: ' + get_addon_version())
            else:
                row.alignment = 'LEFT'
                row.label(text='Version:')
                r2 = row.row(align=False)
                r2.ui_units_x = 3
                s_version = get_addon_version()
                op = r2.operator('wm.zenuv_show_addon_version_info', text=s_version)
                op.is_silent = True
                op.version = s_version
        except Exception:
            print('Zen UV: No version found. There may be several versions installed. Try uninstalling everything and installing the latest version.')

        row = col.row(align=True)

        if not StackSolver():
            row.alert = True
            row.label(text='Core Library' + (": not installed" if not is_zenlib_present() else ": not registered"))
        else:
            result = get_zenlib_version()
            row.label(text='Core: ({}, {}, {})'.format(result[0], result[1], result[2]))
        row.alert = False
        row.operator("ops.zenuv_show_prefs", text="", icon="PREFERENCES").tabs = "MODULES"

        addon_prefs = get_prefs()
        box = layout.box()
        addon_prefs.demo.draw(box, context)


class ZUV_PT_UVL_Help(bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_idname = "ZUV_PT_UVL_Help"
    bl_label = ZuvLabels.PANEL_HELP_LABEL
    bl_context = ""
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('UV', 'ZUV_PT_UVL_Help')

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_UV_panels.enable_pt_help and cls.combo_poll(context)

    get_icon = ZUV_PT_Help.get_icon

    combo_poll = ZUV_PT_Help.combo_poll

    poll_reason = ZUV_PT_Help.poll_reason

    draw = ZUV_PT_Help.draw


class ZUV_PT_3DV_Favourites(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_idname = "ZUV_PT_3DV_Favourites"
    bl_label = ZuvLabels.PANEL_FAVOURITES
    bl_context = ""
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_3DV_Favourites')

    zen_icon = 'FUND'

    @classmethod
    def get_icon(cls):
        return cls.zen_icon

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_favourites and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context):
        return context.mode in {'EDIT_MESH', 'OBJECT'}

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit and Object Modes'

    def draw_header(self, context: bpy.types.Context):
        layout = self.layout
        addon_prefs = get_prefs()
        panel_mode = addon_prefs.t_CONTEXT_PANEL_MAP.get(self.bl_space_type)
        p_fav_props = getattr(addon_prefs, f'favourite_props_{panel_mode}')
        p_fav_props.draw_panel_header(panel_mode, layout, context)

    def draw(self, context):
        layout = self.layout

        addon_prefs = get_prefs()
        panel_mode = addon_prefs.t_CONTEXT_PANEL_MAP.get(self.bl_space_type)
        p_fav_props = getattr(addon_prefs, f'favourite_props_{panel_mode}')
        p_fav_props.draw_ui(panel_mode, layout, context, False)


class ZUV_PT_UVL_Favourites(bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_idname = "ZUV_PT_UVL_Favourites"
    bl_label = ZUV_PT_3DV_Favourites.bl_label
    bl_context = ""
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('UV', 'ZUV_PT_UVL_Favourites')

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_UV_panels.enable_pt_favourites and cls.combo_poll(context)

    get_icon = ZUV_PT_3DV_Favourites.get_icon

    combo_poll = ZUV_PT_3DV_Favourites.combo_poll

    poll_reason = ZUV_PT_3DV_Favourites.poll_reason

    draw_header = ZUV_PT_3DV_Favourites.draw_header

    draw = ZUV_PT_3DV_Favourites.draw


class ZUV_PT_Unwrap(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_idname = "ZUV_PT_Unwrap"
    bl_label = ZuvLabels.PANEL_UNWRAP_LABEL
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_Unwrap')

    zen_icon_value = 'pn_Unwrap'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return addon_prefs.float_VIEW_3D_panels.enable_pt_unwrap and cls.combo_poll(context)

    @classmethod
    def combo_poll(cls, context):
        return context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit Mode'

    def draw(self, context):
        draw_unwrap(self, context)


class ZUV_PT_Preferences(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_idname = "ZUV_PT_Preferences"
    bl_label = ZuvLabels.PANEL_PREFERENCES_LABEL
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    bl_order = get_combo_panel_order('VIEW_3D', 'ZUV_PT_Preferences')

    zen_icon_value = 'pn_Preferences'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        if not cls.combo_poll(context):
            return False

        addon_prefs = get_prefs()
        b_poll = addon_prefs.float_VIEW_3D_panels.enable_pt_preferences and cls.combo_poll(context)
        if not b_poll:
            b_is_any_float = any(
                (val.get('VIEW_3D') is not None and getattr(addon_prefs.float_VIEW_3D_panels, key, False))
                for key, val in uv_enblr.items())
            if not b_is_any_float:
                b_is_any_dock = addon_prefs.dock_VIEW_3D_panels_enabled
                if not b_is_any_dock:
                    return True

        return b_poll

    @classmethod
    def combo_poll(cls, context: bpy.types.Context):
        return context.mode in {'EDIT_MESH', 'OBJECT'}

    @classmethod
    def poll_reason(cls, context: bpy.types.Context):
        return 'Available in Edit and Object Modes'

    @classmethod
    def do_draw(cls, layout: bpy.types.UILayout, context: bpy.types.Context, is_combo=False):
        from .keymap_manager import draw_keymap_controls

        draw_keymap_controls(context, layout)

        layout.operator("zenuv.reset_preferences")
        layout.operator("wm.zenuv_reload_icons")

    def draw(self, context):
        self.do_draw(self.layout, context, is_combo=False)

    @classmethod
    def combo_draw(cls, layout: bpy.types.UILayout, context: bpy.types.Context):
        cls.do_draw(layout, context, is_combo=True)


class ZUV_OT_resetPreferences(bpy.types.Operator):
    """ Reset Zen UV Preferences """
    bl_idname = "zenuv.reset_preferences"
    bl_label = ZuvLabels.RESET_LABEL
    bl_description = ZuvLabels.RESET_DESC
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        is_modifier_right = ZenKeyEventSolver(context, event, get_prefs()).solve()
        # event.alt
        if event.type == "LEFTMOUSE" and is_modifier_right:
            self.register_system_panel()
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text=ZuvLabels.RESET_MES)
        layout.separator()

    def execute(self, context):

        addon_prefs = get_prefs()
        items = addon_prefs.__annotations__.keys()
        for pref in items:
            addon_prefs.property_unset(pref)

        # Reset Angle in Auto Seams Operator props moved to addon preferences.
        # Code below temporarily disabled
        # op = context.window_manager.operator_properties_last('uv.zenuv_auto_mark')
        # if op:
        #     op.angle = 30.03

        return {'FINISHED'}

    def register_system_panel(self):
        from bpy.utils import register_class, unregister_class
        if hasattr(bpy.types, "ZUV_PT_System"):
            unregister_class(bpy.types.ZUV_PT_System)
            unregister_class(bpy.types.ZUV_PT_System_UVL)
            print(" Zen UV: The 'System' panel is unregistered.")
        else:
            register_class(ZUV_PT_System)
            register_class(ZUV_PT_System_UVL)
            print(" Zen UV: The 'System' panel is registered.")

        # if hasattr(bpy.types, bpy.ops.uvpackeroperator.packbtn.idname()):
        from ZenUV.utils.tests.td_tests import ZUV_OT_UnitTestTexelDensity
        from ZenUV.utils.tests.td_tests import register as register_td_tests
        from ZenUV.utils.tests.td_tests import unregister as unregister_td_tests
        if hasattr(bpy.types, ZUV_OT_UnitTestTexelDensity.bl_idname):
            unregister_td_tests()
            print('Operators TD Tests UnRegistered')
        else:
            print('Operators TD Tests Registered')
            register_td_tests()


class ZUV_OT_ReloadIcons(bpy.types.Operator):
    bl_idname = "wm.zenuv_reload_icons"
    bl_label = 'Reload Icons'
    bl_description = 'Reload and check all Zen UV icons and optionally show the preview'
    bl_options = {"REGISTER", "UNDO"}

    show_icons_preview: bpy.props.BoolProperty(
        name="Show Icons Preview",
        description="Show all enabled icons after reload",
        default=True
    )

    def execute(self, context: bpy.types.Context):
        from ..ico import ZENUV_ICONS
        if ZENUV_ICONS is not None:
            v: bpy.types.ImagePreview
            for k, v in ZENUV_ICONS.items():
                if v.icon_id == 0:
                    self.report({'ERROR'}, f"Icon: {k} - has invalid id!")
                if sum(v.icon_size) == 0:
                    self.report({'ERROR'}, f"Icon: {k} - is not loaded properly!")

                v.reload()

            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    area.tag_redraw()

            if self.show_icons_preview:
                def zenuv_icons_check(panel, context: bpy.types.Context):
                    layout: bpy.types.UILayout = panel.layout
                    layout.label(text="Check Zen UV Icons")
                    grid_flow = layout.grid_flow(columns=4)
                    v: bpy.types.ImagePreview
                    for k, v in ZENUV_ICONS.items():
                        row = grid_flow.row(align=True)
                        row.active = v.icon_id != 0 and sum(v.icon_size) > 0
                        row.label(text=k, icon_value=v.icon_id)

                wm = context.window_manager
                wm.popover(zenuv_icons_check, ui_units_x=30)
        else:
            self.report({'ERROR'}, "Zen UV Icon system is broken!")

        return {'FINISHED'}


class ZUV_OT_ShowAddonVersionInfo(bpy.types.Operator):
    bl_idname = "wm.zenuv_show_addon_version_info"
    bl_label = 'Show Zen UV Version Info'
    bl_description = 'Open Zen UV version information from the official website'
    bl_options = {"INTERNAL"}

    is_silent: bpy.props.BoolProperty(
        name='Silent',
        options={'HIDDEN', 'SKIP_SAVE'},
        default=False
    )

    version: bpy.props.StringProperty(
        name='Version',
        options={'HIDDEN', 'SKIP_SAVE'},
        default=''
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self.is_silent:
            return self.execute(context)
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        addon_prefs = get_prefs()
        if self.is_silent:
            pass
        else:
            layout.label(text=f'New Version: {self.version} is available!', icon='ERROR')
            layout.label(text='Visit Blendermarket or Gumroad to update!')

        layout.prop(addon_prefs, 'check_for_updates')

    def execute(self, context):
        try:
            bpy.ops.wm.url_open(url=f'{ZenPolls.doc_url}changelg/release_note_{self.version}/')
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'FINISHED'}


class ZUV_PT_System(bpy.types.Panel):
    bl_space_type = ZUV_SPACE_TYPE
    bl_idname = "ZUV_PT_System"
    bl_label = "System"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        from ZenUV.utils.tests.td_tests import (
            ZUV_OT_DevTestTexelDensity,
            ZUV_OT_UnitTestTexelDensity,
            ZUV_OT_TestPropertiesTexelDensity
        )
        from ZenUV.utils.tests.addon_test import ZUV_OP_GrabCurveToFont
        from ZenUV.zen_checker.check_utils import ZUV_OT_ShowIslandArea

        lt = self.layout
        lt.operator('zenuv_test.test_checking')
        lt.operator("zenuv_test.addon_test")
        lt.operator("zenuv.check_sel_in_sync_states")
        lt.operator("uv.zenuv_debug")
        lt.operator("view3d.zenuv_check_library")
        lt.operator(ZUV_OP_GrabCurveToFont.bl_idname)
        lt.operator(ZUV_OT_ShowIslandArea.bl_idname)

        from ZenUV.zen_checker.check_utils import draw_checker_display_items, t_draw_system_modes
        draw_checker_display_items(lt, context, t_draw_system_modes)

        lt.operator("uv.zenuv_show_sim_index")

        lt.label(text='TD Section')
        box = lt.box()
        col = box.column(align=True)
        col.operator(ZUV_OT_UnitTestTexelDensity.bl_idname)
        col.operator(ZUV_OT_DevTestTexelDensity.bl_idname)
        col.operator(ZUV_OT_TestPropertiesTexelDensity.bl_idname)

        # _lt.prop(context.scene.zen_display, "tagged", toggle=True, icon='HIDE_OFF')


class ZUV_PT_System_UVL(bpy.types.Panel):
    bl_space_type = "IMAGE_EDITOR"
    bl_idname = "ZUV_PT_System_UVL"
    bl_label = "System"
    bl_region_type = ZUV_REGION_TYPE
    bl_category = ZUV_PANEL_CATEGORY
    # bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return True

    def draw(self, context):
        layout = self.layout
        layout.operator("zenuv_test.addon_test")
        layout.operator("zenuv.check_sel_in_sync_states")
        layout.operator("uv.zenuv_debug")
        layout.operator("view3d.zenuv_check_library")

        from ZenUV.zen_checker.check_utils import draw_checker_display_items, t_draw_system_modes
        draw_checker_display_items(layout, context, t_draw_system_modes)

        layout.operator("uv.zenuv_show_sim_index")
        # layout.prop(context.scene.zen_display, "tagged", toggle=True, icon='HIDE_OFF')


main_panel_parented_panels = [
    DATA_PT_Panels_Switch,
    DATA_PT_ZDisplay,
    ZUV_PT_3DV_SubFavourites
]

if __name__ == '__main__':
    pass
