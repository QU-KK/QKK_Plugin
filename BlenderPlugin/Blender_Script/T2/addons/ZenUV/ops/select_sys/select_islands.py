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

# Copyright 2024, Valeriy Yatsenko

import bpy
import bmesh

from ZenUV.utils.register_util import RegisterUtils

from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer,
    select_by_context,
    resort_objects_by_selection,
    select_islands)
from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory
from ZenUV.utils.bounding_box import BoundingBox2d, uv_area_bbox

from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.ui.pie import ZsPieFactory


def calculate_island_dimensions(island, uv_layer):

    min_v = float('inf')
    max_v = float('-inf')
    min_u = float('inf')
    max_u = float('-inf')

    for coo in (lp[uv_layer].uv for f in island for lp in f.loops):
        u, v = coo
        min_v = min(min_v, v)
        max_v = max(max_v, v)
        min_u = min(min_u, u)
        max_u = max(max_u, u)

    height = max_v - min_v
    width = max_u - min_u
    aspect_ratio = width / height if height != 0 else float('inf')

    return height, width, aspect_ratio


def split_ranges_evenly(data, num_groups, sort_key):
    """
    Uniformly divides data into the specified number of ranges, ensuring the exact number of ranges.
    """

    data.sort(key=lambda x: x[sort_key])
    total_items = len(data)

    base_chunk_size = total_items // num_groups
    extra_items = total_items % num_groups

    ranges = []
    start_index = 0

    for i in range(num_groups):
        chunk_size = base_chunk_size + (1 if i < extra_items else 0)
        end_index = start_index + chunk_size
        ranges.append(data[start_index:end_index])
        start_index = end_index

    return ranges


def split_ranges_by_gaps(data, num_groups, sort_key):
    """
    Divides data into ranges by the largest value gaps on the specified key.
    """

    data.sort(key=lambda x: x[sort_key])
    values = [item[sort_key] for item in data]

    gaps = [(i, values[i + 1] - values[i]) for i in range(len(values) - 1)]

    largest_gaps = sorted(gaps, key=lambda x: x[1], reverse=True)[:num_groups - 1]
    split_indices = sorted([gap[0] for gap in largest_gaps])

    ranges = []
    prev_index = 0
    for split_index in split_indices:
        ranges.append(data[prev_index:split_index + 1])
        prev_index = split_index + 1
    ranges.append(data[prev_index:])

    return ranges


def split_ranges_by_auto_gaps(data, sort_key, threshold):
    """
    Automatically determines the number of ranges based on the largest gaps in the data.
    """

    data.sort(key=lambda x: x[sort_key])
    values = [item[sort_key] for item in data]

    gaps = [(i, values[i + 1] - values[i]) for i in range(len(values) - 1)]

    split_indices = [i for i, gap in gaps if gap > threshold]

    ranges = []
    prev_index = 0
    for split_index in split_indices:
        ranges.append(data[prev_index:split_index + 1])
        prev_index = split_index + 1
    ranges.append(data[prev_index:])

    return ranges


