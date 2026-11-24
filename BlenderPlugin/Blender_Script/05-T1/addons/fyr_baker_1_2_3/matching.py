from __future__ import annotations

from collections.abc import Iterable, Mapping
import re
from typing import Any

from . import constants, naming, tagging

_BLENDER_DUP_SUFFIX_RE = re.compile(r"([._-])\d+$")
#: Trailing separators/whitespace left behind by a rename ("Barrel_low ", "Barrel_low_").
_TRAILING_NOISE_RE = re.compile(r"[\s._\-]+$")
_MULTI_SEPARATOR_RE = re.compile(r"[._\-\s]+")
#: A per-source index written straight onto the role suffix ("Barrel_high01").
_TRAILING_NUMBER_RE = re.compile(r"\d+$")
_COMMON_PREFIX_TOKENS = {"SM", "SK", "SKEL", "A", "SEQ", "HLP", "MESH", "OBJ"}


def normalize_name_for_role_detection(name: str) -> str:
    """Strip the noise that hides a role suffix from an exact ``endswith`` test.

    Role detection is anchored to the END of the object name, so anything trailing it
    hides the role and the mesh is skipped by the auto-build with no message at all --
    the object simply does not appear in any bake group. In practice that is trailing
    whitespace ("Barrel_low "), which survives a rename in the Outliner and arrives on
    objects imported from other DCCs, and stacked Blender duplicate suffixes
    ("Barrel_low.001.002"), which one pass of the duplicate-suffix regex cannot remove.
    """
    # The _ignorebf modifier (naming.has_ignorebf_marker) is not part of the role or the base
    # name: Box_high_ignorebf and Box_ignorebf_high are both Box's high.
    cleaned = naming.strip_ignorebf_marker(str(name or "").strip())
    while True:
        stripped = _BLENDER_DUP_SUFFIX_RE.sub("", cleaned)
        stripped = _TRAILING_NOISE_RE.sub("", stripped)
        if stripped == cleaned:
            return cleaned
        cleaned = stripped


def _ends_with_role_suffix(candidate: str) -> bool:
    lowered = candidate.lower()
    return any(
        lowered.endswith(suffix)
        for suffixes in constants.ROLE_SUFFIXES.values()
        for suffix in suffixes
    )


def strip_role_numbering(name: str) -> str:
    """Drop a per-source index that sits directly on the role suffix.

    "Barrel_high01" names the first of several high-poly sources for one pair --
    Marmoset reads the number after the suffix, and that is the convention the
    3ds Max layer workflow arrives with. The duplicate-suffix pass only removes
    digits behind a separator ("_high_01"), so the unseparated form kept reaching
    ``detect_role`` as an unsuffixed name and its mesh silently joined no group.

    Only strip when a role suffix is actually uncovered: "Chain02" is a whole name
    of its own and has to keep both its digits and its own bake group.
    """
    normalized = normalize_name_for_role_detection(name)
    candidate = _TRAILING_NUMBER_RE.sub("", normalized)
    if candidate != normalized:
        candidate = _TRAILING_NOISE_RE.sub("", candidate)
        if _ends_with_role_suffix(candidate):
            return candidate
    return strip_role_variant(normalized)


#: Role words as whole tokens, from the same vocabulary as ``constants.ROLE_SUFFIXES``.
_ROLE_WORDS = sorted(
    {suffix[1:] for suffixes in constants.ROLE_SUFFIXES.values() for suffix in suffixes},
    key=len,
    reverse=True,
)
#: A role word in the MIDDLE of a name, between a non-empty base and a variant tail.
_ROLE_VARIANT_RE = re.compile(
    r"(?<=[^._\-\s])[._\-\s](?:" + "|".join(re.escape(word) for word in _ROLE_WORDS) + r")(?=[._\-\s])",
    re.IGNORECASE,
)


def strip_role_variant(name: str) -> str:
    """Drop a variant tail written after the role word ("Box_high_bolt" -> "Box_high").

    Painter and Marmoset read everything before high/low as the bake group, the role
    word as the slot, and everything after it as a variation of that group's source:
    Myobject1_high, Myobject1_high_bolt and Myobject1_low are one group. Role detection
    here is anchored to the END of the name, so a tail behind the role word left the
    mesh unclassified and the auto-build dropped it without a message. A name that
    already ends in its role keeps it; otherwise the LAST role word followed by a tail
    wins, which never touches the base ("Low_Wall_high_trim" keeps "Low_Wall").
    """
    text = str(name or "")
    if _ends_with_role_suffix(text):
        return text
    last = None
    for last in _ROLE_VARIANT_RE.finditer(text):
        pass
    return text[: last.end()] if last is not None else text


