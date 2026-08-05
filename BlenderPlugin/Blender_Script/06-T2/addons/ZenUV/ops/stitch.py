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
from dataclasses import dataclass, field
from math import radians
from mathutils import Vector
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    resort_objects_by_selection,
    verify_uv_layer
)
from ZenUV.utils.base_clusters.stripes import UvStripes
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
from ZenUV.utils.vlog import Log
from ZenUV.utils.transform import UvTransformUtils
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
from ZenUV.utils.get_uv_islands import LoopsFactory
from ZenUV.utils.annotations_toolbox.math_visualizer import MathVisualizer

from ZenUV.utils.blender_zen_utils import ZenPolls


class MatchAndStitchViz:

    area_type: str = None

    island_1_color = (0.7, 0.0, 0.05)
    island_2_color = (0.05, 0.6, 0.2)

    direction_vectors = []

    island_1_source_vec = []
    island_2_source_vec = []
    island_1_text_position = 0.0
    island_2_text_position = 0.0

    arrow_size = 0.05

    @classmethod
    def show(cls, context, uv_layer):
        vis = MathVisualizer(context, 'ZenUV MatchAndStitch')

        letters_size = 2.4  # NOTE: non-screen: 0.025
        letters_position = (10, 10, 0)  # NOTE: non-screen: (0, -0.1, 0)
        letters_line_width = 1  # NOTE: non-screen: 3
        letters_screen_mode = True

        vis.add_text(
            'Description', 0, "Zen UV | Match and Stitch | islands dependencies",
            line_width=letters_line_width, letters_size=letters_size, position=letters_position,
            is_screen_mode=letters_screen_mode)

        p_text_size = cls.arrow_size * 0.5
        vis.add_text(
            'Static Island', 0,
            "Static Island",
            color=cls.island_1_color,
            line_width=3,
            letters_size=p_text_size,
            position=cls.island_1_text_position)
        vis.add_text(
            'Moved Island', 0,
            "Moved Island",
            color=cls.island_2_color,
            line_width=3,
            letters_size=p_text_size,
            position=cls.island_2_text_position)

        vis.add_vector(
            'Static Island Source',
            0,
            [cls.island_1_source_vec, ],
            color=cls.island_1_color,
            clear=True,
            is_constant_arrow_size=True,
            arrow_size=cls.arrow_size)

        vis.add_vector(
            'Mover Island Source',
            0,
            [cls.island_2_source_vec, ],
            color=cls.island_2_color,
            clear=True,
            is_constant_arrow_size=True,
            arrow_size=cls.arrow_size)

        vis.add_vector(
            'Direction',
            0,
            cls.direction_vectors,
            color=(0.1, 0.2, 0.6),
            clear=True,
            is_constant_arrow_size=True,
            arrow_size=cls.arrow_size)


@dataclass
class TransformSwitch:

    location: bool = False
    rotation: bool = False
    scale: bool = False

    def to_list(self):
        return [self.location, self.rotation, self.scale]

    def set_state(self, operator):
        if operator.allow_match:
            self.location = operator.match_pos
            self.rotation = operator.match_rotation
            self.scale = operator.match_scale
        else:
            self.location = False
            self.rotation = False
            self.scale = False


