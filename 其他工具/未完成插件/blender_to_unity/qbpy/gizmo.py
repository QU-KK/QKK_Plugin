import bpy
from bpy.types import bpy_prop_collection
import statistics
from math import radians
from mathutils import Matrix, Vector
from .blender import dpi_factor, panel


class Gizmo:
    def gizmo_3d(self, operator, color, draw_style="BOX") -> bpy.types.Gizmo:
        """Draw a 3D gizmo.

        operator (str) - The operator that is being used to draw the gizmo.
        color (tuple containing RGBA values) - The color of the gizmo.
        draw_style (enum in ['NORMAL', 'CROSS', 'BOX', 'CONE'], default 'BOX') - The style of the gizmo.
        return (bpy.types.Gizmo) - The gizmo.
        """
        gizmo = self.gizmos.new("GIZMO_GT_arrow_3d")
        gizmo.target_set_operator(operator)
        gizmo.draw_style = draw_style
        gizmo.scale_basis = 1.5
        gizmo.color = color
        gizmo.alpha = 0.5
        gizmo.color_highlight = color
        gizmo.alpha_highlight = 1.0
        gizmo.line_width = 2
        return gizmo

    def gizmo_2d(
        self,
        operator,
        icon,
        enable_icon=None,
        data=None,
        property=None,
        show_drag=False,
        mode="ALL",
    ) -> bpy.types.Gizmo:
        """Draw a 2D gizmo.

        operator (str) - The operator that is being used to draw the gizmo.
        icon (str) - The icon of the gizmo.
        enable_icon (str) - The icon of the gizmo when the gizmo is enabled.
        data (bpy.types) - The data that is being used to draw the gizmo.
        property (str) - The property of the data that is being used to draw the gizmo.
        show_drag (bool) - Whether or not to show the drag.
        mode (enum in ['ALL', 'OBJECT', ''EDIT_MESH', 'SCULPT', 'PAINT_VERTEX', 'PAINT_WEIGHT', 'PAINT_TEXTURE'], default 'ALL') - The mode that is being used to draw the gizmo.
        return (bpy.types.Gizmo) - The gizmo.
        """
        if enable_icon is not None:
            self.gizmo_2d(
                operator=operator,
                icon=enable_icon,
                data=data,
                property=property,
                show_drag=show_drag,
                mode=mode,
            )
        gizmo = self.gizmos.new("GIZMO_GT_button_2d")
        gizmo.target_set_operator(operator)
        gizmo.icon = icon
        gizmo.draw_options = {"BACKDROP", "OUTLINE"}
        gizmo.color = 0, 0, 0
        gizmo.alpha = 0.5
        gizmo.color_highlight = 0.5, 0.5, 0.5
        gizmo.alpha_highlight = 0.5
        gizmo.scale_basis = 14
        gizmo.show_drag = show_drag
        gizmo.use_event_handle_all = True
        self.gizmo_actions.append((gizmo, icon, enable_icon, data, property, mode))
        return gizmo

    def get_gizmos(self) -> list[bpy.types.Gizmo]:
        """Get all gizmos.

        return (list of bpy.types.Gizmo) - The gizmos.
        """
        return [gizmo for gizmo in self.gizmos if not gizmo.hide]

    def gizmo_position(self, region_dimension, align="RIGHT") -> tuple[Vector, tuple[int, int]]:
        """Get the gizmo orientation.

        region_dimension (Vector) - The dimension of the region.
        align (enum in ['TOP', 'RIGHT', 'BOTTOM', 'LEFT'], default 'RIGHT') - The alignment of the gizmo.
        return (tuple containing 3D vector) - The gizmo orientation and the gizmo position.
        """
        gizmos = self.get_gizmos()
        gap = 2.2

        for gizmo in gizmos:
            gizmo_bar = gizmo.scale_basis * 2 * len(gizmos) + (2.2 * len(gizmos) - 32 + gap)

        if align == "TOP":
            position = (
                region_dimension.x / 2 - (gizmo_bar / 2 * dpi_factor()),
                region_dimension.y - (panel("HEADER")[1] + panel("TOOL_HEADER")[1]),
                0,
            )
            orientation = (1 * dpi_factor(), 0, 0)
        elif align == "RIGHT":
            if bpy.context.preferences.view.mini_axis_type == "GIZMO":
                position = (
                    region_dimension.x - (panel("UI")[0] + 22 * dpi_factor()),
                    region_dimension.y - (171.2 + bpy.context.preferences.view.gizmo_size_navigate_v3d) * dpi_factor(),
                    0,
                )
            elif bpy.context.preferences.view.mini_axis_type == "MINIMAL":
                position = (
                    region_dimension.x - (panel("UI")[0] + 22 * dpi_factor()),
                    region_dimension.y
                    - ((196.2 + bpy.context.preferences.view.mini_axis_size) + bpy.context.preferences.view.mini_axis_size) * dpi_factor(),
                    0,
                )
            else:
                position = (
                    region_dimension.x - (panel("UI")[0] + 22 * dpi_factor()),
                    region_dimension.y - 168.2 * dpi_factor(),
                    0,
                )
            orientation = (0, -1 * dpi_factor(), 0)
        elif align == "BOTTOM":
            position = (
                region_dimension.x / 2 - (gizmo_bar / 2 * dpi_factor()),
                22 * dpi_factor(),
                0,
            )
            orientation = (1 * dpi_factor(), 0, 0)
        elif align == "LEFT":
            position = (
                panel("TOOLS")[0] + 22 * dpi_factor(),
                region_dimension.y / 2 + (gizmo_bar / 2 * dpi_factor()),
                0,
            )
            orientation = (0, -1 * dpi_factor(), 0)
        return (Vector(position), orientation)

    def check_object_mode(self, context):
        """Check if the object mode is active."""
        object_mode = context.mode
        for gizmo, icon, enable_icon, data, property, mode in self.gizmo_actions:
            gizmo.hide = mode not in {"ALL", object_mode}
            if data is not None and property is not None:
                data = getattr(data, property)
                state = enable_icon is None
                gizmo.hide = type(data) == bpy_prop_collection and (len(data) == 0) == state or type(data) != bpy_prop_collection and data == state

    def matrix(self, context, axis):
        """Get the matrix for the given axis.

        axis (str) - The axis.
        return (Matrix) - The matrix normalized.
        """
        selection = [objects for objects in context.selected_objects if objects.type == "MESH"]
        objs_origin_loc = [a.matrix_world.translation for a in selection]
        obj_loc = [statistics.median(col) for col in zip(*objs_origin_loc)]
        obj_rot = context.object.rotation_euler

        obj_loc_mat = Matrix.Translation(obj_loc)
        obj_scale_mat = Matrix.Scale(1, 4, (1, 0, 0)) @ Matrix.Scale(1, 4, (0, 1, 0)) @ Matrix.Scale(1, 4, (0, 0, 1))

        if axis == "POS_X":
            pos_x_rot_mat = obj_rot.to_matrix().to_4x4() @ Matrix.Rotation(radians(90), 4, "Y")
            pos_x_matrix = obj_loc_mat @ pos_x_rot_mat @ obj_scale_mat
            return pos_x_matrix.normalized()
        if axis == "POS_Y":
            pos_y_rot_mat = obj_rot.to_matrix().to_4x4() @ Matrix.Rotation(radians(-90), 4, "X")
            pos_y_matrix = obj_loc_mat @ pos_y_rot_mat @ obj_scale_mat
            return pos_y_matrix.normalized()
        if axis == "POS_Z":
            pos_z_rot_mat = obj_rot.to_matrix().to_4x4() @ Matrix.Rotation(radians(90), 4, "Z")
            pos_z_matrix = obj_loc_mat @ pos_z_rot_mat @ obj_scale_mat
            return pos_z_matrix.normalized()
        if axis == "NEG_X":
            neg_x_rot_mat = obj_rot.to_matrix().to_4x4() @ Matrix.Rotation(radians(-90), 4, "Y")
            neg_x_matrix = obj_loc_mat @ neg_x_rot_mat @ obj_scale_mat
            return neg_x_matrix.normalized()
        if axis == "NEG_Y":
            neg_y_rot_mat = obj_rot.to_matrix().to_4x4() @ Matrix.Rotation(radians(90), 4, "X")
            neg_y_matrix = obj_loc_mat @ neg_y_rot_mat @ obj_scale_mat
            return neg_y_matrix.normalized()
        if axis == "NEG_Z":
            neg_z_rot_mat = obj_rot.to_matrix().to_4x4() @ Matrix.Rotation(radians(-180), 4, "X")
            neg_z_matrix = obj_loc_mat @ neg_z_rot_mat @ obj_scale_mat
            return neg_z_matrix.normalized()
