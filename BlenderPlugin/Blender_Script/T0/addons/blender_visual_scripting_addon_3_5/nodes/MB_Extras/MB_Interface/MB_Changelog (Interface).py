import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_MB_Changelog_Interface_Node(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_MB_Changelog_Interface_Node"
    bl_label = "MB_Changelog (Interface)"
    node_color = "INTERFACE"
    bl_width_default = 200

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_interface_input()
        self.add_dynamic_string_input('Input').prev_dynamic = True
        self.add_icon_input('Icon').default_value = 17

        # outputs
        self.add_interface_output()


    def evaluate(self, context):
        # generate the code here
        self.code = f"""
                        row_{self.static_uid} = {self.active_layout}.row(heading='', align=True)
                        row_{self.static_uid}.alignment = 'Left'.upper()
                        row_{self.static_uid}.label(text='Changelog for Version: ')
                        
                        # Convert the version tuple to a string and replace commas with dots
                        version_string = '.'.join(str(v) for v in bpy.context.scene.sn.version)
                        
                        # Use the version string as the text argument to the label method
                        row_{self.static_uid}.label(text=version_string)



                        line_{self.static_uid} = [{",".join([inp.python_value for inp in self.inputs[1:-1] if isinstance(inp.python_value, str)])}]
                        for index_{self.static_uid} in line_{self.static_uid}:
                            if index_{self.static_uid}:
                                row_{self.static_uid} = {self.active_layout}.label(text=index_{self.static_uid}, icon_value={self.inputs['Icon'].python_value})

                        {self.indent(self.outputs[0].python_value, 5)}
                        """

    def evaluate_export(self, context):
        self.code = f"""
                    row_{self.static_uid} = {self.active_layout}.row(heading='', align=True)
                    row_{self.static_uid}.alignment = 'Left'.upper()
                    row_{self.static_uid}.label(text='Changelog for Version:')
                    
                    # Convert the version tuple to a string and replace commas with dots
                    version_string = '.'.join(str(v) for v in {str(tuple(bpy.context.scene.sn.version))})
                        
                    # Use the version string as the text argument to the label method
                    row_{self.static_uid}.label(text=version_string)

                    line_{self.static_uid} = [{",".join([inp.python_value for inp in self.inputs[1:-1] if isinstance(inp.python_value, str)])}]
                    for index_{self.static_uid} in line_{self.static_uid}:
                        if index_{self.static_uid}:
                            row_{self.static_uid} = {self.active_layout}.label(text=index_{self.static_uid}, icon_value={self.inputs['Icon'].python_value})

                    {self.indent(self.outputs[0].python_value, 5)}
                    """