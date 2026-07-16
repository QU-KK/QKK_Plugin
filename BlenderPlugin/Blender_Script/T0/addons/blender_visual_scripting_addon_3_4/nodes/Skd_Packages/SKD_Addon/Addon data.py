import bpy
import addon_utils
import re
import os
from ...base_node import SN_ScriptingBaseNode


class SN_SKD_AddonDataNode(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_AddonDataNode"
    bl_label = "Addon Data"
    node_color = "BOOLEAN"

    def on_create(self, context):
        self.add_string_input("Plugin Name").default_value = "Serpens"
        self.add_boolean_output("Plugin Exists")
        self.add_string_output("Plugin Folder Name")
        self.add_string_output("Plugin Version")
        self.add_string_output("Plugin Description")
        self.add_string_output("Plugin Category")
        self.add_string_output("Plugin Author")
        self.add_string_output("Plugin Location")
        self.add_string_output("Plugin Tracker_url")
        self.add_string_output("Plugin Folder Directory")
        self.add_boolean_output("Plugin Active")
        


    def evaluate(self, context):
        self.code_import = """
                            import addon_utils
                            import re
                            import os
                            """

        self.code_imperative = """
            def get_addon_data(plugin_name):
                return plugin_name in (x.bl_info.get("name") for x in addon_utils.modules())
                plug_act = False
            def get_addon_folder_x(plugin_name):
                plug_act = False
                if get_addon_data(plugin_name):
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

                            if folder_name in bpy.context.preferences.addons:
                                # Check if the add-on is enabled
                                if bpy.context.preferences.addons[folder_name].preferences is not None:
                                    plug_act = True
                            else: 
                                plug_act = False
                                

                            #Return our items for the given plugin
                            return folder_name, module.bl_info.get('version', (-1, -1, -1)) ,module.bl_info.get('description') ,module.bl_info.get('category') ,module.bl_info.get('author') ,module.bl_info.get('location') ,module.bl_info.get('tracker_url'), folder_path, plug_act
                    
                return False, False, False, False, False, False, False, False, False, False
            """

        self.outputs[0].python_value = f"get_addon_data({self.inputs[0].python_value})"
        self.outputs[1].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[0]"
        self.outputs[2].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[1]"
        self.outputs[3].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[2]"
        self.outputs[4].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[3]"
        self.outputs[5].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[4]"
        self.outputs[6].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[5]"
        self.outputs[7].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[6]"
        self.outputs[8].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[7]"
        self.outputs[9].python_value = f"get_addon_folder_x({self.inputs[0].python_value})[8]"