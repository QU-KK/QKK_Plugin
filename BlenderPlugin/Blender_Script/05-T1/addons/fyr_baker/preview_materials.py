from __future__ import annotations

import json

import bpy

from . import constants


_PREVIEW_MATERIAL_NAME = constants.PREVIEW_MATERIAL_NAME_PREFIX
_PREVIEW_OBJECT_FLAG = "_master_baker_preview_material_applied"
_PREVIEW_SLOT_STATE_KEY = "_master_baker_preview_slot_state"
_PREVIEW_SLOT_MATERIALS_KEY = "_master_baker_preview_slot_materials"
_PREVIEW_SIGNATURE_KEY = "_master_baker_preview_signature"
_PREVIEW_BASE_COLOR = (0.5, 0.5, 0.5, 1.0)


def _suppress_preview_side_effects() -> None:
    """Keep show-on-low from arming speculative bake prepares.

    Assigning preview materials tags the low mesh as geometry/transform-updated
    in Blender's depsgraph. That used to schedule a 1s-debounced speculative
    PREPARE which then blocked the UI for seconds re-exporting huge highs.
    """
    try:
        from . import operators

        operators._suppress_bg_prepare(2.0)
    except Exception:
        pass


def _materials():
    return getattr(getattr(bpy, "data", None), "materials", None)


def _objects():
    return getattr(getattr(bpy, "data", None), "objects", None)


def _material_name(material) -> str:
    return getattr(material, "name", "") if material is not None else ""


def _iter_preview_objects():
    objects = _objects()
    if objects is None:
        return
    for obj in objects:
        getter = getattr(obj, "get", None)
        if not callable(getter):
            continue
        try:
            if bool(getter(_PREVIEW_OBJECT_FLAG)):
                yield obj
        except Exception:
            continue


def _object_material_slots(obj):
    return list(getattr(obj, "material_slots", []) or [])


def _is_preview_material(material) -> bool:
    return bool(material is not None and _material_name(material).startswith(_PREVIEW_MATERIAL_NAME))


def object_preview_assignment_is_intact(obj) -> bool:
    """Whether a tracked object still carries the preview material we assigned.

    Artists can replace the material from Blender while preview mode is active.  That
    is an explicit user edit, not state for the preview lifecycle to undo later.
    """
    getter = getattr(obj, "get", None)
    if not callable(getter):
        return False
    try:
        if not getter(_PREVIEW_OBJECT_FLAG):
            return False
    except Exception:
        return False

    slots = _object_material_slots(obj)
    if slots:
        return all(_is_preview_material(getattr(slot, "material", None)) for slot in slots)
    return _is_preview_material(getattr(obj, "active_material", None))


def any_preview_material_applied() -> bool:
    """True while at least one object still wears a Fyr preview material."""
    return any(object_preview_assignment_is_intact(obj) for obj in _iter_preview_objects())


def has_overridden_preview_materials() -> bool:
    """True when an artist replaced a material after Fyr applied its preview."""
    return any(not object_preview_assignment_is_intact(obj) for obj in _iter_preview_objects())


def _serialize_slot_state(obj) -> str:
    slot_state = []
    for slot in _object_material_slots(obj):
        material = getattr(slot, "material", None)
        slot_state.append(
            {
                "material_name": _material_name(material),
                "link": getattr(slot, "link", "DATA"),
                "fake_user": bool(getattr(material, "use_fake_user", False)) if material is not None else False,
            }
        )
    return json.dumps(slot_state)


def _custom_prop(datablock, key: str, default=""):
    getter = getattr(datablock, "get", None)
    if callable(getter):
        try:
            return getter(key, default)
        except Exception:
            return default
    try:
        return datablock[key]
    except Exception:
        return default


_BLENDER_ID_NAME_MAX = 63


def _preview_material_name(material_suffix: str = "") -> str:
    """Datablock name for a preview material, always within Blender's 63-char ID limit.

    materials.new() silently truncates a longer name, so the next materials.get()
    misses, a fresh material is created and uniquified to .001, and every resync
    rebuilt the tree and orphaned another datablock for any texture set or group
    with a long name. Long suffixes are replaced by a stable hash of themselves.
    """
    suffix = str(material_suffix or "")
    name = _PREVIEW_MATERIAL_NAME + (("_" + suffix) if suffix else "")
    if len(name.encode("utf-8")) <= _BLENDER_ID_NAME_MAX:
        return name
    import hashlib

    digest = hashlib.blake2b(suffix.encode("utf-8"), digest_size=6).hexdigest()
    budget = _BLENDER_ID_NAME_MAX - len(_PREVIEW_MATERIAL_NAME) - len(digest) - 2
    head = suffix[: max(0, budget)]
    return f"{_PREVIEW_MATERIAL_NAME}_{head}#{digest}"


