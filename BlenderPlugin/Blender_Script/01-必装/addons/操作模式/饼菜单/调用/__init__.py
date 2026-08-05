from.模型法向处理.__init__ import register as 模型法向处理_register
from.模型法向处理.__init__ import unregister as 模型法向处理_unregister

from.面挤出锐化.__init__ import register as 面挤出锐化_register
from.面挤出锐化.__init__ import unregister as 面挤出锐化_unregister




def register():
    模型法向处理_register()
    面挤出锐化_register()

def unregister(): 
    模型法向处理_unregister()
    面挤出锐化_unregister()
