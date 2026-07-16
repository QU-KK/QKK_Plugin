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

# Copyright 2023, Valeriy Yatsenko, Alex Zhornyak

import bpy
import bmesh
from mathutils import kdtree, Vector

from dataclasses import dataclass, field
from timeit import default_timer as timer

from ZenUV.utils.generic import get_mesh_data, verify_uv_layer
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.vlog import Log
from ZenUV.utils.blender_zen_utils import is_uv_snap_enabled


@dataclass
class TrObjectInfo:
    bm: bmesh.types.BMesh = None
    me: bpy.types.Mesh = None
    loops: list = field(default_factory=list)
    uv_layer: bmesh.types.BMLayerItem = None
    loops_data: dict = field(default_factory=dict)
    selected_loops_uvs: dict = field(default_factory=dict)
    unselected_loops_uvs: dict = field(default_factory=dict)


def match_uv(face, vert, uv, uv_layer):
    return any(uv == loop[uv_layer].uv for loop in face.loops if loop.vert == vert)


def get_uv_island_by_face(seed_face: bmesh.types.BMesh, used_faces: list, uv_layer, skip_hidden=False):
    used_faces[seed_face.index] = True
    island = {seed_face}
    stack = [seed_face]  # Faces still to consider on this island.
    while stack:
        current_face = stack.pop()
        for loop in current_face.loops:
            v = loop.vert
            uv = loop[uv_layer].uv
            for f in v.link_faces:
                if skip_hidden:
                    if f.hide:
                        continue
                if f is current_face or used_faces[f.index]:
                    continue
                if not match_uv(f, v, uv, uv_layer):
                    continue

                # `f` is part of island, add to island and stack
                used_faces[f.index] = True
                island.add(f)
                stack.append(f)
    return island


def get_uv_islands_loops(context: bpy.types.Context, me: bpy.types.Mesh, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, return_unselected=True):
    b_is_uv_no_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

    bm.faces.ensure_lookup_table()

    selected_island_faces = set()
    unselected_faces = set(bm.faces) if return_unselected else set()

    if b_is_uv_no_sync:
        p_selected_faces = {
                    f for f in bm.faces if f.select and not f.hide for loop in f.loops
                    if loop[uv_layer].select} if me.total_face_sel > 0 else {}
    else:
        if context.tool_settings.mesh_select_mode[2]:
            p_selected_faces = {f for f in bm.faces if f.select and not f.hide} if me.total_face_sel > 0 else {}
        else:
            p_selected_faces = {f for f in bm.faces if not f.hide for v in f.verts if v.select} if me.total_vert_sel > 0 else {}

    used = [False] * len(bm.faces)
    seed_face: bmesh.types.BMFace
    for seed_face in p_selected_faces:
        if used[seed_face.index]:
            continue  # Face has already been processed.

        island = get_uv_island_by_face(seed_face, used, uv_layer, skip_hidden=False)

        selected_island_faces.update(island)

    if return_unselected:
        unselected_faces.difference_update(selected_island_faces)

    selected_islands_loops = {loop: loop[uv_layer].uv.copy() for face in selected_island_faces for loop in face.loops}

    unselected_islands_loops = {}
    if return_unselected:
        if b_is_uv_no_sync:
            unselected_islands_loops = {
                loop: loop[uv_layer].uv.copy()
                for face in unselected_faces
                if face.select and not face.hide
                for loop in face.loops} if me.total_face_sel > 0 else {}
        else:
            unselected_islands_loops = {loop: loop[uv_layer].uv.copy() for face in unselected_faces if not face.hide for loop in face.loops}

    return selected_islands_loops, unselected_islands_loops


