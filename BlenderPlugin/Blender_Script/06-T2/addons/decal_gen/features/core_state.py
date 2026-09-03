# SPDX-License-Identifier: GPL-2.0-or-later
"""Core state, source bevel sync helpers, stored settings, regeneration, and decal object management.

Loaded into the add-on package shared namespace by __init__.py.
"""

def last_source_bevel_modifier(source_obj):
    """Return the last Bevel modifier in the source object's stack."""
    if source_obj is None or source_obj.type != "MESH":
        return None
    return next(
        (
            modifier
            for modifier in reversed(source_obj.modifiers)
            if modifier.type == "BEVEL"
        ),
        None,
    )


def source_bevel_world_width(source_obj, bevel_modifier):
    """
    Convert the source modifier's local-space width to the world-space width
    needed by generated decals, whose base mesh is stored in world coordinates.
    """
    raw_width = max(0.0, float(getattr(bevel_modifier, "width", 0.0)))
    scale = source_obj.matrix_world.to_scale()
    absolute_scale = [abs(float(axis)) for axis in scale]

    if not absolute_scale:
        return raw_width

    # Exact for the usual uniform-scale case. For non-uniform scale there is
    # no single globally exact bevel width because it depends on edge direction;
    # the RMS scale is a stable approximation and avoids severe under-scaling.
    if max(absolute_scale) - min(absolute_scale) <= 1.0e-6:
        scale_factor = absolute_scale[0]
    else:
        scale_factor = (
            sum(value * value for value in absolute_scale) / len(absolute_scale)
        ) ** 0.5

    return raw_width * max(scale_factor, 1.0e-8)


def source_bevel_settings(source_obj):
    """Resolve the last source Bevel modifier into decal-compatible values."""
    bevel_modifier = last_source_bevel_modifier(source_obj)
    if bevel_modifier is None:
        return None

    return {
        "width": source_bevel_world_width(source_obj, bevel_modifier),
        "segments": max(1, int(getattr(bevel_modifier, "segments", 1))),
        "profile": max(
            0.0,
            min(1.0, float(getattr(bevel_modifier, "profile", 0.5))),
        ),
        "angle_limit": max(
            0.0,
            min(pi, float(getattr(bevel_modifier, "angle_limit", radians(30.0)))),
        ),
        "limit_method": str(getattr(bevel_modifier, "limit_method", "ANGLE")),
        "affect": str(getattr(bevel_modifier, "affect", "EDGES")),
        "offset_type": str(getattr(bevel_modifier, "offset_type", "OFFSET")),
        "harden_normals": bool(getattr(bevel_modifier, "harden_normals", False)),
        "loop_slide": bool(getattr(bevel_modifier, "loop_slide", True)),
        "use_clamp_overlap": bool(
            getattr(bevel_modifier, "use_clamp_overlap", True)
        ),
        "miter_outer": str(getattr(bevel_modifier, "miter_outer", "SHARP")),
        "miter_inner": str(getattr(bevel_modifier, "miter_inner", "SHARP")),
    }


def apply_source_bevel_to_decal_modifier(source_obj, decal_modifier):
    """Copy the last source Bevel modifier onto one generated decal modifier."""
    values = source_bevel_settings(source_obj)
    if values is None or decal_modifier is None:
        return False

    for property_name in (
        "segments",
        "profile",
        "angle_limit",
        "limit_method",
        "affect",
        "offset_type",
        "loop_slide",
        "use_clamp_overlap",
        "miter_outer",
        "miter_inner",
    ):
        if hasattr(decal_modifier, property_name):
            try:
                setattr(decal_modifier, property_name, values[property_name])
            except (TypeError, ValueError):
                pass

    if hasattr(decal_modifier, "width"):
        decal_modifier.width = values["width"]
    if hasattr(decal_modifier, "harden_normals"):
        # Harden Normals is useful on the solid source mesh, but produces
        # undesirable shading on the thin generated decal surface.
        decal_modifier.harden_normals = False

    return True


def apply_settings_bevel_to_decal_modifier(settings, decal_modifier):
    """Apply the panel's bevel controls when the source has no Bevel."""
    if settings is None or decal_modifier is None:
        return False

    values = {
        "width": max(0.0, float(settings.center_bevel_width)),
        "segments": max(1, int(settings.center_bevel_segments)),
        "profile": max(0.0, min(1.0, float(settings.center_bevel_profile))),
        "angle_limit": max(0.0, min(pi, float(settings.bevel_angle))),
    }
    for property_name, value in values.items():
        if hasattr(decal_modifier, property_name):
            try:
                setattr(decal_modifier, property_name, value)
            except (TypeError, ValueError):
                pass

    for property_name, value in (
        ("limit_method", "ANGLE"),
        ("affect", "EDGES"),
        ("harden_normals", False),
    ):
        if hasattr(decal_modifier, property_name):
            try:
                setattr(decal_modifier, property_name, value)
            except (TypeError, ValueError):
                pass

    return True


def generated_decal_bevel_modifier(decal_obj):
    """Return the add-on-controlled bevel, including older linked bevels."""
    if decal_obj is None:
        return None
    return next(
        (
            modifier
            for modifier in reversed(decal_obj.modifiers)
            if modifier.type == "BEVEL"
            and modifier.name in {"Edge Decal Bevel", "Match Source Edge"}
        ),
        None,
    )


def ensure_decal_match_source_bevel(decal_obj, source_obj, settings=None):
    """Add or refresh the Match Source Edge bevel on one generated decal."""
    if decal_obj is None or source_obj is None:
        return False
    if source_bevel_settings(source_obj) is None:
        return False

    bevel = generated_decal_bevel_modifier(decal_obj)
    if bevel is None:
        bevel = decal_obj.modifiers.new("Match Source Edge", "BEVEL")
    else:
        bevel.name = "Match Source Edge"
    if not apply_source_bevel_to_decal_modifier(source_obj, bevel):
        return False
    if settings is None:
        settings = getattr(decal_obj, "edge_decal_object_settings", None)
    if hasattr(bevel, "harden_normals"):
        bevel.harden_normals = bool(
            getattr(settings, "bevel_harden_normals", False)
        )
    return True


def ensure_decal_bevel_modifier(decal_obj, source_obj, settings):
    """Add the enabled bevel, copying the source or using panel settings."""
    if decal_obj is None or settings is None:
        return None

    if source_bevel_settings(source_obj) is not None:
        ensure_decal_match_source_bevel(decal_obj, source_obj, settings)
        bevel = generated_decal_bevel_modifier(decal_obj)
    else:
        bevel = generated_decal_bevel_modifier(decal_obj)
        if bevel is None:
            bevel = decal_obj.modifiers.new("Edge Decal Bevel", "BEVEL")
        else:
            bevel.name = "Edge Decal Bevel"
        apply_settings_bevel_to_decal_modifier(settings, bevel)

    if bevel is None:
        return None
    if hasattr(bevel, "harden_normals"):
        bevel.harden_normals = bool(
            getattr(settings, "bevel_harden_normals", False)
        )
    if getattr(settings, "bevel_edge_center", False):
        if hasattr(bevel, "limit_method"):
            bevel.limit_method = "VGROUP"
        if hasattr(bevel, "vertex_group"):
            bevel.vertex_group = "EdgeDecal_Center"
    elif hasattr(bevel, "vertex_group"):
        # Source/custom settings above have already restored the appropriate
        # limit method. Clear the add-on's center-group override as well.
        bevel.vertex_group = ""
    return bevel


def generated_decal_weld_modifier(decal_obj):
    """Return the Weld modifier controlled by the add-on."""
    if decal_obj is None:
        return None
    return next(
        (
            modifier
            for modifier in decal_obj.modifiers
            if modifier.type == "WELD"
            and modifier.name in {
                "Weld Strip Sections",
                "Weld Intersection Sections",
            }
        ),
        None,
    )


def ensure_decal_weld_modifier(decal_obj, settings):
    """Add or refresh the generated decal's controlled Weld modifier."""
    if decal_obj is None or settings is None:
        return None

    weld = generated_decal_weld_modifier(decal_obj)
    if weld is None:
        modifier_name = (
            "Weld Intersection Sections"
            if decal_obj.get("edge_decal_mode") == "INTERSECTIONS"
            else "Weld Strip Sections"
        )
        weld = decal_obj.modifiers.new(modifier_name, "WELD")
    weld.merge_threshold = max(0.0, float(settings.weld_distance))
    if hasattr(weld, "mode"):
        weld.mode = "ALL"
    return weld


def generated_decal_center_displace_modifier(decal_obj):
    """Return the center-only Displace modifier controlled by the add-on."""
    if decal_obj is None:
        return None
    return next(
        (
            modifier
            for modifier in decal_obj.modifiers
            if modifier.type == "DISPLACE"
            and modifier.name == "Displace Edge Decal Center"
        ),
        None,
    )


def ensure_decal_center_displace_modifier(decal_obj, settings):
    """Add or refresh a normal displacement for EdgeDecal_Center."""
    if decal_obj is None or settings is None:
        return None

    modifier = generated_decal_center_displace_modifier(decal_obj)
    if modifier is None:
        modifier = decal_obj.modifiers.new(
            "Displace Edge Decal Center",
            "DISPLACE",
        )
    modifier.vertex_group = "EdgeDecal_Center"
    modifier.direction = "NORMAL"
    modifier.strength = float(settings.center_displace_strength)
    return modifier


def ensure_decal_shrinkwrap_to_source(
    decal_obj,
    source_obj,
    surface_offset=0.0,
):
    """Add or refresh the generated decal's source-targeted Shrinkwrap."""
    if decal_obj is None or source_obj is None:
        return None

    shrinkwrap = next(
        (
            modifier
            for modifier in decal_obj.modifiers
            if modifier.type == "SHRINKWRAP"
            and modifier.name == "Shrinkwrap to Source"
        ),
        None,
    )
    if shrinkwrap is None:
        shrinkwrap = decal_obj.modifiers.new(
            "Shrinkwrap to Source",
            "SHRINKWRAP",
        )
    shrinkwrap.target = source_obj
    shrinkwrap.offset = max(0.0, float(surface_offset))
    return shrinkwrap


def source_targeted_decal_shrinkwrap(decal_obj):
    """Return the Shrinkwrap modifier owned by the decal generator."""
    if decal_obj is None:
        return None
    return next(
        (
            modifier
            for modifier in decal_obj.modifiers
            if modifier.type == "SHRINKWRAP"
            and modifier.name == "Shrinkwrap to Source"
        ),
        None,
    )


def ensure_decal_subdivision_modifier(decal_obj):
    """Add or return the generated decal's Subdivision modifier."""
    if decal_obj is None:
        return None

    modifier = generated_decal_subdivision_modifier(decal_obj)
    if modifier is None:
        modifier = decal_obj.modifiers.new(
            "Edge Decal Subdivision",
            "SUBSURF",
        )
    return modifier


def generated_decal_subdivision_modifier(decal_obj):
    """Return the Subdivision modifier controlled by the add-on."""
    if decal_obj is None:
        return None
    return next(
        (
            item
            for item in decal_obj.modifiers
            if item.type == "SUBSURF"
            and item.name == "Edge Decal Subdivision"
        ),
        None,
    )


def ensure_decal_decimate_modifier(decal_obj):
    """Add or return the generated decal's Decimate modifier."""
    if decal_obj is None:
        return None

    modifier = generated_decal_decimate_modifier(decal_obj)
    if modifier is None:
        modifier = decal_obj.modifiers.new(
            "Edge Decal Decimate",
            "DECIMATE",
        )
    return modifier


def generated_decal_decimate_modifier(decal_obj):
    """Return the Decimate modifier controlled by the add-on."""
    if decal_obj is None:
        return None
    return next(
        (
            item
            for item in decal_obj.modifiers
            if item.type == "DECIMATE"
            and item.name == "Edge Decal Decimate"
        ),
        None,
    )


def order_decal_finish_modifiers(decal_obj):
    """Keep the add-on's controlled modifier tail in its required order."""
    if decal_obj is None:
        return

    controlled = []
    for modifier_type, modifier_names in (
        (
            "WELD",
            {"Weld Strip Sections", "Weld Intersection Sections"},
        ),
        ("SHRINKWRAP", {"Shrinkwrap to Source"}),
        ("DISPLACE", {"Displace Edge Decal Center"}),
        ("BEVEL", {"Edge Decal Bevel", "Match Source Edge"}),
        ("SUBSURF", {"Edge Decal Subdivision"}),
        ("DECIMATE", {"Edge Decal Decimate"}),
        (
            "WEIGHTED_NORMAL",
            {
                "Edge Decal Face Area Normals",
                "Edge Decal Weighted Normals",
            },
        ),
    ):
        controlled.extend(
            modifier
            for modifier in decal_obj.modifiers
            if modifier.type == modifier_type
            and modifier.name in modifier_names
        )

    # Moving each controlled modifier to the end in sequence leaves the whole
    # sequence as the final stack tail while preserving all unrelated modifiers.
    for modifier in controlled:
        current_index = next(
            (
                index
                for index, item in enumerate(decal_obj.modifiers)
                if item == modifier
            ),
            -1,
        )
        if current_index >= 0:
            decal_obj.modifiers.move(
                current_index,
                len(decal_obj.modifiers) - 1,
            )


def ensure_decal_finish_modifiers(decal_obj, source_obj, settings):
    """Add enabled finish modifiers and enforce their controlled stack order."""
    if decal_obj is None or settings is None:
        return
    weld = generated_decal_weld_modifier(decal_obj)
    if getattr(settings, "add_weld_modifier", False):
        ensure_decal_weld_modifier(decal_obj, settings)
    elif weld is not None:
        decal_obj.modifiers.remove(weld)

    center_displace = generated_decal_center_displace_modifier(decal_obj)
    if getattr(settings, "add_center_displace_modifier", False):
        ensure_decal_center_displace_modifier(decal_obj, settings)
    elif center_displace is not None:
        decal_obj.modifiers.remove(center_displace)

    bevel = generated_decal_bevel_modifier(decal_obj)
    if getattr(settings, "add_bevel_modifier", False):
        ensure_decal_bevel_modifier(decal_obj, source_obj, settings)
    elif bevel is not None:
        decal_obj.modifiers.remove(bevel)
    shrinkwrap = source_targeted_decal_shrinkwrap(decal_obj)
    if getattr(settings, "add_shrinkwrap_modifier", False):
        ensure_decal_shrinkwrap_to_source(
            decal_obj,
            source_obj,
            getattr(settings, "surface_offset", 0.0),
        )
    elif shrinkwrap is not None:
        decal_obj.modifiers.remove(shrinkwrap)

    subdivision = generated_decal_subdivision_modifier(decal_obj)
    if getattr(settings, "add_subdivision_modifier", False):
        ensure_decal_subdivision_modifier(decal_obj)
    elif subdivision is not None:
        decal_obj.modifiers.remove(subdivision)

    decimate = generated_decal_decimate_modifier(decal_obj)
    if getattr(settings, "add_decimate_modifier", False):
        ensure_decal_decimate_modifier(decal_obj)
    elif decimate is not None:
        decal_obj.modifiers.remove(decimate)
    order_decal_finish_modifiers(decal_obj)


def initialize_decal_finish_settings_from_modifiers(decal_obj):
    """Recover per-layer modifier settings saved before those RNA fields existed."""
    if decal_obj is None:
        return False

    data = getattr(decal_obj, "edge_decal_object_settings", None)
    if data is None:
        return False

    def property_is_set(property_name):
        try:
            return data.is_property_set(property_name)
        except (AttributeError, TypeError):
            return True

    tracked_properties = (
        "add_weld_modifier",
        "weld_distance",
        "add_shrinkwrap_modifier",
        "add_center_displace_modifier",
        "center_displace_strength",
        "add_bevel_modifier",
        "bevel_edge_center",
        "center_bevel_width",
        "center_bevel_segments",
        "center_bevel_profile",
        "bevel_harden_normals",
        "bevel_angle",
        "add_subdivision_modifier",
        "add_decimate_modifier",
    )
    if all(property_is_set(name) for name in tracked_properties):
        return False

    weld = generated_decal_weld_modifier(decal_obj)
    shrinkwrap = source_targeted_decal_shrinkwrap(decal_obj)
    center_displace = generated_decal_center_displace_modifier(decal_obj)
    bevel = generated_decal_bevel_modifier(decal_obj)
    subdivision = generated_decal_subdivision_modifier(decal_obj)
    decimate = generated_decal_decimate_modifier(decal_obj)

    recovered_values = {
        "add_weld_modifier": weld is not None,
        "add_shrinkwrap_modifier": shrinkwrap is not None,
        "add_center_displace_modifier": center_displace is not None,
        "add_bevel_modifier": bevel is not None,
        "add_subdivision_modifier": subdivision is not None,
        "add_decimate_modifier": decimate is not None,
    }
    if weld is not None:
        recovered_values["weld_distance"] = float(
            getattr(weld, "merge_threshold", 0.0001)
        )
    if center_displace is not None:
        recovered_values["center_displace_strength"] = float(
            getattr(center_displace, "strength", 0.002)
        )
    if bevel is not None:
        recovered_values.update({
            "bevel_edge_center": (
                str(getattr(bevel, "limit_method", "")) == "VGROUP"
                and str(getattr(bevel, "vertex_group", ""))
                == "EdgeDecal_Center"
            ),
            "center_bevel_width": float(getattr(bevel, "width", 0.015)),
            "center_bevel_segments": max(
                1,
                int(getattr(bevel, "segments", 2)),
            ),
            "center_bevel_profile": float(getattr(bevel, "profile", 0.5)),
            "bevel_harden_normals": bool(
                getattr(bevel, "harden_normals", False)
            ),
            "bevel_angle": float(
                getattr(bevel, "angle_limit", radians(30.0))
            ),
        })

    global EDGEDECAL_SETTINGS_SYNCING
    previous_syncing = EDGEDECAL_SETTINGS_SYNCING
    EDGEDECAL_SETTINGS_SYNCING = True
    try:
        for property_name in tracked_properties:
            if property_is_set(property_name):
                continue
            if property_name in recovered_values:
                setattr(data, property_name, recovered_values[property_name])
            else:
                # Persist the RNA default for detail fields whose modifier is
                # disabled, so migration happens only once for this layer.
                setattr(data, property_name, getattr(data, property_name))
    finally:
        EDGEDECAL_SETTINGS_SYNCING = previous_syncing

    return True


def _live_finish_modifier_target(settings, context):
    """Resolve the decal and source affected by a live modifier control."""
    scene = getattr(context, "scene", None) if context is not None else None
    scene_settings = getattr(scene, "edge_decal_settings", None) if scene else None

    if settings == scene_settings:
        source_obj = resolve_live_update_source(context)
        decal_obj = (
            active_decal_layer_for_source(
                source_obj,
                include_locked=False,
                context=context,
            )
            if source_obj is not None
            else None
        )
        return decal_obj, source_obj, scene_settings

    decal_obj = getattr(settings, "id_data", None)
    if (
        decal_obj is None
        or getattr(decal_obj, "type", None) != "MESH"
        or not decal_obj.get("edge_decal_generated")
    ):
        return None, None, scene_settings

    source_obj = getattr(settings, "source_object", None)
    if source_obj is None:
        source_obj = find_object_by_name_or_full(
            str(decal_obj.get("edge_decal_source", ""))
        )
    return decal_obj, source_obj, scene_settings


