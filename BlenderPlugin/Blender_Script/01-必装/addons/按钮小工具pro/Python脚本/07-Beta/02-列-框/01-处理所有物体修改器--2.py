import bpy
print('全局本地化几何节')
# 1.全局本地化几何节点（稳定版）
for node_group in bpy.context.blend_data.node_groups:
    if node_group.type == 'GEOMETRY':
        node_group.make_local()


print('全局几何节点增加实现实例（功能版）')
# 2.全局几何节点增加实现实例（功能版）
skip_if_already_realized = True
group_count = 0
total_inserted = 0

for ng in bpy.data.node_groups:
    if ng.bl_idname != "GeometryNodeTree":
        continue

    group_count += 1
    count = 0
    nodes = ng.nodes
    links = ng.links

    # 查找当前节点组中的所有“组输出”节点（避免在遍历中修改集合导致异常）
    output_nodes = [n for n in nodes if n.bl_idname == "NodeGroupOutput"]

    for out_node in output_nodes:
        for input_socket in out_node.inputs:
            # 仅处理已连接的几何体输出接口
            if input_socket.type != "GEOMETRY" or not input_socket.is_linked:
                continue

            existing_link = input_socket.links[0]
            from_socket = existing_link.from_socket
            from_node = existing_link.from_node

            # 若上游已经直接连接“实现实例”节点，则跳过，避免重复插入
            if skip_if_already_realized and from_node.bl_idname == "GeometryNodeRealizeInstances":
                continue

            # 创建“实现实例”节点并摆放在组输出左侧
            realize_node = nodes.new(type="GeometryNodeRealizeInstances")
            ref_y = from_node.location.y if from_node != out_node else out_node.location.y
            realize_node.location = (out_node.location.x - 220, ref_y)

            # 断开原连线，并重新串接：上游输出 -> 实现实例 -> 组输出
            links.remove(existing_link)
            links.new(from_socket, realize_node.inputs["Geometry"])
            links.new(realize_node.outputs["Geometry"], input_socket)




print('全局网格独立化')
# 3.全局网格独立化（稳定版）
for obj in bpy.data.objects:
    if obj.type == "MESH" and obj.data and obj.data.users > 1:
        obj.data = obj.data.copy()



# 3.5新增集合进行缓存
print('创建缓存')
col_name = "自动塌陷缓存"  # 目标集合名称
parent_col = bpy.context.scene.collection  # 父集合（默认当前场景根集合）

# 获取或新建集合，并确保链接到父集合
col = bpy.data.collections.get(col_name)
if col is None:
  col = bpy.data.collections.new(col_name)
  parent_col.children.link(col)
else:
  # 集合已存在，再判断是否已链接到父集合
  if col.name not in parent_col.children:
    parent_col.children.link(col)

# 遍历当前视图层的大纲层级，定位并激活目标集合
stack = [bpy.context.view_layer.layer_collection]
while stack:
  lc = stack.pop()
  if lc.collection == col:
    bpy.context.view_layer.active_layer_collection = lc
    break
  stack.extend(lc.children)



# 4.全局塌陷
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


print('删除缓存集合')
# 删除缓存集合
bpy.data.collections.remove(bpy.data.collections['自动塌陷缓存'])

# 5.删除场景中的所有相机和灯光物体
print('删除灯光、相机')
for obj in list(bpy.data.objects):
    if obj.type in {'CAMERA', 'LIGHT'}:
        bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.outliner.orphans_purge()


# 6.处理可以可视的实例
print('处理可视实例')
bpy.ops.object.select_all(action='DESELECT')
for obj in bpy.context.visible_objects:
    if obj.instance_type == 'COLLECTION':
        bpy.ops.object.select_pattern(pattern=obj.name, case_sensitive=True, extend=True)

# 刷新视图
bpy.context.view_layer.update()
# 直接转换为网格
bpy.ops.object.duplicates_make_real(use_base_parent=True)



print('删除布尔残留')
# 删除布尔残留
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




print('！！！全部完成！！！')