class ZUV_OT_MatchAndStitch(bpy.types.Operator):
    bl_idname = "uv.zenuv_match_stitch"
    bl_label = 'Match and Stitch'
    bl_description = 'Matching the position, rotation, and scale of the island. Stitch the vertices together, if possible'
    bl_options = {'REGISTER', 'UNDO'}

    base_index: bpy.props.IntProperty(name='Base Island', default=0, min=0)
    allow_match: bpy.props.BoolProperty(
        name='Match',
        description='Match Island parameters',
        default=True
    )
    match_pos: bpy.props.BoolProperty(
        name='Position',
        description='Match Island position',
        default=True
    )
    match_rotation: bpy.props.BoolProperty(
        name='Rotation',
        description='Match Island rotation',
        default=True
    )
    match_scale: bpy.props.BoolProperty(
        name='Scale',
        description='Match Island size',
        default=True
    )
    reverse_matched: bpy.props.BoolProperty(
        name='Reverse Matched',
        description='Change the direction to the opposite direction for the matched island',
        default=False
    )
    reverse_base: bpy.props.BoolProperty(
        name='Reverse Base',
        description='Change the direction to the opposite direction for the base island',
        default=False
    )
    cycled_island: bpy.props.BoolProperty(
        name='Cycled Island',
        description='Activate the option if you want to match cycled edgeloops. For example a disk to a round hole',
        default=False
    )
    stripe_offset: bpy.props.IntProperty(name='Offset loop', default=0)
    allow_stitch: bpy.props.BoolProperty(
        name='Stitch',
        description='Stitch the vertices together, if possible',
        default=False
    )
    average: bpy.props.BoolProperty(
        name='Average',
        description='Average Stitching',
        default=True
    )
    ignore_pin: bpy.props.BoolProperty(
        name='Ignore Pin',
        description='Ignore Pinned vertices',
        default=True
    )
    clear_seam: bpy.props.BoolProperty(
        name='Clear Seams',
        description='Clear the seams on the stitched edges',
        default=True
    )
    clear_pin: bpy.props.BoolProperty(
        name='Clear Pin',
        description='Clear the Pins on the Primary edgeloop',
        default=True
    )
    allow_postprocess: bpy.props.BoolProperty(
        name='Postprocess',
        description='Allow Postprocess',
        default=False
    )
    adv_offset: bpy.props.FloatVectorProperty(
        name='Offset',
        description='Advanced Offset',
        size=2,
        default=(0.0, 0.0),
        subtype='COORDINATES',
        precision=3
    )
    adv_rotate: bpy.props.FloatProperty(
        name='Rotate',
        description='Advanced Rotate',
        default=0.0,
        precision=3
    )
    adv_scale: bpy.props.FloatProperty(
        name='Scale',
        description='Advanced Scale',
        default=1.0,
        precision=3
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'base_index')

        layout.prop(self, 'allow_match', text='Match:')
        self.draw_match(layout)

        layout.prop(self, 'allow_stitch', text='Stitch:')
        self.draw_stitch(layout)

        layout.prop(self, 'allow_postprocess', text='Postprocess:')
        self.draw_postprocess(layout)

    def draw_postprocess(self, layout):
        box = layout.box()
        box.enabled = self.allow_postprocess
        box.prop(self, 'adv_offset')
        box.prop(self, 'adv_rotate')
        box.prop(self, 'adv_scale')
        box = box.box()
        row = box.row()
        row.prop(self, 'clear_pin')
        row.prop(self, 'clear_seam')

    def draw_stitch(self, layout):
        box = layout.box()
        box.enabled = self.allow_stitch
        box.prop(self, 'ignore_pin')
        box.prop(self, 'average')
        box.prop(self, 'stripe_offset')

    def draw_match(self, layout):
        box = layout.box()
        box.enabled = self.allow_match
        row = box.row()
        row.prop(self, 'match_pos')
        row.prop(self, 'match_rotation')
        row.prop(self, 'match_scale')
        row = box.row()
        row.prop(self, 'reverse_base')
        row.prop(self, 'reverse_matched')
        box.prop(self, 'cycled_island')

    def reset_props(self):
        # Match
        if not self.allow_match:
            self.match_pos = True
            self.match_rotation = True
            self.match_scale = True
            self.reverse_base = False
            self.reverse_matched = False
        # Stitch
        if not self.allow_stitch:
            self.ignore_pin = True
            self.average = True
            self.stripe_offset = 0
        # Postprocess
        if not self.allow_postprocess:
            self.adv_offset = (0.0, 0.0)
            self.adv_rotate = 0.0
            self.adv_scale = 1.0

            self.clear_pin = True
            self.clear_seam = True

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        self.reset_props()

        Matcher = TransformSwitch()
        Matcher.set_state(self)

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            islands = island_util.get_island(context, bm, uv_layer, _sorted=True)
            islands = sorted(islands, key=(lambda x: x[0].index))

            if len(islands) == 1:
                self.report({'WARNING'}, "Only one Island has been selected. For normal operation, two islands must be selected.")
            if len(islands) > 2:
                self.report({'WARNING'}, "More than two islands selected. The result may not be acceptable.")

            clusters = list()
            for idx, island in enumerate(islands):
                clusters.append(ZenCluster(context, obj, island, bm, idx))
                p_cl = clusters[-1]
                p_edges = p_cl.get_selected_edges()
                if not len(p_edges):
                    clusters.pop(-1)
                    continue
                z_stripes = UvStripes(p_cl.get_selected_edges(), p_cl.uv_layer).get_stripes_from_selection()
                p_cl.stripes = z_stripes.stripes[0]
                p_cl.stripes.orient_alternative()

            if not len(clusters):
                self.report({'WARNING'}, "No islands with correctly selected edge loops were found.")
                return {'CANCELLED'}

            m_clusters = [cl for cl in clusters if True in [n.pinned for n in cl.stripes.nodes]]

            # if len(m_clusters) > 1:
            #     self.report({'WARNING'}, "More than one island is pinned down. The result may not be acceptable")
            if not len(m_clusters):
                # self.report({'WARNING'}, "No Primary island were found for processing")
                # return {'FINISHED'}
                b_index = self.base_index if self.base_index <= len(islands) - 1 else -1
                m_cluster = clusters.pop(b_index)  # type: ZenCluster
            else:
                b_index = 0
                m_cluster = clusters.pop(m_clusters[b_index].index)  # type: ZenCluster

            if self.reverse_base:
                m_cluster.stripes.reverse()

            result_scale = 1.0

            for cl in clusters:
                if cl.stripes.mesh_cycled and m_cluster.stripes.mesh_cycled and self.cycled_island:
                    is_cycled = True
                else:
                    is_cycled = False

                if self.reverse_matched:
                    cl.stripes.reverse()

                if is_cycled and not cl.stripes.is_matched_direction_for_stitch(m_cluster.stripes):
                    cl.stripes.reverse()

                cl.stripes.match_by_offset(m_cluster.stripes)

                if is_cycled:
                    Matcher.rotation = True

                    if Matcher.scale is True:
                        result_scale = cl.stripes.bounding_box.get_diff_scale_vec(m_cluster.stripes.bounding_box)[0]
                        result_scale += self.adv_scale - 1.0
                        Matcher.scale = False

                    origin_pivot = m_cluster.stripes.bounding_box.center
                    cl_pivot = cl.stripes.bounding_box.center
                else:
                    result_scale = self.adv_scale
                    origin_pivot = m_cluster.stripes.head_co
                    cl_pivot = cl.stripes.head_co

                if self.stripe_offset != 0:
                    cl.stripes.offset(self.stripe_offset)

                UvTransformUtils.match_islands_by_vectors(
                    matched_island=cl.island,
                    uv_layer=uv_layer,
                    origin_pivot=origin_pivot,
                    origin_vec=m_cluster.stripes.base_vec,
                    matched_pivot=cl_pivot,
                    matched_vec=cl.stripes.base_vec,
                    image_ratio=ActiveUvImage(context).aspect,
                    adv_offset=self.adv_offset,
                    adv_rotate=radians(-self.adv_rotate),
                    adv_scale=result_scale,
                    matching=Matcher.to_list(),
                    is_cycled=is_cycled
                )
                if context.scene.zen_uv.is_show_ops_annotations:
                    main_full_vec = (origin_pivot, origin_pivot + m_cluster.stripes.base_vec)
                    main_free_vec = main_full_vec[1] - main_full_vec[0]
                    cl_full_vec = (cl_pivot, cl_pivot + cl.stripes.base_vec)
                    cl_free_vec = cl_full_vec[1] - cl_full_vec[0]

                    MatchAndStitchViz.arrow_size = main_free_vec.length * 0.03
                    main_vector_offset = MatchAndStitchViz.arrow_size * 0.1

                    origin_ort = main_free_vec.orthogonal().normalized() * main_vector_offset

                    MatchAndStitchViz.island_1_source_vec = [vec + origin_ort for vec in main_full_vec]

                    cl_ort = cl_free_vec.orthogonal().normalized() * main_vector_offset

                    MatchAndStitchViz.island_2_source_vec = [vec + cl_ort for vec in cl_full_vec]

                    text_1_position = origin_pivot + main_free_vec * 0.5
                    text_2_position = cl_pivot + cl_free_vec * 0.5

                    MatchAndStitchViz.island_1_text_position = (text_1_position[0], text_1_position[1], 0)
                    MatchAndStitchViz.island_2_text_position = (text_2_position[0], text_2_position[1], 0)

                    dir_offset = main_free_vec.length * 0.03
                    free_dir_vec_01 = main_full_vec[0] - cl_full_vec[0]
                    free_dir_vec_02 = main_full_vec[1] - cl_full_vec[1]

                    dir_01_start_position = free_dir_vec_01.normalized() * dir_offset
                    dir_01_end_position = free_dir_vec_01.normalized() * -dir_offset

                    dir_02_start_position = free_dir_vec_02.normalized() * dir_offset
                    dir_02_end_position = free_dir_vec_02.normalized() * -dir_offset

                    # dir_01_start_position = dir_02_start_position = dir_01_end_position = dir_02_end_position = Vector((0.0, 0.0))

                    MatchAndStitchViz.direction_vectors = (
                        [cl_full_vec[0] + dir_01_start_position, main_full_vec[0] + dir_01_end_position],
                        [cl_full_vec[1] + dir_02_start_position, main_full_vec[1] + dir_02_end_position])

                    MatchAndStitchViz.show(context, uv_layer)

                if self.allow_stitch:
                    for c, m in zip(cl.stripes.nodes, m_cluster.stripes.nodes):
                        if self.allow_match:
                            c.update_uv_co()
                        if not self.average:
                            if self.ignore_pin:
                                c.set_position(m.uv_co)
                            else:
                                if not c.pinned:
                                    c.set_position(m.uv_co)
                        else:
                            if self.ignore_pin:
                                pos = (c.uv_co + m.uv_co) * 0.5
                                c.set_position(pos)
                                m.set_position(pos)
                            else:
                                if m.pinned and c.pinned:
                                    continue
                                if m.pinned and not c.pinned:
                                    c.set_position(m.uv_co)
                                elif not m.pinned and c.pinned:
                                    m.set_position(c.uv_co)
                                else:
                                    pos = (c.uv_co + m.uv_co) * 0.5
                                    c.set_position(pos)
                                    m.set_position(pos)

                if self.allow_stitch and self.clear_seam:
                    for edge in m_cluster.stripes.stripe:
                        edge.mesh_edge.seam = False

            if self.clear_pin:
                for node in m_cluster.stripes.nodes:
                    node.pinned = False

            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


