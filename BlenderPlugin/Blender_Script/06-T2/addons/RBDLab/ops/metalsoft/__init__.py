from .creation.create_metal_mesh import RBDLAB_OT_create_metal_mesh
from .creation.clean_fractures import RBDLAB_OT_metal_clean_fractures
from .creation.rebind import RBDLAB_OT_metal_rebind
from .creation.rm_metal_mesh import RBDLAB_OT_rm_metal_mesh

from .creation.set_proxy_mesh import RBDLAB_OT_metalsoft_add_proxy_mesh
from .creation.set_original_mesh import RBDLAB_OT_metalsoft_add_original_mesh

from .creation.modifiers.add_modifiers import RBDLAB_OT_metal_add_modifiers
from .creation.modifiers.remove_modifiers import RBDLAB_OT_metal_remove_modifiers
from .creation.modifiers.move_modifiers import RBDLAB_OT_metal_modifiers_list_item_move
from .creation.modifiers.displace_new_texture import RBDLAB_OT_metal_displace_new_textue

from .creation.modifiers.update import RBDLAB_OT_metal_update_modifiers
from .remesh.modifiers.update import RBDLAB_OT_metalsoft_remesh_update_modifiers

from .common.add_modifiers import RBDLAB_OT_Metalsoft_Add_modifier


METAL_OPS = (
    RBDLAB_OT_create_metal_mesh,
    RBDLAB_OT_metal_clean_fractures,
    RBDLAB_OT_metal_rebind,
    RBDLAB_OT_rm_metal_mesh,
    RBDLAB_OT_metalsoft_add_proxy_mesh, RBDLAB_OT_metalsoft_add_original_mesh,
    RBDLAB_OT_metal_add_modifiers, RBDLAB_OT_metal_remove_modifiers, RBDLAB_OT_metal_modifiers_list_item_move, RBDLAB_OT_metal_update_modifiers, RBDLAB_OT_metal_displace_new_textue, 
    RBDLAB_OT_Metalsoft_Add_modifier, RBDLAB_OT_metalsoft_remesh_update_modifiers
)
