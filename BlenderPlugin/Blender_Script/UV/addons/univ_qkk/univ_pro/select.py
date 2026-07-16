# SPDX-FileCopyrightText: 2024 Oxicid
# SPDX-License-Identifier: GPL-3.0-or-later

if 'bpy' in locals():
    from .. import reload
    reload.reload(globals())

import bpy
import math
import bmesh

from bpy.props import *
from bpy.types import Operator
from collections.abc import Callable
from bmesh.types import BMEdge, BMFace

from .. import utils
from ..utypes import FaceIsland, Islands, MeshIslands, UMeshes, AdvIslands
from ..operators import select


# noinspection PyTypeHints
class UNIV_OT_Select_Flat(Operator):
    bl_idname = 'uv.univ_select_flat'
    bl_label = 'Flat'
    bl_description = "Select linked flat faces"
    bl_options = {'REGISTER', 'UNDO'}

    angle: FloatProperty(name='Angle',
                         default=math.radians(15),
                         min=math.radians(0.1),
                         max=math.radians(180),
                         soft_min=math.radians(1),
                         soft_max=math.radians(89),
                         subtype='ANGLE'
                         )
    clamp_by_seams: BoolProperty(name='Clamp by Seams', default=True)
    grow_method: EnumProperty(name='Grow Method', default='ABSOLUTE',
                              items=(('ABSOLUTE', 'Absolute', ''), ('RELATIVE', 'Relative', '')))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.umeshes: UMeshes | None = None
        self.need_sync_validation_check = False

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'angle', slider=True)
        layout.prop(self, 'clamp_by_seams')
        layout.row(align=True).prop(self, 'grow_method', expand=True)

    def invoke(self, context, event):
        if event.value == 'PRESS':
            return self.execute(context)

        self.grow_method = 'RELATIVE' if event.alt else 'ABSOLUTE'
        return self.execute(context)

    def execute(self, context):
        self.umeshes = UMeshes(report=self.report)
        self.umeshes.filter_by_partial_selected_uv_faces()
        self.umeshes.update_tag = False

        if not self.umeshes:
            self.report({'WARNING'}, "Not found selected faces to extend selection.")
            return {'CANCELLED'}

        self.need_sync_validation_check = False
        if self.umeshes.sync:
            if utils.USE_GENERIC_UV_SYNC:
                self.need_sync_validation_check = self.umeshes.elem_mode in ('VERT', 'EDGE')

        # TODO: For pick system cache face by angle

        if self.grow_method == 'ABSOLUTE':
            self.select_absolute_uv()
        else:
            self.select_relative_uv()
        self.umeshes.update(info="Not found flat linked faces for extend selection.")
        return {'FINISHED'}


    def select_absolute_uv(self):
        for umesh in self.umeshes:
            is_boundary = utils.is_boundary_func(umesh, with_seam=self.clamp_by_seams)
            if self.clamp_by_seams:
                islands = Islands.calc_partial_selected_with_mark_seam(umesh)
            else:
                islands = Islands.calc_partial_selected(umesh)

            for isl in islands:
                isl.tag_selected_faces()

                stack = []
                selected_faces = []
                for f in isl:
                    if f.tag:
                        continue
                    min_angle = float('inf')
                    min_angle_face = None
                    for crn in f.loops:
                        new_face_angle = crn.edge.calc_face_angle(999.0)
                        if new_face_angle <= self.angle:
                            pair_crn = crn.link_loop_radial_prev
                            if pair_crn.face.tag and not is_boundary(crn):
                                if new_face_angle < min_angle:
                                    min_angle = new_face_angle
                                    min_angle_face = crn.face
                    if min_angle_face:
                        selected_faces.append(min_angle_face)
                        stack.append(f)
                if not selected_faces:
                    continue
                for f in isl:
                    f.index = -1
                isl.umesh.update_tag = True

                normals = [f.normal for f in selected_faces]

                for idx, stack_face in enumerate(stack):
                    stack_face.index = idx
                    stack_face.tag = True

                cos_angle = math.cos(self.angle)
                while stack:
                    temp = []
                    for stack_face in stack:
                        stack_face_idx = stack_face.index
                        for crn in stack_face.loops:
                            pair_crn = crn.link_loop_radial_prev
                            pair_crn_face = pair_crn.face

                            if pair_crn_face.tag or is_boundary(crn):
                                continue

                            angle_cos = normals[stack_face_idx].dot(pair_crn_face.normal)
                            if angle_cos >= cos_angle:
                                if pair_crn_face.index == -1:
                                    pair_crn_face.index = stack_face_idx
                                    temp.append(pair_crn_face)
                                else:
                                    angle_cos_first = normals[pair_crn_face.index].dot(pair_crn_face.normal)
                                    if angle_cos > angle_cos_first:
                                        pair_crn_face.index = stack_face_idx

                    if self.need_sync_validation_check:
                        umesh.sync_from_mesh_if_needed()
                    FaceIsland(stack, umesh).select = True
                    for f in temp:
                        f.tag = True
                    stack = temp

    def select_relative_uv(self):
        for umesh in self.umeshes:
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
                if self.need_sync_validation_check:
                    umesh.sync_from_mesh_if_needed()
                FaceIsland(selected_faces, umesh).select = True
                umesh.update_tag = True


