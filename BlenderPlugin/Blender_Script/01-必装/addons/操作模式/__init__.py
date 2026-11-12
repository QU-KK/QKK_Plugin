bl_info = {
    "name" : "操作模式",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "category" : "个人偏好" 
}

import bpy

#饼菜单
from.饼菜单.__init__ import register as 饼菜单_register
from.饼菜单.__init__ import unregister as 饼菜单_unregister

#饼菜单调用
from.饼菜单.调用.__init__ import register as 饼菜单调用_register
from.饼菜单.调用.__init__ import unregister as 饼菜单调用_unregister

#快捷键
from.快捷键.__init__ import register as 快捷键_register
from.快捷键.__init__ import unregister as 快捷键_unregister

#快捷键映射
from.快捷键映射.__init__ import register as 快捷键映射_register
from.快捷键映射.__init__ import unregister as 快捷键映射_unregister


def register():
    饼菜单_register()
    饼菜单调用_register()
    快捷键_register()
    快捷键映射_register

def unregister(): 
    饼菜单_unregister()
    饼菜单调用_unregister()
    快捷键_unregister()
    快捷键映射_unregister

print('操作模式加载成功')