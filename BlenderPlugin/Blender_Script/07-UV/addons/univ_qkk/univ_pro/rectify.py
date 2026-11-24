# SPDX-FileCopyrightText: 2026 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later


import bpy

from .. import utils
from ..preferences import prefs
from .. import utypes
from ..utypes import AdvIsland, Segment, Segments

class RectifyType:
    Four = 1
    Two = 2
    Single = 3
    HalfSelected = 5
    FullSelected = 6

# TODO: Add only short path mode, without boundary correction (bugs on cube with subdiv)
class RectifyBase:
    # @staticmethod
    # def rect_lgs_to_distribute(groups: LoopGroups):
    #     # TODO: Add Only 4 points pin.
    #
    #     # TODO: Add distribute by mask and get intervals from short path if unpinned exist
    #     #  or validate short path by angle  (bugs on cube with subdiv)
    #     uv = groups.umesh.uv
    #
    #     first_lg = groups[0]
    #     card_vec = utils.vec_to_cardinal(first_lg.get_vector())
    #     start = first_lg.src[uv].uv
    #     end = start + (card_vec * first_lg.length_uv)
    #     first_lg.distribute(start, end)
    #
    #     prev_lg = groups[-1]
    #     next_lg = groups[1]
    #     inter_avg_length = (prev_lg.length_uv + next_lg.length_uv) / 2
    #
    #     end = prev_lg.dst[uv].uv
    #     start = end + (inter_avg_length * card_vec.orthogonal())
    #     prev_lg.distribute(start, end)
    #
    #     start = next_lg.src[uv].uv
    #     end = start + (inter_avg_length * card_vec.orthogonal())
    #     next_lg.distribute(start, end)
    #
    #     last_lg = groups[2]
    #     last_lg.distribute(last_lg.src[uv].uv, last_lg.dst[uv].uv)

    @staticmethod
    def total_selected_crn(seg: Segment):
        vert_select_get = utils.vert_select_get_func(seg.umesh)
        return sum(
            (
                vert_select_get(adv_crn.crn.link_loop_next)
                if adv_crn.invert
                else vert_select_get(adv_crn.crn)
            )
            for adv_crn in seg
        )

    @staticmethod
    def selected_to_first(seg: Segment):
        get_vert_select = utils.vert_select_get_func(seg.umesh)
        for idx, adv_crn in enumerate(seg):
            crn = adv_crn.crn.link_loop_next if adv_crn.invert else adv_crn.crn
            if get_vert_select(crn):
                if idx == 0:
                    return
                seg.seg = seg.seg[idx:] + seg.seg[:idx]
                return
        raise ValueError("Selected vertices not found")

    @staticmethod
    def target_to_first(lg: Segment, target_crn):
        for (idx, adv_crn) in enumerate(lg):
            if adv_crn.orig_crn == target_crn:
                if idx == 0:
                    return
                lg.corners = lg.seg[idx:] + lg.seg[:idx]
                return
        raise ValueError("Selected vertices not found")

    @classmethod
    def split_to_four_groups(cls, border_seg: Segment) -> utypes.Segments:
        assert border_seg.is_circular
        cls.selected_to_first(border_seg)
        umesh = border_seg.umesh

        get_vert_select = utils.vert_select_get_func(umesh)
        groups = []
        start_idx = 0

        it = iter(border_seg.seg)
        next(it)
        for idx, adv_crn in enumerate(it, start=1):
            if get_vert_select(adv_crn.orig_crn):
                groups.append(Segment(border_seg.seg[start_idx:idx], umesh))
                start_idx = idx

                if len(groups) == 3:
                    groups.append(Segment(border_seg.seg[start_idx:], umesh))
                    return utypes.Segments(groups, umesh)
        # TODO: Raise ???
        return utypes.Segments(groups, umesh)


