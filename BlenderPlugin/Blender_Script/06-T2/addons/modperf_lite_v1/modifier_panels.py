# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Modifier settings panels, ported from Blender's MOD_*.cc panel code."""

from .state import HUD
from .ui_layout import _UICtx, _UL


def _build_blender_body(b, m, mod, context):
    """Draw a modifier's settings with Blender's own panel layout.
    Returns False when no port exists (caller falls back to the generic list)."""
    fn = _MOD_PANELS.get(mod.type)
    if fn is None:
        return False
    ctx = _UICtx(b, m, mod, mod.id_data, context)
    ctx.search_getters = HUD.search_getters
    ctx.lay_red = lambda c: c.lay.eff_red()
    root = _UL(ctx, None)
    fn(root, mod, mod.id_data, context)
    root.ctx_flush()
    return True


# ---- per-modifier panels (ported from Blender 5.2.2 MOD_*.cc panel_draw) -------

def _armature_data_of(obj):
    return obj.data if (obj is not None and obj.type == 'ARMATURE') else None


def _P_physics(L, md, ob, C, what="Physics"):
    L.label(f"Settings are inside the {what} tab")


def _P_ARMATURE(L, md, ob, C):
    L.split = True
    L.prop("object")
    L.vgroup()
    col = L.column(True)
    col.prop("use_deform_preserve_volume")
    col.prop("use_multi_modifier")
    col = L.column(True, "Bind To")
    col.prop("use_vertex_groups", text="Vertex Groups")
    col.prop("use_bone_envelopes", text="Bone Envelopes")


def _P_ARRAY(L, md, ob, C):
    L.split = True
    L.prop("fit_type")
    if md.fit_type == 'FIXED_COUNT':
        L.prop("count")
    elif md.fit_type == 'FIT_LENGTH':
        L.prop("fit_length")
    elif md.fit_type == 'FIT_CURVE':
        L.prop("curve")
    p = L.panel("relative_offset", "", header="use_relative_offset")
    if p:
        p.split = True
        col = p.column()
        col.active = md.use_relative_offset
        col.prop("relative_offset_displace", text="Factor")
    p = L.panel("constant_offset", "", header="use_constant_offset")
    if p:
        p.split = True
        col = p.column()
        col.active = md.use_constant_offset
        col.prop("constant_offset_displace", text="Distance")
    p = L.panel("object_offset", "", header="use_object_offset")
    if p:
        p.split = True
        col = p.column()
        col.active = md.use_object_offset
        col.prop("offset_object", text="Object")
    p = L.panel("merge", "", header="use_merge_vertices", header_text="Merge")
    if p:
        p.split = True
        col = p.column()
        col.active = md.use_merge_vertices
        col.prop("merge_threshold", text="Distance")
        col.prop("use_merge_vertices_cap", text="First and Last Copies")
    p = L.panel("uv", "UVs")
    if p:
        p.split = True
        col = p.column(True)
        col.prop("offset_u", text="Offset U", expand=True)
        col.prop("offset_v", text="V", expand=True)
    p = L.panel("caps", "Caps")
    if p:
        p.split = True
        col = p.column()
        col.prop("start_cap", text="Cap Start")
        col.prop("end_cap", text="End")


def _P_BEVEL(L, md, ob, C):
    edge = md.affect != 'VERTICES'
    L.prop("affect", expand=True)
    L.split = True
    col = L.column()
    col.prop("offset_type")
    if md.offset_type == 'PERCENT':
        col.prop("width_pct")
    else:
        col.prop("width", text="Amount")
    L.prop("segments")
    L.separator()
    col = L.column()
    col.prop("limit_method")
    if md.limit_method == 'ANGLE':
        sub = col.column()
        sub.active = edge
        sub.prop("angle_limit")
    elif md.limit_method == 'WEIGHT':
        col.prop("edge_weight" if edge else "vertex_weight")
    elif md.limit_method == 'VGROUP':
        col.vgroup()
    p = L.panel("profile", "Profile")
    if p:
        p.prop("profile_type", expand=True)
        p.split = True
        if md.profile_type in {'SUPERELLIPSE', 'CUSTOM'}:
            row = p.row(False)
            row.active = (md.profile_type == 'SUPERELLIPSE' or
                          (md.profile_type == 'CUSTOM' and edge and
                           not (md.miter_inner == 'MITER_SHARP' and
                                md.miter_outer == 'MITER_SHARP')))
            row.prop("profile", slider=True,
                     text="Shape" if md.profile_type == 'SUPERELLIPSE' else "Miter Shape")
            if md.profile_type == 'CUSTOM':
                p.template('curve_profile', "custom_profile")
    p = L.panel("geometry", "Geometry")
    if p:
        p.split = True
        row = p.row(False)
        row.active = edge
        row.prop("miter_outer", text="Miter Outer")
        row = p.row(False)
        row.active = edge
        row.prop("miter_inner", text="Inner")
        if md.miter_inner == 'MITER_ARC':
            row = p.row(False)
            row.active = edge
            row.prop("spread")
        p.separator()
        row = p.row(False)
        row.active = edge
        row.prop("vmesh_method", text="Intersections")
        p.prop("use_clamp_overlap")
        row = p.row(False)
        row.active = edge
        row.prop("loop_slide")
    p = L.panel("shading", "Shading")
    if p:
        p.split = True
        p.prop("harden_normals")
        col = p.column(True, "Mark")
        col.active = edge
        col.prop("mark_seam", text="Seam")
        col.prop("mark_sharp", text="Sharp")
        p.prop("material")
        p.prop("face_strength_mode")


def _P_BOOLEAN(L, md, ob, C):
    L.prop("operation", expand=True)
    L.split = True
    L.prop("operand_type")
    if md.operand_type == 'OBJECT':
        L.prop("object")
    else:
        L.prop("collection")
    L.prop("solver", expand=True)
    p = L.panel("solver_options", "Solver Options")
    if p:
        p.split = True
        col = p.column(True)
        if md.solver == 'EXACT':
            col.prop("material_mode", text="Materials")
            if md.operand_type == 'OBJECT':
                col.prop("use_self")
            col.prop("use_hole_tolerant")
        elif md.solver == 'MANIFOLD':
            col.prop("material_mode", text="Materials")
        else:
            col.prop("double_threshold")


