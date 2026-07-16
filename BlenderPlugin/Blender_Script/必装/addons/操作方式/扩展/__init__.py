from.Blender互导Maya_Max.Blender互导Maya_Max_py import register as Blender互导Maya_Max_register
from.Blender互导Maya_Max.Blender互导Maya_Max_py import unregister as Blender互导Maya_Max_unregister

from.监视材质贴图重名.监视材质贴图重名_py import register as 监视材质贴图重名_register
from.监视材质贴图重名.监视材质贴图重名_py import unregister as 监视材质贴图重名_unregister

def register():
    Blender互导Maya_Max_register()
    监视材质贴图重名_register()

def unregister(): 
    Blender互导Maya_Max_unregister()
    监视材质贴图重名_unregister()