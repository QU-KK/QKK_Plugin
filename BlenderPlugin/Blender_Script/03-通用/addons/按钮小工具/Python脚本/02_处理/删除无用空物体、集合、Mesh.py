import bpy

# 删除不可见集合
stack = [bpy.context.layer_collection]
while stack:
    lc = stack.pop()    
    stack.extend(lc.children)
    print(lc.name)
    if lc.name != 'Scene Collection':
        collection = bpy.context.blend_data.collections[lc.name]
        if lc.exclude ==True or lc.hide_viewport == True or collection.hide_viewport == True:
            bpy.context.blend_data.collections.remove(collection=collection, do_unlink=True)


# 删除不包含MESH的空物体
for obj in bpy.data.objects:
    if obj.type == 'EMPTY':
        if not any(child.type == 'MESH' for child in obj.children_recursive):
            bpy.data.objects.remove(obj, do_unlink=True)


# 删除隐藏的MESH
for obj in bpy.context.blend_data.objects:
    if obj.type == 'MESH':
        if len(obj.children) == 0:
            if obj.hide_get() == True or obj.hide_viewport == True:
                bpy.context.blend_data.objects.remove(object=obj, do_unlink=True)

# 清理残留
bpy.ops.outliner.orphans_purge()