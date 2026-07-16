import bpy 
from ...base_node import SN_ScriptingBaseNode
class SN_SKD_PopUpMessageList(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_PopUpMessageList"
    bl_label = "Popup Message List"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Header").default_value = "Header"
        self.add_string_input("Icon Name").default_value = "FUND"
        self.add_list_input("List Message").default_value = "Test Message"
        self.add_list_input("List Named Icons")
        
    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            """
   
        self.code_imperative = """    
        def ShowMessageBox(title,icon,message_lines,icons):
            scene = bpy.context.scene
            # Access the 2D cursor location
            cursor_location = scene.cursor.location 
            def draw(self, context):
                for i, line in enumerate(message_lines):
                    icon_name = icons[i]
                    self.layout.label(text=line, icon=icon_name)

            bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
        """
        
        self.code = f"""ShowMessageBox({self.inputs[1].python_value},
                                                  {self.inputs[2].python_value},
                                                  {self.inputs[3].python_value},
                                                  {self.inputs[4].python_value})"""
        self.code += f'\n{self.outputs[0].python_value}'