def _image_key_token(image) -> str:
    """Short stable token identifying one image datablock.

    Used to discriminate preview-material datablocks so two bake groups never
    share a preview material unless they are showing the very same image.
    """
    signature = _image_signature(image)
    if not signature:
        return "none"
    import hashlib

    return hashlib.sha1(signature.encode("utf-8", errors="replace")).hexdigest()[:8]


def _image_signature(image) -> str:
    if image is None:
        return ""
    return "{}~{}".format(
        str(getattr(image, "name", "") or ""),
        str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", "") or ""),
    )


def _reuse_preview_material(materials, mat_name: str, signature: str, expected_images=()):
    """Return (material, reusable) for a preview material of this exact shape.

    The preview node tree is scratch data the addon owns, but users legitimately
    tweak it (roughness, AO mix, extra nodes) while judging a bake. Rebuilding it on
    every resync threw those edits away — most visibly on file save, where save_pre
    strips the preview and save_post re-applies it. Reuse the existing tree whenever
    the inputs that shape it are unchanged, and only rebuild when they actually
    differ or the tree was emptied.
    """
    getter = getattr(materials, "get", None)
    material = getter(mat_name) if callable(getter) else None
    if material is None:
        return None, False
    stored = str(_custom_prop(material, _PREVIEW_SIGNATURE_KEY, "") or "")
    if not stored or stored != signature:
        return material, False
    nodes = getattr(getattr(material, "node_tree", None), "nodes", None)
    if nodes is None or not len(nodes):
        return material, False
    # A matching signature is NOT enough. The signature is built from the image's name
    # and filepath, so it still matches after the image datablock has been removed and
    # re-created underneath a surviving material — which is what deleting and rewriting
    # a baked file does. The node's image pointer goes null, the signature does not
    # change, and this short-circuit hands back a tree whose Image Texture feeds an
    # Emission with nothing in it: the mesh renders solid black, and stays black on
    # every resync until the map type or the file name happens to change. Verify the
    # tree still references what the signature promises.
    expected_names = {
        name
        for name in (str(getattr(image, "name", "") or "") for image in expected_images if image is not None)
        if name
    }
    if expected_names:
        present = {
            str(getattr(getattr(node, "image", None), "name", "") or "")
            for node in nodes
            if str(getattr(node, "bl_idname", "")) == "ShaderNodeTexImage"
        }
        if not expected_names.issubset(present):
            return material, False
    return material, True


def _enforce_non_color(image) -> None:
    if image is None:
        return
    try:
        if image.colorspace_settings.name != "Non-Color":
            image.colorspace_settings.name = "Non-Color"
    except Exception:
        pass


def _apply_output_colorspace(image, map_type: str) -> None:
    """Read a baked output back in the encoding the backend wrote it with.

    Without this, a single-map preview of a data map (Roughness, Metalness,
    Normal, AO, ...) was handed to Blender as sRGB and silently linearised on
    load: 0.5 in the file displays as 0.21. Roughness read far glossier and
    Metalness far darker than the file actually is.
    """
    if image is None:
        return
    try:
        expected = constants.map_output_colorspace_name(map_type)
        # Blender's RNA setter invalidates image buffers even on a preview resync.
        # Keep an already-correct image intact while shader previews may use it.
        if image.colorspace_settings.name != expected:
            image.colorspace_settings.name = expected
    except Exception:
        pass


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


_SRGB_LINEAR_THRESHOLD = 0.04045


