import bpy

# 变量
Check_Item_Name = '坐标轴'
Description = '坐标轴检查'
Check_Data = [Check_Item_Name]


# 允许的坐标轴容差（单位：米）
TOLERANCE = 0.0001


# 储存物体名称
Obj_Name_List = []
for obj in selected_objects:
    if '_lod0' in obj.name:
        Obj_Name_List.append(obj.name)
# 按名称排序
Obj_Name_List.sort()


#检查材质数量
mod_name_list = ['_lod1','_lod2','_lod3','_lod4','_lod5','_lod6','_COL1_UM01','_shadowProxy']
for name in Obj_Name_List:
    # lod0坐标
    lod0_location = bpy.data.objects.get(name).location
    for mod in mod_name_list: 

        # 遍历mod_name_list
        obj = bpy.data.objects.get(name.replace('_lod0', mod))

        if obj:
            # 判断方式 1：计算两点间 3D 空间欧氏距离是否大于 0.01m
            distance = (obj.location - lod0_location).length
            
            # 判断方式 2：若要求 X、Y、Z 任意单轴偏差不得超过 0.01m，可用下面这行替换 distance 判断：
            # is_exceeded = any(abs(a - b) > TOLERANCE for a, b in zip(obj.location, lod0_location))
            
            if distance > TOLERANCE:
                description = '轴心与 lod0 不一致'
                data = [obj.name, description]
                Check_Data.append(data)

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)