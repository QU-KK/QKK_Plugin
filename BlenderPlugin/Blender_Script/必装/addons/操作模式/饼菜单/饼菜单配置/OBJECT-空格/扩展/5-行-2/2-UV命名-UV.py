import bpy

# 获取当前所有选中的网格对象
selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

if not selected_objects:
    print("未选中任何网格对象(Mesh)！")
else:
    # 遍历每个选中的对象
    for obj in selected_objects:
        print(f"正在处理对象: {obj.name}")
        
        # 遍历该对象的所有 UV 通道（按通道顺序索引）
        for index, uv_layer in enumerate(obj.data.uv_layers):
            # 生成新的名称，例如：1U, 2U, 3U...
            new_name = f"{index + 1}U"
            
            # 修改 UV 通道名称
            uv_layer.name = new_name
            
    print("所有选中对象的 UV 通道名称已重命名完成！")