def _append_srgb_decode(nodes, links, color_output):
    """Decode ``color_output`` with the exact sRGB transfer curve, per channel.

    A data map is read Non-Color, so Blender treats the stored value as scene-linear
    and the view transform then encodes it for the display: a flat normal's 0.5
    showed as ~0.73 and every data map looked washed out next to Painter or an image
    viewer, which put the file's values on screen as-is. Decoding here cancels the
    display encode, so under the Standard view transform the viewport shows the file
    values exactly. Preview-only: the image stays Non-Color and the file is untouched.
    """

    def vector_math(operation, x, y, *inputs):
        node = nodes.new("ShaderNodeVectorMath")
        node.location = (x, y)
        node.operation = operation
        for index, value in enumerate(inputs):
            if isinstance(value, tuple):
                node.inputs[index].default_value = value
            else:
                links.new(value, node.inputs[index])
        return node.outputs[0]

    def splat(value):
        return (value, value, value)

    # hi = ((max(c, 0) + 0.055) / 1.055) ^ 2.4 ; the clamp keeps POWER off negative bases.
    clamped = vector_math("MAXIMUM", -120, 120, color_output, splat(0.0))
    shifted = vector_math("MULTIPLY_ADD", -120, 60, clamped, splat(1.0 / 1.055), splat(0.055 / 1.055))
    high = vector_math("POWER", -120, 0, shifted, splat(2.4))
    # lo = c / 12.92
    low = vector_math("MULTIPLY", -120, -60, color_output, splat(1.0 / 12.92))
    # mask = c > threshold, per channel (both branches agree at the threshold itself).
    offset = vector_math("SUBTRACT", -120, -120, color_output, splat(_SRGB_LINEAR_THRESHOLD))
    sign = vector_math("SIGN", -120, -180, offset)
    mask = vector_math("MAXIMUM", -120, -240, sign, splat(0.0))
    # lo + mask * (hi - lo)
    span = vector_math("SUBTRACT", 20, -60, high, low)
    weighted = vector_math("MULTIPLY", 20, -120, mask, span)
    return vector_math("ADD", 20, -180, low, weighted)


def _ensure_preview_material(image, map_type: str, *, material_suffix: str = ""):
    materials = _materials()
    if materials is None:
        raise RuntimeError("Blender materials are not available")

    mat_name = _preview_material_name(material_suffix)
    # Colorspace lives on the image datablock, not the node tree, so set it before the
    # reuse short-circuit — an already-built tree must not keep a mis-tagged image.
    _apply_output_colorspace(image, map_type)
    display_file_values = not constants.map_output_is_srgb_encoded(map_type)
    # DISPLAY2 marks trees built with the data-map display decode, so trees saved by
    # an older build are rebuilt instead of reused.
    signature = "EMISSION|DISPLAY2|{}|{}".format(str(map_type or ""), _image_signature(image))
    preview_material, reusable = _reuse_preview_material(
        materials, mat_name, signature, expected_images=(image,)
    )
    if reusable:
        return preview_material
    if preview_material is None:
        preview_material = materials.new(mat_name)

    preview_material.use_nodes = True
    node_tree = getattr(preview_material, "node_tree", None)
    if node_tree is None:
        return preview_material

    nodes = node_tree.nodes
    links = node_tree.links
    if hasattr(nodes, "clear"):
        nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (420, 0)
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.location = (-280, 0)
    image_node.image = image

    # Emission -> Output only. A single baked map is raw data, so the preview must be
    # unlit: no BSDF, no specular response, strength pinned at 1.0 and data maps
    # display-decoded so the displayed value is exactly what the backend wrote.
    shader_node = nodes.new("ShaderNodeEmission")
    shader_node.location = (160, 0)
    try:
        shader_node.inputs["Strength"].default_value = 1.0
    except Exception:
        pass
    color_output = image_node.outputs["Color"]
    if display_file_values:
        color_output = _append_srgb_decode(nodes, links, color_output)
    links.new(color_output, shader_node.inputs["Color"])
    links.new(shader_node.outputs["Emission"], output_node.inputs["Surface"])

    preview_material["map_type"] = str(map_type or "")
    preview_material["image_filepath"] = str(getattr(image, "filepath_raw", "") or getattr(image, "filepath", "") or "")
    preview_material[_PREVIEW_SIGNATURE_KEY] = signature
    return preview_material


