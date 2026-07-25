import bpy
from bpy.types import Panel
from bl_ui.utils import PresetPanel
from ...qbpy.blender import preferences
from ..utils.icon import icon


class Unity:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Unity"

    def draw_list(
        self,
        layout,
        listtype_name,
        dataptr,
        propname: str,
        active_propname: str,
        tooltip="",
        rows=4,
    ):
        row = layout.row()
        row.template_list(
            listtype_name,
            "",
            dataptr=dataptr,
            active_dataptr=dataptr,
            propname=propname,
            active_propname=active_propname,
            item_dyntip_propname=tooltip,
            rows=rows,
            sort_lock=True,
        )
        col = row.column(align=True)
        return col


class UNITY_PT_tool(Panel, Unity):
    bl_label = "Tool"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2

        col = layout.column()
        col.operator("unity.rename", icon="GREASEPENCIL")


class UNITY_PT_collider(Panel, Unity):
    bl_label = "Collider"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2

        vhacd = preferences().unity.vhacd

        col = layout.column(align=False)
        col.operator("unity.collider_box", icon="MESH_CUBE")
        col.operator("unity.collider_capsule", icon="MESH_CAPSULE")
        col.operator("unity.collider_cylinder", icon="MESH_CYLINDER")
        col.operator("unity.collider_sphere", icon="MESH_UVSPHERE")
        if bpy.app.build_platform == b"Windows" and context.mode == "OBJECT" and vhacd.path:
            col.operator("unity.collider_convex_vhacd", icon="MESH_ICOSPHERE")
        else:
            col.operator("unity.collider_convex", icon="MESH_ICOSPHERE")


class UNITY_PT_lod_preset(PresetPanel, Panel):
    bl_label = "LODs Presets"

    def draw(self, context):
        layout = self.layout
        layout.emboss = "PULLDOWN_MENU"
        layout.operator_context = "EXEC_DEFAULT"

        layout.menu_contents("UNITY_MT_lod_preset")
        context.area.tag_redraw()


class UNITY_PT_lod(Panel, Unity):
    bl_label = "Lod"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header_preset(self, context):
        UNITY_PT_lod_preset.draw_panel_header(self.layout)

    def draw(self, context):
        layout = self.layout

        unity = context.scene.unity

        col = self.draw_list(
            layout,
            "UNITY_UL_lod",
            dataptr=unity,
            propname="lods",
            active_propname="lod_index",
            rows=4 if len(unity.lods) > 1 else 3,
        )
        col.operator("unity.lod_add", text="", icon="ADD")

        if unity.lods:
            col = layout.column()
            col.scale_y = 1.2
            col.operator("unity.lod_create")


class UNITY_PT_export(Panel, Unity):
    bl_label = "Export"

    def draw_header_preset(self, context):
        layout = self.layout
        if bpy.app.version < (4, 2, 0):
            layout.operator("unity.fbx_settings", text="", icon="SETTINGS", emboss=False)

    def draw_unity_folder_list(self, layout, export):
        col = self.draw_list(
            layout,
            "UNITY_UL_unity_path",
            dataptr=export,
            propname="unity_folders",
            active_propname="unity_folder_index",
            tooltip="path",
            rows=4 if len(export.unity_folders) > 1 else 3,
        )
        col.operator("unity.folder_add", text="", icon="ADD").type = "UNITY"
        col.operator("unity.folder_load", text="", icon="FILE_REFRESH").type = "UNITY"

    def draw_disk_folder_list(self, layout, export):
        col = self.draw_list(
            layout,
            "UNITY_UL_disk_path",
            dataptr=export,
            propname="disk_folders",
            active_propname="disk_folder_index",
            tooltip="path",
            rows=4 if len(export.unity_folders) > 1 else 3,
        )
        col.operator("unity.folder_add", text="", icon="ADD").type = "DISK"
        col.operator("unity.folder_load", text="", icon="FILE_REFRESH").type = "DISK"

    def draw_progress(self, layout, export):
        layout.enabled = False
        layout.prop(export, "progress", text="Exporting...", slider=True)

    def draw(self, context):
        layout = self.layout

        export = context.scene.unity.export

        col = layout.column()
        col.prop(export, "type", text="")

        if export.type == "UNITY":
            self.draw_unity_folder_list(layout, export)
        elif export.type == "DISK":
            self.draw_disk_folder_list(layout, export)
        else:
            self.draw_unity_folder_list(layout, export)
            self.draw_disk_folder_list(layout, export)

        row = layout.row()
        row.prop(export, "selection_type", expand=True)

        col = layout.column(align=True)
        if export.selection_type == "COLLECTION":
            col.prop(export, "use_sub_collection")
        else:
            col.prop(export, "use_include")

        col.prop(export, "use_materials")
        subcol = col.column()
        subcol.enabled = export.use_materials
        subcol.prop(export, "use_baked_material")

        col = layout.column()
        col.prop(export, "shader_type", text="")

        col = layout.column()
        col.scale_y = 1.6
        if export.progress >= 0:
            self.draw_progress(col, export)
        else:
            col.operator("unity.export_fbx")
            # col.operator('unity.export_test')


class UNITY_PT_help(Panel, Unity):
    bl_label = "Help"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.2

        col = layout.column()
        col.operator("unity.changelog", icon="RECOVER_LAST")
        col.operator("wm.url_open", text="Documentation", icon="HELP").url = "https://b3dhub.github.io/blender-to-unity-docs/"
        col.operator("wm.url_open", text="Report a Bug", icon="URL").url = "https://discord.gg/sdnHHZpWbT"
        col.operator("wm.url_open", text="Blender Market", icon_value=icon["B_MARKET"]).url = "https://blendermarket.com/products/blender-to-unity"
        col.operator("wm.url_open", text="Gumroad", icon_value=icon["GUMROAD"]).url = "https://b3dhub.gumroad.com/l/blender-to-unity"


classes = (
    UNITY_PT_tool,
    UNITY_PT_collider,
    UNITY_PT_lod_preset,
    UNITY_PT_lod,
    UNITY_PT_export,
    UNITY_PT_help,
)


register, unregister = bpy.utils.register_classes_factory(classes)
