from __future__ import annotations

from dataclasses import dataclass
import base64
import glob
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from typing import Iterable, Mapping, Sequence


PAINTER_MESH_MAP_SUFFIXES = {
    "AO": "ambient_occlusion",
    "CURVATURE": "curvature",
    "NORMAL": "normal_base",
    "WORLD_NORMAL": "world_space_normals",
    "ID": "id",
    "POSITION": "position",
    "THICKNESS": "thickness",
}

PAINTER_MESH_MAP_USAGES = {
    "AO": "AO",
    "BENT_NORMAL": "BentNormals",
    "CURVATURE": "Curvature",
    "HEIGHT": "Height",
    "ID": "ID",
    "NORMAL": "Normal",
    "OPACITY": "Opacity",
    "POSITION": "Position",
    "THICKNESS": "Thickness",
    "WORLD_NORMAL": "WorldSpaceNormal",
}

# Wavefront's widely-supported PBR extensions are understood by Toolbag.  Mesh
# maps that are not surface inputs remain staged beside the model for artists.
TOOLBAG_MTL_DIRECTIVES = {
    "MATERIAL_ALBEDO": "map_Kd",
    "MATERIAL_ROUGHNESS": "map_Pr",
    "MATERIAL_METALNESS": "map_Pm",
    "MATERIAL_EMISSION": "map_Ke",
    "MATERIAL_OPACITY": "map_d",
    "MATERIAL_SPECULAR": "map_Ps",
    "NORMAL": "norm",
    "AO": "map_ao",
    "HEIGHT": "disp",
}

# Toolbag 5 subroutine slots used by ``data/plugin/Examples/Creating Materials from Images.py``.
# importModel does not apply MTL maps, so Send to Marmoset assigns these after import.
TOOLBAG_MATERIAL_SLOTS = {
    "MATERIAL_ALBEDO": {"subroutine": "albedo", "shader": "Albedo", "field": "Albedo Map", "srgb": True},
    "MATERIAL_ROUGHNESS": {"subroutine": "microsurface", "shader": "Roughness", "field": "Roughness Map"},
    "MATERIAL_METALNESS": {"subroutine": "reflectivity", "shader": "Metalness", "field": "Metalness Map"},
    "MATERIAL_EMISSION": {"subroutine": "emissive", "shader": "Emissive", "field": "Emissive Map", "srgb": True},
    "MATERIAL_OPACITY": {"subroutine": "transparency", "shader": "Dither", "field": "Alpha Map"},
    "OPACITY": {"subroutine": "transparency", "shader": "Dither", "field": "Alpha Map"},
    "NORMAL": {"subroutine": "surface", "shader": "Normals", "field": "Normal Map"},
    "AO": {"subroutine": "occlusion", "shader": "Occlusion", "field": "Occlusion Map"},
    "HEIGHT": {"subroutine": "displacement", "shader": "Height", "field": "Displacement Map"},
}


@dataclass(frozen=True)
class HandoffMap:
    map_type: str
    texture_set: str
    source_path: Path
    staged_path: Path
    # 0 for an untiled map. Every field below is additive with a default so the untiled
    # construction above stays exactly what it was.
    udim_tile: int = 0
    width: int = 0
    height: int = 0
    logical_source_path: str = ""
    logical_staged_path: str = ""
    map_uuid: str = ""
    output_suffix: str = ""

    @property
    def is_tiled(self) -> bool:
        return bool(self.udim_tile)


@dataclass(frozen=True)
class HandoffPackage:
    root: Path
    mesh_path: Path
    maps: tuple[HandoffMap, ...]
    manifest_path: Path
    #: The bake project's Normal row format ("DIRECTX" / "OPENGL"). Painter decodes
    #: every tangent normal through the project-level setting, so a project created
    #: with the wrong one shows an inverted green channel on the baked Normal.
    normal_map_format: str = "DIRECTX"


def sanitize_name(value: str, fallback: str = "TextureSet") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("_.")
    return cleaned or fallback


# ---------------------------------------------------------------------------
# External application discovery
#
# Artists should not have to hunt for an install path, so every supported
# application is searched for in the places installers actually use: the
# uninstall/App Paths registry entries, the Program Files roots, Steam library
# folders, and (only when the user explicitly asks for a deep search) the
# well-known install folders on every fixed drive.  Candidates are ranked by the
# version baked into their install folder so the newest install wins.
# ---------------------------------------------------------------------------

APPLICATION_LABELS = {
    "painter": "Substance 3D Painter",
    "toolbag": "Marmoset Toolbag",
    "photoshop": "Adobe Photoshop",
    "designer": "Substance 3D Designer",
    "3dcoat": "3DCoat",
    "mari": "Mari",
}

#: Preference path, detect-enum id. Order is the Integrations list.
INTEGRATION_APPLICATIONS = (
    ("painter", "painter_executable", "PAINTER"),
    ("toolbag", "toolbag_executable", "TOOLBAG"),
    ("photoshop", "photoshop_executable", "PHOTOSHOP"),
    ("designer", "designer_executable", "DESIGNER"),
    ("3dcoat", "coat_executable", "COAT"),
    ("mari", "mari_executable", "MARI"),
)

SEND_TO_VISIBILITY = {
    "painter": "show_send_to_painter",
    "toolbag": "show_send_to_toolbag",
    "photoshop": "show_send_to_photoshop",
    "designer": "show_send_to_designer",
    "3dcoat": "show_send_to_coat",
    "mari": "show_send_to_mari",
}


def send_to_visibility_property(application: str) -> str:
    return SEND_TO_VISIBILITY[application]


def send_to_destination_enabled(prefs, application: str) -> bool:
    """True when that Send To entry should appear. Missing preferences keep every entry visible."""
    if prefs is None:
        return True
    prop = SEND_TO_VISIBILITY.get(application)
    if prop is None:
        return True
    return bool(getattr(prefs, prop, True))


def any_send_to_destination_enabled(prefs) -> bool:
    return any(send_to_destination_enabled(prefs, key) for key in SEND_TO_VISIBILITY)

_APPLICATION_ENV_NAMES = {
    "painter": ("ADOBE_SUBSTANCE_3D_PAINTER_PATH", "SUBSTANCE_PAINTER_PATH"),
    "toolbag": ("MARMOSET_TOOLBAG_PATH", "TOOLBAG_PATH"),
    "photoshop": ("PHOTOSHOP_PATH", "ADOBE_PHOTOSHOP_PATH"),
    "designer": ("SUBSTANCE_DESIGNER_PATH", "ADOBE_SUBSTANCE_3D_DESIGNER_PATH"),
    "3dcoat": ("THREEDCOAT_PATH", "COAT_PATH"),
    "mari": ("MARI_PATH", "FOUNDRY_MARI_PATH"),
}

_WINDOWS_EXECUTABLE_NAMES = {
    "painter": ("Adobe Substance 3D Painter.exe", "Substance 3D Painter.exe", "Substance Painter.exe"),
    "toolbag": ("toolbag.exe",),
    "photoshop": ("Photoshop.exe",),
    "designer": ("Adobe Substance 3D Designer.exe", "Substance 3D Designer.exe", "Substance Designer.exe"),
    "3dcoat": ("3DCoat.exe", "3DCoatDX.exe", "3DCoatGL.exe"),
    "mari": ("Mari.exe",),
}

# Globs evaluated against Program Files-style roots.
_WINDOWS_INSTALL_PATTERNS = {
    "painter": (
        "Adobe/Adobe Substance 3D Painter*/Adobe Substance 3D Painter.exe",
        "Adobe/Adobe Substance 3D Painter*/Substance 3D Painter.exe",
        "Adobe Substance 3D Painter*/Adobe Substance 3D Painter.exe",
        "Allegorithmic/Substance Painter*/Substance Painter.exe",
        "Substance Painter*/Substance Painter.exe",
    ),
    "toolbag": (
        "Marmoset/Toolbag*/toolbag.exe",
        "Marmoset/Marmoset Toolbag*/toolbag.exe",
        "Marmoset Toolbag*/toolbag.exe",
        "Toolbag*/toolbag.exe",
    ),
    "photoshop": (
        "Adobe/Adobe Photoshop*/Photoshop.exe",
        "Adobe Photoshop*/Photoshop.exe",
    ),
    "designer": (
        "Adobe/Adobe Substance 3D Designer*/Adobe Substance 3D Designer.exe",
        "Adobe Substance 3D Designer*/Adobe Substance 3D Designer.exe",
        "Allegorithmic/Substance Designer*/Substance Designer.exe",
    ),
    "3dcoat": (
        "3DCoat*/3DCoat.exe",
        "3DCoat*/3DCoatDX.exe",
        "3DCoat*/3DCoatGL.exe",
        "Pilgway/3DCoat*/3DCoat.exe",
    ),
    "mari": (
        "Mari*/Mari*.exe",
        "Foundry/Mari*/Mari*.exe",
    ),
}

# Evaluated against ``<library>/steamapps/common``.
_STEAM_COMMON_PATTERNS = {
    "painter": ("Substance*Painter*/Adobe Substance 3D Painter.exe", "Substance*Painter*/Substance*Painter.exe"),
    "toolbag": ("Marmoset Toolbag*/toolbag.exe", "Toolbag*/toolbag.exe"),
    "photoshop": (),
    "designer": (),
    "3dcoat": ("3DCoat*/3DCoat.exe",),
    "mari": (),
}

_MACOS_PATTERNS = {
    "painter": (
        "Adobe Substance 3D Painter*.app/Contents/MacOS/Adobe Substance 3D Painter",
        "Substance Painter*.app/Contents/MacOS/Substance Painter",
    ),
    "toolbag": ("Marmoset Toolbag*.app/Contents/MacOS/Toolbag", "Toolbag*.app/Contents/MacOS/Toolbag"),
    "photoshop": ("Adobe Photoshop*/Adobe Photoshop*.app/Contents/MacOS/Adobe Photoshop*",),
    "designer": ("Adobe Substance 3D Designer*.app/Contents/MacOS/Adobe Substance 3D Designer",),
    "3dcoat": ("3DCoat*.app/Contents/MacOS/3DCoat",),
    "mari": ("Mari*.app/Contents/MacOS/Mari*",),
}

