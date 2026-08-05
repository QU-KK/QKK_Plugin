# User Translate Addon (C) 2022-2024 Bookyakuno
# Created by Bookyakuno
# License : GNU General Public License version3 (http://www.gnu.org/licenses/)

bl_info = {
    "name": "User Translate",
    "author": "Bookyakuno",
    "version": (1, 0, 22),
    "blender": (4, 1, 0),
    "location": "Addon Preferences",
    "description": "",
    "warning": "",
    "category": "Preferences"
}


if "bpy" in locals():
    import importlib
    reloadable_modules = [
    "utils",
    "translation",
    "op_other",
    ]
    for module in reloadable_modules:
        if module in locals():
            importlib.reload(locals()[module])

import bpy
from .utils import *
from .utils import language_items_old, language_items_V400
from .translation import *
from .op_other import *
from .op_other import re_register_files


from bpy.props import *
from bpy.types import AddonPreferences


def update_auto_toggle(self,context):
    bpy.ops.usertranslate.auto_update_translation_file()


#
class USERTRANSLATE_MT_AddonPreferences(AddonPreferences):
    bl_idname = __name__

    tab_addon_menu : EnumProperty(name="Tab", description="", items=[('Option', "Option", "","DOT",0), ('Link', "Link", "","URL",2)], default='Option')
    ui_toggle_file_data : BoolProperty(name="File Data")
    ui_opened_files : StringProperty()
    update_translation_file_time : IntProperty(name="Update Interval",default=1,min=1)
    update_translation_file_active : BoolProperty(name="Auto Update File",update=update_auto_toggle)

    target_filename : StringProperty(name="File Name")
    clipboard_source : StringProperty(name="Source")
    clipboard_translate : StringProperty(name="Translated")
    # target_dirpath :  StringProperty(type='DIR_PATH')
    translated_text_file : StringProperty(name="Translated Text File",subtype="FILE_PATH")


    if bpy.app.version >= (4,0,0):
        language : EnumProperty(default="zh_HANS",name="Language",items= language_items_V400, update=re_register_files)
    else:
        language : EnumProperty(default="zh_HANS",name="Language",items= language_items_old, update=re_register_files)

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "tab_addon_menu",expand=True)

        layout.prop(context.preferences.view, "use_translate_interface",icon="FONTPREVIEW")

        layout.separator()
        layout.prop(self,"language")
        layout.separator()
        box = layout.box()
        col = box.column()
        row_main = col.row(align=True)
        col = row_main.column()
        col.scale_x = .3
        col.label(text="1.",icon="NONE")
        col.label(text="2.",icon="NONE")
        col.label(text="3.",icon="NONE")
        col = row_main.column()
        row = col.row(align=True)
        op = row.operator("usertranslate.file_extract_text",icon="FILE")
        op.is_dir = False
        op = row.operator("usertranslate.file_extract_text",text="Extract text from .py in a folder",icon="FILE_FOLDER")
        op.is_dir = True
        op = col.operator("usertranslate.paste_clipboard_to_tlanslate_text",icon="PASTEDOWN")
        op.type = "translate"
        # col.prop(self,"translated_text_file")
        box = col.box()
        box.operator("usertranslate.combine_src_and_tras_text",icon="EXPORT")
        box.prop(self,"target_filename")
        row = box.row(align=True)
        op = row.operator("usertranslate.paste_clipboard_to_tlanslate_text",text="",icon="PASTEDOWN")
        op.type = "source"
        row.prop(self,"clipboard_source")
        row.separator()

        op = row.operator("usertranslate.paste_clipboard_to_tlanslate_text",text="",icon="PASTEDOWN")
        op.type = "translate"
        row.prop(self,"clipboard_translate")

        layout.separator()


        # アップデーター
        box = layout.box()
        col = box.column()
        row = col.row(align=True)
        row.scale_y = 1.5
        row.prop(self,"update_translation_file_active",icon="FILE_REFRESH")
        row = col.row(align=True)
        row.use_property_split = True
        row.use_property_decorate = False
        row.prop(self,"update_translation_file_time")



        # ファイルデータ
        sp = layout.split(align=True,factor=0.7)
        row = sp.row(align=True)
        row.alignment="LEFT"
        row.prop(self,"ui_toggle_file_data",icon="TRIA_DOWN" if self.ui_toggle_file_data else "TRIA_RIGHT", emboss=False)
        row = sp.row(align=True)
        row.alignment="RIGHT"
        row.operator("usertranslate.open_folder",icon="FILE_FOLDER")
        if self.ui_toggle_file_data:
            list = get_csv_file_list()
            box = layout.box()
            col_main = box.column(align=True)

            for path in list:
                # if os.path.basename(path) in self.ui_opened_files.split(","):
                #     continue
                col_main.separator()
                col_main.label(text=os.path.basename(path),icon="DOT")
                with codecs.open(path, 'r', 'utf-8') as f:
                    reader = csv.reader(f)
                    for line in reader:
                        if not line or line[0] == "":
                            continue
                        try:
                            row = col_main.row(align=True)
                            row.label(text=line[1].replace('\\n', '\n'),icon="BLANK1")
                        except IndexError: pass






classes = (
USERTRANSLATE_OT_open_folder,
USERTRANSLATE_OT_file_extract_text,
USERTRANSLATE_OT_auto_update_translation_file,
USERTRANSLATE_OT_paste_clipboard_to_tlanslate_text,
USERTRANSLATE_OT_combine_src_and_tras_text,
USERTRANSLATE_MT_AddonPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # translation
    register_translation_dict()




def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    # translation
    unregister_translation_dict()


if __name__ == "__main__":
    register()
