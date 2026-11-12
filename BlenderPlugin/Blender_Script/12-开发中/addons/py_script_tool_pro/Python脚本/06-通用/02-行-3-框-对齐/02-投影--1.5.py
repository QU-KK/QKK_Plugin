import bpy
suffix = '_shadowProxy'
for obj in bpy.context.selected_objects:
    name = obj.name    
    if suffix not in name:
        obj.name = name + suffix