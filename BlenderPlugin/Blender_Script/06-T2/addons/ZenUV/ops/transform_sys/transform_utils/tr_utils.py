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

# Copyright 2023, Valeriy Yatsenko

import bpy
from mathutils import Vector

from ZenUV.utils.blender_zen_utils import rgetattr, rsetattr
from ZenUV.utils.vlog import Log


class TransformOrderSolver:

    @classmethod
    def get(cls, context):
        tr_order = context.scene.zen_uv.tr_pivot_mode
        if tr_order in {'ONE_BY_ONE', 'OVERALL'}:
            return tr_order
        elif tr_order == 'SYSTEM_PIVOT':
            return BlPivotPoint.get(context)
        else:
            raise RuntimeError("context.scene.zen_uv.tr_pivot_mode not in ['ONE_BY_ONE', 'OVERALL', 'SYSTEM_PIVOT']")


class ActiveUvImage:

    def __init__(self, context) -> None:
        self.len_x = 1
        self.len_y = 1
        self.image = self._get_image(context)
        self.aspect = self.len_x / self.len_y
        self.hats = self._get_hats()

    def _get_image(self, context):
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                if area.spaces.active:
                    image = area.spaces.active.image
                    if image is not None:
                        if sum(image.size) != 0:
                            self.len_x = image.size[0]
                            self.len_y = image.size[1]
                        else:
                            self.len_x = 1
                            self.len_y = 1

                return image
        return None

    def _get_hats(self):
        _max = max(self.len_x, self.len_y)
        return Vector((self.len_x / _max, self.len_y / _max))


