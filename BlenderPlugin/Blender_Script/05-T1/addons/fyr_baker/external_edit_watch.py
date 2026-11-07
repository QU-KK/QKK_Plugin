from __future__ import annotations

import time
from pathlib import Path

try:
    import bpy
except ImportError:  # unit tests outside Blender
    bpy = None


class ExternalEditWatcher:
    """Watches baked output files for external editor saves and invalidates the
    output image cache when a change is detected."""

    _INTERVAL_SECONDS = 0.75
    # After this long with no save the poll slows down; the watch itself lives
    # until the addon unloads. It used to expire after 5 minutes, which is shorter
    # than most Photoshop sessions, so "Edit Map Externally" silently stopped
    # reloading the very save it was opened for.
    _SLOW_AFTER_SECONDS = 600.0
    _SLOW_INTERVAL_SECONDS = 2.0
    #: How long a file has to stay unreadable before the watch gives up on it. A
    #: non-atomic save of a large map, or one over a network share, can leave the
    #: destination unopenable for seconds; dropping the watch there ends the feature
    #: for that map with nothing in the UI to say so.
    _MISSING_GRACE_SECONDS = 10.0

    def __init__(self, invalidate_fn=None) -> None:
        self._watches: dict[str, dict[str, float | int | bool]] = {}
        self._invalidate_fn = invalidate_fn
        # Store a stable bound-method reference so Blender's timer registry can
        # identify it consistently (a bare ``self._tick`` access creates a new
        # bound-method object each time).
        self._tick_ref = self._tick

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize(self, file_path: str | Path) -> str:
        try:
            return str(Path(file_path).resolve())
        except Exception:
            return str(file_path)

    def _mtime_ns(self, file_path: str | Path) -> int:
        try:
            return int(Path(file_path).stat().st_mtime_ns)
        except OSError:
            return 0

    def _timers(self):
        return getattr(getattr(bpy, "app", None), "timers", None)

    def _invalidate(self, path: str) -> None:
        if self._invalidate_fn is None:
            from . import runtime

            self._invalidate_fn = runtime.invalidate_output_image_cache
        self._invalidate_fn([path])

    # ------------------------------------------------------------------
    # Timer callback
    # ------------------------------------------------------------------

    def _tick(self):
        now = time.monotonic()
        newest_activity = 0.0
        gone: list[str] = []
        for path, state in list(self._watches.items()):
            last_mtime_ns = int(state.get("mtime_ns", 0) or 0)
            last_change_time = float(state.get("last_change_time", now) or now)
            current_mtime_ns = self._mtime_ns(path)
            if current_mtime_ns <= 0:
                # The file is unreadable. Editors that save atomically write a
                # temp file and rename it over the target, so one missing poll
                # proves nothing. A deletion is a change like any other -- the
                # cached image no longer matches disk -- and it is the last change
                # this path will ever have, so the watch is dropped rather than
                # left polling a dead file for the rest of the session.
                #
                # Two consecutive polls was not enough of a grace: that is 1.5 s,
                # and an editor that deletes and rewrites a 4K map (or one saving
                # over a network share) is unreadable for longer. The watch was
                # then dropped mid-save, with no report, and "Edit Map Externally"
                # simply stopped reloading. Wait for a real absence instead.
                missing_since = float(state.get("missing_since", 0.0) or 0.0)
                if not missing_since:
                    state["missing_since"] = now
                    missing_since = now
                if last_mtime_ns > 0 and now - missing_since >= self._MISSING_GRACE_SECONDS:
                    self._invalidate(path)
                    gone.append(path)
                    continue
                state["missing"] = True
            else:
                state["missing"] = False
                state["missing_since"] = 0.0
                if current_mtime_ns != last_mtime_ns:
                    self._invalidate(path)
                    state["mtime_ns"] = current_mtime_ns
                    state["last_change_time"] = now
                    last_change_time = now
            newest_activity = max(newest_activity, last_change_time)
        for path in gone:
            self._watches.pop(path, None)
        if not self._watches:
            return None
        if now - newest_activity >= self._SLOW_AFTER_SECONDS:
            return self._SLOW_INTERVAL_SECONDS
        return self._INTERVAL_SECONDS

    def _ensure_timer(self) -> None:
        timers = self._timers()
        if timers is None or not hasattr(timers, "register"):
            return
        is_registered = getattr(timers, "is_registered", None)
        if callable(is_registered):
            try:
                if is_registered(self._tick_ref):
                    return
            except Exception:
                pass
        try:
            timers.register(self._tick_ref, first_interval=self._INTERVAL_SECONDS)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, file_path: str | Path) -> None:
        """Begin watching *file_path* for external-editor saves."""
        path = self._normalize(file_path)
        self._watches[path] = {
            "mtime_ns": self._mtime_ns(path),
            "last_change_time": time.monotonic(),
        }
        self._ensure_timer()

    def stop_all(self) -> None:
        """Clear all watches and unregister the Blender timer."""
        self._watches.clear()
        timers = self._timers()
        if timers is not None and hasattr(timers, "unregister"):
            try:
                timers.unregister(self._tick_ref)
            except Exception:
                pass
