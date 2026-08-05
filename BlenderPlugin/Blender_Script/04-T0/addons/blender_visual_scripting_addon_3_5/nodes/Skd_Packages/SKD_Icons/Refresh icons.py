import bpy
import bpy.utils.previews
import os

from ...base_node import SN_ScriptingBaseNode
class SN_SKD_Refresh_Icons(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Refresh_Icons"
    bl_label = "Refresh Icons"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        
        
    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            import bpy.utils.previews
                            import os
                            """
   
        self.code_imperative = """
                _icons = None

                def remove_previews(previews):
                    if previews:
                        bpy.utils.previews.remove(previews)

                def get_previews_from_directory(directory, previews=None):
                    if previews is None:
                        previews = bpy.utils.previews.new()

                    # Supported file extensions (lowercase)
                    supported_extensions = {".png", ".jpg", ".jpeg"}

                    if os.path.isdir(directory):
                        for file_name in os.listdir(directory):
                            ext = os.path.splitext(file_name)[1].lower()  # Get file extension in lowercase
                            if ext in supported_extensions:
                                filepath = os.path.join(directory, file_name)
                                previews.load(file_name, filepath, 'IMAGE')
                    
                    return previews

                def reload_icons():

                    global _icons  

                    # Remove existing previews if they exist
                    if "_icons" in globals() and _icons is not None:
                        bpy.utils.previews.remove(_icons)
                        _icons = None  # Clear the reference

                    # Create a new preview collection
                    _icons = bpy.utils.previews.new()

                    # Determine the add-on's directory dynamically
                    addon_directory = os.path.dirname(os.path.abspath(__file__))
                    addon_icon_directory = os.path.join(addon_directory, "icons")

                    # Load previews from directories
                    _icons = get_previews_from_directory(addon_icon_directory, previews=_icons)
                    _icons = get_previews_from_directory(
                        os.path.join(addon_icon_directory, "placeholder"),
                        previews=_icons
                    )

                    # Force UI refresh
                    for window in bpy.context.window_manager.windows:
                        for area in window.screen.areas:
                            area.tag_redraw()

                    """
        
        self.outputs[0].python_value = f"reload_icons()"
        self.code += f'\n{self.outputs[0].python_value}'