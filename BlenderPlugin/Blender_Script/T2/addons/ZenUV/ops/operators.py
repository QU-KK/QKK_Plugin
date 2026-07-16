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

# Zen UV Generic Opertators

import bpy
import bmesh

from collections import defaultdict

from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import (
    get_mesh_data,
    check_selection,
    is_island_flipped,
    switch_to_edge_sel_mode,
    select_by_context,
    bpy_deselect_by_context,
    resort_by_type_mesh_in_edit_mode_and_sel,
    has_unapplied_rotation,
    has_overlapped_triangles_by_area,
    calc_uv_editor_image_aspect_ratio,
    correct_self_intersecting_face
)
from ZenUV.utils.messages import zen_message
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.vlog import Log

from ZenUV.ui.labels import ZuvLabels
from ZenUV.ui.pie import ZsPieFactory


class ZUV_OT_Select_UV_Overlap(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_uv_overlap"
    bl_label = 'Select Overlapped Islands'
    bl_zen_short_name = 'Overlapped'
    bl_description = 'Select Overlapped Islands'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        bpy_deselect_by_context(context)
        if not bpy.ops.uv.select_overlap.poll():
            self.report({'WARNING'}, "Can not select overlappings. Check UV Maps!")
            return {'CANCELLED'}

        bpy.ops.uv.select_overlap()

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                select_by_context(context, bm, island_util.get_island(context, bm, uv_layer), state=True)

        if not check_selection(context):
            zen_message(context, message="Overlappings are not found.",)

        return {'FINISHED'}


class ZUV_OT_SmoothBySharp(bpy.types.Operator):
    bl_idname = "view3d.zenuv_set_smooth_by_sharp"
    bl_label = "Smooth by Sharp"
    bl_description = "Toggle between Auto Smooth 180° (with sharp edges) and regular smooth modes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        if ZenPolls.version_since_4_1_0:
            return 'Sets the "Shade Smooth" mode for all the mesh faces'
        return cls.bl_description

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from math import pi

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        def set_smooth_faces(bm):
            for f in bm.faces:
                f.smooth = True

        for obj in objs:

            if ZenPolls.version_since_4_1_0:
                bm = bmesh.from_edit_mesh(obj.data)
                set_smooth_faces(bm)
                bmesh.update_edit_mesh(obj.data)

            else:
                me = obj.data
                bm = bmesh.from_edit_mesh(me)
                set_smooth_faces(bm)
                bmesh.update_edit_mesh(me)
                me.use_auto_smooth = not me.use_auto_smooth
                if me.use_auto_smooth:
                    me.auto_smooth_angle = pi

        return {'FINISHED'}


class ZUV_OT_Isolate_Island(bpy.types.Operator):
    bl_idname = "uv.zenuv_isolate_island"
    bl_label = 'Isolate Islands (Toggle)'
    bl_description = 'Isolate Islands (Toggle) by selected edge/face of the Islands'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context: bpy.types.Context):
        ZsPieFactory.mark_pie_cancelled()

        b_is_image_editor = context.space_data.type == 'IMAGE_EDITOR'

        b_is_not_sync = b_is_image_editor and not context.scene.tool_settings.use_uv_select_sync

        b_all_isolated = True
        t_data = {}

        b_something_selected = False

        for p_obj in context.objects_in_mode_unique_data:
            if p_obj.type == 'MESH':
                me: bpy.types.Mesh = p_obj.data

                bm = bmesh.from_edit_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                uv_layer = bm.loops.layers.uv.active

                p_islands = []

                if sum(me.count_selected_items()) > 0 and uv_layer:
                    p_selection = [
                            bm.faces[index] for index in island_util.IslandUtils.face_indexes_by_sel_elements(context, bm)]
                    p_islands = island_util.zen_get_islands(
                        bm, p_selection, has_selected_faces=True, is_include_hidden=True)

                p_faces_for_isolate = {
                    face.index
                    for i in p_islands
                    for face in i}

                t_data[me] = (bm, p_faces_for_isolate)

                if len(p_faces_for_isolate):
                    b_something_selected = True

        if b_something_selected:
            mesh_sel_mode = context.tool_settings.mesh_select_mode
            # NOTE: 'VERT' or 'EDGE' in mesh selection causes issue #931
            b_has_vert_and_edges_in_selection_mode = mesh_sel_mode[0] or mesh_sel_mode[1]

            for k, v in t_data.items():
                me: bpy.types.Mesh = k
                bm: bmesh.types.BMesh = v[0]
                p_faces_for_isolate = v[1]

                face: bmesh.types.BMFace
                b_changed = False

                for face in bm.faces:
                    if b_is_not_sync:
                        b_select = face.index in p_faces_for_isolate

                        b_was_hidden = b_select and face.hide
                        if b_was_hidden:
                            face.hide_set(False)

                        if b_was_hidden or face.select != b_select:
                            face.select_set(b_select)
                            b_all_isolated = False
                            b_changed = True
                    else:
                        b_hide = face.index not in p_faces_for_isolate
                        if face.hide != b_hide:
                            face.hide_set(b_hide)
                            b_all_isolated = False
                            b_changed = True

                if b_changed:
                    # NOTE: Fixes issue #931
                    if b_is_not_sync and b_has_vert_and_edges_in_selection_mode:
                        bm.select_flush(True)
                    else:
                        bm.select_flush_mode()
                    bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if not b_something_selected or b_all_isolated:
            if b_is_not_sync:
                if bpy.ops.uv.reveal.poll():
                    bpy.ops.uv.reveal(select=False)
            else:
                if bpy.ops.mesh.reveal.poll():
                    bpy.ops.mesh.reveal(select=False)

        return {'FINISHED'}


