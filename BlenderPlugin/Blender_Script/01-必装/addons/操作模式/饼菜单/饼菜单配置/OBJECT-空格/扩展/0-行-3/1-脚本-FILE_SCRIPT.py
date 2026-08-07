import bpy
#打开N面板
bpy.ops.sna.refresh_path_5ca64()
bpy.context.space_data.show_region_ui = True

for r in bpy.context.area.regions:
    if r.type == 'UI':
        r.active_panel_category = "Python"
        r.tag_redraw()
        break