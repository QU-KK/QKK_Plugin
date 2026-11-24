"""Typed material-graph front end for procedural capture.

Extracts PBR channel expressions from Principled / Mix / Add / Group graphs,
detects view-dependent dependencies, and reports approximation state.
Native Material IR evaluation is Phase 4; this module feeds sync + Cycles prep.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import constants
from . import material_channel_graph

NODE_COVERAGE_NATIVE = "native"
NODE_COVERAGE_CYCLES_VALID = "cycles_valid"
NODE_COVERAGE_VIEW_DEPENDENT = "view_dependent"
NODE_COVERAGE_UNSUPPORTED_ERROR = "unsupported_error"

_VIEW_DEPENDENT_TYPES = frozenset({
    "CAMERA",
    "UVALONGSTROKE",
})
# Parametric and Backfacing left this set 2026-08-12: both are native and
# Cycles-verified (Parametric = hit barycentrics measured to half-float ULP;
# Backfacing = constant 0 in a bake, measured with normals flipped and not).
_VIEW_DEPENDENT_GEOMETRY_OUTPUTS = frozenset({
    "Incoming",
    "Incoming Vector",
})
_VIEW_DEPENDENT_LAYER_WEIGHT = frozenset({"Facing", "Fresnel"})
_MAX_DEPTH = 24

_NATIVE_NODE_TYPES = frozenset({
    "REROUTE",
    "UVMAP",
    "TEX_COORD",
    "MAPPING",
    "TEX_IMAGE",
    "RGB",
    "VALUE",
    # Constants in a bake (Is Camera Ray 1, Ray Length 1, rest 0), measured vs Cycles.
    "LIGHT_PATH",
    "INVERT",
    "MIX",
    "MIX_RGB",
    "MIXRGB",
    "MATH",
    "VALTORGB",
    "SEPRGB",
    "SEPARATE_COLOR",
    "SEP_COLOR",
    "RGBTOBW",
    "SEPXYZ",
    "SEPARATE_XYZ",
    "COMBXYZ",
    "COMBINE_XYZ",
    "COMBINE_COLOR",
    "COMBCLR",
    "HUE_SAT",
    "HUESAT",
    "HUE_SATURATION",
    "BRIGHTCONTRAST",
    "BRIGHTNESSCONTRAST",
    "GAMMA",
    "VECT_MATH",
    "VECTOR_MATH",
    "MAP_RANGE",
    "CLAMP",
    "TEX_NOISE",
    "TEX_VORONOI",
    "TEX_WHITE_NOISE",
    "TEX_MAGIC",
    "TEX_WAVE",
    "TEX_GRADIENT",
    "TEX_CHECKER",
    "TEX_BRICK",
    "BSDF_PRINCIPLED",
    "EMISSION",
    "MIX_SHADER",
    "ADD_SHADER",
    "BSDF_DIFFUSE",
    "BSDF_GLOSSY",
    "BSDF_GLASS",
    "BSDF_REFRACTION",
    "BSDF_TRANSPARENT",
    "BSDF_TRANSLUCENT",
    "DISPLACEMENT",
    # Landed native and Cycles-verified across 2026-08-09..12 (see
    # docs/MIR_VISUAL_QA.md for the judged A/B sheets). Per-graph cases the
    # compiler cannot express statically (linked Radial Tiling Sides, AO
    # only_local, Raycast attribute outputs, non-constant Attribute lookups)
    # still fall over to Cycles at compile time -- classification here is the
    # UI-level default, the compiler stays the routing authority.
    "NEW_GEOMETRY",
    "OBJECT_INFO",
    "ATTRIBUTE",
    "BUMP",
    "BEVEL",
    "AMBIENT_OCCLUSION",
    "RAYCAST",
    "TEX_GABOR",
    "CURVE_FLOAT",
    "CURVE_RGB",
    "CURVE_VEC",
    # Blender reports the Vector Rotate node as "VECTOR_ROTATE" (checked live on 5.1;
    # its siblings really are VECT_TRANSFORM / CURVE_VEC, which is what made the typo
    # look plausible). Only "VECT_ROTATE" was listed, so a material using Vector Rotate
    # was classified as non-native and routed to Cycles although material_ir compiles it
    # natively - the IR dispatches on "VECTOR_ROTATE". Both spellings are listed, the
    # same hedge material_ir keeps for the Vector Math node.
    "VECTOR_ROTATE",
    "VECT_ROTATE",
    "VECT_TRANSFORM",
    "BLACKBODY",
    "WAVELENGTH",
    "RADIAL_TILING",
})

_CYCLES_VALID_NODE_TYPES = frozenset({
    "GROUP",
    "GROUP_INPUT",
    "GROUP_OUTPUT",
    "VERTEX_COLOR",
    "POINT_INFO",
    "NORMAL",
    "TANGENT",
    "NORMAL_MAP",
    "VECTOR_DISPLACEMENT",
    "TEX_MUSGRAVE",
    "SQUEEZE",
    "BSDF_HAIR",
    "BSDF_HAIR_PRINCIPLED",
    "BSDF_TOON",
    "BSDF_VELVET",
    "SUBSURFACE_SCATTERING",
    "VOLUME_ABSORPTION",
    "VOLUME_SCATTER",
    "TEX_ENVIRONMENT",
    "TEX_SKY",
})

_VIEW_DEPENDENT_NODE_TYPES = _VIEW_DEPENDENT_TYPES | frozenset({
    "SHADER_TO_RGB",
    "LAYER_WEIGHT",
    # Fresnel is view-dependent in exactly the same way Layer Weight is -- both are a
    # function of the angle between the shading normal and the incoming ray -- but it
    # was missing here, so the panel called it "bakes through Cycles" while the bake
    # produced a flat constant: at normal incidence Fresnel is 0.0337 for the default
    # IOR, and that single value is what the whole map got. Layer Weight, the same
    # situation, was correctly flagged Unbakeable.
    # See MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P3.
    "FRESNEL",
})


def node_type_is_view_dependent(node_type: str) -> bool:
    """Whether a node type can never be baked, only rendered.

    The bake has no camera and no incoming ray, so these have no answer and Cycles
    returns whatever normal incidence gives -- a single constant for the whole map.
    Callers use this to WARN rather than to route: the fallback still runs, it just
    should not do so silently. See MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P4.
    """
    return str(node_type or "").strip().upper() in _VIEW_DEPENDENT_NODE_TYPES


@dataclass
class ChannelExpression:
    """Resolved channel source for one material."""

    channel_key: str
    binding_key: str
    linked: bool = False
    constant: Any = None
    approximate: bool = False
    invalid: bool = False
    view_dependent: bool = False
    message: str = ""
    provenance: str = ""


@dataclass
class MaterialExtraction:
    material_name: str
    capture_mode: str = ""
    capture_id: str = ""
    channels: dict[str, ChannelExpression] = field(default_factory=dict)
    custom_outputs: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NodeCoverage:
    node_type: str
    output_name: str = ""
    classification: str = NODE_COVERAGE_CYCLES_VALID
    reason: str = ""


def classify_node_output(node_or_type, output_name: str = "") -> NodeCoverage:
    """Classify one Blender shader-node output for material capture routing."""
    if isinstance(node_or_type, str):
        ntype = node_or_type
    else:
        ntype = str(getattr(node_or_type, "type", "") or "")
    ntype = str(ntype or "").strip().upper()
    out = str(output_name or "")
    if ntype in _VIEW_DEPENDENT_NODE_TYPES:
        if ntype == "LAYER_WEIGHT" and out not in _VIEW_DEPENDENT_LAYER_WEIGHT:
            return NodeCoverage(ntype, out, NODE_COVERAGE_CYCLES_VALID, "Layer Weight output is not view-facing")
        return NodeCoverage(ntype, out, NODE_COVERAGE_VIEW_DEPENDENT, "Output depends on camera/view or rendered lighting")
    if ntype == "NEW_GEOMETRY" and out in _VIEW_DEPENDENT_GEOMETRY_OUTPUTS:
        return NodeCoverage(ntype, out, NODE_COVERAGE_VIEW_DEPENDENT, "Geometry output depends on the incoming view ray")
    if ntype in _NATIVE_NODE_TYPES:
        return NodeCoverage(ntype, out, NODE_COVERAGE_NATIVE, "Material IR native candidate")
    if ntype in _CYCLES_VALID_NODE_TYPES:
        return NodeCoverage(ntype, out, NODE_COVERAGE_CYCLES_VALID, "Valid through Cycles compatibility path")
    if not ntype:
        return NodeCoverage(ntype, out, NODE_COVERAGE_UNSUPPORTED_ERROR, "Missing node type")
    return NodeCoverage(ntype, out, NODE_COVERAGE_CYCLES_VALID, "Unlisted Blender shader node uses Cycles until classified")


def _socket_default(socket):
    try:
        value = socket.default_value
        if hasattr(value, "__len__"):
            return tuple(float(v) for v in value)
        return float(value)
    except Exception:
        return None


def _values_close(a, b, eps: float = 1e-4) -> bool:
    if a is None or b is None:
        return False
    if hasattr(a, "__len__") and hasattr(b, "__len__"):
        if len(a) != len(b):
            return False
        return all(abs(float(x) - float(y)) <= eps for x, y in zip(a, b))
    try:
        return abs(float(a) - float(b)) <= eps
    except Exception:
        return False


def _is_meaningful(channel_key: str, linked: bool, constant) -> bool:
    if channel_key in {"BASE_COLOR", "ROUGHNESS"}:
        return True
    # Normal / Height only matter when actually driven.
    if channel_key in {"NORMAL", "HEIGHT"}:
        return linked
    if linked:
        return True
    neutral = constants.CAPTURE_CHANNEL_NEUTRAL.get(channel_key)
    if neutral is None:
        return linked
    return not _values_close(constant, neutral)


def _follow_reroute(socket):
    node = getattr(socket, "node", None)
    while node is not None and getattr(node, "type", "") == "REROUTE":
        if not node.inputs or not node.inputs[0].links:
            return None
        socket = node.inputs[0].links[0].from_socket
        node = getattr(socket, "node", None)
    return socket


def _collect_dependencies(socket, *, depth: int = 0, seen: set | None = None) -> tuple[bool, bool]:
    """Return (view_dependent, has_shader_to_rgb) for the expression feeding *socket*."""
    if socket is None or depth > _MAX_DEPTH:
        return False, False
    if seen is None:
        seen = set()
    if not getattr(socket, "links", None):
        return False, False
    link = socket.links[0]
    from_socket = _follow_reroute(link.from_socket)
    if from_socket is None:
        return False, False
    node = from_socket.node
    key = (node.as_pointer(), from_socket.identifier if hasattr(from_socket, "identifier") else from_socket.name)
    if key in seen:
        return False, False
    seen.add(key)

    ntype = str(getattr(node, "type", "") or "")
    view = False
    shader_to_rgb = ntype == "SHADER_TO_RGB"
    coverage = classify_node_output(ntype, str(getattr(from_socket, "name", "") or ""))
    if coverage.classification == NODE_COVERAGE_VIEW_DEPENDENT:
        view = True
    elif ntype == "FRESNEL":
        # Fresnel IOR itself is not camera-facing; Layer Weight Facing is.
        pass

    for input_socket in getattr(node, "inputs", []) or []:
        child_view, child_s2r = _collect_dependencies(input_socket, depth=depth + 1, seen=seen)
        view = view or child_view
        shader_to_rgb = shader_to_rgb or child_s2r
    return view, shader_to_rgb


def _principled_channel(node, channel_key: str) -> ChannelExpression:
    binding_key = next(
        (b for key, _label, _kind, b in constants.CAPTURE_COMPACT_CHANNELS if key == channel_key),
        f"STANDARD:{channel_key}",
    )
    if channel_key == "HEIGHT":
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            linked=False,
            constant=0.0,
            message="Height comes from Material Output Displacement or an explicit override",
        )

    socket_name = constants.CAPTURE_CHANNEL_PRINCIPLED_SOCKET.get(channel_key)
    socket = node.inputs.get(socket_name) if socket_name else None
    if socket is None:
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            invalid=True,
            message=f"Missing Principled socket '{socket_name}'",
        )
    linked = bool(socket.links)
    constant = None if linked else _socket_default(socket)
    if channel_key == "EMISSION" and not linked:
        # Blender's Principled default Emission Color is white with Strength 0.
        # Color alone is not meaningful unless strength is raised or the socket is linked.
        strength = node.inputs.get("Emission Strength")
        strength_value = 0.0
        if strength is not None and not strength.links:
            try:
                strength_value = float(strength.default_value)
            except Exception:
                strength_value = 0.0
        elif strength is not None and strength.links:
            linked = True
        if strength_value <= 1e-6 and not linked:
            constant = constants.CAPTURE_CHANNEL_NEUTRAL["EMISSION"]
    view_dep = False
    if linked:
        view_dep, s2r = _collect_dependencies(socket)
        if s2r:
            view_dep = True
    return ChannelExpression(
        channel_key=channel_key,
        binding_key=binding_key,
        linked=linked,
        constant=constant,
        view_dependent=view_dep,
        invalid=view_dep,
        message="View-dependent dependency" if view_dep else "",
        provenance=getattr(node, "name", "") or "Principled BSDF",
    )


def _blend_constants(a, b, factor: float):
    if a is None:
        return b
    if b is None:
        return a
    if hasattr(a, "__len__") and hasattr(b, "__len__"):
        return tuple((1.0 - factor) * float(x) + factor * float(y) for x, y in zip(a, b))
    return (1.0 - factor) * float(a) + factor * float(b)


def _extract_from_shader(node, channel_key: str, *, depth: int = 0) -> ChannelExpression:
    binding_key = next(
        (b for key, _label, _kind, b in constants.CAPTURE_COMPACT_CHANNELS if key == channel_key),
        f"STANDARD:{channel_key}",
    )
    empty = ChannelExpression(channel_key=channel_key, binding_key=binding_key, invalid=True, message="Unsupported shader")
    if node is None or depth > _MAX_DEPTH:
        return empty

    ntype = str(getattr(node, "type", "") or "")
    if ntype == "REROUTE" and node.inputs and node.inputs[0].links:
        return _extract_from_shader(node.inputs[0].links[0].from_node, channel_key, depth=depth + 1)

    # Capture is a CustomGroup passthrough on the Surface path; peel it the same way
    # material_channel_graph.resolve_principled does so extraction still reaches the
    # authored Principled when Capture sits between Output and an asset group.
    bl_id = str(getattr(node, "bl_idname", "") or "")
    if bl_id == constants.FYR_CAPTURE_NODE_ID:
        inputs = getattr(node, "inputs", None)
        shader_in = inputs.get("Shader") if hasattr(inputs, "get") else None
        if shader_in is None and inputs:
            shader_in = inputs[0]
        if shader_in is not None and shader_in.links:
            return _extract_from_shader(
                shader_in.links[0].from_node, channel_key, depth=depth + 1
            )
        return empty

    if ntype == "GROUP":
        inner = material_channel_graph._group_inner_surface_node(node)
        return _extract_from_shader(inner, channel_key, depth=depth + 1)

    if ntype == "BSDF_PRINCIPLED":
        return _principled_channel(node, channel_key)

    if ntype == "EMISSION":
        if channel_key == "EMISSION":
            color = node.inputs.get("Color")
            linked = bool(color and color.links)
            return ChannelExpression(
                channel_key=channel_key,
                binding_key=binding_key,
                linked=linked,
                constant=None if linked else (_socket_default(color) if color else (0, 0, 0, 1)),
                provenance="Emission",
            )
        if channel_key in {"BASE_COLOR", "ROUGHNESS", "METALNESS", "OPACITY"}:
            # Emission-only surfaces: albedo black, rough 0.5, metal 0, opaque.
            defaults = {
                "BASE_COLOR": (0.0, 0.0, 0.0, 1.0),
                "ROUGHNESS": 0.5,
                "METALNESS": 0.0,
                "OPACITY": 1.0,
            }
            return ChannelExpression(
                channel_key=channel_key,
                binding_key=binding_key,
                constant=defaults[channel_key],
                approximate=True,
                message="Emission closure approximated",
                provenance="Emission",
            )
        return ChannelExpression(channel_key=channel_key, binding_key=binding_key, constant=constants.CAPTURE_CHANNEL_NEUTRAL.get(channel_key))

    if ntype in {"BSDF_DIFFUSE", "BSDF_GLOSSY", "BSDF_GLASS", "BSDF_REFRACTION", "BSDF_TRANSPARENT", "BSDF_TRANSLUCENT"}:
        return _approximate_closure(node, ntype, channel_key, binding_key)

    if ntype == "MIX_SHADER":
        fac_socket = node.inputs.get("Fac")
        factor = 0.5
        if fac_socket is not None and not fac_socket.links:
            try:
                factor = float(fac_socket.default_value)
            except Exception:
                factor = 0.5
        shader_a = node.inputs[1].links[0].from_node if len(node.inputs) > 1 and node.inputs[1].links else None
        shader_b = node.inputs[2].links[0].from_node if len(node.inputs) > 2 and node.inputs[2].links else None
        expr_a = _extract_from_shader(shader_a, channel_key, depth=depth + 1)
        expr_b = _extract_from_shader(shader_b, channel_key, depth=depth + 1)
        linked = expr_a.linked or expr_b.linked or bool(fac_socket and fac_socket.links)
        approx = expr_a.approximate or expr_b.approximate
        view = expr_a.view_dependent or expr_b.view_dependent
        constant = None
        if not linked:
            constant = _blend_constants(expr_a.constant, expr_b.constant, factor)
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            linked=linked,
            constant=constant,
            approximate=approx,
            view_dependent=view,
            invalid=view,
            message="Mix Shader blend" if not view else "View-dependent Mix Shader branch",
            provenance="Mix Shader",
        )

    if ntype == "ADD_SHADER":
        shader_a = node.inputs[0].links[0].from_node if node.inputs and node.inputs[0].links else None
        shader_b = node.inputs[1].links[0].from_node if len(node.inputs) > 1 and node.inputs[1].links else None
        expr_a = _extract_from_shader(shader_a, channel_key, depth=depth + 1)
        expr_b = _extract_from_shader(shader_b, channel_key, depth=depth + 1)
        linked = expr_a.linked or expr_b.linked
        if channel_key == "EMISSION":
            # Additive emission.
            constant = None
            if not linked:
                a = expr_a.constant or (0, 0, 0, 1)
                b = expr_b.constant or (0, 0, 0, 1)
                if hasattr(a, "__len__") and hasattr(b, "__len__"):
                    constant = tuple(float(x) + float(y) for x, y in zip(a, b))
            return ChannelExpression(
                channel_key=channel_key,
                binding_key=binding_key,
                linked=linked,
                constant=constant,
                approximate=True,
                message="Add Shader emission is additive",
                provenance="Add Shader",
            )
        if channel_key == "OPACITY":
            constant = None
            if not linked:
                a = float(expr_a.constant if expr_a.constant is not None else 1.0)
                b = float(expr_b.constant if expr_b.constant is not None else 1.0)
                constant = 1.0 - (1.0 - a) * (1.0 - b)
            return ChannelExpression(
                channel_key=channel_key,
                binding_key=binding_key,
                linked=linked,
                constant=constant,
                approximate=True,
                message="Add Shader opacity uses coverage combine",
                provenance="Add Shader",
            )
        # Equal-weight blend for material parameters.
        constant = None if linked else _blend_constants(expr_a.constant, expr_b.constant, 0.5)
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            linked=linked,
            constant=constant,
            approximate=True,
            message="Add Shader uses equal-weight parameter blend",
            provenance="Add Shader",
        )

    mapped = _mapped_closure_channel(node, ntype, channel_key, binding_key)
    if mapped is not None:
        return mapped
    return empty


def _mapped_closure_channel(node, ntype: str, channel_key: str, binding_key: str):
    """Flatten a closure the NATIVE route already models, using its own table.

    Fyr's Material IR carries `_CLOSURE_CHANNEL_SOURCES`: what each non-Principled
    closure contributes to a PBR channel, as either an input socket name or a
    constant. Reading that same table here keeps the two routes from drifting into
    different answers for the same material, and gives the Cycles emit path a value
    for closures it otherwise refuses outright (Metallic BSDF, Sheen, Toon, SSS,
    Hair) instead of failing the bake. A channel absent from a closure's entry
    contributes nothing, matching the IR's `_shader_channel_neutral`.
    """
    from . import material_ir

    sources = material_ir._CLOSURE_CHANNEL_SOURCES.get(ntype)  # noqa: SLF001
    if sources is None:
        return None
    source = sources.get(channel_key)
    if source is None:
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            constant=constants.CAPTURE_CHANNEL_NEUTRAL.get(channel_key),
            approximate=True,
            message=f"{ntype} does not carry {channel_key}",
            provenance=ntype,
        )
    if isinstance(source, str):
        socket = node.inputs.get(source)
        linked = bool(socket and socket.links)
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            linked=linked,
            constant=None if linked else (_socket_default(socket) if socket else None),
            approximate=True,
            provenance=ntype,
        )
    return ChannelExpression(
        channel_key=channel_key,
        binding_key=binding_key,
        constant=float(source),
        approximate=True,
        provenance=ntype,
    )


def _approximate_closure(node, ntype: str, channel_key: str, binding_key: str) -> ChannelExpression:
    color_socket = node.inputs.get("Color")
    rough_socket = node.inputs.get("Roughness")
    linked_color = bool(color_socket and color_socket.links)
    if channel_key == "BASE_COLOR":
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            linked=linked_color,
            constant=None if linked_color else (_socket_default(color_socket) if color_socket else (0.8, 0.8, 0.8, 1)),
            approximate=True,
            message=f"{ntype} approximated to Base Color",
            provenance=ntype,
        )
    if channel_key == "ROUGHNESS":
        linked = bool(rough_socket and rough_socket.links)
        default = 0.0 if ntype in {"BSDF_GLASS", "BSDF_REFRACTION"} else 0.5
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            linked=linked,
            constant=None if linked else (_socket_default(rough_socket) if rough_socket else default),
            approximate=True,
            provenance=ntype,
        )
    if channel_key == "METALNESS":
        metal = 1.0 if ntype == "BSDF_GLOSSY" else 0.0
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            constant=metal,
            approximate=True,
            provenance=ntype,
        )
    if channel_key == "OPACITY":
        opacity = 0.0 if ntype == "BSDF_TRANSPARENT" else 1.0
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            constant=opacity,
            approximate=True,
            provenance=ntype,
        )
    if channel_key == "TRANSMISSION":
        transmission = 1.0 if ntype in {"BSDF_GLASS", "BSDF_REFRACTION"} else 0.0
        return ChannelExpression(
            channel_key=channel_key,
            binding_key=binding_key,
            constant=transmission,
            approximate=True,
            provenance=ntype,
        )
    return ChannelExpression(
        channel_key=channel_key,
        binding_key=binding_key,
        constant=constants.CAPTURE_CHANNEL_NEUTRAL.get(channel_key),
        approximate=True,
        provenance=ntype,
    )


def _displacement_height(material) -> ChannelExpression | None:
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None
    output = material_channel_graph.active_material_output(tree)
    if output is None:
        return None
    disp = output.inputs.get("Displacement")
    if disp is None or not disp.links:
        return None
    from_node = disp.links[0].from_node
    # Displacement node Height input, or direct scalar.
    if getattr(from_node, "type", "") == "DISPLACEMENT":
        height = from_node.inputs.get("Height")
        linked = bool(height and height.links)
        return ChannelExpression(
            channel_key="HEIGHT",
            binding_key=constants.CAPTURE_BINDING_HEIGHT,
            linked=linked,
            constant=None if linked else (_socket_default(height) if height else 0.0),
            provenance="Displacement",
        )
    return ChannelExpression(
        channel_key="HEIGHT",
        binding_key=constants.CAPTURE_BINDING_HEIGHT,
        linked=True,
        provenance=getattr(from_node, "name", "Displacement"),
    )


def extract_material(material, *, profile: str = constants.MATERIAL_PROFILE_STANDARD) -> MaterialExtraction:
    """Extract meaningful channel expressions and custom outputs for *material*."""
    from . import material_capture_nodes

    result = MaterialExtraction(material_name=str(getattr(material, "name", "") or ""))
    tree = getattr(material, "node_tree", None)
    if tree is None or not getattr(material, "use_nodes", False):
        result.warnings.append("Material has no node tree")
        return result

    capture = material_capture_nodes.find_active_capture(material)
    shader_node = None
    if capture is not None:
        result.capture_mode = str(getattr(capture, "capture_mode", "") or "")
        result.capture_id = str(getattr(capture, "identifier", "") or "")
        shader_in = capture.inputs.get("Shader") or (capture.inputs[0] if capture.inputs else None)
        if shader_in is not None and shader_in.links:
            shader_node = shader_in.links[0].from_node
        # Explicit / Hybrid overrides take precedence when enabled.
        mode = result.capture_mode
        for key, label, _kind, binding in constants.CAPTURE_COMPACT_CHANNELS:
            if mode in {constants.CAPTURE_MODE_EXPLICIT, constants.CAPTURE_MODE_HYBRID} and capture._override_enabled(key):
                socket = capture.inputs.get(label)
                linked = bool(socket and socket.links)
                view = False
                if linked:
                    view, s2r = _collect_dependencies(socket)
                    view = view or s2r
                result.channels[key] = ChannelExpression(
                    channel_key=key,
                    binding_key=binding,
                    linked=linked or True,  # override toggle alone is intentional
                    constant=None if linked else (_socket_default(socket) if socket else None),
                    view_dependent=view,
                    invalid=view,
                    message="Explicit override" if not view else "View-dependent override",
                    provenance=f"Capture:{label}",
                )
        if mode == constants.CAPTURE_MODE_EXPLICIT:
            # Only overrides; skip automatic extraction.
            _collect_customs(material, result)
            return result
    else:
        # No capture node: still allow extraction from surface for sync when
        # the user has not inserted nodes yet (manual material rows only).
        output = material_channel_graph.active_material_output(tree)
        if output is not None:
            surface = output.inputs.get("Surface")
            if surface is not None and surface.links:
                shader_node = surface.links[0].from_node

    if shader_node is not None:
        for key, _label, _kind, binding in constants.CAPTURE_COMPACT_CHANNELS:
            if key in result.channels:
                continue
            if key == "HEIGHT":
                height = _displacement_height(material)
                if height is not None:
                    result.channels[key] = height
                continue
            expr = _extract_from_shader(shader_node, key)
            result.channels[key] = expr

    # Filter to meaningful outputs for automatic discovery.
    meaningful = {}
    for key, expr in result.channels.items():
        if expr.invalid and expr.view_dependent:
            meaningful[key] = expr
            continue
        if _is_meaningful(key, expr.linked, expr.constant):
            meaningful[key] = expr
    # Extended profile currently shares the compact set; coat/sheen land with Phase 4/extended UI.
    _ = profile
    result.channels = meaningful
    _collect_customs(material, result)
    return result


def _collect_customs(material, result: MaterialExtraction) -> None:
    from . import material_capture_nodes

    seen_names: dict[str, str] = {}
    for node in material_capture_nodes.iter_custom_outputs(material):
        name = str(getattr(node, "output_name", "") or "").strip() or "Custom"
        normalized = name.casefold()
        data_type = str(getattr(node, "data_type", "") or constants.MATERIAL_DATA_COLOR)
        node_id = str(getattr(node, "identifier", "") or "")
        if normalized in seen_names and seen_names[normalized] != data_type:
            result.warnings.append(f"Custom output '{name}' has conflicting types in {result.material_name}")
            continue
        if normalized in seen_names:
            result.warnings.append(f"Duplicate custom output '{name}' in {result.material_name}")
            continue
        seen_names[normalized] = data_type
        input_socket = node.inputs[0] if node.inputs else None
        linked = bool(input_socket and input_socket.links)
        view = False
        if linked:
            view, s2r = _collect_dependencies(input_socket)
            view = view or s2r
        result.custom_outputs.append({
            "name": name,
            "normalized": normalized,
            "binding_key": f"CUSTOM:{normalized}",
            "data_type": data_type,
            "vector_encoding": str(getattr(node, "vector_encoding", "") or constants.MATERIAL_VECTOR_ENCODE_UNIT),
            "node_id": node_id,
            "linked": linked,
            "view_dependent": view,
            "invalid": view or not linked,
        })


def meaningful_bindings_for_materials(materials, *, profile: str) -> dict[str, dict]:
    """Aggregate bindings across materials for map-stack sync.

    Returns binding_key -> {
      origin, channel_key?, display_name, data_type, coverage, approximate, invalid, messages, node_ids
    }
    """
    totals = len(list(materials))
    materials = list(materials)
    if totals == 0:
        return {}

    aggregated: dict[str, dict] = {}
    for material in materials:
        extraction = extract_material(material, profile=profile)
        for key, expr in extraction.channels.items():
            entry = aggregated.setdefault(expr.binding_key, {
                "origin": constants.MATERIAL_ORIGIN_CAPTURE,
                "channel_key": key,
                "display_name": next(
                    (label for k, label, _kind, _b in constants.CAPTURE_COMPACT_CHANNELS if k == key),
                    key.title(),
                ),
                "data_type": constants.MATERIAL_DATA_COLOR if key in {"BASE_COLOR", "EMISSION"} else (
                    constants.MATERIAL_DATA_VECTOR if key == "NORMAL" else constants.MATERIAL_DATA_VALUE
                ),
                "present": 0,
                "approximate": False,
                "invalid": False,
                "view_dependent": False,
                "messages": [],
                "node_ids": [],
            })
            entry["present"] += 1
            entry["approximate"] = entry["approximate"] or expr.approximate
            entry["invalid"] = entry["invalid"] or expr.invalid
            entry["view_dependent"] = entry["view_dependent"] or expr.view_dependent
            if expr.message:
                entry["messages"].append(f"{extraction.material_name}: {expr.message}")
            if extraction.capture_id:
                entry["node_ids"].append(extraction.capture_id)

        for custom in extraction.custom_outputs:
            entry = aggregated.setdefault(custom["binding_key"], {
                "origin": constants.MATERIAL_ORIGIN_CUSTOM,
                "channel_key": "",
                "display_name": custom["name"],
                "data_type": custom["data_type"],
                "vector_encoding": custom["vector_encoding"],
                "present": 0,
                "approximate": False,
                "invalid": False,
                "view_dependent": False,
                "messages": [],
                "node_ids": [],
            })
            # Prefer first spelling as display name.
            entry["present"] += 1
            entry["invalid"] = entry["invalid"] or custom["invalid"]
            entry["view_dependent"] = entry["view_dependent"] or custom["view_dependent"]
            if custom["node_id"]:
                entry["node_ids"].append(custom["node_id"])

    for binding_key, entry in aggregated.items():
        present = int(entry["present"])
        if entry["invalid"] and entry["view_dependent"]:
            entry["resolve"] = constants.MATERIAL_RESOLVE_INVALID
        elif present <= 0:
            entry["resolve"] = constants.MATERIAL_RESOLVE_MISSING
        elif present < totals and entry["origin"] == constants.MATERIAL_ORIGIN_CAPTURE:
            entry["resolve"] = constants.MATERIAL_RESOLVE_PARTIAL
        elif entry["approximate"]:
            entry["resolve"] = constants.MATERIAL_RESOLVE_APPROXIMATE
        else:
            entry["resolve"] = constants.MATERIAL_RESOLVE_RESOLVED
        entry["coverage"] = present / float(totals)
    return aggregated
