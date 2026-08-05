import bpy

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_String_Value(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_String_Value"
    bl_label = "Get string index value"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("String")
        self.add_integer_input("Index")
        self.add_string_output("OutPut Value")
        
        
    def evaluate(self, context):
   
        self.code_imperative = """
                def skd_string_val_fun(string, index):
                    try:
                        return string[index]
                    except:
                        return "Index out of range"
                    """
        
        self.code = f"""skd_string_value_{self.static_uid} = skd_string_val_fun({self.inputs[1].python_value},{self.inputs[2].python_value} )"""
        self.outputs[1].python_value = f"skd_string_value_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

