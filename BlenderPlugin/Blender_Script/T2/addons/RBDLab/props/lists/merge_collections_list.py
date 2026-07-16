from uuid import uuid4
from bpy.types import PropertyGroup, UIList, Collection
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty

""" Target Collections > dorpdowm > Merge Collections """

class RBDLAB_UL_draw_merge_collections(UIList):
    case_sensitive: BoolProperty(name="aA", description="Use case sensitive or not", default=False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        if not item.id:
            layout.prop(item, "remove", text="Clear", icon='X')
            return
        
        if item.coll is None:
            return
        
        if not item.coll.name:
            return 

        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=item.coll.name, icon='OUTLINER_COLLECTION')

    def draw_filter(self, context, layout):
        """ UI code for the filtering/sorting/search area."""
        layout.separator()
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(self, "filter_name", text="", icon='VIEWZOOM')
        case_sensititve = row.row(align=True)
        case_sensititve.scale_x = 0.35
        case_sensititve.prop(self, "case_sensitive", toggle=True, text="aA")
        row.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)

        filtered_flags = []
        new_order = [i for i in range(len(items))]

        for item in items:

            if item.coll is None:
                continue

            if not item.coll.name:
                continue

            if item.coll.name:

                if self.case_sensitive:
                    match = self.filter_name in item.coll.name
                else:
                    match = self.filter_name.lower() in item.coll.name.lower()

                if match:
                    filtered_flags.append(self.bitflag_filter_item)
                else:
                    filtered_flags.append(0)

        # print(filtered_flags, new_order)
        return filtered_flags, new_order


class MCListItem(PropertyGroup):
    id: StringProperty(name="ID")
    coll: PointerProperty(type=Collection)

    def do_remove(self, context):
        pass
        # if not self.remove:
        #     return
        
        # scn = context.scene
        # rbdlab = scn.rbdlab

        # tcoll_list = rbdlab.lists.target_coll_list
        # tcoll = tcoll_list.active
        # if tcoll:

        #     coll_list = tcoll.rbdlab.list
        #     coll_list.remove_item(self.id)
        #     self.remove = False

    remove: BoolProperty(
        default=False, 
        # update=do_remove
    )
    selected: BoolProperty(default=False)

class MergeCollectionsList(PropertyGroup):
    
    list_index: IntProperty(default=-1)
    list: CollectionProperty(type=MCListItem)

    def add_item(self, coll):
        all_collections = self.all_collections
        if coll not in all_collections:
            item = self.list.add()
            item.id = str(uuid4())
            item.coll = coll
            # seteamos el ultimo elemento como activo:
            self.list_index = len(self.list)-1

    @property
    def active(self):
        return self.list[self.list_index] if len(self.list) > 0 else None

    @property
    def is_void(self):
        return False if len(self.list) > 0 else True
    
    @property
    def length(self):
        return len(self.list)
    
    @property
    def all_collections(self):
        return [item.coll for item in self.list]
    
    @property
    def get_all_items(self):
        return [item for item in self.list]
    
    @property
    def get_all_selected_items(self):
        return [item for item in self.list if item.selected]
    
    @property
    def get_all_selected_collections(self):
        return [item.coll for item in self.list if item.selected]

    @property   
    def clear_all_colls(self): 
        [self.list.remove(idx) for idx in range(len(self.list))]
        self.list_index = len(self.list)-1
    
    def get_item_from_id(self, target_id:str):
        for list_item in self.list:
            if list_item.id == target_id:
                return list_item
    
    def remove_item(self, id_to_rm:str):
        idx = next((idx for idx, group in enumerate(self.list) if group.id == id_to_rm), None)
        self.list.remove(idx)
        self.list_index = len(self.list)-1
    