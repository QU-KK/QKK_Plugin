import bpy

from .documentation import WM_OT_open_unity_material_sync_docs
from .operators import MATERIAL_OT_sync_from_unity


def draw_unity_material_sync_header(self, context):
    layout = self.layout
    row = layout.row(align=True)
    row.operator(
        MATERIAL_OT_sync_from_unity.bl_idname,
        text="同步材质",
        icon="MATERIAL",
    )
    row.operator(
        WM_OT_open_unity_material_sync_docs.bl_idname,
        text="",
        icon="HELP",
    )


def register():
    bpy.types.VIEW3D_HT_header.append(draw_unity_material_sync_header)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_unity_material_sync_header)
