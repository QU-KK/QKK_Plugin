import bpy
import bmesh
import os

# 检查项目开关
triangles_number_switch = Check_Item[0]
mat_slots_number_switch = Check_Item[1]
uv_layers_number_switch = Check_Item[2]
vertex_colors_number_switch = Check_Item[3]
check_tex_number_switch = Check_Item[4]
check_mat_slot_switch = Check_Item[5]
check_image_missing_switch = Check_Item[6]
check_ngon_face_switch = Check_Item[7]
check_non_fluid_switch = Check_Item[8]
check_zero_edge_switch = Check_Item[9]
check_quadrant_1u_switch = Check_Item[10]
check_quadrant_2u_switch = Check_Item[11]
check_1uv_overlap_switch = Check_Item[12]
check_2uv_overlap_switch = Check_Item[13]
check_xfrom_switch = Check_Item[14]
check_ani_switch = Check_Item[15]
check_modifier_switch = Check_Item[16]

# 储存选中物体名称
obj_name_list = []
for obj in bpy.context.view_layer.objects.selected:
    obj_name_list.append(obj.name)

# 清空选择
bpy.ops.object.select_all(action='DESELECT')
data_list_out = []
# 遍历物体名称执行处理
counter = 0
for obj_name in obj_name_list:
    # 设置激活模型、选中模型
    bpy.context.view_layer.objects.active = bpy.data.objects[obj_name]
    bpy.ops.object.select_pattern(pattern=obj_name, case_sensitive=True, extend=False)

    obj = bpy.data.objects[obj_name]
    mesh = obj.data
    # 结果初始化
    a = []
    b = []
    c = []
    d = []
    e = []
    f = []
    g = []
    h = []
    i = []
    j = []
    k = []
    l = []
    m = []
    n = []
    o = []
    p = []
    q = []
    u = []

    #模型名称
    obj_name = obj.name
    a = ["名称",obj_name,"字符串"]

    #三角面数
    if triangles_number_switch:
        triangles_number=len(obj.data.loop_triangles)
        b = ["面数",triangles_number,"整数"]

    #材质槽数
    if mat_slots_number_switch:
        mat_slots_number = len(obj.material_slots)
        c = ["材质槽数",mat_slots_number,"整数"]

    #UV数
    if uv_layers_number_switch:
        uv_layers_number = len(obj.data.uv_layers)
        d = ["UV数",uv_layers_number,"整数"]

    #顶点色数
    if vertex_colors_number_switch:
        vertex_colors_number = len(obj.data.vertex_colors)
        e = ["顶点色数",vertex_colors_number,"整数"]

    #检查贴图数量-os
    if check_tex_number_switch:
        image_texture_names = []
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                #遍历节点，找到使用的图像纹理名称，并添加到列表中
                for node in slot.material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        image_texture_names.append(node.image.name)
        check_tex_number = len(image_texture_names)
        f = ["贴图数",check_tex_number,"整数"]

    #空材质槽检查
    if check_mat_slot_switch:
        check_mat_slot = False
        for slot in obj.material_slots:
            if slot.material is None:
                check_mat_slot = True #结果
                break
        g = ["空材质槽",check_mat_slot,"布尔"]

    #检查引用贴图是否丢失-os  !!!!!!!
    if check_image_missing_switch:
        check_image_missing = False
        image_texture_names = []
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                #遍历节点，找到使用的图像纹理名称，并添加到列表中
                for node in slot.material.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        image_texture_names.append(node.image.name)

        for img_name in image_texture_names:
            #print(images)
            image = bpy.data.images.get(img_name)
            # 检查图像是否存在及本地路径
            filepath = bpy.path.abspath(image.filepath)
            if os.path.exists(filepath):
                check = False
            else:
                check_image_missing = True
                break
        h = ["贴图丢失",check_image_missing,"布尔"]

    #多边面检查
    if check_ngon_face_switch:
        check_ngon_face = False
        for polygon in obj.data.polygons:
            if polygon.loop_total > 4:
                check_ngon_face = True #结果
                break
        i = ["多边面",check_ngon_face,"布尔"]

    #非流体检查
    if check_non_fluid_switch:
        check_non_fluid = False
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type='VERT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_non_manifold(extend=False, use_wire=True, use_boundary=False, use_multi_face=True, use_non_contiguous=True, use_verts=False)
        bpy.ops.object.mode_set(mode='OBJECT')
        for vertice in obj.data.vertices:
            if vertice.select:
                check_non_fluid = True
                break
        j = ["非流体",check_non_fluid,"布尔"]

    #零边检查-Bmesh
    if check_zero_edge_switch:
        check_zero_edge = False
        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        # 遍历每条边并计算长度
        for edge in bm.edges:
            length = edge.calc_length()
            if length < 0.001:
                check_zero_edge = True #结果
                break
        # 释放bmesh
        bm.free()
        k = ["零边",check_zero_edge,"布尔"]

    #1UV象限判断
    if check_quadrant_1u_switch:
        check_quadrant_1u = False
        mesh = obj.data
        # 检查是否存在1U数据
        if len(mesh.uv_layers) >= 1:
            # 获取UV层的数据
            uv_layer = mesh.uv_layers[0].data
            # 遍历UV层的所有顶点
            for loop in mesh.loops:
                uv = uv_layer[loop.index].uv
                # 判断UV是否在第一象限
                if uv.x < 0 or uv.y < 0 or uv.x > 1 or uv.y > 1:
                    check_quadrant_1u = True
                    break
        l = ["1U象限",check_quadrant_1u,"布尔"]

    #2UV象限判断
    if check_quadrant_2u_switch:
        check_quadrant_2u = False
        mesh = obj.data
        # 检查是否存在2U数据
        if len(mesh.uv_layers) >= 2:
            # 获取UV层的数据
            uv_layer = mesh.uv_layers[1].data
            # 遍历UV层的所有顶点
            for loop in mesh.loops:
                uv = uv_layer[loop.index].uv
                # 判断UV是否在第一象限
                if uv.x < 0 or uv.y < 0 or uv.x > 1 or uv.y > 1:
                    check_quadrant_2u = True
                    break
        m = ["2U象限",check_quadrant_2u,"布尔"]

    #1UV重叠判断
    if check_1uv_overlap_switch:
        check_1u_overlap = False
        if len(obj.data.uv_layers) >= 1:
            obj.data.uv_layers.active_index = 0
            bpy.context.scene.tool_settings.use_uv_select_sync = True
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_overlap(extend=False)
            for vertice in obj.data.vertices:
                if vertice.select:
                    check_1u_overlap = True
                    break
        bpy.ops.object.mode_set(mode='OBJECT')
        n = ["1U重叠",check_1u_overlap,"布尔"]

    #2UV重叠判断
    if check_2uv_overlap_switch:
        check_2u_overlap = False
        if len(obj.data.uv_layers) >= 1:
            obj.data.uv_layers.active_index = 0
            bpy.context.scene.tool_settings.use_uv_select_sync = True
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.uv.select_all(action='DESELECT')
            bpy.ops.uv.select_overlap(extend=False)
            for vertice in obj.data.vertices:
                if vertice.select:
                    check_2u_overlap = True
                    break
        bpy.ops.object.mode_set(mode='OBJECT')
        o = ["2U重叠",check_2u_overlap,"布尔"]

    #Xfrom检查
    if check_xfrom_switch:
        check_xfrom = False
        if (obj.rotation_euler[0], obj.rotation_euler[1], obj.rotation_euler[2]) != (0, 0, 0):
            check_xfrom = True
        if (obj.scale[0], obj.scale[1], obj.scale[2]) != (1, 1, 1):
            check_xfrom = True
        p = ["变换归零",check_xfrom,"布尔"]

    #动画数据检查
    if check_ani_switch:
        check_ani = False
        if obj.animation_data is not None:
            if len(obj.animation_data.action.fcurves) != 0:
                check_ani = True
        q = ["动画",check_ani,"布尔"]

    #修改器检查
    if check_modifier_switch:
        check_modifier = False
        if len(obj.modifiers) != 0:
            check_modifier = True
        u = ["修改器",check_modifier,"布尔"]

    # 数据列表
    check_data_list = [a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,u]
    data_list = list(filter(None, check_data_list))
    data_list_out.append(data_list)
    
    # 打印
    counter = counter + 1     
    print(counter,'/',len(obj_name_list),obj_name)