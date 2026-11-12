import bpy
import os
os.system('cls')

objects = bpy.context.view_layer.objects # 当前激活的视图物体
obj_name_lsit = []
# 筛选模型
for obj in objects.selected:
    if obj.data.id_type == 'MESH' and '_lod1' in obj.name or '_lod2' in obj.name or '_lod3' in obj.name:
        obj_name_lsit.append(obj.name)
    else:
         objects.active = obj # 设置为当前激活的物体

for obj_name in obj_name_lsit:
    print('删除：' + obj_name)
    bpy.context.blend_data.objects.remove(object=bpy.data.objects[obj_name])

bpy.ops.outliner.orphans_purge() # 清理未使用数据