class RectifyRing(RectifyBase):

    @classmethod
    def two_pt_ring_lg_to_rect(cls, boundary_loop_groups: Segments, isl: AdvIsland):  # fmt: skip
        assert len(boundary_loop_groups) == 2

        umesh = isl.umesh

        for border_lg in boundary_loop_groups:
            cls.selected_to_first(border_lg)

        for border_lg in boundary_loop_groups:
            border_lg.length_uv  # noqa
            border_lg.calc_chain_linked_corners()

        prioritize_corners = set()

        for border_lg in boundary_loop_groups:
            for linked in border_lg.chain_linked_corners[1:-1]:
                prioritize_corners.update(linked)

        lg_a = boundary_loop_groups[0]
        lg_b = boundary_loop_groups[1]

        include_corners = set(isl.corners_iter())
        segment = utils.ShortPath.calc_path_uv_vert(lg_a.start_orig_crn, lg_b.start_orig_crn, umesh,
                                                    include_corners, set(), prioritize_corners, 0.5
                                                    )

        segment = cls.get_clipped_start_end_segment_by_pair(segment, lg_a, lg_b)
        segment.mark_seam(rewrite_pair_status=False)

        corners = []
        for adv_crn in segment:
            crn = adv_crn.orig_crn
            corners.append(crn)
            corners.append(crn.link_loop_radial_prev)

        segments = Segments.from_corners(corners, umesh)
        assert len(segments) == 2
        assert boundary_loop_groups[0]
        assert boundary_loop_groups[1]

        first_bound = boundary_loop_groups[0]
        second_bound = boundary_loop_groups[1]
        first_inner = segments[0]
        second_inner = segments[1]

        new_first_border = Segments.from_corners(first_bound.to_corners(), umesh)

        assert len(new_first_border) == 1, f"Expected `1` segment, {len(new_first_border)!r} given."
        first_bound = new_first_border[0]

        new_second_border = Segments.from_corners(second_bound.to_corners(), umesh)
        assert len(new_second_border) == 1, f"Expected `1` segment, {len(new_second_border)!r} given."
        second_bound = new_second_border[0]

        segments = Segments([first_bound, second_inner, second_bound, first_inner, ], umesh)
        return segments

    @classmethod
    def one_pt_ring_lg_to_rect(cls, boundary_segments: Segments, isl: AdvIsland):  # fmt: skip
        umesh = isl.umesh
        boundary_segments.segments.sort(key=lambda s: s.value, reverse=True)
        selected_seg = boundary_segments[0]
        cls.selected_to_first(selected_seg)

        first_co = selected_seg.start_co

        unselected_borders = boundary_segments.segments[1:]
        unselected_borders.sort(key=lambda s: s.length_uv, reverse=True)

        max_length = -float("inf")
        min_dist_idx = 0
        min_dist = float("inf")
        min_dist_seg = None
        for seg in unselected_borders:
            # The longest segment might not be cyclic (probably),
            # so we'll check everything possible, instead first sorted.
            if seg.is_circular:
                if seg.length_uv > max_length:
                    max_length = seg.length_uv
                    for i, adv_crn in enumerate(seg):
                        new_dist = (adv_crn.curr_pt - first_co).length
                        if new_dist < min_dist:
                            min_dist = new_dist
                            min_dist_idx = i
                            min_dist_seg = seg

        if not min_dist_seg:
            return None
        utils.list_rotate(min_dist_seg.seg, -min_dist_idx)

        prioritize_corners = set()

        # TODO: Implement ShortPath with weak cost for non-longer, other borders.
        # Prioritize the longest other border.
        min_dist_seg.calc_chain_linked_corners()
        for linked in min_dist_seg.chain_linked_corners:
            prioritize_corners.update(linked)

        short_path = utils.ShortPath.calc_path_uv_vert(
            selected_seg.start_orig_crn,
            min_dist_seg.start_orig_crn,
            umesh,
            set(isl.corners_iter()),
            set(),
            prioritize_corners,
            0.1,
        )

        segment = cls.get_clipped_start_end_segment_pair_and_unpair(short_path, selected_seg, min_dist_seg)
        segment.mark_seam(rewrite_pair_status=False)

        left, right = segment.split_left_and_right()
        right.reverse()
        # Segments([left, right], umesh).draw()
        if prefs().debug == "ENABLED":
            corners = []
            for adv_crn in segment:
                crn = adv_crn.orig_crn
                corners.append(crn)
                corners.append(crn.link_loop_radial_prev)

            segments = Segments.from_corners(corners, umesh)
            assert len(segments) >= 2
            assert selected_seg
            assert min_dist_seg

        first_bound = selected_seg
        second_bound = min_dist_seg
        first_inner = left
        second_inner = right

        # first_inner = right
        # second_inner = left

        new_first_border = Segments.from_corners(first_bound.to_corners(), umesh)

        assert len(new_first_border) == 1, f"Expected `1` segment, {len(new_first_border)!r} given."
        first_bound = new_first_border[0]

        new_second_border = Segments.from_corners(second_bound.to_corners(), umesh)
        assert len(new_second_border) == 1, f"Expected `1` segment, {len(new_second_border)!r} given."
        second_bound = new_second_border[0]

        segments = Segments([first_bound, second_inner, second_bound, first_inner, ], umesh)
        # segments.draw()
        return segments

    @staticmethod
    def get_clipped_start_end_segment_by_pair(short_path, border_seg_a, border_seg_b):
        """An inner segment can cross border segments, potentially splitting an island into two parts.
        When recalculating the border segments, this can cause them to be split into two parts as well."""
        if not border_seg_a.chain_linked_corners:
            border_seg_a.calc_chain_linked_corners()
        if not border_seg_b.chain_linked_corners:
            border_seg_b.calc_chain_linked_corners()

        all_border_corners_a = set()
        all_border_corners_b = set()
        for linked in border_seg_a.chain_linked_corners:
            all_border_corners_a.update(linked)
        for linked in border_seg_b.chain_linked_corners:
            all_border_corners_b.update(linked)

        groups = utils.groups_by_mask(short_path, (adv_crn.is_pair for adv_crn in short_path))
        for s in groups:
            s = Segment(s, short_path.umesh)
            in_a = s.start_orig_crn in all_border_corners_a
            if in_a:
                assert s.start_orig_crn not in all_border_corners_b, "Both border segments are merged into a single segment."

            s.calc_chain_linked_corners()
            start = 0
            for i, linked in enumerate(s.chain_linked_corners[1:]):
                l_crn = linked[0]
                if in_a:
                    if l_crn in all_border_corners_a:
                        start = i
                        in_a = not in_a
                    if l_crn in all_border_corners_b:
                        return Segment(s[start:i+1], s.umesh)
                else:
                    if l_crn in all_border_corners_b:
                        start = i
                        in_a = not in_a
                    if l_crn in all_border_corners_a:
                        return Segment(s[start:i+1], s.umesh)

        raise IndexError("Not found subsegment.")

    @staticmethod
    def get_clipped_start_end_segment_pair_and_unpair(short_path: Segment, border_seg_a, border_seg_b):
        """For single select and multy ather borders"""
        if not border_seg_a.chain_linked_corners:
            border_seg_a.calc_chain_linked_corners()
        if not border_seg_b.chain_linked_corners:
            border_seg_b.calc_chain_linked_corners()

        all_border_corners_a = set()
        all_border_corners_b = set()
        for linked in border_seg_a.chain_linked_corners:
            all_border_corners_a.update(linked)
        for linked in border_seg_b.chain_linked_corners:
            all_border_corners_b.update(linked)

        trimmed_seg = utils.strip_by(short_path.seg, key=lambda a: a.is_pair)
        trimmed_seg = Segment(trimmed_seg, short_path.umesh)

        in_a = trimmed_seg.start_orig_crn in all_border_corners_a
        assert in_a
        if in_a:
            assert trimmed_seg.start_orig_crn not in all_border_corners_b, "Both border segments are merged into a single segment."

        trimmed_seg.calc_chain_linked_corners()
        start = 0
        for i, linked in enumerate(trimmed_seg.chain_linked_corners[1:]):
            l_crn = linked[0]

            if l_crn in all_border_corners_a:
                start = i
            if l_crn in all_border_corners_b:
                return Segment(trimmed_seg[start:i+1], trimmed_seg.umesh)

        raise IndexError("Not found subsegment.")


