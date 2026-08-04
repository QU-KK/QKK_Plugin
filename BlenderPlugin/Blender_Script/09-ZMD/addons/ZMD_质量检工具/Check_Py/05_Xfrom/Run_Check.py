import bpy

# 变量
Check_Item_Name = 'Xfrom'
Description = '旋转不等于0，缩放不等于1 报错。'

# Xfrom检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    

    euler = obj.rotation_euler
    rotation = (euler[0],euler[1],euler[2])
    scale = (obj.scale[0],obj.scale[1],obj.scale[2])

    if rotation != (0,0,0) or scale != (1,1,1):
        description = '旋转或缩放未应用'
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