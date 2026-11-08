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

""" Zen UV Generic Functions"""
import bpy
import bmesh
from mathutils import Vector, Euler
from mathutils.geometry import area_tri, tessellate_polygon, intersect_line_line_2d, convex_hull_2d

import itertools
import re
import time
import math
import numpy as np
from dataclasses import dataclass, field

from .vlog import Log
from ..utils.blender_zen_utils import ZenPolls, get_selection_mode, is_loop_domain, is_sync_off
from ..utils.uv_factory import SelectionUtils


PROCESS_FACEMAP_NAME = "ZenUV_InProcess"
PINNED_FACEMAP_NAME = "ZenUV_Pinned"

HOPS_SHOW_UV_FACEMAP_NAME = "HOPS_Show_UV"

ZUV_PANEL_CATEGORY = "Zen UV"
ZUV_REGION_TYPE = "UI"
ZUV_CONTEXT = "mesh_edit"
ZUV_SPACE_TYPE = "VIEW_3D"


class UnitsConverter:

    """ Current system is centimeters based. """

    converter = {
            'km': 100000.0,
            'm': 100.0,
            'cm': 1.0,
            'mm': 0.1,
            'um': 0.0001,
            'mil': 160934.0,
            'ft': 30.48,
            'in': 2.54,
            'th': 0.00254
        }

    rev_con = {
            'km': 0.001,
            'm': 1.0,
            'cm': 100,
            'mm': 1000,
            'um': 1000000,
            'mil': 0.000621371,
            'ft': 3.28084,
            'in': 39.3701,
            'th': 39370.0787
        }

    meters_based = {
            'km': 1000.0,
            'm': 1.0,
            'cm': 0.01,
            'mm': 0.001,
            'um':  0.000001,
            'mil': 1609.344,
            'ft': 0.3048,
            'in': 0.0254,
            'th': 0.0000254
        }

    base_mult = 1.0
    base_unit = 'cm'

    @classmethod
    def get_count_after_point(cls, units: str) -> int:
        s = str(cls.converter[units])
        return abs(s.find('.') - len(s)) - 1

    @classmethod
    def get_mult_for(self, units):
        if self._units_valid(units):
            return self.converter[units] * self.base_mult
        else:
            return None

    @classmethod
    def convert_raw_world_distance(self, distance=None, units='m'):
        if distance and self._units_valid(units):
            return distance * 100 / self.get_mult_for(units)

    @classmethod
    def _units_valid(self, units):
        return units in self.converter.keys()

    def set_base_units(self, unit):
        if not self._units_valid(unit):
            print("Units Converter --> The requested units is not valid.")
            return None
        self.base_mult = 1 / self.converter[unit]
        self.base_unit = unit
        return self.base_mult

    def get_base_units(self):
        base_unit = [key for key in self.converter.keys() if self.converter[key] * self.base_mult == 1]
        if base_unit:
            return base_unit[0]
        return None


class Scope:

    """ Creates dict data wit automatic structure """
    def __init__(self) -> None:
        self.data = {}
        self.name: str = 'Generic Zen Utils Scope'

    def clear(self) -> None:
        """ Clear current state of the Scope """
        self.data = {}

    def is_empty(self) -> None:
        """ Check Scope.data is empty """
        return not len(self.data)

    def show(self) -> None:
        if not len(self.data):
            print(f"\n{self.name}")
            print('Empty', self.data)
        else:
            print(f"\n{self.name} state:\n\n", ''.join(f"{key}: {val}\n" for key, val in self.data.items()))

    def append(self, key: any, value: any) -> None:
        """ Creates dict {key: [value, ]}"""
        if key not in self.data.keys():
            self.data.update({key: [value]})
        else:
            self.data[key].append(value)

    def get_singles_keys(self) -> any:
        """ Return keys where len(values) == 1 """
        for key, value in self.data.items():
            if len(value) == 1:
                yield key

    def get_mults_keys(self) -> any:
        """ Return keys where len(values) > 1 """
        for key, value in self.data.items():
            if len(value) > 1:
                yield key

    def get_mults_values(self) -> any:
        """ Return value from [values, ] where len([values, ]) > 1 """
        for key, value in self.data.items():
            if len(value) > 1:
                for v in value:
                    yield v

    def get_value_with_min_key(self) -> any:
        """ Return value if key is minimal value """
        return self.data[min(self.data.keys())]

    def get_value_with_max_key(self) -> any:
        """ Return value if key is maximal value """
        return self.data[max(self.data.keys())]

    def get_data(self) -> dict:
        """ Return all stored data as dict """
        return self.data


class ZenReport:

    message: str = ''
    message_type: str = ''
    _is_empty: bool = True
    _is_warning: bool = False

    data: dict = dict()

    def __init__(self) -> None:
        self.data = dict()

    @property
    def is_empty(self):
        return True if self.message == '' else False

    @is_empty.setter
    def is_empty(self):
        raise RuntimeError('ZenReport.is_empty read only.')

    @property
    def is_warning(self):
        return True if self.message_type == 'WARNING' else False

    @is_warning.setter
    def is_warning(self):
        raise RuntimeError('ZenReport.is_warning read only.')


