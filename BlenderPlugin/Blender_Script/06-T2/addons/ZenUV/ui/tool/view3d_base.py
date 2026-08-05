# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2023, Alex Zhornyak, Valeriy Yatsenko

import bpy
import bmesh

from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_line_2d
from dataclasses import dataclass, field
from timeit import default_timer as timer
import numpy as np
from functools import partial

from ZenUV.utils.transform import centroid
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.inject import is_modal_procedure
from ZenUV.utils.vlog import Log
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetGroup, TrimColorSettings
from ZenUV.utils.blender_zen_utils import rgetattr
from ZenUV.utils.transform import ZenLocRotScale

from bpy_extras import view3d_utils


gizmo_trims = {}
gizmo_cage = {}
gizmo_texture = {}


@dataclass
class MeshData:
    face_idx: int = -1
    uv_layer_name: str = ''
    v_co: list = field(default_factory=list)
    uv_co: list = field(default_factory=list)
    mesh: bpy.types.Mesh = None
    mtx_world: Matrix = Matrix()


@dataclass
class ModalDrag:
    up: bool = False
    right: bool = False
    direction: bool = False
    origin: bool = False

    def is_dragging(self):
        return self.up or self.right or self.direction or self.origin


@dataclass
class Cage:

    pivot: Vector = Vector((0.0, 0.0))
    width: float = 0.0
    height: float = 0.0
    color: Vector = Vector((1.0, 1.0, 1.0))
    size_matrix: Matrix = Matrix()
    full_matrix: Matrix = Matrix()


@dataclass
class UvToMeshMatrix:
    mtx_type: str = 'MESH'  # in {'MESH', 'SCREEN'}
    # local matrix
    mtx: Matrix = Matrix()
    # separate components
    translation: Matrix = Matrix()
    rotation: Matrix = Matrix()
    scale: Matrix = Matrix()

    uv_pivot: Vector = Vector((0.0, 0.0))
    uv_pivot_mtx: Matrix = Matrix()

    gizmo_matrix: Matrix = Matrix()

    texture_matrix: Matrix = Matrix()

    offset_correction = 1.0
    scale_correction = 1.0

    # Trim Representation
    cage: Cage = field(default_factory=Cage)


class CageFactory:

    def __init__(self, context, p_trim=None) -> None:

        self.cage = None

        if p_trim is not None:
            self.cage = Cage(
                pivot=(p_trim.left_bottom + p_trim.top_right) * 0.5,
                width=p_trim.width,
                height=p_trim.height,
                color=p_trim.color[:])
        else:
            self.cage = Cage(
                pivot=Vector.Fill(2, 0.5),
                width=1.0,
                height=1.0,
                color=(1.0, 0.0, 0.0))

        self.cage.size_matrix = Matrix.Diagonal(Vector((self.cage.width, self.cage.height, 0.0))).to_4x4()

    def calc_full_matrix(self, M: UvToMeshMatrix):
        if M.mtx_type == 'MESH':
            return self._calc_ma_mesh(M)
        elif M.mtx_type == 'SCREEN':
            return self._calc_ma_screen(M)

    def _calc_ma_screen(self, M: UvToMeshMatrix):
        offset_mtx = M.rotation @ M.scale @ Matrix.Translation((self.cage.pivot - Vector.Fill(2, 0.5)).to_3d()).to_4x4()
        self.cage.full_matrix = M.translation @ offset_mtx @ self.cage.size_matrix
        return self.cage.full_matrix

    def _calc_ma_mesh(self, M: UvToMeshMatrix):
        offset_mtx = M.rotation @ M.scale @ Matrix.Translation((self.cage.pivot - M.uv_pivot).to_3d()).to_4x4()
        self.cage.full_matrix = M.translation @ offset_mtx @ self.cage.size_matrix
        return self.cage.full_matrix


@dataclass
class AdvancedMasterEdge:
    edge: bmesh.types.BMEdge = None
    loop: bmesh.types.BMLoop = None
    cross_x: Vector = None
    cross_y: Vector = None
    edge_index: int = -1
    loop_edge_index: int = -1


def region_2d_to_location_3d_ex(region, rv3d, coord, depth_location):
    from mathutils import Vector

    coord_vec = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    depth_location = Vector(depth_location)

    origin_start = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    origin_end = origin_start + coord_vec

    if rv3d.is_perspective:
        from mathutils.geometry import intersect_line_plane
        viewinv = rv3d.view_matrix.inverted()
        view_vec = viewinv.col[2].copy()
        v_res = intersect_line_plane(
            origin_start,
            origin_end,
            origin_end,  # do not change to 'depth location'
            view_vec, True,
        )
        return v_res
    else:
        from mathutils.geometry import intersect_point_line
        return intersect_point_line(
            depth_location,
            origin_start,
            origin_end,
        )[0]


