"""Serialization for Fyr Baker's timer-driven startup popups.

Fyr Baker opens two dialogs from ``bpy.app.timers`` shortly after the add-on
loads: the first-run settings dialog (1.5s) and the update notification (3.0s).
When the second one is invoked while the first is still on screen, Blender frees
the first popup's block but can still service a queued redraw for it, which then
dereferences the freed operator RNA and crashes in ``RNA_property_subtype``
during ``block_draw``.

The same class of crash appears after disable/purge/enable reload: a props dialog
left on screen (or a timer that outlives unregister) keeps drawing against
torn-down operator RNA and falls back to raw property identifiers. The first-run
timer must be unregistered on disable, and the offer is remembered for the
Blender process so reload loops do not open a second copy.

Only one of these popups may be on screen at a time. Whoever loses the race
waits and tries again rather than opening on top.
"""

from __future__ import annotations

FIRST_RUN_SETTINGS = "FIRST_RUN_SETTINGS"
UPDATE_NOTIFICATION = "UPDATE_NOTIFICATION"

_active_owner: str | None = None


def acquire(owner: str) -> bool:
    """Claim the startup-popup slot. Returns False when another popup holds it."""
    global _active_owner
    if _active_owner is not None:
        # The same owner re-acquiring is the stacked-dialog case this slot exists
        # to prevent (the updater's four dialogs share one owner string): a second
        # invoke_props_dialog over the first freed its block mid-redraw.
        return False
    _active_owner = owner
    return True


def release(owner: str) -> None:
    global _active_owner
    if _active_owner == owner:
        _active_owner = None


def is_busy(owner: str | None = None) -> bool:
    """True when a startup popup other than ``owner`` is currently on screen."""
    return _active_owner is not None and _active_owner != owner


def active_owner() -> str | None:
    return _active_owner


def reset() -> None:
    """Drop any claim; used on add-on reload so a stale flag cannot wedge a dialog."""
    global _active_owner
    _active_owner = None
