import bpy

# 变量
Check_Item_Name = '材质槽'
Description = '存在空材质槽报错。没有材质槽报错。_lod、_COL 材质槽大于5报错。_shadowProxy 材质槽大于1报错。'

# 材质槽数检查
Check_Data = [Check_Item_Name]
for obj in selected_objects:
    name = obj.name
    slots = len(obj.material_slots)

    for slot in obj.material_slots:
        if slot.material == None:
            description = '存在空材质槽'
            data = [name,description]
            Check_Data.append(data)

    if slots == 0:
        description = '材质槽为零'
        data = [name,description]
        Check_Data.append(data)


    if '_lod' in name or '_COL' in name:
        if slots > 5:
            description = '材质槽数>5  =' + str(slots)
            data = [name,description]
            Check_Data.append(data)
    
    if '_shadowProxy' in name:
        if slots > 1:
            description = '材质槽数>1  =' + str(slots)
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