class UNIV_OT_Select_Flat_VIEW3D(UNIV_OT_Select_Flat):
    bl_idname = 'mesh.univ_select_flat'

    def execute(self, context):
        self.umeshes = UMeshes.calc(report=self.report, verify_uv=False)
        self.umeshes.set_sync()
        self.umeshes.sync_invalidate()

        self.umeshes.filter_by_partial_selected_uv_faces()
        self.umeshes.update_tag = False
        if not self.umeshes:
            self.report({'WARNING'}, "Not found selected faces to extend selection.")
            return {'CANCELLED'}

        if self.grow_method == 'ABSOLUTE':
            self.select_absolute_3d()
        else:
            self.select_relative_3d()

        self.umeshes.update(info="Not found linked flat faces for extend selection.")
        return {'FINISHED'}

    def select_absolute_3d(self):
        for umesh in self.umeshes:
            if self.clamp_by_seams:
                # TODO: Replace islands with visited set for speedup.
                # Need iterate over all selected faces, collect their normals,
                # and sort them by the smallest growth angles.

                # Then, for each grown face, iterate over neighboring selected and already grown faces and take the smallest vectors from them.
                islands = MeshIslands.calc_partial_selected_with_mark_seam(umesh)
            else:
                islands = MeshIslands.calc_partial_selected(umesh)

            for isl in islands:
                isl.tag_selected_faces()

                stack = []
                selected_faces = []
                for f in isl:
                    if f.tag:
                        continue
                    min_angle = float('inf')
                    min_angle_face = None
                    for crn in f.loops:
                        face_angle = crn.edge.calc_face_angle(180.1)
                        if face_angle <= self.angle:
                            pair_crn = crn.link_loop_radial_prev
                            if not (self.clamp_by_seams and crn.edge.seam) and pair_crn.face.tag:
                                if face_angle < min_angle:
                                    min_angle = face_angle
                                    min_angle_face = crn.face
                    if min_angle_face:
                        selected_faces.append(min_angle_face)
                        stack.append(f)
                if not selected_faces:
                    continue
                for f in isl:
                    f.index = -1

                normals = [f.normal for f in selected_faces]

                for idx, stack_face in enumerate(stack):
                    stack_face.index = idx
                    stack_face.tag = True

                cos_angle = math.cos(self.angle)
                while stack:
                    temp = []
                    for stack_face in stack:
                        stack_face_idx = stack_face.index
                        for crn in stack_face.loops:
                            pair_crn = crn.link_loop_radial_prev
                            pair_crn_face = pair_crn.face

                            if pair_crn_face.tag or pair_crn_face.hide or (self.clamp_by_seams and crn.edge.seam):
                                continue

                            angle_cos = normals[stack_face_idx].dot(pair_crn_face.normal)
                            if angle_cos >= cos_angle:
                                if pair_crn_face.index == -1:
                                    pair_crn_face.index = stack_face_idx
                                    temp.append(pair_crn_face)
                                else:
                                    try:
                                        # Three and more linked face case.
                                        # TODO: Allow this, used link_loop_radial_next and link_loop_radial_prev
                                        angle_cos_first = normals[pair_crn_face.index].dot(pair_crn_face.normal)
                                    except IndexError:
                                        continue
                                    if angle_cos > angle_cos_first:
                                        pair_crn_face.index = stack_face_idx

                    umesh.sync_valid = False
                    isl.umesh.update_tag = True
                    FaceIsland(stack, umesh).select = True
                    for f in temp:
                        f.tag = True
                    stack = temp

    def select_relative_3d(self):
        for umesh in self.umeshes:
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
                FaceIsland(selected_faces, umesh).select = True
                umesh.sync_valid = False
                umesh.update_tag = True


