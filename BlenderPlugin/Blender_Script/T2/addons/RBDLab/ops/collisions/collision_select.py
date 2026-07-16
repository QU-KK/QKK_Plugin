import bpy
from bpy.types import Operator
from bpy.props import EnumProperty


class RBDLAB_OT_collision_select(Operator):
    ''' NO SE ESTA USANDO '''

    bl_idname = "rbdlab.collision_select"
    bl_label = "Select Collision"

    type: EnumProperty(name="Collision to",
                       items=(
                            ("Low", "Low", ""),
                            ("High", "High", ""),
                       ),
                       default="Low")

    @classmethod
    def poll(cls, context):
        return context.scene.rbdlab.filtered_target_collection is not None

    @classmethod
    def description(cls, context, properties):
        return "Collision to %s" % properties.type

    def execute(self, context):
        context.scene.rbdlab.ui.set_collision_to(self.type)
        return {'FINISHED'}
