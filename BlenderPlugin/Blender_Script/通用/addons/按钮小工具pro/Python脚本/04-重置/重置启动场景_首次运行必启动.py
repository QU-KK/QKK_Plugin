import bpy

# 1. 删除所有场景物体（含网格、灯光、摄像机等）
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# 2. 删除所有网格数据 (Meshes)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh, do_unlink=True)

# 3. 删除所有材质 (Materials)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat, do_unlink=True)

# 4. 删除所有导入/生成的图像 (Images)
for img in list(bpy.data.images):
    bpy.data.images.remove(img, do_unlink=True)

# 5. 彻底清理孤立残留缓存 (Purge Orphan Data)
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


bpy.context.space_data.overlay.show_axis_x = False
bpy.context.space_data.overlay.show_axis_y = False
bpy.context.space_data.overlay.show_axis_z = False
bpy.context.space_data.overlay.show_cursor = False
bpy.context.space_data.overlay.show_annotation = False
bpy.context.space_data.overlay.show_performance = False
bpy.context.space_data.overlay.show_text = True
bpy.context.space_data.overlay.show_stats = True

bpy.context.scene.render.filter_size = 0
bpy.context.scene.eevee.use_taa_reprojection = False
bpy.context.scene.eevee.use_shadow_jitter_viewport = False
bpy.context.scene.render.film_transparent = True



#bpy.ops.wm.save_homefile()