class ZUV_OT_Isolate_Part(bpy.types.Operator):
    bl_idname = "uv.zenuv_isolate_part"
    bl_label = 'Isolate Part (Toggle)'
    bl_description = 'Isolate mesh part (Toggle) by selected edge/face'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        active_object = context.active_object
        return (
            active_object is not None and active_object.type == 'MESH' and
            context.mode == 'EDIT_MESH')

    def execute(self, context: bpy.types.Context):
        ZsPieFactory.mark_pie_cancelled()

        b_is_image_editor = context.space_data.type == 'IMAGE_EDITOR'

        b_is_not_sync = b_is_image_editor and not context.scene.tool_settings.use_uv_select_sync

        t_selection_data = {}
        t_hidden_data = {}
        t_bm_data = {}

        b_something_selected = False

        b_changed = False

        for p_obj in context.objects_in_mode_unique_data:
            if p_obj.type == 'MESH':
                me: bpy.types.Mesh = p_obj.data

                bm = bmesh.from_edit_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                t_selection_data[me] = {
                    "verts": set(vert.index for vert in bm.verts if vert.select) if me.total_vert_sel else [],
                    "edges": set(edge.index for edge in bm.edges if edge.select) if me.total_edge_sel else [],
                    "faces": set(face.index for face in bm.faces if face.select) if me.total_face_sel else [],
                    "loops": []
                }

                t_hidden_data[me] = {
                    "verts": set(vert.index for vert in bm.verts if vert.hide),
                    "edges": set(edge.index for edge in bm.edges if edge.hide),
                    "faces": set(face.index for face in bm.faces if face.hide),
                }

                uv_layer = None
                if b_is_not_sync:
                    uv_faces = set()
                    uv_layer = bm.loops.layers.uv.active
                    if uv_layer:
                        t_selection_data[me]["loops"] = [
                            (loop, loop[uv_layer].select_edge, face.index if ZenPolls.version_since_3_2_0 else None)
                            for face in bm.faces for loop in face.loops
                            if not face.hide and loop[uv_layer].select
                        ]
                        uv_faces = []
                        p_data_loops = t_selection_data[me]["loops"]
                        if p_data_loops:
                            _, _, uv_faces = zip(*p_data_loops)

                        uv_faces = set(uv_faces)
                    for face in bm.faces:
                        face.select = face.index in uv_faces

                t_bm_data[me] = (bm, uv_layer)

                if not b_something_selected:
                    b_something_selected = (
                        len(t_selection_data[me]["loops"]) > 0
                        if b_is_not_sync else
                        sum(me.count_selected_items()) > 0)

        if b_something_selected:
            if bpy.ops.mesh.reveal.poll():
                bpy.ops.mesh.reveal(select=False)
            if bpy.ops.mesh.select_linked.poll():
                bpy.ops.mesh.select_linked(delimit={'NORMAL'})
            if bpy.ops.mesh.hide.poll():
                bpy.ops.mesh.hide(unselected=True)

            bpy.ops.mesh.select_all(action='DESELECT')

            if b_is_not_sync:
                if bpy.ops.uv.select_all.poll():
                    bpy.ops.uv.select_all(action='DESELECT')

            for me, data in t_bm_data.items():
                bm, uv_layer = data

                for vert in bm.verts:
                    if vert.hide != (vert.index in t_hidden_data[me]["verts"]):
                        b_changed = True
                    if vert.index in t_selection_data[me]["verts"]:
                        vert.select = True
                for edge in bm.edges:
                    if edge.hide != (edge.index in t_hidden_data[me]["edges"]):
                        b_changed = True
                    if edge.index in t_selection_data[me]["edges"]:
                        edge.select = True
                for face in bm.faces:
                    if face.hide != (face.index in t_hidden_data[me]["faces"]):
                        b_changed = True
                    if face.index in t_selection_data[me]["faces"]:
                        face.select = True
                    if b_is_not_sync and not face.hide:
                        if not face.select:
                            b_changed = True
                            face.select_set(True)

                for loop, select_edge, _ in t_selection_data[me]["loops"]:
                    loop[uv_layer].select = True
                    if ZenPolls.version_since_3_2_0:
                        loop[uv_layer].select_edge = select_edge

                bm.select_flush_mode()
                bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if not b_changed:
            if bpy.ops.mesh.reveal.poll():
                bpy.ops.mesh.reveal(select=False)
            if b_is_not_sync:
                if bpy.ops.uv.reveal.poll():
                    bpy.ops.uv.reveal(select=False)

        return {'FINISHED'}


