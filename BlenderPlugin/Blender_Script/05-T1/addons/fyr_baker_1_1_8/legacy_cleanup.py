"""One-time cleanup of state left behind by older add-on versions.

Older builds registered the scene settings as ``scene["master_baker_settings"]``
and their Undo-Remove stash pinned role collections with fake users. Files
saved with those builds carry a zombie settings ID-property — an entire
serialized project with preview state and collection pointers — plus orphaned
role collections (some zero-user but still holding the scene's meshes). The
zombie keeps its collections alive through every save, so every new project
created in such a file gets ``.001``-suffixed collection names forever and the
debris accumulates per create/remove cycle.

``purge_legacy_state`` deletes the legacy ID-property and removes addon-tagged
role collections that are no longer linked to any scene nor referenced by any
live project. It runs on every file load and once at register (for the file
that is already open).
"""

from __future__ import annotations

import os

import bpy

from . import constants as _constants
from . import image_cleanup
from . import tagging

# Tolerate the test suite's plain-module bpy mock (no bpy.app package).
_persistent = getattr(getattr(getattr(bpy, "app", None), "handlers", None), "persistent", lambda fn: fn)

_LEGACY_SETTINGS_KEY = "master_baker_settings"
# Default output root written by builds before the FyrBaker rename. Only this
# exact string is migrated — anything else is a deliberate user choice.
_LEGACY_DEFAULT_OUTPUT_ROOT = "//MasterBaker"
_DEFAULT_OUTPUT_ROOT = "//FyrBaker"
# Set on every image datablock the add-on loads for a bake output (see
# runtime._mark_managed_output_image); present on old-session debris too.
_MANAGED_OUTPUT_PATH_KEY = "_master_baker_output_path"


def _live_project_collection_names() -> set[str]:
    keep: set[str] = set()
    for scene in bpy.data.scenes:
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        for project in getattr(settings, "projects", []):
            root = getattr(project, "root_collection", None)
            if root is not None:
                try:
                    keep.add(root.name)
                except ReferenceError:
                    pass
            for group in getattr(project, "groups", []):
                for source in (group, getattr(group, "collections", None)):
                    if source is None:
                        continue
                    for attr in ("group_collection", "low_collection", "high_collection", "cage_collection"):
                        collection = getattr(source, attr, None)
                        if collection is None:
                            continue
                        try:
                            keep.add(collection.name)
                        except ReferenceError:
                            pass
    return keep


_UI_REFERENCER_TYPES = ("Screen", "WindowManager", "WorkSpace")


def _has_non_ui_referencer(image) -> bool:
    """True when any datablock other than UI screens/workspaces references ``image``."""
    try:
        referencers = bpy.data.user_map(subset=[image]).get(image, set())
    except Exception:
        # Unknown is unsafe: keep the image.
        return True
    for referencer in referencers:
        if type(referencer).__name__ not in _UI_REFERENCER_TYPES:
            return True
    return False


