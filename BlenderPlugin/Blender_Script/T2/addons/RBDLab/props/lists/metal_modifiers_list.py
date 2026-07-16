# import bpy
# from ...addon.naming import RBDLabNaming
from bpy.types import PropertyGroup, UIList, Collection, Object
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty
from .common_list_methods import CommonList
from ...Global.functions import set_active_object


""" Metal Modifiers """

class RBDLAB_UL_draw_metal_modifiers(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = False

        if not item.id_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        row = layout.row(align=True)

        # label_txt = item.label_txt
        # row.label(text="  " + label_txt)
        row.prop(item, "label_txt", text="", emboss=False, icon=item.icon)

        # si tiene creado el metal mesh, para visualizar o el metal o los chunks o ambos:
        right_icons = layout.row(align=True)
        right_icons.alignment = 'RIGHT'

        show_bts = right_icons.row(align=True)
        show_bts.prop(item, "show_viewport", text="", icon='RESTRICT_VIEW_OFF' if item.show_viewport else 'RESTRICT_VIEW_ON')
        show_bts.prop(item, "show_render", text="", icon='RESTRICT_RENDER_OFF' if item.show_render else 'RESTRICT_RENDER_ON')
        
        rm_button = right_icons.row(align=True)
        rm_button.separator(factor=0.8)
        rm_button.alert = True
        rm_button.operator("rbdlab.metalsoft_creation_remove_modifiers", text="", emboss=False, icon='X').id_to_rm = item.id_name

class MetalModifiers_StoredObjects(PropertyGroup):
    ob: PointerProperty(type=Object)

class MetalModifiersListItem(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id_name: StringProperty(name="ID")
    icon: StringProperty(default='MODIFIER')
    mod_type: StringProperty(name="")
    mod_name: StringProperty(name="")

    stored_objects: CollectionProperty(type=MetalModifiers_StoredObjects)
    def add_ob(self, ob:Object) -> None:
        # prevenimos guardar objectos que ya esten guardados:
        if not any(ob_item.ob == ob for ob_item in self.stored_objects):
            _item = self.stored_objects.add()
            _item.ob = ob

    def do_remove(self, context):
        pass
        # metal_list = rbdlab.lists.bfracture_gn_list
        # metal_list.remove_item(self.id_name)
        # metal_list.list_index = 0

    remove: BoolProperty(
        default=False, 
        # update=do_remove
    )
    
    # Monitor y camarita en el listado para la Visibilidad de los modifiers:
    @staticmethod
    def visibility_update(self, context, prop:str) -> None:
        for item_ob in self.stored_objects:
            ob = item_ob.ob
            mod = ob.modifiers.get(self.mod_name)
            if mod:
                setattr(mod, prop, getattr(self, prop))

    show_viewport: BoolProperty(
        default=True,
        update=lambda self, context: self.visibility_update(self, context, "show_viewport")
    )
    show_render: BoolProperty(
        default=True,
        update=lambda self, context: self.visibility_update(self, context, "show_render")
    )


class MetalModifiersList(PropertyGroup, CommonList):
    
    def list_index_update(self, context):
        item = self.active
        if not item:
            return
        
        # Hacemos el modifier activo al seleccionar el item del listado:
        mod_name = item.mod_name
        objects = self.get_current_stored_objects
        
        if objects:
            first_ob = objects[0]
            set_active_object(context, first_ob)

            for ob in objects:
                mod = ob.modifiers.get(mod_name)
                if mod:
                    ob.modifiers.active = mod

    list_index: IntProperty(name="Metal Modifiers List", description="Metal Modifiers List", default=-1, update=list_index_update)
    list: CollectionProperty(type=MetalModifiersListItem)


    def add_item(self, label_txt:str, item_id:str, mod_type:str, icon:str, mod_name:str) -> None:
        all_previous_items_names = self.get_all_items_names
        if label_txt not in all_previous_items_names:

            item = self.list.add()
            item.id_name = item_id
            item.label_txt = label_txt
            item.mod_type = mod_type
            item.icon = icon
            item.mod_name = mod_name

            # seteamos el ultimo elemento como activo:
            self.list_index = self.length-1

    @property
    def get_all_mod_types(self):
        return [item.mod_type for item in self.list]
    
    @property
    def get_current_stored_objects(self):
        active = self.active
        if not active:
            return
        
        return list(set([o.ob for o in active.stored_objects]))
    
    @property
    def get_first_object(self):
        item = self.active
        if not item:
            return
        
        objects = self.get_current_stored_objects
        if objects:
            first_ob = objects[0]
            return first_ob
    
    @property
    def get_all_objects(self):
        all_objects = set()
        for item in self.list:
            for o in item.stored_objects:
                all_objects.add(o.ob) 
        return list(all_objects)
    
    @property
    def get_all_mod_names(self):
        return [item.mod_name for item in self.list]
    
    @property
    def get_active_mod_in_first_object(self):
        item = self.active
        if not item:
            return
        
        objects = self.get_current_stored_objects
        if objects:
            first_ob = objects[0]

            # devuelvo el que corresponde, el el que estuviera activo:
            return first_ob.modifiers.get(item.mod_name)