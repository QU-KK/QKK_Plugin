import bpy
#挤出

def run_omnioutset_with_hud():
    wm = bpy.context.window_manager
    window = wm.windows[0]  # 当前主窗口

    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                # 核心点：HUD 和 GPU 渲染必须绑定在 WINDOW 区域上
                if region.type == 'WINDOW':
                    with bpy.context.temp_override(window=window, area=area, region=region):
                        bpy.ops.mesh.omnioutset_smart_face('INVOKE_DEFAULT')

                    # 强制刷新该区域的绘图缓冲区
                    region.tag_redraw()
                    area.tag_redraw()
                    return None

# 0.01 秒后延迟触发
bpy.app.timers.register(run_omnioutset_with_hud, first_interval=0.01)