"""Detect material rows that consume this project's own baked mesh maps.

Substance Painter lets a material graph read the project's own curvature / AO /
thickness bakes (curvature-driven masks, dirt in cavities, ...). Fyr Baker's bake
pipeline snapshots every material texel payload at *export* time
(``export._collect_material_ir_source`` -> ``_normalize_material_image_to_png``,
``export.resolve_material_fast_path``), which happens before a single mesh map has
been written. A material that reads ``Asset_Curvature.png`` therefore bakes against
whatever was on disk from the *previous* run -- same-click freshness is impossible.

This module finds those references so the bake operator can split the run into two
phases (mesh maps -> reload -> materials). Detection is deliberately conservative in
one direction only: a material row is marked dependent when its channel graph reaches
an Image Texture whose file is an output **this run is about to write**. A reference to
a mesh map that exists on disk but is not part of the run needs no split -- that file
is already current.

The module is import-safe without Blender data: every collaborator is resolved lazily
and every path is compared as a normalized string, so the planner is unit-testable
against fake node graphs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

import bpy

from . import constants, naming, properties


# Principled BSDF input socket per material channel. ``export._MATERIAL_CHANNEL_TO_SOCKET``
# covers the emitting channels; Normal is added here because a Normal-channel row reaches
# the graph through the same socket even though it never becomes an EMIT bake.
_CHANNEL_TO_SOCKET: dict[str, str] = {
    constants.MATERIAL_CHANNEL_ALBEDO: "Base Color",
    constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
    constants.MATERIAL_CHANNEL_METALNESS: "Metallic",
    constants.MATERIAL_CHANNEL_EMISSION: "Emission Color",
    constants.MATERIAL_CHANNEL_OPACITY: "Alpha",
    constants.MATERIAL_CHANNEL_SPECULAR: "Specular IOR Level",
    constants.MATERIAL_CHANNEL_TRANSMISSION: "Transmission Weight",
    constants.MATERIAL_CHANNEL_NORMAL: "Normal",
}

# Node-group nesting plus shader chain depth. Blender caps group nesting far below this;
# the bound only exists so a malformed/cyclic tree cannot spin the walk forever.
_MAX_WALK_DEPTH = 64

# Tile placeholders a UDIM-aware filepath can carry in place of a concrete ``.1001``.
_UDIM_TOKENS = ("<UDIM>", "<UVTILE>", "<udim>", "<uvtile>")

# Shader nodes that compile to a Material IR secondary-ray opcode
# (material_ir.GPU_RAY_OPCODES: AO / BEVEL / RAYCAST). Both spellings are matched for the
# same reason material_ir's compiler matches both: newer nodes report their bl_idname
# through ``type``. This is a STATIC node-presence test, not a compile — a node that would
# have routed to Cycles anyway is harmless here, phase 2 simply bakes it via Cycles as it
# always did.
_RAY_NODE_TYPES = frozenset({"AMBIENT_OCCLUSION", "BEVEL", "RAYCAST"})
_RAY_NODE_IDNAMES = frozenset(
    {"ShaderNodeAmbientOcclusion", "ShaderNodeBevel", "ShaderNodeRaycast"}
)


@dataclass(slots=True)
class OutputProducer:
    """One bake output this run will write, as a match target for material images."""

    map_uuid: str
    label: str
    group_name: str
    is_material_row: bool
    path: str


@dataclass(slots=True)
class MaterialDependency:
    """A material row reading an output produced by this same run."""

    map_uuid: str
    label: str
    material_name: str
    node_name: str
    image_name: str
    producer: OutputProducer

    def describe(self) -> str:
        return (
            f"'{self.label}' reads '{self.image_name}' "
            f"(node '{self.node_name}' in material '{self.material_name}')"
        )


@dataclass(slots=True)
class RayOpUsage:
    """A material row whose channel graph contains a secondary-ray shader node.

    Such a row can only compile its ray opcodes natively when the backend picks the
    MATERIAL_ONLY shading permutation, which ``export._job_is_material_only_backend_batch``
    can only vouch for on an all-material job. Mixed mesh+material runs therefore refuse
    the row to Cycles at export time. Moving it to phase 2 -- which is all-material by
    construction -- makes the existing proof pass and the ray ops run native.
    """

    map_uuid: str
    label: str
    material_name: str
    node_name: str
    node_type: str

    def describe(self) -> str:
        return (
            f"'{self.label}' uses secondary-ray node '{self.node_name}' ({self.node_type}) "
            f"in material '{self.material_name}'"
        )


@dataclass(slots=True)
class BakePhasePlan:
    """Result of :func:`plan_bake_phases`.

    ``deferred_map_uuids`` empty means "run exactly like today" -- the caller must not
    change a single thing about the dispatch in that case. A row lands in phase 2 for
    either of two independent reasons (it reads this run's own mesh maps, or it carries
    secondary-ray nodes that only compile on an all-material job); a row with both
    reasons is still a single membership.
    """

    first_phase_map_uuids: list[str] = field(default_factory=list)
    deferred_map_uuids: list[str] = field(default_factory=list)
    deferred_row_labels: list[str] = field(default_factory=list)
    dependencies: list[MaterialDependency] = field(default_factory=list)
    ray_usages: list[RayOpUsage] = field(default_factory=list)
    reload_path_keys: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # Material-detail normals for the secondary-ray maps. When a tangent Normal row on
    # Material Detail = Auto has real high-material normal detail AND this run bakes a
    # map that shades from the surface normal (AO, Cavity, Curvature, Bent Normal ...),
    # that Normal row bakes FIRST, on its own: alone it is an all-material job, so a
    # Bevel in the graph runs natively, and the worker retains its resolved texels. The
    # mesh maps then bake with the row named as their normal source and the shading
    # kernel decodes the retained texels through the low's tangent frame, so a bevel
    # shader bands the curvature and tilts the AO hemisphere exactly like the Normal
    # map the artist ships. Empty uuid = no such ordering.
    normal_first_map_uuid: str = ""
    normal_first_flip_green: bool = False
    normal_first_label: str = ""
    # The Normal row going first was NOT part of this run's selection (the artist baked
    # Curvature or Object Normal alone): it bakes only as the source, its file goes to
    # the job workspace and never replaces the artist's Normal output.
    normal_first_source_only: bool = False

    @property
    def is_split(self) -> bool:
        return bool(self.deferred_map_uuids) and not self.errors

    @property
    def mesh_phase_map_uuids(self) -> list[str]:
        """Phase-1 rows once the Normal row has gone first (empty when it has not)."""
        if not self.normal_first_map_uuid:
            return []
        return [
            map_uuid
            for map_uuid in self.first_phase_map_uuids
            if map_uuid != self.normal_first_map_uuid
        ]

    def material_normal_source(self) -> dict | None:
        """What export.prepare_bake_job needs to name the retained Normal row."""
        if not self.normal_first_map_uuid:
            return None
        return {
            "map_uuid": self.normal_first_map_uuid,
            "flip_green": bool(self.normal_first_flip_green),
        }

    @property
    def normal_first_source_only_uuids(self) -> list[str]:
        """Rows stage 1 bakes as a source only (export.prepare_bake_job source_only_map_uuids)."""
        if self.normal_first_map_uuid and self.normal_first_source_only:
            return [self.normal_first_map_uuid]
        return []

    def deferred_labels(self) -> list[str]:
        return list(self.deferred_row_labels)

    def deferred_reason_label(self) -> str:
        """Word for the status line: what put these rows in phase 2."""
        has_dependency = bool(self.dependencies)
        has_ray = bool(self.ray_usages)
        if has_dependency and has_ray:
            return "dependent/ray"
        if has_ray:
            return "ray"
        return "dependent"


# ---------------------------------------------------------------------------
# Path normalization
# ---------------------------------------------------------------------------


def _strip_tile_token(stem: str) -> str:
    """Drop a trailing UDIM tile segment so ``Asset_Curvature.1001`` matches ``Asset_Curvature``."""
    for token in _UDIM_TOKENS:
        if stem.endswith(f".{token}"):
            return stem[: -(len(token) + 1)]
    base, _tile = naming.split_udim_tile_suffix(stem)
    return base


def normalize_path_key(path: str | Path | None) -> str:
    """Canonical comparison key for an output/image path.

    Case- and separator-insensitive (Windows), and tile-insensitive so a UDIM set
    matches the untiled name the output planner produces.
    """
    text = str(path or "").strip()
    if not text:
        return ""
    for token in _UDIM_TOKENS:
        text = text.replace(token, "<UDIM>")
    try:
        text = os.path.normpath(os.path.abspath(text))
    except (OSError, ValueError):
        text = os.path.normpath(text)
    directory, name = os.path.split(text)
    stem, extension = os.path.splitext(name)
    stem = _strip_tile_token(stem)
    return os.path.normcase(os.path.join(directory, f"{stem}{extension}"))


def image_path_key(image) -> str:
    """Normalized on-disk path an image datablock points at, packed images included.

    A packed image keeps its ``filepath``, so a pack of a previous bake output still
    resolves here -- that is the reference we must know about even though we cannot
    refresh its pixels from disk.
    """
    if image is None:
        return ""
    filepath = str(getattr(image, "filepath", "") or "")
    if not filepath:
        return ""
    library = getattr(image, "library", None)
    resolved = filepath
    try:
        resolved = bpy.path.abspath(filepath, library=library)
    except TypeError:
        try:
            resolved = bpy.path.abspath(filepath)
        except Exception:
            resolved = filepath
    except Exception:
        resolved = filepath
    return normalize_path_key(resolved)


# ---------------------------------------------------------------------------
# Output-path planning (mirrors export._build_output_targets)
# ---------------------------------------------------------------------------


def _row_label(project, map_setting) -> str:
    from . import export

    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    if map_type == constants.MAP_MATERIAL:
        origin = str(getattr(map_setting, "material_origin", "") or "")
        if origin == constants.MATERIAL_ORIGIN_CUSTOM:
            custom = str(getattr(map_setting, "material_custom_name", "") or "").strip()
            return f"Material Custom '{custom}'" if custom else "Material Custom"
        channel = str(
            getattr(map_setting, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or ""
        ).strip().upper()
        return f"Material {channel.title()}" if channel else "Material"
    try:
        return str(export.effective_map_type_for_setting(map_setting) or map_type)
    except Exception:
        return map_type


def planned_output_producers(
    project,
    map_settings,
    selected_group_names,
    *,
    output_dir=None,
) -> dict[str, OutputProducer]:
    """Output path -> producer, for every (group x map row) this run will write.

    Reuses the exact naming pipeline the bake writes with -- ``export.resolved_project_output_dir``
    (the canonical "where a bake actually lands" helper) plus ``naming.build_output_file_name``,
    the same pair ``export._build_output_targets`` uses -- so a match here means the file the
    material reads really is a file this run overwrites. UDIM tiles are collapsed by
    :func:`normalize_path_key` instead of being enumerated, which keeps the planner free of
    a depsgraph.
    """
    from . import export

    if output_dir is None:
        output_dir = export.resolved_project_output_dir(project)
    output_dir = Path(output_dir)

    bit_depth = str(
        getattr(project, "bit_depth", constants.BIT_DEPTH_8) or constants.BIT_DEPTH_8
    )
    image_format = str(
        getattr(project, "image_format", constants.DEFAULT_IMAGE_FORMAT)
        or constants.DEFAULT_IMAGE_FORMAT
    )

    producers: dict[str, OutputProducer] = {}
    groups = list(getattr(project, "groups", None) or ())
    for group in groups:
        group_name = str(getattr(group, "name", "") or "")
        if selected_group_names is not None and group_name not in selected_group_names:
            continue
        metadata_state = properties.group_metadata_state(group)
        set_key = (getattr(metadata_state, "texture_set_name", "") or "").strip()
        texture_set_name = (
            properties.resolve_texture_set_output_name(project, set_key) if set_key else None
        )
        for map_setting in map_settings:
            map_uuid = properties.ensure_map_setting_uuid(map_setting)
            effective_map_type = export.effective_map_type_for_setting(map_setting)
            map_label_override = properties.effective_map_output_suffix(project, map_setting)
            file_name = naming.build_output_file_name(
                group_name=group_name,
                map_type=effective_map_type,
                bit_depth=bit_depth,
                image_format=image_format,
                texture_set_name=texture_set_name,
                udim_tile=None,
                map_label_override=map_label_override,
                project_name=str(getattr(project, "name", "") or ""),
            )
            key = normalize_path_key(output_dir / file_name)
            if not key or key in producers:
                continue
            producers[key] = OutputProducer(
                map_uuid=map_uuid,
                label=_row_label(project, map_setting),
                group_name=group_name,
                is_material_row=str(getattr(map_setting, "map_type", "") or "").strip().upper()
                == constants.MAP_MATERIAL,
                path=str(output_dir / file_name),
            )
    return producers


# ---------------------------------------------------------------------------
# Node-graph walk
# ---------------------------------------------------------------------------


def _group_output_node(tree):
    fallback = None
    for node in getattr(tree, "nodes", None) or ():
        if str(getattr(node, "type", "") or "") != "GROUP_OUTPUT":
            continue
        if getattr(node, "is_active_output", False):
            return node
        if fallback is None:
            fallback = node
    return fallback


def _named_socket(collection, name: str):
    """Socket lookup that works on a bpy collection and on a plain test list alike."""
    if collection is None or not name:
        return None
    getter = getattr(collection, "get", None)
    if callable(getter):
        try:
            found = getter(name)
        except Exception:
            found = None
        if found is not None:
            return found
    try:
        candidates = list(collection)
    except TypeError:
        return None
    for candidate in candidates:
        if str(getattr(candidate, "name", "") or "") == name:
            return candidate
    return None


def _socket_by_name(collection, socket):
    return _named_socket(collection, str(getattr(socket, "name", "") or ""))


def _socket_by_index(source_collection, socket, target_collection):
    items = list(source_collection or ())
    index = -1
    # `is` never matches here: Blender hands out a temporary wrapper per socket
    # access, so even inputs[0] is inputs[0] is False and this fallback always
    # reported "not found". Match on the RNA pointer, as the rest of this walk does.
    target_identity = _rna_identity(socket)
    for position, candidate in enumerate(items):
        if _rna_identity(candidate) == target_identity:
            index = position
            break
    targets = list(target_collection or ())
    if 0 <= index < len(targets):
        return targets[index]
    return None


def is_ray_node(node) -> bool:
    """Whether *node* compiles to a Material IR secondary-ray opcode."""
    if node is None:
        return False
    if str(getattr(node, "type", "") or "") in _RAY_NODE_TYPES:
        return True
    return str(getattr(node, "bl_idname", "") or "") in _RAY_NODE_IDNAMES


def _rna_identity(value) -> int:
    """Stable identity for an RNA struct, falling back to id() off Blender.

    NOT id(): Blender hands out a temporary Python wrapper per socket/node access and
    this walk does not retain them, so a freed wrapper's address can be reused by the
    next one. A collision marks an unvisited socket as seen and prunes the branch that
    holds the map this run is baking - the run then stays single-phase and the material
    bakes against the previous run's mesh maps. bakeability_ui._node_identity already
    does it this way.
    """
    as_pointer = getattr(value, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(value)


def walk_upstream_nodes(start_socket, group_stack=()) -> list:
    """Every shader node reachable upstream of *start_socket*, in encounter order.

    Crosses node-group boundaries in both directions: a ``GROUP`` node descends into the
    matching Group Output socket (pushing the instance onto the stack) and a ``GROUP_INPUT``
    node pops back out to the enclosing instance's input. That precision matters for the
    cycle guard -- a blanket "every image in the material" sweep would refuse a bake because
    of a texture the baked channel never reads -- and it is what lets ray-node detection
    see an AO node buried inside a mask group.

    ``GROUP`` / ``GROUP_INPUT`` are pure plumbing and are not reported; every other node
    is, exactly once, so callers can filter by type.
    """
    found: list = []
    found_ids: set[int] = set()
    seen: set = set()
    queue: list[tuple] = [(start_socket, tuple(group_stack), 0)]
    while queue:
        socket, stack, depth = queue.pop()
        if socket is None or depth > _MAX_WALK_DEPTH:
            continue
        key = (_rna_identity(socket), tuple(_rna_identity(node) for node in stack))
        if key in seen:
            continue
        seen.add(key)
        for link in getattr(socket, "links", None) or ():
            node = getattr(link, "from_node", None)
            from_socket = getattr(link, "from_socket", None)
            if node is None:
                continue
            node_type = str(getattr(node, "type", "") or "")
            if node_type == "GROUP":
                tree = getattr(node, "node_tree", None)
                output_node = _group_output_node(tree)
                if output_node is None:
                    continue
                inner = _socket_by_name(getattr(output_node, "inputs", None), from_socket)
                if inner is None:
                    inner = _socket_by_index(
                        getattr(node, "outputs", None),
                        from_socket,
                        getattr(output_node, "inputs", None),
                    )
                if inner is not None:
                    queue.append((inner, stack + (node,), depth + 1))
                continue
            if node_type == "GROUP_INPUT":
                if not stack:
                    continue
                parent = stack[-1]
                outer = _socket_by_name(getattr(parent, "inputs", None), from_socket)
                if outer is None:
                    outer = _socket_by_index(
                        getattr(node, "outputs", None),
                        from_socket,
                        getattr(parent, "inputs", None),
                    )
                if outer is not None:
                    queue.append((outer, stack[:-1], depth + 1))
                continue
            node_key = _rna_identity(node)
            if node_key not in found_ids:
                found_ids.add(node_key)
                found.append(node)
            # Keep climbing: a texture's Vector input, or an AO node's Color input, can
            # itself be driven by another texture.
            for node_input in getattr(node, "inputs", None) or ():
                queue.append((node_input, stack, depth + 1))
    return found


def walk_upstream_image_nodes(start_socket, group_stack=()) -> list:
    """Image Texture nodes reachable upstream of *start_socket*."""
    return [
        node
        for node in walk_upstream_nodes(start_socket, group_stack)
        if str(getattr(node, "type", "") or "") == "TEX_IMAGE"
    ]


def _channel_start_sockets(material, map_setting) -> list[tuple]:
    """``(socket, group_stack)`` entry points for the channel this row bakes."""
    origin = str(getattr(map_setting, "material_origin", "") or "")
    if origin == constants.MATERIAL_ORIGIN_CUSTOM:
        # Same node predicate as material_capture_nodes.is_custom_output_node /
        # iter_custom_outputs, inlined so detection does not drag the node-class module
        # (and its bpy.props registration) into a plain path scan.
        wanted = str(getattr(map_setting, "material_custom_name", "") or "").strip().casefold()
        if not wanted:
            return []
        tree = getattr(material, "node_tree", None)
        starts: list[tuple] = []
        for node in getattr(tree, "nodes", None) or ():
            if getattr(node, "bl_idname", "") != constants.FYR_CUSTOM_OUTPUT_NODE_ID:
                continue
            if str(getattr(node, "output_name", "") or "").strip().casefold() != wanted:
                continue
            inputs = list(getattr(node, "inputs", None) or ())
            if inputs:
                starts.append((inputs[0], ()))
        return starts

    from . import material_channel_graph

    channel = str(
        getattr(map_setting, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or ""
    ).strip().upper()
    socket_name = _CHANNEL_TO_SOCKET.get(channel)
    if not socket_name:
        return []
    try:
        principled, chain = material_channel_graph.resolve_principled(material)
    except Exception:
        return []
    if principled is None:
        return []
    socket = _named_socket(getattr(principled, "inputs", None), socket_name)
    if socket is None:
        return []
    return [(socket, tuple(chain or ()))]


def collect_group_materials(project, selected_group_names) -> list:
    """Materials a MATERIAL row will compile against, mirroring ``export._collect_material_ir_source``."""
    from . import project_structure

    materials: list = []
    for group in getattr(project, "groups", None) or ():
        group_name = str(getattr(group, "name", "") or "")
        if selected_group_names is not None and group_name not in selected_group_names:
            continue
        targets = list(
            project_structure.group_role_targets(group, constants.OBJECT_ROLE_HIGH) or ()
        )
        if not targets:
            targets = list(
                project_structure.group_role_targets(group, constants.OBJECT_ROLE_LOW) or ()
            )
        for obj in targets:
            for slot in getattr(obj, "material_slots", None) or ():
                material = getattr(slot, "material", None)
                if material is None:
                    continue
                if all(material is not known for known in materials):
                    materials.append(material)
    return materials


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def _selected_rows(project, selected_map_uuids) -> list:
    wanted = {str(value or "").strip() for value in (selected_map_uuids or ()) if str(value or "").strip()}
    rows: list = []
    for map_setting in getattr(project, "maps", None) or ():
        if getattr(map_setting, "is_add_phantom", False):
            continue
        map_uuid = properties.ensure_map_setting_uuid(map_setting)
        if wanted:
            if map_uuid not in wanted:
                continue
        elif not bool(getattr(map_setting, "enabled", True)):
            # No explicit selection: fall back to "what a plain Bake would run".
            continue
        rows.append(map_setting)
    return rows


#: Map types whose shading starts from the surface normal at the hit, so they read the
#: material-detail normal when one is available (backend: map_type_shades_from_material_normal).
#: Env Light stays on the raw surface. AO and Bent Normal join when Use Bevel Normal
#: resolves to Convex or All (Auto does that for a Bevel shader, convex edges only,
#: so a concave fillet keeps the raw surface and the crevice stays dark).
NORMAL_CONSUMER_MAP_TYPES = frozenset(
    {
        constants.MAP_CAVITY,
        constants.MAP_CURVATURE,
        constants.MAP_CONCAVE,
        constants.MAP_CONVEX,
        constants.MAP_PRINCIPAL_CURVATURE,
        constants.MAP_CURVATURE_DIRECTION,
        constants.MAP_OBJECT_NORMAL,
        constants.MAP_WORLD_NORMAL,
    }
)

#: AO and Bent Normal cast a hemisphere around the shading normal. They read the
#: bevelled normal only when Use Bevel Normal resolves on.
BEVEL_OCCLUSION_MAP_TYPES = frozenset(
    {
        constants.MAP_AO,
        constants.MAP_BENT_NORMAL,
    }
)


def _is_bevel_node(node) -> bool:
    """ShaderNodeBevel, matched the same two ways as the other ray nodes."""
    if node is None:
        return False
    if str(getattr(node, "type", "") or "") == "BEVEL":
        return True
    return str(getattr(node, "bl_idname", "") or "") == "ShaderNodeBevel"


def high_normal_graph_has_bevel(project, selected_group_names) -> bool:
    """True when a Bevel shader feeds a high material's Principled Normal input.

    Follows the surface through groups and Mix Shaders, so a preview wrapper
    (ZenBBQ) still counts. A Bevel parked on some other socket does not.
    """
    try:
        materials = collect_group_materials(project, selected_group_names)
    except Exception:
        return False
    if not materials:
        return False
    try:
        from . import export

        principled_nodes = export._surface_principled_nodes  # noqa: SLF001
    except Exception:
        return False
    for material in materials:
        try:
            pairs = principled_nodes(material, with_stack=True)
        except Exception:
            continue
        for node, stack in pairs or ():
            socket = _named_socket(getattr(node, "inputs", None), "Normal")
            if socket is None:
                continue
            for upstream in walk_upstream_nodes(socket, stack):
                if _is_bevel_node(upstream):
                    return True
    return False


def resolve_ao_bevel_normal(row, *, bevel_present: bool) -> str:
    """OFF, ALL, or CONVEX. Auto follows a Bevel shader; anything else is explicit.

    Diffusive Escape does not shade a hemisphere from the hit normal, so it stays
    geometric no matter what the row says.
    """
    ao_mode = str(getattr(row, "ao_mode", constants.MAP_AO_MODE_RAYCAST) or "").strip().upper()
    if ao_mode == constants.MAP_AO_MODE_DIFFUSIVE_ESCAPE:
        return constants.AO_BEVEL_NORMAL_OFF
    value = str(
        getattr(row, "ao_bevel_normal", constants.AO_BEVEL_NORMAL_AUTO) or constants.AO_BEVEL_NORMAL_AUTO
    ).strip().upper()
    if value in (
        constants.AO_BEVEL_NORMAL_OFF,
        constants.AO_BEVEL_NORMAL_ALL,
        constants.AO_BEVEL_NORMAL_CONVEX,
    ):
        return value
    return constants.AO_BEVEL_NORMAL_CONVEX if bevel_present else constants.AO_BEVEL_NORMAL_OFF


def row_consumes_material_normal(row, *, bevel_present: bool = False) -> bool:
    """True when this row shades from the material-detail (bevelled) normal."""
    map_type = str(getattr(row, "map_type", "") or "").strip().upper()
    if map_type in NORMAL_CONSUMER_MAP_TYPES:
        return True
    if map_type not in BEVEL_OCCLUSION_MAP_TYPES:
        return False
    return resolve_ao_bevel_normal(row, bevel_present=bevel_present) != constants.AO_BEVEL_NORMAL_OFF


def _socket_feeds_normal_detail(socket) -> bool:
    """True when a Principled Normal input carries something worth baking."""
    if socket is None:
        return False
    is_linked = getattr(socket, "is_linked", None)
    if is_linked is None:
        # Test fakes: a plain socket with a links list.
        return bool(getattr(socket, "links", None))
    if not is_linked:
        return False
    try:
        from . import export

        return bool(export._normal_socket_has_detail_source(socket))  # noqa: SLF001
    except Exception:
        return True


def _normal_rows_with_material_detail(project, rows, selected_group_names) -> list:
    """Tangent Normal rows (Material Detail = Auto) whose high materials carry normal detail."""
    from . import normal_material_route

    candidates = [row for row in rows if normal_material_route.row_is_eligible(row)]
    if not candidates:
        return []
    try:
        materials = collect_group_materials(project, selected_group_names)
    except Exception:
        return []
    found = []
    for row in candidates:
        view = normal_material_route.NormalAsMaterialRow(row)
        for material in materials:
            starts = list(_channel_start_sockets(material, view))
            if not starts:
                try:
                    from . import export

                    starts = [
                        (node.inputs.get("Normal"), stack)
                        for node, stack in export._surface_principled_nodes(  # noqa: SLF001
                            material, with_stack=True
                        )
                        if node.inputs.get("Normal") is not None
                    ]
                except Exception:
                    starts = []
            if any(_socket_feeds_normal_detail(socket) for socket, _stack in starts):
                found.append(row)
                break
    return found


def _row_flip_green(row) -> bool:
    """The row's green convention, resolved the way export resolves it for the job."""
    try:
        normal_format = str(properties.effective_normal_format(row) or "").strip().upper()
    except Exception:
        normal_format = str(getattr(row, "normal_format", "") or "").strip().upper()
    if normal_format == constants.NORMAL_FORMAT_DIRECTX:
        return True
    if normal_format == constants.NORMAL_FORMAT_OPENGL:
        return False
    return bool(getattr(row, "flip_green", False))