class Distortion:

    def get_vector_2d(size=1):
        return Vector((np.random.rand(1, 2) * size).tolist()[0])

    def get_vector_3d(size=1):
        return Vector((np.random.rand(1, 3) * size).tolist()[0])


class MeshBuilder:

    def __init__(self, bm) -> None:
        self.bm = bm

    def create_vertices_3d(self, coors):
        verts = []
        for co in coors:
            verts.append(self.bm.verts.new(co))
        # self.update_mesh()
        return verts

    def create_edge(self, coords):
        if len(coords) == 2:
            verts = self.create_vertices_3d(coords)
            # edges = []
            return self.bm.edges.new(verts)
        else:
            print("Builder: Needed exactly 2 coordinates.")


class ZenKeyEventSolver:

    def __init__(self, context, event, a_prefs) -> None:
        self.current_modifier = a_prefs.zen_key_modifier
        self.event = event

    # @classmethod
    def solve(self):
        if self.event.type == "LEFTMOUSE":
            if self.event.alt and self.current_modifier == "ALT":
                return True
            elif self.event.ctrl and self.current_modifier == "CTRL":
                return True
            elif self.event.shift and self.current_modifier == "SHIFT":
                return True

            else:
                return False

    def __del__(self):
        del self.current_modifier
        del self.event


class Timer:
    ''' Small class to measure run time of critical parts'''
    def __enter__(self):
        self.start = time.process_time()
        return self

    def __exit__(self, *args):
        self.end = time.process_time()
        self.interval = self.end - self.start

    def delta(self, as_float: bool = False):
        if as_float:
            return self.interval
        return "{0:.6f} sec".format(self.interval)


@dataclass
class ZenOperatorPropertiesBase:
    """ Zen Operator Properties Base Class"""

    def __post_init__(self, PROPS) -> None:
        self.get_properties_from(PROPS)

    def get_properties_from(self, PROPS: bpy.types.OperatorProperties) -> None:
        """ Get properties from bpy.types.OperatorProperties class """

        for prp in self.__annotations__.keys():
            attr = getattr(PROPS, prp, None)
            if attr is None:
                Log.debug('From class ZenOperatorPropertiesBase: ', f'Property "{prp}" not present in the {PROPS} Class')
                continue
            setattr(self, prp, attr)


@dataclass
class ZenOperatorProperties(ZenOperatorPropertiesBase):
    """ Zen Operator Factory Properties """

    _report_type: field(default_factory=set)
    _report: str = ''

    def get_report_message(self):
        return self._report

    def report(self, r_type: set, message):
        self._report_type = r_type
        self._report = message

    @property
    def report_type(self):
        return self._report_type

    def __post_init__(self, PROPS) -> None:
        super().__post_init__(PROPS)


class UvImage:

    @classmethod
    def get_uv_area(cls, context):
        return next((area for area in context.window.screen.areas if area.type == 'IMAGE_EDITOR'), None)

    @classmethod
    def get(cls, context: bpy.types.Context):
        area = cls.get_uv_area(context)
        if area is not None:
            return area.spaces.active.image
        else:
            return None

    @classmethod
    def get_aspect(cls, context: bpy.types.Context):
        p_image = cls.get(context)
        if p_image is not None:
            if p_image.size[0] != 0 or p_image.size[1] != 0:
                return p_image.size[1] / p_image.size[0]
        return 1.0


class HideUnhideProcessor:

    @classmethod
    def hide_by_context(cls, context: bpy.types.Context, bm: bmesh.types.BMesh, uv_layer: bmesh.types.BMLayerItem, islands: list, action: str = 'HIDE', b_is_select: bool = False, is_reveal_in_no_sync: bool = False) -> None:
        if action not in {'HIDE', 'UNHIDE'}:
            raise RuntimeError('Variable "action" not in {"HIDE", "UNHIDE"}')

        p_faces = sum(islands, [])

        if is_sync_off(context):
            if action == 'UNHIDE':
                if is_reveal_in_no_sync:
                    cls.unhide_faces(p_faces)
                    for f in p_faces:
                        f.select = True
                SelectionUtils.select_faces_any_context(context, p_faces, state=b_is_select, bm=bm, uv_layer=uv_layer)
            else:
                cls.deselect_faces(p_faces)
        else:
            if action == 'UNHIDE':
                cls.unhide_faces(p_faces)
                SelectionUtils.select_faces_any_context(context, p_faces, state=b_is_select, bm=bm, uv_layer=uv_layer)
            else:
                cls.hide_faces(p_faces)

    @classmethod
    def select_faces(cls, faces: list):
        for face in faces:
            face.select = True

    @classmethod
    def deselect_faces(cls, faces: list):
        for face in faces:
            face.select = False

    @classmethod
    def hide_faces(cls, faces: list):
        for face in faces:
            face.hide_set(True)

    @classmethod
    def unhide_faces(cls, faces: list):
        for face in faces:
            face.hide_set(False)


def calc_uv_editor_image_aspect_ratio(context: bpy.types.Context):
    from ..ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
    p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
    if p_image and p_image.size[0] > 0 and p_image.size[1] > 0:
        return p_image.size[0] / p_image.size[1]
    return 1


