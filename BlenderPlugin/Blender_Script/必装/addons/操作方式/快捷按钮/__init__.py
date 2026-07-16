from.大纲操作按钮.大纲操作按钮_py import register as 大纲操作按钮_register
from.大纲操作按钮.大纲操作按钮_py import unregister as 大纲操作按钮_unregister

from.偏好操作设置按钮.偏好操作设置按钮_py import register as 偏好操作设置按钮_register
from.偏好操作设置按钮.偏好操作设置按钮_py import unregister as 偏好操作设置按钮_unregister

from.行走模式按钮.行走模式按钮_py import register as 行走模式按钮_register
from.行走模式按钮.行走模式按钮_py import unregister as 行走模式按钮_unregister

from.清理按钮.清理按钮_py import register as 清理按钮_register
from.清理按钮.清理按钮_py import unregister as 清理按钮_unregister

from.吸附放置按钮.吸附放置按钮_py import register as 吸附放置按钮_register
from.吸附放置按钮.吸附放置按钮_py import unregister as 吸附放置按钮_unregister

from.新窗口按钮.新窗口按钮_py import register as 新窗口按钮_register
from.新窗口按钮.新窗口按钮_py import unregister as 新窗口按钮_unregister

from.语言切换按钮.语言切换按钮_py import register as 语言切换按钮_register
from.语言切换按钮.语言切换按钮_py import unregister as 语言切换按钮_unregister

from.快捷键管理按钮.快捷键管理按钮_py import register as 快捷键管理按钮_register
from.快捷键管理按钮.快捷键管理按钮_py import unregister as 快捷键管理按钮_unregister


def register():
    大纲操作按钮_register()
    偏好操作设置按钮_register()
    行走模式按钮_register()
    清理按钮_register()
    吸附放置按钮_register()
    新窗口按钮_register()
    语言切换按钮_register()
    快捷键管理按钮_register()


def unregister(): 
    大纲操作按钮_unregister()
    偏好操作设置按钮_unregister()
    行走模式按钮_unregister()
    清理按钮_unregister()
    吸附放置按钮_unregister()
    新窗口按钮_unregister()
    语言切换按钮_unregister()
    快捷键管理按钮_unregister()