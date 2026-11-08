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
import bmesh
import time
import math
from mathutils import Vector
from dataclasses import asdict
from ...ops.select_sys.select_utils import SmartLoopProps

from ...ops.zen_unwrap.props import ZenUnwrapProps

from ...utils.generic import ResortObjects

from ...ui.pie import ZsPieFactory

from ...utils.generic import switch_to_edge_sel_mode

# NOTE: TD Section
from ...ops.texel_density.td_alternative import register as register_weighted_td
from ...ops.texel_density.td_alternative import unregister as unregister_weighted_td

from ...ops.select_sys.select_utils import MeshAnalyse
from ...utils.iter_utils import IterUtils
from ...utils.uvedit_select import uvedit_get_bm_selected_loops

from ...utils.vlog import Log
from ...utils.blender_zen_utils import ZenPolls, is_sync_off, is_loop_domain, get_selection_mode

from ...utils.uv_factory import UvIslandUtils, SelectionUtils


class ZUV_OT_TestUnwrapConstraint(bpy.types.Operator):
    bl_idname = "uv.zenuv_test_unwrap_constraint"
    bl_label = "Unwrap Constraint"
    bl_description = ('')
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name='Axis',
        description='Active Axis',
        items=[
            ('U', 'U', 'Axis U'),
            ('V', 'V', 'Axis V'),
            ('UV', 'UV', 'Axis U and V'),
        ],
        default='UV')

    amount: bpy.props.FloatProperty(
        name="Amount",
        description="Position along the vector from start to end, in percent (0-100)",
        default=100.0,
        min=0.0,
        max=100.0,
        subtype='PERCENTAGE')

    relax_mode: bpy.props.EnumProperty(
        name="Relax Method",
        description="Method of Relaxation",
        items=ZenUnwrapProps.UNWRAP_METHOD_ITEMS,
        default="ANGLE_BASED")

    ignore_pins: bpy.props.BoolProperty(
        name='Ignore Pins',
        description='Ignore Pins',
        default=False)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context: bpy.types.Context):
        from ...utils.selection_utils import SelectionProcessor, UniSelectedObject
        from collections import defaultdict

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context, require_active_uv=True)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        Storage = defaultdict(dict)
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=False):
            Storage[obj]['user_pins'] = list()
            Storage[obj]['operator_pins'] = list()
            Storage[obj]['uvs'] = list()

            islands = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
            Storage[obj]['islands'] = [[f.index for f in island] for island in islands]
            for island in islands:
                for face in island:
                    for loop in face.loops:
                        Storage[obj]['user_pins'].append(loop[uv_layer].pin_uv)
                        p_state = not loop.uv_select_vert
                        loop[uv_layer].pin_uv = p_state
                        Storage[obj]['operator_pins'].append(p_state)
                        Storage[obj]['uvs'].append(loop[uv_layer].uv.copy())

        if bpy.ops.uv.unwrap.poll():
            bpy.ops.uv.unwrap(
                method=self.relax_mode,
                # fill_holes=self.fill_holes,
                # correct_aspect=self.correct_aspect,
                # ue_subsurf_data=self.use_subsurf_data,
                margin=0
            )

        t = self.amount / 100

        def lerp_u(uv, old):
            uv.x = old.x + (uv.x - old.x) * t
            uv.y = old.y

        def lerp_v(uv, old):
            uv.y = old.y + (uv.y - old.y) * t
            uv.x = old.x

        def lerp_uv(uv, old):
            uv.xy = old.lerp(uv, t)

        lerp_func = {
            "U": lerp_u,
            "V": lerp_v,
            "UV": lerp_uv,
        }[self.axis]

        for obj, data in Storage.items():
            for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv([obj], context, skip_obj_if_no_uv=False):
                islands = [[bm.faces[i] for i in group] for group in data['islands']]
                index = 0
                for island in islands:
                    for face in island:
                        for loop in face.loops:
                            uv = loop[uv_layer].uv
                            old = data['uvs'][index]

                            loop[uv_layer].pin_uv = data['user_pins'][index]
                            lerp_func(uv, old)

                            index += 1

        return {'FINISHED'}


class ZUV_OT_TestUVSyncSelect(bpy.types.Operator):
    bl_idname = "uv.zenuv_test_sync_select"
    bl_label = "Clear Selection"
    bl_description = (
        'Keep UV and edit mode mesh selection in sync,\n'
        'showing all islands of unhided mesh elements.\n'
        '* Edges and Faces - only supported!')
    bl_options = {'REGISTER', 'UNDO'}

    sync_selection_mode: bpy.props.BoolProperty(
        name='Sync Selection Mode',
        description='Keep selection mode in sync between UV Sync Selection states',
        default=True
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context: bpy.types.Context):
        from ...utils.blender_zen_utils import get_selection_mode, _internal_get_uv_select_mode, _internal_get_mesh_select_mode
        from ...utils.loops_factory import LoopsFactory
        from ...utils.iter_utils import IterUtils

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        b_is_loop_domain = is_loop_domain(context)

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
            if is_loop_domain(context):
                looplist = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer)
                print(f'{len(looplist) = }')
            else:
                for f in bm.faces:
                    f.select = False
                for v in bm.verts:
                    v.select = False
                sel_verts = [v.index for v in bm.verts if v.select]

                print(f'{len(sel_verts) = }')
                looplist = LoopsFactory.collect_loops_in_uv_editor(context, bm, bm.faces, False, False)
                print(f'{len(looplist) = }')
            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


