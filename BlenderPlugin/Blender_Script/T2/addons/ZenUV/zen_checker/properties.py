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

""" Zen Checker Properties """

import bpy
import sys
import os
from json import loads, dumps

from .files import update_files_info, load_checker_image, get_checker_previews
from .zen_checker_labels import ZCheckerLabels as label
from .checker import zen_checker_image_update, get_materials_with_overrider

from .get_prefs import get_path, DEF_OVERRIDE_IMAGE_NAME

from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.vlog import Log


resolutions_x = []
resolutions_y = []
values_x = []
values_y = []


def get_prefs():
    from ZenUV.ui.labels import ZuvLabels
    return bpy.context.preferences.addons[ZuvLabels.ADDON_NAME].preferences


class ZUV_CheckerProperties(bpy.types.PropertyGroup):

    bl_idname = "ZenUvChecker"
    prev_color_type: bpy.props.StringProperty(name="Color Type", default='MATERIAL')

    use_custom_image: bpy.props.BoolProperty(
        name="Use Custom Image",
        description="Use custom image as Zen UV texture checker image",
        default=False)

    override_image_name: bpy.props.StringProperty(
        name='Image',
        default=DEF_OVERRIDE_IMAGE_NAME,
        # options={'HIDDEN', 'SKIP_SAVE'}
    )


