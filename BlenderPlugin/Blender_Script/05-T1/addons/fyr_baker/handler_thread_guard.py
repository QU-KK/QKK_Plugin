"""Keep depsgraph handlers on Blender's main thread while a Cycles bake job runs.

``bpy.ops.object.bake("INVOKE_DEFAULT")`` runs the bake as an OBJECT_BAKE job, and
Blender builds that job's render depsgraph ON THE JOB THREAD (object_bake_api.cc:
``bake_startjob`` -> ``bake`` -> ``BKE_scene_graph_update_tagged``). Blender's handler
dispatcher (``bpy_app_generic_callback``) then calls every ``depsgraph_update_pre`` /
``depsgraph_update_post`` handler -- ours and every other add-on's -- from that thread,
with no main-thread check, while ``bpy.context`` is the same context the main thread
is drawing the viewport with. A handler that writes it (``temp_override``, an
operator call) can leave the viewport drawing with no area: Blender then crashed
reading ``area->spacedata`` in the transform gizmo poll the moment a material bake
started (customer report 2026-09-30, Blender 5.2.2).

While a guard is held, each handler in those lists is swapped for a wrapper that
calls it only on the main thread. Main-thread updates reach every handler exactly as
before; only the job thread's calls are dropped. The wrapper compares equal to the
handler it wraps, so an add-on's own ``fn in handlers`` / ``handlers.remove(fn)``
keeps working while the guard is held. Releasing the last guard puts the originals
back in place.

Every invoked bake is covered, not only ours: Blender's own Bake button (Render
Properties > Bake) and other add-ons' bakes go through the same job. Blender fires
``object_bake_pre`` on the main thread before it starts the job thread, so
:func:`register` hooks it to take a hold, and a timer drops the hold once no
OBJECT_BAKE job is running any more.
"""
from __future__ import annotations

import threading
import time
import types

_MAIN_THREAD_IDENT = threading.main_thread().ident

GUARDED_HANDLER_LISTS = ("depsgraph_update_pre", "depsgraph_update_post")

_DEPTH = 0
#: (list name, wrapper) for every wrapper this module put into a handler list.
_INSTALLED: list[tuple[str, "_MainThreadOnlyHandler"]] = []


def on_main_thread() -> bool:
    return threading.get_ident() == _MAIN_THREAD_IDENT


def _is_persistent(handler) -> bool:
    # bpy.app.handlers.persistent marks the function's __dict__; a bound method
    # forwards the attribute lookup to its function, as Blender's file-load purge does.
    return hasattr(handler, "_bpy_persistent")


class _MainThreadOnlyHandler:
    """Calls ``handler`` only on the main thread, with the arguments Blender would pick.

    Blender passes ``(scene)`` to a plain function taking exactly one positional
    argument and ``(scene, depsgraph)`` to everything else (``choose_arguments`` in
    bpy_app_handlers.cc). This wrapper is not a plain function, so it always receives
    both and reproduces that choice for the handler it wraps.
    """

    __slots__ = ("handler", "_single_argument")

    def __init__(self, handler):
        self.handler = handler
        self._single_argument = (
            isinstance(handler, types.FunctionType) and handler.__code__.co_argcount == 1
        )

    def __call__(self, *args):
        if not on_main_thread():
            return None
        if self._single_argument:
            return self.handler(*args[:1])
        return self.handler(*args)

    def __eq__(self, other):
        if isinstance(other, _MainThreadOnlyHandler):
            other = other.handler
        return self.handler == other

    def __hash__(self):
        return hash(self.handler)

    def __repr__(self):
        return f"<main-thread-only {self.handler!r}>"


def _handlers():
    try:
        import bpy
    except ImportError:
        return None
    return getattr(getattr(bpy, "app", None), "handlers", None)


def _wrap_unguarded(handlers) -> None:
    for name in GUARDED_HANDLER_LISTS:
        entries = getattr(handlers, name, None)
        if entries is None:
            continue
        for index, handler in enumerate(list(entries)):
            if isinstance(handler, _MainThreadOnlyHandler):
                continue
            wrapper = _MainThreadOnlyHandler(handler)
            entries[index] = wrapper
            _INSTALLED.append((name, wrapper))


def _restore(handlers, *, after_file_load: bool = False) -> None:
    installed = list(_INSTALLED)
    _INSTALLED.clear()
    if handlers is None:
        return
    for name, wrapper in installed:
        entries = getattr(handlers, name, None)
        if entries is None:
            continue
        index = next((i for i, entry in enumerate(entries) if entry is wrapper), None)
        if index is not None:
            entries[index] = wrapper.handler
        elif after_file_load and _is_persistent(wrapper.handler) and not any(
            entry is wrapper.handler for entry in entries
        ):
            # A file load drops every handler that is not a function marked
            # @persistent, and the wrapper is not a function: put back the persistent
            # ones it was standing in for. Outside a file load a missing wrapper was
            # removed by its owner, so it stays gone.
            entries.append(wrapper.handler)


