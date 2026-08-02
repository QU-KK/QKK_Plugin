import bpy

class SimplePopup(bpy.types.Operator):
    bl_idname = "wm.simple_popup"
    bl_label = "清空变换"

    def draw(self, context):
        layout = self.layout
        layout.operator("mesh.quads_convert_to_tris", text="三角化")
        layout.operator("mesh.tris_convert_to_quads", text="四边化")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=100)


# 先尝试注销，清空“残留”
try:
    bpy.utils.unregister_class(SimplePopup)
except Exception:
    pass

bpy.utils.register_class(SimplePopup)

# 弹出面板
bpy.ops.wm.simple_popup('INVOKE_DEFAULT')