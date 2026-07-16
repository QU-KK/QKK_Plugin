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

from ..app_iface import *
from . import UVPM4_OT_IdCollectionNewItem, UVPM4_OT_IdCollectionRemoveItem, UVPM4_OT_IdCollectionOperatorGeneric, IdCollectionAccess

from ..utils import PanelUtilsMixin


class UVPM4_OT_IdCollectionBrowseItems(UVPM4_OT_IdCollectionOperatorGeneric):

    bl_options = {'INTERNAL'}
    bl_idname = 'uvpackmaster4.id_collection_browse_items'
    bl_label = 'Browse Items'
    bl_description = "Browse Items"

    active_item_uuid : StringProperty(name='', description='', default='')

    def execute_impl(self, context):
        self.access.set_active_item_uuid(self.active_item_uuid)
        return {'FINISHED'}


class UVPM4_MT_IdCollectionBrowseItems(Menu):

    bl_label = "Items"
    bl_idname = "UVPM4_MT_IdCollectionBrowseItems"

    def draw(self, context):
        access = context.uvpm4_id_collection.access_type()(context, desc=context.uvpm4_id_item_access_desc)
        items = access.get_items()

        layout = self.layout
        layout.context_pointer_set('uvpm4_id_collection', context.uvpm4_id_collection)
        layout.context_pointer_set('uvpm4_id_item_access_desc', context.uvpm4_id_item_access_desc)

        for item in items:
            operator = layout.operator(UVPM4_OT_IdCollectionBrowseItems.bl_idname, text=item.name)
            operator.active_item_uuid = item.uuid


class IdCollectionDrawer:

    def __init__(self,
                 access : IdCollectionAccess,
                 browse_only=False,
                 label_plural_form=False,
                 draw_item=False,
                 preset_panel_t=None):
        
        self.access = access
        self.preset_panel_t = preset_panel_t
        self.browse_only = browse_only
        self.label_plural_form = label_plural_form
        self.draw_item = draw_item

    def draw_items_presets(self, layout):
        layout.emboss = 'NONE'
        layout.popover(panel=self.preset_panel_t.__name__, icon='PRESET', text="")

    def op_init(self, op, layout):
        layout.context_pointer_set('uvpm4_id_collection', self.access.coll)
        layout.context_pointer_set('uvpm4_id_item_access_desc', self.access.desc)

    def draw(self, layout):
        main_col = layout.column(align=True)

        if self.access.DRAW_LABEL:
            row = main_col.row(align=True)
            row.label(text=self.access.ITEM_LABEL + ('s' if self.label_plural_form else '') + ':')

            if hasattr(self.access, 'HELP_URL_SUFFIX'):
                PanelUtilsMixin._draw_help_operator(row, help_url_suffix=self.access.HELP_URL_SUFFIX)

        row = main_col.row(align=True)

        row.context_pointer_set('uvpm4_id_collection', self.access.get_collection())
        row.context_pointer_set('uvpm4_id_item_access_desc', self.access.desc)
        row.menu(UVPM4_MT_IdCollectionBrowseItems.bl_idname, text="", icon=self.access.ICON)

        item_available = len(self.access.get_items()) > 0
        item_active = self.access.active_item is not None

        if item_active:
            row2 = row.row(align=True)
            row2.prop(self.access.active_item, "name", text="")
            row2.enabled = not self.browse_only

        else:
            help_msg = None
            if item_available:
                help_msg = '← Select {}'.format(self.access.ITEM_LABEL.lower())

            elif self.browse_only:
                help_msg = self.access.BROWSE_ONLY_NO_ITEM_HELP_MSG

            if help_msg:
                box = row.box()
                box.scale_y = PanelUtilsMixin.BOX_ALIGN_SCALE_Y
                box.enabled = False
                box.label(text=help_msg)


        if not self.browse_only:
            op = row.operator(UVPM4_OT_IdCollectionNewItem.bl_idname, icon='ADD', text='' if item_available else UVPM4_OT_IdCollectionNewItem.bl_label)
            self.op_init(op, row)

            if item_active:
                op = row.operator(UVPM4_OT_IdCollectionRemoveItem.bl_idname, icon='REMOVE', text='')
                self.op_init(op, row)

        if self.preset_panel_t is not None:
            box = row.box()
            box.scale_y = PanelUtilsMixin.BOX_ALIGN_SCALE_Y
            self.draw_items_presets(box)

        if item_active and self.draw_item:
            self.access.draw_item(self.access.active_item, main_col.box().column(align=True))
