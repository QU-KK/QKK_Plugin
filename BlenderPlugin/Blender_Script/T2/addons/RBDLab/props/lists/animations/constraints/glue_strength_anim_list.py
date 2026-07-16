from typing import List
from bpy.types import PropertyGroup, UIList, Object
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty

""" Constraints > Animation > Glue Strength """

class RBDLAB_UL_draw_glue_strength_anim(UIList):
    case_sensitive: BoolProperty(name="aA", description="Use case sensitive or not", default=False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab_const = rbdlab.constraints
        group_name = rbdlab_const.get_group_name_by_idname(item.from_active_group)

        if not item.label_txt or not item.id_name or not group_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        # label_txt = group_name + item.label_txt
        label_txt = item.label_txt

        item_id = item.id_name
        row = layout.row(align=True)

        # if item.offseted > 0:
        #     label_txt = label_txt + " Offseted: " + str(item.offseted)

        row.label(text=label_txt)

        # select_chunks:
        sel_icon = 'RESTRICT_SELECT_OFF' if item.select_chunks else 'RESTRICT_SELECT_ON'
        row.prop(item, "select_chunks", text="", icon=sel_icon, emboss=False)

        row.separator()
        rm_button = row.row(align=True)
        rm_button.alert = True

        rm_button.operator("rbdlab.const_rm_all_glue_keyframes", text="", emboss=False, icon='X').id_to_rm = item_id


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


class GS_StoredChunk(PropertyGroup):
    chunk: PointerProperty(type=Object)

class GS_StoredConstraint(PropertyGroup):
    constraint: PointerProperty(type=Object)

class GS_StoredKeyFrames(PropertyGroup):
    frame: IntProperty(default=-1)

class GlueStrengthListItem(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id_name: StringProperty(name="ID")
    mode: StringProperty(default="")
    from_active_group: StringProperty(default="")

    # guardamos los keyframes:
    stored_keyframes: CollectionProperty(type=GS_StoredKeyFrames)
    def add_frame(self, kf:int):
        # prevenimos guardar frames que ya esten guardados:
        if not any(kf_item.frame == kf for kf_item in self.stored_keyframes):
            _item = self.stored_keyframes.add()
            _item.frame = kf
    
    # guardamos los chunks:
    stored_chunks: CollectionProperty(type=GS_StoredChunk)
    def add_chunk(self, ob:Object):
        # prevenimos guardar chunks que ya esten guardados:
        if not any(chunk_item.chunk == ob for chunk_item in self.stored_chunks):
            _item = self.stored_chunks.add()
            _item.chunk = ob
    
    # guardamos los constraints:
    stored_constraints: CollectionProperty(type=GS_StoredConstraint)
    def add_constraint(self, ob:Object):
        # prevenimos guardar chunks que ya esten guardados:
        if not any(constraint_item.constraint == ob for constraint_item in self.stored_constraints):
            _item = self.stored_constraints.add()
            _item.constraint = ob

    def do_remove(self, context):
        if not self.remove:
            return
        
        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab_const = rbdlab.constraints

        rbdlab_const_active = rbdlab_const.get_active_group
        glue_strength_list = rbdlab_const_active.glue_strength_list

        glue_strength_list.remove_item(self.id)
        self.remove = False

    remove: BoolProperty(
        default=False, 
        update=do_remove
    )
    offseted: IntProperty(default=-1)
    
    def select_chunks_update(self, context):
        [item_chunk.chunk.select_set(self.select_chunks) for item_chunk in self.stored_chunks]

    select_chunks: BoolProperty(default=False, update=select_chunks_update)

class GlueStrengthList(PropertyGroup):
    
    def list_index_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        item = self.active
        if not item:
            return
        
        rbd_animation_porps = rbdlab.constraints.animations
        
        if item.offseted > 0:
            rbd_animation_porps.offset_duration = item.offseted
        else:
            rbd_animation_porps.offset_duration = 0

    list_index: IntProperty(
        default=-1,
        update=list_index_update
    )
    glue_strength_list: CollectionProperty(type=GlueStrengthListItem)

    by_selection: BoolProperty(
        default=False
    )

    def add_item(self, id_name:str, from_active_group:str, label_txt:str, keyframes:List, chunks:List, constraints:List):
        item = self.glue_strength_list.add()
        item.id_name = id_name
        item.label_txt = label_txt
        item.from_active_group = from_active_group
        
        # guardamos los keyframes en item.stored_keyframes[z].frame:
        for kf in keyframes:
            item.add_frame(kf)
                
        # agregamos los chunks:
        if chunks:

            [item.add_chunk(chunk) for chunk in chunks]
        
        # agregamos los constraints:
        if constraints:
            [item.add_constraint(const) for const in constraints]
        
        # seteamos el ultimo elemento como activo:
        self.list_index = len(self.glue_strength_list)-1

    @property
    def active(self):
        return self.glue_strength_list[self.list_index] if len(self.glue_strength_list) > 0 else None
    
    @property
    def type(self):
        return "glue_strength"
    
    @property
    def is_void(self):
        return False if len(self.glue_strength_list) > 0 else True
    
    @property
    def length(self):
        return len(self.glue_strength_list)
    
    @property
    def all_keyframes_stored(self):
        return [f.frame for item in self.glue_strength_list for f in item.stored_keyframes]

    @property
    def all_chunks_stored(self):
        return [c.chunk for item in self.glue_strength_list for c in item.stored_chunks]
    
    @property
    def all_const_stored(self):
        return [c.constraint for item in self.glue_strength_list for c in item.stored_constraints]
    
    def get_id_from_active_group_if_have_target_keyframes(self, keyframes:list[int]):
        return [item.from_active_group for item in self.glue_strength_list for f in item.stored_keyframes if f.frame in keyframes]

    def get_item_from_id(self, target_id:str):
        for list_item in self.glue_strength_list:
            if list_item.id_name == target_id:
                return list_item
    
    def get_item_from_active_group_id(self, active_group_id):
        return next((item.id_name for item in self.glue_strength_list if item.from_active_group == active_group_id), None) 

    def remove_item(self, id_to_rm:str):
        idx = next((idx for idx, group in enumerate(self.glue_strength_list) if group.id_name == id_to_rm), None)
        self.glue_strength_list.remove(idx)
        self.list_index = len(self.glue_strength_list)-1
    