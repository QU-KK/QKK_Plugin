import bpy
# 获取材质
Mat = bpy.data.materials.get('.UV棋盘格')
if Mat == None:
    # 创建材质
    Mat = bpy.context.blend_data.materials.new('.UV棋盘格')
    # 创建节点
    node_tree = Mat.node_tree
    nodes = node_tree.nodes
    links = node_tree.links
    # 清理节点
    nodes.clear()
    # 创建节点
    # 创建 "UV 贴图" (UV Map) 节点
    node_uv = nodes.new(type='ShaderNodeUVMap')
    # 创建 "棋盘格纹理" (Checker Texture) 节点
    node_checker = nodes.new(type='ShaderNodeTexChecker')
    node_checker.name = 'Checker Texture'
    # 创建 "材质输出" (Material Output) 节点
    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    # 连接节点
    # 连接: UV 贴图 的 "UV" -> 棋盘格纹理 的 "矢量" (Vector)
    links.new(node_uv.outputs['UV'], node_checker.inputs['Vector'])
    # 连接: 棋盘格纹理 的 "颜色" (Color) -> 材质输出 的 "表(曲)面" (Surface)
    links.new(node_checker.outputs['Color'], node_output.inputs['Surface'])

# 覆盖全局材质
bpy.context.view_layer.material_override = Mat

# 参数变量
Density = 64
#UV = '1U'
# 设置参数
Node = Mat.node_tree
#Node.nodes['UV Map'].uv_map = UV
Node.nodes['Checker Texture'].inputs['Scale'].default_value = Density
Node.nodes['Checker Texture'].inputs['Color1'].default_value = (0.033,0.033,0.033,1)
Node.nodes['Checker Texture'].inputs['Color2'].default_value = (0.448,0.448,0.448,1)

# 设置3D显示模式
bpy.context.space_data.shading.type = 'MATERIAL'

# 重命名UV
for obj in bpy.context.blend_data.objects:
    if obj.type == 'MESH':    
        # 遍历该对象的所有 UV 通道（按通道顺序索引）
        for index, uv_layer in enumerate(obj.data.uv_layers):
            # 生成新的名称，例如：1U, 2U, 3U...
            new_name = f"{index + 1}U"
            # 修改 UV 通道名称
            uv_layer.name = new_name
print("UV通道名称已重命名完成！")
