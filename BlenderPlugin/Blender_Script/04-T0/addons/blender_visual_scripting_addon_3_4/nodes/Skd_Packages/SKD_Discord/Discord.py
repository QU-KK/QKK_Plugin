import bpy
import webbrowser
import os

from bpy.props import StringProperty
from bpy.types import Operator
from ...base_node import SN_ScriptingBaseNode

# Custom operator to open a URL in a web browser
class OpenTenorWebsiteOperator(Operator):
    bl_idname = "node.open_tenor_website"
    bl_label = "Open Tenor Website"
    bl_description = "Open the Tenor website"

    url: StringProperty(default="https://tenor.com/en-GB/")

    def execute(self, context):
        webbrowser.open(self.url)
        return {'FINISHED'}

# Node class with the button to open the Tenor website
class SN_SKD_Discord(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Discord"
    bl_label = "Discord"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    url: StringProperty(default="https://tenor.com/en-GB/")

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Discord Hook")
        self.add_string_input("Message")
        self.add_string_input("Gif")
        self.add_string_input("File").subtype = "FILE_PATH"

    def draw_buttons(self, context, layout):
        # Add a button that calls the custom operator to open the website
        layout.operator("node.open_tenor_website", text="Open Tenor", icon='WORLD').url = self.url
     
    def evaluate(self, context):
        self.code_import = """
            import requests
            import os
        """

        self.code_imperative = """
            def DisCon(hooker, message, gif, filer):
                message_content = message + '\\n' + gif
                header = {
                    'authorization': hooker
                }
                payload = {
                    "content": message_content
                }
                if filer and os.path.exists(filer) and os.path.getsize(filer) > 0:
                    files = {
                        "file": (filer, open(filer, 'rb')),
                    }
                    r = requests.post(hooker, data=payload, headers=header, files=files).text
                else:
                    r = requests.post(hooker, data=payload, headers=header).text
        """

        self.code = f"DisCon({self.inputs[1].python_value}, {self.inputs[2].python_value}, {self.inputs[3].python_value}, {self.inputs[4].python_value})"
        self.code += f"\n{self.outputs[0].python_value}"
