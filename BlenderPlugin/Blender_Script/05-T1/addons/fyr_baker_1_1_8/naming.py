from __future__ import annotations

import contextlib
import re

from . import constants

_NON_ALNUM = re.compile(r"[^A-Za-z0-9_]+")
_MULTI_UNDERSCORE = re.compile(r"_+")


#: Substance Painter's "_ignorebf" suffix: in Substance the AO rays ignore that mesh's
#: backfaces, which Fyr's AO (Ignore Backface, the default) already does for every mesh. So it
#: does not change the bake; matching strips it so Box_high_ignorebf still pairs with Box_low.
#: It is NOT Casts AO off: that cut a relief decal's halo off at its plate edge (a square).
#: A whole token anywhere in the name: Box_high_ignorebf, Box_ignorebf_high, ..._ignorebf.001.
_IGNOREBF_TOKEN_RE = re.compile(r"(^|[._\-\s])ignorebf(?=$|[._\-\s])", re.IGNORECASE)


def has_ignorebf_marker(name: str) -> bool:
    return _IGNOREBF_TOKEN_RE.search(str(name or "")) is not None


def strip_ignorebf_marker(name: str) -> str:
    """The name without its _ignorebf token, so role detection and pairing see Box_high."""
    text = str(name or "")
    if not has_ignorebf_marker(text):
        return text
    return _IGNOREBF_TOKEN_RE.sub("", text).lstrip("._- ")


def sanitize_token(value: str) -> str:
    cleaned = _NON_ALNUM.sub("_", (value or "").strip())
    cleaned = _MULTI_UNDERSCORE.sub("_", cleaned).strip("_")
    return cleaned or "Untitled"


_MAP_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*\b")


def relabel_attribute_progress(message: str, attribute_suffixes) -> str:
    """Name Attribute rows as such in backend progress text.

    The backend bakes an Attribute row as its VERTEX_COLOR map and labels it
    "VERTEX_COLOR (<output suffix>)"; an Attribute row's suffix is its attribute
    name, so a suffix belonging to one of the project's Attribute rows identifies it.
    """
    text = str(message or "")
    suffixes = {str(s) for s in (attribute_suffixes or ()) if str(s or "").strip()}
    if not text or not suffixes or constants.MAP_VERTEX_COLOR not in text:
        return text

    def _replace(match: "re.Match[str]") -> str:
        if match.group(1) in suffixes:
            return f"{constants.MAP_ATTRIBUTE} ({match.group(1)})"
        return match.group(0)

    return re.sub(r"\bVERTEX_COLOR \(([^)]*)\)", _replace, text)


def project_attribute_suffixes(project) -> set[str]:
    """Output suffixes of the project's enabled Attribute rows (their attribute names)."""
    suffixes: set[str] = set()
    for item in getattr(project, "maps", None) or ():
        if str(getattr(item, "map_type", "") or "").strip().upper() != constants.MAP_ATTRIBUTE:
            continue
        if not bool(getattr(item, "enabled", True)):
            continue
        suffix = effective_map_output_suffix(project, item)
        if suffix:
            suffixes.add(suffix)
    return suffixes


