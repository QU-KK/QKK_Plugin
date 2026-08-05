import bpy
import requests
import json
import webbrowser

from bpy.props import StringProperty
from bpy.types import Operator

from ...base_node import SN_ScriptingBaseNode

# Custom operator to open a URL in a web browser
class OpenDevWebsiteOperator(Operator):
    bl_idname = "node.open_dev_website"
    bl_label = "Open Developers Website"
    bl_description = "Open Developers Website"

    url: StringProperty(default="https://discord.com/developers/")

    def execute(self, context):
        webbrowser.open(self.url)
        return {'FINISHED'}

# Node class with the button to open the Tenor website
class SN_SKD_Discord_Read(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Discord_Read"
    bl_label = "Discord Read"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    url: StringProperty(default="https://discord.com/developers/")

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        
        self.add_string_input("Discord Token")
        self.add_string_input("Channel ID")

        self.add_list_output("Results")

    def draw_buttons(self, context, layout):
        # Add a button that calls the custom operator to open the website
        layout.operator("node.open_dev_website", text="Open Dev", icon='WORLD').url = self.url
        
    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            import requests
                            import json
                            import webbrowser
                            """
   
        self.code_imperative = """
            def get_channel_messages(token, channel_id):
                url = f'https://discord.com/api/v9/channels/{channel_id}/messages'
                headers = {'Authorization': f'Bot {token}'}
                response = requests.get(url, headers=headers)

                if response.status_code == 200:
                    messages = json.loads(response.text)
                    return messages
                else:
                    print(f'Failed to fetch messages: {response.status_code} - {response.text}')
                    return None
            """
        
        self.code = f"""messages_{self.static_uid} = get_channel_messages({self.inputs[1].python_value}, {self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"messages_{self.static_uid}"
        self.code += f"\n{self.outputs[0].python_value}"
