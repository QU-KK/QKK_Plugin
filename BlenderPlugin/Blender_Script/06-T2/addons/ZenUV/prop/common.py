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

# Copyright 2023, Alex Zhornyak, Valeriy Yatsenko


import bpy


_CACHE_PANELS_ORDER = {}


uv_enblr = {
    "enable_pt_favourites": {"VIEW_3D": 'ZUV_PT_3DV_Favourites', "UV": 'ZUV_PT_UVL_Favourites'},
    "enable_pt_adv_uv_map": {"VIEW_3D": 'DATA_PT_uv_texture_advanced', "UV": 'DATA_PT_UVL_uv_texture_advanced'},
    "enable_pt_seam_group": {"VIEW_3D": 'ZUV_PT_ZenSeamsGroups', "UV": None},
    "enable_pt_unwrap": {"VIEW_3D": 'ZUV_PT_Unwrap', "UV": 'ZUV_PT_UVL_Unwrap'},
    "enable_pt_select": {"VIEW_3D": 'ZUV_PT_Select', "UV": 'ZUV_PT_UVL_Select'},
    "enable_pt_transform": {"VIEW_3D": 'ZUV_PT_3DV_Transform', "UV": 'ZUV_PT_UVL_Transform'},
    "enable_pt_trimsheet": {"VIEW_3D": 'ZUV_PT_3DV_Trimsheet', "UV": 'ZUV_PT_UVL_Trimsheet'},
    "enable_pt_stack": {"VIEW_3D": 'ZUV_PT_Stack', "UV": 'ZUV_PT_UVL_Stack'},
    "enable_pt_texel_density": {"VIEW_3D": 'ZUV_PT_Texel_Density', "UV": 'ZUV_PT_UVL_Texel_Density'},
    "enable_pt_checker_map": {"VIEW_3D": 'ZUV_PT_Checker', "UV": 'ZUV_PT_Checker_UVL'},
    "enable_pt_pack": {"VIEW_3D": 'ZUV_PT_Pack', "UV": 'ZUV_PT_UVL_Pack'},
    "enable_pt_preferences": {"VIEW_3D": 'ZUV_PT_Preferences', "UV": 'ZUV_PT_UVL_Preferences'},
    "enable_pt_help": {"VIEW_3D": 'ZUV_PT_Help', "UV": 'ZUV_PT_UVL_Help'}
}


def get_combo_panel_order(s_mode, s_panel_type):

    if s_mode not in _CACHE_PANELS_ORDER:
        _CACHE_PANELS_ORDER[s_mode] = [v.get(s_mode, None) for v in uv_enblr.values() if v.get(s_mode, None) is not None]
        _CACHE_PANELS_ORDER[s_mode] = {it: idx for idx, it in enumerate(_CACHE_PANELS_ORDER[s_mode])}

    return _CACHE_PANELS_ORDER[s_mode][s_panel_type] + 1


def update_addon_prop(self, context: bpy.types.Context):
    if not context.preferences.is_dirty:
        context.preferences.is_dirty = True