_LINUX_PATTERNS = {
    "painter": (
        "Adobe Substance 3D Painter*/Adobe Substance 3D Painter",
        "Adobe_Substance_3D_Painter*/Adobe Substance 3D Painter",
        "Substance*Painter*/Substance*Painter",
    ),
    "toolbag": ("Marmoset Toolbag*/toolbag", "Toolbag*/toolbag"),
    "photoshop": (),
    "designer": (
        "Adobe Substance 3D Designer*/Adobe Substance 3D Designer",
        "Substance Designer*/Substance Designer",
    ),
    "3dcoat": ("3DCoat*/3DCoat",),
    "mari": ("Mari*/Mari*",),
}

_PATH_EXECUTABLE_NAMES = {
    "painter": ("Adobe Substance 3D Painter", "substance-painter", "substance_painter"),
    "toolbag": ("toolbag",),
    "photoshop": ("Photoshop", "photoshop"),
    "designer": ("Adobe Substance 3D Designer", "substance-designer"),
    "3dcoat": ("3DCoat", "3dcoat"),
    "mari": ("Mari", "mari"),
}

# An uninstall entry matches when every token of any one hint appears in its DisplayName.
_REGISTRY_NAME_HINTS = {
    "painter": (("substance", "painter"),),
    "toolbag": (("marmoset",), ("toolbag",)),
    "photoshop": (("photoshop",),),
    "designer": (("substance", "designer"),),
    "3dcoat": (("3dcoat",), ("3d-coat",), ("3d coat",)),
    "mari": (("foundry", "mari"), ("mari",)),
}

# "3D" in a product name is not a version number.
_VERSION_NOISE = re.compile(r"\b3\s*-?\s*D\b", re.IGNORECASE)
_VERSION_NUMBERS = re.compile(r"\d+(?:\.\d+)*")


def _normalize_application(application: str | Path | None) -> str:
    normalized = str(application or "").strip().casefold()
    # Designer before the Substance/Painter test: "Substance 3D Designer" contains both words.
    if "designer" in normalized:
        return "designer"
    if "photoshop" in normalized:
        return "photoshop"
    if "3dcoat" in normalized or "3d-coat" in normalized or "3d coat" in normalized:
        return "3dcoat"
    if "mari" in normalized:
        return "mari"
    if "painter" in normalized or "substance" in normalized:
        return "painter"
    return "toolbag"


def _glob_files(root: Path, pattern: str) -> list[Path]:
    try:
        return [candidate for candidate in root.glob(pattern) if candidate.is_file()]
    except (OSError, ValueError):
        return []


def _version_key(path: Path) -> tuple[int, int, int, int]:
    """Version parsed from the nearest enclosing folder that carries one.

    ``.../Marmoset/Toolbag 5/toolbag.exe`` -> ``(5, 0, 0, 0)`` and
    ``.../Adobe Substance 3D Painter 2024/…`` -> ``(2024, 0, 0, 0)``.
    """
    for part in reversed(path.parts[:-1]):
        matches = _VERSION_NUMBERS.findall(_VERSION_NOISE.sub(" ", part))
        if not matches:
            continue
        numbers = tuple(int(chunk) for chunk in matches[-1].split("."))[:4]
        return numbers + (0,) * (4 - len(numbers))  # type: ignore[return-value]
    return (0, 0, 0, 0)


def _rank_candidates(candidates: Iterable[Path]) -> list[Path]:
    unique: dict[str, Path] = {}
    for candidate in candidates:
        try:
            resolved = Path(candidate).expanduser().resolve()
            if not resolved.is_file():
                continue
        except OSError:
            continue
        unique.setdefault(str(resolved).casefold(), resolved)

    def sort_key(path: Path) -> tuple:
        try:
            modified = path.stat().st_mtime_ns
        except OSError:
            modified = 0
        return (_version_key(path), modified)

    return sorted(unique.values(), key=sort_key, reverse=True)


def _registry_string(key, name: str) -> str:
    import winreg

    try:
        value, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return ""
    return str(value or "").strip()


def _executables_from_registry_value(raw: str, names: Sequence[str]) -> list[Path]:
    """Executables named by an InstallLocation/DisplayIcon style registry value."""
    text = str(raw or "").strip().strip('"').strip()
    if not text:
        return []
    # DisplayIcon carries an icon index: "C:\...\toolbag.exe,0".
    head = text.rsplit(",", 1)[0].strip().strip('"')
    if head.casefold().endswith(".exe"):
        text = head
    candidate = Path(text).expanduser()
    wanted = {name.casefold() for name in names}
    try:
        if candidate.is_file():
            return [candidate] if candidate.name.casefold() in wanted else []
        if not candidate.is_dir():
            return []
    except OSError:
        return []
    found = [candidate / name for name in names if (candidate / name).is_file()]
    for name in names:
        found.extend(_glob_files(candidate, f"*/{name}"))
    return found


_UNINSTALL_SUBKEYS = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
)


def _windows_registry_candidates(application: str) -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []
    names = _WINDOWS_EXECUTABLE_NAMES[application]
    hints = _REGISTRY_NAME_HINTS[application]
    found: list[Path] = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for exe_name in names:
            try:
                with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}") as key:
                    found.extend(_executables_from_registry_value(_registry_string(key, "") or _registry_string(key, "Path"), names))
            except OSError:
                continue
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in _UNINSTALL_SUBKEYS:
            try:
                with winreg.OpenKey(hive, subkey) as root:
                    child_count = winreg.QueryInfoKey(root)[0]
                    for index in range(child_count):
                        try:
                            with winreg.OpenKey(root, winreg.EnumKey(root, index)) as child:
                                display = _registry_string(child, "DisplayName").casefold()
                                if not display or not any(all(token in display for token in hint) for hint in hints):
                                    continue
                                for value_name in ("InstallLocation", "DisplayIcon", "InstallDir", "Path"):
                                    found.extend(_executables_from_registry_value(_registry_string(child, value_name), names))
                        except OSError:
                            continue
            except OSError:
                continue
    return found


