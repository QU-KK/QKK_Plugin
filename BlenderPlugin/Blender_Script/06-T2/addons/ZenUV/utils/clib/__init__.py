
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

from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty

import addon_utils

from shutil import copy, copy2
import os
from pathlib import Path

from ...utils.register_util import RegisterUtils
from ...utils.clib.lib_init import (
    register_library, unregister_library,
    get_zenlib_name, is_zenlib_present, get_zenlib_path, get_zenlib_temp_path)
from ...ui.labels import ZuvLabels
from ...utils.constants import zenuv_update_filename, zenuv_update_filter
from ...utils.blender_zen_utils import are_paths_equal_pathlib, ZenPolls
from ...utils.vlog import Log


def manage_library_in_temp_folder(create_or_delete: bool):
    try:
        s_zen_lib_path = get_zenlib_path()
        s_temp_file_name = get_zenlib_temp_path()

        if create_or_delete:
            if is_zenlib_present():
                copy2(s_zen_lib_path, s_temp_file_name)
        else:
            if os.path.exists(s_temp_file_name):
                os.remove(s_temp_file_name)

    except Exception as e:
        Log.error("STORE CLIB IN TEMP:", e)


class ZUVLibrary_OT_InstallFile(Operator, ImportHelper):
    bl_idname = "view3d.zenuv_install_library"
    bl_label = "Install " + ZuvLabels.CLIB_NAME
    bl_description = "Install and Register Zen UV Dynamic Library"

    def extension():
        _, file_extension = os.path.splitext(get_zenlib_name())
        return file_extension

    use_filter = True
    filter_glob: StringProperty(
        default=f"*{extension()}",
        options={'HIDDEN'}
    )
    files: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    filename: StringProperty(maxlen=1024, subtype="FILE_NAME")
    directory: StringProperty(maxlen=1024, subtype="DIR_PATH")

    def check(self, context: bpy.types.Context):
        s_path = get_zenlib_path()
        self.filename = get_zenlib_name()
        if os.path.exists(s_path):
            self.filepath = s_path

    def execute(self, context: bpy.types.Context):
        try:
            s_library_name = get_zenlib_name()
            s_selected_name = os.path.basename(self.filepath)
            if s_library_name.lower() != s_selected_name.lower():
                raise RuntimeError(f'Expected: {s_library_name}, but selected: {s_selected_name}')

            path = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + s_library_name

            # Only if we didn't change path
            if is_zenlib_present() and (self.filepath.lower() == path.lower()):
                self.report({"INFO"}, ZuvLabels.CLIB_NAME + " is already installed. Trying to activate...")
                register_library()
            else:
                # Copy Library to
                copy(self.filepath, path)
                print("Zen UV: File ", self.filepath)
                print("          Copied to: ", path)

                if is_zenlib_present():
                    register_library()
                    self.report({"INFO"}, ZuvLabels.CLIB_NAME + " was installed!")
                else:
                    self.report({"ERROR"}, "For some reason, the library cannot be installed. Try to do it manually")

            manage_library_in_temp_folder(True)

        except Exception as e:
            self.report({'ERROR'}, str(e))

        for win in context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()

        # Do not use 'CANCELLED' because file path is not stored
        return {'FINISHED'}


class ZUVLibrary_OT_Check(Operator):
    bl_idname = "view3d.zenuv_check_library"
    bl_label = "Check Library"
    bl_description = "Check Zen UV Dynamic Library"

    def execute(self, context):
        # addon_prefs = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences
        if is_zenlib_present():
            # addon_prefs.zen_lib = True
            self.report({"INFO"}, "The library is already installed.  Trying to activate...")
            register_library()
        else:
            self.report({"WARNING"}, "The library is not found. First, install in the Zen UV settings.")
        return {'FINISHED'}