def purge_legacy_state() -> tuple[int, int]:
    """Delete legacy settings ID-props and orphaned role collections.

    Returns ``(legacy_props_removed, collections_removed)``.
    """
    props_removed = 0
    for scene in bpy.data.scenes:
        # The zombie exists on both sides: as a plain user ID-property (the old
        # RNA class is gone, so keys() shows it) and in the system ID-property
        # group, where its serialized project still holds collection pointers
        # that keep the leaked role collections alive.
        try:
            if _LEGACY_SETTINGS_KEY in scene.keys():
                del scene[_LEGACY_SETTINGS_KEY]
                props_removed += 1
        except Exception:
            pass
        try:
            system_get = getattr(scene, "bl_system_properties_get", None)
            system_group = system_get() if callable(system_get) else None
            if system_group is not None and _LEGACY_SETTINGS_KEY in system_group.keys():
                del system_group[_LEGACY_SETTINGS_KEY]
                props_removed += 1
        except Exception:
            pass

    keep = _live_project_collection_names()
    linked: set[str] = set()
    for scene in bpy.data.scenes:
        try:
            for collection in scene.collection.children_recursive:
                linked.add(collection.name)
        except Exception:
            pass

    collections_removed = 0
    for collection in list(bpy.data.collections):
        try:
            name = collection.name
        except ReferenceError:
            continue
        if name in keep or name in linked:
            continue
        if getattr(collection, "library", None) is not None or getattr(collection, "override_library", None) is not None:
            continue
        if tagging.read_role_tag(collection) is None:
            continue
        try:
            # A fake user is the artist deliberately shielding this datablock; clearing
            # it first (ID.users counts the fake user) dropped it to 0 and handed it
            # straight to remove(), which also strips the last user from every object
            # inside. Old-session debris never carries one.
            if getattr(collection, "use_fake_user", False):
                continue
            if collection.users == 0:
                bpy.data.collections.remove(collection)
                collections_removed += 1
        except Exception:
            pass

    # Managed output images from earlier sessions squat on the plain datablock
    # names (BakeProject_AO.tga, ...), so every later session's preview/output
    # load lands on a ".001" twin — and multiple datablocks over one rewritten
    # path is what produced intermittently empty image loads in testing. Drop
    # the unused ones; anything still referenced (editor, preview material)
    # stays untouched.
    images_removed = 0
    for image in list(bpy.data.images):
        try:
            if _MANAGED_OUTPUT_PATH_KEY not in image.keys():
                continue
            if getattr(image, "library", None) is not None or getattr(image, "override_library", None) is not None:
                continue
            # Same rule as the collections above: a fake user is the artist shielding
            # this image (the only way a 0-user datablock survives a save, and the only
            # way a packed one keeps its pixels). Clearing it before the users == 0 test
            # deleted exactly the images they had protected, on every file load, with
            # the surrounding except Exception: pass making it silent.
            if getattr(image, "use_fake_user", False):
                continue
            file_path = bpy.path.abspath(image.filepath) if image.filepath else ""
            file_missing = not file_path or not os.path.exists(file_path)
            if image.users == 0:
                # Deferred while a preview render holds it: freeing an image under
                # a live RENDER_PREVIEW job is the EEVEE texture_bind crash.
                if image_cleanup.remove_image_when_safe(image, reason="legacy managed output"):
                    images_removed += 1
                continue
            if not file_missing:
                continue
            # users>0 with only UI referencers (an Image Editor left open on it)
            # renders a broken image when the file is gone, so drop those too.
            # Anything referenced by a material, node tree, or other datablock
            # stays: a moved output folder or an offline drive must never rip the
            # user's textures out of their materials.
            if _has_non_ui_referencer(image):
                continue
            if image_cleanup._preview_job_running(bpy):  # noqa: SLF001
                continue
            bpy.data.images.remove(image)
            images_removed += 1
        except Exception:
            pass

    roots_migrated = 0
    aa_samples_migrated = 0
    for scene in bpy.data.scenes:
        settings = getattr(scene, "fyr_baker_settings", None)
        if settings is None:
            continue
        for project in getattr(settings, "projects", []):
            # Both used to run from panel draw (a CollectionProperty add and an
            # ID-property write mid-layout); file load is the right time.
            try:
                from . import project_structure

                project_structure.ensure_texture_sets_for_legacy_groups(project)
            except Exception:
                pass
            for texture_set in getattr(project, "texture_sets", []) or []:
                try:
                    if not str(texture_set.get("_identity_name", "") or ""):
                        texture_set["_identity_name"] = str(getattr(texture_set, "name", "") or "").strip()
                except Exception:
                    pass
            try:
                if getattr(project, "output_root", "") == _LEGACY_DEFAULT_OUTPUT_ROOT:
                    project.output_root = _DEFAULT_OUTPUT_ROOT
                    roots_migrated += 1
            except Exception:
                pass
            # Pre-samples files carry only the legacy anti_aliasing enum; seed
            # the new aa_samples int field from it so the UI shows the right
            # count. A never-stored IDProperty reads back as None via .get().
            try:
                getter = getattr(project, "get", None)
                stored = getter("aa_samples") if callable(getter) else None
                if stored is None or int(stored or 0) <= 0:
                    project.aa_samples = _constants.anti_aliasing_to_samples(
                        getattr(project, "anti_aliasing", _constants.DEFAULT_ANTI_ALIASING)
                    )
                    aa_samples_migrated += 1
            except Exception:
                pass

    if props_removed or collections_removed or images_removed or roots_migrated or aa_samples_migrated:
        print(
            f"[Fyr Baker] purged legacy state: {props_removed} legacy settings block(s), "
            f"{collections_removed} orphaned role collection(s), "
            f"{images_removed} orphaned output image(s), "
            f"{roots_migrated} legacy output root(s) renamed, "
            f"{aa_samples_migrated} sample-count field(s) migrated"
        )
    return props_removed, collections_removed


@_persistent
def _load_post(_filepath) -> None:
    try:
        purge_legacy_state()
    except Exception:
        pass
    # A paint proxy only ever exists inside one paint session. One found at load time
    # is debris from a crash or from saving mid-session, and would otherwise sit in
    # the scene as an unexplained duplicate of the low meshes.
    try:
        from . import operators

        operators._remove_paint_proxy(bpy.context)
        # Saved mid-session: the overlay toggles the session flipped come back too.
        operators._restore_paint_overlay_flags(bpy.context)
    except Exception:
        pass
    # The Undo Remove stash lives in module state, not in the .blend, so it has to
    # be dropped here or the newly loaded file inherits the previous file's
    # "Undo Remove '<project>'" offer.
    try:
        from . import runtime

        runtime.clear_removed_project_stash()
    except Exception:
        pass


def _initial_purge_once():
    try:
        purge_legacy_state()
    except Exception:
        pass
    return None


def register() -> None:
    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)
    # bpy.data is restricted while add-ons register; run the pass for the
    # already-open file from a one-shot timer once registration completes.
    try:
        bpy.app.timers.register(_initial_purge_once, first_interval=0.1)
    except Exception:
        pass


def unregister() -> None:
    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)
