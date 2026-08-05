import bpy
# 切换为物体模式
# 判读是否再物体模式中
if bpy.context.mode != 'OBJECT':  
    # 恢复隐藏项
    bpy.ops.mesh.reveal('INVOKE_DEFAULT', select=False)
    # 物体模式
    bpy.ops.object.mode_set(mode='OBJECT')