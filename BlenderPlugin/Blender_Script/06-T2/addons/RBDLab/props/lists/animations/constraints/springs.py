from uuid import uuid4
from typing import List
from bpy.types import PropertyGroup, UIList, Object
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty
from .....Global.get_common_vars import get_common_vars
# from ...common_list_methods import CommonList # no puedo usar estos metodos por los nombres tipo: springs_list


""" Constraints > Animation > Springs """


class RBDLAB_UL_draw_const_springs_anim(UIList):
    case_sensitive: BoolProperty(name="aA", description="Use case sensitive or not", default=False)


    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        rbdlab_const = get_common_vars(context, get_constraints=True)

        group_name = rbdlab_const.get_group_name_by_idname(item.from_active_group)

        if not item.label_txt or not item.id or not group_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        # label_txt = group_name + item.label_txt
        label_txt = item.label_txt

        item_id = item.id
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

        rm_button.operator("rbdlab.const_rm_springs_keyframes", text="", emboss=False, icon='X').id_to_rm = item_id


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


class CSprings_StoredChunk(PropertyGroup):
    chunk: PointerProperty(type=Object)

class CSprings_StoredConstraint(PropertyGroup):
    constraint: PointerProperty(type=Object)

class CSprings_StoredKeyFrames(PropertyGroup):
    frame: IntProperty(default=-1)

class CSprings_StoredDpath(PropertyGroup):
    dpath: StringProperty(default="")


class ConstraintSpringsListItem(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id: StringProperty(name="ID")
    mode: StringProperty(default="")
    from_active_group: StringProperty(default="")


    # guardamos los keyframes:
    stored_keyframes: CollectionProperty(type=CSprings_StoredKeyFrames)
    def add_frame(self, kf:int) -> None:
        # prevenimos guardar frames que ya esten guardados:
        if not any(kf_item.frame == kf for kf_item in self.stored_keyframes):
            _item = self.stored_keyframes.add()
            _item.frame = kf
    

    # guardamos los chunks:
    stored_chunks: CollectionProperty(type=CSprings_StoredChunk)
    def add_chunk(self, ob:Object) -> None:
        # prevenimos guardar chunks que ya esten guardados:
        if not any(chunk_item.chunk == ob for chunk_item in self.stored_chunks):
            _item = self.stored_chunks.add()
            _item.chunk = ob
    

    # guardamos los constraints:
    stored_constraints: CollectionProperty(type=CSprings_StoredConstraint)
    def add_constraint(self, ob:Object) -> None:
        # prevenimos guardar chunks que ya esten guardados:
        if not any(constraint_item.constraint == ob for constraint_item in self.stored_constraints):
            _item = self.stored_constraints.add()
            _item.constraint = ob
    

    # guardamos los dpath:
    stored_dpaths: CollectionProperty(type=CSprings_StoredDpath)
    def add_dpath(self, dpath:str) -> None:
        _item = self.stored_dpaths.add()
        _item.dpath = dpath


    def do_remove(self, context) -> None:
        if not self.remove:
            return
        
        rbdlab_const = get_common_vars(context, get_constraints=True)

        rbdlab_const_active = rbdlab_const.get_active_group
        springs_list = rbdlab_const_active.springs_list

        springs_list.remove_item(self.id)
        self.remove = False

    remove: BoolProperty(
        default=False, 
        update=do_remove
    )
    offseted: IntProperty(default=-1)
    

    def select_chunks_update(self, context):
        [item_chunk.chunk.select_set(self.select_chunks) for item_chunk in self.stored_chunks]

    select_chunks: BoolProperty(default=False, update=select_chunks_update)

class SpringsList(PropertyGroup):
    

    def list_index_update(self, context) -> None:

        rbdlab = get_common_vars(context, get_rbdlab=True)

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
    springs_list: CollectionProperty(type=ConstraintSpringsListItem)

    by_selection: BoolProperty(
        default=False
    )

    def add_item(self, rbdlab_const, from_active_group:str, label_txt:str, keyframes:List, chunks:List, constraints:List, dpaths:str) -> None:

        item = self.springs_list.add()
        item.id = str(uuid4())
        item.label_txt = label_txt
        item.from_active_group = from_active_group
        
        # Guardo los keyframes en item.stored_keyframes[z].frame:
        for kf in keyframes:
            item.add_frame(kf)
                
        # Agrego los chunks:
        if chunks:
            [item.add_chunk(chunk) for chunk in chunks]
        
        # Agrego los constraints:
        if constraints:
            [item.add_constraint(const) for const in constraints]
        
        if dpaths:
            [item.add_dpath(dpath) for dpath in dpaths]
        
        # Seteo el ultimo elemento como activo:
        self.list_index = len(self.springs_list)-1


    @property
    def active(self):
        return self.springs_list[self.list_index] if len(self.springs_list) > 0 else None
    

    @property
    def type(self) -> str:
        return "springs"
    

    @property
    def is_void(self) -> bool:
        return False if len(self.springs_list) > 0 else True
    

    @property
    def length(self) -> int:
        return len(self.springs_list) 
    

    @property
    def all_keyframes_stored(self) -> List:
        return [f.frame for item in self.springs_list for f in item.stored_keyframes]


    @property
    def all_chunks_stored(self) -> List:
        return [c.chunk for item in self.springs_list for c in item.stored_chunks]
    
    @property
    def get_all_dpaths_stored(self) -> List:
        return [dp.dpath for item in self.springs_list for dp in item.stored_dpaths]

    @property
    def all_const_stored(self) -> List:
        return [c.constraint for item in self.springs_list for c in item.stored_constraints]
    

    def get_dpaths_from_id(self, target_id:str) -> List:
        return [dp.dpath for item in self.springs_list if item.id == target_id for dp in item.stored_dpaths]
    

    def get_id_from_active_group_if_have_target_keyframes(self, keyframes:list[int], dpaths:List[str]) -> List:
        
        items = set()

        # Por cada item del listado:
        for item in self.springs_list:

            # Por cada dpath que tenga guardados:
            for d in item.stored_dpaths:
                dpath = d.dpath
                
                # Le quito el prefijo: rigid_body_constraint.
                dpath = dpath.replace("rigid_body_constraint.", "")
                
                # Si el dpath actual está en los dpath del input:
                if dpath in dpaths:

                    # Compruebo cada frame guardado: 
                    for f in item.stored_keyframes:

                        # Si el frame está en los frames del input
                        if f.frame in keyframes:
                            items.add(item.from_active_group)
        
        # devolvemos el resultado:
        return list(items)
    

    def get_item_from_id(self, target_id:str) -> ConstraintSpringsListItem:
        for list_item in self.springs_list:
            if list_item.id == target_id:
                return list_item


    def get_item_from_active_group_id(self, active_group_id) -> str:
        return next((item.id for item in self.springs_list if item.from_active_group == active_group_id), None) 


    def remove_item(self, id_to_rm:str) -> None:
        idx = next((idx for idx, group in enumerate(self.springs_list) if group.id == id_to_rm), None)
        self.springs_list.remove(idx)
        self.list_index = len(self.springs_list)-1