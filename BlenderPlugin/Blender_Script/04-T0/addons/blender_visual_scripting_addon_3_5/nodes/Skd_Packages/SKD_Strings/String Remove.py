import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_StringRemoveNode(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_StringRemoveNode"
    bl_label = "String Remove"
    node_color = "STRING"

    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("String")
        self.add_integer_input("Remove Amount")
        self.add_string_output("Returned Amount")
        
    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            """
   
        self.code_imperative = """
                def strrem(texter_x, remover_x):
                    
                    rem_text = texter_x[0: remover_x]
                    return rem_text
                    """
        
        self.code = f"""rex_{self.static_uid} = strrem({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"rex_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'