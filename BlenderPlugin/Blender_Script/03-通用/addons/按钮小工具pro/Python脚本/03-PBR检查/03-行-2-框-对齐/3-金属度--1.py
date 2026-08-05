import bpy
#设置PBR通道
bpy.context.scene.view_settings.view_transform = 'Standard'
for mat in bpy.data.materials:
    nodes = mat.node_tree.nodes.get('Shader')
    if nodes:
        mat.node_tree.nodes["Shader"].inputs[1].default_value = '金属度'