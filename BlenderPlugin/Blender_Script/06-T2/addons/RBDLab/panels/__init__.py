# UI CLASSES REGISTRATION.
from bpy.utils import register_class, unregister_class

from .main import MAIN_UI
from .fracture import FRACTURE_UI
from .pyshics import PYSHICS_UI
from .constraints import CONSTR_UI
from .activators import ACTIVATORS_UI
from .bake import BAKE_UI
from .particles import PARTICLES_UI
from .collisions import COLLISIONS_UI
from .smoke import SMOKE_UI
from .motion import MOTION_UI
from .tools import TOOLS_UI
from .dynamic_switch import DSWITCH_UI
from .metalsoft import METAL_UI
# from .materials import MATERIALS_UI


def register():
    for cls in MAIN_UI:
        register_class(cls)
    for cls in FRACTURE_UI:
        register_class(cls)
    for cls in PYSHICS_UI:
        register_class(cls)
    for cls in ACTIVATORS_UI:
        register_class(cls)
    for cls in CONSTR_UI:
        register_class(cls)
    for cls in BAKE_UI:
        register_class(cls)
    for cls in PARTICLES_UI:
        register_class(cls)
    for cls in COLLISIONS_UI:
        register_class(cls)
    for cls in SMOKE_UI:
        register_class(cls)
    for cls in MOTION_UI:
        register_class(cls)
    for cls in TOOLS_UI:
        register_class(cls)
    for cls in DSWITCH_UI:
        register_class(cls)
    for cls in METAL_UI:
        register_class(cls)
    # for cls in MATERIALS_UI:
    #     register_class(cls)


def unregister():
    for cls in reversed(MAIN_UI):
        unregister_class(cls)
    for cls in reversed(FRACTURE_UI):
        unregister_class(cls)
    for cls in reversed(PYSHICS_UI):
        unregister_class(cls)
    for cls in reversed(ACTIVATORS_UI):
        unregister_class(cls)
    for cls in reversed(CONSTR_UI):
        unregister_class(cls)
    for cls in reversed(BAKE_UI):
        unregister_class(cls)
    for cls in reversed(PARTICLES_UI):
        unregister_class(cls)
    for cls in reversed(COLLISIONS_UI):
        unregister_class(cls)
    for cls in reversed(SMOKE_UI):
        unregister_class(cls)
    for cls in reversed(MOTION_UI):
        unregister_class(cls)
    for cls in reversed(TOOLS_UI):
        unregister_class(cls)
    for cls in reversed(DSWITCH_UI):
        unregister_class(cls)
    for cls in reversed(METAL_UI):
        unregister_class(cls)
    # for cls in reversed(MATERIALS_UI):
    #     unregister_class(cls)
