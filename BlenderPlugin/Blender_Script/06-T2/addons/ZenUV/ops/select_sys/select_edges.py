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
import math

from ...utils.generic import (
    ResortObjects,
    switch_to_edge_sel_mode
)
from ...utils.uv_factory import UvIslandUtils, SelectionUtils
from ...utils.loops_factory import LoopsFactory
from ...utils.base_clusters.zen_cluster import ZenCluster
from ...utils.constants import u_axis, v_axis

from ...utils.mark_utils import get_splits_edges_indices, get_open_edges_indices
from ...utils.iter_utils import IterUtils


class ZUV_OT_SelectEdgesByDirection(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_edges_by_direction"
    bl_label = 'Select Edges By Direction'
    bl_zen_short_name = 'Edges by Direction'
    bl_description = 'Select edges by direction'
    bl_options = {'REGISTER', 'UNDO'}

    clear_sel: bpy.props.BoolProperty(
        name="Clear",
        description="Clear previous selection",
        default=True
    )
    direction: bpy.props.EnumProperty(
        name="Direction",
        description="Edge direction",
        items=[
            ("U", "U", "U Axis"),
            ("V", "V", "V Axis"),
        ],
        default="U"
    )
    angle: bpy.props.FloatProperty(
        name="Angle",
        min=0,
        max=45,
        default=30,
    )

    desc: bpy.props.StringProperty(name="Description", default='Select edges by direction', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_description

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "clear_sel")
        layout.prop(self, "direction")
        layout.prop(self, "angle")

    def execute(self, context):
        objs = ResortObjects.resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {"CANCELLED"}

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            islands = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
            if not islands:
                self.report({'WARNING'}, "Select some Island.")
                return {"CANCELLED"}

            switch_to_edge_sel_mode(context)

            for island in islands:
                cl = ZenCluster(context, obj, island, bm)
                if self.clear_sel:
                    SelectionUtils.select_faces_any_context(context, island, state=False, bm=bm, uv_layer=uv_layer)
                if self.direction == 'U':
                    axis = u_axis
                elif self.direction == 'V':
                    axis = v_axis
                edges = cl.get_edges_by_angle_to_axis(math.radians(self.angle), axis)

                if edges:
                    LoopsFactory.select_loops(context, bm, [lp for u_e in edges for lp in u_e.loops], uv_layer, state=True)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_Select_UV_Borders(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_uv_borders"
    bl_label = 'Select UV Borders'
    bl_zen_short_name = 'Borders'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select existing UV Borders'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    mode: bpy.props.EnumProperty(
        name="Mode",
        description="Selection Type",
        items=[
            ("ISLAND", "By Island", "By selected island"),
            ("ALL_ISLANDS", "All Borders", "All UV border edges"),
            ("FACES", "By Faces", "By selected faces")
            ],
        default="ALL_ISLANDS")

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

        if self.clear_selection and self.mode == 'ALL_ISLANDS':
            from ...utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        switch_to_edge_sel_mode(context)

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            SelectionUtils.select_uv_border(context, bm, uv_layer, self.mode, self.clear_selection)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_Select_OpenEdges(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_open_edges"
    bl_label = 'Select Open Edges'
    bl_zen_short_name = 'Open Edges'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select open edges. The way that looks in the 3d viewport'

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
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            from ...utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        switch_to_edge_sel_mode(context)

        p_state = self.mode == 'SELECT'

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            looplist = (lp for i in get_open_edges_indices(bm) for lp in bm.edges[i].link_loops)
            LoopsFactory.select_loops(context, bm, looplist=looplist, uv_layer=uv_layer, state=p_state)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if IterUtils.last_errors:
            bpy.app.timers.register(
                lambda: IterUtils.show_iteration_errors_popup(context),
                first_interval=0.1)

        return {'FINISHED'}


class ZUV_OT_Select_SplitsEdges(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_splits_edges"
    bl_label = 'Select Splits Edges'
    bl_zen_short_name = 'Cylinder Edges (Splits)'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects island edges that belong to the same mesh edge and split the island by itself'

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
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            from ...utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        switch_to_edge_sel_mode(context)

        p_state = self.mode == 'SELECT'

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=False, b_include_hidden=False):
                looplist = (lp for i in get_splits_edges_indices(island, uv_layer) for lp in bm.edges[i].link_loops)
                LoopsFactory.select_loops(context, bm, looplist=looplist, uv_layer=uv_layer, state=p_state)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if IterUtils.last_errors:
            bpy.app.timers.register(
                lambda: IterUtils.show_iteration_errors_popup(context),
                first_interval=0.1)

        return {'FINISHED'}


class ConditionEdge:
    def __init__(self, edge, splits_indices_list, open_indices_list, borders_indices_list):
        self.edge = edge
        self.sharp = self.init_is_sharp()
        self.seam = self.init_is_seam()
        self.splits = self.init_is_splits(splits_indices_list)
        self.boundary = self.init_is_borders(borders_indices_list)
        self.open = self.init_is_open(open_indices_list)

    def init_is_sharp(self):
        return not self.edge.smooth

    def init_is_seam(self):
        return self.edge.seam

    def init_is_splits(self, splits_indices_list):
        return self.edge.index in splits_indices_list

    def init_is_borders(self, borders_indices_list):
        return self.edge.index in borders_indices_list

    def init_is_open(self, open_indices_list):
        return self.edge.index in open_indices_list


class ZUV_OT_SelectEdgeByCondition(bpy.types.Operator):
    bl_idname = "mesh.select_edge_by_condition"
    bl_label = "Select Edge by Condition"
    bl_zen_short_name = 'Edges by Condition'
    bl_description = "Select edges based on various conditions and logic operations with NOT support"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clears the initial selection before applying the operation',
        default=True)

    select_condition: bpy.props.EnumProperty(
        name="Select Condition",
        items=[
            ("SHARP", "Sharp", "Select edges that are markerd sharp"),
            ("SEAM", "Seam", "Select edges that are markerd seam"),
            ("SPLITS", "Splits", "Selects edges that belong to the same mesh edge and split the island by itself"),
            ("BORDERS", "Borders", "Select edges that are UV borders"),
            ("OPEN", "Open", "Select edges that are open. Including those adjacent to hidden faces"),
        ],
        default="SHARP",
    )
    is_active_second_condition: bpy.props.BoolProperty(name="Second Condition", default=False)
    logic_operation: bpy.props.EnumProperty(
        name="Logical Operation",
        items=[
            ("AND", "AND", "All conditions must be true"),
            ("OR", "OR", "At least one condition must be true"),
            ("XOR", "XOR", "Only one condition can be true"),
            ("NOR", "NOR", "None of the conditions should be true"),
        ],
        default="AND",
    )
    apply_not: bpy.props.BoolProperty(name="Apply NOT", default=False)
    additional_condition: bpy.props.EnumProperty(
        name="Additional Condition",
        items=[
            ("SHARP", "Sharp", "Additional condition: edges that are markerd sharp"),
            ("SEAM", "Seam", "Additional condition: edges that are markerd seam"),
            ("SPLITS", "Splits", "Additional condition: edges that belong to the same mesh edge and split the island by itself"),
            ("BORDERS", "Borders", "Additional condition: edges that are UV borders"),
            ("OPEN", "Open", "Additional condition: edges that are open"),
        ],
        default="SEAM",
    )

    def draw(self, context):
        layout = self.layout
        p_split = 0.4
        layout.prop(self, 'clear_selection')
        box = layout.box()
        box.label(text='Select edge if:')
        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.label(text="Edge is")
        split.prop(self, "select_condition", text="")

        layout.prop(self, 'is_active_second_condition')
        box = layout.box()
        box.enabled = self.is_active_second_condition
        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.prop(self, "logic_operation", text="")

        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.label(text="Edge is")
        p_text = 'Apply Not' if not self.apply_not else 'Not'
        split.prop(self, "apply_not", text=p_text, toggle=True)

        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.prop(self, "additional_condition", text="")

    def execute(self, context):
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "No objects selected.")
            return {'CANCELLED'}

        switch_to_edge_sel_mode(context)

        if self.clear_selection:
            from ...utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            p_state = True

            p_splits = []
            p_open = []
            p_borders = []
            if 'SPLITS' in {self.select_condition, self.additional_condition}:
                for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=False, b_include_hidden=True):
                    p_splits.extend(get_splits_edges_indices(island, uv_layer))
            if 'OPEN' in {self.select_condition, self.additional_condition}:
                p_open = get_open_edges_indices(bm)
            if 'BORDERS' in {self.select_condition, self.additional_condition}:
                p_borders = UvIslandUtils.get_uv_bound_edges_indexes(bm.faces, uv_layer)

            condition_edges = [ConditionEdge(edge, p_splits, p_open, p_borders) for edge in bm.edges]

            conditions = {
                "SHARP": lambda edge: edge.sharp,
                "SEAM": lambda edge: edge.seam,
                "SPLITS": lambda edge: edge.splits,
                "BORDERS": lambda edge: edge.boundary,
                "OPEN": lambda edge: edge.open,
            }

            primary_condition = conditions[self.select_condition]
            secondary_condition = conditions[self.additional_condition]

            p_cond_edges_idxs = set()
            for condition_edge in condition_edges:
                primary_met = primary_condition(condition_edge)
                if self.is_active_second_condition:
                    if self.apply_not:
                        secondary_met = not secondary_condition(condition_edge)
                    else:
                        secondary_met = secondary_condition(condition_edge)
                else:
                    secondary_met = primary_met

                if self.logic_operation == "AND":
                    condition_met = primary_met and secondary_met
                elif self.logic_operation == "OR":
                    condition_met = primary_met or secondary_met
                elif self.logic_operation == "XOR":
                    condition_met = primary_met != secondary_met
                elif self.logic_operation == "NOR":
                    condition_met = not (primary_met or secondary_met)

                if condition_met:
                    p_cond_edges_idxs.add(condition_edge.edge.index)

            looplist = (lp for i in p_cond_edges_idxs for lp in bm.edges[i].link_loops)
            LoopsFactory.select_loops(context, bm, looplist=looplist, uv_layer=uv_layer, state=p_state)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if IterUtils.last_errors:
            bpy.app.timers.register(
                lambda: IterUtils.show_iteration_errors_popup(context),
                first_interval=0.1)

        return {'FINISHED'}


