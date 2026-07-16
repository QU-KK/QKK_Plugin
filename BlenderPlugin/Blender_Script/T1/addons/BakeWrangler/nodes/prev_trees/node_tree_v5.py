import bpy
from bpy.types import NodeTree, Node, NodeSocket
from ..node_tree import BakeWrangler_Tree_Socket, BakeWrangler_Tree_Node

# Node to globally set bake and output resolutions
class BakeWrangler_Global_Resolution(Node, BakeWrangler_Tree_Node):
    '''Global resolution settings node'''
    bl_label = '分辨率'

    # Inputs are static on this node
    def update_inputs(self):
        pass

    # When toggled as active, any other nodes of the same type need to be deactivated
    def toggle_active(self, context):
        pass

    is_active: bpy.props.BoolProperty(name="活动项", description="使此节点设置全局(一次只能有一个处于活动状态)", default=False, update=toggle_active)
    res_bake_x: bpy.props.IntProperty(name="烘焙X分辨率", description="烘焙贴图的宽度(X)", default=2048, min=1, subtype='PIXEL')
    res_bake_y: bpy.props.IntProperty(name="烘焙Y分辨率", description="烘焙贴图的高度(Y)", default=2048, min=1, subtype='PIXEL')
    res_outp_x: bpy.props.IntProperty(name="图像X分辨率", description="输出图像的宽度(X)(烘焙将按缩放放大或缩小以匹配,此选项通道下采样平滑贴图)", default=2048, min=1, subtype='PIXEL')
    res_outp_y: bpy.props.IntProperty(name="图像Y分辨率", description="输出图像的高度(Y)(烘焙将按缩放放大或缩小以匹配,此选项通道下采样平滑贴图)", default=2048, min=1, subtype='PIXEL')

    def copy(self, node):
        self.is_active = False

    def init(self, context):
        pass
        #BakeWrangler_Tree_Node.init(self, context)
        # Sockets IN
        # Sockets OUT
        # Prefs
        #self.res_bake_x = _prefs("def_glob_bakx")
        #self.res_bake_y = _prefs("def_glob_baky")
        #self.res_outp_x = _prefs("def_glob_outx")
        #self.res_outp_y = _prefs("def_glob_outy")

    def draw_buttons(self, context, layout):
        colres = layout.column(align=True)
        colres.prop(self, "is_active", toggle=True)
        colres.label(text="烘焙分辨率：")
        colres.prop(self, "res_bake_x", text="X")
        colres.prop(self, "res_bake_y", text="Y")
        colres.label(text="输出分辨率：")
        colres.prop(self, "res_outp_x", text="X")
        colres.prop(self, "res_outp_y", text="Y")


classes = (
    BakeWrangler_Global_Resolution,
)


def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

def unregister():
    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)


if __name__ == "__main__":
    register()