def _P_BUILD(L, md, ob, C):
    L.split = True
    L.prop("frame_start")
    L.prop("frame_duration")
    L.prop("use_reverse")
    p = L.panel("randomize", "", header="use_random_order")
    if p:
        p.split = True
        p.active = md.use_random_order
        p.prop("seed")


def _P_CAST(L, md, ob, C):
    L.split = True
    L.prop("cast_type")
    row = L.row(True, "Axis")
    row.prop("use_x", toggle=True)
    row.prop("use_y", toggle=True)
    row.prop("use_z", toggle=True)
    L.prop("factor")
    L.prop("radius")
    L.prop("size")
    L.prop("use_radius_as_size")
    L.vgroup()
    L.prop("object")
    if md.object is not None:
        L.prop("use_transform")


def _P_CORRECTIVE_SMOOTH(L, md, ob, C):
    L.split = True
    L.prop("factor", text="Factor")
    L.prop("iterations")
    L.prop("scale")
    L.prop("smooth_type")
    L.vgroup()
    L.prop("use_only_smooth")
    L.prop("use_pin_boundary")
    L.prop("rest_source")
    if md.rest_source == 'BIND':
        L.op("object.correctivesmooth_bind", "Unbind" if md.is_bind else "Bind")


def _P_CURVE(L, md, ob, C):
    L.split = True
    L.prop("object", text="Curve Object")
    L.prop("deform_axis")
    L.vgroup()


def _P_DATA_TRANSFER(L, md, ob, C):
    L.split = True
    row = L.row(True)
    row.prop("object", text="Source")
    sub = row.row(True)
    sub.prop("use_object_transform", text="", icon='orientation_global')
    L.prop("mix_mode")
    row = L.row(False)
    row.active = md.mix_mode not in {'ABOVE_THRESHOLD', 'BELOW_THRESHOLD'}
    row.prop("mix_factor")
    L.vgroup()
    L.op("object.datalayout_transfer", "Generate Data Layers")
    # Vertex Data
    p = L.panel("vertex", "", header="use_vert_data")
    if p:
        p.active = md.use_vert_data
        p.prop("data_types_verts", expand=True)
        p.split = True
        p.prop("vert_mapping", text="Mapping")
        q = p.panel("vertex_vgroup", "Vertex Groups")
        if q:
            q.active = 'VGROUP_WEIGHTS' in md.data_types_verts
            q.split = True
            q.prop("layers_vgroup_select_src", text="Layer Selection")
            q.prop("layers_vgroup_select_dst", text="Layer Mapping")
        q = p.panel("vert_vcol", "Colors")
        if q:
            q.split = True
            q.active = 'COLOR_VERTEX' in md.data_types_verts
            q.prop("layers_vcol_vert_select_src", text="Layer Selection")
            q.prop("layers_vcol_vert_select_dst", text="Layer Mapping")
    p = L.panel("edge", "", header="use_edge_data")
    if p:
        p.active = md.use_edge_data
        p.prop("data_types_edges", expand=True)
        p.split = True
        p.prop("edge_mapping", text="Mapping")
    p = L.panel("face_corner", "", header="use_loop_data")
    if p:
        p.active = md.use_loop_data
        p.prop("data_types_loops", expand=True)
        p.split = True
        p.prop("loop_mapping", text="Mapping")
        q = p.panel("face_corner_vcol", "Colors")
        if q:
            q.split = True
            q.active = 'COLOR_CORNER' in md.data_types_loops
            q.prop("layers_vcol_loop_select_src", text="Layer Selection")
            q.prop("layers_vcol_loop_select_dst", text="Layer Mapping")
        q = p.panel("face_corner_uv", "UVs")
        if q:
            q.split = True
            q.active = 'UV' in md.data_types_loops
            q.prop("layers_uv_select_src", text="Layer Selection")
            q.prop("layers_uv_select_dst", text="Layer Mapping")
            q.prop("islands_precision")
    p = L.panel("face", "", header="use_poly_data")
    if p:
        p.active = md.use_poly_data
        p.prop("data_types_polys")
        p.split = True
        p.prop("poly_mapping", text="Mapping")
    p = L.panel("advanced", "Topology Mapping")
    if p:
        p.split = True
        row = p.row(True, "Max Distance")
        row.prop("use_max_distance", text="")
        sub = row.row(True)
        sub.active = md.use_max_distance
        sub.prop("max_distance", text="")
        p.prop("ray_radius")


def _P_DECIMATE(L, md, ob, C):
    L.prop("decimate_type", expand=True)
    L.split = True
    if md.decimate_type == 'COLLAPSE':
        L.prop("ratio", slider=True)
        row = L.row(True, "Symmetry")
        sub = row.row(True)
        sub.prop("use_symmetry", text="")
        sub = sub.row(True)
        sub.active = md.use_symmetry
        sub.prop("symmetry_axis", expand=True)
        L.prop("use_collapse_triangulate")
        L.vgroup()
        sub = L.row(True)
        sub.active = bool(md.vertex_group)
        sub.prop("vertex_group_factor")
    elif md.decimate_type == 'UNSUBDIV':
        L.prop("iterations")
    else:
        L.prop("angle_limit")
        col = L.column()
        col.prop("delimit")
        L.prop("use_dissolve_boundaries")
    L.label(f"Face Count: {md.face_count:,}")


def _texture_coords_ui(col, md, ob, coords_attr="texture_coords",
                       obj_attr="texture_coords_object", bone_attr="texture_coords_bone",
                       uv_attr="uv_layer"):
    col.prop(coords_attr, text="Coordinates")
    tc = getattr(md, coords_attr)
    if tc == 'OBJECT':
        col.prop(obj_attr, text="Object")
        tob = getattr(md, obj_attr)
        if tob is not None and tob.type == 'ARMATURE':
            col.search(bone_attr, lambda md_, ob_, a=obj_attr: getattr(md_, a).data, "bones",
                       text="Bone")
    elif tc == 'UV' and ob.type == 'MESH':
        col.prop(uv_attr, icon='group_uvs')


def _P_DISPLACE(L, md, ob, C):
    L.split = True
    L.template('texture', "texture", text="Texture")
    col = L.column()
    col.active = md.texture is not None
    _texture_coords_ui(col, md, ob)
    L.separator()
    col = L.column()
    col.prop("direction")
    if md.direction in {'X', 'Y', 'Z', 'RGB_TO_XYZ'}:
        col.prop("space")
    L.separator()
    col = L.column()
    col.prop("strength")
    col.prop("mid_level")
    col.vgroup()


