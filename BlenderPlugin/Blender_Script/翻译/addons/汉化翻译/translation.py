import bpy
import glob
import os, csv, codecs #辞書
from .utils import *

def get_csv_file_list():
    list = glob.glob(os.path.join(os.path.dirname(__file__), "user_files","*.csv"))
    return list

dist_name_l = []
# 翻訳辞書の登録
def register_translation_dict():
    prefs = preference()
    list = get_csv_file_list()
    global  dist_name_l

    for path in list:
        dict = {}

        with codecs.open(path, 'r', 'utf-8') as f:
            reader = csv.reader(f)
            dict[prefs.language] = {}
            for row in reader:
                if not row or row[0] == "":
                    continue
                for context in bpy.app.translations.contexts:
                    try:
                        dict[prefs.language][(context, row[1].replace('\\n', '\n'))] = row[0].replace('\\n', '\n')
                    except IndexError: pass



        try:
            dist_name = __name__ + os.path.basename(path)
            bpy.app.translations.register(dist_name, dict)
            dist_name_l += [dist_name]

        except Exception as e: print(e)


#
def unregister_translation_dict():
    global  dist_name_l
    for dist_name in dist_name_l:
        try:
            bpy.app.translations.unregister(dist_name)
            del dist_name
        except: pass


#
def re_register_files(self,context):
    unregister_translation_dict()
    register_translation_dict()
    for a in bpy.context.screen.areas:
        a.tag_redraw()
