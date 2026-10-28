import bpy

selected_objects = bpy.context.selected_objects

for obj in selected_objects:
    keys_to_remove = [key for key in obj.keys() if key not in obj.rna_type.bl_rna.properties]
    for key in keys_to_remove:
        del obj[key]
    
    if "_lod0" in obj.name:
        obj["hgSceneModelPlatformData"] = '{"pc": true, "mobile": false}'
    
    if "_lod1" in obj.name or "_lod2" in obj.name or "_lod3" in obj.name or "_lod4" in obj.name or "_lod6" in obj.name or "_lod6" in obj.name:
        obj["hgSceneModelPlatformData"] = '{"pc": true, "mobile": true}'