import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_SKD_List_remove_item(bpy.types.Node, SN_ScriptingBaseNode):

    bl_idname = "SN_SKD_List_remove_item"
    bl_label = "Remove List Duplicate"
    node_color = "PROPERTY"

    def on_create(self, context):
        self.add_list_input("list")
        self.add_data_input("Remove Duplicate Item")

        self.add_boolean_output("Item In List")
        self.add_list_output("Index Of Item")
        self.add_integer_output("Amount Removed")


    def evaluate(self, context):
        self.code_import = """
                            import bpy
                            """

        self.code_imperative = """
            def remove_variable_in_list(rm_list, rm_checker):

                # Count occurrences of the variable in the list
                count = rm_list.count(rm_checker)

                # If there is only one occurrence, return the original list and count
                if count <= 1:
                    return False, rm_list, 0

                # Remove additional occurrences of the variable
                removed_count = 0
                for i in range(count - 1):
                    index = rm_list.index(rm_checker, rm_list.index(rm_checker) + 1)
                    rm_list.pop(index)
                    removed_count += 1

                return True, rm_list, removed_count

            """
        self.code = f"""remove_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})"""
        self.outputs[0].python_value = f"remove_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})[0]"
        self.outputs[1].python_value = f"remove_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})[1]"
        self.outputs[2].python_value = f"remove_variable_in_list({self.inputs[0].python_value},{self.inputs[1].python_value})[2]"


        #self.code += f'\n{self.outputs[0].python_value}'