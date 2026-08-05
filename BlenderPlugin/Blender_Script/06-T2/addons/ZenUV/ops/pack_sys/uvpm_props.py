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

# Part of the UV Packmaster 3.4.0 addon to get the addon properties

def get_class_path(obj):
    t = type(obj)
    return "{}:{}".format(t.__module__, t.__qualname__)


def get_scene_props(context):
    return context.scene.uvpm3_props


class IdCollectionAccess:

    def __init__(self, context, init_collection=False, desc=None, ui_drawing=False):
        self.context = context
        self.ui_drawing = ui_drawing
        self.coll = self._get_collection()

        access_class_path = get_class_path(self)

        if init_collection:
            self.coll.access_class_path = access_class_path

        else:
            assert self.coll.access_class_path == access_class_path

        if desc:
            self.desc = desc

        else:
            self.desc = self._get_access_desc()

        self.init_active_members()

    def init_active_members(self):
        self.active_item = self.init_active_item()

        if not self.ui_drawing and self.active_item is not None:
            self.active_item.init_defaults()

    def get_collection(self):
        return self.coll

    def get_coll_enum_items(self):
        items = []
        enumerated_items = list(enumerate(self.get_items()))
        enumerated_items.sort(key=lambda i: i[1].name)

        for idx, item in enumerated_items:
            items.append((str(item.uuid), item.name, "", idx))
        return items

    # @staticmethod
    # def get_coll_enum_items_callback(property_self, context):
    #     item_access = GroupingSchemeAccess()
    #     item_access.init_access(context, ui_drawing=True, desc_id='default')
    #     return item_access.get_items_enum_items()

    def create_item(self, set_active=True):
        new_item = self.get_items().add()
        new_item.init_defaults()

        if set_active:
            self.set_active_item_uuid(new_item.uuid)

        return new_item

    def _pre_remove_item(self, idx):
        pass

    def remove_item(self, idx):
        if idx < 0:
            return

        self._pre_remove_item(idx)
        self.get_items().remove(idx)

    def remove_active_item(self):
        active_idx = self.get_active_item_idx()
        self.remove_item(active_idx)

        new_idx = min(active_idx, len(self.get_items())-1)
        self.set_active_item_uuid(self.get_items()[new_idx].uuid if new_idx >= 0 else '')

    def get_active_item_uuid(self):
        return self.desc.active_item_uuid

    def get_active_item_idx(self):
        active_item_uuid = self.get_active_item_uuid()

        for idx, item in enumerate(self.get_items()):
            if active_item_uuid == item.uuid:
                return idx

        return -1

    def init_active_item(self):
        active_item_idx = self.get_active_item_idx()
        active_item = None

        if active_item_idx >= 0:
            active_item = self.get_items()[active_item_idx]

        return active_item

    def get_items(self):
        return self.coll.items

    def get_active_item_safe(self):
        if self.active_item is None:
            raise RuntimeError('No active item found')

        return self.active_item

    def set_active_item_uuid(self, uuid):
        self.desc.active_item_uuid = uuid
        self.init_active_members()


class MainPropSetAccess(IdCollectionAccess):

    ITEM_NAME = 'Option Set'
    ICON = 'OPTIONS'
    DRAW_LABEL = False
    HELP_URL_SUFFIX = '/20-packing-functionalities/15-basic-packing-and-options/#option-sets'

    def _get_collection(self):
        return get_scene_props(self.context).main_prop_sets

    def _get_access_desc(self):
        return get_scene_props(self.context).main_prop_access_desc

    def _pre_remove_item(self, idx):
        if len(self.get_items()) == 1:
            raise RuntimeError("Cannot remove the last set. Disable option sets globally in the Packing panel, if you don't want to use them")


def get_main_props(context):
    scene_props = get_scene_props(context)
    if not scene_props.main_prop_sets_enable:
        return scene_props.default_main_props

    return MainPropSetAccess(context).get_active_item_safe()
