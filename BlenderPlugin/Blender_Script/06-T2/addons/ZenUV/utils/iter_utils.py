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

# Copyright 2025, Valeriy Yatsenko - lightbio@gmail.com


import bpy
import bmesh

from collections import defaultdict
from typing import Iterable, Iterator, Tuple, Union, Optional, Any

from ..utils.blender_zen_utils import ZenPolls
from ..utils.generic import verify_uv_layer


class IterUtils:
    """Utility class to iterate over objects and collect soft errors."""
    last_errors: dict[str, dict[str, Any]] = {}

    @staticmethod
    def iter_objs_with_bmesh_uv(
        objs: Iterable[Union[str, bpy.types.Object]],
        context: bpy.types.Context,
        skip_obj_if_no_uv: bool = False,
        errors: Optional[dict[str, dict[str, Any]]] = None,
        is_debug_mode: bool = False
    ) -> Iterator[Tuple[bpy.types.Object, bmesh.types.BMesh, bmesh.types.BMLayerItem]]:

        if errors is None:
            errors = IterUtils.last_errors
        errors.clear()

        def add_error(key: str, msg: str, obj_name: str):
            if key not in errors:
                errors[key] = {'message': msg, 'objects': []}
            errors[key]['objects'].append(obj_name)

        for item in objs:
            obj = bpy.data.objects.get(item) if isinstance(item, str) else item
            if not obj:
                if is_debug_mode:
                    add_error('not_found', 'Object not found:', str(item))
                continue
            if obj.type != 'MESH':
                if is_debug_mode:
                    add_error('not_mesh', 'Object is not a mesh:', obj.name)
                continue

            try:
                bm = bmesh.from_edit_mesh(obj.data)
            except Exception as e:
                if is_debug_mode:
                    add_error('bmesh_failed', f"Cannot access bmesh: {e}", obj.name)
                continue

            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            uv_layer = bm.loops.layers.uv.active
            if ZenPolls.version_since_5_0_0 and uv_layer and not bm.uv_select_sync_valid and context.scene.tool_settings.use_uv_select_sync:
                if is_debug_mode:
                    add_error('uv_not_synced', 'UV selection is not synced to mesh', obj.name)
                bm.uv_select_sync_from_mesh()

            if not uv_layer and skip_obj_if_no_uv:
                add_error('uv_absent', 'No UV map found in', obj.name)
                continue

            yield obj, bm, uv_layer

    @staticmethod
    def show_iteration_errors_popup(context, title="Operator Warnings"):
        """Show popup with grouped iteration errors (IterUtils.last_errors)."""
        errors = IterUtils.last_errors

        if not errors:
            return

        def draw(self_popup, _context):
            layout = self_popup.layout
            for key, entry in errors.items():
                objs = entry.get("objects", [])
                if not objs:
                    continue

                box = layout.box()
                box.label(text=f'{entry["message"]}:', icon='ERROR')

                col = box.column(align=True)
                for obj_name in objs:
                    col.label(text=f"{obj_name}", icon='DOT')

        bpy.context.window_manager.popup_menu(draw, title=title, icon='INFO')


class IterUtils2:
    """Utility class to iterate over objects and collect soft errors."""
    last_errors = defaultdict(list)

    @classmethod
    def iter_objs_with_bmesh(
        cls,
        objs: Iterable[Union[str, bpy.types.Object]],
        errors: defaultdict[str, list] = None,
        is_debug_mode: bool = False
    ) -> Iterator[Tuple[bpy.types.Object, bmesh.types.BMesh]]:

        if errors is None:
            errors = cls.last_errors
        errors.clear()

        for item in objs:
            s_obj_name = item if isinstance(item, str) else 'UNKNOWN'
            obj = bpy.data.objects.get(s_obj_name) if isinstance(item, str) else item
            if not obj:
                if is_debug_mode:
                    errors['Object not found'].append(str(item))
                continue
            if obj.type != 'MESH':
                if is_debug_mode:
                    errors['Object is not a mesh'].append(obj.name)
                continue

            me: bpy.types.Mesh = obj.data
            if not me.is_editmode:
                if is_debug_mode:
                    errors['Mesh is not in edit mode'].append(obj.name)
                continue

            bm = bmesh.from_edit_mesh(me)

            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            yield obj, bm

    @classmethod
    def iter_objs_with_bmesh_uv(
        cls,
        objs: Iterable[Union[str, bpy.types.Object]],
        context: bpy.types.Context,
        errors: defaultdict[str, list] = None,
        create_if_missing: bool = False,
        is_debug_mode: bool = False
    ) -> Iterator[Tuple[bpy.types.Object, bmesh.types.BMesh, bmesh.types.BMLayerItem]]:

        if errors is None:
            errors = cls.last_errors
        errors.clear()

        for obj, bm in cls.iter_objs_with_bmesh(objs, errors=errors, is_debug_mode=is_debug_mode):

            uv_layer = bm.loops.layers.uv.active

            if not uv_layer:
                if create_if_missing:
                    uv_layer = verify_uv_layer(bm)
                else:
                    errors['No UV map found in'].append(obj.name)
                    continue

            if ZenPolls.version_since_5_0_0 and uv_layer and not bm.uv_select_sync_valid and context.scene.tool_settings.use_uv_select_sync:
                if is_debug_mode:
                    errors['UV selection is not synced to mesh'].append(obj.name)
                bm.uv_select_sync_from_mesh()

            yield obj, bm, uv_layer

    @classmethod
    def report_by_operator(cls, op: bpy.types.Operator):
        for msg, objs in cls.last_errors.items():
            for obj_name in objs:
                op.report({'ERROR'}, f"{obj_name} - {msg}")
