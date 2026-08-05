import bpy
prefs = bpy.context.preferences.addons["ZenUV"].preferences.favourite_props_VIEW_3D

prefs.favourites.clear()

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'UV Mapping'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = 'VIEW3D_MT_uv_map'
item_sub_1.mode = 'PANEL'
item_sub_1.layout = 'COL'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

prefs.favourite_index = 0
prefs.expanded = ''
prefs.show_header = True
prefs.header_expanded = True
