import bpy

# ================= 1. 获取或创建“白膜”材质 =================
mat_name = '白膜'
mat = bpy.data.materials.get(mat_name)

if mat is None:
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    
    # 调整新材质的节点参数（白色，高粗糙度）
    if mat.node_tree:
        principled_node = mat.node_tree.nodes.get("Principled BSDF")
        if principled_node:
            principled_node.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            principled_node.inputs['Roughness'].default_value = 0.8

# ================= 2. 收集场景中所有的网格模型 =================
# 提前存入列表以便获取总数
mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
total_objs = len(mesh_objects)

print(f"\n========== 开始执行：共找到 {total_objs} 个网格模型 ==========")

# ================= 3. 遍历模型并打印进度 =================
for index, obj in enumerate(mesh_objects, start=1):
    # 打印实时进度百分比和当前处理的对象名称
    progress_percent = (index / total_objs) * 100
    print(f"进度: [{index}/{total_objs}] ({progress_percent:.1f}%) -> 正在处理: {obj.name}")
    
    # 清空当前模型的所有材质槽
    obj.data.materials.clear()
    
    # 添加 '白膜' 材质，生成唯一的一个材质槽
    obj.data.materials.append(mat)

print("========== 处理完毕！ ==========\n")