def update_decal_finish_modifiers(settings, context):
    """Apply weld and bevel panel changes without rebuilding decal geometry."""
    global EDGEDECAL_SETTINGS_SYNCING

    if (
        EDGEDECAL_SCENE_SETTINGS_COPYING
        or EDGEDECAL_SETTINGS_SYNCING
        or regenerating_active()
    ):
        return

    decal_obj, source_obj, scene_settings = _live_finish_modifier_target(
        settings,
        context,
    )
    if decal_obj is None:
        return

    ensure_decal_finish_modifiers(decal_obj, source_obj, settings)

    data = getattr(decal_obj, "edge_decal_object_settings", None)
    if data is not None and data != settings:
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            for property_name in (
                "add_weld_modifier",
                "weld_distance",
                "add_center_displace_modifier",
                "center_displace_strength",
                "add_shrinkwrap_modifier",
                "add_subdivision_modifier",
                "add_decimate_modifier",
                "add_bevel_modifier",
                "bevel_edge_center",
                "center_bevel_width",
                "center_bevel_segments",
                "center_bevel_profile",
                "bevel_harden_normals",
                "bevel_angle",
            ):
                setattr(data, property_name, getattr(settings, property_name))
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing

    if scene_settings is not None and settings == scene_settings:
        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
            scene_live_sync_cache_key(source_obj, decal_obj)
        ] = scene_live_edit_signature(scene_settings)
    decal_obj.update_tag(refresh={"OBJECT"})


def update_decal_surface_offset(settings, context):
    """Use Shrinkwrap offset directly when available; otherwise regenerate."""
    global EDGEDECAL_SETTINGS_SYNCING

    if (
        EDGEDECAL_SCENE_SETTINGS_COPYING
        or EDGEDECAL_SETTINGS_SYNCING
        or regenerating_active()
    ):
        return

    scene = getattr(context, "scene", None)
    scene_settings = getattr(scene, "edge_decal_settings", None) if scene else None
    decal_obj = None
    source_obj = None

    if settings == scene_settings:
        source_obj = resolve_live_update_source(context)
        if source_obj is not None:
            decal_obj = active_decal_layer_for_source(
                source_obj,
                include_locked=False,
                context=context,
            )
    else:
        candidate = getattr(settings, "id_data", None)
        if (
            candidate is not None
            and getattr(candidate, "type", None) == "MESH"
            and candidate.get("edge_decal_generated")
        ):
            decal_obj = candidate
            source_obj = getattr(settings, "source_object", None)

    shrinkwrap = source_targeted_decal_shrinkwrap(decal_obj)
    if shrinkwrap is None:
        schedule_decal_live_update(settings, context)
        return

    offset = max(0.0, float(getattr(settings, "surface_offset", 0.0)))
    shrinkwrap.offset = offset

    data = getattr(decal_obj, "edge_decal_object_settings", None)
    if data is not None and data != settings:
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            data.surface_offset = offset
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing

    if settings == scene_settings and source_obj is not None:
        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
            scene_live_sync_cache_key(source_obj, decal_obj)
        ] = scene_live_edit_signature(scene_settings)
    decal_obj.update_tag(refresh={"OBJECT"})


def sync_decal_bevel_from_source(source_obj, settings):
    """Enable and copy a detected source bevel into decal settings."""
    if settings is None:
        return None

    values = source_bevel_settings(source_obj)
    if values is None:
        return None

    settings.add_bevel_modifier = True
    settings.center_bevel_width = values["width"]
    settings.center_bevel_segments = values["segments"]
    settings.center_bevel_profile = values["profile"]
    settings.bevel_angle = values["angle_limit"]
    return last_source_bevel_modifier(source_obj)


EDGEDECAL_LIVE_UPDATE_QUEUE = {}
EDGEDECAL_LIVE_UPDATE_RUNNING = False
EDGEDECAL_LIVE_UPDATE_DELAY = 0.30
EDGEDECAL_FAST_LIVE_UPDATE_INTERVAL = 0.08
EDGEDECAL_BEVEL_SYNC_CACHE = {}
EDGEDECAL_BEVEL_SYNC_RUNNING = False
EDGEDECAL_SCENE_LIVE_SYNC_CACHE = {}
EDGEDECAL_SCENE_LIVE_SYNC_RUNNING = False
EDGEDECAL_SCENE_LIVE_SYNC_INTERVAL = 0.15
EDGEDECAL_SCENE_SETTINGS_COPYING = False
EDGEDECAL_SETTINGS_SYNCING = False
EDGEDECAL_REGENERATING_DEPTH = 0


def regenerating_active():
    return EDGEDECAL_REGENERATING_DEPTH > 0


def queue_decal_live_update(decal_obj, fast_geometry_only=False):
    """Queue one rebuild, throttling Fast Geometry instead of debouncing it."""
    global EDGEDECAL_LIVE_UPDATE_RUNNING

    if decal_obj is None:
        return None
    if decal_obj.get("edge_decal_mode") == "BOOLEAN":
        # Boolean layers are intentionally manual: their source modifier stack
        # is sampled only when Generate From Booleans is clicked again.
        return None

    now = time.monotonic()
    object_name = decal_obj.name_full
    if fast_geometry_only:
        deadline = now + EDGEDECAL_FAST_LIVE_UPDATE_INTERVAL
        existing_deadline = EDGEDECAL_LIVE_UPDATE_QUEUE.get(object_name)
        if existing_deadline is not None:
            # Preserve the first deadline while a slider keeps producing
            # events. The queued rebuild therefore runs during the drag and
            # consumes the latest copied settings instead of waiting for the
            # user to stop moving the control.
            deadline = min(existing_deadline, deadline)
    else:
        # Full-quality updates keep the historical trailing debounce so heavy
        # UV processing does not run repeatedly during one slider gesture.
        deadline = now + EDGEDECAL_LIVE_UPDATE_DELAY

    EDGEDECAL_LIVE_UPDATE_QUEUE[object_name] = deadline

    if not EDGEDECAL_LIVE_UPDATE_RUNNING:
        EDGEDECAL_LIVE_UPDATE_RUNNING = True
        if not bpy.app.timers.is_registered(process_decal_live_update_queue):
            bpy.app.timers.register(
                process_decal_live_update_queue,
                first_interval=(
                    EDGEDECAL_FAST_LIVE_UPDATE_INTERVAL
                    if fast_geometry_only
                    else EDGEDECAL_LIVE_UPDATE_DELAY
                ),
            )

    return deadline


def push_regenerating():
    global EDGEDECAL_REGENERATING_DEPTH
    EDGEDECAL_REGENERATING_DEPTH += 1


def pop_regenerating():
    global EDGEDECAL_REGENERATING_DEPTH
    EDGEDECAL_REGENERATING_DEPTH = max(0, EDGEDECAL_REGENERATING_DEPTH - 1)


NORMAL_MODE_ITEMS = (
    (
        "SHADE_SMOOTH",
        "Shade Smooth",
        "Use standard smooth shading without a custom normal modifier",
    ),
    (
        "FACE_AREA",
        "Face Area Averaged",
        "Shade smooth and average normals using neighboring face areas",
    ),
    (
        "WEIGHTED",
        "Weighted Normals",
        "Shade smooth and use face-area plus corner-angle weighted normals",
    ),
)


CREVICE_DETECTION_ITEMS = (
    (
        "AO",
        "Ambient Occlusion",
        "Use local raycast occlusion around each edge or bevel band",
    ),
    (
        "GEOMETRY",
        "Geometry",
        "Use the previous face-normal and corner-angle classification",
    ),
)


def force_object_mode(context):
    """Return to Object Mode, ignoring failures from invalid mode transitions."""
    try:
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except (RuntimeError, ReferenceError):
        pass


def ensure_viewport_mode_coherent(context):
    """Fix Blender's stuck state when one mesh is in Edit Mode but another is active."""
    try:
        if context.mode == "OBJECT":
            return
        edit_obj = context.edit_object
        active = context.view_layer.objects.active
        if edit_obj is not None and active is not None and edit_obj != active:
            bpy.ops.object.mode_set(mode="OBJECT")
    except (RuntimeError, ReferenceError):
        pass


def select_only_object(context, obj):
    """Leave Edit Mode and make exactly one object selected and active."""
    force_object_mode(context)

    for candidate in context.view_layer.objects:
        try:
            candidate.select_set(False)
        except RuntimeError:
            pass

    if obj is not None and obj.name in context.view_layer.objects:
        obj.select_set(True)
        context.view_layer.objects.active = obj

    ensure_viewport_mode_coherent(context)


def clear_mesh_selection(mesh):
    """Clear selection flags without rebuilding or reordering the mesh.

    Source edges are persisted on decal layers by mesh index.  Rebuilding the
    source through ``BMesh.to_mesh`` merely to clear selection can rewrite
    element order after Edit Mode, invalidating those stored indices.  Direct
    RNA selection flags are sufficient in Object Mode and leave topology
    completely untouched.
    """
    if mesh is None or getattr(mesh, "is_editmode", False):
        return

    for vertex in mesh.vertices:
        vertex.select = False
    for edge in mesh.edges:
        edge.select = False
    for polygon in mesh.polygons:
        polygon.select = False

    mesh.update()


def source_mesh_edge_order_signature(source_obj):
    """Return a compact fingerprint for source edge-index identity.

    The signature deliberately ignores vertex coordinates: moving existing
    geometry does not invalidate a layer, while adding/removing/reordering
    vertices or edges does.  Endpoint order inside an edge is normalized so a
    harmless direction flip does not produce a false topology warning.
    """
    if (
        source_obj is None
        or getattr(source_obj, "type", None) != "MESH"
        or getattr(source_obj, "data", None) is None
    ):
        return ""

    mesh = source_obj.data
    endpoint_pairs = []

    if getattr(mesh, "is_editmode", False):
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.index_update()
        for edge in bm.edges:
            endpoint_pairs.append(sorted((
                int(edge.verts[0].index),
                int(edge.verts[1].index),
            )))
        vertex_count = len(bm.verts)
    else:
        endpoint_pairs = [
            sorted((int(edge.vertices[0]), int(edge.vertices[1])))
            for edge in mesh.edges
        ]
        vertex_count = len(mesh.vertices)

    # Deterministic 64-bit FNV-1a style mixing avoids storing a potentially
    # very large JSON edge table in every layer custom property.
    value = 1469598103934665603
    mask = (1 << 64) - 1
    for component in (
        vertex_count,
        len(endpoint_pairs),
        *(item for pair in endpoint_pairs for item in pair),
    ):
        value ^= int(component) & mask
        value = (value * 1099511628211) & mask

    return f"{vertex_count}:{len(endpoint_pairs)}:{value:016x}"


def decal_layer_source_edge_order_is_current(decal_obj, source_obj):
    """Return False only when a recorded layer fingerprint is now stale."""
    if decal_obj is None or source_obj is None:
        return True

    stored = str(
        decal_obj.get("edge_decal_source_edge_order_signature", "")
    )
    if not stored:
        # Legacy layers have no fingerprint.  Adopt the current topology so
        # future changes can be detected without breaking existing files.
        current = source_mesh_edge_order_signature(source_obj)
        if current:
            decal_obj["edge_decal_source_edge_order_signature"] = current
        return True

    current = source_mesh_edge_order_signature(source_obj)
    return not current or stored == current


def resolve_generated_decal_for_source(
    source_obj,
    context=None,
    mode=None,
):
    """Find the populated decal layer for a source mesh after generation."""
    if source_obj is None:
        return None

    if context is None:
        context = bpy.context

    force_object_mode(context)
    ensure_viewport_mode_coherent(context)

    candidates = []

    active_layer = active_decal_layer_for_source(
        source_obj,
        context=context,
    )
    if active_layer is not None:
        candidates.append(active_layer)

    stored_layer = stored_active_decal_layer_for_source(source_obj)
    if stored_layer is not None and stored_layer not in candidates:
        candidates.append(stored_layer)

    for layer_obj in all_decal_layers_for_source(source_obj):
        if layer_obj not in candidates:
            candidates.append(layer_obj)

    for layer_obj in candidates:
        if layer_obj.data is None or len(layer_obj.data.polygons) == 0:
            continue
        if (
            mode is not None
            and layer_obj.get("edge_decal_mode", "SHARP_EDGES") != mode
        ):
            continue
        return layer_obj

    populated = [
        layer_obj
        for layer_obj in all_decal_layers_for_source(source_obj)
        if layer_obj.data is not None and len(layer_obj.data.polygons) > 0
        and (
            mode is None
            or layer_obj.get("edge_decal_mode", "SHARP_EDGES") == mode
        )
    ]
    if not populated:
        return None

    return max(
        populated,
        key=lambda obj: int(obj.get("edge_decal_index", 0)),
    )


def _parse_source_index_tokens(raw):
    indices = []
    if raw is None:
        return indices

    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            try:
                indices.append(int(item))
            except (TypeError, ValueError):
                pass
        return sorted(set(indices))

    text = str(raw).strip()
    if not text:
        return indices

    if text.startswith("[") or text.startswith("("):
        try:
            loaded = json.loads(text.replace("(", "[").replace(")", "]"))
            if isinstance(loaded, (list, tuple, set)):
                return _parse_source_index_tokens(list(loaded))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    for token in text.replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            indices.append(int(float(token)))
        except (TypeError, ValueError):
            pass
    return sorted(set(indices))


def layer_has_geometry_for_source(layer_obj, source_obj=None):
    if (
        layer_obj is None
        or layer_obj.type != "MESH"
        or not layer_obj.get("edge_decal_generated")
        or layer_obj.data is None
        or len(layer_obj.data.polygons) == 0
    ):
        return False

    if source_obj is None:
        return True

    if decal_layer_source_matches(layer_obj, source_obj):
        return True

    stored_source = str(layer_obj.get("edge_decal_source", ""))
    return stored_source in {
        source_obj.name_full,
        source_obj.name,
    }


def sync_stored_indices_from_object_props(decal_obj, source_obj=None):
    """Merge every known source-index storage location onto one decal layer."""
    if decal_obj is None:
        return []

    if source_obj is None:
        data = getattr(decal_obj, "edge_decal_object_settings", None)
        source_obj = getattr(data, "source_object", None)
        if source_obj is None or source_obj.name not in bpy.data.objects:
            source_obj = find_object_by_name_or_full(
                decal_obj.get("edge_decal_source", "")
            )

    combined = set()
    data = getattr(decal_obj, "edge_decal_object_settings", None)

    for raw in (
        decal_obj.get("edge_decal_source_indices"),
        decal_obj.get("edge_decal_base_source_indices"),
        getattr(data, "source_indices", "") if data is not None else "",
    ):
        combined.update(_parse_source_index_tokens(raw))

    indices = sorted(combined)
    if indices:
        set_stored_source_indices(decal_obj, indices, source_obj=source_obj)
    return indices


def resolve_regeneration_source_indices(decal_obj, source_obj, scene_settings):
    _ = scene_settings
    indices = sync_stored_indices_from_object_props(decal_obj, source_obj)
    if indices or parsed_interactive_stroke_edges(decal_obj):
        return indices
    return []



def populated_decal_layers_for_source(source_obj, include_locked=True):
    """Return decal layers that actually contain generated geometry."""
    return [
        layer_obj
        for layer_obj in sorted_decal_layers_for_source(source_obj)
        if (
            include_locked
            or not layer_obj.get("edge_decal_locked", False)
        )
        and layer_obj.data is not None
        and len(layer_obj.data.polygons) > 0
    ]


def resolved_editable_decal_layer(context, source_obj=None):
    """Return the decal layer sidebar actions should target."""
    if source_obj is None:
        source_obj = resolve_live_update_source(context)

    active_obj = getattr(context, "active_object", None)
    if (
        active_obj is not None
        and active_obj.get("edge_decal_generated")
        and layer_has_geometry_for_source(active_obj, source_obj)
    ):
        return active_obj

    if source_obj is not None:
        ui_layer = selected_decal_layer_from_ui(source_obj)
        if layer_has_geometry_for_source(ui_layer, source_obj):
            return ui_layer

        stored_layer = stored_active_decal_layer_for_source(
            source_obj,
            include_locked=False,
        )
        if layer_has_geometry_for_source(stored_layer, source_obj):
            return stored_layer

        populated = populated_decal_layers_for_source(
            source_obj,
            include_locked=False,
        )
        if populated:
            return populated[-1]

    return None


def backup_decal_uvs(decal_obj, generated_uvs):
    if decal_obj is None or not generated_uvs:
        return

    try:
        decal_obj["edge_decal_uv_backup"] = json.dumps(
            [
                [list(uv) for uv in polygon_uvs]
                for polygon_uvs in generated_uvs
            ]
        )
    except (TypeError, ValueError):
        pass


