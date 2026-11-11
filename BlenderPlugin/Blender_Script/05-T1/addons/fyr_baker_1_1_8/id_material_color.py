"""The one colour rule for the ID map's "Material Color" source.

Native (Fyr) and Cycles recovery must paint a material the same colour, so both call
:func:`material_id_color`. The rule, in order:

1. the material's Viewport Display colour, when it differs from Blender's default
   (0.8, 0.8, 0.8) -- an artist who set it did so on purpose;
2. otherwise the Principled BSDF Base Color, when that socket is unlinked and not the
   same default grey -- the colour most materials are actually authored with;
3. otherwise a colour hashed from the material NAME with the backend's ID hash
   (``gpu_projection_hash_color``: 32-bit FNV-1a over the UTF-8 bytes, R/G/B from the
   low three bytes), so two untouched materials never collapse to one grey and the
   colour is identical across sessions and machines.

Pure Python over duck-typed material objects: no bpy import, so the rule is unit
testable without Blender.
"""

from __future__ import annotations

#: Blender's default for both Material.diffuse_color and Principled BSDF Base Color.
DEFAULT_MATERIAL_GREY = (0.8, 0.8, 0.8)
#: Stored colours round-trip through float32, so compare with a small tolerance.
_DEFAULT_TOLERANCE = 1.0e-4


def fnv1a_hash_color(value: str) -> tuple[float, float, float]:
    """Python port of the backend's ``gpu_projection_hash_color`` / ``hash_color``."""
    digest = 2166136261
    for byte in str(value or "").encode("utf-8"):
        digest ^= byte
        digest = (digest * 16777619) & 0xFFFFFFFF
    return (
        float(digest & 0xFF) / 255.0,
        float((digest >> 8) & 0xFF) / 255.0,
        float((digest >> 16) & 0xFF) / 255.0,
    )


def _rgb(value) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        components = [float(component) for component in list(value)[:3]]
    except Exception:
        return None
    if len(components) < 3:
        return None
    return tuple(max(0.0, min(1.0, component)) for component in components)  # type: ignore[return-value]


def _is_default_grey(rgb: tuple[float, float, float]) -> bool:
    return all(abs(component - 0.8) <= _DEFAULT_TOLERANCE for component in rgb)


def _active_output_surface_node(node_tree):
    nodes = list(getattr(node_tree, "nodes", []) or [])
    outputs = [node for node in nodes if getattr(node, "type", "") == "OUTPUT_MATERIAL"]
    active = [node for node in outputs if getattr(node, "is_active_output", False)]
    for output in active or outputs:
        inputs = getattr(output, "inputs", None)
        try:
            surface = inputs["Surface"] if inputs is not None else None
        except Exception:
            surface = None
        links = list(getattr(surface, "links", []) or []) if surface is not None else []
        if links:
            return getattr(links[0], "from_node", None)
    return None


def principled_base_color(material) -> tuple[float, float, float] | None:
    """Unlinked Base Color of the material's Principled BSDF, or None.

    The BSDF feeding the active Material Output's Surface wins; failing that, the
    tree's only Principled BSDF. A linked Base Color (a texture, a ramp) has no single
    colour, so it yields None and the rule falls through to the name hash.
    """
    node_tree = getattr(material, "node_tree", None)
    if node_tree is None:
        return None
    candidate = _active_output_surface_node(node_tree)
    if getattr(candidate, "type", "") != "BSDF_PRINCIPLED":
        principled = [
            node
            for node in (getattr(node_tree, "nodes", []) or [])
            if getattr(node, "type", "") == "BSDF_PRINCIPLED"
        ]
        candidate = principled[0] if len(principled) == 1 else None
    if candidate is None:
        return None
    try:
        socket = candidate.inputs["Base Color"]
    except Exception:
        return None
    if bool(getattr(socket, "is_linked", False)):
        return None
    return _rgb(getattr(socket, "default_value", None))


def material_id_color(material) -> tuple[float, float, float]:
    """The ID-map colour of one material (see the module docstring for the rule)."""
    viewport = _rgb(getattr(material, "diffuse_color", None))
    if viewport is not None and not _is_default_grey(viewport):
        return viewport
    base = principled_base_color(material)
    if base is not None and not _is_default_grey(base):
        return base
    return fnv1a_hash_color(str(getattr(material, "name", "") or ""))
