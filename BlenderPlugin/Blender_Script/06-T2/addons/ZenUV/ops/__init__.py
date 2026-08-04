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

from bpy.props import IntProperty

import platform

from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.vlog import Log

from .operators import operators_classes
from .zen_unwrap.finishing import finishing_classes
from .mark import mark_sys_classes
from .world_orient import w_orient_classes

from .texel_density.td_ops import td_classes
from .texel_density.td_presets import TDPR_classes, TDPRListGroup
from .texel_density.td_tools import register as register_td_tools
from .texel_density.td_tools import unregister as unregister_td_tools

from .quadrify import register as register_quadrify
from .quadrify import unregister as unregister_quadrify
from .distribute import uv_distribute_classes
from .adv_uv_maps_sys.adv_uv_maps import adv_uv_texture_classes
from .seam_groups import seam_groups_classes, ZSGListGroup
from .pack_sys.pack import pack_classes
from .relax import relax_classes
from .select_sys.select import select_classes
from .select_sys.select import poll_3_2_select_classes
from .select_sys.select_islands import register as register_select_islands
from .select_sys.select_islands import unregister as unregister_select_islands
from .reshape.ops import uv_reshape_classes
from .context_utils import context_utils_classes
from .pack_sys.pack_exclusion import register_pack_exclusion, unregister_pack_exclusion
from .transform_sys.tr_register import register_transform_sys, unregister_transform_sys

# Zen Unwrap Compound
from .zen_unwrap.ops import ZenUnwrapClasses
from .zen_unwrap.ui import ZenUV_MT_ZenUnwrap_Popup, ZenUV_MT_ZenUnwrap_ConfirmPopup
from .unwrap_constraint import register_uwrp_constraint, unregister_uwrp_constraint

from .trimsheets.trimsheet import register as register_trimsheets
from .trimsheets.trimsheet import unregister as unregister_trimsheets

from .trimsheets.trimsheet_transform import register as register_trim_transform
from .trimsheets.trimsheet_transform import unregister as unregister_trim_transform
from .transform_sys.trim_batch_operators.system import register_trim_batch_ops, unregister_trim_batch_ops

from .stitch import register as register_stitch
from .stitch import unregister as unregister_stitch

from .zen_unwrap.unwrap_for_tool import register as register_unwrap_for_tool
from .zen_unwrap.unwrap_for_tool import unregister as unregister_unwrap_for_tool

from .zen_unwrap.unwrap_processor import register as register_uwrp_processor
from .zen_unwrap.unwrap_processor import unregister as unregister_uwrp_processor

from ZenUV.ops.event_service import ZUV_OT_EventService, ZUV_OT_EventGet

from ZenUV.ops.adv_uv_maps_sys.udims import register as register_udims
from ZenUV.ops.adv_uv_maps_sys.udims import unregister as unregister_udims

from ZenUV.ops.mirror_uv import register as register_mirror_uv
from ZenUV.ops.mirror_uv import unregister as unregister_mirror_uv

from .auto_uv_unwrap import classes as auto_unwrap_classes



unwrap_ui_classes = (
    ZenUV_MT_ZenUnwrap_Popup, ZenUV_MT_ZenUnwrap_ConfirmPopup
)

misc_classes = (
    # NOTE: Special class for detecting event procedures
    ZUV_OT_EventService, ZUV_OT_EventGet,
)


def zenuv_image_header_draw(self, context: bpy.types.Context):
    layout: bpy.types.UILayout = self.layout

    # NOTE: make the same as in Blender 'space_image.py'
    sima: bpy.types.SpaceImageEditor = context.space_data
    if sima.mode == 'UV':

        show_uv_edit = sima.show_uvedit

        if show_uv_edit:
            from ZenUV.prop.zuv_preferences import get_prefs
            addon_prefs = get_prefs()

            if addon_prefs.show_uv_zen_sync:
                from ZenUV.ico import icon_get

                row = layout.row(align=True)
                row.operator(
                    "uv.zenuv_sync_select",
                    depress=context.scene.tool_settings.use_uv_select_sync,
                    icon_value=icon_get("zen_sync"))


