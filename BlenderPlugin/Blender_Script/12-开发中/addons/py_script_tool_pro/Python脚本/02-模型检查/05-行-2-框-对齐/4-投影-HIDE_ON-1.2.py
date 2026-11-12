import bpy

name = ".投影可视化"
#隐藏投影
for obj in bpy.data.objects:
    if '_shadowProxy' in obj.name:
        obj.hide_set(True)
        obj.show_wire = False

        # 移除修改器
        if name in obj.modifiers:
            obj.modifiers.remove(modifier = obj.modifiers[name])


# 移除节点
node = bpy.data.node_groups.get(name)
if node:
    bpy.context.blend_data.node_groups.remove(tree = node)

# 移除材质
bpy.context.view_layer.material_override = None
Mat = bpy.data.materials.get(name)
if Mat:
    bpy.context.blend_data.materials.remove(Mat)

# 清理
bpy.ops.outliner.orphans_purge()