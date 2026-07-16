import bpy
import requests
import json
import datetime
import webbrowser

from bpy.props import StringProperty
from bpy.types import Operator

from ...base_node import SN_ScriptingBaseNode

# Custom operator to open a URL in a web browser
class OpenTenorWebsiteOperator(Operator):
    bl_idname = "node.open_dev2_website"
    bl_label = "Open Developers Website 2"
    bl_description = "Open Developers Website"

    url: StringProperty(default="https://discord.com/developers/")

    def execute(self, context):
        webbrowser.open(self.url)
        return {'FINISHED'}

# Node class with the button to open the Tenor website
class SN_SKD_Discord_Formatter(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Discord_Formatter"
    bl_label = "Discord Formatter"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    url: StringProperty(default="https://discord.com/developers/")

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_list_input("Discord Threads")
        self.add_list_output("Format Results")

    def draw_buttons(self, context, layout):
        # Add a button that calls the custom operator to open the website
        layout.operator("node.open_dev2_website", text="Open Dev", icon='WORLD').url = self.url
        
    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            import requests
                            import json
                            import datetime
                            import webbrowser
                            """
        self.code_imperative = """
            def format_message(messages):
                formatted_messages = []
                for message in messages:
                    if 'author' in message and 'username' in message['author']:
                        author = message['author']['username']
                    else:
                        author = 'Unknown Author'
                    if 'timestamp' in message:
                        try:
                            format_str = '%Y-%m-%dT%H:%M:%S.%f%z'
                            timestamp = datetime.datetime.strptime(message['timestamp'], format_str)
                            formatted_timestamp = timestamp.strftime('%d/%m/%Y %H:%M:%S')
                        except ValueError:
                            formatted_timestamp = 'Invalid Timestamp'
                    else:
                        formatted_timestamp = 'No Timestamp'
                    content = message['content'] if 'content' in message else 'No content'
                    attachments = []
                    if 'attachments' in message and isinstance(message['attachments'], list):
                        for attachment in message['attachments']:
                            if isinstance(attachment, dict) and 'filename' in attachment and 'size' in attachment and 'url' in attachment:
                                attachment_info = f"{attachment['filename']} ({attachment['size']} bytes): {attachment['url']}"
                                attachments.append(attachment_info)
                    formatted_message = [
                        f"Author: {author}",
                        f"Timestamp: {formatted_timestamp}",
                        f"Content: {content}",
                        f"Attachments: {attachments if attachments else ['No attachments']}"
                    ]
                    formatted_messages.append(formatted_message)
                return formatted_messages
            """
        self.code = f"""messagesform_{self.static_uid} = format_message({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"messagesform_{self.static_uid}"
        self.code += f"\n{self.outputs[0].python_value}"
