import bpy
from ...base_node import SN_ScriptingBaseNode


class SKD_SN_Display_FrameRate(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SKD_SN_Display_FrameRate"
    bl_label = "Display UI"
    node_color = "INTERFACE"
    bl_width_default = 160

    def on_create(self, context):

        # inputs
        self.add_interface_input()
        self.add_string_input().default_value = "RENDER_MT_framerate_presets"
        self.add_data_input().default_value = "scene.render.fps"

        # outputs
        self.add_interface_output()

    def evaluate(self, context): 
        self.code = f"""
                    {self.active_layout}.menu({self.inputs[1].python_value}, text={self.inputs[2].python_value})
                    {self.indent(self.outputs[0].python_value, 5)}
                    """
        self.code_imperative = f"""
                                def frame_rate_update(scene, texts):
                                    for window in bpy.context.window_manager.windows:
                                        for area in window.screen.areas:
                                            area.tag_redraw()
                                """
        self.code_register = f"""bpy.app.handlers.depsgraph_update_post.append(frame_rate_update)"""
        self.code_unregister = f"""bpy.app.handlers.depsgraph_update_post.remove(frame_rate_update)"""
