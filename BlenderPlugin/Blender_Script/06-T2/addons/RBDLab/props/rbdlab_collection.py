from bpy.types import PropertyGroup
from bpy.props import PointerProperty, IntProperty, BoolProperty
from .lists.animations.rbd.rbd_anim_dynamic_list import RBDAnimDynamicList
from .lists.animations.constraints.constswitch_list import ConstSwitchList
from .lists.metal_list import MetalList
from .metal.metal import RBDLabMetalData


class RBDLabCollectionData(PropertyGroup):
    """ collection.rbdlab.x """

    # Physics > RBD > Animation > RBD Dynamic
    dynamic_list: PointerProperty(type=RBDAnimDynamicList)

    # Constratints > Animation > Enable Disable (constswitch)
    constswitch_list: PointerProperty(type=ConstSwitchList)

    # Constratints > Animation > Iterations:
    iter_start: IntProperty(
        default=0
    )
    iter_end: IntProperty(
        default=0
    )
    iter_from: IntProperty(
        default=0
    )
    iter_to: IntProperty(
        default=0
    )
    iter_animed: BoolProperty(default=False)

