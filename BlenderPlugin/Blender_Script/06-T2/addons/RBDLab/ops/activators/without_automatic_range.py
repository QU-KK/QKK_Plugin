from bpy.types import Operator


class ACTIVATORS_OT_transfer_substeps(Operator):
    bl_idname = "rbdlab.transfer_substeps"
    bl_label = "Transfer Substeps"
    bl_description = "Transfer RigidBodyWorld Substeps to Activators ui substeps"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        rbw = scn.rigidbody_world
        if rbw:
            rbdlab.activators.rbdw_substeps_per_frame = rbw.substeps_per_frame
        return {'FINISHED'}


class ACTIVATORS_OT_transfer_total_frames_from_sim(Operator):
    bl_idname = "rbdlab.passive_total_frames_from_sim"
    bl_label = "Set Total Frames"
    bl_description = "Determine Total Frames from RBD Simulation Start-End"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        rbw = scn.rigidbody_world
        if rbw:
            pc = rbw.point_cache
            rbdlab.activators.total_frames = pc.frame_end-pc.frame_start+1

        return {'FINISHED'}
