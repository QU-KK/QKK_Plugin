import bpy
import urllib
import requests
from ...base_node import SN_ScriptingBaseNode
class SN_SKD_ReadText(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_ReadText"
    bl_label = "Read Online Text"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Text File Path").subtype = "FILE_PATH"
        self.add_string_output("Text")
        self.add_list_output("Lines")
        
    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            import urllib
                            import requests
                            """
   
        self.code_imperative = """
                def read_text(texters):

                    import urllib.request

                    # Retrieve the content from the online document
                    response = urllib.request.urlopen(texters)
                    content = response.read().decode('utf-8')
                    lines = content.splitlines()
                    # Split the content into a list of lines
                    return content, lines
                    """
        
        self.code = f"""texter_{self.static_uid} = read_text({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"texter_{self.static_uid}[0]"
        self.outputs[2].python_value = f"texter_{self.static_uid}[1]"
        self.code += f'\n{self.outputs[0].python_value}'