def humanize_map_tokens(message: str) -> str:
    """Replace every raw map identifier in a progress message with its display label.

    The backend names maps by their enum identity and joins multi-map stages with
    commas, so status text reached the artist as
    ``"Shading Skull / Normal,CURVATURE,THICKNESS,BENT_NORMAL"`` -- the first token
    humanised (the caller used to fix only the active map) and the rest raw, underscores
    and all, with no space after the commas. Longest-token-first matching matters:
    replacing ``NORMAL`` before ``BENT_NORMAL`` would corrupt the longer name.
    """
    text = str(message or "")
    if not text:
        return text

    def _is_map_token(token: str) -> bool:
        # Only identifiers the addon knows as map types. map_label() title-cases
        # anything else, which turned GPU, CPU, OIDN, DXGI_ERROR_DEVICE_HUNG and
        # all-caps object names into "Gpu" / "Dxgi_Error_Device_Hung" in the very
        # status line an artist copies into a support report.
        if token in constants.MAP_LABELS:
            return True
        base = constants.base_map_type(token)
        return bool(base) and base in constants.MAP_LABELS and base != token

    def _replace(match: "re.Match[str]") -> str:
        token = match.group(0)
        if not _is_map_token(token):
            return token
        label = map_label(token)
        return label if label and label != token else token

    text = _MAP_TOKEN_RE.sub(_replace, text)

    # The backend joins map lists with a bare comma; give those room to breathe,
    # but only when a map identifier follows so paths and numbers stay intact.
    def _space_after_comma(match: "re.Match[str]") -> str:
        following = match.group(1)
        if _is_map_token(following) or following in constants.MAP_LABELS.values():
            return ", " + following
        return match.group(0)

    label_alternatives = "|".join(re.escape(label) for label in sorted(constants.MAP_LABELS.values(), key=len, reverse=True))
    text = re.sub(r",((?:[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*)|(?:" + label_alternatives + r"))\b", _space_after_comma, text)
    return text


def map_label(map_type: str) -> str:
    known = constants.MAP_LABELS.get(map_type)
    if known is not None:
        return known
    # Duplicated rows reach progress messages as "TYPE_SUFFIX" (the backend's per-row
    # identity), which titled straight through as "Ao_Ao" / "Ao_Raycast". Resolve the base
    # type and show the variant readably -- and drop the variant entirely when it just
    # repeats the base, which is what the FIRST row of a type now resolves to.
    normalized = str(map_type or "").strip().upper()
    if "_" in normalized:
        for split_at in range(len(normalized) - 1, 0, -1):
            if normalized[split_at] != "_":
                continue
            base, variant = normalized[:split_at], normalized[split_at + 1:]
            base_label = constants.MAP_LABELS.get(base)
            if base_label is None or not variant:
                continue
            if variant in {base, str(constants.MAP_FILE_LABELS.get(base, "")).upper()}:
                return base_label
            return f"{base_label} ({variant.replace('_', ' ').title()})"
    return sanitize_token(map_type.title())


def map_file_label(map_type: str) -> str:
    return constants.MAP_FILE_LABELS.get(map_type, sanitize_token(map_type.title()))


def resolved_map_label(map_type: str, map_label_override: str | None = None) -> str:
    override = sanitize_token(map_label_override or "") if map_label_override else ""
    if override:
        return override
    return map_label(map_type)


def resolved_map_file_label(map_type: str, map_label_override: str | None = None) -> str:
    override = sanitize_token(map_label_override or "") if map_label_override else ""
    if override:
        return override
    return map_file_label(map_type)


def output_display_label(
    group_name: str,
    map_type: str,
    texture_set_name: str | None = None,
    map_label_override: str | None = None,
    project_name: str | None = None,
) -> str:
    texture_set_token = normalize_texture_set_name(group_name, texture_set_name, project_name)
    base = map_label(map_type)
    if map_label_override:
        label = f"{base} [{sanitize_token(map_label_override)}]"
    else:
        label = base
    return f"{texture_set_token} - {label}"


def output_extension_for_image_format(image_format: str) -> str:
    normalized = str(image_format or constants.DEFAULT_IMAGE_FORMAT).strip().upper()
    if normalized == constants.IMAGE_FORMAT_TGA:
        return ".tga"
    if normalized == constants.IMAGE_FORMAT_PNG:
        return ".png"
    if normalized == constants.IMAGE_FORMAT_EXR:
        return ".exr"
    if normalized == constants.IMAGE_FORMAT_TIFF:
        return ".tiff"
    if normalized == constants.IMAGE_FORMAT_DDS:
        return ".dds"
    raise ValueError(f"Unsupported image format: {image_format}")


def _optional_suffix_tokens(*values: str | None) -> list[str]:
    tokens: list[str] = []
    for value in values:
        if value is None:
            continue
        token = sanitize_token(value)
        if token:
            tokens.append(token)
    return tokens