def _windows_fixed_drive_roots() -> list[Path]:
    """Fixed (non-removable, non-network) drive roots, so a deep search never
    spins up an empty optical drive or stalls on a disconnected share."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        mask = int(kernel32.GetLogicalDrives())
        roots = []
        for index in range(26):
            if not mask & (1 << index):
                continue
            letter = f"{chr(ord('A') + index)}:\\"
            if int(kernel32.GetDriveTypeW(ctypes.c_wchar_p(letter))) == 3:  # DRIVE_FIXED
                roots.append(Path(letter))
        return roots
    except Exception:
        return []


def _dedupe_dirs(roots: Iterable[Path]) -> list[Path]:
    unique: dict[str, Path] = {}
    for root in roots:
        try:
            if not root.is_dir():
                continue
        except OSError:
            continue
        unique.setdefault(str(root).casefold(), root)
    return list(unique.values())


def _windows_search_roots(deep: bool) -> list[Path]:
    roots = [
        Path(value)
        for value in (
            os.environ.get("PROGRAMW6432", ""),
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
        )
        if value
    ]
    if deep:
        for drive in _windows_fixed_drive_roots():
            roots.extend((drive, drive / "Program Files", drive / "Program Files (x86)", drive / "Games", drive / "Apps"))
    return _dedupe_dirs(roots)


def _steam_library_roots(deep: bool) -> list[Path]:
    """Steam install roots plus every additional library folder Steam knows about."""
    bases: list[Path] = []
    if sys.platform.startswith("win"):
        try:
            import winreg

            for hive, subkey, value_name in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
            ):
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        raw = _registry_string(key, value_name)
                except OSError:
                    continue
                if raw:
                    bases.append(Path(raw).expanduser())
        except ImportError:
            pass
        for value in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", "")):
            if value:
                bases.append(Path(value) / "Steam")
        if deep:
            for drive in _windows_fixed_drive_roots():
                bases.extend((drive / "SteamLibrary", drive / "Steam", drive / "Games/SteamLibrary"))
    else:
        home = Path.home()
        bases.extend((home / ".local/share/Steam", home / ".steam/steam", home / "Library/Application Support/Steam"))
    libraries = list(bases)
    for base in _dedupe_dirs(bases):
        for manifest in (base / "steamapps/libraryfolders.vdf", base / "config/libraryfolders.vdf"):
            try:
                text = manifest.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            libraries.extend(Path(match.group(1).replace("\\\\", "\\")).expanduser() for match in re.finditer(r'"path"\s*"([^"]+)"', text))
    return _dedupe_dirs(libraries)


def discover_application_candidates(application: str | None, deep: bool = False) -> list[Path]:
    """Every installation of ``application`` we can find, newest version first.

    ``deep`` widens the sweep to the common install folders on every fixed drive;
    it costs a few extra directory listings, so only the explicit auto-detect
    button asks for it.
    """
    normalized = _normalize_application(application)
    found: list[Path] = []
    if sys.platform.startswith("win"):
        found.extend(_windows_registry_candidates(normalized))
        for root in _windows_search_roots(deep):
            for pattern in _WINDOWS_INSTALL_PATTERNS[normalized]:
                found.extend(_glob_files(root, pattern))
        for library in _steam_library_roots(deep):
            for pattern in _STEAM_COMMON_PATTERNS[normalized]:
                found.extend(_glob_files(library, f"steamapps/common/{pattern}"))
    elif sys.platform == "darwin":
        for root in _dedupe_dirs((Path("/Applications"), Path.home() / "Applications")):
            for pattern in _MACOS_PATTERNS[normalized]:
                found.extend(_glob_files(root, pattern))
    else:
        home = Path.home()
        roots = (Path("/opt"), Path("/usr/local"), Path("/usr/share"), home, home / ".local/share")
        for root in _dedupe_dirs(roots):
            for pattern in _LINUX_PATTERNS[normalized]:
                found.extend(_glob_files(root, pattern))
        for library in _steam_library_roots(deep):
            for pattern in _LINUX_PATTERNS[normalized]:
                found.extend(_glob_files(library, f"steamapps/common/{pattern}"))
    for name in _PATH_EXECUTABLE_NAMES[normalized]:
        on_path = shutil.which(name)
        if on_path:
            found.append(Path(on_path))
    return _rank_candidates(found)


def _environment_executable(application: str) -> Path | None:
    for env_name in _APPLICATION_ENV_NAMES[_normalize_application(application)]:
        raw = str(os.environ.get(env_name, "") or "").strip()
        if not raw:
            continue
        candidate = Path(raw).expanduser()
        if candidate.is_file():
            return candidate.resolve()
    return None


def resolve_application_executable(configured: str | Path | None, application: str) -> Path | None:
    configured_path = Path(str(configured or "").strip()).expanduser() if str(configured or "").strip() else None
    if configured_path is not None and configured_path.is_file():
        return configured_path.resolve()
    environment = _environment_executable(application)
    if environment is not None:
        return environment
    candidates = discover_application_candidates(application)
    return candidates[0] if candidates else None


def painter_suffix(map_type: str) -> str | None:
    return PAINTER_MESH_MAP_SUFFIXES.get(str(map_type or "").strip().upper())


def output_tile_files(output) -> list[tuple[int, Path, int, int]]:
    """``(tile, path, width, height)`` for every live tile of one output, ascending.

    An untiled output yields a single entry with tile ``0``. Stale tiles are skipped: they are
    files an earlier bake left behind for a tile that is no longer occupied, and shipping them
    downstream would hand the artist a texture that no geometry references.
    """
    tiles: list[tuple[int, Path, int, int]] = []
    for row in getattr(output, "udim_tiles", []) or ():
        if bool(getattr(row, "stale", False)):
            continue
        try:
            tile_number = int(getattr(row, "udim_tile", 0) or 0)
        except (TypeError, ValueError):
            continue
        raw_path = str(getattr(row, "file_path", "") or "").strip()
        if not tile_number or not raw_path:
            continue
        width = int(getattr(row, "width", 0) or 0)
        height = int(getattr(row, "height", 0) or 0)
        tiles.append((tile_number, Path(raw_path).expanduser(), width, height))
    if tiles:
        return sorted(tiles, key=lambda entry: entry[0])
    raw_path = str(getattr(output, "file_path", "") or "").strip()
    return [(0, Path(raw_path).expanduser(), 0, 0)] if raw_path else []


def _measured_size(path: Path, width: int, height: int) -> tuple[int, int]:
    if width > 0 and height > 0:
        return width, height
    try:
        from . import udim_images
    except ImportError:  # pragma: no cover - standalone import of this module
        return width, height
    return udim_images.read_image_size(path)


def _logical_token_path(path: Path, udim_tile: int) -> str:
    """``…_normal.1002.png`` -> ``…_normal.<UDIM>.png``. Empty for an untiled map."""
    if not udim_tile:
        return ""
    from . import udim

    return udim.logical_udim_path(path)


def representative_maps(maps: Iterable[HandoffMap]) -> list[HandoffMap]:
    """One entry per (texture set, map type) -- the lowest tile.

    Destination-side plumbing that models a map as a single texture (the Painter mesh-map
    slots, the OBJ/MTL directives) must see one file, not forty. The full tile list still
    reaches the destination through the copied files and the manifest.
    """
    chosen: dict[tuple[str, str], HandoffMap] = {}
    for item in maps:
        key = (item.texture_set.casefold(), item.map_type)
        current = chosen.get(key)
        if current is None or item.udim_tile < current.udim_tile:
            chosen[key] = item
    return list(chosen.values())


def _output_identity(output, group_texture_sets: Mapping[str, str]) -> tuple[str, str]:
    """``(texture set, map type)`` for one tracked output.

    Tracked outputs carry the RAW stack type (a material row's channels are all
    ``MATERIAL``) with the effective type alongside. Package by the effective one:
    keyed by the raw type, Base Color, Roughness and Metalness of one texture set
    collapsed onto a single ``<set>_material`` file and Toolbag got no PBR
    directives at all (2026-09-06).
    """
    map_type = (
        str(getattr(output, "effective_map_type", "") or "").strip().upper()
        or str(getattr(output, "map_type", "") or "").strip().upper()
    )
    group_name = str(getattr(output, "group_name", "") or "").strip()
    texture_set = sanitize_name(group_texture_sets.get(group_name) or group_name)
    return texture_set, map_type


def _variant_token(output_suffix: str) -> str:
    """The file-name form of an output suffix, or ``""`` when there is none."""
    return sanitize_name(output_suffix, "").lower()


@dataclass(frozen=True)
class LiveMapFile:
    """One live baked file, in output order, with Painter/Toolbag identity rules applied."""

    texture_set: str
    map_type: str
    output_suffix: str
    variant: str
    include_variant: bool
    udim_tile: int
    source_path: Path
    width: int
    height: int
    map_uuid: str


def live_map_files(outputs: Iterable[object], group_texture_sets: Mapping[str, str]) -> list[LiveMapFile]:
    """Every live baked file, deduped the same way a Painter/Toolbag package is.

    Two rows of one type in one texture set (AO Raycast + AO Diffusive, Signed +
    Principal curvature, ...) are different maps that happen to share a type, so
    the variant has to be part of the identity: keyed by type alone the second
    one was skipped as a duplicate and never reached Painter or Toolbag.
    The variant only enters the FILE NAME where it is actually needed. Appending
    it unconditionally would rename the single-variant file every artist already
    links to downstream.

    The tile is part of the identity too: without it, tile 1002 would be skipped
    as a duplicate of 1001. Tile numbers are preserved verbatim.
    """
    outputs = list(outputs)
    variants: dict[tuple[str, str], set[str]] = {}
    for output in outputs:
        variant_set, variant_type = _output_identity(output, group_texture_sets)
        variants.setdefault((variant_set.casefold(), variant_type), set()).add(
            _variant_token(str(getattr(output, "output_suffix", "") or ""))
        )
    seen: set[tuple[str, str, str, int]] = set()
    files: list[LiveMapFile] = []
    for output in outputs:
        texture_set, map_type = _output_identity(output, group_texture_sets)
        map_uuid = str(getattr(output, "map_uuid", "") or "")
        output_suffix = str(getattr(output, "output_suffix", "") or "")
        variant = _variant_token(output_suffix)
        include_variant = bool(variant and len(variants.get((texture_set.casefold(), map_type), ())) > 1)
        for udim_tile, source, width, height in output_tile_files(output):
            if not source.is_file():
                continue
            key = (texture_set.casefold(), map_type, variant, udim_tile)
            if key in seen:
                continue
            seen.add(key)
            files.append(
                LiveMapFile(
                    texture_set,
                    map_type,
                    output_suffix,
                    variant,
                    include_variant,
                    udim_tile,
                    source,
                    width,
                    height,
                    map_uuid,
                )
            )
    return files


def build_package(
    *,
    root: Path,
    mesh_path: Path,
    outputs: Iterable[object],
    group_texture_sets: Mapping[str, str],
    normal_map_format: str = "DIRECTX",
    stage_maps: bool = True,
) -> HandoffPackage:
    root = Path(root)
    maps_root = root / "maps"
    maps_root.mkdir(parents=True, exist_ok=True)
    staged: list[HandoffMap] = []
    for item in live_map_files(outputs, group_texture_sets):
        variant_segment = f"_{item.variant}" if item.include_variant else ""
        suffix = painter_suffix(item.map_type) or sanitize_name(item.map_type, "map").lower()
        source = item.source_path
        tile_segment = f".{item.udim_tile}" if item.udim_tile else ""
        destination = maps_root / f"{item.texture_set}_{suffix}{variant_segment}{tile_segment}{source.suffix.lower()}"
        # Editor handoffs link the bake files in place. Copying every 4k/8k map into
        # the handoff folder again would duplicate the bake on disk.
        if stage_maps and source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        elif not stage_maps:
            destination = source
        measured_width, measured_height = _measured_size(source, item.width, item.height)
        staged.append(
            HandoffMap(
                item.map_type,
                item.texture_set,
                source.resolve(),
                destination.resolve(),
                udim_tile=item.udim_tile,
                width=measured_width,
                height=measured_height,
                logical_source_path=_logical_token_path(source.resolve(), item.udim_tile),
                logical_staged_path=_logical_token_path(destination.resolve(), item.udim_tile),
                map_uuid=item.map_uuid,
                output_suffix=item.output_suffix,
            )
        )

    manifest_path = root / "handoff.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": 1,
                "mesh": str(Path(mesh_path).resolve()),
                "maps": [_manifest_entry(item) for item in staged],
                "texture_sets": _manifest_texture_sets(staged),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return HandoffPackage(
        root.resolve(),
        Path(mesh_path).resolve(),
        tuple(staged),
        manifest_path.resolve(),
        normal_map_format=str(normal_map_format or "DIRECTX").strip().upper() or "DIRECTX",
    )


def _manifest_entry(item: HandoffMap) -> dict:
    entry = {
        "map_type": item.map_type,
        "texture_set": item.texture_set,
        "source": str(item.source_path),
        "path": str(item.staged_path),
    }
    if item.udim_tile:
        # Only tiled maps carry these, so an untiled manifest is unchanged from before UDIM.
        entry.update(
            {
                "udim_tile": item.udim_tile,
                "logical_source": item.logical_source_path,
                "logical_path": item.logical_staged_path,
                "width": item.width,
                "height": item.height,
            }
        )
    if item.map_uuid:
        entry["map_uuid"] = item.map_uuid
    if item.output_suffix:
        entry["output_suffix"] = item.output_suffix
    return entry


def _manifest_texture_sets(staged: Sequence[HandoffMap]) -> list[dict]:
    """Manifest grouped by texture set, then by map UUID -- the §9.3 shape.

    A flat list cannot express "these forty files are one map"; the destination needs the
    grouping to rebuild the tiled texture rather than importing forty unrelated images.
    Maps without a UUID group under their map type, so a legacy output still lands somewhere
    sensible instead of collapsing into one anonymous bucket. The variant joins that fallback
    key for the same reason it joins the file name: two uuid-less AO rows of one set are two
    maps, and merging them would list one file as a tile of the other.
    """
    by_set: dict[str, dict[str, list[HandoffMap]]] = {}
    for item in staged:
        fallback_key = f"type:{item.map_type}"
        if item.output_suffix:
            fallback_key = f"{fallback_key}:{item.output_suffix}"
        by_set.setdefault(item.texture_set, {}).setdefault(item.map_uuid or fallback_key, []).append(item)
    result: list[dict] = []
    for texture_set in sorted(by_set):
        maps: list[dict] = []
        for map_key in sorted(by_set[texture_set]):
            entries = sorted(by_set[texture_set][map_key], key=lambda entry: entry.udim_tile)
            first = entries[0]
            maps.append(
                {
                    "map_uuid": first.map_uuid,
                    "map_type": first.map_type,
                    "output_suffix": first.output_suffix,
                    "logical_path": first.logical_staged_path,
                    "tiled": bool(first.udim_tile),
                    "tiles": [
                        {
                            "udim_tile": entry.udim_tile,
                            "path": str(entry.staged_path),
                            "source": str(entry.source_path),
                            "width": entry.width,
                            "height": entry.height,
                        }
                        for entry in entries
                    ],
                }
            )
        result.append({"texture_set": texture_set, "maps": maps})
    return result


def painter_command(executable: Path, package: HandoffPackage) -> list[str]:
    command = [str(Path(executable)), "--mesh", str(package.mesh_path), "--export-path", str(package.root / "exports")]
    # One --mesh-map per map, not per tile: Painter's mesh-map slots hold a single resource,
    # so passing every tile would just overwrite the slot N times. Painter resolves the rest
    # of the sequence from the numeric files sitting beside the one it is handed.
    # Same vocabulary as the remote script (PAINTER_MESH_MAP_USAGES): the two routes
    # used to ship different map sets, so a cold launch dropped Bent Normal, Height and
    # Opacity that a running Painter received. Painter slots a --mesh-map file by its
    # name suffix; a suffix it does not know is still imported beside the project.
    for item in representative_maps(package.maps):
        if str(item.map_type or "").strip().upper() in PAINTER_MESH_MAP_USAGES:
            command.extend(("--mesh-map", str(item.staged_path)))
    return command


def painter_remote_reachable(host: str = "localhost", port: int = 60041) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.5):
            return True
    except OSError:
        return False


def application_is_running(executable: Path) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {Path(executable).name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    output = (result.stdout or "").casefold()
    return Path(executable).name.casefold() in output and "no tasks are running" not in output


def painter_is_running(executable: Path) -> bool:
    return application_is_running(executable)


def toolbag_is_running(executable: Path) -> bool:
    return application_is_running(executable)


def painter_normal_map_format(package: HandoffPackage) -> str:
    """Painter's ``NormalMapFormat`` member name for the package's Normal row format."""
    normalized = str(getattr(package, "normal_map_format", "") or "").strip().upper()
    return "OpenGL" if normalized == "OPENGL" else "DirectX"


def painter_remote_script(package: HandoffPackage, *, update_existing: bool = False) -> str:
    # See painter_command: a mesh-map slot takes one resource, so the representative tile is
    # imported and the remaining tiles ride along as the numeric files beside it.
    maps = [
        {
            "map_type": item.map_type,
            "texture_set": item.texture_set,
            "path": str(item.staged_path),
        }
        for item in representative_maps(package.maps)
        if item.map_type in PAINTER_MESH_MAP_USAGES
    ]
    project_action = (
        "if not substance_painter.project.is_open(): raise RuntimeError('No Painter project is open to update')\n"
        "reload_state = {'status': None}\n"
        "def on_reload(status, state=reload_state): state['status'] = status\n"
        "substance_painter.project.reload_mesh(mesh_file_path=mesh_file, settings=substance_painter.project.MeshReloadingSettings(import_cameras=False, preserve_strokes=True), loading_status_cb=on_reload)\n"
        "for _ in range(400):\n"
        "    if reload_state['status'] is not None: break\n"
        "    PySide6.QtCore.QCoreApplication.processEvents(); time.sleep(0.05)\n"
        "mesh_reload_succeeded = reload_state['status'] == substance_painter.project.ReloadMeshStatus.SUCCESS\n"
        if update_existing
        else
        "if substance_painter.project.is_open(): substance_painter.project.close()\n"
        f"settings = substance_painter.project.Settings(normal_map_format=substance_painter.project.NormalMapFormat.{painter_normal_map_format(package)}, tangent_space_mode=substance_painter.project.TangentSpace.PerFragment)\n"
        "substance_painter.project.create(mesh_file_path=mesh_file, settings=settings)\n"
    )
    return (
        "import json, os, time\n"
        "import PySide6.QtCore\n"
        "import substance_painter.project\n"
        "import substance_painter.resource\n"
        "import substance_painter.textureset\n"
        f"mesh_file = {json.dumps(str(package.mesh_path))}\n"
        f"mesh_maps = json.loads({json.dumps(json.dumps(maps))})\n"
        f"usage_names = json.loads({json.dumps(json.dumps(PAINTER_MESH_MAP_USAGES))})\n"
        "def norm(value): return ''.join(c for c in str(value or '').lower() if c.isalnum())\n"
        + project_action
        +
        "for _ in range(200):\n"
        "    if substance_painter.project.is_in_edition_state(): break\n"
        "    PySide6.QtCore.QCoreApplication.processEvents(); time.sleep(0.05)\n"
        "texture_sets = substance_painter.textureset.all_texture_sets()\n"
        "by_name = {}\n"
        "for texture_set in texture_sets:\n"
        # A set whose name equals its original name (every set of a freshly created
        # project) must be listed once: listed twice it read as two matches, and every
        # multi-set project failed with 'texture-set match failed'.
        "    for name in (getattr(texture_set, 'name', ''), getattr(texture_set, 'original_name', '')):\n"
        "        bucket = by_name.setdefault(norm(name), []) if norm(name) else None\n"
        "        if bucket is not None and texture_set not in bucket: bucket.append(texture_set)\n"
        "grouped = {}\n"
        "for item in mesh_maps: grouped.setdefault(norm(item['texture_set']), []).append(item)\n"
        "assigned = []\n"
        "skipped = []\n"
        "for key, items in grouped.items():\n"
        "    matches = by_name.get(key, [])\n"
        "    target = matches[0] if len(matches) == 1 else (texture_sets[0] if len(texture_sets) == 1 and len(grouped) == 1 else None)\n"
        "    if target is None: raise RuntimeError('Painter has no single texture set matching ' + repr(items[0]['texture_set']) + ' (Painter texture sets: ' + ', '.join(str(getattr(t, 'name', '')) for t in texture_sets) + ')')\n"
        "    for item in items:\n"
        # A usage this Painter build does not define skips that map instead of raising
        # mid-loop, which left the project half-populated and reported the whole send as failed.
        "        usage = getattr(substance_painter.textureset.MeshMapUsage, usage_names.get(item['map_type'], ''), None)\n"
        "        if usage is None:\n"
        "            skipped.append(item['map_type']); continue\n"
        "        resource = substance_painter.resource.import_project_resource(file_path=item['path'], resource_usage=substance_painter.resource.Usage.TEXTURE, name=os.path.splitext(os.path.basename(item['path']))[0], group='FyrBaker')\n"
        "        target.set_mesh_map_resource(usage, resource.identifier())\n"
        "        assigned.append(item['path'])\n"
        "if mesh_maps and not assigned: raise RuntimeError('Painter did not assign any mesh maps' + (' (this Painter has no slot for: ' + ', '.join(sorted(set(skipped))) + ')' if skipped else ''))\n"
    )


def painter_remote_exec(script: str, host: str = "localhost", port: int = 60041) -> str:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    payload = json.dumps({"python": encoded}).encode("utf-8")
    connection = http.client.HTTPConnection(host, int(port), timeout=3600)
    try:
        connection.request("POST", "/run.json", payload, {"Content-type": "application/json", "Accept": "application/json"})
        response = connection.getresponse()
        data = response.read().decode("utf-8", errors="replace")
    finally:
        connection.close()
    if response.status >= 400:
        raise RuntimeError(f"Painter remote scripting failed with HTTP {response.status}: {data}")
    try:
        parsed = json.loads(data) if data else None
    except ValueError:
        parsed = None
    if isinstance(parsed, dict) and parsed.get("error"):
        raise RuntimeError(f"Painter remote scripting failed: {parsed['error']}")
    if "Traceback (most recent call last):" in data:
        raise RuntimeError(f"Painter remote scripting failed: {data}")
    return data


#: How often the deferred handoff asks a starting Painter whether it is listening.
PAINTER_LAUNCH_POLL_SECONDS = 0.5

#: ``send_package_to_painter`` outcomes.
PAINTER_HANDOFF_SENT = "sent"
PAINTER_HANDOFF_LAUNCHING = "launching"


def _default_timer_register():
    """Blender's app-timer registrar, or None outside Blender."""
    try:
        import bpy  # type: ignore
    except Exception:
        return None
    register = getattr(getattr(getattr(bpy, "app", None), "timers", None), "register", None)
    return register if callable(register) else None


