"""Output-template editor -- Phase 2 of the texture-export feature.

Implements ``docs/archive/TEXTURE_EXPORT_DIALOG_PLAN.md`` section 3.2: a Substance-
Painter-style "Output Templates" editor living in a new addon-preferences tab
(``EXPORT_TEMPLATES``). Phase 1 shipped the store (``export_templates``), the
token engine (``export_tokens``), the packer (``export_pack``) and the read-only
Output Template tab of the export dialog; this module is the authoring half.

Where the editing state lives (and where it deliberately does NOT)
-----------------------------------------------------------------
The plan sketched the staging tree on ``AddonPreferences``. It is on
**WindowManager** instead:

* ``AddonPreferences`` values are written into ``userpref.blend`` on every
  "Save Preferences", so a nested outputs x 4-channel collection would bloat the
  user's preferences file with scratch data that is meaningless the moment the
  JSON on disk changes;
* ``preferences.py`` carries an explicit save/restore-across-reload discipline
  (``_save_prefs_to_dict``) that refuses collection/pointer properties outright
  -- a staging tree there would silently not survive a reload anyway;
* ``WindowManager`` is per-session and never serialised, which is exactly the
  lifetime of a scratch editor buffer.

The JSON files on disk remain the single source of truth, and the editor
**autosaves**: staging is loaded from a file on selection and written straight
back on every edit (:func:`autosave`), so there is no Save button and no unsaved
state to lose. New / Duplicate / Delete are file operations that act immediately
for the same reason. The only manual file steps left are Import / Export, which
are about sharing a template with someone else, not about persisting it.

Layering
--------
:func:`template_to_staging` and :func:`staging_to_template` are **pure**: they
touch no ``bpy`` API beyond the duck-typed collection protocol
(``clear()`` / ``add()`` / iteration), so ``tests/test_export_template_editor.py``
round-trips every shipped built-in through them headless. The channel-block
derivation (:func:`output_blocks`, :func:`is_gray_shaped`, :func:`is_rgb_shaped`),
the assignment writers (:func:`assign_block_source`, :func:`set_block_invert`,
:func:`set_alpha_enabled`) and the palette (:func:`source_color`) are pure on the
same terms -- only :func:`swatch_icon_value` touches ``bpy.utils.previews``.

Shape of the UI -- three columns, slot-first
-------------------------------------------
1. **Templates** -- the list plus New / Duplicate / Delete / Import / Export.
2. **Current preset** -- the template's name, the ``Create:`` shape buttons, and
   *one boxed card per output map*, which is the whole editor for that output::

       [dot] [filename]  [$]  [PNG] [8-bit]                [copy] [X]
         [chip]  [ Material: Albedo · RGB        v ]        [invert]
         [chip]  [ Material: Opacity · Gray      v ]        [invert]
       [Linear] [note]                          [alpha] [up] [down]
       (blank line -- breathing room; the token alert appears here)

   The assignment is Blender's **own** enum dropdown (``prop(entry,
   "assignment")``), bound to the block's anchor slot -- see the "assignment
   dropdown" section. The cards are a plain stack of ``layout.box()`` calls: a
   ``UIList`` was tried and dropped, because its active-row highlight assumes a
   one-line row and cannot cover a card.
3. **Available Sources** -- a read-only legend of every assignable map, grouped
   Material channels / Mesh maps, coloured swatch when this preset uses the map
   and the dark chip when it does not, plus the :func:`validate_staging`
   read-out underneath.

Why the hierarchy is this way round (see
``docs/OUTPUT_TEMPLATE_EDITOR_REDESIGN_PLAN.md``): column 3 used to *be* the
assignment mechanism -- click a tiny R/G/B chip to arm a destination, travel to
the source list, click a map, then answer a component menu. Substance Painter
can afford that layout because it also supports dragging a source onto a slot;
Blender exposes no drop target for a Python-drawn button, so without the drag it
is a hidden mode with four steps and no visible state. Making the slot itself
the control collapses it to one: read the assignment, click it, pick.

The dropdown names the map and nothing else. Its two qualifiers -- *which
channel of that map* and *which bake of it* -- live behind one popover button
beside it (:func:`draw_channel_options_popover`), because they only exist once
something is assigned and they should not compete with the assignment for the
row's width. The pick itself assigns outright, with the read
:func:`default_read_channel` infers; the popover is where that is overridden.

Black / Gray / White / Custom are assignable the same way, under a **Constants**
heading: they write the pinned ``source: "CONSTANT"`` + ``constant: <0..1>``
contract that ``export_templates`` and ``export_pack`` own.

Nothing is assigned for you
---------------------------
A new output -- from any "Create:" shape -- arrives with its slots **empty**, and
"+" creates an **empty template**. The shape decides which slots exist and how
they route, never which maps they read; a map lands in a slot only when the
artist clicks it, and the ``Unassigned`` row takes it back out. The template
format carries that state directly (``"source": ""``, see ``export_templates``),
so an in-progress template is a normal file on disk like any other.

Channel blocks
--------------
A block is *what the artist thinks of as one thing*: R/G/B fed by one source with
identity routing collapse into one ``RGB`` block, one *assigned* grayscale source
across R/G/B collapses into one ``Gray`` block, anything else is one block per
enabled slot. Alpha is always its own block. Blocks are derived from the staged
channels on every draw -- nothing about the grouping is stored, so the JSON
round-trip is untouched. The *selection* is stored as an anchor slot rather than a
block key, which is what keeps a selection alive when an assignment regroups the
blocks under it (assigning AO to the last of three split slots merges them into
Gray).

Several bakes of one map type
-----------------------------
A project may hold two AO bakes, or three Curvature. A channel says which one by
**occurrence ordinal** -- never by the bake's name, which is one project's word
for it and would break the template everywhere else. The dropdown offers the
extra occurrences only when the **open** project actually has them, labelled with
each bake's own name so the artist recognises them, and what it stores is the
ordinal. See the "Map variants" section below and ``docs/MAP_VARIANTS_PLAN.md``.
"""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from pathlib import Path

import bpy

from . import constants, export_pack, export_templates, export_tokens, sidebar_icons
from .ui_map_settings import map_stack_index_label


# ---------------------------------------------------------------------------
# Vocabulary (kept local: constants.py is owned by another workstream)
# ---------------------------------------------------------------------------

#: Output channel slots, in file order.
CHANNEL_SLOTS: tuple[str, ...] = export_pack.CHANNEL_SLOTS

#: Icon for the invert toggle. Blender ships no "invert" glyph; the mask modifier
#: icon is the closest legible stand-in at 20 px and reads as "flip what passes
#: through" rather than as a file/format action.
INVERT_ICON = "MOD_MASK"

SOURCE_CHANNEL_ITEMS = (
    ("R", "R", "Read the source map's red channel"),
    ("G", "G", "Read the source map's green channel"),
    ("B", "B", "Read the source map's blue channel"),
    ("A", "A", "Read the source map's alpha channel"),
    ("GRAY", "Gray", "Read the source map's luminance (pass-through for scalar maps)"),
)

#: Every routing a slot can store, as written into the JSON ``channel`` field.
SOURCE_CHANNELS: tuple[str, ...] = tuple(item[0] for item in SOURCE_CHANNEL_ITEMS)

#: Pseudo-routing for "each slot reads its own letter" (R←R, G←G, B←B). It is
#: **never** written to a channel: :func:`assign_block_source` expands it per
#: slot, which is the only way one click can route a grouped RGB block. Kept
#: distinct from the four real channels so an option list can carry it.
ROUTING_IDENTITY = "IDENTITY"

#: Label of the "no map" pick, and the text a slot with nothing assigned shows.
#: It is a *source* like any other ("no map"), which is why the picker lists it
#: in the same column as the maps rather than as a separate control elsewhere.
UNASSIGN_LABEL = "Unassigned"

#: Routing -> the word the slot's assignment button shows after the map name.
#: ``IDENTITY`` reads "RGB" because that is what it means to the artist: the
#: source's own R/G/B land on the output's R/G/B.
COMPONENT_LABELS: dict[str, str] = {
    ROUTING_IDENTITY: "RGB",
    "GRAY": "Gray",
    "R": "R",
    "G": "G",
    "B": "B",
    "A": "A",
}

# ---------------------------------------------------------------------------
# Constants as a source (Black / Gray / White / Custom)
#
# The pinned data contract lives in ``export_templates`` + ``export_pack``,
# which are owned by another workstream: a channel sets ``"source": "CONSTANT"``
# and carries ``"constant": <float 0..1>``; ``"constant"`` is legal ONLY on a
# CONSTANT channel, and ``"invert"`` on one means ``1.0 - value``.
#
# The names are read off ``export_templates`` when it exports them and fall back
# to the pinned literals otherwise, so this module never *re-types* the contract
# where the other half of it already exists. (At the time of writing the
# constants had not landed there yet -- ``validate_template`` still refuses
# ``source: "CONSTANT"``, so a template using one will not autosave until it
# does. Nothing here needs to change when it happens.)
# ---------------------------------------------------------------------------


def _contract_value(names, fallback):
    """First of ``names`` that ``export_templates`` exports, else ``fallback``."""
    for name in names:
        value = getattr(export_templates, name, None)
        if value is not None:
            return value
    return fallback


#: The ``source`` identifier that means "no map: write a flat value".
CONSTANT_SOURCE: str = str(
    _contract_value(("CONSTANT_SOURCE", "SOURCE_CONSTANT", "CHANNEL_SOURCE_CONSTANT"), "CONSTANT")
).strip().upper()

#: The three preset values, as the contract pins them.
CONSTANT_BLACK: float = float(_contract_value(("CONSTANT_BLACK", "CONSTANT_VALUE_BLACK"), 0.0))
CONSTANT_GRAY: float = float(_contract_value(("CONSTANT_GRAY", "CONSTANT_VALUE_GRAY"), 0.5))
CONSTANT_WHITE: float = float(_contract_value(("CONSTANT_WHITE", "CONSTANT_VALUE_WHITE"), 1.0))

#: Enum-item identifiers for the four constant picks. They are **not** source
#: identifiers -- all four write ``source = CONSTANT`` and differ only in the
#: value -- so they are namespaced out of the identifier space a map could use.
CONSTANT_ITEM_BLACK = "__CONST_BLACK__"
CONSTANT_ITEM_GRAY = "__CONST_GRAY__"
CONSTANT_ITEM_WHITE = "__CONST_WHITE__"
CONSTANT_ITEM_CUSTOM = "__CONST_CUSTOM__"

#: ``(item identifier, label, value)`` for the three presets, menu order.
CONSTANT_PRESETS: tuple[tuple[str, str, float], ...] = (
    (CONSTANT_ITEM_BLACK, "Black", CONSTANT_BLACK),
    (CONSTANT_ITEM_GRAY, "Gray", CONSTANT_GRAY),
    (CONSTANT_ITEM_WHITE, "White", CONSTANT_WHITE),
)

#: Where a fresh "Custom" pick starts. Deliberately not one of the presets, so
#: choosing Custom does not immediately read back as Black and take its own
#: value field away again.
CONSTANT_CUSTOM_DEFAULT = 0.25

#: How close a stored value has to be to a preset to read as that preset.
_CONSTANT_EPSILON = 1e-4


def is_constant_source(identifier) -> bool:
    """True when this ``source`` means "flat value", not "baked map". Pure."""
    return str(identifier or "").strip().upper() == CONSTANT_SOURCE


def clamp_constant(value) -> float:
    """A constant's legal range is 0..1; anything else is clamped, not refused."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if number < 0.0 else (1.0 if number > 1.0 else number)


def constant_preset_item(value) -> str:
    """The preset item ``value`` *is*, or ``""`` when it is a custom value."""
    number = clamp_constant(value)
    for identifier, _label, preset in CONSTANT_PRESETS:
        if abs(number - preset) <= _CONSTANT_EPSILON:
            return identifier
    return ""


def format_constant(value) -> str:
    """``0.25`` -- short, no trailing zeros, for the button and the menu item."""
    return f"{clamp_constant(value):g}"


def constant_label(value, custom: bool = False) -> str:
    """What a constant assignment reads as: ``Black`` / ``Custom · 0.25``.

    ``custom`` is the staged "the artist picked Custom" flag, which is what
    keeps a hand-dialled 0.5 from silently turning back into the Gray preset
    (and taking its value field with it).
    """
    if not custom:
        preset = constant_preset_item(value)
        for identifier, label, _preset in CONSTANT_PRESETS:
            if identifier == preset:
                return label
    return f"Custom · {format_constant(value)}"


# ---------------------------------------------------------------------------
# Colour vs scalar sources
#
# Substance Painter's "which channel of the source?" menu is shaped by what the
# source map actually contains: a scalar (1-channel) map offers its natural read
# and nothing per-letter, a colour map offers R/G/B as well. The classification
# below is that fact about the *bake*, not about the export -- it is unrelated to
# a template's sRGB/Linear ``color_space`` (a normal map is colour data and is
# written Linear).
# ---------------------------------------------------------------------------

#: Sources whose baked image carries more than one meaningful channel. Everything
#: else -- AO, curvature, thickness, density, cavity, concave, convex, opacity,
#: height, principal curvature and the scalar ``MATERIAL_*`` channels -- is a
#: single value replicated across RGB, so picking "R" out of it is meaningless.
#:
#: Unknown identifiers are deliberately **scalar** (see :func:`is_color_source`):
#: a future map type falls through to the conservative menu (natural read + A)
#: rather than inviting a channel pick that its bake cannot honour.
COLOR_SOURCE_IDENTIFIERS: frozenset[str] = frozenset(
    {
        constants.MAP_NORMAL,
        constants.MAP_OBJECT_NORMAL,
        constants.MAP_WORLD_NORMAL,
        constants.MAP_BENT_NORMAL,
        constants.MAP_POSITION,
        constants.MAP_VERTEX_COLOR,
        constants.MAP_ATTRIBUTE,
        constants.MAP_DERIVATIVE,
        constants.MAP_ID,
        constants.MAP_ENV_LIGHT,
        constants.MAP_CURVATURE_DIRECTION,
        constants.MAP_MATERIAL_ALBEDO,
        constants.MAP_MATERIAL_EMISSION,
        constants.MAP_SCENE_LIGHTING,
    }
    # LIGHTING / LIT_COLOR: the legacy rows SCENE_LIGHTING replaced. Taken from
    # the constant that already groups them rather than re-listed here, so a
    # future migration cannot leave this set behind.
    | set(constants.LEGACY_SCENE_LIGHTING_MAP_TYPES)
)


def is_color_source(identifier) -> bool:
    """True when this source map carries independent R/G/B channels. Pure.

    Unknown / empty identifiers are scalar: that is the safe default, because a
    scalar menu never offers a pick the source cannot supply.
    """
    return str(identifier or "").strip().upper() in COLOR_SOURCE_IDENTIFIERS

COLOR_SPACE_ITEMS = (
    (export_templates.COLOR_SPACE_LINEAR, "Linear", "Raw data: written without a view transform"),
    (export_templates.COLOR_SPACE_SRGB, "sRGB", "Color data: sRGB-encoded on write"),
)

IMAGE_FORMAT_ITEMS = tuple(
    (identifier, label, description)
    for identifier, label, description in constants.EXPORT_TEMPLATE_IMAGE_FORMAT_ITEMS
)

#: Display names for the ``MATERIAL_*`` channel sub-types, which are real output
#: identifiers without being rows of ``MAP_TYPE_ITEMS``.
_EXTRA_SOURCE_LABELS = {
    constants.MAP_MATERIAL_ALBEDO: ("Material: Albedo", "Base color from the material"),
    constants.MAP_MATERIAL_ROUGHNESS: ("Material: Roughness", "Roughness from the material"),
    constants.MAP_MATERIAL_METALNESS: ("Material: Metalness", "Metalness from the material"),
    constants.MAP_MATERIAL_EMISSION: ("Material: Emission", "Emission from the material"),
    constants.MAP_MATERIAL_OPACITY: ("Material: Opacity", "Alpha/opacity from the material"),
    constants.MAP_MATERIAL_SPECULAR: ("Material: Specular", "Specular from the material"),
    constants.MAP_MATERIAL_TRANSMISSION: ("Material: Transmission", "Transmission from the material"),
    constants.MAP_MATERIAL_NORMAL: ("Material: Normal", "Normal from the material's Normal Map / Bump nodes"),
    constants.MAP_PRINCIPAL_CURVATURE: ("Principal Curvature", "Backend-derived principal curvature"),
    constants.MAP_CURVATURE_DIRECTION: ("Curvature Direction", "Backend-derived curvature direction"),
}

#: New outputs start here.
#:
#: ``$map`` used to be part of it, and is now **retired entirely** (Glow,
#: 2026-08-05): you set the output's label to "D" and then write
#: ``T_$textureSet_D``. A fresh output carries no suffix at all rather than a
#: filler one; the artist types the suffix that names it, and the validation
#: read-out warns if two outputs end up writing the same file.
DEFAULT_FILENAME = "$textureSet"
DEFAULT_FORMAT = constants.IMAGE_FORMAT_PNG
DEFAULT_BIT_DEPTH = 8
DEFAULT_COLOR_SPACE = export_templates.COLOR_SPACE_LINEAR

#: Sample context for the live filename preview at the bottom of the editor.
PREVIEW_PROJECT = "Skull"
PREVIEW_TEXTURE_SET = "Skull"
PREVIEW_RESOLUTION = 2048

NEW_TEMPLATE_NAME = "New Output Template"


# ---------------------------------------------------------------------------
# Palette + swatch icons
#
# Every channel block and every row of the source panel carries a colored chip,
# which is how Substance Painter makes a template scannable: you read the colors
# before you read the words. Blender has no colored-square glyph and no way to
# tint a built-in icon, so the chips are generated as preview icons at register
# time -- 32x32 RGBA float buffers written straight into an ImagePreview, the
# same trick ``sidebar_icons.py`` uses to avoid the async thumbnail pipeline.
# ---------------------------------------------------------------------------

#: Albedo/base color is the one striped chip, mirroring SP's tricolor swatch.
_TRICOLOR = ((0.86, 0.24, 0.24), (0.32, 0.72, 0.34), (0.28, 0.46, 0.92))

_BLUE = (0.33, 0.44, 0.92)
_BLUE_DEEP = (0.24, 0.32, 0.78)
_TEAL = (0.18, 0.66, 0.66)
_GREEN = (0.30, 0.68, 0.34)
_LIGHT_GRAY = (0.78, 0.78, 0.80)
_OLIVE = (0.62, 0.62, 0.24)
_RED = (0.86, 0.26, 0.22)
_PURPLE = (0.56, 0.36, 0.80)
_ORANGE = (0.92, 0.56, 0.20)
_PALE_YELLOW = (0.92, 0.88, 0.58)

#: Neutral chip for every source without a dedicated color.
NEUTRAL_COLOR = (0.52, 0.52, 0.55)

#: Chip for a block whose source is unknown/unset -- deliberately near-black so an
#: unassigned slot reads as a hole rather than as another map.
UNASSIGNED_COLOR = (0.13, 0.13, 0.15)

#: Source identifier -> swatch color. A value is either one RGB triple (a solid
#: chip) or a tuple of triples (horizontal stripes, top to bottom).
MAP_TYPE_COLORS: dict[str, tuple] = {
    constants.MAP_MATERIAL_ALBEDO: _TRICOLOR,
    constants.MAP_NORMAL: _BLUE,
    constants.MAP_OBJECT_NORMAL: _BLUE,
    constants.MAP_WORLD_NORMAL: _BLUE,
    constants.MAP_BENT_NORMAL: _BLUE_DEEP,
    constants.MAP_MATERIAL_ROUGHNESS: _TEAL,
    constants.MAP_MATERIAL_METALNESS: _GREEN,
    constants.MAP_AO: _LIGHT_GRAY,
    constants.MAP_OPACITY: _OLIVE,
    constants.MAP_MATERIAL_OPACITY: _OLIVE,
    constants.MAP_MATERIAL_EMISSION: _RED,
    constants.MAP_HEIGHT: _PURPLE,
    constants.MAP_CURVATURE: _ORANGE,
    constants.MAP_PRINCIPAL_CURVATURE: _ORANGE,
    constants.MAP_CURVATURE_DIRECTION: _ORANGE,
    constants.MAP_THICKNESS: _PALE_YELLOW,
}


#: Palette value -> the color-name segment of the pre-generated chip PNGs in
#: ``icons/chips`` (see ``scripts/generate_chip_icons.py``; keep the two in sync).
_CHIP_COLOR_NAMES: dict[tuple, str] = {
    _TRICOLOR: "multi",
    _BLUE: "blue",
    _BLUE_DEEP: "bluedeep",
    _TEAL: "teal",
    _GREEN: "green",
    _LIGHT_GRAY: "lightgray",
    _OLIVE: "olive",
    _RED: "red",
    _PURPLE: "purple",
    _ORANGE: "orange",
    _PALE_YELLOW: "paleyellow",
}


#: Swatches for the constant picks and for the ``CONSTANT`` source itself. Kept
#: out of :data:`MAP_TYPE_COLORS` on purpose: that table is asserted to name only
#: real source identifiers, and three of these four keys are menu items rather
#: than sources. Custom is the black/gray/white stripe -- "any value in between".
CONSTANT_COLORS: dict[str, tuple] = {
    CONSTANT_ITEM_BLACK: ((0.05, 0.05, 0.06),),
    CONSTANT_ITEM_GRAY: ((0.50, 0.50, 0.52),),
    CONSTANT_ITEM_WHITE: ((0.95, 0.95, 0.96),),
    CONSTANT_ITEM_CUSTOM: ((0.05, 0.05, 0.06), (0.50, 0.50, 0.52), (0.95, 0.95, 0.96)),
    CONSTANT_SOURCE: ((0.50, 0.50, 0.52),),
}


def chip_color_name(identifier) -> str:
    """Filename color segment for a source's chip PNG. Pure; always resolves."""
    key = str(identifier or "").strip().upper()
    if not key:
        return "unset"
    color = MAP_TYPE_COLORS.get(key)
    if color is None:
        return "neutral"
    return _CHIP_COLOR_NAMES.get(color, "neutral")


def source_color(identifier) -> tuple:
    """Swatch stripes for a source identifier. Always resolves to something.

    Returns a tuple of one or three RGB triples: one for a solid chip, three for
    the striped Albedo chip. An empty/unknown identifier resolves to the dark
    "unassigned" chip, everything the palette does not name to neutral gray, so
    the source panel can never draw a source without a color.
    """
    key = str(identifier or "").strip().upper()
    if not key:
        return (UNASSIGNED_COLOR,)
    fixed = CONSTANT_COLORS.get(key)
    if fixed is not None:
        return tuple(tuple(float(component) for component in stripe) for stripe in fixed)
    color = MAP_TYPE_COLORS.get(key)
    if color is None:
        return (NEUTRAL_COLOR,)
    if color and isinstance(color[0], (tuple, list)):
        return tuple(tuple(float(component) for component in stripe) for stripe in color)
    return (tuple(float(component) for component in color),)


#: Chip resolution. 32 px is what Blender scales its own preview icons from and
#: is small enough that generating ~30 of them at register time is free.
SWATCH_SIZE = 32

#: Preview names are namespaced: the collection is ours, but a stray key clash
#: with a future icon set would be a silent wrong-icon bug.
_SWATCH_PREFIX = "mb_tpl_"
_SWATCH_UNASSIGNED = "__none__"
_CHIP_PREFIX = "mb_chip_"

#: Border darkens the chip's edge so a light swatch still reads as a chip against
#: a light theme. One pixel at 32 px, i.e. invisible as a border and effective as
#: a separation.
_SWATCH_BORDER = (0.08, 0.08, 0.09)

