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

# Copyright 2025, Valeriy Yatsenko - lightbio@gmail.com, Alex Zhornyak - alexander.zhornyak@gmail.com

""" Zen UV Islands Utilities """

import bpy
import bmesh

from .mesh_factory import MeshIslandUtils

from ..utils.blender_zen_utils import (
    ZenPolls, is_loop_domain,
    is_sync_off, get_selection_mode)


# from ..utils.vlog import Log


class UvIslandUtils:

    @staticmethod
    def is_island_selected(context, facelist, uv_layer):
        if is_loop_domain(context):
            if ZenPolls.version_since_5_0_0:
                if is_sync_off(context):
                    return any(loop.uv_select_vert for face in facelist for loop in face.loops if face.select)
                else:
                    return any(loop.uv_select_vert for face in facelist for loop in face.loops)
            else:
                return any(loop[uv_layer].select for face in facelist for loop in face.loops if face.select)
        else:
            return any(v.select for f in facelist for v in f.verts)

    @classmethod
    def sort_islands(cls, islands: list):
        return [sorted(island, key=lambda f: f.index) for island in islands]

    @classmethod
    def get_islands_by_vertlist_indexes(cls, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, vertlist: list, b_incl_partially_hidden: bool = False, b_sorted: bool = False):
        ''' Return islands by vertlist in indexes '''
        bm.verts.ensure_lookup_table()
        preselection = [face for vert in [bm.verts[i] for i in vertlist] for face in vert.link_faces if not face.hide]
        if b_sorted:
            p_islands = [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, preselection, b_include_partially_hidden=b_incl_partially_hidden)]

            return cls.sort_islands(p_islands)

        return [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, preselection, b_include_partially_hidden=b_incl_partially_hidden)]

    @classmethod
    def get_islands_by_edgelist_indexes(cls, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, edgelist: list, b_incl_partially_hidden: bool = False, b_sorted: bool = False):
        ''' Return islands by edgelist in indexes '''
        bm.edges.ensure_lookup_table()
        preselection = {face for edge in [bm.edges[i] for i in edgelist] for face in edge.link_faces if not face.hide}
        if b_sorted:
            p_islands = [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, preselection, b_include_partially_hidden=b_incl_partially_hidden)]

            return cls.sort_islands(p_islands)

        return [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, preselection, b_include_partially_hidden=b_incl_partially_hidden)]

    # TODO Check this
    @classmethod
    def get_islands_by_facelist(
        cls,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        facelist: list,
        b_incl_partially_hidden: bool = False,
        b_sorted: bool = False,
        use_seams_as_separator: bool = False
    ):

        ''' Return islands by facelist '''
        if b_sorted:
            if use_seams_as_separator:
                p_islands = [list(i) for i in MeshIslandUtils._internal_yield_mesh_islands(bm, facelist, b_include_partially_hidden=b_incl_partially_hidden)]
            else:
                p_islands = [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, facelist, b_include_partially_hidden=b_incl_partially_hidden)]

            return cls.sort_islands(p_islands)

        if use_seams_as_separator:
            return [list(i) for i in MeshIslandUtils._internal_yield_mesh_islands(bm, facelist, b_include_partially_hidden=b_incl_partially_hidden)]

        return [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, facelist, b_include_partially_hidden=b_incl_partially_hidden)]

    @staticmethod
    def get_uv_bound_edges_indexes(facelist, uv_layer):
        """ Return indexes of border edges of given island (faces) from current UV Layer """
        if not facelist:
            return []

        edges = {edge for face in facelist for edge in face.edges if edge.link_loops}
        return [edge.index for edge in edges
                if edge.link_loops[0][uv_layer].uv
                != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
                or edge.link_loops[-1][uv_layer].uv
                != edge.link_loops[-1].link_loop_radial_next.link_loop_next[uv_layer].uv]

    @staticmethod
    def _match_uv(face, vert, uv, uv_layer):
        """
        Checks whether a given UV coordinate matches the UV of a specific vertex within a face.

        Args:
            face (bmesh.types.BMFace): The face to search through.
            vert (bmesh.types.BMVert): The vertex to compare against.
            uv (Vector): The UV coordinate to match.
            uv_layer (bmesh.types.BMLayerItem): The active UV layer.

        Returns:
            bool: True if the given vertex in the face has a UV coordinate equal to `uv`,
            otherwise False.
        """
        return any(uv == loop[uv_layer].uv for loop in face.loops if loop.vert == vert)

    @classmethod
    def get_selected_uv_islands(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        in_indices: bool = False,
        b_incl_partially_hidden: bool = False,
        use_seams_as_separator: bool = False
    ):
        """
        Get currently selected UV islands.

        Returns UV islands based on the current selection in the UV Editor.

        This method retrieves only the selected UV islands from the mesh.
        If `in_indices` is True, it returns lists of face indices instead of face objects.

        Args:
            context (bpy.types.Context): The current Blender context.
            bm (bmesh.types.BMesh): The BMesh data structure of the active object in Edit Mode.
            uv_layer (bmesh.types.BMLayerItem): The active UV layer used for island detection.
            in_indices (bool, optional): If True, returns islands as lists of face indices instead of BMFace objects.
                Defaults to False.

        Returns:
            list[list[bmesh.types.BMFace] | list[int]]:
            A list of UV islands, where each island is a list of faces (or their indices if `in_indices` is True).
        """

        if in_indices:
            return [
                [f.index for f in group]
                for group in cls.get_uv_islands(
                    context, bm, uv_layer,
                    b_selected_only=True,
                    b_include_hidden=False,
                    b_incl_partially_hidden=b_incl_partially_hidden,
                    use_seams_as_separator=use_seams_as_separator)]

        return cls.get_uv_islands(
            context, bm, uv_layer,
            b_selected_only=True,
            b_include_hidden=False,
            b_incl_partially_hidden=b_incl_partially_hidden,
            use_seams_as_separator=use_seams_as_separator)

    @classmethod
    def get_all_uv_islands(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        in_indices: bool = False,
        include_hidden: bool = False,
        b_incl_partially_hidden: bool = False,
        use_seams_as_separator: bool = False
    ):
        """
        Returns all UV islands in the mesh, regardless of selection state.

        This method collects every UV island present in the current UV layer.
        If `in_indices` is True, it returns lists of face indices instead of face objects.

        Args:
            context (bpy.types.Context): The current Blender context.
            bm (bmesh.types.BMesh): The BMesh data structure of the active object in Edit Mode.
            uv_layer (bmesh.types.BMLayerItem): The active UV layer used for island detection.
            in_indices (bool, optional): If True, returns islands as lists of face indices instead of BMFace objects.
                Defaults to False.

        Returns:
            list[list[bmesh.types.BMFace] | list[int]]:
            A list of UV islands, where each island is a list of faces (or their indices if `in_indices` is True).
        """

        if include_hidden:
            b_incl_partially_hidden = True

        if in_indices:
            return [
                [f.index for f in group]
                for group in cls.get_uv_islands(
                    context, bm, uv_layer,
                    b_selected_only=False,
                    b_include_hidden=include_hidden,
                    b_incl_partially_hidden=b_incl_partially_hidden,
                    use_seams_as_separator=use_seams_as_separator)]

        return cls.get_uv_islands(
            context, bm, uv_layer,
            b_selected_only=False,
            b_include_hidden=include_hidden,
            b_incl_partially_hidden=b_incl_partially_hidden,
            use_seams_as_separator=use_seams_as_separator)

    @classmethod
    def get_uv_islands(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        b_selected_only: bool,
        b_include_hidden: bool = False,
        b_incl_partially_hidden: bool = False,
        b_sorted: bool = False,
        use_seams_as_separator: bool = False
    ):
        if not uv_layer:
            return []

        if b_selected_only:
            b_include_hidden = False

        bm.faces.ensure_lookup_table()

        if b_selected_only:
            preselection = SelectionUtils._internal_get_faces_by_any_init_selection(context, bm, uv_layer, b_include_hidden)

        else:
            if b_include_hidden:
                preselection = bm.faces
            else:
                preselection = {f for f in bm.faces if not f.hide}

        if not b_sorted:
            if use_seams_as_separator:
                return [list(i) for i in MeshIslandUtils._internal_yield_mesh_islands(bm, preselection, b_include_partially_hidden=b_incl_partially_hidden)]
            return [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, preselection, b_include_partially_hidden=b_incl_partially_hidden)]

        if use_seams_as_separator:
            p_islands = [list(i) for i in MeshIslandUtils._internal_yield_mesh_islands(bm, preselection, b_include_partially_hidden=b_incl_partially_hidden)]
        else:
            p_islands = [list(i) for i in cls._internal_yield_uv_islands(bm, uv_layer, preselection, b_include_partially_hidden=b_incl_partially_hidden)]

        return [sorted(island, key=lambda f: f.index) for island in p_islands]

    @classmethod
    def yield_uv_islands(
        cls,
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        b_selected_only: bool,
        b_include_hidden: bool,
        b_include_partially_hidden: bool = False,
        use_seams_as_separator: bool = False
    ):

        bm.faces.ensure_lookup_table()

        if b_selected_only:
            preselection = SelectionUtils._internal_get_faces_by_any_init_selection(context, bm, uv_layer, b_include_hidden)

        else:
            if b_include_hidden:
                preselection = bm.faces
            else:
                preselection = {f for f in bm.faces if not f.hide}

        if use_seams_as_separator:
            yield from MeshIslandUtils._internal_yield_mesh_islands(bm, preselection, b_include_partially_hidden=b_include_partially_hidden)

        yield from cls._internal_yield_uv_islands(bm, uv_layer, preselection, b_include_partially_hidden=b_include_partially_hidden)

    @classmethod
    def _internal_yield_uv_islands(
        cls,
        bm: bmesh.types.BMesh,
        uv_layer: bmesh.types.BMLayerItem,
        facelist: list,
        b_include_partially_hidden: bool = False
    ):

        used = [False] * len(bm.faces)
        seed_face: bmesh.types.BMFace
        for seed_face in facelist:
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
                        # if not b_include_partially_hidden and f.hide:
                        #     continue
                        if f is current_face or used[f.index]:
                            continue
                        if not cls._match_uv(f, v, uv, uv_layer):
                            continue
                        # `f` is part of island, add to island and stack
                        used[f.index] = True
                        island.append(f)
                        stack.append(f)

            if not b_include_partially_hidden and any(f.hide for f in island):
                continue

            yield island


