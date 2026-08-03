import bpy
#lod全显示
data = ['_lod0','_lod1','_lod2','_lod3']
for obj in bpy.data.objects:
    for i in data:
        if i in obj.name:
            obj.hide_set(False)