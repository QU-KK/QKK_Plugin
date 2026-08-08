bl_info = {
    "name": "Unity 材质同步",
    "author": "Cursor",
    "version": (0, 2, 19),
    "blender": (5, 2, 0),
    "location": "3D View Header > 同步材质",
    "description": "按模型名查询 Unity prefab 材质信息，并写入模板材质的预留贴图节点。",
    "category": "Material",
}


def register():
    from . import documentation, operators, panel, preferences

    documentation.register()
    preferences.register()
    operators.register()
    panel.register()


def unregister():
    from . import documentation, operators, panel, preferences

    panel.unregister()
    operators.unregister()
    preferences.unregister()
    documentation.unregister()
