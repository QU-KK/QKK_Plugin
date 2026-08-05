# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy

from ZenUV.utils.blender_zen_utils import ZenPolls


def normalize(string):
    """ Switch to lower case and replaces SPACES by '-' """
    return string.lower().replace(" ", "-")


# Lower Case Only !
zen_uv_manual_map = (

    # Adv UV Maps
    ('bpy.ops.wm.zuv_adv_maps_rename', 'adv_uv-maps/#rename-uv-maps'),
    ('bpy.ops.mesh.zuv_add_uvs*', 'adv_uv-maps/#duplicate-active-uv-map'),
    ('bpy.ops.mesh.zuv_remove_uvs', 'adv_uv-maps/#remove-active-uv-map'),
    ('bpy.ops.mesh.zuv_move_*', 'adv_uv-maps/#advanced-uv-maps-list'),
    ('bpy.ops.wm.zuv_advmaps_sync', 'adv_uv-maps/#sync-uv-maps'),
    ('bpy.ops.mesh.remove_inactive_uvs', 'adv_uv-maps/#clean-uv-maps'),
    ('bpy.ops.mesh.zenuv_set_uv_name_by_pos', 'adv_uv-maps/#set-uv-map-name-by-index'),
    ('bpy.types.ZUV_AdvMapsSceneProps.*'.lower(), 'adv_uv-maps/#advanced-uv-maps-list'),
    ('bpy.types.ZUV_AdvMapsProps.*'.lower(), 'adv_uv-maps/#uv-maps-status-detection'),
    ('bpy.types.ZUV_AdvMapsSceneProps.sync_seams'.lower(), 'adv-uv-maps/#sync-seams-by-uv-islands'),

    # UDIM
    ('bpy.ops.uv.zenuv_add_missed_udim', 'adv_uv-maps/#add-missed'),
    ('bpy.ops.uv.zenuv_set_active_udim', 'adv_uv-maps/#set-active'),
    ('bpy.ops.uv.zenuv_remove_active_udim_tile', 'adv_uv-maps/#remove-active'),
    # ('bpy.ops.uv.zenuv_select_in_tile', 'adv_uv-maps/#select-in-active'),
    ('bpy.ops.uv.zenuv_move_to_uv_area', 'transform/#move-to-uv-area'),
    ('bpy.ops.uv.zenuv_set_active_udim_mouseover', 'adv_uv-maps/#set-active-eyedropper'),

    # Copy UV / Paste UV Subsection
    ('bpy.ops.uv.zenuv_copy_uv', 'adv_uv-maps/#copy-uv-paste-uv'),
    ('bpy.ops.uv.zenuv_paste_uv', 'adv_uv-maps/#copy-uv-paste-uv'),

    # Unwrap Section
    ('bpy.ops.uv.zenuv_unwrap', 'unwrap/#zen-unwrap'),
    ('bpy.ops.uv.zenuv_unwrap_constraint', 'unwrap/#unwrap-constraint'),
    ('bpy.ops.uv.zenuv_unwrap_inplace', 'unwrap/#unwrap-inplace'),
    ('bpy.ops.uv.zenuv_auto_uv_unwrap', 'unwrap/#auto-unwrap'),
    
    # -- Mark Subsection
    ('bpy.ops.uv.zenuv_auto_mark', 'unwrap/#mark-by-angle'),
    ('bpy.ops.uv.zenuv_mark_seams', 'unwrap/#mark'),
    ('bpy.ops.uv.zenuv_unmark_all', normalize('unwrap/#Unmark All')),
    ('bpy.ops.uv.zenuv_unified_mark', 'unwrap/#conversion-system'),
    ('bpy.types.ZUV_Properties.sl_convert'.lower(), 'unwrap/#conversion-system'),
    ('bpy.ops.mesh.zenuv_mirror_seams', 'unwrap/#mirror-seams'),
    ('bpy.ops.view3d.zenuv_set_smooth_by_sharp', 'unwrap/#smooth-by-sharp-toggle'),
    # -- Conversion Subsection
    ('bpy.ops.uv.zenuv_seams_by_open_edges', 'unwrap/#seams-by-open-edges'),
    ('bpy.ops.uv.zenuv_seams_by_sharp', 'unwrap/#seams-by-sharp-edges'),
    ('bpy.ops.uv.zenuv_seams_by_uv_islands', normalize('unwrap/#Seams by UV Borders')),
    ('bpy.ops.uv.zenuv_sharp_by_seams', normalize('unwrap/#Sharp Edges by Seams')),
    ('bpy.ops.uv.zenuv_sharp_by_uv_islands', normalize('unwrap/#Sharp by UV Borders')),
    # -- Finished Subsection
    ('bpy.ops.uv.zenuv_islands_sorting', normalize('unwrap/#Sort Islands by Tags')),
    ('bpy.ops.uv.zenuv_tag_finished', normalize('unwrap/#Tag Finished')),
    ('bpy.ops.uv.zenuv_untag_finished', normalize('unwrap/#Tag Unfinished')),
    ('bpy.ops.uv.zenuv_select_finished', normalize('unwrap/#Select Finished')),
    ('bpy.ops.uv.zenuv_display_finished', normalize('unwrap/#Display Finished Toggle')),

    # Select Section
    ('bpy.ops.uv.zenuv_select_island', normalize('select/#select-islands')),
    ('bpy.ops.uv.zenuv_select_loop', normalize('select/#select-int-loop')),
    ('bpy.ops.uv.zenuv_select_uv_overlap', normalize('select/#select-overlapped')),
    ('bpy.ops.uv.zenuv_select_flipped', normalize('select/#select-flipped')),
    ('bpy.ops.mesh.zenuv_select_seams', normalize('select/#select-seam')),
    ('bpy.ops.mesh.zenuv_select_sharp', normalize('select/#select-sharp')),
    ('bpy.ops.uv.zenuv_select_uv_borders', normalize('select/#select-uv-borders')),
    ('bpy.ops.uv.zenuv_select_open_edges', normalize('select/#select-open-edges')),
    ('bpy.ops.uv.zenuv_select_similar', normalize('select/#select-similar')),
    ('bpy.ops.uv.zenuv_select_in_tile', normalize('select/#select-in-tile')),
    ('bpy.ops.uv.zenuv_select_half', normalize('select/#select-half')),
    ('bpy.ops.uv.zenuv_select_quaded_islands', normalize('select/#select-quaded-islands')),
    ('bpy.ops.uv.zenuv_select_holed_islands', 'select/#select-holed-islands'),
    ('bpy.ops.uv.zenuv_select_splits_edges', normalize('select/#select-cylinder-edges-splits')),
    ('bpy.ops.mesh.select_edge_by_condition', normalize('select/#select-edges-by-condition')),
    ('bpy.ops.uv.zenuv_select_edges_by_direction', normalize('select/#select-edges-by-direction')),
    ('bpy.ops.uv.zenuv_select_island_by_direction', normalize('select/#select-islands-by-direction')),
    ('bpy.ops.uv.zenuv_select_by_uv_area', normalize('select/#select-by-uv-area')),
    ('bpy.ops.uv.zenuv_grab_sel_area', normalize('select/#get-selected-area')),
    ('bpy.ops.uv.zenuv_select_faces_less_than_pixel', 'select/#select-faces-less-than-pixel'),
    ('bpy.ops.uv.zenuv_convert_sel_faces_to_sel_loops', normalize('select/#convert-face-to-loops')),
    ('bpy.ops.uv.zenuv_convert_sel_edges_to_sel_loops', normalize('select/#convert-edges-to-loops')),
    ('bpy.ops.uv.zenuv_select_linked_loops', normalize('select/#select-linked-loops')),
    ('bpy.ops.uv.zenuv_isolate_island', normalize('select/#isolate-islands-toggle')),
    ('bpy.ops.uv.zenuv_sync_select', 'select/#zen-sync'),
    ('bpy.ops.uv.zenuv_select_self_intersecting', 'select/#select-self-intersecting-faces'),
    ('bpy.ops.uv.zenuv_select_stretched_faces', 'select/#select-stretched-faces'),
    ('bpy.ops.mesh.zenuv_select_faces_by_normal', 'select/#select-faces-by-normal'),
    ('bpy.ops.uv.zenuv_filter_islands_by_property', 'select/#filter-islands-by-property'),


    # Pack Section
    ('bpy.ops.uv.zenuv_pack', normalize('pack/#Pack Islands')),
    ('bpy.ops.uv.zenuv_sync_to_uvp', normalize('pack/#TEMP_LINK')),
    ('bpy.ops.uv.zenuv_get_uv_coverage', normalize('pack/#UV Coverage')),
    ('bpy.ops.uv.zenuv_calculate_recommended_margin', normalize('pack/#calculate-recommended-margin')),

    # Checker Section
    ('bpy.ops.view3d.zenuv_checker_toggle', normalize('checker/#Checker Texture Toggle')),
    ('bpy.ops.view3d.zenuv_checker_remove', normalize('checker/#TEMP_LINK')),
    ('bpy.types.ZUV_Properties.tex_checker_interpolation'.lower(), normalize('checker/#1-interpolation')),
    ('bpy.types.ZUV_Properties.tex_checker_tiling'.lower(), 'checker/#2-checker-textures'),
    ('bpy.types.ZUV_Properties.tex_checker_offset'.lower(), 'checker/#2-checker-textures'),
    ('bpy.types.ZUV_PT_OSL_Display.stretch'.lower(), normalize('checker/#Display Stretch Map')),
    ('bpy.ops.uv.zenuv_select_stretched_islands', normalize('checker/#Display Stretch Map')),
    # -- Checker Props Subsection
    ('bpy.ops.ops.zenuv_checker_reset_path', normalize('checker/#Checker Texture Toggle')),
    ('bpy.ops.view3d.zenuv_check_library', normalize('checker/#Checker Texture Toggle')),
    ('bpy.ops.view3d.zenuv_checker_append_checker_file', normalize('checker/#Checker Texture Toggle')),
    ('bpy.ops.view3d.zenuv_checker_collect_images', normalize('checker/#Checker Texture Toggle')),
    ('bpy.ops.view3d.zenuv_checker_open_editor', normalize('checker/#Checker Texture Toggle')),
    ('bpy.ops.view3d.zenuv_checker_reset', normalize('checker/#Checker Texture Toggle')),
    # -- Checker tools section
    ('bpy.ops.object.zenuv_select_elements_by_index', 'checker/#elements-by-index'),
    # Select Zero Area Faces described in 'bpy.ops.uv.zenuv_select_by_uv_area' 'select/#select-by-uv-area'
    ('bpy.ops.object.zenuv_select_edges_without_faces', 'checker/#edges-without-faces'),
    ('bpy.ops.object.zenuv_select_edges_with_multiple_loops', 'checker/#edges-with-multiple-loops'),
    ('bpy.ops.uv.zenuv_island_counter', 'checker/#uv-islands-counter'),
    ('bpy.ops.object.zenuv_calc_uv_edges_length', 'checker/#calc-uv-edges-length'),
    ('bpy.ops.uv.zenuv_calculate_uv_pixel_size', 'checker/#calculate-uv-pixel-size'),
    ('bpy.ops.uv.zenuv_set_viewport_display_mode', 'checker/#set-viewport-display-mode'),

    # Prefs / System Section
    ('bpy.ops.ops.zenuv_show_prefs', normalize('preferences/#Preferences System')),
    ('bpy.ops.uv.zenuv_debug', '/#TEMP_LINK'),
    ('bpy.ops.uv.zenuv_unregister_library', normalize('installation/#Installation')),
    ('bpy.ops.uv.zenuv_update_addon', normalize('installation/#Installation')),
    ('bpy.ops.view3d.zenuv_install_library', normalize('installation/#Installation')),
    ('bpy.ops.zenuv.reset_preferences', normalize('preferences/#Preferences System')),

    # # -- Unused Operators Subsection
    # ('bpy.ops.zenuv.call_pie', '/#TEMP_LINK'),
    # ('bpy.ops.zenuv.call_popup', '/#TEMP_LINK'),
    # ('bpy.ops.zenuv.pie_caller', '/#TEMP_LINK'),
    # ('bpy.ops.uv.zenuv_show_sim_index', normalize('stack/#Stack')),

    # Seam Groups Section
    ('bpy.ops.uv.zenuv_activate_seam_group', normalize('seam_groups/#Seam Groups')),
    ('bpy.ops.uv.zenuv_assign_seam_to_group', normalize('seam_groups/#Seam Groups')),
    ('bpy.ops.zen_sg_list.delete_item', normalize('seam_groups/#Seam Groups')),
    ('bpy.ops.zen_sg_list.move_item', normalize('seam_groups/#Seam Groups')),
    ('bpy.ops.zen_sg_list.new_item', normalize('seam_groups/#Seam Groups')),

    # Texel Density Section
    ('bpy.ops.uv.zenuv_bake_td_to_vc', normalize('texel_density/#TD Checker')),
    # ('bpy.ops.uv.zenuv_get_image_size_uv_layout', 'texel_density/#TEMP_LINK'),
    ('bpy.ops.uv.zenuv_get_texel_density', normalize('texel_density/#Get TD')),
    ('bpy.ops.uv.zenuv_clear_baked_texel_density', normalize('texel_density/#TD Checker')),
    ('bpy.ops.uv.zenuv_set_texel_density', normalize('texel_density/#Set TD')),

    # -- Texel Density Presets Subsection
    # ('bpy.ops.uv.zenuv_bake_td_to_vc_preset', normalize('texel_density/#Show Presets')),
    ('bpy.ops.zen_tdpr.clear_presets', normalize('texel_density/#Clear')),
    ('bpy.ops.zen_tdpr.delete_item', normalize('texel_density/#Texel Density Presets')),
    ('bpy.ops.zen_tdpr.generate_presets', normalize('texel_density/#Generate')),
    ('bpy.ops.zen_tdpr.get_td_from_preset', normalize('texel_density/#Get')),
    ('bpy.ops.zen_tdpr.move_item', normalize('texel_density/#Texel Density Presets')),
    ('bpy.ops.zen_tdpr.new_item', normalize('texel_density/#Texel Density Presets')),
    ('bpy.ops.zen_tdpr.select_by_texel_density', normalize('texel_density/#Select by TD')),
    ('bpy.ops.zen_tdpr.set_td_from_preset', normalize('texel_density/#Set From Preset')),

    # Transform Section
    ('bpy.ops.uv.zenuv_relax', normalize('transform/#Relax')),
    ('bpy.ops.uv.zenuv_world_orient', normalize('transform/#World Orient')),
    ('bpy.ops.uv.zenuv_randomize_transform', normalize('transform/#Randomize')),
    ('bpy.ops.uv.zenuv_quadrify', normalize('transform/#Quadrify Islands')),
    ('bpy.ops.uv.zenuv_reshape_island', normalize('operators/reshape_island')),
    ('bpy.ops.uv.zenuv_match_stitch', normalize('transform/#match-and-stitch')),
    ('bpy.ops.uv.zenuv_split', normalize('transform/#split-uv')),
    ('bpy.ops.uv.zenuv_merge_uv_verts', normalize('transform/#merge-uv-verts')),
    ('bpy.ops.uv.zenuv_mirror_uv', normalize('transform/#mirror-uv')),

    # Universal Control Vidget
    ('bpy.ops.uv.zenuv_unified_transform', normalize('transform/#Universal Control Panel')),

    # Main selector
    ('bpy.types.ZUV_Properties.tr_pivot_mode'.lower(), normalize('transform/#order')),
    ('bpy.types.ZUV_Properties.tr_type'.lower(), normalize('transform/#Mode')),
    ('bpy.types.ZUV_Properties.tr_mode'.lower(), normalize('transform/#Transform Types')),

    # Move Section
    ('bpy.ops.uv.zenuv_grab_offset', normalize('transform/#move')),
    ('bpy.types.ZUV_Properties.tr_move_inc'.lower(), normalize('transform/#move')),
    ('bpy.ops.uv.zenuv_move_cursor_to', normalize('transform/#move-2d-cursor-to')),
    ('bpy.ops.uv.zenuv_move_to_uv_area_mouseover', normalize('transform/#move-to-uv-area-eyedropper')),
    ('bpy.ops.uv.zenuv_move_to_uv_position_mouseover', normalize('transform/#move-to-uv-position-eyedropper')),

    # Scale
    ('bpy.types.ZUV_Properties.tr_scale_mode'.lower(), normalize('transform/#scale-mode')),
    ('bpy.types.ZUV_Properties.tr_scale'.lower(), normalize('transform/#scale-mode')),
    ('bpy.types.ZUV_Properties.tr_scale_keep_proportion'.lower(), normalize('transform/#scale-mode')),
    ('bpy.types.ZUV_Properties.unts_uv_area_size'.lower(), normalize('transform/#scale-mode')),
    ('bpy.types.ZUV_Properties.unts_desired_size'.lower(), normalize('transform/#scale-mode')),
    ('bpy.types.ZUV_Properties.unts_calculate_by'.lower(), normalize('transform/#scale-mode')),

    # Rotate
    ('bpy.types.ZUV_Properties.tr_rot_inc'.lower(), normalize('transform/#rotate')),
    ('bpy.ops.uv.zenuv_orient_island'.lower(), normalize('transform/#orient-island')),
    ('bpy.ops.uv.zenuv_rotate'.lower(), normalize('transform/#rotate-island')),

    # Flip Section
    ('bpy.types.ZUV_Properties.tr_flip_always_center'.lower(), normalize('transform/#flip')),

    # Fill Section
    ('bpy.types.ZUV_Properties.tr_fit_per_face'.lower(), normalize('transform/#fit')),
    ('bpy.types.ZUV_Properties.tr_fit_padding'.lower(), normalize('transform/#fit')),
    ('bpy.types.ZUV_Properties.tr_fit_bound'.lower(), normalize('transform/#fit')),

    ('bpy.ops.uv.zenuv_fit_grab_region', normalize('transform/#Fit into Region')),
    ('bpy.ops.uv.zenuv_fit_region', normalize('transform/#Fit into Region')),
    ('bpy.ops.uv.zenuv_scale_grab_size', normalize('transform/#Fit into Region')),
    ('bpy.types.ZUV_Properties.tr_fit_region_tr'.lower(), normalize('transform/#Fit into Region')),
    ('bpy.ops.uv.zenuv_tr_scale_tuner', normalize('transform/#scale-mode')),
    ('bpy.types.ZUV_Properties.tr_fit_region_bl'.lower(), normalize('transform/#Fit into Region')),
    ('bpy.ops.uv.zenuv_fit_show_region', normalize('transform/#Fit into Region')),
    ('bpy.ops.uv.zenuv_fit_hide_region', normalize('transform/#Fit into Region')),

    # Align Section
    ('bpy.types.ZUV_Properties.tr_align_vertices'.lower(), normalize('transform/#align')),
    ('bpy.types.ZUV_Properties.tr_align_to'.lower(), normalize('transform/#align')),

    # Distribute Section
    ('bpy.ops.uv.zenuv_arrange_transform', normalize('transform/#arrange')),
    ('bpy.ops.uv.zenuv_distribute_islands', normalize('transform/#distribute-and-sort')),
    ('bpy.ops.uv.zenuv_distribute_verts', normalize('transform/#distribute-vertices')),

    # Advanced Transform
    ('bpy.ops.uv.zenuv_move', 'transform/#move-island'),
    ('bpy.ops.uv.zenuv_scale', 'transform/#scale-island'),
    ('bpy.ops.uv.zenuv_rotate', 'transform/#rotate-island'),
    ('bpy.ops.uv.zenuv_flip', 'transform/#flip-island'),
    ('bpy.ops.uv.zenuv_fit', 'transform/#fit-island'),
    ('bpy.ops.uv.zenuv_align', 'transform/#align-islands'),

    # Stack Section
    ('bpy.ops.uv.zenuv_stack_similar', 'stack/#stack-operator'),
    ('bpy.ops.uv.zenuv_unstack', 'stack/#unstack-operator'),
    ('bpy.ops.uv.zenuv_simple_stack', 'stack/#simple-stack-operator'),
    ('bpy.ops.uv.zenuv_simple_unstack', 'stack/#simple-unstack-operator'),
    ('bpy.ops.uv.zenuv_select_stack', 'stack/#stack-components'),
    ('bpy.ops.uv.zenuv_select_stacked', 'stack/#stacks-display-and-select'),

    # -- Copy/Paste Subsection
    ('bpy.ops.uv.zenuv_copy_param', normalize('operators/stack_copy_paste/#Copy')),
    ('bpy.ops.uv.zenuv_paste_param', normalize('operators/stack_copy_paste/#Paste')),

    # -- Manual Stack Subsection
    ('bpy.ops.uv.zenuv_assign_manual_stack', normalize('stack/#Add Islands')),
    ('bpy.ops.uv.zenuv_collect_manual_stacks', normalize('stack/#Stack_2')),
    ('bpy.ops.zen_stack_list.delete_item', normalize('stack/#Delete')),
    ('bpy.ops.zen_stack_list.new_item', normalize('stack/#Add')),
    ('bpy.ops.zen_stack_list.remove_all_m_stacks', normalize('stack/#Remove All')),
    ('bpy.ops.uv.zenuv_analyze_stack', normalize('stack/#Analyze Stack')),
    ('bpy.ops.uv.zenuv_unstack_manual_stack', 'stack/#unstack-all'),
    ('bpy.ops.uv.zenuv_select_m_stack', 'stack#select-islands'),

    # -- Excluded System
    ('bpy.ops.uv.zenuv_offset_pack_excluded', normalize('pack/#offset-excluded')),
    ('bpy.ops.uv.zenuv_tag_pack_excluded', normalize('pack/#tag-excluded')),
    ('bpy.ops.uv.zenuv_untag_pack_excluded', normalize('pack/#untag-excluded')),
    ('bpy.ops.uv.zenuv_hide_pack_excluded', normalize('pack/#hide')),
    ('bpy.ops.uv.zenuv_select_pack_excluded', normalize('pack/#select-excluded')),
    ('bpy.types.ZUV_PT_OSL_Display.p_excluded'.lower(), normalize('pack/#display-excluded')),

    # -- Trimsheet
    ('bpy.ops.uv.zuv_add_trimsheet_preset', 'trimsheet_creation/#add_1'),
    ('bpy.ops.wm.zenuv_open_presets_folder', 'trimsheet_creation/#open-presets-folder'),
    ('bpy.ops.wm.zuv_trim_preview', 'trimsheet_creation/#select-active-trim-with-preview-panel'),

    ('bpy.ops.uv.zenuv_new_trim', 'trimsheet_creation/#add'),
    ('bpy.ops.uv.zuv_trim_remove_ui', 'trimsheet_creation/#remove'),
    ('bpy.ops.uv.zuv_trim_delete_all', 'trimsheet_creation/#delete-all'),
    ('bpy.ops.uv.zuv_trim_duplicate', 'trimsheet_creation/#duplicate'),
    ('bpy.ops.uv.zuv_copy_trimsheet', 'trimsheet_creation/#copy-trims-to-clipboard'),
    ('bpy.ops.uv.zuv_paste_trimsheet', 'trimsheet_creation/#paste-trims-from-clipboard'),
    ('bpy.ops.wm.zuv_trim_batch_rename', 'trimsheet_creation/#batch-rename'),
    ('bpy.ops.uv.zuv_trim_create_grid', 'trimsheet_creation/#add-trim-grid'),
    ('bpy.ops.uv.zuv_trim_create_udim', 'trimsheet_creation/#add-trim-udim'),
    ('bpy.ops.wm.zuv_trim_create_from_zen_sets', 'trimsheet_creation/#add-trims-from-zen-sets'),
    ('bpy.ops.uv.zuv_set_trim_world_size', 'trimsheet_creation/#set-trim-world-size'),
    ('bpy.ops.uv.zuv_trim_frame', 'trimsheet_creation/#frame-trim'),
    ('bpy.ops.wm.zuv_trim_clear_preview_folder', 'trimsheet_creation/#clear-trimshet-preview-folder'),

    ('bpy.ops.*.zenuv_move_in_trim', 'trimsheet_operators/#move-in-trim'),
    ('bpy.ops.*.zenuv_fit_to_trim', 'trimsheet_operators/#fit-to-trim'),
    ('bpy.ops.*.zenuv_rotate_in_trim', 'trimsheet_operators/#rotate-in-trim'),
    ('bpy.ops.*.zenuv_align_to_trim', 'trimsheet_operators/#align-to-trim'),
    ('bpy.ops.*.zenuv_flip_in_trim', 'trimsheet_operators/#flip-in-trim'),
    ('bpy.ops.*.zenuv_scale_in_trim', 'trimsheet_operators/#scale-in-trim'),

    ('bpy.ops.uv.zenuv_fit_to_trim_hotspot', 'trimsheet_operators/#hotspot-mapping'),
    ('bpy.ops.uv.zenuv_directional_hotspot', 'trimsheet_operators/#directional-hotspot-operator'),
    ('bpy.ops.mesh.zenuv_set_face_normal_to_trim_props', 'trimsheet_operators/#normals-to-trim'),
    ('bpy.ops.uv.zenuv_trim_select_by_face', 'trimsheet_operators/#select-trim-by-face'),
    ('bpy.ops.uv.zenuv_select_island_by_trim', 'trimsheet_operators/#select-islands-by-trim'),

    ('bpy.ops.uv.zuv_crop_trim', 'trimsheet_creation/#crop-trims'),
    ('bpy.ops.uv.zuv_align_trim', 'trimsheet_creation/#align-trims'),
    ('bpy.ops.uv.zuv_adjust_size_trim', 'trimsheet_creation/#adjust-trims'),
    ('bpy.ops.uv.zuv_distribute_trim', 'trimsheet_creation/#distribute-trims'),

    ('bpy.ops.wm.zenuv_set_props_to_trims', 'trimsheet_creation/#how-to-apply-same-settings-to-multiple-trims'),

    ('bpy.types.ZUV_UVToolProps.display_trims'.lower(), 'trimsheet_creation/#display-trims'),
    ('bpy.types.ZUV_UVToolProps.select_trim'.lower(), 'trimsheet_creation/#select-trim-in-the-viewport'),
    ('bpy.types.ZuvTrimsheetTransformProps.trim_transform_mode'.lower(), 'trimsheet_creation/#transform-trims'),
    ('bpy.types.ZuvTrimsheetGroup.*'.lower(), 'trimsheet_creation/#trim-settings'),
    ('bpy.ops.wm.zuv_trim_create_from_image', 'trimsheet_creation/#add-trims-from-color-masks'),

)


def zen_uv_addon_docs():
    return ZenPolls.doc_url, zen_uv_manual_map


def register():
    bpy.utils.register_manual_map(zen_uv_addon_docs)


def unregister():
    bpy.utils.unregister_manual_map(zen_uv_addon_docs)