def _normal_rows_with_ray_nodes(project, rows, selected_group_names) -> list[tuple]:
    """``(row, [RayOpUsage])`` for Normal rows whose material normal graph traces rays.

    Only rows normal_material_route would hand to the Material IR are considered; the
    real row is returned so the caller keeps planning in terms of project rows.
    """
    from . import normal_material_route

    candidates = [row for row in rows if normal_material_route.row_is_eligible(row)]
    if not candidates:
        return []
    try:
        materials = collect_group_materials(project, selected_group_names)
    except Exception:
        return []
    found: list[tuple] = []
    for row in candidates:
        view = normal_material_route.NormalAsMaterialRow(row)
        row_uuid = properties.ensure_map_setting_uuid(row)
        row_label = _row_label(project, row)
        usages: list[RayOpUsage] = []
        for material in materials:
            material_name = str(getattr(material, "name", "") or "Material")
            starts = list(_channel_start_sockets(material, view))
            if not starts:
                # The Principled sits behind a shader group / Mix Shader (ZenBBQ's
                # preview shader): take every Principled feeding the surface.
                try:
                    from . import export

                    starts = [
                        (node.inputs.get("Normal"), stack)
                        for node, stack in export._surface_principled_nodes(  # noqa: SLF001
                            material, with_stack=True
                        )
                        if node.inputs.get("Normal") is not None
                    ]
                except Exception:
                    starts = []
            for socket, stack in starts:
                for node in walk_upstream_nodes(socket, stack):
                    if not is_ray_node(node):
                        continue
                    usages.append(
                        RayOpUsage(
                            map_uuid=row_uuid,
                            label=row_label,
                            material_name=material_name,
                            node_name=str(getattr(node, "name", "") or "node"),
                            node_type=str(
                                getattr(node, "type", "")
                                or getattr(node, "bl_idname", "")
                                or "RAY"
                            ),
                        )
                    )
        if usages:
            found.append((row, usages))
    return found


