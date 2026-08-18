import bpy

# 变量
Check_Item_Name = 'UV'
Description = '_lod UV数等0或大于2报错。_COL、_shadowProxy UV数大于1报错，UV名称检查'

# UV数检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    uvs = len(obj.data.uv_layers)
    
    if '_lod' in name:
        if uvs == 0 or uvs > 2:
            description = 'UV数=' + str(uvs)
            data = [name,description]
            Check_Data.append(data) 


    if "_COL" in name or "_shadowProxy" in name:
        if uvs > 1:
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