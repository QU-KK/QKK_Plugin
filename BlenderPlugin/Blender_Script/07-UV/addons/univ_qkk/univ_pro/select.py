# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later


import bpy
import math
import bmesh

from mathutils import Vector
from bpy.props import *
from bpy.types import Operator
from collections.abc import Callable
from bmesh.types import BMFace


from .. import utils
from .. import utypes
from ..utypes import AdvIsland, Islands, MeshIslands, UMeshes, AdvEdge3D, AdvCorner
from ..operators import select


# noinspection PyTypeHints
class UNIV_OT_Select_Flat(Operator):
    bl_idname = "uv.univ_select_flat"
    bl_label = "Flat"
    bl_description = "Select linked flat faces"
    bl_options = {"REGISTER", "UNDO"}

    angle: FloatProperty(
        name="Angle",
        default=math.radians(15),
        min=math.radians(0.1),
        max=math.radians(180),
        soft_min=math.radians(1),
        soft_max=math.radians(89),
        subtype="ANGLE",
    )
    clamp_by_seams: BoolProperty(name="Clamp by Seams", default=True)
    grow_method: EnumProperty(
        name="Grow Method",
        default="ABSOLUTE",
        items=(("ABSOLUTE", "Absolute", ""), ("RELATIVE", "Relative", "")),
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "angle", slider=True)
        layout.prop(self, "clamp_by_seams")
        layout.row(align=True).prop(self, "grow_method", expand=True)

    def invoke(self, context, event):
        if event.value == "PRESS":
            return self.execute(context)

        self.grow_method = "RELATIVE" if event.alt else "ABSOLUTE"
        return self.execute(context)

    def execute(self, context):
        umeshes = UMeshes(report=self.report)
        umeshes.update_tag = False

        if not umeshes:
            self.report({"WARNING"}, "Not found selected faces to extend selection.")
            return {"CANCELLED"}

        need_sync_validation_check = False
        if umeshes.sync:
            if utils.USE_GENERIC_UV_SYNC:
                need_sync_validation_check = umeshes.elem_mode in ("VERT", "EDGE")

        # TODO: For pick system cache face by angle

        if self.grow_method == "ABSOLUTE":
            self.select_absolute_uv(umeshes, need_sync_validation_check)
        else:
            umeshes.filter_by_partial_selected_uv_faces()
            self.select_relative_uv(umeshes, need_sync_validation_check)
        umeshes.update(info="Not found flat linked faces for extend selection.")
        return {"FINISHED"}

    def select_absolute_uv(self, umeshes: UMeshes, need_sync_validation_check: bool):
        cos_angle = math.cos(self.angle)
        for umesh in umeshes:
            if umesh.is_full_face_deselected:
                continue
            if umesh.is_full_face_selected_for_avoid_force_explicit_check:
                continue

            get_face_select = utils.face_select_get_func(umesh)
            is_boundary = utils.is_boundary_func(umesh, with_seam=self.clamp_by_seams)

            # Find the first layer of unselected faces connected to selected faces.
            # Each face stores the normal of the selected face it was reached from
            step = self.select_absolute_uv_first_step(umesh)
            visited = set(step.keys())

            # Propagate the absolute normal through connected unselected faces.
            # A face is accepted when the angle to the normal of the face it was
            # reached from is within the specified threshold.
            while step:
                next_step: dict[BMFace, Vector] = {}
                for grow_face, abs_face_normal in step.items():
                    for crn in grow_face.loops:
                        next_face = crn.link_loop_radial_prev.face

                        if next_face in visited:
                            continue

                        if next_face in next_step:
                            # TODO: Set abs_face in next_step by min angle.
                            continue

                        if is_boundary(crn):
                            continue

                        # Skip selected face.
                        if get_face_select(next_face):
                            continue

                        # Dot angle, large = flatness.
                        if abs_face_normal.dot(next_face.normal) >= cos_angle:
                            # TODO: Allow this, used link_loop_radial_next and link_loop_radial_prev
                            next_step[next_face] = abs_face_normal

                visited.update(next_step.keys())
                step = next_step

            umesh.update_tag = bool(visited)

            if need_sync_validation_check:
                umesh.sync_from_mesh_if_needed()
            # TODO: Replace with face_select_linked_full
            AdvIsland(visited, umesh).select = True

    def select_absolute_uv_first_step(self, umesh):
        get_face_select = utils.face_select_get_func(umesh)
        is_boundary = utils.is_boundary_func(umesh, with_seam=self.clamp_by_seams)

        # Unselected linked to selected by angle faces.
        visited: dict[BMFace, Vector] = {}

        for abs_face in utils.calc_selected_uv_faces(umesh):
            for abs_crn in abs_face.loops:
                pair_unsel_face = abs_crn.link_loop_radial_prev.face
                if get_face_select(pair_unsel_face) or pair_unsel_face in visited:
                    continue

                if is_boundary(abs_crn):
                    continue

                min_angle = float("inf")
                min_angle_sel_face: BMFace | None = None

                # A face can be connected to multiple selected faces.
                # Use the selected neighbor with the smallest face angle.
                for crn in pair_unsel_face.loops:
                    edge = crn.edge
                    face_angle = edge.calc_face_angle(
                        180.1
                    )  # TODO: Check invalid when non-contiguous ???
                    if face_angle > min_angle or face_angle >= self.angle:
                        continue

                    if is_boundary(crn):
                        continue

                    selected_neighbor = crn.link_loop_radial_prev.face
                    if get_face_select(selected_neighbor):
                        min_angle = face_angle
                        min_angle_sel_face = selected_neighbor

                if min_angle_sel_face:
                    visited[pair_unsel_face] = min_angle_sel_face.normal
        return visited

    def select_relative_uv(self, umeshes: UMeshes, need_sync_validation_check: bool):
        for umesh in umeshes:
            is_boundary = utils.is_boundary_func(umesh, with_seam=self.clamp_by_seams)
            Islands.tag_filter_non_selected(umesh)
            selected_faces = []
            for f in utils.calc_selected_uv_faces(umesh):
                stack = [f]
                temp = []

                while stack:
                    for ff in stack:
                        for crn in ff.loops:
                            shared_face = crn.link_loop_radial_prev.face
                            if shared_face.tag:
                                if crn.edge.calc_face_angle(999.0) <= self.angle:
                                    if not is_boundary(crn):
                                        shared_face.tag = False
                                        temp.append(shared_face)
                    selected_faces.extend(temp)
                    stack = temp
                    temp = []

            if selected_faces:
                if need_sync_validation_check:
                    umesh.sync_from_mesh_if_needed()
                AdvIsland(selected_faces, umesh).select = True
                umesh.update_tag = True


