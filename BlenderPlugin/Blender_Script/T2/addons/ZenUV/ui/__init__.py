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

""" Zen UV Init UI module """

import bpy

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.ops.adv_uv_maps_sys.adv_uv_maps import DATA_PT_uv_texture_advanced, DATA_PT_UVL_uv_texture_advanced
from ZenUV.ui import main_panel, ots_local_props

from ZenUV.ops.texel_density.td_ui import register as register_td_ui
from ZenUV.ops.texel_density.td_ui import unregister as unregister_td_ui

from ZenUV.zen_checker.panel import ZUV_PT_Checker, ZUV_PT_Checker_UVL
from ZenUV.ui import ui_call

from ZenUV.ops.pack_sys.pack_ui import ZUV_PT_Pack, ZUV_PT_UVL_Pack, pack_ui_parented_panels

from ZenUV.ops.select_sys.select_ui import ZUV_PT_Select, ZUV_PT_UVL_Select

from ZenUV.ui.zen_pack_popup import register as register_pack_popups
from ZenUV.ui.zen_pack_popup import unregister as unregister_pack_popups

from ZenUV.ui import zen_mark_popup
from ZenUV.ui import keymap_operator
from ZenUV.ui import uv_panel
from ZenUV.ops import seam_groups
# from ZenUV.ui.user_alt_commands import ZUV_OT_search_operator
from ZenUV.ui import third_party_popups
from ZenUV.ui import manual_map
from ZenUV.ui.pie import ZsPieFactory

# Importing Parented panels classes
from ZenUV.ops.pack_sys.pack_exclusion import pack_exclusion_parented_panels
from ZenUV.ops.texel_density.td_ui import td_parented_panels
from ZenUV.stacks import m_stacks_parented_panels

from ZenUV.ui.main_panel import main_panel_parented_panels
from ZenUV.ui.uv_panel import main_panel_uv_parented_panels
from ZenUV.ops.trimsheets.trimsheet_panel import (
    ZUV_PT_UVL_Trimsheet, ZUV_PT_3DV_Trimsheet, ZUV_PT_PopupTrimsheetMaterial, trimsheet_parented_panels)
from ZenUV.zen_checker.check_utils import checker_parented_panels

from .combo_panel import (
    ZUV_PT_UVL_ComboPanel, ZUV_PT_3DV_ComboPanel,
    ZUV_OT_SetComboPanel, ZUV_OT_ExpandComboPanel, ZUV_OT_PinComboPanel,
    ZUV_OT_ExpandFavCategory)

from ZenUV.ui import tool

from .gizmo_draw import (
    ZUV_GGT_DetectionUV,
    ZUV_GGT_DrawUV, UV_GT_zenuv_overlay_draw,
    ZUV_GGT_Draw3D, VIEW3D_GT_zenuv_overlay_draw,
    ZUV_GGT_DrawView2D, VIEW2D_GT_zenuv_overlay_draw,
    ZUV_PT_GizmoDrawProperties,
    ZUV_PT_TdDrawProperties,
    ZUV_OT_WMDrawUpdate,
    zenuv_despgraph_delayed,
    zenuv_depsgraph_ui_update)

from ZenUV.ops.transform_sys.tr_ui import transform_parented_panels
from ZenUV.ops.adv_uv_maps_sys.udims import udims_parented_panels
from ZenUV.ops.zen_unwrap.finishing import finishing_parented_panels

from ZenUV.ui import right_menu_inject

from ZenUV.stacks.stacks_ui import ZUV_PT_UVL_Stack, ZUV_PT_Stack

# Transform Extended panel
# from ZenUV.ops.transform_sys.tr_ui import (
#     # ZUV_PT_3DV_ExtendedTransform,
#     # ZUV_PT_UVL_ExtendedTransform
# )

main_panel_classes = (
    # main_panel.ZUV_PT_Global,
    DATA_PT_uv_texture_advanced,
    seam_groups.ZUV_PT_ZenSeamsGroups,
    main_panel.ZUV_PT_Unwrap,
    # main_panel.SYSTEM_PT_Finished,
    ZUV_PT_Select,
    ZUV_PT_Pack,
    # main_panel.PROPS_PT_Packer,
    ZUV_PT_Checker,
    # ZUV_PT_Texel_Density,
    main_panel.ZUV_PT_3DV_Transform,
    ZUV_PT_3DV_Trimsheet,
    # ZUV_PT_3DV_ExtendedTransform,
    ZUV_PT_Stack,
    main_panel.ZUV_PT_Preferences,
    main_panel.ZUV_OT_resetPreferences,
    main_panel.ZUV_OT_ShowAddonVersionInfo,
    main_panel.ZUV_OT_ReloadIcons,
    # main_panel.DATA_PT_ZDisplay,
    # main_panel.DATA_PT_Panels_Switch,
    main_panel.ZUV_PT_Help,
    main_panel.ZUV_PT_ZenCore,
    main_panel.ZUV_PT_3DV_Favourites,

    ZUV_PT_3DV_ComboPanel,
)

