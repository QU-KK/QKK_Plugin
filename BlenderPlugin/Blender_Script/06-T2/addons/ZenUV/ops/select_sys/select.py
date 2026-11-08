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
import math
from itertools import chain

from ...ui.labels import ZuvLabels

from ...utils.uv_factory import UvIslandUtils, SelectionUtils
from ...utils.loops_factory import LoopsFactory
from ...utils.iter_utils import IterUtils, IterUtils2

from ...utils.generic import ResortObjects, verify_uv_layer, switch_to_face_sel_mode
from ...utils.blender_zen_utils import (
    ZenPolls, update_areas_in_all_screens,
    is_loop_domain, get_selection_mode, is_sync_off)
from ...ops.texel_density.td_utils import UvFaceArea
from ...utils.constants import FACE_UV_AREA_MULT


class ZUV_OT_ConvertSelFacesToSelLoops(bpy.types.Operator):
    bl_idname = "uv.zenuv_convert_sel_faces_to_sel_loops"
    bl_label = "Faces To UV Loops"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Convert selected mesh faces to UV loops and vice versa'

    toggle_uv_sync: bpy.props.BoolProperty(
        name='Toggle UV Sync',
        description='Toggle UV Sync Selection',
        default=True
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if is_sync_off(context):
            return 'Convert selected UV loops to mesh face selection'
        else:
            return 'Convert selected mesh faces to UV loops'

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

        b_is_sync_off = is_sync_off(context)

        if b_is_sync_off:
            bpy.ops.mesh.select_mode(type="FACE")

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
            loops = LoopsFactory._internal_get_loops_by_sel_mode(context, bm, bm.faces, uv_layer, only_uv_edges=True, per_face=False)
            LoopsFactory.select_loops(context, bm, loops, uv_layer)

            if ZenPolls.version_since_5_0_0:
                loops = LoopsFactory._internal_get_loops_by_sel_mode(context, bm, bm.faces, uv_layer, only_uv_edges=True, per_face=False)
                LoopsFactory.select_loops(context, bm, loops, uv_layer)
                # if is_not_sync:
                #     p_state = [None] * len(bm.faces)
                #     for face in bm.faces:
                #         p_state[face.index] = all(lp.uv_select_vert for lp in face.loops)

                #     for face in bm.faces:
                #         face.select = False

                #     for i, state in enumerate(p_state):
                #         if state is True:
                #             bm.faces[i].select = True
                # else:
                #     for face in bm.faces:
                #         for loop in face.loops:
                #             loop.uv_select_vert = face.select
                #             loop.uv_select_edge = face.select

            else:

                if b_is_sync_off:
                    p_state = [None] * len(bm.faces)

                    if ZenPolls.version_since_3_2_0:
                        for face in bm.faces:
                            p_state[face.index] = all(lp[uv_layer].select_edge for lp in face.loops)
                    else:
                        for face in bm.faces:
                            p_state[face.index] = all(lp[uv_layer].select for lp in face.loops)

                    for face in bm.faces:
                        face.select = False

                    for i, state in enumerate(p_state):
                        if state is True:
                            bm.faces[i].select = True

                else:
                    if ZenPolls.version_since_3_2_0:
                        for face in bm.faces:
                            for loop in face.loops:
                                loop[uv_layer].select = face.select
                                loop[uv_layer].select_edge = face.select
                    else:
                        for face in bm.faces:
                            for loop in face.loops:
                                loop[uv_layer].select = face.select

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        if self.toggle_uv_sync:
            if b_is_sync_off:
                context.scene.tool_settings.use_uv_select_sync = True
                if bpy.ops.mesh.select_mode.poll():
                    bpy.ops.mesh.select_mode(type='FACE')
            else:
                context.scene.tool_settings.use_uv_select_sync = False
                if bpy.ops.mesh.select_all.poll():
                    bpy.ops.mesh.select_all(action="SELECT")
                if context.scene.tool_settings.uv_select_mode not in {"FACE", "ISLAND"}:
                    context.scene.tool_settings.uv_select_mode = "FACE"

        update_areas_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OT_ConvertSelEdgesToSelLoops(bpy.types.Operator):
    bl_idname = "uv.zenuv_convert_sel_edges_to_sel_loops"
    bl_label = "Edges To UV Loops"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Convert selected mesh edges to UV loops and vice versa'

    toggle_uv_sync: bpy.props.BoolProperty(
        name='Toggle UV Sync',
        description='Toggle UV Sync Selection',
        default=True
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if is_sync_off(context):
            return 'Convert selected UV loops to mesh edge selection'
        else:
            return 'Convert selected mesh edges to UV loops'

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
        b_is_sync_off = is_sync_off(context)

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            if ZenPolls.version_since_5_0_0:
                loops = LoopsFactory._internal_get_loops_by_sel_mode(context, bm, bm.faces, uv_layer, only_uv_edges=True, per_face=False)
                LoopsFactory.select_loops(context, bm, loops, uv_layer)
            else:
                if b_is_sync_off:
                    bpy.ops.mesh.select_mode(type="EDGE")

                    p_state = [None] * len(bm.edges)

                    if ZenPolls.version_since_3_2_0:
                        for edge in bm.edges:
                            p_state[edge.index] = any(lp[uv_layer].select_edge for lp in edge.link_loops)
                    else:
                        for edge in bm.edges:
                            p_state[edge.index] = any(lp[uv_layer].select for lp in edge.link_loops)

                    for edge in bm.edges:
                        edge.select = False

                    for i, state in enumerate(p_state):
                        if state is True:
                            bm.edges[i].select = True

                else:
                    sel_edges = [e.index for e in bm.edges if e.select]
                    for lp in (lp for v in bm.verts for lp in v.link_loops):
                        lp[uv_layer].select = False
                        lp[uv_layer].select_edge = False

                    if ZenPolls.version_since_3_2_0:
                        def select_connected_loops(p_loop):
                            p_uv = p_loop[uv_layer].uv
                            for lp in p_loop.vert.link_loops:
                                if lp[uv_layer].uv == p_uv:
                                    lp[uv_layer].select = True

                        for i in sel_edges:
                            for loop in bm.edges[i].link_loops:
                                loop[uv_layer].select = True
                                loop[uv_layer].select_edge = True
                                loop.link_loop_next[uv_layer].select = True
                                select_connected_loops(loop)
                                select_connected_loops(loop.link_loop_next)

                    else:
                        for edge in bm.edges:
                            for loop in edge.link_loops:
                                loop[uv_layer].select = True

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if self.toggle_uv_sync:
            if b_is_sync_off:
                context.scene.tool_settings.use_uv_select_sync = True
                if bpy.ops.mesh.select_mode.poll():
                    bpy.ops.mesh.select_mode(type='EDGE')
            else:
                context.scene.tool_settings.use_uv_select_sync = False
                if bpy.ops.mesh.select_all.poll():
                    bpy.ops.mesh.select_all(action="SELECT")
                if context.scene.tool_settings.uv_select_mode not in {"EDGE"}:
                    context.scene.tool_settings.uv_select_mode = "EDGE"

        update_areas_in_all_screens(context)

        return {'FINISHED'}


class ZUV_OT_UVSyncSelect(bpy.types.Operator):
    bl_idname = "uv.zenuv_sync_select"
    bl_label = "Zen Sync"
    bl_description = (
        'Keep UV and edit mode mesh selection in sync,\n'
        'showing all islands of unhided mesh elements.\n'
        '* Edges and Faces - only supported!')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context: bpy.types.Context):

        if ZenPolls.version_since_5_0_0:
            objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
            if not objs:
                self.report({'WARNING'}, "No objects selected.")
                return {'CANCELLED'}

            b_is_sync_off = not context.scene.tool_settings.use_uv_select_sync
            sync_selection_types = True

            bpy_selection_mode = get_selection_mode(context)

            if not sync_selection_types and get_selection_mode(context) == 'EDGE':
                bpy_selection_mode = 'EDGE'

            storage = dict()

            for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
                if is_loop_domain(context):
                    looplist = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer, only_uv_edges=bpy_selection_mode == 'EDGE')
                    storage[obj] = {lp.index for lp in looplist}
                else:
                    if b_is_sync_off:
                        looplist = LoopsFactory.collect_loops_in_uv_editor_in_sync_off(context, bm.faces, only_uv_edges=bpy_selection_mode == 'EDGE', per_face=False)
                    else:
                        looplist = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer, only_uv_edges=bpy_selection_mode == 'EDGE')
                    storage[obj] = {lp.index for lp in looplist}

            if b_is_sync_off:
                context.scene.tool_settings.use_uv_select_sync = True
                bpy.ops.mesh.select_all(action="DESELECT")
            else:
                context.scene.tool_settings.use_uv_select_sync = False
                bpy.ops.mesh.select_all(action="SELECT")

            if sync_selection_types:
                if b_is_sync_off:
                    if bpy.ops.mesh.select_mode.poll():
                        bpy.ops.mesh.select_mode(type=bpy_selection_mode)
                else:
                    if bpy_selection_mode == 'VERT':
                        context.scene.tool_settings.uv_select_mode = 'VERTEX'
                    else:
                        context.scene.tool_settings.uv_select_mode = bpy_selection_mode

            for obj, loopidxs in storage.items():
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                looplist = [lp for f in bm.faces for lp in f.loops if lp.index in loopidxs]

                if is_loop_domain(context):
                    LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)
                else:
                    if not context.scene.tool_settings.use_uv_select_sync:
                        LoopsFactory.select_loops_in_uv_editor_in_sync_off(context, bm, looplist, uv_layer, state=True)
                    else:
                        LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)

                if is_sync_off(context):
                    bm.uv_select_sync_valid = False

                bmesh.update_edit_mesh(obj.data)

            return {'FINISHED'}
        else:

            was_mesh_selection = list(context.tool_settings.mesh_select_mode)
            was_uv_selection = context.scene.tool_settings.uv_select_mode

            res = (
                bpy.ops.uv.zenuv_convert_sel_edges_to_sel_loops(toggle_uv_sync=True)
                if get_selection_mode(context) == 'EDGE' else
                bpy.ops.uv.zenuv_convert_sel_faces_to_sel_loops(toggle_uv_sync=True))

            if is_sync_off(context):
                context.scene.tool_settings.uv_select_mode = was_uv_selection
            else:
                context.tool_settings.mesh_select_mode = was_mesh_selection

            return res


