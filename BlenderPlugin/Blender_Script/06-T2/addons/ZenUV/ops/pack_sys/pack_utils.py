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

# Copyright 2023, Valeriy Yatsenko

import bpy
import bmesh
from dataclasses import dataclass, field

from ZenUV.utils.selection_utils import SelectionProcessor, UniSelectedObject

from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer)
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils.vlog import Log


@dataclass
class PackSelectedObject(UniSelectedObject):


    is_hidden_faces: bool = False
    f_pack_excluded_idxs: list = field(default_factory=list)

    def store_selection(self, context: bpy.types.Context) -> None:

        me = self.obj.data
        bm = bmesh.from_edit_mesh(me)
        self.bm = bm
        self.uv_layer = verify_uv_layer(bm)

        b_is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync


        self.selected_items = SelectionProcessor.get_selected_items(
            me, bm, self.uv_layer,
            b_is_store_loops=b_is_not_sync)

    def restore_selection(self, context: bpy.types.Context) -> None:
        """ Restore selected elements depending of Blender selection Mode """
        b_is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        SelectionProcessor.restore_selection_in_object(self, b_is_not_sync)

    def hide_p_excluded(self, context: bpy.types.Context):
        p_facemap = self.get_p_excl_facemap()
        if p_facemap is None:
            return
        islands = [island for island in island_util.get_islands(context, self.bm) if True in [f[p_facemap] for f in island]]

        self.f_pack_excluded_idxs.extend([f.index for island in islands for f in island])
        self.bm.faces.ensure_lookup_table()
        for i in self.f_pack_excluded_idxs:
            self.bm.faces[i].hide_set(True)

    def unhide_p_excluded(self):
        if self.get_p_excl_facemap() is None:
            return
        self.bm.faces.ensure_lookup_table()
        for i in self.f_pack_excluded_idxs:
            self.bm.faces[i].hide_set(False)

    def get_p_excl_facemap(self):
        from ZenUV.utils.constants import PACK_EXCLUDED_FACEMAP_NAME
        return self.bm.faces.layers.int.get(PACK_EXCLUDED_FACEMAP_NAME, None)

    def is_pack_excluded_present(self):
        p_facemap = self.get_p_excl_facemap()
        if p_facemap is None:
            return False
        else:
            self.bm.faces.ensure_lookup_table()
            return True in [f[p_facemap] for f in self.bm.faces]

    def check_is_hidden_faces(self):
        if get_prefs().packEngine == "UVPACKER":
            self.is_hidden_faces = True in [f.hide for f in self.bm.faces] or self.is_pack_excluded_present()


