import bpy

# 变量
Check_Item_Name = '激活UV'
Description = '激活UV检查'
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

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)