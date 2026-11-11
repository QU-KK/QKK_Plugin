"""Filename token engine for the texture export dialog.

Substance-Painter-style tokens (``$name`` with an optional ``$(name)`` form for
disambiguation) expand against a per-(texture set x output x tile) context. See
``docs/archive/TEXTURE_EXPORT_DIALOG_PLAN.md`` section D3.

Two rules matter and are easy to get wrong:

1. **Only token values are sanitised.** Literal separators typed into the
   template (``_``, ``.``, ``-``, ``/`` for subfolders) survive verbatim;
   ``naming.sanitize_token`` runs on each expanded value so a texture set named
   ``Body Paint`` becomes ``Body_Paint`` without eating the author's own
   punctuation.
2. **An empty token takes one adjacent separator with it.** A token with no
   value in the context (an untiled bake's ``$udim``, or an unknown token)
   expands to ``""`` *and* swallows one neighbouring separator -- the preceding
   one when there is one, otherwise the following one. This is what makes the
   canonical ``$textureSet_$udim`` collapse to ``Body_Normal`` instead of
   ``Body_Normal.`` for a single-tile bake, mirroring how
   ``naming.build_output_stem`` appends ``.1001`` as the last dot segment only
   when a tile exists.

This module is import-safe outside Blender: it touches ``bpy`` nowhere.
"""

from __future__ import annotations

from . import naming


TOKEN_PROJECT = "project"
TOKEN_TEXTURE_SET = "textureSet"
TOKEN_UDIM = "udim"
TOKEN_UV_TILE_NAME = "uvTileName"
TOKEN_MESH = "mesh"
TOKEN_COLOR_SPACE = "colorSpace"
TOKEN_RESOLUTION = "resolution"
TOKEN_BIT_DEPTH = "bitDepth"
TOKEN_FORMAT = "format"
TOKEN_BLEND_NAME = "blendName"

# Order is the order the "$" insert menu should offer them in.
TOKEN_ITEMS: tuple[tuple[str, str], ...] = (
    (TOKEN_TEXTURE_SET, "Texture set name"),
    (TOKEN_MESH, "Low-poly mesh name this texture set bakes"),
    (TOKEN_PROJECT, "Bake project name"),
    (TOKEN_UDIM, "UDIM tile number, e.g. 1001 (collapses when the bake has no tiles)"),
    (TOKEN_UV_TILE_NAME, "UDIM tile in u/v form, e.g. u1_v1 (collapses when untiled)"),
    (TOKEN_COLOR_SPACE, "Color space of this output, sRGB or Linear"),
    (TOKEN_RESOLUTION, "Output resolution, e.g. 2048 or 2048x1024"),
    (TOKEN_BIT_DEPTH, "Bit depth of this output, e.g. 8 or 16"),
    (TOKEN_FORMAT, "Image format identifier of this output, e.g. PNG"),
    (TOKEN_BLEND_NAME, "Name of the .blend file, without extension"),
)

KNOWN_TOKENS: tuple[str, ...] = tuple(name for name, _description in TOKEN_ITEMS)

# Longest first so a shorter token can never claim the prefix of a longer one.
_MATCH_ORDER: tuple[str, ...] = tuple(sorted(KNOWN_TOKENS, key=len, reverse=True))
_LOWER_TO_CANONICAL = {name.lower(): name for name in KNOWN_TOKENS}

# Characters an empty token is allowed to absorb one of.
SEPARATORS = "_-. "

_LITERAL = "literal"
_TOKEN = "token"


def _is_identifier_char(char: str) -> bool:
    """Characters a bare ``$token`` name may contain.

    Alphanumerics only -- deliberately *not* ``_``. Underscore is the primary
    separator in every filename convention we ship, so ``T_$textureSet_$udim``
    has to end the token at the underscore rather than reading
    ``textureSet_`` as one name. Use the ``$(name)`` form for anything exotic.
    """
    return char.isalnum()


def _match_known_token(template: str, start: int) -> str | None:
    """Longest known token name matching at ``start``, case-insensitively."""
    tail = template[start:]
    lowered = tail.lower()
    for name in _MATCH_ORDER:
        if not lowered.startswith(name.lower()):
            continue
        end = start + len(name)
        # "$mapping" must not resolve to $mesh + "ping" (or any other prefix);
        # only accept a known token when the next character cannot continue an
        # identifier.
        if end < len(template) and _is_identifier_char(template[end]):
            continue
        return name
    return None


def parse_template(template: str) -> list[tuple[str, str]]:
    """Split ``template`` into ``("literal", text)`` / ``("token", name)`` parts.

    ``$$`` is an escaped literal dollar. ``$(name)`` is the explicit form and may
    contain any character except ``)``. A bare ``$`` followed by neither is kept
    as a literal dollar rather than raising -- the dialog shows a preview while
    the user is still typing.
    """
    text = str(template or "")
    parts: list[tuple[str, str]] = []
    literal: list[str] = []
    index = 0
    length = len(text)

    def flush_literal() -> None:
        if literal:
            parts.append((_LITERAL, "".join(literal)))
            literal.clear()

    while index < length:
        char = text[index]
        if char != "$":
            literal.append(char)
            index += 1
            continue

        if index + 1 < length and text[index + 1] == "$":
            literal.append("$")
            index += 2
            continue

        if index + 1 < length and text[index + 1] == "(":
            closing = text.find(")", index + 2)
            if closing != -1:
                flush_literal()
                parts.append((_TOKEN, text[index + 2:closing].strip()))
                index = closing + 1
                continue

        known = _match_known_token(text, index + 1)
        if known is not None:
            flush_literal()
            parts.append((_TOKEN, known))
            index += 1 + len(known)
            continue

        cursor = index + 1
        while cursor < length and _is_identifier_char(text[cursor]):
            cursor += 1
        if cursor == index + 1:
            # Lone "$" (or "$" before punctuation) -- treat it as a literal.
            literal.append("$")
            index += 1
            continue
        flush_literal()
        parts.append((_TOKEN, text[index + 1:cursor]))
        index = cursor

    flush_literal()
    return parts


