"""Channel packing + image encoding for the Texture Export dialog.

Implements the packer half of `docs/archive/TEXTURE_EXPORT_DIALOG_PLAN.md` (D2 template
schema, D4 "packing runs in the addon (numpy)", section 4 steps 3-4). Two layers
live here and they are deliberately separated:

* **Compositing (pure numpy).** ``compose_output`` turns a bag of freshly baked
  float source maps plus one template *output definition* into a single float32
  RGB/RGBA array. It never imports ``bpy``, so the whole channel-routing contract
  is unit-testable headless (`tests/test_export_pack.py`).
* **Encoding (Blender).** ``save_composed_image`` writes that array to disk
  through a scratch ``bpy.data.images`` datablock. ``bpy`` is imported lazily
  inside the function so importing this module outside Blender stays free.
  ``resolve_format_settings`` is the pure decision function behind it and is unit
  tested on its own.

Row order
---------
Arrays are in **Blender's native bottom-up order**: ``array[0]`` is the bottom
row of the image, matching ``Image.pixels`` reshaped to ``(height, width, 4)``.
Sources read with ``read_image_pixels`` and results written with
``save_composed_image`` round-trip without any flip. Callers that obtain sources
from some other decoder must flip them into this convention first.

Resolution
----------
v1 requires every source of one output to share a resolution. All sources come
from a single bake at a single output size (plan section 4 step 2), so a mismatch
means the caller mixed bakes; resizing is explicitly out of scope and raises
``ExportPackError`` instead of silently resampling. Constant channels carry no
resolution of their own; an output made *only* of constants is sized by
``compose_output``'s ``fallback_size`` argument.

Color management (measured, not guessed)
----------------------------------------
See the long comment above ``save_composed_image`` -- the encoder path was chosen
from measurements against Blender 5.1.1, not from the docs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path

import numpy as np

from . import constants, naming


# --- template schema vocabulary (plan D2) -----------------------------------

#: Output slots of one packed image, in memory order.
CHANNEL_SLOTS = ("R", "G", "B", "A")

CHANNEL_R = "R"
CHANNEL_G = "G"
CHANNEL_B = "B"
CHANNEL_A = "A"
CHANNEL_GRAY = "GRAY"

#: Values accepted for a slot's ``channel`` (which channel of the *source* to read).
SOURCE_CHANNELS = (CHANNEL_R, CHANNEL_G, CHANNEL_B, CHANNEL_A, CHANNEL_GRAY)

#: ``source`` sentinel for a slot filled with a flat value rather than a map.
#: Mirrors ``export_templates.CONSTANT_SOURCE`` (kept as a literal for the same
#: reason ``CHANNEL_SLOTS`` is: this half of the packer imports no addon schema
#: module). It is **not** a map type and never appears in ``referenced_sources``.
CONSTANT_SOURCE = "CONSTANT"
CONSTANT_MIN = 0.0
CONSTANT_MAX = 1.0
CONSTANT_BLACK = 0.0
CONSTANT_GRAY = 0.5
CONSTANT_WHITE = 1.0
#: Value a constant slot takes when it carries no ``constant`` key.
CONSTANT_DEFAULT = CONSTANT_BLACK

# --- neutral fill for a source that was never baked --------------------------
#
# An output whose channels come from four maps used to be dropped whole when ONE
# of them had not been baked: a Unity mask map with AO and roughness on disk but
# no metalness wrote nothing at all, and neither did a base map whose only gap
# was the opacity in its alpha. That is the worst of both worlds -- the artist
# loses the three channels that DO exist, and nothing tells them which file went
# missing.
#
# So a partly-sourced output is written, with the unbaked channels filled by the
# value that makes that channel a no-op downstream. Only map types whose absence
# has an unambiguous "as if it were not there" value are listed here; everything
# else (albedo, roughness, normal, curvature, ...) has no such value and falls
# back to :data:`DEFAULT_FILL_VALUE`, i.e. exactly what the template's own
# ``null`` channel writes. Either way the substitution is reported -- see
# :func:`substitute_missing_sources` -- because a filled channel is a fact about
# the file the artist must be able to see, never a silent guess.
#
# Extend by adding a map type here; nothing else needs to change.

#: Map type -> the value an unbaked channel of that type is filled with, before
#: ``invert``. 0-1 scale, same as every other constant in this module.
NEUTRAL_FILL_VALUES = {
    constants.MAP_MATERIAL_OPACITY: CONSTANT_WHITE,
    constants.MAP_OPACITY: CONSTANT_WHITE,
    constants.MAP_MATERIAL_METALNESS: CONSTANT_BLACK,
    constants.MAP_MATERIAL_EMISSION: CONSTANT_BLACK,
    constants.MAP_AO: CONSTANT_WHITE,
    constants.MAP_CAVITY: CONSTANT_WHITE,
    constants.MAP_THICKNESS: CONSTANT_WHITE,
}

#: Fill for a map type with no documented neutral. Identical to what a ``null``
#: channel slot packs, so the file's shape is the one the template describes.
DEFAULT_FILL_VALUE = CONSTANT_BLACK


@dataclass(frozen=True)
class MissingFill:
    """One channel slot that was filled with a constant instead of a bake.

    ``constant`` is the neutral before ``invert``; ``value`` is what actually
    lands in the texel. ``neutral`` is False when the map type had no documented
    neutral and :data:`DEFAULT_FILL_VALUE` was used -- the caller warns either
    way, but that is the case where the fill is a placeholder rather than a
    no-op.
    """

    slot: str
    source: str
    constant: float
    value: float
    neutral: bool


def neutral_fill_value(source: str) -> float:
    """The pre-invert constant an unbaked ``source`` is filled with.

    Takes a composite source key, so ``AO#1`` fills like ``AO`` -- the neutral is
    a property of the map type, not of which bake of it is missing.
    """

    map_type, _variant = parse_source_key(source)
    return float(NEUTRAL_FILL_VALUES.get(map_type.strip().upper(), DEFAULT_FILL_VALUE))


def has_neutral_fill(source: str) -> bool:
    """True when this source's map type has a documented neutral (not the fallback)."""

    map_type, _variant = parse_source_key(source)
    return map_type.strip().upper() in NEUTRAL_FILL_VALUES


