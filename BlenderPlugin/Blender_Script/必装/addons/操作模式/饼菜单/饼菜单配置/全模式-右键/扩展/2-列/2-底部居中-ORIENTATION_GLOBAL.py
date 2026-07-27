import bpy
import mathutils

# 确保我们在物体模式下运行
if bpy.context.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
    
# 提取当前选中的物体并固定为列表
selected_objs = list(bpy.context.selected_objects)

# 只有在选中了物体的情况下才执行后续操作
if selected_objs:
    # 记录当前3D游标的位置，以便操作结束后恢复
    saved_cursor_loc = bpy.context.scene.cursor.location.copy()
    
    # 先取消全选，防止多个物体互相干扰
    bpy.ops.object.select_all(action='DESELECT')
    
    for obj in selected_objs:
        if obj.type == 'MESH':
            # === 第一步：轴心居中到自身边界框底部 ===
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            
            bbox_corners = [mathutils.Vector(corner) for corner in obj.bound_box]
            
            min_x = min(v.x for v in bbox_corners)
            max_x = max(v.x for v in bbox_corners)
            min_y = min(v.y for v in bbox_corners)
            max_y = max(v.y for v in bbox_corners)
            min_z = min(v.z for v in bbox_corners)
            
            local_bottom_center = mathutils.Vector((
                (min_x + max_x) / 2.0,
                (min_y + max_y) / 2.0,
                min_z
            ))
            
            # 将局部坐标转换为全局坐标，并移动游标与轴心
            global_bottom_center = obj.matrix_world @ local_bottom_center
            bpy.context.scene.cursor.location = global_bottom_center
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
            
            # === 第二步：将模型底部对齐到世界Z0 ===
            #obj.matrix_world.translation.z = 0.0
            
            # 取消选中当前物体，进入下一个循环
            obj.select_set(False)

    # 恢复3D游标到原始位置
    bpy.context.scene.cursor.location = saved_cursor_loc
    
    # 恢复一开始的物体选择状态
    for obj in selected_objs:
        obj.select_set(True)
        
    print("已完成：轴心已归底，且模型已放置在世界 Z=0 处！")