def get_selection_loops(context: bpy.types.Context, me: bpy.types.Mesh, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, return_unselected=True):
    unselected_loops = {}
    if context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
        if return_unselected:
            unselected_loops = {loop for v in bm.verts if v.select and not v.hide for loop in v.link_loops if loop.face.select} if me.total_face_sel > 0 else {}
        selected_loops = {loop for v in bm.verts for loop in v.link_loops if loop.face.select and loop[uv_layer].select and not loop.face.hide} if me.total_face_sel > 0 else {}
    else:
        if return_unselected:
            unselected_loops = {loop for v in bm.verts if not v.hide for loop in v.link_loops if not loop.face.hide}
        if context.tool_settings.mesh_select_mode[2]:  # Selection mode FACE
            selected_loops = {loop for v in bm.verts if v.select for loop in v.link_loops if loop.face.select} if me.total_face_sel > 0 else {}
        else:
            selected_loops = {loop for v in bm.verts if v.select for loop in v.link_loops if not loop.face.hide} if me.total_vert_sel > 0 else {}

    if return_unselected:
        unselected_loops.difference_update(selected_loops)

    return {loop: loop[uv_layer].uv.copy() for loop in selected_loops}, {loop: loop[uv_layer].uv.copy() for loop in unselected_loops}


class TrObjectData:

    def __init__(self) -> None:
        self.object_storage = {}  # type: dict[bpy.types.Object, TrObjectInfo]
        self.influence_mode = ''
        self.order = ''
        self.message = ''
        self.kdtree = None

    def is_valid(self, objs, influence_mode, order):
        res = (
            self.influence_mode == influence_mode and
            self.order == order and
            (len(self.object_storage) != 0) == (len(objs) != 0) and
            set(self.object_storage.keys()).issubset(objs)
            )
        if res:
            try:
                # this operation will check that loops are still actual
                for _, v in self.object_storage.items():
                    for lp_cluster in v.loops:
                        if lp_cluster:
                            _ = lp_cluster[0][v.uv_layer]
                            break
            except Exception:
                return False
        return res

    def setup(
        self,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
    ) -> int:
        self.object_storage.clear()

        self.influence_mode = influence_mode
        self.order = order

        i_total_loops_count = 0

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if influence_mode == 'ISLAND':
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
                for lp_cluster in loops:
                    if len(lp_cluster) == 0:
                        pass
            else:
                loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)

            if order == 'OVERALL':
                if len(loops) > 0:
                    loops = [[lp for group in loops for lp in group], ]

            n_loops_count = len(loops)
            if n_loops_count:
                self.object_storage[obj] = TrObjectInfo(
                    bm=bm, me=me, loops=loops, uv_layer=uv_layer)

            i_total_loops_count += n_loops_count

        return i_total_loops_count

    def setup_uvs(self, context: bpy.types.Context, store_kd_tree: bool = True):
        n_kd_tree_count = 0
        for obj, info in self.object_storage.items():
            self.object_storage[obj].loops_uvs = {loop: loop[info.uv_layer].uv.copy() for cluster in info.loops for loop in cluster}
            if store_kd_tree:
                if info.bm and info.uv_layer:
                    self.object_storage[obj].unselected_loops_uvs = {
                        loop: loop[info.uv_layer].uv.copy()
                        for face in info.bm.faces
                        for loop in face.loops
                        if loop not in set(self.object_storage[obj].loops_uvs.keys())}
                    n_kd_tree_count += len(self.object_storage[obj].unselected_loops_uvs)

        if n_kd_tree_count:
            self.kdtree = kdtree.KDTree(n_kd_tree_count)

            index = 0
            for obj, info in self.object_storage.items():
                for loop_uv in info.unselected_loops_uvs.values():
                    self.kdtree.insert(loop_uv.to_3d(), index)
                    index += 1

            self.kdtree.balance()
        else:
            self.kdtree = None


