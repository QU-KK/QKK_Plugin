import bpy


def draw_tools_panel(self, context):
    col = self.layout.column()
    col.scale_x = 1.0
    col.scale_y = 1.5
    col.operator("openmatpanel.open_mat_panel", text="", icon="SHADING_RENDERED")


class OPENMATPANEL_OT_open_mat_panel(bpy.types.Operator):
    bl_idname = "openmatpanel.open_mat_panel"
    bl_label = "Open_Mat_Panel"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.screen.area_split(direction="HORIZONTAL", factor=0.4)  # VERTICAL
        areas = bpy.context.screen.areas
        area = areas[int(len(areas) - 1.0)]
        area.ui_type = "ShaderNodeTree"
        return {"FINISHED"}


def draw_node_mt_editor_menus_menu(self, context):
    self.layout.operator("openmatpanel.close_panel", text="", icon="QUIT")


class OPENMATPANEL_OT_close_panel(bpy.types.Operator):
    bl_idname = "openmatpanel.close_panel"
    bl_label = "Close_Panel"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        bpy.ops.screen.area_close()
        return {"FINISHED"}


def register():
    bpy.types.VIEW3D_PT_tools_active.append(draw_tools_panel)
    bpy.types.NODE_MT_editor_menus.prepend(draw_node_mt_editor_menus_menu)


def unregister():
    bpy.types.VIEW3D_PT_tools_active.remove(draw_tools_panel)
    bpy.types.NODE_MT_editor_menus.remove(draw_node_mt_editor_menus_menu)
