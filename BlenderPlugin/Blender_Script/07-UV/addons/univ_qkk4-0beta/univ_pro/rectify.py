# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy
from math import isclose, sqrt
import itertools

from mathutils import Vector, Matrix
from mathutils.geometry import area_tri
from bmesh.types import BMLoopUV

from .. import utils
from collections import deque
from ..preferences import prefs
from ..utypes import UMeshes, IslandsBase, AdvIslands, AdvIsland, LoopGroup, LoopGroups, Segment, AdvCorner


class RectIsl:
    def __init__(self, isl: AdvIsland, groups: LoopGroups):
        self.isl: AdvIsland = isl
        self.lgs: LoopGroups = groups
        self.prev_pos: Vector | utils.NoInit = utils.NoInit()
        self._is_unpinned_exist: bool | None = None
        self.is_flipped_to_preserve_flip = False

    def has_unpinned(self):
        if self._is_unpinned_exist is None:
            assert len(self.lgs) == 4
            self._is_unpinned_exist = any(lg.has_unpinned for lg in self.lgs)
        return self._is_unpinned_exist

    def prepare_island_for_scale_reset(self):
        self.prev_pos = self.get_curr_pos()
        self.isl.value = self.prev_pos

        self.isl.calc_tris_simple()
        self.isl.calc_flat_uv_coords(save_triplet_=True)
        self.isl.calc_flat_unique_uv_coords()
        self.isl.calc_flat_3d_coords(save_triplet=True)
        self.isl.calc_area_3d(areas_to_weight=True)

    def get_curr_pos(self):
        return self.lgs[0][0][self.isl.umesh.uv].uv.copy()

    def individual_scale(self):
        from .. import operators
        operators.texel.UNIV_OT_ResetScale.individual_scale(self.isl, 'XY', shear=False, threshold=1e-07)

    def individual_scale_final(self):
        threshold = 1e-7
        uv_coords_and_3d_vectors_and_3d_areas = []
        for flat, (va, vb, vc), w, tris in zip(self.isl.flat_coords, self.isl.flat_3d_coords, self.isl.weights, self.isl.tris):
            if tris[0].face.tag:
                vectors_ac_bc = (va - vc, vb - vc)
                uv_coords_and_3d_vectors_and_3d_areas.append((flat, vectors_ac_bc, w))

        for j in range(5):
            scale_cou = 0.0
            scale_cov = 0.0

            for (uv_a, uv_b, uv_c), (vec_ac, vec_bc), weight in uv_coords_and_3d_vectors_and_3d_areas:
                if isclose(area_tri(uv_a, uv_b, uv_c), 0, abs_tol=threshold):
                    continue
                m = Matrix((uv_a - uv_c, uv_b - uv_c))
                try:
                    m.invert()
                except ValueError:
                    continue

                cou = m[0][0] * vec_ac + m[0][1] * vec_bc
                cov = m[1][0] * vec_ac + m[1][1] * vec_bc

                scale_cou += cou.length * weight
                scale_cov += cov.length * weight

            if scale_cou * scale_cov < 1e-10:
                break

            scale_factor_u = sqrt(scale_cou / scale_cov)
            if isclose(scale_factor_u, 1.0, abs_tol=1e-5):  # Trade accuracy for performance.
                break

            scale = Vector((scale_factor_u, 1.0 / scale_factor_u))
            for uv_coord in self.isl.flat_unique_uv_coords:
                uv_coord *= scale

    def tag_inner_rect_face(self):
        uv = self.isl.umesh.uv
        for f in self.isl:
            f.tag = False
        f_index = self.isl[0].index

        for lg in self.lgs:
            if lg.has_unpinned():
                continue
            for crn in lg:

                face = crn.face
                if face.tag:
                    continue
                face.tag = True

                parts_of_island = [face]
                temp = []

                while parts_of_island:
                    for f in parts_of_island:
                        for crn_ in f.loops:
                            if crn_[uv].pin_uv and crn_.link_loop_next[uv].pin_uv:
                                continue
                            shared_crn = crn_.link_loop_radial_prev
                            ff = shared_crn.face
                            if ff.tag or ff.index != f_index:
                                continue
                            temp.append(ff)
                            ff.tag = True

                    parts_of_island = temp
                    temp = []