def decal_uvs_are_valid(decal_obj):
    mesh = getattr(decal_obj, "data", None)
    if mesh is None or not mesh.uv_layers:
        return False

    uv_layer = mesh.uv_layers.active or mesh.uv_layers[0]
    if uv_layer is None or not uv_layer.data:
        return False

    non_zero = sum(
        1
        for loop in uv_layer.data
        if loop.uv.length_squared > 1.0e-12
    )
    return non_zero >= max(1, len(uv_layer.data) // 8)


def restore_decal_uv_backup(decal_obj):
    if decal_obj is None:
        return False

    raw = decal_obj.get("edge_decal_uv_backup", "")
    if not raw:
        return False

    try:
        generated_uvs = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False

    return restore_generated_uvs_to_decal(decal_obj, generated_uvs)


def restore_generated_uvs_to_decal(decal_obj, generated_uvs):
    """Restore strip UVs after unwrap/quadrify on generated decal layers."""
    if (
        decal_obj is None
        or decal_obj.data is None
        or not generated_uvs
        or len(generated_uvs) != len(decal_obj.data.polygons)
    ):
        return False

    mesh = decal_obj.data
    ensure_fn = globals().get("ensure_decal_mesh_uv_layers")
    if ensure_fn is not None:
        ensure_fn(mesh)
    elif not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")

    uv_layer = mesh.uv_layers.active
    if uv_layer is None:
        return False

    for polygon, polygon_uvs in zip(mesh.polygons, generated_uvs):
        if len(polygon_uvs) != len(polygon.loop_indices):
            continue
        for loop_index, uv in zip(polygon.loop_indices, polygon_uvs):
            uv_layer.data[loop_index].uv = uv

    mesh.update()
    return True


def apply_decal_mesh_material_direct(decal_obj, material):
    """Assign one material directly on mesh faces without RNA update callbacks."""
    if decal_obj is None or decal_obj.data is None:
        return None

    mesh = decal_obj.data
    mesh.materials.clear()
    if material is not None:
        mesh.materials.append(material)
        for polygon in mesh.polygons:
            polygon.material_index = 0
    mesh.update()
    return material



def complete_generated_decal_result(context, source_obj, decal_obj, settings=None):
    """Finalize one generated decal layer for viewport editing and live update."""
    if source_obj is None or decal_obj is None:
        return None

    if settings is None:
        scene = getattr(context, "scene", None)
        settings = getattr(scene, "edge_decal_settings", None) if scene else None
    if settings is None:
        return decal_obj

    finalize_generated_decal_layer(source_obj, decal_obj, settings)

    sync_fn = globals().get("sync_source_layer_ui")
    if sync_fn is not None:
        sync_fn(source_obj, active_layer=decal_obj)

    scene_sync_fn = globals().get("sync_scene_settings_from_decal_layer")
    if scene_sync_fn is not None:
        scene_sync_fn(context, source_obj, decal_obj)

    finish_decal_generation(context, source_obj, decal_obj)
    return decal_obj


def finish_decal_generation(context, source_obj, decal_obj):
    """
    Leave generation with a clean viewport state.

    The source mesh must not keep edge/face selection from the generation
    prep pass, and the finished decal object should be the active result.
    """
    force_object_mode(context)

    if source_obj is not None and source_obj.data is not None:
        clear_mesh_selection(source_obj.data)

    if decal_obj is not None and source_obj is not None:
        signature = source_mesh_edge_order_signature(source_obj)
        if signature:
            decal_obj["edge_decal_source_edge_order_signature"] = signature

    if (
        decal_obj is not None
        and decal_obj.get("edge_decal_generated")
        and decal_obj.data is not None
    ):
        scene = getattr(context, "scene", None)
        settings = getattr(scene, "edge_decal_settings", None) if scene else None
        ensure_fn = globals().get("ensure_decal_mesh_uv_layers")
        if ensure_fn is not None:
            ensure_fn(decal_obj.data)
        if settings is not None:
            apply_scene_decal_material(decal_obj, settings)
        decal_obj.update_tag(refresh={"DATA"})

    select_only_object(
        context,
        decal_obj if decal_obj is not None else source_obj,
    )


EDGEDECAL_PENDING_LAYER_REPAIRS = set()


def schedule_decal_layer_repair(source_obj):
    """Repair stale layer metadata outside restricted UI draw contexts."""
    if source_obj is None:
        return

    source_name = source_obj.name_full

    if source_name in EDGEDECAL_PENDING_LAYER_REPAIRS:
        return

    EDGEDECAL_PENDING_LAYER_REPAIRS.add(source_name)

    def _repair_once():
        EDGEDECAL_PENDING_LAYER_REPAIRS.discard(source_name)
        obj = find_object_by_name_or_full(source_name)

        if obj is None:
            return None

        repair_fn = globals().get("repair_decal_layers_for_source")

        if repair_fn is not None:
            repair_fn(obj, bpy.context, activate=False)

        sync_fn = globals().get("schedule_source_layer_ui_sync")

        if sync_fn is not None:
            sync_fn(obj)

        return None

    bpy.app.timers.register(_repair_once, first_interval=0.0)


def remove_edge_decal_normal_modifiers(obj):
    """Remove only normal modifiers owned by this add-on."""
    controlled_names = {
        "Area Weighted Normals",
        "Edge Decal Face Area Normals",
        "Edge Decal Weighted Normals",
    }

    for modifier in list(obj.modifiers):
        if (
            modifier.type == "WEIGHTED_NORMAL"
            and modifier.name in controlled_names
        ):
            obj.modifiers.remove(modifier)


def apply_decal_normal_settings(
    decal_obj,
    normal_mode,
    keep_sharp=False,
    weight=50.0,
    threshold=0.01,
):
    """Apply the selected shading mode without touching unrelated modifiers."""
    remove_edge_decal_normal_modifiers(decal_obj)

    for polygon in decal_obj.data.polygons:
        polygon.use_smooth = True

    if normal_mode == "SHADE_SMOOTH":
        decal_obj.data.update()
        return

    modifier_name = (
        "Edge Decal Face Area Normals"
        if normal_mode == "FACE_AREA"
        else "Edge Decal Weighted Normals"
    )
    modifier = decal_obj.modifiers.new(
        modifier_name,
        "WEIGHTED_NORMAL",
    )

    if hasattr(modifier, "mode"):
        modifier.mode = (
            "FACE_AREA"
            if normal_mode == "FACE_AREA"
            else "FACE_AREA_WITH_ANGLE"
        )

    if hasattr(modifier, "keep_sharp"):
        modifier.keep_sharp = keep_sharp

    if hasattr(modifier, "weight"):
        modifier.weight = max(
            1,
            min(100, int(round(weight))),
        )

    if hasattr(modifier, "thresh"):
        modifier.thresh = threshold

    decal_obj.data.update()



def active_generated_decal(context):
    obj = getattr(context, "active_object", None)
    return obj if (
        obj is not None
        and obj.type == "MESH"
        and obj.get("edge_decal_generated")
    ) else None



def find_object_by_name_or_full(name):
    """Resolve a Blender object from either its local name or name_full."""
    if not name:
        return None

    obj = bpy.data.objects.get(name)
    if obj is not None:
        return obj

    for candidate in bpy.data.objects:
        if candidate.name_full == name:
            return candidate
    return None


def object_name_exists(name):
    """Return whether an object name still resolves in bpy.data.objects."""
    return find_object_by_name_or_full(name) is not None


def selected_decal_layer_from_ui(source_obj):
    """Resolve the decal layer selected in the source mesh UIList."""
    if source_obj is None or source_obj.type != "MESH":
        return None
    if not (
        hasattr(source_obj, "edge_decal_layers_ui")
        and hasattr(source_obj, "edge_decal_layer_index")
    ):
        return None

    ui = source_obj.edge_decal_layers_ui
    index = int(source_obj.edge_decal_layer_index)
    if not ui or index < 0 or index >= len(ui):
        return None

    layer_obj = ui[index].layer_object
    if layer_has_geometry_for_source(layer_obj, source_obj):
        return layer_obj
    if not decal_layer_is_valid(layer_obj, source_obj):
        return None
    return layer_obj


def decal_layer_is_valid(layer_obj, source_obj=None, assume_in_object_data=False):
    """Return whether an object is still a usable decal layer for a source mesh."""
    if layer_obj is None:
        return False
    try:
        object_name = layer_obj.name
    except ReferenceError:
        return False
    # Callers iterating a registry or ``bpy.data.objects`` already know the
    # object came from Blender's live object database. Repeating a name lookup
    # for every candidate makes a scene scan quadratic because
    # ``bpy_prop_collection`` name lookup is linear in large files.
    if not assume_in_object_data and object_name not in bpy.data.objects:
        return False
    # Viewport Delete can unlink an object from every collection while leaving
    # its datablock in ``bpy.data.objects`` until Blender purges orphans. Such
    # an object is not in any scene/view layer and cannot be a generation or
    # interactive-merge target.
    if not getattr(layer_obj, "users_collection", ()):
        return False
    if layer_obj.get("edge_decal_interactive_backup", False):
        return False
    if layer_obj.type != "MESH" or not layer_obj.get("edge_decal_generated"):
        return False
    if source_obj is not None and not decal_layer_source_matches(
        layer_obj,
        source_obj,
    ):
        return False
    return True


def source_mesh_needs_layer_repair(source_obj):
    """Return whether a source mesh still has stale layer/UI metadata."""
    if (
        source_obj is None
        or source_obj.type != "MESH"
        or source_obj.get("edge_decal_generated")
    ):
        return False

    layers = list(iter_generated_decals(source_obj=source_obj))
    valid_names = {layer.name_full for layer in layers}
    active_name = str(source_obj.get("edge_decal_active_layer", ""))

    if active_name and (
        active_name not in valid_names
        or not object_name_exists(active_name)
    ):
        return True

    if not layer_ui_props_available(source_obj):
        return False

    ui = source_obj.edge_decal_layers_ui
    if len(ui) != len(layers):
        return True
    return any(
        not decal_layer_is_valid(item.layer_object, source_obj)
        for item in ui
    )


def ensure_source_decal_layers_ready(source_obj, context=None):
    """Repair stale active-layer/UI state before generation or live update."""
    if source_obj is None or source_obj.get("edge_decal_generated"):
        return None

    repair_fn = globals().get("repair_decal_layers_for_source")
    if repair_fn is None:
        return None

    if source_mesh_needs_layer_repair(source_obj):
        return repair_fn(source_obj, context, activate=False)

    return stored_active_decal_layer_for_source(source_obj)


def stored_active_decal_layer_for_source(source_obj, include_locked=True):
    """Resolve the decal layer recorded on the source mesh custom property."""
    if source_obj is None or source_obj.type != "MESH":
        return None

    active_name = str(source_obj.get("edge_decal_active_layer", ""))
    active_obj = find_object_by_name_or_full(active_name)
    if decal_layer_is_valid(active_obj, source_obj):
        if not include_locked and active_obj.get("edge_decal_locked", False):
            return None
        return active_obj
    return None


def _legacy_active_decal_layer_tail(source_obj, include_locked=True, context=None):
    """Previous fallback path kept for reference during refactor."""
    layer_obj = stored_active_decal_layer_for_source(source_obj, include_locked)
    if layer_obj is not None:
        return layer_obj

    layer_obj = selected_decal_layer_from_ui(source_obj)
    if decal_layer_is_valid(layer_obj, source_obj):
        if include_locked or not layer_obj.get("edge_decal_locked", False):
            return layer_obj

    for layer_obj in sorted_decal_layers_for_source(source_obj):
        if include_locked or not layer_obj.get("edge_decal_locked", False):
            return layer_obj

    return None


def active_decal_layer_for_source(source_obj, include_locked=True, context=None):
    """Resolve the decal layer sidebar edits and live update should target."""
    if source_obj is None or source_obj.type != "MESH":
        return None

    if context is None:
        context = bpy.context

    active_obj = getattr(context, "active_object", None)
    if decal_layer_is_valid(active_obj, source_obj):
        if include_locked or not active_obj.get("edge_decal_locked", False):
            return active_obj

    # Respect the stored active layer even when it is still an empty shell.
    layer_obj = stored_active_decal_layer_for_source(source_obj, include_locked)
    if layer_obj is not None:
        return layer_obj

    layer_obj = selected_decal_layer_from_ui(source_obj)
    if decal_layer_is_valid(layer_obj, source_obj):
        if include_locked or not layer_obj.get("edge_decal_locked", False):
            return layer_obj

    populated = populated_decal_layers_for_source(
        source_obj,
        include_locked=include_locked,
    )
    if populated:
        return populated[-1]

    for layer_obj in sorted_decal_layers_for_source(source_obj):
        if include_locked or not layer_obj.get("edge_decal_locked", False):
            return layer_obj

    return None


def decal_layer_source_matches(layer_obj, source_obj):
    if source_obj is None:
        return True

    # Generated decals are parented directly to their source. Blender repairs
    # that hierarchy correctly when a source and its decal are duplicated,
    # while copied PointerProperty/custom-property metadata still references
    # the original source. Treat a valid source parent as authoritative so one
    # copied decal cannot appear in both the copied and original layer stacks.
    parent = getattr(layer_obj, "parent", None)
    if (
        parent is not None
        and getattr(parent, "type", None) == "MESH"
        and not parent.get("edge_decal_generated")
    ):
        return parent == source_obj

    data = getattr(layer_obj, "edge_decal_object_settings", None)
    source_ref = (
        getattr(data, "source_object", None)
        if data is not None
        else None
    )

    if source_ref is not None:
        try:
            if source_ref == source_obj:
                return True
            if source_ref.name_full == source_obj.name_full:
                return True
        except ReferenceError:
            pass

    stored_source = str(layer_obj.get("edge_decal_source", ""))
    return stored_source in {
        source_obj.name_full,
        source_obj.name,
    }


def all_decal_layers_for_source(source_obj):
    """Return every generated decal object associated with one source mesh."""
    if source_obj is None:
        return []

    registry_fn = globals().get("registered_decal_layers_for_source")
    if registry_fn is not None:
        registered = registry_fn(source_obj)
        if registered is not None:
            return sorted(
                registered,
                key=lambda obj: int(obj.get("edge_decal_index", 0)),
            )

    collection = bpy.data.collections.get(COLLECTION_NAME)
    object_pool = (
        collection.all_objects
        if collection is not None
        else bpy.data.objects
    )
    layers = []

    for candidate in object_pool:
        if not decal_layer_is_valid(candidate, source_obj):
            continue
        layers.append(candidate)

    seen = {layer.name_full for layer in layers}
    for candidate in bpy.data.objects:
        if candidate.name_full in seen:
            continue
        if not decal_layer_is_valid(candidate, source_obj):
            continue
        if getattr(candidate, "parent", None) != source_obj:
            continue
        layers.append(candidate)
        seen.add(candidate.name_full)

    layers.sort(key=lambda obj: int(obj.get("edge_decal_index", 0)))
    return layers


def sync_decal_layer_source_reference(layer_obj, source_obj):
    if layer_obj is None or source_obj is None:
        return

    layer_obj["edge_decal_source"] = source_obj.name_full

    if hasattr(layer_obj, "edge_decal_object_settings"):
        layer_obj.edge_decal_object_settings.source_object = source_obj


def repair_duplicated_decal_source_ownership(layer_obj):
    """Rebind copied decal metadata to Blender's duplicated source parent."""
    if (
        layer_obj is None
        or not layer_obj.get("edge_decal_generated")
        or getattr(layer_obj, "type", None) != "MESH"
    ):
        return None

    source_obj = getattr(layer_obj, "parent", None)
    if (
        source_obj is None
        or getattr(source_obj, "type", None) != "MESH"
        or source_obj.get("edge_decal_generated")
    ):
        return None

    data = getattr(layer_obj, "edge_decal_object_settings", None)
    old_source = getattr(data, "source_object", None) if data is not None else None
    if old_source is None:
        old_source = find_object_by_name_or_full(
            str(layer_obj.get("edge_decal_source", ""))
        )

    stored_source_name = str(layer_obj.get("edge_decal_source", ""))
    shrinkwrap = source_targeted_decal_shrinkwrap(layer_obj)
    needs_rebind = bool(
        old_source != source_obj
        or stored_source_name != source_obj.name_full
        or (shrinkwrap is not None and shrinkwrap.target != source_obj)
    )
    if not needs_rebind:
        return None

    layer_obj["edge_decal_source"] = source_obj.name_full
    if data is not None:
        global EDGEDECAL_SETTINGS_SYNCING
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            data.source_object = source_obj
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing

    if shrinkwrap is not None:
        shrinkwrap.target = source_obj

    signature = source_mesh_edge_order_signature(source_obj)
    if signature:
        layer_obj["edge_decal_source_edge_order_signature"] = signature

    return old_source, source_obj


def layer_is_empty_decal_shell(layer_obj):
    if layer_obj is None or layer_obj.data is None:
        return False

    return len(layer_obj.data.polygons) == 0


def find_generation_shell_layer(
    source_obj,
    context=None,
    include_locked=False,
):
    """Return the empty decal shell that should receive new geometry."""
    if source_obj is None:
        return None

    candidates = []

    active = stored_active_decal_layer_for_source(
        source_obj,
        include_locked=include_locked,
    )
    if active is not None:
        candidates.append(active)

    ui_layer = selected_decal_layer_from_ui(source_obj)
    if ui_layer is not None and ui_layer not in candidates:
        candidates.append(ui_layer)

    for layer_obj in all_decal_layers_for_source(source_obj):
        if layer_obj not in candidates:
            candidates.append(layer_obj)

    for layer_obj in candidates:
        if not include_locked and layer_obj.get("edge_decal_locked", False):
            continue

        sync_decal_layer_source_reference(layer_obj, source_obj)

        if not layer_is_empty_decal_shell(layer_obj):
            continue

        return layer_obj

    return None


def adopt_generated_decal_into_empty_shell(source_obj, generated_obj, context=None):
    """Move a standalone generated decal into a waiting empty shell layer."""
    if (
        generated_obj is None
        or source_obj is None
        or not generated_obj.get("edge_decal_generated")
    ):
        return generated_obj

    scene = getattr(context, "scene", None) if context is not None else None
    configure_decal_object(
        generated_obj,
        source_obj=source_obj,
        scene=scene,
    )

    shell = find_generation_shell_layer(
        source_obj,
        context=context,
        include_locked=False,
    )
    if (
        shell is None
        or shell is generated_obj
        or not layer_is_empty_decal_shell(shell)
    ):
        return generated_obj

    sync_decal_layer_source_reference(shell, source_obj)
    configure_decal_object(
        shell,
        source_obj=source_obj,
        scene=scene,
    )

    generated_mesh = generated_obj.data
    shell_mesh = shell.data
    shell.data = generated_mesh
    generated_obj.data = None

    shell["edge_decal_mode"] = generated_obj.get(
        "edge_decal_mode",
        shell.get("edge_decal_mode", "SHARP_EDGES"),
    )
    shell["edge_decal_generated"] = True
    shell["edge_decal_source"] = source_obj.name_full
    shell["edge_decal_index"] = int(
        shell.get("edge_decal_index", generated_obj.get("edge_decal_index", 0))
    )

    for key in (
        "edge_decal_last_uv_signature",
        "edge_decal_source_indices",
        "edge_decal_base_source_indices",
        "edge_decal_source_edge_order_signature",
        "edge_decal_uv_backup",
        "edge_decal_selection_mode",
        "edge_decal_selected_graph",
    ):
        if key in generated_obj:
            shell[key] = generated_obj[key]

    generated_data = generated_obj.edge_decal_object_settings
    shell_data = shell.edge_decal_object_settings
    global EDGEDECAL_SETTINGS_SYNCING
    EDGEDECAL_SETTINGS_SYNCING = True
    try:
        shell_data.initialized = False
        shell_data.live_update = False
        shell_data.selection_mode = generated_data.selection_mode
        shell_data.source_object = source_obj
        shell_data.source_material = generated_data.source_material
        shell_data.source_indices = generated_data.source_indices
        shell_data.decal_template_material = (
            generated_data.decal_template_material
        )
        shell_data.decal_material = generated_data.decal_material
        shell_data.match_source_material = (
            generated_data.match_source_material
        )

        for property_name in (
            "face_width",
            "relative_face_width",
            "randomize_face_width",
            "minimum_face_width",
            "maximum_face_width",
            "use_edge_split",
            "split_angle",
            "surface_offset",
            "uv_scale",
            "seed",
            "decal_amount",
            "edge_slice",
            "maximum_decal_length",
            "taper_sliced_ends",
            "slice_taper_length",
            "auto_trim_corner_ends",
            "corner_end_trim_multiplier",
            "crevice_removal",
            "crevice_detection_mode",
            "crevice_ao_distance",
            "crevice_ao_samples",
            "remove_short_edges",
            "minimum_edge_length",
            "minimum_length_per_edge",
            "randomize_horizontal_offset",
            "horizontal_randomize_amount",
            "auto_face_width",
            "auto_width_samples",
            "auto_width_clearance",
            "clamp_edge_overlaps",
            "overlap_clearance",
            "normal_mode",
            "normal_keep_sharp",
            "normal_weight",
            "normal_threshold",
            "use_face_loop_slide",
            "add_weld_modifier",
            "weld_distance",
            "add_center_displace_modifier",
            "center_displace_strength",
            "add_shrinkwrap_modifier",
            "add_subdivision_modifier",
            "add_decimate_modifier",
            "add_bevel_modifier",
            "bevel_edge_center",
            "center_bevel_width",
            "center_bevel_segments",
            "center_bevel_profile",
            "bevel_harden_normals",
            "bevel_angle",
            "uv_pin_indices",
        ):
            if hasattr(shell_data, property_name) and hasattr(generated_data, property_name):
                setattr(
                    shell_data,
                    property_name,
                    getattr(generated_data, property_name),
                )

        shell_data.initialized = True
        shell_data.live_update = True
    finally:
        EDGEDECAL_SETTINGS_SYNCING = False

    bpy.data.objects.remove(generated_obj, do_unlink=True)
    if shell_mesh is not None and shell_mesh.users == 0:
        bpy.data.meshes.remove(shell_mesh)

    set_active_decal_layer(source_obj, shell)
    return shell


def decal_layer_source_count(layer_obj):
    data = getattr(layer_obj, "edge_decal_object_settings", None)

    if data is not None:
        indices = parsed_source_indices(data, layer_obj)
        if indices:
            return len(indices)

    if layer_obj is not None and layer_obj.data is not None:
        return len(layer_obj.data.polygons)

    return 0


def resolve_generation_target_layer(
    source_obj,
    context=None,
    include_locked=False,
):
    """Return the decal layer shell generation should populate or merge into."""
    ensure_source_decal_layers_ready(source_obj, context)

    shell_layer = find_generation_shell_layer(
        source_obj,
        context=context,
        include_locked=include_locked,
    )
    if shell_layer is not None:
        return shell_layer

    return active_decal_layer_for_source(
        source_obj,
        include_locked=include_locked,
        context=context,
    )


def set_active_decal_layer(source_obj, decal_obj):
    if source_obj is None:
        return

    try:
        source_obj["edge_decal_active_layer"] = (
            decal_obj.name_full if decal_obj is not None else ""
        )
    except (AttributeError, TypeError):
        schedule_decal_layer_repair(source_obj)
        return

    if decal_obj is not None:
        register_fn = globals().get("register_decal_in_registry")
        if register_fn is not None:
            register_fn(decal_obj, source_obj)

    if hasattr(source_obj, "edge_decal_layers_ui"):
        sync_fn = globals().get("schedule_source_layer_ui_sync")
        if sync_fn is not None:
            sync_fn(source_obj)


def sorted_decal_layers_for_source(source_obj):
    """Return decal layers for a source mesh in UI stack order."""
    return sorted(
        iter_generated_decals(source_obj=source_obj),
        key=lambda obj: int(obj.get("edge_decal_index", 0)),
    )


def primary_generated_decal_for_source(source_obj, context=None):
    if source_obj is None or source_obj.type != "MESH":
        return None

    active_layer = active_decal_layer_for_source(source_obj, context=context)
    if active_layer is not None:
        return active_layer

    decals = list(iter_generated_decals(source_obj=source_obj))
    if not decals:
        return None

    decals.sort(key=lambda obj: int(obj.get("edge_decal_index", 0)))
    set_active_decal_layer(source_obj, decals[0])
    return decals[0]


def editable_generated_decal(context):
    return resolved_editable_decal_layer(context)


def resolve_live_update_source(context):
    """Return the source mesh whose active decal layer should receive live edits."""
    obj = getattr(context, "active_object", None)
    if obj is None:
        return None

    if obj.get("edge_decal_generated"):
        data = getattr(obj, "edge_decal_object_settings", None)
        source_obj = getattr(data, "source_object", None)
        if (
            source_obj is not None
            and source_obj.name in bpy.data.objects
            and source_obj.type == "MESH"
            and not source_obj.get("edge_decal_generated")
        ):
            return source_obj
        return None

    if obj.type == "MESH" and not obj.get("edge_decal_generated"):
        return obj

    return None


def finalize_generated_decal_layer(source_obj, decal_obj, settings):
    """Mark a freshly generated decal layer editable, shaded, and UV-ready."""
    if source_obj is None or decal_obj is None:
        return

    configure_decal_object(
        decal_obj,
        source_obj=source_obj,
        scene=getattr(bpy.context, "scene", None),
    )

    set_active_decal_layer(source_obj, decal_obj)
    data = decal_obj.edge_decal_object_settings
    data.initialized = True
    data.live_update = True

    context = bpy.context
    select_only_object(context, decal_obj)

    ensure_fn = globals().get("ensure_decal_mesh_uv_layers")
    if ensure_fn is not None and decal_obj.data is not None:
        ensure_fn(decal_obj.data)

    apply_scene_decal_material(decal_obj, settings)
    decal_obj.update_tag(refresh={"DATA"})


def apply_scene_settings_to_active_layer(context, scene_settings):
    """Copy scene sidebar values onto the active decal layer without regenerating."""
    source_obj = resolve_live_update_source(context)
    if source_obj is None or scene_settings is None:
        return None

    obj = active_decal_layer_for_source(
        source_obj,
        include_locked=False,
        context=context,
    )
    if obj is None:
        return None

    copy_scene_live_settings_to_decal(scene_settings, obj)
    # Empty layer shells still own their material state. Presets are commonly
    # selected before the first geometry is placed, so initialization must not
    # prevent the chosen material from being recorded on the active layer.
    if not decal_material_assignment_matches_scene(obj, scene_settings):
        apply_scene_decal_material(obj, scene_settings)

    EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
        scene_live_sync_cache_key(source_obj, obj)
    ] = scene_live_edit_signature(scene_settings)
    return obj


