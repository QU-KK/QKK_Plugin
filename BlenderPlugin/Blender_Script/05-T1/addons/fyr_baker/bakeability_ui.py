"""Live "Bakeability" readout for the Shader Editor sidebar.

Answers, before the user ever presses Bake, the only question that matters about
a material graph: does it bake *natively* through Fyr, does it fall back to
Cycles (correct but slower), or does it contain something that cannot be baked
at all (view-dependent nodes -- there is no camera during a bake).

Ground truth is the Material IR compiler itself: every channel is actually
compiled (``material_ir.compile_channel_program``) and its refusal captured.
``material_graph.classify_node_output`` is only the fast pre-pass that separates
"needs Cycles" from "genuinely unbakeable" once the compiler has already
refused.

Compilation is milliseconds, but it never runs from ``draw``: a
``depsgraph_update_post`` handler sets a dirty flag, a debounced timer
recomputes for whichever materials are on screen, and the panel only ever reads
the cache.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time

try:  # pragma: no cover - the analysis layer is unit-tested without Blender
    import bpy  # type: ignore
except ImportError:  # pragma: no cover
    bpy = None  # type: ignore

from . import constants
from .handler_thread_guard import on_main_thread
from . import material_graph
from . import material_ir


# --------------------------------------------------------------------------
# Analysis layer (pure -- no bpy)
# --------------------------------------------------------------------------

STATUS_NATIVE = "NATIVE"
STATUS_CYCLES = "CYCLES"
STATUS_UNBAKEABLE = "UNBAKEABLE"

#: Worse status wins when folding channel verdicts into one summary.
STATUS_RANK = {STATUS_NATIVE: 0, STATUS_CYCLES: 1, STATUS_UNBAKEABLE: 2}

STATUS_ICON = {
    STATUS_NATIVE: "CHECKMARK",
    STATUS_CYCLES: "INFO",
    STATUS_UNBAKEABLE: "ERROR",
}

STATUS_TEXT = {
    STATUS_NATIVE: "",
    STATUS_CYCLES: "via Cycles",
    STATUS_UNBAKEABLE: "unbakeable",
}

#: Depth cap for the view-dependency walk, matching material_graph._MAX_DEPTH.
_MAX_DEPTH = 24

#: Node attributes that change what a node computes. Folded into the graph
#: signature so an enum flip (Mix blend type, Math operation, ...) invalidates
#: the cached verdict even though no link or default value moved.
_SIGNIFICANT_NODE_ATTRS = (
    "blend_type",
    "operation",
    "data_type",
    "vector_type",
    "distribution",
    "feature",
    "noise_dimensions",
    "voronoi_dimensions",
    "wave_type",
    "wave_profile",
    "bands_direction",
    "rings_direction",
    "gradient_type",
    "interpolation",
    "projection",
    "extension",
    "convert_from",
    "convert_to",
    "mode",
    "space",
    "target",
    "attribute_name",
    "attribute_type",
    "uv_map",
    "output_name",
    "clamp",
    "use_clamp",
    "use_pixel_size",
    "invert",
    "inside",
    "only_local",
    "samples",
    "turbulence_depth",
    "normalize",
    "from_instancer",
    "component",
)


@dataclass(frozen=True)
class ChannelVerdict:
    """One channel's bakeability, as decided by an actual compile."""

    channel: str
    label: str
    status: str = STATUS_NATIVE
    reason: str = ""
    node_name: str = ""
    node_type: str = ""
    node_path: tuple[str, ...] = ()

    @property
    def is_issue(self) -> bool:
        return self.status != STATUS_NATIVE


@dataclass(frozen=True)
class Issue:
    """One distinct refusal, with every channel it blocks."""

    status: str
    reason: str
    node_name: str = ""
    node_type: str = ""
    node_path: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class MaterialReport:
    material_name: str = ""
    signature: str = ""
    channels: tuple[ChannelVerdict, ...] = ()
    issues: tuple[Issue, ...] = ()
    status: str = STATUS_NATIVE
    summary: str = "Bakes natively"
    has_principled: bool = True
    note: str = ""