class ZUV_OT_Select_Loop(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_loop"
    bl_label = 'Select Interseams Loop'
    bl_zen_short_name = 'Int. Loop'
    bl_description = 'Selects an edge loop starting from a given edge, and stops at seam edges. Useful for selecting edge loops without crossing UV seams'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None \
            and active_object.type == 'MESH' \
            and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.get_uv_islands import LoopsFactory as LF
        for obj in context.objects_in_mode:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            bm.edges.ensure_lookup_table()
            no_sync_mode = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

            if no_sync_mode:
                if ZenPolls.version_since_3_2_0:
                    for lp in LF.walk_edgeloop_along(
                                                        [lp for edge in bm.edges for lp in edge.link_loops if lp[uv_layer].select and lp[uv_layer].select_edge],
                                                        uv_layer, no_sync_mode):
                        lp[uv_layer].select = True
                        lp[uv_layer].select_edge = True
                else:
                    for lp in LF.walk_edgeloop_along(
                                                        [lp for edge in bm.edges for lp in edge.link_loops if lp[uv_layer].select],
                                                        uv_layer, no_sync_mode):
                        lp[uv_layer].select = True
            else:
                for lp in LF.walk_edgeloop_along(
                                                    [lp for edge in bm.edges for lp in edge.link_loops if edge.select],
                                                    uv_layer, no_sync_mode):
                    lp.edge.select = True

            bm.select_flush_mode()

            bmesh.update_edit_mesh(me, loop_triangles=False)
            switch_to_edge_sel_mode(context)

        return {'FINISHED'}


class ZUV_OT_SelectSharp(bpy.types.Operator):
    bl_idname = "mesh.zenuv_select_sharp"
    bl_label = 'Select Sharp Edges'
    bl_zen_short_name = 'Sharp'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select Edges Marked as Sharp'

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

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = self.mode == 'SELECT'
        row.prop(self, 'clear_selection')
        layout.prop(self, 'mode')

    @classmethod
    def poll(cls, context):
        if context.objects_in_mode:
            return True
        else:
            return False

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, 'There are no selected objects')
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            bpy_deselect_by_context(context)

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        p_state = self.mode == 'SELECT'

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            p_seams = (e for e in bm.edges if not e.smooth)

            if context.space_data and context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                if ZenPolls.version_since_3_2_0:
                    for e in p_seams:
                        for lp in e.link_loops:
                            lp[uv_layer].select = p_state
                            lp[uv_layer].select_edge = p_state
                            lp.link_loop_next[uv_layer].select = p_state
                else:
                    for e in p_seams:
                        for lp in e.link_loops:
                            lp[uv_layer].select = p_state
                            lp.link_loop_next[uv_layer].select = p_state
            else:
                for e in p_seams:
                    e.select = p_state
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_SelectSeams(bpy.types.Operator):
    bl_idname = 'mesh.zenuv_select_seams'
    bl_label = 'Select Seams Edges'
    bl_zen_short_name = 'Seam'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select Edges Marked as Seams'

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

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = self.mode == 'SELECT'
        row.prop(self, 'clear_selection')
        layout.prop(self, 'mode')

    @classmethod
    def poll(cls, context):
        if context.objects_in_mode:
            return True
        else:
            return False

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, 'There are no selected objects')
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            bpy_deselect_by_context(context)

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        p_state = self.mode == 'SELECT'

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)

            p_seams = (e for e in bm.edges if e.seam)

            if context.space_data and context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                uv_layer = bm.loops.layers.uv.active
                if not uv_layer:
                    continue

                if ZenPolls.version_since_3_2_0:
                    for e in p_seams:
                        for lp in e.link_loops:
                            lp[uv_layer].select = p_state
                            lp[uv_layer].select_edge = p_state
                            lp.link_loop_next[uv_layer].select = p_state
                else:
                    for e in p_seams:
                        for lp in e.link_loops:
                            lp[uv_layer].select = p_state
                            lp.link_loop_next[uv_layer].select = p_state
            else:
                for e in p_seams:
                    e.select = p_state
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_SelectFlipped(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_flipped"
    bl_label = 'Select Flipped Islands'
    bl_zen_short_name = 'Flipped'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select Flipped Islands'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}

        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
        bpy_deselect_by_context(context)

        p_flipped_count = 0
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            for island in island_util.get_islands(context, bm):
                if is_island_flipped(island, uv_layer):
                    p_flipped_count += 1
                    select_by_context(context, bm, [island, ], state=True)

            bm.select_flush_mode()
            # bmesh.update_edit_mesh(me, loop_triangles=False, destructive=False)

        if p_flipped_count == 0:
            self.report({'INFO'}, "No flipped islands were found.")
            zen_message(context, message="No flipped islands were found.",)
        else:
            self.report({'INFO'}, f"Flipped islands found: {p_flipped_count}")

        return {'FINISHED'}


class ZUV_OT_SelectSelfIntersecting(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_self_intersecting"
    bl_label = 'Select Self-Intersecting Faces'
    bl_description = 'Select faces that have intersecting uv edges'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}

        bpy_deselect_by_context(context)

        b_is_uv_no_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

        n_processed = 0
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            loops = bm.calc_loop_triangles()
            bm.faces.ensure_lookup_table()

            triangles = defaultdict(list)

            for looptris in loops:
                if not looptris[0].face.hide and (not b_is_uv_no_sync or looptris[0].face.select):
                    triangles[looptris[0].face.index].append([loop[uv_layer].uv.to_tuple(5) for loop in looptris])

            for k, v in triangles.items():
                p_face: bmesh.types.BMFace = bm.faces[k]
                if has_overlapped_triangles_by_area(p_face, v, uv_layer):
                    n_processed += 1
                    if b_is_uv_no_sync:
                        for loop in bm.faces[k].loops:
                            loop[uv_layer].select = True
                            loop[uv_layer].select_edge = True
                    else:
                        bm.faces[k].select_set(True)

            bm.select_flush_mode()

        if n_processed == 0:
            self.report({'INFO'}, "No self-intersecting faces were found.")
        else:
            self.report({'INFO'}, f"Self-intersecting faces found: {n_processed}")

        return {'FINISHED'}


class ZUV_OT_CorrectSelfIntersecting(bpy.types.Operator):
    bl_idname = "uv.zenuv_correct_self_intersecting"
    bl_label = 'Correct Self-Intersecting'
    bl_description = 'Correct faces that have intersecting uv edges by re-unwrapping its island'
    bl_options = {'REGISTER', 'UNDO'}

    influence: bpy.props.EnumProperty(
        name='Influence',
        description='Defines what parts of mesh will be processed',
        items=[
            ("ISLAND", "Island", "Process islands", "UV_ISLANDSEL", 0),
            ("SELECTION", "Selection", "Process selected mesh elements (vertices, edges, faces)", 'UV_FACESEL', 1)
        ],
        default="ISLAND"
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):

        ZsPieFactory.mark_pie_cancelled()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {"CANCELLED"}

        sync_uv = context.scene.tool_settings.use_uv_select_sync
        b_is_uv_no_sync = context.space_data.type == 'IMAGE_EDITOR' and not sync_uv

        t_processed = defaultdict(list)
        n_processed = 0

        b_is_island_mode = self.influence == 'ISLAND'

        image_aspect_ratio = calc_uv_editor_image_aspect_ratio(context)

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            loops = bm.calc_loop_triangles()
            bm.faces.ensure_lookup_table()

            triangles = defaultdict(list)

            for looptris in loops:
                if not looptris[0].face.hide and (not b_is_uv_no_sync or looptris[0].face.select):
                    triangles[looptris[0].face.index].append([loop[uv_layer].uv.to_tuple(5) for loop in looptris])

            used_faces = [False] * len(bm.faces)

            for k, v in triangles.items():
                p_face: bmesh.types.BMFace = bm.faces[k]

                if used_faces[p_face.index]:
                    continue

                if has_overlapped_triangles_by_area(p_face, v, uv_layer):

                    t_processed[bm].append(p_face.index)
                    n_processed += 1

                    correct_self_intersecting_face(
                        context, p_face, uv_layer, used_faces, image_aspect_ratio,
                        b_is_island_mode, b_is_uv_no_sync)

        if n_processed == 0:
            self.report({'INFO'}, "No self-intersecting faces were found.")
        else:
            bpy_deselect_by_context(context)

            for bm, indices in t_processed.items():
                bm.faces.ensure_lookup_table()
                uv_layer = bm.loops.layers.uv.active
                if uv_layer:
                    for idx in indices:
                        bm.faces[idx].select_set(True)
                        if not sync_uv:
                            for loop in bm.faces[idx].loops:
                                loop[uv_layer].select = True
                                loop[uv_layer].select_edge = True

            bm.select_flush_mode()

            self.report({'INFO'}, f"Self-intersecting islands corrected: {n_processed}")

        return {'FINISHED'}


class ZUV_OT_MirrorSeams(bpy.types.Operator):
    bl_idname = "mesh.zenuv_mirror_seams"
    bl_label = ZuvLabels.OT_MIRROR_SEAMS_LABEL
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = ZuvLabels.OT_MIRROR_SEAMS_DESC

    axis: bpy.props.EnumProperty(
        name='Axis',
        description='The axis along which the mirroring is made',
        items=[
            ("X", "X", "Aalong the X axis"),
            ("Y", "Y", "Along the Y axis"),
            ("Z", "Z", "Along the Z axis"),
            ("TOPOLOGY", "Topology", "Use topology based mirroring")],
        default='X')
    axis_direction: bpy.props.EnumProperty(
        name='Axis Direction',
        description='Axis direction',
        items=[
            ("NEGATIVE", "-", "Negative", 0, 2**0),
            ("POSITIVE", "+", "Positive", 0, 2**1)
            ],
        default={'POSITIVE'},
        options={'ENUM_FLAG'},
    )
    set_mode: bpy.props.EnumProperty(
        name='Set Mode',
        description='Mode for setting seams',
        items=[
            ("ADD", "Add", "Add seams to existing ones"),
            ("REPLACE", "Replace", "Replace existing seams")
            ],
        default='REPLACE'
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        p_split = 0.2

        row = layout.row(align=True)
        row.label(text='Source:')
        row = row.row(align=True)
        s = row.split(factor=p_split, align=True)
        row = s.row(align=True)
        row.prop(self, 'axis_direction', expand=True)
        s.prop(self, 'axis', text='')

        row = layout.row(align=True)
        s = row.split(factor=0.225, align=True)
        row = s.row(align=True)
        row.label(text='Mode:')
        row = s.row(align=True)
        row.prop(self, "set_mode", expand=True)

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if self.axis == 'TOPOLOGY':
            from ZenUV.utils.selection_utils import SelectionProcessor

            SelectionProcessor.reset_state()

            is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

            Storage = SelectionProcessor.collect_selected_objects(
                context,
                is_not_sync,
                b_in_indices=True,
                b_is_skip_objs_without_selection=True,
                b_skip_uv_layer_fail=False)

        is_use_topology = self.axis == 'TOPOLOGY'
        self.precision = 4
        p_axis = {'X': 0, 'Y': 1, 'Z': 2, 'TOPOLOGY': 0}[self.axis]
        m_x, m_y, m_z = {'X': (-1, 1, 1), 'Y': (1, -1, 1), 'Z': (1, 1, -1), 'TOPOLOGY': (-1, 1, 1)}[self.axis]

        if is_use_topology:
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        p_suitable = {}
        is_has_rotation = False
        for obj in objs:
            if has_unapplied_rotation(obj):
                is_has_rotation = True
                print(f'"{obj.name}" has unapplied rotation')
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()

            p_edges = self.collect_edges(p_axis, bm)
            p_suitable.update({obj: [bm, obj.data.use_mirror_topology, p_edges, []]})

            if is_use_topology:
                continue

            mesh_cache = {v.co.to_tuple(self.precision): [e for e in v.link_edges if not e.hide] for v in bm.verts}
            for i in p_edges:
                co, e = i[:]
                adj_edges = mesh_cache.get((co[0] * m_x, co[1] * m_y, co[2] * m_z))
                if adj_edges is None:
                    continue
                for adj_edge in adj_edges:
                    for v in adj_edge.verts:
                        co = v.co.to_tuple(self.precision)
                        if e.verts[1].co.to_tuple(self.precision) == (co[0] * m_x, co[1] * m_y, co[2] * m_z):
                            p_suitable[obj][3].append(adj_edge)

        was_processed = 0
        for obj, edges in p_suitable.items():

            if len(edges[2]) == 0:
                print(f'"{obj.name}" symmetric edges not found')
                continue

            was_processed += 1
            if self.set_mode == 'REPLACE':
                if self.axis_direction == {'NEGATIVE'}:
                    p_be_cleared = self.get_positive(p_axis, edges[0])
                elif self.axis_direction == {'POSITIVE'}:
                    p_be_cleared = self.get_negative(p_axis, edges[0])
                else:
                    p_be_cleared = self.get_all(p_axis, edges[0])

                for i in p_be_cleared:
                    i[1].seam = False

            if is_use_topology:
                for _, edge in edges[2]:
                    edge.select = True
                obj.data.use_mirror_topology = True

            else:
                for e in edges[3]:
                    e.seam = True

            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        if is_use_topology:
            bpy.ops.mesh.select_mirror(axis={self.axis if self.axis != 'TOPOLOGY' else 'X'}, extend=True)
            bpy.ops.mesh.mark_seam(clear=False)

            for obj, data in p_suitable.items():
                obj.data.use_mirror_topology = data[1]

            SelectionProcessor.restore_selection_in_objects(context, Storage, is_not_sync)

        combined_message = [
            'Unapplied Rotation' if is_has_rotation else None,
            'No Symmetric Edges' if was_processed != len(objs) else None,
        ]

        if combined_message:
            self.report({'WARNING'}, f"{', '.join(item for item in combined_message if item is not None)}. The result may be unpredictable")
            return {'FINISHED'}

        return {'FINISHED'}

    def collect_edges(self, p_axis, bm):
        if self.axis_direction == {'NEGATIVE'}:
            return self.get_negative(p_axis, bm)
        elif self.axis_direction == {'POSITIVE'}:
            return self.get_positive(p_axis, bm)
        else:
            return self.get_all(p_axis, bm)

    def get_all(self, p_axis, bm):
        n = self.get_negative(p_axis, bm)
        n.extend(self.get_positive(p_axis, bm))
        return n

    def get_positive(self, p_axis, bm):
        return [(e.verts[0].co.to_tuple(self.precision), e)for e in bm.edges if not e.hide and e.seam and not any(v.co[p_axis] >= 0 for v in e.verts)]

    def get_negative(self, p_axis, bm):
        return [(e.verts[0].co.to_tuple(self.precision), e) for e in bm.edges if not e.hide and e.seam and not any(v.co[p_axis] <= 0 for v in e.verts)]


class ZUV_OT_SetTextureSizePreset(bpy.types.Operator):
    bl_idname = 'wm.zenuv_set_texture_size_preset'
    bl_label = 'Get Texture Size'
    bl_description = 'Get texture size preset from active image size'
    bl_options = {'REGISTER', 'UNDO'}

    def get_items(self, context: bpy.types.Context):
        p_items = []
        for k, v in bpy.data.images.items():
            p_items.append((k, k, ""))

        s_id = "ZUV_OT_SetTextureSizePreset_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])

        if p_was_items != p_items:
            bpy.app.driver_namespace[s_id] = p_items

        return bpy.app.driver_namespace.get(s_id, [])

    image_name: bpy.props.EnumProperty(
        name='Image Name',
        description='Source image name, which will be used for texture size',
        items=get_items
    )

    def get_image_size(self):
        p_image = bpy.data.images.get(self.image_name, None)
        if p_image:
            return p_image.size
        return (0, 0)

    image_size: bpy.props.IntVectorProperty(
        name='Image Size',
        description='Source image width and height',
        get=get_image_size,
        size=2
    )

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @classmethod
    def getActiveImage(cls, context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image is not None:
            return p_image

        if hasattr(context, 'area') and context.area is not None and context.area.type != 'IMAGE_EDITOR':
            if context.active_object is not None:
                p_act_mat = context.active_object.active_material
                if p_act_mat is not None:
                    if p_act_mat.use_nodes:
                        # Priority for Base Color Texture
                        try:
                            principled = next(n for n in p_act_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                            base_color = principled.inputs['Base Color']
                            link = base_color.links[0]
                            link_node = link.from_node
                            return link_node.image
                        except Exception:
                            pass

        return None

    @classmethod
    def draw_image_size_preset(
            cls, s_data_path: str, context: bpy.types.Context, layout: bpy.types.UILayout,
            s_import_data_path='', b_alert_accent=True, use_property_split=False):
        from ZenUV.utils.adv_generic_ui_list import _get_context_attr

        s_instance, s_attr = s_data_path.rsplit('.', 1)
        p_instance = _get_context_attr(context, s_instance)

        row = layout.row(align=True)

        b_has_texture_size_mismatch = cls.has_image_size_mismatch(s_data_path, context)
        if b_alert_accent:
            row.alert = b_has_texture_size_mismatch
        if not use_property_split:
            row.label(text=ZuvLabels.PREF_TD_TEXTURE_SIZE_LABEL + ": ")
        row.use_property_split = use_property_split
        row.prop(p_instance, s_attr, text=ZuvLabels.PREF_TD_TEXTURE_SIZE_LABEL if use_property_split else "")
        r1 = row.row(align=True)
        op = r1.operator(cls.bl_idname, text='', icon="IMPORT")
        op.data_path = s_import_data_path if s_import_data_path else s_data_path

        if p_instance.td_im_size_presets == 'Custom':
            col = layout.column(align=True)
            if b_alert_accent:
                col.alert = b_has_texture_size_mismatch
            module = s_attr.replace('im_size_presets', '').upper()
            col.prop(p_instance, f'{module}TextureSizeX', text="Custom Res X")
            col.prop(p_instance, f'{module}TextureSizeY', text="Custom Res Y")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_image = self.getActiveImage(context)
        if p_image:
            try:
                self.image_name = p_image.name
            except Exception as e:
                Log.error('DETECT IMAGE:', e)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    @classmethod
    def has_image_size_mismatch(cls, data_path: str, context: bpy.types.Context):
        from ZenUV.utils.adv_generic_ui_list import _get_context_attr
        p_image = cls.getActiveImage(context)
        if p_image:
            s_image_preset = _get_context_attr(context, data_path)
            if s_image_preset == 'Custom':
                s_instance, s_attr = data_path.rsplit('.', 1)
                module = s_attr.replace('im_size_presets', '').upper()
                i_width = _get_context_attr(context, f'{s_instance}.{module}TextureSizeX')
                i_height = _get_context_attr(context, f'{s_instance}.{module}TextureSizeY')
            else:
                i_width = int(s_image_preset)
                i_height = i_width

            if i_width != p_image.size[0] or i_height != p_image.size[1]:
                return True
        return False

    def execute(self, context: bpy.types.Context):
        try:
            i_size = self.image_size
            if i_size[0] and i_size[1]:
                from ZenUV.utils.adv_generic_ui_list import _set_context_attr, _get_context_attr

                s_instance, s_attr = self.data_path.rsplit('.', 1)
                p_instance = _get_context_attr(context, s_instance)
                if p_instance:
                    p_prop = p_instance.bl_rna.properties[s_attr]

                    s_image_preset = 'Custom'

                    if i_size[0] == i_size[1]:
                        for it in p_prop.enum_items:
                            if it.name == str(i_size[0]):
                                s_image_preset = it.name
                                break

                    _set_context_attr(context, self.data_path, s_image_preset)
                    if s_image_preset == 'Custom':
                        module = s_attr.replace('im_size_presets', '').upper()
                        _set_context_attr(context, f'{s_instance}.{module}TextureSizeX', i_size[0])
                        _set_context_attr(context, f'{s_instance}.{module}TextureSizeY', i_size[1])

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


operators_classes = (
    ZUV_OT_SmoothBySharp,
    ZUV_OT_SelectSharp,
    ZUV_OT_SelectSeams,
    ZUV_OT_SelectFlipped,
    ZUV_OT_SelectSelfIntersecting,
    ZUV_OT_CorrectSelfIntersecting,
    ZUV_OT_Select_UV_Overlap,
    ZUV_OT_Select_Loop,
    ZUV_OT_Isolate_Island,
    ZUV_OT_MirrorSeams,
    ZUV_OT_SetTextureSizePreset,
    ZUV_OT_Isolate_Part
)

if __name__ == '__main__':
    pass
