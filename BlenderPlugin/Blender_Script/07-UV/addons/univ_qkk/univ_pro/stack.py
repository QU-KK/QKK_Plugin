# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later


import bpy  # noqa

from ..operators import stack
from ..operators.stack import FacePattern

from .. import utypes
from collections import deque

from bmesh.types import BMFace, BMLoop


class StackIsland(stack.StackIsland):

    def preprocessing(self):
        super().preprocessing()
        self.face_start_pattern_bw, self.face_start_pattern_crn_bw = (self.calc_linked_corners_pattern_bw(idx=0))  # fmt: skip

    def calc_linked_corners_pattern_bw(self, idx):

        init_face: BMFace = self.unique_faces[idx]
        face_idx = init_face.index

        # The first element of the pattern is the size of the shared edge.
        # The remaining sorted sizes are those of the linked corners.
        # [shared face size, *linked corners face sides]
        face_start_pattern: deque[list[int]] = deque()
        face_start_pattern_crn: deque[BMLoop] = deque(reversed(init_face.loops))

        # Sort by longest edge.
        unique_dist_idx = self.get_unique_start_crn_idx(face_start_pattern_crn)
        face_start_pattern_crn.rotate(-(unique_dist_idx - 1))

        from ..utils import linked_crn_to_vert_by_idx_without_co_check_unordered as get_linked

        for crn in face_start_pattern_crn:
            linked_corners_face_sides = [len(l_crn.face.loops) for l_crn in get_linked(crn)]

            # Insert start corner to first.
            shared_face_sides = 0
            prev_crn = crn.link_loop_prev
            shared_crn = prev_crn.link_loop_radial_prev
            if shared_crn != prev_crn and shared_crn.face.index == face_idx:
                shared_face_sides = len(shared_crn.face.loops)

            # Contain corners face sides and linked corners to start corner.
            linked_corners_face_sides.sort()
            linked_corners_face_sides.insert(0, shared_face_sides)
            face_start_pattern.append(linked_corners_face_sides)

        return [face_start_pattern, face_start_pattern_crn]

    def calc_all_linked_corners_pattern_bw(self):
        start_faces_patterns_bw: list[list[deque[list[int]] | deque[BMLoop]]] = []
        for idx, sequ in enumerate(self.unique_faces):
            if idx:
                start_faces_patterns_bw.append(self.calc_linked_corners_pattern_bw(idx))
        self.start_faces_patterns_bw = start_faces_patterns_bw

    def compared_matching_first_pattern_bw(self, transformed: "StackIsland"):
        if len(self.face_start_pattern_fw) != len(transformed.face_start_pattern_bw):
            return

        # Single face check.
        for _ in range(len(transformed.face_start_pattern_bw)):
            if self.face_start_pattern_fw == transformed.face_start_pattern_bw:
                yield transformed.face_start_pattern_crn_bw

            transformed.face_start_pattern_bw.rotate(1)
            transformed.face_start_pattern_crn_bw.rotate(1)

        if not transformed.start_faces_patterns_bw:
            transformed.calc_all_linked_corners_pattern_bw()

        # Check by all other faces.
        for face_start_pattern_bw, face_start_pattern_crn_bw in transformed.start_faces_patterns_bw:
            for _ in range(len(face_start_pattern_bw)):
                if self.face_start_pattern_fw == face_start_pattern_bw:
                    yield face_start_pattern_crn_bw

                face_start_pattern_bw.rotate(1)
                face_start_pattern_crn_bw.rotate(1)

    def calc_transfer_stack_island_bw(self, transform: "StackIsland"):
        for transform_pattern in self.compared_matching_first_pattern_bw(transform):

            transfer_island_walked: list[list[FacePattern]] = []
            transform.island.set_tag(True)  # TODO: Tagging transfer_island_walked

            start_crn_ = transform_pattern[0]  # Error might be this
            init_face_pattern = FacePattern(start_crn_.face, start_crn_, transform_pattern)
            init_face_pattern.face.tag = False

            # Container collector of island elements
            parts_of_island: list[FacePattern] = [init_face_pattern]

            face_idx = init_face_pattern.face.index

            temp = []  # Container for get elements from loop from parts_of_island
            failed = False
            for generation_of_shared_face in self.walked_island_from_init_face:
                for trans_face, tar_face in zip(generation_of_shared_face, parts_of_island):

                    if len(trans_face.ordered_corners) != len(tar_face.ordered_corners):
                        failed = True
                        break
                    for tar_face_size, transfer_crn in zip(
                        trans_face.ordered_corners_pair_crn_face_sides,
                        tar_face.ordered_corners,
                    ):
                        transfer_crn = transfer_crn.link_loop_prev

                        trans_pair_crn = transfer_crn.link_loop_radial_prev
                        trans_pair_face = trans_pair_crn.face

                        if tar_face_size == 0:
                            if (
                                trans_pair_crn == transfer_crn
                                or (not trans_pair_face.tag)
                                or (trans_pair_face.index != face_idx)
                            ):
                                continue
                            else:
                                # Transfer corner has valid pair corner, stop the walking.
                                failed = True
                                break

                        if trans_pair_crn == transfer_crn:
                            failed = True
                            break

                        if (
                            tar_face_size != len(trans_pair_face.loops)
                            or (not trans_pair_face.tag)
                            or (trans_pair_face.index != face_idx)
                        ):
                            failed = True
                            break

                        trans_pair_face.tag = False
                        temp.append(FacePattern.calc_bw(trans_pair_face, trans_pair_crn.link_loop_next))
                    if failed:
                        break

                transfer_island_walked.append(parts_of_island)
                parts_of_island = temp
                temp = []

                if failed:
                    break
            if not failed:
                return transfer_island_walked
        return None