def is_edge_select_mode_in_uv(context: bpy.types.Context):
    if ZenPolls.version_since_5_0_0:
        return get_selection_mode(context) == 'EDGE'
    elif ZenPolls.version_since_3_2_0:
        if is_loop_domain(context):
            return get_selection_mode(context) == 'EDGE'
        return False
    return False


def store_loops(bm):
    return [loop for f in bm.faces for loop in f.loops]


def update_loops_indexes(bm):
    loops = [loop for f in bm.faces for loop in f.loops]
    for index, ele in enumerate(loops):
        ele.index = index


def generate_range_values(range_start: float, range_end: float, n: int):
    ''' Creates n- values within given range '''
    step = (range_end - range_start) / (n - 1)
    return [range_start + i * step for i in range(n)]


def map_range(value, from_min, from_max, to_min, to_max):
    try:
        ratio = (value - from_min) / (from_max - from_min)
    except ZeroDivisionError:
        return to_max
    return round(to_min + ratio * (to_max - to_min), 0)


def remap_ranges(value, base_range, new_range):
    reverse = False
    if new_range[0] > new_range[1]:
        reverse = True
    b_min = min(base_range)
    b_max = max(base_range)
    n_min = min(new_range)
    n_max = max(new_range)
    b_range = (b_max - b_min)
    n_range = (n_max - n_min)
    if b_range == 0:
        result = n_min
    else:
        result = (((value - b_min) * n_range) / b_range) + n_min

    if reverse:
        result = new_range[1] + (new_range[0] - result)
    return result


def lerp_two_colors(c1, c2, steps=10):
    return (c1[0]+(c2[0]-c1[0])*steps, c1[1]+(c2[1]-c1[1])*steps, c1[2]+(c2[2]-c1[2])*steps)


def hex_to_RGB(hex):
    ''' "#FFFFFF" -> [255,255,255] '''
    # Pass 16 to the integer function for change of base
    return [int(hex[i:i+2], 16) for i in range(1, 6, 2)]


def RGB_to_hex(RGB):
    ''' [255,255,255] -> "#FFFFFF" '''
    # Components need to be integers for hex to make sense
    if isinstance(RGB[0], float):
        RGB = [round(x * 255) for x in RGB]
    RGB = [int(x) for x in RGB]
    return "#"+"".join(["0{0:x}".format(v) if v < 16 else
                        "{0:x}".format(v) for v in RGB])


def to_hex(c):
    if c < 0.0031308:
        srgb = 0.0 if c < 0.0 else c * 12.92
    else:
        srgb = 1.055 * math.pow(c, 1.0 / 2.4) - 0.055

    return hex(max(min(int(srgb * 255 + 0.5), 255), 0))


def toHex(color):
    rgb = color[:]
    result = ""
    i = 0
    while i < 3:
        val = str(to_hex(rgb[i]))
        val = val[2:]
        if len(val) == 1:
            val += val
        result += val
        i += 1
    return result


def edge_loops_from_uvs(loops, uv_layer):
    """
    Edge loops defined by loops

    Takes [mesh loops] and returns the loop loops
    as lists of loops.
    [ [loop, loop, loop, loop], ...]

    closed loops have matching start and end values.
    """
    s_loop_idxs = {lp.index for lp in loops}

    def loops_from_co(co, loops):
        stripes = []
        for stripe in co:
            sorted_loops = []
            for uv_vert_co in stripe:
                uv_verts = [loop for loop in loops if loop[uv_layer].uv == uv_vert_co]
                sorted_loops.append(uv_verts)
            stripes.append(sorted_loops)
        return stripes

    def collect_uv_edges(uv_layer, loops):
        uv_edges = set()
        for loop in loops:
            next_loop = loop.link_loop_next
            if next_loop.index in s_loop_idxs:
                l1 = loop[uv_layer].uv.copy().freeze()
                l2 = next_loop[uv_layer].uv.copy().freeze()
                if (l2, l1) not in uv_edges:
                    uv_edges.add((l1, l2))
        return uv_edges

    line_polys = []
    unsorted_edges = list(collect_uv_edges(uv_layer, loops))

    while unsorted_edges:
        current_edge = unsorted_edges.pop()
        vert_end, vert_start = current_edge[:]
        line_poly = [vert_start, vert_end]

        ok = True
        while ok:
            ok = False
            i = len(unsorted_edges)
            while i:
                i -= 1
                edge = unsorted_edges[i]
                v1, v2 = edge[:]
                if v1 == vert_end:
                    line_poly.append(v2)
                    vert_end = line_poly[-1]
                    ok = 1
                    del unsorted_edges[i]
                elif v2 == vert_end:
                    line_poly.append(v1)
                    vert_end = line_poly[-1]
                    ok = 1
                    del unsorted_edges[i]
                elif v1 == vert_start:
                    line_poly.insert(0, v2)
                    vert_start = line_poly[0]
                    ok = 1
                    del unsorted_edges[i]
                elif v2 == vert_start:
                    line_poly.insert(0, v1)
                    vert_start = line_poly[0]
                    ok = 1
                    del unsorted_edges[i]

        line_polys.append(line_poly)
    return loops_from_co(line_polys, loops)


