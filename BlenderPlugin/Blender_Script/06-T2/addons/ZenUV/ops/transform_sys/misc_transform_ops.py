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

# Copyright 2025, Valeriy Yatsenko - lightbio@gmail.com


import bpy
import bmesh
from mathutils import Vector
from itertools import product

from ...utils.register_util import RegisterUtils

from ...utils.uv_factory import UvIslandUtils
from ...utils.loops_factory import LoopsFactory
from ...utils.blender_zen_utils import is_loop_domain, get_selection_mode

from ...utils.shortest_path import ShortPathUtils, GraphProcessor
from ...utils.generic import bpy_select_by_context, ResortObjects
from ...utils.iter_utils import IterUtils
from ...ops.zen_unwrap.props import ZenUnwrapProps
from ...ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
from ...utils.bounding_box import BoundingBox2d
from ...ops.transform_sys.transform_utils.transform_uvs import TransformUVS
from ...utils.mesh_factory import MeshIslandUtils


class ZUV_OT_SelectionToCircle(bpy.types.Operator):
    bl_idname = "uv.zenuv_selection_to_circle"
    bl_label = 'Circular'
    bl_zen_short_name = 'Circular'
    bl_description = 'Transform selection to the circular shape'
    bl_options = {'REGISTER', 'UNDO'}

    evenly: bpy.props.BoolProperty(
        name='Evenly',
        description='Arrange the vertices evenly',
        default=False
    )
    radius_mode: bpy.props.EnumProperty(
        name="Radius mode",
        description="Determines how to set the radius of a circle",
        items=[
            ('AUTO', "Automatically", "Calculate radius automatically"),
            ('MANUAL', "Custom", "Use manually entered radius")
        ],
        default='AUTO'
    )
    radius: bpy.props.FloatProperty(
        name="Radius",
        description="Circle radius",
        default=0.5,
        min=0.0,
    )
    amount: bpy.props.FloatProperty(
        name="Amount",
        description="Position along the vector from start to end, in percent (0-100)",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'evenly')
        layout.prop(self, 'amount')
        layout.prop(self, 'radius_mode')
        row = layout.row()
        row.enabled = self.radius_mode == 'MANUAL'
        row.prop(self, 'radius')

    def execute(self, context):
        import math
        from ...utils.base_clusters.stripes import UvStripes, Stripe
        from ...utils.base_clusters.zen_cluster import ZenCluster, UvVertex

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        b_is_loop_based = is_loop_domain(context)
        is_face_mode = get_selection_mode(context) == 'FACE'

        def get_border_in_face_mode(obj, bm, cluster: ZenCluster):
            faces = cluster.get_selected_faces(context)
            p_cluster = ZenCluster(context, obj, faces, bm, 0)
            return p_cluster.get_bound_edges()

        clusters_count = 0
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
            islands = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)

            clusters = list()
            for idx, island in enumerate(islands):
                clusters.append(ZenCluster(context, obj, island, bm, idx))
                p_cl: ZenCluster = clusters[-1]

                p_edges = p_cl.get_selected_edges() if not is_face_mode else get_border_in_face_mode(obj, bm, p_cl)
                if not p_edges:
                    clusters.pop(-1)
                    continue
                clusters_count += 1
                z_stripes = UvStripes(p_edges, p_cl.uv_layer).get_stripes_from_selection()
                stripe: Stripe = None
                node: UvVertex = None
                for stripe in z_stripes.stripes:
                    p_bbox = stripe.bounding_box
                    center = p_bbox.center
                    count = len(stripe.nodes)
                    if self.radius_mode == 'AUTO':
                        p_scope = [(node.uv_co - center).length for node in stripe.nodes]
                        radius = sum(p_scope) / len(p_scope)
                    else:
                        radius = self.radius

                    if stripe.get_direction(center) > 0:
                        stripe.reverse()
                    if stripe.is_cycled()['UV']:
                        count = len(stripe.nodes) - 1
                    if self.evenly:
                        vert_x, vert_y = stripe.head_co
                        start_angle = math.atan2(vert_y - center.y, vert_x - center.x)
                        step = 2 * math.pi / count
                        for i in range(count):
                            node = stripe.nodes[i]
                            angle = start_angle + step * i
                            x = center.x + radius * math.cos(angle)
                            y = center.y + radius * math.sin(angle)
                            current_position = Vector(node.uv_co).lerp(Vector((x, y)), self.amount / 100.0)
                            node.set_position(current_position, is_set_linked=True, b_is_loop_based=b_is_loop_based)
                    else:
                        for i in range(count):
                            node = stripe.nodes[i]
                            final_position = center + (node.uv_co - center).normalized() * radius
                            current_position = Vector(node.uv_co).lerp(final_position, self.amount / 100.0)
                            node.set_position(current_position, is_set_linked=True, b_is_loop_based=b_is_loop_based)

            if clusters_count == 0:
                for island in islands:
                    loops = LoopsFactory.get_selected_loops_by_island(context, bm, island, uv_layer)
                    if not loops:
                        continue

                    p_bbox = BoundingBox2d(points=[lp[uv_layer].uv for lp in loops])
                    center = p_bbox.center
                    count = len(loops)
                    if self.radius_mode == 'AUTO':
                        radius = sum((lp[uv_layer].uv - center).length for lp in loops) / count
                    else:
                        radius = self.radius

                    if self.evenly:
                        nodes = GraphProcessor.compound_graph(context, b_is_loop_based, uv_layer, bm, island, skip_unselected=True)
                        if len(nodes) <= 1:
                            continue
                        clusters_count += 1
                        vert_x, vert_y = nodes[0].uv
                        start_angle = math.atan2(vert_y - center.y, vert_x - center.x)
                        step = 2 * math.pi / len(nodes)

                        nodes = GraphProcessor.sort_loops_by_angle(nodes, start_angle)

                        for i, node in enumerate(nodes):
                            angle = start_angle + step * i
                            x = center.x + radius * math.cos(angle)
                            y = center.y + radius * math.sin(angle)
                            position = node.uv.lerp(Vector((x, y)), self.amount / 100.0)
                            GraphProcessor.node_set_position(node, uv_layer, position)

                    else:
                        if len({lp[uv_layer].uv.to_tuple(5) for lp in loops}) == 1:
                            continue
                        clusters_count += 1
                        for loop in loops:
                            p_uv = loop[uv_layer].uv.copy()
                            final_position = center + (p_uv - center).normalized() * radius
                            loop[uv_layer].uv = p_uv.lerp(final_position, self.amount / 100.0)

            bmesh.update_edit_mesh(obj.data)

        if not clusters_count:
            self.report({'WARNING'}, "Zen UV: Select at least two verts per island.")
            return {'CANCELLED'}

        return {'FINISHED'}