def painter_launch_poll_callback(
    package: HandoffPackage,
    *,
    update_existing: bool = False,
    deadline: float,
    poll_interval: float = PAINTER_LAUNCH_POLL_SECONDS,
    on_status=None,
    now_fn=time.monotonic,
    reachable_fn=None,
    exec_fn=None,
):
    """Build the callback that finishes a Painter handoff once Painter answers.

    Painter takes seconds to come up. Waiting for it on the calling thread froze
    Blender for the whole startup, so the wait lives on an app timer instead: the
    returned zero-argument callable reports ``poll_interval`` while Painter is
    still loading and ``None`` once the maps were sent, the send failed, or the
    deadline passed.
    """
    reachable = reachable_fn if callable(reachable_fn) else painter_remote_reachable
    run_script = exec_fn if callable(exec_fn) else painter_remote_exec

    def _report(message: str, ok: bool) -> None:
        if callable(on_status):
            try:
                on_status(message, ok)
            except Exception:
                pass

    def _poll():
        try:
            if not reachable():
                if now_fn() < deadline:
                    return poll_interval
                _report(
                    "Substance Painter started but did not answer. "
                    "Turn on remote scripting in Painter, then send again",
                    False,
                )
                return None
            run_script(painter_remote_script(package, update_existing=update_existing))
        except Exception as exc:  # noqa: BLE001 - a timer callback must never raise
            _report(f"Painter handoff failed: {exc}", False)
            return None
        _report(f"Sent {len(package.maps)} baked map(s) to Painter", True)
        return None

    return _poll


