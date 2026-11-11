"""Export Textures dialog -- packed texture export through an output template (Phase 1).

Implements `docs/archive/TEXTURE_EXPORT_DIALOG_PLAN.md` sections 3.1 (dialog), 4
(execution flow) and 5 "Phase 1". The three engine halves it drives already
exist and are consumed unchanged:

* ``export_tokens``   -- ``$textureSet``/``$mesh``/... filename expansion,
* ``export_templates`` -- the JSON output-template store,
* ``export_pack``     -- numpy channel compositing plus the Blender encoder.

Layering
--------
Everything above :class:`MASTER_BAKER_OT_export_textures` is **pure**: it takes
plain dicts/dataclasses and returns dataclasses, touches no ``bpy`` state, and is
unit tested headless in ``tests/test_export_dialog.py``. The operators below it
only turn project state into those plain inputs and write the results to disk.
That split is deliberate -- the interesting failure modes (name collisions,
unknown tokens, unbaked sources, illegal format/depth pairs) are all decided in
the pure layer where they can be tested without Blender.

Execution route (READ THIS BEFORE CHANGING IT)
----------------------------------------------
The plan's D4 asks for a warm bake forced to EXR intermediates under
``.export_intermediate/`` before packing. **Phase 1 packs from the latest bake's
on-disk outputs instead**, i.e. the plan's own non-goal wording: "we export from
latest bake state, like SP exports current channels".

Why: ``export.prepare_bake_job`` has no output-root or image-format override, and
threading one through would touch ``_build_output_targets``, the output-directory
resolution, the ``latest_outputs`` bookkeeping and the progress/finalize path --
all on the hot bake path, which is under concurrent work. Forcing EXR by
temporarily assigning ``project.image_format`` is worse: its ``update=`` callback
marks every map dirty, so the user would silently pay a full re-bake twice.

The cost of the route taken is precision, not correctness: an 8-bit source is
packed at 8-bit. It is called out in the Export List tab and is the natural place
for a later increment to slot the forced-EXR warm bake back in (the constant
``constants.EXPORT_INTERMEDIATE_DIRNAME`` is already reserved for it).

Sources that were never baked are skipped with a warning, never fatal.
``latest_outputs`` is only *read* here -- exported files are a separate product
from bake outputs (plan section 4 step 6).

Several bakes of one map type
-----------------------------
A project may hold three AO bakes. Every source in this module is therefore
addressed by a **composite source key** (``export_pack.source_key``): the map
type for the first bake of that type, ``TYPE#n`` for the n-th, with the ordinal
counted in map-stack order (:func:`map_stack_occurrences`). Occurrence 0 keeping
the bare key is what makes a project with one bake per type -- and every template
written before ordinals existed -- behave exactly as it did.

An occurrence the project does not have is **unresolved**, and the row is skipped
with a reason naming the map and the occurrence. It never falls back to the first
bake: that would write a texture the artist did not ask for and cannot tell apart
from the one they wanted. See ``docs/MAP_VARIANTS_PLAN.md``.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import bpy

from . import constants, export_overwrite, export_pack, export_templates, export_tokens, naming, ui_utils


# ---------------------------------------------------------------------------
# Pure layer
# ---------------------------------------------------------------------------

#: Template ``color_space`` values (SRGB / LINEAR) mapped onto the encoder's
#: vocabulary (SRGB / NON_COLOR). "LINEAR" in a template means "raw data, no view
#: transform", which is exactly what ``export_pack``'s NON_COLOR path writes.
_COLOR_SPACE_TO_PACK = {
    export_templates.COLOR_SPACE_SRGB: export_pack.COLOR_SPACE_SRGB,
    export_templates.COLOR_SPACE_LINEAR: export_pack.COLOR_SPACE_NON_COLOR,
}

#: Source maps whose files carry sRGB-encoded values and must therefore be read
#: back through an sRGB colorspace to recover linear floats. Mirrors the write
#: side exactly (``blender_bake._make_bake_target_image``); every other map is
#: raw data and is read as Non-Color, so a raw -> raw export round-trips
#: byte-for-byte.
SRGB_SOURCE_MAP_TYPES = frozenset(
    {
        constants.MAP_MATERIAL_ALBEDO,
        constants.MAP_MATERIAL_EMISSION,
    }
)

#: Tile key used for an output that has no UDIM tile.
UNTILED = ""


def source_display_label(source: str) -> str:
    """Human-readable name of one composite source key.

    ``"AO" -> "AO"`` and ``"AO#1" -> "AO (bake 2)"``. The ordinal is shown
    1-based because that is how an artist counts the rows of their map stack;
    the key stays 0-based because that is what the template JSON carries. Every
    message that names a source -- skip reasons, channel chips -- goes through
    here, so a project with one bake per type reads exactly as it always did.
    """
    map_type, variant = export_pack.parse_source_key(source)
    label = constants.MAP_FILE_LABELS.get(map_type, map_type)
    if not variant:
        return label
    return f"{label} (bake {variant + 1})"


def missing_source_reason(source: str, disabled_sources=()) -> str:
    """Why one source is unavailable: a switched-off row reads differently from no bake."""
    if source in tuple(disabled_sources or ()):
        return f"{source_display_label(source)} map row disabled, never baked"
    return f"{source_display_label(source)} not baked"


#: Prefix marking a row warning as "why this row will not be written". Parsed by
#: :func:`skip_reason`, so it is a contract, not decoration.
SKIP_WARNING_PREFIX = "skipped: "
#: Prefix marking a row warning as "this channel was filled with a constant".
#: The row IS written, so these must never read as a skip.
FILL_WARNING_PREFIX = "filled: "


def _format_fill_value(value: float) -> str:
    """``0``, ``1``, ``0.5`` -- short enough for a one-line warning."""
    return f"{float(value):g}"


def fill_reason(fill, disabled_sources=()) -> str:
    """``R (Metalness) not baked, filled with 0`` for one substituted channel.

    Names the slot, the source behind it and the value that landed in the texel
    (``invert`` already applied, because that is what the file contains). A map
    type with no documented neutral says so, so a placeholder never reads like a
    deliberate no-op.
    """
    slot = str(getattr(fill, "slot", "") or "")
    source = str(getattr(fill, "source", "") or "")
    value = _format_fill_value(getattr(fill, "value", 0.0))
    reason = missing_source_reason(source, disabled_sources)
    text = f"{slot} ({reason}), filled with {value}"
    if not bool(getattr(fill, "neutral", False)):
        text += " (no neutral value for this map)"
    return text


def fill_notes(row) -> list[str]:
    """The substitution lines of one row, without the warning prefix."""
    notes: list[str] = []
    for warning in getattr(row, "warnings", ()) or ():
        text = str(warning)
        if text.startswith(FILL_WARNING_PREFIX):
            notes.append(text[len(FILL_WARNING_PREFIX):])
    return notes


def skipped_messages(rows) -> list[str]:
    """One line per dropped output, **naming the file it dropped**.

    The row warning on its own says "skipped: Opacity not baked", which never
    told the artist *which* of the template's four outputs vanished.
    """
    messages: list[str] = []
    for row in rows or ():
        if not getattr(row, "skipped", False):
            continue
        for warning in getattr(row, "warnings", ()) or ():
            messages.append(f"{getattr(row, 'filename', '')}: {warning}")
    return messages


def fill_messages(rows) -> list[str]:
    """One line per substituted channel of every row that WILL be written."""
    messages: list[str] = []
    for row in rows or ():
        if getattr(row, "skipped", False):
            continue
        for note in fill_notes(row):
            messages.append(f"{getattr(row, 'filename', '')}: {note}")
    return messages


@dataclass(frozen=True)
class ExportSetSpec:
    """One exportable texture set, flattened to plain data.

    ``sources`` maps a **composite source key** -- ``export_pack.source_key``: a
    map-type identifier for the first bake of that type, ``TYPE#n`` for the n-th
    -- to ``{tile_key: file path}``, where the tile key is the tile number as a
    string or ``UNTILED`` for an untiled bake. A project with one bake per type
    produces only bare keys, exactly as it always did.
    """

    key: str
    display_name: str
    implicit: bool = False
    group_names: tuple[str, ...] = ()
    #: What ``$mesh`` expands to: the set's first low-poly object, falling back
    #: to its first bake group's name (which is the object name for an implicit
    #: set). Empty when the set has no resolvable meshes.
    mesh_name: str = ""
    sources: dict = field(default_factory=dict)
    #: Source keys whose map row is disabled AND has no tracked output, so the skip
    #: reason can say "row disabled" instead of the misleading "not baked".
    disabled_sources: tuple[str, ...] = ()
    tiles: tuple[str, ...] = (UNTILED,)
    width: int = 0
    height: int = 0


@dataclass(frozen=True)
class ExportSetOptions:
    """Resolved Size / Padding / filter / DDS settings for one texture set."""

    width: int
    height: int
    resize_filter: str = constants.EXPORT_RESIZE_FILTER_TRIANGLE
    padding_mode: str = constants.EXPORT_PADDING_NONE
    padding_size: int = 0
    dds_compression: str = constants.EXPORT_DDS_BC7
    dds_generate_mips: bool = False


@dataclass
class ExportRow:
    """One file the export would write, plus everything the dialog must show."""

    set_key: str
    set_name: str
    output_index: int
    filename: str
    directory: str = ""
    format_id: str = ""
    bit_depth: int = 8
    color_space: str = export_pack.COLOR_SPACE_NON_COLOR
    width: int = 0
    height: int = 0
    tile: str = UNTILED
    sources: tuple[str, ...] = ()
    #: Source keys this row wanted and the project does not have. A row with SOME
    #: of them missing is still written -- see ``fills``; only a row missing
    #: *every* source is skipped.
    missing: tuple[str, ...] = ()
    #: ``export_pack.MissingFill`` per channel slot that was filled with a
    #: constant because its source was never baked. Empty for a fully sourced row.
    fills: tuple = ()
    warnings: list = field(default_factory=list)
    skipped: bool = False
    alert: bool = False
    resize_filter: str = constants.EXPORT_RESIZE_FILTER_TRIANGLE
    padding_mode: str = constants.EXPORT_PADDING_NONE
    padding_size: int = 0
    dds_compression: str = constants.EXPORT_DDS_BC7
    dds_generate_mips: bool = False

    @property
    def path(self) -> str:
        return os.path.join(self.directory, self.filename) if self.directory else self.filename

    @property
    def summary(self) -> str:
        """The Export List row text: ``T_Skull_N.png - 2048x2048 PNG 16-bit``."""
        size = f"{int(self.width)}x{int(self.height)}" if self.width and self.height else "?"
        return f"{self.filename} - {size} {self.format_id} {int(self.bit_depth)}-bit"


def template_color_space(output_def) -> str:
    """Encoder colorspace for one template output. Unknown values fall back to data."""
    raw = str((output_def or {}).get("color_space") or export_templates.COLOR_SPACE_LINEAR).strip().upper()
    return _COLOR_SPACE_TO_PACK.get(raw, export_pack.COLOR_SPACE_NON_COLOR)


def effective_format_and_depth(output_def, format_override=None, bit_depth_override=None) -> tuple[str, int, list[str]]:
    """Resolve one output's file type + bit depth against the dialog overrides.

    Returns ``(format_id, bit_depth, warnings)``. An override that the format
    cannot honour (TGA is 8-bit only, EXR has no 8-bit mode) is clamped rather
    than refused, with a warning, so one impossible pair never blocks the export.
    """
    warnings: list[str] = []
    template_format = str((output_def or {}).get("format") or "").strip().upper()
    template_depth = (output_def or {}).get("bit_depth", 8)

    format_id = str(format_override or "").strip().upper()
    if not format_id or format_id == constants.EXPORT_OVERRIDE_NONE:
        format_id = template_format

    requested_depth = bit_depth_override
    if requested_depth is None or str(requested_depth).strip().upper() in ("", constants.EXPORT_OVERRIDE_NONE):
        requested_depth = template_depth

    try:
        depth = export_pack.clamp_bit_depth_for_format(format_id, requested_depth)
    except export_pack.ExportPackError as error:
        warnings.append(str(error))
        return format_id, 8, warnings

    try:
        if int(str(requested_depth)) != int(depth):
            warnings.append(f"{format_id} cannot store {requested_depth}-bit; written at {depth}-bit")
    except (TypeError, ValueError):
        pass
    return format_id, int(depth), warnings


def find_set_override(export_settings, set_key: str):
    """Return the ``set_overrides`` row for ``set_key``, or ``None``."""
    key = str(set_key or "").strip()
    if not key:
        return None
    for item in getattr(export_settings, "set_overrides", []) or ():
        if str(getattr(item, "name", "") or "").strip() == key:
            return item
    return None


def ensure_set_override(export_settings, set_key: str):
    """Return (creating if needed) the ``set_overrides`` row for ``set_key``."""
    existing = find_set_override(export_settings, set_key)
    if existing is not None:
        return existing
    item = export_settings.set_overrides.add()
    item.name = str(set_key or "").strip()
    return item


def rename_set_override(export_settings, old_key: str, new_key: str) -> None:
    """Keep per-set overrides attached when a texture set is renamed."""
    old = str(old_key or "").strip()
    new = str(new_key or "").strip()
    if not old or not new or old == new:
        return
    item = find_set_override(export_settings, old)
    if item is None:
        return
    collision = find_set_override(export_settings, new)
    if collision is not None and not _same_override_row(collision, item):
        # Prefer the destination row that already exists for the new name. Rows are
        # matched by RNA pointer: every collection access returns a fresh wrapper, so
        # an identity check never found the old row and left it behind as a
        # stale duplicate.
        for index, candidate in enumerate(list(export_settings.set_overrides)):
            if _same_override_row(candidate, item):
                export_settings.set_overrides.remove(index)
                break
        return
    item.name = new


def _same_override_row(left, right) -> bool:
    if left is right:
        return True
    left_ptr = getattr(left, "as_pointer", None)
    right_ptr = getattr(right, "as_pointer", None)
    if callable(left_ptr) and callable(right_ptr):
        try:
            return left_ptr() == right_ptr()
        except Exception:
            return False
    return False


def resolve_size_side(size_mode: str, source_w: int, source_h: int) -> tuple[int, int]:
    """Map a Size enum value onto concrete width/height. Pure."""
    mode = str(size_mode or "").strip().upper()
    if not mode or mode in (constants.EXPORT_SIZE_FROM_SOURCE, constants.EXPORT_SET_USE_GLOBAL):
        return int(source_w), int(source_h)
    try:
        side = int(mode)
    except (TypeError, ValueError):
        return int(source_w), int(source_h)
    if side <= 0:
        return int(source_w), int(source_h)
    return side, side


def _override_field(override, field_name: str) -> str:
    if override is None:
        return constants.EXPORT_SET_USE_GLOBAL
    return str(getattr(override, field_name, "") or "").strip().upper() or constants.EXPORT_SET_USE_GLOBAL


def effective_export_options(export_settings, set_key: str, source_w: int, source_h: int) -> ExportSetOptions:
    """Resolve Global + per-set Size/Padding/filter into concrete pack options."""
    override = find_set_override(export_settings, set_key) if export_settings is not None else None

    size_mode = _override_field(override, "size")
    if size_mode == constants.EXPORT_SET_USE_GLOBAL:
        size_mode = str(getattr(export_settings, "size", "") or constants.EXPORT_SIZE_FROM_SOURCE).strip().upper()
    width, height = resolve_size_side(size_mode, source_w, source_h)

    resize_filter = _override_field(override, "resize_filter")
    if resize_filter == constants.EXPORT_SET_USE_GLOBAL:
        resize_filter = str(
            getattr(export_settings, "resize_filter", "") or constants.EXPORT_RESIZE_FILTER_TRIANGLE
        ).strip().upper()

    padding_mode = _override_field(override, "padding_mode")
    if padding_mode == constants.EXPORT_SET_USE_GLOBAL:
        padding_mode = str(
            getattr(export_settings, "padding_mode", "") or constants.EXPORT_PADDING_NONE
        ).strip().upper()

    if override is not None and _override_field(override, "padding_mode") != constants.EXPORT_SET_USE_GLOBAL:
        padding_size = int(getattr(override, "padding_size", 0) or 0)
    else:
        padding_size = int(getattr(export_settings, "padding_size", 0) or 0) if export_settings is not None else 0
    if padding_mode != constants.EXPORT_PADDING_DISTANCE:
        padding_size = 0

    dds_compression = str(
        getattr(export_settings, "dds_compression", "") or constants.EXPORT_DDS_BC7
    ).strip().upper()

    return ExportSetOptions(
        width=int(width),
        height=int(height),
        resize_filter=resize_filter or constants.EXPORT_RESIZE_FILTER_TRIANGLE,
        padding_mode=padding_mode or constants.EXPORT_PADDING_NONE,
        padding_size=max(0, int(padding_size)),
        dds_compression=dds_compression or constants.EXPORT_DDS_BC7,
        dds_generate_mips=bool(getattr(export_settings, "dds_generate_mips", False)),
    )


def build_export_rows(
    template,
    sets,
    *,
    project_name: str = "",
    blend_name: str = "",
    format_override=None,
    bit_depth_override=None,
    directory: str = "",
    options_by_set=None,
) -> list[ExportRow]:
    """Expand a template across texture sets x outputs x tiles into concrete rows.

    Pure: ``sets`` is a sequence of :class:`ExportSetSpec`. A row whose sources
    were never baked comes back ``skipped``, and so does a row for an output that
    has no map assigned to any channel yet ("no channels assigned"); a row whose
    filename uses an unknown token comes back ``alert``. None of them is fatal --
    the plan's step 1 says warn and skip, never abort the whole export.

    ``options_by_set`` maps set keys to :class:`ExportSetOptions` (Size/Padding/
    filter). Missing keys keep the bake resolution and default pack options.
    """
    rows: list[ExportRow] = []
    outputs = list((template or {}).get("outputs") or ())
    options_map = dict(options_by_set or {})

    for spec in sets:
        options = options_map.get(spec.key) or ExportSetOptions(
            width=int(spec.width),
            height=int(spec.height),
        )
        out_w = int(options.width) if int(options.width) > 0 else int(spec.width)
        out_h = int(options.height) if int(options.height) > 0 else int(spec.height)
        tiles = tuple(spec.tiles) or (UNTILED,)
        for index, output_def in enumerate(outputs):
            warnings: list[str] = []
            filename_template = str((output_def or {}).get("filename") or "")
            unknown = export_tokens.find_unknown_tokens(filename_template)
            if unknown:
                warnings.append("unknown token(s): " + ", ".join(f"${name}" for name in unknown))

            format_id, depth, format_warnings = effective_format_and_depth(
                output_def, format_override, bit_depth_override
            )
            warnings.extend(format_warnings)

            try:
                needed = export_pack.referenced_sources(output_def)
                uses_alpha = export_pack.output_uses_alpha(output_def)
                malformed = False
            except export_pack.ExportPackError as error:
                needed = ()
                uses_alpha = False
                malformed = True
                warnings.append(str(error))

            try:
                has_content = export_pack.output_has_content(output_def)
            except export_pack.ExportPackError:
                has_content = False
            unassigned = not has_content and not malformed

            if uses_alpha and format_id == constants.IMAGE_FORMAT_TIFF and int(depth) == 16:
                warnings.append(
                    "associated-alpha TIFF: strict readers un-premultiply; prefer PNG-16"
                )

            try:
                extension = naming.output_extension_for_image_format(format_id)
            except ValueError:
                extension = ""
                warnings.append(f"unsupported file type '{format_id}'")

            for tile in tiles:
                tile_key = str(tile or UNTILED)
                missing = tuple(
                    name
                    for name in needed
                    if not (spec.sources.get(name) or {}).get(tile_key)
                )
                # An output is dropped only when it has NOTHING to say: no channel
                # assigned at all, or not one of its sources on disk. With even one
                # source baked the file is written and the gaps are filled with a
                # neutral constant -- dropping a four-channel mask map because one
                # of its four maps is missing throws away the three that exist.
                fully_missing = bool(needed) and len(missing) == len(needed)
                fills: tuple = ()
                row_warnings = list(warnings)
                if unassigned:
                    row_warnings.append(SKIP_WARNING_PREFIX + "no channels assigned")
                elif fully_missing:
                    row_warnings.append(
                        SKIP_WARNING_PREFIX + ", ".join(
                            missing_source_reason(name, spec.disabled_sources) for name in missing
                        )
                    )
                elif missing:
                    _filled_def, fills = export_pack.substitute_missing_sources(output_def, missing)
                    row_warnings.extend(
                        FILL_WARNING_PREFIX + fill_reason(fill, spec.disabled_sources)
                        for fill in fills
                    )

                context = export_tokens.build_export_context(
                    project_name=project_name,
                    texture_set_name=spec.display_name,
                    udim_tile=tile_key or None,
                    resolution_x=out_w,
                    resolution_y=out_h,
                    bit_depth=depth,
                    image_format=format_id,
                    blend_name=blend_name,
                    mesh_name=spec.mesh_name,
                    color_space=str((output_def or {}).get("color_space") or ""),
                )
                stem = export_tokens.expand_template(filename_template, context)
                rows.append(
                    ExportRow(
                        set_key=spec.key,
                        set_name=spec.display_name,
                        output_index=index,
                        filename=f"{stem}{extension}",
                        directory=directory,
                        format_id=format_id,
                        bit_depth=int(depth),
                        color_space=template_color_space(output_def),
                        width=out_w,
                        height=out_h,
                        tile=tile_key,
                        sources=tuple(needed),
                        missing=missing,
                        fills=fills,
                        warnings=row_warnings,
                        skipped=unassigned or fully_missing or not extension,
                        alert=bool(unknown),
                        resize_filter=str(options.resize_filter),
                        padding_mode=str(options.padding_mode),
                        padding_size=int(options.padding_size),
                        # A DDS output may name its own BCn: one set has no single
                        # right answer (BC5 normals, BC4 masks, BC7 colour), so the
                        # template's per-output choice outranks the dialog's control.
                        # An output that names none reads the dialog, exactly as
                        # every template written before the key did.
                        dds_compression=export_templates.output_dds_compression(
                            output_def, str(options.dds_compression)
                        ),
                        dds_generate_mips=bool(options.dds_generate_mips),
                    )
                )
    return rows


def _bakeable_type_for_source(identifier: str) -> str:
    """Map a template source identifier to the map-stack type that bakes it.

    A ``MATERIAL_*`` channel source is produced by the single ``MATERIAL`` bake
    (the stack stores the bare type; per-channel effective types are a read of it,
    see ``constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE``). Everything else bakes
    under its own identifier.
    """
    key = str(identifier or "").strip().upper()
    if key.startswith("MATERIAL_"):
        return constants.MAP_MATERIAL
    return key


def missing_bakeable_map_types(project, rows) -> tuple[str, ...]:
    """Enabled map types a bake would produce that the export is missing. Pure-ish.

    "Bake Missing Maps First" only bakes what a bake can actually create: a source
    is bakeable iff its map type is **enabled in the stack**. A template asking for
    an occurrence the stack cannot supply (``AO#2`` with one AO row) stays missing
    after the bake and is still skipped with a reason -- baking a type refreshes
    every occurrence it has, and cannot invent one it does not.

    Reads ``project.maps`` only (via :func:`map_rebuild.enabled_map_types`); the
    ``rows`` are the already-computed export rows, so the "what is missing" decision
    is not duplicated here.
    """
    from . import map_rebuild

    enabled = {str(t or "").strip().upper() for t in map_rebuild.enabled_map_types(project)}
    if not enabled:
        return ()
    wanted: set[str] = set()
    for row in rows:
        # Not only skipped rows: a row that WILL be written with a neutral fill in
        # place of an unbaked channel is exactly a row "Bake Missing Maps First"
        # should complete, and it is no longer skipped.
        for source in getattr(row, "missing", ()) or ():
            map_type, _variant = export_pack.parse_source_key(source)
            bakeable = _bakeable_type_for_source(map_type)
            if bakeable in enabled:
                wanted.add(bakeable)
    return tuple(sorted(wanted))


def find_collisions(rows) -> list[tuple[ExportRow, ExportRow]]:
    """Pairs of rows that would write the same file.

    Only rows that will actually be written participate: a skipped row never
    reaches disk, so it cannot collide with anything. The first offender is
    reported against each later one so the error message can name both template
    entries.
    """
    seen: dict[str, ExportRow] = {}
    collisions: list[tuple[ExportRow, ExportRow]] = []
    for row in rows:
        if row.skipped:
            continue
        key = os.path.normcase(os.path.normpath(row.path))
        first = seen.get(key)
        if first is None:
            seen[key] = row
            continue
        collisions.append((first, row))
    return collisions


def mark_collisions(rows) -> list[tuple[ExportRow, ExportRow]]:
    """:func:`find_collisions`, additionally flagging both offenders on the rows."""
    collisions = find_collisions(rows)
    for first, second in collisions:
        message = f"name collision with template output #{first.output_index + 1}"
        for row in (first, second):
            row.alert = True
            if message not in row.warnings:
                row.warnings.append(message)
    return collisions


def _export_file_identity(path):
    """Compare destinations through relative paths, links and filesystem aliases."""
    canonical = os.path.normcase(os.path.realpath(path))
    try:
        info = os.stat(path)
        identity = (info.st_dev, info.st_ino) if info.st_ino else None
    except OSError:
        identity = None
    return canonical, identity


def find_bake_source_collisions(rows, source_paths) -> list[tuple[ExportRow, str]]:
    """Exports that would replace a tracked bake, even through a hard link."""
    paths, identities = {}, {}
    for source in source_paths:
        canonical, identity = _export_file_identity(source)
        paths.setdefault(canonical, source)
        if identity is not None:
            identities.setdefault(identity, source)
    collisions = []
    for row in rows:
        if row.skipped:
            continue
        canonical, identity = _export_file_identity(row.path)
        source = paths.get(canonical) or identities.get(identity)
        if source:
            collisions.append((row, source))
    return collisions


def bake_source_collision_message(row) -> str:
    return (
        f"Export would overwrite the original bake '{row.filename}'. "
        "Choose a different output folder or filename."
    )


#: Keycap icons Blender ships for the letters R/G/B/A, used as SP-style channel
#: chips in the Output Template tab.
CHANNEL_SLOT_ICONS = {"R": "EVENT_R", "G": "EVENT_G", "B": "EVENT_B", "A": "EVENT_A"}

#: Chip icon for an output whose RGB all come from the same grayscale source.
GRAY_CHIP_ICON = "IMAGE_ALPHA"

#: Placeholder text for a channel slot the template leaves empty.
EMPTY_CHIP_TEXT = "None"


@dataclass(frozen=True)
class ChannelChip:
    """One channel chip: a keycap icon plus the source it is fed from."""

    slot: str
    icon: str
    text: str
    filled: bool


def _slot_key(definition) -> str:
    """The composite source key one raw channel definition reads (``""`` if none).

    Two slots reading different *occurrences* of one map type are two different
    sources, so this -- not the bare ``source`` string -- is what the gray-chip
    collapse below compares.
    """
    try:
        return export_pack.channel_source_key(definition or {})
    except export_pack.ExportPackError:
        return str((definition or {}).get("source") or "")


def _slot_source_label(definition, slot: str) -> str:
    """``Normal.G`` / ``AO`` / ``Curvature inv`` for one channel definition."""
    source = str((definition or {}).get("source") or "")
    label = source_display_label(_slot_key(definition) or source)
    source_channel = str((definition or {}).get("channel") or "").strip().upper()
    if source_channel and source_channel not in ("GRAY", slot):
        label = f"{label}.{source_channel}"
    if (definition or {}).get("invert"):
        label = f"{label} inv"
    return label


def channel_chips(output_def) -> tuple[ChannelChip, ...]:
    """The chips one template output shows, in slot order.

    Four chips normally -- one per RGBA slot, with an unfilled slot carrying
    :data:`EMPTY_CHIP_TEXT` and ``filled=False`` so the drawing code can gray it.
    A slot that exists but has **no map assigned yet** reads as unfilled here too:
    it contributes zeros exactly like an absent slot, so it must not be shown as
    if it carried something.

    The single exception is an output whose R, G and B all read the *same*
    grayscale source with the same inversion and no alpha: that is one gray image,
    not a three-channel pack, so it collapses to a single ``GRAY`` chip. An output
    that fills only R is deliberately **not** collapsed -- ``export_pack`` writes
    zeros into the untouched slots, and hiding that would hide a real result.
    """
    channels = (output_def or {}).get("channels") or {}
    slots = {
        slot: (channels.get(slot) if isinstance(channels.get(slot), dict) else None)
        for slot in export_pack.CHANNEL_SLOTS
    }
    rgb = [slots["R"], slots["G"], slots["B"]]
    if slots["A"] is None and all(definition is not None for definition in rgb):
        # Composite keys, so three slots reading AO, AO#1 and AO#2 stay three
        # chips: they are three different bakes that merely share a type.
        sources = {_slot_key(definition) or str(definition.get("source") or "") for definition in rgb}
        source_channels = {str(definition.get("channel") or "").strip().upper() for definition in rgb}
        inversions = {bool(definition.get("invert")) for definition in rgb}
        # ``sources != {""}``: three unassigned slots are not one gray image, they
        # are three empty slots, and collapsing them would hide that.
        if len(sources) == 1 and sources != {""} and source_channels == {"GRAY"} and len(inversions) == 1:
            return (ChannelChip("GRAY", GRAY_CHIP_ICON, _slot_source_label(rgb[0], "R"), True),)

    chips = []
    for slot in export_pack.CHANNEL_SLOTS:
        definition = slots[slot]
        assigned = definition is not None and bool(str(definition.get("source") or "").strip())
        chips.append(
            ChannelChip(
                slot,
                CHANNEL_SLOT_ICONS[slot],
                _slot_source_label(definition, slot) if assigned else EMPTY_CHIP_TEXT,
                assigned,
            )
        )
    return tuple(chips)


def shorten_path(path, max_chars: int = 72) -> str:
    """Trim a path from the *left*, keeping the tail that identifies the folder.

    Paths overflow the dialog at the front (drive + user profile), and the part an
    artist checks is the end, so the ellipsis goes first.
    """
    text = str(path or "")
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return "..."[:max_chars]
    return "..." + text[-(max_chars - 3):]


def row_detail(row) -> str:
    """``256x256 - PNG 16-bit`` for the right-hand side of an Export List row."""
    size = f"{int(row.width)}×{int(row.height)}" if row.width and row.height else "?"
    return f"{size} · {row.format_id} {int(row.bit_depth)}-bit"


def skip_reason(row) -> str:
    """Why one row will not be written, short enough for a single grayed line."""
    for warning in getattr(row, "warnings", ()) or ():
        text = str(warning)
        if text.startswith(SKIP_WARNING_PREFIX):
            return text[len(SKIP_WARNING_PREFIX):]
    missing = tuple(getattr(row, "missing", ()) or ())
    if missing:
        return ", ".join(f"{source_display_label(name)} not baked" for name in missing)
    return "not exportable"


def alert_messages(rows) -> list[str]:
    """One line per real problem (collision / unknown token), deduplicated.

    Skip reasons and neutral fills are *not* problems -- an unbaked source is
    expected -- so they are filtered out here and summarised separately
    (:func:`skipped_messages`, :func:`fill_messages`).
    """
    messages: list[str] = []
    for row in rows or ():
        if not getattr(row, "alert", False):
            continue
        for warning in getattr(row, "warnings", ()) or ():
            text = str(warning)
            if text.startswith(SKIP_WARNING_PREFIX) or text.startswith(FILL_WARNING_PREFIX):
                continue
            line = f"{row.filename}: {text}"
            if line not in messages:
                messages.append(line)
    return messages


def group_rows_by_set(rows) -> list[tuple[str, list]]:
    """``[(set name, rows)]`` in first-seen order, so the list reads per set."""
    order: list[str] = []
    grouped: dict[str, list] = {}
    for row in rows or ():
        name = str(getattr(row, "set_name", "") or "")
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].append(row)
    return [(name, grouped[name]) for name in order]


def excluded_set_keys(export_settings) -> set[str]:
    return {
        str(getattr(item, "name", "") or "").strip()
        for item in getattr(export_settings, "excluded_texture_sets", []) or ()
        if str(getattr(item, "name", "") or "").strip()
    }


def set_is_included(export_settings, set_key: str) -> bool:
    """Sets are included unless explicitly excluded, so new sets are opt-out."""
    return str(set_key or "").strip() not in excluded_set_keys(export_settings)


def count_exportable(rows) -> int:
    return sum(1 for row in rows if not row.skipped)


# ---------------------------------------------------------------------------
# Project -> plain data
# ---------------------------------------------------------------------------


def collect_export_sets(project) -> list[tuple[str, str, bool, tuple[str, ...]]]:
    """Every exportable texture set as ``(key, display name, implicit, groups)``.

    Mirrors how ``export._build_output_targets`` names files: a bake group that
    joins a texture set contributes to that set's single output, and a group with
    no set is its own implicit set named after the group -- because
    ``naming.normalize_texture_set_name`` falls back to the group name there.
    """
    from . import properties

    ordered: list[tuple[str, str, bool, tuple[str, ...]]] = []
    members: dict[str, list[str]] = {}
    for group in getattr(project, "groups", []) or ():
        state = properties.group_metadata_state(group)
        key = str(getattr(state, "texture_set_name", "") or "").strip()
        group_name = str(getattr(group, "name", "") or "").strip()
        if not key:
            if group_name:
                ordered.append((group_name, naming.sanitize_token(group_name), True, (group_name,)))
            continue
        members.setdefault(key, []).append(group_name)

    real: list[tuple[str, str, bool, tuple[str, ...]]] = []
    for key, group_names in members.items():
        display = properties.resolve_texture_set_output_name(project, key) or key
        real.append((key, naming.sanitize_token(display), False, tuple(group_names)))
    real.sort(key=lambda entry: entry[1].casefold())
    return real + ordered


def _group_to_set_key(project) -> dict[str, str]:
    from . import properties

    mapping: dict[str, str] = {}
    for group in getattr(project, "groups", []) or ():
        group_name = str(getattr(group, "name", "") or "").strip()
        if not group_name:
            continue
        state = properties.group_metadata_state(group)
        mapping[group_name] = str(getattr(state, "texture_set_name", "") or "").strip() or group_name
    return mapping


@dataclass(frozen=True)
class MapOccurrence:
    """One real row of the map stack, tagged with its occurrence ordinal.

    ``variant`` is 0-based and counted among rows of the *same* ``map_type``, in
    map-stack order, phantom "+" rows skipped. It is the portable half of a
    composite source key: it says *which* AO without naming a uuid or a variant
    name, neither of which survives a trip to another project.
    """

    index: int
    uuid: str
    map_type: str
    variant: int
    map_setting: object = None

    @property
    def source_key(self) -> str:
        return export_pack.source_key(self.map_type, self.variant)


def map_stack_occurrences(project) -> tuple[MapOccurrence, ...]:
    """Every bakeable row of ``project.maps``, in stack order, with its ordinal.

    The single source of occurrence order in this module. Deriving it from the
    stack -- and never from ``latest_outputs`` iteration order -- is what makes
    ``AO#1`` mean the same bake on every redraw and after every re-bake.
    """
    counts: dict[str, int] = {}
    occurrences: list[MapOccurrence] = []
    for index, item in enumerate(getattr(project, "maps", []) or ()):
        if getattr(item, "is_add_phantom", False):
            continue
        map_type = str(getattr(item, "map_type", "") or "").strip()
        if not map_type:
            continue
        bucket = map_type.upper()
        variant = counts.get(bucket, 0)
        counts[bucket] = variant + 1
        occurrences.append(
            MapOccurrence(
                index=index,
                uuid=str(getattr(item, "uuid", "") or "").strip(),
                map_type=map_type,
                variant=variant,
                map_setting=item,
            )
        )
    return tuple(occurrences)


def _effective_map_types_by_uuid(occurrences) -> dict[str, str]:
    """``map uuid -> effective map type`` for every row of the stack.

    The effective type is what the backend/template calls the output (``MATERIAL_ALBEDO``,
    ``LIGHTING``, ``CURVATURE_DIRECTION``); the row itself stores the base type. Resolved
    through ``export`` so there is exactly one implementation of that translation."""
    from . import export

    resolved: dict[str, str] = {}
    for occurrence in occurrences:
        if not occurrence.uuid or occurrence.map_setting is None:
            continue
        try:
            effective = str(export.effective_map_type_for_setting(occurrence.map_setting) or "").strip()
        except Exception:  # pragma: no cover - defensive, Blender-only
            continue
        if effective:
            resolved[occurrence.uuid] = effective
    return resolved


def disabled_unbaked_source_keys(project, sources) -> tuple[str, ...]:
    """Source keys whose map row exists but is DISABLED and has no tracked output.

    Lets the export list say "row disabled" instead of the misleading "not baked" for a
    channel the artist switched off. A disabled row that *does* have a tracked output is
    absent here on purpose: it exports, exactly like a disabled mesh-map row always did."""
    baked = set(sources or ())
    occurrences = map_stack_occurrences(project)
    effective_types = _effective_map_types_by_uuid(occurrences)
    # Variants are counted over EVERY row in stack order (not only the disabled ones) so
    # the ordinal of a given row is the same one collect_baked_sources hands the template.
    effective_variants: dict[str, int] = {}
    keys: list[str] = []
    for occurrence in occurrences:
        candidate_keys = [occurrence.source_key]
        effective = effective_types.get(occurrence.uuid, "")
        if effective and effective.upper() != occurrence.map_type.upper():
            variant = effective_variants.get(effective.upper(), 0)
            effective_variants[effective.upper()] = variant + 1
            candidate_keys.append(export_pack.source_key(effective, variant))
        if bool(getattr(occurrence.map_setting, "enabled", True)):
            continue
        for key in candidate_keys:
            if key not in baked and key not in keys:
                keys.append(key)
    return tuple(keys)


def _source_file_exists(path: str) -> bool:
    """True when a recorded bake output is still on disk.

    ``project.latest_outputs`` is a record of what a bake *wrote*, not of what still
    exists. Deleting or moving textures -- an everyday thing to do between a bake and a
    hand-off -- left the dialog counting them: it advertised "8 textures will be
    exported" and then wrote 1 and skipped 18 (RC sweep 2026-08-29, finding 20). The
    surrounding comment already claimed a row is dropped when a source is not "on disk";
    this makes that true.
    """
    try:
        return os.path.isfile(path)
    except Exception:
        return False


def tracked_bake_paths(project) -> set[str]:
    """Protect every recorded bake in the blend, not only selected export sources.

    Disabled/orphaned maps, excluded sets and stale UDIM files are still originals.
    Read the records directly: collect_baked_sources intentionally filters these out.
    """
    projects = [project]
    for scene in getattr(bpy.data, "scenes", ()):
        settings = getattr(scene, "fyr_baker_settings", None)
        projects.extend(getattr(settings, "projects", ()))
    paths = set()
    for owner in projects:
        for output in getattr(owner, "latest_outputs", ()):
            records = [output, *getattr(output, "udim_tiles", ())]
            for record in records:
                path = str(getattr(record, "file_path", "") or "").strip()
                if path:
                    paths.add(bpy.path.abspath(path))
    return paths


def collect_baked_sources(project) -> dict[str, dict[str, dict[str, str]]]:
    """``{set key: {composite source key: {tile: file path}}}`` from the latest bake.

    Read-only view of ``project.latest_outputs``; stale UDIM tiles are ignored so
    a tile that is no longer occupied never feeds a pack.

    Several bakes of one map type get one key each -- ``AO``, ``AO#1``,
    ``AO#2``. This used to be ``setdefault(map_type, {})``, which put all three
    on one key and let **the last one silently win**: today's export picked an
    arbitrary AO and said nothing about it.

    Ordering is by map-stack position, resolved through each output's
    ``map_uuid``, so the ordinals match the template schema's ``variant``. Two
    outputs carrying the same ``map_uuid`` (one bake
    reached through two groups of one texture set) share an ordinal and merge, as
    they always did. An output whose map row no longer exists cannot be placed
    from the stack, so it sorts after every row that can, in ``latest_outputs``
    order -- deterministic, and it still never collapses onto another bake's key.
    """
    from . import properties

    group_sets = _group_to_set_key(project)
    occurrences = map_stack_occurrences(project)
    stack_rank = {
        occurrence.uuid: occurrence.index
        for occurrence in occurrences
        if occurrence.uuid
    }
    effective_types = _effective_map_types_by_uuid(occurrences)

    # (set key, map type) -> [(stack rank, latest_outputs position, uuid, item)]
    buckets: dict[tuple[str, str], list[tuple[int, int, str, object]]] = {}
    order: list[tuple[str, str]] = []
    tracked: list[tuple[int, object, str, str, str, str]] = []
    for position, item in enumerate(getattr(project, "latest_outputs", []) or ()):
        map_type = str(getattr(item, "map_type", "") or "").strip()
        if not map_type:
            continue
        set_key = group_sets.get(str(getattr(item, "group_name", "") or "").strip())
        if not set_key:
            continue
        uuid = str(getattr(item, "map_uuid", "") or "").strip()
        # Live rows translate raw->effective through the stack; an orphaned uuid (the
        # stack was rebuilt, e.g. by a preset load) falls back to the effective type
        # recorded on the entry at ingestion time.
        alias = effective_types.get(uuid, "") or str(
            getattr(item, "effective_map_type", "") or ""
        )
        tracked.append((position, item, set_key, map_type, uuid, alias))
    # Texture sets whose material bake already provides an opacity channel; the
    # projected Opacity map must not shadow it there.
    material_opacity_sets = {
        set_key
        for _position, _item, set_key, map_type, _uuid, alias in tracked
        if constants.MAP_MATERIAL_OPACITY in (map_type.upper(), alias.upper())
    }
    for position, item, set_key, map_type, uuid, alias in tracked:
        # A tracked output is addressable under the type it was stored with AND under
        # its row's EFFECTIVE type. Ingestion stores the raw stack type (``MATERIAL``,
        # ``SCENE_LIGHTING``) so the Outputs panel can match the row, while templates
        # reference the effective type (``MATERIAL_ALBEDO``, ``LIGHTING``) -- without
        # the alias those channels read as "not baked" even with the file on disk.
        map_types = [map_type]
        if alias and alias.upper() != map_type.upper():
            map_types.append(alias)
        # Every built-in template carries opacity as `MATERIAL_OPACITY` (Base Color
        # alpha, Painter's Opacity file). A high-to-low project bakes the projected
        # high-poly alpha as the `OPACITY` map, which is that very channel, yet the
        # slot read "Opacity not baked" with the file on disk. Alias it unless a
        # material bake in the same set already provides its own opacity.
        if map_type.upper() == constants.MAP_OPACITY and set_key not in material_opacity_sets:
            map_types.append(constants.MAP_MATERIAL_OPACITY)
        # Every built-in template spells the normal slot `NORMAL` -- the mesh-map,
        # high-to-low normal -- while a material project produces `MATERIAL_NORMAL`.
        # The slot therefore never resolved and the export logged "skipped: Normal
        # not baked" for a map that WAS baked, writing every other channel
        # (MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P12). Alias it here rather than
        # editing six template files, and only in a material-workflow project, where
        # a geometry NORMAL row cannot exist to be shadowed by it.
        if (
            str(getattr(project, "workflow", "") or "").strip().upper() == constants.WORKFLOW_MATERIAL
            and alias.upper() == constants.MAP_MATERIAL_NORMAL
        ):
            map_types.append(constants.MAP_NORMAL)
        for bucket_type in map_types:
            bucket = (set_key, bucket_type)
            if bucket not in buckets:
                buckets[bucket] = []
                order.append(bucket)
            buckets[bucket].append((stack_rank.get(uuid, sys.maxsize), position, uuid, item))

    sources: dict[str, dict[str, dict[str, str]]] = {}
    for bucket in order:
        set_key, map_type = bucket
        entries = sorted(buckets[bucket], key=lambda entry: (entry[0], entry[1]))
        assigned: dict[str, int] = {}
        next_variant = 0
        for _rank, _position, uuid, item in entries:
            if uuid and uuid in assigned:
                variant = assigned[uuid]
            else:
                variant = next_variant
                next_variant += 1
                if uuid:
                    assigned[uuid] = variant
            key = export_pack.source_key(map_type, variant)
            per_map = sources.setdefault(set_key, {}).setdefault(key, {})
            if properties.output_is_tiled(item):
                for tile in properties.output_live_tiles(item):
                    path = str(getattr(tile, "file_path", "") or "").strip()
                    number = int(getattr(tile, "udim_tile", 0) or 0)
                    if path and number and _source_file_exists(path):
                        per_map[str(number)] = path
                continue
            path = str(getattr(item, "file_path", "") or "").strip()
            if path and _source_file_exists(path):
                per_map[UNTILED] = path
    return sources


def _set_mesh_name(project, set_key: str, group_names) -> str:
    """What ``$mesh`` expands to for one texture set.

    The set's first low-poly object; a set that spans several meshes names the
    first (the token is singular by definition). Falls back to the first bake
    group's name, which for an implicit set *is* the object name, so the token is
    never empty just because the low-poly list could not be resolved.
    """
    from . import export

    try:
        objects = export._texture_set_low_objects(project, set_key)
    except Exception:  # pragma: no cover - defensive, Blender-only
        objects = []
    for obj in objects or ():
        name = str(getattr(obj, "name", "") or "").strip()
        if name:
            return name
    for group_name in group_names or ():
        name = str(group_name or "").strip()
        if name:
            return name
    return ""


def build_set_specs(project, keys=None) -> list[ExportSetSpec]:
    """Turn the project's texture sets into pure :class:`ExportSetSpec` inputs."""
    baked = collect_baked_sources(project)
    width = int(getattr(project, "resolution_x", constants.DEFAULT_RESOLUTION) or 0)
    height = int(getattr(project, "resolution_y", constants.DEFAULT_RESOLUTION) or 0)
    wanted = None if keys is None else {str(key or "").strip() for key in keys}

    specs: list[ExportSetSpec] = []
    for key, display, implicit, group_names in collect_export_sets(project):
        if wanted is not None and key not in wanted:
            continue
        sources = baked.get(key, {})
        tiles = sorted({tile for per_map in sources.values() for tile in per_map if tile})
        specs.append(
            ExportSetSpec(
                key=key,
                display_name=display,
                implicit=implicit,
                group_names=tuple(group_names),
                mesh_name=_set_mesh_name(project, key, group_names),
                sources=sources,
                disabled_sources=disabled_unbaked_source_keys(project, sources),
                tiles=tuple(tiles) if tiles else (UNTILED,),
                width=width,
                height=height,
            )
        )
    return specs


def active_export_settings(project):
    return getattr(project, "export_settings", None)


#: ``{template name: (path, mtime_ns, payload)}``. ``draw`` runs on every redraw
#: of the popup, and re-reading plus re-validating the JSON at mouse-move rate is
#: pure waste; the mtime keeps the cache honest against an edit on disk.
_TEMPLATE_CACHE: dict[str, tuple[str, int, dict]] = {}

#: ``list_templates()`` reads *and validates* every template file, and the dialog
#: needs the list three times per redraw (dropdown items, name resolution, load).
#: A sub-second TTL is imperceptible to someone dropping a new JSON in the folder
#: and removes the whole cost from the redraw path.
_TEMPLATE_LIST_TTL_SECONDS = 1.0
_TEMPLATE_LIST_CACHE: dict[str, object] = {"stamp": 0.0, "infos": ()}


def cached_template_infos():
    """``export_templates.list_templates()`` behind a short TTL."""
    now = time.monotonic()
    stamp = float(_TEMPLATE_LIST_CACHE.get("stamp") or 0.0)
    if _TEMPLATE_LIST_CACHE.get("infos") and (now - stamp) < _TEMPLATE_LIST_TTL_SECONDS:
        return _TEMPLATE_LIST_CACHE["infos"]
    try:
        infos = tuple(export_templates.list_templates())
    except Exception:
        infos = ()
    _TEMPLATE_LIST_CACHE["infos"] = infos
    _TEMPLATE_LIST_CACHE["stamp"] = now
    return infos


def invalidate_template_cache() -> None:
    _TEMPLATE_CACHE.clear()
    _TEMPLATE_LIST_CACHE["infos"] = ()
    _TEMPLATE_LIST_CACHE["stamp"] = 0.0


def find_template_cached(template_name: str):
    wanted = str(template_name or "").strip().casefold()
    if not wanted:
        return None
    for info in cached_template_infos():
        if info.name.casefold() == wanted:
            return info
    return None


def load_template_cached(template_name: str) -> dict:
    info = find_template_cached(template_name)
    if info is None:
        raise export_templates.TemplateError(f"Output template '{template_name}' was not found")
    try:
        stamp = info.path.stat().st_mtime_ns
    except OSError:
        stamp = -1
    cached = _TEMPLATE_CACHE.get(info.name)
    if cached is not None and cached[0] == str(info.path) and cached[1] == stamp:
        return cached[2]
    payload = export_templates.load_template_file(info.path)
    _TEMPLATE_CACHE[info.name] = (str(info.path), stamp, payload)
    return payload


def _stored_template_is_available(export_settings) -> bool:
    """True when the artist's stored template name actually resolves to a file."""
    name = str(getattr(export_settings, "template", "") or "").strip()
    return bool(name) and find_template_cached(name) is not None


def unavailable_template_message(export_settings) -> str:
    """Why the export is not using the artist's chosen template, or "".

    Silence here is what let an unreadable template export a different set of
    files into the artist's content folder without a word.
    """
    name = str(getattr(export_settings, "template", "") or "").strip()
    if not name or find_template_cached(name) is not None:
        return ""
    substitute = resolve_template_name(export_settings)
    detail = ""
    try:
        stem = export_templates.sanitize_template_name(name).casefold()
        for path, message in export_templates.list_template_errors():
            if Path(path).stem.casefold() == stem:
                detail = message
                break
    except Exception:
        detail = ""
    if detail:
        return detail + (f" -- exporting with '{substitute}'" if substitute else "")
    return (
        f"Output template '{name}' is unavailable"
        + (f"; exporting with '{substitute}'" if substitute else "")
    )


def resolve_template_name(export_settings) -> str:
    name = str(getattr(export_settings, "template", "") or "").strip()
    if name and find_template_cached(name) is not None:
        return name
    names = {info.name.casefold(): info.name for info in cached_template_infos()}
    if export_templates.DEFAULT_TEMPLATE_NAME.casefold() in names:
        return export_templates.DEFAULT_TEMPLATE_NAME
    return next(iter(names.values()), "")


def resolve_export_dir(project, export_settings) -> Path:
    """Destination folder: the dialog's own, or an exports subfolder beside bakes."""
    from . import export

    raw = str(getattr(export_settings, "output_dir", "") or "").strip()
    if not raw:
        return export.resolved_project_output_dir(project) / "exports"
    if raw.startswith("//") and not bpy.data.filepath:
        return Path(bpy.app.tempdir or Path.cwd()) / raw[2:]
    return Path(bpy.path.abspath(raw))


def _override_value(raw) -> str | None:
    value = str(raw or "").strip().upper()
    if not value or value == constants.EXPORT_OVERRIDE_NONE:
        return None
    return value


def compute_rows(project, export_settings, *, keys=None, directory: str = ""):
    """Everything the dialog and ``execute`` need: ``(template, rows, error)``."""
    try:
        template = load_template_cached(resolve_template_name(export_settings))
    except export_templates.TemplateError as error:
        return None, [], str(error)

    if keys is None:
        keys = [
            key
            for key, _display, _implicit, _groups in collect_export_sets(project)
            if set_is_included(export_settings, key)
        ]
    specs = build_set_specs(project, keys)
    options_by_set = {
        spec.key: effective_export_options(
            export_settings, spec.key, int(spec.width), int(spec.height)
        )
        for spec in specs
    }
    rows = build_export_rows(
        template,
        specs,
        project_name=str(getattr(project, "name", "") or ""),
        blend_name=Path(bpy.data.filepath).stem if getattr(bpy.data, "filepath", "") else "",
        format_override=_override_value(getattr(export_settings, "file_format_override", None)),
        bit_depth_override=_override_value(getattr(export_settings, "bit_depth_override", None)),
        directory=directory,
        options_by_set=options_by_set,
    )
    mark_collisions(rows)
    for row, _source in find_bake_source_collisions(rows, tracked_bake_paths(project)):
        row.alert = True
        row.warnings.append(bake_source_collision_message(row))
    return template, rows, ""


# ---------------------------------------------------------------------------
# Blender-side image IO
# ---------------------------------------------------------------------------


def _load_source_array(path: str, map_type: str):
    """Load one baked map as a float32 HxWx4 array in Blender's bottom-up order.

    The image is read through the same colorspace it was written with (see
    :data:`SRGB_SOURCE_MAP_TYPES`), so ``image.pixels`` hands back linear floats
    and ``export_pack.save_composed_image`` re-encodes them identically.
    """
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        image.colorspace_settings.name = "sRGB" if map_type in SRGB_SOURCE_MAP_TYPES else "Non-Color"
        return export_pack.read_image_pixels(image)
    finally:
        try:
            bpy.data.images.remove(image)
        except Exception:  # pragma: no cover - Blender-only cleanup
            pass


def _fallback_row_sources(row, spec, cache):
    """Load each set/tile/variant once for fallback validation and composition."""
    sources = {}
    for source in row.sources:
        if source in row.missing:
            continue
        path = (spec.sources.get(source) or {}).get(row.tile, "")
        key = (source, path)
        if key not in cache:
            map_type, _variant = export_pack.parse_source_key(source)
            cache[key] = _load_source_array(path, map_type)
        sources[source] = cache[key]
    return sources


def _coverage_provider(project):
    """``coverage_for(spec, tile, width, height) -> HxW bool mask | None`` for one export.

    The Dilation Infinite / Distance padding modes stretch UV island borders outward,
    so they need to know where the islands ARE: the union of the undilated low-mesh
    UV coverage of every bake group in the texture set, rasterized at the output
    size (the backend dilates after its resize) and restricted to the tile being
    written. Bottom-up, the same order as the loaded planes. Memoized per
    (set, tile, size) because every output of a set shares one mask.
    """
    from . import export  # noqa: PLC0415 -- lazy: bpy-heavy

    cache: dict[tuple[str, str, int, int], object] = {}
    groups_by_name = {
        str(getattr(group, "name", "") or ""): group
        for group in (getattr(project, "groups", None) or ())
    }

    def coverage_for(spec, tile, width, height):
        key = (str(getattr(spec, "key", "")), str(tile or ""), int(width), int(height))
        if key in cache:
            return cache[key]
        tile_text = str(tile or "").strip()
        udim_tile = 0
        if tile_text and tile_text != UNTILED:
            try:
                udim_tile = int(tile_text)
            except ValueError:
                udim_tile = 0
        union = None
        for name in getattr(spec, "group_names", ()) or ():
            group = groups_by_name.get(str(name))
            if group is None:
                continue
            mask = export.rasterize_group_low_uv_mask(group, int(width), int(height), udim_tile=udim_tile)
            if mask is None:
                continue
            union = mask if union is None else (union | mask)
        cache[key] = union
        return union

    return coverage_for


def _dilate_fallback_output(composed, row, spec, coverage_for) -> tuple:
    """``(composed, warning)``: the numpy fallback's Dilation Infinite / Distance.

    Mirrors what the backend does after composing: every uncovered texel takes the
    nearest island's colour, either everywhere or out to ``padding_size`` texels.
    The fallback never resizes, so the coverage is rasterized at the source size.
    """
    height, width = int(composed.shape[0]), int(composed.shape[1])
    reason = ""
    mask = None
    try:
        mask = coverage_for(spec, row.tile, width, height)
    except Exception as error:
        reason = str(error)
    if mask is None or tuple(getattr(mask, "shape", ())) != (height, width):
        detail = f" ({reason})" if reason else ""
        return composed, (
            f"{row.filename}: padding skipped: no UV coverage could be rasterized for this "
            f"texture set{detail}; left as baked"
        )
    return export_pack.dilate_composed(composed, mask, row.padding_mode, row.padding_size), ""


def _validate_fallback_export(rows, specs, cache):
    """Refuse unsupported operations before the fallback writes any output.

    Blender can encode the composed source pixels and (since padding grew a numpy
    twin, see export_pack.dilate_composed) dilate them, but resize/filter and DDS
    belong to the backend. Validate actual loaded dimensions, including every
    UDIM tile, and reuse these arrays during composition.
    """
    for row in rows:
        if row.format_id == constants.IMAGE_FORMAT_DDS:
            raise export_pack.ExportPackError(
                f"'{row.filename}': DDS requires the Fyr texture exporter, which is unavailable. "
                "Restore the bundled backend, or choose PNG, TGA, TIFF or EXR."
            )

    for row in rows:
        spec = specs.get(row.set_key)
        if spec is None:
            continue
        try:
            sources = _fallback_row_sources(row, spec, cache)
        except Exception as error:
            raise export_pack.ExportPackError(f"'{row.filename}': {error}") from error
        target = (int(row.width), int(row.height))
        for source, array in sources.items():
            actual = (int(array.shape[1]), int(array.shape[0]))
            if min(target) > 0 and actual != target:
                raise export_pack.ExportPackError(
                    f"'{row.filename}': resizing {source_display_label(source)} from "
                    f"{actual[0]}x{actual[1]} to {target[0]}x{target[1]} requires the Fyr "
                    "texture exporter, which is unavailable. Restore the bundled backend, "
                    "or set Size to the source resolution."
                )


def _open_directory(directory: str) -> bool:
    path = str(directory or "").strip()
    if not path or not os.path.isdir(path):
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606 -- the shell handler is the point
        elif sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", path])
        else:
            import subprocess

            subprocess.Popen(["xdg-open", path])
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Mesh export
# ---------------------------------------------------------------------------


def _deselect_all_in_view_layer(context) -> None:
    view_layer_objects = getattr(getattr(context, "view_layer", None), "objects", None)
    try:
        objects = list(view_layer_objects or ())
    except TypeError:
        return
    for obj in objects:
        try:
            obj.select_set(False)
        except Exception:
            pass


def _export_set_objects(project, spec: ExportSetSpec):
    """Resolve the same low meshes for destination planning and export."""
    from . import export

    objects = export._texture_set_low_objects(project, spec.key)
    if not objects:
        # An implicit set is a bake group, whose lows are not reachable by set key.
        from . import project_structure

        seen: set[str] = set()
        objects = []
        for group in getattr(project, "groups", []) or ():
            if str(getattr(group, "name", "") or "").strip() not in spec.group_names:
                continue
            # The group's Fyr Low collection, or its low slots when it has none.
            for obj in project_structure.group_low_mesh_objects(group):
                if obj.name not in seen:
                    seen.add(obj.name)
                    objects.append(obj)
    return objects


def _export_mesh_path(spec: ExportSetSpec, directory: Path, mesh_format: str) -> Path:
    extension = constants.MESH_EXPORT_EXTENSIONS.get(mesh_format, ".fbx")
    return Path(directory) / f"{spec.display_name}{extension}"


def _export_destinations(project, settings, rows, specs, directory):
    paths = [row.path for row in rows if not row.skipped]
    if bool(getattr(settings, "export_mesh", False)):
        mesh_format = str(getattr(settings, "mesh_format", constants.MESH_EXPORT_FBX))
        paths.extend(
            _export_mesh_path(spec, directory, mesh_format)
            for spec in specs.values() if _export_set_objects(project, spec)
        )
    return paths


def _export_set_meshes(context, project, spec: ExportSetSpec, directory: Path, mesh_format: str) -> str:
    """Write one set's low meshes, restoring selection; return its path or ""."""
    objects = _export_set_objects(project, spec)
    if not objects:
        return ""
    mesh_path = _export_mesh_path(spec, directory, mesh_format)
    mesh_path.parent.mkdir(parents=True, exist_ok=True)

    selected_before = list(getattr(context, "selected_objects", []) or [])
    active_before = getattr(context.view_layer.objects, "active", None)
    try:
        # Not select_all: it only polls in Object Mode and the export dialog can
        # be run from Edit Mode.
        _deselect_all_in_view_layer(context)
        for obj in objects:
            obj.select_set(True)
        context.view_layer.objects.active = objects[0]
        if mesh_format == constants.MESH_EXPORT_OBJ:
            bpy.ops.wm.obj_export(
                filepath=str(mesh_path),
                export_selected_objects=True,
                apply_modifiers=True,
                export_materials=False,
            )
        elif mesh_format == constants.MESH_EXPORT_GLB:
            bpy.ops.export_scene.gltf(
                filepath=str(mesh_path),
                export_format="GLB",
                use_selection=True,
                export_apply=True,
            )
        else:
            bpy.ops.export_scene.fbx(
                filepath=str(mesh_path),
                use_selection=True,
                use_mesh_modifiers=True,
                object_types={"MESH"},
                add_leaf_bones=False,
                bake_anim=False,
                path_mode="AUTO",
            )
    finally:
        try:
            _deselect_all_in_view_layer(context)
            for obj in selected_before:
                try:
                    obj.select_set(True)
                except ReferenceError:
                    pass
            context.view_layer.objects.active = active_before
        except Exception:  # pragma: no cover - Blender-only cleanup
            pass
    return str(mesh_path)


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


def _active_project(context):
    from . import properties

    return properties.get_active_project(getattr(context, "scene", None))


class MASTER_BAKER_OT_export_include_all_sets(bpy.types.Operator):
    bl_idname = "master_baker.export_include_all_sets"
    bl_label = "Include All"
    bl_description = "Include every texture set of this project in the export"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        project = _active_project(context)
        settings = active_export_settings(project) if project is not None else None
        if settings is None:
            return {"CANCELLED"}
        settings.excluded_texture_sets.clear()
        return {"FINISHED"}


class MASTER_BAKER_OT_export_toggle_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.export_toggle_texture_set"
    bl_label = "Toggle Texture Set"
    bl_description = "Include or exclude this texture set from the export"
    bl_options = {"INTERNAL"}

    set_key: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project(context)
        settings = active_export_settings(project) if project is not None else None
        key = str(self.set_key or "").strip()
        if settings is None or not key:
            return {"CANCELLED"}
        for index, item in enumerate(settings.excluded_texture_sets):
            if str(getattr(item, "name", "") or "").strip() == key:
                settings.excluded_texture_sets.remove(index)
                return {"FINISHED"}
        settings.excluded_texture_sets.add().name = key
        return {"FINISHED"}


class MASTER_BAKER_OT_export_rename_texture_set(bpy.types.Operator):
    bl_idname = "master_baker.export_rename_texture_set"
    bl_label = "Rename Texture Set"
    bl_description = (
        "Rename this texture set without leaving the export dialog. "
        "A bake group that never joined a set gets its own named set"
    )
    bl_options = {"INTERNAL"}

    set_key: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})
    implicit: bpy.props.BoolProperty(name="Implicit", default=False, options={"HIDDEN"})
    new_name: bpy.props.StringProperty(name="Name", default="")

    def invoke(self, context, event):
        self.new_name = str(self.set_key or "").strip()
        return context.window_manager.invoke_props_dialog(self, width=300)

    def execute(self, context):
        project = _active_project(context)
        settings = active_export_settings(project) if project is not None else None
        old_key = str(self.set_key or "").strip()
        new_name = str(self.new_name or "").strip()
        if project is None or settings is None or not old_key:
            return {"CANCELLED"}
        if not new_name:
            self.report({"ERROR"}, "Texture set name cannot be empty")
            return {"CANCELLED"}
        if new_name == old_key:
            return {"CANCELLED"}

        if self.implicit:
            # The "set" is a lone bake group: naming it assigns the group to a
            # real texture set, exactly what the group editor's picker does.
            result = bpy.ops.master_baker.assign_texture_set(name=new_name, group_name=old_key)
            if "FINISHED" not in result:
                return {"CANCELLED"}
        else:
            # Renamed directly rather than via master_baker.rename_texture_set:
            # MasterBakerTextureSet.name syncs member groups on assignment, which
            # makes that operator's own group loop find zero matches and report a
            # false "not found" error after the rename already happened. Update
            # any stragglers first, then the set item; neither step depends on
            # the other having run.
            for group in getattr(project, "groups", []) or ():
                if str(getattr(group, "texture_set_name", "") or "").strip() == old_key:
                    group.texture_set_name = new_name
            for texture_set in getattr(project, "texture_sets", []) or ():
                if str(getattr(texture_set, "name", "") or "").strip() == old_key:
                    texture_set.name = new_name

        # Keep the include/exclude choice and per-set overrides attached.
        for item in settings.excluded_texture_sets:
            if str(getattr(item, "name", "") or "").strip() == old_key:
                item.name = new_name
        rename_set_override(settings, old_key, new_name)
        if str(getattr(settings, "active_export_target", "") or "").strip() == old_key:
            settings.active_export_target = new_name
        return {"FINISHED"}


