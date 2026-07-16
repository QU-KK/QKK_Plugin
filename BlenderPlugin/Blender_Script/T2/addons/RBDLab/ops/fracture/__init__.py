from .add_highs_mods import SET_OT_inner_detail


# from .apply_mods import APPLY_OT_mods

# from .backup_apply_mods import APPLY_OT_mods
from .apply_mods import APPLY_OT_mods

from .auto_fix_chunks import AUTO_OT_fix_chunks

from .cellfracture import CELL_FRACTURE_OT_custom
# from .old_cellfracture_backup import CELL_FRACTURE_OT_custom

from .octree_deepth_uniform import OCTREE_DEPTH_OT_uniform
from .rm_void_chunks import SELECT_OT_rm_void_chunks
from .select_bad_chunks import SELECT_OT_bad_chunks
from .toggle_decimate_mod import HIGH_DETAILS_OT_toggle_decimate
from .working_in_innner_details_cancel import RBDLAB_OT_working_in_innner_detals_cancel


FRACTURE_OPS = (
    SET_OT_inner_detail,
    APPLY_OT_mods,
    AUTO_OT_fix_chunks,
    CELL_FRACTURE_OT_custom,
    OCTREE_DEPTH_OT_uniform,
    SELECT_OT_rm_void_chunks,
    SELECT_OT_bad_chunks,
    HIGH_DETAILS_OT_toggle_decimate,
    RBDLAB_OT_working_in_innner_detals_cancel,
)
