import bpy

# 变量
Check_Item_Name = '短边'
Description = '检查边<0.1cm'
Check_Data = [Check_Item_Name]

#检查短边
for obj in selected_objects:
    matrix_world = obj.matrix_world
    vertices = obj.data.vertices
    # 遍历模型的所有边
    name = obj.name
    Number = 0
    if '_lod' in name:
        for edge in obj.data.edges:
            # 获取边两端的顶点索引
            v1_idx, v2_idx = edge.vertices
            # 将局部坐标转换为世界坐标系下的真实位置
            v1_world_co = matrix_world @ vertices[v1_idx].co
            v2_world_co = matrix_world @ vertices[v2_idx].co
            # 计算两点之间的距离 (Blender 默认单位 1 = 1米，0.01 即 1cm)
            edge_length = (v1_world_co - v2_world_co).length
            if edge_length < 0.001:
                Number += 1

    if '_COL' in name or '_shadowProxy' in name:
        for edge in obj.data.edges:
            # 获取边两端的顶点索引
            v1_idx, v2_idx = edge.vertices
            # 将局部坐标转换为世界坐标系下的真实位置
            v1_world_co = matrix_world @ vertices[v1_idx].co
            v2_world_co = matrix_world @ vertices[v2_idx].co
            # 计算两点之间的距离 (Blender 默认单位 1 = 1米，0.01 即 1cm)
            edge_length = (v1_world_co - v2_world_co).length
            if edge_length < 0.02:
                Number += 1


    if Number != 0:
        description = '存在短边<0.1cm 数量=' + str(Number)
        data = [name,description]
        Check_Data.append(data)





# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)