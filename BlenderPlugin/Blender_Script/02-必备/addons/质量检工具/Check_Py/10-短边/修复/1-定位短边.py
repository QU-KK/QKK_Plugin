import bpy

# 1. 确保在物体模式下操作（在编辑模式下直接修改 data.edges 会失效）
if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

# 仅获取选中的网格(Mesh)物体
selected_objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

for obj in selected_objects:
    matrix_world = obj.matrix_world
    vertices = obj.data.vertices
    name = obj.name
    short_edge_count = 0
    
    # 2. 依据命名规则确定阈值
    threshold = 0
    if '_lod' in name:
        threshold = 0.001
    elif '_COL' in name or '_shadowProxy' in name:
        threshold = 0.02
    else:
        continue  # 如果名称不包含上述后缀，则跳过该物体
        
    # 3. (可选) 清空该物体当前的所有选择，确保最终只选中短边
    for v in vertices:
        v.select = False
    for edge in obj.data.edges:
        edge.select = False
    for poly in obj.data.polygons:
        poly.select = False
        
    # 4. 遍历并选中短边
    for edge in obj.data.edges:
        v1_idx, v2_idx = edge.vertices
        
        v1_world_co = matrix_world @ vertices[v1_idx].co
        v2_world_co = matrix_world @ vertices[v2_idx].co
        
        edge_length = (v1_world_co - v2_world_co).length
        
        if edge_length < threshold:
            edge.select = True          # 选中边
            vertices[v1_idx].select = True  # 必须同时选中两端的顶点
            vertices[v2_idx].select = True
            short_edge_count += 1
            
    # 5. 更新网格数据，将选择状态写入
    obj.data.update()
    
    print(f"物体 '{name}' 中发现并选中了 {short_edge_count} 条短边。")

# 6. 切换回编辑模式，并将视图设置为“边选择”，以便直观查看结果
if selected_objects:
    # 确保有一个活动物体才能进入编辑模式
    bpy.context.view_layer.objects.active = selected_objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='EDGE')