# TODO: Add only short path mode, without boundary correction (bugs on cube with subdiv)
class RectifyBase:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aspect: float = 1.0
        self.bound_priority_factor = 0.95
        self.umeshes: UMeshes | None = None
        # Exclude islands, so that you don't accidentally unwrap
        self.pinned_crn_from_excluded_isl: list[list[BMLoopUV]] = []
        self.rect_lg_groups_with_isl_of_mesh: list[list[RectIsl]] = []

    @staticmethod
    def rect_lgs_to_distribute(groups: LoopGroups):
        # TODO: Add distribute by mask and get intervals from short path if unpinned exist
        #  or validate short path by angle  (bugs on cube with subdiv)
        uv = groups.umesh.uv

        first_lg = groups[0]
        card_vec = utils.vec_to_cardinal(first_lg.get_vector())
        start = first_lg.src[uv].uv
        end = start + (card_vec * first_lg.length_uv)
        first_lg.distribute(start, end)

        prev_lg = groups[-1]
        next_lg = groups[1]
        inter_avg_length = (prev_lg.length_uv + next_lg.length_uv) / 2

        end = prev_lg.dst[uv].uv
        start = end + (inter_avg_length * card_vec.orthogonal())
        prev_lg.distribute(start, end)

        start = next_lg.src[uv].uv
        end = start + (inter_avg_length * card_vec.orthogonal())
        next_lg.distribute(start, end)

        last_lg = groups[2]
        last_lg.distribute(last_lg.src[uv].uv, last_lg.dst[uv].uv)

    @staticmethod
    def has_four_selected_crn(lg):
        vert_select_get = utils.vert_select_get_func(lg.umesh)
        return sum(vert_select_get(crn) for crn in lg) == 4

    @staticmethod
    def total_selected_crn(lg):
        vert_select_get = utils.vert_select_get_func(lg.umesh)
        return sum(vert_select_get(crn) for crn in lg)

    @staticmethod
    def selected_to_first(lg):
        vert_select_get = utils.vert_select_get_func(lg.umesh)
        for idx, crn, in enumerate(lg):
            if vert_select_get(crn):
                if idx == 0:
                    return
                lg.corners = lg.corners[idx:] + lg.corners[:idx]
                return
        raise ValueError('Selected vertices not found')

    @staticmethod
    def target_to_first(lg, target_crn):
        for idx, crn, in enumerate(lg):
            if crn == target_crn:
                if idx == 0:
                    return
                lg.corners = lg.corners[idx:] + lg.corners[:idx]
                return
        raise ValueError('Selected vertices not found')

    @classmethod
    def split_to_four_groups(cls, border_lg: LoopGroup) -> deque[LoopGroup] | None:
        cls.selected_to_first(border_lg)

        vert_select_get = utils.vert_select_get_func(border_lg.umesh)
        groups = deque()
        start_idx = 0

        it = iter(border_lg.corners)
        next(it)
        for idx, crn in enumerate(it, start=1):
            if vert_select_get(crn):
                lg = LoopGroup(border_lg.umesh)
                lg.corners = border_lg.corners[start_idx:idx]
                groups.append(lg)
                start_idx = idx
                if len(groups) == 3:
                    lg = LoopGroup(border_lg.umesh)
                    lg.corners = border_lg.corners[start_idx:]
                    groups.append(lg)
                    return groups
        return groups

    def apply_aspect_ratio(self, isl):
        scale = Vector((self.aspect, 1))
        isl.scale_simple(scale)

    def reset_aspect_ratio(self, isl):
        scale = Vector((1 / self.aspect, 1))
        isl.scale_simple(scale)


