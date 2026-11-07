"""Analysis + UV-generation layer for the "Bake Selected Materials" workflow.

This workflow flattens a low-poly object's own materials into PBR texture sets
(one set per object in V1). There is no high-poly projection: every channel is a
property of the object's assigned materials, read directly from the Principled
BSDF (or a linked Image Texture, resolved elsewhere via ``export`` helpers).

The module is deliberately read-only for the analysis half -- ``analyze_selection``
never mutates the scene. Only ``generate_smart_uvs`` writes, and it does so
transactionally (full rollback + state restore on every exit path).

Signature notes for the reused helpers (verified against the current source):
  * ``export._material_surface_shader(node_tree)`` -> node | None. Walks the active
    Material Output ``Surface`` link; falls back to a lone Principled/Emission node;
    returns None for an untraceable graph (output present but Surface unlinked).
  * ``export._shader_vec3_input(node, socket_name)`` -> (rgb list | None, is_linked).
  * ``export._shader_scalar_input(node, socket_name, default=1.0)`` -> (float, is_linked).
  * ``export.resolve_material_fast_path(obj, channel, workspace_path=None)`` -> abs
    path str | None (direct Image Texture -> Principled, file-backed, on every slot).
  * ``validation._object_uv_layers(obj_or_mesh)`` -> uv_layers collection | None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from . import constants, export, validation


# --- Principled BSDF socket names (Blender 4.x) -----------------------------

_PRINCIPLED_NODE_TYPE = "BSDF_PRINCIPLED"
_EMISSION_NODE_TYPE = "EMISSION"
_NORMAL_MAP_NODE_TYPE = "NORMAL_MAP"
_BUMP_NODE_TYPE = "BUMP"

# Material-space normal channel key. Distinct from the MATERIAL_CHANNEL_* PBR
# scalars/colors: it carries constants.MAP_NORMAL, not MAP_MATERIAL.
_NORMAL_CHANNEL = "NORMAL"

# Scalar Principled channels: channel -> (socket name, factory default value).
# Factory defaults per the Blender 4.x Principled BSDF.
_SCALAR_CHANNELS: tuple[tuple[str, str, float], ...] = (
    (constants.MATERIAL_CHANNEL_ROUGHNESS, "Roughness", 0.5),
    (constants.MATERIAL_CHANNEL_METALNESS, "Metallic", 0.0),
    (constants.MATERIAL_CHANNEL_OPACITY, "Alpha", 1.0),
    (constants.MATERIAL_CHANNEL_SPECULAR, "Specular IOR Level", 0.5),
    (constants.MATERIAL_CHANNEL_TRANSMISSION, "Transmission Weight", 0.0),
)

# Deterministic channel emission order for the review dialog.
_CHANNEL_ORDER: tuple[str, ...] = (
    constants.MATERIAL_CHANNEL_ALBEDO,
    constants.MATERIAL_CHANNEL_ROUGHNESS,
    constants.MATERIAL_CHANNEL_METALNESS,
    constants.MATERIAL_CHANNEL_EMISSION,
    constants.MATERIAL_CHANNEL_OPACITY,
    constants.MATERIAL_CHANNEL_SPECULAR,
    constants.MATERIAL_CHANNEL_TRANSMISSION,
    _NORMAL_CHANNEL,
)

_FLOAT_EPS = 1e-6
# UV bounding-box area below this is treated as degenerate (a UV layer that
# exists but collapses to a point/line carries no usable parameterization).
_UV_AREA_EPS = 1e-9


# --- Data model -------------------------------------------------------------

@dataclass
class ChannelProposal:
    channel: str        # a MATERIAL_CHANNEL_* value, or "NORMAL" for material-space normal
    map_type: str       # constants.MAP_MATERIAL for PBR channels, constants.MAP_NORMAL for normal
    proposed: bool      # True => enabled by default in the review dialog
    reason: str         # short human phrase, e.g. "linked texture", "authored 0.20", "always meaningful"
    approximate: bool = False   # True => closure/graph conversion is approximate or uncertain


@dataclass
class ObjectMaterialInfo:
    obj_name: str
    material_count: int
    has_usable_uvs: bool
    unsupported: list = field(default_factory=list)  # human-readable notes about unsupported/ambiguous branches


@dataclass
class SelectionAnalysis:
    objects: list = field(default_factory=list)              # list[ObjectMaterialInfo]
    channels: list = field(default_factory=list)             # list[ChannelProposal], deterministic order
    objects_without_uvs: list = field(default_factory=list)  # list[str] object names
    expected_texture_sets: int = 0                           # == number of eligible selected objects (V1: one set per object)
    blocking_error: str = ""                                 # non-empty => project creation must be blocked


# --- Selection / UV inspection (read-only) ----------------------------------

def _has_material(obj) -> bool:
    """True if *obj* has at least one material slot holding a material."""
    slots = getattr(obj, "material_slots", None) or ()
    for slot in slots:
        if getattr(slot, "material", None) is not None:
            return True
    return False


def selected_material_target_objects(context) -> list:
    """Visible, selected MESH objects that have at least one material slot with a material.

    Deterministic order (sorted by object name). No scene mutation.
    """
    selected = getattr(context, "selected_objects", None) or ()
    targets = []
    for obj in selected:
        if getattr(obj, "type", None) != "MESH":
            continue
        # Respect viewport visibility so hidden-but-selected objects are excluded.
        visible_get = getattr(obj, "visible_get", None)
        if callable(visible_get):
            try:
                if not bool(visible_get()):
                    continue
            except Exception:
                # A visibility query failure should not silently include the object.
                continue
        if not _has_material(obj):
            continue
        targets.append(obj)
    targets.sort(key=lambda ob: str(getattr(ob, "name", "")))
    return targets


def object_has_usable_uvs(obj) -> bool:
    """True if *obj*'s mesh has at least one UV layer with a non-degenerate UV area.

    Guards against a UV layer that exists but is collapsed to a point/line (all UVs
    equal, or a zero-area bounding box). Read-only.
    """
    if obj is None or getattr(obj, "type", None) != "MESH":
        return False
    uv_layers = validation._object_uv_layers(obj)
    if not uv_layers:
        return False
    try:
        layers = list(uv_layers)
    except TypeError:
        return False
    for layer in layers:
        data = getattr(layer, "data", None)
        if not data:
            continue
        min_u = min_v = math.inf
        max_u = max_v = -math.inf
        saw_any = False
        for element in data:
            uv = getattr(element, "uv", None)
            if uv is None:
                continue
            try:
                u = float(uv[0])
                v = float(uv[1])
            except (TypeError, ValueError, IndexError):
                continue
            saw_any = True
            if u < min_u:
                min_u = u
            if u > max_u:
                max_u = u
            if v < min_v:
                min_v = v
            if v > max_v:
                max_v = v
        if not saw_any:
            continue
        area = (max_u - min_u) * (max_v - min_v)
        if area > _UV_AREA_EPS:
            return True
    return False


# --- Material channel analysis (read-only) ----------------------------------

class _ChannelAccumulator:
    """Union state for one candidate channel across every scanned material."""

    __slots__ = ("proposed", "reason", "approximate", "_any_linked", "_sample_value")

    def __init__(self):
        self.proposed = False
        self.reason = ""
        self.approximate = False
        self._any_linked = False
        self._sample_value = None


def _surface_shader(material):
    """Return (shader_node | None, shader_type_str, is_node_material).

    is_node_material is False for legacy no-node materials (or a missing node tree),
    which cannot be read via the Principled socket helpers.

    Asset-library materials (Sanctus, etc.) and Fyr Capture wrap Principled inside
    node groups / a Capture passthrough. Resolve through those so channel detection
    can propose Roughness/Metalness/Normal exactly instead of only approximate Albedo.
    """
    if not bool(getattr(material, "use_nodes", False)):
        return None, "", False
    node_tree = getattr(material, "node_tree", None)
    if node_tree is None:
        return None, "", False
    from . import material_channel_graph

    principled, _chain = material_channel_graph.resolve_principled(material)
    if principled is not None:
        return principled, _PRINCIPLED_NODE_TYPE, True
    shader = export._material_surface_shader(node_tree)
    shader_type = str(getattr(shader, "type", "") or "") if shader is not None else ""
    return shader, shader_type, True


def _normal_source_reason(shader) -> str:
    """Classify what drives the Principled Normal input, for a friendly reason."""
    inputs = getattr(shader, "inputs", None)
    socket = inputs.get("Normal") if hasattr(inputs, "get") else None
    if socket is None or not bool(getattr(socket, "is_linked", False)):
        return ""
    links = getattr(socket, "links", None) or ()
    if links:
        from_node = getattr(links[0], "from_node", None)
        from_type = str(getattr(from_node, "type", "") or "")
        if from_type == _NORMAL_MAP_NODE_TYPE:
            return "normal map"
        if from_type == _BUMP_NODE_TYPE:
            return "bump node"
    return "linked normal"


def analyze_selection(context) -> SelectionAnalysis:
    """Analyze the active selection's visible mesh objects. Convenience wrapper that reads
    the scene selection then defers to ``analyze_objects``. Read-only."""
    return analyze_objects(selected_material_target_objects(context))


def analyze_objects(objects) -> SelectionAnalysis:
    """Analyze an explicit list of already-resolved mesh objects WITHOUT reading or
    changing the scene selection (used by both the onboarding dialog and Rescan Materials).

    Deterministic. Channel proposal rules (union across all eligible objects):
      - ALBEDO: proposed whenever a supported surface material exists ('always meaningful').
      - ROUGHNESS/METALNESS/OPACITY/SPECULAR/TRANSMISSION: proposed when the socket is
        linked, OR its authored default differs from the Principled factory default, in
        >=1 material.
      - EMISSION: proposed when Emission Color or Emission Strength is linked, OR effective
        authored emission is non-black AND strength != 0.
      - NORMAL (map_type=MAP_NORMAL): proposed when a Normal Map, Bump, or a linked Normal
        socket contributes on >=1 material.
      - A material whose surface shader is NOT a Principled BSDF is recorded in that object's
        `unsupported` notes and marked approximate on any channel it affects (ALBEDO, which is
        always bakeable via an EEVEE flatten). Unsupported branches are never treated as exact.
      - If no eligible object exists, blocking_error explains why.
    """
    result = SelectionAnalysis()

    objects = list(objects or [])
    if not objects:
        result.blocking_error = (
            "Select at least one visible mesh object that has a material to bake."
        )
        return result

    # Channel accumulators keyed by channel constant.
    accum: dict[str, _ChannelAccumulator] = {
        channel: _ChannelAccumulator() for channel in _CHANNEL_ORDER
    }

    # Whether any material anywhere presented a shader the readers understand exactly
    # (Principled or Emission). Drives the ALBEDO proposal.
    have_supported_surface = False
    # Whether any material could not be read exactly (unsupported graph / no nodes).
    have_unsupported = False
    # Track per (object, material) whether that material yielded any bakeable channel.
    objects_with_no_channel: list[str] = []

    for obj in objects:
        info = ObjectMaterialInfo(
            obj_name=str(getattr(obj, "name", "")),
            material_count=0,
            has_usable_uvs=object_has_usable_uvs(obj),
        )
        if not info.has_usable_uvs:
            result.objects_without_uvs.append(info.obj_name)

        object_has_bakeable = False

        slots = getattr(obj, "material_slots", None) or ()
        for slot in slots:
            material = getattr(slot, "material", None)
            if material is None:
                continue
            info.material_count += 1
            mat_name = str(getattr(material, "name", "") or "material")

            shader, shader_type, is_node_material = _surface_shader(material)

            if shader_type == _PRINCIPLED_NODE_TYPE:
                have_supported_surface = True
                object_has_bakeable = True
                _scan_principled(shader, accum)
            elif shader_type == _EMISSION_NODE_TYPE:
                have_supported_surface = True
                object_has_bakeable = True
                _scan_emission_node(shader, accum)
            else:
                # Non-Principled node graph (Mix/Add shader, other closure, untraceable),
                # or a legacy material with no nodes. Albedo is still bakeable via an EEVEE
                # flatten, but the static readers cannot resolve the individual channels --
                # so mark it approximate and record a note. Never silent.
                have_unsupported = True
                object_has_bakeable = True  # albedo flatten still works
                if not is_node_material:
                    detail = "material has no shader nodes"
                elif shader is None:
                    detail = "surface shader could not be traced"
                else:
                    detail = f"surface is '{shader_type}', not Principled BSDF"
                info.unsupported.append(f"{mat_name}: {detail}; channels are approximate")
                # The albedo channel is the one guaranteed to bake; flag it uncertain.
                accum[constants.MATERIAL_CHANNEL_ALBEDO].approximate = True

        if not object_has_bakeable:
            objects_with_no_channel.append(info.obj_name)

        result.objects.append(info)

    result.expected_texture_sets = len(objects)

    # ALBEDO: always meaningful when any bakeable surface exists.
    albedo = accum[constants.MATERIAL_CHANNEL_ALBEDO]
    if have_supported_surface or have_unsupported:
        albedo.proposed = True
        albedo.reason = "always meaningful"
    if have_unsupported and not have_supported_surface:
        albedo.approximate = True

    # Finalize reasons for accumulators that were left at defaults.
    _finalize_reasons(accum)

    # Build the deterministic channel list.
    result.channels = _build_channels(accum)

    # Blocking: every eligible object failed to yield any channel (degenerate).
    if objects_with_no_channel and len(objects_with_no_channel) == len(objects):
        offenders = ", ".join(objects_with_no_channel)
        result.blocking_error = (
            f"No material channel can be baked for the selected object(s): {offenders}."
        )
    elif not result.channels:
        # Defensive: eligible objects but nothing proposable at all.
        result.blocking_error = (
            "The selected materials expose no bakeable channels."
        )

    return result


def _scan_principled(shader, accum: dict[str, _ChannelAccumulator]) -> None:
    """Fold one Principled BSDF's exact reads into the channel accumulators."""
    # Scalar channels: linked, or authored value differs from factory default.
    for channel, socket_name, default in _SCALAR_CHANNELS:
        value, linked = export._shader_scalar_input(shader, socket_name, default)
        state = accum[channel]
        if linked:
            state.proposed = True
            state._any_linked = True
        elif abs(float(value) - float(default)) > _FLOAT_EPS:
            state.proposed = True
            if state._sample_value is None:
                state._sample_value = float(value)

    # Emission: linked color/strength, or non-black effective emission with strength != 0.
    emit_color, color_linked = export._shader_vec3_input(shader, "Emission Color")
    emit_strength, strength_linked = export._shader_scalar_input(shader, "Emission Strength", 1.0)
    _fold_emission(accum, emit_color, color_linked, emit_strength, strength_linked)

    # Normal: a linked Normal socket (Normal Map / Bump / other) contributes.
    reason = _normal_source_reason(shader)
    if reason:
        normal = accum[_NORMAL_CHANNEL]
        normal.proposed = True
        if not normal.reason:
            normal.reason = reason


