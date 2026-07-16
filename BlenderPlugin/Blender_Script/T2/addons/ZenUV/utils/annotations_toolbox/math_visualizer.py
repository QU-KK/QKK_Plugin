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
import json
import math
from mathutils import Vector, Color, Matrix

from dataclasses import dataclass

from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.utils.vlog import Log

from .shapes import AnnotationShapes


@dataclass
class FramePrepareStorage:
    frame_idx: int = 0
    stroke_placement_2d: str = 'IMAGE'
    stroke_placement_3d: str = 'CURSOR'
    frame: bpy.types.GPencilFrame = None
    layer: bpy.types.GPencilLayer = None

    def restore(self):
        if not ZenPolls.version_lower_4_3_0:
            p_scene = bpy.context.scene
            p_tool_settings = p_scene.tool_settings

            if self.frame_idx != p_scene.frame_current:
                p_scene.frame_current = self.frame_idx

            if self.stroke_placement_2d != p_tool_settings.annotation_stroke_placement_view2d:
                p_tool_settings.annotation_stroke_placement_view2d = self.stroke_placement_2d

            if self.stroke_placement_3d != p_tool_settings.annotation_stroke_placement_view3d:
                p_tool_settings.annotation_stroke_placement_view3d = self.stroke_placement_3d

    def __del__(self):
        self.restore()


class TextFactory:

    letters_dict = dict()

    @classmethod
    def format_entry(cls, key, value, split_by: int = 2):
        """ format a dictionary entry """
        # Format the numeric values
        formatted_values = ',\n    '.join(str(v) if isinstance(v, float) else repr(v) for v in value[:2])

        # Format the list with two elements per row
        list_values = value[2]
        formatted_list = ',\n        '.join(', '.join(map(repr, list_values[i:i+split_by])) for i in range(0, len(list_values), split_by))

        return f"{key} = [\n    {formatted_values},\n    [\n        {formatted_list}\n    ]\n]"

    @classmethod
    def read_json_font(cls, json_font_name: str = 'isocpeur'):
        import os
        try:
            base_dir = os.path.dirname(__file__)
            p_font_file = os.path.join(base_dir, json_font_name + '.json')
            if os.path.isfile(p_font_file):
                with open(p_font_file, "r") as json_file:
                    cls.letters_dict = json.load(json_file)
                    return True
            else:
                return False
        except Exception as e:
            print(f'Error when reading font file: {e}')

    @classmethod
    def process_string(cls, string):
        for letter in string:
            if letter in TextFactory.letters_dict:
                yield TextFactory.letters_dict[letter]

    @classmethod
    def grab_curves_to_json_font(
            cls, is_output_to_file: bool = False,
            json_font_name: str = 'isocpeur', append_space_character: bool = False,
            round_to: int = 4):

        split_by: int = 4
        selected_curves_data = {}

        for obj in bpy.context.selected_objects:
            if obj.type == 'CURVE':
                curve_data = obj.data

                curve_width = obj.dimensions.x
                curve_height = obj.dimensions.y

                curve_data_list = [curve_width, curve_height, []]
                for spline in curve_data.splines:
                    if len(spline.points) != 2:
                        continue
                    curve_data_list[2].append(
                        [[round(v, round_to) for v in spline.points[0].co[:2]],
                         [round(v, round_to) for v in spline.points[1].co[:2]]])
                selected_curves_data[obj.name] = curve_data_list

        if append_space_character:
            # print(selected_curves_data)
            # " ": [0.5, 0.1, []] Append SPACE
            selected_curves_data[' '] = [0.5, 0.1, []]

        if is_output_to_file:
            import os
            base_dir = os.path.dirname(__file__)
            p_font_file = os.path.join(base_dir, json_font_name + '.json')

            with open(p_font_file, "w") as json_file:
                json.dump(selected_curves_data, json_file)

            print("JSON file created successfully:", p_font_file)
        else:
            for v in [cls.format_entry(key, value, split_by) for key, value in selected_curves_data.items()]:
                print(v)


