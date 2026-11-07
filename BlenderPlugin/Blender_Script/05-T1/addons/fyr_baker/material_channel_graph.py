"""Locate and temporarily expose a Principled BSDF channel socket for EMIT baking.

``bpy.ops.object.bake(type="EMIT")`` can only read what is wired into the active
Material Output, so baking a PBR channel (Roughness, Metallic, Base Color, ...) means
routing that channel's source through an Emission node. Finding the source is the
hard part: production materials rarely expose a bare Principled BSDF at the top
level. Asset-library and procedural materials wrap it in one or more node groups, and
a socket that lives inside a group's node tree cannot be linked to a node in the
material's own tree.

This module walks the active surface link through any depth of node-group nesting to
find the Principled BSDF, then promotes the requested socket outward by adding a
temporary output socket to each group on the way up. The caller ends up with a real
socket in the material's own tree carrying the channel value, exactly as authored --
including procedural input, which a flat read of the group node's input default would
have thrown away. Every node, link, and interface socket created here is removed
again when the context exits.
"""

from __future__ import annotations

from contextlib import contextmanager
import itertools

from . import constants


_MAX_GROUP_DEPTH = 8
_TEMP_SOCKET_PREFIX = "__fyr_bake_"
_TEMP_SOCKET_IDS = itertools.count()

# Socket kind (``NodeSocket.type``) -> group-interface socket type.
_INTERFACE_SOCKET_TYPES = {
    "VALUE": "NodeSocketFloat",
    "RGBA": "NodeSocketColor",
    "VECTOR": "NodeSocketVector",
}

# Socket kind -> constant node used to carry an unlinked default value.
_CONSTANT_NODES = {
    "VALUE": "ShaderNodeValue",
    "RGBA": "ShaderNodeRGB",
}


def _nodes(tree) -> list:
    return list(getattr(tree, "nodes", None) or [])


def _pick_active(candidates: list):
    for node in candidates:
        if getattr(node, "is_active_output", False):
            return node
    return candidates[0] if candidates else None


def active_material_output(tree):
    return _pick_active([node for node in _nodes(tree) if getattr(node, "type", "") == "OUTPUT_MATERIAL"])


def _first_principled(tree):
    for node in _nodes(tree):
        if getattr(node, "type", "") == "BSDF_PRINCIPLED":
            return node
    return None


def _surface_source_node(tree):
    """Node driving the active Material Output's Surface, else a lone Principled."""
    output = active_material_output(tree)
    if output is not None:
        socket = output.inputs.get("Surface")
        if socket is not None and socket.links:
            return socket.links[0].from_node
    return _first_principled(tree)


def _group_output_node(tree):
    return _pick_active([node for node in _nodes(tree) if getattr(node, "type", "") == "GROUP_OUTPUT"])


def _group_inner_surface_node(group_node):
    """Node feeding the group's shader output, else a lone Principled inside it."""
    tree = getattr(group_node, "node_tree", None)
    if tree is None:
        return None
    output = _group_output_node(tree)
    if output is not None:
        for socket in output.inputs:
            if getattr(socket, "type", "") == "SHADER" and socket.links:
                return socket.links[0].from_node
    return _first_principled(tree)


def _follow_passthrough_shader(node):
    """Next surface shader through a transparent Capture / Reroute, else ``None``.

    Fyr Material Capture is a CustomGroup passthrough sitting on the Material Output
    Surface path. It must not stop Principled resolution or enter the promotion chain:
    the authored Principled lives upstream (often inside an asset-library node group),
    and treating Capture as an opaque surface made Cycles scalar EMIT bakes refuse with
    "not a Principled BSDF and could not be flattened".
    """
    if node is None:
        return None
    ntype = str(getattr(node, "type", "") or "")
    bl_id = str(getattr(node, "bl_idname", "") or "")
    if ntype == "REROUTE":
        inputs = getattr(node, "inputs", None) or ()
        if inputs and getattr(inputs[0], "links", None):
            return inputs[0].links[0].from_node
        return None
    if bl_id == constants.FYR_CAPTURE_NODE_ID:
        inputs = getattr(node, "inputs", None)
        shader_in = inputs.get("Shader") if hasattr(inputs, "get") else None
        if shader_in is None and inputs:
            shader_in = inputs[0]
        if shader_in is not None and getattr(shader_in, "links", None):
            return shader_in.links[0].from_node
        return None
    return None


