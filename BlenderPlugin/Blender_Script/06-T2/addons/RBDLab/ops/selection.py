import bpy
from typing import List
from collections import defaultdict
from bpy.types import Operator, Object
from ..Global.basics import select_object, deselect_all_objects, set_active_object
from ..addon.naming import RBDLabNaming
from ..Global.functions import get_high_collection_objects


class SELECT_OT_piece(Operator):
    bl_idname = "rbdlab.selectpiece"
    bl_label = "Select Piece"
    bl_description = "Select all the chunks belonging to the same piece"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        if bpy.context.active_object.type == 'MESH':
            first_obj = context.active_object
            father = first_obj[RBDLabNaming.FROM]
            if father:
                deselect_all_objects(context)
                for obj in context.scene.objects:
                    if obj.type == 'MESH' and obj.visible_get():
                        if RBDLabNaming.FROM in obj and obj[RBDLabNaming.FROM] == father:
                            select_object(context, obj)

        return {'FINISHED'}


class SELECT_OT_by_color(Operator):
    bl_idname = "rbdlab.selecbycolor"
    bl_label = "Select By Color"
    bl_description = "Select chunks of the same color as the currently selected chunk ( in this current Target Collection )"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        # este operador funciona segun el target collection q tengas activo.

        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if tcoll:

            # recopilamos los objetos de low y de high:
            high_objects = get_high_collection_objects(tcoll)

            # Convierte ambas listas en conjuntos para eliminar duplicados
            conjunto1 = set(tcoll.objects[:])
            conjunto2 = set(high_objects)

            # Agrega el conjunto2 al conjunto1
            conjunto1.update(conjunto2)

            # Convierte el conjunto1 de nuevo a una lista si lo deseas
            all_objects = list(conjunto1)

            chunks = [ob for ob in all_objects if ob.type == 'MESH' and ob.visible_get() and ob.name in context.view_layer.objects]
            
            ob_by_color: dict[str, List[Object]] = defaultdict(list)
                    
            for ob in chunks:
                color = ob.color[:]
                if color:
                    ob_by_color[color].append(ob)
            
            for selected_ob in context.selected_objects:
                for value in ob_by_color.values():
                    if selected_ob in value:
                        for ob in value:
                            ob.select_set(True)

        return {'FINISHED'}


class SELECT_OT_chunks_without_movement(Operator):
    bl_idname = "rbdlab.chunks_without_movement"
    bl_label = "Select Chunks"
    bl_description = "Select Chunks without movement"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        frame_current = context.scene.frame_current
        motion_threshold = rbdlab.motion_threshold

        if rbdlab.filtered_target_collection:
            all_rbd_chunks = [obj for obj in rbdlab.filtered_target_collection.objects
                              if obj.type == 'MESH' and obj.rigid_body is not None]

            if all_rbd_chunks:

                # obteniendo los tipos:
                all_passive_chunks = [obj for obj in all_rbd_chunks if obj.rigid_body.type == 'PASSIVE']

                all_kinematics = [obj for obj in all_rbd_chunks
                                  if obj.rigid_body.type == 'ACTIVE'
                                  and obj.rigid_body.kinematic]

                all_kinematic_chunks = [obj for obj in all_kinematics if obj.animation_data is None]

                all_kinematic_with_data_anim = [obj for obj in all_kinematics if obj.animation_data is not None]
                all_kinematic_with_data_anim_without_keyframes = [
                    obj for obj in all_kinematic_with_data_anim if obj.animation_data.action is None]

                if all_passive_chunks:
                    for passive in all_passive_chunks:
                        select_object(context, passive)

                if all_kinematic_chunks:
                    for kinematic in all_kinematic_chunks:
                        select_object(context, kinematic)

                if all_kinematic_with_data_anim_without_keyframes:
                    for kinematic in all_kinematic_with_data_anim_without_keyframes:
                        select_object(context, kinematic)

                all_active_chunks = [obj for obj in all_rbd_chunks
                                     if obj.rigid_body.type == 'ACTIVE'
                                     and not obj.rigid_body.kinematic and RBDLabNaming.NO_SHAPE_OBJ not in obj]

                if all_active_chunks:

                    depsgraph = context.evaluated_depsgraph_get()
                    all_active_chunks_evaluated = [obj.evaluated_get(depsgraph) for obj in all_active_chunks]

                    chunks_in_movement = []
                    current_locations = []

                    for f in range(scn.frame_start, scn.frame_end):
                        context.scene.frame_set(f)
                        previous_locations = current_locations.copy()
                        current_locations = [obj.matrix_world.translation.copy() for obj in all_active_chunks_evaluated]

                        for i, obj in enumerate(all_active_chunks_evaluated):
                            if len(previous_locations) > i:
                                velocity = round((current_locations[i] - previous_locations[i]).length, 4)
                                # print("frame", f, obj.name, velocity, "velocity > 0.02:", velocity < 0.02)
                                if velocity > motion_threshold:
                                    if obj.name not in chunks_in_movement:
                                        chunks_in_movement.append(obj.name)

                    # print("chunks_in_movement", chunks_in_movement)
                    for chunk in all_active_chunks:
                        # print(chunk.name, chunk.name not in chunks_in_movement)
                        if chunk.name not in chunks_in_movement:
                            select_object(context, chunk)

            all_chunks_no_rbd = [obj for obj in rbdlab.filtered_target_collection.objects
                                 if obj.type == 'MESH' and obj.rigid_body is None and obj.animation_data is None and
                                 RBDLabNaming.INNER_EMISOR not in obj]

            for obj in all_chunks_no_rbd:
                select_object(context, obj)

            if context.selected_objects:
                set_active_object(context, context.selected_objects[-1])

            context.scene.frame_current = frame_current

            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Not valid Target Collection!")
            return {'CANCELLED'}


class SELECT_OT_compounds(Operator):

    bl_idname = "rbdlab.select_compounds"
    bl_label = "Select Compounds"
    bl_description = "Select Compounds"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if rbdlab.filtered_target_collection:

            valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                             if obj.type == 'MESH' and RBDLabNaming.NO_SHAPE_OBJ in obj]

            if valid_objects:

                for obj in valid_objects:
                    obj.select_set(True)

                return {'FINISHED'}

            else:
                self.report({'WARNING'}, "Not valid Objects!")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "Not valid Target Collection!")
            return {'CANCELLED'}
