import bpy

# 变量
Check_Item_Name = '顶点色检查'
Description = 'Mod顶点色检查'

# 顶点色检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    vc = len(obj.data.color_attributes)
    if vc != 0:
        name = obj.name
        description = '顶点色数=' + str(vc)
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