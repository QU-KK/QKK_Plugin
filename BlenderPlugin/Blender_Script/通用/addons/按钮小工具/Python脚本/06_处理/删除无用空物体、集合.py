import bpy
#bpy.context.blend_data.collections

#for collection in bpy.context.view_layer.layer_collections:
    #if collection.exclude ==True or collection.hide_get() == True or collection.hide_viewport == True:


        #bpy.context.blend_data.collections.remove(collection=collection, do_unlink=True)

for obj in bpy.context.blend_data.objects:
    if obj.type == 'MESH':
        if obj.hide_get() == True or obj.hide_viewport == True:
            bpy.context.blend_data.objects.remove(object=obj, do_unlink=True)