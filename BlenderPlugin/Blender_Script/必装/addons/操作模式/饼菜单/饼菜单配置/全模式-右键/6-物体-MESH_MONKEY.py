import bpy
# 切换为物体模式
selected = list(bpy.context.selected_objects)
if not selected:
    print("没有选中任何物体")
else:
    bpy.ops.object.mode_set(mode='OBJECT')