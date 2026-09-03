# SPDX-License-Identifier: GPL-2.0-or-later
"""Scene settings and manual, contextual, bevel-face, and automatic decal generation operators.

Loaded into the add-on package shared namespace by __init__.py.
"""


class EDGEDECAL_PG_settings(PropertyGroup):
    face_width: FloatProperty(
        name="Face Width",
        default=0.01,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        precision=6,
        description="Width as a fraction of the source object's largest world-space dimension when Relative Width is enabled",
        update=schedule_scene_decal_live_update,
    )

    relative_face_width: BoolProperty(
        name="Relative Width",
        default=True,
        description="Scale Face Width from the source object's largest world-space dimension so differently sized assets get proportional decals",
        update=schedule_scene_decal_live_update,
    )

    crevice_removal: FloatProperty(
        name="Crevice Removal",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description=(
            "Remove damage from inward concave edges. 0 keeps all crevice edges; "
            "1 removes all detected concave edges"
        ),
    )
    crevice_detection_mode: EnumProperty(
        name="Crevice Detection",
        items=CREVICE_DETECTION_ITEMS,
        default="AO",
        description=(
            "Ambient Occlusion uses local raycasts and is more reliable on "
            "Geometry keeps the older angle test"
        ),
    )

    crevice_ao_distance: FloatProperty(
        name="AO Distance",
        default=0.0,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
        description=(
            "Maximum local occlusion distance. Zero automatically uses four "
            "times Face Width"
        ),
    )

    crevice_ao_samples: IntProperty(
        name="AO Samples",
        default=8,
        min=4,
        max=32,
        description=(
            "Number of cross-section rays per test point. Higher values are "
            "more stable but slower"
        ),
    )

    remove_short_edges: BoolProperty(
        name="Remove Short Edges",
        default=False,
        description=(
            "Ignore eligible edges shorter than the Minimum Edge Length"
        ),
    )

    minimum_edge_length: FloatProperty(
        name="Minimum Edge Length",
        default=0.05,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
        description=(
            "World-space edge length below which edges are excluded from decal generation"
        ),
    )

    auto_minimum_edge_length: FloatProperty(
        name="Automatic Minimum Edge Length",
        default=0.30,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
        description=(
            "World-space minimum used only by Generate Automatically. "
            "Automatic mode measures individual source edges to reject tiny "
            "segments that can create unstable geometry"
        ),
    )

    decal_amount: FloatProperty(
        name="Decal Amount",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description=(
            "Controls total decal coverage and slice intensity. Lower values "
            "retain less edge wear and shorten continuous decal chains more aggressively"
        ),
        update=schedule_scene_decal_live_update,
    )

    edge_slice: FloatProperty(
        name="Legacy Edge Slice",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        options={"HIDDEN"},
        description="Legacy compatibility value; Decal Amount now continuously controls slicing",
    )

    interactive_slice_start: FloatProperty(
        name="Interactive Slice Start",
        default=-1.0,
        min=-1.0,
        max=1.0,
        options={"HIDDEN"},
    )

    interactive_slice_end: FloatProperty(
        name="Interactive Slice End",
        default=-1.0,
        min=-1.0,
        max=1.0,
        options={"HIDDEN"},
    )


    interactive_detect_endpoint_taper: BoolProperty(
        name="Interactive Endpoint Taper",
        default=False,
        options={"HIDDEN"},
        description="Internal interactive mode flag: taper only visually exposed endpoints on full selected edges",
    )

    maximum_decal_length: FloatProperty(
        name="Maximum Decal Length",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
        description=(
            "Maximum continuous generated decal length. Zero disables the limit"
        ),
    )

    taper_sliced_ends: BoolProperty(
        name="Taper Sliced Ends",
        default=True,
        description=(
            "Taper only endpoints introduced by Decal Amount slicing; "
            "original decal endpoints remain unchanged"
        ),
    )

    slice_taper_length: FloatProperty(
        name="Taper Length",
        default=0.24,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
        description="Distance from a sliced tip to full decal width",
    )

    auto_trim_corner_ends: BoolProperty(
        name="Auto Trim Tight Corner Ends",
        default=False,
        description=(
            "Trim only open decal ends that stop beside a real turning continuation"
        ),
        update=schedule_scene_decal_live_update,
    )

    corner_end_trim_multiplier: FloatProperty(
        name="Corner Trim Multiplier",
        default=1.0,
        min=0.0,
        soft_max=3.0,
        description="Trim distance relative to the last source Bevel modifier width",
        update=schedule_scene_decal_live_update,
    )

    auto_width_samples: IntProperty(
        name="Auto Width Samples",
        default=1,
        min=1,
        max=5,
        description="Lower values are faster; higher values detect nearby edges more reliably",
    )

    auto_face_width: BoolProperty(
        name="Auto Face Width",
        default=False,
        description=(
            "Reduce the width per edge side when the requested Face Width "
            "would reach a nearby edge on the same surface"
        ),
    )

    auto_width_clearance: FloatProperty(
        name="Width Clearance",
        default=0.85,
        min=0.05,
        max=0.99,
        subtype="FACTOR",
        description=(
            "Percentage of the detected free space that the decal is allowed to use"
        ),
    )

    clamp_edge_overlaps: BoolProperty(
        name="Clamp Edge Overlaps",
        default=True,
        description=(
            "Build a connected curve-graph strip and locally reduce its width "
            "before it reaches another selected decal edge"
        ),
    )

    overlap_clearance: FloatProperty(
        name="Overlap Clearance",
        default=0.98,
        min=0.5,
        max=0.999,
        subtype="FACTOR",
        description=(
            "Fraction of the shared space used by two opposing strips; "
            "lower values leave a larger gap"
        ),
    )

    use_face_loop_slide: BoolProperty(
        name="Follow Connected Face Edges",
        default=True,
        description=(
            "Prefer a real connected support-face edge at safe endpoints, "
            "and fall back to the existing miter solver when no suitable rail exists"
        ),
    )

    surface_offset: FloatProperty(
        name="Surface Offset",
        default=0.002,
        min=0.0,
        soft_max=0.05,
        unit="LENGTH",
        description="Small world-space offset used to prevent z-fighting",
        update=update_decal_surface_offset,
    )

    miter_limit: FloatProperty(
        name="Miter Limit",
        default=4.0,
        min=1.0,
        max=20.0,
        description="Limits very long planar miters at acute corners",
    )

    auto_edge_angle: FloatProperty(
        name="Auto Edge Angle",
        default=radians(30.0),
        min=0.0,
        max=radians(180.0),
        subtype="ANGLE",
        description=(
            "In Object Mode, use manifold edges whose angle between adjacent "
            "faces is at least this value as automatic generation seeds"
        ),
    )

    use_edge_split: BoolProperty(
        name="Split Edge Paths",
        default=True,
        description=(
            "Build separate geometry islands where a connected edge path "
            "turns farther than Split Angle"
        ),
        update=schedule_scene_decal_live_update,
    )

    randomize_face_width: BoolProperty(
        name="Random Width",
        default=False,
        description="Choose a repeatable random width for each disconnected decal path",
        update=schedule_scene_decal_live_update,
    )

    minimum_face_width: FloatProperty(
        name="Minimum Width",
        default=0.005,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        precision=6,
        description="Smallest width used when Random Width is enabled",
        update=schedule_scene_decal_live_update,
    )

    maximum_face_width: FloatProperty(
        name="Maximum Width",
        default=0.02,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        precision=6,
        description="Largest width used when Random Width is enabled",
        update=schedule_scene_decal_live_update,
    )

    auto_follow_edge_loops: BoolProperty(
        name="Auto Follow Edge Loops",
        default=True,
        description=(
            "Follow connected quad-topology loops without including edges "
            "below Auto Edge Angle"
        ),
    )

    split_angle: FloatProperty(
        name="Split Angle",
        default=radians(45.0),
        min=0.0,
        max=radians(180.0),
        subtype="ANGLE",
        description=(
            "Split only when the actual path turn exceeds this angle; "
            "straight continuations remain connected even at topology junctions"
        ),
        update=schedule_scene_decal_live_update,
    )

    add_weld_modifier: BoolProperty(
        name="Add Weld Modifier",
        default=False,
        description="Add the Weld modifier to generated decals",
        update=update_decal_finish_modifiers,
    )

    add_bevel_modifier: BoolProperty(
        name="Add Bevel Modifier",
        default=False,
        description=(
            "Add a final Bevel modifier; copy the source Bevel when available, "
            "otherwise use the custom bevel settings below"
        ),
        update=update_decal_finish_modifiers,
    )

    add_center_displace_modifier: BoolProperty(
        name="Displace Center",
        default=False,
        description=(
            "Add a Displace modifier restricted to the EdgeDecal_Center "
            "vertex group and place it before the Bevel modifier"
        ),
        update=update_decal_finish_modifiers,
    )

    bevel_edge_center: BoolProperty(
        name="Bevel Edge Center",
        default=False,
        description=(
            "Limit the Bevel modifier to the EdgeDecal_Center vertex group"
        ),
        update=update_decal_finish_modifiers,
    )

    add_shrinkwrap_modifier: BoolProperty(
        name="Add Shrinkwrap Modifier",
        default=False,
        description=(
            "Add a Shrinkwrap modifier to generated decals and automatically "
            "use the source mesh as its target, with Surface Offset as its offset"
        ),
        update=update_decal_finish_modifiers,
    )

    add_subdivision_modifier: BoolProperty(
        name="Add Subdivision Modifier",
        default=False,
        description="Add a Subdivision Surface modifier to generated decals",
        update=update_decal_finish_modifiers,
    )

    add_decimate_modifier: BoolProperty(
        name="Add Decimate Modifier",
        default=False,
        description="Add a Decimate modifier to generated decals",
        update=update_decal_finish_modifiers,
    )

    weld_distance: FloatProperty(
        name="Weld Distance",
        default=0.0001,
        min=0.0,
        soft_max=0.01,
        precision=6,
        unit="LENGTH",
        description="Merge overlapping vertices before the final bevel modifier",
        update=update_decal_finish_modifiers,
    )

    center_displace_strength: FloatProperty(
        name="Center Displace Strength",
        default=0.002,
        precision=5,
        unit="LENGTH",
        description=(
            "Normal displacement strength applied only to EdgeDecal_Center"
        ),
        update=update_decal_finish_modifiers,
    )

    center_bevel_width: FloatProperty(
        name="Bevel Width",
        default=0.015,
        min=0.0,
        soft_max=0.2,
        unit="LENGTH",
        description="Width of the angle-limited bevel",
        update=update_decal_finish_modifiers,
    )

    center_bevel_segments: IntProperty(
        name="Bevel Segments",
        default=2,
        min=1,
        max=16,
        description="Number of segments used by the angle-limited bevel",
        update=update_decal_finish_modifiers,
    )

    center_bevel_profile: FloatProperty(
        name="Bevel Profile",
        default=0.5,
        min=0.0,
        max=1.0,
        description="Shape of the bevel profile; 0.5 creates a circular arc",
        update=update_decal_finish_modifiers,
    )

    bevel_harden_normals: BoolProperty(
        name="Harden Normals",
        default=False,
        description="Harden normals on the generated decal's Bevel modifier",
        update=update_decal_finish_modifiers,
    )

    normal_mode: EnumProperty(
        name="Normal Shading",
        items=NORMAL_MODE_ITEMS,
        default="SHADE_SMOOTH",
        description="Normal shading used by newly generated decals",
    )

    normal_keep_sharp: BoolProperty(
        name="Keep Sharp Edges",
        default=False,
        description="Preserve sharp edge boundaries in the normal modifier",
    )

    normal_weight: IntProperty(
        name="Weight",
        default=50,
        min=1,
        max=100,
        description="Weight used by the Weighted Normals mode",
    )

    normal_threshold: FloatProperty(
        name="Threshold",
        default=0.01,
        min=0.0,
        max=10.0,
        precision=4,
        description="Ignore normal contributions below this threshold",
    )

    bevel_angle: FloatProperty(
        name="Angle Limit",
        default=radians(30.0),
        min=0.0,
        max=radians(180.0),
        subtype="ANGLE",
        description="Only edges sharper than this angle are beveled",
        update=update_decal_finish_modifiers,
    )

    replace_previous: BoolProperty(
        name="Merge With Existing Decals",
        default=True,
        description=(
            "Append newly generated decal geometry to the existing edge decal "
            "object for this source mesh instead of creating separate objects"
        ),
    )

    auto_use_uv_pins: BoolProperty(
        name="Automatically Use UV Pins",
        default=False,
        description=(
            "Automatically center and vertically scale newly generated decal "
            "UV islands to the existing UV pins"
        ),
    )

    fast_geometry_only: BoolProperty(
        name="Fast Geometry Only",
        default=False,
        description=(
            "Skip quadrify, texel-density processing, UV strip placement, "
            "random UV offsets, and automatic UV-pin fitting without changing "
            "the saved UV-pin preference"
        ),
    )

    auto_unwrap_uvs: BoolProperty(
        name="Unwrap UVs",
        default=True,
        description=(
            "Generate and process UVs for the created decal strips"
        ),
    )

    generate_second_uv: BoolProperty(
        name="Material UV Projection",
        default=True,
        description=(
            "Create UVMap.001; Match Material projects the source object's "
            "first UV map onto it, otherwise Blender's Conformal unwrap and "
            "the Texel Density target are used"
        ),
    )

    use_integrated_quadrify: BoolProperty(
        name="Quadrify UV Strips",
        default=True,
        description=(
            "Use the self-contained GPL quadrify implementation built into "
            "this add-on"
        ),
    )

    integrated_quadrify_average_shape: BoolProperty(
        name="Average Strip Shape",
        default=True,
        description=(
            "Average corresponding mesh edge-loop lengths before quadrifying"
        ),
    )

    integrated_quadrify_even_shape: BoolProperty(
        name="Even Quad Shape",
        default=False,
        description=(
            "Use square UV quads instead of preserving mesh proportions"
        ),
    )

    use_follow_active_quads: BoolProperty(
        name="Blender Follow Active Quads Fallback",
        default=False,
        description=(
            "Use Blender Follow Active Quads only when Quadrify UV Strips "
            "is disabled"
        ),
    )

    uv_scale: FloatProperty(
        name="UV Scale",
        default=1.0,
        min=0.01,
        soft_min=0.1,
        soft_max=10.0,
        precision=3,
        description=(
            "Additional UV scale multiplier applied after unwrap, alignment, "
            "texel density, and strip placement"
        ),
        update=schedule_scene_decal_live_update,
    )

    set_target_texel_density: BoolProperty(
        name="Set Texel Density",
        default=True,
        description=(
            "Scale generated UV islands to an exact pixels-per-centimeter target; "
            "quarter-strip placement will not resize them afterward"
        ),
    )

    target_texel_density: FloatProperty(
        name="Texel Density",
        default=5.12,
        min=0.01,
        soft_max=20.0,
        precision=3,
        description="Target UV density in pixels per centimeter",
    )

    texture_resolution: IntProperty(
        name="Texture Resolution",
        default=2048,
        min=1,
        soft_max=8192,
        description=(
            "Resolution of the square decal texture used to convert px/cm "
            "into UV scale"
        ),
    )

    average_uv_island_scale: BoolProperty(
        name="Average Islands Scale",
        default=True,
        description=(
            "Equalize texel density across generated UV islands before "
            "horizontal alignment and quarter-strip placement"
        ),
    )

    align_uvs_horizontally: BoolProperty(
        name="Align UVs Horizontally",
        default=True,
        description=(
            "Rotate each UV island so its longest dimension runs horizontally"
        ),
    )

    place_in_quarter_strips: BoolProperty(
        name="Use 0.25 UV Strips",
        default=True,
        description=(
            "Fit each UV island into one of four horizontal 0.25-high bands "
            "inside the 0-1 UV space"
        ),
    )

    randomize_quarter_strip: BoolProperty(
        name="Random Quarter Strip",
        default=True,
        description=(
            "Randomly choose which of the four 0.25-high bands receives each island"
        ),
    )

    randomize_horizontal_offset: BoolProperty(
        name="Random Horizontal Offset",
        default=True,
        description=(
            "Give every UV island a distinct randomized U position; wide "
            "islands may tile beyond 0-1 so their horizontal phase can change"
        ),
    )

    horizontal_randomize_amount: FloatProperty(
        name="Horizontal Randomize Amount",
        default=1.0,
        min=0.0,
        soft_max=500.0,
        description="Total U-space span used to separate randomized UV islands",
    )

    seed: IntProperty(
        name="Seed",
        default=0,
        min=0,
        description=(
            "Controls independently mixed per-path Decal Amount cuts, "
            "slice selection, and random UV placement"
        ),
        update=schedule_scene_decal_live_update,
    )

    uv_strip_padding: FloatProperty(
        name="Strip Padding",
        default=0.01,
        min=0.0,
        max=0.12,
        subtype="FACTOR",
        description=(
            "Padding inside each 0.25-high UV strip, measured in UV space"
        ),
    )

    use_material: BoolProperty(
        name="Assign Material",
        default=True,
        description="Assign the selected decal material to generated decals",
        update=schedule_scene_decal_live_update,
    )
    decal_material: PointerProperty(
        name="Decal Material",
        type=bpy.types.Material,
        description="Material assigned to newly generated decal objects",
        update=schedule_scene_decal_live_update,
    )
    match_source_material: BoolProperty(
        name="Match Material",
        default=True,
        description=(
            "Match Base Color, Metallic, and Roughness to the source mesh; "
            "when disabled, use the decal material's authored values"
        ),
        update=update_scene_match_source_material,
    )


    show_geometry_settings: BoolProperty(
        name="Geometry",
        default=False,
        description="Show geometry generation settings",
    )
    show_geometry_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show geometry settings that are changed less frequently",
    )
    show_bevel_settings: BoolProperty(
        name="Weld and Bevel",
        default=False,
        description="Show generated decal modifier settings",
    )
    show_bevel_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show detailed Weld and Bevel modifier settings",
    )
    show_normals_settings: BoolProperty(
        name="Normals",
        default=False,
        description="Show normal shading settings",
    )
    show_normals_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show detailed normal modifier settings",
    )
    show_uv_settings: BoolProperty(
        name="UV Generation",
        default=False,
        description="Show UV generation and placement settings",
    )
    show_uv_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show UV settings that are changed less frequently",
    )
    show_options_settings: BoolProperty(
        name="Options",
        default=False,
        description="Show general generation options",
    )
    show_options_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show options that are changed less frequently",
    )
    show_generation_actions: BoolProperty(
        name="Edge Generation",
        default=True,
        description="Show manual or automatic edge generation actions",
    )
    show_layer_details: BoolProperty(
        name="Active UV Pins",
        default=False,
        description="Show the active layer's material and UV pin assignments",
    )
    show_material_category: BoolProperty(
        name="Material",
        default=True,
        description="Show material assignment controls",
    )
    show_masking_category: BoolProperty(
        name="Masking",
        default=True,
        description="Show painted texture and crevice masking controls",
    )
    show_uv_category: BoolProperty(
        name="UV Placement",
        default=True,
        description="Show UV placement controls",
    )
    show_interactive_help: BoolProperty(
        name="Interactive Shortcuts",
        default=False,
        description="Show the interactive generation shortcut reference",
    )


