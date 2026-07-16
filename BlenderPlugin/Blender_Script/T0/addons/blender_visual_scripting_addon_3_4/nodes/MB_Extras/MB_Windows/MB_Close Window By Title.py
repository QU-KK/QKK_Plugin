import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_MB_Close_Window_By_Title_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_MB_Close_Window_By_Title_Node"
    bl_label = "MB_Close Window By Title"
    node_color = "PROGRAM"
    bl_width_default = 200

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_execute_input()
        self.add_string_input("Title")

        # outputs
        self.add_execute_output()
        self.add_string_output('Title')

    def evaluate(self, context):
        # generate the code here
        self.code = f"""

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
                    
                    title = {self.inputs['Title'].python_value}
                    
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
                        else:
                            print("No matching window found.")
                            return False
                    
                    if title:
                        close_window(title, process_id)
                        for a in bpy.context.screen.areas:
                            a.tag_redraw()
                    else: 
                        print("No title entered.")

                    {self.indent(self.outputs[0].python_value, 5)}
                    """
        self.outputs['Title'].python_value = f'title'

        self.code_import = f"""
                            import ctypes
                            """