class PackObjectsStorage:


    def __init__(self) -> None:
        self.objs: list = []
        self.is_sync_mode: bool = None
        self.selection_mode: str = None  # in ['EDGE', 'FACE', 'VERTEX']
        self.marker_face_idxs: list = []

    def clear(self) -> None:
        self.objs.clear()
        self.is_sync_mode = None
        self.selection_mode = None
        self.marker_face_idxs.clear()

    def is_hidden_faces_in_objects(self) -> bool:
        return True in [o.is_hidden_faces for o in self.objs]

    def hide_pack_excluded(self, context: bpy.types.Context):
        for s_obj in self.objs:
            s_obj.hide_p_excluded(context)

    def unhide_pack_excluded(self) -> None:
        if self.is_unhide_allowed():
            for s_obj in self.objs:
                s_obj.unhide_p_excluded()

    def is_unhide_allowed(self):
        return not get_prefs().packEngine == "UVPACKER"

    def remove_marker_faces(self):
        if len(self.marker_face_idxs):
            self.objs[0].bm.faces.ensure_lookup_table()
            bmesh.ops.delete(self.objs[0].bm, geom=[self.objs[0].bm.faces[i] for i in self.marker_face_idxs], context='FACES')

    def collect_objects(self, context: bpy.types.Context) -> bool:

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not objs:
            return False
        else:
            self.selection_mode = self.check_selection_mode(context)
            self.is_sync_mode = context.space_data.type == 'VIEW_3D' \
                or context.space_data.type == 'IMAGE_EDITOR' \
                and context.scene.tool_settings.use_uv_select_sync is True
            for obj in objs:
                s_obj = PackSelectedObject(obj)
                s_obj.store_selection(context)
                s_obj.check_is_hidden_faces()
                s_obj.obj_name = obj.name
                self.objs.append(s_obj)
        return True

    def restore_selection_all_objects(self, context: bpy.types.Context) -> None:
        PackUtils.bpy_select_by_context(context, action='DESELECT')

        s_obj: PackSelectedObject = None
        if not get_prefs().packEngine == "UVPACKER":
            for s_obj in self.objs:
                s_obj.restore_selection(context)

    def check_selection_mode(self, context: bpy.types.Context) -> str:
        if context.tool_settings.mesh_select_mode[:] == (False, True, False):
            return 'EDGE'
        elif context.tool_settings.mesh_select_mode[:] == (False, False, True):
            return 'FACE'
        return 'VERTEX'

    def select_islands(self, context) -> None:
        from ZenUV.utils.generic import select_loops
        if context.area.type == "IMAGE_EDITOR" and not context.scene.tool_settings.use_uv_select_sync:
            for s_obj in self.objs:
                bm = s_obj.bm
                uv_layer = s_obj.uv_layer
                select_loops(island_util.get_island(context, bm, uv_layer), uv_layer, state=True)
                bm.select_flush_mode()
                # bmesh.update_edit_mesh(s_obj.obj.data, loop_triangles=False, destructive=False)
        else:
            s_obj: PackSelectedObject = None
            for s_obj in self.objs:
                bm = s_obj.bm
                uv_layer = s_obj.uv_layer
                islands = island_util.get_island(context, bm, uv_layer)
                for island in islands:
                    for f in island:
                        f.select_set(True)
                if not context.scene.tool_settings.use_uv_select_sync:
                    select_loops(islands, uv_layer, state=True)
                bm.select_flush_mode()
                # bmesh.update_edit_mesh(s_obj.obj.data, loop_triangles=False, destructive=False)

    def yield_selected_objects(self):
        s_obj: UniSelectedObject = None
        for s_obj in self.objs:
            p_obj = bpy.data.objects.get(s_obj.obj.name, None)
            if not p_obj:
                continue
            s_obj.obj = p_obj
            bm = bmesh.from_edit_mesh(p_obj.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            s_obj.bm = bm
            s_obj.uv_layer = bm.loops.layers.uv.active
            if not s_obj.uv_layer:
                continue
            yield s_obj

    def get_object_by_name(self, obj_name: str):
        p_obj = bpy.data.objects.get(obj_name, None)
        if not p_obj:
            return None
        return p_obj


class PackUtils:

    @classmethod
    def resolve_pack_selected_only(
            cls,
            context: bpy.types.Context,
            addon_prefs: bpy.types.AddonPreferences,
            Storage: PackObjectsStorage,
            set_sel_only: bool = False) -> None:

        if set_sel_only:
            cls.bpy_select_by_context(context, action='SELECT')
        else:
            if addon_prefs.packSelectedIslOnly:
                Storage.select_islands(context)
            else:
                cls.bpy_select_by_context(context, action='SELECT')

    @classmethod
    def bpy_select_by_context(cls, context: bpy.types.Context, action: str = 'DESELECT'):
        if not context.scene.tool_settings.use_uv_select_sync:
            if context.space_data.type == 'IMAGE_EDITOR':
                if action == 'SELECT':
                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.uv.select_all(action='SELECT')
                else:
                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.mesh.select_all(action='SELECT')

                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.uv.select_all(action='DESELECT')

                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.mesh.select_all(action='DESELECT')
            else:
                if action == 'SELECT':
                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.mesh.select_all(action='SELECT')

                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.uv.select_all(action='SELECT')
                else:
                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.mesh.select_all(action='SELECT')

                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.uv.select_all(action='DESELECT')

                    if bpy.ops.uv.select_all.poll():
                        bpy.ops.mesh.select_all(action='DESELECT')
        else:
            if bpy.ops.uv.select_all.poll():
                bpy.ops.mesh.select_all(action=action)