def selected_bevel_face_long_rails(face, world_matrix):
    """Return the longer opposite edge pair of one selected quad."""
    loops = list(face.loops)
    if len(loops) != 4:
        return None
    edges = [loop.edge for loop in loops]
    pairs = []
    for first_index in (0, 1):
        opposite_index = first_index + 2
        length = sum(
            (
                world_matrix @ edges[index].verts[1].co
                - world_matrix @ edges[index].verts[0].co
            ).length
            for index in (first_index, opposite_index)
        )
        pairs.append((length, first_index))
    rail_start = max(pairs)[1]
    return edges[rail_start], edges[rail_start + 2]


def selected_bevel_patch_descriptors(selected_faces, world_matrix):
    """Order selected bevel quads into independent cross-width patches."""
    selected_faces = list(selected_faces or ())
    selected_face_set = set(selected_faces)
    rails_by_face = {}
    for face in selected_faces:
        rails = selected_bevel_face_long_rails(face, world_matrix)
        if rails is None:
            return [], "Face generation currently requires quad faces."
        rails_by_face[face] = rails

    neighbors_by_face = {face: [] for face in selected_faces}
    for face, rails in rails_by_face.items():
        for rail in rails:
            neighbor = next(
                (
                    linked_face
                    for linked_face in rail.link_faces
                    if linked_face in selected_face_set and linked_face is not face
                ),
                None,
            )
            if neighbor is not None and neighbor not in neighbors_by_face[face]:
                neighbors_by_face[face].append(neighbor)
        if len(neighbors_by_face[face]) > 2:
            return [], "Selected bevel faces must form non-branching strips."

    descriptors = []
    unvisited = set(selected_faces)
    while unvisited:
        seed = next(iter(unvisited))
        component = set()
        pending = [seed]
        while pending:
            face = pending.pop()
            if face in component:
                continue
            component.add(face)
            unvisited.discard(face)
            pending.extend(neighbors_by_face[face])

        ends = [
            face for face in component
            if sum(neighbor in component for neighbor in neighbors_by_face[face]) <= 1
        ]
        if len(component) > 1 and len(ends) != 2:
            return [], "Selected bevel faces must form open cross-width strips."
        current = ends[0] if ends else next(iter(component))
        previous = None
        ordered_faces = []
        while current is not None:
            ordered_faces.append(current)
            candidates = [
                neighbor
                for neighbor in neighbors_by_face[current]
                if neighbor in component and neighbor is not previous
            ]
            next_face = candidates[0] if candidates else None
            previous, current = current, next_face
        if len(ordered_faces) != len(component):
            return [], "Could not order the selected bevel strip."

        first_rails = rails_by_face[ordered_faces[0]]
        if len(ordered_faces) == 1:
            ordered_rails = [first_rails[0], first_rails[1]]
        else:
            shared = next(
                rail
                for rail in first_rails
                if rail in rails_by_face[ordered_faces[1]]
            )
            ordered_rails = [
                next(rail for rail in first_rails if rail is not shared),
                shared,
            ]
            for face in ordered_faces[1:]:
                rails = rails_by_face[face]
                if ordered_rails[-1] not in rails:
                    return [], "Selected bevel rails do not form one strip."
                ordered_rails.append(
                    next(rail for rail in rails if rail is not ordered_rails[-1])
                )

        support_a = next(
            (
                face
                for face in ordered_rails[0].link_faces
                if face not in selected_face_set
            ),
            None,
        )
        support_b = next(
            (
                face
                for face in ordered_rails[-1].link_faces
                if face not in selected_face_set
            ),
            None,
        )
        if support_a is None or support_b is None:
            return [], (
                "The selected bevel strip needs a neighboring surface on both outer sides."
            )

        oriented_vertices = []
        first_vertices = list(ordered_rails[0].verts)
        oriented_vertices.append((first_vertices[0], first_vertices[1]))
        for rail in ordered_rails[1:]:
            vertex_a, vertex_b = rail.verts
            previous_start, previous_end = oriented_vertices[-1]
            direct_cost = (
                (world_matrix @ vertex_a.co - world_matrix @ previous_start.co).length
                + (world_matrix @ vertex_b.co - world_matrix @ previous_end.co).length
            )
            reversed_cost = (
                (world_matrix @ vertex_b.co - world_matrix @ previous_start.co).length
                + (world_matrix @ vertex_a.co - world_matrix @ previous_end.co).length
            )
            oriented_vertices.append(
                (vertex_a, vertex_b)
                if direct_cost <= reversed_cost
                else (vertex_b, vertex_a)
            )

        descriptors.append({
            "faces": ordered_faces,
            "rails": ordered_rails,
            "oriented_vertices": oriented_vertices,
            "support_a": support_a,
            "support_b": support_b,
        })
    return descriptors, None


def build_selected_face_centerline_bmesh(
    source_bm,
    selected_faces,
    world_matrix,
):
    """Build one temporary longitudinal path per selected bevel patch."""
    _ = source_bm
    descriptors, error = selected_bevel_patch_descriptors(
        selected_faces,
        world_matrix,
    )
    if error is not None:
        return None, [], {}, error
    if not descriptors:
        return None, [], {}, "Select at least one bevel face."

    generation_bm = bmesh.new()
    descriptor_by_edge = {}
    try:
        pending = []
        for descriptor in descriptors:
            oriented = descriptor["oriented_vertices"]
            start_local = (
                oriented[0][0].co + oriented[-1][0].co
            ) * 0.5
            end_local = (
                oriented[0][1].co + oriented[-1][1].co
            ) * 0.5
            center_start = generation_bm.verts.new(start_local)
            center_end = generation_bm.verts.new(end_local)
            side_a_start = generation_bm.verts.new(oriented[0][0].co.copy())
            side_a_end = generation_bm.verts.new(oriented[0][1].co.copy())
            side_b_start = generation_bm.verts.new(oriented[-1][0].co.copy())
            side_b_end = generation_bm.verts.new(oriented[-1][1].co.copy())
            generation_bm.faces.new((
                center_start,
                center_end,
                side_a_end,
                side_a_start,
            ))
            generation_bm.faces.new((
                center_end,
                center_start,
                side_b_start,
                side_b_end,
            ))
            pending.append((center_start, center_end, descriptor))

        generation_bm.normal_update()
        generation_bm.edges.ensure_lookup_table()
        generation_bm.faces.ensure_lookup_table()
        generation_bm.edges.index_update()
        center_edges = []
        for center_start, center_end, descriptor in pending:
            edge = generation_bm.edges.get((center_start, center_end))
            if edge is None or len(edge.link_faces) != 2:
                generation_bm.free()
                return None, [], {}, "Could not build a valid bevel path."
            center_edges.append(edge)
            descriptor_by_edge[edge] = descriptor
        return generation_bm, center_edges, descriptor_by_edge, None
    except (ValueError, RuntimeError) as error:
        generation_bm.free()
        return None, [], {}, f"Could not build the selected bevel path: {error}"


