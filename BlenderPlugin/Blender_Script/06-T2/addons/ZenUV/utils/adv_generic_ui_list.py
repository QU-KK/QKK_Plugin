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

# originally taken from 'bl_ui.generic_ui_list'

# Copyright 2023, Alex Zhornyak

import bpy
from bpy.types import Operator
from bpy.props import (
    EnumProperty,
    StringProperty,
)
from bpy.utils import is_path_builtin
from bpy.app.translations import (
    pgettext_tip as tip_,
)

from bl_operators.wm import context_path_validate
from bl_operators.presets import AddPresetBase

import os
from pathlib import Path


LITERAL_ADD = "zenuvlist.entry_add"
LITERAL_REMOVE = "zenuvlist.entry_remove"
LITERAL_MOVE = "zenuvlist.entry_move"
LITERAL_DELETE_ALL = "zenuvlist.entry_delete_all"


def zenuv_draw_ui_list(
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
        class_name="UI_UL_list",
        *,
        unique_id,
        list_path,
        active_index_path,
        insertion_operators=True,
        move_operators=True,
        menu_class_name="",

        new_name_attr="",
        new_name_val="",

        op_id_add=LITERAL_ADD,
        op_id_remove=LITERAL_REMOVE,
        op_id_move=LITERAL_MOVE,
        op_id_delete_all=LITERAL_DELETE_ALL,

        **kwargs,
):
    """
    Draw a UIList with Add/Remove/Move buttons and a menu.

    :arg layout: UILayout to draw the list in.
    :type layout: :class:`UILayout`
    :arg context: Blender context to get the list data from.
    :type context: :class:`Context`
    :arg class_name: Name of the UIList class to draw. The default is the UIList class that ships with Blender.
    :type class_name: str
    :arg unique_id: Unique identifier to differentiate this from other UI lists.
    :type unique_id: str
    :arg list_path: Data path of the list relative to context, eg. "object.vertex_groups".
    :type list_path: str
    :arg active_index_path: Data path of the list active index integer relative to context,
       eg. "object.vertex_groups.active_index".
    :type active_index_path: str
    :arg insertion_operators: Whether to draw Add/Remove buttons.
    :type insertion_operators: bool
    :arg move_operators: Whether to draw Move Up/Down buttons.
    :type move_operators: str
    :arg menu_class_name: Identifier of a Menu that should be drawn as a drop-down.
    :type menu_class_name: str

    :returns: The right side column.
    :rtype: :class:`UILayout`.

    Additional keyword arguments are passed to :class:`UIList.template_list`.
    """

    row = layout.row(align=False)

    list_owner_path, list_prop_name = list_path.rsplit('.', 1)
    list_owner = _get_context_attr(context, list_owner_path)

    index_owner_path, index_prop_name = active_index_path.rsplit('.', 1)
    index_owner = _get_context_attr(context, index_owner_path)

    list_to_draw = _get_context_attr(context, list_path)

    row.template_list(
        class_name,
        unique_id,
        list_owner, list_prop_name,
        index_owner, index_prop_name,
        rows=4 if list_to_draw else 1,
        **kwargs
    )

    col = row.column(align=True)

    if insertion_operators:
        _draw_add_remove_buttons(
            layout=col,
            list_path=list_path,
            active_index_path=active_index_path,
            list_length=len(list_to_draw),
            new_name_attr=new_name_attr,
            new_name_val=new_name_val
        )
        col.separator()

    if menu_class_name:
        col.menu(menu_class_name, icon='DOWNARROW_HLT', text="")
        col.separator()

    if move_operators and list_to_draw:
        _draw_move_buttons(
            layout=col,
            list_path=list_path,
            active_index_path=active_index_path,
            list_length=len(list_to_draw)
        )

    if insertion_operators:
        col.separator()
        _draw_delete_all_button(
            layout=col,
            list_path=list_path,
            active_index_path=active_index_path,
            list_length=len(list_to_draw)
        )

    # Return the right-side column.
    return col


def _draw_add_remove_buttons(
    *,
    layout: bpy.types.UILayout,
    list_path,
    active_index_path,
    list_length,
    new_name_attr='',
    new_name_val=''
):
    """Draw the +/- buttons to add and remove list entries."""
    col = layout.column(align=True)
    row = col.row(align=True)
    props = row.operator(ZENUVLIST_OT_entry_add.bl_idname, text="", icon='ADD')
    props.list_path = list_path
    props.active_index_path = active_index_path
    props.new_name_attr = new_name_attr
    props.new_name_val = new_name_val

    row = col.row(align=True)
    row.enabled = list_length > 0
    props = row.operator(ZENUVLIST_OT_entry_remove.bl_idname, text="", icon='REMOVE')
    props.list_path = list_path
    props.active_index_path = active_index_path