def normalize_texture_set_name(
    group_name: str,
    texture_set_name: str | None = None,
    project_name: str | None = None,
) -> str:
    """The output stem's leading token, resolved by a fixed precedence.

    ``explicit texture-set name > bake group name > project name``. A bake group only
    carries a texture-set name when the artist actually put it in one (the property
    default is empty), so a standalone group named ``Pottery`` writes ``Pottery_Normal.*``
    rather than a generic placeholder. The project name is the last resort for the
    degenerate case of an unnamed group, and ``sanitize_token`` still guarantees a usable
    token ("Untitled") when every source is empty.
    """
    return sanitize_token(texture_set_name or group_name or project_name)


class InvalidUdimTileError(ValueError):
    """A UDIM tile number was supplied but is not a usable tile.

    Raised rather than silently ignored: a mistyped or out-of-range tile must surface at
    preflight, never fall through to an untiled filename that quietly overwrites another
    tile's output.
    """


def normalize_udim_tile(udim_tile: str | int | None = None) -> str | None:
    """Return the canonical tile token, or ``None`` for "this output has no tile".

    ``None`` in means ``None`` out -- that is the ordinary single-tile case. Anything else
    must be a valid tile in ``[UDIM_TILE_MIN, UDIM_TILE_MAX]`` or this raises.
    """
    if udim_tile is None:
        return None

    # bool is an int subclass; True would otherwise normalize to a nonsense tile.
    if isinstance(udim_tile, bool):
        raise InvalidUdimTileError(f"UDIM tile must be a number, got {udim_tile!r}")

    if isinstance(udim_tile, int):
        value = udim_tile
    else:
        token = sanitize_token(str(udim_tile))
        if not token or not token.isdigit():
            raise InvalidUdimTileError(f"UDIM tile must be a number, got {udim_tile!r}")
        value = int(token)

    if value < constants.UDIM_TILE_MIN or value > constants.UDIM_TILE_MAX:
        raise InvalidUdimTileError(
            f"UDIM tile {value} is outside the supported range "
            f"{constants.UDIM_TILE_MIN}-{constants.UDIM_TILE_MAX}"
        )
    return str(value)


def udim_tile_from_coords(tile_u: int, tile_v: int) -> int:
    """``1001 + tile_u + 10 * tile_v`` -- the standard UDIM numbering."""
    if tile_u < 0 or tile_u > 9:
        raise InvalidUdimTileError(
            f"UDIM column must be 0-9 (ten-column convention), got tile_u={tile_u}"
        )
    if tile_v < 0:
        raise InvalidUdimTileError(f"UDIM row must be >= 0, got tile_v={tile_v}")
    return constants.UDIM_TILE_MIN + tile_u + 10 * tile_v


def udim_tile_to_coords(udim_tile: str | int) -> tuple[int, int]:
    """Inverse of :func:`udim_tile_from_coords`. Returns ``(tile_u, tile_v)``."""
    token = normalize_udim_tile(udim_tile)
    if token is None:
        raise InvalidUdimTileError("UDIM tile is required")
    offset = int(token) - constants.UDIM_TILE_MIN
    return offset % 10, offset // 10


def split_udim_tile_suffix(stem: str) -> tuple[str, str | None]:
    """Split a trailing ``.1001`` tile suffix off a filename stem.

    ``"Asset_Normal.1001"`` -> ``("Asset_Normal", "1001")``; a stem with no tile suffix comes
    back unchanged with ``None``. Needed because ``pathlib.Path("a.1001.png").stem`` keeps the
    tile, so any comparison against an untiled stem would never match.
    """
    base, separator, candidate = stem.rpartition(".")
    if not separator or not candidate.isdigit():
        return stem, None
    try:
        token = normalize_udim_tile(candidate)
    except InvalidUdimTileError:
        return stem, None
    return base, token