def register():
    """Registering Operators"""
    RegisterUtils.register(operators_classes)

    register_trimsheets()

    # Quadrify
    register_quadrify()

    # Zen Unwrap Registration
    RegisterUtils.register(ZenUnwrapClasses)

    RegisterUtils.register(unwrap_ui_classes)

    # Zen Transform Registration
    register_transform_sys()

    # Zen Distribute Registration
    RegisterUtils.register(uv_distribute_classes)

    # Reshape Island Registration
    RegisterUtils.register(uv_reshape_classes)

    # Advanced UV Texture Registration
    RegisterUtils.register(adv_uv_texture_classes)

    # Zen Seam Groups Registration
    RegisterUtils.register(seam_groups_classes)

    # Texel Density Registration
    RegisterUtils.register(td_classes)

    # Texel Density Presets Registration
    RegisterUtils.register(TDPR_classes)

    RegisterUtils.register_class(TDPRListGroup)

    register_td_tools()

    # Pack Registration
    RegisterUtils.register(pack_classes)

    # World Orient Registration
    RegisterUtils.register(w_orient_classes)

    # Relax Registration
    RegisterUtils.register(relax_classes)

    # Finishing Sys
    RegisterUtils.register(finishing_classes)

    # Mark Sys
    RegisterUtils.register(mark_sys_classes)

    RegisterUtils.register(context_utils_classes)

    # Select Registration ----------------
    if ZenPolls.version_since_3_2_0:
        RegisterUtils.register(poll_3_2_select_classes)

    RegisterUtils.register(select_classes)
    register_select_islands()
    # Select Registration END ------------

    register_pack_exclusion()
    register_uwrp_constraint()

    # Smooth Groups
    bpy.types.Object.zen_sg_list = bpy.props.CollectionProperty(type=ZSGListGroup)
    bpy.types.Object.zsg_list_index = IntProperty(name="Index for zen_sg_list", default=0)

    # Texel Density Presets
    bpy.types.Scene.zen_tdpr_list = bpy.props.CollectionProperty(type=TDPRListGroup)
    bpy.types.Scene.zen_tdpr_list_index = IntProperty(name="Index for zen_tdpr_list", default=0)

    register_trim_transform()

    register_stitch()
    register_trim_batch_ops()

    register_unwrap_for_tool()

    register_uwrp_processor()

    register_udims()

    register_mirror_uv()

    RegisterUtils.register(misc_classes)


    if platform.system() == 'Windows':
        RegisterUtils.register(auto_unwrap_classes)

    try:
        bpy.types.IMAGE_HT_header.prepend(zenuv_image_header_draw)
    except Exception as e:
        Log.error("Register in IMAGE_HT_header:", e)


def unregister():
    """Unregistering Operators"""

    try:
        bpy.types.IMAGE_HT_header.remove(zenuv_image_header_draw)
    except Exception as e:
        Log.error("Unregister in IMAGE_HT_header:", e)

    if platform.system() == 'Windows':
        RegisterUtils.unregister(auto_unwrap_classes)

    RegisterUtils.unregister(misc_classes)

    RegisterUtils.unregister(operators_classes)

    # Quadrify
    unregister_quadrify()

    # Zen Unwrap Registration
    RegisterUtils.unregister(ZenUnwrapClasses)

    RegisterUtils.unregister(unwrap_ui_classes)

    # Zen Transform
    unregister_transform_sys()

    # Zen Distribute
    RegisterUtils.unregister(uv_distribute_classes)

    # Reshape Island
    RegisterUtils.unregister(uv_reshape_classes)

    # Advanced UV Texture
    RegisterUtils.unregister(adv_uv_texture_classes)

    # Zen Seam Groups
    RegisterUtils.unregister(seam_groups_classes)

    # Texel Density
    RegisterUtils.unregister(td_classes)

    # Texel Density Presets
    RegisterUtils.unregister(TDPR_classes)

    RegisterUtils.unregister_class(TDPRListGroup)

    unregister_td_tools()

    # Pack Unregister
    RegisterUtils.unregister(pack_classes)

    # World Orient Unregister
    RegisterUtils.unregister(w_orient_classes)

    # Relax Unregister
    RegisterUtils.unregister(relax_classes)

    # Finishing Sys
    RegisterUtils.unregister(finishing_classes)

    # Mark Sys
    RegisterUtils.unregister(mark_sys_classes)

    RegisterUtils.unregister(context_utils_classes)

    # Select Unregister ------------------
    if ZenPolls.version_since_3_2_0:
        RegisterUtils.unregister(poll_3_2_select_classes)

    RegisterUtils.unregister(select_classes)
    unregister_select_islands()
    # Select Unregister END --------------

    unregister_trimsheets()

    unregister_pack_exclusion()
    unregister_uwrp_constraint()

    unregister_trim_transform()

    unregister_stitch()
    unregister_trim_batch_ops()

    unregister_unwrap_for_tool()

    unregister_uwrp_processor()

    unregister_udims()

    unregister_mirror_uv()



if __name__ == "__main__":
    pass
