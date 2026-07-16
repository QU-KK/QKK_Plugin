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

# Copyright 2021, Alex Zhornyak

""" Zen Blender Utils """

import bpy
import blf
from mathutils import Matrix, Vector
import gpu
from gpu_extras.batch import batch_for_shader

import platform
import functools
import os
import re
import math
import uuid
import pickle
import zlib
from dataclasses import dataclass, field
import itertools
from enum import IntEnum
import subprocess

from .vlog import Log

app_version = bpy.app.version

EXEC_BLENDER_OPERATOR_ARGUMENTS = 'from mathutils import Vector, Matrix, Color, Euler, Quaternion'


class ZenPolls:
    ADDON_PACKAGE = "ZenUV"

    # API:
    # - Event - mouse_prev_x, mouse_prev_y
    version_since_3_0_0 = app_version >= (3, 0, 0)

    version_since_3_2_0 = app_version >= (3, 2, 0)

    # Reason: Operator: bpy.app.is_job_running
    version_since_3_3_0 = app_version >= (3, 3, 0)

    version_lower_3_4_0 = app_version < (3, 4, 0)

    version_lower_3_5_0 = app_version < (3, 5, 0)
    version_equal_3_6_0 = app_version == (3, 6, 0)
    version_greater_3_6_0 = app_version > (3, 6, 0)

    # GPU unique shaders names, operators only through 'temp_override'
    version_since_4_0_0 = app_version >= (4, 0, 0)

    version_since_4_1_0 = app_version >= (4, 1, 0)

    # NEW: extensions
    version_since_4_2_0 = app_version >= (4, 2, 0)

    # Theme: 'widget_label' was changed to 'tooltip'
    version_lower_4_3_0 = app_version < (4, 3, 0)

    # for Math Vis
    version_lower_4_4_0 = app_version < (4, 4, 0)

    # Will be taken from bl_info['doc_url'] !!!
    doc_url = ''

    # Will be taken from bl_info['traker_url'] !!!
    support_url = ""

    donate_url = "https://www.patreon.com/zenmasters_blender/membership"

    # Will be taken from 'ZenMastersTeam/Zen-UV/main/README.md'
    new_addon_version = None

    SESSION_UUID = None

    # Will be taken from Preferences
    n_panel_name = ''

    @classmethod
    def register_session(cls):
        cls.SESSION_UUID = str(uuid.uuid4())

    @classmethod
    def unregister_session(cls):
        cls.SESSION_UUID = None

    @classmethod
    def internet_enabled(cls):
        return bpy.app.online_access if hasattr(bpy.app, "online_access") else True

    @classmethod
    def is_zen_sets_present(cls):
        return hasattr(bpy.types, bpy.ops.zsts.assign_to_group.idname())

    map_operator_defaults = {
        "UV_OT_zenuv_quadrify": {
            "influence", "edge_length_mode", "shape", "average_shape", "use_selected_edges",
            "skip_non_quads", "mark_borders", "mark_seams", "mark_sharp", "orient", "algorithm",
            "post_td_mode", "use_pack_islands", "auto_pin", "tag_finished", "is_correct_aspect",
            "quadrify_edge_detection_limit"},
        "UV_OT_zenuv_unwrap": {
            "MarkUnwrapped", "ProcessingMode", "packAfUnwrap", "post_td_mode", "fill_holes",
            "correct_aspect", "markSeamEdges", "markSharpEdges", "UnwrapMethod"},
        "UV_OT_zenuv_world_orient": {"further_orient"},
        "UV_OT_zenuv_fit_to_trim_hotspot": {
            "trims_preselection", "orient", "priority", "area_match", "manual_scale", "allow_rotation",
            "allow_rotation_variation", "allow_location_variation", "allow_offset_variation",
            "allow_flip_variation", "loc_var_offset", "fit_axis", "inset_mode", "inset", "seed", "keep_proportion",
            "detect_radial", "select_radials", "aspect_precision", "allow_variability"}
        }

    operator_defaults = dict()

    @classmethod
    def get_operator_defaults(cls, idname, propname, default):
        if idname in cls.operator_defaults:
            return cls.operator_defaults[idname].get(propname, default)
        return default