def build_output_stem(
    group_name: str,
    map_type: str,
    texture_set_name: str | None = None,
    udim_tile: str | int | None = None,
    map_label_override: str | None = None,
    project_name: str | None = None,
) -> str:
    """Build the filename stem, with the tile as a trailing ``.NNNN`` segment.

    Ordering is ``TextureSet_Map.1001``, not ``TextureSet_1001_Map``: the tile must be the
    last dot-separated segment before the extension for UDIM-aware consumers (Blender's
    ``<UDIM>`` token, Arnold, V-Ray) to recognise the sequence at all.

    The leading token follows :func:`normalize_texture_set_name`'s precedence
    (texture set > bake group > project).
    """
    texture_set_token = normalize_texture_set_name(group_name, texture_set_name, project_name)
    stem_tokens = [texture_set_token]
    stem_tokens.append(sanitize_token(resolved_map_file_label(map_type, map_label_override)))

    stem = "_".join(stem_tokens)

    udim_token = normalize_udim_tile(udim_tile)
    if udim_token is not None:
        stem = f"{stem}.{udim_token}"
    return stem


def build_output_file_name(
    group_name: str,
    map_type: str,
    bit_depth: str,
    image_format: str = constants.DEFAULT_IMAGE_FORMAT,
    texture_set_name: str | None = None,
    udim_tile: str | int | None = None,
    map_label_override: str | None = None,
    project_name: str | None = None,
) -> str:
    _ = bit_depth
    return (
        f"{build_output_stem(group_name, map_type, texture_set_name=texture_set_name, udim_tile=udim_tile, map_label_override=map_label_override, project_name=project_name)}"
        f"{output_extension_for_image_format(image_format)}"
    )


# --- Effective output suffix ----------------------------------------------------
# A map row's suffix is not simply its ``output_suffix`` field: same-type rows with no
# explicit suffix are auto-discriminated so each still writes its own file. The
# resolution lives here, beside build_output_file_name, because the exporter (through
# properties, which re-exports these) and the bpy-free preflight validator must arrive
# at exactly the same file names -- resolving the raw field in the validator reported
# collisions that the bake never had. Everything below reads plain attributes, so it
# works on a Blender PropertyGroup and on a plain object alike.


def map_output_suffix(map_setting) -> str | None:
    raw_suffix = (getattr(map_setting, "output_suffix", "") or "").strip()
    return raw_suffix or None


def _iter_same_type_maps(project, map_type: str):
    normalized_map_type = str(map_type or "").strip().upper()
    for item in getattr(project, "maps", []):
        if getattr(item, "is_add_phantom", False):
            continue
        if str(getattr(item, "map_type", "") or "").strip().upper() != normalized_map_type:
            continue
        yield item


def normal_row_is_derivative(map_setting) -> bool:
    """A tangent Normal row whose Output is Derivative (see constants.MAP_DERIVATIVE).

    Only tangent space has slopes to write; an Object/World row ignores the setting.
    """
    if str(getattr(map_setting, "map_type", "") or "").strip().upper() != constants.MAP_NORMAL:
        return False
    if str(getattr(map_setting, "normal_encoding", "") or "").strip().upper() != constants.NORMAL_ENCODING_DERIVATIVE:
        return False
    space = str(getattr(map_setting, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT) or "").strip().upper()
    return space in {"", constants.MAP_NORMAL_SPACE_TANGENT}


def effective_map_type_for_setting(map_setting) -> str:
    """Return the effective map_type for output tracking, translating sub-type modes.

    Curvature variants (Signed/Principal/Direction) share raw type ``CURVATURE`` in the
    stack but the backend receives distinct types per mode. Material maps share raw type
    ``MATERIAL`` in the stack but are tracked per-channel. This centralises both
    translations so output-tracking code can match produced files back to map settings.
    Lives here (bpy-free) so validation resolves file names exactly like export does."""
    raw = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    if raw == constants.MAP_CURVATURE:
        mode = str(getattr(map_setting, "curvature_output_mode", "SIGNED") or "SIGNED").strip().upper()
        if mode == "PRINCIPAL":
            return constants.MAP_PRINCIPAL_CURVATURE
        if mode == "DIRECTION":
            return constants.MAP_CURVATURE_DIRECTION
    if raw == constants.MAP_MATERIAL:
        origin = str(getattr(map_setting, "material_origin", "") or "")
        if origin == constants.MATERIAL_ORIGIN_CUSTOM:
            return constants.MAP_MATERIAL_CUSTOM
        channel = str(getattr(map_setting, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO) or "").strip().upper()
        return constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.get(channel, constants.MAP_MATERIAL_ALBEDO)
    if raw == constants.MAP_SCENE_LIGHTING:
        # Consolidated scene-lighting row: the backend/wire map_type is the chosen
        # output (LIGHTING or LIT_COLOR), never SCENE_LIGHTING itself.
        return constants.effective_lighting_map_type(map_setting) or constants.MAP_LIGHTING
    if normal_row_is_derivative(map_setting):
        return constants.MAP_DERIVATIVE
    return str(getattr(map_setting, "map_type", "") or "").strip()


