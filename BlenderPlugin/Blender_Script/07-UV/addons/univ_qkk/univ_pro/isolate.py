# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .. import utils
from .. import utypes
from ..preferences import prefs


class UNIV_OT_Isolate(utypes.RayCastAndPick):
    bl_idname = "uv.univ_isolate"
    bl_label = "Isolate"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Isolate selected islands."

    def draw(self, context):
        self.layout.prop(prefs(), "isolate_hide_full_unsel_first")

    def invoke(self, context, event):
        self.store_mouse_pose_on_uv_and_max_distance_if_allowed(event)
        return self.execute(context)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            # TODO: Implement removing attrs.
            self.report({"WARNING"}, "Expected edit mode.")
            return {"FINISHED"}

        all_umeshes = utypes.UMeshes(report=self.report)
        all_umeshes.update_tag = False

        selected, visible, hidden = (
            all_umeshes.filtered_by_selected_and_visible_and_hidden_uv_faces()
        )

        if not selected and not visible:
            self.unhide_isolate_hidden_faces_3d(all_umeshes, hidden)
            return {"FINISHED"}

        if selected:
            self.isolate_for_selected(all_umeshes, selected, visible)
        else:  # Unselect Case.
            self.isolated_pick_or_unhide_all(all_umeshes, visible)
        return {"FINISHED"}

    def isolated_pick_or_unhide_all(self, all_umeshes, visible):
        # Isolate by Pick.
        if self.mouse_position:
            hit = utypes.CrnEdgeHit(self.mouse_position, self.max_distance)
            for umesh in visible:
                umesh.sequence = utils.calc_visible_uv_faces(umesh)
                hit.find_nearest_vert_by_visible_faces(
                    umesh, use_faces_from_umesh_seq=True
                )

            if hit:
                adv_isl, faces_set = hit.calc_island_with_seam()
                if len(hit.umesh.sequence) != len(faces_set):
                    to_hide = set(hit.umesh.sequence) - faces_set
                    self.hide_faces_for_isolate(hit.umesh, to_hide)
                    hit.umesh.update_tag = True

                    for umesh in visible:
                        if hit.umesh != umesh:
                            self.hide_faces_for_isolate(umesh, umesh.sequence)
                            umesh.update_tag = True

        if not all_umeshes.update_tag:
            self.unhide_isolate_hidden_faces_uv(all_umeshes)

        # all_umeshes.update(info="Not found to unhide - isolate hidden faces.") # TODO: Check changing local_view and affecting on objects.
        all_umeshes.silent_update()

    def isolate_for_selected(self, all_umeshes, selected, visible):
        sanitized_count = 0
        has_unselected_faces = bool(visible)

        if not has_unselected_faces or not prefs().isolate_hide_full_unsel_first:
            # Not a bug, but a feature! First, isolation skips meshes that have selected faces,
            # and only in the second pass are those meshes processed as well.

            for u in selected:
                if self.bl_idname.startswith("UV"):
                    u.sequence = [
                        isl
                        for isl in utypes.Islands.calc_visible(u)
                        if isl.is_full_face_deselected()
                    ]
                else:
                    u.sequence = [
                        isl
                        for isl in utypes.MeshIslands.calc_visible(u)
                        if isl.is_full_face_deselected()
                    ]
                has_unselected_faces |= bool(u.sequence)

        if has_unselected_faces:
            # Set isolated hidden to unselected faces.
            for umesh in visible:
                unselected_faces = utils.calc_unselected_uv_faces(umesh)
                if unselected_faces:
                    self.hide_faces_for_isolate(umesh, unselected_faces)
                    umesh.update_tag = True
                else:
                    sanitized_count += self.remove_empty_attr(umesh)

            # Set isolated hidden when selected islands exist.
            for umesh in selected:
                unselected_islands = umesh.sequence
                if unselected_islands:
                    self.hide_faces_for_isolate(
                        umesh, [f for isl in unselected_islands for f in isl]
                    )
                    umesh.update_tag = True
                else:
                    sanitized_count += self.remove_empty_attr(umesh)

            if sanitized_count:
                self.report(
                    {"INFO"},
                    f"Sanitized {sanitized_count} attributes. "
                    f"The default Hide/Unhide operator may have been used, or the geometry was modified.",
                )
            all_umeshes.update()

        else:
            # Unhide isolate hidden faces
            self.unhide_isolate_hidden_faces_uv(all_umeshes)
            if self.bl_idname.startswith("UV"):
                all_umeshes.update(info="Not found to unhide - isolate hidden faces.")
            else:
                all_umeshes.silent_update()  # TODO: Check for isolating objects? a print more informative info
        return has_unselected_faces

    def unhide_isolate_hidden_faces_3d(self, all_umeshes, hidden):
        if not hidden:
            # self.report({"WARNING"}, "Not found faces.")
            return False

        has_to_unhide = False
        sync = all_umeshes.sync

        for umesh in hidden:
            attr = umesh.bm.faces.layers.int.get("univ_isolate_hidden")
            if attr:
                to_unhide = [f for f in umesh.bm.faces if f[attr]]
                has_to_unhide |= bool(to_unhide)
                utils.unhide_faces_for_3d(to_unhide)
                if not sync:
                    for f in to_unhide:
                        f.select = True
                umesh.bm.faces.layers.int.remove(attr)
                umesh.update_tag = True

        if not has_to_unhide:
            self.report(
                {"INFO"}, "Not found isolate hidden faces, reveal all faces instead."
            )
            if self.bl_idname.startswith("UV"):
                bpy.ops.uv.reveal(select=True)
            else:
                bpy.ops.mesh.reveal(select=True)
        hidden.silent_update()
        return True

    @staticmethod
    def hide_faces_for_isolate(umesh, faces):
        attr = umesh.bm.faces.layers.int.get("univ_isolate_hidden")
        if not attr:
            umesh.bm.faces.index_update()
            indexes = [f.index for f in faces]
            attr = umesh.bm.faces.layers.int.new(
                "univ_isolate_hidden"
            )  # NOTE: That operation reallocate faces

            bm_faces = umesh.bm.faces
            bm_faces.ensure_lookup_table()
            faces = [bm_faces[i] for i in indexes]

        for f in faces:
            f[attr] = 1

        utils.linked_hide_faces_for_3d(faces)
        umesh.bm.select_history.validate()

    @staticmethod
    def unhide_isolate_hidden_faces_uv(umeshes):
        for umesh in umeshes:
            attr = umesh.bm.faces.layers.int.get("univ_isolate_hidden")
            if attr:
                to_unhide = [f for f in umesh.bm.faces if f.hide and f[attr]]
                utils.unhide_faces_for_3d(to_unhide)
                if not umesh.sync:
                    for f in to_unhide:
                        f.select = True
                umesh.bm.faces.layers.int.remove(attr)
                umesh.update_tag = True

    @staticmethod
    def remove_empty_attr(umesh):
        attr = umesh.bm.faces.layers.int.get("univ_isolate_hidden")
        if attr:
            is_invisible_check = utils.is_invisible_func(umesh.sync)
            is_not_found_marked_in_hidden = not any(
                f[attr] for f in umesh.bm.faces if is_invisible_check(f)
            )
            if is_not_found_marked_in_hidden:
                # Remove empty attribute if hidden isolated not exist.
                umesh.bm.faces.layers.int.remove(attr)
                umesh.update_tag = True
                return True
        return False


