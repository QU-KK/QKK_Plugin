# SPDX-License-Identifier: GPL-2.0-or-later
"""Reusable, versioned Edge Decal presets stored in Blender's user config.

Loaded into the add-on package shared namespace by __init__.py.
"""

import hashlib
import os
import re


EDGEDECAL_PRESET_SCHEMA_VERSION = 1
EDGEDECAL_PRESET_NONE = "__NONE__"
EDGEDECAL_DEFAULT_PRESET_IDENTIFIER = "factory::edge_decal_damage_01"
EDGEDECAL_PRESET_ENUM_ITEMS = []
EDGEDECAL_PRESET_RECORDS_CACHE = None
EDGEDECAL_PRESET_DIRECTORY_MTIME = None
EDGEDECAL_PRESET_SELECTION_APPLYING = False

# Only output and workflow settings belong in a reusable preset. Scene-local
# selection state, interactive scratch values, and UI disclosure state are
# deliberately excluded.
EDGEDECAL_PRESET_PROPERTIES = (
    "face_width",
    "relative_face_width",
    "randomize_face_width",
    "minimum_face_width",
    "maximum_face_width",
    "crevice_removal",
    "crevice_detection_mode",
    "crevice_ao_distance",
    "crevice_ao_samples",
    "remove_short_edges",
    "minimum_edge_length",
    "auto_minimum_edge_length",
    "decal_amount",
    "maximum_decal_length",
    "taper_sliced_ends",
    "slice_taper_length",
    "auto_trim_corner_ends",
    "corner_end_trim_multiplier",
    "auto_width_samples",
    "auto_face_width",
    "auto_width_clearance",
    "clamp_edge_overlaps",
    "overlap_clearance",
    "use_face_loop_slide",
    "surface_offset",
    "miter_limit",
    "auto_edge_angle",
    "auto_follow_edge_loops",
    "use_edge_split",
    "split_angle",
    "add_weld_modifier",
    "add_center_displace_modifier",
    "add_shrinkwrap_modifier",
    "add_subdivision_modifier",
    "add_decimate_modifier",
    "add_bevel_modifier",
    "bevel_edge_center",
    "weld_distance",
    "center_displace_strength",
    "center_bevel_width",
    "center_bevel_segments",
    "center_bevel_profile",
    "bevel_harden_normals",
    "normal_mode",
    "normal_keep_sharp",
    "normal_weight",
    "normal_threshold",
    "bevel_angle",
    "replace_previous",
    "auto_use_uv_pins",
    "fast_geometry_only",
    "auto_unwrap_uvs",
    "generate_second_uv",
    "use_integrated_quadrify",
    "integrated_quadrify_average_shape",
    "integrated_quadrify_even_shape",
    "use_follow_active_quads",
    "uv_scale",
    "set_target_texel_density",
    "target_texel_density",
    "texture_resolution",
    "average_uv_island_scale",
    "align_uvs_horizontally",
    "place_in_quarter_strips",
    "randomize_quarter_strip",
    "randomize_horizontal_offset",
    "horizontal_randomize_amount",
    "seed",
    "uv_strip_padding",
    "use_material",
    "match_source_material",
)


def edge_decal_preset_directory(create=False):
    """Return the per-user preset folder without touching the current blend."""
    root = edge_decal_user_library_root(create=create)
    if not root:
        return ""
    directory = os.path.join(root, "presets")
    if create:
        os.makedirs(directory, exist_ok=True)
    return directory


def _edge_decal_preset_identifier(name):
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-").lower()
    clean = clean[:64] or "preset"
    digest = hashlib.sha256(name.casefold().encode("utf-8")).hexdigest()[:8]
    return f"{clean}-{digest}"


def _edge_decal_read_preset_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Preset root must be a JSON object")
    if payload.get("schema_version") != EDGEDECAL_PRESET_SCHEMA_VERSION:
        raise ValueError("Unsupported preset version")
    if not isinstance(payload.get("name"), str) or not payload["name"].strip():
        raise ValueError("Preset has no name")
    if not isinstance(payload.get("settings"), dict):
        raise ValueError("Preset has no settings")
    return payload