class UNIV_OT_Select_Flat_VIEW3D(UNIV_OT_Select_Flat):
    bl_idname = "mesh.univ_select_flat"

    def execute(self, context):
        umeshes = UMeshes.calc_with_no_uv(report=self.report, verify_uv=False)
        umeshes.set_sync()
        umeshes.sync_invalidate()

        umeshes.update_tag = False
        if not umeshes:
            self.report({"WARNING"}, "Not found selected faces to extend selection.")
            return {"CANCELLED"}

        if self.grow_method == "ABSOLUTE":
            self.select_absolute_3d(umeshes)
        else:
            umeshes.filter_by_partial_selected_uv_faces()
            self.select_relative_3d(umeshes)

        umeshes.update(info="Not found linked flat faces for extend selection.")
        return {"FINISHED"}

    def select_absolute_3d(self, umeshes: UMeshes):
        cos_angle = math.cos(self.angle)
        for umesh in umeshes:
            if umesh.is_full_face_selected or umesh.is_full_face_deselected:
                continue

            # Find the first layer of unselected faces connected to selected faces.
            # Each face stores the normal of the selected face it was reached from
            step = self.select_absolute_3d_first_step(umesh)
            visited = set(step.keys())

            # Propagate the absolute normal through connected unselected faces.
            # A face is accepted when the angle to the normal of the face it was
            # reached from is within the specified threshold.
            while step:
                next_step: dict[BMFace, Vector] = {}
                for grow_face, abs_face_normal in step.items():
                    for crn in grow_face.loops:
                        next_face = crn.link_loop_radial_prev.face

                        if next_face in visited:
                            continue

                        if next_face in next_step:
                            # TODO: Set abs_face in next_step by min angle.
                            continue

                        # Skip selected or hidden face.
                        if next_face.select or next_face.hide:
                            continue
                        # Do not cross seams when seam clamping is enabled.
                        if self.clamp_by_seams and crn.edge.seam:
                            continue

                        # Dot angle, large = flatness.
                        if abs_face_normal.dot(next_face.normal) >= cos_angle:
                            # TODO: Allow this, used link_loop_radial_next and link_loop_radial_prev
                            next_step[next_face] = abs_face_normal

                visited.update(next_step.keys())
                step = next_step

            umesh.update_tag = bool(visited)
            for f in visited:
                f.select = True

    def select_absolute_3d_first_step(self, umesh):
        import itertools

        # Unselected linked to selected by angle faces.
        visited: dict[BMFace, Vector] = {}

        # Limit iteration using the known number of selected faces.
        # This avoids traversing the whole face sequence when only a few faces
        # are selected.
        selected_faces_iter = (f for f in umesh.bm.faces if f.select)
        # TODO: Add Early exit for utils (by few/lot selected faces)
        for abs_face in itertools.islice(selected_faces_iter, umesh.total_face_sel):
            for abs_crn in abs_face.loops:
                pair_unsel_face = abs_crn.link_loop_radial_prev.face
                if pair_unsel_face.select or pair_unsel_face in visited:
                    continue

                min_angle = float("inf")
                min_angle_sel_face: BMFace | None = None

                # A face can be connected to multiple selected faces.
                # Use the selected neighbor with the smallest face angle.
                for crn in pair_unsel_face.loops:
                    edge = crn.edge
                    face_angle = edge.calc_face_angle(
                        180.1
                    )  # TODO: Check invalid when non-contiguous ???
                    if face_angle > min_angle or face_angle >= self.angle:
                        continue

                    if self.clamp_by_seams and edge.seam:
                        continue

                    selected_neighbor = crn.link_loop_radial_prev.face
                    if selected_neighbor.select:
                        min_angle = face_angle
                        min_angle_sel_face = selected_neighbor

                if min_angle_sel_face:
                    visited[pair_unsel_face] = min_angle_sel_face.normal
        return visited

    def select_relative_3d(self, umeshes: UMeshes):
        for umesh in umeshes:
            MeshIslands.tag_filter_non_selected(umesh)
            selected_faces = []
            for f in utils.calc_selected_uv_faces(umesh):
                stack = [f]
                temp = []

                while stack:
                    for ff in stack:
                        for crn in ff.loops:
                            shared_face = crn.link_loop_radial_prev.face
                            if shared_face.tag:
                                if crn.edge.calc_face_angle(999.0) <= self.angle:
                                    if not (self.clamp_by_seams and crn.edge.seam):
                                        shared_face.tag = False
                                        temp.append(shared_face)
                    selected_faces.extend(temp)
                    stack = temp
                    temp = []

            if selected_faces:
                AdvIsland(selected_faces, umesh).select = True
                umesh.sync_valid = False
                umesh.update_tag = True


