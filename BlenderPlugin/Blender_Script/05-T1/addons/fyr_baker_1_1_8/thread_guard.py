"""Thread targets that never let an exception reach the interpreter's thread excepthook.

An exception that escapes a ``threading.Thread`` target is printed by the interpreter from
that thread, formatting traceback objects that reference frames and objects the addon (or a
reload, an undo, an autosave) may be tearing down on the main thread. A crash dump from a
customer machine showed exactly that: an access violation in python313 on a Python-created
thread while the main thread was inside Blender's autosave. Every background thread the addon
starts goes through :func:`guarded`, which catches everything, logs one line and returns.
"""

from __future__ import annotations

import functools


def guarded(target, label: str = ""):
    """``target`` wrapped so that no exception leaves it."""
    name = label or getattr(target, "__name__", "thread")

    @functools.wraps(target)
    def _run(*args, **kwargs):
        try:
            return target(*args, **kwargs)
        except BaseException as error:  # noqa: BLE001 - nothing may escape a worker thread
            try:
                print(f"[Fyr Baker] background task '{name}' failed: {error!r}")
            except Exception:
                pass
            return None

    return _run
