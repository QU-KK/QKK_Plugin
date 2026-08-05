import bpy

#清空父子集合
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
Empty_list = []
for obj in bpy.context.selected_objects:
    if obj.type == 'EMPTY':
        Empty_list.append(obj)

progress = 0
for obj in Empty_list:
    if obj.type == 'EMPTY':
        bpy.data.objects.remove(object=obj, do_unlink=True, do_id_user=True, do_ui_user=True)
    progress += 1
    print(progress,'/',len(Empty_list))

def group_objects_by_lod0_prefix():
    # 获取当前选中的所有物体
    selected_objs = bpy.context.selected_objects
    
    # 用来记录已经处理过的基础名称，避免多选时重复处理
    processed_bases = set()

    for obj in selected_objs:
        # 筛选名称中包含 '_lod0' 的选中物体
        if '_lod0' in obj.name:
            # 提取 '_lod0' 前面的基础名称
            # 例如: "Obj_A_lod0" 会被提取为 "Obj_A"
            base_name = obj.name.split('_lod0')[0]
            
            # 如果已经处理过该前缀，则跳过
            if base_name in processed_bases:
                continue
            processed_bases.add(base_name)
            
            # 1. 检查是否已存在同名集合，如果没有则新建并链接到主场景
            if base_name in bpy.data.collections:
                target_collection = bpy.data.collections[base_name]
            else:
                target_collection = bpy.data.collections.new(base_name)
                bpy.context.scene.collection.children.link(target_collection)
            
            # 2. 遍历文件中的所有物体，查找以该基础名称开头的所有物体
            for scene_obj in bpy.data.objects:
                if scene_obj.name.startswith(base_name):
                    
                    # 将匹配到的物体链接到目标集合
                    if target_collection.name not in [c.name for c in scene_obj.users_collection]:
                        target_collection.objects.link(scene_obj)
                    
                    # 从其他原有集合中取消链接，实现“移动”效果
                    # 注意：使用 list() 包装以防止在遍历时因为打断集合关系而报错
                    for old_col in list(scene_obj.users_collection):
                        if old_col != target_collection:
                            old_col.objects.unlink(scene_obj)
                            
    print("物体整理完成！")

# 运行函数
group_objects_by_lod0_prefix()