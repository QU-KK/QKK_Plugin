from __future__ import annotations

import json

import bpy

try:
    from . import properties as _properties
except Exception:
    _properties = None


_HEATMAP_ATTRIBUTE_NAME = "_master_baker_heatmap"
_HEATMAP_MATERIAL_NAME = "_FYR_BAKER_HEATMAP_MATERIAL"
_HEATMAP_MODIFIER_NAME = "_FYR_BAKER_HEATMAP"
_HEATMAP_NODE_GROUP_PREFIX = "_FYR_BAKER_HEATMAP_NG_"
_HEATMAP_OBJECT_FLAG = "_master_baker_heatmap_preview_applied"
_HEATMAP_SIGNATURE_KEY = "_master_baker_heatmap_signature"
_HEATMAP_SLOT_STATE_KEY = "_master_baker_heatmap_slot_state"
_HEATMAP_NODE_GROUP_FLAG = "_master_baker_heatmap_node_group"


def _materials():
    return getattr(getattr(bpy, "data", None), "materials", None)


def _node_groups():
    return getattr(getattr(bpy, "data", None), "node_groups", None)


def _objects():
    return getattr(getattr(bpy, "data", None), "objects", None)


def _material_name(material) -> str:
    return getattr(material, "name", "") if material is not None else ""


def _object_material_slots(obj):
    return list(getattr(obj, "material_slots", []) or [])