def _P_EDGE_SPLIT(L, md, ob, C):
    L.split = True
    row = L.row(True, "Edge Angle")
    row.prop("use_edge_angle", text="")
    sub = row.row(True)
    sub.active = md.use_edge_angle
    sub.prop("split_angle", text="")
    L.prop("use_edge_sharp", text="Sharp Edges")


def _P_EXPLODE(L, md, ob, C):
    L.split = True
    L.prop("particle_uv", icon='group_uvs')
    row = L.row(True, "Show")
    row.prop("show_alive", toggle=True)
    row.prop("show_dead", toggle=True)
    row.prop("show_unborn", toggle=True)
    col = L.column()
    col.prop("use_edge_cut")
    col.prop("use_size")
    L.vgroup()
    row = L.row(False)
    row.active = bool(md.vertex_group)
    row.prop("protect")
    L.op("object.explode_refresh", "Refresh")


def _P_HOOK(L, md, ob, C):
    L.split = True
    col = L.column()
    col.prop("object")
    if md.object is not None and md.object.type == 'ARMATURE':
        col.search("subtarget", lambda md_, ob_: md_.object.data, "bones", text="Bone")
    L.vgroup()
    L.prop("strength", slider=True)
    if ob.mode == 'EDIT':
        row = L.row(True)
        row.op("object.hook_reset", "Reset")
        row.op("object.hook_recenter", "Recenter")
        row = L.row(True)
        row.op("object.hook_select", "Select")
        row.op("object.hook_assign", "Assign")
    p = L.panel("falloff", "Falloff")
    if p:
        p.split = True
        p.prop("falloff_type", text="Type")
        row = p.row(False)
        row.active = md.falloff_type != 'NONE'
        row.prop("falloff_radius")
        p.prop("use_falloff_uniform")
        if md.falloff_type == 'CURVE':
            p.template('curve_mapping', "falloff_curve")


def _P_LAPLACIANDEFORM(L, md, ob, C):
    L.split = True
    L.prop("iterations")
    L.vgroup()
    L.separator()
    row = L.row(True)
    row.enabled = bool(md.vertex_group)
    row.op("object.laplaciandeform_bind", "Unbind" if md.is_bind else "Bind")


def _P_LAPLACIANSMOOTH(L, md, ob, C):
    L.split = True
    L.prop("iterations")
    row = L.row(True, "Axis")
    row.prop("use_x", toggle=True)
    row.prop("use_y", toggle=True)
    row.prop("use_z", toggle=True)
    L.prop("lambda_factor")
    L.prop("lambda_border")
    L.prop("use_volume_preserve")
    L.prop("use_normalized")
    L.vgroup()


def _P_LATTICE(L, md, ob, C):
    L.split = True
    L.prop("object")
    L.vgroup()
    L.prop("strength", slider=True)


def _P_MASK(L, md, ob, C):
    L.prop("mode", expand=True)
    L.split = True
    if md.mode == 'ARMATURE':
        row = L.row(True)
        row.prop("armature")
        sub = row.row(True)
        sub.prop("invert_vertex_group", text="", icon='arrow_leftright')
    elif md.mode == 'VERTEX_GROUP':
        L.vgroup()
        L.prop("use_smooth")
    L.prop("threshold")


def _P_MESH_TO_VOLUME(L, md, ob, C):
    L.split = True
    L.prop("object")
    L.prop("density")
    L.column().prop("interior_band_width")
    col = L.column()
    col.prop("resolution_mode")
    col.prop("voxel_amount" if md.resolution_mode == 'VOXEL_AMOUNT' else "voxel_size")


def _P_MESH_CACHE(L, md, ob, C):
    L.split = True
    L.prop("cache_format")
    L.prop("filepath")
    L.prop("factor", slider=True)
    L.prop("deform_mode")
    L.prop("interpolation")
    L.vgroup()
    p = L.panel("time_remapping", "Time Remapping")
    if p:
        p.prop("time_mode", expand=True)
        p.split = True
        p.prop("play_mode", expand=True)
        if md.play_mode == 'SCENE':
            p.prop("frame_start")
            p.prop("frame_scale")
        elif md.time_mode == 'FRAME':
            p.prop("eval_frame")
        elif md.time_mode == 'TIME':
            p.prop("eval_time")
        else:
            p.prop("eval_factor")
    p = L.panel("axis_mapping", "Axis Mapping")
    if p:
        p.split = True
        col = p.column(True)
        col.red = md.forward_axis == md.up_axis
        col.prop("forward_axis")
        col.prop("up_axis")
        row = col.row(True, "Flip Axis")
        for i, a in enumerate("XYZ"):
            row.prop("flip_axis", index=i, text=a, toggle=True)


def _P_MESH_DEFORM(L, md, ob, C):
    L.split = True
    col = L.column(True)
    col.enabled = not md.is_bound
    col.prop("object")
    L.vgroup()
    col = L.column()
    col.enabled = not md.is_bound
    col.prop("precision")
    col.prop("use_dynamic_bind")
    L.op("object.meshdeform_bind", "Unbind" if md.is_bound else "Bind")


def _P_MESH_SEQUENCE_CACHE(L, md, ob, C):
    L.split = True
    L.template('cache_file', "cache_file", text="Cache File")
    if md.cache_file is not None:
        L.search("object_path", lambda md_, ob_: md_.cache_file, "object_paths")
    if ob.type == 'MESH':
        L.prop("read_data", expand=True)
        L.prop("use_vertex_interpolation")
    elif ob.type == 'CURVES':
        L.prop("use_vertex_interpolation")
    if md.cache_file is not None:
        p = L.panel("time", "Time")
        if p:
            p.template('cache_time', "cache_file", text="Time Settings")
        p = L.panel("velocity", "Velocity")
        if p:
            p.split = True
            p.template('cache_velocity', "cache_file", text="Velocity Attribute")
            p.prop("velocity_scale")
        p = L.panel("override_layers", "Override Layers")
        if p:
            p.template('cache_layers', "cache_file", text="Layers")