class RectifyFour(RectifyBase):

    @classmethod
    def four_pt_border_lg_to_rect(cls, border_lg: LoopGroup, isl: AdvIsland, bound_priority_factor: float):
        assert border_lg.value == 4
        four_groups = cls.split_to_four_groups(border_lg)
        assert len(four_groups) == 4

        for lg in four_groups:
            lg.length_uv  # noqa
            lg.calc_chain_linked_corners()

        prioritize_corners = set()
        for crn_chain in border_lg.chain_linked_corners:
            prioritize_corners.update(crn_chain)

        for idx, lg in enumerate(four_groups):
            exclude_corners_group = [four_groups[idx-1], four_groups[idx-2], four_groups[idx-3]]
            short_path = utils.ShortPath.calc_path_uv_vert(isl, lg.src, lg.dst,
                                                           exclude_corners_group,
                                                           prioritize_corners,
                                                           bound_priority_factor)
            # Get pin mask
            lg.calc_chain_linked_corners_mask_from_short_path(short_path)
            if not all(lg.chain_linked_corners_mask):  # is unpinned exist
                # The lengths by short path are more correct, we take them to avoid large stretches
                length_3d, length_uv = utils.ShortPath.calc_length_3d_and_uv_from_path(short_path, lg.umesh)
                lg.length_3d = length_3d
                lg.length_uv = length_uv
            else:
                lg.calc_length_uv()

        max_length_lg = max(four_groups, key=lambda lg_m: lg_m.length_3d)
        four_groups.rotate(-four_groups.index(max_length_lg))

        groups = LoopGroups(list(four_groups), border_lg.umesh)
        cls.rect_lgs_to_distribute(groups)

        return groups


