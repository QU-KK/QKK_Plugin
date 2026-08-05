from bpy.types import Operator
from ......addon.naming import RBDLabNaming
from ......Global.get_common_vars import get_common_vars
from ......Global.basics import select_object, set_active_object, deselect_all_objects
from ....common_rigidbodies_functs import update_values, my_settings_copy
from .common_methods import compute_mass

class RBDLAB_OT_update(Operator):
    bl_idname = "rbdlab.rigidbody_update"
    bl_label = "Update Rigid Bodies"
    bl_description = "Update Rigid Bodies Settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        scn, rbdlab, tcoll_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True)
        tcoll_item = tcoll_list.active_item

        if not tcoll_item:
            self.report({'WARNING'}, "No valid Target Collection!")
            return {'CANCELLED'}

        metal_list = tcoll_item.metal_list
        current_metal = metal_list.active

        if current_metal:
            metal_previous_state = current_metal.metal_or_fractures
            if 'FRACTURES' not in metal_previous_state:
                current_metal.metal_or_fractures = {'FRACTURES'}

        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)

        if not chunks:
            self.report({'WARNING'}, "No valid objects in this collection!")
            return {'CANCELLED'}
        
        rbd_props = rbdlab.physics.rigidbodies
        metal_props = tcoll_item.metal_props

        deselect_all_objects(context)

        valid_objects = [ob for ob in chunks if hasattr(ob, "rigid_body") and hasattr(ob.rigid_body, "type")]
        if valid_objects:
            for ob in valid_objects:
                select_object(context, ob)

            if context.selected_objects:

                set_active_object(context, valid_objects[0])

                update_values(valid_objects[0], rbdlab)
                my_settings_copy(context, valid_objects, rbdlab)

                # deselect_all_objects(context)

                # con el shape compound parent no permite calcular la masa:
                [
                    setattr(ob.rigid_body, "collision_shape", 'CONVEX_HULL')
                    for ob in valid_objects
                    if RBDLabNaming.NO_SHAPE_OBJ in ob.name
                ]

                set_active_object(context, valid_objects[0])

                compute_mass(rbd_props, metal_props, valid_objects)

                # bpy.ops.rigidbody.mass_calculate(material=rbd_props.avalidable_mass)

                # restauramos el shape compound:
                [
                    setattr(ob.rigid_body, "collision_shape", 'COMPOUND')
                    for ob in valid_objects
                    if RBDLabNaming.NO_SHAPE_OBJ in ob.name
                ]

            scn.frame_set(scn.frame_start)
            deselect_all_objects(context)

        if current_metal and metal_previous_state:
            current_metal.metal_or_fractures = metal_previous_state
    
        return {'FINISHED'}
