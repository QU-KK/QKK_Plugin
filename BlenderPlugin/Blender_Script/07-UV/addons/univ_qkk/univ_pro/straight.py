# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
import math

from .. import utils
from .. import utypes


# noinspection PyTypeHints
class UNIV_OT_Straight(utypes.RayCastAndPick):
    bl_idname = "uv.univ_straight"
    bl_label = "Straight"
    bl_description = "Straighten selected edge-chain and relax the rest of the UV Island."  # fmt: skip
    bl_options = {"REGISTER", "UNDO"}

    # fmt: off
    unwrap_type: bpy.props.EnumProperty(name='Unwrap', default='ANGLE_BASED',
                                   items=(('ANGLE_BASED', 'Hard Surface', ''),
                                          ('CONFORMAL', 'Conformal', '')))
    fill_holes: bpy.props.BoolProperty(name='Fill Holes', default=True)
    use_correct_aspect: bpy.props.BoolProperty(name='Correct Aspect', default=True)

    constr_weight: bpy.props.FloatProperty(name='Constraints Weight', default=1, min=0.1, soft_max=1, max=10)
    constr_correction_weight: bpy.props.FloatProperty(name='Constraints Correction Weight', default=4, min=0.5, soft_min=1, soft_max=8, max=100)
    constr_edge_weight: bpy.props.FloatProperty(name='Constraints Length Weight', default=0.1, min=0.0, soft_max=2, max=100)
    # fmt: on
    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def invoke(self, context, event):
        self.store_mouse_pose_on_uv_and_max_distance_if_allowed(event)
        return self.execute(context)

    def draw(self, context):
        from ..preferences import univ_settings

        self.layout.prop(univ_settings(), "use_texel")
        self.layout.prop(self, "fill_holes")
        self.layout.prop(self, "use_correct_aspect")
        self.layout.separator()
        self.layout.prop(self, "constr_weight", slider=True)
        self.layout.prop(self, "constr_correction_weight", slider=True)
        self.layout.prop(self, "constr_edge_weight", slider=True)
        self.layout.separator()
        self.layout.row(align=True).prop(self, "unwrap_type", expand=True)

    def execute(self, context):

        assert context.area.ui_type == "UV"
        failed_total = 0  # TODO: Add report.

        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False

        if self.use_correct_aspect:
            umeshes.calc_aspect_ratio(from_mesh=False)

        if umeshes.elem_mode in ("VERT", "EDGE"):
            selected, visible = umeshes.filtered_by_selected_and_visible_uv_edges()
            islands_calc_type = utypes.Islands.calc_visible
        else:
            selected, visible = umeshes.filtered_by_selected_and_visible_uv_faces()
            islands_calc_type = utypes.Islands.calc_extended

        umeshes = selected if selected else visible

        if selected:
            for umesh in umeshes:
                islands = islands_calc_type(umesh)

                for isl in islands:
                    to_segmenting_corners = self.get_to_segmenting_corners(isl)
                    if not to_segmenting_corners:
                        continue

                    self.straight_ex(failed_total, isl, to_segmenting_corners)

                    utils.set_global_texel(isl)
        elif self.mouse_position:
            edge_hit = utypes.CrnEdgeHit(self.mouse_position)
            for umesh in umeshes:
                edge_hit.find_nearest_crn_by_visible_faces(umesh)

            if edge_hit:
                umesh = edge_hit.umesh
                isl, faces_set = edge_hit.calc_island_with_seam()
                from . import select

                is_boundary_without_seam_check = utils.is_boundary_func(
                    umesh, with_seam=False
                )

                stack = []
                crn = edge_hit.crn
                pair_crn = crn.link_loop_radial_prev
                if is_boundary_without_seam_check(crn) or pair_crn.face not in faces_set:
                    stack.append(utypes.AdvCorner(crn, umesh, is_pair=False))
                    stack.append(utypes.AdvCorner(crn.link_loop_next, umesh, is_pair=False, invert=True))
                else:
                    stack.append(utypes.AdvCorner(crn, umesh, is_pair=True))
                    stack.append(utypes.AdvCorner(pair_crn, umesh, is_pair=True))

                # TODO: Set constraints type by linked corners.

                grow_included = self.loop_select_by_abs_angle_by_pick(umesh, stack, max_angle=math.radians(25.0))
                segments_corners = []
                for adv_crn in grow_included:
                    orig_crn = adv_crn.orig_crn
                    segments_corners.append(orig_crn)
                    if adv_crn.is_pair:
                        segments_corners.append(orig_crn.link_loop_radial_prev)


                self.straight_ex(failed_total, isl, segments_corners)
                umesh.update_tag = True

        umeshes.update(info="Loops not found")
        return {"FINISHED"}

    def straight_ex(self, failed_total, isl, to_segmenting_corners):
        from . import mark
        umesh = isl.umesh
        umesh.update_tag = True
        with isl.temp_aspect():
            for seg_with_circle in utypes.Segments.from_corners(to_segmenting_corners, umesh):
                # TODO: Check is_circular with radial linked loop with seam check.
                #  This is necessary to avoid squashing when segment might be circular, but there are also randomly selected non-circle segments.
                if seg_with_circle.is_circular:
                    segments = seg_with_circle.break_by_cardinal_dir()
                else:
                    segments = [seg_with_circle]

                for seg in segments:
                    # TODO: Add Segment.is_vertical_weighted
                    x, y = seg.end_co - seg.start_co
                    constraints_type = "HORIZONTAL" if abs(x) > abs(y) else "VERTICAL"
                    corners = seg.get_corners_for_marking()
                    mark.UNIV_OT_MarkConstraints.set_constraints(umesh, corners, constraints_type)
                # TODO: Join segment (if possible).

            # Mark Seam and set tags by pins.
            uv = umesh.uv
            is_boundary = utils.is_boundary_func(umesh)
            for crn in isl.corners_iter():
                if is_boundary(crn):
                    crn.edge.seam = True
                crn.tag = not crn[uv].pin_uv

            # Unwrap.
            with utils.uv_parametrizer.unwrap_time_report(self.report):
                failed_total += utils.uv_parametrizer.unwrap_isl_by_tag(
                    isl,
                    unwrap_along="UV",
                    use_abf=self.unwrap_type == "ANGLE_BASED",
                    constraints_factor=self.constr_weight * 100,
                    constr_edge_weight=self.constr_edge_weight,
                    constr_correction_weight=self.constr_correction_weight,
                    fill_holes=self.fill_holes,
                )

    @staticmethod
    def get_to_segmenting_corners(isl) -> list:
        umesh = isl.umesh
        is_boundary = utils.is_boundary_func(umesh)
        get_edge_select = utils.edge_select_get_func(umesh)
        get_face_select = utils.face_select_get_func(umesh)

        to_segmenting_corners = []
        if umesh.elem_mode in ("VERT", "EDGE"):
            for crn in isl.corners_iter():
                if get_edge_select(crn):
                    if is_boundary(crn):
                        to_segmenting_corners.append(crn)
                    else:
                        pair_face = crn.link_loop_radial_prev.face
                        has_two_selected_faces = get_face_select(
                            crn.face
                        ) and get_face_select(pair_face)
                        if not has_two_selected_faces:
                            to_segmenting_corners.append(crn)
        else:
            for crn in isl.corners_iter():
                if get_face_select(crn.face):
                    if is_boundary(crn):
                        to_segmenting_corners.append(crn)
                    else:
                        pair_face = crn.link_loop_radial_prev.face
                        if not get_face_select(pair_face):
                            to_segmenting_corners.append(crn)
        return to_segmenting_corners

    @classmethod
    def loop_select_by_abs_angle_by_pick(cls, umesh, stack: list[utypes.AdvCorner], max_angle: float):
        grow: list[utypes.AdvCorner] = []
        exclude_edges = set()
        is_boundary = utils.is_boundary_func(umesh, with_seam=False)

        from . import select

        while stack:
            next_stack = []
            for eg in stack:
                left, right, is_cyclic = eg.get_linked_left_right_and_get_cyclic_status(is_boundary)
                linked = left + right

                # Clamp by seams.
                if not eg.orig_crn.edge.seam:
                    if any(adv_crn.edge.seam for adv_crn in linked):
                        continue

                orig_vec = eg.vec.copy()
                eg = eg.copy()
                eg.toggle_dir()

                min_angle_adv_crn = select.UNIV_OT_Select_Loop_Pick_VIEW2D.get_grow_by_angle_crn(
                    eg, linked, max_angle, True, True)
                if min_angle_adv_crn and min_angle_adv_crn not in exclude_edges:
                    exclude_edges.add(min_angle_adv_crn)

                    other_dir = min_angle_adv_crn.copy()
                    other_dir.toggle_dir()
                    other_dir.vec = orig_vec.copy()  # Copy absolute angle.

                    exclude_edges.add(other_dir)
                    next_stack.append(other_dir)

            grow.extend(stack)
            stack = next_stack
        return grow
