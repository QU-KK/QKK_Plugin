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

# Copyright 2023, Valeriy Yatsenko, Alex Zhornyak


import bpy
import bmesh
import numpy as np
from mathutils import Vector
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer,
    UnitsConverter)
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.ops.transform_sys.transform_utils.tr_utils import Cursor2D, TransformSysOpsProps


class ZUV_OT_NewTrim(bpy.types.Operator):
    bl_idname = "uv.zenuv_new_trim"
    bl_label = "New Trim"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Add Trim to Trimsheet'

    creation_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Creation Mode",
        items=[
            ('DEFAULT', 'Default', 'Creates trim in trimsheet without bounding to geometry'),
            # Mesh Mode
            ("ISLAND", "Islands", "Creates trims from selected islands"),
            ("SELECTION", "Selection", "Creates Trims from selected elements (vertices, edges, faces). Each separate group of selections will create a separate island"),
            ("VERTS", "Vertices", "Creates a single island from all selected vertices"),
            ("FACES", "Faces", "Creates an Island from each selected face"),
        ],
        default="DEFAULT",
        options={"SKIP_SAVE"}
    )

    size: bpy.props.FloatProperty(
        name='Size',
        description='Size of the Trim',
        min=0.0,
        default=0.0
    )

    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="Trim color",
        subtype='COLOR',
        default=(0.0, 0.0, 0.0),
        size=3,
        min=0,
        max=1,
        options={'HIDDEN'}
    )

    set_trim_normal: bpy.props.BoolProperty(
        name='Set Trim Normal',
        description='Set the "Normal" property for new trims, using values derived from the corresponding polygons',
        default=False
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        b_is_edit_mesh = context.mode == 'EDIT_MESH'

        r_split = layout.row(align=False)
        r1 = r_split.row(align=True)
        r1.ui_units_x = 4
        r1.alignment = 'RIGHT'
        r1.label(text=self.properties.bl_rna.properties['creation_mode'].name)

        r2 = r_split.column(align=True)
        r_split.separator()

        col = r2.column(align=True)
        col.prop_enum(self, 'creation_mode', 'DEFAULT')
        if self.creation_mode == 'DEFAULT':
            col.prop(self, 'size')

        r2.separator()

        col = r2.column(align=True)
        col.active = b_is_edit_mesh
        for it in self.properties.bl_rna.properties['creation_mode'].enum_items:
            if it.identifier not in {'DEFAULT', 'CLONE'}:
                col.prop_enum(self, 'creation_mode', it.identifier)
        if self.creation_mode == 'FACES':
            col.prop(self, 'set_trim_normal')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.action = 'CREATE'
        if event.shift:
            self.action = 'CLONE'
        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet:
            self.color = ZuvTrimsheetUtils.getTrimsheetGeneratedColor(p_trimsheet)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        if self.color[:] == (0.0, 0.0, 0.0):
            p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
            if p_trimsheet:
                self.color = ZuvTrimsheetUtils.getTrimsheetGeneratedColor(p_trimsheet)

        if self.creation_mode == 'DEFAULT':
            if bpy.ops.uv.zuv_trim_add_sized.poll():
                return bpy.ops.uv.zuv_trim_add_sized('INVOKE_DEFAULT', size=self.size, color=self.color)
        else:
            if context.mode != 'EDIT_MESH':
                s_creation_mode = bpy.types.UILayout.enum_item_name(self, 'creation_mode', self.creation_mode)
                self.report({'INFO'}, f'Creation mode not available now: {s_creation_mode}')
                return {'FINISHED'}

            objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
            if not objs:
                self.report({'INFO'}, "There are no selected objects.")
                return {'CANCELLED'}

            bboxes = []
            for obj in objs:
                bm = bmesh.from_edit_mesh(obj.data).copy()
                try:
                    uv_layer = verify_uv_layer(bm)

                    if self.creation_mode == 'ISLAND':
                        loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
                    elif self.creation_mode == 'SELECTION':
                        loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)
                    elif self.creation_mode == 'VERTS':
                        loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False)
                        if len(loops):
                            loops = [loops]
                    elif self.creation_mode == 'FACES':
                        loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False, per_face=True)
                        if self.set_trim_normal:
                            M = obj.matrix_world
                            p_data = [(
                                    (M.to_3x3() @ group[0].face.normal).normalized(),
                                    M @ group[0].face.calc_center_median()
                                ) for group in loops]

                    else:
                        raise RuntimeError("creation_mode not in {'ISLAND', 'SELECTION', 'FACES'}")
                    if self.creation_mode == 'FACES' and self.set_trim_normal:
                        bboxes = []
                        for region, data in zip(loops, p_data):
                            p_bbox = BoundingBox2d(points=([lp[uv_layer].uv for lp in region]))
                            p_bbox.extras = data
                            bboxes.append(p_bbox)
                    else:
                        bboxes.extend([BoundingBox2d(points=([lp[uv_layer].uv for lp in region])) for region in loops])
                finally:
                    bm.free()

            if not len(bboxes):
                self.report({'WARNING'}, "There is no Selection.")
                return {'FINISHED'}

            stat = []
            for bbox in self.sort_bboxes_by_pos(bboxes):
                if round(bbox.len_x, 4) == 0.0 or round(bbox.len_y, 4) == 0.0:
                    stat.append(False)
                    continue
                p_trim = Trim.new_generic_from_bbox(context, bbox)
                if not p_trim:
                    self.report({'WARNING'}, "It is impossible to create Trim in this state of the scene")
                    return {'CANCELLED'}
                if self.creation_mode == 'FACES' and self.set_trim_normal:
                    p_trim.normal = bbox.extras[0]
                    p_trim.world_position = bbox.extras[1]
                stat.append(True)

            if False in stat:
                self.report({'WARNING'}, f"Some trims with zero dimensions were not created. Number of incorrect trims {len([1 for i in stat if i is False])}")

            return {"FINISHED"}

    def sort_bboxes_by_pos(self, bboxes):
        return [bboxes[i] for i in np.lexsort(np.array(([bb.center.x for bb in bboxes], [bb.center.y for bb in bboxes])) * -1)]