class ZUV_OT_FilterIslandsByProperty(bpy.types.Operator):
    bl_idname = "uv.zenuv_filter_islands_by_property"
    bl_label = "Filter Islands by Property"
    bl_description = "Filter and select UV islands based on specific properties such as height, width, or aspect ratio, and divide them into ranges using customizable methods"
    bl_options = {'REGISTER', 'UNDO'}

    group_method: bpy.props.EnumProperty(
        name="Group Method",
        description="Method of defining groups",
        items=[
            ('EVEN', "Even Split", "Uniform division"),
            ('GAPS', "Split by Gaps", "Automatic splitting by gaps"),
            ('AUTO_GAPS', "Auto Split by Gaps", "Automatically determines the number of groups"),
        ],
        default='EVEN'
    )

    num_groups: bpy.props.IntProperty(
        name="Number of Groups",
        description="The number of groups for partitioning",
        default=5,
        min=1
    )
    island_property: bpy.props.EnumProperty(
        name="Property",
        description="The property by which islands will be grouped (height, width, or aspect ratio)",
        items=[
            ('HEIGHT', "Island Height", "Grouping based on island height"),
            ('WIDTH', "Island Width", "Grouping based on island width"),
            ('ASPECT_RATIO', "Island Aspect Ratio", "Grouping based on island aspect ratio"),
        ],
        default='HEIGHT'
    )
    group_index: bpy.props.IntProperty(
        name="Group Index",
        description="Specifies which group’s islands should be selected",
        default=1,
        min=1
    )
    threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Threshold for detecting large gaps (used in **Auto Split by Gaps** mode)",
        default=0.1,
        min=0
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'group_method')
        layout.prop(self, 'island_property')

        box = layout.box()
        box.label(text=f'Selected group {self.group_index} from {self.ranges_count} groups')

        row = layout.row()
        row.enabled = self.group_method != 'AUTO_GAPS'
        row.prop(self, 'num_groups')

        layout.prop(self, 'group_index')

        row = layout.row()
        row.enabled = self.group_method == 'AUTO_GAPS'
        row.prop(self, 'threshold')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        self.ranges_count = 0
        p_group_index = self.group_index - 1

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            uv_layer = verify_uv_layer(bm)

            if not uv_layer:
                continue

            island_data = [
                {
                    'island': island,
                    'height': height,
                    'width': width,
                    'aspect_ratio': aspect_ratio,
                }
                for island in island_util.get_island(context, bm, uv_layer)
                for height, width, aspect_ratio in [calculate_island_dimensions(island, uv_layer)]
            ]

            sort_key_map = {
                'HEIGHT': 'height',
                'WIDTH': 'width',
                'ASPECT_RATIO': 'aspect_ratio',
            }
            sort_key = sort_key_map[self.island_property]

            if self.group_method == 'EVEN':
                ranges = split_ranges_evenly(island_data, self.num_groups, sort_key)
            elif self.group_method == 'GAPS':
                ranges = split_ranges_by_gaps(island_data, self.num_groups, sort_key)
            elif self.group_method == 'AUTO_GAPS':
                ranges = split_ranges_by_auto_gaps(island_data, sort_key, self.threshold)

            self.ranges_count = len(ranges)

            if p_group_index >= len(ranges):
                self.group_index = len(ranges)
                p_group_index = len(ranges) - 1

            selected_range = ranges[p_group_index]
            selected_islands = [data['island'] for data in selected_range]

            bpy.ops.mesh.select_all(action='DESELECT')

            for island in selected_islands:
                for f in island:
                    f.select = True

            self.report({'INFO'}, f"Selected {len(selected_islands)} islands in group {self.group_index}.")

        return {'FINISHED'}


class ZUV_OP_SelectIslandByDirection(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_island_by_direction"
    bl_label = 'Select Island by Direction'
    bl_zen_short_name = 'Island by Direction'
    bl_description = 'Select island by direction'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    orient_direction: bpy.props.EnumProperty(
        name="Type",
        description="What type of islands will be selected",
        items=[
            ("HORIZONTAL", "Horizontal", "Horizontally oriented islands"),
            ("VERTICAL", "Vertical", "Vertically oriented islands"),
            ("RADIAL", "Radial", "Islands that are shaped like a circle"),
            ("NOT_ALIGNED", "Not Aligned", "Islands that are not aligned with the axes"),
        ],
        default="HORIZONTAL"
    )

    def execute(self, context):
        from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage

        def is_oriented(p_angle):
            return abs(p_angle) < 0.0087  # Half a degree

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "FACE"
        else:
            bpy.ops.mesh.select_mode(type="FACE")

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            for island in island_util.get_islands(context, bm):
                p_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)
                p_angle = p_bbox.get_orient_angle(ActiveUvImage(context).aspect)
                is_island_radial = p_bbox.is_circle()

                if not is_island_radial and self.orient_direction == 'HORIZONTAL':
                    if is_oriented(p_angle) and p_bbox.len_x > p_bbox.len_y:
                        select_by_context(context, bm, [island, ], state=True)

                elif self.orient_direction == 'VERTICAL':
                    if not is_island_radial and is_oriented(p_angle) and p_bbox.len_x < p_bbox.len_y:
                        select_by_context(context, bm, [island, ], state=True)

                elif self.orient_direction == 'RADIAL':
                    if is_island_radial:
                        select_by_context(context, bm, [island, ], state=True)

                else:
                    if not is_island_radial and not is_oriented(p_angle):
                        select_by_context(context, bm, [island, ], state=True)

            bm.select_flush_mode()

        return {'FINISHED'}


