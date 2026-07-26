import bpy
import os
# 导入人物
Fbx_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "资源", "地面.fbx")
bpy.ops.wm.fbx_import(filepath=Fbx_Path, mtl_name_collision_mode='REFERENCE_EXISTING')
# 清空变换
bpy.ops.object.location_clear()
bpy.ops.object.rotation_clear()
bpy.ops.object.scale_clear()