def send_package_to_painter(
    executable: Path,
    package: HandoffPackage,
    *,
    update_existing: bool = False,
    timeout_seconds: float = 30.0,
    register_timer=None,
    on_status=None,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
) -> str:
    """Send the staged package to Painter, launching Painter first if needed.

    Returns ``PAINTER_HANDOFF_SENT`` when the maps went across during this call,
    or ``PAINTER_HANDOFF_LAUNCHING`` when Painter was started and the send was
    handed to a timer. ``on_status(message, ok)`` receives the deferred outcome.
    """
    if painter_remote_reachable():
        painter_remote_exec(painter_remote_script(package, update_existing=update_existing))
        return PAINTER_HANDOFF_SENT

    if painter_is_running(executable):
        raise RuntimeError("Painter is already running without remote scripting. Close Painter and send again")
    # Update with no Painter open has no project to update, so it launches and
    # sends like Send: a fresh Painter needs a new project, not a mesh reload.
    update_existing = False

    subprocess.Popen(
        [str(executable), "--enable-remote-scripting"],
        env=clean_external_environment(),
    )

    poll = painter_launch_poll_callback(
        package,
        update_existing=update_existing,
        deadline=now_fn() + max(0.0, float(timeout_seconds)),
        on_status=on_status,
        now_fn=now_fn,
    )

    register = register_timer if callable(register_timer) else _default_timer_register()
    if register is None:
        # No app-timer facility (outside Blender, or a very old build): drive the
        # same callback here rather than keeping a second code path around.
        while True:
            delay = poll()
            if delay is None:
                return PAINTER_HANDOFF_SENT
            sleep_fn(delay)

    register(poll, first_interval=PAINTER_LAUNCH_POLL_SECONDS)
    return PAINTER_HANDOFF_LAUNCHING


def clean_external_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """Do not leak Blender's private OCIO configuration into downstream DCCs."""
    cleaned = dict(os.environ if environment is None else environment)
    for key in tuple(cleaned):
        if key.upper() == "OCIO" or key.upper().startswith("OCIO_"):
            cleaned.pop(key, None)
    return cleaned


def write_painter_mtl(package: HandoffPackage) -> Path:
    """Declare texture-set materials without Toolbag-only PBR map directives."""
    mtl_path = package.mesh_path.with_suffix(".mtl")
    texture_sets = sorted({item.texture_set for item in package.maps})
    lines: list[str] = ["# Fyr Baker Painter handoff"]
    for texture_set in texture_sets:
        lines.extend(("", f"newmtl {texture_set}", "Kd 1.0 1.0 1.0"))
    mtl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mtl_path


def write_toolbag_mtl(package: HandoffPackage) -> Path:
    by_set: dict[str, dict[str, Path]] = {}
    # An MTL directive takes one path, and the format has no UDIM token, so a tiled map is
    # referenced by its lowest tile's concrete file. Toolbag expands the numeric sequence from
    # there; emitting the literal "<UDIM>" would give loaders a filename that does not exist.
    for item in representative_maps(package.maps):
        directive = TOOLBAG_MTL_DIRECTIVES.get(item.map_type)
        if directive:
            by_set.setdefault(item.texture_set, {})[directive] = item.staged_path
    mtl_path = package.mesh_path.with_suffix(".mtl")
    lines: list[str] = ["# Fyr Baker Toolbag handoff"]
    texture_sets = sorted({item.texture_set for item in package.maps} | set(by_set))
    for texture_set in texture_sets:
        lines.extend(("", f"newmtl {texture_set}", "Kd 1.0 1.0 1.0", "Pr 0.5", "Pm 0.0"))
        for directive, path in sorted(by_set.get(texture_set, {}).items()):
            try:
                relative = os.path.relpath(path, mtl_path.parent).replace("\\", "/")
            except ValueError:
                # Windows has no relative path between two drives (an output folder
                # on D: beside a handoff staged on C:). The absolute path still
                # resolves for the loader.
                relative = str(path).replace("\\", "/")
            lines.append(f"{directive} {relative}")
    mtl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mtl_path


def rewrite_obj_materials(obj_path: Path, object_texture_sets: Mapping[str, str], mtl_path: Path) -> None:
    obj_path = Path(obj_path)
    lookup = {_object_key(name): sanitize_name(value) for name, value in object_texture_sets.items()}
    result = [f"mtllib {Path(mtl_path).name}"]
    active_material: str | None = None
    for line in obj_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("mtllib "):
            continue
        if line.startswith(("o ", "g ")):
            name = line[2:].strip()
            matched_material = lookup.get(_object_key(name))
            if matched_material is not None or line.startswith("o "):
                active_material = matched_material
            result.append(line)
            if active_material:
                result.append(f"usemtl {active_material}")
            continue
        if line.startswith("usemtl ") and active_material:
            continue
        result.append(line)
    obj_path.write_text("\n".join(result) + "\n", encoding="utf-8")


def toolbag_material_assignments(package: HandoffPackage) -> dict[str, list[dict]]:
    """Per texture-set Toolbag subroutine assignments for maps the material can show."""
    flip_y = str(getattr(package, "normal_map_format", "DIRECTX") or "DIRECTX").strip().upper() != "OPENGL"
    by_set: dict[str, list[dict]] = {}
    for item in representative_maps(package.maps):
        slot = TOOLBAG_MATERIAL_SLOTS.get(str(item.map_type or "").strip().upper())
        if slot is None:
            continue
        entry = {
            "subroutine": slot["subroutine"],
            "shader": slot["shader"],
            "field": slot["field"],
            "path": str(item.staged_path),
        }
        if slot.get("srgb"):
            entry["srgb"] = True
        if item.map_type == "NORMAL":
            entry["flip_y"] = flip_y
            entry["object_space"] = False
        by_set.setdefault(item.texture_set, []).append(entry)
    return by_set


def toolbag_update_request_path(package: HandoffPackage) -> Path:
    return Path(package.root) / "update_request.json"


_TOOLBAG_MAP_VERSION = re.compile(r"_u(\d+)$")


def _toolbag_map_versions(staged: Path) -> list[tuple[int, Path]]:
    """Earlier Update copies of one staged map: ``<stem>_u<N><ext>`` beside it."""
    versions = []
    for candidate in staged.parent.glob(f"{glob.escape(staged.stem)}_u*{staged.suffix}"):
        match = _TOOLBAG_MAP_VERSION.search(candidate.stem[len(staged.stem):])
        if match and candidate.stem == f"{staged.stem}_u{match.group(1)}":
            versions.append((int(match.group(1)), candidate))
    return versions


def remove_toolbag_map_versions(package: HandoffPackage) -> None:
    for item in package.maps:
        for _, old in _toolbag_map_versions(Path(item.staged_path)):
            old.unlink(missing_ok=True)


def _version_toolbag_maps(assignments: dict[str, list[dict]], maps_root: Path) -> None:
    """Move each assigned map to a fresh name and point the assignment at it.

    Toolbag caches textures by path: re-assigning, or even its own Reload button,
    keeps the old pixels for a path it has loaded. A new name forces a fresh read.
    The staged file is moved, not copied, so the handoff folder still holds one
    copy per map; older versions are deleted. Only staged copies under
    ``maps_root`` are moved, never a bake output linked in place.
    """
    maps_root = Path(maps_root).resolve()
    moved: dict[str, str] = {}
    for items in assignments.values():
        for entry in items:
            source = entry["path"]
            if source not in moved:
                staged = Path(source)
                if staged.resolve().parent != maps_root or not staged.is_file():
                    moved[source] = source
                    continue
                versions = _toolbag_map_versions(staged)
                generation = max((number for number, _ in versions), default=0) + 1
                target = staged.with_name(f"{staged.stem}_u{generation}{staged.suffix}")
                os.replace(staged, target)
                for _, old in versions:
                    old.unlink(missing_ok=True)
                moved[source] = str(target)
            entry["path"] = moved[source]


def write_toolbag_update_request(package: HandoffPackage) -> Path:
    """Ask the open Toolbag send-script to replace the mesh and refresh maps in place."""
    path = toolbag_update_request_path(package)
    assignments = toolbag_material_assignments(package)
    _version_toolbag_maps(assignments, Path(package.root) / "maps")
    payload = {
        "mesh": str(package.mesh_path),
        "assignments": assignments,
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, path)
    return path


