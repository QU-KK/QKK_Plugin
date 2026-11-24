from __future__ import annotations

import time

import bpy

from . import mesh_read
from . import constants, dirty_rules, mesh_digest, properties

# ---------------------------------------------------------------------------
# Type alias: maps group_name -> set of map_type strings that need rebaking.
# ---------------------------------------------------------------------------
DirtyMatrix = dict[str, set[str]]

# Maps that must be rebaked when only a transform changes (no geometry change).
# Excludes ID because material slots / collection membership is not transform data.
_PROJECTION_MAPS: frozenset[str] = dirty_rules.PROJECTION_MAPS

# All maps dirtied when geometry changes (every map type we know about).
_ALL_REBAKE_MAPS: frozenset[str] = dirty_rules.ALL_REBAKE_MAPS

# ---------------------------------------------------------------------------
# Module-level state (all transient; never persisted to disk).
# ---------------------------------------------------------------------------
_dirty_groups: DirtyMatrix = {}
_dirty_group_objects: dict[str, set[str]] = {}
_last_dirty_time: float = 0.0
_membership_index: dict[str, list[str]] = {}  # object_name -> [group_name, ...]
_high_membership_index: dict[str, list[str]] = {}  # high_object_name -> [owning_group_name, ...]
# Custom cages that are not also a low/high: their UVs never reach a bake, so both the
# fingerprint baseline and the handler skip the UV digest for them.
_cage_only_names: set[str] = set()
_global_high_scene_group_names: list[str] = []  # groups whose projection can see high meshes from other groups
_texture_set_siblings: dict[str, list[str]] = {}  # group_name -> [sibling_group_name, ...] (only groups in multi-group sets)
_session_active: bool = False
_debounce_seconds: float = 0.3
_suppress_count: int = 0  # >0 means _on_depsgraph_update is silenced
_cooldown_until: float = 0.0  # depsgraph updates ignored until this monotonic time
# Per-object geometry fingerprints (see _geometry_fingerprint): counts, bounding box, a
# coordinate digest, and the UV digest for lows.
# Changed fingerprint = real geometry edit.  Unchanged = mode switch / noise.
_geometry_fingerprints: dict[str, tuple] = {}
# Per-object material slot hashes (preview materials excluded).
_material_hashes: dict[str, str] = {}
# Scene-lighting inputs (every light + the world) as one string, plus the row types and
# groups that consume them.  Empty _lighting_map_types = the project has no enabled
# lighting row, so the signature is never computed at all.
_lighting_signature: str = ""
_lighting_map_types: list[str] = []
_lighting_group_names: list[str] = []
_world_lighting_map_types: list[str] = []  # lighting rows with Include Other Groups (see dirty_rules)
_world_occlusion_map_types: list[str] = []  # AO-family rows with Occlude Other Groups (see dirty_rules)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PREVIEW_MATERIAL_PREFIX = constants.PREVIEW_MATERIAL_NAME_PREFIX


def _hash_material_slots(obj) -> str:
    """Return a cheap string fingerprint of an object's material slot assignments.

    Preview materials are excluded so toggling PBR / live-normal preview never
    looks like a real material change to the dirty tracker.
    """
    slots = getattr(obj, "material_slots", None)
    if not slots:
        return ""
    names: list[str] = []
    for slot in slots:
        mat = getattr(slot, "material", None)
        name = str(getattr(mat, "name", "") or "")
        if name.startswith(_PREVIEW_MATERIAL_PREFIX):
            continue
        names.append(name)
    return "|".join(names)


def _build_membership_index(project) -> dict[str, list[str]]:
    """Return object_name -> [group_name, ...] for every low, high, and cage object."""
    index: dict[str, list[str]] = {}

    def _register(obj_name: str, group_name: str) -> None:
        if not obj_name:
            return
        if obj_name not in index:
            index[obj_name] = []
        if group_name not in index[obj_name]:
            index[obj_name].append(group_name)

    for group in getattr(project, "groups", []):
        gname = str(getattr(group, "name", "") or "").strip()
        if not gname:
            continue
        for slot_collection in (
            getattr(group, "low_meshes", []),
            properties.effective_high_mesh_slots(group),
        ):
            for slot in slot_collection:
                obj = getattr(slot, "object_ref", None)
                if obj is None:
                    continue
                _register(str(getattr(obj, "name", "") or "").strip(), gname)
        cage_obj = getattr(group, "custom_cage", None)
        if cage_obj is not None:
            _register(str(getattr(cage_obj, "name", "") or "").strip(), gname)

    return index


