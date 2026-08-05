import bpy
# 新建相机
bpy.ops.object.camera_add()
bpy.context.scene.camera = bpy.context.active_object
bpy.ops.view3d.camera_to_view()