class CrnEdgeGrow:
    def __init__(self, crn: bmesh.types.BMLoop, uv, invert=False):
        self.crn = crn
        self.invert: bool = invert
        self.uv = uv
        self._vec = None
        self.is_pair = None

    @property
    def vec(self):
        if not self._vec:
            if self.invert:
                self._vec = self.crn.link_loop_prev[self.uv].uv - self.crn[self.uv].uv
            else:
                self._vec = self.crn.link_loop_next[self.uv].uv - self.crn[self.uv].uv
        return self._vec

    @vec.setter
    def vec(self, v):
        self._vec = v

    def angle(self, other: 'typing.Self', max_angle: float):
        # TODO: Use extrapolate vector
        # 2D
        # a = Vector((0.34202, 0.939693))
        # b = Vector((0.642788, 0.766044))
        # extrapolate_vector = b @ Matrix.Rotation(a.angle_signed(b), 2)

        # 3D
        # # Rotate around axis (axis is the normal to the plane A and B)
        # axis = a.cross(b).normalized()
        # theta = a.angle(b)
        #
        # rotation_matrix = mathutils.Matrix.Rotation(theta, 4, axis)
        # v_rotated = rotation_matrix @ b
        return self.vec.angle(other.vec, max_angle)  # noqa

    @property
    def is_pair(self):
        if self._is_pair is None:
            if self.invert:
                pair = self.crn.link_loop_prev.link_loop_radial_prev
                self._is_pair = utils.is_pair_by_idx(self.crn.link_loop_prev, pair, self.uv)
            else:
                pair = self.crn.link_loop_radial_prev
                self._is_pair = utils.is_pair_by_idx(self.crn, pair, self.uv)
        return self._is_pair

    @is_pair.setter
    def is_pair(self, v):
        self._is_pair = v

    def linked_edges(self):
        linked = []
        uv = self.uv
        idx = self.crn.face.index
        if self.is_pair:
            pair = self.crn.link_loop_radial_prev
            uv_co = pair[uv].uv
            pair_prev = pair.link_loop_prev
            if not pair_prev.tag:
                # boundary invert add
                if not utils.is_pair_by_idx(pair_prev, pair_prev.link_loop_radial_prev, uv):
                    eg = CrnEdgeGrow(self.crn, uv, True)
                    eg.is_pair = False
                    linked.append(eg)

            for crn in pair.vert.link_loops:
                if crn.face.index == idx and not crn.tag and crn[uv].uv == uv_co:
                    if crn != pair:
                        if utils.is_pair_by_idx(crn, crn.link_loop_radial_prev, uv):
                            eg = CrnEdgeGrow(crn, uv)
                            eg.is_pair = True
                            linked.append(eg)
                        else:
                            # boundary add
                            eg = CrnEdgeGrow(crn, uv)
                            eg.is_pair = False
                            linked.append(eg)

                        # boundary invert add
                        prev_crn = crn.link_loop_prev
                        if not utils.is_pair_by_idx(prev_crn, prev_crn.link_loop_radial_prev, uv) and \
                                prev_crn != self.crn and not prev_crn.tag:
                            eg = CrnEdgeGrow(crn, uv, True)
                            eg.is_pair = False
                            linked.append(eg)

        else:
            if self.invert:
                prev_crn = self.crn.link_loop_prev
                uv_co = prev_crn[uv].uv

                prev_crn_prev = prev_crn.link_loop_prev
                if not prev_crn_prev.tag:
                    # boundary invert add
                    if not utils.is_pair_by_idx(prev_crn_prev, prev_crn_prev.link_loop_radial_prev, uv):
                        eg = CrnEdgeGrow(prev_crn, uv, True)
                        eg.is_pair = False
                        linked.append(eg)

                for crn in prev_crn.vert.link_loops:
                    if crn.face.index == idx and not crn.tag and crn[uv].uv == uv_co:
                        if crn != prev_crn:
                            if utils.is_pair_by_idx(crn, crn.link_loop_radial_prev, uv):
                                eg = CrnEdgeGrow(crn, uv)
                                eg.is_pair = True
                                linked.append(eg)
                            else:
                                # boundary add
                                eg = CrnEdgeGrow(crn, uv)
                                eg.is_pair = False
                                linked.append(eg)

                            # boundary invert add
                            prev_crn_ = crn.link_loop_prev
                            if not utils.is_pair_by_idx(prev_crn_, prev_crn_.link_loop_radial_prev, uv) and \
                                    prev_crn_ != self.crn and not prev_crn_.tag:
                                eg = CrnEdgeGrow(crn, uv, True)
                                eg.is_pair = False
                                linked.append(eg)
            else:
                next_crn = self.crn.link_loop_next
                uv_co = next_crn[uv].uv

                # add pair
                if utils.is_pair_by_idx(next_crn, next_crn.link_loop_radial_prev, uv):
                    eg = CrnEdgeGrow(next_crn, uv)
                    eg.is_pair = True
                    linked.append(eg)

                for crn in next_crn.vert.link_loops:
                    if crn.face.index == idx and not crn.tag and crn[uv].uv == uv_co:
                        if crn != next_crn:
                            if utils.is_pair_by_idx(crn, crn.link_loop_radial_prev, uv):
                                eg = CrnEdgeGrow(crn, uv)
                                eg.is_pair = True
                                linked.append(eg)
                            else:
                                # boundary add
                                eg = CrnEdgeGrow(crn, uv)
                                eg.is_pair = False
                                linked.append(eg)

                            # boundary invert add
                            prev_crn_ = crn.link_loop_prev
                            if not utils.is_pair_by_idx(prev_crn_, prev_crn_.link_loop_radial_prev, uv) and \
                                    prev_crn_ != self.crn and not prev_crn_.tag:
                                eg = CrnEdgeGrow(crn, uv, True)
                                eg.is_pair = False
                                linked.append(eg)
        return linked

    def linked_edges_contiguous(self):
        # assert self.is_pair
        linked = []
        uv = self.uv
        pair = self.crn.link_loop_radial_prev
        idx = pair.face.index
        uv_co = pair[uv].uv
        for crn in pair.vert.link_loops:
            if crn != pair and crn.face.index == idx and not crn.tag and crn[uv].uv == uv_co:
                if utils.is_pair_by_idx(crn, crn.link_loop_radial_prev, uv):
                    eg = CrnEdgeGrow(crn, uv)
                    eg.is_pair = True
                    linked.append(eg)
        return linked

    def linked_edges_boundary(self):
        # assert not self.is_pair
        linked = []
        uv = self.uv
        idx = self.crn.face.index

        if self.invert:
            prev_crn = self.crn.link_loop_prev
            uv_co = prev_crn[uv].uv

            prev_crn_prev = prev_crn.link_loop_prev
            if not prev_crn_prev.tag:
                # boundary invert add
                if not utils.is_pair_by_idx(prev_crn_prev, prev_crn_prev.link_loop_radial_prev, uv):
                    eg = CrnEdgeGrow(self.crn, uv, True)
                    eg.is_pair = False
                    linked.append(eg)

            for crn in prev_crn.vert.link_loops:
                if crn.face.index == idx and not crn.tag and crn[uv].uv == uv_co:
                    if crn != prev_crn:
                        if not utils.is_pair_by_idx(crn, crn.link_loop_radial_prev, uv):
                            # boundary add
                            eg = CrnEdgeGrow(crn, uv)
                            eg.is_pair = False
                            linked.append(eg)

                        # boundary invert add
                        prev_crn_ = crn.link_loop_prev
                        if not utils.is_pair_by_idx(prev_crn_, prev_crn_.link_loop_radial_prev, uv) and \
                                prev_crn_ != self.crn and not prev_crn_.tag:
                            eg = CrnEdgeGrow(crn, uv, True)
                            eg.is_pair = False
                            linked.append(eg)
        else:
            next_crn = self.crn.link_loop_next
            uv_co = next_crn[uv].uv

            if not utils.is_pair_by_idx(next_crn, next_crn.link_loop_radial_prev, uv):
                eg = CrnEdgeGrow(next_crn, uv)
                eg.is_pair = False
                linked.append(eg)

            for crn in next_crn.vert.link_loops:
                if crn.face.index == idx and not crn.tag and crn[uv].uv == uv_co:
                    if crn != next_crn:
                        if not utils.is_pair_by_idx(crn, crn.link_loop_radial_prev, uv):
                            # boundary add
                            eg = CrnEdgeGrow(crn, uv)
                            eg.is_pair = False
                            linked.append(eg)

                        # boundary invert add
                        prev_crn_ = crn.link_loop_prev
                        if not utils.is_pair_by_idx(prev_crn_, prev_crn_.link_loop_radial_prev, uv) and \
                                prev_crn_ != self.crn and not prev_crn_.tag:
                            eg = CrnEdgeGrow(crn, uv, True)
                            eg.is_pair = False
                            linked.append(eg)
        return linked

    def has_clamp(self, check_seam):
        uv = self.uv
        crn = self.crn
        idx = crn.face.index

        if self.is_pair:
            pair = crn.link_loop_radial_prev
            uv_co = pair[uv].uv
            if pair.link_loop_prev.tag or (check_seam and pair.link_loop_prev.edge.seam):
                return True

            for crn_ in pair.vert.link_loops:
                if crn_ != pair and crn_.face.index == idx and crn_[uv].uv == uv_co:
                    if crn_.tag or (check_seam and crn_.edge.seam):
                        return True
                    prev_crn = crn_.link_loop_prev
                    if (prev_crn != crn and prev_crn.tag) or (check_seam and prev_crn.edge.seam):
                        return True

        elif self.invert:
            prev_crn = crn.link_loop_prev
            prev_prev_crn = prev_crn.link_loop_prev
            if prev_prev_crn.tag or (check_seam and prev_prev_crn.edge.seam):
                return True

            uv_co = prev_crn[uv].uv
            for crn_ in prev_crn.vert.link_loops:
                if crn_ != prev_crn and crn_.face.index == idx and crn_[uv].uv == uv_co:
                    if crn_.tag or (check_seam and crn_.edge.seam):
                        return True
                    prev_crn_ = crn_.link_loop_prev
                    if prev_crn_ != crn and prev_crn_.tag or (check_seam and prev_crn_.edge.seam):
                        return True
        else:
            next_crn = crn.link_loop_next
            if next_crn.tag or (check_seam and next_crn.edge.seam):
                return True

            uv_co = next_crn[uv].uv
            for crn_ in next_crn.vert.link_loops:
                if crn_ != next_crn and crn_.face.index == idx and crn_[uv].uv == uv_co:
                    if crn_.tag or (check_seam and crn_.edge.seam):
                        return True
                    prev_crn_ = crn_.link_loop_prev
                    if prev_crn_ != crn and prev_crn_.tag or (check_seam and prev_crn_.edge.seam):
                        return True
        return False

    def __hash__(self):
        return hash(self.crn)

    def __eq__(self, other):
        return self.crn == other.crn and self.invert == other.invert