def _ensure_pbr_preview_material(
    *,
    normal_image=None,
    ao_image=None,
    curvature_image=None,
    albedo_image=None,
    roughness_image=None,
    metalness_image=None,
    emission_image=None,
    opacity_image=None,
    specular_image=None,
    transmission_image=None,
    normal_space: str = "TANGENT",
    normal_format: str = "OPENGL",
    flip_green: bool = False,
    ao_strength: float = 1.0,
    material_suffix: str = "",
):
    materials = _materials()
    if materials is None:
        raise RuntimeError("Blender materials are not available")

    mat_name = _preview_material_name(material_suffix)
    # Colorspace lives on the image datablock, not in the node tree, so tag every input
    # regardless of whether the tree is rebuilt. AO and Curvature used to be left at
    # whatever Blender guessed from the file extension (sRGB for TGA/PNG), which
    # darkened the AO multiply and skewed the curvature-derived roughness fallback.
    for data_image in (
        normal_image,
        roughness_image,
        curvature_image,
        ao_image,
        metalness_image,
        specular_image,
        transmission_image,
        opacity_image,
    ):
        _enforce_non_color(data_image)
    # Albedo and Emission are the two channels the backend sRGB-encodes on write.
    _apply_output_colorspace(albedo_image, constants.MAP_MATERIAL_ALBEDO)
    _apply_output_colorspace(emission_image, constants.MAP_MATERIAL_EMISSION)
    signature = "PBR|" + "|".join(
        (
            _image_signature(normal_image),
            _image_signature(ao_image),
            _image_signature(curvature_image),
            _image_signature(albedo_image),
            _image_signature(roughness_image),
            _image_signature(metalness_image),
            _image_signature(emission_image),
            _image_signature(opacity_image),
            _image_signature(specular_image),
            _image_signature(transmission_image),
            str(normal_space or "").strip().upper(),
            str(normal_format or "").strip().upper(),
            "1" if flip_green else "0",
            f"{float(ao_strength):.6f}",
        )
    )
    preview_material, reusable = _reuse_preview_material(
        materials,
        mat_name,
        signature,
        expected_images=(
            normal_image,
            ao_image,
            curvature_image,
            albedo_image,
            roughness_image,
            metalness_image,
            emission_image,
            opacity_image,
            specular_image,
            transmission_image,
        ),
    )
    if reusable:
        return preview_material
    if preview_material is None:
        preview_material = materials.new(mat_name)

    preview_material.use_nodes = True
    node_tree = getattr(preview_material, "node_tree", None)
    if node_tree is None:
        return preview_material

    nodes = node_tree.nodes
    links = node_tree.links
    if hasattr(nodes, "clear"):
        nodes.clear()

    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (520, 0)
    shader_node = nodes.new("ShaderNodeBsdfPrincipled")
    shader_node.location = (260, 0)
    try:
        shader_node.inputs["Base Color"].default_value = _PREVIEW_BASE_COLOR
        shader_node.inputs["Roughness"].default_value = 0.6
    except Exception:
        pass

    if albedo_image is not None:
        base_color_node = nodes.new("ShaderNodeTexImage")
        base_color_node.location = (-520, 140)
        base_color_node.image = albedo_image
        base_color_output = base_color_node.outputs["Color"]
    else:
        base_color_node = nodes.new("ShaderNodeRGB")
        base_color_node.location = (-520, 140)
        try:
            base_color_node.outputs[0].default_value = _PREVIEW_BASE_COLOR
        except Exception:
            pass
        base_color_output = base_color_node.outputs[0]

    if ao_image is not None:
        ao_image_node = nodes.new("ShaderNodeTexImage")
        ao_image_node.location = (-420, -20)
        ao_image_node.image = ao_image
        multiply_node = nodes.new("ShaderNodeMixRGB")
        multiply_node.location = (-80, 60)
        try:
            multiply_node.blend_type = "MULTIPLY"
            multiply_node.inputs[0].default_value = min(1.0, max(0.0, float(ao_strength)))
        except Exception:
            pass
        links.new(base_color_output, multiply_node.inputs[1])
        links.new(ao_image_node.outputs["Color"], multiply_node.inputs[2])
        base_color_output = multiply_node.outputs[0]

    links.new(base_color_output, shader_node.inputs["Base Color"])

    # Prefer real baked roughness. Curvature remains a useful preview-only
    # fallback when the source material did not provide a roughness output.
    roughness_source_image = roughness_image or curvature_image
    if roughness_source_image is not None:
        roughness_image_node = nodes.new("ShaderNodeTexImage")
        roughness_image_node.location = (-520, -120)
        roughness_image_node.image = roughness_source_image
        try:
            roughness_image_node.image.colorspace_settings.name = "Non-Color"
        except Exception:
            pass
        roughness_output = roughness_image_node.outputs["Color"]
        if roughness_image is None:
            invert_curvature_node = nodes.new("ShaderNodeInvert")
            invert_curvature_node.location = (-180, -120)
            links.new(roughness_output, invert_curvature_node.inputs[1])
            roughness_output = invert_curvature_node.outputs[0]
        roughness_socket = shader_node.inputs["Roughness"]
        if getattr(roughness_socket, "type", "") == "VALUE":
            sep_type = "ShaderNodeSeparateColor" if hasattr(bpy.types, "ShaderNodeSeparateColor") else "ShaderNodeSeparateRGB"
            separate_node = nodes.new(sep_type)
            separate_node.location = (-180, -120)
            links.new(roughness_output, separate_node.inputs[0])
            links.new(separate_node.outputs[0], roughness_socket)
        else:
            links.new(roughness_output, roughness_socket)

    def _link_scalar_image(image, socket_name: str, y: int) -> None:
        if image is None:
            return
        image_node = nodes.new("ShaderNodeTexImage")
        image_node.location = (-520, y)
        image_node.image = image
        _enforce_non_color(image)
        try:
            target_socket = shader_node.inputs[socket_name]
        except Exception:
            return
        color_output = image_node.outputs["Color"]
        # Scalar maps are stored as greyscale PNGs. Linking Color directly to a
        # float socket is unreliable across Blender versions; take the red channel.
        if getattr(target_socket, "type", "") == "VALUE":
            sep_type = "ShaderNodeSeparateColor" if hasattr(bpy.types, "ShaderNodeSeparateColor") else "ShaderNodeSeparateRGB"
            separate_node = nodes.new(sep_type)
            separate_node.location = (-180, y)
            links.new(color_output, separate_node.inputs[0])
            links.new(separate_node.outputs[0], target_socket)
        else:
            links.new(color_output, target_socket)

    _link_scalar_image(metalness_image, "Metallic", -210)
    _link_scalar_image(specular_image, "Specular IOR Level", -300)
    _link_scalar_image(transmission_image, "Transmission Weight", -390)
    _link_scalar_image(opacity_image, "Alpha", -480)

    if emission_image is not None:
        emission_node = nodes.new("ShaderNodeTexImage")
        emission_node.location = (-520, -570)
        emission_node.image = emission_image
        try:
            links.new(emission_node.outputs["Color"], shader_node.inputs["Emission Color"])
        except Exception:
            try:
                links.new(emission_node.outputs["Color"], shader_node.inputs["Emission"])
            except Exception:
                pass

    if normal_image is not None:
        normal_image_node = nodes.new("ShaderNodeTexImage")
        normal_image_node.location = (-420, -260)
        normal_image_node.image = normal_image
        try:
            normal_image_node.image.colorspace_settings.name = "Non-Color"
        except Exception:
            pass
        normal_color_output = normal_image_node.outputs["Color"]
        effective_flip_green = bool(flip_green) or str(normal_format or "").strip().upper() == "DIRECTX"

        if effective_flip_green:
            sep_type = "ShaderNodeSeparateColor" if hasattr(bpy.types, "ShaderNodeSeparateColor") else "ShaderNodeSeparateRGB"
            comb_type = "ShaderNodeCombineColor" if hasattr(bpy.types, "ShaderNodeCombineColor") else "ShaderNodeCombineRGB"
            separate_node = nodes.new(sep_type)
            separate_node.location = (-180, -260)
            combine_node = nodes.new(comb_type)
            combine_node.location = (240, -260)
            links.new(normal_image_node.outputs["Color"], separate_node.inputs[0])

            links.new(separate_node.outputs[0], combine_node.inputs[0])

            invert_green_node = nodes.new("ShaderNodeInvert")
            invert_green_node.location = (20, -320)
            links.new(separate_node.outputs[1], invert_green_node.inputs[1])
            links.new(invert_green_node.outputs[0], combine_node.inputs[1])

            links.new(separate_node.outputs[2], combine_node.inputs[2])

            normal_color_output = combine_node.outputs[0]

        normal_map_node = nodes.new("ShaderNodeNormalMap")
        normal_map_node.location = (40, -160)
        try:
            normal_map_node.space = str(normal_space or "TANGENT").strip().upper()
        except Exception:
            pass
        links.new(normal_color_output, normal_map_node.inputs["Color"])
        links.new(normal_map_node.outputs["Normal"], shader_node.inputs["Normal"])

    links.new(shader_node.outputs[0], output_node.inputs["Surface"])
    # Solid "Texture" colour and texture painting show the ACTIVE image node, which is
    # otherwise whichever was added last -- the Normal map. Keep it on the colour.
    try:
        colour_image = albedo_image if albedo_image is not None else ao_image
        colour_node = next(
            (n for n in nodes if getattr(n, "bl_idname", "") == "ShaderNodeTexImage"
             and colour_image is not None and getattr(n, "image", None) == colour_image),
            None,
        )
        nodes.active = colour_node if colour_node is not None else shader_node
    except Exception:
        pass
    preview_material["map_type"] = "PBR_PREVIEW"
    preview_image = (
        albedo_image
        or normal_image
        or ao_image
        or roughness_image
        or metalness_image
        or curvature_image
        or emission_image
        or opacity_image
        or specular_image
        or transmission_image
    )
    preview_material["image_filepath"] = str(getattr(preview_image, "filepath_raw", "") or getattr(preview_image, "filepath", "") or "")
    preview_material[_PREVIEW_SIGNATURE_KEY] = signature
    return preview_material