def _P_MIRROR(L, md, ob, C):
    has_bisect = any(md.use_bisect_axis)
    col = L.column()
    col.split = True
    for prop, head, act in (("use_axis", "Axis", True), ("use_bisect_axis", "Bisect", True),
                            ("use_bisect_flip_axis", "Flip", has_bisect)):
        row = col.row(True, head)
        row.active = act
        for i, a in enumerate("XYZ"):
            row.prop(prop, index=i, text=a, toggle=True)
    col.separator()
    col.prop("mirror_object")
    col.prop("use_clip", text="Clipping")
    row = col.row(True, "Merge")
    row.prop("use_mirror_merge", text="")
    sub = row.row(True)
    sub.active = md.use_mirror_merge
    sub.prop("merge_threshold", text="")
    sub = col.row(True)
    sub.active = has_bisect
    sub.prop("bisect_threshold", text="Bisect Distance")
    p = L.panel("data", "Data")
    if p:
        p.split = True
        col = p.column(True)
        for use, off, head in (("use_mirror_u", "mirror_offset_u", "Mirror U"),
                               ("use_mirror_v", "mirror_offset_v", "V")):
            row = col.row(True, head)
            sub = row.row(True)
            sub.prop(use, text="")
            sub = sub.row(True)
            sub.active = getattr(md, use)
            sub.prop(off, text="", slider=True)
        col = p.column(True)
        col.prop("offset_u", slider=True, text="Offset U")
        col.prop("offset_v", slider=True, text="V")
        p.prop("use_mirror_vertex_groups", text="Vertex Groups")
        p.prop("use_mirror_udim", text="Flip UDIM")


def _P_MULTIRES(L, md, ob, C):
    L.split = True
    col = L.column(True)
    col.prop("levels", text="Levels Viewport")
    col.prop("sculpt_levels", text="Sculpt")
    col.prop("render_levels", text="Render")
    sub = col.column(True)
    sub.enabled = ob.mode == 'SCULPT'
    sub.prop("use_sculpt_base_mesh", text="Sculpt Base Mesh")
    L.prop("show_only_control_edges")
    not_edit = ob.mode != 'EDIT'
    p = L.panel("subdivide", "Subdivision")
    if p:
        p.enabled = not_edit
        p.op("object.multires_subdivide", "Subdivide", mode='CATMULL_CLARK')
        row = p.row(False)
        row.op("object.multires_subdivide", "Simple", mode='SIMPLE')
        row.op("object.multires_subdivide", "Linear", mode='LINEAR')
        p.separator()
        p.op("object.multires_unsubdivide", "Unsubdivide")
        p.op("object.multires_higher_levels_delete", "Delete Higher")
    p = L.panel("shape", "Shape")
    if p:
        p.enabled = not_edit
        p.row(False).op("object.multires_reshape", "Reshape")
        row = p.row(False)
        row.op("object.multires_base_apply", "Apply Base", apply_heuristic=True)
        row.op("object.multires_base_apply", "Conform Base", apply_heuristic=False)
    p = L.panel("generate", "Generate")
    if p:
        if md.total_levels == 0:
            p.op("object.multires_rebuild_subdiv", "Rebuild Subdivisions")
        col = p.column()
        if md.is_external:
            col.row(False).op("object.multires_external_pack", "Pack External")
            col.split = True
            col.row(False).prop("filepath")
        else:
            col.op("object.multires_external_save", "Save External...")
    p = L.panel("advanced", "Advanced")
    if p:
        p.split = True
        p.active = md.total_levels == 0
        p.prop("quality")
        col = p.column()
        col.active = True
        col.prop("uv_smooth")
        col.prop("boundary_smooth")
        p.prop("use_creases")
        p.prop("use_custom_normals")


def _P_NORMAL_EDIT(L, md, ob, C):
    L.prop("mode", expand=True)
    L.split = True
    L.prop("target")
    col = L.column()
    col.active = md.mode == 'DIRECTIONAL'
    col.prop("use_direction_parallel")
    p = L.panel("mix", "Mix")
    if p:
        p.split = True
        p.prop("mix_mode")
        p.prop("mix_factor")
        p.vgroup()
        row = p.row(True)
        row.prop("mix_limit")
        row.prop("no_polynors_fix", text="",
                 icon=lambda v: 'locked' if v else 'unlocked')
    p = L.panel("offset", "Offset")
    if p:
        needs = ((md.mode == 'RADIAL' and md.target is None) or
                 (md.mode == 'DIRECTIONAL' and md.use_direction_parallel))
        p.split = True
        p.active = needs
        p.prop("offset")


def _P_OCEAN(L, md, ob, C):
    L.split = True
    col = L.column()
    col.prop("geometry_mode")
    if md.geometry_mode == 'GENERATE':
        sub = col.column(True)
        sub.prop("repeat_x", text="Repeat X")
        sub.prop("repeat_y", text="Y")
    sub = col.column(True)
    sub.prop("viewport_resolution", text="Resolution Viewport")
    sub.prop("resolution", text="Render")
    for a in ("time", "depth", "size", "spatial_size", "random_seed", "use_normals"):
        col.prop(a)
    p = L.panel("waves", "Waves")
    if p:
        p.split = True
        col = p.column()
        col.prop("wave_scale", text="Scale")
        col.prop("wave_scale_min")
        col.prop("choppiness")
        col.prop("wind_velocity")
        p.separator()
        col = p.column()
        col.prop("wave_alignment", slider=True, text="Alignment")
        sub = col.column()
        sub.active = md.wave_alignment > 0.0
        sub.prop("wave_direction", text="Direction")
        sub.prop("damping")
    p = L.panel("foam", "", header="use_foam", header_text="Foam")
    if p:
        p.split = True
        col = p.column()
        col.active = md.use_foam
        col.prop("foam_layer_name", text="Data Layer")
        col.prop("foam_coverage", text="Coverage")
        q = p.panel("spray", "", header="use_spray", header_text="Spray",
                    header_active=md.use_foam)
        if q:
            q.split = True
            col = q.column()
            col.active = md.use_foam and md.use_spray
            col.prop("spray_layer_name", text="Data Layer")
            col.prop("invert_spray", text="Invert")
    p = L.panel("spectrum", "Spectrum")
    if p:
        p.split = True
        col = p.column()
        col.prop("spectrum")
        if md.spectrum in {'TEXEL_MARSEN_ARSLOE', 'JONSWAP'}:
            col.prop("sharpen_peak_jonswap", slider=True)
            col.prop("fetch_jonswap")
    p = L.panel("bake", "Bake")
    if p:
        p.split = True
        if md.is_cached:
            p.op("object.ocean_bake", "Delete Bake", free=True)
        else:
            p.op("object.ocean_bake", "Bake", free=False)
        p.prop("filepath")
        col = p.column(True)
        col.enabled = not md.is_cached
        col.prop("frame_start", text="Frame Start")
        col.prop("frame_end", text="End")
        col = p.column()
        col.active = md.use_foam
        col.prop("bake_foam_fade")


