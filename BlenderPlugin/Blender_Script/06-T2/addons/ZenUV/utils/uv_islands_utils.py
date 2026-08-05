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

""" Zen UV Islands Utilities """

import bpy
import bmesh


def match_uv(face, vert, uv, uv_layer):
    return any(uv == loop[uv_layer].uv for loop in face.loops if loop.vert == vert)


def get_selected_uv_islands(context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
    return get_uv_islands_sketch(context, bm, uv_layer, b_selected_only=True)


def get_all_uv_islands(context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
    return get_uv_islands_sketch(context, bm, uv_layer, b_selected_only=False)


def get_selected_uv_islands_in_indices(context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
    return [[f.index for f in group] for group in get_uv_islands_sketch(context, bm, uv_layer, b_selected_only=True, b_include_hidden=False)]


def get_uv_islands_sketch(
    context: bpy.types.Context,
    bm: bmesh.types.BMesh,
    uv_layer: bmesh.types.BMLayerItem,
    b_selected_only: bool,
    b_include_hidden: bool
):

    b_is_uv_no_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

    bm.faces.ensure_lookup_table()

    islands = list()

    if b_selected_only:
        if b_include_hidden:
            if b_is_uv_no_sync:
                p_selected_faces = {
                            f for f in bm.faces for loop in f.loops
                            if loop[uv_layer].select}
            else:
                if context.tool_settings.mesh_select_mode[2]:
                    p_selected_faces = {f for f in bm.faces if f.select}
                else:
                    p_selected_faces = {f for f in bm.faces for v in f.verts if v.select}
        else:
            if b_is_uv_no_sync:
                p_selected_faces = {
                            f for f in bm.faces if f.select and not f.hide for loop in f.loops
                            if loop[uv_layer].select}
            else:
                if context.tool_settings.mesh_select_mode[2]:
                    p_selected_faces = {f for f in bm.faces if f.select and not f.hide}
                else:
                    p_selected_faces = {f for f in bm.faces if not f.hide for v in f.verts if v.select}

    else:
        if b_include_hidden:
            p_selected_faces = bm.faces
        else:
            p_selected_faces = {f for f in bm.faces if not f.hide}

    islands.append(yield_uv_islands(bm, uv_layer, p_selected_faces))

    return islands


def yield_uv_islands(bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, p_selected_faces: list):

    used = [False] * len(bm.faces)
    seed_face: bmesh.types.BMFace
    for seed_face in p_selected_faces:
        if used[seed_face.index]:
            continue  # Face has already been processed.
        used[seed_face.index] = True
        island = [seed_face]
        stack = [seed_face]  # Faces still to consider on this island.
        while stack:
            current_face = stack.pop()
            for loop in current_face.loops:
                v = loop.vert
                uv = loop[uv_layer].uv
                for f in v.link_faces:
                    # If disabled, we also transform the hidden faces that belong to the island.
                    # if f.hide:
                    #     continue
                    if f is current_face or used[f.index]:
                        continue
                    if not match_uv(f, v, uv, uv_layer):
                        continue

                    # `f` is part of island, add to island and stack
                    used[f.index] = True
                    island.append(f)
                    stack.append(f)
        yield island