class ZUV_OT_SelectLinkedLoops(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_linked_loops"
    bl_label = "Select Linked Loops"
    bl_zen_short_name = "Linked Loops"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects all loops belonging to the mesh vertex based on any already selected loop'

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        s_desc = cls.bl_description
        if not is_sync_off(context):
            s_desc += ".\nRequires UV Sync Selection - off"
        return s_desc

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        if ZenPolls.version_since_5_0_0:
            return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'
        else:
            b_is_loop_domain = is_loop_domain(context)
            return b_is_loop_domain and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ...utils.loops_factory import LoopsFactory

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if is_loop_domain(context):
            for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

                p_loops = LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer, groupped=False)

                LoopsFactory.select_linked_loops(p_loops, uv_layer)

                bm.select_flush_mode()
                bmesh.update_edit_mesh(obj.data, loop_triangles=False)
        else:
            if not ZenPolls.version_since_5_0_0:
                self.report({'WARNING'}, "Only in UV Sync Selection is Off")
                return {'CANCELLED'}

        return {'FINISHED'}


class ZUV_OT_SelectHalf(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_half"
    bl_label = 'Select Half'
    bl_zen_short_name = 'Half'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects a part of the model according to its location relative to the coordinate axis'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)
    mesh_axis: bpy.props.EnumProperty(
        name='Mesh Axis',
        description='The axis along which the selection is made',
        items=[
            ("X", "X", "Aalong the X axis"),
            ("Y", "Y", "Along the Y axis"),
            ("Z", "Z", "Along the Z axis")],
        default='X')
    axis_direction: bpy.props.EnumProperty(
        name='Axis Direction',
        description='Axis direction',
        items=[
            ("NEGATIVE", "-", "Negative"),
            ("POSITIVE", "+", "Positive")],
        default='POSITIVE')
    include_zero: bpy.props.BoolProperty(
        name='Include Zero',
        description='Including zero coordinates',
        default=True)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'clear_selection')
        row = layout.row(align=True)
        row.label(text='Mesh Axis:')
        row = row.row(align=True)
        s = row.split(factor=0.2, align=True)
        row = s.row(align=True)
        row.prop(self, 'axis_direction', expand=True)
        s.prop(self, 'mesh_axis', text='')
        layout.prop(self, 'include_zero')

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        self.precision = 6

        if self.clear_selection:
            from ...utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        p_axis = {'X': 0, 'Y': 1, 'Z': 2}[self.mesh_axis]

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=False):

            if not uv_layer:
                uv_layer = verify_uv_layer(bm)

            if is_loop_domain(context):
                p_uv_select_mode = get_selection_mode(context)
                if p_uv_select_mode == 'EDGE':
                    looplist = (lp for e in self.collect_edges(p_axis, bm) for lp in e.link_loops)
                    LoopsFactory.select_loops(context, bm, looplist, uv_layer)

                    if not self.include_zero:
                        looplist = (lp for e in self.get_zero_edges(p_axis, bm) for lp in e.link_loops)
                        LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=False)

                elif p_uv_select_mode == 'FACE':
                    p_cache = self.collect_faces(bm)
                    if self.axis_direction == 'NEGATIVE':
                        looplist = (lp for i in p_cache for lp in i[1].loops if i[0][p_axis] < 0)
                    else:
                        looplist = (lp for i in p_cache for lp in i[1].loops if i[0][p_axis] > 0)

                    LoopsFactory.select_loops(context, bm, looplist, uv_layer)

                    if self.include_zero:
                        looplist = (lp for i in p_cache for lp in i[1].loops if i[0][p_axis] == 0)
                        LoopsFactory.select_loops(context, bm, looplist, uv_layer)

                else:
                    p_cache = self.collect_verts(bm)
                    if self.axis_direction == 'NEGATIVE':
                        looplist = (lp for i in p_cache for lp in i[1].link_loops if i[0][p_axis] < 0)
                    else:
                        looplist = (lp for i in p_cache for lp in i[1].link_loops if i[0][p_axis] > 0)
                    LoopsFactory.select_loops(context, bm, looplist, uv_layer)

                    if self.include_zero:
                        looplist = (lp for i in p_cache for lp in i[1].link_loops if i[0][p_axis] == 0)
                        LoopsFactory.select_loops(context, bm, looplist, uv_layer)
            else:
                mesh_select_mode = context.tool_settings.mesh_select_mode[:]

                if mesh_select_mode == (False, True, False):
                    for e in self.collect_edges(p_axis, bm):
                        e.select = True

                    if not self.include_zero:
                        for e in self.get_zero_edges(p_axis, bm):
                            e.select = False

                elif mesh_select_mode == (False, False, True):
                    self.select_mesh_items(p_axis, self.collect_faces(bm))

                else:
                    self.select_mesh_items(p_axis, self.collect_verts(bm))

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}

    def collect_verts(self, bm):
        return [(v.co.to_tuple(self.precision), v) for v in bm.verts]

    def collect_faces(self, bm):
        return [(f.calc_center_bounds().to_tuple(self.precision), f) for f in bm.faces]

    def collect_edges(self, p_axis, bm):
        if self.axis_direction == 'NEGATIVE':
            return (e for e in bm.edges if all(v.co.to_tuple(self.precision)[p_axis] <= 0 for v in e.verts))
        else:
            return (e for e in bm.edges if all(v.co.to_tuple(self.precision)[p_axis] >= 0 for v in e.verts))

    def get_zero_edges(self, p_axis, bm):
        return (e for e in bm.edges if all(v.co.to_tuple(self.precision)[p_axis] == 0 for v in e.verts))

    def select_mesh_items(self, p_axis, p_cache):
        if self.axis_direction == 'NEGATIVE':
            for i in p_cache:
                if i[0][p_axis] < 0:
                    i[1].select = True
        else:
            for i in p_cache:
                if i[0][p_axis] > 0:
                    i[1].select = True
        if self.include_zero:
            for i in p_cache:
                if i[0][p_axis] == 0:
                    i[1].select = True


