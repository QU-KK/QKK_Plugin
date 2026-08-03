import bpy
old_str = '_1_'
new_str = '+1_'

# 将所有名称中包含 '_1_' 的材质提取到一个列表中，避免在遍历时修改名称导致异常
materials_to_process = [mat for mat in bpy.data.materials if '_1_' in mat.name]

# 记录操作次数
renamed_count = 0
replaced_count = 0

for mat in materials_to_process:
    old_name = mat.name
    # 生成目标名称
    target_name = old_name.replace('_1_', '+1_')
    
    # 检查目标名称是否已经存在于材质库中
    if target_name not in bpy.data.materials:
        # 情况 1：不重名，直接改名
        mat.name = target_name
        print(f"已重命名: {old_name} -> {target_name}")
        renamed_count += 1
    else:
        # 情况 2：发生重名，获取已经存在的目标材质
        target_mat = bpy.data.materials[target_name]
        print(f"发现重名: [{target_name}] 已存在。正在将使用 [{old_name}] 的模型替换为目标材质...")
        
        # 遍历场景中的所有物体
        for obj in bpy.data.objects:
            # 只有支持材质的物体（网格、曲线、字体等）才有 material_slots 属性
            if hasattr(obj, 'material_slots'):
                for slot in obj.material_slots:
                    # 如果该物体的材质槽正在使用我们要被替换的材质
                    if slot.material == mat:
                        slot.material = target_mat
                        print(f"  - 物体 [{obj.name}] 的材质已被替换")
        
        replaced_count += 1

print("-" * 30)
print(f"操作完成！")
print(f"直接重命名的材质数量: {renamed_count}")
print(f"因重名而重新分配的材质数量: {replaced_count}")