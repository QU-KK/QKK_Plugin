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
from bpy_extras import view3d_utils
import gpu

from timeit import default_timer as timer

from mathutils import Vector, Matrix

from .view3d_pos_sca import ZuvGizmoPosSca
from ZenUV.ops.event_service import get_blender_event
from ZenUV.utils.vlog import Log
from ZenUV.utils.blender_zen_utils import ZenPolls


# Area Pointer must be a key
t_gizmo_line = {}


class ZUV_GGT_2DVTransformScale(bpy.types.GizmoGroup):
    bl_idname = "ZUV_GGT_2DVTransformScale"
    bl_label = "Transform (Scale)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SHOW_MODAL_ALL'}

    tool_mode = 'SCALE'

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return ZuvGizmoPosSca.poll_by_tool_mode_and_mesh(context, cls.tool_mode)

    def setup(self, context: bpy.types.Context):
        self.mpr_line = self.gizmos.new("VIEW2D_GT_zenuv_transform_line")
        self.mpr_line.color = 0.0, 1.0, 0.0
        self.mpr_line.alpha = 1.0
        self.mpr_line.color_highlight = 0, 1.0, 1.0
        self.mpr_line.alpha_highlight = 1
        self.mpr_line.use_draw_value = True
        self.mpr_line.use_draw_scale = False
        self.mpr_line.use_select_background = False
        self.mpr_line.use_event_handle_all = False
        self.mpr_line.use_grab_cursor = False
        self.mpr_line.hide_select = True
        self.mpr_line.use_draw_self_line = True
        self.mpr_line.hide = True

        t_gizmo_line[context.area.as_pointer()] = self.mpr_line


