import bpy
import os
os.system('cls')

print('开始统计数据')
bpy.ops.object.select_all(action='DESELECT')
obj_lsit = []
for obj in bpy.data.objects:
    if obj.data.id_type == 'MESH':
        data = obj.data
        vertices=len(data.vertices)
        edges=len(data.edges)
        polygons=len(data.polygons)
        triangle=len(data.loop_triangle_polygons)
        vertice_p0 = str(obj.data.vertices[0].undeformed_co)
        vertice_p1 = str(obj.data.vertices[0].undeformed_co)
        vertice_p2 = str(obj.data.vertices[0].undeformed_co)
        data = [obj.name,(vertices,edges,polygons,triangle,vertice_p0,vertice_p1,vertice_p2)]
        obj_lsit.append(data)
print('开始唯一化数据')
# 创建一个集合来跟踪出现过的第二个元素
seen = set()
unique_data = []
for item in obj_lsit:
    if item[1] not in seen:
        unique_data.append(item)
        seen.add(item[1])
print('开始选择')
progress=0
for obj in unique_data:
    obj = bpy.data.objects[obj[0]] # 按名称获取物体
    obj.select_set(True) # 选中模型
    progress = progress + 1
    print(progress , '/' , len(unique_data))
print('开始反选')
bpy.ops.object.select_all(action='INVERT')
print('开始删除耐心等待')
bpy.ops.object.delete(use_global=True)
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
print('完成')