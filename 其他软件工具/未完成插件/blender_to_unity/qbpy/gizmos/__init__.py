import bpy
from .viewport import (
    CP_GT_custom_shape,
    CP_GG_viewport,
)


classes = (
    CP_GT_custom_shape,
    CP_GG_viewport,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
