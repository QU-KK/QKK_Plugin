import bpy

for obj in bpy.context.selected_objects:
    if obj.type != 'MESH':
        continue
    # 使用 color_attributes 访问所有颜色层（包括顶点色）
    color_attrs = obj.data.color_attributes
    # 收集所有需要删除的层名称，避免迭代时修改集合
    layers_to_remove = [attr.name for attr in color_attrs]
    for name in layers_to_remove:
        color_attrs.remove(color_attrs[name])