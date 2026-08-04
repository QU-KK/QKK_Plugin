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
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Color, Vector

import numpy as np
import uuid
from timeit import default_timer as timer
from dataclasses import dataclass
from collections import defaultdict
from itertools import chain
import functools

from ZenUV.utils.simple_geometry import TextRect
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.inject import is_modal_procedure
from ZenUV.utils.generic import get_unique_mesh_object_map_with_active, has_overlapped_triangles_by_area
from ZenUV.utils.blender_zen_utils import (
    update_areas_in_uv, update_areas_in_view3d,
    prop_with_icon,
    ZenPolls, ZenCompat, ZenDrawConstants)
from ZenUV.utils.vlog import Log
from ZenUV.prop.zuv_preferences import get_prefs
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.stacks.utils import (
    M_STACK_LAYER_NAME,
    STACK_LAYER_NAME,
    StacksSystem,
    write_sim_data_to_layer,
    color_by_layer_sim_index,
    color_by_sim_index,
    enshure_stack_layer)


LITERAL_ZENUV_UPDATE = 'zenuv_update'
LITERAL_ZENUV_GENERAL_UPDATE = 'zenuv_general_update'
LITERAL_ZENUV_DELAYED_UV_GIZMOS = 'zenuv_delayed_uv_gizmos'
LITERAL_ZENUV_DELAYED_3D_GIZMOS = 'zenuv_delayed_3d_gizmos'
LITERAL_ZENUV_TD_SCOPE = 'zenuv_td_scope'

COLOR_FLIPPED = (0, 1, 0, 0.1)

t_3D_GIZMOS = {}
t_UV_GIZMOS = {}


def update_all_gizmos_3D(context: bpy.types.Context, force=False):
    b_need_to_update = False

    p_keys = set(t_3D_GIZMOS.keys())
    for key in p_keys:
        try:
            t_3D_GIZMOS[key].mesh_data = {}
            if force:
                t_3D_GIZMOS[key].mark_build = -1
            b_need_to_update = True
        except Exception as e:
            del t_3D_GIZMOS[key]

    if b_need_to_update:
        update_areas_in_view3d(context)


def update_all_gizmos_UV(context: bpy.types.Context, force=False):
    b_need_to_update = False

    p_keys = set(t_UV_GIZMOS.keys())
    for key in p_keys:
        try:
            t_UV_GIZMOS[key].mesh_data = {}
            if force:
                t_UV_GIZMOS[key].mark_build = -1
            b_need_to_update = True
        except Exception as e:
            del t_UV_GIZMOS[key]

    if b_need_to_update:
        update_areas_in_uv(context)


def get_z_offset(p_obj: bpy.types.Object):
    try:
        object_volume = sum([p_obj.dimensions.x, p_obj.dimensions.y, p_obj.dimensions.z]) / 3
        z_offset = object_volume / 20000 if object_volume < 5 else 0.0001
        return z_offset
    except Exception:
        return 0.0001


if not bpy.app.background:
    if ZenPolls.version_lower_3_5_0:
        shader_tris = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        shader_smooth_tris = gpu.shader.from_builtin('3D_SMOOTH_COLOR')
    else:

        def get_tris_shader():
            vert_out = gpu.types.GPUStageInterfaceInfo("gizmo_tris")
            vert_out.smooth('VEC4', 'finalColor')

            shader_info = gpu.types.GPUShaderCreateInfo()
            shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
            shader_info.push_constant('FLOAT', "z_offset")
            shader_info.push_constant('VEC4', "color")

            shader_info.vertex_in(0, 'VEC3', "pos")
            shader_info.vertex_out(vert_out)
            shader_info.fragment_out(0, 'VEC4', "fragColor")

            shader_info.vertex_source(
                """
                void main()
                {
                    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0f);
                    gl_Position.z -= z_offset;
                    finalColor = color;
                }
                """
            )

            shader_info.fragment_source(
                """
                void main()
                {
                fragColor = finalColor;
                }
                """
            )

            try:
                shader = gpu.shader.create_from_info(shader_info)
            except Exception as e:
                Log.error('GIZMO_SHADER:', str(e))
                shader = gpu.shader.from_builtin(ZenCompat.get_3d_uniform_color())

            del vert_out
            del shader_info

            return shader

        def get_tris_smooth_shader():
            vert_out = gpu.types.GPUStageInterfaceInfo("gizmo_smooth_tris")
            vert_out.smooth('VEC4', 'finalColor')

            shader_info = gpu.types.GPUShaderCreateInfo()
            shader_info.push_constant('MAT4', "ModelViewProjectionMatrix")
            shader_info.push_constant('FLOAT', "z_offset")

            shader_info.vertex_in(0, 'VEC3', "pos")
            shader_info.vertex_in(1, 'VEC4', "color")

            shader_info.vertex_out(vert_out)
            shader_info.fragment_out(0, 'VEC4', "fragColor")

            shader_info.vertex_source(
                """
                void main()
                {
                    gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0f);
                    gl_Position.z -= z_offset;
                    finalColor = color;
                }
                """
            )

            shader_info.fragment_source(
                """
                void main()
                {
                fragColor = finalColor;
                }
                """
            )

            shader = gpu.shader.create_from_info(shader_info)
            del vert_out
            del shader_info

            return shader

        shader_tris = get_tris_shader()
        shader_smooth_tris = get_tris_smooth_shader()

    shader_3D_lines = gpu.shader.from_builtin(ZenCompat.get_3d_polyline_uniform())
    shader_2D_lines = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())

    shader_2D_tris = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())


def zenuv_despgraph_delayed():
    try:
        ctx = bpy.context
        if ctx.mode == 'OBJECT':
            p_scene = ctx.scene
            if (
                    (p_scene.zen_uv.ui.draw_mode_UV == 'UV_OBJECT') or
                    ('DATA_PT_UVL_uv_texture_advanced' in get_prefs().combo_panel.combo_UV_edit_mode)):
                update_areas_in_uv(ctx)
    except Exception as e:
        Log.error('DEPS UPDATE DELAYED:', e)


@bpy.app.handlers.persistent
def zenuv_depsgraph_ui_update(_):
    ctx = bpy.context


    # NOTE: Fixes problem with SimpleBake addon
    if ZenPolls.version_since_3_3_0:
        for s_job in {'RENDER', 'RENDER_PREVIEW', 'OBJECT_BAKE', 'COMPOSITE', 'SHADER_COMPILATION'}:
            if bpy.app.is_job_running(s_job):
                return

    depsgraph = ctx.evaluated_depsgraph_get()

    t_updates = None

    b_update_general = False

    for update in depsgraph.updates:
        if not isinstance(update.id, bpy.types.Mesh):
            continue

        b_geom = update.is_updated_geometry
        b_shade = update.is_updated_shading

        if b_geom or b_shade:
            if t_updates is None:
                t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

            s_uuid = str(uuid.uuid4())

            if not b_update_general:
                bpy.app.driver_namespace[LITERAL_ZENUV_GENERAL_UPDATE] = s_uuid
                b_update_general = True

            p_data = t_updates.get(update.id.original, ['', ''])

            if b_geom:
                p_data[0] = s_uuid
            if b_shade:
                p_data[1] = s_uuid

            t_updates[update.id.original] = p_data

    if t_updates is not None:
        bpy.app.driver_namespace[LITERAL_ZENUV_UPDATE] = t_updates

    if bpy.app.timers.is_registered(zenuv_despgraph_delayed):
        bpy.app.timers.unregister(zenuv_despgraph_delayed)

    bpy.app.timers.register(zenuv_despgraph_delayed, first_interval=0.1)


@dataclass
class DrawCustomShape:
    batch: object = None
    shader: object = None
    obj: bpy.types.Object = None
    color: callable = None
    z_offset: float = 0.0001
    mode: int = 0  # 0 - Default, 1 - Polyline

    def get_shape(self):
        return (self.batch, self.shader)


class GizmoColumnButton:

    @classmethod
    def set_position(cls, p_gizmo: bpy.types.Gizmo, context: bpy.types.Context, gizmo_type: str):
        p_view = context.preferences.view
        ui_scale = context.preferences.system.ui_scale
        widget_size = ((ZenDrawConstants.GIZMO_ICON_SIZE / 2) + 8) * ui_scale

        widget_height = ZenDrawConstants.GIZMO_SIZE * ui_scale

        i_add_y = 0
        if p_view.mini_axis_type == 'MINIMAL':
            i_add_y += p_view.mini_axis_size * 2 * ui_scale
        elif p_view.mini_axis_type == 'GIZMO':
            i_add_y += p_view.gizmo_size_navigate_v3d * ui_scale

        p_offsets = ZuvTrimsheetUtils.get_area_offsets(context.area)

        n_panel_width = p_offsets.get('right')
        base_position = context.region.width - n_panel_width - widget_size
        p_gizmo.matrix_basis[0][3] = base_position

        i_gizmo_col = ZenDrawConstants.GIZMO_COLUMN_INDICES.get(gizmo_type, 0)
        p_gizmo.matrix_basis[1][3] = (
            context.region.height - p_offsets.get('top') - widget_height * i_gizmo_col - i_add_y)


