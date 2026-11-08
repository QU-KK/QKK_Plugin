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

import bpy
import bmesh
from dataclasses import dataclass, field

from ..utils.uv_factory import UvIslandUtils
from ..ops.zen_unwrap.finishing import FINISHED_FACEMAP_NAME
from ..utils.generic import verify_uv_layer
from ..utils.blender_zen_utils import ZenPolls


class MarkStateManager:

    def __init__(self, context: bpy.types.Context) -> None:
        a_prefs = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences
        self.Gpriority = a_prefs.useGlobalMarkSettings
        self.Gseam = a_prefs.markSeamEdges
        self.Gsharp = a_prefs.markSharpEdges

    # def get_state(self):
    #     if self.Gpriority:
    #         return self.Gseam, self.Gsharp
    #     else:
    #         return self.Lseam, self.Lsharp

    def get_state_from_generic_operator(self, b_is_mark_seams: bool, b_is_mark_sharp: bool):
        if self.Gpriority:
            return self.Gseam, self.Gsharp
        else:
            return b_is_mark_seams, b_is_mark_sharp


# def call_from_zen_check():
#     return ZUV_OT_Mark_Seams.call_from_zen


def restore_selected_faces(selfaces):
    for face in selfaces:
        face.select = True


def assign_seam_to_edges(edges, assign=True):
    for edge in edges:
        edge.seam = assign


def assign_sharp_to_edges(edges, assign=True):
    for edge in edges:
        edge.smooth = not assign


def assign_seam_to_selected_edges(bm):
    for edge in bm.edges:
        if edge.select:
            edge.seam = True


def unmark_all_seams_sharp(bm, cl_seam=False, cl_sharp=False):
    bm.edges.ensure_lookup_table()
    if cl_seam:
        for edge in bm.edges:
            edge.seam = False
    if cl_sharp:
        for edge in bm.edges:
            edge.smooth = True


def mark_seams_by_uv_border(bm):
    bm.edges.ensure_lookup_table()
    uv_layer = verify_uv_layer(bm)
    faces = [f for f in bm.faces if not f.hide]
    for i in UvIslandUtils.get_uv_bound_edges_indexes(faces, uv_layer):
        bm.edges[i].seam = True


def sharp_by_uv_border(context: bpy.types.Context, bm, uv_layer, influence: str):
    if influence == 'ISLAND':
        from collections import Counter
        for island in UvIslandUtils.yield_uv_islands(context, bm, uv_layer, b_selected_only=False, b_include_hidden=False):
            edges = (edge for face in island for edge in face.edges if edge.link_loops)
            i_bound_edges = Counter(
                [edge.index for edge in edges
                    if edge.link_loops[0][uv_layer].uv
                    != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
                    or edge.link_loops[-1][uv_layer].uv
                    != edge.link_loops[-1].link_loop_radial_next.link_loop_next[uv_layer].uv])

            for i, count in i_bound_edges.items():
                if count >= 2:
                    continue
                bm.edges[i].smooth = False
    elif influence == 'UV':
        faces = [f for f in bm.faces if not f.hide]
        for i in UvIslandUtils.get_uv_bound_edges_indexes(faces, uv_layer):
            bm.edges[i].smooth = False
    else:
        raise RuntimeError('influence not in ("ISLAND", "UV")')


def get_splits_edges_indices(island, uv_layer) -> int:
    from collections import Counter

    edges = (edge for face in island for edge in face.edges if edge.link_loops)
    i_bound_edges = Counter(
        [edge.index for edge in edges
            if edge.link_loops[0][uv_layer].uv
            != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
            or edge.link_loops[-1][uv_layer].uv
            != edge.link_loops[-1].link_loop_radial_next.link_loop_next[uv_layer].uv])

    for i, count in i_bound_edges.items():
        if count >= 2:
            yield i


def seams_by_open_edges(bm):
    for i in get_open_edges_indices(bm):
        bm.edges[i].seam = True


def get_open_edges_indices(bm):
    hidden_face_edges = {e.index for e in bm.edges if any(f.hide for f in e.link_faces) and not e.hide}
    boundary_edges = {e.index for e in bm.edges if e.is_boundary and not e.link_faces[0].hide}
    sources = hidden_face_edges | boundary_edges
    return sources


def seams_by_sharp(bm):
    for edge in bm.edges:
        edge.seam = not edge.smooth


def sharp_by_seam(bm):
    for edge in bm.edges:
        edge.smooth = not edge.seam


@dataclass
class ObjMarkState:

    bl_object: bpy.types.Object
    bm: bmesh.types.BMesh = None

    mode: str = None

    faces: list = field(default_factory=list)
    edges_inside: list = field(default_factory=list)
    edges: list = field(default_factory=list)

    b_is_seam_exist: bool = False
    b_is_remove_inside: bool = False


