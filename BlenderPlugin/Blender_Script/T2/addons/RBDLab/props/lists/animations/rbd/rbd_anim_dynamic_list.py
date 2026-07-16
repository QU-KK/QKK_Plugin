from uuid import uuid4
from typing import List
from bpy.types import PropertyGroup, UIList, Object
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty

""" Physics > RBD > Animation > RBD Dynamic """

class RBDLAB_UL_draw_rbd_anim_dynamic(UIList):
    case_sensitive: BoolProperty(name="aA", description="Use case sensitive or not", default=False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        if not item.label_txt or not item.id:
            layout.prop(item, "remove", text="Clear", icon='X')
            return
        
        label_txt = item.label_txt
        item_id = item.id
        row = layout.row(align=True)

        if item.offseted > 0:
            label_txt = label_txt + " Offseted: " + str(item.offseted)

        row.label(text=label_txt)

        # select_chunks:
        sel_icon = 'RESTRICT_SELECT_OFF' if item.select_chunks else 'RESTRICT_SELECT_ON'
        row.prop(item, "select_chunks", text="", icon=sel_icon, emboss=False)

        row.separator()
        rm_button = row.row(align=True)
        rm_button.alert = True
        # con este solo lo quitaríamos del listado:
        # rm_button.prop(item, "remove", text="", emboss=False, icon='X')
        # con este operador tenemos undo y eliminamos lo que corresponda en el operador:
        rm_button.operator("rbdlab.physics_rbd_anim_dynamic_list_rm_item", text="", emboss=False, icon='X').id_to_rm = item_id

    def draw_filter(self, context, layout):
        """UI code for the filtering/sorting/search area."""
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

            if item.name:

                if self.case_sensitive:
                    match = self.filter_name in item.name
                else:
                    match = self.filter_name.lower() in item.name.lower()

                if match:
                    filtered_flags.append(self.bitflag_filter_item)
                else:
                    filtered_flags.append(0)

        # print(filtered_flags, new_order)
        return filtered_flags, new_order


class StoredChunk(PropertyGroup):
    chunk: PointerProperty(type=Object)

class StoredKeyFrames(PropertyGroup):
    frame: IntProperty(default=-1)

class RBDAnimDynamicListItem(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id: StringProperty(name="ID")
    mode: StringProperty(default="")

    # guardamos los keyframes:
    stored_keyframes: CollectionProperty(type=StoredKeyFrames)
    def add_frame(self, kf:int):
        # prevenimos guardar frames que ya esten guardados:
        if not any(kf_item.frame == kf for kf_item in self.stored_keyframes):
            _item = self.stored_keyframes.add()
            _item.frame = kf
    
    # guardamos los chunks:
    stored_chunks: CollectionProperty(type=StoredChunk)
    def add_chunk(self, ob:Object):
        # prevenimos guardar chunks que ya esten guardados:
        if not any(chunk_item.chunk == ob for chunk_item in self.stored_chunks):
            _item = self.stored_chunks.add()
            _item.chunk = ob

    def do_remove(self, context):
        if not self.remove:
            return
        
        scn = context.scene
        rbdlab = scn.rbdlab

        rbd_props = rbdlab.physics.rigidbodies
        dynamic_list = rbd_props.animation.dynamic_list 
        dynamic_list.remove_item(self.id)

        self.remove = False

    remove: BoolProperty(default=False, update=do_remove)
    offseted: IntProperty(default=-1)
    
    def select_chunks_update(self, context):
        [item_chunk.chunk.select_set(self.select_chunks) for item_chunk in self.stored_chunks]

    select_chunks: BoolProperty(default=False, update=select_chunks_update)

class RBDAnimDynamicList(PropertyGroup):
    dynamic_list: CollectionProperty(type=RBDAnimDynamicListItem)


    def list_index_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        item = self.active
        if not item:
            return
        
        rbd_animation_porps = rbdlab.physics.rigidbodies.animation
        
        if item.offseted > 0:
            rbd_animation_porps.offset_duration = item.offseted
        else:
            rbd_animation_porps.offset_duration = 0

    list_index: IntProperty(
        default=-1,
        update=list_index_update
    )


    def add_item(self, mode:str, label_txt:str, keyframes:List, chunks:List):
        item = self.dynamic_list.add()
        item.id = str(uuid4())
        item.mode = mode
        item.label_txt = label_txt
        
        # guardamos los keyframes en item.stored_keyframes[z].frame:
        for kf in keyframes:
            item.add_frame(kf)
                
        if chunks:
            for chunk in chunks:
                item.add_chunk(chunk)
        
        # seteamos el ultimo elemento como activo:
        self.list_index = len(self.dynamic_list)-1

    
    @property
    def active(self):
        return self.dynamic_list[self.list_index] if len(self.dynamic_list) > 0 else None
    
    
    @property
    def is_void(self):
        return False if len(self.dynamic_list) > 0 else True
    

    @property
    def length(self):
        return len(self.dynamic_list)
    
    
    def get_items_with_keyframes(self, keyframes):
        return [item for item in self.dynamic_list for f in item.stored_keyframes if f.frame in keyframes]


    def get_item_from_id(self, target_id:str):
        return next((list_item for list_item in self.dynamic_list if list_item.id == target_id), None)


    def remove_item(self, id_to_rm:str):
        for index, list_item in enumerate(self.dynamic_list):
            if list_item.id == id_to_rm:
                # si el id es el deseado lo quitamos del property group:
                self.dynamic_list.remove(index)
                self.list_index = min(max(0, index - 1), len(self.dynamic_list) - 1)
                break
    