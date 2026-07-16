import bpy
from . import ops


def register():
    ops.register()


def unregister():
    ops.unregister()


if __name__ == "__main__":
    register()
