import bpy

old_str = '_1_'
new_str = '+1_'

def replace_names(old_str, new_str):
    # 获取当前选中的所有物体
    selected_objects = bpy.context.selected_objects
    
    if not selected_objects:
        print("请先在场景中选中至少一个物体！")
        return

    # 用于记录已被修改过材质的集合，防止同一个材质被重复处理
    processed_materials = set()

    for obj in selected_objects:
        # 1. 替换物体名称
        if old_str in obj.name:
            old_obj_name = obj.name
            obj.name = obj.name.replace(old_str, new_str)
            print(f"物体改名: {old_obj_name} -> {obj.name}")
            
        # 2. 遍历物体关联的材质槽
        if obj.material_slots:
            for slot in obj.material_slots:
                mat = slot.material
                # 确保材质槽里确实有材质，且该材质还没被处理过
                if mat and mat not in processed_materials:
                    processed_materials.add(mat)
                    
                    if old_str in mat.name:
                        old_mat_name = mat.name
                        mat.name = mat.name.replace(old_str, new_str)
                        print(f"  材质改名: {old_mat_name} -> {mat.name}")
replace_names(old_str,new_str)