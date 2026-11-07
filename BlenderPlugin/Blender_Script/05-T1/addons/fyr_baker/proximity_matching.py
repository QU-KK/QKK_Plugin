"""Low/High name prep for baking.

A *pre-project* helper for the common duplicate workflow: a user copies a mesh
to sculpt the high-poly, so Blender leaves a ``.001`` suffix (``Jaw_01`` +
``Jaw_01.001``). This plans clean ``_low`` / ``_high`` renames so the existing
name-based auto-build (`matching.collect_role_matches`) pairs them afterward.

Rules that fall out of that workflow:

* **Retain each mesh's own name.** Objects are never renamed to some shared or
  "active" name -- ``Jaw_01.001`` becomes ``Jaw_01_high``, not ``<active>_high``.
  The one exception is a proximity pair whose own names would never group
  together (``Rock`` + ``RockDetail``): the high takes its low's base so the pair
  lands in one bake group (``Rock_low`` + ``Rock_high``).
* **Strip only the Blender duplicate suffix** (``.001``), never the user's own
  tokens: ``Jaw_01.001`` -> base ``Jaw_01`` -> ``Jaw_01_high`` (the ``_01`` stays).
* **Low vs High is decided by polygon count** -- within a pair the lower-tri mesh
  is the low-poly.

Pairing key is the shared base name (the duplicate pair). Meshes whose base name
is unique fall back to bounding-box proximity so an overlapping high with a
different name can still pair. Meshes that can't be paired (no partner) or can't
be told apart (equal tri counts) are left untouched and reported.

This module is ``bpy``-free -- it works on plain `MeshSample` records so it can be
unit-tested like `matching.py`. The operator layer builds samples from evaluated
Blender objects and applies the returned plan.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
import math
import re

from . import constants, matching

LOW_SUFFIX = constants.ROLE_SUFFIXES[constants.OBJECT_ROLE_LOW][0]  # "_low"
HIGH_SUFFIX = constants.ROLE_SUFFIXES[constants.OBJECT_ROLE_HIGH][0]  # "_high"

# Blender's duplicate suffix is specifically ".NNN" (a dot + digits). We strip
# ONLY that -- user tokens like "_01"/"-02" are part of the real name and stay.
_BLENDER_DUP_DOT_RE = re.compile(r"\.\d+$")


@dataclass(frozen=True)
class MeshSample:
    """One candidate mesh: name, evaluated tri count, and world-space AABB."""

    name: str
    tri_count: int
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]


@dataclass(frozen=True)
class RenamePlanEntry:
    object_name: str  # current object name (the key the caller renames)
    new_name: str  # desired name: own base (minus .NNN) + role suffix
    role: str  # constants.OBJECT_ROLE_LOW / OBJECT_ROLE_HIGH
    group_base: str  # base token this mesh keeps (its own retained name)


@dataclass
class PrepPlan:
    renames: list[RenamePlanEntry] = field(default_factory=list)
    # Groups that couldn't be prepped, kept for an honest operator report.
    skipped_singletons: list[str] = field(default_factory=list)
    skipped_ambiguous: list[list[str]] = field(default_factory=list)

    @property
    def pair_count(self) -> int:
        return sum(1 for entry in self.renames if entry.role == constants.OBJECT_ROLE_LOW)


def retain_base(name: str) -> str:
    """The mesh's own name with only the Blender ``.NNN`` duplicate suffix removed."""
    base = _BLENDER_DUP_DOT_RE.sub("", name or "").rstrip()
    return base or (name or "Mesh")


def _diagonal(sample: MeshSample) -> float:
    return math.dist(sample.bounds_min, sample.bounds_max)


# A pair of differently-named meshes must share at least this much of their combined
# box (intersection over union). A sculpt grown 8% and nudged off-centre still scores
# ~0.75; two props standing side by side, or a button inside a body, score near 0.
_PAIR_MIN_IOU = 0.5
# Duplicates (``Bolt`` + ``Bolt.001``) are already tied by name, so overlap only has to
# rule out a copy that was moved somewhere else; a heavily displaced sculpt still pairs.
_DUPLICATE_MIN_IOU = 0.25
# A leftover mesh joins a bake group when this much of its own box lies inside the
# group's box (floating bolts on a panel, a third duplicate, a handle under the sculpt).
_CONTAINED_MIN_RATIO = 0.9
# Several lone pieces whose combined box covers a lone mesh this well bake with it
# (a crate low-poly with separately modelled planks, or one sculpt over a split low).
_PIECES_MIN_IOU = 0.5
# Within a pair the high must carry at least this many times the low's triangles. Two
# low-poly props pushed into each other differ by a few percent; a sculpt or subdivided
# copy by 4x and up. Anything closer cannot say which one is the low.
_MIN_TRI_RATIO = 2.0