class ZUV_OT_MergeUvVerts(bpy.types.Operator):
    bl_idname = 'uv.zenuv_merge_uv_verts'
    bl_label = 'Merge UV Verts'
    bl_description = 'Merge UV vertices belonging to the same mesh vertex'
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(
        name='Threshold',
        description='Distance beyond which the merger does not take place',
        default=0.01,
        precision=3,
        step=0.1)
    unselected: bpy.props.BoolProperty(
        name='Unselected',
        description='Merge all matching vertices. Not only the selected',
        default=False)
    use_pinned: bpy.props.BoolProperty(
        name='Use Pinned',
        description='Pinned vertices remain in place. The unpinned ones will be moved to the pinned ones',
        default=False)
    use_seams: bpy.props.BoolProperty(
        name='Use Seams',
        description='Edges marked as seams will be ignored',
        default=False)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.ops.quadrify import ZenFollowQuad

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)
            if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                if self.unselected:
                    p_is_no_sync = False
                    bm_verts = (v for v in bm.verts if v.select and True not in [f.hide for f in v.link_faces])
                else:
                    bm_verts = {loop.vert for loop in LoopsFactory._loops_by_sel_mode(context, bm.faces, uv_layer, only_uv_edges=False, per_face=False)}
                    p_is_no_sync = True
            else:
                if self.unselected:
                    bm_verts = bm.verts
                else:
                    bm_verts = (v for v in bm.verts if v.select and True not in [f.hide for f in v.link_faces])
                p_is_no_sync = False

            ZenFollowQuad.merge_uv_verts(
                context,
                bm_verts,
                verify_uv_layer(bm),
                self.threshold,
                p_is_no_sync,
                self.use_pinned,
                self.use_seams)

            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


