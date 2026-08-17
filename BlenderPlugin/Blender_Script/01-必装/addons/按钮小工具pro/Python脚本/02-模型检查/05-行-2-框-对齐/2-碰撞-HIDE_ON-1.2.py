import bpy
#隐藏碰撞
for obj in bpy.data.objects:
    if '_COL' in obj.name:
        obj.hide_set(True)