def _padded_box(sample: MeshSample, margin: float = 0.0):
    """AABB with every axis given a minimum thickness, grown by `margin`.

    A flat plane has zero volume, which would make every overlap ratio 0/0; the floor
    is relative to the mesh's own size so it does not swamp small parts.
    """
    floor = max(_diagonal(sample) * 1e-3, 1e-9)
    lo = []
    hi = []
    for axis in range(3):
        a = sample.bounds_min[axis]
        b = sample.bounds_max[axis]
        if b - a < floor:
            mid = (a + b) * 0.5
            a, b = mid - floor * 0.5, mid + floor * 0.5
        lo.append(a - margin)
        hi.append(b + margin)
    return tuple(lo), tuple(hi)


def _volume(box) -> float:
    lo, hi = box
    return max(0.0, hi[0] - lo[0]) * max(0.0, hi[1] - lo[1]) * max(0.0, hi[2] - lo[2])


def _intersection(a, b) -> float:
    (alo, ahi), (blo, bhi) = a, b
    volume = 1.0
    for axis in range(3):
        extent = min(ahi[axis], bhi[axis]) - max(alo[axis], blo[axis])
        if extent <= 0.0:
            return 0.0
        volume *= extent
    return volume


def _iou(a, b) -> float:
    inter = _intersection(a, b)
    if inter <= 0.0:
        return 0.0
    union = _volume(a) + _volume(b) - inter
    return inter / union if union > 0.0 else 0.0


def _inside_ratio(box, region) -> float:
    """Share of `box`'s volume that lies inside `region`."""
    return _intersection(box, region) / max(_volume(box), 1e-30)


def _union_box(boxes):
    boxes = list(boxes)
    lo = tuple(min(box[0][axis] for box in boxes) for axis in range(3))
    hi = tuple(max(box[1][axis] for box in boxes) for axis in range(3))
    return lo, hi


def _boxes_touch(a: MeshSample, b: MeshSample, tolerance_ratio: float) -> bool:
    """Do the two AABBs overlap once each is grown by a scale-relative margin?"""
    margin_a = _diagonal(a) * tolerance_ratio
    margin_b = _diagonal(b) * tolerance_ratio
    for axis in range(3):
        a_lo = a.bounds_min[axis] - margin_a
        a_hi = a.bounds_max[axis] + margin_a
        b_lo = b.bounds_min[axis] - margin_b
        b_hi = b.bounds_max[axis] + margin_b
        if a_hi < b_lo or b_hi < a_lo:
            return False
    return True


def _touching_pairs(samples: Sequence[MeshSample], tolerance_ratio: float):
    """Index pairs ``(i, j)``, ``i < j``, whose grown boxes touch, via a sweep on X."""
    spans = []
    for index, sample in enumerate(samples):
        margin = _diagonal(sample) * tolerance_ratio
        spans.append((sample.bounds_min[0] - margin, sample.bounds_max[0] + margin, index))
    spans.sort()
    for position, (_lo, hi, i) in enumerate(spans):
        for other_lo, _other_hi, j in spans[position + 1:]:
            if other_lo > hi:
                break
            if _boxes_touch(samples[i], samples[j], tolerance_ratio):
                yield (i, j) if i < j else (j, i)


@dataclass
class _Group:
    lows: list[int]  # lows[0] names the group; the rest are further low-poly parts
    highs: list[int]
    # highs[0] is the group's main sculpt (its pass-1 partner, or the one high over a
    # split low). Pieces found in pass 3 have no main one.
    has_main_high: bool = True


