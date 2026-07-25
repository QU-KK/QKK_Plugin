import bpy
from . import icon
from . import manual
from . import props


def register():
    icon.register()
    manual.register()
    props.register()


def unregister():
    icon.unregister()
    props.unregister()