def decal_material_assignment_matches_scene(decal_obj, settings):
    """Return whether the layer already has the scene's material assignment."""
    if decal_obj is None or decal_obj.data is None or settings is None:
        return False

    data = getattr(decal_obj, "edge_decal_object_settings", None)
    if data is None:
        return False

    mesh = decal_obj.data
    if not getattr(settings, "use_material", True):
        return (
            getattr(data, "decal_material", None) is None
            and getattr(data, "decal_template_material", None) is None
            and len(mesh.materials) == 0
        )

    expected_template = getattr(settings, "decal_material", None)
    if expected_template is None and len(mesh.polygons) == 0:
        # Empty layer shells intentionally keep unloaded preset assets and the
        # generic fallback out of the blend until geometry is generated.
        return (
            getattr(data, "decal_material", None) is None
            and getattr(data, "decal_template_material", None) is None
            and len(mesh.materials) == 0
        )
    if expected_template is None:
        expected_template = bpy.data.materials.get(DEFAULT_MATERIAL_NAME)
    if expected_template is None:
        return False
    expected_template = root_decal_template_material(expected_template)

    assigned_material = getattr(data, "decal_material", None)
    assigned_template = (
        getattr(data, "decal_template_material", None)
        or root_decal_template_material(assigned_material)
    )
    base_assignment_matches = (
        root_decal_template_material(assigned_template) == expected_template
        and assigned_material is not None
        and len(mesh.materials) == 1
        and mesh.materials[0] == assigned_material
    )
    if not base_assignment_matches:
        return False

    should_match_source = bool(
        getattr(settings, "match_source_material", False)
    )
    assigned_is_matched = bool(
        assigned_material.get("edge_decal_source_matched")
    )
    if not should_match_source:
        return assigned_material == expected_template and not assigned_is_matched

    source_material = getattr(data, "source_material", None)
    if source_material is None:
        source_material = active_source_material(
            getattr(data, "source_object", None)
        )
    if source_material is None:
        return assigned_material == expected_template

    return (
        assigned_is_matched
        and str(assigned_material.get("edge_decal_template_material_name", ""))
        == expected_template.name_full
        and str(assigned_material.get("edge_decal_source_material_name", ""))
        == source_material.name_full
    )


def schedule_decal_live_update(settings, context):
    """Queue a reliable live rebuild for object or scene-level settings."""
    if (
        EDGEDECAL_SCENE_SETTINGS_COPYING
        or EDGEDECAL_SETTINGS_SYNCING
        or regenerating_active()
    ):
        return

    scene = getattr(context, "scene", None)
    scene_settings = getattr(scene, "edge_decal_settings", None) if scene else None

    # The modern UI edits the scene settings while the source mesh remains
    # selected. Route those callbacks directly to the active decal layer rather
    # than waiting for the polling timer or requiring the scene property group
    # itself to be initialized.
    if settings == scene_settings:
        if EDGEDECAL_INTERACTIVE_RUNNING:
            apply_scene_settings_to_active_layer(context, scene_settings)
            return

        source_obj = resolve_live_update_source(context)
        if source_obj is None:
            return

        obj = active_decal_layer_for_source(
            source_obj,
            include_locked=False,
            context=context,
        )
        if obj is None:
            return

        # Material assignment is independent of generated geometry. In
        # particular, applying a preset to a new empty layer must update the
        # layer now instead of leaving its previous template material behind.
        if not decal_material_assignment_matches_scene(obj, scene_settings):
            apply_scene_decal_material(obj, scene_settings)

        data = obj.edge_decal_object_settings
        if (
            obj.data is None
            or len(obj.data.polygons) == 0
            or not getattr(data, "initialized", False)
            or not getattr(data, "live_update", False)
            or not decal_has_regeneratable_source_data(obj)
        ):
            return

        copy_scene_live_settings_to_decal(scene_settings, obj)
        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
            scene_live_sync_cache_key(source_obj, obj)
        ] = scene_live_edit_signature(scene_settings)
    else:
        # Object-property callbacks only apply while a decal actor is selected.
        # Scene sidebar edits are owned exclusively by edge_decal_scene_live_sync_timer.
        active_obj = getattr(context, "active_object", None)
        if (
            active_obj is None
            or active_obj.type != "MESH"
            or not active_obj.get("edge_decal_generated")
        ):
            return

        if not getattr(settings, "initialized", False):
            return
        if not getattr(settings, "live_update", False):
            return
        obj = editable_generated_decal(context)
        if obj is None:
            return

    queue_decal_live_update(
        obj,
        fast_geometry_only=bool(
            getattr(scene_settings, "fast_geometry_only", False)
        ),
    )


def schedule_scene_decal_live_update(self, context):
    """Route scene-level slider edits to the active decal layer immediately."""
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    schedule_decal_live_update(scene.edge_decal_settings, context)


def enable_second_uv_for_material_matching(settings):
    """Enable the UV output required by source-matched image textures."""
    if settings is None or not bool(
        getattr(settings, "match_source_material", False)
    ):
        return False

    changed = False
    if hasattr(settings, "auto_unwrap_uvs") and not settings.auto_unwrap_uvs:
        settings.auto_unwrap_uvs = True
        changed = True
    if hasattr(settings, "generate_second_uv") and not settings.generate_second_uv:
        settings.generate_second_uv = True
        changed = True
    return changed


def update_scene_match_source_material(settings, context):
    """Switch the active layer's material mode without rebuilding geometry."""
    if (
        EDGEDECAL_SCENE_SETTINGS_COPYING
        or EDGEDECAL_SETTINGS_SYNCING
        or regenerating_active()
    ):
        return

    enable_second_uv_for_material_matching(settings)

    source_obj = resolve_live_update_source(context)
    if source_obj is None:
        return
    decal_obj = active_decal_layer_for_source(
        source_obj,
        include_locked=False,
        context=context,
    )
    if decal_obj is None:
        return

    apply_scene_decal_material(decal_obj, settings)
    EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
        scene_live_sync_cache_key(source_obj, decal_obj)
    ] = scene_live_edit_signature(settings)


def process_decal_live_update_queue():
    global EDGEDECAL_LIVE_UPDATE_RUNNING

    context = bpy.context

    # Never hijack mode/selection while the user is editing mesh geometry.
    if context.mode == "EDIT_MESH":
        return 0.1

    now = time.monotonic()
    ready = [
        name
        for name, deadline in EDGEDECAL_LIVE_UPDATE_QUEUE.items()
        if deadline <= now
    ]

    if not ready:
        if EDGEDECAL_LIVE_UPDATE_QUEUE:
            return 0.05
        EDGEDECAL_LIVE_UPDATE_RUNNING = False
        return None

    object_name = ready[-1]
    EDGEDECAL_LIVE_UPDATE_QUEUE.pop(object_name, None)
    obj = bpy.data.objects.get(object_name)

    if (
        obj is not None
        and obj.get("edge_decal_generated")
        and obj.data is not None
        and len(obj.data.polygons) > 0
        and getattr(obj.edge_decal_object_settings, "initialized", False)
        and decal_has_regeneratable_source_data(obj)
    ):
        push_regenerating()
        try:
            context = bpy.context
            active_before = getattr(context, "active_object", None)

            for selected in list(context.selected_objects):
                selected.select_set(False)
            obj.select_set(True)
            context.view_layer.objects.active = obj
            bpy.ops.object.edge_decal_regenerate(preview=False)

            if (
                active_before is not None
                and active_before.name in bpy.data.objects
            ):
                select_only_object(context, active_before)
            ensure_viewport_mode_coherent(context)
        except (RuntimeError, ReferenceError):
            ensure_viewport_mode_coherent(bpy.context)
        finally:
            pop_regenerating()

    if EDGEDECAL_LIVE_UPDATE_QUEUE:
        return 0.05

    EDGEDECAL_LIVE_UPDATE_RUNNING = False
    return None



def decal_uv_settings_signature(settings):
    """Return settings whose changes make raw loop-order UV restoration unsafe.

    UV coordinates may be copied back only when both UV-placement controls and
    topology-changing controls are unchanged. In particular, Decal Amount can
    keep the same total loop count while changing which strip owns each loop;
    copying by loop index in that case produces crossed/fanned UV islands.
    """
    return json.dumps({
        # Explicit UV-placement controls.
        "uv_scale": round(float(getattr(settings, "uv_scale", 1.0)), 8),
        "seed": int(getattr(settings, "seed", 1)),
        "randomize_horizontal_offset": bool(
            getattr(settings, "randomize_horizontal_offset", True)
        ),
        "horizontal_randomize_amount": round(float(
            getattr(settings, "horizontal_randomize_amount", 1.0)
        ), 8),
        "generate_second_uv": bool(
            getattr(settings, "generate_second_uv", False)
        ),

        # Controls that can add, remove, split, or reorder generated islands.
        "decal_amount": round(float(getattr(settings, "decal_amount", 1.0)), 8),
        "edge_slice": round(float(getattr(settings, "edge_slice", 0.0)), 8),
        "maximum_decal_length": round(
            float(getattr(settings, "maximum_decal_length", 0.0)), 8
        ),
        "use_edge_split": bool(
            getattr(settings, "use_edge_split", False)
        ),
        "split_angle": round(
            float(getattr(settings, "split_angle", radians(45.0))), 8
        ),
        "crevice_removal": round(
            float(getattr(settings, "crevice_removal", 0.0)), 8
        ),
        "crevice_detection_mode": str(
            getattr(settings, "crevice_detection_mode", "AO")
        ),
        "remove_short_edges": bool(
            getattr(settings, "remove_short_edges", False)
        ),
        "minimum_edge_length": round(
            float(getattr(settings, "minimum_edge_length", 0.05)), 8
        ),
        "minimum_length_per_edge": bool(
            getattr(settings, "minimum_length_per_edge", False)
        ),
        "auto_trim_corner_ends": bool(
            getattr(settings, "auto_trim_corner_ends", False)
        ),
        "corner_end_trim_multiplier": round(
            float(getattr(settings, "corner_end_trim_multiplier", 1.0)), 8
        ),
    }, sort_keys=True)





def store_decal_settings(
    decal_obj,
    source_obj,
    selection_mode,
    source_indices,
    scene_settings,
    values,
):
    global EDGEDECAL_SETTINGS_SYNCING
    data = decal_obj.edge_decal_object_settings
    EDGEDECAL_SETTINGS_SYNCING = True
    try:
        data.initialized = False
        data.live_update = False
        data.selection_mode = selection_mode
        data.source_object = source_obj
        data.source_material = active_source_material(source_obj)
        data.match_source_material = bool(
            getattr(scene_settings, "match_source_material", False)
        )
        set_stored_source_indices(
            decal_obj,
            source_indices,
            source_obj=source_obj,
        )
        decal_obj["edge_decal_selection_mode"] = selection_mode
        if decal_obj.data is not None and decal_obj.data.materials:
            data.decal_material = decal_obj.data.materials[0]
        elif getattr(scene_settings, "use_material", True):
            template_material = getattr(scene_settings, "decal_material", None)
            pending_fn = globals().get(
                "edge_decal_pending_preset_material_name"
            )
            pending_name = (
                pending_fn(getattr(bpy.context, "scene", None), scene_settings)
                if pending_fn is not None
                else ""
            )
            if template_material is None and not pending_name:
                template_material = get_or_create_material()
            if template_material is not None:
                data.decal_template_material = root_decal_template_material(
                    template_material
                )
                data.decal_material = template_material

        property_names = (
            "face_width",
            "relative_face_width",
            "randomize_face_width",
            "minimum_face_width",
            "maximum_face_width",
            "use_edge_split",
            "split_angle",
            "surface_offset",
            "uv_scale",
            "seed",
            "decal_amount",
            "crevice_removal",
            "crevice_detection_mode",
            "crevice_ao_distance",
            "crevice_ao_samples",
            "remove_short_edges",
            "minimum_edge_length",
            "minimum_length_per_edge",
            "randomize_horizontal_offset",
            "horizontal_randomize_amount",
            "auto_face_width",
            "auto_width_samples",
            "auto_width_clearance",
            "clamp_edge_overlaps",
            "overlap_clearance",
            "normal_mode",
            "normal_keep_sharp",
            "normal_weight",
            "normal_threshold",
            "use_face_loop_slide",
            "slice_taper_length",
            "auto_trim_corner_ends",
            "corner_end_trim_multiplier",
            "add_weld_modifier",
            "weld_distance",
            "add_center_displace_modifier",
            "center_displace_strength",
            "add_shrinkwrap_modifier",
            "add_subdivision_modifier",
            "add_decimate_modifier",
            "add_bevel_modifier",
            "bevel_edge_center",
            "center_bevel_width",
            "center_bevel_segments",
            "center_bevel_profile",
            "bevel_harden_normals",
            "bevel_angle",
        )

        for property_name in property_names:
            if property_name in values:
                setattr(data, property_name, values[property_name])
            elif hasattr(scene_settings, property_name):
                setattr(data, property_name, getattr(scene_settings, property_name))

        data.initialized = True
        data.live_update = True
        decal_obj["edge_decal_last_uv_signature"] = decal_uv_settings_signature(data)
    finally:
        EDGEDECAL_SETTINGS_SYNCING = False


def parsed_source_indices(data, decal_obj=None):
    if decal_obj is None and data is not None:
        decal_obj = getattr(data, "id_data", None)

    combined = set()
    if decal_obj is not None:
        for key in (
            "edge_decal_source_indices",
            "edge_decal_base_source_indices",
        ):
            combined.update(
                _parse_source_index_tokens(decal_obj.get(key))
            )

    if data is not None:
        combined.update(
            _parse_source_index_tokens(getattr(data, "source_indices", ""))
        )

    return sorted(combined)


def parsed_interactive_stroke_edges(decal_obj):
    if decal_obj is None:
        return []

    raw = decal_obj.get("edge_decal_interactive_strokes", "[]")
    if isinstance(raw, (list, tuple)):
        strokes = raw
    else:
        try:
            strokes = json.loads(raw)
        except Exception:
            return []

    edges = []
    for stroke in strokes:
        if not isinstance(stroke, dict):
            continue
        for edge_index in stroke.get("edges", []):
            try:
                edges.append(int(edge_index))
            except (TypeError, ValueError):
                pass
    return edges


def full_edge_selection_uses_graph(
    edge_indices,
    force_connected=False,
    slice_interval=None,
):
    """Return whether a complete selection needs branch-aware graph topology.

    This is shared by initial Interactive placement and later layer/live-update
    regeneration. In particular, a first Alt edge loop is a multi-edge graph
    even though it was not created by a merge operation.
    """
    if slice_interval is not None:
        return False

    unique_edges = set()
    for index in edge_indices or ():
        try:
            edge_index = int(index)
        except (TypeError, ValueError):
            continue
        if edge_index >= 0:
            unique_edges.add(edge_index)

    return bool(force_connected or len(unique_edges) > 1)