class AreaIsland:

    def __init__(self, faces, uv_layer) -> None:
        self.faces = faces
        self.area = UvFaceArea.get_uv_faces_area(faces, uv_layer) * FACE_UV_AREA_MULT


class ZUV_OT_SelectByUvArea(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_by_uv_area"
    bl_label = 'Select by UV Area'
    bl_zen_short_name = 'By UV Area'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select faces by their UV area'

    clear_selection: bpy.props.BoolProperty(
        name=ZuvLabels.OT_TDPR_SEL_BY_TD_CLEAR_SEL_LABEL,
        description=ZuvLabels.OT_TDPR_SEL_BY_TD_CLEAR_SEL_DESC,
        default=True
        )

    condition: bpy.props.EnumProperty(
        name=ZuvLabels.PROP_SEL_BY_UV_AREA_CONDITION_LABEL,
        description=ZuvLabels.PROP_SEL_BY_UV_AREA_CONDITION_DESC,
        items=[
            ("LESS", "Less than", ""),
            ("EQU", "Equal to", ""),
            ("MORE", "More than", ""),
            ("WITHIN", "Within range", ""),
            ("ZERO", "Zero Area", "")
        ],
        default="ZERO"
    )
    treshold: bpy.props.FloatProperty(
        name=ZuvLabels.PROP_SEL_BY_UV_AREA_TRESHOLD_LABEL,
        description=ZuvLabels.PROP_SEL_BY_UV_AREA_TRESHOLD_DESC,
        precision=2,
        default=0.5,
        min=0.0
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Mode for getting area",
        items=[
            ('ISLAND', 'Island', 'Get Area from selected island'),
            ('FACE', 'Face', 'Get area from selected faces'),
        ],
        default="ISLAND"
    )

    def draw(self, context):
        sc_lv_prop = context.scene.zen_uv
        layout = self.layout
        layout.prop(self, 'mode')
        layout.prop(self, "clear_selection")
        box = layout.box()
        box.label(text=ZuvLabels.LABEL_SEL_BY_UV_AREA_DRAW if self.mode == 'FACE' else ZuvLabels.LABEL_SEL_BY_UV_AREA_DRAW.replace('Faces', 'Islands'))
        box.prop(self, "condition")
        if self.condition == "WITHIN":
            row = box.row(align=True)
            row.prop(sc_lv_prop, "range_value_start")
            row.prop(sc_lv_prop, "range_value_end")
        elif self.condition == "ZERO":
            pass
        else:
            box.prop(sc_lv_prop, "area_value_for_sel")
        box.prop(self, "treshold")

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        for obj in objs:
            if len(obj.data.uv_layers) == 0:
                self.report({'WARNING'}, f"Cancelled. Object {obj.name} have no active UV Map.")
                return {'CANCELLED'}

        self.sc_lv_prop = context.scene.zen_uv

        condition = {"LESS": self.less, "EQU": self.equ, "MORE": self.more, "WITHIN": self.within, "ZERO": self.zero}

        if self.clear_selection:
            bpy.ops.uv.select_all(action='DESELECT')

        p_counter = 0
        if is_sync_off(context):

            context.scene.tool_settings.uv_select_mode = "FACE"

            for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

                if self.mode == 'FACE':
                    for_sel_faces = [f for f in bm.faces if condition[self.condition](UvFaceArea.get_uv_faces_area([f, ], uv_layer) * FACE_UV_AREA_MULT, self.sc_lv_prop.area_value_for_sel)]
                else:
                    for_sel_faces = self.get_faces_for_select(context, condition, bm, uv_layer)
                SelectionUtils.select_faces_any_context(context, for_sel_faces, state=True, bm=bm, uv_layer=uv_layer)
                p_counter += sum(1 for _ in for_sel_faces)
                self.update_edit_bmesh(bm, obj)
        else:

            bpy.ops.mesh.select_mode(type="FACE")

            for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):
                init_selection = [f.index for f in bm.faces if f.select]
                if self.mode == 'FACE':
                    for face in bm.faces:
                        p_condition = condition[self.condition](UvFaceArea.get_uv_faces_area([face, ], uv_layer) * FACE_UV_AREA_MULT, self.sc_lv_prop.area_value_for_sel)
                        face.select = p_condition
                        p_counter += p_condition
                else:
                    for face in self.get_faces_for_select(context, condition, bm, uv_layer):
                        face.select = True
                        p_counter += 1

                if not self.clear_selection:
                    self.restore_selection(bm, init_selection)

                self.update_edit_bmesh(bm, obj)

        if self.condition == 'ZERO':
            self.report({'INFO'}, f"Selected {p_counter} zero area face{'s' if p_counter != 1 else ''}")

        return {'FINISHED'}

    def get_faces_for_select(self, context, condition, bm, uv_layer):
        ar_islands = [
            AreaIsland(island, uv_layer)
            for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=False, b_include_hidden=False)]
        return chain.from_iterable([i.faces for i in ar_islands if condition[self.condition](i.area, self.sc_lv_prop.area_value_for_sel)])

    def update_edit_bmesh(self, bm, obj):
        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

    def restore_selection(self, bm, init_selection):
        for i in init_selection:
            bm.faces[i].select = True

    def less(self, area, value):
        return area < value + self.treshold

    def equ(self, area, value):
        return value - self.treshold < area <= value + self.treshold

    def more(self, area, value):
        return area > value - self.treshold

    def within(self, area, value):
        return self.sc_lv_prop.range_value_start - self.treshold <= area <= self.sc_lv_prop.range_value_end + self.treshold

    def zero(self, area, value):
        return area <= 0.0 + self.treshold


