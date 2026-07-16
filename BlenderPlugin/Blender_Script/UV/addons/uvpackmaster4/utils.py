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


import os
import json
import traceback
import sys
import textwrap

from .os_iface import os_exec_dirname, os_exec_extension

from .app_iface import *


def get_multi_panel_manager(context):
    from .multi_panel_manager import MultiPanelManager
    return MultiPanelManager.get(context)


def get_engine_path():
    return get_prefs().engine_path


def get_engine_execpath():
    engine_basename = 'uvpm'
    return os.path.join(get_engine_path(), os_exec_dirname(), engine_basename + os_exec_extension())


def process_file_path(file_path):
    return os.path.realpath(file_path)


def in_debug_mode(debug_lvl=1):
    return AppInterface.debug_value() >= debug_lvl or AppInterface.debug()


def split_by_chars(str, cnt):
    str_split = str.split()

    array = []
    curr_str = ''
    curr_cnt = 0

    for word in str_split:
        curr_str += ' ' + word
        curr_cnt += len(word)

        if curr_cnt > cnt:
            array.append((curr_str))
            curr_str = ''
            curr_cnt = 0

    if curr_str != '':
        array.append((curr_str))

    return array
        

def remove_whitespace(s):
    return "".join(ch for ch in s if not ch.isspace())


def remove_non_alpha(s):
    return "".join(ch for ch in s if not ch.isalpha())


def print_backtrace(ex):
    print('[UVPACKMASTER ERROR BEGIN]:')
    _, _, trback = sys.exc_info()
    traceback.print_tb(trback)
    trbackDump = traceback.extract_tb(trback)
    filename, line, func, msg = trbackDump[-1]

    print('Line: {} Message: {}'.format(line, msg))
    print(str(ex))
    print('[UVPACKMASTER ERROR END]')


def print_backtrace_if_debug(ex, debug_lvl=1):
    if in_debug_mode(debug_lvl):
        print_backtrace(ex)


def print_debug(debug_str):
    print('[UVPACKMASTER_DEBUG]: ' + debug_str)


def print_log(log_str):
    print('[UVPACKMASTER_LOG]: ' + log_str)


def print_error(error_str):
    print('[UVPACKMASTER_ERROR]: ' + error_str)


def print_warning(warning_str):
    print('[UVPACKMASTER_WARNING]: ' + warning_str)


def log_separator():
    return '-'*80


def redraw_ui(context):
    for area in context.screen.areas:
        if area is not None:
            area.tag_redraw()


def parse_json_file(json_file_path):
    with open(json_file_path) as f:
        try:
            data = json.load(f)
        except Exception as e:
            if in_debug_mode():
                print_backtrace(e)
            data = None
    return data


def version_to_str(v):
    return '.'.join(str(n) for n in v)


def unique_min_num(num_list, num_from=0):
    if not num_list:
        return num_from
    counter = num_from
    while True:
        counter += 1
        if counter in num_list:
            continue
        return counter


def remove_non_ascii(s : str) -> str:
    return s.encode("ascii", "ignore").decode("ascii")


def format_name(name : str) -> str:
    return remove_non_ascii(name).strip()


def unique_name(value, collection, instance=None):
    if collection.find(value) > -1:
        name_parts = value.rsplit(".", 1)
        base_name = name_parts[0]
        name_num_list = []
        found = 0
        same_found = 0
        for element in collection:
            if element == instance:
                continue

            if element.name.startswith(base_name):
                if element.name == value:
                    same_found += 1
                element_name_parts = element.name.rsplit(".", 1)
                if element_name_parts[0] != base_name:
                    continue
                found += 1
                if len(element_name_parts) < 2 or not element_name_parts[1].isnumeric():
                    continue
                name_num_list.append(int(element_name_parts[1]))

        if found > 0 and same_found > 0:
            return "{}.{:03d}".format(base_name, unique_min_num(name_num_list or [0]))
    return value


def snake_to_camel_case(snake_case_str):
    words = snake_case_str.split('_')
    camel_case_str = ''.join(word.capitalize() for word in words)
    return camel_case_str


def swap_attr(obj1, obj2, attr_name):
    tmp = getattr(obj1, attr_name)
    setattr(obj1, attr_name, getattr(obj2, attr_name))
    setattr(obj2, attr_name, tmp)


def is_builtin_class_instance(obj):
    return obj.__class__.__module__ == '__builtin__'


def reverse_dict(d):
    return {v: k for k, v in d.items()}


def lower_first(s):
    return s[0].lower() + s[1:]


def clamp(x, _min, _max):
    return max(_min, min(x, _max))
        

