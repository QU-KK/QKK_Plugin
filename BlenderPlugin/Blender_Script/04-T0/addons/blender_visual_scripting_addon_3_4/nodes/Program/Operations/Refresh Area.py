import bpy
from ...base_node import SN_ScriptingBaseNode



class SN_RefreshAreaNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_RefreshAreaNode"
    bl_label = "Refresh Area"
    bl_width_default = 200
    node_color = "PROGRAM"
    
    def on_create(self, context):
        self.add_execute_input()
        self.add_execute_output()

    def area_items(self,context):
        types = ["VIEW_3D", "IMAGE_EDITOR", "NODE_EDITOR", "SEQUENCE_EDITOR",
                 "CLIP_EDITOR", "DOPESHEET_EDITOR", "GRAPH_EDITOR", "NLA_EDITOR",
                 "TEXT_EDITOR", "CONSOLE", "INFO", "TOPBAR", "STATUSBAR", "OUTLINER",
                 "PROPERTIES", "FILE_BROWSER", "PREFERENCES"]
        items = []
        for a_type in types:
            items.append((a_type,a_type.replace("_"," ").title(),a_type))
        return items
    
    area_type: bpy.props.EnumProperty(name="Area Type",
                                    description="The type of area to find",
                                    items=area_items,
                                    update=SN_ScriptingBaseNode._evaluate)
    
    def evaluate(self, context):
        self.code = f"""
                    next((area.tag_redraw() for area in bpy.context.screen.areas if area.type == "{self.area_type}"), None)
                    {self.indent(self.outputs[0].python_value, 5)}
                    """
    def draw_node(self, context, layout):
        layout.prop(self, "area_type", text="Area Type")