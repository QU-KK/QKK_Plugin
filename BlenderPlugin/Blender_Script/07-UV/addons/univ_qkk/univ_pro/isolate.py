# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from mathutils import Vector

from .. import utils
from .. import utypes
from ..preferences import prefs


class UNIV_OT_Isolate(bpy.types.Operator):
    bl_idname = 'uv.univ_isolate'
    bl_label = 'Isolate'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Isolate selected islands."

    def draw(self, context):
        self.layout.prop(prefs(), "isolate_hide_full_unsel_first")

    def invoke(self, context, event):
        if context.area.type == 'IMAGE_EDITOR' and context.area.ui_type == 'UV':
            if event.value == 'PRESS':
                self.max_distance = utils.get_max_distance_from_px(prefs().max_pick_distance, context.region.view2d)
                self.mouse_pos = Vector(context.region.view2d.region_to_view(event.mouse_region_x, event.mouse_region_y))
                return self.execute(context)
        return self.execute(context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_distance: float = 0.0
        self.mouse_pos: Vector | None = None

    def execute(self, context):
        if context.mode != 'EDIT_MESH':
            # TODO: Implement removing attrs.
            self.report({"WARNING"}, "Expected edit mode.")
            return {'FINISHED'}

        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False

        selected, visible, hidden = umeshes.filtered_by_selected_and_visible_and_hidden_uv_faces()

        if not selected and not visible:
            return self.isolate_for_hidden(hidden, umeshes)
        if selected:
            return self.isolate_for_selected(selected, umeshes, visible)
        else:  # Unselect Case.
            return self.isolated_pick_or_unhide_all(umeshes, visible)

    def isolated_pick_or_unhide_all(self, umeshes, visible):
        # Isolate by Pick.
        if self.mouse_pos:
            hit = utypes.CrnEdgeHit(self.mouse_pos, self.max_distance)
            for umesh in visible:
                umesh.sequence = utils.calc_visible_uv_faces(umesh)
                hit.find_nearest_vert_by_visible_faces(umesh, use_faces_from_umesh_seq=True)

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

        if not umeshes.update_tag:
            self.unhide_isolate_hidden_faces(umeshes)

        umeshes.update(info="Not found to unhide - isolate hidden faces.")
        return {"FINISHED"}

    def isolate_for_selected(self, selected, umeshes, visible):
        sanitized_count = 0
        has_unselected_faces = bool(visible)

        if not has_unselected_faces or not prefs().isolate_hide_full_unsel_first:
            # Not a bug, but a feature! First, isolation skips meshes that have selected faces,
            # and only in the second pass are those meshes processed as well.

            for u in selected:
                u.sequence = [isl for isl in utypes.Islands.calc_visible(u) if isl.is_full_face_deselected()]
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
                    self.hide_faces_for_isolate(umesh, [f for isl in unselected_islands for f in isl])
                    umesh.update_tag = True
                else:
                    sanitized_count += self.remove_empty_attr(umesh)

            if sanitized_count:
                self.report({"INFO"},
                            f"Sanitized {sanitized_count} attributes. "
                            f"The default Hide/Unhide operator may have been used, or the geometry was modified.")
            umeshes.update()
            return {"FINISHED"}

        else:
            # Unhide isolate hidden faces
            self.unhide_isolate_hidden_faces(umeshes)
            umeshes.update(info="Not found to unhide - isolate hidden faces.")
            return {"FINISHED"}

    def isolate_for_hidden(self, hidden, umeshes):
        if not hidden:
            # self.report({"WARNING"}, "Not found faces.")
            return {"CANCELLED"}

        has_to_unhide = False
        sync = umeshes.sync

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
            self.report({"INFO"}, "Not found isolate hidden faces, un-hided all faces instead.")
            bpy.ops.uv.reveal(select=True)
        hidden.update()
        return {"FINISHED"}


    @staticmethod
    def hide_faces_for_isolate(umesh, faces):
        attr = umesh.bm.faces.layers.int.get("univ_isolate_hidden")
        if not attr:
            umesh.bm.faces.index_update()
            indexes = [f.index for f in faces]
            attr = umesh.bm.faces.layers.int.new("univ_isolate_hidden")  # NOTE: That operation realloc faces

            bm_faces = umesh.bm.faces
            bm_faces.ensure_lookup_table()
            faces = [bm_faces[i] for i in indexes]

        for f in faces:
            f[attr] = 1

        utils.linked_hide_faces_for_3d(faces)


    @staticmethod
    def unhide_isolate_hidden_faces(umeshes):
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
            is_not_found_marked_in_hidden = not any(f[attr] for f in umesh.bm.faces if is_invisible_check(f))
            if is_not_found_marked_in_hidden:
                # Remove empty attribute if hidden isolated not exist.
                umesh.bm.faces.layers.int.remove(attr)
                umesh.update_tag = True
                return True
        return False