class TrObjectLoopData:

    def __init__(self) -> None:
        self.object_storage = {}  # type: dict[bpy.types.Object, TrObjectInfo]
        self.influence_mode = ''
        self.message = ''
        self.kdtree = None

    def is_valid(self, objs, influence_mode, order):
        res = (
            self.influence_mode == influence_mode and
            (len(self.object_storage) != 0) == (len(objs) != 0) and
            set(self.object_storage.keys()).issubset(objs)
            )
        if res:
            try:
                # this operation will check that loops are still actual
                for _, v in self.object_storage.items():
                    for loop in v.selected_loops_uvs.keys():
                        _ = loop[v.uv_layer]
                        break
                    for loop in v.unselected_loops_uvs.keys():
                        _ = loop[v.uv_layer]
                        break
            except Exception:
                return False
        return res

    def setup_full_kdtree(self, context: bpy.types.Context, objs: list):
        self.object_storage.clear()

        n_kd_tree_count = 0

        t_loops = {}

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                selected_loops, unselected_loops = get_selection_loops(context, me, bm, uv_layer)
                n_count = len(selected_loops) + len(unselected_loops)
                t_loops[obj] = selected_loops, unselected_loops
                n_kd_tree_count += n_count

        if n_kd_tree_count:
            self.kdtree = kdtree.KDTree(n_kd_tree_count)

            index = 0
            for selected_loops, unselected_loops in t_loops.values():
                for loop_uv in selected_loops.values():
                    self.kdtree.insert(loop_uv.to_3d(), index)
                    index += 1

                for loop_uv in unselected_loops.values():
                    self.kdtree.insert(loop_uv.to_3d(), index)
                    index += 1

            self.kdtree.balance()

    def setup_uvs(
        self,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        use_kdtree: bool = True
    ) -> int:
        self.object_storage.clear()

        self.influence_mode = influence_mode

        i_total_loops_count = 0

        all_unselected_loops = []
        n_kd_tree_count = 0

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if influence_mode == 'ISLAND':
                interval = timer()
                selected_loops, unselected_loops = get_uv_islands_loops(context, me, bm, uv_layer)
            else:
                interval = timer()
                selected_loops, unselected_loops = get_selection_loops(context, me, bm, uv_layer)

            n_loops_count = len(selected_loops)
            if n_loops_count:
                self.object_storage[obj] = TrObjectInfo(
                    bm=bm, me=me, selected_loops_uvs=selected_loops, unselected_loops_uvs=unselected_loops, uv_layer=uv_layer)

            if unselected_loops:
                all_unselected_loops.append(unselected_loops)
                n_kd_tree_count += len(unselected_loops)

            i_total_loops_count += n_loops_count

        if use_kdtree and i_total_loops_count:
            self.kdtree = kdtree.KDTree(n_kd_tree_count)

            index = 0
            for unselected_loops in all_unselected_loops:
                for loop_uv in unselected_loops.values():
                    self.kdtree.insert(loop_uv.to_3d(), index)
                    index += 1

            self.kdtree.balance()

        return i_total_loops_count

    def get_snap_point_view(
            self, context: bpy.types.Context,
            v_mouse_view: Vector, v_view_1px: Vector,
            b_tweak_snap: bool, snap_threshold_px: int = 15) -> Vector:
        p_scene = context.scene

        b_snap_enabled = is_uv_snap_enabled(p_scene, b_tweak_snap)

        v_snapped_view = v_mouse_view

        if b_snap_enabled:
            p_snap_uv_element = p_scene.tool_settings.snap_uv_element
            b_vertex_snap = 'VERTEX' in p_snap_uv_element
            b_grid_snap = 'GRID' in p_snap_uv_element
            b_grid_increment_snap = 'INCREMENT' in p_snap_uv_element

            try:
                # NOTE: We are making all grids snaps the same,
                #       because Blender 2d cursor behaves in the same way
                if b_grid_snap or b_grid_increment_snap:
                    from ZenUV.ops.trimsheets.trimsheet import UvOverlayGrid
                    snap_step_x, snap_step_y = UvOverlayGrid.get_snap(context)
                    x = UvOverlayGrid.snap_to_grid_x(v_mouse_view.x, snap_step_x)
                    y = UvOverlayGrid.snap_to_grid_y(v_mouse_view.y, snap_step_y)
                    v_snapped_view = Vector((x, y))

                # NOTE: Vertex snap has priority
                if b_vertex_snap:
                    if transform_object_loop_data.kdtree:
                        if v_view_1px != 0.0:
                            closest_uv: Vector
                            distance: float
                            closest_uv, index, distance = self.kdtree.find(v_mouse_view.to_3d())

                            if distance is not None:
                                d_pixel_distance = distance / v_view_1px.length
                                if d_pixel_distance <= snap_threshold_px:
                                    v_snapped_view = closest_uv.to_2d()
            except Exception as e:
                Log.error("GET SNAP POINT:", e)

        return v_snapped_view


# Global Object Data Storage
transform_object_data = TrObjectData()
transform_object_loop_data = TrObjectLoopData()
