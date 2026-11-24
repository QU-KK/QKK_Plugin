"""Output-template store for the texture export dialog.

Templates are JSON files on disk, not .blend data, because they are
cross-project assets (see ``docs/archive/TEXTURE_EXPORT_DIALOG_PLAN.md`` D1/D2). Two
tiers, same discipline as ``preset_store.py``:

* built-ins shipped with the addon in ``<repo>/presets/output_templates`` --
  read-only in the UI;
* user templates in ``bpy.utils.extension_path_user(..., "output_templates")``
  so they survive addon updates.

The .blend stores only the selected template *name*.

Channel states (schema note)
----------------------------
A channel slot has four states, and all four are legal:

* **absent / ``null``** -- the output has no such channel at all. It contributes
  zeros and, for ``A``, decides RGB vs RGBA;
* **present with ``"source": ""``** -- the slot exists in this output's shape but
  no map is assigned to it *yet*. This is what the editor writes while an artist
  is building an output, and it packs exactly like an unused slot (zeros);
* **present with a real map identifier** -- assigned;
* **present with ``"source": "CONSTANT"``** -- the slot is filled with a flat
  value instead of a map (:data:`CONSTANT_SOURCE`). The value lives in the
  entry's ``"constant"`` key, a float in ``[0.0, 1.0]`` defaulting to ``0.0``,
  and ``"invert"`` means ``1.0 - value`` exactly as it does everywhere else.
  ``CONSTANT`` is a *source sentinel*, never a map type: ``MAP_TYPE_ITEMS`` is
  append-only and knows nothing about it. A constant slot has no component to
  read, so its ``"channel"`` is accepted (the editor writes one on every entry)
  and ignored. ``"constant"`` on an entry whose source is anything else is an
  **error** rather than a silent no-op.

Block compression (schema note)
-------------------------------
An output whose ``format`` is ``DDS`` may carry ``"dds_compression": "<BCn>"``,
one of :data:`constants.EXPORT_DDS_COMPRESSION_ITEMS`. It is a **per-output**
choice because a texture set has no single right answer: a tangent-space normal
map wants BC5, a single-channel mask wants BC4, and colour wants BC7 or BC1.
Absent means "use whatever the Export Textures dialog's DDS Compression control
is set to", so a template written before this key keeps behaving exactly as it
did. ``dds_compression`` on a non-DDS output is an **error** rather than a silent
no-op, for the same reason ``constant`` on a map-backed channel is.

Occurrence ordinals (schema note)
---------------------------------
A project may hold several bakes of one map type. A map-backed channel picks one
of them with an optional ``"variant": <int >= 0>`` -- a 0-based occurrence among
same-type bakes in map-stack order (``docs/MAP_VARIANTS_PLAN.md``). **Absent
means 0**, i.e. "the first bake of this type", which is what every template
written so far means and what it must keep meaning; a template that sets no
variant therefore behaves identically in a project with one AO and in a project
with three. A negative or non-integer value is an error, and so is ``"variant"``
on a ``CONSTANT`` channel: a constant reads no bake, so there is no occurrence
to pick. ``export_pack.source_key`` turns ``(type, ordinal)`` into the composite
key the packer looks up, and gives occurrence 0 the bare map type so nothing
written before ordinals existed changes shape.

Consequently an output may have zero assigned channels, and a template may have
an empty ``outputs`` list: both are in-progress states the editor must be able to
write to disk. Nothing downstream may treat them as errors -- the export dialog
skips an output with nothing assigned instead of failing the export. An output
whose only filled slots are constants is *not* in progress: it is fully
determined and writes a file.

Everything except :func:`user_template_dir` is import-safe outside Blender, and
``user_template_dir`` itself is a module-level function precisely so tests can
monkeypatch it to a temp directory.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import constants

try:  # pragma: no cover - exercised only inside Blender
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - exercised in unit tests outside Blender
    bpy = None


TEMPLATE_SCHEMA = "master_baker.output_template.v1"

# Repo layout, matching preset_store.PRESET_DIR: <repo>/presets/output_templates.
BUILTIN_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "presets" / "output_templates"
# scripts/package_extension.py copies only addon/ into the shipped zip, so an
# addon-local copy is checked first: whichever layout packaging settles on, the
# store finds the built-ins.
BUILTIN_TEMPLATE_DIR_PACKAGED = Path(__file__).resolve().parent / "presets" / "output_templates"

USER_TEMPLATE_SUBDIR = "output_templates"

DEFAULT_TEMPLATE_NAME = "Mesh Maps (raw)"

CHANNEL_SLOTS: tuple[str, ...] = ("R", "G", "B", "A")
CHANNEL_SOURCE_CHANNELS: tuple[str, ...] = ("R", "G", "B", "A", "GRAY")

# --- constant channels (schema note above) ----------------------------------
#: ``source`` sentinel for a slot filled with a flat value. NOT a map type --
#: never add it to ``MAP_TYPE_ITEMS``. ``export_pack`` mirrors this identifier.
CONSTANT_SOURCE = "CONSTANT"
#: Inclusive bounds of a constant's value.
CONSTANT_MIN = 0.0
CONSTANT_MAX = 1.0
#: The three one-click presets the editor offers. Import these; do not retype.
CONSTANT_BLACK = 0.0
CONSTANT_GRAY = 0.5
CONSTANT_WHITE = 1.0
CONSTANT_PRESETS: tuple[tuple[str, float], ...] = (
    ("BLACK", CONSTANT_BLACK),
    ("GRAY", CONSTANT_GRAY),
    ("WHITE", CONSTANT_WHITE),
)
#: Value a constant entry takes when it carries no ``"constant"`` key.
CONSTANT_DEFAULT = CONSTANT_BLACK


#: Compression identifiers a DDS output may name. Derived from the enum the
#: dialog offers so the two cannot drift.
DDS_COMPRESSIONS: tuple[str, ...] = tuple(
    str(item[0]) for item in constants.EXPORT_DDS_COMPRESSION_ITEMS
)


def output_dds_compression(data, default: str = constants.EXPORT_DDS_BC7) -> str:
    """The BCn an output asks for, or ``default`` when it names none.

    Returns ``default`` for a non-DDS output too, so a caller can read this
    unconditionally.
    """
    if not isinstance(data, dict):
        return default
    if str(data.get("format") or "").strip().upper() != constants.IMAGE_FORMAT_DDS:
        return default
    raw = data.get("dds_compression")
    if not isinstance(raw, str):
        return default
    value = raw.strip().upper()
    return value if value in DDS_COMPRESSIONS else default


def is_constant_source(source) -> bool:
    """True when a channel entry's ``source`` names the constant sentinel."""
    return isinstance(source, str) and source.strip().upper() == CONSTANT_SOURCE


