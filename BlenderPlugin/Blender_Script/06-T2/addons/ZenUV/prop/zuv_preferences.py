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

""" Zen UV Addon Properties module """
import os
from timeit import default_timer as timer
import platform

import bpy
import addon_utils
from bpy.types import AddonPreferences
from bpy.props import (
    BoolProperty,
    FloatProperty,
    EnumProperty,
    IntProperty,
    StringProperty,
    FloatVectorProperty,
    PointerProperty
)

from ZenUV.utils.messages import zen_message

from ZenUV.ico import icon_get
from ZenUV.ui.labels import ZuvLabels

from ZenUV.utils.generic import get_padding_in_pct, get_padding_in_px

from ZenUV.ui.keymap_manager import draw_keymaps
from ZenUV.utils.clib.lib_init import (
    StackSolver, get_zenlib_name, get_zenlib_dir,
    get_zenlib_version, is_zenlib_present)

from ZenUV.sticky_uv_editor.stk_uv_props import UVEditorSettings, draw_sticky_editor_settings
from ZenUV.zen_checker.properties import ZUV_CheckerAddonLevelProperties

from ZenUV.ops.zen_unwrap.props import ZUV_ZenUnwrapOpAddonProps
from ZenUV.ops.trimsheets.trimsheet_props import ZuvTrimsheetProps

from ZenUV.ops.trimsheets.trimsheet_labels import TrimSheetLabels as TrsLabels

from ZenUV.utils.blender_zen_utils import (
    ZenPolls,
    update_areas_in_all_screens,
    on_prop_update_uv)
from ZenUV.utils.vlog import Log

from ZenUV.prop.demo_examples import ZUV_DemoExampleProps
from ZenUV.prop.user_script_props import ZUV_UserScriptProps
from ZenUV.prop.td_draw_props import ZUV_TexelDensityDrawProps
from ZenUV.prop.adv_maps_props import ZUV_AdvMapsProps
from ZenUV.prop.uv_borders_draw_props import ZUV_UVBordersDrawProps
from ZenUV.prop.favourites_props import ZUV_FavProps
from ZenUV.prop.world_size_props import ZUV_WorldSizeAddonProps
from ZenUV.prop.uv_transform_tool_props import ZUV_UVTransformToolProps
from ZenUV.prop.addon_op_props import ZUV_AddonOperatorProps


resolutions_x = []
resolutions_y = []
values_x = []
values_y = []


_CACHE_ADDON_VERSION = None


def get_addon_version():
    global _CACHE_ADDON_VERSION
    if _CACHE_ADDON_VERSION is None:
        for addon in addon_utils.modules():
            if addon.bl_info['name'] == 'Zen UV':
                ver = addon.bl_info['version']
                _CACHE_ADDON_VERSION = '%i.%i.%i' % (ver[0], ver[1], ver[2])
                break

    return _CACHE_ADDON_VERSION if _CACHE_ADDON_VERSION else '0.0.0'


def get_name():
    """Get Name"""
    return os.path.basename(get_path())


def get_path():
    """Get the path of Addon"""
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def draw_panels_enabler(context: bpy.types.Context, layout: bpy.types.UILayout, viewport, is_combo=False):
    ''' @Draw Panels Enabler '''
    from .common import uv_enblr

    layout = layout.column(align=True)
    layout.use_property_split = False

    addon_prefs = get_prefs()

    if is_combo:
        op = layout.operator(
            'ops.zenuv_show_prefs',
            text=addon_prefs.bl_rna.properties[f'dock_{viewport}_panels_enabled'].name.replace('Enable', 'Disable'),
            icon='NONE', emboss=True)
        op.tabs = 'PANELS'
        box = layout.box()
        box.use_property_split = True
        box.prop(addon_prefs.combo_panel, 'use_shift_select')
        box.prop(addon_prefs.combo_panel, 'combo_popup_width')
        box.prop(addon_prefs.combo_panel, 'selector_orientation')
        box.prop(addon_prefs.combo_panel, 'selector_header')

        # Temporary
        col = box.column(align=True)
        col.prop(addon_prefs.combo_panel, 'selector_style', expand=True)
    else:
        b1 = layout.box()
        b1.prop(addon_prefs, f'dock_{viewport}_panels_enabled')

    box = layout.box()

    for pref, switch in uv_enblr.items():
        p_type = switch.get(viewport, None)
        b_enabled = p_type is not None
        p_row = box.split(factor=0.5, align=True)
        p_row.enabled = b_enabled

        r1 = p_row.row(align=True)
        r1.alignment = 'LEFT'
        r1.active = getattr(addon_prefs, f'dock_{viewport}_panels_enabled')

        p_float_prop = getattr(addon_prefs, f'float_{viewport}_panels')
        p_prop_name = p_float_prop.bl_rna.properties[pref].name

        if b_enabled:
            p_panel_type = getattr(bpy.types, p_type)
            p_dock_prop = getattr(addon_prefs, f'dock_{viewport}_panels')
            if pref == 'enable_pt_preferences':
                r1.label(text=p_prop_name, icon='LOCKED')
            else:
                r1.prop(p_dock_prop, pref)

            enb = p_row.row(align=True)
            enb.alignment = 'RIGHT'

            if p_panel_type:
                if hasattr(p_panel_type, 'combo_poll'):
                    b_active = p_panel_type.combo_poll(context)
                    p_row.active = b_active

            enb.prop(p_float_prop, pref, text='Floating')
        else:
            r1.label(text=p_prop_name, icon='CHECKBOX_DEHLT')


def draw_alt_commands(self):
    ''' @Draw Pie Alt Commands '''
    box = self.layout.box()
    addon_prefs = self
    box.label(text="Pie Menu commands that will be executed in combination with the SHIFT key.")
    row = box.row(align=True)
    row.prop(addon_prefs, 's8', icon="TRIA_UP")
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's8'
    row = box.row(align=True)
    row.prop(addon_prefs, 's9')
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's9'
    row.enabled = False
    row = box.row(align=True)
    row.prop(addon_prefs, 's6', icon="TRIA_RIGHT")
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's6'
    row = box.row(align=True)
    row.prop(addon_prefs, 's3')
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's3'
    row = box.row(align=True)
    row.prop(addon_prefs, 's2', icon="TRIA_DOWN")
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's2'
    row = box.row(align=True)
    row.prop(addon_prefs, 's1')
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's1'
    row = box.row(align=True)
    row.prop(addon_prefs, 's4', icon="TRIA_LEFT")
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's4'
    row = box.row(align=True)
    row.prop(addon_prefs, 's7')
    row.operator("zenuv.search_operator", icon="COLLAPSEMENU", text="").sector = 's7'