def edge_loops_from_bmedges(bmesh, bm_edges):
    """
    Edge loops defined by edges

    Takes [mesh edge indices] and returns the edge loops
    as lists of vertex indices.
    [ [1, 6, 7, 2], ...]

    closed loops have matching start and end values.
    """
    line_polys = []
    unsorted_edges = bm_edges.copy()  # so as not to mutate the input list

    while unsorted_edges:
        current_edge = bmesh.edges[unsorted_edges.pop()]
        vert_e, vert_st = current_edge.verts[:]
        vert_end, vert_start = vert_e.index, vert_st.index
        line_poly = [vert_start, vert_end]

        ok = True  # just to get started
        while ok:
            ok = False
            i = len(unsorted_edges)
            while i:
                i -= 1
                edge = bmesh.edges[unsorted_edges[i]]
                vertex_1, vertex_2 = edge.verts
                v1, v2 = vertex_1.index, vertex_2.index
                if v1 == vert_end:
                    line_poly.append(v2)
                    vert_end = line_poly[-1]
                    ok = 1
                    del unsorted_edges[i]
                    # break
                elif v2 == vert_end:
                    line_poly.append(v1)
                    vert_end = line_poly[-1]
                    ok = 1
                    del unsorted_edges[i]
                    # break
                elif v1 == vert_start:
                    line_poly.insert(0, v2)
                    vert_start = line_poly[0]
                    ok = 1
                    del unsorted_edges[i]
                    # break
                elif v2 == vert_start:
                    line_poly.insert(0, v1)
                    vert_start = line_poly[0]
                    ok = 1
                    del unsorted_edges[i]
                    # break
        line_polys.append(line_poly)
    # print(f"Line Polys: {line_polys}")
    return line_polys


def clear_tag_data(bm):
    """
    clear tag data for all faces in bmesh representation
    """
    for f in bm.faces:
        f.tag = False


def set_tag_data(bm, face_ids):
    """
    tag given faces face.tag
    """
    faces = [bm.faces[_id].index for _id in face_ids if not bm.faces[_id].hide]
    for f_id in faces:
        bm.faces[f_id].tag = True


def get_dir_vector(pos_0, pos_1):
    """ Return direction Vector from 2 Vectors """
    return Vector(pos_1 - pos_0)


def distance_vec(point1: Vector, point2: Vector) -> float:
    """Calculate distance between two points."""
    return (point2 - point1).length


def create_new_mesh(bm, name):
    """ Create New Mesh object in scene based on bm data"""
    mesh_data = bpy.data.meshes.new(name)
    bm.to_mesh(mesh_data)
    obj = bpy.data.objects.new(name, mesh_data)
    scene = bpy.context.scene
    scene.collection.objects.link(obj)


class ResortObjects:

    result: bool = True
    message: str = ''

    @classmethod
    def reset_state(cls):
        cls.result = True
        cls.message = ''

    @staticmethod
    def resort_by_type_mesh_for_stacks(context):
        from ..utils.iter_utils import IterUtils
        return [obj for obj, _, _ in IterUtils.iter_objs_with_bmesh_uv(context.selected_objects, context)]

    @staticmethod
    def resort_by_type_mesh(context):
        return [obj for obj in context.selected_objects if obj.type == 'MESH' and len(obj.data.polygons) != 0]

    @staticmethod
    def resort_by_type_mesh_in_edit_mode_and_sel(context: bpy.types.Context, require_active_uv: bool = False):
        """Return mesh objects in edit mode (or selected in object mode),
        ignoring instances. Optionally skip objects without active UV map."""

        def is_valid(obj):
            me = obj.data

            if require_active_uv and me.uv_layers.active is None:
                return False

            return (
                obj.type == 'MESH'
                and len(me.polygons) != 0
                and not obj.hide_get()
                and not obj.hide_viewport
            )

        if context.mode == 'EDIT_MESH':
            return {obj for obj in context.objects_in_mode_unique_data if is_valid(obj)}
        else:
            t_objects = {
                obj.data: obj
                for obj in context.selected_objects
                if is_valid(obj)
            }
            return t_objects.values()

    @classmethod
    def resort_objects_by_selection(cls, context: bpy.types.Context, objs: list, b_skip_uv_layer_fail: bool = True):
        b_is_loop_domain = is_loop_domain(context)
        if ZenPolls.version_since_5_0_0:
            if b_is_loop_domain:
                if is_sync_off(context):
                    p_objects = []
                    for obj in objs:
                        me: bpy.types.Mesh = obj.data
                        if me.total_face_sel > 0:
                            bm = bmesh.from_edit_mesh(obj.data)
                            uv_layer = bm.loops.layers.uv.active
                            if not b_skip_uv_layer_fail and uv_layer is None:
                                cls.result = False
                                cls.message = 'One or more objects do not have a UV Map'
                                return []
                            if any(True for f in bm.faces if f.uv_select or any(lp.uv_select_vert for lp in f.loops)):
                                p_objects.append(obj)
                    return p_objects
                else:  # UV Sync is on
                    p_objects = []
                    for obj in objs:
                        bm = bmesh.from_edit_mesh(obj.data)
                        uv_layer = bm.loops.layers.uv.active
                        if ZenPolls.version_since_5_0_0 and uv_layer:
                            if not bm.uv_select_sync_valid:
                                bm.uv_select_sync_from_mesh()
                        if not b_skip_uv_layer_fail and uv_layer is None:
                            cls.result = False
                            cls.message = 'One or more objects do not have a UV Map'
                            return []
                        if any(True for f in bm.faces if f.uv_select or any(lp.uv_select_vert for lp in f.loops)):
                            p_objects.append(obj)
                    return p_objects

            else:  # VIEW_3D
                if context.mode in {'EDIT_MESH', 'OBJECT'}:
                    return [obj for obj in objs if sum(obj.data.count_selected_items()) != 0]
        else:  # Below Blender 5.0
            if b_is_loop_domain:
                p_objects = []
                for obj in objs:
                    me: bpy.types.Mesh = obj.data
                    if me.total_face_sel > 0:
                        bm = bmesh.from_edit_mesh(obj.data)
                        uv_layer = bm.loops.layers.uv.active
                        if not b_skip_uv_layer_fail and uv_layer is None:
                            cls.result = False
                            cls.message = 'One or more objects do not have a UV Map'
                            return []
                        if uv_layer:
                            if any(loop[uv_layer].select for f in bm.faces for loop in f.loops if f.select and not f.hide):
                                p_objects.append(obj)
                return p_objects
            else:
                if context.mode in {'EDIT_MESH', 'OBJECT'}:
                    p_objs = []
                    for obj in objs:
                        if not b_skip_uv_layer_fail and not obj.data.uv_layers.active:
                            cls.result = False
                            cls.message = 'One or more objects do not have a UV Map'
                            return []
                        if sum(obj.data.count_selected_items()) != 0:
                            p_objs.append(obj)
                    return p_objs


