import bpy
import urllib.request

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_TestInternet(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_TestInternet"
    bl_label = "Test Internet Connection"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Website Path").subtype = "FILE_PATH"
        self.add_boolean_output("Confirmed Connection")
        
    def evaluate(self, context):
        
        self.code_import = """
                            import urllib.request
                            """
   
        self.code_imperative = """
                def testconnection(Url_test):
                    try:
                        urllib.request.urlopen(Url_test, timeout=1)
                        return True
                    except:
                        return False
                    """
        
        self.code = f"""contestz_{self.static_uid} = testconnection({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"contestz_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