class ZUV_OP_SelectHoledIslands(bpy.types.Operator):
    bl_idname = 'uv.zenuv_select_holed_islands'
    bl_label = 'Select Holed Islands'
    bl_description = 'Selects islands that have holes within their geometry'
    bl_zen_short_name = 'Holed Islands'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {"CANCELLED"}

        from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
        from ZenUV.utils.base_clusters.stripes import UvStripes
        from ZenUV.utils.generic import bpy_deselect_by_context, switch_to_face_sel_mode

        if self.clear_selection:
            bpy_deselect_by_context(context)

        switch_to_face_sel_mode(context)

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            islands = island_util.get_islands(context, bm)

            for island in islands:
                cl = ZenCluster(context, obj, island, bm)
                p_uv_bound_edges = cl.get_bound_edges()
                z_stripes = UvStripes(p_uv_bound_edges, uv_layer)

                if z_stripes.is_cluster_holed():
                    select_by_context(context, bm, [island, ])

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_SelectInTile(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_in_tile"
    bl_label = 'Select In Tile'
    bl_zen_short_name = 'In Tile'
    bl_description = 'Selects islands depending on their location bounding box relative to the UV Area or UDIM tile'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    base: bpy.props.EnumProperty(
        name='Base',
        description='What to select relative to',
        items=[
            ('UV_AREA', 'UV Area', 'UV Area square'),
            ('UDIM_NUM', 'UDIM tile number', 'UDIM tile number'),
            ('ACTIVE_UDIM', 'Active UDIM', 'Active UDIM tile'),
            ('ANY_UDIM', 'Any UDIM', 'Any UDIM tile')
        ],
        default='UV_AREA')

    location: bpy.props.EnumProperty(
        name='Location',
        description="Location of the island",
        items=[
            ('INSIDE', 'Inside', 'Inside of UV Area'),
            ('OUTSIDE', 'Outside', 'Outside of UV Area'),
            ('CROSS', 'Cross', 'Crossing of UV Area borders'),
            ('MARGIN', 'Check Margin', 'Select islands where the margin between islands within the defined area and the area itself are less than the specified value'),
        ],
        default='INSIDE'
    )
    tile_number: bpy.props.IntProperty(
        name='Tile Number',
        description='Number of UDIM tile',
        default=1001,
        min=UdimFactory.min_udim_number,
        max=UdimFactory.max_udim_number)

    margin: bpy.props.FloatProperty(
        name='Margin',
        description='Minimum margin between the island and the defined area',
        min=0.0,
        default=0.005,
        precision=3
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'clear_selection')
        layout.prop(self, 'base')
        layout.prop(self, 'location')
        box = layout.box()
        box.enabled = self.base == 'UDIM_NUM'
        box.prop(self, 'tile_number')
        box = layout.box()
        box.enabled = self.location == 'MARGIN'
        box.prop(self, 'margin')

    def execute(self, context):
        from ZenUV.utils.generic import select_by_context
        UdimFactory.reset_report()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        if self.base == 'UV_AREA':
            p_bboxes = [uv_area_bbox(), ]
        elif self.base == 'UDIM_NUM':
            if UdimFactory.is_udim_number_valid(self.tile_number) is False:
                self.report({'WARNING'}, '"Tile Number" value is not valid UDIM number')
                return {'CANCELLED'}
            p_bboxes = [UdimFactory.get_bbox_of_udim(self.tile_number), ]
        elif self.base == 'ACTIVE_UDIM':
            p_tile = UdimFactory.get_active_udim_tile(context)
            if p_tile is not None:
                p_bboxes = [UdimFactory.get_bbox_of_udim(p_tile.number), ]
        elif self.base == 'ANY_UDIM':
            p_udims = UdimFactory.get_udims_from_loops(objs)
            p_bboxes = [UdimFactory.get_bbox_of_udim(tile) for tile in p_udims]
        else:
            raise RuntimeError('base value not in {"UV_AREA", "UDIM_NUM", "ACTIVE_UDIM", "ANY_UDIM"}')

        if UdimFactory.result is False:
            self.report({'WARNING'}, UdimFactory.message)
            return {'CANCELLED'}

        m_bbox: BoundingBox2d = None

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            for island in island_util.get_islands(context, bm):
                p_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)

                for m_bbox in p_bboxes:

                    b_is_overlapped = p_bbox.overlapped_with_bbox(m_bbox)
                    b_is_inside = p_bbox.inside_of_bbox(m_bbox)

                    if b_is_overlapped:
                        if self.location == 'INSIDE' and b_is_inside:
                            select_by_context(context, bm, [island, ], state=True)
                        elif self.location == 'CROSS' and not b_is_inside:
                            select_by_context(context, bm, [island, ], state=True)
                        elif self.location == 'MARGIN' and b_is_inside:
                            p_min_value = min([abs(m_bbox.rect[i] - p_bbox.rect[i]) for i in range(4)])
                            if p_min_value < self.margin:
                                select_by_context(context, bm, [island, ], state=True)
                    else:
                        if self.location == 'OUTSIDE' and b_is_inside is False:
                            select_by_context(context, bm, [island, ], state=True)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_Select_QuadedIslands(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_quaded_islands"
    bl_label = 'Select Quaded Islands'
    bl_zen_short_name = 'Quaded Islands'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects islands that consist only of quads'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Selection Type",
        items=[
            ("SELECT", "Select", "Select"),
            ("DESELECT", "Deselect", "Deselect")
            ],
        default="SELECT")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = self.mode == 'SELECT'
        row.prop(self, 'clear_selection')
        layout.prop(self, 'mode')

    def execute(self, context):
        from collections import Counter

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        p_state = self.mode == 'SELECT'

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            uv_layer = verify_uv_layer(bm)

            for island in island_util.get_islands(context, bm):
                if Counter((len(f.verts) == 4 for f in island))[False] == 0:
                    if context.space_data and context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                        if ZenPolls.version_since_3_2_0:
                            for f in island:
                                for lp in f.loops:
                                    lp[uv_layer].select = p_state
                                    lp[uv_layer].select_edge = p_state
                        else:
                            for f in island:
                                for lp in f.loops:
                                    lp[uv_layer].select = p_state
                    else:
                        for f in island:
                            f.select = p_state

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_Select_UV_Island(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_island"
    bl_label = 'Select Islands'
    bl_zen_short_name = 'Islands'
    bl_description = 'Select Islands by selected edge/face of the Islands'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        objs = resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        select_islands(context, objs)
        context.tool_settings.mesh_select_mode = [False, False, True]

        return {'FINISHED'}


classes = (
    ZUV_OT_FilterIslandsByProperty,
    ZUV_OP_SelectIslandByDirection,
    ZUV_OP_SelectHoledIslands,
    ZUV_OT_SelectInTile,
    ZUV_OT_Select_QuadedIslands,
    ZUV_OT_Select_UV_Island
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
