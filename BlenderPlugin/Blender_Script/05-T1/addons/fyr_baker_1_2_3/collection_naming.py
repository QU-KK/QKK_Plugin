"""Collection-driven Low/High naming.

A second, *additive* route to suffixed mesh names, alongside
`proximity_matching.plan_lowhigh_prep`. That one infers the pairing from the scene
(shared base name, then bounding-box overlap, low decided by polycount); this one
asks the artist's own scene organisation instead:

    Barrel/            <- set key: the parent collection
      low/             <- collection name carries the role
        BarrelBody
      high/
        BarrelBody_sculpt
        BarrelBolts
        BarrelRim

becomes ``417_low`` + ``417_high01`` / ``417_high02`` / ``417_high03``.

It exists because the layer-per-role habit comes straight from 3ds Max, where the
role is a property of the *container*, not of the object name -- so the meshes
inside arrive with production names that no suffix heuristic can pair, and the
polycount rule is simply wrong when several high-poly parts feed one low.

Two conventions this encodes, both from that workflow:

* **A shared, arbitrary base name per set.** The base carries no meaning and is not
  derived from any mesh, so it can never collide with the semantics of a name the
  artist chose; a random one just has to be unique in the scene.
* **The index goes after the suffix** (``_high01``, not ``_01_high``) because that
  is the position Marmoset Toolbag reads it from. `matching.strip_role_numbering`
  is the other half of that contract -- it has to see these names as roles.

Only a role with more than one mesh is numbered: a lone high-poly stays ``_high``,
which is the more readable form and equally valid downstream.

This module is ``bpy``-free -- it plans over plain `CollectionMeshSample` records,
so it unit-tests like `matching.py` and `proximity_matching.py`. The operator layer
builds the samples from Blender collections and applies the returned plan.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
import re

from . import constants

_TOKEN_SPLIT_RE = re.compile(r"[._\-\s]+")

#: Collection-name tokens that name a bake role. Matched as whole tokens, so a
#: collection called "Highland" or "Slow" is not a role -- same guarantee the
#: object-name suffix table gives, but without requiring a leading separator: a
#: collection is usually named for the role and nothing else ("high", "LP").
ROLE_COLLECTION_TOKENS: dict[str, tuple[str, ...]] = {
    constants.OBJECT_ROLE_LOW: ("low", "lp", "lowpoly", "lowres"),
    constants.OBJECT_ROLE_HIGH: ("high", "hp", "highpoly", "highres"),
    constants.OBJECT_ROLE_CAGE: ("cage",),
}

#: Role order within a set, so a plan is stable and reads low-first.
_ROLE_ORDER = (
    constants.OBJECT_ROLE_LOW,
    constants.OBJECT_ROLE_HIGH,
    constants.OBJECT_ROLE_CAGE,
)


@dataclass(frozen=True)
class CollectionMeshSample:
    """One candidate mesh and the collections it sits in.

    ``parent_names`` is index-aligned with ``collection_names``: the parent of each
    collection, or "" when it hangs directly off the scene. The parent of the
    role collection is what groups meshes into one bake set, so selecting several
    assets at once renames each of them against its own base.
    """

    name: str
    collection_names: tuple[str, ...] = ()
    parent_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class CollectionRenameEntry:
    object_name: str  # current object name (the key the caller renames)
    new_name: str  # "<base><role suffix>" plus an index when the role has several
    role: str  # constants.OBJECT_ROLE_LOW / OBJECT_ROLE_HIGH / OBJECT_ROLE_CAGE
    base: str  # the shared base name assigned to this mesh's set
    set_key: str  # parent collection that grouped the set ("" = scene root)


@dataclass
class CollectionNamePlan:
    renames: list[CollectionRenameEntry] = field(default_factory=list)
    #: Meshes in no role-named collection. Reported, never guessed at.
    skipped_unclassified: list[str] = field(default_factory=list)
    #: Meshes whose collections named two different roles at once.
    skipped_ambiguous: list[str] = field(default_factory=list)

    @property
    def set_count(self) -> int:
        return len({entry.set_key for entry in self.renames})

    @property
    def base_names(self) -> list[str]:
        seen: list[str] = []
        for entry in self.renames:
            if entry.base not in seen:
                seen.append(entry.base)
        return seen


def role_from_collection_name(name: str) -> str | None:
    """The bake role a collection's name declares, or None.

    Returns None when the name names more than one role, so an "old_low_high_backup"
    collection is reported rather than silently resolved to whichever came first.
    """
    tokens = {token.lower() for token in _TOKEN_SPLIT_RE.split(str(name or "")) if token}
    if not tokens:
        return None
    matched = [role for role, words in ROLE_COLLECTION_TOKENS.items() if tokens & set(words)]
    if len(matched) != 1:
        return None
    return matched[0]


def resolve_sample_role(sample: CollectionMeshSample) -> tuple[str | None, str, bool]:
    """Resolve one mesh's (role, set key, ambiguous) from its collections.

    A mesh linked into several collections takes the first that names a role, in
    the order Blender reports them. ``ambiguous`` is True only when a collection
    name itself named two roles -- that is a scene problem worth reporting, not a
    mesh to skip quietly.
    """
    parents = sample.parent_names
    for index, collection_name in enumerate(sample.collection_names):
        tokens = {token.lower() for token in _TOKEN_SPLIT_RE.split(str(collection_name or "")) if token}
        matched = [role for role, words in ROLE_COLLECTION_TOKENS.items() if tokens & set(words)]
        if not matched:
            continue
        if len(matched) > 1:
            return None, "", True
        parent = parents[index] if index < len(parents) else ""
        return matched[0], str(parent or ""), False
    return None, "", False


def numbered_name(base: str, role: str, index: int, total: int, *, pad: int = 2) -> str:
    """"<base>_high01" when the role has several meshes, "<base>_high" when it has one.

    The index trails the suffix because that is where Marmoset Toolbag looks for it.
    """
    suffix = constants.ROLE_SUFFIXES[role][0]
    if total <= 1:
        return f"{base}{suffix}"
    return f"{base}{suffix}{index:0{pad}d}"


def plan_collection_names(
    samples: Iterable[CollectionMeshSample],
    *,
    base_name_factory: Callable[[int], str],
    pad: int = 2,
) -> CollectionNamePlan:
    """Plan ``<base>_low`` / ``<base>_highNN`` renames from collection membership.

    ``base_name_factory`` is called once per set, in plan order, and owns uniqueness
    against the scene -- the planner stays deterministic and testable by never
    generating a name itself.
    """
    plan = CollectionNamePlan()
    by_set: dict[str, dict[str, list[str]]] = {}

    for sample in samples:
        role, set_key, ambiguous = resolve_sample_role(sample)
        if ambiguous:
            plan.skipped_ambiguous.append(sample.name)
            continue
        if role is None:
            plan.skipped_unclassified.append(sample.name)
            continue
        by_set.setdefault(set_key, {}).setdefault(role, []).append(sample.name)

    for set_index, set_key in enumerate(sorted(by_set)):
        roles = by_set[set_key]
        base = base_name_factory(set_index)
        for role in _ROLE_ORDER:
            members = sorted(roles.get(role, []))
            total = len(members)
            for position, object_name in enumerate(members, start=1):
                new_name = numbered_name(base, role, position, total, pad=pad)
                if new_name == object_name:
                    continue
                plan.renames.append(
                    CollectionRenameEntry(object_name, new_name, role, base, set_key)
                )

    plan.skipped_unclassified.sort()
    plan.skipped_ambiguous.sort()
    return plan


def sequential_base_factory(bases: Sequence[str]) -> Callable[[int], str]:
    """A factory over a fixed list of base names, for tests and explicit input."""

    def factory(index: int) -> str:
        return bases[index] if index < len(bases) else f"{bases[-1] if bases else 'Set'}_{index}"

    return factory
