import bpy
def label(chinese, english):
    prefs=bpy.context.preferences.view
    return chinese if prefs.use_translate_interface and prefs.language.startswith('zh') else english
