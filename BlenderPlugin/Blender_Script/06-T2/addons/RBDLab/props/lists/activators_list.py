from bpy.types import PropertyGroup, UIList, Object, Menu
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty, FloatProperty
from ...addon.naming import RBDLabNaming
from ...Global.functions import set_active_object
from .common_list_methods import CommonList
from ...Global.get_common_vars import get_common_vars


""" Activators List """


class RBDLAB_UL_draw_activators(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        self.use_filter_show = False

        if not item.id_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        # layout.scale_x = 0.55
        row = layout.row(align=True)

        compute = row.row(align=True)
        compute.scale_x = 0.9
        compute.prop(item, "compute", text="")
        
        # items:
        # row.prop(item, "label_txt", text="", emboss=False, icon='LIGHTPROBE_SPHERE')
        dict_icons = {'SPHERE':'MESH_UVSPHERE', 'CUBE':'CUBE', 'MESH':'MESH_DATA'}
        main = row.row(align=True)
        main.prop(item.activator, "name", text="", emboss=False, icon=dict_icons[item.type])

        # Si tiene creado el metal mesh, para visualizar o el metal o los chunks o ambos:
        right_sect = layout.row(align=True)
        right_sect.alignment = 'RIGHT'

        # Select icon:
        sel_bt = right_sect.row(align=True)
        sel_bt.enabled = item.visible
        sel_bt.alignment = 'RIGHT'
        sel_bt.prop(item, "select_activators", text="", icon='RESTRICT_SELECT_OFF' if item.select_activators else 'RESTRICT_SELECT_ON', emboss=False)
        
        right_sect.separator(factor=0.8)
        
        # Visibility icon:
        visib_bt = right_sect.row(align=True)
        visib_bt.alignment = 'RIGHT'
        visib_bt.prop(item, "visible", text="", icon='HIDE_OFF' if item.visible else 'HIDE_ON', emboss=False)

        right_sect.separator(factor=0.8)

        # Remove icon:
        rm_button = right_sect.row(align=True)
        rm_button.alignment = 'RIGHT'
        rm_button.scale_x = 1.1
        rm_button.alert = True
        rm_button.operator("rbdlab.act_rm_item", text="", emboss=False, icon='X').id_to_rm = item.id_name



class Activators_lst_StoredObjects(PropertyGroup):
    ob: PointerProperty(type=Object)

class Activators_lst_StoredTypes(PropertyGroup):
    type: StringProperty(default="")


class Activators_lst_item(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id_name: StringProperty(name="ID")
    activator: PointerProperty(type=Object)
    type: StringProperty(name="")

    def compute_update(self, context):
        # Actualizamos el estado en el propio objeto:
        activator = self.activator
        activator[RBDLabNaming.ACT_OB_COMPUTE] = self.compute

    compute: BoolProperty(
        name="Compute",
        description="Compute this Activator",
        default=True,
        update=compute_update
    )
    
    def do_remove(self, context):
        
        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)
        tcoll = tcoll_list.active
        
        if not tcoll:
            return

        layer_active = rbdlab.lists.ac_layers_list.active
        if not layer_active:
            return
        
        activators_list = layer_active.activators_list
        activators_list.remove_item(self.id_name)
        activators_list.list_index = 0

    remove: BoolProperty(
        default=False, 
        update=do_remove
    )

    def select_activators_update(self, context):
        
        rbdlab, tcoll_list, ac_layers_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True, get_ac_layers_list=True)
        tcoll = tcoll_list.active
        
        if not tcoll:
            return

        layers_item = ac_layers_list.active

        if not layers_item:
            return

        activators_list = layers_item.activators_list
        activator_item = activators_list.get_item_from_id(self.id_name)
        
        if not activator_item:
            return

        ob = activator_item.activator
        ob.select_set(self.select_activators)


    select_activators: BoolProperty(
        default=False, 
        update=select_activators_update
    )

    def visible_update(self, context):
        
        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)
        tcoll = tcoll_list.active
        
        if not tcoll:
            return

        ac_layers_list = rbdlab.lists.ac_layers_list
        layers_item = ac_layers_list.active

        if not layers_item:
            return

        activators_list = layers_item.activators_list
        activator_item = activators_list.get_item_from_id(self.id_name)
        
        if not activator_item:
            return

        ob = activator_item.activator
        ob.hide_set(not self.visible)


    visible: BoolProperty(
        default=True, 
        update=visible_update
    )

    @staticmethod
    def activators_scale_update(self, context, call_from):

        tcoll_list, ac_layers_list = get_common_vars(context, get_tcoll_list=True, get_ac_layers_list=True)
        tcoll = tcoll_list.active
        
        if not tcoll:
            return

        layer_active = ac_layers_list.active
        if not layer_active:
            return
        
        if call_from == "activators_scale":

            # Para manipular solo el activo:
            
            activators_list = layer_active.activators_list
            act = activators_list.active

            new_scale = [self.activators_scale] * 3
            if act.activator.scale != new_scale: 
                act.activator.scale = new_scale 
            ##  act.dimensions = [self.activators_scale] * 3
            ##  bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        elif call_from == "all_activators_scales":

            # Para manipular todos al mismo tiempo:
            
            activators_list = layer_active.activators_list
            items_activators = activators_list.get_all_computable_items_activators
            new_scale = [self.all_activators_scales] * 3

            for act in items_activators:
                
                if act.activators_scale != self.all_activators_scales:
                    act.activators_scale = self.all_activators_scales
                
                if act.activator.scale != new_scale:
                    act.activator.scale = new_scale
                
                if act.all_activators_scales != self.all_activators_scales:
                    act.all_activators_scales = self.all_activators_scales

    activators_scale: FloatProperty(
        name="Scale", 
        description="Individual Sacle", 
        default=1, 
        min=0.01, 
        update=lambda self, context: self.activators_scale_update(self, context, "activators_scale")
    )

    all_activators_scales: FloatProperty(
        name="Scale", 
        description="All Act Sacles", 
        default=1, 
        min=0.01, 
        update=lambda self, context: self.activators_scale_update(self, context, "all_activators_scales")
    )

    #------------------------------------------------------------------------------------------------------------------------------
    # Other Properties:
    #------------------------------------------------------------------------------------------------------------------------------