class ZUV_OT_GrabSelectedArea(bpy.types.Operator):
    bl_idname = "uv.zenuv_grab_sel_area"
    bl_label = 'Get Selected Area'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Get the area of the selected. This value is used in the 'Select by UV Area' operator"

    real_area: bpy.props.FloatProperty(
        name=ZuvLabels.PROP_GET_UV_REAL_LABEL,
        description=ZuvLabels.PROP_GET_UV_REAL_DESC,
        default=0.0,
        options={'HIDDEN'}
    )
    multiplied_area: bpy.props.FloatProperty(
        name=ZuvLabels.PROP_GET_UV_MULT_LABEL,
        description=ZuvLabels.PROP_GET_UV_REAL_DESC,
        default=2.0,
        options={'HIDDEN'},
    )
    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Mode for getting area",
        items=[
            ('ISLAND', 'Island', 'Get Area from selected island'),
            ('FACE', 'Face', 'Get area from selected faces'),
        ],
        default="ISLAND"
    )
    average: bpy.props.BoolProperty(
        name='Average',
        description='Get the average value from the selected',
        default=False
        )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'mode')
        layout.prop(self, 'average')
        box = layout.box()
        box.prop(self, "real_area")
        box.label(text="Real UV Area" + ": " + str(self.real_area))
        box.prop(self, "multiplied_area")

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}
        self.sc_lv_prop = context.scene.zen_uv
        sel_faces_count = []
        part_area = []
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            if self.mode == 'FACE':
                faces = SelectionUtils.get_faces_by_any_init_selection(context, bm, uv_layer, b_include_hidden=False)
                sel_faces_count.append(len(faces))
                part_area.append(sum([UvFaceArea.get_uv_faces_area([face, ], uv_layer) for face in faces]))
            else:
                islands = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
                sel_faces_count.append(len(islands))
                faces = [f for island in islands for f in island]
                part_area.append(sum([UvFaceArea.get_uv_faces_area([face, ], uv_layer) for face in faces]))
        sel_faces_count = sum(sel_faces_count)
        if sel_faces_count != 0:
            self.real_area = sum(part_area)
            if self.average:
                self.real_area /= sel_faces_count
            self.multiplied_area = self.real_area * FACE_UV_AREA_MULT
            self.sc_lv_prop.area_value_for_sel = self.multiplied_area
            self.update_range_values()
            self.report({'INFO'}, f'Area of selected {"islands " if self.mode == "ISLAND" else "faces "} {self.real_area}')
        else:
            self.report({'WARNING'}, "There are no selected faces")
        return {'FINISHED'}

    def update_range_values(self):
        self.sc_lv_prop.range_value_start = self.multiplied_area - 2
        self.sc_lv_prop.range_value_end = self.multiplied_area + 2


