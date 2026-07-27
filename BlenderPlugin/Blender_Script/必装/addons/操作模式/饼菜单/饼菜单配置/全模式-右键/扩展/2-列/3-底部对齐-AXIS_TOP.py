import bpy
import mathutils

# 确保我们在物体模式下运行
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
    
# 提取当前选中的 MESH 物体
selected_objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

if selected_objs:
    # 刷新视图层，确保获取到的世界矩阵(matrix_world)是最新状态
    bpy.context.view_layer.update()
    
    for obj in selected_objs:
        # 计算包围框8个顶点在【世界坐标系】下的Z轴数值
        global_z_coords = [(obj.matrix_world @ mathutils.Vector(corner)).z for corner in obj.bound_box]
        
        # 找到当前模型包围框底部的全局 Z 坐标最低点
        min_z = min(global_z_coords)
        
        # 仅修改模型的全局Z轴位置，将底部对齐到 Z=0
        # 无论物体原本在地下(负值)还是在半空(正值)，减去 min_z 就能刚好归零
        obj.matrix_world.translation.z -= min_z

    print("已完成：模型底部已对齐到世界 Z=0，轴心保持原样不动！")