def _P_PARTICLE_INSTANCE(L, md, ob, C):
    L.split = True
    L.prop("object")
    if md.object is not None:
        L.search("particle_system", lambda md_, ob_: md_.object, "particle_systems",
                 text="Particle System")
    else:
        L.prop("particle_system_index", text="Particle System")
    L.separator()
    row = L.row(True, "Create Instances")
    for a in ("use_normal", "use_children", "use_size"):
        row.prop(a, toggle=True)
    row = L.row(True, "Show")
    for a in ("show_alive", "show_dead", "show_unborn"):
        row.prop(a, toggle=True)
    L.prop("particle_amount", text="Amount")
    L.prop("particle_offset", text="Offset")
    L.separator()
    L.prop("space", text="Coordinate Space")
    row = L.row(True)
    row.prop("axis", expand=True)
    p = L.panel("paths", "", header="use_path", header_text="Create Along Paths")
    if p:
        p.split = True
        p.active = md.use_path
        col = p.column(True)
        col.prop("position", slider=True)
        col.prop("random_position", slider=True, text="Random")
        col = p.column(True)
        col.prop("rotation", slider=True)
        col.prop("random_rotation", slider=True, text="Random")
        p.prop("use_preserve_shape")
    p = L.panel("layers", "Layers")
    if p:
        p.split = True
        col = p.column()
        getter = lambda md_, ob_: ob_.data
        coll = "vertex_colors" if hasattr(ob.data, "vertex_colors") else "color_attributes"
        col.search("index_layer_name", getter, coll, text="Index")
        col.search("value_layer_name", getter, coll, text="Value")


def _P_PARTICLE_SYSTEM(L, md, ob, C):
    L.label("Settings are inside the Particles tab")
    if ob.mode != 'PARTICLE_EDIT':
        part = md.particle_system.settings if md.particle_system else None
        if part is not None and part.render_type in {'COLLECTION', 'OBJECT'}:
            L.op("object.duplicates_make_real", "Make Instances Real")
        elif part is not None and part.render_type == 'PATH':
            L.op("object.modifier_convert", "Convert to Mesh")


def _P_REMESH(L, md, ob, C):
    L.prop("mode", expand=True)
    L.split = True
    col = L.column()
    if md.mode == 'VOXEL':
        col.prop("voxel_size")
        col.prop("adaptivity")
    else:
        col.prop("octree_depth")
        col.prop("scale")
        if md.mode == 'SHARP':
            col.prop("sharpness")
        L.prop("use_remove_disconnected")
        row = L.row(False)
        row.active = md.use_remove_disconnected
        row.prop("threshold")
    L.prop("use_smooth_shade")


def _P_SCREW(L, md, ob, C):
    L.split = True
    col = L.column()
    col.prop("angle")
    row = col.row(False)
    row.active = md.object is None or not md.use_object_screw_offset
    row.prop("screw_offset")
    col.prop("iterations")
    L.separator()
    col = L.column()
    row = col.row(False)
    row.prop("axis", expand=True)
    col.prop("object", text="Axis Object")
    sub = col.column()
    sub.active = md.object is not None
    sub.prop("use_object_screw_offset")
    L.separator()
    col = L.column(True)
    col.prop("steps", text="Steps Viewport")
    col.prop("render_steps", text="Render")
    L.separator()
    row = L.row(True, "Merge")
    row.prop("use_merge_vertices", text="")
    sub = row.row(True)
    sub.active = md.use_merge_vertices
    sub.prop("merge_threshold", text="")
    L.separator()
    row = L.row(True, "Stretch UVs")
    row.prop("use_stretch_u", toggle=True, text="U")
    row.prop("use_stretch_v", toggle=True, text="V")
    p = L.panel("normals", "Normals")
    if p:
        p.split = True
        col = p.column()
        col.prop("use_smooth_shade")
        col.prop("use_normal_calculate")
        col.prop("use_normal_flip")


def _P_SHRINKWRAP(L, md, ob, C):
    L.split = True
    wm = md.wrap_method
    L.prop("wrap_method")
    if wm in {'PROJECT', 'NEAREST_SURFACEPOINT', 'TARGET_PROJECT'}:
        L.prop("wrap_mode")
    if wm == 'PROJECT':
        L.prop("project_limit", text="Limit")
        L.prop("subsurf_levels")
        col = L.column()
        row = col.row(True, "Axis")
        row.prop("use_project_x", toggle=True)
        row.prop("use_project_y", toggle=True)
        row.prop("use_project_z", toggle=True)
        col.prop("use_negative_direction")
        col.prop("use_positive_direction")
        L.prop("cull_face", expand=True)
        col = L.column()
        col.active = md.use_negative_direction and md.cull_face != 'OFF'
        col.prop("use_invert_cull")
    L.prop("target")
    if wm == 'PROJECT':
        L.prop("auxiliary_target")
    L.prop("offset")
    L.vgroup()


def _P_SIMPLE_DEFORM(L, md, ob, C):
    row = L.row(False)
    row.prop("deform_method", expand=True)
    L.split = True
    if md.deform_method in {'TAPER', 'STRETCH'}:
        L.prop("factor")
    else:
        L.prop("angle")
    L.prop("origin")
    L.prop("deform_axis", expand=True)
    p = L.panel("restrictions", "Restrictions")
    if p:
        p.split = True
        p.prop("limits", slider=True)
        if md.deform_method in {'TAPER', 'STRETCH', 'TWIST'}:
            row = p.row(True, "Lock")
            ax = md.deform_axis
            if ax != 'X':
                row.prop("lock_x", toggle=True)
            if ax != 'Y':
                row.prop("lock_y", toggle=True)
            if ax != 'Z':
                row.prop("lock_z", toggle=True)
        p.vgroup()


