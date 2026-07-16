from typing import List
import bpy
from bpy.types import Operator, Object
import random
from .base import BaseConstraintOperator

# def update_values(context, constraints_coll_name):
    
#     """ PARECE QUE ESTO NO SE ESTA USANDO """
    
#     rbdlab = context.scene.rbdlab

#     for obj in bpy.data.collections[constraints_coll_name].objects:
#         if not obj.rigid_body_constraint:
#             continue
#         # override_iterations
#         obj.rigid_body_constraint.use_override_solver_iterations = rbdlab.constraints.override_iterations
#         obj.rigid_body_constraint.solver_iterations = rbdlab.constraints.iterations
#         # breakeable
#         obj.rigid_body_constraint.use_breaking = rbdlab.constraints.breakable
#         obj.rigid_body_constraint.breaking_threshold = rbdlab.constraints.glue_strength

#         if rbdlab.constraints.breakable:
#             obj.rigid_body_constraint.disable_collisions = False

#         obj.rigid_body_constraint.type = rbdlab.constraints.constraint_type


class CONSTRAINTS_OT_update(Operator, BaseConstraintOperator):
    bl_idname = "rbdlab.const_update"
    bl_label = "Constraints Update"
    bl_description = "Update Constraints Settigns"
    bl_options = {'REGISTER', 'UNDO'}

    def action(self, context, rbdlab_const, group, collection, chunks: List[Object], const_objects: List[Object]):
        rbdlab = context.scene.rbdlab

        # print("Update:", const_objects)

        for const_ob in const_objects:
            rbd_const = const_ob.rigid_body_constraint
            # override_iterations
            rbd_const.use_override_solver_iterations = rbdlab.constraints.override_iterations
            rbd_const.solver_iterations = rbdlab.constraints.iterations
            # breakeable
            rbd_const.use_breaking = rbdlab.constraints.breakable

            if not rbdlab.constraints.glue_strength_mode:

                if "rbdlab_use_glue_strength_random" in const_ob:
                    del const_ob["rbdlab_use_glue_strength_random"]
                
                if "rbdlab_glue_strength_random_from" in const_ob:
                    del const_ob["rbdlab_glue_strength_random_from"]
                
                if "rbdlab_glue_strength_random_to" in const_ob:
                    del const_ob["rbdlab_glue_strength_random_to"]

                rbd_const.breaking_threshold = rbdlab.constraints.glue_strength
                
                # [On Update] Guardo el glue strength en el active_group:
                group.glue_strength = rbdlab.constraints.glue_strength

            else:
                const_ob["rbdlab_use_glue_strength_random"] = True
                const_ob["rbdlab_glue_strength_random_from"] = rbdlab.constraints.glue_strength_range[0]
                const_ob["rbdlab_glue_strength_random_to"] = rbdlab.constraints.glue_strength_range[1]
                strength_range = rbdlab.constraints.glue_strength_range
                rbd_const.breaking_threshold = random.uniform(*strength_range)

            if rbdlab.constraints.breakable:
                rbd_const.disable_collisions = False

            rbd_const.type = rbdlab.constraints.constraint_type

            # Spring constrinats (plasticidad):
            if rbdlab.constraints.constraint_type == 'GENERIC_SPRING':
    
                rbd_const.spring_type = group.spring_type

                # use axis
                rbd_const.use_limit_ang_x = group.use_limit_ang_x
                rbd_const.use_limit_ang_y = group.use_limit_ang_y
                rbd_const.use_limit_ang_z = group.use_limit_ang_z
                    
                if group.limit_ang_lowers_uniq:
                    rbd_const.limit_ang_x_lower = group.limit_ang_x_lower
                    rbd_const.limit_ang_y_lower = group.limit_ang_y_lower
                    rbd_const.limit_ang_z_lower = group.limit_ang_z_lower
                else:
                    rbd_const.limit_ang_x_lower = group.limit_ang_lower_uniq
                    rbd_const.limit_ang_y_lower = group.limit_ang_lower_uniq
                    rbd_const.limit_ang_z_lower = group.limit_ang_lower_uniq

                if group.limit_ang_uppers_uniq:
                    rbd_const.limit_ang_x_upper = group.limit_ang_x_upper
                    rbd_const.limit_ang_y_upper = group.limit_ang_y_upper
                    rbd_const.limit_ang_z_upper = group.limit_ang_z_upper
                else:
                    rbd_const.limit_ang_x_upper = group.limit_ang_upper_uniq
                    rbd_const.limit_ang_y_upper = group.limit_ang_upper_uniq
                    rbd_const.limit_ang_z_upper = group.limit_ang_upper_uniq

                
                # use axis
                rbd_const.use_limit_lin_x = group.use_limit_lin_x
                rbd_const.use_limit_lin_y = group.use_limit_lin_y
                rbd_const.use_limit_lin_z = group.use_limit_lin_z
                
                if group.limit_lin_lowers_uniq:
                    rbd_const.limit_lin_x_lower = group.limit_lin_x_lower
                    rbd_const.limit_lin_y_lower = group.limit_lin_y_lower
                    rbd_const.limit_lin_z_lower = group.limit_lin_z_lower
                else:
                    rbd_const.limit_lin_x_lower = group.limit_lin_lower_uniq
                    rbd_const.limit_lin_y_lower = group.limit_lin_lower_uniq
                    rbd_const.limit_lin_z_lower = group.limit_lin_lower_uniq

                if group.limit_lin_x_uppers_uniq:
                    rbd_const.limit_lin_x_upper = group.limit_lin_x_upper
                    rbd_const.limit_lin_y_upper = group.limit_lin_y_upper
                    rbd_const.limit_lin_z_upper = group.limit_lin_z_upper
                else:
                    rbd_const.limit_lin_x_upper = group.limit_lin_upper_uniq
                    rbd_const.limit_lin_y_upper = group.limit_lin_upper_uniq
                    rbd_const.limit_lin_z_upper = group.limit_lin_upper_uniq
                
                # use axis
                rbd_const.use_spring_ang_x = group.use_spring_ang_x 
                rbd_const.use_spring_ang_y = group.use_spring_ang_y
                rbd_const.use_spring_ang_z = group.use_spring_ang_z

                if group.springs_stiffness_ang_uniq:
                    rbd_const.spring_stiffness_ang_x = group.spring_stiffness_ang_x
                    rbd_const.spring_stiffness_ang_y = group.spring_stiffness_ang_y
                    rbd_const.spring_stiffness_ang_z = group.spring_stiffness_ang_z
                else:
                    rbd_const.spring_stiffness_ang_x = group.spring_stiffness_ang_uniq
                    rbd_const.spring_stiffness_ang_y = group.spring_stiffness_ang_uniq
                    rbd_const.spring_stiffness_ang_z = group.spring_stiffness_ang_uniq

                if group.springs_damping_ang_uniq:
                    rbd_const.spring_damping_ang_x = group.spring_damping_ang_x
                    rbd_const.spring_damping_ang_y = group.spring_damping_ang_y
                    rbd_const.spring_damping_ang_z = group.spring_damping_ang_z
                else:
                    rbd_const.spring_damping_ang_x = group.spring_damping_ang_uniq
                    rbd_const.spring_damping_ang_y = group.spring_damping_ang_uniq
                    rbd_const.spring_damping_ang_z = group.spring_damping_ang_uniq

                # use axis
                rbd_const.use_spring_x = group.use_spring_x
                rbd_const.use_spring_y = group.use_spring_y
                rbd_const.use_spring_z = group.use_spring_z

                if group.springs_stiffness_uniq:
                    rbd_const.spring_stiffness_x = group.spring_stiffness_x
                    rbd_const.spring_stiffness_y = group.spring_stiffness_y
                    rbd_const.spring_stiffness_z = group.spring_stiffness_z
                else:
                    rbd_const.spring_stiffness_x = group.spring_stiffness_uniq
                    rbd_const.spring_stiffness_y = group.spring_stiffness_uniq
                    rbd_const.spring_stiffness_z = group.spring_stiffness_uniq
 
                if group.springs_damping_uniq:
                    rbd_const.spring_damping_x = group.spring_damping_x
                    rbd_const.spring_damping_y = group.spring_damping_y
                    rbd_const.spring_damping_z = group.spring_damping_z
                else:
                    rbd_const.spring_damping_x = group.spring_damping_uniq
                    rbd_const.spring_damping_y = group.spring_damping_uniq
                    rbd_const.spring_damping_z = group.spring_damping_uniq
            
            else:

                group.spring_type = group.get_default_properties("spring_type")

                # use axis
                rbd_const.use_limit_ang_x = False
                rbd_const.use_limit_ang_y = False
                rbd_const.use_limit_ang_z = False

                group.limit_ang_lower_uniq = group.get_default_properties("limit_ang_lower_uniq") 
                rbd_const.limit_ang_x_lower = group.get_default_properties("limit_ang_x_lower")
                rbd_const.limit_ang_y_lower = group.get_default_properties("limit_ang_y_lower")
                rbd_const.limit_ang_z_lower = group.get_default_properties("limit_ang_z_lower")

                group.limit_ang_upper_uniq = group.get_default_properties("limit_ang_upper_uniq")
                rbd_const.limit_ang_x_upper = group.get_default_properties("limit_ang_x_upper")
                rbd_const.limit_ang_y_upper = group.get_default_properties("limit_ang_y_upper")
                rbd_const.limit_ang_z_upper = group.get_default_properties("limit_ang_z_upper")

                # use axis
                rbd_const.use_limit_lin_x = False
                rbd_const.use_limit_lin_y = False
                rbd_const.use_limit_lin_z = False

                group.limit_lin_lower_uniq = group.get_default_properties("limit_lin_lower_uniq")
                rbd_const.limit_lin_x_lower = group.get_default_properties("limit_lin_x_lower")
                rbd_const.limit_lin_y_lower = group.get_default_properties("limit_lin_y_lower")
                rbd_const.limit_lin_z_lower = group.get_default_properties("limit_lin_z_lower")

                group.limit_lin_upper_uniq = group.get_default_properties("limit_lin_upper_uniq")
                rbd_const.limit_lin_x_upper = group.get_default_properties("limit_lin_x_upper")
                rbd_const.limit_lin_y_upper = group.get_default_properties("limit_lin_y_upper")
                rbd_const.limit_lin_z_upper = group.get_default_properties("limit_lin_z_upper")
                
                # use axis
                rbd_const.use_spring_ang_x = False
                rbd_const.use_spring_ang_y = False
                rbd_const.use_spring_ang_z = False

                group.spring_stiffness_ang_uniq = group.get_default_properties("spring_stiffness_ang_uniq")
                rbd_const.spring_stiffness_ang_x = group.get_default_properties("spring_stiffness_ang_x")
                rbd_const.spring_stiffness_ang_y = group.get_default_properties("spring_stiffness_ang_y")
                rbd_const.spring_stiffness_ang_z = group.get_default_properties("spring_stiffness_ang_z")
                
                group.spring_damping_ang_uniq = group.get_default_properties("spring_damping_ang_uniq")
                rbd_const.spring_damping_ang_x = group.get_default_properties("spring_damping_ang_x")
                rbd_const.spring_damping_ang_y = group.get_default_properties("spring_damping_ang_y")
                rbd_const.spring_damping_ang_z = group.get_default_properties("spring_damping_ang_z")

                # use axis# use axis
                rbd_const.use_spring_x = False
                rbd_const.use_spring_y = False
                rbd_const.use_spring_z = False
                
                group.spring_stiffness_uniq = group.get_default_properties("spring_stiffness_uniq")
                rbd_const.spring_stiffness_x = group.get_default_properties("spring_stiffness_x")
                rbd_const.spring_stiffness_y = group.get_default_properties("spring_stiffness_y")
                rbd_const.spring_stiffness_z = group.get_default_properties("spring_stiffness_z")

                group.spring_damping_uniq = group.get_default_properties("spring_damping_uniq")
                rbd_const.spring_damping_x = group.get_default_properties("spring_damping_x")
                rbd_const.spring_damping_y = group.get_default_properties("spring_damping_y")
                rbd_const.spring_damping_z = group.get_default_properties("spring_damping_z")
                
            # End Spring constraitns



            rbd_const.disable_collisions = rbdlab.constraints.disable_collisions

        if context.scene.frame_current != context.scene.frame_start:
            context.scene.frame_current = context.scene.frame_start
