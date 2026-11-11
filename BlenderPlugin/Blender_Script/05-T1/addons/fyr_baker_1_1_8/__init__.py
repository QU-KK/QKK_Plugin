from __future__ import annotations

bl_info = {
    "name": "Fyr Baker",
    "author": "Fyr Plugins - Marcus 'Glow' Rasmussen",
    "version": (1, 1, 8),
    "blender": (5, 1, 0),
    "location": "Render Properties, 3D View Sidebar, Image Editor Sidebar",
    "description": "Offline bake project workflow with an external backend for Blender 5.1+",
    "category": "Render",
}

try:
    import bpy  # type: ignore
except ImportError:  # pragma: no cover - exercised in unit tests outside Blender
    bpy = None
else:
    # Headless unit tests install small ``bpy`` stand-ins for the individual
    # module under test. They intentionally do not represent a Blender runtime
    # and must not trigger eager import/registration of the entire addon.
    if not getattr(getattr(bpy, "app", None), "version", None):
        bpy = None


if bpy is not None:
    import importlib

    MODULE_IMPORT_ORDER = (
        "constants",
        # Pure lookup for a backend that arrived through the standalone
        # installer. bpy-free; shared by runtime and indexed_geometry.
        "backend_install",
        "workspace",
        "protocol",
        "reprojection_protocol",
        "naming",
        # Texture-export engine halves: pure, depend only on constants/naming.
        "export_tokens",
        "export_templates",
        "export_pack",
        "export_backend_pack",
        # Floater faces (pure; bmesh/numpy imported lazily). Read by cage, export and
        # high_mesh_cache, so it precedes them.
        "floater_faces",
        "low_material_subset",
        "cage",
        "cage_session",
        "tagging",
        "metadata_sync",
        "matching",
        "quality",
        "map_rebuild",
        "validation",
        "registration",
        # Leaf utility (bpy only); imported by export/blender_bake/cycles_projection.
        "image_cleanup",
        "startup_dialogs",
        # Mirrors a few preferences into the user config dir so an update,
        # which rewrites the add-on package, cannot take them with it.
        "persistent_settings",
        # Owns the update-mode vocabulary and the soft link to "updater", which
        # the Superhive archive ships without. Must precede preferences.
        "update_policy",
        "preferences",
        # Arms before anything heavy registers, so a hang during startup is caught too.
        "hang_watchdog",
        "updater",
        "storage_cleanup",
        "uv_snapshot",
        "uv_transfer",
        "properties",
        "project_structure",
        "legacy_cleanup",
        "high_mesh_cache",
        "sidebar_state",
        "sidebar_icons",
        "output_thumbnails",
        # Pure; presents a Normal row as a MATERIAL/NORMAL row (constants only).
        "normal_material_route",
        "uv_seam_optimizer",
        "uv_selection_preview",
        "material_channel_graph",
        "material_graph",
        "material_ir",
        "material_capture_nodes",
        "material_capture_sync",
        "export",
        # Bake-phase dependency detection; reads export/properties/naming, no register().
        "bake_dependencies",
        "external_handoff",
        "blender_bake",
        "material_workflow",
        "dirty_tracker",
        "runtime",
        # Parks high-poly mesh data during a heavy bake; reads runtime's bake state.
        "high_poly_park",
        "preview_materials",
        "heatmap_preview",
        "cage_visualization",
        "overlays",
        # Timer queues of automatic cage fits and Distance offset fits; reset on load.
        "auto_cage_fit_queue",
        "distance_offset_queue",
        "texture_reprojection",
        "udim_images",
        # Paint Offset / Paint Skew brush (numpy core, then the tool); operators call it.
        "paint_brush_core",
        "paint_brush",
        "operators",
        # Reads Outliner moves into bake group slots; the panel requests its sweeps.
        "collection_membership",
        # Mark / Clear / Select Floater in Edit Mode.
        "floater_faces_ops",
        "unhide_shortcut",
        # Reads project/export state via properties + export; must follow them.
        "export_dialog",
        # Output-template editor (preferences tab); reads export_dialog's cache.
        "export_template_editor",
        "ui_utils",
        "ui_map_settings",
        "ui_group_editor",
        "ui_sidebar_viewport",
        "ui_image_editor",
        "bakeability_ui",
        "ui",
    )

    # Single source of truth for registration. Both the reload path
    # (``_safe_unregister_loaded_modules``) and ``register()`` derive from this
    # tuple, so a module can never be registered by one and skipped by the other
    # - the drift that left ``udim_images`` importing fine while its stale-tile
    # cleanup operator was never registered. Order is registration order;
    # unregistration walks it in reverse. Modules without register/unregister
    # are tolerated so a module can gain them independently of this list.
    REGISTER_MODULE_NAMES = (
        "preferences",
        "hang_watchdog",
        "updater",
        "storage_cleanup",
        "properties",
        "legacy_cleanup",
        "high_mesh_cache",
        "sidebar_icons",
        "output_thumbnails",
        "uv_selection_preview",
        "material_capture_nodes",
        "material_capture_sync",
        "image_cleanup",
        "blender_bake",
        "runtime",
        "high_poly_park",
        "preview_materials",
        "heatmap_preview",
        "cage_visualization",
        "overlays",
        # Timer queues of automatic cage fits and Distance offset fits; reset on load.
        "auto_cage_fit_queue",
        "distance_offset_queue",
        "texture_reprojection",
        "udim_images",
        "paint_brush",
        "operators",
        "collection_membership",
        "floater_faces_ops",
        "unhide_shortcut",
        "export_dialog",
        "export_template_editor",
        "bakeability_ui",
        "ui",
    )

    def _loaded_module(name):
        return globals().get(name)


    def _safe_unregister_loaded_modules():
        for name in reversed(REGISTER_MODULE_NAMES):
            module = _loaded_module(name)
            if module is None or not hasattr(module, "unregister"):
                continue
            try:
                module.unregister()
            except Exception:
                pass


    # Modules the Superhive archive is packaged without. Their absence is a
    # supported shape, not a broken install: everything that reads them goes
    # through update_policy, which reports "no updater" instead of raising.
    OPTIONAL_MODULE_NAMES = frozenset({"updater"})

    def _import_or_reload_module(name):
        module = _loaded_module(name)
        if module is not None:
            return importlib.reload(module)
        try:
            module = importlib.import_module(f".{name}", __package__)
        except ImportError:
            if name in OPTIONAL_MODULE_NAMES:
                return None
            raise
        globals()[name] = module
        return module


    def _reload_unlisted_submodules():
        """Reload the submodules MODULE_IMPORT_ORDER does not name.

        importlib.reload(parent) does not re-execute a child, and that tuple lists
        about half of this package: dirty_rules, udim, material_detail, preset_store,
        modifier_signature and every overlay_*/runtime_*/preview_* helper are absent.
        Blender's own disable -> enable therefore kept running the OLD bytecode for
        them, so a fix to a helper simply appeared not to work. (The dev reload script
        purges sys.modules first, which is why it never showed up there.)

        Helpers first, then the listed modules below, because a module that did
        ``from .helper import thing`` keeps the old function object until it is itself
        re-executed.
        """
        import sys

        prefix = f"{__package__}."
        listed = set(MODULE_IMPORT_ORDER)
        for full_name, module in list(sys.modules.items()):
            if not full_name.startswith(prefix) or module is None:
                continue
            short_name = full_name[len(prefix):]
            if "." in short_name or short_name in listed:
                continue
            try:
                importlib.reload(module)
            except Exception:
                # A helper that cannot reload is not worth failing the enable for; the
                # listed modules below still carry the registration.
                pass

    if "ui" in locals():
        _safe_unregister_loaded_modules()
        _reload_unlisted_submodules()
        for module_name in MODULE_IMPORT_ORDER:
            _import_or_reload_module(module_name)
    else:
        for module_name in MODULE_IMPORT_ORDER:
            _import_or_reload_module(module_name)

    REGISTER_MODULES = tuple(
        module
        for module in (_loaded_module(name) for name in REGISTER_MODULE_NAMES)
        if module is not None
    )

    def register():
        for module in reversed(REGISTER_MODULES):
            if not hasattr(module, "unregister"):
                continue
            try:
                module.unregister()
            except Exception:
                pass

        registered_modules = []
        try:
            for module in REGISTER_MODULES:
                if not hasattr(module, "register"):
                    continue
                module.register()
                registered_modules.append(module)
        except BaseException:
            # A module can fail after registering only part of its classes.
            # Unwind it first, then every module completed in this attempt, so
            # Blender never retains callable operators backed by incomplete RNA.
            try:
                module.unregister()
            except Exception:
                pass
            for registered_module in reversed(registered_modules):
                try:
                    registered_module.unregister()
                except Exception:
                    pass
            raise


    def unregister():
        for module in reversed(REGISTER_MODULES):
            if not hasattr(module, "unregister"):
                continue
            try:
                module.unregister()
            except Exception:
                pass

else:  # pragma: no cover - only used outside Blender
    def register():
        raise RuntimeError("Fyr Baker requires Blender's bpy module")


    def unregister():
        return None
