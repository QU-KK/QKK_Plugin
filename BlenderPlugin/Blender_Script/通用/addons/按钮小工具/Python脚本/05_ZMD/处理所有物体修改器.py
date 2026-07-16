import bpy

# 强制取消当前场景的所有选中，避免干扰后续的激活物体操作
bpy.ops.object.select_all(action='DESELECT')

# 统计需要处理的物体
Progress = 0
Obj_List = []
for obj in bpy.data.objects:
    
    # 只处理网格物体，且身上带有修改器
    if obj.type == 'MESH' and obj.modifiers:
        Progress += 1
        Obj_List.append(obj)

# 初始化处理
a = 0
Obj_Link_List = []
for obj in Obj_List:
    #打印进度
    a += 1    
    print(a,'/',Progress,'    ',obj.name)
    #链接到3D视口中
    bpy.context.collection.objects.link(obj)
    # 记录显示状态
    data = [obj,obj.hide_get(),obj.hide_viewport]
    # 让其显示
    obj.hide_set(False)
    obj.hide_viewport = False
    
    # 将其设为激活并选中
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    Obj_Link_List.append(data)

# 刷新视图
bpy.context.view_layer.update() 
# 直接转换为网格
bpy.ops.object.convert(target='MESH')

for data in Obj_Link_List:
    obj = data[0]
    obj.hide_set(data[1])
    obj.hide_viewport = data[2]    
    # 移除
    bpy.context.collection.objects.unlink(obj)


print('！！！全部完成！！！')