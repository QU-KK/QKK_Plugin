import bpy


bpy.ops.mesh.omnioutset_smart_face('INVOKE_DEFAULT')
#bpy.ops.mesh.omnioutset_edge('INVOKE_DEFAULT')



#def draw(self, context):
#    layout = self.layout
#    layout.operator("object.location_clear", text="清空位置")
#    layout.operator("object.rotation_clear", text="清空旋转")
#    layout.operator("object.scale_clear", text="清空缩放")

#bpy.context.window_manager.popup_menu(
#    draw,
#    title="清空变换",
#    icon='OBJECT_ORIGIN'
#)