def _draw_move_buttons(
    *,
    layout: bpy.types.UILayout,
    list_path,
    active_index_path,
    list_length,
):
    """Draw the up/down arrows to move elements in the list."""
    col = layout.column(align=True)
    col.enabled = list_length > 1
    props = col.operator(ZENUVLIST_OT_entry_move.bl_idname, text="", icon='TRIA_UP')
    props.direction = 'UP'
    props.list_path = list_path
    props.active_index_path = active_index_path

    props = col.operator(ZENUVLIST_OT_entry_move.bl_idname, text="", icon='TRIA_DOWN')
    props.direction = 'DOWN'
    props.list_path = list_path
    props.active_index_path = active_index_path


def _draw_delete_all_button(
    *,
    layout: bpy.types.UILayout,
    list_path,
    active_index_path,
    list_length,
):
    """Draw the up/down arrows to move elements in the list."""
    col = layout.column(align=True)
    col.enabled = list_length > 0
    props = col.operator(ZENUVLIST_OT_entry_delete_all.bl_idname, text="", icon='TRASH')
    props.list_path = list_path
    props.active_index_path = active_index_path


def _get_context_attr(context, data_path):
    """Return the value of a context member based on its data path."""
    return context_path_validate(context, data_path)


def _set_context_attr(context, data_path, value):
    """Set the value of a context member based on its data path."""
    owner_path, attr_name = data_path.rsplit('.', 1)
    owner = context_path_validate(context, owner_path)
    setattr(owner, attr_name, value)


class ZuvGenericUIListOperator:
    """Mix-in class containing functionality shared by operators
    that deal with managing Blender list entries."""
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    list_path: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    active_index_path: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def get_list(self, context):
        return _get_context_attr(context, self.list_path)

    def get_active_index(self, context):
        return _get_context_attr(context, self.active_index_path)

    def set_active_index(self, context, index):
        _set_context_attr(context, self.active_index_path, index)


class ZENUVLIST_OT_entry_remove(ZuvGenericUIListOperator, Operator):
    """Remove the selected entry from the list"""

    bl_idname = LITERAL_REMOVE
    bl_label = "Remove Selected Entry"

    def execute(self, context):
        my_list = self.get_list(context)
        active_index = self.get_active_index(context)

        my_list.remove(active_index)
        to_index = min(active_index, len(my_list) - 1)
        self.set_active_index(context, to_index)

        return {'FINISHED'}


class ZENUVLIST_OT_entry_delete_all(ZuvGenericUIListOperator, Operator):
    """Delete all entries from the list"""

    bl_idname = LITERAL_DELETE_ALL
    bl_label = "Delete All"

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)

    def execute(self, context):
        my_list = self.get_list(context)
        my_list.clear()
        self.set_active_index(context, -1)

        return {'FINISHED'}


class ZENUVLIST_OT_entry_add(ZuvGenericUIListOperator, Operator):
    """Add an entry to the list after the current active item"""

    bl_idname = LITERAL_ADD
    bl_label = "Add Entry"

    new_name_attr: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    new_name_val: StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        my_list = self.get_list(context)
        active_index = self.get_active_index(context)

        to_index = min(len(my_list), active_index + 1)

        my_list.add()

        if self.new_name_attr and self.new_name_val:
            setattr(my_list[-1], self.new_name_attr, self.new_name_val)

        my_list.move(len(my_list) - 1, to_index)
        self.set_active_index(context, to_index)

        return {'FINISHED'}


class ZENUVLIST_OT_entry_move(ZuvGenericUIListOperator, Operator):
    """Move an entry in the list up or down"""

    bl_idname = LITERAL_MOVE
    bl_label = "Move Entry"

    direction: EnumProperty(
        name="Direction",
        items=(
            ('UP', 'UP', 'UP'),
            ('DOWN', 'DOWN', 'DOWN'),
        ),
        default='UP',
    )

    def execute(self, context):
        my_list = self.get_list(context)
        active_index = self.get_active_index(context)

        delta = {
            'DOWN': 1,
            'UP': -1,
        }[self.direction]

        to_index = (active_index + delta) % len(my_list)

        my_list.move(active_index, to_index)
        self.set_active_index(context, to_index)

        return {'FINISHED'}


