from uuid import uuid4
from typing import List
from bpy.props import EnumProperty, IntProperty, BoolProperty, StringProperty
from bpy.types import Operator, Object
from ...base import BaseConstraintOperator
# from .....Global.basics import ocultar_post_panel_settings
# from .....addon.naming import RBDLabNaming
from ..check_previous_keyframes import check_keyframes
from .....Global.get_common_vars import get_common_vars


class RBDLAB_OT_constswitch_add(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_constswitch_add"
    bl_label = "Animation Enable/Disable"
    bl_description = "Add keyframes for Enable and Disable Constrinats"
    bl_options = {'REGISTER', 'UNDO'}
    
    id_name: StringProperty(default="-1")

    # lo hago por separado para poder acceder a la descripcion luego:
    modos = [
            ('ENABLE_TO_DISABLE', "Enable to Disable", ""),
            ('DISABLE_TO_ENABLE', "Disable to Enable", ""),
        ]

    mode : EnumProperty(
        items=modos, 
        default='ENABLE_TO_DISABLE'
    )
    
    frame: IntProperty(default=0)

    single_item: BoolProperty(default=True)


    def ikf_enabe_to_disable(self, dpath, const, rbd_const, user_frame):
        rbd_const.enabled = True
        const.keyframe_insert(data_path=dpath, frame=user_frame)

        rbd_const.enabled = False
        const.keyframe_insert(data_path=dpath, frame=user_frame+1)


    def ikf_disable_to_enable(self, dpath, const, rbd_const, user_frame):
        rbd_const.enabled = False
        const.keyframe_insert(data_path=dpath, frame=user_frame)

        rbd_const.enabled = True
        const.keyframe_insert(data_path=dpath, frame=user_frame+1)


    def action(self, context, rbdlab_const, active_group, const_coll, chunks: List[Object], const_objects: List[Object]) -> set:
        
        tcoll_list = get_common_vars(context, get_tcoll_list=True)

        # necesitamos el target collection para guardar sus items dentro:
        tcoll = tcoll_list.active

        if not tcoll:
            return {'CANCELLED'}
        
        selected_objects = context.selected_objects
    
        # ocultar_post_panel_settings()
        
        constswitch_list = tcoll.rbdlab.constswitch_list

        # Si es por seleccion:
        if constswitch_list.by_selection:
            # Compruebo la seleccion:
            check_valid_obs = next((ob for ob in selected_objects if ob.type == 'MESH'), None)
            if check_valid_obs is None:
                self.report({'ERROR'}, "No selected chunks were detected!")
                return {'CANCELLED'}

            # Filtramos los objetos por seleccion (solo los constraints que sus object (ambos) formen parte de la selecion actual):
            tmp_const_objects = [const for const in const_objects if const.rigid_body_constraint.object1 in selected_objects and const.rigid_body_constraint.object2 in selected_objects]
            if tmp_const_objects:
                const_objects = tmp_const_objects
            else:
                # Si no se encuentra ninguno, entonces con que solo uno de los dos objects tenga realcion ya vale:
                const_objects = [const for const in const_objects if const.rigid_body_constraint.object1 in selected_objects or const.rigid_body_constraint.object2 in selected_objects]
            
            if not const_objects:
                self.report({'ERROR'}, "No constraints were detected!")
                return {'CANCELLED'}

            # Elimino los repetidos (creando un conjunto "set" y luego volvemos a convertirlo a lista):
            const_objects = list(set(const_objects))

            chunks = set([chunk for chunk in chunks if chunk in context.selected_objects])
            chunks = list(chunks)
        
        check = check_keyframes(self, active_group, constswitch_list, self.frame, chunks)
        if check:
            if 'CANCELLED' in check:
                return {'CANCELLED'}
            
        # Procedemos:
        dpath = "rigid_body_constraint.enabled"
        
        if self.id_name == "-1":
            short_id = str(uuid4())[:6]
        else:
            short_id = str(self.id_name)

        cp_sid = "rbdlab_constswitch_" + short_id
        
        for const in const_objects:
            
            rbd_const = const.rigid_body_constraint
            if not rbd_const:
                continue

            if cp_sid not in const:
                const[cp_sid] = rbd_const.enabled

            if self.mode == 'ENABLE_TO_DISABLE':
                self.ikf_enabe_to_disable(dpath, const, rbd_const, self.frame)

            elif self.mode == 'DISABLE_TO_ENABLE':
                self.ikf_disable_to_enable(dpath, const, rbd_const, self.frame)
        
        if self.mode == 'ENABLE_TO_DISABLE':
            # mode_desription = self.modos[0][1]
            mode_desription = "E to D"
            active_group.enable_disable_animed = True
        
        elif self.mode == 'DISABLE_TO_ENABLE':
            # mode_desription = self.modos[1][1]
            mode_desription = "D to E"
            active_group.disable_enable_animed = True
        
        # Si se usa single item, insertamos un item cada vez que ejecuto este operador,
        # de lo contrario en switcher.py el operador de Switcher Between Groups, trataré de hacer un único item por pero se ejecutará 2 veces.
        if self.single_item:

            # Agregamos el nuevo item con toda la info que nos hace falta:
            constswitch_list.add_item(
                id_name = short_id,
                mode = self.mode, 
                from_active_group = active_group.idname, 
                label_txt = " " + mode_desription + " In Frame: " + str(self.frame), 
                keyframes = [self.frame, self.frame+1], 
                chunks = chunks,
                constraints = const_objects,
            )

        return {'FINISHED'}
    
    def invoke(self, context, event):
        scn = context.scene
        self.frame = scn.frame_current
        return context.window_manager.invoke_props_dialog(self, width=200)

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.prop(self, "frame", text="Frame:")
        col.prop(self, "mode", text="Choose", expand=True)
