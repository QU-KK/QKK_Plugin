from bpy.types import Operator


class RBDLAB_OT_const_init_work_group(Operator):
    bl_idname = "rbdlab.const_init_work_group"
    bl_label = "Load Collections"
    bl_description = "Load Collection List"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab_const = scn.rbdlab.constraints
        rbdlab_const.init_coll_list(context)
        return {'FINISHED'}