# noinspection PyTypeHints
class UNIV_OT_Rectify(bpy.types.Operator, RectifyRing):
    """
    1) Calc segments by boundary corners.
    2) Filtering to Ring or Four Point Rect
    3) Get 4 segments
    4) Set Constraints
    5) Unwrap
    """

    bl_idname = "uv.univ_rectify"
    bl_label = "Rectify"
    bl_description = "Align selected UV 4 or 2 point to rectangular distribution"
    bl_options = {"REGISTER", "UNDO"}

    border_priority: bpy.props.FloatProperty(name="Boundary Priority Factor", default=0.05, min=0, soft_max=0.3, max=0.5)  # fmt: skip
    use_aspect: bpy.props.BoolProperty(name="Correct Aspect", default=True)

    @classmethod
    def poll(cls, context):
        tool_settings = context.scene.tool_settings
        if tool_settings.use_uv_select_sync:
            if tool_settings.mesh_select_mode[:] != (True, False, False):
                return False
        else:
            if tool_settings.uv_select_mode != "VERTEX":
                return False
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "border_priority", slider=True)
        layout.prop(prefs(), "use_texel")
        layout.prop(self, "use_aspect")

    def execute(self, context):
        umeshes = utypes.UMeshes(report=self.report)
        umeshes.update_tag = False
        umeshes.fix_context()
        if self.use_aspect:
            umeshes.calc_aspect_ratio(from_mesh=False)
        umeshes.filter_by_selected_uv_verts()

        rect_islands = self.get_rect_lg_with_isl_of_mesh(umeshes)
        for isl, four_seg in rect_islands:
            isl.umesh.update_tag = True
            isl.mark_seam(additional=True)

            v_corners = []
            h_corners = []
            four_seg.rotate_longest_to_first()

            start = four_seg[0].is_horizontal_by_bbox(aspect_y=1.2)
            for i, lg in enumerate(four_seg, start=int(start)):
                if (i % 2) == 0:
                    v_corners.extend([a.orig_crn for a in lg])
                else:
                    h_corners.extend([a.orig_crn for a in lg])

            isl.set_corners_tag(True)
            utils.uv_parametrizer.unwrap_isl_by_tag_v2(
                isl,
                unwrap_along="UV",
                use_abf=True,
                topology_from_uvs=True,
                constraints_factor=20.0,
                constr_correction_weight=4.0,
                constr_edge_weight=0.1,
                constraints=(h_corners, v_corners, []),
            )

            self.finished_rect(isl, four_seg)

            if prefs().use_texel:
                utils.set_global_texel(isl, isl.calc_bbox())

        return umeshes.update(info="Did not find 4 selected boundary points or 2 boundary points on the ring.")

    def get_rect_lg_with_isl_of_mesh(self, umeshes):
        for umesh in umeshes:
            for isl in utypes.Islands.calc_visible(umesh):
                if utypes.IslandsBase.island_filter_is_any_vert_selected(isl.faces, umesh):  # fmt: skip
                    with isl.temp_aspect():
                        rect_isl = self.to_rect_isl(isl)
                        if rect_isl:
                            yield rect_isl  # TODO: Add test for avoid issues with face tags.

    def to_rect_isl(self, isl: AdvIsland):

        is_boundary = utils.is_boundary_func(isl.umesh)

        # TODO: Add faces selected.
        boundary_corners = [crn for crn in isl.corners_iter() if is_boundary(crn)]
        boundary_segments = utypes.Segments.from_corners(boundary_corners, isl.umesh)

        if not boundary_segments:
            return None

        # if isl.is_full_face_selected():
        #     # Cace with more than 4 breaks on border loops.
        #     # Cace with mno breaks (get by bbox).
        #
        #     boundary_segments.rotate_longest_to_first()
        #     long_seg = boundary_segments[0]
        #
        #
        #
        #     return None

        # NOTE: value == total selected corners
        for border_seg in boundary_segments:
            border_seg.value = self.total_selected_crn(border_seg)

        # Check 4 point Rect (4 selected points in one border loop)
        if any(b_seg.value == 4 for b_seg in boundary_segments):
            for border_seg in boundary_segments:
                if border_seg.value == 4:
                    four_groups = self.split_to_four_groups(border_seg)
                    assert len(four_groups) == 4
                    four_groups.rotate_longest_to_first()
                    return isl, four_groups

        # Check Ring (two border loops and 2 selected points)
        elif (
            len(boundary_segments) == 2
            and boundary_segments[0].value == 1
            and boundary_segments[1].value == 1
        ):
            try:
                return isl, self.two_pt_ring_lg_to_rect(boundary_segments, isl)

            except Exception as e:
                import traceback
                from .. import info
                self.report({"ERROR"}, f"{info.bugreport_info}: \n {e}")
                traceback.print_exc()
                return None

        # Single pointer case.
        elif (not (isl.umesh.sync and not utils.USE_GENERIC_UV_SYNC)  # Skip for legacy sync (or make ViewBox filter).
              and isl.umesh.elem_mode in ("VERT", "EDGE")
              and (len(boundary_segments) >= 2 and sum(seg.value for seg in boundary_segments) == 1)):
            four_groups = self.one_pt_ring_lg_to_rect(boundary_segments, isl)
            if four_groups:
                return isl, four_groups

        # elif utypes.IslandsBase.island_filter_is_partial_face_selected(isl.faces, isl.umesh)
            #
        # elif utypes.IslandsBase.island_filter_is_partial_vert_selected(isl.faces, isl.umesh):
            # 4 pt
            # 1 pt

        # if isl.select():
        #     pass
        return None

    def finished_rect(self, isl: AdvIsland, four_seg: Segments):
        for seg in four_seg:
            if not seg.chain_linked_corners:
                seg.calc_chain_linked_corners()

        short_paths: list[Segment] = []
        include_corners = set(isl.corners_iter())

        for idx, seg in enumerate(four_seg):
            if seg.has_intervals:
                short_paths.append(seg)
                continue
            prioritize_corners = set()
            for crn_chain in seg.chain_linked_corners:
                prioritize_corners.update(crn_chain)

            #  Add to exclude other 3 corners, to avoid collisions
            exclude_corners = set()
            for exclude_seg in [four_seg[idx - 1], four_seg[idx - 2], four_seg[idx - 3]]:
                for linked in exclude_seg.chain_linked_corners:
                    exclude_corners.update(linked)

            short_path = utils.ShortPath.calc_path_uv_vert(
                seg.start_orig_crn,
                seg.end_orig_crn,
                isl.umesh,
                include_corners,
                exclude_corners,
                prioritize_corners,
                1.0 - self.border_priority,
            )
            assert len(short_path), f"Not found short path {idx!r}."
            short_paths.append(short_path)

        segments = Segments(short_paths, isl.umesh)
        segments.rotate_longest_to_first()

        v_corners = []
        h_corners = []
        start = segments[0].is_horizontal_by_bbox(aspect_y=1.2) # TODO: Orient by inner short path.
        for i, lg in enumerate(segments, start=int(start)):
            if (i % 2) == 0:
                v_corners.extend([a.orig_crn for a in lg])
            else:
                h_corners.extend([a.orig_crn for a in lg])

        assert v_corners
        assert h_corners
        isl.set_corners_tag(True)
        utils.uv_parametrizer.unwrap_isl_by_tag_v2(
            isl,
            unwrap_along="UV",
            use_abf=True,
            topology_from_uvs=True,
            constraints_factor=100.0,
            constr_correction_weight=4.0,
            constr_edge_weight=0.1,
            constraints=(h_corners, v_corners, []),
        )
