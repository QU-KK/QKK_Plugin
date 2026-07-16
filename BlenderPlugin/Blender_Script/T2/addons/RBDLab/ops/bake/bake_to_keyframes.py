import bpy
from bpy.types import Operator
from ...Global.basics import enter_object_mode, select_object, set_active_object, deselect_all_objects
from ...addon.naming import RBDLabNaming


class BAKE_OT_TO_KEYFRAMES(Operator):
    bl_idname = "rbdlab.bake_tokeyframes"
    bl_label = "Bake to Keyframes"
    bl_description = "To convert your simulation to objects with keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rbdlab = context.scene.rbdlab

        valid_objects = None
        passives_objects = None

        if rbdlab.bake.bk_to_kf_by_selection:
            valid_objects = [obj for obj in context.selected_objects if obj.type == 'MESH' and obj.visible_get()]
        else:
            if rbdlab.filtered_target_collection:
                coll_name = rbdlab.filtered_target_collection.name
                if coll_name:
                    valid_objects = [obj for obj in bpy.data.collections[coll_name].objects
                                     if obj.type == 'MESH' and obj.visible_get()]

        if not valid_objects:
            self.report({'WARNING'}, "Not valid objects!")
            return {'CANCELLED'}

        passives_objects = [obj for obj in valid_objects if RBDLabNaming.PASSIVE in obj]

        enter_object_mode(context)
        fstart = rbdlab.bake.bk_to_kf_start
        fend = rbdlab.bake.bk_to_kf_end
        steps = rbdlab.bake.bk_to_kf_steps

        properties_to_rm = [
            "rbdlab_rbd_kinematic", "rbdlab_active", RBDLabNaming.ACETONABLE, RBDLabNaming.CURRENT_MASS, RBDLabNaming.PASSIVE,
            RBDLabNaming.RBD_SEL_KINEMATIC, RBDLabNaming.ACTIVATORS_EXPLODED_DEST, RBDLabNaming.ACTIVATORS_INITIAL_EXPLODE,
            "rbdlab_acetonized_kineatic", "rbdlab_acetonized_with_explode_force"]

        deselect_all_objects(context)
        for ob in valid_objects:

            ob[RBDLabNaming.BAKED_TO_KFRAMES] = True

            if not ob.rigid_body:
                continue
            if RBDLabNaming.GROUND == ob.name:
                continue
            if RBDLabNaming.SUFIX_BBOX in ob.name:
                continue
            if RBDLabNaming.PASSIVE in ob:
                continue

            if RBDLabNaming.CHUNK_EXTRACTED not in ob:
                color = ob.color_stack.get_first_color()
                if color:
                    ob.color = color

            for prop in properties_to_rm:
                if prop in ob:
                    del ob[prop]

            # les desactivamos el constraints child of si los tuviera:
            for conts in ob.constraints:
                if conts.type == 'CHILD_OF':
                    conts.enabled = False
            
            select_object(context, ob)

        if len(context.selected_objects) > 0:
            # print(context.selected_objects)
            # para q bake to keyframes no diga context incorrect necesita active
            set_active_object(context, context.selected_objects[0])
            # clear_custom_attribute_to_obj(obj, RBDLabNaming.CONSTRAINTS)
            bpy.ops.rigidbody.bake_to_keyframes(frame_start=fstart, frame_end=fend, step=steps)
            # bpy.ops.ptcache.bake_all(bake=True) # rbd
            bpy.ops.ptcache.free_bake_all()  # particles

        # remove constraints collection:
        # coll_constraints_name = coll_name + "_GlueConstraints"
        # if coll_constraints_name in bpy.data.collections:
        #     remove_collection_by_name(context, coll_constraints_name, True)

        # remove rigidbodies to passives:
        deselect_all_objects(context)
        if passives_objects:
            for obj in passives_objects:
                if not obj.rigid_body:
                    continue
                if RBDLabNaming.GROUND == obj.name:
                    continue
                if RBDLabNaming.SUFIX_BBOX in obj.name:
                    continue

                select_object(context, obj)
                color = obj.color_stack.get_first_color()
                if color:
                    obj.color = color

            if len(context.selected_objects) > 0:
                set_active_object(context, context.selected_objects[0])
                bpy.ops.rigidbody.objects_remove()

        deselect_all_objects(context)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="You will lose the options of your Rigid Bodies.")
        col.label(text="Do you wish to continue?")
