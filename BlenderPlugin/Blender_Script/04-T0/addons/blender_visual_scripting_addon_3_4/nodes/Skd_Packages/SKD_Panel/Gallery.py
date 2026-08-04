import bpy
import os

from ...base_node import SN_ScriptingBaseNode
from ...templates.VariableReferenceNode import VariableReferenceNode

class SN_SKD_Gallery_Node(SN_ScriptingBaseNode, bpy.types.Node, VariableReferenceNode):
    bl_idname = "SN_SKD_Gallery_Node"
    bl_label = "Gallery"
    bl_width_default = 240
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_list_input("Items")
        self.ref_ntree = self.node_tree

    def evaluate(self, context):
        var = self.get_var()
        if var is None:
            return

        self.code_import = """
                            import os
                            """

        self.code_imperative = f"""
                                def load_preview_icons(path):
                                    global _icons
                                    if not path in _icons:
                                        if os.path.exists(path):
                                            _icons.load(path, path, "IMAGE")
                                        else:
                                            return 0
                                    return _icons[path].icon_id

                                def skd_gallery(files_img):
                                    {var.data_path} = []
                                    {var.data_path} = [[img, os.path.splitext(os.path.basename(img))[0], os.path.splitext(os.path.basename(img))[0], load_preview_icons(img)] for idx, img in enumerate(files_img)]
                                
                                """

        self.code = f"""gallery_{self.static_uid} = skd_gallery({self.inputs[1].python_value})"""
        self.outputs[0].python_value = f"gallery_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):
        self.draw_variable_reference(layout)
        if self.get_var() is None:
            layout.label(text="Variable not set!", icon="ERROR")