class Activators_list(PropertyGroup, CommonList):
    
    def list_index_update(self, context):

        rbdlab, ac_layers_list = get_common_vars(context, get_rbdlab=True, get_ac_layers_list=True)
        layer = ac_layers_list.active

        item = self.active
        if not item:
            return
        
        act = item.activator
        set_active_object(context, act)

        # si estamos trabajando con Vertex Groups:
        if layer.type == 'VERTEX_GROUPS':

            brush_mod = act.modifiers.get(RBDLabNaming.ACT_BRUSH_MOD)
            if not brush_mod:
                return            

            # Actualizamos las propiedades del ui, recuperando el data del activator acitvo:
            lab_actvtrs = rbdlab.activators

            if lab_actvtrs.dpaint_paint_source != brush_mod.brush_settings.paint_source:
                lab_actvtrs.dpaint_paint_source = brush_mod.brush_settings.paint_source
            
            if lab_actvtrs.dpaint_paint_distance != brush_mod.brush_settings.paint_distance:
                lab_actvtrs.dpaint_paint_distance = brush_mod.brush_settings.paint_distance

            if lab_actvtrs.dpaint_proximity_falloff != brush_mod.brush_settings.proximity_falloff:
                lab_actvtrs.dpaint_proximity_falloff = brush_mod.brush_settings.proximity_falloff
            
            if lab_actvtrs.dpaint_invert_proximity != brush_mod.brush_settings.invert_proximity:
                lab_actvtrs.dpaint_invert_proximity = brush_mod.brush_settings.invert_proximity
            
            if lab_actvtrs.dpaint_use_negative_volume != brush_mod.brush_settings.use_negative_volume:
                lab_actvtrs.dpaint_use_negative_volume = brush_mod.brush_settings.use_negative_volume

            if lab_actvtrs.dpaint_use_proximity_project != brush_mod.brush_settings.use_proximity_project:
                lab_actvtrs.dpaint_use_proximity_project = brush_mod.brush_settings.use_proximity_project

            if lab_actvtrs.dpaint_ray_direction != brush_mod.brush_settings.ray_direction:
                lab_actvtrs.dpaint_ray_direction = brush_mod.brush_settings.ray_direction


    list_index: IntProperty(
                                name="Activators List", 
                                description="The Activators List", 
                                default=-1, 
                                update=list_index_update
                            )
    list: CollectionProperty(type=Activators_lst_item)


    def add_item(self, label_txt:str, item_id:str, activator:Object, type:str) -> None:

        item = self.list.add()
        item.id_name = item_id
        item.label_txt = label_txt
        item.activator = activator
        item.type = type
        item.compute = True
        
        # seteamos el ultimo elemento como activo:
        self.list_index = self.length-1
    

    @property
    def get_all_activators(self):
        return list(set([actv.activator for actv in self.list]))
    
    
    @property
    def get_all_computable_activators(self):
        return list(set([actv.activator for actv in self.list if actv.compute]))
    
    @property
    def get_all_computable_items_activators(self):
        return list(set([actv for actv in self.list if actv.compute]))

    
    @property
    def get_all_types(self):
        # return list(set([t.type for item in self.list for t in item.types]))
        return [item.type for item in self.list]


    @property
    def get_current_type(self):
        
        active = self.active
        if not active:
            return

        return active.type
    

    @property
    def get_current_activator(self):
        
        active = self.active
        if not active:
            return        

        return active.activator
    

    @property
    def get_all_computable_ids(self):
        return list(set([actv.id_name for actv in self.list if actv.compute]))


    def get_activator_by_id(self, id_name):
        for item in self.list:
            if item.id_name == id_name:
                return item.activator
        
        print("Not found " + id_name + " id, check that your id is an activator id and not a layer id.")
        return None