class ZUV_OT_TestContext(bpy.types.Operator):
    bl_idname = "uv.zenuv_test_vert_select"
    bl_label = 'Test Vert Select'
    bl_description = bl_label
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None \
            and active_object.type == 'MESH' \
            and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ...utils.loops_factory import LoopsFactory
        from ...utils.generic import bpy_select_by_context
        print('\n########################## Start ###################################')

        if context.space_data.type == 'VIEW_3D':
            if not context.space_data.overlay.show_stats:
                context.space_data.overlay.show_stats = True

        ZsPieFactory.mark_pie_cancelled()

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        bpy_select_by_context(context, action='DESELECT')

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            # selection = [v.index for v in bm.verts if v.select]
            # print(selection)
            # idxs = [136, 151, 166, 181, 196, 211, 226, 241, 256, 271, 286, 301, 316, 331, 346, 361, 376]
            idxs = [136, 137, 151, 152, 166, 167, 181, 182, 196, 197, 211, 212, 226, 227, 241, 242, 254, 255, 256, 257, 258, 269, 270, 271, 272, 273, 286, 287, 301, 302, 316, 317, 331, 332, 346, 347, 361, 362, 376, 377]
            vertlist = [bm.verts[i] for i in idxs]

            SelectionUtils.select_verts_any_context_b5(context, bm, vertlist, True)

            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


class ZUV_OT_SmartSelectEdges(bpy.types.Operator):
    bl_idname = "uv.zenuv_smart_select_edges"
    bl_label = 'Smart Select Edges'
    bl_description = 'Smart select edges'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    angle_tolerance: bpy.props.FloatProperty(
        name="Angle Tolerance",
        description="Allowed angle between adjacent faces",
        default=math.radians(35),
        max=math.pi,
        subtype='ANGLE')  # RADIANS

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None \
            and active_object.type == 'MESH' \
            and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ...utils.generic import bpy_select_by_context

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if self.clear_selection:
            bpy_select_by_context(context, action='DESELECT')

        for obj, bm, _ in IterUtils.iter_objs_with_bmesh_uv(objs, context):

            # b_is_loop_domain = is_loop_domain(context)

            # for lp in MeshAnalyse.walk_edgeloop_along(
            #         bm,
            #         [lp for edge in bm.edges for lp in edge.link_loops if edge.select],
            #         b_is_loop_domain):

            #     lp.edge.select = True

            # Select Caps in cylinders
            verts = [v.index for v in bm.verts if not v.hide and len(v.link_faces) >= 5]
            if verts:
                for i in verts:
                    v = bm.verts[i]
                    if MeshAnalyse.faces_same_area(v.link_faces):
                        for f in v.link_faces:
                            for e in f.edges:
                                if e.calc_face_angle() <= math.radians(25):
                                    continue
                                if v not in e.verts:
                                    e.select = True
            # Holed Cap
            tolerance = 0.1

            def almost_equal(a, b, tol):
                longer = max(a, b)
                shorter = min(a, b)
                return longer <= shorter * (1 + tol)

            pairs = ((0, 2), (1, 3))
            # faces = [f for f in bm.faces if not f.hide and len(f.edges) == 4 and len({round(e.calc_length(), 6) for e in f.edges}) == 3]
            # Any pair equal ================================
            faces = [
                f.index for f in bm.faces
                if not f.hide
                and len(f.edges) == 4
                and any(
                    almost_equal(
                        (f.edges[i].verts[0].co - f.edges[i].verts[1].co).length,
                        (f.edges[k].verts[0].co - f.edges[k].verts[1].co).length,
                        tolerance
                    )
                    for i, k in pairs
                )
            ]
            print(f'{len(faces) = }')
            # Any equal END ============================

            # Only one pair equal ============================
            # faces = [
            #     f.index for f in bm.faces
            #     if not f.hide
            #     and len(f.edges) == 4
            #     and sum(
            #         almost_equal(
            #             (f.edges[i].verts[0].co - f.edges[i].verts[1].co).length,
            #             (f.edges[k].verts[0].co - f.edges[k].verts[1].co).length,
            #             tolerance
            #         )
            #         for i, k in pairs
            #     ) == 1
            # ]
            # print([f.index for f in faces])
            # Only one pair equal END ============================

            for i in faces:
                bm.faces[i].select = True

            if faces:
                for i in faces:
                    for e in bm.faces[i].edges:
                        if e.calc_face_angle(0) <= self.angle_tolerance:
                            continue
                        e.select = True

            bm.select_flush_mode()

            bmesh.update_edit_mesh(obj.data, loop_triangles=False)
            switch_to_edge_sel_mode(context)

        return {'FINISHED'}


