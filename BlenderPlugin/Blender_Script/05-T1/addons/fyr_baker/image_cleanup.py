"""Safe removal of temporary image datablocks.

Freeing a ``bpy.types.Image`` while a background preview job still holds a GPU
texture for it is a use-after-free: the preview thread binds the texture after
the datablock is gone and Blender dies inside ``GLStateManager::texture_bind``
(see ``docs/CRASH_CANCEL_PREVIEW_EEVEE_2026_08_29.md``, and the earlier prep-path
instance fixed in ``07da4180``).  Bake targets are wired into material nodes, so
any material preview of those materials references our scratch images.

``remove_image_when_safe`` removes the datablock immediately when no preview job
is in flight, and otherwise defers the removal to an app timer that retries
until the job finishes. Callers must already have unlinked the image from any
material nodes before calling. Deferred requests are abandoned if the image is
renamed, replaced, or acquires users (including a newly enabled fake user).
"""

from __future__ import annotations

import time

# Jobs whose worker threads may hold a GPU texture for one of our images.
_BUSY_JOB_TYPES = ("RENDER_PREVIEW", "RENDER")

# How often a deferred removal re-checks whether the preview job has finished.
RETRY_INTERVAL_SECONDS = 0.25

# Images waiting for a preview job to finish, keyed by datablock name so a second
# request for the same image does not register a second timer. Keep only scalar
# identity/state, never a live datablock across a file load. A name lookup must
# match the captured session UID before it can authorize removal.
_PENDING: dict[str, dict] = {}


def _image_is_valid(image) -> bool:
    """True when ``image`` is a live datablock (a freed one raises on access)."""
    if image is None:
        return False
    try:
        name = image.name
    except Exception:
        # ReferenceError for a freed datablock; anything else is equally unusable.
        return False
    return isinstance(name, str)


def _preview_job_running(bpy) -> bool:
    """True when a render/preview job may be touching our textures.

    ``bpy.app.is_job_running`` exists in Blender 5.x.  Older builds and the test
    stubs do not have it; treat its absence as "nothing running" so the caller
    falls back to the historical immediate removal.
    """
    app = getattr(bpy, "app", None)
    is_job_running = getattr(app, "is_job_running", None)
    if not callable(is_job_running):
        return False
    for job_type in _BUSY_JOB_TYPES:
        try:
            if is_job_running(job_type):
                return True
        except Exception:
            # Unknown job enum on this build - it cannot be running, keep looking.
            continue
    return False


def _remove_now(image) -> bool:
    try:
        import bpy

        # Never unlink an image that has been adopted by a material or marked
        # for retention since the caller requested cleanup.
        if image.users != 0 or image.use_fake_user:
            return False
        bpy.data.images.remove(image, do_unlink=False)
        return True
    except Exception:
        return False


def _defuse(image) -> None:
    """Make a datablock we are about to orphan harmless to Blender's purge."""
    try:
        image.use_fake_user = False
    except Exception:
        pass


def _image_session_uid(image) -> int | None:
    """A non-reusable ID; memory addresses and names can belong to replacements."""
    try:
        uid = int(image.session_uid)
        return uid if uid > 0 else None
    except Exception:
        return None


def _resolve_pending_image(bpy, name: str, session_uid: int):
    """Resolve only the original datablock, abandoning renames/replacements."""
    try:
        image = bpy.data.images.get(name)
    except Exception:
        return None
    if not _image_is_valid(image) or _image_session_uid(image) != session_uid:
        return None
    return image


def _retry_callback(name: str, entry: dict):
    def _retry():
        # A timer callback must never raise: an exception here is reported every
        # 0.25s and can leave the timer registered forever.
        try:
            # An old timer must not consume a newer request with the same name,
            # even if unregister/load/requeue happened to reuse the same UID.
            if _PENDING.get(name) is not entry:
                return None
            import bpy

            image = _resolve_pending_image(bpy, name, entry["session_uid"])
            if image is None:
                # Removed by someone else, or the file this image belonged to was
                # closed. Nothing left to free.
                _PENDING.pop(name, None)
                return None

            if image.users != 0 or image.use_fake_user:
                _PENDING.pop(name, None)
                return None

            if _preview_job_running(bpy):
                if time.monotonic() >= entry.get("deadline", 0.0):
                    # Give up and leave the orphan (0 users) for Blender's purge.
                    _PENDING.pop(name, None)
                    return None
                return RETRY_INTERVAL_SECONDS
            _PENDING.pop(name, None)
            _remove_now(image)
            return None
        except Exception:
            if _PENDING.get(name) is entry:
                _PENDING.pop(name, None)
            return None

    return _retry