def write_toolbag_import_script(package: HandoffPackage) -> Path:
    """Import the mesh as a file reference, assign maps, and watch for in-place updates.

    ``importModel`` alone leaves materials empty. A second import would add a duplicate,
    so Update destroys the previous Fyr mesh and imports once, then reassigns maps.
    """
    script_path = package.root / "open_in_toolbag.py"
    script_path.write_text(
        "import json\n"
        "import os\n"
        "import mset\n"
        f"mesh = {json.dumps(str(package.mesh_path))}\n"
        f"assignments = json.loads({json.dumps(json.dumps(toolbag_material_assignments(package)))})\n"
        f"request_path = {json.dumps(str(toolbag_update_request_path(package)))}\n"
        "\n"
        "def same_path(left, right):\n"
        "    try:\n"
        "        return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))\n"
        "    except Exception:\n"
        "        return False\n"
        "\n"
        "def protected(obj):\n"
        "    for name in ('CameraObject', 'LightObject', 'SkyBoxObject', 'FogObject', 'BakerObject', 'TextureProjectObject', 'RenderObject', 'ShadowCatcherObject'):\n"
        "        cls = getattr(mset, name, None)\n"
        "        if cls is not None and isinstance(obj, cls):\n"
        "            return True\n"
        "    return False\n"
        "\n"
        "def mark_reference(obj):\n"
        "    if obj is None:\n"
        "        return\n"
        "    try:\n"
        "        if isinstance(obj, mset.ExternalObject):\n"
        "            obj.autoReload = True\n"
        "            obj.replaceTransforms = True\n"
        "    except Exception:\n"
        "        pass\n"
        "    try:\n"
        "        for child in obj.getChildren() or []:\n"
        "            mark_reference(child)\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "def import_as_reference(path):\n"
        "    prefs = mset.getPreferences()\n"
        "    restore = None\n"
        "    try:\n"
        "        restore = prefs.importModelsAsReferences\n"
        "        prefs.importModelsAsReferences = True\n"
        "    except Exception:\n"
        "        pass\n"
        "    try:\n"
        "        return mset.importModel(path)\n"
        "    finally:\n"
        "        if restore is not None:\n"
        "            try:\n"
        "                prefs.importModelsAsReferences = restore\n"
        "            except Exception:\n"
        "                pass\n"
        "\n"
        "def apply_maps(mat, items):\n"
        "    for item in items:\n"
        "        try:\n"
        "            mat.setSubroutine(item['subroutine'], item['shader'])\n"
        "            sub = mat.getSubroutine(item['subroutine'])\n"
        "            sub.setField(item['field'], item['path'])\n"
        "            if 'flip_y' in item:\n"
        "                try:\n"
        "                    sub.setField('Flip Y', bool(item['flip_y']))\n"
        "                    sub.setField('Object Space', bool(item.get('object_space')))\n"
        "                except Exception:\n"
        "                    pass\n"
        "            if item.get('srgb'):\n"
        "                texture = sub.getField(item['field'])\n"
        "                if texture is not None:\n"
        "                    texture.sRGB = True\n"
        "        except Exception:\n"
        "            continue\n"
        "\n"
        "def apply_all(root, items_by_name):\n"
        "    for name, items in items_by_name.items():\n"
        "        try:\n"
        "            mat = mset.findMaterial(name)\n"
        "        except Exception:\n"
        "            mat = None\n"
        "        if mat is None:\n"
        "            mat = mset.Material(name)\n"
        "            if root is not None:\n"
        "                mat.assign(root, includeChildren=True)\n"
        "        apply_maps(mat, items)\n"
        "\n"
        "def replace_mesh(path, items_by_name):\n"
        "    saved = None\n"
        "    for obj in list(mset.getAllObjects()):\n"
        "        if protected(obj):\n"
        "            continue\n"
        "        obj_path = getattr(obj, 'path', '') or ''\n"
        "        if obj_path and same_path(obj_path, path):\n"
        "            if saved is None:\n"
        "                saved = (obj.parent, obj.position, obj.rotation, obj.scale)\n"
        "            obj.destroy()\n"
        "    if saved is None:\n"
        "        stem = os.path.splitext(os.path.basename(path))[0]\n"
        "        for obj in list(mset.getAllObjects()):\n"
        "            if protected(obj) or obj.parent is not None:\n"
        "                continue\n"
        "            if obj.name == stem:\n"
        "                saved = (obj.parent, obj.position, obj.rotation, obj.scale)\n"
        "                obj.destroy()\n"
        "                break\n"
        "    root = import_as_reference(path)\n"
        "    mark_reference(root)\n"
        "    if root is not None and saved is not None:\n"
        "        try:\n"
        "            root.parent, root.position, root.rotation, root.scale = saved\n"
        "        except Exception:\n"
        "            pass\n"
        "    apply_all(root, items_by_name)\n"
        "    try:\n"
        "        mset.refreshUI()\n"
        "    except Exception:\n"
        "        pass\n"
        "    return root\n"
        "\n"
        "try:\n"
        "    os.remove(request_path)\n"
        "except OSError:\n"
        "    pass\n"
        "mset.newScene()\n"
        "root = import_as_reference(mesh)\n"
        "mark_reference(root)\n"
        "apply_all(root, assignments)\n"
        "\n"
        "previous_tick = getattr(mset.callbacks, 'onPeriodicUpdate', None)\n"
        "\n"
        "def on_tick():\n"
        "    if callable(previous_tick):\n"
        "        try:\n"
        "            previous_tick()\n"
        "        except Exception:\n"
        "            pass\n"
        "    if not os.path.isfile(request_path):\n"
        "        return\n"
        "    try:\n"
        "        with open(request_path, 'r', encoding='utf-8') as handle:\n"
        "            payload = json.load(handle)\n"
        "        os.remove(request_path)\n"
        "    except Exception:\n"
        "        return\n"
        "    replace_mesh(payload.get('mesh') or mesh, payload.get('assignments') or assignments)\n"
        "\n"
        "mset.callbacks.onPeriodicUpdate = on_tick\n"
        "\n"
        "# Toolbag only keeps a plugin's callbacks alive while one of its windows is\n"
        "# visible, so this window is what lets Update in Marmoset reach this scene.\n"
        "window = mset.UIWindow('Fyr Baker')\n"
        "window.width = 240\n"
        "window.addElement(mset.UILabel('Linked to Blender.'))\n"
        "window.addReturn()\n"
        "window.addElement(mset.UILabel('Update in Marmoset refreshes'))\n"
        "window.addReturn()\n"
        "window.addElement(mset.UILabel('this mesh and its maps.'))\n"
        "window.addReturn()\n"
        "unlink = mset.UIButton('Unlink')\n"
        "unlink.onClick = lambda: mset.shutdownPlugin()\n"
        "window.addElement(unlink)\n",
        encoding="utf-8",
    )
    return script_path


#: ``send_package_to_toolbag`` outcomes. Launch is immediate; Update never starts a second Toolbag.
TOOLBAG_HANDOFF_SENT = "sent"
TOOLBAG_HANDOFF_LAUNCHED = "launched"


def send_package_to_toolbag(
    executable: Path,
    package: HandoffPackage,
    *,
    update_existing: bool = False,
) -> str:
    """Send or replace the staged package in Toolbag.

    Send launches Toolbag with the import script. Update rewrites the request
    file that the already-running script watches, so the open scene replaces
    the mesh in place and refreshes maps instead of importing a second copy.
    Update with no Toolbag open has no scene to preserve, so it launches like
    Send and returns ``TOOLBAG_HANDOFF_LAUNCHED``.
    """
    write_toolbag_import_script(package)
    if update_existing and toolbag_is_running(executable):
        write_toolbag_update_request(package)
        return TOOLBAG_HANDOFF_SENT
    # A fresh scene loads the fixed staged names; earlier Update copies are leftovers.
    remove_toolbag_map_versions(package)
    subprocess.Popen(
        [str(Path(executable)), str(package.root / "open_in_toolbag.py")],
        env=clean_external_environment(),
    )
    return TOOLBAG_HANDOFF_LAUNCHED if update_existing else TOOLBAG_HANDOFF_SENT


def toolbag_command(executable: Path, package: HandoffPackage) -> list[str]:
    return [str(Path(executable)), str(write_toolbag_import_script(package))]


# ---------------------------------------------------------------------------
# Photoshop
#
# One document, every live baked file as its own layer, opened in Photoshop.
# Photoshop reads the bake files itself (PNG, TGA, TIFF, EXR) and writes the
# PSD, so Send to Photoshop does not re-encode pixels and does not copy the
# maps into a second folder. The script, the result note, and the PSD are
# overwritten in place on the next send.
# ---------------------------------------------------------------------------

_PHOTOSHOP_NAME_BAD = re.compile(r'[\\/:*?"<>|\r\n]+')
_PHOTOSHOP_SEND_ACTIVE = False
_UNSET = object()

PHOTOSHOP_HANDOFF_SENT = "sent"
PHOTOSHOP_HANDOFF_LAUNCHING = "launching"
PHOTOSHOP_LAUNCH_POLL_SECONDS = 0.5
PHOTOSHOP_LAUNCH_TIMEOUT_SECONDS = 300.0

_PHOTOSHOP_PROGID_CACHE: dict[str, str] = {}

_PHOTOSHOP_POWERSHELL = """
param(
    [Parameter(Mandatory = $true)][string]$JsxPath,
    [Parameter(Mandatory = $true)][string]$ResultPath,
    [Parameter(Mandatory = $true)][string]$ProgId
)
$ErrorActionPreference = 'Stop'

function Write-Result([bool]$Ok, [string]$Message) {
    if (Test-Path -LiteralPath $ResultPath) { return }
    $payload = @{ ok = $Ok; message = $Message } | ConvertTo-Json -Compress
    Set-Content -LiteralPath $ResultPath -Value $payload -Encoding utf8
}

try {
    $app = New-Object -ComObject $ProgId
    $app.Visible = $true
    [void]$app.DoJavaScriptFile($JsxPath)
    Write-Result $true 'Opened baked maps in Photoshop'
} catch {
    Write-Result $false ([string]$_.Exception.Message)
    exit 1
}
""".strip() + "\n"