@dataclass
class CallerCmdProps:
    bl_op_cls: bpy.types.Operator = None
    bl_label: str = None
    bl_desc: str = None
    cmd: str = None
    undo: bool = False
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)


class ZenCompat:
    @classmethod
    def blf_font_size(cls, font_size, ui_scale):
        p_font_size = font_size * ui_scale
        if app_version < (3, 1, 0):
            p_font_size = round(p_font_size)

        if app_version < (3, 4, 0):
            blf.size(0, p_font_size, 72)
        else:
            blf.size(0, p_font_size)

    @classmethod
    def get_2d_smooth_color(cls):
        return '2D_SMOOTH_COLOR' if ZenPolls.version_lower_3_5_0 else 'SMOOTH_COLOR'

    @classmethod
    def get_3d_smooth_color(cls):
        return '3D_SMOOTH_COLOR' if ZenPolls.version_lower_3_5_0 else 'SMOOTH_COLOR'

    @classmethod
    def get_3d_polyline_uniform(cls):
        return '3D_POLYLINE_UNIFORM_COLOR' if ZenPolls.version_lower_3_5_0 else 'POLYLINE_UNIFORM_COLOR'

    @classmethod
    def get_2d_polyline_smooth(cls):
        return '2D_POLYLINE_SMOOTH_COLOR' if ZenPolls.version_lower_3_5_0 else 'POLYLINE_SMOOTH_COLOR'

    @classmethod
    def get_3d_polyline_smooth(cls):
        return '3D_POLYLINE_SMOOTH_COLOR' if ZenPolls.version_lower_3_5_0 else 'POLYLINE_SMOOTH_COLOR'

    @classmethod
    def get_2d_polyline_uniform(cls):
        return '2D_POLYLINE_UNIFORM_COLOR' if ZenPolls.version_lower_3_5_0 else 'POLYLINE_UNIFORM_COLOR'

    @classmethod
    def get_2d_uniform_color(cls):
        return '2D_UNIFORM_COLOR' if ZenPolls.version_lower_3_5_0 else 'UNIFORM_COLOR'

    @classmethod
    def get_3d_uniform_color(cls):
        return '3D_UNIFORM_COLOR' if ZenPolls.version_lower_3_5_0 else 'UNIFORM_COLOR'


class ZenDrawConstants:
    DEFAULT_VERT_ACTIVE_ALPHA = 80
    DEFAULT_VERT_INACTIVE_ALPHA = 60
    DEFAULT_VERT_ACTIVE_POINT_SIZE = 10
    DEFAULT_VERT_INACTIVE_POINT_SIZE = 6
    DEFAULT_VERT_USE_ZOOM_FACTOR = False

    DEFAULT_EDGE_ACTIVE_ALPHA = 60
    DEFAULT_EDGE_INACTIVE_ALPHA = 40
    DEFAULT_EDGE_ACTIVE_LINE_WIDTH = 3
    DEFAULT_EDGE_INACTIVE_LINE_WIDTH = 2

    DEFAULT_FACE_ACTIVE_ALPHA = 60
    DEFAULT_FACE_INACTIVE_ALPHA = 40

    DEFAULT_OBJECT_ACTIVE_ALPHA = 40
    DEFAULT_OBJECT_INACTIVE_ALPHA = 20
    DEFAULT_OBJECT_COLLECTION_BOUNDBOX_WIDTH = 2
    DEFAULT_OBJECT_COLLECTION_LABEL_SIZE = 12

    BGL_ACTIVE_FONT_COLOR = (0.855, 0.141, 0.07)  # Zen Red Color
    BGL_INACTIVE_FONT_COLOR = (0.8, 0.8, 0.8)

    GIZMO_ICON_SIZE = 28
    GIZMO_SIZE = 30

    GIZMO_COLUMN_INDICES = {
        "TRIM_SELECTOR": 6,
        "UPDATE_DRAW": 7,
        "STICKY": 8,
        "UV_COVERAGE": 9,
        "TOOL_TRANSFORM": 10,
    }

    GIZMO_BTN_SIZE = 24

    # NOTE: SVG icon width is 20px, 14px is equal to 0.0039... internal units
    WIDTH_14_PX = 0.0039511919021606445
    GIZMO_BTN_ICON_14_PX = 14 * (GIZMO_BTN_SIZE / 20)
    GIZMO_BTN_ICON_SCALE_FACTOR = GIZMO_BTN_ICON_14_PX / WIDTH_14_PX

    DRAW_ICON_BATCHES = {}

    icon_shader = gpu.shader.from_builtin(ZenCompat.get_2d_uniform_color())

    @classmethod
    def get_ui_icon_batch(cls, s_identifier: str):
        if s_identifier not in cls.DRAW_ICON_BATCHES:

            cls.DRAW_ICON_BATCHES[s_identifier] = None

            try:
                s_icon_id = s_identifier

                ico_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../ico/standard")
                icon_file = os.path.join(ico_dir, s_icon_id.lower() + ".pkz")
                if os.path.exists(icon_file):
                    with open(icon_file, 'rb') as file:
                        compressed_data = file.read()
                        t_data = pickle.loads(zlib.decompress(compressed_data))

                        p_coords = t_data['coords']

                        # NOTE: used for detecting real width and height
                        # x_min = min(p_coords)[0]
                        # y_min = min(p_coords)[1]

                        # x_max = max(p_coords)[0]
                        # y_max = max(p_coords)[1]

                        cls.DRAW_ICON_BATCHES[s_icon_id] = batch_for_shader(
                            cls.icon_shader, 'TRIS', {
                                "pos": p_coords}, indices=t_data['indices'])
                else:
                    raise RuntimeError("Source icon data does not exist!")
            except Exception as e:
                Log.error("GENERATE ICON:", s_identifier, e)

        return cls.DRAW_ICON_BATCHES[s_identifier]