class ZUV_OT_Test_Select_Loops(bpy.types.Operator):
    bl_idname = "uv.zenuv_test_select_loops"
    bl_label = 'Test_Select Loops'
    bl_zen_short_name = 'Loops'
    bl_description = 'Select Loops by selected edge/face of the Islands'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ...utils.loops_factory import LoopsFactory
        from ...utils.generic import bpy_select_by_context
        print('\n########################## Start ###################################')

        if context.space_data.type == 'VIEW_3D':
            if not context.space_data.overlay.show_stats:
                context.space_data.overlay.show_stats = True

        ZsPieFactory.mark_pie_cancelled()

        objs = ResortObjects.resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            sel_mode = get_selection_mode(context)

            # Collect loops
            loops = LoopsFactory._internal_get_loops_by_sel_mode(context, bm, bm.faces, uv_layer, only_uv_edges=sel_mode == 'EDGE', per_face=False)

            print('--------------------------------------------------------------\n')
            print(f'{len(loops) = }')

            # Deselect
            bpy_select_by_context(context, action='DESELECT')

            # Select loops
            LoopsFactory.select_loops(context, bm, loops, uv_layer)

            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


class ZUV_OT_Test_Select_Island(bpy.types.Operator):
    bl_idname = "uv.zenuv_test_select_island"
    bl_label = 'Test_Select Islands'
    bl_zen_short_name = 'Islands'
    bl_description = 'Select Islands by selected edge/face of the Islands'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        print('\n########################## Start ###################################')

        ZsPieFactory.mark_pie_cancelled()

        objs = ResortObjects.resort_objects_by_selection(context, context.objects_in_mode)
        print(objs)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        b_is_loop_domain = b_is_loop_domain(context)

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=False):

            if b_is_loop_domain and not uv_layer:
                continue

            print(f'Editor type: {context.space_data.type}')

            # Collect selection in 3D VIEW
            if context.space_data.type == 'VIEW_3D':
                mesh_selection_mode = context.tool_settings.mesh_select_mode
                if mesh_selection_mode[2]:
                    selection = [f for f in bm.faces if f.select and not f.hide]
                else:
                    selection = [f for f in bm.faces if any(v.select for v in f.verts) and not f.hide]

            # Collect selection in UV EDITOR
            elif context.space_data.type == 'IMAGE_EDITOR':
                print(f'Sticky Selection Mode: {context.tool_settings.uv_sticky_select_mode}')
                print(f'UV Sync Mode: {not is_sync_off(context)}')

                if is_sync_off(context):
                    uv_selection_mode = context.scene.tool_settings.uv_select_mode
                    if uv_selection_mode == 'FACE':
                        selection = [f for f in bm.faces if f.select and f.uv_select and not f.hide]
                    else:
                        selection = [f for f in bm.faces if f.select and not f.hide and any([loop.uv_select_vert for loop in f.loops])]

                else:
                    if not bm.uv_select_sync_valid:
                        bm.uv_select_sync_from_mesh()

                    selection = [f for f in bm.faces if f.uv_select or any(lp.uv_select_vert for lp in f.loops)]

            else:
                return {'FINISHED'}

            print('\n--------------------------------------------------------------------------------------')
            print(f'Total: {len(selection)}, Selection faces: {[f.index for f in selection]}')
            print('--------------------------------------------------------------------------------------\n')

            islands = UvIslandUtils.get_uv_islands(context, bm, uv_layer, b_selected_only=True)

            print(f'{len(islands) = }')

            if not islands:
                continue

            if context.space_data.type == 'VIEW_3D':

                for island in islands:
                    for f in island:
                        f.select = True
                bm.uv_select_sync_from_mesh(sticky_select_mode=context.tool_settings.uv_sticky_select_mode)

            elif context.space_data.type == 'IMAGE_EDITOR':

                if b_is_loop_domain:
                    for island in islands:
                        for f in island:
                            f.uv_select = True
                            for lp in f.loops:
                                lp.uv_select_vert = True
                else:
                    bm.uv_select_sync_valid = True

                    bm.uv_select_foreach_set_from_mesh(
                        True,
                        faces=[f for island in islands for f in island],
                        sticky_select_mode=context.tool_settings.uv_sticky_select_mode)

                    bm.uv_select_sync_to_mesh()
            else:
                return {'FINISHED'}

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_SmartSelectLoop(bpy.types.Operator):
    bl_idname = "uv.zenuv_smart_select_loop"
    bl_label = 'Smart Select Loop'
    bl_description = (
        "Selects an edge loop starting from a given edge with customizable stopping rules. "
        "Stops can be triggered by seams, selected edges, self-intersections, simple or complex vertices. "
        "Optionally filters for closed loops only."
    )
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        name="Direction",
        description="Traversal direction of the edge loop",
        items=[
            ('CW', "CW", "Clockwise direction"),
            ('CCW', "CCW", "Counterclockwise direction"),
        ],
        default='CW')

    stop_on_self_intersect: bpy.props.BoolProperty(
        name="Stop on Self Intersect",
        description=("Stop the edge loop if it begins to intersect with itself"),
        default=True)
    stop_on_selected: bpy.props.BoolProperty(
        name="Stop on Selected",
        description=("Stop the edge loop if a selected edge is reached"),
        default=True)
    stop_on_seam: bpy.props.BoolProperty(
        name="Stop on Seam",
        description=("Stop the edge loop when a seam edge is reached"),
        default=True)
    stop_on_sharp: bpy.props.BoolProperty(
        name="Stop on Sharp",
        description=("Stop the edge loop when a sharp-marked edge is reached"),
        default=True)
    stop_on_simple_vertex: bpy.props.BoolProperty(
        name="Stop on Simple Vertex",
        description=("Stop the edge loop when a vertex with 3 connected edges is reached"),
        default=True)
    simple_detect_obtuse_angle: bpy.props.BoolProperty(
        name="Detect Obtuse Angle",
        description=("Stop the edge loop when an obtuse angle is detected at a vertex"),
        default=True)
    stop_on_complex_vertex: bpy.props.BoolProperty(
        name="Stop on Complex Vertex",
        description=("Stop the edge loop when a vertex with more than 4 connected edges is reached"),
        default=False)
    complex_dir_sharp_balance: bpy.props.FloatProperty(
        name="Direction Sharpness Balance",
        description="Weight factor balancing direction vs. sharpness when evaluating complex vertices (0 = direction only, 1 = sharpness only",
        default=0.35,
        min=0.0,
        max=1,
        subtype='FACTOR')
    use_edge_sharpness_limit: bpy.props.BoolProperty(
        name="Use Edge Sharpness Limit",
        description="Enable filtering edges based on angle using the Edge Sharpness Limit",
        default=False)
    edge_sharpness_mode: bpy.props.EnumProperty(
        name="Edge Sharpness Mode",
        description="Select edges with angle below or above the threshold value",
        items=[
            ('BELOW', "Below", "Select edges with angle smaller (sharper) than the threshold"),
            ('ABOVE', "Above", "Select edges with angle larger (smoother) than the threshold"),
            ('AUTO', "Auto", "Choose sharper or smoother edges automatically, using the first selected edge as reference.")
        ],
        default='AUTO')
    edge_sharpness_limit: bpy.props.FloatProperty(
        name="Edge Sharpness Limit",
        description="Maximum edge angle (sharpness) to include an edge in the loop (smoother will be ignored)",
        default=0.5235988,
        min=0.0,
        max=math.pi,
        subtype='ANGLE')  # Radians

    use_edge_angle_limit: bpy.props.BoolProperty(
        name="Use Edge Angle Limit",
        description="Enable filtering edges based on angle between current and next edge in loop",
        default=False)
    edge_angle_limit: bpy.props.FloatProperty(
        name="Edge Angle Limit",
        description="Minimum angle between edges to include an edge in the loop (sharper angles are ignored)",
        default=0.61086524,
        min=0.0,
        max=math.pi,
        subtype='ANGLE')  # Radians

    filter_closed_loops: bpy.props.BoolProperty(
        name="Filter Closed Loops",
        description="Only select edge loops that form a closed ring",
        default=False)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.prop(self, 'stop_on_self_intersect')
        box.prop(self, 'stop_on_seam')
        box.prop(self, 'stop_on_sharp')
        box.prop(self, 'stop_on_selected')

        box = layout.box()
        box.prop(self, 'stop_on_simple_vertex')
        col = box.column()
        col.use_property_split = True
        col.enabled = not self.stop_on_simple_vertex
        col.prop(self, 'simple_detect_obtuse_angle')

        box = layout.box()
        box.prop(self, 'stop_on_complex_vertex')
        col = box.column()
        col.enabled = not self.stop_on_complex_vertex
        row = col.row(align=True)
        split = row.split(factor=0.15)
        split.label(text='Sharp')
        sub = split.split(factor=0.8)
        sub.prop(self, 'complex_dir_sharp_balance', text='')
        sub.label(text='Direct')
        # col = box.column()
        # col.use_property_split = True
        # col.prop(self, 'use_edge_sharpness_limit')
        # col = box.column()
        # col.use_property_split = True
        # col.enabled = self.use_edge_sharpness_limit
        # col.prop(self, 'edge_sharpness_limit')

        box = layout.box()
        box.prop(self, 'use_edge_angle_limit')
        row = box.row()
        row.use_property_split = True
        row.enabled = self.use_edge_angle_limit
        row.prop(self, 'edge_angle_limit', text='Angle Limit')

        box = layout.box()
        box.prop(self, 'use_edge_sharpness_limit')
        row = box.row()
        row.use_property_split = True
        row.prop(self, 'edge_sharpness_mode')
        row = box.row()
        row.use_property_split = True
        row.enabled = self.use_edge_sharpness_limit
        row.prop(self, 'edge_sharpness_limit', text='Sharpness Limit')

        box = layout.box()
        box.label(text='Postporocess:')
        row = box.row()
        row.use_property_split = True
        row.prop(self, 'filter_closed_loops')

        box = layout.box()
        box.label(text='Direction:')
        row = box.row(align=True)
        row.prop(self, 'direction', expand=True)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None \
            and active_object.type == 'MESH' \
            and context.mode == 'EDIT_MESH'

    def extract_properties(self, props_cls):
        """Extract operator properties into a dataclass container"""
        props_instance = props_cls()
        prop_class_dict = asdict(props_instance)

        for prp in prop_class_dict:
            attr = getattr(self.properties, prp, None)
            if attr is None:
                # Log.debug('From class ZuvUnwrapTemplate: ',
                #           f'Property "{prp}" not present in the {self.bl_idname} Class')
                continue
            setattr(props_instance, prp, attr)

        return props_instance

    def execute(self, context):
        print('=================================\n')
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        is_show_seams = context.space_data.overlay.show_edge_seams
        is_show_sharp = context.space_data.overlay.show_edge_sharp
        overlay_warn = ''
        if self.stop_on_seam and is_show_seams is False:
            overlay_warn = 'Seam'
        if self.stop_on_sharp and is_show_sharp is False:
            overlay_warn += ' and Sharp' if overlay_warn else 'Sharp'
        if overlay_warn:
            self.report({"WARNING"}, f"{overlay_warn} display is turned off. Enable it to see where the edge loop stops.")

        props_cls = self.extract_properties(SmartLoopProps)

        closed_loops_counter = 0
        for obj, bm, _ in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            loops = [lp for edge in bm.edges for lp in edge.link_loops if edge.select]
            p_loops = MeshAnalyse.walk_edgeloop_along(
                    props_cls, bm,
                    loops if self.direction == 'CW' else list(reversed(loops)),
                    max_steps=len(bm.edges))

            if self.filter_closed_loops:
                closed_loops = MeshAnalyse.find_closed_edge_loops(bm, [lp.edge.index for lp in p_loops])
                if not closed_loops:
                    continue

                closed_loops_counter += len(closed_loops)
                for group in closed_loops:
                    for i in group:
                        bm.edges[i].select = True
            else:
                for lp in p_loops:
                    lp.edge.select = True

            bm.select_flush_mode()

            bmesh.update_edit_mesh(obj.data, loop_triangles=False)
            switch_to_edge_sel_mode(context)

        if self.filter_closed_loops and closed_loops_counter == 0:
            self.report({'INFO'}, "No closed edge loops found.")

        return {'FINISHED'}