def decal_has_regeneratable_source_data(decal_obj):
    if decal_obj is None:
        return False

    if decal_obj.get("edge_decal_mode") == "INTERSECTIONS":
        source_a = find_object_by_name_or_full(
            decal_obj.get("edge_decal_intersection_source_a", "")
        )
        source_b = find_object_by_name_or_full(
            decal_obj.get("edge_decal_intersection_source_b", "")
        )
        return source_a is not None and source_b is not None

    if decal_obj.get("edge_decal_mode") == "BOOLEAN":
        source_obj = find_object_by_name_or_full(
            decal_obj.get(
                "edge_decal_boolean_source",
                decal_obj.get("edge_decal_source", ""),
            )
        )
        return bool(
            source_obj is not None
            and any(
                modifier.type == "BOOLEAN"
                and modifier.show_viewport
                and getattr(modifier, "operand_type", "OBJECT") == "OBJECT"
                and modifier.object is not None
                and modifier.object.type == "MESH"
                for modifier in source_obj.modifiers
            )
        )

    data = getattr(decal_obj, "edge_decal_object_settings", None)
    if data is not None and parsed_source_indices(data, decal_obj):
        return True
    return bool(parsed_interactive_stroke_edges(decal_obj))


def append_stored_source_indices(decal_obj, indices):
    combined = set(parsed_source_indices(decal_obj.edge_decal_object_settings))
    for index in indices or ():
        try:
            combined.add(int(index))
        except (TypeError, ValueError):
            pass
    set_stored_source_indices(decal_obj, sorted(combined))


def set_stored_source_indices(decal_obj, indices, source_obj=None):
    """Store a stable, unique source selection on a generated decal object."""
    joined = ",".join(
        str(index) for index in sorted(set(int(index) for index in indices))
    )
    decal_obj["edge_decal_source_indices"] = joined

    data = decal_obj.edge_decal_object_settings
    if source_obj is None:
        source_obj = getattr(data, "source_object", None)
        if source_obj is None or source_obj.name not in bpy.data.objects:
            source_obj = find_object_by_name_or_full(
                decal_obj.get("edge_decal_source", "")
            )

    if source_obj is not None:
        data.source_object = source_obj
        decal_obj["edge_decal_source"] = source_obj.name_full
        signature = source_mesh_edge_order_signature(source_obj)
        if signature:
            decal_obj["edge_decal_source_edge_order_signature"] = signature

    global EDGEDECAL_SETTINGS_SYNCING
    EDGEDECAL_SETTINGS_SYNCING = True
    try:
        data.source_indices = joined
    finally:
        EDGEDECAL_SETTINGS_SYNCING = False


def merge_stored_decal_source_data(existing_obj, new_obj):
    """Keep regeneration metadata valid when generated decal meshes are merged."""
    existing_data = existing_obj.edge_decal_object_settings
    new_data = new_obj.edge_decal_object_settings

    if not new_data.initialized:
        return

    if not existing_data.initialized:
        existing_data.initialized = False
        existing_data.live_update = False
        existing_data.selection_mode = new_data.selection_mode
        existing_data.source_object = new_data.source_object
        existing_data.source_material = new_data.source_material
        existing_data.decal_template_material = (
            new_data.decal_template_material
        )
        existing_data.match_source_material = (
            new_data.match_source_material
        )

        for property_name in (
            "face_width", "relative_face_width", "randomize_face_width",
            "minimum_face_width", "maximum_face_width",
            "use_edge_split", "split_angle",
            "surface_offset", "uv_scale", "seed",
            "decal_amount", "edge_slice", "maximum_decal_length",
            "taper_sliced_ends", "slice_taper_length",
            "auto_trim_corner_ends", "corner_end_trim_multiplier",
            "crevice_removal",
            "crevice_detection_mode", "crevice_ao_distance",
            "crevice_ao_samples", "remove_short_edges",
            "minimum_edge_length", "minimum_length_per_edge",
            "randomize_horizontal_offset", "horizontal_randomize_amount",
            "auto_face_width",
            "auto_width_samples", "auto_width_clearance",
            "clamp_edge_overlaps", "overlap_clearance", "normal_mode",
            "normal_keep_sharp", "normal_weight", "normal_threshold",
            "use_face_loop_slide",
        ):
            if hasattr(existing_data, property_name) and hasattr(new_data, property_name):
                setattr(existing_data, property_name, getattr(new_data, property_name))

        set_stored_source_indices(
            existing_obj,
            parsed_source_indices(new_data, new_obj),
        )
        if getattr(new_data, "decal_material", None) is not None:
            existing_data.decal_material = new_data.decal_material
        existing_data.initialized = True
        existing_data.live_update = True
        return

    same_source = existing_data.source_object == new_data.source_object
    same_mode = existing_data.selection_mode == new_data.selection_mode
    if not same_source or not same_mode:
        return

    combined = parsed_source_indices(existing_data, existing_obj)
    combined.extend(parsed_source_indices(new_data, new_obj))
    set_stored_source_indices(existing_obj, combined)


def update_decal_object_material(self, context):
    global EDGEDECAL_SCENE_SETTINGS_COPYING
    global EDGEDECAL_SETTINGS_SYNCING

    obj = getattr(self, "id_data", None)
    if obj is None or getattr(obj, "type", None) != "MESH":
        return

    material = getattr(self, "decal_material", None)
    if (
        not EDGEDECAL_SETTINGS_SYNCING
        and (
            material is None
            or not material.get("edge_decal_source_matched")
        )
    ):
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            self.decal_template_material = root_decal_template_material(material)
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing
    material_key = material.name_full if material is not None else ""
    previous_material_key = str(
        obj.get("edge_decal_uv_pin_material_name", "")
    )
    material_changed = material_key != previous_material_key
    obj["edge_decal_uv_pin_material_name"] = material_key
    obj.data.materials.clear()
    if material is not None:
        obj.data.materials.append(material)
        for polygon in obj.data.polygons:
            polygon.material_index = 0

    apply_pins_fn = globals().get(
        "apply_uv_pins_to_decal_objects_by_material"
    )
    scene = getattr(context, "scene", None) if context is not None else None
    if (
        apply_pins_fn is not None
        and scene is not None
        and material_changed
        and obj.get("edge_decal_generated")
        and obj.data.uv_layers.active is not None
    ):
        apply_pins_fn(scene, [obj])

    # The Active UV Pins picker edits the layer property directly, while
    # the width and other sidebar controls edit the scene property group. Keep
    # the scene-side material mirror current so the next scene-property update
    # cannot copy an older material back onto this layer.
    if (
        context is None
        or scene is None
        or EDGEDECAL_SCENE_SETTINGS_COPYING
        or EDGEDECAL_SETTINGS_SYNCING
        or regenerating_active()
        or not obj.get("edge_decal_generated")
    ):
        return

    source_obj = getattr(self, "source_object", None)
    if source_obj is None or source_obj.name not in bpy.data.objects:
        source_obj = find_object_by_name_or_full(
            str(obj.get("edge_decal_source", ""))
        )
    if source_obj is None:
        return

    if resolve_live_update_source(context) != source_obj:
        return

    active_layer = active_decal_layer_for_source(
        source_obj,
        context=context,
    )
    if active_layer != obj:
        return

    scene_settings = getattr(scene, "edge_decal_settings", None)
    if scene_settings is None:
        return

    previous_copying = EDGEDECAL_SCENE_SETTINGS_COPYING
    EDGEDECAL_SCENE_SETTINGS_COPYING = True
    try:
        displayed_material = (
            getattr(self, "decal_template_material", None)
            or material
        )
        scene_settings.use_material = displayed_material is not None
        scene_settings.decal_material = displayed_material
        scene_settings.match_source_material = bool(
            getattr(self, "match_source_material", False)
            or (
                material is not None
                and material.get("edge_decal_source_matched")
            )
        )
    finally:
        EDGEDECAL_SCENE_SETTINGS_COPYING = previous_copying

    signature_fn = globals().get("scene_live_edit_signature")
    cache_key_fn = globals().get("scene_live_sync_cache_key")
    if signature_fn is not None and cache_key_fn is not None:
        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
            cache_key_fn(source_obj, obj)
        ] = signature_fn(scene_settings)


def update_decal_template_material(self, context):
    """Resolve the assigned material when a layer's template changes."""
    global EDGEDECAL_SCENE_SETTINGS_COPYING
    global EDGEDECAL_SETTINGS_SYNCING

    if EDGEDECAL_SETTINGS_SYNCING or EDGEDECAL_SCENE_SETTINGS_COPYING:
        return

    obj = getattr(self, "id_data", None)
    if obj is None or getattr(obj, "type", None) != "MESH":
        return

    template = root_decal_template_material(
        getattr(self, "decal_template_material", None)
    )
    scene = getattr(context, "scene", None) if context is not None else None
    scene_settings = getattr(scene, "edge_decal_settings", None) if scene else None

    previous_copying = EDGEDECAL_SCENE_SETTINGS_COPYING
    EDGEDECAL_SCENE_SETTINGS_COPYING = True
    try:
        if scene_settings is not None:
            scene_settings.use_material = template is not None
            scene_settings.decal_material = template
            scene_settings.match_source_material = bool(
                getattr(self, "match_source_material", False)
            )
    finally:
        EDGEDECAL_SCENE_SETTINGS_COPYING = previous_copying

    if template is None:
        obj.data.materials.clear()
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            self.decal_material = None
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing
        return

    if getattr(self, "match_source_material", False):
        material, _unsupported = ensure_source_matched_decal_material(
            obj,
            template,
            force_refresh=True,
        )
        ensure_source_material_uv_map(obj, material)
    else:
        material = template
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.material_index = 0

    previous_syncing = EDGEDECAL_SETTINGS_SYNCING
    EDGEDECAL_SETTINGS_SYNCING = True
    try:
        self.decal_material = material
    finally:
        EDGEDECAL_SETTINGS_SYNCING = previous_syncing

    apply_pins_fn = globals().get(
        "apply_uv_pins_to_decal_objects_by_material"
    )
    if apply_pins_fn is not None and scene is not None:
        apply_pins_fn(scene, [obj])


def update_decal_match_source_material(self, context):
    """Swap a layer between its authored template and source-matched copy."""
    if EDGEDECAL_SETTINGS_SYNCING or EDGEDECAL_SCENE_SETTINGS_COPYING:
        return
    scene = getattr(context, "scene", None) if context is not None else None
    scene_settings = getattr(scene, "edge_decal_settings", None) if scene else None
    if getattr(self, "match_source_material", False):
        enable_second_uv_for_material_matching(scene_settings)
    update_decal_template_material(self, context)


def poll_decal_layer_mask(self, candidate):
    """Offer only sibling decal layers that sit above the owning layer."""
    target_layer = getattr(self, "id_data", None)
    source_obj = getattr(self, "source_object", None)
    if (
        target_layer is None
        or source_obj is None
        or not decal_layer_is_valid(target_layer, source_obj)
        or not decal_layer_is_valid(candidate, source_obj)
        or candidate == target_layer
    ):
        return False

    layers = sorted_decal_layers_for_source(source_obj)
    try:
        return layers.index(candidate) < layers.index(target_layer)
    except ValueError:
        return False


class EDGEDECAL_PG_object_settings(PropertyGroup):
    initialized: BoolProperty(default=False, options={"HIDDEN"})
    live_update: BoolProperty(
        name="Live Update",
        default=True,
        description="Regenerate after a short pause while changing settings",
    )
    selection_mode: StringProperty(default="SELECTED_EDGES", options={"HIDDEN"})
    source_indices: StringProperty(default="", options={"HIDDEN"})
    source_object: PointerProperty(name="Source Object", type=bpy.types.Object)
    layer_mask: PointerProperty(
        name="Mask Layer",
        type=bpy.types.Object,
        poll=poll_decal_layer_mask,
        description=(
            "Decal layer above this one whose visible footprint is removed "
            "from this layer during regeneration"
        ),
    )
    source_material: PointerProperty(
        name="Source Material",
        type=bpy.types.Material,
        description=(
            "Source mesh material used for Base Color, Metallic, and Roughness"
        ),
        options={"HIDDEN"},
    )
    decal_template_material: PointerProperty(
        name="Material",
        type=bpy.types.Material,
        description="Edge decal material template used by this layer",
        update=update_decal_template_material,
    )
    decal_material: PointerProperty(
        name="Material",
        type=bpy.types.Material,
        description="Material assigned to this generated decal object",
        update=update_decal_object_material,
    )
    match_source_material: BoolProperty(
        name="Match Material",
        default=True,
        description=(
            "Match Base Color, Metallic, and Roughness to the source mesh; "
            "when disabled, use the decal material's authored values"
        ),
        update=update_decal_match_source_material,
    )
    uv_pin_indices: StringProperty(
        name="UV Pins",
        default="",
        description=(
            "Comma-separated UV pin indices used by this decal layer. "
            "Leave empty to cycle through all pins automatically"
        ),
    )
    use_texture_mask: BoolProperty(
        name="Use Texture Mask",
        default=False,
        description=(
            "Limit this layer to white areas of its painted source-UV mask; "
            "black areas do not generate decals"
        ),
    )
    texture_mask: PointerProperty(
        name="Texture Mask",
        type=bpy.types.Image,
        description="Black-and-white source-UV image controlling layer generation",
    )
    texture_mask_threshold: FloatProperty(
        name="Mask Threshold",
        default=0.5,
        min=0.001,
        max=1.0,
        subtype="FACTOR",
        description="Minimum painted brightness that permits decal generation",
    )

    face_width: FloatProperty(
        name="Face Width", default=0.01, min=MIN_FACE_WIDTH, soft_max=0.25,
        subtype="FACTOR", update=schedule_decal_live_update,
        description="Width as a fraction of the source object's largest world-space dimension when Relative Width is enabled",
    )
    relative_face_width: BoolProperty(
        name="Relative Width",
        default=True,
        description="Interpret Face Width as a fraction of the source object's largest world-space dimension",
        update=schedule_decal_live_update,
    )
    surface_offset: FloatProperty(
        name="Surface Offset", default=0.002, min=0.0, soft_max=0.05,
        unit="LENGTH", update=update_decal_surface_offset,
    )
    uv_scale: FloatProperty(
        name="UV Scale", default=1.0, min=0.01, soft_min=0.1,
        soft_max=10.0, precision=3, update=schedule_decal_live_update,
    )
    seed: IntProperty(
        name="Seed", default=1, min=0, soft_max=1000,
        update=schedule_decal_live_update,
    )
    decal_amount: FloatProperty(
        name="Decal Amount", default=1.0, min=0.0, max=1.0,
        subtype="FACTOR", update=schedule_decal_live_update,
    )
    edge_slice: FloatProperty(
        name="Edge Slice", default=0.0, min=0.0, max=1.0,
        subtype="FACTOR",
        description="How often retained open chains use their UV pin slice points",
        update=schedule_decal_live_update,
    )
    maximum_decal_length: FloatProperty(
        name="Maximum Decal Length", default=0.0, min=0.0, soft_max=10.0,
        unit="LENGTH",
        description="Maximum continuous decal length; zero disables the limit",
        update=schedule_decal_live_update,
    )
    taper_sliced_ends: BoolProperty(
        name="Taper Sliced Ends",
        default=True,
        description="Narrow only endpoints created by Decal Amount slicing",
        update=schedule_decal_live_update,
    )
    slice_taper_length: FloatProperty(
        name="Taper Length",
        default=0.24,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
        description="World-space distance used to widen a sliced endpoint back to full width",
        update=schedule_decal_live_update,
    )
    auto_trim_corner_ends: BoolProperty(
        name="Auto Trim Tight Corner Ends",
        default=False,
        description=(
            "Shorten only decal endpoints that stop beside a turning manifold edge"
        ),
        update=schedule_decal_live_update,
    )
    corner_end_trim_multiplier: FloatProperty(
        name="Corner Trim Multiplier",
        default=1.0,
        min=0.0,
        soft_max=3.0,
        description="Endpoint trim distance relative to the source object's last Bevel width",
        update=schedule_decal_live_update,
    )
    crevice_removal: FloatProperty(
        name="Crevice Removal", default=0.0, min=0.0, max=1.0,
        subtype="FACTOR", update=schedule_decal_live_update,
    )
    crevice_detection_mode: EnumProperty(
        name="Crevice Detection",
        items=CREVICE_DETECTION_ITEMS,
        default="AO",
        update=schedule_decal_live_update,
    )
    crevice_ao_distance: FloatProperty(
        name="AO Distance",
        default=0.0,
        min=0.0,
        soft_max=2.0,
        unit="LENGTH",
        description=(
            "Maximum ray distance. Zero automatically uses four times "
            "the decal width"
        ),
        update=schedule_decal_live_update,
    )
    crevice_ao_samples: IntProperty(
        name="AO Samples",
        default=8,
        min=4,
        max=32,
        description="Ray samples per test point",
        update=schedule_decal_live_update,
    )
    remove_short_edges: BoolProperty(
        name="Remove Short Edges", default=False,
        update=schedule_decal_live_update,
    )
    minimum_edge_length: FloatProperty(
        name="Minimum Edge Length", default=0.05, min=0.0, soft_max=10.0,
        unit="LENGTH", update=schedule_decal_live_update,
    )
    minimum_length_per_edge: BoolProperty(
        name="Measure Each Edge Separately",
        default=False,
        description=(
            "Enabled for automatic generation so short source segments are "
            "removed individually. Disabled for manual generation so the "
            "complete selected chain is measured and preserved"
        ),
        update=schedule_decal_live_update,
    )
    randomize_horizontal_offset: BoolProperty(
        name="Random Horizontal Offset", default=True,
        update=schedule_decal_live_update,
    )
    randomize_face_width: BoolProperty(
        name="Random Width",
        default=False,
        description="Choose a repeatable random width for each disconnected decal path",
        update=schedule_decal_live_update,
    )
    minimum_face_width: FloatProperty(
        name="Minimum Width",
        default=0.005,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        precision=6,
        update=schedule_decal_live_update,
    )
    maximum_face_width: FloatProperty(
        name="Maximum Width",
        default=0.02,
        min=MIN_FACE_WIDTH,
        soft_max=0.25,
        subtype="FACTOR",
        precision=6,
        update=schedule_decal_live_update,
    )
    horizontal_randomize_amount: FloatProperty(
        name="Horizontal Randomize Amount",
        default=1.0,
        min=0.0,
        soft_max=500.0,
        update=schedule_decal_live_update,
    )
    auto_face_width: BoolProperty(
        name="Auto Face Width", default=False,
        update=schedule_decal_live_update,
    )
    auto_width_samples: IntProperty(
        name="Auto Width Samples", default=1, min=1, max=5,
        update=schedule_decal_live_update,
    )
    auto_width_clearance: FloatProperty(
        name="Width Clearance", default=0.85, min=0.05, max=0.99,
        subtype="FACTOR", update=schedule_decal_live_update,
    )
    clamp_edge_overlaps: BoolProperty(
        name="Clamp Edge Overlaps",
        default=True,
        description=(
            "Build a connected curve-graph strip and locally reduce its width "
            "before it reaches another selected decal edge"
        ),
        update=schedule_decal_live_update,
    )
    overlap_clearance: FloatProperty(
        name="Overlap Clearance",
        default=0.98,
        min=0.5,
        max=0.999,
        subtype="FACTOR",
        description=(
            "Fraction of the shared gap used by two opposing decal strips"
        ),
        update=schedule_decal_live_update,
    )

    use_edge_split: BoolProperty(
        name="Split Edge Paths",
        default=True,
        description=(
            "Build separate geometry islands where a connected edge path "
            "turns farther than Split Angle"
        ),
        update=schedule_decal_live_update,
    )
    split_angle: FloatProperty(
        name="Split Angle",
        default=radians(45.0),
        min=0.0,
        max=radians(180.0),
        subtype="ANGLE",
        description="Split when the actual path turn exceeds this angle",
        update=schedule_decal_live_update,
    )

    use_face_loop_slide: BoolProperty(
        name="Follow Connected Face Edges",
        default=True,
        description=(
            "Prefer a real connected support-face edge at safe endpoints, "
            "and fall back to the existing miter solver when no suitable rail exists"
        ),
        update=schedule_decal_live_update,
    )

    # Finish modifiers belong to the layer, just like its geometry and UV
    # settings.  Keeping these only on the scene settings makes switching or
    # regenerating layers reuse whichever modifier toggles were edited last.
    add_weld_modifier: BoolProperty(
        name="Add Weld Modifier",
        default=False,
        description="Add the Weld modifier to this decal layer",
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
    add_shrinkwrap_modifier: BoolProperty(
        name="Add Shrinkwrap Modifier",
        default=False,
        description="Add a source-targeted Shrinkwrap modifier to this layer",
        update=update_decal_finish_modifiers,
    )
    add_center_displace_modifier: BoolProperty(
        name="Displace Center",
        default=False,
        description="Displace only the EdgeDecal_Center vertex group",
        update=update_decal_finish_modifiers,
    )
    center_displace_strength: FloatProperty(
        name="Center Displace Strength",
        default=0.002,
        precision=5,
        unit="LENGTH",
        description="Normal displacement applied to EdgeDecal_Center",
        update=update_decal_finish_modifiers,
    )
    add_bevel_modifier: BoolProperty(
        name="Add Bevel Modifier",
        default=False,
        description="Add the final Bevel modifier to this layer",
        update=update_decal_finish_modifiers,
    )
    bevel_edge_center: BoolProperty(
        name="Bevel Edge Center",
        default=False,
        description="Limit the Bevel modifier to EdgeDecal_Center",
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
        description="Number of segments used by the bevel",
        update=update_decal_finish_modifiers,
    )
    center_bevel_profile: FloatProperty(
        name="Bevel Profile",
        default=0.5,
        min=0.0,
        max=1.0,
        description="Shape of the bevel profile",
        update=update_decal_finish_modifiers,
    )
    bevel_harden_normals: BoolProperty(
        name="Harden Normals",
        default=False,
        description="Harden normals on the generated decal's Bevel modifier",
        update=update_decal_finish_modifiers,
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
    add_subdivision_modifier: BoolProperty(
        name="Add Subdivision Modifier",
        default=False,
        description="Add a Subdivision Surface modifier to this layer",
        update=update_decal_finish_modifiers,
    )
    add_decimate_modifier: BoolProperty(
        name="Add Decimate Modifier",
        default=False,
        description="Add a Decimate modifier to this layer",
        update=update_decal_finish_modifiers,
    )


    normal_mode: EnumProperty(
        name="Normal Shading",
        items=NORMAL_MODE_ITEMS,
        default="SHADE_SMOOTH",
        update=schedule_decal_live_update,
    )
    normal_keep_sharp: BoolProperty(
        name="Keep Sharp Edges",
        default=False,
        update=schedule_decal_live_update,
    )
    normal_weight: IntProperty(
        name="Weight",
        default=50,
        min=1,
        max=100,
        update=schedule_decal_live_update,
    )
    normal_threshold: FloatProperty(
        name="Threshold",
        default=0.01,
        min=0.0,
        max=10.0,
        precision=4,
        update=schedule_decal_live_update,
    )


    show_edit_settings: BoolProperty(
        name="Edit Selected Decal",
        default=True,
        description="Show settings stored on the selected decal object",
    )
    show_edit_geometry: BoolProperty(
        name="Geometry",
        default=True,
        description="Show the selected decal geometry settings",
    )
    show_edit_geometry_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show geometry settings that are changed less frequently",
    )
    show_edit_uv: BoolProperty(
        name="UV Placement",
        default=True,
        description="Show the selected decal UV settings",
    )
    show_edit_uv_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show UV settings that are changed less frequently",
    )

    show_edit_normals: BoolProperty(
        name="Normals",
        default=True,
        description="Show normal shading settings for the selected decal",
    )
    show_edit_normals_advanced: BoolProperty(
        name="Advanced",
        default=False,
        description="Show detailed normal modifier settings",
    )


