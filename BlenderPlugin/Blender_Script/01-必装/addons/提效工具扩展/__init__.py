bl_info = {
    "name" : "提效工具扩展",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "category" : "个人偏好" 
}

import bpy

#快捷按钮
from.快捷按钮.__init__ import register as 快捷按钮_register
from.快捷按钮.__init__ import unregister as 快捷按钮_unregister

#扩展
from.扩展.__init__ import register as 扩展_register
from.扩展.__init__ import unregister as 扩展_unregister


def register():
    扩展_register()
    快捷按钮_register()



def unregister(): 
    扩展_unregister()
    快捷按钮_unregister()



print('提效工具扩展加载成功')