class ZUV_OT_SelectFacesLessOnePixel(bpy.types.Operator):
    bl_description = 'Selects faces with an area less than the specified number of pixels'
    bl_idname = 'uv.zenuv_select_faces_less_than_pixel'
    bl_zen_short_name = 'Faces Less than Pixel'
    bl_label = 'Select Faces Less than Pixel'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    pixel_count: bpy.props.IntProperty(
        name="Pixel Count",
        description="Number of pixels for the calculation",
        default=1,
        min=1
    )

    area_threshold: bpy.props.FloatProperty(
        name="Area Threshold",
        description="Tolerance level for face area selection",
        default=0.0,
        min=0.0,
        max=1.0
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return context.area.type == 'IMAGE_EDITOR' and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'clear_selection')
        layout.prop(self, 'pixel_count')
        layout.prop(self, 'area_threshold')

    def execute(self, context):
        from ...ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image is None:
            self.report({'ERROR'}, "No image selected in the UV Editor.")
            return {'CANCELLED'}

        if p_image.size[0] == 0 or p_image.size[1] == 0:
            self.report({'ERROR'}, "The active image in the UV Editor is incorrect.")
            return {'CANCELLED'}

        switch_to_face_sel_mode(context)

        if self.clear_selection:
            from ...utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        p_pixel_size = 1 / p_image.size[0], 1 / p_image.size[1]

        p_pixel_area = p_pixel_size[0] * p_pixel_size[1] * self.pixel_count

        p_counter = 0
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            p_faces = []
            for f in bm.faces:
                if UvFaceArea.get_uv_faces_area([f, ], uv_layer) <= p_pixel_area * (1 + self.area_threshold):
                    p_faces.append(f)

            p_counter += len(p_faces)

            SelectionUtils.select_faces_any_context(context, p_faces, state=True, bm=bm, uv_layer=uv_layer)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if p_counter:
            p_message = f'Selected {p_counter} face{"s" if p_counter != 1 else ""}'
        else:
            p_message = 'No faces were selected'

        self.report({'INFO'}, p_message)

        return {'FINISHED'}