def clear_decal_mesh_inplace(decal_obj):
    """Drop all decal geometry while keeping the object shell."""
    if decal_obj is None or decal_obj.type != "MESH":
        return

    old_mesh = decal_obj.data
    decal_obj.data = bpy.data.meshes.new(f"{decal_obj.name}_RebuildMesh")
    if old_mesh is not None and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)


def replace_vertex_groups_from_object(target_obj, source_obj):
    """Mirror source vertex-group definitions without rewriting mesh weights.

    Vertex-group membership is stored on mesh vertices, while the group names
    and indices live on the object. During regeneration ``source_obj.data`` is
    about to be moved onto ``target_obj``. The replacement mesh already carries
    the correct deform weights, including ``EdgeDecal_Center``.

    The previous implementation added those weights to the *old target mesh*
    before the mesh swap. After the swap, short Amount-cut islands could lose
    their usable centerline mapping, making UV pin alignment fall back to the
    island's longest bounding axis. For a short decal that axis is its width,
    so the pin fitter rotated/scaled the wrong direction.

    Recreate only the object-level group definitions, in the exact source index
    order. The replacement mesh's existing memberships then resolve correctly
    as soon as it is assigned to the target object.
    """
    source_groups = sorted(
        ((group.index, group.name) for group in source_obj.vertex_groups),
        key=lambda item: item[0],
    )

    for group in list(target_obj.vertex_groups):
        target_obj.vertex_groups.remove(group)

    for _group_index, group_name in source_groups:
        target_obj.vertex_groups.new(name=group_name)


def reapply_decal_layer_mask_after_regeneration(
    context,
    source_obj,
    layer_obj,
    result,
    operator=None,
):
    """Keep a layer's explicit mask assignment durable across updates."""
    if "FINISHED" not in result or layer_obj is None:
        return result

    data = getattr(layer_obj, "edge_decal_object_settings", None)
    mask_layer = getattr(data, "layer_mask", None) if data is not None else None
    if mask_layer is None:
        return result

    apply_mask = globals().get("apply_decal_layer_mask")
    if apply_mask is None:
        return result

    success, message = apply_mask(
        context,
        source_obj,
        layer_obj,
        mask_layer,
    )
    if operator is not None and message:
        operator.report({"INFO" if success else "WARNING"}, message)
    return result



class EDGEDECAL_OT_regenerate(Operator):
    bl_idname = "object.edge_decal_regenerate"
    bl_label = "Update Decal"
    bl_description = "Regenerate the active decal from stored source data"
    bl_options = {"REGISTER", "UNDO"}

    preview: BoolProperty(default=False, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return editable_generated_decal(context) is not None

    def execute(self, context):
        user_started_in_edit_mode = context.mode == "EDIT_MESH"
        old_obj = editable_generated_decal(context)
        if old_obj is None:
            self.report({"ERROR"}, "No populated decal layer is available.")
            return {"CANCELLED"}

        data = old_obj.edge_decal_object_settings
        initialize_decal_finish_settings_from_modifiers(old_obj)
        source_obj = data.source_object

        if source_obj is None or source_obj.name not in bpy.data.objects:
            source_obj = find_object_by_name_or_full(
                old_obj.get("edge_decal_source", "")
            )
            if source_obj is not None:
                data.source_object = source_obj

        if source_obj is None:
            source_obj = edge_decal_context_source(context)

        if source_obj is None or source_obj.name not in bpy.data.objects:
            self.report({"ERROR"}, "Stored source object is missing.")
            return {"CANCELLED"}

        if old_obj.get("edge_decal_mode") == "INTERSECTIONS":
            push_regenerating()
            try:
                result = regenerate_intersection_decal(
                    context,
                    old_obj,
                    operator=self,
                )
                return reapply_decal_layer_mask_after_regeneration(
                    context,
                    source_obj,
                    old_obj,
                    result,
                    operator=self,
                )
            finally:
                pop_regenerating()
                ensure_viewport_mode_coherent(context)

        if old_obj.get("edge_decal_mode") == "BOOLEAN":
            push_regenerating()
            try:
                result = regenerate_boolean_decal(
                    context,
                    old_obj,
                    operator=self,
                )
                return reapply_decal_layer_mask_after_regeneration(
                    context,
                    source_obj,
                    old_obj,
                    result,
                    operator=self,
                )
            finally:
                pop_regenerating()
                ensure_viewport_mode_coherent(context)

        if not decal_layer_source_edge_order_is_current(old_obj, source_obj):
            self.report(
                {"ERROR"},
                "The source mesh topology changed after this decal layer was "
                "created. Regeneration was stopped to avoid generating decals "
                "from unrelated edge indices. Create a new layer for the "
                "updated source mesh.",
            )
            return {"CANCELLED"}

        scene_settings = context.scene.edge_decal_settings
        source_indices = resolve_regeneration_source_indices(
            old_obj,
            source_obj,
            scene_settings,
        )
        if not source_indices and not parsed_interactive_stroke_edges(old_obj):
            self.report({"ERROR"}, "Stored source selection is empty.")
            return {"CANCELLED"}

        previous_replace = scene_settings.replace_previous
        previous_fast = scene_settings.fast_geometry_only
        previous_auto_unwrap = scene_settings.auto_unwrap_uvs
        previous_auto_pins = scene_settings.auto_use_uv_pins
        old_index = int(old_obj.get("edge_decal_index", 0))
        old_mode = old_obj.get("edge_decal_mode", "SHARP_EDGES")
        if old_mode == "APPLIED_BEVEL_FACES":
            self.report(
                {"ERROR"},
                "Applied-bevel decal layers are no longer supported. "
                "Delete this layer and regenerate from sharp edges.",
            )
            return {"CANCELLED"}
        selection_mode = (
            data.selection_mode
            or str(old_obj.get("edge_decal_selection_mode", "SELECTED_EDGES"))
        )

        old_material = data.decal_material
        previous_active_layer_name = str(
            source_obj.get("edge_decal_active_layer", "")
        )
        interactive_strokes_raw = old_obj.get("edge_decal_interactive_strokes", "[]")
        try:
            interactive_strokes = json.loads(interactive_strokes_raw) if isinstance(interactive_strokes_raw, str) else list(interactive_strokes_raw)
        except Exception:
            interactive_strokes = []
        interactive_edge_indices = {
            int(edge_index)
            for stroke in interactive_strokes
            if isinstance(stroke, dict)
            for edge_index in stroke.get("edges", [])
        }
        # An explicitly stored empty base list means this decal contains only
        # interactive strokes. Do not reinterpret it as "all source edges",
        # otherwise a live update rebuilds every stroke again at the global
        # Face Width before rebuilding the per-stroke versions.
        if "edge_decal_base_source_indices" in old_obj:
            stored_base_indices = str(old_obj.get("edge_decal_base_source_indices", ""))
            try:
                base_source_indices = [
                    int(token)
                    for token in stored_base_indices.split(",")
                    if token.strip()
                ]
            except Exception:
                base_source_indices = [
                    index for index in source_indices
                    if index not in interactive_edge_indices
                ]
        else:
            base_source_indices = [
                index for index in source_indices
                if index not in interactive_edge_indices
            ]
            if not base_source_indices and not interactive_strokes:
                base_source_indices = list(source_indices)

        global EDGEDECAL_STANDALONE_GENERATION
        previous_standalone = EDGEDECAL_STANDALONE_GENERATION
        EDGEDECAL_STANDALONE_GENERATION = True
        globals()["EDGEDECAL_REGENERATE_TARGET"] = old_obj.name_full
        push_regenerating()
        try:
            result = self._execute_regenerate_body(
                context,
                user_started_in_edit_mode=user_started_in_edit_mode,
                old_obj=old_obj,
                data=data,
                source_obj=source_obj,
                scene_settings=scene_settings,
                previous_replace=previous_replace,
                previous_fast=previous_fast,
                previous_auto_unwrap=previous_auto_unwrap,
                previous_auto_pins=previous_auto_pins,
                old_index=old_index,
                old_mode=old_mode,
                old_material=old_material,
                previous_active_layer_name=previous_active_layer_name,
                interactive_strokes=interactive_strokes,
                base_source_indices=base_source_indices,
                selection_mode=selection_mode,
            )
            return reapply_decal_layer_mask_after_regeneration(
                context,
                source_obj,
                old_obj,
                result,
                operator=self,
            )
        finally:
            EDGEDECAL_STANDALONE_GENERATION = previous_standalone
            globals()["EDGEDECAL_REGENERATE_TARGET"] = None
            pop_regenerating()
            ensure_viewport_mode_coherent(context)

    def _execute_regenerate_body(
        self,
        context,
        *,
        user_started_in_edit_mode,
        old_obj,
        data,
        source_obj,
        scene_settings,
        previous_replace,
        previous_fast,
        previous_auto_unwrap,
        previous_auto_pins,
        old_index,
        old_mode,
        old_material,
        previous_active_layer_name,
        interactive_strokes,
        base_source_indices,
        selection_mode,
    ):
        scene_settings.replace_previous = False

        # Regeneration must create a temporary standalone replacement. If the
        # current layer remains active, the multilayer generator merges the
        # temporary result directly into that layer, which can corrupt or
        # remove another layer during Update Layer/live update.
        source_obj["edge_decal_active_layer"] = ""

        # Preserve the current performance override during Update Layer and
        # live updates. Fast Geometry is a temporary workflow choice, so a
        # settings adjustment must not silently switch regeneration back to
        # the complete UV path.
        scene_settings.fast_geometry_only = previous_fast
        scene_settings.use_edge_split = bool(data.use_edge_split)
        scene_settings.split_angle = float(data.split_angle)

        copied_values = {
            name: getattr(data, name)
            for name in (
                "face_width", "relative_face_width", "randomize_face_width",
                "minimum_face_width", "maximum_face_width",
                "use_edge_split", "split_angle",
                "surface_offset", "uv_scale", "seed",
                "decal_amount", "edge_slice", "maximum_decal_length",
                "taper_sliced_ends", "slice_taper_length",
                "auto_trim_corner_ends", "corner_end_trim_multiplier",
                "crevice_removal",
                "crevice_detection_mode", "crevice_ao_distance",
                "crevice_ao_samples", "remove_short_edges",
                "minimum_edge_length", "minimum_length_per_edge",
                "randomize_horizontal_offset",
                "horizontal_randomize_amount",
                "auto_face_width", "auto_width_samples",
                "auto_width_clearance", "clamp_edge_overlaps",
                "overlap_clearance", "normal_mode",
                "normal_keep_sharp", "normal_weight",
                "normal_threshold",
                "use_face_loop_slide",
            )
        }
        interactive_only_regen = (
            bool(interactive_strokes)
            and not base_source_indices
        )

        for selected in list(context.selected_objects):
            selected.select_set(False)
        source_obj.select_set(True)
        context.view_layer.objects.active = source_obj

        if interactive_only_regen:
            force_object_mode(context)
            clear_decal_mesh_inplace(old_obj)
            for group in list(old_obj.vertex_groups):
                old_obj.vertex_groups.remove(group)
            result = {"FINISHED"}
        else:
            try:
                bpy.ops.object.mode_set(mode="EDIT")
                bm = bmesh.from_edit_mesh(source_obj.data)
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

                for edge in bm.edges:
                    edge.select = False
                for face in bm.faces:
                    face.select = False

                for index in base_source_indices:
                    if (
                        selection_mode == "SELECTED_FACES"
                        and 0 <= index < len(bm.faces)
                    ):
                        bm.faces[index].select = True
                    elif (
                        selection_mode != "SELECTED_FACES"
                        and 0 <= index < len(bm.edges)
                    ):
                        bm.edges[index].select = True

                bmesh.update_edit_mesh(
                    source_obj.data,
                    loop_triangles=False,
                    destructive=False,
                )
                if selection_mode == "SELECTED_FACES":
                    result = bpy.ops.mesh.generate_edge_decal_strips(
                        surface_offset=data.surface_offset,
                        uv_scale=data.uv_scale,
                        fast_geometry_only=previous_fast,
                        face_width=data.face_width,
                        randomize_face_width=data.randomize_face_width,
                        minimum_face_width=data.minimum_face_width,
                        maximum_face_width=data.maximum_face_width,
                        remove_short_edges=data.remove_short_edges,
                        minimum_edge_length=data.minimum_edge_length,
                        decal_amount=data.decal_amount,
                        edge_slice=0.0,
                        maximum_decal_length=data.maximum_decal_length,
                        taper_sliced_ends=data.taper_sliced_ends,
                        slice_taper_length=data.slice_taper_length,
                        auto_trim_corner_ends=data.auto_trim_corner_ends,
                        corner_end_trim_multiplier=data.corner_end_trim_multiplier,
                        randomize_horizontal_offset=data.randomize_horizontal_offset,
                        horizontal_randomize_amount=data.horizontal_randomize_amount,
                        seed=data.seed,
                        auto_face_width=data.auto_face_width,
                        auto_width_samples=data.auto_width_samples,
                        auto_width_clearance=data.auto_width_clearance,
                        clamp_edge_overlaps=data.clamp_edge_overlaps,
                        overlap_clearance=data.overlap_clearance,
                        use_face_loop_slide=data.use_face_loop_slide,
                        add_weld_modifier=data.add_weld_modifier,
                        add_bevel_modifier=data.add_bevel_modifier,
                        generate_selected_edge_graph=True,
                        generate_from_selected_faces=True,
                        interactive_skip_limited_dissolve=True,
                    )
                else:
                    result = bpy.ops.mesh.generate_edge_decal_strips(
                        face_width=data.face_width,
                        randomize_face_width=data.randomize_face_width,
                        minimum_face_width=data.minimum_face_width,
                        maximum_face_width=data.maximum_face_width,
                        crevice_removal=data.crevice_removal,
                        crevice_detection_mode=data.crevice_detection_mode,
                        crevice_ao_distance=data.crevice_ao_distance,
                        crevice_ao_samples=data.crevice_ao_samples,
                        remove_short_edges=data.remove_short_edges,
                        minimum_edge_length=data.minimum_edge_length,
                        decal_amount=data.decal_amount,
                        edge_slice=0.0,
                        maximum_decal_length=data.maximum_decal_length,
                        taper_sliced_ends=data.taper_sliced_ends,
                        slice_taper_length=data.slice_taper_length,
                        auto_trim_corner_ends=data.auto_trim_corner_ends,
                        corner_end_trim_multiplier=data.corner_end_trim_multiplier,
                        randomize_horizontal_offset=data.randomize_horizontal_offset,
                        horizontal_randomize_amount=data.horizontal_randomize_amount,
                        seed=data.seed,
                        uv_scale=data.uv_scale,
                        auto_face_width=data.auto_face_width,
                        auto_width_samples=data.auto_width_samples,
                        auto_width_clearance=data.auto_width_clearance,
                        clamp_edge_overlaps=data.clamp_edge_overlaps,
                        overlap_clearance=data.overlap_clearance,
                        use_face_loop_slide=data.use_face_loop_slide,
                        fast_geometry_only=previous_fast,
                        add_weld_modifier=data.add_weld_modifier,
                        add_bevel_modifier=data.add_bevel_modifier,
                        generate_selected_edge_graph=bool(
                            old_obj.get("edge_decal_selected_graph", False)
                        ),
                        interactive_skip_limited_dissolve=bool(
                            old_obj.get("edge_decal_selected_graph", False)
                        ),
                        surface_offset=data.surface_offset,
                    )
            except RuntimeError as error:
                force_object_mode(context)
                source_obj["edge_decal_active_layer"] = previous_active_layer_name
                scene_settings.replace_previous = previous_replace
                scene_settings.fast_geometry_only = previous_fast
                scene_settings.auto_unwrap_uvs = previous_auto_unwrap
                scene_settings.auto_use_uv_pins = previous_auto_pins
                self.report({"ERROR"}, f"Regeneration failed: {error}")
                return {"CANCELLED"}

        source_obj["edge_decal_active_layer"] = previous_active_layer_name
        scene_settings.replace_previous = previous_replace
        scene_settings.fast_geometry_only = previous_fast
        scene_settings.auto_unwrap_uvs = previous_auto_unwrap
        scene_settings.auto_use_uv_pins = previous_auto_pins

        if "FINISHED" not in result:
            force_object_mode(context)
            return {"CANCELLED"}

        if interactive_only_regen:
            old_obj["edge_decal_index"] = old_index
            old_obj["edge_decal_mode"] = old_mode
            old_obj["edge_decal_generated"] = True
            old_obj["edge_decal_source"] = source_obj.name_full
            set_active_decal_layer(source_obj, old_obj)
        else:
            candidates = list(
                iter_generated_decals(
                    source_obj=source_obj,
                    mode=old_mode,
                    exclude=old_obj,
                )
            )

            if not candidates:
                force_object_mode(context)
                self.report({"ERROR"}, "No replacement decal was generated.")
                return {"CANCELLED"}

            new_obj = max(
                candidates,
                key=lambda obj: int(obj.get("edge_decal_index", 0)),
            )

            # Regenerate in place. Keeping the original object preserves its name,
            # parenting, collections, modifiers, visibility, constraints, and any
            # external references.
            old_mesh = old_obj.data
            replacement_mesh = new_obj.data
            replace_vertex_groups_from_object(old_obj, new_obj)

            # Generated mesh coordinates live in the temporary replacement
            # object's local space. A duplicated decal can have a non-identity
            # world transform inherited from moving its copied source. Moving
            # the raw replacement mesh onto that existing object would apply
            # the copy transform twice and send the decal away from the mesh.
            # Convert the replacement into the preserved object's local space
            # before swapping datablocks:
            #
            #   old_world @ converted = replacement_world @ generated
            replacement_to_existing = (
                old_obj.matrix_world.inverted_safe()
                @ new_obj.matrix_world
            )
            replacement_mesh.transform(replacement_to_existing)
            replacement_mesh.update()

            new_obj.data = None
            bpy.data.objects.remove(new_obj, do_unlink=True)
            old_obj.data = replacement_mesh

            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)

            old_obj["edge_decal_index"] = old_index
            old_obj["edge_decal_mode"] = old_mode
            old_obj["edge_decal_generated"] = True
            old_obj["edge_decal_source"] = source_obj.name_full
            set_active_decal_layer(source_obj, old_obj)

        # Rebuild interactive strokes separately so automatic-generation
        # filters cannot remove them when this mixed decal is adjusted.
        rebuilt_strokes = []
        stored_source_indices = sorted(set(base_source_indices))
        if interactive_strokes:
            combined_indices = list(base_source_indices)
            stroke_face_width = float(data.face_width)
            for stroke in interactive_strokes:
                if not isinstance(stroke, dict):
                    continue
                stroke_edges = sorted(set(int(index) for index in stroke.get("edges", [])))
                if not stroke_edges:
                    continue

                for selected in list(context.selected_objects):
                    selected.select_set(False)
                source_obj.select_set(True)
                context.view_layer.objects.active = source_obj
                try:
                    bpy.ops.object.mode_set(mode="EDIT")
                    bm = bmesh.from_edit_mesh(source_obj.data)
                    bm.edges.ensure_lookup_table()
                    for edge in bm.edges:
                        edge.select = False
                    valid_edges = []
                    for index in stroke_edges:
                        if 0 <= index < len(bm.edges) and len(bm.edges[index].link_faces) == 2:
                            bm.edges[index].select = True
                            valid_edges.append(index)
                    bmesh.update_edit_mesh(source_obj.data, loop_triangles=False, destructive=False)
                    if not valid_edges:
                        bpy.ops.object.mode_set(mode="OBJECT")
                        continue

                    existing_names = {obj.name_full for obj in iter_generated_decals(source_obj=source_obj)}
                    previous_split = scene_settings.use_edge_split
                    scene_settings.use_edge_split = False if stroke.get("force_connected", False) else previous_split
                    interval = stroke.get("slice_interval")
                    result = bpy.ops.mesh.generate_edge_decal_strips(
                        "EXEC_DEFAULT",
                        face_width=stroke_face_width,
                        randomize_face_width=data.randomize_face_width,
                        minimum_face_width=data.minimum_face_width,
                        maximum_face_width=data.maximum_face_width,
                        crevice_removal=0.0,
                        remove_short_edges=False,
                        minimum_edge_length=data.minimum_edge_length,
                        decal_amount=1.0,
                        interactive_slice_start=(float(interval[0]) if interval else -1.0),
                        interactive_slice_end=(float(interval[1]) if interval else -1.0),
                        interactive_detect_endpoint_taper=True,
                        interactive_skip_limited_dissolve=True,
                        generate_selected_edge_graph=(
                            full_edge_selection_uses_graph(
                                valid_edges,
                                force_connected=bool(
                                    stroke.get("force_connected", False)
                                ),
                                slice_interval=interval,
                            )
                        ),
                        maximum_decal_length=0.0,
                        taper_sliced_ends=(True if interval else data.taper_sliced_ends),
                        slice_taper_length=data.slice_taper_length,
                        auto_trim_corner_ends=data.auto_trim_corner_ends,
                        corner_end_trim_multiplier=data.corner_end_trim_multiplier,
                        randomize_horizontal_offset=data.randomize_horizontal_offset,
                        horizontal_randomize_amount=data.horizontal_randomize_amount,
                        seed=data.seed,
                        uv_scale=data.uv_scale,
                        auto_face_width=data.auto_face_width,
                        auto_width_samples=data.auto_width_samples,
                        auto_width_clearance=data.auto_width_clearance,
                        clamp_edge_overlaps=data.clamp_edge_overlaps,
                        overlap_clearance=data.overlap_clearance,
                        use_face_loop_slide=data.use_face_loop_slide,
                        fast_geometry_only=previous_fast,
                        add_weld_modifier=data.add_weld_modifier,
                        add_bevel_modifier=data.add_bevel_modifier,
                        surface_offset=data.surface_offset,
                    )
                    scene_settings.use_edge_split = previous_split
                    if "FINISHED" not in result:
                        continue
                    candidates = [obj for obj in iter_generated_decals(source_obj=source_obj) if obj.name_full not in existing_names and obj != old_obj]
                    if not candidates:
                        continue
                    stroke_obj = max(candidates, key=lambda obj: int(obj.get("edge_decal_index", 0)))
                    start_vertex = len(old_obj.data.vertices)
                    old_obj = merge_generated_decal_objects(old_obj, stroke_obj)
                    end_vertex = len(old_obj.data.vertices)
                    rebuilt_strokes.append({
                        "id": str(stroke.get("id", len(rebuilt_strokes) + 1)),
                        "edges": valid_edges,
                        "vertices": list(range(start_vertex, end_vertex)),
                        "force_connected": bool(stroke.get("force_connected", False)),
                        "slice_interval": interval,
                        "face_width": stroke_face_width,
                    })
                    combined_indices.extend(valid_edges)
                except RuntimeError:
                    try:
                        bpy.ops.object.mode_set(mode="OBJECT")
                    except RuntimeError:
                        pass
                    continue

            stored_source_indices = sorted(set(combined_indices))
            old_obj["edge_decal_interactive_strokes"] = json.dumps(rebuilt_strokes)
            old_obj["edge_decal_base_source_indices"] = ",".join(
                str(index) for index in sorted(set(base_source_indices))
            )

        store_decal_settings(
            old_obj,
            source_obj,
            selection_mode,
            stored_source_indices,
            scene_settings,
            copied_values,
        )

        if old_material is not None:
            old_obj.data.materials.clear()
            old_obj.data.materials.append(old_material)
            for polygon in old_obj.data.polygons:
                polygon.material_index = 0
            old_obj.edge_decal_object_settings.decal_material = old_material

        ensure_decal_mesh_uv_layers(old_obj.data)

        apply_decal_normal_settings(
            old_obj,
            data.normal_mode,
            data.normal_keep_sharp,
            data.normal_weight,
            data.normal_threshold,
        )

        # Generation operators work through Edit Mode internally. Live updates
        # must not leave the user in Edit Mode after moving a sidebar slider.
        force_object_mode(context)

        set_active_decal_layer(source_obj, old_obj)
        select_only_object(context, source_obj)

        # Only restore Edit Mode when Update Layer was deliberately invoked
        # while the user was already editing the source mesh. Normal sidebar
        # adjustments made from Object Mode stay in Object Mode.
        if user_started_in_edit_mode:
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except RuntimeError:
                pass

        ensure_viewport_mode_coherent(context)

        configure_decal_object(
            old_obj,
            source_obj=source_obj,
            scene=context.scene,
        )

        EDGEDECAL_SCENE_LIVE_SYNC_CACHE[
            scene_live_sync_cache_key(source_obj, old_obj)
        ] = scene_live_edit_signature(scene_settings)
        return {"FINISHED"}





