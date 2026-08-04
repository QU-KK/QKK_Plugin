
from bpy.types import PropertyGroup
from bpy.props import PointerProperty
from .dparent.dynamic_parent_props import RBDLAB_PG_dynamic_parent
from .visual_switching_props import RBDLab_PG_visual_switching_props

class RBDLAB_PG_DSwitch(PropertyGroup):
    """ context.scene.rbdlab.physics.dswitch.x """

    dynamic_parent: PointerProperty(type=RBDLAB_PG_dynamic_parent)
    visual_switching: PointerProperty(type=RBDLab_PG_visual_switching_props)