class RectifyRing(RectifyBase):
    @classmethod
    def two_pt_ring_lg_to_rect(cls, border_lgs: LoopGroups, isl: AdvIsland, bound_priority_factor: float):
        four_groups: LoopGroups = cls.two_pt_ring_lg_to_rect_ex(border_lgs, isl)

        for idx, lg in enumerate(four_groups):
            lg.length_uv  # noqa
            if idx in (0, 2):
                for crn in lg:
                    crn.edge.seam = True
                continue
            lg.calc_chain_linked_corners()

        prioritize_corners = set()
        for border_lg in border_lgs:
            prioritize_corners.update(border_lg.corners)

        for idx, lg in enumerate(four_groups):
            if idx in (0, 2):
                lg.calc_length_uv()
                continue
            exclude_corners_group = [four_groups[idx - 1], four_groups[idx - 2], four_groups[idx - 3]]
            short_path = utils.ShortPath.calc_path_uv_vert(isl, lg.src, lg.dst,
                                                           exclude_corners_group,
                                                           prioritize_corners,
                                                           bound_priority_factor)
            lg.calc_chain_linked_corners_mask_from_short_path(short_path)
            if not all(lg.chain_linked_corners_mask):  # is unpinned exist
                # The lengths by short path are more correct, we take them to avoid large stretches
                length_3d, length_uv = utils.ShortPath.calc_length_3d_and_uv_from_path(short_path, lg.umesh)
                lg.length_3d = length_3d
                lg.length_uv = length_uv
            else:
                lg.calc_length_uv()

        cls.rect_lgs_to_distribute(four_groups)

        return four_groups

    @classmethod
    def two_pt_ring_lg_to_rect_ex(cls, boundary_loop_groups: LoopGroups, isl: AdvIsland):
        assert len(boundary_loop_groups) == 2

        umesh = isl.umesh
        uv = umesh.uv

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

        segment = cls.find_one_edge_short_path(umesh, lg_a.src, lg_b.src)
        if segment is None:
            short_path = utils.ShortPath.calc_path_uv_vert(isl, lg_a.src, lg_b.src,
                                                           (),
                                                           prioritize_corners,
                                                           0.5)

            segment = cls.short_path_to_segment(umesh, short_path)

        cls.clip_start_end_segment_by_pair(segment)

        loop_groups = cls.split_to_ring_segments(segment, lg_a, lg_b)

        for linked in loop_groups[0].chain_linked_corners:
            for crn in linked:
                crn[uv].uv += Vector((1e-5, 1e-5))

        # Clear prioritize borders
        for border_lg in boundary_loop_groups:
            border_lg.chain_linked_corners = []

        return loop_groups

    @staticmethod
    def clip_start_end_segment_by_pair(seg):
        """[0,0,1,1,1,0,1] -> [1,1,1]"""
        it = itertools.dropwhile(lambda adv_crn: not adv_crn.is_pair, seg)
        seg.seg = list(itertools.takewhile(lambda adv_crn: adv_crn.is_pair, it))
        assert seg.seg

    @classmethod
    def split_to_ring_segments(cls, seg_a: Segment, border_a, border_b):
        """LoopGroups = inner_a -> border_b -> inner_b -> border_a"""
        uv = seg_a.umesh.uv

        seg_b = seg_a.deepcopy()
        seg_b.reverse()

        for adv_crn in seg_a:
            adv_crn.is_pair = False
            adv_crn.edge.seam = True

        for adv_crn in seg_b:
            adv_crn.is_pair = False

        # Inner A
        chain_a = []
        for adv_crn in seg_a:
            crn = adv_crn.crn
            chain = utils.linked_crn_to_vert_pair_by_idx_with_seam(crn, uv)
            chain.append(crn)
            chain_a.append(chain)

        crn = seg_a[-1].crn.link_loop_next
        chain = utils.linked_crn_to_vert_pair_by_idx_with_seam(crn, uv)
        chain.insert(0, crn)
        chain_a.append(chain)

        inner_a = LoopGroup(seg_a.umesh)
        inner_a.corners = [adv_crn.crn for adv_crn in seg_a]
        inner_a.chain_linked_corners = chain_a
        inner_a.chain_linked_corners_mask = [True] * len(chain_a)
        inner_a.is_unpinned_exist_ = False

        # TODO: Improve that
        # TODO: In a normal situation, if the short path runs orthogonal to the border,
        #  everything is fine - the last corner is always valid.
        #  But when the short path runs diagonally, you need to iterate through all linked corners.
        for border_crn_b in reversed(chain_a[-1]):
            try:
                cls.target_to_first(border_b, border_crn_b)
                break
            except ValueError:
                continue
        else:
            raise ValueError('Failed to move border edges to the beginning')

        # Inner B
        chain_b = []
        for adv_crn in seg_b:
            crn = adv_crn.crn
            chain = utils.linked_crn_to_vert_pair_by_idx_with_seam(crn, uv)
            chain.append(crn)
            chain_b.append(chain)

        inner_b = LoopGroup(seg_b.umesh)
        inner_b.corners = [adv_crn.crn for adv_crn in seg_b]
        inner_b.chain_linked_corners = chain_b
        inner_b.chain_linked_corners_mask = [True] * len(chain_b)
        inner_b.is_unpinned_exist_ = False

        crn = seg_b[-1].crn.link_loop_next
        chain = utils.linked_crn_to_vert_pair_by_idx_with_seam(crn, uv)
        chain.insert(0, crn)
        chain_b.append(chain)

        for border_crn_a in reversed(chain_b[-1]):
            try:
                cls.target_to_first(border_a, border_crn_a)
                break
            except ValueError:
                continue
        else:
            raise ValueError('Failed to move border edges to the beginning')

        return LoopGroups([inner_a, border_b, inner_b, border_a], seg_a.umesh)

    @staticmethod
    def find_one_edge_short_path(umesh, first_crn, next_crn):
        """Quickly finds dst crn in the range of one step"""
        from ..utypes import AdvCorner
        uv = umesh.uv
        segment = []

        next_vert = next_crn.vert
        for l_crn in utils.linked_crn_uv_by_idx_unordered_included(first_crn, uv):
            if next_vert == l_crn.link_loop_next.vert:
                if next_crn in utils.linked_crn_uv_by_idx_unordered_included(l_crn.link_loop_next, uv):
                    segment.append(AdvCorner(l_crn, uv))
                    return Segment(segment, umesh)
        return None

    @staticmethod
    def short_path_to_segment(umesh, short_path):
        uv = umesh.uv
        segment = []
        for next_idx, crn in enumerate(short_path[:-1], start=1):
            next_crn = short_path[next_idx]
            next_vert = next_crn.vert
            linked = utils.linked_crn_uv_by_idx_unordered_included(crn, uv)

            continue_ = False
            for l_crn in linked:
                if next_vert == l_crn.link_loop_next.vert:
                    if next_crn in utils.linked_crn_uv_by_idx_unordered_included(l_crn.link_loop_next, uv):
                        segment.append(AdvCorner(l_crn, uv))
                        continue_ = True
                        break
            if continue_:
                continue

            for l_crn in linked:
                if next_vert == l_crn.link_loop_prev.vert:
                    if next_crn in utils.linked_crn_uv_by_idx_unordered_included(l_crn.link_loop_prev, uv):
                        segment.append(AdvCorner(l_crn, uv, invert=True))
                        break
        return Segment(segment, umesh)