def _plan_groups(samples: Sequence[MeshSample], tolerance_ratio: float, plan: PrepPlan) -> list[_Group]:
    """Decide which meshes bake together; see `plan_lowhigh_prep` for the passes."""
    count = len(samples)
    boxes = [_padded_box(sample) for sample in samples]
    grown = [_padded_box(sample, _diagonal(sample) * tolerance_ratio) for sample in samples]
    bases = [retain_base(sample.name) for sample in samples]
    touching = sorted(_touching_pairs(samples, tolerance_ratio))

    # Pass 1: one-to-one pairs, strongest evidence first. Same base name (the .001
    # duplicate) outranks overlap; then how much the boxes coincide; then how far apart
    # the triangle counts are, so Gun + Gun.001 wins over two high variants Gun.001 +
    # Gun.002. Equal triangle counts cannot say which is the low, so they never pair.
    candidates = []
    tied_pairs: list[tuple[int, int]] = []
    for i, j in touching:
        same_base = bases[i] == bases[j]
        overlap = _iou(boxes[i], boxes[j])
        if overlap < (_DUPLICATE_MIN_IOU if same_base else _PAIR_MIN_IOU):
            continue
        tris_i, tris_j = samples[i].tri_count, samples[j].tri_count
        ratio = max(tris_i, tris_j) / max(1, min(tris_i, tris_j))
        if ratio < _MIN_TRI_RATIO:
            tied_pairs.append((i, j))
            continue
        # Overlap is compared in 0.1 steps: two sculpt variants of one mask coincide a
        # hair better with each other than with the low, and must not pair on that.
        candidates.append((same_base, int(overlap * 10), ratio, -i, -j, i, j))
    candidates.sort(reverse=True)
    group_of: dict[int, _Group] = {}
    groups: list[_Group] = []
    for *_rank, i, j in candidates:
        if i in group_of or j in group_of:
            continue
        low, high = (i, j) if samples[i].tri_count < samples[j].tri_count else (j, i)
        group = _Group(lows=[low], highs=[high])
        groups.append(group)
        group_of[i] = group_of[j] = group
    # An unpaired mesh that coincides with a near-equal-tri twin is a duplicate nobody has
    # subdivided yet, or two props pushed into each other: which one is the low is
    # unknowable, so neither may be guessed at by the passes below.
    tied: set[int] = set()
    for i, j in tied_pairs:
        if i not in group_of and j not in group_of:
            tied.update((i, j))
            plan.skipped_ambiguous.append(sorted((samples[i].name, samples[j].name)))

    # Pass 2: a leftover that sits inside a group's box is part of that bake. The
    # tightest enclosing group wins, so a bolt on a button joins the button rather than
    # the body around it. Inside the LOW's own box it is a floating detail or another
    # high variant; outside the low but under the high it is another low-poly part the
    # one sculpt also covers (a sword handle next to the blade).
    for index in range(count):
        if index in group_of or index in tied:
            continue
        best = None
        for group in groups:
            low = group.lows[0]
            if samples[index].tri_count <= samples[low].tri_count and bases[index] == bases[low]:
                continue  # a second low-poly copy of the same mesh is not a high
            region = _union_box(grown[member] for member in (*group.lows, *group.highs))
            if _inside_ratio(boxes[index], region) < _CONTAINED_MIN_RATIO:
                continue
            size = _volume(region)
            if best is None or size < best[0]:
                best = (size, group)
        if best is None:
            continue
        group = best[1]
        on_low = _inside_ratio(boxes[index], _union_box(grown[low] for low in group.lows))
        fewest_high_tris = min(samples[high].tri_count for high in group.highs)
        if on_low < _CONTAINED_MIN_RATIO and samples[index].tri_count < fewest_high_tris:
            group.lows.append(index)
        else:
            group.highs.append(index)
        group_of[index] = group

    # Pass 3: a lone mesh whose box is filled by several other lone meshes. With more
    # triangles in the pieces it is the low-poly of a high modelled in pieces (a crate
    # and its planks); with fewer, it is one sculpt over a low split into parts.
    leftovers = [index for index in range(count) if index not in group_of and index not in tied]
    for host in sorted(leftovers, key=lambda index: (-_volume(boxes[index]), index)):
        if host in group_of:
            continue
        pieces = [
            index
            for index in leftovers
            if index != host
            and index not in group_of
            and _inside_ratio(boxes[index], grown[host]) >= _CONTAINED_MIN_RATIO
        ]
        if len(pieces) < 2:
            continue
        if _iou(_union_box(boxes[index] for index in pieces), boxes[host]) < _PIECES_MIN_IOU:
            continue
        piece_tris = sum(samples[index].tri_count for index in pieces)
        if piece_tris == samples[host].tri_count:
            continue
        if piece_tris > samples[host].tri_count:
            group = _Group(lows=[host], highs=pieces, has_main_high=False)
        else:
            pieces.sort(key=lambda index: (-_volume(boxes[index]), samples[index].name))
            group = _Group(lows=pieces, highs=[host])
        groups.append(group)
        for member in (host, *pieces):
            group_of[member] = group

    # Pass 4: the original rule for whatever is left. Two lone meshes that touch only
    # each other are a pair even when one box is much bigger (a sculpt displaced well
    # past its low-poly). Three or more touching lone meshes stay ambiguous: labeling
    # every visible part of a character "_high" by polycount corrupts names.
    remaining = [index for index in range(count) if index not in group_of and index not in tied]
    remaining_set = set(remaining)
    neighbours: dict[int, set[int]] = {index: set() for index in remaining}
    for i, j in touching:
        if i in remaining_set and j in remaining_set:
            neighbours[i].add(j)
            neighbours[j].add(i)
    seen: set[int] = set()
    for start in remaining:
        if start in seen:
            continue
        cluster = []
        stack = [start]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            cluster.append(node)
            stack.extend(neighbours[node] - seen)
        cluster.sort()
        names = sorted(samples[index].name for index in cluster)
        if len(cluster) == 1:
            plan.skipped_singletons.append(names[0])
            continue
        if len(cluster) > 2:
            plan.skipped_ambiguous.append(names)
            continue
        i, j = cluster
        tris_i, tris_j = samples[i].tri_count, samples[j].tri_count
        if max(tris_i, tris_j) < _MIN_TRI_RATIO * max(1, min(tris_i, tris_j)):
            plan.skipped_ambiguous.append(names)
            continue
        low, high = (i, j) if samples[i].tri_count < samples[j].tri_count else (j, i)
        groups.append(_Group(lows=[low], highs=[high]))
    return groups