def invalidate_edge_decal_preset_cache():
    global EDGEDECAL_PRESET_ENUM_ITEMS
    global EDGEDECAL_PRESET_RECORDS_CACHE
    global EDGEDECAL_PRESET_DIRECTORY_MTIME
    EDGEDECAL_PRESET_ENUM_ITEMS = []
    EDGEDECAL_PRESET_RECORDS_CACHE = None
    EDGEDECAL_PRESET_DIRECTORY_MTIME = None


def _edge_decal_preset_directory_signature(directory):
    if not directory or not os.path.isdir(directory):
        return ()
    entries = []
    try:
        filenames = sorted(os.listdir(directory), key=str.casefold)
    except OSError:
        return ()
    for filename in filenames:
        if not filename.lower().endswith(".json"):
            continue
        path = os.path.join(directory, filename)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        entries.append((filename.casefold(), stat.st_mtime_ns, stat.st_size))
    return tuple(entries)


def _edge_decal_collect_preset_records(directory, source):
    records = []
    if not directory or not os.path.isdir(directory):
        return records
    try:
        filenames = sorted(os.listdir(directory), key=str.casefold)
    except OSError:
        return records

    factory = source == "factory"
    for filename in filenames:
        if not filename.lower().endswith(".json"):
            continue
        path = os.path.join(directory, filename)
        try:
            payload = _edge_decal_read_preset_file(path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        file_identifier = os.path.splitext(filename)[0]
        records.append({
            "identifier": f"{source}::{file_identifier}",
            "file_identifier": file_identifier,
            "name": payload["name"].strip(),
            "path": path,
            "payload": payload,
            "factory": factory,
        })
    return records


def edge_decal_preset_records():
    global EDGEDECAL_PRESET_RECORDS_CACHE
    global EDGEDECAL_PRESET_DIRECTORY_MTIME
    user_directory = edge_decal_preset_directory(create=False)
    factory_directory = edge_decal_factory_preset_directory()
    directory_mtime = (
        _edge_decal_preset_directory_signature(factory_directory),
        _edge_decal_preset_directory_signature(user_directory),
    )
    if (
        EDGEDECAL_PRESET_RECORDS_CACHE is not None
        and EDGEDECAL_PRESET_DIRECTORY_MTIME == directory_mtime
    ):
        return EDGEDECAL_PRESET_RECORDS_CACHE

    records = _edge_decal_collect_preset_records(
        factory_directory,
        "factory",
    )
    records.extend(_edge_decal_collect_preset_records(user_directory, "user"))
    records.sort(key=lambda record: (
        record["name"].casefold(),
        0 if record["factory"] else 1,
    ))
    EDGEDECAL_PRESET_RECORDS_CACHE = records
    EDGEDECAL_PRESET_DIRECTORY_MTIME = directory_mtime
    return records


def edge_decal_preset_record(identifier):
    if not identifier or identifier == EDGEDECAL_PRESET_NONE:
        return None
    for record in edge_decal_preset_records():
        if record["identifier"] == identifier:
            return record
    # Compatibility with enum values saved before factory/user namespaces were
    # introduced. Prefer the editable user copy when both sources share a stem.
    matches = [
        record for record in edge_decal_preset_records()
        if record["file_identifier"] == identifier
    ]
    for record in reversed(matches):
        if not record["factory"]:
            return record
    if matches:
        return matches[0]
    return None


def edge_decal_preset_items(_self, _context):
    """Dynamic enum callback; retain strings globally for Blender RNA safety."""
    global EDGEDECAL_PRESET_ENUM_ITEMS
    records = edge_decal_preset_records()
    if not records:
        EDGEDECAL_PRESET_ENUM_ITEMS = [(
            EDGEDECAL_PRESET_NONE,
            "No Presets",
            "Save the current settings to create a reusable preset",
            0,
        )]
    else:
        EDGEDECAL_PRESET_ENUM_ITEMS = [
            (
                record["identifier"],
                (
                    f"{record['name']} (Built-in)"
                    if record["factory"]
                    else record["name"]
                ),
                (
                    f"Load the bundled {record['name']} preset"
                    if record["factory"]
                    else f"Load the {record['name']} preset"
                ),
                index,
            )
            for index, record in enumerate(records)
        ]
    return EDGEDECAL_PRESET_ENUM_ITEMS


def update_edge_decal_preset_selection(self, context):
    record = edge_decal_preset_record(self.selected)
    if record is None:
        return

    self.name = record["name"]

    global EDGEDECAL_PRESET_SELECTION_APPLYING
    if EDGEDECAL_PRESET_SELECTION_APPLYING or context is None:
        return

    EDGEDECAL_PRESET_SELECTION_APPLYING = True
    try:
        bpy.ops.object.edge_decal_preset_apply("EXEC_DEFAULT")
    finally:
        EDGEDECAL_PRESET_SELECTION_APPLYING = False


def apply_default_edge_decal_preset(context):
    """Apply the factory Damage preset to a scene with no saved selection."""
    if context is None or getattr(context, "scene", None) is None:
        return False

    scene = context.scene
    preset_ui = getattr(scene, "edge_decal_preset_ui", None)
    settings = getattr(scene, "edge_decal_settings", None)
    if preset_ui is None or settings is None:
        return False

    # A stored selection belongs to the file/user. Only initialize the untouched
    # RNA default so loading an existing project never changes its chosen preset.
    if preset_ui.is_property_set("selected"):
        return False

    record = edge_decal_preset_record(EDGEDECAL_DEFAULT_PRESET_IDENTIFIER)
    if record is None:
        return False

    global EDGEDECAL_PRESET_SELECTION_APPLYING
    previous_applying = EDGEDECAL_PRESET_SELECTION_APPLYING
    EDGEDECAL_PRESET_SELECTION_APPLYING = True
    try:
        preset_ui.selected = record["identifier"]
        preset_ui.name = record["name"]
    finally:
        EDGEDECAL_PRESET_SELECTION_APPLYING = previous_applying

    apply_edge_decal_preset(context, record["payload"])
    return True


class EDGEDECAL_PG_preset_ui(PropertyGroup):
    selected: EnumProperty(
        name="Preset",
        description="Reusable Edge Decal preset",
        items=edge_decal_preset_items,
        update=update_edge_decal_preset_selection,
    )
    name: StringProperty(
        name="Preset Name",
        description="Name used when saving the current settings",
        default="",
        maxlen=128,
    )


def edge_decal_material_uv_pin_payload(scene, material):
    """Serialize the scene pins owned by one preset material."""
    if (
        scene is None
        or material is None
        or not hasattr(scene, "edge_decal_uv_pins")
    ):
        return []

    return [
        {
            "name": str(getattr(pin, "pin_name", "")),
            "u": float(pin.u),
            "v": float(pin.v),
            "width": float(pin.width),
            "slice_pins": [
                float(slice_pin.u)
                for slice_pin in pin.slice_pins
            ],
        }
        for pin in scene.edge_decal_uv_pins
        if getattr(pin, "material", None) == material
    ]


def restore_edge_decal_material_uv_pins(scene, material, definitions):
    """Restore saved material pins without replacing scene customizations."""
    if (
        scene is None
        or material is None
        or not hasattr(scene, "edge_decal_uv_pins")
        or not isinstance(definitions, list)
        or not definitions
    ):
        return 0

    if any(
        getattr(pin, "material", None) == material
        for pin in scene.edge_decal_uv_pins
    ):
        return 0

    added = 0
    for definition in definitions:
        if not isinstance(definition, dict):
            continue
        try:
            u = float(definition.get("u", 0.5))
            v = float(definition.get("v", 0.5))
            width = max(0.0001, float(definition.get("width", 0.25)))
        except (TypeError, ValueError):
            continue

        pin = scene.edge_decal_uv_pins.add()
        pin.material = material
        pin.pin_name = str(definition.get("name", ""))
        pin.u = u
        pin.v = v
        pin.width = width
        for slice_u in definition.get("slice_pins", []) or []:
            try:
                slice_pin = pin.slice_pins.add()
                slice_pin.u = max(0.0, min(1.0, float(slice_u)))
            except (TypeError, ValueError):
                if len(pin.slice_pins):
                    pin.slice_pins.remove(len(pin.slice_pins) - 1)
        added += 1
    return added


def edge_decal_preset_payload(name, settings, scene=None):
    values = {}
    for property_name in EDGEDECAL_PRESET_PROPERTIES:
        if hasattr(settings, property_name):
            value = getattr(settings, property_name)
            if isinstance(value, (bool, int, float, str)):
                values[property_name] = value

    material = getattr(settings, "decal_material", None)
    payload = {
        "schema_version": EDGEDECAL_PRESET_SCHEMA_VERSION,
        "name": name,
        "addon_version": list(EDGEDECAL_ADDON_VERSION),
        "settings": values,
        "material": (
            getattr(material, "name_full", getattr(material, "name", None))
            if material is not None
            else None
        ),
    }
    material_uv_pins = edge_decal_material_uv_pin_payload(
        scene or getattr(bpy.context, "scene", None),
        material,
    )
    if material_uv_pins:
        payload["material_uv_pins"] = material_uv_pins
    return payload


def edge_decal_user_preset_texture_references():
    references = set()
    for record in edge_decal_preset_records():
        if record.get("factory", False):
            continue
        asset = record.get("payload", {}).get("material_asset", {})
        mappings = asset.get("textures", {}) if isinstance(asset, dict) else {}
        if not isinstance(mappings, dict):
            continue
        references.update(
            str(relative)
            for relative in mappings.values()
            if relative
        )
    return references


def save_edge_decal_preset(name, settings, scene=None):
    name = str(name).strip()
    if not name:
        raise ValueError("Enter a preset name")

    directory = edge_decal_preset_directory(create=True)
    if not directory:
        raise OSError("Blender did not provide a user configuration directory")

    existing = next(
        (
            record for record in edge_decal_preset_records()
            if (
                not record["factory"]
                and record["name"].casefold() == name.casefold()
            )
        ),
        None,
    )
    file_identifier = (
        existing["file_identifier"]
        if existing is not None
        else _edge_decal_preset_identifier(name)
    )
    path = os.path.join(directory, f"{file_identifier}.json")
    temporary_path = f"{path}.tmp"
    payload = edge_decal_preset_payload(name, settings, scene=scene)
    material = getattr(settings, "decal_material", None)
    if material is not None:
        payload["material_asset"] = export_edge_decal_user_material_asset(
            material,
            file_identifier,
        )

    try:
        with open(temporary_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass

    invalidate_edge_decal_preset_cache()
    prune_edge_decal_user_textures(
        edge_decal_user_preset_texture_references()
    )
    return f"user::{file_identifier}"


def apply_edge_decal_preset(context, payload):
    """Apply preset values without importing its material asset.

    The selected preset identifier is the durable, string-only reference to an
    unloaded factory or user material.  The material is resolved later, after
    generation has produced geometry that will actually use it.
    """
    settings = context.scene.edge_decal_settings
    values = payload.get("settings", {})
    skipped = []

    global EDGEDECAL_SCENE_SETTINGS_COPYING
    EDGEDECAL_SCENE_SETTINGS_COPYING = True
    try:
        for property_name in EDGEDECAL_PRESET_PROPERTIES:
            if property_name not in values or not hasattr(settings, property_name):
                continue
            try:
                setattr(settings, property_name, values[property_name])
            except (TypeError, ValueError):
                skipped.append(property_name)

        material_name = payload.get("material")
        if material_name:
            # Reuse a material that is already part of this blend, but never
            # append a factory/user library merely because a preset was chosen.
            material = bpy.data.materials.get(material_name)
            settings.decal_material = material
        else:
            settings.decal_material = None

        # Matching source image channels reads UVMap.001. Older presets may
        # enable material matching while explicitly storing Second UV as off;
        # normalize that combination when the preset is applied.
        enable_second_uv_for_material_matching(settings)
    finally:
        EDGEDECAL_SCENE_SETTINGS_COPYING = False

    schedule_decal_live_update(settings, context)
    return skipped


def edge_decal_selected_preset_material(scene):
    """Return ``(record, payload, material_name)`` without loading datablocks."""
    if scene is None:
        return None, None, ""
    preset_ui = getattr(scene, "edge_decal_preset_ui", None)
    if preset_ui is None:
        return None, None, ""
    record = edge_decal_preset_record(getattr(preset_ui, "selected", ""))
    if record is None:
        return None, None, ""
    payload = record.get("payload", {})
    if not isinstance(payload, dict):
        return record, None, ""
    material_name = str(payload.get("material") or "").strip()
    return record, payload, material_name


def edge_decal_pending_preset_material_name(scene, settings=None):
    """Return the selected unloaded material name, or an empty string."""
    if settings is None and scene is not None:
        settings = getattr(scene, "edge_decal_settings", None)
    if settings is None or not getattr(settings, "use_material", True):
        return ""
    if getattr(settings, "decal_material", None) is not None:
        return ""
    _record, _payload, material_name = edge_decal_selected_preset_material(scene)
    return material_name


def ensure_edge_decal_preset_material_for_use(context, settings):
    """Resolve the selected preset material at its first real use.

    Returns ``(material, warnings, expected_name)``.  ``expected_name`` is
    non-empty when a selected preset requested an asset, even if that asset
    could not be loaded.  This lets callers avoid silently substituting the
    generic fallback material.
    """
    global EDGEDECAL_BUNDLED_ASSET_LAST_WARNINGS
    global EDGEDECAL_SCENE_SETTINGS_COPYING

    if context is None or settings is None:
        return None, [], ""
    scene = getattr(context, "scene", None)
    if scene is None or not getattr(settings, "use_material", True):
        return None, [], ""

    record, payload, material_name = edge_decal_selected_preset_material(scene)
    material = getattr(settings, "decal_material", None)
    if not material_name:
        return material, [], ""

    # An explicitly selected in-file material takes precedence when it differs
    # from the preset's deferred material reference.
    if material is not None and material.name_full != material_name:
        return material, [], ""

    material_asset = payload.get("material_asset") if payload else None
    missing_textures = []
    if material is None:
        material = bpy.data.materials.get(material_name)
    if material is not None:
        # Reopened blends may already contain a lazily imported material. Reuse
        # it, while refreshing only assets that this add-on previously marked.
        if material_asset and material.get("edge_decal_user_material", False):
            material, missing_textures = ensure_user_edge_decal_material(
                material_name,
                material_asset,
            )
        elif (
            record is not None
            and record.get("factory", False)
            and material.get("edge_decal_bundled_material", False)
        ):
            material, missing_textures = ensure_bundled_edge_decal_material(
                material_name
            )
    else:
        if material_asset:
            material, missing_textures = ensure_user_edge_decal_material(
                material_name,
                material_asset,
            )
        else:
            material, missing_textures = ensure_bundled_edge_decal_material(
                material_name
            )

    warnings = [
        f"texture '{image_name}'"
        for image_name in missing_textures
    ]
    if material is None:
        warnings.insert(0, f"material '{material_name}'")
    else:
        restore_edge_decal_material_uv_pins(
            scene,
            material,
            payload.get("material_uv_pins") if payload else None,
        )
        if record is not None and record.get("factory", False):
            ensure_bundled_edge_decal_uv_pins(scene, material)

        previous_copying = EDGEDECAL_SCENE_SETTINGS_COPYING
        EDGEDECAL_SCENE_SETTINGS_COPYING = True
        try:
            settings.decal_material = material
        finally:
            EDGEDECAL_SCENE_SETTINGS_COPYING = previous_copying

    EDGEDECAL_BUNDLED_ASSET_LAST_WARNINGS = warnings
    if warnings:
        print("Edge Decal preset assets missing: " + ", ".join(warnings))
    return material, warnings, material_name


def edge_decal_initialize_presets_timer():
    """Initialize preset settings without importing materials or images."""
    apply_default_edge_decal_preset(bpy.context)
    return None


def schedule_edge_decal_preset_initialization():
    if not bpy.app.timers.is_registered(edge_decal_initialize_presets_timer):
        bpy.app.timers.register(
            edge_decal_initialize_presets_timer,
            first_interval=0.0,
        )


@persistent
def edge_decal_initialize_presets_handler(_unused):
    invalidate_edge_decal_bundled_asset_cache()
    invalidate_edge_decal_preset_cache()
    schedule_edge_decal_preset_initialization()


class EDGEDECAL_OT_preset_save(Operator):
    bl_idname = "object.edge_decal_preset_save"
    bl_label = "Save Edge Decal Preset"
    bl_description = (
        "Save the current settings and bundle the assigned material and its "
        "textures for use in any blend file"
    )

    def execute(self, context):
        preset_ui = context.scene.edge_decal_preset_ui
        try:
            identifier = save_edge_decal_preset(
                preset_ui.name,
                context.scene.edge_decal_settings,
                scene=context.scene,
            )
        except (OSError, RuntimeError, ValueError, TypeError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        global EDGEDECAL_PRESET_SELECTION_APPLYING
        EDGEDECAL_PRESET_SELECTION_APPLYING = True
        try:
            preset_ui.selected = identifier
        finally:
            EDGEDECAL_PRESET_SELECTION_APPLYING = False
        material = context.scene.edge_decal_settings.decal_material
        self.report(
            {"INFO"},
            (
                f"Saved preset and material assets: {preset_ui.name.strip()}"
                if material is not None
                else f"Saved preset: {preset_ui.name.strip()}"
            ),
        )
        return {"FINISHED"}


class EDGEDECAL_OT_preset_apply(Operator):
    bl_idname = "object.edge_decal_preset_apply"
    bl_label = "Apply Edge Decal Preset"
    bl_description = "Apply the selected preset to the current settings"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        preset_ui = getattr(context.scene, "edge_decal_preset_ui", None)
        return (
            preset_ui is not None
            and edge_decal_preset_record(preset_ui.selected) is not None
        )

    def execute(self, context):
        preset_ui = context.scene.edge_decal_preset_ui
        record = edge_decal_preset_record(preset_ui.selected)
        if record is None:
            self.report({"ERROR"}, "Select a valid preset")
            return {"CANCELLED"}

        try:
            payload = _edge_decal_read_preset_file(record["path"])
            skipped = apply_edge_decal_preset(context, payload)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            self.report({"ERROR"}, f"Could not load preset: {error}")
            return {"CANCELLED"}

        if skipped:
            self.report({"WARNING"}, "Skipped: " + ", ".join(skipped))
        else:
            pending_name = edge_decal_pending_preset_material_name(
                context.scene,
                context.scene.edge_decal_settings,
            )
            message = f"Applied preset: {record['name']}"
            if pending_name:
                message += "; material will load on first generation"
            self.report({"INFO"}, message)
        return {"FINISHED"}


class EDGEDECAL_OT_preset_delete(Operator):
    bl_idname = "object.edge_decal_preset_delete"
    bl_label = "Delete Edge Decal Preset"
    bl_description = "Permanently delete the selected reusable preset"

    @classmethod
    def poll(cls, context):
        preset_ui = getattr(context.scene, "edge_decal_preset_ui", None)
        record = (
            edge_decal_preset_record(preset_ui.selected)
            if preset_ui is not None
            else None
        )
        return (
            preset_ui is not None
            and record is not None
            and not record["factory"]
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        preset_ui = context.scene.edge_decal_preset_ui
        record = edge_decal_preset_record(preset_ui.selected)
        if record is None:
            self.report({"ERROR"}, "Select a valid preset")
            return {"CANCELLED"}
        if record["factory"]:
            self.report({"ERROR"}, "Built-in presets cannot be deleted")
            return {"CANCELLED"}

        material_asset = record.get("payload", {}).get("material_asset")

        try:
            os.remove(record["path"])
        except OSError as error:
            self.report({"ERROR"}, f"Could not delete preset: {error}")
            return {"CANCELLED"}

        invalidate_edge_decal_preset_cache()
        remove_edge_decal_user_material_asset(material_asset)
        prune_edge_decal_user_textures(
            edge_decal_user_preset_texture_references()
        )
        remaining = edge_decal_preset_records()
        if remaining:
            preset_ui.selected = remaining[0]["identifier"]
        else:
            preset_ui.selected = EDGEDECAL_PRESET_NONE
            preset_ui.name = ""
        self.report({"INFO"}, f"Deleted preset: {record['name']}")
        return {"FINISHED"}


def draw_edge_decal_presets(layout, context):
    box = layout.box()
    box.label(text="Presets", icon="PRESET")
    preset_ui = context.scene.edge_decal_preset_ui

    choose = box.row(align=True)
    choose.prop(preset_ui, "selected", text="")

    manage = box.row(align=True)
    manage.prop(preset_ui, "name", text="Name")
    manage.operator(
        EDGEDECAL_OT_preset_save.bl_idname,
        text="",
        icon="FILE_TICK",
    )
    manage.operator(
        EDGEDECAL_OT_preset_delete.bl_idname,
        text="",
        icon="TRASH",
    )