def _scan_emission_node(shader, accum: dict[str, _ChannelAccumulator]) -> None:
    """Fold a pure Emission shader node (Color * Strength) into the accumulators."""
    emit_color, color_linked = export._shader_vec3_input(shader, "Color")
    emit_strength, strength_linked = export._shader_scalar_input(shader, "Strength", 1.0)
    _fold_emission(accum, emit_color, color_linked, emit_strength, strength_linked)


def _fold_emission(accum, emit_color, color_linked, emit_strength, strength_linked) -> None:
    state = accum[constants.MATERIAL_CHANNEL_EMISSION]
    non_black = bool(emit_color) and any(abs(float(c)) > _FLOAT_EPS for c in emit_color)
    strength_nonzero = abs(float(emit_strength)) > _FLOAT_EPS
    if color_linked or strength_linked:
        state.proposed = True
        state._any_linked = True
    elif non_black and strength_nonzero:
        state.proposed = True


def _finalize_reasons(accum: dict[str, _ChannelAccumulator]) -> None:
    """Assign human reasons to proposed scalar/emission channels lacking one."""
    for channel, _socket_name, _default in _SCALAR_CHANNELS:
        state = accum[channel]
        if not state.reason:
            if state._any_linked:
                state.reason = "linked texture"
            elif state.proposed and state._sample_value is not None:
                state.reason = f"authored {state._sample_value:.2f}"
            elif state.proposed:
                state.reason = "authored value"
            else:
                state.reason = "factory default"

    emission = accum[constants.MATERIAL_CHANNEL_EMISSION]
    if not emission.reason:
        if emission._any_linked:
            emission.reason = "linked texture"
        elif emission.proposed:
            emission.reason = "authored emission"
        else:
            emission.reason = "no emission"

    normal = accum[_NORMAL_CHANNEL]
    if not normal.reason:
        normal.reason = "no normal input"

    albedo = accum[constants.MATERIAL_CHANNEL_ALBEDO]
    if not albedo.reason:
        albedo.reason = "always meaningful" if albedo.proposed else "no surface"


