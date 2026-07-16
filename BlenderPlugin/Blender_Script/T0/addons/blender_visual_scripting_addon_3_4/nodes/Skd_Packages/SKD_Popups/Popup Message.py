import bpy 
from ...base_node import SN_ScriptingBaseNode
class SN_SKD_PopUpMessage(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_PopUpMessage"
    bl_label = "Popup Message"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Header").default_value = "Header"
        self.add_string_input("Icon Name").default_value = "FUND"
        self.add_string_input("Message")
        
    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            """
   
        self.code_imperative = """ 
        

        def ShowMessageBoxer(title, icon, message):

            scene = bpy.context.scene
            # Access the 2D cursor location
            cursor_location = scene.cursor.location 
    
            def draw(self, context):
                self.layout.label(text=message)

            bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
        """
        
        self.code = f"""ShowMessageBoxer({self.inputs[1].python_value},
                                                  {self.inputs[2].python_value},
                                                  {self.inputs[3].python_value})"""
        self.code += f'\n{self.outputs[0].python_value}'
