import bpy
import sys
import textwrap
from ...base_node import SN_ScriptingBaseNode

# Console capture class to redirect and capture stdout
class ConsoleCapture:
    def __init__(self):
        self.output = ''
        self.is_enabled = False  # Flag to enable/disable capturing
        self.original_stdout = sys.stdout  # Store original stdout
        sys.stdout = self

    def write(self, message):
        if not self.is_enabled:
            self.original_stdout.write(message)
            return
        
        if message.startswith('-') or message.startswith('Compiled successfully!'):
            return
        
        self.output += message + '\n'
        # Update the node's custom property with the latest output
        if hasattr(self, 'node'):
            self.node['console_output'] = self.output

    def get_output(self):
        return self.output

    def clear_output(self):
        self.output = ''
        if hasattr(self, 'node'):
            self.node['console_output'] = ''

    def toggle_capture(self, enable):
        self.is_enabled = enable

# Initialize console capture
console_capture = ConsoleCapture()

# Define custom node class
class SN_SKD_Console(bpy.types.Node, SN_ScriptingBaseNode):
    bl_idname = "SN_SKD_Console"
    bl_label = "Console Printer"
    bl_width_default = 500

    print_to_node: bpy.props.BoolProperty(name="Print to Node", default=False)
    export_button: bpy.props.BoolProperty(name="Export Prints", default=False)

    console_output: bpy.props.StringProperty(name="Console Output", default="")

    def draw_buttons(self, context, layout):
        
        box = layout.box()

        if self.console_output:
            texters = self.console_output
            width = self.width
            threshold = (int(width / 12) if int(width <= 150) else int(width / 7))
            text_to_wrap = texters
            wrap = textwrap.TextWrapper(width=threshold)
            wrapped_list = wrap.wrap(text=text_to_wrap)
            for item in wrapped_list:
                box.label(text=item)

        row = layout.row()
        row.prop(self, "print_to_node", text="Print to Node", toggle=True)
        row.operator("node.clear_output_button", text="Clear Output")
        row.operator("node.print_output_button", text="Print Output")

        if self.print_to_node != console_capture.is_enabled:
            console_capture.node = self  # Set the node for console capture
            console_capture.toggle_capture(self.print_to_node)

# Define an operator to clear the output
class ClearOutputButton(bpy.types.Operator):
    bl_idname = "node.clear_output_button"
    bl_label = "Clear Output"
    
    def execute(self, context):
        console_capture.clear_output()
        return {'FINISHED'}

# Define an operator to print the output
class PrintOutputButton(bpy.types.Operator):
    bl_idname = "node.print_output_button"
    bl_label = "Print Output"
    
    def execute(self, context):
        node = context.node
        if 'console_output' in node:
            text_to_print = node['console_output']  # Get captured output
        
            # Remove blank lines from the text
            lines = text_to_print.split('\n')
            non_empty_lines = [line for line in lines if line.strip()]
            filtered_text = '\n'.join(non_empty_lines)
            # Prefix ANSI escape code for yellow color and suffix ANSI escape code for resetting color
            colored_text = "\033[33m\033[7m\033[3m" + filtered_text + "\033[0m"
        
            self.report({'INFO'}, "SKD Console Output:\n" + colored_text)  # Display in Blender's info panel
        return {'FINISHED'}