def get_zen_platform():
    s_system = platform.system()
    if s_system == 'Darwin':
        try:
            import sysconfig
            if 'arch64-apple-darwin' in sysconfig.get_config_vars()['HOST_GNU_TYPE']:
                s_system = 'DarwinSilicon'

        except Exception as e:
            Log.error(e)
    return s_system


def extract_arguments_to_py(*args, **kwargs):
    return args, kwargs


def get_command_props(cmd, context=bpy.context, use_last_properties=True) -> CallerCmdProps:

    op_props = CallerCmdProps()

    if cmd:
        op_cmd = cmd
        op_args = '()'

        cmd_split = cmd.split("(", 1)
        if len(cmd_split) == 2:
            op_cmd = cmd_split[0]
            op_args = '(' + cmd_split[1]

            if len(cmd_split[1]) > 1:
                s_args = cmd_split[1][:-1]
                exec(EXEC_BLENDER_OPERATOR_ARGUMENTS)
                args, kwargs = eval('extract_arguments_to_py(' + s_args + ')')
                op_props.args = args
                op_props.undo = True in args

                try:
                    if use_last_properties:
                        wm = context.window_manager
                        op_cmd_short = op_cmd.replace("bpy.ops.", "", 1)
                        op_last = wm.operator_properties_last(op_cmd_short)
                        if op_last:
                            props = op_last.bl_rna.properties
                            keys = set(props.keys()) - {'rna_type'}
                            for k in keys:
                                if k not in kwargs:
                                    kwargs[k] = getattr(op_last, k)

                    op_props.kwargs = kwargs
                except Exception as e:
                    Log.error('BUILD KWARGS', cmd, e)

        op_cmd_short = op_cmd.replace("bpy.ops.", "", 1)
        op_cmd = f"bpy.ops.{op_cmd_short}"

        try:
            if op_args == '()':
                if use_last_properties:
                    wm = context.window_manager
                    op_last = wm.operator_properties_last(op_cmd_short)
                    if op_last:
                        props = op_last.bl_rna.properties
                        keys = set(props.keys()) - {'rna_type'}
                        args = [
                            k + '=' + repr(getattr(op_last, k))
                            for k in dir(op_last)
                            if k in keys and not props[k].is_readonly and not props[k].is_skip_save]

                        if len(args):
                            op_args = f'({",".join(args)})'

            exec(EXEC_BLENDER_OPERATOR_ARGUMENTS)
            op_props.bl_op_cls = eval(op_cmd)
            op_props.cmd = op_cmd + op_args

            try:
                rna = op_props.bl_op_cls.get_rna().rna_type \
                    if hasattr(op_props.bl_op_cls, "get_rna") \
                    else op_props.bl_op_cls.get_rna_type()

                op_props.bl_label = rna.name
                op_props.bl_desc = rna.description
            except Exception as ex:
                Log.warn('Description error:', ex)

        except Exception as ex:
            op_props = CallerCmdProps()
            Log.error('Eval error:', ex, 'cmd:', cmd)

    return op_props


