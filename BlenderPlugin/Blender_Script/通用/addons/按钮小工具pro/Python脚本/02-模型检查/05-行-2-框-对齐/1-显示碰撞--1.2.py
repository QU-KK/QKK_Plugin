import bpy
#显示碰撞
for obj in bpy.data.objects:
    if '_COL' in obj.name:
        obj.hide_set(False)