def get_unique_mesh_object_map_with_active(context):
    return {
        p_obj.data: p_obj
        for p_obj in itertools.chain.from_iterable(
            [
                [context.active_object],
                context.objects_in_mode_unique_data
                if context.mode == 'EDIT_MESH' else
                context.selected_objects])
        if p_obj and p_obj.type == 'MESH'}


def bpy_select_by_context(context: bpy.types.Context, action: str = 'DESELECT', area_type=None):

    if area_type is None:
        p_space = getattr(context, "space_data", None)
        if p_space:
            area_type = p_space.type

    b_is_uv_editor = area_type == 'IMAGE_EDITOR'

    if ZenPolls.version_since_5_0_0:
        if b_is_uv_editor:
            if bpy.ops.uv.select_all.poll():
                bpy.ops.uv.select_all(action=action)
            if context.scene.tool_settings.use_uv_select_sync:
                context.scene.tool_settings.use_uv_select_sync = False
                context.scene.tool_settings.use_uv_select_sync = True
        else:
            if bpy.ops.mesh.select_all.poll():
                bpy.ops.mesh.select_all(action=action)

    else:
        if is_sync_off(context, area_type=area_type):
            if bpy.ops.uv.select_all.poll():
                bpy.ops.uv.select_all(action=action)
        else:
            if bpy.ops.mesh.select_all.poll():
                bpy.ops.mesh.select_all(action=action)


def select_pure_loops(loops, uv_layer, state=True):
    for loop in loops:
        loop[uv_layer].select = state
    if ZenPolls.version_since_3_2_0:
        for loop in loops:
            loop[uv_layer].select_edge = state


def get_padding_in_pct(context, value_px):
    side_min = min(
        context.scene.zen_uv.td_props.TD_TextureSizeX,
        context.scene.zen_uv.td_props.TD_TextureSizeY)
    return value_px / side_min


def get_padding_in_px(context, value_pct):
    side_min = min(
        context.scene.zen_uv.td_props.TD_TextureSizeX,
        context.scene.zen_uv.td_props.TD_TextureSizeY)
    return int(round(value_pct * side_min))


def Diff(li1, li2):
    """ Find difference of two lists """
    li_dif = [i for i in li1 + li2 if i not in li1 or i not in li2]
    return li_dif


def fit_uv_view(context, mode="selected"):
    """ Make Fit UV Viewport depends of specific types """
    addon_prefs = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences
    if addon_prefs.autoFitUV:
        for window in context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == "IMAGE_EDITOR":
                    override = {"window": window, "screen": screen, "area": area}
                    try:
                        if mode == "selected":  # mode - True meant fit to selected
                            bpy.ops.image.view_selected(override)
                        elif mode == "all":  # mode - False meant fit to All
                            bpy.ops.image.view_all(override, fit_view=True)
                        elif mode == "checker":
                            bpy.ops.image.view_zoom_ratio(override, ratio=0.5)
                        area.tag_redraw()
                    except Exception:
                        pass
                    break


