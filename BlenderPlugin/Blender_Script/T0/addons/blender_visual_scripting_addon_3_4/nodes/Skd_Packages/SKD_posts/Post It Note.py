import bpy
import textwrap
from random import uniform
from ...base_node import SN_ScriptingBaseNode


class SN_SKD_PostItNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_PostItNode"
    bl_label = "Post It Note"
    bl_width_default = 300
    node_color = (0.800,0.656,0.010)

    def on_create(self, context):
        self.add_string_input("String").set_hide(True)


    show_text: bpy.props.BoolProperty(default=False,
                                    name="Add text",
                                    description="Add text to the post note",
                                    update=SN_ScriptingBaseNode._evaluate)


    def draw_node(self, context, layout):

        layout.prop(self, "show_text" , icon_value=0, emboss=True, toggle=True)

        if self.show_text:
            layout.prop(self.inputs["String"], "default_value", text="")

        box = layout.box()
        remove_quotes = self.inputs["String"].python_value
        texters = remove_quotes.replace("'", '')
        width = self.width
        threshold = (int(width / 12) if int(width <= 150) else int(width / 7))
        textTowrap = texters      
        wrapp = textwrap.TextWrapper(width=threshold)       
        wList = wrapp.wrap(text=textTowrap)
        for item in wList:
            box.label(text=item)