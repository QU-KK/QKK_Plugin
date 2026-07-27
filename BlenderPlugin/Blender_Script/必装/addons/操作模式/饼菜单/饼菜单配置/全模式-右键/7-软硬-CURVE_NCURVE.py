import bpy
bpy.ops.sna.mod_normal_33321('INVOKE_DEFAULT')

#bpy.ops.sna.open_f0c59('INVOKE_DEFAULT')




#class SimplePopup(bpy.types.Operator):
#    bl_idname = "wm.simple_popup" 
#    bl_label = "自动光滑"      

#    def draw(self, context):
#        self.layout.operator("mesh.primitive_cube_add", text="按钮 1 (生成立方体)")
#        self.layout.operator("mesh.primitive_monkey_add", text="按钮 2 (生成猴头)")

#    def execute(self, context):
#        return {'FINISHED'}

#    def invoke(self, context, event):
#        return context.window_manager.invoke_props_dialog(self)

# ==========================================
# 核心改动：先尝试注销，清空“残留”
# ==========================================
#try:
#    bpy.utils.unregister_class(SimplePopup)
#except Exception:
#    pass  # 如果是第一次运行，没东西可注销，就直接跳过
# 重新干干净净地注册
#bpy.utils.register_class(SimplePopup)
# 弹出面板
#bpy.ops.wm.simple_popup('INVOKE_DEFAULT')