# ExtendScript (ES3). Photoshop opens each bake file and stacks it into one
# document, first map on top, one layer group per texture set when there are
# several. The script writes the result JSON itself so the Blender side can
# report success or the Photoshop error without parsing a dialog.
_PHOTOSHOP_JSX = r"""#target photoshop
(function () {
  var previousDialogs = app.displayDialogs;
  var previousRuler = app.preferences.rulerUnits;
  app.displayDialogs = DialogModes.NO;
  app.preferences.rulerUnits = Units.PIXELS;
  var job = __FYR_JOB__;
  var placed = 0;
  var failed = [];
  var master = null;

  function writeResult(ok, message) {
    try {
      var file = new File(job.resultPath);
      file.encoding = "UTF8";
      file.open("w");
      var text = String(message).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r/g, "\\r").replace(/\n/g, "\\n");
      file.write('{"ok":' + (ok ? "true" : "false") + ',"message":"' + text + '"}');
      file.close();
    } catch (ignored) {}
  }

  function errorText(err) {
    if (!err) return "Photoshop could not build the document";
    var message = err.message ? String(err.message) : String(err);
    if (err.line) message += " (line " + err.line + ")";
    return message;
  }

  function px(value) {
    return value.as("px");
  }

  function depthRank(doc) {
    if (doc.bitsPerChannel == BitsPerChannelType.THIRTYTWO) return 32;
    if (doc.bitsPerChannel == BitsPerChannelType.SIXTEEN) return 16;
    return 8;
  }

  function unlockActive(doc) {
    var layer = doc.activeLayer;
    if (layer.isBackgroundLayer) layer.isBackgroundLayer = false;
    return doc.activeLayer;
  }

  function alignLayer(layer) {
    var bounds = layer.bounds;
    var left = bounds[0].as("px");
    var top = bounds[1].as("px");
    if (Math.abs(left) > 0.5 || Math.abs(top) > 0.5) {
      layer.translate(UnitValue(-left, "px"), UnitValue(-top, "px"));
    }
  }

  function closeNamedDocuments() {
    var names = {};
    names[job.documentName] = true;
    names[job.psdFileName] = true;
    names[job.documentName + ".psd"] = true;
    for (var i = app.documents.length - 1; i >= 0; i--) {
      var doc = app.documents[i];
      if (names[doc.name]) doc.close(SaveOptions.DONOTSAVECHANGES);
    }
  }

  function findOpen(path) {
    var wanted = new File(path).fsName.toLowerCase();
    for (var i = 0; i < app.documents.length; i++) {
      try {
        if (app.documents[i].fullName.fsName.toLowerCase() == wanted) return app.documents[i];
      } catch (missingPath) {}
    }
    return null;
  }

  function ensureCanvas(src) {
    var width = Math.max(px(master.width), px(src.width));
    var height = Math.max(px(master.height), px(src.height));
    if (width - px(master.width) > 0.5 || height - px(master.height) > 0.5) {
      master.resizeCanvas(UnitValue(width, "px"), UnitValue(height, "px"), AnchorPosition.TOPLEFT);
    }
  }

  function ensureDepth(src) {
    var need = depthRank(src);
    if (need <= depthRank(master)) return;
    master.bitsPerChannel = (need >= 32) ? BitsPerChannelType.THIRTYTWO : BitsPerChannelType.SIXTEEN;
  }

  function destinationFor(entry, groups) {
    if (!job.useGroups) return master;
    return groups[entry.group];
  }

  function placedLayer(duplicateResult) {
    var layer = master.activeLayer;
    try {
      if (duplicateResult && duplicateResult.typename == "ArtLayer") layer = duplicateResult;
    } catch (ignored) {}
    if (layer.isBackgroundLayer) layer.isBackgroundLayer = false;
    return layer;
  }

  try {
    if (!job.entries || !job.entries.length) throw new Error("No baked maps were available to open");
    closeNamedDocuments();
    var groups = [];
    for (var index = job.entries.length - 1; index >= 0; index--) {
      var entry = job.entries[index];
      var sourceFile = new File(entry.path);
      if (!sourceFile.exists) {
        failed.push(entry.name);
        continue;
      }
      var src = null;
      var openedHere = false;
      var created = null;
      try {
        src = findOpen(entry.path);
        if (src == null) {
          src = app.open(sourceFile);
          openedHere = true;
        }
        if (master == null) {
          app.activeDocument = src;
          created = src.duplicate(job.documentName, false);
          if (openedHere) {
            src.close(SaveOptions.DONOTSAVECHANGES);
            openedHere = false;
          }
          src = null;
          app.activeDocument = created;
          if (created.mode != DocumentMode.RGB) created.changeMode(ChangeMode.RGB);
          var base = unlockActive(created);
          if (job.useGroups) {
            for (var g = job.groupNames.length - 1; g >= 0; g--) {
              var group = created.layerSets.add();
              group.name = job.groupNames[g];
              groups[g] = group;
            }
            base.move(groups[entry.group], ElementPlacement.PLACEATBEGINNING);
          }
          base.name = entry.name;
          alignLayer(base);
          master = created;
          created = null;
          placed++;
        } else {
          ensureDepth(src);
          ensureCanvas(src);
          app.activeDocument = src;
          var duplicated = src.activeLayer.duplicate(destinationFor(entry, groups), ElementPlacement.PLACEATBEGINNING);
          if (openedHere) {
            src.close(SaveOptions.DONOTSAVECHANGES);
            openedHere = false;
          }
          src = null;
          app.activeDocument = master;
          var layer = placedLayer(duplicated);
          layer.name = entry.name;
          alignLayer(layer);
          placed++;
        }
      } catch (placeError) {
        if (openedHere && src) {
          try { src.close(SaveOptions.DONOTSAVECHANGES); } catch (closeError) {}
        }
        if (created) {
          try { created.close(SaveOptions.DONOTSAVECHANGES); } catch (closeCreated) {}
        }
        failed.push(entry.name);
      }
    }
    if (master == null || placed < 1) {
      throw new Error(failed.length ? ("Could not open " + failed.join(", ")) : "No baked maps could be opened");
    }
    app.activeDocument = master;
    if (job.useGroups) {
      for (var setIndex = master.layerSets.length - 1; setIndex >= 0; setIndex--) {
        var layerSet = master.layerSets[setIndex];
        if (layerSet.layers.length == 0) layerSet.remove();
      }
    }
    var options = new PhotoshopSaveOptions();
    options.layers = true;
    options.embedColorProfile = true;
    options.alphaChannels = true;
    master.saveAs(new File(job.psdPath), options, false);
    app.bringToFront();
    var message = "Opened " + placed + " baked map" + (placed == 1 ? "" : "s") + " in Photoshop";
    if (failed.length) message += ". Skipped " + failed.join(", ");
    writeResult(true, message);
  } catch (err) {
    writeResult(false, errorText(err));
  } finally {
    app.displayDialogs = previousDialogs;
    app.preferences.rulerUnits = previousRuler;
  }
})();
"""


@dataclass(frozen=True)
class PhotoshopLayer:
    name: str
    source_path: Path
    texture_set: str


@dataclass(frozen=True)
class PhotoshopDocument:
    name: str
    psd_path: Path
    layers: tuple[PhotoshopLayer, ...]


