import bpy
#清理缩放
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.object.mode_set(mode='EDIT')
#挤出
bpy.ops.sna.qkk_hard_edge_extrusion_dbef6('INVOKE_DEFAULT')