def _store_original_slot_state_if_needed(obj) -> None:
    getter = getattr(obj, "get", None)
    if callable(getter):
        try:
            if getter(_PREVIEW_OBJECT_FLAG):
                return
        except Exception:
            pass
    obj[_PREVIEW_SLOT_STATE_KEY] = _serialize_slot_state(obj)
    # Native ID references follow renames and Blender's save/undo remapping,
    # and retain displaced materials without changing their fake-user flags.
    # Keep the group even for empty slots: its presence distinguishes this
    # snapshot from legacy name-only state. A deleted ID must not resolve to
    # an unrelated material that subsequently took its name.
    obj[_PREVIEW_SLOT_MATERIALS_KEY] = {
        str(index): slot.material
        for index, slot in enumerate(_object_material_slots(obj))
        if getattr(slot, "material", None) is not None
    }


def _apply_preview_material_to_object(obj, preview_material) -> bool:
    _store_original_slot_state_if_needed(obj)
    slots = _object_material_slots(obj)
    if slots:
        # Write only what differs. Every RNA write here tags the object for a depsgraph
        # update even when the value is unchanged, and the viewport cage overlay keys its
        # static cache on those updates: re-applying the same preview material after each
        # bake progress update re-captured every group's cage (Ubrion: 32 s of the main
        # thread blocked per bake, 5 s with the overlay off; 2026-09-29).
        for slot in slots:
            try:
                if getattr(slot, "link", None) != "OBJECT":
                    slot.link = "OBJECT"
            except Exception:
                pass
            # `!=`, not `is not`: RNA wrappers are rebuilt per access, equality compares
            # the underlying pointer.
            if getattr(slot, "material", None) != preview_material:
                slot.material = preview_material
    else:
        try:
            if getattr(obj, "active_material", None) != preview_material:
                obj.active_material = preview_material
        except Exception:
            data_materials = getattr(getattr(obj, "data", None), "materials", None)
            if data_materials is None:
                return False
            if hasattr(data_materials, "clear"):
                try:
                    data_materials.clear()
                except Exception:
                    pass
            if hasattr(data_materials, "append"):
                data_materials.append(preview_material)
    getter = getattr(obj, "get", None)
    if not (callable(getter) and getter(_PREVIEW_OBJECT_FLAG)):
        obj[_PREVIEW_OBJECT_FLAG] = True
    return True


