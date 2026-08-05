from .add import CONSTRAINTS_OT_add
from .update import CONSTRAINTS_OT_update
from .remove import CONSTRAINTS_OT_rm

# animations:
from .animations.enable_disable.constswitchs_add import RBDLAB_OT_constswitch_add
from .animations.enable_disable.constswitchs_rm import RBDLAB_OT_constswitch_rm
from .animations.enable_disable.switcher import GLUE_OT_anim_enable_disable_switcher

from .animations.glue_strength.set_glue_keyframes import GLUE_OT_set_glue_keyframes
from .animations.glue_strength.rm_all_glue_keyframes import GLUE_OT_rm_all_glue_keyframes
from .animations.springs.set_springs_keyframes import SPRINGS_OT_set_springs_keyframes
from .animations.springs.rm_springs_keyframes import SPRINGS_OT_rm_springs_keyframes

from .set_anim_brekeable import CONST_OT_set_anim_brekeable
from .set_anim_brekeable_remove import CONST_OT_set_anim_brekeable_remove
from .const_init_work_group import RBDLAB_OT_const_init_work_group
from .mute import CONST_OT_mute, CONST_OT_select_muted
from .detect import RBDLAB_OT_neighbour_chunks_calculate_broken
from .rm_constraints_groups import RM_OT_constraint_group

from .select_adjacents import RBDLAB_OT_select_adjacents_neighbours

CONST_OPS = (
    RBDLAB_OT_neighbour_chunks_calculate_broken,
    CONSTRAINTS_OT_update,
    CONSTRAINTS_OT_rm,
    CONSTRAINTS_OT_add,
    
    # animations:
    RBDLAB_OT_constswitch_add,
    RBDLAB_OT_constswitch_rm, 
    GLUE_OT_anim_enable_disable_switcher,
    
    GLUE_OT_set_glue_keyframes,
    GLUE_OT_rm_all_glue_keyframes,
    SPRINGS_OT_set_springs_keyframes,
    SPRINGS_OT_rm_springs_keyframes,

    CONST_OT_set_anim_brekeable,
    CONST_OT_set_anim_brekeable_remove,
    RBDLAB_OT_const_init_work_group,
    CONST_OT_mute, CONST_OT_select_muted,
    RM_OT_constraint_group,

    RBDLAB_OT_select_adjacents_neighbours,
    
)
