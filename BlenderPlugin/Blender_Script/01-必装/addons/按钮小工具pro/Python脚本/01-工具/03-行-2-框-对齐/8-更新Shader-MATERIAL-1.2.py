import bpy
# 改名
NodeTree = bpy.data.node_groups['ZMD_Lit_Two']
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


print("Shader更新完成！")