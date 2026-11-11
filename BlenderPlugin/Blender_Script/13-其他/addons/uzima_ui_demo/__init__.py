# Copyright (C) 2026 Raisy Clutch
# raisycltch@gmail.com
#
# Created by Raisy Clutch
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Uzima UI demo add-on.

Shows every Uzima UI element in a custom N-panel tab ("Uzima") and over the 3D viewport.
Almost everything is connected to real Blender data: scene and render settings, the active
object, materials, node curves and color ramps, collections, keymaps and operators.

Files:
    demo_core.py   properties, the app, actions with hotkeys, viewport tools
    demo_pages.py  one function per sidebar page
    uzima/         the library (copy this folder into your own add-on)
"""
bl_info = {
    "name" : "UI_Demo",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "category" : "UI" 
}
import bpy
from bpy.app.handlers import persistent
from bpy.props import PointerProperty

from . import uzima as ui
from .demo_core import CLASSES, UzimaDemoProps, app, ensure_demo_nodes
from .demo_pages import build_sidebar

sidebar = app.sidebar("Uzima", build=build_sidebar)
viewport = app.viewport()


@persistent
def _on_load(*_):
    bpy.app.timers.register(ensure_demo_nodes, first_interval=0.2)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.uzima_demo = PointerProperty(type=UzimaDemoProps)
    app.register()
    bpy.app.handlers.load_post.append(_on_load)
    bpy.app.timers.register(ensure_demo_nodes, first_interval=0.5)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    app.unregister()
    del bpy.types.Scene.uzima_demo
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