def restore_object_preview_material(obj) -> bool:
    getter = getattr(obj, "get", None)
    if not callable(getter):
        return False
    try:
        if not getter(_PREVIEW_OBJECT_FLAG):
            return False
    except Exception:
        return False

    slots_now = _object_material_slots(obj)
    preview_slots = [
        index for index, slot in enumerate(slots_now)
        if _is_preview_material(getattr(slot, "material", None))
    ]
    if slots_now and not preview_slots:
        # Every slot is an explicit Blender-side edit made after Fyr armed preview mode.
        # Drop only our bookkeeping; restoring the older snapshot here would overwrite
        # the artist's choice, and save_post would otherwise replace it with the Fyr
        # preview again on Ctrl+S.
        for key in (_PREVIEW_OBJECT_FLAG, _PREVIEW_SLOT_STATE_KEY, _PREVIEW_SLOT_MATERIALS_KEY):
            try:
                del obj[key]
            except Exception:
                pass
        return False
    # Per slot from here on. It used to be all-or-nothing: one reassigned slot (or one
    # slot ADDED while the preview was up) made the whole object count as overridden,
    # so the remaining slots kept Fyr's emission material for good - Restore Original
    # Materials reported success, the ID snapshot that could still have recovered them
    # was deleted, and save_pre wrote the addon's temp material into the artist's .blend.
    restorable = set(preview_slots)

    raw_state = str(getter(_PREVIEW_SLOT_STATE_KEY, "[]") or "[]")
    try:
        slot_state = json.loads(raw_state)
    except json.JSONDecodeError:
        slot_state = []

    slots = _object_material_slots(obj)
    material_refs = getter(_PREVIEW_SLOT_MATERIALS_KEY)
    if slot_state:
        for index, state in enumerate(slot_state):
            if index >= len(slots):
                break
            if index not in restorable:
                # The artist owns this slot now; leave it exactly as they set it.
                continue
            slot = slots[index]
            try:
                slot.link = str(state.get("link", "DATA") or "DATA")
            except Exception:
                pass
            original = (
                material_refs.get(str(index))
                if material_refs is not None
                else _material_by_name(str(state.get("material_name", "") or ""))
            )
            slot.material = original
            if original is not None and material_refs is None:
                try:
                    original.use_fake_user = bool(state.get("fake_user", False))
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

    for key in (_PREVIEW_OBJECT_FLAG, _PREVIEW_SLOT_STATE_KEY, _PREVIEW_SLOT_MATERIALS_KEY):
        try:
            del obj[key]
        except Exception:
            pass
    return True