uv_panel_classes = (
    DATA_PT_UVL_uv_texture_advanced,
    uv_panel.ZUV_PT_UVL_Unwrap,
    ZUV_PT_UVL_Select,
    uv_panel.ZUV_PT_UVL_Transform,
    ZUV_PT_UVL_Trimsheet,
    # ZUV_PT_UVL_ExtendedTransform,
    # ZUV_PT_UVL_Texel_Density,
    ZUV_PT_UVL_Pack,
    ZUV_PT_Checker_UVL,
    # uv_panel.PROPS_PT_UVL_Packer,
    ZUV_PT_UVL_Stack,
    uv_panel.ZUV_PT_UVL_Preferences,
    # uv_panel.DATA_PT_UVL_Panels_Switch,
    # uv_panel.SYSTEM_PT_Finished_UV,
    # uv_panel.SYSTEM_PT_FitRegion_UV
    main_panel.ZUV_PT_UVL_Help,
    main_panel.ZUV_PT_UVL_Favourites,

    ZUV_PT_UVL_ComboPanel,
)

props_classes = (
    # manual_stacks.ZUV_PT_ZenManualStack,
    # manual_stacks.ZUV_PT_UVL_ZenManualStack,
    # ots_local_props.ZENUNWRAP_PT_Properties,
    ots_local_props.MARK_PT_Properties,
    ots_local_props.FINISHED_PT_Properties,
    ots_local_props.RELAX_PT_Properties,
    # ots_local_props.PACK_PT_Properties,
    # ots_local_props.TD_PT_Project_Properties,
    # ots_local_props.TR_PT_Properties,
    ots_local_props.STACK_PT_Properties,
    ots_local_props.STACK_PT_DrawProperties,
    # main_pie.ZUV_OT_StretchMapSwitch,
    # main_pie.ZUV_MT_Main_Pie,
    # main_pie.ZUV_OT_Pie_Caller,
    # main_popup.ZenUV_MT_Main_Popup,
    # ui_call.ZUV_OT_Main_Pie_call,
    ui_call.ZUV_OT_Main_Popup_call,
    third_party_popups.ZUV_MT_HOPS_Popup,
    # zen_unwrap_popup.ZenUV_MT_ZenUnwrap_Popup,
    # zen_pack_popup.ZUV_MT_ZenPack_Uvp_Popup,
    # zen_pack_popup.ZUV_MT_ZenPack_Uvpacker_Popup,
    zen_mark_popup.ZenUV_MT_ZenMark_Popup,

    keymap_operator.ZenKmiWrapper,
    keymap_operator.ZUV_OT_Keymaps,
    keymap_operator.ZUV_OT_KeymapsRestoreCategory,
    keymap_operator.ZUV_OT_KeymapsResolveCollisions,

    ZUV_OT_SetComboPanel,
    ZUV_OT_ExpandComboPanel,
    ZUV_OT_PinComboPanel,

    ZUV_OT_ExpandFavCategory,

    ZUV_OT_WMDrawUpdate,
    ZUV_GGT_DetectionUV,
    UV_GT_zenuv_overlay_draw,
    ZUV_GGT_DrawUV,
    VIEW3D_GT_zenuv_overlay_draw,
    ZUV_GGT_Draw3D,
    VIEW2D_GT_zenuv_overlay_draw,
    ZUV_GGT_DrawView2D,
    ZUV_PT_GizmoDrawProperties,
    ZUV_PT_TdDrawProperties,

    ZUV_PT_PopupTrimsheetMaterial
)

# Order is important!!!
parented_groups = [
    m_stacks_parented_panels,
    td_parented_panels,
    main_panel_parented_panels,
    main_panel_uv_parented_panels,
    pack_ui_parented_panels,
    pack_exclusion_parented_panels,
    trimsheet_parented_panels,
    checker_parented_panels,
    transform_parented_panels,
    udims_parented_panels,
    finishing_parented_panels
]


def register_parented_panels():
    for group in parented_groups:
        RegisterUtils.register(group)


def unregister_parented_panels():
    for group in parented_groups:
        RegisterUtils.unregister(group)


def register():

    # Main Panel registration
    RegisterUtils.register(main_panel_classes)

    # UV Panel registration
    RegisterUtils.register(uv_panel_classes)

    register_td_ui()

    register_parented_panels()

    # Pie menu
    RegisterUtils.register(ZsPieFactory.classes)

    # Properties Popups
    RegisterUtils.register(props_classes)

    register_pack_popups()

    manual_map.register()

    tool.register()

    # register_class(ZUV_OT_search_operator)

    if zenuv_depsgraph_ui_update not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(zenuv_depsgraph_ui_update)

    right_menu_inject.register()


def unregister():

    right_menu_inject.unregister()

    if zenuv_depsgraph_ui_update in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(zenuv_depsgraph_ui_update)

    if bpy.app.timers.is_registered(zenuv_despgraph_delayed):
        bpy.app.timers.unregister(zenuv_despgraph_delayed)

    tool.unregister()

    unregister_parented_panels()

    RegisterUtils.unregister(main_panel_classes)

    # Unregister UV Panel
    RegisterUtils.unregister(uv_panel_classes)

    unregister_td_ui()

    # Pie menu
    RegisterUtils.unregister(ZsPieFactory.classes)

    RegisterUtils.unregister(props_classes)

    # Unregistering System Classes
    if hasattr(bpy.types, "ZUV_PT_System"):
        RegisterUtils.unregister_class(bpy.types.ZUV_PT_System)
    if hasattr(bpy.types, "ZUV_PT_System_UVL"):
        RegisterUtils.unregister_class(bpy.types.ZUV_PT_System_UVL)
    if hasattr(bpy.types, 'ZUV_OT_UnitTestTexelDensity'):
        from ZenUV.utils.tests.td_tests import unregister as unregister_td_tests
        unregister_td_tests()
    # unregister_class(ZUV_OT_search_operator)

    unregister_pack_popups()

    manual_map.unregister()


if __name__ == "__main__":
    pass
