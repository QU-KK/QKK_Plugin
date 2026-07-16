import bpy
from bpy.types import UIList


class UNITY_UL_lod(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "ratio", text=f"LOD{str(index + 1)}", slider=True, emboss=False)
        row.operator("unity.lod_remove", text="", icon="X", emboss=False).index = index


class UNITY_UL_unity_path(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if item.use_subfolder:
            row.label(text="", icon="BLANK1")
        row.prop(item, "name", text="", icon="FILE_FOLDER", emboss=False)
        operator = row.operator("unity.folder_remove", text="", icon="X", emboss=False)
        operator.type = "UNITY"
        operator.index = index


class UNITY_UL_disk_path(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if item.use_subfolder:
            row.label(text="", icon="BLANK1")
        row.prop(item, "name", text="", icon="FILE_FOLDER", emboss=False)
        operator = row.operator("unity.folder_remove", text="", icon="X", emboss=False)
        operator.type = "DISK"
        operator.index = index


classes = (
    UNITY_UL_lod,
    UNITY_UL_unity_path,
    UNITY_UL_disk_path,
)


register, unregister = bpy.utils.register_classes_factory(classes)