class ZuvPanelEnableGroup(bpy.types.PropertyGroup):

    def get_context(self):
        p_context = self.get('_context', None)
        if p_context is None:

            p_context = {}

            addon_prefs = get_prefs()

            if addon_prefs.dock_UV_panels == self:
                p_context['is_floating'] = False
                p_context['mode'] = 'UV'
            elif addon_prefs.dock_VIEW_3D_panels == self:
                p_context['is_floating'] = False
                p_context['mode'] = 'VIEW_3D'
            elif addon_prefs.float_UV_panels == self:
                p_context['is_floating'] = True
                p_context['mode'] = 'UV'
            elif addon_prefs.float_VIEW_3D_panels == self:
                p_context['is_floating'] = True
                p_context['mode'] = 'VIEW_3D'

            self['_context'] = p_context
        return p_context

    def get_val(self, prop_name):
        from .common import uv_enblr

        p_context = self.get_context()
        b_is_floating = p_context['is_floating']
        s_context_mode = p_context['mode']

        p_default = False if (b_is_floating or prop_name == 'enable_pt_favourites') else uv_enblr[prop_name][s_context_mode] is not None
        if p_default and not b_is_floating:
            if prop_name == 'enable_pt_preferences':
                return True

        return self.get(prop_name, p_default)

    def set_val(self, prop_name, value):
        p_old_val = self.get_val(prop_name)
        if p_old_val != value:
            self[prop_name] = value
            update_areas_in_all_screens(bpy.context)

    enable_pt_adv_uv_map: BoolProperty(
        name=ZuvLabels.PT_ADV_UV_MAPS_LABEL,
        get=lambda self: self.get_val('enable_pt_adv_uv_map'),
        set=lambda self, value: self.set_val('enable_pt_adv_uv_map', value))
    enable_pt_seam_group: BoolProperty(
        name=ZuvLabels.PT_SEAMS_GROUP_LABEL,
        get=lambda self: self.get_val('enable_pt_seam_group'),
        set=lambda self, value: self.set_val('enable_pt_seam_group', value))
    enable_pt_unwrap: BoolProperty(
        name=ZuvLabels.PANEL_UNWRAP_LABEL,
        get=lambda self: self.get_val('enable_pt_unwrap'),
        set=lambda self, value: self.set_val('enable_pt_unwrap', value))
    enable_pt_select: BoolProperty(
        name=ZuvLabels.PANEL_SELECT_LABEL,
        get=lambda self: self.get_val('enable_pt_select'),
        set=lambda self, value: self.set_val('enable_pt_select', value))
    enable_pt_pack: BoolProperty(
        name=ZuvLabels.PANEL_PACK_LABEL,
        get=lambda self: self.get_val('enable_pt_pack'),
        set=lambda self, value: self.set_val('enable_pt_pack', value))
    enable_pt_checker_map: BoolProperty(
        name=ZuvLabels.PANEL_CHECKER_LABEL,
        get=lambda self: self.get_val('enable_pt_checker_map'),
        set=lambda self, value: self.set_val('enable_pt_checker_map', value))
    enable_pt_texel_density: BoolProperty(
        name=ZuvLabels.TEXEL_DENSITY_LABEL,
        get=lambda self: self.get_val('enable_pt_texel_density'),
        set=lambda self, value: self.set_val('enable_pt_texel_density', value))
    enable_pt_transform: BoolProperty(
        name=ZuvLabels.PANEL_TRANSFORM_LABEL,
        get=lambda self: self.get_val('enable_pt_transform'),
        set=lambda self, value: self.set_val('enable_pt_transform', value))
    enable_pt_help: BoolProperty(
        name=ZuvLabels.PANEL_HELP_LABEL,
        get=lambda self: self.get_val('enable_pt_help'),
        set=lambda self, value: self.set_val('enable_pt_help', value))
    enable_pt_stack: BoolProperty(
        name=ZuvLabels.PANEL_STACK_LABEL,
        get=lambda self: self.get_val('enable_pt_stack'),
        set=lambda self, value: self.set_val('enable_pt_stack', value))
    enable_pt_preferences: BoolProperty(
        name=ZuvLabels.PANEL_PREFERENCES_LABEL,
        get=lambda self: self.get_val('enable_pt_preferences'),
        set=lambda self, value: self.set_val('enable_pt_preferences', value))
    enable_pt_trimsheet: BoolProperty(
        name=TrsLabels.PANEL_TRSH_LABEL,
        get=lambda self: self.get_val('enable_pt_trimsheet'),
        set=lambda self, value: self.set_val('enable_pt_trimsheet', value))
    enable_pt_favourites: BoolProperty(
        name=ZuvLabels.PANEL_FAVOURITES,
        get=lambda self: self.get_val('enable_pt_favourites'),
        set=lambda self, value: self.set_val('enable_pt_favourites', value))


