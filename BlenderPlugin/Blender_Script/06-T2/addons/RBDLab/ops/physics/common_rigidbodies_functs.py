import bpy
from ...addon.naming import RBDLabNaming
from bpy.types import Object


def save_type_of_mass_in_obj(rbdlab, ob):

    if isinstance(ob, Object):
        rbd_props = rbdlab.physics.rigidbodies

        ob[RBDLabNaming.CURRENT_MASS] = rbd_props.avalidable_mass
        if rbd_props.avalidable_mass == 'Custom':
            if RBDLabNaming.METAL_MASS in ob:
                del ob[RBDLabNaming.METAL_MASS]

            ob[RBDLabNaming.CUSTOM_MASS] = rbd_props.custom_mass

        elif rbd_props.avalidable_mass == 'Metallic':
            
            if RBDLabNaming.CUSTOM_MASS in ob:
                del ob[RBDLabNaming.CUSTOM_MASS]

            ob[RBDLabNaming.METAL_MASS] = rbd_props.metal_mass
        
        else:

            if RBDLabNaming.CUSTOM_MASS in ob:
                del ob[RBDLabNaming.CUSTOM_MASS]
            
            if RBDLabNaming.METAL_MASS in ob:
                del ob[RBDLabNaming.METAL_MASS]



def my_settings_copy(context, valid_objects, rbdlab):
    # con chuleta por si otro dia necesito mas:
    attrs = (
        "type",
        "kinematic",
        "mass",
        "collision_shape",
        "use_margin",
        "collision_margin",
        "friction",
        "restitution",
        "use_deactivation",
        "use_start_deactivated",
        "deactivate_linear_velocity",
        "deactivate_angular_velocity",
        "linear_damping",
        "angular_damping",
        # "collision_collections",
        # "mesh_source",
        # "use_deform",
        # "enabled", # <- Respetamos el Enabled que tuviera.
    )

    if valid_objects:
        rb_from = context.object.rigid_body

        ac_layers_list = rbdlab.lists.ac_layers_list 
        all_types = ac_layers_list.get_all_types

        for ob in valid_objects:
            save_type_of_mass_in_obj(rbdlab, ob)
            current_active = context.active_object
            rb_to = ob.rigid_body

            if ob == current_active:
                continue

            if RBDLabNaming.RBD_SEL_KINEMATIC not in ob:
                if rbdlab.physics.rigidbodies.kinematic:
                    ob[RBDLabNaming.RBD_KINEMATIC] = True
                else:
                    if RBDLabNaming.RBD_KINEMATIC in ob:
                        del ob[RBDLabNaming.RBD_KINEMATIC]

            if rb_to and rb_from:

                for attr in attrs:

                    # Solo actualizo Deactivation si el objeto no forma parte de un activator de tipo Dynamic:
                    if attr == "use_deactivation":
                        # Sólo hacemos la comprobación si hay algún activator de tipo Dynamic:
                        if 'DYNAMIC' in all_types:
                            # Si hay activators de tipo dynamic, compruebo si mi objeto esta en alguno de ellos (computable o no):
                            already_with_dynamic = ac_layers_list.check_if_ob_in_any_item_by_type(ob, 'DYNAMIC')
                            # Si forma parte de alguno, no lo actualizamos:
                            if already_with_dynamic:
                                continue
                    
                    if attr == "type":

                        if RBDLabNaming.PASSIVE not in ob:
                            setattr(rb_to, attr, 'ACTIVE')

                    elif attr == "kinematic":
                        if RBDLabNaming.RBD_SEL_KINEMATIC not in ob:
                            setattr(rb_to, attr, getattr(rb_from, attr))

                    elif attr == "collision_shape":
                        if RBDLabNaming.NO_SHAPE_OBJ not in ob and RBDLabNaming.JOINED not in ob:
                            setattr(rb_to, attr, getattr(rb_from, attr))
                    else:
                        # print(obj.name, rb_to, attr, rb_from, attr)
                        setattr(rb_to, attr, getattr(rb_from, attr))


def remove_fcurves_keyframes(obj, path_name):
    if obj:
        ad = obj.animation_data
        if hasattr(ad, "action"):
            action = ad.action
            if hasattr(action, "fcurves"):
                for fc in action.fcurves:
                    if fc.data_path == path_name:
                        action.fcurves.remove(fc)


def update_values(ob, rbdlab):
    rbd_props = rbdlab.physics.rigidbodies
    ac_layers_list = rbdlab.lists.ac_layers_list 
    all_types = ac_layers_list.get_all_types

    if RBDLabNaming.PASSIVE not in ob:
        ob.rigid_body.type = 'ACTIVE'

    if RBDLabNaming.RBD_SEL_KINEMATIC not in ob:
        ob.rigid_body.kinematic = rbd_props.kinematic

        if rbd_props.kinematic:
            ob[RBDLabNaming.RBD_KINEMATIC] = True
        else:
            if RBDLabNaming.RBD_KINEMATIC in ob:
                del ob[RBDLabNaming.RBD_KINEMATIC]

    # Respetamos el enabled que tuviera:
    # ob.rigid_body.enabled = rbd_props.dynamic

    if 'DYNAMIC' not in all_types:
        # si no hay Activators de tipo DYNAMIC se actualiza como siempre:
        ob.rigid_body.use_deactivation = rbd_props.deactivation
    
    else:

        # Si hay activators de dinamic compruebo si mi objeto esta en alguno de ellos:
        already_with_dynamic = ac_layers_list.check_if_ob_in_any_item_by_type(ob, 'DYNAMIC')
        # Si no forma parte de ninguno lo actualizo con normalidad:
        if not already_with_dynamic:
            ob.rigid_body.use_deactivation = rbd_props.deactivation

    ob.rigid_body.deactivate_linear_velocity = rbd_props.deactivate_linear_velocity
    ob.rigid_body.deactivate_angular_velocity = rbd_props.deactivate_angular_velocity
    ob.rigid_body.use_start_deactivated = rbd_props.use_start_deactivated
    ob.rigid_body.linear_damping = rbd_props.d_translation
    ob.rigid_body.angular_damping = rbd_props.d_rotation
    ob.rigid_body.friction = rbd_props.rb_friction
    ob.rigid_body.restitution = rbd_props.restitution

    # si es de tipo shape compound parent no se lo cambiamos:
    if RBDLabNaming.NO_SHAPE_OBJ not in ob and RBDLabNaming.JOINED not in ob:
        ob.rigid_body.collision_shape = rbd_props.collision_shape
        # obj.rigid_body.collision_shape = rbd_props.collision_shape_combobox

    ob.rigid_body.use_margin = rbd_props.use_collision_margin
    ob.rigid_body.collision_margin = rbd_props.collision_margin

    # si es de masa RBDLab Metalic:
    if rbd_props.avalidable_mass == "Metallic":
        ob.rigid_body.mass = rbd_props.metal_mass
