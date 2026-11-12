import bpy
#lod全显示
data = ['_lod0','_lod1','_lod2','_lod3','_COL','_shadowProxy']
for obj in bpy.data.objects:
    for i in data:
        if i in obj.name:
            obj.hide_set(False)
            obj.show_wire = False



name_list = [".碰撞可视化",".投影可视化",".UV像素密度可视化",".UV棋盘格"]

for name in name_list:

    # 移除修改器
    for obj in bpy.data.objects:
       
        if name in obj.modifiers:
            obj.modifiers.remove(modifier = obj.modifiers[name])

    # 移除节点
    node = bpy.data.node_groups.get(name)
    if node:
        bpy.context.blend_data.node_groups.remove(tree = node)

    # 移除材质
    Mat = bpy.data.materials.get(name)
    if Mat:
        bpy.context.blend_data.materials.remove(Mat)

# 清理
bpy.ops.outliner.orphans_purge()