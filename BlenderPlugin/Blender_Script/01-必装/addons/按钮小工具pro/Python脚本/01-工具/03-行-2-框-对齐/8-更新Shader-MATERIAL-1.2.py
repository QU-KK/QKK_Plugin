import bpy
import os
# 改名
NodeTree = bpy.data.node_groups.get('ZMD_Lit_Two')
if NodeTree:
    NodeTree.name = 'ZMD_Lit_Two.old'

# 追加外部材质并修正节点组引用
Shader_Name = 'ZMD_Lit_Two'
Dir_path = os.path.dirname(os.path.abspath(__file__))
Blender_Path = Dir_path.split('Blender_Script')[0]+'Blender_Shader\\ZMD_Lit_Two.blend\\NodeTree\\' 
bpy.ops.wm.append(directory=Blender_Path, filename=Shader_Name, link=False)

# 获取最新节点组
NodeTree = bpy.data.node_groups['ZMD_Lit_Two']

# 更新Shader
for mat in bpy.data.materials:
    Node = mat.node_tree.nodes.get('Shader')
    if Node:
        Node.node_tree = NodeTree

bpy.ops.outliner.orphans_purge()

print("Shader更新完成！")




# 设置模型UV名称
for obj in bpy.context.blend_data.objects:
    if obj.type == 'MESH':
        
        # 激活UV 0为渲染输出
        if len(obj.data.uv_layers) > 0:
            obj.data.uv_layers.active_index = 0
            obj.data.uv_layers.active_render_index = 0

        # 遍历该对象的所有 UV 通道（按通道顺序索引）
        for index, uv_layer in enumerate(obj.data.uv_layers):
            # 生成新的名称，例如：1U, 2U, 3U...
            new_name = f"{index + 1}U"
            # 修改 UV 通道名称
            uv_layer.name = new_name
print("UV通道名称已重命名完成！")