def substitute_missing_sources(output_def: Mapping, missing_sources=()) -> tuple[dict, tuple[MissingFill, ...]]:
    """Rewrite one output so its unbaked channels pack a neutral constant.

    Returns ``(output definition, fills)``. Every slot reading a key listed in
    ``missing_sources`` is replaced by an ordinary ``"source": "CONSTANT"`` slot
    carrying that source's :func:`neutral_fill_value` -- the *same* schema entry
    a template author would write by hand, so there is exactly one fill path in
    the packer and the constant is encoded in the output's declared color space
    like any other constant. ``invert`` is carried over untouched and therefore
    applies to the constant exactly as it would have applied to the pixels
    (``1 - value``).

    The returned definition still references every source that IS available, so
    it keeps its resolution from a real map; only an output whose sources are
    *all* missing degenerates to constants, and the caller skips those rather
    than writing a flat file nobody asked for.

    Slots that read nothing, slots that already carry a constant and sources that
    are present are left byte-identical, so an output with nothing missing comes
    back unchanged with no fills.
    """

    missing = {str(name) for name in (missing_sources or ()) if str(name)}
    definition = dict(output_def or {})
    if not missing:
        return definition, ()

    slots = _slot_definitions(output_def)
    channels = dict((output_def or {}).get("channels") or {})
    fills: list[MissingFill] = []
    for slot in CHANNEL_SLOTS:
        normalized = slots[slot]
        if normalized is None or normalized["constant"] is not None:
            continue
        source = normalized["source"]
        if not source or source not in missing:
            continue
        constant = neutral_fill_value(source)
        invert = bool(normalized["invert"])
        channels[slot] = {
            "source": CONSTANT_SOURCE,
            "channel": CHANNEL_GRAY,
            "invert": invert,
            "constant": constant,
        }
        fills.append(
            MissingFill(
                slot=slot,
                source=source,
                constant=constant,
                value=(1.0 - constant) if invert else constant,
                neutral=has_neutral_fill(source),
            )
        )

    if fills:
        definition["channels"] = channels
    return definition, tuple(fills)


# --- composite source keys (map type + occurrence ordinal) -------------------
#
# A project may hold several bakes of one map type -- three AO, two Curvature.
# A channel addresses one of them by map type plus a 0-based *occurrence
# ordinal* in map-stack order (``docs/MAP_VARIANTS_PLAN.md``). Not by uuid and
# not by variant *name*: a template is a cross-project asset and neither of
# those means anything in the next project.
#
# Occurrence 0 keeps the BARE map type as its key. That is the compatibility
# hinge -- every template written before variants existed, every ``sources``
# dict and every caller that never heard of an ordinal keeps working untouched.

#: Separates a map type from its occurrence ordinal in a composite source key.
VARIANT_SEPARATOR = "#"
#: Occurrence a channel addresses when it carries no ``variant`` key.
DEFAULT_VARIANT = 0

_CHANNEL_INDEX = {CHANNEL_R: 0, CHANNEL_G: 1, CHANNEL_B: 2, CHANNEL_A: 3}

#: Per-output color space (plan D2 ``color_space``).
COLOR_SPACE_SRGB = "SRGB"
COLOR_SPACE_NON_COLOR = "NON_COLOR"
COLOR_SPACES = (COLOR_SPACE_SRGB, COLOR_SPACE_NON_COLOR)

#: Rec.709 luminance weights, used for ``channel: "GRAY"`` on an RGB source.
#: The weights sum to 1.0, so a scalar map that carries the same value in R, G
#: and B degenerates to that value (to within float32 rounding, ~1e-7 -- two
#: orders of magnitude below a 16-bit quantization step).
REC709_LUMA = (0.2126, 0.7152, 0.0722)


