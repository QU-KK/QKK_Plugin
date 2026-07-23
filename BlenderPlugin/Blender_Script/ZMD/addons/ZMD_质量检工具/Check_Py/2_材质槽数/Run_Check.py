import bpy

# 变量
Check_Item_Name = '材质槽数'
Description = '材质槽数'

# 顶点色检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    slots = len(obj.material_slots)
    if slots > 5:
        name = obj.name
        description = '材质槽数>5  =' + str(slots)
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