import bpy
import os
from mathutils import Vector
from .. import __package__ as package


def preferences() -> dict:
    """Get addon preferences.

    return (dict) - Preferences of the current addon.
    """
    return bpy.context.preferences.addons[package].preferences


def ui_scale() -> float:
    # return dpi() / 72
    return bpy.context.preferences.system.ui_scale


def dpi() -> int:
    # system_preferences = bpy.context.preferences.system
    # retina_factor = getattr(system_preferences, 'pixel_size', 1)
    # return int(system_preferences.dpi * retina_factor)
    return bpy.context.preferences.system.dpi


def scene_unit(value: float, unit_system: str = None, length_unit: str = None) -> str:
    unit_settings = bpy.context.scene.unit_settings
    unit_scale = unit_settings.scale_length

    if unit_system is None:
        unit_system = unit_settings.system
    if length_unit is None:
        length_unit = unit_settings.length_unit

    if length_unit == "MICROMETERS":
        return f"{round((value * unit_scale) * 1e6, None)} μm"
    elif length_unit == "MILLIMETERS":
        return f"{round((value * unit_scale) * 1e3, None)} mm"
    elif length_unit == "CENTIMETERS":
        return f"{round((value * unit_scale) * 1e2, None)} cm"
    elif length_unit == "METERS":
        return f"{round((value * unit_scale), 1)} m"
    elif length_unit == "KILOMETERS":
        return f"{round((value * unit_scale) * 1e-3, 5)} km"
    elif length_unit == "THOU":
        return f"{round((value * unit_scale) * 39370.1, None)} thou"
    elif length_unit == "INCHES":
        return f'{round((value * unit_scale) * 39.3701, 1)} "'
    elif length_unit == "FEET":
        return f"{round((value * unit_scale) * 3.28084, 2)} '"
    elif length_unit == "MILES":
        return f"{round((value * unit_scale) * 0.000621, 6)} mi"
    elif length_unit == "ADAPTIVE":
        if unit_system == "IMPERIAL":
            if unit_scale >= 1607.734:
                return f"{round((value * unit_scale) * 0.000621, 3)} mi"
            elif unit_scale >= 0.3048:
                return f"{round((value * unit_scale) * 3.28084, 2)} '"
            elif unit_scale >= 0.0255:
                return f'{round((value * unit_scale) * 39.3701, 1)} "'
            else:
                return f"{round((value * unit_scale) * 39370.1, 1)} thou"
        elif unit_system == "METRIC":
            if unit_scale >= 1000:
                return f"{round((value * unit_scale) / 1e3, 4)} km"
            elif unit_scale >= 0.999:
                return f"{round((value * unit_scale), 2)} m"
            elif unit_scale >= 0.01:
                return f"{round((value * unit_scale) * 1e2, 1)} cm"
            elif unit_scale >= 0.001:
                return f"{round((value * unit_scale) * 1e3, None)} mm"
            else:
                return f"{round((value * unit_scale) * 1e6, None)} μm"
        else:
            return f"{round(value, 3)}"


def icons_dir(file) -> str:
    """Get icon directory.

    file (str) - Name of the directory.
    """
    return os.path.join(os.path.dirname(file), "../icons/")


def panel(type) -> tuple:
    """Panel in the region.

    type (enum in ['WINDOW', 'HEADER', 'CHANNELS', 'TEMPORARY', 'UI', 'TOOLS', 'TOOL_PROPS', 'PREVIEW', 'HUD', 'NAVIGATION_BAR', 'EXECUTE', 'FOOTER', 'TOOL_HEADER', 'XR']) - Type of the region.
    return (tuple) - Dimension of the region.
    """
    width = 0
    height = 0
    for region in bpy.context.area.regions:
        if region.type == type:
            width = region.width
            height = region.height
    return Vector((width, height))


def collapse_panels(t_panel=False, n_panel=False) -> bool:
    """Collapse all panels.

    t_panel (bool) - Collapse T panel.
    n_panel (bool) - Collapse N panel.
    return (bool) - True if panels were collapsed.
    """
    original_t_panel = False
    original_n_panel = False

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if hasattr(space, "show_region_toolbar"):
                        if hasattr(space, "show_region_ui"):
                            # Returns
                            original_t_panel = space.show_region_toolbar
                            original_n_panel = space.show_region_ui

                        # Sets
                        if t_panel != space.show_region_toolbar:
                            space.show_region_toolbar = t_panel

                        if n_panel != space.show_region_ui:
                            space.show_region_ui = n_panel

    return (original_t_panel, original_n_panel)


def set_cursor(context, cursor):
    """Set the cursor.

    cursor (enum in ['DEFAULT', 'NONE', 'WAIT', 'CROSSHAIR', 'MOVE_X', 'MOVE_Y', 'KNIFE', 'TEXT', 'PAINT_BRUSH', 'PAINT_CROSS', 'DOT', 'ERASER', 'HAND', 'SCROLL_X', 'SCROLL_Y', 'SCROLL_XY', 'EYEDROPPER', 'PICK_AREA', 'STOP', 'COPY', 'CROSS', 'MUTE', 'ZOOM_IN', 'ZOOM_OUT']) – cursor
    """
    context.window.cursor_modal_set(cursor)


def warp_cursor(context, event) -> bool:
    warped = False
    mouse_pos = (event.mouse_region_x, event.mouse_region_y)
    x_pos = mouse_pos[0]
    y_pos = mouse_pos[1]
    margin = 30
    padding = 0

    if mouse_pos[0] + margin > context.area.width:
        x_pos = margin + padding
    elif mouse_pos[0] - margin < 0:
        x_pos = context.area.width - (margin + padding)

    if mouse_pos[1] + margin > context.area.height:
        y_pos = margin + padding
    elif mouse_pos[1] - margin < 0:
        y_pos = context.area.height - (margin + padding)
    if x_pos != mouse_pos[0] or y_pos != mouse_pos[1]:
        x_pos += context.area.x
        y_pos += context.area.y
        context.window.cursor_warp(x_pos, y_pos)
        warped = True
    return warped


def axis_color(axis="X") -> tuple:
    """Get the color of the axis.

    axis (enum in ['X', 'Y', 'Z'], default 'X') - Axis.
    return (tuple) - Color of the axis.
    """
    if axis == "X":
        return bpy.context.preferences.themes["Default"].user_interface.axis_x
    elif axis == "Y":
        return bpy.context.preferences.themes["Default"].user_interface.axis_y
    elif axis == "Z":
        return bpy.context.preferences.themes["Default"].user_interface.axis_z
