import bpy
import os
os.system('cls')

print('1/4')
guid_data_lsit = []
for obj in bpy.context.view_layer.objects.selected:
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
        guid_data_lsit.append(data)
bpy.ops.object.select_all(action='DESELECT')
print('2/4')
all_data_lsit = []
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
        all_data_lsit.append(data)
print('3/4')
for guid_data in guid_data_lsit:
    GUID = bpy.data.objects[guid_data[0]]['Messiah_GUID']
    # 找相同的列表数据
    matching_items = [item[0] for item in all_data_lsit if item[1] == guid_data[1]]
    for obj_name in matching_items:
            bpy.data.objects[obj_name]['Messiah_GUID'] = GUID
print('完成')