def _P_SKIN(L, md, ob, C):
    L.split = True
    L.prop("branch_smoothing")
    row = L.row(True, "Symmetry")
    for a in ("use_x_symmetry", "use_y_symmetry", "use_z_symmetry"):
        row.prop(a, toggle=True)
    L.prop("use_smooth_shade")
    row = L.row(False)
    row.op("object.skin_armature_create", "Create Armature")
    row.op("mesh.customdata_skin_add", "Add Skin Data")
    row = L.row(False)
    row.op("object.skin_loose_mark_clear", "Mark Loose", action='MARK')
    row.op("object.skin_loose_mark_clear", "Clear Loose", action='CLEAR')
    L.op("object.skin_root_mark", "Mark Root")
    L.op("object.skin_radii_equalize", "Equalize Radii")


def _P_SMOOTH(L, md, ob, C):
    L.split = True
    row = L.row(True, "Axis")
    for a in ("use_x", "use_y", "use_z"):
        row.prop(a, toggle=True)
    col = L.column()
    col.prop("factor")
    col.prop("iterations")
    L.vgroup()


def _P_SOLIDIFY(L, md, ob, C):
    nm = md.solidify_mode == 'NON_MANIFOLD'
    L.split = True
    L.prop("solidify_mode")
    if nm:
        L.prop("nonmanifold_thickness_mode", text="Thickness Mode")
        L.prop("nonmanifold_boundary_mode", text="Boundary")
    L.prop("thickness")
    L.prop("offset")
    if nm:
        L.prop("nonmanifold_merge_threshold")
    else:
        L.prop("use_even_offset")
    col = L.column(False, "Rim")
    col.prop("use_rim", text="Fill")
    sub = col.column()
    sub.active = md.use_rim
    sub.prop("use_rim_only")
    L.separator()
    L.vgroup()
    row = L.row(False)
    row.active = bool(md.vertex_group)
    row.prop("thickness_vertex_group", text="Factor")
    if nm:
        row = L.row(False)
        row.active = bool(md.vertex_group)
        row.prop("use_flat_faces")
    p = L.panel("normals", "Normals")
    if p:
        p.split = True
        col = p.column()
        col.prop("use_flip_normals", text="Flip")
        if md.solidify_mode == 'EXTRUDE':
            col.prop("use_quality_normals", text="High Quality")
    p = L.panel("materials", "Materials")
    if p:
        p.split = True
        p.prop("material_offset")
        col = p.column(True)
        col.active = md.use_rim
        col.prop("material_offset_rim", text="Rim")
    p = L.panel("edge_data", "Edge Data")
    if p:
        p.split = True
        if md.solidify_mode == 'EXTRUDE':
            col = p.column(True)
            col.prop("edge_crease_inner", text="Crease Inner")
            col.prop("edge_crease_outer", text="Outer")
            col.prop("edge_crease_rim", text="Rim")
        p.prop("bevel_convex", slider=True)
    p = L.panel("clamp", "Thickness Clamp")
    if p:
        p.split = True
        col = p.column()
        col.prop("thickness_clamp")
        row = col.row(False)
        row.active = md.thickness_clamp > 0.0
        row.prop("use_thickness_angle_clamp")
    p = L.panel("vertex_groups", "Output Vertex Groups")
    if p:
        p.split = True
        col = p.column()
        col.prop("shell_vertex_group", text="Shell", icon='group_vertex')
        col.prop("rim_vertex_group", text="Rim", icon='group_vertex')


def _P_SUBSURF(L, md, ob, C):
    L.prop("subdivision_type", expand=True)
    L.split = True
    col = L.column(True)
    col.prop("levels", text="Levels Viewport")
    col.prop("render_levels", text="Render")
    L.prop("show_only_control_edges")
    scene = C.scene
    if (scene.render.engine == 'CYCLES' and ob.modifiers and ob.modifiers[-1] == md
            and hasattr(md, "use_adaptive_subdivision")):
        p = L.panel("adaptive", "", header="use_adaptive_subdivision",
                    header_text="Adaptive Subdivision",
                    open_prop="open_adaptive_subdivision_panel")
        if p:
            p.split = True
            p.active = md.use_adaptive_subdivision
            p.prop("adaptive_space", text="Space")
            cy = getattr(scene, "cycles", None)
            rr = getattr(cy, "dicing_rate", 1.0)
            pr = getattr(cy, "preview_dicing_rate", 8.0)
            if md.adaptive_space == 'OBJECT':
                p.prop("adaptive_object_edge_length")
                v = md.adaptive_object_edge_length
                pv, rv = f"{pr * v:.5g}", f"{rr * v:.5g}"
            else:
                p.prop("adaptive_pixel_size")
                v = md.adaptive_pixel_size
                pv, rv = f"{max(pr * v, 0.1):.2f} px", f"{max(rr * v, 0.1):.2f} px"
            r = p.row(True, "Viewport")
            r.label(pv)
            r = p.row(True, "Render")
            r.label(rv)
    p = L.panel("advanced", "Advanced", open_prop="open_advanced_panel")
    if p:
        p.split = True
        p.prop("use_limit_surface")
        col = p.column(True)
        col.active = getattr(md, "use_adaptive_subdivision", False) or md.use_limit_surface
        col.prop("quality")
        p.prop("uv_smooth")
        p.prop("boundary_smooth")
        p.prop("use_creases")
        p.prop("use_custom_normals")


def _P_SURFACE_DEFORM(L, md, ob, C):
    L.split = True
    col = L.column()
    col.active = not md.is_bound
    col.prop("target")
    col.prop("falloff")
    L.prop("strength")
    L.vgroup()
    col = L.column()
    col.enabled = not md.is_bound
    col.active = not md.is_bound and bool(md.vertex_group)
    col.prop("use_sparse_bind")
    L.separator()
    col = L.column()
    if md.is_bound:
        col.op("object.surfacedeform_bind", "Unbind")
    else:
        col.active = md.target is not None
        col.op("object.surfacedeform_bind", "Bind")


def _P_TRIANGULATE(L, md, ob, C):
    L.split = True
    for a in ("quad_method", "ngon_method", "min_vertices", "keep_custom_normals"):
        L.prop(a)