class ZUV_OP_TestOperator(bpy.types.Operator):
    bl_idname = 'zenuv_test.test_operator'
    bl_label = 'Select Bevel Seam'
    bl_description = 'Selects edges that were created after chamfering'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    selection_mode: bpy.props.EnumProperty(
        name="Selection Mode",
        description="Defines whether the operator selects individual edges or entire edge loops",
        items=[
            ('SEL_EDGE', "Edges", "Select individual edges"),
            ('SEL_EDGE_LOOP', "Edge Loops", "Select entire edge loops"),
        ],
        default='SEL_EDGE'
    )

    preselect_type: bpy.props.EnumProperty(
        name="Preselect",
        description="Preselection of vertices by number of connected edges",
        items=[
            ('3', "3 Edges", "Preselect vertices that have 3 edges"),
            ('4', "4 Edges", "Preselect vertices that have 4 edges"),
            ('6', "6 Edges", "Preselect vertices that have 6 edges"),
        ],
        default={'3', '6'},
        options={'ENUM_FLAG'})

    angle_detection: bpy.props.EnumProperty(
        name="Angle Detection",
        description="Method for calculating edge sharpness",
        items=[
            (
                'ONE_BY_ONE',
                "One by One",
                "Compare each edge angle with the Threshold. "
                "Best for low-poly meshes with bevels."
            ),
            (
                'EDGE_LOOP',
                "Edge Loop",
                "Compare the average loop angle with the Threshold. "
                "Best for high-poly meshes with smoothing."
            ),
        ],
        default='ONE_BY_ONE'
    )

    threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Angle threshold in degrees. All edges sharper than this angle will be selected",
        default=math.radians(30.0),
        min=0.0,
        max=math.pi,
        subtype='ANGLE')

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        row = col.row()
        row.use_property_split = True
        row.prop(self, 'clear_selection')

        row = col.row(align=True)
        row.label(text='Preselect:')
        row.prop_enum(self, 'preselect_type', '3')
        row.prop_enum(self, 'preselect_type', '4')
        row.prop_enum(self, 'preselect_type', '6')

        row = col.row()
        row.use_property_split = True
        row.prop(self, 'selection_mode')

        box = layout.box()
        box.label(text='Angles detection:')
        box.prop(self, 'angle_detection', text='')
        box.prop(self, 'threshold')

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        import math
        from ...utils.iter_utils import IterUtils
        from ...utils.generic import switch_to_edge_sel_mode
        from ...utils.generic import bpy_select_by_context

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if not self.preselect_type:
            self.report({'WARNING'}, 'There are no pre-selection criteria')
            return {'FINISHED'}

        b_is_loop_domain = is_loop_domain(context)

        count_values = {int(i) for i in self.preselect_type if i.isdigit()}

        if self.clear_selection:
            bpy_select_by_context(context, action='DESELECT')

        def select_loop(loop, uv_layer):
            loop[uv_layer].select = True
            loop[uv_layer].select_edge = True

        def select_edge(loop):
            loop.edge.select = True

        # def check_vertex_uniform(v, tolerance_deg=15.0):
        #     vecs = []
        #     for e in v.link_edges:
        #         other = e.other_vert(v)
        #         vecs.append((other.co - v.co).normalized())

        #     n = len(vecs)
        #     if n < 2:
        #         return False

        #     normal = Vector((0, 0, 0))
        #     for f in v.link_faces:
        #         normal += f.normal
        #     if normal.length < 1e-6:
        #         return False
        #     normal.normalize()

        #     ref = vecs[0]
        #     tangent = ref.cross(normal)
        #     if tangent.length < 1e-6:
        #         tangent = normal.orthogonal()
        #     tangent.normalize()
        #     bitangent = normal.cross(tangent)

        #     angles2d = []
        #     for vec in vecs:
        #         x = vec.dot(tangent)
        #         y = vec.dot(bitangent)
        #         ang = math.degrees(math.atan2(y, x))
        #         angles2d.append(ang)

        #     angles2d.sort()

        #     angles2d.append(angles2d[0] + 360)

        #     diffs = [angles2d[i+1] - angles2d[i] for i in range(n)]
        #     avg = sum(diffs) / len(diffs)
        #     return all(abs(d - avg) <= tolerance_deg for d in diffs)

        # def is_averaged_edge_lengths_for_around(vertex, tolerance_perc=20):
        #     p_edges_length = []
        #     for loop in vertex.link_loops:
        #         lp1 = loop.link_loop_next
        #         lp2 = lp1.link_loop_next
        #         p_edges_length.extend((lp1.edge.calc_length(), lp2.edge.calc_length()))
        #     print(p_edges_length)

        #     if not p_edges_length:
        #         return False
        #     avg = sum(p_edges_length) / len(p_edges_length)
        #     tolerance_len = avg / 100 * tolerance_perc
        #     # print(f'{tolerance_len = }')
        #     print([abs(ln - avg) for ln in p_edges_length])
        #     return all(abs(ln - avg) <= tolerance_len for ln in p_edges_length)

        def is_averaged_edge_lengths(vertex, tolerance_perc=20):
            p_edges_length = [edge.calc_length() for edge in vertex.link_edges]
            if not p_edges_length:
                return False
            avg = sum(p_edges_length) / len(p_edges_length)
            tolerance_len = avg / 100 * tolerance_perc
            return all(abs(ln - avg) <= tolerance_len for ln in p_edges_length)

        def is_vert_sharp_by_faces(vertex, tolerance_deg=30):
            tolerance_rad = math.radians(tolerance_deg)
            v_linked_normals = [f.normal for f in vertex.link_faces]
            avg_normal = sum(v_linked_normals, Vector())
            if avg_normal.length < 1e-6:
                return False
            avg_normal.normalize()
            return any(abs(avg_normal.angle(nrm) > tolerance_rad) for nrm in v_linked_normals)

        def has_equal_edge_lengths(vertex, tol=1e-5) -> bool:
            p_edges = vertex.link_edges
            n = len(p_edges)

            for i in range(n):
                l1 = p_edges[i].calc_length()
                for j in range(i + 1, n):
                    if abs(l1 - p_edges[j].calc_length()) < tol:
                        return True
            return False

        def find_equal_edge_lengths(vertex, tol=1e-5):
            p_edges = vertex.link_edges
            groups = []
            used = set()

            for i, e1 in enumerate(p_edges):
                if e1 in used:
                    continue
                group = [e1]
                l1 = e1.calc_length()
                for e2 in p_edges[i+1:]:
                    if e2 in used:
                        continue
                    l2 = e2.calc_length()
                    if abs(l1 - l2) < tol:
                        group.append(e2)
                        used.add(e2)
                if len(group) > 1:
                    groups.append(group)
                    used.update(group)

            return len(groups) > 0, groups

        def check_vertex_bevelled(vertex):
            if not all(len(f.verts) == 4 for f in vertex.link_faces):
                return False

            if not is_vert_sharp_by_faces(vertex, tolerance_deg=25):
                return False

            if len(vertex.link_faces) == 4:
                return has_equal_edge_lengths(vertex)

            if not is_averaged_edge_lengths(vertex, tolerance_perc=20):
                return False

            return True

        # def is_quad_almost_rectangle(face, angle_tol=10.0, aspect_tol=0.2) -> bool:
        #     if len(face.verts) != 4:
        #         return False

        #     verts = [v.co for v in face.verts]

        #     for i in range(4):
        #         v_prev = verts[i - 1]
        #         v_cur = verts[i]
        #         v_next = verts[(i + 1) % 4]

        #         vec1 = (v_prev - v_cur).normalized()
        #         vec2 = (v_next - v_cur).normalized()
        #         angle = math.degrees(vec1.angle(vec2))

        #         if abs(90 - angle) > angle_tol:
        #             return False

        #     edges = [(verts[i] - verts[(i + 1) % 4]).length for i in range(4)]

        #     if abs(edges[0] - edges[2]) / max(edges[0], edges[2]) > aspect_tol:
        #         return False
        #     if abs(edges[1] - edges[3]) / max(edges[1], edges[3]) > aspect_tol:
        #         return False

        #     return True

        def is_edge_counter(vertex, count_values: set):
            return len(vertex.link_faces) in count_values

        def collect_loops(bm, p_verts, b_is_loop_domain, threshold=math.pi / 4):
            p_loops = set()
            check_select = b_is_loop_domain

            for i in p_verts:
                vert = bm.verts[i]

                if len(vert.link_faces) == 4 or len(vert.link_faces) == 6:
                    res, groups = find_equal_edge_lengths(vert)
                    if res:
                        for group in groups:
                            for e in group:
                                if abs(e.calc_face_angle(0)) > threshold:
                                    p_loops.update(e.link_loops)
                else:
                    for e in vert.link_edges:
                        for lp in e.link_loops:
                            if lp.face.hide:
                                continue
                            if check_select and not lp.face.select:
                                continue
                            p_loops.add(lp)

            return p_loops

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
            obj_max_steps = len(bm.edges)
            print(f'{obj_max_steps = }')

            p_verts = [v.index for v in bm.verts if not v.hide and is_edge_counter(v, count_values) and check_vertex_bevelled(v)]

            print(f'{len(p_verts) = }')

            if not p_verts:
                print('No verts collected')
                continue

            p_loops = collect_loops(bm, p_verts, b_is_loop_domain)

            stored_edges = {lp.edge.index for lp in p_loops}

            visited_edges = []

            start_time = time.time()
            for loop in p_loops:
                cycles_counter = 0
                loops_in_cycle = []
                loop.edge.select = True
                if self.selection_mode == 'SEL_EDGE_LOOP':
                    for lp in MeshAnalyse.walk_edgeloop_along(bm, [loop], max_steps=obj_max_steps):
                        if lp.edge.index in visited_edges:
                            continue
                        if lp.edge.hide:
                            continue
                        if self.angle_detection == 'ONE_BY_ONE':
                            if lp.edge.calc_face_angle(0) >= self.threshold:
                                if b_is_loop_domain:
                                    select_loop(lp, uv_layer)
                                else:
                                    select_edge(lp)
                        else:
                            loops_in_cycle.append([lp, lp.edge.calc_face_angle(0)])

                        if lp.edge.index in stored_edges:
                            visited_edges.append(lp.edge.index)
                        cycles_counter += 1

                    if self.angle_detection == 'EDGE_LOOP':
                        if loops_in_cycle:
                            sum_angle = sum(s for _, s in loops_in_cycle) / len(loops_in_cycle)
                            if sum_angle >= self.threshold:
                                for p_lp, _ in loops_in_cycle:
                                    if b_is_loop_domain:
                                        select_loop(p_lp, uv_layer)
                                    else:
                                        select_edge(p_lp)
            Log.debug('time', f"Total processing time: {time.time() - start_time:.5f} seconds\n")
            bm.select_flush_mode()

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        switch_to_edge_sel_mode(context)

        return {'FINISHED'}


