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
import bmesh
import addon_utils

from dataclasses import dataclass
import itertools
import os
import sys

from ZenUV.ui.labels import ZuvLabels
from bpy.props import BoolProperty
from ZenUV.utils.generic import fit_uv_view, UvImage
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

from ZenUV.utils.blender_zen_utils import ZenPolls

from ZenUV.utils.vlog import Log

from .pack_utils import PackObjectsStorage, PackUtils
from .uvpm_props import get_main_props


@dataclass
class UnifiedPackerProps:

    result: bool = False
    message: str = ''
    raise_popup_id_name: str = None


class UVPmData:
    packmaster_names = {'UVPackmaster3', 'UVPackmaster 3', 'UVPackmaster 2', 'UVPackmaster2'}

    _CACHE_UVPM_VERSION = None
    _CACHE_UVPM_PATH = None
    _CACHE_UVPM_PACK_PANELS = None
    _CACHE_UVPM_PACKAGE = None

    @classmethod
    def update_data(cls):
        if cls._CACHE_UVPM_VERSION is None:
            for addon in addon_utils.modules():
                if addon.bl_info['name'] in cls.packmaster_names:
                    ver = addon.bl_info['version']
                    cls._CACHE_UVPM_VERSION = (ver[0], ver[1], ver[2])
                    cls._CACHE_UVPM_PACKAGE = addon.__name__
                    cls._CACHE_UVPM_PATH = os.path.dirname(addon.__file__)
                    break

    @classmethod
    def get_packmaster_version(cls):
        cls.update_data()
        return cls._CACHE_UVPM_VERSION

    @classmethod
    def get_packmaster_path(cls):
        cls.update_data()
        return cls._CACHE_UVPM_PATH

    @classmethod
    def get_packmaster_pack_panels_module(cls):
        if cls._CACHE_UVPM_PACK_PANELS is None:
            for mod in sys.modules:
                if mod.endswith('scripted_pipeline.panels.pack_panels'):
                    cls._CACHE_UVPM_PACK_PANELS = sys.modules[mod]
        return cls._CACHE_UVPM_PACK_PANELS

    @classmethod
    def get_packmaster_package(cls):
        cls.update_data()
        return cls._CACHE_UVPM_PACKAGE

    @classmethod
    def get_packmaster_prefs(cls):
        cls.update_data()
        if cls._CACHE_UVPM_PACKAGE:
            p_addon = bpy.context.preferences.addons.get(cls._CACHE_UVPM_PACKAGE, None)
            if p_addon:
                return p_addon.preferences
        return None


class UVPmPoll:

    # Reason: Changes in the API. Changed way to get addon properties
    @classmethod
    def version_since_3_4_0(cls):
        current_version = UVPmData.get_packmaster_version()
        if current_version is None:
            return False
        return current_version >= (3, 4, 0)

    # Reason: Changes in the API. fixed_scale changed to scale_mode ENUM
    @classmethod
    def version_since_3_3_3(cls):
        current_version = UVPmData.get_packmaster_version()
        if current_version is None:
            return False
        return current_version >= (3, 3, 3)

    # Reason: Changes in the API. pack_to_others=False changed to pack_op_type='0'
    @classmethod
    def version_since_3_3_2(cls):
        current_version = UVPmData.get_packmaster_version()
        if current_version is None:
            return False
        return current_version >= (3, 3, 2)

    # Reason: Changes in the API.
    @classmethod
    def version_since_3(cls):
        current_version = UVPmData.get_packmaster_version()
        if current_version is None:
            return False
        return current_version >= (3, 0, 0)

    # Reason: first supported version
    @classmethod
    def version_2(cls):
        current_version = UVPmData.get_packmaster_version()
        if current_version is None:
            return False
        return current_version < (3, 0, 0)


