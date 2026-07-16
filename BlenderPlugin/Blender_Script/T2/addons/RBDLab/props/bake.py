from bpy.types import PropertyGroup
from bpy.props import BoolProperty, FloatProperty, StringProperty, IntProperty


class RBDLab_PG_Bake(PropertyGroup):
    # Bake to keyframes (por ahora estoy compartiendo todas menos steps con bake action)
    bk_to_kf_by_selection: BoolProperty(
        default=False
    )
    bk_to_kf_start: IntProperty(
        default=1,
        min=0
    )
    bk_to_kf_end: IntProperty(
        default=250,
        min=1
    )
    bk_to_kf_steps: IntProperty(
        default=1,
        min=1,
        max=120
    )
    ###########################################################################
    # for bake action (visual keying):
    ###########################################################################
    bake_action_by_selection: BoolProperty(
        default=False
    )
    bake_action_start: IntProperty(
        default=1,
        min=0
    )
    bake_action_end: IntProperty(
        default=250,
        min=1
    )
    frame_step: IntProperty(
        min=1,
        max=120,
        default=1
    )
    ###########################################################################
    sync_frame_end: BoolProperty(
        name="Sync End Frames",
        description="Symc multiple End Frames Settings",
        default=True
    )

    def frame_end_update(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        rbw = scn.rigidbody_world
        rbw.point_cache.frame_end = self.frame_end

        if self.sync_frame_end:
            scn.frame_end = self.frame_end
            rbdlab.particles.debris.range_out = self.frame_end
            rbdlab.particles.dust.range_out = self.frame_end
            rbdlab.particles.smoke.range_out = self.frame_end
            rbdlab.bake.bake_action_end = self.frame_end
            rbdlab.bake.bk_to_kf_end = self.frame_end

    frame_end: IntProperty(
        name="Frame End",
        default=250,
        update=frame_end_update
    )
