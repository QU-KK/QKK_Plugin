import bpy

# 变量
Check_Item_Name = '模型名称'
Description = '检查名称是否含有 S_、+1、空格、.0，以及判断是否存在"_lod" "_COL" "_shadowProxy"，判断名称字段数'

# 名称检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    description = ''
    if "S_" not in name or "+1_" not in name or " " in name or ".0" in name:
  
        if "S_" not in name:
            description = description + '缺少S_    '
         
        if "+1_" not in name:    
            description = description + '缺少+1_    '

        if " " in name:    
            description = description + '存在空格    '

        if ".0" in name:    
            description = description + '存在 .0    '


    if "_lod" not in name and "_COL" not in name and "_shadowProxy" not in name:    
        description = description +  '缺少尾缀    '

    if len(name.split('_')) != 7 and '+1_' in name and "_COL" not in name:
        description = description +  '字段数错误    '

    if len(name.split('_')) != 8 and '+1_' in name and "_COL" in name:
        description = description + '字段数错误    '

    if description != '':
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