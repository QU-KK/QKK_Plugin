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

# Copyright 2023, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy

import math
from timeit import default_timer as timer

from ZenUV.sticky_uv_editor.controls import StkUvEditorSolver
from ZenUV.utils.blender_zen_utils import ZenPolls, show_message_box, get_ui_region_width, get_tools_region_width
from ZenUV.ui.labels import ZuvLabels
from ZenUV.prop.zuv_preferences import get_prefs


_solver = None
_was_context = None


def zenuv_handle_sticky_solver():
    if _solver is None:
        return

    if _solver.is_open_separate_window:
        _solver.create_uv_editor(new_window=True)
        return None

    result = _solver.close_uv_editor()

    if result:
        return None
    elif result is None:
        message = _solver.analyser.message if _solver.analyser.message != '' else "Failed to figure out current layout!"
        show_message_box(
            title="Sticky UV Editor",
            message=message,
            icon="ERROR")
        return None
    else:
        _solver.init_state(_was_context)
        _solver.create_uv_editor(new_window=False)

    return None


def zenuv_handle_snooper():
    if _solver is None:
        return

    if _solver.warp_it == 0:

        if math.fabs(_solver.view3d_area.width - (_solver.warp_was_width + math.fabs(_solver.delta))) < 2.0:
            return None

    _solver.context["window"].cursor_warp(_solver.warp_x, _solver.warp_y)

    _solver.warp_it += 1

    # no need to wait more than 1 sec, something wrong
    if timer() - _solver.warp_timer > 1.0:
        return None

    if ZenPolls.version_since_3_2_0:
        with bpy.context.temp_override(**_solver.context):
            if not bpy.ops.screen.area_move.poll():
                return 0.001

            # should poll now
            bpy.ops.screen.area_move(x=_solver.warp_x, y=_solver.warp_y, delta=_solver.delta)
    else:
        if not bpy.ops.screen.area_move.poll(_solver.context, 'INVOKE_REGION_WIN'):
            return 0.001

        # should poll now
        bpy.ops.screen.area_move(x=_solver.warp_x, y=_solver.warp_y, delta=_solver.delta)

    w = _solver.context["window"]
    w.cursor_warp(_solver.imp_x, _solver.imp_y)
    return None


