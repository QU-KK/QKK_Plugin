import bpy

# 设置对应贴图精度
node = bpy.data.node_groups.get(".UV像素密度可视化")
if node:
    # 字体大小
    node.nodes['字符尺寸'].outputs[0].default_value = node.nodes['字符尺寸'].outputs[0].default_value - node.nodes['字符尺寸'].outputs[0].default_value/4