# using wonder's beautiful simplification: https://stackoverflow.com/questions/31174295/getattr-and-setattr-on-nested-objects/31174427?noredirect=1#comment86638618_31174427
def rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)
    return functools.reduce(_getattr, [obj] + attr.split('.'))


def rsetattr(obj, attr, val):
    pre, _, post = attr.rpartition('.')
    return setattr(rgetattr(obj, pre) if pre else obj, post, val)


def getattr_for_repr(p_instance, s_attr_name):
    p_val = getattr(p_instance, s_attr_name)
    try:
        # NOTE: convert thin wrapped sequences
        # to simple lists to repr()
        p_val = p_val[:]
    except Exception:
        pass
    return p_val


class ZuvPresets:

    LITERAL_OPERATOR_DEFAULTS = "operator_defaults"

    @classmethod
    def get_preset_path(cls, s_preset_subdir):
        return os.path.join('zen_uv', s_preset_subdir)

    @classmethod
    def get_full_preset_path(cls, s_preset_dir):
        target_path = os.path.join("presets", cls.get_preset_path(s_preset_dir))
        target_path = bpy.utils.user_resource('SCRIPTS', path=target_path, create=False)
        return target_path

    @classmethod
    def force_full_preset_path(cls, s_preset_dir):
        target_path = os.path.join("presets", cls.get_preset_path(s_preset_dir))
        target_path = bpy.utils.user_resource('SCRIPTS', path=target_path, create=True)

        if not target_path:
            raise RuntimeError(f"Can not find or create: {s_preset_dir}")

        return target_path


class ZsOperatorAttrs:
    @classmethod
    def get_operator_attr(cls, op_name, attr_name, default=None):
        wm = bpy.context.window_manager
        op_last = wm.operator_properties_last(op_name)
        if op_last:
            return getattr(op_last, attr_name, default)
        return default

    @classmethod
    def set_operator_attr(cls, op_name, attr_name, value):
        wm = bpy.context.window_manager
        op_last = wm.operator_properties_last(op_name)
        if op_last:
            setattr(op_last, attr_name, value)

    @classmethod
    def get_operator_attr_int_enum(cls, op_name, attr_name, default, p_items):
        p_val = cls.get_operator_attr(op_name, attr_name, default)
        for i, item in enumerate(p_items):
            if item[0] == p_val:
                return i
        return 0

    @classmethod
    def set_operator_attr_int_enum(cls, op_name, attr_name, value, p_items):
        for i, item in enumerate(p_items):
            if i == value:
                cls.set_operator_attr(op_name, attr_name, item[0])


def get_region_width(context: bpy.types.Context, rgn_type: str):
    t_rgn = [region.width for region in context.area.regions if region.type == rgn_type]
    return t_rgn[0] if t_rgn else 0


def get_ui_region_width(context: bpy.types.Context):
    return get_region_width(context, "UI")


def get_tools_region_width(context: bpy.types.Context):
    return get_region_width(context, "TOOLS")