def _P_UV_PROJECT(L, md, ob, C):
    L.split = True
    L.prop("uv_layer", icon='group_uvs')
    has_cam = any(pr.object is not None and pr.object.type == 'CAMERA' for pr in md.projectors)
    sub = L.column(True)
    sub.active = has_cam
    sub.prop("aspect_x")
    sub.prop("aspect_y", text="Y")
    sub = L.column(True)
    sub.active = has_cam
    sub.prop("scale_x")
    sub.prop("scale_y", text="Y")
    L.prop("projector_count", text="Projectors")
    for i, pr in enumerate(md.projectors):
        L.prop("object", owner=pr, path=f"projectors[{i}].object")


def _P_UV_WARP(L, md, ob, C):
    L.split = True
    L.prop("uv_layer", icon='group_uvs')
    L.column().prop("center")
    col = L.column()
    col.prop("axis_u", text="Axis U")
    col.prop("axis_v", text="V")
    col = L.column()
    col.prop("object_from")
    if md.object_from is not None and md.object_from.type == 'ARMATURE':
        col.search("bone_from", lambda md_, ob_: md_.object_from.data, "bones",
                   icon='bone_data')
    col.prop("object_to", text="To")
    if md.object_to is not None and md.object_to.type == 'ARMATURE':
        col.search("bone_to", lambda md_, ob_: md_.object_to.data, "bones", icon='bone_data')
    L.vgroup()
    p = L.panel("offset", "Transform")
    if p:
        p.split = True
        p.prop("offset")
        p.prop("scale")
        p.prop("rotation")


def _P_VOLUME_DISPLACE(L, md, ob, C):
    L.split = True
    L.template('texture', "texture", text="Texture")
    L.prop("texture_map_mode", text="Texture Mapping")
    if md.texture_map_mode == 'OBJECT':
        L.prop("texture_map_object", text="Object")
    L.prop("strength")
    L.prop("texture_sample_radius", text="Sample Radius")
    L.prop("texture_mid_level", text="Mid Level")


def _P_VOLUME_TO_MESH(L, md, ob, C):
    L.split = True
    col = L.column()
    col.prop("object")
    col.prop("grid_name")
    col = L.column()
    col.prop("resolution_mode")
    if md.resolution_mode == 'VOXEL_AMOUNT':
        col.prop("voxel_amount")
    elif md.resolution_mode == 'VOXEL_SIZE':
        col.prop("voxel_size")
    col = L.column()
    col.prop("threshold")
    col.prop("adaptivity")
    col.prop("use_smooth_shade")


def _P_WARP(L, md, ob, C):
    L.split = True
    col = L.column(True)
    col.prop("object_from")
    if md.object_from is not None and md.object_from.type == 'ARMATURE':
        col.search("bone_from", lambda md_, ob_: md_.object_from.data, "bones", text="Bone",
                   icon='bone_data')
    col = L.column(True)
    col.prop("object_to")
    if md.object_to is not None and md.object_to.type == 'ARMATURE':
        col.search("bone_to", lambda md_, ob_: md_.object_to.data, "bones", text="Bone",
                   icon='bone_data')
    L.prop("use_volume_preserve")
    L.prop("strength")
    L.vgroup()
    p = L.panel("falloff", "Falloff")
    if p:
        p.split = True
        p.prop("falloff_type")
        if md.falloff_type != 'NONE':
            p.prop("falloff_radius")
            if md.falloff_type == 'CURVE':
                p.template('curve_mapping', "falloff_curve")
    p = L.panel("texture", "Texture")
    if p:
        p.template('texture', "texture", text="")
        p.split = True
        _texture_coords_ui(p.column(), md, ob)


def _P_WAVE(L, md, ob, C):
    L.split = True
    row = L.row(True, "Motion")
    row.prop("use_x", toggle=True)
    row.prop("use_y", toggle=True)
    L.prop("use_cyclic")
    row = L.row(True, "Along Normals")
    row.prop("use_normal", text="")
    sub = row.row(True)
    sub.active = md.use_normal
    sub.prop("use_normal_x", toggle=True, text="X")
    sub.prop("use_normal_y", toggle=True, text="Y")
    sub.prop("use_normal_z", toggle=True, text="Z")
    col = L.column()
    col.prop("falloff_radius", text="Falloff")
    col.prop("height", slider=True)
    col.prop("width", slider=True)
    col.prop("narrowness", slider=True)
    L.vgroup()
    p = L.panel("position", "Start Position")
    if p:
        p.split = True
        p.prop("start_position_object", text="Object")
        col = p.column(True)
        col.prop("start_position_x", text="Start Position X")
        col.prop("start_position_y", text="Y")
    p = L.panel("time", "Time")
    if p:
        p.split = True
        col = p.column()
        col.prop("time_offset", text="Offset")
        col.prop("lifetime", text="Life")
        col.prop("damping_time", text="Damping")
        col.prop("speed", slider=True)
    p = L.panel("texture", "Texture")
    if p:
        p.template('texture', "texture", text="")
        p.split = True
        _texture_coords_ui(p.column(), md, ob)


def _P_WEIGHTED_NORMAL(L, md, ob, C):
    L.split = True
    L.prop("mode")
    L.prop("weight", text="Weight")
    L.prop("thresh", text="Threshold")
    col = L.column()
    col.prop("keep_sharp")
    col.prop("use_face_influence")
    L.vgroup()


def _weightvg_falloff(p, md):
    p.split = True
    row = p.row(True)
    row.prop("falloff_type", text="Type")
    row.prop("invert_falloff", text="", icon='arrow_leftright')
    if md.falloff_type == 'CURVE':
        p.template('curve_mapping', "map_curve")


def _weightvg_influence(p, md, ob):
    """weightvg_ui_common()"""
    p.split = True
    p.prop("mask_constant", slider=True, text="Global Influence:")
    if md.mask_texture is None:
        p.vgroup("mask_vertex_group", "invert_mask_vertex_group")
    if not md.mask_vertex_group:
        p.template('texture', "mask_texture", text="Mask Texture")
        if md.mask_texture is not None:
            p.prop("mask_tex_use_channel", text="Channel")
            p.prop("mask_tex_mapping")
            if md.mask_tex_mapping == 'OBJECT':
                p.prop("mask_tex_map_object", text="Object")
            elif md.mask_tex_mapping == 'UV' and ob.type == 'MESH':
                p.prop("mask_tex_uv_layer", icon='group_uvs')


