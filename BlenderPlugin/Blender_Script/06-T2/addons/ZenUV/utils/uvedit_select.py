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

# originally taken from 'uvedit_select.cc'

# Copyright 2025, Alex Zhornyak

import bpy
import bmesh
from mathutils import Vector


def ED_uvedit_sync_uvselect_ignore(ts: bpy.types.ToolSettings):
    if ts.use_uv_select_sync:
        if ts.uv_sticky_select_mode == 'SHARED_VERTEX':
            return True
    return False


def uvedit_face_visible_test(ts: bpy.types.ToolSettings, face: bmesh.types.BMFace):
    return not face.hide if ts.use_uv_select_sync else not face.hide and face.select


def BM_loop_uv_share_vert_check(l_a: bmesh.types.BMLoop, l_b: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
    return l_a[uv_layer].uv == l_b[uv_layer].uv


def uvedit_face_select_test(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, face: bmesh.types.BMFace):
    if face.hide:
        return False

    if ts.use_uv_select_sync:
        if not bm.uv_select_sync_valid or ED_uvedit_sync_uvselect_ignore(ts):
            return face.select
        return face.uv_select

    # NOTE: No Sync
    if ts.uv_select_mode[:] == (False, False, True):  # FACE
        return face.uv_select

    hflag_test = 'uv_select_vert' if ts.uv_select_mode[0] else 'uv_select_edge'
    for loop_iter in face.loops:
        if not getattr(loop_iter, hflag_test):
            return False
    return True


def uvedit_vert_is_face_select_any_other(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
    loop_iter: bmesh.types.BMLoop
    for loop_iter in loop.vert.link_loops:
        if not uvedit_face_visible_test(ts, loop_iter.face) or (loop_iter.face == loop.face):
            continue
        if BM_loop_uv_share_vert_check(loop, loop_iter, uv_layer) and uvedit_face_select_test(ts, bm, loop_iter.face):
            return True
    return False


def uvedit_edge_is_face_select_any_other(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
    l_radial_iter = loop.link_loop_radial_next
    if l_radial_iter == loop:
        return False

    l_iter = l_radial_iter

    while True:
        if uvedit_face_visible_test(ts, l_iter.face):
            if BM_loop_uv_share_edge_check(loop, l_iter, uv_layer) and uvedit_face_select_test(ts, bm, l_iter.face):
                return True
        l_iter = l_iter.link_loop_radial_next
        if not l_iter or l_iter == l_radial_iter:
            break
    return False


def BM_loop_uv_share_edge_check(loop_a: bmesh.types.BMLoop, loop_b: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
    uv_a1: Vector = loop_a[uv_layer].uv
    uv_a2: Vector = loop_a.link_loop_next[uv_layer].uv
    uv_b1: Vector = loop_b[uv_layer].uv
    uv_b2: Vector = loop_b.link_loop_next[uv_layer].uv

    return ((uv_a1 - uv_b1).length_squared < 1e-10 and
            (uv_a2 - uv_b2).length_squared < 1e-10) or \
        ((uv_a1 - uv_b2).length_squared < 1e-10 and
            (uv_a2 - uv_b1).length_squared < 1e-10)


def uvedit_edge_select_test(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
    if ts.use_uv_select_sync:
        if not bm.uv_select_sync_valid and ts.mesh_select_mode[:] == (False, False, True):  # FACE
            if ts.uv_sticky_select_mode == 'SHARED_LOCATION':
                if loop.face.select:
                    return True
                if uvedit_edge_is_face_select_any_other(ts, bm, loop, uv_layer):
                    return True
                return False
            elif ts.uv_sticky_select_mode == 'DISABLED':
                return loop.face.select
            else:  # NOTE: 'SHARED_VERTEX'
                return loop.edge.select

        if not bm.uv_select_sync_valid or ED_uvedit_sync_uvselect_ignore(ts):
            if ts.mesh_select_mode[2]:  # 'FACE'
                return loop.face.select
            if ts.mesh_select_mode[:2] == (False, True):  # Edge or Edge|Face
                return loop.edge.select
            return loop.vert.select and loop.link_loop_next.vert.select

        return loop.uv_select_edge

    # NOTE: NO SYNC:
    if ts.uv_select_mode[0]:  # 'VERTEX'
        return loop.uv_select_vert and loop.link_loop_next.uv_select_vert

    return loop.uv_select_edge


def bm_disk_edge_next(edge: bmesh.types.BMEdge, vert: bmesh.types.BMVert):
    """
    Simulates BM_DISK_EDGE_NEXT(e, v) in Python.
    Returns the next edge around the vertex in a circular list.
    """
    edges = list(vert.link_edges)
    if edge not in edges or len(edges) < 2:
        return edge  # No traversal possible

    idx = edges.index(edge)
    return edges[(idx + 1) % len(edges)]


def uvedit_vert_is_edge_select_any_other(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
    e_iter = loop.edge
    start_edge = loop.edge
    visited_edges = set()
    v = loop.vert

    while True:
        if e_iter in visited_edges:
            break
        visited_edges.add(e_iter)

        # Skip wire edges (no loops)
        l_radial: bmesh.types.BMLoop = e_iter.link_loops[0] if e_iter.link_loops else None
        if l_radial:
            l_iter = l_radial

            while True:
                if uvedit_face_visible_test(ts, l_iter.face):
                    l_other: bmesh.types.BMLoop = l_iter.link_loop_next if l_iter.vert != loop.vert else l_iter
                    if BM_loop_uv_share_vert_check(loop, l_other, uv_layer) and uvedit_edge_select_test(ts, bm, l_iter, uv_layer):
                        return True

                l_iter = l_iter.link_loop_radial_next
                if not l_iter or l_iter == l_radial:
                    break

        e_iter = bm_disk_edge_next(e_iter, v)
        if not e_iter or e_iter == start_edge:
            break

    return False


def uvedit_uv_select_test(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, loop: bmesh.types.BMLoop, uv_layer: bmesh.types.BMLayerItem):
    if ts.use_uv_select_sync:
        if not bm.uv_select_sync_valid and ts.mesh_select_mode[:] == (False, False, True):  # NOTE: Face
            # NOTE: /* Face only is a special case that can respect sticky modes. */
            if ts.uv_sticky_select_mode == 'SHARED_LOCATION':
                if loop.face.select:
                    return True
                if uvedit_vert_is_face_select_any_other(ts, bm, loop, uv_layer):
                    return True
                return False
            elif ts.uv_sticky_select_mode == 'DISABLED':
                return loop.face.select
            else:  # NOTE: 'SHARED_VERTEX'
                return loop.vert.select

        if bm.uv_select_sync_valid:
            pass
        # NOTE: /* Edge/Face is a special case that can respect sticky modes. */
        elif ts.mesh_select_mode[:] == (False, True, True) or ts.mesh_select_mode[:] == (False, True, False):
            if ts.uv_sticky_select_mode == 'SHARED_LOCATION':
                if loop.face.select:
                    return True
                if uvedit_vert_is_edge_select_any_other(ts, bm, loop, uv_layer):
                    return True
                return False
            elif ts.uv_sticky_select_mode == 'DISABLED':
                return loop.edge.select or loop.link_loop_prev.edge.select
            else:  # NOTE: 'SHARED_VERTEX'
                return loop.vert.select

        if not bm.uv_select_sync_valid or ED_uvedit_sync_uvselect_ignore(ts):
            if ts.mesh_select_mode[2]:  # NOTE: 'FACE'
                return loop.face.select
            if ts.mesh_select_mode[1]:  # NOTE: 'EDGE'
                # TODO: /* Are you looking for `uvedit_edge_select_test(...)` instead? */
                pass
            return loop.vert.select
        return loop.uv_select_vert

    # NOTE: No Sync
    if ts.mesh_select_mode[2]:  # NOTE: 'FACE'
        # TODO: /* Are you looking for `uvedit_edge_select_test(...)` instead? */
        pass
    if ts.mesh_select_mode[1]:  # NOTE: 'EDGE'
        # TODO: /* Are you looking for `uvedit_edge_select_test(...)` instead? */
        pass
    return loop.uv_select_vert


def uvedit_get_bm_selected_loops(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
    return [
        loop
        for face in bm.faces
        for loop in face.loops
        if not face.hide and (ts.use_uv_select_sync or face.select) and uvedit_uv_select_test(ts, bm, loop, uv_layer)
    ]


def uvedit_get_bm_unselected_loops(ts: bpy.types.ToolSettings, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
    return [
        loop
        for face in bm.faces
        for loop in face.loops
        if not face.hide and (ts.use_uv_select_sync or face.select) and not uvedit_uv_select_test(ts, bm, loop, uv_layer)
    ]