def update_areas_in_all_screens(context: bpy.types.Context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in {'VIEW_3D', 'IMAGE_EDITOR'}:
                area.tag_redraw()


def update_areas_in_uv(context: bpy.types.Context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.tag_redraw()


def on_prop_update_uv(self, context: bpy.types.Context):
    update_areas_in_uv(context)


def update_areas_in_view3d(context: bpy.types.Context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _collection_from_element(self):
    # this gets the collection that the element is in
    path = self.path_from_id()
    match = re.match(r'(.*)\[\d*\]', path)
    parent = self.id_data
    try:
        coll_path = match.group(1)
    except AttributeError:
        raise TypeError("Propery not element in a collection.")
    else:
        return parent.path_resolve(coll_path)


def _setnameex(self, value, collection_from_element=_collection_from_element):

    def new_val(stem, nbr):
        # simply for formatting
        return '{st}.{nbr:03d}'.format(st=stem, nbr=nbr)

    # =====================================================
    if value == self.get('name', ''):
        # check for assignement of current value
        return

    coll = collection_from_element(self)
    if value not in coll:
        # if value is not in the collection, just assign
        self['name'] = value
        return

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
    while new_value in coll:
        nbr += 1
        new_value = new_val(stem, nbr)

    self['name'] = new_value


def setnameex(self, value):
    _setnameex(self, value)


def calc_pixel_size(context: bpy.types.Context, co):
    # returns size in blender units of a pixel at 3d coord co
    # see C code in ED_view3d_pixel_size and ED_view3d_update_viewmat
    m = context.region_data.perspective_matrix
    v1 = m[0].to_3d()
    v2 = m[1].to_3d()
    ll = min(v1.length_squared, v2.length_squared)
    len_pz = 2.0 / math.sqrt(ll)
    len_sz = max(context.region.width, context.region.height)
    rv3dpixsize = len_pz / len_sz
    proj = m[3][0] * co[0] + m[3][1] * co[1] + m[3][2] * co[2] + m[3][3]
    ups = context.preferences.system.pixel_size
    return proj * rv3dpixsize * ups


def get_view_1px_from_region(context: bpy.types.Context, region_co: Vector):
    rgn2d = context.region.view2d
    v_rgn_to_2d = Vector(rgn2d.region_to_view(region_co.x, region_co.y))
    v_rgn_to_2d_1px = Vector(rgn2d.region_to_view(region_co.x + 1, region_co.y + 1))
    v_view_1px = v_rgn_to_2d_1px - v_rgn_to_2d
    return v_view_1px


def draw_ex_last_operator_properties(context: bpy.types.Context, op_id, layout: bpy.types.UILayout):
    wm = context.window_manager
    op_last = wm.operator_properties_last(op_id)
    if op_last:
        op = bpy.types.Operator.bl_rna_get_subclass_py(op_last.__class__.__name__)
        if op:
            op.draw_ex(op_last, layout, context)


def prop_with_icon(p_layout: bpy.types.UILayout, p_data, s_prop, s_icon, s_icon_operator_id=""):
    row = p_layout.row(align=True)
    r = row.split(factor=1.5/4)
    r1 = r.row(align=True)
    r1.alignment = 'RIGHT'
    if s_icon_operator_id:
        r1.operator(s_icon_operator_id, text='', icon=s_icon)
    else:
        r1.label(text='', icon=s_icon)
    r2 = r.row(align=True)
    r2.alignment = 'LEFT'
    r2.prop(p_data, s_prop)


class ZenStrUtils:
    @classmethod
    def ireplace(cls, text, find, repl):
        return re.sub('(?i)' + re.escape(find), lambda m: repl, text)

    @classmethod
    def smart_replace(cls, text, props):
        err = ''
        new_name = ''
        try:
            if props.find != '':
                if props.use_regex:
                    new_name = re.sub(props.find, props.replace, text)
                else:
                    if props.match_case:
                        new_name = text.replace(props.find, props.replace)
                    else:
                        new_name = cls.ireplace(text, props.find, props.replace)
            else:
                new_name = props.replace
        except Exception as e:
            err = str(e)

        if new_name == '':
            new_name = text

        return (new_name, err)


def matrix_flatten(m: Matrix):
    return tuple(itertools.chain(*m.col))


def matrix_unflatten(array):
    size = len(array)
    if size == 16:
        m = Matrix.Identity(4)
        m.col[0] = array[0:4]
        m.col[1] = array[4:8]
        m.col[2] = array[8:12]
        m.col[3] = array[12:16]
    elif size == 9:
        m = Matrix.Identity(3)
        m.col[0] = array[0:3]
        m.col[1] = array[3:6]
        m.col[2] = array[6:9]
    elif size == 4:
        m = Matrix.Identity(2)
        m.col[0] = array[0:2]
        m.col[1] = array[2:4]
    return m


def matrix_from_float_vector_16(array):
    size = len(array)
    if size == 16:
        m = Matrix.Identity(4)
        m.col[0] = array[0:4]
        m.col[1] = array[4:8]
        m.col[2] = array[8:12]
        m.col[3] = array[12:16]
    elif size == 9:
        m = Matrix.Identity(3)
        m.col[0] = array[0:3]
        m.col[1] = array[3:6]
        m.col[2] = array[6:9]
    elif size == 4:
        m = Matrix.Identity(2)
        m.col[0] = array[0:2]
        m.col[1] = array[2:4]
    return m


def open_document(filepath):
    if platform.system() == 'Darwin':       # macOS
        subprocess.call(('open', filepath))
    elif platform.system() == 'Windows':    # Windows
        os.startfile(filepath)
    else:                                   # linux variants
        subprocess.call(('xdg-open', filepath))


class ZsViewLayerStoredType(IntEnum):
    HideSelect = 0,
    HideViewport = 1,
    HideGet = 2,
    SelectGet = 3,
    WasEditable = 4


def save_viewlayer_layers_state(parent_layer, layers_state):
    for child_layer in parent_layer.children:
        layers_state[child_layer.name] = (child_layer.exclude, child_layer.hide_viewport)
        save_viewlayer_layers_state(child_layer, layers_state)


def show_all_viewlayers(parent_layer):
    for child_layer in parent_layer.children:
        child_layer.exclude = False
        child_layer.hide_viewport = False
        show_all_viewlayers(child_layer)


def restore_viewlayer_layers(parent_layer, layers_state):
    for child_layer in parent_layer.children:
        if child_layer.name in layers_state:
            is_excluded, is_viewport_hidden = layers_state[child_layer.name]
            if child_layer.exclude != is_excluded:
                child_layer.exclude = is_excluded
            if child_layer.hide_viewport != is_viewport_hidden:
                child_layer.hide_viewport = is_viewport_hidden
        restore_viewlayer_layers(child_layer, layers_state)


def save_viewlayer_objects_state():
    view_layer = bpy.context.view_layer
    act_obj_name = view_layer.objects.active.name if view_layer.objects.active else ''
    were_objects = {obj.name: (obj.hide_select,
                               obj.hide_viewport,
                               obj.hide_get(),
                               obj.select_get(),
                               obj.data.is_editmode if obj.type == 'MESH' else (act_obj_name == obj.name))
                    for obj in view_layer.objects}
    return (were_objects, act_obj_name)


def restore_viewlayer_objects(were_objects):
    obj_list = bpy.context.view_layer.objects
    for obj_name, obj_data in were_objects.items():
        obj = obj_list.get(obj_name)
        if obj:
            if obj.hide_get() != obj_data[ZsViewLayerStoredType.HideGet]:
                obj.hide_set(obj_data[ZsViewLayerStoredType.HideGet])

            if obj.hide_select != obj_data[ZsViewLayerStoredType.HideSelect]:
                obj.hide_select = obj_data[ZsViewLayerStoredType.HideSelect]
            if obj.hide_viewport != obj_data[ZsViewLayerStoredType.HideViewport]:
                obj.hide_viewport = obj_data[ZsViewLayerStoredType.HideViewport]

            if obj.select_get() != obj_data[ZsViewLayerStoredType.SelectGet]:
                obj.select_set(obj_data[ZsViewLayerStoredType.SelectGet])
        else:
            Log.error('Can not restore:', obj_name)


def ensure_object_in_viewlayer(obj, parent_layer):
    if obj.hide_viewport:
        obj.hide_viewport = False
    if obj.hide_select:
        obj.hide_select = False

    for child_layer in parent_layer.children:
        if obj.name in child_layer.collection.all_objects[:]:
            if child_layer.exclude:
                child_layer.exclude = False
            if child_layer.hide_viewport:
                child_layer.hide_viewport = False
            if child_layer.collection.hide_select:
                child_layer.collection.hide_select = False

        ensure_object_in_viewlayer(obj, child_layer)


def unhide_and_select_all_viewlayer_objects(act_obj_name):
    view_layer = bpy.context.view_layer
    for obj in view_layer.objects:
        if obj.type == 'MESH':
            if obj.hide_viewport:
                obj.hide_viewport = False
            if obj.hide_select:
                obj.hide_select = False
            if obj.hide_get():
                obj.hide_set(False)
            if not obj.select_get():
                obj.select_set(True)
        if obj.name == act_obj_name:
            view_layer.objects.active = obj


def prepare_stored_objects_for_edit(were_objects, act_obj_name):
    view_layer = bpy.context.view_layer
    for obj in view_layer.objects:
        if obj.name in were_objects:
            was_in_edit_mode = were_objects[obj.name][ZsViewLayerStoredType.WasEditable]
            if was_in_edit_mode:
                try:
                    if obj.hide_viewport:
                        obj.hide_viewport = False
                    if obj.hide_select:
                        obj.hide_select = False
                    if obj.hide_get():
                        obj.hide_set(False)
                    if not obj.select_get():
                        obj.select_set(True)
                except Exception:
                    pass
            else:
                try:
                    b_hide_viewport = were_objects[obj.name][ZsViewLayerStoredType.HideViewport]
                    if b_hide_viewport != obj.hide_viewport:
                        obj.hide_viewport = b_hide_viewport
                    b_hide_select = were_objects[obj.name][ZsViewLayerStoredType.HideSelect]
                    if b_hide_select != obj.hide_select:
                        obj.hide_select = b_hide_select
                    b_hide_get = were_objects[obj.name][ZsViewLayerStoredType.HideGet]
                    if obj.hide_get() != b_hide_get:
                        obj.hide_set(b_hide_get)
                    if obj.select_get():
                        obj.select_set(False)
                except Exception:
                    pass

        if obj.name == act_obj_name:
            view_layer.objects.active = obj


def show_message_box(message="", title="Message Box", icon='INFO'):

    def zenuv_show_message_draw(self, context: bpy.types.Context):
        layout: bpy.types.UILayout = self.layout
        for line in message.splitlines():
            layout.label(text=line)

    bpy.context.window_manager.popup_menu(zenuv_show_message_draw, title=title, icon=icon)


def reset_properties_modified(obj_prop: bpy.types.bpy_struct):
    for k in obj_prop.bl_rna.properties.keys():
        try:
            if obj_prop.is_property_set(k):
                obj_prop.property_unset(k)
        except Exception as e:
            Log.error('RESET PROPERTY:', e)


class ZenModeSwitcher:
    def __init__(self, mode='OBJECT'):
        self.were_objects, self.act_obj_name = save_viewlayer_objects_state()
        ctx_mode = bpy.context.mode
        if ctx_mode == 'OBJECT':
            self.was_mode = 'OBJECT'
        else:
            self.was_mode = 'EDIT'
        if mode != self.was_mode:
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode=mode)

    def return_to_edit_mode(self):
        prepare_stored_objects_for_edit(self.were_objects, self.act_obj_name)
        bpy.ops.object.mode_set(mode='EDIT')
        restore_viewlayer_objects(self.were_objects)

    def return_to_mode(self):
        if self.was_mode == 'EDIT':
            prepare_stored_objects_for_edit(self.were_objects, self.act_obj_name)
        if bpy.ops.object.mode_set.poll():
            bpy.ops.object.mode_set(mode=self.was_mode)
        restore_viewlayer_objects(self.were_objects)


def get_gizmo_scale(context: bpy.types.Context):
    d_gizmo_size = context.preferences.view.gizmo_size
    ui_scale = context.preferences.system.ui_scale
    return (d_gizmo_size / 75) * (ui_scale / 1)


def is_uv_snap_enabled(scene: bpy.types.Scene, b_tweak_snap):
    return (
        (scene.tool_settings.use_snap_uv and not b_tweak_snap) or
        (not scene.tool_settings.use_snap_uv and b_tweak_snap))