class UNIV_OT_Select_Loop_VIEW2D(select.UNIV_OT_Select_Edge_Grow_Base):
    bl_label = "Loop"
    bl_idname = "uv.univ_select_loop"
    bl_description = "Edge Loop Select\n\n" "Has [Alt + Scroll Up/Down] keymap"

    # noinspection PyTypeHints
    use_aspect: BoolProperty(name="Correct Aspect", default=True)

    def draw(self, context):
        layout = self.layout
        if self.grow:
            layout.prop(self, "prioritize_sharps")
        layout.prop(self, "boundary_by_boundary")
        layout.prop(self, "ignore_seams")
        layout.prop(self, "use_aspect")
        layout.prop(self, "max_angle")

    def execute(self, context):
        umeshes = UMeshes(report=self.report)
        umeshes.fix_context()

        if umeshes.elem_mode not in ("VERT", "EDGE"):
            # TODO: Implement loop select by face by 'edge apex'
            return bpy.ops.uv.univ_select_linked(deselect=False)  # noqa

        umeshes.filter_by_partial_selected_uv_edges()

        if self.use_aspect:
            umeshes.calc_aspect_ratio(from_mesh=False)
        self.loop_select(umeshes)

        umeshes.update(info="Not found edges for loop select")
        return {"FINISHED"}

    def loop_select(self, umeshes: UMeshes):
        from ..preferences import debug

        umeshes.update_tag = False
        max_angle = math.nextafter(self.max_angle, float("inf"))

        for umesh in umeshes:
            stack = list(self.get_unique_selected_uv_corners_without_selected_faces_iter(umesh))
            # assert len(stack) == len(exclude_edges), f"{len(stack) = }, {len(set(stack)) = }"

            grow = self.loop_select_ex(umesh, stack, max_angle, self.ignore_seams, self.prioritize_sharps, self.boundary_by_boundary)
            if grow:
                if umesh.sync:
                    umesh.sync_from_mesh_if_needed()

                edge_select_set = utils.edge_select_linked_set_func(umesh)
                for adv_crn in grow:
                    edge_select_set(adv_crn.orig_crn, True)
                umesh.update_tag = True

                if debug():
                    duplicates = len(grow) - len(set(grow))
                    if duplicates:
                        print(f"UniV Debug: Loop Select: Duplicate selection {duplicates}.")

    @classmethod
    def loop_select_ex(cls, umesh, stack: list[AdvCorner], max_angle: float, ignore_seams: bool, prioritize_sharps: bool, boundary_by_boundary: bool):
        grow: list[AdvCorner] = []
        exclude_edges = set()
        is_boundary = utils.is_boundary_func(umesh, with_seam=False)
        get_edge_select = utils.edge_select_get_func(umesh)

        is_first_loop = True
        while stack:
            next_stack = []
            for eg in stack:
                left, right, is_cyclic = eg.get_linked_left_right_and_get_cyclic_status(is_boundary)
                linked = left + right

                # Clamp by seams or selection.
                if ignore_seams or eg.orig_crn.edge.seam:
                    if any(get_edge_select(adv_crn.orig_crn) for adv_crn in linked):
                        continue
                else:
                    if any(get_edge_select(adv_crn.orig_crn) or adv_crn.edge.seam for adv_crn in linked):
                        continue

                eg = eg.copy()
                eg.toggle_dir()

                # Grow without check angle
                if is_cyclic:
                    if cls.grow_without_check_angle_or_with_prioritize_contiguous(eg, linked, exclude_edges, next_stack, max_angle):  # fmt: skip
                        continue
                elif not eg.is_pair:
                    if cls.grow_without_check_angle_or_with_prioritize_boundary(eg, exclude_edges, linked, next_stack, max_angle):
                        continue

                min_angle_adv_crn = cls.get_grow_by_angle_crn(eg, linked, max_angle, prioritize_sharps, boundary_by_boundary)
                if min_angle_adv_crn and min_angle_adv_crn not in exclude_edges:
                    exclude_edges.add(min_angle_adv_crn)

                    other_dir = min_angle_adv_crn.copy()
                    other_dir.toggle_dir()
                    exclude_edges.add(other_dir)

                    next_stack.append(other_dir)

            if not is_first_loop:
                grow.extend(stack)
            is_first_loop = False
            stack = next_stack
        return grow

    @staticmethod
    def grow_without_check_angle_or_with_prioritize_contiguous(
        eg: AdvCorner, linked: list[AdvCorner], exclude_edges: set[AdvCorner], next_stack: list[AdvCorner], max_angle: float
    ):
        """Grow when start edge has two same poly count faces and grew edge has two same poly count faces"""
        # TODO: Add case with prioritize by (len(linked) % 2).

        if len(linked) == 3:
            is_grow = False
            next_adv_crn = linked[1]

            # A case where a next corner has the same number of polygons as its linked faces.
            #  * - - - * - - - *
            #  |   N   | ^  N  |
            #  |       | |     |
            #  * - - - * - - - *
            #  |       | ^     |
            #  *       | |     *
            #  |       |       |
            #  * - - - * - - - *
            if len(next_adv_crn.face.loops) == len(next_adv_crn.pair_face.loops):
                is_grow = True

            if not is_grow:
                # A case where a corner has the same number of polygons.
                #           *
                #         / | \
                #       /   |   \
                #     /     | ^   \
                #   /       | |     \
                #  *  - - - * - - -  *
                #   \       | ^     /
                #     \     | |   /
                #       \   |   /
                #         \ | /
                #           *
                face_size = len(eg.face.loops)
                is_grow = all(face_size == len(l_adv_crn.face.loops) for l_adv_crn in linked)

            if not is_grow:
                # A case where linked faces have different polycounts.
                #  * - * - * - - - *
                #  |       |       |
                #  |   N1  | ^ N1  |
                #  |       | |     |
                #  * - - - * - - - *
                #  |       | ^    /
                #  *   N2  | | T /
                #  |       |    /
                #  |       |   /
                #  *       |  /
                #  |       | /
                #  |       |/
                #  * - - - *

                angle = eg.angle(next_adv_crn, max_angle) * 0.6
                if angle < max_angle:
                    is_grow = True

            if is_grow:
                if next_adv_crn in exclude_edges:
                    return True  # Skip circular step without add.

                next_grow = linked[1].copy()
                next_grow.toggle_dir()
                if next_grow not in exclude_edges:
                    next_stack.append(next_grow)
                    exclude_edges.add(next_grow)
                exclude_edges.add(linked[1])
                return True

        elif len(linked) == 2:
            # A case with prioritize one N-Gone and either two Quads or two Tris.
            #  * - - - * - - - *
            #  |       | ^     |
            #  *       | | 3|4 |
            #  |       |       |
            #  *   N   * - - - *
            #  |       | ^     |
            #  *       | | 3|4 |
            #  |       |       |
            #  * - - - * - - - *
            faces_gons_count = sorted(len(f.loops) for f in eg.crn.vert.link_faces)
            if faces_gons_count[-1] >= 5 and faces_gons_count[:2] in ([3, 3], [4, 4]):
                for l_adv_crn in linked:
                    if any(len(f.loops) >= 5 for f in l_adv_crn.edge.link_faces):

                        angle = eg.angle(l_adv_crn, max_angle) * 0.65
                        if angle < max_angle:
                            next_grow = l_adv_crn.copy()
                            next_grow.toggle_dir()

                            if l_adv_crn not in exclude_edges:
                                next_stack.append(next_grow)
                                exclude_edges.add(next_grow)
                            exclude_edges.add(l_adv_crn)
                            return True
        # Case when has two shared N-Gone.
        #  * - - - * - - - *
        #  |       | |     |
        #  |       |       *
        #  *  N1   *   N2  |
        #  |       | ^     *
        #  |       | |     |
        #  * - - - * - - - *

        elif len(linked) == 1:
            l_adv_crn = linked[0]
            angle = eg.angle(l_adv_crn, max_angle) * 0.65
            if angle < max_angle:
                next_grow = l_adv_crn.copy()
                next_grow.toggle_dir()

                if l_adv_crn not in exclude_edges:
                    next_stack.append(next_grow)
                    exclude_edges.add(next_grow)
                exclude_edges.add(l_adv_crn)
                return True
        return False

    @staticmethod
    def grow_without_check_angle_or_with_prioritize_boundary(adv_edge: AdvCorner,
                                                             added_edges: set[AdvCorner],
                                                             linked: list[AdvCorner],
                                                             next_stack: list[AdvCorner],
                                                             max_angle: float
                                                             ):

        assert not adv_edge.is_pair
        # NOTE: Not replace contiguous with simple check. This does not take hidden linked faces into account.

        if len(linked) == 2:
            # Multi-bounds select case along two quads (or by angle with other bound with priority).
            #   * - * - *
            #   | F | F |
            #   *   |   *
            #    \  |  /
            #  \  \ | /  /\
            #  \/  \|/   /
            #       *
            linked_contiguous = [adv_crn for adv_crn in linked if adv_crn.is_pair]
            if len(linked_contiguous) != 1:  # Nothing be happened.
                raise ValueError(f"Given 3 boundary's corners, linked_crn incorrect worked.")
                # return False
            link_eg_with_pair = linked_contiguous[0]

            linked_boundary = [b_eg for b_eg in linked if not b_eg.is_pair]
            if len(linked_boundary) != 1:  # Nothing be happened.
                raise ValueError(f"Given 2 contiguous corners, linked_crn incorrect worked.")
                # return False
            bound_edge = linked_boundary[0]

            face_sizes = [len(f.loops) for f in link_eg_with_pair.edge.link_faces]
            if any(f_size != 4 for f_size in face_sizes):
                # Ignore prioritize for tris.
                if 3 in face_sizes:
                    return False

                # Non-quads case, check other bound with priority.
                angle = adv_edge.angle(bound_edge, max_angle) * 0.65
                if max_angle < angle:
                    return False

            next_grow = bound_edge.copy()
            next_grow.toggle_dir()

            if bound_edge not in added_edges:
                next_stack.append(next_grow)
                added_edges.add(next_grow)
            added_edges.add(bound_edge)
            return True
        # The prioritization triangle usually gives an unnecessary result, so ignore the prioritization.
        elif len(linked) == 1 and len(adv_edge.face.loops) != 3:
            # Bounds with priority along single face.
            #  * - * - *
            #  | F | F |  /\
            #  *   |   *  ||
            #   \  |  /
            #    \ | /  /\
            #     \|/   /
            #      *

            bound_edge = linked[0]
            assert not bound_edge.is_pair
            angle = adv_edge.angle(bound_edge, max_angle) * 0.65

            if angle <= max_angle:
                get_linked_unordered_inc = utils.linked_crn_uv_to_vert_unordered_included_func(adv_edge.umesh)

                if len(get_linked_unordered_inc(bound_edge.crn)) == 1: # Non-manifold preserve case.
                    next_grow = bound_edge.copy()
                    next_grow.toggle_dir()

                    if bound_edge not in added_edges:
                        next_stack.append(next_grow)
                        added_edges.add(next_grow)
                    added_edges.add(bound_edge)
                    return True

        return False