class ZUV_OT_SelectFacesByNormal(bpy.types.Operator):
    bl_idname = 'mesh.zenuv_select_faces_by_normal'
    bl_label = 'Select Faces By Normal'
    bl_description = "Select polygons by reference normal"
    bl_zen_short_name = 'Faces By Normal'
    bl_options = {'REGISTER', 'UNDO'}

    clear_initial_selection: bpy.props.BoolProperty(
        name='Clear Initial Selection',
        description='Clears the initial selection before applying the operation',
        default=False)

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Defines how faces are selected based on the reference normal",
        items=[
            ('FRONT', "Front", "Selects polygons facing the reference normal"),
            ('BACK', "Back", "Selects polygons oriented away from the reference normal"),
            ('ALL', "All", "Selects all polygons that match the reference normal")
        ],
        default='ALL')

    reverse_reference_normal: bpy.props.BoolProperty(
        name='Reverse Ref. Normal',
        description='Reverses the reference normal direction',
        default=False)

    threshold: bpy.props.FloatProperty(
        name="Threshold",
        description="Controls the accuracy of normal alignment (acts as an angular tolerance)",
        default=0.0872664600610733,
        min=0.0,
        max=math.pi / 2,
        subtype='ANGLE')

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return context.area.type == 'VIEW_3D' and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from collections import defaultdict

        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        input_data = defaultdict(list)
        reference_data = []

        for obj, bm in IterUtils2.iter_objs_with_bmesh(objs):

            M = obj.matrix_world

            input_data[obj.name].extend([f.index for f in bm.faces if f.select])

            for i in input_data[obj.name]:
                reference_data.append((M.to_3x3() @ bm.faces[i].normal, M @ bm.faces[i].calc_center_median()))

        if not any(len(lst) > 0 for lst in input_data.values()):
            self.report({'WARNING'}, "Select reference faces")
            return {'CANCELLED'}

        for obj, bm in IterUtils2.iter_objs_with_bmesh(objs):
            M = obj.matrix_world

            for reference_normal, reference_center in reference_data:
                for face in bm.faces:

                    p_normal = - reference_normal if self.reverse_reference_normal else reference_normal

                    if p_normal.angle((M.to_3x3() @ face.normal).normalized()) > self.threshold:
                        continue

                    direction = (M @ face.calc_center_median() - reference_center).normalized()
                    dot_product = direction.dot(reference_normal)

                    if self.mode == 'FRONT' and dot_product <= 0:
                        continue
                    elif self.mode == 'BACK' and dot_product >= 0:
                        continue

                    face.select = True

            bmesh.update_edit_mesh(obj.data)

        if self.clear_initial_selection:
            for obj_name in input_data.keys():
                obj = bpy.data.objects.get(obj_name, None)
                if not obj:
                    continue
                bm = bmesh.from_edit_mesh(obj.data)
                for i in input_data[obj.name]:
                    bm.faces[i].select = False
                bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


select_classes = (
    ZUV_OT_SelectByUvArea,
    ZUV_OT_GrabSelectedArea,
    ZUV_OT_SelectHalf,
    ZUV_OT_ConvertSelFacesToSelLoops,
    ZUV_OT_SelectLinkedLoops,
    ZUV_OT_UVSyncSelect,
    ZUV_OT_ConvertSelEdgesToSelLoops,
    ZUV_OT_SelectFacesLessOnePixel,
    ZUV_OT_SelectFacesByNormal
)


if __name__ == '__main__':
    pass
