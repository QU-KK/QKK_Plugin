import bpy

from bpy.types import Operator
from ....Global.functions import (
    set_active_collection_to_master_coll
)
from ....Global.basics import deselect_all_objects
from ....addon.paths import RBDLabPreferences
from ....addon.naming import RBDLabNaming


class GROUND_OT_add(Operator):
    bl_idname = "rbdlab.add_ground"
    bl_label = "Add ground"
    bl_description = "Add one basic floor"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scn = context.scene
        rbdlab = scn.rbdlab

        addon_preferences = RBDLabPreferences.get_prefs(context)

        if RBDLabNaming.GROUND not in bpy.context.scene.objects:
            size_and_offset = 0.25
            set_active_collection_to_master_coll(context)
            bpy.ops.mesh.primitive_cube_add(enter_editmode=False, align='WORLD',
                                            location=(0, 0, -size_and_offset), scale=(30, 30, size_and_offset))

            ground = bpy.context.object
            ground.name = RBDLabNaming.GROUND
            ground[RBDLabNaming.GROUND] = True

            bpy.ops.rigidbody.object_add()
            ground.rigid_body.type = 'PASSIVE'
            bpy.ops.object.modifier_add(type='COLLISION')
            ground.collision.damping_factor = 1
            ground.collision.friction_factor = 0.8
            ground.collision.damping_random = 0.1
            ground.rigid_body.friction = 0.7

            ground.color = list(addon_preferences.col_ground)

            if addon_preferences.ground_in_wiremode:
                ground.display_type = 'WIRE'

        deselect_all_objects(context)
        # rbdlab.ui.physics_switch_subsections = 'RBD'

        return {'FINISHED'}
