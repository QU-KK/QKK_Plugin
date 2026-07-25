import bpy
from bpy.types import Menu


class UNITY_MT_lod_preset(Menu):
    """LODs Presets"""

    bl_label = "Presets"
    preset_operator = "script.execute_preset"
    preset_subdir = "Unity/lod"
    preset_add_operator = "unity.lod_preset_add"
    preset_operator_defaults = {"menu_idname": "UNITY_MT_lod_preset"}

    def draw(self, context):
        self.draw_preset(context)


classes = (UNITY_MT_lod_preset,)

register, unregister = bpy.utils.register_classes_factory(classes)
