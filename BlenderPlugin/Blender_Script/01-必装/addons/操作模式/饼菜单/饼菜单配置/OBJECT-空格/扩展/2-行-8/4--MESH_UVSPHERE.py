import bpy
# 新建经纬球
bpy.ops.mesh.primitive_uv_sphere_add()

# 平滑着色
bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=0.8)
bpy.ops.object.convert(target='MESH')
bpy.context.object.data.uv_layers[0].name = "1U"