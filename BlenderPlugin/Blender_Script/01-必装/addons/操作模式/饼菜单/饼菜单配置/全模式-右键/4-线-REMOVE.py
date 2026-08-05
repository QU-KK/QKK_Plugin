import bpy
# 切换为线模式
if bpy.context.active_object != None:
    # 进入编辑模式
    bpy.ops.object.mode_set(mode='EDIT')
    # 设置为面模式
    bpy.ops.mesh.select_mode(type='EDGE')
    # 设置为选择模式
    bpy.ops.wm.tool_set_by_id(name='builtin.select_box')