def plan_lowhigh_prep(
    samples: Iterable[MeshSample],
    *,
    tolerance_ratio: float = 0.05,
) -> PrepPlan:
    """Plan clean Low/High renames, retaining names and stripping only ``.NNN``.

    Passes, strongest evidence first:

    1. One-to-one pairs: a ``.001`` duplicate, or two meshes whose boxes largely
       coincide. The lower-tri mesh of each pair is the LOW.
    2. A leftover mesh inside a pair's box joins it: as another HIGH when it sits on
       the low (floaters), as another LOW when only the high covers it.
    3. A lone mesh whose box is filled by several lone meshes is their LOW, or, when
       it has more triangles than all of them, their HIGH.
    4. Two lone meshes touching only each other pair; bigger lone clusters and
       triangle counts too close to tell apart are reported, never guessed.
    """
    ordered = list(samples)
    plan = PrepPlan()
    if not ordered:
        return plan
    groups = _plan_groups(ordered, tolerance_ratio, plan)
    groups.sort(key=lambda group: (ordered[group.lows[0]].bounds_min, ordered[group.lows[0]].name))
    for group in groups:
        low = ordered[group.lows[0]]
        low_base = retain_base(low.name)
        low_key = matching.group_key_for_name(low_base)
        plan.renames.append(
            RenamePlanEntry(low.name, f"{low_base}{LOW_SUFFIX}", constants.OBJECT_ROLE_LOW, low_base)
        )
        for index in sorted(group.lows[1:], key=lambda member: ordered[member].name):
            part = ordered[index]
            base = retain_base(part.name)
            # A further low part keeps its own name as the PART token behind the group
            # prefix (``Handle`` -> ``Blade_Handle_low``): renaming a low-poly away from
            # what the artist called it would lose which part it is.
            if matching.group_key_for_name(base) != low_key:
                base = f"{low_base}_{base}"
            plan.renames.append(
                RenamePlanEntry(part.name, f"{base}{LOW_SUFFIX}", constants.OBJECT_ROLE_LOW, base)
            )
        main = group.highs[:1] if group.has_main_high else []
        rest = sorted((index for index in group.highs if index not in main), key=lambda member: ordered[member].name)
        for index in (*main, *rest):
            high = ordered[index]
            base = retain_base(high.name)
            # The name-based build groups by prefix, so a high whose own name keys to a
            # different group than its low is renamed under the low's base: the main
            # sculpt plainly (``Rock`` + ``RockDetail`` -> ``Rock_low`` + ``Rock_high``),
            # any further piece or floater keeping its own name as the part token
            # (``BoltA`` -> ``Panel_BoltA_high``). Duplicates keep their own name.
            if matching.group_key_for_name(base) != low_key:
                base = low_base if index in main else f"{low_base}_{base}"
            plan.renames.append(
                RenamePlanEntry(high.name, f"{base}{HIGH_SUFFIX}", constants.OBJECT_ROLE_HIGH, base)
            )
    return plan
