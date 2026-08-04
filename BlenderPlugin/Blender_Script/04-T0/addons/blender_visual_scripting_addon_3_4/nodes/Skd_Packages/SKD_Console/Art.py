import bpy
import random
from ...base_node import SN_ScriptingBaseNode

class SN_SKD_ASCII_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_ASCII_Node"
    bl_label = "Print ASCII"
    node_color = "PROPERTY"


    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()
        self.add_string_input("ASCII File").subtype = "FILE_PATH"

                
    def evaluate(self, context):

        self.code_import = """
                            import random
                            """

        self.code_imperative = """
                    # ANSI color codes
                    colors = [
                        '\033[91m',  # Red
                        '\033[92m',  # Green
                        '\033[93m',  # Yellow
                        '\033[94m',  # Blue
                        '\033[95m',  # Magenta
                        '\033[96m',  # Cyan
                        '\033[97m',  # White
                        '\033[90m',  # Bright Black
                        '\033[31m',  # Bright Red
                        '\033[32m',  # Bright Green
                        '\033[33m',  # Bright Yellow
                        '\033[34m',  # Bright Blue
                        '\033[35m',  # Bright Magenta
                        '\033[36m',  # Bright Cyan
                        '\033[37m',  # Bright White
                        '\033[0m'    # Reset
                    ]

                    def print_colored_ascii_art(file_path):
                        with open(file_path, 'r') as file:
                            art = file.read()
                        lines = art.split('\\n')
                        max_len = max(len(line) for line in lines)  # Find the maximum line length
                        random_colors = [random.choice(colors[:-1]) for _ in range(max_len)]  # Random color for each column
                        
                        for line in lines:
                            colored_line = ''
                            for i, char in enumerate(line.ljust(max_len)):
                                if char != ' ':
                                    colored_line += random_colors[i] + char
                                else:
                                    colored_line += char
                            print(colored_line + colors[-1])  # Reset color at the end of each line
        """
        
        self.code = f"""print_colored_art_{self.static_uid} = print_colored_ascii_art({self.inputs[1].python_value})"""
        self.outputs[0].python_value = f"print_colored_art_{self.static_uid}"
        self.code += f'\n{self.outputs[0].python_value}'