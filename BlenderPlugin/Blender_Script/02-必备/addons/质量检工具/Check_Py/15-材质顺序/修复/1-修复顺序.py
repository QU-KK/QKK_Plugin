import bpy

def align_lod_materials_strict():
    # 1. 获取选中的网格物体，筛选名称中包含 '_lod0' 的模型
    selected_objs = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    lod0_list = [obj for obj in selected_objs if '_lod0' in obj.name.lower()]

    if not lod0_list:
        print("提示：当前选中的物体中未找到包含 '_lod0' 的网格模型。")
        return

    aligned_count = 0

    # 2. 遍历 lod0 模型
    for lod0_obj in lod0_list:
        lod0_slots = lod0_obj.material_slots
        lod0_mats = [slot.material for slot in lod0_slots]
        lod0_slot_count = len(lod0_slots)
        
        desired_mat_to_index = {mat: idx for idx, mat in enumerate(lod0_mats)}

        is_lowercase = '_lod0' in lod0_obj.name
        source_tag = '_lod0' if is_lowercase else '_LOD0'

        # 3. 查找并处理 lod1 ~ lod6
        for i in range(1, 7):
            target_tag = f"_lod{i}" if is_lowercase else f"_LOD{i}"
            target_name = lod0_obj.name.replace(source_tag, target_tag)
            target_obj = bpy.data.objects.get(target_name)

            if target_obj and target_obj.type == 'MESH':
                # 材质槽数量校验：数量不一致则直接跳过
                if len(target_obj.material_slots) != lod0_slot_count:
                    print(f"[跳过] {target_name}: 材质槽数量 ({len(target_obj.material_slots)}) 与 lod0 ({lod0_slot_count}) 不一致。")
                    continue

                mesh = target_obj.data
                current_mats = [slot.material for slot in target_obj.material_slots]

                # 构建【旧槽位索引 -> 新槽位索引】映射
                old_to_new_index = {}
                for old_idx, mat in enumerate(current_mats):
                    if mat in desired_mat_to_index:
                        old_to_new_index[old_idx] = desired_mat_to_index[mat]
                    else:
                        old_to_new_index[old_idx] = old_idx

                # 重映射多边形面的 material_index，确保材质外观不变
                for poly in mesh.polygons:
                    if poly.material_index in old_to_new_index:
                        poly.material_index = old_to_new_index[poly.material_index]

                # 按 lod0 物理顺序更新材质槽
                for idx, mat in enumerate(lod0_mats):
                    target_obj.material_slots[idx].material = mat

                aligned_count += 1
                print(f"[成功] 已同步材质槽顺序: {target_obj.name}")

    print(f"处理完成，共更新 {aligned_count} 个 LOD 模型的材质排序。")

# 执行脚本
align_lod_materials_strict()