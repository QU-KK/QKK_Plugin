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
from mathutils import Vector
from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils.transform import UvTransformUtils
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    select_by_context,
    bpy_deselect_by_context
)
from ZenUV.utils.mark_utils import MarkStateManager
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.ops.zen_unwrap.props import ZenUnwrapProps


class UC_Lables:

    OT_UWRP_CONSTR_L = 'Unwrap constraint'
    OT_UWRP_CONSTR_D = 'Unwrap constraint'

    PREF_UWRP_CONSTR_URP_METHOD_L = 'Method'
    PREF_UWRP_CONSTR_URP_METHOD_D = 'Unwrapping method'

    # Enums prop METHOD
    ENUM_UWRP_CONSTR_URP_METHOD_ANGL_BAS_L = 'Angle Based'
    ENUM_UWRP_CONSTR_URP_METHOD_ANGL_BAS_D = 'Angle Based'
    ENUM_UWRP_CONSTR_URP_METHOD_CONFORM_L = 'Conformal'
    ENUM_UWRP_CONSTR_URP_METHOD_CONFORM_D = 'Conformal'

    ENUM_UWRP_CONSTR_INFLUENCE_MODE_L = 'Mode'
    ENUM_UWRP_CONSTR_INFLUENCE_MODE_D = 'Affect Islands or selected Faces'
    ENUM_UWRP_CONSTR_INFLUENCE_MODE_ISL_L = 'Islands'
    ENUM_UWRP_CONSTR_INFLUENCE_MODE_FACE_L = 'Faces'

    PREF_UWRP_CONSTR_CONSTR_METHOD_L = 'Method'
    PREF_UWRP_CONSTR_CONSTR_METHOD_D = 'Constraint method'

    # Enum Constraint method
    ENUM_UWRP_CONSTR_CONSTR_METHOD_FULL_L = 'Full Unwrap'
    ENUM_UWRP_CONSTR_CONSTR_METHOD_FULL_D = 'Unwrap Island, but keep in init bounding box limits'

    ENUM_UWRP_CONSTR_CONSTR_METHOD_AXIS_L = 'Along Axis'
    ENUM_UWRP_CONSTR_CONSTR_METHOD_AXIS_D = 'Unwrap Island while keeping U or V coordinate'

    PREF_UWRP_CONSTR_FULL_URP_L = 'Full Unwrap'
    PREF_UWRP_CONSTR_FULL_URP_D = 'Unwrap Island, but keep in init bounding box limits'

    PREF_UWRP_CONSTR_FILL_H_L = 'Fill Holes'
    PREF_UWRP_CONSTR_FILL_H_D = 'Virtual fill holes in meshes before unwrapping'

    PREF_UWRP_CONSTR_CORR_ASP_L = 'Correct Aspect'
    PREF_UWRP_CONSTR_CORR_ASP_D = 'Map UVs taking image aspect ratio into account'

    PREF_UWRP_CONSTR_USE_SUBS_L = 'Use Subsurf Modifier'
    PREF_UWRP_CONSTR_USE_SUBS_D = 'Map UVs taking vertex position after subsurf into account'

    PREF_UWRP_CONSTR_AXIS_L = 'Axis'
    PREF_UWRP_CONSTR_AXIS_D = 'Active Axis'

    # Enum prop AXIS
    ENUM_UWRP_CONSTR_AXIS_MIN_L = 'Min'
    ENUM_UWRP_CONSTR_AXIS_MIN_D = 'The minimum length axis is automatically determined'

    ENUM_UWRP_CONSTR_AXIS_MAX_L = 'Max'
    ENUM_UWRP_CONSTR_AXIS_MAX_D = 'The maximum length axis is automatically determined'

    ENUM_UWRP_CONSTR_AXIS_U_L = 'U'
    ENUM_UWRP_CONSTR_AXIS_U_D = 'U axis'

    ENUM_UWRP_CONSTR_AXIS_V_L = 'V'
    ENUM_UWRP_CONSTR_AXIS_V_D = 'V axis'

    # Draw Labels
    LAB_UWRP_CONSTR_AXIS_01 = 'Fit Axis:'
    LAB_UWRP_CONSTR_AXIS_02 = 'Axis'
    LAB_UWRP_CONSTR_ADV = 'Unwrap Options:'
    PROP_UWRP_CONSTR_CURRENT_AXIS = "Current Axis"
    LAB_UWRP_CONSTR_OP_BOX_L = 'Constraint Options:'
    LAB_UWRP_CONSTR_NONUNIFORM_L = '  Not uniform'


