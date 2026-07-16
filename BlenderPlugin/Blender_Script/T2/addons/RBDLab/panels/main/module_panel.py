class ModulePanel():
    rbdlab_section = ""
    bl_category = "RBDLab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_parent_id = "RBDLAB_PT_panel_manager"

    @classmethod
    def poll(cls, context):
        return cls.rbdlab_section == context.scene.rbdlab.ui.main_modules
