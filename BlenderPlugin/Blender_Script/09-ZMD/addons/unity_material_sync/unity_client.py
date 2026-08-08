import asyncio
import json
import os
import re
import socket
import sys
from urllib.parse import urlparse


DEFAULT_NATS_URL = "nats://127.0.0.1:14222"
DEFAULT_TIMEOUT = 3.0
NATS_PREFLIGHT_TIMEOUT = 1.0
SERVICE_INFO_SUBJECT = "$SRV.INFO.FlowEngine"
REQUEST_MSG_TYPE = "ScenePrefabMatInfos"
VENDOR_DIR = os.path.join(os.path.dirname(__file__), "vendor")
WORKSPACE_DIR_RESPONSE_KEY = "_unity_workspace_dir"
LOD_SUFFIX_RE = re.compile(r"_lod\d+$", re.IGNORECASE)
BLENDER_DUPLICATE_SUFFIX_RE = re.compile(r"\.\d{3}$")


class UnityClientError(RuntimeError):
    pass


def sanitize(name):
    return name.replace(".", "_").replace("*", "_").replace(">", "_").replace(" ", "_")


def prefab_name_from_model_name(model_name):
    base_name = model_name_without_lod_suffix(model_name)
    if base_name.startswith("SK_"):
        return "P_" + base_name[3:]
    if base_name.startswith("S_"):
        return "P_" + base_name[2:]
    return base_name


def prefab_name_query_candidates(prefab_name):
    candidates = []
    for name in (prefab_name, _prefab_without_exported_instance_suffix(prefab_name)):
        if not name:
            continue
        _append_unique(candidates, name)
        plus_variant = _prefab_plus_variant(name)
        if plus_variant:
            _append_unique(candidates, plus_variant)
    return candidates


def validate_lod_model_name(model_name):
    if not LOD_SUFFIX_RE.search(model_name):
        raise UnityClientError(
            f"模型“{model_name}”不符合同步规则：名称需要以 _lod数字 结尾，例如 _lod0"
        )


def model_name_without_lod_suffix(model_name):
    return LOD_SUFFIX_RE.sub("", model_name)


def _prefab_plus_variant(prefab_name):
    if "+" in prefab_name:
        return ""
    match = re.match(r"^(.*?_[^_]+)_(\d)(_\d+_\d+.*)$", prefab_name)
    if not match:
        return ""
    return f"{match.group(1)}+{match.group(2)}{match.group(3)}"


def _prefab_without_exported_instance_suffix(prefab_name):
    stripped = re.sub(r"__\d+_$", "", prefab_name)
    if stripped == prefab_name:
        return ""
    return stripped


def _append_unique(values, value):
    if value not in values:
        values.append(value)


def material_match_name(material_name):
    if not material_name:
        return ""
    without_duplicate_suffix = BLENDER_DUPLICATE_SUFFIX_RE.sub("", material_name)
    normalized = re.sub(r"[^0-9a-zA-Z]+", "_", without_duplicate_suffix)
    return normalized.strip("_").lower()


def build_prefab_material_request_payload(prefab_name):
    return {
        "MsgType": REQUEST_MSG_TYPE,
        "MsgBody": json.dumps({"prefab_name": prefab_name}, ensure_ascii=False),
    }


def fetch_material(material_name, material_infos=None, texture_root="", material_index=None):
    if material_infos is None:
        raise UnityClientError("尚未获得 Unity 返回的材质数据")

    texture_root = texture_root or workspace_dir_from_material_infos(material_infos)
    selected = select_material_info(
        material_infos,
        material_name,
        texture_root=texture_root,
    )
    if selected is None:
        selected = select_material_info_by_index(
            material_infos,
            material_index,
            texture_root=texture_root,
        )
    if selected is None:
        available_names = list_material_names(material_infos)
        if available_names:
            names = "、".join(available_names)
            raise UnityClientError(
                f"返回结果中找不到材质“{material_name}”。Unity 返回的材质有：{names}"
            )
        raise UnityClientError(f"返回结果中找不到材质“{material_name}”，且 Unity 返回中没有可识别的材质列表")

    return selected