def _build_high_membership_index(project) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for group in getattr(project, "groups", []):
        gname = str(getattr(group, "name", "") or "").strip()
        if not gname:
            continue
        for slot in properties.effective_high_mesh_slots(group):
            obj = getattr(slot, "object_ref", None)
            if obj is None:
                continue
            obj_name = str(getattr(obj, "name", "") or "").strip()
            if not obj_name:
                continue
            index.setdefault(obj_name, [])
            if gname not in index[obj_name]:
                index[obj_name].append(gname)
    return index


def _build_global_high_scene_group_names(project) -> list[str]:
    group_names: list[str] = []
    for group in getattr(project, "groups", []):
        gname = str(getattr(group, "name", "") or "").strip()
        if not gname:
            continue
        projection_state = properties.group_projection_settings_state(group)
        if not bool(getattr(projection_state, "match_by_isolation", False)):
            group_names.append(gname)
    return group_names


def _build_material_hashes(project) -> dict[str, str]:
    """Baseline slot fingerprints for every low and high, keyed by object name.

    Deliberately NOT the same walk as _build_membership_index: the custom cage belongs
    there (it is bake input as geometry) but not here, because no cage material reaches
    the ID map. _on_depsgraph_update uses these keys as the registry of objects whose
    material slots are worth comparing -- adding the cage here would resurrect the
    spurious ID rebakes this exclusion exists to prevent, just with a baseline attached.
    """
    hashes: dict[str, str] = {}
    for group in getattr(project, "groups", []):
        for slot_collection in (
            getattr(group, "low_meshes", []),
            properties.effective_high_mesh_slots(group),
        ):
            for slot in slot_collection:
                obj = getattr(slot, "object_ref", None)
                if obj is None:
                    continue
                obj_name = str(getattr(obj, "name", "") or "").strip()
                if obj_name:
                    hashes[obj_name] = _hash_material_slots(obj)
    return hashes


_LIGHTING_SIGNATURE_LIGHT_TYPES = ("POINT", "SPOT", "SUN", "AREA")


def _lighting_light_signature(obj) -> str:
    """One light's bake-relevant state, mirroring export._build_scene_light_record."""
    data = getattr(obj, "data", None)
    light_type = str(getattr(data, "type", "") or "").upper()
    parts: list[str] = [
        str(getattr(obj, "name", "") or ""),
        light_type,
        f"{float(getattr(data, 'energy', 0.0) or 0.0):.6g}",
        ",".join(f"{float(component):.6g}" for component in tuple(getattr(data, "color", (1.0, 1.0, 1.0)))[:3]),
        "1" if bool(getattr(obj, "hide_render", False)) else "0",
        "1" if bool(getattr(data, "use_shadow", True)) else "0",
        f"{float(getattr(data, 'diffuse_factor', 1.0) or 1.0):.6g}",
        f"{float(getattr(data, 'specular_factor', 1.0)):.6g}",
        "1" if bool(getattr(obj, "visible_diffuse", True)) else "0",
        "1" if bool(getattr(obj, "visible_glossy", True)) else "0",
        f"{float(getattr(data, 'shadow_soft_size', 0.0) or 0.0):.6g}",
        f"{float(getattr(data, 'angle', 0.0) or 0.0):.6g}",
        f"{float(getattr(data, 'spot_size', 0.0) or 0.0):.6g}",
        f"{float(getattr(data, 'spot_blend', 0.0) or 0.0):.6g}",
        str(getattr(data, "shape", "") or ""),
        f"{float(getattr(data, 'size', 0.0) or 0.0):.6g}",
        f"{float(getattr(data, 'size_y', 0.0) or 0.0):.6g}",
    ]
    matrix = getattr(obj, "matrix_world", None)
    if matrix is not None:
        try:
            parts.append(",".join(f"{float(value):.6g}" for row in matrix for value in row))
        except (TypeError, ValueError):
            pass
    return "|".join(parts)