class ZUV_GGT_3DVTransformScale(bpy.types.GizmoGroup, ZuvGizmoPosSca):
    bl_idname = "ZUV_GGT_3DVTransformScale"
    bl_label = "Transform (Scale)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {
        '3D', 'PERSISTENT', 'SHOW_MODAL_ALL'
    } if bpy.app.version < (3, 3, 0) else {
        '3D', 'PERSISTENT', 'TOOL_FALLBACK_KEYMAP', 'SHOW_MODAL_ALL'
    }

    tool_mode = 'SCALE'

    pivot_prop = 'zen_uv.ui.view3d_tool.scale_island_pivot'

    def setup(self, context):
        super().setup(context)

        self.mpr_up.draw_style = 'BOX'
        self.mpr_right.draw_style = 'BOX'

    def _create_up_right(self):
        self.mpr_up = self.gizmos.new("VIEW3D_GT_zenuv_trim_scale")
        self.mpr_up.color = 0.0, 1.0, 0.0
        self.mpr_up.alpha = 0.0
        self.mpr_up.color_highlight = 0, 1.0, 1.0
        self.mpr_up.alpha_highlight = 0.0

        self.mpr_right = self.gizmos.new("VIEW3D_GT_zenuv_trim_scale")
        self.mpr_right.color = 1.0, 0.0, 0.0
        self.mpr_right.alpha = 0.0
        self.mpr_right.color_highlight = 1.0, 0, 1.0
        self.mpr_right.alpha_highlight = 0.0

        self.mpr_up_fake = self.gizmos.new("GIZMO_GT_arrow_3d")
        self.mpr_up_fake.color = 0.0, 1.0, 0.0
        self.mpr_up_fake.alpha = 0.5
        self.mpr_up_fake.color_highlight = 0, 1.0, 1.0
        self.mpr_up_fake.alpha_highlight = 1
        self.mpr_up_fake.line_width = 3.0
        self.mpr_up_fake.hide_select = True
        self.mpr_up_fake.draw_style = 'BOX'

        self.mpr_right_fake = self.gizmos.new("GIZMO_GT_arrow_3d")
        self.mpr_right_fake.color = 1.0, 0.0, 0.0
        self.mpr_right_fake.alpha = 0.5
        self.mpr_right_fake.color_highlight = 1.0, 0, 1.0
        self.mpr_right_fake.alpha_highlight = 1
        self.mpr_right_fake.line_width = 3.0
        self.mpr_right_fake.hide_select = True
        self.mpr_right_fake.draw_style = 'BOX'

    def _create_dir(self):
        self.mpr_dir = self.gizmos.new("VIEW3D_GT_zenuv_trim_scale")
        self.mpr_dir.color = 1.0, 1.0, 0.0
        self.mpr_dir.alpha = 0.0
        self.mpr_dir.color_highlight = 0.0, 0.0, 1.0
        self.mpr_dir.alpha_highlight = 0.0
        self.mpr_dir.scale_basis = 1.2
        self.mpr_dir.line_width = 1.0
        self.mpr_dir.use_draw_scale = True
        self.mpr_dir.draw_style = 'CIRCLE'

        self.mpr_dir_fake = self.gizmos.new("GIZMO_GT_move_3d")
        self.mpr_dir_fake.color = 1.0, 1.0, 0.0
        self.mpr_dir_fake.alpha = 0.5
        self.mpr_dir_fake.color_highlight = 0.0, 0.0, 1.0
        self.mpr_dir_fake.alpha_highlight = 1
        self.mpr_dir_fake.scale_basis = 1.2 if 'SCALE' == self.tool_mode else 0.2
        self.mpr_dir_fake.line_width = 3.0
        self.mpr_dir_fake.hide_select = True

    def _setup_dragged(self, context: bpy.types.Context):

        # Do not change Gizmo Order !

        self._create_up_right()

        self._create_dir()

        self.tool_region = Vector((0, 0))
        self.tool_dir_increase = False
        self.tool_scale = 1.0
        self.tool_event_pt = Vector((0, 0))
        self.tool_offset_value = Vector((1.0, 1.0))

    def _setup_matrices_final(self, context: bpy.types.Context):
        super()._setup_matrices_final(context)

        if not self.are_gizmos_modal():
            rgn = context.region
            rgn3d = context.space_data.region_3d

            v_pos = self.mpr_dir.matrix_world.to_translation()

            self.tool_offset_dir = Vector()
            self.tool_offset_value = Vector((1.0, 1.0))

            self.tool_region = view3d_utils.location_3d_to_region_2d(rgn, rgn3d, v_pos, default=Vector())
            self.tool_event_pt = Vector((0, 0))
            self.tool_event_length = 0.0
            self.tool_dir_increase = False
            self.tool_scale = 1.0
            self.tool_x_negative = False
            self.tool_y_negative = False
            self.tool_angle_x = 0.0
            self.tool_angle_y = 0.0

            self.mpr_right_fake.matrix_basis = self.mpr_right.matrix_basis
            self.mpr_up_fake.matrix_basis = self.mpr_up.matrix_basis
            self.mpr_dir_fake.matrix_basis = self.mpr_dir.matrix_basis

    def _setup_trimsheet_colors(self, context: bpy.types.Context, p_trimsheet, p_active_color):
        super()._setup_trimsheet_colors(context, p_trimsheet, p_active_color)

        def set_color(prop_name):
            p_gizmo = getattr(self, f'mpr_{prop_name}')  # type: bpy.types.Gizmo
            p_fake_gizmo = getattr(self, f'mpr_{prop_name}_fake')  # type: bpy.types.Gizmo
            if self.are_gizmos_modal():
                p_fake_gizmo.color = ZuvTrimScaleGizmo.INACTIVE_COLOR
                p_fake_gizmo.alpha = 0.75
            elif p_gizmo.is_highlight:
                p_fake_gizmo.color = p_gizmo.color_highlight
                p_fake_gizmo.alpha = 1.0
            else:
                p_fake_gizmo.color = p_gizmo.color
                p_fake_gizmo.alpha = 0.5

        set_color('up')
        set_color('right')
        set_color('dir')

        try:
            p_2d_line = t_gizmo_line.get(context.area.as_pointer(), None)
            if p_2d_line is None:
                raise RuntimeError('Scale 2d line must not be zero!')

            p_2d_line.hide = (
                (
                    not self.mpr_dir.is_modal and
                    not self.mpr_up.is_modal and
                    not self.mpr_right.is_modal) or
                self.tool_event_pt[:] == (0, 0))

            if not p_2d_line.hide:
                p_2d_line.start = self.tool_region
                p_2d_line.end = self.tool_event_pt
                p_2d_line.color = (0, 0, 0) if self.tool_dir_increase else (0, 0, 0)
        except Exception:
            pass

        self.setup_operator_pivot(context)

    def _do_scale(self, axis='XY'):
        if self.tool_scale == 0:
            return

        ctx = bpy.context

        p_event = get_blender_event(force=True)
        self.tool_event_pt = Vector(
            (p_event.get('mouse_region_x', 0.0), p_event.get('mouse_region_y', 0.0)))

        new_axis = self.tool_event_pt - self.tool_region  # type: Vector
        if new_axis.length == 0:
            return

        if 'XY' in axis:
            tool_event_init_pt = self.mpr_dir.init_mouse_rgn
        elif 'X' in axis:
            tool_event_init_pt = self.mpr_right.init_mouse_rgn
        elif 'Y' in axis:
            tool_event_init_pt = self.mpr_up.init_mouse_rgn
        else:
            raise RuntimeError('TOOL SCALE: Must not come here!')

        tool_event_init_axis = tool_event_init_pt - self.tool_region  # type: Vector
        tool_event_init_length = tool_event_init_axis.length

        if tool_event_init_length == 0:
            return

        new_length = new_axis.length
        new_increase = new_length >= self.tool_event_length

        self.tool_dir_increase = new_increase
        self.tool_event_length = new_length

        d_ratio = new_length / tool_event_init_length

        d_offset = (d_ratio - self.tool_scale) / self.tool_scale

        d_new_scale = self.tool_scale * (1.0 + d_offset)

        if d_new_scale != 0.0:
            self.tool_scale = d_new_scale

            p_act_obj = ctx.active_object
            if p_act_obj and p_act_obj.type == 'MESH':

                if p_event.get('shift'):
                    d_offset *= 0.1

                x_offset = 1.0 + d_offset if 'X' in axis else 1.0
                y_offset = 1.0 + d_offset if 'Y' in axis else 1.0

                if ctx.scene.zen_uv.tr_space_mode == "TEXTURE":
                    try:
                        if 'X' in axis:
                            x_offset = 1 / x_offset
                        if 'Y' in axis:
                            y_offset = 1 / y_offset
                    except ZeroDivisionError:
                        pass

                res = Vector((x_offset, y_offset))
                self._do_offset(ctx, res)
                self.drag_started = True

    def _do_offset(self, context: bpy.types.Context, v_offset: Vector):
        self.tool_offset_value *= v_offset

        b_executed = False

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_Tr3DVScaleInTrim

        # prevent endless undo chain
        wm = context.window_manager
        if self.drag_started and wm.operators:
            op = wm.operators[-1]
            if isinstance(op, ZUV_OT_Tr3DVScaleInTrim):


                op.allow_negative = False
                op.is_offset_mode = True
                op.op_tr_scale_positive_only = v_offset.to_tuple()
                op.scale_offset = self.tool_offset_value[:]

                op.execute(context)

                context.area.tag_redraw()

                b_executed = True

        # First time call from dragging
        if not b_executed:


            self.switch_blender_overlay(context, False)

            # call with undo
            bpy.ops.view3d.zenuv_scale_in_trim(
                'INVOKE_DEFAULT', True,
                allow_negative=False, op_tr_scale_positive_only=v_offset.to_tuple(),
                is_offset_mode=True,
                scale_offset=self.tool_offset_value[:])

        s_info = ''

        op_props = wm.operator_properties_last(ZUV_OT_Tr3DVScaleInTrim.bl_idname)
        if op_props:
            if op_props.info_message:
                s_info = '    Info: ' + op_props.info_message

        context.area.header_text_set(
            f'Scale: {self.tool_offset_value.x:.4f}, {self.tool_offset_value.y:.4f}{s_info}')

        # HACK: we stopped receive refresh message so here is the only place to get it
        if ZenPolls.version_since_4_2_0:
            self.do_refresh(context)

    def move_get_cb_up(self):
        return self.tool_offset

    def move_get_cb_right(self):
        return self.tool_offset

    def move_set_cb_right(self, value):
        if self.tool_offset != value:
            self.tool_offset = value

            self._do_scale(axis='X')

    def move_set_cb_up(self, value):
        if self.tool_offset != value:
            self.tool_offset = value

            self._do_scale(axis='Y')

    def move_set_cb_dir(self, value):
        p_vec = Vector(value)
        if self.tool_offset_dir != p_vec:
            self.tool_offset_dir = p_vec

            self._do_scale()