class UC_IslandState:

    def __init__(
        self,
        bm: bmesh.types.BMesh,
        island: list,
        uv_layer: bmesh.types.BMLayerItem,
        influence: str
    ) -> None:

        self.uv_layer: bmesh.types.BMLayerItem = uv_layer
        self.bbox: BoundingBox2d = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)
        self.p_edge: list = self._collect_p_edges(bm, island, influence)

        self.reserved_pins: list = self._collect_reserved_pins(island)
        self.uv_storage: dict = self._store_uvs(island)
        self.i_loops_idxs: list = [lp.index for f in island for lp in f.loops]

        self._pin_edges_set(bm, self.uv_layer, self.i_loops_idxs, action=True)

    def _collect_reserved_pins(self, island):
        loops = [lp[self.uv_layer] for f in island for lp in f.loops]
        pins_state = [lp.pin_uv for lp in loops]
        for lp in loops:
            lp.pin_uv = False
        return pins_state

    def _restore_reserved_pins(self, island):
        if True in self.reserved_pins:
            loops = [lp[self.uv_layer] for f in island for lp in f.loops]
            for loop, state in zip(loops, self.reserved_pins):
                loop.pin_uv = state

    def _store_uvs(self, island):
        return {f.index: [lp[self.uv_layer].uv.copy() for lp in f.loops] for f in island}

    def _collect_p_edges_fast(self, island):
        edges = {}
        bound_edges = island_util.get_uv_bound_edges_indexes(island, self.uv_layer)
        for axis in (Vector((1.0, 0.0)), Vector((0.0, 1.0))):
            edges.update(
                {
                    axis.angle(loop.link_loop_next[self.uv_layer].uv - loop[self.uv_layer].uv): loop.edge.index
                    for face in island
                    for loop in face.loops
                    if loop.edge.index not in bound_edges
                }
            )

        return edges[min(edges.keys())]

    def _collect_p_edges(self, bm, island, influence) -> list:
        if len(island) == 1:
            influence = 'SELECTION'
        if influence == 'SELECTION':
            border_edges = island_util.get_bound_edges_idxs_from_selected_faces(island)
        else:
            border_edges = set(island_util.get_uv_bound_edges_indexes(island, self.uv_layer))
        in_edges_idxs = {e.index for f in island for e in f.edges}.difference(border_edges)
        if not in_edges_idxs:
            e_loops = [lp for i in border_edges for lp in bm.edges[i].link_loops]
        else:
            e_loops = [lp for i in in_edges_idxs for lp in bm.edges[i].link_loops]

        loops = {
                loop: min(
                    (
                        Vector((1.0, 0.0)).angle(loop.link_loop_next[self.uv_layer].uv - loop[self.uv_layer].uv, 3.14),
                        Vector((0.0, 1.0)).angle(loop.link_loop_next[self.uv_layer].uv - loop[self.uv_layer].uv, 3.14)
                    )
                ) for loop in e_loops
            }
        min_angle = min(loops.values())
        return sorted([lp for lp, angle in loops.items() if angle == min_angle], key=self._sort_by_index)[0].edge.index

    def _sort_by_index(self, f):
        return f.index

    def restore_uv(self, bm, uv_layer, axis, b_is_axis_constraint_mode):
        self.uv_layer = uv_layer
        island = [bm.faces[i] for i in self.uv_storage.keys()]
        self._pin_edges_set(bm, self.uv_layer, self.i_loops_idxs, action=False)

        self._restore_reserved_pins(island)

        if b_is_axis_constraint_mode:

            UvTransformUtils.fit_island(
                island=island,
                uv_layer=uv_layer,
                fit_bbox=self.bbox,
                fit_axis_name=self.reverse_axis(axis),
                single_axis=True,
                keep_proportion=True,
                pivot=BoundingBox2d(islands=[island, ], uv_layer=uv_layer).center
            )
        else:
            UvTransformUtils.fit_island(
                island,
                uv_layer,
                self.bbox,
                axis,
                single_axis=False,
                keep_proportion=True,
                pivot=self.bbox.center
            )

    # def _apply_constraint(self, bm, axis):
    #     axis = {
    #         'V': 'V',
    #         'U': 'U',
    #         'MIN': self.bbox.get_shortest_axis_name(),
    #         'MAX': self.bbox.get_longest_axis_name()
    #     }[axis]
    #     if axis == 'V':
    #         for f_index, uvs in self.uv_storage.items():
    #             for loop, co in zip([lp[self.uv_layer] for lp in bm.faces[f_index].loops], [i.x for i in uvs]):
    #                 loop.uv.x = co
    #     elif axis == 'U':
    #         for f_index, uvs in self.uv_storage.items():
    #             for loop, co in zip([lp[self.uv_layer] for lp in bm.faces[f_index].loops], [i.y for i in uvs]):
    #                 loop.uv.y = co
    #     else:
    #         pass

    def get_current_axis(self, axis):
        return {
            'V': 'V',
            'U': 'U',
            'MIN': self.bbox.get_shortest_axis_name(),
            'MAX': self.bbox.get_longest_axis_name()
        }[axis]

    def reverse_axis(self, axis):
        return {
            'V': 'U',
            'U': 'V',
            'MIN': self.bbox.get_longest_axis_name(),
            'MAX': self.bbox.get_shortest_axis_name()
        }[axis]

    def _pin_edges_set(self, bm, uv_layer, island_loops_idxs, action):
        for lp in [lp for lp in bm.edges[self.p_edge].link_loops if lp.index in island_loops_idxs]:
            lp[uv_layer].pin_uv = action
            lp.link_loop_next[uv_layer].pin_uv = action