class PropertyWrapper:

    def __init__(self, obj, prop_id, text=None):
        self.obj = obj
        self.prop_id = prop_id
        self.text = text

    def get(self):
        return getattr(self.obj, self.prop_id)
    
    def set(self, value):
        setattr(self.obj, self.prop_id, value)
    
    def draw(self, layout, text=None, help_url_suffix=None):
        if text is None:
            text = self.text
            
        kwargs = {}
        if text is not None:
            kwargs['text'] = text

        row = layout.row(align=True)
        prop = self.get()
        if hasattr(prop, 'draw'):
            prop.draw(row, **kwargs)

        else:
            row.prop(self.obj, self.prop_id, **kwargs)

        if help_url_suffix:
            PanelUtilsMixin._draw_help_operator(row, help_url_suffix)

    def get_name(self):
        return self.property_data().name if hasattr(self.obj, self.prop_id) else ''
    
    def get_default(self):
        return self.property_data().default
    
    def get_fixed_type(self):
        return self.property_data().fixed_type
    
    def property_data(self):
        return AppInterface.object_property_data(self.obj)[self.prop_id]

        
class CollectionPropertyDictWrapper:

    def __dict_value(self, elem):
        return elem if self.value_id is None else getattr(elem, self.value_id)

    def __init__(self, collection, key_id, value_id):
        self.collection = collection
        self.key_id = key_id
        self.value_id = value_id
        self.dict = { getattr(elem, self.key_id): self.__dict_value(elem) for elem in self.collection }

    def get(self, key):
        return self.dict.get(key)
    
    def keys(self):
        return self.dict.keys()
    
    def values(self):
        return self.dict.values()
    
    def items(self):
        return self.dict.items()
    
    def _find(self, key):
        try:
            first_idx = next(idx for idx, elem in enumerate(self.collection) if getattr(elem, self.key_id) == key)
            return first_idx
        except StopIteration:
            pass

        return -1

    def __getitem__(self, key):
        value = self.get(key)
        if value is not None:
            return value
            
        new_elem = self.collection.add()
        setattr(new_elem, self.key_id, key)
        new_value = self.__dict_value(new_elem)
        self.dict[key] = new_value
        return new_value
    
    def __delitem__(self, key):
        index = self._find(key)

        if index < 0:
            raise KeyError()
        
        del self.dict[key]
        self.collection.remove(index)


    

