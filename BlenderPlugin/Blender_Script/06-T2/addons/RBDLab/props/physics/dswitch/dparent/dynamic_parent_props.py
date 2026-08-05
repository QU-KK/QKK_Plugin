from .....addon.naming import RBDLabNaming
from bpy.types import PropertyGroup, Object
from bpy.props import PointerProperty


class RBDLAB_PG_dynamic_parent(PropertyGroup):
    select_original: PointerProperty(
        name="Select Original",
        description="Select Original Object, from where the object was fractured",
        type=Object
    )
