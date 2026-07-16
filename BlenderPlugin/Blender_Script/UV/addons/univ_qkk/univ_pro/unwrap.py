# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy
from .. import utypes
from .. import utils
from ..operators import unwrap
from ..preferences import prefs, univ_settings



class UNIV_OT_Unwrap(unwrap.UNIV_OT_Unwrap):

    # noinspection PyTypeHints
    constraints_weight: bpy.props.FloatProperty(name='Constraints Weight', default=1, min=0, soft_max=1, max=10)
    # noinspection PyTypeHints
    unwrap_along: bpy.props.EnumProperty(name='Unwrap Along', default='UV', items=(('UV', 'Both', ''), ('U', 'U', ''), ('V', 'V', '')),
                                         description="Doesnt work properly with disk-shaped topologies, which completely change their structure with default unwrap")


    def draw(self, context):
        if self.unwrap_along == 'UV':
            self.layout.prop(univ_settings(), 'use_texel')

        self.layout.prop(self, 'use_correct_aspect')
        self.layout.prop(self, 'fill_holes')
        self.layout.prop(self, 'mark_seam_inner_island')


        split = self.layout.split(factor=0.35, align=True)
        split.label(text='Unwrap Along')
        row = split.row(align=True)
        row.prop(self, 'unwrap_along', expand=True)

        self.layout.prop(self, 'constraints_weight', slider=True)
        self.layout.prop(self, 'blend_factor', slider=True)
        self.layout.row(align=True).prop(self, 'unwrap', expand=True)

    def invoke(self, context, event):
        if self.bl_idname.startswith('UV'):
            if event.value == 'PRESS':
                self.max_distance = utils.get_max_distance_from_px(prefs().max_pick_distance, context.region.view2d)
                self.mouse_pos = utils.get_mouse_pos(context, event)
            else:
                self.max_distance = None
        return self.execute(context)

    def execute(self, context):
        if self.unwrap_along == 'UV':
            return super().execute(context)

        if self.unwrap == 'MINIMUM_STRETCH':
            self.unwrap = 'ANGLE_BASED'
            self.report({'WARNING'}, 'Organic Mode is not supported in for unwrap along axis')

        self.umeshes = utypes.UMeshes()
        selected_umeshes, unselected_umeshes = self.umeshes.filtered_by_selected_and_visible_uv_by_context()
        self.umeshes = selected_umeshes if selected_umeshes else unselected_umeshes
        if not self.umeshes:
            return self.umeshes.update()

        if not selected_umeshes and self.max_distance is not None and context.area.ui_type == 'UV':
            return self.pick_unwrap_along()
        else:
            if not selected_umeshes:
                self.report({'WARNING'}, 'Not found selected uv')
                return {'CANCELLED'}


            self.unwrap_selected_along()
            return self.umeshes.update()


    def unwrap_selected_along(self):
        for umesh in self.umeshes:
            uv = umesh.uv
            sync = umesh.sync
            get_face_select = utils.face_select_get_func(umesh)

            safety = False
            if sync and umesh.total_face_sel:
                if utils.USE_GENERIC_UV_SYNC:
                    if not umesh.sync_valid:
                        safety = True
                else:
                    safety = True

            if safety or self.umeshes.elem_mode in ('FACE', 'ISLAND'):
                for isl in utypes.AdvIslands.calc_extended_with_mark_seam(umesh):
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
                                        crn.tag = any(get_face_select(l_crn.face)
                                                  for l_crn in utils.linked_crn_to_vert_pair_with_seam(crn, uv, sync))

                    with utils.uv_parametrizer.unwrap_time_report(self.report):
                        failed = utils.uv_parametrizer.unwrap_isl_by_tag(isl,
                                                                     unwrap_along=self.unwrap_along,
                                                                     use_abf=self.unwrap == 'ANGLE_BASED',
                                                                     topology_from_uvs=self.mark_seam_inner_island,
                                                                     blend_factor=self.blend_factor,
                                                                     fill_holes=self.fill_holes,
                                                                     constraints_factor=self.constraints_weight*100
                                                                     )
                    if failed:
                        self.report({'WARNING'}, f"It is not possible to unwrap {failed!r} islands. "
                                                 f"Try again by setting at least one pin or by partially selecting the island.")
            else:
                get_vert_select = utils.vert_select_get_func(umesh)
                get_edge_select = utils.edge_select_get_func(umesh)
                for isl in utypes.AdvIslands.calc_extended_by_context_with_mark_seam(umesh):
                    if isl.is_full_face_selected():
                        # Tag for unwrap
                        uv = isl.umesh.uv
                        for crn in isl.corners_iter():
                            crn.tag = not crn[uv].pin_uv
                    else:
                        if umesh.elem_mode == 'EDGE' and sync:
                            for f in isl:
                                if get_face_select(f):
                                    for crn in f.loops:
                                        crn.tag = not crn[uv].pin_uv
                                else:
                                    for crn in f.loops:
                                        if crn[uv].pin_uv:
                                            crn.tag = False
                                        else:
                                            crn.tag = get_edge_select(crn) or get_edge_select(crn.link_loop_prev)
                        else:
                            for crn in isl.corners_iter():
                                crn.tag = not crn[uv].pin_uv and get_vert_select(crn)

                    with utils.uv_parametrizer.unwrap_time_report(self.report):
                        failed = utils.uv_parametrizer.unwrap_isl_by_tag(isl,
                                                                     unwrap_along=self.unwrap_along,
                                                                     use_abf=self.unwrap == 'ANGLE_BASED',
                                                                     topology_from_uvs=self.mark_seam_inner_island,
                                                                     blend_factor=self.blend_factor,
                                                                     fill_holes=self.fill_holes,
                                                                     constraints_factor=self.constraints_weight*100
                                                                     )
                    if failed:
                        self.report({'WARNING'}, f"It is not possible to unwrap {failed!r} islands. "
                                                 f"Try again by setting at least one pin or by partially selecting the island.")



    def pick_unwrap_along(self):
        hit = utypes.IslandHit(self.mouse_pos, self.max_distance)
        for umesh in self.umeshes:
            for isl in utypes.AdvIslands.calc_visible_with_mark_seam(umesh):
                hit.find_nearest_island(isl)

        if not hit or (self.max_distance < hit.min_dist):
            self.report({'WARNING'}, 'Island not found within a given radius')
            return {'CANCELLED'}

        isl = hit.island

        # unique_number_for_multiply = hash(isl[0])  # multiplayer
        # self.multiply_relax(unique_number_for_multiply, unwrap_kwargs)

        isl.umesh.value = isl.umesh.check_uniform_scale(report=self.report)
        isl.umesh.aspect = utils.get_aspect_ratio() if self.use_correct_aspect else 1.0
        isl.apply_aspect_ratio()

        # Tag for unwrap
        uv = isl.umesh.uv
        for crn in isl.corners_iter():
            crn.tag = not crn[uv].pin_uv

        with utils.uv_parametrizer.unwrap_time_report(self.report):
            failed = utils.uv_parametrizer.unwrap_isl_by_tag(isl,
                                                         unwrap_along=self.unwrap_along,
                                                         use_abf=self.unwrap == 'ANGLE_BASED',
                                                         topology_from_uvs=self.mark_seam_inner_island,
                                                         blend_factor=self.blend_factor,
                                                         fill_holes=self.fill_holes,
                                                         constraints_factor=self.constraints_weight*100
                                                         )
        if failed:
            self.report({'WARNING'}, f"It is not possible to unwrap {failed!r} islands. "
                                     f"Try again by setting at least one pin or by partially selecting the island.")
        isl.reset_aspect_ratio()
        isl.umesh.update()
        return {'FINISHED'}


    def pick_unwrap_by_constraints(self, isl):
        isl.apply_aspect_ratio()
        islands = utypes.AdvIslands([isl], isl.umesh)
        islands.indexing()

        if self.mark_seam_inner_island:
            isl.mark_seam(additional=True)
        else:
            isl.mark_seam_by_index(additional=True)

        uv = isl.umesh.uv
        for crn in isl.corners_iter():
            crn.tag = not crn[uv].pin_uv

        with utils.uv_parametrizer.unwrap_time_report(self.report):
            failed = utils.uv_parametrizer.unwrap_isl_by_tag(isl,
                                                         unwrap_along=self.unwrap_along,
                                                         use_abf=self.unwrap == 'ANGLE_BASED',
                                                         topology_from_uvs=self.mark_seam_inner_island,
                                                         blend_factor=self.blend_factor,
                                                         fill_holes=self.fill_holes,
                                                         constraints_factor=self.constraints_weight*100
                                                         )

        if failed:
            self.report({'WARNING'}, f"It is not possible to unwrap {failed!r} islands. "
                                     f"Try again by setting at least one pin or by partially selecting the island.")
        isl.reset_aspect_ratio()
        utils.set_global_texel(isl)
        isl.umesh.update()
        return {'FINISHED'}