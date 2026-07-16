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

from ..app_iface import Operator, StringProperty, PropertyGroup
from ..pgroup import standalone_property_group
from ..spipeline.engine.id_collection import IdCollectionAccess # Required for other submodules


@standalone_property_group
class UVPM4_IdCollectionAccessDescriptor:

    active_item_uuid : StringProperty(default='')


class IdCollectionMixin:

    def access_type(self):
        from ..utils import PropertyWrapper
        return PropertyWrapper(self, 'items').get_fixed_type().ACCESS_TYPE
    

class IdCollectionBase(IdCollectionMixin, PropertyGroup):
    pass


class IdCollectionItemMixin:
    pass


def _update_id_collection_item_name(self, context):
    access = self.ACCESS_TYPE(context)
    items = access.get_items()

    orig_name = self.name

    from ..utils import format_name
    name = format_name(self.name)

    if name == '':
        name = self.ACCESS_TYPE.DEFAULT_ITEM_NAME

    from ..utils import unique_name
    name = unique_name(name, items, self)

    if orig_name != name:
        self.name = name


def id_collection_item(new_cls):
    if not hasattr(new_cls, "__annotations__"):
        new_cls.__annotations__ = {}

    new_cls.__annotations__['name'] = StringProperty(name="name", default="", update=_update_id_collection_item_name)
    new_cls.__annotations__['uuid'] = StringProperty(name="uuid", default="")

    return type(new_cls.__name__, tuple(dict.fromkeys((PropertyGroup, IdCollectionItemMixin) + new_cls.__bases__)), dict(new_cls.__dict__))



class UVPM4_OT_IdCollectionOperatorGeneric(Operator):

    bl_options = {'INTERNAL', 'UNDO'}

    def execute(self, context):
        try:
            access_desc = None
            if hasattr(context, 'uvpm4_id_item_access_desc'):
                access_desc = context.uvpm4_id_item_access_desc

            coll = context.uvpm4_id_collection

            self.access = coll.access_type()(context, desc=access_desc)
            ret = self.execute_impl(context)
            self.access.state_changed_handler()

            return ret

        except Exception as ex:
            self.report({'ERROR'}, str(ex))

        return {'CANCELLED'}


class UVPM4_OT_IdCollectionNewItem(UVPM4_OT_IdCollectionOperatorGeneric):

    bl_idname = "uvpackmaster4.id_collection_new_item"
    bl_label = "Add New"
    bl_description = "Add a new item"

    @classmethod
    def description(cls, context, properties):
        coll = context.uvpm4_id_collection
        return 'Add a new {}'.format(coll.access_type().ITEM_LABEL.lower())

    def execute_impl(self, context):
        self.access.create_item()
        return {'FINISHED'}


class UVPM4_OT_IdCollectionRemoveItem(UVPM4_OT_IdCollectionOperatorGeneric):

    bl_idname = "uvpackmaster4.id_collection_remove_item"
    bl_label = "Remove Active"
    bl_description = "Remove the active item"

    @classmethod
    def description(cls, context, properties):
        coll = context.uvpm4_id_collection
        return 'Remove the active {}'.format(coll.access_type().ITEM_LABEL.lower())
    
    def confirmation_msg(self):
        coll = self.context.uvpm4_id_collection
        return 'Are you sure you want to remove the {}?'.format(coll.access_type().ITEM_LABEL.lower())
    
    def execute_impl(self, context):
        self.access.remove_active_item()
        return {'FINISHED'}
    