class GenericPackerManager(UnifiedPackerProps):

    def __init__(self, context, addon_prefs) -> None:
        self.context: bpy.types.Context = context
        self.addon_prefs: bpy.types.AddonPreferences = addon_prefs
        self.packer_parsed_props = {"generic": "generic"}
        self.packer_name: str = None
        self.stored_props = None
        self.packer_props_pointer = None
        self.show_transfer: bool = False
        self.raise_popup_id_name: str = None

    def pack(self):
        return False

    def get_engine_version(self, context):
        return False

    # PROTECTED
    # this method must be overrided in all derived classes !!!
    def _is_engine_present(self):
        return False

    def _store_packer_props(self):
        self.stored_props = dict()
        for attr in self.packer_parsed_props.keys():
            p_attr = getattr(self.packer_props_pointer, attr, None)
            if p_attr is None:
                for p_attr in self.packer_parsed_props.keys():
                    pass
                self.stored_props = None
                return None
            self.stored_props.update({attr: p_attr})

        return self.stored_props

    def _restore_packer_props(self):
        for attr in self.packer_parsed_props.keys():
            try:
                setattr(self.packer_props_pointer, attr, self.stored_props[attr])
            except Exception:
                return False
        if self.show_transfer:
            print(f"\nRestored Packer Props: {self.stored_props}\n")
        return True

    def _is_attribute_real(self, attrib):
        if isinstance(attrib, str):
            if getattr(self.addon_prefs, attrib, "NOT_PASSED") == "NOT_PASSED":
                return False
            return True
        return False

    def _trans_props_zen_to_packer(self):
        for packer_attr, zuv_attr in self.packer_parsed_props.items():
            try:
                if self._is_attribute_real(zuv_attr):
                    if self.show_transfer:
                        print(f"attr type: {type(zuv_attr)}.\t{self.packer_name}: {packer_attr} -> {getattr(self.packer_props_pointer, packer_attr)}, Zen UV: {zuv_attr} -> {getattr(self.addon_prefs, zuv_attr, False)}")
                    setattr(self.packer_props_pointer, packer_attr, getattr(self.addon_prefs, zuv_attr))

                else:
                    if self.show_transfer:
                        print(f"attr type: {type(zuv_attr)}.\t{self.packer_name}: {packer_attr} -> {getattr(self.packer_props_pointer, packer_attr)}, Zen UV: {zuv_attr} -> {self.packer_parsed_props[packer_attr]}")
                    setattr(self.packer_props_pointer, packer_attr, zuv_attr)

            except Exception:
                if self.show_transfer:
                    print(f"\nError in: {packer_attr}. Value: {getattr(self.packer_props_pointer, packer_attr)}")
                    print(f"\t\t{self.packer_name}: {packer_attr}, Zen UV: {zuv_attr}: {getattr(self.addon_prefs, zuv_attr, 'UNDEFINED')}, Type: {type(zuv_attr)}\n")


class UVPackerManager(GenericPackerManager):

    def __init__(self, context, addon_prefs) -> None:
        GenericPackerManager.__init__(self, context, addon_prefs)
        self.packer_parsed_props = {
            "uvp_width": "TD_TextureSizeX",
            "uvp_height": "TD_TextureSizeY",
            "uvp_rescale": "averageBeforePack",
            "uvp_prerotate": "rotateOnPack",
            "uvp_rotate": None,
            "uvp_padding": None,
            "uvp_selection_only": "packSelectedIslOnly",
        }
        self.packer_name = "UV-Packer"
        self.show_transfer = False

    def pack(self, context: bpy.types.Context, Storage: PackObjectsStorage, addon_prefs: bpy.types.AddonPreferences):
        print("Zen UV - Pack: UV-Packer Engine activated.")
        if UvImage.get_aspect(context) != 1.0:
            print('UV-Packer can not pack correctly if UV Editor image is non-square.')
        self.result, self.message = self._do_pack(context, Storage, addon_prefs)

    def _is_engine_present(self):
        if hasattr(bpy.types, bpy.ops.uvpackeroperator.packbtn.idname()):
            if hasattr(self.context.scene, "UVPackerProps") and hasattr(self.context.scene.UVPackerProps, "uvp_padding"):
                if self.show_transfer:
                    print("Engine present. Props Pointer created.")
                self.packer_props_pointer = self.context.scene.UVPackerProps
                return True
        return False

    def _do_pack(self, context: bpy.types.Context, Storage: PackObjectsStorage, addon_prefs: bpy.types.AddonPreferences):

        if not self._is_engine_present():
            self.raise_popup_id_name = 'ZUV_MT_ZenPack_Uvpacker_Popup'
            return False, f"Nothing is produced. Seems like {self.packer_name} is not installed on your system."

        self._store_packer_props()

        if self.stored_props is None:
            return False, 'No UVPacker properties found.'

        # Setting additional Packer Properties
        self.packer_parsed_props["uvp_rotate"] = self.context.scene.UVPackerProps.uvp_rotate
        if not addon_prefs.rotateOnPack:
            self.packer_parsed_props["uvp_rotate"] = "0"
        self.packer_parsed_props["uvp_padding"] = self.context.scene.zen_uv.pack_uv_packer_margin

        self._trans_props_zen_to_packer()

        if addon_prefs.packSelectedIslOnly is False and Storage.is_hidden_faces_in_objects():
            PackUtils.resolve_pack_selected_only(context, addon_prefs, Storage, set_sel_only=True)
            context.scene.UVPackerProps.uvp_selection_only = True
        elif addon_prefs.packSelectedIslOnly is True and Storage.is_hidden_faces_in_objects():
            PackUtils.resolve_pack_selected_only(context, addon_prefs, Storage)
            context.scene.UVPackerProps.uvp_selection_only = True
        else:
            PackUtils.resolve_pack_selected_only(context, addon_prefs, Storage)

        res = True
        out_msg = []

        try:
            if not bpy.ops.uvpackeroperator.packbtn.poll():
                raise RuntimeError(f"For some reason, {self.packer_name} cannot be launched. Check out its performance separately from Zen UV.")

            bpy.ops.uvpackeroperator.packbtn('INVOKE_DEFAULT')
            out_msg.append("Finished")
        except Exception as e:
            res = False
            out_msg.append(str(e))

        restored = self._restore_packer_props()

        if not restored:
            res = False
            out_msg.append(f"The properties of the {self.packer_name} are not restored.")

        return res, '.'.join(out_msg)


