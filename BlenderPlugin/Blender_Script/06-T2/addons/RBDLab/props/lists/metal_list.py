# import bpy
from typing import List, Union
# from ...addon.naming import RBDLabNaming
from bpy.types import PropertyGroup, UIList, Object, Collection
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty, EnumProperty
from ...Global.functions import hide_collection_in_viewport, unhide_collection_in_viewport, hide_collection_in_render
from ...Global.get_common_vars import get_common_vars
from .metal_modifiers_list import MetalModifiersList


""" Metal """

class RBDLAB_UL_draw_metal(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = False

        if not item.id_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        row = layout.row(align=True)

        # label_txt = item.label_txt
        # row.label(text="  " + label_txt)
        row.prop(item, "label_txt", text="", emboss=False)

        # si tiene creado el metal mesh, para visualizar o el metal o los chunks o ambos:
        right_icons = layout.row(align=True)
        right_icons.alignment = 'RIGHT'
        
        right_icons.prop(item, "metal_or_fractures", text=" ", expand=True)

        rm_button = right_icons.row(align=True)
        rm_button.separator(factor=0.8)
        rm_button.alert = True
        rm_button.operator("rbdlab.metalsoft_creation_rm_metal_mesh", text="", emboss=False, icon='X').id_to_rm = str("[\"" + item.id_name +"\", \""+ item.from_coll_id + "\"]")



class Metal_StoredObjects(PropertyGroup):
    ob: PointerProperty(type=Object)


class Metal_StoredCollections(PropertyGroup):
    coll: PointerProperty(type=Collection)


class MetalListItem(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id_name: StringProperty(name="ID")
    from_coll: PointerProperty(type=Collection)
    from_coll_id: StringProperty(name="ID")
    modifiers: PointerProperty(type=MetalModifiersList)


    stored_originals: CollectionProperty(type=Metal_StoredObjects)
    def add_original(self, ob:Object) -> None:
        # prevenimos guardar objectos que ya esten guardados:
        if not any(ob_item.ob == ob for ob_item in self.stored_originals):
            _item = self.stored_originals.add()
            _item.ob = ob
    
    stored_collections: CollectionProperty(type=Metal_StoredCollections)
    def add_coll(self, coll:Collection) -> None:
        # prevenimos guardar objectos que ya esten guardados:
        if not any(c_item.coll == coll for c_item in self.stored_collections):
            _item = self.stored_collections.add()
            _item.coll = coll
    
    stored_gn_ob: CollectionProperty(type=Metal_StoredObjects)
    def add_gn_ob(self, ob:Object) -> None:
        # prevenimos guardar objectos que ya esten guardados:
        if not any(ob_item.ob == ob for ob_item in self.stored_gn_ob):
            _item = self.stored_gn_ob.add()
            _item.ob = ob

    
    def do_remove(self, context):
        
        tcoll_list = get_common_vars(context, get_tcoll_list=True)
        
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list

        self.remove = False
        metal_list.remove_item(self.id_name)
        metal_list.list_index = 0
    

    remove: BoolProperty(
        default=False, 
        update=do_remove
    )


    def metal_or_fractures_update(self, context):

        tcoll = self.from_coll

        if self.metal_or_fractures == {'METAL'}:
            # ver metal:

            # los chunks visivbilidad viewport y render OFF
            hide_collection_in_viewport(context, tcoll.name)
            hide_collection_in_render(tcoll.name)

            # el "Select Original" de la ui de Metal Creation en viewport y render ON 
            [(
                org_ob.ob.hide_set(False), 
                setattr(org_ob.ob, "hide_render", False)
              ) for org_ob in self.stored_originals]
            

        elif self.metal_or_fractures == {'FRACTURES'}:
            # ver fracturas:

            # los chunks en viewport ON en render OFF
            unhide_collection_in_viewport(context, tcoll.name)
            hide_collection_in_render(tcoll.name)

            # el "Select Original" en viewport OFF en render ON
            [(
                org_ob.ob.hide_set(True), 
                setattr(org_ob.ob, "hide_render", False)
              ) for org_ob in self.stored_originals]

        elif 'FRACTURES' in self.metal_or_fractures and 'METAL' in self.metal_or_fractures:
            # los chunks en viewport ON en render OFF
            unhide_collection_in_viewport(context, tcoll.name)
            hide_collection_in_render(tcoll.name)
            # el "Select Original" en viewport y render ON
            [(
                org_ob.ob.hide_set(False), 
                setattr(org_ob.ob, "hide_render", False)
              ) for org_ob in self.stored_originals]

    metal_or_fractures: EnumProperty(
        name="Metal Visualization",
        items=[
            ('METAL',       "",        "Visualize Metal",      'SNAP_FACE', 1),
            ('FRACTURES',   "",    "Visualize Fractures",  'SNAP_VERTEX', 2),
        ],
        options={'ENUM_FLAG'},
        default={'METAL'},
        update=metal_or_fractures_update
    )



class MetalList(PropertyGroup):
    
    def list_index_update(self, context):

        item = self.active
        if not item:
            return

    list_index: IntProperty(name="Mesh Deform List", description="Metal Mesh Deform List", default=-1, update=list_index_update)
    list: CollectionProperty(type=MetalListItem)


    def add_item(self, label_txt:str, item_id:str, tcoll:Collection, from_coll_id:str, originals:List, link_coll:Union[List[Collection], Collection], GN_ob:Union[List[Object], Object]):
        all_previous_items_names = self.get_all_items_names
        if label_txt not in all_previous_items_names:

            item = self.list.add()
            item.id_name = item_id
            item.label_txt = label_txt
            
            if tcoll:
                item.from_coll = tcoll

            if from_coll_id:
                item.from_coll_id = from_coll_id

            # agregamos los objetos:
            if originals:
                [item.add_original(ob) for ob in originals]

            if link_coll:
                
                if isinstance(link_coll, List):
                    [item.add_coll(c) for c in link_coll]
                
                elif isinstance(link_coll, Collection):
                    item.add_coll(link_coll)
            
            if GN_ob:
                
                if isinstance(GN_ob, List):
                    [item.add_gn_ob(ob) for ob in GN_ob]

                elif isinstance(GN_ob, Object):
                    item.add_gn_ob(GN_ob)


            # seteamos el ultimo elemento como activo:
            self.list_index = self.length-1
 

    @property
    def clear_originals(self):
        
        item = self.active
        if not item:
            return
        
        item.stored_originals.clear()


    @property
    def active(self):
        
        # me aseguro de que el indice esta dentro del rango:
        if not (0 <= self.list_index < self.length):
            return            
            
        return self.list[self.list_index]


    @property
    def is_void(self):
        return False if len(self.list) > 0 else True


    @property
    def length(self):
        return len(self.list)


    @property
    def get_all_originals(self):
        return list(set([org_ob.ob for item in self.list for org_ob in item.stored_originals]))
    
    @property
    def get_current_originals(self):
        
        active = self.active
        if not active:
            return

        return list(set([org_ob.ob for org_ob in active.stored_originals]))
    

    @property
    def get_all_metal_links(self):
        return list(set([c.coll for item in self.list for c in item.stored_collections]))
    
    @property
    def get_current_metal_links(self):
        
        active = self.active
        if not active:
            return

        return list(set([c.coll for c in active.stored_collections]))

    
    @property
    def get_active_id(self):

        active = self.active
        if not active:
            return
        
        return active.id_name


    @property
    def get_all_items(self):
        return [item for item in self.list]


    @property
    def get_all_items_names(self):
        return [item.label_txt for item in self.list]


    @property
    def get_all_items_ids(self):
        return [item.id_name for item in self.list]


    def get_item_from_id(self, target_id:str):
        for list_item in self.list:
            if list_item.id_name == target_id:
                return list_item


    def get_item_from_active_group_id(self, active_group_id):
        return next((item.id_name for item in self.list if item.from_active_group == active_group_id), None) 


    def remove_item(self, id_to_rm:str):
        idx = next((idx for idx, group in enumerate(self.list) if group.id_name == id_to_rm), None)
        self.list.remove(idx)
        self.list_index = self.length-1
