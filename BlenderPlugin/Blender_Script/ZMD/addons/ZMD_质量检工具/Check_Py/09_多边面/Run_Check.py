import bpy

# 变量
Check_Item_Name = '多边面'
Description = '检查边大于4的面'
Check_Data = [Check_Item_Name]

#检查多边面
for obj in selected_objects:
    Number = 0
    for poly in obj.data.polygons:
        if len(poly.vertices) > 4:
            Number += 1
    if Number != 0:
        description = '存在多边面=' + str(Number)
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