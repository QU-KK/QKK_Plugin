import os
import re


TEMPLATE_BLEND_FILENAME = "ZMD_Lit_Two.blend"
BLENDER_DUPLICATE_SUFFIX_RE = re.compile(r"\.\d{3}$")


class TemplateMaterialError(RuntimeError):
    pass


def template_blend_path():
    return os.path.join(os.path.dirname(__file__), TEMPLATE_BLEND_FILENAME)


def ensure_template_material_for_slot(slot, material_name, material_loader=None, bpy_module=None):
    bpy = bpy_module or _import_bpy()
    loader = material_loader or load_template_material
    template = loader()
    if template is None:
        raise TemplateMaterialError("模板材质加载失败")

    original = getattr(slot, "material", None)
    target_material_name = _material_base_name(material_name)

    template_copy = template.copy()
    template_copy.name = f"{target_material_name}_sync_tmp"
    replaced_node_groups = _reuse_template_node_groups(template_copy, bpy)

    material = template_copy
    replaced_users = _replace_material_users(original, material, bpy)
    if original is None or replaced_users == 0:
        slot.material = material

    _remove_material_if_unused(original, bpy)
    _remove_material_if_unused(template, bpy)
    for node_group in replaced_node_groups:
        _remove_node_group_if_unused(node_group, bpy)
    material.name = target_material_name
    return material


def load_template_material(bpy_module=None, blend_path=None, material_name=None):
    blend_path = blend_path or template_blend_path()
    if not os.path.exists(blend_path):
        raise TemplateMaterialError(f"模板材质文件不存在：{blend_path}")

    bpy = bpy_module or _import_bpy()
    return _append_template_material(bpy, blend_path, material_name)


def _import_bpy():
    try:
        import bpy
    except ImportError as exc:
        raise TemplateMaterialError("当前环境无法访问 Blender bpy 模块") from exc
    return bpy


def _append_template_material(bpy, blend_path, material_name):
    with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
        available_materials = list(data_from.materials)
        if not available_materials:
            raise TemplateMaterialError(f"模板材质文件中没有材质：{blend_path}")

        selected_material_name = material_name or available_materials[0]
        if selected_material_name not in available_materials:
            raise TemplateMaterialError(
                f"模板材质文件中找不到材质“{selected_material_name}”：{blend_path}"
            )

        data_to.materials = [selected_material_name]

    material = data_to.materials[0] if data_to.materials else None
    if material is None:
        raise TemplateMaterialError(f"模板材质加载失败：{blend_path}")

    return material


def _remove_material_if_unused(material, bpy):
    if material is None:
        return
    if getattr(material, "users", 0) > 0:
        return

    materials = getattr(getattr(bpy, "data", None), "materials", None)
    remove = getattr(materials, "remove", None)
    if remove is None:
        return

    try:
        remove(material)
    except (ReferenceError, RuntimeError):
        return


def _replace_material_users(old_material, new_material, bpy):
    if old_material is None or new_material is None or old_material is new_material:
        return 0

    user_remap = getattr(old_material, "user_remap", None)
    if user_remap is not None:
        before_users = getattr(old_material, "users", 0)
        user_remap(new_material)
        return before_users

    replaced_count = 0
    objects = getattr(getattr(bpy, "data", None), "objects", [])
    for obj in objects:
        for slot in getattr(obj, "material_slots", []):
            if getattr(slot, "material", None) is old_material:
                slot.material = new_material
                replaced_count += 1
                if getattr(old_material, "users", 0) > 0:
                    old_material.users -= 1
                if hasattr(new_material, "users"):
                    new_material.users += 1
    return replaced_count


def _material_base_name(name):
    return BLENDER_DUPLICATE_SUFFIX_RE.sub("", str(name))


def _reuse_template_node_groups(material, bpy):
    replaced_node_groups = []
    for node in _iter_group_nodes(material):
        current = getattr(node, "node_tree", None)
        if current is None:
            continue

        reusable = _find_reusable_node_group(bpy, current)
        if reusable is not None and reusable is not current:
            replaced_node_groups.append(current)
            node.node_tree = reusable
        else:
            _restore_node_group_base_name_if_available(bpy, current)

    return replaced_node_groups


def _iter_group_nodes(material):
    node_tree = getattr(material, "node_tree", None)
    nodes = getattr(node_tree, "nodes", [])
    for node in nodes:
        if getattr(node, "type", None) != "GROUP":
            continue
        if getattr(node, "node_tree", None) is not None:
            yield node


def _find_reusable_node_group(bpy, current):
    node_groups = getattr(getattr(bpy, "data", None), "node_groups", None)
    if node_groups is None:
        return None

    base_name = _node_group_base_name(getattr(current, "name", ""))
    exact_match = None
    fallback_match = None

    for node_group in node_groups:
        if node_group is current:
            continue
        if not _node_group_has_same_identity(node_group, base_name, current):
            continue
        if getattr(node_group, "name", None) == base_name:
            exact_match = node_group
            break
        if fallback_match is None:
            fallback_match = node_group
    return exact_match or fallback_match


def _restore_node_group_base_name_if_available(bpy, node_group):
    base_name = _node_group_base_name(getattr(node_group, "name", ""))
    if not base_name or getattr(node_group, "name", None) == base_name:
        return
    if _find_node_group_with_name(bpy, base_name) is not None:
        return
    node_group.name = base_name


def _find_node_group_with_name(bpy, name):
    node_groups = getattr(getattr(bpy, "data", None), "node_groups", None)
    if node_groups is None:
        return None
    get = getattr(node_groups, "get", None)
    if get is not None:
        return get(name)

    for node_group in node_groups:
        if getattr(node_group, "name", None) == name:
            return node_group
    return None


def _node_group_has_same_identity(node_group, base_name, current):
    if _node_group_base_name(getattr(node_group, "name", "")) != base_name:
        return False
    return _node_group_type_key(node_group) == _node_group_type_key(current)


def _node_group_base_name(name):
    return BLENDER_DUPLICATE_SUFFIX_RE.sub("", str(name))


def _node_group_type_key(node_group):
    return (
        getattr(node_group, "type", None),
        getattr(node_group, "bl_idname", None),
    )


def _remove_node_group_if_unused(node_group, bpy):
    if node_group is None:
        return
    if getattr(node_group, "users", 0) > 0:
        return

    node_groups = getattr(getattr(bpy, "data", None), "node_groups", None)
    remove = getattr(node_groups, "remove", None)
    if remove is None:
        return

    try:
        remove(node_group)
    except (ReferenceError, RuntimeError):
        return
