import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_Enum_Swapper(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_Enum_Swapper"
    bl_label = "Enum Switcher"
    node_color = "PROPERTY"

    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("Enum")
        self.add_string_input("Current Item")
        self.add_string_output("Next")
        self.add_string_output("Previous")

    def evaluate(self, context):
        self.code_imperative = f"""
            def find_neighbors(var):
                enum_name = "{self.inputs[1].python_value}".replace("SCENE_PLACEHOLDER.", "")[1:-1]
                
                # Check if the property exists
                if hasattr(bpy.types.Scene, enum_name):
                    # Access the enum property
                    enum_property = bpy.types.Scene.bl_rna.properties[enum_name]
                    
                    # Extract the items
                    enum_items = enum_property.enum_items

                    # Store items in a list
                    enum_list = [item.identifier for item in enum_items]

                    if len(enum_list) < 3:
                        return None, None
                    
                    if var not in enum_list:
                        return None, None
                    
                    index = enum_list.index(var)
                    
                    previous_item = enum_list[index - 1] if index > 0 else enum_list[-1]
                    next_item = enum_list[index + 1] if index < len(enum_list) - 1 else enum_list[0]
                    
                    return previous_item, next_item
                else:
                    print(f"The enum property '{{enum_name}}' does not exist in bpy.types.Scene")
                    return None, None
            """

        self.code = f"""find_neighbors_{self.static_uid} = find_neighbors({self.inputs[2].python_value})"""
        self.outputs[1].python_value = f"find_neighbors_{self.static_uid}[1]"
        self.outputs[2].python_value = f"find_neighbors_{self.static_uid}[0]"
        self.code += f'\n{self.outputs[0].python_value}'