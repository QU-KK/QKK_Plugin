import bpy
from ...base_node import SN_ScriptingBaseNode



class SN_SKD_SwapFromListNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_SwapFromListNode"
    bl_label = "Swap In List"
    node_color = "PROPERTY"


    def on_create(self, context):
        self.add_execute_input()
        self.add_list_input("List")
        self.add_data_input("New Value")
        self.add_data_input("Element")
        
        self.add_execute_output()
        self.add_list_output("New List")

                
    def update_lister(self, context):
        if self.type == "INDEX":
            self.convert_socket(self.inputs[3], self.socket_names["Integer"])
            self.inputs[3].name = "Index"
        else:
            self.convert_socket(self.inputs[3], self.socket_names["Data"])
            self.inputs[3].name = "Element"
        self._evaluate(context)
        
    type: bpy.props.EnumProperty(name="type",
                            description="How to find the element to swap",
                            items=[("ELEMENT", "Element", "Use the elements value to swap it"),
                                   ("INDEX", "Index", "Use the elements index to swap it")],
                            update=update_lister)


    def evaluate(self, context):

        if self.type == "INDEX":

            self.code_imperative = """
                        def swap_listz():
                            lister_return = []
                            lister_return = {self.inputs[1].python_value}
                            lister_return[{self.inputs[3].python_value}] = {self.inputs[2].python_value}
                            return lister_return
                    
                        """
        else:
            self.code_imperative = """
                        def swap_listz():
                            lister_return = []
                            lister_return = {self.inputs[1].python_value}

                            for i in range(len(lister_return)):
                                if lister_return[i] == {self.inputs[3].python_value}:
                                    lister_return[i] = {self.inputs[2].python_value}
                            return lister_return
                        """
        
        self.code = f"""swapped_lists_{self.static_uid} = swap_listz()"""
        self.outputs[1].python_value = f"swapped_lists_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'

    def draw_node(self, context, layout):

        layout.prop(self, "type", text="Select Option", expand=True)