def _material_row_identity(map_setting) -> tuple:
    """The set of MATERIAL rows a row must be disambiguated against.

    Rows with different identities already write distinct files through their
    effective map types' file labels, so only rows sharing one identity need the
    auto-suffix discrimination below. That holds per channel -- an Albedo and a
    Roughness row resolve to MATERIAL_ALBEDO/MATERIAL_ROUGHNESS, whose labels
    differ -- but NOT per custom output: every custom row resolves to
    MATERIAL_CUSTOM, whose file label is the constant "Custom". Keying custom rows
    by name therefore split "Wear" and "Scratches" into sets of one, both resolved
    to no suffix, both wrote <set>_Custom.png, and the bake was hard-blocked by the
    duplicate-output check until the artist typed suffixes by hand. All
    CUSTOM-origin rows are one set, so ``map_mode_label``'s custom-name path gives
    each of them its own label."""
    origin = str(getattr(map_setting, "material_origin", "") or constants.MATERIAL_ORIGIN_MANUAL).strip().upper()
    if origin == constants.MATERIAL_ORIGIN_CUSTOM:
        return ("CUSTOM",)
    return ("CHANNEL", str(getattr(map_setting, "material_channel", "") or "").strip().upper())


def _base_output_file_label(map_type: str, first_map_setting) -> str:
    """The file label a row of ``map_type`` writes when it carries NO suffix override.

    For most types that is simply the type's file label. MATERIAL and SCENE_LIGHTING rows
    resolve their file name through the effective type instead (Albedo, Roughness, Lit
    Color, ...), and ``map_mode_label`` already returns exactly that label for them.
    """
    normalized = str(map_type or "").strip().upper()
    if normalized == constants.MAP_NORMAL and normal_row_is_derivative(first_map_setting):
        return constants.MAP_FILE_LABELS[constants.MAP_DERIVATIVE]
    if normalized in {constants.MAP_MATERIAL, constants.MAP_SCENE_LIGHTING}:
        resolved = map_mode_label(first_map_setting)
        if resolved:
            return resolved
    return constants.MAP_FILE_LABELS.get(normalized, map_label(normalized))


def _auto_map_output_suffix_base(map_setting) -> str:
    base_label = map_mode_label(map_setting)
    if base_label:
        return base_label
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    return constants.MAP_LABELS.get(map_type, map_type.title().replace("_", " ")) or "Variant"


def _suffix_file_key(label: str) -> str:
    """The form of *label* that decides collisions: what it becomes in a file name.

    ``build_output_stem`` puts every suffix through ``sanitize_token``, and the
    duplicate-output check compares finished file names case-insensitively, so
    that is the only comparison that means anything here.
    """
    return sanitize_token(str(label or "")).casefold()


def _next_available_suffix(base_label: str, used_labels: set[str]) -> str:
    """The first variant of *base_label* whose FILE NAME is still free.

    ``used_labels`` holds the keys of the labels already claimed, in
    ``_suffix_file_key`` form. Comparing raw labels instead let an auto suffix
    land on a name another row already owned once sanitisation folded them
    together: a stack whose explicit suffix was "Mesh_Rays" happily auto-picked
    "Mesh Rays" for the next row, both wrote <set>_Mesh_Rays.png, and the bake
    was blocked by a duplicate-output-path error the artist could not see the
    cause of.
    """
    candidate = str(base_label or "Variant").strip() or "Variant"
    if _suffix_file_key(candidate) not in used_labels:
        return candidate
    suffix_index = 2
    while True:
        candidate_with_index = f"{candidate} {suffix_index}"
        if _suffix_file_key(candidate_with_index) not in used_labels:
            return candidate_with_index
        suffix_index += 1


