"""Finding a backend that arrived through the standalone installer.

The Superhive channel ships an add-on with no native payload at all: no
``fyr_baker_backend.exe``, and no ``fyr_geometry_hash.dll`` either. Both come
from a separate signed installer, so both are looked up here.

Kept free of ``bpy`` and of the rest of the add-on so the two very different
callers can share it: ``runtime`` (resolving the backend executable) and
``indexed_geometry`` (loading the hash library, which it does from a worker
thread during mesh transport). The discovery contract itself, the registry key
and the payload layout, lives in ``constants`` because the installer reads it
from there too.

Every lookup here answers "not installed" rather than raising. A missing
installation is an ordinary state on the marketplace channel, not an error: the
add-on reports it and bakes through Cycles.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import constants


def _registry_roots() -> list[Path]:
    """Install roots the installer recorded, per-user first.

    A per-user install needs no elevation and is the wizard's default, so HKCU
    is checked before HKLM. Only the registry knows a CUSTOM install directory;
    guessing %ProgramFiles% for that user would miss a backend they did install.
    """
    if os.name != "nt":
        return []
    try:
        import winreg
    except Exception:
        return []

    roots: list[Path] = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, constants.BACKEND_INSTALL_REGISTRY_KEY) as key:
                value, value_type = winreg.QueryValueEx(
                    key, constants.BACKEND_INSTALL_REGISTRY_VALUE
                )
        except Exception:
            # Key absent (nothing installed), value absent, access denied, or a
            # hive that does not exist. All of them mean "not installed here".
            continue
        if value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
            continue
        text = str(value or "").strip()
        if text:
            roots.append(Path(os.path.expandvars(text)))
    return roots


def _default_roots() -> list[Path]:
    """Where the installer puts things when the user takes the defaults."""
    if os.name != "nt":
        return []
    roots: list[Path] = []
    for variable, *parents in (
        ("LOCALAPPDATA", "Programs"),
        ("PROGRAMFILES",),
        ("PROGRAMW6432",),
    ):
        base = os.environ.get(variable, "").strip()
        if base:
            roots.append(Path(base).joinpath(*parents) / constants.BACKEND_INSTALL_DIRNAME)
    return roots


def install_roots() -> list[Path]:
    """Every plausible installation root, most authoritative first, deduplicated."""
    roots: list[Path] = []
    seen: set[str] = set()
    for root in (*_registry_roots(), *_default_roots()):
        key = os.path.normcase(str(root))
        if key not in seen:
            seen.add(key)
            roots.append(root)
    return roots


def payload_paths(filename: str) -> list[Path]:
    """Candidate locations for one file of the installed payload.

    The installed tree mirrors the bundled one, so ``<root>/bin/windows-x64/``
    is where things are. ``<root>/`` itself is also tried for an installation
    laid out flat by hand or by an older installer.
    """
    relative = Path(constants.BACKEND_INSTALL_RELATIVE_DIR)
    paths: list[Path] = []
    seen: set[str] = set()
    for root in install_roots():
        for candidate in (root / relative / filename, root / filename):
            key = os.path.normcase(str(candidate))
            if key not in seen:
                seen.add(key)
                paths.append(candidate)
    return paths


def find_payload_file(filename: str) -> Path | None:
    """First existing copy of ``filename`` in an installed payload, or None."""
    for candidate in payload_paths(filename):
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None
