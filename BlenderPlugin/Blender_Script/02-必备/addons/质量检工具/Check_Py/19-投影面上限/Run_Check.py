import bpy

# 变量
Check_Item_Name = '投影面上限'
Description = '投影面上限'
Check_Data = [Check_Item_Name]

# 储存物体名称
Obj_Name_List = []
for obj in selected_objects:
    Obj_Name_List.append(obj.name)
# 按名称排序
Obj_Name_List.sort()


#检查碰撞  面上限
for name in Obj_Name_List:
    if '_shadowProxy' in name:
        col1_obj = bpy.data.objects.get(name)
        lod1_obj = bpy.data.objects.get(name.replace("_shadowProxy", "_lod1"))
        if lod1_obj:
            # 'S_mod_'   'S_imod_'
            if 'S_mod_' in name or 'S_imod_' in name:
                shadow_face = len(col1_obj.data.loop_triangles)
                lod1_face = len(lod1_obj.data.loop_triangles)

                if lod1_face < 1500:
                    if not(shadow_face < lod1_face*0.3):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.3))
                        data = [name,description]
                        Check_Data.append(data)

                if 1501 <= lod1_face <= 6600:
                    if not(shadow_face <= lod1_face*0.15):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.15))
                        data = [name,description]
                        Check_Data.append(data)
                
                if 6600 < lod1_face:
                    if not(shadow_face <= lod1_face*0.1 and shadow_face < 2500):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.1)) + '且小于2500'
                        data = [name,description]
                        Check_Data.append(data)             


            # 'S_prop_'   'S_iprop_'   'S_cloth_'
            if 'S_prop_' in name or 'S_iprop_' in name or 'S_cloth_' in name:
                shadow_face = len(col1_obj.data.loop_triangles)
                lod1_face = len(lod1_obj.data.loop_triangles)

                if lod1_face < 1200:
                    if not(shadow_face < lod1_face*0.3):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.3))
                        data = [name,description]
                        Check_Data.append(data)

                if 1201 <= lod1_face <= 5000:
                    if not(shadow_face <= lod1_face*0.25):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.25))
                        data = [name,description]
                        Check_Data.append(data)
                
                if 5001 <= lod1_face <= 10000:
                    if not(shadow_face <= lod1_face*0.5):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.1)) + '且小于2500'
                        data = [name,description]
                        Check_Data.append(data)  


                if 10000 < lod1_face:
                    if not(shadow_face <= lod1_face*0.15 and shadow_face < 3500):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.15)) + '且小于3500'
                        data = [name,description]
                        Check_Data.append(data)  



            # 'S_building'
            if 'S_building' in name :
                shadow_face = len(col1_obj.data.loop_triangles)
                lod1_face = len(lod1_obj.data.loop_triangles)

                if lod1_face < 2000:
                    if not(shadow_face < lod1_face*0.3):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.3))
                        data = [name,description]
                        Check_Data.append(data)

                if 2001 <= lod1_face <= 10000:
                    if not(shadow_face <= lod1_face*0.2):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.2))
                        data = [name,description]
                        Check_Data.append(data)
                
                if 10000 < lod1_face:
                    if not(shadow_face <= lod1_face*0.15 and shadow_face < 2500):
                        description = '当前投影面数=' + str(shadow_face) + '      需要小于'+ str(int(lod1_face*0.15)) + '且小于2500'
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