import bpy

def enable_addon_with_timer(module_name):
    """使用定时器延迟启用插件"""
    def timer_callback():
        try:
            if hasattr(bpy.context, 'preferences') and module_name not in bpy.context.preferences.addons:
                bpy.ops.preferences.addon_enable(module=module_name)
                print(f"强制启动: {module_name}")
            return None  # 停止定时器
        except:
            return 0.1  # 0.1秒后重试

    bpy.app.timers.register(timer_callback, first_interval=0.1)

def register():
    enable_addon_with_timer("插件管理器")  # 模块名