def channel_constant_value(data) -> float:
    """The value a validated constant channel entry carries (``0.0`` by default).

    Applies ``invert`` (``1.0 - value``), so this is the number that actually
    lands in the packed texel. Returns :data:`CONSTANT_DEFAULT` for anything that
    is not a constant entry, so UI code can call it unconditionally.
    """
    if not isinstance(data, dict) or not is_constant_source(data.get("source")):
        return CONSTANT_DEFAULT
    raw = data.get("constant", CONSTANT_DEFAULT)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return CONSTANT_DEFAULT
    value = min(max(float(raw), CONSTANT_MIN), CONSTANT_MAX)
    if data.get("invert") is True:
        value = 1.0 - value
    return value

# --- occurrence ordinals (docs/MAP_VARIANTS_PLAN.md) -------------------------
#: Occurrence a channel addresses when it carries no ``"variant"`` key: the
#: **first** bake of that map type, in every project, however many extras that
#: project happens to hold. A shipped template therefore behaves identically
#: everywhere and ordinals stay opt-in. ``export_pack.source_key`` mirrors this.
DEFAULT_VARIANT = 0


def channel_variant(data) -> int:
    """The 0-based occurrence a validated channel entry addresses.

    :data:`DEFAULT_VARIANT` for anything that is not a map-backed entry carrying
    a legal ordinal, so UI code can call it unconditionally -- a constant reads
    no bake and therefore never has one.
    """
    if not isinstance(data, dict) or is_constant_source(data.get("source")):
        return DEFAULT_VARIANT
    raw = data.get("variant", DEFAULT_VARIANT)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return DEFAULT_VARIANT
    return int(raw)