def workspace_dir_from_material_infos(material_infos):
    decoded = _decode_nested_json(material_infos)
    if isinstance(decoded, dict):
        return decoded.get(WORKSPACE_DIR_RESPONSE_KEY, "")
    return ""


def validate_material_infos_response(response, prefab_name):
    decoded = _decode_nested_json(response)
    if isinstance(decoded, dict) and decoded.get("error"):
        raise UnityClientError(f"Unity 返回错误（prefab：{prefab_name}）：{decoded['error']}")


def list_material_names(response):
    names = []
    for candidate in _iter_material_candidates(_decode_nested_json(response)):
        name = candidate.get("name") or candidate.get("material_name") or candidate.get("mat_name")
        if name and name not in names:
            names.append(name)
    return names


def select_material_info_by_index(response, material_index, texture_root=""):
    if material_index is None:
        return None

    candidates = list(_iter_material_candidates(_decode_nested_json(response)))
    if material_index < 0 or material_index >= len(candidates):
        return None

    candidate = candidates[material_index]
    return _normalize_material_info(candidate, material_match_name(str(material_index)), texture_root)


def fetch_material_infos_for_prefab(prefab_name, nats_url=DEFAULT_NATS_URL, timeout=DEFAULT_TIMEOUT):
    return asyncio.run(_fetch_material_infos_for_prefab_async(prefab_name, nats_url, timeout))


async def _fetch_material_infos_for_prefab_async(
    prefab_name,
    nats_url,
    timeout,
    connector=socket.create_connection,
):
    nats = _import_nats()
    ensure_nats_endpoint_reachable(nats_url, timeout=timeout, connector=connector)

    try:
        nc = await nats.connect(
            nats_url,
            allow_reconnect=False,
            connect_timeout=min(timeout, NATS_PREFLIGHT_TIMEOUT),
            max_reconnect_attempts=0,
        )
    except Exception as exc:
        raise UnityClientError(
            diagnose_nats_connection(nats_url, timeout=timeout, original_error=exc)
        ) from exc

    try:
        request_subject, workspace_dir = await _find_first_request_target(nc, timeout)
        payload = build_prefab_material_request_payload(prefab_name)
        msg = await nc.request(
            request_subject,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=timeout,
        )
        response = _decode_json_payload(msg.data)
        validate_material_infos_response(response, prefab_name)
        if isinstance(response, dict) and workspace_dir:
            response[WORKSPACE_DIR_RESPONSE_KEY] = workspace_dir
        return response
    finally:
        await nc.close()


def ensure_nats_endpoint_reachable(nats_url, timeout=DEFAULT_TIMEOUT, connector=socket.create_connection):
    message = diagnose_nats_connection(
        nats_url,
        timeout=min(timeout, NATS_PREFLIGHT_TIMEOUT),
        connector=connector,
    )
    if not message.startswith("TCP 端口可连接"):
        raise UnityClientError(message)


def diagnose_nats_connection(
    nats_url,
    timeout=DEFAULT_TIMEOUT,
    original_error=None,
    connector=socket.create_connection,
):
    parsed = _parse_nats_url(nats_url)
    if parsed is None:
        return (
            f"通信地址格式不支持：{nats_url}。"
            "请确认地址形如 nats://127.0.0.1:14222。"
        )

    host, port = parsed
    endpoint = f"{host}:{port}"
    try:
        connection = connector((host, port), timeout=timeout)
    except (TimeoutError, socket.timeout):
        return (
            f"连接 FlowServer 超时：无法在 {timeout} 秒内连接到 {endpoint}。"
            "请确认 FlowServer 89.0+ 已启动，并且当前机器可以访问该端口。"
        )
    except ConnectionRefusedError:
        return (
            f"连接 FlowServer 被拒绝：{endpoint} 没有服务监听。"
            "请确认 FlowServer 89.0+ 已启动。"
        )
    except OSError as exc:
        return (
            f"连接 FlowServer 失败：无法访问 {endpoint}（{exc}）。"
            "请确认 FlowServer 89.0+ 已启动，且防火墙没有拦截该端口。"
        )
    else:
        close = getattr(connection, "close", None)
        if close:
            close()

    if original_error is not None:
        return (
            f"TCP 端口可连接（{endpoint}），但 NATS 握手失败：{original_error}。"
            "请确认该端口确实是 FlowServer/NATS 服务，且 FlowServer 版本为 89.0+。"
        )

    return f"TCP 端口可连接（{endpoint}）。"