class SelectionUtils:

    @staticmethod
    def get_faces_by_any_init_selection_below_b5(context, bm):
        """
            Returns face indices converted from selected elements
            Use only for Island detection !!!
        """
        if is_loop_domain(context):
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                return []

            uv_selection_mode = context.scene.tool_settings.uv_select_mode
            if ZenPolls.version_since_3_2_0:
                if uv_selection_mode == 'VERTEX':
                    return list({f for f in bm.faces if not f.hide and f.select and True in [loop[uv_layer].select for loop in f.loops]})
                else:
                    return list({f for f in bm.faces for loop in f.loops if not f.hide and f.select and loop[uv_layer].select and loop[uv_layer].select_edge})
            else:
                if uv_selection_mode == 'VERTEX':
                    return list({f for f in bm.faces if not f.hide and f.select and True in [loop[uv_layer].select for loop in f.loops]})
                else:
                    return list({f for f in bm.faces for loop in f.loops if not f.hide and f.select and loop[uv_layer].select})
        # Mesh domain
        else:
            selection_mode = context.tool_settings.mesh_select_mode
            if selection_mode[1]:
                return [face for edge in [e for e in bm.edges if e.select] for face in edge.link_faces if not face.hide]
            elif selection_mode[2]:
                return [face for face in bm.faces if face.select and not face.hide]
            elif selection_mode[0]:
                return [face for vert in [v for v in bm.verts if v.select] for face in vert.link_faces if not face.hide]

    @staticmethod
    def _internal_get_faces_by_any_init_selection(context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, b_include_hidden: bool, area_type=None):
        """
        Only for islands detection
        Returns a list of polygons adjacent to the current selection (vertices, edges, or faces).

        This function is primarily used to identify connected UV or mesh islands
        based on the user's initial selection in Edit Mode.
        It analyzes mesh connectivity and expands the selection to include
        all polygons that share common elements (vertices or edges) with the selected ones.
        """
        if area_type is None:
            p_space = getattr(context, "space_data", None)
            if p_space:
                area_type = p_space.type

        b_is_uv_editor = area_type == 'IMAGE_EDITOR'

        if ZenPolls.version_since_5_0_0:

            selection_mode = get_selection_mode(context, area_type=area_type)
            # Collect selection in UV EDITOR
            if b_is_uv_editor:
                if is_loop_domain(context, area_type=area_type):
                    if is_sync_off(context, area_type=area_type):
                        if selection_mode == 'FACE':
                            if b_include_hidden:
                                return [f for f in bm.faces if f.select and f.uv_select]
                            return [f for f in bm.faces if f.select and f.uv_select and not f.hide]
                        else:
                            if b_include_hidden:
                                return [f for f in bm.faces if f.select and any([loop.uv_select_vert or loop.uv_select_edge for loop in f.loops])]
                            return [f for f in bm.faces if f.select and not f.hide and any([loop.uv_select_vert or loop.uv_select_edge for loop in f.loops])]
                    else:
                        if not bm.uv_select_sync_valid:
                            bm.uv_select_sync_from_mesh()

                        if selection_mode == 'FACE':
                            if b_include_hidden:
                                return [f for f in bm.faces if f.uv_select]
                            return [f for f in bm.faces if f.uv_select and not f.hide]
                        else:
                            if b_include_hidden:
                                return [f for f in bm.faces if any([loop.uv_select_vert or loop.uv_select_edge for loop in f.loops])]
                            return [f for f in bm.faces if not f.hide and any([loop.uv_select_vert or loop.uv_select_edge for loop in f.loops])]
                else:

                    if selection_mode == 'FACE':
                        if b_include_hidden:
                            return [f for f in bm.faces if f.select]
                        return [f for f in bm.faces if not f.hide and (f.select or any(v.select for v in f.verts))]
                    else:
                        if b_include_hidden:
                            return [f for f in bm.faces if f.select or any(v.select for v in f.verts)]
                        return [f for f in bm.faces if not f.hide and (f.select or any(v.select for v in f.verts))]

            # Collect selection in 3D VIEW
            else:
                if selection_mode == 'FACE':
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select]
                    return [f for f in bm.faces if f.select and not f.hide]
                else:
                    if b_include_hidden:
                        return [f for f in bm.faces if any(v.select for v in f.verts)]
                    return [f for f in bm.faces if not f.hide and any(v.select for v in f.verts)]

        else:  # Below Blender v5.0
            if is_loop_domain(context):
                uv_selection_mode = context.scene.tool_settings.uv_select_mode
                if uv_selection_mode == 'FACE':
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select and all(lp[uv_layer].select for lp in f.loops)]
                    return [f for f in bm.faces if f.select and all(lp[uv_layer].select for lp in f.loops) and not f.hide]
                else:
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select and any([loop[uv_layer].select for loop in f.loops])]
                    return [f for f in bm.faces if f.select and not f.hide and any([loop[uv_layer].select for loop in f.loops])]
            else:
                mesh_selection_mode = context.tool_settings.mesh_select_mode
                if mesh_selection_mode[:] == (False, False, True):
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select]
                    return [f for f in bm.faces if f.select and not f.hide]
                else:
                    if b_include_hidden:
                        return [f for f in bm.faces if any(v.select for v in f.verts)]
                    return [f for f in bm.faces if any(v.select for v in f.verts) and not f.hide]

    @staticmethod
    def get_faces_by_any_init_selection(context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, b_include_hidden: bool = False, area_type=None):
        """
        Returns a list of polygons adjacent to the current selection (vertices, edges, or faces).
        The face selected if all verts selected.
        """

        if area_type is None:
            p_space = getattr(context, "space_data", None)
            if p_space:
                area_type = p_space.type

        b_is_uv_editor = area_type == 'IMAGE_EDITOR'

        if ZenPolls.version_since_5_0_0:
            # Collect selection in UV EDITOR
            selection_mode = get_selection_mode(context, area_type=area_type)
            if b_is_uv_editor:
                if is_sync_off(context, area_type=area_type):
                    if selection_mode == 'FACE':
                        if b_include_hidden:
                            return [f for f in bm.faces if f.select and f.uv_select]
                        return [f for f in bm.faces if f.select and f.uv_select and not f.hide]
                    else:
                        if b_include_hidden:
                            return [f for f in bm.faces if f.select and all([loop.uv_select_vert for loop in f.loops])]
                        return [f for f in bm.faces if f.select and not f.hide and all([loop.uv_select_vert for loop in f.loops])]

                # UV Sync Selection is On
                else:
                    if not bm.uv_select_sync_valid:
                        bm.uv_select_sync_from_mesh()

                    if selection_mode == 'FACE':
                        if b_include_hidden:
                            return [f for f in bm.faces if f.uv_select or all(lp.uv_select_vert for lp in f.loops)]
                        return [f for f in bm.faces if not f.hide and (f.uv_select or all(lp.uv_select_vert for lp in f.loops))]
                    else:
                        if b_include_hidden:
                            return [f for f in bm.faces if f.uv_select or all(lp.uv_select_vert for lp in f.loops)]
                        return [f for f in bm.faces if not f.hide and (f.uv_select or all(lp.uv_select_vert for lp in f.loops))]

            # Collect selection in 3D VIEW
            else:
                mesh_selection_mode = context.tool_settings.mesh_select_mode
                if mesh_selection_mode[:] == (False, False, True):
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select]
                    return [f for f in bm.faces if f.select and not f.hide]
                else:
                    if b_include_hidden:
                        return [f for f in bm.faces if all(v.select for v in f.verts)]
                    return [f for f in bm.faces if all(v.select for v in f.verts) and not f.hide]

        else:
            if is_sync_off(context, area_type=area_type):
                uv_selection_mode = context.scene.tool_settings.uv_select_mode
                if uv_selection_mode == 'FACE':
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select and all(lp[uv_layer].select for lp in f.loops)]
                    return [f for f in bm.faces if f.select and all(lp[uv_layer].select for lp in f.loops) and not f.hide]
                else:
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select and all([loop[uv_layer].select for loop in f.loops])]
                    return [f for f in bm.faces if f.select and not f.hide and all([loop[uv_layer].select for loop in f.loops])]
            else:
                mesh_selection_mode = context.tool_settings.mesh_select_mode
                if mesh_selection_mode[:] == (False, False, True):
                    if b_include_hidden:
                        return [f for f in bm.faces if f.select]
                    return [f for f in bm.faces if f.select and not f.hide]
                if mesh_selection_mode[:] == (False, True, False):
                    if b_include_hidden:
                        return [f for f in bm.faces if all(e.select for e in f.edges)]
                    return [f for f in bm.faces if not f.hide and all(e.select for e in f.edges)]
                else:
                    if b_include_hidden:
                        return [f for f in bm.faces if all(v.select for v in f.verts)]
                    return [f for f in bm.faces if all(v.select for v in f.verts) and not f.hide]

    @staticmethod
    def select_faces_any_context_b5(context: bpy.types.Context, bm: bmesh.types.BMesh, facelist: list, state: bool, area_type=None):
        """
        Since Blender 5.0
        Selects the given faces in 3D View or UV Editor depending on context.
        Handles both UV Sync modes and ensures consistent selection synchronization.
        """
        """
        Selects the specified faces in either the 3D View or UV Editor, depending on the current context.

        This utility ensures consistent face selection between mesh and UV contexts.
        It handles both UV Sync On/Off modes and automatically updates selection states
        to reflect the current editor type.

        Args:
            context (bpy.types.Context): The current Blender context.
            bm (bmesh.types.BMesh): The BMesh data structure of the active object in Edit Mode.
            facelist (list[bmesh.types.BMFace]): The list of faces to select.
            state (bool): State of the face. True - Select, False - Deselect.

        Raises:
            RuntimeError: If the current editor type is not 'IMAGE_EDITOR' or 'VIEW_3D'.

        Behavior:
            - **VIEW_3D:**
            Selects the given faces in mesh edit mode and synchronizes the UV selection
            using `bm.uv_select_sync_from_mesh()`.

            - **IMAGE_EDITOR:**
            - If **UV Sync Selection** is enabled, it performs synchronized selection
                using `bm.uv_select_foreach_set_from_mesh()` and `bm.uv_select_sync_to_mesh()`.
            - If **UV Sync Selection** is disabled, it directly sets `f.uv_select` and
                `lp.uv_select_vert` flags for each face and its loops.

        This method allows the same selection logic to be applied seamlessly in both editors.
        """

        if not facelist:
            return

        if area_type is None:
            p_space = getattr(context, "space_data", None)
            if p_space:
                area_type = p_space.type

        b_is_uv_editor = area_type == 'IMAGE_EDITOR'

        if b_is_uv_editor:
            if is_sync_off(context, area_type=area_type):
                bm.uv_select_sync_valid = True
                bm.uv_select_foreach_set_from_mesh(
                    state,
                    faces=[f for f in facelist],
                    sticky_select_mode=context.tool_settings.uv_sticky_select_mode)
            else:
                for f in facelist:
                    f.select = state
                    f.uv_select = state
                    for lp in f.loops:
                        lp.uv_select_vert = state
                        lp.uv_select_edge = state
        else:
            for f in facelist:
                f.select = state
            bm.uv_select_sync_from_mesh(sticky_select_mode=context.tool_settings.uv_sticky_select_mode)

    @staticmethod
    def select_faces_any_context_below_b5(context: bpy.types.Context, uv_layer: bmesh.types.BMLayerItem, facelist: list, state: bool):
        """
        Before Blender 5.0
        Selects the given faces in 3D View or UV Editor depending on context.
        state: the state of the face. True - Select, False - Deselect.
        """

        if not facelist:
            return

        if is_sync_off(context):
            for f in facelist:
                for lp in f.loops:
                    lp[uv_layer].select = state
                    lp[uv_layer].select_edge = state

        else:
            for f in facelist:
                f.select = state

    @classmethod
    def select_faces_any_context(cls, context: bpy.types.Context, facelist: list, state: bool, bm: bmesh.types.BMesh = None, uv_layer: bmesh.types.BMLayerItem = None):
        if ZenPolls.version_since_5_0_0:
            if not bm:
                raise RuntimeError('Since Blender v5.0 "bm" required.')
            cls.select_faces_any_context_b5(context, bm, facelist, state=state)
        else:
            if not uv_layer:
                raise RuntimeError('Above Blender v5.0 "uv_layer" required.')
            cls.select_faces_any_context_below_b5(context, uv_layer, facelist, state=state)

    @staticmethod
    def select_all(bm: bmesh.types.BMesh, is_select: bool):
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f.uv_select = is_select
            for lp in f.loops:
                lp.uv_select_vert = is_select
                lp.uv_select_edge = is_select

    @classmethod
    def select_uv_border(
            cls,
            context: bpy.types.Context,
            bm: bmesh.types.BMesh,
            uv_layer: bmesh.types.BMLayerItem,
            mode: str = 'ALL_ISLANDS',
            is_clear_selection: bool = False) -> bool:

        ''' Assume that we are working only in edge selection mode '''

        if uv_layer is None:
            return False

        from ..utils.loops_factory import LoopsFactory
        if mode == 'FACES':
            grouplist = [SelectionUtils.get_faces_by_any_init_selection(context, bm, uv_layer, b_include_hidden=False), ]
        elif mode == 'ISLAND':
            grouplist = UvIslandUtils.get_selected_uv_islands(context, bm, uv_layer)
        elif mode == 'ALL_ISLANDS':
            grouplist = UvIslandUtils.get_all_uv_islands(context, bm, uv_layer)
        else:
            raise RuntimeError("mode not in ['FACES', 'ISLAND', 'ALL_ISLANDS']")

        if is_clear_selection and (mode == 'ISLAND' or mode == 'FACES'):
            for group in grouplist:
                LoopsFactory.select_loops(context, bm, [lp for f in group for lp in f.loops], uv_layer, state=False)

        for group in grouplist:
            looplist = LoopsFactory.get_uv_border_loops_from_facelist(group, uv_layer, include_split_uv_coo=True)
            LoopsFactory.select_loops(context, bm, looplist, uv_layer, state=True)


if __name__ == "__main__":
    pass
