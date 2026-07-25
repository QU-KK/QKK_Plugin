bl_info = {
    "name": "Blender to Unity",
    "author": "Karan, Bananenbrot",
    "description": "Export Meshes, Animations, Colliders and Lods to Unity Engine.",
    "blender": (3, 3, 0),
    "version": (2, 1, 1),
    "category": "Import-Export",
    "location": "3D Viewport > Sidebar(N-Panel) > Unity",
    "support": "COMMUNITY",
    "warning": "",
    "doc_url": "https://b3dhub.github.io/blender-to-unity-docs/",
    "tracker_url": "https://discord.gg/sdnHHZpWbT",
}


import bpy
from . import source
from . import preferences
from . import changelog


def register():
    source.register()
    preferences.register()
    changelog.register()


def unregister():
    source.unregister()
    preferences.unregister()
    changelog.unregister()


if __name__ == "__main__":
    register()
