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


class RegisterUtils:

    @classmethod
    def get_n_panel_name(cls):
        from ZenUV.utils.blender_zen_utils import ZenPolls
        if not ZenPolls.n_panel_name:
            from ZenUV.prop.zuv_preferences import get_prefs
            addon_prefs = get_prefs()
            ZenPolls.n_panel_name = bpy.types.UILayout.enum_item_name(
                addon_prefs, "n_panel_name", addon_prefs.n_panel_name
            )
        return ZenPolls.n_panel_name

    @classmethod
    def register_class(cls, instance):
        if issubclass(instance, bpy.types.Panel):
            if hasattr(instance, "bl_category"):
                from ZenUV.utils.generic import ZUV_PANEL_CATEGORY

                if instance.bl_category == ZUV_PANEL_CATEGORY:
                    s_n_panel_name = cls.get_n_panel_name()
                    if s_n_panel_name != ZUV_PANEL_CATEGORY:
                        instance.bl_category = s_n_panel_name

        bpy.utils.register_class(instance)

    @classmethod
    def unregister_class(cls, instance):
        bpy.utils.unregister_class(instance)

    @classmethod
    def register(cls, classes):
        for c in classes:
            cls.register_class(c)

    @classmethod
    def unregister(cls, classes):
        for c in reversed(classes):
            cls.unregister_class(c)