class ZUV_CheckerAddonLevelProperties(bpy.types.PropertyGroup):

    bl_idname = "ZenUvCheckerProps"

    # Zen UV Checker Preferences
    def get_files_dict(self, context):
        try:
            if self.files_dict == "":
                self.files_dict = dumps(update_files_info(self.checker_assets_path))
            files_dict = loads(self.files_dict)
            return files_dict
        except Exception:
            print("Warning!", sys.exc_info()[0], "occurred.")
            self.files_dict = dumps(update_files_info(self.checker_assets_path))
            return None

    def get_x_res_list(self, context):
        """ Get resolutions list for files from files_dict """
        files_dict = self.get_files_dict(context)
        if files_dict:
            # Update info in resolutions_x list
            values_x.clear()
            for image in files_dict:
                value = files_dict[image]["res_x"]
                if value not in values_x:
                    values_x.append(value)
            values_x.sort()
            identifier = 0
            resolutions_x.clear()
            for value in values_x:
                resolutions_x.append((str(value), str(value), "", identifier))
                identifier += 1
            return resolutions_x
        return [('None', 'None', '', 0), ]

    def get_y_res_list(self, context):
        """ Fills resolutions_y depend on current value of SizeX """
        files_dict = self.get_files_dict(context)
        if files_dict:
            res_x = self.SizesX
            if res_x and res_x.isdigit():
                res_x = int(res_x)
                # If axes locked - return same value as Resolution X
                if self.lock_axes:
                    return [(str(res_x), str(res_x), "", 0)]
                identifier = 0
                values_y.clear()
                resolutions_y.clear()
                for image in files_dict:
                    value = files_dict[image]["res_y"]
                    if files_dict[image]["res_x"] == res_x and value not in values_y:
                        values_y.append(value)
                        resolutions_y.append((str(value), str(value), "", identifier))
                        identifier += 1
            if resolutions_y:
                return resolutions_y
        return [('None', 'None', '', 0), ]

    def zchecker_image_items(self, context):
        files_dict = self.get_files_dict(context)
        if files_dict:
            files = []
            identifier = 0
            # If filter disabled - return all images from dict
            if not self.chk_rez_filter:
                for image in files_dict:
                    icon_id = 'BLANK1'
                    try:
                        icon_id = get_checker_previews()[image].icon_id
                    except Exception as e:
                        print(str(e))
                    files.append((image, image, "", icon_id, identifier))
                    identifier += 1
                return files

            res_x = self.SizesX
            res_y = self.SizesY
            if res_x and res_y and res_x.isdigit() and res_y.isdigit():
                res_x = int(res_x)
                res_y = int(res_y)
                values = []
                for image in files_dict:
                    if files_dict[image]["res_x"] == res_x \
                            and files_dict[image]["res_y"] == res_y \
                            and image not in values:
                        values.append(image)

                        icon_id = 'BLANK1'
                        try:
                            icon_id = get_checker_previews()[image].icon_id
                        except Exception as e:
                            print(str(e))

                        if self.chk_orient_filter:
                            if "orient" in image:
                                files.append((image, image, "", icon_id, identifier))
                                identifier += 1
                        else:
                            files.append((image, image, "", icon_id, identifier))
                            identifier += 1
            if files:
                return files
        return [('None', 'None', '', 0), ]

    def dynamic_update_function(self, context: bpy.types.Context):
        try:
            if self.dynamic_update and get_materials_with_overrider(bpy.data.materials):
                self.checker_presets_update_function(context)
            self.update_mark_dirty(context)
        except Exception as e:
            Log.error("CHECKER DYN UPDATE:", e)

    def update_x_res(self, context: bpy.types.Context):
        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        addon_prefs["SizesY"] = 0
        addon_prefs["ZenCheckerImages"] = 0
        self.dynamic_update_function(context)

    def update_orient_switch(self, context: bpy.types.Context):
        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        if self.chk_orient_filter:
            addon_prefs["SizesX"] = 1
            addon_prefs["SizesY"] = 0
        addon_prefs["ZenCheckerImages"] = 0
        self.dynamic_update_function(context)

    def update_y_res(self, context):
        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        addon_prefs["ZenCheckerImages"] = 0
        self.dynamic_update_function(context)

    def dynamic_update_function_overall(self, context):
        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        addon_prefs["SizesY"] = 0
        addon_prefs["ZenCheckerImages"] = 0
        if self.dynamic_update:
            materials_with_overrider = get_materials_with_overrider(bpy.data.materials)
            # print("Mats with overrider in bpy.data: ", materials_with_overrider)
            if materials_with_overrider:
                self.checker_presets_update_function(context)

    def checker_presets_update_function(self, context):
        try:
            from ZenUV.zen_checker.checker import get_zen_checker_image
            image = get_zen_checker_image(context)
            if image:
                zen_checker_image_update(context, image)
            else:
                # print("Image not Loaded. Load image ", self.ZenCheckerPresets)
                image = load_checker_image(context, self.ZenCheckerImages)
                if image:
                    zen_checker_image_update(context, image)
            # self.show_checker_in_uv_layout(context)
            self.update_mark_dirty(context)
        except Exception as e:
            Log.error("CHECKER PRESETS UPDATE:", e)

    def update_checker_assets_path(self, context):
        self.files_dict = dumps(update_files_info(self.checker_assets_path))

    def update_mark_dirty(self, context: bpy.types.Context):
        if not context.preferences.is_dirty:
            context.preferences.is_dirty = True

    checker_assets_path: bpy.props.StringProperty(
        name=label.PROP_ASSET_PATH,
        subtype='DIR_PATH',
        default=os.path.join(get_path(), "images"),
        update=update_checker_assets_path
    )

    files_dict: bpy.props.StringProperty(
        name="Zen Checker Files Dict",
        default="",
        update=update_mark_dirty
    )

    dynamic_update: bpy.props.BoolProperty(
        name=label.PROP_DYNAMIC_UPDATE_LABEL,
        description=label.PROP_DYNAMIC_UPDATE_DESC,
        default=True,
        update=update_mark_dirty
    )

    ZenCheckerPresets: bpy.props.EnumProperty(
        name=label.CHECKER_PRESETS_LABEL,
        description=label.CHECKER_PRESETS_DESC,
        items=[
            ('Zen-UV-512-colour.png', 'Zen Color 512x512', '', 1),
            ('Zen-UV-1K-colour.png', 'Zen Color 1024x1024', '', 2),
            ('Zen-UV-2K-colour.png', 'Zen Color 2048x2048', '', 3),
            ('Zen-UV-4K-colour.png', 'Zen Color 4096x4096', '', 4),
            ('Zen-UV-512-mono.png', 'Zen Mono 512x512', '', 5),
            ('Zen-UV-1K-mono.png', 'Zen Mono 1024x1024', '', 6),
            ('Zen-UV-2K-mono.png', 'Zen Mono 2048x2048', '', 7),
            ('Zen-UV-4K-mono.png', 'Zen Mono 4096x4096', '', 8)],
        default="Zen-UV-1K-colour.png",
        update=checker_presets_update_function
    )

    lock_axes: bpy.props.BoolProperty(
        name=label.PROP_LOCK_AXES_LABEL,
        description=label.PROP_LOCK_AXES_DESC,
        default=True,
        update=update_x_res
    )

    chk_rez_filter: bpy.props.BoolProperty(
        name=label.PROP_RES_FILTER_LABEL,
        description=label.PROP_RES_FILTER_DESC,
        default=False,
        update=update_x_res
    )

    chk_orient_filter: bpy.props.BoolProperty(
        name=label.PROP_ORIENT_FILTER_LABEL,
        description=label.PROP_ORIENT_FILTER_DESC,
        default=False,
        update=update_orient_switch
    )

    SizesX: bpy.props.EnumProperty(
        name='X Resolution',
        description=label.PROP_TEXTURE_X_DESC,
        items=get_x_res_list,
        update=update_x_res
    )

    SizesY: bpy.props.EnumProperty(
        name='Y Resolution',
        description=label.PROP_TEXTURE_Y_DESC,
        items=get_y_res_list,
        update=update_y_res
    )

    ZenCheckerImages: bpy.props.EnumProperty(
        name='Zen Checker Images',
        items=zchecker_image_items,
        update=checker_presets_update_function
    )


classes = [
    ZUV_CheckerAddonLevelProperties,
]


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)


if __name__ == '__main__':
    pass
