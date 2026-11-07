from.吸附到点快捷键.plugin.__init__ import register as 吸附到点快捷键_register
from.吸附到点快捷键.plugin.__init__ import unregister as 吸附到点快捷键_unregister

from.轴自定义快捷键.plugin.__init__ import register as 轴自定义快捷键_register
from.轴自定义快捷键.plugin.__init__ import unregister as 轴自定义快捷键_unregister

from.HDR旋转.plugin.__init__ import register as HDR旋转_register
from.HDR旋转.plugin.__init__ import unregister as HDR旋转_unregister

def register():
    吸附到点快捷键_register()
    轴自定义快捷键_register()
    HDR旋转_register()

def unregister(): 
    吸附到点快捷键_unregister()
    轴自定义快捷键_unregister()
    HDR旋转_unregister()