class ZUV_OT_TrimCreateGrid(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_create_grid"
    bl_label = 'Add Trim Grid'
    bl_description = 'Create Grid of Trims inside active, selected Trims, from Zero coordinates or 2D cursor position'
    bl_options = {'REGISTER', 'UNDO'}

    def get_lim_count_x(self):
        return self.get('trims_count_x', 2)

    def set_lim_count_x(self, value):
        if value * self.trims_count_y >= self.limit:
            self['trims_count_x'] = self.limit // self.trims_count_y
        else:
            self['trims_count_x'] = value

    def get_lim_count_y(self):
        return self.get('trims_count_y', 2)

    def set_lim_count_y(self, value):
        if value * self.trims_count_x >= self.limit:
            self['trims_count_y'] = self.limit // self.trims_count_x
        else:
            self['trims_count_y'] = value

    start_position: bpy.props.EnumProperty(
        name='Start Position',
        description='The starting position for creating trims',
        items=[
            ("ZERO_WORLD", "Zero Coordinates", "Start from zero coordinates x=0, y=0"),
            ("CURSOR_2D", "2D Cursor", "Start from 2D Cursor"),
            ("INSIDE_ACTIVE", "Inside of active Trim", "Creates a grid of Trims within the active Trim"),
            ("BBOX_SELECTION", "Inside of selected Trims", "Creates a grid of Trims within the selected Trims bounding box")
            ],
        default='ZERO_WORLD')
    trims_count_x: bpy.props.IntProperty(
        name='Trims Count U',
        description='Trims count Horizontal',
        set=set_lim_count_x,
        get=get_lim_count_x,
        min=1,
        default=2)
    trims_count_y: bpy.props.IntProperty(
        name='Trims Count V',
        description='Trims count Horizontal',
        set=set_lim_count_y,
        get=get_lim_count_y,
        min=1,
        default=2)
    grid_size: bpy.props.FloatVectorProperty(
        name="Grid Size",
        description="Size of the grid",
        subtype='COORDINATES',
        default=(1.0, 1.0),
        size=2,
        min=0)
    margin: bpy.props.FloatProperty(
        name='Margin',
        description='The gap between Trims',
        min=0.0,
        default=0.0,
        precision=3)
    remove_template: bpy.props.BoolProperty(
        name='Remove Template',
        default=False,
        description='Delete the Trim that served as a template')
    total: bpy.props.IntProperty(name='Count', default=1)
    limit: bpy.props.IntProperty(
        name='Trim Count Limit',
        description='Limit the number of trims. A large number of trims may cause Blender to freeze. This sets the threshold at which processing will stop',
        default=100, min=1)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def invoke(self, context, _event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'start_position')
        layout.prop(self, 'limit')
        layout.label(text='Count:')
        box = layout.box()
        row = box.row()
        row.alert = self.total >= self.limit
        p_alert_message = ' Limit reached' if row.alert else ''
        row.label(text='Total: ' + str(self.total) + p_alert_message)
        box.prop(self, 'trims_count_x')
        box.prop(self, 'trims_count_y')

        row = layout.row()
        row.enabled = self.start_position != 'INSIDE_ACTIVE'
        row.prop(self, 'grid_size')
        layout.prop(self, 'margin')
        row = layout.row()
        row.enabled = self.start_position in {'INSIDE_ACTIVE', 'BBOX_SELECTION'}
        row.prop(self, 'remove_template')

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:
            if self.start_position == 'INSIDE_ACTIVE':
                p_a_trim = ZuvTrimsheetUtils.getActiveTrim(context)
                a_index = p_data.trimsheet_index
                if p_a_trim is None:
                    self.report({'WARNING'}, "There are no Active Trim.")
                    return {'FINISHED'}
                else:
                    p_a_trim.selected = True
                    init_position = p_a_trim.left_bottom.copy()
                    self.grid_size.x = p_a_trim.width
                    self.grid_size.y = p_a_trim.height

            elif self.start_position == 'ZERO_WORLD':
                init_position = Vector((0.0, 0.0))

            elif self.start_position == 'CURSOR_2D':
                init_position = Cursor2D(context).uv_cursor_pos
            elif self.start_position == 'BBOX_SELECTION':
                p_trims_sel_idxs = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_data.trimsheet)

                if not len(p_trims_sel_idxs):
                    self.report({'WARNING'}, "There are no Selected Trims.")
                    return {'FINISHED'}

                points = sum([[p_data.trimsheet[idx].left_bottom, p_data.trimsheet[idx].top_right] for idx in p_trims_sel_idxs], [])
                bbox = BoundingBox2d(points=points)
                init_position = bbox.bot_left.copy()
                self.grid_size.x = bbox.len_x
                self.grid_size.y = bbox.len_y
            else:
                init_position = Vector((0.0, 0.0))

            self.total = self.trims_count_x * self.trims_count_y

            margin = self.margin
            if margin * (self.trims_count_x - 1) >= self.grid_size.x:
                margin = self.grid_size.x / (self.trims_count_x - 1) + 0.0001
                self.margin = margin

            gap_x = margin * (self.trims_count_x - 1)
            gap_y = margin * (self.trims_count_y - 1)

            try:
                x_size = (self.grid_size.x - gap_x) / self.trims_count_x
            except ZeroDivisionError:
                x_size = 0.0
            try:
                y_size = (self.grid_size.y - gap_y) / self.trims_count_y
            except ZeroDivisionError:
                y_size = 0.0

            p_trim_size = Vector((x_size, y_size))

            if self.total >= self.limit:
                self.report({'WARNING'}, 'The limit of the number of Trims has been reached.')

            for i in range(self.trims_count_x):
                p_trim_bl = init_position
                p_trim_tr = init_position + p_trim_size
                bbox = BoundingBox2d(points=(p_trim_bl, p_trim_tr))
                Trim.new_generic_from_bbox(context, bbox)

                init_y = Vector((init_position.x, init_position.y + p_trim_size.y + margin))
                for k in range(self.trims_count_y - 1):
                    p_trim_bl = init_y
                    p_trim_tr = init_y + p_trim_size
                    bbox = BoundingBox2d(points=(p_trim_bl, p_trim_tr))
                    Trim.new_generic_from_bbox(context, bbox)
                    init_y += Vector((0.0, margin + p_trim_size.y))

                init_position += Vector((margin + p_trim_size.x, 0.0))

            if self.start_position == 'INSIDE_ACTIVE':
                p_data.trimsheet_index = a_index

            if self.start_position == 'INSIDE_ACTIVE' and self.remove_template:
                p_data.trimsheet.remove(a_index)

            if self.start_position == 'BBOX_SELECTION' and self.remove_template:
                for idx in reversed(p_trims_sel_idxs):
                    p_data.trimsheet.remove(idx)

            return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_TrimCreateUDIM(bpy.types.Operator):
    bl_idname = "uv.zuv_trim_create_udim"
    bl_label = 'Add Trim UDIM'
    bl_description = 'Creates trims in positions and with UDIM tile sizes'
    bl_options = {'REGISTER', 'UNDO'}

    def get_udims_range_start(self):
        return self.get('udims_range_start', 1)

    def set_udims_range_start(self, value):
        if value >= self.udims_range_end:
            self['udims_range_start'] = self.udims_range_end
        else:
            self['udims_range_start'] = value

    def get_udims_range_end(self):
        return self.get('udims_range_end', 1)

    def set_udims_range_end(self, value):
        if value <= self.udims_range_end:
            self['udims_range_end'] = self.udims_range_start
        else:
            self['udims_range_end'] = value

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Trims creation mode",
        items=(
            ('SINGLE', "Single", "Create a single trim by number"),
            ('RANGE', "Range", "Create multiple trims in a given range")
        ),
        default='RANGE',
    )

    udims_range_start: bpy.props.IntProperty(
        name='Udims start',
        description='Udims range start',
        set=set_udims_range_start,
        get=get_udims_range_start,
        min=1,
        default=1)
    udims_range_end: bpy.props.IntProperty(
        name='Udims End',
        description='Udims range end',
        set=set_udims_range_end,
        get=get_udims_range_end,
        min=1,
        default=1)
    udim_single_mode_number: bpy.props.IntProperty(
        name='Udim number',
        description='UDIM number in single creation mode',
        min=1,
        default=1)

    total: bpy.props.IntProperty(name='Count', default=1)
    limit: bpy.props.IntProperty(name='Trim Count Limit', description='Limit the number of trims', default=100, min=1)

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def invoke(self, context, _event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'mode', expand=True)
        row = layout.row(align=True)

        if self.mode == 'RANGE':
            row.prop(self, 'udims_range_start')
            row.prop(self, 'udims_range_end')
        else:
            row.prop(self, 'udim_single_mode_number')

        layout.label(text='Count:')
        box = layout.box()
        box.prop(self, 'limit')
        row = box.row()
        row.alert = self.total >= self.limit
        p_alert_message = ' Limit reached' if row.alert else ''
        row.label(text='Total: ' + str(self.total) + p_alert_message)

    def execute(self, context: bpy.types.Context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        from ZenUV.ops.trimsheets.trimsheet_from_mesh import Trim
        from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory

        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_data is not None:

            if self.mode == 'RANGE':
                p_udims = UdimFactory.split_range_into_sublists(self.udims_range_start - 1, self.udims_range_end - 1, n=10)

                p_total = self.udims_range_end - self.udims_range_start + 1

                if p_total >= self.limit:
                    self.report({'WARNING'}, 'The limit of the number of Trims has been reached.')
            else:
                p_udims = [[self.udim_single_mode_number - 1, ], ]

            counter = 0
            for row in p_udims:
                for index in row:
                    if counter >= self.limit:
                        continue
                    p_trim_name = UdimFactory.int_to_udim(index)
                    p_trim_bl = UdimFactory.udim_to_uv(p_trim_name)
                    p_new_trim = Trim.new_generic_from_rect(context, (p_trim_bl[0], p_trim_bl[1] + 1, p_trim_bl[0] + 1, p_trim_bl[1]), name=str(p_trim_name))
                    p_new_trim.text_align = 'bl'
                    p_new_trim.text_offset[0] = 10.0
                    p_new_trim.text_offset[1] = 10.0
                    counter += 1

            self.total = counter

            return {'FINISHED'}

        return {'CANCELLED'}


class ZUV_OT_SetTrimWorldSize(bpy.types.Operator):
    bl_idname = "uv.zuv_set_trim_world_size"
    bl_label = "Set Trim World Size"
    bl_description = "Set trim 'World Size' property based on texture size. Works on selected trims"
    bl_options = {'REGISTER', 'UNDO'}

    use_trims: bpy.props.EnumProperty(
        name='Use',
        description='Operate on',
        items=[
            ('ALL', 'All Trims', 'Use all trims in trimsheet'),
            ('SELECTED', 'Selected Trims', 'Use selected trims in trimsheet')
        ],
        default='ALL'
    )

    texture_size: bpy.props.FloatVectorProperty(
        name="Texture Size",
        description="The texture size where trimsheet are located",
        size=2,
        default=(1.0, 1.0),
        subtype='XYZ'
    )
    texture_units: TransformSysOpsProps.get_units_enum(name='Texture Units')
    trim_units: TransformSysOpsProps.get_units_enum(name='Trim Units')

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvTrimsheetUtils.isTrimsheetEditable(context)

    def invoke(self, context, _event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'use_trims')
        box = layout.box()
        box.prop(self, 'texture_units')
        box.prop(self, 'texture_size')
        layout.prop(self, 'trim_units')

    def execute(self, context: bpy.types.Context):
        p_data = ZuvTrimsheetUtils.getTrimsheetOwner(context)

        if p_data is None:
            self.report({'WARNING'}, "There are no TrimSheet Data.")
            return {'CANCELLED'}

        p_trimsheet = p_data.trimsheet

        if not len(p_trimsheet):
            self.report({'WARNING'}, "There are no Trims.")
            return {'CANCELLED'}

        if self.use_trims == 'SELECTED':
            p_indices = ZuvTrimsheetUtils.getTrimsheetSelectedIndices(p_trimsheet)
            if not len(p_indices):
                self.report({'WARNING'}, "There are no selected Trims.")
                return {'CANCELLED'}
        else:
            p_indices = range(len(p_trimsheet))

        for i in p_indices:
            trim = p_trimsheet[i]
            p_mult = UnitsConverter.meters_based[self.texture_units]
            p_texture_size_in_meters = self.texture_size[0] * p_mult, self.texture_size[1] * p_mult

            p_trim_size_in_meters = self.convert_units_to_meters(p_texture_size_in_meters, trim.get_width(), trim.get_height())
            p_trim_mult = UnitsConverter.rev_con[self.trim_units]

            trim.world_size = p_trim_size_in_meters[0] * p_trim_mult, p_trim_size_in_meters[1] * p_trim_mult
            trim.world_size_units = self.trim_units

        p_data.trimsheet_mark_geometry_update()
        ZuvTrimsheetUtils.fix_undo()
        ZuvTrimsheetUtils.update_imageeditor_in_all_screens()

        return {'FINISHED'}

    def convert_units_to_meters(self, texture_size_in_meters, rect_width_generic_units, rect_height_generic_units):

        rect_width_m = rect_width_generic_units * texture_size_in_meters[0]
        rect_height_m = rect_height_generic_units * texture_size_in_meters[1]

        return rect_width_m, rect_height_m


class Trim:

    @classmethod
    def new_generic_from_bbox(cls, context: bpy.types.Context, bbox: BoundingBox2d, name: str = None) -> bool:
        res = bpy.ops.uv.zuv_trim_add('INVOKE_DEFAULT')
        if 'FINISHED' in res:
            p_new_trim = ZuvTrimsheetUtils.getActiveTrim(context)
            if p_new_trim:
                p_new_trim.rect = bbox.rect
                if name is not None:
                    p_new_trim.name = name
            return p_new_trim
        else:
            return False

    @classmethod
    def new_generic_from_rect(cls, context: bpy.types.Context, rect: list, name: str = None) -> bool:
        res = bpy.ops.uv.zuv_trim_add('INVOKE_DEFAULT')
        if 'FINISHED' in res:
            p_new_trim = ZuvTrimsheetUtils.getActiveTrim(context)
            if p_new_trim:
                p_new_trim.rect = rect
                if name is not None:
                    p_new_trim.name = name
            return p_new_trim
        else:
            return False


trim_creation_classes = (
    ZUV_OT_NewTrim,
    ZUV_OT_TrimCreateGrid,
    ZUV_OT_TrimCreateUDIM,
    ZUV_OT_SetTrimWorldSize
)


def register_trim_create():
    RegisterUtils.register(trim_creation_classes)


def unregister_trim_create():
    RegisterUtils.unregister(trim_creation_classes)
