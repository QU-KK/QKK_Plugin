import bpy
from bpy.types import Operator
from .....Global.basics import rm_ob
from .....addon.naming import RBDLabNaming


class RBDLAB_OT_physics_parents_reset_handler(Operator):
    bl_idname = "rbd.reset_handler"
    bl_label = "Reset handler"
    bl_description = "Reset Handler"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        tcoll = rbdlab.filtered_target_collection

        if tcoll is not None:
            tcoll_objs = tcoll.objects
            
            if tcoll_objs:

                valid_objects = [ob for ob in tcoll_objs if ob.type == 'MESH' and ob.visible_get()]

                # obtenemos su handler del listado de target collections:
                active_item = rbdlab.lists.target_coll_list.active_item
                handler = active_item.handler
                if handler:

                    for obj in valid_objects:
                        mw = obj.matrix_world
                        if obj.parent:
                            if obj.parent == handler:
                                obj.parent = None
                                obj.matrix_world = mw

                    rm_ob(handler)
                    bpy.ops.rbdlab.rigidbody_add_handler()
                    rbdlab.edit_handler_toggle = False
                    
                    return {'FINISHED'}
                else:
                    self.report({'WARNING'}, "No handler detected!")
                    return {'CANCELLED'}
            else:
                self.report({'WARNING'}, "No valid objects in this Target Collection!")
                return {'CANCELLED'}

        else:
            self.report({'WARNING'}, "No Target Collection!")
            return {'CANCELLED'}