COLOR_SPACE_SRGB = "SRGB"
COLOR_SPACE_LINEAR = "LINEAR"
COLOR_SPACES: tuple[str, ...] = (COLOR_SPACE_SRGB, COLOR_SPACE_LINEAR)

# 32 is accepted for float EXR only; the project-wide bit-depth enum
# (constants.BIT_DEPTH_ITEMS) still offers just 8/16.
BIT_DEPTHS: tuple[int, ...] = (8, 16, 32)

_NON_TOKEN = re.compile(r"[^A-Za-z0-9_.-]+")
_MULTI_UNDERSCORE = re.compile(r"_+")


class TemplateError(Exception):
    """A template file is unreadable, invalid, or would collide with another."""


@dataclass(frozen=True, slots=True)
class TemplateInfo:
    name: str
    path: Path
    builtin: bool


def valid_source_identifiers() -> frozenset[str]:
    """Map identifiers a channel may name as its source.

    ``MAP_TYPE_ITEMS`` is append-only, so this is derived from it rather than
    hardcoded, plus the ``MATERIAL_*`` channel sub-types that are real output
    identifiers (``MAP_FILE_LABELS`` names them) without being their own rows in
    the map-type enum.
    """
    identifiers = {str(item[0]) for item in constants.MAP_TYPE_ITEMS}
    identifiers.update(
        {
            constants.MAP_MATERIAL_ALBEDO,
            constants.MAP_MATERIAL_ROUGHNESS,
            constants.MAP_MATERIAL_METALNESS,
            constants.MAP_MATERIAL_EMISSION,
            constants.MAP_MATERIAL_OPACITY,
            constants.MAP_MATERIAL_SPECULAR,
            constants.MAP_MATERIAL_TRANSMISSION,
            constants.MAP_MATERIAL_NORMAL,
        }
    )
    identifiers.update({constants.MAP_PRINCIPAL_CURVATURE, constants.MAP_CURVATURE_DIRECTION})
    # A Normal row whose Output is Derivative writes its own file under this name.
    identifiers.add(constants.MAP_DERIVATIVE)
    return frozenset(identifiers)


def valid_image_formats() -> frozenset[str]:
    # Templates may declare DDS; bake project format may not.
    return frozenset(str(item[0]) for item in constants.EXPORT_TEMPLATE_IMAGE_FORMAT_ITEMS)


