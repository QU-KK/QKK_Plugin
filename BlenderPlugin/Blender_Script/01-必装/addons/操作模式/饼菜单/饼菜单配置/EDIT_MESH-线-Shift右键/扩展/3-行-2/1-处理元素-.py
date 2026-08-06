import bpy
# 操作项
class QKK_Duplicate_The_Element(bpy.types.Operator):
    bl_idname = "qkk.duplicate_the_element"
    bl_label = "复制出元素"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        #分离出
        bpy.ops.mesh.separate(type='SELECTED')
        bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "分离出元素完成！")
        return {'FINISHED'}

# 绘制弹出菜单
def draw_menu(self, context):
    layout = self.layout
    layout.scale_y = 1.2
    
    layout.operator("mesh.edge_split", text="线断开", icon='NONE')
    layout.operator("qkk.duplicate_the_element", text="分离出元素", icon='NONE')
 
    #layout.separator()  # 分割线
# 注册操作项
bpy.utils.register_class(QKK_Duplicate_The_Element)
# 弹窗
bpy.context.window_manager.popup_menu(draw_menu, title="处理元素")