def restore_preview_materials(*, exclude_objects=None) -> int:
    excluded_ptrs = set()
    for obj in (exclude_objects or []):
        if obj is not None:
            try:
                excluded_ptrs.add(obj.as_pointer())
            except Exception:
                pass
    restored = 0
    _suppress_preview_side_effects()
    for obj in list(_iter_preview_objects()):
        try:
            if obj.as_pointer() in excluded_ptrs:
                continue
        except Exception:
            pass
        if restore_object_preview_material(obj):
            restored += 1
    return restored


def _find_group(project, group_name: str):
    for group in getattr(project, "groups", []):
        if getattr(group, "name", "") == group_name:
            return group
    return None


def _iter_low_mesh_objects(group):
    for slot in getattr(group, "low_meshes", []):
        obj = getattr(slot, "object_ref", None)
        if obj is not None and getattr(obj, "type", None) == "MESH":
            yield obj


def apply_preview_output(project, output_target, image) -> int:
    group_name = str(getattr(output_target, "group_name", "") or "")
    target_group = _find_group(project, group_name)
    if target_group is None:
        restore_preview_materials()
        return 0

    target_objects = list(_iter_low_mesh_objects(target_group))
    if not target_objects:
        restore_preview_materials()
        return 0

    _suppress_preview_side_effects()
    preview_material = _ensure_preview_material(image, str(getattr(output_target, "map_type", "") or ""))
    restore_preview_materials(exclude_objects=target_objects)

    applied = 0
    for obj in target_objects:
        if _apply_preview_material_to_object(obj, preview_material):
            applied += 1
    return applied


def apply_preview_output_all_groups(project, *, per_group_sources: list) -> int:
    """Apply a single-map emission preview across multiple groups.

    *per_group_sources* is a list of dicts, each with ``group_name``, ``image``,
    and ``map_type`` keys.  Groups sharing a texture-set name will share the
    same preview material.
    """
    all_target_objects = []
    group_targets: list[tuple[dict, list, str]] = []
    for src in per_group_sources:
        group_name = str(src.get("group_name") or "")
        target_group = _find_group(project, group_name)
        if target_group is None:
            continue
        objects = list(_iter_low_mesh_objects(target_group))
        if not objects:
            continue
        texture_set = _group_texture_set_name(target_group)
        # Two groups may only share ONE preview material when they share both the
        # texture set AND the resolved image. Keying on the set alone let a second
        # group inherit the first group's image datablock through the cache below.
        material_key = "{}#{}".format(
            texture_set if texture_set else group_name,
            _image_key_token(src.get("image")),
        )
        group_targets.append((src, objects, material_key))
        all_target_objects.extend(objects)

    if not group_targets:
        restore_preview_materials()
        return 0

    _suppress_preview_side_effects()
    restore_preview_materials(exclude_objects=all_target_objects)

    applied = 0
    created_materials: dict[str, object] = {}
    for src, objects, material_key in group_targets:
        preview_material = created_materials.get(material_key)
        if preview_material is None:
            preview_material = _ensure_preview_material(
                src["image"],
                str(src.get("map_type") or ""),
                material_suffix=material_key,
            )
            created_materials[material_key] = preview_material
        for obj in objects:
            if _apply_preview_material_to_object(obj, preview_material):
                applied += 1
    return applied