def sanitize_template_name(value: str) -> str:
    cleaned = _NON_TOKEN.sub("_", (value or "").strip())
    cleaned = _MULTI_UNDERSCORE.sub("_", cleaned).strip("._-")
    return cleaned or "OutputTemplate"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_channel(slot: str, data, index: int, sources: frozenset[str], errors: list[str]) -> bool:
    """Validate one channel slot; ``True`` when the slot *exists* in this output.

    An existing slot may be unassigned (``"source": ""``) or constant
    (``"source": "CONSTANT"``) -- see the module docstring. Only a non-string
    source, or a non-empty identifier this build does not know, is an error;
    ``CONSTANT`` is always known even though it is not a map type.
    """
    where = f"output {index} channel {slot}"
    if data is None:
        return False
    if not isinstance(data, dict):
        errors.append(f"{where}: must be an object or null")
        return False

    source = data.get("source")
    constant_source = is_constant_source(source)
    if not isinstance(source, str):
        errors.append(
            f"{where}: 'source' must be a map identifier, '{CONSTANT_SOURCE}', or \"\" when unassigned"
        )
    elif source.strip() and not constant_source and source not in sources:
        errors.append(f"{where}: unknown source map '{source}'")

    # A constant fills the slot outright, so it has no component to read. The
    # editor writes 'channel' on every entry, so one is tolerated (and still has
    # to be a legal letter) rather than rejected -- it is simply ignored.
    channel = data.get("channel", "GRAY")
    if not isinstance(channel, str) or channel.upper() not in CHANNEL_SOURCE_CHANNELS:
        errors.append(f"{where}: 'channel' must be one of {', '.join(CHANNEL_SOURCE_CHANNELS)}")

    invert = data.get("invert", False)
    if not isinstance(invert, bool):
        errors.append(f"{where}: 'invert' must be true or false")

    if "constant" in data:
        if not constant_source:
            # Not a warning: a 'constant' on a map-backed slot would silently do
            # nothing, which is exactly the accident this key exists to prevent.
            errors.append(f"{where}: 'constant' is only valid when 'source' is '{CONSTANT_SOURCE}'")
        else:
            value = data["constant"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(
                    f"{where}: 'constant' must be a number between {CONSTANT_MIN} and {CONSTANT_MAX}"
                )
            elif not CONSTANT_MIN <= float(value) <= CONSTANT_MAX:
                errors.append(
                    f"{where}: 'constant' {value} is outside the {CONSTANT_MIN}-{CONSTANT_MAX} range"
                )

    if "variant" in data:
        if constant_source:
            # A constant reads no bake, so there is no occurrence to pick.
            errors.append(
                f"{where}: 'variant' is not valid on a '{CONSTANT_SOURCE}' channel; a constant reads no bake"
            )
        else:
            value = data["variant"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                errors.append(
                    f"{where}: 'variant' must be an integer >= 0 "
                    "(the 0-based occurrence among same-type bakes, in map stack order)"
                )

    unknown = sorted(set(data) - {"source", "channel", "invert", "constant", "variant"})
    if unknown:
        errors.append(f"{where}: unknown keys {', '.join(unknown)}")
    return True


def _filename_escapes_output_folder(filename: str) -> bool:
    """Whether this filename template could write outside the artist's export folder.

    Tokens expand to sanitized names, so what matters is the literal path shape the
    template author wrote: an absolute or drive/UNC-qualified path, or any ``..``
    segment. Checked on BOTH separators, because a template written on one platform is
    imported on the other and ``os.path`` only understands the local one.
    """
    text = str(filename or "").strip()
    if not text:
        return False
    normalized = text.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        return True
    # "C:", "C:/", "C:name" - a drive-qualified path makes os.path.join drop the folder.
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        return True
    return any(segment == ".." for segment in normalized.split("/"))


def _validate_output(data, index: int, sources: frozenset[str], formats: frozenset[str], errors: list[str]) -> tuple | None:
    """Validate one output; return its identity key, or ``None`` when unusable.

    The identity key is ``(filename template, first source label, occurrence)``,
    where the label and the occurrence both come from the **first assigned
    map-backed slot**.

    The filename template alone is not enough: every row of a one-file-per-map
    template shares one filename and is told apart only by its first source.
    Two rows naming different sources that happen to share a file label
    (OPACITY and MATERIAL_OPACITY are both "Opacity") are therefore caught here
    rather than silently overwriting each other at export time.

    The occurrence is the ordinal of the slot that supplied the label: two rows
    reading ``AO`` and ``AO#1`` under one filename are two files, not a
    duplicate. Two rows reading the *same* source under one filename template
    are.

    An output with **nothing assigned** returns ``None``: it writes no file (the
    export dialog skips it), so it cannot collide with anything, and two freshly
    created outputs must not read as duplicates of each other. An all-*constant*
    output is the opposite case -- it names no map but is fully determined and
    does write a file, so it keeps an identity (keyed on the ``CONSTANT``
    sentinel) and two of them sharing a filename template still read as
    duplicates.
    """
    where = f"output {index}"
    if not isinstance(data, dict):
        errors.append(f"{where}: must be an object")
        return None


    filename = data.get("filename")
    if not isinstance(filename, str) or not filename.strip():
        errors.append(f"{where}: 'filename' must be a non-empty template string")
        filename = ""
    elif _filename_escapes_output_folder(filename):
        # The export dialog builds each destination as os.path.join(directory,
        # filename), so "../../$textureSet" walks out of the artist's Export Folder
        # and "C:/Tex/$textureSet" makes os.path.join discard it entirely. Nothing
        # downstream re-checks, and Import Template accepts an arbitrary .json, so
        # this is where a template stops being allowed to choose the folder.
        errors.append(
            f"{where}: 'filename' must stay inside the export folder "
            "(no absolute paths, drive letters, or '..' segments)"
        )
        filename = ""

    image_format = data.get("format")
    if not isinstance(image_format, str) or image_format.upper() not in formats:
        errors.append(f"{where}: 'format' must be one of {', '.join(sorted(formats))}")
        image_format = ""

    bit_depth = data.get("bit_depth", 8)
    if isinstance(bit_depth, bool) or not isinstance(bit_depth, (int, str)):
        errors.append(f"{where}: 'bit_depth' must be one of {', '.join(str(value) for value in BIT_DEPTHS)}")
    else:
        try:
            depth = int(bit_depth)
        except (TypeError, ValueError):
            depth = -1
        if depth not in BIT_DEPTHS:
            errors.append(f"{where}: 'bit_depth' must be one of {', '.join(str(value) for value in BIT_DEPTHS)}")
        elif depth == 32 and image_format and image_format.upper() != constants.IMAGE_FORMAT_EXR:
            errors.append(f"{where}: 32-bit output requires the EXR format, not {image_format.upper()}")

    color_space = data.get("color_space", COLOR_SPACE_LINEAR)
    if not isinstance(color_space, str) or color_space.upper() not in COLOR_SPACES:
        errors.append(f"{where}: 'color_space' must be one of {', '.join(COLOR_SPACES)}")

    notes = data.get("notes", "")
    if not isinstance(notes, str):
        errors.append(f"{where}: 'notes' must be a string")

    if "dds_compression" in data:
        compression = data["dds_compression"]
        if not isinstance(compression, str) or compression.strip().upper() not in DDS_COMPRESSIONS:
            errors.append(
                f"{where}: 'dds_compression' must be one of {', '.join(DDS_COMPRESSIONS)}"
            )
        elif image_format and image_format.upper() != constants.IMAGE_FORMAT_DDS:
            # Not a warning: a compression on a PNG would silently do nothing,
            # which is exactly the accident this check exists to prevent.
            errors.append(
                f"{where}: 'dds_compression' is only valid on a DDS output, not {image_format.upper()}"
            )

    first_source = ""
    first_variant = DEFAULT_VARIANT
    has_constant = False
    channels = data.get("channels")
    if not isinstance(channels, dict):
        errors.append(f"{where}: 'channels' must be an object keyed by {', '.join(CHANNEL_SLOTS)}")
    else:
        unknown_slots = sorted(set(channels) - set(CHANNEL_SLOTS))
        if unknown_slots:
            errors.append(f"{where}: unknown channel slots {', '.join(unknown_slots)}")
        for slot in CHANNEL_SLOTS:
            if slot not in channels:
                continue
            if not _validate_channel(slot, channels[slot], index, sources, errors):
                continue
            slot_source = str(channels[slot].get("source", "") or "").strip()
            if is_constant_source(slot_source):
                # A constant names no map, so a real source in a later slot still
                # labels the file.
                has_constant = True
                continue
            if not first_source:
                first_source = slot_source
                first_variant = channel_variant(channels[slot])

    unknown_keys = sorted(
        set(data)
        - {"filename", "format", "bit_depth", "color_space", "channels", "notes", "dds_compression"}
    )
    if unknown_keys:
        errors.append(f"{where}: unknown keys {', '.join(unknown_keys)}")

    if not filename:
        return None
    if not first_source:
        if has_constant:
            # All constants: it names no map but writes a file, so it has an
            # identity.
            return (filename, CONSTANT_SOURCE, DEFAULT_VARIANT)
        # Nothing assigned: an in-progress output. It has no identity to collide
        # on -- see the docstring.
        return None
    label = constants.MAP_FILE_LABELS.get(first_source, first_source)
    return (filename, label, first_variant)


def validate_template(data) -> list[str]:
    """Return a list of human-readable errors; empty means the template is usable."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["template must be a JSON object"]

    schema = data.get("schema")
    if schema != TEMPLATE_SCHEMA:
        errors.append(f"'schema' must be '{TEMPLATE_SCHEMA}', got {schema!r}")

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("'name' must be a non-empty string")

    notes = data.get("notes", "")
    if not isinstance(notes, str):
        errors.append("'notes' must be a string")

    outputs = data.get("outputs")
    if not isinstance(outputs, list):
        # An EMPTY list is legal: that is a template the editor's "+" just made,
        # and it has to be writable before the artist adds the first output.
        errors.append("'outputs' must be a list")
        return errors

    sources = valid_source_identifiers()
    formats = valid_image_formats()
    seen: set[tuple] = set()
    for index, output in enumerate(outputs):
        key = _validate_output(output, index, sources, formats, errors)
        if key is None:
            continue
        if key in seen:
            errors.append(f"output {index}: duplicates an earlier output ('{key[0]}', map label '{key[1]}')")
        seen.add(key)

    unknown_keys = sorted(set(data) - {"schema", "name", "outputs", "notes"})
    if unknown_keys:
        errors.append(f"unknown keys {', '.join(unknown_keys)}")

    return errors


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def user_template_dir(create: bool = False) -> Path | None:
    """Directory holding this user's templates, or ``None`` outside Blender.

    Monkeypatch this in tests; every other function in the module resolves the
    user directory through it.

    ``extension_path_user`` only accepts real extension packages; a dev install
    loads Fyr Baker as a legacy add-on and it raises, which would make every
    template save fail. The fallback keeps user templates in Blender's per-user
    config dir instead -- a different location than the packaged build uses, but
    stable per install, so nothing is lost across sessions either way.
    """
    if bpy is None:
        return None
    try:
        path = bpy.utils.extension_path_user(__package__, path=USER_TEMPLATE_SUBDIR, create=create)
        if path:
            return Path(path)
    except Exception:
        pass
    try:
        base = bpy.utils.user_resource("CONFIG", path=f"fyr_baker/{USER_TEMPLATE_SUBDIR}", create=create)
    except Exception:
        return None
    return Path(base) if base else None


def builtin_template_dir() -> Path:
    """Where the shipped templates live. Packaged copy wins when it exists."""
    if BUILTIN_TEMPLATE_DIR_PACKAGED.is_dir():
        return BUILTIN_TEMPLATE_DIR_PACKAGED
    return BUILTIN_TEMPLATE_DIR


def _template_paths(directory: Path | None) -> list[Path]:
    if directory is None or not directory.exists():
        return []
    return sorted(directory.glob("*.json"), key=lambda path: path.stem.lower())


def template_path_for_name(template_name: str, builtin: bool = False) -> Path:
    directory = builtin_template_dir() if builtin else user_template_dir()
    if directory is None:
        raise TemplateError("User template directory is unavailable outside Blender")
    return directory / f"{sanitize_template_name(template_name)}.json"


# ---------------------------------------------------------------------------
# Read / write
# ---------------------------------------------------------------------------


def load_template_file(path: str | Path) -> dict:
    """Read and validate one template file. Raises ``TemplateError`` on any problem."""
    file_path = Path(path)
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise TemplateError(f"Output template not found: {file_path}") from error
    except (OSError, ValueError) as error:
        raise TemplateError(f"Output template {file_path.name} could not be read: {error}") from error

    errors = validate_template(data)
    if errors:
        raise TemplateError(f"Output template {file_path.name} is invalid: " + "; ".join(errors))
    return data


def list_template_errors() -> list[tuple[Path, str]]:
    """``(path, message)`` for every template file that will not load.

    list_templates has to skip these -- one hand-edited file must not take the
    whole dialog down -- but skipping silently is how an unreadable template
    became invisible: the dialog then resolved the artist's chosen name to the
    default and exported a different set of files with no warning anywhere. This
    is the channel the error takes out.
    """
    errors: list[tuple[Path, str]] = []
    for directory in (builtin_template_dir(), user_template_dir()):
        for path in _template_paths(directory):
            try:
                load_template_file(path)
            except TemplateError as error:
                errors.append((path, str(error)))
    return errors


def list_templates() -> list[TemplateInfo]:
    """Built-ins first, then user templates, each alphabetical by display name.

    Unreadable or invalid files are skipped rather than raising: one bad hand-
    edited JSON must not take the whole dialog down. A user file whose display
    name shadows a built-in is skipped too -- :func:`save_user_template` rejects
    that name up front, so a shadow here can only come from a hand-placed file.
    """
    infos: list[TemplateInfo] = []
    builtin_names: set[str] = set()

    for path in _template_paths(builtin_template_dir()):
        try:
            data = load_template_file(path)
        except TemplateError:
            continue
        name = str(data.get("name", "")).strip()
        builtin_names.add(name.casefold())
        infos.append(TemplateInfo(name=name, path=path, builtin=True))

    user_infos: list[TemplateInfo] = []
    for path in _template_paths(user_template_dir()):
        try:
            data = load_template_file(path)
        except TemplateError:
            continue
        name = str(data.get("name", "")).strip()
        if name.casefold() in builtin_names:
            continue
        user_infos.append(TemplateInfo(name=name, path=path, builtin=False))

    infos.sort(key=lambda info: info.name.casefold())
    user_infos.sort(key=lambda info: info.name.casefold())
    return infos + user_infos


def find_template(template_name: str) -> TemplateInfo | None:
    """Look a template up by display name (case-insensitive). Built-ins win."""
    wanted = str(template_name or "").strip().casefold()
    if not wanted:
        return None
    for info in list_templates():
        if info.name.casefold() == wanted:
            return info
    return None


def load_template(template_name: str) -> dict:
    info = find_template(template_name)
    if info is None:
        raise TemplateError(f"Output template '{template_name}' was not found")
    return load_template_file(info.path)


def save_user_template(data: dict, template_name: str | None = None) -> Path:
    """Validate and write a user template. Built-in names are refused.

    ``template_name`` renames the payload; without it the payload's own ``name``
    is used.
    """
    payload = dict(data or {})
    payload.setdefault("schema", TEMPLATE_SCHEMA)
    if template_name is not None:
        payload["name"] = str(template_name)

    errors = validate_template(payload)
    if errors:
        raise TemplateError("Output template is invalid: " + "; ".join(errors))

    name = str(payload["name"]).strip()
    file_stem = sanitize_template_name(name)
    for info in list_templates():
        if info.builtin and info.name.casefold() == name.casefold():
            raise TemplateError(f"'{name}' is a built-in template name; choose another name")
        if info.builtin or info.name.casefold() == name.casefold():
            continue
        # Two different names can sanitize onto one file ("My Template" and
        # "My_Template"); writing the second silently destroyed the first.
        if str(getattr(info, "path", "") or "") and Path(info.path).stem.casefold() == file_stem.casefold():
            raise TemplateError(
                f"'{name}' would be saved over the template '{info.name}'; choose another name"
            )

    directory = user_template_dir(create=True)
    if directory is None:
        raise TemplateError("User template directory is unavailable outside Blender")
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / f"{file_stem}.json"
    # Temp + replace, with the pid in the temp name. A direct write_text truncates the
    # artist's existing template first, so a crash, a full disk or a second Blender
    # session saving the same name left it torn - and a torn template then vanishes
    # from the UI silently, because list_templates swallows the load error, the export
    # falls back to the default template, and the next export writes a different set of
    # files into the same folder.
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def delete_user_template(template_name: str) -> bool:
    """Delete a user template. Returns False when there was nothing to delete.

    Built-ins are never deleted -- shipped files are not the user's to remove.
    """
    name = str(template_name or "").strip()
    if not name:
        return False

    directory = user_template_dir()
    if directory is None or not directory.exists():
        return False

    removed = False
    for path in _template_paths(directory):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if str(data.get("name", "")).strip().casefold() != name.casefold():
            continue
        try:
            path.unlink()
        except OSError as error:
            raise TemplateError(f"Could not delete {path.name}: {error}") from error
        removed = True
    return removed


def default_template_name() -> str:
    """Name of the template a project falls back to when its choice is missing."""
    names = {info.name.casefold(): info.name for info in list_templates()}
    if DEFAULT_TEMPLATE_NAME.casefold() in names:
        return DEFAULT_TEMPLATE_NAME
    return next(iter(names.values()), "")
