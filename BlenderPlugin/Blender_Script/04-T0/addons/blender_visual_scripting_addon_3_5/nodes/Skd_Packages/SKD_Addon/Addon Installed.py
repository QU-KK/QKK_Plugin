import bpy
import addon_utils
import os
from ...base_node import SN_ScriptingBaseNode


class SN_SKD_AddonInstalledNode(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_AddonInstalledNode"
    bl_label = "Addon Installed"
    node_color = "BOOLEAN"

    def on_create(self, context):
        self.add_string_input("Plugin Name").default_value = "Serpens"
        self.add_boolean_output("Plugin Exists")
        self.add_string_output("Plugin Name")

    def evaluate(self, context):
        self.code_import = """
                            import addon_utils
                            import os
                            """

        self.code_imperative = """
            def get_addon_installed(plugin_name):
                return plugin_name in (x.bl_info.get("name") for x in addon_utils.modules())

            def get_addon_folder(plugin_name):
                if get_addon_installed(plugin_name):
                    for module in addon_utils.modules():
                        info = addon_utils.module_bl_info(module)
                        if info['name'] == plugin_name:
                            filepath = module.__file__
                            folder_path = os.path.dirname(filepath)
                            folder_name = os.path.basename(folder_path)
                            if folder_name == 'addons':
                                folder_name = os.path.basename(os.path.dirname(folder_path))
                                file_name = os.path.splitext(os.path.basename(filepath))[0]
                                folder_name = file_name
                            else:
                                folder_name = os.path.splitext(folder_name)[0]
                            return folder_name
                return "False"
            """

        self.outputs[0].python_value = f"get_addon_installed({self.inputs[0].python_value})"
        self.outputs[1].python_value = f"get_addon_folder({self.inputs[0].python_value})"
