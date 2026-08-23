import bpy
# 物体实例化
if len(bpy.context.selected_objects) == 1 and bpy.context.active_object.data != None and bpy.context.active_object.data.id_type == 'MESH':

    # 创建几何节点组
    group_name = ".物体实例化"
    node_groups = bpy.context.blend_data.node_groups.get(group_name)

    if not node_groups:
            
        node_tree = bpy.data.node_groups.new(name=group_name, type='GeometryNodeTree')

        node_tree.interface.new_socket(name="物体", in_out='INPUT', socket_type='NodeSocketObject')
        node_tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')


        # 获取节点和链接集合
        nodes = node_tree.nodes
        links = node_tree.links

        # 组输入 (Group Input)
        node_input = nodes.new(type='NodeGroupInput')
        node_input.location = (-400, 0)

        # 物体信息 (Object Info)
        node_obj_info = nodes.new(type='GeometryNodeObjectInfo')
        node_obj_info.location = (-200, 0)
        node_obj_info.transform_space = 'ORIGINAL' # 对应 "原始"
        node_obj_info.inputs['As Instance'].default_value = True # 勾选 "作为实例"

        # 缩放实例 (Scale Instances)
        node_scale = nodes.new(type='GeometryNodeScaleInstances')
        node_scale.location = (0, -100)
        # 局部空间 (Local Space) 默认即为 True 勾选状态

        # 旋转实例 (Rotate Instances)
        node_rotate = nodes.new(type='GeometryNodeRotateInstances')
        node_rotate.location = (200, 50)
        # 局部空间 (Local Space) 默认即为 True 勾选状态

        # 组输出 (Group Output)
        node_output = nodes.new(type='NodeGroupOutput')
        node_output.location = (400, 50)

        # 组输入 -> 物体信息
        links.new(node_input.outputs['物体'], node_obj_info.inputs['Object'])

        # 物体信息 -> 缩放实例
        links.new(node_obj_info.outputs['Geometry'], node_scale.inputs['Instances']) # 几何数据 -> 实例
        links.new(node_obj_info.outputs['Scale'], node_scale.inputs['Scale'])        # 缩放 -> 缩放

        # 缩放实例 -> 旋转实例
        links.new(node_scale.outputs['Instances'], node_rotate.inputs['Instances'])  # 实例 -> 实例
        links.new(node_obj_info.outputs['Rotation'], node_rotate.inputs['Rotation']) # 旋转 -> 旋转

        # 旋转实例 -> 组输出
        links.new(node_rotate.outputs['Instances'], node_output.inputs['Geometry'])



    mesh_obj = bpy.context.active_object
    mesh_obj_name = mesh_obj.name
    mesh_obj_location = mesh_obj.location


    bpy.ops.object.empty_add(type='PLAIN_AXES')

    instancuing = bpy.context.active_object
    instancuing.name = mesh_obj_name + '_实例'
    instancuing.location = mesh_obj_location

    bpy.ops.object.modifier_add(type='NODES')
    modifiers = instancuing.modifiers[0]
    modifiers.name = group_name
    modifiers.node_group = bpy.context.blend_data.node_groups.get(group_name)

    modifiers.properties.inputs.Socket_0.value = mesh_obj
