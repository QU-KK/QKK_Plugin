bl_info = {
    "name" : "操作模式",
    "author" : "渠奎奎", 
    "description" : "",
    "blender" : (5, 2, 0),
    "version" : (1, 0, 0),
    "location" : "",
    "warning" : "",
    "doc_url": "", 
    "tracker_url": "", 
    "category" : "操作模式" 
}

import bpy

#print('加载QKK插件')

#第三方关联插件加载
#from.第三方关联插件加载.__init__ import register as 第三方关联插件加载_register
#from.第三方关联插件加载.__init__ import unregister as 第三方关联插件加载_unregister


#饼菜单
from.饼菜单.__init__ import register as 饼菜单_register
from.饼菜单.__init__ import unregister as 饼菜单_unregister
#饼菜单调用
from.饼菜单.调用.__init__ import register as 饼菜单调用_register
from.饼菜单.调用.__init__ import unregister as 饼菜单调用_unregister


def register():
    #第三方关联插件加载_register()
    饼菜单_register()
    饼菜单调用_register()

def unregister(): 
    #第三方关联插件加载_unregister()
    饼菜单_unregister()
    饼菜单调用_unregister()

print('QKK插件加载成功')
