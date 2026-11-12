from.大纲操作按钮.plugin.__init__ import register as 大纲操作按钮_register
from.大纲操作按钮.plugin.__init__ import unregister as 大纲操作按钮_unregister


from.行走模式按钮.plugin.__init__ import register as 行走模式按钮_register
from.行走模式按钮.plugin.__init__ import unregister as 行走模式按钮_unregister

from.新窗口按钮.plugin.__init__ import register as 新窗口按钮_register
from.新窗口按钮.plugin.__init__ import unregister as 新窗口按钮_unregister

from.监视材质贴图重名.plugin.__init__ import register as 监视材质贴图重名_register
from.监视材质贴图重名.plugin.__init__ import unregister as 监视材质贴图重名_unregister

from.清理按钮.plugin.__init__ import register as 清理按钮_register
from.清理按钮.plugin.__init__ import unregister as 清理按钮_unregister

from.吸附放置按钮.plugin.__init__ import register as 吸附放置按钮_register
from.吸附放置按钮.plugin.__init__ import unregister as 吸附放置按钮_unregister

from.语言切换按钮.plugin.__init__ import register as 语言切换按钮_register
from.语言切换按钮.plugin.__init__ import unregister as 语言切换按钮_unregister

from.打开质面板按钮.plugin.__init__ import register as 打开质面板按钮_register
from.打开质面板按钮.plugin.__init__ import unregister as 打开质面板按钮_unregister

def register():
    大纲操作按钮_register()
    行走模式按钮_register()
    新窗口按钮_register()    
    监视材质贴图重名_register()
    清理按钮_register()
    吸附放置按钮_register()    
    语言切换按钮_register()
    打开质面板按钮_register()


def unregister(): 
    大纲操作按钮_unregister()
    行走模式按钮_unregister()
    新窗口按钮_unregister()    
    监视材质贴图重名_unregister()
    清理按钮_unregister()
    吸附放置按钮_unregister()
    语言切换按钮_unregister()
    打开质面板按钮_unregister()