class MarkFactory:

    message: str = ''
    raise_popup: bool = False
    popup_name: str = ''

    b_is_use_popup: bool = False

    @classmethod
    def initialize(cls):
        cls.message = ''
        cls.raise_popup = False
        cls.popup_name = ''
        cls.b_is_use_popup = False

    @classmethod
    def _remove_inside(cls, ST: ObjMarkState, b_inf_seam: bool = True, b_inf_sharp: bool = True):
        ST.bm.edges.ensure_lookup_table()
        if b_inf_seam is True and b_inf_sharp is False:
            for i in ST.edges_inside:
                ST.bm.edges[i].seam = False
        elif b_inf_seam is True and b_inf_sharp is True:
            for i in ST.edges_inside:
                ST.bm.edges[i].seam = False
                ST.bm.edges[i].smooth = True
        elif b_inf_seam is False and b_inf_sharp is True:
            for i in ST.edges_inside:
                ST.bm.edges[i].smooth = True
        else:
            pass

    @classmethod
    def _assign_to_edges(cls, ST: ObjMarkState, b_inf_seam: bool = True, b_inf_sharp: bool = True, assign: bool = True):
        ST.bm.edges.ensure_lookup_table()
        if b_inf_seam is True and b_inf_sharp is False:
            for i in ST.edges:
                ST.bm.edges[i].seam = assign
        elif b_inf_seam is True and b_inf_sharp is True:
            for i in ST.edges:
                ST.bm.edges[i].seam = assign
                ST.bm.edges[i].smooth = not assign
        elif b_inf_seam is False and b_inf_sharp is True:
            for i in ST.edges:
                ST.bm.edges[i].smooth = not assign
        else:
            pass

    @classmethod
    def _clear_finished(cls, ST: ObjMarkState):
        ''' Clear tag "FINISHED" for selected faces '''
        fin_fmap = ST.bm.faces.layers.int.get(FINISHED_FACEMAP_NAME, None)
        ST.bm.faces.ensure_lookup_table()
        if fin_fmap is not None:
            for i in ST.faces:
                ST.bm.faces[i][fin_fmap] = 0

    @classmethod
    def _get_bound_edges_from_faces(cls, facelist: list) -> list:
        return {e for f in facelist for e in f.edges if e.is_boundary or not all(f.select for f in e.link_faces)}

    @classmethod
    def _create_mark_state_object(cls, bl_object, overrided_selection_mode: str = None) -> ObjMarkState:

        return cls.create_mark_state_object_from_bm(
            bl_object=bl_object,
            bm=bmesh.from_edit_mesh(bl_object.data),
            overrided_selection_mode=overrided_selection_mode)

    @classmethod
    def create_mark_state_object_from_bm(cls, bl_object: bpy.types.Object, bm: bmesh.types.BMesh, overrided_selection_mode: str = None) -> ObjMarkState:

        if overrided_selection_mode is not None:
            p_select_mode = overrided_selection_mode
        else:
            if bm.select_mode != {'FACE'}:
                p_select_mode = 'EDGE'
            else:
                p_select_mode = 'FACE'

        if p_select_mode == 'FACE' and any((f.select for f in bm.faces)):
            p_faces = [f for f in bm.faces if f.select]
            p_face_edges = {e for f in p_faces for e in f.edges}
            p_edges = cls._get_bound_edges_from_faces([f for f in bm.faces if f.select])
            p_edges_indices = {e.index for e in p_edges}
            return ObjMarkState(
                bl_object=bl_object,
                bm=bm,
                mode='FACE',
                faces=[f.index for f in p_faces],
                edges_inside={e.index for e in p_face_edges}.difference(p_edges_indices),
                edges=p_edges_indices,
                b_is_seam_exist=False not in [edge.seam for edge in p_edges])

        elif p_select_mode == 'EDGE' and any((x.select for x in bm.edges)):
            p_edges = [e for e in bm.edges if e.select]
            return ObjMarkState(
                bl_object=bl_object,
                bm=bm,
                mode='EDGE',
                edges=[e.index for e in p_edges],
                b_is_seam_exist=False not in [edge.seam for edge in p_edges])

        else:
            return None

    @classmethod
    def collect_mark_objects(cls, objs: list, overrided_selection_mode: str = None) -> list:
        p_objs = []
        for obj in objs:
            p_obj = cls._create_mark_state_object(obj, overrided_selection_mode)
            if p_obj is not None:
                p_objs.append(p_obj)
        return p_objs

    @classmethod
    def mark_edges(
            cls,
            mark_objects: list,
            b_set_seam: bool,
            b_set_sharp: bool,
            is_silent_mode: bool = False,
            is_assign: bool = True,
            is_switch: bool = False,
            is_remove_inside: bool = True):

        ''' Mark edges as seam or/and sharp '''

        m_obj: ObjMarkState = None
        for m_obj in mark_objects:
            if m_obj is None:
                continue

            # Emulate Live Unwrap as Blender's native
            is_assign = not is_assign if is_switch and m_obj.b_is_seam_exist else is_assign

            if m_obj.mode == 'FACE':
                cls._clear_finished(m_obj)

                if is_remove_inside:
                    m_obj.b_is_remove_inside = True
                    cls._remove_inside(m_obj, b_set_seam, b_set_sharp)
                    bmesh.update_edit_mesh(m_obj.bl_object.data, loop_triangles=False, destructive=False)

                if not m_obj.edges and not is_remove_inside:
                    if not is_silent_mode:
                        if is_assign is True:
                            if cls.b_is_use_popup:
                                cls.raise_popup = True
                                cls.popup_name = "ZUV_MT_ZenMark_Popup"
                            else:
                                cls.message = "Nothing is produced. Selected faces do not have a borders."
                            return None
                        else:
                            cls.message = "Nothing is produced. Selected faces do not have a borders."
                            return None

                if m_obj.edges:
                    cls._assign_to_edges(m_obj, b_set_seam, b_set_sharp, is_assign)
                else:
                    cls.message = "Nothing is produced. Selected faces do not have a borders."

            if m_obj.mode == 'EDGE':
                cls._assign_to_edges(m_obj, b_set_seam, b_set_sharp, is_assign)

            bmesh.update_edit_mesh(m_obj.bl_object.data, loop_triangles=False, destructive=False)
