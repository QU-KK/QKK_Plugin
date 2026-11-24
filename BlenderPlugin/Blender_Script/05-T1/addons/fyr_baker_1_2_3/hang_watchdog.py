"""Turn a frozen Blender into a stack trace instead of a shrug.

The 2026-08-19 QA session ended with Blender wedged: not responding, 0.03 s of
CPU over ten minutes, the bake worker idle and healthy. All we could recover was
process counters, which is not enough to name a deadlock, so the bug survived the
session (see docs/MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G12).

How this works
--------------
``faulthandler.dump_traceback_later(timeout)`` arms a watchdog thread that dumps
**every thread's** Python stack after ``timeout`` seconds unless something
cancels it first. That "unless" is the whole trick: a Blender timer re-arms it on
every heartbeat, and a Blender timer only runs while the main loop is alive. Wedge
the main loop and the re-arm never happens, the deadline passes, and the watchdog
thread -- which is not blocked, because it is not the main thread -- writes the
stacks out.

It cannot catch a hang inside a C call that never returns to Python, and it
cannot unwedge anything. It only makes the next hang diagnosable.

Cost is a timer callback every few seconds that cancels and re-arms a timeout.
No polling, no threads of our own, nothing on the bake path.
"""
from __future__ import annotations

import contextlib
import datetime
import faulthandler
import os
from pathlib import Path

try:  # pragma: no cover - the module is unit-tested without Blender
    import bpy  # type: ignore
except ImportError:  # pragma: no cover
    bpy = None  # type: ignore

#: Seconds of main-loop silence before the stacks are dumped. Must clear the
#: longest legitimate main-thread block by a wide margin or the log fills with
#: false positives: a high-scene rebuild on a 7.4 M-poly mesh blocks ~20 s, and
#: writing two per-corner UV sidecars for the same mesh measured ~16 s. A real
#: deadlock never ends, so nothing is lost by being generous here.
HANG_THRESHOLD_SECONDS = 90.0

#: How often the main loop proves it is alive. Cheap: cancel + re-arm.
HEARTBEAT_SECONDS = 5.0

#: Env var to turn the watchdog off entirely, for anyone profiling or debugging
#: who does not want a second faulthandler owner in the process.
DISABLE_ENV_VAR = "FYR_BAKER_NO_HANG_WATCHDOG"

_log_handle = None
_armed = False
#: Nesting depth of suspended() scopes. A synchronous Cycles recovery bake blocks the
#: main thread for minutes per map by design (constants: "minutes per map and hours per
#: bake"), so the heartbeat cannot run and the watchdog fired once PER MAP - ~3.4 MB of
#: all-threads stacks apiece, shipped in every support bundle, turning a slow bake into
#: a hung-looking one.
_suspend_depth = 0


def log_path() -> Path:
    """Where the stacks land. Next to the backend cache, so support bundles find it."""
    try:
        from . import preferences

        root = Path(preferences.persistent_cache_root())
    except Exception:
        import tempfile

        root = Path(tempfile.gettempdir()) / "fyr_baker_backend_cache"
    return root / "hang_traceback.log"


#: Roll the traceback log over once it passes this. Each fired dump is an all-threads
#: stack of a process with a large worker pool (~3.4 MB apiece), and the file was opened
#: "a" with no cap: 91.5 MB across 9 days on one machine, invisible to the cache budget
#: and untouched by Clear Cache (RC sweep 2026-08-29, finding 11). One rollover keeps the
#: previous session's evidence, which is all a support bundle ever needs.
MAX_LOG_BYTES = 8 * 1024 * 1024


def _rotate_log_if_oversized(path: Path) -> None:
    """Move an oversized log aside so the fresh one starts empty. Never raises."""
    try:
        if not path.exists() or path.stat().st_size <= MAX_LOG_BYTES:
            return
        previous = path.with_suffix(path.suffix + ".1")
        try:
            if previous.exists():
                previous.unlink()
        except Exception:
            pass
        path.replace(previous)
    except Exception:
        # A watchdog that cannot rotate its log still has to arm.
        pass


def _rotate_log_if_oversized_now() -> None:
    """Rotate mid-session, closing the open handle first.

    _rotate_log_if_oversized only runs from _open_log, which returns early whenever a
    handle is already open - and the handle is held for the watchdog's whole lifetime.
    So the 8 MB cap was evaluated once per start() and never again, which is exactly how
    one session grew a 91.5 MB log. Checked from the heartbeat instead, every 5 s, at
    the cost of one stat().
    """
    global _log_handle
    try:
        path = log_path()
        if not path.exists() or path.stat().st_size <= MAX_LOG_BYTES:
            return
        handle, _log_handle = _log_handle, None
        if handle is not None:
            _release_faulthandler()
            try:
                handle.close()
            except Exception:
                pass
        _rotate_log_if_oversized(path)
    except Exception:
        pass


