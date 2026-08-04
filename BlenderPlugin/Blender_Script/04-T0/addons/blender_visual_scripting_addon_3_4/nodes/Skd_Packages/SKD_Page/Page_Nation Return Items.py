import bpy
import math
from ...base_node import SN_ScriptingBaseNode

class PageNationReturnItems(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "PageNationReturnItems"
    bl_label = "Page Return Items"
    node_color = "FLOAT"

    def on_create(self, context):
        self.add_integer_input("Start Index") 
        self.add_integer_input("End Index") 
        self.add_list_input("List Of Items") 
        self.add_boolean_input("Start at position 1") 
        self.add_list_output("Returned Items")

    def evaluate(self, context):
        self.code_import = """
                            import math
                            """

        self.code_imperative = """
            def skd_Return_Items(start_index, end_index, list_to_get_items, boolean_to_remove_one_index_count):
                
                # Adjust indices if boolean is ticked
                if boolean_to_remove_one_index_count:
                    start_index -= 1
                    end_index -= 1

                # Ensure indices are within bounds
                start_index = max(0, start_index)
                end_index = min(len(list_to_get_items) - 1, end_index)

                # Ensure valid range
                if start_index > end_index:
                    return []

                return list_to_get_items[start_index:end_index + 1]
         
                """
        
        self.outputs[0].python_value = self.code = f"""skd_Return_Items({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[2].python_value},{self.inputs[3].python_value})"""
