import bpy

# 变量
Check_Item_Name = '材质名称'
Description = '检查材质名称是否含有 M_、+1、空格、.0，判断名称字段数'

# 材质名称检查
Check_Data = [Check_Item_Name]

Mat_Name_List = []
for obj in selected_objects:
    name = obj.name
    if '_lod' in name:
        for slot in obj.material_slots:
            if slot.material:                          
                mat_name = slot.material.name                
                if mat_name not in Mat_Name_List:
                    Mat_Name_List.append(mat_name)
                    description = ''
                    if "M_" not in mat_name:
                        description = description +  '缺少M_    '
                        
                    if "+1_" not in mat_name:    
                        description = description +  '缺少+1_    '
                        
                    if " " in mat_name:    
                        description = description +  '存在空格    '
                        
                    if ".0" in mat_name:    
                        description = description +  '存在 .0    '

                    split = mat_name.split('_')
                    
                    if len(split[len(split)-1]) > 3:
                        description = description +  '尾缀错误    '

                    if len(mat_name.split('_')) != 6 and '+1_' in mat_name:
                        description = description +  '字段数错误    '

                    if description != '':
                        data = [mat_name,description]
                        Check_Data.append(data)

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)