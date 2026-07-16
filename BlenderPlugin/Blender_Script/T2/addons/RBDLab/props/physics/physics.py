
from bpy.types import PropertyGroup
from bpy.props import PointerProperty
from .rbd_props.rigidbodies import RBDLAB_PG_rigidbodies
from .dswitch.dswitch_pointers import RBDLAB_PG_DSwitch


class RBDLAB_PG_Physics(PropertyGroup):
    """ context.scene.rbdlab.physics.x """
    rigidbodies: PointerProperty(type=RBDLAB_PG_rigidbodies)
    dswitch: PointerProperty(type=RBDLAB_PG_DSwitch)
