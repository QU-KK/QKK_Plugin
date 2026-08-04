from .ground.ground_add import GROUND_OT_add

from .rigidbodies.rbd_ops.settings.rbd_add import RBDLAB_OT_add
from .rigidbodies.rbd_ops.settings.rbd_remove import RBDLAB_OT_rm
from .rigidbodies.rbd_ops.settings.rbd_update import RBDLAB_OT_update

from .rigidbodies.rbd_ops.settings.set_passive import RBDLAB_OT_passive
from .rigidbodies.rbd_ops.settings.set_passive_remove import RBDLAB_OT_rm_passives
from .rigidbodies.rbd_ops.settings.select_passives import RBDLAB_OT_select_passives

from .rigidbodies.rbd_ops.settings.join_separate.join_by_selection import RBDLAB_OT_join_by_selection
from .rigidbodies.rbd_ops.settings.join_separate.separate_by_selection import RBDLAB_OT_separate_by_selection

from .rigidbodies.rbd_ops.animation.add_off_on import RBDLAB_OT_physics_rbd_anim_add_off_on
from .rigidbodies.rbd_ops.animation.add_substep_per_frame_keyframes import RBDLAB_OT_rbd_anim_add_substep_per_frame_keyframes
from .rigidbodies.rbd_ops.animation.add_solver_iterations_keyframes import RBDLAB_OT_rbd_anim_add_solver_iterations_keyframes
from .rigidbodies.rbd_ops.animation.add_world_speed_keyframes import RBDLAB_OT_rbd_anim_add_world_speed_keyframes
from .rigidbodies.rbd_ops.animation.rm_substeps_keyframes import RBDLAB_OT_rbd_anim_rm_substep_per_frame_keyframes
from .rigidbodies.rbd_ops.animation.rm_solver_iterations_keyframes import RBDLAB_OT_rbd_anim_rm_solver_iterations_keyframes
from .rigidbodies.rbd_ops.animation.rm_world_speed_keyframes import RBDLAB_OT_rbd_anim_rm_world_speed_keyframes

from .rigidbodies.rbd_ops.animation.dynamic_list_rm_item import RBDLAB_OT_physics_rbd_anim_dynamic_list_rm_item

from .rigidbodies.kinematics.set_kinematic import RBDLAB_OT_sel_to_kinematic
from .rigidbodies.kinematics.set_kinematic_remove import RBDLAB_OT_rm_sel_to_kinematics
from .rigidbodies.kinematics.set_kinematic_select import RBDLAB_OT_select_sel_kinematics
from .rigidbodies.kinematics.selset_anim_keyframe import RBDLAB_OT_sel_set_animated_keyframe
from .rigidbodies.kinematics.remove_sel_anim_keyframe import RBDLAB_OT_rm_sel_animated_keyframes

from .rigidbodies.kinematics.set_anim_keyframe import RBDLAB_OT_set_animated_keyframe
from .rigidbodies.kinematics.remove_all_anim_keyframe import RBDLAB_OT_rm_all_animated_keyframes

from .parents.handler.handler_add import RBDLAB_OT_physics_parents_add_handler, RBDLAB_OT_physics_parents_rm_handler
from .parents.handler.handler_reset import RBDLAB_OT_physics_parents_reset_handler

from .parents.dswitch.dswitch_bake_original import RBDLAB_OT_physics_parents_bake_original
from .parents.dswitch.dswitch_clear_bake_original import RBDLAB_OT_physics_parents_clear_bake_original

from .parents.dswitch.dswitch_dynamic_parent import RBDLAB_OT_physics_dynamic_switch
from .parents.dswitch.dswitch_dynamic_parent_reset import RBDLAB_OT_physics_parents_reset

from .rigidbodies.parents.parent_edge_compound import RBDLAB_OT_edges_parent, RBDLAB_OT_edges_parent_remove

GROUND_OPS = (
    GROUND_OT_add,
)

RBD_OPS = (
    RBDLAB_OT_add,
    RBDLAB_OT_rm,
    RBDLAB_OT_update,
    RBDLAB_OT_passive,
    RBDLAB_OT_select_passives,
    
    RBDLAB_OT_physics_rbd_anim_add_off_on,
    RBDLAB_OT_rbd_anim_add_substep_per_frame_keyframes,
    RBDLAB_OT_rbd_anim_add_solver_iterations_keyframes,
    RBDLAB_OT_rbd_anim_add_world_speed_keyframes,
    RBDLAB_OT_rbd_anim_rm_substep_per_frame_keyframes,
    RBDLAB_OT_rbd_anim_rm_solver_iterations_keyframes,
    RBDLAB_OT_rbd_anim_rm_world_speed_keyframes,

    RBDLAB_OT_physics_rbd_anim_dynamic_list_rm_item,

    RBDLAB_OT_rm_passives,
    RBDLAB_OT_set_animated_keyframe,
    RBDLAB_OT_rm_all_animated_keyframes,
    RBDLAB_OT_select_sel_kinematics,
    RBDLAB_OT_sel_set_animated_keyframe,
    RBDLAB_OT_rm_sel_animated_keyframes,

    RBDLAB_OT_join_by_selection,
    RBDLAB_OT_separate_by_selection,

    RBDLAB_OT_physics_parents_add_handler, RBDLAB_OT_physics_parents_rm_handler,
    RBDLAB_OT_physics_parents_reset_handler,
    RBDLAB_OT_physics_parents_bake_original,
    RBDLAB_OT_physics_parents_clear_bake_original,
    RBDLAB_OT_physics_dynamic_switch,
    RBDLAB_OT_physics_parents_reset,

    RBDLAB_OT_sel_to_kinematic,
    RBDLAB_OT_rm_sel_to_kinematics,
    RBDLAB_OT_edges_parent,
    RBDLAB_OT_edges_parent_remove,
)
