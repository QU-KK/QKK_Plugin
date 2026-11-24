# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later


import bpy
from .. import utypes
from .. import utils
from ..operators import unwrap
from ..preferences import prefs


# noinspection PyTypeHints
class UNIV_OT_Unwrap(unwrap.UNIV_OT_Unwrap):
    # fmt: off
    constr_weight: bpy.props.FloatProperty(name='Constraints Factor', default=1, min=0, soft_max=1, max=10)
    constr_correction_weight: bpy.props.FloatProperty(name='Non-Constrained Face Bloating Factor', default=4, min=0.5, soft_min=1, soft_max=8, max=100)
    constr_edge_weight: bpy.props.FloatProperty(name='Constraints Edge-Length Preserve Factor', default=0.1, min=0.0, soft_max=2, max=100)
    constr_d_edge_factor: bpy.props.FloatProperty(name='Diagonal Constraints Factor', default=0.1, min=0.02, soft_min=0.05, soft_max=1, max=100)
    unwrap_along: bpy.props.EnumProperty(name='Unwrap Along', default='UV', items=(('UV', 'Both', ''), ('U', 'U', ''), ('V', 'V', '')),
                                         description="Doesnt work properly with disk-shaped topologies, which completely change their structure with default unwrap")
    # fmt: on

    def draw(self, context):
        if self.unwrap_along == "UV":
            self.layout.prop(prefs(), "use_texel")

        self.layout.prop(self, "use_correct_aspect")
        self.layout.prop(self, "fill_holes")
        self.layout.prop(self, "mark_seams_only_with_other_islands")

        split = self.layout.split(factor=0.35, align=True)
        split.label(text="Unwrap Along")
        row = split.row(align=True)
        row.prop(self, "unwrap_along", expand=True)

        self.layout.prop(self, "constr_weight", slider=True)
        if self.unwrap_along == "UV":
            self.layout.prop(self, "constr_correction_weight", slider=True)
        self.layout.prop(self, "constr_edge_weight", slider=True)
        self.layout.prop(self, "constr_d_edge_factor", slider=True)

        self.layout.separator()

        self.layout.prop(self, "blend_factor", slider=True)
        self.layout.row(align=True).prop(self, "unwrap", expand=True)

    def invoke(self, context, event):
        self.store_mouse_pose_on_uv_and_max_distance_if_allowed(event)
        return self.execute(context)

    def execute(self, context):
        if self.unwrap_along == "UV":
            return super().execute(context)

        if self.unwrap == "MINIMUM_STRETCH":
            self.unwrap = "ANGLE_BASED"
            self.report(
                {"WARNING"}, "Organic Mode is not supported in for unwrap along axis"
            )

        umeshes = utypes.UMeshes()
        selected_umeshes, unselected_umeshes = umeshes.filtered_by_selected_and_visible_uv_by_context()
        umeshes = selected_umeshes if selected_umeshes else unselected_umeshes
        if not umeshes:
            return umeshes.update()

        if (
            not selected_umeshes
            and self.max_distance is not None
            and context.area.ui_type == "UV"
        ):
            return self.pick_unwrap_along(umeshes)
        else:
            if not selected_umeshes:
                self.report({"WARNING"}, "Not found selected uv")
                return {"CANCELLED"}

            self.unwrap_selected_along(umeshes)
            return umeshes.update()

    def unwrap_selected_along(self, umeshes):
        for umesh in umeshes:
            uv = umesh.uv
            sync = umesh.sync
            get_linked_it = utils.get_linked_crn_iter_fn(umesh)
            get_face_select = utils.face_select_get_func(umesh)

            safety = False
            if sync and umesh.total_face_sel:
                if utils.USE_GENERIC_UV_SYNC:
                    if not umesh.sync_valid:
                        safety = True
                else:
                    safety = True

            if safety or umeshes.elem_mode in ("FACE", "ISLAND"):
                for isl in utypes.Islands.calc_extended(umesh):
                    if isl.is_full_face_selected():
                        # Tag for unwrap
                        uv = isl.umesh.uv
                        for crn in isl.corners_iter():
                            crn.tag = not crn[uv].pin_uv
                    else:
                        for f in isl:
                            if get_face_select(f):
                                for crn in f.loops:
                                    crn.tag = not crn[uv].pin_uv
                            else:
                                for crn in f.loops:
                                    if crn[uv].pin_uv:
                                        crn.tag = False
                                    else:
                                        # TODO: Optimize for shared sticky
                                        crn.tag = any(get_face_select(l_crn.face) for l_crn in get_linked_it(crn))

                    with utils.uv_parametrizer.unwrap_time_report(self.report):
                        failed = utils.uv_parametrizer.unwrap_isl_by_tag(
                            isl,
                            unwrap_along=self.unwrap_along,
                            use_abf=self.unwrap == "ANGLE_BASED",
                            topology_from_uvs=not self.mark_seams_only_with_other_islands,
                            blend_factor=self.blend_factor,
                            fill_holes=self.fill_holes,
                            constraints_factor=self.constr_weight * 100,
                            constr_correction_weight=self.constr_correction_weight,
                            constr_edge_weight=self.constr_edge_weight,
                        )
                    if failed:
                        self.report(
                            {"WARNING"},
                            f"It is not possible to unwrap {failed!r} islands. "
                            f"Try again by setting at least one pin or by partially selecting the island.",
                        )
            else:
                get_vert_select = utils.vert_select_get_func(umesh)
                get_edge_select = utils.edge_select_get_func(umesh)
                for isl in utypes.Islands.calc_extended_by_context(umesh):
                    if isl.is_full_face_selected():
                        # Tag for unwrap
                        uv = isl.umesh.uv
                        for crn in isl.corners_iter():
                            crn.tag = not crn[uv].pin_uv
                    else:
                        if umesh.elem_mode == "EDGE" and sync:
                            for f in isl:
                                if get_face_select(f):
                                    for crn in f.loops:
                                        crn.tag = not crn[uv].pin_uv
                                else:
                                    for crn in f.loops:
                                        if crn[uv].pin_uv:
                                            crn.tag = False
                                        else:
                                            crn.tag = get_edge_select(
                                                crn
                                            ) or get_edge_select(crn.link_loop_prev)
                        else:
                            for crn in isl.corners_iter():
                                crn.tag = not crn[uv].pin_uv and get_vert_select(crn)

                    with utils.uv_parametrizer.unwrap_time_report(self.report):
                        failed = utils.uv_parametrizer.unwrap_isl_by_tag(
                            isl,
                            unwrap_along=self.unwrap_along,
                            use_abf=self.unwrap == "ANGLE_BASED",
                            topology_from_uvs=not self.mark_seams_only_with_other_islands,
                            blend_factor=self.blend_factor,
                            fill_holes=self.fill_holes,
                            constraints_factor=self.constr_weight * 100,
                            constr_correction_weight=self.constr_correction_weight,
                            constr_edge_weight=self.constr_edge_weight,
                        )
                    if failed:
                        self.report(
                            {"WARNING"},
                            f"It is not possible to unwrap {failed!r} islands. "
                            f"Try again by setting at least one pin or by partially selecting the island.",
                        )

    def pick_unwrap_along(self, umeshes: utypes.UMeshes):
        hit = utypes.IslandHit(self.mouse_position, self.max_distance)
        for umesh in umeshes:
            for isl in utypes.Islands.calc_visible(umesh):
                hit.find_nearest_island(isl)

        if not hit or (self.max_distance < hit.min_dist):
            self.report({"WARNING"}, "Island not found within a given radius")
            return {"CANCELLED"}

        isl = hit.island

        # unique_number_for_multiply = hash(isl[0])  # multiplayer
        # self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)
        if self.mark_seams_only_with_other_islands:
            isl.mark_seams_only_with_other_islands()
        else:
            isl.mark_seam(additional=True)

        isl.umesh.value = isl.umesh.check_uniform_scale(report=self.report)
        isl.umesh.aspect = utils.get_aspect_ratio() if self.use_correct_aspect else 1.0
        with isl.temp_aspect():
            # Tag for unwrap
            uv = isl.umesh.uv
            for crn in isl.corners_iter():
                crn.tag = not crn[uv].pin_uv

            with utils.uv_parametrizer.unwrap_time_report(self.report):
                failed = utils.uv_parametrizer.unwrap_isl_by_tag(
                    isl,
                    unwrap_along=self.unwrap_along,
                    use_abf=self.unwrap == "ANGLE_BASED",
                    topology_from_uvs=not self.mark_seams_only_with_other_islands,
                    blend_factor=self.blend_factor,
                    fill_holes=self.fill_holes,
                    constraints_factor=self.constr_weight * 100,
                    constr_correction_weight=self.constr_correction_weight,
                    constr_edge_weight=self.constr_edge_weight,
                    constr_d_edge_factor=self.constr_d_edge_factor,
                )
            if failed:
                self.report(
                    {"WARNING"},
                    f"It is not possible to unwrap {failed!r} islands. "
                    f"Try again by setting at least one pin or by partially selecting the island.",
                )
        isl.umesh.update()
        return {"FINISHED"}

    def pick_unwrap_by_constraints_ex(self, isl: utypes.AdvIsland):
        with isl.temp_aspect():
            if self.mark_seams_only_with_other_islands:
                isl.mark_seams_only_with_other_islands()
            else:
                isl.mark_seam(additional=True)

            uv = isl.umesh.uv
            for crn in isl.corners_iter():
                crn.tag = not crn[uv].pin_uv

            with utils.uv_parametrizer.unwrap_time_report(self.report):
                failed = utils.uv_parametrizer.unwrap_isl_by_tag(
                    isl,
                    unwrap_along=self.unwrap_along,
                    use_abf=self.unwrap == "ANGLE_BASED",
                    topology_from_uvs=not self.mark_seams_only_with_other_islands,
                    blend_factor=self.blend_factor,
                    fill_holes=self.fill_holes,
                    constraints_factor=self.constr_weight * 100,
                    constr_correction_weight=self.constr_correction_weight,
                    constr_edge_weight=self.constr_edge_weight,
                    constr_d_edge_factor=self.constr_d_edge_factor,
                )

            if failed:
                self.report(
                    {"WARNING"},
                    f"It is not possible to unwrap {failed!r} islands. "
                    f"Try again by setting at least one pin or by partially selecting the island.",
                )
        utils.set_global_texel(isl)
        isl.umesh.update()
        return {"FINISHED"}
