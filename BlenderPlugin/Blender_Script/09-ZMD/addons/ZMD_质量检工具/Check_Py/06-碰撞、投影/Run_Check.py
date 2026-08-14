import bpy

# 变量
Check_Item_Name = '碰撞、投影'
Description = '碰撞材质:"PM_Metal", "PM_Concrete", "PM_Wood", "PM_Crystal", "PM_Rubber"", "PM_Stone"、投影材质:"M_shadowproxy_static_opaque"'

# Xfrom检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    
    if "_COL" in name:
        colliders_list = ['PM_Metal', 'PM_Concrete', 'PM_Wood', 'PM_Crystal', 'PM_Rubber', 'PM_Stone']
        for slot in obj.material_slots:
            if slot.material:# 判断材质槽
                mat_name = slot.material.name 
                if mat_name not in colliders_list:
                    description = '碰撞材质错误: ' + mat_name
                    data = [name, description]
                    Check_Data.append(data)

    if "_shadowProxy" in name:
        for slot in obj.material_slots:
            if slot.material:# 判断材质槽
                mat_name = slot.material.name 
                if mat_name != 'M_shadowproxy_static_opaque':
                    description = '投影材质错误: ' + mat_name
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