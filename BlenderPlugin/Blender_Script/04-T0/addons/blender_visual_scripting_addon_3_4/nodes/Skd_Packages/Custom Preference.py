import bpy 
from ..base_node import SN_ScriptingBaseNode
class SN_SKD_CustomPreference(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_CustomPreference"
    bl_label = "Custom Preference"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_boolean_input("Pref Switcher")
        self.add_boolean_output("Pref Status")
        
    def evaluate(self, context):
        
        self.code_import = """
                            import bpy
                            from bl_ui import space_userpref
                            """
        self.code_imperative = """
                def fn_reg_unreg_prefs(Checker):
                    scene = bpy.context.scene
                    for cls in space_userpref.classes:
                        try:
                            if Checker:
                                bpy.utils.unregister_class(cls)
                            else:
                                bpy.utils.register_class(cls)
                        except:
                            pass
                    """
        
        self.code = f"""fn_reg_unreg_prefs({self.inputs[1].python_value})"""
        self.outputs[1].python_value = f"{self.inputs[1].python_value}"
        self.code += f'\n{self.outputs[0].python_value}'

