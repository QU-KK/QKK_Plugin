import math

import bpy

from . import continuous_rotation as _continuous_rotation
from . import utils

_mouse_position = 0.0


def get_mouse_position():
    return _mouse_position


def set_mouse_position(value):
    global _mouse_position
    _mouse_position = value


_initial_angle = 0.0


def get_initial_angle():
    return _initial_angle


def set_initial_angle(value):
    global _initial_angle
    _initial_angle = value


_angle_increment = 0.0


def get_angle_increment():
    return _angle_increment


def set_angle_increment(value):
    global _angle_increment
    _angle_increment = value


class HDR_OT_hdr_rotation(bpy.types.Operator):
    bl_idname = "hdr.hdr_rotation"
    bl_label = "HDR_Rotation"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        set_mouse_position((event.mouse_region_x, event.mouse_region_y)[0])
        set_initial_angle(
            context.screen.areas[2].spaces[0].shading.studiolight_rotate_z
        )
        if context.window:
            context.window.cursor_modal_set("SCROLL_X")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        result = self._modal(context, event)
        if result is None:
            return {"RUNNING_MODAL"}
        if not result & {"RUNNING_MODAL", "PASS_THROUGH"}:
            self._end(context)
        return result

    def _modal(self, context, event):
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return {"CANCELLED"}
        print(
            str(
                math.radians(
                    (
                        get_mouse_position()
                        - (event.mouse_region_x, event.mouse_region_y)[0]
                    )
                    * 0.5
                )
                + (get_initial_angle() + get_angle_increment())
            )
        )
        context.screen.areas[2].spaces[0].shading.studiolight_rotate_z = math.radians(
            (get_mouse_position() - (event.mouse_region_x, event.mouse_region_y)[0])
            * 0.5
        ) + (get_initial_angle() + get_angle_increment())
        _continuous_rotation.continuous_rotation(180.0, context=context)
        _continuous_rotation.continuous_rotation(-180.0, context=context)
        if event.type == "RIGHTMOUSE" and event.value == "RELEASE":
            return {"FINISHED"}

    def _end(self, context):
        if context.window:
            context.window.cursor_modal_restore()

    def cancel(self, context):
        self._end(context)


def hdr_rotation(angle):
    pass


def register():
    utils.add_shortcut(
        "3D View", "VIEW_3D", "hdr.hdr_rotation", "RIGHTMOUSE", ctrl=True, shift=True
    )