def resolve_principled(material):
    """Return ``(principled_node, group_chain)`` for *material*.

    *group_chain* is the node-group instances traversed to reach the shader,
    outermost first; it is empty when the Principled sits in the material's own tree.
    Both are ``(None, [...])`` when no Principled drives the surface.

    Transparent Fyr Capture / Reroute nodes on the Surface path are peeled without
    entering *group_chain* so temporary EMIT promotion still targets the real groups.
    """
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None, []
    node = _surface_source_node(tree)
    chain: list = []
    steps = 0
    while node is not None and steps < _MAX_GROUP_DEPTH * 2:
        steps += 1
        passthrough = _follow_passthrough_shader(node)
        if passthrough is not None:
            node = passthrough
            continue
        if getattr(node, "type", "") == "GROUP" and len(chain) < _MAX_GROUP_DEPTH:
            chain.append(node)
            node = _group_inner_surface_node(node)
            continue
        break
    if node is not None and getattr(node, "type", "") == "BSDF_PRINCIPLED":
        return node, chain
    return None, chain


def can_resolve(material, socket_name: str) -> bool:
    """True when *socket_name* can be exposed as a bakeable socket for *material*."""
    principled, chain = resolve_principled(material)
    if principled is None:
        return False
    socket = principled.inputs.get(socket_name)
    if socket is None:
        return False
    kind = str(getattr(socket, "type", "") or "")
    if kind not in _INTERFACE_SOCKET_TYPES:
        return False
    if not chain:
        return True
    if kind not in _CONSTANT_NODES and not socket.links:
        return False
    return all(_group_output_node(getattr(node, "node_tree", None)) is not None for node in chain)


def _normalize_output_name(name: str) -> str:
    return "".join(ch for ch in str(name or "").casefold() if ch.isalnum())


#: Authored tangent-space normal bake outputs (Sanctus Library and similar).
NORMAL_BAKE_OUTPUT_NAMES: tuple[str, ...] = (
    "Normal Bake",
    "NormalBake",
    "normal_bake",
    "Bake Normal",
)

#: Authored scalar height / displacement bake outputs (Sanctus Library and similar).
#: Prefer these over a flat ``Normal Bake`` when the live look is true displacement.
HEIGHT_BAKE_OUTPUT_NAMES: tuple[str, ...] = (
    "Displacement Bake",
    "Height Bake",
    "Displace Bake",
    "Height",
    "Displacement",
)

#: Node types whose outputs are view- / ray-dependent and collapse under UV EMIT bake.
_VIEW_DEPENDENT_NODE_TYPES = frozenset(
    {"LAYER_WEIGHT", "FRESNEL", "LIGHT_PATH", "CAMERA"}
)