class ZuvComboSettings(bpy.types.PropertyGroup):
    def on_prefs_updated(self, context: bpy.types.Context):
        context.preferences.is_dirty = True

    expanded: bpy.props.StringProperty(
        name='Expanded Combo Panels',
        default=''
    )

    pinned: bpy.props.StringProperty(
        name='Pinned Combo Panels',
        default=''
    )

    use_shift_select: bpy.props.BoolProperty(
        name='Multiselect With Shift',
        description='If set multiple docked panels are selected with shift',
        default=True,
        update=on_prefs_updated
    )

    combo_popup_width: bpy.props.IntProperty(
        name='Popup Panel Width',
        description='If set multiple docked panels are selected with shift',
        min=100,
        max=1200,
        subtype='PIXEL',
        default=300,
        update=on_prefs_updated
    )

    combo_VIEW_3D_edit_mode: bpy.props.EnumProperty(
        name='Combo Edit Mode',
        description='Selected panel in view 3d edit mesh combo mode',
        items=[
            ('ZUV_PT_3DV_Favourites', 'Favourites', ''),
            ('DATA_PT_uv_texture_advanced', 'Adv UV Maps', ''),
            ('ZUV_PT_ZenSeamsGroups', 'Seam Groups', ''),
            ('ZUV_PT_Unwrap', 'Unwrap', ''),
            ('ZUV_PT_Select', 'Select', ''),
            ('ZUV_PT_3DV_Transform', 'Transform', ''),
            ('ZUV_PT_3DV_Trimsheet', 'Trimsheet', ''),
            ('ZUV_PT_Stack', 'Stack', ''),
            ('ZUV_PT_Texel_Density', 'Texel Density', ''),
            ('ZUV_PT_Checker', 'UV Checker', ''),
            ('ZUV_PT_Pack', 'Pack', ''),
            ('ZUV_PT_Preferences', 'Preferences', ''),
            ('ZUV_PT_Help', 'Help', '')
        ],
        options={'ENUM_FLAG'},
        default={'DATA_PT_uv_texture_advanced'}
    )

    combo_UV_edit_mode: bpy.props.EnumProperty(
        name='Combo Edit Mode',
        description='Selected panel in view 3d edit mesh combo mode',
        items=[
            ('ZUV_PT_UVL_Favourites', 'Favourites', ''),
            ('DATA_PT_UVL_uv_texture_advanced', 'Adv UV Maps', ''),
            ('ZUV_PT_UVL_Unwrap', 'Unwrap', ''),
            ('ZUV_PT_UVL_Select', 'Select', ''),
            ('ZUV_PT_UVL_Transform', 'Transform', ''),
            ('ZUV_PT_UVL_Trimsheet', 'Trimsheet', ''),
            ('ZUV_PT_UVL_Stack', 'Stack', ''),
            ('ZUV_PT_UVL_Texel_Density', 'Texel Density', ''),
            ('ZUV_PT_Checker_UVL', 'UV Checker', ''),
            ('ZUV_PT_UVL_Pack', 'Pack', ''),
            ('ZUV_PT_UVL_Preferences', 'Preferences', ''),
            ('ZUV_PT_UVL_Help', 'Help', '')
        ],
        options={'ENUM_FLAG'},
        default={'DATA_PT_UVL_uv_texture_advanced'}
    )

    selector_style: bpy.props.EnumProperty(
        name='Selector Style',
        description='Dock panel selector style',
        items=[
            ('NO_BACK', 'No background 1', ''),
            ('NO_BACK_2', 'No background 2', ''),
            ('BL_1', 'Blender Style 1', ''),
            ('BL_2', 'Blender Style 2', ''),
            ('BL_INV_1', 'Blender Invert Style 1', ''),
            ('BL_INV_2', 'Blender Invert Style 2', ''),
        ],
        default='NO_BACK',
        update=on_prefs_updated
    )

    selector_orientation: bpy.props.EnumProperty(
        name='Selector Orientation',
        description='Dock panel selector orientation',
        items=[
            ('VERT', 'Vertical', 'Selector and subpanels are placed vertically'),
            ('HOR', 'Horizontal', 'Selector and subpanels are placed horizontally'),
            ('HOR_MIX', 'Horizontal Mix', 'Selector is placed horizontally, but subpanels are placed vertically')
        ],
        default='VERT',
        update=on_prefs_updated
    )

    selector_header: bpy.props.EnumProperty(
        name='Selector Header',
        description='Dock panel selector header style',
        items=[
            ('AUTO', 'Auto', 'Header style will be selected automatically depending on panel width'),
            ('FIXED', 'Fixed', 'Fixed header style: 1 column or 1 row always'),
        ],
        default='AUTO',
        update=on_prefs_updated
    )


