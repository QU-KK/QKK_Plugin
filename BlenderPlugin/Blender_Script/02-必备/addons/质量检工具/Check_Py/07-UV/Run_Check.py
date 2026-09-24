import bpy

# 变量
Check_Item_Name = 'UV'
Description = '_lod UV数大于2报错。_COL、_shadowProxy UV数大于0报错，UV名称检查'

# UV数检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    uvs = len(obj.data.uv_layers)
    
    if '_lod' in name:
        # 检查UV数量
        if uvs > 2:
            description = 'UV数未<2    当前=' + str(uvs)
            data = [name,description]
            Check_Data.append(data)

        # 检查UV名称
        name_error = False
        if uvs > 0 and obj.data.uv_layers[0].name != '1U':
            name_error = True
        if uvs > 1 and obj.data.uv_layers[1].name != '2U':
            name_error = True            
        if name_error:
            description = "UV名称不规范"
            data = [name,description]
            Check_Data.append(data) 


    if "_COL" in name or "_shadowProxy" in name:
        if uvs > 0:
            description = 'UV数未=0     当前=' + str(uvs)
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