from bpy.types import Operator
# from ......addon.naming import RBDLabNaming
from bpy.props import IntProperty
from ......Global.get_common_vars import get_common_vars

class RBDLAB_OT_physics_rbd_anim_add_off_on(Operator):
    bl_idname = "rbdlab.physics_rbd_anim_add_off_on"
    bl_label = "Add Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    frame: IntProperty(
        name="Frame",
        default=0
    )

    def check_previous_kf(self, dynamic_list, keyframes, chunks):
        # chekeamos si existen keyframes previos guardados en la posicion que se está intentando guardar los nuevos:
        items = dynamic_list.get_items_with_keyframes(keyframes)
        if items:
            chunks_with_keyframes = []
            for item in items:
                for chunk in item.stored_chunks:
                    chunks_with_keyframes.append(chunk.chunk)
            
            # para saber si hay elementos en ambas listas:
            intersection = set(chunks) & set(chunks_with_keyframes)
            if len(intersection) > 0:
                self.report({'ERROR'}, "Already exist keyframes in " + str(keyframes) + " in some chunk")
                return {'CANCELLED'}


    def execute(self, context):

        rbdlab, tcoll_list = get_common_vars(context, get_rbdlab=True, get_tcoll_list=True)

        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation
        mode = rbd_animation_porps.add_mode

        tcoll = tcoll_list.active

        if not mode or not tcoll:
            return {'CANCELLED'}        

        # si estamos visualizando metal, lo cambio a chunks para poder trabajar:
        tcoll_item = tcoll_list.active_item
        metal_list = tcoll_item.metal_list
        current_metal = metal_list.active

        if current_metal:
            metal_previous_state = current_metal.metal_or_fractures
            if 'FRACTURES' not in metal_previous_state:
                current_metal.metal_or_fractures = {'FRACTURES'}

        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)
        chunks_with_rbd = [chunk for chunk in chunks if chunk.rigid_body]

        if not chunks_with_rbd:
            self.report({'ERROR'}, "No RigidBodies in chunks!")
            return {'CANCELLED'}
        
        dynamic_list = tcoll.rbdlab.dynamic_list
        # current_frame = scn.frame_current
        current_frame = self.frame

        # para el by selection:

        if rbd_animation_porps.by_selection:
            chunks = [chunk for chunk in chunks if chunk in context.selected_objects]

        # uno previo en ON el current en off, el current+1 mantenemos off y el ultimo en on:
        keyframes = [current_frame-1, current_frame, current_frame+1, current_frame+2]
        
        if mode != "OFF/ON":
            keyframes = keyframes[:-2]
        
        check = self.check_previous_kf(dynamic_list, keyframes, chunks)
        if check:
            if 'CANCELLED' in check:
                return {'CANCELLED'}

        for chunk in chunks:
            
            if not chunk.rigid_body:
                continue
            
            chunk_rbd = chunk.rigid_body

            chunk_rbd.enabled = True if mode != "ON" else False
            chunk.keyframe_insert(data_path="rigid_body.enabled", frame=keyframes[0])
            
            chunk_rbd.enabled = False if mode != "ON" else True
            chunk.keyframe_insert(data_path="rigid_body.enabled", frame=keyframes[1])
            
            # solo si es de tipo OFF/ON hacemos los dos finales:
            if mode == "OFF/ON":
                chunk_rbd.enabled = False
                chunk.keyframe_insert(data_path="rigid_body.enabled", frame=keyframes[2])

                chunk_rbd.enabled = True
                chunk.keyframe_insert(data_path="rigid_body.enabled", frame=keyframes[3])

        dynamic_list.add_item(
            mode=mode, 
            label_txt=mode + " in Frame: " + str(current_frame), 
            keyframes=keyframes, 
            chunks=chunks
        )
        dynamic_list.list_index = dynamic_list.length-1

        # restauro la visibilidad del metal:
        if current_metal and metal_previous_state:
            current_metal.metal_or_fractures = metal_previous_state

        return {'FINISHED'}
    
    def invoke(self, context, event):

        scn, rbdlab = get_common_vars(context, get_scn=True, get_rbdlab=True)

        self.frame = scn.frame_current

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if not tcoll:
            return {'CANCELLED'}

        # Si ya tengo animaciones de activators prohibimos agregar más animaciones aquí:
        ac_layers_list = rbdlab.lists.ac_layers_list
        if ac_layers_list.is_void == False:
             all_computable_types = ac_layers_list.get_all_computable_types
             if 'DYNAMIC' in all_computable_types:
                 activators = ac_layers_list.get_all_computable_activators
                 if len(activators) >0:
                     self.report({'WARNING'}, "You already have previous dynamic keyframes in Activators > Layers!")
                     return {'CANCELLED'}
        
        return context.window_manager.invoke_props_dialog(self, width=250)

    def draw(self, context):
        layout = self.layout

        rbdlab = get_common_vars(context, get_rbdlab=True)

        rbd_props = rbdlab.physics.rigidbodies
        rbd_animation_porps = rbd_props.animation

        col = layout.column(align=True)
        col.use_property_split = False
        col.use_property_decorate = False
        
        col.prop(self, "frame")
        col.separator()

        options = col.row(align=True)
        options.scale_y = 1.3
        options.prop(rbd_animation_porps, "add_mode", expand=True)
