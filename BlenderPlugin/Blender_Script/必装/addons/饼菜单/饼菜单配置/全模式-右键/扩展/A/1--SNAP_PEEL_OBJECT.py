import bpy
# 合并模型
for obj in bpy.context.selected_objects:
    bpy.context.view_layer.objects.active = obj

bpy.ops.object.join()