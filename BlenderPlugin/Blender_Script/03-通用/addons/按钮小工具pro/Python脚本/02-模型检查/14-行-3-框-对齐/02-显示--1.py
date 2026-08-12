import bpy
# 新建UV像素密度材质
# 获取材质
Mat_Name = '.UV像素密度'
Mat = bpy.data.materials.get(Mat_Name)
if Mat == None:
    # 创建材质
    Mat = bpy.context.blend_data.materials.new(Mat_Name)
    # 创建节点
    node_tree = Mat.node_tree
    nodes = node_tree.nodes
    links = node_tree.links
    # 清理节点
    nodes.clear()

    # 创建属性节点
    node_attribute = nodes.new(type='ShaderNodeAttribute')
    # 创建材质输出节点
    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    # 连接
    links.new(node_attribute.outputs['Color'], node_output.inputs['Surface'])


# 覆盖全局材质
bpy.context.view_layer.material_override = Mat

# 设置参数
Node = Mat.node_tree
Node.nodes['Attribute'].attribute_name = 'UV纹理密度'


bpy.context.space_data.shading.type = 'MATERIAL'