def _group_output_input_for(group_node, output_socket):
    """Group Output input inside *group_node* that feeds *output_socket*, if any."""
    tree = getattr(group_node, "node_tree", None)
    if tree is None or output_socket is None:
        return None
    gout = _group_output_node(tree)
    if gout is None:
        return None
    name = getattr(output_socket, "name", "")
    otype = str(getattr(output_socket, "type", "") or "")
    candidates = [
        socket
        for socket in getattr(gout, "inputs", []) or []
        if getattr(socket, "name", "") == name
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    for socket in candidates:
        if str(getattr(socket, "type", "") or "") == otype:
            return socket
    return candidates[0]


def _group_output_is_fed(group_node, output_socket) -> bool:
    """True when the Group Output input for *output_socket* is linked inside the group.

    Sanctus dual EEVEE/Cycles setups often expose an empty ``Displacement Bake`` on
    the EEVEE group while the real height lives as a linked VALUE ``Displacement`` on
    the Cycles group. Matching by name alone would pick the dead socket and bake black.

    If no matching Group Output input exists (out-of-sync interface / test doubles),
    treat the socket as usable rather than rejecting every match.
    """
    inner = _group_output_input_for(group_node, output_socket)
    if inner is None:
        return True
    return bool(getattr(inner, "is_linked", False))


def _group_output_matching(
    group_node,
    wanted: set[str],
    *,
    socket_type: str | None = None,
    require_fed: bool = False,
):
    """First interface output on *group_node* whose name normalizes into *wanted*.

    When *socket_type* is set (Blender ``NodeSocket.type``, e.g. ``VALUE``), only
    sockets of that type match. Sanctus groups often expose both a VECTOR
    ``Displacement`` (shader) and a VALUE ``Displacement`` (height bake).

    When *require_fed* is true, skip interface outputs whose internal Group Output
    input is unlinked (placeholder bake sockets on alternate EEVEE groups).
    """
    if group_node is None or getattr(group_node, "type", "") != "GROUP":
        return None
    for output in getattr(group_node, "outputs", []) or []:
        if _normalize_output_name(getattr(output, "name", "")) not in wanted:
            continue
        if socket_type is not None and str(getattr(output, "type", "") or "") != socket_type:
            continue
        if require_fed and not _group_output_is_fed(group_node, output):
            continue
        return output
    return None


def _surface_group_from_output(output_node):
    """GROUP driving *output_node*'s Surface, peeling Capture / Reroute passthroughs."""
    if output_node is None:
        return None
    socket = output_node.inputs.get("Surface") if hasattr(output_node, "inputs") else None
    if socket is None or not getattr(socket, "links", None):
        return None
    node = socket.links[0].from_node
    steps = 0
    while node is not None and steps < _MAX_GROUP_DEPTH * 2:
        steps += 1
        passthrough = _follow_passthrough_shader(node)
        if passthrough is not None:
            node = passthrough
            continue
        if getattr(node, "type", "") == "GROUP":
            return node
        break
    return None


def find_named_surface_output(
    material,
    candidates,
    *,
    socket_type: str | None = None,
    require_fed: bool = False,
):
    """Return a surface-path group output matching *candidates*, else ``None``.

    Walks Capture / Reroute passthroughs on Material Output Surface links, then
    matches against GROUP interface outputs. Bake helper sockets such as Sanctus
    ``Normal Bake`` / ``Color Bake`` live there — not on Principled — so
    :func:`exposed_channel_socket` cannot see them.

    Searches every Material Output's surface group, preferring ``CYCLES``-targeted
    outputs, then ``ALL``, then ``EEVEE``. Dual EEVEE/Cycles setups (Sanctus carbon
    fiber) often put bake sockets on only one of the two groups.

    When *require_fed* is true, unlinked placeholder outputs (common on Sanctus
    EEVEE companion groups) are skipped so a dead ``Displacement Bake`` cannot
    beat a linked Cycles ``Displacement`` height.
    """
    wanted = {_normalize_output_name(name) for name in (candidates or ()) if name}
    if not wanted:
        return None
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None

    outputs = [
        node
        for node in _nodes(tree)
        if getattr(node, "type", "") == "OUTPUT_MATERIAL"
    ]
    if not outputs:
        return None

    def rank(node) -> tuple:
        target = str(getattr(node, "target", "ALL") or "ALL").upper()
        active = 0 if getattr(node, "is_active_output", False) else 1
        # Prefer CYCLES (the bake engine), then ALL, then EEVEE; break ties with active.
        target_rank = {"CYCLES": 0, "ALL": 1, "EEVEE": 2}.get(target, 3)
        return (target_rank, active)

    for output_node in sorted(outputs, key=rank):
        group = _surface_group_from_output(output_node)
        found = _group_output_matching(
            group, wanted, socket_type=socket_type, require_fed=require_fed
        )
        if found is not None:
            return found
    return None


def find_normal_bake_output(material):
    """Authored tangent-space normal bake socket on *material*, if any."""
    return find_named_surface_output(
        material, NORMAL_BAKE_OUTPUT_NAMES, require_fed=True
    )


def find_height_bake_output(material):
    """Authored scalar height / displacement bake socket, if any.

    Sanctus materials that use true displacement often ship a VALUE ``Displacement``
    (or ``Displacement Bake``) alongside a VECTOR displacement shader output and a
    nearly flat ``Normal Bake``. Prefer the scalar height when converting to a
    tangent normal map so bevels / cracks match the live displaced look.

    Only **fed** (internally linked) sockets count — Sanctus EEVEE groups may expose
    an empty ``Displacement Bake`` that must not win over the Cycles height.
    """
    # Prefer explicit *Bake / Height names before the ambiguous ``Displacement``.
    # Search each name tier across outputs, but only accept fed sockets so an
    # unlinked EEVEE ``Displacement Bake`` cannot hide a linked Cycles height.
    for names in (
        ("Displacement Bake", "Height Bake", "Displace Bake", "Height"),
        ("Displacement",),
    ):
        found = find_named_surface_output(
            material, names, socket_type="VALUE", require_fed=True
        )
        if found is not None:
            return found
    return None


def named_output_graph_has_types(material, candidates, node_types) -> bool:
    """True when the graph feeding a named surface output contains any of *node_types*."""
    wanted_types = {str(t) for t in (node_types or ()) if t}
    if not wanted_types:
        return False
    sock = find_named_surface_output(material, candidates)
    if sock is None:
        return False
    group = None
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return False
    for node in _nodes(tree):
        if getattr(node, "type", "") != "GROUP":
            continue
        for output in getattr(node, "outputs", []) or []:
            if output is sock or (
                getattr(output, "as_pointer", None)
                and output.as_pointer() == sock.as_pointer()
            ):
                group = node
                break
        if group is not None:
            break
    if group is None or getattr(group, "node_tree", None) is None:
        return False
    gout = _group_output_node(group.node_tree)
    if gout is None:
        return False
    start = gout.inputs.get(getattr(sock, "name", ""))
    if start is None or not start.links:
        return False
    from collections import deque

    queue = deque([start])
    seen: set[int] = set()
    while queue and len(seen) < 200:
        socket = queue.popleft()
        if socket is None or not getattr(socket, "links", None):
            continue
        node = socket.links[0].from_node
        key = node.as_pointer() if hasattr(node, "as_pointer") else id(node)
        if key in seen:
            continue
        seen.add(key)
        if str(getattr(node, "type", "") or "") in wanted_types:
            return True
        for inp in getattr(node, "inputs", []) or []:
            if getattr(inp, "links", None):
                queue.append(inp)
        if getattr(node, "type", "") == "GROUP" and getattr(node, "node_tree", None):
            fs = socket.links[0].from_socket.name
            nested = _group_output_node(node.node_tree)
            if nested is not None and fs in nested.inputs:
                queue.append(nested.inputs[fs])
    return False


def named_output_is_view_dependent(material, candidates) -> bool:
    """True when a named bake output is driven by Facing / Fresnel / camera rays."""
    return named_output_graph_has_types(material, candidates, _VIEW_DEPENDENT_NODE_TYPES)


def _new_group_output_socket(tree, name: str, kind: str):
    socket_type = _INTERFACE_SOCKET_TYPES.get(kind)
    interface = getattr(tree, "interface", None)
    if socket_type is None or interface is None or not hasattr(interface, "new_socket"):
        return None
    try:
        return interface.new_socket(name=name, in_out="OUTPUT", socket_type=socket_type)
    except Exception:
        return None


@contextmanager
def exposed_channel_socket(material, socket_name: str):
    """Yield a socket in *material*'s node tree carrying the channel's value.

    Yields ``None`` when the graph cannot be resolved, so callers can fall back to a
    different bake strategy instead of silently baking black.
    """
    principled, chain = resolve_principled(material)
    target_input = principled.inputs.get(socket_name) if principled is not None else None
    if target_input is None:
        yield None
        return

    kind = str(getattr(target_input, "type", "") or "")
    created_nodes: list[tuple] = []
    created_links: list[tuple] = []
    created_sockets: list[tuple] = []

    def constant_source(tree, socket):
        """A constant node carrying *socket*'s unlinked default value."""
        node_type = _CONSTANT_NODES.get(kind)
        if node_type is None:
            return None
        node = tree.nodes.new(node_type)
        created_nodes.append((tree, node))
        try:
            value = socket.default_value
            if node_type == "ShaderNodeRGB":
                components = list(value)
                node.outputs[0].default_value = (
                    components[0],
                    components[1],
                    components[2],
                    components[3] if len(components) > 3 else 1.0,
                )
            else:
                node.outputs[0].default_value = float(value)
        except Exception:
            pass
        return node.outputs[0]

    try:
        inner_tree = getattr(chain[-1], "node_tree", None) if chain else getattr(material, "node_tree", None)
        if inner_tree is None:
            yield None
            return
        if target_input.links:
            socket = target_input.links[0].from_socket
        else:
            socket = constant_source(inner_tree, target_input)
        if socket is None:
            yield None
            return

        # Promote the socket out of each enclosing group, innermost first, so the
        # material's own tree finally holds a socket the Emission node can read.
        for group_node in reversed(chain):
            tree = getattr(group_node, "node_tree", None)
            output_node = _group_output_node(tree)
            if output_node is None:
                yield None
                return
            name = f"{_TEMP_SOCKET_PREFIX}{socket_name}_{next(_TEMP_SOCKET_IDS)}".replace(" ", "_")
            interface_socket = _new_group_output_socket(tree, name, kind)
            if interface_socket is None:
                yield None
                return
            created_sockets.append((tree, interface_socket))
            promoted_input = output_node.inputs.get(name)
            promoted_output = group_node.outputs.get(name)
            if promoted_input is None or promoted_output is None:
                yield None
                return
            created_links.append((tree, tree.links.new(socket, promoted_input)))
            socket = promoted_output

        yield socket
    finally:
        for tree, link in reversed(created_links):
            try:
                tree.links.remove(link)
            except Exception:
                pass
        for tree, node in reversed(created_nodes):
            try:
                tree.nodes.remove(node)
            except Exception:
                pass
        for tree, interface_socket in reversed(created_sockets):
            try:
                tree.interface.remove(interface_socket)
            except Exception:
                pass
