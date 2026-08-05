import bpy
from typing import List
from ...addon.naming import RBDLabNaming
from ...Global.functions import set_active_object
from bpy.types import PropertyGroup, UIList, Object, Collection
from ...Global.geometry_nodes import get_gn_index_or_identifier_by
from bpy.props import StringProperty, IntProperty, CollectionProperty, IntProperty, BoolProperty, PointerProperty
from .common_list_methods import CommonList


""" Scatte > Boolean Fracture > GN """

class RBDLAB_UL_draw_bf_gn(UIList):
    case_sensitive: BoolProperty(name="aA", description="Use case sensitive or not", default=False)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        # scn = context.scene
        # rbdlab = scn.rbdlab
        
        if not item.id_name:
            layout.prop(item, "remove", text="Clear", icon='X')
            return

        row = layout.row(align=True)

        # label_txt = item.label_txt
        # row.label(text="  " + label_txt)
        row.prop(item, "label_txt", text="", emboss=False)


        sw_planes_points = row.row(align=True)
        sw_planes_points.alignment = 'RIGHT'
        sw_planes_points_icon = 'LIGHTPROBE_VOLUME' if item.switch_planes_points else 'VIEW_ORTHO' 
        sw_planes_points.prop(item, "switch_planes_points", text="", emboss=False, toggle=True, icon=sw_planes_points_icon)

        show_v = row.row(align=True)
        show_v_icon = 'RESTRICT_VIEW_OFF' if item.show_viewport else 'RESTRICT_VIEW_ON'
        show_v.prop(item, "show_viewport", text="", emboss=False, toggle=True, icon=show_v_icon)

        row.separator()
        rm_button = row.row(align=True)
        rm_button.alert = True
        rm_button.operator("rbdlab.boolean_fracture_rm", text="", emboss=False, icon='X').id_to_rm = item.id_name


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


class BF_GN_StoredObjects(PropertyGroup):
    ob: PointerProperty(type=Object)


class BFractureGNListItem(PropertyGroup):
    label_txt: StringProperty(name="Name")
    id_name: StringProperty(name="ID")
    from_coll: PointerProperty(type=Collection)
    
    # guardamos los objects:
    stored_base_planes: CollectionProperty(type=BF_GN_StoredObjects)
    def add_base_plane(self, ob:Object):
        # prevenimos guardar objectos que ya esten guardados:
        if not any(ob_item.ob == ob for ob_item in self.stored_base_planes):
            _item = self.stored_base_planes.add()
            _item.ob = ob
    
    stored_objects_to_fracture: CollectionProperty(type=BF_GN_StoredObjects)
    def add_objects_to_fracture(self, ob:Object):
        # prevenimos guardar objectos que ya esten guardados:
        if not any(ob_item.ob == ob for ob_item in self.stored_objects_to_fracture):
            _item = self.stored_objects_to_fracture.add()
            _item.ob = ob
    
    stored_bool_planes: CollectionProperty(type=BF_GN_StoredObjects)
    def add_bool_planes(self, ob:Object):
        # prevenimos guardar objectos que ya esten guardados:
        if not any(ob_item.ob == ob for ob_item in self.stored_bool_planes):
            _item = self.stored_bool_planes.add()
            _item.ob = ob
    
    def do_remove(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui

        bfracture_gn_list = rbdlab.lists.bfracture_gn_list
        bfracture_gn_list.remove_item(self.id_name)

        if bfracture_gn_list.is_void:
            ui.boolean_method_phase = 'NONE'
        
        bfracture_gn_list.list_index = 0
    

    remove: BoolProperty(
        default=False, 
        update=do_remove
    )
    
    def switch_planes_points_update(self, context):
        
        item = self
        base_plane = next((bp.ob for bp in item.stored_base_planes), None)
        if not base_plane:
            return
            
        GN_mod = base_plane.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        if not GN_mod:
            return

        group_input = GN_mod.node_group.nodes.get("Group Input")
        if group_input:
            identifier = get_gn_index_or_identifier_by("identifier", "name", "outputs", group_input, "Switch Planes/Points", debug=False)
            GN_mod[identifier] = self.switch_planes_points
            base_plane.data.update()

    switch_planes_points: BoolProperty(default=True, update=switch_planes_points_update)

    def show_viewport_update(self, context):
        
        item = self
        base_plane = next((bp.ob for bp in item.stored_base_planes), None)
        if not base_plane:
            return

        GN_mod = base_plane.modifiers.get(RBDLabNaming.BOOLFRACTURE_GN_OB)
        GN_mod.show_viewport = self.show_viewport
   
    show_viewport: BoolProperty(default=True, update=show_viewport_update)



class BFractureGNList(PropertyGroup, CommonList):
    
    def list_index_update(self, context):

        item = self.active
        if not item:
            return
        
        base_plane = next((bp.ob for bp in item.stored_base_planes), None)
        if not base_plane:
            return
        
        bpy.ops.object.select_all(action='DESELECT')
        if base_plane.name in context.view_layer.objects:
            base_plane.select_set(True)
            set_active_object(context, base_plane)

    list_index: IntProperty(default=-1, update=list_index_update)
    list: CollectionProperty(type=BFractureGNListItem)
    by_selection: BoolProperty(default=False)

    def add_item(self, label_txt:str, item_id:str, tcoll:Collection, base_planes:List, objects_to_fracture:List):
        all_previous_items_names = self.get_all_items_names
        if label_txt not in all_previous_items_names:

            item = self.list.add()
            item.id_name = item_id
            item.label_txt = label_txt
            item.from_coll = tcoll

            # agregamos los objetos:
            if base_planes:
                [item.add_base_plane(ob) for ob in base_planes]
            
            if objects_to_fracture:
                [item.add_objects_to_fracture(ob) for ob in objects_to_fracture]
            
            # seteamos el ultimo elemento como activo:
            self.list_index = self.length-1

    def store_bool_planes(self, bool_planes:List):
        item = self.active
        if not item:
            return
        
        if bool_planes:
            [item.add_bool_planes(ob) for ob in bool_planes]
    
    @property
    def clear_bool_planes(self):
        item = self.active
        if not item:
            return
        
        item.stored_bool_planes.clear()

    
    @property
    def get_base_plane(self):
        
        active = self.active
        if not active:
            return
        
        return next((bp.ob for bp in active.stored_base_planes), None)

    @property
    def get_all_base_planes(self):
        return list(set([bp.ob for item in self.list for bp in item.stored_base_planes]))
    
    @property
    def get_bool_plane(self):
        
        active = self.active
        if not active:
            return
        
        return next((bop.ob for bop in active.stored_bool_planes), None)
    
    @property
    def get_bool_planes(self):
        
        active = self.active
        if not active:
            return
        
        return [bop.ob for bop in active.stored_bool_planes]
    
    @property
    def get_objects_to_fracture(self):
        
        active = self.active
        if not active:
            return
        
        return [otf.ob for otf in active.stored_objects_to_fracture]
    
    @property
    def get_all_bool_planes(self):
        return list(set([bop.ob for item in self.list for bop in item.stored_bool_planes]))
    
    
    def get_item_from_active_group_id(self, active_group_id):
        return next((item.id_name for item in self.list if item.from_active_group == active_group_id), None) 
