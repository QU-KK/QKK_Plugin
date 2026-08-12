import bpy
import os

# 获取当前脚本所在目录
dir_path = os.path.dirname(os.path.abspath(__file__))
blend_path = os.path.join(dir_path, "资产", "UV像素密度可视化.blend")

node_name = ".UV像素密度可视化"

node = bpy.data.node_groups.get(node_name)

# 追加
if node:
    print(f"节点 '{node_name}' 已存在，跳过追加")
else:
    bpy.ops.wm.append(directory=blend_path + r'\NodeTree', filename=node_name, link=False)

# 设置修改器
for obj in bpy.data.objects:
    if '_lod' in obj.name:

        if node_name not in obj.modifiers:
            # 添加几何节点修改器
            mod = obj.modifiers.new(name=node_name, type='NODES')
            mod.node_group = bpy.data.node_groups[node_name]




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