class RBDLAB_MT_activators_dropdow(Menu):
    bl_label = "Activators Dropdown"
    # Operator Types Flag Items (Parece ser que no es de Menu, 3.6 se lo come, pero blender 4.0 no):
    # bl_options = {'REGISTER', 'UNDO'}

    def draw(self, context):
        layout = self.layout

        tcoll_list, ac_layers_list = get_common_vars(context, get_tcoll_list=True, get_ac_layers_list=True)
        tcoll = tcoll_list.active
        
        if not tcoll:
            layout.enabled = False

        layers_item = ac_layers_list.active

        if not layers_item:
            layout.enabled = False

        activators_list = layers_item.activators_list

        layout.operator("rbdlab.act_dropdown", text="Mark All", icon='CHECKBOX_HLT').action = "mark_all"
        layout.operator("rbdlab.act_dropdown", text="Unmark All", icon='CHECKBOX_DEHLT').action = "unmark_all"
        
        layout.separator()

        layout.operator("rbdlab.act_dropdown", text="Select Marked", icon='RESTRICT_SELECT_OFF').action = "select_all"
        layout.operator("rbdlab.act_dropdown", text="Deselect Marked", icon='RESTRICT_SELECT_ON').action = "deselect_all"
        
        layout.separator()

        layout.operator("rbdlab.act_dropdown", text="Hide All", icon='HIDE_ON').action = "hide_all"
        layout.operator("rbdlab.act_dropdown", text="Unhide All", icon='HIDE_OFF').action = "unhide_all"
        
        layout.separator()

        layout.operator("rbdlab.act_dropdown", text="Delete Marked", icon='TRASH').action = "delete_all"
        layout.enabled = not activators_list.is_void