def _lighting_world_signature(scene) -> str:
    """The world's bake-relevant state, mirroring export._build_scene_world_record.

    Node graphs are summarized by the Background node's Color/Strength (plus the linked
    Environment Texture's identity), which is exactly the set of inputs the lighting job
    carries. A deeper procedural graph edit is not detected here -- the same limitation
    the export path already has."""
    world = getattr(scene, "world", None)
    if world is None:
        return "NONE"
    parts: list[str] = [str(getattr(world, "name", "") or "")]
    if not bool(getattr(world, "use_nodes", False)):
        parts.append("COLOR")
        parts.append(",".join(f"{float(c):.6g}" for c in tuple(getattr(world, "color", (0.0, 0.0, 0.0)))[:3]))
        return "|".join(parts)
    node_tree = getattr(world, "node_tree", None)
    for node in getattr(node_tree, "nodes", None) or ():
        if str(getattr(node, "type", "") or "") != "BACKGROUND":
            continue
        inputs = getattr(node, "inputs", None)
        color_input = inputs.get("Color") if hasattr(inputs, "get") else None
        strength_input = inputs.get("Strength") if hasattr(inputs, "get") else None
        parts.append(f"{float(getattr(strength_input, 'default_value', 1.0) or 0.0):.6g}")
        if color_input is not None and bool(getattr(color_input, "is_linked", False)):
            parts.append("LINKED")
            for link in getattr(color_input, "links", None) or ():
                image = getattr(getattr(link, "from_node", None), "image", None)
                parts.append(str(getattr(image, "name", "") or ""))
        elif color_input is not None:
            parts.append(
                ",".join(f"{float(c):.6g}" for c in tuple(getattr(color_input, "default_value", (0.0, 0.0, 0.0, 1.0)))[:3])
            )
        break
    return "|".join(parts)


def _lighting_scene_signature(scene) -> str:
    """Cheap digest of every input a SCENE_LIGHTING bake reads from the scene.

    Cost is O(number of lights); it is only ever computed when the project has an
    enabled lighting row AND the depsgraph reported a light / world / scene change.

    Walks ``scene.objects`` rather than the depsgraph's object_instances the export path
    uses, to stay off the evaluated graph on a handler: a light that only exists as a
    collection-instance dupli therefore does not register here."""
    if scene is None:
        return ""
    signatures: list[str] = []
    for obj in getattr(scene, "objects", None) or ():
        if str(getattr(obj, "type", "") or "") != "LIGHT":
            continue
        data = getattr(obj, "data", None)
        if str(getattr(data, "type", "") or "").upper() not in _LIGHTING_SIGNATURE_LIGHT_TYPES:
            continue
        signatures.append(_lighting_light_signature(obj))
    signatures.sort()
    return "\n".join(signatures) + "\nworld=" + _lighting_world_signature(scene)


def lighting_scene_signature(scene=None) -> str:
    """Public wrapper for :func:`_lighting_scene_signature`, defaulting to the active scene.

    Used by map_rebuild to fold the lighting inputs into a lighting row's recorded bake
    state, so "Rebuild Changed Maps" sees a light/world edit the same way this tracker does."""
    if scene is None:
        scene = getattr(getattr(bpy, "context", None), "scene", None)
    return _lighting_scene_signature(scene)


def _build_lighting_map_types(project) -> list[str]:
    return dirty_rules.lighting_dirty_map_types(getattr(project, "maps", []))


def _build_group_names(project) -> list[str]:
    names: list[str] = []
    for group in getattr(project, "groups", []):
        gname = str(getattr(group, "name", "") or "").strip()
        if gname and gname not in names:
            names.append(gname)
    return names