# noinspection PyTypeHints
class UNIV_OT_Rectify(bpy.types.Operator, RectifyFour, RectifyRing):
    """
    1)
    2) Calc Loop Groups by tagged borders
    3) Filtering to Ring or Four Point Rect
    4) Get 4 Loop Groups -> Distribute -> Set pins by mask (mask got from short path)
    5) Mark Seam -> Select -> Unwrap
    6) Final -
    """
    bl_idname = 'uv.univ_rectify'
    bl_label = 'Rectify'
    bl_description = "Align selected UV 4 or 2 point to rectangular distribution"
    bl_options = {'REGISTER', 'UNDO'}

    xy_scale: bpy.props.BoolProperty(name='Scale Independently', default=True,
                                     description='Scale U and V independently')
    user_boundary_priority_factor: bpy.props.FloatProperty(name='Boundary priority factor', default=0.05, min=0,
                                                           soft_max=0.3, max=0.5)
    use_aspect: bpy.props.BoolProperty(name='Correct Aspect', default=True)

    @classmethod
    def poll(cls, context):
        tool_settings = context.scene.tool_settings
        if tool_settings.use_uv_select_sync:
            if tool_settings.mesh_select_mode[:] != (True, False, False):
                return False
        else:
            if tool_settings.uv_select_mode != 'VERTEX':
                return False
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'user_boundary_priority_factor', slider=True)
        layout.prop(self, 'xy_scale')
        layout.prop(prefs(), 'use_texel')
        layout.prop(self, 'use_aspect')

    def execute(self, context):
        if context.area.ui_type != 'UV':
            self.report({'WARNING'}, 'Active area must be UV')  # need for unwrap  # TODO: Add unwrap.poll
            return {'CANCELLED'}

        self.umeshes = UMeshes(report=self.report)
        self.umeshes.fix_context()
        # NOTE: Aspect is not saved in umesh.aspect to avoid problems with individual_scale
        self.aspect = utils.get_aspect_ratio() if self.use_aspect else 1.0
        self.bound_priority_factor = 1 - self.user_boundary_priority_factor
        self.umeshes.filter_by_selected_uv_verts()
        self.pinned_crn_from_excluded_isl: list[list[BMLoopUV]] = []
        # Separating by mesh is important to avoid a lot of tagging
        self.rect_lg_groups_with_isl_of_mesh: list[list[RectIsl]] = []

        self.rectify()

        return self.umeshes.update()

    def rectify(self):
        self.prepare()

        if not self.rect_lg_groups_with_isl_of_mesh:
            self.restore_pins_and_selection()
            self.report({'WARNING'}, 'Did not find 4 selected boundary points or 2 boundary points on the ring.')
            return

        for rect_lg_groups_with_isl in self.rect_lg_groups_with_isl_of_mesh:
            for rect_isl in rect_lg_groups_with_isl:
                rect_isl.isl.set_pins(False)
                rect_isl.isl.select = True
                rect_isl.isl.mark_seam()
                if self.xy_scale:
                    rect_isl.prepare_island_for_scale_reset()

                rect_isl.lgs.set_pins_by_mask()  # Set pin
                rect_isl.has_unpinned()

        bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=False, use_subsurf_data=False, margin=0)

        # Reset Scale
        if self.xy_scale:
            for rect_lg_groups_with_isl in self.rect_lg_groups_with_isl_of_mesh:
                for rect_isl in rect_lg_groups_with_isl:
                    rect_isl.individual_scale()

        # Reset Scale again
        self.finished_rect()

        # Reset Scale again
        if self.xy_scale:
            for rect_lg_groups_with_isl in self.rect_lg_groups_with_isl_of_mesh:
                for rect_isl in rect_lg_groups_with_isl:
                    rect_isl.individual_scale()
                    rect_isl.isl.set_position(rect_isl.prev_pos, rect_isl.get_curr_pos())

        if prefs().use_texel:
            texel = prefs().texel_density
            texture_size = (int(prefs().size_x) + int(prefs().size_y)) / 2

            for rect_lg_groups_with_isl in self.rect_lg_groups_with_isl_of_mesh:
                for rect_isl in rect_lg_groups_with_isl:
                    isl = rect_isl.isl
                    if isl.area_3d == -1 or isl.umesh.check_uniform_scale() is not None:
                        isl.calc_area_3d(isl.umesh.check_uniform_scale())
                    if isl.area_uv == -1:
                        isl.calc_area_uv()
                    isl.set_texel(texel, texture_size)

        bpy.ops.uv.select_all(action='DESELECT')

        self.restore_pins_and_selection()

    def restore_pins_and_selection(self):
        if utils.USE_GENERIC_UV_SYNC:
            umeshes = {r_isl.isl.umesh for rect_groups in self.rect_lg_groups_with_isl_of_mesh for r_isl in rect_groups}
            for u in umeshes:
                utils.fast_deselect(u)

        for rect_lg_groups_with_isl in self.rect_lg_groups_with_isl_of_mesh:
            for rect_isl in rect_lg_groups_with_isl:
                if rect_isl.is_flipped_to_preserve_flip:
                    rect_isl.isl.scale_simple(Vector((-1.0, 1.0)))
                self.reset_aspect_ratio(rect_isl.isl)
                rect_isl.lgs.set_pins(False)

                umesh = rect_isl.isl.umesh
                select_vert = utils.vert_select_func(umesh)
                for g in rect_isl.lgs:
                    for crn in g.chain_linked_corners[0]:
                        select_vert(crn)

        for pinned_crn in self.pinned_crn_from_excluded_isl:
            for crn_uv in pinned_crn:
                crn_uv.pin_uv = False

    def prepare(self):
        for umesh in self.umeshes:
            islands = AdvIslands.calc_visible_with_mark_seam(umesh)
            if islands:
                rect_islands: list[RectIsl] = []
                umesh.set_corners_tag(False)

                islands.indexing()
                for isl in islands:
                    if not IslandsBase.island_filter_is_any_vert_selected(isl.faces, umesh):
                        # Pin and skip
                        if self.umeshes.sync:
                            pinned_corners = isl.set_pins(True, with_pinned=True)
                            self.pinned_crn_from_excluded_isl.append(pinned_corners)
                        continue

                    isl.set_boundary_tag(match_idx=True)
                    rect_isl = self.to_rect_isl(isl)
                    if rect_isl:
                        rect_islands.append(rect_isl)
                        isl.set_corners_tag(False)
                        continue

                    isl.set_corners_tag(False)

                    # Pin or unselect - not matched, to avoid unwrap
                    if isl.umesh.sync:
                        pinned_corners = isl.set_pins(True, with_pinned=True)
                        self.pinned_crn_from_excluded_isl.append(pinned_corners)
                    else:
                        isl.select = False

                if rect_islands:
                    self.rect_lg_groups_with_isl_of_mesh.append(rect_islands)

    def to_rect_isl(self, isl: AdvIsland):
        # NOTE: value == total selected corners
        boundary_loop_groups = LoopGroups.calc_by_boundary_crn_tags(isl)
        if not boundary_loop_groups:
            return None

        for b_lg in boundary_loop_groups:
            b_lg.value = self.total_selected_crn(b_lg)

        # Check Ring (two border loops and 2 selected points)
        if (len(boundary_loop_groups) == 2 and
                boundary_loop_groups[0].value == 1 and
                boundary_loop_groups[1].value == 1):
            try:
                self.apply_aspect_ratio(isl)
                flipped = isl.should_flip_after_unwrap()
                if flipped:
                    isl.scale_simple(Vector((-1.0, 1.0)))
                groups = self.two_pt_ring_lg_to_rect(boundary_loop_groups, isl, self.bound_priority_factor)

                rect_isl = RectIsl(isl, groups)
                rect_isl.is_flipped_to_preserve_flip = flipped
                return rect_isl

            except Exception as e:
                from .. import info
                self.report({'ERROR'}, f'{info.bugreport_info}: \n {e}')
                import traceback
                traceback.print_exc()
                return None

        # Check 4 point Rect (4 selected points in one border loop)
        elif any(b_lg.value == 4 for b_lg in boundary_loop_groups):
            for b_lg in boundary_loop_groups:
                if b_lg.value == 4:
                    self.apply_aspect_ratio(isl)
                    flipped = isl.should_flip_after_unwrap()
                    if flipped:
                        isl.scale_simple(Vector((-1.0, 1.0)))
                    groups = self.four_pt_border_lg_to_rect(b_lg, isl, self.bound_priority_factor)

                    rect_isl = RectIsl(isl, groups)
                    rect_isl.is_flipped_to_preserve_flip = flipped
                    return rect_isl
        return None

    @staticmethod
    def has_unpinned(rect_sequence: list[list[RectIsl]] | list[RectIsl]):
        for seq in rect_sequence:
            if isinstance(seq, list):
                for rect_isl in seq:
                    if rect_isl.has_unpinned():
                        return True
            else:
                if seq.has_unpinned():  # noqa
                    return True
        return False

    def finished_rect(self):
        if not self.has_unpinned(self.rect_lg_groups_with_isl_of_mesh):
            return

        loop_groups_from_path = []
        for rect_lg_groups_with_isl in self.rect_lg_groups_with_isl_of_mesh:
            if not self.has_unpinned(rect_lg_groups_with_isl):
                continue

            umesh = rect_lg_groups_with_isl[0].isl.umesh
            umesh.set_corners_tag(False)
            uv = umesh.uv
            for rect_isl in rect_lg_groups_with_isl:
                if not rect_isl.has_unpinned():
                    continue
                # Restore indexes after unwrap (check resetting)
                # NOTE: The previous index is not saved, a potential conflict is possible.
                isl_idx = rect_isl.isl[0].index
                for f in rect_isl.isl:
                    f.index = isl_idx

                for idx, lg in enumerate(rect_isl.lgs):
                    if lg.has_unpinned():
                        prioritize_corners = set()
                        for crn_chain in lg.chain_linked_corners:
                            prioritize_corners.update(crn_chain)

                        # Add to exclude other 3 corners, to avoid collisions
                        exclude_corners_group = [rect_isl.lgs[idx-1], rect_isl.lgs[idx-2], rect_isl.lgs[idx-3]]
                        short_path = utils.ShortPath.calc_path_uv_vert(rect_isl.isl, lg.src, lg.dst,
                                                                       exclude_corners_group,
                                                                       prioritize_corners,
                                                                       self.bound_priority_factor)

                        lg_from_path = utils.ShortPath.path_to_loop_group_for_rect(short_path, umesh)
                        lg_from_path.set_pins()
                        lg_from_path.distribute(lg.src[uv].uv, lg.dst[uv].uv)
                        loop_groups_from_path.append(lg_from_path)

                    if self.xy_scale:
                        # Reset scale for inner faces
                        rect_isl.tag_inner_rect_face()
                        rect_isl.individual_scale_final()

                rect_isl.isl.set_corners_tag(False)

        bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=False, use_subsurf_data=False, margin=0)

        for lg in loop_groups_from_path:
            lg.set_pins(False)
