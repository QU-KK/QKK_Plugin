from .materials import RBDLAB_OT_assign_materials, RBDLAB_OT_set_current_material_to_rbdlab_inner_mat
from .materials_init_collections import RBDLAB_OT_materials_init_collections

MATERIALS_OPS = (
    RBDLAB_OT_assign_materials,
    RBDLAB_OT_materials_init_collections,
    RBDLAB_OT_set_current_material_to_rbdlab_inner_mat
)