def _P_VERTEX_WEIGHT_EDIT(L, md, ob, C):
    L.split = True
    L.column(True).prop("vertex_group", icon='group_vertex')
    L.prop("default_weight", slider=True)
    for use, thr, head in (("use_add", "add_threshold", "Group Add"),
                           ("use_remove", "remove_threshold", "Group Remove")):
        col = L.column(False, head)
        row = col.row(True)
        sub = row.row(True)
        sub.prop(use, text="")
        sub = sub.row(True)
        sub.active = getattr(md, use)
        sub.split = False
        sub.prop(thr, slider=True, text="Threshold")
    L.prop("normalize")
    p = L.panel("falloff", "Falloff")
    if p:
        _weightvg_falloff(p, md)
    p = L.panel("influence", "Influence")
    if p:
        _weightvg_influence(p, md, ob)


def _P_VERTEX_WEIGHT_MIX(L, md, ob, C):
    L.split = True
    L.vgroup("vertex_group_a", "invert_vertex_group_a")
    L.vgroup("vertex_group_b", "invert_vertex_group_b", text="B")
    L.separator()
    L.prop("default_weight_a")
    L.prop("default_weight_b", text="B")
    L.separator()
    L.prop("mix_set")
    L.prop("mix_mode")
    L.prop("normalize")
    p = L.panel("influence", "Influence")
    if p:
        _weightvg_influence(p, md, ob)


def _P_VERTEX_WEIGHT_PROXIMITY(L, md, ob, C):
    L.split = True
    L.prop("vertex_group", icon='group_vertex')
    L.prop("target")
    L.separator()
    L.prop("proximity_mode")
    if md.proximity_mode == 'GEOMETRY':
        L.prop("proximity_geometry", expand=True, text="Geometry")
    col = L.column(True)
    col.prop("min_dist")
    col.prop("max_dist")
    L.prop("normalize")
    p = L.panel("falloff", "Falloff")
    if p:
        _weightvg_falloff(p, md)
    p = L.panel("influence", "Influence")
    if p:
        _weightvg_influence(p, md, ob)


def _P_WELD(L, md, ob, C):
    L.split = True
    L.prop("mode")
    L.prop("merge_threshold", text="Distance")
    if md.mode == 'CONNECTED':
        L.prop("loose_edges")
    L.vgroup()


def _P_WIREFRAME(L, md, ob, C):
    L.split = True
    L.prop("thickness", text="Thickness")
    L.prop("offset")
    col = L.column(True)
    col.prop("use_boundary", text="Boundary")
    col.prop("use_replace", text="Replace Original")
    col = L.column(True, "Thickness")
    col.prop("use_even_offset", text="Even")
    col.prop("use_relative_offset", text="Relative")
    row = L.row(True, "Crease Edges")
    row.prop("use_crease", text="")
    sub = row.row(True)
    sub.active = md.use_crease
    sub.prop("crease_weight", slider=True, text="")
    L.prop("material_offset", text="Material Offset")
    p = L.panel("vertex_group", "Vertex Group")
    if p:
        p.split = True
        p.vgroup()
        row = p.row(True)
        row.active = bool(md.vertex_group)
        row.prop("thickness_vertex_group", text="Factor")


_MOD_PANELS = {
    'ARMATURE': _P_ARMATURE, 'ARRAY': _P_ARRAY, 'BEVEL': _P_BEVEL, 'BOOLEAN': _P_BOOLEAN,
    'BUILD': _P_BUILD, 'CAST': _P_CAST, 'CORRECTIVE_SMOOTH': _P_CORRECTIVE_SMOOTH,
    'CURVE': _P_CURVE, 'DATA_TRANSFER': _P_DATA_TRANSFER, 'DECIMATE': _P_DECIMATE,
    'DISPLACE': _P_DISPLACE, 'EDGE_SPLIT': _P_EDGE_SPLIT, 'EXPLODE': _P_EXPLODE,
    'HOOK': _P_HOOK, 'LAPLACIANDEFORM': _P_LAPLACIANDEFORM,
    'LAPLACIANSMOOTH': _P_LAPLACIANSMOOTH, 'LATTICE': _P_LATTICE, 'MASK': _P_MASK,
    'MESH_TO_VOLUME': _P_MESH_TO_VOLUME, 'MESH_CACHE': _P_MESH_CACHE,
    'MESH_DEFORM': _P_MESH_DEFORM, 'MESH_SEQUENCE_CACHE': _P_MESH_SEQUENCE_CACHE,
    'MIRROR': _P_MIRROR, 'MULTIRES': _P_MULTIRES, 'NORMAL_EDIT': _P_NORMAL_EDIT,
    'OCEAN': _P_OCEAN, 'PARTICLE_INSTANCE': _P_PARTICLE_INSTANCE,
    'PARTICLE_SYSTEM': _P_PARTICLE_SYSTEM, 'REMESH': _P_REMESH, 'SCREW': _P_SCREW,
    'SHRINKWRAP': _P_SHRINKWRAP, 'SIMPLE_DEFORM': _P_SIMPLE_DEFORM, 'SKIN': _P_SKIN,
    'SMOOTH': _P_SMOOTH, 'SOLIDIFY': _P_SOLIDIFY, 'SUBSURF': _P_SUBSURF,
    'SURFACE_DEFORM': _P_SURFACE_DEFORM, 'TRIANGULATE': _P_TRIANGULATE,
    'UV_PROJECT': _P_UV_PROJECT, 'UV_WARP': _P_UV_WARP,
    'VOLUME_DISPLACE': _P_VOLUME_DISPLACE, 'VOLUME_TO_MESH': _P_VOLUME_TO_MESH,
    'WARP': _P_WARP, 'WAVE': _P_WAVE, 'WEIGHTED_NORMAL': _P_WEIGHTED_NORMAL,
    'VERTEX_WEIGHT_EDIT': _P_VERTEX_WEIGHT_EDIT, 'VERTEX_WEIGHT_MIX': _P_VERTEX_WEIGHT_MIX,
    'VERTEX_WEIGHT_PROXIMITY': _P_VERTEX_WEIGHT_PROXIMITY, 'WELD': _P_WELD,
    'WIREFRAME': _P_WIREFRAME,
    'CLOTH': _P_physics, 'COLLISION': _P_physics, 'DYNAMIC_PAINT': _P_physics,
    'FLUID': _P_physics, 'SOFT_BODY': _P_physics, 'SURFACE': _P_physics,
}