class UNIV_OT_Select_Loop_VIEW2D(select.UNIV_OT_Select_Edge_Grow_Base):
    bl_label = 'Loop'
    bl_idname = 'uv.univ_select_loop'
    bl_description = "Edge Loop Select\n\n" \
                     "Has [Alt + Scroll Up/Down] keymap"

    def draw(self, context):
        layout = self.layout
        if self.grow:
            layout.prop(self, 'prioritize_sharps')
        layout.prop(self, 'boundary_by_boundary')
        layout.prop(self, 'clamp_on_seam')
        layout.prop(self, 'max_angle')

    def execute(self, context):
        self.umeshes = UMeshes(report=self.report)
        self.umeshes.fix_context()

        if self.umeshes.elem_mode not in ('VERT', 'EDGE'):
            # TODO: Implement loop select by face by 'edge apex'
            return bpy.ops.uv.univ_select_linked(deselect=False)  # noqa

        self.calc_islands = Islands.calc_extended_any_edge_with_markseam if self.clamp_on_seam else Islands.calc_extended_any_edge
        self.umeshes.filter_by_partial_selected_uv_edges()

        self.loop_select()

        self.umeshes.update(info='Not found edges for loop select')
        return {'FINISHED'}

    def loop_select(self):
        from ..preferences import debug
        for umesh in reversed(self.umeshes):
            islands = self.calc_islands(umesh)  # noqa
            if not islands:
                self.umeshes.umeshes.remove(umesh)
                continue
            uv = umesh.uv
            islands.indexing()
            global_grow = []
            for isl in islands:
                grow = []
                isl.set_selected_crn_edge_tag()

                stack: list[CrnEdgeGrow] = []
                exclude_pair = set()
                for crn in isl.iter_corners_by_tag():
                    if crn in exclude_pair:
                        continue

                    if not self.boundary_by_boundary:
                        pair = crn.link_loop_radial_prev
                        if utils.is_pair_by_idx(crn, pair, uv):
                            exclude_pair.add(pair)
                            self.pair_stack_append(crn, pair, uv, stack)
                        else:
                            self.unpair_stack_append(crn, uv, stack)

                    elif utils.is_pair_by_idx(crn, crn.link_loop_radial_prev, uv):
                        pair = crn.link_loop_radial_prev
                        exclude_pair.add(pair)
                        self.pair_stack_append(crn, pair, uv, stack)
                    else:  # boundary
                        self.unpair_stack_append(crn, uv, stack)

                exclude_edges = set()
                max_angle = math.nextafter(self.max_angle, float('inf'))

                while stack:
                    temp = []
                    for eg in stack:
                        if self.clamp_on_seam:
                            if eg.invert:
                                check_seam = not eg.crn.link_loop_prev.edge.seam
                            else:
                                check_seam = not eg.crn.edge.seam
                        else:
                            check_seam = False

                        if eg.has_clamp(check_seam):
                            continue

                        if not self.boundary_by_boundary:
                            linked = eg.linked_edges()
                        elif eg.is_pair:
                            linked = eg.linked_edges_contiguous()
                        else:
                            linked = eg.linked_edges_boundary()

                        # assert len(linked) == len(set(linked))
                        # Grow without check angle
                        if not self.boundary_by_boundary:
                            if eg.is_pair:
                                if len(eg.crn.link_loop_next.vert.link_loops) - \
                                        1 == sum(pair_eg.is_pair for pair_eg in linked):
                                    if self.grow_without_check_angle_or_with_prioritize(
                                            eg, linked, exclude_edges, temp, max_angle):
                                        continue
                            else:
                                if len(linked) == 2:
                                    linked_boundary: list[CrnEdgeGrow] = [b_eg for b_eg in linked if not b_eg.is_pair]
                                    if len(linked_boundary) == 1:
                                        linked_boundary: CrnEdgeGrow = linked_boundary[0]
                                        crn_with_pair = next(b_eg for b_eg in linked if b_eg.is_pair).crn

                                        if len(crn_with_pair.face.loops) == 4 and len(crn_with_pair.link_loop_radial_prev.face.loops) == 4:
                                            if linked_boundary not in exclude_edges:
                                                temp.append(linked_boundary)
                                                exclude_edges.add(linked_boundary)
                                            continue
                                        else:
                                            angle = eg.angle(linked_boundary, max_angle) * 0.65
                                            if angle <= max_angle:
                                                if linked_boundary not in exclude_edges:
                                                    temp.append(linked_boundary)
                                                    exclude_edges.add(linked_boundary)
                                                continue

                        elif eg.is_pair:
                            if len(eg.crn.link_loop_next.vert.link_loops) - 1 == len(linked):
                                if self.grow_without_check_angle_or_with_prioritize(
                                        eg, linked, exclude_edges, temp, max_angle):
                                    continue
                        else:  # boundary
                            if len(linked) == 1:
                                linked_edges = eg.linked_edges()
                                if len(linked_edges) == 2:
                                    if linked[0] in linked_edges:
                                        linked_edges.remove(linked[0])
                                        link_e = linked_edges[0]
                                        if len(link_e.crn.face.loops) == 4 and len(link_e.crn.link_loop_radial_prev.face.loops) == 4:
                                            if linked[0] not in exclude_edges:
                                                temp.append(linked[0])
                                                exclude_edges.add(linked[0])
                                            continue
                                    else:
                                        angle = eg.angle(linked[0], max_angle) * 0.65
                                        if angle <= max_angle:
                                            if linked[0] not in exclude_edges:
                                                temp.append(linked[0])
                                                exclude_edges.add(linked[0])
                                            continue

                        min_eg = None
                        min_angle = max_angle
                        for ed_ in linked:
                            angle = eg.angle(ed_, max_angle)
                            if angle <= max_angle:
                                if self.prioritize_sharps and not ed_.crn.edge.smooth:
                                    angle *= 0.65
                                if angle < min_angle:
                                    min_eg = ed_
                                    min_angle = angle
                        if min_eg and min_eg not in exclude_edges:
                            temp.append(min_eg)
                            exclude_edges.add(min_eg)

                    grow.append(stack)
                    stack = temp

                if grow:
                    del grow[0]
                    if grow:
                        global_grow.append(grow)

            if global_grow:
                to_select = []
                for grow_ in global_grow:
                    for edge_group in grow_:
                        for eg in edge_group:
                            to_select.append(eg.crn.link_loop_prev if eg.invert else eg.crn)

                if utils.USE_GENERIC_UV_SYNC:
                    if umesh.sync:
                        umesh.sync_from_mesh_if_needed()

                    edge_select_set = utils.edge_select_linked_set_func(umesh)
                    for crn in to_select:
                        edge_select_set(crn, True)

                    if debug():
                        duplicates = len(to_select) - len(set(to_select))
                        if duplicates:
                            print(f"UniV Debug: Loop Select: Duplicate selection {duplicates}.")
                else:
                    edge_select_set = utils.edge_select_linked_set_func(umesh)
                    for crn in to_select:
                        edge_select_set(crn, True)

                umesh.update()

    @staticmethod
    def grow_without_check_angle_or_with_prioritize(eg: CrnEdgeGrow, linked: list[CrnEdgeGrow], exclude_edges, temp, max_angle):
        """ Grow when start edge has two same poly count faces and grew edge has two same poly count faces """
        # case when has quadro faces
        idx = eg.crn.face.index
        if len(linked) == 3:
            if len(eg.crn.face.loops) == len(eg.crn.link_loop_radial_prev.face.loops):
                left_next_face_crn_size = len(eg.crn.link_loop_next.link_loop_radial_prev.face.loops)
                right_next_face_crn_size = len(
                    eg.crn.link_loop_radial_prev.link_loop_prev.link_loop_radial_prev.face.loops)
                if left_next_face_crn_size == right_next_face_crn_size:
                    target_crn = eg.crn.link_loop_next.link_loop_radial_prev.link_loop_next
                    for eg_ in linked:
                        if eg_.crn == target_crn:
                            if eg_ not in exclude_edges:
                                temp.append(eg_)
                                exclude_edges.add(eg_)
                            return True
        elif len(linked) == 2:
            faces_gons_count = [len(f.loops) for f in eg.crn.vert.link_faces if f.index == idx]
            faces_gons_count.sort()
            if faces_gons_count[-1] >= 5 and faces_gons_count[:2] in ([3, 3], [4, 4]):
                for eg_ in linked:
                    if len(eg_.crn.face.loops) >= 5 or len(eg_.crn.link_loop_radial_prev.face.loops) >= 5:
                        angle = eg.angle(eg_, max_angle) * 0.65

                        if angle < max_angle and eg_ not in exclude_edges:
                            temp.append(eg_)
                            exclude_edges.add(eg_)
                        return True
        # case when has two shared faces
        elif len(linked) == 1:
            eg_ = linked[0]
            angle = eg.angle(eg_, max_angle) * 0.65
            if angle < max_angle and eg_ not in exclude_edges:
                temp.append(eg_)
                exclude_edges.add(eg_)
            return True
        return False

    @staticmethod
    def has_unselect_linked_corners_pair(crn, uv):
        idx = crn.face.index
        pair = crn.link_loop_radial_prev
        uv_co = crn[uv].uv

        for crn__ in crn.vert.link_loops:
            if crn__ != crn and crn__.face.index == idx and crn__[uv].uv == uv_co:
                if crn__.tag:
                    return False
                prev_crn = crn__.link_loop_prev
                if prev_crn != pair and prev_crn.tag:
                    return False
        return True

    @staticmethod
    def has_unselect_linked_corners_a(crn, uv):
        idx = crn.face.index
        uv_co = crn[uv].uv

        if crn.link_loop_prev.tag:
            return False

        for crn__ in crn.vert.link_loops:
            if crn__ != crn and crn__.face.index == idx and crn__[uv].uv == uv_co:
                if crn__.tag or crn__.link_loop_prev.tag:
                    return False
        return True

    @staticmethod
    def has_unselect_linked_corners_b(crn, uv):
        idx = crn.face.index
        next_crn = crn.link_loop_next
        uv_co = next_crn[uv].uv

        if next_crn.tag:
            return False

        for crn__ in next_crn.vert.link_loops:
            if crn__ != next_crn and crn__.face.index == idx and crn__[uv].uv == uv_co:
                if crn__.tag or crn__.link_loop_prev.tag:
                    return False
        return True

    def pair_stack_append(self, crn, pair, uv, stack):
        if self.has_unselect_linked_corners_pair(crn, uv):
            eg = CrnEdgeGrow(pair, uv)
            eg.is_pair = True
            stack.append(eg)
        if self.has_unselect_linked_corners_pair(pair, uv):
            eg = CrnEdgeGrow(crn, uv)
            eg.is_pair = True
            stack.append(eg)

    def unpair_stack_append(self, crn, uv, stack):
        if self.has_unselect_linked_corners_a(crn, uv):
            eg = CrnEdgeGrow(crn.link_loop_next, uv, True)
            eg.is_pair = False
            stack.append(eg)
        if self.has_unselect_linked_corners_b(crn, uv):
            eg = CrnEdgeGrow(crn, uv)
            eg.is_pair = False
            stack.append(eg)


