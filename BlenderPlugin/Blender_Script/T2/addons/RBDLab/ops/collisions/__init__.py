from .collision_select import RBDLAB_OT_collision_select
from .p_collision_to import RBDLAB_OT_p_collisions_to
from .p_collision_update import RBDLAB_OT_p_collisions_update
from .p_collision_remove import RBDLAB_OT_p_collisions_remove
from .p_single_object_collisions_create import RBDLAB_OT_p_single_object_collisions_create
from .p_single_object_collisions_remove import RBDLAB_OT_p_single_object_collisions_remove
from .to_static_objects import COLLISIONS_OT_to_static_objects, COLLISIONS_OT_to_static_objects_update

COLLISION_OPS = (
    RBDLAB_OT_collision_select,
    RBDLAB_OT_p_collisions_to,
    RBDLAB_OT_p_collisions_update,
    RBDLAB_OT_p_collisions_remove,
    RBDLAB_OT_p_single_object_collisions_create,
    RBDLAB_OT_p_single_object_collisions_remove,
    COLLISIONS_OT_to_static_objects,
    COLLISIONS_OT_to_static_objects_update
)
