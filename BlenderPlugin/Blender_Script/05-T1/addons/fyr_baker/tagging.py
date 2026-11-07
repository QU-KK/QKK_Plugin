from __future__ import annotations

from collections.abc import Mapping, MutableMapping

from . import constants, naming

ROLE_KEY = "master_baker_role"
GROUP_KEY = "master_baker_group"
SOURCE_KEY = "master_baker_tag_source"
COLLECTION_KEY = "master_baker_collection"


def normalize_role(role: str | None) -> str | None:
    if role is None:
        return None
    normalized = str(role).strip().upper()
    return normalized if normalized in {constants.OBJECT_ROLE_LOW, constants.OBJECT_ROLE_HIGH, constants.OBJECT_ROLE_CAGE} else None


def _is_mapping(target) -> bool:
    if isinstance(target, MutableMapping) or isinstance(target, Mapping):
        return True
    if isinstance(target, (str, bytes, bytearray)):
        return False
    return all(hasattr(target, attribute) for attribute in ("__getitem__", "__setitem__"))


def _get_value(target, key, default=None):
    if _is_mapping(target):
        return target.get(key, default)
    return getattr(target, key, default)


def _set_value(target, key, value):
    if _is_mapping(target):
        target[key] = value
        return
    setattr(target, key, value)


def _delete_value(target, key):
    if _is_mapping(target):
        if hasattr(target, "pop"):
            target.pop(key, None)
        elif key in target:
            del target[key]
        return
    if hasattr(target, key):
        delattr(target, key)


def _clean_metadata_name(value: str | None) -> str | None:
    cleaned = naming.sanitize_token(value) if value else ""
    return cleaned or None


def build_role_tag(
    role: str,
    *,
    group_name: str | None = None,
    source: str | None = None,
    collection_name: str | None = None,
) -> dict[str, str]:
    normalized_role = normalize_role(role)
    if normalized_role is None:
        raise ValueError(f"Unsupported bake role: {role!r}")

    payload: dict[str, str] = {ROLE_KEY: normalized_role}
    if group_name:
        payload[GROUP_KEY] = naming.sanitize_token(group_name)
    if source:
        payload[SOURCE_KEY] = str(source)
    if collection_name:
        payload[COLLECTION_KEY] = naming.sanitize_token(collection_name)
    return payload


def set_metadata_names(
    target,
    *,
    group_name: str | None = None,
    collection_name: str | None = None,
) -> dict[str, str]:
    payload: dict[str, str] = {}
    normalized_group_name = _clean_metadata_name(group_name)
    normalized_collection_name = _clean_metadata_name(collection_name)

    if normalized_group_name is None:
        _delete_value(target, GROUP_KEY)
    else:
        _set_value(target, GROUP_KEY, normalized_group_name)
        payload[GROUP_KEY] = normalized_group_name

    if normalized_collection_name is None:
        _delete_value(target, COLLECTION_KEY)
    else:
        _set_value(target, COLLECTION_KEY, normalized_collection_name)
        payload[COLLECTION_KEY] = normalized_collection_name

    return payload


def apply_role_tag(
    target,
    role: str,
    *,
    group_name: str | None = None,
    source: str | None = None,
    collection_name: str | None = None,
) -> dict[str, str]:
    payload = build_role_tag(
        role,
        group_name=group_name,
        source=source,
        collection_name=collection_name,
    )
    for key, value in payload.items():
        _set_value(target, key, value)
    return payload


def apply_collection_tag(
    collection,
    role: str,
    *,
    group_name: str | None = None,
    source: str | None = None,
) -> dict[str, str]:
    collection_name = _get_value(collection, "name", None)
    return apply_role_tag(
        collection,
        role,
        group_name=group_name,
        source=source or "collection",
        collection_name=collection_name,
    )


def apply_object_tag(
    obj,
    role: str,
    *,
    group_name: str | None = None,
    source: str | None = None,
    collection_name: str | None = None,
) -> dict[str, str]:
    return apply_role_tag(
        obj,
        role,
        group_name=group_name,
        source=source or "object",
        collection_name=collection_name,
    )


def read_role_tag(target) -> dict[str, str] | None:
    role = normalize_role(_get_value(target, ROLE_KEY))
    if role is None:
        return None

    payload: dict[str, str] = {ROLE_KEY: role}
    group_name = _get_value(target, GROUP_KEY)
    source = _get_value(target, SOURCE_KEY)
    collection_name = _get_value(target, COLLECTION_KEY)

    if group_name:
        payload[GROUP_KEY] = str(group_name)
    if source:
        payload[SOURCE_KEY] = str(source)
    if collection_name:
        payload[COLLECTION_KEY] = str(collection_name)
    return payload


def clear_role_tag(target) -> None:
    for key in (ROLE_KEY, GROUP_KEY, SOURCE_KEY, COLLECTION_KEY):
        _delete_value(target, key)


def restore_role_tag(target, payload) -> bool:
    """Write back a tag captured by ``read_role_tag``. True when anything was written.

    The Undo Remove path needs this: removing a bake group strips its objects' role
    tags, and the restore has to put back the ORIGINAL tag, ``source`` included.
    Rebuilding the tag instead would have to guess that source, and the guess is not
    free -- only a "suffix"-sourced tag is treated as stale by the prep pass -- so
    the captured payload is replayed verbatim.
    """
    if not payload:
        return False
    role = normalize_role(payload.get(ROLE_KEY))
    if role is None:
        return False
    _set_value(target, ROLE_KEY, role)
    for key in (GROUP_KEY, SOURCE_KEY, COLLECTION_KEY):
        value = payload.get(key)
        if value:
            _set_value(target, key, str(value))
        else:
            _delete_value(target, key)
    return True


def clear_collection_tag(collection) -> None:
    clear_role_tag(collection)


def clear_object_tag(obj) -> None:
    clear_role_tag(obj)


def get_tag_role(target) -> str | None:
    tag = read_role_tag(target)
    if tag is None:
        return None
    return tag[ROLE_KEY]


def get_tag_group_name(target) -> str | None:
    tag = read_role_tag(target)
    if tag is None:
        return None
    return tag.get(GROUP_KEY)


def rename_group_tag(target, previous_group_name: str, group_name: str) -> bool:
    """Point a role tag at a renamed bake group. Tags naming any other group are left alone."""
    previous = naming.sanitize_token(previous_group_name) if previous_group_name else ""
    if not previous or _get_value(target, GROUP_KEY) != previous:
        return False
    _set_value(target, GROUP_KEY, naming.sanitize_token(group_name))
    return True


def get_tag_collection_name(target) -> str | None:
    tag = read_role_tag(target)
    if tag is None:
        return None
    return tag.get(COLLECTION_KEY)


def get_metadata_group_name(target) -> str | None:
    value = _get_value(target, GROUP_KEY)
    if not value:
        return None
    return str(value)


def get_metadata_collection_name(target) -> str | None:
    value = _get_value(target, COLLECTION_KEY)
    if not value:
        return None
    return str(value)


def is_tagged(target) -> bool:
    return read_role_tag(target) is not None
