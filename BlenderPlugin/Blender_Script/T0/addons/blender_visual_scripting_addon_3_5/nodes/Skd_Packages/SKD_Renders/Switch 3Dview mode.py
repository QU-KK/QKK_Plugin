import bpy


from ...base_node import SN_ScriptingBaseNode
class SN_SKD_3dView_mode(SN_ScriptingBaseNode, bpy.types.Node):
    bl_idname = "SN_SKD_3dView_mode"
    bl_label = "Switch 3Dviewport view mode"
    bl_width_default = 240
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()

    type: bpy.props.EnumProperty(name="",
                                 items=[("WIREFRAME", "WIREFRAME", "WIREFRAME",),
                                        ("SOLID", "SOLID", "SOLID",),
                                        ("MATERIAL", "MATERIAL", "MATERIAL",),
                                        ("RENDERED", "RENDERED", "RENDERED",)
                                        ],
                                 update=SN_ScriptingBaseNode._evaluate)


    def evaluate(self, context):

        self.code_import = f"""
                            import bpy
                            """
        self.code_imperative = f"""

                def change_viewmode_skd(viewmode):

                    for window in bpy.context.window_manager.windows:
                        for area in window.screen.areas:
                            if area.type == 'VIEW_3D':
                                for space in area.spaces:
                                    if space.type == 'VIEW_3D':
                                        space.shading.type = viewmode

                    """
        
        self.code = f"""change_viewmode_skd("{self.type}")"""
        self.code += f'\n{self.outputs[0].python_value}'


    def draw_node(self, context, layout):
        layout.prop(self, "type", text="Select type")