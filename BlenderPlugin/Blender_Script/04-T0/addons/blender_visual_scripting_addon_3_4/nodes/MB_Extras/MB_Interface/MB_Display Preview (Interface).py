import bpy
from ...base_node import SN_ScriptingBaseNode


class SN_MB_DisplayPreview_Node(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_MB_DisplayPreview_Node"
    bl_label = "MB_Display Preview (Interface)"
    node_color = "INTERFACE"
    bl_width_default = 200

    def on_create(self, context):
        # create your sockets here

        # inputs
        self.add_interface_input()
        self.add_boolean_input('Show Buttons').default_value = True

        # outputs
        self.add_interface_output().passthrough_layout_type = True

    def evaluate(self, context):
		# generate the code here
        self.code = f"""
                    bool = {self.inputs['Show Buttons'].python_value}
                    def get_id_preview_id(data):
                        if hasattr(data, "preview"):
                            if not data.preview:
                                data.preview_ensure()
                            if hasattr(data.preview, "icon_id"):
                                return data.preview.icon_id
                        return 0
                    {self.active_layout}
                    row_{self.static_uid} = layout.row(heading='', align=True)
                    row_{self.static_uid}.enabled = True
                    row_{self.static_uid}.active = True
                    row_{self.static_uid}.alignment = 'Expand'.upper()
                    row_{self.static_uid}.template_icon(icon_value=get_id_preview_id(bpy.data.materials[bpy.context.view_layer.objects.active.active_material.name]), scale=7.0)
                    
                    if bool:
                        col_{self.static_uid} = row_{self.static_uid}.column(heading='', align=True)
                        col_{self.static_uid}.enabled = True
                        col_{self.static_uid}.active = True
                        col_{self.static_uid}.scale_x = 1.5
                        col_{self.static_uid}.scale_y = 1.0
                        col_{self.static_uid}.alignment = 'Expand'.upper()
                        col_{self.static_uid}.prop(bpy.context.view_layer.objects.active.active_material, 'preview_render_type', text='', icon_value=0, emboss=True, expand=True)
                        col_{self.static_uid}.separator(factor=0.5)
                        col_{self.static_uid}.prop(bpy.context.view_layer.objects.active.active_material, 'use_preview_world', text='', icon_value=82, emboss=True, expand=True)
                    else:
                        pass

                    {self.indent(self.outputs[0].python_value, 5)}
                    """

    def draw_node(self, context, layout):
        box = layout.box()
        box.label(text="Only materials can be displayed", icon="INFO")
