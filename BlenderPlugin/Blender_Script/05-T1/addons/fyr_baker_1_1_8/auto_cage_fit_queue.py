"""Fit automatic preview cages one group per timer tick, with a progress card.

The viewport used to fit every visible automatic cage inside its draw: with the ray reach
check (cage.raise_offsets_to_ray_reach) a customer's 73-group gun froze the viewport for
minutes with nothing on screen. The static overlay build now asks here for a fit it does
not have yet, draws the groups that are ready, and is rebuilt as each fit lands, while the
setup_progress card counts the groups down.

Two stages, so cages show quickly (2026-10-28): every group's plain coverage fit first
("Fitting automatic cages"), then each group's ray reach refinement ("Refining automatic
cages"), which needs a BVH of the high and is most of the cost. A refined fit found in
cage_fit_store skips both.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback

import bpy

from . import cage

STAGE_PLAIN = "plain"
STAGE_REFINE = "refine"
_TITLES = {STAGE_PLAIN: "Fitting automatic cages", STAGE_REFINE: "Refining automatic cages"}

#: stage -> {fit key -> builder(depsgraph)}, in request order.
_PENDING: dict = {STAGE_PLAIN: {}, STAGE_REFINE: {}}
#: Keys whose fit raised or came back empty, so the draw does not re-request them forever.
_FAILED: set = set()
_DONE = {STAGE_PLAIN: 0, STAGE_REFINE: 0}
_TOTAL = {STAGE_PLAIN: 0, STAGE_REFINE: 0}
_CARD_TITLE = ""
#: Fits keep running in one tick until this much time has passed, or this many fits:
#: the fitted-cage memo holds 12 groups, and more fits than that before the drawing data
#: is rebuilt would evict cages still waiting to be drawn.
_TICK_BUDGET_SECONDS = 0.25
_TICK_MAX_FITS = 6


#: A refine tick can block for seconds (a dense high's BVH cannot be split), so it waits
#: until no 3D view has moved for this long: orbiting while cages refine stays smooth.
_NAVIGATION_QUIET_SECONDS = 0.75
_LAST_VIEW_SIGNATURE = None
_LAST_VIEW_CHANGE = 0.0


def _viewport_navigating() -> bool:
    """True while a 3D view moved (orbit, pan, zoom) within the last quiet window."""
    global _LAST_VIEW_SIGNATURE, _LAST_VIEW_CHANGE
    signature = []
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                region_3d = getattr(area.spaces.active, "region_3d", None)
                if region_3d is not None:
                    signature.append(tuple(round(value, 5) for row in region_3d.view_matrix for value in row))
    except Exception:
        return False
    signature = tuple(signature)
    now = time.monotonic()
    if signature != _LAST_VIEW_SIGNATURE:
        _LAST_VIEW_SIGNATURE = signature
        _LAST_VIEW_CHANGE = now
    return now - _LAST_VIEW_CHANGE < _NAVIGATION_QUIET_SECONDS


def _background() -> bool:
    return bool(getattr(getattr(bpy, "app", None), "background", True))


def background() -> bool:
    """True in headless Blender, where there is no draw loop to finish a Deferred fit."""
    return _background()


class Deferred:
    """A fit whose slow half needs no Blender data: ``work()`` runs on a worker thread and
    ``finish(result)`` turns its result into the fitted triangles on the main thread.

    A builder returns one instead of the triangles; the queue starts the thread, keeps the
    viewport drawing, and stores what ``finish`` returns once the thread is done."""

    def __init__(self, work, finish):
        self.work = work
        self.finish = finish
        self.result = None
        self.error = None
        self.thread = None

    def start(self) -> None:
        # Blender enters Python hundreds of times a frame (panel draws, handlers) and each
        # entry waits up to the switch interval (5 ms) for the worker to let go: about a
        # second per frame on a customer's gun. 0.2 ms keeps frames near their usual time.
        global _SAVED_SWITCH_INTERVAL
        if _SAVED_SWITCH_INTERVAL is None:
            _SAVED_SWITCH_INTERVAL = sys.getswitchinterval()
            sys.setswitchinterval(min(_SAVED_SWITCH_INTERVAL, _WORKER_SWITCH_INTERVAL))

        def _run():
            try:
                self.result = self.work()
            except BaseException as exc:  # reported on the main thread
                self.error = exc

        self.thread = threading.Thread(target=_run, name="FyrCageFit", daemon=True)
        self.thread.start()


def _inline(fitted):
    """A Deferred run to completion on this thread (no queue to finish it later)."""
    if isinstance(fitted, Deferred):
        return fitted.finish(fitted.work())
    return fitted


_WORKER_SWITCH_INTERVAL = 0.0002
_SAVED_SWITCH_INTERVAL = None


def _restore_switch_interval() -> None:
    global _SAVED_SWITCH_INTERVAL
    if _SAVED_SWITCH_INTERVAL is not None:
        sys.setswitchinterval(_SAVED_SWITCH_INTERVAL)
        _SAVED_SWITCH_INTERVAL = None


#: (key, stage, Deferred) of the fit whose worker thread is running, or None.
_IN_FLIGHT = None


def fitted_or_request(key, builder, *, front: bool = False, stage: str = STAGE_PLAIN):
    """The fitted triangles for ``key`` if they are ready, else None after queueing the fit.

    Background (headless) Blender has no draw loop to come back, so it fits inline."""
    if key is None or _background():
        return cage.get_or_build_auto_cage_fitted(key, lambda: _inline(builder(None))) or []
    cached = cage.peek_auto_cage_fitted(key)
    if cached is not None:
        return cached
    if key in _FAILED:
        return []
    pending = _PENDING[stage]
    if key not in pending:
        pending[key] = builder
        _TOTAL[stage] += 1
    if front and next(iter(pending)) != key:
        # Fit this one next (the active group): rebuild the order with it first.
        rest = {k: v for k, v in pending.items() if k != key}
        pending.clear()
        pending[key] = builder
        pending.update(rest)
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.01)
    return None


def cancel(key, stage: str) -> None:
    """Drop a queued fit that is no longer needed (its result came from elsewhere)."""
    if _PENDING[stage].pop(key, None) is not None:
        _TOTAL[stage] = max(_DONE[stage], _TOTAL[stage] - 1)


def has_failed(key) -> bool:
    return key in _FAILED


def pending_count() -> int:
    return sum(len(pending) for pending in _PENDING.values()) + (1 if _IN_FLIGHT is not None else 0)


def _show_card(stage: str) -> None:
    global _CARD_TITLE
    from . import setup_progress

    title = _TITLES[stage]
    total = max(_TOTAL[stage], 1)
    done = _DONE[stage]
    detail = f"{min(done + 1, total)} of {total}"
    try:
        owner = setup_progress.current_title()
        if owner and owner not in _TITLES.values():
            # Another job (a bake's setup) owns the card: never write into it.
            return
        if owner == title:
            setup_progress.update(detail, done / total)
        else:
            setup_progress.begin(title, detail, done / total)
        _CARD_TITLE = title
    except Exception:
        pass


def _hide_card() -> None:
    global _CARD_TITLE
    from . import setup_progress

    if _CARD_TITLE and setup_progress.current_title() == _CARD_TITLE:
        try:
            setup_progress.end()
        except Exception:
            pass
    _CARD_TITLE = ""
    for stage in _DONE:
        _DONE[stage] = 0
        _TOTAL[stage] = 0


def _redraw(clear_static: bool) -> None:
    from . import overlays

    try:
        if clear_static:
            overlays.invalidate_overlay_cache(clear_static=True)
        # A plain region redraw: the default also re-syncs every group's preview objects,
        # ~15 ms a call on a 73-group gun, and this runs after every fit.
        overlays.tag_redraw_all_view3d(sync_preview=False)
    except Exception:
        pass


def _land(key, fitted) -> None:
    if fitted:
        cage.get_or_build_auto_cage_fitted(key, lambda: fitted)
    else:
        _FAILED.add(key)


def _finish_in_flight() -> str | None:
    """Store the in-flight fit if its thread is done: its stage, else None."""
    global _IN_FLIGHT
    key, stage, deferred = _IN_FLIGHT
    if deferred.thread is not None and deferred.thread.is_alive():
        return None
    _IN_FLIGHT = None
    _restore_switch_interval()
    fitted = None
    if deferred.error is None:
        try:
            fitted = deferred.finish(deferred.result)
        except Exception:
            traceback.print_exc()
    else:
        traceback.print_exception(deferred.error)
    _land(key, fitted)
    _DONE[stage] += 1
    return stage


def _tick():
    global _IN_FLIGHT
    if _IN_FLIGHT is not None:
        finished = _finish_in_flight()
        if finished is None:
            return 0.05  # the worker is still casting rays; the viewport stays live
        if pending_count():
            _show_card(STAGE_PLAIN if _PENDING[STAGE_PLAIN] else STAGE_REFINE)
        else:
            _hide_card()
        _redraw(clear_static=True)
        return 0.01 if pending_count() else None
    stage = STAGE_PLAIN if _PENDING[STAGE_PLAIN] else STAGE_REFINE
    pending = _PENDING[stage]
    if not pending:
        _hide_card()
        _redraw(clear_static=False)
        return None
    if stage == STAGE_REFINE and _viewport_navigating():
        # Cages are all on screen already; refine once the view rests.
        return 0.25
    # Announce before the blocking fit so the card is on screen while it runs.
    if _CARD_TITLE != _TITLES[stage]:
        _show_card(stage)
        _redraw(clear_static=False)
        return 0.01
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    except Exception:
        depsgraph = None
    # Several quick fits per tick (each tick ends in a full rebuild of the cage drawing
    # data), but never past the budget, so the card and the viewport keep updating.
    started = time.perf_counter()
    while pending:
        key = next(iter(pending))
        builder = pending.pop(key)
        fitted = cage.peek_auto_cage_fitted(key)
        if fitted is None:
            try:
                fitted = builder(depsgraph)
            except Exception:
                traceback.print_exc()
                fitted = None
            if isinstance(fitted, Deferred):
                fitted.start()
                _IN_FLIGHT = (key, stage, fitted)
                _redraw(clear_static=False)
                return 0.05
        _land(key, fitted)
        _DONE[stage] += 1
        if time.perf_counter() - started > _TICK_BUDGET_SECONDS or _DONE[stage] % _TICK_MAX_FITS == 0:
            break
    if pending_count():
        if (STAGE_PLAIN if _PENDING[STAGE_PLAIN] else STAGE_REFINE) == stage:
            _show_card(stage)
    else:
        _hide_card()
    _redraw(clear_static=True)
    return 0.01 if pending_count() else None


def reset() -> None:
    """Forget every queued and in-flight fit. Loading a file drops the queue's timer, and
    builders hold the old file's objects, so a queue left behind would never drain: the
    prewarm waits on it forever and the worker switch interval stays lowered. A worker
    still running finishes on its own and its result is dropped."""
    global _IN_FLIGHT
    try:
        if bpy.app.timers.is_registered(_tick):
            bpy.app.timers.unregister(_tick)
    except Exception:
        pass
    _IN_FLIGHT = None
    _restore_switch_interval()
    for pending in _PENDING.values():
        pending.clear()
    _FAILED.clear()
    try:
        _hide_card()
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


def forget_failures() -> None:
    """A geometry edit may make a failed fit work: let the draw ask again."""
    _FAILED.clear()
