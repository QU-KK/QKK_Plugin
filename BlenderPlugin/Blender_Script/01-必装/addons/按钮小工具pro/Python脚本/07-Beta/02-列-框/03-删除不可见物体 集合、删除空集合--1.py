import bpy

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