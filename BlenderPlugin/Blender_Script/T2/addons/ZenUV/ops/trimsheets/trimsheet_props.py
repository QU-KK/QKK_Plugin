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

import numpy as np
from dataclasses import dataclass
from timeit import default_timer as timer

from .trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.event_service import get_blender_event
from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens
from ZenUV.utils.vlog import Log
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps


class ZuvTrimTextPropsConsts:
    text_align = bpy.props.EnumProperty(
        name="Text Align",
        description="Trim text align to its bounding box",
        items=TransformSysOpsProps._bbox_names_with_center,
        default=4,  # 'cen'
        options=set()
    )

    text_offset = bpy.props.FloatVectorProperty(
        name="Text Offset",
        description="Trim text offset in screen points or percents",
        size=2,
        default=(0.0, 0.0),
        options=set()
    )

    text_offset_mode = bpy.props.EnumProperty(
        name="Offset Mode",
        description="Trim text offset mode",
        items=[
            ('POINT', 'Point', 'Text offset in screen points'),
            ('PERCENT', 'Percent', 'Text offset in percents'),
        ],
        default='POINT',
        options=set()
    )


class ZuvTrimsheetProps(bpy.types.PropertyGroup):

    def update_mark_dirty(self, context: bpy.types.Context):
        if not context.preferences.is_dirty:
            context.preferences.is_dirty = True

    border_style: bpy.props.EnumProperty(
        name='Border Style',
        description='Border color style: match fill color, individual, etc',
        items=[
            ('DEFAULT', 'Default', 'Border color matches trim fill color'),
            ('FIXED', 'Fixed', 'Border colors has 3 types: default, active, selected'),
            ('USER', 'User', 'Every border color is overrided by user')
        ],
        default='DEFAULT',
        update=update_mark_dirty
    )

    display_name: bpy.props.BoolProperty(
        name='Display Name',
        description='Display Trim names',
        default=True,
        update=update_mark_dirty
    )

    # MUST BE Integer to support previous BLF versions
    font_size: bpy.props.IntProperty(
        name='Font Size',
        subtype='PIXEL',
        min=4,
        max=40,
        default=10,
        update=update_mark_dirty
    )

    scale_font: bpy.props.BoolProperty(
        name='Scale Font',
        description='If set then font is scaled by resolution scale value in preferences',
        default=False,
        update=update_mark_dirty
    )

    font_color: bpy.props.EnumProperty(
        name='Font Color',
        description="Font color by fill or stroke color settings",
        items=[
            ("BY_FILL", "By Fill Color", "Inherits trim fill color"),
            ("BY_STROKE", "By Stroke Color", "Inherits trim stroke color"),
        ],
        default="BY_FILL",
        update=update_mark_dirty
    )

    text_align_style: bpy.props.EnumProperty(
        name='Align Mode',
        description="Global or individual trim text align settings",
        items=[
            ('DEFAULT', 'Default', 'Global trim text align settings'),
            ('USER', 'User', 'Individual trim text align settings')
        ],
        default='DEFAULT',
        update=update_mark_dirty
    )

    text_align_expanded: bpy.props.BoolProperty(
        name="Text Align Settings",
        description="Display expanded text align settings",
        default=False,
        update=update_mark_dirty
    )

    border_width: bpy.props.FloatProperty(
        name='Border Width',
        min=0.0,
        max=100.0,
        precision=1,
        step=10,
        subtype='PIXEL',
        default=1.0,
        update=update_mark_dirty
    )

    background_color: bpy.props.FloatVectorProperty(
        name='Background Edit Color',
        description='Background dimming color in Create Trims mode',
        subtype='COLOR_GAMMA',
        size=4,
        default=(0.068, 0.1, 0.06, 0.6),
        min=0, max=1,
        update=update_mark_dirty
    )

    texture_gamma_color: bpy.props.FloatVectorProperty(
        name='View3D Texture Gamma',
        description='View 3D texture gamma color (texture color * gamma color)',
        subtype='COLOR_GAMMA',
        size=4,
        default=(1.0, 1.0, 1.0, 0.5),
        min=0, max=1,
        update=update_mark_dirty
    )

    border_color: bpy.props.FloatVectorProperty(
        name='Stroke color for trim rectangle border',
        subtype='COLOR_GAMMA',
        size=3,
        default=(0.5, 0.8, 0.7),
        min=0, max=1,
        update=update_mark_dirty
    )

    active_border_color: bpy.props.FloatVectorProperty(
        name='Stroke color for active Trim rectangle border',
        subtype='COLOR_GAMMA',
        size=3,
        default=(1.0, 0.5, 0.0),
        min=0, max=1,
        update=update_mark_dirty
    )

    selected_border_color: bpy.props.FloatVectorProperty(
        name='Stroke Color for Seleted Trims rectangle border',
        subtype='COLOR_GAMMA',
        size=3,
        default=(0.0, 0.0, 1.0),
        min=0, max=1,
        update=update_mark_dirty
    )

    fill_transparency: bpy.props.IntProperty(
        name='Fill Opacity',
        subtype='PERCENTAGE',
        min=0,
        max=100,
        default=9,
        update=update_mark_dirty
    )

    border_transparency: bpy.props.IntProperty(
        name='Border Opacity',
        subtype='PERCENTAGE',
        min=0,
        max=100,
        default=75,
        update=update_mark_dirty
    )

    mode: bpy.props.EnumProperty(
        name='Trimsheet Mode',
        description='Trimsheet data storage',
        items=[
            ('SCENE', 'Scene', 'Scene is used to store Trimsheet data', 'SCENE_DATA', 0),
            ('IMAGE', 'Image', 'Image is used to store Trimsheet data', 'IMAGE_DATA', 1)
        ],
        default='SCENE',
        update=update_mark_dirty
    )

    edit_mode: bpy.props.EnumProperty(
        name='Edit Mode',
        items=[
            ('RESIZE', 'Resize', 'Trim resize mode', ZuvTrimsheetUtils.icon_edit_mode_resize, 0),
            ('CREATE', 'Create', 'Trim creation mode', ZuvTrimsheetUtils.icon_edit_mode_create, 1)
        ],
        default='RESIZE',
        update=update_mark_dirty
    )

    size_mode: bpy.props.EnumProperty(
        name='Trim Size Mode',
        description='Trim setting size mode: percent or pixels',
        items=[
            ('PERCENT', 'Percent', 'Percent size 0 - 1'),
            ('PIXEL', 'Pixel', 'Pixel size based on image dimensions'),
        ],
        default='PERCENT',
        update=update_mark_dirty
    )

    auto_highlight: bpy.props.EnumProperty(
        name='Auto Highlight',
        description='Enable trimsheet display depending on mode',
        items=[
            ('DEFAULT', 'Default', 'Enable display on new trim and enter tool, disable on exit tool'),
            ('MANUAL', 'Manual', 'Enable display only by user command')
        ],
        default='DEFAULT',
        update=update_mark_dirty
    )

    auto_disable_blender_overlay: bpy.props.BoolProperty(
        name='Auto Disable Blender Overlay',
        description='Disable blender overlay on modal operation',
        default=False,
        update=update_mark_dirty
    )

    auto_disable_trims_overlay: bpy.props.BoolProperty(
        name='Auto Disable Trims Overlay',
        description='Disable trims overlay on modal operation',
        default=False,
        update=update_mark_dirty
    )

    style_settings_expanded: bpy.props.BoolProperty(
        name='Style Settings',
        description='Expand-collapse trimsheet style settings',
        default=False,
        update=update_mark_dirty
    )

    text_align: ZuvTrimTextPropsConsts.text_align

    text_offset: ZuvTrimTextPropsConsts.text_offset

    text_offset_mode: ZuvTrimTextPropsConsts.text_offset_mode

    def draw_style(self, layout: bpy.types.UILayout, context: bpy.types.Context):
        ''' @Draw Trims Style '''
        layout = layout.column()

        row = layout.row(align=True)
        row.alignment = 'LEFT'
        row.prop(
            self, 'style_settings_expanded',
            emboss=False,
            icon='DISCLOSURE_TRI_DOWN' if self.style_settings_expanded else 'DISCLOSURE_TRI_RIGHT')

        if not self.style_settings_expanded:
            return

        if context.area.type == 'IMAGE_EDITOR':
            layout.prop(self, 'background_color')
        else:
            layout.label(text='View3D Settings')
            layout.prop(self, 'texture_gamma_color', text='Texture Gamma')

        layout.separator(factor=2.0)
        layout.label(text='Trim Text Settings')
        col = layout.column(align=False)
        col.use_property_split = True
        col.active = self.display_name
        col.prop(self, 'font_size')
        col.prop(self, 'scale_font')
        row = col.row(align=True)
        row.prop(self, "font_color", expand=False)

        # row = col.row(align=True)
        # row.alignment = 'LEFT'
        # row.prop(
        #     self, "text_align_expanded",
        #     icon='TRIA_DOWN' if self.text_align_expanded else 'TRIA_RIGHT',
        #     emboss=False)

        row = col.row(align=True)
        row.prop(self, 'text_align_style', expand=True)
        if self.text_align_style == 'DEFAULT':
            subcol = col.column()
            subcol.use_property_split = True
            subcol.prop(self, 'text_align')
            subcol.prop(self, 'text_offset')
            subcol.prop(self, 'text_offset_mode')
        else:
            row = col.row(align=True)
            row.alignment = 'CENTER'
            row.label(text='Use text align properties in Trim')

        layout.separator(factor=2.0)
        layout.label(text='Trim Fill Settings')
        col = layout.column(align=False)
        col.prop(self, 'fill_transparency', text='Opacity')

        layout.separator(factor=2.0)
        layout.label(text='Trim Stroke Settings')
        row = layout.row(align=True)
        row.prop(self, 'border_style', expand=True)
        col = layout.column(align=False)

        col.prop(self, 'border_transparency', text='Opacity')

        col.separator()
        if self.border_style == 'FIXED':
            col.prop(self, 'border_color', text='Stroke Color')
            col.prop(self, 'active_border_color', text='Active Color')
        col.prop(self, 'selected_border_color', text='Selected Color')

    def draw(self, layout: bpy.types.UILayout, context: bpy.types.Context):
        # reserved for full property page
        pass


