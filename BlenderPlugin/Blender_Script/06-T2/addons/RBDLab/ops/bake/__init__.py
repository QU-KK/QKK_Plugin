from .bake import BAKE_OT_current_to_cache, BAKE_OT_free_bake_all_particles  # , BAKE_OT_bake_curren_particles
from .bake_to_keyframes import BAKE_OT_TO_KEYFRAMES
from .bake_action_visual_keying import BAKE_OT_action_visual_keying, BAKE_OT_remove_bake_action


BAKE_OPS = (
    BAKE_OT_TO_KEYFRAMES,
    BAKE_OT_action_visual_keying,
    BAKE_OT_remove_bake_action,
    BAKE_OT_current_to_cache,
    # BAKE_OT_bake_curren_particles,
    BAKE_OT_free_bake_all_particles,
)