class UNIV_OT_Select_Loop_Pick_VIEW2D(utypes.RayCastAndPick, UNIV_OT_Select_Loop_VIEW2D):
    bl_label = "Loop Pick"
    bl_idname = "uv.univ_select_loop_pick"
    bl_description = "Edge Loop Select Pick\n\n" "Has [Double LMB] and [Shift + Double LMB] keymap"

    def invoke(self, context, event):
        if not (context.area.type == "IMAGE_EDITOR" and context.area.ui_type == "UV"):
            self.report({"WARNING"}, "Active area must be UV type")
            return {"CANCELLED"}

        self.store_mouse_pose_on_uv_and_max_distance_if_allowed(event)
        return self.execute(context)

    def execute(self, context):
        umeshes = UMeshes(report=self.report)
        umeshes.fix_context()

        if umeshes.elem_mode != "EDGE" or not self.mouse_position:
            # TODO: Implement loop select by face by 'edge apex'
            return bpy.ops.uv.univ_select_linked(deselect=False)  # noqa

        hit = utypes.CrnEdgeHit(self.mouse_position)  # TODO: Use 75 px with scale correction
        for umesh in umeshes:
            e = umesh.bm.select_history.active
            if isinstance(e, bmesh.types.BMEdge):

                get_face_visible = utils.face_visible_get_func(umesh)
                visible_selected_crn = [crn for crn in getattr(e, "link_loops", ()) if get_face_visible(crn.face)]
                if not any(visible_selected_crn):
                    continue

                hit.find_nearest_crn_by_corners_from_pick(umesh, visible_selected_crn)

        if not hit:
            self.report({"WARNING"}, "Not found edge for loop select.")
            return {"CANCELLED"}

        if self.use_aspect:
            umeshes.calc_aspect_ratio(from_mesh=False)

        umesh = hit.umesh
        crn = hit.crn
        is_boundary = utils.is_boundary_func(umesh, with_seam=False)

        if is_boundary(crn):
            stack = [AdvCorner(crn, umesh, is_pair=False), AdvCorner(crn.link_loop_next, umesh, is_pair=False, invert=True)]
        else:
            stack = [AdvCorner(crn, umesh, is_pair=True), AdvCorner(crn.link_loop_radial_prev, umesh, is_pair=True)]

        max_angle = math.nextafter(self.max_angle, float("inf"))
        grow = self.loop_select_ex(umesh, stack, max_angle, self.ignore_seams, self.prioritize_sharps, self.boundary_by_boundary)
        umesh.update_tag = bool(grow)

        if grow:
            if umesh.sync:
                umesh.sync_from_mesh_if_needed()
            edge_select_set = utils.edge_select_linked_full_func(umesh)
            for adv_crn in grow:
                edge_select_set(adv_crn.orig_crn)

            if context.view_layer.objects.active != umesh.obj:
                context.view_layer.objects.active = umesh.obj
        umeshes.umeshes = [umesh]
        umeshes.update(info="Not found edges for loop select")
        return {"FINISHED"}