class OBJECT_OT_ComparePerformanceComprehension(bpy.types.Operator):
    """Compare performance of three methods for filtering faces in BMesh"""
    bl_idname = "object.compare_performance"
    bl_label = "Compare Performance"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print('-----------------------------------------------')
        obj = context.object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Active object must be a mesh")
            return {'CANCELLED'}

        bm = bmesh.from_edit_mesh(obj.data)

        uv_layer = bm.loops.layers.uv.verify()

        # Variant 1
        start_time = time.time()
        p_selected_faces_v1 = set()
        for f in bm.faces:
            if f.select and not f.hide:
                for loop in f.loops:
                    if loop[uv_layer].select:
                        p_selected_faces_v1.add(f)
                        break
        time_v1 = time.time() - start_time

        # Variant 2
        start_time = time.time()
        p_selected_faces_v2 = {f for f in bm.faces if f.select and not f.hide and any(loop[uv_layer].select for loop in f.loops)}
        time_v2 = time.time() - start_time

        # Variant 3
        start_time = time.time()
        p_selected_faces_v3 = {
            f for f in bm.faces if f.select and not f.hide for loop in f.loops
            if loop[uv_layer].select}
        time_v3 = time.time() - start_time

        # Variant 4
        start_time = time.time()
        p_selected_faces_v4 = {
                f for f in bm.faces for loop in f.loops
                if not f.hide and f.select and loop[uv_layer].select and loop[uv_layer].select_edge
            }
        time_v4 = time.time() - start_time

        # Variant 5
        start_time = time.time()
        p_selected_faces_v5 = set()
        for f in bm.faces:
            if f.select and not f.hide:
                if all(loop[uv_layer].select for loop in f.loops):
                    p_selected_faces_v5.add(f)

        time_v5 = time.time() - start_time

        # Вывод результатов в консоль
        print(f"Variant 1: {time_v1:.6f} seconds, {len(p_selected_faces_v1)} faces")
        print(f"Variant 2: {time_v2:.6f} seconds, {len(p_selected_faces_v2)} faces")
        print(f"Variant 3: {time_v3:.6f} seconds, {len(p_selected_faces_v3)} faces")
        print(f"Variant 4: {time_v4:.6f} seconds, {len(p_selected_faces_v4)} faces")
        print(f"Variant 5: {time_v5:.6f} seconds, {len(p_selected_faces_v4)} faces")

        return {'FINISHED'}


