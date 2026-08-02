import bpy
import os
os.system('cls')
#bpy.ops.wm.console_toggle()

obj_name_list = []
for obj in bpy.context.view_layer.objects.selected:
    if obj.data.id_type == 'MESH':
        obj_name_list.append(obj.name)

bpy.ops.object.select_all(action='DESELECT')
for i_62AFA in range(len(obj_name_list)):
    bpy.ops.object.select_pattern(pattern=obj_name_list[i_62AFA], case_sensitive=True, extend=False)
    bpy.context.view_layer.objects.active = bpy.data.objects[obj_name_list[i_62AFA]]
    bpy.ops.mesh.separate(type='MATERIAL')
    obj_name = bpy.context.view_layer.objects.active.name
    for i_1F4D7 in range(len(bpy.context.view_layer.objects.selected)):
        bpy.context.view_layer.objects.selected[i_1F4D7].name = obj_name + '_c' + str(int(i_1F4D7 + 1.0)) + '_lod0'

#bpy.ops.wm.console_toggle()