class AdvancedBaseVectors:

    def __init__(self, p_face, uv_layer) -> None:

        self.p_face: bmesh.types.BMFace = p_face
        self.basement_vector: Vector = Vector()  # 3-Dimensions
        self.basement_vector_x: Vector = Vector()  # 3-Dimensions
        self.uv_pivot: Vector = Vector((0, 0))  # 2-Dimensions

        self.scalar_u: float = 0.0
        self.m_edge_length: float = 0.0
        self.scalar_v: float = 0.0

        self.uv_edge_u_length: float = 1.0
        self.uv_edge_v_length: float = 1.0
        self.f_size_uv: float = 1.0

        self.uv_to_mesh_mtx: UvToMeshMatrix = UvToMeshMatrix()

        # Processing
        if uv_layer is not None:
            self._calc_base_edges(uv_layer)

    def _is_face_flipped(self, uv_layer):
        from ZenUV.utils.generic import is_face_flipped
        return is_face_flipped(self.p_face, uv_layer)

    def _calc_base_edges(self, uv_layer):
        self.uv_pivot = centroid([loop[uv_layer].uv for loop in self.p_face.loops])
        x_line_dir = 1000.0 if not self._is_face_flipped(uv_layer) else - 1000.0

        a_edges = [
            AdvancedMasterEdge(
                edge=edge,
                loop=loop,
                cross_x=intersect_line_line_2d(self.uv_pivot, self.uv_pivot + Vector((x_line_dir, 0.0)), loop[uv_layer].uv, loop.link_loop_next[uv_layer].uv),
                cross_y=intersect_line_line_2d(self.uv_pivot, self.uv_pivot + Vector((0.0, 1000.0)), loop[uv_layer].uv, loop.link_loop_next[uv_layer].uv),
                edge_index=edge.index,
                loop_edge_index=loop.edge.index
            )
            for edge, loop in zip(self.p_face.edges, self.p_face.loops)
        ]

        try:
            y_edge = [e for e in a_edges if e.cross_y is not None][0]
        except Exception:
            y_edge = None
        try:
            x_edge = [e for e in a_edges if e.cross_x is not None][0]
        except Exception:
            x_edge = y_edge
        if y_edge is not None:
            self._append_up(uv_layer, y_edge)
            self._append_right(uv_layer, x_edge)

    def _append_up(self, uv_layer, m_edge: AdvancedMasterEdge):
        self.m_edge_length = m_edge.edge.calc_length()
        self.uv_edge_u_length = (m_edge.loop[uv_layer].uv - m_edge.loop.link_loop_next[uv_layer].uv).magnitude
        try:
            scalar = 1.0 if m_edge.cross_y is None else (m_edge.cross_y - m_edge.loop[uv_layer].uv).magnitude / self.uv_edge_u_length
            self.scalar_u = self.m_edge_length / self.uv_edge_u_length
        except ZeroDivisionError:
            scalar = 1.0
            self.scalar_u = 1.0
        cross_y_3d = m_edge.loop.vert.co + (m_edge.loop.link_loop_next.vert.co - m_edge.loop.vert.co) * scalar
        self.basement_vector = cross_y_3d - self.p_face.calc_center_median()

    def _append_right(self, uv_layer, m_edge: AdvancedMasterEdge):
        m_edge_length = m_edge.edge.calc_length()
        self.uv_edge_v_length = (m_edge.loop[uv_layer].uv - m_edge.loop.link_loop_next[uv_layer].uv).magnitude
        self.f_size_uv = (self.uv_edge_v_length + self.uv_edge_u_length) / 2
        try:
            scalar = 1.0 if m_edge.cross_x is None else (m_edge.cross_x - m_edge.loop[uv_layer].uv).magnitude / self.uv_edge_v_length
            self.scalar_v = m_edge_length / self.uv_edge_v_length
        except ZeroDivisionError:
            self.scalar_v = 1.0
            scalar = 1.0
        cross_x_3d = m_edge.loop.vert.co + (m_edge.loop.link_loop_next.vert.co - m_edge.loop.vert.co) * scalar
        self.basement_vector_x = cross_x_3d - self.p_face.calc_center_median()

    def calc_uv_mtx(self, context: bpy.types.Context, mtx_type: str, min_l=0.0, min_b=0.0, max_r=1.0, max_t=1.0) -> None:
        self.uv_to_mesh_mtx.mtx_type = mtx_type
        self.uv_to_mesh_mtx.uv_pivot = self.uv_pivot
        self.uv_to_mesh_mtx.uv_pivot_mtx = Matrix.Translation(self.uv_pivot.to_3d())
        if mtx_type == 'MESH':
            self._calc_uv_to_mesh_mtx()
            self._calc_texture_matrix_mesh()

        elif mtx_type == 'SCREEN':
            self._calc_uv_to_screen_matrix(context, min_l=min_l, min_b=min_b, max_r=max_r, max_t=max_t)
        else:
            raise RuntimeError("tool Matrix type not in ('MESH', 'SCREEN')")

        # cage mtx calculation
        CF = CageFactory(context, p_trim=ZuvTrimsheetUtils.getActiveTrim(context))
        CF.calc_full_matrix(self.uv_to_mesh_mtx)
        self.uv_to_mesh_mtx.cage = CF.cage

    def _calc_uv_to_mesh_mtx(self):
        self.uv_to_mesh_mtx.translation = Matrix.Translation(self.p_face.calc_center_median())
        self.uv_to_mesh_mtx.rotation = self._calc_local_rotation_matrix()

        self.uv_to_mesh_mtx.scale = Matrix.Diagonal((self.scalar_u, self.scalar_v, 0)).to_4x4()

        self.uv_to_mesh_mtx.mtx = self.uv_to_mesh_mtx.translation @ self.uv_to_mesh_mtx.rotation
        self.uv_to_mesh_mtx.gizmo_matrix = self.uv_to_mesh_mtx.mtx

        self.uv_to_mesh_mtx.offset_correction = self._calc_gizmo_offset_correction()
        self.uv_to_mesh_mtx.scale_correction = self._calc_gizmo_scale_correction()

    def _calc_matrix(self, pivot) -> Matrix:
        position = self.uv_to_mesh_mtx.rotation @ self.uv_to_mesh_mtx.scale @ (pivot - self.uv_to_mesh_mtx.uv_pivot.to_3d())
        return Matrix.Translation(position) @ self.uv_to_mesh_mtx.mtx @ self.uv_to_mesh_mtx.scale

    def _calc_texture_matrix_screen(self):
        self.uv_to_mesh_mtx.texture_matrix = self.uv_to_mesh_mtx.translation

    def _calc_texture_matrix_mesh(self) -> None:
        self.uv_to_mesh_mtx.texture_matrix = self._calc_matrix(Vector.Fill(3, 0.5))

    def _calc_gizmo_scale_correction(self):
        try:
            return 1 / self.m_edge_length
        except ZeroDivisionError:
            return 1

    def _calc_gizmo_offset_correction(self):
        try:
            p_scope = self.f_size_uv, self.m_edge_length
            return min(p_scope) / max(p_scope) if max(self.scalar_u, self.scalar_v) > 1.0 else max(p_scope) / min(p_scope)
        except ZeroDivisionError:
            return 1.0

    def _calc_local_rotation_matrix(self):
        f_normal = self.p_face.normal.normalized()
        base_vec_y = self.basement_vector.normalized()
        base_vec_x = self.basement_vector_x.normalized()

        X = Vector((1, 0, 0))
        Y = Vector((0, 1, 0))
        Z = Vector((0, 0, 1))

        matrix_rotate_normal = Z.rotation_difference(f_normal).to_matrix().to_4x4()
        Y = Y @ matrix_rotate_normal.inverted()
        mat_tmp = Y.rotation_difference(base_vec_y).to_matrix().to_4x4()

        base_vec_x = base_vec_x @ mat_tmp @ matrix_rotate_normal

        mat_x = X.rotation_difference(base_vec_x).to_matrix().to_4x4()

        return mat_tmp @ matrix_rotate_normal @ mat_x

    def _calc_uv_to_gizmo_screen_matrix(self, context: bpy.types.Context, gizmo_pos3d: Vector):
        r3d = context.region
        rv3d = context.space_data.region_3d
        if rv3d and rv3d:

            gizmo_pos2d = view3d_utils.location_3d_to_region_2d(r3d, rv3d, gizmo_pos3d, default=Vector((0, 0)))

            p_scale = context.preferences.system.ui_scale  # depends on UI scale

            d_gizmo_size = context.preferences.view.gizmo_size * p_scale

            view3d_area_width = d_gizmo_size * 3

            left = gizmo_pos2d.x - d_gizmo_size
            bottom = gizmo_pos2d.y - d_gizmo_size

            area_points = (
                Vector((left, bottom)),
                Vector((left, bottom + view3d_area_width)),
                Vector((left + view3d_area_width, bottom + view3d_area_width)),
                Vector((left + view3d_area_width, bottom)))

            view_rot = rv3d.view_rotation

            view_pos_in_3d = region_2d_to_location_3d_ex(
                r3d,
                rv3d,
                gizmo_pos2d,
                (0, 0, 0))

            view_rotation_ma = view_rot.to_matrix().to_4x4()

            points = [
                view3d_utils.region_2d_to_location_3d(r3d, rv3d, p, view_pos_in_3d)
                for p in area_points]
            scale_vec = min((points[0] - points[1]).length, (points[1] - points[2]).length)

            self.uv_to_mesh_mtx.translation = Matrix.Translation(view_pos_in_3d)
            self.uv_to_mesh_mtx.rotation = view_rotation_ma
            self.uv_to_mesh_mtx.scale = Matrix.Diagonal(Vector.Fill(3, scale_vec)).to_4x4()
            self.uv_to_mesh_mtx.mtx = self.uv_to_mesh_mtx.translation @ self.uv_to_mesh_mtx.rotation

    def _calc_uv_to_screen_matrix(self, context: bpy.types.Context, min_l=0.0, min_b=0.0, max_r=1.0, max_t=1.0):

        r3d = context.region
        rv3d = context.space_data.region_3d
        if rv3d and rv3d:

            p_scene = context.scene

            tool_props = p_scene.zen_uv.ui.view3d_tool

            p_area = context.area
            p_offsets = ZuvTrimsheetUtils.get_area_offsets(p_area)

            ui_scale = context.preferences.system.ui_scale

            gizmo_zone_width = 40 * ui_scale
            vertical_margin = 10 * ui_scale

            d_right_offset = p_offsets.get('right') + gizmo_zone_width
            d_left_offset = p_offsets.get('left') + gizmo_zone_width
            d_top_offset = p_offsets.get('top') + vertical_margin
            d_bottom_offset = p_offsets.get('bottom') + vertical_margin

            d_area_height = p_area.height
            d_area_width = p_area.width

            d_left = d_left_offset
            d_top = d_area_height - d_top_offset
            d_right = d_area_width - d_right_offset
            d_bottom = d_bottom_offset

            d_trims_width = max_r - min_l
            d_trims_height = max_t - min_b

            d_rect_true_width = d_right - d_left
            d_rect_true_height = d_top - d_bottom

            d_new_width = d_rect_true_width / d_trims_width if d_trims_width > 0 else d_rect_true_width
            d_new_height = d_rect_true_height / d_trims_height if d_trims_height > 0 else d_rect_true_height

            d_half_width = (d_rect_true_width - d_new_width) / 2.0
            d_half_height = (d_rect_true_height - d_new_height) / 2.0

            d_left += d_half_width
            d_right -= d_half_width
            d_top -= d_half_height
            d_bottom += d_half_height

            area_points = (
                Vector((d_left, d_bottom)),
                Vector((d_left, d_top)),
                Vector((d_right, d_top)),
                Vector((d_right, d_bottom)))

            view_rot = rv3d.view_rotation

            x2d = d_left + (d_right - d_left) / 2
            y2d = d_bottom + (d_top - d_bottom) / 2

            x2d += tool_props.screen_pan_x
            y2d += tool_props.screen_pan_y

            d_user_zoom_factor = tool_props.screen_scale

            d_rect_width = d_new_width * d_user_zoom_factor
            d_rect_height = d_new_height * d_user_zoom_factor

            d_rect_length = min(d_rect_width, d_rect_height)

            if tool_props.screen_position_locked:
                x2d, y2d = tool_props.screen_pos[:]
                d_rect_length = tool_props.screen_size
                d_user_zoom_factor = 1.0

                area_points = (
                    Vector((x2d - d_rect_length / 2, y2d - d_rect_length / 2)),
                    Vector((x2d - d_rect_length / 2, y2d + d_rect_length / 2)),
                    Vector((x2d + d_rect_length / 2, y2d + d_rect_length / 2)),
                    Vector((x2d + d_rect_length / 2, y2d - d_rect_length / 2)),
                )

            d_scaled_width = d_rect_length * d_trims_width
            d_scaled_height = d_rect_length * d_trims_height

            d_scaled_left = x2d - d_scaled_width / 2 - d_half_width
            d_scaled_right = x2d + d_scaled_width / 2 + d_half_width
            d_scaled_top = y2d + d_scaled_height / 2 + d_half_height
            d_scaled_bottom = y2d - d_scaled_height / 2 - d_half_height

            d_check_left = d_scaled_left - (d_right - 10)
            if d_check_left > 0:
                x2d -= d_check_left
            else:
                d_check_right = (d_left + 10) - d_scaled_right
                if d_check_right > 0:
                    x2d += d_check_right

            d_check_bottom = d_scaled_bottom - (d_top - 30)
            if d_check_bottom > 0:
                y2d -= d_check_bottom
            else:
                d_check_top = (d_bottom + 30) - d_scaled_top
                if d_check_top > 0:
                    y2d += d_check_top

            if not tool_props.screen_position_locked:
                def zen_uv_post_write_screen_rect(p_x2d, p_y2d, p_rect_length):
                    bpy.context.scene.zen_uv.ui.view3d_tool.screen_pos = (p_x2d, p_y2d)
                    bpy.context.scene.zen_uv.ui.view3d_tool.screen_size = p_rect_length

                bpy.app.timers.register(partial(zen_uv_post_write_screen_rect, x2d, y2d, d_rect_length))

            view_pos_in_3d = region_2d_to_location_3d_ex(
                r3d,
                rv3d,
                Vector((x2d, y2d)),
                (0, 0, 0)
            )

            view_rotation_ma = view_rot.to_matrix().to_4x4()

            points = [
                view3d_utils.region_2d_to_location_3d(
                    r3d, rv3d, p, view_pos_in_3d)
                for p in area_points]
            scale_vec = min((points[0] - points[1]).length, (points[1] - points[2]).length)

            scale_vec *= d_user_zoom_factor

            self.uv_to_mesh_mtx.translation = Matrix.Translation(view_pos_in_3d)
            self.uv_to_mesh_mtx.rotation = view_rotation_ma
            self.uv_to_mesh_mtx.scale = Matrix.Diagonal(Vector.Fill(3, scale_vec)).to_4x4()
            self.uv_to_mesh_mtx.mtx = self.uv_to_mesh_mtx.translation @ self.uv_to_mesh_mtx.rotation


            if self.p_face is not None:
                self.uv_to_mesh_mtx.gizmo_matrix = Matrix.Translation(self.p_face.calc_center_median()) @ self._calc_local_rotation_matrix()

            self.uv_to_mesh_mtx.texture_matrix = (
                self.uv_to_mesh_mtx.translation @ view_rotation_ma @ self.uv_to_mesh_mtx.scale)