def remove_image_when_safe(image, *, reason: str = "", max_wait_seconds: float = 60.0) -> bool:
    """Remove ``image`` now, or defer until no preview/render job is running.

    Returns True when the datablock was removed during this call, False when it
    was invalid/in use, when removal failed, or when removal was deferred.
    """
    if not _image_is_valid(image):
        return False

    try:
        import bpy
    except Exception:
        return False

    name = image.name
    try:
        # Existing fake users on scratch images can be cleared, but real users
        # mean the caller has not finished unlinking the image.
        if image.users > int(image.use_fake_user):
            return False
    except Exception:
        return False

    if not _preview_job_running(bpy):
        _PENDING.pop(name, None)
        _defuse(image)
        return _remove_now(image)

    session_uid = _image_session_uid(image)
    entry = _PENDING.get(name)
    if entry is not None and entry["session_uid"] == session_uid:
        # Do not clear a fake user re-enabled while this request was waiting.
        return False

    # A job is in flight: do not free the datablock under it.
    _defuse(image)

    if session_uid is None:
        # Without stable identity, leave the orphan for Blender's purge.
        return False

    timers = getattr(getattr(bpy, "app", None), "timers", None)
    register = getattr(timers, "register", None)
    if not callable(register):
        # A timer failure does not make freeing a busy GPU image safe.
        return False

    entry = {
        "session_uid": session_uid,
        "reason": reason,
        "deadline": time.monotonic() + max(0.0, float(max_wait_seconds)),
    }
    _PENDING[name] = entry
    try:
        register(_retry_callback(name, entry), first_interval=RETRY_INTERVAL_SECONDS)
    except Exception:
        _PENDING.pop(name, None)
        return False
    return False


def remove_images_when_safe(images, *, reason: str = "", max_wait_seconds: float = 60.0) -> int:
    """Convenience wrapper: returns how many datablocks were removed immediately."""
    removed = 0
    for image in images or ():
        if remove_image_when_safe(image, reason=reason, max_wait_seconds=max_wait_seconds):
            removed += 1
    return removed


def pending_count() -> int:
    """How many images are waiting on a preview job to finish."""
    return len(_PENDING)


def pending_names() -> tuple[str, ...]:
    return tuple(_PENDING)


def _reset_pending_for_tests() -> None:
    _PENDING.clear()


# ---------------------------------------------------------------- registration

#: The load_post callback actually appended to the handler list. `@persistent` is
#: applied at register time because `bpy` is not importable when this module is.
_LOAD_POST_HANDLER = None


def _load_post(_filepath=None) -> None:
    # Blender frees the app timers and every Image datablock of the outgoing file
    # when a new one is loaded. A queue entry that survived that would block the
    # same scratch name from ever being queued again this session.
    _PENDING.clear()


def register() -> None:
    global _LOAD_POST_HANDLER
    _PENDING.clear()
    try:
        import bpy

        handlers = bpy.app.handlers
        persistent = getattr(handlers, "persistent", None)
        _LOAD_POST_HANDLER = persistent(_load_post) if callable(persistent) else _load_post
        load_post = getattr(handlers, "load_post", None)
        if load_post is not None and _LOAD_POST_HANDLER not in load_post:
            load_post.append(_LOAD_POST_HANDLER)
    except Exception:
        _LOAD_POST_HANDLER = None


def unregister() -> None:
    global _LOAD_POST_HANDLER
    try:
        import bpy

        load_post = getattr(getattr(getattr(bpy, "app", None), "handlers", None), "load_post", None)
        if load_post is not None and _LOAD_POST_HANDLER is not None and _LOAD_POST_HANDLER in load_post:
            load_post.remove(_LOAD_POST_HANDLER)
    except Exception:
        pass
    _LOAD_POST_HANDLER = None
    _PENDING.clear()
