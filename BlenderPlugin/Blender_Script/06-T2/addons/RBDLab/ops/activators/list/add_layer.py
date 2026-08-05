import bpy
from uuid import uuid4
from datetime import datetime
from ....addon.naming import RBDLabNaming
from bpy.types import Operator, Object, VertexGroup
from ....Global.functions import create_modifier, set_active_object
from ...metalsoft.common.reorder_modifiers import reorder_modifiers
# from ....addon.paths import RBDLabPreferences

has_kinematics = None



class ACTIVATORS_OT_create_item(Operator):
    bl_idname = "rbdlab.act_add_layer"
    bl_label = "Add Layer"
    bl_description = "Add Layer"
    bl_options = {'REGISTER', 'UNDO'}


    # def toggle_kinematics_update(self, context):
    
    #     scn = context.scene
    #     rbdlab = scn.rbdlab
    #     tcoll_list = rbdlab.lists.target_coll_list
    #     chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

    #     for ob in chunks:

    #         if not ob.select_get():
    #             continue
            
    #         if not hasattr(ob, "rigid_body"):
    #             continue

    #         ob.rigid_body.kinematic = self.toggle_kinematics

    #         if self.toggle_kinematics:
    #             ob[RBDLabNaming.RBD_KINEMATIC] = True
    #             ob[RBDLabNaming.RBD_SEL_KINEMATIC] = True
            
    #         else:
    #             if RBDLabNaming.RBD_KINEMATIC in ob:
    #                 del ob[RBDLabNaming.RBD_KINEMATIC]

    #             if RBDLabNaming.RBD_SEL_KINEMATIC in ob:
    #                 del ob[RBDLabNaming.RBD_SEL_KINEMATIC]

    #     # if self.toggle_kinematics:
    #     #     rbdlab.physics.rigidbodies.kinematic = True


    # toggle_kinematics: BoolProperty(default=False, update=toggle_kinematics_update)


    def check_if_hasent_kinematics(self, context, rbdlab):

        tcoll_list = rbdlab.lists.target_coll_list
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        rbd_chunks = [ob for ob in chunks if ob.rigid_body and ob.select_get()]
        if rbd_chunks:
            hasent_kinematics = next((ob for ob in rbd_chunks if not ob.rigid_body.kinematic), None)
            return hasent_kinematics
        
        return None
    

    def check_if_has_rigidbodies(self, context, rbdlab):
        tcoll_list = rbdlab.lists.target_coll_list
        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)
        return next((True for ob in chunks if ob.rigid_body and ob.select_get()), None)

    
    def is_valid_object(self, ob: Object) -> bool:
        
        #-----------------------------------------------------------------------------------------------------------
        # NOTA: hay que intentar prohibir volver a incluir chunks ya incluidos, pero no globalmente, sino por tipo.
        #-----------------------------------------------------------------------------------------------------------

        return (
            ob.type == 'MESH' and 
            ob.visible_get() and 
            # RBDLabNaming.ACETONABLE in ob and # Si ya fue marcado como included (cuando se usaba el inlude viejo)
            # RBDLabNaming.ACETONABLE not in ob and # Si NO fue previamente marcado como included (ahora se hace auto include) <-(si se quiere reincluir chunks ya incluidos)
            RBDLabNaming.ACTIVATORS_OBJECTS not in ob and
            RBDLabNaming.GROUND not in ob.name and 
            RBDLabNaming.SUFIX_BBOX not in ob.name and
            ob.select_get() # ahora al tener auto include es requisito q esté selected
        )


    def is_rigid_body(self, ob: Object) -> bool:
        return (
            hasattr(ob, "rigid_body") and 
            hasattr(ob.rigid_body, "type")
        )


    def is_rigid_body_active(self, ob: Object) -> bool:
        
        if not ob.rigid_body:
            return False
        
        return ob.rigid_body.type == 'ACTIVE'
    

    def include_chunk(self, context, ob):
        # addon_preferences = RBDLabPreferences.get_prefs(context)
        ob[RBDLabNaming.ACETONABLE] = True
        # col_activators = list(addon_preferences.col_activators)
        # ob.color_stack.add_color(col_activators)
        # ob.color = col_activators


    def add_canvas(self, context, objects:list, name_layer:str) -> None:
        
        # Agregamos y seteamos los vertex groups:
        def add_vertex_group(ob: Object) -> VertexGroup:
            vg = ob.vertex_groups.get(RBDLabNaming.ACT_VG_DP_WEIGHT)
            if not vg:
                vg = ob.vertex_groups.new(name=RBDLabNaming.ACT_VG_DP_WEIGHT)
        
            vg.add(range(len(ob.data.vertices)), 1.0, 'ADD')
            return vg

        for ob in objects:

            set_active_object(context, ob)

            canvas_mod = ob.modifiers.get(RBDLabNaming.ACT_CANVAS_MOD)
            if not canvas_mod:
                canvas_mod = create_modifier(ob, RBDLabNaming.ACT_CANVAS_MOD, 'DYNAMIC_PAINT')

            if not canvas_mod:
                continue

            # Pongo el modifier de RBDLab_Canvas despues del RBDLab_SurfaceDeform :
            canvas_idx = ob.modifiers.find(RBDLabNaming.ACT_CANVAS_MOD)
            surface_deform_idx = ob.modifiers.find(RBDLabNaming.SURFACE_DEFORM)

            if canvas_idx != -1 and surface_deform_idx != -1:
                ob.modifiers.move(canvas_idx, surface_deform_idx+1)
            
            # canvas_settings = canvas_mod.canvas_settings # <- este no lo puedo guardar en la var antes del op type_toggle
            if not hasattr(canvas_mod.canvas_settings, "canvas_surfaces"): # canvas_settings en este punto sería NoneType (si es la primera vez)
                bpy.ops.dpaint.type_toggle(type='CANVAS')

            canvas_settings = canvas_mod.canvas_settings # <- lo vuelvo a recuperar con el type_toggle ya hecho
            canvas_surface = canvas_settings.canvas_surfaces.active
            canvas_surface.surface_type = 'WEIGHT'
            vg = add_vertex_group(ob)
            canvas_surface.output_name_a = vg.name
            point_cache = canvas_surface.point_cache
            point_cache.name = ob.name

            # canvas_mod_index = ob.modifiers.find(canvas_mod.name)
            # if canvas_mod_index != 0:
            #     if ob.modifiers.active != canvas_mod:
            #         ob.modifiers.active = canvas_mod
            #     ob.modifiers.move(canvas_mod_index, 0)
            #    # bpy.ops.object.modifier_move_up({'object': ob}, modifier=canvas_mod.name)
            
            # reordenamos
            # reorder_modifiers(ob)



    def execute(self, context):
        start = datetime.now()

        scn = context.scene
        rbdlab = scn.rbdlab
        ui = rbdlab.ui
        
        activators = rbdlab.activators
        work_with = activators.work_with


        if 'KINEMATIC' in work_with:
            hasent_kinematics = self.check_if_hasent_kinematics(context, rbdlab)
            if hasent_kinematics:
                self.report({'ERROR'}, "You don't have kinematics in your chunks in your Target Collection!")
                return {'CANCELLED'}
        
        
        if 'VERTEX_GROUPS' in work_with:
            # pongo la ui de disolve por defecto al crearse:
            ui.dpaint_use_dissolve = False

            have_rbd = self.check_if_has_rigidbodies(context, rbdlab)
            if have_rbd:
                self.report({'ERROR'}, "You have RigidBodies in your chunks, this is incompatible with Canvas/Brushes!")
                return {'CANCELLED'}


        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if 'VERTEX_GROUPS' not in work_with:

            # Si no estamos en Vertex Groups si necesitamos el tcoll:
            if not tcoll:
                self.report({'ERROR'}, "In valid Target Collection!")
                return {'CANCELLED'}

        target_objects = set()
        
        # Preparando los includes:
        # ahora al tener auto include es requisito q esté selected
        # si usamos Vertex Group irá solo por la selección:
        if activators.type_selection == "Scene" or 'VERTEX_GROUPS' in work_with:
            source_obs = [ob for ob in context.view_layer.objects if ob.select_get()]
            source_feedback = "current Scene selection"

        elif activators.type_selection == "Collection":
            source_obs = [ob for ob in tcoll.objects if ob.select_get()]
            source_feedback = "Target Collection"



        #------------------------------------------------------------------------------
        # Compruebo si los chunks no fueron ya incluidos al listado con el mismo type:
        #------------------------------------------------------------------------------
        ac_layers_list = rbdlab.lists.ac_layers_list
        # work_with = set(work_with)
        all_items = ac_layers_list.get_all_items

        for item in all_items:

            if item.type != work_with:
                continue
            
            item_includes = [it.ob for it in item.stored_includes]

            # si son del mismo tipo, chekeaamos si tiene ya alguno de los chunks:
            common_chunk = next((ob for ob in source_obs if ob in item_includes), None)
            if common_chunk:
                self.report({'WARNING'},  "The chunk " + common_chunk.name + " has already been added to the Layers List with the same type!")
                return {'CANCELLED'}
        #------------------------------------------------------------------------------


        not_have_rbd = False
        # recopilamos los objetos:
        for ob in source_obs:

            if not self.is_valid_object(ob):
                continue
            
            # Si no tiene color (por ejemplo si con vertex group pillas un mesh q no tienen nada del addon)
            color = ob.color_stack.get_last_color()
            if not color:
                # Guardamos su color actual para poder luego al hacer el exclude restaurarlo:
                ob.color_stack.add_color(ob.color)

            # Si solo se solicita Vertex Groups, no es necesario que tenga rigidbodies puestos:
            if 'VERTEX_GROUPS' not in work_with:

                if not self.is_rigid_body(ob):
                    not_have_rbd = True
                    continue
                
                if not self.is_rigid_body_active(ob):
                    not_have_rbd = True
                    continue
            
            # le hago el auto include:
            self.include_chunk(context, ob)

            # guardamos los objetso:
            target_objects.add(ob)
        
        # Si no hay includeds:
        if len(target_objects) < 1:

            if not_have_rbd:
                self.report({'WARNING'}, "No chunks with RigidBodies have been detected in " + source_feedback + "!")
            else:
                self.report({'WARNING'}, "No chunks selected have been detected in " + source_feedback + "!")

            return {'CANCELLED'}    

        # Procedemos
        ac_layers_list = rbdlab.lists.ac_layers_list
        all_types = ac_layers_list.get_all_types
        
        # un layer por cada type:
        if len(work_with) > 0:
            target_objects = list(target_objects)

            # un id por cada item de la lista:
            item_id = str(uuid4())

            total = all_types.count(work_with)
            padding = len(str(total)) + 1
            # name_layer = t_name.title() + "_" + str(total).zfill(padding)
            abbreviations = {
                                "Constraints": "CO",
                                "Kinematic": "KM",
                                "Vertex_Groups": "VG",
                                "Dynamic": "DY",
                                "Deactivation": "DA"
                                }
            name_layer = abbreviations[work_with.title()] + "_" + str(total).zfill(padding)
            
            if 'VERTEX_GROUPS' in work_with:
                self.add_canvas(context, target_objects, name_layer)

            # Integramos initial velociti si se usa kinematik:
            # types_dict = {work_with, 'INITIALVEL'} if work_with == 'KINEMATIC' else {work_with}

            ac_layers_list.add_item(label_txt=name_layer, item_id=item_id, tcoll=tcoll, objects=target_objects, work_with=work_with)
            
            # guardamos el nuevo color a los chunks el en stack:
            active_item = ac_layers_list.active
            if active_item:

                col_activators = [active_item.r_c, active_item.g_c, active_item.b_c, active_item.a_c]
                for ob in target_objects:

                    # Al crear el Dynamic desactivamos los Deactivation:
                    if work_with == 'DYNAMIC' and ob.rigid_body:
                        ob.rigid_body.use_deactivation = False
                
                    # les ponemos su color:
                    ob.color_stack.add_color(col_activators)
                    ob.color = col_activators

            

        # Cambiamos a la segunda pestaña:
        # Como aun no se el nombre definitivo para el segundo item del enum, y por no tener q estar cambiandolo siempre:
        # accedemos a todos los items de enum, pero solo me quedo con uno:
        item_no_creation = next((item.identifier for item in ui.bl_rna.properties['activators_mode'].enum_items if item.identifier != 'CREATION'), None)
        if item_no_creation:
            ui.activators_mode = item_no_creation

        # Si entramos en Dynamic, ya que start_on_off_toggle por defecto está en OFF, lo seteamos al crearlo: 
        if 'DYNAMIC' in work_with:
            active_item.start_on_off_toggle = 'OFF'
        
        # oculto el post panel:
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

        print("[activators.add_layer] End: " + str(datetime.now() - start))

        bpy.ops.object.select_all(action='DESELECT')    
        return {'FINISHED'}


    def invoke(self, context, event):
        
        scn = context.scene
        rbdlab = scn.rbdlab
        activators = rbdlab.activators
        work_with = activators.work_with

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if 'VERTEX_GROUPS' in work_with:
            return self.execute(context)
        
        
        if 'DYNAMIC' in work_with:
            dynamic_list = tcoll.rbdlab.dynamic_list
            # Si ya tiene keyframes previos en DYNAMIC Animations, impedimos continuar:
            if dynamic_list.is_void == False:
                self.report({'WARNING'}, "You already have previous dynamic keyframes in Physics > RBD > Animation!")
                return {'CANCELLED'}

        
        # si no se está trabajando con kinematic skipeamos el popup:
        if 'KINEMATIC' not in work_with:
            return self.execute(context)

        # hasent_kinematics = self.check_if_hasent_kinematics(context, rbdlab)
        # if hasent_kinematics:
        #     return context.window_manager.invoke_props_dialog(self, width=200)
        # else:
        #     # Si tiene kinematics adelante:
        #     return self.execute(context)
        return self.execute(context)
        
            

    def draw(self, context):
        layout = self.layout

        col = layout.column()                
        col.label(text="You don't have kinematics in your")
        col.label(text="chunks in your target collection!")
        # col.prop(self, "toggle_kinematics", text="UnSet Kinematic" if self.toggle_kinematics else "Set Kinematic", toggle=True)
