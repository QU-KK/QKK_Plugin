from __future__ import annotations

from . import naming, tagging


def _clean(value) -> str:
    return (str(value).strip() if value is not None else "")


def _group_metadata_state(group):
    try:
        from . import properties as _properties
    except Exception:
        return getattr(group, "metadata", None) or group
    return _properties.group_metadata_state(group)


def _collection_has_baker_metadata(collection) -> bool:
    return (
        tagging.is_tagged(collection)
        or bool(_clean(tagging.get_metadata_group_name(collection)))
        or bool(_clean(tagging.get_metadata_collection_name(collection)))
    )


def _primary_collection(obj):
    collections = [collection for collection in getattr(obj, "users_collection", []) if collection is not None]
    if not collections:
        return None
    # Prefer a collection carrying MasterBaker role/group metadata over an untagged
    # generic one (e.g. Blender's default "Collection"). Objects often live in both
    # their tagged bake-group collection AND a catch-all scene collection; picking the
    # alphabetically-first would derive the group's texture set from the catch-all's
    # name (e.g. "Collection") instead of the real bake collection.
    def _sort_key(collection):
        name = _clean(getattr(collection, "name", ""))
        return (0 if _collection_has_baker_metadata(collection) else 1, name.lower(), name)

    return sorted(collections, key=_sort_key)[0]


def collection_group_metadata(collection) -> dict[str, str]:
    if collection is None:
        return {}

    explicit_texture_set_name = _clean(tagging.get_metadata_group_name(collection))
    explicit_collection_name = _clean(tagging.get_metadata_collection_name(collection)) or _clean(tagging.get_tag_collection_name(collection))
    fallback_collection_name = _clean(getattr(collection, "name", ""))
    texture_set_name = explicit_texture_set_name or explicit_collection_name or fallback_collection_name
    id_collection_name = explicit_collection_name or fallback_collection_name or texture_set_name

    if not texture_set_name and not id_collection_name:
        return {}

    payload: dict[str, str] = {}
    if texture_set_name:
        payload["texture_set_name"] = texture_set_name
    if id_collection_name:
        payload["id_collection_name"] = id_collection_name
    return payload


def object_group_metadata(obj) -> dict[str, str]:
    if obj is None:
        return {}

    tagged_group_name = _clean(tagging.get_metadata_group_name(obj)) or _clean(tagging.get_tag_group_name(obj))
    tagged_collection_name = _clean(tagging.get_metadata_collection_name(obj)) or _clean(tagging.get_tag_collection_name(obj))
    primary_collection = _primary_collection(obj)
    collection_metadata = collection_group_metadata(primary_collection)
    id_collection_name = tagged_collection_name or collection_metadata.get("id_collection_name", "")
    texture_set_name = tagged_group_name or id_collection_name or _clean(getattr(obj, "name", ""))

    payload: dict[str, str] = {}
    if texture_set_name:
        payload["texture_set_name"] = texture_set_name
    if id_collection_name:
        payload["id_collection_name"] = id_collection_name
    return payload


def apply_group_metadata(group, metadata: dict[str, str]) -> bool:
    changed = False
    metadata_state = _group_metadata_state(group)
    for attribute_name in ("texture_set_name", "id_collection_name"):
        if attribute_name not in metadata:
            continue
        new_value = _clean(metadata.get(attribute_name, ""))
        old_value = _clean(getattr(metadata_state, attribute_name, ""))
        if old_value == new_value:
            continue
        setattr(group if hasattr(group, attribute_name) else metadata_state, attribute_name, new_value)
        changed = True
    return changed


def group_metadata_payload(group) -> dict[str, str]:
    metadata_state = _group_metadata_state(group)
    payload: dict[str, str] = {}
    texture_set_name = _clean(getattr(metadata_state, "texture_set_name", ""))
    id_collection_name = _clean(getattr(metadata_state, "id_collection_name", ""))
    if texture_set_name:
        payload["texture_set_name"] = texture_set_name
    if id_collection_name:
        payload["id_collection_name"] = id_collection_name
    return payload


def apply_group_metadata_to_target(target, metadata: dict[str, str]) -> bool:
    group_name = naming.sanitize_token(_clean(metadata.get("texture_set_name", ""))) if _clean(metadata.get("texture_set_name", "")) else ""
    collection_name = naming.sanitize_token(_clean(metadata.get("id_collection_name", ""))) if _clean(metadata.get("id_collection_name", "")) else ""
    old_group_name = _clean(tagging.get_metadata_group_name(target))
    old_collection_name = _clean(tagging.get_metadata_collection_name(target))
    if old_group_name == group_name and old_collection_name == collection_name:
        return False
    tagging.set_metadata_names(
        target,
        group_name=group_name or None,
        collection_name=collection_name or None,
    )
    return True
