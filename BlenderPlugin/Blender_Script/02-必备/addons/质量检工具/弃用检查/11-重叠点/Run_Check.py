import bpy
import mathutils

# 变量
Check_Item_Name = '重叠点'
Description = '重叠点'
Check_Data = [Check_Item_Name]

#检查短边
for obj in selected_objects:
    vertices = obj.data.vertices
    vert_count = len(vertices)       
    Number = 0
    kd = mathutils.kdtree.KDTree(vert_count)
    for i, v in enumerate(vertices):
        # 检查重叠点属于模型内部拓扑问题，直接用局部坐标 (v.co) 即可，速度更快
        kd.insert(v.co, i)
        
    # 平衡树（必须执行，用于优化搜索性能）
    kd.balance()
    
    # 2. 设置重叠点的判断阈值（Blender "按距离合并/M" 的默认值是 0.0001 米，即 0.1 毫米）
    merge_distance = 0.0001 
    
    # 3. 遍历所有顶点，在树中搜索极小范围内的相邻点
    for i, v in enumerate(vertices):
        # find_range 会返回在阈值半径内的所有点：格式为 [(坐标, 索引, 距离), ...]
        neighbors = kd.find_range(v.co, merge_distance)
        
        # 划重点：搜索时必然会查找到顶点“自己本身”（距离为0）。
        # 因此，如果在阈值范围内找到的顶点数量 > 1，就说明有别的点和它重叠了！
        if len(neighbors) > 1:
            Number += 1

    
    if Number != 0:
        description = '存在重叠点 数量=' + str(Number)
        data = [obj.name,description]
        Check_Data.append(data)

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)