class UVPMmanager(GenericPackerManager):

    def __init__(self, context, addon_prefs) -> None:
        GenericPackerManager.__init__(self, context, addon_prefs)

        self.uvp_3_3_3_parsed_props = {
            "margin": "margin",
            "rotation_enable": "rotateOnPack",
            "lock_overlapping_enable": "lock_overlapping_enable",
            "lock_overlapping_mode": "lock_overlapping_mode",
            "scale_mode": "1" if addon_prefs.packFixedScale else "0",
            "heuristic_enable": False,
            "normalize_scale": "averageBeforePack",  # Changed var name in UVPackmaster 3.2
            # "pack_to_others": False,
            "use_blender_tile_grid": False,
            "tex_ratio": False
        }
        self.uvp_3_2_parsed_props = {
            "margin": "margin",
            "rotation_enable": "rotateOnPack",
            "lock_overlapping_enable": "lock_overlapping_enable",
            "lock_overlapping_mode": "lock_overlapping_mode",
            "fixed_scale": "packFixedScale",
            "heuristic_enable": False,
            "normalize_scale": "averageBeforePack",  # Changed var name in UVPackmaster 3.2
            # "pack_to_others": False,
            "use_blender_tile_grid": False,
            "tex_ratio": False
        }
        self.uvp_3_parsed_props = {
            "margin": "margin",
            "rotation_enable": "rotateOnPack",
            "lock_overlapping_enable": "lock_overlapping_enable",
            "lock_overlapping_mode": "lock_overlapping_mode",
            "fixed_scale": "packFixedScale",
            "heuristic_enable": False,
            "normalize_islands": "averageBeforePack",
            # "pack_to_others": False,
            "use_blender_tile_grid": False,
            "tex_ratio": False
        }
        self.uvp_2_parsed_props = {
            "margin": "margin",
            "rot_enable": "rotateOnPack",
            "lock_overlapping_mode": "lock_overlapping_mode",
            "fixed_scale": "packFixedScale",
            "heuristic_enable": False,
            "normalize_islands": "averageBeforePack",
            "pack_to_others": False,
            "use_blender_tile_grid": False,
            "tex_ratio": False
        }

        self.uvpm_version = None
        self.packer_name = "UV Packmaster"
        self.show_transfer = False
        self.disable_overlay = False
        self.stored_t_b = None

    def pack(self, context, Storage: PackObjectsStorage, addon_prefs, disable_overlay):
        print("Zen UV - Pack: UV Packmaster Engine activated.")

        PackUtils.resolve_pack_selected_only(context, addon_prefs, Storage)

        self.is_pack_in_trim(context, addon_prefs)

        # Disable UVP Overlay case HOps display is on.
        if addon_prefs.hops_uv_activate is True:
            self.disable_overlay = True
            print('Zen UV message: UVP Overlay is temporarily disabled. Reason - HOps UV Display is On . Only one overlay info can be activated.')
        else:
            self.disable_overlay = disable_overlay

        self.result, self.message = self._do_pack(context)
        self.raise_popup_id_name = self.raise_popup_id_name

        # bpy.ops.mesh.select_all(action='DESELECT')
        PackUtils.bpy_select_by_context(context, action='DESELECT')
        self.restore_uvpm3_target_box(context)

    def get_engine_version(self, context: bpy.types.Context):
        p_version = UVPmData.get_packmaster_version()
        Log.debug('Pack', f'detected version {p_version = }')
        self.uvpm_version = p_version
        if UVPmPoll.version_since_3_4_0():
            self.packer_props_pointer = get_main_props(context)
            if self.packer_props_pointer:
                self.packer_parsed_props = self.uvp_3_3_3_parsed_props
            else:
                return None

        elif UVPmPoll.version_since_3_3_3():
            if hasattr(self.context.scene, "uvpm3_props"):
                self.packer_parsed_props = self.uvp_3_3_3_parsed_props
                self.packer_props_pointer = self.context.scene.uvpm3_props
            else:
                return None

        elif UVPmPoll.version_since_3_3_2():
            if hasattr(self.context.scene, "uvpm3_props"):
                self.packer_parsed_props = self.uvp_3_2_parsed_props
                self.packer_props_pointer = self.context.scene.uvpm3_props
            else:
                return None

        elif UVPmPoll.version_since_3():
            if hasattr(self.context.scene, "uvpm3_props"):
                if hasattr(self.context.scene.uvpm3_props, 'normalize_scale'):
                    self.packer_parsed_props = self.uvp_3_2_parsed_props
                    self.packer_props_pointer = self.context.scene.uvpm3_props
                else:
                    self.packer_parsed_props = self.uvp_3_parsed_props
                    self.packer_props_pointer = self.context.scene.uvpm3_props

            else:
                return None

        elif UVPmPoll.version_2():
            if hasattr(self.context.scene, "uvp2_props"):
                self.packer_parsed_props = self.uvp_2_parsed_props
                self.packer_props_pointer = self.context.scene.uvp2_props
            else:
                return None

        else:
            return None

        return p_version

    def is_pack_in_trim(self, context: bpy.types.Context, addon_prefs) -> bool:
        if UVPmPoll.version_since_3_4_0():
            uvpm3_props = get_main_props(context)
        elif not UVPmPoll.version_since_3():
            Log.debug(self.uvpm_version)
            Log.debug('uvpm_ver_not_3')
            self.raise_message('uvpm_ver_not_3')
            return False
        else:
            uvpm3_props = context.scene.uvpm3_props

        t_b_props = uvpm3_props.custom_target_box

        trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if trim is None:
            self.raise_message('active_trim_is_none')
            return False

        self.stored_t_b = [
            t_b_props.p1_x,
            t_b_props.p1_y,
            t_b_props.p2_x,
            t_b_props.p2_y,
            uvpm3_props.custom_target_box_enable
        ]
        rect = trim.rect

        uvpm3_props.custom_target_box_enable = addon_prefs.packInTrim
        t_b_props.p1_x = rect[0]
        t_b_props.p1_y = rect[3]
        t_b_props.p2_x = rect[2]
        t_b_props.p2_y = rect[1]

        return True

    def restore_uvpm3_target_box(self, context: bpy.types.Context) -> bool:
        if self.stored_t_b is None:
            return False
        if UVPmPoll.version_since_3_4_0():
            uvpm3_props = get_main_props(context)
        else:
            uvpm3_props = context.scene.uvpm3_props
        t_b_props = uvpm3_props.custom_target_box
        uvpm3_props.custom_target_box_enable = self.stored_t_b[4]

        t_b_props.p1_x = self.stored_t_b[0]
        t_b_props.p1_y = self.stored_t_b[1]
        t_b_props.p2_x = self.stored_t_b[2]
        t_b_props.p2_y = self.stored_t_b[3]

        return True

    def transfer_attrs_to_uvpm(self):
        self._trans_props_zen_to_packer()

    def set_image_aspect_correction(self, context: bpy.types.Context):
        if UvImage.get_aspect(context) != 1.0:
            self.packer_props_pointer.tex_ratio = True


    def _do_pack(self, context: bpy.types.Context):

        ZsPieFactory.mark_pie_cancelled()

        if not self.get_engine_version(context):
            self.raise_popup_id_name = 'ZUV_MT_ZenPack_Uvp_Popup'
            return False, self.raise_message("engine_not_present")

        print(f"Zen UV: UVPMmanager: Pack Engine UV Packmaster {self.uvpm_version} detected.")

        if not self.packer_props_pointer:
            return False, self.raise_message("props_error")

        self._store_packer_props()

        if not self.stored_props:
            return False, self.raise_message("props_not_found")

        self._trans_props_zen_to_packer()

        self.set_image_aspect_correction(context)

        try:
            if UVPmPoll.version_since_3_4_0():
                if bpy.ops.uvpackmaster3.pack.poll():
                    p_prefs = UVPmData.get_packmaster_prefs()
                    if not p_prefs:
                        raise RuntimeError("Can not get UVPackmaster preferences!")

                    active_mode = p_prefs.get_active_main_mode(context)

                    if self.disable_overlay:
                        bpy.ops.uvpackmaster3.pack(mode_id=active_mode.MODE_ID, pack_op_type='0')
                    else:
                        bpy.ops.uvpackmaster3.pack("INVOKE_DEFAULT", mode_id=active_mode.MODE_ID, pack_op_type='0')
                else:
                    return False, self.raise_message("engine_error")

            elif UVPmPoll.version_since_3_3_2():
                if bpy.ops.uvpackmaster3.pack.poll():
                    if self.disable_overlay:
                        bpy.ops.uvpackmaster3.pack(mode_id=self.context.scene.zen_uv.uvp3_packing_method, pack_op_type='0')
                    else:
                        bpy.ops.uvpackmaster3.pack("INVOKE_DEFAULT", mode_id=self.context.scene.zen_uv.uvp3_packing_method, pack_op_type='0')
                else:
                    return False, self.raise_message("engine_error")

            elif UVPmPoll.version_since_3():
                if bpy.ops.uvpackmaster3.pack.poll():
                    if self.disable_overlay:
                        bpy.ops.uvpackmaster3.pack(mode_id=self.context.scene.zen_uv.uvp3_packing_method, pack_to_others=False)
                    else:
                        bpy.ops.uvpackmaster3.pack("INVOKE_DEFAULT", mode_id=self.context.scene.zen_uv.uvp3_packing_method, pack_to_others=False)
                else:
                    return False, self.raise_message("engine_error")

            elif UVPmPoll.version_2():
                if not bpy.ops.uvpackmaster2.uv_pack.poll():
                    self._restore_packer_props()
                    raise RuntimeError(f"For some reason, {self.packer_name} cannot be launched. Check out its performance separately from Zen UV.")
                else:
                    if self.disable_overlay:
                        bpy.ops.uvpackmaster2.uv_pack()
                    else:
                        bpy.ops.uvpackmaster2.uv_pack("INVOKE_DEFAULT")

        except Exception as e:
            self._restore_packer_props()
            from ZenUV.utils.messages import zen_message
            zen_message(context, str(e))
            return False, str(e)

        restored = self._restore_packer_props()
        if not restored:
            return False, self.raise_message("restore_props_error")

        return True, self.raise_message("finished")

    def raise_message(self, err_type):
        messages = {
            "detected_engine": f"Zen UV: UVPMmanager: Pack Engine UV Packmaster {self.uvpm_version} detected.",
            "props_error": "Some Properties of UV Packmaster cannot be found. Update UV Packmaster to the latest version.",
            "restore_props_error": "Property restoring error.",
            "engine_not_present": "Nothing is produced. Seems like UV Packmaster is not installed on your system.",
            "props_not_found": "No UVPackmaster properties found.",
            "finished": "Finished.",
            "err_finished": "Finished with Errors.",
            "poll_failed": "For some reason, UVPackmaster cannot be launched. Check out its performance separately from Zen UV.",
            "uvpm_ver_not_3": "Supported only in UV Packmaster v3",
            "active_trim_is_none": "There are no Active Trim.",
            "engine_error": "For some reason operator can not be launched. Check UV Packmaster panel"
        }
        if err_type in messages.keys():
            out_message = f"Zen UV: {messages[err_type]}"
            if self.show_transfer:
                print(out_message)
        else:
            out_message = "Zen UV: UVPMmanager: Message is not classified."
            if self.show_transfer:
                print(out_message)

        return out_message


