import bpy
import textwrap
from random import uniform
from ...base_node import SN_ScriptingBaseNode


class SN_SKD_PostNode(SN_ScriptingBaseNode, bpy.types.Node):

    bl_idname = "SN_SKD_PostNode"
    bl_label = "Post It Node"
    bl_width_default = 300
    

    def update_custom_color(self, context):
        # update own color
        self.color = self.custom_color
        
    
    custom_color: bpy.props.FloatVectorProperty(name="Color",
                                size=3, min=0, max=1, subtype="COLOR",
                                description="The color of this node",
                                update=update_custom_color)

    def on_create(self, context):
        self.custom_color = (uniform(0,1), uniform(0,1), uniform(0,1))
        self.add_string_input("String").set_hide(True)


    show_text: bpy.props.BoolProperty(default=False,
                                    name="Add text",
                                    description="Add text to the post note",
                                    update=SN_ScriptingBaseNode._evaluate)



    def draw_node(self, context, layout):

        layout.prop(self, "show_text", icon_value=0, emboss=True, toggle=True)

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