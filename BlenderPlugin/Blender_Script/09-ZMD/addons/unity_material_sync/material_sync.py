import os
from dataclasses import dataclass, field


TEMPLATE_TEXTURE_SLOTS = {
    "color": ("color", "basecolor", "base_color"),
    "nro": ("nro", "normalroughnessocclusion"),
    "mask": ("mask", "三通道mask"),
    "emissive": ("自发光", "emissive"),
    "macro_normal": ("本体法线", "macronormal"),
}
REQUIRED_TEMPLATE_TEXTURE_SLOTS = {"color", "nro"}


@dataclass
class MaterialSyncResult:
    updated_textures: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class MaterialSyncError(RuntimeError):
    pass


def apply_material_data(material, data, image_loader=None):
    result = MaterialSyncResult()
    textures = data.get("textures", {})
    if not _has_template_texture_nodes(material):
        raise MaterialSyncError("模板材质缺少贴图节点：Color、NRO 或 Mask")

    _apply_template_textures(material, textures, image_loader, result)
    _apply_shader_parameters(material, data.get("parameters", {}))
    return result


def _has_template_texture_nodes(material):
    return any(
        _find_template_texture_nodes(material, slot_name)
        for slot_name in TEMPLATE_TEXTURE_SLOTS
    )


def _apply_template_textures(material, textures, image_loader, result):
    for slot_name in ("color", "nro", "mask", "emissive", "macro_normal"):
        nodes = _find_template_texture_nodes(material, slot_name)
        if not nodes:
            if slot_name in REQUIRED_TEMPLATE_TEXTURE_SLOTS:
                raise MaterialSyncError(f"模板材质缺少贴图节点：{slot_name}")
            continue

        texture_path = textures.get(slot_name)
        if not texture_path:
            for node in nodes:
                node.image = None
            result.warnings.append(f"Unity 返回缺少贴图：{slot_name}")
            continue

        if not os.path.exists(texture_path):
            for node in nodes:
                node.image = None
            result.warnings.append(f"贴图不存在：{texture_path}")
            continue

        image = _load_image(texture_path, image_loader)
        for node in nodes:
            node.image = image
            _set_channel_packed_alpha(image)
            if slot_name in {"nro", "mask", "macro_normal"}:
                _set_non_color_space(image)
            else:
                _set_color_space(image, "sRGB")
        result.updated_textures.append(slot_name)


def _find_template_texture_nodes(material, slot_name):
    aliases = TEMPLATE_TEXTURE_SLOTS[slot_name]
    nodes = []
    for node in material.node_tree.nodes:
        if not _is_image_texture_node(node):
            continue

        node_names = (
            getattr(node, "name", ""),
            getattr(node, "label", ""),
        )
        normalized_names = tuple(_normalize_node_name(name) for name in node_names)
        if any(alias in normalized_names for alias in aliases):
            nodes.append(node)

    return nodes


def _is_image_texture_node(node):
    return getattr(node, "type", None) in {"TEX_IMAGE", "ShaderNodeTexImage"}


