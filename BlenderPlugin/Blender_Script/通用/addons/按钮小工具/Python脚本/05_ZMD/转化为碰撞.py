import bpy

# 获取当前所有选中的物体
selected_objects = bpy.context.selected_objects

# 取消当前的所有选中状态，方便后续操作
bpy.ops.object.select_all(action='DESELECT')

for obj in selected_objects:
    # 检查物体的名称是否以 _lod0 结尾（或者包含 _lod0）
    if "_lod0" in obj.name:
        # 选择当前循环到的物体
        obj.select_set(True)
        # 设置为当前活跃物体（Active Object）
        bpy.context.view_layer.objects.active = obj
        # 清理空材质槽
        bpy.ops.object.material_slot_remove_unused()
        
        # 复制物体（完全复制数据）
        bpy.ops.object.duplicate(linked=False)
        
        # 复制出来的物体会自动变成当前的活跃物体
        new_obj = bpy.context.active_object
        
        # 替换名称中的 _lod0 为 _COL1_UM01
        # 注意：Blender 复制时可能会自动加 .001，这里顺便把 .001 去掉
        base_name = new_obj.name.replace(".001", "")
        new_name = base_name.replace("_lod0", "_COL1_UM01")        
        new_obj.name = new_name
        
        # 清理UV
        for i in new_obj.data.uv_layers:
            new_obj.data.uv_layers.remove(new_obj.data.uv_layers[0])
        # 清理顶点色
        for i in new_obj.data.vertex_colors:
            new_obj.data.vertex_colors.remove(new_obj.data.vertex_colors[0])
        # 清理材质
        for i in new_obj.material_slots:
            bpy.ops.object.material_slot_remove()
        # 增加材质
        bpy.ops.object.material_slot_add()    
            
        
        # 取消选择当前新物体，为下一次循环做准备
        new_obj.select_set(False)
        
        print(f"已成功复制并重命名: {obj.name} -> {new_obj.name}")
    else:
        print(f"跳过物体（不包含 _lod0）: {obj.name}")

print("批量复制与重命名完成！")