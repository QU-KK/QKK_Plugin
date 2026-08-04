import bpy
#打开面板浮窗
#bpy.ops.sna.shader_mat_2f193()


#打开N面板
bpy.context.space_data.show_region_ui = True

for r in bpy.context.area.regions:
    if r.type == 'UI':
        r.active_panel_category = "材质"
        r.tag_redraw()
        break  # 找到 UI 区域处理完毕后立即跳出循环，精简且高效