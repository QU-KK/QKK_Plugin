from ..G import *
"""Reusable UI foldouts and generation/shape/UV/material/finish/normal sections.
Loaded into the add-on package shared namespace by __init__.py.
"""
def draw_edge_decal_foldout(layout,owner,property_name,label,icon=None,prominent=False,):
	expanded=bool(getattr(owner,property_name))
	row=layout.row(align=True)
	row.scale_y=1.2 if prominent else 1.05
	if icon:
		icon_cell=row.row(align=True)
		icon_cell.scale_x=0.7
		icon_cell.label(text="",icon=icon)
	GP(row,owner,property_name,text=(label if expanded or not prominent else f"Show {label}"),icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",emboss=prominent,)
	return expanded
def draw_generation_actions(layout,context,settings):
	box=layout.box()
	GL(box,"Generate",icon="OUTLINER_OB_MESH")
	body=box.column(align=True)
	if context.mode== "EDIT_MESH":
		face_select_mode=bool(context.tool_settings.mesh_select_mode[2])
		GL(body,("Face selection: wrapped bevel decals" if face_select_mode else "Edge selection: sharp edge paths"),icon="FACESEL" if face_select_mode else "EDGESEL",)
		button=body.column()
		button.scale_y=1.45
		GO(button,EDGEDECAL_OT_generate_contextual.bl_idname,text="Generate From Selection",icon="PLAY",)
		interactive=body.column()
		interactive.scale_y=1.2
		GO(interactive,EDGEDECAL_OT_interactive_generate.bl_idname,text="Interactive Generate",icon="RESTRICT_SELECT_OFF",depress=EDGEDECAL_INTERACTIVE_RUNNING,)
	else:
		GP(body,settings, "auto_edge_angle")
		GP(body,settings, "auto_follow_edge_loops")
		button=body.column()
		button.scale_y=1.45
		GO(button,EDGEDECAL_OT_generate_contextual.bl_idname,text="Generate Automatically",icon="SHARPCURVE",)
		boolean_actions=body.row(align=True)
		boolean_actions.scale_y=1.2
		GO(boolean_actions,EDGEDECAL_OT_generate_intersections.bl_idname,text="Generate Intersections",icon="MOD_BOOLEAN",)
		GO(boolean_actions,EDGEDECAL_OT_generate_boolean.bl_idname,text="Generate From Booleans",icon="SELECT_INTERSECT",)
		interactive=body.column()
		interactive.scale_y=1.2
		GO(interactive,EDGEDECAL_OT_interactive_generate.bl_idname,text="Interactive Generate",icon="RESTRICT_SELECT_OFF",depress=EDGEDECAL_INTERACTIVE_RUNNING,)
def draw_shape_settings(layout,settings):
	box=layout.box()
	if not draw_edge_decal_foldout(box,settings,"show_geometry_settings","Geometry",
		icon="MESH_DATA",):
		return
	body=box.column(align=True)
	GP(body,settings, "surface_offset")
	GP(body,settings, "maximum_decal_length",text="Maximum Decal Length")
	GP(body,settings, "auto_trim_corner_ends")
	corner_trim=body.row()
	corner_trim.enabled=settings.auto_trim_corner_ends
	GP(corner_trim,settings, "corner_end_trim_multiplier")
	body.separator()
	GL(body,"Filtering & Width Control",icon="FILTER")
	advanced=body.column(align=True)
	GP(advanced,settings, "use_face_loop_slide")
	GP(advanced,settings, "use_edge_split")
	split_row=advanced.row()
	split_row.enabled=settings.use_edge_split
	GP(split_row,settings, "split_angle")
	advanced.separator()
	GP(advanced,settings, "remove_short_edges")
	minimum_row=advanced.row()
	minimum_row.enabled=settings.remove_short_edges
	GP(minimum_row,settings, "minimum_edge_length")
	advanced.separator()
	GP(advanced,settings, "auto_face_width")
	GP(advanced,settings, "clamp_edge_overlaps")
	samples=advanced.row()
	samples.enabled=(settings.auto_face_width or settings.clamp_edge_overlaps)
	GP(samples,settings, "auto_width_samples")
	clearance=advanced.row()
	clearance.enabled=settings.auto_face_width
	GP(clearance,settings, "auto_width_clearance")
	overlap=advanced.row()
	overlap.enabled=settings.clamp_edge_overlaps
	GP(overlap,settings, "overlap_clearance")
def draw_uv_settings(layout,settings):
	box=layout.box()
	if not draw_edge_decal_foldout(box,settings,"show_uv_settings","More UV Settings",
		icon="UV",):
		return
	body=box.column(align=True)
	GP(body,settings, "auto_unwrap_uvs")
	source_projection_required=bool(getattr(settings, "match_source_material",False))
	if not source_projection_required:
		second_uv=body.row()
		second_uv.enabled=settings.auto_unwrap_uvs
		GP(second_uv,settings,"generate_second_uv",text="Conformal Second UV",)
	advanced=body.column(align=True)
	GP(advanced,settings, "use_integrated_quadrify")
	quadrify=advanced.column(align=True)
	quadrify.enabled=(settings.auto_unwrap_uvs and settings.use_integrated_quadrify)
	GP(quadrify,settings, "integrated_quadrify_average_shape")
	GP(quadrify,settings, "integrated_quadrify_even_shape")
	GP(advanced,settings, "set_target_texel_density")
	density=advanced.column(align=True)
	density.enabled=(settings.auto_unwrap_uvs
		and (settings.set_target_texel_density
			or (settings.generate_second_uv and not source_projection_required)))
	GP(density,settings, "target_texel_density")
	GP(density,settings, "texture_resolution")
	GP(advanced,settings, "average_uv_island_scale")
	GP(advanced,settings, "align_uvs_horizontally")
	GP(advanced,settings, "place_in_quarter_strips")
	strips=advanced.column(align=True)
	strips.enabled=(settings.auto_unwrap_uvs and settings.place_in_quarter_strips)
	GP(strips,settings, "randomize_quarter_strip")
	GP(strips,settings, "randomize_horizontal_offset")
	amount_row=strips.row()
	amount_row.enabled=settings.randomize_horizontal_offset
	GP(amount_row,settings, "horizontal_randomize_amount")
	GP(strips,settings, "uv_strip_padding")
def draw_finish_settings(layout,settings):
	box=layout.box()
	if not draw_edge_decal_foldout(box,settings,"show_options_settings","Modifiers",
		icon="MODIFIER",):
		return
	body=box.column(align=True)
	GP(body,settings, "replace_previous")
	body.separator()
	weld=body.box()
	GP(weld,settings, "add_weld_modifier")
	if settings.add_weld_modifier:
		GP(weld,settings, "weld_distance")
	shrinkwrap=body.box()
	GP(shrinkwrap,settings, "add_shrinkwrap_modifier")
	if settings.add_shrinkwrap_modifier:
		GP(shrinkwrap,settings,"surface_offset",text="Shrinkwrap Offset",)
	center_displace=body.box()
	GP(center_displace,settings, "add_center_displace_modifier")
	if settings.add_center_displace_modifier:
		GP(center_displace,settings, "center_displace_strength")
	bevel=body.box()
	GP(bevel,settings, "add_bevel_modifier")
	if settings.add_bevel_modifier:
		bevel_settings=bevel.column(align=True)
		GP(bevel_settings,settings, "bevel_edge_center")
		if settings.bevel_edge_center:
			GL(bevel_settings,"Vertex Group: EdgeDecal_Center",icon="GROUP_VERTEX",)
		source_obj=edge_decal_context_source(bpy.context)
		source_bevel=last_source_bevel_modifier(source_obj)
		if source_bevel is not None:
			linked=bevel_settings.row()
			GL(linked,f"Linked to: {source_bevel.name}",icon="LINKED",)
			display=bevel_settings.column(align=True)
			display.enabled=False
			GP(display,settings, "center_bevel_width")
			GP(display,settings, "center_bevel_segments")
			GP(display,settings, "center_bevel_profile")
			if not settings.bevel_edge_center:
				GP(display,settings, "bevel_angle")
		else:
			warning=bevel_settings.row()
			GL(warning,"Using custom bevel settings",icon="MOD_BEVEL")
			GP(bevel_settings,settings, "center_bevel_width")
			GP(bevel_settings,settings, "center_bevel_segments")
			GP(bevel_settings,settings, "center_bevel_profile")
			if not settings.bevel_edge_center:
				GP(bevel_settings,settings, "bevel_angle")
	subdivision=body.box()
	GP(subdivision,settings, "add_subdivision_modifier")
	decimate=body.box()
	GP(decimate,settings, "add_decimate_modifier")
def draw_normals_settings(layout,settings):
	box=layout.box()
	if not draw_edge_decal_foldout(box,settings,"show_normals_settings","Normals",
		icon="NORMALS_FACE",):
		return
	body=box.column(align=True)
	GP(body,settings, "normal_mode")
	harden=body.row()
	harden.enabled=settings.add_bevel_modifier
	GP(harden,settings, "bevel_harden_normals")
	normals=body.column(align=True)
	normals.enabled=settings.normal_mode != "SHADE_SMOOTH"
	GP(normals,settings, "normal_keep_sharp")
	weight=normals.row()
	weight.enabled=settings.normal_mode== "WEIGHTED"
	GP(weight,settings, "normal_weight")
	GP(normals,settings, "normal_threshold")