class ZUV_OP_TestIslandUtils(bpy.types.Operator):
    bl_description = 'Test Islands utils'
    bl_idname = "uv.test_islandutils"
    bl_label = 'Test Island Utils'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        b_is_loop_domain = is_loop_domain(context)

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=False):

            if b_is_loop_domain and not uv_layer:
                continue

            # interval = timer()

            # islands = UvIslandUtils.get_uv_islands(
            #     context, bm, uv_layer,
            #     b_selected_only=False,
            #     b_include_hidden=False,
            #     b_incl_partially_hidden=True)

            # print(f'Time: {timer()-interval}')
            # print(f'Islands count: {len(islands)}: {"#" * len(islands)}')

            # print(f'''Islands Indices: {
            #         UvIslandUtils.get_selected_uv_islands(
            #         context, bm, uv_layer,
            #         in_indices=True,
            #         b_incl_partially_hidden=True)
            #     }''')

            # print('--------------- Yield ----------------------')
            # print(UvIslandUtils.yield_uv_islands(context, bm, uv_layer, True, False))
            # for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, True, False, b_include_partially_hidden=False):
            #     print([f.index for f in island])

            for i, island in enumerate(UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=True, b_include_hidden=False, b_include_partially_hidden=False)):
                print(i)
                SelectionUtils.select_faces_any_context_b5(context, bm, island)

            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