class ZUV_GGT_DetectionUV(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_DetectionUV"
    bl_label = "UV Detection Utils"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene

        return (
            (context.space_data.overlay.show_overlays or not p_scene.zen_uv.ui.use_draw_overlay_sync) and
            (p_scene.zen_uv.ui.draw_mode_3D == 'UV_NO_SYNC' or p_scene.zen_uv.ui.draw_mode_UV == 'SIMILAR_SELECTED')
            and context.mode in {'EDIT_MESH'}
        )

    def setup(self, context: bpy.types.Context):
        pass

    def refresh(self, context: bpy.types.Context):
        if not is_modal_procedure(context):

            p_scene = context.scene

            if p_scene.zen_uv.ui.draw_mode_3D == 'UV_NO_SYNC':
                update_all_gizmos_3D(context)

            if p_scene.zen_uv.ui.draw_mode_UV == 'SIMILAR_SELECTED':
                update_all_gizmos_UV(context)


class ZUV_GGT_DrawUV(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_DrawUV"
    bl_label = "Draw UV"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SCALE',
    } if bpy.app.version < (3, 0, 0) else {
        'PERSISTENT', 'EXCLUDE_MODAL', 'SCALE'
    }
    tool_mode = {'DISPLAY'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        p_space_data = context.space_data
        if context.space_data.overlay.show_overlays or not p_scene.zen_uv.ui.use_draw_overlay_sync:
            # bug in Blender: https://projects.blender.org/blender/blender/issues/110721
            if hasattr(p_space_data, 'show_gizmo') and not p_space_data.show_gizmo:
                return False

            p_uv_draw_mode = p_scene.zen_uv.ui.draw_mode_UV
            s_context_mode = context.mode
            if s_context_mode == 'OBJECT':
                if p_uv_draw_mode in {'UV_OBJECT'}:
                    return True
            elif s_context_mode == 'EDIT_MESH':
                if p_uv_draw_mode not in {'NONE', 'UV_OBJECT'}:
                    return True
        return False

    def draw_prepare(self, context: bpy.types.Context):

        wm = context.window_manager

        self.mpr_update_draw.hide = wm.zen_uv.draw_props.draw_auto_update
        if not self.mpr_update_draw.hide:
            GizmoColumnButton.set_position(self.mpr_update_draw, context, 'UPDATE_DRAW')

    def create_update_draw_button(self, context: bpy.types.Context):
        self.mpr_update_draw = self.gizmos.new("GIZMO_GT_button_2d")
        self.mpr_update_draw.show_drag = False
        self.mpr_update_draw.icon = 'FILE_REFRESH'
        self.mpr_update_draw.draw_options = {'BACKDROP', 'OUTLINE'}

        self.mpr_update_draw.color = 0.0, 0.0, 0.0
        self.mpr_update_draw.alpha = 0.4
        self.mpr_update_draw.color_highlight = 0.8, 0.8, 0.8
        self.mpr_update_draw.alpha_highlight = 0.2
        self.mpr_update_draw.scale_basis = ZenDrawConstants.GIZMO_ICON_SIZE / 2

        _ = self.mpr_update_draw.target_set_operator("wm.zuv_draw_update")

    def setup(self, context: bpy.types.Context):
        self.mpr_draw = self.gizmos.new("UV_GT_zenuv_overlay_draw")
        self.mpr_draw.color = Color((0.02, 0.68, 0.53))
        self.mpr_draw.alpha = 0.2
        self.mpr_draw.color_highlight = self.mpr_draw.color
        self.mpr_draw.alpha_highlight = 0.4
        self.mpr_draw.line_width = 1
        self.mpr_draw.use_draw_value = False
        self.mpr_draw.use_draw_scale = False
        self.mpr_draw.use_draw_modal = False
        self.mpr_draw.use_select_background = False
        self.mpr_draw.use_event_handle_all = False
        self.mpr_draw.use_grab_cursor = False
        self.mpr_draw.hide_select = True

        t_UV_GIZMOS[context.area.as_pointer()] = self.mpr_draw

        self.create_update_draw_button(context)

    def refresh(self, context: bpy.types.Context):
        pass


def zenuv_delayed_overlay_build_uv():
    try:
        ctx = bpy.context
        t_delayed_gizmos = bpy.app.driver_namespace.get(LITERAL_ZENUV_DELAYED_UV_GIZMOS, set())
        while t_delayed_gizmos:
            p_gizmo = t_delayed_gizmos.pop()  # type: UV_GT_zenuv_overlay_draw
            try:
                if not p_gizmo.mark_build:
                    p_gizmo.mark_build = 1  # it is ok that Gizmo may not exist at the moment
            except Exception as e:
                Log.error('DELAYED GIZMO BUILD UV: MARK:', str(e))

        bpy.app.driver_namespace[LITERAL_ZENUV_DELAYED_UV_GIZMOS] = set()
        update_areas_in_uv(ctx)
    except Exception as e:
        Log.error('DELAYED GIZMO BUILD UV:', str(e))


def zenuv_delayed_overlay_build_3D():
    try:
        ctx = bpy.context
        t_delayed_gizmos = bpy.app.driver_namespace.get(LITERAL_ZENUV_DELAYED_3D_GIZMOS, set())
        while t_delayed_gizmos:
            p_gizmo = t_delayed_gizmos.pop()  # type: UV_GT_zenuv_overlay_draw
            try:
                if not p_gizmo.mark_build:
                    p_gizmo.mark_build = 1  # it is ok that Gizmo may not exist at the moment
            except Exception as e:
                Log.error('DELAYED GIZMO BUILD 3D: MARK:', str(e))
        bpy.app.driver_namespace[LITERAL_ZENUV_DELAYED_3D_GIZMOS] = set()
        update_areas_in_view3d(ctx)
    except Exception as e:
        Log.error('DELAYED GIZMO BUILD 3D:', str(e))


class GradientProperties:

    r = (1, 0, 0)
    g = (0, 1, 0)
    b = (0, 0, 1)

    white = (1, 1, 1)
    black = (0, 0, 0)

    range_values = [
            0, 50, 100, 150, 200, 250
        ]
    range_colors = [
            r, g, b, white, r, g
        ]
    range_labels = range_values.copy()


class UvSelectionStorage:
    @classmethod
    def store_selection(self, p_unique_mesh_objects, b_is_not_sync):
        was_selection = {}
        for p_obj in p_unique_mesh_objects:
            me: bpy.types.Mesh = p_obj.data
            bm = bmesh.from_edit_mesh(me)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            selected_items = []
            if uv_layer:
                if b_is_not_sync:
                    selected_items = [
                        (loop, loop[uv_layer].select_edge if ZenPolls.version_since_3_2_0 else None)
                        for face in bm.faces for loop in face.loops
                        if not face.hide and loop[uv_layer].select
                    ]
                else:
                    selected_verts = [
                        item
                        for item in bm.verts
                        if not item.hide and item.select
                    ] if me.total_vert_sel else []
                    selected_edges = [
                        item
                        for item in bm.edges
                        if not item.hide and item.select
                    ] if me.total_edge_sel else []
                    selected_faces = [
                        item
                        for item in bm.faces
                        if not item.hide and item.select
                    ] if me.total_face_sel else []
                    selected_items = (selected_verts, selected_edges, selected_faces)
            was_selection[p_obj] = (bm, uv_layer, selected_items)
        return was_selection

    @classmethod
    def restore_selection(self, context: bpy.types.Context, b_is_not_sync, was_selection: dict):
        if b_is_not_sync:
            for v in was_selection.values():
                uv_layer = v[1]
                if uv_layer:
                    for loop, select_edge in v[2]:
                        loop[uv_layer].select = True
                        if ZenPolls.version_since_3_2_0:
                            loop[uv_layer].select_edge = select_edge
                    bm = v[0]
                    bm.select_flush_mode()
        else:
            for v in was_selection.values():
                for elem in v[2]:
                    for item in elem:
                        item.select = True
                bm = v[0]
                bm.select_flush_mode()


class UvOverlap:
    def __init__(self, context: bpy.types.Context) -> None:
        self.context = context

        self.t_meshes = get_unique_mesh_object_map_with_active(context)

        self.uv_sync = context.tool_settings.use_uv_select_sync

        self.was_selection = UvSelectionStorage.store_selection(self.t_meshes.values(), not self.uv_sync)
        if bpy.ops.uv.select_all.poll():
            bpy.ops.uv.select_all(action='DESELECT')
        if bpy.ops.uv.select_overlap.poll():
            bpy.ops.uv.select_overlap(extend=False)

    def restore(self):

        if bpy.ops.uv.select_all.poll():
            bpy.ops.uv.select_all(action='DESELECT')

        UvSelectionStorage.restore_selection(self.context, not self.uv_sync, self.was_selection)


class UV_GT_zenuv_overlay_draw(bpy.types.Gizmo):
    bl_idname = "UV_GT_zenuv_overlay_draw"
    bl_target_properties = ()

    __slots__ = (
        "custom_shapes",
        "mesh_data",
        "uv_sync",
        "last_mode",
        "mark_build",
        "background_shape",
        "custom_data"
    )

    def draw_gradient(self, context: bpy.types.Context):
        interval = timer()

        from ZenUV.utils.generic import map_range
        vertices = (
            (100, 100), (300, 100),
            (100, 200), (300, 200))

        indices = (
            (0, 1, 2),
            (2, 1, 3))

        td_values = GradientProperties.range_values
        td_colors = GradientProperties.range_colors
        td_labels = GradientProperties.range_labels

        n_input_count = len(td_values)
        if n_input_count == 0:
            return

        if len(set([n_input_count, len(td_colors), len(td_labels)])) != 1:
            Log.error(
                f'DRAW GRADIENT: MISMATCH - td_values:{len(td_values)}, td_colors:{len(td_colors)}, td_labels:{len(td_labels)} !!!')
            return

        if n_input_count == 1:
            td_values = [td_values[0], td_values[0]]
            td_colors = [td_colors[0], td_colors[0]]
            td_labels = [td_labels[0], td_labels[0]]

        s_act_obj_td_value = ''

        try:
            if context.area.type == 'IMAGE_EDITOR':
                p_draw_gizmo = None
                # NOTE: In UV context detection of active face is buggy, that's why we disable it
                # p_draw_gizmo = t_UV_GIZMOS.get(context.area.as_pointer(), None)
            else:
                p_draw_gizmo = t_3D_GIZMOS.get(context.area.as_pointer(), None)

            if p_draw_gizmo:
                p_td_map = p_draw_gizmo.custom_data.get("texel_data_map", {})
                p_act_obj = context.active_object
                if p_act_obj and p_act_obj.type == 'MESH':
                    p_data = p_td_map.get(p_act_obj.name, None)
                    if p_data:
                        bm = bmesh.from_edit_mesh(p_act_obj.data)
                        p_act_face = bm.faces.active
                        if p_act_face and p_act_face.select:
                            p_face_td_data = p_data.get(p_act_face.index, None)
                            if p_face_td_data:
                                _, island_td_value = p_face_td_data

                                s_act_obj_td_value = f' / Current TD: {island_td_value:.2f}'
        except Exception as e:
            pass

        addon_prefs = get_prefs()

        indices = []
        vertices = []
        vertex_colors = []

        p_area = context.area

        p_offsets = ZuvTrimsheetUtils.get_area_offsets(p_area)

        n_left_offset = p_offsets.get('left')
        n_right_offset = p_offsets.get('right')

        ui_scale = context.preferences.system.ui_scale
        i_font_size = addon_prefs.draw_label_font_size
        ZenCompat.blf_font_size(i_font_size, ui_scale)

        i_height = addon_prefs.td_draw.height
        d_font_offset_top = i_font_size
        d_font_offset_bottom = i_font_size * 2

        start_x = p_area.width - addon_prefs.td_draw.width - n_right_offset - 20 * ui_scale

        if start_x < n_left_offset:
            start_x = n_left_offset

        end_x = start_x + addon_prefs.td_draw.width

        start_y = 10 * ui_scale + d_font_offset_bottom

        p_td_labels = []
        idx = 0
        for v in td_labels:
            p_td_labels.append([idx if v != '' else 0, v])
            if v != '':
                idx += 1

        i_last_top_x = 0
        i_last_bottom_x = 0

        n_max_values = len(td_values)

        for idx in range(n_max_values):
            val = td_values[idx]
            if idx == 0:
                val = start_x
            elif idx == n_max_values - 1:
                val = end_x
            else:
                val = map_range(val, td_values[0], td_values[-1], start_x, end_x)

            vertices.append(
                (val, start_y)
            )
            vertices.append(
                (val, start_y + i_height)
            )
            vertex_colors.append((*td_colors[idx], 1))
            vertex_colors.append((*td_colors[idx], 1))

            b_is_odd = p_td_labels[idx][0] % 2 == 1

            s_label_name = str(p_td_labels[idx][1])

            pos_x = val
            pos_y = start_y + i_height + d_font_offset_top if not b_is_odd else start_y - d_font_offset_bottom
            t_width, _ = blf.dimensions(0, s_label_name)

            b_enable_draw_label = False

            if not b_is_odd:
                i_new_last_x = pos_x + t_width
                if pos_x > i_last_top_x + 10:
                    i_last_top_x = i_new_last_x
                    b_enable_draw_label = True
            else:
                i_new_last_x = pos_x + t_width
                if pos_x > i_last_bottom_x + 10:
                    i_last_bottom_x = i_new_last_x
                    b_enable_draw_label = True

            if b_enable_draw_label:
                label = TextRect(
                    left=pos_x,
                    bottom=pos_y,
                    name=s_label_name,
                    auto_normalize=False,
                    color=(1, 1, 1, 1)
                )

                label.draw_text()

            if idx != 0:

                n_v_idx = len(vertices) - 4

                indices.extend(
                    [
                        (n_v_idx, n_v_idx + 1, n_v_idx + 2),
                        (n_v_idx + 2, n_v_idx + 1, n_v_idx + 3)])

        s_display_method = bpy.types.UILayout.enum_item_name(
            context.scene.zen_uv.td_draw_props,
            'display_method',
            context.scene.zen_uv.td_draw_props.display_method
        )

        label = TextRect(
            left=start_x,
            bottom=start_y + i_height + d_font_offset_top + i_font_size * ui_scale + 5 * ui_scale,
            name=s_display_method + s_act_obj_td_value,
            auto_normalize=False,
            color=addon_prefs.draw_label_font_color[:]
        )

        label.draw_text()

        gpu.state.blend_set('ALPHA')
        shader = gpu.shader.from_builtin(ZenCompat.get_2d_smooth_color())
        batch = batch_for_shader(
            shader, 'TRIS',
            {"pos": vertices, "color": vertex_colors}, indices=indices
        )
        shader.bind()
        batch.draw(shader)
        gpu.state.blend_set('NONE')


    def draw_label(self, context: bpy.types.Context):
        p_scene = context.scene
        ui_scale = context.preferences.system.ui_scale
        addon_prefs = get_prefs()
        i_font_size = addon_prefs.draw_label_font_size
        ZenCompat.blf_font_size(i_font_size, ui_scale)

        p_offsets = ZuvTrimsheetUtils.get_area_offsets(context.area)
        n_top_offset = p_offsets.get('top')
        n_right_offset = p_offsets.get('right')
        n_left_offset = p_offsets.get('left')
        n_bottom_offset = p_offsets.get('bottom')

        attr_name, p_mode = p_scene.zen_uv.ui.get_draw_mode_pair_by_context(context)

        s_label = bpy.types.UILayout.enum_item_name(
            p_scene.zen_uv.ui, attr_name, p_mode)
        s_label = f'ZenUV: Display {s_label}'

        n_area_width = context.area.width
        n_area_height = context.area.height
        v_sca = Vector((n_area_width - n_left_offset - n_right_offset, n_area_height - n_top_offset - n_bottom_offset, 1.0))
        t_width, t_height = blf.dimensions(0, s_label)

        i_left = round(n_left_offset + v_sca.x / 2 - t_width / 2)
        i_bottom = round(n_bottom_offset + v_sca.y - t_height - 10 * ui_scale)

        label = TextRect(
            left=i_left,
            bottom=i_bottom,
            name=s_label,
            color=addon_prefs.draw_label_font_color[:],
            auto_normalize=False
        )

        # ##### Draw Background Option
        # mtx_background = (
        #     Matrix.Translation(Vector((n_area_width / 2, n_area_height / 2, 0))) @
        #     Matrix.Diagonal(Vector((n_area_width, n_area_height, 1.0))).to_4x4())

        # self.color = (0.0, 0.0, 0.0)
        # self.alpha = 0.8
        # self.draw_custom_shape(self.background_shape, matrix=self.matrix_world @ mtx_background)

        label.draw_text()

    def _delayed_build(self):
        if bpy.app.timers.is_registered(zenuv_delayed_overlay_build_uv):
            bpy.app.timers.unregister(zenuv_delayed_overlay_build_uv)
        t_delayed_gizmos = bpy.app.driver_namespace.get(LITERAL_ZENUV_DELAYED_UV_GIZMOS, set())
        t_delayed_gizmos.add(self)
        bpy.app.driver_namespace[LITERAL_ZENUV_DELAYED_UV_GIZMOS] = t_delayed_gizmos
        bpy.app.timers.register(zenuv_delayed_overlay_build_uv, first_interval=0.05)

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        self.draw_label(context)

        # special case
        s_draw_mode_UV = context.scene.zen_uv.ui.draw_mode_UV
        if s_draw_mode_UV == 'TEXEL_DENSITY':
            if context.scene.zen_uv.ui.draw_sub_TD_UV in {'GRADIENT', 'ALL'}:
                self.draw_gradient(context)

        # when we assigned nothing
        if self.mesh_data is None:
            return

        wm = context.window_manager
        if self.mark_build == -1 or wm.zen_uv.draw_props.draw_auto_update:
            if self.mark_build:
                if not is_modal_procedure(context):
                    self.build(context)
                else:
                    self._delayed_build()
            elif not self.check_valid_data(context):
                if not is_modal_procedure(context):
                    self._delayed_build()
                return

        if not self.custom_shapes:
            return

        viewport_info = gpu.state.viewport_get()

        width = viewport_info[2]
        height = viewport_info[3]

        region = context.region

        uv_to_view = region.view2d.view_to_region

        origin_x, origin_y = uv_to_view(0, 0, clip=False)
        top_x, top_y = uv_to_view(1.0, 1.0, clip=False)
        axis_x = top_x - origin_x
        axis_y = top_y - origin_y

        matrix = Matrix((
            [axis_x / width * 2, 0, 0, 2.0 * -
                ((width - origin_x - 0.5 * width)) / width],
            [0, axis_y / height * 2, 0, 2.0 * -
                ((height - origin_y - 0.5 * height)) / height],
            [0, 0, 1.0, 0],
            [0, 0, 0, 1.0]))

        identiy = Matrix.Identity(4)

        gpu.state.blend_set('ALPHA')

        addon_prefs = get_prefs()
        p_scene = context.scene

        if addon_prefs.UvPointsOnZoom:
            zoom_factor = context.space_data.zoom[:]
            pt_size = 1.0 * zoom_factor[1] * p_scene.zen_uv.ui.uv_points_draw_zoom_ratio

            gpu.state.point_size_set(pt_size)

        if s_draw_mode_UV == 'UV_BORDERS':
            gpu.state.line_width_set(addon_prefs.uv_borders_draw.line_width)

        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(matrix)

            with gpu.matrix.push_pop_projection():
                gpu.matrix.load_projection_matrix(identiy)

                draw_shape: DrawCustomShape
                for draw_shape in self.custom_shapes:
                    batch, shader = draw_shape.get_shape()

                    shader.bind()
                    if draw_shape.color is not None:
                        shader.uniform_float("color", draw_shape.color())
                    batch.draw()

        gpu.state.point_size_set(1)
        gpu.state.line_width_set(1)
        gpu.state.blend_set('NONE')

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def test_select(self, context: bpy.types.Context, location):
        return -1

    def draw_select(self, context: bpy.types.Context, select_id):
        self._do_draw(context, select_id=select_id)

    def setup(self):
        if not hasattr(self, "mesh_data"):
            self.custom_shapes = []
            self.mesh_data = {}
            self.uv_sync = False
            self.last_mode = ''
            self.mark_build = 0
            self.custom_data = {}

            custom_shape_verts = (
                (-0.5, -0.5), (-0.5, 0.5), (0.5, 0.5),
                (0.5, 0.5), (0.5, -0.5), (-0.5, -0.5)
            )

            self.background_shape = self.new_custom_shape('TRIS', custom_shape_verts)

    def exit(self, context, cancel):
        context.area.header_text_set(None)

    @classmethod
    def is_face_flipped(cls, uv_layer, p_face):
        from ZenUV.utils.generic import is_face_flipped
        return is_face_flipped(p_face, uv_layer)

    def check_valid_data(self, context: bpy.types.Context):
        b_is_uv_sync = context.scene.tool_settings.use_uv_select_sync
        if self.uv_sync != b_is_uv_sync:
            return False

        p_scene = context.scene
        if self.last_mode != p_scene.zen_uv.ui.draw_mode_UV:
            return False

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        check_data = {}

        for me in get_unique_mesh_object_map_with_active(context).keys():
            check_data[me] = t_updates.get(me, ['', ''])

        # 1) check shading, geometry
        if not b_is_uv_sync or p_scene.zen_uv.ui.draw_mode_UV == 'SIMILAR_SELECTED':
            return self.mesh_data == check_data

        # 2) check geometry only
        if self.mesh_data.keys() != check_data.keys():
            return False

        for key in self.mesh_data.keys():
            if self.mesh_data[key][0] != check_data[key][0]:
                return False

        return True

    def build(self, context: bpy.types.Context):
        p_scene = context.scene

        self.mark_build = 0

        method_name = 'build_' + p_scene.zen_uv.ui.draw_mode_UV.lower()
        if hasattr(self, method_name):
            p_method = getattr(self, method_name)

            b_is_uv_sync = context.scene.tool_settings.use_uv_select_sync

            self.custom_shapes.clear()
            self.mesh_data = {}
            self.last_mode = p_scene.zen_uv.ui.draw_mode_UV
            self.uv_sync = b_is_uv_sync

            p_method(context)
        else:
            raise RuntimeError(f'UV Build: {method_name} is not defined!')

    def build_self_intersecting(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                loops = bm.calc_loop_triangles()

                triangles = defaultdict(list)

                for looptris in loops:
                    if not looptris[0].face.hide and (self.uv_sync or looptris[0].face.select):
                        triangles[looptris[0].face.index].append([loop[uv_layer].uv.to_tuple(5) for loop in looptris])

                uvs = []

                for k, v in triangles.items():
                    p_face: bmesh.types.BMFace = bm.faces[k]
                    if has_overlapped_triangles_by_area(p_face, v, uv_layer):
                        uvs.extend(chain(chain.from_iterable(v)))

                if uvs:
                    uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                    uv_coords = uv_verts.tolist()
                    uv_indices = uv_indices.astype(np.int32)

                    shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                    batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                    batch.program_set(shader)

                    self.custom_shapes.append(
                        DrawCustomShape(
                            batch, shader, p_obj,
                            lambda: (*addon_prefs.UvOverlappedColor[:3], addon_prefs.UvOverlappedColor[3])))

    def build_finished(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                loops = bm.calc_loop_triangles()

                fmap = bm.faces.layers.int.get("ZenUV_Finished")

                uvs = defaultdict(list)
                for looptris in loops:
                    if not looptris[0].face.hide and (self.uv_sync or looptris[0].face.select):
                        idx = looptris[0].face[fmap] if fmap is not None else 0
                        for loop in looptris:
                            uvs[idx].append(loop[uv_layer].uv.to_tuple(5))

                t_colors = {
                    0: lambda: (*addon_prefs.UnFinishedColor[:3], addon_prefs.UnFinishedColor[3]),
                    1: lambda: (*addon_prefs.FinishedColor[:3], addon_prefs.FinishedColor[3]),
                }

                for k, v in uvs.items():
                    if len(v) > 0:
                        uv_verts, uv_indices = np.unique(v, return_inverse=True, axis=0)
                        uv_coords = uv_verts.tolist()
                        uv_indices = uv_indices.astype(np.int32)

                        shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                        batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                        batch.program_set(shader)

                        self.custom_shapes.append(
                            DrawCustomShape(batch, shader, p_obj, t_colors[k]))

    def build_overlapped(self, context: bpy.types.Context):

        def zenuv_uv_delayed_build_overlap(self, context: bpy.types.Context):
            try:
                addon_prefs = get_prefs()

                p_overlap = UvOverlap(context)

                t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

                me: bpy.types.Mesh
                for me, p_obj in p_overlap.t_meshes.items():
                    update_data = t_updates.get(me, ['', ''])
                    self.mesh_data[me] = update_data.copy()

                    bm = bmesh.from_edit_mesh(me)
                    bm.faces.ensure_lookup_table()
                    uv_layer = bm.loops.layers.uv.active
                    if uv_layer:
                        loops = bm.calc_loop_triangles()
                        uvs = [
                            loop[uv_layer].uv.to_tuple(5)
                            for looptris in loops for loop in looptris
                            if not looptris[0].face.hide and
                            (
                                (self.uv_sync and looptris[0].face.select) or
                                (looptris[0].face.select and loop[uv_layer].select)
                            )
                        ] if me.total_face_sel else []

                        if len(uvs):
                            uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                            uv_coords = uv_verts.tolist()
                            uv_indices = uv_indices.astype(np.int32)

                            shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                            batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                            batch.program_set(shader)

                            self.custom_shapes.append(
                                DrawCustomShape(
                                    batch, shader, p_obj,
                                    lambda: (*addon_prefs.UvOverlappedColor[:3], addon_prefs.UvOverlappedColor[3])))

                p_overlap.restore()
            except Exception as e:
                Log.error('DELAYED OVERLAP:', e)

        bpy.app.timers.register(functools.partial(zenuv_uv_delayed_build_overlap, self, context))

    def build_flipped(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                loops = bm.calc_loop_triangles()
                uvs = [
                    loop[uv_layer].uv.to_tuple(5)
                    for looptris in loops for loop in looptris
                    if not looptris[0].face.hide and
                    (self.uv_sync or looptris[0].face.select) and
                    self.is_face_flipped(uv_layer, looptris[0].face)
                ]

                if len(uvs):
                    uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                    uv_coords = uv_verts.tolist()
                    uv_indices = uv_indices.astype(np.int32)

                    shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                    batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                    batch.program_set(shader)

                    self.custom_shapes.append(
                        DrawCustomShape(
                            batch, shader, p_obj,
                            lambda: (*addon_prefs.FlippedColor[:3], addon_prefs.FlippedColor[3])))

    def build_seams(self, context: bpy.types.Context):
        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        def get_color():
            p_color = bpy.context.preferences.themes[0].view_3d.edge_seam[:3]
            return (*p_color, 1.0)

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                uvs = []
                for e in bm.edges:
                    if not e.hide and (self.uv_sync or e.select) and e.seam:
                        for loop in e.link_loops:
                            next_loop = loop.link_loop_next
                            if (self.uv_sync and not loop.face.hide) or (loop.face.select and next_loop.face.select):
                                uv = loop[uv_layer].uv
                                next_uv = next_loop[uv_layer].uv
                                uvs.append(uv.to_tuple(5))
                                uvs.append(next_uv.to_tuple(5))

                if len(uvs):
                    uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                    uv_coords = uv_verts.tolist()
                    uv_indices = uv_indices.astype(np.int32)

                    shader = shader_2D_lines

                    batch = batch_for_shader(
                        shader, 'LINES',
                        {"pos": uv_coords},
                        indices=uv_indices)
                    batch.program_set(shader)
                    self.custom_shapes.append(
                        DrawCustomShape(batch, shader, p_obj, get_color))

    def build_uv_borders(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        def get_color():
            return addon_prefs.uv_borders_draw.color[:]

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        d_margin = 0
        if addon_prefs.uv_borders_draw.mode == 'PACK_MARGIN':
            from ZenUV.utils.generic import get_padding_in_pct
            d_margin = (
                get_padding_in_pct(context, addon_prefs.margin_px)
                if addon_prefs.margin_show_in_px else addon_prefs.margin)
        elif addon_prefs.uv_borders_draw.mode == 'USER_MARGIN':
            d_margin = addon_prefs.uv_borders_draw.user_margin * 0.01

        if d_margin != 0:
            shader = shader_2D_tris
        else:
            shader = shader_2D_lines

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                p_bound_edges = {}
                for face in bm.faces:
                    if not face.hide and (self.uv_sync or face.select):
                        b_flipped = self.is_face_flipped(uv_layer, face)
                        for edge in face.edges:
                            if (
                                    edge.link_loops and edge.link_loops[0][uv_layer].uv
                                    != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
                                    or edge.link_loops[-1][uv_layer].uv
                                    != edge.link_loops[-1].link_loop_radial_next.link_loop_next[uv_layer].uv):
                                p_bound_edges[edge] = b_flipped

                if p_bound_edges:
                    uvs = []
                    uv_indices = []
                    for e in bm.edges:
                        b_is_edge_flipped = p_bound_edges.get(e, None)
                        if b_is_edge_flipped is not None:
                            for loop in e.link_loops:
                                next_loop = loop.link_loop_next
                                if (self.uv_sync and not loop.face.hide) or (loop.face.select and next_loop.face.select):
                                    uv = loop[uv_layer].uv
                                    next_uv = next_loop[uv_layer].uv
                                    # pair 1
                                    uvs.append(uv.to_tuple(5))
                                    uvs.append(next_uv.to_tuple(5))

                                    if d_margin != 0:
                                        # pair 2
                                        ort = (uv - next_uv).orthogonal().normalized() * d_margin
                                        if b_is_edge_flipped:
                                            ort.negate()

                                        uv_2 = uv + ort
                                        next_uv_2 = next_uv + ort

                                        uvs.append(uv_2.to_tuple(5))
                                        uvs.append(next_uv_2.to_tuple(5))

                                        n_v_idx = len(uvs) - 4

                                        uv_indices.extend(
                                            [
                                                (n_v_idx, n_v_idx + 1, n_v_idx + 2),
                                                (n_v_idx + 2, n_v_idx + 1, n_v_idx + 3)])

                    if len(uvs):
                        if d_margin != 0:
                            batch = batch_for_shader(
                                shader, 'TRIS',
                                {"pos": uvs},
                                indices=uv_indices)
                            batch.program_set(shader)
                            self.custom_shapes.append(
                                DrawCustomShape(batch, shader, p_obj, get_color))
                        else:
                            uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                            uv_coords = uv_verts.tolist()
                            uv_indices = uv_indices.astype(np.int32)

                            batch = batch_for_shader(
                                shader, 'LINES',
                                {"pos": uv_coords},
                                indices=uv_indices)
                            batch.program_set(shader)
                            self.custom_shapes.append(
                                DrawCustomShape(batch, shader, p_obj, get_color))

    def build_uv_object(self, context: bpy.types.Context):
        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        addon_prefs = get_prefs()

        def get_color(me):

            p_act_me = (
                context.active_object.data
                if context.active_object and context.active_object.type == 'MESH'
                else None)

            p_color = (
                    addon_prefs.UvObjectActiveColor
                    if me == p_act_me
                    else addon_prefs.UvObjectInactiveColor
                )

            return p_color

        def get_point_color(me):

            p_act_me = (
                context.active_object.data
                if context.active_object and context.active_object.type == 'MESH'
                else None)

            p_color = (
                    addon_prefs.UvObjectActivePoint
                    if me == p_act_me
                    else addon_prefs.UvObjectInactivePoint
                )

            return p_color

        shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
        format = gpu.types.GPUVertFormat()
        format.attr_add(id="pos", comp_type='F32', len=2, fetch_mode='FLOAT')

        me: bpy.types.Mesh
        for me, p_obj in reversed(get_unique_mesh_object_map_with_active(context).items()):
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy() if update_data is not None else None

            if context.mode == 'OBJECT':
                uv_layer = me.uv_layers.active
                if uv_layer:
                    me.calc_loop_triangles()

                    if ZenPolls.version_lower_3_5_0:
                        uvs = [
                            uv_layer.data[loop].uv.to_tuple(5)
                            for looptris in me.loop_triangles for loop in looptris.loops
                        ]
                    else:
                        uvs = [
                            uv_layer.uv[loop].vector.to_tuple(5)
                            for looptris in me.loop_triangles for loop in looptris.loops
                        ]

                    if len(uvs) > 0:
                        uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                        uv_coords = uv_verts.tolist()
                        uv_indices = uv_indices.astype(np.int32)

                        n_uv_coords = len(uv_coords)

                        if n_uv_coords > 0 and len(uv_indices) > 0:
                            vbo = gpu.types.GPUVertBuf(format, len=n_uv_coords)
                            vbo.attr_fill(0, data=uv_coords)

                            ibo = gpu.types.GPUIndexBuf(type='TRIS', seq=uv_indices)
                            batch = gpu.types.GPUBatch(type='TRIS', buf=vbo, elem=ibo)
                            batch.program_set(shader)

                            self.custom_shapes.append(
                                DrawCustomShape(
                                    batch, shader, p_obj,
                                    functools.partial(get_color, me)))

                            if addon_prefs.UvObjectPointsDisplay:
                                ibo = gpu.types.GPUIndexBuf(type='POINTS', seq=uv_indices)
                                batch = gpu.types.GPUBatch(type='POINTS', buf=vbo, elem=ibo)
                                batch.program_set(shader)

                                self.custom_shapes.append(
                                    DrawCustomShape(
                                        batch, shader, p_obj,
                                        functools.partial(get_point_color, me)))

    def build_excluded(self, context: bpy.types.Context):
        from ZenUV.ops.pack_sys.pack_exclusion import PACK_EXCLUDED_FACEMAP_NAME

        addon_prefs = get_prefs()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            mesh_layer = bm.faces.layers.int.get(PACK_EXCLUDED_FACEMAP_NAME)
            if uv_layer and mesh_layer:
                loops = bm.calc_loop_triangles()
                uvs = [
                    loop[uv_layer].uv.to_tuple(5)
                    for looptris in loops for loop in looptris
                    if not looptris[0].face.hide and
                    (self.uv_sync or looptris[0].face.select) and
                    looptris[0].face[mesh_layer] == 1
                ]

                if len(uvs):
                    uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                    uv_coords = uv_verts.tolist()
                    uv_indices = uv_indices.astype(np.int32)

                    shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                    batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                    batch.program_set(shader)

                    self.custom_shapes.append(
                        DrawCustomShape(
                            batch, shader, p_obj,
                            lambda: (*addon_prefs.ExcludedColor[:3], addon_prefs.ExcludedColor[3])))

    def build_similar_static(self, context: bpy.types.Context):
        self.do_build_similar(context, False)

    def build_stacked_manual(self, context: bpy.types.Context):
        self.do_build_similar(context, True)

    def do_build_similar(self, context: bpy.types.Context, b_is_manual: bool):
        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        stacks = StacksSystem(context)
        sim_data = stacks.forecast_stacks()
        write_sim_data_to_layer(context, sim_data)

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm = bm.copy()

            bm.verts.index_update()
            bm.edges.index_update()
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer is None:
                continue

            if not self.uv_sync:
                t_face_sel = {face: face.select for face in bm.faces}

            bound_edges = [
                bm.edges[index]
                for index in island_util.get_uv_bound_edges_indexes(bm.faces, uv_layer)]
            if bound_edges:
                bmesh.ops.split_edges(bm, edges=bound_edges)

            bm.verts.ensure_lookup_table()

            no_actual_verts = [v for v in bm.verts if not v.link_faces]
            if no_actual_verts:
                bmesh.ops.delete(bm, geom=no_actual_verts, context='VERTS')
            bm.verts.ensure_lookup_table()
            stacks_layer = enshure_stack_layer(
                bm,
                stack_layer_name=M_STACK_LAYER_NAME if b_is_manual else STACK_LAYER_NAME)
            colors = [color_by_layer_sim_index(bm, v_idx, stacks_layer) for v_idx in range(len(bm.verts))]
            loops = bm.calc_loop_triangles()

            colors = []
            uvs = []
            for looptris in loops:
                p_face: bmesh.types.BMFace = looptris[0].face
                if not p_face.hide and (self.uv_sync or t_face_sel.get(p_face, True)):
                    for loop in looptris:
                        colors.append(
                            color_by_layer_sim_index(
                                bm, loop.vert.index, stacks_layer))
                        uvs.append(loop[uv_layer].uv.to_tuple(5))

            if len(uvs):
                uv_verts, tri_indices, uv_indices = np.unique(uvs, return_index=True, return_inverse=True, axis=0)
                uv_coords = uv_verts.tolist()
                uv_indices = uv_indices.astype(np.int32)
                uv_colors = [colors[idx] for idx in tri_indices]

                shader = gpu.shader.from_builtin(ZenCompat.get_2d_smooth_color())
                batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords, "color": uv_colors}, indices=uv_indices)
                batch.program_set(shader)

                self.custom_shapes.append(
                    DrawCustomShape(
                        batch=batch,
                        shader=shader,
                        color=None,
                        obj=p_obj))

            bm.free()

    def build_stacked(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        def get_color():
            return (*addon_prefs.StackedColor[:3], addon_prefs.StackedColor[3])

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        stacks = StacksSystem(context)
        stacked = stacks.get_stacked()
        ids_dict = stacks.get_stacked_faces_ids(stacked)

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            faces_ids = ids_dict.get(p_obj.name, [])
            if faces_ids:
                bm = bmesh.from_edit_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                uv_layer = bm.loops.layers.uv.active
                if uv_layer is None:
                    continue

                loops = bm.calc_loop_triangles()

                uvs = [
                    loop[uv_layer].uv.to_tuple(5)
                    for looptris in loops for loop in looptris
                    if not looptris[0].face.hide and
                    (self.uv_sync or looptris[0].face.select) and
                    looptris[0].face.index in faces_ids
                ]

                if len(uvs):
                    uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                    uv_coords = uv_verts.tolist()
                    uv_indices = uv_indices.astype(np.int32)

                    shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                    batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                    batch.program_set(shader)

                    self.custom_shapes.append(
                        DrawCustomShape(batch, shader, p_obj, get_color))

    def build_similar_selected(self, context: bpy.types.Context):
        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        stacks = StacksSystem(context)
        sim_data = stacks.forecast_selected()

        def get_color(p_color):
            return p_color

        for me in get_unique_mesh_object_map_with_active(context).keys():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

        for sim_index, data in sim_data.items():
            s_index = sim_index
            for obj_name, islands in data["objs"].items():
                obj = context.scene.objects[obj_name]

                bms = bmesh.from_edit_mesh(obj.data).copy()
                bms.faces.ensure_lookup_table()
                n_faces = len(bms.faces)
                if n_faces == 0:
                    continue

                bms.verts.ensure_lookup_table()

                s_faces = set(chain.from_iterable(islands.values()))

                if n_faces - len(s_faces) > 0:
                    faces_to_del = [f for f in bms.faces if f.index not in s_faces]

                    bmesh.ops.delete(bms, geom=faces_to_del, context='FACES')
                    bms.verts.ensure_lookup_table()
                    bms.faces.ensure_lookup_table()

                uv_layer = bms.loops.layers.uv.active
                if uv_layer is None:
                    continue

                loops = bms.calc_loop_triangles()

                color = color_by_sim_index(s_index)

                uvs = [
                    loop[uv_layer].uv.to_tuple(5)
                    for looptris in loops for loop in looptris
                    if not looptris[0].face.hide
                    and (self.uv_sync or looptris[0].face.select)
                ]

                if len(uvs):
                    uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
                    uv_coords = uv_verts.tolist()
                    uv_indices = uv_indices.astype(np.int32)

                    shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                    batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                    batch.program_set(shader)

                    self.custom_shapes.append(
                        DrawCustomShape(batch, shader, obj, functools.partial(get_color, color)))

                bms.free()

    def build_texel_density(self, context: bpy.types.Context):
        interval = timer()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        p_objects = []

        p_geometry_keys = []

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()
            p_geometry_keys.append(update_data[0])
            p_objects.append(p_obj)

        if context.scene.zen_uv.ui.draw_sub_TD_UV not in {'VIEWPORT', 'ALL'}:
            return

        if len(p_objects) == 0:
            return

        addon_prefs = get_prefs()

        from ZenUV.ops.texel_density.td_utils import TdUtils, TdContext, TdBmeshManager
        from ZenUV.ops.texel_density.td_display_utils import TdColorProcessor
        td_inputs = TdContext(context)
        interval1 = timer()

        td_scope = None

        p_stored_td_scope = bpy.app.driver_namespace.get(LITERAL_ZENUV_TD_SCOPE, None)
        if p_stored_td_scope:
            if p_geometry_keys and p_geometry_keys == p_stored_td_scope[0]:
                td_scope = p_stored_td_scope[1]

        if not td_scope:
            td_scope = TdUtils.get_td_data_with_precision(context, p_objects, td_inputs, False)
            bpy.app.driver_namespace[LITERAL_ZENUV_TD_SCOPE] = (p_geometry_keys, td_scope)


        td_display_props = context.scene.zen_uv.td_draw_props

        CP = TdColorProcessor(context, td_scope, td_display_props)
        CP.calc_output_range(context, td_inputs, td_display_props.display_method)

        def get_color(p_color):
            return (*p_color, addon_prefs.td_draw.alpha)

        self.custom_data['texel_data_map'] = {}

        for p_obj_name, p_islands in td_scope.get_islands_by_objects().items():
            if len(p_islands) == 0:
                continue

            p_obj = context.scene.objects[p_obj_name]
            bm = TdBmeshManager.get_bm(td_inputs, p_obj)
            bm.faces.ensure_lookup_table()

            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                p_loops = bm.calc_loop_triangles()

                t_color_map = {
                    idx: [(round(island.color[0], 2), round(island.color[1], 2), round(island.color[2], 2)), island.td]
                    for island in p_islands for idx in island.indices}
                self.custom_data['texel_data_map'][p_obj_name] = t_color_map

                face_tri_indices = defaultdict(list)
                for looptris in p_loops:
                    p_face: bmesh.types.BMFace = looptris[0].face
                    if not p_face.hide and (self.uv_sync or p_face.select):
                        p_color, _ = t_color_map.get(p_face.index, [(0, 0, 0), 0])
                        for loop in looptris:
                            face_tri_indices[p_color].append(loop[uv_layer].uv.to_tuple(5))

                if face_tri_indices:
                    for k, v in face_tri_indices.items():
                        if len(v) > 0:
                            uv_verts, uv_indices = np.unique(v, return_inverse=True, axis=0)
                            uv_coords = uv_verts.tolist()
                            uv_indices = uv_indices.astype(np.int32)

                            shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())
                            batch = batch_for_shader(shader, 'TRIS', {"pos": uv_coords}, indices=uv_indices)
                            batch.program_set(shader)

                            self.custom_shapes.append(
                                DrawCustomShape(batch, shader, p_obj, functools.partial(get_color, k)))



class ZUV_GGT_Draw3D(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_Draw3D"
    bl_label = "Draw 3D"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {
        '3D', 'PERSISTENT', 'SHOW_MODAL_ALL'
    }

    tool_mode = {'DISPLAY'}

    t_draw_handles = {}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return (
            (context.space_data.overlay.show_overlays or not p_scene.zen_uv.ui.use_draw_overlay_sync) and
            p_scene.zen_uv.ui.draw_mode_3D != 'NONE' and context.mode == 'EDIT_MESH')

    def setup(self, context: bpy.types.Context):
        self.mpr_draw: VIEW3D_GT_zenuv_overlay_draw = self.gizmos.new("VIEW3D_GT_zenuv_overlay_draw")
        self.mpr_draw.color = 0.0, 1.0, 0.0
        self.mpr_draw.alpha = 0.1
        self.mpr_draw.color_highlight = 0, 1.0, 1.0
        self.mpr_draw.alpha_highlight = 1
        self.mpr_draw.line_width = 1
        self.mpr_draw.use_draw_value = False
        self.mpr_draw.use_draw_scale = False
        self.mpr_draw.use_draw_modal = False
        self.mpr_draw.use_select_background = False
        self.mpr_draw.use_event_handle_all = False
        self.mpr_draw.use_grab_cursor = False
        self.mpr_draw.hide_select = True

        t_3D_GIZMOS[context.area.as_pointer()] = self.mpr_draw

        s_draw_guid = str(uuid.uuid4())
        ZUV_GGT_Draw3D.t_draw_handles[s_draw_guid] = bpy.types.SpaceView3D.draw_handler_add(
            self.draw, (s_draw_guid,), 'WINDOW', 'POST_VIEW')

    def draw(self, s_draw_guid):
        try:
            context = bpy.context
            p_space_data = context.space_data
            if self.poll(context) and (not hasattr(p_space_data, 'show_gizmo') or p_space_data.show_gizmo):
                self.mpr_draw._do_draw(bpy.context)
        except ReferenceError as e:
            bpy.types.SpaceView3D.draw_handler_remove(
                ZUV_GGT_Draw3D.t_draw_handles[s_draw_guid], 'WINDOW')
            del ZUV_GGT_Draw3D.t_draw_handles[s_draw_guid]

    def refresh(self, context: bpy.types.Context):
        pass


class VIEW3D_GT_zenuv_overlay_draw(bpy.types.Gizmo):
    bl_idname = "VIEW3D_GT_zenuv_overlay_draw"
    bl_target_properties = ()

    __slots__ = (
        "custom_shapes",
        "mesh_data",
        "last_mode",
        "mark_build",
        # NOTE: use this attribute to store special data that is unique for some draw modes, it will clear on build
        "custom_data"
    )

    def _delayed_build(self):
        if bpy.app.timers.is_registered(zenuv_delayed_overlay_build_3D):
            bpy.app.timers.unregister(zenuv_delayed_overlay_build_3D)
        t_delayed_gizmos = bpy.app.driver_namespace.get(LITERAL_ZENUV_DELAYED_3D_GIZMOS, set())
        t_delayed_gizmos.add(self)
        bpy.app.driver_namespace[LITERAL_ZENUV_DELAYED_3D_GIZMOS] = t_delayed_gizmos
        bpy.app.timers.register(zenuv_delayed_overlay_build_3D, first_interval=0.05)

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        # when we assigned nothing
        if self.mesh_data is None:
            return

        wm = context.window_manager
        if self.mark_build == -1 or wm.zen_uv.draw_props.draw_auto_update:
            if self.mark_build:
                if not is_modal_procedure(context):
                    self.build(context)
                else:
                    self._delayed_build()
            elif not self.check_valid_data(context):
                if not is_modal_procedure(context):
                    self._delayed_build()
                return

        if not self.custom_shapes:
            return

        if ZenPolls.version_lower_3_5_0:
            import bgl
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glEnable(bgl.GL_LINE_SMOOTH)
            bgl.glEnable(bgl.GL_DEPTH_TEST)
            bgl.glEnable(bgl.GL_POLYGON_OFFSET_FILL)
            bgl.glPolygonOffset(-1, -1)
        else:
            gpu.state.blend_set('ALPHA')
            gpu.state.depth_test_set('LESS_EQUAL')

        addon_prefs = get_prefs()

        s_draw_mode_3D = context.scene.zen_uv.ui.draw_mode_3D
        i_line_width = 1
        if s_draw_mode_3D == 'UV_BORDERS':
            i_line_width = addon_prefs.uv_borders_draw.line_width
            gpu.state.line_width_set(i_line_width)

        draw_shape: DrawCustomShape
        for draw_shape in self.custom_shapes:
            self.matrix_space = draw_shape.obj.matrix_world.copy()

            batch, shader = draw_shape.get_shape()

            shader.bind()

            if draw_shape.color is not None:
                shader.uniform_float('color', draw_shape.color())

            if draw_shape.mode == 0:
                if not ZenPolls.version_lower_3_5_0:
                    shader.uniform_float('z_offset', draw_shape.z_offset)
            elif draw_shape.mode == 1:
                shader.uniform_float('viewportSize', gpu.state.viewport_get()[2:])
                shader.uniform_float('lineWidth', i_line_width)

            with gpu.matrix.push_pop():
                gpu.matrix.multiply_matrix(self.matrix_world)

                batch.draw(shader)

        if ZenPolls.version_lower_3_5_0:
            import bgl
            bgl.glDisable(bgl.GL_BLEND)
            bgl.glDisable(bgl.GL_LINE_SMOOTH)
            bgl.glDisable(bgl.GL_POLYGON_OFFSET_FILL)
            bgl.glPolygonOffset(0, 0)
        else:
            gpu.state.blend_set('NONE')
            gpu.state.depth_mask_set(False)
        gpu.state.line_width_set(1)

    def draw(self, context: bpy.types.Context):
        return
        # NOTE: we comment this until will be fixed: https://projects.blender.org/blender/blender/issues/98598
        # self._do_draw(context)

    def test_select(self, context: bpy.types.Context, location):
        return -1

    def draw_select(self, context: bpy.types.Context, select_id):
        self._do_draw(context, select_id=select_id)

    def setup(self):
        if not hasattr(self, "mesh_data"):
            self.custom_shapes = []
            self.mesh_data = {}
            self.last_mode = ''
            self.mark_build = 0

            # NOTE: is cleard on every build
            self.custom_data = defaultdict(dict)

    def exit(self, context, cancel):
        context.area.header_text_set(None)

    def check_valid_data(self, context: bpy.types.Context):
        p_scene = context.scene
        if self.last_mode != p_scene.zen_uv.ui.draw_mode_3D:
            return False

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        check_data = {}

        for me in get_unique_mesh_object_map_with_active(context).keys():
            check_data[me] = t_updates.get(me, ['', ''])

        s_draw_mode = p_scene.zen_uv.ui.draw_mode_3D

        # 1) check shading, geometry
        b_is_uv_sync = p_scene.tool_settings.use_uv_select_sync
        if ((not b_is_uv_sync and s_draw_mode == 'UV_NO_SYNC') or
                s_draw_mode in {'SIMILAR_SELECTED'}):
            return self.mesh_data == check_data

        # 2) check only geometry
        if self.mesh_data.keys() != check_data.keys():
            return False

        for key in self.mesh_data.keys():
            if self.mesh_data[key][0] != check_data[key][0]:
                return False

        # NOTE: special case for Trim Colors
        if s_draw_mode == 'TRIM_COLORS':
            from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
            addon_prefs = get_prefs()
            if addon_prefs.trimsheet.mode != self.custom_data.get("trimsheet_mode", None):
                return False

            p_uuids = ZuvTrimsheetUtils.getAllTrimsheetUuids(context)

            # NOTE: we are checking for all uuids, maybe in the future we should make more performance checks
            return self.custom_data.get("trimsheet_uuids_all", set()) == p_uuids

        return True

    def build(self, context: bpy.types.Context):
        p_scene = context.scene

        self.mark_build = 0

        method_name = 'build_' + p_scene.zen_uv.ui.draw_mode_3D.lower()
        if hasattr(self, method_name):
            p_method = getattr(self, method_name)

            self.custom_shapes.clear()
            self.mesh_data = {}
            self.last_mode = p_scene.zen_uv.ui.draw_mode_3D

            p_method(context)
        else:
            raise RuntimeError(f'3D Build: {method_name} is not defined!')

    def build_finished(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()

            verts = [v.co.to_tuple() for v in bm.verts]

            fmap = bm.faces.layers.int.get("ZenUV_Finished")

            p_loops = bm.calc_loop_triangles()
            face_tri_indices = defaultdict(list)
            for looptris in p_loops:
                if not looptris[0].face.hide:
                    idx = looptris[0].face[fmap] if fmap is not None else 0
                    face_tri_indices[idx].append([loop.vert.index for loop in looptris])

            shader = shader_tris

            z_offset = get_z_offset(p_obj)

            t_colors = {
                0: lambda: (*addon_prefs.UnFinishedColor[:3], addon_prefs.UnFinishedColor[3]),
                1: lambda: (*addon_prefs.FinishedColor[:3], addon_prefs.FinishedColor[3]),
            }

            for k, v in face_tri_indices.items():
                if len(v) > 0:
                    batch = batch_for_shader(
                        shader, 'TRIS',
                        {"pos": verts},
                        indices=v)
                    batch.program_set(shader)
                    self.custom_shapes.append(
                        DrawCustomShape(batch, shader, p_obj, t_colors[k], z_offset))

    def build_excluded(self, context: bpy.types.Context):
        from ZenUV.ops.pack_sys.pack_exclusion import PACK_EXCLUDED_FACEMAP_NAME

        addon_prefs = get_prefs()

        def get_layer(bm: bmesh.types.BMesh):
            return bm.faces.layers.int.get(PACK_EXCLUDED_FACEMAP_NAME)

        def is_face_enabled(layer: bmesh.types.BMLayerItem, face: bmesh.types.BMFace):
            return face[layer] == 1

        def get_color():
            return (*addon_prefs.ExcludedColor[:3], addon_prefs.ExcludedColor[3])

        self.build_uniform_layer(context, get_layer, is_face_enabled, get_color)

    def build_flipped(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        def get_layer(bm: bmesh.types.BMesh):
            return bm.loops.layers.uv.active

        def is_face_enabled(layer: bmesh.types.BMLayerItem, face: bmesh.types.BMFace):
            return UV_GT_zenuv_overlay_draw.is_face_flipped(layer, face)

        def get_color():
            return (*addon_prefs.FlippedColor[:3], addon_prefs.FlippedColor[3])

        self.build_uniform_layer(context, get_layer, is_face_enabled, get_color)

    def build_uv_borders(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        def get_color():
            return addon_prefs.uv_borders_draw.color[:]

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.edges.ensure_lookup_table()
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                edges = {
                    edge
                    for face in bm.faces
                    for edge in face.edges
                    if not face.hide and not edge.hide and edge.link_loops}
                p_edge_indices = [
                    (v.index for v in edge.verts) for edge in edges
                    if edge.link_loops[0][uv_layer].uv
                    != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
                    or edge.link_loops[-1][uv_layer].uv
                    != edge.link_loops[-1].link_loop_radial_next.link_loop_next[uv_layer].uv]

                if p_edge_indices:
                    shader = shader_3D_lines

                    verts = [v.co.to_tuple() for v in bm.verts]

                    batch = batch_for_shader(
                        shader, 'LINES',
                        {"pos": verts},
                        indices=p_edge_indices)
                    batch.program_set(shader)
                    self.custom_shapes.append(
                        DrawCustomShape(batch, shader, p_obj, get_color, mode=1))

    def build_overlapped(self, context: bpy.types.Context):

        def zenuv_3d_delayed_build_overlap(self: VIEW3D_GT_zenuv_overlay_draw, context: bpy.types.Context):
            try:
                addon_prefs = get_prefs()

                p_overlap = UvOverlap(context)

                def get_layer(bm: bmesh.types.BMesh):
                    return bm.loops.layers.uv.active

                def is_face_enabled(layer: bmesh.types.BMLayerItem, face: bmesh.types.BMFace):
                    return face.select if context.tool_settings.use_uv_select_sync else any(loop[layer].select for loop in face.loops)

                def get_color():
                    return (*addon_prefs.UvOverlappedColor[:3], addon_prefs.UvOverlappedColor[3])

                self.build_uniform_layer(context, get_layer, is_face_enabled, get_color)

                p_overlap.restore()
            except Exception as e:
                Log.error('DELAYED OVERLAP:', e)

        bpy.app.timers.register(functools.partial(zenuv_3d_delayed_build_overlap, self, context))

    def build_tagged(self, context: bpy.types.Context):
        def get_face_color():
            return (0.505, 0.8, 0.175, 0.2)

        def get_edge_color():
            return (0.0, 1.0, 0.25, 1)

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()

            p_loops = bm.calc_loop_triangles()
            p_indices = [
                [loop.vert.index for loop in looptris]
                for looptris in p_loops
                if not looptris[0].face.hide and
                looptris[0].face.tag
            ]

            verts = [v.co.to_tuple() for v in bm.verts]

            if p_indices:
                shader = shader_tris

                z_offset = get_z_offset(p_obj)

                batch = batch_for_shader(
                    shader, 'TRIS',
                    {"pos": verts},
                    indices=p_indices)
                batch.program_set(shader)
                self.custom_shapes.append(
                    DrawCustomShape(batch, shader, p_obj, get_face_color, z_offset))

            edge_indices = [(v.index for v in e.verts) for e in bm.edges if e.tag]
            if edge_indices:
                shader = shader_tris

                z_offset = get_z_offset(p_obj)

                batch = batch_for_shader(
                    shader, 'LINES',
                    {"pos": verts},
                    indices=p_indices)
                batch.program_set(shader)
                self.custom_shapes.append(
                    DrawCustomShape(batch, shader, p_obj, get_edge_color, z_offset))

    def build_uniform_layer(self, context: bpy.types.Context, get_layer: callable, is_face_enabled: callable, fn_color: callable):

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()
            uv_layer = get_layer(bm)
            if uv_layer:
                p_loops = bm.calc_loop_triangles()
                p_indices = [
                    [loop.vert.index for loop in looptris]
                    for looptris in p_loops
                    if not looptris[0].face.hide and
                    is_face_enabled(uv_layer, looptris[0].face)
                ]
                if p_indices:
                    shader = shader_tris

                    verts = [v.co.to_tuple() for v in bm.verts]

                    z_offset = get_z_offset(p_obj)

                    batch = batch_for_shader(
                        shader, 'TRIS',
                        {"pos": verts},
                        indices=p_indices)
                    batch.program_set(shader)
                    self.custom_shapes.append(
                        DrawCustomShape(batch, shader, p_obj, fn_color, z_offset))

    def build_uv_no_sync(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        b_is_uv_sync = context.scene.tool_settings.use_uv_select_sync

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            if b_is_uv_sync:
                continue

            bm = bmesh.from_edit_mesh(me).copy()
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            if uv_layer:
                p_loops = bm.calc_loop_triangles()
                p_indices = [
                    [loop.vert.index for loop in looptris]
                    for looptris in p_loops
                    if not looptris[0].face.hide and looptris[0].face.select and
                    all(loop[uv_layer].select for loop in looptris[0].face.loops)
                ]

                if p_indices:
                    shader = shader_tris

                    verts = [v.co.to_tuple() for v in bm.verts]

                    z_offset = get_z_offset(p_obj)

                    batch = batch_for_shader(
                        shader, 'TRIS',
                        {"pos": verts},
                        indices=p_indices)
                    batch.program_set(shader)
                    self.custom_shapes.append(
                        DrawCustomShape(
                            batch, shader, p_obj,
                            lambda: (*addon_prefs.UvNoSyncColor[:3], addon_prefs.UvNoSyncColor[3]),
                            z_offset))

            bm.free()

    def build_stretched(self, context: bpy.types.Context):
        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        def get_dir_vector(pos_0, pos_1):
            """ Return direction Vector from 2 Vectors """
            return Vector(pos_1 - pos_0)

        def get_distortion_color(uv_layer, vertex: bmesh.types.BMVert):
            """ Returns the distortion factor for a given vertex"""
            distortion = 0

            loops = vertex.link_loops
            for loop in loops:
                mesh_angle = loop.calc_angle()
                vec_0 = get_dir_vector(loop[uv_layer].uv, loop.link_loop_next[uv_layer].uv)
                vec_1 = get_dir_vector(loop[uv_layer].uv, loop.link_loop_prev[uv_layer].uv)
                uv_angle = vec_0.angle(vec_1, 0)
                distortion += abs(mesh_angle - uv_angle)

            return (0.2, baseColor.g + distortion, baseColor.b - distortion, alpha)

        p_scene = context.scene
        b_modal = p_scene.zen_uv.ui.draw_stretched_modal

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            colors = []
            baseColor = Color((0.0, 0.0, 1.0))
            alpha = 0.6

            bm = bmesh.from_edit_mesh(me)
            if not bm.loops.layers.uv.active:
                continue

            if b_modal:
                bm = bm.copy()

            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active

            p_loops = bm.calc_loop_triangles()

            face_tri_indices = [
                [loop.vert.index for loop in looptris]
                for looptris in p_loops
                if not looptris[0].face.hide]

            if face_tri_indices:
                verts = [v.co.to_tuple() for v in bm.verts]

                colors = [get_distortion_color(uv_layer, vertex) for vertex in bm.verts]

                shader = shader_smooth_tris

                z_offset = get_z_offset(p_obj)

                batch = batch_for_shader(
                    shader, 'TRIS',
                    {"pos": verts, "color": colors},
                    indices=face_tri_indices)
                batch.program_set(shader)
                self.custom_shapes.append(
                    DrawCustomShape(
                        batch=batch,
                        shader=shader,
                        color=None,
                        obj=p_obj,
                        z_offset=z_offset))

            if b_modal:
                bm.free()

    def build_trim_colors(self, context: bpy.types.Context):
        interval = timer()

        addon_prefs = get_prefs()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetGroup
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

        b_is_scene_mode = addon_prefs.trimsheet.mode == "SCENE"
        p_scene_trimsheet = context.scene.zen_uv.trimsheet
        p_scene_trimsheet_geometry_uuid = context.scene.zen_uv.trimsheet_geometry_uuid

        def get_trim_color(p_trim: ZuvTrimsheetGroup):
            try:
                return (*p_trim.color[:], addon_prefs.TrimColorsAlpha)
            except Exception as e:
                Log.error(e)

            return (0, 0, 0, 0)

        self.custom_data["trimsheet_uuids"] = set()
        self.custom_data["trimsheet_mode"] = addon_prefs.trimsheet.mode
        self.custom_data["trimsheet_uuids_all"] = ZuvTrimsheetUtils.getAllTrimsheetUuids(context)

        p_obj: bpy.types.Object
        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            bm.faces.ensure_lookup_table()

            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            t_trimsheet_map = {}

            if b_is_scene_mode:
                if len(p_scene_trimsheet) == 0:
                    continue
                t_trimsheet_map[-1] = (
                    p_scene_trimsheet,
                    np.array([trim.rect[:] for trim in p_scene_trimsheet]),
                    p_scene_trimsheet_geometry_uuid)
            else:
                for slot in p_obj.material_slots:
                    p_image = ZuvTrimsheetUtils.getMaterialImage(slot.material)
                    if p_image:
                        p_trimsheet = p_image.zen_uv.trimsheet
                        if p_trimsheet:
                            t_trimsheet_map[slot.slot_index] = (
                                p_trimsheet,
                                np.array([trim.rect for trim in p_trimsheet]),
                                p_image.zen_uv.trimsheet_geometry_uuid)

            verts = [v.co.to_tuple() for v in bm.verts]

            p_loops = bm.calc_loop_triangles()
            face_tri_indices = defaultdict(lambda: defaultdict(list))

            p_handled_faces = dict()

            for looptris in p_loops:
                p_face: bmesh.types.BMFace = looptris[0].face
                if not p_face.hide:
                    p_face_info = p_handled_faces.get(p_face.index, None)
                    if p_face_info is None:

                        idx = -1 if b_is_scene_mode else p_face.material_index

                        p_face_info = (idx, -1)

                        p_trim_data = t_trimsheet_map.get(idx, None)
                        if p_trim_data is not None:
                            p_trimsheet, p_arr_rects, p_uuid = p_trim_data
                            uv_center = 0.0
                            if len(p_arr_rects) > 0 and len(p_face.loops) > 0:
                                uv_center = sum([loop[uv_layer].uv for loop in p_face.loops], Vector((0.0, 0.0))) / len(p_face.loops)

                                # Check if the point is within the rectangle bounds
                                inside = (
                                    (uv_center[0] >= p_arr_rects[:, 0]) &
                                    (uv_center[0] <= p_arr_rects[:, 2]) &
                                    (uv_center[1] >= p_arr_rects[:, 3]) &
                                    (uv_center[1] <= p_arr_rects[:, 1]))

                                # Find index of first matching rectangle
                                indices = np.where(inside)[0]

                                p_trim_index = indices[0] if indices.size > 0 else -1
                                if p_trim_index != -1:
                                    p_face_info = (idx, p_trim_index)
                                    self.custom_data["trimsheet_uuids"].add(p_uuid)

                        p_handled_faces[p_face.index] = p_face_info

                    idx, p_trim_index = p_face_info

                    if p_trim_index != -1:
                        face_tri_indices[idx][p_trim_index].append([loop.vert.index for loop in looptris])

            shader = shader_tris

            z_offset = get_z_offset(p_obj)

            for k, v in face_tri_indices.items():
                # NOTE: there must not be a case, when 'k' is not in dict, so not catches here!
                p_trimsheet = t_trimsheet_map[k][0]
                for idx, v_indices in v.items():
                    if len(v_indices) > 0:
                        batch = batch_for_shader(
                            shader, 'TRIS',
                            {"pos": verts},
                            indices=v_indices)
                        batch.program_set(shader)
                        self.custom_shapes.append(
                            DrawCustomShape(batch, shader, p_obj, functools.partial(get_trim_color, p_trimsheet[idx]), z_offset))


    def build_similar_static(self, context: bpy.types.Context):
        self.do_build_similar(context, False)

    def build_stacked_manual(self, context: bpy.types.Context):
        self.do_build_similar(context, True)

    def do_build_similar(self, context: bpy.types.Context, b_is_manual: bool):
        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        stacks = StacksSystem(context)
        sim_data = stacks.forecast_stacks()
        write_sim_data_to_layer(context, sim_data)

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            bm = bmesh.from_edit_mesh(me)
            if not bm.loops.layers.uv.active:
                continue

            # NOTE: we need to copy BMesh because Blender can crash in UV Editor while moving loops
            bm = bm.copy()

            bm.verts.index_update()
            bm.edges.index_update()
            bm.edges.ensure_lookup_table()
            uv_layer = bm.loops.layers.uv.active
            bound_edges = [bm.edges[index] for index in island_util.get_uv_bound_edges_indexes(bm.faces, uv_layer)]
            bmesh.ops.split_edges(bm, edges=bound_edges)
            bm.verts.ensure_lookup_table()
            no_actual_verts = [v for v in bm.verts if not v.link_faces]
            bmesh.ops.delete(bm, geom=no_actual_verts, context='VERTS')
            bm.verts.ensure_lookup_table()
            stacks_layer = enshure_stack_layer(
                bm,
                stack_layer_name=M_STACK_LAYER_NAME if b_is_manual else STACK_LAYER_NAME)
            colors = [color_by_layer_sim_index(bm, v_idx, stacks_layer) for v_idx in range(len(bm.verts))]
            loops = bm.calc_loop_triangles()
            verts = [v.co for v in bm.verts]

            face_tri_indices = [
                [loop.vert.index for loop in looptris]
                for looptris in loops
                if not looptris[0].face.hide]

            shader = shader_smooth_tris

            z_offset = get_z_offset(p_obj)

            batch = batch_for_shader(
                shader, 'TRIS',
                {"pos": verts, "color": colors},
                indices=face_tri_indices)
            batch.program_set(shader)
            self.custom_shapes.append(
                DrawCustomShape(
                    batch=batch,
                    shader=shader,
                    color=None,
                    obj=p_obj,
                    z_offset=z_offset))

            bm.free()

    def build_similar_selected(self, context: bpy.types.Context):
        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        stacks = StacksSystem(context)
        sim_data = stacks.forecast_selected()

        def get_color(p_color):
            return p_color

        for me in get_unique_mesh_object_map_with_active(context).keys():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

        for sim_index, data in sim_data.items():
            s_index = sim_index
            for obj_name, islands in data["objs"].items():
                obj = context.scene.objects[obj_name]

                bms = bmesh.from_edit_mesh(obj.data).copy()
                bms.faces.ensure_lookup_table()
                bms.verts.ensure_lookup_table()

                s_faces = set(chain.from_iterable(islands.values()))

                faces_to_del = [f for f in bms.faces if f.index not in s_faces]

                bmesh.ops.delete(bms, geom=faces_to_del, context='FACES')
                bms.verts.ensure_lookup_table()
                bms.faces.ensure_lookup_table()

                loops = bms.calc_loop_triangles()

                verts = [v.co for v in bms.verts]

                face_tri_indices = [[
                    loop.vert.index for loop in looptris]
                    for looptris in loops
                    if not looptris[0].face.hide]

                color = color_by_sim_index(s_index)

                shader = shader_tris

                z_offset = get_z_offset(obj)

                batch = batch_for_shader(
                    shader, 'TRIS',
                    {"pos": verts},
                    indices=face_tri_indices)
                batch.program_set(shader)
                self.custom_shapes.append(
                    DrawCustomShape(
                        batch=batch,
                        shader=shader,
                        color=functools.partial(get_color, color),
                        obj=obj,
                        z_offset=z_offset))

                bms.free()

    def build_stacked(self, context: bpy.types.Context):
        addon_prefs = get_prefs()

        def get_color():
            return (*addon_prefs.StackedColor[:3], addon_prefs.StackedColor[3])

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        stacks = StacksSystem(context)
        stacked = stacks.get_stacked()
        ids_dict = stacks.get_stacked_faces_ids(stacked)

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()

            faces_ids = ids_dict.get(p_obj.name, [])
            if faces_ids:
                bm = bmesh.from_edit_mesh(me)
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                loops = bm.calc_loop_triangles()
                verts = [v.co for v in bm.verts]

                face_tri_indices = [
                    [loop.vert.index for loop in looptris]
                    for looptris in loops
                    if not looptris[0].face.hide and
                    looptris[0].face.index in faces_ids]

                shader = shader_tris

                z_offset = get_z_offset(p_obj)

                batch = batch_for_shader(
                    shader, 'TRIS',
                    {"pos": verts},
                    indices=face_tri_indices)
                batch.program_set(shader)
                self.custom_shapes.append(
                    DrawCustomShape(
                        batch=batch,
                        shader=shader,
                        color=get_color,
                        obj=p_obj,
                        z_offset=z_offset))

    def build_texel_density(self, context: bpy.types.Context):
        interval = timer()

        t_updates = bpy.app.driver_namespace.get(LITERAL_ZENUV_UPDATE, {})

        p_objects = []

        p_geometry_keys = []

        for me, p_obj in get_unique_mesh_object_map_with_active(context).items():
            update_data = t_updates.get(me, ['', ''])
            self.mesh_data[me] = update_data.copy()
            p_geometry_keys.append(update_data[0])
            p_objects.append(p_obj)

        if context.scene.zen_uv.ui.draw_sub_TD_3D not in {'VIEWPORT', 'ALL'}:
            return

        if len(p_objects) == 0:
            return

        addon_prefs = get_prefs()

        from ZenUV.ops.texel_density.td_utils import TdUtils, TdContext, TdBmeshManager
        from ZenUV.ops.texel_density.td_display_utils import TdColorProcessor
        td_inputs = TdContext(context)
        interval1 = timer()

        td_scope = None

        td_display_props = context.scene.zen_uv.td_draw_props

        p_stored_td_scope = bpy.app.driver_namespace.get(LITERAL_ZENUV_TD_SCOPE, None)
        if p_stored_td_scope:
            if p_geometry_keys and p_geometry_keys == p_stored_td_scope[0]:
                td_scope = p_stored_td_scope[1]

        if not td_scope:
            td_scope = TdUtils.get_td_data_with_precision(
                context, p_objects, td_inputs, td_influence=td_display_props.influence)
            bpy.app.driver_namespace[LITERAL_ZENUV_TD_SCOPE] = (p_geometry_keys, td_scope)


        CP = TdColorProcessor(context, td_scope, td_display_props)
        CP.calc_output_range(context, td_inputs, td_display_props.display_method)

        def get_color(p_color):
            return (*p_color, addon_prefs.td_draw.alpha)

        self.custom_data['texel_data_map'] = {}

        for p_obj_name, p_islands in td_scope.get_islands_by_objects().items():
            if len(p_islands) == 0:
                continue

            p_obj = context.scene.objects[p_obj_name]
            bm = TdBmeshManager.get_bm(td_inputs, p_obj)
            bm.faces.ensure_lookup_table()

            p_loops = bm.calc_loop_triangles()

            t_color_map = {
                idx: [(round(island.color[0], 2), round(island.color[1], 2), round(island.color[2], 2)), island.td]
                for island in p_islands for idx in island.indices}
            self.custom_data['texel_data_map'][p_obj_name] = t_color_map

            face_tri_indices = defaultdict(list)
            for looptris in p_loops:
                p_face: bmesh.types.BMFace = looptris[0].face
                if not p_face.hide:
                    p_color, _ = t_color_map.get(p_face.index, [(0, 0, 0), 0])
                    face_tri_indices[p_color].append([loop.vert.index for loop in looptris])

            if face_tri_indices:
                verts = [v.co.to_tuple() for v in bm.verts]

                shader = shader_tris

                z_offset = get_z_offset(p_obj)

                for k, v in face_tri_indices.items():
                    if len(v) > 0:
                        batch = batch_for_shader(
                            shader, 'TRIS',
                            {"pos": verts},
                            indices=v)
                        batch.program_set(shader)
                        self.custom_shapes.append(
                            DrawCustomShape(batch, shader, p_obj, functools.partial(get_color, k), z_offset))



class ZUV_GGT_DrawView2D(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_DrawView2D"
    bl_label = "Draw 2D"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL'
    }

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return (
            (context.space_data.overlay.show_overlays or not p_scene.zen_uv.ui.use_draw_overlay_sync) and
            p_scene.zen_uv.ui.draw_mode_3D != 'NONE' and context.mode == 'EDIT_MESH')

    create_update_draw_button = ZUV_GGT_DrawUV.create_update_draw_button
    draw_prepare = ZUV_GGT_DrawUV.draw_prepare

    def setup(self, context: bpy.types.Context):
        self.mpr_draw = self.gizmos.new("VIEW2D_GT_zenuv_overlay_draw")
        self.mpr_draw.color = 0.0, 1.0, 0.0
        self.mpr_draw.alpha = 0.1
        self.mpr_draw.color_highlight = 0, 1.0, 1.0
        self.mpr_draw.alpha_highlight = 1
        self.mpr_draw.line_width = 1
        self.mpr_draw.use_draw_value = False
        self.mpr_draw.use_draw_scale = False
        self.mpr_draw.use_draw_modal = False
        self.mpr_draw.use_select_background = False
        self.mpr_draw.use_event_handle_all = False
        self.mpr_draw.use_grab_cursor = False
        self.mpr_draw.hide_select = True

        self.create_update_draw_button(context)

    def refresh(self, context: bpy.types.Context):
        pass


class VIEW2D_GT_zenuv_overlay_draw(bpy.types.Gizmo):
    bl_idname = "VIEW2D_GT_zenuv_overlay_draw"
    bl_target_properties = ()

    __slots__ = ()

    draw_label = UV_GT_zenuv_overlay_draw.draw_label

    draw_gradient = UV_GT_zenuv_overlay_draw.draw_gradient

    def _do_draw(self, context: bpy.types.Context, select_id=None):
        self.draw_label(context)

        # special case
        if context.scene.zen_uv.ui.draw_mode_3D == 'TEXEL_DENSITY':
            if context.scene.zen_uv.ui.draw_sub_TD_3D in {'GRADIENT', 'ALL'}:
                self.draw_gradient(context)

    def draw(self, context: bpy.types.Context):
        self._do_draw(context)

    def test_select(self, context: bpy.types.Context, location):
        return -1

    def draw_select(self, context: bpy.types.Context, select_id):
        self._do_draw(context, select_id=select_id)

    def setup(self):
        pass

    def exit(self, context, cancel):
        context.area.header_text_set(None)


class ZUV_PT_GizmoDrawProperties(bpy.types.Panel):
    bl_idname = "ZUV_PT_GizmoDrawProperties"
    bl_label = "Display Properties"
    bl_context = "__POPUP__"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 16

    def draw(self, context: bpy.types.Context):
        ''' @Draw Display Sys Properties '''
        addon_prefs = get_prefs()
        layout = self.layout

        b_is_UV = context.space_data.type == 'IMAGE_EDITOR'

        p_scene = context.scene
        wm = context.window_manager

        b_is_editmesh = context.mode == 'EDIT_MESH'
        b_is_object = context.mode == 'OBJECT'

        prop_with_icon(layout, p_scene.zen_uv.ui, 'use_draw_overlay_sync', 'OVERLAY')
        prop_with_icon(layout, wm.zen_uv.draw_props, 'draw_auto_update', 'FILE_REFRESH', s_icon_operator_id='wm.zuv_draw_update')
        prop_with_icon(layout, addon_prefs, 'draw_auto_disable', 'SCREEN_BACK')

        col_layout = layout.column()
        col_layout.use_property_split = True

        if b_is_UV:
            col = col_layout.column(align=True)
            col.prop(addon_prefs, 'UvPointsOnZoom')
            if addon_prefs.UvPointsOnZoom:
                col.prop(p_scene.zen_uv.ui, 'uv_points_draw_zoom_ratio')

        if b_is_editmesh:
            col = col_layout.column(align=True)
            col.prop(addon_prefs, 'FinishedColor')
            col.prop(addon_prefs, 'UnFinishedColor')

            col_layout.prop(addon_prefs, 'FlippedColor')
            col_layout.prop(addon_prefs, 'ExcludedColor')
            col_layout.prop(addon_prefs, 'UvOverlappedColor')
            col_layout.prop(addon_prefs, 'UvNoSyncColor')

            if not b_is_UV:
                col_layout.prop(addon_prefs, 'TrimColorsAlpha')

        if b_is_object:
            if b_is_UV:
                col = col_layout.column(align=True)

                b_are_object_points_displayed = addon_prefs.UvObjectPointsDisplay

                col.prop(addon_prefs, 'UvObjectPointsDisplay')

                r = col.split(factor=1.5/4)
                r.separator()
                r.label(text='UV Object Active')
                col.prop(addon_prefs, 'UvObjectActiveColor', text='Fill Color')
                if b_are_object_points_displayed:
                    col.prop(addon_prefs, 'UvObjectActivePoint', text='Vertex Color')
                r = col.split(factor=1.5/4)
                r.separator()
                r.label(text='UV Object Inactive')
                col.prop(addon_prefs, 'UvObjectInactiveColor', text='Fill Color')
                if b_are_object_points_displayed:
                    col.prop(addon_prefs, 'UvObjectInactivePoint', text='Vertex Color')

        col = col_layout.column(align=True)
        col.prop(addon_prefs, 'draw_label_font_size')
        col.prop(addon_prefs, 'draw_label_font_color')

        if b_is_editmesh:
            if not b_is_UV:
                col_layout.prop(p_scene.zen_uv.ui, 'draw_stretched_modal')

            col_layout.separator()
            col = col_layout.column(align=True)
            addon_prefs.td_draw.draw(col, context)

            col_layout.separator()
            col = col_layout.column(align=True)
            addon_prefs.uv_borders_draw.draw(col, context)


class ZUV_PT_TdDrawProperties(bpy.types.Panel):
    bl_idname = "ZUV_PT_TdDrawProperties"
    bl_label = "Texel Density Display Properties"
    bl_context = "__POPUP__"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_ui_units_x = 16

    def draw(self, context: bpy.types.Context):
        ''' @Draw Texel Density Display Properties '''
        addon_prefs = get_prefs()
        layout = self.layout

        wm = context.window_manager
        prop_with_icon(layout, wm.zen_uv.draw_props, 'draw_auto_update', 'FILE_REFRESH', s_icon_operator_id='wm.zuv_draw_update')

        col = layout.column(align=True)
        col.use_property_split = True
        addon_prefs.td_draw.draw(col, context)


class ZUV_OT_WMDrawUpdate(bpy.types.Operator):
    bl_idname = 'wm.zuv_draw_update'
    bl_label = 'Update Draw System'

    bl_description = """Update Zen UV draw system cache
* Shift+Click - Enable 'Auto Update Draw' option"""

    bl_options = {'REGISTER'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        if event.shift:
            wm.zen_uv.draw_props.draw_auto_update = True
            return {'FINISHED'}

        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        b_is_uv = context.space_data.type == 'IMAGE_EDITOR'
        if b_is_uv:
            update_all_gizmos_UV(context, force=True)
        else:
            update_all_gizmos_3D(context, force=True)

        return {'FINISHED'}
