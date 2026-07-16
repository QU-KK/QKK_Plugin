import bpy
from bpy.types import Operator
from ...Global.functions import set_active_collection_to_master_coll, create_new_collection
from ...Global.basics import set_active_object, deselect_all_objects
from ...addon.naming import RBDLabNaming


class ACTIVATORS_OT_set_activators(Operator):
    bl_idname = "rbdlab.act_set"
    bl_label = "Convert in Activators objects"
    bl_description = "Set/Convert selected objects in Activators objects"
    bl_options = {'REGISTER', 'UNDO'}

    # @classmethod
    # def poll(cls, context):
    #     if len(context.selected_objects) == 0:
    #         return False
            
    #     return any([True for ob in context.selected_objects if ob.type == 'MESH' and RBDLabNaming.ACTIVATORS_OBJECTS not in ob])

    def execute(self, context):
        
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll_list = rbdlab.lists.target_coll_list
        tcoll = tcoll_list.active

        if not tcoll or not tcoll.name:
            self.report({'WARNING'}, "Not valid Target Collection!")
            return {'CANCELLED'}

        objects = [ob for ob in context.selected_objects if ob.type == 'MESH' and RBDLabNaming.FROM not in ob and RBDLabNaming.ACTIVATORS_OBJECTS not in ob]

        if not objects:
            self.report({'WARNING'}, "Not valid pre-activators objects in your selection!")
            return {'CANCELLED'}
        
        set_active_collection_to_master_coll(context)

        if RBDLabNaming.ACTIVATORS_COLL not in rbdlab.root_collection.children:
            create_new_collection(context, RBDLabNaming.ACTIVATORS_COLL)

        for ob in objects:
            # unlink from all collections the original object
            for coll in ob.users_collection:
                if coll.name != RBDLabNaming.RBD_WORLD:
                    coll.objects.unlink(ob)

            # link to the Originals collection
            coll_target = rbdlab.root_collection.children.get(RBDLabNaming.ACTIVATORS_COLL)
            coll_target.objects.link(ob)

        # les quito los rigid body:
        deselect_all_objects(context)
        for ob in objects:
            if hasattr(ob, "rigid_body"):
                if hasattr(ob.rigid_body, "type"):
                    ob.select_set(True)

        if len(context.selected_objects) > 0:
            set_active_object(context, context.selected_objects[0])
            bpy.ops.rigidbody.objects_remove()

        for ob in objects:

            ob.select_set(True)
            ob.display_type = 'WIRE'
            ob.hide_render = True

            if RBDLabNaming.ACTIVATORS_OBJECTS not in ob:
                ob[RBDLabNaming.ACTIVATORS_OBJECTS] = ob.name

            if "activator" not in ob:
                ob["activator"] = 'MESH'

            # append_attribute_to_obj(scn, RBDLabNaming.ACTIVATORS_OBJECTS, ob.name)

            if RBDLabNaming.CURRENT_MASS in ob:
                del ob[RBDLabNaming.CURRENT_MASS]

            if RBDLabNaming.RBD_WORLD in bpy.data.collections:
                if ob.name in bpy.data.collections[RBDLabNaming.RBD_WORLD]:
                    bpy.data.collections[RBDLabNaming.RBD_WORLD].objects.unlink(ob)

        return {'FINISHED'}
