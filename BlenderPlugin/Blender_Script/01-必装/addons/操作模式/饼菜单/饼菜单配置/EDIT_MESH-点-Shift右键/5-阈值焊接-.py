import bpy
#阈值焊接
def draw_menu(self, context):
    layout = self.layout
    layout.scale_y = 1.2
    layout.operator("mesh.remove_doubles", text="阈值焊接", icon='NONE')

bpy.context.window_manager.popup_menu(draw_menu, title="阈值焊接")