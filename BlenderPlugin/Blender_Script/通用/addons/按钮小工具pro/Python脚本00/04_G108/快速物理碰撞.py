import bpy
import os
os.system('cls')
objects = bpy.context.view_layer.objects # 当前激活的视图物体

if len(objects.selected) > 0:
    # 筛选模型
    for obj in objects.selected:
        if obj.data.id_type == 'MESH' and '_lod0' in obj.name: # 判断是否为模型  名称是否有 _lod0
            objects.active = obj # 设置为当前激活的物体
        else:
            obj.select_set(False) # 不选中模型

    # 清理修改器  清理UV  清理顶点色
    def clear_mesh(objects):
        bpy.context.object.modifiers.clear() # 清空修改器
        for i in objects.active.data.uv_layers:
            bpy.ops.mesh.uv_texture_remove() # 清理UV
        for i in objects.active.data.vertex_colors:
            bpy.ops.geometry.color_attribute_remove() # 清理顶点色


    bpy.ops.object.duplicate_move() # 复制模型
    bpy.ops.object.join() # 合并模型

    name_split = objects.active.name.split('_') # 拆分名称
    objects.active.name = name_split[0] + '_' + name_split[1] + '_' + name_split[2] + '_autophy' # 子弹碰撞命名
    clear_mesh(objects) # 执行清理

    bpy.ops.object.duplicate_move() # 复制模型
    objects.active.name = name_split[0] + '_' + name_split[1] + '_' + name_split[2] + '_autophy_s' # 行走碰撞命名
    bpy.ops.object.material_slot_remove_all( )# 清空所有材质槽
    bpy.ops.object.material_slot_add() # 增加材质槽
    clear_mesh(objects) # 执行清理