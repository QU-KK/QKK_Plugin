from .fracture.prepare import PREPARE_OPS
from .visualization_options import VISUALIZATION_OPTIONS_OPS
from .particles import PARTICLE_OPS
from .collisions import COLLISION_OPS
from .motion import MOTION_OPS

from .materials import MATERIALS_OPS

# fracture module:
from .fracture import FRACTURE_OPS

# physics module:
from .physics import GROUND_OPS
from .physics import RBD_OPS
from .constraints import CONST_OPS
from .activators import ACTIVATORS_OPS

from .visual_switching import SWITCHING_OPS

from .bake import BAKE_OPS

from .tools import OTHER_OPS
from .smoke import SMOKE_OPS
from bpy.utils import register_class, unregister_class


from .metalsoft import METAL_OPS

##################################################################
# operatiors #####################################################
##################################################################
from .target_collection import TARGET_COLLECTION_OPS

from .fracture.scatter import SCATTER_OPS, SCATTER_METHODS_OPS

from .fracture_restore import RBDLAB_OT_fracture_restore, RBDLAB_OT_scatter_restore, RBDLAB_OT_not_working_now_in_inner_details

from .speed_visualization import VISUAL_OT_speed, VISUAL_OT_speed_remove

from .invert_selection import RBDLAB_OT_invert_selection


from .custom_debris import CUSTOM_OT_debris

from .selection import SELECT_OT_piece, SELECT_OT_by_color, SELECT_OT_chunks_without_movement, SELECT_OT_compounds
from .particles_in_motion import ComputeVelocities

from .tools.tools import RAND_OT_color, CLEAR_ALL_OT_attributes, CLEAR_ALL_OT_motions, CLEAR_ALL_OT_velocities, CLEAR_OT_rbo_in_limbo, CLEAR_OT_const_in_limbo, RECALCULATE_OT_neighbors  # , REMOVE_ALL_OT_less_than_tree_verts


from .modifiers_rm_button import RBDLAB_OT_Modifiers_rm_button
from .modifiers_apply_button import RBDLAB_OT_Modifier_apply_mod

OPS_CLASSES = [

    RBDLAB_OT_Modifiers_rm_button,
    RBDLAB_OT_Modifier_apply_mod,

    # TARGET_COLL_PT_ui,
    RBDLAB_OT_scatter_restore,
    RBDLAB_OT_fracture_restore,
    RBDLAB_OT_not_working_now_in_inner_details,
    VISUAL_OT_speed,
    VISUAL_OT_speed_remove,
    # SPEED_OT_visualization,
    # REMOVE_SPEED_OT_visualization,
    RAND_OT_color,
    RBDLAB_OT_invert_selection,

    SELECT_OT_piece,
    SELECT_OT_by_color,
    SELECT_OT_chunks_without_movement,
    SELECT_OT_compounds,
    CUSTOM_OT_debris,

    ComputeVelocities,

    CLEAR_ALL_OT_attributes,
    CLEAR_ALL_OT_motions,
    CLEAR_ALL_OT_velocities,
    CLEAR_OT_rbo_in_limbo,
    CLEAR_OT_const_in_limbo,
    RECALCULATE_OT_neighbors,
    # REMOVE_ALL_OT_less_than_tree_verts
]

#######################################
# NUEVO MÉTODO
#######################################


def register():

    # Fracture > Prepare
    for cls in PREPARE_OPS:
        register_class(cls)

    # visualization options
    for cls in VISUALIZATION_OPTIONS_OPS:
        register_class(cls)

    # Modules
    for cls in TARGET_COLLECTION_OPS:
        register_class(cls)

    for cls in SMOKE_OPS:
        register_class(cls)
    for cls in OTHER_OPS:
        register_class(cls)
    for cls in PARTICLE_OPS:
        register_class(cls)
    for cls in COLLISION_OPS:
        register_class(cls)
    for cls in MOTION_OPS:
        register_class(cls)

    # fracture module
    for cls in FRACTURE_OPS:
        register_class(cls)
    for cls in SCATTER_OPS:
        register_class(cls)
    for cls in SCATTER_METHODS_OPS:
        register_class(cls)

    # physics module
    for cls in GROUND_OPS:
        register_class(cls)
    for cls in RBD_OPS:
        register_class(cls)
    for cls in CONST_OPS:
        register_class(cls)
    for cls in ACTIVATORS_OPS:
        register_class(cls)

    for cls in SWITCHING_OPS:
        register_class(cls)

    # bake module
    for cls in BAKE_OPS:
        register_class(cls)

    # OLD. reemplazar poco a poco OPS_CLASSES por [MODULO]_OPS para cada módulo (fracture, pyshics, particles...)
    for cls in OPS_CLASSES:
        register_class(cls)

    for cls in MATERIALS_OPS:
        register_class(cls)
    
    for cls in METAL_OPS:
        register_class(cls)


def unregister():

    # Fracture > Prepare
    for cls in PREPARE_OPS:
        unregister_class(cls)

    # visualization options
    for cls in VISUALIZATION_OPTIONS_OPS:
        unregister_class(cls)

    # Modules.
    for cls in TARGET_COLLECTION_OPS:
        unregister_class(cls)

    for cls in SMOKE_OPS:
        unregister_class(cls)
    for cls in OTHER_OPS:
        unregister_class(cls)
    for cls in PARTICLE_OPS:
        unregister_class(cls)
    for cls in COLLISION_OPS:
        unregister_class(cls)
    for cls in MOTION_OPS:
        unregister_class(cls)

    # fracture module
    for cls in FRACTURE_OPS:
        unregister_class(cls)
    for cls in SCATTER_OPS:
        unregister_class(cls)
    for cls in SCATTER_METHODS_OPS:
        unregister_class(cls)

    # physics module
    for cls in GROUND_OPS:
        unregister_class(cls)
    for cls in RBD_OPS:
        unregister_class(cls)
    for cls in CONST_OPS:
        unregister_class(cls)
    for cls in ACTIVATORS_OPS:
        unregister_class(cls)

    for cls in SWITCHING_OPS:
        unregister_class(cls)

    # bake module
    for cls in BAKE_OPS:
        unregister_class(cls)

    # OLD. reemplazar poco a poco OPS_CLASSES por [MODULO]_OPS para cada módulo (fracture, pyshics, particles...)
    for cls in OPS_CLASSES:
        unregister_class(cls)

    for cls in MATERIALS_OPS:
        unregister_class(cls)
    
    for cls in METAL_OPS:
        unregister_class(cls)
