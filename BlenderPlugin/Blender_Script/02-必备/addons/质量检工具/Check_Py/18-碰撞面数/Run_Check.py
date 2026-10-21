import bpy

# 变量
Check_Item_Name = '碰撞面上限'
Description = '碰撞面上限'
Check_Data = [Check_Item_Name]

# 储存物体名称
Obj_Name_List = []
for obj in selected_objects:
    Obj_Name_List.append(obj.name)
# 按名称排序
Obj_Name_List.sort()


#检查碰撞  面上限
for name in Obj_Name_List:
    if '_COL1_' in name:
        col1_obj = bpy.data.objects.get(name)
        lod1_obj = bpy.data.objects.get(name.replace("_COL1_UM01", "_lod1"))
        if lod1_obj:
            # 'S_mod_'   'S_imod_'   'S_build'
            if 'S_mod_' in name or 'S_imod_' in name or 'S_build_' in name:
                col1_face = len(col1_obj.data.loop_triangles)
                lod1_face = len(lod1_obj.data.loop_triangles)

                if lod1_face < 400:
                    if col1_face >= lod1_face:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于'+ str(int(lod1_face))
                        data = [name,description]
                        Check_Data.append(data)

                if 401 < lod1_face < 1500:
                    if col1_face >= 400 and col1_face >= lod1_face*0.55:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于400或小于'+ str(int(lod1_face*0.55))
                        data = [name,description]
                        Check_Data.append(data)
                
                if 1501 < lod1_face < 3000:
                    if col1_face >= 750 and col1_face >= lod1_face*0.35:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于750或小于'+ str(int(lod1_face*0.35))
                        data = [name,description]
                        Check_Data.append(data)
                
                if 3000 < lod1_face:
                    if col1_face >= 900 and col1_face >= lod1_face*0.2:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于900或小于'+ str(int(lod1_face*0.2))
                        data = [name,description]
                        Check_Data.append(data)                





            # 'S_prop_'   'S_iprop_'   'S_cloth_'
            if 'S_prop_' in name or 'S_iprop_' in name or 'S_cloth_' in name:
                col1_face = len(col1_obj.data.loop_triangles)
                lod1_face = len(lod1_obj.data.loop_triangles)

                if lod1_face < 400:
                    if col1_face >= lod1_face:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于'+ str(int(lod1_face))
                        data = [name,description]
                        Check_Data.append(data)

                if 401 < lod1_face < 1500:
                    if col1_face >= 400 and col1_face >= lod1_face*0.5:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于400或小于'+ str(int(lod1_face*0.5))
                        data = [name,description]
                        Check_Data.append(data)
                
                if 1501 < lod1_face < 6000:
                    if col1_face >= 750 and col1_face >= lod1_face*0.3:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于750或小于'+ str(int(lod1_face*0.3))
                        data = [name,description]
                        Check_Data.append(data)
                
                if 6000 < lod1_face:
                    if col1_face >= 1800 and col1_face >= lod1_face*0.1:
                        description = '当前碰撞面数=' + str(col1_face) + '      需要小于900或小于'+ str(int(lod1_face*0.1))
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