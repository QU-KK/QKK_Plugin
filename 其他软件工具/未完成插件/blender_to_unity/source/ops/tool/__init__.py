import bpy
from . import rename


def register():
    rename.register()


def unregister():
    rename.unregister()


if __name__ == "__main__":
    register()
