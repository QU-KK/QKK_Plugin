import bpy
from uuid import uuid4
from typing import List
from bpy.props import EnumProperty
from bpy.types import Operator, Object, Collection
from ....addon.naming import RBDLabNaming
from ....Global.functions import rm_ob, create_new_collection, create_modifier, set_active_object

class ACTIVATORS_OT_add_activator(Operator):
    bl_idname = "rbdlab.act_add"
    bl_label = "Add Activator"
    bl_description = "Add Activator"
    bl_options = {'REGISTER', 'UNDO'}

    activator_type: EnumProperty(
        items=[
            ('SPHERE',  "Sphere",   "",  0),
            ('CUBE',    "Cube",     "",  1),
            ('MESH',    "Mesh",     "",  2)
        ],
        default='SPHERE'
    )

    def configure_activator(self, scn, coll_dest:Collection, ob:Object, loop_ob:Object, with_obs:bool) -> None:
        
        # si no se lo pongo el bpy.ops.rbdlab.act_set() le pone 'MESH' por defecto
        ob["activator"] = self.activator_type 

        ob.visible_camera = False
        ob.visible_diffuse = False
        ob.visible_glossy = False
        ob.display_type = 'WIRE'
        
        if with_obs and loop_ob:
            # Con objetos preseleccionamos ponemos los activators en sus origenes y con sus dimensiones:
            ob.matrix_world = loop_ob.matrix_world.copy()
            ob.dimensions = [max(loop_ob.dimensions)] * 3
            ob[RBDLabNaming.ACTIVATOR_OB_TO_PARENT] = loop_ob.name
        else:
            # lo ponemos en el 3d cursor:
            ob.location = scn.cursor.location

        coll_dest.objects.link(ob)
    

    def prepare_name(self, active_item, activators_list, activator_type:str)-> str:
        # Chuleta: los activator types pueden ser ('SPHERE' 'CUBE' 'MESH')
        
        # Todos los tipos del listado:
        all_types = activators_list.get_all_types 
        # El total de tipos que hay en el listado:
        total = all_types.count(activator_type)

        padding = len(str(total)) + 1
        # title = "AC_" + activator_type.title() + "_" + str(total).zfill(padding)
        # title = "AC_" + activator_type.upper()[:2] + "_" + str(total).zfill(padding)
        title = "AC_" + active_item.type[:1] + activator_type.upper()[:1] + "_" + str(total).zfill(padding)
        
        # Si ya existiera ese nombre:
        if title in bpy.data.objects:
            # Trato de iterar hasta que no exista:
            n = 1
            while title in bpy.data.objects:
                title = "AC_" + active_item.type[:1] + activator_type.upper()[:1] + "_" + str(total).zfill(padding+n)
                n += 1
        
        return title
    

    def in_3d_cursor(self, scn, active_item, new_activator: Object, dest_coll: Collection) -> None:
        
        # Creamos singles Activators en las coordenadas del 3D Cursor:

        self.configure_activator(scn, dest_coll, new_activator, None, False)
        
        ac_id = str(uuid4())
        new_activator.select_set(True)
        activators_list = active_item.activators_list
        title = self.prepare_name(active_item, activators_list, self.activator_type)
        new_activator.name = title
        new_activator.hide_render = True
        activators_list.add_item(title, ac_id, new_activator, self.activator_type)


    def with_preselection(self, scn, active_item, org_ob: Object, dest_coll: Collection, selected_obs: List[Object]) -> None:

        # Poniendo x activators en el numero de objetos 
        # seleccionados y en su misma posicion:

        for loop_ob in selected_obs:
        
            # Duplicamos objeto en low level:
            new_activator = org_ob.copy()
            new_activator.data = org_ob.data.copy()
            new_activator.animation_data_clear()

            ac_id = str(uuid4())
            self.configure_activator(scn, dest_coll, new_activator, loop_ob, True)  
        
            activators_list = active_item.activators_list
            title = self.prepare_name(active_item, activators_list, self.activator_type)
            new_activator.name = title
            new_activator.hide_render = True
            activators_list.add_item(title, ac_id, new_activator, self.activator_type)
        
    

    def mesh_method(self, contextx, sel_obs:List, active_item, ac_layers_list, activators_coll) -> None:
        # convertimos los objetos seleccionados por el usuario en activators:
        rbw_coll = bpy.data.collections.get(RBDLabNaming.RBD_WORLD)
        for org_ob in sel_obs:

            # org_ob["activator"] = self.activator_type
            # org_ob.select_set(True)

            # Para que no se copien los settings de rigidbodies y de conflicto de 
            # ciclo de dependencias al emparentarlo, lo desvinculo temporalmente del rbw_coll:
            with_rbd = False
            if rbw_coll:
                if org_ob.name in rbw_coll.objects:
                    with_rbd = True
                    rbw_coll.objects.unlink(org_ob)

            # Duplicamos objeto en low level:
            new_activator = org_ob.copy()
            new_activator.data = org_ob.data.copy()
            new_activator.animation_data_clear()

            ac_id = str(uuid4())
            activators_list = active_item.activators_list
            title = self.prepare_name(active_item, activators_list, self.activator_type)
            new_activator.name = title
            new_activator[RBDLabNaming.ACT_RECORD_TYPE] = ac_layers_list.get_current_type
            activators_list.add_item(title, ac_id, new_activator, self.activator_type)
            
            if new_activator.name not in activators_coll:
                activators_coll.objects.link(new_activator)
                new_activator.select_set(True)
                # para poder emparentarlo es necesario esto:
                new_activator[RBDLabNaming.ACTIVATOR_OB_TO_PARENT] = org_ob.name

            new_activator[RBDLabNaming.ACT_RM_MESH] = org_ob.name
            # org_ob.hide_set(True) # oculto en ojito
            new_activator.hide_render = True # oculto en render
            new_activator.show_wire = True # vemos en wireframe pero sin ser transparente
            
            # si tenía rbd se lo volvemos a poner:
            if with_rbd:
                rbw_coll.objects.link(org_ob)

    
    def check_collection(self, context) -> Collection:
        activators_coll = bpy.data.collections.get(RBDLabNaming.ACTIVATORS_COLL)
        if not activators_coll:
            activators_coll = create_new_collection(context, RBDLabNaming.ACTIVATORS_COLL)
        
        return activators_coll


    def add_dpaint_brushes(self, context, objects) -> None:
        if len(objects) > 0:

            first_ob = objects[0]
            set_active_object(context, first_ob)

            dpaint_mod = first_ob.modifiers.get(RBDLabNaming.ACT_BRUSH_MOD)
            if not dpaint_mod:
                dpaint_mod = create_modifier(first_ob, RBDLabNaming.ACT_BRUSH_MOD, 'DYNAMIC_PAINT')

            dpaint_mod.ui_type = 'BRUSH'
            if dpaint_mod.brush_settings is None:
                bpy.ops.dpaint.type_toggle(type='BRUSH')
    
            dpaint_mod.brush_settings.paint_source = 'VOLUME_DISTANCE'

            [ob.select_set(True) for ob in objects if not ob.select_get()]
            bpy.ops.object.make_links_data(type='MODIFIERS')


    def execute(self, context):

        scn = context.scene
        rbdlab = scn.rbdlab

        # tcoll_list = rbdlab.lists.target_coll_list
        # tcoll = tcoll_list.active

        ac_layers_list = rbdlab.lists.ac_layers_list
        active_item = ac_layers_list.active

        if not active_item:
            self.report({'ERROR'}, "It was not possible to obtain the active layer!")
            return {'CANCELLED'}
        
        # oculto el post panel:
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        
        types = ac_layers_list.get_current_type
        
        # si no existe la collection Activators la creamos:
        activators_coll = self.check_collection(context)

        sel_obs = [ob for ob in context.selected_objects if ob.type == "MESH" and ob.visible_get() and RBDLabNaming.ACTIVATORS_OBJECTS not in ob]
        bpy.ops.object.select_all(action='DESELECT')

        if self.activator_type == 'SPHERE':
            bpy.ops.mesh.primitive_uv_sphere_add()
        
        elif self.activator_type == 'CUBE':
            bpy.ops.mesh.primitive_cube_add(size=2.0, calc_uvs=False, enter_editmode=False)

        org_ob = context.active_object
        r_type = ac_layers_list.get_current_type
        org_ob[RBDLabNaming.ACT_RECORD_TYPE] = r_type


        if sel_obs:

            if self.activator_type == 'MESH':
                
                self.mesh_method(context, sel_obs, active_item, ac_layers_list, activators_coll)
                # rm_ob(org_ob)

            else:

                # En modo activator_type == 'SPHERE':
                # with preselected objects:
                self.with_preselection(scn, active_item, org_ob, activators_coll, sel_obs)
                rm_ob(org_ob)
        
            # Se hace el parent tanto si es de tipo spheres in obs como si es custom mesh del usuario:
            bpy.ops.rbdlab.act_parent(call='PARENT')
        
        else:

            # In 3D Cursor:
            self.in_3d_cursor(scn, active_item, org_ob, activators_coll)
        
        if 'VERTEX_GROUPS' in types:
            # aqui me da un ciclo de dependencia no se porque:
            self.add_dpaint_brushes(context, context.selected_objects)

        # tras crear activators vamos a la pestaña activators:
        active_item.activators_sect_vertex_group = 'ACTIVATORS'


        
        bpy.ops.rbdlab.act_set()
        return {'FINISHED'}


    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=200)
            

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        buttons_row = col.row(align=True)
        buttons_row.scale_y = 1.3
        buttons_row.prop(self, "activator_type", expand=True)
        if self.activator_type == 'MESH':
            col.box().label(text="Activator Object:  " + context.active_object.name, icon='INFO')
