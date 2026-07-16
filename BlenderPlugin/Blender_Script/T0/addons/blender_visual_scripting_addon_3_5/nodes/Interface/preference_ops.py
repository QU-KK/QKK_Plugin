import bpy



class SN_OT_OpenPreferences(bpy.types.Operator):
    bl_idname = "sn.open_preferences"
    bl_label = "Open Preferences"
    bl_description = "Open Preferences"
    bl_options = {"REGISTER", "UNDO"}
    
    navigation: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        has_prefs = False
        for area in context.screen.areas:
            if area.type == "PREFERENCES":
                has_prefs = True
                break
        if not has_prefs:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
        context.preferences.active_section = "ADDONS"
        context.window_manager.addon_search = "Serpens"
        addon_module = __name__.partition('.')[0]
        context.preferences.addons[addon_module].preferences.navigation = self.navigation
        bpy.ops.preferences.addon_expand(module=addon_module)
        return {"FINISHED"}
