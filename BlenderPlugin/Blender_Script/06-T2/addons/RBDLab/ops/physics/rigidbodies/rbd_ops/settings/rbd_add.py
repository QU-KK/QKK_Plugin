import bpy
from bpy.types import Operator
from ......addon.naming import RBDLabNaming
from ......Global.get_common_vars import get_common_vars
from ......Global.functions import rm_ob
from ......Global.basics import enter_object_mode, select_object, set_active_object, deselect_all_objects
from ......Global.utilities import finding_home_for_orphaned_chunks
from ....common_rigidbodies_functs import update_values, my_settings_copy, save_type_of_mass_in_obj
from .common_methods import compute_mass


class RBDLAB_OT_add(Operator):
    bl_idname = "rbdlab.rigidbody_add"
    bl_label = "Add Rigid Bodies"
    bl_description = "Add Rigid Bodies to the current Target Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        scn, rbdlab, tcoll_list = get_common_vars(context, get_scn=True, get_rbdlab=True, get_tcoll_list=True)

        tcoll_item = tcoll_list.active_item
        
        if not tcoll_item:
            self.report({'WARNING'}, "Target Collection is Empty!")
            return {'CANCELLED'}
        
        tcoll = tcoll_item.coll

        chunks = tcoll_list.get_current_active_tcoll_valild_objects(context)
        rbd_props = rbdlab.physics.rigidbodies

        metal_props = tcoll_item.metal_props

        enter_object_mode(context)
        
        # si no se usa metallic o custom aprovecho para poner sus defaults:
        if not metal_props.metal_soft_mass:
            rbd_props.metal_mass = rbd_props.get_default_properties("metal_mass")
        
        if rbd_props.avalidable_mass != "Custom":
            rbd_props.custom_mass = rbd_props.get_default_properties("custom_mass")

        rbdlab.ui.show_hide_physics_rbd_settings = True

        coll_name = tcoll.name

        deselect_all_objects(context)

        tcoll['RBDLAB'] = True

        if hasattr(scn.rigidbody_world, "enabled"):
            if not scn.rigidbody_world.enabled:
                scn.rigidbody_world.enabled = True

        valid_objects = [
            ob for ob in chunks
            if RBDLabNaming.PASSIVE not in ob and RBDLabNaming.NO_SHAPE_OBJ
            not in ob]

        if len(valid_objects) <= 0:
            self.report({'WARNING'}, "No valid objects in this collection!")
            return {'CANCELLED'}

        scn.frame_set(scn.frame_start)

        for ob in valid_objects:
            select_object(context, ob)
            ob["rbdlab_active"] = True

        ob = valid_objects[0]
        set_active_object(context, ob)

        deleted_any = False

        if ob:
            if not ob.rigid_body:
                bpy.ops.rigidbody.objects_add(type='ACTIVE')

            update_values(ob, rbdlab)
            my_settings_copy(context, valid_objects, rbdlab)

            compute_mass(rbd_props, metal_props, valid_objects)

            # Auto clean de objetos con masa 0 ########################
            if rbd_props.rm_chunks_with_low_mass:
                
                deselect_all_objects(context)
                
                low_mass = 0.000009
                # low_mass = 0.000002
                for ob in valid_objects:

                    if ob.rigid_body is None:
                        continue

                    if hasattr(ob.rigid_body, "mass"):

                        save_type_of_mass_in_obj(rbdlab, ob)
                        mass = ob.rigid_body.mass

                        if mass <= low_mass:
                            rm_ob(ob)
                            deleted_any = True

            # End auto clean ##########################################

            if deleted_any:
                coll_low = None
                coll_high = None

                if RBDLabNaming.SUFIX_LOW in coll_name:
                    coll_high_name = coll_name.replace(RBDLabNaming.SUFIX_LOW, RBDLabNaming.SUFIX_HIGH)
                else:
                    coll_high_name = coll_name + RBDLabNaming.SUFIX_HIGH

                coll_low = bpy.data.collections.get(coll_name)
                coll_high = bpy.data.collections.get(coll_high_name)

                if coll_low and coll_high:
                    finding_home_for_orphaned_chunks(context, coll_low, coll_high)

            tcoll[RBDLabNaming.COLL_WITH_RBD] = RBDLabNaming.COLL_WITH_RBD

            # seteo el tab de create de constraints
            rbdlab.ui.active_const_tab = 'CREATE'

            deselect_all_objects(context)
            return {'FINISHED'}
