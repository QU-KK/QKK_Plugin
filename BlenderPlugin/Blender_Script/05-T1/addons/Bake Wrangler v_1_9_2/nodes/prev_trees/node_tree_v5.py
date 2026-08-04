import bpy
from bpy.types import NodeTree, Node, NodeSocket
from ..node_tree import BakeWrangler_Tree_Socket, BakeWrangler_Tree_Node

# Node to globally set bake and output resolutions
class BakeWrangler_Global_Resolution(Node, BakeWrangler_Tree_Node):
    '''Global resolution settings node'''
    bl_label = 'Resolutions'

    # Inputs are static on this node
    def update_inputs(self):
        pass

    # When toggled as active, any other nodes of the same type need to be deactivated
    def toggle_active(self, context):
        pass

    is_active: bpy.props.BoolProperty(name="Active", description="Causes this nodes settings to be used globally (only one can be active at a time)", default=False, update=toggle_active)
    res_bake_x: bpy.props.IntProperty(name="Bake X resolution ", description="Width (X) to bake maps at", default=2048, min=1, subtype='PIXEL')
    res_bake_y: bpy.props.IntProperty(name="Bake Y resolution ", description="Height (Y) to bake maps at", default=2048, min=1, subtype='PIXEL')
    res_outp_x: bpy.props.IntProperty(name="Image X resolution ", description="Width (X) to output images at (bake will be scaled up or down to match, use this to smooth maps by down sampling)", default=2048, min=1, subtype='PIXEL')
    res_outp_y: bpy.props.IntProperty(name="Image Y resolution ", description="Height (Y) to output images at (bake will be scaled up or down to match, use this to smooth maps by down sampling)", default=2048, min=1, subtype='PIXEL')

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
        colres.label(text="Bake Resolution:")
        colres.prop(self, "res_bake_x", text="X")
        colres.prop(self, "res_bake_y", text="Y")
        colres.label(text="Output Resolution:")
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