class ZUV_OT_Update(Operator, ImportHelper):
    bl_idname = "uv.zenuv_update_addon"
    bl_label = "Update Zen UV"
    bl_description = "Update Zen UV add-on"

    filename_ext = ".zip"
    use_filter = True
    filter_glob: StringProperty(
        default=zenuv_update_filter,
        options={'HIDDEN'}
    )
    files: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)
    filename: StringProperty(maxlen=1024, subtype="FILE_NAME")
    directory: StringProperty(maxlen=1024, subtype="DIR_PATH")

    keep_core_library: bpy.props.BoolProperty(
        name="Keep Zen UV Core Library",
        description="If option is set, Zen UV core library will be saved to temporary placed and will be restored after the addon upgrade",
        default=True
    )

    def check(self, context):
        self.filename = zenuv_update_filename

    def execute(self, context):
        message = "Zen UV: Select only one *.zip file containing an addon."
        message_02 = "Zen UV: The file should be the type of ZenUV_x_x.zip."
        if not self.files or len(self.files) > 1:
            self.report({"WARNING"}, message)
            return {'CANCELLED'}
        filename, extension = os.path.splitext(self.filepath)
        if extension != '.zip':
            self.report({"WARNING"}, message)
            return {'CANCELLED'}
        file = self.files[0]
        if not file.name.startswith("ZenUV"):
            self.report({"WARNING"}, message_02)
            return {'CANCELLED'}

        fullname = os.path.join(self.directory, file.name)
        print("Zen UV: Updating by ", fullname)

        unregister_library()

        manage_library_in_temp_folder(True)

        s_install_target = "DEFAULT"

        paths = context.preferences.filepaths

        s_root_addons = Path(ZenPolls.ADDON_DIR).parent

        try:
            for script_directory in paths.script_directories:
                s_script_addons = os.path.join(script_directory.directory, "addons")
                if are_paths_equal_pathlib(s_script_addons, s_root_addons):
                    s_install_target = script_directory.name
                    self.report({'INFO'}, f"Addon is installing to custom directory: {s_install_target}")
                    break
        except Exception as e:
            Log.error("ADDON UPDATE:", e)

        if ZenPolls.version_since_4_2_0 and addon_utils.check_extension(ZenPolls.ADDON_PACKAGE):

            from bl_pkg import repo_paths_or_none  # type: ignore

            s_repo = ""

            extension_repos = context.preferences.extensions.repos
            for repo_item in extension_repos:
                if not repo_item.enabled:
                    continue
                directory, _repo_path = repo_paths_or_none(repo_item)
                if directory is None:
                    continue

                if are_paths_equal_pathlib(directory, s_root_addons):
                    s_repo = repo_item.module
                    break

            if s_repo:

                return bpy.ops.extensions.package_install_files(
                    'INVOKE_DEFAULT',
                    url=fullname,
                    repo=s_repo
                )

            else:
                self.report({'ERROR'}, "Extension repository is disabled or missing! Update manually!")
        else:
            bpy.ops.preferences.addon_install(
                overwrite=True,
                target=s_install_target,
                filepath=fullname,
                filter_folder=True,
                filter_python=True,
                filter_glob="*.zip"
            )

        return {'FINISHED'}


class ZUVLibrary_OT_Unregister(Operator):
    bl_idname = "uv.zenuv_unregister_library"
    bl_label = "Unregister Zen UV Core Library"
    bl_description = "Library will be deleted from application memory, so it will be available to be deleted from disk or reinstalled"

    def execute(self, context):

        unregister_library()

        # manage_library_in_temp_folder(False)

        for win in context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()

        return {'FINISHED'}


classes = (
    ZUVLibrary_OT_InstallFile,
    ZUVLibrary_OT_Check,
    ZUVLibrary_OT_Unregister,
    ZUV_OT_Update
)


def register():
    RegisterUtils.register(classes)

    register_library()


def unregister():
    RegisterUtils.unregister(classes)

    unregister_library()


if __name__ == "__main__":
    pass
