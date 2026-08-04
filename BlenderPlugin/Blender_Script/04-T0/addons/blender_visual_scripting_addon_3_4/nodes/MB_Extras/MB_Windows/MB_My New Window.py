import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_MB_My_New_Window_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_MB_My_New_Window_Node"
    bl_label = "MB_My New Window"
    node_color = "PROGRAM"
    bl_width_default = 310

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_execute_input()
        self.add_string_input("Title").default_value = 'My New Window'
        self.add_integer_input("Size_X").default_value = 960
        self.add_integer_input("Size_Y").default_value = 540
        self.add_boolean_input('Open Under Mouse').default_value = True
        self.add_boolean_input("Show Header").default_value = False
        self.add_boolean_input("Show Menu").default_value = False

        # outputs
        self.add_execute_output()
        self.add_string_output("Title")
        self.add_property_output('Ui Type')
        # self.add_integer_output('Size_X')
        # self.add_integer_output('Size_Y')

    # Custom Enum Property
    type: bpy.props.EnumProperty(name="",
                                 items=[("Asset Browser", "Asset Browser", "", 124, 0),
                                        ("Compositor", "Compositor", "", 125, 1),
                                        ("Drivers", "Drivers", "", 519, 2),
                                        ("Dope Sheet", "Dope Sheet", "", 125, 3),
                                        ("File Browser", "File Browser", "", 108, 4),
                                        ("Geometry Node Editor", "Geometry Node Editor", "", 120, 5),
                                        ("Graph Editor", "Graph Editor", "", 105, 6),
                                        ("Image Editor", "Image Editor", "", 109, 7),
                                        ("Info", "Info", "", 110, 8),
                                        ("Movie Clip Editor", "Movie Clip Editor", "", 123, 9),
                                        ("Nonlinear Animation", "Nonlinear Animation", "", 116, 10),
                                        ("Outliner", "Outliner", "", 106, 11),
                                        ("Preferences", "Preferences", "", 117, 12),
                                        ("Properties", "Properties", "", 107, 13),
                                        ("Python Console", "Python Console", "", 121, 14),
                                        ("Shader Editor", "Shader Editor", "", 627, 15),
                                        ("Spreadsheet", "Spreadsheet", "", 113, 16),
                                        ("Text Editor", "Text Editor", "", 112, 17),
                                        ("Texture Node Editor", "Texture Node Editor", "", 126, 18),
                                        ("Time Line", "Time Line", "", 118, 19),
                                        ("UV Editor", "UV Editor", "", 128, 20),
                                        ("Video Sequencer", "Video Sequencer", "", 111, 21),
                                        ("View 3D", "View 3D", "", 104, 22),
                                        ("Visual Scripting Editor", "Visual Scripting Editor", "", 698, 23),
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)

    def evaluate(self, context):
		# generate the code here

        self.code = f"""
                    title = {self.inputs['Title'].python_value}
                    size_x = int(max(360, min(int({self.inputs['Size_X'].python_value}), 3840)))
                    size_y = int(max(360, min(int({self.inputs['Size_Y'].python_value}), 3840)))
                    open_under_mouse = {self.inputs['Open Under Mouse'].python_value}
                    user32 = ctypes.WinDLL('user32')
                    child_window_created = False

                    def is_child_window(hwnd):
                        parent = ctypes.windll.user32.GetParent(hwnd)
                        if parent == 0:
                            return False
                        return True

                    titles = range(len(bpy.data.screens)-1,-1,-1)   
                    for index in titles:
                        if title in bpy.data.screens[index].name:
                            # Get the process ID using the ctypes library
                            process_id = ctypes.windll.kernel32.GetCurrentProcessId()
                            user32 = ctypes.WinDLL('user32')
                            EnumWindows = user32.EnumWindows
                            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), 
                            ctypes.POINTER(ctypes.c_int))
                            GetWindowText = user32.GetWindowTextW
                            GetWindowTextLength = user32.GetWindowTextLengthW
                            IsWindowVisible = user32.IsWindowVisible
                            GetParent = user32.GetParent
                            GetWindowThreadProcessId = user32.GetWindowThreadProcessId
                
                            def close_window(window_name, parent_pid):
                                titles = []
                                hwnds = []
                
                                def foreach_window(hwnd, lParam):
                                    if IsWindowVisible(hwnd):
                                        length = GetWindowTextLength(hwnd)
                                        buff = ctypes.create_unicode_buffer(length + 1)
                                        GetWindowText(hwnd, buff, length + 1)
                                        titles.append(buff.value)
                                        hwnds.append(hwnd)
                                    return True
                                EnumWindows(EnumWindowsProc(foreach_window), 0)
                                found = False
                                for hwnd, title in zip(hwnds, titles):
                                    if window_name in title:
                                        parent = GetParent(hwnd)
                                        pid = ctypes.c_ulong()
                                        thread_id = GetWindowThreadProcessId(parent, ctypes.byref(pid))
                                        if pid.value == parent_pid:
                                            user32.PostMessageW(hwnd, 0x0010, 0, 0)
                                            found = True
                                            break
                                if found:
                                    for a in bpy.context.screen.areas:
                                        a.tag_redraw()
                            if title:
                                close_window(title, process_id)
                                for a in bpy.context.screen.areas:
                                    a.tag_redraw()
                            scr = title
                            ignored_list = ['Animation', 'Compositing', 'Geometry Nodes', 'Layout',
                                            'Modeling','Rendering', 'Scripting', 'Scripting.001',
                                            'temp', 'Sculpting', 'Shading', 'Texture Paint', 'UV Editing']
                            for scr in bpy.data.screens:
                                if scr.name not in ignored_list:
                                    scr.user_clear()
                            if bpy.context and bpy.context.screen:
                                for a in bpy.context.screen.areas:
                                    a.tag_redraw()

                    windows = []
                    counter = 1

                    def update_window_titles():
                        while True:
                            for handle, title in windows:
                                ctypes.windll.user32.SetWindowTextA(handle, ctypes.c_char_p(title.encode('utf-8')))
                            time.sleep(1)

                    if bpy.context.screen.show_fullscreen:
                        bpy.ops.screen.back_to_previous('INVOKE_DEFAULT', )
                        bpy.ops.wm.window_new("INVOKE_DEFAULT", )
                    else:
                        bpy.ops.wm.window_new("INVOKE_DEFAULT", )

                    # Get the handle to the active new window and rename
                    string = title.encode('utf-8').decode('utf-8')
                    active_w = ctypes.windll.user32.GetActiveWindow()

                    # Check if the title already exists in the list
                    while string in [w[1] for w in windows]:
                        string = f"{{title}} ({{counter}})"
                        counter += 1

                    ctypes.windll.user32.SetWindowTextA(active_w,ctypes.c_char_p(string.encode('utf-8')))

                    # Store the handle and title in the list
                    windows.append((active_w, string))

                    # Start the timer to update the window titles
                    update_thread = threading.Thread(target=update_window_titles)
                    update_thread.start()
                    
                    class MONITORINFO(ctypes.Structure):
                        _fields_ = [("cbSize", ctypes.c_ulong),
                                    ("rcMonitor", ctypes.wintypes.RECT),
                                    ("rcWork", ctypes.wintypes.RECT),
                                    ("dwFlags", ctypes.c_ulong)]
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                    if open_under_mouse == True:
                        if is_child_window(hwnd):
                            if child_window_created:
                                user32.SetForegroundWindow(hwnd)
                            else:
                                def get_mouse_position():
                                    POINT = ctypes.wintypes.POINT
                                    pt = POINT()
                                    user32.GetCursorPos(ctypes.byref(pt))
                                    return pt
    
                                def get_parent_monitor_handle(mouse_pos):
                                    try:
                                        parent_monitor_info = MONITORINFO()
                                        parent_monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                                        parent_monitor_handle = user32.MonitorFromPoint(mouse_pos, 2)
                                        user32.GetMonitorInfoW(parent_monitor_handle, ctypes.byref(parent_monitor_info))
                                        return parent_monitor_handle, parent_monitor_info
                                    except TypeError as e:
                                        print("The mouse is not on the same monitor as Blender.")
                                        return None, None
    
                                def set_child_window_position(child_hwnd, parent_hwnd, parent_monitor_handle, parent_monitor_info, size_x, size_y, mouse_pos, user32):
                                    try:
                                        if parent_monitor_handle == user32.MonitorFromWindow(parent_hwnd, 2):
                                            child_x = mouse_pos.x - size_x / 2
                                            child_y = mouse_pos.y - size_y / 2
                                            user32.SetWindowPos(child_hwnd, 0, int(child_x), int(child_y), size_x, size_y, 0x0040)
                                        else:
                                            child_x = parent_monitor_info["rcMonitor"].left + (parent_monitor_info["rcMonitor"].right - parent_monitor_info["rcMonitor"].left - size_x) / 2
                                            child_y = parent_monitor_info["rcMonitor"].top + (parent_monitor_info["rcMonitor"].bottom - parent_monitor_info["rcMonitor"].top - size_y) / 2
                                            user32.CloseWindow(child_hwnd)
                                            user32.ShowWindow(child_hwnd, 1)
                                            user32.SetWindowPos(child_hwnd, 0, int(child_x), int(child_y), size_x, size_y, 0x0040)
                                    except TypeError as e:
                                        print("The mouse is not on the same monitor as Blender.")
                                mouse_pos = get_mouse_position()
                                parent_monitor_handle, parent_monitor_info = get_parent_monitor_handle(mouse_pos)
                                set_child_window_position(hwnd, hwnd, parent_monitor_handle, parent_monitor_info, size_x, size_y, mouse_pos, user32)
                                bpy.context.screen.id_data.name = title
                    else:
                        if open_under_mouse == False:
                            def is_child_window(hwnd):
                                parent = ctypes.windll.user32.GetParent(hwnd)
                                if parent == 0:
                                    return False
                                return True
                            hwnd = ctypes.windll.user32.GetForegroundWindow()
                            if is_child_window(hwnd):
                                class RECT(ctypes.Structure):
                                    _fields_ = [("left", ctypes.c_long),
                                                ("top", ctypes.c_long),
                                                ("right", ctypes.c_long),
                                                ("bottom", ctypes.c_long)]
                                class MONITORINFO(ctypes.Structure):
                                    _fields_ = [("cbSize", ctypes.c_ulong),
                                                ("rcMonitor", RECT),
                                                ("rcWork", RECT),
                                                ("dwFlags", ctypes.c_ulong)]

                                    def move_window_to_parent_center(child_hwnd, parent_hwnd, width=None, height=None):
                                        parent_rect = RECT()
                                        ctypes.windll.user32.GetWindowRect(parent_hwnd, ctypes.byref(parent_rect))
                                        parent_monitor_info = MONITORINFO()
                                        parent_monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                                        ctypes.windll.user32.GetMonitorInfoW(ctypes.windll.user32.MonitorFromWindow(parent_hwnd, 1), ctypes.byref(parent_monitor_info))
                                        child_rect = RECT()
                                        ctypes.windll.user32.GetWindowRect(child_hwnd, ctypes.byref(child_rect))
                                        if width is not None:
                                            child_rect.right = child_rect.left + width
                                        if height is not None:
                                            child_rect.bottom = child_rect.top + height
                                        child_x = parent_rect.left + ((parent_rect.right - parent_rect.left) - (child_rect.right - child_rect.left)) / 2
                                        child_y = parent_rect.top + ((parent_rect.bottom - parent_rect.top) - (child_rect.bottom - child_rect.top)) / 2
                                        ctypes.windll.user32.SetWindowPos(child_hwnd, 0, int(child_x), int(child_y), int(child_rect.right - child_rect.left), int(child_rect.bottom - child_rect.top), 0x0040)
                                    # Example usage:
                                    child_hwnd = ctypes.windll.user32.GetForegroundWindow()
                                    if child_hwnd:
                                        parent_hwnd = ctypes.windll.user32.GetForegroundWindow()
                                        move_window_to_parent_center(child_hwnd, parent_hwnd, width=size_x, height=size_y)
                    
                    # Set area ui type for new window
                    hwnd = ctypes.windll.user32.GetForegroundWindow()
                    if is_child_window(hwnd):
                        if {self.type == "Asset Browser"}:
                            if open_under_mouse:
                                print('Aborted to avoid a crash')
                            else:
                                bpy.context.area.ui_type = 'ASSETS'                                                   
                        if {self.type == "Compositor"}:
                            bpy.context.area.ui_type = 'CompositorNodeTree'
                        if {self.type == "Drivers"}:
                            bpy.context.area.ui_type = 'DRIVERS'
                        if {self.type == "Dope Sheet"}:
                            bpy.context.area.ui_type = 'DOPESHEET'
                        if {self.type == "File Browser"}:
                            bpy.context.area.ui_type = 'FILES'
                        if {self.type == "Geometry Node Editor"}:
                            bpy.context.area.ui_type = 'GeometryNodeTree'
                        if {self.type == "Graph Editor"}:
                            bpy.context.area.ui_type = 'FCURVES'
                        if {self.type == "Image Editor"}:
                            bpy.context.area.ui_type = 'IMAGE_EDITOR'
                        if {self.type == "Info"}:
                            bpy.context.area.ui_type = 'INFO'
                        if {self.type == "Movie Clip Editor"}:
                            bpy.context.area.ui_type = 'CLIP_EDITOR'
                        if {self.type == "Nonlinear Animation"}:
                            bpy.context.area.ui_type = 'NLA_EDITOR'
                        if {self.type == "Outliner"}:
                            bpy.context.area.ui_type = 'OUTLINER'
                        if {self.type == "Preferences"}:
                            bpy.context.area.ui_type = 'PREFERENCES'
                        if {self.type == "Properties"}:
                            bpy.context.area.ui_type = 'PROPERTIES'
                        if {self.type == "Python Console"}:
                            bpy.context.area.ui_type = 'CONSOLE'
                        if {self.type == "Shader Editor"}:
                            bpy.context.area.ui_type = 'ShaderNodeTree'
                        if {self.type == "Spreadsheet"}:
                            bpy.context.area.ui_type = 'SPREADSHEET'
                        if {self.type == "Text Editor"}:
                            bpy.context.area.ui_type = 'TEXT_EDITOR'
                        if {self.type == "Texture Node Editor"}:
                            bpy.context.area.ui_type = 'TextureNodeTree'
                        if {self.type == "Time Line"}:
                            bpy.context.area.ui_type = 'TIMELINE'
                        if {self.type == "UV Editor"}:
                            bpy.context.area.ui_type = 'UV'
                        if {self.type == "Video Sequencer"}:
                            bpy.context.area.ui_type = 'SEQUENCE_EDITOR'
                        if {self.type == "View 3D"}:
                            bpy.context.area.ui_type = 'VIEW_3D'
                        if {self.type == "Visual Scripting Editor"}:
                            bpy.context.area.ui_type = 'ScriptingNodesTree'
                        {self.indent(self.outputs[0].python_value, 6)}
                    
                    # Boolean Props to enable / disable headers & menus                    
                    if {self.inputs['Show Header'].python_value}:
                        bpy.context.area.spaces.active.show_region_header = True
                    else:
                        bpy.context.area.spaces.active.show_region_header = False
                    
                    if {self.inputs['Show Menu'].python_value}:
                        if (bpy.context.area.spaces.active.show_region_header and bpy.context.area.show_menus):
                            bpy.context.area.show_menus = True
                        else:
                            bpy.context.area.spaces.active.show_region_header = True
                    else:
                        bpy.context.area.show_menus = False
                    """
        self.outputs['Title'].python_value = self.inputs['Title'].python_value
        self.outputs['Ui Type'].python_value = f'bpy.context.area.ui_type'
        # self.outputs['Size_X'].python_value = self.inputs['Size_X'].python_value = f'size_x'
        # self.outputs['Size_Y'].python_value = self.inputs['Size_Y'].python_value = f'size_y'

        self.code_import = f"""
                        import bpy
                        import ctypes
                        import time
                        import threading
                        from ctypes import wintypes, windll, Structure, c_int, c_double, c_byte, c_char_p, c_long, byref
                        """

    def draw_node(self, context, layout):
        box = layout.box()
        box.label(text="Default = 960x540")
        box.label(text="Min/Max = 360x3840")
        box.label(text="'Asset Browser'")
        box.label(text="Can only be used with Open Under Mouse disabled")
        box.label(text="The Window will open set to the next available option")
        layout.prop(self, "type", text="Ui Type")
