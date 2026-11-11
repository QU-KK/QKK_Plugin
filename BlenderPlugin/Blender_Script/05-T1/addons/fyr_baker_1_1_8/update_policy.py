"""Update-mode vocabulary, and the one seam the Superhive build removes.

Fyr Baker ships through two channels with different rules about updates:

* the direct channel (fyrplugins.com) carries ``updater.py`` and can check the
  release feed, download an archive, and install it through Blender's extension
  operator;
* the Superhive channel must not. Marketplace review rejects an add-on that
  installs its own updates, because customers are meant to receive reviewed
  updates through the store, so ``scripts/package_extension.py`` builds that
  archive with ``updater.py``, ``update_archive.py`` and ``updater_state.py``
  omitted outright (``device_link.py`` with them) and no ``network``
  permission in the manifest.

Everything outside the updater imports the update vocabulary from HERE rather
than from ``updater``, so dropping those three files is a packaging decision and
not a code change. The constants live here for the same reason: an add-on that
carries no updater still has an ``update_check_mode`` preference to normalise
and a saved value to read back.
"""

from __future__ import annotations

import importlib

UPDATE_MODE_STARTUP = "STARTUP"
UPDATE_MODE_EVERY_30_MINUTES = "EVERY_30_MINUTES"
UPDATE_MODE_MANUAL = "MANUAL"
UPDATE_MODE_NEVER = "NEVER"

UPDATE_MODE_ITEMS = (
    (UPDATE_MODE_STARTUP, "On Startup", "Check for updates when Blender starts"),
    (
        UPDATE_MODE_EVERY_30_MINUTES,
        "Every 30 Minutes",
        "Check after Blender starts, then every 30 minutes while Blender remains open",
    ),
    (UPDATE_MODE_MANUAL, "Manual Only", "Check only when you select Check Now in the add-on preferences"),
    (UPDATE_MODE_NEVER, "Never", "Disable all update checks"),
)

# The only mode a build without an updater can be in. Kept as a one-item tuple
# rather than an empty one: EnumProperty rejects an empty items sequence.
UPDATE_MODE_ITEMS_WITHOUT_UPDATER = (
    (UPDATE_MODE_NEVER, "Never", "This build does not check for updates"),
)

# Blender ships with online access off, so Fyr Baker must not reach the network
# until the user asks it to. Every default resolves to "Never"; the first-run
# dialog is where the user can opt in.
UPDATE_MODE_DEFAULT = UPDATE_MODE_NEVER

AUTOMATIC_UPDATE_MODES = (UPDATE_MODE_STARTUP, UPDATE_MODE_EVERY_30_MINUTES)

_VALID_MODES = frozenset(item[0] for item in UPDATE_MODE_ITEMS)

# None = not looked up yet. False = looked up and absent (the Superhive build).
_updater_module: object | None | bool = None


def updater_module():
    """The ``updater`` module, or None when this build ships without one.

    Resolved once and cached. ``importlib`` rather than a module-level ``from .
    import updater`` because the import must be allowed to fail: on the
    Superhive channel the file is not in the archive at all.
    """
    global _updater_module
    if _updater_module is None:
        try:
            _updater_module = importlib.import_module(".updater", __package__)
        except Exception:
            # Anything raised while importing the updater must leave the rest of
            # the add-on usable, not just ImportError - a partially staged
            # archive should degrade to "no updates", never to "no add-on".
            _updater_module = False
    return _updater_module or None


def updater_available() -> bool:
    """True when this build can check for and install updates."""
    return updater_module() is not None


def update_mode_items():
    """Enum items for the ``update_check_mode`` preference on this build."""
    if updater_available():
        return UPDATE_MODE_ITEMS
    return UPDATE_MODE_ITEMS_WITHOUT_UPDATER


def normalize_update_mode(value) -> str:
    """Coerce a saved/raw mode to a mode this build actually honours."""
    if value in _VALID_MODES:
        if not updater_available():
            return UPDATE_MODE_NEVER
        return str(value)
    return UPDATE_MODE_DEFAULT


def get_update_mode(prefs) -> str:
    """Read ``update_check_mode`` off preferences, tolerating every absence.

    ``prefs.get(...)`` is tried first so a preference block that has never been
    written returns the stored value rather than the RNA default.
    """
    raw = None
    getter = getattr(prefs, "get", None)
    if callable(getter):
        try:
            raw = getter("update_check_mode", None)
        except Exception:
            raw = None
    if raw is None:
        raw = getattr(prefs, "update_check_mode", UPDATE_MODE_DEFAULT)
    return normalize_update_mode(raw)


def is_automatic_update_mode(mode: str) -> bool:
    return updater_available() and mode in AUTOMATIC_UPDATE_MODES


def reschedule_update_check() -> None:
    """Re-arm (or cancel) the periodic check. A no-op without an updater."""
    module = updater_module()
    if module is None:
        return
    module.reschedule_update_check()


def cancel_scheduled_check() -> None:
    module = updater_module()
    if module is None:
        return
    module.cancel_scheduled_check()


def draw_account_section(layout) -> None:
    """Draw the Fyr account block of the Updates preferences. A no-op without an updater."""
    module = updater_module()
    if module is None:
        return
    draw = getattr(module, "draw_account_section", None)
    if callable(draw):
        draw(layout)