def safe_normalized(vector, fallback=None):
    if vector.length_squared > EPSILON:
        return vector.normalized()
    if fallback is not None and fallback.length_squared > EPSILON:
        return fallback.normalized()
    return Vector((0.0, 0.0, 1.0))


def get_or_create_collection(scene):
    collection = bpy.data.collections.get(COLLECTION_NAME)

    if collection is None:
        collection = bpy.data.collections.new(COLLECTION_NAME)
        scene.collection.children.link(collection)
    else:
        try:
            if collection.name not in scene.collection.children:
                scene.collection.children.link(collection)
        except RuntimeError:
            pass

    return collection


def configure_decal_object(decal_obj, source_obj=None, scene=None):
    """Match source collection membership and disable shadow-ray visibility."""
    if decal_obj is None:
        return None

    if hasattr(decal_obj, "visible_shadow"):
        decal_obj.visible_shadow = False

    if source_obj is None or source_obj is decal_obj:
        return decal_obj

    target_collections = list(source_obj.users_collection)
    if not target_collections:
        if scene is None:
            scene = getattr(bpy.context, "scene", None)
        if scene is not None:
            target_collections = [scene.collection]

    linked_targets = []
    for collection in target_collections:
        try:
            if collection.objects.get(decal_obj.name) is None:
                collection.objects.link(decal_obj)
            linked_targets.append(collection)
        except (ReferenceError, RuntimeError):
            continue

    # Only remove legacy/dedicated collection links after at least one source
    # collection accepted the object, so a failed link can never orphan it.
    if linked_targets:
        for collection in tuple(decal_obj.users_collection):
            if collection in linked_targets:
                continue
            try:
                collection.objects.unlink(decal_obj)
            except (ReferenceError, RuntimeError):
                pass

    return decal_obj


