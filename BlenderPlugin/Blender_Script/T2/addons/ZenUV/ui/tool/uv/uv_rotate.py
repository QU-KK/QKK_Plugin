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

# Copyright 2023, Alex Zhornyak

import bpy
from mathutils import Matrix, Vector

import math

from .uv_base import ZuvUVGizmoBase

from ZenUV.ops.event_service import get_blender_event
from ZenUV.utils.vlog import Log
from ZenUV.utils.blender_zen_utils import ZenPolls


class ZUV_GGT_UVTransformRot(bpy.types.GizmoGroup, ZuvUVGizmoBase):
    bl_idname = "ZUV_GGT_UVTransformRot"
    bl_label = "Transform (Rotate)"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'WINDOW'
    bl_options = {
        'PERSISTENT', 'SHOW_MODAL_ALL',
    } if bpy.app.version < (3, 3, 0) else {
        'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL',
    }

    tool_mode = {'ROTATE'}

    pivot_prop = 'zen_uv.ui.uv_tool.rotate_island_pivot'

    # INHERITED METHODS

    def _check_object_data_after_refresh(self, context: bpy.types.Context):
        if self.is_trimsheet_modified(context):
            self.setup_position(context, update_drag=False)

        self.enqueue_gizmo_check(context)

    def _setup_dragged(self, context: bpy.types.Context):
        self.mpr_rot = self.gizmos.new("GIZMO_GT_move_3d")
        self.mpr_rot.color = 0.0, 1.0, 0.0
        self.mpr_rot.alpha = 0.5
        self.mpr_rot.color_highlight = 0, 1.0, 1.0
        self.mpr_rot.alpha_highlight = 1
        self.mpr_rot.line_width = 3
        self.mpr_rot.use_draw_value = True
        self.mpr_rot.scale_basis = 1.2
        self.mpr_rot.use_select_background = False
        self.mpr_rot.use_event_handle_all = False
        self.mpr_rot.use_grab_cursor = False

        self.mpr_rot_line = self.gizmos.new("UV_GT_zenuv_transform_line")
        self.mpr_rot_line.color = 0.0, 0.0, 0.0
        self.mpr_rot_line.alpha = 1.0
        self.mpr_rot_line.use_draw_value = True
        self.mpr_rot_line.use_draw_scale = False
        self.mpr_rot_line.use_select_background = False
        self.mpr_rot_line.use_event_handle_all = False
        self.mpr_rot_line.use_grab_cursor = False
        self.mpr_rot_line.hide_select = True
        self.mpr_rot_line.use_draw_self_line = True

        self.gizmo_drag[self.mpr_rot] = False

    def _setup_matrices_final(self, context: bpy.types.Context):
        if super()._setup_matrices_final(context):
            if not self.are_gizmos_modal() and self.is_uv_selected():
                rgn2d = context.region.view2d

                x, y, = rgn2d.view_to_region(self.uv_selection_center.x, self.uv_selection_center.y, clip=False)

                mtx = Matrix.Translation(Vector((x, y, 0)))
                self.mpr_rot.matrix_basis = mtx
                self.tool_offset = Vector((0, 0, 0))
                self.angle = None

                self.angle_offset = 0

                self.mouse_init = Vector((x, y))

                def direction_get_cb():
                    return self.tool_offset

                def direction_set_cb(value):
                    p_vec = Vector(value)
                    if math.fabs((self.tool_offset - p_vec).length) > 0.01:

                        ctx = bpy.context

                        p_event = get_blender_event(force=True)
                        v_mouse = Vector((p_event.get('mouse_region_x', 0.0), p_event.get('mouse_region_y', 0.0)))

                        self.mpr_rot_line.start = self.mouse_init
                        self.mpr_rot_line.end = v_mouse

                        axis = (v_mouse - self.mouse_init).normalized()
                        if axis.length == 0:
                            return

                        angle = axis.angle_signed(Vector((0, 1)))

                        # print(math.degrees(angle), math.degrees(self.angle) if self.angle is not None else 0)

                        if self.angle is None:
                            self.angle = angle
                            p_angle = 0
                        else:
                            p_angle = angle - self.angle
                            self.angle = angle

                        if p_angle > math.pi:
                            p_angle = -1 * (2 * math.pi - p_angle)
                        elif p_angle < -math.pi:
                            p_angle = -1 * ((-2 * math.pi) - p_angle)

                        self.tool_offset = p_vec

                        if p_angle != 0 and self.is_uv_selected():
                            p_act_obj = ctx.active_object
                            if p_act_obj and p_act_obj.type == 'MESH':
                                self._do_offset(context, -math.degrees(p_angle))
                                self.drag_started = True

                self.mpr_rot.target_set_handler("offset", get=direction_get_cb, set=direction_set_cb)
                return True
        return False

    def _reset_dragged(self, context: bpy.types.Context):
        self.tool_offset = Vector()
        self.drag_started = False
        context.area.header_text_set(None)

        self.setup_position(context)

    def _setup_dragged_position(self, context: bpy.types.Context):
        self.tool_offset = Vector()
        self.drag_started = False

    def _do_offset(self, context: bpy.types.Context, dir_angle: float):
        # prevent endless undo chain
        wm = bpy.context.window_manager

        self.angle_offset += dir_angle

        b_executed = False

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_TrUVRotateInTrim

        if self.drag_started and wm.operators:
            op = wm.operators[-1]
            if isinstance(op, ZUV_OT_TrUVRotateInTrim):
                op.tr_rot_inc_full_range = dir_angle
                op.is_offset_mode = True
                op.rotate_offset_rad = math.radians(self.angle_offset)
                op.execute(context)
                b_executed = True

        if not b_executed:


            # call with undo
            bpy.ops.uv.zenuv_rotate_in_trim(
                'INVOKE_DEFAULT', True,
                tr_rot_inc_full_range=dir_angle,
                is_offset_mode=True,
                rotate_offset_rad=math.radians(self.angle_offset)
            )

        s_info = ''

        op_props = wm.operator_properties_last(ZUV_OT_TrUVRotateInTrim.bl_idname)
        if op_props:
            if op_props.info_message:
                s_info = '    Info: ' + op_props.info_message

        context.area.header_text_set(f'Rotate: {self.angle_offset:.4f}°{s_info}')

        # HACK: we stopped receive refresh message so here is the only place to get it
        if ZenPolls.version_since_4_2_0:
            self.do_refresh(context)

    def _setup_trimsheet_colors(self, context: bpy.types.Context, p_trimsheet, p_active_color):
        super()._setup_trimsheet_colors(context, p_trimsheet, p_active_color)

        b_is_mesh_selected = self.poll_edit_mesh_selected(context)

        b_require_hide = not b_is_mesh_selected or self.is_hide_required(context)

        self.mpr_rot.hide = b_require_hide
        self.mpr_rot_line.hide = not self.mpr_rot.is_modal

        if not self.mpr_rot.hide:
            self.mpr_rot.alpha_highlight = 0.0 if self.mpr_rot.is_modal else 1.0

        self.setup_operator_pivot(context)