def map_mode_label(map_setting) -> str | None:
    """Return a short label describing the map's active method/mode, used to auto-discriminate
    duplicate maps of the same type when no explicit output_suffix is set."""
    normalized_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    if normalized_type == constants.MAP_AO:
        mode = str(getattr(map_setting, "ao_mode", constants.MAP_AO_MODE_RAYCAST) or "").strip().upper()
        return "Diffusive" if mode == constants.MAP_AO_MODE_DIFFUSIVE_ESCAPE else "Raycast"
    if normalized_type == constants.MAP_CURVATURE:
        # Curvature maps primary discriminator is the output mode (Signed/Principal/Direction),
        # since those produce fundamentally different data. This must take priority over method so
        # that multiple curvature stacks of the same method don't collide on the same filename.
        output_mode = str(getattr(map_setting, "curvature_output_mode", "SIGNED") or "SIGNED").strip().upper()
        if output_mode == "PRINCIPAL":
            return "Principal"
        if output_mode == "DIRECTION":
            return "Direction"
        return "Signed"
    if normalized_type == constants.MAP_CAVITY:
        return "Hybrid"
    if normalized_type in {constants.MAP_CONCAVE, constants.MAP_CONVEX}:
        method = str(getattr(map_setting, "curvature_method", "NORMAL_DERIVATIVE") or "").strip().upper()
        if method == "NORMAL_DERIVATIVE":
            return "Normal Derivative"
        # Mesh Rays needs its own discriminator or a Geometric and a Mesh Rays Concave
        # row in the same stack would collide on one filename.
        if method == "MESH_RAYS":
            return "Mesh Rays"
        return "Geometric"
    if normal_row_is_derivative(map_setting):
        return "Derivative"
    if normalized_type in {constants.MAP_NORMAL, constants.MAP_BENT_NORMAL, constants.MAP_OBJECT_NORMAL, constants.MAP_WORLD_NORMAL}:
        space = str(getattr(map_setting, "normal_space", constants.MAP_NORMAL_SPACE_TANGENT) or "").strip().upper()
        if space == constants.MAP_NORMAL_SPACE_OBJECT:
            return "Object"
        if space == constants.MAP_NORMAL_SPACE_WORLD:
            return "World"
        return "Tangent"
    if normalized_type == constants.MAP_POSITION:
        mode = str(getattr(map_setting, "position_mode", "ABSOLUTE") or "").strip().upper()
        return "Relative" if mode == "RELATIVE" else "Absolute"
    if normalized_type == constants.MAP_MATERIAL:
        # Same rule as SCENE_LIGHTING below: the suffix REPLACES the map file label, so
        # discriminating rows must reuse the effective type's own file label. Otherwise
        # two channels auto-named "Material 2"/"Material 3" instead of Albedo/Roughness.
        if str(getattr(map_setting, "material_origin", "") or "").strip().upper() == constants.MATERIAL_ORIGIN_CUSTOM:
            custom_name = str(getattr(map_setting, "material_custom_name", "") or "").strip()
            if custom_name:
                return custom_name
            return constants.MAP_FILE_LABELS.get(constants.MAP_MATERIAL_CUSTOM, "Custom")
        channel = str(
            getattr(map_setting, "material_channel", constants.MATERIAL_CHANNEL_ALBEDO)
            or constants.MATERIAL_CHANNEL_ALBEDO
        ).strip().upper()
        effective_type = constants.MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.get(channel)
        if effective_type:
            return constants.MAP_FILE_LABELS.get(effective_type)
        return None
    if normalized_type == constants.MAP_SCENE_LIGHTING:
        # Only reached when two rows bake the SAME output (effective_map_output_suffix
        # filters by effective type first). Match the effective types' FILE labels so a
        # suffix never renames the base output file (naming treats the suffix as a
        # map-label override, not an append).
        output = str(getattr(map_setting, "lighting_output", constants.LIGHTING_OUTPUT_LIGHTING) or "").strip().upper()
        return constants.MAP_FILE_LABELS.get(
            constants.LIGHTING_OUTPUT_TO_EFFECTIVE_TYPE.get(output, constants.MAP_LIGHTING),
            "Lighting",
        )
    return None