def _parse_nats_url(nats_url):
    first_url = str(nats_url).split(",", 1)[0].strip()
    parsed = urlparse(first_url)
    if parsed.scheme not in {"nats", "tls"}:
        return None
    if not parsed.hostname or not parsed.port:
        return None
    return parsed.hostname, parsed.port


def _import_nats():
    if os.path.isdir(VENDOR_DIR) and VENDOR_DIR not in sys.path:
        sys.path.insert(0, VENDOR_DIR)

    try:
        import nats
    except ImportError as exc:
        raise UnityClientError(
            f"插件缺少 nats 依赖，请确认 vendor 目录存在：{VENDOR_DIR}"
        ) from exc

    return nats


async def _find_first_request_target(nc, timeout):
    inbox = nc.new_inbox()
    sub = await nc.subscribe(inbox)
    await nc.publish(SERVICE_INFO_SUBJECT, b"", reply=inbox)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(sub.next_msg(), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise UnityClientError(
                    "没有检测到 Unity 客户端。请确认 FlowServer 89.0+ 已启动，"
                    "Unity 工程已打开，并且 Unity 客户端已连接到 FlowServer。"
                ) from exc

            if not msg.data:
                continue

            service = _decode_json_payload(msg.data)
            target = request_target_from_service_info(service)
            if target is not None:
                return target
    finally:
        await sub.unsubscribe()


def request_target_from_service_info(service):
    meta = service.get("metadata", {}) if isinstance(service, dict) else {}
    workspace = meta.get("workspace", "")
    sanitized = meta.get("sanitized") or sanitize(workspace)
    if not sanitized:
        return None
    return f"flow.request.{sanitized}", meta.get("workspace_dir", "")


def select_material_info(response, material_name, texture_root=""):
    candidates = _iter_material_candidates(_decode_nested_json(response))
    expected_name = material_match_name(material_name)
    for candidate in candidates:
        name = candidate.get("name") or candidate.get("material_name") or candidate.get("mat_name")
        if material_match_name(name) == expected_name:
            return _normalize_material_info(candidate, material_name, texture_root)
    return None


def _iter_material_candidates(value):
    if isinstance(value, dict):
        if _looks_like_material_info(value):
            yield value
        for child in value.values():
            yield from _iter_material_candidates(_decode_nested_json(child))
    elif isinstance(value, list):
        for item in value:
            yield from _iter_material_candidates(_decode_nested_json(item))


def _looks_like_material_info(value):
    keys = {str(key).lower() for key in value.keys()}
    return bool(keys & {"name", "material_name", "mat_name"}) and (
        "properties" in keys
        or "textures" in keys
        or bool(keys & {"color", "nro", "mask"})
    )


def _normalize_material_info(info, default_name, texture_root=""):
    properties = info.get("properties", [])
    textures = _extract_textures_from_properties(properties)
    textures.update(info.get("textures", info))
    normalized_textures = {}
    for source_key, target_key in (
        ("color", "color"),
        ("Color", "color"),
        ("COLOR", "color"),
        ("nro", "nro"),
        ("NRO", "nro"),
        ("mask", "mask"),
        ("Mask", "mask"),
        ("MASK", "mask"),
        ("emissive", "emissive"),
        ("Emissive", "emissive"),
        ("EMISSIVE", "emissive"),
        ("macro_normal", "macro_normal"),
        ("MacroNormal", "macro_normal"),
        ("MACRONORMAL", "macro_normal"),
    ):
        value = textures.get(source_key) if isinstance(textures, dict) else None
        if value:
            normalized_textures[target_key] = resolve_texture_path(value, texture_root)

    return {
        "name": info.get("name") or info.get("material_name") or info.get("mat_name") or default_name,
        "textures": normalized_textures,
        "parameters": _extract_parameters_from_properties(properties),
    }


def resolve_texture_path(texture_path, texture_root=""):
    if not texture_path or os.path.isabs(texture_path):
        return texture_path

    normalized = texture_path.replace("\\", "/")
    if normalized.startswith(("Assets/", "Packages/")):
        if not texture_root:
            raise UnityClientError(
                f"Unity 返回了工程相对贴图路径“{texture_path}”，但客户端 metadata 缺少 workspace_dir"
            )
        return os.path.normpath(os.path.join(texture_root, normalized))

    return texture_path


def _extract_textures_from_properties(properties):
    textures = {}
    if not isinstance(properties, list):
        return textures

    property_to_slot = {
        "_BaseColorMap": "Color",
        "_NormalMap": "NRO",
        "_MaskMap": "Mask",
        "_EmissiveMap": "Emissive",
        "_MacroNormalMap": "MacroNormal",
    }
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        if prop.get("property_type") != "Texture":
            continue

        slot_name = property_to_slot.get(prop.get("property"))
        if slot_name is None:
            continue

        value = prop.get("value")
        if not isinstance(value, dict):
            continue

        texture_path = value.get("texture_path")
        if texture_path:
            textures[slot_name] = texture_path

    return textures


def _extract_parameters_from_properties(properties):
    if not isinstance(properties, list):
        return {}

    by_name = {
        prop.get("property"): prop.get("value")
        for prop in properties
        if isinstance(prop, dict)
    }
    return {
        "base_color": {
            "tiling": _first_vector2_value(
                by_name,
                ("_BaseColorMapTiling", "_BaseColorMapTilling", "_BaseColorTiling", "_BaseColorTilling"),
                _texture_scale_value(by_name.get("_BaseColorMap"), [1.0, 1.0]),
            ),
            "offset": _first_vector2_value(
                by_name,
                ("_BaseColorMapOffset", "_BaseColorOffset"),
                _texture_offset_value(by_name.get("_BaseColorMap"), [0.0, 0.0]),
            ),
            "uv_set": _uv_set_name(
                _first_existing_value(
                    by_name,
                    ("_BaseUVSet",),
                    _texture_uv_set_value(by_name.get("_BaseColorMap")),
                )
            ),
            "color": _color_value(by_name.get("_BaseColor"), [1.0, 1.0, 1.0, 1.0]),
            "tint_cover": _float_value(by_name.get("_BaseColorTintCover"), 0.0),
            "brighter_scale": _float_value(by_name.get("_BaseColorBrighterScale"), 1.0),
        },
        "nro": {
            "tiling": _first_vector2_value(
                by_name,
                ("_NormalMapTiling", "_NormalMapTilling", "_BasePbrMapTiling", "_BasePbrMapTilling"),
                _texture_scale_value(by_name.get("_NormalMap"), [1.0, 1.0]),
            ),
            "offset": _first_vector2_value(
                by_name,
                ("_NormalMapOffset", "_BasePbrMapOffset"),
                _texture_offset_value(by_name.get("_NormalMap"), [0.0, 0.0]),
            ),
            "uv_set": _uv_set_name(
                _first_existing_value(
                    by_name,
                    ("_BasePbrMapUVSet",),
                    _texture_uv_set_value(by_name.get("_NormalMap")),
                )
            ),
            "normal_scale": _float_value(by_name.get("_NormalScale"), 1.0),
            "two_sided_normal": _bool_value(by_name.get("_TwoSidedNormal"), False),
            "use_macro_normal": _macro_normal_use_name(by_name.get("_UseMacroNormalMap")),
            "macro_normal_scale": _float_value(by_name.get("_MacroNormalMapScale"), 1.0),
            "macro_normal_ao_strength": _float_value(by_name.get("_MacroNormalMapAOStrength"), 0.0),
        },
        "pbr": {
            "specular": _float_value(by_name.get("_Specular"), 0.5),
            "roughness_min": _float_value(by_name.get("_RoughnessMin"), 0.0),
            "roughness_max": _float_value(by_name.get("_RoughnessMax"), 1.0),
            "occlusion_strength": _float_value(by_name.get("_OcclusionStrength"), 1.0),
        },
        "emissive": {
            "channel": _emissive_channel_name(
                by_name.get("_EnableEmissiveMap"),
                by_name.get("_EmissiveMaskChannel"),
            ),
            "uv_set": _uv_set_name(
                _first_existing_value(
                    by_name,
                    ("_EmissiveUVSet",),
                    _texture_uv_set_value(by_name.get("_EmissiveMap")),
                )
            ),
            "albedo_affect_emissive": _bool_value(by_name.get("_AlbedoAffectEmissive"), False),
            "color": _hdr_color_value(by_name.get("_EmissiveColor"), [1.0, 1.0, 1.0, 1.0]),
            "speed": _vector4_value(by_name.get("_EmissiveSpeed"), [0.0, 0.0, 0.0, 0.0]),
        },
        "trichannel_blend": {
            "tiling": _first_vector2_value(
                by_name,
                ("_MaskMapTiling", "_MaskMapTilling", "_MaskTiling", "_MaskTilling"),
                _texture_scale_value(by_name.get("_MaskMap"), [1.0, 1.0]),
            ),
            "offset": _first_vector2_value(
                by_name,
                ("_MaskMapOffset", "_MaskOffset"),
                _texture_offset_value(by_name.get("_MaskMap"), [0.0, 0.0]),
            ),
            "uv_set": _uv_set_name(
                _first_existing_value(
                    by_name,
                    ("_MaskUVSet",),
                    _texture_uv_set_value(by_name.get("_MaskMap")),
                )
            ),
            "pc_texture": _trichannel_pc_texture_name(
                by_name.get("_EnableTriChannelMask"),
                by_name.get("_SwitchTriChannelTexture"),
            ),
            "mask_r_color": _color_value(by_name.get("_MaskAlbedoR"), [1.0, 0.0, 0.0, 1.0]),
            "mask_r_scale": _float_value(by_name.get("_MaskRScale"), 0.0),
            "mask_r_offset": _float_value(by_name.get("_MaskROffset"), 0.0),
            "mask_r_roughness": _float_value(by_name.get("_MaskRoghnessR"), 0.0),
            "mask_r_metallic": _float_value(by_name.get("_MaskMetallicR"), 0.0),
            "mask_g_color": _color_value(by_name.get("_MaskAlbedoG"), [0.0, 1.0, 0.0, 1.0]),
            "mask_g_scale": _float_value(by_name.get("_MaskGScale"), 0.0),
            "mask_g_offset": _float_value(by_name.get("_MaskGOffset"), 0.0),
            "mask_g_roughness": _float_value(by_name.get("_MaskRoghnessG"), 0.25),
            "mask_g_metallic": _float_value(by_name.get("_MaskMetallicG"), 0.0),
            "mask_b_color": _color_value(by_name.get("_MaskAlbedoB"), [0.0, 0.0, 1.0, 1.0]),
            "mask_b_scale": _float_value(by_name.get("_MaskBScale"), 0.0),
            "mask_b_offset": _float_value(by_name.get("_MaskBOffset"), 0.0),
            "mask_b_roughness": _float_value(by_name.get("_MaskRoghnessB"), 0.25),
            "mask_b_metallic": _float_value(by_name.get("_MaskMetallicB"), 0.0),
        },
        "alpha_test": {
            "channel": _alpha_test_channel_name(
                by_name.get("_EnableAlphaTest"),
                by_name.get("_AlphaMaskChannel"),
            ),
            "clip_threshold": _float_value(by_name.get("_AlphaClipThreshold"), 0.5),
        },
    }


def _vector2_value(value, default):
    if isinstance(value, dict):
        x = value.get("x", value.get("r", default[0]))
        y = value.get("y", value.get("g", default[1]))
        return [_float_value(x, default[0]), _float_value(y, default[1])]
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [_float_value(value[0], default[0]), _float_value(value[1], default[1])]
    return list(default)


def _first_vector2_value(by_name, names, default):
    for name in names:
        if name in by_name:
            return _vector2_value(by_name.get(name), default)
    return list(default)


def _first_existing_value(by_name, names, default):
    for name in names:
        if name in by_name and by_name.get(name) is not None:
            return by_name.get(name)
    return default


def _texture_scale_value(texture_value, default):
    if isinstance(texture_value, dict):
        return _vector2_value(texture_value.get("m_Scale"), default)
    return list(default)


def _texture_offset_value(texture_value, default):
    if isinstance(texture_value, dict):
        return _vector2_value(texture_value.get("m_Offset"), default)
    return list(default)


def _texture_uv_set_value(texture_value):
    if isinstance(texture_value, dict):
        return texture_value.get("m_UVSetIndex")
    return None


def _vector4_value(value, default):
    if isinstance(value, dict):
        return [
            _float_value(value.get("x", value.get("r")), default[0]),
            _float_value(value.get("y", value.get("g")), default[1]),
            _float_value(value.get("z", value.get("b")), default[2]),
            _float_value(value.get("w", value.get("a")), default[3]),
        ]
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return [
            _float_value(value[0], default[0]),
            _float_value(value[1], default[1]),
            _float_value(value[2], default[2]),
            _float_value(value[3], default[3]),
        ]
    return list(default)


def _color_value(value, default):
    if isinstance(value, dict):
        return [
            _srgb_to_linear(_float_value(value.get("r"), default[0])),
            _srgb_to_linear(_float_value(value.get("g"), default[1])),
            _srgb_to_linear(_float_value(value.get("b"), default[2])),
            _float_value(value.get("a"), default[3]),
        ]
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return [
            _srgb_to_linear(_float_value(value[0], default[0])),
            _srgb_to_linear(_float_value(value[1], default[1])),
            _srgb_to_linear(_float_value(value[2], default[2])),
            _float_value(value[3], default[3]),
        ]
    return [
        _srgb_to_linear(default[0]),
        _srgb_to_linear(default[1]),
        _srgb_to_linear(default[2]),
        default[3],
    ]


def _hdr_color_value(value, default):
    if isinstance(value, dict):
        return [
            _float_value(value.get("r"), default[0]),
            _float_value(value.get("g"), default[1]),
            _float_value(value.get("b"), default[2]),
            _float_value(value.get("a"), default[3]),
        ]
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        return [
            _float_value(value[0], default[0]),
            _float_value(value[1], default[1]),
            _float_value(value[2], default[2]),
            _float_value(value[3], default[3]),
        ]
    return list(default)


def _srgb_to_linear(value):
    value = max(0.0, min(1.0, value))
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _uv_set_name(value):
    try:
        return f"UV{int(value)}"
    except (TypeError, ValueError):
        return "UV0"


def _emissive_channel_name(enable_emissive_map, emissive_mask_channel):
    if not _bool_value(enable_emissive_map, False):
        return "不启用"
    try:
        channel = int(emissive_mask_channel)
    except (TypeError, ValueError):
        channel = 0
    if channel == 0:
        return "Emissive Map"
    if channel == 1:
        return "Base Color A"
    if channel == 3:
        return "Normal Map A"
    return "不启用"


def _trichannel_pc_texture_name(enable_trichannel_mask, switch_value):
    if enable_trichannel_mask is None and switch_value is None:
        return "不启用"
    if enable_trichannel_mask is not None and not _bool_value(enable_trichannel_mask, False):
        return "不启用"

    try:
        mode = int(switch_value)
    except (TypeError, ValueError):
        mode = 0
    return {
        1: "Legacy",
        2: "G With Normal",
    }.get(mode, "Off")


def _macro_normal_use_name(value):
    if _bool_value(value, False):
        return "开启本体法线"
    return "关闭本体法线"


def _alpha_test_channel_name(enable_alpha_test, alpha_mask_channel):
    if not _bool_value(enable_alpha_test, False):
        return "不启用"
    try:
        channel = int(alpha_mask_channel)
    except (TypeError, ValueError):
        channel = 0
    return "NRO_A" if channel == 1 else "Base Color_A"


def _float_value(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bool_value(value, default):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _decode_json_payload(data):
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return _decode_nested_json(json.loads(data))


def _decode_nested_json(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return _decode_nested_json(json.loads(stripped))
            except json.JSONDecodeError:
                return value
    if isinstance(value, dict):
        return {
            key: _decode_nested_json(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_decode_nested_json(child) for child in value]
    return value