class BlenderPackManager(UnifiedPackerProps):

    def __init__(self, context) -> None:
        self.show_transfer = False
        self.is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

    def is_pack_allowed(cls):
        if ZenPolls.version_equal_3_6_0:
            return False
        return True

    def pack(self, context: bpy.types.Context, Storage: PackObjectsStorage, addon_prefs: bpy.types.AddonPreferences, fast_mode: bool):
        print("Zen UV - Pack: Blender Engine activated.")
        if not self.is_pack_allowed():
            self.result = False
            self.message = 'Blender Pack Engine: In Blender v3.6.0 pack is not allowed because Packer is modal. Use Blender v3.6.1 istead'
            self.raise_popup_id_name = 'ZUV_MT_ZenWarningV36Popup'
            return

        PackUtils.resolve_pack_selected_only(context, addon_prefs, Storage)

        if addon_prefs.packInTrim:
            bpy.ops.uv.zenuv_fit_to_trim(
                influence_mode='ISLAND',
                op_order='OVERALL',
                fit_mode='TO_TRIM_T',
                op_fit_axis='AUTO',
                op_keep_proportion=True,
                op_align_to='cen')
            self.create_fake_geometry(context, Storage)

        self.result, self.message = self._do_pack(addon_prefs, fast_mode, Storage)
        Storage.remove_marker_faces()
        PackUtils.bpy_select_by_context(context, action='DESELECT')

    def _do_pack(self, addon_prefs: bpy.types.AddonPreferences, fast_mode: bool, Storage: PackObjectsStorage):
        if addon_prefs.averageBeforePack:
            if bpy.ops.uv.average_islands_scale.poll():
                bpy.ops.uv.average_islands_scale('INVOKE_DEFAULT')

        if ZenPolls.version_greater_3_6_0:
            p_check_data = self.store_checking_coords(Storage)

            try:
                self._bpy_pack(addon_prefs, fast_mode)
            except Exception:
                _message = "Zen UV: Potential Crash in Blender Pack process. \
                    Try to clean up geometry."
                return False, _message

            p_was_packed = self.check_was_packed(Storage, p_check_data)
            if not p_was_packed:
                self._bpy_alert_pack(addon_prefs, fast_mode)
        else:
            try:
                bpy.ops.uv.pack_islands(
                    'INVOKE_DEFAULT',
                    rotate=addon_prefs.rotateOnPack,
                    margin=addon_prefs.margin * 2.95
                    )
            except Exception:
                _message = "Zen UV: Potential Crash in Blender Pack process. \
                    Try to clean up geometry."
                return False, _message

        return True, "Zen UV: Pack Finished"

    def _bpy_pack(self, addon_prefs, fast_mode: bool):
        if fast_mode:
            bpy.ops.uv.pack_islands(
                shape_method='AABB',
                scale=True,
                rotate=True,
                rotate_method='AXIS_ALIGNED',
                margin_method='ADD',
                margin=addon_prefs.margin,
                pin=False,
                pin_method='LOCKED',
                merge_overlap=addon_prefs.lock_overlapping_enable,
                udim_source='ORIGINAL_AABB' if addon_prefs.packInTrim else 'CLOSEST_UDIM'
                )
        else:
            bpy.ops.uv.pack_islands(
                shape_method='CONCAVE',
                scale=True,
                rotate=addon_prefs.rotateOnPack,
                rotate_method='AXIS_ALIGNED',
                margin_method='ADD',
                margin=addon_prefs.margin,  # * 2.95,
                pin=False,
                pin_method='LOCKED',
                merge_overlap=addon_prefs.lock_overlapping_enable,
                udim_source='ORIGINAL_AABB' if addon_prefs.packInTrim else 'CLOSEST_UDIM'
                )

    def _bpy_alert_pack(self, addon_prefs, fast_mode: bool):
        if fast_mode:
            bpy.ops.uv.pack_islands(
                'INVOKE_DEFAULT',
                shape_method='AABB',
                scale=True,
                rotate=True,
                rotate_method='AXIS_ALIGNED',
                margin_method='ADD',
                margin=addon_prefs.margin,
                pin=False,
                pin_method='LOCKED',
                merge_overlap=addon_prefs.lock_overlapping_enable,
                udim_source='ORIGINAL_AABB' if addon_prefs.packInTrim else 'CLOSEST_UDIM'
                )
        else:
            bpy.ops.uv.pack_islands(
                'INVOKE_DEFAULT',
                shape_method='CONCAVE',
                scale=True,
                rotate=addon_prefs.rotateOnPack,
                rotate_method='AXIS_ALIGNED',
                margin_method='ADD',
                margin=addon_prefs.margin,  # * 2.95,
                pin=False,
                pin_method='LOCKED',
                merge_overlap=addon_prefs.lock_overlapping_enable,
                udim_source='ORIGINAL_AABB' if addon_prefs.packInTrim else 'CLOSEST_UDIM'
                )

    def get_chk_coordinates(self, bm: bmesh.types.BMesh, uv_layer):
        bm.edges.ensure_lookup_table()
        if self.is_not_sync:
            p_edge_idxs = [edge.index for edge in bm.edges if edge.link_loops and not edge.hide and edge.select]
        else:
            p_edge_idxs = [edge.index for edge in bm.edges if edge.link_loops and not edge.hide]

        if p_edge_idxs:
            e0 = 0
            e2 = len(p_edge_idxs) - 1
            e1 = e2 // 2
        else:
            return [(0.0, 0.0)] * 3

        if self.is_not_sync:
            return list(itertools.chain(
                loop[uv_layer].uv[:]
                for edge_index in (p_edge_idxs[e0], p_edge_idxs[e1], p_edge_idxs[e2])
                for loop in bm.edges[edge_index].link_loops
                if not not loop.face.hide and loop.face.select
            ))
        else:
            return list(itertools.chain(
                loop[uv_layer].uv[:]
                for edge_index in (p_edge_idxs[e0], p_edge_idxs[e1], p_edge_idxs[e2])
                for loop in bm.edges[edge_index].link_loops
                if not loop.face.hide
            ))

    def store_checking_coords(self, Storage: PackObjectsStorage):
        return {s_obj.obj.name: self.get_chk_coordinates(s_obj.bm, s_obj.uv_layer) for s_obj in Storage.yield_selected_objects()}

    def check_was_packed(self, Storage: PackObjectsStorage, stored_check_coords: dict):
        p_check_data = [
            stored_check_coords[s_obj.obj.name] != self.get_chk_coordinates(s_obj.bm, s_obj.uv_layer)
            for s_obj in Storage.yield_selected_objects() if not all(x == 0.0 and y == 0.0 for x, y in stored_check_coords[s_obj.obj.name])]

        if not p_check_data:
            return True

        return any(p_check_data)

    def create_fake_geometry(self, context: bpy.types.Context, Storage: PackObjectsStorage):
        trim = ZuvTrimsheetUtils.getActiveTrim(context)
        if trim is None:
            self.raise_message('active_trim_is_none')
            return False
        self.create_markers(Storage, [trim.left_bottom, trim.top_right])
        return True

    def create_markers(self, Storage: PackObjectsStorage, trim_corners):
        obj = Storage.get_object_by_name(Storage.objs[0].obj.name)
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = bm.loops.layers.uv.active
        p_face = bm.faces[0]
        verts_co = (
            (-1.0000, -1.0000, 0.0000),
            (1.0000, -1.0000, 0.0000),
            (1.0000, 1.0000, 0.0000),
            (-1.0000, 1.0000, 0.0000))

        faces = ((0, 1, 2), (0, 2, 3))
        p_verts = []
        p_b_idx = len(bm.verts)

        for c, co in enumerate(verts_co):
            vert = bm.verts.new(co, p_face.verts[0])
            vert.index = p_b_idx + c
            p_verts.append(vert)

        for f_idxs, uv_co in zip(faces, trim_corners):
            verts = [p_verts[i] for i in f_idxs]
            p_f_idx = len(bm.faces) - 1
            face = bm.faces.new(verts, p_face)
            face.index = p_f_idx + 1
            face.select_set(True)
            Storage.marker_face_idxs.append(face.index)
            for lp in face.loops:
                lp[uv_layer].uv = uv_co

    def raise_message(self, err_type):
        messages = {
            "active_trim_is_none": "There are no Active Trim.",
        }
        if err_type in messages.keys():
            out_message = f"Zen UV: {messages[err_type]}"
            if self.show_transfer:
                print(out_message)
        else:
            out_message = "Zen UV: UVPMmanager: Message is not classified."
            if self.show_transfer:
                print(out_message)

        return out_message