def build_selected_bevel_face_wrapped_strip(
    descriptor,
    world_matrix,
    normal_matrix,
    face_width,
    surface_offset,
    uv_scale,
    vertices_out,
    faces_out,
    face_uvs_out,
    center_vertices_out,
    slice_interval=None,
    taper_sliced_ends=True,
    slice_taper_length=0.0,
    longitudinal_station_cache=None,
):
    """Preserve a multi-face bevel patch and extend width onto both sides."""
    selected_faces = descriptor["faces"]
    rails = descriptor["rails"]
    oriented = descriptor["oriented_vertices"]
    support_a = descriptor["support_a"]
    support_b = descriptor["support_b"]
    selected_normals = [
        transform_normal(normal_matrix, face.normal)
        for face in selected_faces
    ]
    support_normal_a = transform_normal(normal_matrix, support_a.normal)
    support_normal_b = transform_normal(normal_matrix, support_b.normal)
    rail_starts = [world_matrix @ pair[0].co for pair in oriented]
    rail_ends = [world_matrix @ pair[1].co for pair in oriented]
    center_start_source = (rail_starts[0] + rail_starts[-1]) * 0.5
    center_end_source = (rail_ends[0] + rail_ends[-1]) * 0.5
    path_vector = center_end_source - center_start_source
    path_length = path_vector.length
    if path_length <= EPSILON:
        return 0
    tangent = path_vector / path_length
    inward_a = face_inward_direction(
        support_a,
        rails[0],
        world_matrix,
        normal_matrix,
        tangent,
    )
    inward_b = face_inward_direction(
        support_b,
        rails[-1],
        world_matrix,
        normal_matrix,
        tangent,
    )

    start_fraction, end_fraction = (0.0, 1.0)
    if slice_interval is not None:
        start_fraction = max(0.0, min(1.0, float(slice_interval[0])))
        end_fraction = max(0.0, min(1.0, float(slice_interval[1])))
        if end_fraction < start_fraction:
            start_fraction, end_fraction = end_fraction, start_fraction
    if end_fraction - start_fraction <= 1.0e-5:
        return 0

    taper_fraction = min(
        (end_fraction - start_fraction) * 0.49,
        max(0.0, float(slice_taper_length)) / path_length,
    )
    taper_start = bool(
        taper_sliced_ends
        and start_fraction > EPSILON
        and taper_fraction > EPSILON
    )
    taper_end = bool(
        taper_sliced_ends
        and end_fraction < 1.0 - EPSILON
        and taper_fraction > EPSILON
    )
    stations = [(start_fraction, 0.0 if taper_start else 1.0)]
    if taper_start:
        stations.append((start_fraction + taper_fraction, 1.0))
    if taper_end:
        shoulder = end_fraction - taper_fraction
        if shoulder > stations[-1][0] + EPSILON:
            stations.append((shoulder, 1.0))
    stations.append((end_fraction, 0.0 if taper_end else 1.0))

    center_cross_index = None

    def full_cross_section(factor):
        nonlocal center_cross_index
        source_rail_points = [
            start.lerp(end, factor)
            for start, end in zip(rail_starts, rail_ends)
        ]
        offset_rails = []
        for index, point in enumerate(source_rail_points):
            if index == 0:
                normals = (support_normal_a, selected_normals[0])
            elif index == len(source_rail_points) - 1:
                normals = (selected_normals[-1], support_normal_b)
            else:
                normals = (
                    selected_normals[index - 1],
                    selected_normals[index],
                )
            offset_rails.append(
                offset_point_from_face_normals(point, normals, surface_offset)
            )
        cross_section = [
            offset_rails[0] + inward_a * face_width,
            *offset_rails,
            offset_rails[-1] + inward_b * face_width,
        ]
        face_count = len(selected_faces)
        if face_count % 2 == 1:
            middle_face = face_count // 2
            insert_at = middle_face + 2
            center = (
                offset_rails[middle_face]
                + offset_rails[middle_face + 1]
            ) * 0.5
            cross_section.insert(insert_at, center)
            center_cross_index = insert_at
        else:
            center_cross_index = 1 + face_count // 2
        return cross_section

    station_records = []
    base_v_values = None
    for factor, scale in stations:
        cross_section = full_cross_section(factor)
        center = cross_section[center_cross_index]
        if base_v_values is None:
            distances = [0.0]
            for point_a, point_b in zip(cross_section, cross_section[1:]):
                distances.append(distances[-1] + (point_b - point_a).length)
            total_cross = max(distances[-1], EPSILON)
            base_v_values = [distance / total_cross for distance in distances]
        u = factor * path_length * uv_scale
        if scale <= EPSILON:
            index = len(vertices_out)
            vertices_out.append(center)
            center_vertices_out.append(index)
            station_records.append({
                "indices": [index] * len(cross_section),
                "collapsed": True,
                "u": u,
            })
            continue
        final_cross_section = [
            center + (point - center) * scale
            for point in cross_section
        ]
        source_order = None
        if longitudinal_station_cache is not None:
            if abs(factor) <= EPSILON:
                source_order = tuple(pair[0].index for pair in oriented)
            elif abs(factor - 1.0) <= EPSILON:
                source_order = tuple(pair[1].index for pair in oriented)

        indices = None
        if source_order is not None:
            station_key = tuple(sorted(source_order))
            cached = longitudinal_station_cache.get(station_key)
            if cached is not None:
                cached_indices = tuple(cached["indices"])
                cached_order = tuple(cached["source_order"])
                if source_order == cached_order:
                    indices = list(cached_indices)
                elif source_order == tuple(reversed(cached_order)):
                    indices = list(reversed(cached_indices))
                if indices is not None and len(indices) == len(final_cross_section):
                    previous_count = int(cached.get("count", 1))
                    inverse_count = 1.0 / float(previous_count + 1)
                    for index, point in zip(indices, final_cross_section):
                        vertices_out[index] = (
                            vertices_out[index] * previous_count + point
                        ) * inverse_count
                    cached["count"] = previous_count + 1
                else:
                    indices = None

        if indices is None:
            indices = []
            for point in final_cross_section:
                index = len(vertices_out)
                vertices_out.append(point)
                indices.append(index)
            if source_order is not None:
                longitudinal_station_cache[tuple(sorted(source_order))] = {
                    "source_order": source_order,
                    "indices": tuple(indices),
                    "count": 1,
                }

        center_vertex_index = indices[center_cross_index]
        if center_vertex_index not in center_vertices_out:
            center_vertices_out.append(center_vertex_index)
        station_records.append({
            "indices": indices,
            "collapsed": False,
            "u": u,
        })

    created = 0
    band_count = len(base_v_values) - 1
    band_normals = [
        support_normal_a,
        *selected_normals,
        support_normal_b,
    ]
    if len(selected_faces) % 2 == 1:
        middle_face = len(selected_faces) // 2
        band_normals.insert(
            middle_face + 1,
            selected_normals[middle_face],
        )
    for start_record, end_record in zip(station_records, station_records[1:]):
        start_indices = start_record["indices"]
        end_indices = end_record["indices"]
        for band_index in range(band_count):
            if start_record["collapsed"]:
                face = (
                    start_indices[0],
                    end_indices[band_index + 1],
                    end_indices[band_index],
                )
                uvs = (
                    Vector((start_record["u"], base_v_values[center_cross_index])),
                    Vector((end_record["u"], base_v_values[band_index + 1])),
                    Vector((end_record["u"], base_v_values[band_index])),
                )
            elif end_record["collapsed"]:
                face = (
                    start_indices[band_index],
                    start_indices[band_index + 1],
                    end_indices[0],
                )
                uvs = (
                    Vector((start_record["u"], base_v_values[band_index])),
                    Vector((start_record["u"], base_v_values[band_index + 1])),
                    Vector((end_record["u"], base_v_values[center_cross_index])),
                )
            else:
                face = (
                    start_indices[band_index],
                    start_indices[band_index + 1],
                    end_indices[band_index + 1],
                    end_indices[band_index],
                )
                uvs = (
                    Vector((start_record["u"], base_v_values[band_index])),
                    Vector((start_record["u"], base_v_values[band_index + 1])),
                    Vector((end_record["u"], base_v_values[band_index + 1])),
                    Vector((end_record["u"], base_v_values[band_index])),
                )
            face, uvs = oriented_face_with_uvs(
                face,
                uvs,
                vertices_out,
                band_normals[band_index],
            )
            faces_out.append(face)
            face_uvs_out.append(uvs)
            created += 1
    return created