class UC_ObjState:

    def __init__(
        self,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        obj: bpy.types.Object,
        uv_layer: bmesh.types.BMLayerItem,
        islands: list,
        influence: str
    ) -> None:

        self.obj: bpy.types.Object = obj
        self.uv_layer: bmesh.types.BMLayerItem = uv_layer
        self.bm: bmesh.types.BMesh = bm

        self.islands: list = self._collect_islands(bm, islands, uv_layer, influence)
        self.selection: list = self._store_selection(context, bm, uv_layer)

        self._select_islands(context, bm, islands)

    def _is_no_sync(self, context):
        return context.area.type == "IMAGE_EDITOR" and not context.scene.tool_settings.use_uv_select_sync

    def _store_selection(self, context, bm, uv_layer):
        if self._is_no_sync(context):
            if context.scene.tool_settings.uv_select_mode == "EDGE":
                return [lp[uv_layer].select_edge for f in bm.faces for lp in f.loops]
            else:
                return [lp[uv_layer].select for f in bm.faces for lp in f.loops]
        else:
            return [f.index for f in bm.faces if f.select]

    def _select_islands(self, context, bm, islands):
        select_by_context(context, bm, islands, state=True)

    def _collect_islands(self, bm, islands, uv_layer, influence):
        return [UC_IslandState(bm, i, uv_layer, influence) for i in islands]

    def restore_selection(self, context, bm, uv_layer):
        if self._is_no_sync(context):
            loops = [lp[uv_layer] for f in bm.faces for lp in f.loops]
            if ZenPolls.version_since_3_2_0:
                for loop, state in zip(loops, self.selection):
                    loop.select = state
                    loop.select_edge = state
            else:
                for loop, state in zip(loops, self.selection):
                    loop.select = state
        else:
            select_by_context(context, bm, [[bm.faces[i] for i in self.selection], ], state=True)
        bm.select_flush_mode()


