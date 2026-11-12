from.快捷键管理.plugin.__init__ import register as 快捷键管理_register
from.快捷键管理.plugin.__init__ import unregister as 快捷键管理_unregister

from.快捷键预设.plugin.__init__ import register as 快捷键预设_register
from.快捷键预设.plugin.__init__ import unregister as 快捷键预设_unregister


def register():
    快捷键管理_register
    快捷键预设_register


def unregister(): 
    快捷键管理_unregister
    快捷键预设_unregister