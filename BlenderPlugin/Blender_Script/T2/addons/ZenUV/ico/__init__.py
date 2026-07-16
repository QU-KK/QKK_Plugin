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

import os
import bpy
import bpy.utils.previews


ZENUV_ICONS: bpy.utils.previews.ImagePreviewCollection = None

# Register Icons
icons = (
    "unmark-seams_32.png",
    "mark-seams_32.png",
    "zen-uv_32.png",
    "zen-unwrap_32.png",
    "Discord-Logo-White_32.png",
    "quadrify_32.png",
    "checker_32.png",
    "tr_control_cen.png",
    "transform-orient.png",
    "transform-flip.png",
    "transform-scale.png",
    "transform-rotate.png",
    "transform-fit.png",
    "transform-cursor.png",
    "transform-move.png",
    "transform-distribute.png",
    "tr_control_bl.png",
    "tr_control_br.png",
    "tr_control_tl.png",
    "tr_control_tr.png",
    "tr_control_bc.png",
    "tr_control_lc.png",
    "tr_control_rc.png",
    "tr_control_tc.png",
    "tr_rotate_bc.png",
    "tr_rotate_br.png",
    "tr_rotate_cen.png",
    "tr_rotate_bl.png",
    "tr_rotate_lc.png",
    "tr_rotate_rc.png",
    "tr_rotate_tc.png",
    "tr_rotate_tl.png",
    "tr_rotate_tr.png",
    "tr_control_off.png",
    "stack_32.png",
    "pack.png",
    "select.png",
    "zen-bbq.png",
    "zen-sets.png",
    "relax-1_32.png",
    "hotspot-mapping.png",
    "zen_sync.png",
    "patreon_32.png"
)


icons_combo = (
    'AdvUVMaps.png',
    'CheckerMap.png',
    'Help.png',
    'Pack.png',
    'Preferences.png',
    'SeamsGroups.png',
    'Select.png',
    'Stack.png',
    'TD.png',
    'Transform.png',
    'Trimsheet.png',
    'Unwrap.png'
)


def _icon_register(fileName, base_name, prefix=''):
    name = fileName.split('.')[0]   # Don't include file extension
    s_icon_path = os.path.join(base_name, fileName)
    p_icon_preview: bpy.types.ImagePreview = ZENUV_ICONS.load(prefix + name, s_icon_path, 'IMAGE')
    if p_icon_preview:
        from ..utils.vlog import Log
        try:
            if p_icon_preview.icon_id == 0:
                raise RuntimeError("Icon has invalid ID!")
            if sum(p_icon_preview.icon_size) == 0:
                raise RuntimeError("Icon was not loaded properly!")
        except Exception as e:
            Log.error(str(e), "Name:", prefix + name, "Path:", s_icon_path)


def icon_get(name) -> int:
    global ZENUV_ICONS
    if ZENUV_ICONS is None:
        # We must not never come here !
        raise RuntimeError('It is a bug! Send log to the developers, pls :)')
    else:
        return ZENUV_ICONS[name].icon_id


_zenuv_tools_icon_path = ''
_zenuv_tools_transform_icon_path = ''


def zenuv_tool_icon():
    global _zenuv_tools_icon_path
    if _zenuv_tools_icon_path == '':
        _icons_dir = os.path.dirname(__file__)
        _zenuv_tools_icon_path = os.path.join(_icons_dir, 'zenuv_tool_icon')

    return _zenuv_tools_icon_path


def zenuv_tool_transform_icon():
    global _zenuv_tools_transform_icon_path
    if _zenuv_tools_transform_icon_path == '':
        _icons_dir = os.path.dirname(__file__)
        _zenuv_tools_transform_icon_path = os.path.join(_icons_dir, 'zenuv_transform_tool')

    return _zenuv_tools_transform_icon_path


def is_blender_icon_valid(s_icon):
    return s_icon in bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items


def register():
    global ZENUV_ICONS
    if ZENUV_ICONS is None:
        ZENUV_ICONS = bpy.utils.previews.new()

        icons_base_dir = os.path.dirname(__file__)
        icons_combo_base_dir = os.path.join(icons_base_dir, 'combo')

        for icon in icons:
            _icon_register(icon, icons_base_dir)

        for icon in icons_combo:
            _icon_register(icon, icons_combo_base_dir, 'pn_')


def unregister():
    global ZENUV_ICONS
    if ZENUV_ICONS:
        b_icon_debug = False  # Set 'True' when you are debugging icons
        if b_icon_debug:
            bpy.utils.previews.remove(ZENUV_ICONS)
            ZENUV_ICONS = None