class EDGEDECAL_OT_generate(Operator):
    bl_idname = "mesh.generate_edge_decal_strips"
    bl_label = "Generate Beveled Edge Decal"
    bl_description = (
        "Create an edge decal and adjust Face Width and Surface Offset "
        "interactively from Blender's Adjust Last Operation panel"
    )
    bl_options = {"REGISTER", "UNDO"}

    randomize_horizontal_offset: BoolProperty(
        name="Random Horizontal Offset",
        default=True,
        description="Give every generated UV island a distinct randomized U position",
    )

    horizontal_randomize_amount: FloatProperty(
        name="Horizontal Randomize Amount",
        default=1.0,
        min=0.0,
        soft_max=500.0,
        description="Total U-space span used to separate randomized UV islands",
    )

    seed: IntProperty(
        name="Seed",
        default=1,
        min=0,
        soft_max=1000,
        description=(
            "Controls independently mixed per-path cuts and random UV placement"
        ),
    )

    uv_scale: FloatProperty(
        name="UV Scale",
        default=1.0,
        min=0.01,
        soft_min=0.1,
        soft_max=10.0,
        precision=3,
        description="Interactive multiplier for the generated UV islands",
    )

    face_width: FloatProperty(
        name="Face Width",
        default=0.01,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        description="Relative decal width; with Relative Width enabled, 0.01 means 1% of the source object's largest dimension",
    )

    randomize_face_width: BoolProperty(
        name="Random Width",
        default=False,
        description="Choose a repeatable random width for each disconnected decal path",
    )

    minimum_face_width: FloatProperty(
        name="Minimum Width",
        default=0.005,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        precision=6,
    )

    maximum_face_width: FloatProperty(
        name="Maximum Width",
        default=0.02,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        precision=6,
    )

    crevice_removal: FloatProperty(
        name="Crevice Removal",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Reduce decals on inward concave/crevice edges",
    )

    crevice_detection_mode: EnumProperty(
        name="Crevice Detection",
        items=CREVICE_DETECTION_ITEMS,
        default="AO",
    )

    crevice_ao_distance: FloatProperty(
        name="AO Distance",
        default=0.0,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
        description="Zero automatically uses four times Face Width",
    )

    crevice_ao_samples: IntProperty(
        name="AO Samples",
        default=8,
        min=4,
        max=32,
    )


    remove_short_edges: BoolProperty(
        name="Remove Short Edges",
        default=False,
        description="Ignore edges shorter than the minimum length",
    )

    minimum_edge_length: FloatProperty(
        name="Minimum Edge Length",
        default=0.05,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
        description="World-space minimum length for eligible decal edges",
    )

    minimum_length_per_edge: BoolProperty(
        name="Measure Each Edge Separately",
        default=False,
        options={"HIDDEN"},
        description=(
            "Automatic mode filters individual source edges; manual mode "
            "filters the total connected selected chain"
        ),
    )

    decal_amount: FloatProperty(
        name="Decal Amount",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description=(
            "Controls total coverage and automatic chain shortening intensity"
        ),
    )

    edge_slice: FloatProperty(
        name="Legacy Edge Slice",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        options={"HIDDEN"},
        description="Legacy compatibility value; Decal Amount now continuously controls slicing",
    )


    interactive_slice_start: FloatProperty(
        name="Interactive Slice Start",
        default=-1.0,
        min=-1.0,
        max=1.0,
        options={"HIDDEN"},
        description="Internal partial-edge start fraction used by Interactive Generate",
    )

    interactive_slice_end: FloatProperty(
        name="Interactive Slice End",
        default=-1.0,
        min=-1.0,
        max=1.0,
        options={"HIDDEN"},
        description="Internal partial-edge end fraction used by Interactive Generate",
    )


    interactive_detect_endpoint_taper: BoolProperty(
        name="Interactive Endpoint Taper",
        default=False,
        options={"HIDDEN"},
        description="Internal interactive mode flag: taper only visually exposed endpoints on full selected edges",
    )

    interactive_force_endpoint_taper: BoolProperty(
        name="Interactive Force Endpoint Taper",
        default=False,
        options={"HIDDEN"},
        description="Internal interactive mode flag: taper every open endpoint on newly placed edges",
    )

    interactive_merge_taper_start: BoolProperty(
        name="Interactive Merge Taper Start",
        default=False,
        options={"HIDDEN"},
        description="Internal interactive flag: taper the open start of a merged chain",
    )

    interactive_merge_taper_end: BoolProperty(
        name="Interactive Merge Taper End",
        default=False,
        options={"HIDDEN"},
        description="Internal interactive flag: taper the open end of a merged chain",
    )

    interactive_skip_limited_dissolve: BoolProperty(
        name="Interactive Skip Limited Dissolve",
        default=False,
        options={"HIDDEN"},
        description="Internal interactive flag: generate from unchanged source topology",
    )

    generate_selected_edge_graph: BoolProperty(
        name="Generate Selected Edge Graph",
        default=False,
        options={"HIDDEN"},
        description=(
            "Build all selected full edges in one branch-aware topology pass"
        ),
    )

    generate_from_selected_faces: BoolProperty(
        name="Generate From Selected Faces",
        default=False,
        options={"HIDDEN"},
        description="Use selected quad faces as virtual center paths",
    )

    maximum_decal_length: FloatProperty(
        name="Maximum Decal Length",
        default=0.0,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
        description="Maximum continuous decal length; zero disables the limit",
    )

    taper_sliced_ends: BoolProperty(
        name="Taper Sliced Ends",
        default=True,
        description="Taper endpoints created by Decal Amount slicing",
    )

    slice_taper_length: FloatProperty(
        name="Taper Length",
        default=0.24,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
        description="Distance from a sliced tip to full decal width",
    )

    auto_trim_corner_ends: BoolProperty(
        name="Auto Trim Tight Corner Ends",
        default=True,
    )

    corner_end_trim_multiplier: FloatProperty(
        name="Corner Trim Multiplier",
        default=1.0,
        min=0.0,
        soft_max=3.0,
    )

    auto_width_samples: IntProperty(
        name="Auto Width Samples",
        default=1,
        min=1,
        max=5,
        description="Lower is faster; higher is more accurate",
    )

    auto_face_width: BoolProperty(
        name="Auto Face Width",
        default=False,
        description=(
            "Automatically clamp the width per edge side to nearby surface edges"
        ),
    )

    auto_width_clearance: FloatProperty(
        name="Width Clearance",
        default=0.85,
        min=0.05,
        max=0.99,
        subtype="FACTOR",
        description="Fraction of detected free space used by the decal",
    )

    clamp_edge_overlaps: BoolProperty(
        name="Clamp Edge Overlaps",
        default=True,
        description=(
            "Build a connected curve-graph strip and locally reduce its width "
            "before selected decal paths overlap"
        ),
    )

    overlap_clearance: FloatProperty(
        name="Overlap Clearance",
        default=0.98,
        min=0.5,
        max=0.999,
        subtype="FACTOR",
        description="Fraction of the shared gap used by opposing strips",
    )

    use_face_loop_slide: BoolProperty(
        name="Follow Connected Face Edges",
        default=True,
        description=(
            "At safe open endpoints, follow a connected support-face edge. "
            "Corners and junctions continue using the bounded miter solver"
        ),
    )

    fast_geometry_only: BoolProperty(
        name="Fast Geometry Only",
        default=False,
        description="Skip expensive final UV processing",
    )

    add_weld_modifier: BoolProperty(
        name="Add Weld Modifier",
        default=False,
    )

    add_bevel_modifier: BoolProperty(
        name="Add Bevel Modifier",
        default=False,
    )

    surface_offset: FloatProperty(
        name="Surface Offset",
        default=0.002,
        min=0.0,
        soft_max=0.05,
        unit="LENGTH",
        description="Interactive distance above the source surface",
    )

    def invoke(self, context, event):
        settings = context.scene.edge_decal_settings
        sync_decal_bevel_from_source(context.edit_object, settings)
        self.face_width = settings.face_width
        self.randomize_face_width = settings.randomize_face_width
        self.minimum_face_width = settings.minimum_face_width
        self.maximum_face_width = settings.maximum_face_width
        self.crevice_removal = settings.crevice_removal
        self.crevice_detection_mode = settings.crevice_detection_mode
        self.crevice_ao_distance = settings.crevice_ao_distance
        self.crevice_ao_samples = settings.crevice_ao_samples
        self.remove_short_edges = settings.remove_short_edges
        self.minimum_edge_length = settings.minimum_edge_length
        self.minimum_length_per_edge = False
        self.decal_amount = settings.decal_amount
        self.edge_slice = settings.edge_slice
        self.maximum_decal_length = settings.maximum_decal_length
        self.taper_sliced_ends = settings.taper_sliced_ends
        self.slice_taper_length = settings.slice_taper_length
        self.auto_trim_corner_ends = settings.auto_trim_corner_ends
        self.corner_end_trim_multiplier = settings.corner_end_trim_multiplier
        self.randomize_horizontal_offset = settings.randomize_horizontal_offset
        self.horizontal_randomize_amount = settings.horizontal_randomize_amount
        self.seed = settings.seed
        self.uv_scale = settings.uv_scale
        self.auto_face_width = settings.auto_face_width
        self.auto_width_samples = settings.auto_width_samples
        self.auto_width_clearance = settings.auto_width_clearance
        self.clamp_edge_overlaps = settings.clamp_edge_overlaps
        self.overlap_clearance = settings.overlap_clearance
        self.use_face_loop_slide = settings.use_face_loop_slide
        self.fast_geometry_only = settings.fast_geometry_only
        self.add_weld_modifier = settings.add_weld_modifier
        self.add_bevel_modifier = settings.add_bevel_modifier
        self.surface_offset = settings.surface_offset
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        width = layout.row()
        width.enabled = not self.randomize_face_width
        width.prop(self, "face_width")
        layout.prop(self, "randomize_face_width", toggle=True)
        random_bounds = layout.column(align=True)
        random_bounds.enabled = self.randomize_face_width
        random_bounds.prop(self, "minimum_face_width")
        random_bounds.prop(self, "maximum_face_width")
        layout.prop(self, "use_face_loop_slide")
        layout.prop(self, "crevice_removal")

        crevice_options = layout.column(align=True)
        crevice_options.enabled = self.crevice_removal > 0.0
        crevice_options.prop(self, "crevice_detection_mode")

        ao_options = crevice_options.column(align=True)
        ao_options.enabled = self.crevice_detection_mode == "AO"
        ao_options.prop(self, "crevice_ao_distance")
        ao_options.prop(self, "crevice_ao_samples")

        layout.prop(self, "remove_short_edges")

        min_length_row = layout.row()
        min_length_row.enabled = self.remove_short_edges
        min_length_row.prop(self, "minimum_edge_length")

        layout.prop(self, "decal_amount")
        layout.prop(self, "maximum_decal_length")
        layout.prop(self, "taper_sliced_ends")
        taper_row = layout.row()
        taper_row.enabled = self.taper_sliced_ends
        taper_row.prop(self, "slice_taper_length")
        layout.prop(self, "auto_trim_corner_ends")
        trim_row = layout.row()
        trim_row.enabled = self.auto_trim_corner_ends
        trim_row.prop(self, "corner_end_trim_multiplier")
        layout.prop(self, "uv_scale")
        layout.prop(self, "randomize_horizontal_offset")
        amount_row = layout.row()
        amount_row.enabled = self.randomize_horizontal_offset
        amount_row.prop(self, "horizontal_randomize_amount")
        layout.prop(self, "seed")
        layout.prop(self, "auto_face_width")
        layout.prop(self, "clamp_edge_overlaps")

        samples_row = layout.row()
        samples_row.enabled = (
            self.auto_face_width or self.clamp_edge_overlaps
        )
        samples_row.prop(self, "auto_width_samples")

        clearance_row = layout.row()
        clearance_row.enabled = self.auto_face_width
        clearance_row.prop(self, "auto_width_clearance")

        overlap_row = layout.row()
        overlap_row.enabled = self.clamp_edge_overlaps
        overlap_row.prop(self, "overlap_clearance")

        layout.prop(self, "surface_offset")
        layout.prop(self, "fast_geometry_only")
        layout.prop(self, "add_weld_modifier")
        layout.prop(self, "add_bevel_modifier")

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "EDIT_MESH"
            and context.edit_object is not None
            and context.edit_object.type == "MESH"
        )

    def execute(self, context):
        source_obj = context.edit_object
        ensure_source_decal_layers_ready(source_obj, context)
        settings = context.scene.edge_decal_settings
        sync_decal_bevel_from_source(source_obj, settings)

        # Store the latest interactive values as the defaults for the next run.
        settings.face_width = self.face_width
        settings.randomize_face_width = self.randomize_face_width
        settings.minimum_face_width = self.minimum_face_width
        settings.maximum_face_width = self.maximum_face_width
        settings.crevice_removal = self.crevice_removal
        settings.crevice_detection_mode = self.crevice_detection_mode
        settings.crevice_ao_distance = self.crevice_ao_distance
        settings.crevice_ao_samples = self.crevice_ao_samples
        settings.remove_short_edges = self.remove_short_edges
        settings.minimum_edge_length = self.minimum_edge_length
        settings.decal_amount = self.decal_amount
        settings.edge_slice = self.edge_slice
        settings.maximum_decal_length = self.maximum_decal_length
        settings.taper_sliced_ends = self.taper_sliced_ends
        settings.slice_taper_length = self.slice_taper_length
        settings.auto_trim_corner_ends = self.auto_trim_corner_ends
        settings.corner_end_trim_multiplier = self.corner_end_trim_multiplier
        settings.randomize_horizontal_offset = self.randomize_horizontal_offset
        settings.horizontal_randomize_amount = self.horizontal_randomize_amount
        settings.seed = self.seed
        settings.uv_scale = self.uv_scale
        settings.auto_face_width = self.auto_face_width
        settings.auto_width_samples = self.auto_width_samples
        settings.auto_width_clearance = self.auto_width_clearance
        settings.clamp_edge_overlaps = self.clamp_edge_overlaps
        settings.overlap_clearance = self.overlap_clearance
        settings.use_face_loop_slide = self.use_face_loop_slide
        settings.fast_geometry_only = self.fast_geometry_only
        settings.add_weld_modifier = self.add_weld_modifier
        self.add_bevel_modifier = bool(
            not self.generate_from_selected_faces
            and (
                self.add_bevel_modifier
                or source_bevel_settings(source_obj) is not None
            )
        )
        settings.add_bevel_modifier = self.add_bevel_modifier
        settings.surface_offset = self.surface_offset

        source_bm = bmesh.from_edit_mesh(source_obj.data)
        source_bm.normal_update()
        source_bm.verts.ensure_lookup_table()
        source_bm.edges.ensure_lookup_table()
        source_bm.faces.ensure_lookup_table()
        source_bm.edges.index_update()
        source_bm.faces.index_update()

        world_matrix = source_obj.matrix_world.copy()

        try:
            normal_matrix = world_matrix.to_3x3().inverted().transposed()
        except ValueError:
            self.report(
                {"ERROR"},
                "The source object has a non-invertible transform. Check for zero scale.",
            )
            return {"CANCELLED"}

        generate_from_selected_faces = bool(self.generate_from_selected_faces)
        face_source_count = 0
        face_generation_bm = None
        face_generation_edges = []
        face_generation_descriptor_by_edge = {}
        if generate_from_selected_faces:
            source_selected_faces = [
                face
                for face in source_bm.faces
                if face.select and not face.hide
            ]
            (
                face_generation_bm,
                face_generation_edges,
                face_generation_descriptor_by_edge,
                face_generation_error,
            ) = build_selected_face_centerline_bmesh(
                source_bm,
                source_selected_faces,
                world_matrix,
            )
            if face_generation_error is not None:
                self.report({"ERROR"}, face_generation_error)
                return {"CANCELLED"}
            source_selected_edge_indices = [
                face.index for face in source_selected_faces
            ]
            source_manifold_edges = face_generation_edges
            face_source_count = len(source_selected_faces)
            skipped_count = 0
            generation_selected_edge_indices = set()
            mask_layer = None
            mask_status = "DISABLED"
        else:
            source_selected_edges = [
                edge
                for edge in source_bm.edges
                if edge.select and not edge.hide
            ]
            if not source_selected_edges:
                self.report({"ERROR"}, "Select at least one edge.")
                return {"CANCELLED"}
            source_selected_edge_indices = [
                edge.index for edge in source_selected_edges
            ]
            source_manifold_edges = [
                edge
                for edge in source_selected_edges
                if len(edge.link_faces) == 2
            ]
            skipped_count = (
                len(source_selected_edges) - len(source_manifold_edges)
            )
            if not source_manifold_edges:
                self.report(
                    {"ERROR"},
                    "Selected edges must each have exactly two linked faces.",
                )
                return {"CANCELLED"}
            generation_selected_edge_indices = set(
                source_selected_edge_indices
            )
            mask_layer = generation_mask_layer(source_obj, context=context)
            mask_status = generation_mask_status(
                source_bm,
                mask_layer,
            )
        if mask_status == "NO_UV":
            self.report(
                {"ERROR"},
                "The layer mask needs an active UV map on the source mesh.",
            )
            return {"CANCELLED"}
        if mask_status == "MISSING":
            self.report(
                {"ERROR"},
                "The layer mask is enabled but its image is missing.",
            )
            return {"CANCELLED"}
        interactive_endpoint_taper_requested = bool(
            self.interactive_force_endpoint_taper
            or self.interactive_merge_taper_start
            or self.interactive_merge_taper_end
        )
        selected_vertex_degrees = {}
        for edge in source_manifold_edges:
            for vertex in edge.verts:
                selected_vertex_degrees[vertex] = (
                    selected_vertex_degrees.get(vertex, 0) + 1
                )
        selected_graph_has_branch = any(
            degree > 2 for degree in selected_vertex_degrees.values()
        )
        selected_graph_has_open_end = any(
            degree == 1 for degree in selected_vertex_degrees.values()
        )
        taper_aware_chain_builder_required = bool(
            interactive_endpoint_taper_requested
            and selected_graph_has_open_end
            and not selected_graph_has_branch
        )
        selected_graph_topology_requested = bool(
            self.generate_selected_edge_graph
            and self.maximum_decal_length <= EPSILON
            and self.interactive_slice_start < 0.0
            and self.interactive_slice_end < 0.0
            # The graph builder authors branch-safe shared junctions, but it
            # does not insert taper shoulders. An open, non-branching merged
            # run is an ordered chain, so keep it on the taper-aware strip
            # builder whenever Interactive asks to preserve endpoint tapers.
            and not taper_aware_chain_builder_required
        )
        use_selected_graph_builder = bool(
            not generate_from_selected_faces
            and selected_graph_topology_requested
            and self.decal_amount >= 1.0 - EPSILON
        )
        apply_generation_limited_dissolve = bool(
            not self.interactive_skip_limited_dissolve
            and not use_selected_graph_builder
        )
        use_prepared_source_cache = not generate_from_selected_faces
        source_cache_key = (
            prepared_source_cache_key(
                source_obj,
                apply_limited_dissolve=apply_generation_limited_dissolve,
            )
            if use_prepared_source_cache
            else None
        )
        if generate_from_selected_faces:
            bm = face_generation_bm
            original_index_by_edge = {}
            support_edges_dissolved = 0
            selected_edges = list(face_generation_edges)
        else:
            bm, original_index_by_edge = (
                build_limited_dissolve_generation_bmesh(
                    source_bm,
                    apply_limited_dissolve=apply_generation_limited_dissolve,
                    cache_source=source_obj,
                    use_cache=use_prepared_source_cache,
                )
            )
            support_edges_dissolved = max(
                0,
                len(source_bm.edges) - len(bm.edges),
            )
            selected_edges = [
                edge
                for edge in bm.edges
                if (
                    original_index_by_edge.get(edge)
                    in generation_selected_edge_indices
                    and not edge.hide
                )
            ]
        manifold_candidates = [
            edge for edge in selected_edges
            if (
                len(edge.link_faces) == 2
            )
        ]
        mask_split_stats = {
            "cut_count": 0,
            "partial_edge_count": 0,
            "cut_vertex_indices": set(),
        }
        if mask_status == "READY":
            (
                manifold_edges,
                mask_split_stats,
            ) = split_bmesh_edges_by_generation_mask(
                bm,
                manifold_candidates,
                mask_layer,
            )
            # Edge subdivision changes BMesh indices, so cached chain records
            # from the unsplit prepared source must not be reused.
            source_cache_key = None
            if mask_split_stats["cut_count"]:
                # The graph builder intentionally keeps source endpoints full
                # width. Mask-created endpoints need the Decal Amount taper
                # path, so use ordered open chains whenever the mask made cuts.
                use_selected_graph_builder = False
        else:
            manifold_edges = manifold_candidates

        if not manifold_edges:
            bm.free()
            if mask_status == "READY":
                self.report(
                    {"WARNING"},
                    "The layer mask is black over every selected edge. Paint white where decals may generate.",
                )
            else:
                self.report(
                    {"ERROR"},
                    "Whole-mesh Limited Dissolve left no eligible selected manifold edges.",
                )
            return {"CANCELLED"}

        original_manifold_count = len(manifold_edges)
        crevice_removed_count = 0
        short_removed_count = 0

        if self.crevice_removal > 0.0 and not generate_from_selected_faces:
            before_crevice_filter = len(manifold_edges)
            crevice_bvh = (
                build_world_bvh_from_bmesh(
                    bm,
                    world_matrix,
                )
                if self.crevice_detection_mode == "AO"
                else None
            )
            manifold_edges = filter_edges_by_crevice(
                manifold_edges,
                self.crevice_removal,
                world_matrix,
                normal_matrix,
                self.crevice_detection_mode,
                crevice_bvh,
                self.crevice_ao_distance,
                self.crevice_ao_samples,
                self.face_width,
                self.surface_offset,
            )
            crevice_removed_count = before_crevice_filter - len(manifold_edges)

        if not manifold_edges:
            bm.free()
            self.report(
                {"WARNING"},
                "Crevice Removal excluded every eligible edge.",
            )
            return {"CANCELLED"}

        if self.remove_short_edges:
            before_short_filter = len(manifold_edges)
            if self.minimum_length_per_edge:
                manifold_edges = filter_edges_by_minimum_length(
                    manifold_edges,
                    world_matrix,
                    self.minimum_edge_length,
                )
            else:
                manifold_edges = filter_edge_chains_by_minimum_length(
                    manifold_edges,
                    world_matrix,
                    self.minimum_edge_length,
                )
            short_removed_count = before_short_filter - len(manifold_edges)

        if not manifold_edges:
            bm.free()
            self.report(
                {"WARNING"},
                "Every eligible edge was shorter than the minimum length.",
            )
            return {"CANCELLED"}

        pin_target_layer = resolve_generation_target_layer(
            source_obj,
            context=context,
            include_locked=False,
        )
        pins = uv_pins_for_decal_layer_material(
            context.scene,
            pin_target_layer,
            fallback_material=(
                (
                    settings.decal_material
                    or bpy.data.materials.get(DEFAULT_MATERIAL_NAME)
                )
                if getattr(settings, "use_material", True)
                else None
            ),
        )
        all_source_edges = list(bm.edges)
        width_reference_edges = (
            list(source_bm.edges)
            if generate_from_selected_faces
            else all_source_edges
        )
        resolved_face_width = resolve_relative_face_width(
            self.face_width,
            width_reference_edges,
            world_matrix,
        )
        use_per_pin_slice_cuts = bool(
            self.decal_amount < 1.0 - EPSILON
            or self.maximum_decal_length > EPSILON
        )

        if use_per_pin_slice_cuts:
            source_chains = extract_cached_edge_chains_by_surface_bend(
                bm,
                manifold_edges,
                world_matrix,
                normal_matrix,
                cache_key=source_cache_key,
            )
            minimum_fragment_length = max(
                self.minimum_edge_length if self.remove_short_edges else 0.0,
                resolved_face_width * 4.0,
            )
            selected_chain_records = select_chains_by_global_amount(
                source_chains,
                self.decal_amount,
                self.seed,
                world_matrix,
                pins,
                minimum_fragment_length,
                0.0,
                self.maximum_decal_length,
                pin_target_layer,
                minimum_gap_length=resolved_face_width * 2.0,
            )
            kept_edge_set = {
                edge
                for record in selected_chain_records
                for edge in record["edges"]
            }
            amount_removed_count = len(manifold_edges) - len(kept_edge_set)
            manifold_edges = [
                edge for edge in manifold_edges if edge in kept_edge_set
            ]
        else:
            before_amount_filter = len(manifold_edges)
            manifold_edges = filter_edges_by_amount(
                manifold_edges,
                self.decal_amount,
                self.seed,
            )
            amount_removed_count = before_amount_filter - len(manifold_edges)
            selected_chain_records = [
                {
                    "verts": verts,
                    "edges": edges,
                    "closed": closed,
                    "amount": 1.0,
                    "pin_index": pin_index_for_layer_cycle(
                        index,
                        pins,
                        pin_target_layer,
                        self.seed,
                    ),
                    "source_index": index,
                }
                for index, (verts, edges, closed) in enumerate(
                    extract_cached_edge_chains_by_surface_bend(
                        bm,
                        manifold_edges,
                        world_matrix,
                        normal_matrix,
                        cache_key=source_cache_key,
                    )
                )
            ]

        if not manifold_edges or not selected_chain_records:
            bm.free()
            self.report(
                {"WARNING"},
                "Decal Amount removed every remaining eligible chain.",
            )
            return {"CANCELLED"}

        chains = []
        for record in selected_chain_records:
            chain_verts = record["verts"]
            chain_edges = record["edges"]
            closed = record["closed"]
            local_amount = record["amount"]
            pin_index = record["pin_index"]
            record_slice_interval = record.get("slice_interval")
            # The one partially retained boundary chain stays intact until its
            # slice interval is resolved. Fully retained chains may still use
            # the normal angle-based island split.
            if (
                settings.use_edge_split
                and local_amount >= 1.0 - EPSILON
                and record_slice_interval is None
            ):
                for split_verts, split_edges, split_closed in split_chain_by_angle(
                    chain_verts,
                    chain_edges,
                    closed,
                    world_matrix,
                    settings.split_angle,
                ):
                    chains.append((
                        split_verts, split_edges, split_closed, 1.0, pin_index,
                        None,
                    ))
            else:
                chains.append((
                    chain_verts, chain_edges, closed, local_amount, pin_index,
                    record_slice_interval,
                ))

        generated_vertices = []
        generated_faces = []
        generated_uvs = []
        generated_center_vertices = []
        created_face_count = 0
        selected_edge_set = set(manifold_edges)
        mask_cut_vertex_indices = set(
            mask_split_stats.get("cut_vertex_indices", ())
        )
        if self.randomize_face_width:
            random_width_minimum, random_width_maximum = (
                resolve_random_face_width_bounds(
                    self.minimum_face_width,
                    self.maximum_face_width,
                    width_reference_edges,
                    world_matrix,
                )
            )
        else:
            random_width_minimum = resolved_face_width
            random_width_maximum = resolved_face_width
        width_search_context = build_adaptive_width_search_context(
            all_source_edges,
            selected_edge_set,
            world_matrix,
            clamp_boundaries=self.auto_face_width,
            clamp_selected_overlaps=self.clamp_edge_overlaps,
            search_radius=max(random_width_maximum * 4.0, 1.0e-4),
        )
        # Strip extraction can split a selected pole into multiple chains.
        # Keep one shared center and one face-local outer vertex per junction
        # so those chains form a single authored topology instead of overlapping
        # caps or triangular bridge flaps.
        junction_vertex_cache = {}
        surface_voronoi_used = False
        curve_local_width_used = bool(
            use_selected_graph_builder and self.clamp_edge_overlaps
        )
        if generate_from_selected_faces:
            face_longitudinal_station_cache = {}
            for record in selected_chain_records:
                record_edges = list(record.get("edges", ()))
                record_verts = list(record.get("verts", ()))
                if not record_edges or len(record_verts) < 2:
                    continue
                record_width = resolved_face_width
                if self.randomize_face_width:
                    record_width = randomized_face_width(
                        random_width_minimum,
                        random_width_maximum,
                        self.seed,
                        chain_random_signature(
                            record_verts,
                            record_edges,
                            world_matrix,
                        ),
                    )
                edge_lengths = [
                    (
                        world_matrix @ record_verts[index + 1].co
                        - world_matrix @ record_verts[index].co
                    ).length
                    for index in range(len(record_edges))
                ]
                total_length = sum(edge_lengths)
                if total_length <= EPSILON:
                    continue
                record_interval = record.get("slice_interval") or (0.0, 1.0)
                record_start = max(0.0, min(1.0, float(record_interval[0])))
                record_end = max(0.0, min(1.0, float(record_interval[1])))
                if record_end < record_start:
                    record_start, record_end = record_end, record_start
                cursor = 0.0
                for edge, edge_length in zip(record_edges, edge_lengths):
                    segment_start = cursor / total_length
                    cursor += edge_length
                    segment_end = cursor / total_length
                    overlap_start = max(record_start, segment_start)
                    overlap_end = min(record_end, segment_end)
                    if overlap_end - overlap_start <= EPSILON:
                        continue
                    segment_span = max(segment_end - segment_start, EPSILON)
                    local_interval = (
                        (overlap_start - segment_start) / segment_span,
                        (overlap_end - segment_start) / segment_span,
                    )
                    descriptor = face_generation_descriptor_by_edge.get(edge)
                    if descriptor is None:
                        continue
                    created_face_count += build_selected_bevel_face_wrapped_strip(
                        descriptor=descriptor,
                        world_matrix=world_matrix,
                        normal_matrix=normal_matrix,
                        face_width=record_width,
                        surface_offset=self.surface_offset,
                        uv_scale=self.uv_scale,
                        vertices_out=generated_vertices,
                        faces_out=generated_faces,
                        face_uvs_out=generated_uvs,
                        center_vertices_out=generated_center_vertices,
                        slice_interval=local_interval,
                        taper_sliced_ends=self.taper_sliced_ends,
                        slice_taper_length=self.slice_taper_length,
                        longitudinal_station_cache=(
                            face_longitudinal_station_cache
                        ),
                    )
        elif use_selected_graph_builder:
            selected_graph_groups = partition_selected_edge_graph_by_angle(
                manifold_edges,
                world_matrix,
                settings.split_angle if settings.use_edge_split else pi,
            )
            face_width_by_edge = None
            if self.randomize_face_width:
                face_width_by_edge = randomized_face_widths_for_edge_groups(
                    selected_graph_groups,
                    random_width_minimum,
                    random_width_maximum,
                    self.seed,
                    world_matrix,
                )
            # Local-width decals are authored directly from the selected curve
            # graph. Source faces are used only for support normals and
            # projection; their triangulation never becomes output topology.
            # Every graph vertex and surface-sector miter has one logical mesh
            # vertex, so connectivity is established by construction rather
            # than repaired afterward with coordinate-based welding.
            created_face_count = build_partitioned_selected_edge_graph_strip(
                selected_edges=manifold_edges,
                edge_groups=selected_graph_groups,
                all_source_edges=all_source_edges,
                world_matrix=world_matrix,
                normal_matrix=normal_matrix,
                face_width=resolved_face_width,
                surface_offset=self.surface_offset,
                miter_limit=settings.miter_limit,
                vertices_out=generated_vertices,
                faces_out=generated_faces,
                face_uvs_out=generated_uvs,
                center_vertices_out=generated_center_vertices,
                auto_face_width=self.auto_face_width,
                auto_width_samples=self.auto_width_samples,
                auto_width_clearance=self.auto_width_clearance,
                clamp_edge_overlaps=self.clamp_edge_overlaps,
                overlap_clearance=self.overlap_clearance,
                width_search_context=width_search_context,
                face_width_resolved=True,
                uv_scale=self.uv_scale,
                face_width_by_edge=face_width_by_edge,
            )
        generated_island_count = (
            len(selected_chain_records)
            if generate_from_selected_faces
            else (
                len(selected_graph_groups)
                if use_selected_graph_builder
                else len(chains)
            )
        )
        for chain_index, (
            chain_verts, chain_edges, closed, local_amount, pin_index,
            amount_slice_interval,
        ) in enumerate(
            []
            if (use_selected_graph_builder or generate_from_selected_faces)
            else chains
        ):
            chain_slice_positions = []
            explicit_interval = (
                (self.interactive_slice_start, self.interactive_slice_end)
                if (
                    self.interactive_slice_start >= 0.0
                    and self.interactive_slice_end >= 0.0
                )
                else None
            )
            auto_corner_interval = None
            if self.auto_trim_corner_ends and explicit_interval is None:
                source_bevel = next(
                    (modifier for modifier in reversed(source_obj.modifiers) if modifier.type == "BEVEL"),
                    None,
                )
                source_bevel_width = float(getattr(source_bevel, "width", 0.0)) if source_bevel else 0.0
                auto_corner_interval = chain_endpoint_corner_trim_interval(
                    chain_verts,
                    chain_edges,
                    closed,
                    world_matrix,
                    source_bevel_width,
                    self.corner_end_trim_multiplier,
                )
            forced_interval = (
                explicit_interval
                or amount_slice_interval
                or auto_corner_interval
            )

            # Interactive partial-edge placement is an explicit geometry cut,
            # independent of the layer's global Decal Amount. Always taper the
            # cut endpoints, even when Decal Amount is 1.0 or the global taper
            # option is disabled. Original source endpoints remain square.
            explicit_interval_is_partial = bool(
                explicit_interval is not None
                and (
                    explicit_interval[0] > EPSILON
                    or explicit_interval[1] < 1.0 - EPSILON
                )
            )

            interactive_taper_start = False
            interactive_taper_end = False
            mask_taper_start = bool(
                self.taper_sliced_ends
                and not closed
                and chain_verts
                and int(chain_verts[0].index) in mask_cut_vertex_indices
            )
            mask_taper_end = bool(
                self.taper_sliced_ends
                and not closed
                and chain_verts
                and int(chain_verts[-1].index) in mask_cut_vertex_indices
            )
            if (
                self.interactive_force_endpoint_taper
                and explicit_interval is None
                and not closed
            ):
                interactive_taper_start = True
                interactive_taper_end = True
            elif (
                self.interactive_detect_endpoint_taper
                and explicit_interval is None
                and not closed
            ):
                (
                    interactive_taper_start,
                    interactive_taper_end,
                ) = interactive_endpoint_taper_flags(
                    chain_verts,
                    chain_edges,
                    selected_edge_set,
                    world_matrix,
                )

            if explicit_interval is None and not closed:
                if self.interactive_merge_taper_start:
                    interactive_taper_start = True
                if self.interactive_merge_taper_end:
                    interactive_taper_end = True

            interactive_taper_start = (
                interactive_taper_start or mask_taper_start
            )
            interactive_taper_end = interactive_taper_end or mask_taper_end

            # A genuine slice cut comes from Decal Amount / Maximum Decal Length
            # (an amount slice interval, or a per-chain amount below 1.0), as
            # opposed to the square Auto Trim Tight Corner Ends length
            # correction. Slice cuts must still taper (when Taper Sliced Ends is
            # enabled) even while Auto Trim is also active.
            has_amount_slice = bool(
                amount_slice_interval is not None
                or local_amount < 1.0 - EPSILON
            )

            if explicit_interval_is_partial:
                use_chain_taper = True
                strip_builder = build_corner_strip_tapered
            elif has_amount_slice:
                use_chain_taper = (
                    self.taper_sliced_ends
                    or interactive_taper_start
                    or interactive_taper_end
                )
                strip_builder = (
                    build_corner_strip_tapered
                    if use_chain_taper
                    else build_corner_strip
                )
            elif auto_corner_interval is not None and explicit_interval is None and not (interactive_taper_start or interactive_taper_end):
                # Auto tight-corner trim only: keep the trimmed ends square.
                strip_builder = build_corner_strip
                use_chain_taper = False
            else:
                use_chain_taper = (
                    self.taper_sliced_ends
                    or interactive_taper_start
                    or interactive_taper_end
                )
                strip_builder = (
                    build_corner_strip_tapered
                    if use_chain_taper
                    else build_corner_strip
                )
            chain_face_width = resolved_face_width
            if self.randomize_face_width:
                chain_face_width = randomized_face_width(
                    random_width_minimum,
                    random_width_maximum,
                    self.seed,
                    chain_random_signature(
                        chain_verts,
                        chain_edges,
                        world_matrix,
                    ),
                )
            created_face_count += strip_builder(
                chain_verts=chain_verts,
                chain_edges=chain_edges,
                closed=closed,
                selected_edge_set=selected_edge_set,
                all_source_edges=all_source_edges,
                world_matrix=world_matrix,
                normal_matrix=normal_matrix,
                face_width=chain_face_width,
                decal_amount=local_amount,
                slice_positions=chain_slice_positions,
                forced_slice_interval=forced_interval,
                taper_sliced_ends=use_chain_taper,
                force_taper_start=interactive_taper_start,
                force_taper_end=interactive_taper_end,
                slice_taper_length=self.slice_taper_length,
                auto_face_width=self.auto_face_width,
                auto_width_samples=self.auto_width_samples,
                auto_width_clearance=self.auto_width_clearance,
                clamp_edge_overlaps=self.clamp_edge_overlaps,
                overlap_clearance=self.overlap_clearance,
                surface_offset=self.surface_offset,
                miter_limit=settings.miter_limit,
                use_face_loop_slide=self.use_face_loop_slide,
                vertices_out=generated_vertices,
                faces_out=generated_faces,
                face_uvs_out=generated_uvs,
                center_vertices_out=generated_center_vertices,
                width_search_context=width_search_context,
                face_width_resolved=True,
                junction_vertex_cache=junction_vertex_cache,
            )
        if created_face_count == 0:
            bm.free()
            self.report({"ERROR"}, "No valid corner strip could be generated.")
            return {"CANCELLED"}

        bm.free()

        intended_layer = resolve_generation_target_layer(
            source_obj,
            include_locked=False,
            context=context,
        )

        decal_index = next_decal_index(source_obj)
        decal_base_name = f"{source_obj.name}_EdgeDecal_{decal_index:02d}"

        decal_mesh = bpy.data.meshes.new(f"{decal_base_name}_Mesh")
        decal_mesh.from_pydata(
            [tuple(vertex) for vertex in generated_vertices],
            [],
            generated_faces,
        )
        decal_mesh.update(calc_edges=True)

        decal_obj = bpy.data.objects.new(
            decal_base_name,
            decal_mesh,
        )
        configure_decal_object(
            decal_obj,
            source_obj=source_obj,
            scene=context.scene,
        )

        decal_obj.matrix_world = Matrix.Identity(4)

        # Parent the generated decal directly to the source mesh while
        # preserving the decal's exact world-space placement.
        decal_world_matrix = decal_obj.matrix_world.copy()
        decal_obj.parent = source_obj
        decal_obj.matrix_parent_inverse = (
            source_obj.matrix_world.inverted_safe()
        )
        decal_obj.matrix_world = decal_world_matrix

        center_group = decal_obj.vertex_groups.new(
            name="EdgeDecal_Center"
        )
        if generated_center_vertices:
            center_group.add(
                generated_center_vertices,
                1.0,
                "REPLACE",
            )

        decal_obj["edge_decal_generated"] = True
        decal_obj["edge_decal_source"] = source_obj.name_full
        decal_obj["edge_decal_index"] = decal_index
        register_fn = globals().get("register_decal_in_registry")
        if register_fn is not None:
            register_fn(decal_obj, source_obj)
        decal_obj["edge_decal_mode"] = (
            "FACE_SURFACES"
            if generate_from_selected_faces
            else "SHARP_EDGES"
        )
        # Persist the topology of the complete source selection, not the
        # builder used for this particular output. Decal Amount slicing must
        # temporarily use ordered chains, but later regeneration still needs
        # the unchanged source topology (and the graph builder again if the
        # amount returns to 1). Recording the sliced builder here caused the
        # next settings adjustment to enable Limited Dissolve and lose source
        # edge segments.
        decal_obj["edge_decal_selected_graph"] = bool(
            selected_graph_topology_requested
        )
        decal_obj["edge_decal_surface_voronoi"] = bool(
            surface_voronoi_used
        )
        decal_obj["edge_decal_surface_voronoi_revision"] = (
            13 if surface_voronoi_used else 0
        )
        decal_obj["edge_decal_curve_local_width"] = bool(
            curve_local_width_used
        )
        decal_obj["edge_decal_curve_local_width_revision"] = (
            1 if curve_local_width_used else 0
        )

        # Geometry now exists and will consume the selected preset material.
        # This is the first point where importing its material/images is valid.
        resolve_material = globals().get(
            "ensure_edge_decal_preset_material_for_use"
        )
        if resolve_material is not None and getattr(
            settings,
            "use_material",
            True,
        ):
            _material, asset_warnings, expected_material = resolve_material(
                context,
                settings,
            )
            if expected_material and _material is None:
                self.report(
                    {"WARNING"},
                    "Could not load preset assets: " + ", ".join(asset_warnings),
                )

        store_decal_settings(
            decal_obj,
            source_obj,
            (
                "SELECTED_FACES"
                if generate_from_selected_faces
                else "SELECTED_EDGES"
            ),
            source_selected_edge_indices,
            settings,
            {
                "face_width": self.face_width,
                "randomize_face_width": self.randomize_face_width,
                "minimum_face_width": self.minimum_face_width,
                "maximum_face_width": self.maximum_face_width,
                "surface_offset": self.surface_offset,
                "uv_scale": self.uv_scale,
                "seed": self.seed,
                "decal_amount": self.decal_amount,
                "taper_sliced_ends": self.taper_sliced_ends,
                "slice_taper_length": self.slice_taper_length,
                "auto_trim_corner_ends": self.auto_trim_corner_ends,
                "corner_end_trim_multiplier": self.corner_end_trim_multiplier,
                "crevice_removal": self.crevice_removal,
                "crevice_detection_mode": self.crevice_detection_mode,
                "crevice_ao_distance": self.crevice_ao_distance,
                "crevice_ao_samples": self.crevice_ao_samples,
                "remove_short_edges": self.remove_short_edges,
                "minimum_edge_length": self.minimum_edge_length,
                "minimum_length_per_edge": self.minimum_length_per_edge,
                "randomize_horizontal_offset": self.randomize_horizontal_offset,
                "horizontal_randomize_amount": self.horizontal_randomize_amount,
                "auto_face_width": self.auto_face_width,
                "auto_width_samples": self.auto_width_samples,
                "auto_width_clearance": self.auto_width_clearance,
                "clamp_edge_overlaps": self.clamp_edge_overlaps,
                "overlap_clearance": self.overlap_clearance,
                "use_face_loop_slide": self.use_face_loop_slide,
            },
        )

        # The final UV-pin pass operates on this newly generated object before
        # normal layer generation merges/adopts it, while standalone
        # interactive generation can keep it as the final object. Carry the
        # intended layer's explicit pin assignment onto it so
        # pins_for_decal_layer() does not interpret its empty default as
        # "Auto (all pins)".
        if intended_layer is not None:
            decal_obj.edge_decal_object_settings.uv_pin_indices = (
                format_uv_pin_indices(
                    layer_assigned_uv_pin_indices(intended_layer)
                )
            )

        # Storing source-matched material settings can initialize UV1 and UV2
        # before provisional strip coordinates are written. Reuse that UV1;
        # unconditionally creating another "UVMap" here produces UVMap.002.
        uv_layer = ensure_decal_mesh_uv_layers(decal_mesh)
        for polygon, polygon_uvs in zip(decal_mesh.polygons, generated_uvs):
            for loop_index, uv in zip(polygon.loop_indices, polygon_uvs):
                uv_layer.data[loop_index].uv = uv

        if surface_voronoi_used:
            # The constrained arrangement is triangulated for robustness, but
            # adjacent coplanar triangles are only implementation fragments.
            # Join good pairs after UV creation so BMesh can preserve the loop
            # data while removing those unnecessary diagonals.  A tight face
            # angle keeps genuine bends and ownership corners intact.
            cleanup_bmesh = bmesh.new()
            try:
                cleanup_bmesh.from_mesh(decal_mesh)
                cleanup_bmesh.normal_update()
                triangle_faces = [
                    face for face in cleanup_bmesh.faces
                    if len(face.verts) == 3
                ]
                before_face_count = len(cleanup_bmesh.faces)
                if triangle_faces:
                    bmesh.ops.join_triangles(
                        cleanup_bmesh,
                        faces=triangle_faces,
                        angle_face_threshold=radians(5.0),
                        angle_shape_threshold=radians(120.0),
                        cmp_seam=False,
                        cmp_sharp=False,
                        cmp_uvs=False,
                        cmp_vcols=False,
                        cmp_materials=False,
                    )
                cleanup_bmesh.to_mesh(decal_mesh)
                decal_mesh.update(calc_edges=True)
                decal_obj["edge_decal_surface_voronoi_joined_faces"] = max(
                    0,
                    before_face_count - len(decal_mesh.polygons),
                )
                created_face_count = len(decal_mesh.polygons)
            finally:
                cleanup_bmesh.free()

        merge_target = None

        if not EDGEDECAL_STANDALONE_GENERATION:
            if (
                intended_layer is not None
                and decal_layer_is_valid(intended_layer, source_obj)
                and intended_layer is not decal_obj
                and not intended_layer.get("edge_decal_locked", False)
                and (
                    intended_layer.data is None
                    or len(intended_layer.data.polygons) == 0
                    or bool(
                        intended_layer.get(
                            "edge_decal_mode",
                            "SHARP_EDGES",
                        ) == "FACE_SURFACES"
                        or str(
                            intended_layer.get(
                                "edge_decal_selection_mode",
                                "SELECTED_EDGES",
                            )
                        ) == "SELECTED_FACES"
                    ) == generate_from_selected_faces
                )
            ):
                merge_target = intended_layer
            elif settings.replace_previous:
                merge_target = find_existing_edge_decal(
                    source_obj,
                    exclude=decal_obj,
                    mode=(
                        "FACE_SURFACES"
                        if generate_from_selected_faces
                        else "SHARP_EDGES"
                    ),
                    context=context,
                )

        if (
            merge_target is not None
            and not decal_layer_source_edge_order_is_current(
                merge_target,
                source_obj,
            )
        ):
            self.report(
                {"WARNING"},
                "The active decal layer belongs to an older source topology; "
                "the new decals were placed in a separate layer to avoid "
                "reusing unrelated edge indices.",
            )
            merge_target = None

        existing_face_count = (
            len(merge_target.data.polygons)
            if merge_target is not None
            else 0
        )
        effective_uv_seed = (
            self.seed
            + existing_face_count * 1009
        )

        quadrify_result = "DISABLED"
        processed_uv_islands = 0
        measured_uv_density = 0.0

        has_interactive_partial_interval = bool(
            self.interactive_slice_start >= 0.0
            and self.interactive_slice_end >= 0.0
            and (
                self.interactive_slice_start > EPSILON
                or self.interactive_slice_end < 1.0 - EPSILON
            )
        )

        use_auto_uv_pins = bool(
            settings.auto_use_uv_pins
            and not self.fast_geometry_only
        )
        force_full_uv_for_pins = bool(
            use_auto_uv_pins
            and pins
        )

        if (
            (settings.auto_unwrap_uvs or force_full_uv_for_pins)
            and not self.fast_geometry_only
        ):
            try:
                (
                    quadrify_result,
                    processed_uv_islands,
                    measured_uv_density,
                ) = unwrap_generated_decal(
                    context,
                    source_obj,
                    decal_obj,
                    settings.use_integrated_quadrify,
                    settings.integrated_quadrify_average_shape,
                    settings.integrated_quadrify_even_shape,
                    settings.use_follow_active_quads,
                    self.uv_scale,
                    settings.set_target_texel_density,
                    settings.target_texel_density,
                    settings.texture_resolution,
                    context.scene.unit_settings.scale_length,
                    settings.generate_second_uv,
                    settings.average_uv_island_scale,
                    settings.align_uvs_horizontally,
                    settings.place_in_quarter_strips,
                    settings.randomize_quarter_strip,
                    False,
                    self.horizontal_randomize_amount,
                    effective_uv_seed,
                    settings.uv_strip_padding,
                )
            except RuntimeError as error:
                quadrify_result = "FAILED"
                self.report(
                    {"WARNING"},
                    f"UV unwrap workflow failed: {error}",
                )

        if (
            settings.auto_unwrap_uvs
            and settings.generate_second_uv
            and self.fast_geometry_only
            and merge_target is None
        ):
            # Fast Geometry skips the optional UV1 quadrify, density, packing,
            # randomization, and pin workflow. Second UV is an explicit output
            # request, though, so it must still receive its own Conformal
            # unwrap. When appending to an existing layer, the post-merge path
            # below rebuilds UV2 once on the complete combined topology.
            try:
                generate_decal_second_uv(
                    context,
                    source_obj,
                    decal_obj,
                    settings.target_texel_density,
                    settings.texture_resolution,
                    context.scene.unit_settings.scale_length,
                )
            except RuntimeError as error:
                self.report(
                    {"WARNING"},
                    f"Second UV unwrap failed: {error}",
                )

        auto_pin_islands = 0
        merged_with_existing = False

        if merge_target is not None:
            decal_obj = merge_generated_decal_objects(
                merge_target,
                decal_obj,
            )
            merged_with_existing = True
            set_active_decal_layer(source_obj, decal_obj)
            decal_data = decal_obj.edge_decal_object_settings
            decal_data.initialized = True
            decal_data.live_update = True

            if settings.generate_second_uv:
                # Rebuild UV2 on the complete merged topology so enabling the
                # option on an older layer also covers its existing faces.
                generate_decal_second_uv(
                    context,
                    source_obj,
                    decal_obj,
                    settings.target_texel_density,
                    settings.texture_resolution,
                    context.scene.unit_settings.scale_length,
                )

        if merge_target is None and not EDGEDECAL_STANDALONE_GENERATION:
            set_active_decal_layer(source_obj, decal_obj)

        if use_auto_uv_pins:
            pins = uv_pins_for_decal_layer_material(
                context.scene,
                decal_obj,
                fallback_material=(
                    (
                        settings.decal_material
                        or bpy.data.materials.get(DEFAULT_MATERIAL_NAME)
                    )
                    if getattr(settings, "use_material", True)
                    else None
                ),
            )

            if pins:
                # Pin the final object after merging so existing and newly
                # generated islands are averaged and fitted together.
                auto_pin_islands = apply_uv_pins_to_decal_objects(
                    [decal_obj],
                    pins,
                    self.seed,
                )
            else:
                self.report(
                    {"WARNING"},
                    "Automatically Use UV Pins is enabled, but no UV pins exist.",
                )

        # Horizontal phase is deliberately last. Full unwrap, layer merging,
        # and UV-pin fitting may all translate islands along U; applying the
        # explicit randomization setting here guarantees that it survives and
        # covers every island in the final merged decal object.
        if self.randomize_horizontal_offset and not self.fast_geometry_only:
            processed_uv_islands = max(
                processed_uv_islands,
                randomize_decal_uv_islands_horizontally(
                    decal_obj,
                    effective_uv_seed,
                    settings.uv_strip_padding,
                    self.horizontal_randomize_amount,
                ),
            )

        if merge_target is None and not EDGEDECAL_STANDALONE_GENERATION:
            decal_obj = adopt_generated_decal_into_empty_shell(
                source_obj,
                decal_obj,
                context=context,
            )

        apply_decal_normal_settings(
            decal_obj,
            settings.normal_mode,
            settings.normal_keep_sharp,
            settings.normal_weight,
            settings.normal_threshold,
        )

        ensure_decal_finish_modifiers(decal_obj, source_obj, settings)

        if not EDGEDECAL_STANDALONE_GENERATION:
            finalize_generated_decal_layer(source_obj, decal_obj, settings)
        else:
            apply_scene_decal_material(decal_obj, settings)

        # Interactive generation creates a short-lived standalone object for
        # each click, then merges it into the active layer itself. Publishing
        # that scratch object here creates a temporary UI row and makes it the
        # active layer before the interactive transaction can finish.
        if not EDGEDECAL_STANDALONE_GENERATION:
            sync_fn = globals().get("sync_source_layer_ui")
            activate_fn = globals().get("activate_decal_layer")

            if sync_fn is not None:
                sync_fn(source_obj, active_layer=decal_obj)

            if activate_fn is not None:
                activate_fn(context, source_obj, decal_obj)

        source_label = "face path" if generate_from_selected_faces else "edge"
        source_count = (
            face_source_count
            if generate_from_selected_faces
            else len(manifold_edges)
        )
        if merged_with_existing:
            message = (
                f"Merged {source_count} new {source_label}(s) into "
                f"{decal_obj.name}: {generated_island_count} island(s), "
                f"{created_face_count} new face(s)"
            )
        else:
            message = (
                f"Created {decal_obj.name}: {source_count} {source_label}(s), "
                f"{generated_island_count} island(s), {created_face_count} face(s)"
            )

        if skipped_count:
            message += f"; skipped {skipped_count} non-manifold edge(s)"

        if support_edges_dissolved:
            message += (
                f"; whole-mesh dissolved {support_edges_dissolved} temporary "
                "edge(s)"
            )

        if mask_split_stats["cut_count"]:
            message += (
                f"; mask cut {mask_split_stats['cut_count']} transition(s) "
                f"across {mask_split_stats['partial_edge_count']} edge(s)"
            )

        if crevice_removed_count:
            message += f"; removed {crevice_removed_count} crevice edge(s)"

        if short_removed_count:
            message += f"; removed {short_removed_count} short edge(s)"

        if amount_removed_count:
            message += f"; amount removed {amount_removed_count} edge(s)"

        if quadrify_result == "INTEGRATED":
            message += "; integrated quadrify"

        if settings.auto_unwrap_uvs and processed_uv_islands:
            message += f"; processed {processed_uv_islands} UV island(s)"

        if auto_pin_islands:
            message += f"; pinned {auto_pin_islands} UV island(s)"

        if settings.set_target_texel_density and measured_uv_density > 0.0:
            decal_obj["edge_decal_texel_density_px_cm"] = measured_uv_density
            message += f"; {measured_uv_density:.3f} px/cm"

        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
            scene_live_sync_cache_key(source_obj, decal_obj)
        ] = scene_live_edit_signature(settings)
        finish_decal_generation(context, source_obj, decal_obj)

        self.report({"INFO"}, message)
        return {"FINISHED"}