def canonical_token_name(name: str) -> str | None:
    """Canonical spelling of ``name`` if it is a known token, else ``None``."""
    return _LOWER_TO_CANONICAL.get(str(name or "").strip().lower())


def find_tokens(template: str) -> list[str]:
    """Every token used by ``template``, in first-use order, deduplicated."""
    seen: list[str] = []
    for kind, value in parse_template(template):
        if kind != _TOKEN:
            continue
        canonical = canonical_token_name(value) or value
        if canonical not in seen:
            seen.append(canonical)
    return seen


def find_unknown_tokens(template: str) -> list[str]:
    """Token names the engine does not recognise, for the dialog's warning rows.

    Unknown tokens are not an error: they expand to ``""`` (and collapse an
    adjacent separator) so an export never dies on a typo, but the dialog must
    be able to flag the row red.
    """
    return [name for name in find_tokens(template) if canonical_token_name(name) is None]


def _token_value(name: str, context: dict) -> str:
    canonical = canonical_token_name(name)
    if canonical is None:
        return ""
    raw = context.get(canonical)
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    # sanitize_token substitutes "Untitled" for an empty result, so it is only
    # ever called on values we already know are non-empty.
    return naming.sanitize_token(text)


def _absorb_trailing_separator(chunks: list[str]) -> bool:
    """Drop one trailing separator from the emitted text. True when one was found."""
    for position in range(len(chunks) - 1, -1, -1):
        chunk = chunks[position]
        if not chunk:
            continue
        if chunk[-1] in SEPARATORS:
            chunks[position] = chunk[:-1]
            return True
        return False
    return False


def expand_template(template: str, context: dict) -> str:
    """Expand ``template`` against ``context`` (keyed by canonical token name).

    Missing keys, ``None`` values and unknown tokens all expand to ``""`` and
    collapse one adjacent separator; see the module docstring.
    """
    chunks: list[str] = []
    skip_leading_separator = False

    for kind, value in parse_template(template):
        if kind == _LITERAL:
            text = value
            if skip_leading_separator and text and text[0] in SEPARATORS:
                text = text[1:]
            skip_leading_separator = False
            chunks.append(text)
            continue

        expanded = _token_value(value, context)
        if expanded:
            chunks.append(expanded)
            skip_leading_separator = False
            continue

        # Empty token: eat the separator behind it, or else the one in front.
        skip_leading_separator = not _absorb_trailing_separator(chunks)

    return "".join(chunks)


def uv_tile_name(udim_tile: str | int | None) -> str:
    """``1001`` -> ``u1_v1``: Substance Painter's ``$uvTileName`` spelling.

    UDIM numbering is ``1001 + (u - 1) + (v - 1) * 10`` with ten columns per row,
    so this is the exact inverse of ``naming.udim_tile_from_coords``. Anything
    that is not a usable tile expands to ``""`` (and the token collapses).
    """
    normalized = naming.normalize_udim_tile(udim_tile)
    if not normalized:
        return ""
    try:
        offset = int(normalized) - 1001
    except (TypeError, ValueError):  # pragma: no cover - normalize_udim_tile guards
        return ""
    if offset < 0:
        return ""
    return f"u{offset % 10 + 1}_v{offset // 10 + 1}"


def build_export_context(
    project_name: str = "",
    texture_set_name: str = "",
    udim_tile: str | int | None = None,
    resolution_x: int | None = None,
    resolution_y: int | None = None,
    bit_depth: str | int | None = None,
    image_format: str = "",
    blend_name: str = "",
    mesh_name: str = "",
    color_space: str = "",
) -> dict[str, str]:
    """Assemble an expansion context from plain values (no bpy types).

    ``udim_tile`` goes through ``naming.normalize_udim_tile``, so a malformed
    tile raises ``naming.InvalidUdimTileError`` here at preflight instead of
    silently producing an untiled name that overwrites another tile.
    """
    udim_token = naming.normalize_udim_tile(udim_tile)

    if resolution_x and resolution_y:
        resolution = str(int(resolution_x)) if int(resolution_x) == int(resolution_y) else f"{int(resolution_x)}x{int(resolution_y)}"
    elif resolution_x:
        resolution = str(int(resolution_x))
    elif resolution_y:
        resolution = str(int(resolution_y))
    else:
        resolution = ""

    # sRGB / Linear, spelled the way Substance Painter writes them into filenames.
    space = str(color_space or "").strip().upper()
    if space in ("SRGB",):
        space_token = "sRGB"
    elif space in ("LINEAR", "NON_COLOR", "NONCOLOR", "DATA"):
        space_token = "Linear"
    else:
        space_token = ""

    return {
        TOKEN_PROJECT: str(project_name or ""),
        TOKEN_TEXTURE_SET: str(texture_set_name or ""),
        TOKEN_MESH: str(mesh_name or ""),
        TOKEN_UDIM: udim_token or "",
        TOKEN_UV_TILE_NAME: uv_tile_name(udim_token),
        TOKEN_COLOR_SPACE: space_token,
        TOKEN_RESOLUTION: resolution,
        TOKEN_BIT_DEPTH: "" if bit_depth is None else str(bit_depth),
        TOKEN_FORMAT: str(image_format or "").strip().upper(),
        TOKEN_BLEND_NAME: str(blend_name or ""),
    }