class UNIV_OT_Select_Loop_VIEW3D(select.UNIV_OT_Select_Edge_Grow_Base):
    bl_label = "Loop"
    bl_idname = "mesh.univ_select_loop"
    bl_description = "Loop Select\n\n" "Has [Alt + Scroll Up] keymap"
    # noinspection PyTypeHints
    max_angle: FloatProperty(
        name="Angle",
        default=math.radians(40),
        min=math.radians(1),
        soft_min=math.radians(5),
        max=math.radians(90),
        subtype="ANGLE",
        description="Max select angle.",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "prioritize_sharps")
        layout.prop(self, "boundary_by_boundary")
        layout.prop(self, "ignore_seams")
        layout.prop(self, "max_angle")

    def execute(self, context):
        if utils.get_select_mode_mesh() not in ("VERT", "EDGE"):
            # TODO: Implement loop select by face by 'edge apex'
            return bpy.ops.mesh.select_linked(
                delimit={"NORMAL"} if self.ignore_seams else {"SEAM"}
            )

        umeshes = UMeshes.calc_with_no_uv_and_no_faces(verify_uv=False)
        umeshes.set_sync()
        umeshes.sync_invalidate()
        self.loop_select_edge(umeshes)

        if not umeshes:
            self.report({"WARNING"}, "Not found edges for loop select")
        return {"FINISHED"}

    def loop_select_edge(self, umeshes: UMeshes):
        umeshes.filter_by_partial_selected_3d_edges()
        for umesh in umeshes:
            selected_edges = utils.calc_selected_edges_iter(umesh)
            stack = self.get_start_growable_edges_3d(selected_edges)
            self.grow_by_angle(stack, umesh)

    def grow_by_angle(self, stack: list[AdvEdge3D], umesh):
        max_angle = math.nextafter(self.max_angle, float("inf"))

        grow: list[list[AdvEdge3D]] = []
        added_edges: set[AdvEdge3D] = set()
        while stack:
            next_stack = []
            for eg in stack:
                if eg.is_wire:
                    linked = eg.get_linked_wire()
                elif not self.boundary_by_boundary:
                    linked = eg.get_linked_non_wire()
                elif eg.is_boundary:
                    linked = eg.get_linked_bound_by_bound()
                else:
                    linked = eg.get_linked_contiguous()

                # Clamp on selected edges and on seams.
                if self.ignore_seams or eg.e.seam:
                    if any(next_e.select for next_e in linked):
                        continue
                else:
                    if any(next_e.select or next_e.seam for next_e in linked):
                        continue

                # Grow without check angle.
                if not eg.is_wire:
                    if self.grow_without_check_angle(eg, added_edges, linked, next_stack, max_angle):
                        continue

                min_angle_edge = self.get_grow_by_angle_edge(eg, linked, max_angle)
                if min_angle_edge and min_angle_edge not in added_edges:
                    next_stack.append(min_angle_edge)
                    added_edges.add(min_angle_edge)

            grow.append(stack)
            stack = next_stack

        if grow:
            del grow[0]
            for edge_group in grow:
                for eg in edge_group:
                    eg.e.select = True
            umesh.update()

    def grow_without_check_angle(self,
                                 adv_edge: AdvEdge3D,
                                 added_edges: set[AdvEdge3D],
                                 linked: list[AdvEdge3D],
                                 next_stack: list[AdvEdge3D],
                                 max_angle: float
                                 ):

        if adv_edge.is_boundary:
            # NOTE: Not replace contiguous with simple check. This does not take hidden linked faces into account.
            linked_contiguous = adv_edge.get_linked_contiguous()

            if len(linked_contiguous) == 1:
                # Multi-bounds select case along two quads (or by angle with other bound with priority).
                #   * - * - *
                #   | F | F |
                #   *   |   *
                #    \  |  /
                #  \  \ | /  /\
                #  \/  \|/   /
                #       *

                if len(linked) != [2,1][self.boundary_by_boundary]:
                    return False

                link_eg_with_pair = linked_contiguous[0]
                if self.boundary_by_boundary:
                    bound_edge = linked[0]

                else:
                    linked_boundary = [b_eg for b_eg in linked if b_eg.is_boundary]
                    if len(linked_boundary) != 1:  # Unlikely?
                        return False
                    bound_edge = linked_boundary[0]

                face_sizes = [len(f.loops) for f in link_eg_with_pair.e.link_faces]
                if any(f_size != 4 for f_size in face_sizes):
                    # Ignore prioritize for tris.
                    if 3 in face_sizes:
                        return False

                    # Non-quads case, check other bound with priority.
                    angle = adv_edge.angle(bound_edge, max_angle) * 0.65
                    if max_angle < angle:
                        return False

                if bound_edge not in added_edges:
                    next_stack.append(bound_edge)
                    added_edges.add(bound_edge)
                    return True
            elif len(linked) == 1:
                # Bounds with priority along single face.
                #  * - * - *
                #  | F | F |  /\
                #  *   |   *  ||
                #   \  |  /
                #    \ | /  /\
                #     \|/   /
                #      *
                visible_faces = [f for f in adv_edge.head_v.link_faces if not f.hide]
                # Non-manifold preserve case.
                if len(visible_faces) == 1:
                    # The prioritization triangle usually gives an unnecessary result, so ignore the prioritization.
                    if len(visible_faces[0].loops) != 3:
                        bound_edge = linked[0]
                        assert bound_edge.is_boundary
                        angle = adv_edge.angle(bound_edge, max_angle) * 0.65

                        if angle <= max_angle:
                            if bound_edge not in added_edges:
                                next_stack.append(bound_edge)
                                added_edges.add(bound_edge)
                                return True

        else:
            return self.grow_without_check_angle_or_with_prioritize_contiguous(
                adv_edge, linked, added_edges, next_stack, max_angle
            )
        return False

    # TODO: Grow without check should be done on a flat Edge, that is, the 2 faces should be coplanar.
    #  And also for triangulated grid it is necessary to make the rules stricter,
    #  i.e. check first by the angle of the edge, and then with the coefficient to check with no check.
    @staticmethod
    def grow_without_check_angle_or_with_prioritize_contiguous(
        eg: AdvEdge3D,
        linked: list[AdvEdge3D],
        added_edges: set[AdvEdge3D],
        next_stack: list[AdvEdge3D],
        max_angle: float,
    ):
        """Grow when start edge has two same poly count faces and grew edge has two same poly count faces"""
        linked_to_vert_size = len(eg.head_v.link_faces)
        match len(linked):
            case 3:  # Quad - Quad case.
                #  *  -  *  -  *
                #  |  F  |  F  |
                #  *  -  *  -  *
                #  |  F  |  F  |
                #  *  -  *  -  *
                if linked_to_vert_size == 4:
                    linked_faces: list[BMFace] = [
                        f for f in eg.head_v.link_faces if not f.hide
                    ]
                    if len(linked_faces) == 4:
                        # TODO: improve behavior for tris and ngons (* 0.65)
                        curr_face_a = eg.e.link_faces[0]
                        curr_face_b = eg.e.link_faces[1]
                        if len(curr_face_a.loops) == 4 and len(curr_face_b.loops) == 4:
                            linked_faces.remove(curr_face_a)
                            linked_faces.remove(curr_face_b)

                            next_face_a, next_face_b = linked_faces
                            if (
                                len(next_face_a.loops) == 4
                                and len(next_face_a.loops) == 4
                            ):
                                for edge_grow in linked:
                                    if edge_grow not in added_edges:
                                        if not any(
                                            f in [curr_face_a, curr_face_b]
                                            for f in edge_grow.e.link_faces
                                        ):
                                            next_stack.append(edge_grow)
                                            added_edges.add(edge_grow)
                                            return True
            case 2:  # N-Gon and two Face case.
                #  *  -  *  -  *
                #  |     |  F  |
                #  *  N  *  -  *
                #  |     |  F  |
                #  *  -  *  -  *
                if linked_to_vert_size == 3:
                    faces_gons_count = sorted(
                        len(f.loops) for f in eg.head_v.link_faces if not f.hide
                    )
                    if len(faces_gons_count) == 3:
                        ngone = faces_gons_count.pop()
                        if ngone >= 5 and faces_gons_count[:2] in ([3, 3], [4, 4]):
                            for edge_grow in linked:
                                if any(
                                    len(f.loops) >= 5
                                    for f in edge_grow.e.link_faces
                                    if not f.hide
                                ):
                                    # TODO: With pointers to previous edges, one does not have to check for angle from vectors,
                                    #  but rather check by the normal that forms the previous edges and check against the subsequent one.
                                    angle = eg.angle(edge_grow, max_angle) * 0.65

                                    if (
                                        angle < max_angle
                                        and edge_grow not in added_edges
                                    ):
                                        next_stack.append(edge_grow)
                                        added_edges.add(edge_grow)
                                    return True
            case 1:  # Edge inner two N-Gon, with prioritize case.
                #  *  -  *  -  *
                #  |     |     |
                #  *     * <-  *
                #  |     | <-  |
                #  *     * <-  *
                #  |     |     |
                #  *  -  *  -  *
                if linked_to_vert_size == 2:
                    if sum(not f.hide for f in eg.head_v.link_faces) == 2:
                        edge_grow = linked[0]
                        if edge_grow not in added_edges:
                            angle = eg.angle(edge_grow, max_angle) * 0.65
                            if angle < max_angle:
                                next_stack.append(edge_grow)
                                added_edges.add(edge_grow)
                                return True
        return False