class ZenAddPresetBase(AddPresetBase):

    # NOTE: we override this method because we need preset name that was activated
    def execute(self, context: bpy.types.Context):

        if hasattr(self, "pre_cb"):
            self.pre_cb(context)

        preset_menu_class = getattr(bpy.types, self.preset_menu)

        is_xml = getattr(preset_menu_class, "preset_type", None) == 'XML'
        is_preset_add = not (self.remove_name or self.remove_active)

        if is_xml:
            ext = ".xml"
        else:
            ext = ".py"

        name = self.name.strip() if is_preset_add else self.name

        if is_preset_add:
            if not name:
                self.report({'WARNING'}, 'Preset name is empty!')
                return {'FINISHED'}

            # Reset preset name
            wm = bpy.data.window_managers[0]
            if name == wm.preset_name:
                wm.preset_name = 'New Preset'

            filename = self.as_filename(name)

            target_path = os.path.join("presets", self.preset_subdir)
            target_path = bpy.utils.user_resource('SCRIPTS', path=target_path, create=True)

            if not target_path:
                self.report({'WARNING'}, "Failed to create presets path")
                return {'CANCELLED'}

            filepath = os.path.join(target_path, filename) + ext

            if hasattr(self, "add"):
                self.add(context, filepath)
            else:
                print("Writing Preset: %r" % filepath)

                if is_xml:
                    import rna_xml
                    rna_xml.xml_file_write(context,
                                           filepath,
                                           preset_menu_class.preset_xml_map)
                else:

                    def rna_recursive_attr_expand(value, rna_path_step, level):
                        if isinstance(value, bpy.types.PropertyGroup):
                            for sub_value_attr, sub_value_prop in value.bl_rna.properties.items():
                                if sub_value_attr == "rna_type":
                                    continue
                                if sub_value_prop.is_skip_save:
                                    continue
                                sub_value = getattr(value, sub_value_attr)
                                rna_recursive_attr_expand(sub_value, "%s.%s" % (rna_path_step, sub_value_attr), level)
                        elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
                            file_preset.write("%s.clear()\n" % rna_path_step)
                            for sub_value in value:
                                file_preset.write("\n")
                                file_preset.write("item_sub_%d = %s.add()\n" % (level, rna_path_step))
                                rna_recursive_attr_expand(sub_value, "item_sub_%d" % level, level + 1)
                            if len(value) > 0:
                                file_preset.write("\n")
                        else:
                            # convert thin wrapped sequences
                            # to simple lists to repr()
                            try:
                                value = value[:]
                            except Exception:
                                pass

                            file_preset.write("%s = %r\n" % (rna_path_step, value))

                    file_preset = open(filepath, 'w', encoding="utf-8")
                    file_preset.write("import bpy\n")

                    if hasattr(self, "preset_defines"):
                        for rna_path in self.preset_defines:
                            exec(rna_path)
                            file_preset.write("%s\n" % rna_path)
                        file_preset.write("\n")

                    for rna_path in self.preset_values:
                        value = eval(rna_path)
                        rna_recursive_attr_expand(value, rna_path, 1)

                    file_preset.close()

            preset_menu_class.bl_label = Path(filename).stem

        else:
            if self.remove_active:
                name = preset_menu_class.bl_label

            # fairly sloppy but convenient.
            filepath = bpy.utils.preset_find(name,
                                             self.preset_subdir,
                                             ext=ext)

            if not filepath:
                filepath = bpy.utils.preset_find(name,
                                                 self.preset_subdir,
                                                 display_name=True,
                                                 ext=ext)

            if not filepath:
                self.report({'WARNING'}, f'Preset: {name} - not found!')
                return {'CANCELLED'}

            # Do not remove bundled presets
            if is_path_builtin(filepath):
                self.report({'WARNING'}, "Unable to remove default presets")
                return {'CANCELLED'}

            try:
                if hasattr(self, "remove"):
                    self.remove(context, filepath)
                else:
                    os.remove(filepath)
            except Exception as e:
                self.report({'ERROR'}, tip_("Unable to remove preset: %r") % e)
                import traceback
                traceback.print_exc()
                return {'CANCELLED'}

            preset_menu_class.bl_label = preset_menu_class.default_label

        if hasattr(self, "post_cb"):
            self.post_cb(context)

        context.area.tag_redraw()

        return {'FINISHED'}


# Registration.
classes = (
    ZENUVLIST_OT_entry_remove,
    ZENUVLIST_OT_entry_add,
    ZENUVLIST_OT_entry_move,
    ZENUVLIST_OT_entry_delete_all
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
