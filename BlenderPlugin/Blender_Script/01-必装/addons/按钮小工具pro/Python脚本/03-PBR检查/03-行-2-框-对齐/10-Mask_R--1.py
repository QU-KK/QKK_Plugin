import bpy
#设置PBR通道
bpy.context.scene.view_settings.view_transform = 'Standard'
for mat in bpy.data.materials:
    nodes = mat.node_tree.nodes.get('Shader')
    if nodes:
        data = mat.node_tree.nodes["Shader"].inputs.get('PBR通道')
        if data:
            mat.node_tree.nodes["Shader"].inputs['PBR通道'].default_value = 'Mask_R'
        else:
            mat.node_tree.nodes["Shader"].inputs[1].default_value = 'Mask_R'