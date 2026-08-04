import bpy
# 显示缝合
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.seams_from_islands()
bpy.ops.mesh.select_all(action='DESELECT')
bpy.context.space_data.overlay.show_edge_seams = not bpy.context.space_data.overlay.show_edge_seams
