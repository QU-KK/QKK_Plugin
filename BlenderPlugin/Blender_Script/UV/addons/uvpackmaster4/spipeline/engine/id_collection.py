
from .param import EngineParamTarget



class IdCollectionAccessDescriptor(EngineParamTarget):

    active_item_uuid : str


class IdCollectionAccess:

    def __init__(self, context, coll=None, desc=None, ui_drawing=False):
        self.context = context
        self.ui_drawing = ui_drawing
        self.coll = coll if coll else self._get_collection()

        self.desc = desc if desc else self._get_access_desc()
        self.init_active_members()

    def state_changed_handler(self):
        pass

    @staticmethod
    def uuid_is_valid(uuid_to_test):
        import uuid
        try:
            uuid_obj = uuid.UUID(uuid_to_test, version=4)
        except ValueError:
            return False
        return uuid_obj.hex == uuid_to_test
    
    @staticmethod
    def uuid_generate():
        import uuid
        return uuid.uuid4().hex

    def init_item(self, item):
        if item.name == '':
            item.name = self.DEFAULT_ITEM_NAME

        if item.uuid == '':
            item.uuid = self.uuid_generate()

    def init_active_members(self):
        self.active_item = self.init_active_item()
        
        if self.active_item is not None:
            assert self.uuid_is_valid(self.active_item.uuid)

    def get_collection(self):
        return self.coll

    def get_coll_enum_items(self):
        items = []
        enumerated_items = list(enumerate(self.get_items()))
        enumerated_items.sort(key=lambda i: i[1].name)

        for idx, item in enumerated_items:
            items.append((str(item.uuid), item.name, "", idx))
        return items

    def create_item(self, set_active=True):
        new_item = self.get_items().add()
        self.init_item(new_item)

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
        self.set_active_item_uuid(self.get_items()[new_idx].uuid if new_idx >=0 else '')

    def get_active_item_uuid(self):
        return self.desc.active_item_uuid
    
    def get_item_by_uuid(self, uuid):
        for item in self.get_items():
            if uuid == item.uuid:
                return item
            
        return None
    
    def get_item_by_uuid_safe(self, uuid):
        item = self.get_item_by_uuid(uuid)

        if item is None:
            raise AttributeError()
            
        return item

    def get_active_item_idx(self):
        active_item_uuid = self.get_active_item_uuid()

        for idx, item in enumerate(self.get_items()):
            if active_item_uuid == item.uuid:
                return idx

        return -1

    def init_active_item(self):
        return self.get_item_by_uuid(self.get_active_item_uuid())
    
    def get_items(self):
        return self.coll.items
    
    def get_active_item(self):       
        return self.active_item

    def get_active_item_safe(self):
        if self.active_item is None:
            raise AttributeError()
        
        return self.active_item

    def set_active_item_uuid(self, uuid):
        self.desc.active_item_uuid = uuid
        self.init_active_members()

    def __len__(self):
        return len(self.get_items())

    def ensure_selected(self):
        if len(self) == 0:
            return
        
        if self.active_item is None:
            self.set_active_item_uuid(self.get_items()[0].uuid)

    def draw_item(self, item, layout):
        item.draw(layout)
        