"""Route a tangent Normal map through the native Material IR.

The Normal mesh map used to hand any procedural high-material normal detail (Bevel,
Bump, Noise -> Bump ...) to a hidden Cycles bake and paste the result over the Fyr
normal afterwards. The MATERIAL row's NORMAL channel already evaluates exactly those
graphs on the GPU -- the high's full shading normal at the projection hit, converted
to the low's tangent frame and 0-1 encoded -- so a Normal row whose graph compiles
natively is sent to the backend as that channel instead. The row keeps its identity
(uuid, output file name, Normal Format); only the job's map type changes.
"""

from __future__ import annotations

from . import constants


class NormalAsMaterialRow:
    """A NORMAL map row seen as a MATERIAL row on the NORMAL channel.

    Read-only view: every material-row field the IR collector, the phase planner and
    the job writer read is answered here, everything else comes from the real row.
    Writes are dropped so the route status of the virtual row never lands on the
    artist's Normal row.
    """

    __slots__ = ("_item",)

    _OVERRIDES = {
        "map_type": constants.MAP_MATERIAL,
        "material_channel": constants.MATERIAL_CHANNEL_NORMAL,
        "material_origin": constants.MATERIAL_ORIGIN_MANUAL,
        "material_custom_name": "",
        "material_data_type": "",
        "execution_route": constants.EXECUTION_ROUTE_AUTO,
        # Encode in the LOW's tangent frame: the output is a normal map, not the
        # material's own detail (material_ir._encode_world_normal_as_tangent).
        "normal_encode_low_frame": True,
    }

    def __init__(self, item):
        object.__setattr__(self, "_item", item)

    def __getattr__(self, name):
        overrides = NormalAsMaterialRow._OVERRIDES
        if name in overrides:
            return overrides[name]
        return getattr(object.__getattribute__(self, "_item"), name)

    def __setattr__(self, name, value):
        return None


def row_is_eligible(item) -> bool:
    """Static half of the decision: a tangent Normal row with Material Detail = Auto.

    Object/World normal rows, Material Only and Off keep their existing routes. Whether
    the graph actually compiles natively is decided at export, per job.
    """
    if getattr(item, "is_add_phantom", False):
        return False
    if str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_NORMAL:
        return False
    space = str(
        getattr(item, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT)
        or constants.MAP_NORMAL_SPACE_TANGENT
    ).strip().upper()
    if space != constants.MAP_NORMAL_SPACE_TANGENT:
        return False
    mode = str(
        getattr(item, "material_detail_mode", constants.MATERIAL_DETAIL_AUTO)
        or constants.MATERIAL_DETAIL_AUTO
    ).strip().upper()
    return mode == constants.MATERIAL_DETAIL_AUTO