class StkShaderEditorSolver(StkUvEditorSolver):
    def _find_view3d_area(self):
        if self.active.ui_type == "VIEW_3D":
            self.view3d_area = self.active
            self.v_3d_idx = self.active_index
        else:
            if self.active.ui_type == "ShaderNodeTree":
                if self.prefs_side_left:
                    v_3d_idx = self.active_index + 1
                elif not self.prefs_side_left:
                    v_3d_idx = self.active_index - 1
            if self._index_in_list(v_3d_idx) and self.areas[v_3d_idx].ui_type == "VIEW_3D":
                self.view3d_area = self.areas[v_3d_idx]
            self.v_3d_idx = v_3d_idx

    def close_uv_editor(self):
        if not self._is_init():
            return False
        if self.side not in {"LEFT", "RIGHT"}:
            print("Zen UV: class StkShaderEditorSolver solver side not in ['LEFT', 'RIGHT']")
            return None

        if 'VIEW_3D' not in [area.ui_type for area in self.input_areas]:
            self.analyser.message_type = 'WARNING'
            self.analyser.message = "It's impossible to close the last UV Editor in a layout without a 3D View."
            return None

        if self.app_is_3:
            if self.prefs_side_left and self.area_on_left and self.area_on_left.ui_type == "ShaderNodeTree":
                # NOTE: how to save ?
                # self.stk_props.save_from_area(self.context['scene'], self.area_on_left)
                ctx = self.context.copy()
                ctx["area"] = self.area_on_left
                self._warp()
                if ZenPolls.version_since_3_2_0:
                    ctx["region"] = self.area_on_left.regions[0]
                    with bpy.context.temp_override(**ctx):
                        bpy.ops.screen.area_close()
                else:
                    bpy.ops.screen.area_close(ctx)

                return True
            elif not self.prefs_side_left and self.area_on_right and self.area_on_right.ui_type == "ShaderNodeTree":
                # NOTE:
                # self.stk_props.save_from_area(self.context['scene'], self.area_on_right)
                ctx = self.context.copy()
                ctx["area"] = self.area_on_right
                self._warp()
                if ZenPolls.version_since_3_2_0:
                    ctx["region"] = self.area_on_right.regions[0]
                    with bpy.context.temp_override(**ctx):
                        bpy.ops.screen.area_close()
                else:
                    bpy.ops.screen.area_close(ctx)
                return True
            return False
        else:
            # Close UV Editor In 2.9
            if self.prefs_side_left and self.area_on_left and self.area_on_left.ui_type == "ShaderNodeTree":
                # NOTE:
                # self.stk_props.save_from_area(self.context['scene'], self.area_on_left)
                if self.active.ui_type == "ShaderNodeTree":
                    self._close_UVE_on_left(self.view3d_area)
                else:
                    self._close_UVE_on_left(self.active)
                self._force_update_layout(self.view3d_area)
                return True

            elif not self.prefs_side_left and self.area_on_right and self.area_on_right.ui_type == "ShaderNodeTree":
                # NOTE:
                # self.stk_props.save_from_area(self.context['scene'], self.area_on_right)
                self._close_UVE_on_right(self.area_on_right)
                self._force_update_layout(self.area_on_right)
                return True
            else:
                return False

    def create_uv_editor(self, new_window=False):
        """ Create UV Editor on side """
        if not self._is_init():
            return False
        if not new_window:
            if ZenPolls.version_since_3_2_0:
                with bpy.context.temp_override(**self.context):
                    bpy.ops.screen.area_split(direction='VERTICAL', factor=0.5)
            else:
                bpy.ops.screen.area_split(self.context, direction='VERTICAL', factor=0.5)

        if self.prefs_side_left:
            for area in reversed(self.input_areas):
                if area.ui_type == 'VIEW_3D':
                    uv_area = area
                    break
        else:
            uv_area = self.active

        if uv_area:

            init_ui_type = self.active.ui_type
            uv_area.ui_type = 'ShaderNodeTree'

            self.set_stk_area_props(uv_area)

            self.set_stk_area_mode(uv_area)

            if new_window:
                override = self.context.copy()
                override['area'] = uv_area
                override['region'] = uv_area.regions[0]

                if ZenPolls.version_since_3_2_0:
                    with bpy.context.temp_override(**override):
                        bpy.ops.screen.area_dupli('INVOKE_DEFAULT')
                else:
                    bpy.ops.screen.area_dupli(override, 'INVOKE_DEFAULT')
                self.active.ui_type = init_ui_type

    def set_stk_area_props(self, uv_area):
        # we must save it from addon preferences
        pass