@dataclass
class UvNode:

    vis_layer_name = 'ZenUV Split'
    vis_letter_size = None

    index: int = 0
    loops: list = field(default_factory=list)
    loops_count: int = 0
    neighbors: set = field(default_factory=set)
    neighbors_count: int = 0
    result_coordinates: dict = field(default_factory=dict)

    vis_directions: list = field(default_factory=list)

    def __hash__(self):
        return hash(self.index)

    def init(self):
        self.loops_count = len(self.loops)

    def show_in_annotations(self, context, uv_layer):
        vis = MathVisualizer(context, UvNode.vis_layer_name)
        if len(self.loops):

            self._set_letter_size(uv_layer)

            p_position = self.loops[0][uv_layer].uv

            vis.add_dot(
                'point', 0, color=(1, 0, 0),
                position=p_position,
                clear=False, size=UvNode.vis_letter_size * 0.01, line_width=6)

            # Debug only
            # vis.add_text(
            #     'indexes',
            #     0,
            #     f'n{self.index}:v{self.loops[0].vert.index}:r{self.neighbors_count}',
            #     letters_size=UvNode.vis_letter_size * 0.1,
            #     position=(
            #         p_position[0] + UvNode.vis_letter_size * 0.01,
            #         p_position[1] + UvNode.vis_letter_size * 0.01, 0),
            #     clear=False)
        else:
            raise RuntimeError('Zen UV.UvNode.loops is empty')

    def _set_letter_size(self, uv_layer):
        if UvNode.vis_letter_size is None:
            from ZenUV.utils.bounding_box import BoundingBox2d
            p_bbox = BoundingBox2d(points=[lp.link_loop_next[uv_layer].uv for lp in self.loops])
            p_size = ((p_bbox.len_x + p_bbox.len_y) * 0.5) * 0.6
            UvNode.vis_letter_size = p_size

    def show_directions(self, context, uv_layer):
        vis = MathVisualizer(context, UvNode.vis_layer_name)

        self._set_letter_size(uv_layer)

        if len(self.vis_directions) != 0:
            vis.add_vector(
                'corners',
                0,
                self.vis_directions,
                color=(0.3, 0.3, 0.7),
                clear=False,
                is_constant_arrow_size=True,
                arrow_size=UvNode.vis_letter_size * 0.05,
                show_in_front=False)
        else:
            pass
            Log.debug('Split', f'Node {self.index} do not have direction vectors')


