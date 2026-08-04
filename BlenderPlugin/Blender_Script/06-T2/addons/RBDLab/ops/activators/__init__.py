from .set_activators import ACTIVATORS_OT_set_activators
from .unset_activators import ACTIVATORS_OT_unset_activators

from .include_chunks import ACTIVATORS_OT_include_chunks
from .exclude_chunks import ACTIVATORS_OT_exclude_chunks

from .explode import ACTIVATORS_OT_explode_done

from .record import ACTIVATORS_OT_recording
from .rm_record import ACTIVATORS_OT_rm_record

from .without_automatic_range import ACTIVATORS_OT_transfer_substeps, ACTIVATORS_OT_transfer_total_frames_from_sim

from .set_interpolation import ACTIVATORS_OT_set_interpolation

from .parent_activators import ACTIVATORS_OT_parent_activators

from .list.add_layer import ACTIVATORS_OT_create_item
from .list.ac_layers_rm_item_list import ACTIVATORS_OT_ac_layers_rm_item

from .list.add_activators import ACTIVATORS_OT_add_activator
from .list.activators_rm_item_list import ACTIVATORS_OT_activators_rm_item
from .list.activators_dropdow import ACTIVATORS_OT_dropdown

ACTIVATORS_OPS = (
    ACTIVATORS_OT_set_activators,
    ACTIVATORS_OT_unset_activators,
    ACTIVATORS_OT_include_chunks,
    ACTIVATORS_OT_exclude_chunks,
    ACTIVATORS_OT_explode_done,
    ACTIVATORS_OT_recording,
    ACTIVATORS_OT_rm_record,
    ACTIVATORS_OT_transfer_total_frames_from_sim,
    ACTIVATORS_OT_transfer_substeps, ACTIVATORS_OT_set_interpolation,
    ACTIVATORS_OT_parent_activators,
    ACTIVATORS_OT_create_item, ACTIVATORS_OT_ac_layers_rm_item,
    ACTIVATORS_OT_add_activator, ACTIVATORS_OT_activators_rm_item, ACTIVATORS_OT_dropdown
)