class ZUV_AddonPreferences(AddonPreferences):
    bl_idname = ZenPolls.ADDON_PACKAGE  # "ZenUV"

    t_CONTEXT_PANEL_MAP = {
        "IMAGE_EDITOR": 'UV',
        "VIEW_3D": "VIEW_3D"
    }

    def draw_help_section(self, layout: bpy.types.UILayout, context: bpy.types.Context):
        col = layout.column(align=True)

        col.operator(
            "wm.url_open",
            text=ZuvLabels.PANEL_HELP_DOC_LABEL,
            icon="HELP"
        ).url = ZenPolls.doc_url

        col.operator(
            "wm.url_open",
            text="Support",
            icon='USER'
        ).url = ZenPolls.support_url

        col.operator(
            "wm.url_open",
            text=ZuvLabels.PANEL_HELP_DISCORD_LABEL,
            icon_value=icon_get(ZuvLabels.PANEL_HELP_DISCORD_ICO)
        ).url = ZuvLabels.PANEL_HELP_DISCORD_LINK

        col.operator(
            "wm.url_open",
            text="Patreon",
            icon_value=icon_get("patreon_32")
        ).url = ZenPolls.donate_url

        op = col.operator('wm.url_open', text='Recommended Addons', icon='URL')
        op.url = f"{ZenPolls.doc_url}recommended_addons"

    def draw(self, context):
        layout = self.layout
        self.draw_update_note(layout)

        row = layout.row()
        row.prop(self, "tabs", expand=True)

        if self.tabs == 'KEYMAP':
            layout.prop(self, "zen_key_modifier")

            draw_keymaps(context, layout)

        # if self.tabs == 'PIE_MENU':
        #     draw_alt_commands(self)
        if self.tabs == 'PANELS':
            layout = self.layout

            box = layout.box()
            box.use_property_split = True
            box.prop(self, "n_panel_name")

            pie_box = layout.box()
            pie_box.label(text="Pie Menu: ")
            pie_box.prop(self, "pie_assist")
            pie_box.prop(self, "pie_assist_font_size")

            rmb_box = layout.box()
            rmb_box.prop(self, 'right_menu_assist')
            rmb_box.prop(self, "show_uv_zen_sync")

            box = layout.box()
            box.prop(self, "show_uv_tool_transform_gizmo_button")
            box.prop(self, "show_uv_tool_transform_adjust_header")

            box_adv_maps = layout.box()
            box_adv_maps.label(text=ZuvLabels.PT_ADV_UV_MAPS_LABEL)
            box_adv_maps.prop(self.adv_maps, 'eye_dropper_object_enabled')

            row = layout.row()
            col = row.column()
            title_box = col.box()
            title_box.label(text="UV Editor", icon="UV")
            draw_panels_enabler(context, col, "UV")
            col = row.column()
            title_box = col.box()
            title_box.label(text="3D Viewport", icon="VIEW3D")
            draw_panels_enabler(context, col, "VIEW_3D")

        if self.tabs == 'HELP':
            box = layout.box()

            self.draw_help_section(box, context)

            box = layout.box()
            self.demo.draw(box, context)

        if self.tabs == 'MODULES':
            self.draw_modules_tab(layout)
            self.user_script.draw(layout, context)
        if self.tabs == 'STK_UV_EDITOR':
            draw_sticky_editor_settings(self, context)

        box_products = layout.box()
        box_products.label(text='Zen Add-ons')
        box_products.operator(
            "wm.url_open",
            text=ZuvLabels.PREF_ZEN_SETS_URL_DESC,
            icon_value=icon_get(ZuvLabels.AddonZenSets)
        ).url = ZuvLabels.PREF_ZEN_SETS_URL_LINK
        box_products.operator(
            "wm.url_open",
            text=ZuvLabels.PREF_ZEN_UV_BBQ_URL_DESC,
            icon_value=icon_get(ZuvLabels.AddonZenBBQ)
        ).url = ZuvLabels.PREF_ZEN_UV_BBQ_URL_LINK
        box_products.operator(
            "wm.url_open",
            text=ZuvLabels.PREF_ZEN_UV_CHECKER_URL_DESC,
            icon_value=icon_get(ZuvLabels.AddonZenChecker)
        ).url = ZuvLabels.PREF_ZEN_UV_CHECKER_URL_LINK
        box_products.operator(
            "wm.url_open",
            text=ZuvLabels.PREF_ZEN_UV_TOPMOST_URL_DESC,
            icon='WINDOW',
        ).url = ZuvLabels.PREF_ZEN_UV_TOPMOST_URL_LINK

    def draw_modules_tab(self, layout: bpy.types.UILayout):
        ''' @Draw Prefs Modules Tab '''
        box = layout.box()

        def draw_zenlib_dir_op(layout: bpy.types.UILayout):
            op = layout.operator('wm.path_open', text='', icon='FILEBROWSER')
            op.filepath = get_zenlib_dir()

        if not StackSolver():
            b_is_zenlib_present = is_zenlib_present()
            row = box.row()
            row.alert = True
            row.label(text=ZuvLabels.CLIB_NAME + (": not installed" if not b_is_zenlib_present else ": not registered"))
            draw_zenlib_dir_op(row)
            box.operator(
                    "wm.url_open",
                    text=ZuvLabels.PREF_ZEN_CORE_URL_DESC,

                ).url = ZuvLabels.PREF_ZEN_CORE_URL_LINK

            s_label = ("Register " if b_is_zenlib_present else "Install ") + ZuvLabels.CLIB_NAME
            box.operator("view3d.zenuv_install_library", text=s_label)
        else:
            result = get_zenlib_version()

            row = box.row(align=True)
            row.label(text=ZuvLabels.CLIB_NAME + f": {result[0]}.{result[1]}.{result[2]} ({get_zenlib_name()})" + ' is installed.')
            draw_zenlib_dir_op(row)

            box.operator("uv.zenuv_unregister_library")
            box.label(text=ZuvLabels.UPDATE_WARNING_UNREGISTER)

        box = layout.box()
        from ZenUV.utils.clib.lib_init import get_zen_relax_name
        s_relax_app_name = get_zen_relax_name()
        box.label(text=f'Zen UV Relax Application: {s_relax_app_name}')
        box.prop(self, 'use_relax_in_shell')

        if platform.system() == 'Windows':
            from ZenUV.ops.auto_uv_unwrap import MinistryOfFlatData, ZUV_OT_AutoUVUnwrap, ZUV_OT_AutoUVUnwrapInstall
            box = layout.box()
            b_is_installed = os.path.exists(ZUV_OT_AutoUVUnwrap.get_unwrapper_file_path())
            s_status = "installed" if b_is_installed else "not installed"
            row = box.row(align=True)

            r1 = row.row(align=True)
            r1.enabled = b_is_installed
            r1.label(text=f'The Ministry Of Flat Auto UV Unwrapper is {s_status}')

            row.operator(
                ZUV_OT_AutoUVUnwrapInstall.bl_idname,
                icon='IMPORT' if ZenPolls.internet_enabled() else 'INTERNET_OFFLINE',
                text='')

            row.separator()

            r1 = row.row(align=True)
            r1.enabled = b_is_installed
            op = r1.operator('wm.path_open', text='', icon='FILEBROWSER')
            op.filepath = os.path.dirname(ZUV_OT_AutoUVUnwrap.get_unwrapper_file_path())

            row = box.row(align=True)
            row.label(text=f"Author: {MinistryOfFlatData.MINISTRY_OF_FLAT_AUTHOR}")
            op = row.operator("wm.url_open", text=MinistryOfFlatData.MINISTRY_OF_FLAT_TEXT)
            op.url = MinistryOfFlatData.URL_MINISTRY_OF_FLAT

    def draw_update_note(self, layout: bpy.types.UILayout):
        ''' @Draw Prefs Update Note '''
        upd_box = layout.box()
        # col.label(text=ZuvLabels.UPDATE_MESSAGE_SHORT)
        if StackSolver():
            # col = upd_box.column()
            # col.alert = True
            upd_box.label(text='NOTE', icon='ERROR')
            mes_box = upd_box.box()
            mes_box.label(text=ZuvLabels.UPDATE_WARNING_MAIN_01)
            mes_box.label(text=ZuvLabels.UPDATE_WARNING_MAIN_02)

        row = upd_box.row()
        row.prop(self, 'check_for_updates')
        if self.check_for_updates:
            if ZenPolls.new_addon_version:
                s_version = '.'.join(map(str, ZenPolls.new_addon_version))
                op = row.operator('wm.zenuv_show_addon_version_info', text=f'Ver. {s_version} available!')
                op.is_silent = False
                op.version = s_version

        r2 = row.row(align=True)
        r2.alignment = 'RIGHT'

        r2.operator("zenuv.reset_preferences", text='', icon='FILE_REFRESH')

        op = r2.operator("wm.zenuv_import_from_json", text='', icon='IMPORT')
        op.data_path = f"preferences.addons['{ZenPolls.ADDON_PACKAGE}'].preferences"
        op.desc = "Import addon preferences from json file"

        op = r2.operator("wm.zenuv_export_to_json", text='', icon='EXPORT')
        op.data_path = f"preferences.addons['{ZenPolls.ADDON_PACKAGE}'].preferences"
        op.desc = "Export addon preferences to json file"

        row = upd_box.row()
        row.operator("uv.zenuv_update_addon")

    def pack_eng_callback(self, context):
        return (
            ("BLDR", ZuvLabels.PREF_PACK_ENGINE_BLDR_LABEL, ZuvLabels.PREF_PACK_ENGINE_BLDR_DESC),
            ("UVP", ZuvLabels.PREF_PACK_ENGINE_UVP_LABEL, ZuvLabels.PREF_PACK_ENGINE_UVP_DESC),
            ("UVPACKER", ZuvLabels.PREF_PACK_ENGINE_UVPACKER_LABEL, ZuvLabels.PREF_PACK_ENGINE_UVPACKER_DESC)
            # ("CUSTOM", ZuvLabels.PREF_PACK_CUSTOM_LABEL, ZuvLabels.PREF_PACK_CUSTOM_DESC)
        )

    def mark_update_function(self, context):
        if not self.markSharpEdges and not self.markSeamEdges:
            zen_message(
                context,
                message=ZuvLabels.PREF_MARK_WARN_MES,
                title=ZuvLabels.PREF_MARK_WARN_TITLE)

    def update_uv_borders_draw(self, context: bpy.types.Context):
        p_scene = context.scene
        if p_scene.zen_uv.ui.draw_mode_UV == 'UV_BORDERS':
            from ZenUV.ui.gizmo_draw import update_all_gizmos_UV
            update_all_gizmos_UV(context, force=True)

    def update_margin_px(self, context):
        self.margin = get_padding_in_pct(context, self.margin_px)

        self.update_uv_borders_draw(context)

    def update_margin_show_in_px(self, context):
        if self.margin_show_in_px:
            self.margin_px = get_padding_in_px(context, self.margin)
        else:
            self.margin = get_padding_in_pct(context, self.margin_px)

        self.update_uv_borders_draw(context)

    # def image_size_update_function(self, context):
    #     if self.td_im_size_presets.isdigit():
    #         self.TD_TextureSizeX = self.TD_TextureSizeY = int(self.td_im_size_presets)
    #     self.margin = get_padding_in_pct(context, self.margin_px)

    op_zen_unwrap_props: bpy.props.PointerProperty(type=ZUV_ZenUnwrapOpAddonProps)

    uv_checker_props: bpy.props.PointerProperty(type=ZUV_CheckerAddonLevelProperties)

    pie_assist: bpy.props.BoolProperty(
        name=ZuvLabels.PROP_DISPLAY_PIE_ASSIST_LABEL,
        description=ZuvLabels.PROP_DISPLAY_PIE_ASSIST_DESC,
        default=True
    )

    pie_assist_font_size: IntProperty(
        name=ZuvLabels.PROP_PIE_ASSIST_FONT_SIZE_LABEL,
        description=ZuvLabels.PROP_PIE_ASSIST_FONT_SIZE_DESC,
        min=8,
        max=16,
        default=11,
    )

    # Stack Preferences
    StackedColor: bpy.props.FloatVectorProperty(
        name=ZuvLabels.PREF_ST_STACKED_COLOR_LABEL,
        description=ZuvLabels.PREF_ST_STACKED_COLOR_DESC,
        subtype='COLOR',
        default=[0.325, 0.65, 0.0, 0.35],
        size=4,
        min=0,
        max=1
    )

    unstack_direction: FloatVectorProperty(
        name="Direction",
        size=2,
        max=1.0,
        min=-1.0,
        default=(1.0, 0.0),
        subtype='XYZ'
    )

    stack_offset: FloatVectorProperty(
        name="Direction",
        size=2,
        default=(0.0, 0.0),
        subtype='XYZ'
    )

    stackMoveOnly: BoolProperty(
        name=ZuvLabels.PREF_STACK_MOVE_ONLY_LABEL,
        default=False,
        description=ZuvLabels.PREF_STACK_MOVE_ONLY_DESC,
        )

    dock_VIEW_3D_panels: bpy.props.PointerProperty(
        name='Docked View3D Panels', type=ZuvPanelEnableGroup)

    dock_UV_panels: bpy.props.PointerProperty(
        name='Docked UV Panels', type=ZuvPanelEnableGroup)

    dock_VIEW_3D_panels_enabled: bpy.props.BoolProperty(
        name="Enable Docked View3D Panel",
        default=True
    )

    dock_UV_panels_enabled: bpy.props.BoolProperty(
        name="Enable Docked UV Panel",
        default=True
    )

    float_VIEW_3D_panels: bpy.props.PointerProperty(
        name='Floating View3D Panels', type=ZuvPanelEnableGroup)

    float_UV_panels: bpy.props.PointerProperty(
        name='Floating UV Panels', type=ZuvPanelEnableGroup)

    combo_panel: bpy.props.PointerProperty(name='Combo Panel Settings', type=ZuvComboSettings)

    # Alt Commands Preferences
    s8: StringProperty(name="Sector 8", default='')
    s9: StringProperty(name="Sector 9", default='')
    s6: StringProperty(name="Sector 6", default='')
    s3: StringProperty(name="Sector 3", default='')
    s2: StringProperty(name="Sector 2", default='')
    s1: StringProperty(name="Sector 1", default='')
    s4: StringProperty(name="Sector 4", default='')
    s7: StringProperty(name="Sector 7", default='bpy.ops.uv.zenuv_select_similar()')

    operator: StringProperty(
        name="Operator",
        default=''
    )

    # Zen UV Preferences
    hops_uv_activate: BoolProperty(
        name=ZuvLabels.HOPS_UV_ACTIVATE_LABEL,
        description=ZuvLabels.HOPS_UV_ACTIVATE_DESC,
        default=False,
    )
    hops_uv_context: BoolProperty(
        name=ZuvLabels.HOPS_UV_CONTEXT_LABEL,
        description=ZuvLabels.HOPS_UV_CONTEXT_DESC,
        default=True,
    )

    def on_tabs_update(self, context: bpy.types.Context):
        if self.tabs == 'HELP':
            try:
                from .demo_examples import ZUV_OT_DemoExamplesUpdate

                d_last_update = bpy.app.driver_namespace.get(ZUV_OT_DemoExamplesUpdate.LITERAL_LAST_UPDATE, 0)
                if d_last_update == 0 or timer() - d_last_update > 60000:
                    if bpy.ops.wm.zuv_demo_examples_update.poll():
                        bpy.ops.wm.zuv_demo_examples_update('INVOKE_DEFAULT', True)
            except Exception as e:
                Log.error("UPDATE DEMO EXAMPLES:", e)

    tabs: EnumProperty(
        items=[
            ("KEYMAP", "Keymap", ""),
            ("PANELS", "UI", ""),
            ("MODULES", "Modules", ""),
            ("STK_UV_EDITOR", "Sticky UV Editor", ""),
            ("HELP", "Help", ""),
        ],
        default="MODULES",
        update=on_tabs_update
    )
    # Zen UV UI Key modifier
    zen_key_modifier: EnumProperty(
        items=[
            ("ALT", "Alt", "Alt"),
            ("CTRL", "Ctrl", "Ctrl"),
            ("SHIFT", "Shift", "Shift")
        ],
        default="ALT",
        description=ZuvLabels.ZEN_MODIFIER_KEY_DESC,
        name=ZuvLabels.ZEN_MODIFIER_KEY_LABEL,

    )
    # Tabs for Sticky UV Editor Setup
    stk_tabs: EnumProperty(
        items=[
            ("GENERAL", "General", ""),
            ("SAVE_RESTORE", "Save & Restore", ""),
            ("ABOUT", "About", "")
        ],
        default="GENERAL"
    )

    useGlobalMarkSettings: BoolProperty(
        name=ZuvLabels.PREF_USE_GLOBAL_MARK_LABEL,
        description=ZuvLabels.PREF_USE_GLOBAL_MARK_DESC,
        default=True
    )

    markSharpEdges: BoolProperty(
        name=ZuvLabels.PREF_MARK_SHARP_EDGES_LABEL,
        description=ZuvLabels.PREF_MARK_SHARP_EDGES_DESC,
        default=False,
        update=mark_update_function)

    markSeamEdges: BoolProperty(
        name=ZuvLabels.PREF_MARK_SEAM_EDGES_LABEL,
        description=ZuvLabels.PREF_MARK_SEAM_EDGES_DESC,
        default=True,
        update=mark_update_function)

    # MarkUnwrapped: BoolProperty(
    #     name=ZuvLabels.PREF_AUTO_SEAMS_WITH_UNWRAP_LABEL,
    #     description=ZuvLabels.PREF_AUTO_SEAMS_WITH_UNWRAP_DESC,
    #     default=True)

    # packAfUnwrap: BoolProperty(
    #     name=ZuvLabels.PREF_PACK_AF_UNWRAP_LABEL,
    #     description=ZuvLabels.PREF_PACK_AF_UNWRAP_DESC,
    #     default=True)

    packEngine: EnumProperty(
        items=pack_eng_callback,
        name=ZuvLabels.PREF_PACK_ENGINE_LABEL,
        description=ZuvLabels.PREF_PACK_ENGINE_DESC,
        default=None
        )

    # customEngine: StringProperty(
    #     default="bpy.ops.uvpackeroperator.packbtn()",
    #     description="Custom Pack Command"
    # )

    averageBeforePack: BoolProperty(
        name=ZuvLabels.PREF_AVERAGE_BEFORE_PACK_LABEL,
        description=ZuvLabels.PREF_AVERAGE_BEFORE_PACK_DESC,
        default=True)

    rotateOnPack: BoolProperty(
        name=ZuvLabels.PREF_ROTATE_ON_PACK_LABEL,
        description=ZuvLabels.PREF_ROTATE_ON_PACK_DESC,
        default=True)

    packInTrim: BoolProperty(
        name='Pack in Trim',
        description='Use Active Trim instead of UV Area',
        default=False)

    packSelectedIslOnly: BoolProperty(
        name='Pack Selected Islands',
        description='Pack only selected Islands',
        default=False)

    pack_blen_margin_method: EnumProperty(
        items=[
            ('SCALED', 'Scaled', 'Use scale of existing UVs to multiply margin'),
            ('ADD', 'Add', 'Just add the margin, ignoring any UV scale'),
            ('FRACTION', 'Fraction', 'Specify a precise fraction of final UV output')
        ],
        name='Margin Method',
    )
    # keepStacked: BoolProperty(
    #     name=ZuvLabels.PREF_KEEP_STACKED_LABEL,
    #     description=ZuvLabels.PREF_KEEP_STACKED_DESC,
    #     default=True)

    def update_lock_ovelap_enbl(self, context):
        if self.lock_overlapping_mode == '0':
            self.lock_overlapping_enable = False
        else:
            self.lock_overlapping_enable = True

    lock_overlapping_mode: EnumProperty(
        items=[
            ('0', 'Disabled', ZuvLabels.LOCK_OVERLAPPING_MODE_DISABLED_DESC),
            ('1', 'Any Part', ZuvLabels.LOCK_OVERLAPPING_MODE_ANY_PART_DESC),
            ('2', 'Exact', ZuvLabels.LOCK_OVERLAPPING_MODE_EXACT_DESC)
        ],
        name=ZuvLabels.LOCK_OVERLAPPING_MODE_NAME,
        description=ZuvLabels.LOCK_OVERLAPPING_MODE_DESC,
        update=update_lock_ovelap_enbl
    )

    lock_overlapping_enable: BoolProperty(
        name=ZuvLabels.LOCK_OVERLAPPING_ENABLE_NAME,
        description=ZuvLabels.LOCK_OVERLAPPING_ENABLE_DESC,
    )

    packFixedScale: BoolProperty(
        name=ZuvLabels.PREF_FIXED_SCALE_LABEL,
        description=ZuvLabels.PREF_FIXED_SCALE_DESC,
        default=False)

    autoFitUV: BoolProperty(
        name=ZuvLabels.PREF_AUTO_FIT_UV_LABEL,
        description=ZuvLabels.PREF_AUTO_FIT_UV_DESC,
        default=False)

    # unwrapAutoSorting: BoolProperty(
    #     name=ZuvLabels.PREF_ZEN_UNWRAP_SORT_ISLANDS_LABEL,
    #     description=ZuvLabels.PREF_ZEN_UNWRAP_SORT_ISLANDS_DESC,
    #     default=False)

    sortAutoSorting: BoolProperty(
        name=ZuvLabels.PREF_ZEN_SORT_ISLANDS_LABEL,
        description=ZuvLabels.PREF_ZEN_SORT_ISLANDS_DESC,
        default=True)

    autoPinnedAsFinished: BoolProperty(
        name=ZuvLabels.PREF_AUTO_PINNED_AS_FINISHED_LABEL,
        description=ZuvLabels.PREF_AUTO_PINNED_AS_FINISHED_DESC,
        default=True)

    autoFinishedToPinned: BoolProperty(
        name=ZuvLabels.PREF_AUTO_FINISHED_TO_PINNED_LABEL,
        description=ZuvLabels.PREF_AUTO_FINISHED_TO_PINNED_DESC,
        default=False)

    # autoTagFinished: BoolProperty(
    #     name=ZuvLabels.PREF_AUTO_TAG_FINISHED_LABEL,
    #     description=ZuvLabels.PREF_AUTO_TAG_FINISHED_DESC,
    #     default=False)

    def on_margin_update(self, context: bpy.types.Context):
        self.update_uv_borders_draw(context)

    margin: FloatProperty(
        name='Margin (Units)',
        description='Set space between Islands in units for Pack Islands operation',
        min=0.0,
        default=0.005,
        precision=3,
        update=on_margin_update
    )

    margin_px: IntProperty(
        name=ZuvLabels.PREF_MARGIN_PX_LABEL,
        description=ZuvLabels.PREF_MARGIN_PX_DESC,
        min=0,
        default=5,
        update=update_margin_px
    )

    margin_show_in_px: BoolProperty(
        name=ZuvLabels.PREF_MARGIN_SHOW_PX_LABEL,
        description=ZuvLabels.PREF_MARGIN_SHOW_PX_DESC,
        default=True,
        update=update_margin_show_in_px
    )

    PinColor: bpy.props.FloatVectorProperty(
        name=ZuvLabels.PIN_UV_ISLAND_ISLAND_COLOR_NAME,
        description=ZuvLabels.PIN_UV_ISLAND_ISLAND_COLOR_DESC,
        subtype='COLOR',
        default=[0.25, 0.4, 0.4, 1],
        size=4,
        min=0,
        max=1)

    FlippedColor: bpy.props.FloatVectorProperty(
        name='Flipped Color',
        description='Flipped islands viewport display color',
        subtype='COLOR',
        default=[0, 1, 0, 0.3],
        size=4,
        min=0,
        max=1)

    UvOverlappedColor: bpy.props.FloatVectorProperty(
        name='Overlapped Color',
        description='Color of overlapped faces',
        subtype='COLOR',
        default=[0, 1, 0, 0.3],
        size=4,
        min=0,
        max=1)

    UvNoSyncColor: bpy.props.FloatVectorProperty(
        name='UV No Sync Color',
        description='Color of mesh elements that are selected in UV no sync mode',
        subtype='COLOR',
        default=[1, 1, 0, 0.5],
        size=4,
        min=0,
        max=1)

    FinishedColor: bpy.props.FloatVectorProperty(
        name=ZuvLabels.TAG_FINISHED_COLOR_NAME,
        description=ZuvLabels.TAG_FINISHED_COLOR_DESC,
        subtype='COLOR',
        default=[0, 0.5, 0, 0.4],
        size=4,
        min=0,
        max=1)

    ExcludedColor: bpy.props.FloatVectorProperty(
        name=ZuvLabels.TAG_EXCLUDED_COLOR_NAME,
        description=ZuvLabels.TAG_EXCLUDED_COLOR_DESC,
        subtype='COLOR',
        default=[0.97, 0.026, 0.5, 0.4],
        size=4,
        min=0,
        max=1)

    UnFinishedColor: bpy.props.FloatVectorProperty(
        name=ZuvLabels.TAG_UNFINISHED_COLOR_NAME,
        description=ZuvLabels.TAG_UNFINISHED_COLOR_DESC,
        subtype='COLOR',
        default=[0.937, 0.448, 0.735, 0.2],
        size=4,
        min=0,
        max=1)

    RandomizePinColor: bpy.props.BoolProperty(
        name=ZuvLabels.PIN_UV_ISLAND_RAND_COLOR_NAME,
        description=ZuvLabels.PIN_UV_ISLAND_RAND_COLOR_DESC,
        default=True)

    TrimColorsAlpha: bpy.props.FloatProperty(
        name="Trim Colors Alpha",
        description="Transparency of trim colors viewport mode",
        min=0.2,
        max=1.0,
        default=0.8
    )

    UvPointsOnZoom: bpy.props.BoolProperty(
        name='Scale Points On Zoom',
        description='Scale points when zoom is changed',
        default=True
    )

    def on_uvpoints_display_update(self, context: bpy.types.Context):
        from ZenUV.ui.gizmo_draw import update_all_gizmos_UV
        update_all_gizmos_UV(context)

    UvObjectPointsDisplay: bpy.props.BoolProperty(
        name='Display UV Object Vertices',
        description='Show vertices in UV Object mode',
        default=True,
        update=on_uvpoints_display_update
    )

    UvObjectActiveColor: bpy.props.FloatVectorProperty(
        name='UV Object Active Fill',
        description='UVs fill color of the active object',
        subtype='COLOR',
        default=[0, 1, 0, 0.3],
        size=4,
        min=0,
        max=1)

    UvObjectInactiveColor: bpy.props.FloatVectorProperty(
        name='UV Object Fill',
        description='UVs fill color of the selected objects',
        subtype='COLOR',
        default=[0.5, 0.5, 0, 0.5],
        size=4,
        min=0,
        max=1)

    UvObjectActivePoint: bpy.props.FloatVectorProperty(
        name='UV Object Active Vertex',
        description='UVs vertex color of the active object',
        subtype='COLOR',
        default=[1, 1, 0, 1],
        size=4,
        min=0,
        max=1)

    UvObjectInactivePoint: bpy.props.FloatVectorProperty(
        name='UV Object Vertex',
        description='UVs vertex color of the selected objects',
        subtype='COLOR',
        default=[0.5, 0.5, 0.5, 0.5],
        size=4,
        min=0,
        max=1)

    trimsheet: bpy.props.PointerProperty(type=ZuvTrimsheetProps)

    use_progress_bar: bpy.props.BoolProperty(
        name='Display Progress Bar',
        description='Display progress bar window',
        default=True)

    use_zensets: BoolProperty(
        name="Use Zen Sets to Highlight Errors",
        description="Use Zen Sets to create Zen Sets Groups with Mesh Errors",
        default=False)

    use_relax_in_shell: bpy.props.BoolProperty(
        name='Call Relax Application in Shell',
        description=(
            'Relax application is invoked via the shell and is platform-dependent\n'
            'NOTE: Use this method if application can not be started via Blender'),
        default=False
    )

    # Sticky UV Editor Properties
    uv_editor_side: EnumProperty(
        name="UV Editor Side",
        description="3D Viewport area side where to open UV Editor",
        items={('LEFT', "Left",
                "Open UV Editor on the left side of 3D Viewport area", 0),
               ('RIGHT', "Right",
                "Open UV Editor on the right side of 3D Viewport area", 1)},
        default='LEFT')
    show_ui_button: BoolProperty(
        name="Show Overlay Button",
        description="Show overlay button on corresponding side of 3D Viewport",
        default=True)
    remember_uv_editor_settings: BoolProperty(
        name="Remember UV Editor Settings",
        description="Remember changes made in UV Editor on area close event",
        default=True)

    StkUvEdProps: PointerProperty(type=UVEditorSettings)

    view_mode: EnumProperty(
        name="View Mode",
        description="Adjust UV Editor view when open",
        items={('DISABLE', "Disable",
                "Do not modify the view", 0),
               ('FRAME_ALL', "Frame All UVs",
                "View all UVs", 1),
               ('FRAME_SELECTED', "Frame Selected",
                "View all selected UVs", 2),
               ('FRAME_ALL_FIT', "Frame All UDIMs",
                "View all UDIMs", 3)},
        default='DISABLE')
    use_uv_select_sync: BoolProperty(
        name="UV Sync Selection",
        description="Keep UV an edit mode mesh selection in sync",
        default=False)

    stk_ed_button_position_mode: bpy.props.EnumProperty(
        name='Button Position Mode',
        items=[
            ('PERCENTAGE', 'Percentage', 'Horizontal and vertical position in percents'),
            ('GIZMO_COLUMN', 'Gizmo Column', 'Button will be placed in viewport gizmo group column'),
        ],
        default='PERCENTAGE'
    )

    stk_ed_button_v_position: FloatProperty(
        name="Vertical Position, %",
        description="The vertical position of the button in percentages.",
        min=2.0,
        max=90.0,
        default=50,
        precision=1
    )

    stk_ed_button_h_position: FloatProperty(
        name="Horizontal Position, %",
        description="The horizontal position of the button in percentages.",
        min=0.0,
        max=40.0,
        default=0.0,
        precision=1
    )

    # MUST BE Integer to support previous BLF versions
    draw_label_font_size: bpy.props.IntProperty(
        name='Font Size',
        description='Font size of drawing mode label',
        subtype='PIXEL',
        min=4,
        max=40,
        default=10
    )

    draw_label_font_color: bpy.props.FloatVectorProperty(
        name='Font Color',
        description='Font color of drawing mode label',
        subtype='COLOR',
        default=(1, 1, 1, 1),
        size=4,
        min=0,
        max=1)

    draw_auto_disable: bpy.props.BoolProperty(
        name='Auto Disable Draw',
        description='Switch off draw system when object mode (Object, Edit) is changed',
        default=False
    )

    check_for_updates: bpy.props.BoolProperty(
        name='Check For Updates',
        description='Check for available new addon version on the official Zen UV website',
        default=True
    )

    demo: bpy.props.PointerProperty(
        name='Demo',
        type=ZUV_DemoExampleProps
    )

    user_script: bpy.props.PointerProperty(
        name='User Script',
        type=ZUV_UserScriptProps
    )

    td_draw: bpy.props.PointerProperty(
        name='Texel Density Draw',
        type=ZUV_TexelDensityDrawProps
    )

    adv_maps: bpy.props.PointerProperty(
        name='Advanced Maps',
        type=ZUV_AdvMapsProps
    )

    uv_borders_draw: bpy.props.PointerProperty(
        name='UV Borders Draw',
        type=ZUV_UVBordersDrawProps
    )

    right_menu_assist: bpy.props.BoolProperty(
        name='Right Menu Assist',
        description='Context assistance by right menu click',
        default=True
    )

    show_uv_zen_sync: bpy.props.BoolProperty(
        name="UV Zen Sync Button",
        description="Display sync button in uv header",
        default=True,
        update=on_prop_update_uv
    )

    show_uv_tool_transform_gizmo_button: bpy.props.BoolProperty(
        name="UV Transform Mode Button",
        description="Display uv tool transform mode button",
        default=True,
        update=on_prop_update_uv
    )

    show_uv_tool_transform_adjust_header: bpy.props.BoolProperty(
        name="UV Transform Adjust Header",
        description="Display uv tool transform adjust panel in header",
        default=True,
        update=on_prop_update_uv
    )

    n_panel_name: bpy.props.EnumProperty(
        name="Addon N-Panel Name",
        description=(
            "Name of the addon tab in N-Panel\n"
            "* You can set it to Zen to combine all Zen addons in one tab\n"
            "** Requires Blender restart"),
        items=[
            ("ZEN_UV", "Zen UV", "Default addon name"),
            ("ZEN", "Zen", "Is used to combine all Zen addons in one tab")
        ],
        default="ZEN_UV"
    )

    favourite_props_VIEW_3D: bpy.props.PointerProperty(
        name='Favourite Props 3D',
        type=ZUV_FavProps
    )

    favourite_props_UV: bpy.props.PointerProperty(
        name='Favourite Props UV',
        type=ZUV_FavProps
    )

    uv_world_size: bpy.props.PointerProperty(
        name="UV World Size",
        type=ZUV_WorldSizeAddonProps
    )

    uv_transform_tool: bpy.props.PointerProperty(
        name="UV Transform Tool",
        type=ZUV_UVTransformToolProps
    )

    op_addon_props: bpy.props.PointerProperty(
        name="Auto Unwrap Operator Properties",
        type=ZUV_AddonOperatorProps
    )


def get_prefs() -> ZUV_AddonPreferences:
    """ Return Zen UV Properties obj """
    return bpy.context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences


def get_scene_props(context: bpy.types.Context):
    """ Return Zen UV Scene level Properties obj """
    return context.scene.zen_uv
