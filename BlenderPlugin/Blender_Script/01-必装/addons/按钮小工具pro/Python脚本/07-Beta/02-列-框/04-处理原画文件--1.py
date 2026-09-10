import bpy

print('应用网格修改器、曲线转mesh')
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

    if obj.type == 'CURVE':
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
    obj.hide_select = False
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



# 删除场景中的所有相机和灯光物体
print('删除灯光、相机')
for obj in list(bpy.data.objects):
    if obj.type in {'CAMERA', 'LIGHT'}:
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.outliner.orphans_purge()


# 处理可以可视的实例
print('处理可视实例')
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.visible_objects:
    if obj.instance_type == 'COLLECTION':
        bpy.ops.object.select_pattern(pattern=obj.name, case_sensitive=True, extend=True)

# 刷新视图
bpy.context.view_layer.update()
# 直接转换为网格
bpy.ops.object.duplicates_make_real(use_base_parent=True)
print('完成步骤1')


#2
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
print('完成步骤2')




#3

print("\n" + "="*50)
print("开始执行线性清理脚本 (顺序: 空集合 -> 隐藏集合 -> 隐藏物体)")
print("="*50 + "\n")


# ==========================================
# [阶段 1] 优先删除空集合 (利用 while 实现线性深度清理)
# ==========================================
print(">>> [1/3] 正在扫描并删除空集合...")
removed_empty_colls = 0

while True:
    # 查找没有任何物体、且没有任何子集合的空集合
    empty_colls = [c for c in bpy.data.collections if len(c.objects) == 0 and len(c.children) == 0]
    
    if not empty_colls:
        break
        
    for coll in empty_colls:
        coll_name = coll.name
        bpy.data.collections.remove(coll)
        removed_empty_colls += 1
        print(f"  -> [空集合清理] 已删除: {coll_name}")

if removed_empty_colls == 0:
    print("  -> 未发现空集合。")
print("-" * 50)


# ==========================================
# [阶段 2] 删除隐藏/不启用的集合
# ==========================================
print(">>> [2/3] 正在扫描并删除隐藏/不启用的集合...")

hidden_colls_to_delete = set()
# 使用列表作为“栈(Stack)”，代替原本的递归函数，保持代码结构平铺且线性
layer_colls_stack = list(bpy.context.view_layer.layer_collection.children)

while layer_colls_stack:
    current_layer = layer_colls_stack.pop()
    
    # 判断条件：取消打勾 (exclude) 或 闭眼隐藏 (hide_viewport)
    is_hidden = current_layer.exclude or current_layer.hide_viewport or current_layer.collection.hide_viewport
    
    if is_hidden:
        hidden_colls_to_delete.add(current_layer.collection)
        # 【关键衔接】：在彻底删除该隐藏集合前，将其内部的物体强行打上"隐藏"标记。
        # 这样它们就不会在集合被删后“掉到外面”变成可见，从而保证在第三步能被精准删除。
        for obj in current_layer.collection.objects:
            obj.hide_viewport = True
            
    # 把子集合压入栈中，继续进行线性遍历
    for child in current_layer.children:
        layer_colls_stack.append(child)

# 开始执行删除并打印进度
hidden_colls_list = list(hidden_colls_to_delete)
total_hidden_colls = len(hidden_colls_list)

if total_hidden_colls == 0:
    print("  -> 未发现隐藏/不启用的集合。")
else:
    for idx, coll in enumerate(hidden_colls_list, 1):
        coll_name = coll.name
        if bpy.data.collections.get(coll_name):
            bpy.data.collections.remove(coll)
        percent = (idx / total_hidden_colls) * 100
        print(f"  -> [隐藏集合清理 {percent:5.1f}%] ({idx}/{total_hidden_colls}) 已删除: {coll_name}")

print("-" * 50)


# ==========================================
# [阶段 3] 删除隐藏物体
# ==========================================
print(">>> [3/3] 正在扫描并删除隐藏物体...")

# 收集所有自身隐藏的物体（包含刚才第二步继承了隐藏属性的物体）
hidden_objs = [obj for obj in bpy.data.objects if obj.hide_viewport or obj.hide_get()]
total_hidden_objs = len(hidden_objs)

if total_hidden_objs == 0:
    print("  -> 未发现隐藏物体。")
else:
    for idx, obj in enumerate(hidden_objs, 1):
        obj_name = obj.name
        if bpy.data.objects.get(obj_name):
            bpy.data.objects.remove(obj, do_unlink=True)
        percent = (idx / total_hidden_objs) * 100
        print(f"  -> [隐藏物体清理 {percent:5.1f}%] ({idx}/{total_hidden_objs}) 已删除: {obj_name}")


# ==========================================
# 结束汇总
# ==========================================
print("\n" + "="*50)
print("【线性清理执行完毕】")
print(f" - 删除 空集合 : {removed_empty_colls} 个")
print(f" - 删除 隐藏集合: {total_hidden_colls} 个")
print(f" - 删除 隐藏物体: {total_hidden_objs} 个")
print("="*50 + "\n")

print('完成步骤3')

#4
#清空父子集合
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
Empty_list = []
for obj in bpy.context.selected_objects:
    if obj.type == 'EMPTY':
        Empty_list.append(obj)

progress = 0
for obj in Empty_list:
    if obj.type == 'EMPTY':
        bpy.data.objects.remove(object=obj, do_unlink=True, do_id_user=True, do_ui_user=True)
    progress += 1
    print(progress,'/',len(Empty_list))
print('完成步骤4')



#5
# 删除不可见集合
stack = [bpy.context.layer_collection]
while stack:
    lc = stack.pop()    
    stack.extend(lc.children)
    print(lc.name)
    if lc.name != 'Scene Collection':
        collection = bpy.context.blend_data.collections[lc.name]
        if lc.exclude ==True or lc.hide_viewport == True or collection.hide_viewport == True:
            bpy.context.blend_data.collections.remove(collection=collection, do_unlink=True)

# 删除不包含MESH的空物体
for obj in bpy.data.objects:
    if obj.type == 'EMPTY':
        if not any(child.type == 'MESH' for child in obj.children_recursive):
            bpy.data.objects.remove(obj, do_unlink=True)


# 删除隐藏的MESH
for obj in bpy.context.blend_data.objects:
    if obj.type == 'MESH':
        if len(obj.children) == 0:
            if obj.hide_get() == True or obj.hide_viewport == True:
                bpy.context.blend_data.objects.remove(object=obj, do_unlink=True)

# 清理残留
bpy.ops.outliner.orphans_purge()




print('全部完成')