class EDGEDECAL_OT_generate_selected_faces(Operator):
    """Route selected quad faces through the regular edge-strip pipeline."""

    bl_idname = "mesh.generate_edge_decal_faces"
    bl_label = "Generate Face Decals"
    bl_description = "Generate adjustable decal strips through selected quad faces"
    bl_options = {"REGISTER", "UNDO"}

    surface_offset: FloatProperty(
        name="Surface Offset",
        default=0.002,
        min=0.0,
        soft_max=0.05,
        unit="LENGTH",
        description="Distance above the selected source faces",
    )

    uv_scale: FloatProperty(
        name="UV Scale",
        default=1.0,
        min=0.01,
        soft_min=0.1,
        soft_max=10.0,
        precision=3,
    )

    fast_geometry_only: BoolProperty(
        name="Fast Geometry Only",
        default=False,
        description="Skip optional UV placement processing",
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "EDIT_MESH"
            and context.edit_object is not None
            and context.edit_object.type == "MESH"
        )

    def invoke(self, context, event):
        settings = context.scene.edge_decal_settings
        self.surface_offset = settings.surface_offset
        self.uv_scale = settings.uv_scale
        self.fast_geometry_only = settings.fast_geometry_only
        return self.execute(context)

    def execute(self, context):
        source_obj = context.edit_object
        settings = context.scene.edge_decal_settings
        ensure_source_decal_layers_ready(source_obj, context)
        sync_decal_bevel_from_source(source_obj, settings)

        settings.surface_offset = self.surface_offset
        settings.uv_scale = self.uv_scale
        settings.fast_geometry_only = self.fast_geometry_only

        # The face selection supplies only a virtual center path. All geometry
        # and layer work stays in the normal edge-strip operator so every
        # width, amount, taper, UV, and finish control behaves identically.
        return bpy.ops.mesh.generate_edge_decal_strips(
            "EXEC_DEFAULT",
            face_width=settings.face_width,
            randomize_face_width=settings.randomize_face_width,
            minimum_face_width=settings.minimum_face_width,
            maximum_face_width=settings.maximum_face_width,
            crevice_removal=settings.crevice_removal,
            crevice_detection_mode=settings.crevice_detection_mode,
            crevice_ao_distance=settings.crevice_ao_distance,
            crevice_ao_samples=settings.crevice_ao_samples,
            remove_short_edges=settings.remove_short_edges,
            minimum_edge_length=settings.minimum_edge_length,
            decal_amount=settings.decal_amount,
            edge_slice=settings.edge_slice,
            maximum_decal_length=settings.maximum_decal_length,
            taper_sliced_ends=settings.taper_sliced_ends,
            slice_taper_length=settings.slice_taper_length,
            auto_trim_corner_ends=settings.auto_trim_corner_ends,
            corner_end_trim_multiplier=settings.corner_end_trim_multiplier,
            randomize_horizontal_offset=settings.randomize_horizontal_offset,
            horizontal_randomize_amount=settings.horizontal_randomize_amount,
            seed=settings.seed,
            uv_scale=settings.uv_scale,
            auto_face_width=settings.auto_face_width,
            auto_width_samples=settings.auto_width_samples,
            auto_width_clearance=settings.auto_width_clearance,
            clamp_edge_overlaps=settings.clamp_edge_overlaps,
            overlap_clearance=settings.overlap_clearance,
            use_face_loop_slide=settings.use_face_loop_slide,
            fast_geometry_only=settings.fast_geometry_only,
            add_weld_modifier=settings.add_weld_modifier,
            add_bevel_modifier=settings.add_bevel_modifier,
            surface_offset=settings.surface_offset,
            generate_from_selected_faces=True,
            generate_selected_edge_graph=True,
            interactive_skip_limited_dissolve=True,
        )