class ZuvGizmoBase():

    tool_mode = None

    pivot_prop = ''

    CAGE_DEFAULT_COLOR = (1, 0, 0)

    # ABSTRACT METHODS

    def _reset_dragged(self, context: bpy.types.Context):
        raise NotImplementedError('ABSTRACT> _reset_dragged!')

    def _setup_dragged(self, context: bpy.types.Context):
        raise NotImplementedError('ABSTRACT> _setup_dragged!')

    def _setup_dragged_position(self, context: bpy.types.Context):
        raise NotImplementedError('ABSTRACT> _setup_dragged_position!')

    def _check_and_set_drag_completed(self):
        raise NotImplementedError('ABSTRACT> _check_and_set_drag_completed')

    def are_gizmos_modal(self):
        n_gizmo_count = len(self.gizmos)
        if n_gizmo_count:
            p_arr = np.empty(n_gizmo_count, 'b')
            self.gizmos.foreach_get('is_modal', p_arr)
            return np.any(p_arr)
        return False

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return cls.poll_by_tool_mode_and_mesh(context, cls.tool_mode)

    @classmethod
    def poll_by_edit_mesh(cls, context: bpy.types.Context):
        if context.mode == 'EDIT_MESH' and context.active_object is not None:
            p_obj = context.active_object
            if p_obj.type == 'MESH':
                _id = getattr(context.workspace.tools.from_space_view3d_mode(context.mode, create=False), 'idname', None)
                if isinstance(_id, str) and _id == 'zenuv.view3d_tool':
                    mesh = p_obj.data  # type: bpy.types.Mesh
                    bm = bmesh.from_edit_mesh(mesh)
                    return bm.faces.active is not None
        return False

    @classmethod
    def poll_by_tool_mode_and_mesh(cls, context: bpy.types.Context, s_tool_mode: str):
        if cls.poll_by_edit_mesh(context):
            p_scene = context.scene
            if p_scene.zen_uv.ui.view3d_tool.mode == s_tool_mode:
                return True
        return False

    def setup_operator_pivot(self, context: bpy.types.Context):
        if not self.are_gizmos_modal():
            p_scene = context.scene

            pivot = rgetattr(p_scene, self.pivot_prop)

            for v in self.mpr_trim_align.values():
                v.is_pivot = v.direction == pivot

    @classmethod
    def getActiveMeshMtx(cls, context: bpy.types.Context, p_obj: bpy.types.Object) -> UvToMeshMatrix:
        base_factory = cls.getBaseVectors(context, p_obj, 'MESH')
        if base_factory is not None:
            return base_factory.uv_to_mesh_mtx

        return UvToMeshMatrix()

    @classmethod
    def getBaseVectors(cls, context: bpy.types.Context, p_obj: bpy.types.Object, s_mode: str) -> AdvancedBaseVectors:
        if p_obj is not None:
            bm = bmesh.from_edit_mesh(p_obj.data)
            bm.faces.ensure_lookup_table()
            p_face = bm.faces.active
            uv_layer = bm.loops.layers.uv.active
            if p_face is not None and uv_layer is not None:
                base_factory = AdvancedBaseVectors(p_face, uv_layer)
                base_factory.calc_uv_mtx(context, s_mode)

                return base_factory

        return None

    @classmethod
    def getObjMeshData(cls, p_obj: bpy.types.Object) -> MeshData:
        p_data = MeshData()

        if p_obj is not None and p_obj.type == 'MESH':
            p_data.mtx_world = p_obj.matrix_world.copy()
            bm = bmesh.from_edit_mesh(p_obj.data)
            bm.faces.ensure_lookup_table()
            p_face = bm.faces.active
            uv_layer = bm.loops.layers.uv.active
            if p_face and uv_layer:
                p_data.mesh = p_obj.data
                p_data.face_idx = p_face.index
                p_data.uv_layer_name = uv_layer.name
                p_data.v_co = [v.co.to_tuple(8) for v in p_face.verts]
                p_data.uv_co = [loop[uv_layer].uv.to_tuple(4) for loop in p_face.loops]
        return p_data

    def setup(self, context: bpy.types.Context):
        self.obj_data = MeshData()
        self.gizmo_drag = ModalDrag()
        self.tool_mtx = Matrix()
        self.drag_started = False
        self.trimsheet_uuid = ''
        self.active_trim_uuid = ''
        self.active_trim_index = -1
        self.last_setup_position = 0
        self.offset_correction = 1.0
        self.min_left = 0.0
        self.min_bottom = 0.0
        self.max_top = 1.0
        self.max_right = 1.0

        self.base_vectors = None  # type: AdvancedBaseVectors

        # Clear all Gizmos
        self.gizmos.clear()

        # Start creating Gizmos

        self.mpr_trim_align = {}
        self.mpr_trim_fitflip = {}

        for k in UV_AREA_BBOX.bbox_all_handles:

            self.mpr_trim_fitflip[k] = self.gizmos.new("VIEW3D_GT_zenuv_trim_fitflip")
            self.mpr_trim_fitflip[k].alpha = 1.0
            self.mpr_trim_fitflip[k].color = (0.8, 0.8, 0.8)
            self.mpr_trim_fitflip[k].color_highlight = (0.8, 0.8, 0.8)
            self.mpr_trim_fitflip[k].alpha_highlight = 1.0
            self.mpr_trim_fitflip[k].hide_select = True
            self.mpr_trim_fitflip[k].use_draw_scale = True
            self.mpr_trim_fitflip[k].scale_basis = 0.2  # used when 'draw is scaled only'
            self.mpr_trim_fitflip[k].direction = k
            # create shapes when we know the direction
            self.mpr_trim_fitflip[k].setup()

            self.mpr_trim_align[k] = self.gizmos.new("VIEW3D_GT_zenuv_trim_align")
            self.mpr_trim_align[k].alpha = 0.0
            self.mpr_trim_align[k].color_highlight = 1.0, 1.0, 1.0
            self.mpr_trim_align[k].alpha_highlight = 1.0
            self.mpr_trim_align[k].hide_select = False
            self.mpr_trim_align[k].use_draw_scale = True
            self.mpr_trim_align[k].scale_basis = 0.2  # used when 'draw is scaled only'
            self.mpr_trim_align[k].select_bias = 0.1  # Do not change !!!
            self.mpr_trim_align[k].direction = k
            op_props = self.mpr_trim_align[k].target_set_operator('zenuv.tool_trim_handle')
            op_props.direction = k
            op_props.pivot_prop = self.pivot_prop

        self._setup_dragged(context)

        self.mpr_trim = self.gizmos.new("VIEW3D_GT_zenuv_trim_cage")
        self.mpr_trim.color = 1.0, 0.0, 0.0
        self.mpr_trim.alpha = 0.5
        self.mpr_trim.color_highlight = 1.0, 1.0, 1.0
        self.mpr_trim.alpha_highlight = 1
        self.mpr_trim.hide_select = True
        self.mpr_trim.use_draw_scale = False
        gizmo_cage[context.area.as_pointer()] = self.mpr_trim

        self.mpr_trim_select = {}
        gizmo_trims[context.area.as_pointer()] = {}

        self.mpr_tex = self.gizmos.new("VIEW3D_GT_zenuv_texture")
        self.mpr_tex.use_draw_scale = False
        self.mpr_tex.alpha = 0.5
        self.mpr_tex.color = (0, 0, 0)
        self.mpr_tex.hide_keymap = True
        self.mpr_tex.hide_select = True
        gizmo_texture[context.area.as_pointer()] = self.mpr_tex

        self._reset_dragged(context)

    def _update_offset_correction(self, p_obj: bpy.types.Object):
        if p_obj and self.base_vectors:
            self.offset_correction = self.base_vectors.uv_to_mesh_mtx.offset_correction * p_obj.matrix_world.inverted_safe().median_scale
            self.scale_correction = self.base_vectors.uv_to_mesh_mtx.scale_correction * p_obj.matrix_world.inverted_safe().median_scale

    def setup_position(self, context: bpy.types.Context, update_drag=True):
        p_obj = context.active_object
        self.obj_data = self.getObjMeshData(p_obj)

        # Tool pivot matrix
        self.base_vectors = self.getBaseVectors(
            context, p_obj,
            'MESH'
        )
        UvToMeshMtx = self.base_vectors.uv_to_mesh_mtx if self.base_vectors else UvToMeshMatrix()
        self.tool_mtx = UvToMeshMtx.gizmo_matrix

        self._update_offset_correction(p_obj)

        p_cage_color = self.CAGE_DEFAULT_COLOR

        if update_drag:
            self._setup_dragged_position(context)

        # Trimsheet Section
        was_active_trim_uuid = self.active_trim_uuid
        self.active_trim_uuid = ''
        self.active_trim_index = -1

        p_trimsheet_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        p_trimsheet = None

        def clear_select_gizmos():
            for p_gizmo in self.mpr_trim_select.values():
                self.gizmos.remove(p_gizmo)

            self.mpr_trim_select.clear()

        if p_trimsheet_owner:
            p_trimsheet = p_trimsheet_owner.trimsheet
            p_trim = ZuvTrimsheetUtils.getActiveTrimFromOwner(p_trimsheet_owner)

            b_need_to_update_trims = False

            if self.trimsheet_uuid != p_trimsheet_owner.trimsheet_geometry_uuid:
                self.trimsheet_uuid = p_trimsheet_owner.trimsheet_geometry_uuid
                b_need_to_update_trims = True

            p_new_uuid = p_trim.uuid if p_trim else ''
            if was_active_trim_uuid != p_new_uuid:
                b_need_to_update_trims = True

            n_trimsheet_count = len(p_trimsheet) if p_trimsheet else 0
            if len(self.mpr_trim_select) != n_trimsheet_count:
                b_need_to_update_trims = True

            if b_need_to_update_trims:
                clear_select_gizmos()

                p_area_ptr = context.area.as_pointer()
                p_gizmo_trims = {}

                self.min_left = 0.0
                self.min_bottom = 0.0
                self.max_top = 1.0
                self.max_right = 1.0

                # WARNING! We are making inverse to be the same order as in UV Editor
                for k in range(len(p_trimsheet) - 1, -1, -1):
                    it_trim = p_trimsheet[k]

                    self.mpr_trim_select[k] = self.gizmos.new("VIEW3D_GT_zenuv_trim_select")
                    self.mpr_trim_select[k].alpha = 0.3
                    self.mpr_trim_select[k].alpha_highlight = 0.8
                    self.mpr_trim_select[k].hide_select = False
                    self.mpr_trim_select[k].use_draw_scale = False

                    op_props = self.mpr_trim_select[k].target_set_operator('wm.zuv_trim_set_index')
                    op_props.trimsheet_index = k

                    p_gizmo_trims[k] = self.mpr_trim_select[k]

                    left, top, right, bottom = it_trim.rect
                    if left < self.min_left:
                        self.min_left = left
                    if bottom < self.min_bottom:
                        self.min_bottom = bottom
                    if right > self.max_right:
                        self.max_right = right
                    if top > self.max_top:
                        self.max_top = top

                global gizmo_trims
                gizmo_trims[p_area_ptr] = p_gizmo_trims

            if p_trim:
                self.active_trim_uuid = p_trim.uuid
                self.active_trim_index = p_trimsheet_owner.trimsheet_index
                p_cage_color = p_trim.color[:]
        else:
            self.trimsheet_uuid = ''
            clear_select_gizmos()

        # Texture Section
        self.mpr_tex.dimensions = (1.0, 1.0, 0.0)
        self.mpr_tex.setup()

        self._setup_trimsheet_colors(context, p_trimsheet, p_cage_color)

        self.last_setup_position = timer()

    def _setup_trimsheet_colors(self, context: bpy.types.Context, p_trimsheet, p_active_color):
        addon_prefs = get_prefs()

        b_modal_disable = self.are_gizmos_modal() and addon_prefs.trimsheet.auto_disable_trims_overlay

        n_trim_count = 0
        if p_trimsheet:
            n_trim_count = len(p_trimsheet)

        p_cage_color = p_active_color

        p_scene = context.scene

        tool_props = p_scene.zen_uv.ui.view3d_tool

        for k, v in self.mpr_trim_select.items():
            b_active = self.active_trim_index == k

            b_select_enabled = tool_props.is_select_trim_enabled()

            b_visible = (
                k in range(n_trim_count) and
                (
                    tool_props.display_trims and
                    (tool_props.display_all or b_active)
                ) or
                b_select_enabled
            )

            v.hide = b_modal_disable or not b_visible
            if not v.hide:
                p_trim: ZuvTrimsheetGroup = p_trimsheet[k]
                p_color_settings: TrimColorSettings = p_trim.get_draw_color_settings(addon_prefs.trimsheet, b_active, p_trim.selected)

                v.hide_select = not b_select_enabled

                v.fill_color = p_color_settings.color[:]
                v.fill_alpha = p_color_settings.color_alpha
                v.border_color = p_color_settings.border[:]
                v.border_alpha = p_color_settings.border_alpha
                v.text_color = p_color_settings.text_color[:]

                if b_active:
                    p_cage_color = v.border_color

        self.mpr_tex.hide = b_modal_disable or not tool_props.is_texture_visible()
        if not self.mpr_tex.hide:
            self.mpr_tex.color = addon_prefs.trimsheet.texture_gamma_color[0:3]
            self.mpr_tex.alpha = addon_prefs.trimsheet.texture_gamma_color[-1]

        self.mpr_trim.hide = b_modal_disable or not tool_props.is_cage_visible()
        if not self.mpr_trim.hide:
            self.mpr_trim.color = p_cage_color
            self.mpr_trim.color_highlight = self.mpr_trim.color

        for k, v in self.mpr_trim_align.items():
            v.hide = b_modal_disable or tool_props.tr_handles == 'OFF'
            self.mpr_trim_fitflip[k].hide = v.hide or v.is_highlight
            if not v.hide:
                v.color = p_active_color
                v.color_highlight = v.color

                self.mpr_trim_fitflip[k].color = p_active_color

    def setup_colors(self, context: bpy.types.Context):
        p_trimsheet = None
        p_active_color = self.CAGE_DEFAULT_COLOR

        p_trimsheet_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_trimsheet_owner:
            p_trimsheet = p_trimsheet_owner.trimsheet
            p_trim = ZuvTrimsheetUtils.getActiveTrimFromOwner(p_trimsheet_owner)
            if p_trim:
                p_active_color = p_trim.color[:]

        self._setup_trimsheet_colors(context, p_trimsheet, p_active_color)

    def _setup_dynamic_matrix(self, context, p_trimsheet_owner, p_obj: bpy.types.Object):
        p_scene = context.scene
        tool_props = p_scene.zen_uv.ui.view3d_tool

        uv_to_mesh = self.base_vectors.uv_to_mesh_mtx
        uv_to_gizmo = uv_to_mesh

        b_is_screen = tool_props.enable_screen_selector

        b_override_gizmo_screen = tool_props.tr_handles == 'GIZMO'  # and not b_is_screen

        if b_override_gizmo_screen:
            base_vectors = AdvancedBaseVectors(None, None)
            mtx_tool = p_obj.matrix_world @ uv_to_mesh.gizmo_matrix
            v_pos_3d = mtx_tool.to_translation()
            base_vectors._calc_uv_to_gizmo_screen_matrix(context, v_pos_3d)
            uv_to_gizmo = base_vectors.uv_to_mesh_mtx

        if b_is_screen:
            base_vectors = AdvancedBaseVectors(None, None)
            base_vectors.calc_uv_mtx(
                context, 'SCREEN',
                min_l=self.min_left,
                min_b=self.min_bottom,
                max_r=self.max_right,
                max_t=self.max_top)

            uv_to_mesh = base_vectors.uv_to_mesh_mtx
            if not b_override_gizmo_screen:
                uv_to_gizmo = uv_to_mesh

        b_is_gizmo_screen = b_is_screen or tool_props.tr_handles == 'GIZMO'

        # Cage Section
        self.mpr_trim.matrix_basis = uv_to_mesh.cage.full_matrix
        self.mpr_trim.matrix_space = Matrix() if b_is_screen else p_obj.matrix_world

        # Texture Section
        self.mpr_tex.matrix_basis = uv_to_mesh.texture_matrix
        self.mpr_tex.matrix_space = Matrix() if b_is_screen else p_obj.matrix_world

        p_trim = None

        if p_trimsheet_owner:
            for k, v in self.mpr_trim_select.items():
                CF = CageFactory(context, p_trim=p_trimsheet_owner.trimsheet[k])
                v.matrix_basis = CF.calc_full_matrix(uv_to_mesh)
                v.matrix_space = Matrix() if b_is_screen else p_obj.matrix_world

            p_trim = ZuvTrimsheetUtils.getActiveTrimFromOwner(p_trimsheet_owner)

        p_UV_AREA_DEFAULT = UV_AREA_BBOX.get_bbox_with_center_in(center=Vector((0.0, 0.0)))
        for k, v in self.mpr_trim_align.items():
            v_p = getattr(p_UV_AREA_DEFAULT, k)

            v.use_draw_scale = True
            self.mpr_trim_fitflip[k].use_draw_scale = True

            if b_is_gizmo_screen:
                if p_trim and not b_override_gizmo_screen:
                    CF = CageFactory(context, p_trim=p_trim)
                    v_p = Vector((v_p.x, v_p.y))
                    v_p = v_p @ CF.cage.size_matrix.to_2x2()
                    v_p -= Vector((0.5, 0.5)) - CF.cage.pivot

                v_p *= uv_to_gizmo.scale.to_scale().to_2d()

                v_p = v_p.to_3d()

                offset_mtx = (
                    uv_to_gizmo.rotation
                    @ Matrix.Translation(v_p.to_3d()).to_4x4()
                    )
                MA = uv_to_gizmo.translation @ offset_mtx

                v.matrix_basis = MA
                v.matrix_space = Matrix()
            else:
                CF = CageFactory(context, p_trim=p_trim)
                MA = CF.calc_full_matrix(uv_to_gizmo)

                loc, rot, sca = p_obj.matrix_world.decompose()

                v_p = v_p.to_3d()
                v_px = MA @ v_p @ Matrix.Diagonal(sca)

                v.matrix_basis = Matrix.Translation(v_px) @ uv_to_gizmo.rotation
                v.matrix_space = ZenLocRotScale(loc, rot, None)

            from .view3d_trim import ZuvTrimFitFlipGizmo

            mtx_flip = v.matrix_basis.copy()
            if b_is_gizmo_screen:
                mtx_flip = mtx_flip @ Matrix.Diagonal((0.8, 0.8, 1.0)).to_4x4()
            self.mpr_trim_fitflip[k].matrix_basis = (
                mtx_flip @ ZuvTrimFitFlipGizmo.get_direction_rotation_matrix(self.mpr_trim_fitflip[k].direction)
            )
            self.mpr_trim_fitflip[k].matrix_space = v.matrix_space

    def _setup_matrices_final(self, context: bpy.types.Context):
        if self.base_vectors is None:
            return

        p_obj = context.active_object  # type: bpy.types.Object
        if p_obj is None or p_obj.type != 'MESH':
            return

        self._update_offset_correction(p_obj)

        p_trimsheet_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        self._setup_dynamic_matrix(context, p_trimsheet_owner, p_obj)

    def is_trimsheet_modified(self, context: bpy.types.Context) -> bool:
        b_modified = False
        p_trimsheet_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_trimsheet_owner:
            if p_trimsheet_owner.trimsheet_geometry_uuid != self.trimsheet_uuid:
                b_modified = True
            else:
                p_uuid = ''
                p_trim = ZuvTrimsheetUtils.getActiveTrimFromOwner(p_trimsheet_owner)
                if p_trim:
                    p_uuid = p_trim.uuid
                if self.active_trim_uuid != p_uuid:
                    b_modified = True
        else:
            if self.trimsheet_uuid != '':
                b_modified = True
        return b_modified

    def draw_prepare(self, context: bpy.types.Context):

        b_was_setup = False

        if self.is_trimsheet_modified(context):
            self.setup_position(context, update_drag=False)
            b_was_setup = True
        else:
            if not is_modal_procedure(context):
                if timer() - self.last_setup_position > 0.1:
                    p_obj = context.active_object
                    p_obj_data = self.getObjMeshData(p_obj)
                    if p_obj_data != self.obj_data:
                        self.setup_position(context)
                        b_was_setup = True

        if not b_was_setup:
            self.setup_colors(context)

        # Must be used after base matrices were setup
        self._setup_matrices_final(context)

    def switch_blender_overlay(self, context: bpy.types.Context, value: bool):
        addon_prefs = get_prefs()
        if addon_prefs.trimsheet.auto_disable_blender_overlay:
            context.space_data.overlay.show_overlays = value

    def do_refresh(self, context: bpy.types.Context):
        # NOTE: Do not do check for modal procedure here!


        # -- Are we in drag mode
        b_drag_completed = self._check_and_set_drag_completed()

        if b_drag_completed:
            # -- Rebuilding Gizmos
            self._reset_dragged(context)
        else:
            p_obj = context.active_object
            p_obj_data = self.getObjMeshData(p_obj)
            if p_obj_data != self.obj_data:
                self.setup_position(context, update_drag=not self.gizmo_drag.is_dragging())
            else:
                if self.is_trimsheet_modified(context):
                    self.setup_position(context, update_drag=False)

    def refresh(self, context: bpy.types.Context):
        from ZenUV.utils.inject import is_modal_procedure

        if is_modal_procedure(context):
            return

        self.do_refresh(context)
