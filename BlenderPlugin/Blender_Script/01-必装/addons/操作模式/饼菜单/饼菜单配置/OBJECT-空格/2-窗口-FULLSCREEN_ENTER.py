import bpy
#打开窗口
bpy.ops.wm.window_new()
bpy.context.area.ui_type = 'OUTLINER'
bpy.context.space_data.display_mode = 'LIBRARIES'
bpy.context.space_data.filter_id_type = 'IMAGE'
bpy.context.space_data.use_filter_id_type = True
bpy.ops.screen.area_split(direction='VERTICAL', factor=0.2)
bpy.context.area.ui_type = 'OUTLINER'
bpy.context.space_data.display_mode = 'LIBRARIES'
bpy.context.space_data.filter_id_type = 'MATERIAL'
bpy.context.space_data.use_filter_id_type = True
bpy.ops.screen.area_split(direction='VERTICAL', factor=0.75)
bpy.context.area.ui_type = 'IMAGE_EDITOR'