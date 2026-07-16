import bpy
import os
os.system('cls')

bpy.ops.object.material_slot_remove_unused() # 清理空材质槽

objects = bpy.context.view_layer.objects # 视图物体
obj_name_list = [] # 物体名称列表
# 循环储存选中的物体名称到列表
for obj in objects.selected:
    obj_name_list.append(obj.name)

bpy.ops.object.select_all(action='DESELECT') # 取消选择

# 循环获取物体
progress=0
for obj_name in obj_name_list:
    obj = bpy.data.objects[obj_name] # 按名称获取物体
    objects.active = obj # 设置当前激活物体
    obj.select_set(True) # 选中模型
    mat_slot_ids = len(obj.material_slots) # 材质槽数量
    bpy.ops.object.mode_set(mode='EDIT') # 进入编辑模型

    # 循环获取材质槽
    for slots_id in range(mat_slot_ids):
        bpy.ops.mesh.select_all(action='DESELECT') # 取消mesh选择
        # 循环获取材质槽
        for id in range(mat_slot_ids):
            obj.active_material_index = id # 设置当前激活的材质槽
            # 判断当前材质槽名称是否相同
            if (obj.material_slots[slots_id].name == obj.material_slots[id].name):
                bpy.ops.object.material_slot_select() # 按材质槽选择面

        obj.active_material_index = slots_id # 设置当前激活的材质槽
        bpy.ops.object.material_slot_assign() # 将选中的面设置当前激活的材质槽
        bpy.ops.mesh.select_all(action='DESELECT') # 取消面选择

    bpy.ops.object.mode_set(mode='OBJECT') # 进入物体模式
    bpy.ops.object.material_slot_remove_unused() # 清理空材质槽
    obj.select_set(False) # 取消选中模型

    progress=progress + 1
    print(progress , '/' , len(obj_name_list) , '    ' , obj_name)