class EDGEDECAL_OT_generate_contextual(Operator):
    bl_idname = "mesh.generate_edge_decal_contextual"
    bl_label = "Generate Edge Decals"
    bl_description = (
        "In Edit Mode, generate from selected faces or manually selected edges. "
        "In Object Mode, generate automatically by face angle"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode == "EDIT_MESH":
            return (
                context.edit_object is not None
                and context.edit_object.type == "MESH"
            )

        if context.mode == "OBJECT":
            source_obj = edge_decal_context_source(context)
            return source_obj is not None and source_obj.type == "MESH"

        return False

    def execute(self, context):
        if context.mode == "EDIT_MESH":
            bm = bmesh.from_edit_mesh(context.edit_object.data)
            face_select_mode = bool(
                context.tool_settings.mesh_select_mode[2]
            )
            selected_faces = [
                face for face in bm.faces
                if face.select and not face.hide
            ]

            if face_select_mode and selected_faces:
                settings = context.scene.edge_decal_settings
                return bpy.ops.mesh.generate_edge_decal_faces(
                    "EXEC_DEFAULT",
                    surface_offset=settings.surface_offset,
                    uv_scale=settings.uv_scale,
                    fast_geometry_only=settings.fast_geometry_only,
                )

            selected_edges = [
                edge for edge in bm.edges
                if edge.select and not edge.hide
            ]

            if selected_edges:
                return bpy.ops.mesh.generate_edge_decal_strips(
                    "INVOKE_DEFAULT",
                    generate_selected_edge_graph=True,
                    interactive_skip_limited_dissolve=True,
                )

            self.report(
                {"ERROR"},
                "Select faces in Face Select mode or manifold edges in Edge Select mode.",
            )
            return {"CANCELLED"}

        if context.mode == "OBJECT":
            return bpy.ops.object.generate_edge_decals_by_angle(
                "INVOKE_DEFAULT"
            )

        self.report(
            {"ERROR"},
            "Use Edit Mode for selected faces/edges or Object Mode for automatic angle generation.",
        )
        return {"CANCELLED"}







class EDGEDECAL_OT_generate_automatic(Operator):
    bl_idname = "object.generate_edge_decals_by_angle"
    bl_label = "Generate Automatically"
    bl_description = "Automatically generate decal strips from sharp manifold edges"
    bl_options = {"REGISTER", "UNDO"}

    crevices_only: BoolProperty(
        default=False,
        options={"HIDDEN"},
        description="Generate only edges selected by the inverted crevice mask",
    )

    auto_edge_angle: FloatProperty(
        name="Auto Edge Angle",
        default=radians(30.0),
        min=0.0,
        max=radians(180.0),
        subtype="ANGLE",
        description="Generate from manifold edges at or above this face angle",
    )

    auto_follow_edge_loops: BoolProperty(
        name="Auto Follow Edge Loops",
        default=True,
        description=(
            "Follow connected quad-topology loops without including edges "
            "below Auto Edge Angle"
        ),
    )

    face_width: FloatProperty(
        name="Face Width",
        default=0.06,
        min=MIN_FACE_WIDTH,
        soft_max=1.0,
        unit="LENGTH",
        description="Interactive world-space decal width",
    )

    randomize_face_width: BoolProperty(
        name="Random Width",
        default=False,
        description="Choose a repeatable random width for each disconnected decal path",
    )

    minimum_face_width: FloatProperty(
        name="Minimum Width",
        default=0.005,
        min=MIN_FACE_WIDTH,
        soft_max=1.0,
        unit="LENGTH",
    )

    maximum_face_width: FloatProperty(
        name="Maximum Width",
        default=0.02,
        min=MIN_FACE_WIDTH,
        soft_max=1.0,
        unit="LENGTH",
    )

    fast_geometry_only: BoolProperty(
        name="Fast Geometry Only",
        default=False,
        description="Skip expensive final UV processing",
    )

    add_weld_modifier: BoolProperty(
        name="Add Weld Modifier",
        default=False,
    )

    add_bevel_modifier: BoolProperty(
        name="Add Bevel Modifier",
        default=False,
    )

    surface_offset: FloatProperty(
        name="Surface Offset",
        default=0.002,
        min=0.0,
        soft_max=0.05,
        unit="LENGTH",
        description="Interactive distance above the source surface",
    )

    randomize_horizontal_offset: BoolProperty(
        name="Random Horizontal Offset",
        default=True,
        description="Give every generated UV island a distinct randomized U position",
    )

    horizontal_randomize_amount: FloatProperty(
        name="Horizontal Randomize Amount",
        default=1.0,
        min=0.0,
        soft_max=500.0,
        description="Total U-space span used to separate randomized UV islands",
    )

    seed: IntProperty(
        name="Seed",
        default=1,
        min=0,
        soft_max=1000,
        description=(
            "Controls independently mixed per-path cuts and random UV placement"
        ),
    )

    uv_scale: FloatProperty(
        name="UV Scale",
        default=1.0,
        min=0.01,
        soft_min=0.1,
        soft_max=10.0,
        precision=3,
        description="Interactive multiplier for generated UV islands",
    )

    crevice_removal: FloatProperty(
        name="Crevice Removal",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Reduce automatically generated decals on inward crevice edges",
    )

    use_face_loop_slide: BoolProperty(
        name="Follow Connected Face Edges",
        default=True,
        description="Prefer connected support-face rails at strip endpoints",
    )

    crevice_detection_mode: EnumProperty(
        name="Crevice Detection",
        items=CREVICE_DETECTION_ITEMS,
        default="AO",
    )

    crevice_ao_distance: FloatProperty(
        name="AO Distance",
        default=0.0,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
        description="Zero automatically uses four times Face Width",
    )

    crevice_ao_samples: IntProperty(
        name="AO Samples",
        default=8,
        min=4,
        max=32,
    )

    remove_short_edges: BoolProperty(
        name="Remove Short Edges",
        default=False,
        description="Ignore automatically detected edges shorter than the minimum length",
    )

    minimum_edge_length: FloatProperty(
        name="Automatic Minimum Edge Length",
        default=0.30,
        min=0.0,
        soft_max=10.0,
        unit="LENGTH",
        description=(
            "World-space minimum for Generate Automatically. Each detected "
            "source edge is measured separately"
        ),
    )

    decal_amount: FloatProperty(
        name="Decal Amount",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        description="Percentage of automatically detected sharp edges kept at random",
    )

    auto_width_samples: IntProperty(
        name="Auto Width Samples",
        default=1,
        min=1,
        max=5,
        description="Lower is faster; higher is more accurate",
    )

    auto_face_width: BoolProperty(
        name="Auto Face Width",
        default=False,
        description="Clamp width automatically near neighboring source edges",
    )

    auto_width_clearance: FloatProperty(
        name="Width Clearance",
        default=0.85,
        min=0.05,
        max=0.99,
        subtype="FACTOR",
        description="Fraction of detected free space used by adaptive width",
    )

    clamp_edge_overlaps: BoolProperty(
        name="Clamp Edge Overlaps",
        default=True,
        description=(
            "Build connected curve-graph strips and locally reduce their width "
            "before generated sharp-edge paths overlap"
        ),
    )

    overlap_clearance: FloatProperty(
        name="Overlap Clearance",
        default=0.98,
        min=0.5,
        max=0.999,
        subtype="FACTOR",
        description="Fraction of the shared gap used by opposing sharp-edge strips",
    )

    def invoke(self, context, event):
        settings = context.scene.edge_decal_settings
        source_obj = edge_decal_context_source(context)
        sync_decal_bevel_from_source(source_obj, settings)
        self.auto_edge_angle = settings.auto_edge_angle
        self.auto_follow_edge_loops = settings.auto_follow_edge_loops
        self.face_width = settings.face_width
        self.randomize_face_width = settings.randomize_face_width
        self.minimum_face_width = settings.minimum_face_width
        self.maximum_face_width = settings.maximum_face_width
        self.crevice_removal = settings.crevice_removal
        self.crevice_detection_mode = settings.crevice_detection_mode
        self.crevice_ao_distance = settings.crevice_ao_distance
        self.crevice_ao_samples = settings.crevice_ao_samples
        self.use_face_loop_slide = settings.use_face_loop_slide
        self.remove_short_edges = settings.remove_short_edges
        self.minimum_edge_length = settings.auto_minimum_edge_length
        self.decal_amount = settings.decal_amount
        self.surface_offset = settings.surface_offset
        self.randomize_horizontal_offset = settings.randomize_horizontal_offset
        self.horizontal_randomize_amount = settings.horizontal_randomize_amount
        self.seed = settings.seed
        self.uv_scale = settings.uv_scale
        self.auto_face_width = settings.auto_face_width
        self.auto_width_samples = settings.auto_width_samples
        self.auto_width_clearance = settings.auto_width_clearance
        self.clamp_edge_overlaps = settings.clamp_edge_overlaps
        self.overlap_clearance = settings.overlap_clearance
        self.fast_geometry_only = settings.fast_geometry_only
        self.add_weld_modifier = settings.add_weld_modifier
        self.add_bevel_modifier = settings.add_bevel_modifier
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "auto_edge_angle")
        layout.prop(self, "auto_follow_edge_loops")
        width = layout.row()
        width.enabled = not self.randomize_face_width
        width.prop(self, "face_width")
        layout.prop(self, "randomize_face_width", toggle=True)
        random_bounds = layout.column(align=True)
        random_bounds.enabled = self.randomize_face_width
        random_bounds.prop(self, "minimum_face_width")
        random_bounds.prop(self, "maximum_face_width")
        layout.prop(self, "crevice_removal")

        crevice_options = layout.column(align=True)
        crevice_options.enabled = self.crevice_removal > 0.0
        crevice_options.prop(self, "crevice_detection_mode")

        ao_options = crevice_options.column(align=True)
        ao_options.enabled = self.crevice_detection_mode == "AO"
        ao_options.prop(self, "crevice_ao_distance")
        ao_options.prop(self, "crevice_ao_samples")

        layout.prop(self, "remove_short_edges")

        min_length_row = layout.row()
        min_length_row.enabled = self.remove_short_edges
        min_length_row.prop(self, "minimum_edge_length")

        layout.prop(self, "decal_amount")
        layout.prop(self, "surface_offset")
        layout.prop(self, "uv_scale")
        layout.prop(self, "randomize_horizontal_offset")
        amount_row = layout.row()
        amount_row.enabled = self.randomize_horizontal_offset
        amount_row.prop(self, "horizontal_randomize_amount")
        layout.prop(self, "seed")
        layout.prop(self, "auto_face_width")
        layout.prop(self, "clamp_edge_overlaps")

        samples = layout.row()
        samples.enabled = (
            self.auto_face_width or self.clamp_edge_overlaps
        )
        samples.prop(self, "auto_width_samples")

        clearance = layout.row()
        clearance.enabled = self.auto_face_width
        clearance.prop(self, "auto_width_clearance")

        overlap = layout.row()
        overlap.enabled = self.clamp_edge_overlaps
        overlap.prop(self, "overlap_clearance")
        layout.prop(self, "use_face_loop_slide")
        layout.prop(self, "fast_geometry_only")
        layout.prop(self, "add_weld_modifier")
        layout.prop(self, "add_bevel_modifier")

    @classmethod
    def poll(cls, context):
        if context.mode != "OBJECT":
            return False
        source_obj = edge_decal_context_source(context)
        return source_obj is not None and source_obj.type == "MESH"

    def execute(self, context):
        source_obj = edge_decal_context_source(context)
        if source_obj is None:
            return {"CANCELLED"}
        ensure_source_decal_layers_ready(source_obj, context)
        settings = context.scene.edge_decal_settings
        sync_decal_bevel_from_source(source_obj, settings)

        settings.auto_edge_angle = self.auto_edge_angle
        settings.auto_follow_edge_loops = self.auto_follow_edge_loops
        settings.face_width = self.face_width
        settings.randomize_face_width = self.randomize_face_width
        settings.minimum_face_width = self.minimum_face_width
        settings.maximum_face_width = self.maximum_face_width
        settings.crevice_removal = self.crevice_removal
        settings.crevice_detection_mode = self.crevice_detection_mode
        settings.crevice_ao_distance = self.crevice_ao_distance
        settings.crevice_ao_samples = self.crevice_ao_samples
        settings.use_face_loop_slide = self.use_face_loop_slide
        settings.remove_short_edges = self.remove_short_edges
        settings.auto_minimum_edge_length = self.minimum_edge_length
        settings.decal_amount = self.decal_amount
        settings.surface_offset = self.surface_offset
        settings.randomize_horizontal_offset = self.randomize_horizontal_offset
        settings.horizontal_randomize_amount = self.horizontal_randomize_amount
        settings.seed = self.seed
        settings.uv_scale = self.uv_scale
        settings.auto_face_width = self.auto_face_width
        settings.auto_width_samples = self.auto_width_samples
        settings.auto_width_clearance = self.auto_width_clearance
        settings.clamp_edge_overlaps = self.clamp_edge_overlaps
        settings.overlap_clearance = self.overlap_clearance
        settings.fast_geometry_only = self.fast_geometry_only
        settings.add_weld_modifier = self.add_weld_modifier
        self.add_bevel_modifier = bool(
            self.add_bevel_modifier
            or source_bevel_settings(source_obj) is not None
        )
        settings.add_bevel_modifier = self.add_bevel_modifier

        select_only_object(context, source_obj)

        try:
            bpy.ops.object.mode_set(mode="EDIT")
        except RuntimeError:
            self.report({"ERROR"}, "Could not enter Edit Mode on the active mesh.")
            return {"CANCELLED"}

        bm = bmesh.from_edit_mesh(source_obj.data)
        bm.normal_update()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        for vert in bm.verts:
            vert.select = False
        for face in bm.faces:
            face.select = False
        for edge in bm.edges:
            edge.select = False

        seed_edge_indices = filter_automatic_edges_by_angle(
            bm,
            self.auto_edge_angle,
        )

        if self.crevices_only:
            world_matrix = source_obj.matrix_world.copy()
            try:
                normal_matrix = world_matrix.to_3x3().inverted().transposed()
            except ValueError:
                force_object_mode(context)
                self.report(
                    {"ERROR"},
                    "The source object has a non-invertible transform.",
                )
                return {"CANCELLED"}
            seed_edges = [bm.edges[index] for index in seed_edge_indices]
            crevice_bvh = (
                build_world_bvh_from_bmesh(bm, world_matrix)
                if self.crevice_detection_mode == "AO"
                else None
            )
            resolved_width = resolve_relative_face_width(
                self.face_width,
                list(bm.edges),
                world_matrix,
            )
            selected_edge_indices = [
                edge.index
                for edge in select_edges_by_crevice_mask(
                    seed_edges,
                    world_matrix,
                    normal_matrix,
                    self.crevice_detection_mode,
                    crevice_bvh,
                    self.crevice_ao_distance,
                    self.crevice_ao_samples,
                    resolved_width,
                    self.surface_offset,
                )
            ]
        else:
            selected_edge_indices = (
                expand_automatic_edge_loop_seeds(bm, seed_edge_indices)
                if self.auto_follow_edge_loops
                else seed_edge_indices
            )
            selected_edge_indices = filter_automatic_edges_by_angle(
                bm,
                self.auto_edge_angle,
                selected_edge_indices,
            )
        selected_edge_count = 0
        for edge_index in selected_edge_indices:
            if not (0 <= edge_index < len(bm.edges)):
                continue
            edge = bm.edges[edge_index]
            if (
                edge.hide
                or len(edge.link_faces) != 2
            ):
                continue
            edge.select = True
            selected_edge_count += 1

        bmesh.update_edit_mesh(
            source_obj.data,
            loop_triangles=False,
            destructive=False,
        )

        if not selected_edge_count:
            force_object_mode(context)
            self.report(
                {"WARNING"},
                (
                    "No crevice edges matched the current mask and Auto Edge Angle."
                    if self.crevices_only
                    else "No manifold edges matched the Auto Edge Angle."
                ),
            )
            return {"CANCELLED"}

        try:
            sharp_result = bpy.ops.mesh.generate_edge_decal_strips(
                face_width=self.face_width,
                randomize_face_width=self.randomize_face_width,
                minimum_face_width=self.minimum_face_width,
                maximum_face_width=self.maximum_face_width,
                crevice_removal=(
                    0.0 if self.crevices_only else self.crevice_removal
                ),
                crevice_detection_mode=self.crevice_detection_mode,
                crevice_ao_distance=self.crevice_ao_distance,
                crevice_ao_samples=self.crevice_ao_samples,
                remove_short_edges=self.remove_short_edges,
                minimum_edge_length=self.minimum_edge_length,
                minimum_length_per_edge=True,
                decal_amount=self.decal_amount,
                randomize_horizontal_offset=self.randomize_horizontal_offset,
                horizontal_randomize_amount=self.horizontal_randomize_amount,
                seed=self.seed,
                uv_scale=self.uv_scale,
                auto_face_width=self.auto_face_width,
                auto_width_samples=self.auto_width_samples,
                auto_width_clearance=self.auto_width_clearance,
                clamp_edge_overlaps=self.clamp_edge_overlaps,
                overlap_clearance=self.overlap_clearance,
                use_face_loop_slide=self.use_face_loop_slide,
                generate_selected_edge_graph=True,
                interactive_skip_limited_dissolve=True,
                fast_geometry_only=self.fast_geometry_only,
                add_weld_modifier=self.add_weld_modifier,
                add_bevel_modifier=self.add_bevel_modifier,
                surface_offset=self.surface_offset,
            )
        except RuntimeError as error:
            force_object_mode(context)
            self.report(
                {"WARNING"},
                f"Sharp-edge generation failed: {error}",
            )
            return {"CANCELLED"}

        if "FINISHED" not in sharp_result:
            force_object_mode(context)
            return {"CANCELLED"}

        last_generated_obj = active_generated_decal(context)
        finish_decal_generation(context, source_obj, last_generated_obj)
        self.report(
            {"INFO"},
            (
                f"Generated decals from {selected_edge_count} crevice edge(s)"
                if self.crevices_only
                else f"Generated decals from {selected_edge_count} sharp edge(s)"
            ),
        )
        return {"FINISHED"}