class SYSTEM_PT_Debug(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_label = "Debug"
    # bl_parent_id = "DATA_PT_uv_texture_advanced"
    bl_region_type = 'UI'
    bl_idname = "SYSTEM_PT_Debug"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):

        if ZenPolls.version_since_5_0_0:
            p_act_obj = context.active_object
            if p_act_obj and p_act_obj.type == 'MESH':
                me: bpy.types.Mesh = p_act_obj.data
                if me.is_editmode:
                    bm_orig = bmesh.from_edit_mesh(me)
                    bm = bm_orig.copy()
                    bm.uv_select_sync_valid = bm_orig.uv_select_sync_valid
                    bm.verts.ensure_lookup_table()
                    bm.edges.ensure_lookup_table()
                    bm.faces.ensure_lookup_table()

                    row = self.layout.row(align=True)
                    r1 = row.row(align=True)
                    r1.label(text='UV Sync Valid:')
                    r2 = row.row(align=True)
                    r2.alignment = 'RIGHT'
                    r2.alert = not bm.uv_select_sync_valid
                    r2.label(text=str(bm.uv_select_sync_valid))

                    p_loops = uvedit_get_bm_selected_loops(context.tool_settings, bm, bm.loops.layers.uv.active)
                    row = self.layout.row(align=True)
                    row.label(text=f"Loops: {len(p_loops)}")

                    row = self.layout.row(align=True)
                    p_loops = [
                        loop for face in bm.faces
                        for loop in face.loops
                        if not face.hide and (context.tool_settings.use_uv_select_sync or face.select) and loop.uv_select_vert]
                    row.label(text=f"Loops (UV Vert): {len(p_loops)}")

                    bm.free()

        draw_test_operators(context, self.layout)


def draw_test_operators(context, layout):
    for cl in test_classes:
        layout.operator(cl.bl_idname)


test_classes = (
    ZUV_OT_TestUnwrapConstraint,
    ZUV_OT_TestContext,
    ZUV_OT_Test_Select_Loops,
    ZUV_OT_Test_Select_Island,
    ZUV_OT_SmartSelectLoop,
    ZUV_OP_TestOperator,
    OBJECT_OT_ComparePerformanceComprehension,
    ZUV_OP_TestIslandUtils,
    ZUV_OT_SmartSelectEdges,
    ZUV_OT_TestUVSyncSelect
    )


def register_test_operator():
    for cl in test_classes:
        bpy.utils.register_class(cl)

    # Panel registration
    bpy.utils.register_class(SYSTEM_PT_Debug)

    register_weighted_td()


def unregister_test_operator():
    bpy.utils.unregister_class(SYSTEM_PT_Debug)

    for cl in test_classes:
        bpy.utils.unregister_class(cl)

    unregister_weighted_td()


if __name__ == "__main__":
    pass