class MASTER_BAKER_OT_export_select_target(bpy.types.Operator):
    bl_idname = "master_baker.export_select_target"
    bl_label = "Select Export Target"
    bl_description = "Edit Global export settings or overrides for this texture set"
    bl_options = {"INTERNAL"}

    set_key: bpy.props.StringProperty(name="Texture Set", default="", options={"HIDDEN"})

    def execute(self, context):
        project = _active_project(context)
        settings = active_export_settings(project) if project is not None else None
        if settings is None:
            return {"CANCELLED"}
        key = str(self.set_key or "").strip()
        settings.active_export_target = key
        if key:
            ensure_set_override(settings, key)
        return {"FINISHED"}


class MASTER_BAKER_OT_export_open_folder(bpy.types.Operator):
    bl_idname = "master_baker.export_open_folder"
    bl_label = "Open Export Folder"
    bl_description = "Open the folder the textures were exported to"

    directory: bpy.props.StringProperty(name="Directory", subtype="DIR_PATH", default="", options={"HIDDEN"})

    def execute(self, context):
        target = str(self.directory or "").strip()
        if not target:
            project = _active_project(context)
            settings = active_export_settings(project) if project is not None else None
            if settings is not None:
                try:
                    target = str(resolve_export_dir(project, settings))
                except Exception:
                    target = ""
        if not _open_directory(target):
            self.report({"WARNING"}, f"Could not open {target or 'the export folder'}")
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_confirm_export_overwrite(bpy.types.Operator):
    bl_idname = "master_baker.confirm_export_overwrite"
    bl_label = "Replace Existing Export Files?"
    bl_description = "Replace the listed existing files with this export"
    bl_options = {"INTERNAL"}

    snapshot: bpy.props.StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"})
    skip_bake: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"})
    show_all_files: bpy.props.BoolProperty(name="Show All Files", default=False, options={"SKIP_SAVE"})

    def invoke(self, context, event):
        self.show_all_files = False
        return context.window_manager.invoke_props_dialog(
            self, width=650, confirm_text="Replace Files", cancel_default=True,
        )

    def draw(self, context):
        paths = export_overwrite.replacement_paths(self.snapshot)
        layout = self.layout
        layout.label(text=f"{len(paths)} existing file{'' if len(paths) == 1 else 's'} will be replaced.", icon="ERROR")
        layout.label(text="Any edits to these files will be lost.")
        listing = layout.box().column(align=True)
        shown = paths if self.show_all_files else paths[:10]
        previous_parent = None
        for path in shown:
            if path.parent != previous_parent:
                listing.label(text=str(path.parent), icon="FILE_FOLDER")
                previous_parent = path.parent
            listing.label(text=path.name, icon="FILE")
        if len(paths) > 10:
            layout.prop(self, "show_all_files", text=f"Show All {len(paths)} Files")

    def execute(self, context):
        if not self.snapshot:
            return {"CANCELLED"}
        return bpy.ops.master_baker.export_textures(
            "EXEC_DEFAULT", skip_bake=self.skip_bake, overwrite_snapshot=self.snapshot,
        )


