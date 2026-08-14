import bpy

# 变量
Check_Item_Name = '材质'
Description = '检查材质名称是否含有 M_、+1、空格、.0，判断名称字段数'

# 材质名称检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    if '_lod' in name:
        for slot in obj.material_slots:
            if slot.material:
                mat_name = slot.material.name
                if "M_" not in mat_name:
                    description = '缺少 M_ : '
                    data = [mat_name,description]
                    Check_Data.append(data)
                    
                if "+1_" not in mat_name:    
                    description = '缺少 +1_ : '
                    data = [mat_name,description]
                    Check_Data.append(data)
                    
                if " " in mat_name:    
                    description = '存在空格 : '
                    data = [mat_name,description]
                    Check_Data.append(data)
                    
                if ".0" in mat_name:    
                    description = '存在 .0 : '
                    data = [mat_name,description]
                    Check_Data.append(data)

                if len(mat_name.split('_')) != 6 and '+1_' in mat_name:
                    description = '名称字段数量错误'
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