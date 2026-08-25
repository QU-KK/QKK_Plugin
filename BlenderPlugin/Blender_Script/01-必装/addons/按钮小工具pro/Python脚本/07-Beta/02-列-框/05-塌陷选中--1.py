import bpy

# 处理实例
print('开始处理实例')
bpy.ops.object.duplicates_make_real()
print('实例处理完成')



selected_objects = bpy.context.selected_objects


# 直接转换为网格
print('开始处理修改器')
bpy.ops.object.convert(target='MESH')
print('修改器处理完成')


# 刷新视图
#bpy.context.view_layer.update()
# 直接转换为网格
#bpy.ops.object.duplicates_make_real(use_base_parent=True)


# 删除场景中的所有相机和灯光物体
print('开始删除灯光、相机')
for obj in selected_objects:
    if obj.type in {'CAMERA', '  '}:
        bpy.data.objects.remove(obj, do_unlink=True)
print('灯光、相机  删除完毕')
#清理
#bpy.ops.outliner.orphans_purge()


def move_selected_to_new_top_collection(collection_name="My_New_Collection"):
    # 获取当前选中的物体
    selected_objects = bpy.context.selected_objects
    
    # 如果没有选中任何物体，直接退出
    if not selected_objects:
        print("未选中任何物体。请先选择要移动的物体！")
        return
    
    # 1. 创建一个新的集合
    new_collection = bpy.data.collections.new(collection_name)
    
    # 2. 将新集合链接到顶层集合（Scene Collection）
    bpy.context.scene.collection.children.link(new_collection)
    
    # 3. 遍历所有选中的物体进行移动
    for obj in selected_objects:
        # 将物体链接到新创建的集合
        new_collection.objects.link(obj)
        
        # 遍历物体当前所在的其他集合，并将其从中移除（取消链接）
        for old_collection in obj.users_collection:
            if old_collection != new_collection:
                old_collection.objects.unlink(obj)

    print(f"成功将 {len(selected_objects)} 个物体移动到顶层集合 '{collection_name}' 中。")

# 执行函数，可以自行修改新集合的名称
move_selected_to_new_top_collection("新建顶层集合")






# 刷新视图
#bpy.context.view_layer.update() 
print('！！！全部完成！！！')