def _open_log():
    """Keep one handle open for the lifetime of the watchdog.

    faulthandler writes from a thread while the main thread is stuck, so it needs
    a file object it can use without allocating or acquiring anything of ours.
    Line buffering matters: a dump that never reaches disk is no better than no
    dump at all, and the process may well be killed rather than recovered.
    """
    global _log_handle
    if _log_handle is not None:
        return _log_handle
    path = log_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_log_if_oversized(path)
        _log_handle = open(path, "a", buffering=1, encoding="utf-8", errors="replace")
        _log_handle.write(
            f"\n=== Fyr Baker hang watchdog armed {datetime.datetime.now().isoformat(timespec='seconds')} "
            f"(threshold {HANG_THRESHOLD_SECONDS:.0f}s, pid {os.getpid()}) ===\n"
        )
    except Exception:
        _log_handle = None
        return None
    if _armed:
        # faulthandler.enable() keeps the descriptor, not the file object. After a
        # close_log() the crash dump must be re-pointed at the reopened file or it
        # would write into whatever file next reused the freed descriptor.
        try:
            faulthandler.enable(file=_log_handle, all_threads=True)
        except Exception:
            pass
    return _log_handle


@contextlib.contextmanager
def suspended(reason: str = ""):
    """Stand the watchdog down around a block that is SUPPOSED to hold the main thread.

    The synchronous Cycles recovery bake is the case this exists for: it owns the main
    thread for minutes at a time, which is slow but healthy, and a dump per map buried
    the real signal in the support bundle.
    """
    global _suspend_depth
    _suspend_depth += 1
    if _suspend_depth == 1:
        try:
            faulthandler.cancel_dump_traceback_later()
        except Exception:
            pass
        handle = _log_handle
        if handle is not None and reason:
            try:
                handle.write(f"--- watchdog suspended: {reason} ---\n")
            except Exception:
                pass
    try:
        yield
    finally:
        _suspend_depth = max(0, _suspend_depth - 1)
        if _suspend_depth == 0 and _armed:
            # Re-arm from now, not from whenever the last heartbeat ran.
            _heartbeat()


def _heartbeat():
    """Re-arm the deadline. Returns the next interval, as Blender timers want."""
    if not _armed:
        return None
    if _suspend_depth > 0:
        # Suspended: keep ticking so the timer stays registered, but do not arm a
        # deadline against a block that is meant to be long.
        return HEARTBEAT_SECONDS
    try:
        faulthandler.cancel_dump_traceback_later()
        _rotate_log_if_oversized_now()
        handle = _open_log()
        if handle is not None:
            faulthandler.dump_traceback_later(
                HANG_THRESHOLD_SECONDS, repeat=False, file=handle, exit=False
            )
    except Exception:
        # A watchdog that raises into Blender's timer loop is worse than no
        # watchdog: it would unregister itself and take the heartbeat with it.
        pass
    return HEARTBEAT_SECONDS


def start() -> bool:
    global _armed
    if bpy is None or _armed:
        return False
    if str(os.environ.get(DISABLE_ENV_VAR, "") or "").strip():
        return False
    if _open_log() is None:
        return False
    _armed = True
    try:
        faulthandler.enable(file=_log_handle, all_threads=True)
    except Exception:
        pass
    try:
        bpy.app.timers.register(_heartbeat, first_interval=HEARTBEAT_SECONDS, persistent=True)
    except Exception:
        _armed = False
        return False
    _heartbeat()
    return True


def close_log() -> None:
    """Release the log handle without disarming.

    Lets Clear Cache delete the file on Windows; the next heartbeat reopens it via
    _open_log(), so the watchdog keeps protecting the session.
    """
    global _log_handle
    if _log_handle is None:
        return
    _release_faulthandler()
    try:
        _log_handle.close()
    except Exception:
        pass
    _log_handle = None


def _release_faulthandler() -> None:
    """Detach faulthandler from the log before its descriptor is closed."""
    try:
        faulthandler.cancel_dump_traceback_later()
    except Exception:
        pass
    try:
        faulthandler.disable()
    except Exception:
        pass


def stop() -> None:
    global _armed, _log_handle
    _armed = False
    _release_faulthandler()
    if bpy is not None:
        try:
            if bpy.app.timers.is_registered(_heartbeat):
                bpy.app.timers.unregister(_heartbeat)
        except Exception:
            pass
    if _log_handle is not None:
        try:
            _log_handle.close()
        except Exception:
            pass
        _log_handle = None


def register() -> None:
    start()


def unregister() -> None:
    stop()
