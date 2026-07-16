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
print('开始分组')
# 创建一个字典来存储分组
grouped_data = {}
for item in obj_lsit:
    key = item[1]  # 使用坐标作为键
    if key not in grouped_data:
        grouped_data[key] = []  # 如果键不存在，初始化列表
    grouped_data[key].append(item[0])  # 将名称添加到相应的列表中
# 只保留名称列表
result = [names for names in grouped_data.values()]
print('开始分配mesh')
a = 0
for data in result:
    mesh = bpy.data.objects[data[0]].data
    for list_data in data:
        bpy.data.objects[list_data].data = mesh
    a=a+1
    print(a,'/',len(result))
print('清理残留mesh数据')
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
print('完成')