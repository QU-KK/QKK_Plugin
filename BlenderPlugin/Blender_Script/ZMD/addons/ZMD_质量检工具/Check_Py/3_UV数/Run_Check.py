import bpy

# 变量
Check_Item_Name = 'UV数'
Description = 'UV数'

# 顶点色检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    uvs = len(obj.data.uv_layers)
    
    if "_COL" in name or "_sh" in name:
        if uvs != 0:
            description = 'UV数=' + str(uvs)
            data = [name,description]
            Check_Data.append(data)
    else:
        if uvs == 0 or uvs > 2:
            description = 'UV数=' + str(uvs)
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