@dataclass
class TimeData:
    time: float = 0.0
    idx: int = -1

    trim = None
    literal_id = 'zenuv_uilist_time_data'


class ZuvTrimsheetOwnerProps:
    def get_index(self):
        return self.trimsheet_index

    def set_index(self, value):
        p_event = get_blender_event(force=True)

        mode = 'ACTIVE'

        b_ctrl = p_event.get('ctrl', False)
        b_shift = p_event.get('shift', False)

        if b_shift and b_ctrl:
            mode = 'TOGGLE_ALL'
        elif b_ctrl:
            mode = 'TOGGLE'
        elif b_shift:
            mode = 'EXTEND'

        try:
            n_count = len(self.trimsheet)
            if n_count > 0:
                if mode == 'ACTIVE':
                    arr_selected = [False] * n_count
                    arr_selected[value] = True

                    # NOTE: foreach does not work if it is linked
                    if self.id_data and self.id_data.library:
                        for idx in range(n_count):
                            self.trimsheet[idx].selected = idx == value
                    else:
                        self.trimsheet.foreach_set("selected", arr_selected)

                    self.trimsheet_index = value
                elif mode == 'EXTEND':
                    start_idx = min(max(0, self.trimsheet_index), max(0, value))
                    end_idx = max(max(0, self.trimsheet_index), max(0, value))
                    for idx in range(start_idx, end_idx + 1):
                        self.trimsheet[idx].selected = True
                    self.trimsheet_index = value
                elif mode == 'TOGGLE':
                    self.trimsheet[value].selected = not self.trimsheet[value].selected
                    if self.trimsheet[value].selected:
                        self.trimsheet_index = value
                elif mode == 'TOGGLE_ALL':
                    arr = np.empty(n_count, 'b')
                    self.trimsheet.foreach_get('selected', arr)

                    b_is_selected = False if arr.all() else True
                    arr.fill(b_is_selected)

                    # NOTE: foreach does not work if it is linked
                    if self.id_data and self.id_data.library:
                        for idx in range(n_count):
                            self.trimsheet[idx].selected = b_is_selected
                    else:
                        self.trimsheet.foreach_set('selected', arr)

        except Exception as e:
            Log.error('SET TRIM INDEX:', str(e))

    def update_index(self, context):
        p_last_time_data = bpy.app.driver_namespace.get(TimeData.literal_id, TimeData())  # type: TimeData

        if timer() - p_last_time_data.time < 0.3 and self.trimsheet_index == p_last_time_data.idx:
            p_last_time_data.trim = (
                self.trimsheet[self.trimsheet_index]
                if self.trimsheet_index in range(len(self.trimsheet))
                else None)
        else:
            p_last_time_data.trim = None
        p_last_time_data.time = timer()
        p_last_time_data.idx = self.trimsheet_index
        bpy.app.driver_namespace[TimeData.literal_id] = p_last_time_data

        if context.mode == 'EDIT_MESH':
            bpy.ops.ed.undo_push(message='Select Trim')

        update_areas_in_all_screens(context)

    trimsheet_index_ui = bpy.props.IntProperty(
        name='Trimsheet Index',
        get=get_index,
        set=set_index,
        update=update_index,
        min=-1,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def get_trimsheet_geometry_uuid(self):
        p_uuid = self.get('trimsheet_geometry_uuid', '')
        if p_uuid:
            return p_uuid
        else:
            p_uuid = self.id_data.name
            return p_uuid

    def set_trimsheet_geometry_uuid(self, value):
        self['trimsheet_geometry_uuid'] = value

    trimsheet_index = bpy.props.IntProperty(name='Trimsheet Index', default=-1, min=-1)
    trimsheet_geometry_uuid = bpy.props.StringProperty(
        name='Modification Geometry UUID',
        get=get_trimsheet_geometry_uuid,
        set=set_trimsheet_geometry_uuid
    )
