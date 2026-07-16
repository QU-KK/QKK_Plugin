from .subdivision import RBDLAB_OT_surface
from .annotate import RBDLAB_anotation_paint
from .paint import RBDLAB_weight_paint, CLEAR_weight_paint
from .add_modifier import RBDLAB_OT_Prepare_Add_modifier
from .accept_proxy import RBDLAB_OT_Prepare_Accept_proxy
from .cancel_proxy import RBDLAB_OT_Cancel_proxy

PREPARE_OPS = (
    RBDLAB_OT_surface,
    RBDLAB_anotation_paint,
    RBDLAB_weight_paint, CLEAR_weight_paint,
    RBDLAB_OT_Prepare_Add_modifier, RBDLAB_OT_Prepare_Accept_proxy, RBDLAB_OT_Cancel_proxy
)