class UNIV_OT_Select_Loop_Pick_VIEW3D(UNIV_OT_Select_Loop_VIEW3D):
    bl_label = "Select Loop Pick"
    bl_idname = "mesh.univ_select_loop_pick"
    bl_description = (
        "Loop Select Pick\n\n" "Has [Double Click and Shift+Double Click] keymaps"
    )

    def loop_select_edge(self, umeshes: UMeshes):
        # TODO: Implement ray cast, for pick in vertex mode and implement face loops select
        # Pick Vertex Mode: Need find by raycast (generated from linked faces) (for solid mode to avoid selecting edges under face)
        # If not found raycast -> find nearest edge by dot product
        if utils.get_select_mode_mesh() == "VERT":
            bpy.ops.mesh.select_linked(
                delimit={"NORMAL"} if self.ignore_seams else {"SEAM"}
            )
            return

        for umesh in reversed(umeshes):
            if umesh.obj != bpy.context.active_object:
                umeshes.umeshes.remove(umesh)
                continue

            if not umesh.total_edge_sel:
                self.report({"WARNING"}, "Not found selected edge")
                return
            if not isinstance(umesh.bm.select_history.active, bmesh.types.BMEdge):
                self.report({"WARNING"}, "Active element must be an edge")
                return

            stack = self.get_start_growable_edges_3d([umesh.bm.select_history.active])
            self.grow_by_angle(stack, umesh)
            return

