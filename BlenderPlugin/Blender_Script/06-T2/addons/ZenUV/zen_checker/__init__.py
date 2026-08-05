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

""" Init Zen Checker """

from bpy.utils import register_class, unregister_class
import bpy
import bpy.utils.previews

from .properties import ZUV_CheckerProperties

from .panel import register as register_checker_ui
from .panel import unregister as unregister_checker_ui

from .checker import register as register_checker
from .checker import unregister as unregister_checker

from .files import register as register_files
from .files import unregister as unregister_files

from .stretch_map import register as register_stretch_map
from .stretch_map import unregister as unregister_stretch_map

from .files import _checker_previews
from .check_utils import register as register_check_utils
from .check_utils import unregister as unregister_check_utils


addon_keymaps = []


def register():
    """ Register classes """

    register_class(ZUV_CheckerProperties)
    bpy.types.Scene.zen_uv_checker = bpy.props.PointerProperty(type=ZUV_CheckerProperties)

    register_files()
    register_checker()
    register_checker_ui()

    register_stretch_map()
    register_check_utils()

    # wm = bpy.context.window_manager
    # if wm.keyconfigs.addon:
    #     km = wm.keyconfigs.addon.keymaps.new(name='Window', space_type='EMPTY')
    #     kmi = km.keymap_items.new('view3d.zch_toggle', 'T', 'PRESS', alt=True)
    #     addon_keymaps.append((km, kmi))


def unregister():
    """ Unregister classes """

    unregister_checker_ui()
    unregister_checker()
    unregister_files()

    unregister_class(ZUV_CheckerProperties)

    if _checker_previews is not None:
        bpy.utils.previews.remove(_checker_previews)

    unregister_check_utils()
    unregister_stretch_map()

    del bpy.types.Scene.zen_uv_checker

    # wm = bpy.context.window_manager
    # kc = wm.keyconfigs.addon
    # if kc:
    #     for km, kmi in addon_keymaps:
    #         km.keymap_items.remove(kmi)
    # addon_keymaps.clear()


if __name__ == "__main__":
    pass