def _refresh_lighting_state(project, scene=None) -> None:
    global _lighting_signature, _lighting_map_types, _lighting_group_names, _world_lighting_map_types
    global _world_occlusion_map_types
    _lighting_map_types = _build_lighting_map_types(project)
    _lighting_group_names = _build_group_names(project)
    _world_lighting_map_types = dirty_rules.world_lighting_dirty_map_types(getattr(project, "maps", []))
    _world_occlusion_map_types = dirty_rules.world_occlusion_dirty_map_types(getattr(project, "maps", []))
    if not _lighting_map_types:
        _lighting_signature = ""
        return
    if scene is None:
        scene = getattr(getattr(bpy, "context", None), "scene", None)
    _lighting_signature = _lighting_scene_signature(scene)


def _lighting_relevant_id_types() -> tuple[type, ...]:
    # Resolved defensively (and never `object`, which would match every id) so a partial
    # bpy stand-in cannot turn the gate into "always relevant" or an AttributeError.
    types_module = getattr(bpy, "types", None)
    return tuple(
        candidate
        for candidate in (
            getattr(types_module, "Light", None),
            getattr(types_module, "World", None),
            getattr(types_module, "Scene", None),
        )
        if isinstance(candidate, type) and candidate is not object
    )


def _lighting_update_is_relevant(depsgraph) -> bool:
    """Whether this depsgraph batch could have changed a light or the world.

    Light removal reports the Scene, not the (gone) object, so Scene counts too."""
    relevant_types = _lighting_relevant_id_types()
    object_type = getattr(getattr(bpy, "types", None), "Object", None)
    for update in getattr(depsgraph, "updates", None) or ():
        id_data = getattr(update, "id", None)
        if id_data is None:
            continue
        if relevant_types and isinstance(id_data, relevant_types):
            return True
        if (
            isinstance(object_type, type)
            and isinstance(id_data, object_type)
            and str(getattr(id_data, "type", "") or "").upper() == "LIGHT"
        ):
            return True
    return False


def _process_lighting_updates(scene, depsgraph) -> None:
    global _lighting_signature
    if not _lighting_map_types or not _lighting_group_names:
        return
    if not _lighting_update_is_relevant(depsgraph):
        return
    signature = _lighting_scene_signature(scene)
    if signature == _lighting_signature:
        return
    _lighting_signature = signature
    dirty_maps = set(_lighting_map_types)
    for group_name in _lighting_group_names:
        _mark_dirty_internal(group_name, dirty_maps)


def _build_texture_set_siblings(project) -> dict[str, list[str]]:
    """Return group_name -> [sibling_group_names] for groups in multi-group texture sets."""
    ts_groups: dict[str, list[str]] = {}
    for group in getattr(project, "groups", []):
        gname = str(getattr(group, "name", "") or "").strip()
        if not gname:
            continue
        ts = (getattr(properties.group_metadata_state(group), "texture_set_name", "") or "").strip()
        if ts:
            ts_groups.setdefault(ts.casefold(), []).append(gname)
    siblings: dict[str, list[str]] = {}
    for members in ts_groups.values():
        if len(members) < 2:
            continue
        for gname in members:
            siblings[gname] = [m for m in members if m != gname]
    return siblings


# ---------------------------------------------------------------------------
# Depsgraph handler
# ---------------------------------------------------------------------------