class ZUV_OT_RoundUvCoordinates(bpy.types.Operator):
    bl_idname = "uv.zenuv_round_uv_coordinates"
    bl_label = 'Round UV Coordinates'
    bl_description = 'Rounds the value of each UV coordinate to the specified value'
    bl_options = {'REGISTER', 'UNDO'}

    step_x: bpy.props.FloatProperty(
        name="Rounding Step X",
        description="Step to which the value will be rounded along X axis",
        default=0.25,
        min=0.0001
    )

    step_y: bpy.props.FloatProperty(
        name="Rounding Step Y",
        description="Step to which the value will be rounded along Y axis",
        default=0.25,
        min=0.0001,
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        description="Influence axis selection",
        items=[
            ('X', "X", "Axis X"),
            ('Y', "Y", "Axis Y"),
        ],
        options={'ENUM_FLAG'},
        default={'X'}
    )
    step_lock: bpy.props.BoolProperty(
        name="Lock Step Values",
        description="Lock Step Values",
        default=True
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        row = col.row(align=True)
        row.label(text="Axis:")
        row.prop_enum(self, "axis", 'X')
        row.prop_enum(self, "axis", 'Y')

        row = col.row(align=True)
        row.label(text="Step:")
        row.prop(self, "step_x", text='')

        lock_icon = "LOCKED" if self.step_lock else "UNLOCKED"
        row.prop(self, "step_lock", icon=lock_icon, icon_only=True)

        y_row = row.row(align=True)
        y_row.enabled = not self.step_lock
        y_row.prop(self, "step_y", text='')

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        def calc_rounded_coo(step, uv_layer, loop):
            co = loop[uv_layer].uv
            return (
                round(co.x / step.x) * step.x if 'X' in self.axis else co.x,
                round(co.y / step.y) * step.y if 'Y' in self.axis else co.y
            )

        if self.step_lock:
            self.step_y = self.step_x

        step = Vector((self.step_x, self.step_x if self.step_lock else self.step_y))

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
            if is_loop_domain(context):
                looplist = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer)
                for loop in looplist:
                    loop[uv_layer].uv = calc_rounded_coo(step, uv_layer, loop)
            else:
                for vert in (v for v in bm.verts if not v.hide and v.select):
                    for loop in vert.link_loops:
                        loop[uv_layer].uv = calc_rounded_coo(step, uv_layer, loop)

            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


