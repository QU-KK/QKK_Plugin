import bpy
#显示投影
# 名称
name = '.投影可视化'

# 配置材质
Mat = bpy.data.materials.get(name)
if Mat == None:
    # 创建材质
    Mat = bpy.context.blend_data.materials.new(name)
    # 透明类型
    Mat.surface_render_method = 'BLENDED'
    # 创建节点
    node_tree = Mat.node_tree
    nodes = node_tree.nodes
    links = node_tree.links
    # 清理节点
    nodes.clear()
    # 创建材质输出节点
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    node_output.name = 'Material Output'
    node_output.location = (0,0) # 设置位置

    # 创建材质
    node_attribute = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_attribute.name = 'Principled BSDF'
    node_attribute.location = (-300,0) # 设置位置
    node_attribute.inputs[0].default_value = (0,0,0,1) #颜色
    node_attribute.inputs[2].default_value = 0 #粗糙度
    node_attribute.inputs[4].default_value = 0.15 #透明
    node_attribute.inputs[14].default_value = 0 #高光
    node_attribute.inputs[28].default_value = (0,0.4,0.8,1) #自发颜色
    node_attribute.inputs[29].default_value = 1 #自发光强度

    # 连接
    links.new(node_attribute.outputs['BSDF'], node_output.inputs['Surface'])


# 配置节点
node_group = bpy.data.node_groups.get(name)
if node_group == None:
    # 创建节点
    node_group = bpy.data.node_groups.new(name, type='GeometryNodeTree')

    node_group.interface.new_socket(name="几何数据", in_out='INPUT', socket_type='NodeSocketGeometry')
    node_group.interface.new_socket(name="几何数据", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    
    Node = node_group.nodes
    # 创建 [组输入] 节点
    node_in = Node.new(type='NodeGroupInput')
    node_in.location = (-600,0) # 设置界面中的大致位置

    # 创建 [设置材质] 节点
    node_set_mat = Node.new(type='GeometryNodeSetMaterial')
    node_set_mat.location = (-300,0)

    # 为 [设置材质] 节点指定材质
    for input_socket in node_set_mat.inputs:
        if input_socket.type == 'MATERIAL':
            input_socket.default_value = Mat
            break

    # 创建 [组输出] 节点
    node_out = Node.new(type='NodeGroupOutput')
    node_out.location = (0,0)

    # 连接节点
    links = node_group.links

    # 组输入(几何数据) -> 设置材质(几何数据)
    links.new(node_in.outputs[0], node_set_mat.inputs[0])

    # 设置材质(几何数据) -> 组输出(几何数据)
    links.new(node_set_mat.outputs[0], node_out.inputs[0])


# 关闭线框显示
bpy.context.space_data.overlay.show_wireframes = False
# 显示碰撞
for obj in bpy.data.objects:
    if '_shadowProxy' in obj.name:
        obj.hide_set(False)
        obj.show_wire = True

        # 设置修改器
        if name not in obj.modifiers:
            # 添加几何节点修改器
            mod = obj.modifiers.new(name=name, type='NODES')
            mod.node_group = bpy.data.node_groups[name]