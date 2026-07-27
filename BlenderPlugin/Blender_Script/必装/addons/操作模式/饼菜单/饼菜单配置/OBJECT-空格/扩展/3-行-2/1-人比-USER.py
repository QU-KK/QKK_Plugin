import bpy
import os
# 导入人物
Fbx_Path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "调用","资源","人物.fbx")
bpy.ops.wm.fbx_import(filepath=Fbx_Path, mtl_name_collision_mode='REFERENCE_EXISTING')
# 清空变换
bpy.ops.object.location_clear()
bpy.ops.object.rotation_clear()
bpy.ops.object.scale_clear()

# 设置材质
bpy.context.object.active_material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0,0,0,1)
bpy.context.object.active_material.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value = 0
bpy.context.object.active_material.diffuse_color = (1,1,1,1)
