keyconfig_version = (5, 2, 2)  # 键位配置版本号
# 键位配置数据，原生精简键位
keyconfig_data = \
[
# 窗口
 ("Window",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("wm.save_mainfile", {"type": 'S', "value": 'PRESS', "ctrl": True}, None),  # 窗口：保存主文件
    ("wm.save_as_mainfile", {"type": 'S', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 窗口：另存为主文件
    ("wm.call_panel", {"type": 'NDOF_BUTTON_MENU', "value": 'PRESS'}, {"properties": [("name", 'USERPREF_PT_ndof_settings')]}),  # 窗口：打开面板
    ("wm.context_scale_float", {"type": 'NDOF_BUTTON_PLUS', "value": 'PRESS'}, {"properties": [("data_path", 'preferences.inputs.ndof_sensitivity'), ("value", 1.1)]}),  # 窗口：缩放浮点值
    ("wm.context_scale_float", {"type": 'NDOF_BUTTON_MINUS', "value": 'PRESS'}, {"properties": [("data_path", 'preferences.inputs.ndof_sensitivity'), ("value", 0.9)]}),  # 窗口：缩放浮点值
    ("wm.context_scale_float", {"type": 'NDOF_BUTTON_PLUS', "value": 'PRESS', "shift": True}, {"properties": [("data_path", 'preferences.inputs.ndof_sensitivity'), ("value", 1.5)]}),  # 窗口：缩放浮点值
    ("wm.context_scale_float", {"type": 'NDOF_BUTTON_MINUS', "value": 'PRESS', "shift": True}, {"properties": [("data_path", 'preferences.inputs.ndof_sensitivity'), ("value", 0.6)]}),  # 窗口：缩放浮点值
    ("info.reports_display_update", {"type": 'TIMER_REPORT', "value": 'ANY', "any": True}, None),  # 信息：刷新报告显示
    ("wm.doc_view_manual_ui_context", {"type": 'F1', "value": 'PRESS'}, None),  # 窗口：查看手册(UI上下文)
    ("wm.search_menu", {"type": 'F3', "value": 'PRESS'}, None),  # 窗口：搜索菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 3D视图-3D视图(全局)
 ("3D View",
  {"space_type": 'VIEW_3D', "region_type": 'WINDOW'},  # 3D视图(全局)   空间类型：3D 视图；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("view3d.rotate", {"type": 'LEFTMOUSE', "value": 'PRESS', "alt": True}, None),  # 3D视图：旋转
    ("view3d.move", {"type": 'MIDDLEMOUSE', "value": 'PRESS', "alt": True}, None),  # 3D视图：移动
    ("view3d.zoom", {"type": 'RIGHTMOUSE', "value": 'PRESS', "alt": True}, None),  # 3D视图：缩放
    ("view3d.view_selected", {"type": 'F', "value": 'PRESS'}, {"properties": [("use_all_regions", True)]}),  # 3D视图：查看选中
    ("view3d.smoothview", {"type": 'TIMER1', "value": 'ANY', "any": True}, None),  # 3D视图：平滑视图
    ("view3d.zoom", {"type": 'WHEELUPMOUSE', "value": 'PRESS', "alt": True}, {"properties": [("delta", 1)]}),  # 3D视图：缩放
    ("view3d.zoom", {"type": 'WHEELDOWNMOUSE', "value": 'PRESS', "alt": True}, {"properties": [("delta", -1)]}),  # 3D视图：缩放
    ("view3d.zoom", {"type": 'WHEELINMOUSE', "value": 'PRESS'}, {"properties": [("delta", 1)]}),  # 3D视图：缩放
    ("view3d.zoom", {"type": 'WHEELOUTMOUSE', "value": 'PRESS'}, {"properties": [("delta", -1)]}),  # 3D视图：缩放
    ("view3d.select", {"type": 'LEFTMOUSE', "value": 'CLICK'}, {"properties": [("deselect_all", True)]}),  # 3D视图：选择
    ("view3d.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True}, {"properties": [("toggle", True)]}),  # 3D视图：选择
    ("view3d.copybuffer", {"type": 'C', "value": 'PRESS', "ctrl": True}, {"active": False}),  # 3D视图：复制到缓冲
    ("view3d.pastebuffer", {"type": 'V', "value": 'PRESS', "ctrl": True}, {"active": False}),  # 3D视图：从缓冲粘贴
    ("wm.tool_set_by_id", {"type": 'Q', "value": 'PRESS'}, {"properties": [("name", 'builtin.select_box'), ("cycle", False)]}),  # 窗口：切换工具
    #("view3d.view_center_camera", {"type": 'HOME', "value": 'PRESS'}, None),  # 3D视图：摄像机居中视图
    #("view3d.view_all", {"type": 'HOME', "value": 'PRESS'}, {"properties": [("center", False)]}),  # 3D视图：查看全部
    #("view3d.navigate", {"type": 'ACCENT_GRAVE', "value": 'PRESS', "shift": True}, None),  # 3D视图：导航
    #("view3d.localview", {"type": 'NUMPAD_SLASH', "value": 'PRESS'}, None),  # 3D视图：局部视图
    #("view3d.localview_remove_from", {"type": 'NUMPAD_SLASH', "value": 'PRESS', "alt": True}, None),  # 3D视图：移出局部视图
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 3D视图-物体模式
 ("Object Mode",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 物体模式去(全局)空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("object.select_all", {"type": 'A', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'SELECT')]}),  # 对象：全选
    ("object.delete", {"type": 'DEL', "value": 'PRESS'}, {"properties": [("use_global", False), ("confirm", False)]}),  # 对象：删除
    ("object.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 对象：复制并移动
    ("object.duplicate_move_linked", {"type": 'D', "value": 'PRESS', "alt": True}, {"active": False}),  # 对象：复制并移动(关联)
    ("object.move_to_collection", {"type": 'M', "value": 'PRESS'}, None),  # 对象：移动到集合
    ("object.subdivision_set", {"type": 'ONE', "value": 'PRESS'}, {"properties": [("level", 0), ("relative", False)]}),  # 对象：设置细分
    ("object.subdivision_set", {"type": 'TWO', "value": 'PRESS'}, {"properties": [("level", 1), ("relative", False)]}),  # 对象：设置细分
    ("object.subdivision_set", {"type": 'THREE', "value": 'PRESS'}, {"properties": [("level", 2), ("relative", False)]}),  # 对象：设置细分
    ("object.subdivision_set", {"type": 'THREE', "value": 'PRESS'}, {"properties": [("level", 3), ("relative", False)]}),  # 对象：设置细分
    ("wm.tool_set_by_id", {"type": 'W', "value": 'PRESS'}, {"properties": [("name", 'builtin.move')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'E', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.rotate')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'R', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.scale')]}),  # 窗口：切换工具
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 3D视图-网格
 ("Mesh",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("mesh.loop_select", {"type": 'LEFTMOUSE', "value": 'DOUBLE_CLICK'}, None),  # 网格：循环边选择
    ("mesh.loop_select", {"type": 'LEFTMOUSE', "value": 'DOUBLE_CLICK', "shift": True}, {"properties": [("extend", True), ("toggle", False)]}),  # 网格：循环边选择
    ("mesh.shortest_path_pick", {"type": 'LEFTMOUSE', "value": 'RELEASE', "ctrl": True}, {"properties": [("use_fill", False)]}),  # 网格：最短路径点选
    ("mesh.select_all", {"type": 'A', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'SELECT')]}),  # 网格：全选
    ("mesh.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 网格：复制并移动
    ("wm.call_menu", {"type": 'DEL', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_mesh_delete')]}),  # 窗口：打开菜单
    ("mesh.knife_tool", {"type": 'K', "value": 'PRESS'}, {"properties": [("use_occlude_geometry", True), ("only_selected", False)]}),  # 网格：刻刀工具
    ("wm.call_menu", {"type": 'U', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_uv_map')]}),  # 窗口：打开菜单
    ("wm.tool_set_by_id", {"type": 'Q', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.select_box')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'W', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.move')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'E', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.rotate')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'R', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.scale')]}),  # 窗口：切换工具
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 3D视图-曲线-曲线(全局)(常规曲线)
 ("Curve",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("curve.select_all", {"type": 'A', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'SELECT')]}),  # 曲线：全选
    ("curve.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 曲线：复制并移动
    ("wm.call_menu", {"type": 'DEL', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_curve_delete')]}),  # 曲线：打开菜单(删除)
    ("wm.tool_set_by_id", {"type": 'Q', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.select_box')]}),  # 曲线：切换工具(框选)
    ("wm.tool_set_by_id", {"type": 'W', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.move')]}),  # 曲线：切换工具(移动)
    ("wm.tool_set_by_id", {"type": 'E', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.rotate')]}),  # 曲线：切换工具(旋转)
    ("wm.tool_set_by_id", {"type": 'R', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.scale')]}),  # 曲线：切换工具(缩放)
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 3D视图-曲线(毛发曲线)
# 曲线（Curves）
 ("Curves",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("curves.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 曲线：复制并移动
    ("curves.select_all", {"type": 'A', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'SELECT')]}),  # 曲线：全选
    ("curves.delete", {"type": 'DEL', "value": 'PRESS'}, None),  # 曲线：删除
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 3D视图-顶点绘制
 ("Vertex Paint",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  #顶点色绘制(全局) 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("paint.vertex_paint", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),  # 绘制：顶点绘制
    ("paint.vertex_paint", {"type": 'LEFTMOUSE', "value": 'PRESS', "ctrl": True}, {"properties": [("mode", 'INVERT')], "active": False}),  # 绘制：顶点绘制
    ("paint.brush_colors_flip", {"type": 'X', "value": 'PRESS'}, {"active": False}),  # 绘制：翻转笔刷颜色
    ("paint.sample_color", {"type": 'X', "value": 'PRESS', "shift": True}, {"properties": [("merged", False)], "active": False}),  # 绘制：取样颜色
    ("paint.vertex_color_set", {"type": 'X', "value": 'PRESS', "ctrl": True}, {"active": False}),  # 绘制：设置顶点颜色
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 图像-UV编辑器-UV编辑器(全局)
 ("UV Editor",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # UV编辑器(全局)   空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("uv.select", {"type": 'LEFTMOUSE', "value": 'CLICK'}, {"properties": [("deselect_all", True)]}),  # UV：选择
    ("uv.select", {"type": 'LEFTMOUSE', "value": 'ANY', "shift": True}, {"properties": [("extend", True), ("toggle", False), ("deselect_all", False), ("select_passthrough", False)]}),  # UV：选择
    ("uv.shortest_path_pick", {"type": 'LEFTMOUSE', "value": 'CLICK', "ctrl": True}, {"properties": [("use_fill", False)]}),  # UV：最短路径点选
    ("uv.shortest_path_pick", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True, "ctrl": True}, {"properties": [("use_fill", True)]}),  # UV：最短路径点选
    ("uv.select_all", {"type": 'A', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'SELECT')]}),  # UV：全选
    ("wm.tool_set_by_id", {"type": 'W', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.move')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'E', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.rotate')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'R', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.scale')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'Q', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.select_box')]}),  # 窗口：切换工具
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

# 帧
 ("Frames",
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("screen.frame_offset", {"type": 'LEFT_ARROW', "value": 'PRESS', "repeat": True}, {"properties": [("delta", -1)]}),  # 屏幕：帧偏移
    ("screen.frame_offset", {"type": 'RIGHT_ARROW', "value": 'PRESS', "repeat": True}, {"properties": [("delta", 1)]}),  # 屏幕：帧偏移
    ("screen.frame_jump", {"type": 'RIGHT_ARROW', "value": 'PRESS', "shift": True, "repeat": True}, {"properties": [("end", True)]}),  # 屏幕：跳帧
    ("screen.frame_jump", {"type": 'LEFT_ARROW', "value": 'PRESS', "shift": True, "repeat": True}, {"properties": [("end", False)]}),  # 屏幕：跳帧
    ("screen.keyframe_jump", {"type": 'UP_ARROW', "value": 'PRESS', "repeat": True}, {"properties": [("next", True)]}),  # 屏幕：关键帧跳转
    ("screen.keyframe_jump", {"type": 'DOWN_ARROW', "value": 'PRESS', "repeat": True}, {"properties": [("next", False)]}),  # 屏幕：关键帧跳转 
    ("screen.animation_play", {"type": 'SPACE', "value": 'CLICK', "shift": True}, None),  # 屏幕：播放动画
    ("screen.animation_cancel", {"type": 'ESC', "value": 'PRESS'}, None),  # 屏幕：停止动画
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

]


if __name__ == "__main__":  # 主程序入口（在 Blender 中导入键位表）
    # 只添加当前 Blender 版本支持的关键字
    from bpy.app import version as blender_version  # 导入 Blender 版本号
    keywords = {}  # 关键字字典
    if blender_version >= (2, 92, 0):  # 2.92 及以上才支持版本号
        keywords["keyconfig_version"] = keyconfig_version  # 写入键位配置版本
    import os  # 导入 os 模块
    from bl_keymap_utils.io import keyconfig_import_from_data  # 导入键位导入函数
    keyconfig_import_from_data(  # 执行键位数据导入
        os.path.splitext(os.path.basename(__file__))[0],  # 用文件名作为键位表名
        keyconfig_data,  # 键位数据
        **keywords,  # 额外关键字参数
    )