class PackerProcessor:

    def __init__(self, PROPS) -> None:

        self.result: bool = False
        self.message: str = ''
        self.raise_popup_id_name: str = None

        self.disable_overlay = PROPS.disable_overlay

        self.fast_mode: bool = PROPS.fast_mode

    def pack(self, context: bpy.types.Context, Storage: PackObjectsStorage):
        addon_prefs = get_prefs()
        current_engine = addon_prefs.packEngine

        if current_engine == "UVP":

            Packer = UVPMmanager(context, addon_prefs)
            Packer.pack(context, Storage, addon_prefs, self.disable_overlay)

        elif current_engine == "BLDR":

            Packer = BlenderPackManager(context)
            Packer.pack(context, Storage, addon_prefs, self.fast_mode)

        elif current_engine == "UVPACKER":

            Packer = UVPackerManager(context, addon_prefs)
            Packer.pack(context, Storage, addon_prefs)

        else:
            self.result = False
            self.message = "Zen UV: There is no selected Engine for packing."
            return

        self.result = Packer.result
        self.message = Packer.message
        self.raise_popup_id_name = Packer.raise_popup_id_name


class ZUV_OT_Pack(bpy.types.Operator):
    bl_idname = "uv.zenuv_pack"
    bl_label = ZuvLabels.PACK_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.PACK_DESC

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.Storage: PackObjectsStorage = PackObjectsStorage()
        self.invoked: bool = False

    display_uv: BoolProperty(
        name="Display UV",
        default=False,
        options={'HIDDEN'}
    )
    disable_overlay: BoolProperty(
        name="Disable Overlay",
        default=False,
        options={'HIDDEN'}
    )
    fast_mode: BoolProperty(
        name="Fast (simpliest) pack settings",
        default=False,
        options={'HIDDEN'}
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_res = self.Storage.collect_objects(context)
        self.invoked = True
        if p_res is False:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}
        return self.execute(context)

    def execute(self, context):
        if not self.invoked:
            p_res = self.Storage.collect_objects(context)
            if p_res is False:
                self.report({'WARNING'}, "Zen UV: There are no selected objects.")
                return {'CANCELLED'}

        ZsPieFactory.mark_pie_cancelled()

        self.Storage.hide_pack_excluded(context)

        PackProcessor = PackerProcessor(self.properties)
        PackProcessor.pack(context, self.Storage)

        if PackProcessor.result is False:
            self.Storage.unhide_pack_excluded()
            self.report({'WARNING'}, PackProcessor.message)
            if PackProcessor.raise_popup_id_name is not None:
                bpy.ops.wm.call_menu(name=PackProcessor.raise_popup_id_name)
            return {'CANCELLED'}

        print(PackProcessor.message)

        self.Storage.unhide_pack_excluded()
        self.Storage.restore_selection_all_objects(context)

        fit_uv_view(context, mode="all")

        if self.display_uv and get_prefs().packEngine != "UVPACKER":
            # Display UV Widget from HOPS addon
            from ZenUV.utils.hops_integration import show_uv_in_3dview
            show_uv_in_3dview(context, use_selected_meshes=True, use_selected_faces=False, use_tagged_faces=False)

        return {'FINISHED'}


class ZUV_OT_SyncZenUvToUVP(bpy.types.Operator):
    bl_idname = "uv.zenuv_sync_to_uvp"
    bl_label = ZuvLabels.OT_SYNC_TO_UVP_LABEL
    bl_description = ZuvLabels.OT_SYNC_TO_UVP_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_prefs = get_prefs()
        current_engine = addon_prefs.packEngine

        if current_engine == "UVP":
            print("Zen UV: UV Packmaster Engine detected")
            packer = UVPMmanager(context, addon_prefs)
            if not packer.get_engine_version(context):
                return {'CANCELLED'}
            packer.transfer_attrs_to_uvpm()
        else:
            bpy.ops.wm.call_menu(name="ZUV_MT_ZenPack_Uvp_Popup")
            return {'CANCELLED'}
        return {'FINISHED'}


pack_classes = (
    ZUV_OT_Pack,
    ZUV_OT_SyncZenUvToUVP,
)


if __name__ == '__main__':
    pass
