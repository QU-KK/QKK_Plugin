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




 ("Curve",  # 键位表：曲线
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, {"active": False}),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, {"active": False}),  # 变换：调整大小
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, None),  # 变换：平移
    ("transform.bend", {"type": 'W', "value": 'PRESS', "shift": True}, None),  # 变换：弯曲
    ("transform.mirror", {"type": 'M', "value": 'PRESS', "ctrl": True}, None),  # 变换：镜像
    ("wm.call_menu", {"type": 'A', "value": 'PRESS', "shift": True}, {"properties": [("name", 'TOPBAR_MT_edit_curve_add')]}),  # 窗口：打开菜单
    ("curve.handle_type_set", {"type": 'V', "value": 'PRESS'}, {"active": False}),  # 曲线：设置控制柄类型
    ("curve.vertex_add", {"type": 'RIGHTMOUSE', "value": 'CLICK', "ctrl": True}, {"active": False}),  # 曲线：添加顶点
    ("curve.select_all", {"type": 'A', "value": 'PRESS'}, {"properties": [("action", 'SELECT')]}),  # 曲线：全选
    ("curve.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, {"properties": [("action", 'DESELECT')]}),  # 曲线：取消全选
    ("curve.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'INVERT')]}),  # 曲线：反选
    ("curve.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, {"properties": [("action", 'DESELECT')]}),  # 曲线：取消全选
    ("curve.select_row", {"type": 'R', "value": 'PRESS', "shift": True}, None),  # 曲线：选择整行
    ("curve.select_more", {"type": 'NUMPAD_PLUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 曲线：扩大选择
    ("curve.select_less", {"type": 'NUMPAD_MINUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 曲线：缩小选择
    ("curve.select_linked", {"type": 'L', "value": 'PRESS', "ctrl": True}, None),  # 曲线：选择关联元素
    ("curve.select_similar", {"type": 'G', "value": 'PRESS', "shift": True}, None),  # 曲线：选择相似元素
    ("curve.select_linked_pick", {"type": 'L', "value": 'PRESS'}, {"properties": [("deselect", False)]}),  # 曲线：点选关联元素
    ("curve.select_linked_pick", {"type": 'L', "value": 'PRESS', "shift": True}, {"properties": [("deselect", True)]}),  # 曲线：点选关联元素
    ("curve.shortest_path_pick", {"type": 'LEFTMOUSE', "value": 'CLICK', "ctrl": True}, None),  # 曲线：最短路径点选
    ("curve.separate", {"type": 'P', "value": 'PRESS'}, None),  # 曲线：分离
    ("curve.split", {"type": 'Y', "value": 'PRESS'}, None),  # 曲线：分割
    ("curve.extrude_move", {"type": 'E', "value": 'PRESS'}, {"active": False}),  # 曲线：挤出并移动
    ("curve.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 曲线：复制并移动
    ("curve.make_segment", {"type": 'F', "value": 'PRESS'}, {"active": False}),  # 曲线：创建线段
    ("curve.cyclic_toggle", {"type": 'C', "value": 'PRESS', "alt": True}, None),  # 曲线：切换循环
    ("wm.call_menu", {"type": 'X', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_curve_delete')], "active": False}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'DEL', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_curve_delete')]}),  # 窗口：打开菜单
    ("curve.dissolve_verts", {"type": 'X', "value": 'PRESS', "ctrl": True}, None),  # 曲线：溶解顶点
    ("curve.dissolve_verts", {"type": 'DEL', "value": 'PRESS', "ctrl": True}, None),  # 曲线：溶解顶点
    ("curve.tilt_clear", {"type": 'T', "value": 'PRESS', "alt": True}, None),  # 曲线：清除倾斜
    ("transform.tilt", {"type": 'T', "value": 'PRESS', "ctrl": True}, None),  # 变换：倾斜
    ("transform.transform", {"type": 'S', "value": 'PRESS', "alt": True}, {"properties": [("mode", 'CURVE_SHRINKFATTEN')]}),  # 变换：变换
    ("curve.reveal", {"type": 'H', "value": 'PRESS', "alt": True}, None),  # 曲线：显示全部
    ("curve.hide", {"type": 'H', "value": 'PRESS'}, {"properties": [("unselected", False)]}),  # 曲线：隐藏
    ("curve.hide", {"type": 'H', "value": 'PRESS', "shift": True}, {"properties": [("unselected", True)]}),  # 曲线：隐藏
    ("curve.normals_make_consistent", {"type": 'N', "value": 'PRESS', "shift": True}, None),  # 曲线：法线一致
    ("object.vertex_parent_set", {"type": 'P', "value": 'PRESS', "ctrl": True}, None),  # 对象：设置顶点父级
    ("wm.call_menu", {"type": 'H', "value": 'PRESS', "ctrl": True}, {"properties": [("name", 'VIEW3D_MT_hook')], "active": False}),  # 窗口：打开菜单
    ("wm.call_menu_pie", {"type": 'O', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_proportional_editing_falloff_pie')], "active": False}),  # 窗口：打开饼菜单
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS'}, {"properties": [("data_path", 'tool_settings.use_proportional_edit')], "active": False}),  # 窗口：切换开关
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS', "alt": True}, {"properties": [("data_path", 'tool_settings.use_proportional_connected')], "active": False}),  # 窗口：切换开关
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_curve_context_menu')], "active": False}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_curve_context_menu')]}),  # 窗口：打开菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Curves",  # 键位表：曲线(多层)
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, {"active": False}),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, {"active": False}),  # 变换：调整大小
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, None),  # 变换：平移
    ("transform.bend", {"type": 'W', "value": 'PRESS', "shift": True}, None),  # 变换：弯曲
    ("transform.mirror", {"type": 'M', "value": 'PRESS', "ctrl": True}, None),  # 变换：镜像
    ("curves.set_selection_domain", {"type": 'ONE', "value": 'PRESS'}, {"properties": [("domain", 'POINT')]}),  # 曲线：设置选择域
    ("curves.set_selection_domain", {"type": 'TWO', "value": 'PRESS'}, {"properties": [("domain", 'CURVE')]}),  # 曲线：设置选择域
    ("curves.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 曲线：复制并移动
    ("curves.select_all", {"type": 'A', "value": 'PRESS'}, {"properties": [("action", 'SELECT')], "active": False}),  # 曲线：全选
    ("curves.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, {"properties": [("action", 'DESELECT')]}),  # 曲线：取消全选
    ("curves.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'INVERT')], "active": False}),  # 曲线：反选
    ("curves.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, {"properties": [("action", 'DESELECT')], "active": False}),  # 曲线：取消全选
    ("curves.extrude_move", {"type": 'E', "value": 'PRESS'}, {"active": False}),  # 曲线：挤出并移动
    ("curves.select_linked", {"type": 'L', "value": 'PRESS', "ctrl": True}, None),  # 曲线：选择关联元素
    ("curves.delete", {"type": 'X', "value": 'PRESS'}, {"active": False}),  # 曲线：删除
    ("curves.delete", {"type": 'DEL', "value": 'PRESS'}, None),  # 曲线：删除
    ("curves.select_more", {"type": 'NUMPAD_PLUS', "value": 'PRESS', "ctrl": True, "repeat": True}, {"active": False}),  # 曲线：扩大选择
    ("curves.select_less", {"type": 'NUMPAD_MINUS', "value": 'PRESS', "ctrl": True, "repeat": True}, {"active": False}),  # 曲线：缩小选择
    ("wm.call_menu_pie", {"type": 'O', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_proportional_editing_falloff_pie')]}),  # 窗口：打开饼菜单
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS'}, {"properties": [("data_path", 'tool_settings.use_proportional_edit')], "active": False}),  # 窗口：切换开关
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS', "alt": True}, {"properties": [("data_path", 'tool_settings.use_proportional_connected')], "active": False}),  # 窗口：切换开关
    ("curves.tilt_clear", {"type": 'T', "value": 'PRESS', "alt": True}, None),  # 曲线：清除倾斜
    ("transform.tilt", {"type": 'T', "value": 'PRESS', "ctrl": True}, None),  # 变换：倾斜
    ("transform.transform", {"type": 'S', "value": 'PRESS', "alt": True}, {"properties": [("mode", 'CURVE_SHRINKFATTEN')]}),  # 变换：变换
    ("curves.cyclic_toggle", {"type": 'C', "value": 'PRESS', "alt": True}, None),  # 曲线：切换循环
    ("curves.handle_type_set", {"type": 'V', "value": 'PRESS'}, {"active": False}),  # 曲线：设置控制柄类型
    ("wm.call_menu", {"type": 'A', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_edit_curves_add')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_curves_context_menu')], "active": False}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_curves_context_menu')]}),  # 窗口：打开菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

 ("Dopesheet",  # 键位表：动画摄影表
  {"space_type": 'DOPESHEET_EDITOR', "region_type": 'WINDOW'},  # 空间类型：动画摄影表；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("action.clickselect", {"type": 'LEFTMOUSE', "value": 'PRESS'}, {"properties": [("deselect_all", True)]}),  # 动画：点击选择
    ("action.clickselect", {"type": 'LEFTMOUSE', "value": 'PRESS', "alt": True}, {"properties": [("column", True)]}),  # 动画：点击选择
    ("action.clickselect", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True}, {"properties": [("extend", True)]}),  # 动画：点击选择
    ("action.clickselect", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True, "alt": True}, {"properties": [("extend", True), ("column", True)]}),  # 动画：点击选择
    ("action.clickselect", {"type": 'LEFTMOUSE', "value": 'PRESS', "ctrl": True, "alt": True}, {"properties": [("channel", True)]}),  # 动画：点击选择
    ("action.clickselect", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True, "ctrl": True, "alt": True}, {"properties": [("extend", True), ("channel", True)]}),  # 动画：点击选择
    ("action.select_leftright", {"type": 'LEFTMOUSE', "value": 'CLICK', "ctrl": True}, {"properties": [("mode", 'CHECK')]}),  # 动画：左右选择
    ("action.select_leftright", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True, "ctrl": True}, {"properties": [("mode", 'CHECK'), ("extend", True)]}),  # 动画：左右选择
    ("action.select_leftright", {"type": 'LEFT_BRACKET', "value": 'PRESS'}, {"properties": [("mode", 'LEFT')]}),  # 动画：左右选择
    ("action.select_leftright", {"type": 'RIGHT_BRACKET', "value": 'PRESS'}, {"properties": [("mode", 'RIGHT')]}),  # 动画：左右选择
    ("action.select_all", {"type": 'A', "value": 'PRESS'}, {"properties": [("action", 'SELECT')]}),  # 动画：全选
    ("action.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, {"properties": [("action", 'DESELECT')]}),  # 动画：取消全选
    ("action.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'INVERT')]}),  # 动画：反选
    ("action.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, {"properties": [("action", 'DESELECT')]}),  # 动画：取消全选
    ("action.select_box", {"type": 'B', "value": 'PRESS'}, {"properties": [("axis_range", False)]}),  # 动画：框选
    ("action.select_box", {"type": 'B', "value": 'PRESS', "alt": True}, {"properties": [("axis_range", True)]}),  # 动画：框选
    ("action.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"properties": [("mode", 'SET'), ("tweak", True)]}),  # 动画：框选
    ("action.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "shift": True}, {"properties": [("mode", 'ADD'), ("tweak", True)]}),  # 动画：框选
    ("action.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": True}, {"properties": [("mode", 'SUB'), ("tweak", True)]}),  # 动画：框选
    ("action.select_lasso", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "ctrl": True}, {"properties": [("mode", 'ADD')]}),  # 动画：套索选择
    ("action.select_lasso", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "shift": True, "ctrl": True}, {"properties": [("mode", 'SUB')]}),  # 动画：套索选择
    ("action.select_circle", {"type": 'C', "value": 'PRESS'}, None),  # 动画：圈选
    ("action.select_column", {"type": 'K', "value": 'PRESS'}, {"properties": [("mode", 'KEYS')]}),  # 动画：选择整列
    ("action.select_column", {"type": 'K', "value": 'PRESS', "ctrl": True}, {"properties": [("mode", 'CFRA')]}),  # 动画：选择整列
    ("action.select_column", {"type": 'K', "value": 'PRESS', "shift": True}, {"properties": [("mode", 'MARKERS_COLUMN')]}),  # 动画：选择整列
    ("action.select_column", {"type": 'K', "value": 'PRESS', "alt": True}, {"properties": [("mode", 'MARKERS_BETWEEN')]}),  # 动画：选择整列
    ("action.select_more", {"type": 'NUMPAD_PLUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 动画：扩大选择
    ("action.select_less", {"type": 'NUMPAD_MINUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 动画：缩小选择
    ("action.select_linked", {"type": 'L', "value": 'PRESS'}, None),  # 动画：选择关联元素
    ("action.frame_jump", {"type": 'G', "value": 'PRESS', "ctrl": True}, None),  # 动画：跳帧
    ("wm.call_menu_pie", {"type": 'S', "value": 'PRESS', "shift": True}, {"properties": [("name", 'DOPESHEET_MT_snap_pie')]}),  # 窗口：打开饼菜单
    ("action.mirror", {"type": 'M', "value": 'PRESS', "ctrl": True}, None),  # 动画：镜像
    ("action.handle_type", {"type": 'V', "value": 'PRESS'}, None),  # 动画：控制柄类型
    ("action.interpolation_type", {"type": 'T', "value": 'PRESS'}, None),  # 动画：插值类型
    ("action.extrapolation_type", {"type": 'E', "value": 'PRESS', "shift": True}, None),  # 动画：外推类型
    ("action.easing_type", {"type": 'E', "value": 'PRESS', "ctrl": True}, None),  # 动画：缓动类型
    ("action.keyframe_type", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 动画：关键帧类型
    ("action.bake_keys", {"type": 'O', "value": 'PRESS', "shift": True, "alt": True}, None),  # 动画：烘焙关键帧
    ("wm.call_menu", {"type": 'X', "value": 'PRESS'}, {"properties": [("name", 'DOPESHEET_MT_delete')]}),  # 窗口：打开菜单
    ("action.delete", {"type": 'DEL', "value": 'PRESS'}, {"properties": [("confirm", False)]}),  # 动画：删除
    ("action.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 动画：复制并移动
    ("action.keyframe_insert", {"type": 'I', "value": 'PRESS'}, None),  # 动画：插入关键帧
    ("action.copy", {"type": 'C', "value": 'PRESS', "ctrl": True}, None),  # 动画：复制
    ("action.paste", {"type": 'V', "value": 'PRESS', "ctrl": True}, None),  # 动画：粘贴
    ("action.paste", {"type": 'V', "value": 'PRESS', "shift": True, "ctrl": True}, {"properties": [("flipped", True)]}),  # 动画：粘贴
    ("action.previewrange_set", {"type": 'P', "value": 'PRESS', "ctrl": True, "alt": True}, None),  # 动画：设置预览范围
    ("action.view_all", {"type": 'HOME', "value": 'PRESS'}, None),  # 动画：查看全部
    ("action.view_all", {"type": 'NDOF_BUTTON_FIT', "value": 'PRESS'}, None),  # 动画：查看全部
    ("action.view_selected", {"type": 'NUMPAD_PERIOD', "value": 'PRESS'}, None),  # 动画：查看选中
    ("action.view_frame", {"type": 'NUMPAD_0', "value": 'PRESS'}, None),  # 动画：查看当前帧
    ("wm.call_menu_pie", {"type": 'ACCENT_GRAVE', "value": 'PRESS'}, {"properties": [("name", 'DOPESHEET_MT_view_pie')]}),  # 窗口：打开饼菜单
    ("anim.channels_editable_toggle", {"type": 'TAB', "value": 'PRESS'}, None),  # 动画：切换通道可编辑
    ("anim.channels_select_filter", {"type": 'F', "value": 'PRESS', "ctrl": True}, None),  # 动画：通道选择过滤
    ("transform.transform", {"type": 'G', "value": 'PRESS'}, {"properties": [("mode", 'TIME_TRANSLATE')]}),  # 变换：变换
    ("transform.transform", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"properties": [("mode", 'TIME_TRANSLATE')]}),  # 变换：变换
    ("transform.transform", {"type": 'E', "value": 'PRESS'}, {"properties": [("mode", 'TIME_EXTEND')]}),  # 变换：变换
    ("transform.transform", {"type": 'S', "value": 'PRESS'}, {"properties": [("mode", 'TIME_SCALE')]}),  # 变换：变换
    ("transform.transform", {"type": 'T', "value": 'PRESS', "shift": True}, {"properties": [("mode", 'TIME_SLIDE')]}),  # 变换：变换
    ("wm.call_menu_pie", {"type": 'O', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_proportional_editing_falloff_pie')]}),  # 窗口：打开饼菜单
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS'}, {"properties": [("data_path", 'tool_settings.use_proportional_action')]}),  # 窗口：切换开关
    ("marker.add", {"type": 'M', "value": 'PRESS'}, None),  # 标记：添加标记
    ("marker.camera_bind", {"type": 'B', "value": 'PRESS', "ctrl": True}, None),  # 标记：绑定摄像机
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'DOPESHEET_MT_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'DOPESHEET_MT_context_menu')]}),  # 窗口：打开菜单
    ("anim.change_frame", {"type": 'RIGHTMOUSE', "value": 'PRESS', "shift": True}, None),  # 动画：切换帧
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

 ("Grease Pencil Stroke Edit Mode",  # 键位表：蜡笔笔触编辑模式
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("gpencil.interpolate", {"type": 'E', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：插值
    ("gpencil.interpolate_sequence", {"type": 'E', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 蜡笔：序列插值
    ("gpencil.select_all", {"type": 'A', "value": 'PRESS'}, None),  # 蜡笔：全选
    ("gpencil.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, None),  # 蜡笔：全选
    ("gpencil.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：全选
    ("gpencil.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, None),  # 蜡笔：全选
    ("gpencil.select_circle", {"type": 'C', "value": 'PRESS'}, None),  # 蜡笔：圈选
    ("gpencil.select_box", {"type": 'B', "value": 'PRESS'}, None),  # 蜡笔：框选
    ("gpencil.select", {"type": 'LEFTMOUSE', "value": 'CLICK'}, None),  # 蜡笔：选择
    ("gpencil.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True}, None),  # 蜡笔：选择
    ("gpencil.select_linked", {"type": 'L', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：选择关联元素
    ("gpencil.select", {"type": 'L', "value": 'PRESS'}, None),  # 蜡笔：选择
    ("gpencil.select", {"type": 'L', "value": 'PRESS', "shift": True}, None),  # 蜡笔：选择
    ("gpencil.select_grouped", {"type": 'G', "value": 'PRESS', "shift": True}, None),  # 蜡笔：按组选择
    ("gpencil.select_more", {"type": 'NUMPAD_PLUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 蜡笔：扩大选择
    ("gpencil.select_less", {"type": 'NUMPAD_MINUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 蜡笔：缩小选择
    ("gpencil.select_lasso", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "ctrl": True}, None),  # 蜡笔：套索选择
    ("gpencil.select_lasso", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "shift": True, "ctrl": True}, None),  # 蜡笔：套索选择
    ("gpencil.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 蜡笔：复制并移动
    ("gpencil.extrude_move", {"type": 'E', "value": 'PRESS'}, None),  # 蜡笔：挤出并移动
    ("wm.call_menu", {"type": 'X', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_gpencil_delete')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'DEL', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_gpencil_delete')]}),  # 窗口：打开菜单
    ("gpencil.dissolve", {"type": 'X', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：溶解
    ("gpencil.dissolve", {"type": 'DEL', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：溶解
    ("gpencil.blank_frame_add", {"type": 'I', "value": 'PRESS', "shift": True}, None),  # 蜡笔：添加空白帧
    ("wm.call_menu", {"type": 'I', "value": 'PRESS', "alt": True}, {"properties": [("name", 'GPENCIL_MT_gpencil_draw_delete')]}),  # 窗口：打开菜单
    ("gpencil.active_frames_delete_all", {"type": 'DEL', "value": 'PRESS', "shift": True}, None),  # 蜡笔：删除所有活动帧
    ("gpencil.stroke_separate", {"type": 'P', "value": 'PRESS'}, None),  # 蜡笔：分离笔触
    ("gpencil.stroke_split", {"type": 'V', "value": 'PRESS'}, None),  # 蜡笔：分割笔触
    ("gpencil.stroke_join", {"type": 'J', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：连接笔触
    ("gpencil.stroke_join", {"type": 'J', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 蜡笔：连接笔触
    ("gpencil.stroke_cyclical_set", {"type": 'F', "value": 'PRESS'}, None),  # 蜡笔：设置笔触循环
    ("gpencil.copy", {"type": 'C', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：复制
    ("gpencil.paste", {"type": 'V', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：粘贴
    ("wm.call_menu_pie", {"type": 'S', "value": 'PRESS', "shift": True}, {"properties": [("name", 'GPENCIL_MT_snap_pie')]}),  # 窗口：打开饼菜单
    ("gpencil.reveal", {"type": 'H', "value": 'PRESS', "alt": True}, None),  # 蜡笔：显示全部
    ("gpencil.hide", {"type": 'H', "value": 'PRESS'}, None),  # 蜡笔：隐藏
    ("gpencil.hide", {"type": 'H', "value": 'PRESS', "shift": True}, None),  # 蜡笔：隐藏
    ("gpencil.selection_opacity_toggle", {"type": 'H', "value": 'PRESS', "ctrl": True}, None),  # 蜡笔：切换选择不透明度
    ("wm.context_toggle", {"type": 'Q', "value": 'PRESS', "shift": True}, {"properties": [("data_path", 'space_data.overlay.use_gpencil_edit_lines')]}),  # 窗口：切换开关
    ("wm.context_toggle", {"type": 'Q', "value": 'PRESS', "shift": True, "alt": True}, {"properties": [("data_path", 'space_data.overlay.use_gpencil_multiedit_line_only')]}),  # 窗口：切换开关
    ("gpencil.layer_isolate", {"type": 'NUMPAD_ASTERIX', "value": 'PRESS'}, None),  # 蜡笔：隔离图层
    ("wm.call_menu", {"type": 'M', "value": 'PRESS'}, {"properties": [("name", 'GPENCIL_MT_move_to_layer')]}),  # 窗口：打开菜单
    ("gpencil.layer_merge", {"type": 'M', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 蜡笔：合并图层
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, None),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, None),  # 变换：调整大小
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, None),  # 变换：平移
    ("transform.bend", {"type": 'W', "value": 'PRESS', "shift": True}, None),  # 变换：弯曲
    ("transform.mirror", {"type": 'M', "value": 'PRESS', "ctrl": True}, None),  # 变换：镜像
    ("transform.tosphere", {"type": 'S', "value": 'PRESS', "shift": True, "alt": True}, None),  # 变换：球形化
    ("transform.shear", {"type": 'S', "value": 'PRESS', "shift": True, "ctrl": True, "alt": True}, None),  # 变换：错切
    ("transform.transform", {"type": 'S', "value": 'PRESS', "alt": True}, None),  # 变换：变换
    ("transform.transform", {"type": 'F', "value": 'PRESS', "shift": True}, {"properties": [("mode", 'GPENCIL_OPACITY')]}),  # 变换：变换
    ("wm.call_menu_pie", {"type": 'O', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_proportional_editing_falloff_pie')]}),  # 窗口：打开饼菜单
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS'}, {"properties": [("data_path", 'tool_settings.use_proportional_edit')]}),  # 窗口：切换开关
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS', "alt": True}, {"properties": [("data_path", 'tool_settings.use_proportional_connected')]}),  # 窗口：切换开关
    ("wm.context_toggle", {"type": 'U', "value": 'PRESS'}, {"properties": [("data_path", 'gpencil_data.use_curve_edit')]}),  # 窗口：切换开关
    ("object.gpencil_add", {"type": 'A', "value": 'PRESS', "shift": True}, None),  # 对象：添加蜡笔对象
    ("wm.call_menu", {"type": 'G', "value": 'PRESS', "ctrl": True}, {"properties": [("name", 'GPENCIL_MT_gpencil_vertex_group')]}),  # 窗口：打开菜单
    ("gpencil.selectmode_toggle", {"type": 'ONE', "value": 'PRESS'}, None),  # 蜡笔：切换选择模式
    ("gpencil.selectmode_toggle", {"type": 'TWO', "value": 'PRESS'}, None),  # 蜡笔：切换选择模式
    ("gpencil.selectmode_toggle", {"type": 'THREE', "value": 'PRESS'}, None),  # 蜡笔：切换选择模式
    ("wm.call_menu", {"type": 'Y', "value": 'PRESS'}, {"properties": [("name", 'GPENCIL_MT_layer_active')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'I', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_gpencil_animation')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_gpencil_edit_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_gpencil_edit_context_menu')]}),  # 窗口：打开菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Image",  # 键位表：图像
  {"space_type": 'IMAGE_EDITOR', "region_type": 'WINDOW'},  # 空间类型：图像编辑器；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("image.view_all", {"type": 'HOME', "value": 'PRESS'}, None),  # 图像：查看全部
    ("image.view_all", {"type": 'HOME', "value": 'PRESS', "shift": True}, {"properties": [("fit_view", True)]}),  # 图像：查看全部
    ("image.view_selected", {"type": 'NUMPAD_PERIOD', "value": 'PRESS'}, None),  # 图像：查看选中
    ("image.view_cursor_center", {"type": 'C', "value": 'PRESS', "shift": True}, None),  # 图像：光标居中视图
    ("image.view_pan", {"type": 'MIDDLEMOUSE', "value": 'PRESS'}, None),  # 图像：平移视图
    ("image.view_pan", {"type": 'MIDDLEMOUSE', "value": 'PRESS', "alt": True}, None),  # 图像：平移视图
    ("image.view_pan", {"type": 'TRACKPADPAN', "value": 'ANY'}, None),  # 图像：平移视图
    ("image.view_all", {"type": 'NDOF_BUTTON_FIT', "value": 'PRESS'}, None),  # 图像：查看全部
    ("image.view_ndof", {"type": 'NDOF_MOTION', "value": 'ANY'}, None),  # 图像：NDOF视图
    ("image.view_zoom_in", {"type": 'WHEELINMOUSE', "value": 'PRESS'}, None),  # 图像：放大视图
    ("image.view_zoom_out", {"type": 'WHEELOUTMOUSE', "value": 'PRESS'}, None),  # 图像：缩小视图
    ("image.view_zoom_in", {"type": 'WHEELUPMOUSE', "value": 'PRESS', "alt": True}, None),  # 图像：放大视图
    ("image.view_zoom_out", {"type": 'WHEELDOWNMOUSE', "value": 'PRESS', "alt": True}, None),  # 图像：缩小视图
    ("image.view_zoom", {"type": 'MIDDLEMOUSE', "value": 'PRESS', "ctrl": True}, None),  # 图像：缩放视图
    ("image.view_zoom", {"type": 'TRACKPADZOOM', "value": 'ANY'}, None),  # 图像：缩放视图
    ("image.view_zoom", {"type": 'TRACKPADPAN', "value": 'ANY', "ctrl": True}, None),  # 图像：缩放视图
    ("image.view_zoom_border", {"type": 'B', "value": 'PRESS', "shift": True}, None),  # 图像：框选缩放
    ("image.view_zoom_ratio", {"type": 'NUMPAD_8', "value": 'PRESS', "ctrl": True}, {"properties": [("ratio", 8.0)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_4', "value": 'PRESS', "ctrl": True}, {"properties": [("ratio", 4.0)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_2', "value": 'PRESS', "ctrl": True}, {"properties": [("ratio", 2.0)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_8', "value": 'PRESS', "shift": True}, {"properties": [("ratio", 8.0)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_4', "value": 'PRESS', "shift": True}, {"properties": [("ratio", 4.0)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_2', "value": 'PRESS', "shift": True}, {"properties": [("ratio", 2.0)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_1', "value": 'PRESS'}, {"properties": [("ratio", 1.0)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_2', "value": 'PRESS'}, {"properties": [("ratio", 0.5)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_4', "value": 'PRESS'}, {"properties": [("ratio", 0.25)]}),  # 图像：缩放比例
    ("image.view_zoom_ratio", {"type": 'NUMPAD_8', "value": 'PRESS'}, {"properties": [("ratio", 0.125)]}),  # 图像：缩放比例
    ("image.change_frame", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),  # 图像：切换帧
    ("image.sample", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, None),  # 图像：取样
    ("image.curves_point_set", {"type": 'RIGHTMOUSE', "value": 'PRESS', "ctrl": True}, {"properties": [("point", 'BLACK_POINT')]}),  # 图像：设置曲线点
    ("image.curves_point_set", {"type": 'RIGHTMOUSE', "value": 'PRESS', "shift": True}, {"properties": [("point", 'WHITE_POINT')]}),  # 图像：设置曲线点
    ("object.mode_set", {"type": 'TAB', "value": 'PRESS'}, {"properties": [("mode", 'EDIT'), ("toggle", True)]}),  # 对象：设置模式
    ("wm.context_set_int", {"type": 'ONE', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 0)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'TWO', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 1)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'THREE', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 2)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'FOUR', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 3)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'FIVE', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 4)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'SIX', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 5)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'SEVEN', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 6)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'EIGHT', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 7)]}),  # 窗口：设置整数值
    ("wm.context_set_int", {"type": 'NINE', "value": 'PRESS'}, {"properties": [("data_path", 'space_data.image.render_slots.active_index'), ("value", 8)]}),  # 窗口：设置整数值
    ("image.render_border", {"type": 'B', "value": 'PRESS', "ctrl": True}, None),  # 图像：渲染边框
    ("image.clear_render_border", {"type": 'B', "value": 'PRESS', "ctrl": True, "alt": True}, None),  # 图像：清除渲染边框
    ("wm.context_toggle", {"type": 'ACCENT_GRAVE', "value": 'PRESS', "ctrl": True}, {"properties": [("data_path", 'space_data.show_gizmo')]}),  # 窗口：切换开关
    ("wm.context_toggle", {"type": 'Z', "value": 'PRESS', "shift": True, "alt": True}, {"properties": [("data_path", 'space_data.overlay.show_overlays')]}),  # 窗口：切换开关
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'IMAGE_MT_mask_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'IMAGE_MT_mask_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu_pie", {"type": 'PERIOD', "value": 'PRESS'}, {"properties": [("name", 'IMAGE_MT_pivot_pie')]}),  # 窗口：打开饼菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Image Editor Tool: Uv, Tweak",  # 键位表：图像编辑器工具：UV 调整
  {"space_type": 'IMAGE_EDITOR', "region_type": 'WINDOW'},  # 空间类型：图像编辑器；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("uv.select", {"type": 'LEFTMOUSE', "value": 'PRESS'}, {"properties": [("deselect_all", True), ("select_passthrough", True)]}),  # UV：选择
    ("uv.select", {"type": 'LEFTMOUSE', "value": 'CLICK'}, {"properties": [("deselect_all", True)]}),  # UV：选择
    ("uv.select", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True}, {"properties": [("toggle", True), ("deselect_all", False)]}),  # UV：选择
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Image Editor Tool: Uv, Tweak (fallback)",  # 键位表：图像编辑器工具：UV 调整(回退)
  {"space_type": 'IMAGE_EDITOR', "region_type": 'WINDOW'},  # 空间类型：图像编辑器；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("uv.select", {"type": 'LEFTMOUSE', "value": 'PRESS'}, {"properties": [("deselect_all", True), ("select_passthrough", True)]}),  # UV：选择
    ("uv.select", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True}, {"properties": [("toggle", True)]}),  # UV：选择
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"properties": [("release_confirm", True)]}),  # 变换：平移
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Lattice",  # 键位表：晶格
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, None),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, None),  # 变换：调整大小
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, None),  # 变换：平移
    ("transform.bend", {"type": 'W', "value": 'PRESS', "shift": True}, None),  # 变换：弯曲
    ("transform.mirror", {"type": 'M', "value": 'PRESS', "ctrl": True}, None),  # 变换：镜像
    ("transform.tosphere", {"type": 'S', "value": 'PRESS', "shift": True, "alt": True}, None),  # 变换：球形化
    ("transform.shear", {"type": 'S', "value": 'PRESS', "shift": True, "ctrl": True, "alt": True}, None),  # 变换：错切
    ("lattice.select_all", {"type": 'A', "value": 'PRESS'}, {"properties": [("action", 'SELECT')]}),  # 晶格：全选
    ("lattice.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, {"properties": [("action", 'DESELECT')]}),  # 晶格：取消全选
    ("lattice.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'INVERT')]}),  # 晶格：反选
    ("lattice.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, {"properties": [("action", 'DESELECT')]}),  # 晶格：取消全选
    ("lattice.select_more", {"type": 'NUMPAD_PLUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 晶格：扩大选择
    ("lattice.select_less", {"type": 'NUMPAD_MINUS', "value": 'PRESS', "ctrl": True, "repeat": True}, None),  # 晶格：缩小选择
    ("object.vertex_parent_set", {"type": 'P', "value": 'PRESS', "ctrl": True}, None),  # 对象：设置顶点父级
    ("lattice.flip", {"type": 'F', "value": 'PRESS', "alt": True}, None),  # 晶格：翻转
    ("wm.call_menu", {"type": 'H', "value": 'PRESS', "ctrl": True}, {"properties": [("name", 'VIEW3D_MT_hook')]}),  # 窗口：打开菜单
    ("wm.call_menu_pie", {"type": 'O', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_proportional_editing_falloff_pie')]}),  # 窗口：打开饼菜单
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS'}, {"properties": [("data_path", 'tool_settings.use_proportional_edit')]}),  # 窗口：切换开关
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_lattice_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_lattice_context_menu')]}),  # 窗口：打开菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束

 ("Metaball",  # 键位表：融球
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, None),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, None),  # 变换：调整大小
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, None),  # 变换：平移
    ("transform.mirror", {"type": 'M', "value": 'PRESS', "ctrl": True}, None),  # 变换：镜像
    ("object.metaball_add", {"type": 'A', "value": 'PRESS', "shift": True}, None),  # 对象：添加融球对象
    ("mball.reveal_metaelems", {"type": 'H', "value": 'PRESS', "alt": True}, None),  # 融球：显示全部融球元素
    ("mball.hide_metaelems", {"type": 'H', "value": 'PRESS'}, {"properties": [("unselected", False)]}),  # 融球：隐藏融球元素
    ("mball.hide_metaelems", {"type": 'H', "value": 'PRESS', "shift": True}, {"properties": [("unselected", True)]}),  # 融球：隐藏融球元素
    ("mball.delete_metaelems", {"type": 'X', "value": 'PRESS'}, None),  # 融球：删除融球元素
    ("mball.delete_metaelems", {"type": 'DEL', "value": 'PRESS'}, None),  # 融球：删除融球元素
    ("mball.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, None),  # 融球：复制并移动
    ("mball.select_all", {"type": 'A', "value": 'PRESS'}, {"properties": [("action", 'SELECT')]}),  # 融球：全选
    ("mball.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, {"properties": [("action", 'DESELECT')]}),  # 融球：取消全选
    ("mball.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'INVERT')]}),  # 融球：反选
    ("mball.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, {"properties": [("action", 'DESELECT')]}),  # 融球：取消全选
    ("mball.select_similar", {"type": 'G', "value": 'PRESS', "shift": True}, None),  # 融球：选择相似元素
    ("wm.call_menu_pie", {"type": 'O', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_proportional_editing_falloff_pie')]}),  # 窗口：打开饼菜单
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS'}, {"properties": [("data_path", 'tool_settings.use_proportional_edit')]}),  # 窗口：切换开关
    ("wm.context_toggle", {"type": 'O', "value": 'PRESS', "alt": True}, {"properties": [("data_path", 'tool_settings.use_proportional_connected')]}),  # 窗口：切换开关
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_metaball_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_edit_metaball_context_menu')]}),  # 窗口：打开菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Node Editor",  # 键位表：节点编辑器
  {"space_type": 'NODE_EDITOR', "region_type": 'WINDOW'},  # 空间类型：节点编辑器；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK'}, {"properties": [("deselect_all", True), ("select_passthrough", True)]}),  # 节点：选择
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "ctrl": True}, None),  # 节点：选择
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "alt": True}, None),  # 节点：选择
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "ctrl": True, "alt": True}, None),  # 节点：选择
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True}, {"properties": [("toggle", True)]}),  # 节点：选择
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True, "ctrl": True}, {"properties": [("toggle", True)]}),  # 节点：选择
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True, "alt": True}, {"properties": [("toggle", True)]}),  # 节点：选择
    ("node.select", {"type": 'LEFTMOUSE', "value": 'CLICK', "shift": True, "ctrl": True, "alt": True}, {"properties": [("toggle", True)]}),  # 节点：选择
    ("wm.tool_set_by_id", {"type": 'W', "value": 'PRESS'}, {"properties": [("name", 'builtin.select_box'), ("cycle", True)], "active": False}),  # 窗口：切换工具
    ("node.select_box", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"properties": [("tweak", True)]}),  # 节点：框选
    ("node.select_lasso", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": True, "alt": True}, {"properties": [("mode", 'ADD')]}),  # 节点：套索选择
    ("node.select_lasso", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "shift": True, "ctrl": True, "alt": True}, {"properties": [("mode", 'SUB')]}),  # 节点：套索选择
    ("node.select_box", {"type": 'B', "value": 'PRESS'}, {"properties": [("tweak", False)]}),  # 节点：框选
    ("node.select_circle", {"type": 'C', "value": 'PRESS'}, None),  # 节点：圈选
    ("node.link", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"properties": [("detach", False)]}),  # 节点：连接
    ("node.link", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "ctrl": True}, {"properties": [("detach", True)]}),  # 节点：连接
    ("node.resize", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, None),  # 节点：调整大小
    ("node.add_reroute", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "shift": True}, None),  # 节点：添加转接点
    ("node.links_cut", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "ctrl": True}, None),  # 节点：切断连接
    ("node.links_mute", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "ctrl": True, "alt": True}, None),  # 节点：静音连接
    ("node.select_link_viewer", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 节点：选择连接查看器
    ("node.connect_to_output", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True, "alt": True}, {"properties": [("run_in_geometry_nodes", True)]}),  # 节点：连接到输出
    ("node.connect_to_output", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True, "ctrl": True}, {"properties": [("run_in_geometry_nodes", False)]}),  # 节点：连接到输出
    ("node.connect_to_output", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True, "alt": True}, {"properties": [("run_in_geometry_nodes", False)]}),  # 节点：连接到输出
    ("node.backimage_move", {"type": 'MIDDLEMOUSE', "value": 'PRESS', "alt": True}, None),  # 节点：背景图移动
    ("node.backimage_zoom", {"type": 'V', "value": 'PRESS', "repeat": True}, {"properties": [("factor", 0.8333333)]}),  # 节点：背景图缩放
    ("node.backimage_zoom", {"type": 'V', "value": 'PRESS', "alt": True, "repeat": True}, {"properties": [("factor", 1.2)]}),  # 节点：背景图缩放
    ("node.backimage_fit", {"type": 'HOME', "value": 'PRESS', "alt": True}, None),  # 节点：背景图适配
    ("node.backimage_sample", {"type": 'RIGHTMOUSE', "value": 'PRESS', "alt": True}, None),  # 节点：背景图取样
    ("node.link_make", {"type": 'F', "value": 'PRESS'}, {"properties": [("replace", False)]}),  # 节点：建立连接
    ("node.link_make", {"type": 'F', "value": 'PRESS', "shift": True}, {"properties": [("replace", True)]}),  # 节点：建立连接
    ("wm.call_menu", {"type": 'A', "value": 'PRESS', "shift": True}, {"properties": [("name", 'NODE_MT_add')]}),  # 窗口：打开菜单
    ("node.duplicate_move", {"type": 'D', "value": 'PRESS', "shift": True}, {"properties": [("NODE_OT_translate_attach", [("TRANSFORM_OT_translate", [("view2d_edge_pan", True)])])]}),  # 节点：复制并移动
    ("node.duplicate_move_linked", {"type": 'D', "value": 'PRESS', "alt": True}, {"properties": [("NODE_OT_translate_attach", [("TRANSFORM_OT_translate", [("view2d_edge_pan", True)])])]}),  # 节点：复制并移动(关联)
    ("node.duplicate_move_keep_inputs", {"type": 'D', "value": 'PRESS', "shift": True, "ctrl": True}, {"properties": [("NODE_OT_translate_attach", [("TRANSFORM_OT_translate", [("view2d_edge_pan", True)])])]}),  # 节点：复制并移动(保留输入)
    ("node.parent_set", {"type": 'P', "value": 'PRESS', "ctrl": True}, None),  # 节点：设置父级
    ("node.detach", {"type": 'P', "value": 'PRESS', "alt": True}, None),  # 节点：分离
    ("node.join", {"type": 'J', "value": 'PRESS', "ctrl": True}, None),  # 节点：合并
    ("node.hide_toggle", {"type": 'H', "value": 'PRESS'}, None),  # 节点：切换隐藏
    ("node.mute_toggle", {"type": 'M', "value": 'PRESS'}, None),  # 节点：切换静音
    ("node.preview_toggle", {"type": 'H', "value": 'PRESS', "shift": True}, None),  # 节点：切换预览
    ("node.hide_socket_toggle", {"type": 'H', "value": 'PRESS', "ctrl": True}, None),  # 节点：切换插口隐藏
    ("node.view_all", {"type": 'HOME', "value": 'PRESS'}, None),  # 节点：查看全部
    ("node.view_all", {"type": 'NDOF_BUTTON_FIT', "value": 'PRESS'}, None),  # 节点：查看全部
    ("node.view_selected", {"type": 'NUMPAD_PERIOD', "value": 'PRESS'}, None),  # 节点：查看选中
    ("wm.call_menu_pie", {"type": 'ACCENT_GRAVE', "value": 'PRESS'}, {"properties": [("name", 'NODE_MT_view_pie')]}),  # 窗口：打开饼菜单
    ("node.delete", {"type": 'X', "value": 'PRESS'}, None),  # 节点：删除
    ("node.delete", {"type": 'DEL', "value": 'PRESS'}, None),  # 节点：删除
    ("node.delete_reconnect", {"type": 'X', "value": 'PRESS', "ctrl": True}, None),  # 节点：删除并重连
    ("node.delete_reconnect", {"type": 'DEL', "value": 'PRESS', "ctrl": True}, None),  # 节点：删除并重连
    ("node.select_all", {"type": 'A', "value": 'PRESS'}, {"properties": [("action", 'SELECT')]}),  # 节点：全选
    ("node.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, {"properties": [("action", 'DESELECT')]}),  # 节点：取消全选
    ("node.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'INVERT')]}),  # 节点：反选
    ("node.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, {"properties": [("action", 'DESELECT')]}),  # 节点：取消全选
    ("node.select_linked_to", {"type": 'L', "value": 'PRESS', "shift": True}, None),  # 节点：选择连接到
    ("node.select_linked_from", {"type": 'L', "value": 'PRESS'}, None),  # 节点：选择连接自
    ("node.select_grouped", {"type": 'G', "value": 'PRESS', "shift": True}, None),  # 节点：按组选择
    ("node.select_grouped", {"type": 'G', "value": 'PRESS', "shift": True, "ctrl": True}, {"properties": [("extend", True)]}),  # 节点：按组选择
    ("node.select_same_type_step", {"type": 'RIGHT_BRACKET', "value": 'PRESS', "shift": True}, {"properties": [("prev", False)]}),  # 节点：选择同类型
    ("node.select_same_type_step", {"type": 'LEFT_BRACKET', "value": 'PRESS', "shift": True}, {"properties": [("prev", True)]}),  # 节点：选择同类型
    ("node.find_node", {"type": 'F', "value": 'PRESS', "ctrl": True}, None),  # 节点：查找节点
    ("node.group_make", {"type": 'G', "value": 'PRESS', "ctrl": True}, None),  # 节点：创建组
    ("node.group_ungroup", {"type": 'G', "value": 'PRESS', "ctrl": True, "alt": True}, None),  # 节点：解散组
    ("node.group_separate", {"type": 'P', "value": 'PRESS'}, None),  # 节点：分离组
    ("node.group_edit", {"type": 'TAB', "value": 'PRESS'}, {"properties": [("exit", False)]}),  # 节点：编辑组
    ("node.group_edit", {"type": 'TAB', "value": 'PRESS', "ctrl": True}, {"properties": [("exit", True)]}),  # 节点：编辑组
    ("node.read_viewlayers", {"type": 'R', "value": 'PRESS', "ctrl": True}, None),  # 节点：读取视图层
    ("node.render_changed", {"type": 'Z', "value": 'PRESS'}, None),  # 节点：渲染已更改
    ("node.clipboard_copy", {"type": 'C', "value": 'PRESS', "ctrl": True}, None),  # 节点：复制到剪贴板
    ("node.clipboard_paste", {"type": 'V', "value": 'PRESS', "ctrl": True}, None),  # 节点：从剪贴板粘贴
    ("node.viewer_border", {"type": 'B', "value": 'PRESS', "ctrl": True}, None),  # 节点：查看器边框
    ("node.clear_viewer_border", {"type": 'B', "value": 'PRESS', "ctrl": True, "alt": True}, None),  # 节点：清除查看器边框
    ("node.translate_attach", {"type": 'G', "value": 'PRESS'}, {"properties": [("TRANSFORM_OT_translate", [("view2d_edge_pan", True)])]}),  # 节点：平移附着
    ("node.translate_attach", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"properties": [("TRANSFORM_OT_translate", [("view2d_edge_pan", True)])]}),  # 节点：平移附着
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, {"properties": [("view2d_edge_pan", True)]}),  # 变换：平移
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"properties": [("view2d_edge_pan", True), ("release_confirm", True)]}),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, None),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, None),  # 变换：调整大小
    ("node.move_detach_links_release", {"type": 'RIGHTMOUSE', "value": 'CLICK_DRAG', "alt": True}, {"properties": [("NODE_OT_translate_attach", [("TRANSFORM_OT_translate", [("view2d_edge_pan", True)])])]}),  # 节点：移动并断开连接(松开)
    ("node.move_detach_links", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG', "alt": True}, {"properties": [("TRANSFORM_OT_translate", [("view2d_edge_pan", True)])]}),  # 节点：移动并断开连接
    ("wm.context_toggle", {"type": 'TAB', "value": 'PRESS', "shift": True}, {"properties": [("data_path", 'tool_settings.use_snap_node')]}),  # 窗口：切换开关
    ("wm.context_menu_enum", {"type": 'TAB', "value": 'PRESS', "shift": True, "ctrl": True}, {"properties": [("data_path", 'tool_settings.snap_node_element')]}),  # 窗口：上下文枚举菜单
    ("wm.context_toggle", {"type": 'Z', "value": 'PRESS', "shift": True, "alt": True}, {"properties": [("data_path", 'space_data.overlay.show_overlays')]}),  # 窗口：切换开关
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'NODE_MT_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'NODE_MT_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'SPACE', "value": 'PRESS'}, {"properties": [("name", 'NODE_MT_add')]}),  # 窗口：打开菜单
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Paint Curve",  # 键位表：绘画曲线
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("paintcurve.add_point_slide", {"type": 'RIGHTMOUSE', "value": 'PRESS', "ctrl": True}, None),  # 绘画曲线：添加点并滑动
    ("paintcurve.select", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),  # 绘画曲线：选择
    ("paintcurve.select", {"type": 'LEFTMOUSE', "value": 'PRESS', "shift": True}, {"properties": [("extend", True)]}),  # 绘画曲线：选择
    ("paintcurve.slide", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("align", False)]}),  # 绘画曲线：滑动
    ("paintcurve.slide", {"type": 'RIGHTMOUSE', "value": 'PRESS', "shift": True}, {"properties": [("align", True)]}),  # 绘画曲线：滑动
    ("paintcurve.select", {"type": 'A', "value": 'PRESS'}, {"properties": [("toggle", True)]}),  # 绘画曲线：选择
    ("paintcurve.cursor", {"type": 'RIGHTMOUSE', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 绘画曲线：光标
    ("paintcurve.delete_point", {"type": 'X', "value": 'PRESS'}, None),  # 绘画曲线：删除点
    ("paintcurve.delete_point", {"type": 'DEL', "value": 'PRESS'}, None),  # 绘画曲线：删除点
    ("paintcurve.draw", {"type": 'RET', "value": 'PRESS'}, None),  # 绘画曲线：绘制
    ("paintcurve.draw", {"type": 'NUMPAD_ENTER', "value": 'PRESS'}, None),  # 绘画曲线：绘制
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, None),  # 变换：平移
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, None),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, None),  # 变换：调整大小
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Pose",  # 键位表：姿态
  {"space_type": 'EMPTY', "region_type": 'WINDOW'},  # 空间类型：通用(所有空间)；区域类型：窗口
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("transform.translate", {"type": 'G', "value": 'PRESS'}, {"active": False}),  # 变换：平移
    ("transform.rotate", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 变换：旋转
    ("transform.resize", {"type": 'S', "value": 'PRESS'}, {"active": False}),  # 变换：调整大小
    ("transform.translate", {"type": 'LEFTMOUSE', "value": 'CLICK_DRAG'}, {"active": False}),  # 变换：平移
    ("transform.mirror", {"type": 'M', "value": 'PRESS', "ctrl": True}, None),  # 变换：镜像
    ("object.parent_set", {"type": 'P', "value": 'PRESS', "ctrl": True}, None),  # 对象：设置父级
    ("pose.reveal", {"type": 'H', "value": 'PRESS', "alt": True}, None),  # 姿态：显示全部
    ("pose.hide", {"type": 'H', "value": 'PRESS'}, {"properties": [("unselected", False)]}),  # 姿态：隐藏
    ("pose.hide", {"type": 'H', "value": 'PRESS', "shift": True}, {"properties": [("unselected", True)]}),  # 姿态：隐藏
    ("wm.call_menu", {"type": 'A', "value": 'PRESS', "ctrl": True}, {"properties": [("name", 'VIEW3D_MT_pose_apply')]}),  # 窗口：打开菜单
    ("pose.rot_clear", {"type": 'R', "value": 'PRESS', "alt": True}, None),  # 姿态：清除旋转
    ("pose.loc_clear", {"type": 'G', "value": 'PRESS', "alt": True}, None),  # 姿态：清除位置
    ("pose.scale_clear", {"type": 'S', "value": 'PRESS', "alt": True}, None),  # 姿态：清除缩放
    ("pose.quaternions_flip", {"type": 'F', "value": 'PRESS', "alt": True}, None),  # 姿态：翻转四元数
    ("pose.rotation_mode_set", {"type": 'R', "value": 'PRESS', "ctrl": True}, None),  # 姿态：设置旋转模式
    ("pose.copy", {"type": 'C', "value": 'PRESS', "ctrl": True}, None),  # 姿态：复制
    ("pose.paste", {"type": 'V', "value": 'PRESS', "ctrl": True}, {"properties": [("flipped", False)]}),  # 姿态：粘贴
    ("pose.paste", {"type": 'V', "value": 'PRESS', "shift": True, "ctrl": True}, {"properties": [("flipped", True)]}),  # 姿态：粘贴
    ("pose.select_all", {"type": 'A', "value": 'PRESS'}, {"properties": [("action", 'SELECT')]}),  # 姿态：全选
    ("pose.select_all", {"type": 'A', "value": 'PRESS', "alt": True}, {"properties": [("action", 'DESELECT')]}),  # 姿态：取消全选
    ("pose.select_all", {"type": 'I', "value": 'PRESS', "ctrl": True}, {"properties": [("action", 'INVERT')]}),  # 姿态：反选
    ("pose.select_all", {"type": 'A', "value": 'DOUBLE_CLICK'}, {"properties": [("action", 'DESELECT')]}),  # 姿态：取消全选
    ("pose.select_parent", {"type": 'P', "value": 'PRESS', "shift": True}, None),  # 姿态：选择父级
    ("pose.select_hierarchy", {"type": 'LEFT_BRACKET', "value": 'PRESS', "repeat": True}, {"properties": [("direction", 'PARENT'), ("extend", False)]}),  # 姿态：选择层级
    ("pose.select_hierarchy", {"type": 'LEFT_BRACKET', "value": 'PRESS', "shift": True, "repeat": True}, {"properties": [("direction", 'PARENT'), ("extend", True)]}),  # 姿态：选择层级
    ("pose.select_hierarchy", {"type": 'RIGHT_BRACKET', "value": 'PRESS', "repeat": True}, {"properties": [("direction", 'CHILD'), ("extend", False)]}),  # 姿态：选择层级
    ("pose.select_hierarchy", {"type": 'RIGHT_BRACKET', "value": 'PRESS', "shift": True, "repeat": True}, {"properties": [("direction", 'CHILD'), ("extend", True)]}),  # 姿态：选择层级
    ("pose.select_linked", {"type": 'L', "value": 'PRESS', "ctrl": True}, None),  # 姿态：选择关联元素
    ("pose.select_linked_pick", {"type": 'L', "value": 'PRESS'}, None),  # 姿态：点选关联元素
    ("pose.select_grouped", {"type": 'G', "value": 'PRESS', "shift": True}, None),  # 姿态：按组选择
    ("pose.select_mirror", {"type": 'M', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 姿态：镜像选择
    ("pose.constraint_add_with_targets", {"type": 'C', "value": 'PRESS', "shift": True, "ctrl": True}, None),  # 姿态：添加约束(带目标)
    ("pose.constraints_clear", {"type": 'C', "value": 'PRESS', "ctrl": True, "alt": True}, None),  # 姿态：清除约束
    ("pose.ik_add", {"type": 'I', "value": 'PRESS', "shift": True}, None),  # 姿态：添加IK
    ("pose.ik_clear", {"type": 'I', "value": 'PRESS', "ctrl": True, "alt": True}, None),  # 姿态：清除IK
    ("wm.call_menu", {"type": 'W', "value": 'PRESS', "shift": True}, {"properties": [("name", 'VIEW3D_MT_bone_options_toggle')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'W', "value": 'PRESS', "shift": True, "ctrl": True}, {"properties": [("name", 'VIEW3D_MT_bone_options_enable')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'W', "value": 'PRESS', "alt": True}, {"properties": [("name", 'VIEW3D_MT_bone_options_disable')]}),  # 窗口：打开菜单
    ("armature.collection_show_all", {"type": 'ACCENT_GRAVE', "value": 'PRESS', "ctrl": True}, None),  # 骨骼：显示全部集合
    ("armature.assign_to_collection", {"type": 'M', "value": 'PRESS', "shift": True}, None),  # 骨骼：分配到集合
    ("armature.move_to_collection", {"type": 'M', "value": 'PRESS'}, None),  # 骨骼：移动到集合
    ("transform.bbone_resize", {"type": 'S', "value": 'PRESS', "shift": True, "ctrl": True, "alt": True}, None),  # 变换：弯曲骨骼缩放
    ("anim.keyframe_insert_menu", {"type": 'K', "value": 'PRESS'}, {"properties": [("always_prompt", True)]}),  # 动画：插入关键帧菜单
    ("anim.keyframe_delete_v3d", {"type": 'I', "value": 'PRESS', "alt": True}, None),  # 动画：删除关键帧
    ("anim.keying_set_active_set", {"type": 'K', "value": 'PRESS', "shift": True}, None),  # 动画：设置活动关键帧集
    ("pose.push", {"type": 'E', "value": 'PRESS', "ctrl": True}, None),  # 姿态：推
    ("pose.relax", {"type": 'E', "value": 'PRESS', "alt": True}, None),  # 姿态：松弛
    ("pose.breakdown", {"type": 'E', "value": 'PRESS', "shift": True}, None),  # 姿态：分解
    ("pose.blend_to_neighbor", {"type": 'E', "value": 'PRESS', "shift": True, "alt": True}, None),  # 姿态：混合到邻近
    ("wm.call_menu", {"type": 'P', "value": 'PRESS', "alt": True}, {"properties": [("name", 'VIEW3D_MT_pose_propagate')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'RIGHTMOUSE', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_pose_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'APP', "value": 'PRESS'}, {"properties": [("name", 'VIEW3D_MT_pose_context_menu')]}),  # 窗口：打开菜单
    ("wm.call_menu", {"type": 'W', "value": 'PRESS', "shift": True, "alt": True}, {"properties": [("name", 'POSE_MT_selection_sets_select')]}),  # 窗口：打开菜单
    ("anim.keyframe_insert", {"type": 'I', "value": 'PRESS'}, None),  # 动画：插入关键帧
    ("wm.tool_set_by_id", {"type": 'Q', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.select_box')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'W', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.move')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'E', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.rotate')]}),  # 窗口：切换工具
    ("wm.tool_set_by_id", {"type": 'R', "value": 'PRESS', "repeat": True}, {"properties": [("name", 'builtin.scale')]}),  # 窗口：切换工具
    ],  # 条目列表结束
   },  # 键位表数据结束
  ),  # 键位表结束
 ("Primitive Tool Modal Map",  # 键位表：图元工具模态映射
  {"space_type": 'EMPTY', "region_type": 'WINDOW', "modal": True},  # 空间类型：通用(所有空间)；区域类型：窗口；模态映射
  {"items":  # 快捷键条目（操作符、按键绑定、参数）
   [  # 条目列表开始
    ("CANCEL", {"type": 'ESC', "value": 'PRESS', "any": True}, None),  # 取消
    ("CANCEL", {"type": 'Q', "value": 'PRESS', "any": True}, None),  # 取消
    ("PANNING", {"type": 'MIDDLEMOUSE', "value": 'ANY', "any": True}, None),  # 平移
    ("CONFIRM", {"type": 'RET', "value": 'PRESS', "any": True}, None),  # 确认
    ("CONFIRM", {"type": 'NUMPAD_ENTER', "value": 'PRESS', "any": True}, None),  # 确认
    ("EXTRUDE", {"type": 'E', "value": 'PRESS'}, None),  # 挤出
    ("GRAB", {"type": 'G', "value": 'PRESS'}, None),  # 抓取
    ("ROTATE", {"type": 'R', "value": 'PRESS'}, {"active": False}),  # 旋转
    ("SCALE", {"type": 'S', "value": 'PRESS'}, None),  # 缩放
    ("INCREASE_SUBDIVISION", {"type": 'UP_ARROW', "value": 'PRESS', "repeat": True}, None),  # 增加细分
    ("DECREASE_SUBDIVISION", {"type": 'DOWN_ARROW', "value": 'PRESS', "repeat": True}, None),  # 减少细分
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

