import bpy
import textwrap

from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Custom_Wrap(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_Custom_Wrap"
    bl_label = "Wrap Text"
    node_color = "INTERFACE"

    def on_create(self, context):
        self.add_string_input("Text to wrap")
        self.add_integer_input("Break Point").default_value = 405
        self.add_integer_input("High").default_value = 12
        self.add_integer_input("Low").default_value = 8
        self.add_list_output("Text List Output")
        

    def evaluate(self, context):
        self.code_import = """
                            import textwrap
                            """
        self.code_imperative = f"""
            def wrap_text(texters):
                threshold = (int(bpy.context.region.width / {self.inputs[2].python_value}) if int(bpy.context.region.width <= {self.inputs[1].python_value}) else int(bpy.context.region.width / {self.inputs[3].python_value}))
                textTowrap = texters      
                wrapp = textwrap.TextWrapper(width=threshold)       
                wList = wrapp.wrap(text=textTowrap) 
                return wList
            """
        self.outputs[0].python_value = f"wrap_text({self.inputs[0].python_value})"