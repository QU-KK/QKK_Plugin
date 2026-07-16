import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.functions import create_modifier


class RBDLAB_OT_Metalsoft_Add_modifier(Operator):
    bl_idname = "rbdlab.metalsoft_add_modifier"
    bl_label = "Add Modifier"
    bl_description = "Add Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    mod_type: StringProperty(default='REMESH')


    def _reorder_modifiers(self, ob):

        """ Reordenamos modificadores (Remesh, Decimate) """

        # Posicionamos los modifiers de arriba si los hubiera:
        # RBDLab_Remesh
        # RBDLab_Decimate

        modifiers = ob.modifiers

        # cada vez que se ejecute reorder_modifiers se tendra 
        # el siguiente orden de los modificadores:
        modifier_order = {
            RBDLabNaming.REMESH_ORIGNAL: 0,
            RBDLabNaming.DECIMATE_ORIGINAL: 1,
        }
        for mod_name, desired_index in modifier_order.items():
            if mod_name in modifiers:
                current_index = modifiers.find(mod_name)
                if current_index is not None and current_index != desired_index:

                    # Si no existiera algún modifier, podría intentar ir mas allá de la pila. 
                    # Si es el caso lo skipeamos:
                    print(mod_name, current_index, desired_index)
                    if desired_index < 0 or desired_index >= len(modifiers):
                        continue

                    modifiers.move(current_index, desired_index)


    def execute(self, context):

        view_layer, rbdlab = get_common_vars(context, get_view_layer=True, get_rbdlab=True)

        # Filtra los objetos seleccionados por tipo "MESH"
        selected_mesh_objects = [ob for ob in view_layer.objects.selected if ob.type == 'MESH']

        if not selected_mesh_objects:
            self.report({'WARNING'}, "No valid object were detected in your selection!!")
            return {'CANCELLED'}
        
        org_ob = selected_mesh_objects[0]

        if org_ob.rigid_body is not None:
            self.report({'WARNING'}, "Invalid object, make sure you do not use objects that already have ridigbodies!!")
            return {'CANCELLED'}

        if org_ob:

            rbdlab.current_org_ob = org_ob
            mod_names_mod_tpyes = {
                                    'REMESH': RBDLabNaming.REMESH_ORIGNAL,
                                    'DECIMATE': RBDLabNaming.DECIMATE_ORIGINAL,
                                }
            
            for ob in selected_mesh_objects:
                create_modifier(ob, mod_names_mod_tpyes[self.mod_type], self.mod_type)
                self._reorder_modifiers(ob)

        return {'FINISHED'}