class UNIV_OT_Isolate_VIEW3D(UNIV_OT_Isolate):
    bl_idname = "object.univ_isolate"
    bl_description = "Isolate selected mesh islands and objects."

    # noinspection PyTypeHints
    ignore_seam: bpy.props.BoolProperty(name="Ignore Seams", default=True)

    def draw(self, context):
        self.layout.prop(prefs(), "isolate_focus_in_3d")
        if context.mode == "EDIT_MESH":
            self.layout.prop(self, "ignore_seam")
            self.layout.prop(prefs(), "isolate_hide_full_unsel_first")

    def invoke(self, context, event):
        if event.value == "PRESS":
            self.init_data_for_ray_cast(event)
            return self.execute(context)
        return self.execute(context)

    def execute(self, context):
        if context.mode != "EDIT_MESH":
            # TODO: Add Pick System.
            return bpy.ops.view3d.localview(frame_selected=prefs().isolate_focus_in_3d)

        all_umeshes = utypes.UMeshes.calc_with_no_uv(
            report=self.report, verify_uv=False
        )
        all_umeshes.set_sync()
        all_umeshes.sync_invalidate()
        all_umeshes.update_tag = False
        for u in all_umeshes:
            u.elem_mode = utils.get_select_mode_mesh()

        selected, visible, hidden = (
            all_umeshes.filtered_by_selected_and_visible_and_hidden_uv_faces()
        )

        if not selected and not visible:
            self.unhide_isolate_hidden_faces_3d(all_umeshes, hidden)
            if context.area.spaces.active.local_view:
                # Exit from local view.
                bpy.ops.view3d.localview(frame_selected=prefs().isolate_focus_in_3d)
            utils.update_area_by_type()
            return {"FINISHED"}

        if selected:
            is_isolated = self.isolate_for_selected(all_umeshes, selected, visible)
        else:  # Unselect Case.
            is_isolated = self.isolated_pick_or_unhide_all_3d(all_umeshes, visible)

        if is_isolated:
            if not context.area.spaces.active.local_view:
                # Set local view.
                bpy.ops.view3d.localview(frame_selected=prefs().isolate_focus_in_3d)
        else:
            # Toggle local view.
            bpy.ops.view3d.localview(frame_selected=prefs().isolate_focus_in_3d)
        utils.update_area_by_type()
        return {"FINISHED"}

    def isolated_pick_or_unhide_all_3d(self, all_umeshes, visible):
        # Isolate by Pick.
        if self.mouse_pos_from_3d:
            hit = self.ray_cast(visible, 1 << 10)
            if hit:
                if self.ignore_seam:
                    adv_isl, faces_set = hit.calc_visible_mesh_island_without_ms()
                else:
                    adv_isl, faces_set = hit.calc_visible_mesh_island()

                visible_faces = utils.calc_visible_uv_faces(hit.umesh)
                if len(visible_faces) != len(faces_set):
                    to_hide = set(visible_faces) - faces_set
                    self.hide_faces_for_isolate(hit.umesh, to_hide)
                    hit.umesh.update_tag = True

                    for umesh in visible:
                        if hit.umesh != umesh:
                            self.hide_faces_for_isolate(
                                umesh, utils.calc_visible_uv_faces(umesh)
                            )
                            umesh.update_tag = True

        is_isolated = all_umeshes.update_tag
        if not is_isolated:
            self.unhide_isolate_hidden_faces_uv(all_umeshes)
        # all_umeshes.update(info="Not found to unhide - isolate hidden faces.")
        all_umeshes.silent_update()

        return is_isolated
