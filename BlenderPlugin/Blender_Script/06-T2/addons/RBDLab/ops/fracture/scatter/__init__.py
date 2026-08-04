from .scatter import (
    ACCEPT_OT_scatter,
    SCATTER_OT_cancel,
    SCATTER_OT_object,
    SELECT_OT_scatter,
)

from .organic import SCATTER_OT_add_organic, SCATTER_OT_organic_accept
from .by_texture import SCATTER_OT_add_by_texture, SCATTER_OT_by_texture_accept

from .BooleanFracture.bf_gn_add import BFRACTURE_OT_add
from .BooleanFracture.bf_gn_remove import BFRACTURE_OT_rm
from .BooleanFracture.bf_gn_append_new_gn import BFRACTURE_OT_append
from .BooleanFracture.bf_gn_make_real import BFRACTURE_OT_make_real
from .BooleanFracture.bf_gn_go_back import BFRACTURE_OT_go_back
from .BooleanFracture.bf_gn_apply import BFRACTURE_OT_apply

from .by_edges import SCATTER_OT_extract_edges_all, SCATTER_OT_extract_edges_all_cancel, SCATTER_OT_extract_edges_all_accept, SCATTER_OT_extract_edges_inners, SCATTER_OT_extract_edges_inners_accept, SCATTER_OT_extract_edges_inners_cancel, SCATTER_OT_extract_edges_innerfaces, SCATTER_OT_extract_edges_innerfaces_cancel

SCATTER_OPS = (
    ACCEPT_OT_scatter,
    SCATTER_OT_cancel,
    SCATTER_OT_object,
    SELECT_OT_scatter,
)

SCATTER_METHODS_OPS = (
    SCATTER_OT_add_organic,
    SCATTER_OT_extract_edges_all_cancel,
    SCATTER_OT_organic_accept,
    SCATTER_OT_add_by_texture,
    SCATTER_OT_by_texture_accept,
    BFRACTURE_OT_add,
    BFRACTURE_OT_rm,
    BFRACTURE_OT_append,
    BFRACTURE_OT_make_real,
    BFRACTURE_OT_go_back,
    BFRACTURE_OT_apply,
    SCATTER_OT_extract_edges_all,
    SCATTER_OT_extract_edges_all_accept,
    SCATTER_OT_extract_edges_inners,
    SCATTER_OT_extract_edges_inners_accept,
    SCATTER_OT_extract_edges_inners_cancel,
    SCATTER_OT_extract_edges_innerfaces,
    SCATTER_OT_extract_edges_innerfaces_cancel,
)
