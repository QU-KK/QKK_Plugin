import bpy
from .blender import preferences, dpi_factor


class Event:
    def __init__(self):
        self.prefs = preferences()
        self.pause_modal = False
        self.input_list = {
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "+",
            "-",
            ".",
        }
        self.input = ""

    def mouse(self, event, axis) -> float:
        """Handle mouse move.

        axis (enum in ['X', 'Z']) - Axis to handle mouse move.
        return (float) - Delta.
        """
        if axis == "X":
            delta = (event.mouse_x - event.mouse_prev_x) / window.width * 1000 * dpi_factor()
        elif axis == "Z":
            delta = (event.mouse_y - event.mouse_prev_y) / window.width * 1000 * dpi_factor()
        if event.shift:
            delta = delta * 0.1 * dpi_factor()
        elif event.ctrl:
            delta = delta * 0.5 * dpi_factor()

        return delta

    def scroll(self, event):
        if event.type == "TRACKPADPAN":
            delta = event.mouse_y - event.mouse_prev_y
            if abs(delta) < 5:
                return 0
            if delta > 0:
                return 1
            elif delta < 0:
                return -1
            else:
                return 0
        scroll = 0
        if event.type == "WHEELDOWNMOUSE":
            scroll += -1
        elif event.type == "WHEELUPMOUSE":
            scroll += 1
        return scroll

    def input_value(self, value):
        """Handle input value.

        value (str) - Input value.
        """
        if value == "-":
            if not self.input.startswith("-"):
                self.input = f"-{self.input}"
        elif value == "+":
            if self.input.startswith("-"):
                self.input = self.input.split("-")[-1]
        elif value != "." or "." not in self.input:
            self.input += value

    def confirm_input_value(self, data, property):
        """Confirm input value.

        data (AnyType) - Data from which to take property.
        property (str) - Identifier of property in data.
        """
        value = self.input_as_value(data, property)
        self.set_property_value(data, property, value)