def _normalize_node_name(name):
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _apply_shader_parameters(material, parameters):
    base_color = parameters.get("base_color", {}) if isinstance(parameters, dict) else {}
    nro = parameters.get("nro", {}) if isinstance(parameters, dict) else {}
    pbr = parameters.get("pbr", {}) if isinstance(parameters, dict) else {}
    emissive = parameters.get("emissive", {}) if isinstance(parameters, dict) else {}
    trichannel_blend = parameters.get("trichannel_blend", {}) if isinstance(parameters, dict) else {}
    alpha_test = parameters.get("alpha_test", {}) if isinstance(parameters, dict) else {}
    if not base_color and not nro and not pbr and not emissive and not trichannel_blend and not alpha_test:
        return

    for shader_node in _find_shader_nodes(material):
        if base_color:
            _set_input_value(shader_node, "Color_Tiling", base_color.get("tiling"))
            _set_input_value(shader_node, "Color_Offset", base_color.get("offset"))
            _set_input_value(shader_node, "Color_UV通道", base_color.get("uv_set"))
            _set_input_value(shader_node, "Color_底色", base_color.get("color"))
            _set_input_value(shader_node, "Color_底色覆盖贴图颜色", base_color.get("tint_cover"))
            _set_input_value(shader_node, "Color_固有色变亮", base_color.get("brighter_scale"))

        if nro:
            _set_input_value(shader_node, "NRO_Tiling", nro.get("tiling"))
            _set_input_value(shader_node, "NRO_Offset", nro.get("offset"))
            _set_input_value(shader_node, "NRO_UV通道", nro.get("uv_set"))
            _set_input_value(shader_node, "NRO_法线贴图强度", nro.get("normal_scale"))
            _set_input_value(shader_node, "NRO_双面材质反转背面法线", nro.get("two_sided_normal"))
            _set_input_value(shader_node, "NRO_使用本体法线", nro.get("use_macro_normal"))
            _set_input_value(shader_node, "本体法线贴图强度", nro.get("macro_normal_scale"))
            _set_input_value(shader_node, "本体法线AO强度", nro.get("macro_normal_ao_strength"))

        if pbr:
            _set_input_value(shader_node, "PBR_Specular(Default 0.5)", pbr.get("specular"))
            _set_input_value(shader_node, "PBR_最小粗糙度", pbr.get("roughness_min"))
            _set_input_value(shader_node, "PBR_最大粗糙度", pbr.get("roughness_max"))
            _set_input_value(shader_node, "PBR_AO强度", pbr.get("occlusion_strength"))

        if emissive:
            _set_input_value(shader_node, "自发光_通道", emissive.get("channel"))
            _set_input_value(shader_node, "自发光_UV", emissive.get("uv_set"))
            _set_input_value(shader_node, "自发光_UV通道", emissive.get("uv_set"))
            _set_input_value(shader_node, "自发光_不受固有色影响", emissive.get("albedo_affect_emissive"))
            _set_input_value(shader_node, "自发光_颜色", emissive.get("color"))
            _set_input_value(shader_node, "自发光_Emissive Speed", emissive.get("speed"))

        if trichannel_blend:
            _set_input_value(shader_node, "混合_Tiling", trichannel_blend.get("tiling"))
            _set_input_value(shader_node, "混合_Offset", trichannel_blend.get("offset"))
            _set_input_value(shader_node, "混合_UV通道", trichannel_blend.get("uv_set"))
            _set_input_value(shader_node, "混合_三通道Mask贴图 - 仅PC", trichannel_blend.get("pc_texture"))
            _set_input_value(shader_node, "混合_Mask R Color", trichannel_blend.get("mask_r_color"))
            _set_input_value(shader_node, "混合_Mask R Scale", trichannel_blend.get("mask_r_scale"))
            _set_input_value(shader_node, "混合_Mask R Offset", trichannel_blend.get("mask_r_offset"))
            _set_input_value(shader_node, "混合_Mask R Roughness", trichannel_blend.get("mask_r_roughness"))
            _set_input_value(shader_node, "混合_Mask R Metallic", trichannel_blend.get("mask_r_metallic"))
            _set_input_value(shader_node, "混合_Mask G Color", trichannel_blend.get("mask_g_color"))
            _set_input_value(shader_node, "混合_Mask G Scale", trichannel_blend.get("mask_g_scale"))
            _set_input_value(shader_node, "混合_Mask G Offset", trichannel_blend.get("mask_g_offset"))
            _set_input_value(shader_node, "混合_Mask G Roughness", trichannel_blend.get("mask_g_roughness"))
            _set_input_value(shader_node, "混合_Mask G Metallic", trichannel_blend.get("mask_g_metallic"))
            _set_input_value(shader_node, "混合_Mask B Color", trichannel_blend.get("mask_b_color"))
            _set_input_value(shader_node, "混合_Mask B Scale", trichannel_blend.get("mask_b_scale"))
            _set_input_value(shader_node, "混合_Mask B Offset", trichannel_blend.get("mask_b_offset"))
            _set_input_value(shader_node, "混合_Mask B Roughness", trichannel_blend.get("mask_b_roughness"))
            _set_input_value(shader_node, "混合_Mask B Metallic", trichannel_blend.get("mask_b_metallic"))

        if alpha_test:
            _set_input_value(shader_node, "透贴_通道", alpha_test.get("channel"))
            _set_input_value(shader_node, "透贴_Clip Threshold", alpha_test.get("clip_threshold"))


def _find_shader_nodes(material):
    nodes = []
    for node in material.node_tree.nodes:
        node_names = (
            getattr(node, "name", ""),
            getattr(node, "label", ""),
        )
        normalized_names = tuple(_normalize_node_name(name) for name in node_names)
        if "shader" in normalized_names:
            nodes.append(node)
    return nodes


def _set_input_value(node, input_name, value):
    if value is None:
        return

    socket = _get_input_socket(node, input_name)
    if socket is None:
        return

    try:
        socket.default_value = value
    except TypeError:
        if isinstance(value, tuple):
            socket.default_value = list(value)


def _get_input_socket(node, input_name):
    inputs = getattr(node, "inputs", {})
    if hasattr(inputs, "get"):
        return inputs.get(input_name)
    try:
        return inputs[input_name]
    except (KeyError, TypeError):
        return None


def _load_image(texture_path, image_loader):
    if image_loader is not None:
        return image_loader(texture_path)

    try:
        import bpy
    except ImportError:
        return None

    return bpy.data.images.load(texture_path, check_existing=True)


def _set_non_color_space(image):
    _set_color_space(image, "Non-Color")


def _set_channel_packed_alpha(image):
    if image is not None and hasattr(image, "alpha_mode"):
        image.alpha_mode = "CHANNEL_PACKED"


def _set_color_space(image, color_space):
    colorspace_settings = getattr(image, "colorspace_settings", None)
    if colorspace_settings is not None and hasattr(colorspace_settings, "name"):
        colorspace_settings.name = color_space