class EdgeGrow:
    def __init__(self, e, head_v):
        self.e: BMEdge = e
        self.head_v: bmesh.types.BMVert = head_v
        self._vec = None

    @property
    def vec(self):
        if not self._vec:
            tail_v = self.e.other_vert(self.head_v)
            self._vec = self.head_v.co - tail_v.co
        return self._vec

    @vec.setter
    def vec(self, v):
        self._vec = v

    def angle(self, other: 'typing.Self', max_angle: float):
        return self.vec.angle(other.vec, max_angle)  # noqa

    def linked_edges_wire(self):
        return [EdgeGrow(e, e.other_vert(self.head_v))
                for e in self.head_v.link_edges if not e.hide and e.is_wire and e != self.e]

    def linked_edges_contiguous(self):
        return [EdgeGrow(e, e.other_vert(self.head_v)) for e in self.head_v.link_edges
                if e != self.e and not e.hide and e.is_contiguous and all(not f.hide for f in self.e.link_faces)]

    def linked_edges_boundary_by_boundary(self):
        edges = []
        for e in self.head_v.link_edges:
            if e != self.e:
                if not e.hide:
                    if e.is_boundary:
                        edges.append(EdgeGrow(e, e.other_vert(self.head_v)))
                    elif sum(not f.hide for f in e.link_faces) == 1:
                        edges.append(EdgeGrow(e, e.other_vert(self.head_v)))
        return edges

    def linked_edges_non_wire(self):
        return [EdgeGrow(e, e.other_vert(self.head_v)) for e in self.head_v.link_edges
                if e != self.e and not e.hide and not e.is_wire]

    def linked_edges(self):
        if self.is_wire:
            return self.linked_edges_wire()
        if self.is_contiguous:
            return self.linked_edges_contiguous()
        return self.linked_edges_boundary_by_boundary()

    @property
    def is_wire(self):
        return self.e.is_wire

    @property
    def is_boundary(self):
        return self.e.is_boundary or sum(not f.hide for f in self.e.link_faces) == 1

    @property
    def is_contiguous(self):
        if self.e.is_contiguous:
            return all(not f.hide for f in self.e.link_faces)
        return False

    def __hash__(self):
        return hash(self.e)

    def __eq__(self, other):
        return self.e == other.e and self.head_v == other.head_v


