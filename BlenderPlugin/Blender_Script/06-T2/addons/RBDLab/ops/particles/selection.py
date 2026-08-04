import bpy
from bpy.types import Operator
from bpy.props import EnumProperty


class RBDLAB_OT_particles_select(Operator):
    bl_idname = "rbdlab.particles_select"
    bl_label = "Select Particle"

    type: EnumProperty(name="Particle type",
                       items=(
                            ("debris", "Debris", ""),
                            ("dust", "Dust", ""),
                            ("smoke", "Smoke", "")
                       ),
                       default="debris")

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, context, properties):
        return "Select %s particles" % properties.type

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab
        rbdlab.ui.select_particle(self.type)
        return {'FINISHED'}
