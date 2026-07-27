import bpy
# 新建面片
bpy.ops.mesh.primitive_plane_add()

# 平滑着色
bpy.ops.object.shade_auto_smooth(use_auto_smooth=True, angle=0.8)
bpy.ops.object.convert(target='MESH')