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

# Copyright 2023 - 2025, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy

import os
import tempfile
import json

from .vlog import Log


def group_to_dict(group: bpy.types.PropertyGroup, fn_skip_prop: callable = None, default_only=True) -> dict:
    """Get values from a property group as a dict."""

    prop_dict = {}

    def rna_recursive_attr_expand(value, p_dict, rna_path_step, level):
        if isinstance(value, bpy.types.bpy_struct):
            for sub_value_attr, sub_value_prop in value.bl_rna.properties.items():
                if sub_value_attr in {"rna_type", "bl_idname"}:
                    continue
                if sub_value_prop.is_skip_save:
                    continue
                if fn_skip_prop is not None:
                    if fn_skip_prop(value, sub_value_attr):
                        continue

                b_skip_by_default = False
                if not isinstance(sub_value_prop, (bpy.types.CollectionProperty, bpy.types.PointerProperty)):
                    b_skip_by_default = not value.is_property_set(sub_value_attr) if default_only else False
                if b_skip_by_default:
                    continue

                sub_value = getattr(value, sub_value_attr)

                it_dict = p_dict
                b_is_pointer = isinstance(sub_value_prop, bpy.types.PointerProperty)
                if b_is_pointer:
                    p_dict[sub_value_attr] = {}
                    it_dict = p_dict[sub_value_attr]

                rna_recursive_attr_expand(sub_value, it_dict, sub_value_attr, level)

                if b_is_pointer:
                    if not it_dict:
                        del p_dict[sub_value_attr]
        elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
            p_dict[rna_path_step] = []
            for sub_value in value:

                p_dict[rna_path_step].append({})

                rna_recursive_attr_expand(sub_value, p_dict[rna_path_step][-1], '', level + 1)
        else:

            bl_rna = None
            if value and hasattr(value, 'bl_rna'):
                bl_rna = getattr(value, 'bl_rna')

            def get_value(value):
                if bl_rna:
                    p_rna_prop = bl_rna.properties.get(rna_path_step, None)
                    if p_rna_prop:
                        if isinstance(p_rna_prop, bpy.types.StringProperty):
                            if p_rna_prop.subtype == 'BYTE_STRING':
                                return value.decode('utf-8')

                subvalue_type = type(value)

                if subvalue_type in {int, bool, float, str}:
                    return value

                if subvalue_type is set:
                    return list(value)

                try:
                    value = list(value[:])
                except Exception:
                    pass

                return value

            p_dict[rna_path_step] = get_value(value)

    rna_recursive_attr_expand(group, prop_dict, '', 0)

    return prop_dict


def group_from_dict(group: bpy.types.PropertyGroup, p_dict: dict, fn_skip_prop: callable = None, errors_list: list = None) -> None:
    """ Assign dict to group """

    bl_rna = None
    if group and hasattr(group, 'bl_rna'):
        bl_rna = getattr(group, 'bl_rna')

    for key, val in p_dict.items():

        if fn_skip_prop is not None:
            if fn_skip_prop(group, key):
                continue

        p_prop = bl_rna.properties.get(key, None)
        if p_prop is None:
            s_error_msg = f"Import: {key} - property is not found in RNA: {str(type(group))}"
            if errors_list is not None:
                errors_list.append(s_error_msg)
            else:
                Log.error(s_error_msg)
            continue

        if isinstance(p_prop, bpy.types.EnumProperty):
            if p_prop.is_enum_flag:
                val = set(val)

        p_attr = getattr(group, key, None)
        if type(p_attr).__name__ == "bpy_prop_collection_idprop":
            p_attr.clear()
            for sub in val:
                p_attr.add()
                group_from_dict(p_attr[-1], sub)
        elif isinstance(p_attr, bpy.types.bpy_struct):
            group_from_dict(p_attr, val, fn_skip_prop=fn_skip_prop, errors_list=errors_list)
        else:
            if val != p_attr:
                try:
                    setattr(group, key, val)
                except Exception as e:
                    s_error_msg = f"Import: {key} failed: {str(e)}"
                    if errors_list is not None:
                        errors_list.append(s_error_msg)
                    else:
                        Log.error(s_error_msg)


def save_group_to_json(group: bpy.types.bpy_struct, file_path, fn_skip_prop: callable = None, default_only=True) -> dict:
    with open(file_path, 'w', encoding='utf-8') as json_file:
        t_data = group_to_dict(group, fn_skip_prop=fn_skip_prop, default_only=default_only)
        json.dump(t_data, json_file, indent=4)
        return t_data


def save_group_to_tempfile(group: bpy.types.bpy_struct, temp_name="prefs.json", fn_skip_prop: callable = None, default_only=True) -> dict:
    s_out_file = os.path.join(tempfile.gettempdir(), temp_name)
    return save_group_to_json(group, s_out_file, fn_skip_prop=fn_skip_prop, default_only=default_only)


def load_group_from_json(group: bpy.types.bpy_struct, file_path, fn_skip_prop=None, errors_list: list = None):
    with open(file_path, 'r', encoding='utf-8') as f:
        t_data = json.load(f)
        group_from_dict(group, t_data, fn_skip_prop=fn_skip_prop, errors_list=errors_list)
        return t_data


def load_group_from_tempfile(group: bpy.types.bpy_struct, temp_name="prefs.json", fn_skip_prop: callable = None, errors_list: list = None) -> dict:
    s_out_file = os.path.join(tempfile.gettempdir(), temp_name)
    return load_group_from_json(group, s_out_file, fn_skip_prop=fn_skip_prop, errors_list=errors_list)
