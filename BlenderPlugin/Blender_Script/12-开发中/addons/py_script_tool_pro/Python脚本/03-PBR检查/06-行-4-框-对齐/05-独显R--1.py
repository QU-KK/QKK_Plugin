import bpy
#独显R
for mat in bpy.data.materials:
    nodes = mat.node_tree.nodes.get('Shader')
    if nodes:
        data = mat.node_tree.nodes["Shader"].inputs.get('混合独显')
        if data:
            mat.node_tree.nodes["Shader"].inputs['混合独显'].default_value = (1,0,0)
        else:
            mat.node_tree.nodes["Shader"].inputs[2].default_value = (1,0,0)