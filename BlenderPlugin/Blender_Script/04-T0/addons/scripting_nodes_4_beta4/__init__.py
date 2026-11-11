bl_info = {
    "name" : "scripting_nodes_4_beta4",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "category" : "可视化插件" 
}

from . import auto_load


def register():
    auto_load.init()
    auto_load.register()


def unregister():
    auto_load.unregister()
