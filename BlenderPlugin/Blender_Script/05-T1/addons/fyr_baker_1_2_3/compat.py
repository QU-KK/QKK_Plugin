"""Behaviour differences between the Blender versions Fyr Baker supports (4.2 LTS and newer).

Keep every version branch in this module so the rest of the add-on calls one name and
reads the same on every Blender. Each shim states what it was measured against.

EXR colour tag (measured on Blender 4.5.2 LTS and 5.1.1, 2026-11-18):

* Both versions encode a float image tagged ``sRGB`` the same way on ``Image.save()``
  to OPEN_EXR (0.5 is stored as 0.735), and both decode it the same way once the
  datablock's colorspace is set.
* Blender 5.x also writes ``colorInteropID = srgb_rec709_display`` into the header, and
  reads it back, so the file self-describes as display-encoded. Blender 4.5 writes no
  tag, so the same pixels read as linear in any tag-aware app (Blender 5.x included):
  a 4.5 Albedo EXR opened there was too bright.

:func:`tag_srgb_exr` adds the tag 5.x would have written, so a 4.5 bake produces the
same file a 5.x bake does. It never runs on 5.x.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The header value Blender 5.x writes for an sRGB image saved to EXR.
EXR_SRGB_INTEROP_ID = "srgb_rec709_display"

#: Colorspace names whose EXR files Blender 5.x tags as display-encoded sRGB.
_SRGB_COLORSPACES = frozenset({"sRGB"})


def blender_version() -> tuple[int, ...]:
    try:
        import bpy  # type: ignore
    except ImportError:  # pragma: no cover - unit tests outside Blender
        return ()
    return tuple(getattr(getattr(bpy, "app", None), "version", ()) or ())


def blender_writes_exr_colorspace(version: tuple[int, ...] | None = None) -> bool:
    """True when Blender itself writes the EXR colour tag (5.0 and newer)."""
    current = tuple(version if version is not None else blender_version())
    return not current or current >= (5, 0, 0)


def blend_relative_path_options(version: tuple[int, ...] | None = None) -> set[str]:
    """``options=`` for a path StringProperty whose value may start with ``//``.

    Blender 4.5 added ``PATH_SUPPORTS_BLEND_RELATIVE`` and from then on flags a
    ``//`` path on a property without it. Blender 4.2 accepts ``//`` paths as they
    are and rejects the unknown option, failing registration of the whole class.
    """
    current = tuple(version if version is not None else blender_version())
    if current and current < (4, 5, 0):
        return set()
    return {"PATH_SUPPORTS_BLEND_RELATIVE"}


def tag_srgb_exr(path, colorspace_name: str, *, version: tuple[int, ...] | None = None) -> bool:
    """Give an sRGB EXR written by Blender 4.x the colour tag Blender 5.x writes.

    Returns True when the file was rewritten. A no-op on Blender 5.x, for non-EXR
    files, for data (non-sRGB) images, and for a file that already carries a tag.
    The rewrite keeps pixel type, channels and compression, and replaces the file
    atomically.
    """
    if blender_writes_exr_colorspace(version):
        return False
    if str(colorspace_name or "") not in _SRGB_COLORSPACES:
        return False
    path = Path(path)
    if path.suffix.lower() != ".exr" or not path.is_file():
        return False
    try:
        import OpenImageIO as oiio  # type: ignore  # noqa: PLC0415 - bundled with Blender 4.5+
    except ImportError:
        return False

    source = oiio.ImageInput.open(str(path))
    if source is None:
        return False
    try:
        spec = source.spec()
        if spec.get_string_attribute("colorInteropID"):
            return False
        pixels = source.read_image(0, 0, 0, spec.nchannels, spec.format)
    finally:
        source.close()
    if pixels is None:
        return False

    spec.attribute("colorInteropID", EXR_SRGB_INTEROP_ID)
    spec.attribute("oiio:ColorSpace", EXR_SRGB_INTEROP_ID)
    temporary = path.with_name(path.name + ".fyrtag.exr")
    out = oiio.ImageOutput.create(str(temporary))
    if out is None:
        return False
    try:
        if not out.open(str(temporary), spec) or not out.write_image(pixels):
            raise OSError(out.geterror() or f"could not write {temporary}")
    except Exception:
        out.close()
        try:
            temporary.unlink()
        except OSError:
            pass
        return False
    out.close()
    os.replace(str(temporary), str(path))
    return True


def tag_saved_image(image, path, *, version: tuple[int, ...] | None = None) -> bool:
    """:func:`tag_srgb_exr` for the file a Blender image datablock was just saved to."""
    settings = getattr(image, "colorspace_settings", None)
    return tag_srgb_exr(path, str(getattr(settings, "name", "") or ""), version=version)
