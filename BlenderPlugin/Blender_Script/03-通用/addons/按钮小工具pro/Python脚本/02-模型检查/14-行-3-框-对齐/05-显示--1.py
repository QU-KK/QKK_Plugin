import bpy

# 设置对应贴图精度
node = bpy.data.node_groups.get(".UV像素密度可视化")
if node:
    node.nodes["精度显示模式"].inputs[0].default_value = '全部显示'