class MASTER_BAKER_OT_export_textures(bpy.types.Operator):
    bl_idname = "master_baker.export_textures"
    bl_label = "Export Textures"
    bl_description = "Pack and export the baked maps through an output template"

    #: Display-only. Skipped outputs are the normal case (a template covers more
    #: maps than any one project bakes), so they are folded into one summary line
    #: unless the user asks to see them.
    show_skipped: bpy.props.BoolProperty(
        name="Show Skipped",
        default=False,
        description="List every output that will not be written, with the reason",
        options={"SKIP_SAVE"},
    )

    #: Set on the re-entry that runs after "Bake Missing Maps First" has baked, so
    #: the second pass packs the fresh outputs without kicking off another bake.
    #: Never persisted -- a stale True would suppress baking on a normal export.
    skip_bake: bpy.props.BoolProperty(
        default=False,
        options={"SKIP_SAVE", "HIDDEN"},
    )

    # Set only by the explicit replacement dialog; never saved with the project.
    overwrite_snapshot: bpy.props.StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return _active_project(context) is not None

    # -- dialog ------------------------------------------------------------

    def invoke(self, context, event):
        self.overwrite_snapshot = ""
        project = _active_project(context)
        if project is None:
            self.report({"ERROR"}, "Create a bake project first")
            return {"CANCELLED"}
        settings = active_export_settings(project)
        if settings is not None:
            # Seed the dropdown from the persisted name so the dialog reopens on
            # the template the user actually chose, not on enum index 0.
            name = resolve_template_name(settings)
            if name:
                try:
                    settings.template_enum = name
                except (TypeError, ValueError):
                    pass
                # Only persist the name when it IS the artist's choice. When the
                # chosen template cannot be loaded (invalidated by a newer build's
                # validation, hand-edited, half-synced from cloud storage), this
                # used to write the default over their stored choice, so a project
                # set to a 4-output game template silently became "Mesh Maps (raw)"
                # in the .blend -- 28 files into their content folder, and the
                # dialog reopening on the default as if they had picked it. Keep
                # the stored name so the choice comes back when the file does.
                if _stored_template_is_available(settings):
                    settings.template = name
        # The props-dialog title is painted with no icon, and the popup API
        # has no icon argument. An empty title skips that label so draw() can
        # put the picture icon on the header row.
        return context.window_manager.invoke_props_dialog(
            self, width=1080, title="", confirm_text="Export",
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_decorate = False
        self._draw_title(layout)
        project = _active_project(context)
        settings = active_export_settings(project) if project is not None else None
        if project is None or settings is None:
            layout.label(text="No bake project is active", icon="ERROR")
            return

        tabs = layout.row(align=True)
        tabs.scale_y = 1.35
        tabs.prop(settings, "dialog_tab", expand=True)
        layout.separator(factor=0.45)
        tab = str(getattr(settings, "dialog_tab", constants.EXPORT_TAB_SETTINGS))

        try:
            directory = str(resolve_export_dir(project, settings))
        except Exception:
            directory = ""
        template, rows, error = compute_rows(project, settings, directory=directory)
        if error:
            layout.label(text=error, icon="ERROR")
            return

        # The rows below are the SUBSTITUTE template's, which is a different set of
        # files in a different naming scheme. Say so before the artist presses Export.
        unavailable = unavailable_template_message(settings)
        if unavailable:
            box = layout.box()
            box.label(text=unavailable, icon="ERROR")

        if tab == constants.EXPORT_TAB_EXPORT_LIST:
            self._draw_export_list_tab(layout, directory, rows)
        else:
            self._draw_settings_tab(layout, project, settings, rows, directory)

        exportable = count_exportable(rows)
        layout.separator(factor=0.35)
        footer = layout.row()
        footer.alignment = "LEFT"
        footer.label(
            text=(
                f"{exportable} texture{'' if exportable == 1 else 's'} will be exported to "
                f"{shorten_path(directory, 64) or '(no output folder)'}"
            ),
            icon="INFO",
        )

    def _draw_title(self, layout):
        # The dialog inserts half a row of space before operator properties.
        # Pull the header back up so it sits with the close button.
        layout.separator(factor=-0.5)
        header = layout.row()
        header.alignment = "LEFT"
        header.label(text="Export Textures", icon="IMAGE_DATA")
        layout.separator(factor=0.2, type="LINE")

    # -- shared drawing helpers -------------------------------------------

    #: Label column of the settings form. Wide enough for "Output Directory" plus
    #: its icon, and shared so every value lines up.
    _FORM_LABEL = 0.30
    #: Share of the space after the label used by Size / Filter / Padding / Format.
    #: The rest of that row is where Bit Depth sits, so these dropdowns line up.
    _VALUE_FRACTION = 0.38

    @staticmethod
    def _hint(column, text):
        row = column.row()
        row.enabled = False
        row.label(text=text)

    @classmethod
    def _form_slots(cls, parent, factor=None, align=True):
        split = parent.split(factor=cls._FORM_LABEL if factor is None else factor, align=align)
        return split.row(align=align), split.row(align=align)

    @classmethod
    def _wide_field(cls, column, data, prop, text, icon, placeholder=None):
        """Icon + label, then a value that uses the rest of the row."""
        label, field = cls._form_slots(column.row(align=True))
        label.label(text=text, icon=icon)
        kwargs = {"text": ""}
        if placeholder is not None:
            kwargs["placeholder"] = placeholder
        field.prop(data, prop, **kwargs)
        return field

    @classmethod
    def _half_field(cls, column, data, prop, text, icon):
        """Icon + label, then a value only as wide as the Format dropdown."""
        label, rest = cls._form_slots(column.row(align=True))
        label.label(text=text, icon=icon)
        value, _rest = cls._form_slots(rest, factor=cls._VALUE_FRACTION)
        value.prop(data, prop, text="")

    @classmethod
    def _format_depth_row(cls, column, settings):
        label, rest = cls._form_slots(column.row(align=True))
        label.label(text="Format", icon="IMAGE_DATA")
        value, depth = cls._form_slots(rest, factor=cls._VALUE_FRACTION)
        value.prop(settings, "file_format_override", text="")
        depth_label, depth_value = cls._form_slots(depth, factor=0.42)
        depth_label.label(text="Bit Depth", icon="MESH_CYLINDER")
        depth_value.prop(settings, "bit_depth_override", text="")

    @staticmethod
    def _sidebar_gap(entry_count, *, editing_set, show_padding_size, show_dds):
        """Push Include All to the bottom of the texture-set column.

        Blender columns size to their content, so the shorter sidebar has to
        insert the gap explicitly. The factor is a fraction of the column width
        (see UILayout.separator) and was tuned for this dialog.
        """
        if editing_set:
            right_rows = 6.0 + (1.0 if show_padding_size else 0.0)
        else:
            right_rows = 19.0 + (1.0 if show_padding_size else 0.0) + (2.0 if show_dds else 0.0)
        left_rows = 2.0 + max(entry_count, 1)
        # uiItemS treats factor as a multiple of one UI unit (~one text row).
        return max(0.0, (right_rows - left_rows) * 2.05)

    # -- Settings tab ------------------------------------------------------

    def _draw_settings_tab(self, layout, project, settings, rows, directory):
        split = layout.split(factor=0.30)
        active_target = str(getattr(settings, "active_export_target", "") or "")
        editing_set = active_target.strip()
        entries = collect_export_sets(project)
        padding_owner = settings if not editing_set else find_set_override(settings, editing_set)
        show_padding_size = (
            padding_owner is not None
            and str(getattr(padding_owner, "padding_mode", "")) == constants.EXPORT_PADDING_DISTANCE
        )
        format_override = str(getattr(settings, "file_format_override", "") or "")
        show_dds = (not editing_set) and (
            format_override == constants.IMAGE_FORMAT_DDS
            or any(str(getattr(row, "format_id", "") or "") == constants.IMAGE_FORMAT_DDS for row in rows or ())
        )

        side = split.column().box().column()
        side.label(text="Texture Sets", icon="GRID")
        listing = side.column(align=True)
        global_selected = active_target == constants.EXPORT_TARGET_GLOBAL
        select_global = listing.operator(
            "master_baker.export_select_target",
            text="Global settings",
            icon="WORLD",
            depress=global_selected,
        )
        select_global.set_key = constants.EXPORT_TARGET_GLOBAL

        if not entries:
            listing.label(text="No bake groups yet", icon="INFO")
        for key, display, implicit, _groups in entries:
            included = set_is_included(settings, key)
            selected = active_target == key
            row = listing.row(align=True)
            toggle = row.operator(
                "master_baker.export_toggle_texture_set",
                text="",
                icon="CHECKBOX_HLT" if included else "CHECKBOX_DEHLT",
                emboss=False,
            )
            toggle.set_key = key
            label = display if not implicit else f"{display} (group)"
            select = row.operator(
                "master_baker.export_select_target",
                text=label,
                depress=selected,
                **ui_utils._icon_kwargs("texture_set", "OUTLINER_COLLECTION"),
            )
            select.set_key = key
            rename = row.operator(
                "master_baker.export_rename_texture_set",
                text="",
                icon="GREASEPENCIL",
                emboss=False,
            )
            rename.set_key = key
            rename.implicit = implicit

        gap = self._sidebar_gap(
            len(entries),
            editing_set=bool(editing_set),
            show_padding_size=show_padding_size,
            show_dds=show_dds,
        )
        if gap:
            side.separator(factor=gap)
        else:
            side.separator(factor=0.35)
        # An action, not another row of the list, so it stays a real button.
        side.operator("master_baker.export_include_all_sets", text="Include All", icon="ADD")

        right = split.column()
        right.use_property_decorate = False
        if editing_set:
            right.label(
                text=editing_set,
                **ui_utils._icon_kwargs("texture_set", "OUTLINER_COLLECTION"),
            )
        else:
            right.label(text="General Export Parameters", icon="SETTINGS")
            self._hint(right, "Configure output paths, file format and texture export options.")

        params = right.column()
        params.use_property_decorate = False
        params.separator(factor=0.35)

        if not editing_set:
            # Ghost text inside the field (Blender 4.1+): an empty field means "use
            # the project's exports subfolder", so show that folder as the placeholder.
            self._wide_field(
                params,
                settings,
                "output_dir",
                "Output Directory",
                "FILE_FOLDER",
                placeholder=shorten_path(directory, 64),
            )
            template_name = resolve_template_name(settings)
            template_field = self._wide_field(
                params, settings, "template_enum", "Output Template", "FILE_BLANK",
            )
            # Jump to the output-template editor in the add-on preferences. Sits next
            # to the selector so editing the chosen template is one click away; the
            # operator preloads this template into the editor's staging buffer.
            template_field.operator(
                "master_baker.open_template_editor", text="", icon="TOOL_SETTINGS",
            ).template_name = template_name

            params.separator(factor=0.45)
            self._format_depth_row(params, settings)
            self._half_field(params, settings, "size", "Size", "PIVOT_BOUNDBOX")
            self._half_field(params, settings, "resize_filter", "Filter", "FILTER")
            self._half_field(params, settings, "padding_mode", "Padding", "SELECT_SET")
            if show_padding_size:
                self._half_field(params, settings, "padding_size", "Padding Size", "SELECT_SET")
            if show_dds:
                self._wide_field(params, settings, "dds_compression", "DDS Compression", "IMAGE_DATA")
                params.prop(settings, "dds_generate_mips", text="Generate Mipmaps")

            params.separator(factor=0.55)
            params.prop(settings, "bake_missing_maps", text="Bake Missing Maps First")
            hint = params.row()
            hint.enabled = False
            hint.separator(factor=1.35)
            hint.label(text="Generate any missing maps before exporting.")

            params.separator(factor=0.7)
            mesh_box = params.box()
            mesh_box.label(text="Mesh", icon="GEOMETRY_NODES")
            self._hint(mesh_box, "Export the low or high poly mesh alongside your textures.")
            mesh_box.separator(type="LINE")
            mesh_box.prop(settings, "export_mesh", text="Export Mesh")
            self._wide_field(mesh_box, settings, "mesh_format", "Mesh Format", "MESH_DATA")
        else:
            # Read-only lookup: draw must not resize set_overrides (a
            # CollectionProperty add mid-layout is the crash class noted in the
            # template editor). export_select_target creates the row.
            override = padding_owner
            if override is None:
                params.label(text="Select this texture set in the list to edit its settings", icon="INFO")
                return
            self._half_field(params, override, "size", "Size", "PIVOT_BOUNDBOX")
            self._half_field(params, override, "resize_filter", "Filter", "FILTER")
            self._half_field(params, override, "padding_mode", "Padding", "SELECT_SET")
            if show_padding_size:
                self._half_field(params, override, "padding_size", "Padding Size", "SELECT_SET")

    # -- Export List tab ---------------------------------------------------

    def _draw_export_list_tab(self, layout, directory, rows):
        problems = alert_messages(rows)
        if problems:
            alert_box = layout.box().column(align=True)
            alert_box.alert = True
            for message in problems[:8]:
                alert_box.label(text=message, icon="ERROR")
            if len(problems) > 8:
                alert_box.label(text=f"+{len(problems) - 8} more problems")
            layout.separator()

        destination = layout.row()
        destination.enabled = False
        destination.label(text=shorten_path(directory, 96) or "(no output folder)", icon="FILE_FOLDER")
        layout.separator()

        writing = [row for row in rows if not row.skipped]
        skipped = [row for row in rows if row.skipped]

        if not writing:
            empty = layout.box().column()
            empty.label(text="Nothing will be exported. Bake the source maps first", icon="INFO")
        for set_name, set_rows in group_rows_by_set(writing):
            box = layout.box().column(align=True)
            head = box.row(align=True)
            head.label(text=set_name, icon="OUTLINER_COLLECTION")
            tally = head.row()
            tally.alignment = "RIGHT"
            tally.enabled = False
            tally.label(text=f"{len(set_rows)} file{'' if len(set_rows) == 1 else 's'}")
            box.separator(factor=0.4)
            for row in set_rows:
                notes = fill_notes(row)
                line = box.split(factor=0.62)
                line.label(text=row.filename, icon="INFO" if notes else "CHECKMARK")
                detail = line.row()
                detail.alignment = "RIGHT"
                detail.enabled = False
                detail.label(text=row_detail(row))
                # The row is written; these say which channels are constants.
                for note in notes:
                    note_line = box.row()
                    note_line.enabled = False
                    note_line.label(text=note, icon="BLANK1")
            layout.separator(factor=0.5)

        if skipped:
            layout.separator(factor=0.5)
            summary = layout.row(align=True)
            summary.label(
                text=f"{len(skipped)} output{'' if len(skipped) == 1 else 's'} skipped (source maps not baked)",
                icon="INFO",
            )
            toggle = summary.row()
            toggle.alignment = "RIGHT"
            toggle.prop(
                self,
                "show_skipped",
                text="Show Skipped",
                toggle=True,
                icon="HIDE_OFF" if self.show_skipped else "HIDE_ON",
            )
            if self.show_skipped:
                for set_name, set_rows in group_rows_by_set(skipped):
                    box = layout.box().column(align=True)
                    box.enabled = False
                    box.label(text=set_name, icon="OUTLINER_COLLECTION")
                    for row in set_rows:
                        line = box.split(factor=0.62)
                        line.label(text=row.filename, icon="BLANK1")
                        reason = line.row()
                        reason.alignment = "RIGHT"
                        reason.label(text=skip_reason(row))

        layout.separator()
        note = layout.row()
        note.enabled = False
        note.label(
            text="Sources come from the latest bake, at the bit depth it wrote.",
            icon="INFO",
        )

    # -- execution ---------------------------------------------------------

    def execute(self, context):
        project = _active_project(context)
        settings = active_export_settings(project) if project is not None else None
        if project is None or settings is None:
            self.report({"ERROR"}, "Create a bake project first")
            return {"CANCELLED"}

        included = [
            key
            for key, _display, _implicit, _groups in collect_export_sets(project)
            if set_is_included(settings, key)
        ]
        if not included:
            self.report({"ERROR"}, "Include at least one texture set before exporting")
            return {"CANCELLED"}

        try:
            directory = resolve_export_dir(project, settings)
        except Exception as error:
            self.report({"ERROR"}, f"Output directory could not be resolved: {error}")
            return {"CANCELLED"}

        template, rows, error = compute_rows(project, settings, keys=included, directory=str(directory))
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        # A substituted template writes a different set of files under different
        # names. Warn on the way out too: the dialog notice above is not there for a
        # scripted export, and this must never be silent.
        substituted = unavailable_template_message(settings)
        if substituted:
            self.report({"WARNING"}, substituted)

        # Validate before Bake Missing Maps First, directory creation or either packer.
        # Recheck here too: direct execution must enforce the same guard as the dialog.
        source_collisions = find_bake_source_collisions(rows, tracked_bake_paths(project))
        if source_collisions:
            message = bake_source_collision_message(source_collisions[0][0])
            project.last_status_message = message
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        collisions = find_collisions(rows)
        if collisions:
            first, second = collisions[0]
            self.report(
                {"ERROR"},
                (
                    f"Two template outputs expand to the same file '{first.filename}': "
                    f"output #{first.output_index + 1} and output #{second.output_index + 1}. "
                    "Give one of them a distinct filename or map label."
                ),
            )
            return {"CANCELLED"}

        # Bake Missing Maps First: if the template needs enabled maps this project
        # has not baked yet, bake exactly those and re-run the export when the bake
        # finishes. skip_bake guards the re-entry so this cannot loop. Anything the
        # bake cannot create (an occurrence the stack lacks) stays skipped below.
        if bool(getattr(settings, "bake_missing_maps", False)) and not self.skip_bake:
            missing_types = missing_bakeable_map_types(project, rows)
            if missing_types:
                from . import operators

                return operators.bake_then_export(self, context, project, missing_types)

        specs = {spec.key: spec for spec in build_set_specs(project, included)}
        try:
            paths = _export_destinations(project, settings, rows, specs, directory)
            scope = str(project.as_pointer() if hasattr(project, "as_pointer") else id(project))
            snapshot = export_overwrite.replacement_snapshot(paths, scope=scope)
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, f"Cannot inspect export destinations: {error}")
            return {"CANCELLED"}
        if snapshot and snapshot != str(getattr(self, "overwrite_snapshot", "") or ""):
            if bpy.app.background or getattr(context, "window", None) is None:
                self.report({"ERROR"}, "Existing export files require replacement confirmation. Open Export Textures to review them.")
                return {"CANCELLED"}
            return bpy.ops.master_baker.confirm_export_overwrite(
                "INVOKE_DEFAULT", snapshot=snapshot, skip_bake=self.skip_bake,
            )
        # Consent belongs to this attempt, even if packing fails partway through.
        self.overwrite_snapshot = ""

        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as os_error:
            self.report({"ERROR"}, f"Cannot write to {directory}: {os_error}")
            return {"CANCELLED"}

        outputs = list((template or {}).get("outputs") or ())
        pending = [row for row in rows if not row.skipped]
        # Both halves name the file they are about: "skipped: Opacity not baked"
        # on its own never said WHICH output was dropped.
        warnings = skipped_messages(rows)
        skipped_count = len(warnings)
        warnings.extend(fill_messages(pending))

        window_manager = context.window_manager
        try:
            window_manager.progress_begin(0, max(len(pending), 1))
        except Exception:
            window_manager = None

        written = 0
        cache: dict[tuple[str, str], object] = {}
        from . import export_backend_pack  # noqa: PLC0415 -- lazy: keeps headless imports free of numpy side paths

        use_backend = False
        try:
            use_backend = export_backend_pack.backend_pack_available()
        except Exception:
            use_backend = False

        dds_pending = [
            row for row in pending if str(getattr(row, "format_id", "") or "").upper() == constants.IMAGE_FORMAT_DDS
        ]
        # UV coverage for the padding modes, on both routes. Without it the backend
        # left every "Dilation ..." output exactly as baked and said so only in a
        # warning that never reached the artist.
        coverage_for = _coverage_provider(project)
        try:
            if use_backend and pending:
                # Default packer: compose/resize/encode in the backend (D6). The
                # Blender can still encode at source size if the capability is
                # missing or the backend pack raises; validate its limits first.
                try:
                    written, pack_warnings = export_backend_pack.pack_rows_with_backend(
                        pending,
                        outputs=outputs,
                        specs=specs,
                        load_source=_load_source_array,
                        coverage_source=coverage_for,
                    )
                    warnings.extend(pack_warnings)
                    if window_manager is not None:
                        try:
                            window_manager.progress_update(len(pending))
                        except Exception:
                            pass
                except Exception as backend_error:
                    if dds_pending:
                        self.report(
                            {"ERROR"},
                            f"Backend pack failed for DDS export: {backend_error}",
                        )
                        return {"CANCELLED"}
                    warnings.append(f"Backend pack failed, falling back to numpy: {backend_error}")
                    use_backend = False

            if not use_backend:
                try:
                    _validate_fallback_export(pending, specs, cache)
                except export_pack.ExportPackError as fallback_error:
                    message = f"Export cancelled: {fallback_error}"
                    project.last_status_message = message
                    self.report({"ERROR"}, message)
                    return {"CANCELLED"}
                for index, row in enumerate(pending):
                    spec = specs.get(row.set_key)
                    if spec is None:
                        continue
                    # Channels whose source was never baked become ordinary
                    # constant slots carrying that map's neutral value, so the
                    # packer has exactly one fill path and the rest of the file
                    # is written from the maps that DO exist.
                    output_def, _fills = export_pack.substitute_missing_sources(
                        outputs[row.output_index], row.missing
                    )
                    try:
                        sources = _fallback_row_sources(row, spec, cache)
                        # compose_output clamps unless the *effective* format is EXR,
                        # so it has to see the override, not the template's own value.
                        # fallback_size only ever applies when EVERY filled channel is
                        # a constant, so nothing else carries a resolution. Any
                        # map-backed slot still decides the size, so passing the set's
                        # resolution here cannot override a real map.
                        composed = export_pack.compose_output(
                            sources,
                            dict(output_def, format=row.format_id),
                            fallback_size=(int(row.width), int(row.height)),
                        )
                        if row.padding_mode != constants.EXPORT_PADDING_NONE:
                            composed, padding_warning = _dilate_fallback_output(
                                composed, row, spec, coverage_for
                            )
                            if padding_warning:
                                warnings.append(padding_warning)
                        export_pack.save_composed_image(
                            composed,
                            row.path,
                            row.format_id,
                            row.bit_depth,
                            row.color_space,
                        )
                        written += 1
                    except Exception as pack_error:
                        warnings.append(f"{row.filename}: {pack_error}")
                    if window_manager is not None:
                        try:
                            window_manager.progress_update(index + 1)
                        except Exception:
                            pass
        finally:
            cache.clear()
            if window_manager is not None:
                try:
                    window_manager.progress_end()
                except Exception:
                    pass

        meshes = 0
        if bool(getattr(settings, "export_mesh", False)):
            mesh_format = str(getattr(settings, "mesh_format", constants.MESH_EXPORT_FBX))
            for key in included:
                spec = specs.get(key)
                if spec is None:
                    continue
                try:
                    if _export_set_meshes(context, project, spec, directory, mesh_format):
                        meshes += 1
                except Exception as mesh_error:
                    warnings.append(f"{spec.display_name} mesh: {mesh_error}")

        # Real warnings first. The skip lines come first in the list, and a
        # "Mesh Maps (raw)" export has easily more than eight of them, so a
        # warning about a file that WAS written -- padding left as baked, an
        # encode error -- was pushed off the end and never seen.
        ordered = warnings[skipped_count:] + warnings[:skipped_count]
        for warning in ordered[:8]:
            self.report({"WARNING"}, warning)
        if len(ordered) > 8:
            self.report({"WARNING"}, f"...and {len(ordered) - 8} more; see the export list")
        if not written and not meshes:
            self.report({"ERROR"}, "Nothing was exported. Bake the source maps first")
            return {"CANCELLED"}

        message = f"Exported {written} texture{'' if written == 1 else 's'}"
        if meshes:
            message += f" and {meshes} mesh{'' if meshes == 1 else 'es'}"
        message += f" to {directory}"
        # Only real drops are counted as skipped; a filled channel is a warning
        # about a file that WAS written, and calling it "skipped" would be a lie.
        extra = len(warnings) - skipped_count
        if skipped_count:
            message += f" ({skipped_count} skipped)"
        elif extra:
            message += f" ({extra} warning{'' if extra == 1 else 's'})"
        try:
            project.last_status_message = message
        except Exception:
            pass
        self.report({"INFO"}, message)
        return {"FINISHED"}


CLASSES = (
    MASTER_BAKER_OT_export_include_all_sets,
    MASTER_BAKER_OT_export_toggle_texture_set,
    MASTER_BAKER_OT_export_rename_texture_set,
    MASTER_BAKER_OT_export_select_target,
    MASTER_BAKER_OT_export_open_folder,
    MASTER_BAKER_OT_confirm_export_overwrite,
    MASTER_BAKER_OT_export_textures,
)


def register():
    from .registration import safe_register_class

    for cls in CLASSES:
        safe_register_class(cls)


def unregister():
    from .registration import safe_unregister_class

    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
