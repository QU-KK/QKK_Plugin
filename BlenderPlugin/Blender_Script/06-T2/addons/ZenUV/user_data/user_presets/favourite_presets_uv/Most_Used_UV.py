import bpy
prefs = bpy.context.preferences.addons["ZenUV"].preferences.favourite_props_UV

prefs.favourites.clear()

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = False
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'EVENT_I'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'HEART'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'EVENT_Z'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'EVENT_E'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'EVENT_N'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'EVENT_U'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Item'
item_sub_1.category = ''
item_sub_1.display_text = True
item_sub_1.command = ''
item_sub_1.mode = 'LABEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'EVENT_V'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Zen Unwrap'
item_sub_1.category = 'Unwrap'
item_sub_1.display_text = True
item_sub_1.command = "uv.zenuv_unwrap(action='DEFAULT')"
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = True
item_sub_1.icon = 'zen-uv_32'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Unwrap Inplace'
item_sub_1.category = 'Unwrap'
item_sub_1.display_text = True
item_sub_1.command = "uv.zenuv_unwrap_inplace"
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Relax'
item_sub_1.category = 'Transform'
item_sub_1.display_text = True
item_sub_1.command = "uv.zenuv_relax"
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'OPEN'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = True
item_sub_1.icon = 'relax-1_32'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Quadrify'
item_sub_1.category = 'Transform'
item_sub_1.display_text = True
item_sub_1.command = "uv.zenuv_quadrify"
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = True
item_sub_1.icon = 'quadrify_32'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'World Orient'
item_sub_1.category = 'Transform'
item_sub_1.display_text = True
item_sub_1.command = "uv.zenuv_world_orient"
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Reshape Island'
item_sub_1.category = 'Transform'
item_sub_1.display_text = True
item_sub_1.command = 'uv.zenuv_reshape_island'
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Split'
item_sub_1.category = 'Transform'
item_sub_1.display_text = True
item_sub_1.command = 'uv.zenuv_split'
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Merge'
item_sub_1.category = 'Transform'
item_sub_1.display_text = True
item_sub_1.command = 'uv.zenuv_merge_uv_verts'
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Stack'
item_sub_1.category = 'Stack'
item_sub_1.display_text = False
item_sub_1.command = 'from ZenUV.stacks.stacks_ui import draw_stack_in_favourites; draw_stack_in_favourites(op_row)'
item_sub_1.mode = 'SCRIPT'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Select by TD'
item_sub_1.category = 'Texel Density'
item_sub_1.display_text = True
item_sub_1.command = "wm.zenuv_script_exec(script='bpy.ops.uv.zenuv_select_by_texel_density(\"INVOKE_DEFAULT\", True, selection_mode=\"TRESHOLD\",treshold=0.01,sel_underrated=False,sel_overrated=False,clear_selection=True,texel_density=bpy.context.scene.zen_uv.td_props.prp_current_td)',return_value='{\"PASS_THROUGH\"}',desc='Select islands by Texel Density')"
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'OPEN'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'RESTRICT_SELECT_OFF'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Current TD'
item_sub_1.category = 'Texel Density'
item_sub_1.display_text = False
item_sub_1.command = 'scene.zen_uv.td_props.prp_current_td'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'TD Unit'
item_sub_1.category = 'Texel Density'
item_sub_1.display_text = False
item_sub_1.command = 'scene.zen_uv.td_props.td_unit'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Texture Size'
item_sub_1.category = 'Texel Density'
item_sub_1.display_text = True
item_sub_1.command = 'scene.zen_uv.td_props.td_im_size_presets'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'TEXTURE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Get TD'
item_sub_1.category = 'Texel Density'
item_sub_1.display_text = True
item_sub_1.command = 'uv.zenuv_get_texel_density'
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Set TD'
item_sub_1.category = 'Texel Density'
item_sub_1.display_text = True
item_sub_1.command = "uv.zenuv_set_texel_density(global_mode=True)"
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Texel Density Mode'
item_sub_1.category = 'Texel Density'
item_sub_1.display_text = False
item_sub_1.command = 'scene.zen_uv.td_props.td_set_mode'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'COL'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Checker Texture'
item_sub_1.category = 'UV Checker'
item_sub_1.display_text = True
item_sub_1.command = 'view3d.zenuv_checker_toggle(action="TOGGLE")'
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'OPEN'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = True
item_sub_1.icon = 'checker_32'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'UV Checker'
item_sub_1.category = 'UV Checker'
item_sub_1.display_text = False
item_sub_1.command = 'preferences.addons["ZenUV"].preferences.uv_checker_props.SizesX'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'TEXTURE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'UV Checker Filter'
item_sub_1.category = 'UV Checker'
item_sub_1.display_text = False
item_sub_1.command = 'preferences.addons["ZenUV"].preferences.uv_checker_props.chk_rez_filter'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'FILTER'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'ZenCheckerImages'
item_sub_1.category = 'UV Checker'
item_sub_1.display_text = False
item_sub_1.command = 'preferences.addons["ZenUV"].preferences.uv_checker_props.ZenCheckerImages'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Display'
item_sub_1.category = 'UV Checker'
item_sub_1.display_text = True
item_sub_1.command = 'ZUV_PT_UVL_CheckDisplayPanel'
item_sub_1.mode = 'PANEL'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = ''

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Pack Islands'
item_sub_1.category = 'Pack'
item_sub_1.display_text = True
item_sub_1.command = 'uv.zenuv_pack(display_uv=True)'
item_sub_1.mode = 'OPERATOR'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'OPEN'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = True
item_sub_1.icon = 'pack'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Texture Size'
item_sub_1.category = 'Pack'
item_sub_1.display_text = True
item_sub_1.command = 'scene.zen_uv.td_props.td_im_size_presets'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = True
item_sub_1.is_icon_value = False
item_sub_1.icon = 'TEXTURE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Margin px'
item_sub_1.category = 'Pack'
item_sub_1.display_text = True
item_sub_1.command = 'preferences.addons["ZenUV"].preferences.margin_px'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Average Scale'
item_sub_1.category = 'Pack'
item_sub_1.display_text = True
item_sub_1.command = 'preferences.addons["ZenUV"].preferences.averageBeforePack'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'ROW'
item_sub_1.layout_group = 'CLOSE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

item_sub_1 = prefs.favourites.add()
item_sub_1.name = 'Rotate Islands'
item_sub_1.category = 'Pack'
item_sub_1.display_text = True
item_sub_1.command = 'preferences.addons["ZenUV"].preferences.rotateOnPack'
item_sub_1.mode = 'PROPERTY'
item_sub_1.layout = 'AUTO'
item_sub_1.layout_group = 'NONE'
item_sub_1.icon_only = False
item_sub_1.is_icon_value = False
item_sub_1.icon = 'NONE'

prefs.favourite_index = 29
prefs.expanded = "{'UV': False, 'Pack': True, 'UV Checker': True, 'Texel Density': True, 'Stack': True, 'Transform': True, 'Unwrap': True}"
prefs.show_header = True
prefs.header_expanded = True