def switch_to_edge_sel_mode(context: bpy.types.Context, area_type=None):
    ''' Switch to edge selection mode in any context '''

    if area_type is None:
        p_space = getattr(context, "space_data", None)
        if p_space:
            area_type = p_space.type

    b_is_uv_editor = area_type == 'IMAGE_EDITOR'

    if b_is_uv_editor:
        if context.scene.tool_settings.use_uv_select_sync:
            context.tool_settings.mesh_select_mode = [False, True, False]
        else:
            context.scene.tool_settings.uv_select_mode = "EDGE"
    else:
        context.tool_settings.mesh_select_mode = [False, True, False]


def switch_to_face_sel_mode(context: bpy.types.Context, area_type=None):
    ''' Switch to face selection mode in any context '''

    if area_type is None:
        p_space = getattr(context, "space_data", None)
        if p_space:
            area_type = p_space.type

    b_is_uv_editor = area_type == 'IMAGE_EDITOR'

    if b_is_uv_editor:
        if context.scene.tool_settings.use_uv_select_sync:
            context.tool_settings.mesh_select_mode = [False, False, True]
        else:
            context.scene.tool_settings.uv_select_mode = "FACE"
    else:
        context.tool_settings.mesh_select_mode = [False, False, True]


def switch_to_vert_sel_mode(context: bpy.types.Context, area_type=None):
    ''' Switch to vertex selection mode in any context '''

    if area_type is None:
        p_space = getattr(context, "space_data", None)
        if p_space:
            area_type = p_space.type

    b_is_uv_editor = area_type == 'IMAGE_EDITOR'

    if b_is_uv_editor:
        if context.scene.tool_settings.use_uv_select_sync:
            context.tool_settings.mesh_select_mode = [True, False, False]
        else:
            context.scene.tool_settings.uv_select_mode = "VERTEX"
    else:
        context.tool_settings.mesh_select_mode = [True, False, False]


def update_image_in_uv_layout(context, _image):
    addon_prefs = context.preferences.addons[ZenPolls.ADDON_PACKAGE].preferences
    screen = context.screen
    for area in screen.areas:
        if area.type == 'IMAGE_EDITOR':
            if addon_prefs.ShowCheckerInUVLayout and _image:
                area.spaces.active.image = _image
            else:
                area.spaces.active.image = None


def is_face_flipped(p_face, uv_layer):
    return sum(
        [
            (lp.link_loop_next[uv_layer].uv - lp[uv_layer].uv).cross(lp[uv_layer].uv - lp.link_loop_prev[uv_layer].uv)
            for lp in p_face.loops]) >= 0


def set_face_int_tag(islands, facemap, int_tag):
    """ Set INT tag for given Islands"""
    for face in sum([list(i) for i in islands], []):
        face[facemap] = int_tag


def ensure_facemap(bm, facemap_name):
    """ Return facemap int type or create new """
    facemap = bm.faces.layers.int.get(facemap_name, None)
    if facemap is None:
        facemap = bm.faces.layers.int.new(facemap_name)
    return facemap


def ensure_text_block(name):
    """ Return text block or create new """
    block = bpy.data.texts.get(name)
    if not block:
        block = bpy.data.texts.new(name)
    return block


def remove_facemap(bm, facemap_name):
    facemap = bm.faces.layers.int.get(facemap_name)
    if facemap:
        bm.faces.layers.int.remove(facemap)


def select_faces_by_facemap(bm, facemap_name):
    facemap = bm.faces.layers.int.get(facemap_name)
    faces = None
    if facemap:
        faces = [f for f in bm.faces if f[facemap] == 1]
    if faces:
        for face in faces:
            face.select = True


def set_vcolor_to_display(context):
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.color_type = "VERTEX"
                    return True
    return False


def set_texture_to_display(context):
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.shading.color_type = "TEXTURE"
                    return True
    return False


def _switch(area, style, switch):
    for space in area.spaces:
        if space.type == 'VIEW_3D':
            if space.shading.color_type == "VERTEX" and style == "VERTEX" and switch:
                style = "MATERIAL"
            if space.shading.type != 'WIREFRAME':
                space.shading.color_type = style
            return True
        return False


def switch_shading_style(context, style, switch):
    """ Switch Shading style in current viewport """
    if context.area.type == 'VIEW_3D':
        return _switch(context.area, style, switch)
    else:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                return _switch(area, style, switch)


def get_current_shading_style(context):
    """ Return Shading Style from current viewport """
    if context.area.type == 'IMAGE_EDITOR':
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        return space.shading.color_type
    elif context.area.type == 'VIEW_3D':
        for space in context.area.spaces:
            if space.type == 'VIEW_3D':
                return space.shading.color_type
    else:
        return context.scene.zen_uv_checker.prev_color_type


def view3d_find(context, return_area=False):
    area = context.area
    if area.type == 'VIEW_3D':
        v3d = area.spaces[0]
        rv3d = v3d.region_3d
        for region in area.regions:
            if region.type == 'WINDOW':
                if return_area:
                    return region, rv3d, v3d, area
                return region, rv3d, v3d
    return None, None, None


