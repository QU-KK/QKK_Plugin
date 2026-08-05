import bpy
# 切换为线模式
selected = list(bpy.context.selected_objects)
if not selected:
    print("没有选中任何物体")
else:
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')
    bpy.ops.wm.tool_set_by_id(name='builtin.select_box')