class MathVisualizer:
    def __init__(self, context: bpy.types.Context, pencil_name: str = '') -> None:

        self.display_mode = '3DSPACE' if context.space_data.type == 'VIEW_3D' else '2DSPACE'

        self.pencil = None
        if pencil_name:
            self.pencil = bpy.data.grease_pencils.get(pencil_name, None)
        else:
            self.pencil = bpy.context.annotation_data
        if not self.pencil:
            bpy.ops.gpencil.annotation_add()
            self.pencil = bpy.data.grease_pencils[-1]
            if pencil_name:
                self.pencil.name = pencil_name

        gpd_owner = bpy.context.annotation_data_owner
        if gpd_owner and gpd_owner.grease_pencil != self.pencil:
            gpd_owner.grease_pencil = self.pencil

    def clear(self, group: str, frame_idx: int):
        layer = self.pencil.layers.get(group, None)
        if layer is None:
            return

        frame = None

        for it_frame in layer.frames:
            if it_frame.frame_number == frame_idx:
                frame = it_frame
                break

        if frame is not None:
            if ZenPolls.version_lower_4_3_0:
                frame.clear()
            else:
                layer.frames.remove(frame)

    def add_cross(
            self,
            group: str, frame_idx: int,
            color: Color = None, size: float = 1.0,
            line_width: int = 3, position: tuple = (0.0, 0.0, 0.0),
            rotation: Matrix = Matrix(),
            clear: bool = True,
            show_in_front: bool = True):

        storage = self._prepare_frame(
            group, frame_idx, color=color,
            clear=clear, show_in_front=show_in_front)
        storage.layer.thickness = line_width

        for co in AnnotationShapes.cross[2]:

            co_start, co_end = co

            vec_start = Vector(co_start) * size
            vec_start.resize_3d()
            vec_end = Vector(co_end) * size
            vec_end.resize_3d()

            position = Vector(position)
            position.resize_3d()
            v1 = rotation @ vec_start + position
            v2 = rotation @ vec_end + position

            if ZenPolls.version_lower_4_3_0:
                gp_stroke = storage.frame.strokes.new()
                gp_stroke.start_cap_mode = 'ROUND'
                gp_stroke.end_cap_mode = 'ROUND'
                gp_stroke.use_cyclic = False

                gp_stroke.display_mode = self.display_mode

                gp_stroke.points.add(2)
                gp_stroke.points[0].co = v1
                gp_stroke.points[-1].co = v2
            else:
                self._add_stroke_by_gpencil_annotate((v1, v2), self.pencil, storage.layer)

    def add_dot(
            self,
            group: str, frame_idx: int,
            color: Color = None, size: float = 1.0,
            line_width: int = 3, position: tuple = (0.0, 0.0, 0.0),
            rotation: Matrix = Matrix(),
            clear: bool = True,
            show_in_front: bool = True):

        storage = self._prepare_frame(
            group, frame_idx, color=color,
            clear=clear, show_in_front=show_in_front)
        storage.layer.thickness = line_width

        for co in AnnotationShapes.get_dot('simple dot')[2]:
            co_start, co_end = co

            vec_start = Vector(co_start) * size
            vec_start.resize_3d()
            vec_end = Vector(co_end) * size
            vec_end.resize_3d()
            position = Vector(position)
            position.resize_3d()

            v1 = rotation @ vec_start + position
            v2 = rotation @ vec_end + position

            if ZenPolls.version_lower_4_3_0:
                gp_stroke = storage.frame.strokes.new()
                gp_stroke.start_cap_mode = 'ROUND'
                gp_stroke.end_cap_mode = 'ROUND'
                gp_stroke.use_cyclic = False

                gp_stroke.display_mode = self.display_mode

                gp_stroke.points.add(2)
                gp_stroke.points[0].co = v1
                gp_stroke.points[-1].co = v2
            else:
                self._add_stroke_by_gpencil_annotate((v1, v2), self.pencil, storage.layer)

    def add_text(
            self,
            group: str, frame_idx: int, text: str,
            color: Color = None, letters_size: float = 1.0,
            line_width: int = 3, position: tuple = (0.0, 0.0, 0.0),
            clear: bool = True,
            show_in_front: bool = True,
            space_between_letters: float = 0.3,
            # NOTE: if set then text is drawn in view percent coordinates from 0 to 100%
            is_screen_mode: bool = False):

        storage = self._prepare_frame(
            group, frame_idx, color=color,
            clear=clear, show_in_front=show_in_front,
            stroke_placement_2d='VIEW' if is_screen_mode else 'IMAGE',
            stroke_placement_3d='VIEW' if is_screen_mode else 'CURSOR')
        storage.layer.thickness = line_width

        if TextFactory.read_json_font(json_font_name='isocpeur') is False:
            return

        next_offset = 0.0
        for letter_width, letter_height, vectors in TextFactory.process_string(text):

            for co in vectors:
                if not len(co):
                    # Skip for SPACE reason
                    continue
                p_offset = Vector((next_offset, 0.0))
                co_start, co_end = co
                vec_start = (Vector(co_start) + p_offset) * letters_size
                vec_start.resize_3d()
                vec_end = (Vector(co_end) + p_offset) * letters_size
                vec_end.resize_3d()

                v1 = vec_start + Vector(position)
                v2 = vec_end + Vector(position)

                if ZenPolls.version_lower_4_3_0:
                    gp_stroke = storage.frame.strokes.new()
                    gp_stroke.start_cap_mode = 'ROUND'
                    gp_stroke.end_cap_mode = 'ROUND'
                    gp_stroke.use_cyclic = False

                    gp_stroke.display_mode = 'SCREEN' if is_screen_mode else self.display_mode

                    gp_stroke.points.add(2)

                    gp_stroke.points[0].co = v1
                    gp_stroke.points[-1].co = v2
                else:
                    self._add_stroke_by_gpencil_annotate((v1, v2), self.pencil, storage.layer)

            next_offset += letter_width + space_between_letters

    def _prepare_frame(
            self,
            group: str, frame_idx: int,
            color: Color = None, clear: bool = True,
            show_in_front: bool = True,
            stroke_placement_2d: str = 'IMAGE',
            stroke_placement_3d: str = 'CURSOR'):
        storage = FramePrepareStorage()

        p_scene = bpy.context.scene

        storage.layer = self.pencil.layers.get(group, None)
        if storage.layer is None:
            storage.layer = self.pencil.layers.new(group)

        self._activate_layer(storage.layer)

        if not ZenPolls.version_lower_4_3_0:
            was_frame_idx = p_scene.frame_current

            p_tool_settings = p_scene.tool_settings

            storage.stroke_placement_2d = p_tool_settings.annotation_stroke_placement_view2d
            storage.stroke_placement_3d = p_tool_settings.annotation_stroke_placement_view3d

            if storage.stroke_placement_2d != stroke_placement_2d:
                p_tool_settings.annotation_stroke_placement_view2d = stroke_placement_2d

            if storage.stroke_placement_3d != stroke_placement_3d:
                p_tool_settings.annotation_stroke_placement_view3d = stroke_placement_3d

            if storage.frame_idx != was_frame_idx:
                p_scene.frame_set(storage.frame_idx)

        p_was_frame = None
        for it_frame in storage.layer.frames:
            if it_frame.frame_number == frame_idx:
                storage.frame = it_frame
                p_was_frame = it_frame
                break

        if storage.frame is None:
            storage.frame = storage.layer.frames.new(frame_idx, active=True)

        if clear:
            if ZenPolls.version_lower_4_3_0:
                storage.frame.clear()
            else:
                if p_was_frame:
                    storage.layer.frames.remove(p_was_frame)
                    storage.frame = storage.layer.frames.new(frame_idx, active=True)

        if color is not None:
            storage.layer.color = color[:]

        storage.layer.show_in_front = show_in_front

        return storage

    def _add_stroke_by_gpencil_annotate(self, points: tuple, pencil: bpy.types.GreasePencil, layer: bpy.types.GPencilLayer):
        try:
            strokes = [
                {
                    "name": f"stroke{idx}",
                    "mouse": (idx * 10, idx * 10),
                    "mouse_event": (0, 0),
                    # "pen_flip": False,  # NOTE: Removed in Blender 4.4
                    "is_start": True if idx == 0 else False,
                    "location": point,
                    "size": 1,
                    "pressure": 1,
                    "time": 0.0,
                    "x_tilt": 0.0,
                    "y_tilt": 0.0
                }
                for idx, point in enumerate(points)
            ]

            # NOTE: necessary attribute for Blender 4.3
            if ZenPolls.version_lower_4_4_0:
                for stroke in strokes:
                    stroke["pen_flip"] = False

            ctx_override = bpy.context.copy()
            ctx_override['annotation_data'] = pencil
            ctx_override['active_annotation_layer'] = layer

            with bpy.context.temp_override(**ctx_override):
                bpy.ops.gpencil.annotate(
                    mode='DRAW_STRAIGHT', arrowstyle_start='ARROW', arrowstyle_end='ARROW',
                    use_stabilizer=False, stabilizer_factor=0.75, stabilizer_radius=35, stroke=strokes,
                    wait_for_input=False)

            # NOTE: use only 'active_frame', because 'gpencil.annotate' will create it with current frame number
            if layer.active_frame and len(layer.active_frame.strokes) > 0:
                p_stroke = layer.active_frame.strokes[-1]
                n_stroke_points_count = len(p_stroke.points)
                n_points_count = len(points)
                if n_stroke_points_count == n_points_count:
                    for idx, pt in enumerate(points):
                        p_stroke.points[idx].co = pt
                else:
                    raise RuntimeError(f"Stroke points count:{n_stroke_points_count} mismatches to:{n_points_count}")
            else:
                raise RuntimeError("Strokes were not created!")
        except Exception as e:
            Log.error("GPENCIL STROKE:", e, "Points:", str(points))

    def _activate_layer(self, layer: bpy.types.GPencilLayer):
        if ZenPolls.version_lower_4_3_0:
            self.pencil.layers.active = layer
        else:
            idx = self.pencil.layers.find(layer.info)
            if idx == -1:
                raise RuntimeError("Can not get GPencilLayer index!")

            self.pencil.layers.active_index = idx

    def add_vector(
            self,
            group: str, frame_idx: int, co_list: tuple,
            color: Color = None, clear: bool = True,
            is_constant_arrow_size: bool = True, arrow_size: float = 0.005,
            show_in_front: bool = True):

        storage = self._prepare_frame(
            group, frame_idx, color=color,
            clear=clear, show_in_front=show_in_front)

        for co in co_list:
            co_start, co_end = co
            vec_start = co_start.copy()
            vec_start.resize_3d()
            vec_end = co_end.copy()
            vec_end.resize_3d()

            if ZenPolls.version_lower_4_3_0:
                gp_stroke = storage.frame.strokes.new()

                gp_stroke.start_cap_mode = 'ROUND'
                gp_stroke.end_cap_mode = 'ROUND'
                gp_stroke.use_cyclic = False

                gp_stroke.display_mode = self.display_mode

                gp_stroke.points.add(2)

                gp_stroke.points[0].co = vec_start
                gp_stroke.points[-1].co = vec_end
            else:
                self._add_stroke_by_gpencil_annotate((vec_start, vec_end), self.pencil, storage.layer)

            axis_raw = vec_end - vec_start  # type: Vector
            distance = axis_raw.length
            if distance == 0:
                return

            if is_constant_arrow_size:
                vec_arrow = Vector((0, 1.0, 0)) * arrow_size
            else:
                distance /= 10
                vec_arrow = Vector((0, distance, 0)) * arrow_size * 400

            axis = axis_raw.normalized()  # type: Vector

            vec_right = vec_arrow.copy()
            vec_right.rotate(Matrix.Rotation(math.radians(-160), 4, "Z"))

            vec_left = vec_arrow.copy()
            vec_left.rotate(Matrix.Rotation(math.radians(160), 4, "Z"))

            mtxRotDir = axis.to_track_quat('Y', 'Z').to_matrix().to_4x4()

            vec_left = Matrix.Translation(vec_end) @ mtxRotDir @ vec_left
            vec_right = Matrix.Translation(vec_end) @ mtxRotDir @ vec_right

            if ZenPolls.version_lower_4_3_0:
                gp_stroke_left = storage.frame.strokes.new()

                gp_stroke_left.start_cap_mode = 'ROUND'
                gp_stroke_left.end_cap_mode = 'ROUND'
                gp_stroke_left.use_cyclic = False

                gp_stroke_left.display_mode = self.display_mode

                gp_stroke_left.points.add(2)

                gp_stroke_left.points[0].co = vec_end
                gp_stroke_left.points[-1].co = vec_right
            else:
                self._add_stroke_by_gpencil_annotate((vec_end, vec_right), self.pencil, storage.layer)

            if ZenPolls.version_lower_4_3_0:
                gp_stroke_right = storage.frame.strokes.new()

                gp_stroke_right.start_cap_mode = 'ROUND'
                gp_stroke_right.end_cap_mode = 'ROUND'
                gp_stroke_right.use_cyclic = False

                gp_stroke_right.display_mode = self.display_mode

                gp_stroke_right.points.add(2)

                gp_stroke_right.points[0].co = vec_end
                gp_stroke_right.points[-1].co = vec_left
            else:
                self._add_stroke_by_gpencil_annotate((vec_end, vec_left), self.pencil, storage.layer)
