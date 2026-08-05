import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from ...addon.naming import RBDLabNaming


class ACTIVATORS_OT_parent_activators(Operator):
    bl_idname = "rbdlab.act_parent"
    bl_label = "Parent Activators"
    bl_description = "Parent Activators"
    bl_options = {'REGISTER', 'UNDO'}

    call: StringProperty(default="")

    def execute(self, context):

        # scn = context.scene
        # rbdlab = scn.rbdlab
        
        sel_obs = [ob for ob in context.selected_objects if ob.type == "MESH" and ob.visible_get() and RBDLabNaming.ACTIVATOR_OB_TO_PARENT in ob]
        if not sel_obs:
            self.report({'ERROR'}, "Invalid Selected Objects!!")
            return {'CANCELLED'}

        for ob in sel_obs:

            father = bpy.data.objects.get(ob[RBDLabNaming.ACTIVATOR_OB_TO_PARENT])

            if not father:
                continue
            
            if self.call == 'PARENT':

                # fast parent:
                father_mw = father.matrix_world.copy()
                ob.parent = father
                ob.matrix_world = father_mw
            
            elif self.call == 'DEPARENT':

                mw = ob.matrix_world.copy()
                ob.parent = None
                ob.matrix_world = mw
        
        return {'FINISHED'}
