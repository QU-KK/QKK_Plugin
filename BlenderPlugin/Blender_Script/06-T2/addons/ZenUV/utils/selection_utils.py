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

# Copyright 2021, Valeriy Yatsenko


import bpy
import bmesh
from mathutils import Vector

import math
from dataclasses import dataclass, field

from ..utils.iter_utils import IterUtils
from ..utils.blender_zen_utils import (
    ZenPolls, is_loop_domain, get_selection_mode)
from ..utils.loops_factory import LoopsFactory
from ..utils.mesh_factory import MeshIslandUtils


@dataclass
class SelectedItems:

    selected_verts: list = field(default_factory=list)
    selected_edges: list = field(default_factory=list)
    selected_faces: list = field(default_factory=list)
    selected_loops: list = field(default_factory=list)

    is_storage_in_indices: bool = False

    def __str__(self) -> str:
        return f'\nSelected verts -> count: {len(self.selected_verts)}\n{self.selected_verts}\n' + \
            f'\nSelected edges -> count: {len(self.selected_edges)}\n{str(self.selected_edges)}\n' + \
            f'\nSelected faces -> count: {len(self.selected_faces)}\n{str(self.selected_faces)}\n' + \
            f'\nSelected loops -> count: {len(self.selected_loops)}\n{str(self.selected_loops)}\n'

    def show_storage(self, is_short: bool = True):
        if is_short:
            if self.is_storage_in_indices:
                print('Storage in Indices')
            else:
                print('Storage not in Indices')
            print(
                f'\nSelected verts -> count: {len(self.selected_verts)}\n' +
                f'\nSelected edges -> count: {len(self.selected_edges)}\n' +
                f'\nSelected faces -> count: {len(self.selected_faces)}\n' +
                f'\nSelected loops -> count: {len(self.selected_loops)}\n'
            )
        else:
            print(self)

    def get_elements(self):
        return self.selected_verts, self.selected_edges, self.selected_faces

    def convert_into_indices(self):
        self.selected_verts = [i.index for i in self.selected_verts]
        self.selected_edges = [i.index for i in self.selected_edges]
        self.selected_faces = [i.index for i in self.selected_faces]
        self.selected_loops = [lp.index for lp in self.selected_loops]


@dataclass
class UniSelectedObject:

    obj: bpy.types.Object = None
    obj_name: str = None

    bm: bmesh.types.BMesh = None
    uv_layer: bmesh.types.BMLayerItem = None

    selected_items: SelectedItems = None

    attribute_storage: dict = field(default_factory=dict)


