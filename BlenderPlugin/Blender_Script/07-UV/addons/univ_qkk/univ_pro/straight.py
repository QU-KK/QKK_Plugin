# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .. import utils
from .. import utypes


class UNIV_OT_Straight(bpy.types.Operator):
    bl_idname = "uv.univ_straight"
    bl_label = "Straight"
    bl_description = "Straighten selected edge-chain and relax the rest of the UV Island."
    bl_options = {'REGISTER', 'UNDO'}

    # noinspection PyTypeHints
    use_correct_aspect: bpy.props.BoolProperty(name='Correct Aspect', default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        from ..preferences import univ_settings
        self.layout.prop(univ_settings(), 'use_texel')
        self.layout.prop(self, 'use_correct_aspect')

    def execute(self, context):
        from . import mark
        assert (context.area.ui_type == 'UV')
        failed_total = 0

        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False
        if self.use_correct_aspect:
            umeshes.calc_aspect_ratio(from_mesh=False)

        if umeshes.elem_mode in ('VERT', 'EDGE'):
            umeshes.filter_by_selected_uv_edges()
            islands_calc_type = utypes.Islands.calc_visible
        else:
            umeshes.filter_by_selected_uv_faces()
            islands_calc_type = utypes.Islands.calc_extended

        for umesh in umeshes:
            islands = islands_calc_type(umesh)
            for isl in islands:
                to_segmenting_corners = self.get_to_segmenting_corners(isl)
                if not to_segmenting_corners:
                    continue

                umesh.update_tag = True
                isl.apply_aspect_ratio()
                for seg_with_circle in utypes.Segments.from_corners(to_segmenting_corners, umesh):
                    # TODO: Check is_circular with radial linked loop with seam check.
                    #  This is necessary to avoid squashing when segment might be circular, but there are also randomly selected non-circle segments.
                    if umeshes.elem_mode not in ('VERT', 'EDGE') and seg_with_circle.is_circular:
                        segments = seg_with_circle.break_by_cardinal_dir()
                    else:
                        segments = [seg_with_circle]

                    for seg in segments:
                        # TODO: Add Segment.is_vertical_weighted
                        x, y = (seg.end_co - seg.start_co)
                        is_vertical =  abs(x) <= abs(y)
                        corners = seg.get_corners_for_marking()
                        mark.UNIV_OT_Constraint.set_constraints(umesh, corners, is_vertical)
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
                    failed_total += utils.uv_parametrizer.unwrap_isl_by_tag(isl, unwrap_along="UV")

                isl.reset_aspect_ratio()
                utils.set_global_texel(isl)

        umeshes.update(info="Loops not found")
        return {'FINISHED'}

    @staticmethod
    def get_to_segmenting_corners(isl) -> list:
        umesh = isl.umesh
        is_boundary = utils.is_boundary_func(umesh)
        get_edge_select = utils.edge_select_get_func(umesh)
        get_face_select = utils.face_select_get_func(umesh)

        to_segmenting_corners = []
        if umesh.elem_mode in ('VERT', 'EDGE'):
            for crn in isl.corners_iter():
                if get_edge_select(crn):
                    if is_boundary(crn):
                        to_segmenting_corners.append(crn)
                    else:
                        pair_face = crn.link_loop_radial_prev.face
                        has_two_selected_faces = get_face_select(crn.face) and get_face_select(pair_face)
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

