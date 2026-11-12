import bpy

# 设置对应贴图精度
node = bpy.data.node_groups.get(".UV像素密度可视化")
if node:
    node.nodes['贴图尺寸'].integer = 1024
