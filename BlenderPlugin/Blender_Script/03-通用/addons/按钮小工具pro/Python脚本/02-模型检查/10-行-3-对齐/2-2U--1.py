import bpy
# 获取材质
Mat = bpy.data.materials.get('.UV棋盘格')
if Mat:
    UV = '2U'
    # 设置参数
    Node = Mat.node_tree
    Node.nodes['UV Map'].uv_map = UV



for obj in bpy.context.blend_data.objects:
    if obj.type == 'MESH':    
        # 遍历该对象的所有 UV 通道（按通道顺序索引）
        for index, uv_layer in enumerate(obj.data.uv_layers):
            # 生成新的名称，例如：1U, 2U, 3U...
            new_name = f"{index + 1}U"
            # 修改 UV 通道名称
            uv_layer.name = new_name
print("UV通道名称已重命名完成！")