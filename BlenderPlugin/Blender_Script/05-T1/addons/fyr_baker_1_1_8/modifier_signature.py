"""Cheap identity for what an object's modifier stack will evaluate to.

Shared by the Cage Check overlay cache and the low-mesh export cache: both build
from the EVALUATED mesh, so their keys have to move when a Subdivision level, a
Displace strength or a Weighted Normal weight changes while the original
datablock stays untouched. Property names are resolved once per modifier RNA type
and only scalars, short vectors and datablock pointers are read, so this stays a
handful of attribute reads per modifier. UI-only properties are skipped on
purpose: a false invalidation throws away finished work for nothing.
"""

from __future__ import annotations

# UI-only modifier properties: they never change the evaluated mesh, so folding them
# into the cache signature would throw away a finished coverage batch (a multi-second
# rebuild) every time the artist expands a modifier panel.
MODIFIER_SIGNATURE_SKIP_PROPERTIES = frozenset(
    {
        "execution_time",
        "is_active",
        "is_override_data",
        "name",
        "persistent_uid",
        "rna_type",
        "show_expanded",
        "show_in_editmode",
        "show_on_cage",
        "show_render",
        "type",
        "use_pin_to_last",
    }
)

#: RNA identifier -> the property names worth hashing. Resolved once per modifier type.
MODIFIER_PROPERTY_NAMES: dict[str, tuple[str, ...]] = {}


def modifier_property_names(modifier) -> tuple[str, ...]:
    bl_rna = getattr(modifier, "bl_rna", None)
    identifier = str(getattr(bl_rna, "identifier", "") or type(modifier).__name__)
    cached = MODIFIER_PROPERTY_NAMES.get(identifier)
    if cached is not None:
        return cached
    names: list[str] = []
    try:
        for rna_property in getattr(bl_rna, "properties", None) or ():
            property_id = str(getattr(rna_property, "identifier", "") or "")
            if not property_id or property_id in MODIFIER_SIGNATURE_SKIP_PROPERTIES:
                continue
            if str(getattr(rna_property, "type", "") or "") not in (
                "BOOLEAN",
                "ENUM",
                "FLOAT",
                "INT",
                "POINTER",
                "STRING",
            ):
                continue
            if int(getattr(rna_property, "array_length", 0) or 0) > 16:
                continue
            names.append(property_id)
    except Exception:
        names = []
    resolved = tuple(sorted(names))
    MODIFIER_PROPERTY_NAMES[identifier] = resolved
    return resolved


def modifier_property_value(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 6)
    as_pointer = getattr(value, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            return 0
    try:
        if len(value) > 16:
            return len(value)
        return tuple(modifier_property_value(item) for item in value)
    except Exception:
        return str(value)


def modifier_custom_property_signature(modifier) -> tuple:
    """Geometry Nodes stores its socket inputs as custom properties, not RNA fields."""
    items = getattr(modifier, "items", None)
    if not callable(items):
        return ()
    entries: list[tuple[str, object]] = []
    try:
        for key, value in items():
            entries.append((str(key), modifier_property_value(value)))
    except Exception:
        return ()
    entries.sort(key=lambda entry: entry[0])
    return tuple(entries)


def _vector_signature(values) -> tuple:
    if values is None:
        return ()
    try:
        return tuple(round(float(value), 6) for value in values)
    except Exception:
        return ()


def deform_signature(obj) -> tuple:
    """Identity for deformation the modifier stack's own properties do not carry.

    An Armature modifier contributes only its rig's POINTER, which does not change
    when the rig is POSED, and shape-key values are not in the stack at all. Anything
    keyed on the evaluated mesh therefore has to fold this in as well, or it serves
    rest-pose geometry for a posed character. Only the bones of this object's own
    Armature modifiers are read, through the pose channels rather than a 4x4 per bone.
    """
    values: list[object] = []
    data = getattr(obj, "data", None)
    shape_keys = getattr(data, "shape_keys", None) if data is not None else None
    key_blocks = getattr(shape_keys, "key_blocks", None) if shape_keys is not None else None
    try:
        for block in key_blocks or ():
            values.append((str(getattr(block, "name", "") or ""), round(float(getattr(block, "value", 0.0)), 6)))
    except Exception:
        return ()
    try:
        for modifier in getattr(obj, "modifiers", None) or ():
            if str(getattr(modifier, "type", "") or "") != "ARMATURE":
                continue
            rig = getattr(modifier, "object", None)
            pose = getattr(rig, "pose", None)
            for bone in getattr(pose, "bones", None) or ():
                values.append((
                    _vector_signature(getattr(bone, "location", None)),
                    _vector_signature(getattr(bone, "rotation_quaternion", None)),
                    _vector_signature(getattr(bone, "rotation_euler", None)),
                    _vector_signature(getattr(bone, "scale", None)),
                ))
    except Exception:
        return ()
    return tuple(values)


def modifier_stack_signature(obj) -> tuple:
    """Cheap identity for whatever the modifier stack will evaluate to.

    The batch this signature guards is built from ``obj_eval.to_mesh()``, so it has to
    move when the evaluated result moves. The original mesh counts alone do not: a
    Subdivision level or a Displace strength changes the evaluated mesh while leaving
    the original datablock untouched, and the stale batch was then served forever.

    Property names are resolved once per modifier type and only scalars, short vectors
    and datablock pointers are read, so this stays a handful of attribute reads per
    modifier on the draw path. UI-only properties are skipped on purpose.
    """
    modifiers = getattr(obj, "modifiers", None)
    if not modifiers:
        return ()
    signature: list[tuple] = []
    try:
        for modifier in modifiers:
            values: list[object] = []
            for property_id in modifier_property_names(modifier):
                try:
                    values.append(modifier_property_value(getattr(modifier, property_id, None)))
                except Exception:
                    values.append(None)
            signature.append(
                (
                    str(getattr(modifier, "name", "") or ""),
                    str(getattr(modifier, "type", "") or ""),
                    bool(getattr(modifier, "show_viewport", True)),
                    tuple(values),
                    modifier_custom_property_signature(modifier),
                )
            )
    except Exception:
        return ()
    return tuple(signature)