class UvSplitProcessor:

    def __init__(self, context: bpy.types.Context) -> None:
        self.show_in_annotations: bool = False
        self.is_not_sync: bool = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        self.is_pure_uv_edge_mode: bool = context.space_data.type == 'IMAGE_EDITOR' and self.is_not_sync and ZenPolls.version_since_3_2_0 and context.scene.tool_settings.uv_select_mode == "EDGE"

    def compound_nodes(self, uv_layer: bmesh.types.BMLayerItem, groupped_bmesh_loops: list) -> list[list, list]:
        from ZenUV.utils.generic import Scope
        from collections import defaultdict, Counter

        p_node_groups = []
        for group in groupped_bmesh_loops:
            scp = Scope()
            scp.data = defaultdict(list)
            for loop in group:
                scp.data[loop[uv_layer].uv.to_tuple()].append(loop)
            p_node_groups.append(scp)

        node_groups = []
        for node_group in p_node_groups:
            p_group = []
            for idx, lps in enumerate(node_group.data.items()):
                p_group.append(UvNode(index=idx, loops=lps[1]))
            node_groups.append(p_group)

        i_stats = 0

        if self.is_pure_uv_edge_mode:
            for node_group in node_groups:
                for node in node_group:
                    for loop in node.loops:
                        if loop[uv_layer].select_edge:
                            node.neighbors_count += 1
                            i_stats += 1
        else:
            for node_group in node_groups:
                for node in node_group:
                    node.neighbors_count = Counter([e.other_vert(node.loops[0].vert).select for e in node.loops[0].vert.link_edges])[True]

        return node_groups

    def calculate_loops_positions(self, uv_layer: bmesh.types.BMLayerItem, node_groups: list, distance: float, is_split_ends: bool, is_per_vertex: bool):
        loop: bmesh.types.BMLoop = None
        node: UvNode = None

        is_split_ends = False if is_per_vertex else is_split_ends

        for node_group in node_groups:
            for node in node_group:
                if node.neighbors_count >= 1:
                    if node.neighbors_count == 1 and len(node.loops) > 2:
                        if is_split_ends:
                            if self.is_not_sync:
                                for loop in node.loops:
                                    self._handle_simple_case(uv_layer, node, loop, distance)
                            else:
                                # Split ends in no sync
                                for loop in node.loops:
                                    if loop.edge.select or loop.link_loop_prev.edge.select:
                                        self._handle_simple_case(uv_layer, node, loop, distance)
                                    else:
                                        node.result_coordinates[loop.index] = loop[uv_layer].uv

                        else:
                            if is_per_vertex:
                                self._split_per_vertex(uv_layer, node, distance)
                            else:
                                for loop in node.loops:
                                    node.result_coordinates[loop.index] = loop[uv_layer].uv
                        continue

                    if is_per_vertex:
                        self._split_per_vertex(uv_layer, node, distance)
                    else:
                        self._calc_coordinates(uv_layer, node, distance)
                else:
                    # Handle nodes with ONE vertex selected
                    if is_per_vertex:
                        self._split_per_vertex(uv_layer, node, distance)
                    else:
                        for loop in node.loops:
                            node.result_coordinates[loop.index] = loop[uv_layer].uv

    def collect_neighbors(self, node_groups: list):
        for node_group in node_groups:
            for node in node_group:
                for loop in node.loops:
                    for adj_node in node_group:
                        if loop.link_loop_prev in adj_node.loops or loop.link_loop_next in adj_node.loops:
                            node.neighbors.add(adj_node)
                            adj_node.neighbors.add(node)
        return node_groups

    def set_uv_coordinates(self, node_groups: list, uv_layer: bmesh.types.BMLayerItem):
        if not len(node_groups):
            return
        if len(node_groups[0][0].result_coordinates) == 0:
            raise RuntimeError('The result_coordinates were not calculated')
        for node_group in node_groups:
            for node in node_group:
                for loop in node.loops:
                    loop[uv_layer].uv = node.result_coordinates[loop.index]

    def _calc_coordinates(self, uv_layer: bmesh.types.BMLayerItem, node: UvNode, distance: float):
        for loop in node.loops:
            if loop.index in node.result_coordinates:
                continue

            if self._is_no_selected(loop, uv_layer):
                coo = self._handle_two_vectors(uv_layer, loop, node, distance)
                node.result_coordinates[loop.index] = coo

                node.result_coordinates[loop.link_loop_radial_next.link_loop_next.index] = coo
                node.result_coordinates[loop.link_loop_prev.link_loop_radial_next.index] = coo

            elif self._is_all_selected(loop, uv_layer):
                coo = self._handle_two_vectors(uv_layer, loop, node, distance)
                node.result_coordinates[loop.index] = coo

            else:
                coo = self._handle_simple_case(uv_layer, node, loop, distance)

            if self.show_in_annotations:
                node.vis_directions.append((Vector(loop[uv_layer].uv.to_tuple()), coo))

    def show_nodes(self, node_groups: list):
        print(f'Total groups: {len(node_groups)}')
        for idx, node_group in enumerate(node_groups):
            print(f'Nodes in group {idx} --> {len(node_group)}')
            print('Node Statistic:')
            for node in node_group:
                print(f'node {node.index}')
                if len(node.neighbors):
                    print('\tadj -> ')
                    for adj_node in node.neighbors:
                        print(f'\t\t{adj_node.index}')
                else:
                    print('no adj')

    def _split_per_vertex(self, uv_layer: bmesh.types.BMLayerItem, node: UvNode, distance: float):
        for loop in node.loops:
            base_pos = loop[uv_layer].uv
            p_new_pos = base_pos + (loop.link_loop_next.link_loop_next[uv_layer].uv - base_pos).normalized() * distance
            loop[uv_layer].uv = p_new_pos
            node.result_coordinates[loop.index] = p_new_pos

    def _is_all_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_next = loop.link_loop_next
        lp_prev = loop.link_loop_prev

        if self.is_pure_uv_edge_mode:
            return lp[uv_layer].select_edge and lp_prev[uv_layer].select_edge

        elif self.is_not_sync:
            return lp[uv_layer].select and lp_next[uv_layer].select and lp_prev[uv_layer].select

        else:
            return lp.vert.select and lp_next.vert.select and lp_prev.vert.select

    def _is_no_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_next = loop.link_loop_next
        lp_prev = loop.link_loop_prev

        if self.is_pure_uv_edge_mode:
            return not lp[uv_layer].select_edge and not lp_prev[uv_layer].select_edge

        elif self.is_not_sync:
            return lp[uv_layer].select and not lp_next[uv_layer].select and not lp_prev[uv_layer].select

        else:
            return lp.vert.select and not lp_next.vert.select and not lp_prev.vert.select

    def _is_not_prev_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_prev = loop.link_loop_prev

        if self.is_pure_uv_edge_mode:
            return lp[uv_layer].select and not lp_prev[uv_layer].select_edge
        elif self.is_not_sync:
            return lp[uv_layer].select and not lp_prev[uv_layer].select
        else:
            return lp.vert.select and not lp_prev.vert.select

    def _is_not_next_selected(self, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
        lp = loop
        lp_next = loop.link_loop_next

        if self.is_pure_uv_edge_mode:
            return lp[uv_layer].select and lp_next[uv_layer].select_edge
        elif self.is_not_sync:
            return lp[uv_layer].select and not lp_next[uv_layer].select
        else:
            return lp.vert.select and not lp_next.vert.select

    def _handle_simple_case(self, uv_layer: bmesh.types.BMLayerItem, node: UvNode, loop: bmesh.types.BMLoop, distance: float) -> Vector:
        base_pos = Vector(loop[uv_layer].uv.to_tuple())
        if self.is_pure_uv_edge_mode:
            if loop[uv_layer].select_edge:
                coo = base_pos + (loop.link_loop_prev[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            elif loop.link_loop_prev[uv_layer].select_edge:
                coo = base_pos + (loop.link_loop_next[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            else:
                coo = node.result_coordinates[loop.index] = base_pos
        else:
            if self._is_not_prev_selected(loop, uv_layer):
                coo = base_pos + (loop.link_loop_prev[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            elif self._is_not_next_selected(loop, uv_layer):
                coo = base_pos + (loop.link_loop_next[uv_layer].uv - base_pos).normalized() * distance
                node.result_coordinates[loop.index] = coo
            else:
                coo = node.result_coordinates[loop.index] = base_pos

        if self.show_in_annotations:
            node.vis_directions.append((base_pos, coo))

        return coo

    def _handle_two_vectors(self, uv_layer: bmesh.types.BMLayerItem, loop: bmesh.types.BMLoop, node: UvNode, distance: float):
        from math import sqrt
        base_pos = loop[uv_layer].uv.copy().freeze()
        p_v01 = (loop.link_loop_next[uv_layer].uv - base_pos)
        p_v02 = (loop.link_loop_prev[uv_layer].uv - base_pos)
        p_offset = sqrt(2) * distance
        p_direction = (p_v01.normalized() + p_v02.normalized()) * 0.5
        # node.vis_directions.append((base_pos, base_pos + p_direction.normalized() * p_offset))

        return base_pos + p_direction.normalized() * p_offset


class ZUV_OT_Split(bpy.types.Operator):
    bl_idname = 'uv.zenuv_split'
    bl_label = 'Split UV'
    bl_description = 'Splits selected in the UV'
    bl_options = {'REGISTER', 'UNDO'}

    set_minimum: bpy.props.BoolProperty(
        name='Minimum distance',
        description='Sets the smallest distance sufficient for splitting but not visible to the eye',
        default=False)
    distance: bpy.props.FloatProperty(
        name='Distance',
        description='The distance to which the vertices need to be moved',
        default=0.005,
        min=0.0,
        precision=3,
        step=0.1)
    per_vertex: bpy.props.BoolProperty(
        name='Per Vertex',
        description='Split each vertex separately',
        default=False)
    split_ends: bpy.props.BoolProperty(
        name='Split Ends',
        description='Splits the ends. The gap remains the same along the entire length',
        default=False)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'set_minimum')
        row = layout.row()
        row.enabled = not self.set_minimum
        row.prop(self, 'distance')
        layout.prop(self, 'per_vertex')
        row = layout.row()
        row.enabled = not self.per_vertex
        row.prop(self, 'split_ends')

    def execute(self, context):
        if self.set_minimum is False and self.distance == 0.0:
            self.report({'WARNING'}, "Zen UV: The split was not performed. Distance is zero")
            return {'FINISHED'}

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}

        objs = resort_objects_by_selection(context, objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        if context.scene.zen_uv.is_show_ops_annotations:
            vis = MathVisualizer(context, UvNode.vis_layer_name)
            vis.clear('indexes', 0)
            vis.clear('point', 0)
            vis.clear('corners', 0)

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            p_loops = LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)

            SP = UvSplitProcessor(context)

            node_groups = SP.compound_nodes(uv_layer, p_loops)

            # Must be before computation
            if context.scene.zen_uv.is_show_ops_annotations:
                SP.show_in_annotations = True
                for node_group in node_groups:
                    for node in node_group:
                        node.show_in_annotations(context, uv_layer)

            # 1e-4 minimal value for native 'Select Linked' compatibility
            SP.calculate_loops_positions(
                uv_layer=uv_layer,
                node_groups=node_groups,
                distance=1e-4 if self.set_minimum else self.distance * 0.5,
                is_split_ends=self.split_ends,
                is_per_vertex=self.per_vertex)

            SP.set_uv_coordinates(node_groups, uv_layer)

            if context.scene.zen_uv.is_show_ops_annotations:
                for node_group in node_groups:
                    for node in node_group:
                        node.show_directions(context, uv_layer)

            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


classes = (
    ZUV_OT_MatchAndStitch,
    ZUV_OT_MergeUvVerts,
    ZUV_OT_Split

)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
