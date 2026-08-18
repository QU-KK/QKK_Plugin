import bpy
#设置PBR通道
bpy.context.scene.view_settings.view_transform = 'ACES 2.0'

for mat in bpy.data.materials:
    nodes = mat.node_tree.nodes.get('Shader')
    if nodes:
        mat.node_tree.nodes["Shader"].inputs['PBR通道    '].default_value = 'PBR'