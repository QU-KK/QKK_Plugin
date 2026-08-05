import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_SKD_List_item_amount(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_List_item_amount"
    bl_label = "Item Amount In List"
    node_color = "PROPERTY"

    def on_create(self, context):
        self.add_list_input("list")
        self.add_data_input("Search Item")

        self.add_boolean_output("Item In List")
        self.add_list_output("Index Of Item")
        self.add_integer_output("Amount Found")


    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def find_variable_in_list(my_list, my_checker):

                # Initialize variables to store results
                found_matches = []
                num_matches = 0

                # Iterate through the list and check for matches
                for i, item in enumerate(my_list):
                    if item == my_checker:
                        found_matches.append(i)
                        num_matches += 1

                # Return the results
                return num_matches > 0, found_matches, num_matches

            """
        self.code = f"""find_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})"""
        self.outputs[0].python_value = f"find_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})[0]"
        self.outputs[1].python_value = f"find_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})[1]"
        self.outputs[2].python_value = f"find_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})[2]"
        #self.code += f'\n{self.outputs[0].python_value}'