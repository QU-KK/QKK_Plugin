import bpy

# 变量
Check_Item_Name = '面上限'
Description = '面上限'
Check_Data = [Check_Item_Name]

# 储存物体名称
Obj_Name_List = []
for obj in selected_objects:
    Obj_Name_List.append(obj.name)
# 按名称排序
Obj_Name_List.sort()


#检查lod0  面上限
for name in Obj_Name_List:
    obj = bpy.data.objects.get(name)

    # 'S_mod_'   'S_imod_'
    if 'S_mod_' in name or 'S_imod_' in name:
        if '_lod0' in name:
            lod0_face = len(obj.data.loop_triangles)
            if lod0_face > 22000:
                description = '当前面数=' + str(lod0_face) + '      大于22000需要减少'
                data = [name,description]
                Check_Data.append(data)
        
        if '_lod1' in name:
            lod1_face = len(obj.data.loop_triangles)
            if lod1_face > 6600:
                description = '当前面数=' + str(lod1_face) + '      大于6600需要减少'
                data = [name,description]
                Check_Data.append(data)


    # 'S_prop_'   'S_iprop_'
    if 'S_prop_' in name or 'S_prop_' in name:
        if '_lod0' in name:
            lod0_face = len(obj.data.loop_triangles)
            if lod0_face > 44000:
                description = '当前面数=' + str(lod0_face) + '      大于44000需要减少'
                data = [name,description]
                Check_Data.append(data)
        
        if '_lod1' in name:
            lod1_face = len(obj.data.loop_triangles)
            if lod1_face > 11000:
                description = '当前面数=' + str(lod1_face) + '      大于11000需要减少'
                data = [name,description]
                Check_Data.append(data)



    # 'S_build_' 
    if 'S_build_' in name:
        if '_lod0' in name:
            lod0_face = len(obj.data.loop_triangles)
            if lod0_face > 35000:
                description = '当前面数=' + str(lod0_face)  + '      大于35000需要减少'
                data = [name,description]
                Check_Data.append(data)
        
        if '_lod1' in name:
            lod1_face = len(obj.data.loop_triangles)
            if lod1_face > 11000:
                description = '当前面数=' + str(lod1_face) + '      大于11000需要减少'
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