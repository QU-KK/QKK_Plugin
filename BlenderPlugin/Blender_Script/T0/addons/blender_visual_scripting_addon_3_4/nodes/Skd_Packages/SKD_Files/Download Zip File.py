import bpy
from ...base_node import SN_ScriptingBaseNode
class SN_SKD_DownLoadFileNode(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_DownLoadFileNode"
    bl_label = "Download Zip File"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Zip File Path").subtype = "FILE_PATH"
        self.add_string_input("Save Path").subtype = "DIR_PATH"
        self.add_boolean_output("Confirmed Download")
        
    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            import os
                            import io
                            import requests
                            import zipfile
                            """
   
        self.code_imperative = """
                def zipload(zip_file_url_address, download_location_address):

                    try: 
                        r = requests.get(zip_file_url_address)
                        z = zipfile.ZipFile(io.BytesIO(r.content))
                        z.extractall(download_location_address)
                        return True
                    except:
                        return False
                    """
        
        self.code = f"""zip_{self.static_uid} = zipload({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"zip_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

