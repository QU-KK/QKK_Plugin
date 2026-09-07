import bpy

# 获取当前所有被选中的物体
selected_objects = bpy.context.selected_objects

# 遍历这些选中的物体
for obj in selected_objects:
    # 判断物体名称中是否不包含 '_lod0'
    if '_lod0' not in obj.name:
        # 从 Blender 数据中彻底删除该物体（do_unlink=True 会自动将其从场景中解除链接）
        bpy.data.objects.remove(obj, do_unlink=True)
        
print("清理完成！")