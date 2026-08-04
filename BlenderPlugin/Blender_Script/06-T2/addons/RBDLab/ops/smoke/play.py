import bpy
from bpy.types import Operator
from ...addon.naming import RBDLabNaming


class SMOKE_OT_play(Operator):
    bl_idname = "rbdlab.smoke_play"
    bl_label = "Play/Stop"
    bl_description = "Play/Stop Smoke"
    bl_options = {'PRESET'}
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        if scn.frame_current != scn.frame_start:
            scn.frame_current = scn.frame_start

        if not rbdlab.smoke.toggle_play:
            # fuerzo a que recompute la cache:
            domain = [obj for obj in bpy.data.objects if obj.name.endswith(RBDLabNaming.SUFIX_DOMAIN)]
            if domain:
                domain = domain[0]
                domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max = domain.modifiers[RBDLabNaming.SMOKE_MOD].domain_settings.resolution_max

            bpy.ops.screen.animation_play()
            rbdlab.smoke.toggle_play = True
        else:
            bpy.ops.screen.animation_cancel()
            rbdlab.smoke.toggle_play = False

        return {'FINISHED'}
