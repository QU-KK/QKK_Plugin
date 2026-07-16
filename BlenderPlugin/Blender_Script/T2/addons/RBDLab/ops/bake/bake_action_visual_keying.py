import bpy
from bpy.types import Operator
from ...Global.basics import enter_object_mode, select_object, set_active_object, deselect_all_objects
from ...addon.naming import RBDLabNaming


class BAKE_OT_action_visual_keying(Operator):
    bl_idname = "rbdlab.bake_action_visual_keying"
    bl_label = "Bake Action (Visual Keying)"
    bl_description = "To add keyframes to your objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        valid_objects = None
        passives_objects = None

        if rbdlab.bake.bake_action_by_selection:
            valid_objects = [obj for obj in context.selected_objects if obj.type ==
                             'MESH' and obj.visible_get() and RBDLabNaming.PASSIVE not in obj]
        else:
            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                     if obj.type == 'MESH' and obj.visible_get() and RBDLabNaming.PASSIVE not in obj]

        if not valid_objects:
            self.report({'WARNING'}, "Not valid objects!")
            return {'CANCELLED'}

        # passives_objects = [obj for obj in valid_objects if RBDLabNaming.PASSIVE in obj]

        enter_object_mode(context)

        fstart = rbdlab.bake.bake_action_start
        fend = rbdlab.bake.bake_action_end
        steps = rbdlab.bake.frame_step

        deselect_all_objects(context)
        for obj in valid_objects:

            obj[RBDLabNaming.BAKED_ACTION] = True

            if obj.rigid_body is None:
                continue
            if RBDLabNaming.GROUND == obj.name:
                continue
            if RBDLabNaming.SUFIX_BBOX in obj.name:
                continue

            if RBDLabNaming.CHUNK_EXTRACTED not in obj:
                color = obj.color_stack.get_first_color()
                if color:
                    obj.color = color

            select_object(context, obj)

        if context.scene.frame_current != context.scene.frame_start:
            context.scene.frame_current = context.scene.frame_start

        if len(context.selected_objects) > 0:
            bpy.ops.nla.bake(
                frame_start=fstart,
                frame_end=fend,
                step=steps,
                only_selected=True,
                visual_keying=True,
                clear_constraints=False,
                clear_parents=False,
                use_current_action=False,
                clean_curves=False,
                bake_types={'OBJECT'}
            )
            # para impedir el Dependency cycle detected:
            set_active_object(context, context.selected_objects[0])
            bpy.ops.rigidbody.objects_remove()

        # remove rigidbodies to passives:
        # deselect_all_objects(context)
        # if passives_objects:
        #     for obj in passives_objects:
        #         if not obj.rigid_body:
        #             continue
        #         if RBDLabNaming.GROUND == obj.name:
        #             continue
        #         if RBDLabNaming.SUFIX_BBOX in obj.name:
        #             continue

        #         select_object(context, obj)
        #         color = obj.color_stack.get_first_color()
        #         if color:
        #             obj.color = color

        #     if len(context.selected_objects) > 0:
        #         set_active_object(context, context.selected_objects[0])
        #         bpy.ops.rigidbody.objects_remove()

        # deselect_all_objects(context)
        return {'FINISHED'}


class BAKE_OT_remove_bake_action(Operator):
    bl_idname = "rbdlab.bake_remove_bake_action"
    bl_label = "Remove Bake Action"
    bl_description = "Remove keyframes to your objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab
        valid_objects = None

        if rbdlab.bake.bake_action_by_selection:
            valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]
        else:
            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    valid_objects = [obj for obj in rbdlab.filtered_target_collection.objects
                                     if obj.type == 'MESH' and obj.visible_get()]

        if valid_objects:

            if context.scene.frame_current != context.scene.frame_start:
                context.scene.frame_set(context.scene.frame_start)

            actions_to_remove = []

            for obj in valid_objects:

                if obj.animation_data is None:
                    continue

                if obj.animation_data.action is None:
                    continue

                action_to_remove = obj.animation_data.action
                if action_to_remove not in actions_to_remove:
                    actions_to_remove.extend(actions_to_remove)

                if RBDLabNaming.BAKED_ACTION in obj:
                    del obj[RBDLabNaming.BAKED_ACTION]

                if RBDLabNaming.ACTIVE_ACTION in obj:
                    previous_action = obj[RBDLabNaming.ACTIVE_ACTION]

                    if previous_action:
                        if previous_action.name in bpy.data.actions:
                            obj.animation_data.action = previous_action
                    else:
                        # si no tenia action le dejo sin action:
                        obj.animation_data.action = None

                    del obj[RBDLabNaming.ACTIVE_ACTION]

            if len(actions_to_remove) > 0:
                for action in actions_to_remove:
                    bpy.data.actions.remove(action, do_unlink=True)

            if RBDLabNaming.BAKED_ACTION in rbdlab.filtered_target_collection:
                del rbdlab.filtered_target_collection[RBDLabNaming.BAKED_ACTION]

        deselect_all_objects(context)

        if context.scene.frame_current != context.scene.frame_start:
            context.scene.frame_set(context.scene.frame_start)

        return {'FINISHED'}
