import bpy
from . import auto_convex
from . import box
from . import capsule
from . import convex
from . import cylinder
from . import sphere


def register():
    auto_convex.register()
    box.register()
    capsule.register()
    convex.register()
    cylinder.register()
    sphere.register()


def unregister():
    auto_convex.unregister()
    box.unregister()
    capsule.unregister()
    convex.unregister()
    cylinder.unregister()
    sphere.unregister()


if __name__ == "__main__":
    register()