def acquire() -> None:
    """Hold the guard; the first holder wraps every handler in the guarded lists."""
    global _DEPTH
    _DEPTH += 1
    handlers = _handlers()
    if handlers is not None:
        _wrap_unguarded(handlers)


def refresh() -> None:
    """Wrap handlers added since the guard was taken (an add-on enabled mid-bake)."""
    if _DEPTH <= 0:
        return
    handlers = _handlers()
    if handlers is not None:
        _wrap_unguarded(handlers)


def release() -> None:
    """Drop one hold; the last one puts every original handler back."""
    global _DEPTH
    if _DEPTH <= 0:
        return
    _DEPTH -= 1
    if _DEPTH == 0:
        _restore(_handlers())


def reset(*, after_file_load: bool = False) -> None:
    """Drop every hold and restore (file load, add-on disable)."""
    global _DEPTH
    _DEPTH = 0
    # Blender frees app timers on file load and add-on disable, watcher included.
    _clear_bake_job_watch()
    _restore(_handlers(), after_file_load=after_file_load)


def is_held() -> bool:
    return _DEPTH > 0


# ------------------------------------------------------------- any OBJECT_BAKE job

#: Holds taken for OBJECT_BAKE jobs by _on_object_bake_pre, dropped by the watcher.
_BAKE_JOB_HOLDS = 0
_BAKE_JOB_WATCH = {"registered": False, "observed": False, "started_at": 0.0}
#: A job that has not appeared this long after object_bake_pre never will (the
#: blocking EXEC bake fires no job; an invoke that failed to start).
_BAKE_JOB_START_GRACE_SEC = 3.0
_BAKE_JOB_POLL_SEC = 0.1
_OBJECT_BAKE_PRE_HANDLER = None


def _object_bake_job_running() -> bool:
    try:
        import bpy

        return bool(bpy.app.is_job_running("OBJECT_BAKE"))
    except Exception:
        return False


def _release_bake_job_holds() -> None:
    global _BAKE_JOB_HOLDS
    holds, _BAKE_JOB_HOLDS = _BAKE_JOB_HOLDS, 0
    for _ in range(holds):
        release()


def _bake_job_watch():
    """bpy timer: drop the OBJECT_BAKE holds once the job has ended."""
    watch = _BAKE_JOB_WATCH
    if _BAKE_JOB_HOLDS <= 0:
        watch["registered"] = False
        return None
    if _object_bake_job_running():
        watch["observed"] = True
        return _BAKE_JOB_POLL_SEC
    if not watch["observed"] and time.monotonic() - watch["started_at"] < _BAKE_JOB_START_GRACE_SEC:
        return _BAKE_JOB_POLL_SEC
    # No job thread is left to call handlers.
    _release_bake_job_holds()
    watch["registered"] = False
    return None


def _on_object_bake_pre(*_args) -> None:
    """object_bake_pre: runs on the main thread right before the job thread starts."""
    global _BAKE_JOB_HOLDS
    acquire()
    _BAKE_JOB_HOLDS += 1
    watch = _BAKE_JOB_WATCH
    watch["observed"] = False
    watch["started_at"] = time.monotonic()
    if watch["registered"]:
        return
    try:
        import bpy

        bpy.app.timers.register(_bake_job_watch, first_interval=_BAKE_JOB_POLL_SEC)
        watch["registered"] = True
    except Exception:
        # Without a watcher nothing would ever drop the hold.
        _release_bake_job_holds()


def _clear_bake_job_watch() -> None:
    global _BAKE_JOB_HOLDS
    _BAKE_JOB_HOLDS = 0
    _BAKE_JOB_WATCH.update(registered=False, observed=False, started_at=0.0)
    try:
        import bpy

        if bpy.app.timers.is_registered(_bake_job_watch):
            bpy.app.timers.unregister(_bake_job_watch)
    except Exception:
        pass


def register() -> None:
    global _OBJECT_BAKE_PRE_HANDLER
    handlers = _handlers()
    entries = getattr(handlers, "object_bake_pre", None) if handlers is not None else None
    if entries is None:
        return
    if _OBJECT_BAKE_PRE_HANDLER is None:
        persistent = getattr(handlers, "persistent", None)
        _OBJECT_BAKE_PRE_HANDLER = (
            persistent(_on_object_bake_pre) if callable(persistent) else _on_object_bake_pre
        )
    if _OBJECT_BAKE_PRE_HANDLER not in entries:
        entries.append(_OBJECT_BAKE_PRE_HANDLER)


def unregister() -> None:
    global _OBJECT_BAKE_PRE_HANDLER
    handlers = _handlers()
    entries = getattr(handlers, "object_bake_pre", None) if handlers is not None else None
    if entries is not None and _OBJECT_BAKE_PRE_HANDLER is not None:
        while _OBJECT_BAKE_PRE_HANDLER in entries:
            entries.remove(_OBJECT_BAKE_PRE_HANDLER)
    _OBJECT_BAKE_PRE_HANDLER = None
    _clear_bake_job_watch()
    reset()
