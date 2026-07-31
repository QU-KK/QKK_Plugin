import bpy
#清理缩放
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.object.mode_set(mode='EDIT')
# 均等内插
bpy.ops.mesh.inset('INVOKE_DEFAULT', use_even_offset=True, use_edge_rail=True)