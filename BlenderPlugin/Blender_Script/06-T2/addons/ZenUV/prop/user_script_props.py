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

# Copyright 2023, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy
from bpy_extras.io_utils import ImportHelper

import os
import shutil

from ZenUV.utils.blender_zen_utils import ZuvPresets
from ZenUV.utils.vlog import Log
from ZenUV.prop.common import update_addon_prop


class ZUV_UserScriptProps(bpy.types.PropertyGroup):
    active: bpy.props.BoolProperty(
        name='Active',
        description="""Activate user script which will be loaded when addon is started
* Requires Blender restart""",
        default=False,
        update=update_addon_prop
    )

    file_path: bpy.props.StringProperty(
        name='User Script Path',
        description="""File path to user script which will be loaded when addon is started
* Requires Blender restart""",
        default='',
        update=update_addon_prop
    )

    def draw(self, layout: bpy.types.UILayout, context: bpy.types.Context):
        box = layout.box()
        box.active = self.active

        row = box.row(align=True)

        r = row.row(align=True)
        r.alert = box.active and not os.path.exists(self.file_path)
        r.prop(self, 'active', text='')
        r.prop(self, 'file_path')

        r2 = row.row(align=True)
        r2.alignment = 'RIGHT'
        r2.operator(ZUV_OT_UserScriptTemplate.bl_idname, text='New', icon='ADD')
        r2.operator(ZUV_OT_UserScriptSelect.bl_idname, text='Select', icon='FILEBROWSER')


class ZUV_OT_UserScriptSelect(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.zuv_user_script_select"
    bl_label = "Select User Script"
    bl_description = """Select user script which will be loaded when addon is started
* Requires Blender restart"""
    bl_options = {'INTERNAL'}

    filename_ext = ".py"
    filter_glob: bpy.props.StringProperty(default="*.py", options={'HIDDEN'})

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        from ZenUV.prop.zuv_preferences import get_prefs

        addon_prefs = get_prefs()

        try:
            if not addon_prefs.user_script.file_path:
                source_dir = os.path.join(os.path.dirname(__file__))
                # TODO: require checks Linux, Mac OS
                self.filepath = os.path.join(source_dir, '../user_data/user_scripts/')
            else:
                self.filepath = addon_prefs.user_script.file_path
        except Exception as e:
            Log.error('SET DIR:', e)

        return super().invoke(context, event)

    def execute(self, context: bpy.types.Context):
        try:
            from ZenUV.prop.zuv_preferences import get_prefs

            addon_prefs = get_prefs()
            addon_prefs.user_script.file_path = self.filepath

            context.preferences.is_dirty = True

            bpy.ops.text.open(
                filepath=self.filepath
            )

            self.report({'INFO'}, "See 'user_script.py' in text editor and restart Blender!")

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_UserScriptTemplate(bpy.types.Operator):
    bl_idname = "wm.zuv_user_script_template"
    bl_label = "Create User Script"
    bl_description = """Create and activate user script template
WARNING! File 'user_script.py' will be overreded in addon presets folder!
* Requires Blender restart"""
    bl_options = {'INTERNAL'}

    def get_templates(self, context):
        items = []
        source_dir = os.path.join(os.path.dirname(__file__))
        user_dir = os.path.join(source_dir, '../user_data/user_scripts')
        for file in os.listdir(user_dir):
            s_file_path = os.path.join(user_dir, file)
            if os.path.isfile(s_file_path):
                if s_file_path.lower().endswith('.py'):
                    items.append((file, file, s_file_path))

        t_items = bpy.app.driver_namespace.get('zenuv_user_script_templates', [])
        if items != t_items:
            bpy.app.driver_namespace['zenuv_user_script_templates'] = items

        return bpy.app.driver_namespace.get('zenuv_user_script_templates', [])

    templates: bpy.props.EnumProperty(
        name='Templates',
        description='User script templates',
        items=get_templates
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()

        try:
            if self.templates:

                source = bpy.types.UILayout.enum_item_description(self, 'templates', self.templates)

                s_preset_path = ZuvPresets.force_full_preset_path('user_scripts')
                target = os.path.join(s_preset_path, self.templates)
                shutil.copy2(source, target)

                addon_prefs.user_script.file_path = target
                addon_prefs.user_script.active = True

                context.preferences.is_dirty = True

                bpy.ops.text.open(
                    filepath=target
                )

                self.report({'INFO'}, f"See '{self.templates}' in text editor and restart Blender!")

                return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}
