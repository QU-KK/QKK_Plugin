import bpy

# 获取当前所有选中的物体
selected_objects = bpy.context.selected_objects

# 定义需要删除的物体类型
# 'CAMERA' 代表相机, 'EMPTY' 代表空物体, 'LIGHT' 代表灯光
target_types = {'CAMERA', 'EMPTY', 'LIGHT'}

# 过滤出符合条件的物体
objects_to_delete = [obj for obj in selected_objects if obj.type in target_types]

# 遍历并删除这些物体
for obj in objects_to_delete:
    # 确保物体存在于当前集合中，避免重复删除报错
    if obj.name in bpy.context.scene.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

print(f"删除完成！共删除了 {len(objects_to_delete)} 个物体。")