def _attribute_row_output_suffix(project, map_setting) -> str | None:
    """An Attribute row's file is named after its attribute ("Body_wear"), not "Attribute".

    Rows baking the same attribute (say at two ranges) count up in stack order, with
    disabled rows skipped as everywhere else: "wear", "wear 2", ...
    """
    name = str(getattr(map_setting, "attribute_name", "") or "").strip()
    if not name:
        return None
    target_uuid = str(getattr(map_setting, "uuid", "") or "").strip()
    target_ptr = getattr(map_setting, "as_pointer", lambda: None)()
    position = 0
    for item in _iter_same_type_maps(project, constants.MAP_ATTRIBUTE):
        is_target = item is map_setting or (
            target_ptr is not None and getattr(item, "as_pointer", lambda: None)() == target_ptr
        ) or (bool(target_uuid) and str(getattr(item, "uuid", "") or "").strip() == target_uuid)
        if is_target:
            return name if position == 0 else f"{name} {position + 1}"
        if not bool(getattr(item, "enabled", True)):
            continue
        if str(getattr(item, "attribute_name", "") or "").strip() == name and not str(
            getattr(item, "output_suffix", "") or ""
        ).strip():
            position += 1
    return name


#: Active only inside output_suffix_memo(): {(project ptr, map ptr): suffix}.
_SUFFIX_MEMO: dict | None = None


@contextlib.contextmanager
def output_suffix_memo():
    """Memoise effective_map_output_suffix while the map stack cannot change.

    Applying bake progress resolves every output's suffix, and each resolution rescans
    the project's map list, so one progress poll was groups x maps x maps."""
    global _SUFFIX_MEMO
    if _SUFFIX_MEMO is not None:
        yield
        return
    _SUFFIX_MEMO = {}
    try:
        yield
    finally:
        _SUFFIX_MEMO = None


def _memo_pointer(value):
    as_pointer = getattr(value, "as_pointer", None)
    if as_pointer is None:
        return None
    try:
        return int(as_pointer())
    except Exception:
        return None


def effective_map_output_suffix(project, map_setting) -> str | None:
    memo = _SUFFIX_MEMO
    if memo is None:
        return _effective_map_output_suffix(project, map_setting)
    project_ptr = _memo_pointer(project)
    map_ptr = _memo_pointer(map_setting)
    if project_ptr is None or map_ptr is None:
        return _effective_map_output_suffix(project, map_setting)
    key = (project_ptr, map_ptr)
    if key not in memo:
        memo[key] = _effective_map_output_suffix(project, map_setting)
    return memo[key]


