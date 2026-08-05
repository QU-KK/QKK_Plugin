import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Panel_Name(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Panel_Name"
    bl_label = "Change N Panel Name"
    node_color = "PROGRAM"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Addon Name")
        self.add_string_input("New Category")


    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def get_addon_panels(addon_module_name):
                panels = []
                for cls_name in dir(bpy.types):
                    panel_class = getattr(bpy.types, cls_name)
                    if hasattr(panel_class, "bl_category") and hasattr(panel_class, "bl_idname"):
                        # Check if the panel class is part of the addon's module
                        if panel_class.__module__.startswith(addon_module_name):
                            panels.append(panel_class)
                return panels

            def change_addon_panel_category(addon_module_name, new_category):
                panels = get_addon_panels(addon_module_name)
                if panels:
                    for panel_class in panels:
                        old_category = panel_class.bl_category
                        panel_class.bl_category = new_category
                        # Unregister and re-register the panel class to apply the change
                        bpy.utils.unregister_class(panel_class)
                        bpy.utils.register_class(panel_class)
                else:
                    print("No panels found for addon to change category.")
            """

        self.code = f"""change_addon_panel_category({self.inputs[1].python_value},{self.inputs[2].python_value})"""
        self.code += f'\n{self.outputs[0].python_value}'