def _material_session_uid(material) -> int:
    """The material's session_uid, or 0 when it has none (stubs, older data)."""
    try:
        return int(getattr(material, "session_uid", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _serialize_slot_state(obj) -> str:
    slot_state = []
    for slot in _object_material_slots(obj):
        material = getattr(slot, "material", None)
        slot_state.append(
            {
                "material_name": _material_name(material),
                # Names are not an identity: renaming a material while the preview
                # is on made the name lookup miss and the restore then cleared the
                # slot, dropping the artist's material from the mesh with no undo
                # push behind it (preview swaps are view state). session_uid is
                # stable for the life of the session, which outlives any preview.
                "session_uid": _material_session_uid(material),
                "link": getattr(slot, "link", "DATA"),
            }
        )
    return json.dumps(slot_state, separators=(",", ":"))


def _material_by_name(name: str):
    materials = _materials()
    if materials is None or not name:
        return None
    getter = getattr(materials, "get", None)
    if callable(getter):
        return getter(name)
    for material in materials:
        if getattr(material, "name", "") == name:
            return material
    return None


def _material_by_session_uid(session_uid: int):
    if not session_uid:
        return None
    materials = _materials()
    if materials is None:
        return None
    for material in materials:
        if _material_session_uid(material) == session_uid:
            return material
    return None


def _restored_slot_material(state: dict):
    """The material a recorded slot should get back.

    session_uid first so a rename cannot lose it; the name is the fallback for
    state written before uids were recorded. Both missing means the material was
    really deleted from the file, and an empty slot is the honest result.
    """
    material = _material_by_session_uid(_coerced_session_uid(state.get("session_uid")))
    if material is not None:
        return material
    return _material_by_name(str(state.get("material_name", "") or ""))


def _coerced_session_uid(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _iter_heatmap_objects():
    objects = _objects()
    if objects is None:
        return
    for obj in objects:
        getter = getattr(obj, "get", None)
        if not callable(getter):
            continue
        try:
            if bool(getter(_HEATMAP_OBJECT_FLAG)):
                yield obj
        except Exception:
            continue


def _iter_valid_meshes(slot_collection):
    for slot in slot_collection:
        obj = getattr(slot, "object_ref", None)
        if obj is not None and getattr(obj, "type", None) == "MESH":
            yield obj


def _preview_session_state(settings):
    if _properties is not None and hasattr(_properties, "preview_session_state"):
        return _properties.preview_session_state(settings)
    nested_state = getattr(settings, "preview_session", None) if settings is not None else None
    if nested_state is not None:
        return nested_state
    return settings


def _overlay_settings_state(settings):
    if _properties is not None and hasattr(_properties, "overlay_settings_state"):
        return _properties.overlay_settings_state(settings)
    nested_state = getattr(settings, "overlay_settings", None) if settings is not None else None
    if nested_state is not None:
        return nested_state
    return settings


def _is_heatmap_enabled(settings, group=None) -> bool:
    overlay_state = _overlay_settings_state(settings)
    if overlay_state is None or not bool(getattr(overlay_state, "show_error_heatmap", False)):
        return False
    # The per-group flag as well, the way the GPU overlay path requires both. The master
    # latches True as soon as ANY group turns coverage on and is only cleared by Toggle
    # All Cage Coverage, so gating on it alone swapped the materials of whichever group
    # happened to be active - including one whose own toggle reads off - and re-applied
    # them on every sync. Save at that moment and the temporary heatmap material and its
    # Geometry Nodes modifier went into the artist's .blend.
    if group is not None and not bool(getattr(group, "show_cage_coverage", False)):
        return False
    session_state = _preview_session_state(settings)
    if bool(getattr(session_state, "preview_on_low_active", False)):
        return False
    if bool(getattr(session_state, "preview_pbr_on_low_active", False)):
        return False
    if bool(getattr(session_state, "live_normal_preview_active", False)):
        return False
    return True


def _group_input_socket(node_group, name: str, *, in_out: str, socket_type: str):
    interface = getattr(node_group, "interface", None)
    if interface is not None and hasattr(interface, "new_socket"):
        return interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    socket_collection = getattr(node_group, "inputs" if in_out == "INPUT" else "outputs", None)
    if socket_collection is not None and hasattr(socket_collection, "new"):
        return socket_collection.new(socket_type, name)
    return None


def _node_input(node, *names: str, index: int | None = None):
    sockets = getattr(node, "inputs", None)
    if sockets is None:
        return None
    for name in names:
        try:
            return sockets[name]
        except Exception:
            continue
    if index is not None:
        try:
            return sockets[index]
        except Exception:
            return None
    return None


def _node_output(node, *names: str, index: int | None = None):
    sockets = getattr(node, "outputs", None)
    if sockets is None:
        return None
    for name in names:
        try:
            return sockets[name]
        except Exception:
            continue
    if index is not None:
        try:
            return sockets[index]
        except Exception:
            return None
    return None


def _set_socket_default(socket, value) -> None:
    if socket is None:
        return
    try:
        socket.default_value = value
    except Exception:
        pass


def _safe_link(links, output_socket, input_socket) -> None:
    if links is None or output_socket is None or input_socket is None:
        return
    try:
        links.new(output_socket, input_socket)
    except Exception:
        pass


def _normalize_distance_value(nodes, links, distance_output, *, min_distance: float, max_distance: float):
    span = max(1.0e-6, float(max_distance) - float(min_distance))

    subtract_node = nodes.new("ShaderNodeMath")
    subtract_node.operation = "SUBTRACT"
    _set_socket_default(_node_input(subtract_node, index=1), float(min_distance))

    divide_node = nodes.new("ShaderNodeMath")
    divide_node.operation = "DIVIDE"
    _set_socket_default(_node_input(divide_node, index=1), span)

    minimum_node = nodes.new("ShaderNodeMath")
    minimum_node.operation = "MINIMUM"
    _set_socket_default(_node_input(minimum_node, index=1), 1.0)

    maximum_node = nodes.new("ShaderNodeMath")
    maximum_node.operation = "MAXIMUM"
    _set_socket_default(_node_input(maximum_node, index=1), 0.0)

    invert_node = nodes.new("ShaderNodeMath")
    invert_node.operation = "SUBTRACT"
    _set_socket_default(_node_input(invert_node, index=0), 1.0)

    _safe_link(links, distance_output, _node_input(subtract_node, index=0))
    _safe_link(links, _node_output(subtract_node, index=0), _node_input(divide_node, index=0))
    _safe_link(links, _node_output(divide_node, index=0), _node_input(minimum_node, index=0))
    _safe_link(links, _node_output(minimum_node, index=0), _node_input(maximum_node, index=0))
    _safe_link(links, _node_output(maximum_node, index=0), _node_input(invert_node, index=1))
    return _node_output(invert_node, index=0)


def _heatmap_node_group_name(obj) -> str:
    pointer = 0
    as_pointer = getattr(obj, "as_pointer", None)
    if callable(as_pointer):
        try:
            pointer = int(as_pointer())
        except Exception:
            pointer = 0
    return f"{_HEATMAP_NODE_GROUP_PREFIX}{getattr(obj, 'name', 'Object')}_{pointer}"


def _build_heatmap_node_group(obj, high_objects, *, min_distance: float, max_distance: float):
    node_groups = _node_groups()
    if node_groups is None:
        raise RuntimeError("Blender node groups are not available")

    node_group = node_groups.new(_heatmap_node_group_name(obj), "GeometryNodeTree")
    for attribute_name, value in (
        ("is_modifier", True),
        ("is_mode_object", True),
        ("is_mode_edit", True),
    ):
        if hasattr(node_group, attribute_name):
            try:
                setattr(node_group, attribute_name, value)
            except Exception:
                pass
    node_group[_HEATMAP_NODE_GROUP_FLAG] = True
    node_group["heatmap_target_count"] = int(len(high_objects))
    node_group["heatmap_max_distance"] = float(max_distance)

    _group_input_socket(node_group, "Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    _group_input_socket(node_group, "Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nodes = node_group.nodes
    links = node_group.links
    if hasattr(nodes, "clear"):
        nodes.clear()

    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")
    store_node = nodes.new("GeometryNodeStoreNamedAttribute")
    store_node.data_type = "FLOAT"
    store_node.domain = "POINT"
    _set_socket_default(_node_input(store_node, "Name", index=2), _HEATMAP_ATTRIBUTE_NAME)
    _safe_link(
        links,
        _node_output(input_node, "Geometry", index=0),
        _node_input(store_node, "Geometry", index=0),
    )

    value_output = None
    if high_objects:
        join_node = nodes.new("GeometryNodeJoinGeometry")
        realize_node = nodes.new("GeometryNodeRealizeInstances")
        proximity_node = nodes.new("GeometryNodeProximity")
        position_node = nodes.new("GeometryNodeInputPosition")
        try:
            proximity_node.target_element = "FACES"
        except Exception:
            pass
        for high_obj in high_objects:
            object_info_node = nodes.new("GeometryNodeObjectInfo")
            try:
                object_info_node.transform_space = "RELATIVE"
            except Exception:
                pass
            _set_socket_default(_node_input(object_info_node, "Object", index=0), high_obj)
            _set_socket_default(_node_input(object_info_node, "As Instance", index=1), False)
            _safe_link(
                links,
                _node_output(object_info_node, "Geometry", index=3),
                _node_input(join_node, "Geometry", index=0),
            )

        _safe_link(
            links,
            _node_output(join_node, "Geometry", index=0),
            _node_input(realize_node, "Geometry", index=0),
        )
        _safe_link(
            links,
            _node_output(realize_node, "Geometry", index=0),
            _node_input(proximity_node, "Target", "Geometry", index=0),
        )
        _safe_link(
            links,
            _node_output(position_node, "Position", index=0),
            _node_input(proximity_node, "Source Position", "Position", index=1),
        )
        value_output = _normalize_distance_value(
            nodes,
            links,
            _node_output(proximity_node, "Distance", index=1),
            min_distance=min_distance,
            max_distance=max_distance,
        )
    else:
        value_node = nodes.new("ShaderNodeValue")
        _set_socket_default(_node_output(value_node, index=0), 0.0)
        value_output = _node_output(value_node, index=0)

    _safe_link(links, value_output, _node_input(store_node, "Value", index=3))
    _safe_link(
        links,
        _node_output(store_node, "Geometry", index=0),
        _node_input(output_node, "Geometry", index=0),
    )
    return node_group


def _ensure_heatmap_material(settings):
    materials = _materials()
    if materials is None:
        raise RuntimeError("Blender materials are not available")

    getter = getattr(materials, "get", None)
    material = getter(_HEATMAP_MATERIAL_NAME) if callable(getter) else None
    if material is None:
        material = materials.new(_HEATMAP_MATERIAL_NAME)

    material.use_nodes = True
    node_tree = getattr(material, "node_tree", None)
    if node_tree is None:
        return material

    nodes = node_tree.nodes
    links = node_tree.links
    if hasattr(nodes, "clear"):
        nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    shader_node = nodes.new("ShaderNodeBsdfPrincipled")
    attribute_node = nodes.new("ShaderNodeAttribute")
    ramp_node = nodes.new("ShaderNodeValToRGB")

    try:
        attribute_node.attribute_name = _HEATMAP_ATTRIBUTE_NAME
    except Exception:
        _set_socket_default(_node_input(attribute_node, "Name", index=0), _HEATMAP_ATTRIBUTE_NAME)
    try:
        attribute_node.attribute_type = "GEOMETRY"
    except Exception:
        pass

    try:
        shader_node.inputs["Roughness"].default_value = 0.6
    except Exception:
        pass

    overlay_state = _overlay_settings_state(settings)
    inside_rgb = tuple(float(component) for component in getattr(overlay_state, "heatmap_inside_color", (0.12, 0.46, 1.0)))
    outside_rgb = tuple(float(component) for component in getattr(overlay_state, "heatmap_outside_color", (1.0, 0.08, 0.08)))
    try:
        ramp = ramp_node.color_ramp
        ramp.elements[0].position = 0.0
        ramp.elements[0].color = (outside_rgb[0], outside_rgb[1], outside_rgb[2], 1.0)
        ramp.elements[1].position = 1.0
        ramp.elements[1].color = (inside_rgb[0], inside_rgb[1], inside_rgb[2], 1.0)
    except Exception:
        pass

    _safe_link(
        links,
        _node_output(attribute_node, "Fac", index=2),
        _node_input(ramp_node, "Fac", index=0),
    )
    _safe_link(
        links,
        _node_output(ramp_node, "Color", index=0),
        _node_input(shader_node, "Base Color", index=0),
    )
    _safe_link(
        links,
        _node_output(shader_node, index=0),
        _node_input(output_node, "Surface", index=0),
    )

    material["heatmap_attribute"] = _HEATMAP_ATTRIBUTE_NAME
    return material


def _store_original_slot_state_if_needed(obj) -> None:
    getter = getattr(obj, "get", None)
    if callable(getter):
        try:
            if getter(_HEATMAP_OBJECT_FLAG):
                return
        except Exception:
            pass
    obj[_HEATMAP_SLOT_STATE_KEY] = _serialize_slot_state(obj)


def _apply_material_to_object(obj, material) -> bool:
    _store_original_slot_state_if_needed(obj)
    slots = _object_material_slots(obj)
    if slots:
        for slot in slots:
            try:
                slot.link = "OBJECT"
            except Exception:
                pass
            slot.material = material
    else:
        try:
            obj.active_material = material
        except Exception:
            pass
        data_materials = getattr(getattr(obj, "data", None), "materials", None)
        if data_materials is not None:
            if hasattr(data_materials, "clear"):
                try:
                    data_materials.clear()
                except Exception:
                    pass
            if hasattr(data_materials, "append"):
                try:
                    data_materials.append(material)
                except Exception:
                    pass
    obj[_HEATMAP_OBJECT_FLAG] = True
    return True


def _restore_material(obj) -> bool:
    getter = getattr(obj, "get", None)
    if not callable(getter):
        return False
    try:
        if not getter(_HEATMAP_OBJECT_FLAG):
            return False
    except Exception:
        return False

    raw_state = str(getter(_HEATMAP_SLOT_STATE_KEY, "[]") or "[]")
    try:
        slot_state = json.loads(raw_state)
    except json.JSONDecodeError:
        slot_state = []

    slots = _object_material_slots(obj)
    if slot_state:
        for index, state in enumerate(slot_state):
            if index >= len(slots):
                break
            slot = slots[index]
            try:
                slot.link = str(state.get("link", "DATA") or "DATA")
            except Exception:
                pass
            slot.material = _restored_slot_material(state)
        # Slots added after the state was captured were handed the heatmap
        # material by the next apply, and nothing above clears them -- that left
        # Fyr's preview material sitting in the artist's mesh, keeping it alive
        # in the .blend. There is no recorded original for them, so empty them.
        for slot in slots[len(slot_state):]:
            try:
                slot.material = None
            except Exception:
                pass
    else:
        try:
            obj.active_material = None
        except Exception:
            pass
        data_materials = getattr(getattr(obj, "data", None), "materials", None)
        if data_materials is not None and hasattr(data_materials, "clear"):
            try:
                data_materials.clear()
            except Exception:
                pass

    for key in (_HEATMAP_OBJECT_FLAG, _HEATMAP_SLOT_STATE_KEY):
        try:
            del obj[key]
        except Exception:
            pass
    return True


def _find_heatmap_modifier(obj):
    modifiers = getattr(obj, "modifiers", None)
    if modifiers is None:
        return None
    getter = getattr(modifiers, "get", None)
    if callable(getter):
        return getter(_HEATMAP_MODIFIER_NAME)
    for modifier in modifiers:
        if getattr(modifier, "name", "") == _HEATMAP_MODIFIER_NAME:
            return modifier
    return None


def _remove_addon_node_group(node_group) -> None:
    if node_group is None:
        return
    getter = getattr(node_group, "get", None)
    if callable(getter):
        try:
            if not bool(getter(_HEATMAP_NODE_GROUP_FLAG)):
                return
        except Exception:
            return
    node_groups = _node_groups()
    if node_groups is None:
        return
    try:
        node_groups.remove(node_group)
    except Exception:
        pass


def _cleanup_heatmap_material_if_unused() -> None:
    for _obj in _iter_heatmap_objects():
        return
    materials = _materials()
    if materials is None:
        return
    getter = getattr(materials, "get", None)
    material = getter(_HEATMAP_MATERIAL_NAME) if callable(getter) else None
    if material is None:
        return
    try:
        materials.remove(material)
    except Exception:
        pass


def _remove_heatmap_from_object(obj) -> bool:
    removed = False
    modifier = _find_heatmap_modifier(obj)
    if modifier is not None:
        node_group = getattr(modifier, "node_group", None)
        modifiers = getattr(obj, "modifiers", None)
        if modifiers is not None and hasattr(modifiers, "remove"):
            try:
                modifiers.remove(modifier)
                removed = True
            except Exception:
                pass
        _remove_addon_node_group(node_group)
    if _restore_material(obj):
        removed = True
    for key in (_HEATMAP_SIGNATURE_KEY,):
        try:
            del obj[key]
        except Exception:
            pass
    return removed


def _object_key(obj) -> int:
    """Stable identity for a bpy object: wrappers are fresh per access, so id() never
    matches an object seen through another collection. as_pointer() does."""
    as_pointer = getattr(obj, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(obj)


def clear_heatmap_preview(*, exclude_objects=None) -> int:
    excluded_ids = {_object_key(obj) for obj in (exclude_objects or []) if obj is not None}
    cleared = 0
    for obj in list(_iter_heatmap_objects()):
        if _object_key(obj) in excluded_ids:
            continue
        if _remove_heatmap_from_object(obj):
            cleared += 1
    _cleanup_heatmap_material_if_unused()
    return cleared


def _effective_distance_max(group, slot) -> float:
    group_offset = float(getattr(group, "cage_offset", 0.0) or 0.0)
    slot_offset = float(getattr(slot, "cage_offset_delta", 0.0) or 0.0)
    return max(0.005, max(0.0, group_offset + slot_offset))


def _signature_for_object(high_objects, *, min_distance: float, max_distance: float) -> str:
    high_pointers = []
    for high_obj in high_objects:
        as_pointer = getattr(high_obj, "as_pointer", None)
        if callable(as_pointer):
            try:
                high_pointers.append(int(as_pointer()))
            except Exception:
                continue
    return json.dumps(
        {
            "high": sorted(high_pointers),
            "min": round(float(min_distance), 6),
            "max": round(float(max_distance), 6),
        },
        separators=(",", ":"),
    )


def _ensure_heatmap_modifier(obj, node_group):
    modifiers = getattr(obj, "modifiers", None)
    if modifiers is None:
        return None
    modifier = _find_heatmap_modifier(obj)
    if modifier is None and hasattr(modifiers, "new"):
        modifier = modifiers.new(name=_HEATMAP_MODIFIER_NAME, type="NODES")
    if modifier is None:
        return None
    try:
        modifier.node_group = node_group
    except Exception:
        return None
    for attribute_name, value in (
        ("show_viewport", True),
        ("show_render", False),
        ("show_in_editmode", True),
    ):
        if hasattr(modifier, attribute_name):
            try:
                setattr(modifier, attribute_name, value)
            except Exception:
                pass
    return modifier


def _apply_heatmap_to_object(obj, settings, group, slot, high_objects, material) -> bool:
    min_distance = 0.0
    max_distance = _effective_distance_max(group, slot)
    signature = _signature_for_object(high_objects, min_distance=min_distance, max_distance=max_distance)
    current_signature = str(getattr(obj, "get", lambda *_args, **_kwargs: "")(_HEATMAP_SIGNATURE_KEY, "") or "")
    modifier = _find_heatmap_modifier(obj)
    if modifier is None or getattr(modifier, "node_group", None) is None or current_signature != signature:
        old_group = getattr(modifier, "node_group", None) if modifier is not None else None
        node_group = _build_heatmap_node_group(
            obj,
            high_objects,
            min_distance=min_distance,
            max_distance=max_distance,
        )
        modifier = _ensure_heatmap_modifier(obj, node_group)
        if modifier is None:
            _remove_addon_node_group(node_group)
            return False
        _remove_addon_node_group(old_group)
        obj[_HEATMAP_SIGNATURE_KEY] = signature

    _apply_material_to_object(obj, material)
    return True


def sync_heatmap_preview(scene=None, *, settings=None, group=None) -> int:
    if scene is None:
        scene = getattr(bpy.context, "scene", None)
    if settings is None and scene is not None:
        settings = getattr(scene, "fyr_baker_settings", None)
    if group is None and scene is not None:
        try:
            from . import cage_session

            _settings, _project, group = cage_session.resolve_project_group(scene)
        except Exception:
            group = None

    if group is None or not _is_heatmap_enabled(settings, group):
        return clear_heatmap_preview()

    low_slots = [slot for slot in getattr(group, "low_meshes", []) if getattr(getattr(slot, "object_ref", None), "type", None) == "MESH"]
    high_resolver = getattr(_properties, "effective_high_mesh_slots", None) if _properties is not None else None
    if callable(high_resolver):
        high_slots = high_resolver(group)
    else:
        role_state = getattr(group, "role_assignments", None) or group
        use_low_as_high = bool(getattr(role_state, "use_low_as_high", getattr(group, "use_low_as_high", False)))
        high_slots = getattr(role_state, "low_meshes" if use_low_as_high else "high_meshes", [])
    high_objects = list(_iter_valid_meshes(high_slots))
    if not low_slots or not high_objects:
        return clear_heatmap_preview()

    material = _ensure_heatmap_material(settings)
    target_objects = [slot.object_ref for slot in low_slots]
    clear_heatmap_preview(exclude_objects=target_objects)

    applied = 0
    seen_object_ids: set[int] = set()
    for slot in low_slots:
        obj = getattr(slot, "object_ref", None)
        if obj is None or _object_key(obj) in seen_object_ids:
            continue
        seen_object_ids.add(_object_key(obj))
        if _apply_heatmap_to_object(obj, settings, group, slot, high_objects, material):
            applied += 1
        else:
            _remove_heatmap_from_object(obj)
    return applied


def register() -> None:
    return None


def unregister() -> None:
    clear_heatmap_preview()