def _build_channels(accum: dict[str, _ChannelAccumulator]) -> list:
    """Materialize accumulators into ordered ChannelProposal objects."""
    channels = []
    for channel in _CHANNEL_ORDER:
        state = accum[channel]
        if channel == _NORMAL_CHANNEL:
            map_type = constants.MAP_NORMAL
        else:
            map_type = constants.MAP_MATERIAL
        channels.append(
            ChannelProposal(
                channel=channel,
                map_type=map_type,
                proposed=bool(state.proposed),
                reason=str(state.reason),
                approximate=bool(state.approximate),
            )
        )
    return channels


# --- Smart-UV generation (transactional, restores all state) ----------------

def _find_view3d_area_region(context):
    """Return (area, region) for the first VIEW_3D area, or (None, None).

    Local copy to avoid importing operators.py (owned by another writer / circular).
    """
    screen = getattr(context, "screen", None)
    areas = getattr(screen, "areas", None) or ()
    for area in areas:
        if getattr(area, "type", None) != "VIEW_3D":
            continue
        for region in getattr(area, "regions", None) or ():
            if getattr(region, "type", None) == "WINDOW":
                return area, region
    return None, None


def generate_smart_uvs(objects, layer_name: str = "FyrMaterialBake") -> tuple:
    """(ok: bool, message: str). Create smart-projected UVs for objects lacking usable UVs.

    For each object in *objects* that lacks usable UVs, create a NEW UV layer named
    *layer_name* (existing layers are never touched) and run ``bpy.ops.uv.smart_project``
    with production-safe defaults. Selection, active object, per-mesh active UV layer,
    and Object/Edit mode are preserved and restored on every exit path.

    TRANSACTIONAL: if any object fails, every UV layer this call created is removed
    (rollback) and (False, reason) is returned leaving no partial state.
    """
    import bpy

    if not objects:
        return True, "No objects required UV generation."

    context = bpy.context
    view3d_area, view3d_region = _find_view3d_area_region(context)
    if view3d_area is None:
        return False, "Smart UV projection requires an open 3D Viewport."

    view_layer = context.view_layer

    # --- Capture state to restore on every exit path -----------------------
    prev_selected = [ob for ob in view_layer.objects if ob.select_get()]
    prev_active = view_layer.objects.active
    prev_active_mode = str(getattr(prev_active, "mode", "OBJECT") or "OBJECT") if prev_active else "OBJECT"

    # Track UV layers we create for rollback, and prior active-UV-layer per mesh.
    created: list[tuple] = []          # (mesh, layer_name)
    prev_active_uv: dict[int, str] = {}  # id(mesh) -> previous active uv layer name ("" if none)
    prev_active_render: dict[int, str] = {}  # id(mesh) -> previous render uv layer name ("" if none)

    def _restore_selection_and_mode():
        # Best-effort return to Object mode before touching selection/active.
        try:
            if getattr(view_layer.objects, "active", None) is not None and view_layer.objects.active.mode != "OBJECT":
                with context.temp_override(area=view3d_area, region=view3d_region):
                    bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
        try:
            for ob in view_layer.objects:
                ob.select_set(ob in prev_selected)
        except Exception:
            pass
        try:
            view_layer.objects.active = prev_active
        except Exception:
            pass
        # Restore the original active object's mode, if it was not Object mode.
        if prev_active is not None and prev_active_mode != "OBJECT":
            try:
                with context.temp_override(area=view3d_area, region=view3d_region):
                    bpy.ops.object.mode_set(mode=prev_active_mode)
            except Exception:
                pass

    def _rollback():
        for mesh, name in reversed(created):
            try:
                layer = mesh.uv_layers.get(name)
                if layer is not None:
                    mesh.uv_layers.remove(layer)
            except Exception:
                pass
            # Restore the mesh's previously active UV layer, if we changed it.
            prior = prev_active_uv.get(id(mesh))
            if prior:
                try:
                    restore_layer = mesh.uv_layers.get(prior)
                    if restore_layer is not None:
                        mesh.uv_layers.active = restore_layer
                except Exception:
                    pass
            # The new layer was also made the render layer; put the previous one back
            # or the mesh renders/bakes from whichever layer Blender falls back to.
            prior_render = prev_active_render.get(id(mesh))
            if prior_render:
                try:
                    render_layer = mesh.uv_layers.get(prior_render)
                    if render_layer is not None:
                        render_layer.active_render = True
                except Exception:
                    pass

    processed = 0
    try:
        # Start from a clean Object mode so mode transitions are predictable.
        try:
            if prev_active is not None and prev_active.mode != "OBJECT":
                with context.temp_override(area=view3d_area, region=view3d_region):
                    bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass

        for obj in objects:
            if getattr(obj, "type", None) != "MESH":
                continue
            mesh = getattr(obj, "data", None)
            if mesh is None or not hasattr(mesh, "uv_layers"):
                # Guard: object carries no mesh data. Skip rather than fail the batch.
                continue
            if object_has_usable_uvs(obj):
                # Already parameterized: leave existing layers untouched.
                continue

            # Isolate this object for the operator context.
            for ob in view_layer.objects:
                ob.select_set(False)
            obj.select_set(True)
            view_layer.objects.active = obj

            # Remember the mesh's active UV layer so rollback can restore it.
            existing_active = getattr(mesh.uv_layers, "active", None)
            prev_active_uv[id(mesh)] = str(getattr(existing_active, "name", "") or "")
            prev_active_render[id(mesh)] = next(
                (str(layer.name) for layer in mesh.uv_layers if getattr(layer, "active_render", False)),
                "",
            )

            # Create a fresh layer (never mutate existing ones) and make it active
            # so smart_project writes into it.
            new_layer = mesh.uv_layers.new(name=layer_name, do_init=False)
            if new_layer is None:
                raise RuntimeError(f"Could not create UV layer on '{obj.name}'.")
            created.append((mesh, new_layer.name))
            mesh.uv_layers.active = new_layer

            # Edit mode + select-all + smart project, then back to Object mode.
            with context.temp_override(area=view3d_area, region=view3d_region, active_object=obj, object=obj, selected_objects=[obj], selected_editable_objects=[obj]):
                bpy.ops.object.mode_set(mode="EDIT")
                try:
                    bpy.ops.mesh.select_all(action="SELECT")
                    bpy.ops.uv.smart_project(
                        angle_limit=math.radians(66.0),
                        island_margin=0.02,
                        correct_aspect=True,
                        scale_to_bounds=False,
                    )
                finally:
                    bpy.ops.object.mode_set(mode="OBJECT")

            # Prefer the freshly projected layer for rendering/baking.
            try:
                new_layer.active_render = True
            except Exception:
                pass
            processed += 1

    except Exception as exc:
        _rollback()
        _restore_selection_and_mode()
        return False, f"Smart UV projection failed: {exc}"

    _restore_selection_and_mode()

    if processed == 0:
        return True, "No objects required UV generation."
    return True, f"Generated smart UVs for {processed} object(s)."