class ZUV_OT_SelectMaterialBoundaryEdges(bpy.types.Operator):
    bl_idname = "mesh.zenuv_select_material_boundary_edges"
    bl_label = 'Select Material Boundary Edges'
    bl_zen_short_name = 'Material Boundary Edges'
    bl_description = (
        "Selects all edges where the adjacent faces "
        "have different material assignments"
    )
    bl_options = {'REGISTER', 'UNDO'}

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

        switch_to_edge_sel_mode(context)

        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(objs, context, skip_obj_if_no_uv=True):

            looplist = []
            for e in bm.edges:
                if len(e.link_faces) == 2:
                    f1, f2 = e.link_faces
                    if f1.material_index != f2.material_index:
                        looplist.extend(e.link_loops)

            LoopsFactory.select_loops(context, bm, looplist=looplist, uv_layer=uv_layer, state=self.mode == 'SELECT')

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if IterUtils.last_errors:
            bpy.app.timers.register(
                lambda: IterUtils.show_iteration_errors_popup(context),
                first_interval=0.1)

        return {'FINISHED'}


classes = (
    ZUV_OT_Select_UV_Borders,
    ZUV_OT_Select_OpenEdges,
    ZUV_OT_Select_SplitsEdges,
    ZUV_OT_SelectEdgeByCondition,
    ZUV_OT_SelectMaterialBoundaryEdges
)

poll_3_2_select_classes = (
    ZUV_OT_SelectEdgesByDirection,

)


def register():
    for cl in classes:
        bpy.utils.register_class(cl)


def unregister():
    for cl in classes:
        bpy.utils.unregister_class(cl)


if __name__ == "__main__":
    pass