def strip_role_suffix(name: str) -> str:
    normalized = strip_role_numbering(name)
    lowered = normalized.lower()
    for suffixes in constants.ROLE_SUFFIXES.values():
        for suffix in suffixes:
            if lowered.endswith(suffix):
                return normalized[: -len(suffix)]
    return normalized


#: Mirrors ``strip_role_suffix`` in backend/src/master_baker_backend.cpp, which is what Match By
#: Isolation actually pairs on at trace time. Derived from :data:`constants.ROLE_SUFFIXES` because
#: the backend's list is now that same set verbatim -- keeping one source of truth is what stops
#: the two drifting apart again (they had, and the _LP/_HP half of the convention could not
#: isolate at all as a result). ``tests/test_cage_coverage_cross_part.py`` asserts the parity.
#:
#: Still deliberately NOT :func:`strip_role_suffix` above: that one *also* normalizes Blender
#: duplicate suffixes and numbered roles. The backend does pair numbered highs ("Body_high_01") at
#: trace time, but as a family of sources; this one-high answer stays None for them, so the cage
#: is fitted against the whole group and can only come out longer, never short.
_BACKEND_ROLE_SUFFIXES = tuple(
    suffix for suffixes in constants.ROLE_SUFFIXES.values() for suffix in suffixes
)


def backend_strip_role_suffix(name: str) -> str:
    """Strip one role suffix exactly the way the backend does, or return the name unchanged."""
    text = naming.strip_ignorebf_marker(str(name or ""))
    lowered = text.lower()
    for suffix in _BACKEND_ROLE_SUFFIXES:
        if len(text) > len(suffix) and lowered.endswith(suffix):
            return text[: -len(suffix)]
    return text


def isolation_high_index_for_low(low_object_name: str, high_object_names) -> int | None:
    """Index of the one high mesh Match By Isolation pairs with ``low_object_name``.

    ``None`` when nothing matches or when several *distinct* high meshes do: the backend's
    ``find_isolation_source_name`` refuses to isolate ambiguously and falls back to tracing the
    whole group there, so nothing on the addon side may assume a pair either.
    """
    base = backend_strip_role_suffix(low_object_name)
    matched_index = None
    matched_name = None
    for index, name in enumerate(high_object_names):
        if not name or backend_strip_role_suffix(str(name)) != base:
            continue
        if matched_name is None:
            matched_index = index
            matched_name = str(name)
        elif matched_name != str(name):
            return None
    return matched_index


def normalize_group_name(name: str) -> str:
    # Naming model: <Group>_<Part>_<Role>. The GROUP is the name prefix — the first
    # meaningful token. Strip the role suffix and any Blender duplicate suffix, drop
    # leading boilerplate tokens (SM_, SK_, ...), then take the first remaining token.
    # The "part" tokens are intentionally dropped from the group name so every part of
    # one prefix shares a single bake group ("Teeth_Lower_LP" + "Teeth_Upper_HP" ->
    # "Teeth"); the meshes keep their full object names, so the part info isn't lost.
    cleaned = strip_role_suffix(name or "")
    tokens = [token for token in _MULTI_SEPARATOR_RE.split(cleaned) if token]
    while len(tokens) > 1 and tokens[0].upper() in _COMMON_PREFIX_TOKENS:
        tokens.pop(0)
    if not tokens:
        return "BakeGroup"
    return naming.sanitize_token(tokens[0])


def group_key_for_name(name: str) -> str:
    return normalize_group_name(name)


def detect_role(name: str) -> str | None:
    lowered = strip_role_numbering(name).lower()
    for role, suffixes in constants.ROLE_SUFFIXES.items():
        for suffix in suffixes:
            if lowered.endswith(suffix):
                return role
    return None


