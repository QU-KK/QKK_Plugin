import bpy

# 变量
Check_Item_Name = '材质顺序'
Description = '材质顺序'
Check_Data = [Check_Item_Name]

# 储存物体名称
Obj_Name_List = []
for obj in selected_objects:
    if '_lod0' in obj.name:
        Obj_Name_List.append(obj.name)
# 按名称排序
Obj_Name_List.sort()


#检查材质数量
lod_list = ['_lod1','_lod2','_lod3','_lod4','_lod5','_lod6']
for name in Obj_Name_List:
    for lod in lod_list:
        # 获取lod
        lod0_obj = bpy.data.objects.get(name)
        # lod0材质槽数量
        lod0_mat_quantity = len(lod0_obj.material_slots)
        # 获取lod0材质列表
        lod0_mat_list = []
        for lod0_mat in lod0_obj.material_slots:
            lod0_mat_list.append(lod0_mat.name)

        # 遍历lod
        obj = bpy.data.objects.get(name.replace('_lod0', lod))        
        if obj:
            # 材质数量
            obj_mat_quantity = len(obj.material_slots)
            # 材质顺序
            obj_mat_list = []
            for obj_mat in obj.material_slots:
                obj_mat_list.append(obj_mat.name)

            if obj_mat_quantity != lod0_mat_quantity:
                    description = '材质    数量与lod0 不匹配'
                    data = [obj.name,description]
                    Check_Data.append(data)
            else:                
                if obj_mat_list != lod0_mat_list:
                        description = '材质    顺序与lod0 不匹配'
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