import bpy
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
Empty_list = []
for obj in bpy.context.selected_objects:
    if obj.type == 'EMPTY':
        Empty_list.append(obj)

progress = 0
for obj in Empty_list:
    if obj.type == 'EMPTY':
        bpy.data.objects.remove(object=obj, do_unlink=True, do_id_user=True, do_ui_user=True)
    progress += 1
    print(progress,'/',len(Empty_list))