class PanelUtilsMixin:

    BOX_ALIGN_SCALE_Y = 0.6

    @staticmethod
    def handle_prop(obj, prop_id, layout, not_supported_msg=None, warning_msg=None):
        supported = not_supported_msg is None
        row = layout.row(align=True)

        prop_row = row.row(align=True)
        prop_row.prop(obj, prop_id)
        prop_row.enabled = supported

        warning_text =  not_supported_msg if not supported else warning_msg

        if warning_text is not None:
            from .help import UVPM4_OT_WarningPopup
            UVPM4_OT_WarningPopup.draw_operator(row, text=warning_text)

    @staticmethod
    def draw_prop_saved_state(obj, prop_id, layout):
        col = layout.column(align=True)

        prop = PropertyWrapper(obj, prop_id)
        prop_saved = PropertyWrapper(obj, prop_id + '_saved')

        prop.draw(col)

        if prop.get() != prop_saved.get():
            col.label(text='Press the Save Preferences button below and', icon='ERROR')
            col.label(text='restart the application for the change to take effect')

    @classmethod
    def draw_expanded_enum(self, obj, prop_id, layout, item_enabled_checker=None):
        enum_values = AppInterface.object_property_data(obj)[prop_id].enum_items_static.keys()
        for enum_value in enum_values:
            row = layout.row(align=True)
            row.prop_enum(obj, prop_id, enum_value)
            if item_enabled_checker is not None:
                row.enabled = item_enabled_checker(enum_value)

    @classmethod
    def exclude_enum_item_checker(self, exclude_obj, prop_id):
        prop_value = getattr(exclude_obj, prop_id)
        return lambda enum_value: False if enum_value == prop_value else True

    @staticmethod
    def create_split_columns(layout, factors):
        cols = []
        space_left = 1.0
        prev_split = layout

        for factor in factors:
            new_split = prev_split.split(factor=factor / space_left, align=True)
            space_left -= factor

            cols.append(new_split.column(align=True))
            prev_split = new_split

        cols.append(prev_split.column(align=True))
        return cols
    
    @classmethod
    def draw_check_supported(cls, layout, not_supported_msg, draw_func):
        if not_supported_msg:
            cls._draw_error_label(layout, text=not_supported_msg)

        else:
            draw_func(layout)

    @staticmethod
    def _draw_error_label(layout, text):
        layout.box().label(text=text, icon='ERROR')

    @classmethod
    def _draw_help_operator(cls, layout, help_url_suffix):
        from .help import UVPM4_OT_Help
        help_op = layout.operator(UVPM4_OT_Help.bl_idname, icon=UVPM4_OT_Help.ICON, text='', emboss=False)
        help_op.url_suffix = help_url_suffix

    @classmethod
    def _draw_help_popover(cls, layout, help_panel_t):
        help_row = layout.row()
        help_row.emboss = 'NONE'
        help_row.popover(panel=help_panel_t.__name__, icon=help_panel_t.ICON, text="")

    @staticmethod
    def wrap_text_preserve_newlines(text, width):
        wrapper = textwrap.TextWrapper(width=width)
        paragraphs = text.split('\n')

        lines = []
        for p in paragraphs:
            lines += wrapper.wrap(text=p) if p else ['']
            
        return lines

    @classmethod
    def _draw_multiline_label(cls, layout, text, width):
        chars = int(width / 6)

        text_lines = cls.wrap_text_preserve_newlines(text, width=chars)
        for text_line in text_lines:
            layout.label(text=text_line)

    @staticmethod
    def draw_engine_status(prefs, layout):
        if not prefs.engine_initialized:
            box = layout.box()
            box.alert = True
            prefs.draw_engine_status(box)

    @staticmethod
    def draw_prop_name_up(obj, prop_id, layout):
        col = layout.column(align=True)
        col.label(text=PropertyWrapper(obj, prop_id).get_name() + ':')
        col.prop(obj, prop_id, text='')

    @staticmethod
    def draw_prop_with_set_menu(obj, prop_id, layout, menu_class, not_supported_msg=None):
        row = layout.row(align=True)
        split = row.split(factor=0.8, align=True)

        col_s = split.row(align=True)
        col_s.prop(obj, prop_id)
        col_s = split.row(align=True)
        col_s.menu(menu_class.bl_idname, text='Set')

        if not_supported_msg is not None:
            split.enabled = False
            from .help import UVPM4_OT_WarningPopup
            UVPM4_OT_WarningPopup.draw_operator(row, text=not_supported_msg)

    @classmethod
    def draw_enum_in_box(
            cls,
            obj,
            prop_id,
            layout,
            help_url_suffix=None,
            expand=False,
            not_supported_msg=None,
            warning_msg=None,
            prop_name=None):

        supported = not_supported_msg is None
        prop_kwargs = { 'expand' : expand }
        if not expand:
            prop_kwargs['text'] = ''

        box = layout.box()
        col = box.column(align=True)

        if prop_name is None:
            prop_name = PropertyWrapper(obj, prop_id).get_name()

        if prop_name:
            label_row = col.row(align=True)
            label_row.label(text=prop_name + ':')
            label_row.enabled = supported
            
        row = col.row(align=True)
        prop_row = row.row(align=True)
        prop_row.prop(obj, prop_id, **prop_kwargs)
        prop_row.enabled=supported

        if help_url_suffix:
            cls._draw_help_operator(row, help_url_suffix)

        warning_text = not_supported_msg if not supported else warning_msg

        if warning_text is not None:
            from .help import UVPM4_OT_WarningPopup
            UVPM4_OT_WarningPopup.draw_operator(row, text=warning_text)

        return col
    
    @classmethod
    def prop_with_help(cls, obj, prop_id, layout, help_url_suffix=None):
        row = layout.row(align=True)
        row.prop(obj, prop_id)

        if help_url_suffix:
            cls._draw_help_operator(row, help_url_suffix)

    @classmethod
    def get_active_mode(cls, context):
        return None

    def init_draw(self, context):
        self.prefs = get_prefs()
        self.scene_props = get_scene_props(context)

        from .spipeline.engine.props import MainProps
        self.main_props : MainProps = get_main_props(context)
        self.context = context

        if not hasattr(self, 'multi_panel'):
            self.multi_panel = True

        self.props_with_help = not self.multi_panel
        self.active_mode = self.get_active_mode(context)

    def draw_pixel_margin_tex_size(self, layout):
        row = layout.row(align=True)

        from .operator_misc import UVPM4_MT_SetPixelMarginTexSizeScene

        self.draw_prop_with_set_menu(
            self.main_props,
            "pixel_margin_tex_size",
            row,
            UVPM4_MT_SetPixelMarginTexSizeScene,
            not_supported_msg=self.main_props.tex_size_not_supported_msg())
        
        return row

    def draw_main_prop_sets(self, layout):
        from .id_collection.main_props import MainPropSetAccess

        if not self.scene_props.main_prop_sets_enable:
            pass

        else:
            from .id_collection.ui import IdCollectionDrawer
            IdCollectionDrawer(access=MainPropSetAccess(self.context, ui_drawing=True)).draw(layout)
            layout.separator()

    def draw_main_prop_sets_cond(self, layout, access_desc, not_enabled_msg):
        row = layout.row(align=True)
        row.label(text='Option set:')
        
        if self.scene_props.main_prop_sets_enable:
            row2 = layout.row(align=True)
            from .id_collection.ui import IdCollectionDrawer
            from .id_collection.main_props import MainPropSetAccess

            IdCollectionDrawer(access=MainPropSetAccess(self.context, desc=access_desc, ui_drawing=True), browse_only=True).draw(row2)
            row2.enabled = self.scene_props.main_prop_sets_enable
        else:
            from .help import UVPM4_OT_HelpPopup
            UVPM4_OT_HelpPopup.draw_operator(row, text=not_enabled_msg)


def type_from_class_path(class_path):
    module_name, qual_name = class_path.split(':')

    import importlib
    module = importlib.import_module(module_name)
    t = module
    for part in qual_name.split('.'):
        t = getattr(t, part)

    return t


def construct_from_class_path(class_path, *args, **kw_args):    
    return type_from_class_path(class_path)(*args, **kw_args)
