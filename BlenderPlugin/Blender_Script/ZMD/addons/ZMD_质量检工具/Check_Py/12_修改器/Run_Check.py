import bpy

# 变量
Check_Item_Name = '修改器'
Description = '是否存在修改器'
Check_Data = [Check_Item_Name]

#检查短边
for obj in selected_objects:
   if len(obj.modifiers) > 0:
        description = '存在修改器'
        data = [obj.name,description]
        Check_Data.append(data)

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)