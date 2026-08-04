import bpy
from bpy.types import Operator
from bpy.props import StringProperty
from ....addon.naming import RBDLabNaming
from ....Global.get_common_vars import get_common_vars
from ....Global.functions import create_modifier, low_level_duplicate_ob, set_active_object


class RBDLAB_OT_Prepare_Add_modifier(Operator):
    bl_idname = "rbdlab.prepare_proxy_add_modifier"
    bl_label = "Add Modifier"
    bl_description = "Add Modifier"
    bl_options = {'REGISTER', 'UNDO'}

    mod_type: StringProperty(default='REMESH')


    def _reorder_modifiers(self, ob):

        """ Reordenamos modificadores (Remesh, Decimate, Solidify) """

        # Posicionamos los modifiers de arriba si los hubiera:
        # RBDLab_Remesh
        # RBDLab_Decimate
        # RBDLab_Solidify

        modifiers = ob.modifiers

        # cada vez que se ejecute reorder_modifiers se tendra 
        # el siguiente orden de los modificadores:
        modifier_order = {
            RBDLabNaming.REMESH: 0,
            RBDLabNaming.DECIMATE: 1,
            RBDLabNaming.SOLIDIFY_MOD: 2,
        }

        for mod_name, desired_index in modifier_order.items():
            if mod_name in modifiers:
                current_index = modifiers.find(mod_name)
                if current_index is not None and current_index != desired_index:

                    # Si no existiera algún modifier, podría intentar ir mas allá de la pila. 
                    # Si es el caso lo skipeamos:
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

        if len(selected_mesh_objects) > 1:
            self.report({'WARNING'}, "You can only create one proxy at a time!!")
            return {'CANCELLED'}
        
        proxy_ob = selected_mesh_objects[0]

        if proxy_ob.rigid_body is not None:
            self.report({'WARNING'}, "Invalid object, make sure you do not use objects that already have ridigbodies!!")
            return {'CANCELLED'}

        # duplicamos los objetos y les agregamos el modifier remesh:
        
        if RBDLabNaming.OB_PROXY not in proxy_ob:
            
            new_ob = low_level_duplicate_ob(proxy_ob)
            new_ob[RBDLabNaming.OB_PROXY] = True    
            proxy_ob.hide_set(True)
            proxy_ob.hide_render = True

        else:
            new_ob = proxy_ob

        if not new_ob.name.endswith("_proxy"):
            new_ob.name = proxy_ob.name + "_proxy"

        if new_ob:

            rbdlab.current_proxy_ob = new_ob
            mod_names_mod_tpyes = {
                                    'REMESH': RBDLabNaming.REMESH,
                                    'DECIMATE': RBDLabNaming.DECIMATE,
                                    'SOLIDIFY': RBDLabNaming.SOLIDIFY_MOD,
                                }
            create_modifier(new_ob, mod_names_mod_tpyes[self.mod_type], self.mod_type)
            
            self._reorder_modifiers(new_ob)
            bpy.ops.object.select_all(action='DESELECT')
            new_ob.select_set(True)
            set_active_object(context, new_ob)

        return {'FINISHED'}
