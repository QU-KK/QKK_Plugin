import bpy
from uuid import uuid4
from typing import List
from itertools import chain
from bpy.types import Operator, Object
from ...base import BaseConstraintOperator
from .....addon.naming import RBDLabNaming
from bpy.props import IntProperty, FloatProperty
from ..check_previous_keyframes import check_keyframes


class GLUE_OT_set_glue_keyframes(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_set_glue_keyframes"
    bl_label = "Glue Strength Animation"
    bl_description = "Add keyframes in Glue Strength"
    bl_options = {'REGISTER', 'UNDO'}

    glue_anim_frame_initial: IntProperty(
        default=10,
        description="The initial frame where the first keyframe will be placed."
    )
    glue_initial_strength: FloatProperty(
        default=420.0
    )
    glue_anim_frame_end: IntProperty(
        default=11,
        description="The last frame where the end keyframe will be placed."
    )
    glue_end_strength: FloatProperty(
        default=0.0
    )
    
    def action(self, context, rbdlab_const, group, collection, chunks: List[Object], const_objects: List[Object]):

        if collection.name not in bpy.data.collections:
            self.report({'WARNING'}, "No GlueConstraints collection in the scene!")
            return {'CANCELLED'}
        
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active
        
        if not tcoll:
            return {'CANCELLED'}
        
        rbdlab_const_active = rbdlab_const.get_active_group
        glue_strength_list = rbdlab_const_active.glue_strength_list

        active_group = rbdlab_const.get_active_group
        chunks_group_const: List[Object] = rbdlab_const.get_chunks_from_group()

        if rbdlab_const.glue_anim_by_selection:
            valid_chunks = [ob for ob in context.selected_objects if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.GROUND not in ob]
            all_const_names_stored_in_chunk: List[str] = [ob[RBDLabNaming.CONSTRAINTS].split() for ob in valid_chunks if RBDLabNaming.CONSTRAINTS in ob]
        else:
            valid_chunks = [ob for ob in chunks_group_const if ob.type == 'MESH' and ob.visible_get() and RBDLabNaming.GROUND not in ob]
            all_const_names_stored_in_chunk: List[str] = [ob[RBDLabNaming.CONSTRAINTS].split() for ob in chunks_group_const if RBDLabNaming.CONSTRAINTS in ob]
        
        # print("all_const_names_stored_in_chunk", all_const_names_stored_in_chunk)
        # Nota: con list(chain.from_iterable(all_const_names_stored_in_chunk))) hacemos flatten la lista 2d a 1d
        real_const_obs: List[Object] = [context.scene.objects.get(const_name) for const_name in list(chain.from_iterable(all_const_names_stored_in_chunk)) if context.scene.objects.get(const_name)]
        # print("real_const_obs", real_const_obs)
        
        constraints_to_work: List[Object] = [const for const in real_const_obs if const.type == RBDLabNaming.CONST_TYPE]
        # print("object_to_work", object_to_work)

        if not constraints_to_work:
            if rbdlab_const.glue_anim_by_selection:
                self.report({'WARNING'}, "No Selected valid Chunks!1")
            else:
                self.report({'WARNING'}, "No valid Constraints in the collection!")
            return {'CANCELLED'}

        # remove doubles/duplicates in list:
        constraints_to_work = list(set(constraints_to_work))

        target_frames = [self.glue_anim_frame_initial, self.glue_anim_frame_end]
        check = check_keyframes(self, active_group, glue_strength_list, target_frames, constraints_to_work)
        if check:
            if 'CANCELLED' in check:
                return {'CANCELLED'}
        

        short_id = str(uuid4())[:6]
        cp_sid = "rbdlab_glue_" + short_id

        for const in constraints_to_work:
            
            # Los adjacents al estar unidos a varios chunks les afectaba los keyfraemes y no queremos eso:
            from_valid_coll = [coll.name for coll in const.users_collection if active_group.name in coll.name]
            # Chekeo si el constraint actual es de la collection correspondiente al active group con el que se esta trabajando:
            if not from_valid_coll:
                # si no está en la collection con la que se está trabajando lo skipeamos: 
                continue
            
            # si voy a meterle keyframes descarto que este ya muteado:
            if "rbdlab_const_muted" in const:
                del const["rbdlab_const_muted"]

            if not const.rigid_body_constraint:
                continue
            
            rbd_const = const.rigid_body_constraint
            
            if cp_sid not in const:
                const[cp_sid] = rbd_const.breaking_threshold

            rbd_const.breaking_threshold = self.glue_initial_strength
            dpath = "rigid_body_constraint.breaking_threshold"
            const.keyframe_insert(
                data_path=dpath,
                frame=self.glue_anim_frame_initial
            )
            rbd_const.breaking_threshold = self.glue_end_strength
            const.keyframe_insert(
                data_path=dpath,
                frame=self.glue_anim_frame_end
            )
        
        # agregamos el nuevo item con toda la info que nos hace falta:
        glue_strength_list.add_item(
            id_name=short_id,
            from_active_group=active_group.idname, 
            label_txt=" From: " + str(self.glue_anim_frame_initial) + " To: " + str(self.glue_anim_frame_end) + " Strength: " + str(self.glue_initial_strength) + " To: " + str(self.glue_end_strength), 
            keyframes=[self.glue_anim_frame_initial, self.glue_anim_frame_end], 
            chunks=valid_chunks,
            constraints=constraints_to_work,
        )

        return {'FINISHED'}


    def invoke(self, context, event):
        wm = context.window_manager

        # leyendo del streng del usuario:
        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab_const = rbdlab.constraints

        # sugerimos los settings:

        if rbdlab_const.glue_strength > 0:
            self.glue_initial_strength = rbdlab_const.glue_strength

        self.glue_anim_frame_initial = scn.frame_current
        self.glue_anim_frame_end = scn.frame_current +1

        return wm.invoke_props_dialog(self, width=200)


    def draw(self, context):
        layout = self.layout
    
        initial = layout.column(align=True)
        initial.prop(self, "glue_anim_frame_initial", text="Frame Start")
        initial.prop(self, "glue_initial_strength", text="Strength", expand=True)

        final = layout.column(align=True)
        final.prop(self, "glue_anim_frame_end", text="Frame End", expand=True)
        final.prop(self, "glue_end_strength", text="Strength", expand=True)