class UNIV_OT_Select_Loop_VIEW3D(select.UNIV_OT_Select_Edge_Grow_Base):
    bl_label = 'Loop'
    bl_idname = 'mesh.univ_select_loop'
    bl_description = "Loop Select\n\n" \
                     "Has [Alt + Scroll Up] keymap"
    # noinspection PyTypeHints
    max_angle: FloatProperty(name='Angle', default=math.radians(40), min=math.radians(1), soft_min=math.radians(5), max=math.radians(90), subtype='ANGLE',
                             description="Max select angle.")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'prioritize_sharps')
        layout.prop(self, 'boundary_by_boundary')
        layout.prop(self, 'clamp_on_seam')
        layout.prop(self, 'max_angle')

    def execute(self, context):
        self.umeshes = UMeshes.calc_any_unique(verify_uv=False)
        self.umeshes.set_sync()
        self.umeshes.sync_invalidate()

        if self.umeshes.elem_mode not in ('VERT', 'EDGE'):
            # TODO: Implement loop select by face by 'edge apex'
            return bpy.ops.mesh.select_linked(delimit={'SEAM'} if self.clamp_on_seam else {'NORMAL'})

        self.loop_select_edge()

        if not self.umeshes:
            self.report({'WARNING'}, 'Not found edges for loop select')
        return {'FINISHED'}

    def loop_select_edge(self):
        self.umeshes.filter_by_partial_selected_3d_edges()
        for umesh in self.umeshes:
            selected_edges = utils.calc_selected_edges_iter(umesh)
            stack = self.get_growable_edges(selected_edges)
            self.grow_by_angle(stack, umesh)

    def get_growable_edges(self, selected_edges) -> list[EdgeGrow]:
        stack = []
        for e in selected_edges:
            a, b = e.verts
            if e.is_wire:
                can_be_grow_a = not any(ee.select for ee in self.linked_edges_wire_start(e, a))
                can_be_grow_b = not any(ee.select for ee in self.linked_edges_wire_start(e, b))
            elif not self.boundary_by_boundary:
                can_be_grow_a = not any(ee.select for ee in self.linked_edges_non_wire_start(e, a))
                can_be_grow_b = not any(ee.select for ee in self.linked_edges_non_wire_start(e, b))
            elif e.is_boundary or sum(not f.hide for f in e.link_faces) == 1:
                can_be_grow_a = not any(ee.select for ee in self.linked_edges_boundary_start(e, a))
                can_be_grow_b = not any(ee.select for ee in self.linked_edges_boundary_start(e, b))
            else:  # contiguous
                can_be_grow_a = not any(ee.select for ee in self.linked_edges_contiguous_start(e, a))
                can_be_grow_b = not any(ee.select for ee in self.linked_edges_contiguous_start(e, b))

            if can_be_grow_a:
                stack.append(EdgeGrow(e, a))
            if can_be_grow_b:
                stack.append(EdgeGrow(e, b))
        return stack

    def grow_by_angle(self, stack: list[EdgeGrow], umesh):
        grow = []
        exclude_edges = set()
        max_angle = math.nextafter(self.max_angle, float('inf'))
        while stack:
            temp = []
            for eg in stack:
                if eg.is_wire:
                    linked = eg.linked_edges_wire()
                elif not self.boundary_by_boundary:
                    linked = eg.linked_edges_non_wire()
                elif eg.is_boundary:
                    linked = eg.linked_edges_boundary_by_boundary()
                else:
                    linked = eg.linked_edges_contiguous()

                # Clamp on selected edges and on seams.
                check_seam = self.clamp_on_seam and not eg.e.seam
                if any(next_edge.e.select or (check_seam and next_edge.e.seam) for next_edge in linked):
                    continue


                # Grow without check angle.
                if not eg.is_wire:
                    if not self.boundary_by_boundary:
                        if eg.is_boundary:
                            if len(linked) == 2:
                                linked_boundary = [b_eg for b_eg in linked if b_eg.is_boundary]
                                if len(linked_boundary) == 1:
                                    link_eg_with_pair = next(b_eg for b_eg in linked if b_eg.is_contiguous)

                                    if len(link_eg_with_pair.e.link_faces[0].loops) == 4 and len(link_eg_with_pair.e.link_faces[1].loops) == 4:
                                        if linked_boundary[0] not in exclude_edges:
                                            temp.append(linked_boundary[0])
                                            exclude_edges.add(linked_boundary[0])
                                            continue
                                    else:
                                        angle = eg.angle(linked_boundary[0], max_angle) * 0.65
                                        if angle <= max_angle:
                                            if linked_boundary[0] not in exclude_edges:
                                                temp.append(linked_boundary[0])
                                                exclude_edges.add(linked_boundary[0])
                                            continue
                        else:
                            if all(b_eg.is_contiguous for b_eg in linked):
                                if self.grow_without_check_angle_or_with_prioritize_contiguous(eg, linked, exclude_edges, temp, max_angle):
                                    continue

                    elif eg.is_boundary:
                        if len(linked) == 1:
                            linked_non_wire = eg.linked_edges_contiguous()
                            if len(linked_non_wire) == 1:
                                link_eg_with_pair = linked_non_wire[0]
                                if len(link_eg_with_pair.e.link_faces[0].loops) == 4 and len(link_eg_with_pair.e.link_faces[1].loops) == 4:
                                    if linked[0] not in exclude_edges:
                                        temp.append(linked[0])
                                        exclude_edges.add(linked[0])
                                else:
                                    angle = eg.angle(linked[0], max_angle) * 0.65
                                    if angle <= max_angle:
                                        if linked[0] not in exclude_edges:
                                            temp.append(linked[0])
                                            exclude_edges.add(linked[0])
                                continue

                    else:  # contiguous
                        if self.grow_without_check_angle_or_with_prioritize_contiguous(eg, linked, exclude_edges, temp, max_angle):
                            continue


                # Check angle.
                min_eg = None
                min_angle = max_angle
                for next_edge in linked:
                    angle = eg.angle(next_edge, max_angle)
                    if angle <= max_angle:
                        if self.prioritize_sharps and not next_edge.e.smooth:
                            angle *= 0.65
                        if angle < min_angle:
                            min_eg = next_edge
                            min_angle = angle
                if min_eg and min_eg not in exclude_edges:
                    temp.append(min_eg)
                    exclude_edges.add(min_eg)

            grow.append(stack)
            stack = temp
        if grow:
            del grow[0]

            for edge_group in grow:
                for eg in edge_group:
                    eg.e.select = True
            umesh.update()

    @staticmethod
    def linked_edges_wire_start(e: BMEdge, v):
        return [e_ for e_ in v.link_edges if e_ != e and not e_.hide and e_.is_wire]

    @staticmethod
    def linked_edges_boundary_start(e: BMEdge, v):
        return [e_ for e_ in v.link_edges if e_ != e and not e_.hide and (e_.is_boundary or sum(not f.hide for f in e_.link_faces) == 1)]

    @staticmethod
    def linked_edges_contiguous_start(e: BMEdge, v):
        return [e_ for e_ in v.link_edges if e_ != e and not e_.hide and (e.is_contiguous and all(not f.hide for f in e.link_faces))]

    @staticmethod
    def linked_edges_non_wire_start(e: BMEdge, v):
        return [e_ for e_ in v.link_edges if e_ != e and not e_.hide and not e_.is_wire]

    # TODO: Grow without check should be done on a flat Edge, that is, the 2 faces should be coplanar.
    #  And also for triangulated grid it is necessary to make the rules stricter,
    #  i.e. check first by the angle of the edge, and then with the coefficient to check with no check.
    @staticmethod
    def grow_without_check_angle_or_with_prioritize_contiguous(
            eg: EdgeGrow, non_included_linked: list[EdgeGrow], exclude_edges: set[EdgeGrow], temp: list[EdgeGrow], max_angle: float):
        """ Grow when start edge has two same poly count faces and grew edge has two same poly count faces """
        linked_to_vert_size = len(eg.head_v.link_faces)
        match len(non_included_linked):
            case 3:  # Quad - Quad case.
                #  *  -  *  -  *
                #  |  F  |  F  |
                #  *  -  *  -  *
                #  |  F  |  F  |
                #  *  -  *  -  *
                if linked_to_vert_size == 4:
                    linked_faces: list[BMFace] = [f for f in eg.head_v.link_faces if not f.hide]
                    if len(linked_faces) == 4:
                        # TODO: improve behavior for tris and ngons (* 0.65)
                        curr_face_a = eg.e.link_faces[0]
                        curr_face_b = eg.e.link_faces[1]
                        if len(curr_face_a.loops) == 4 and len(curr_face_b.loops) == 4:
                            linked_faces.remove(curr_face_a)
                            linked_faces.remove(curr_face_b)

                            next_face_a, next_face_b = linked_faces
                            if len(next_face_a.loops) == 4 and len(next_face_a.loops) == 4:
                                for edge_grow in non_included_linked:
                                    if edge_grow not in exclude_edges:
                                        if not any(f in [curr_face_a, curr_face_b] for f in edge_grow.e.link_faces):
                                            temp.append(edge_grow)
                                            exclude_edges.add(edge_grow)
                                            return True
            case 2:  # N-Gon and two Face case.
                #  *  -  *  -  *
                #  |     |  F  |
                #  *  N  *  -  *
                #  |     |  F  |
                #  *  -  *  -  *
                if linked_to_vert_size == 3:
                    faces_gons_count = sorted(len(f.loops) for f in eg.head_v.link_faces if not f.hide)
                    if len(faces_gons_count) == 3:
                        ngone = faces_gons_count.pop()
                        if ngone >= 5 and faces_gons_count[:2] in ([3, 3], [4, 4]):
                            for edge_grow in non_included_linked:
                                if any(len(f.loops) >= 5 for f in edge_grow.e.link_faces if not f.hide):
                                    # TODO: With pointers to previous edges, one does not have to check for angle from vectors,
                                    #  but rather check by the normal that forms the previous edges and check against the subsequent one.
                                    angle = eg.angle(edge_grow, max_angle) * 0.65

                                    if angle < max_angle and edge_grow not in exclude_edges:
                                        temp.append(edge_grow)
                                        exclude_edges.add(edge_grow)
                                    return True
            case 1:  # Edge inner two N-Gon case.
                #  *  -  *  -  *
                #  |     |     |
                #  *     * <-  *
                #  |     | <-  |
                #  *     * <-  *
                #  |     |     |
                #  *  -  *  -  *
                if linked_to_vert_size == 2:
                    if sum(not f.hide for f in eg.head_v.link_faces) == 2:
                        edge_grow = non_included_linked[0]
                        if edge_grow not in exclude_edges:
                            angle = eg.angle(edge_grow, max_angle) * 0.65
                            if angle < max_angle:
                                temp.append(edge_grow)
                                exclude_edges.add(edge_grow)
                                return True
        return False