class SelectionProcessor:

    result: bool = True
    message: str = ''

    CURSOR_UNDEFINED = Vector((math.nan, math.nan))

    @classmethod
    def get_uv_selection_center(cls, context: bpy.types.Context) -> Vector:
        """Get UV selection center:
        1) Image Area must be active
        2) Can not be used in draw functions !!!"""

        new_cursor = cls.CURSOR_UNDEFINED

        if bpy.ops.uv.snap_cursor.poll():
            p_space = context.space_data
            was_cursor = Vector(p_space.cursor_location)
            p_space.cursor_location = cls.CURSOR_UNDEFINED
            bpy.ops.uv.snap_cursor(target='SELECTED')
            new_cursor = Vector(p_space.cursor_location)
            p_space.cursor_location = was_cursor

        return new_cursor

    @classmethod
    def is_uv_selected(cls, context: bpy.types.Context):
        p_selection_center = cls.get_uv_selection_center(context)
        return math.isfinite(p_selection_center.x) and math.isfinite(p_selection_center.y)

    @classmethod
    def reset_state(cls):
        cls.result = True
        cls.message = ''

    @classmethod
    def collect_selected_objects(
            cls,
            context: bpy.types.Context,
            b_in_indices: bool = False,
            b_is_skip_objs_without_selection: bool = False,
            b_skip_uv_layer_fail: bool = False,
            b_skip_store_selected_items: bool = False
            ):

        from ..utils.generic import ResortObjects
        objs = ResortObjects.resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            cls.result = False
            cls.message = 'There are no selected objects'
            return []

        if b_is_skip_objs_without_selection:
            ResortObjects.reset_state()
            objs = ResortObjects.resort_objects_by_selection(context, objs, b_skip_uv_layer_fail=b_skip_uv_layer_fail)
            if ResortObjects.result is False:
                cls.result = False
                cls.message = ResortObjects.message
                return []
            if not objs:
                cls.result = False
                cls.message = 'Select something'
                return []

        b_is_loop_domain = is_loop_domain(context)

        return cls.store_selection(context, objs, b_is_loop_domain, b_in_indices=b_in_indices, b_skip_store_selected_items=b_skip_store_selected_items)

    @classmethod
    def store_selection(cls, context, p_unique_mesh_objects: list, b_is_loop_domain: bool, b_in_indices: bool = False, b_skip_store_selected_items: bool = False):
        p_storage = list()
        for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv(p_unique_mesh_objects, context, skip_obj_if_no_uv=True):

            if b_skip_store_selected_items:
                si = SelectedItems()
            else:
                si = cls.get_selected_items(context, obj.data, bm, uv_layer, b_is_loop_domain)

            if b_in_indices:
                si.is_storage_in_indices = True
                si.convert_into_indices()

            p_storage.append(UniSelectedObject(
                obj=obj,
                obj_name=obj.name,
                bm=bm,
                uv_layer=uv_layer,
                selected_items=si))

        return p_storage

    @classmethod
    def get_selected_items(cls, context, me, bm, uv_layer, b_is_store_loops: bool) -> SelectedItems:
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        SI = SelectedItems()

        SI.selected_verts = [
            item
            for item in bm.verts
            if not item.hide and item.select
        ] if me.total_vert_sel else []

        SI.selected_edges = [
            item
            for item in bm.edges
            if not item.hide and item.select
        ] if me.total_edge_sel else []

        SI.selected_faces = [
            item
            for item in bm.faces
            if not item.hide and item.select
        ] if me.total_face_sel else []

        if b_is_store_loops:
            if uv_layer:
                SI.selected_loops = cls._get_loops_selection(context, bm, uv_layer)
        return SI

    @classmethod
    def _get_loops_selection(cls, context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem):
        is_edge_sel_mode = get_selection_mode(context) == 'EDGE'
        return LoopsFactory.get_loops_by_sel_mode(context, bm, uv_layer, only_uv_edges=is_edge_sel_mode)

    @classmethod
    def restore_selection_in_object(cls, context, s_obj: UniSelectedObject):
        if is_loop_domain(context):
            cls.restore_loops_selection(context, s_obj)
        else:
            cls.restore_items_selection(context, s_obj)

    @classmethod
    def restore_selection_in_objects(cls, context: bpy.types.Context, s_objs: list):
        """
            objs: list of UniSelectedObject instances
        """
        from ..utils.generic import bpy_select_by_context
        bpy_select_by_context(context, action='DESELECT')
        for s_obj in s_objs:
            cls.restore_selection_in_object(context, s_obj)

    @classmethod
    def restore_items_selection(cls, context: bpy.types.Context, s_obj: UniSelectedObject):
        if s_obj.selected_items.is_storage_in_indices:
            p_obj = bpy.data.objects.get(s_obj.obj_name)
            if p_obj:
                bm = bmesh.from_edit_mesh(p_obj.data)
                si = s_obj.selected_items

                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                for i in si.selected_verts:
                    bm.verts[i].select = True
                for i in si.selected_edges:
                    bm.edges[i].select = True
                for i in si.selected_faces:
                    bm.faces[i].select = True
                bm.select_flush_mode()

                MeshIslandUtils.update_uv_select_sync(context, bm)

        else:
            si = s_obj.selected_items
            bm = s_obj.bm

            for elem in (si.selected_verts, si.selected_edges, si.selected_faces):
                for item in elem:
                    item.select_set(True)

            bm.select_flush_mode()

            MeshIslandUtils.update_uv_select_sync(context, bm)

    @classmethod
    def restore_loops_selection(cls, context, s_obj: UniSelectedObject):
        s_loops = set(s_obj.selected_items.selected_loops)
        if s_obj.selected_items.is_storage_in_indices:
            for obj, bm, uv_layer in IterUtils.iter_objs_with_bmesh_uv([bpy.data.objects.get(s_obj.obj_name)], context, skip_obj_if_no_uv=True):
                p_loops = [lp for f in bm.faces for lp in f.loops if lp.index in s_loops]
                LoopsFactory.select_loops(context, bm, p_loops, uv_layer, state=True)

        else:  # Restore from Loops list
            LoopsFactory.select_loops(context, s_obj.bm, s_loops, s_obj.uv_layer, state=True)

    @classmethod
    def yield_selected_objects(cls, context, storage: list, yield_no_uv_layer: bool = False):
        s_obj: UniSelectedObject = None
        for s_obj in storage:
            obj = bpy.data.objects.get(s_obj.obj_name, None)
            if not obj:
                continue
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active

            if not uv_layer and not yield_no_uv_layer:
                continue

            if ZenPolls.version_since_5_0_0 and uv_layer and not bm.uv_select_sync_valid and context.scene.tool_settings.use_uv_select_sync:
                bm.uv_select_sync_from_mesh()

            s_obj.obj = obj
            s_obj.bm = bm
            s_obj.uv_layer = uv_layer

            yield s_obj


if __name__ == "__main__":
    pass
