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

from .utils import CollectionPropertyDictWrapper, construct_from_class_path
from .spipeline.engine.utils import get_class_path
from .operator import UVPM4_OT_GenericHandler
from .app_iface import *


class KeyAttrMixin:

    key : StringProperty(name='Key', default='')


class UVPM4_OT_MultiSelectAddEntry(UVPM4_OT_GenericHandler, KeyAttrMixin):

    bl_idname = 'uvpackmaster4.multi_select_add_entry'
    bl_label = 'Add Entry'
    bl_description = 'Add a new entry to the collection'

    def execute_impl(self, context):
        access = MultiSelectCollectionAccess.construct_from_context(context)
        access.add_entry(self.key)

        return {'FINISHED'}


class UVPM4_OT_MultiSelectRemoveEntry(UVPM4_OT_GenericHandler, KeyAttrMixin):

    bl_idname = 'uvpackmaster4.multi_select_remove_entry'
    bl_label = 'Remove Entry'
    bl_description = 'Remove the given entry from the collection'

    bl_options = {'UNDO'}

    def execute_impl(self, context):
        access = MultiSelectCollectionAccess.construct_from_context(context)
        access.remove_entry(self.key)

        return {'FINISHED'}


class UVPM4_MT_MultiSelectAddEntry(Menu):

    bl_idname = 'UVPM4_MT_MultiSelectAddEntry'
    bl_label = 'Add Entry'

    def draw(self, context):
        layout = self.layout
        access = MultiSelectCollectionAccess.construct_from_context(context)
        access.draw_add_menu(layout)


class MultiSelectCollectionAccess:

    @staticmethod
    def construct_from_context(context):
        return construct_from_class_path(context.uvpm4_access_class_path, *(context, context.uvpm4_access_init_str))

    def __init__(self, context, init_str):
        self.class_path = get_class_path(self)
        self.context = context
        self.init_str = init_str
        self.key_id = 'name'
        
        self.key_collection = CollectionPropertyDictWrapper(self._get_key_collection(), self.key_id, None)
        self.sel_collection = CollectionPropertyDictWrapper(self._get_sel_collection(), self.key_id, None)
        self.valid_collection = { key: self.sel_collection.get(key) for key in self.sel_collection.keys() if self.key_collection.get(key) is not None }

    def __set_context_strings(self, layout):
        layout.context_string_set('uvpm4_access_class_path', self.class_path)
        layout.context_string_set('uvpm4_access_init_str', self.init_str)

    def add_entry(self, key):
        assert key

        if self.key_collection.get(key) is None:
            return
        
        if self.sel_collection.get(key) is not None:
            return
        
        new_entry = self.sel_collection[key]
        self.valid_collection[key] = new_entry

        return new_entry
    
    def remove_entry(self, key):
        assert key
        
        if self.sel_collection.get(key) is None:
            return
        
        del self.sel_collection[key]

        try:
            del self.valid_collection[key]

        except KeyError:
            pass

    def entries(self):
        return self.valid_collection.values()

    def draw_add_menu(self, layout):
        self.__set_context_strings(layout)

        for key_entry in self.key_collection.values():
            key = getattr(key_entry, self.key_id)

            if self.sel_collection.get(key) is not None:
                continue

            op = layout.operator(UVPM4_OT_MultiSelectAddEntry.bl_idname, text=key)
            op.key = key

    def draw(self, layout):
        main = layout.box().column(align=True)
        self.__set_context_strings(main)

        main.menu(UVPM4_MT_MultiSelectAddEntry.bl_idname, text=self.ADD_ENTRY_MENU_LABEL)
        entries = self.entries()

        if len(entries) > 0:
            col = main.box().column(align=False)

        for idx, entry in enumerate(entries):
            e_layout = col.column(align=True)
            e_layout.label(text='{} {}:'.format(self.ENTRY_NAME, idx+1))
            row = e_layout.row(align=True)
            row2 = row.row(align=True)
            row2.prop(entry, self.key_id, text='')
            row2.enabled = False
            e_layout.separator()
            op = row.operator(UVPM4_OT_MultiSelectRemoveEntry.bl_idname, text='', icon='REMOVE')
            op.key = getattr(entry, self.key_id)

            self._draw_entry(entry, e_layout.column(align=True))

            col.separator(factor=1.0)
