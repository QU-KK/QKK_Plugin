import bpy
import bmesh
# 变量
Check_Item_Name = '碰撞闭口'
Description = '碰撞闭口'
Check_Data = [Check_Item_Name]

#检查多边面
for obj in selected_objects:
    name = obj.name
    if '_COL' in name:
        # 1. 实例化一个空的 BMesh 容器
        bm = bmesh.new()    
        # 2. 将当前物体的网格数据加载进 BMesh 中
        bm.from_mesh(obj.data)    
        # 3. 遍历所有的边，进行拓扑检查
        for edge in bm.edges:
            # is_manifold 属性会自动判断该边是否恰好连接了两个面
            # 如果不是（说明有破洞，或者有内部错面），即为非闭口结构
            if not edge.is_manifold:
                description = '碰撞未闭口'
                data = [name,description]
                Check_Data.append(data)
                break  # 检查到一处开口，立刻中断！       
        # 4. 重点：用完 BMesh 后必须手动释放内存，否则会导致内存泄漏！
        bm.free()

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)