def find_new_name(value, col):
    if value not in col:
        return value

    def new_val(stem, nbr):
        # simply for formatting
        return '{st}.{nbr:03d}'.format(st=stem, nbr=nbr)

    # see if value is already in a format like 'name.012'
    match = re.match(r'^(.*)\.(\d{3,})$', value)
    if match is None:
        stem, nbr = value, 1
    else:
        stem, nbr = match.groups()
        try:
            nbr = int(nbr)
        except Exception:
            nbr = 1

    # check for each value if in collection
    new_value = new_val(stem, nbr)
    while new_value in col:
        nbr += 1
        new_value = new_val(stem, nbr)

    return new_value


def verify_uv_layer(bm: bmesh.types.BMesh):

    p_names = set(bm.loops.layers.uv.keys())
    s_name = "UVMap"

    p_uv_layer = bm.loops.layers.uv.active
    if not p_uv_layer:
        s_name = find_new_name(s_name, p_names)
        p_uv_layer = bm.loops.layers.uv.new(s_name)

        from ..ops.zen_unwrap.finishing import FINISHED_FACEMAP_NAME
        from ..utils.constants import PACK_EXCLUDED_FACEMAP_NAME

        for fmap_name in {FINISHED_FACEMAP_NAME, PACK_EXCLUDED_FACEMAP_NAME}:
            p_fmap = bm.faces.layers.int.get(fmap_name, None)
            if p_fmap:
                bm.faces.layers.int.remove(p_fmap)

    return p_uv_layer


def has_unapplied_location(obj: bpy.types.Object):
    return obj.location != Vector((0, 0, 0))


def has_unapplied_rotation(obj: bpy.types.Object):
    return obj.rotation_euler != Euler((0, 0, 0), 'XYZ')


def has_unapplied_scale(obj: bpy.types.Object):
    return obj.scale != Vector((1, 1, 1))


def has_unapplied_transform(obj: bpy.types.Object):
    return has_unapplied_location(obj) or has_unapplied_rotation(obj) or has_unapplied_scale(obj)


def check_tri_winding(tri, allowReversed):
    trisq = np.ones((3, 3))
    trisq[:, 0:2] = np.array(tri)
    detTri = np.linalg.det(trisq)
    if detTri < 0.0:
        if allowReversed:
            a = trisq[2, :].copy()
            trisq[2, :] = trisq[1, :]
            trisq[1, :] = a
        else:
            raise ValueError("triangle has wrong winding direction")
    return trisq


def is_overlapped_tri_tri_2d(t1, t2, eps=1e-5, allowReversed=True, onBoundary=False):
    # Trangles must be expressed anti-clockwise
    t1s = check_tri_winding(t1, allowReversed)
    t2s = check_tri_winding(t2, allowReversed)

    if onBoundary:
        # Points on the boundary are considered as colliding
        def chkEdge(x): return np.linalg.det(x) < eps
    else:
        # Points on the boundary are not considered as colliding
        def chkEdge(x): return np.linalg.det(x) <= eps

    # For edge E of trangle 1,
    for i in range(3):
        edge = np.roll(t1s, i, axis=0)[:2, :]

        # Check all points of trangle 2 lay on the external side of the edge E.
        # If they do, the triangles do not collide.
        res = (
            chkEdge(np.vstack((edge, t2s[0]))) and
            chkEdge(np.vstack((edge, t2s[1]))) and
            chkEdge(np.vstack((edge, t2s[2]))))
        if res:
            return False

    # For edge E of trangle 2,
    for i in range(3):
        edge = np.roll(t2s, i, axis=0)[:2, :]

        # Check all points of trangle 1 lay on the external side of the edge E.
        # If they do, the triangles do not collide.
        res = (
            chkEdge(np.vstack((edge, t1s[0]))) and
            chkEdge(np.vstack((edge, t1s[1]))) and
            chkEdge(np.vstack((edge, t1s[2]))))
        if res:
            return False

    # The triangles collide
    return True


def find_overlapped_triangles(triangles):
    overlapped_pairs = []

    for i in range(len(triangles)):
        for j in range(i + 1, len(triangles)):
            triangle1 = triangles[i]
            triangle2 = triangles[j]

            if is_overlapped_tri_tri_2d(triangle1, triangle2):
                overlapped_pairs.append((i, j))
    return overlapped_pairs


def has_overlapped_triangles_by_intersection(triangles):
    for pair in itertools.combinations(triangles, 2):
        if is_overlapped_tri_tri_2d(pair[0], pair[1]):
            return True

    return False


def has_overlapped_triangles_by_area(p_face: bmesh.types.BMFace, triangles: list, uv_layer, tolerance=1e-5):

    if len(p_face.loops) < 4:
        return False

    d_loops_area = sum(
        area_tri(
            p_face.loops[idx[0]][uv_layer].uv,
            p_face.loops[idx[1]][uv_layer].uv,
            p_face.loops[idx[2]][uv_layer].uv)
        for idx in tessellate_polygon([[loop[uv_layer].uv for loop in p_face.loops]]))
    d_tesellated_area = sum(area_tri(*tri[:]) for tri in triangles)

    if not math.isclose(d_loops_area, d_tesellated_area, abs_tol=tolerance):
        return True

    def uv_edges_crossing(loop_points: bmesh.types.BMLoopSeq):
        n = len(loop_points)
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue
                p1, p2 = loop_points[i][uv_layer].uv, loop_points[(i + 1) % n][uv_layer].uv
                p3, p4 = loop_points[j][uv_layer].uv, loop_points[(j + 1) % n][uv_layer].uv
                res = intersect_line_line_2d(p1, p2, p3, p4)
                if res is not None:
                    return True
        return False

    if uv_edges_crossing(p_face.loops):
        return True

    return False


