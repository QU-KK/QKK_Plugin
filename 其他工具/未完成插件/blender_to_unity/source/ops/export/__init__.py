import bpy
from . import background
from . import fbx
from . import fbx_test
from . import path


def register():
    background.register()
    fbx.register()
    # fbx_test.register()
    path.register()


def unregister():
    background.unregister()
    fbx.unregister()
    # fbx_test.unregister()
    path.unregister()


if __name__ == "__main__":
    register()