class ExportPackError(RuntimeError):
    """A channel-pack or encode step could not be completed.

    Carries ``missing_sources`` when it was raised because ``sources`` did not
    contain a map the template output references, so the caller can decide
    between skipping that output and failing the whole export (plan section 4
    step 1: "warn + skip that output").
    """

    def __init__(self, message: str, *, missing_sources: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.missing_sources = tuple(missing_sources)


# --- composite source keys ---------------------------------------------------


def normalized_variant(value, *, where: str = "'variant'") -> int:
    """Validate one occurrence ordinal: a non-negative ``int``.

    ``bool`` is rejected on purpose -- ``True`` is an ``int`` in Python and
    ``AO#True`` is nobody's intent -- and so are floats and numeric strings: an
    ordinal indexes the map stack, it is not a measurement.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise ExportPackError(
            f"{where} must be a non-negative integer occurrence ordinal, got {value!r}"
        )
    if value < 0:
        raise ExportPackError(f"{where} must be >= 0, got {value}")
    return int(value)


def source_key(map_type: str, variant: int = DEFAULT_VARIANT) -> str:
    """Composite key naming **one bake**: a map type plus its occurrence ordinal.

    ``source_key("AO", 0) == "AO"`` and ``source_key("AO", 1) == "AO#1"``.
    Occurrence 0 deliberately keeps the bare map type, so a caller that knows
    nothing about ordinals produces exactly the keys it always produced.

    An empty map type stays empty (that is the "slot exists but is unassigned"
    state, which addresses no bake and therefore has no ordinal).
    """

    name = str(map_type or "").strip()
    index = normalized_variant(variant, where=f"variant of '{name or '?'}'")
    if not name or index == DEFAULT_VARIANT:
        return name
    return f"{name}{VARIANT_SEPARATOR}{index}"


def parse_source_key(key) -> tuple[str, int]:
    """Inverse of :func:`source_key`: ``"AO#1" -> ("AO", 1)``, ``"AO" -> ("AO", 0)``.

    Total by construction -- anything that is not ``<map type>#<digits>`` comes
    back as ``(the whole string, 0)``, so a caller can always split a key it did
    not build without guarding for garbage.
    """

    text = str(key or "").strip()
    head, separator, tail = text.rpartition(VARIANT_SEPARATOR)
    if not separator or not head or not tail.isdigit():
        return text, DEFAULT_VARIANT
    return head, int(tail)


def channel_variant(channel_def) -> int:
    """The occurrence one *raw* channel entry addresses (:data:`DEFAULT_VARIANT` by default).

    Absent means "the first bake of this type", which is what every template
    written before this existed means and what it must keep meaning.
    """

    if not isinstance(channel_def, Mapping) or "variant" not in channel_def:
        return DEFAULT_VARIANT
    return normalized_variant(channel_def["variant"], where="Channel 'variant'")


def channel_source_key(channel_def) -> str:
    """The composite source key one *raw* channel entry reads.

    ``""`` when it reads no bake at all -- an unassigned slot, or a constant.
    """

    if not isinstance(channel_def, Mapping):
        return ""
    source = str(channel_def.get("source") or "").strip()
    if not source or source.upper() == CONSTANT_SOURCE:
        return ""
    return source_key(source, channel_variant(channel_def))


# --- pure numpy compositing --------------------------------------------------


def _constant_value(raw_value, slot: str) -> float:
    """Validate one slot's flat value. Same bounds the template store enforces."""

    if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
        raise ExportPackError(
            f"Channel slot '{slot}' constant must be a number between "
            f"{CONSTANT_MIN} and {CONSTANT_MAX}, got {raw_value!r}"
        )
    value = float(raw_value)
    if not CONSTANT_MIN <= value <= CONSTANT_MAX:
        raise ExportPackError(
            f"Channel slot '{slot}' constant {value} is outside the "
            f"{CONSTANT_MIN}-{CONSTANT_MAX} range"
        )
    return value


def _normalized_slot(raw, slot: str):
    """Validate one channel-slot definition; ``None`` for an unused slot.

    A slot that *exists* but carries ``"source": ""`` is an unassigned slot (see
    ``export_templates``' schema note): it is returned with an empty ``source``
    rather than as ``None``, because the slot still exists -- that is what decides
    RGB vs RGBA for the ``A`` slot -- and it composites as zeros.

    The returned mapping always carries a ``"constant"`` key: ``None`` for a
    map-backed or unassigned slot, and the flat value for a
    ``"source": "CONSTANT"`` slot. A constant slot reads no image, so its
    ``channel`` is accepted and ignored rather than validated -- the editor writes
    a channel on every entry and it means nothing here.

    ``"source"`` comes back as a **composite source key** (:func:`source_key`),
    so an entry carrying ``"variant": 1`` reads ``AO#1`` and an entry carrying
    none reads ``AO`` -- byte for byte what it read before variants existed. The
    ordinal is also returned on its own as ``"variant"``.
    """

    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ExportPackError(
            f"Channel slot '{slot}' must be a mapping or null, got {type(raw).__name__}"
        )

    source = str(raw.get("source") or "").strip()
    invert = bool(raw.get("invert", False))

    if source.upper() == CONSTANT_SOURCE:
        if "variant" in raw:
            # A constant reads no bake, so there is no occurrence to pick. Same
            # reasoning as 'constant' on a map-backed slot below: silently doing
            # nothing is exactly the accident worth refusing.
            raise ExportPackError(
                f"Channel slot '{slot}' carries a 'variant' but its source is "
                f"{CONSTANT_SOURCE}, which reads no bake"
            )
        return {
            "source": CONSTANT_SOURCE,
            "channel": CHANNEL_GRAY,
            "invert": invert,
            "constant": _constant_value(raw.get("constant", CONSTANT_DEFAULT), slot),
            "variant": DEFAULT_VARIANT,
        }

    if "constant" in raw:
        # Would silently do nothing. The template store rejects it too; failing
        # here keeps a hand-written template from packing something the artist
        # did not ask for.
        raise ExportPackError(
            f"Channel slot '{slot}' carries a 'constant' but its source is "
            f"'{source}', not {CONSTANT_SOURCE}"
        )

    # Omitted ``channel`` means identity routing (source R -> output R). The
    # built-in templates always spell it out; this only covers hand-written JSON.
    channel = str(raw.get("channel") or slot).strip().upper()
    if channel not in SOURCE_CHANNELS:
        raise ExportPackError(
            f"Channel slot '{slot}' requests unknown source channel '{channel}' "
            f"(expected one of {', '.join(SOURCE_CHANNELS)})"
        )

    variant = normalized_variant(raw["variant"], where=f"Channel slot '{slot}' 'variant'") if "variant" in raw else DEFAULT_VARIANT
    return {
        "source": source_key(source, variant),
        "channel": channel,
        "invert": invert,
        "constant": None,
        "variant": variant,
    }


def _slot_definitions(output_def: Mapping) -> dict:
    if not isinstance(output_def, Mapping):
        raise ExportPackError(f"Output definition must be a mapping, got {type(output_def).__name__}")
    channels = output_def.get("channels")
    if not isinstance(channels, Mapping):
        raise ExportPackError("Output definition has no 'channels' mapping")
    return {slot: _normalized_slot(channels.get(slot), slot) for slot in CHANNEL_SLOTS}


def output_uses_alpha(output_def: Mapping) -> bool:
    """True when the output's A slot **exists**, i.e. the file needs 4 channels.

    Deliberately about the slot, not about the assignment: an A slot that is
    present but unassigned still makes the file RGBA, with a zero alpha. The shape
    of the file an artist asked for must not silently change to RGB just because
    the alpha map has not been picked yet -- the artist sees the A chip in the
    editor and the file they get has the channel that chip stands for.
    """

    return _slot_definitions(output_def)["A"] is not None


def referenced_sources(output_def: Mapping) -> tuple[str, ...]:
    """Composite source keys this output reads, in slot order, without duplicates.

    Each entry is a :func:`source_key` -- a bare map type for the first bake of
    that type, ``TYPE#n`` for the n-th. An output asking for ``AO#1`` therefore
    declares a dependency on the *second* AO bake and **not** on AO, which is
    what lets the caller skip the row honestly in a project that has only one.

    Unassigned slots name nothing, so they are skipped: an output with nothing
    assigned references no sources at all. Constant slots name nothing either --
    ``CONSTANT`` is a sentinel, not a bakeable map, and must never reach the
    caller as a map to bake or a file to look up.
    """

    slots = _slot_definitions(output_def)
    ordered: list[str] = []
    for slot in CHANNEL_SLOTS:
        definition = slots[slot]
        if definition is None or definition["constant"] is not None:
            continue
        if not definition["source"]:
            continue
        if definition["source"] not in ordered:
            ordered.append(definition["source"])
    return tuple(ordered)


def constant_slots(output_def: Mapping) -> dict[str, float]:
    """Slot letter -> the value it packs, for every constant slot of this output.

    ``invert`` is already applied, so this is what lands in the texel.
    """

    slots = _slot_definitions(output_def)
    values: dict[str, float] = {}
    for slot in CHANNEL_SLOTS:
        definition = slots[slot]
        if definition is None or definition["constant"] is None:
            continue
        values[slot] = _constant_plane_value(definition)
    return values


def output_has_content(output_def: Mapping) -> bool:
    """True when this output has anything to write: a real source *or* a constant.

    The complement of the "nothing assigned yet, skip the row" test in the export
    dialog. ``referenced_sources`` alone is not that test any more: an
    all-constant output references no source and is still fully determined.
    """

    slots = _slot_definitions(output_def)
    for slot in CHANNEL_SLOTS:
        definition = slots[slot]
        if definition is None:
            continue
        if definition["constant"] is not None or definition["source"]:
            return True
    return False


def _as_source_array(value, source: str) -> np.ndarray:
    try:
        array = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise ExportPackError(f"Source '{source}' is not a numeric array: {exc}") from exc
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ExportPackError(
            f"Source '{source}' must be a HxWx3 or HxWx4 array, got shape {tuple(array.shape)}"
        )
    return array


def _extract_channel(array: np.ndarray, definition: Mapping, source: str) -> np.ndarray:
    channel = definition["channel"]
    if channel == CHANNEL_GRAY:
        weights = np.asarray(REC709_LUMA, dtype=np.float32)
        weights = weights / weights.sum(dtype=np.float32)
        plane = array[:, :, :3] @ weights
    else:
        index = _CHANNEL_INDEX[channel]
        if index >= array.shape[2]:
            raise ExportPackError(
                f"Source '{source}' has {array.shape[2]} channels and cannot supply channel '{channel}'"
            )
        plane = array[:, :, index]

    plane = np.asarray(plane, dtype=np.float32)
    if definition["invert"]:
        # 1 - x after extraction, exactly as the template schema describes. On an
        # unclamped (EXR) output an HDR input can invert to a negative value; that
        # is the definition, not a bug.
        plane = np.float32(1.0) - plane
    return plane


def _constant_plane_value(definition: Mapping) -> float:
    """The value a constant slot packs, with ``invert`` applied.

    ``invert`` on a constant is ``1.0 - value``, the same thing it means for a
    map-backed slot. Both the value and its inverse are inside [0, 1] by
    construction, so no format's clamp can move them.
    """

    value = float(definition["constant"])
    if definition["invert"]:
        value = 1.0 - value
    return value


def _output_is_unclamped(output_def: Mapping) -> bool:
    image_format = str(output_def.get("format") or "").strip().upper()
    return image_format in (constants.IMAGE_FORMAT_EXR, "OPEN_EXR")


def _fallback_resolution(fallback_size) -> tuple[int, int]:
    """``(width, height)`` from the caller -> the ``(rows, cols)`` used internally."""

    if fallback_size is None:
        raise ExportPackError(
            "Every channel of this output is a constant, so nothing carries a "
            "resolution: pass fallback_size=(width, height) to size the image"
        )
    try:
        width, height = (int(fallback_size[0]), int(fallback_size[1]))
    except (TypeError, ValueError, IndexError, KeyError) as exc:
        raise ExportPackError(
            f"fallback_size must be a (width, height) pair, got {fallback_size!r}"
        ) from exc
    if width <= 0 or height <= 0:
        raise ExportPackError(f"fallback_size must be positive, got {width}x{height}")
    return (height, width)


def compose_output(
    sources: Mapping[str, np.ndarray],
    output_def: Mapping,
    *,
    fallback_size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Compose one packed image from baked source maps.

    ``sources`` maps a **composite source key** (:func:`source_key`: a
    ``MAP_TYPE_ITEMS`` identifier, plan D2 ``source``, optionally suffixed with
    an occurrence ordinal) to a float32 ``HxWx4`` array -- linear values for
    color maps, raw data otherwise. ``HxWx3`` sources are accepted; asking such
    a source for its A channel is an error. A key that is not in ``sources``
    raises rather than falling back to another occurrence of the same type.

    ``output_def`` is one entry of a template's ``outputs`` list. Only
    ``channels`` and ``format`` are read here; filename/label/bit depth belong to
    the token engine and the encoder.

    Returns float32 ``HxWx3`` when the A slot is unused and ``HxWx4`` when it is
    filled. Values are clamped to [0, 1] unless ``format`` is EXR, which is left
    unclamped so HDR sources survive. A caller honouring the export settings'
    ``file_format_override`` (plan D5) must therefore pass the *effective* format
    in ``output_def["format"]``, not the template's.

    An unused R/G/B slot (explicit ``null``) contributes zeros, and so does a slot
    that exists but has no map assigned yet (``"source": ""``) -- an in-progress
    output is packed, not refused. An output with *nothing* assigned anywhere is
    still an error here: with no source there is no resolution to allocate. The
    export dialog skips such an output before it ever reaches this function.

    A slot with ``"source": "CONSTANT"`` is filled with its ``"constant"`` value
    (``invert`` -> ``1.0 - value``) and loads no image at all; it works in every
    slot including ``A``. Resolution still comes from the map-backed slots. When
    there are none -- an output that is *all* constants, which is legal and fully
    determined -- ``fallback_size`` decides, as ``(width, height)``; callers pass
    the export's requested resolution. Without it such an output raises rather
    than guessing a size.
    """

    slots = _slot_definitions(output_def)
    use_alpha = slots[CHANNEL_A] is not None
    out_slots = CHANNEL_SLOTS if use_alpha else CHANNEL_SLOTS[:3]

    needed = referenced_sources(output_def)
    has_constant = any(
        slots[slot] is not None and slots[slot]["constant"] is not None for slot in CHANNEL_SLOTS
    )
    if not needed and not has_constant:
        raise ExportPackError("Output definition assigns no source to any channel")

    missing = tuple(name for name in needed if name not in sources or sources[name] is None)
    if missing:
        raise ExportPackError(
            "Missing baked source map(s) for this output: " + ", ".join(missing),
            missing_sources=missing,
        )

    arrays: dict[str, np.ndarray] = {}
    resolution: tuple[int, int] | None = None
    for name in needed:
        array = _as_source_array(sources[name], name)
        if resolution is None:
            resolution = (int(array.shape[0]), int(array.shape[1]))
        elif (int(array.shape[0]), int(array.shape[1])) != resolution:
            detail = ", ".join(
                f"{other}={int(arrays[other].shape[1])}x{int(arrays[other].shape[0])}"
                for other in arrays
            )
            raise ExportPackError(
                "Sources of one output must share a resolution (v1 does not resize): "
                f"{detail}, {name}={int(array.shape[1])}x{int(array.shape[0])}"
            )
        arrays[name] = array

    if resolution is None:
        # Every filled slot is a constant, so no source carries a size.
        resolution = _fallback_resolution(fallback_size)

    planes = []
    for slot in out_slots:
        definition = slots[slot]
        if definition is not None and definition["constant"] is not None:
            planes.append(
                np.full(resolution, np.float32(_constant_plane_value(definition)), dtype=np.float32)
            )
            continue
        if definition is None or not definition["source"]:
            planes.append(np.zeros(resolution, dtype=np.float32))
            continue
        source = definition["source"]
        planes.append(_extract_channel(arrays[source], definition, source))

    composed = np.stack(planes, axis=-1).astype(np.float32, copy=False)
    if not _output_is_unclamped(output_def):
        composed = np.clip(composed, 0.0, 1.0).astype(np.float32, copy=False)
    return np.ascontiguousarray(composed, dtype=np.float32)


def premultiply_compensate(rgba: np.ndarray) -> np.ndarray:
    """Pre-divide-proof an RGBA buffer against Blender's premul->straight step.

    Blender treats a float image buffer as premultiplied and un-premultiplies it
    (RGB /= A) when writing any non-EXR format. Measured on Blender 5.1.1: RGB
    ``(0.5, 0.25, 1.0)`` with A ``0.25`` writes as ``(255, 255, 255, 64)`` -- the
    packed RGB is destroyed. That is fatal for channel packing, where A carries an
    unrelated mask rather than opacity, and ``Image.alpha_mode`` (STRAIGHT /
    PREMUL / CHANNEL_PACKED / NONE) has **no** effect on it.

    Multiplying RGB by A first cancels the division exactly (same float buffer,
    same A, both in float32 before quantization): the same case then writes as
    ``(128, 64, 255, 64)``. Where A is 0, Blender leaves RGB alone rather than
    zeroing it, so those texels are passed through untouched.

    Whether the division happens is per format *and* depth, so
    ``resolve_format_settings`` decides -- do not call this unconditionally. See
    ``_PREMULTIPLIED_ALPHA_COMBOS``.
    """

    array = np.asarray(rgba, dtype=np.float32)
    if array.ndim != 3 or array.shape[2] != 4:
        raise ExportPackError(
            f"premultiply_compensate expects a HxWx4 array, got shape {tuple(array.shape)}"
        )
    alpha = array[:, :, 3:4]
    out = array.copy()
    out[:, :, :3] = np.where(alpha > 0.0, array[:, :, :3] * alpha, array[:, :, :3])
    return out


# --- format resolution (pure) ------------------------------------------------

# Depth support is what Blender's ImageFormatSettings actually accepts, verified
# by assignment on Blender 5.1.1 -- the RNA enum advertises 8/10/12/16/32 for
# every format, but assigning an unsupported depth raises. TGA really is 8-bit
# only; EXR really has no 8-bit mode.
_FORMAT_SPECS = {
    constants.IMAGE_FORMAT_TGA: {
        # Uncompressed, matching IMAGE_FORMAT_ITEMS' description and the mapping
        # already used by blender_bake.py. TARGA (RLE) would be smaller but is a
        # different documented product.
        "file_format": "TARGA_RAW",
        "depths": ("8",),
        "is_linear": False,
    },
    constants.IMAGE_FORMAT_PNG: {
        "file_format": "PNG",
        "depths": ("8", "16"),
        "is_linear": False,
    },
    constants.IMAGE_FORMAT_TIFF: {
        "file_format": "TIFF",
        "depths": ("8", "16"),
        "is_linear": False,
    },
    constants.IMAGE_FORMAT_EXR: {
        "file_format": "OPEN_EXR",
        "depths": ("16", "32"),
        "is_linear": True,
    },
    # DDS is encoded by the backend packer (DirectXTex), not by Blender's
    # ImageFormatSettings. Listed so clamp/validate accept it; save_composed_image
    # refuses and points at the backend path.
    constants.IMAGE_FORMAT_DDS: {
        "file_format": "DDS",
        "depths": ("8",),
        "is_linear": False,
    },
}

# (format, depth) combinations Blender writes with ASSOCIATED (premultiplied)
# alpha, i.e. where it does *not* divide RGB by A on write and
# ``premultiply_compensate`` must be skipped. Measured on Blender 5.1.1 by
# writing (0.5, 0.25, 1.0) at A = 0.25 and reading the file back:
#
#   PNG 8/16, TGA 8, TIFF 8  -> RGB came back saturated, i.e. divided by A
#                               (TIFF 8 tags itself unassociated, tag 338 = 2)
#   TIFF 16                  -> RGB came back verbatim; the file is tagged
#                               associated alpha (tag 338 = 1)
#
# Caveat worth surfacing in the export UI: because 16-bit TIFF is written as
# associated alpha, a strict TIFF reader will un-premultiply it, which is wrong
# for a channel pack whose A is a mask rather than opacity. PNG 16 is the safe
# 16-bit RGBA target.
_PREMULTIPLIED_ALPHA_COMBOS = frozenset({(constants.IMAGE_FORMAT_TIFF, "16")})


def _normalized_format(format_id: str) -> str:
    normalized = str(format_id or "").strip().upper()
    if normalized == "OPEN_EXR":
        normalized = constants.IMAGE_FORMAT_EXR
    elif normalized in ("TARGA", "TARGA_RAW"):
        normalized = constants.IMAGE_FORMAT_TGA
    elif normalized == "TIF":
        normalized = constants.IMAGE_FORMAT_TIFF
    if normalized not in _FORMAT_SPECS:
        raise ExportPackError(
            f"Unsupported image format '{format_id}' "
            f"(expected one of {', '.join(sorted(_FORMAT_SPECS))})"
        )
    return normalized


def _normalized_depth(bit_depth) -> str:
    try:
        return str(int(str(bit_depth).strip()))
    except (TypeError, ValueError) as exc:
        raise ExportPackError(f"Bit depth '{bit_depth}' is not an integer") from exc


def supported_bit_depths(format_id: str) -> tuple[int, ...]:
    """Bit depths Blender can actually write for this format."""

    return tuple(int(depth) for depth in _FORMAT_SPECS[_normalized_format(format_id)]["depths"])


def clamp_bit_depth_for_format(format_id: str, bit_depth) -> int:
    """Nearest bit depth this format supports.

    Lets callers sanitize project-wide settings (which allow TGA + 16-bit and
    EXR + 8-bit) before calling ``resolve_format_settings``, which rejects them.
    """

    supported = supported_bit_depths(format_id)
    requested = int(_normalized_depth(bit_depth))
    return min(supported, key=lambda depth: (abs(depth - requested), depth))


def resolve_format_settings(format_id: str, bit_depth, has_alpha: bool) -> dict:
    """Translate an addon format id + bit depth into Blender output settings.

    Pure function -- no ``bpy`` -- so the whole format matrix is unit tested.
    Returns the keys ``save_composed_image`` needs:

    ``image_format``   normalized addon id (``constants.IMAGE_FORMAT_*``)
    ``file_format``    ``ImageFormatSettings.file_format`` enum
    ``color_depth``    ``ImageFormatSettings.color_depth`` enum
    ``color_mode``     ``RGBA`` when an alpha channel is used, else ``RGB``
    ``extension``      file extension including the dot
    ``is_linear``      the format stores linear data (EXR): no view transform,
                       no clamping, no premultiply compensation
    ``clamp``          composited values should be clamped to [0, 1]
    ``premultiply_compensation``  ``premultiply_compensate`` must run first,
                       because Blender divides RGB by A for this format/depth
    """

    image_format = _normalized_format(format_id)
    spec = _FORMAT_SPECS[image_format]
    depth = _normalized_depth(bit_depth)
    if depth not in spec["depths"]:
        raise ExportPackError(
            f"{image_format} does not support {depth}-bit output "
            f"(supported: {', '.join(spec['depths'])}-bit)"
        )

    is_linear = bool(spec["is_linear"])
    divides_by_alpha = not is_linear and (image_format, depth) not in _PREMULTIPLIED_ALPHA_COMBOS
    return {
        "image_format": image_format,
        "file_format": spec["file_format"],
        "color_depth": depth,
        "color_mode": "RGBA" if has_alpha else "RGB",
        "extension": naming.output_extension_for_image_format(image_format),
        "is_linear": is_linear,
        "clamp": not is_linear,
        "premultiply_compensation": bool(has_alpha) and divides_by_alpha,
    }


# --- Blender-side encoding ---------------------------------------------------

_SCRATCH_IMAGE_NAME = "FyrBaker_ExportPack_Scratch"

#: ``ImageFormatSettings`` attributes captured and restored around a save.
_IMAGE_SETTINGS_KEYS = ("file_format", "color_mode", "color_depth", "color_management")
#: ``ImageFormatSettings.view_settings`` attributes captured and restored.
_VIEW_SETTINGS_KEYS = ("view_transform", "look", "exposure", "gamma")


def _capture_image_settings(image_settings) -> dict:
    captured = {"media_type": None, "settings": {}, "view": {}}
    if hasattr(image_settings, "media_type"):
        captured["media_type"] = image_settings.media_type
    for key in _IMAGE_SETTINGS_KEYS:
        if hasattr(image_settings, key):
            captured["settings"][key] = getattr(image_settings, key)
    view_settings = getattr(image_settings, "view_settings", None)
    if view_settings is not None:
        for key in _VIEW_SETTINGS_KEYS:
            if hasattr(view_settings, key):
                captured["view"][key] = getattr(view_settings, key)
    return captured


def _assign(target, key, value) -> None:
    try:
        setattr(target, key, value)
    except (AttributeError, TypeError, ValueError):
        # A value the current Blender build rejects (e.g. a look name from a
        # different OCIO config). Never let restore bookkeeping kill an export.
        pass


def _restore_image_settings(image_settings, captured: dict) -> None:
    # media_type gates which file formats are assignable; file_format gates which
    # depths and modes are assignable. Restore outside-in.
    if captured.get("media_type") is not None:
        _assign(image_settings, "media_type", captured["media_type"])
    settings = captured.get("settings", {})
    if "file_format" in settings:
        _assign(image_settings, "file_format", settings["file_format"])
    for key, value in settings.items():
        if key != "file_format":
            _assign(image_settings, key, value)
    view_settings = getattr(image_settings, "view_settings", None)
    if view_settings is not None:
        for key, value in captured.get("view", {}).items():
            _assign(view_settings, key, value)


def _apply_image_settings(image_settings, resolved: dict) -> None:
    if hasattr(image_settings, "media_type"):
        _assign(image_settings, "media_type", "IMAGE")
    image_settings.file_format = resolved["file_format"]
    image_settings.color_mode = resolved["color_mode"]
    image_settings.color_depth = resolved["color_depth"]

    # Neutralize color management *on the image format*, never on the scene.
    if hasattr(image_settings, "color_management"):
        image_settings.color_management = "OVERRIDE"
        view_settings = getattr(image_settings, "view_settings", None)
        if view_settings is not None:
            _assign(view_settings, "view_transform", "Standard")
            _assign(view_settings, "look", "None")
            _assign(view_settings, "exposure", 0.0)
            _assign(view_settings, "gamma", 1.0)


def _active_scene(bpy):
    scene = getattr(getattr(bpy, "context", None), "scene", None)
    if scene is not None:
        return scene
    scenes = getattr(getattr(bpy, "data", None), "scenes", None)
    if scenes:
        return scenes[0]
    raise ExportPackError("No scene available to source image format settings from")


def coverage_mask_to_backend_u8(mask) -> bytes:
    """A bottom-up boolean UV-coverage mask as the raw u8 plane the backend loads.

    ``rasterize_group_low_uv_mask`` follows Blender's ``Image.pixels`` order (row 0
    = bottom). The backend's ``load_coverage_u8`` reads ``width * height`` bytes with
    row 0 at the TOP, the same convention ``_write_rgba32f`` flips the colour planes
    into, so the mask is flipped once here as well. Non-zero = covered.
    """
    array = np.asarray(mask, dtype=bool)
    if array.ndim != 2:
        raise ExportPackError(f"Coverage mask must be HxW, got shape {array.shape}")
    return np.ascontiguousarray(np.flipud(array)).astype(np.uint8).tobytes()


def _nearest_covered_texels(coverage: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per texel: (row, column) of the nearest covered texel and the squared distance.

    Jump-flooding in numpy: log2(N) passes over eight offsets, each pass halving the
    step. Exact for the covered texels themselves, and within one texel of exact for
    the rest, which is the same guarantee the backend's own JFA dilation gives.
    Uncovered texels that no seed ever reaches (an all-empty mask) keep row = -1.
    """
    height, width = coverage.shape
    rows, cols = np.indices((height, width), dtype=np.int32)
    seed_r = np.where(coverage, rows, np.int32(-1))
    seed_c = np.where(coverage, cols, np.int32(-1))
    far = np.int64(np.iinfo(np.int32).max)
    best = np.where(coverage, np.int64(0), far)

    def shifted(source: np.ndarray, dy: int, dx: int) -> np.ndarray:
        # The value at (y + dy, x + dx), or -1 outside the image.
        out = np.full_like(source, -1)
        ys = slice(max(0, -dy), height - max(0, dy))
        yd = slice(max(0, dy), height - max(0, -dy))
        xs = slice(max(0, -dx), width - max(0, dx))
        xd = slice(max(0, dx), width - max(0, -dx))
        out[ys, xs] = source[yd, xd]
        return out

    step = 1
    while step * 2 < max(height, width):
        step *= 2
    while step >= 1:
        for dy in (-step, 0, step):
            for dx in (-step, 0, step):
                if dy == 0 and dx == 0:
                    continue
                cand_r = shifted(seed_r, dy, dx)
                cand_c = shifted(seed_c, dy, dx)
                valid = cand_r >= 0
                dr = rows.astype(np.int64) - cand_r
                dc = cols.astype(np.int64) - cand_c
                distance = dr * dr + dc * dc
                better = valid & (distance < best)
                seed_r = np.where(better, cand_r, seed_r)
                seed_c = np.where(better, cand_c, seed_c)
                best = np.where(better, distance, best)
        step //= 2
    return seed_r, seed_c, best


def dilate_composed(
    composed: np.ndarray,
    coverage,
    padding_mode: str,
    padding_size: int = 0,
) -> np.ndarray:
    """Stretch UV island borders outward, the numpy twin of the backend's dilate_rgba.

    Every uncovered texel takes the RGB of its nearest covered texel: all of them for
    ``INFINITE``, only those within ``padding_size`` texels for ``DISTANCE``. Covered
    texels are untouched, and so is alpha, matching the backend. ``coverage`` is a
    bottom-up HxW mask like ``composed`` itself; a mismatched shape is refused rather
    than silently dilated against the wrong islands.
    """
    mode = str(padding_mode or constants.EXPORT_PADDING_NONE).upper()
    if mode == constants.EXPORT_PADDING_NONE:
        return composed
    if mode not in (constants.EXPORT_PADDING_INFINITE, constants.EXPORT_PADDING_DISTANCE):
        raise ExportPackError(f"Unknown padding mode '{padding_mode}'")
    mask = np.asarray(coverage, dtype=bool)
    height, width = int(composed.shape[0]), int(composed.shape[1])
    if mask.shape != (height, width):
        raise ExportPackError(
            f"Coverage mask is {mask.shape[1]}x{mask.shape[0]} but the image is {width}x{height}"
        )
    if not mask.any() or mask.all():
        return composed
    seed_r, seed_c, _distance = _nearest_covered_texels(mask)
    fill = (~mask) & (seed_r >= 0)
    if mode == constants.EXPORT_PADDING_DISTANCE:
        # The backend grows its band with 8-neighbour rings (expand_mask), i.e. a
        # Chebyshev distance: N texels out includes the diagonals. Measured the same
        # way here, from the texel each fill takes its colour from.
        limit = np.int64(max(0, int(padding_size or 0)))
        rows, cols = np.indices(mask.shape, dtype=np.int64)
        chebyshev = np.maximum(np.abs(rows - seed_r), np.abs(cols - seed_c))
        fill &= chebyshev <= limit
    out = np.array(composed, copy=True)
    out[fill, :3] = composed[seed_r[fill], seed_c[fill], :3]
    return out


def read_image_pixels(image) -> np.ndarray:
    """Read a Blender image into a float32 ``HxWx4`` array in bottom-up order.

    The exact inverse of what ``save_composed_image`` writes, so EXR
    intermediates loaded with it feed ``compose_output`` unflipped.
    """

    width, height = int(image.size[0]), int(image.size[1])
    channels = int(image.channels)
    buffer = np.empty(width * height * channels, dtype=np.float32)
    image.pixels.foreach_get(buffer)
    array = buffer.reshape(height, width, channels)
    if channels == 4:
        return array
    if channels == 3:
        padded = np.ones((height, width, 4), dtype=np.float32)
        padded[:, :, :3] = array
        return padded
    raise ExportPackError(f"Image '{getattr(image, 'name', '?')}' has {channels} channels, expected 3 or 4")


def save_composed_image(
    pixels: np.ndarray,
    filepath: str,
    format_id: str,
    bit_depth,
    color_space: str,
) -> None:
    """Write a composed array to disk through a scratch Blender image.

    Color-management decision (measured on Blender 5.1.1, scene view transform
    AgX, not taken from the docs):

    * ``Image.save()`` with ``filepath_raw`` + ``file_format`` touches no scene
      state, but **cannot choose a bit depth**: a float-buffer image always wrote
      16-bit PNG/TIFF, with no way to request 8-bit. It is therefore unusable for
      an exporter that must honour a per-output bit depth (and would silently
      double the storage footprint of every 8-bit export).
    * ``Image.save_render()`` reads ``scene.render.image_settings``, which *does*
      expose ``color_depth`` -- verified 8 vs 16-bit PNG (IHDR), 8 vs 16-bit TIFF,
      16 vs 32-bit EXR, and ``color_mode`` RGB vs RGBA (PNG color type 2 vs 6).
      By default it also bakes the scene's view transform into the file (an sRGB
      color map came out as ``(166, 151, 200)`` under AgX instead of
      ``(188, 137, 255)``).
    * The fix is ``image_settings.color_management = 'OVERRIDE'`` plus
      ``image_settings.view_settings`` = Standard / look None / exposure 0 /
      gamma 1. That is a property **of the output format**, so
      ``scene.view_settings`` and ``scene.display_settings`` -- the color
      management the user sees in Render Properties and in every viewport -- are
      never touched, not even transiently. Only ``scene.render.image_settings``
      is written, and it is restored in a ``finally`` block.

    With that override, measured round trips are exact:

    * ``color_space=NON_COLOR`` -> image colorspace ``Non-Color``. Data
      colorspaces bypass color management entirely, so linear 0.5 writes as byte
      128 / 16-bit 32768. (Confirmed immune even with FOLLOW_SCENE + AgX.)
    * ``color_space=SRGB`` -> image colorspace ``sRGB``. Linear 0.5 writes as byte
      188, i.e. correctly sRGB-encoded and byte-faithful on read-back.

    ``pixels`` is float32 ``HxWx3`` or ``HxWx4`` in bottom-up row order. RGB
    input is padded with alpha 1.0 because Blender image buffers are always RGBA
    internally; ``color_mode`` still drops the channel from the file.
    """

    import bpy  # noqa: PLC0415 -- lazy so the module imports headless

    if str(format_id or "").strip().upper() == constants.IMAGE_FORMAT_DDS:
        raise ExportPackError(
            "DDS export requires the backend packer (DirectXTex); "
            "the numpy/Blender path cannot write DDS"
        )

    array = np.asarray(pixels, dtype=np.float32)
    if array.ndim != 3 or array.shape[2] not in (3, 4):
        raise ExportPackError(
            f"save_composed_image expects a HxWx3 or HxWx4 array, got shape {tuple(array.shape)}"
        )
    height, width = int(array.shape[0]), int(array.shape[1])
    if height <= 0 or width <= 0:
        raise ExportPackError(f"Refusing to save a {width}x{height} image")

    has_alpha = array.shape[2] == 4
    resolved = resolve_format_settings(format_id, bit_depth, has_alpha)

    normalized_space = str(color_space or "").strip().upper()
    if normalized_space not in COLOR_SPACES:
        raise ExportPackError(
            f"Unknown color space '{color_space}' (expected one of {', '.join(COLOR_SPACES)})"
        )
    is_data = normalized_space == COLOR_SPACE_NON_COLOR

    if has_alpha:
        rgba = array
    else:
        rgba = np.ones((height, width, 4), dtype=np.float32)
        rgba[:, :, :3] = array
    if resolved["premultiply_compensation"]:
        rgba = premultiply_compensate(rgba)

    flat = np.ascontiguousarray(rgba.reshape(-1), dtype=np.float32)

    directory = os.path.dirname(str(filepath))
    if directory:
        os.makedirs(directory, exist_ok=True)

    image = bpy.data.images.new(
        _SCRATCH_IMAGE_NAME,
        width,
        height,
        alpha=True,
        float_buffer=True,
        is_data=is_data,
    )
    captured = None
    image_settings = None
    try:
        image.colorspace_settings.name = "Non-Color" if is_data else "sRGB"
        # No effect on the write path (measured), but it states the intent for
        # anyone inspecting the scratch datablock mid-export.
        _assign(image, "alpha_mode", "CHANNEL_PACKED")
        image.pixels.foreach_set(flat)

        image_settings = _active_scene(bpy).render.image_settings
        captured = _capture_image_settings(image_settings)
        _apply_image_settings(image_settings, resolved)
        # Encode beside the destination and move it into place. save_render writes the
        # artist's final file directly, so a failure part way through (a full disk, a
        # format the encoder refuses) destroyed the file they had just consented to
        # replace and left a truncated one behind, reported only as a generic warning.
        final_path = Path(str(filepath))
        temporary_path = final_path.with_name(f"{final_path.name}.{os.getpid()}.tmp{final_path.suffix}")
        try:
            image.save_render(filepath=str(temporary_path))
            os.replace(temporary_path, final_path)
        except BaseException:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    finally:
        if captured is not None and image_settings is not None:
            _restore_image_settings(image_settings, captured)
        try:
            bpy.data.images.remove(image)
        except Exception:  # pragma: no cover - Blender-only cleanup
            pass