def plan_bake_phases(
    project,
    selected_map_uuids,
    selected_group_names,
    *,
    output_dir=None,
) -> BakePhasePlan:
    """Split this run into "mesh maps first, dependent materials second" when needed.

    A material row moves to phase 2 for either of two independent reasons:

    1. **Dependency** -- its channel graph samples an image file this same run writes,
       so it must bake after that file exists (and after the datablock is reloaded).
    2. **Secondary-ray nodes** -- its graph contains an AO / Bevel / Raycast node. Those
       opcodes only compile natively in the backend's MATERIAL_ONLY shading permutation,
       which ``export._job_is_material_only_backend_batch`` can only vouch for on an
       all-material job; in a mixed mesh+material run the row is refused to Cycles at
       export. Phase 2 is all-material by construction, so the existing proof passes
       there and the ray ops run native.

    Both reasons need a mesh map in the same selection to be worth acting on, so an
    all-material selection (already vouchable) and a mesh-only selection both stay
    single-phase. Returns a plan whose ``deferred_map_uuids`` is empty in those cases --
    callers must treat that as "no change". ``errors`` is non-empty only for the cycle
    case (a material row reading a MATERIAL output produced by this same run), which v1
    refuses rather than scheduling N phases.
    """
    rows = _selected_rows(project, selected_map_uuids)
    material_rows = [
        row
        for row in rows
        if str(getattr(row, "map_type", "") or "").strip().upper() == constants.MAP_MATERIAL
    ]
    mesh_rows = [
        row
        for row in rows
        if str(getattr(row, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL
    ]
    all_uuids = [properties.ensure_map_setting_uuid(row) for row in rows]
    plan = BakePhasePlan(first_phase_map_uuids=list(all_uuids))
    # Material-detail normals: when a map in this run shades from the surface normal
    # and the Normal row carries high-material normal detail, the Normal row goes
    # first and the others read its retained texels (see BakePhasePlan).
    bevel_present = high_normal_graph_has_bevel(project, selected_group_names)
    consumer_rows = [
        row for row in mesh_rows if row_consumes_material_normal(row, bevel_present=bevel_present)
    ]
    normal_first_row = None
    if consumer_rows:
        detail_rows = _normal_rows_with_material_detail(project, mesh_rows, selected_group_names)
        source_only = False
        if not detail_rows:
            # Curvature / Object Normal baked without their Normal row (a re-bake of one
            # map, or a stack whose Normal row is switched off): the bevel must not
            # silently drop out of them. The project's own Normal row still goes first,
            # as a source only, with its settings, so the maps match the Normal map.
            selected_uuids = set(all_uuids)
            unselected = [
                row
                for row in getattr(project, "maps", None) or ()
                if not getattr(row, "is_add_phantom", False)
                and properties.ensure_map_setting_uuid(row) not in selected_uuids
            ]
            detail_rows = _normal_rows_with_material_detail(project, unselected, selected_group_names)
            source_only = bool(detail_rows)
        if detail_rows:
            normal_first_row = detail_rows[0]
            plan.normal_first_map_uuid = properties.ensure_map_setting_uuid(normal_first_row)
            plan.normal_first_flip_green = _row_flip_green(normal_first_row)
            plan.normal_first_label = _row_label(project, normal_first_row)
            plan.normal_first_source_only = source_only
    # A tangent Normal row on Material Detail = Auto bakes through the Material IR when
    # its high-material normal graph compiles natively (normal_material_route), so a
    # ray node there (the Bevel shader, typically) carries the same all-material
    # constraint as a MATERIAL row. Such a row is not a mesh row for this split.
    normal_ray_rows = _normal_rows_with_ray_nodes(project, mesh_rows, selected_group_names)
    if normal_ray_rows:
        ray_row_ids = {id(row) for row, _usages in normal_ray_rows}
        mesh_rows = [row for row in mesh_rows if id(row) not in ray_row_ids]
    if (not material_rows and not normal_ray_rows) or not mesh_rows:
        # Nothing to order: a run with no material rows, or an all-material run whose
        # materials cannot read a mesh map written by this same run AND whose ray ops are
        # already vouchable by the material-only proof.
        return plan

    # Not an early exit on emptiness: a ray-only phase-2 member involves no image
    # reference at all, so it must not depend on there being any producer paths.
    producers = planned_output_producers(
        project, rows, selected_group_names, output_dir=output_dir
    )

    materials = collect_group_materials(project, selected_group_names)
    if not materials:
        return plan

    dependencies: list[MaterialDependency] = []
    ray_usages: list[RayOpUsage] = []
    errors: list[str] = []
    deferred: list[str] = []
    deferred_labels: list[str] = []
    reload_keys: list[str] = []

    for normal_row, normal_usages in normal_ray_rows:
        normal_uuid = properties.ensure_map_setting_uuid(normal_row)
        if normal_uuid == plan.normal_first_map_uuid:
            # Going first, alone: already an all-material job, so its ray ops run
            # natively there. Phase 2 would also be too late for the maps reading it.
            continue
        if normal_uuid not in deferred:
            deferred.append(normal_uuid)
            deferred_labels.append(_row_label(project, normal_row))
        ray_usages.extend(normal_usages)

    for row in material_rows:
        row_uuid = properties.ensure_map_setting_uuid(row)
        row_label = _row_label(project, row)
        row_is_deferred = False
        for material in materials:
            material_name = str(getattr(material, "name", "") or "Material")
            for socket, stack in _channel_start_sockets(material, row):
                for node in walk_upstream_nodes(socket, stack):
                    if is_ray_node(node):
                        ray_usages.append(
                            RayOpUsage(
                                map_uuid=row_uuid,
                                label=row_label,
                                material_name=material_name,
                                node_name=str(getattr(node, "name", "") or "node"),
                                node_type=str(
                                    getattr(node, "type", "")
                                    or getattr(node, "bl_idname", "")
                                    or "RAY"
                                ),
                            )
                        )
                        row_is_deferred = True
                        # Fall through: the node's own inputs are still walked by the
                        # traversal, and a ray node is never an Image Texture.
                    if str(getattr(node, "type", "") or "") != "TEX_IMAGE":
                        continue
                    image = getattr(node, "image", None)
                    if image is None:
                        continue
                    key = image_path_key(image)
                    if not key:
                        continue
                    producer = producers.get(key)
                    if producer is None:
                        # Either an unrelated texture, or a mesh map on disk that this
                        # run is not rewriting -- already current, no split needed.
                        continue
                    dependency = MaterialDependency(
                        map_uuid=row_uuid,
                        label=row_label,
                        material_name=material_name,
                        node_name=str(getattr(node, "name", "") or "Image Texture"),
                        image_name=str(getattr(image, "name", "") or "image"),
                        producer=producer,
                    )
                    if producer.is_material_row:
                        detail = (
                            "material reads its own baked output"
                            if producer.map_uuid == row_uuid
                            else f"material reads '{producer.label}', baked in the same run"
                        )
                        message = f"{dependency.describe()}: {detail}"
                        if message not in errors:
                            errors.append(message)
                        continue
                    dependencies.append(dependency)
                    row_is_deferred = True
                    if key not in reload_keys:
                        reload_keys.append(key)
        # One membership per row, however many reasons it accumulated.
        if row_is_deferred and row_uuid not in deferred:
            deferred.append(row_uuid)
            deferred_labels.append(row_label)

    if errors:
        plan.errors = errors
        return plan
    if not deferred:
        return plan

    plan.first_phase_map_uuids = [
        map_uuid for map_uuid in all_uuids if map_uuid not in set(deferred)
    ]
    plan.deferred_map_uuids = deferred
    plan.deferred_row_labels = deferred_labels
    plan.dependencies = dependencies
    plan.ray_usages = ray_usages
    plan.reload_path_keys = reload_keys
    return plan


# ---------------------------------------------------------------------------
# Phase boundary: refresh the referenced datablocks
# ---------------------------------------------------------------------------


def reload_images_for_path_keys(path_keys) -> tuple[list[str], list[str], list[str]]:
    """Reload every image datablock pointing at one of *path_keys*.

    Scans ``bpy.data.images`` instead of remembering datablock identities from planning
    time: the same file may be referenced by more than one datablock, and a name captured
    before phase 1 can go stale. Returns ``(reloaded_names, packed_names, failed_names)``;
    a packed image has no disk pixels to pick up, and a reload that RAISES means phase 2
    would shade from the previous run's pixels, so both are reported rather than silently
    trusted.
    """
    wanted = {str(key or "") for key in (path_keys or ()) if str(key or "")}
    reloaded: list[str] = []
    packed: list[str] = []
    failed: list[str] = []
    if not wanted:
        return reloaded, packed, failed
    for image in getattr(getattr(bpy, "data", None), "images", None) or ():
        if image_path_key(image) not in wanted:
            continue
        name = str(getattr(image, "name", "") or "image")
        if getattr(image, "packed_file", None) is not None:
            if name not in packed:
                packed.append(name)
            continue
        try:
            image.reload()
        except Exception as exc:
            # Swallowing this let phase 2 re-snapshot the previous run's curvature/AO
            # and report success.
            print(f"[MasterBaker] could not reload '{name}' between bake phases: {exc}")
            if name not in failed:
                failed.append(name)
            continue
        if name not in reloaded:
            reloaded.append(name)
    return reloaded, packed, failed