def _item_name(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        return str(item.get("name", ""))
    return str(getattr(item, "name", ""))


def _item_collections(item: Any) -> list[Any]:
    if isinstance(item, str):
        return []
    for attribute in ("collections", "users_collection", "collection_names"):
        value = getattr(item, attribute, None)
        if value:
            return list(value)
    if isinstance(item, Mapping):
        value = item.get("collections") or item.get("users_collection") or item.get("collection_names")
        if value:
            return list(value)
    return []


def _collection_name(collection: Any) -> str:
    if isinstance(collection, str):
        return collection
    if isinstance(collection, Mapping):
        return str(collection.get("name", ""))
    return str(getattr(collection, "name", ""))


def _tag_payload(target: Any) -> dict[str, str] | None:
    return tagging.read_role_tag(target)


def _collection_tag(collection: Any, collection_tags: Mapping[str, Any] | None) -> dict[str, str] | None:
    if collection_tags is not None:
        collection_name = _collection_name(collection)
        tag_source = collection_tags.get(collection_name)
        if tag_source is not None:
            return tagging.read_role_tag(tag_source)
    return tagging.read_role_tag(collection)


def _first(values: Iterable[str | None]) -> str | None:
    for value in values:
        if value:
            return value
    return None


def classify_bake_item(
    item: Any,
    collection_tags: Mapping[str, Any] | None = None,
    *,
    prefer_suffix: bool = False,
) -> dict[str, str | None]:
    """Resolve one mesh's (role, group), from its tags, its collection, or its name.

    ``prefer_suffix`` makes the mesh's OWN name the authority whenever it carries a
    role suffix, ignoring any group a tag or collection would otherwise impose. The
    suffix-driven auto-build passes it, and has to: a mesh already linked into some
    group's role collection was classified into THAT group by collection name even
    when its suffix plainly named another one, so "Auto-Build by Suffix" could not
    move a mesh out of a group it had been manually assigned to. Both 2026-08-19
    tester bundles are that bug -- group #1 held every mesh, and re-running the
    suffix build kept putting them back.
    """
    name = _item_name(item)
    object_tag = _tag_payload(item)
    collections = _item_collections(item)
    collection_tag = None
    collection_name = None
    for collection in collections:
        tag = _collection_tag(collection, collection_tags)
        if tag is None:
            continue
        collection_tag = tag
        collection_name = _collection_name(collection)
        break

    explicit_group = _first(
        [
            object_tag.get(tagging.GROUP_KEY) if object_tag else None,
            collection_tag.get(tagging.GROUP_KEY) if collection_tag else None,
        ]
    )
    explicit_role = _first(
        [
            object_tag.get(tagging.ROLE_KEY) if object_tag else None,
            collection_tag.get(tagging.ROLE_KEY) if collection_tag else None,
        ]
    )

    suffix_role = detect_role(name)

    if prefer_suffix and suffix_role is not None:
        return {
            "name": name,
            "role": suffix_role,
            "group_name": normalize_group_name(name),
            "source": "suffix",
            "collection_name": collection_name,
        }

    role = explicit_role or suffix_role
    group_name = explicit_group or normalize_group_name(name)

    if explicit_group is None and collection_name and collection_tag is not None and role is None:
        group_name = normalize_group_name(collection_name)
    elif explicit_group is None and collection_name and collection_tag is not None and suffix_role is not None:
        group_name = normalize_group_name(collection_name)

    source = "tag:object" if object_tag else "tag:collection" if collection_tag else "suffix" if suffix_role else "name"
    if explicit_group and source == "name":
        source = "tag:group"

    return {
        "name": name,
        "role": role,
        "group_name": group_name,
        "source": source,
        "collection_name": collection_name,
    }


def collect_role_matches(
    items: Iterable[Any],
    collection_tags: Mapping[str, Any] | None = None,
    *,
    prefer_suffix: bool = False,
) -> dict[str, dict[str, list[str]]]:
    matches: dict[str, dict[str, list[str]]] = {}
    for item in items:
        classification = classify_bake_item(
            item, collection_tags=collection_tags, prefer_suffix=prefer_suffix
        )
        role = classification["role"]
        if role is None:
            continue
        group_name = classification["group_name"] or normalize_group_name(classification["name"] or "")
        bucket = matches.setdefault(
            group_name,
            {
                constants.OBJECT_ROLE_LOW: [],
                constants.OBJECT_ROLE_HIGH: [],
                constants.OBJECT_ROLE_CAGE: [],
            },
        )
        bucket[role].append(classification["name"] or "")
    # Blender hands objects over in an order that changes from launch to launch (a view
    # layer is not name ordered), and the group order becomes the job's group order. The
    # backend fuses members and numbers raster items in that order, and for overlapping UVs
    # the highest item wins, so the same scene baked twice produced different maps (a nine
    # group Uzi subset: up to 65% of Object Normal). Name order makes it repeatable.
    ordered: dict[str, dict[str, list[str]]] = {}
    for group_name in sorted(matches, key=lambda name: (name.casefold(), name)):
        bucket = matches[group_name]
        ordered[group_name] = {role: sorted(names, key=lambda n: (n.casefold(), n)) for role, names in bucket.items()}
    return ordered


def collect_group_matches(items: Iterable[Any], collection_tags: Mapping[str, Any] | None = None) -> dict[str, dict[str, list[str]]]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for item in items:
        classification = classify_bake_item(item, collection_tags=collection_tags)
        group_name = classification["group_name"] or normalize_group_name(classification["name"] or "")
        role = classification["role"]
        bucket = grouped.setdefault(
            group_name,
            {
                constants.OBJECT_ROLE_LOW: [],
                constants.OBJECT_ROLE_HIGH: [],
                constants.OBJECT_ROLE_CAGE: [],
            },
        )
        if role is not None:
            bucket[role].append(classification["name"] or "")
    return grouped


def part_key_for_name(name: str) -> str:
    """The PART a mesh belongs to: its name without the role suffix and duplicate index.

    ``axe_001_low`` and ``axe_001_high_1`` share the part ``axe_001``; the prefix model
    collapses both to ``axe``.
    """
    return (strip_role_suffix(name or "") or "").strip("._- ") or "Part"


_NUMBERED_TAIL_RE = re.compile(r"^[._\- ]*\d+$")


def _parent_part_highs(part_key: str, highs: list[str]) -> list[str]:
    """The highs of the longest part that ``part_key`` extends with a word ("Axe" for
    "Axe_Blade"). A numbered sibling is not a child: "Cube_020_low" with no high of its
    own got all 29 "Cube_*_high" meshes of a customer's gun (2026-10-27), where Painter
    and Marmoset give it none."""
    best_key, best = "", []
    for high in highs:
        key = part_key_for_name(high)
        if len(key) <= len(best_key) or not part_key.startswith(key) or len(part_key) == len(key):
            if key == best_key and best_key:
                best.append(high)
            continue
        tail = part_key[len(key):]
        if tail[0] not in "._- " or _NUMBERED_TAIL_RE.match(tail):
            continue
        best_key, best = key, [high]
    return best


def split_role_matches_per_part(
    matches: Mapping[str, Mapping[str, list[str]]],
) -> tuple[dict[str, dict[str, list[str]]], dict[str, str]]:
    """Re-key prefix buckets into one bucket per low-poly PART.

    Every low mesh becomes its own bucket named after its part; the high and cage meshes
    whose part matches join it. A high or cage mesh with no part of its own is the shared
    sculpt of the whole prefix ("Teeth_HP" for "Teeth_Upper_LP" + "Teeth_Lower_LP") and
    joins every part, which is what the prefix bucket gave it. A bucket with at most one
    low mesh is already one part and is kept as it is, under its prefix name.

    Returns ``(part_matches, prefix_by_part)`` so the caller can keep the parts of one
    prefix in one texture set.
    """
    part_matches: dict[str, dict[str, list[str]]] = {}
    prefix_by_part: dict[str, str] = {}
    for prefix, bucket in matches.items():
        lows = list(bucket.get(constants.OBJECT_ROLE_LOW, []) or [])
        highs = list(bucket.get(constants.OBJECT_ROLE_HIGH, []) or [])
        cages = list(bucket.get(constants.OBJECT_ROLE_CAGE, []) or [])
        if len(lows) <= 1:
            # One part: name it after that part ("Cube_004_Curve"), not the first token
            # ("Cube"), the way Painter and Marmoset name a group by everything before
            # the role word.
            name = part_key_for_name(lows[0]) if lows else prefix
            if name in part_matches:
                name = prefix if prefix not in part_matches else f"{prefix}_{name}"
            part_matches[name] = {
                constants.OBJECT_ROLE_LOW: lows,
                constants.OBJECT_ROLE_HIGH: highs,
                constants.OBJECT_ROLE_CAGE: cages,
            }
            prefix_by_part[name] = prefix
            continue
        parts: dict[str, dict[str, list[str]]] = {}
        for low in lows:
            parts.setdefault(
                part_key_for_name(low),
                {
                    constants.OBJECT_ROLE_LOW: [],
                    constants.OBJECT_ROLE_HIGH: [],
                    constants.OBJECT_ROLE_CAGE: [],
                },
            )[constants.OBJECT_ROLE_LOW].append(low)
        shared_highs: list[str] = []
        for high in highs:
            key = part_key_for_name(high)
            if key in parts:
                parts[key][constants.OBJECT_ROLE_HIGH].append(high)
            else:
                shared_highs.append(high)
        shared_cages: list[str] = []
        for cage in cages:
            key = part_key_for_name(cage)
            if key in parts:
                parts[key][constants.OBJECT_ROLE_CAGE].append(cage)
            else:
                shared_cages.append(cage)
        for part_key, part_bucket in parts.items():
            part_bucket[constants.OBJECT_ROLE_HIGH].extend(shared_highs)
            part_bucket[constants.OBJECT_ROLE_CAGE].extend(shared_cages)
            # "Axe_low" + "Axe_Blade_low" + "Axe_high": the high's part is "Axe", so it
            # joins only that part and "Axe_Blade" would bake with no source at all. A
            # part nothing claimed borrows the highs of its nearest named parent.
            if not part_bucket[constants.OBJECT_ROLE_HIGH]:
                part_bucket[constants.OBJECT_ROLE_HIGH].extend(_parent_part_highs(part_key, highs))
        for key, part_bucket in parts.items():
            name = key if key not in part_matches else f"{prefix}_{key}"
            part_matches[name] = part_bucket
            prefix_by_part[name] = prefix
    return part_matches, prefix_by_part


def split_role_matches_per_material(
    matches: Mapping[str, Mapping[str, list[str]]],
    prefix_by_part: Mapping[str, str],
    materials_of,
) -> tuple[dict[str, dict[str, list[str]]], dict[str, str], dict[str, str]]:
    """Re-key buckets whose low meshes use several materials into one bucket per material.

    ``materials_of(low_name)`` lists the materials a low's faces use. A bucket with at most
    one material is kept as it is. The high and cage meshes join every material's bucket:
    each material bakes from the same source. A low with no material goes with the first.

    Returns ``(matches, prefix_by_part, material_by_group)``; a group absent from the last
    bakes whole objects.
    """
    split: dict[str, dict[str, list[str]]] = {}
    prefixes: dict[str, str] = {}
    material_by_group: dict[str, str] = {}
    for name, bucket in matches.items():
        lows = list(bucket.get(constants.OBJECT_ROLE_LOW, []) or [])
        low_materials = {low: list(materials_of(low) or ()) for low in lows}
        ordered = list(dict.fromkeys(material for low in lows for material in low_materials[low]))
        if len(ordered) <= 1:
            split[name] = {role: list(names) for role, names in bucket.items()}
            prefixes[name] = prefix_by_part.get(name, name)
            continue
        for index, material in enumerate(ordered):
            key = f"{name}_{material}"
            suffix = 2
            while key in split or key in matches:
                key = f"{name}_{material}_{suffix}"
                suffix += 1
            split[key] = {
                constants.OBJECT_ROLE_LOW: [
                    low for low in lows if material in low_materials[low] or (index == 0 and not low_materials[low])
                ],
                constants.OBJECT_ROLE_HIGH: list(bucket.get(constants.OBJECT_ROLE_HIGH, []) or []),
                constants.OBJECT_ROLE_CAGE: list(bucket.get(constants.OBJECT_ROLE_CAGE, []) or []),
            }
            prefixes[key] = prefix_by_part.get(name, name)
            material_by_group[key] = material
    return split, prefixes, material_by_group


def suggest_group_name(items: Iterable[Any]) -> str:
    for item in items:
        name = _item_name(item)
        if name:
            classification = classify_bake_item(item)
            if classification["group_name"]:
                return classification["group_name"] or normalize_group_name(name)
    return "BakeGroup"