class TransformSysOpsProps:

    align_directions_items = [
        ("br", 'Bottom-Right', '', 0),
        ("bl", 'Bottom-Left', '', 1),
        ("tr", 'Top-Right', '', 2),
        ("tl", 'Top-Left', '', 3),
        ("cen", 'Center', '', 4),
        ("rc", 'Right', '', 5),
        ("lc", 'Left', '', 6),
        ("bc", 'Bottom', '', 7),
        ("tc", 'Top', '', 8),
        ("cen_v", 'Center Vertical', '', 9),
        ("cen_h", 'Center Horizontal', '', 10)
    ]

    align_directions_map = {
        id: name for id, name, _, _ in align_directions_items
    }

    def _align_directions(self, context):
        return TransformSysOpsProps.align_directions_items

    @classmethod
    def get_align_direction_description(cls, s_direction: str):
        return cls.align_directions_map.get(s_direction, "")

    def _bbox_names_with_center(self, context):
        return [
                ("br", 'Bottom-Right', '', 0),
                ("bl", 'Bottom-Left', '', 1),
                ("tr", 'Top-Right', '', 2),
                ("tl", 'Top-Left', '', 3),
                ("cen", 'Center', '', 4),
                ("rc", 'Right', '', 5),
                ("lc", 'Left', '', 6),
                ("bc", 'Bottom', '', 7),
                ("tc", 'Top', '', 8),
            ]

    def _bbox_names(self, context):
        return [
                ("br", 'Bottom-Right', '', 0),
                ("bl", 'Bottom-Left', '', 1),
                ("tr", 'Top-Right', '', 2),
                ("tl", 'Top-Left', '', 3),
                ("rc", 'Right', '', 4),
                ("lc", 'Left', '', 5),
                ("bc", 'Bottom', '', 6),
                ("tc", 'Top', '', 7),
            ]

    influence_mode = bpy.props.EnumProperty(
        name='Mode',
        description="Transform Mode",
        items=[
            ("ISLAND", "Islands", "Transform islands mode", 'UV_ISLANDSEL', 0),
            ("SELECTION", "Selection", "Transform selection (uv, mesh) mode", 'UV_FACESEL', 1),
        ],
        default="ISLAND"
    )

    def _units_items(self, context):
        return [
                ('km', 'km', 'KILOMETERS', 0),
                ('m', 'm', 'METERS', 1),
                ('cm', 'cm', 'CENTIMETERS', 2),
                ('mm', 'mm', 'MILLIMETERS', 3),
                ('um', 'um', 'MICROMETERS', 4),
                ('mil', 'mil', 'MILES', 5),
                ('ft', 'ft', 'FEET', 6),
                ('in', 'in', 'INCHES', 7),
                ('th', 'th', 'THOU', 8)
            ]

    @classmethod
    def get_units_enum(cls, name='Units', description='UV world size calculation units', default: int = 1):
        return bpy.props.EnumProperty(
            name=name,
            description=description,
            items=cls._units_items,
            default=default,
            options=set()
        )

    def get_influence_mode(self):
        p_scene = bpy.context.scene
        if p_scene.zen_uv.tr_type == 'SELECTION':
            return 1
        return 0

    def set_influence_mode(self, value):
        p_scene = bpy.context.scene
        if value == 1:
            p_scene.zen_uv.tr_type = "SELECTION"
        elif value == 0:
            p_scene.zen_uv.tr_type = "ISLAND"

    influence_scene_mode = bpy.props.EnumProperty(
        name='Mode',
        description="Transform Mode",
        items=[
            ("ISLAND", "Islands", "Transform islands mode", 'UV_ISLANDSEL', 0),
            ("SELECTION", "Selection", "Transform selection (uv, mesh) mode", 'UV_FACESEL', 1),
        ],
        get=get_influence_mode,
        set=set_influence_mode,
        options={'SKIP_SAVE'}
    )

    op_order = bpy.props.EnumProperty(
            name='Order',
            description="Processing order",
            items=[
                (
                    'ONE_BY_ONE',
                    "One by one",
                    "Processing islands one by one"
                ),
                (
                    'OVERALL',
                    "Overall",
                    "Processing whole selection"
                ),
            ],
            default="OVERALL"
        )
    direction = bpy.props.EnumProperty(
            name="Direction",
            items=_bbox_names,
            default=4
        )
    island_pivot = bpy.props.EnumProperty(
            name="Island Pivot",
            items=_bbox_names_with_center,
            default=4,
            description='The pivot of the transformed unit'
        )

    @classmethod
    def get_island_pivot_dynamic(cls, wm_path: str):

        def get_island_pivot(self):
            ctx = bpy.context
            p_scene = ctx.scene
            pivot = rgetattr(p_scene, wm_path)
            for id_str, _, _, idx in cls._bbox_names_with_center(self, ctx):
                if id_str == pivot:
                    return idx
            return 4

        def set_island_pivot(self, value: int):
            ctx = bpy.context
            p_scene = ctx.scene
            for id_str, _, _, idx in cls._bbox_names_with_center(self, ctx):
                if value == idx:
                    rsetattr(p_scene, wm_path, id_str)
                    return

        return bpy.props.EnumProperty(
            name="Island Pivot",
            items=cls._bbox_names_with_center,
            get=get_island_pivot,
            set=set_island_pivot
        )

    island_pivot_hidden = bpy.props.EnumProperty(
            name="Island Pivot",
            items=_bbox_names_with_center,
            default=4,
            options={'HIDDEN'}
        )
    align_direction = bpy.props.EnumProperty(
                name="Island Pivot",
                items=_align_directions,
                default=4
            )

    @classmethod
    def get_align_direction(cls, default: int):
        return bpy.props.EnumProperty(
                name="Island Pivot",
                items=cls._align_directions,
                default=default
            )
    cursor_2d_as_pivot = bpy.props.BoolProperty(
        name='2D Cursor as Pivot',
        description='Use Cursor 2D as Island Pivot',
        default=False
        )

    def update_lock(self, context):
        wm = context.window_manager
        if wm.operators:
            op = wm.operators[-1]
            if op.lock_in_trim != self.lock_in_trim:
                op.lock_in_trim = self.lock_in_trim
        context.area.tag_redraw()

    @classmethod
    def get_lock_in_trim_sync(cls, idname: str):

        def update_lock(self, context):
            wm = context.window_manager
            if wm.operators:
                op = wm.operators[-1]
                if op.bl_idname == idname:
                    if op.lock_in_trim != self.lock_in_trim:
                        op.lock_in_trim = self.lock_in_trim
                        context.area.tag_redraw()

        return bpy.props.BoolProperty(
            name="Lock in Trim",
            description="Perform transform operations only inside of trim",
            default=False,
            update=update_lock
        )

    lock_in_trim = bpy.props.BoolProperty(
        name="Lock in Trim",
        description="Lock in Trim",
        default=False
    )

    info_message = bpy.props.StringProperty(
        name='Warning',
        description='Transform warning message',
        default='',
        options={'SKIP_SAVE'}
    )

    is_offset_mode = bpy.props.BoolProperty(
        name='Offset Mode',
        description="Transform is performed by chain of small offsets",
        default=False,
        options={'SKIP_SAVE'}
    )

    def get_order_prop(default: str = 'ONE_BY_ONE'):
        return bpy.props.EnumProperty(
            name='Order',
            description="Processing order",
            items=[
                (
                    'ONE_BY_ONE',
                    "One by one",
                    "Processing islands one by one"
                ),
                (
                    'OVERALL',
                    "Overall",
                    "Processing whole selection"
                ),
            ],
            default=default
        )

    @classmethod
    def get_island_pivot_prop(cls, default: int = 4):
        return bpy.props.EnumProperty(
            name="Island Pivot",
            items=cls._bbox_names_with_center,
            default=default
        )

    @classmethod
    def poll_edit_mesh_and_active_object(cls, context: bpy.types.Context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    @classmethod
    def poll_reason_edit_mesh_and_active_object(cls, context: bpy.types.Context):
        if context.mode != 'EDIT_MESH':
            return 'Available in Edit Mesh!'

        p_act_obj = context.active_object
        if p_act_obj is None:
            return 'No Active Object!'

        if p_act_obj.type != 'MESH':
            return 'Active object is not Mesh!'

        return ''


class TrConstants:

    opposite_direction = {
        "tl": "br",
        "tc": "bc",
        "tr": "bl",
        "lc": "rc",
        "cen": "tr",
        "rc": "lc",
        "bl": "tr",
        "bc": "tc",
        "br": "tl",
        "cen_v": "cen_h",
        "cen_h": "cen_v"

    }

    dir_vector = {
        "tl": Vector((-1, 1)),
        "tc": Vector((0, 1)),
        "tr": Vector((1, 1)),
        "lc": Vector((-1, 0)),
        "cen": Vector((0, 0)),
        "rc": Vector((1, 0)),
        "bl": Vector((-1, -1)),
        "bc": Vector((0, -1)),
        "br": Vector((1, -1))
    }
    flip_vector = {
        "tl": Vector((-1, -1)),
        "tc": Vector((1, -1)),
        "tr": Vector((-1, -1)),
        "lc": Vector((-1, 1)),
        "cen": Vector((1, 1)),
        "rc": Vector((-1, 1)),
        "bl": Vector((-1, -1)),
        "bc": Vector((1, -1)),
        "br": Vector((-1, -1))
    }
    fit_position = {
        "tl": Vector((0, 1)),
        "tc": Vector((0.5, 1)),
        "tr": Vector((1, 1)),
        "lc": Vector((0, 0.5)),
        "cen": Vector((0.5, 0.5)),
        "rc": Vector((1, 0.5)),
        "bl": Vector((0, 0)),
        "bc": Vector((0.5, 0)),
        "br": Vector((1, 0))
    }
    mute_axis = {
        "tl": Vector((1, 1)),
        "tc": Vector((0, 1)),
        "tr": Vector((1, 1)),
        "lc": Vector((1, 0)),
        "cen": Vector((1, 1)),
        "rc": Vector((1, 0)),
        "bl": Vector((1, 1)),
        "bc": Vector((0, 1)),
        "br": Vector((1, 1)),
        "none": Vector((0, 0)),
        "cen_v": Vector((1.0, 0.0)),
        "cen_h":  Vector((0.0, 1.0)),
    }
    uv_area_tr = Vector((1.0, 1.0))
    uv_area_bl = Vector((0.0, 0.0))

    pivot_view_3d = {
            'BOUNDING_BOX_CENTER',
            'CURSOR',
            'INDIVIDUAL_ORIGINS',
            'MEDIAN_POINT',
            'ACTIVE_ELEMENT',
    }
    pivot_uv_editor = {
            "CENTER",
            "CURSOR",
            "MEDIAN",
            "INDIVIDUAL_ORIGINS",
        }
    order = {'ONE_BY_ONE', 'OVERALL'}

    global_fit_axis = {
            "tl": 'AUTO',
            "tc": 'U',
            "tr": 'AUTO',
            "lc": 'V',
            "cen": 'AUTO',
            "rc": 'V',
            "bl": 'AUTO',
            "bc": 'U',
            "br": 'AUTO'
        }


class TrSpaceMode:
    """
    Represents transformation direction depends of the current Editor
    and scene level variable tr_space_mode.
    """
    def __init__(self, context, disable=False) -> None:
        self.editor_direction = self._get_tr_space_mode(context, disable)

    def _get_tr_space_mode(self, context, disable) -> int:
        """
        Return 1 for 'IMAGE_EDITOR' of -1 for 'VIEW_3D'
        """
        return -1 if not disable and context.scene.zen_uv.tr_space_mode == "TEXTURE" and context.space_data.type == 'VIEW_3D' else 1


class Cursor2D:

    def __init__(self, context) -> None:
        self.uv_cursor_pos = self._get_uv_cursor_pos(context)

    def _get_uv_cursor_pos(self, context) -> Vector:
        """
        Return 2d cursor position -> Vector or None
        """
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                return area.spaces.active.cursor_location.copy()
        return None

    def set_position(self, context, position: list = [0.0, 0.0]):
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.cursor_location = Vector(position)


class BlPivotPoint:

    @classmethod
    def get(cls, context):
        """
        Return Pivot Point Type
        case VIEW_3D:
            'BOUNDING_BOX_CENTER'
            'CURSOR'
            'INDIVIDUAL_ORIGINS'
            'MEDIAN_POINT'
            'ACTIVE_ELEMENT'

        case IMAGE_EDITOR:
            "CENTER"
            "CURSOR"
            "MEDIAN"
            "INDIVIDUAL_ORIGINS"
        """
        if context.space_data.type == 'VIEW_3D':
            pp = context.scene.tool_settings.transform_pivot_point
            if pp == 'CURSOR':
                if 'IMAGE_EDITOR' in [area.type for area in context.screen.areas]:
                    return pp
                else:
                    return 'BOUNDING_BOX_CENTER'
            return pp
        elif context.space_data.type == 'IMAGE_EDITOR':
            return context.space_data.pivot_point
        return None


class TrOrder:

    @ classmethod
    def from_pivot_point(cls, context, pivot_point):
        pivots = TrConstants.pivot_view_3d.copy()
        pivots.update(TrConstants.pivot_uv_editor)

        if pivot_point in TrConstants.order:
            return pivot_point
        elif pivot_point == 'SYSTEM_PIVOT':
            pivot_point = BlPivotPoint.get(context)

        if pivot_point in pivots:
            if pivot_point in {"INDIVIDUAL_ORIGINS", "ACTIVE_ELEMENT"}:
                return 'ONE_BY_ONE'
            else:
                return 'OVERALL'
        else:
            pivots.update(TrConstants.order)
            message = f'TrOrder.pivot_point (current: {pivot_point}) not in {pivots}'
            raise RuntimeError(message)


class TransformLimitsManager:

    left = None
    right = None
    up = None
    down = None

    results = []

    @classmethod
    def fill(cls, anchor, cluster_bbox, limits_bbox, scale):
        cls.left = DirVector(anchor, cluster_bbox, limits_bbox, 'lc', scale)
        cls.right = DirVector(anchor, cluster_bbox, limits_bbox, 'rc', scale)
        cls.up = DirVector(anchor, cluster_bbox, limits_bbox, 'tc', scale)
        cls.down = DirVector(anchor, cluster_bbox, limits_bbox, 'bc', scale)

    @classmethod
    def get_scale(cls, scale: Vector) -> Vector:
        ''' Return new (independent) scale Vector '''
        if scale.x == scale.y:
            if scale.x < 0 and scale.y < 0:
                return Vector([max(cls.get_min_horizontal_scalar(), cls.get_min_vertical_scalar())] * 2)
            return Vector([min(cls.get_min_horizontal_scalar(), cls.get_min_vertical_scalar())] * 2)
        return Vector((cls.get_min_horizontal_scalar(), cls.get_min_vertical_scalar()))

    @classmethod
    def get_scale_same(cls, scale: Vector) -> Vector:
        ''' Correct input scale Vector and Return corrected (same) scale Vector '''
        if scale.x == scale.y:
            if scale.x < 0 and scale.y < 0:
                _max_value = max(cls.get_min_horizontal_scalar(), cls.get_min_vertical_scalar())
                scale.x = _max_value
                scale.y = _max_value
                return scale
            _min_value = min(cls.get_min_horizontal_scalar(), cls.get_min_vertical_scalar())
            scale.x = _min_value
            scale.y = _min_value
            return scale
        scale.x = cls.get_min_horizontal_scalar()
        scale.y = cls.get_min_vertical_scalar()
        return scale

    @classmethod
    def get_offset_less_zero(cls, offset_axis, mid_axis):
        if offset_axis < mid_axis:
            # Limit reached
            cls.results.append(False)
            return mid_axis
        else:
            cls.results.append(True)
            return offset_axis

    @classmethod
    def get_offset_gret_zero(cls, offset_axis, mid_axis):
        if offset_axis > mid_axis:
            # Limit reached
            cls.results.append(False)
            return mid_axis
        else:
            cls.results.append(True)
            return offset_axis

    @classmethod
    def get_offset(cls, offset):

        if offset.x < 0:
            mid_x = cls.left.mid * -1
            offset.x = cls.get_offset_less_zero(offset.x, mid_x)
        else:
            mid_x = cls.right.mid
            offset.x = cls.get_offset_gret_zero(offset.x, mid_x)
        if offset.y < 0:
            mid_y = cls.down.mid * -1
            offset.y = cls.get_offset_less_zero(offset.y, mid_y)
        else:
            mid_y = cls.up.mid
            offset.y = cls.get_offset_gret_zero(offset.y, mid_y)

        return Vector((offset.x, offset.y))

    @classmethod
    def get_min_vertical_scalar(cls):
        if cls.up.mid <= 0.0 or cls.down.mid <= 0.0:
            cls.results.append(False)
        return cls.up.scalar if cls.up.mid < cls.down.mid else cls.down.scalar

    @classmethod
    def get_min_horizontal_scalar(cls):
        if cls.left.mid <= 0.0 or cls.right.mid <= 0.0:
            cls.results.append(False)
        return cls.left.scalar if cls.left.mid < cls.right.mid else cls.right.scalar


class DirVector:

    def __init__(self, anchor, cl_bbox, lim_bbox, direction, scale) -> None:
        opposite_dir = {
            'lc': 'rc',
            'rc': 'lc',
            'tc': 'bc',
            'bc': 'tc'
        }
        self.horizontal_dir = {'lc', 'rc'}
        self.vertical_dir = {'tc', 'bc'}
        self.axis = self._get_axis(direction)

        mult = -1 if direction in {'lc', 'bc'} else 1
        safe_zone = Vector([0.000001] * 2) * mult

        # LIMIT
        limit = self._get_vector(anchor, lim_bbox, direction) - safe_zone

        # GABARIT
        g_direction, lim_mult = self.calc_gabarit_direction(direction, scale, opposite_dir)
        gabarit = self._get_vector(anchor, cl_bbox, g_direction)

        # MID
        axis_index = 0 if direction in {'lc', 'rc'} else 1
        self.mid = ((limit - gabarit * scale) * mult)[axis_index]

        # SCALAR
        lim_scalar = limit.length / gabarit.length if gabarit.length != 0 else 0
        self.scalar = lim_scalar * lim_mult if self.mid <= 0 else scale[axis_index]

    def calc_gabarit_direction(self, direction, scale, opposite_dir):
        t_scale = scale * self.axis
        if t_scale.x < 0 or t_scale.y < 0:
            return opposite_dir[direction], -1
        return direction, 1

    def _get_vector(self, anchor, bbox, direction):
        return (bbox.get_as_dict()[direction] - anchor) * self.axis

    def _get_axis(self, direction):
        if direction in self.horizontal_dir:
            return Vector((1, 0))
        elif direction in self.vertical_dir:
            return Vector((0, 1))
        else:
            message = "direction = " + direction + " not in {'lc', 'rc', 'tc', 'bc'}"
            raise RuntimeError(message)