def photoshop_document_name(value: str) -> str:
    cleaned = _PHOTOSHOP_NAME_BAD.sub(" ", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return (cleaned or "Bake")[:120]


def _unique_photoshop_name(label: str, used: set[str]) -> str:
    candidate = label.strip() or "Map"
    if candidate.casefold() not in used:
        used.add(candidate.casefold())
        return candidate
    index = 2
    while f"{candidate} {index}".casefold() in used:
        index += 1
    unique = f"{candidate} {index}"
    used.add(unique.casefold())
    return unique


def photoshop_layer_name(map_type: str, output_suffix: str, *, include_variant: bool, udim_tile: int) -> str:
    from . import constants

    base = constants.MAP_FILE_LABELS.get(str(map_type or "").strip().upper()) or sanitize_name(map_type, "Map")
    suffix = str(output_suffix or "").strip()
    if include_variant and suffix and suffix.casefold() != base.casefold():
        label = f"{base} ({suffix})"
    else:
        label = base
    if udim_tile:
        label = f"{label}.{udim_tile}"
    return label[:120]


def build_photoshop_document(
    outputs: Iterable[object],
    group_texture_sets: Mapping[str, str],
    *,
    document_name: str,
    psd_path: Path,
) -> PhotoshopDocument:
    """Layer plan for one PSD. Raises when no live bake file can be stacked."""
    used: dict[str, set[str]] = {}
    layers: list[PhotoshopLayer] = []
    for item in live_map_files(outputs, group_texture_sets):
        label = photoshop_layer_name(
            item.map_type,
            item.output_suffix,
            include_variant=item.include_variant,
            udim_tile=item.udim_tile,
        )
        bucket = used.setdefault(item.texture_set.casefold(), set())
        layers.append(PhotoshopLayer(_unique_photoshop_name(label, bucket), item.source_path.resolve(), item.texture_set))
    if not layers:
        raise RuntimeError("No baked map files are available to send")
    return PhotoshopDocument(photoshop_document_name(document_name), Path(psd_path), tuple(layers))


def photoshop_script_path(psd_path: Path) -> Path:
    return Path(psd_path).with_name("open_in_photoshop.jsx")


def photoshop_result_path(psd_path: Path) -> Path:
    return Path(psd_path).with_name("open_in_photoshop.result.json")


def photoshop_script_job(document: PhotoshopDocument, result_path: Path) -> dict:
    group_names: list[str] = []
    index_by_set: dict[str, int] = {}
    entries: list[dict] = []
    for layer in document.layers:
        key = layer.texture_set.casefold()
        if key not in index_by_set:
            index_by_set[key] = len(group_names)
            group_names.append(layer.texture_set)
        entries.append(
            {
                "group": index_by_set[key],
                "name": layer.name,
                "path": layer.source_path.resolve().as_posix(),
            }
        )
    return {
        "documentName": document.name,
        "psdFileName": Path(document.psd_path).name,
        "psdPath": Path(document.psd_path).resolve().as_posix(),
        "resultPath": Path(result_path).resolve().as_posix(),
        "useGroups": len(group_names) > 1,
        "groupNames": group_names,
        "entries": entries,
    }


def render_photoshop_jsx(job: Mapping[str, object]) -> str:
    payload = json.dumps(job, ensure_ascii=False)
    if "__FYR_JOB__" not in _PHOTOSHOP_JSX:
        raise RuntimeError("Photoshop script template is missing its payload slot")
    return _PHOTOSHOP_JSX.replace("__FYR_JOB__", payload, 1)


def write_photoshop_script(document: PhotoshopDocument, result_path: Path) -> Path:
    script_path = photoshop_script_path(document.psd_path)
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("\ufeff" + render_photoshop_jsx(photoshop_script_job(document, result_path)), encoding="utf-8")
    return script_path


def macos_photoshop_bundle(executable: Path) -> Path | None:
    for parent in Path(executable).parents:
        if parent.suffix.casefold() == ".app":
            return parent
    return None


def _photoshop_server_matches(command: str, executable: Path) -> bool:
    text = str(command or "").strip()
    if not text:
        return False
    if text.startswith('"'):
        end = text.find('"', 1)
        text = text[1:end] if end > 1 else text.strip('"')
    else:
        marker = "photoshop.exe"
        at = text.casefold().find(marker)
        if at >= 0:
            text = text[: at + len(marker)]
    return os.path.normcase(os.path.normpath(text)) == os.path.normcase(os.path.normpath(str(executable)))


def _photoshop_local_server(progid: str) -> str:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\CLSID") as key:
            clsid = str(winreg.QueryValueEx(key, "")[0] or "").strip()
    except OSError:
        return ""
    if not clsid:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32") as key:
            return str(winreg.QueryValueEx(key, "")[0] or "")
    except OSError:
        return ""


def _photoshop_registered_progids() -> list[str]:
    """Newest registration first. Reads CurVer and Adobe's install keys, not all of HKCR."""
    import winreg

    names: list[str] = []
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Photoshop.Application\CurVer") as key:
            current = str(winreg.QueryValueEx(key, "")[0] or "").strip()
    except OSError:
        current = ""
    if current:
        names.append(current)
    names.append("Photoshop.Application")
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in (r"SOFTWARE\Adobe\Photoshop", r"SOFTWARE\WOW6432Node\Adobe\Photoshop"):
            try:
                with winreg.OpenKey(hive, subkey) as root:
                    count = winreg.QueryInfoKey(root)[0]
                    for index in range(count):
                        try:
                            version = winreg.EnumKey(root, index)
                        except OSError:
                            continue
                        major = version.split(".", 1)[0]
                        if major.isdigit():
                            names.append(f"Photoshop.Application.{major}")
            except OSError:
                continue
    ordered: list[str] = []
    seen: set[str] = set()
    for name in names:
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            ordered.append(name)
    return ordered


def photoshop_com_progid(executable: Path) -> str:
    """ProgID whose LocalServer32 is this executable, or the version-independent one."""
    if not sys.platform.startswith("win"):
        return ""
    try:
        target = os.path.normcase(os.path.normpath(str(Path(executable))))
    except (OSError, ValueError):
        return "Photoshop.Application"
    cached = _PHOTOSHOP_PROGID_CACHE.get(target)
    if cached:
        return cached
    progid = "Photoshop.Application"
    try:
        for name in _photoshop_registered_progids():
            server = _photoshop_local_server(name)
            if server and _photoshop_server_matches(server, Path(executable)):
                progid = name
                break
    except (ImportError, OSError):
        progid = "Photoshop.Application"
    _PHOTOSHOP_PROGID_CACHE[target] = progid
    return progid


def _photoshop_apple_script(bundle: Path, jsx_path: Path) -> str:
    app = str(bundle).replace("\\", "\\\\").replace('"', '\\"')
    jsx = str(jsx_path).replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'tell application "{app}"\n'
        f"  activate\n"
        f"  with timeout of 600 seconds\n"
        f'    do javascript file (POSIX file "{jsx}")\n'
        f"  end timeout\n"
        f"end tell\n"
    )


def photoshop_host_command(
    executable: Path,
    jsx_path: Path,
    result_path: Path,
    *,
    progid: str = "Photoshop.Application",
) -> list[str]:
    executable = Path(executable)
    jsx_path = Path(jsx_path)
    result_path = Path(result_path)
    if sys.platform.startswith("win"):
        launcher = jsx_path.with_name("open_in_photoshop.ps1")
        launcher.write_text(_PHOTOSHOP_POWERSHELL, encoding="utf-8")
        return [
            "powershell.exe",
            "-NoProfile",
            "-Sta",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(launcher),
            str(jsx_path),
            str(result_path),
            progid or "Photoshop.Application",
        ]
    if sys.platform == "darwin":
        bundle = macos_photoshop_bundle(executable)
        if bundle is None:
            raise RuntimeError("The Photoshop path is not an application bundle")
        return ["osascript", "-e", _photoshop_apple_script(bundle, jsx_path)]
    return [str(executable), str(jsx_path)]


def _read_photoshop_result(path: Path) -> dict | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(payload, dict) or "ok" not in payload:
        return None
    return payload


def photoshop_launch_poll_callback(
    process,
    result_path: Path,
    *,
    deadline: float,
    poll_interval: float = PHOTOSHOP_LAUNCH_POLL_SECONDS,
    on_status=None,
    on_finished=None,
    now_fn=time.monotonic,
):
    """Poll until Photoshop writes a result, the launcher exits, or the deadline passes."""
    result_path = Path(result_path)

    def _report(message: str, ok: bool) -> None:
        if callable(on_status):
            try:
                on_status(message, ok)
            except Exception:
                pass

    def _finish() -> None:
        if callable(on_finished):
            try:
                on_finished()
            except Exception:
                pass

    def _poll():
        payload = _read_photoshop_result(result_path)
        if payload is not None:
            message = str(payload.get("message") or "").strip()
            ok = bool(payload.get("ok"))
            if not message:
                message = "Opened baked maps in Photoshop" if ok else "Photoshop handoff failed"
            _report(message, ok)
            _finish()
            return None
        code = None
        if process is not None:
            try:
                code = process.poll()
            except Exception:
                code = None
        if code is not None:
            _report("Photoshop closed before the document was ready", False)
            _finish()
            return None
        if now_fn() >= deadline:
            _report(
                "Photoshop did not finish opening the baked maps. If its home screen is open, dismiss it and send again",
                False,
            )
            _finish()
            return None
        return poll_interval

    return _poll


def send_document_to_photoshop(
    executable: Path,
    document: PhotoshopDocument,
    *,
    timeout_seconds: float = PHOTOSHOP_LAUNCH_TIMEOUT_SECONDS,
    popen_fn=None,
    register_timer=_UNSET,
    on_status=None,
    now_fn=time.monotonic,
    sleep_fn=time.sleep,
    progid_fn=None,
) -> str:
    """Open ``document`` in Photoshop. Returns immediately while Photoshop starts.

    The bake files stay where they are. Photoshop stacks them and saves one PSD.
    ``on_status(message, ok)`` receives the outcome once the script finishes.
    """
    global _PHOTOSHOP_SEND_ACTIVE
    if _PHOTOSHOP_SEND_ACTIVE:
        raise RuntimeError("Photoshop is already opening the baked maps")
    if not document.layers:
        raise RuntimeError("No baked map files are available to send")

    _PHOTOSHOP_SEND_ACTIVE = True
    finished = False

    def _release() -> None:
        nonlocal finished
        global _PHOTOSHOP_SEND_ACTIVE
        if finished:
            return
        finished = True
        _PHOTOSHOP_SEND_ACTIVE = False

    try:
        result_path = photoshop_result_path(document.psd_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        if result_path.exists():
            result_path.unlink()
        jsx_path = write_photoshop_script(document, result_path)
        progid = progid_fn(executable) if callable(progid_fn) else photoshop_com_progid(executable)
        command = photoshop_host_command(executable, jsx_path, result_path, progid=progid or "Photoshop.Application")
        launch = popen_fn if callable(popen_fn) else subprocess.Popen
        popen_kwargs = {
            "env": clean_external_environment(),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform.startswith("win"):
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = launch(command, **popen_kwargs)
        poll = photoshop_launch_poll_callback(
            process,
            result_path,
            deadline=now_fn() + max(0.0, float(timeout_seconds)),
            on_status=on_status,
            on_finished=_release,
            now_fn=now_fn,
        )
        if register_timer is _UNSET:
            register = _default_timer_register()
        elif callable(register_timer):
            register = register_timer
        else:
            register = None
        if register is None:
            while True:
                delay = poll()
                if delay is None:
                    return PHOTOSHOP_HANDOFF_SENT
                sleep_fn(delay)
        register(poll, first_interval=PHOTOSHOP_LAUNCH_POLL_SECONDS)
        return PHOTOSHOP_HANDOFF_LAUNCHING
    except Exception:
        _release()
        raise


def _object_key(value: str) -> str:
    # Blender's OBJ exporter may replace spaces/punctuation with underscores.
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())
