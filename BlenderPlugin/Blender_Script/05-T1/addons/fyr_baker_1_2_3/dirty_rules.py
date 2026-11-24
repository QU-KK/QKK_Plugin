from __future__ import annotations

from . import constants


DirtyMatrix = dict[str, set[str]]


# Every stored row type whose output is a function of the bake group's meshes: their
# shape, their UVs, and where they sit in the scene. A mesh edit or a move invalidates
# all of them, and so does a change to the group's projection settings.
#
# This set is a WHITELIST, so anything missing from it is silently never dirtied. Three
# families were missing and each one served pre-edit pixels in a live session while
# Normal/AO/Curvature rebaked around them:
#
#  * DENSITY  - a probe map in the Thickness family (constants.MAP_STACK_DETAIL_MASK_MAPS,
#               MAP_SAMPLE_CONTROL_TYPES, the shared thickness_settings block). It was a
#               plain omission: nothing about it differs from THICKNESS here.
#  * MATERIAL - MAP_MATERIAL rows ride the same HIGH_TO_LOW backend IR path as the
#               projection maps (see the map-config loop in export.py), so the cage, the
#               high's shape and the low's UVs decide every texel exactly as they do for
#               NORMAL.
#  * LIGHTING - on the Fyr route a SCENE_LIGHTING / LIGHTING / LIT_COLOR row is an
#               ordinary map config in the same projection job (export._build_scene_lighting_config
#               rides alongside the other map configs); on the Cycles route it is a
#               COMBINED bake of the low itself (cycles_projection._CYCLES_MAP_STRATEGIES).
#               Either way, edit the low's shape or move it relative to the lights and
#               every lit texel changes.
#
# Widening this costs nothing on a project that does not use those rows: the dirty matrix
# is intersected with the project's ENABLED rows before any bake is prepared
# (dirty_rules.select_dirty_rebake_batch, called from the live-rebake timer). And it makes
# the live tracker agree with the committed path rather than exceed it -- map_rebuild's
# "Rebuild Changed Maps" already returns EVERY enabled row when its projection_groups
# state (vertex counts, matrix_world, bounds, uv digest) differs.
PROJECTION_MAPS: frozenset[str] = frozenset({
    constants.MAP_NORMAL,
    constants.MAP_OBJECT_NORMAL,
    constants.MAP_WORLD_NORMAL,
    constants.MAP_AO,
    constants.MAP_THICKNESS,
    constants.MAP_DENSITY,
    constants.MAP_BENT_NORMAL,
    constants.MAP_POSITION,
    constants.MAP_HEIGHT,
    constants.MAP_CURVATURE,
    constants.MAP_CAVITY,
    constants.MAP_CONCAVE,
    constants.MAP_CONVEX,
    constants.MAP_VERTEX_COLOR,
    constants.MAP_ATTRIBUTE,
    # Drawn from the low's UVs and topology, which a low edit changes.
    constants.MAP_WIREFRAME,
    constants.MAP_OPACITY,
    constants.MAP_ENV_LIGHT,
    constants.MAP_MATERIAL,
}) | constants.LIGHTING_FAMILY_MAP_TYPES

ALL_REBAKE_MAPS: frozenset[str] = frozenset(set(PROJECTION_MAPS) | {constants.MAP_ID})

# Rows whose output is ALSO shaped by the scene's lights and world, not just by the bake
# group. They are a SUBSET of the sets above, not an alternative to them: a light or world
# edit dirties only these (see dirty_tracker._lighting_scene_signature), while a mesh edit
# or a move dirties them along with every other projected row. Includes the legacy pre-
# consolidation types so a .blend saved before the SCENE_LIGHTING retype still matches.
LIGHTING_MAPS: frozenset[str] = constants.LIGHTING_FAMILY_MAP_TYPES


def normalize_map_type(value: str) -> str:
    return str(value or "").strip().upper()


def normalize_map_types(values) -> set[str]:
    return {
        normalized
        for normalized in (normalize_map_type(value) for value in (values or ()))
        if normalized
    }