def get_or_create_material():
    material = bpy.data.materials.get(DEFAULT_MATERIAL_NAME)

    if material is None:
        material = bpy.data.materials.new(DEFAULT_MATERIAL_NAME)
        material.use_nodes = True
        material.diffuse_color = (1.0, 0.18, 0.02, 1.0)

        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (1.0, 0.18, 0.02, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.45

    return material


def primary_principled_node(material):
    """Return the material's main Principled node for source-channel matching."""
    if material is None or not getattr(material, "use_nodes", False):
        return None

    nodes = material.node_tree.nodes
    named = nodes.get("Principled BSDF")
    if named is not None and named.type == "BSDF_PRINCIPLED":
        return named

    principled_nodes = [
        node for node in nodes if node.type == "BSDF_PRINCIPLED"
    ]
    return principled_nodes[0] if len(principled_nodes) == 1 else None


def active_source_material(source_obj):
    """Resolve the source material captured by a newly generated decal layer."""
    if source_obj is None or source_obj.type != "MESH":
        return None

    material = getattr(source_obj, "active_material", None)
    if material is not None:
        return material

    return next(
        (
            candidate
            for candidate in getattr(source_obj.data, "materials", ())
            if candidate is not None
        ),
        None,
    )


def root_decal_template_material(material):
    """Resolve a generated matched material back to its decal template."""
    visited = set()
    while (
        material is not None
        and material.get("edge_decal_source_matched")
        and material.name_full not in visited
    ):
        visited.add(material.name_full)
        template_name = str(
            material.get("edge_decal_template_material_name", "")
        )
        template = bpy.data.materials.get(template_name)
        if template is None:
            break
        material = template
    return material


def _clear_material_input_links(node_tree, input_socket):
    for link in tuple(input_socket.links):
        node_tree.links.remove(link)


def _copy_image_node_settings(source_node, target_node):
    target_node.image = source_node.image
    for property_name in (
        "interpolation",
        "projection",
        "extension",
        "projection_blend",
    ):
        if hasattr(source_node, property_name) and hasattr(target_node, property_name):
            try:
                setattr(
                    target_node,
                    property_name,
                    getattr(source_node, property_name),
                )
            except (TypeError, ValueError):
                pass


def _direct_source_image_connection(input_socket):
    """Describe a direct image link, optionally through a Separate node."""
    if input_socket is None or not input_socket.is_linked:
        return None

    source_link = input_socket.links[0]
    source_node = source_link.from_node
    if source_node.type == "TEX_IMAGE" and source_node.image is not None:
        return {
            "image_node": source_node,
            "image_output": source_link.from_socket.name,
            "separator_node": None,
            "separator_output": "",
        }

    if source_node.type not in {"SEPARATE_COLOR", "SEPRGB"}:
        return None

    separator_input = source_node.inputs[0] if source_node.inputs else None
    if separator_input is None or not separator_input.is_linked:
        return None

    image_link = separator_input.links[0]
    image_node = image_link.from_node
    if image_node.type != "TEX_IMAGE" or image_node.image is None:
        return None

    return {
        "image_node": image_node,
        "image_output": image_link.from_socket.name,
        "separator_node": source_node,
        "separator_output": source_link.from_socket.name,
    }


def _add_source_image_connection(
    target_material,
    target_socket,
    connection,
    channel_name,
    vertical_offset,
):
    node_tree = target_material.node_tree
    nodes = node_tree.nodes

    uv_node = nodes.new("ShaderNodeUVMap")
    uv_node.name = f"Edge Decal Source {channel_name} UV"
    uv_node.label = "Source Material UV"
    uv_node.uv_map = SECOND_UV_LAYER_NAME
    uv_node.location = (-760.0, vertical_offset)
    uv_node["edge_decal_source_channel"] = channel_name

    source_image = connection["image_node"]
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.name = f"Edge Decal Source {channel_name} Image"
    image_node.label = f"Source {channel_name}"
    image_node.location = (-560.0, vertical_offset)
    image_node["edge_decal_source_channel"] = channel_name
    _copy_image_node_settings(source_image, image_node)

    node_tree.links.new(uv_node.outputs["UV"], image_node.inputs["Vector"])

    image_output = image_node.outputs.get(connection["image_output"])
    if image_output is None:
        image_output = image_node.outputs.get("Color")

    separator_source = connection["separator_node"]
    if separator_source is None:
        node_tree.links.new(image_output, target_socket)
        return

    separator = nodes.new(separator_source.bl_idname)
    separator.name = f"Edge Decal Source {channel_name} Separate"
    separator.label = f"Source {channel_name} Channel"
    separator.location = (-340.0, vertical_offset)
    separator["edge_decal_source_channel"] = channel_name
    if hasattr(separator_source, "mode") and hasattr(separator, "mode"):
        separator.mode = separator_source.mode

    node_tree.links.new(image_output, separator.inputs[0])
    separator_output = separator.outputs.get(connection["separator_output"])
    if separator_output is None:
        separator_output = separator.outputs[0]
    node_tree.links.new(separator_output, target_socket)


def update_source_channels_on_decal_material(decal_material, source_material):
    """Copy Base Color, Metallic, and Roughness onto a decal copy."""
    target_bsdf = primary_principled_node(decal_material)
    if target_bsdf is None:
        return False, ("Base Color", "Metallic", "Roughness")

    node_tree = decal_material.node_tree
    for node in tuple(node_tree.nodes):
        if node.get("edge_decal_source_channel"):
            node_tree.nodes.remove(node)

    base_target = target_bsdf.inputs.get("Base Color")
    metallic_target = target_bsdf.inputs.get("Metallic")
    roughness_target = target_bsdf.inputs.get("Roughness")
    unsupported = []

    source_bsdf = primary_principled_node(source_material)
    if source_bsdf is None:
        base_value = (
            tuple(source_material.diffuse_color)
            if source_material is not None
            else tuple(base_target.default_value)
        )
        _clear_material_input_links(node_tree, base_target)
        base_target.default_value = (
            float(base_value[0]),
            float(base_value[1]),
            float(base_value[2]),
            1.0,
        )
        if source_material is not None and roughness_target is not None:
            _clear_material_input_links(node_tree, roughness_target)
            roughness_target.default_value = float(
                getattr(source_material, "roughness", roughness_target.default_value)
            )
        if source_material is not None and metallic_target is not None:
            _clear_material_input_links(node_tree, metallic_target)
            metallic_target.default_value = float(
                getattr(source_material, "metallic", metallic_target.default_value)
            )
        return True, tuple(unsupported)

    channel_specs = (
        ("Base Color", base_target, -40.0),
        ("Metallic", metallic_target, -360.0),
        ("Roughness", roughness_target, -680.0),
    )
    for channel_name, target_socket, vertical_offset in channel_specs:
        source_socket = source_bsdf.inputs.get(channel_name)
        if source_socket is None or target_socket is None:
            unsupported.append(channel_name)
            continue

        _clear_material_input_links(node_tree, target_socket)
        connection = _direct_source_image_connection(source_socket)
        if connection is not None:
            _add_source_image_connection(
                decal_material,
                target_socket,
                connection,
                channel_name,
                vertical_offset,
            )
            continue

        if source_socket.is_linked:
            unsupported.append(channel_name)

        if channel_name == "Base Color":
            value = source_socket.default_value
            target_socket.default_value = (
                float(value[0]),
                float(value[1]),
                float(value[2]),
                1.0,
            )
        else:
            target_socket.default_value = float(source_socket.default_value)

    return True, tuple(unsupported)


def ensure_source_material_uv_map(decal_obj, decal_material):
    """Refresh UVMap.001 from source UV1 for copied source images."""
    if decal_obj is None or decal_obj.data is None or decal_material is None:
        return None
    if not getattr(decal_material, "use_nodes", False):
        return None
    if not any(
        node.type == "TEX_IMAGE" and node.get("edge_decal_source_channel")
        for node in decal_material.node_tree.nodes
    ):
        return None

    mesh = decal_obj.data
    data = getattr(decal_obj, "edge_decal_object_settings", None)
    source_obj = getattr(data, "source_object", None) if data else None
    transfer_fn = globals().get("transfer_source_first_uv_to_decal")
    if source_obj is not None and transfer_fn is not None:
        transferred = transfer_fn(source_obj, decal_obj)
        if transferred is not None:
            return transferred

    existing = mesh.uv_layers.get(SECOND_UV_LAYER_NAME)
    if existing is not None:
        return existing

    primary = ensure_decal_mesh_uv_layers(mesh)
    if len(mesh.uv_layers) >= 2:
        # UV2 is a reserved decal channel. Reuse its existing slot even when
        # an older workflow gave it another name; creating by name here would
        # add an unintended UVMap.002 third channel.
        second = mesh.uv_layers[1]
        second.name = SECOND_UV_LAYER_NAME
    else:
        second = mesh.uv_layers.new(name=SECOND_UV_LAYER_NAME)
        for source_uv, target_uv in zip(primary.data, second.data):
            target_uv.uv = source_uv.uv
    mesh.uv_layers.active = primary
    if hasattr(mesh.uv_layers, "active_render"):
        mesh.uv_layers.active_render = primary
    mesh.update()
    return second


def ensure_source_matched_decal_material(
    decal_obj,
    template_material,
    force_refresh=False,
):
    """Create, reuse, or refresh a source/template matched material."""
    if decal_obj is None or decal_obj.data is None or template_material is None:
        return template_material, ()

    data = getattr(decal_obj, "edge_decal_object_settings", None)
    template_material = root_decal_template_material(template_material)
    source_obj = getattr(data, "source_object", None) if data else None
    source_material = getattr(data, "source_material", None) if data else None
    if source_material is None:
        source_material = active_source_material(source_obj)
        if data is not None:
            data.source_material = source_material

    # A mesh without a source material keeps the historical direct assignment.
    if source_material is None:
        return template_material, ()

    def matches_source_and_template(material):
        return (
            material is not None
            and material.get("edge_decal_source_matched")
            and str(material.get("edge_decal_template_material_name", ""))
            == template_material.name_full
            and str(material.get("edge_decal_source_material_name", ""))
            == source_material.name_full
        )

    current = getattr(data, "decal_material", None) if data else None
    derived = current if matches_source_and_template(current) else None
    if derived is None:
        derived = next(
            (
                material
                for material in bpy.data.materials
                if matches_source_and_template(material)
            ),
            None,
        )
    reusable = derived is not None

    material_match_schema = 3
    if reusable:
        if (
            not force_refresh
            and int(derived.get("edge_decal_material_match_schema", 0))
            >= material_match_schema
        ):
            return derived, ()
    else:
        derived = template_material.copy()
        layer_index = int(decal_obj.get("edge_decal_index", 0))
        derived.name = (
            f"{template_material.name}_Matched_"
            f"{source_obj.name if source_obj is not None else 'Source'}_"
            f"{layer_index:02d}"
        )
        derived["edge_decal_source_matched"] = True
        derived["edge_decal_template_material_name"] = (
            template_material.name_full
        )

    derived["edge_decal_source_material_name"] = source_material.name_full
    updated, unsupported = update_source_channels_on_decal_material(
        derived,
        source_material,
    )
    # Viewport Display Color belongs to the decal template, not to the source
    # shader channels being matched above. Preserve it on both newly copied and
    # previously generated matched materials.
    derived.diffuse_color = tuple(template_material.diffuse_color)
    derived["edge_decal_material_match_schema"] = material_match_schema
    if not updated and not reusable:
        # Keep a distinct copy for this source/template pair even when it has
        # no top-level Principled node, so a different source cannot overwrite it.
        unsupported = ("Base Color", "Metallic", "Roughness")

    if data is not None:
        data.source_material = source_material
    return derived, unsupported


def apply_scene_decal_material(decal_obj, settings):
    """Assign a material, resolving preset assets only for real geometry."""
    global EDGEDECAL_SETTINGS_SYNCING

    if decal_obj is None or decal_obj.data is None:
        return None

    mesh = decal_obj.data

    if not getattr(settings, "use_material", True):
        mesh.materials.clear()
        for polygon in mesh.polygons:
            polygon.material_index = 0
        mesh.update()
        if hasattr(decal_obj, "edge_decal_object_settings"):
            data = decal_obj.edge_decal_object_settings
            previous_syncing = EDGEDECAL_SETTINGS_SYNCING
            EDGEDECAL_SETTINGS_SYNCING = True
            try:
                data.decal_material = None
                data.decal_template_material = None
                data.match_source_material = bool(
                    getattr(settings, "match_source_material", False)
                )
            finally:
                EDGEDECAL_SETTINGS_SYNCING = previous_syncing
        return None

    template_material = getattr(settings, "decal_material", None)
    pending_fn = globals().get("edge_decal_pending_preset_material_name")
    pending_name = (
        pending_fn(getattr(bpy.context, "scene", None), settings)
        if pending_fn is not None
        else ""
    )

    if len(mesh.polygons) > 0:
        resolve_fn = globals().get(
            "ensure_edge_decal_preset_material_for_use"
        )
        if resolve_fn is not None:
            resolved, _warnings, expected_name = resolve_fn(
                bpy.context,
                settings,
            )
            if resolved is not None:
                template_material = resolved
            pending_name = expected_name or pending_name

    if template_material is None and len(mesh.polygons) == 0:
        # Preset selection and empty-layer creation must not manufacture or
        # append datablocks. Clear stale state and wait for real geometry.
        mesh.materials.clear()
        if hasattr(decal_obj, "edge_decal_object_settings"):
            data = decal_obj.edge_decal_object_settings
            previous_syncing = EDGEDECAL_SETTINGS_SYNCING
            EDGEDECAL_SETTINGS_SYNCING = True
            try:
                data.decal_material = None
                data.decal_template_material = None
            finally:
                EDGEDECAL_SETTINGS_SYNCING = previous_syncing
        return None

    if template_material is None and pending_name:
        # Do not hide a missing preset asset by assigning an unrelated generic
        # material. The resolver has already emitted a precise warning.
        mesh.materials.clear()
        return None

    if template_material is None:
        template_material = get_or_create_material()
    template_material = root_decal_template_material(template_material)
    match_source_material = bool(
        getattr(settings, "match_source_material", False)
    )
    decal_material = template_material if not match_source_material else None
    if match_source_material and EDGEDECAL_STANDALONE_GENERATION:
        data = getattr(decal_obj, "edge_decal_object_settings", None)
        source_obj = getattr(data, "source_object", None) if data else None
        master = active_decal_layer_for_source(
            source_obj,
            include_locked=False,
        ) if source_obj is not None else None
        if master is None and regenerating_active():
            master = find_object_by_name_or_full(
                str(EDGEDECAL_REGENERATE_TARGET or "")
            )
        if master is not None and master is not decal_obj:
            master_data = getattr(master, "edge_decal_object_settings", None)
            master_template = (
                getattr(master_data, "decal_template_material", None)
                if master_data else None
            )
            if root_decal_template_material(master_template) == template_material:
                decal_material = getattr(master_data, "decal_material", None)
                if data is not None and master_data is not None:
                    data.source_material = master_data.source_material

    if match_source_material and decal_material is None:
        decal_material, _unsupported = ensure_source_matched_decal_material(
            decal_obj,
            template_material,
        )
    if match_source_material:
        ensure_source_material_uv_map(decal_obj, decal_material)

    mesh.materials.clear()
    mesh.materials.append(decal_material)

    for polygon in mesh.polygons:
        polygon.material_index = 0

    mesh.update()

    if hasattr(decal_obj, "edge_decal_object_settings"):
        data = decal_obj.edge_decal_object_settings
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            data.decal_template_material = template_material
            data.decal_material = decal_material
            data.match_source_material = match_source_material
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing

    return decal_material


class EDGEDECAL_OT_update_material(Operator):
    bl_idname = "object.edge_decal_update_material"
    bl_label = "Update Material"
    bl_description = (
        "Refresh this layer's Base Color, Metallic, Roughness, and matched "
        "source UVs from its stored source material and mesh"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source_obj = edge_decal_context_source(context)
        if source_obj is None:
            return False
        layer_obj = active_decal_layer_for_source(
            source_obj,
            context=context,
        )
        if layer_obj is None or layer_obj.data is None:
            return False
        data = layer_obj.edge_decal_object_settings
        material = getattr(data, "decal_material", None)
        return bool(
            getattr(data, "match_source_material", False)
            or (
                material is not None
                and material.get("edge_decal_source_matched")
            )
        )

    def execute(self, context):
        source_obj = edge_decal_context_source(context)
        layer_obj = active_decal_layer_for_source(
            source_obj,
            context=context,
        )
        if layer_obj is None:
            self.report({"ERROR"}, "No active edge decal layer")
            return {"CANCELLED"}

        data = layer_obj.edge_decal_object_settings
        material_is_matched = bool(
            getattr(data, "decal_material", None)
            and data.decal_material.get("edge_decal_source_matched")
        )
        if not (
            getattr(data, "match_source_material", False)
            or material_is_matched
        ):
            self.report({"ERROR"}, "Enable Match Material first")
            return {"CANCELLED"}
        template = (
            getattr(data, "decal_template_material", None)
            or root_decal_template_material(getattr(data, "decal_material", None))
            or root_decal_template_material(
                context.scene.edge_decal_settings.decal_material
            )
        )
        if template is None:
            self.report({"ERROR"}, "No edge decal material is assigned")
            return {"CANCELLED"}

        if getattr(data, "source_material", None) is None:
            data.source_material = active_source_material(source_obj)
        if data.source_material is None:
            self.report({"ERROR"}, "The source mesh has no material")
            return {"CANCELLED"}

        material, unsupported = ensure_source_matched_decal_material(
            layer_obj,
            template,
            force_refresh=True,
        )
        ensure_source_material_uv_map(layer_obj, material)
        mesh = layer_obj.data
        mesh.materials.clear()
        mesh.materials.append(material)
        for polygon in mesh.polygons:
            polygon.material_index = 0

        global EDGEDECAL_SETTINGS_SYNCING
        previous_syncing = EDGEDECAL_SETTINGS_SYNCING
        EDGEDECAL_SETTINGS_SYNCING = True
        try:
            data.decal_template_material = template
            data.decal_material = material
            data.match_source_material = True
        finally:
            EDGEDECAL_SETTINGS_SYNCING = previous_syncing

        if unsupported:
            self.report(
                {"WARNING"},
                "Updated material; unsupported linked "
                + ", ".join(unsupported)
                + " used their fallback values",
            )
        else:
            self.report(
                {"INFO"},
                f"Updated material and source UVs from "
                f"{data.source_material.name}",
            )
        return {"FINISHED"}


def iter_generated_decals(
    source_obj=None,
    mode=None,
    exclude=None,
):
    """Iterate generated decals regardless of their source collection."""
    registry_fn = globals().get("registered_decal_layers_for_source")
    registered = registry_fn(source_obj) if registry_fn is not None else None
    object_pool = registered if registered is not None else bpy.data.objects
    source_name = (
        source_obj.name_full
        if source_obj is not None
        else None
    )

    for candidate in object_pool:
        if (
            candidate is exclude
            or not decal_layer_is_valid(
                candidate,
                source_obj,
                assume_in_object_data=(registered is not None),
            )
        ):
            continue

        if (
            mode is not None
            and candidate.get(
                "edge_decal_mode",
                "SHARP_EDGES",
            ) != mode
        ):
            continue

        yield candidate


def locked_decal_source_edge_indices(source_obj):
    indices = set()
    for decal_obj in iter_generated_decals(source_obj=source_obj):
        if not decal_obj.get("edge_decal_locked", False):
            continue
        data = getattr(decal_obj, "edge_decal_object_settings", None)
        if data is not None and getattr(data, "initialized", False):
            indices.update(parsed_source_indices(data))
        base_raw = decal_obj.get("edge_decal_base_source_indices", "")
        if base_raw:
            for token in str(base_raw).split(","):
                token = token.strip()
                if not token:
                    continue
                try:
                    indices.add(int(token))
                except ValueError:
                    pass
    return indices


def next_decal_index(source_obj):
    """Return the next available decal number for this source object."""
    highest = 0

    for candidate in iter_generated_decals(source_obj=source_obj):
        try:
            highest = max(
                highest,
                int(candidate.get("edge_decal_index", 0)),
            )
        except (TypeError, ValueError):
            pass

    return highest + 1



def find_existing_edge_decal(
    source_obj,
    exclude=None,
    mode="SHARP_EDGES",
    context=None,
):
    """Prefer the active layer, then the lowest-index compatible layer."""
    active_layer = active_decal_layer_for_source(source_obj, context=context)
    if (
        active_layer is not None
        and active_layer is not exclude
        and active_layer.get("edge_decal_mode", "SHARP_EDGES") == mode
        and not active_layer.get("edge_decal_locked", False)
    ):
        return active_layer

    return min(
        (
            candidate
            for candidate in iter_generated_decals(
                source_obj=source_obj,
                mode=mode,
                exclude=exclude,
            )
            if not candidate.get("edge_decal_locked", False)
        ),
        key=lambda candidate: int(
            candidate.get("edge_decal_index", 0)
        ),
        default=None,
    )


def merge_generated_decal_objects(existing_obj, new_obj):
    """
    Append new_obj's base mesh and UVs into existing_obj.

    Preserves:
    - existing modifiers and parenting
    - UV coordinates from both objects
    - material slots and per-face material indices
    - smooth shading
    - centerline vertex-group membership
    """
    existing_mesh = existing_obj.data
    new_mesh = new_obj.data

    if hasattr(existing_obj, "visible_shadow"):
        existing_obj.visible_shadow = False

    existing_vertices = [
        vertex.co.copy()
        for vertex in existing_mesh.vertices
    ]
    new_vertices = [
        vertex.co.copy()
        for vertex in new_mesh.vertices
    ]
    vertex_offset = len(existing_vertices)

    combined_vertices = existing_vertices + new_vertices

    existing_faces = [
        tuple(polygon.vertices)
        for polygon in existing_mesh.polygons
    ]
    new_faces = [
        tuple(
            vertex_index + vertex_offset
            for vertex_index in polygon.vertices
        )
        for polygon in new_mesh.polygons
    ]
    combined_faces = existing_faces + new_faces

    # Preserve material slots from both meshes and remap polygon indices.
    combined_materials = []

    def material_slot_index(material):
        for index, existing_material in enumerate(combined_materials):
            if existing_material == material:
                return index

        combined_materials.append(material)
        return len(combined_materials) - 1

    existing_material_map = {
        slot_index: material_slot_index(material)
        for slot_index, material in enumerate(existing_mesh.materials)
        if material is not None
    }
    new_material_map = {
        slot_index: material_slot_index(material)
        for slot_index, material in enumerate(new_mesh.materials)
        if material is not None
    }

    existing_material_indices = [
        existing_material_map.get(polygon.material_index, 0)
        for polygon in existing_mesh.polygons
    ]
    new_material_indices = [
        new_material_map.get(polygon.material_index, 0)
        for polygon in new_mesh.polygons
    ]
    combined_material_indices = (
        existing_material_indices + new_material_indices
    )

    combined_smooth_flags = (
        [polygon.use_smooth for polygon in existing_mesh.polygons]
        + [polygon.use_smooth for polygon in new_mesh.polygons]
    )

    uv_layer_count = max(
        len(existing_mesh.uv_layers),
        len(new_mesh.uv_layers),
        1,
    )
    uv_layer_names = []
    for layer_index in range(uv_layer_count):
        existing_layer = (
            existing_mesh.uv_layers[layer_index]
            if layer_index < len(existing_mesh.uv_layers)
            else None
        )
        new_layer = (
            new_mesh.uv_layers[layer_index]
            if layer_index < len(new_mesh.uv_layers)
            else None
        )
        if layer_index == 1 and any(
            layer is not None and layer.name == "UVMap.001"
            for layer in (existing_layer, new_layer)
        ):
            uv_layer_names.append("UVMap.001")
        elif existing_layer is not None:
            uv_layer_names.append(existing_layer.name)
        elif new_layer is not None:
            uv_layer_names.append(new_layer.name)
        else:
            uv_layer_names.append("UVMap")

    def mesh_face_uvs(mesh, layer_index):
        uv_layer = (
            mesh.uv_layers[layer_index]
            if layer_index < len(mesh.uv_layers)
            else None
        )
        result = []

        for polygon in mesh.polygons:
            if uv_layer is None:
                result.append([
                    Vector((0.0, 0.0))
                    for _ in polygon.loop_indices
                ])
            else:
                result.append([
                    uv_layer.data[loop_index].uv.copy()
                    for loop_index in polygon.loop_indices
                ])

        return result

    combined_uvs_by_layer = {
        layer_index: (
            mesh_face_uvs(existing_mesh, layer_index)
            + mesh_face_uvs(new_mesh, layer_index)
        )
        for layer_index in range(uv_layer_count)
    }

    existing_center_group = existing_obj.vertex_groups.get(
        "EdgeDecal_Center"
    )
    existing_center_indices = set()

    if existing_center_group is not None:
        group_index = existing_center_group.index

        for vertex in existing_mesh.vertices:
            if any(
                membership.group == group_index
                and membership.weight > 0.0
                for membership in vertex.groups
            ):
                existing_center_indices.add(vertex.index)

    new_center_group = new_obj.vertex_groups.get("EdgeDecal_Center")
    new_center_indices = set()

    if new_center_group is not None:
        group_index = new_center_group.index

        for vertex in new_mesh.vertices:
            if any(
                membership.group == group_index
                and membership.weight > 0.0
                for membership in vertex.groups
            ):
                new_center_indices.add(
                    vertex.index + vertex_offset
                )

    replacement_mesh = bpy.data.meshes.new(
        f"{existing_obj.name}_MergedMesh"
    )
    replacement_mesh.from_pydata(
        [tuple(vertex) for vertex in combined_vertices],
        [],
        combined_faces,
    )
    replacement_mesh.update(calc_edges=True)

    for material in combined_materials:
        replacement_mesh.materials.append(material)

    for polygon, material_index, use_smooth in zip(
        replacement_mesh.polygons,
        combined_material_indices,
        combined_smooth_flags,
    ):
        polygon.material_index = material_index
        polygon.use_smooth = use_smooth

    for layer_index, layer_name in enumerate(uv_layer_names):
        uv_layer = replacement_mesh.uv_layers.new(name=layer_name)

        for polygon, polygon_uvs in zip(
            replacement_mesh.polygons,
            combined_uvs_by_layer[layer_index],
        ):
            for loop_index, uv in zip(
                polygon.loop_indices,
                polygon_uvs,
            ):
                uv_layer.data[loop_index].uv = uv

    replacement_mesh.uv_layers.active = replacement_mesh.uv_layers[0]
    if hasattr(replacement_mesh.uv_layers, "active_render"):
        replacement_mesh.uv_layers.active_render = replacement_mesh.uv_layers[0]

    old_mesh = existing_obj.data
    existing_obj.data = replacement_mesh

    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    center_group = existing_obj.vertex_groups.get("EdgeDecal_Center")
    if center_group is not None:
        existing_obj.vertex_groups.remove(center_group)

    center_group = existing_obj.vertex_groups.new(
        name="EdgeDecal_Center"
    )
    combined_center_indices = sorted(
        existing_center_indices | new_center_indices
    )

    if combined_center_indices:
        center_group.add(
            combined_center_indices,
            1.0,
            "REPLACE",
        )

    # The merged object must remember every source edge represented by both
    # meshes. Otherwise Update Decal regenerates only one stroke and appears to
    # delete the other interactively generated sections.
    merge_stored_decal_source_data(existing_obj, new_obj)

    mode = new_obj.get("edge_decal_mode")
    if mode:
        existing_obj["edge_decal_mode"] = mode
    if new_obj.get("edge_decal_selected_graph", False):
        existing_obj["edge_decal_selected_graph"] = True

    temporary_mesh = new_obj.data
    bpy.data.objects.remove(new_obj, do_unlink=True)

    if temporary_mesh.users == 0:
        bpy.data.meshes.remove(temporary_mesh)

    return existing_obj