class UNIV_OT_Select_Loop_Pick_VIEW3D(UNIV_OT_Select_Loop_VIEW3D):
    bl_label = 'Select Loop Pick'
    bl_idname = 'mesh.univ_select_loop_pick'
    bl_description = "Loop Select Pick\n\n" \
                     "Has [Double Click and Shift+Double Click] keymaps"

    def loop_select_edge(self):
        # TODO: Implement ray cast, for pick in vertex mode and implement face loops select
        # Pick Vertex Mode: Need find by raycast (generated from linked faces) (for solid mode to avoid selecting edges under face)
        # If not found raycast -> find nearest edge by dot product
        if self.umeshes.elem_mode == 'VERT':
            bpy.ops.mesh.select_linked(delimit={'SEAM'} if self.clamp_on_seam else {'NORMAL'})
            return

        for umesh in reversed(self.umeshes):
            if umesh.obj != bpy.context.active_object:
                self.umeshes.umeshes.remove(umesh)
                continue

            if not umesh.total_edge_sel:
                self.report({'WARNING'}, 'Not found selected edge')
                return
            if not isinstance(umesh.bm.select_history.active, bmesh.types.BMEdge):
                self.report({'WARNING'}, 'Active element must be an edge')
                return

            stack = self.get_growable_edges([umesh.bm.select_history.active])
            self.grow_by_angle(stack, umesh)

