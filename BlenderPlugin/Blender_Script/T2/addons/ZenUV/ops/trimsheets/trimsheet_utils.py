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

# Copyright 2022, Alex Zhornyak

import bpy
from mathutils import Color, Vector
import blf

import json
import uuid
from zlib import adler32
import numpy as np
import random

from ZenUV.utils.vlog import Log
from ZenUV.utils.simple_geometry import Rectangle
from ZenUV.utils.bounding_box import t_SYMBOL_BBOX_2_DIGITS


_ATTR_TRIMSHEETS_REGION_CURSOR = 'zuv_trimsheet_region_cursor'


class ZuvTrimsheetUtils:

    CORNER_RADIUS = 6
    MIDDLE_RADIUS = 4

    icon_edit_mode_create = 'GREASEPENCIL'
    icon_edit_mode_resize = 'FULLSCREEN_EXIT'

    TRIM_PRESET_SUBDIR = 'trimsheet_presets'
    TRIM_PREVIEW_SUBDIR = 'trimsheet_preview'

    @classmethod
    def getSpaceDataImage(cls, context: bpy.types.Context) -> bpy.types.Image:
        if hasattr(context, 'space_data'):
            if context.space_data is not None and hasattr(context.space_data, 'image'):
                return context.space_data.image
        return None

    @classmethod
    def isImageEditorSpace(cls, context: bpy.types.Context) -> bool:
        if hasattr(context, 'space_data'):
            if context.space_data is not None:
                return context.space_data.type == 'IMAGE_EDITOR'
        return False

    @classmethod
    def getMaterialImage(cls, material: bpy.types.Material) -> bpy.types.Image:
        if material is not None:
            if material.zen_uv.trimsheet_image is not None:
                return material.zen_uv.trimsheet_image

            if material.use_nodes:
                # Priority for Base Color Texture
                try:
                    principled = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                    base_color = principled.inputs['Base Color']
                    link = base_color.links[0]
                    link_node = link.from_node
                    return link_node.image
                except Exception:
                    pass

                # DO NOT REMOVE, MAY BE CHANGED IN THE FUTURE
                # def iterate_node_tree_for_image(nodes):
                #     for it_node in nodes:
                #         if it_node.type == 'BSDF_PRINCIPLED':
                #             continue
                #         elif it_node.type == 'TEX_IMAGE':
                #             return it_node.image
                #         elif it_node.type == 'GROUP':
                #             p_image = iterate_node_tree_for_image(it_node.node_tree.nodes)
                #             if p_image is not None:
                #                 return p_image

                #     return p_image

                # return iterate_node_tree_for_image(material.node_tree.nodes)
        return None

    @classmethod
    def getActiveImage(cls, context):
        p_image = cls.getSpaceDataImage(context)
        if p_image is not None:
            return p_image

        if hasattr(context, 'area') and context.area is not None and context.area.type != 'IMAGE_EDITOR':
            if context.active_object is not None:
                return cls.getMaterialImage(context.active_object.active_material)

        return None

    @classmethod
    def getActiveOverridedData(cls, p_trim_data, context: bpy.types.Context):
        p_active_data = None
        if p_trim_data is not None:
            p_active_data = p_trim_data.zen_uv

            # HACK: option to change active trim when it is linked as library image
            if isinstance(p_trim_data, bpy.types.Image) and p_trim_data.library is not None:
                s_name_full = p_trim_data.name_full
                if s_name_full:
                    wm = context.window_manager
                    p_active_data = wm.zen_uv.trimsheet_linked_overrides.get(s_name_full)
                    if p_active_data is None:
                        wm.zen_uv.trimsheet_linked_overrides.add()
                        p_active_data = wm.zen_uv.trimsheet_linked_overrides[-1]
                        p_active_data.name = s_name_full
        return p_active_data

    @classmethod
    def getTrimsheet(cls, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        p_data = context.scene if addon_prefs.trimsheet.mode == 'SCENE' else cls.getActiveImage(context)
        return p_data.zen_uv.trimsheet if p_data is not None else []

    @classmethod
    def getTrimsheetOwner(cls, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        p_data = context.scene if addon_prefs.trimsheet.mode == 'SCENE' else cls.getActiveImage(context)
        if p_data is not None:
            return p_data.zen_uv
        else:
            return None

    @classmethod
    def getActiveTrimDataFromData(cls, p_data):
        if p_data is not None:
            n_count = len(p_data.zen_uv.trimsheet)
            idx = p_data.zen_uv.trimsheet_index
            if idx in range(0, n_count):
                return (idx, p_data.zen_uv.trimsheet[idx], p_data.zen_uv.trimsheet)
        return None

    @classmethod
    def getActiveTrimFromOwner(cls, p_owner):
        if p_owner is not None:
            n_count = len(p_owner.trimsheet)
            idx = p_owner.trimsheet_index
            if idx in range(0, n_count):
                return p_owner.trimsheet[idx]
        return None

    @classmethod
    def getActiveTrimData(cls, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        p_data = context.scene if addon_prefs.trimsheet.mode == 'SCENE' else cls.getActiveImage(context)
        return cls.getActiveTrimDataFromData(p_data)

    @classmethod
    def getActiveTrimPair(cls, context: bpy.types.Context):
        p_trimsheet_data = cls.getActiveTrimData(context)
        if p_trimsheet_data:
            idx, p_trim, _ = p_trimsheet_data
            return (idx, p_trim)

        return None

    @classmethod
    def getActiveTrim(cls, context: bpy.types.Context):
        p_trimsheet_data = cls.getActiveTrimData(context)
        if p_trimsheet_data:
            _, p_trim, _ = p_trimsheet_data
            return p_trim

        return None

    @classmethod
    def isTrimsheetEditable(cls, context: bpy.types.Context):
        p_trim_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_trim_data:
            if p_trim_data.id_data and not p_trim_data.id_data.library:
                return True
        return False

    @classmethod
    def setActiveTrimsheetIndex(cls, context: bpy.types.Context, value):
        p_data = cls.getTrimsheetOwner(context)
        if p_data:
            p_data.trimsheet_index = value

    @classmethod
    def getTrimsheetSelectedIndices(cls, p_trimsheet) -> tuple:
        n_trimsheet_count = len(p_trimsheet)
        if n_trimsheet_count > 0:
            p_arr = np.empty(n_trimsheet_count, 'b')
            p_trimsheet.foreach_get('selected', p_arr)
            p_nonzero = np.nonzero(p_arr)
            if p_nonzero:
                return p_nonzero[0]
        return tuple()

    @classmethod
    def getTrimsheetSelectedCount(cls, context: bpy.types.Context):
        p_trimsheet = cls.getTrimsheet(context)
        if p_trimsheet:
            return len(cls.getTrimsheetSelectedIndices(p_trimsheet))
        return 0

    @classmethod
    def getTrimsheetSelectedAndActiveCount(cls, context: bpy.types.Context):
        p_trimsheet = cls.getTrimsheet(context)
        if p_trimsheet:
            return len(cls.getTrimsheetSelectedAndActiveIndices(p_trimsheet))
        return 0

    @classmethod
    def getTrimsheetRandomColor(cls):
        color = Color((random.uniform(0.0, 1.0), random.uniform(0.0, 1.0), random.uniform(0.0, 1.0)))
        color.v = min(0.7, color.v)
        return color[:]

    @classmethod
    def getTrimsheetGeneratedColor(cls, p_trimsheet):
        from .color_palette import ColorUtils
        return ColorUtils.new_color(p_trimsheet)

    @classmethod
    def getTrimsheetSelectedAndActiveIndices(cls, p_trimsheet) -> set:
        p_selected_indices = set()
        act_idx = p_trimsheet.id_data.zen_uv.trimsheet_index
        if act_idx in range(len(p_trimsheet)):
            p_selected_indices.add(act_idx)

        p_selected_indices.update(cls.getTrimsheetSelectedIndices(p_trimsheet))

        return p_selected_indices

    @classmethod
    def getTrimsheetBounds(cls, p_trimsheet) -> Rectangle:
        left = 0.0
        top = 0.0
        right = 0.0
        bottom = 0.0
        for p_trim in p_trimsheet:
            l, t, r, b = p_trim.rect
            if l < left:
                left = l
            if t > top:
                top = t
            if r > right:
                right = r
            if b < bottom:
                bottom = b
        return Rectangle(left, top, right, bottom)

    @classmethod
    def getSelectedTrims(cls, p_trimsheet):
        for idx in cls.getTrimsheetSelectedIndices(p_trimsheet):
            yield p_trimsheet[idx]

    @classmethod
    def getSelectedAndActiveTrims(cls, p_trimsheet):
        for idx in cls.getTrimsheetSelectedAndActiveIndices(p_trimsheet):
            yield p_trimsheet[idx]

    @classmethod
    def getAllTrimsheetUuids(cls, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        p_scene = context.scene

        if addon_prefs.trimsheet.mode == 'SCENE':
            p_uuids = set() if len(p_scene.zen_uv.trimsheet) == 0 else {p_scene.zen_uv.trimsheet_geometry_uuid}
        else:
            p_uuids = {
                image.zen_uv.trimsheet_geometry_uuid for image in bpy.data.images if len(image.zen_uv.trimsheet) > 0
            }
        return p_uuids

    @classmethod
    def getTrimTextAlignmentBounds(
            cls,
            v_text_center: Vector, d_trim_width: float, d_trim_height: float,
            s_trim_text: str, b_trim_active: bool, p_align_props):
        t_width, t_height = blf.dimensions(0, s_trim_text)

        # NOTE: conversion to 2 digits X, Y
        p_text_align = t_SYMBOL_BBOX_2_DIGITS[p_align_props.text_align]

        x_offset = 0
        y_offset = 0

        x_text = v_text_center.x
        y_text = v_text_center.y

        if p_align_props.text_offset_mode == 'PERCENT':
            if d_trim_width != 0.0:
                x_ratio = p_align_props.text_offset[0] / 100.0
                x_offset = d_trim_width * x_ratio
            if d_trim_height != 0.0:
                y_ratio = p_align_props.text_offset[1] / 100.0
                y_offset = d_trim_height * y_ratio
        else:
            x_offset, y_offset = p_align_props.text_offset

        # NOTE: special case to offset by trim center
        if p_text_align == "cc":
            x_offset += 10 if b_trim_active else (- t_width / 2)
            y_offset += (- t_height / 2)
        else:
            x_symbol = p_text_align[0]
            y_symbol = p_text_align[1]

            if x_symbol == 'c':
                x_offset += (- t_width / 2)
            else:
                x_offset += (0 if x_symbol == 'l' else (- t_width))

            if y_symbol == 'c':
                y_offset += (- t_height / 2)
            else:
                y_offset += ((- t_height) if y_symbol == 't' else 0)

        x_text += x_offset
        y_text += y_offset

        # NOTE: 'left, bottom' are required to draw label
        left = round(x_text)
        bottom = round(y_text)

        # NOTE: 'right, top' are required to have bounding box
        d_intersect_ratio = 0.7
        right = round(left + t_width * d_intersect_ratio)
        top = round(bottom + t_height * d_intersect_ratio)

        return left, top, right, bottom

    @classmethod
    def indexOfTrimByUuid(cls, p_trimsheet, uuid: str):
        for idx, p_trim in enumerate(p_trimsheet):
            if p_trim.uuid == uuid:
                return idx
        return -1

    @classmethod
    def pointInRect(cls, point, left, top, right, bottom):
        x, y = point
        if (left < x and x < right):
            if (bottom < y and y < top):
                return True
        return False

    @classmethod
    def pointInHandle(cls, point, center, radius):
        return cls.pointInRect(point, center[0] - radius, center[1] + radius, center[0] + radius, center[1] - radius)

    @classmethod
    def getPointInMode(cls, pt, left, top, right, bottom) -> str:

        p_width = abs(right - left)
        p_height = abs(top - bottom)

        p_ratio = 2

        # corners
        if cls.pointInHandle(pt, (left, top), cls.CORNER_RADIUS * p_ratio):
            return 'LEFT_TOP'
        if cls.pointInHandle(pt, (right, top), cls.CORNER_RADIUS * p_ratio):
            return 'RIGHT_TOP'
        if cls.pointInHandle(pt, (left, bottom), cls.CORNER_RADIUS * p_ratio):
            return 'LEFT_BOTTOM'
        if cls.pointInHandle(pt, (right, bottom), cls.CORNER_RADIUS * p_ratio):
            return 'RIGHT_BOTTOM'

        # middle
        if cls.pointInHandle(pt, (left + p_width / 2, top), cls.MIDDLE_RADIUS * p_ratio):
            return 'TOP'
        if cls.pointInHandle(pt, (right, top - p_height / 2), cls.CORNER_RADIUS * p_ratio):
            return 'RIGHT'
        if cls.pointInHandle(pt, (left, bottom + p_height / 2), cls.CORNER_RADIUS * p_ratio):
            return 'LEFT'
        if cls.pointInHandle(pt, (left + p_width / 2, bottom), cls.CORNER_RADIUS * p_ratio):
            return 'BOTTOM'

        return ''

    @classmethod
    def set_modal_cursor_by_in_mode(cls, context: bpy.types.Context, s_in_mode: str):
        t_cursors = {
            'LEFT_TOP': 'SCROLL_XY',
            'RIGHT_TOP': 'SCROLL_XY',
            'LEFT_BOTTOM': 'SCROLL_XY',
            'RIGHT_BOTTOM': 'SCROLL_XY',

            'TOP': 'SCROLL_Y',
            'BOTTOM': 'SCROLL_Y',
            'LEFT': 'SCROLL_X',
            'RIGHT': 'SCROLL_X',
        }

        s_cursor = t_cursors.get(s_in_mode, None)
        if s_cursor:
            context.window.cursor_modal_set(s_cursor)
        else:
            context.window.cursor_modal_set('DEFAULT')

    @classmethod
    def set_edit_mode_region_cursor(cls, mouse_region_x, mouse_region_y):
        bpy.app.driver_namespace[_ATTR_TRIMSHEETS_REGION_CURSOR] = (mouse_region_x, mouse_region_y)

    @classmethod
    def get_edit_mode_region_cursor(cls):
        return bpy.app.driver_namespace.get(_ATTR_TRIMSHEETS_REGION_CURSOR, (0.0, 0.0))

    @classmethod
    def export_to_json(cls, context: bpy.types.Context, p_op: bpy.types.Operator) -> str:
        p_data = cls.getTrimsheetOwner(context)
        if p_data is not None:
            json_data = {}
            json_data['trimsheet'] = {}

            act_idx = p_data.trimsheet_index
            for idx, p_trim in enumerate(p_data.trimsheet):
                if p_op.mode == 'ACTIVE':
                    if idx != act_idx:
                        continue
                elif p_op.mode == 'SELECTED':
                    if idx != act_idx and not p_trim.selected:
                        continue

                def fn_skip_prop(inst, attr):
                    if inst == p_trim and attr == 'name':
                        return True
                    return False

                json_data['trimsheet'][p_trim.name] = p_trim.to_dict(fn_skip_prop=fn_skip_prop)

            if len(json_data['trimsheet']) == 0:
                p_op.report({'INFO'}, 'No trims to copy!')

            return json.dumps(json_data)

        return ''

    @classmethod
    def import_from_trim_dict(cls, p_data, p_op: bpy.types.Operator, p_trim_dict: dict):
        was_active_name = None
        if p_data.trimsheet_index in range(0, len(p_data.trimsheet)):
            was_active_name = p_data.trimsheet[p_data.trimsheet_index].name

        # b_select = getattr(p_op, 'select', True)

        p_new_trims = set()

        if p_op.mode == 'CLEAR':
            p_data.trimsheet.clear()
            p_data.trimsheet_index = -1

        # 1. update existing first
        if p_op.mode == 'REPLACE':
            for p_trim in p_data.trimsheet:
                p_dict = p_trim_dict.get(p_trim.name, None)
                if p_dict is not None:
                    p_trim.from_dict(p_dict)
                    p_new_trims.add(p_trim)
                    # if b_select:
                    #     p_trim.selected = True
                    del p_trim_dict[p_trim.name]

        # 2. all left json trims
        for k, v in p_trim_dict.items():
            p_data.trimsheet.add()
            p_data.trimsheet[-1].create_uuid()

            def skip_name(group, key):
                if key == 'name' and group == p_data.trimsheet[-1]:
                    return True
                return False

            p_data.trimsheet[-1].from_dict(v, fn_skip_prop=skip_name)
            p_data.trimsheet[-1].name_ex = k
            # if b_select:
            #     p_data.trimsheet[-1].selected = True
            p_new_trims.add(p_data.trimsheet[-1])

        # 3. set new index
        i_new_index = min(0, len(p_data.trimsheet) - 1)
        if was_active_name:
            for idx, p_trim in enumerate(p_data.trimsheet):
                if was_active_name == p_trim.name:
                    i_new_index = idx
                    break

        if len(p_new_trims) > 0:
            for p_trim in p_data.trimsheet:
                p_trim.selected = p_trim in p_new_trims

        p_data.trimsheet_mark_geometry_update()
        if p_data.trimsheet_index != i_new_index:
            p_data.trimsheet_index = i_new_index

    @classmethod
    def import_from_json(cls, context: bpy.types.Context, p_op: bpy.types.Operator, json_data: str):
        json_data = json.loads(json_data)

        p_trim_json = json_data.get('trimsheet', None)
        if p_trim_json is None:
            raise RuntimeError("Invalid JSON format")

        p_data = cls.getTrimsheetOwner(context)
        if p_data is None:
            raise RuntimeError('No active trimsheet')

        if len(p_trim_json) == 0:
            raise RuntimeError("Empty clipboard JSON")

        cls.import_from_trim_dict(p_data, p_op, p_trim_json)

    @classmethod
    def get_area_offsets(cls, p_area: bpy.types.Area):
        n_left_offset = sum([
            region.width for region in p_area.regions
            if region.alignment == "LEFT" and region.width > 1
        ])
        n_top_offset = sum([
            region.height for region in p_area.regions
            if region.alignment == "TOP"
        ])
        n_right_offset = sum([
            region.width for region in p_area.regions
            if region.alignment == "RIGHT" and region.width > 1
        ])
        n_bottom_offset = sum([
            region.height for region in p_area.regions
            if region.alignment == "BOTTOM"
        ])

        return {
            'left': n_left_offset, 'top': n_top_offset, 'right': n_right_offset, 'bottom': n_bottom_offset
        }

    @classmethod
    def is_point_in_area_view(cls, point, context: bpy.types.Context):
        b_point_outside_window = False
        p_area = context.area
        for rgn in p_area.regions:
            b_is_in_region = cls.pointInRect(point, rgn.x, rgn.y + rgn.height, rgn.x + rgn.width, rgn.y)
            if b_is_in_region:
                if rgn.type != 'WINDOW':
                    b_point_outside_window = True
                    break

        p_left = p_area.x
        p_bottom = p_area.y
        p_right = p_area.x + p_area.width
        p_top = p_area.y + p_area.height

        return not b_point_outside_window and cls.pointInRect(point, p_left, p_top, p_right, p_bottom)

    @classmethod
    def update_imageeditor_in_all_screens(cls):
        context = bpy.context

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.tag_redraw()

    @classmethod
    def auto_highlight_trims(cls, context: bpy.types.Context):
        from ZenUV.prop.zuv_preferences import get_prefs
        addon_prefs = get_prefs()
        if addon_prefs.trimsheet.auto_highlight == 'DEFAULT':
            p_scene = context.scene
            p_scene.zen_uv.ui.uv_tool.display_trims = True
            p_scene.zen_uv.ui.view3d_tool.display_trims = True

    @classmethod
    def fix_undo(cls):
        try:
            # this is the only dirty option to save scene collection properties
            p_mesh = bpy.data.meshes.new(name=str(uuid.uuid4()))
            bpy.data.meshes.remove(p_mesh)
        except Exception as e:
            Log.error('FIX_UNDO:', e)

    @classmethod
    def hash32(cls, str):
        y = np.int64(adler32(str.encode()) & 0xFFFFFFFF)
        return y.astype(np.int32)


class TrimImportUtils:
    paste_mode = bpy.props.EnumProperty(
        name='Mode',
        description='Trims paste mode',
        items=[
            ('CLEAR', 'Clear', 'Clear all trims before paste'),
            ('ADD', 'Add', 'Add trims to the trimsheet'),
            ('REPLACE', 'Replace', 'Add new trims and replace trims with the same name'),
        ],
        default='ADD')

    paste_select = bpy.props.BoolProperty(
        name='Select',
        description='Select trims after paste',
        default=True
    )
