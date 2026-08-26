import bpy

# 变量
Check_Item_Name = '投影比率'
Description = '投影比率'
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
    if '_COL1_UM01' in name:
        lod0 = bpy.data.objects.get(name.replace('_COL1_UM01', '_lod0'))
        if lod0:
            lod0_face = len(lod0.data.loop_triangles)
            COL1_face = len(obj.data.loop_triangles)

            lod1_0 = round((1-COL1_face/lod0_face)*100)
            if lod1_0 < 40:
                description = '比率='+ str(lod1_0)+'%'    +'    不满足40%    ' +'面数=' + str(lod1_face) + '    建议面数=' + str(int(lod0_face*0.6))
                data = [name,description]
                Check_Data.append(data)


#_shadowProxy

# 枚举
icon = 'NODE_SOCKET_SHADER'
if len(Check_Data) > 1:
    icon = 'NODE_SOCKET_MATRIX'
Check_Ui = [Check_Item_Name,Check_Item_Name, Description, icon]

# Merge Data
Check_Overall_Ui.append(Check_Ui)
Check_Overall_Data.append(Check_Data)