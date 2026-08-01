import bpy
# 切割
bpy.ops.mesh.knife_tool('INVOKE_DEFAULT',use_occlude_geometry=True, only_selected=False, wait_for_input=True)