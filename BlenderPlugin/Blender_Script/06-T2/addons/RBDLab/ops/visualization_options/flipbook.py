import bpy
import os
import time
from bpy.types import Operator
# from bpy.props import StringProperty
from ...addon.paths import RBDLabPreferences


class RBDLAB_OT_flipbook(Operator):
    bl_idname = "rbdlab.flipbook"
    bl_label = "Flipbook Render"
    bl_description = "Make a Flipbook Preview"
    bl_options = {'REGISTER', 'UNDO'}

    # previous_path: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)
        return addon_preferences.flipbooks_path is not None

    def execute(self, context):
        addon_preferences = RBDLabPreferences.get_prefs(context)

        use_flipbooks_in_subfolders = addon_preferences.use_flipbooks_in_subfolders
        use_flipbooks_in_subfolders_only_videos = addon_preferences.use_flipbooks_in_subfolders_only_videos
        flipbooks_path = addon_preferences.flipbooks_path
        flipbook_without_overlays = addon_preferences.flipbook_without_overlays

        # self.previous_path = context.scene.render.filepath
        blend_file = os.path.split(bpy.data.filepath)[-1].split(".")[0]

        # print(blend_file)

        if len(flipbooks_path) == 0:
            self.report({'WARNING'}, "First indicates the Flipbook Path!")
            return {'CANCELLED'}

        if not blend_file:
            blend_file = "UnsavedScene" + "_" + time.strftime("%dd_%Hh_%Mm_%Ss")
            # self.report({'WARNING'}, "Save the scene first!")
            # return {'CANCELLED'}

        if use_flipbooks_in_subfolders_only_videos:
            video_formats = ['AVI_JPEG', 'AVI_RAW', 'FFMPEG']
            if context.scene.render.image_settings.file_format in video_formats:
                final_path = os.path.join(flipbooks_path, blend_file+"_")
            else:
                final_path = os.path.join(flipbooks_path, blend_file, blend_file+"_")
        else:
            if use_flipbooks_in_subfolders:
                final_path = os.path.join(flipbooks_path, blend_file, blend_file+"_")
            else:
                final_path = os.path.join(flipbooks_path, blend_file+"_")

        # print(final_path)
        if final_path and final_path:
            context.scene.render.filepath = final_path

            if flipbook_without_overlays:
                context.space_data.overlay.show_overlays = False

            bpy.ops.render.opengl('INVOKE_DEFAULT', animation=True)
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, "Is necesary set in addon preferences the flipbook path and save scene!")
            return {'CANCELLED'}