class ZuvTrimScaleGizmo(bpy.types.Gizmo):
    bl_idname = "VIEW3D_GT_zenuv_trim_scale"
    bl_target_properties = (
        {"id": "offset", "type": 'FLOAT', "array_length": 3},
    )

    __slots__ = (
        "init_mouse",
        "init_mouse_rgn",
        "init_value",
        "init_mtx_world",
        "draw_style",
        "last_update",
    )

    INACTIVE_COLOR = (0.5, 0.5, 0.5)

    def do_draw_box_handle(self, context: bpy.types.Context, matrix: Matrix, select_id=-1):
        mtx_scale_line = Matrix.Diagonal((0.01, 0.01, 0.5)).to_4x4()
        mtx_pos = Matrix.Translation((0, 0, 0.5))
        mtx_line = mtx_pos @ mtx_scale_line
        self.draw_preset_box(matrix @ mtx_line, select_id=select_id)

        mtx_scale = Matrix.Diagonal((0.05, 0.05, 0.05)).to_4x4()
        ui_scale = context.preferences.system.ui_scale
        mtx_pos = Matrix.Translation((0, 0 * ui_scale, 1))
        mtx_box = mtx_pos @ mtx_scale
        self.draw_preset_box(matrix @ mtx_box, select_id=select_id)

    def draw(self, context):
        was_color = self.color.copy()

        gpu.state.blend_set('ALPHA')

        if self.is_modal:
            self.color = self.INACTIVE_COLOR
            if self.draw_style == 'ARROW':
                self.draw_preset_arrow(self.init_mtx_world)
            elif self.draw_style == 'CIRCLE':
                self.draw_preset_arrow(self.init_mtx_world)
            else:
                self.do_draw_box_handle(context, self.init_mtx_world)
        else:
            self.color = self.color_highlight if self.is_highlight else self.color
            if self.draw_style == 'ARROW':
                self.draw_preset_arrow(self.matrix_world)
            elif self.draw_style == 'CIRCLE':
                self.draw_preset_circle(
                    self.matrix_world
                )
            else:
                self.do_draw_box_handle(context, self.matrix_world)

        gpu.state.blend_set('NONE')

        self.color = was_color

    def draw_select(self, context, select_id):
        if self.draw_style == 'ARROW':
            self.draw_preset_arrow(self.matrix_world, select_id=select_id)
        elif self.draw_style == 'CIRCLE':
            self.draw_preset_circle(self.matrix_world, select_id=select_id)
        else:
            self.do_draw_box_handle(context, self.matrix_world, select_id=select_id)

    def setup(self):
        if not hasattr(self, 'draw_style'):
            self.init_mtx_world = Matrix()
            self.draw_style = 'ARROW'
            self.last_update = 0
            self.init_mouse_rgn = Vector((0, 0))
            self.init_value = Vector()

    def invoke(self, context, event: bpy.types.Event):
        self.init_mouse = Vector((event.mouse_x, event.mouse_y, 0))
        self.init_value = Vector(self.target_get_value("offset"))
        self.init_mtx_world = self.matrix_world.copy()
        self.last_update = 0
        self.init_mouse_rgn = Vector((event.mouse_region_x, event.mouse_region_y))
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        context.area.header_text_set(None)
        if cancel:
            self.target_set_value("offset", self.init_value)

    def modal(self, context: bpy.types.Context, event: bpy.types.Event, tweak):
        # Filter with 60 FPS
        if timer() - self.last_update >= 1/60:
            delta = self.init_mouse - Vector((event.mouse_x, event.mouse_y, 0))
            value = self.init_value - delta
            self.target_set_value("offset", value[:])
            self.last_update = timer()
        return {'RUNNING_MODAL'}
