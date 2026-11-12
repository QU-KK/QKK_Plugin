import bpy
#设置PBR通道
#bpy.context.scene.view_settings.view_transform = 'ACES 2.0'
bpy.context.scene.view_settings.view_transform = 'Khronos PBR Neutral'

bpy.context.scene.render.filter_size = 0

for mat in bpy.data.materials:
    nodes = mat.node_tree.nodes.get('Shader')
    if nodes:
        data = mat.node_tree.nodes["Shader"].inputs.get('PBR通道')
        if data:
            mat.node_tree.nodes["Shader"].inputs['PBR通道'].default_value = 'PBR'
        else:
            mat.node_tree.nodes["Shader"].inputs[1].default_value = 'PBR'



#恢复混合
for mat in bpy.data.materials:
    nodes = mat.node_tree.nodes.get('Shader')
    if nodes:
        data = mat.node_tree.nodes["Shader"].inputs.get('混合独显')
        if data:
            mat.node_tree.nodes["Shader"].inputs['混合独显'].default_value = (1,1,1)
        else:
            mat.node_tree.nodes["Shader"].inputs[2].default_value = (1,1,1) 