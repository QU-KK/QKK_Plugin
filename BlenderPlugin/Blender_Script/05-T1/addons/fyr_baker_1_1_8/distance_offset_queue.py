"""Fit the Distance offsets of freshly built bake groups after the build returns.

operators._apply_estimated_cage_offsets_to_new_groups queues every new Distance group.
The estimate builds a BVH of each high (~17 s on a customer's 71-group gun of ~100 M
triangles), so it runs one group per timer tick instead of inside Auto-Build, and a bake
started before the queue drains finishes it first (export.prepare_bake_job).
"""

import bpy

from . import cage_offset_estimator, constants

#: (scene name, project name, group name) awaiting a fitted offset, oldest first.
_PENDING: list[tuple[str, str, str]] = []
#: Groups whose offset was already estimated this session (fitted, or the estimate stayed
#: at the floor), so the bake-time sweep below never repeats a ~17 s estimate per rebake.
_CHECKED: set[tuple[str, str, str]] = set()


def enqueue(context, group) -> bool:
    """Queue ``group``'s offset fit. Groups are re-found by name at fit time, so a group
    renamed or removed in the meantime is skipped instead of dangling."""
    scene = getattr(context, "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None)
    project = next(
        (
            candidate
            for candidate in getattr(settings, "projects", []) or []
            if any(member == group for member in getattr(candidate, "groups", []) or [])
        ),
        None,
    )
    if project is None:
        return False
    _PENDING.append((str(scene.name), str(project.name), str(group.name)))
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.2)
    return True


def pending_count() -> int:
    return len(_PENDING)


def _fit_one(entry, depsgraph=None) -> bool:
    _CHECKED.add(tuple(entry))
    scene_name, project_name, group_name = entry
    scene = bpy.data.scenes.get(scene_name)
    settings = getattr(scene, "fyr_baker_settings", None)
    project = next((p for p in getattr(settings, "projects", []) or [] if p.name == project_name), None)
    group = next((g for g in getattr(project, "groups", []) or [] if g.name == group_name), None)
    if group is None:
        return False
    # Groups that share a high capture it once: the estimator keeps the high's digest and
    # world vertices while this scope is open (closed when the queue drains).
    cage_offset_estimator.begin_shared_fit()
    return fit_group(group, depsgraph)


def fit_group(group, depsgraph=None) -> bool:
    """Give ``group`` the estimator's offset; True when it changed."""
    from . import operators, properties

    # Only while the artist has not taken over: still Distance, still on the default.
    if str(getattr(group, "cage_mode", "") or "") != constants.CAGE_MODE_DISTANCE:
        return False
    default_offset = float(constants.DEFAULT_CAGE_OFFSET)
    if abs(float(getattr(group, "cage_offset", default_offset) or 0.0) - default_offset) > 1e-9:
        return False
    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            depsgraph = None
    try:
        estimate = operators._estimate_group_cage_offset(group, depsgraph=depsgraph)
    except Exception:
        estimate = None
    if estimate is None or float(estimate) <= default_offset:
        return False
    # Fitted per group: a Texture Set / Global "Apply To" scope would mirror the first
    # group's estimate onto its siblings, which then no longer sit on the default.
    with properties.suppress_cage_scope_propagation():
        group.cage_offset = float(estimate)
    return True


_DONE = 0
_TOTAL = 0
_CARD_SHOWN = False


def _card(detail: str | None, factor: float = 0.0) -> None:
    """The setup_progress card: shown while fits remain, so a long fit never looks stuck."""
    global _CARD_SHOWN, _DONE, _TOTAL
    from . import overlays, setup_progress

    try:
        owner = setup_progress.current_title()
        if detail is None:
            if _CARD_SHOWN and owner == "Fitting cage offsets":
                setup_progress.end()
            _CARD_SHOWN = False
            _DONE = _TOTAL = 0
        elif owner and owner != "Fitting cage offsets":
            pass  # another job owns the card
        elif _CARD_SHOWN and owner:
            setup_progress.update(detail, factor)
        else:
            setup_progress.begin("Fitting cage offsets", detail, factor)
            _CARD_SHOWN = True
        # Redraw only: a full preview-visibility sync walks every group and object,
        # which on every fit tick made Auto-Build quadratic in the group count.
        overlays.tag_redraw_all_view3d(sync_preview=False)
    except Exception:
        pass


def _tick():
    global _DONE, _TOTAL
    if not _PENDING:
        cage_offset_estimator.end_shared_fit()
        _card(None)
        return None
    _TOTAL = max(_TOTAL, _DONE + len(_PENDING))
    if not _CARD_SHOWN:
        # Announce first, so the card is on screen while the next fit blocks.
        _card(f"{_DONE + 1} of {_TOTAL}", _DONE / _TOTAL)
        return 0.01
    _fit_one(_PENDING.pop(0))
    _DONE += 1
    if _PENDING:
        _card(f"{_DONE + 1} of {_TOTAL}", _DONE / _TOTAL)
        return 0.01
    cage_offset_estimator.end_shared_fit()
    _card(None)
    return None


def reset() -> None:
    """Forget the queue (file load, unregister): its groups belong to the old file, and
    the timer that drains it does not survive a load."""
    try:
        if bpy.app.timers.is_registered(_tick):
            bpy.app.timers.unregister(_tick)
    except Exception:
        pass
    _PENDING.clear()
    _CHECKED.clear()
    cage_offset_estimator.end_shared_fit()
    try:
        _card(None)
    except Exception:
        pass


@bpy.app.handlers.persistent
def _load_post(_dummy):
    reset()


def register() -> None:
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)


def unregister() -> None:
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
    reset()


def fit_now(project=None) -> int:
    """Finish the queued fits (all, or one project's) before a bake reads the offsets."""
    if not _PENDING:
        return 0
    project_name = str(getattr(project, "name", "") or "") if project is not None else None
    remaining, due = [], []
    for entry in _PENDING:
        (due if project_name is None or entry[1] == project_name else remaining).append(entry)
    _PENDING[:] = remaining
    if not remaining:
        _card(None)
    depsgraph = None
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    except Exception:
        pass
    try:
        return sum(1 for entry in due if _fit_one(entry, depsgraph))
    finally:
        if not _PENDING:
            cage_offset_estimator.end_shared_fit()


def fit_unfitted_now(context, project) -> int:
    """Fit every Distance group of ``project`` still on the default offset that was never
    estimated this session. Auto-Build queues its new groups, but a group switched to
    Distance later (from Automatic, Custom or a loaded file) kept the 2 cm default and
    baked with holes wherever the high stands further off the low."""
    scene = getattr(context, "scene", None)
    if scene is None or project is None:
        return 0
    default_offset = float(constants.DEFAULT_CAGE_OFFSET)
    due = []
    for group in getattr(project, "groups", []) or []:
        if str(getattr(group, "cage_mode", "") or "") != constants.CAGE_MODE_DISTANCE:
            continue
        if abs(float(getattr(group, "cage_offset", default_offset) or 0.0) - default_offset) > 1e-9:
            continue
        entry = (str(scene.name), str(project.name), str(group.name))
        if entry not in _CHECKED:
            due.append(entry)
    if not due:
        return 0
    depsgraph = None
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    except Exception:
        pass
    try:
        return sum(1 for entry in due if _fit_one(entry, depsgraph))
    finally:
        if not _PENDING:
            cage_offset_estimator.end_shared_fit()
