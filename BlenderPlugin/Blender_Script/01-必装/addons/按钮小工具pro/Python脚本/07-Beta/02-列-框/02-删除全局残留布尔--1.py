import bpy

# 强制取消当前场景的所有选中，避免干扰后续的激活物体操作
bpy.ops.object.select_all(action='DESELECT')

# 统计需要处理的物体、
Progress = 0
Obj_List = []
for obj in bpy.data.objects:
    # 只处理网格物体，且身上带有修改器
    if obj.type == 'MESH' and obj.display_type == 'WIRE':
        Obj_List.append(obj)
        Progress += 1


# 初始化处理
a = 0
Obj_Link_List = []
for obj in Obj_List:
    a += 1    
    print(a,'/',Progress,'    ',obj.name)
    bpy.data.objects.remove(obj, do_unlink=True)
    # 选中
    #obj.select_set(True)
# 刷新视图
#bpy.context.view_layer.update() 

#bpy.ops.object.delete(use_global=True)
print('！！！全部完成！！！')

