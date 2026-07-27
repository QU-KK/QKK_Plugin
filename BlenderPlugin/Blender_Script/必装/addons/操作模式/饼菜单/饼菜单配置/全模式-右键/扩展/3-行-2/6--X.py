import bpy
# 清空  位置  旋转  缩放
class SimplePopup(bpy.types.Operator):
    bl_idname = "wm.simple_popup" 
    bl_label = "清空变换"      

    def draw(self, context):
        self.layout.operator("mesh.primitive_cube_add", text="清空位置")
        self.layout.operator("mesh.primitive_monkey_add", text="清空旋转")
        self.layout.operator("mesh.primitive_monkey_add", text="清空缩放")

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

# ==========================================
# 核心改动：先尝试注销，清空“残留”
# ==========================================
try:
    bpy.utils.unregister_class(SimplePopup)
except Exception:
    pass  # 如果是第一次运行，没东西可注销，就直接跳过
# 重新干干净净地注册
bpy.utils.register_class(SimplePopup)
# 弹出面板
bpy.ops.wm.simple_popup('INVOKE_DEFAULT')