# noinspection PyTypeHints
class UNIV_OT_SelectSimilar_VIEW3D(Operator):
    bl_idname = "mesh.univ_select_similar"
    bl_label = "Similar"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Select Similar Islands\n\n" \
                     "Default - Select Similar\n" \
                     "Shift or Alt - By Selected\n\n" \
                     "Has Shift+G keymap"

    by_selected: bpy.props.BoolProperty(name='By Selected', default=False)

    walk_mode: bpy.props.EnumProperty(name='Walk Mode', default='BOTH',
                                      items=(
                                          ('BOTH', 'Both', ''),
                                          ('DIRECT', 'Direct', ''),
                                          ('SYMMETRY', 'Symmetry', 'For mirror islands')
                                      ))
    island_mode: bpy.props.EnumProperty(name='Island Mode', default='UV',
                                        items=(
                                            # ('BOTH', 'Both', ''),
                                            ('UV', 'UV', 'UV islands'),
                                            ('MESH', 'Mesh', 'Mesh islands')
                                        ))
    ignore_mark_seam: bpy.props.BoolProperty(name='Ignore Mark Seam', default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw(self, context):
        self.layout.row(align=True).prop(self, 'walk_mode', expand=True)
        self.layout.row(align=True).prop(self, 'island_mode', expand=True)
        self.layout.prop(self, 'ignore_mark_seam')
        self.layout.prop(self, 'by_selected')

    def invoke(self, context, event):
        if event.value == 'PRESS':
            return self.execute(context)

        self.by_selected = event.alt or event.shift
        return self.execute(context)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from . import stack
        self.umeshes: UMeshes | None = None
        self.targets: list[stack.StackIsland] = []
        self.transfer: list[stack.StackIsland] = []
        self.counter: int = 0
        self.island_calc_type: Callable = AdvIslands.calc_selected
        self.calc_non_selected: Callable = AdvIslands.calc_non_selected
        self.walk_direct = True
        self.walk_symmetry = True
        self.need_sync_validation_check = False

    def execute(self, context) -> set[str]:
        self.counter = 0
        self.umeshes = UMeshes(report=self.report)
        self.umeshes.update_tag = False

        if not self.bl_idname.startswith('UV'):
            self.umeshes.set_sync(True)
            self.umeshes.sync_invalidate()
            self.umeshes.elem_mode = 'FACE'
        else:
            self.need_sync_validation_check = False
            if self.umeshes.sync:
                if utils.USE_GENERIC_UV_SYNC:
                    self.need_sync_validation_check = self.umeshes.elem_mode in ('VERT', 'EDGE')



        self.walk_direct = self.walk_mode in ('DIRECT', 'BOTH')
        self.walk_symmetry = self.walk_mode in ('SYMMETRY', 'BOTH')

        self.get_island_calc_types()

        if self.by_selected:
            self.select_similar_by_selected()
        else:
            self.select_similar_reference_transfer()

        if self.counter:
            self.report({'INFO'}, f'Found {self.counter} similar islands')

        return {'FINISHED'}

    def islands_preprocessing_reference_and_transfer(self) -> list[list]:
        from . import stack

        for umesh in reversed(self.umeshes):
            islands = self.island_calc_type(umesh)
            if not islands:
                self.umeshes.umeshes.remove(umesh)
                continue
            if isinstance(islands, MeshIslands):
                islands = islands.to_adv_islands()
            islands.indexing()

            for isl in islands:
                stack_isl = stack.StackIsland(isl)
                stack_isl.preprocessing()
                self.targets.append(stack_isl)

        if not self.targets:
            self.report({'WARNING'}, 'Not found islands')
            return []

        sort_stack_islands_groups = utils.true_groupby(self.targets)
        if not sort_stack_islands_groups:
            self.report({'WARNING'}, 'Islands have different set and number of polygons')
            return []
        return sort_stack_islands_groups

    def get_island_calc_types(self):
        type_class = AdvIslands if self.island_mode == 'UV' else MeshIslands
        suffix = '' if self.ignore_mark_seam else '_with_mark_seam'
        mode = 'selected' if self.by_selected else 'visible'

        self.island_calc_type = getattr(type_class, f'calc_{mode}{suffix}')
        self.calc_non_selected = getattr(type_class, f'calc_non_selected{suffix}')

    def islands_preprocessing_by_selected(self):
        from . import stack
        for umesh in reversed(self.umeshes):
            # TODO: With extended selection, you can calculate islands via calc_visible
            #  and add them to selected and non_selected. This does not work with calc_selected.
            selected = self.island_calc_type(umesh)
            non_selected = self.calc_non_selected(umesh)

            if not selected and not non_selected:
                self.umeshes.umeshes.remove(umesh)
                continue

            if isinstance(selected, MeshIslands):
                selected = selected.to_adv_islands()
                non_selected = non_selected.to_adv_islands()

            if not selected:
                proxi = non_selected
            elif not non_selected:
                proxi = selected
            else:
                proxi = AdvIslands(non_selected.islands + selected.islands, umesh)

            proxi.indexing()

            for sel_isl in selected:
                stack_isl = stack.StackIsland(sel_isl)
                stack_isl.preprocessing()
                stack_isl.calc_walked_reference_island_fw_and_for_bw()
                self.targets.append(stack_isl)

            for non_sel_isl in non_selected:
                stack_isl = stack.StackIsland(non_sel_isl)
                stack_isl.preprocessing()
                self.transfer.append(stack_isl)

        if not self.targets:
            self.report({'WARNING'}, 'Not found selected islands')
            return []

        if not self.transfer:
            self.report({'WARNING'}, 'Not found unselected islands')
            return []

        sort_stack_islands = stack.UNIV_OT_Stack_VIEW3D.sort_stack_islands_target_with_transfer(self)  # noqa
        if not sort_stack_islands:
            self.report({'WARNING'}, 'Islands have different set and number of polygons')
        return sort_stack_islands

    # By Selected
    def select_similar_reference_transfer(self):
        from .stack import StackIsland
        self.targets: list[StackIsland] = []
        preprocessing = self.islands_preprocessing_reference_and_transfer()
        if not preprocessing:
            return

        self.umeshes.deselect_all_elem()

        to_select = set()
        for sort_stack_islands in preprocessing:
            for reference in sort_stack_islands:
                if reference.island.tag:
                    reference.island.tag = False
                    if not any(i.island.tag for i in sort_stack_islands):
                        break
                    reference.calc_walked_reference_island_fw_and_for_bw()
                    for transfer in sort_stack_islands:
                        if transfer.island.tag:
                            if (self.walk_direct and reference.calc_transfer_stack_island_fw(transfer)) or \
                                    (self.walk_symmetry and reference.calc_transfer_stack_island_bw(transfer)):
                                to_select.add(transfer.island)
                                to_select.add(reference.island)
                                transfer.island.tag = False
                                self.counter += 1
                            transfer.island.set_tag(False)
        if to_select:
            for isl in to_select:
                if self.need_sync_validation_check:
                    isl.umesh.sync_from_mesh_if_needed()
                elif isl.umesh._sync_invalidate:  # noqa
                    isl.umesh.sync_valid = False
                isl.select = True
                isl.umesh.update_tag = True

        self.umeshes.update(info_type={'WARNING'}, info='No found islands for stacking')

    # Reference Transfer
    def select_similar_by_selected(self):
        from .stack import StackIsland
        self.targets: list[StackIsland] = []
        self.transfer: list[StackIsland] = []

        sort_stack_islands = self.islands_preprocessing_by_selected()
        if not sort_stack_islands:
            return

        to_select = set()
        for reference, stacks_transfers in sort_stack_islands:
            for stack_transfer_isl in stacks_transfers:
                if stack_transfer_isl.island.tag:
                    if (self.walk_direct and reference.calc_transfer_stack_island_fw(stack_transfer_isl)) or \
                            (self.walk_symmetry and reference.calc_transfer_stack_island_bw(stack_transfer_isl)):
                        stack_transfer_isl.island.tag = False
                        to_select.add(reference.island)
                        to_select.add(stack_transfer_isl.island)
                    stack_transfer_isl.island.set_tag(False)

        if to_select:
            for isl in to_select:
                if self.need_sync_validation_check:
                    isl.umesh.sync_from_mesh_if_needed()
                elif isl.umesh._sync_invalidate:  # noqa
                    isl.umesh.sync_valid = False
                isl.select = True
                isl.umesh.update_tag = True

        self.counter = len(to_select)
        self.umeshes.update(info_type={'WARNING'}, info='No found islands for stacking')


class UNIV_OT_SelectSimilar_VIEW2D(UNIV_OT_SelectSimilar_VIEW3D):
    bl_idname = "uv.univ_select_similar"
