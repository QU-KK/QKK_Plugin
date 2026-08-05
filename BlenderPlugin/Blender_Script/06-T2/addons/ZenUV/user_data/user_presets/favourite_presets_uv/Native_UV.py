import bpy
prefs = bpy.context.preferences.addons["ZenUV"].preferences.favourite_props_UV

prefs.favourites.clear()

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'UV'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = 'IMAGE_MT_uvs'
item_sub_1.mode = 'PANEL'
item_sub_1.layout = 'COL'
item_sub_1.layout_group = 'CLOSE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

prefs.favourite_index = 0
prefs.expanded = "{'UV': False}"
prefs.show_header = True
prefs.header_expanded = True