def _node_identity(node) -> int:
    as_pointer = getattr(node, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(node)


def _principled(material):
    """The Principled that actually drives the surface, through node groups.

    Not "the first BSDF_PRINCIPLED in the tree": the compiler resolves the channel
    through the Material Output's Surface link (material_ir), so a stray disconnected
    Principled, or one wrapped in a node group, made this panel read a different node
    than the bake would - and for a Diffuse/Glass/Mix surface it found none, returned
    None, and find_view_dependent(None) bailed out at once. A Base Color driven by
    Layer Weight then reported "via Cycles" although it is not bakeable at all (there
    is no camera during a bake), and the artist got a wrong map with no explanation.
    """
    from . import material_channel_graph

    try:
        node, _chain = material_channel_graph.resolve_principled(material)
    except Exception:
        node = None
    if node is not None:
        return node
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None
    for candidate in getattr(tree, "nodes", ()) or ():
        if str(getattr(candidate, "type", "") or "") == "BSDF_PRINCIPLED":
            return candidate
    return None


def _channel_socket(material, channel: str):
    """The Principled input socket a material channel bakes from."""
    socket_name = material_ir.CHANNEL_TO_PRINCIPLED.get(str(channel or "").upper())
    if not socket_name:
        return None
    node = _principled(material)
    if node is None:
        return None
    inputs = getattr(node, "inputs", None)
    if inputs is None:
        return None
    getter = getattr(inputs, "get", None)
    return getter(socket_name) if callable(getter) else None


def _group_output_socket(group_node, output_name: str):
    """The socket inside a node group that feeds ``output_name``."""
    tree = getattr(group_node, "node_tree", None)
    if tree is None:
        return None
    candidates = [
        node
        for node in getattr(tree, "nodes", ()) or ()
        if str(getattr(node, "type", "") or "") == "GROUP_OUTPUT"
    ]
    if not candidates:
        return None
    active = next((n for n in candidates if getattr(n, "is_active_output", False)), candidates[0])
    inputs = getattr(active, "inputs", None)
    if inputs is None:
        return None
    getter = getattr(inputs, "get", None)
    socket = getter(output_name) if callable(getter) else None
    if socket is not None:
        return socket
    for candidate in inputs:
        if str(getattr(candidate, "name", "") or "") == str(output_name or ""):
            return candidate
    return None


def find_view_dependent(socket, *, depth: int = 0, seen: set | None = None, path: tuple = ()):
    """First view-dependent node feeding ``socket``, or None.

    Returns ``(node_name, node_type, reason, path)``. Descends through node
    groups, because a Camera Data buried three groups deep is still fatal.
    """
    if socket is None or depth > _MAX_DEPTH:
        return None
    if seen is None:
        seen = set()
    for link in tuple(getattr(socket, "links", ()) or ()):
        node = getattr(link, "from_node", None) or getattr(getattr(link, "from_socket", None), "node", None)
        from_socket = getattr(link, "from_socket", None)
        if node is None:
            continue
        out_name = str(getattr(from_socket, "name", "") or "")
        key = (_node_identity(node), out_name)
        if key in seen:
            continue
        seen.add(key)

        node_name = str(getattr(node, "name", "") or "")
        ntype = str(getattr(node, "type", "") or "")
        node_path = path + (node_name,)
        coverage = material_graph.classify_node_output(ntype, out_name)
        if coverage.classification == material_graph.NODE_COVERAGE_VIEW_DEPENDENT:
            return node_name, ntype, coverage.reason, node_path

        if ntype == "GROUP":
            inner = _group_output_socket(node, out_name)
            found = find_view_dependent(inner, depth=depth + 1, seen=seen, path=node_path)
            if found is not None:
                return found

        for input_socket in getattr(node, "inputs", ()) or ():
            found = find_view_dependent(input_socket, depth=depth + 1, seen=seen, path=node_path)
            if found is not None:
                return found
    return None


def _socket_default_signature(socket) -> str:
    try:
        value = socket.default_value
    except Exception:
        return ""
    try:
        if hasattr(value, "__len__") and not isinstance(value, str):
            return ",".join(f"{float(v):.6g}" for v in value)
        if isinstance(value, str):
            return value
        return f"{float(value):.6g}"
    except Exception:
        return str(value)


def _node_signature_parts(node) -> list[str]:
    parts = [
        str(getattr(node, "name", "") or ""),
        str(getattr(node, "type", "") or ""),
        str(getattr(node, "label", "") or ""),
        "1" if getattr(node, "mute", False) else "0",
    ]
    image = getattr(node, "image", None)
    if image is not None:
        parts.append(str(getattr(image, "name", "") or ""))
        parts.append(str(getattr(image, "filepath", "") or ""))
    subtree = getattr(node, "node_tree", None)
    if subtree is not None:
        parts.append(str(getattr(subtree, "name", "") or ""))
    for attr in _SIGNIFICANT_NODE_ATTRS:
        if not hasattr(node, attr):
            continue
        try:
            parts.append(f"{attr}={getattr(node, attr)!r}")
        except Exception:
            continue
    for socket in getattr(node, "inputs", ()) or ():
        name = str(getattr(socket, "name", "") or "")
        parts.append(f"<{name}={_socket_default_signature(socket)}")
        for link in tuple(getattr(socket, "links", ()) or ()):
            from_socket = getattr(link, "from_socket", None)
            from_node = getattr(link, "from_node", None) or getattr(from_socket, "node", None)
            parts.append(
                f"~{getattr(from_node, 'name', '')}:{getattr(from_socket, 'name', '')}"
            )
    return parts


def _tree_signature_parts(tree, seen: set | None = None) -> list[str]:
    if tree is None:
        return []
    if seen is None:
        seen = set()
    key = _node_identity(tree)
    if key in seen:
        return []
    seen.add(key)
    parts: list[str] = []
    for node in getattr(tree, "nodes", ()) or ():
        parts.extend(_node_signature_parts(node))
        subtree = getattr(node, "node_tree", None)
        if subtree is not None:
            parts.append("{")
            parts.extend(_tree_signature_parts(subtree, seen))
            parts.append("}")
    return parts


def graph_signature(material) -> str:
    """Cheap content hash of a material's node graph.

    Covers nodes, their type-defining enums, unlinked socket values, image
    assignments and every link, recursing into node groups. Two materials with
    the same signature compile to the same verdicts, so the cache can skip the
    recompile entirely.
    """
    if material is None:
        return ""
    parts = [str(getattr(material, "name", "") or ""), "1" if getattr(material, "use_nodes", False) else "0"]
    parts.extend(_tree_signature_parts(getattr(material, "node_tree", None)))
    digest = hashlib.blake2b("\x1f".join(parts).encode("utf-8", "replace"), digest_size=16)
    return digest.hexdigest()


def _verdict_for_program(channel: str, label: str, program, socket) -> ChannelVerdict:
    if getattr(program, "native", False):
        return ChannelVerdict(channel=channel, label=label, status=STATUS_NATIVE)

    # The compiler refused. Only now does the static classifier get a say, and
    # only to answer "is this Cycles-recoverable or truly unbakeable?".
    found = find_view_dependent(socket)
    if found is not None:
        node_name, node_type, reason, node_path = found
        return ChannelVerdict(
            channel=channel,
            label=label,
            status=STATUS_UNBAKEABLE,
            reason=reason or "Output depends on camera/view or rendered lighting",
            node_name=node_name,
            node_type=node_type,
            node_path=node_path,
        )
    return ChannelVerdict(
        channel=channel,
        label=label,
        status=STATUS_CYCLES,
        reason=str(getattr(program, "fallback_reason", "") or "Not native yet"),
        node_name=str(getattr(program, "fallback_node_name", "") or ""),
        node_type=str(getattr(program, "fallback_node_type", "") or ""),
        node_path=tuple(getattr(program, "fallback_node_path", ()) or ()),
    )


def collect_issues(channels) -> tuple[Issue, ...]:
    """Fold channel verdicts into one row per distinct refusal."""
    order: list[tuple] = []
    grouped: dict[tuple, list[str]] = {}
    for verdict in channels:
        if not verdict.is_issue:
            continue
        key = (verdict.status, verdict.reason, verdict.node_name, verdict.node_type, verdict.node_path)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(verdict.label)
    issues = []
    for key in order:
        status, reason, node_name, node_type, node_path = key
        issues.append(
            Issue(
                status=status,
                reason=reason,
                node_name=node_name,
                node_type=node_type,
                node_path=node_path,
                channels=tuple(grouped[key]),
            )
        )
    # Unbakeable first -- it is the only thing that stops a bake being correct.
    issues.sort(key=lambda item: -STATUS_RANK.get(item.status, 0))
    return tuple(issues)


def summarize(channels) -> tuple[str, str]:
    """(status, one-line summary) for a set of channel verdicts."""
    unbakeable = [c for c in channels if c.status == STATUS_UNBAKEABLE]
    cycles = [c for c in channels if c.status == STATUS_CYCLES]
    if unbakeable:
        count = len(unbakeable)
        return STATUS_UNBAKEABLE, f"{count} channel{'s' if count != 1 else ''} unbakeable"
    if cycles:
        count = len(cycles)
        return STATUS_CYCLES, f"{count} channel{'s' if count != 1 else ''} via Cycles"
    return STATUS_NATIVE, "Bakes natively"


def _iter_custom_outputs(material):
    try:
        from . import material_capture_nodes
    except Exception:
        return []
    try:
        return list(material_capture_nodes.iter_custom_outputs(material))
    except Exception:
        return []


def analyze_material(
    material,
    *,
    compile_channel=None,
    compile_custom=None,
    custom_outputs=None,
    workspace_path=None,
    signature: str | None = None,
    allow_ray_ops: bool = False,
) -> MaterialReport:
    """Compile every channel of ``material`` and report how each one bakes.

    ``compile_channel`` / ``compile_custom`` are injectable so the analysis layer
    can be exercised without Blender; production passes the real Material IR
    entry points, which are the routing authority.

    ``allow_ray_ops`` mirrors the exporter's `_job_is_material_only_backend_batch`
    predicate. Without it the AO / Bevel / Raycast nodes always report "needs
    Cycles", which is wrong for the material-only project where the backend
    actually runs them natively — the panel would warn about a fallback the bake
    never takes. The Blender-side caller resolves it from the active project.
    """
    name = str(getattr(material, "name", "") or "")
    sig = graph_signature(material) if signature is None else str(signature)

    if material is None or not getattr(material, "use_nodes", False):
        return MaterialReport(
            material_name=name,
            signature=sig,
            status=STATUS_CYCLES,
            summary="No node tree",
            has_principled=False,
            note="Material has no node tree",
        )

    if compile_channel is None:
        compile_channel = material_ir.compile_channel_program
    if compile_custom is None:
        compile_custom = material_ir.compile_custom_output_program
    if allow_ray_ops:
        _channel_impl, _custom_impl = compile_channel, compile_custom

        def compile_channel(mat, chan, **kwargs):  # noqa: F811 - deliberate rebind
            return _channel_impl(mat, chan, allow_ray_ops=True, **kwargs)

        def compile_custom(mat, label, **kwargs):  # noqa: F811 - deliberate rebind
            return _custom_impl(mat, label, allow_ray_ops=True, **kwargs)

    # No early-out on "there is no Principled BSDF". The compiler does not require
    # one -- Diffuse BSDF, Emission, Metallic, Glass and friends all flatten to
    # channels natively -- so returning "Bakes through Cycles" here reported a
    # fallback that does not happen, and reported it in the same words as the cases
    # that really do fall back. Let the per-channel compile below answer instead; it
    # is the routing authority, and it is what the bake actually does.

    verdicts: list[ChannelVerdict] = []
    for channel, label, _description in constants.MATERIAL_CHANNEL_ITEMS:
        try:
            program = compile_channel(material, channel, workspace_path=workspace_path)
        except Exception as exc:  # a compiler crash must not take the panel with it
            verdicts.append(
                ChannelVerdict(
                    channel=channel,
                    label=label,
                    status=STATUS_CYCLES,
                    reason=f"Could not analyze: {exc}",
                )
            )
            continue
        verdicts.append(
            _verdict_for_program(channel, label, program, _channel_socket(material, channel))
        )

    outputs = _iter_custom_outputs(material) if custom_outputs is None else list(custom_outputs)
    for node in outputs:
        label = str(getattr(node, "output_name", "") or "").strip() or "Custom"
        data_type = str(getattr(node, "data_type", "") or "")
        inputs = getattr(node, "inputs", None)
        socket = inputs[0] if inputs else None
        try:
            program = compile_custom(
                material, label, workspace_path=workspace_path, data_type=data_type
            )
        except Exception as exc:
            verdicts.append(
                ChannelVerdict(
                    channel=f"CUSTOM:{label}",
                    label=label,
                    status=STATUS_CYCLES,
                    reason=f"Could not analyze: {exc}",
                )
            )
            continue
        verdicts.append(_verdict_for_program(f"CUSTOM:{label}", label, program, socket))

    status, summary = summarize(verdicts)
    return MaterialReport(
        material_name=name,
        signature=sig,
        channels=tuple(verdicts),
        issues=collect_issues(verdicts),
        status=status,
        summary=summary,
        has_principled=True,
    )


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------

#: material name -> MaterialReport. Panel draw reads this and nothing else.
_REPORTS: dict[str, MaterialReport] = {}


def cached_report(material_name: str) -> MaterialReport | None:
    return _REPORTS.get(str(material_name or ""))


def clear_cache() -> None:
    _REPORTS.clear()


def active_project_allows_ray_ops() -> bool:
    """Whether the active project would let the exporter emit ray opcodes.

    Same rule as `export._job_is_material_only_backend_batch`: every enabled map
    row has to be a MATERIAL row, because only an all-material shading batch gets
    the backend's MATERIAL_ONLY permutation. Conservative on any error — the panel
    would rather under-promise than claim a native AO that the bake cannot run.
    """
    if bpy is None:
        return False
    try:
        from . import properties

        scene = getattr(bpy.context, "scene", None)
        project = properties.peek_active_project(scene) if scene is not None else None
        if project is None:
            return False
        saw_material = False
        for item in getattr(project, "maps", ()) or ():
            if getattr(item, "is_add_phantom", False) or not getattr(item, "enabled", False):
                continue
            if str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_MATERIAL:
                return False
            saw_material = True
        return saw_material
    except Exception:
        return False


def refresh_report(material, *, force: bool = False, **kwargs) -> MaterialReport | None:
    """Recompute a material's report unless its cached signature still holds."""
    if material is None:
        return None
    name = str(getattr(material, "name", "") or "")
    if not name:
        return None
    kwargs.setdefault("allow_ray_ops", active_project_allows_ray_ops())
    signature = f"{graph_signature(material)}|ray={int(bool(kwargs['allow_ray_ops']))}"
    cached = _REPORTS.get(name)
    if not force and cached is not None and cached.signature == signature:
        return cached
    report = analyze_material(material, signature=signature, **kwargs)
    _REPORTS[name] = report
    return report


# --------------------------------------------------------------------------
# Blender integration: debounce, handler, operator, panel
# --------------------------------------------------------------------------

_DEBOUNCE_SEC = 0.5
_PENDING = False
_LAST_REQUEST = 0.0


def _visible_shader_materials() -> list:
    """Materials currently edited in a Shader Editor, deduplicated."""
    if bpy is None:
        return []
    found: list = []
    seen: set[str] = set()
    windows = getattr(getattr(bpy.context, "window_manager", None), "windows", ()) or ()
    for window in windows:
        screen = getattr(window, "screen", None)
        for area in getattr(screen, "areas", ()) or ():
            if getattr(area, "type", "") != "NODE_EDITOR":
                continue
            for space in getattr(area, "spaces", ()) or ():
                if getattr(space, "type", "") != "NODE_EDITOR":
                    continue
                if str(getattr(space, "tree_type", "") or "") != "ShaderNodeTree":
                    continue
                material = getattr(space, "id", None)
                if not isinstance(material, bpy.types.Material):
                    continue
                if material.name in seen:
                    continue
                seen.add(material.name)
                found.append(material)
    return found


def _tag_node_editors() -> None:
    if bpy is None:
        return
    windows = getattr(getattr(bpy.context, "window_manager", None), "windows", ()) or ()
    for window in windows:
        screen = getattr(window, "screen", None)
        for area in getattr(screen, "areas", ()) or ():
            if getattr(area, "type", "") == "NODE_EDITOR":
                area.tag_redraw()


def request_update() -> None:
    """Mark the readout stale; the timer does the work off the draw path."""
    global _PENDING, _LAST_REQUEST
    if bpy is None:
        return
    _PENDING = True
    _LAST_REQUEST = time.monotonic()
    if not bpy.app.timers.is_registered(_timer_poll):
        bpy.app.timers.register(_timer_poll, first_interval=_DEBOUNCE_SEC)


def _timer_poll():
    global _PENDING
    if not _PENDING:
        return None
    if time.monotonic() - _LAST_REQUEST < _DEBOUNCE_SEC:
        return 0.1
    _PENDING = False
    changed = False
    try:
        for material in _visible_shader_materials():
            before = _REPORTS.get(material.name)
            report = refresh_report(material)
            if report is not before:
                changed = True
    except Exception as exc:  # pragma: no cover - never let the timer die
        print(f"[FyrBaker] bakeability analysis failed: {exc}")
    if changed:
        _tag_node_editors()
    return None


def _depsgraph_update_post(_scene, depsgraph):
    # Blender also calls this from a bake/render job thread (handler_thread_guard).
    if not on_main_thread():
        return
    try:
        updates = getattr(depsgraph, "updates", ()) or ()
    except Exception:
        return
    for update in updates:
        datablock = getattr(update, "id", None)
        if isinstance(datablock, (bpy.types.Material, bpy.types.ShaderNodeTree)):
            request_update()
            return


def _load_post(*_args):
    clear_cache()
    request_update()


#: The callbacks actually appended to the handler lists. Blender drops every handler
#: that is not marked `@persistent` when a file is loaded, so an unwrapped
#: depsgraph handler stops firing the moment the user opens a .blend and `_load_post`
#: never runs to clear the cache -- leaving the panel showing verdicts keyed by
#: material name from the *previous* file. `@persistent` is applied at register time
#: because `bpy` may be absent when this module is imported (unit tests).
_DEPSGRAPH_HANDLER = None
_LOAD_POST_HANDLER = None


if bpy is not None:
    _PanelBase = bpy.types.Panel
    _OperatorBase = bpy.types.Operator
    _StringProperty = bpy.props.StringProperty
else:  # pragma: no cover - import-time shims so tests can load this module
    class _PanelBase:  # type: ignore[no-redef]
        pass

    class _OperatorBase:  # type: ignore[no-redef]
        pass

    def _StringProperty(**_kwargs):  # type: ignore[no-redef]
        return ""


def _find_node(tree, node_path: tuple[str, ...], node_name: str):
    """Deepest node of ``node_path`` that exists in ``tree`` (innermost first)."""
    if tree is None:
        return None
    nodes = getattr(tree, "nodes", None)
    if nodes is None:
        return None
    for name in tuple(reversed(node_path or ())) + ((node_name,) if node_name else ()):
        if not name:
            continue
        node = nodes.get(name)
        if node is not None:
            return node
    return None


class MASTER_BAKER_OT_bakeability_focus_node(_OperatorBase):
    """Select the node behind this issue and frame it in the editor"""

    bl_idname = "master_baker.bakeability_focus_node"
    bl_label = "Focus Node"
    bl_options = {"REGISTER", "INTERNAL"}

    material_name: _StringProperty(name="Material", default="")
    node_name: _StringProperty(name="Node", default="")
    node_path: _StringProperty(name="Node Path", default="")

    def execute(self, context):
        try:
            path = tuple(json.loads(self.node_path or "[]"))
        except Exception:
            path = ()
        path = tuple(str(item) for item in path)

        space = getattr(context, "space_data", None)
        material = bpy.data.materials.get(self.material_name) if self.material_name else None
        candidates = []
        edit_tree = getattr(space, "edit_tree", None)
        if edit_tree is not None:
            candidates.append(edit_tree)
        if material is not None and getattr(material, "node_tree", None) is not None:
            candidates.append(material.node_tree)

        node = None
        tree = None
        for candidate in candidates:
            node = _find_node(candidate, path, self.node_name)
            if node is not None:
                tree = candidate
                break
        if node is None:
            self.report({"WARNING"}, "Could not find that node here -- it may be inside a node group")
            return {"CANCELLED"}

        for other in tree.nodes:
            other.select = False
        node.select = True
        tree.nodes.active = node

        if tree is edit_tree:
            area = getattr(context, "area", None)
            region = None
            if area is not None:
                region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if area is not None and region is not None:
                with context.temp_override(window=context.window, area=area, region=region):
                    bpy.ops.node.view_selected()
        return {"FINISHED"}


class MASTER_BAKER_PT_node_bakeability(_PanelBase):
    bl_label = "Bakeability"
    bl_idname = "MASTER_BAKER_PT_node_bakeability"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = constants.UI_TAB_NAME

    @classmethod
    def poll(cls, context):
        space = getattr(context, "space_data", None)
        if space is None or str(getattr(space, "tree_type", "") or "") != "ShaderNodeTree":
            return False
        material = getattr(space, "id", None)
        return isinstance(material, bpy.types.Material)

    def draw(self, context):
        layout = self.layout
        material = context.space_data.id
        report = cached_report(getattr(material, "name", ""))
        if report is None:
            request_update()
            layout.label(text="Analyzing...", icon="TIME")
            return

        header = layout.row(align=True)
        header.label(text=report.summary, icon=STATUS_ICON.get(report.status, "INFO"))

        if not report.has_principled:
            if report.note:
                layout.label(text=report.note, icon="INFO")
            return

        grid = layout.column(align=True)
        for verdict in report.channels:
            row = grid.row(align=True)
            row.label(text=verdict.label, icon=STATUS_ICON.get(verdict.status, "BLANK1"))
            text = STATUS_TEXT.get(verdict.status, "")
            if text:
                sub = row.row()
                sub.alignment = "RIGHT"
                sub.label(text=text)

        if not report.issues:
            return

        layout.separator()
        issues = layout.column(align=True)
        for issue in report.issues:
            box = issues.box()
            row = box.row(align=True)
            row.label(text=issue.reason, icon=STATUS_ICON.get(issue.status, "INFO"))
            if issue.node_name:
                op = row.operator(
                    "master_baker.bakeability_focus_node", text="", icon="VIEWZOOM"
                )
                op.material_name = report.material_name
                op.node_name = issue.node_name
                op.node_path = json.dumps(list(issue.node_path))
            if issue.channels:
                sub = box.row()
                sub.label(text=", ".join(issue.channels))


CLASSES = (
    MASTER_BAKER_OT_bakeability_focus_node,
    MASTER_BAKER_PT_node_bakeability,
)


def register():
    global _DEPSGRAPH_HANDLER, _LOAD_POST_HANDLER
    if bpy is None:  # pragma: no cover
        return
    from .registration import safe_register_class

    for cls in CLASSES:
        safe_register_class(cls)

    handlers = bpy.app.handlers
    persistent = getattr(handlers, "persistent", None)
    if _DEPSGRAPH_HANDLER is None:
        _DEPSGRAPH_HANDLER = (
            persistent(_depsgraph_update_post) if callable(persistent) else _depsgraph_update_post
        )
    if _LOAD_POST_HANDLER is None:
        _LOAD_POST_HANDLER = persistent(_load_post) if callable(persistent) else _load_post
    if _DEPSGRAPH_HANDLER not in handlers.depsgraph_update_post:
        handlers.depsgraph_update_post.append(_DEPSGRAPH_HANDLER)
    if _LOAD_POST_HANDLER not in handlers.load_post:
        handlers.load_post.append(_LOAD_POST_HANDLER)
    request_update()


def unregister():
    global _DEPSGRAPH_HANDLER, _LOAD_POST_HANDLER
    if bpy is None:  # pragma: no cover
        return
    from .registration import safe_unregister_class

    handlers = bpy.app.handlers
    if _DEPSGRAPH_HANDLER is not None and _DEPSGRAPH_HANDLER in handlers.depsgraph_update_post:
        handlers.depsgraph_update_post.remove(_DEPSGRAPH_HANDLER)
    if _LOAD_POST_HANDLER is not None and _LOAD_POST_HANDLER in handlers.load_post:
        handlers.load_post.remove(_LOAD_POST_HANDLER)
    _DEPSGRAPH_HANDLER = None
    _LOAD_POST_HANDLER = None
    if bpy.app.timers.is_registered(_timer_poll):
        bpy.app.timers.unregister(_timer_poll)
    clear_cache()

    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
