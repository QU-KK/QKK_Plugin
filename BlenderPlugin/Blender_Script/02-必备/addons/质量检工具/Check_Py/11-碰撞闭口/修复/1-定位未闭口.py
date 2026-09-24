import bpy
import bmesh

# 1. 获取所有当前选中的网格对象（过滤掉相机、灯光等非网格物体）
selected_meshes = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']

if not selected_meshes:
    print("错误：请先在场景中至少选择一个网格（Mesh）对象！")
else:
    # 确保我们在物体模式下初始化，避免因当前处于其他模式导致状态混乱
    if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
        
    # 必须保证当前有一个"活动对象"且为网格，才能顺利执行进入编辑模式的命令
    bpy.context.view_layer.objects.active = selected_meshes[0]
    
    # 2. 切换到编辑模式 (Blender会将所有被选中的对象同时切入编辑模式)
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 3. 设置选择模式为“边模式”
    bpy.ops.mesh.select_mode(type="EDGE")
    
    # 4. 取消当前所有选中状态 (此操作会对所有已进入编辑模式的模型生效)
    bpy.ops.mesh.select_all(action='DESELECT')
    
    total_selected_count = 0
    
    # 5. 遍历每一个被选中的网格对象
    for obj in selected_meshes:
        # 获取当前对象的 Edit Mesh 的 BMesh 数据
        bm = bmesh.from_edit_mesh(obj.data)
        
        # 遍历该对象的所有边，选中未闭口边（连接的面数量小于 2 的边）
        for edge in bm.edges:
            if len(edge.link_faces) < 2:
                edge.select = True
                total_selected_count += 1
                
        # 6. 刷新当前网格的状态显示，使选择生效
        bmesh.update_edit_mesh(obj.data)
        
    print(f"操作完成：已在 {len(selected_meshes)} 个模型中，选中了 {total_selected_count} 条未闭口边。")