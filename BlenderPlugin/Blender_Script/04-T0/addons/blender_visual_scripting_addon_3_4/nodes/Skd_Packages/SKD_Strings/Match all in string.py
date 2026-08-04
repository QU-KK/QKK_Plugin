import bpy
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_matchPlus(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_matchPlus"
    bl_label = "Match in String"
    bl_width_default = 200
    node_color = "STRING"
    
    def on_create(self, context):
        self.add_string_input("String Input")
        self.add_string_input("Sub String") 
        self.add_string_input("Split On") 
        self.add_boolean_input("Match All") 

        self.add_boolean_output("Matches Found")
        self.add_list_output("Matches")
        self.add_list_output("No Matches")  

    def evaluate(self, context):
        
        self.code_imperative = f"""
            def find_matches(main_string: str, pattern_string: str, match_all: bool, split_char: str) -> (bool, list, list):
                patterns = pattern_string.split(split_char)
                matches = [pattern for pattern in patterns if pattern in main_string]
                not_found = [pattern for pattern in patterns if pattern not in main_string]
                found = (len(matches) == len(patterns)) if match_all else (len(matches) > 0)
                return found, matches, not_found
            """
        self.code = f"""find_matches({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[3].python_value},{self.inputs[2].python_value})"""
        self.outputs[0].python_value = f"find_matches({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[3].python_value},{self.inputs[2].python_value})[0]"
        self.outputs[1].python_value = f"find_matches({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[3].python_value},{self.inputs[2].python_value})[1]"
        self.outputs[2].python_value = f"find_matches({self.inputs[0].python_value},{self.inputs[1].python_value},{self.inputs[3].python_value},{self.inputs[2].python_value})[2]"
