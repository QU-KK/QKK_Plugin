import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_SKD_List_clear_item(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_List_clear_item"
    bl_label = "Clean List Duplicate"
    node_color = "PROPERTY"

    def on_create(self, context):
        self.add_list_input("list")
        self.add_list_output("Clean List")


    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def clean_variable_in_list(cm_list):

                seen = set()
                unique_list = [x for x in cm_list if x not in seen and not seen.add(x)]
                return unique_list

            """
        self.code = f"""clean_variable_in_list({self.inputs[0].python_value})"""
        self.outputs[0].python_value = f"clean_variable_in_list({self.inputs[0].python_value})"