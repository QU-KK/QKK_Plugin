bl_info = {
    "name" : "操作方式",
    "author" : "渠奎奎", 
    "description" : "",
    "blender" : (4, 2, 0),
    "version" : (3, 0, 0),
    "location" : "位置",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "3D View" 
}

import bpy

#print('加载QKK插件')

#第三方关联插件加载
#from.第三方关联插件加载.__init__ import register as 第三方关联插件加载_register
#from.第三方关联插件加载.__init__ import unregister as 第三方关联插件加载_unregister


#物体模式饼菜单
from.物体模式饼菜单.__init__ import register as 物体模式饼菜单_register
from.物体模式饼菜单.__init__ import unregister as 物体模式饼菜单_unregister

#编辑模式饼菜单
from.编辑模式饼菜单.__init__ import register as 编辑模式饼菜单_register
from.编辑模式饼菜单.__init__ import unregister as 编辑模式饼菜单_unregister

#快捷按钮
from.快捷按钮.__init__ import register as 快捷按钮_register
from.快捷按钮.__init__ import unregister as 快捷按钮_unregister

#快捷键
from.快捷键.__init__ import register as 快捷键_register
from.快捷键.__init__ import unregister as 快捷键_unregister

#扩展
from.扩展.__init__ import register as 扩展_register
from.扩展.__init__ import unregister as 扩展_unregister




def register():
    #第三方关联插件加载_register()
    物体模式饼菜单_register()
    编辑模式饼菜单_register()
    快捷按钮_register()
    快捷键_register()
    扩展_register()

def unregister(): 
    #第三方关联插件加载_unregister()
    物体模式饼菜单_unregister()
    编辑模式饼菜单_unregister()
    快捷按钮_unregister()
    快捷键_unregister()
    扩展_unregister()

print('QKK插件加载成功')
