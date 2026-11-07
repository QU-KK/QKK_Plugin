from __future__ import annotations

import bpy


def _get_registered_class(cls):
    return getattr(bpy.types, cls.__name__, None)


def safe_register_class(cls):
    existing = _get_registered_class(cls)
    if existing is not None and existing is not cls:
        try:
            bpy.utils.unregister_class(existing)
        except Exception:
            pass

    try:
        bpy.utils.register_class(cls)
        return
    except ValueError as exc:
        if "already registered" not in str(exc):
            raise

    try:
        bpy.utils.unregister_class(cls)
    except Exception:
        pass

    existing = _get_registered_class(cls)
    if existing is not None and existing is not cls:
        try:
            bpy.utils.unregister_class(existing)
        except Exception:
            pass

    bpy.utils.register_class(cls)


def safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
        return
    except Exception:
        pass

    existing = _get_registered_class(cls)
    if existing is not None and existing is not cls:
        try:
            bpy.utils.unregister_class(existing)
        except Exception:
            pass


def safe_remove_attr(owner, attribute_name):
    if hasattr(owner, attribute_name):
        try:
            delattr(owner, attribute_name)
        except Exception:
            pass
