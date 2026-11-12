import bpy
obj_list = []
for obj in bpy.context.selected_objects:
    if obj.name[-5:] == '_lod0':
        obj_list.append(obj)
        
a=0
for obj in obj_list:
    bpy.context.view_layer.objects.active = obj
    a+=1
    bpy.ops.material.sync_from_unity()
    data = str(a)+'/'+str(len(obj_list))
    print(data)