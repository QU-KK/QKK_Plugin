import bpy

# 变量
Check_Item_Name = '模型名称'
Description = '检查名称是否含有 S_、+1、空格、.0，以及判断是否存在"_lod" "_COL" "_shadowProxy"'

# 名称检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    
    if "S_" not in name:
        description = '缺少  S_'
        data = [name,description]
        Check_Data.append(data)
        
    if "+1_" not in name:    
        description = '缺少  +1_'
        data = [name,description]
        Check_Data.append(data)
        
    if " " in name:    
        description = '存在空格'
        data = [name,description]
        Check_Data.append(data)
        
    if ".0" in name:    
        description = '存在  .0'
        data = [name,description]
        Check_Data.append(data)
    
    if "_lod" not in name and "_COL" not in name and "_shadowProxy" not in name:    
        description = '模型名称不规范'
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