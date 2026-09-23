import bpy

old_str = '_1_'
new_str = '+1_'

def replace_names(old_str, new_str):
    # 获取当前选中的所有物体
    selected_objects = bpy.context.selected_objects
    
    if not selected_objects:
        print("请先在场景中选中至少一个物体！")
        return

    for obj in selected_objects:
        # 替换物体名称
        if old_str in obj.name:
            old_obj_name = obj.name
            obj.name = obj.name.replace(old_str, new_str)
            print(f"物体改名: {old_obj_name} -> {obj.name}")

replace_names(old_str,new_str)