# noinspection PyTypeHints
class UNIV_OT_Stack_VIEW3D(stack.UNIV_OT_Stack_VIEW3D):

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
    ignore_seams: bpy.props.BoolProperty(name="Ignore Seams", default=True)

    def draw(self, context):
        self.layout.row(align=True).prop(self, "walk_mode", expand=True)
        self.layout.row(align=True).prop(self, "island_mode", expand=True)
        self.layout.prop(self, "target_and_ref_ordering", expand=True)
        self.layout.prop(self, "ignore_seams")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.walk_direct = True
        self.walk_symmetry = True

    def execute(self, context) -> set[str]:
        self.counter = 0
        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False
        if not umeshes.sync and context.area.ui_type != "UV":
            umeshes.set_sync(True)

        self.walk_direct = self.walk_mode in ("DIRECT", "BOTH")
        self.walk_symmetry = self.walk_mode in ("SYMMETRY", "BOTH")

        self.get_island_calc_types()

        if self.target_and_ref_ordering == "BETWEEN_SELECTED":
            self.stack_selected_between(umeshes)
        else:
            self.stack_transfer_to_target(umeshes)
        if self.counter:
            self.report({"INFO"}, f"Found {self.counter} islands for stacking")

        return {"FINISHED"}

    def get_island_calc_types(self):
        type_class = utypes.Islands if self.island_mode == "UV" else utypes.MeshIslands
        self.calc_selected = type_class.calc_selected
        self.calc_non_selected = type_class.calc_non_selected

    # Between Selected
    def stack_selected_between(self, umeshes: utypes.UMeshes):
        for sorted_targets_islands in self.islands_preprocessing_selected_between(
            umeshes, StackIsland
        ):
            for tar in sorted_targets_islands:
                if tar.island.tag:
                    tar.island.tag = False
                    if not any(i.island.tag for i in sorted_targets_islands):
                        break
                    tar.calc_walked_reference_island_fw_and_for_bw()
                    for trans in sorted_targets_islands:
                        if trans.island.tag:

                            res = None
                            if self.walk_direct:
                                res = tar.calc_transfer_stack_island_fw(trans)
                            if self.walk_symmetry and not res:
                                res = tar.calc_transfer_stack_island_bw(trans)

                            if res:
                                tar.transfer_co_to(res, trans.island.umesh.uv)

                                trans.island.mark_seam()
                                trans.island.umesh.update_tag = True
                                trans.island.tag = False
                                self.counter += 1
                            trans.island.set_tag(False)  # TODO: Check when else

        umeshes.update(info_type={"WARNING"}, info="No found islands for stacking")

    def stack_transfer_to_target(self, umeshes: utypes.UMeshes):
        sorted_targets_islands_with_transfers = (
            self.islands_preprocessing_target_and_transfer(umeshes, StackIsland)
        )

        tar: StackIsland
        for tar, transfers in sorted_targets_islands_with_transfers:
            for trans in transfers:
                if trans.island.tag:

                    res = None
                    if self.walk_direct:
                        res = tar.calc_transfer_stack_island_fw(trans)
                    if self.walk_symmetry and not res:
                        res = tar.calc_transfer_stack_island_bw(trans)

                    if res:
                        tar.transfer_co_to(res, trans.island.umesh.uv)

                        trans.island.mark_seam()
                        trans.island.umesh.update_tag = True
                        trans.island.tag = False
                        self.counter += 1
                    trans.island.set_tag(False)

        umeshes.update(info_type={"WARNING"}, info="No found islands for stacking")


class UNIV_OT_Stack(UNIV_OT_Stack_VIEW3D):
    bl_idname = "uv.univ_stack"