def suppress():
    """Context manager: silence _on_depsgraph_update for the duration."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        global _suppress_count
        _suppress_count += 1
        try:
            yield
        finally:
            _suppress_count -= 1

    return _ctx()


def is_silenced() -> bool:
    """True while dirty tracking is suppressed or inside the post-bake cooldown.

    Other depsgraph listeners (Live Reproject) use this to ignore the addon's
    own writes: preview-material swaps, image reloads, and the bake-time
    visibility sweep all fire depsgraph updates that are not artist edits."""
    return _suppress_count > 0 or time.monotonic() < _cooldown_until


def set_post_bake_cooldown(seconds: float = 1.5) -> None:
    """Silence dirty tracking for `seconds` after a bake completes.

    Blender fires depsgraph updates for image reloads and preview material
    changes AFTER the timer callback returns, so a context-manager suppress
    doesn't catch them.  A time-based cooldown covers the async window.
    """
    global _cooldown_until
    _cooldown_until = time.monotonic() + seconds


def mesh_uv_digest(obj) -> str:
    """Digest of every UV layer on ``obj``'s mesh, "" when it has none.

    A UV edit (unwrap, island move, repack) changes no vertex, count, or bound,
    so the shape fingerprint below cannot see it, yet every projected map is
    written through those UVs. One foreach_get per layer into numpy plus a
    blake2b of the bytes costs a few milliseconds on a production low mesh;
    callers keep it off high meshes, which bake FROM their surface and whose
    UVs never reach the output.
    """
    data = getattr(obj, "data", None)
    layers = getattr(data, "uv_layers", None)
    if not layers:
        return ""
    try:
        import hashlib

        import numpy as np

        digest = hashlib.blake2b(digest_size=8)
        for layer in layers:
            loops = getattr(layer, "data", None)
            count = len(loops) if loops is not None else 0
            digest.update(str(getattr(layer, "name", "") or "").encode("utf-8", "replace"))
            digest.update(count.to_bytes(8, "little"))
            if count <= 0:
                continue
            buffer = np.empty(count * 2, dtype=np.float32)
            loops.foreach_get("uv", buffer)
            digest.update(buffer.tobytes())
        return digest.hexdigest()
    except Exception:
        return ""


# The exact/strided coordinate digest lives in mesh_digest so map_rebuild -- which
# loads before bpy is safe and so cannot import this module -- uses the same policy
# rather than a weaker counts-and-bounds comparison of its own.
_EXACT_SHAPE_DIGEST_MAX_VERTS = mesh_digest.EXACT_SHAPE_DIGEST_MAX_VERTS
_SAMPLED_SHAPE_VERTS = mesh_digest.SAMPLED_SHAPE_VERTS
_mesh_shape_digest = mesh_digest.mesh_shape_digest_from_vertices


def _geometry_fingerprint(obj, *, include_uvs: bool = False) -> tuple:
    """Proxy for evaluated mesh shape in object mode.

    Vertex count, polygon count, bounding box, and a digest of the vertex coordinates
    (see :func:`_mesh_shape_digest` for the exact/sampled split and its cost).
    ``include_uvs`` folds in :func:`mesh_uv_digest` (low meshes only).
    """
    data = getattr(obj, "data", None)
    verts = getattr(data, "vertices", None)
    v_count = len(verts) if verts is not None else 0
    p_count = mesh_read.element_count(data, "polygons")

    bb = getattr(obj, "bound_box", None)
    try:
        bb_flat = tuple(round(float(c), 4) for corner in bb for c in corner[:3]) if bb else ()
    except Exception:
        bb_flat = ()

    shape_digest = _mesh_shape_digest(verts, v_count)

    uv_digest = mesh_uv_digest(obj) if include_uvs else ""
    return (v_count, p_count, bb_flat, shape_digest, uv_digest)


def _on_depsgraph_update(scene, depsgraph) -> None:  # noqa: ARG001
    global _material_hashes, _last_dirty_time

    if _suppress_count > 0:
        return
    if _cooldown_until > 0.0 and time.monotonic() < _cooldown_until:
        return
    if not _session_active:
        return

    # Lights and the world live outside the mesh membership index, so this runs before
    # (and independently of) the per-object walk below.
    _process_lighting_updates(scene, depsgraph)

    if not _membership_index:
        return

    for update in depsgraph.updates:
        id_data = getattr(update, "id", None)
        if id_data is None:
            continue

        if not isinstance(id_data, bpy.types.Object):
            continue
        if getattr(id_data, "type", "") != "MESH":
            continue

        obj_name = str(getattr(id_data, "name", "") or "").strip()
        group_names_for_obj = _membership_index.get(obj_name)
        if not group_names_for_obj:
            continue

        # --- Positive list: only dirty on changes that affect bake output ---

        # 1. Transform change (moves/rotates/scales the object in world space).
        geometry_changed = False
        transform_changed = bool(update.is_updated_transform)

        # 2. Real geometry change: vertex/polygon count or shape changed.
        #    id_data is the EVALUATED object; we fingerprint the ORIGINAL object
        #    (bpy.data.objects[name]) so modifiers don't cause a mismatch with the
        #    session-start baseline (which is also computed from the original).
        #    We skip the check while in edit mode and only compare on exit.
        if update.is_updated_geometry:
            in_edit = getattr(id_data, "mode", "OBJECT") == "EDIT"
            if not in_edit:
                try:
                    orig_obj = bpy.data.objects.get(obj_name)
                except Exception:
                    orig_obj = None
                if orig_obj is not None and not _high_is_parked(orig_obj):
                    # (A parked high is an empty placeholder until the restore reaches it:
                    # its fingerprint would read as "everything changed".)
                    # Must match _build_geometry_fingerprints' rule exactly, or the
                    # baseline and this comparison disagree about the UV term and every
                    # fingerprint mismatches for the wrong reason.
                    fp = _geometry_fingerprint(
                        orig_obj,
                        include_uvs=(
                            obj_name not in _high_membership_index
                            and obj_name not in _cage_only_names
                        ),
                    )
                    prev_fp = _geometry_fingerprints.get(obj_name)
                    _geometry_fingerprints[obj_name] = fp
                    if prev_fp is not None and fp != prev_fp:
                        geometry_changed = True

        # 3. Material slot reassignment (ID map, not preview materials).
        #    Preview material names are filtered by _hash_material_slots.
        #
        #    Only lows and highs are checked, because only their slots reach the ID map --
        #    and _build_material_hashes walks exactly those two collections, so its keys
        #    ARE the registry. The membership index is wider: it also carries the custom
        #    cage, which is bake input as geometry only. A cage is usually a duplicate of
        #    the low, so it arrives carrying the low's materials with no baseline hash,
        #    and the old unconditional check compared that real slot list against the ""
        #    default: the first nudge of a custom cage in a live session reported a
        #    material change and ran an ID rebake for a map the cage cannot affect. It
        #    repeated after every refresh_membership_index, which rebuilds the baseline
        #    without the cage in it.
        mat_changed = False
        prev_mat_hash = _material_hashes.get(obj_name)
        if prev_mat_hash is not None:
            current_mat_hash = _hash_material_slots(id_data)
            if current_mat_hash != prev_mat_hash:
                _material_hashes[obj_name] = current_mat_hash
                mat_changed = True

        if not geometry_changed and not transform_changed and not mat_changed:
            continue

        if geometry_changed:
            dirty_maps: set[str] = set(_ALL_REBAKE_MAPS)
        elif transform_changed:
            dirty_maps = set(_PROJECTION_MAPS)
        else:
            dirty_maps = set()
        if mat_changed:
            dirty_maps.add(constants.MAP_ID)

        target_group_names = set(group_names_for_obj)
        if obj_name in _high_membership_index:
            # Without match-by-isolation, a high-mesh edit can affect every
            # group projected against the global high scene, not just the
            # edited object's owning group.
            target_group_names.update(_global_high_scene_group_names)
        if (geometry_changed or transform_changed) and _world_lighting_map_types:
            # Scene lighting with Include Other Groups: this mesh shadows and bounces light
            # onto every group, lows included (Use Low as High environments).
            for group_name in _lighting_group_names:
                _mark_dirty_internal(group_name, set(_world_lighting_map_types), object_name=obj_name)
        if (geometry_changed or transform_changed) and _world_occlusion_map_types and obj_name in _high_membership_index:
            # Occlude Other Groups: this high darkens every group's AO.
            for group_name in _lighting_group_names:
                _mark_dirty_internal(group_name, set(_world_occlusion_map_types), object_name=obj_name)
        for group_name in sorted(target_group_names):
            _mark_dirty_internal(group_name, dirty_maps, object_name=obj_name)


def _mark_dirty_internal(group_name: str, map_types: set[str], *, object_name: str = "") -> None:
    global _last_dirty_time
    if group_name not in _dirty_groups:
        _dirty_groups[group_name] = set()
    _dirty_groups[group_name].update(map_types)
    clean_object_name = str(object_name or "").strip()
    if clean_object_name:
        _dirty_group_objects.setdefault(group_name, set()).add(clean_object_name)
    _last_dirty_time = time.monotonic()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mark_dirty(group_name: str, map_types: set[str]) -> None:
    """Manually mark specific map types for a group as needing rebake."""
    if not group_name or not map_types:
        return
    _mark_dirty_internal(group_name, map_types)


def mark_all_dirty(project) -> None:
    """Mark every group and every known map type as dirty (forces full incremental bake)."""
    for group in getattr(project, "groups", []):
        gname = str(getattr(group, "name", "") or "").strip()
        if gname:
            _mark_dirty_internal(gname, set(_ALL_REBAKE_MAPS))


def clear_dirty(group_name: str, map_types: set[str]) -> None:
    """Clear specific (group, map_type) entries after a successful partial bake."""
    bucket = _dirty_groups.get(group_name)
    if bucket is None:
        return
    for map_type in map_types:
        bucket.discard(map_type)
    if not bucket:
        del _dirty_groups[group_name]
        _dirty_group_objects.pop(group_name, None)


def clear_all_dirty() -> None:
    _dirty_groups.clear()
    _dirty_group_objects.clear()


def get_pending_dirty() -> DirtyMatrix:
    """Return a snapshot of the current dirty matrix (copy; safe to hold across frames).

    Expands dirty state to texture-set siblings: if any group in a shared
    texture set is dirty, all siblings are included with the same map types
    (the backend composites them into a single output so all must be re-baked).
    """
    snapshot: DirtyMatrix = {group_name: set(map_types) for group_name, map_types in _dirty_groups.items() if map_types}
    if _texture_set_siblings:
        expanded: DirtyMatrix = {}
        for group_name, map_types in snapshot.items():
            siblings = _texture_set_siblings.get(group_name)
            if siblings:
                for sibling in siblings:
                    if sibling in expanded:
                        expanded[sibling].update(map_types)
                    else:
                        expanded[sibling] = set(map_types)
        for sibling, map_types in expanded.items():
            if sibling in snapshot:
                snapshot[sibling].update(map_types)
            else:
                snapshot[sibling] = map_types
    return snapshot


def get_pending_dirty_objects() -> dict[str, set[str]]:
    """Return direct group_name -> object names that caused the current dirty state.

    Texture-set sibling expansion happens in get_pending_dirty(). Expanded
    siblings intentionally do not inherit the source group's dirty object
    names; groups without explicit dirty low-mesh names run a full selected
    group/map bake instead of a dirty-UV-rect update.
    """
    return {
        group_name: set(object_names)
        for group_name, object_names in _dirty_group_objects.items()
        if _dirty_groups.get(group_name)
    }


def has_pending_dirty() -> bool:
    return any(_dirty_groups.values())


def time_since_last_dirty() -> float:
    """Seconds since the last dirty event. Returns inf if nothing is dirty yet."""
    if _last_dirty_time == 0.0:
        return float("inf")
    return time.monotonic() - _last_dirty_time


def debounce_elapsed() -> bool:
    """True when enough quiet time has passed after the last dirty event."""
    return time_since_last_dirty() >= _debounce_seconds


def is_session_active() -> bool:
    return _session_active


def refresh_membership_index(project) -> None:
    """Call after group membership changes (add/remove objects) without restarting the session."""
    global _membership_index, _high_membership_index, _global_high_scene_group_names, _material_hashes, _texture_set_siblings, _cage_only_names
    if not _session_active:
        return
    _membership_index = _build_membership_index(project)
    _high_membership_index = _build_high_membership_index(project)
    _cage_only_names = _build_cage_only_names(project)
    _global_high_scene_group_names = _build_global_high_scene_group_names(project)
    _material_hashes = _build_material_hashes(project)
    _texture_set_siblings = _build_texture_set_siblings(project)
    _geometry_fingerprints.update(_build_geometry_fingerprints(project))
    _refresh_lighting_state(project)


def _build_cage_only_names(project) -> set[str]:
    """Custom cages that are not also a low or high somewhere.

    Their UVs never reach a bake, so the fingerprint skips the UV digest for them --
    and the baseline below and the handler have to agree on that, or every cage
    fingerprint would mismatch on its first comparison for the wrong reason.
    """
    cages: set[str] = set()
    meshes: set[str] = set()
    for group in getattr(project, "groups", []):
        for slot_collection in (
            getattr(group, "low_meshes", []),
            properties.effective_high_mesh_slots(group),
        ):
            for slot in slot_collection:
                obj = getattr(slot, "object_ref", None)
                if obj is not None:
                    meshes.add(str(getattr(obj, "name", "") or "").strip())
        cage_obj = getattr(group, "custom_cage", None)
        if cage_obj is not None:
            cages.add(str(getattr(cage_obj, "name", "") or "").strip())
    cages.discard("")
    return cages - meshes


def _high_is_parked(obj) -> bool:
    try:
        from . import high_poly_park

        return high_poly_park.is_object_parked(obj)
    except Exception:
        return False


def _build_geometry_fingerprints(project) -> dict[str, tuple]:
    fingerprints: dict[str, tuple] = {}
    cage_only = _build_cage_only_names(project)
    for group in getattr(project, "groups", []):
        for slot_collection, is_low in (
            (getattr(group, "low_meshes", []), True),
            (properties.effective_high_mesh_slots(group), False),
        ):
            for slot in slot_collection:
                obj = getattr(slot, "object_ref", None)
                if obj is None:
                    continue
                obj_name = str(getattr(obj, "name", "") or "").strip()
                if not is_low and _high_is_parked(obj):
                    # An empty placeholder until its slice of the restore runs: keep the
                    # baseline taken from the real mesh instead of fingerprinting nothing.
                    continue
                if obj_name and obj_name not in fingerprints:
                    try:
                        fingerprints[obj_name] = _geometry_fingerprint(obj, include_uvs=is_low)
                    except Exception:
                        pass
        # The custom cage is registered in the membership index as bake input (it is
        # geometry the projection rays start from) but was never given a baseline here.
        # With no baseline the handler's `prev_fp is not None` guard swallows the FIRST
        # cage edit of a session: push the cage verts out to fix a skew artifact, tab
        # back to object mode, and the live session keeps serving the pre-edit maps. The
        # second edit works, and toggling Live Bake off/on re-arms the miss.
        cage_obj = getattr(group, "custom_cage", None)
        if cage_obj is None:
            continue
        cage_name = str(getattr(cage_obj, "name", "") or "").strip()
        if cage_name and cage_name not in fingerprints:
            try:
                fingerprints[cage_name] = _geometry_fingerprint(
                    cage_obj, include_uvs=cage_name not in cage_only
                )
            except Exception:
                pass
    return fingerprints


def start_session(project, *, debounce: float = 0.3) -> None:
    """
    Start tracking depsgraph changes for the given project.
    Safe to call again if already active; refreshes index without clearing dirty state.
    """
    global _session_active, _debounce_seconds, _membership_index, _high_membership_index, _global_high_scene_group_names, _material_hashes, _texture_set_siblings, _cage_only_names
    _debounce_seconds = max(0.05, float(debounce))
    _membership_index = _build_membership_index(project)
    _high_membership_index = _build_high_membership_index(project)
    _cage_only_names = _build_cage_only_names(project)
    _global_high_scene_group_names = _build_global_high_scene_group_names(project)
    _material_hashes = _build_material_hashes(project)
    _texture_set_siblings = _build_texture_set_siblings(project)
    _geometry_fingerprints.update(_build_geometry_fingerprints(project))
    _refresh_lighting_state(project)
    clear_all_dirty()
    _session_active = True
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is None:
        return
    post = getattr(handlers, "depsgraph_update_post", None)
    if post is None:
        return
    if _on_depsgraph_update not in post:
        post.append(_on_depsgraph_update)


def stop_session() -> None:
    """Stop tracking and discard all dirty state."""
    global _session_active, _cooldown_until, _lighting_signature, _lighting_map_types, _lighting_group_names
    _session_active = False
    _cooldown_until = 0.0
    _geometry_fingerprints.clear()
    _material_hashes.clear()
    _cage_only_names.clear()
    _lighting_signature = ""
    _lighting_map_types = []
    _lighting_group_names = []
    handlers = getattr(getattr(bpy, "app", None), "handlers", None)
    if handlers is not None:
        post = getattr(handlers, "depsgraph_update_post", None)
        if post is not None:
            try:
                post.remove(_on_depsgraph_update)
            except (ValueError, AttributeError):
                pass
    clear_all_dirty()
