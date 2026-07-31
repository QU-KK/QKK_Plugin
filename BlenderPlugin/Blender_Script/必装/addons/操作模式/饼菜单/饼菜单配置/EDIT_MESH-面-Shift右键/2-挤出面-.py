import bpy
#清理缩放
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.object.mode_set(mode='EDIT')
#挤出

def run_qkk_hard_edge_extrusion():
    wm = bpy.context.window_manager
    window = wm.windows[0]  # 当前主窗口

    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                # 核心点：HUD 和 GPU 渲染必须绑定在 WINDOW 区域上
                if region.type == 'WINDOW':
                    with bpy.context.temp_override(window=window, area=area, region=region):
                        bpy.ops.sna.qkk_hard_edge_extrusion_dbef6('INVOKE_DEFAULT')

                    return None

# 0.01 秒后延迟触发
bpy.app.timers.register(run_qkk_hard_edge_extrusion, first_interval=0)