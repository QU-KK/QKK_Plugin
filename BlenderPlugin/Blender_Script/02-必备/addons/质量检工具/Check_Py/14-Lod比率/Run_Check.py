import bpy

# 变量
Check_Item_Name = 'Lod比率'
Description = 'Lod比率'
Check_Data = [Check_Item_Name]

# 储存物体名称
Obj_Name_List = []
for obj in selected_objects:
    Obj_Name_List.append(obj.name)
# 按名称排序
Obj_Name_List.sort()


#检查lod比率
for name in Obj_Name_List:
    obj = bpy.data.objects.get(name)
    if '_lod1' in name:
        lod0 = bpy.data.objects.get(name.replace('_lod1', '_lod0'))
        if lod0:
            lod0_face = len(lod0.data.loop_triangles)
            lod1_face = len(obj.data.loop_triangles)

            lod1_0 = round((1-lod1_face/lod0_face)*100)
            if lod1_0 < 40:
                description = '比率='+ str(lod1_0)+'%'    +'    不满足40%    ' +'面数=' + str(lod1_face) + '    建议面数=' + str(int(lod0_face*0.6))
                data = [name,description]
                Check_Data.append(data)

    if '_lod2' in name:
        lod1 = bpy.data.objects.get(name.replace('_lod2', '_lod1'))
        if lod1:
            lod1_face = len(lod1.data.loop_triangles)
            lod2_face = len(obj.data.loop_triangles)

            lod2_1 = round((1-lod2_face/lod1_face)*100)
            if lod2_1 < 35:
                description = '比率='+ str(lod2_1)+'%'    +'    不满足35%    ' + '面数=' + str(lod2_face) +'    建议面数=' + str(int(lod1_face*0.65))
                data = [name,description]
                Check_Data.append(data)


    if '_lod3' in name:
        lod2 = bpy.data.objects.get(name.replace('_lod3', '_lod2'))
        if lod2:
            lod2_face = len(lod2.data.loop_triangles)
            lod3_face = len(obj.data.loop_triangles)

            lod3_2 = round((1-lod3_face/lod2_face)*100)
            if lod3_2 < 30:
                description = '比率='+ str(lod3_2)+'%'    +'    不满足30%    ' + '面数=' + str(lod3_face) +'    建议面数=' + str(int(lod2_face*0.7))
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