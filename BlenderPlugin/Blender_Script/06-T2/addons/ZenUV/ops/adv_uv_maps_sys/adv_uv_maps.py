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

# <pep8 compliant>

# Copyright 2023, Valeriy Yatsenko, Alex Zhornyak


import bpy
import bmesh

import re
import uuid
import itertools
from functools import cmp_to_key

from bpy.types import Operator, Panel
from ZenUV.ui.labels import ZuvLabels
from ZenUV.utils.get_uv_islands import get_uv_bound_edges_indexes
from ZenUV.utils.hops_integration import show_uv_in_3dview
from ZenUV.utils.generic import (
    ZenKeyEventSolver,
    resort_by_type_mesh_in_edit_mode_and_sel,
    verify_uv_layer
)
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.prop.common import get_combo_panel_order
from ZenUV.utils.constants import ADV_UV_MAP_NAME_PATTERN
from ZenUV.ico import icon_get
from collections import defaultdict
from ZenUV.prop.wm_props import TimeDataUVMap, ZuvUVMeshGroup
from ZenUV.prop.adv_maps_props import ZUV_AdvMapsProps, ZUV_AdvMapsSceneProps
from ZenUV.utils.blender_zen_utils import ZenPolls, ZenStrUtils
from ZenUV.zen_checker.check_utils import draw_checker_display_items, DisplayItem
from ZenUV.utils.adv_generic_ui_list import zenuv_draw_ui_list
from ZenUV.utils.generic import find_new_name, ZUV_PANEL_CATEGORY


