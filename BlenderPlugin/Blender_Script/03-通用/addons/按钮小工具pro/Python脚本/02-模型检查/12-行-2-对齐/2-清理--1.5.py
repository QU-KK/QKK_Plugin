import bpy
name = ".UV像素密度可视化"

# 移除修改器
for obj in bpy.data.objects:
    if '_lod' in obj.name:
        if name in obj.modifiers:
            obj.modifiers.remove(modifier = obj.modifiers[name])

# 移除节点
node = bpy.data.node_groups.get(name)
if node:
    bpy.context.blend_data.node_groups.remove(tree = node)


# 移除材质
bpy.context.view_layer.material_override = None
Mat = bpy.data.materials.get('.UV像素密度')
if Mat:
    bpy.context.blend_data.materials.remove(Mat)

# 清理
bpy.ops.outliner.orphans_purge()