from.Ctrl右键.Ctrl右键_py import register as Ctrl右键_register
from.Ctrl右键.Ctrl右键_py import unregister as Ctrl右键_unregister

from.Shift右键.Shift右键_py import register as Shift右键_register
from.Shift右键.Shift右键_py import unregister as Shift右键_unregister

from.空格.空格_py import register as 空格_register
from.空格.空格_py import unregister as 空格_unregister

from.右键.右键_py import register as 右键_register
from.右键.右键_py import unregister as 右键_unregister


def register():
    Ctrl右键_register()
    Shift右键_register()
    空格_register()
    右键_register()


def unregister(): 
    Ctrl右键_unregister()
    Shift右键_unregister()
    空格_unregister()
    右键_unregister()