def get_polygon_orientation_2D(polygon_points, by_convex_hull=True):
    # Convert the polygon points to a numpy array
    if by_convex_hull:
        points = np.array([polygon_points[idx] for idx in convex_hull_2d(polygon_points)])
    else:
        points = np.array(polygon_points)

    # Calculate the centroid of the polygon
    centroid = np.mean(points, axis=0)

    # Center the points around the centroid
    centered_points = points - centroid

    # Perform PCA to find the principal axis
    covariance_matrix = np.cov(centered_points, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eig(covariance_matrix)

    # The principal axis is the eigenvector with the highest eigenvalue
    principal_axis = eigenvectors[:, np.argmax(eigenvalues)]

    principal_vector = Vector(principal_axis)

    return principal_vector


def correct_self_intersecting_face(
        context: bpy.types.Context,
        bm: bmesh.types.BMesh,
        p_face: bmesh.types.BMFace,
        uv_layer: bmesh.types.BMLayerItem,
        used_faces: list,
        image_aspect_ratio: float,
        is_island_mode: bool,
        b_is_loop_domain: bool):
    from ..utils.bounding_box import BoundingBox2d
    from ..ops.transform_sys.transform_utils.tr_object_data import get_uv_island_by_face
    from ..ops.transform_sys.transform_utils.transform_loops import TransformLoops
    from ..utils.loops_factory import LoopsFactory

    island = (
        get_uv_island_by_face(p_face, used_faces.copy(), uv_layer, skip_hidden=False)
        if is_island_mode else [p_face])

    p_island_loops = {loop: loop[uv_layer].uv.to_tuple() for it_face in island for loop in it_face.loops}

    p_loops_co = list(p_island_loops.values())
    p_bbox = BoundingBox2d(points=p_loops_co)

    if is_island_mode and len(island) > 2:
        # NOTE: if face is broken it is better to calculate orientation by rest of the island, if there are more faces left
        p_loops_co = [loop[uv_layer].uv.to_tuple() for it_face in island for loop in it_face.loops if it_face != p_face]

    bpy_select_by_context(context, action='DESELECT')

    if b_is_loop_domain:
        LoopsFactory.select_loops(context, bm, p_island_loops.keys(), uv_layer, state=True)
    else:
        it_face: bmesh.types.BMFace
        for it_face in island:
            if it_face.hide:
                it_face.hide_set(False)
            it_face.select_set(True)

    was_orientation = get_polygon_orientation_2D(p_loops_co, by_convex_hull=False)

    t_seams = {}
    if is_island_mode:
        if len(island) > 1:
            # NOTE: let's remark by current Island to avoid Cube situation, when unwrap is failed
            t_seams = {edge: edge.seam for it_face in island for edge in it_face.edges}
            bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)

    bpy.ops.uv.unwrap(
        method='CONFORMAL',
        fill_holes=True,
        margin_method='SCALED',
        margin=0.001,
        use_subsurf_data=False,
        correct_aspect=True
    )

    if t_seams:
        for it_edge, it_seam in t_seams.items():
            it_edge.seam = it_seam

    # NOTE: loops after unwrap
    p_new_island_loops = {loop: loop[uv_layer].uv.to_tuple() for it_face in island for loop in it_face.loops}
    p_new_loops_co = list(p_new_island_loops.values())

    cur_orientation = get_polygon_orientation_2D(p_new_loops_co, by_convex_hull=False)

    reference_vector = Vector((0, 1))
    was_angle_deg = round(math.degrees(was_orientation.angle_signed(reference_vector, 0)))
    new_angle_deg = round(math.degrees(cur_orientation.angle_signed(reference_vector, 0)))

    restoration_angle = 0
    angle_diff = 0
    if was_angle_deg != new_angle_deg:
        # NOTE: we avoid the case when difference is 180°, so let be as is
        angle_diff = abs(was_angle_deg - new_angle_deg) % 360
        if angle_diff > 180:
            angle_diff -= 360
        if angle_diff != 180:
            restoration_angle = was_orientation.angle_signed(cur_orientation, 0)

    # NOTE: if new unwrapped island is in 90° position and difference with old angle is small, let's accept new position
    if new_angle_deg % 90 == 0:
        if abs(angle_diff) < 5:
            restoration_angle = 0

    _ = TransformLoops.fit_loops(
        list(p_new_island_loops.keys()),
        uv_layer,
        p_bbox,
        fit_axis_name='AUTO',
        angle=restoration_angle,
        image_aspect=image_aspect_ratio,
        move=True,
        rotate=True,
        scale=True
    )


if __name__ == "__main__":
    pass
