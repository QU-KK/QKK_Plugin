"""Per-job index of ``Object.users_collection``.

``users_collection`` scans every collection per call (O(collections x objects)): 0.4 s over
the ~1000 lookups of a 300-group job build. While a scope is open the index is built once
and answers every lookup, in the same order Blender returns (``bpy.data.collections``, then
each scene's master collection). Outside a scope, or if the index cannot be built, lookups go
straight to Blender.
"""

from __future__ import annotations

import bpy

_INDEX: dict | None = None
_DEPTH = 0


def _build() -> dict | None:
    try:
        index: dict = {}
        for collection in bpy.data.collections:
            for member in collection.objects:
                index.setdefault(member.as_pointer(), []).append(collection)
        for scene in bpy.data.scenes:
            master = scene.collection
            for member in master.objects:
                index.setdefault(member.as_pointer(), []).append(master)
        return index
    except Exception:
        return None


def open_scope() -> None:
    """Start answering lookups from an index built now. Pair with :func:`close_scope`; nests."""
    global _INDEX, _DEPTH
    _DEPTH += 1
    if _DEPTH == 1:
        _INDEX = _build()


def close_scope() -> None:
    global _INDEX, _DEPTH
    _DEPTH = max(0, _DEPTH - 1)
    if _DEPTH == 0:
        _INDEX = None


def users_collection(obj) -> tuple:
    """The collections ``obj`` is linked to (what ``obj.users_collection`` returns)."""
    index = _INDEX
    if index is not None:
        try:
            return tuple(index.get(obj.as_pointer(), ()))
        except Exception:
            pass
    return tuple(getattr(obj, "users_collection", ()) or ())