class ZUV_OT_AddUVMaps(bpy.types.Operator):

    bl_description = ZuvLabels.OT_ADD_UV_MAPS_DESC
    bl_idname = "mesh.zuv_add_uvs"
    bl_label = "Add UV Map"
    bl_description = "Duplicate active UV map"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name='Unwrap Mode',
        items=[
            ('DEFAULT', 'Default', 'Active UV map is duplicated'),
            ('SMART', 'Smart', ''),
            ('CUBE', 'Cube', ''),
            ('CYLINDER', 'Cylinder', ''),
            ('SPHERE', 'Sphere', ''),
        ],
        default='DEFAULT'
    )

    def unwrap_active_uv_texture(self, obj: bpy.types.Object):
        bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.select_all(action='SELECT')

        if self.mode == 'SMART':
            bpy.ops.uv.smart_project(correct_aspect=True)
        elif self.mode == 'CUBE':
            bpy.ops.uv.cube_project(correct_aspect=True)
        elif self.mode == 'CYLINDER':
            bpy.ops.uv.cylinder_project(correct_aspect=True)
        elif self.mode == 'SPHERE':
            bpy.ops.uv.sphere_project(correct_aspect=True)

        bpy.ops.object.mode_set(mode='OBJECT')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        update_advanced_uv_maps(context)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            wm = context.window_manager

            s_name = wm.zen_uv.obj_uvs.active_uv_name
            if not s_name:
                s_name = 'UVMap'

            p_names = set()
            for p_uvmap in wm.zen_uv.obj_uvs.uvmaps:
                p_names.add(p_uvmap.name)
                p_uvmap.select = False

            def new_val(stem, nbr):
                # simply for formatting
                return '{st}.{nbr:03d}'.format(st=stem, nbr=nbr)

            match = re.match(r'^(.*)\.(\d{3,})$', s_name)
            if match is None:
                stem, nbr = s_name, 1
            else:
                stem, nbr = match.groups()
                try:
                    nbr = int(nbr)
                except Exception:
                    nbr = 1

            if s_name in p_names:
                # check for each value if in collection
                new_name = new_val(stem, nbr)
                while new_name in p_names:
                    nbr += 1
                    new_name = new_val(stem, nbr)
            else:
                new_name = s_name

            p_act_me = (
                context.active_object.data
                if context.active_object and context.active_object.type == 'MESH'
                else None)

            if p_act_me:
                p_scene_options: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps

                p_objects = []

                p_me_group: ZuvUVMeshGroup
                for p_me_group in wm.zen_uv.obj_uvs.selected_meshes:
                    p_me = p_me_group.get_mesh(context)
                    if not p_scene_options.sync_adv_maps and p_act_me != p_me:
                        continue

                    p_uv_layer = p_me.uv_layers.get(s_name, None)
                    if p_uv_layer:
                        if p_me.uv_layers.active != p_uv_layer:
                            p_me.uv_layers.active = p_uv_layer

                    p_obj = p_me_group.get_obj(context)

                    if len(p_me.uv_layers) < 8:
                        p_new_layer = p_me.uv_layers.new(name=new_name)
                        p_new_layer.active = True
                        p_objects.append(p_obj)
                    else:
                        self.report({'WARNING'}, f"Cannot add more than 8 UV maps to {p_obj.name} !")

                if self.mode != 'DEFAULT' and len(p_objects) > 0:
                    was_mode = context.mode
                    if was_mode == 'EDIT_MESH':
                        was_mode = 'EDIT'

                    if was_mode not in {'EDIT', 'OBJECT'}:
                        raise RuntimeError(f'Mode:{was_mode} not in EDIT, OBJECT!')

                    active_ob = context.active_object
                    was_selected_objs = set(context.selected_objects)

                    if was_mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode='OBJECT')

                    bpy.ops.object.select_all(action='DESELECT')

                    for p_obj in p_objects:
                        context.view_layer.objects.active = p_obj
                        self.unwrap_active_uv_texture(p_obj)

                    context.view_layer.objects.active = active_ob

                    for p_obj in was_selected_objs:
                        p_obj.select_set(True)

                    if was_mode != context.mode:
                        bpy.ops.object.mode_set(mode=was_mode)

                return {'FINISHED'}
            else:
                raise RuntimeError('No selected UV Maps!')

        except Exception as e:
            self.report({'WARNING'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_RemoveUVMaps(bpy.types.Operator):
    bl_idname = "mesh.zuv_remove_uvs"
    bl_label = "Remove UV Maps"
    bl_description = "Remove selected and active UV maps"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        update_advanced_uv_maps(context)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            wm = context.window_manager

            b_was_removed = False

            s_active_uv_name = wm.zen_uv.obj_uvs.active_uv_name

            p_scene_options: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps

            p_act_obj = context.active_object
            p_me = p_act_obj.data if p_act_obj and p_act_obj.type == 'MESH' else None

            for p_uvmap in reversed(wm.zen_uv.obj_uvs.uvmaps):
                if p_uvmap.name == s_active_uv_name or p_uvmap.select:
                    me_group: ZuvUVMeshGroup
                    for me_group in reversed(p_uvmap.mesh_groups):
                        it_me = me_group.get_mesh(context)
                        if not p_scene_options.sync_adv_maps and p_me != it_me:
                            continue
                        p_uvs = it_me.uv_layers
                        p_uv_layer = p_uvs.get(p_uvmap.name, None)
                        if p_uv_layer:
                            p_uvs.remove(p_uv_layer)
                            b_was_removed = True
                            it_me.update()

            if not b_was_removed:
                raise RuntimeError('No selected UV maps!')
            else:
                for win in context.window_manager.windows:
                    for area in win.screen.areas:
                        area.tag_redraw()

            return {'FINISHED'}

        except Exception as e:
            self.report({'WARNING'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_ShowUVMap(Operator):

    bl_description = ZuvLabels.OT_SHOW_UV_MAP_DESC
    bl_idname = "mesh.zuv_show_uvs"
    bl_label = ZuvLabels.OT_SHOW_UV_MAP_LABEL
    bl_options = {'INTERNAL'}

    desc: bpy.props.StringProperty(
        name="Description",
        default=ZuvLabels.OT_SHOW_UV_MAP_DESC,
        options={'HIDDEN'}
    )

    @classmethod
    def description(cls, context, properties):
        addon_prefs = get_prefs()
        zk_mod = addon_prefs.bl_rna.properties['zen_key_modifier'].enum_items
        zk_mod = zk_mod.get(addon_prefs.zen_key_modifier)
        cls.desc = ZuvLabels.OT_SHOW_UV_MAP_DESC.replace("*", zk_mod.name)
        return cls.desc

    def execute(self, context):
        show_uv_in_3dview(context, use_selected_meshes=True, use_selected_faces=False, use_tagged_faces=False)
        return {'FINISHED'}


class ZUV_OT_RenameUVMaps(Operator):

    bl_description = ZuvLabels.OT_RENAME_UV_MAPS_DESC
    bl_idname = "mesh.zuv_rename_uvs"
    bl_label = ZuvLabels.OT_RENAME_UV_MAPS_LABEL
    bl_options = {'REGISTER', 'UNDO'}

    name_pattern: bpy.props.StringProperty(name="Name", default=ADV_UV_MAP_NAME_PATTERN)

    use_numbering: bpy.props.BoolProperty(
        name='Use Numbering',
        default=True,
        description='Use numbering along renaming',
        )

    use_default_name: bpy.props.BoolProperty(
        name='Use Default Name (UVMap)',
        default=False,
        description='Use native name (UVMap)',
        )

    active_only: bpy.props.BoolProperty(
        name='Active Only',
        default=False,
        description='Rename Active UV Maps only',
        )

    desc: bpy.props.StringProperty(
        name="Description",
        default=ZuvLabels.OT_RENAME_UV_MAPS_DESC,
        options={'HIDDEN'}
    )
    is_modifier_right: bpy.props.BoolProperty(name='Is Zen Modifier key', default=False, options={'HIDDEN'})

    @classmethod
    def description(cls, context, properties):
        addon_prefs = get_prefs()
        zk_mod = addon_prefs.bl_rna.properties['zen_key_modifier'].enum_items
        zk_mod = zk_mod.get(addon_prefs.zen_key_modifier)
        cls.desc = ZuvLabels.OT_RENAME_UV_MAPS_DESC.replace("*", zk_mod.name)
        return cls.desc

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = not self.use_default_name
        row.prop(self, "name_pattern")
        layout.prop(self, "use_default_name")
        layout.prop(self, "use_numbering")
        layout.prop(self, "active_only")

    def invoke(self, context, event):
        wm = context.window_manager
        self.is_modifier_right = ZenKeyEventSolver(context, event, get_prefs()).solve()
        return wm.invoke_props_dialog(self)
        # return {'FINISHED'}

    def execute(self, context):
        # if event.alt:
        if self.is_modifier_right:
            # for ob in context.selected_objects:
            for ob in resort_by_type_mesh_in_edit_mode_and_sel(context):
                self.rename_uvs(ob)
        else:
            self.rename_uvs(context.active_object)
        return {'FINISHED'}

    def rename_uvs(self, ob):
        uv_layers = ob.data.uv_layers if not self.active_only else [layer for layer in ob.data.uv_layers if layer.active]
        name = 'UVMap' if self.use_default_name else self.name_pattern

        for i in range(0, len(uv_layers)):
            if self.use_numbering:
                uv_layers[i].name = name + str(i + 1)
            else:
                uv_layers[i].name = name


class ZuvUVMapsReOrder:

    @classmethod
    def poll(cls, context: bpy.types.Context):
        uvs = cls.get_uvs(context)
        return uvs and len(uvs) > 1

    @classmethod
    def get_uvs(cls, context: bpy.types.Context) -> bpy.types.UVLoopLayers:
        p_obj = context.active_object
        if p_obj and p_obj.data and p_obj.type == 'MESH':
            return p_obj.data.uv_layers
        return None

    @classmethod
    def get_active_object_uv(cls, context: bpy.types.Context):
        p_uvs = cls.get_uvs(context)
        if p_uvs:
            return p_uvs.active
        return None

    @classmethod
    def get_active_render_uv(cls, context: bpy.types.Context):
        p_uvs = cls.get_uvs(context)
        if p_uvs:
            for uv in p_uvs:
                if uv.active_render:
                    return uv
        return None

    @classmethod
    def make_active(cls, name: str, p_obj: bpy.types.Object):
        uvs = p_obj.data.uv_layers  # type: bpy.types.UVLoopLayers
        i_act_idx = uvs.find(name)
        if i_act_idx == -1:
            raise Exception(f'Can not find UV:[{name}]')

        uvs.active_index = i_act_idx

    @classmethod
    def move_to_bottom(cls, index, p_obj: bpy.types.Object, context: bpy.types.Context):
        uvs = p_obj.data.uv_layers  # type: bpy.types.UVLoopLayers
        uvs.active_index = index
        new_name = uvs.active.name if uvs.active else ''

        ctx_override = context.copy()
        ctx_override['active_object'] = p_obj
        ctx_override['object'] = p_obj
        ctx_override['mesh'] = p_obj.data

        if ZenPolls.version_since_3_2_0:
            with bpy.context.temp_override(**ctx_override):
                bpy.ops.mesh.uv_texture_add()
        else:
            bpy.ops.mesh.uv_texture_add(ctx_override)

        # delete the "old" one
        cls.make_active(new_name, p_obj)

        if ZenPolls.version_since_3_2_0:
            with bpy.context.temp_override(**ctx_override):
                bpy.ops.mesh.uv_texture_remove()
        else:
            bpy.ops.mesh.uv_texture_remove(ctx_override)

        # set the name of the last one
        uvs.active_index = len(uvs) - 1
        uvs.active.name = new_name

    @classmethod
    def move_down(cls, p_obj: bpy.types.Object, context: bpy.types.Context):
        uvs = p_obj.data.uv_layers  # type: bpy.types.UVLoopLayers

        # get the selected UV map
        orig_ind = uvs.active_index
        orig_name = uvs.active.name if uvs.active else ''

        if orig_ind < len(uvs) - 1:

            # use "trick" on the one after it
            cls.move_to_bottom(orig_ind + 1, p_obj, context)

            # use the "trick" on the UV map
            cls.move_to_bottom(orig_ind, p_obj, context)

            # use the "trick" on the rest that are after where it was
            for i in range(orig_ind, len(uvs) - 2):
                cls.move_to_bottom(orig_ind, p_obj, context)

            cls.make_active(orig_name, p_obj)

    @classmethod
    def move_up(cls, p_obj: bpy.types.Object, context: bpy.types.Context):
        uvs = p_obj.data.uv_layers  # type: bpy.types.UVLoopLayers

        if uvs.active_index > 0:
            original = uvs.active.name if uvs.active else ''
            uvs.active_index -= 1

            cls.move_down(p_obj, context)

            cls.make_active(original, p_obj)


class ZUV_MoveUVMapDown(Operator, ZuvUVMapsReOrder):
    bl_idname = "mesh.zuv_move_uvmap_down"
    bl_label = "Move Down"
    bl_description = 'Moves the active UV Map item down one position'
    bl_options = {"REGISTER", "UNDO"}

    sync: bpy.props.BoolProperty(
        name='Sync',
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene_options: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps
        self.sync = p_scene_options.sync_adv_maps

        return self.execute(context)

    def execute(self, context):
        try:
            if self.sync:
                wm = context.window_manager
                p_obj_uvs = wm.zen_uv.obj_uvs
                p_uv_map: ZuvUVMeshGroup
                for p_uv_map in p_obj_uvs.selected_meshes:
                    self.move_down(p_uv_map.get_obj(context), context)
            else:
                p_obj = context.active_object
                if p_obj and p_obj.type == 'MESH':
                    self.move_down(p_obj, context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_MoveUVMapUp(Operator, ZuvUVMapsReOrder):
    bl_idname = "mesh.zuv_move_uvmap_up"
    bl_label = "Move Up"
    bl_description = 'Moves the active UV Map item up one position'
    bl_options = {"REGISTER", "UNDO"}

    sync: bpy.props.BoolProperty(
        name='Sync',
        default=False,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene_options: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps
        self.sync = p_scene_options.sync_adv_maps

        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            if self.sync:
                wm = context.window_manager
                p_obj_uvs = wm.zen_uv.obj_uvs
                p_uv_map: ZuvUVMeshGroup
                for p_uv_map in p_obj_uvs.selected_meshes:
                    self.move_up(p_uv_map.get_obj(context), context)
            else:
                p_obj = context.active_object
                if p_obj and p_obj.type == 'MESH':
                    self.move_up(p_obj, context)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_UVMapSetIndex(bpy.types.Operator):
    bl_idname = "wm.zuv_advmaps_set_index"
    bl_label = "Set Adv Maps Index"
    bl_description = "Sets index of advanced UV maps and optionally synchronize seams"
    bl_options = {"REGISTER"}

    idx: bpy.props.IntProperty(
        name='Index',
        description="Index of UV map in Advanced UV Maps list",
        default=-1
    )

    sync: bpy.props.BoolProperty(
        name='Multi UV Maps Mode',
        description="Set active UV map for display, editing and rendering to all selected or active object",
        default=True,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    ui: bpy.props.BoolProperty(
        name="Used in UI",
        description="Special flag that must be unset if operator is used for keymap",
        default=False
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        p_scene_options: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps
        t_target = {
            1: "all selected objects",
            -1: "active object"
        }

        idx = 1 if p_scene_options.sync_adv_maps else -1

        b_is_ui = False
        if properties:
            b_is_ui = properties.ui
        if b_is_ui:
            s_desc = (
                'Set active UV map for display and editing in ' + t_target[idx] + '\n' +
                'Shift: Multirange UV maps selection\n' +
                'Ctrl: Extend-subtract UV map in selection\n' +
                'Shift+Ctrl: Toggle selection'
            )
        else:
            s_desc = 'Set active UV map for display and editing in ' + t_target[idx]

        return s_desc

    def execute(self, context: bpy.types.Context):
        try:
            wm = context.window_manager

            if self.ui:
                if self.sync:
                    wm.zen_uv.obj_uvs.selected_index = self.idx
                else:
                    wm.zen_uv.obj_uvs.selected_index_active = self.idx
            else:
                update_advanced_uv_maps(context)
                if self.sync:
                    wm.zen_uv.obj_uvs.selected_index_for_keymap = self.idx
                else:
                    wm.zen_uv.obj_uvs.selected_index_for_keymap_active = self.idx

            p_act_obj = context.active_object

            if context.scene.zen_uv.adv_maps.sync_seams and self.idx in range(len(wm.zen_uv.obj_uvs.uvmaps)):
                p_uvmap = wm.zen_uv.obj_uvs.uvmaps[self.idx]
                me_group: ZuvUVMeshGroup

                for me_group in p_uvmap.mesh_groups:
                    it_me = me_group.get_mesh(context)

                    if not self.sync:
                        if it_me != p_act_obj.data:
                            continue

                    if it_me.is_editmode:
                        bm = bmesh.from_edit_mesh(it_me)
                        bm.edges.ensure_lookup_table()

                        uv_layer = verify_uv_layer(bm)
                        p_seam_edges = set(get_uv_bound_edges_indexes(bm.faces, uv_layer))
                        for edge in bm.edges:
                            edge.seam = edge.index in p_seam_edges
                        bmesh.update_edit_mesh(it_me, loop_triangles=False, destructive=False)
                    else:
                        bm = bmesh.new(use_operators=False)
                        bm.from_mesh(it_me)
                        bm.edges.ensure_lookup_table()
                        uv_layer = verify_uv_layer(bm)
                        p_seam_edges = set(get_uv_bound_edges_indexes(bm.faces, uv_layer))
                        for edge in bm.edges:
                            edge.seam = edge.index in p_seam_edges
                        bm.to_mesh(it_me)
                        bm.free()
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class ZUV_OT_ObjectSwapSourceTarget(bpy.types.Operator):
    bl_idname = "wm.zuv_object_swap_active"
    bl_label = "Swap Source and Target Objects"
    bl_description = 'Make active object and first selected mesh object'
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context):
        wm = context.window_manager
        p_act_obj = context.active_object
        if p_act_obj and p_act_obj.type == 'MESH':
            p_me_group: ZuvUVMeshGroup
            for p_me_group in wm.zen_uv.obj_uvs.selected_meshes:
                p_obj = p_me_group.get_obj(context)
                if p_obj and p_obj != p_act_obj:
                    context.view_layer.objects.active = p_obj
                    return {'FINISHED'}
        return {'CANCELLED'}


class ZUV_UVMapSync(bpy.types.Operator):
    bl_idname = "wm.zuv_advmaps_sync"
    bl_label = "Sync Create"
    bl_description = 'Check that selected UV maps are present and active in all selected objects'
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name='UV Creation Mode',
        description='Create UVs mode in all, selected or active UVs',
        items=[
            ('ALL', 'All', 'All UVs'),
            ('SELECTED', 'Selected', 'Selected UVs'),
            ('ACTIVE', 'Active', 'Active UV'),
        ],
        default='ALL'
    )

    sync_missing_uv: bpy.props.BoolProperty(
        name='Sync Missing UV',
        description='Create UV maps if they are missing in the selected objects',
        default=True
    )

    sync_mode: bpy.props.EnumProperty(
        name='UV Sync Mode',
        description='Sychronize UV by name or postion index in UV list',
        items=[
            ('NAME', 'By Name', 'Match UV maps to affect by name'),
            ('INDEX', 'By Order', 'Match UV maps to affect by order (indices)'),
        ],
        default='NAME'
    )

    sync_active: bpy.props.BoolProperty(
        name='Sync Active',
        default=True
    )

    sync_position: bpy.props.BoolProperty(
        name='Sync Position',
        default=True
    )

    sync_render: bpy.props.BoolProperty(
        name='Sync Render',
        default=True
    )

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True

        box = layout.box()
        box.active = self.sync_missing_uv
        box.prop(self, 'sync_missing_uv')
        box.prop(self, 'sync_mode')
        if self.sync_mode == 'NAME':
            box.prop(self, 'mode')

        layout.prop(self, 'sync_active')
        layout.prop(self, 'sync_position')
        layout.prop(self, 'sync_render')

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        try:
            wm = context.window_manager

            p_obj_uvs = wm.zen_uv.obj_uvs

            t_meshes = [p_me_group.get_mesh(context) for p_me_group in p_obj_uvs.selected_meshes]
            t_active_maps = {it_me: it_me.uv_layers.active for it_me in t_meshes if it_me is not None}

            p_act_obj = context.active_object
            p_act_me = None
            if p_act_obj and p_act_obj.type == 'MESH':
                p_act_me: bpy.types.Mesh = p_act_obj.data

            if self.sync_missing_uv:
                if self.sync_mode == 'NAME':

                    p_active_uv = ZuvUVMapsReOrder.get_active_object_uv(context)
                    s_active_name = p_active_uv.name if p_active_uv else ''

                    for p_uv_map in p_obj_uvs.uvmaps:
                        if self.mode == 'SELECTED':
                            if not p_uv_map.select:
                                continue
                        elif self.mode == 'ACTIVE':
                            if not p_uv_map.name == s_active_name:
                                continue

                        for p_me_group in p_obj_uvs.selected_meshes:
                            me = p_me_group.get_mesh(context)
                            if me:
                                idx = me.uv_layers.find(p_uv_map.name)
                                if idx == -1:
                                    me.uv_layers.new(name=p_uv_map.name)
                else:
                    i_max_count = 0
                    for p_me_group in p_obj_uvs.selected_meshes:
                        me = p_me_group.get_mesh(context)
                        if me:
                            n_uv_count = len(me.uv_layers)
                            if n_uv_count > i_max_count:
                                i_max_count = n_uv_count
                            for p_uv in me.uv_layers:
                                p_uv.name = str(uuid.uuid4())

                    for p_me_group in p_obj_uvs.selected_meshes:
                        me = p_me_group.get_mesh(context)
                        if me:
                            for idx in range(len(me.uv_layers), i_max_count):
                                me.uv_layers.new(name=str(uuid.uuid4()))
                            for idx, p_uv in enumerate(me.uv_layers):
                                p_uv.name = 'UVMap' if idx == 0 else f'UVMap.{idx:03d}'

            if p_act_me:
                p_uv_list = {p_uv.name: idx for idx, p_uv in enumerate(p_act_me.uv_layers)}

                if self.sync_position:

                    def compare(item1, item2):
                        n_count = len(p_uv_list)
                        idx1 = p_uv_list.get(item1, n_count)
                        idx2 = p_uv_list.get(item2, n_count)
                        if idx1 < idx2:
                            return -1
                        elif idx1 > idx2:
                            return 1
                        else:
                            return 0

                    p_me_group: ZuvUVMeshGroup
                    for p_me_group in p_obj_uvs.selected_meshes:
                        p_me = p_me_group.get_mesh(context)
                        if p_me and p_me != p_act_me:
                            p_list = [p_uv.name for p_uv in p_me.uv_layers]
                            p_list.sort(key=cmp_to_key(compare))

                            for idx, p_name in enumerate(p_list):
                                i_cur_idx = p_me.uv_layers.find(p_name)
                                i_distance = i_cur_idx - idx
                                for _ in range(i_distance):
                                    p_uv_layer = p_me.uv_layers.get(p_name, None)
                                    if p_uv_layer:
                                        p_me.uv_layers.active = p_uv_layer
                                        ZuvUVMapsReOrder.move_up(p_me_group.get_obj(context), context)
                                    else:
                                        return RuntimeError('Must not come to this position in UV:' + p_name)

            # set active as they were
            for k, v in t_active_maps.items():
                k.uv_layers.active = v

            if self.sync_active:
                p_active_uv = ZuvUVMapsReOrder.get_active_object_uv(context)
                s_active_name = p_active_uv.name if p_active_uv else ''
                if s_active_name:
                    for p_me_group in p_obj_uvs.selected_meshes:
                        p_me = p_me_group.get_mesh(context)
                        if p_me:
                            i_cur_idx = p_me.uv_layers.find(s_active_name)
                            if i_cur_idx != -1 and i_cur_idx != p_me.uv_layers.active_index:
                                if p_me.uv_layers.active_index != i_cur_idx:
                                    p_me.uv_layers.active_index = i_cur_idx

            if self.sync_render:
                p_render_uv = ZuvUVMapsReOrder.get_active_render_uv(context)
                s_active_render_name = p_render_uv.name if p_render_uv else ''
                if s_active_render_name:
                    for p_me_group in p_obj_uvs.selected_meshes:
                        p_me = p_me_group.get_mesh(context)
                        if p_me:
                            p_uv_layer = p_me.uv_layers.get(s_active_render_name, None)
                            if p_uv_layer:
                                if not p_uv_layer.active_render:
                                    p_uv_layer.active_render = True

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'CANCELLED'}


class DATA_PT_uv_texture_advanced(Panel):
    bl_label = ZuvLabels.PT_ADV_UV_MAPS_LABEL
    bl_order = get_combo_panel_order('VIEW_3D', 'DATA_PT_uv_texture_advanced')
    bl_category = ZUV_PANEL_CATEGORY
    bl_region_type = "UI"
    bl_context = ""
    bl_space_type = "VIEW_3D"

    zen_icon_value = 'pn_AdvUVMaps'

    @classmethod
    def get_icon(cls):
        return icon_get(cls.zen_icon_value)

    @classmethod
    def do_poll(cls, context: bpy.types.Context):
        p_act_obj = context.active_object
        return p_act_obj is not None and p_act_obj.type == "MESH"

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        return addon_prefs.float_VIEW_3D_panels.enable_pt_adv_uv_map and cls.do_poll(context)

    @classmethod
    def combo_poll(cls, context: bpy.types.Context):
        return cls.do_poll(context)

    @classmethod
    def poll_reason(cls, context: bpy.types.Context) -> str:
        p_act_obj = context.active_object
        if p_act_obj is None:
            return 'No Active Object!'
        if p_act_obj.type != 'MESH':
            return 'No Active Mesh Object'
        return ""

    def draw(self, context):
        layout = self.layout
        draw_adv_uv_maps(context, layout)
        draw_copy_paste(context, layout)


class DATA_PT_UVL_uv_texture_advanced(Panel):
    bl_label = ZuvLabels.PT_ADV_UV_MAPS_LABEL
    bl_order = get_combo_panel_order('UV', 'DATA_PT_UVL_uv_texture_advanced')
    bl_category = ZUV_PANEL_CATEGORY
    bl_region_type = "UI"
    bl_context = ""
    bl_space_type = "IMAGE_EDITOR"

    get_icon = DATA_PT_uv_texture_advanced.get_icon

    @classmethod
    def poll(cls, context):
        addon_prefs = context.preferences.addons[ZuvLabels.ADDON_NAME].preferences
        return addon_prefs.float_UV_panels.enable_pt_adv_uv_map and DATA_PT_uv_texture_advanced.do_poll(context)

    combo_poll = DATA_PT_uv_texture_advanced.combo_poll

    poll_reason = DATA_PT_uv_texture_advanced.poll_reason

    def draw(self, context):
        layout = self.layout
        draw_adv_uv_maps(context, layout)
        draw_copy_paste(context, layout)


class ZUV_UL_AdvMapsList(bpy.types.UIList):

    def filter_items(self, context: bpy.types.Context, data: bpy.types.Collection, propname: str):
        p_uv_maps = getattr(data, propname)

        filters = []

        p_scene_props: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps
        if not p_scene_props.sync_adv_maps:
            p_act_obj = context.active_object
            uv_layers = set()
            if p_act_obj and p_act_obj.type == 'MESH':
                uv_layers = p_act_obj.data.uv_layers
            filters = [
                idx for idx, p_uv_map in enumerate(p_uv_maps)
                if p_uv_map.name not in uv_layers]

        # Default return values.
        flt_flags = [self.bitflag_filter_item] * len(p_uv_maps)

        if self.filter_name:
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name, self.bitflag_filter_item, p_uv_maps,
                reverse=self.use_filter_sort_reverse)

        for idx in filters:
            flt_flags[idx] &= ~self.bitflag_filter_item

        flt_neworder = []
        if self.use_filter_sort_alpha:
            flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(p_uv_maps, 'name')

        return flt_flags, flt_neworder

    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):

        p_last_time_data = bpy.app.driver_namespace.get(TimeDataUVMap.literal_id, TimeDataUVMap())  # type: TimeDataUVMap

        addon_prefs = get_prefs()
        p_options: ZUV_AdvMapsProps = addon_prefs.adv_maps
        p_scene_props: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps

        layout.active = False

        row_main = layout.row(align=True)

        s_icon = 'GROUP_UVS'
        b_active_uv = False
        b_active_render = False

        i_selected_meshes = len(data.selected_meshes)
        i_meshes = len(item.mesh_groups)

        i_act_meshes = 0
        t_act_renders = []
        t_act_indices = []

        p_act_mesh = context.active_object.data if context.active_object else None

        for me_group in item.mesh_groups:
            me = me_group.get_mesh(context)
            if me is None:
                continue
            p_uvs = me.uv_layers
            p_uv_layer = p_uvs.active

            uv_idx = p_uvs.find(item.name)

            b_is_active_object = p_act_mesh == me

            t_act_indices.append(uv_idx)
            if p_uv_layer:
                if p_uv_layer.name == item.name:
                    i_act_meshes += 1
                    if b_is_active_object:
                        s_icon = 'EVENT_A'
                        b_active_uv = True

            if uv_idx != -1:
                t_act_renders.append(p_uvs[uv_idx].active_render)
                if b_is_active_object:
                    layout.active = True
                    if p_uvs[uv_idx].active_render:
                        b_active_render = True

        row = row_main.row(align=True)
        if p_options.detect_uv_map_display_active and b_active_uv:
            row.alert = i_act_meshes != i_selected_meshes
        op = row.operator(
            "wm.zuv_advmaps_set_index",
            text='', icon=s_icon, emboss=b_active_uv, depress=b_active_uv)
        op.idx = index
        op.sync = p_scene_props.sync_adv_maps
        op.ui = True

        row = row_main.row(align=True)
        if p_last_time_data.obj and p_last_time_data.obj == context.active_object and p_last_time_data.idx == index:
            row.prop(item, "name_ex_auto", text="", emboss=True)
        else:
            op = row.operator(
                "wm.zuv_advmaps_set_index",
                text=item.name, emboss=b_active_uv or item.select, depress=item.select)
            op.idx = index
            op.sync = p_scene_props.sync_adv_maps
            op.ui = True

        row_pos = row_main.row(align=True)
        s_position = f'{i_meshes}' if i_selected_meshes == i_meshes else f'{i_meshes}/{i_selected_meshes}'
        if p_options.detect_uv_map_position and i_selected_meshes > 1:
            row_pos.alert = t_act_indices.count(t_act_indices[0]) != i_selected_meshes
        else:
            row_pos.alert = False

        row_pos.ui_units_x = 1.5
        if row_pos.alert:
            op = row_pos.operator(
                "wm.zuv_advmaps_sync",
                text=s_position, emboss=b_active_uv or item.select, depress=item.select)
            op.mode = 'ALL'
            op.sync_missing_uv = True
            op.sync_position = True
        else:
            op = row_pos.operator(
                "wm.zuv_advmaps_set_index",
                text=s_position, emboss=b_active_uv or item.select, depress=item.select)
            op.idx = index
            op.sync = p_scene_props.sync_adv_maps
            op.ui = True

        row = row_main.row(align=True)
        row.alignment = 'RIGHT'
        icon_id = 'RESTRICT_RENDER_OFF' if b_active_render else 'RESTRICT_RENDER_ON'
        if p_options.detect_uv_map_render_active and b_active_render:
            row.alert = t_act_renders.count(t_act_renders[0]) != i_selected_meshes
        row.enabled = layout.active
        row.prop(
            item,
            'active_render_ex' if p_scene_props.sync_adv_maps else 'active_render_ex_active',
            text='', emboss=item.select, icon=icon_id)


def update_advanced_uv_maps(context: bpy.types.Context):
    wm = context.window_manager
    p_uv_list = wm.zen_uv.obj_uvs.uvmaps

    t_were_uvs = {
        uv.name: uv.select for uv in p_uv_list
    }

    t_were_idx_sel = {
        idx: uv.select for idx, uv in enumerate(p_uv_list)
    }

    uvs = defaultdict(set)

    p_selected_meshes = wm.zen_uv.obj_uvs.selected_meshes
    p_selected_meshes.clear()

    s_mesh_name = ''
    s_uv_name = ''
    p_act_obj = context.active_object
    if p_act_obj and p_act_obj.type == 'MESH':
        s_mesh_name = p_act_obj.data.name
        if p_act_obj.data.uv_layers.active:
            s_uv_name = p_act_obj.data.uv_layers.active.name

    addon_prefs = get_prefs()

    b_need_to_change = False
    if wm.zen_uv.obj_uvs.active_mesh_name != s_mesh_name:
        wm.zen_uv.obj_uvs['active_uv_object_name'] = context.active_object.name if context.active_object else ''
        if addon_prefs.adv_maps.eye_dropper_object_enabled:
            wm.zen_uv.obj_uvs['active_uv_object'] = context.active_object
        wm.zen_uv.obj_uvs.active_mesh_name = s_mesh_name
        b_need_to_change = True
    else:
        p_wm_act_obj = wm.zen_uv.obj_uvs.get_active_uv_object(context)
        if p_wm_act_obj is not None and p_wm_act_obj != context.active_object:
            wm.zen_uv.obj_uvs['active_uv_object_name'] = context.active_object.name if context.active_object else ''
            if addon_prefs.adv_maps.eye_dropper_object_enabled:
                wm.zen_uv.obj_uvs['active_uv_object'] = context.active_object

    if wm.zen_uv.obj_uvs.active_uv_name != s_uv_name:
        wm.zen_uv.obj_uvs.active_uv_name = s_uv_name
        b_need_to_change = True

    t_meshes = {
        p_obj.data: p_obj
        for p_obj in itertools.chain.from_iterable(
            [
                [context.active_object],
                context.objects_in_mode_unique_data
                if context.mode == 'EDIT_MESH' else
                context.selected_objects])
        if p_obj.type == 'MESH'}

    for k, v in t_meshes.items():
        p_selected_meshes.add()
        p_selected_meshes[-1].mesh_name = k.name
        p_selected_meshes[-1].obj_name = v.name
        for uv in k.uv_layers:
            uvs[uv.name].add(v)

    if list(uvs.keys()) != list(t_were_uvs.keys()) or len(p_uv_list) != len(t_were_uvs):
        b_need_to_change = True
        p_uv_list.clear()

        idx = 0
        for k, v in uvs.items():
            p_uv_list.add()
            p_uv_list[-1].name = k
            if wm.zen_uv.obj_uvs.lock_selection_by_index:
                p_uv_list[-1]['select'] = t_were_idx_sel.get(idx, False)
            else:
                p_uv_list[-1]['select'] = t_were_uvs.get(k, False)

            idx += 1

    act_idx = -1
    for i, v in enumerate(uvs.values()):
        p_uv_list[i].mesh_groups.clear()

        if b_need_to_change and p_uv_list[i].name == wm.zen_uv.obj_uvs.active_uv_name:
            act_idx = i

        for p_obj in v:
            p_uv_list[i].mesh_groups.add()
            p_uv_list[i].mesh_groups[-1].mesh_name = p_obj.data.name
            p_uv_list[i].mesh_groups[-1].obj_name = p_obj.name

    if wm.zen_uv.obj_uvs.lock_selection_by_index:
        wm.zen_uv.obj_uvs.lock_selection_by_index = False

    if b_need_to_change:
        wm.zen_uv.obj_uvs['selected_index'] = act_idx


def draw_adv_uv_maps(context: bpy.types.Context, layout: bpy.types.UILayout):
    ''' @Draw Pt UV Texture Advanced '''
    wm = context.window_manager

    addon_prefs = get_prefs()

    row = layout.row()

    if context.mode == 'OBJECT':
        b_is_UV = context.space_data.type == 'IMAGE_EDITOR'
        if b_is_UV:
            draw_checker_display_items(row, context, {'UV_OBJECT': DisplayItem({'OBJECT'}, {'UV'}, '', None)})

    row.operator(ZUV_UVMapSync.bl_idname, icon='UV_SYNC_SELECT')
    row.operator(ZUV_OT_AdvMapsBatchRename.bl_idname, icon='SORTALPHA')

    p_scene_props: ZUV_AdvMapsSceneProps = context.scene.zen_uv.adv_maps

    row.prop(p_scene_props, "sync_seams", text="", icon="STICKY_UVS_VERT")
    row.prop(p_scene_props, 'sync_adv_maps', icon='WINDOW', icon_only=True)

    row.popover(panel='ZUV_PT_AdvMapsFilter', text='', icon='FILTER')

    # row = layout.row(align=True)
    # row.alignment = 'CENTER'
    # row.label(text='Multi Object UV Maps')

    update_advanced_uv_maps(context)

    row = layout.row()
    col = row.column()

    col.template_list(
        "ZUV_UL_AdvMapsList", 'name_ex_auto',
        wm.zen_uv.obj_uvs,
        "uvmaps",
        wm.zen_uv.obj_uvs,
        'selected_index_auto',
        rows=5
    )

    col = row.column(align=True)

    col.operator(ZUV_OT_AddUVMaps.bl_idname, icon='ADD', text="")
    col.operator(ZUV_OT_RemoveUVMaps.bl_idname, icon='REMOVE', text="")
    if addon_prefs.hops_uv_activate:
        col.operator(ZUV_OT_ShowUVMap.bl_idname, icon='HIDE_OFF', text="")

    col.separator()
    col.menu(menu='ZUV_MT_AdvMapsMenu', text='', icon='DOWNARROW_HLT')

    col.separator()
    col.operator('mesh.zuv_move_uvmap_up', icon='TRIA_UP', text="")
    col.operator('mesh.zuv_move_uvmap_down', icon='TRIA_DOWN', text="")


def draw_copy_paste(context: bpy.types.Context, layout: bpy.types.UILayout):
    ''' @Draw Copy Paste '''
    row = layout.row(align=True)

    row.operator("uv.zenuv_copy_uv", icon="COPYDOWN")
    row.operator("uv.zenuv_paste_uv", icon="PASTEDOWN")


    if context.mode in {'OBJECT'}:
        wm = context.window_manager
        box = layout.box()
        col = box.column(align=False)
        col.use_property_split = True

        row = col.row(align=True)
        s = row.split(factor=1.5/4)
        r1 = s.row(align=True)
        r1.alignment = 'RIGHT'
        r1.label(text='Source:')

        p_act_obj = context.active_object
        p_act_uv_obj = p_act_obj if p_act_obj.type == 'MESH' else None
        p_first_obj = None

        r2 = s.row(align=True)
        addon_prefs = get_prefs()
        if addon_prefs.adv_maps.eye_dropper_object_enabled:
            r2.prop(wm.zen_uv.obj_uvs, 'active_uv_object', text='')
        else:
            r2.prop(context.view_layer.objects, 'active', text='')
        r2.operator(ZUV_OT_ObjectSwapSourceTarget.bl_idname, icon='ARROW_LEFTRIGHT', text='')

        s_target = ''
        n_count = len(wm.zen_uv.obj_uvs.selected_meshes)
        if n_count > 1:
            p_first_obj = context.view_layer.objects.get(wm.zen_uv.obj_uvs.selected_meshes[1].obj_name, None)
            if p_first_obj:
                s_target = p_first_obj.name
                if n_count > 2:
                    s_target += f' and {n_count - 2} object(s)'
        row = col.row(align=True)
        row.active = s_target != ''
        s = row.split(factor=1.5/4)
        r = s.row(align=True)
        r.alignment = 'RIGHT'
        r.label(text='Target:')
        s.label(text=s_target, icon='OBJECT_DATA')

        col = box.column(align=False)
        # col.use_property_split = True

        b_is_enabled = False
        b_same_geometry = False
        if p_act_uv_obj and p_first_obj:
            if len(p_act_uv_obj.data.uv_layers):
                b_is_enabled = True

            b_same_geometry = len(p_act_uv_obj.data.loops) == len(p_first_obj.data.loops)

        col.enabled = b_is_enabled

        p_transfer_mode = context.scene.zen_uv.adv_maps.transfer_mode
        if p_transfer_mode == 'MATCH_GEOMETRY':
            r = col.row(align=True)
            r.enabled = b_same_geometry
            r.operator('object.join_uvs', text='Transfer UV Maps')
        elif p_transfer_mode == 'ADVANCED':
            op = col.operator('object.data_transfer', text='Transfer UV Maps')
            op.data_type = 'UV'
        elif p_transfer_mode == 'LAYOUT':
            op = col.operator('object.datalayout_transfer', text='Transfer UV Maps')
            op.data_type = 'UV'
        else:
            raise RuntimeError('UNREACHABLE CODE!')

        col.prop(context.scene.zen_uv.adv_maps, 'transfer_mode', text='Mode')


class ZUV_OT_AdvMapsBatchRename(bpy.types.Operator):
    bl_idname = 'wm.zuv_adv_maps_rename'
    bl_label = 'Rename'
    bl_description = "If 'what' is empty, text will be completely replaced with 'replace' value"
    bl_options = {'REGISTER'}

    group_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Rename UV maps mode",
        items=[
            ('SELECTED', 'Selected', 'Operates on the currently selected UV Map items in the list'),
            ('ALL', 'All', 'Operates on all UV Map items in the list'),
        ],
        default='SELECTED')
    find: bpy.props.StringProperty(
        name='Find',
        description='The text to search for in names')
    replace: bpy.props.StringProperty(
        name='Replace',
        description='The text to replace for in matching names found from the Find text')
    match_case: bpy.props.BoolProperty(
        name='Match Case',
        description='Search results must exactly match the case of the Find text',
        default=True)
    use_counter: bpy.props.BoolProperty(
        name='Counter',
        description="Integer value will be added to the end of the name",
        default=False)
    start_from: bpy.props.IntProperty(
        name='Start from',
        description='If Counter property is used, integer value will be started from this value',
        default=1)
    use_regex: bpy.props.BoolProperty(
        name='Use Regex',
        description='Replace by regular expression in the "Find" text',
        default=False
    )

    generate_template_names: bpy.props.BoolProperty(
        name='Generate Template Names',
        description='Rename UV maps from replace preset templates',
        default=False
    )

    def get_replace_template_items(self, context):
        addon_prefs = get_prefs()

        p_rename_templates = addon_prefs.adv_maps.rename_templates
        if len(p_rename_templates) == 0:
            t_default = (
              'UVMap',
              'Channel',
              'Lightmap',
              'Diffuse',
              'Bake'
            )

            items = [(p_item, p_item, '') for p_item in t_default]
        else:
            items = [(p_item.name, p_item.name, '') for p_item in p_rename_templates]

        LITERAL_REPLACE_ITEMS = 'zenuv_adv_maps_replace_templates_items'

        t_items = bpy.app.driver_namespace.get(LITERAL_REPLACE_ITEMS, [])
        if t_items != items:
            bpy.app.driver_namespace[LITERAL_REPLACE_ITEMS] = items

        return bpy.app.driver_namespace[LITERAL_REPLACE_ITEMS]

    def on_replace_templates_update(self, context: bpy.types.Context):
        self.replace = self.replace_templates

    replace_templates: bpy.props.EnumProperty(
        name='Replace Templates',
        description="List of template names to rename UV maps",
        items=get_replace_template_items,
        update=on_replace_templates_update
    )

    show_replace_templates_settings: bpy.props.BoolProperty(
        name='Show Replace Templates Settings',
        description="Show list of template names to rename UV maps",
        default=False
    )

    def execute(self, context):
        if self.replace == '' and self.find == '' and not self.generate_template_names:
            self.report({'WARNING'}, 'Nothing was defined to replace!')
            return {'CANCELLED'}

        i_start = self.start_from
        is_modified = False

        try:
            wm = context.window_manager
            p_uv_map = wm.zen_uv.obj_uvs.get_active_uvmap()
            if p_uv_map is None:
                self.report({'WARNING'}, 'No Active UV Map!')
                return {'CANCELLED'}

            addon_prefs = get_prefs()
            p_rename_templates = addon_prefs.adv_maps.rename_templates

            idx = 0

            t_map = {}

            t_new_names = set()

            for it_uvmap in wm.zen_uv.obj_uvs.uvmaps:
                if self.group_mode == 'SELECTED':
                    if not it_uvmap.select and it_uvmap != p_uv_map:
                        continue

                p_old_name = it_uvmap.name
                new_name = p_old_name

                if self.generate_template_names:
                    if idx in range(len(p_rename_templates)):
                        new_name = p_rename_templates[idx].name
                else:
                    new_name, err = ZenStrUtils.smart_replace(p_old_name, self)
                    if err:
                        raise RuntimeError(err)

                if self.use_counter:
                    new_name = new_name + str(i_start)
                    i_start += 1

                if new_name in t_new_names:
                    new_name = find_new_name(new_name, t_new_names)

                t_new_names.add(new_name)

                # NOTE: we must not rename immediately because it will affect the all chain !!!
                if p_old_name != new_name:
                    is_modified = True
                    t_map[it_uvmap] = new_name

                idx += 1

            # NOTE: rename existing items with the same names
            # We use it only if count more than 1 otherwise we use default swapping existing names
            if len(t_map) > 1:
                for it_uvmap in wm.zen_uv.obj_uvs.uvmaps:
                    if it_uvmap not in t_map:
                        if it_uvmap.name in set(t_map.values()):
                            s_all_names = {p_uvmap.name for p_uvmap in wm.zen_uv.obj_uvs.uvmaps}
                            s_new_name = find_new_name(it_uvmap.name, set(t_map.values()).union(s_all_names))
                            it_uvmap.name_ex = s_new_name

                # NOTE: we need to rename to unique names to prevent reordering
                for k, v in t_map.items():
                    s_new_name = str(uuid.uuid4())
                    k.name_ex = s_new_name

            for k, v in t_map.items():
                s_new_name = v
                k.name_ex = s_new_name

        except Exception as e:
            self.report({'ERROR'}, str(e))
            is_modified = True

        if is_modified:
            wm.zen_uv.obj_uvs.lock_selection_by_index = True
            bpy.ops.ed.undo_push(message='Rename UVs')

            return {'FINISHED'}
        else:
            self.report({'WARNING'}, 'No replace matches found!')

        return {'CANCELLED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        layout.prop(self, "group_mode", expand=True)
        row = layout.row(align=True)
        row.enabled = not self.generate_template_names
        row.prop(self, "find")

        row_replace = layout.row(align=True)
        r1 = row_replace.row(align=True)
        r1.enabled = not self.generate_template_names
        r1.prop(self, "replace")
        row_replace.prop_menu_enum(self, 'replace_templates', text='', icon='TRIA_DOWN')
        row_replace.prop(self, 'show_replace_templates_settings', text='', icon='PREFERENCES')

        if self.show_replace_templates_settings:

            zenuv_draw_ui_list(
                layout,
                context,
                class_name="ZUV_UL_AdvMapsReplaceTemplatesList",
                list_path="preferences.addons['ZenUV'].preferences.adv_maps.rename_templates",
                active_index_path="preferences.addons['ZenUV'].preferences.adv_maps.rename_templates_index",
                unique_id="name_ex",
                new_name_attr="name_ex",
                new_name_val="Item"
            )

        layout.prop(self, "match_case")
        layout.prop(self, 'use_regex')
        layout.prop(self, 'generate_template_names')

        row = layout.row()
        row.prop(self, "use_counter")
        row.prop(self, "start_from")

        wm = context.window_manager
        p_uv_map = wm.zen_uv.obj_uvs.get_active_uvmap()
        if p_uv_map:
            box = layout.box()
            box.label(text='Preview')

            err = ''

            p_old_name = p_uv_map.name
            if self.generate_template_names:
                addon_prefs = get_prefs()
                p_rename_templates = addon_prefs.adv_maps.rename_templates
                if p_rename_templates:
                    p_new_name = p_rename_templates[0].name
            else:
                p_new_name, err = ZenStrUtils.smart_replace(p_old_name, self)

            if self.use_counter:
                p_new_name = p_new_name + str(self.start_from)

            col = box.column(align=True)
            col.alert = err != ''
            col.active = p_old_name != p_new_name
            row = col.row(align=True)
            row = row.split(factor=0.2)
            row.label(text='Old:')
            row.label(text=p_old_name)

            row = col.row(align=True)
            row = row.split(factor=0.2)
            row.label(text='New:')
            row.label(text=p_new_name)

            if err:
                row = box.row(align=True)
                row.alert = True
                row.label(text='ERROR: ' + err, icon='ERROR')


class ZUV_PT_AdvMapsFilter(bpy.types.Panel):
    bl_label = "Adv UV Maps Filter"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        addon_prefs = get_prefs()
        p_adv_maps_options = addon_prefs.adv_maps

        layout.label(text='Detect UV Maps Status')

        col = layout.column(align=True)
        for key in p_adv_maps_options.__annotations__.keys():
            if key.startswith('detect_uv_map_'):
                row = col.row(align=True)
                row.prop(p_adv_maps_options, key)


class ZUV_UL_AdvMapsReplaceTemplatesList(bpy.types.UIList):

    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        act_idx = getattr(active_data, active_propname)
        b_active = index == act_idx
        layout.prop(item, 'name_ex', text='', emboss=b_active)


class ZUV_OT_RemoveInactiveUVMaps(bpy.types.Operator):
    bl_idname = "mesh.remove_inactive_uvs"
    bl_description = 'Remove all inactive UV Maps'
    bl_label = 'Clean UV Maps'
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name='Influence',
        items=[
            ('ACTIVE', 'Active Object', 'Remove inactive UV maps in active object'),
            ('SELECTED', 'Selected Objects', 'Remove inactive UV maps in selected objects'),
        ],
        default='SELECTED'
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        p_act_obj = context.active_object
        b_is_modified = False
        for obj in resort_by_type_mesh_in_edit_mode_and_sel(context):
            if self.mode == 'ACTIVE' and obj != p_act_obj:
                continue

            me: bpy.types.Mesh = obj.data
            p_uv_layers = me.uv_layers
            # NOTE: Do not remove by pointers! Only by names
            p_uvs = [p_uv.name for p_uv in p_uv_layers if not p_uv.active]
            for s_uv in p_uvs:
                p_uv = p_uv_layers.get(s_uv, None)
                if p_uv:
                    p_uv_layers.remove(p_uv)
                    b_is_modified = True
            if b_is_modified:
                me.update()

        if not b_is_modified:
            self.report({'WARNING'}, 'Nothing to remove!')
        else:
            for win in context.window_manager.windows:
                for area in win.screen.areas:
                    area.tag_redraw()

        return {'FINISHED'}


class ZUV_OT_AdvMapsSetNameByPos(bpy.types.Operator):
    bl_idname = "mesh.zenuv_set_uv_name_by_pos"
    bl_description = 'Set UV map name by given index in the list of UV maps'
    bl_label = 'Set UV Map Name By Index'
    bl_options = {"REGISTER", "UNDO"}

    mode: bpy.props.EnumProperty(
        name='Influence',
        items=[
            ('ACTIVE', 'Active Object', 'Remove inactive UV maps in active object'),
            ('SELECTED', 'Selected Objects', 'Remove inactive UV maps in selected objects'),
        ],
        default='SELECTED'
    )

    uv_position: bpy.props.IntProperty(
        name='Index',
        description=(
            'UV map index in the list\n'),
        min=1,
        default=1
    )

    uv_name: bpy.props.StringProperty(
        name='UV Map Name',
        default=''
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        b_is_modified = False
        if self.uv_name:
            from ZenUV.prop.wm_props import ZuvUVMapWrapper

            i_pos = self.uv_position - 1

            p_act_obj = context.active_object

            for obj in resort_by_type_mesh_in_edit_mode_and_sel(context):
                if self.mode == 'ACTIVE' and obj != p_act_obj:
                    continue

                me: bpy.types.Mesh = obj.data
                p_uv_layers = me.uv_layers
                for idx, p_uv in enumerate(p_uv_layers):
                    if idx == i_pos:
                        ZuvUVMapWrapper.rename_uv(self.uv_name, p_uv, p_uv_layers)
                        b_is_modified = True
                        me.update()
                        break

        if not b_is_modified:
            self.report({'WARNING'}, f'Can not set name <{self.uv_name}>!')
        else:
            for win in context.window_manager.windows:
                for area in win.screen.areas:
                    area.tag_redraw()

        return {'FINISHED'}


class ZUV_MT_AdvMapsMenu(bpy.types.Menu):
    bl_label = "Advanced Maps Menu"

    def draw(self, context):
        layout = self.layout
        layout.operator('mesh.remove_inactive_uvs')
        layout.separator()
        layout.operator('mesh.zenuv_set_uv_name_by_pos')


adv_uv_texture_classes = (
    ZUV_OT_AddUVMaps,
    ZUV_OT_RemoveUVMaps,
    ZUV_OT_RenameUVMaps,
    ZUV_OT_ShowUVMap,
    ZUV_UVMapSetIndex,
    ZUV_MoveUVMapDown,
    ZUV_MoveUVMapUp,
    ZUV_UVMapSync,
    ZUV_OT_AdvMapsBatchRename,
    ZUV_OT_ObjectSwapSourceTarget,
    ZUV_OT_RemoveInactiveUVMaps,
    ZUV_OT_AdvMapsSetNameByPos,

    ZUV_UL_AdvMapsReplaceTemplatesList,
    ZUV_UL_AdvMapsList,

    ZUV_MT_AdvMapsMenu,

    ZUV_PT_AdvMapsFilter
)


if __name__ == "__main__":
    pass