# noinspection PyTypeHints
class UNIV_OT_SelectSimilar_VIEW3D(Operator):
    bl_idname = "mesh.univ_select_similar"
    bl_label = "Similar"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = (
        "Select Similar Islands\n\n"
        "Default - Select Similar\n"
        "Shift or Alt - By Selected\n\n"
        "Has Shift+G keymap"
    )

    by_selected: bpy.props.BoolProperty(name="By Selected", default=False)

    walk_mode: bpy.props.EnumProperty(
        name="Walk Mode",
        default="BOTH",
        items=(
            ("BOTH", "Both", ""),
            ("DIRECT", "Direct", ""),
            ("SYMMETRY", "Symmetry", "For mirror islands"),
        ),
    )
    island_mode: bpy.props.EnumProperty(
        name="Island Mode",
        default="UV",
        items=(
            # ('BOTH', 'Both', ''),
            ("UV", "UV", "UV islands"),
            ("MESH", "Mesh", "Mesh islands"),
        ),
    )
    ignore_mark_seam: bpy.props.BoolProperty(name="Ignore Mark Seam", default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        self.layout.row(align=True).prop(self, "walk_mode", expand=True)
        self.layout.row(align=True).prop(self, "island_mode", expand=True)
        self.layout.prop(self, "ignore_mark_seam")
        self.layout.prop(self, "by_selected")

    def invoke(self, context, event):
        if event.value == "PRESS":
            return self.execute(context)

        self.by_selected = event.alt or event.shift
        return self.execute(context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.counter: int = 0
        self.island_calc_type: Callable = Islands.calc_selected
        self.calc_non_selected: Callable = Islands.calc_non_selected
        self.walk_direct = True
        self.walk_symmetry = True
        self.need_sync_validation_check = False

    def execute(self, context) -> set[str]:
        self.counter = 0
        umeshes = UMeshes(report=self.report)
        umeshes.update_tag = False

        if not self.bl_idname.startswith("UV"):
            umeshes.set_sync(True)
            umeshes.sync_invalidate()
            umeshes.elem_mode = "FACE"
        else:
            self.need_sync_validation_check = False
            if umeshes.sync:
                if utils.USE_GENERIC_UV_SYNC:
                    self.need_sync_validation_check = umeshes.elem_mode in (
                        "VERT",
                        "EDGE",
                    )

        self.walk_direct = self.walk_mode in ("DIRECT", "BOTH")
        self.walk_symmetry = self.walk_mode in ("SYMMETRY", "BOTH")

        self.get_island_calc_types()

        if self.by_selected:
            self.select_similar_by_selected(umeshes)
        else:
            self.select_similar_reference_transfer(umeshes)

        if self.counter:
            self.report({"INFO"}, f"Found {self.counter} similar islands")

        return {"FINISHED"}

    def islands_preprocessing_reference_and_transfer(self, umeshes: UMeshes):
        from .stack import StackIsland

        targets: list[StackIsland] = []
        for umesh in reversed(umeshes):
            islands = self.island_calc_type(umesh, with_seams=not self.ignore_mark_seam)
            if not islands:
                umeshes.umeshes.remove(umesh)
                continue
            if isinstance(islands, MeshIslands):
                islands = islands.to_adv_islands()
            islands.indexing()

            for isl in islands:
                stack_isl = StackIsland(isl)
                stack_isl.preprocessing()
                targets.append(stack_isl)

        if not targets:
            self.report({"WARNING"}, "Not found islands")
            return []

        sort_stack_islands_groups = utils.true_groupby(targets)
        if not sort_stack_islands_groups:
            self.report(
                {"WARNING"}, "Islands have different set and number of polygons"
            )
            return []
        return sort_stack_islands_groups

    def get_island_calc_types(self):
        type_class = Islands if self.island_mode == "UV" else MeshIslands
        if self.by_selected:
            self.island_calc_type = type_class.calc_selected
        else:
            self.island_calc_type = type_class.calc_visible
        self.calc_non_selected = type_class.calc_non_selected

    def islands_preprocessing_by_selected(self, umeshes: UMeshes):
        from . import stack

        targets = []
        transfers = []
        for umesh in reversed(umeshes):
            # TODO: With extended selection, you can calculate islands via calc_visible
            #  and add them to selected and non_selected. This does not work with calc_selected.
            selected = self.island_calc_type(
                umesh, with_seams=not self.ignore_mark_seam
            )
            non_selected = self.calc_non_selected(
                umesh, with_seams=not self.ignore_mark_seam
            )

            if not selected and not non_selected:
                umeshes.umeshes.remove(umesh)
                continue

            if isinstance(selected, MeshIslands):
                selected = selected.to_adv_islands()
                non_selected = non_selected.to_adv_islands()

            if not selected:
                proxi = non_selected
            elif not non_selected:
                proxi = selected
            else:
                proxi = Islands(non_selected.islands + selected.islands, umesh)

            proxi.indexing()

            for sel_isl in selected:
                stack_isl = stack.StackIsland(sel_isl)
                stack_isl.preprocessing()
                stack_isl.calc_walked_reference_island_fw_and_for_bw()
                targets.append(stack_isl)

            for non_sel_isl in non_selected:
                stack_isl = stack.StackIsland(non_sel_isl)
                stack_isl.preprocessing()
                transfers.append(stack_isl)

        if not targets:
            self.report({"WARNING"}, "Not found selected islands")
            return []

        if not transfers:
            self.report({"WARNING"}, "Not found unselected islands")
            return []

        sort_stack_islands = (
            stack.UNIV_OT_Stack_VIEW3D.sort_stack_islands_target_with_transfer(
                targets, transfers
            )
        )
        if not sort_stack_islands:
            self.report(
                {"WARNING"}, "Islands have different set and number of polygons"
            )
        return sort_stack_islands

    # By Selected
    def select_similar_reference_transfer(self, umeshes: UMeshes):
        from .stack import StackIsland

        preprocessing: list[list[StackIsland]] = (
            self.islands_preprocessing_reference_and_transfer(umeshes)
        )
        if not preprocessing:
            return

        umeshes.deselect_all_elem()

        to_select: set[AdvIsland] = set()
        for sort_stack_islands in preprocessing:
            for reference in sort_stack_islands:
                if reference.island.tag:
                    reference.island.tag = False
                    if not any(i.island.tag for i in sort_stack_islands):
                        break
                    reference.calc_walked_reference_island_fw_and_for_bw()
                    for trans in sort_stack_islands:
                        if trans.island.tag:
                            if (
                                self.walk_direct
                                and reference.calc_transfer_stack_island_fw(trans)
                            ) or (
                                self.walk_symmetry
                                and reference.calc_transfer_stack_island_bw(trans)
                            ):
                                to_select.add(trans.island)
                                to_select.add(reference.island)
                                trans.island.tag = False
                                self.counter += 1
                            trans.island.set_tag(False)
        if to_select:
            for isl in to_select:
                if self.need_sync_validation_check:
                    isl.umesh.sync_from_mesh_if_needed()
                elif isl.umesh._sync_invalidate:  # noqa
                    isl.umesh.sync_valid = False
                isl.select = True
                isl.umesh.update_tag = True

        umeshes.update(info_type={"WARNING"}, info="No found islands for stacking")

    # Reference Transfer
    def select_similar_by_selected(self, umeshes: UMeshes):
        from .stack import StackIsland

        sort_stack_islands: list[tuple[StackIsland, list[StackIsland]]] = (
            self.islands_preprocessing_by_selected(umeshes)
        )
        if not sort_stack_islands:
            return

        to_select = set()
        for reference, transfers in sort_stack_islands:
            for trans in transfers:
                if trans.island.tag:
                    if (
                        self.walk_direct
                        and reference.calc_transfer_stack_island_fw(trans)
                    ) or (
                        self.walk_symmetry
                        and reference.calc_transfer_stack_island_bw(trans)
                    ):
                        trans.island.tag = False
                        to_select.add(reference.island)
                        to_select.add(trans.island)
                    trans.island.set_tag(False)

        if to_select:
            for isl in to_select:
                if self.need_sync_validation_check:
                    isl.umesh.sync_from_mesh_if_needed()
                elif isl.umesh._sync_invalidate:  # noqa
                    isl.umesh.sync_valid = False
                isl.select = True
                isl.umesh.update_tag = True

        self.counter = len(to_select)
        umeshes.update(info_type={"WARNING"}, info="No found islands for stacking")


class UNIV_OT_SelectSimilar_VIEW2D(UNIV_OT_SelectSimilar_VIEW3D):
    bl_idname = "uv.univ_select_similar"


class UNIV_OT_SelectConstraints(Operator):
    bl_idname = "uv.univ_select_constraints"
    bl_label = "Select Constraints"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Select constraints edges by type."

    # noinspection PyTypeHints
    mode: EnumProperty(
        name="Select Mode",
        default="SELECT",
        items=(
            ("SELECT", "Select", ""),
            ("ADDITION", "Addition", ""),
            # ('DESELECT', 'Deselect', ''), # TODO: Add Deselect
        ),
    )
    # noinspection PyTypeHints
    constraints_type: bpy.props.EnumProperty(
        name="Constraint Type",
        default="VERTICAL",
        items=utils.ENUM(
            "VERTICAL",
            "HORIZONTAL",
            "DIAGONAL"
        ),
    )

    def invoke(self, context, event):
        if event.value == "PRESS":
            return self.execute(context)

        # if event.ctrl:
        #     self.mode = 'DESELECT'
        if event.shift:
            self.mode = "ADDITION"
        else:
            self.mode = "SELECT"
        return self.execute(context)

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        self.layout.row(align=True).prop(self, "mode", expand=True)
        self.layout.row(align=True).prop(self, "constraints_type", expand=True)

    def execute(self, context):
        umeshes = UMeshes()
        umeshes.fix_context()
        umeshes.update_tag = False

        if self.mode == "SELECT":
            bpy.ops.uv.select_all(action="DESELECT")

        has_found_edges = False

        from . import mark
        if self.constraints_type == "VERTICAL":
            expect_bits = mark.VERTICAL_CONSTR
        elif self.constraints_type == "HORIZONTAL":
            expect_bits = mark.HORIZONTAL_CONSTR
        else:
            expect_bits = mark.DIAGONAL_CONSTR

        for umesh in umeshes:
            constraints_attr = umesh.bm.edges.layers.int.get("univ_constraints")
            if not constraints_attr:
                continue

            to_select = []
            for crn in utils.calc_visible_uv_corners_iter(umesh):
                e = crn.edge
                edge_bits: int = e[constraints_attr]

                if edge_bits:
                    for i, crn_l in enumerate(e.link_loops):
                        if crn == crn_l:
                            if i == 16:
                                break

                            shift = i * 2
                            bits = (edge_bits >> shift) & 3  # Isolate bits.
                            if bits == expect_bits:
                                to_select.append(crn_l)
                            break
            has_found_edges |= bool(to_select)
            if self.mode == "ADDITION":
                get_edge_selection = utils.edge_select_get_func(umesh)
                to_select = [crn for crn in to_select if not get_edge_selection(crn)]

            umesh.sequence = to_select
            umesh.update_tag |= bool(to_select)

        if umeshes.update_tag:
            if umeshes.elem_mode not in ("EDGE", "VERT"):
                umeshes.elem_mode = "EDGE"
                umeshes.update_tag = True

            for umesh in umeshes:
                if utils.USE_GENERIC_UV_SYNC and umesh.sync:
                    umesh.sync_from_mesh_if_needed()

                select_set = utils.edge_select_linked_set_func(umesh)
                for crn in umesh.sequence:
                    select_set(crn, True)

        if not has_found_edges:
            self.report({"INFO"}, "Not found marked constraints edges for select.")
        umeshes.silent_update()
        return {"FINISHED"}