def _effective_map_output_suffix(project, map_setting) -> str | None:
    """Return the effective output suffix for a map setting.

    Returns the user-set suffix if non-empty.  When multiple maps share the same map_type in the
    stack and the user hasn't set a suffix, falls back to a deterministic auto-generated label so
    each map produces a distinct output file automatically."""
    user_suffix = (getattr(map_setting, "output_suffix", "") or "").strip()
    if user_suffix:
        return user_suffix
    if project is None:
        return None
    map_type = str(getattr(map_setting, "map_type", "") or "").strip().upper()
    if map_type == constants.MAP_ATTRIBUTE:
        attribute_suffix = _attribute_row_output_suffix(project, map_setting)
        if attribute_suffix:
            return attribute_suffix
    same_type_maps = list(_iter_same_type_maps(project, map_type))
    # Consolidated scene-lighting rows: two SCENE_LIGHTING rows baking DIFFERENT
    # outputs (Lighting vs Lit Color) already produce distinct files through their
    # effective map types' file labels — an auto-suffix would REPLACE those labels
    # and silently rename the outputs (BakeProject_LitColor -> BakeProject_Lit_Color).
    # Only rows sharing the same effective output need suffix discrimination.
    target_effective_lighting = constants.effective_lighting_map_type(map_setting)
    if target_effective_lighting is not None:
        same_type_maps = [
            item
            for item in same_type_maps
            if constants.effective_lighting_map_type(item) == target_effective_lighting
        ]
    # MATERIAL rows follow the same rule per channel: an Albedo and a Roughness row
    # already write distinct files through their effective types' file labels, so
    # only rows baking the SAME channel need a suffix. Custom-output rows all share
    # one file label ("Custom"), so they form a single set -- see
    # _material_row_identity.
    # A Derivative row and a Normal row write different files (their effective types'
    # file labels differ), so each only needs a suffix against rows of its own output.
    if map_type == constants.MAP_NORMAL:
        target_is_derivative = normal_row_is_derivative(map_setting)
        same_type_maps = [
            item for item in same_type_maps if normal_row_is_derivative(item) == target_is_derivative
        ]
    if map_type == constants.MAP_MATERIAL:
        target_material_identity = _material_row_identity(map_setting)
        same_type_maps = [
            item
            for item in same_type_maps
            if _material_row_identity(item) == target_material_identity
        ]
    # Identify map_setting within same_type_maps using multiple strategies so that
    # re-iteration of a Blender CollectionProperty (which may yield fresh Python wrappers
    # for the same C struct) and maps without UUIDs are all handled correctly.
    target_ptr = getattr(map_setting, "as_pointer", lambda: None)()
    target_uuid = str(getattr(map_setting, "uuid", "") or "").strip()

    def _is_target(item) -> bool:
        if item is map_setting:
            return True
        if target_ptr is not None:
            item_ptr = getattr(item, "as_pointer", lambda: None)()
            if item_ptr is not None and item_ptr == target_ptr:
                return True
        if target_uuid:
            return str(getattr(item, "uuid", "") or "").strip() == target_uuid
        return False

    # A disabled row writes no file, so it must not consume a label an enabled row
    # would otherwise get (the disabled catalogue Material row used to claim
    # "Albedo" and push the enabled row to "Albedo 2" with no Albedo file on disk).
    # The target itself always stays, so a disabled row's own UI label still resolves.
    # Missing attribute defaults to True: only a row that EXPLICITLY carries
    # enabled=False is excluded (plain mocks and partial records stay counted).
    same_type_maps = [
        item
        for item in same_type_maps
        if bool(getattr(item, "enabled", True)) or _is_target(item)
    ]
    if len(same_type_maps) <= 1:
        return None

    # The FIRST surviving row of a type keeps the plain map file label (no suffix
    # override). Auto-suffixing it too meant that ADDING a second row of the same type
    # silently renamed the output of the row the artist never touched -- duplicating an
    # AO row moved its file from "<set>_AO.tga" to "<set>_Raycast.tga", orphaning the old
    # file and breaking every downstream reference (Painter/engine links, prior exports).
    # Only the rows added on top get a discriminating label.
    base_file_label = _base_output_file_label(map_type, same_type_maps[0])

    # Keyed by the FILE NAME each label produces, not the label itself: two labels
    # that sanitise to the same token would otherwise both look free and the stack
    # would resolve to two rows writing one file.
    used_labels: set[str] = set()
    for index, item in enumerate(same_type_maps):
        is_target = _is_target(item)
        explicit_suffix = map_output_suffix(item)
        if explicit_suffix:
            used_labels.add(_suffix_file_key(explicit_suffix))
            if is_target:
                return explicit_suffix
            continue
        if index == 0:
            # Return the BASE label rather than None: the resulting file name is identical
            # either way (a None override falls back to exactly this label), but returning
            # it keeps the "disambiguating rows always resolve to a token" contract every
            # caller already relies on.
            used_labels.add(_suffix_file_key(base_file_label))
            if is_target:
                return base_file_label
            continue
        auto_suffix = _next_available_suffix(_auto_map_output_suffix_base(item), used_labels)
        if is_target:
            return auto_suffix
        used_labels.add(_suffix_file_key(auto_suffix))
    return None