class ZUV_OT_UnwrapConstraint(bpy.types.Operator):

    bl_idname = "uv.zenuv_unwrap_constraint"
    bl_label = UC_Lables.OT_UWRP_CONSTR_L
    bl_description = UC_Lables.OT_UWRP_CONSTR_D
    bl_options = {'REGISTER', 'UNDO'}

    influence_mode: bpy.props.EnumProperty(
        name=UC_Lables.ENUM_UWRP_CONSTR_INFLUENCE_MODE_L,
        description=UC_Lables.ENUM_UWRP_CONSTR_INFLUENCE_MODE_D,
        items=[
            ("ISLAND", UC_Lables.ENUM_UWRP_CONSTR_INFLUENCE_MODE_ISL_L, ""),
            ("SELECTION", UC_Lables.ENUM_UWRP_CONSTR_INFLUENCE_MODE_FACE_L, "")
        ],
        default="ISLAND"
    )
    axis: bpy.props.EnumProperty(
            name=UC_Lables.PREF_UWRP_CONSTR_AXIS_L,
            description=UC_Lables.PREF_UWRP_CONSTR_AXIS_D,
            items=[
                ('U', UC_Lables.ENUM_UWRP_CONSTR_AXIS_U_L, UC_Lables.ENUM_UWRP_CONSTR_AXIS_U_D),
                ('V', UC_Lables.ENUM_UWRP_CONSTR_AXIS_V_L, UC_Lables.ENUM_UWRP_CONSTR_AXIS_V_D),
                ('MIN', UC_Lables.ENUM_UWRP_CONSTR_AXIS_MIN_L, UC_Lables.ENUM_UWRP_CONSTR_AXIS_MIN_D),
                ('MAX', UC_Lables.ENUM_UWRP_CONSTR_AXIS_MAX_L, UC_Lables.ENUM_UWRP_CONSTR_AXIS_MAX_D),
            ],
            default='MIN'
        )
    constraint_method: bpy.props.EnumProperty(
        name=UC_Lables.PREF_UWRP_CONSTR_CONSTR_METHOD_L,
        description=UC_Lables.PREF_UWRP_CONSTR_CONSTR_METHOD_D,
        items=[
            ('FULL', UC_Lables.ENUM_UWRP_CONSTR_CONSTR_METHOD_FULL_L, UC_Lables.ENUM_UWRP_CONSTR_CONSTR_METHOD_FULL_D),
            ('AXIS', UC_Lables.ENUM_UWRP_CONSTR_CONSTR_METHOD_AXIS_L, UC_Lables.ENUM_UWRP_CONSTR_CONSTR_METHOD_AXIS_L)
        ],
        default='FULL'
    )
    urp_method: bpy.props.EnumProperty(
        name=UC_Lables.PREF_UWRP_CONSTR_URP_METHOD_L,
        description=UC_Lables.PREF_UWRP_CONSTR_URP_METHOD_D,
        items=ZenUnwrapProps.UNWRAP_METHOD_ITEMS,
        default='ANGLE_BASED'
    )
    fill_holes: bpy.props.BoolProperty(
        name=UC_Lables.PREF_UWRP_CONSTR_FILL_H_L,
        description=UC_Lables.PREF_UWRP_CONSTR_FILL_H_D,
        default=True
    )
    correct_aspect: bpy.props.BoolProperty(
        name=UC_Lables.PREF_UWRP_CONSTR_CORR_ASP_L,
        description=UC_Lables.PREF_UWRP_CONSTR_CORR_ASP_D,
        default=True
    )
    use_subsurf_data: bpy.props.BoolProperty(
        name=UC_Lables.PREF_UWRP_CONSTR_USE_SUBS_L,
        description=UC_Lables.PREF_UWRP_CONSTR_USE_SUBS_D,
        default=False
    )
    mark: bpy.props.BoolProperty(name='Mark', description='Mark Seam or Sharp', default=False)
    mark_seams: bpy.props.BoolProperty(name="Mark Seams", default=True, description="Mark seam in case Mark Borders is on")
    mark_sharp: bpy.props.BoolProperty(name="Mark Sharp", default=False, description="Mark sharp in case Mark Borders is on")

    current_axis: bpy.props.StringProperty(
        name=UC_Lables.PROP_UWRP_CONSTR_CURRENT_AXIS,
        default='',
        options={'HIDDEN'}
    )

    @classmethod
    def poll(cls, context):
        is_sync_mode = context.area.type == "VIEW_3D" or context.area.type == "IMAGE_EDITOR" and context.scene.tool_settings.use_uv_select_sync
        return context.mode == "EDIT_MESH" and is_sync_mode

    def draw_mark_section(self, layout, uv_sync):
        addon_prefs = get_prefs()
        mark_box = layout.box()
        mark_box.enabled = self.influence_mode == 'SELECTION' and uv_sync
        s_mark_settings = 'Mark Settings'

        s_mark_settings += ' (Global Mode)' if addon_prefs.useGlobalMarkSettings else ' (Local Mode)'
        mark_box.label(text=s_mark_settings)

        row = mark_box.row(align=True)
        row.prop(self, "mark")
        sub_row = row.row(align=True)
        sub_row.enabled = self.mark
        if not addon_prefs.useGlobalMarkSettings:
            sub_row.prop(self, "mark_seams")
            sub_row.prop(self, "mark_sharp")
        else:
            sub_row.enabled = False
            sub_row.prop(addon_prefs, "markSeamEdges")
            sub_row.prop(addon_prefs, "markSharpEdges")

    def draw(self, context):
        _lt = self.layout
        uv_sync = context.scene.tool_settings.use_uv_select_sync
        row = _lt.row()
        row.enabled = uv_sync
        row.prop(self, "influence_mode")
        op_box = _lt.box()
        op_box.label(text=UC_Lables.LAB_UWRP_CONSTR_OP_BOX_L)
        op_box.prop(self, 'constraint_method')
        row = op_box.row(align=True)
        row.label(
            text=UC_Lables.LAB_UWRP_CONSTR_AXIS_01 if self.constraint_method == 'FULL'
            else UC_Lables.LAB_UWRP_CONSTR_AXIS_02
        )
        row.prop(self, "axis", expand=True)
        op_box.label(text=UC_Lables.PROP_UWRP_CONSTR_CURRENT_AXIS + ': ' + self.current_axis)

        self.draw_mark_section(_lt, uv_sync)

        box = _lt.box()
        box.use_property_split = True
        box.label(text=UC_Lables.LAB_UWRP_CONSTR_ADV)
        box.prop(self, "urp_method")
        box.prop(self, "fill_holes")
        box.prop(self, "correct_aspect")
        box.prop(self, "use_subsurf_data")

    def execute(self, context):
        from ZenUV.ui.gizmo_draw import UvSelectionStorage
        b_is_uv_sync: bool = context.scene.tool_settings.use_uv_select_sync
        if b_is_uv_sync is False:
            self.report({'WARNING'}, "Only when UV Sync Selection On")
            return {'CANCELLED'}

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        b_is_axis_constraint = self.constraint_method == 'AXIS'

        p_stored_objs = UvSelectionStorage.store_selection(objs, not b_is_uv_sync)

        # Collect phase
        uc_objs_collector = []
        for obj, data in p_stored_objs.items():
            bm = data[0]
            uv_layer = data[1]

            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            if self.influence_mode == 'ISLAND' or not b_is_uv_sync:
                islands = island_util.get_island(context, bm, uv_layer)
            else:
                islands = island_util.get_islands_selected_only(bm, [f for f in bm.faces if f.select])

            if len(islands):
                uc_objs_collector.append(
                    UC_ObjState(
                        context,
                        bm,
                        obj,
                        uv_layer=uv_layer,
                        islands=islands,
                        influence=self.influence_mode
                    )
                )

        # Unwrap phase
        bpy.ops.uv.unwrap(
            method=self.urp_method,
            fill_holes=self.fill_holes,
            correct_aspect=self.correct_aspect,
            use_subsurf_data=self.use_subsurf_data,
            )

        uc_obj: UC_ObjState = None

        for uc_obj in uc_objs_collector:
            bm = uc_obj.bm
            uv_layer = uc_obj.uv_layer

            island: UC_IslandState = None

            for island in uc_obj.islands:
                island.restore_uv(bm, uv_layer, self.axis, b_is_axis_constraint)
                if len([i for ob in uc_objs_collector for i in ob.islands]) <= 1:
                    self.current_axis = island.get_current_axis(self.axis)
                else:
                    if self.axis in {'U', 'V'}:
                        self.current_axis = self.axis
                    else:
                        self.current_axis = UC_Lables.LAB_UWRP_CONSTR_NONUNIFORM_L

        # Seam mark phase
        if self.influence_mode == 'SELECTION' and self.mark and b_is_uv_sync:
            from ZenUV.utils.mark_utils import MarkFactory

            b_mSeam, b_mSharp = MarkStateManager(
                context
                ).get_state_from_generic_operator(self.mark_seams, self.mark_sharp)

            p_objs = [MarkFactory.create_mark_state_object_from_bm(uc_obj.obj, uc_obj.bm) for uc_obj in uc_objs_collector]

            MarkFactory.mark_edges(
                p_objs,
                b_mSeam,
                b_mSharp,
                is_switch=False,
                is_assign=True,
                is_remove_inside=True,
                is_silent_mode=True
            )

        # Restore selection
        bpy_deselect_by_context(context)

        UvSelectionStorage.restore_selection(context, not b_is_uv_sync, p_stored_objs)

        return {'FINISHED'}


system_classes = (
    ZUV_OT_UnwrapConstraint,
)


def register_uwrp_constraint():
    RegisterUtils.register(system_classes)


def unregister_uwrp_constraint():
    RegisterUtils.unregister(system_classes)


if __name__ == "__main__":
    pass