def enabled_map_types_from_settings(map_settings) -> list[str]:
    enabled: list[str] = []
    for item in map_settings or ():
        if not bool(getattr(item, "enabled", False)):
            continue
        map_type = normalize_map_type(getattr(item, "map_type", ""))
        if map_type:
            enabled.append(map_type)
    return enabled


def projection_dirty_map_types(map_settings) -> list[str]:
    return [map_type for map_type in enabled_map_types_from_settings(map_settings) if map_type in PROJECTION_MAPS]


def lighting_dirty_map_types(map_settings) -> list[str]:
    """Enabled row types that must rebake when the scene's lights or world change."""
    return [map_type for map_type in enabled_map_types_from_settings(map_settings) if map_type in LIGHTING_MAPS]


def world_lighting_dirty_map_types(map_settings) -> list[str]:
    """Enabled lighting row types that see every group (Include Other Groups): any group's
    mesh edit or move changes their shadows and bounces, not only their own group's."""
    types: list[str] = []
    for item in map_settings or ():
        if not bool(getattr(item, "enabled", False)):
            continue
        map_type = normalize_map_type(getattr(item, "map_type", ""))
        if map_type in LIGHTING_MAPS and bool(getattr(item, "lighting_occlude_other_groups", True)):
            types.append(map_type)
    return types


def world_occlusion_dirty_map_types(map_settings) -> list[str]:
    """Enabled rows whose rays hit other groups' highs (Occlude / Include Other Groups):
    an edit or move of a high in any group changes them, and a job holding only some
    groups would bake them without the rest of the scene."""
    types: list[str] = []
    for item in map_settings or ():
        if not bool(getattr(item, "enabled", False)):
            continue
        map_type = normalize_map_type(getattr(item, "map_type", ""))
        if map_type in constants.WORLD_OCCLUSION_MAP_TYPES and bool(getattr(item, "ao_occlude_other_groups", False)):
            types.append(map_type)
    return types


def tangent_basis_dirty_map_types(map_settings) -> list[str]:
    affected: list[str] = []
    for item in map_settings or ():
        if not bool(getattr(item, "enabled", False)):
            continue
        map_type = normalize_map_type(getattr(item, "map_type", ""))
        if map_type == constants.MAP_NORMAL:
            affected.append(map_type)
            continue
        if map_type != constants.MAP_BENT_NORMAL:
            continue
        normal_space = normalize_map_type(getattr(item, "normal_space", ""))
        if not normal_space or normal_space == constants.MAP_NORMAL_SPACE_TANGENT:
            affected.append(map_type)
    return affected


def select_dirty_rebake_batch(dirty_groups: DirtyMatrix, enabled_map_types) -> DirtyMatrix:
    normalized_enabled = normalize_map_types(enabled_map_types)
    if not normalized_enabled:
        return {}

    buckets: dict[tuple[str, ...], list[str]] = {}
    for group_name, map_types in (dirty_groups or {}).items():
        normalized_group_name = str(group_name or "").strip()
        if not normalized_group_name:
            continue
        selected_map_types = tuple(sorted(normalize_map_types(map_types) & normalized_enabled))
        if not selected_map_types:
            continue
        buckets.setdefault(selected_map_types, []).append(normalized_group_name)

    if not buckets:
        return {}

    best_key: tuple[int, int, tuple[str, ...], tuple[str, ...]] | None = None
    best_map_types: tuple[str, ...] = ()
    best_group_names: list[str] = []
    for map_types, group_names in buckets.items():
        normalized_group_names = sorted({str(name or "").strip() for name in group_names if str(name or "").strip()})
        candidate_key = (-len(normalized_group_names), -len(map_types), map_types, tuple(normalized_group_names))
        if best_key is not None and candidate_key >= best_key:
            continue
        best_key = candidate_key
        best_map_types = map_types
        best_group_names = normalized_group_names

    return {group_name: set(best_map_types) for group_name in best_group_names}
