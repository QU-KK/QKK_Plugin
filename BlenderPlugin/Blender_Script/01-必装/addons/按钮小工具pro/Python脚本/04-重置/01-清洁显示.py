import bpy

bpy.context.space_data.overlay.show_axis_x = False
bpy.context.space_data.overlay.show_axis_y = False
bpy.context.space_data.overlay.show_axis_z = False
bpy.context.space_data.overlay.show_cursor = False
bpy.context.space_data.overlay.show_annotation = False
bpy.context.space_data.overlay.show_performance = False
bpy.context.space_data.overlay.show_text = True
bpy.context.space_data.overlay.show_stats = True

bpy.context.scene.render.filter_size = 0
bpy.context.scene.eevee.use_taa_reprojection = False
bpy.context.scene.eevee.use_shadow_jitter_viewport = False
bpy.context.scene.render.film_transparent = True