class ZUV_StickyShaderEditor(bpy.types.Operator):
    bl_idname = "wm.sticky_shader_editor"
    bl_label = "Sticky Shader Editor"
    bl_options = {'REGISTER'}

    ui_button: bpy.props.BoolProperty(default=False)

    desc: bpy.props.StringProperty(
        name="Description",
        default=ZuvLabels.STK_UV_ED_OPERATOR_DESC,
        options={'HIDDEN'}
    )

    @classmethod
    def description(cls, context, properties):
        cls.desc = ZuvLabels.STK_UV_ED_OPERATOR_DESC.replace('UV Editor', 'Shader Editor')
        return cls.desc

    @classmethod
    def poll(self, context):
        return context.area and context.area.ui_type in ['ShaderNodeTree', 'VIEW_3D']

    def modal(self, context, event):
        if event.type == "LEFTMOUSE" and event.value == 'RELEASE':
            return self.execute(context)
        elif event.type not in {'MOUSEMOVE', 'TIMER', 'TIMER_REPORT', 'INBETWEEN_MOUSEMOVE'}:
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if event.ctrl and event.shift:
            if event.type == "LEFTMOUSE":
                bpy.ops.ops.zenuv_show_prefs(tabs="STK_UV_EDITOR")
                return {'FINISHED'}

        self.mouse_x = event.mouse_x
        self.mouse_y = event.mouse_y
        self.is_open_separate_window = False
        if event.ctrl:
            if event.type == "LEFTMOUSE":
                self.is_open_separate_window = True

        if event.type == "LEFTMOUSE" and event.value == 'PRESS':
            if context.window_manager.modal_handler_add(self):
                return {'RUNNING_MODAL'}
        else:
            return self.execute(context)

        return {'CANCELLED'}

    def execute(self, context):
        if (bpy.app.timers.is_registered(zenuv_handle_sticky_solver) or
                bpy.app.timers.is_registered(zenuv_handle_snooper)):
            self.report({'WARNING'},
                        "Sticky UV Editor: Previous operation was not finished yet!")
            return {'CANCELLED'}

        if context.window.screen.show_fullscreen:
            self.report({'WARNING'},
                        "Sticky UV Editor: Fullscreen mode is not supported!")
            return {'CANCELLED'}

        global _solver

        _solver = StkShaderEditorSolver((self.mouse_x, self.mouse_y), self.ui_button)
        _solver.is_open_separate_window = self.is_open_separate_window
        _solver.operator = self

        global _was_context
        _was_context = context.copy()

        if not _solver.init_state(_was_context):
            _solver = None
            print("Sticky UV Editor: Failed to init.")
            show_message_box(
                title="Sticky UV Editor",
                message="Failed to figure out current layout!",
                icon="ERROR")
            return {'CANCELLED'}

        bpy.app.timers.register(zenuv_handle_sticky_solver)

        return {'FINISHED'}


class ZUV_StickyShaderEditor_UI_Button(bpy.types.GizmoGroup):
    bl_idname = "StickyShaderEditor_UI_Button"
    bl_label = "Sticky Shader Editor UI Button"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        addon_prefs = get_prefs()
        return (addon_prefs.show_ui_button) and \
            (not context.window.screen.show_fullscreen)

    def draw_prepare(self, context):
        addon_prefs = get_prefs()
        ui_scale = context.preferences.system.ui_scale
        widget_size = self.foo_gizmo.scale_basis * ui_scale
        correction = 2

        if addon_prefs.uv_editor_side == 'RIGHT':
            n_panel_width = get_ui_region_width(context)
            base_position = context.region.width - n_panel_width - widget_size - correction
            props_influence = (100 - addon_prefs.stk_ed_button_h_position) * 0.01
            self.foo_gizmo.matrix_basis[0][3] = base_position * props_influence
        else:
            tools_width = get_tools_region_width(context)
            base_position = tools_width + widget_size + correction
            props_influence = (((context.region.width - base_position) * addon_prefs.stk_ed_button_h_position) / 100)
            self.foo_gizmo.matrix_basis[0][3] = base_position + props_influence

        self.foo_gizmo.matrix_basis[1][3] = context.region.height * addon_prefs.stk_ed_button_v_position * 0.01 - 50

    def setup(self, context):
        mpr = self.gizmos.new("GIZMO_GT_button_2d")
        mpr.show_drag = False
        mpr.icon = 'NODE_MATERIAL'
        mpr.draw_options = {'BACKDROP', 'OUTLINE'}

        mpr.color = 0.0, 0.0, 0.0
        mpr.alpha = 0.5
        mpr.color_highlight = 0.8, 0.8, 0.8
        mpr.alpha_highlight = 0.2

        mpr.scale_basis = (80 * 0.35) / 2  # Same as buttons defined in C
        op = mpr.target_set_operator("wm.sticky_shader_editor")
        op.ui_button = True
        self.foo_gizmo = mpr


classes = (
    ZUV_StickyShaderEditor,
    ZUV_StickyShaderEditor_UI_Button
)


def register():
    print('Starting Zen UV user script...')
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    print('Finishing Zen UV user script...')
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