_SWATCH_PREVIEWS = None


def _preview_api():
    """``bpy.utils.previews``, or ``None`` (headless tests stub ``bpy``).

    See ``sidebar_icons._preview_api``: the submodule is not bound until imported.
    """
    utils = getattr(bpy, "utils", None)
    if utils is None:
        return None
    previews = getattr(utils, "previews", None)
    if previews is not None:
        return previews
    try:
        import importlib
        return importlib.import_module("bpy.utils.previews")
    except Exception:
        return None


def swatch_pixels(stripes, size: int = SWATCH_SIZE) -> list[float]:
    """Flat RGBA float buffer for a chip. Pure; unit-testable without ``bpy``.

    Colors are opaque, so no alpha premultiply is needed (Blender's preview
    system stores premultiplied pixels; at alpha 1.0 the two are identical).
    """
    bands = tuple(stripes) or (NEUTRAL_COLOR,)
    pixels: list[float] = []
    for y in range(size):
        # Row 0 is the bottom row in Blender's buffers; index the bands from the
        # end so the first stripe of the palette entry ends up on top.
        band = bands[min(len(bands) - 1, (size - 1 - y) * len(bands) // size)]
        for x in range(size):
            edge = x == 0 or y == 0 or x == size - 1 or y == size - 1
            red, green, blue = _SWATCH_BORDER if edge else band
            pixels.extend((red, green, blue, 1.0))
    return pixels


def _swatch_keys() -> tuple[str, ...]:
    """Every chip the editor can ask for: one per valid source, plus unassigned."""
    try:
        valid = sorted(export_templates.valid_source_identifiers())
    except Exception:
        valid = sorted(MAP_TYPE_COLORS)
    # The constant picks are chips like any other source row: the dropdown shows
    # the selected item's icon, so Black/Gray/White/Custom each need one. Deduped
    # because CONSTANT itself becomes a valid source once the contract lands.
    keys: list[str] = []
    for key in tuple(valid) + tuple(sorted(CONSTANT_COLORS)) + (_SWATCH_UNASSIGNED,):
        if key not in keys:
            keys.append(key)
    return tuple(keys)


def _register_swatches() -> None:
    """(Re)build the chip collection. Idempotent -- safe on an addon reload.

    Mirrors ``sidebar_icons.register``: tear the old collection down first, so a
    disable/enable cycle cannot leak a collection or leave stale icon ids behind
    (a preview whose collection was freed draws as garbage, not as nothing).
    """
    global _SWATCH_PREVIEWS
    _unregister_swatches()
    previews_api = _preview_api()
    if previews_api is None:
        return
    try:
        previews = previews_api.new()
    except Exception:
        return
    for key in _swatch_keys():
        stripes = (UNASSIGNED_COLOR,) if key == _SWATCH_UNASSIGNED else source_color(key)
        try:
            preview = previews.new(f"{_SWATCH_PREFIX}{key}")
            preview.image_size = (SWATCH_SIZE, SWATCH_SIZE)
            preview.image_pixels_float[:] = swatch_pixels(stripes)
        except Exception:
            continue
    # SP-style channel-chip PNGs (letter baked into the colored block). Loaded
    # into the same collection so the reload discipline covers them too; a
    # missing directory simply leaves the draw code on its swatch+text fallback.
    chips_dir = Path(__file__).resolve().parent / "icons" / "chips"
    try:
        for chip_path in sorted(chips_dir.glob("*.png")):
            try:
                # Lazy load is fine: chips appear on the tab's first draw and
                # stay resident. Do NOT touch image_pixels_float here to force
                # the read -- doing so blanks file-backed previews (verified
                # live: most chips rendered empty).
                previews.load(f"{_CHIP_PREFIX}{chip_path.stem}", str(chip_path), "IMAGE")
            except Exception:
                continue
    except OSError:
        pass
    _SWATCH_PREVIEWS = previews
    # The assignment items bake each row's icon_value in, so the memo built
    # before the chips existed would pin every row to "no icon".
    _invalidate_assignment_items()


def _unregister_swatches() -> None:
    global _SWATCH_PREVIEWS
    previews_api = _preview_api()
    if _SWATCH_PREVIEWS is not None and previews_api is not None:
        try:
            previews_api.remove(_SWATCH_PREVIEWS)
        except Exception:
            pass
    _SWATCH_PREVIEWS = None
    # Same reason in reverse: icon ids into a freed collection draw as garbage.
    _invalidate_assignment_items()


def swatch_icon_value(identifier) -> int:
    """``icon_value=`` for a source's chip. ``0`` (no icon) when unavailable."""
    if _SWATCH_PREVIEWS is None:
        return 0
    key = str(identifier or "").strip().upper() or _SWATCH_UNASSIGNED
    preview = _SWATCH_PREVIEWS.get(f"{_SWATCH_PREFIX}{key}")
    if preview is None:
        preview = _SWATCH_PREVIEWS.get(f"{_SWATCH_PREFIX}{_SWATCH_UNASSIGNED}")
    return int(getattr(preview, "icon_id", 0) or 0) if preview is not None else 0


def chip_icon_value(label: str, identifier) -> int:
    """``icon_value=`` for a full SP-style channel chip (letter baked in).

    ``label`` is a block label (R/G/B/A/RGB/Gray). Returns ``0`` when the chip
    PNGs are unavailable so the caller can fall back to swatch+text buttons.
    Selection is button styling (emboss + depress), not an icon variant.
    """
    if _SWATCH_PREVIEWS is None:
        return 0
    preview = _SWATCH_PREVIEWS.get(
        f"{_CHIP_PREFIX}{str(label or '').lower()}_{chip_color_name(identifier)}"
    )
    return int(getattr(preview, "icon_id", 0) or 0) if preview is not None else 0


# ---------------------------------------------------------------------------
# Enum item callbacks
#
# Dynamic ``items=`` callbacks must not hand Blender temporary strings: the RNA
# enum keeps borrowed pointers and a freed tuple shows up as garbled menu text.
# Every callback below therefore returns a tuple built once and cached at module
# level.
# ---------------------------------------------------------------------------

_SOURCE_ITEMS_CACHE: tuple = ()
_BIT_DEPTH_ITEMS_CACHE: dict[str, tuple] = {}

#: Map-stack types that are not offered in the template editor. ``MAP_MATERIAL``
#: is a stack row with a per-project channel selector; templates address the
#: resolved ``MATERIAL_*`` effective types instead so they stay portable.
_TEMPLATE_EDITOR_EXCLUDED_SOURCES = frozenset({constants.MAP_MATERIAL})


def is_material_channel_source(identifier) -> bool:
    """True when ``identifier`` is a material-channel output source. Pure."""
    key = str(identifier or "").strip().upper()
    return key.startswith("MATERIAL_")


def source_items_tuple() -> tuple:
    """``(identifier, label, description)`` for every legal channel source.

    Ordered like the map picker (``MAP_TYPE_ITEMS`` order) so an artist finds
    Normal/AO/Curvature where they expect them, with the material sub-channels
    and the backend-derived curvature types appended. Derived from
    ``export_templates.valid_source_identifiers()`` so it cannot drift from what
    the validator accepts.
    """
    global _SOURCE_ITEMS_CACHE
    if _SOURCE_ITEMS_CACHE:
        return _SOURCE_ITEMS_CACHE

    # CONSTANT is a legal channel *source* without being a bakeable map: it gets
    # its own Constants group in the dropdown, so it must never also show up as a
    # mesh map here (it will be in valid_source_identifiers once the contract in
    # export_templates lands).
    valid = export_templates.valid_source_identifiers() - {CONSTANT_SOURCE}
    items: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for identifier, label, description in constants.MAP_TYPE_ITEMS:
        if identifier in _TEMPLATE_EDITOR_EXCLUDED_SOURCES:
            continue
        if identifier in valid and identifier not in seen:
            seen.add(identifier)
            items.append((identifier, str(label), str(description)))
    for identifier, (label, description) in _EXTRA_SOURCE_LABELS.items():
        if identifier in valid and identifier not in seen:
            seen.add(identifier)
            items.append((identifier, label, description))
    for identifier in sorted(valid - seen):
        if identifier in _TEMPLATE_EDITOR_EXCLUDED_SOURCES:
            continue
        items.append((identifier, constants.MAP_FILE_LABELS.get(identifier, identifier), ""))

    _SOURCE_ITEMS_CACHE = tuple(items)
    return _SOURCE_ITEMS_CACHE


def valid_source_or_empty(identifier) -> str:
    """Normalise a source identifier, keeping ``""`` (unassigned) as a valid value.

    Returns ``""`` for anything the validator would not accept, so a caller can
    never write a garbage identifier into the staging buffer.
    """
    key = str(identifier or "").strip().upper()
    if not key:
        return ""
    try:
        return key if key in export_templates.valid_source_identifiers() else ""
    except Exception:  # pragma: no cover - defensive
        return key


def bit_depth_items_tuple(format_id: str) -> tuple:
    """Depths this format can actually store, as enum items.

    The item *number* is the depth itself, not a positional index, so a stored
    value survives the list changing under it when the format dropdown moves.
    """
    key = str(format_id or "").strip().upper() or DEFAULT_FORMAT
    cached = _BIT_DEPTH_ITEMS_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        depths = export_pack.supported_bit_depths(key)
    except export_pack.ExportPackError:
        depths = (8, 16)
    items = tuple(
        (str(depth), f"{depth}-bit", f"Write this output at {depth} bits per channel", "NONE", int(depth))
        for depth in depths
    )
    _BIT_DEPTH_ITEMS_CACHE[key] = items
    return items


def _bit_depth_items(self, context):
    del context
    return bit_depth_items_tuple(getattr(self, "format", DEFAULT_FORMAT))


# ---------------------------------------------------------------------------
# Map variants -- "which of this project's three AO bakes?"
#
# See ``docs/MAP_VARIANTS_PLAN.md``. A project may hold several bakes of one map
# type, and a channel has to be able to name WHICH one **portably**: a template
# is authored once and opened in other projects, so it may not reference a bake's
# ``uuid`` (meaningless elsewhere) nor its *name* ("Fine" is one project's word
# for it). What travels is the **occurrence ordinal** -- 0-based, among same-type
# bakes, in map-stack order (``project.maps`` with the phantom "+" row skipped).
#
# So:
#
# * the staged channel carries ``variant: <int >= 0>``; 0 means "the first bake
#   of this type", which is what every template written so far already means, so
#   the JSON emits the key ONLY when it is non-zero and every existing file stays
#   byte-identical;
# * ``entry.source`` keeps holding the **bare** map type. The composite key
#   (``AO``, ``AO#1``, ``AO#2``) exists only as a menu-item identifier here and
#   as the packer's source key -- which is what keeps every colour lookup, the
#   legend, ``assigned_sources`` and the validator working on the map type;
# * the *labels* below are display-only. They are read off the open project's map
#   stack so the menu can say "Ambient Occlusion · Fine", and are thrown away the
#   moment the template is written. Nothing project-specific reaches the file.
#
# Fan-out ("one file per AO, whatever they are called") is increment 2 and is
# deliberately not here: selection has to exist first.
# ---------------------------------------------------------------------------

#: The occurrence a channel addresses when it carries no ``variant``: the first
#: bake of its type, which is what every template written so far already means.
DEFAULT_VARIANT: int = export_pack.DEFAULT_VARIANT

#: Where the stack-index field's drag range stops being useful. A *soft* max
#: only: a template is authored for projects that are not open, so the index it
#: names is not bounded by what the current map stack holds -- the artist can
#: still type a higher one.
STACK_INDEX_SOFT_MAX = 8


def stack_index_resolvable(spec, source, variant=DEFAULT_VARIANT) -> bool:
    """Whether the open project actually holds this occurrence of ``source``. Pure.

    ``False`` is not an error -- it is the honest cost of portability (see
    ``docs/MAP_VARIANTS_PLAN.md``): the template keeps the index, and the export
    skips the channel with a stated reason rather than silently reading the first
    bake. The popover says so at the moment the index is picked.
    """
    try:
        ordinal = max(DEFAULT_VARIANT, int(variant or DEFAULT_VARIANT))
    except (TypeError, ValueError):
        ordinal = DEFAULT_VARIANT
    return ordinal < variant_count(spec, source)


def build_source_key(map_type, variant=DEFAULT_VARIANT) -> str:
    """``("AO", 0) -> "AO"``, ``("AO", 1) -> "AO#1"``. Pure.

    A thin, *normalising* wrapper over ``export_pack.source_key``, which owns the
    format: the ``"#"`` is never spelled in this module. The wrapper exists only
    because the editor's callers hand it whatever is in the staging buffer --
    ``None``, a float that survived an RNA round-trip, a lower-cased identifier --
    and ``normalized_variant`` refuses all three by design (it validates a *file's*
    ordinal, where a float is a bug worth raising on). Here that would be a
    dropdown that cannot draw, so it clamps instead.
    """
    name = str(map_type or "").strip().upper()
    try:
        ordinal = max(DEFAULT_VARIANT, int(variant or DEFAULT_VARIANT))
    except (TypeError, ValueError):
        ordinal = DEFAULT_VARIANT
    return export_pack.source_key(name, ordinal)


def split_source_key(key) -> tuple:
    """``"AO#1" -> ("AO", 1)``. Anything without an ordinal answers ``(key, 0)``.

    ``export_pack.parse_source_key`` is total by construction, so this only
    upper-cases the map type to the editor's identifier convention.
    """
    base, ordinal = export_pack.parse_source_key(key)
    return (str(base or "").strip().upper(), int(ordinal))


def ordinal_word(number) -> str:
    """``1 -> "1st"``, ``2 -> "2nd"``, ``11 -> "11th"``. Pure.

    **One-based**: the artist counts bakes from one, the schema counts
    occurrences from zero, so callers pass ``variant + 1``.
    """
    try:
        value = int(number)
    except (TypeError, ValueError):
        value = 1
    value = max(1, value)
    if 11 <= (value % 100) <= 13:
        return f"{value}th"
    return f"{value}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')}"


def entry_variant(entry) -> int:
    """Which occurrence a staged channel addresses. ``0`` == the first. Pure.

    A CONSTANT channel answers 0 unconditionally: ``variant`` is an error on one
    (there is no bake to count), so the staging never carries a live value there.
    """
    if is_constant_source(getattr(entry, "source", "")):
        return 0
    try:
        return max(0, int(getattr(entry, "variant", 0) or 0))
    except (TypeError, ValueError):
        return 0


def project_variant_spec(project) -> tuple:
    """``((map_type, (name per occurrence, ...)), ...)`` for one project. Pure.

    One entry per map type **present in the stack**, including the types with a
    single bake: the count is what tells an unresolved ordinal ("this project has
    1 AO") apart from an unknown map type, so the validator needs the ones. The
    order within a type is the pinned ordinal -- map-stack order with the phantom
    "+" row skipped.

    The names are each bake's *effective* output suffix (user-set, or the one the
    map stack auto-generates when a second same-type bake appears), i.e. what the
    artist already sees on that row. They are display-only.
    """
    if project is None:
        return ()
    try:
        from . import properties
    except Exception:  # pragma: no cover - defensive
        properties = None

    rows: list[tuple[str, list[str]]] = []
    index: dict[str, list[str]] = {}
    for item in getattr(project, "maps", ()) or ():
        if bool(getattr(item, "is_add_phantom", False)):
            continue
        map_type = str(getattr(item, "map_type", "") or "").strip().upper()
        if not map_type:
            continue
        label = ""
        if properties is not None:
            try:
                label = str(properties.effective_map_output_suffix(project, item) or "").strip()
            except Exception:
                label = ""
        if not label:
            label = str(getattr(item, "output_suffix", "") or "").strip()
        bucket = index.get(map_type)
        if bucket is None:
            bucket = []
            index[map_type] = bucket
            rows.append((map_type, bucket))
        bucket.append(label)
    return tuple((map_type, tuple(labels)) for map_type, labels in rows)


def multi_variant_spec(spec) -> tuple:
    """Only the types this project has **more than one** bake of. Pure.

    This is what the assignment dropdown is keyed on, and it is what keeps a
    project with one bake per type behaving exactly as it did before variants
    existed: it reduces to ``()``, which is also what "no project" reduces to, so
    the menu is built from the identical cache key either way.
    """
    return tuple(
        (str(map_type).strip().upper(), tuple(str(label or "") for label in labels))
        for map_type, labels in (spec or ())
        if len(tuple(labels)) > 1
    )


def variant_count(spec, map_type) -> int:
    """How many bakes of ``map_type`` the spec says the project holds. Pure."""
    wanted = str(map_type or "").strip().upper()
    for candidate, labels in (spec or ()):
        if str(candidate).strip().upper() == wanted:
            return len(tuple(labels))
    return 0


def variant_display_names(map_type, spec=()) -> tuple:
    """One name per occurrence of ``map_type``, guaranteed **distinct**. Pure.

    Display only. Normally each bake's own name, because that is the word the
    artist recognises off the map stack -- but nothing stops a project from
    naming two of its bakes the same thing (or naming neither), and two menu rows
    reading ``Ambient Occlusion · Raycast`` would look unpickable even though
    their identifiers differ. A blank or already-taken name therefore falls back
    to the bare ordinal, which is unique by construction.
    """
    names: tuple = ()
    wanted = str(map_type or "").strip().upper()
    for candidate, labels in (spec or ()):
        if str(candidate).strip().upper() == wanted:
            names = tuple(str(label or "").strip() for label in labels)
            break
    resolved: list[str] = []
    seen: set[str] = set()
    for ordinal, name in enumerate(names):
        if not name or name.casefold() in seen:
            name = ordinal_word(ordinal + 1)
        seen.add(name.casefold())
        resolved.append(name)
    return tuple(resolved)


def variant_display_name(map_type, variant, spec=()) -> str:
    """What to CALL one occurrence in the UI. Display only; never stored. Pure.

    This project's own name for that bake when it has one -- "Fine", "Wide". The
    bare ordinal ("2nd") when it cannot: the project has no such bake (a template
    authored elsewhere), or :func:`variant_display_names` had to disambiguate it.
    """
    ordinal = max(0, int(variant or 0))
    names = variant_display_names(map_type, spec)
    return names[ordinal] if ordinal < len(names) else ordinal_word(ordinal + 1)


#: One-slot memo of the open project's spec, keyed on a *cheap* signature of the
#: map stack. ``project_variant_spec`` calls ``effective_map_output_suffix`` per
#: row, which is quadratic in the same-type count -- fine once, wasteful on every
#: redraw of every dropdown in the editor. The signature carries exactly what a
#: label depends on (type, explicit suffix, mode label), so a stale answer is not
#: reachable by editing the stack.
_VARIANT_SPEC_SIGNATURE: tuple = ()
_VARIANT_SPEC_CACHED = None


def _project_stack_signature(project) -> tuple:
    try:
        from . import properties
    except Exception:  # pragma: no cover - defensive
        properties = None
    rows: list[tuple] = []
    for item in getattr(project, "maps", ()) or ():
        if bool(getattr(item, "is_add_phantom", False)):
            continue
        mode = ""
        if properties is not None:
            try:
                mode = str(properties.map_mode_label(item) or "")
            except Exception:
                mode = ""
        rows.append(
            (
                str(getattr(item, "map_type", "") or "").strip().upper(),
                str(getattr(item, "output_suffix", "") or "").strip(),
                mode,
            )
        )
    return tuple(rows)


def current_variant_spec(context=None):
    """The open project's spec, or ``None`` when there is no project at all.

    ``None`` and ``()`` are deliberately different answers: "we cannot know what
    this project has" (Preferences open with no project, headless tests) versus
    "it has no baked maps". Only the first suppresses the unresolved-occurrence
    warning -- guessing a count we do not have would either invent a warning or
    hide a real one.
    """
    global _VARIANT_SPEC_SIGNATURE, _VARIANT_SPEC_CACHED
    try:
        from . import properties

        scene = getattr(context or bpy.context, "scene", None)
        # peek, not get: this runs from draw and must not create a project.
        project = properties.peek_active_project(scene) if scene is not None else None
    except Exception:
        return None
    if project is None:
        return None
    signature = _project_stack_signature(project)
    if _VARIANT_SPEC_CACHED is None or signature != _VARIANT_SPEC_SIGNATURE:
        _VARIANT_SPEC_CACHED = project_variant_spec(project)
        _VARIANT_SPEC_SIGNATURE = signature
    return _VARIANT_SPEC_CACHED


def current_menu_variants(context=None) -> tuple:
    """:func:`multi_variant_spec` of the open project -- what the menu is keyed on."""
    return multi_variant_spec(current_variant_spec(context) or ())


# ---------------------------------------------------------------------------
# The assignment dropdown
#
# The assignment control is a real ``EnumProperty`` drawn with
# ``layout.prop(entry, "assignment", text="")``: Blender then renders its own
# dropdown -- text left-aligned, chevron on the right, native rounded styling --
# instead of an operator button with a chevron glyph faked onto its left.
#
# Three facts about dynamic enums this depends on, all verified on screen in
# Blender 5.1 before the code was written:
#
# * an item whose **identifier is empty** (``("", "Mesh Maps", "")``) draws as a
#   non-selectable group heading, which is how the menu gets its three sections;
# * an item's icon slot takes either an icon *name* or an integer ``icon_value``,
#   so :func:`swatch_icon_value`'s generated chips can be per-item icons -- and
#   the button shows the selected item's icon, which is the assigned/unassigned
#   indicator;
# * the items callback must not hand Blender temporary strings. Everything below
#   is cached at MODULE level; a freed items tuple draws as garbage, not as
#   nothing.
#
# The item *number* is stable per identifier for the lifetime of the cache, and
# the property's ``get``/``set`` translate between that number and the staged
# ``source`` (+ ``constant``) -- so the dropdown has no storage of its own and
# can never disagree with the data the JSON is written from.
# ---------------------------------------------------------------------------

#: Item identifier for "no map assigned". Not ``""``: an empty identifier is how
#: a heading is spelled, and an enum cannot store the empty string anyway.
UNASSIGNED_ITEM = "__NONE__"

#: Icon for the Unassigned row. Blender's empty radio button reads as "nothing
#: in this slot" next to a column of filled colour chips.
UNASSIGNED_ITEM_ICON = "RADIOBUT_OFF"

#: Menu items that are not maps, so cannot have occurrences: Unassigned and the
#: four constant picks. They share the item-number space with the maps, which is
#: why :func:`assignment_identifier_for_number` has to exclude them explicitly.
NON_MAP_ITEMS: frozenset[str] = frozenset(
    {UNASSIGNED_ITEM, CONSTANT_ITEM_CUSTOM} | {identifier for identifier, _label, _value in CONSTANT_PRESETS}
)

#: The dropdown's three group headings, in menu order.
ASSIGNMENT_GROUP_MATERIAL = "Material Channels"
ASSIGNMENT_GROUP_MESH = "Mesh Maps"
ASSIGNMENT_GROUP_CONSTANTS = "Constants"

#: ``(selected, component suffix, project variants) -> items tuple``. Module-level
#: *and* never evicted while the addon is enabled: RNA borrows the strings inside.
#: The variant spec joined the key rather than replacing the memo, because the
#: menu's *text* now depends on the open project (a bake's own name labels its
#: row) -- and a tuple rebuilt per draw is exactly the freed-string bug the whole
#: cache exists to prevent.
_ASSIGNMENT_ITEMS_CACHE: dict[tuple, tuple] = {}

#: identifier <-> stable item number, built once alongside the first item list.
#: **Occurrence 0 only** -- see :data:`VARIANT_NUMBER_STRIDE`.
_ASSIGNMENT_NUMBERS: dict[str, int] = {}
_ASSIGNMENT_IDENTIFIERS: dict[int, str] = {}

#: How an occurrence ordinal is folded into an enum item number.
#:
#: Item numbers must be stable *for a given menu*, and the menu's length now
#: depends on the open project -- three AO bakes add two rows that a one-AO
#: project does not have. Enumerating the items positionally would therefore
#: renumber every item after AO the moment a project with a different stack was
#: opened, and a stored number would read back as a different map.
#:
#: So numbers are not positions at all: an occurrence's number is *computed*,
#: ``base number + ordinal * STRIDE``. ``AO`` is 12 in every project, ``AO#1`` is
#: 1012 in every project, ``AO#2`` is 2012 -- whether or not that project has
#: them. The stride is an order of magnitude above the number of base identifiers
#: (~35 today), so the bands can never collide; :func:`_assignment_numbers`
#: asserts that as it builds.
VARIANT_NUMBER_STRIDE = 1000


def assignment_identifiers() -> tuple[str, ...]:
    """Every selectable item identifier, in menu order. Headings excluded."""
    material, mesh = (items for _title, items in grouped_source_items())
    return (
        (UNASSIGNED_ITEM,)
        + tuple(identifier for identifier, _label, _description in material)
        + tuple(identifier for identifier, _label, _description in mesh)
        + tuple(identifier for identifier, _label, _value in CONSTANT_PRESETS)
        + (CONSTANT_ITEM_CUSTOM,)
    )


def _assignment_numbers() -> dict[str, int]:
    """identifier -> item number, for occurrence 0. Built once; never persisted."""
    if not _ASSIGNMENT_NUMBERS:
        for number, identifier in enumerate(assignment_identifiers()):
            # An overflow here would make ``AO#1`` collide with some other map's
            # base number, i.e. one stored assignment silently reading back as a
            # different map. Refusing to number at all is the safe failure: every
            # identifier then answers 0 (Unassigned) instead of a wrong map.
            if number >= VARIANT_NUMBER_STRIDE:  # pragma: no cover - ~35 items today
                _ASSIGNMENT_NUMBERS.clear()
                _ASSIGNMENT_IDENTIFIERS.clear()
                break
            _ASSIGNMENT_NUMBERS[identifier] = number
            _ASSIGNMENT_IDENTIFIERS[number] = identifier
    return _ASSIGNMENT_NUMBERS


def assignment_number(identifier) -> int:
    """Item number for an item identifier; unknown falls back to Unassigned.

    ``AO#2`` answers ``base("AO") + 2 * STRIDE`` -- computed, not looked up, so
    the number of a given occurrence is the same in every project regardless of
    how many bakes any of them holds. See :data:`VARIANT_NUMBER_STRIDE`.
    """
    key = str(identifier or "")
    numbers = _assignment_numbers()
    direct = numbers.get(key)
    if direct is not None:
        return direct
    base, ordinal = split_source_key(key)
    if ordinal <= DEFAULT_VARIANT:
        return 0
    base_number = numbers.get(base)
    if base_number is None:
        return 0
    return base_number + ordinal * VARIANT_NUMBER_STRIDE


def assignment_identifier_for_number(number) -> str:
    """Item identifier for an item number; unknown falls back to Unassigned."""
    _assignment_numbers()
    try:
        value = int(number)
    except (TypeError, ValueError):
        return UNASSIGNED_ITEM
    if value < 0:
        return UNASSIGNED_ITEM
    ordinal, base_number = divmod(value, VARIANT_NUMBER_STRIDE)
    base = _ASSIGNMENT_IDENTIFIERS.get(base_number)
    if base is None:
        return UNASSIGNED_ITEM
    if ordinal <= DEFAULT_VARIANT:
        return base
    # Only a *map* has occurrences to count. Unassigned and the constants sit in
    # the same number space, so a stray high number must not come back as
    # ``__NONE__#7`` -- an identifier no menu contains and no writer understands.
    if base in NON_MAP_ITEMS:
        return UNASSIGNED_ITEM
    return build_source_key(base, ordinal)


def assignment_item_icon(identifier):
    """The item's status icon: a colour chip when assigned, empty when not.

    Returns an ``int`` (a generated chip's ``icon_value``) or a ``str`` (an icon
    name). Blender accepts either in an enum item's icon slot; ``0`` means "no
    icon", which is what the headless/stripped case degrades to.

    Every occurrence of a map wears that **map's** colour: the ordinal says which
    bake, not which kind of data, so a second AO that stopped being AO-coloured
    would be lying about what it is.
    """
    key = str(identifier or "")
    if not key or key == UNASSIGNED_ITEM:
        return UNASSIGNED_ITEM_ICON
    base, _ordinal = split_source_key(key)
    return swatch_icon_value(base or key)


def assignment_items_tuple(current: str = UNASSIGNED_ITEM, suffix: str = "", variants: tuple = ()) -> tuple:
    """The dropdown's items, with ``suffix`` folded into the selected one.

    Blender draws the *selected item's name* on the button, and the readable
    assignment is "which map" **plus** "which part of it" -- so the item that is
    currently selected carries the component (``Material: Albedo · RGB``) while
    the other rows stay plain map names. That is what keeps the button's text the
    assignment without giving every row a component it does not have.

    ``variants`` is :func:`multi_variant_spec` of the **open project**: only the
    map types it holds more than one bake of. A type listed there expands into
    one row per bake, each labelled with that bake's own name (``Ambient
    Occlusion · Fine``) so the artist recognises it; every other type draws the
    single plain row it always drew. A project with one bake per type passes
    ``()`` and gets a menu identical to the pre-variant one, down to the cache key.

    One further row is synthesised when the selection needs it: a template
    authored elsewhere may address an occurrence this project does not have, and
    that assignment must stay **visible and unchanged** rather than being
    silently re-pointed at occurrence 0. It is labelled by bare ordinal
    (``Ambient Occlusion · 2nd``), because this project has no name for a bake it
    does not hold.

    Pure apart from :func:`swatch_icon_value`, and memoised on
    ``(current, suffix, variants)``: the tuple handed to RNA must outlive the draw.
    """
    selected = str(current or UNASSIGNED_ITEM)
    tail = str(suffix or "")
    spec = multi_variant_spec(variants)
    cached = _ASSIGNMENT_ITEMS_CACHE.get((selected, tail, spec))
    if cached is not None:
        return cached

    def row(identifier: str, label: str, description: str):
        text = f"{label} · {tail}" if tail and identifier == selected else label
        return (identifier, text, description, assignment_item_icon(identifier), assignment_number(identifier))

    def source_rows(identifier: str, label: str, description: str) -> list[tuple]:
        """One row per map type; stack index is chosen separately."""
        return [row(identifier, label, description)]

    material, mesh = (items for _title, items in grouped_source_items())
    items: list[tuple] = [
        row(UNASSIGNED_ITEM, UNASSIGN_LABEL, "Leave this output channel empty (writes zeros)")
    ]
    for title, group in (
        (ASSIGNMENT_GROUP_MATERIAL, material),
        (ASSIGNMENT_GROUP_MESH, mesh),
    ):
        # An empty identifier is a heading, not a pick. Verified on screen.
        items.append(("", title, ""))
        for identifier, label, description in group:
            items.extend(source_rows(identifier, label, description))

    items.append(("", ASSIGNMENT_GROUP_CONSTANTS, ""))
    for identifier, label, value in CONSTANT_PRESETS:
        items.append(row(identifier, label, f"Write a flat {format_constant(value)} into this channel"))
    items.append(row(CONSTANT_ITEM_CUSTOM, "Custom", "Write a flat value you choose into this channel"))

    built = tuple(items)
    _ASSIGNMENT_ITEMS_CACHE[(selected, tail, spec)] = built
    return built


def _invalidate_assignment_items() -> None:
    """Drop the memo so the next build picks up freshly generated chip icons."""
    _ASSIGNMENT_ITEMS_CACHE.clear()


def entry_assignment_identifier(entry) -> str:
    """Which map-type dropdown item a staged channel entry currently *is*. Pure."""
    source = str(getattr(entry, "source", "") or "").strip().upper()
    if not source:
        return UNASSIGNED_ITEM
    if is_constant_source(source):
        if bool(getattr(entry, "constant_custom", False)):
            return CONSTANT_ITEM_CUSTOM
        return constant_preset_item(getattr(entry, "constant", 0.0)) or CONSTANT_ITEM_CUSTOM
    if source not in _assignment_numbers():
        return UNASSIGNED_ITEM
    return source


def entry_assignment_suffix(entry, output=None) -> str:
    """The ``· <tail>`` half of the assignment button's text for this entry. Pure.

    A **map** answers with nothing: "which channel of it" and "which bake of it"
    are the channel-options popover's two questions now, and repeating either on
    the assignment button would state it twice in one row (and stretch the
    button past the words that actually name the map).

    A **Custom constant** still answers with its value -- ``Custom · 0.25`` --
    because it has no popover, and the value is the whole assignment.
    """
    source = str(getattr(entry, "source", "") or "").strip().upper()
    if not source:
        return ""
    if is_constant_source(source):
        return format_constant(getattr(entry, "constant", 0.0)) if entry_is_custom_constant(entry) else ""
    del output
    return ""


def entry_is_custom_constant(entry) -> bool:
    """Whether this entry's value field should be drawn. Pure.

    Only for a **Custom** constant: Black / Gray / White are the value, so a
    field next to them would just be a second way to say the same thing (and a
    way to dial one of them off its preset by accident)."""
    if not is_constant_source(getattr(entry, "source", "")):
        return False
    if bool(getattr(entry, "constant_custom", False)):
        return True
    return not constant_preset_item(getattr(entry, "constant", 0.0))


def assignment_button_text(entry, output=None, variants: tuple = ()) -> str:
    """What the dropdown draws on itself: its selected item's name. Pure.

    Blender puts the selected item's label on the button, so this is the one
    place the readable assignment ("Material: Albedo · RGB" / "Unassigned") is
    decided -- there is no separate button text to keep in step with the menu.
    """
    identifier = entry_assignment_identifier(entry)
    for candidate, label, *_rest in assignment_items_tuple(
        identifier, entry_assignment_suffix(entry, output), variants
    ):
        if candidate == identifier:
            return label
    return UNASSIGN_LABEL


def _stack_index_number_get(self):
    """The field is **one-based**: the artist counts bakes from 1, like the map stack."""
    return entry_variant(self) + 1


def _stack_index_number_set(self, value):
    try:
        ordinal = max(0, int(value) - 1)
    except (TypeError, ValueError):
        ordinal = DEFAULT_VARIANT
    state = editor_state()
    output = entry_output(self, state)
    block = block_for_slot(output, str(getattr(self, "slot", "") or ""))
    if output is None or block is None:
        return
    with suspend_autosave():
        set_block_variant(output, block, ordinal)
    autosave(state)


def _assignment_items(self, context):
    return assignment_items_tuple(
        entry_assignment_identifier(self),
        entry_assignment_suffix(self, entry_output(self)),
        current_menu_variants(context),
    )


def _assignment_get(self):
    return assignment_number(entry_assignment_identifier(self))


def _assignment_set(self, value):
    """One click = one assignment, written through the block and autosaved.

    The dropdown has no storage of its own, so this is where a pick becomes
    data: resolve the entry's output and block, write every slot of that block,
    then autosave once.
    """
    state = editor_state()
    output = entry_output(self, state)
    if output is None:
        return
    block = block_for_slot(output, str(getattr(self, "slot", "") or ""))
    if block is None:
        return
    with suspend_autosave():
        assign_block_item(output, block, assignment_identifier_for_number(value))
    autosave(state)


#: ``outputs[3]`` out of an RNA path, so an entry can name its own output in
#: O(1) instead of a scan. The scan stays as the fallback -- ``path_from_id`` is
#: not available on the plain objects the headless tests stage.
_OUTPUT_INDEX_RE = re.compile(r"outputs\[(\d+)\]")


def entry_output(entry, state=None):
    """The staged output that owns this channel entry, or ``None``.

    The dropdown lives on the *channel*, but an assignment is written through
    the *block*, which only the output knows about -- so the entry has to be
    able to find its way back up. RNA gives no parent pointer; the property path
    does.
    """
    if entry is None:
        return None
    if state is None:
        state = editor_state()
    outputs = list(getattr(state, "outputs", ()) or ()) if state is not None else []
    if not outputs:
        return None

    def owns(candidate) -> bool:
        for other in getattr(candidate, "channels", ()) or ():
            if other == entry:
                return True
        return False

    try:
        match = _OUTPUT_INDEX_RE.search(str(entry.path_from_id() or ""))
    except Exception:
        match = None
    if match is not None:
        index = int(match.group(1))
        if 0 <= index < len(outputs) and owns(outputs[index]):
            return outputs[index]
    for candidate in outputs:
        if owns(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Staging state
# ---------------------------------------------------------------------------

#: Set while a bulk write into live RNA is in flight -- :func:`template_to_staging`
#: loading a file, or an operator rebuilding a whole output -- so the ``update=``
#: callbacks below do not autosave a half-written buffer. Every such section ends
#: in exactly one explicit :func:`autosave`.
_LOADING = False


@contextmanager
def suspend_autosave():
    """Silence the autosave funnel for the duration of a bulk mutation.

    Saves and restores rather than clearing, so nesting (an operator wrapping a
    helper that wraps itself) cannot re-arm autosave halfway through.
    """
    global _LOADING
    previous = _LOADING
    _LOADING = True
    try:
        yield
    finally:
        _LOADING = previous


def _autosave_edit(self, context) -> None:
    """``update=`` hook shared by every staging property.

    Every widget in the editor is bound to a staged property, so this is the
    funnel a *typed* edit reaches autosave through; the operators (assign,
    invert, add/remove/move output, insert token) call :func:`autosave`
    themselves after their multi-field write. Blender fires a text field's
    ``update`` once on confirm, not per keystroke, so writing synchronously here
    is one small JSON write per edit -- no debounce needed.
    """
    del self
    if _LOADING:
        return
    autosave(editor_state(context))


def _format_changed(self, context) -> None:
    """Keep the bit depth legal when the file type changes under it."""
    try:
        current = int(self.get("bit_depth_value", DEFAULT_BIT_DEPTH) or DEFAULT_BIT_DEPTH)
    except (TypeError, ValueError):
        current = DEFAULT_BIT_DEPTH
    with suspend_autosave():
        set_output_bit_depth(self, current)
    _autosave_edit(self, context)


#: Every write that spans more than one slot goes through an operator
#: (:class:`MASTER_BAKER_OT_template_editor_assign_source` and friends) rather
#: than through a widget's ``update=`` hook, so there is no propagation to guard
#: against here: the only widgets bound directly to a channel are the
#: single-slot source-channel dropdown and nothing else.
def _channel_edited(self, context) -> None:
    _autosave_edit(self, context)


class MASTER_BAKER_PG_template_editor_channel(bpy.types.PropertyGroup):
    """One RGBA slot of one output. ``enabled`` off == JSON ``null``."""

    slot: bpy.props.StringProperty(name="Slot", default="R", options={"HIDDEN"})
    enabled: bpy.props.BoolProperty(
        name="Enabled",
        default=False,
        description="Feed this output channel from a baked map. Off writes the JSON null (zeros)",
        update=_channel_edited,
    )
    #: A **string**, not an enum: "" is a first-class value here -- the slot
    #: exists in the output's shape but no map is assigned to it yet -- and an
    #: EnumProperty cannot hold the empty string. Nothing binds this to a widget
    #: (assignment goes through the source panel's operator, which validates the
    #: identifier), so the enum bought nothing that ``valid_source_or_empty``
    #: does not.
    source: bpy.props.StringProperty(
        name="Source Map",
        description="Baked map this channel reads from. Empty means unassigned",
        default="",
        update=_channel_edited,
        options={"HIDDEN"},
    )
    #: Which bake of ``source`` this channel reads, when the project holds more
    #: than one: a 0-based occurrence ordinal in map-stack order. 0 -- "the first
    #: one" -- is the default and is NOT serialised, so every template written
    #: before variants existed keeps its exact bytes and its exact meaning. The
    #: ordinal is what travels between projects; the bake's *name* never leaves
    #: the UI. Meaningless on a CONSTANT channel (see :func:`entry_variant`).
    variant: bpy.props.IntProperty(
        name="Variant",
        description=(
            "Which bake of this map to read when the project has several: 1 for the "
            "first, 2 for the second, counted down the map stack"
        ),
        default=0,
        min=0,
        update=_channel_edited,
        options={"HIDDEN"},
    )
    #: The stack index as the artist counts it (1 == the first bake of this
    #: type). A **field**, not an enum: a template is authored for projects that
    #: are not open, so the index it may name cannot be bounded by what the
    #: current map stack happens to hold. No ``max`` for the same reason.
    stack_index_number: bpy.props.IntProperty(
        name="Stack Index",
        description=(
            "Which bake of this map type to read, counted down the map stack: "
            "1 for the first, 2 for the second"
        ),
        default=1,
        min=1,
        soft_max=STACK_INDEX_SOFT_MAX,
        get=_stack_index_number_get,
        set=_stack_index_number_set,
    )
    channel: bpy.props.EnumProperty(
        name="Source Channel",
        description="Which channel of the source map to read",
        items=SOURCE_CHANNEL_ITEMS,
        default="GRAY",
        update=_channel_edited,
    )
    invert: bpy.props.BoolProperty(
        name="Invert",
        default=False,
        description="Invert this channel: write 1 - value (roughness to smoothness, AO to occlusion)",
        update=_channel_edited,
    )
    #: Flat value written when ``source`` is ``CONSTANT``. Meaningless (and not
    #: serialised) otherwise -- the contract makes ``"constant"`` legal only on a
    #: CONSTANT channel.
    constant: bpy.props.FloatProperty(
        name="Value",
        description="Flat value written into this channel, 0 (black) to 1 (white)",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_channel_edited,
    )
    #: Staging-only: "the artist picked Custom, not a preset". Derived on load
    #: (a value that is not one of the three presets *is* custom) and never
    #: written to the file, so it costs the JSON nothing. Without it, dialling a
    #: custom value to exactly 0.5 would silently turn back into the Gray preset
    #: and take its own value field away.
    constant_custom: bpy.props.BoolProperty(name="Custom Value", default=False, options={"HIDDEN"})
    #: The assignment dropdown. No storage: ``get``/``set`` translate between the
    #: item number and ``source`` (+ ``constant``), so the widget can never
    #: disagree with what the JSON is written from. See the section above.
    assignment: bpy.props.EnumProperty(
        name="Assignment",
        description="Which map (or flat value) this output channel reads",
        items=_assignment_items,
        get=_assignment_get,
        set=_assignment_set,
    )


class MASTER_BAKER_PG_template_editor_output(bpy.types.PropertyGroup):
    """One exported file of the template."""

    filename: bpy.props.StringProperty(
        name="Filename",
        default=DEFAULT_FILENAME,
        description="Filename template, without extension. Use the $ menu to append a token",
        update=_autosave_edit,
    )
    format: bpy.props.EnumProperty(
        name="File Type",
        items=IMAGE_FORMAT_ITEMS,
        default=DEFAULT_FORMAT,
        update=_format_changed,
    )
    bit_depth: bpy.props.EnumProperty(
        name="Bit Depth",
        description="Bits per channel. Only depths this file type can store are offered",
        items=_bit_depth_items,
        update=_autosave_edit,
    )
    color_space: bpy.props.EnumProperty(
        name="Color Space",
        items=COLOR_SPACE_ITEMS,
        default=DEFAULT_COLOR_SPACE,
        update=_autosave_edit,
    )
    dds_compression: bpy.props.EnumProperty(
        name="Compression",
        items=constants.EXPORT_DDS_COMPRESSION_ITEMS,
        default=constants.EXPORT_DDS_BC7,
        description=(
            "Block compression for this DDS output. Set per output because one "
            "texture set has no single right answer: normals want BC5, "
            "single-channel masks BC4, colour BC7 or BC1"
        ),
        update=_autosave_edit,
    )
    notes: bpy.props.StringProperty(
        name="Notes",
        default="",
        description="Free-form note stored with this output map",
        update=_autosave_edit,
    )
    channels: bpy.props.CollectionProperty(type=MASTER_BAKER_PG_template_editor_channel)


#: Guards the mirror collection against re-entering itself. ``template_index``'s
#: update callback loads a template, which writes a dozen staged fields and may
#: itself want to move the index; without this flag the two chase each other.
_SYNCING_TEMPLATES = False

#: One pending ``bpy.app.timers`` rebuild at a time. ``draw`` can notice the same
#: mismatch on every redraw of every open Preferences area.
_REFRESH_SCHEDULED = False


class MASTER_BAKER_PG_template_editor_item(bpy.types.PropertyGroup):
    """One row of the template UIList.

    A **mirror** of what ``export_templates.list_templates()`` found on disk, not
    a source of truth: the JSON files are. It exists only because
    ``UILayout.template_list`` can iterate a ``CollectionProperty`` and nothing
    else, and a real UIList is what gives the column its scrollbar, its filter
    field and its full-height pane.
    """

    name: bpy.props.StringProperty(name="Name", default="")
    builtin: bpy.props.BoolProperty(name="Built-in", default=False)


def _template_index_changed(self, context) -> None:
    """Selecting a row loads that template into the staging buffer."""
    if _SYNCING_TEMPLATES:
        return
    items = getattr(self, "templates", None)
    if not items:
        return
    index = int(getattr(self, "template_index", 0) or 0)
    if not (0 <= index < len(items)):
        return
    name = str(getattr(items[index], "name", "") or "")
    if not name or name == str(getattr(self, "selected_name", "") or ""):
        return
    error = load_into_staging(self, name)
    if error:
        self.error = error
    del context


class MASTER_BAKER_PG_template_editor_state(bpy.types.PropertyGroup):
    """The whole scratch buffer: one template being edited, plus the selection."""

    #: Mirror of the templates on disk; see the class docstring above.
    templates: bpy.props.CollectionProperty(type=MASTER_BAKER_PG_template_editor_item)
    template_index: bpy.props.IntProperty(
        name="Template",
        default=-1,
        description="Output template being edited",
        update=_template_index_changed,
    )
    #: Name of the row highlighted in the left-hand list (may be a built-in).
    selected_name: bpy.props.StringProperty(name="Selected", default="", options={"HIDDEN"})
    #: Editable name of the staged template.
    template_name: bpy.props.StringProperty(
        name="Name",
        default="",
        description="Template name, as it appears in the export dialog's dropdown",
        update=_autosave_edit,
    )
    #: Built-in this staging buffer was duplicated from, for the header hint.
    source_builtin_name: bpy.props.StringProperty(name="Duplicated From", default="", options={"HIDDEN"})
    notes: bpy.props.StringProperty(
        name="Notes",
        default="",
        description="Free-form description stored with the template",
        update=_autosave_edit,
    )
    outputs: bpy.props.CollectionProperty(type=MASTER_BAKER_PG_template_editor_output)
    active_output_index: bpy.props.IntProperty(name="Active Output", default=0, min=0)
    #: Anchor slot of the selected channel block ("" == nothing selected). Stored
    #: as a *slot*, not as a block key, so a selection survives an assignment that
    #: regroups the blocks under it (three split slots merging into one Gray).
    active_slot: bpy.props.StringProperty(name="Active Block", default="", options={"HIDDEN"})
    loaded: bpy.props.BoolProperty(name="Loaded", default=False)
    #: Path the staging was loaded from, and the file autosave keeps in step: a
    #: rename writes the new file and deletes this one. Empty for a built-in
    #: (nothing here may be written) and for a buffer not yet on disk.
    loaded_from: bpy.props.StringProperty(name="Loaded From", default="", options={"HIDDEN"})
    #: Last autosave/validation failure, shown as an error box until an edit that
    #: does save. There is no dirty flag: every valid edit is already on disk.
    error: bpy.props.StringProperty(name="Error", default="", options={"HIDDEN"})


def editor_state(context=None):
    """The staging buffer on the WindowManager, or ``None`` before registration."""
    window_manager = getattr(context or bpy.context, "window_manager", None)
    if window_manager is None:
        window_manager = next(iter(getattr(bpy.data, "window_managers", []) or []), None)
    return getattr(window_manager, "master_baker_template_editor", None)


# ---------------------------------------------------------------------------
# The template-list mirror
#
# ``template_list`` needs a CollectionProperty, and a CollectionProperty must
# never be written from ``draw`` -- Blender's UI code is re-entrant over the data
# it is drawing and a resize mid-draw is a crash, not a glitch. So: every
# operator that touches the store on disk refreshes the mirror explicitly, and
# ``draw`` only ever *detects* a mismatch and defers the rebuild to a one-shot
# app timer.
# ---------------------------------------------------------------------------


def build_template_items(infos) -> tuple[tuple[str, bool], ...]:
    """``(name, builtin)`` rows for the UIList. Pure; no bpy calls."""
    rows: list[tuple[str, bool]] = []
    for info in infos or ():
        name = str(getattr(info, "name", "") or "")
        if name:
            rows.append((name, bool(getattr(info, "builtin", False))))
    return tuple(rows)


def template_items_match(collection, rows) -> bool:
    """True when the mirror already says exactly ``rows`` (count *and* names)."""
    existing = tuple(
        (str(getattr(item, "name", "") or ""), bool(getattr(item, "builtin", False)))
        for item in collection or ()
    )
    return existing == tuple(rows)


def apply_template_items(collection, rows) -> None:
    """Rewrite ``collection`` to ``rows``. Duck-typed, so it is unit-testable."""
    collection.clear()
    for name, builtin in rows:
        item = collection.add()
        item.name = name
        item.builtin = bool(builtin)


def index_of_template(rows, name: str) -> int:
    """Row index of ``name`` (case-insensitive), or ``-1``."""
    wanted = str(name or "").strip().casefold()
    if not wanted:
        return -1
    for index, (candidate, _builtin) in enumerate(rows):
        if candidate.casefold() == wanted:
            return index
    return -1


def template_infos():
    """The templates on disk, through the export dialog's short-TTL cache."""
    try:
        from . import export_dialog

        infos = tuple(export_dialog.cached_template_infos())
        if infos:
            return infos
    except Exception:
        pass
    try:
        return tuple(export_templates.list_templates())
    except Exception:
        return ()


def refresh_template_items(state=None, *, select=None) -> None:
    """Rebuild the mirror from disk and re-point ``template_index`` at ``select``.

    Never call this from ``draw`` -- see the section comment above.
    """
    global _SYNCING_TEMPLATES
    if state is None:
        state = editor_state()
    if state is None:
        return
    rows = build_template_items(template_infos())
    wanted = select if select is not None else str(getattr(state, "selected_name", "") or "")
    _SYNCING_TEMPLATES = True
    try:
        apply_template_items(state.templates, rows)
        state.template_index = index_of_template(rows, wanted)
    except Exception:
        pass
    finally:
        _SYNCING_TEMPLATES = False


def sync_template_index(state, name: str) -> None:
    """Point the UIList at ``name`` without re-triggering the load callback."""
    global _SYNCING_TEMPLATES
    if state is None:
        return
    rows = build_template_items(getattr(state, "templates", ()) or ())
    _SYNCING_TEMPLATES = True
    try:
        state.template_index = index_of_template(rows, name)
    except Exception:
        pass
    finally:
        _SYNCING_TEMPLATES = False


def _tag_preferences_redraw() -> None:
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "PREFERENCES":
                    area.tag_redraw()
    except Exception:
        pass


def _deferred_template_refresh():
    global _REFRESH_SCHEDULED
    _REFRESH_SCHEDULED = False
    refresh_template_items()
    _tag_preferences_redraw()
    return None


def _schedule_template_refresh() -> None:
    """One-shot rebuild on the next timer tick. Safe to call from ``draw``."""
    global _REFRESH_SCHEDULED
    if _REFRESH_SCHEDULED:
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None:
        return
    _REFRESH_SCHEDULED = True
    try:
        timers.register(_deferred_template_refresh, first_interval=0.0)
    except Exception:
        _REFRESH_SCHEDULED = False


# ---------------------------------------------------------------------------
# Pure staging <-> JSON conversion
# ---------------------------------------------------------------------------


def output_bit_depth(output) -> int:
    """Read an output's bit depth defensively.

    A dynamic enum whose stored number is not in the current item list reads back
    as an empty string rather than raising, so the fallback matters.
    """
    try:
        raw = output.bit_depth
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_BIT_DEPTH
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_BIT_DEPTH


def set_output_bit_depth(output, value) -> int:
    """Assign a bit depth, clamped to what the output's format can store."""
    try:
        requested = int(str(value))
    except (TypeError, ValueError):
        requested = DEFAULT_BIT_DEPTH
    format_id = str(getattr(output, "format", DEFAULT_FORMAT) or DEFAULT_FORMAT)
    try:
        depth = export_pack.clamp_bit_depth_for_format(format_id, requested)
    except export_pack.ExportPackError:
        depth = requested
    # Mirrored into an IDProperty so _format_changed can recover the user's last
    # intent after a clamp (PNG 16 -> TGA 8 -> PNG should come back at 16).
    try:
        output["bit_depth_value"] = int(requested)
    except (TypeError, ValueError):
        pass
    try:
        output.bit_depth = str(depth)
    except (TypeError, ValueError):
        pass
    return int(depth)


def ensure_channel_slots(output) -> None:
    """Give an output exactly four channel entries, R/G/B/A in order."""
    output.channels.clear()
    for slot in CHANNEL_SLOTS:
        entry = output.channels.add()
        entry.slot = slot
        entry.enabled = False
        entry.channel = "GRAY"
        entry.variant = DEFAULT_VARIANT
        entry.invert = False
        entry.constant = 0.0
        entry.constant_custom = False


def channel_for_slot(output, slot: str):
    for entry in output.channels:
        if str(getattr(entry, "slot", "")) == slot:
            return entry
    return None


# ---------------------------------------------------------------------------
# Channel blocks (pure)
# ---------------------------------------------------------------------------


def is_gray_shaped(output) -> bool:
    """True when R, G and B are one grayscale image.

    That is: all three enabled, reading the *same, assigned* source, all through
    ``GRAY``, with the same inversion. The alpha slot is deliberately ignored -- a
    gray image plus an independent alpha is still edited as one gray row plus one
    alpha row.

    The "assigned" part is what keeps the channel-pack shapes usable. Three
    unassigned slots routed through ``GRAY`` are what BOTH "Create: Gray" and
    "Create: R+G+B" produce -- the schema stores no shape, so the two are the same
    data -- and collapsing them would leave a pack with a single chip that assigns
    all three slots at once, i.e. no way to fill only G and B. Three chips is
    therefore the honest rendering of "three empty slots"; they merge into one
    ``Gray`` block the moment all three read the same map.
    """
    entries = [channel_for_slot(output, slot) for slot in ("R", "G", "B")]
    if any(entry is None or not bool(getattr(entry, "enabled", False)) for entry in entries):
        return False
    sources = {_entry_group_key(entry) for entry in entries}
    if sources == {("", "")}:
        return False
    channels = {str(getattr(entry, "channel", "") or "").strip().upper() for entry in entries}
    inversions = {bool(getattr(entry, "invert", False)) for entry in entries}
    return len(sources) == 1 and channels == {"GRAY"} and len(inversions) == 1


def is_rgb_shaped(output) -> bool:
    """True when R, G and B are one *color* image: one source, identity routing.

    ``R←source.R, G←source.G, B←source.B`` with a single inversion state. This is
    the Normal / BaseColor case, and the reason it groups is that an artist never
    reassigns one channel of a normal map: the three move together or not at all.

    Unlike :func:`is_gray_shaped` this holds for an *unassigned* triple as well:
    identity routing is only ever produced by the "RGB" shape, so it is an
    unambiguous signature, and a fresh RGB output must stay one chip that assigns
    all three slots together.
    """
    entries = [channel_for_slot(output, slot) for slot in ("R", "G", "B")]
    if any(entry is None or not bool(getattr(entry, "enabled", False)) for entry in entries):
        return False
    sources = {_entry_group_key(entry) for entry in entries}
    routed = all(
        str(getattr(entry, "channel", "") or "").strip().upper() == slot
        for slot, entry in zip(("R", "G", "B"), entries)
    )
    inversions = {bool(getattr(entry, "invert", False)) for entry in entries}
    return len(sources) == 1 and routed and len(inversions) == 1


#: Block kinds. ``SLOT`` is one channel on its own; the other two are the two
#: ways three channels can be one thing.
BLOCK_GRAY = "GRAY"
BLOCK_RGB = "RGB"
BLOCK_SLOT = "SLOT"


class ChannelBlock:
    """One clickable chip of an output row. Derived, never stored.

    ``key`` is the block's *anchor slot* -- "R" for a Gray/RGB block, the slot
    itself otherwise -- and doubles as the selection handle written to
    ``state.active_slot``.
    """

    #: ``source`` stays the **bare** map type and ``variant`` carries the
    #: occurrence beside it, rather than the two being fused into a composite
    #: key: every palette lookup, the legend, ``is_color_source`` and the
    #: validator all ask "what kind of map is this", which the ordinal does not
    #: change. Defaulted so the five-argument constructor keeps working.
    __slots__ = ("key", "label", "kind", "slots", "source", "variant")

    def __init__(self, key: str, label: str, kind: str, slots: tuple, source: str, variant: int = 0):
        self.key = key
        self.label = label
        self.kind = kind
        self.slots = tuple(slots)
        self.source = source
        self.variant = int(variant or 0)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ChannelBlock({self.label!r}, {self.kind}, {self.slots}, "
            f"{build_source_key(self.source, self.variant)!r})"
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, ChannelBlock):
            return NotImplemented
        return (
            self.key == other.key
            and self.label == other.label
            and self.kind == other.kind
            and self.slots == other.slots
            and self.source == other.source
            and self.variant == other.variant
        )


def _entry_source(entry) -> str:
    return str(getattr(entry, "source", "") or "")


def _entry_group_key(entry) -> tuple[str, str]:
    """What makes two slots "the same thing" for the block grouping. Pure.

    The source alone is not enough once constants exist: three slots all reading
    ``CONSTANT`` are one Gray block **only** if they carry the same value, or a
    pack of black / gray / white would collapse into a single chip and hide two
    of its three values.

    The same argument makes the **occurrence** part of the key: R reading the
    first AO and G reading the second are two different images, and merging them
    into one chip would hide one of the two assignments. The ordinal rides in the
    second field (empty for occurrence 0) so an unassigned slot still keys as
    ``("", "")``, which is the sentinel :func:`is_gray_shaped` tests against.
    """
    source = _entry_source(entry)
    if is_constant_source(source):
        return (source.strip().upper(), format_constant(getattr(entry, "constant", 0.0)))
    variant = entry_variant(entry)
    return (source, str(variant) if variant else "")


def output_blocks(output) -> list:
    """The channel blocks an output draws, left to right.

    * all three of R/G/B one grayscale source -> a single ``Gray`` block;
    * all three one source with identity routing -> a single ``RGB`` block;
    * anything else -> one ``R`` / ``G`` / ``B`` block per *enabled* slot.

    Alpha is always its own block. Disabled slots produce no block at all: the
    shape buttons decide which slots exist, and a gap in the row is the honest
    rendering of "this output has no green channel".
    """
    blocks: list[ChannelBlock] = []
    rgb = [channel_for_slot(output, slot) for slot in ("R", "G", "B")]
    if is_gray_shaped(output):
        blocks.append(
            ChannelBlock("R", "Gray", BLOCK_GRAY, ("R", "G", "B"), _entry_source(rgb[0]), entry_variant(rgb[0]))
        )
    elif is_rgb_shaped(output):
        blocks.append(
            ChannelBlock("R", "RGB", BLOCK_RGB, ("R", "G", "B"), _entry_source(rgb[0]), entry_variant(rgb[0]))
        )
    else:
        for slot, entry in zip(("R", "G", "B"), rgb):
            if entry is not None and bool(getattr(entry, "enabled", False)):
                blocks.append(
                    ChannelBlock(slot, slot, BLOCK_SLOT, (slot,), _entry_source(entry), entry_variant(entry))
                )
    alpha = channel_for_slot(output, "A")
    if alpha is not None and bool(getattr(alpha, "enabled", False)):
        blocks.append(ChannelBlock("A", "A", BLOCK_SLOT, ("A",), _entry_source(alpha), entry_variant(alpha)))
    return blocks


def block_for_slot(output, slot: str):
    """The block that currently owns ``slot``, or ``None``.

    Resolving the selection through the slot (rather than storing a block key) is
    what makes the selection survive a regrouping: assign AO/GRAY to the last of
    three split slots and the three ``R``/``G``/``B`` blocks become one ``Gray``
    block, whose key is still "R".
    """
    wanted = str(slot or "").strip().upper()
    if not wanted:
        return None
    for block in output_blocks(output):
        if wanted in block.slots:
            return block
    return None


def assign_block_source(output, block, source: str, channel=None, variant: int = DEFAULT_VARIANT) -> None:
    """Point every slot of ``block`` at ``source``.

    ``variant`` is the occurrence ordinal (0 == the first bake of this type) and
    lands on every slot of the block alongside the map, because a block is one
    image: two of its slots reading different bakes would stop being one block on
    the next draw. ``source`` may also be given as a composite key (``AO#1``),
    which is what the dropdown hands over -- the ordinal in the key wins.

    With no ``channel`` the routing follows the block's kind, which is the whole
    point of grouping: a Gray block writes ``GRAY`` into all three slots, an RGB
    block writes the identity routing, and a single slot keeps whatever source
    channel it was reading (reassigning the map does not silently re-route the
    channel). That is the historical behaviour and stays the default.

    ``channel`` is the explicit read the source popover picks (see
    :func:`source_read_options`): one of ``R``/``G``/``B``/``A``/``GRAY``, or
    :data:`ROUTING_IDENTITY` for "each slot reads its own letter". It lands on
    **every** slot of the block, so choosing "G Channel" on a grouped RGB block
    feeds all three output channels from the source's green -- which is a real
    (if unusual) pack, and the row honestly redraws as three separate chips
    because it is no longer identity-routed.

    An **empty** ``source`` is the unassign path (the source panel's "Unassigned"
    button): it clears the map on every slot of the block while keeping the slots
    themselves enabled, so the chip goes dark and the output keeps its shape.
    """
    identifier, key_variant = split_source_key(source)
    try:
        ordinal = max(DEFAULT_VARIANT, int(variant or DEFAULT_VARIANT))
    except (TypeError, ValueError):
        ordinal = DEFAULT_VARIANT
    if key_variant:
        ordinal = key_variant
    if not identifier:
        # Unassigning addresses no bake, so it cannot carry an ordinal either.
        ordinal = DEFAULT_VARIANT
    routing = str(channel or "").strip().upper()
    if routing and routing != ROUTING_IDENTITY and routing not in SOURCE_CHANNELS:
        # An identifier no build of the schema knows: fall back to the per-kind
        # default rather than writing a channel the packer would refuse.
        routing = ""
    if block is None:
        return
    for slot in block.slots:
        entry = channel_for_slot(output, slot)
        if entry is None:
            continue
        entry.enabled = True
        try:
            entry.source = identifier
        except (TypeError, ValueError):
            continue
        try:
            entry.variant = ordinal
        except (TypeError, ValueError):  # pragma: no cover - defensive
            entry.variant = DEFAULT_VARIANT
        # A map and a constant are mutually exclusive: "constant" is only legal
        # on a CONSTANT channel, so assigning a map has to take the value with it.
        entry.constant = 0.0
        entry.constant_custom = False
        if routing == ROUTING_IDENTITY:
            channel_value = slot
        elif routing:
            channel_value = routing
        elif block.kind == BLOCK_GRAY:
            channel_value = "GRAY"
        elif block.kind == BLOCK_RGB:
            channel_value = slot
        else:
            channel_value = str(getattr(entry, "channel", "") or "GRAY").strip().upper() or "GRAY"
        try:
            entry.channel = channel_value
        except (TypeError, ValueError):
            entry.channel = "GRAY"


def assign_block_constant(output, block, value, *, custom: bool = False) -> None:
    """Fill every slot of ``block`` with a flat value. Pure; duck-typed.

    Writes the pinned contract: ``source = CONSTANT`` plus ``constant = value``.
    The routing is forced to ``GRAY`` because "which channel of a flat value" is
    not a question -- which is also what makes a constant fed to R/G/B collapse
    into one Gray block, correctly: it *is* one gray image.
    """
    if block is None:
        return
    number = clamp_constant(value)
    for slot in block.slots:
        entry = channel_for_slot(output, slot)
        if entry is None:
            continue
        entry.enabled = True
        try:
            entry.source = CONSTANT_SOURCE
        except (TypeError, ValueError):
            continue
        # An occurrence ordinal counts bakes; a flat value is not one, and the
        # contract makes "variant" an error on a CONSTANT channel.
        try:
            entry.variant = DEFAULT_VARIANT
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass
        entry.constant = number
        entry.constant_custom = bool(custom)
        try:
            entry.channel = "GRAY"
        except (TypeError, ValueError):
            pass


def assign_block_item(output, block, item: str) -> None:
    """Apply one dropdown pick to a block. Pure; duck-typed.

    The single place a menu identifier becomes staged data, so the dropdown, the
    tests and any future caller all take the same path:

    * ``__NONE__`` clears the block (the slots stay, the map goes);
    * a constant item writes the flat value, Custom keeping whatever value was
      already there so switching Gray -> Custom does not jump;
    * anything else is a source map -- possibly a composite key naming one
      occurrence of it (``AO#1``) -- assigned with the component
      :func:`default_read_channel` infers. Note the component is inferred from
      the **map type**, not from the key: which bake it is says nothing about how
      many channels it carries.
    """
    if block is None:
        return
    identifier = str(item or UNASSIGNED_ITEM)
    if identifier == UNASSIGNED_ITEM:
        assign_block_source(output, block, "", channel="")
        return
    for constant_item, _label, value in CONSTANT_PRESETS:
        if identifier == constant_item:
            assign_block_constant(output, block, value, custom=False)
            return
    if identifier == CONSTANT_ITEM_CUSTOM:
        anchor = channel_for_slot(output, block.slots[0]) if block.slots else None
        current = getattr(anchor, "constant", None) if anchor is not None else None
        if not is_constant_source(getattr(anchor, "source", "")) or current is None:
            current = CONSTANT_CUSTOM_DEFAULT
        assign_block_constant(output, block, current, custom=True)
        return
    base, ordinal = split_source_key(identifier)
    assign_block_source(output, block, base, channel=default_read_channel(block, base), variant=ordinal)


# ---------------------------------------------------------------------------
# "Which channel of the source map?" -- the read-options list (pure)
#
# Substance Painter does not assign a map the moment you drop it on a channel: it
# opens a small menu naming the ways that source can be read. The two shapes it
# shows are
#
#     scalar source:  From Metallic · Gray Channel · A Channel
#     colour source:  From Coat normal · Gray · R · G · B · A
#
# with the first entry being the natural read for the slot you dropped it on.
# :func:`source_read_options` is that menu as data, so the picker's contents are
# unit-tested headless and the operator only has to draw them.
# ---------------------------------------------------------------------------


def default_read_channel(block, source) -> str:
    """The natural read of ``source`` for ``block`` -- the popover's first entry.

    * grouped **RGB** block -> :data:`ROUTING_IDENTITY` (R←R, G←G, B←B);
    * grouped **Gray** block -> ``GRAY`` (luminance on all three slots);
    * single **R/G/B** slot -> the slot's own letter for a colour source (that is
      what "drop a normal map on G" means), ``GRAY`` for a scalar one, whose
      letters all carry the same value anyway;
    * single **A** slot -> ``GRAY``: alpha is a scalar destination, so the
      natural read of any source into it is its luminance.
    """
    if block is None:
        return "GRAY"
    kind = str(getattr(block, "kind", BLOCK_SLOT) or BLOCK_SLOT)
    if kind == BLOCK_RGB:
        return ROUTING_IDENTITY
    if kind == BLOCK_GRAY:
        return "GRAY"
    slots = tuple(getattr(block, "slots", ()) or ())
    slot = str(slots[0] if slots else "R").strip().upper()
    if slot in ("R", "G", "B") and is_color_source(source):
        return slot
    return "GRAY"


def source_read_options(block, source) -> tuple:
    """``((routing, label), ...)`` -- the reads this source can actually supply. Pure.

    The natural read (:func:`default_read_channel`) comes first, named
    ``From <Map>``; the other **distinct** reads follow in a fixed order. Every
    entry does something the others do not, which is the whole rule here:

    * **No alpha.** A baked source has no meaningful alpha to read.
      ``export_pack._image_to_array`` pads a 3-channel buffer with alpha 1.0, so
      "A Channel" is a constant white, never the map. It used to be offered
      unconditionally (Substance Painter offers it, and the padding meant it
      could not *fail*) -- but "cannot fail" is not "is useful", and Glow called
      it correctly: a channel the source does not have should not be pickable.
    * **No repeats.** A scalar map is one value replicated across RGB, so
      ``From AO``, ``Gray Channel`` and ``R/G/B`` are all the same pixels. Only
      the natural read is listed, which leaves a single entry -- and a
      one-entry list is not a choice, so the popover draws no read section at
      all (see :func:`draw_channel_options_popover`).

    A colour source keeps the full set, minus whichever letter the natural read
    already is: an RGB block offers ``From Normal`` + Gray + R + G + B, and a
    single G slot offers ``From Normal`` (which *is* G) + Gray + R + B.
    """
    default = default_read_channel(block, source)
    options: list[tuple[str, str]] = [(default, f"From {source_label(source)}")]
    if not is_color_source(source):
        return tuple(options)
    for routing in ("GRAY", "R", "G", "B"):
        if routing == default:
            continue
        options.append((routing, "Gray Channel" if routing == "GRAY" else f"{routing} Channel"))
    return tuple(options)


def channel_read_options(output, block) -> tuple:
    """:func:`source_read_options` for ``block``, guaranteed to contain its current read.

    A template authored before a read stopped being offered (a stored ``A``, say)
    must still show which read it is on, rather than drawing a list with nothing
    selected in it. The stale entry is appended rather than hidden, so picking
    anything else is what clears it.
    """
    if block is None:
        return ()
    source = str(getattr(block, "source", "") or "").strip()
    options = source_read_options(block, source)
    current = block_routing(output, block)
    if current in {routing for routing, _label in options}:
        return options
    return options + ((current, f"{component_label(current)} Channel"),)


def block_invert(output, block) -> bool:
    """Whether ``block`` is inverted (its anchor slot's state)."""
    if block is None:
        return False
    entry = channel_for_slot(output, block.slots[0]) if block.slots else None
    return bool(getattr(entry, "invert", False))


def set_block_variant(output, block, ordinal: int) -> None:
    """Point every slot of ``block`` at the same occurrence. Pure; duck-typed.

    All of them, for the same reason :func:`set_block_invert` writes all of them:
    a block is one image, and two slots addressing different bakes would stop
    being one block on the next draw.
    """
    if block is None:
        return
    try:
        value = max(DEFAULT_VARIANT, int(ordinal))
    except (TypeError, ValueError):
        value = DEFAULT_VARIANT
    for slot in block.slots:
        entry = channel_for_slot(output, slot)
        if entry is None:
            continue
        try:
            entry.variant = value
        except (TypeError, ValueError):  # pragma: no cover - defensive
            entry.variant = DEFAULT_VARIANT


def set_block_invert(output, block, value: bool) -> None:
    """Invert (or un-invert) every slot of a block at once.

    A grouped block whose slots disagreed about inversion would stop being one
    block on the next draw, so this always writes all of them.
    """
    if block is None:
        return
    for slot in block.slots:
        entry = channel_for_slot(output, slot)
        if entry is not None:
            entry.invert = bool(value)


def set_alpha_enabled(output, enabled: bool) -> None:
    """Add or drop the alpha channel without rebuilding the output.

    Dropping it only clears ``enabled`` -- the slot keeps its source, so toggling
    alpha off and on again comes back to the same assignment.

    Adding it assigns **nothing**: the new slot is an empty A chip waiting to be
    clicked, the same rule the shape buttons follow. (It used to seed
    ``MATERIAL_OPACITY`` because the validator refused a sourceless channel; it
    no longer does.)
    """
    entry = channel_for_slot(output, "A")
    if entry is None:
        return
    if not enabled:
        entry.enabled = False
        return
    entry.enabled = True
    try:
        entry.channel = str(getattr(entry, "channel", "") or "GRAY").strip().upper() or "GRAY"
    except (TypeError, ValueError):
        entry.channel = "GRAY"


# ---------------------------------------------------------------------------
# Row text (pure)
# ---------------------------------------------------------------------------


def elide(text: str, max_chars: int) -> str:
    """Trim to ``max_chars`` including the ellipsis. ``0`` disables trimming."""
    value = str(text or "")
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    return value[: max(1, max_chars - 1)].rstrip() + "…"


def source_label(identifier) -> str:
    """The human label for a source identifier, as the source panel shows it."""
    key = str(identifier or "").strip().upper()
    if not key:
        return "Unassigned"
    if is_constant_source(key):
        # Value-less: the caller that has the entry (block_assignment_label)
        # names the value; this one only ever has the identifier.
        return "Constant"
    for candidate, label, _description in source_items_tuple():
        if candidate == key:
            return label
    return constants.MAP_FILE_LABELS.get(key, key)


# ---------------------------------------------------------------------------
# Slot-first assignment text (pure)
#
# The editor's primary control is the slot, not the source list: each channel
# block draws one wide button whose *text* is the assignment. Everything the
# button and its picker need is derived here, so the wording is unit-tested
# headless and the draw code only places widgets.
# ---------------------------------------------------------------------------


def block_slot_letters(block) -> str:
    """The destination letters a block owns: ``RGB`` / ``R`` / ``A``.

    Deliberately the *slots*, not ``block.label``: a Gray block and an RGB block
    both fill R, G and B, and which of the two it is shows up in the assignment
    text's component ("AO · Gray" vs "Normal · RGB") rather than twice.
    """
    if block is None:
        return ""
    return "".join(str(slot) for slot in getattr(block, "slots", ()) or ())


def block_routing(output, block) -> str:
    """How ``block`` currently reads its source: a channel, or ``IDENTITY``.

    Grouped blocks answer from their kind (that is what made them one block);
    a single slot answers from the channel it stores.
    """
    if block is None:
        return "GRAY"
    kind = str(getattr(block, "kind", BLOCK_SLOT) or BLOCK_SLOT)
    if kind == BLOCK_RGB:
        return ROUTING_IDENTITY
    if kind == BLOCK_GRAY:
        return "GRAY"
    slots = tuple(getattr(block, "slots", ()) or ())
    entry = channel_for_slot(output, slots[0]) if slots else None
    return str(getattr(entry, "channel", "GRAY") or "GRAY").strip().upper() or "GRAY"


def component_label(routing) -> str:
    """``GRAY`` -> ``Gray``, ``IDENTITY`` -> ``RGB``, a letter -> itself."""
    key = str(routing or "").strip().upper()
    return COMPONENT_LABELS.get(key, key or "Gray")


def block_assignment_label(output, block, variants: tuple = ()) -> str:
    """The wide button's text: ``"Material: Albedo · RGB"`` or ``"Unassigned"``.

    One string says both halves of the assignment -- *which map* and *which part
    of it* -- which is the whole point of the inversion: the destination is
    already visible as the row it sits in, so the control can spend its width on
    the answer instead of on a colour the artist has to decode.

    A block addressing a later occurrence gains a third part naming **which
    bake** -- ``Ambient Occlusion · Fine · Gray`` -- taken from ``variants``, the
    open project's spec. Occurrence 0 says nothing extra, so a project with one
    bake per type reads exactly as it always did.
    """
    source = str(getattr(block, "source", "") or "").strip() if block is not None else ""
    if not source:
        return UNASSIGN_LABEL
    if is_constant_source(source):
        # A flat value has no component to name; what it has is the value, and
        # only when it is not one of the three presets ("Black" says it already).
        entry = channel_for_slot(output, block.slots[0]) if block.slots else None
        return constant_label(getattr(entry, "constant", 0.0), entry_is_custom_constant(entry))
    entry = channel_for_slot(output, block.slots[0]) if block.slots else None
    variant = entry_variant(entry) if entry is not None else 0
    count = variant_count(variants, source)
    index_label = ""
    if variant > 0 or count > 1:
        index_label = f" · {map_stack_index_label(source, variant, max(count, variant + 1))}"
    return f"{source_label(source)}{index_label} · {component_label(block_routing(output, block))}"


def channel_options_available(block) -> bool:
    """Whether this block has qualifiers to open a popover for. Pure.

    Any assigned **map**: it can always address a later bake of its type, and a
    colour source can additionally be read a different way (grouped blocks
    included -- routing a whole RGB block off the source's green is a real pack).
    A scalar source has only the index question, which is still a question; the
    popover simply draws no read list for it. A constant has neither question,
    and an empty slot has nothing to qualify.
    """
    if block is None:
        return False
    source = str(getattr(block, "source", "") or "").strip()
    return bool(source) and not is_constant_source(source)


def channel_options_summary(output, block) -> str:
    """What the qualifier button says: the read, plus the index when it is not the first.

    ``Gray`` / ``R`` / ``RGB`` normally, ``Gray #2`` once the channel addresses a
    later bake -- the same ``#n`` the map stack labels duplicates with, so the two
    read as the same numbering.
    """
    if block is None:
        return ""
    source = str(getattr(block, "source", "") or "").strip()
    if not source or is_constant_source(source):
        return ""
    routing = component_label(block_routing(output, block))
    variant = int(getattr(block, "variant", 0) or 0)
    return f"{routing} #{variant + 1}" if variant > 0 else routing


def output_primary_source(output) -> str:
    """First assigned source of an output -- the dot in its header row.

    The first *assigned* slot's source -- the dot in its header row. A
    ``CONSTANT`` slot counts (it has a swatch).
    """
    for slot in CHANNEL_SLOTS:
        entry = channel_for_slot(output, slot)
        if entry is None or not bool(getattr(entry, "enabled", False)):
            continue
        source = str(getattr(entry, "source", "") or "").strip()
        if source:
            return source
    return ""


def output_display_name(output) -> str:
    """The output's filename as authored; tokens stay visible."""
    text = str(getattr(output, "filename", "") or "")
    return text or "(unnamed)"


def _channel_to_staging(entry, definition) -> None:
    if not isinstance(definition, dict):
        entry.enabled = False
        entry.source = ""
        entry.variant = DEFAULT_VARIANT
        entry.constant = 0.0
        entry.constant_custom = False
        return
    entry.enabled = True
    # Stored verbatim, including "" for an unassigned slot: the file is the source
    # of truth and every built-in must round-trip byte-identically. A source this
    # build does not know is kept as-is too -- the validator names it in the error
    # box rather than the editor silently rewriting the template.
    entry.source = str(definition.get("source") or "")
    channel = str(definition.get("channel") or "GRAY").strip().upper()
    try:
        entry.channel = channel
    except (TypeError, ValueError):
        entry.channel = "GRAY"
    entry.invert = bool(definition.get("invert", False))
    if is_constant_source(entry.source):
        # "constant" is legal only on a CONSTANT channel, so it is read only
        # there. The Custom flag is derived, never stored: a value that is not
        # one of the three presets IS a custom one.
        entry.variant = DEFAULT_VARIANT
        entry.constant = clamp_constant(definition.get("constant", 0.0))
        entry.constant_custom = not constant_preset_item(entry.constant)
    else:
        # Kept VERBATIM, including an occurrence this project does not have.
        # Clamping it to 0 here is exactly the silent rewrite the ordinal exists
        # to prevent: it would write a file the artist did not ask for and cannot
        # tell apart. The Validation panel names it instead
        # (:func:`validate_staging`).
        try:
            entry.variant = max(DEFAULT_VARIANT, int(definition.get("variant", DEFAULT_VARIANT) or DEFAULT_VARIANT))
        except (TypeError, ValueError):
            entry.variant = DEFAULT_VARIANT
        entry.constant = 0.0
        entry.constant_custom = False


def _output_to_staging(output, definition: dict) -> None:
    output.filename = str(definition.get("filename") or "")
    image_format = str(definition.get("format") or DEFAULT_FORMAT).strip().upper()
    try:
        output.format = image_format
    except (TypeError, ValueError):
        output.format = DEFAULT_FORMAT
    set_output_bit_depth(output, definition.get("bit_depth", DEFAULT_BIT_DEPTH))
    color_space = str(definition.get("color_space") or DEFAULT_COLOR_SPACE).strip().upper()
    try:
        output.color_space = color_space
    except (TypeError, ValueError):
        output.color_space = DEFAULT_COLOR_SPACE
    try:
        output.dds_compression = export_templates.output_dds_compression(definition)
    except (TypeError, ValueError):
        output.dds_compression = constants.EXPORT_DDS_BC7
    output.notes = str(definition.get("notes") or "")

    ensure_channel_slots(output)
    channels = definition.get("channels") or {}
    for slot in CHANNEL_SLOTS:
        entry = channel_for_slot(output, slot)
        if entry is not None:
            _channel_to_staging(entry, channels.get(slot) if isinstance(channels, dict) else None)


def template_to_staging(data: dict, state) -> None:
    """Fill ``state`` from a validated template payload. Pure; no bpy calls."""
    payload = dict(data or {})
    state.template_name = str(payload.get("name") or "")
    state.notes = str(payload.get("notes") or "")
    state.outputs.clear()
    for definition in payload.get("outputs") or ():
        _output_to_staging(state.outputs.add(), definition if isinstance(definition, dict) else {})
    state.active_output_index = 0
    # A freshly loaded template has nothing selected: the source panel opens on
    # its hint, exactly like SP's, rather than on an arbitrary channel.
    state.active_slot = ""
    state.loaded = True
    state.error = ""


def _channel_to_dict(entry):
    if not bool(getattr(entry, "enabled", False)):
        return None
    source = str(getattr(entry, "source", "") or "")
    definition = {
        "source": source,
        "channel": str(getattr(entry, "channel", "GRAY") or "GRAY"),
        "invert": bool(getattr(entry, "invert", False)),
    }
    if is_constant_source(source):
        # Emitted ONLY here: the contract makes "constant" an unknown key on any
        # other channel, and every built-in without one must round-trip to a dict
        # equal to the file it came from.
        definition["constant"] = round(clamp_constant(getattr(entry, "constant", 0.0)), 6)
    else:
        variant = entry_variant(entry)
        if variant:
            # Emitted ONLY when non-zero. Absent means occurrence 0, which is
            # what every template written before variants existed already means,
            # so no existing file changes by a byte and no existing test moves.
            definition["variant"] = variant
    return definition


def _output_to_dict(output) -> dict:
    definition = {
        "filename": str(getattr(output, "filename", "") or ""),
        "format": str(getattr(output, "format", DEFAULT_FORMAT) or DEFAULT_FORMAT),
        "bit_depth": output_bit_depth(output),
        "color_space": str(getattr(output, "color_space", DEFAULT_COLOR_SPACE) or DEFAULT_COLOR_SPACE),
        "channels": {slot: _channel_to_dict(channel_for_slot(output, slot)) for slot in CHANNEL_SLOTS},
    }
    if str(definition["format"]).strip().upper() == constants.IMAGE_FORMAT_DDS:
        # Only on a DDS output: the validator rejects the key anywhere else, and
        # every template that predates it must round-trip unchanged.
        definition["dds_compression"] = str(
            getattr(output, "dds_compression", constants.EXPORT_DDS_BC7)
            or constants.EXPORT_DDS_BC7
        )
    notes = str(getattr(output, "notes", "") or "")
    if notes:
        # Emitted only when set: every shipped built-in without notes must
        # round-trip to a dict equal to the file it came from.
        definition["notes"] = notes
    return definition


def staging_to_template(state) -> dict:
    """Serialise the staging buffer back to a template payload. Pure."""
    payload = {
        "schema": export_templates.TEMPLATE_SCHEMA,
        "name": str(getattr(state, "template_name", "") or "").strip(),
        "outputs": [_output_to_dict(output) for output in getattr(state, "outputs", ()) or ()],
    }
    notes = str(getattr(state, "notes", "") or "")
    if notes:
        payload["notes"] = notes
    return payload


# ---------------------------------------------------------------------------
# Output shapes (SP's "Create:" row)
# ---------------------------------------------------------------------------

SHAPE_GRAY = "GRAY"
SHAPE_RGB = "RGB"
SHAPE_R_G_B = "R_G_B"
SHAPE_RGB_A = "RGB_A"
SHAPE_R_G_B_A = "R_G_B_A"

SHAPE_ITEMS = (
    (SHAPE_GRAY, "Gray", "One grayscale image: R, G and B all read the same map's luminance"),
    (SHAPE_RGB, "RGB", "One color image: R, G and B read the matching channels of one map"),
    (SHAPE_R_G_B, "R+G+B", "A channel pack: three independent grayscale maps in R, G and B"),
    (SHAPE_RGB_A, "RGB+A", "One color image plus an independent grayscale alpha"),
    (SHAPE_R_G_B_A, "R+G+B+A", "A channel pack: four independent grayscale maps in R, G, B and A"),
)

#: What a shape decides: which slots the output HAS, and how each of them reads
#: its (future) source map -- ``GRAY`` for a luminance slot, ``R``/``G``/``B`` for
#: the identity-routed color shape. It deliberately picks **no maps**: a new
#: output starts completely unassigned, because an output that arrives with maps
#: already in it is a guess about the artist's intent that they then have to undo
#: (reported by Glow, 2026-08-04). Every slot below is created with ``source = ""``
#: and draws as a dark chip until it is clicked and assigned.
_SHAPE_ROUTING = {
    SHAPE_GRAY: ("GRAY", "GRAY", "GRAY"),
    SHAPE_RGB: ("R", "G", "B"),
    SHAPE_R_G_B: ("GRAY", "GRAY", "GRAY"),
    SHAPE_RGB_A: ("R", "G", "B", "GRAY"),
    SHAPE_R_G_B_A: ("GRAY", "GRAY", "GRAY", "GRAY"),
}


def used_output_filenames(state, skip=None) -> set[str]:
    """Every filename template the staged outputs already use, casefolded."""
    names: set[str] = set()
    for output in getattr(state, "outputs", ()) or ():
        # `==` not `is`: RNA rebuilds the wrapper per access, so `is` never skipped.
        if skip is not None and output == skip:
            continue
        name = str(getattr(output, "filename", "") or "").strip()
        if name:
            names.add(name.casefold())
    return names


def unique_output_filename(state, base: str, skip=None) -> str:
    """``$textureSet_AO`` / ``...AO2`` / ``...AO3`` -- keeps a copy savable.

    Identity is ``(filename template, first source, occurrence)``, so a plain
    copy of an output is a duplicate as far as
    ``export_templates.validate_template`` is concerned and the autosave would
    refuse the template the editor itself just built. The copy reads the same
    bake -- changing *that* would silently retarget it -- so the filename is the
    axis that has to move. An empty base falls back to :data:`DEFAULT_FILENAME`.
    """
    stem = str(base or "").strip() or DEFAULT_FILENAME
    taken = used_output_filenames(state, skip=skip)
    if stem.casefold() not in taken:
        return stem
    index = 2
    while f"{stem}{index}".casefold() in taken:
        index += 1
    return f"{stem}{index}"


def append_output(state, shape: str):
    """Append a pre-shaped, **unassigned** output and return it.

    The shape decides which slots exist and how they route; no map is assigned
    to any of them (``validate_template`` gives an output with nothing assigned
    no identity, so two blank outputs are not duplicates of each other).
    """
    routing = _SHAPE_ROUTING.get(shape, _SHAPE_ROUTING[SHAPE_GRAY])
    output = state.outputs.add()
    output.filename = DEFAULT_FILENAME
    try:
        output.format = DEFAULT_FORMAT
    except (TypeError, ValueError):
        pass
    set_output_bit_depth(output, DEFAULT_BIT_DEPTH)
    try:
        output.color_space = DEFAULT_COLOR_SPACE
    except (TypeError, ValueError):
        pass
    output.notes = ""
    ensure_channel_slots(output)

    for slot, channel in zip(CHANNEL_SLOTS, routing):
        entry = channel_for_slot(output, slot)
        if entry is None:
            continue
        entry.enabled = True
        entry.source = ""
        try:
            entry.channel = channel
        except (TypeError, ValueError):
            entry.channel = "GRAY"

    state.active_output_index = max(0, len(state.outputs) - 1)
    # Focus the new output's first block, so "Create: RGB" lands the artist in the
    # source panel with something to assign instead of on an empty right column.
    blocks = output_blocks(output)
    state.active_slot = blocks[0].key if blocks else ""
    return output


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def preview_filename(output) -> str:
    """The active output's filename expanded against the sample context.

    ``$udim`` is deliberately absent from the context: the preview shows the
    untiled case, which is what collapses the trailing separator and is the
    shape most users are checking.
    """
    context = export_tokens.build_export_context(
        project_name=PREVIEW_PROJECT,
        texture_set_name=PREVIEW_TEXTURE_SET,
        udim_tile=None,
        resolution_x=PREVIEW_RESOLUTION,
        resolution_y=PREVIEW_RESOLUTION,
        bit_depth=output_bit_depth(output),
        image_format=str(getattr(output, "format", DEFAULT_FORMAT) or DEFAULT_FORMAT),
        blend_name=PREVIEW_TEXTURE_SET,
    )
    stem = export_tokens.expand_template(str(getattr(output, "filename", "") or ""), context)
    try:
        from . import naming

        extension = naming.output_extension_for_image_format(
            str(getattr(output, "format", DEFAULT_FORMAT) or DEFAULT_FORMAT)
        )
    except Exception:
        extension = ""
    return f"{stem}{extension}"


# ---------------------------------------------------------------------------
# Validation (pure)
#
# A read-out of the staged template, NOT a gate: autosave already refuses
# anything ``export_templates.validate_template`` rejects. What is collected
# here is the layer above that -- the template is legal JSON and still will not
# do what the artist meant (a typo'd token, a normal map written sRGB, two
# outputs racing for one filename). Every rule is computed from the staging
# buffer alone, so the whole panel is unit-tested headless.
# ---------------------------------------------------------------------------

LEVEL_ERROR = "ERROR"
LEVEL_WARNING = "WARNING"
LEVEL_INFO = "INFO"

#: Level -> the Blender icon its row draws with. ``CANCEL`` (red disc) for a
#: hard error, the warning triangle for a warning, ``INFO`` for a note.
VALIDATION_ICONS = {
    LEVEL_ERROR: "CANCEL",
    LEVEL_WARNING: "ERROR",
    LEVEL_INFO: "INFO",
}

#: Whether a file format can carry an alpha channel.
#:
#: This table lives here rather than in ``constants.py`` or ``export_pack.py``
#: because neither of them records the fact: ``IMAGE_FORMAT_ITEMS`` is
#: (id, label, description) only, and ``export_pack._FORMAT_SPECS`` carries
#: file_format / depths / is_linear -- it hands ``color_mode="RGBA"`` straight
#: through from the caller's ``has_alpha`` without ever asking whether the
#: format could store it. ``constants.py`` is also owned by another workstream.
#: All four formats the addon ships **can** store alpha (Blender writes RGBA
#: TGA, PNG, TIFF and EXR), so today this rule is a guard rather than a fault
#: anyone can hit; it exists so that adding an alpha-less format (JPEG, say)
#: surfaces the mistake in the editor instead of silently dropping the A slot
#: at export time. A format missing from the table is assumed capable -- the
#: panel never invents a warning about something it does not know.
FORMAT_ALPHA_CAPABLE: dict[str, bool] = {
    constants.IMAGE_FORMAT_TGA: True,
    constants.IMAGE_FORMAT_PNG: True,
    constants.IMAGE_FORMAT_TIFF: True,
    constants.IMAGE_FORMAT_EXR: True,
    constants.IMAGE_FORMAT_DDS: True,
}


def format_supports_alpha(format_id) -> bool:
    """Whether ``format_id`` can store an alpha channel. Unknown == yes."""
    return bool(FORMAT_ALPHA_CAPABLE.get(str(format_id or "").strip().upper(), True))


#: Sources whose pixels are a tangent/object/world-space direction. Written sRGB
#: they are silently re-encoded and the shader reads a bent surface, which is the
#: single most common template mistake worth naming.
NORMAL_SOURCE_IDENTIFIERS: frozenset[str] = frozenset(
    {
        constants.MAP_NORMAL,
        constants.MAP_OBJECT_NORMAL,
        constants.MAP_WORLD_NORMAL,
        constants.MAP_BENT_NORMAL,
    }
)


def is_normal_source(identifier) -> bool:
    """True when this source is a normal map (any space). Pure."""
    return str(identifier or "").strip().upper() in NORMAL_SOURCE_IDENTIFIERS


def assigned_sources(output) -> tuple:
    """Sources this output actually reads, in slot order, without duplicates."""
    seen: list[str] = []
    for slot in CHANNEL_SLOTS:
        entry = channel_for_slot(output, slot)
        if entry is None or not bool(getattr(entry, "enabled", False)):
            continue
        source = str(getattr(entry, "source", "") or "").strip().upper()
        if source and source not in seen:
            seen.append(source)
    return tuple(seen)


#: Validation rows sit in the narrow right-hand column, so a long filename is
#: elided rather than allowed to push the rest of the message out of view.
_VALIDATION_NAME_CHARS = 28


def output_title(output, index: int) -> str:
    """How an output is named in a validation message.

    The filename as authored, falling back to the output's position when nothing
    is assigned yet -- six fresh outputs sharing the default filename would
    otherwise be indistinguishable in a validation list.
    """
    if output_primary_source(output):
        name = output_display_name(output)
        if name and name != "(unnamed)":
            return elide(name, _VALIDATION_NAME_CHARS)
    return f"Output {int(index) + 1}"


def unresolved_variant_message(title: str, map_type: str, variant: int, available: int) -> str:
    """The wording of the unresolved-occurrence warning. Pure.

    Names all three things the artist needs: which output, which bake it asks
    for, and what this project actually holds. It is a **warning**, not an error:
    the template is perfectly valid and does exactly this in the project it was
    authored in -- it is only here that the channel cannot be filled.
    """
    have = "none" if available <= 0 else str(available)
    return (
        f"{title}: wants the {ordinal_word(int(variant) + 1)} {source_label(map_type)} "
        f"bake, but this project has {have}"
    )


def validate_staging(state, variants=None) -> tuple:
    """``((level, message), ...)`` for the staged template.

    Ordered by severity first (errors, warnings, infos) and by output within a
    level, so the panel reads top-down as "fix this, then look at that".

    Pure **when ``variants`` is given** -- every rule is then computed from the
    staging buffer and that argument alone, which is how the whole panel stays
    unit-tested headless. Left at ``None`` it makes exactly one call outward, to
    read the open project's map stack (below); headless that answers "no
    project" and the one rule that needs it is skipped.

    ``variants`` is :func:`project_variant_spec` of the project the template is
    being read *in*, and it is what powers the portability rule: a channel asking
    for the 2nd AO in a project with one AO is flagged rather than quietly
    re-pointed. Passing ``None`` resolves it from the open project;
    :func:`current_variant_spec` answers ``None`` again when there is no project
    at all, and then the rule is skipped -- a count we do not have would either
    invent a warning or hide a real one.
    """
    outputs = list(getattr(state, "outputs", ()) or ())
    errors: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
    infos: list[tuple[str, str]] = []

    spec = current_variant_spec() if variants is None else tuple(variants)

    try:
        valid = export_templates.valid_source_identifiers()
    except Exception:  # pragma: no cover - defensive
        valid = frozenset()

    #: preview filename -> the outputs that write it, for the collision rule.
    by_filename: dict[str, list[str]] = {}

    for index, output in enumerate(outputs):
        title = output_title(output, index)

        unknown = export_tokens.find_unknown_tokens(str(getattr(output, "filename", "") or ""))
        if unknown:
            errors.append(
                (
                    LEVEL_ERROR,
                    f"{title}: unknown filename token " + ", ".join(f"${name}" for name in unknown),
                )
            )

        sources = assigned_sources(output)
        for source in sources:
            # CONSTANT is a legal source that is deliberately not a bakeable map
            # -- the packer synthesises a flat channel for it. Skipped explicitly
            # rather than relying on it being in valid_source_identifiers, so the
            # rule reads right whichever side of that contract landing we are on.
            if is_constant_source(source):
                continue
            if valid and source not in valid:
                errors.append((LEVEL_ERROR, f"{title}: '{source}' is not a bakeable map"))

        if spec is not None:
            # One row per (map, occurrence) an output asks for and this project
            # cannot supply -- deduplicated, because a packed output reading the
            # 2nd AO into three slots has one problem, not three.
            seen_variants: set[tuple[str, int]] = set()
            for slot in CHANNEL_SLOTS:
                entry = channel_for_slot(output, slot)
                if entry is None or not bool(getattr(entry, "enabled", False)):
                    continue
                source = str(getattr(entry, "source", "") or "").strip().upper()
                wanted = entry_variant(entry)
                if not source or is_constant_source(source) or wanted <= DEFAULT_VARIANT:
                    continue
                available = variant_count(spec, source)
                if wanted < available or (source, wanted) in seen_variants:
                    continue
                seen_variants.add((source, wanted))
                warnings.append(
                    (LEVEL_WARNING, unresolved_variant_message(title, source, wanted, available))
                )

        image_format = str(getattr(output, "format", DEFAULT_FORMAT) or DEFAULT_FORMAT).strip().upper()
        alpha = channel_for_slot(output, "A")
        alpha_assigned = (
            alpha is not None
            and bool(getattr(alpha, "enabled", False))
            and bool(str(getattr(alpha, "source", "") or "").strip())
        )
        if alpha_assigned and not format_supports_alpha(image_format):
            warnings.append(
                (LEVEL_WARNING, f"{title}: {image_format} cannot store the alpha channel it is assigned")
            )

        color_space = str(getattr(output, "color_space", "") or "").strip().upper()
        if color_space == export_templates.COLOR_SPACE_SRGB and any(is_normal_source(s) for s in sources):
            warnings.append((LEVEL_WARNING, f"{title}: a normal map written as sRGB. Use Linear"))

        if not sources:
            infos.append((LEVEL_INFO, f"{title}: nothing assigned yet"))
        else:
            # Outputs with nothing assigned write no file at all (the exporter
            # skips them), so they cannot collide -- and three blank rows of a
            # half-built template would otherwise all "collide" on the same
            # default filename.
            by_filename.setdefault(preview_filename(output), []).append(title)

    for filename, titles in by_filename.items():
        if len(titles) > 1:
            warnings.append(
                (LEVEL_WARNING, f"{' and '.join(titles[:2])} both write {filename}" if len(titles) == 2
                 else f"{len(titles)} outputs write {filename}")
            )

    return tuple(errors) + tuple(warnings) + tuple(infos)


def active_output(state):
    outputs = getattr(state, "outputs", None)
    if not outputs or not len(outputs):
        return None
    index = max(0, min(int(getattr(state, "active_output_index", 0) or 0), len(outputs) - 1))
    return outputs[index]


def output_at_index(state, index):
    """The staged output at ``index``, or ``None`` when it is out of range.

    A popover is drawn *after* the operator that opened it returns, so its
    callback re-resolves the row it was opened for rather than holding the RNA
    pointer -- which an output removed in between would leave dangling.
    """
    outputs = getattr(state, "outputs", None) if state is not None else None
    if not outputs or not len(outputs):
        return None
    try:
        position = int(index)
    except (TypeError, ValueError):
        return None
    if 0 <= position < len(outputs):
        return outputs[position]
    return None


def selected_block(state):
    """The channel block the source panel is editing, or ``None``.

    ``None`` covers both "nothing clicked yet" and "the slot that was selected no
    longer exists" (its output was deleted, or its alpha was dropped), so the
    panel falls back to its hint instead of drawing a dangling assignment.
    """
    output = active_output(state)
    if output is None:
        return None
    return block_for_slot(output, str(getattr(state, "active_slot", "") or ""))


def is_readonly(state) -> bool:
    """True while the staging buffer holds an unmodified built-in.

    Selecting a built-in stages a *view* of it: every widget is drawn disabled
    and Save is hidden, because ``save_user_template`` refuses built-in names
    anyway. Duplicate clears ``selected_name`` while keeping
    ``source_builtin_name``, which is what flips the editor back on.
    """
    selected = str(getattr(state, "selected_name", "") or "")
    return bool(selected) and selected == str(getattr(state, "source_builtin_name", "") or "")


def shadowed_builtin_name(name: str) -> str:
    """The built-in whose name ``name`` collides with, or ``""``.

    ``save_user_template`` refuses such a name outright, so the editor warns
    while the field is still being typed rather than at Save time.
    """
    wanted = str(name or "").strip().casefold()
    if not wanted:
        return ""
    try:
        infos = export_templates.list_templates()
    except Exception:
        return ""
    for info in infos:
        if info.builtin and info.name.casefold() == wanted:
            return info.name
    return ""


# ---------------------------------------------------------------------------
# Load / save plumbing
# ---------------------------------------------------------------------------


def load_into_staging(state, name: str) -> str:
    """Load a template by name into ``state``. Returns an error string, or ``""``."""
    try:
        info = export_templates.find_template(name)
        if info is None:
            return f"Output template '{name}' was not found"
        data = export_templates.load_template_file(info.path)
    except export_templates.TemplateError as error:
        return str(error)

    with suspend_autosave():
        template_to_staging(data, state)
        state.selected_name = info.name
        state.source_builtin_name = info.name if info.builtin else ""
        # A built-in has no file autosave may write: duplicating it is the only
        # way to edit it, and that duplicate gets its own file.
        state.loaded_from = "" if info.builtin else str(info.path)
    return ""


def clear_staging(state) -> None:
    with suspend_autosave():
        state.outputs.clear()
        state.template_name = ""
        state.notes = ""
        state.selected_name = ""
        state.source_builtin_name = ""
        state.loaded_from = ""
        state.active_slot = ""
        state.loaded = False
        state.error = ""


# ---------------------------------------------------------------------------
# Autosave
#
# Every edit is persisted immediately: there is no Save button, no Revert and no
# dirty flag. One funnel does it, reached from the ``update=`` hooks (typed
# fields, dropdowns) and from every mutating operator, under three rules:
#
# * a built-in staged read-only, or nothing loaded at all, is a no-op;
# * validation runs FIRST -- an invalid intermediate state (a duplicate output
#   mid-edit, a cleared name) sets ``state.error`` and writes nothing, so the
#   file on disk stays the last good version while the staging buffer keeps the
#   user's in-progress edit. The next valid edit saves;
# * a renamed template moves its file: the new name is written, the old file is
#   deleted (only ever from the user template directory), and a name that would
#   land on somebody else's file is refused instead.
# ---------------------------------------------------------------------------


def _paths_equal(left, right) -> bool:
    """Compare two filesystem paths tolerantly (case-insensitive on Windows)."""
    if not left or not right:
        return False
    try:
        return Path(left).resolve() == Path(right).resolve()
    except (OSError, ValueError):  # pragma: no cover - defensive
        return str(left) == str(right)


def _user_template_path(name: str):
    """Where a user template of this name is written, or ``None``."""
    try:
        return export_templates.template_path_for_name(name)
    except export_templates.TemplateError:
        return None


def _inside_user_template_dir(path) -> bool:
    """Whether ``path`` is a file in the user template directory.

    The guard on deleting the old file after a rename: ``loaded_from`` is only
    ever ours to remove when it is one of the user's own template files.
    """
    directory = export_templates.user_template_dir()
    if directory is None or not path:
        return False
    try:
        return Path(path).resolve().parent == Path(directory).resolve()
    except (OSError, ValueError):  # pragma: no cover - defensive
        return False


def colliding_template(state, name: str) -> str:
    """Name of a *different* template ``name`` would overwrite, or ``""``.

    ``save_user_template`` already refuses a built-in's name with its own
    message; what it cannot see is that the write would land on another **user**
    template's file, which is what renaming "My Pack 2" to "My Pack" would do.
    A template whose file is the one currently staged is not a collision -- that
    is just saving over yourself.
    """
    wanted = str(name or "").strip().casefold()
    if not wanted:
        return ""
    loaded_from = str(getattr(state, "loaded_from", "") or "")
    target = _user_template_path(name)
    try:
        infos = export_templates.list_templates()
    except Exception:  # pragma: no cover - defensive
        infos = ()
    for info in infos:
        if info.builtin or _paths_equal(info.path, loaded_from):
            continue
        if info.name.casefold() == wanted:
            return info.name
        if target is not None and _paths_equal(info.path, target):
            return info.name
    return ""


def autosave(state) -> str:
    """Persist the staging buffer to its JSON file. Returns an error, or ``""``.

    Safe to call from anywhere the buffer may have changed, including from an
    ``update=`` callback: nothing here writes a CollectionProperty, and the
    UIList mirror rebuild a rename needs is deferred onto the same one-shot timer
    ``draw`` uses.
    """
    if state is None or _LOADING:
        return ""
    if not bool(getattr(state, "loaded", False)) or is_readonly(state):
        return ""

    payload = staging_to_template(state)
    name = str(payload.get("name") or "").strip()
    if not name:
        state.error = "Give the template a name"
        return state.error

    errors = export_templates.validate_template(payload)
    if errors:
        state.error = "; ".join(errors)
        return state.error

    collision = colliding_template(state, name)
    if collision:
        state.error = f"'{collision}' already exists. Choose another name"
        return state.error

    previous = str(getattr(state, "loaded_from", "") or "")
    try:
        path = export_templates.save_user_template(payload)
    except export_templates.TemplateError as error:
        state.error = str(error)
        return state.error

    renamed = bool(previous) and not _paths_equal(previous, path)
    if renamed and _inside_user_template_dir(previous):
        try:
            Path(previous).unlink()
        except OSError:  # pragma: no cover - the new file is already written
            pass

    rows_changed = renamed or str(getattr(state, "selected_name", "") or "") != name
    state.loaded_from = str(path)
    state.selected_name = name
    state.error = ""
    _invalidate_dialog_cache()
    if rows_changed:
        # A new row, or a renamed one. NEVER write the mirror from here: this can
        # run inside Blender's button handling, so the rebuild goes through the
        # deferred timer. Operators that know they are safe refresh directly.
        _schedule_template_refresh()
    return ""


def new_user_template(state) -> tuple[str, str]:
    """Create an **empty** user template on disk and select it. ``(name, error)``.

    No seeded output: ``validate_template`` accepts an empty ``outputs`` list, so
    "+" gives the artist a blank template and the Create row decides what goes in
    it. (It used to be seeded with a Gray output purely because the validator
    refused an empty list.) The file still exists before this returns -- the row
    in the list is never ahead of disk.
    """
    if state is None:
        return "", "Template editor state is unavailable"
    with suspend_autosave():
        clear_staging(state)
        state.template_name = _unique_user_template_name(NEW_TEMPLATE_NAME)
        state.loaded = True
    error = autosave(state)
    if error:
        return "", error
    refresh_template_items(state, select=state.selected_name)
    return str(getattr(state, "selected_name", "") or ""), ""


def duplicate_user_template(state, source: str) -> tuple[str, str]:
    """Copy ``source`` (built-in or user) to a new file and select it."""
    if state is None:
        return "", "Template editor state is unavailable"
    name = str(source or "").strip()
    if not name:
        return "", "Select a template to duplicate"

    original = str(getattr(state, "selected_name", "") or "")
    error = load_into_staging(state, name)
    if error:
        return "", error
    with suspend_autosave():
        state.source_builtin_name = original if original == name else name
        state.template_name = _unique_user_template_name(f"{name} Copy")
        # A fresh file, not a rename: there is no old file to move, and clearing
        # the selection is what takes the copy out of the read-only built-in view.
        state.loaded_from = ""
        state.selected_name = ""
    error = autosave(state)
    if error:
        return "", error
    refresh_template_items(state, select=state.selected_name)
    return str(getattr(state, "selected_name", "") or ""), ""


def _invalidate_dialog_cache() -> None:
    """The export dialog memoises the template list; a write here must show up."""
    try:
        from . import export_dialog

        export_dialog.invalidate_template_cache()
    except Exception:
        pass


def _template_name_is_free(name: str, infos) -> bool:
    """Whether *name* collides with no existing template, by name OR by file.

    Two checks, because a template has two identities. ``save_user_template``
    writes ``sanitize_template_name(name) + ".json"``, and sanitisation folds
    every non-token character to "_", so "My/Template" and "My_Template" are
    different display names that land on the same file. This is the same path
    comparison ``colliding_template`` makes for the editor's own save.
    """
    wanted = str(name or "").strip().casefold()
    target = _user_template_path(name)
    for info in infos:
        if info.name.casefold() == wanted:
            return False
        if info.builtin:
            # A built-in lives outside the user directory; its NAME is already
            # refused above, and save_user_template refuses it again.
            continue
        if target is not None and _paths_equal(info.path, target):
            return False
    return True


def _unique_user_template_name(base: str) -> str:
    """A template name that overwrites nothing, neither a name nor a file."""
    stem = str(base or NEW_TEMPLATE_NAME).strip() or NEW_TEMPLATE_NAME
    try:
        infos = tuple(export_templates.list_templates())
    except Exception:
        infos = ()
    if _template_name_is_free(stem, infos):
        return stem
    index = 2
    while not _template_name_is_free(f"{stem} {index}", infos):
        index += 1
    return f"{stem} {index}"


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------


class MASTER_BAKER_OT_template_editor_select(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_select"
    bl_label = "Select Output Template"
    bl_description = "Load this output template into the editor"
    bl_options = {"INTERNAL"}

    name: bpy.props.StringProperty(name="Template", default="", options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None:
            return {"CANCELLED"}
        error = load_into_staging(state, self.name)
        if error:
            state.error = error
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        # Kept as a real operator (the export dialog and scripts call it by name);
        # it now also drags the UIList's highlight along.
        sync_template_index(state, state.selected_name)
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_new(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_new"
    bl_label = "New Output Template"
    bl_description = "Create a new output template. It is saved and selected immediately"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        state = editor_state(context)
        if state is None:
            return {"CANCELLED"}
        # The file exists before the operator returns, so the new row is a real
        # template the moment it appears in the list -- no save step in between.
        name, error = new_user_template(state)
        if error:
            state.error = error
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, f"Created output template '{name}'")
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_duplicate(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_duplicate"
    bl_label = "Duplicate Output Template"
    bl_description = (
        "Copy the selected template into a new, editable one, saved immediately. "
        "This is how a built-in template is customised"
    )
    bl_options = {"INTERNAL"}

    name: bpy.props.StringProperty(name="Template", default="", options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None:
            return {"CANCELLED"}
        source = str(self.name or "").strip() or str(getattr(state, "selected_name", "") or "")
        name, error = duplicate_user_template(state, source)
        if error:
            state.error = error
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        self.report({"INFO"}, f"Created output template '{name}'")
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_delete(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_delete"
    bl_label = "Delete Output Template"
    bl_description = "Delete this user template from disk. Built-in templates cannot be deleted"
    bl_options = {"INTERNAL"}

    name: bpy.props.StringProperty(name="Template", default="", options={"HIDDEN"})

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self,
            event,
            title="Delete Output Template",
            message=f"Delete '{self.name}'? The JSON file is removed from disk.",
            confirm_text="Delete",
        )

    def execute(self, context):
        state = editor_state(context)
        name = str(self.name or "").strip()
        if not name:
            return {"CANCELLED"}
        try:
            removed = export_templates.delete_user_template(name)
        except export_templates.TemplateError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        if not removed:
            self.report({"WARNING"}, f"'{name}' is not a user template")
            return {"CANCELLED"}
        _invalidate_dialog_cache()
        if state is not None and str(getattr(state, "selected_name", "")) == name:
            clear_staging(state)
        refresh_template_items(state)
        self.report({"INFO"}, f"Deleted output template '{name}'")
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_add_output(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_add_output"
    bl_label = "Add Output"
    bl_description = "Append a pre-shaped output map to this template"
    bl_options = {"INTERNAL"}

    shape: bpy.props.EnumProperty(name="Shape", items=SHAPE_ITEMS, default=SHAPE_GRAY, options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None or not bool(getattr(state, "loaded", False)):
            return {"CANCELLED"}
        # One autosave for the whole write, not one per field the shape fills in:
        # a half-built output would fail validation and set a spurious error.
        with suspend_autosave():
            append_output(state, self.shape)
        autosave(state)
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_remove_output(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_remove_output"
    bl_label = "Remove Output"
    bl_description = "Remove this output map from the template"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Index", default=0, options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None or not (0 <= self.index < len(state.outputs)):
            return {"CANCELLED"}
        with suspend_autosave():
            state.outputs.remove(self.index)
            state.active_output_index = max(
                0, min(int(state.active_output_index), len(state.outputs) - 1)
            )
            # The selection is a slot of an output that may no longer be the one
            # at this index: drop it rather than let the panel edit a stranger.
            state.active_slot = ""
        # Removing the last output leaves an empty template, which is a legal one:
        # it saves, and the Create row is right there to refill it.
        autosave(state)
        return {"FINISHED"}


def duplicate_output(state, index: int):
    """Copy output ``index`` and place the copy directly after it. Pure.

    ``CollectionProperty`` has no insert, so the copy is appended and moved --
    which is also why the filename is re-uniquified *after* the move: two
    outputs sharing a filename template and a first source are a duplicate
    as far as the validator is concerned, so a plain copy would not save. The
    filename is the axis that moves because the copy must keep reading the same
    bake.
    """
    outputs = getattr(state, "outputs", None)
    if outputs is None or not (0 <= index < len(outputs)):
        return None
    original = outputs[index]
    copy = outputs.add()
    copy.filename = str(getattr(original, "filename", "") or "")
    try:
        copy.format = str(getattr(original, "format", DEFAULT_FORMAT) or DEFAULT_FORMAT)
    except (TypeError, ValueError):
        pass
    set_output_bit_depth(copy, output_bit_depth(original))
    try:
        copy.color_space = str(getattr(original, "color_space", DEFAULT_COLOR_SPACE) or DEFAULT_COLOR_SPACE)
    except (TypeError, ValueError):
        pass
    copy.notes = str(getattr(original, "notes", "") or "")
    ensure_channel_slots(copy)
    for slot in CHANNEL_SLOTS:
        source_entry = channel_for_slot(original, slot)
        target_entry = channel_for_slot(copy, slot)
        if source_entry is None or target_entry is None:
            continue
        target_entry.enabled = bool(getattr(source_entry, "enabled", False))
        try:
            target_entry.source = _entry_source(source_entry)
        except (TypeError, ValueError):
            pass
        try:
            target_entry.channel = str(getattr(source_entry, "channel", "GRAY") or "GRAY")
        except (TypeError, ValueError):
            target_entry.channel = "GRAY"
        try:
            target_entry.variant = entry_variant(source_entry)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            target_entry.variant = DEFAULT_VARIANT
        target_entry.invert = bool(getattr(source_entry, "invert", False))
        target_entry.constant = clamp_constant(getattr(source_entry, "constant", 0.0))
        target_entry.constant_custom = bool(getattr(source_entry, "constant_custom", False))

    outputs.move(len(outputs) - 1, index + 1)
    moved = outputs[index + 1]
    moved.filename = unique_output_filename(
        state, str(getattr(original, "filename", "") or ""), skip=moved
    )
    state.active_output_index = index + 1
    return moved


class MASTER_BAKER_OT_template_editor_duplicate_output(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_duplicate_output"
    bl_label = "Duplicate Output"
    bl_description = (
        "Copy this output map. The copy is placed directly below and given a free "
        "filename so both files can be written"
    )
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Index", default=0, options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None or not (0 <= self.index < len(state.outputs)):
            return {"CANCELLED"}
        with suspend_autosave():
            copy = duplicate_output(state, int(self.index))
        if copy is None:
            return {"CANCELLED"}
        autosave(state)
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_move_output(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_move_output"
    bl_label = "Move Output"
    bl_description = "Reorder this output map"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Index", default=0, options={"HIDDEN"})
    offset: bpy.props.IntProperty(name="Offset", default=-1, options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None:
            return {"CANCELLED"}
        target = int(self.index) + int(self.offset)
        if not (0 <= self.index < len(state.outputs)) or not (0 <= target < len(state.outputs)):
            return {"CANCELLED"}
        with suspend_autosave():
            state.outputs.move(self.index, target)
            state.active_output_index = target
        autosave(state)
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_set_active_output(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_set_active_output"
    bl_label = "Select Output"
    bl_description = "Make this the output the source panel on the right edits"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Index", default=0, options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None or not (0 <= self.index < len(state.outputs)):
            return {"CANCELLED"}
        state.active_output_index = int(self.index)
        state.active_slot = ""
        return {"FINISHED"}


# NOTE: ``master_baker.template_editor_select_block`` used to live here. It was
# the "arm a destination chip, then travel to the source list" half of the old
# hidden mode; the slot's own picker replaced both halves, and nothing selects a
# block as a separate step any more (the picker records the slot it was opened
# from). ``state.active_slot`` survives as the assignment writer's target.


class MASTER_BAKER_OT_template_editor_assign_source(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_assign_source"
    bl_label = "Assign Source Map"
    bl_description = "Feed the selected channel from this map"
    bl_options = {"INTERNAL"}

    #: Empty is a legal value: it is the "Unassigned" row at the top of the source
    #: panel, which clears the map from every slot of the selected block.
    source: bpy.props.StringProperty(name="Source", default="", options={"HIDDEN"})
    #: Explicit read picked in the source popover: one of R/G/B/A/GRAY, or
    #: ``IDENTITY``. A **string**, not an enum, because "" (use the block kind's
    #: default routing) has to be expressible and ``IDENTITY`` is not a channel.
    channel: bpy.props.StringProperty(name="Channel", default="", options={"HIDDEN"})
    #: Occurrence ordinal, for a project holding several bakes of ``source``.
    #: 0 is "the first one", which is what an unset ordinal has always meant.
    #: ``source`` may equally be given as a composite key (``AO#1``); the key wins.
    variant: bpy.props.IntProperty(name="Variant", default=DEFAULT_VARIANT, min=0, options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        del context
        if not str(getattr(properties, "source", "") or "").strip():
            return "Clear the selected channel: the slot stays, with no map assigned"
        routing = str(getattr(properties, "channel", "") or "").strip().upper()
        label = source_label(getattr(properties, "source", ""))
        if routing == ROUTING_IDENTITY:
            return f"Read {label} channel for channel: R←R, G←G, B←B"
        if routing == "GRAY":
            return f"Read {label} as luminance (pass-through for a scalar map)"
        if routing in ("R", "G", "B", "A"):
            return f"Read the {routing} channel of {label}"
        return cls.bl_description

    def execute(self, context):
        state = editor_state(context)
        if state is None:
            return {"CANCELLED"}
        output = active_output(state)
        block = selected_block(state)
        if output is None or block is None:
            self.report({"WARNING"}, "Select a channel block first")
            return {"CANCELLED"}
        identifier, key_variant = split_source_key(self.source)
        if identifier and identifier not in export_templates.valid_source_identifiers():
            self.report({"ERROR"}, f"'{identifier}' is not a bakeable map")
            return {"CANCELLED"}
        with suspend_autosave():
            assign_block_source(
                output,
                block,
                identifier,
                channel=str(self.channel or ""),
                variant=key_variant or int(self.variant or DEFAULT_VARIANT),
            )
        autosave(state)
        return {"FINISHED"}


# NOTE: ``master_baker.template_editor_source_popover`` and
# ``draw_assignment_picker`` used to live here: a hand-rolled picker for the
# *assignment*, opened from an operator button with a chevron glyph faked onto
# it. Blender's own enum dropdown does that job natively (grouped items with
# headings, per-item icons, left-aligned text, real chevron) -- see the
# "assignment dropdown" section -- so that button and its picker body are gone.
# ``MASTER_BAKER_OT_template_editor_assign_source`` stays: it is the scriptable
# way to write an assignment by name.
#
# What follows is a different control: once a map IS assigned, "how is it read"
# and "which bake of it" are two more questions, and they were briefly two more
# dropdowns crowded into the row. They are one popover now -- Substance Painter
# opens exactly this list when a map lands on a channel -- with the read options
# as buttons and the stack index as a typed field beneath them.
# ---------------------------------------------------------------------------


#: Wide enough for "From Material: Transmission" -- the longest read label the
#: list can hold -- without the panel snapping to the small button's width.
CHANNEL_OPTIONS_POPOVER_UI_UNITS_X = 13


def draw_channel_options_popover(layout, output, block, entry, index: int = 0, spec=()) -> None:
    """The popover body: the read options, then the stack index.

    The read list is :func:`channel_read_options` -- Substance Painter's menu
    shape (``From <Map>`` first, then the channels the source can supply), with
    the current read depressed so the popover says what it is set to.

    A scalar map supplies exactly one read, so its list has one entry and is not
    drawn: a lone always-depressed button is not a choice, and the popover is
    then just the stack index.
    """
    source = str(getattr(block, "source", "") or "").strip()
    if not channel_options_available(block):
        return

    reads = channel_read_options(output, block)
    if len(reads) > 1:
        current = block_routing(output, block)
        column = layout.column(align=True)
        for routing, label in reads:
            button = column.operator(
                "master_baker.template_editor_set_channel_read",
                text=label,
                depress=(routing == current),
            )
            button.index = index
            button.slot = block.key
            button.channel = routing
        layout.separator(factor=0.5)

    field = layout.column(align=True)
    field.prop(entry, "stack_index_number")
    if source and not stack_index_resolvable(spec, source, getattr(block, "variant", 0)):
        # Only when it is true, and only here: picking an index this project
        # cannot supply is legal (templates are portable) but the export will
        # skip the channel, which is not guessable from the number alone.
        note = layout.row()
        note.label(text="Not in this project", icon="INFO")


class MASTER_BAKER_OT_template_editor_set_channel_read(bpy.types.Operator):
    """Write one read option from the channel-options popover."""

    bl_idname = "master_baker.template_editor_set_channel_read"
    bl_label = "Source Channel"
    bl_description = "Choose which channel of the source map this output channel reads"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Output", default=0, options={"HIDDEN"})
    slot: bpy.props.StringProperty(name="Slot", default="", options={"HIDDEN"})
    channel: bpy.props.StringProperty(name="Channel", default="", options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        del context
        routing = str(getattr(properties, "channel", "") or "").strip().upper()
        if routing == ROUTING_IDENTITY:
            return "Read the source's own R, G and B into this block's R, G and B"
        if routing == "GRAY":
            return "Read the source's luminance (pass-through for a scalar map)"
        if routing in ("R", "G", "B", "A"):
            return f"Read the {routing} channel of the source map"
        return cls.bl_description

    def execute(self, context):
        state = editor_state(context)
        output = output_at_index(state, int(self.index))
        block = block_for_slot(output, str(self.slot or ""))
        if output is None or block is None:
            return {"CANCELLED"}
        with suspend_autosave():
            assign_block_source(
                output,
                block,
                block.source,
                channel=str(self.channel or ""),
                variant=int(getattr(block, "variant", 0) or 0),
            )
        autosave(state)
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_channel_options(bpy.types.Operator):
    """Open the read/stack-index popover for one channel block.

    ``wm.popover`` takes a draw callback Blender calls with none of our
    arguments, so ``execute`` closes over the row identity (output index + block
    key) and hands that closure over -- the same trick the token popover uses.
    """

    bl_idname = "master_baker.template_editor_channel_options"
    bl_label = "Channel Options"
    bl_description = "Choose which channel of the source map to read, and which bake of it"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Output", default=0, options={"HIDDEN"})
    slot: bpy.props.StringProperty(name="Slot", default="", options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        output_index = int(self.index)
        slot = str(self.slot or "")
        output = output_at_index(state, output_index)
        block = block_for_slot(output, slot)
        if output is None or block is None:
            return {"CANCELLED"}
        spec = current_variant_spec(context) or ()

        def draw(panel, panel_context):
            del panel_context
            live_output = output_at_index(editor_state(), output_index)
            live_block = block_for_slot(live_output, slot)
            if live_block is None:
                return
            anchor = channel_for_slot(live_output, live_block.slots[0])
            if anchor is None:
                return
            draw_channel_options_popover(
                panel.layout, live_output, live_block, anchor, output_index, spec
            )

        window_manager = getattr(context, "window_manager", None)
        if window_manager is None:
            return {"CANCELLED"}
        try:
            window_manager.popover(draw, ui_units_x=CHANNEL_OPTIONS_POPOVER_UI_UNITS_X)
        except Exception as error:  # pragma: no cover - Blender-only
            self.report({"WARNING"}, f"Could not open the channel options: {error}")
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_toggle_invert(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_toggle_invert"
    bl_label = "Invert"
    bl_description = (
        "Write 1 - value for this channel (roughness to smoothness, AO to "
        "occlusion). A grouped RGB or Gray block inverts all of its slots together"
    )
    bl_options = {"INTERNAL"}

    #: Addressed per row like the other per-output operators. Left at the
    #: defaults the operator still falls back to the active block, which is what
    #: any external caller invoking it bare would expect.
    index: bpy.props.IntProperty(name="Output", default=-1, options={"HIDDEN"})
    slot: bpy.props.StringProperty(name="Slot", default="", options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None:
            return {"CANCELLED"}
        if 0 <= self.index < len(state.outputs) and str(self.slot or "").strip():
            output = state.outputs[int(self.index)]
            block = block_for_slot(output, str(self.slot))
        else:
            output = active_output(state)
            block = selected_block(state)
        if output is None or block is None:
            return {"CANCELLED"}
        with suspend_autosave():
            set_block_invert(output, block, not block_invert(output, block))
        autosave(state)
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_toggle_alpha(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_toggle_alpha"
    bl_label = "Alpha Channel"
    bl_description = (
        "Add or remove this output's alpha channel. Removing it keeps the "
        "assignment, so turning alpha back on restores the same source map"
    )
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Output", default=0, options={"HIDDEN"})
    enable: bpy.props.BoolProperty(name="Enable", default=True, options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        if state is None or not (0 <= self.index < len(state.outputs)):
            return {"CANCELLED"}
        output = state.outputs[self.index]
        with suspend_autosave():
            set_alpha_enabled(output, bool(self.enable))
            if not self.enable and str(getattr(state, "active_slot", "")) == "A":
                state.active_slot = ""
            elif self.enable:
                state.active_slot = "A"
        autosave(state)
        return {"FINISHED"}


def _token_enum_items(self, context):
    del self, context
    return _TOKEN_ITEMS


_TOKEN_ITEMS = tuple(
    (name, f"${name}", description) for name, description in export_tokens.TOKEN_ITEMS
)


#: How wide the token popover opens, in Blender UI units. 14 is what fits the
#: longest token (``$resolution``) without the panel snapping to the button's
#: width, which is what a popover does when it is not told a size.
TOKEN_POPOVER_UI_UNITS_X = 14


def token_popover_rows() -> tuple:
    """``(token, label, description)`` per popover button. Pure; cached tuple."""
    return _TOKEN_ITEMS


def draw_token_popover(layout, index: int) -> None:
    """The popover body: one full-width button per known filename token."""
    column = layout.column(align=True)
    for name, label, _description in token_popover_rows():
        button = column.operator("master_baker.template_editor_insert_token", text=label)
        button.index = int(index)
        button.token = name


class MASTER_BAKER_OT_template_editor_token_popover(bpy.types.Operator):
    """Open the filename-token list for one output row.

    A popover rather than ``operator_menu_enum``: the enum menu is a dropdown of
    bare identifiers with nowhere to put a token's description, and it inherits
    the button's width. ``wm.popover`` takes a *draw callback*, which Blender
    calls with no arguments of ours -- so ``execute`` closes over the output
    index and hands that closure over, which is how the row identity survives
    into a panel that is drawn later.
    """

    bl_idname = "master_baker.template_editor_token_popover"
    bl_label = "Filename Tokens"
    bl_description = "Append a filename token to this output's filename"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Index", default=0, options={"HIDDEN"})

    def execute(self, context):
        index = int(self.index)

        def draw(panel, panel_context):
            del panel_context
            draw_token_popover(panel.layout, index)

        window_manager = getattr(context, "window_manager", None)
        if window_manager is None:
            return {"CANCELLED"}
        try:
            window_manager.popover(draw, ui_units_x=TOKEN_POPOVER_UI_UNITS_X)
        except Exception as error:  # pragma: no cover - Blender-only
            self.report({"WARNING"}, f"Could not open the token list: {error}")
            return {"CANCELLED"}
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_insert_token(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_insert_token"
    bl_label = "Insert Token"
    bl_description = "Append a filename token to this output's filename"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty(name="Index", default=0, options={"HIDDEN"})
    token: bpy.props.EnumProperty(name="Token", items=_token_enum_items, options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        """The popover buttons carry only ``$name``; the tooltip explains it."""
        del context
        wanted = str(getattr(properties, "token", "") or "")
        for name, label, description in token_popover_rows():
            if name == wanted:
                return f"Append {label}: {description}"
        return cls.bl_description

    def execute(self, context):
        state = editor_state(context)
        if state is None or not (0 <= self.index < len(state.outputs)):
            return {"CANCELLED"}
        output = state.outputs[self.index]
        # Blender text fields expose no caret position to Python (there is no
        # RNA for the edit cursor), so a token can only be APPENDED, never
        # inserted where the user is typing. Documented limitation, same as the
        # plan's section 3.2 note.
        # The filename property's own update= hook is the autosave for this: it
        # fires on assignment, so calling autosave here too would write twice.
        output.filename = f"{output.filename}${self.token}"
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_import(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_import"
    bl_label = "Import Template"
    bl_description = "Import an output template JSON file into your user templates"
    bl_options = {"INTERNAL"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="")
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        del event
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        state = editor_state(context)
        path = Path(str(self.filepath or ""))
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            self.report({"ERROR"}, f"Could not read {path.name}: {error}")
            return {"CANCELLED"}

        payload = dict(data or {})
        payload.setdefault("schema", export_templates.TEMPLATE_SCHEMA)
        errors = export_templates.validate_template(payload)
        if errors:
            self.report({"ERROR"}, f"{path.name} is not a valid output template: " + "; ".join(errors[:3]))
            return {"CANCELLED"}

        name = _unique_user_template_name(str(payload.get("name") or path.stem))
        try:
            saved = export_templates.save_user_template(payload, template_name=name)
        except export_templates.TemplateError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        _invalidate_dialog_cache()
        if state is not None:
            load_into_staging(state, name)
        refresh_template_items(state, select=name)
        self.report({"INFO"}, f"Imported '{name}' to {saved}")
        return {"FINISHED"}


class MASTER_BAKER_OT_template_editor_export(bpy.types.Operator):
    bl_idname = "master_baker.template_editor_export"
    bl_label = "Export Template"
    bl_description = "Write the template currently in the editor to a JSON file"
    bl_options = {"INTERNAL"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="")
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        del event
        state = editor_state(context)
        stem = export_templates.sanitize_template_name(
            str(getattr(state, "template_name", "") or "output_template") if state is not None else "output_template"
        )
        self.filepath = f"{stem}.json"
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        state = editor_state(context)
        if state is None or not bool(getattr(state, "loaded", False)):
            self.report({"ERROR"}, "Load a template into the editor first")
            return {"CANCELLED"}
        payload = staging_to_template(state)
        errors = export_templates.validate_template(payload)
        if errors:
            self.report({"ERROR"}, "Template is invalid: " + "; ".join(errors[:3]))
            return {"CANCELLED"}
        path = Path(str(self.filepath or ""))
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except OSError as error:
            self.report({"ERROR"}, f"Could not write {path}: {error}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Exported output template to {path}")
        return {"FINISHED"}


class MASTER_BAKER_OT_open_template_editor(bpy.types.Operator):
    """Jump from the export dialog to the preferences tab that edits templates.

    What this can focus automatically (verified on Blender 5.1.1):

    * opening the Preferences window -- ``screen.userpref_show``;
    * the Add-ons section, the "All" filter, the add-on search field and the
      add-on's expanded state -- all four are exactly what Blender's own
      ``preferences.addon_show`` does, so it is called rather than reimplemented;
    * the add-on's ``pref_tabs`` enum, set directly on the preferences instance.

    What it cannot: Blender exposes no API to scroll the add-ons list to a
    specific entry, so on a long add-on list the expanded Fyr Baker entry may sit
    below the fold and the user has to scroll. Setting ``addon_search`` filters
    the list down to one row, which is the closest the API gets.
    """

    bl_idname = "master_baker.open_template_editor"
    bl_label = "Edit Templates…"
    bl_description = "Open the output-template editor in the add-on preferences"

    template_name: bpy.props.StringProperty(name="Template", default="", options={"HIDDEN"})

    def execute(self, context):
        state = editor_state(context)
        wanted = str(self.template_name or "").strip()
        if not wanted:
            wanted = _template_name_from_export_settings(context)
        # No dirty check any more: staging is never ahead of disk, so loading the
        # dialog's template can't discard an unsaved edit.
        if state is not None and wanted:
            load_into_staging(state, wanted)

        try:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT")
        except Exception as error:  # pragma: no cover - Blender-only
            self.report({"WARNING"}, f"Could not open Preferences: {error}")

        preferences = getattr(context, "preferences", None)
        if preferences is not None:
            try:
                preferences.active_section = "ADDONS"
            except Exception:
                pass
        try:
            # Sets ADDONS + filter All + addon_search + show_expanded in one go.
            bpy.ops.preferences.addon_show(module=__package__)
        except Exception:
            pass

        try:
            from . import preferences as preferences_module

            addon_prefs = preferences_module.get_preferences()
            if addon_prefs is not None:
                addon_prefs.pref_tabs = "EXPORT_TEMPLATES"
        except Exception:
            pass
        return {"FINISHED"}


def _template_name_from_export_settings(context) -> str:
    """The template the export dialog currently has selected, if any."""
    try:
        from . import export_dialog, properties

        project = properties.get_active_project(getattr(context, "scene", None))
        settings = export_dialog.active_export_settings(project) if project is not None else None
        if settings is None:
            return ""
        return export_dialog.resolve_template_name(settings)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------


#: How tall the template list runs. The left column has nothing else in it, so
#: the list may as well use the height -- 12 rows is roughly the point at which
#: the pane stops looking like a stub next to the two columns beside it.
TEMPLATE_LIST_ROWS = 12


class MASTER_BAKER_UL_output_templates(bpy.types.UIList):
    """The left column's list of templates.

    Draws the *mirror* collection (see the module's mirror section): a built-in
    carries the lock, a user template a document icon, and the name is a plain
    left-aligned label because the row is not where a template is renamed --
    that is the name field in column 2, which writes a new file on Save.
    """

    bl_idname = "MASTER_BAKER_UL_output_templates"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        del context, data, icon, active_data, active_propname, index
        name = str(getattr(item, "name", "") or "")
        row = layout.row(align=True)
        if self.layout_type == "GRID":
            row.alignment = "CENTER"
            row.label(text="", icon="LOCKED" if getattr(item, "builtin", False) else "FILE_TEXT")
            return
        row.alignment = "LEFT"
        row.label(text=name, icon="LOCKED" if getattr(item, "builtin", False) else "FILE_TEXT")


def _draw_template_list(layout, state) -> None:
    column = layout.column()

    infos = template_infos()
    rows = build_template_items(infos)
    selected = str(getattr(state, "selected_name", "") or "")
    selected_info = next((info for info in infos if info.name == selected), None)

    header = column.row(align=True)
    caption = header.row(align=True)
    caption.alignment = "LEFT"
    caption.label(text="Output Templates", icon="PRESET")

    # Icon-only, right-aligned: the list below is the subject of the column, and
    # five labelled buttons under it were reading as the column's content.
    tools = header.row(align=True)
    tools.alignment = "RIGHT"
    duplicate_row = tools.row(align=True)
    duplicate_row.enabled = selected_info is not None
    duplicate_row.operator(
        "master_baker.template_editor_duplicate", text="", icon="DUPLICATE"
    ).name = selected
    delete_row = tools.row(align=True)
    # Built-ins are shipped assets: selectable and duplicable, never deletable.
    delete_row.enabled = selected_info is not None and not selected_info.builtin
    delete_row.operator("master_baker.template_editor_delete", text="", icon="REMOVE").name = selected
    tools.operator("master_baker.template_editor_new", text="", icon="ADD")
    tools.separator()
    tools.operator("master_baker.template_editor_import", text="", icon="IMPORT")
    export_row = tools.row(align=True)
    export_row.enabled = bool(getattr(state, "loaded", False))
    export_row.operator("master_baker.template_editor_export", text="", icon="EXPORT")

    # NEVER write the mirror from draw() -- resizing a collection Blender is
    # iterating is a crash, not a glitch. Detect the drift, defer the rebuild.
    if not template_items_match(getattr(state, "templates", ()) or (), rows):
        _schedule_template_refresh()

    if not rows:
        column.box().column().label(text="No templates found", icon="ERROR")
    else:
        body = column.row()
        body.template_list(
            "MASTER_BAKER_UL_output_templates",
            "",
            state,
            "templates",
            state,
            "template_index",
            rows=TEMPLATE_LIST_ROWS,
        )

    hint = column.row()
    hint.enabled = False
    hint.scale_y = 0.85
    # Short enough to survive the 22% column without mid-string truncation.
    hint.label(text="Built-ins: duplicate to edit", icon="INFO")


#: Column geometry. Two nested splits, because ``layout.split`` only ever makes
#: two children: 22% template list | ~55% preset editor | ~23% reference column.
#: The second factor is the middle column's share *of what is left*. The middle
#: column carries the wide assignment buttons now, and the right one is a
#: read-only legend + validation list, so the weight moved left (0.64 -> 0.70).
COLUMN_LIST_FACTOR = 0.22
COLUMN_EDITOR_FACTOR = 0.70

#: Header-row geometry, as ``scale_x`` weights inside one aligned row. The
#: filename takes whatever the fixed-width cells beside it leave, because it is
#: the field that gets typed into. (``_HEADER_LABEL_SCALE`` lived here for the
#: map-label field; that field is gone from the card -- see _draw_output_header.)
_HEADER_TOKEN_SCALE = 0.4
_HEADER_SPEC_SCALE = 0.7

#: Share of the channel row given to ``[letters][chip][assignment]``. The rest
#: carries the channel-options popover (or a Custom constant's value field) and
#: the invert toggle at its right edge.
#:
#: Tuned on screen, three times. 0.70 (two small dropdowns in the tail) and then
#: 0.52 both left the assignment far wider than the map names in it. The tail is
#: one compact button now, so this is deliberately **short of** what the row
#: could give the dropdown: the leftover is empty space, which is what Glow asked
#: for -- a row with air in it rather than a wall of adjacent widgets.
_ASSIGN_ROW_SPLIT = 0.44

#: How far the channel rows sit in from the card's left edge, so the chip column
#: is clearly subordinate to the header above it.
_CHANNEL_INDENT = 4.0

#: The qualifier popover button says "Gray" / "R #2" -- a word, so it is sized a
#: little wider than the header's one-glyph ``$`` button and no more. It is only
#: a multiplier on the *content* width: the row it sits in is aligned LEFT, so
#: the button does not stretch to its share of the row.
_QUALIFIER_BUTTON_SCALE = 1.5

#: Blank space between one card's box and the next one's, so a template reads as
#: a stack of separate objects rather than as one long panel.
_CARD_TRAILING_AIR = 0.5

#: Taller channel rows. The assignment is the primary control of the editor and
#: at default height four of them stack into an unreadable brick; the reference
#: design gives each one real vertical presence.
_CHANNEL_ROW_SCALE = 1.35

#: The header carries the output's identity (label + filename), so it sits a
#: touch taller than the channel rows under it.
_HEADER_ROW_SCALE = 1.25

#: Air before the options line, so a card reads as three bands, not one stack.
_CARD_BAND_AIR = 0.45

#: Air between the header band (name, format, bit depth) and the first channel
#: row. Bigger than the band air below it, because that is the seam Glow reads
#: the card at: "what this file is" above, "what goes in it" below.
_CARD_HEADER_AIR = 1.1

#: How far the stack of cards sits in from the column's left edge. Most of the
#: inset is the box's own padding now; this is the last bit on top of it, so the
#: cards do not run flush against the pane and read as its chrome.
_CARD_LEFT_INDENT = 1.2


def _draw_channel_rows(layout, state, output, index: int, *, readonly: bool) -> None:
    """One row per channel block: ``[chip] [ assignment v ] [component] [invert]``.

    The assignment is the primary control of the whole editor, and it is
    Blender's **own** enum dropdown (``prop(entry, "assignment")``) rather than
    an operator button with a chevron drawn on it: that is what gives it
    left-aligned text, the chevron on the right and the native rounded styling,
    and it is why the menu can carry group headings and per-item status icons.
    It is bound to the block's **anchor slot**, so the row needs no context
    threading -- the entry finds its own output (see :func:`entry_output`).

    The chip beside it is a *label*, not a button -- with the assignment spelled
    out in words the colour is a scanning aid, and a second control opening the
    same menu would only be a second thing to explain.

    Two small controls appear to its right, each only when it has something to
    say: the source-**component** dropdown when the read is genuinely ambiguous
    (a colour map into one slot), and a **value** field when the assignment is a
    Custom constant. They are mutually exclusive by construction -- a constant is
    not a colour source.
    """
    del state
    blocks = output_blocks(output)
    if not blocks:
        empty = layout.row(align=True)
        empty.alert = True
        empty.operator(
            "master_baker.template_editor_set_active_output",
            text="no channels",
            icon="ERROR",
        ).index = index
        return

    # align=False: fused rows drew as one continuous slab of widgets. A hairline
    # between them is what makes four assignments read as four things.
    # NEVER put scale_y on the split below -- it silently suppresses icon-only
    # labels inside it, which made every channel chip vanish. Row height belongs
    # on the enclosing column.
    column = layout.column(align=False)
    column.scale_y = _CHANNEL_ROW_SCALE
    for block in blocks:
        entry = channel_for_slot(output, block.key)
        # Split, not a plain row: the dropdown would otherwise stretch the full
        # column width and leave no quiet space for the qualifiers beside it.
        split = column.split(factor=_ASSIGN_ROW_SPLIT, align=False)

        # Everything that names the assignment goes in the split's FIRST child --
        # `factor` sizes that child alone and the remaining children share what is
        # left, so these have to be wrapped together rather than added to the
        # split directly. Bounding the button this way stops its centred text from
        # floating across the whole column and leaves the right side quiet.
        row = split.row(align=True)
        # Indent the channel rows inside this row, before the chip -- NOT by
        # wrapping the whole column in a row with a leading separator. That was
        # tried and it silently collapsed the icon-only chip label, the same
        # failure mode as scale_y on a split. Indenting within the row that
        # already exists changes nothing structural, so the chip survives.
        row.separator(factor=_CHANNEL_INDENT)

        # SP convention: the chip IS the colored block, letter baked into a
        # pre-generated PNG (scripts/generate_chip_icons.py) -- so the chip
        # already says "RGB"/"R"/"A" and a text label beside it only says it
        # twice. The letters come back ONLY as a fallback, when the chip PNGs are
        # unavailable (stripped install) and the plain swatch carries no letter:
        # without them the row would not say which slot it is at all.
        chip_icon = chip_icon_value(block.label, block.source)
        if not chip_icon:
            letters = row.row(align=True)
            letters.alignment = "LEFT"
            letters.label(text=block_slot_letters(block))

        chip = row.row(align=True)
        chip.alignment = "LEFT"
        chip.label(text="", icon_value=chip_icon or swatch_icon_value(block.source))

        picker = row.row(align=True)
        picker.enabled = not readonly
        # THE control: Blender's native enum dropdown, bound to this block's own
        # anchor slot. Nothing is threaded through an operator any more.
        picker.prop(entry, "assignment", text="")

        tail = split.row(align=False)
        tail.enabled = not readonly

        if channel_options_available(block):
            # ONE button, not the two dropdowns this used to be: "which channel
            # of the source" and "which bake of it" are both qualifiers on the
            # assignment beside them, and side by side they read as three
            # competing controls. The popover is also where SP puts the same list.
            #
            # alignment=LEFT is what stops it filling its share of the row: it
            # was drawn expanded with a chevron and read as a second dropdown
            # rather than as a button. Sized like the header's `$` -- a little
            # wider, because it carries a word rather than one glyph -- with the
            # leftover width left EMPTY between it and the invert toggle, which
            # is the air that keeps the row from reading as a solid bar.
            options = tail.row(align=True)
            options.alignment = "LEFT"
            options.scale_x = _QUALIFIER_BUTTON_SCALE
            button = options.operator(
                "master_baker.template_editor_channel_options",
                text=channel_options_summary(output, block),
            )
            button.index = index
            button.slot = block.key
        elif entry_is_custom_constant(entry):
            value = tail.row(align=True)
            value.prop(entry, "constant", text="")

        invert = tail.row(align=True)
        invert.alignment = "RIGHT"
        toggle = invert.operator(
            "master_baker.template_editor_toggle_invert",
            text="",
            icon=INVERT_ICON,
            depress=block_invert(output, block),
        )
        toggle.index = index
        toggle.slot = block.key


def _draw_output_header(layout, output, index: int, *, readonly: bool) -> None:
    """``[dot] [filename]  [$]  [format] [depth]  [copy] [X]``.

    ``align=False`` on the outer row: the ``$`` token button used to be fused
    into the same aligned run as the filename and the format, which gave it
    square shoulders on both sides and made it read as part of the field rather
    than as its own action. Each group is aligned internally and detached from
    its neighbours, so ``$`` is a rounded button of its own.
    """
    row = layout.row(align=False)
    row.scale_y = _HEADER_ROW_SCALE

    dot = row.row(align=True)
    dot.alignment = "LEFT"
    dot.label(text="", icon_value=swatch_icon_value(output_primary_source(output)))

    # NOTE: a per-output "map label" field used to sit here, before the filename.
    # The whole concept is gone -- field, property, JSON key and validation.
    # ``$map`` is retired entirely; templates now name their maps literally.
    fields = row.row(align=True)
    fields.enabled = not readonly
    fields.prop(output, "filename", text="", placeholder=DEFAULT_FILENAME)

    # Its own detached, rounded button -- not fused onto the filename field.
    # A popover, not operator_menu_enum: the enum menu drew as a cramped dropdown
    # of identifiers with no room for the token descriptions. The operator's
    # execute() closes over this index and hands the closure to wm.popover, which
    # is how the index reaches a draw callback Blender passes no arguments to.
    token_cell = row.row(align=True)
    token_cell.enabled = not readonly
    token_cell.scale_x = _HEADER_TOKEN_SCALE
    token_cell.operator("master_baker.template_editor_token_popover", text="$").index = index

    spec = row.row(align=True)
    spec.enabled = not readonly
    spec.scale_x = _HEADER_SPEC_SCALE
    spec.prop(output, "format", text="")
    spec.prop(output, "bit_depth", text="")

    tools = row.row(align=True)
    tools.enabled = not readonly
    tools.alignment = "RIGHT"
    tools.operator(
        "master_baker.template_editor_duplicate_output", text="", icon="DUPLICATE"
    ).index = index
    tools.operator("master_baker.template_editor_remove_output", text="", icon="X").index = index


def _draw_output_options(layout, state, output, index: int, *, readonly: bool) -> None:
    """The per-output tail: colour space, note, alpha, reorder.

    These used to live in the right-hand column, under whichever block was
    selected. The right column is a reference legend now, so they moved onto the
    output they belong to -- which is also where they were always about to be
    looked for.

    Reordering stays Up / Down: Blender exposes no drop target for a
    Python-drawn button (``FileHandler`` covers external files into editors
    only), so the mockup's drag handles cannot be built.
    """
    row = layout.row(align=True)
    row.enabled = not readonly

    settings = row.row(align=True)
    settings.prop(output, "color_space", text="")
    if str(getattr(output, "format", "") or "").strip().upper() == constants.IMAGE_FORMAT_DDS:
        settings.prop(output, "dds_compression", text="")
    settings.prop(output, "notes", text="", placeholder="Optional note")

    tools = row.row(align=True)
    tools.alignment = "RIGHT"
    alpha = channel_for_slot(output, "A")
    has_alpha = alpha is not None and bool(getattr(alpha, "enabled", False))
    toggle = tools.operator(
        "master_baker.template_editor_toggle_alpha",
        text="",
        icon="IMAGE_ALPHA",
        depress=has_alpha,
    )
    toggle.index = index
    toggle.enable = not has_alpha

    up = tools.row(align=True)
    up.enabled = index > 0
    move_up = up.operator("master_baker.template_editor_move_output", text="", icon="TRIA_UP")
    move_up.index = index
    move_up.offset = -1
    down = tools.row(align=True)
    down.enabled = index < len(getattr(state, "outputs", ()) or ()) - 1
    move_down = down.operator("master_baker.template_editor_move_output", text="", icon="TRIA_DOWN")
    move_down.index = index
    move_down.offset = 1


def _draw_output_footer(layout, output) -> None:
    """The card's closing strip: blank air, plus this output's token alert.

    It used to print ``Example:  T_Skull_D.png`` here. Glow read that as filler
    and it is gone -- but the *space* it occupied is not: the cards need the
    breathing room at the bottom or they read as busy. So the row stays, empty,
    sized to what the label took.

    The unknown-``$token`` alert is a real warning and stays per-card: it is
    about this output's filename, and with the UIList gone nothing on screen
    says which output is active, so a lone warning would have named an arbitrary
    card.
    """
    # An empty label, not layout.separator(): a separator's height is a fraction
    # of a row, and the point is to hold exactly the line the example occupied.
    spacer = layout.row(align=True)
    spacer.active = False
    spacer.label(text="")

    unknown = export_tokens.find_unknown_tokens(str(getattr(output, "filename", "") or ""))
    if unknown:
        warning = layout.row()
        warning.alert = True
        warning.label(text="Unknown token(s): " + ", ".join(f"${name}" for name in unknown), icon="ERROR")


def _draw_output_row(layout, state, output, index: int, *, readonly: bool) -> None:
    """One output map, top to bottom: header, channel rows, options, footer.

    The whole editor for the output is here -- there is nothing left in the
    right-hand column to travel to, which is the redesign.
    """
    # A real box: it IS the card the reference shows, and it brings the border,
    # the background and most of the left inset with it -- so the manual gutter
    # that used to indent a bare column is gone rather than stacked on top of the
    # box's own padding. (This is only possible now the UIList is: a box inside a
    # UIList row fought the active-row highlight and could not cover it.)
    box = layout.box().column(align=True)
    _draw_output_header(box, output, index, readonly=readonly)
    # Deliberately more air here than under the channels: this is the seam
    # between "what this file is" and "what goes in it".
    box.separator(factor=_CARD_HEADER_AIR)
    _draw_channel_rows(box, state, output, index, readonly=readonly)
    box.separator(factor=_CARD_BAND_AIR)
    _draw_output_options(box, state, output, index, readonly=readonly)
    _draw_output_footer(box, output)


def _draw_output_cards(layout, state, outputs, readonly: bool) -> None:
    """The stack of output cards, in order. One :func:`layout.box` each.

    This used to be a ``UIList`` (``MASTER_BAKER_UL_output_maps``), added purely
    so a long template scrolled inside its own pane instead of growing the
    Preferences page. That was a fix for the *old* one-line-per-output layout and
    it costs more than it saves now (Glow's call, 2026-08-05): Blender draws a
    UIList's active-row highlight assuming a one-line row, so on a 5-6 line card
    the highlight covers the header line and stops -- verified on screen, and not
    fixable from Python (wrapping the card in a ``box()`` does not cover the band
    and there is no flag to size it). The list also constrained the row's
    formatting and fought the per-card spacing.

    A long template makes the page tall again. That is accepted: no scrolling
    machinery comes back.
    """
    # The stack is indented as a whole; each card's box supplies the rest.
    gutter = layout.row(align=False)
    gutter.separator(factor=_CARD_LEFT_INDENT)
    column = gutter.column(align=False)
    for index, output in enumerate(outputs):
        _draw_output_row(column, state, output, index, readonly=readonly)
        column.separator(factor=_CARD_TRAILING_AIR)


def _draw_preset_header(layout, state, readonly: bool) -> None:
    """``Current preset:`` plus the name, notes and the built-in escape hatch."""
    header = layout.column(align=True)
    top = header.row(align=True)
    caption = top.row(align=True)
    caption.alignment = "LEFT"
    caption.label(text="Current preset:")

    if readonly:
        title = top.row(align=True)
        title.label(text=str(getattr(state, "template_name", "") or ""), icon="LOCKED")
        notes = str(getattr(state, "notes", "") or "")
        if notes:
            note_row = header.row()
            note_row.active = False
            note_row.label(text=notes, icon="TEXT")
        action = top.row(align=True)
        action.alignment = "RIGHT"
        action.operator(
            "master_baker.template_editor_duplicate", text="Duplicate to Edit", icon="DUPLICATE"
        ).name = state.selected_name
        return

    name_field = top.row(align=True)
    name_field.scale_x = 1.6
    name_field.prop(state, "template_name", text="", icon="PRESET", placeholder="Template name")
    top.prop(state, "notes", text="", placeholder="Optional description", icon="TEXT")

    shadowed = shadowed_builtin_name(getattr(state, "template_name", ""))
    if shadowed:
        alert = header.row()
        alert.alert = True
        alert.label(text=f"'{shadowed}' is a built-in name. Choose another before saving", icon="ERROR")
    elif str(getattr(state, "source_builtin_name", "") or ""):
        origin = header.row()
        origin.active = False
        origin.label(text=f"Based on '{state.source_builtin_name}'", icon="DUPLICATE")


def _draw_preset_editor(layout, state) -> None:
    """Column 2: the template being edited, one card per output map."""
    if not bool(getattr(state, "loaded", False)):
        placeholder = layout.column()
        placeholder.separator()
        placeholder.label(text="Select a template on the left, or press New.", icon="INFO")
        placeholder.label(text="Built-in templates are read-only. Duplicate one to edit it.")
        return

    readonly = is_readonly(state)
    _draw_preset_editor_body(layout, state, readonly)


def _draw_preset_editor_body(layout, state, readonly: bool) -> None:
    _draw_preset_header(layout, state, readonly)

    outputs = list(getattr(state, "outputs", ()) or ())

    layout.separator(factor=0.8)
    tools = layout.row(align=True)
    caption = tools.row(align=True)
    caption.alignment = "LEFT"
    caption.label(text="Output maps", icon="RENDERLAYERS")
    create = tools.row(align=True)
    create.enabled = not readonly
    create.alignment = "RIGHT"
    create.label(text="Create:")
    for identifier, label, _description in SHAPE_ITEMS:
        create.operator("master_baker.template_editor_add_output", text=label).shape = identifier

    # No "examples below use a texture set named ..." note any more: the per-card
    # example line it explained is gone, so it named nothing.
    layout.separator(factor=0.3)

    if not outputs:
        layout.box().column().label(text="No outputs yet. Use the Create row above.", icon="INFO")
    else:
        _draw_output_cards(layout, state, outputs, readonly)
    layout.separator(factor=0.3)

    if str(getattr(state, "error", "") or ""):
        error_box = layout.box().column(align=True)
        error_box.alert = True
        for message in str(state.error).split("; ")[:6]:
            error_box.label(text=message, icon="ERROR")

    # No Save/Revert footer: every valid edit is already on disk (see the
    # Autosave section). Export is the only way a template leaves the addon.


def grouped_source_items() -> tuple[tuple[str, tuple], ...]:
    """The source panel's two lists: material channels, then mesh maps.

    Both come out of :func:`source_items_tuple`, so the panel offers exactly what
    the template editor can assign. Material-channel effective types live under
    Material channels; bare ``MAP_MATERIAL`` is excluded (see
    :data:`_TEMPLATE_EDITOR_EXCLUDED_SOURCES`).
    """
    material: list[tuple[str, str, str]] = []
    mesh: list[tuple[str, str, str]] = []
    for item in source_items_tuple():
        (material if is_material_channel_source(item[0]) else mesh).append(item)
    return (("Material channels", tuple(material)), ("Mesh maps", tuple(mesh)))


def used_source_keys(state) -> frozenset:
    """Composite source keys referenced by the staged template (type + stack index)."""
    used = set()
    for output in getattr(state, "outputs", ()) or ():
        for slot in CHANNEL_SLOTS:
            entry = channel_for_slot(output, slot)
            if entry is None or not bool(getattr(entry, "enabled", False)):
                continue
            source = str(getattr(entry, "source", "") or "").strip().upper()
            if not source or is_constant_source(source):
                if source:
                    used.add(source)
                continue
            used.add(build_source_key(source, entry_variant(entry)))
    return frozenset(used)


def available_source_legend() -> list[tuple[str, str, str]]:
    """``(legend_key, label, map_type)`` rows for the Available Sources panel.

    One row per assignable map **type**, and deliberately **not** a function of
    the open project: a template is authored for projects that are not open, so
    a legend that grew an ``AO #2`` row only while this project happened to hold
    two AO bakes would be advertising something the template cannot rely on.
    Which bake a channel reads is the channel-options popover's question.
    """
    rows: list[tuple[str, str, str]] = []
    for _title, items in grouped_source_items():
        for identifier, label, _description in items:
            map_type = str(identifier or "").strip().upper()
            rows.append((map_type, label, map_type))
    return rows


def _legend_source_in_use(map_type: str, used: frozenset) -> bool:
    """Whether any staged channel references ``map_type`` (any stack index). Pure."""
    wanted = str(map_type or "").strip().upper()
    if not wanted:
        return False
    for key in used:
        base, _ordinal = split_source_key(key)
        if str(base or key).strip().upper() == wanted:
            return True
    return False


#: A legend row is a plain label, so it can be packed tighter than a button.
_LEGEND_SCALE_Y = 0.85


def _draw_available_sources(layout, used: frozenset = frozenset()) -> None:
    """The reference legend: every assignable map, coloured if this preset uses it.

    Labels, not buttons. This column stopped being the assignment mechanism when
    the slots became the primary control -- what is left is the question it was
    always best at answering, "what can I use, and what am I already using".
    """
    legend_rows = available_source_legend()
    if legend_rows:
        current_group = None
        for legend_key, label, map_type in legend_rows:
            group_title = (
                "Material channels"
                if is_material_channel_source(map_type)
                else "Mesh maps"
            )
            if group_title != current_group:
                if current_group is not None:
                    layout.separator(factor=0.4)
                heading = layout.row()
                heading.active = False
                heading.label(text=group_title)
                current_group = group_title
            group = layout.column(align=True)
            group.scale_y = _LEGEND_SCALE_Y
            in_use = _legend_source_in_use(map_type, used)
            group.label(
                text=label,
                icon_value=swatch_icon_value(map_type if in_use else ""),
            )
        return

    for title, items in grouped_source_items():
        if not items:
            continue
        heading = layout.row()
        heading.active = False
        heading.label(text=title)
        group = layout.column(align=True)
        group.scale_y = _LEGEND_SCALE_Y
        for identifier, label, _description in items:
            # Colored swatch only when this preset uses the map; the unset
            # swatch is the same dark chip an unassigned slot shows.
            group.label(
                text=label,
                icon_value=swatch_icon_value(identifier if identifier in used else ""),
            )
        layout.separator(factor=0.4)


#: Key of Glow's validation glyph in ``sidebar_icons`` (icons/ui/Validation_Check.png).
VALIDATION_OK_ICON = "validation_check"


def validation_ok_icon_value() -> int:
    """``icon_value=`` for the all-good row, or ``0`` when it is unavailable."""
    try:
        return int(sidebar_icons.get_icon_value(VALIDATION_OK_ICON) or 0)
    except Exception:  # pragma: no cover - defensive
        return 0


def _draw_validation(layout, state) -> None:
    """The validation read-out. See :func:`validate_staging` for the rules."""
    issues = validate_staging(state)
    box = layout.box().column(align=True)
    caption = box.row()
    caption.alignment = "LEFT"
    caption.label(text="Validation")
    if not issues:
        # Glow's own check glyph. ``get_icon_value`` answers 0 when the preview
        # collection is unavailable (stripped install, headless), so the built-in
        # CHECKMARK stays the fallback rather than the row losing its icon.
        icon_value = validation_ok_icon_value()
        if icon_value:
            box.label(text="All good!", icon_value=icon_value)
        else:
            box.label(text="All good!", icon="CHECKMARK")
        return
    for level, message in issues:
        row = box.row()
        # Only a hard error paints the row red; a warning would make a template
        # that exports perfectly well look broken.
        row.alert = level == LEVEL_ERROR
        row.label(text=message, icon=VALIDATION_ICONS.get(level, "INFO"))


def _draw_source_panel(layout, state) -> None:
    """Column 3: available sources, then validation. Reference, not controls."""
    column = layout.column()
    if not bool(getattr(state, "loaded", False)):
        return

    header = column.column(align=True)
    header.label(text="Available Sources", icon="TEXTURE")
    hint = header.row()
    hint.active = False
    hint.label(text="Assign from an output's slot")

    listing = column.box().column(align=True)
    _draw_available_sources(listing, used_source_keys(state))

    column.separator(factor=0.5)
    _draw_validation(column, state)


def draw_export_templates(layout, context) -> None:
    """Entry point used by ``preferences.MasterBakerPreferences._draw_export_templates``."""
    state = editor_state(context)
    if state is None:
        layout.label(text="Template editor state is unavailable", icon="ERROR")
        return

    split = layout.split(factor=COLUMN_LIST_FACTOR)
    _draw_template_list(split.column(), state)
    # Fixed widths: the source panel is always populated now (SP-style legend),
    # so there is no idle state to collapse it for.
    rest = split.split(factor=COLUMN_EDITOR_FACTOR)
    _draw_preset_editor(rest.column(), state)
    _draw_source_panel(rest.column(), state)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

CLASSES = (
    MASTER_BAKER_PG_template_editor_channel,
    MASTER_BAKER_PG_template_editor_output,
    # The mirror's item type must register before the state that points a
    # CollectionProperty at it, or the state's registration fails outright.
    MASTER_BAKER_PG_template_editor_item,
    MASTER_BAKER_PG_template_editor_state,
    MASTER_BAKER_UL_output_templates,
    MASTER_BAKER_OT_template_editor_select,
    MASTER_BAKER_OT_template_editor_new,
    MASTER_BAKER_OT_template_editor_duplicate,
    MASTER_BAKER_OT_template_editor_delete,
    MASTER_BAKER_OT_template_editor_add_output,
    MASTER_BAKER_OT_template_editor_remove_output,
    MASTER_BAKER_OT_template_editor_duplicate_output,
    MASTER_BAKER_OT_template_editor_move_output,
    MASTER_BAKER_OT_template_editor_set_active_output,
    MASTER_BAKER_OT_template_editor_assign_source,
    MASTER_BAKER_OT_template_editor_set_channel_read,
    MASTER_BAKER_OT_template_editor_channel_options,
    MASTER_BAKER_OT_template_editor_toggle_invert,
    MASTER_BAKER_OT_template_editor_toggle_alpha,
    MASTER_BAKER_OT_template_editor_token_popover,
    MASTER_BAKER_OT_template_editor_insert_token,
    MASTER_BAKER_OT_template_editor_import,
    MASTER_BAKER_OT_template_editor_export,
    MASTER_BAKER_OT_open_template_editor,
)


def register():
    from .registration import safe_register_class

    for cls in CLASSES:
        safe_register_class(cls)
    bpy.types.WindowManager.master_baker_template_editor = bpy.props.PointerProperty(
        type=MASTER_BAKER_PG_template_editor_state
    )
    # Rebuilt from scratch on every enable: a preview collection that outlived a
    # disable/enable cycle would hand out icon ids into freed memory, which draws
    # as garbled chips rather than as nothing.
    _register_swatches()
    # First fill of the UIList mirror. draw() may only *detect* drift, so the
    # list would otherwise stay empty until something happened to write it.
    try:
        refresh_template_items()
    except Exception:
        pass


def unregister():
    global _REFRESH_SCHEDULED

    from .registration import safe_remove_attr, safe_unregister_class

    # A pending one-shot refresh would fire into a torn-down state; it no-ops
    # there, but the flag must not survive into the next enable or the first
    # drift after a reload would never schedule anything.
    _REFRESH_SCHEDULED = False
    _unregister_swatches()
    safe_remove_attr(bpy.types.WindowManager, "master_baker_template_editor")
    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
