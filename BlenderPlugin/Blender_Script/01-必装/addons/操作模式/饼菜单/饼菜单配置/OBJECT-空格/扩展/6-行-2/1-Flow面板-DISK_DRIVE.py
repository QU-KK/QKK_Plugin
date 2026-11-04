import bpy
import ctypes

bpy.ops.wm.window_new()
new_window = bpy.context.window_manager.windows[-1]

for area in new_window.screen.areas:
  area.ui_type = 'FlowNodeTree'
  
  user32 = ctypes.windll.user32
  hwnd = user32.GetForegroundWindow()

  # 设定位置 (x=200, y=200) 与 尺寸 (宽=300, 高=600)
  user32.MoveWindow(hwnd, 1200, 200, 600, 1000, True)