class ZUV_OT_Rectify(bpy.types.Operator):
    bl_idname = "uv.zenuv_rectify"
    bl_label = 'Rectify'
    bl_description = 'Transforms the selected island into a rectangular shape'
    bl_options = {'REGISTER', 'UNDO'}

    reference: bpy.props.EnumProperty(
        name='Reference',
        description='Defines what the transformation is based on',
        items=[
            ("ISLAND", "Island Bounds", "Use island bounds as reference"),
            ("SELECTION", "Selection", "Use user selection as reference"),
        ],
        default="ISLAND"
    )

    orient_to_axis: bpy.props.BoolProperty(
        name='Orient To Axis',
        description='Auto-orient island to nearest axis',
        default=True)

    spacing: bpy.props.EnumProperty(
        name="Spacing",
        description="How to create spaces between points",
        items=[
            ("UV", "UV", ""),
            ("GEOMETRY", "Geometry", ""),
            ("EVENLY", "Evenly", "")
        ],
        default="GEOMETRY")

    is_relax: bpy.props.BoolProperty(name='Relax', description='Enable relaxation of adjacent vertices', default=True)

    relax_mode: bpy.props.EnumProperty(
        name="Relax Method",
        description="Method of Relaxation",
        items=ZenUnwrapProps.UNWRAP_METHOD_ITEMS,
        default="ANGLE_BASED")

    is_pin: bpy.props.BoolProperty(name='Pin', description='Set the pin to the vertices to be processed', default=False)

    select_mode: bpy.props.EnumProperty(
        name="Select Mode",
        description="Select vertices based on their position relative to the bounding box",
        items=[
            ('SKIP', "Skip", "Do not select vertices"),
            ('BORDER', "Border", "Select vertices on the border of the bounding box"),
            ('INSIDE', "Inside", "Select vertices strictly inside the bounding box"),
            ('OUTSIDE', "Outside", "Select vertices outside the bounding box"),
        ],
        default='SKIP'
    )

    amount: bpy.props.FloatProperty(
        name="Amount",
        description="Position along the vector from start to end, in percent (0-100)",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE'
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        layout.prop(self, 'reference')

        layout.prop(self, "orient_to_axis")

        layout.prop(self, "spacing")
        layout.prop(self, "amount")

        box = layout.box()
        box.label(text="Relax Options:")
        box.prop(self, "is_relax")

        sub = box.column(align=True)
        sub.enabled = self.is_relax
        sub.prop(self, "relax_mode")

        box = layout.box()
        box.label(text="Postprocess:")
        box.prop(self, "is_pin")
        box.prop(self, "select_mode")

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        self.image_aspect = ActiveUvImage(context).aspect

        b_is_loop_based = is_loop_domain(context)

        # Collecting data
        scope = dict()
        islands_skipped_counter = 0
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            scope[obj.name] = {'clusters': [], 'paths': [], 'bboxes': []}

            for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=True, b_include_hidden=False):

                graph = GraphProcessor.compound_graph(context, b_is_loop_based, uv_layer, bm, island, collect_neighbours=True, store_selection=True)

                if self.reference == 'SELECTION':
                    processed_nodes = [n for n in graph if n.select]
                    if len(processed_nodes) <= 3:
                        islands_skipped_counter += 1
                        continue
                elif self.reference == 'ISLAND':
                    if len(graph) <= 3:
                        islands_skipped_counter += 1
                        continue
                    processed_nodes = graph

                scope[obj.name]['clusters'].append(graph)

                corner_nodes, main_bbox = self.get_corner_nodes(processed_nodes, self.orient_to_axis)
                scope[obj.name]['bboxes'].append(main_bbox.rect)

                paths = []
                for i in range(len(corner_nodes)):
                    a = corner_nodes[i]
                    b = corner_nodes[(i + 1) % len(corner_nodes)]

                    path = [graph[i] for i in ShortPathUtils.get_shortest_path_uv(graph, a.index, b.index)]

                    paths.append(path)

                if self.spacing == 'UV':
                    uv_spaces = [
                        [(path[i].uv - path[i + 1].uv).length for i in range(len(path) - 1)]
                        for path in paths
                    ]
                else:
                    uv_spaces = []

                for node in corner_nodes:
                    GraphProcessor.node_set_position(node, uv_layer, percent=self.amount)

                # Handle with pin state
                for path in paths:
                    for node in path:
                        node.in_path = True
                        node.pin_states = [lp[uv_layer].pin_uv for lp in node.link_loops]

                for i, path in enumerate(paths):

                    base_vec = path[-1].uv - path[0].uv

                    if self.spacing == 'GEOMETRY':
                        dest_lengths = [e.calc_length() for e in GraphProcessor.iter_edges_from_nodes_path(bm, path)]
                        total_length = sum(dest_lengths)
                        factor = base_vec.length / total_length if total_length != 0 else 1
                    elif self.spacing == 'EVENLY':
                        c_segments = len(path) - 1
                        dest_lengths = [base_vec.length / c_segments] * c_segments
                        factor = 1
                    elif self.spacing == 'UV':
                        dest_lengths = uv_spaces[i]
                        p_total = sum(dest_lengths)
                        factor = base_vec.length / p_total if p_total != 0 else 1

                    else:
                        raise RuntimeError('self.spacing not in {"GEOMETRY", "EVENLY", "UV"}')

                    base_vec.normalize()
                    base_position = path[0].uv
                    for k in range(1, len(path)-1):
                        position = base_position + base_vec * dest_lengths[k-1] * factor
                        position = Vector(path[k].uv).lerp(position, self.amount / 100.0)
                        GraphProcessor.node_set_position(path[k], uv_layer, position)
                        base_position = position.copy()

                    for node in path:
                        for lp in node.link_loops:
                            lp[uv_layer].pin_uv = True

                scope[obj.name]['paths'].append(paths)

            bmesh.update_edit_mesh(obj.data)

        bpy_select_by_context(context, action='DESELECT')

        if self.is_relax:
            for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(scope, context, skip_obj_if_no_uv=True):
                for cluster in scope[obj.name]['clusters']:
                    GraphProcessor.graph_select(context, b_is_loop_based, bm, uv_layer, cluster)

            if bpy.ops.uv.unwrap.poll():
                bpy.ops.uv.unwrap(method=self.relax_mode, margin=0)

        bpy_select_by_context(context, action='DESELECT')

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(scope, context, skip_obj_if_no_uv=True):

            clusters = scope[obj.name]['clusters']
            paths = scope[obj.name]['paths']
            bboxes = scope[obj.name]['bboxes']

            if self.select_mode == 'BORDER' or not self.is_pin:
                for cluster, paths, bbox in zip(clusters, paths, bboxes):
                    for path in paths:
                        GraphProcessor.set_pin_graph(b_is_loop_based, bm, uv_layer, path, self.is_pin)
                        if self.select_mode == 'BORDER':
                            if b_is_loop_based:
                                uv_select_mode = get_selection_mode(context)
                                if uv_select_mode == 'VERT':
                                    p_loops_idxs = {lpi for node in cluster for lpi in node.link_loops_indices}
                                    looplist = GraphProcessor.iter_loops_from_nodes_path_for_vertex(bm, path, p_loops_idxs)
                                    LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)
                                if uv_select_mode == 'EDGE':
                                    p_loops_idxs = {lpi for node in cluster for lpi in node.link_loops_indices}
                                    looplist = GraphProcessor.iter_loops_from_nodes_path_for_edge(bm, path, p_loops_idxs)
                                    LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)
                                elif uv_select_mode == 'FACE':
                                    looplist = []
                                    for edge in GraphProcessor.iter_edges_from_nodes_path(bm, path):
                                        for face in {loop.face for loop in edge.link_loops}:
                                            if all(self.point_inside_of_bbox(bbox, loop[uv_layer].uv, is_inside=True) for loop in face.loops):
                                                looplist.extend(face.loops)
                                    LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)
                            else:
                                mesh_selection_mode = get_selection_mode(context)
                                if mesh_selection_mode == 'VERT':
                                    for path in paths:
                                        for node in path:
                                            bm.verts[node.vert_index].select = True
                                    bm.select_flush_mode()
                                elif mesh_selection_mode == 'EDGE':
                                    for edge in GraphProcessor.iter_edges_from_nodes_path(bm, path):
                                        edge.select = True
                                    bm.select_flush_mode()
                                elif mesh_selection_mode == 'FACE':
                                    for edge in GraphProcessor.iter_edges_from_nodes_path(bm, path):
                                        for face in edge.link_faces:
                                            if all(self.point_inside_of_bbox(bbox, loop[uv_layer].uv, is_inside=True) for loop in face.loops):
                                                face.select = True

                                MeshIslandUtils.update_uv_select_sync(context, bm)

            if self.select_mode == 'SKIP':
                for graph in clusters:
                    GraphProcessor.restore_selection_graph(context, b_is_loop_based, bm, uv_layer, graph)
            elif self.select_mode == 'INSIDE':
                for graph, bbox in zip(clusters, bboxes):
                    self.select_inside_outside_bbox_graph(context, b_is_loop_based, bm, uv_layer, graph, bbox, is_inside=True)
            elif self.select_mode == 'OUTSIDE':
                for graph, bbox in zip(clusters, bboxes):
                    self.select_inside_outside_bbox_graph(context, b_is_loop_based, bm, uv_layer, graph, bbox, is_inside=False)

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if islands_skipped_counter > 0:
            extend = 'Try to select at least four vertices per island.' if self.reference == 'SELECTION' else 'Some of the selected islands could be triangles.'
            self.report({'WARNING'}, f"Some islands remained unprocessed. {extend}")
            return {'FINISHED'}

        return {'FINISHED'}

    def point_inside_of_bbox(self, bbox, point, is_inside):
        safe_zone = 1e-6

        x, y = point
        xmin, ymax, xmax, ymin = bbox

        if is_inside:
            return (xmin - safe_zone <= x <= xmax + safe_zone and
                    ymin - safe_zone <= y <= ymax + safe_zone)
        else:
            return (x <= xmin + safe_zone or x >= xmax - safe_zone or
                    y <= ymin + safe_zone or y >= ymax - safe_zone)

    def select_inside_outside_bbox_graph(self, context, b_is_loop_based: bool, bm, uv_layer, graph, bbox, is_inside: bool = True):
        select_mode = get_selection_mode(context)
        if b_is_loop_based:
            looplist = []
            if select_mode == 'VERT':
                for node in graph:
                    GraphProcessor.node_recollect_loops(bm, node)
                    if self.point_inside_of_bbox(bbox, node.link_loops[0][uv_layer].uv, is_inside):
                        looplist.extend(node.link_loops)
            elif select_mode == 'EDGE':
                for node in graph:
                    GraphProcessor.node_recollect_loops(bm, node)
                    for loop in node.link_loops:
                        if self.point_inside_of_bbox(bbox, loop[uv_layer].uv, is_inside) and self.point_inside_of_bbox(bbox, loop.link_loop_next[uv_layer].uv, is_inside):
                            looplist.append(loop)
            elif select_mode == 'FACE':
                for i in GraphProcessor.get_all_faces_idxs_from_graph(graph):
                    if all(self.point_inside_of_bbox(bbox, loop[uv_layer].uv, is_inside) for loop in bm.faces[i].loops):
                        looplist.extend(bm.faces[i].loops)
            else:  # 'ISLAND' mode
                for i in GraphProcessor.get_all_faces_idxs_from_graph(graph):
                    if all(self.point_inside_of_bbox(bbox, loop[uv_layer].uv, is_inside) for loop in bm.faces[i].loops):
                        looplist.extend(bm.faces[i].loops)
            LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)
        else:
            if select_mode == 'VERT':
                for node in graph:
                    GraphProcessor.node_recollect_loops(bm, node)
                    if self.point_inside_of_bbox(bbox, node.link_loops[0][uv_layer].uv, is_inside):
                        bm.verts[node.vert_index].select = True
                bm.select_flush_mode()
            elif select_mode == 'EDGE':
                for node in graph:
                    GraphProcessor.node_recollect_loops(bm, node)
                    for loop in node.link_loops:
                        if self.point_inside_of_bbox(bbox, loop[uv_layer].uv, is_inside) and self.point_inside_of_bbox(bbox, loop.link_loop_next[uv_layer].uv, is_inside):
                            loop.edge.select = True
                bm.select_flush_mode()
            elif select_mode == 'FACE':
                for i in GraphProcessor.get_all_faces_idxs_from_graph(graph):
                    if all(self.point_inside_of_bbox(bbox, loop[uv_layer].uv, is_inside) for loop in bm.faces[i].loops):
                        bm.faces[i].select = True

            MeshIslandUtils.update_uv_select_sync(context, bm)

    def get_corner_nodes(self, test_nodes, auto_orient: bool = False):

        def match_corners_global(test_nodes, oriented_corners, K=4):
            cand_per_corner = []
            for c in oriented_corners:
                ranked = sorted((((n.uv - c).length, n) for n in test_nodes), key=lambda x: x[0])
                cand_per_corner.append([n for _, n in ranked[:min(K, len(ranked))]])

            best = None  # (cost, combo_nodes)
            for combo in product(*cand_per_corner):
                idxs = {n.index for n in combo}
                if len(idxs) != 4:
                    continue
                cost = sum((combo[i].uv - oriented_corners[i]).length for i in range(4))
                if best is None or cost < best[0]:
                    best = (cost, combo)

            if best is None:
                raise RuntimeError("Failed to find a unique match for the 4 corners.")

            corner_nodes = list(best[1])

            for i, n in enumerate(corner_nodes):
                n.bbox_corner_position = p_bbox.corners[i].copy() if auto_orient else oriented_corners[i].copy()

            return corner_nodes

        test_bbox = BoundingBox2d(points=[n.uv for n in test_nodes])
        angle = test_bbox.get_orient_angle(self.image_aspect)

        p_cluster_uvs = [n.uv for n in test_nodes]
        p_cluster_uvs = TransformUVS.rotate_uvs(p_cluster_uvs, angle, test_bbox.center, self.image_aspect)
        p_bbox = BoundingBox2d(points=p_cluster_uvs)
        oriented_corners = TransformUVS.rotate_uvs(p_bbox.corners[:4], -angle, test_bbox.center, self.image_aspect)

        if self.reference == 'ISLAND':
            p_nodes = [n for n in test_nodes if len(n.link_loops) == 1]
            if len(p_nodes) == 4:
                test_nodes = p_nodes

        return match_corners_global(test_nodes, oriented_corners), p_bbox


classes = [
    ZUV_OT_SelectionToCircle,
    ZUV_OT_RoundUvCoordinates,
    ZUV_OT_Rectify
]


def register_misc_transform_tools():
    RegisterUtils.register(classes)


def unregister_misc_transform_tools():
    RegisterUtils.unregister(classes)


if __name__ == '__main__':
    pass
