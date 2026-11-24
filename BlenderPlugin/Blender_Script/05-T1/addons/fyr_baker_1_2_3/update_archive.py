from __future__ import annotations

import zipfile
import re
from pathlib import Path
from typing import Callable


_LEADING_DIGITS = re.compile(r"\d+")


def parse_version(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    parts: list[int] = []
    for part in value.strip().split("."):
        # "57-hotfix" / "3rc1" still carry an ordering number in front; a part
        # with no leading digits ends the tuple. Without this a feed version of
        # 0.1.57-hotfix parsed as (0, 1) and never counted as newer than 0.1.56.
        digits = _LEADING_DIGITS.match(part)
        if digits is None:
            break
        parts.append(int(digits.group(0)))
    return tuple(parts)


def extension_manifest_version(addon_dir: Path) -> tuple[int, ...]:
    manifest_path = addon_dir / "blender_manifest.toml"
    if not manifest_path.is_file():
        return ()

    try:
        import tomllib

        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return ()

    if manifest.get("id") != "fyr_baker":
        return ()
    return parse_version(manifest.get("version"))


def extension_manifest_blender_range(manifest: dict) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """``(blender_version_min, blender_version_max)`` from a parsed manifest.

    Either bound is ``()`` when the manifest does not declare it. Blender reads
    ``blender_version_max`` as EXCLUSIVE, so callers compare with ``<`` there.
    """
    return (
        parse_version(manifest.get("blender_version_min")),
        parse_version(manifest.get("blender_version_max")),
    )


def archive_blender_version_range(zip_path: Path) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The Blender range the archive's own manifest declares, ``((), ())`` if unreadable.

    This is the bound Blender's installer enforces, read from the file it will
    enforce it against. The update feed carries the same numbers, but a feed row
    is typed by hand at publish time; the manifest inside the zip is what
    actually decides whether the install lands.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            names = {name.replace("\\", "/").lstrip("./"): name for name in archive.namelist()}
            member = names.get("blender_manifest.toml")
            if member is None:
                return (), ()
            text = archive.read(member).decode("utf-8", errors="replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        return (), ()

    try:
        import tomllib

        manifest = tomllib.loads(text)
    except Exception:
        return (), ()
    if manifest.get("id") != "fyr_baker":
        return (), ()
    return extension_manifest_blender_range(manifest)


def is_fyr_baker_archive(zip_path: Path) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            names = {name.replace("\\", "/").lstrip("./") for name in archive.namelist()}

            # Blender Extensions place their files at the archive root. Keep
            # accepting the former one-folder layout so transition builds can
            # still be inspected or installed manually.
            if "__init__.py" in names and "blender_manifest.toml" in names:
                manifest = archive.read("blender_manifest.toml").decode("utf-8", errors="replace")
                init_source = archive.read("__init__.py").decode("utf-8", errors="replace")
                return 'id = "fyr_baker"' in manifest and _looks_like_fyr_baker(init_source)

            classic_init = next(
                (
                    name
                    for name in names
                    if name.endswith("/__init__.py") and name.count("/") == 1
                ),
                None,
            )
            if classic_init is None:
                return False
            init_source = archive.read(classic_init).decode("utf-8", errors="replace")
            return _looks_like_fyr_baker(init_source)
    except (OSError, KeyError, zipfile.BadZipFile):
        return False


def install_extension_archive(
    zip_path: Path,
    install_operator: Callable[..., set[str]],
    repo_module: str = "user_default",
) -> bool:
    """Hand the archive to Blender's extension installer.

    A ``True`` here means only "the operator ran without raising". It is NOT
    proof the package was replaced: Blender's non-modal ``execute()`` path
    returns ``{'FINISHED'}`` unconditionally, and the extension CLI it drives
    exits 0 even when every archive was rejected (a version/platform filter
    miss, a locked directory, a full disk). The caller must confirm the install
    by reading the installed manifest back off disk - see
    ``updater.installed_extension_version``.

    ``repo_module`` must be the repository the running package actually lives
    in. Hard-coding ``user_default`` installs a second copy elsewhere when it
    does not, which reads as a silent no-op: the old copy keeps loading and the
    update popup returns on every launch.
    """
    try:
        result = install_operator(
            filepath=str(zip_path),
            repo=repo_module,
            overwrite=True,
            enable_on_install=True,
        )
    except Exception:
        return False
    return "FINISHED" in result


def _looks_like_fyr_baker(init_source: str) -> bool:
    return "bl_info" in init_source and (
        "Fyr Baker" in init_source or "fyr_baker" in init_source.lower()
    )