def apply_preview_pbr_output(
    project,
    *,
    group_name: str,
    normal_image=None,
    ao_image=None,
    curvature_image=None,
    albedo_image=None,
    roughness_image=None,
    metalness_image=None,
    emission_image=None,
    opacity_image=None,
    specular_image=None,
    transmission_image=None,
    normal_space: str = "TANGENT",
    normal_format: str = "OPENGL",
    flip_green: bool = False,
    ao_strength: float = 1.0,
) -> int:
    target_group = _find_group(project, group_name)
    if target_group is None:
        restore_preview_materials()
        return 0

    target_objects = list(_iter_low_mesh_objects(target_group))
    if not target_objects:
        restore_preview_materials()
        return 0

    preview_material = _ensure_pbr_preview_material(
        normal_image=normal_image,
        ao_image=ao_image,
        curvature_image=curvature_image,
        albedo_image=albedo_image,
        roughness_image=roughness_image,
        metalness_image=metalness_image,
        emission_image=emission_image,
        opacity_image=opacity_image,
        specular_image=specular_image,
        transmission_image=transmission_image,
        normal_space=normal_space,
        normal_format=normal_format,
        flip_green=flip_green,
        ao_strength=ao_strength,
    )
    _suppress_preview_side_effects()
    restore_preview_materials(exclude_objects=target_objects)

    applied = 0
    for obj in target_objects:
        if _apply_preview_material_to_object(obj, preview_material):
            applied += 1
    return applied


def _group_texture_set_name(group) -> str:
    try:
        from . import properties as _properties
        metadata_state = _properties.group_metadata_state(group)
        return (getattr(metadata_state, "texture_set_name", "") or "").strip()
    except Exception:
        return ""


def apply_preview_pbr_output_all_groups(
    project,
    *,
    per_group_inputs: list,
) -> int:
    all_target_objects = []
    group_targets = []
    for inputs in per_group_inputs:
        group_name = inputs["group_name"]
        target_group = _find_group(project, group_name)
        if target_group is None:
            continue
        objects = list(_iter_low_mesh_objects(target_group))
        if not objects:
            continue
        texture_set = _group_texture_set_name(target_group)
        # Same rule as the single-map path: two groups share ONE preview material
        # only when they share the texture set AND every resolved image. Keyed on
        # the set alone, the second group showed the first group's channel set.
        import hashlib

        image_tokens = "|".join(
            _image_key_token(inputs.get(key))
            for key in (
                "normal_image", "ao_image", "curvature_image", "albedo_image",
                "roughness_image", "metalness_image", "emission_image",
                "opacity_image", "specular_image", "transmission_image",
            )
        )
        material_suffix = "{}#{}".format(
            texture_set if texture_set else group_name,
            hashlib.blake2b(image_tokens.encode("utf-8"), digest_size=4).hexdigest(),
        )
        group_targets.append((inputs, objects, material_suffix))
        all_target_objects.extend(objects)

    if not group_targets:
        restore_preview_materials()
        return 0

    _suppress_preview_side_effects()
    restore_preview_materials(exclude_objects=all_target_objects)

    applied = 0
    created_materials: dict[str, object] = {}
    for inputs, objects, material_suffix in group_targets:
        preview_material = created_materials.get(material_suffix)
        if preview_material is None:
            preview_material = _ensure_pbr_preview_material(
                normal_image=inputs.get("normal_image"),
                ao_image=inputs.get("ao_image"),
                curvature_image=inputs.get("curvature_image"),
                albedo_image=inputs.get("albedo_image"),
                roughness_image=inputs.get("roughness_image"),
                metalness_image=inputs.get("metalness_image"),
                emission_image=inputs.get("emission_image"),
                opacity_image=inputs.get("opacity_image"),
                specular_image=inputs.get("specular_image"),
                transmission_image=inputs.get("transmission_image"),
                normal_space=inputs.get("normal_space", "TANGENT"),
                normal_format=inputs.get("normal_format", "OPENGL"),
                flip_green=inputs.get("flip_green", False),
                ao_strength=inputs.get("ao_strength", 1.0),
                material_suffix=material_suffix,
            )
            created_materials[material_suffix] = preview_material
        for obj in objects:
            if _apply_preview_material_to_object(obj, preview_material):
                applied += 1
    return applied


def register() -> None:
    return None


def unregister() -> None:
    restore_preview_materials()
