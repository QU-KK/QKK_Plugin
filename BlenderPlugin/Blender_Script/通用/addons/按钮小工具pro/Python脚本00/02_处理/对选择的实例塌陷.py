import bpy
# 获取实例物体
obj = bpy.context.active_object
obj_name = obj.name

#判断类似是否为实例
if obj.instance_type == 'COLLECTION':

    # 记录集合内数据
    Obj_List = []
    Progress = 0
    # 获取实例里的物体
    for obj in obj.instance_collection.all_objects:
        if obj.type == 'MESH' and obj.modifiers:
            Progress += 1
            Obj_List.append(obj)

    # 取消选中
    bpy.ops.object.select_all(action='DESELECT')

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



    # 获取储存好的实例
    obj = bpy.data.objects.get(obj_name)
    obj.select_set(True)  # 选择物体
    bpy.context.view_layer.objects.active = obj # 设置为激活物体（高亮橙色）    
    bpy.ops.object.duplicates_make_real()
    bpy.ops.object.convert(target='MESH')