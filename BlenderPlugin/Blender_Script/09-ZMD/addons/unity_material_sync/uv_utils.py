UNITY_UV_NAMES = ("1U", "2U")


def ensure_unity_uv_names(obj):
    uv_layers = list(getattr(getattr(obj, "data", None), "uv_layers", []) or [])
    if not uv_layers:
        return []

    rename_count = min(len(uv_layers), len(UNITY_UV_NAMES))
    target_names = UNITY_UV_NAMES[:rename_count]

    _clear_conflicting_uv_names(uv_layers, target_names, rename_count)

    renamed = []
    for index, target_name in enumerate(target_names):
        layer = uv_layers[index]
        old_name = layer.name
        if old_name != target_name:
            layer.name = target_name
            renamed.append((old_name, target_name))

    return renamed


def _clear_conflicting_uv_names(uv_layers, target_names, rename_count):
    target_name_set = set(target_names)
    for index, layer in enumerate(uv_layers):
        if index < rename_count:
            continue
        if layer.name in target_name_set:
            layer.name = _temporary_uv_name(index, uv_layers)

    for index, layer in enumerate(uv_layers[:rename_count]):
        intended_name = target_names[index]
        if layer.name in target_name_set and layer.name != intended_name:
            layer.name = _temporary_uv_name(index, uv_layers)


def _temporary_uv_name(index, uv_layers):
    existing_names = {layer.name for layer in uv_layers}
    candidate = f"__unity_material_sync_uv_{index}__"
    suffix = 1
    while candidate in existing_names:
        candidate = f"__unity_material_sync_uv_{index}_{suffix}__"
        suffix += 1
    return candidate
