import bpy
#隐藏投影
for obj in bpy.data.objects:
    if '_COL' in obj.name:
        obj.hide_set(True)