# SPDX-License-Identifier: GPL-2.0-or-later
"""Bundled factory materials, textures, and preset asset discovery."""

import os
import shutil


EDGEDECAL_BUNDLED_ASSET_SCHEMA_VERSION = 1
EDGEDECAL_BUNDLED_ASSET_ROOT_OVERRIDE = ""
EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE = None
EDGEDECAL_BUNDLED_ASSET_MANIFEST_MTIME = None
EDGEDECAL_BUNDLED_ASSET_LAST_WARNINGS = []
EDGEDECAL_USER_ASSET_SCHEMA_VERSION = 1
EDGEDECAL_USER_ASSET_ROOT_OVERRIDE = ""
EDGEDECAL_ADDON_MODULE_NAME = __package__ or __name__.split(".")[0]


def edge_decal_addon_preferences(context=None):
    context = context or bpy.context
    preferences = getattr(context, "preferences", None)
    addons = getattr(preferences, "addons", None)
    if addons is None:
        return None
    addon = addons.get(EDGEDECAL_ADDON_MODULE_NAME)
    return getattr(addon, "preferences", None) if addon is not None else None


def update_edge_decal_user_library_directory(_self, _context):
    invalidate_edge_decal_preset_cache()


def edge_decal_default_user_library_root(create=False):
    return bpy.utils.user_resource(
        "CONFIG",
        path="lazy_edge_decals",
        create=create,
    )


def edge_decal_user_library_root(create=False):
    preferences = edge_decal_addon_preferences()
    configured = str(
        getattr(preferences, "user_library_directory", "") or ""
    ).strip()
    if configured:
        root = os.path.realpath(bpy.path.abspath(configured))
        if create:
            os.makedirs(root, exist_ok=True)
        return root
    return edge_decal_default_user_library_root(create=create)


class EDGEDECAL_AP_preferences(AddonPreferences):
    bl_idname = EDGEDECAL_ADDON_MODULE_NAME

    user_library_directory: StringProperty(
        name="User Preset Library",
        description=(
            "Folder containing user presets, material libraries, and copied "
            "textures; leave empty to use Blender's configuration directory"
        ),
        subtype="DIR_PATH",
        default="",
        update=update_edge_decal_user_library_directory,
    )

    def draw(self, _context):
        layout = self.layout
        layout.prop(self, "user_library_directory")
        layout.label(
            text=f"Active: {edge_decal_user_library_root(create=False)}",
            icon="FILE_FOLDER",
        )
        layout.label(
            text="Changing folders switches libraries; files are not moved automatically.",
            icon="INFO",
        )


def edge_decal_bundled_asset_root():
    override = str(EDGEDECAL_BUNDLED_ASSET_ROOT_OVERRIDE or "").strip()
    if override:
        return os.path.realpath(override)
    return os.path.join(os.path.dirname(__file__), "assets")


def _edge_decal_safe_bundled_path(relative_path):
    """Resolve a manifest path while keeping it inside the asset package."""
    root = os.path.realpath(edge_decal_bundled_asset_root())
    candidate = os.path.realpath(os.path.join(root, str(relative_path or "")))
    try:
        if os.path.commonpath((root, candidate)) != root:
            return ""
    except ValueError:
        return ""
    return candidate


def edge_decal_user_asset_root(create=False):
    override = str(EDGEDECAL_USER_ASSET_ROOT_OVERRIDE or "").strip()
    if override:
        root = os.path.realpath(override)
        if create:
            os.makedirs(root, exist_ok=True)
        return root
    return edge_decal_user_library_root(create=create)


def _edge_decal_legacy_user_asset_root():
    return bpy.utils.user_resource(
        "CONFIG",
        path=os.path.join("lazy_edge_decals", "assets"),
        create=False,
    )


def _edge_decal_safe_user_asset_path(relative_path, create_root=False):
    root = edge_decal_user_asset_root(create=create_root)
    if not root:
        return ""
    root = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root, str(relative_path or "")))
    try:
        if os.path.commonpath((root, candidate)) != root:
            return ""
    except ValueError:
        return ""
    if (
        not create_root
        and not os.path.exists(candidate)
        and not str(EDGEDECAL_USER_ASSET_ROOT_OVERRIDE or "").strip()
        and not str(
            getattr(edge_decal_addon_preferences(), "user_library_directory", "")
            or ""
        ).strip()
    ):
        legacy_root = _edge_decal_legacy_user_asset_root()
        if legacy_root:
            legacy_root = os.path.realpath(legacy_root)
            legacy_candidate = os.path.realpath(
                os.path.join(legacy_root, str(relative_path or ""))
            )
            try:
                if (
                    os.path.commonpath((legacy_root, legacy_candidate))
                    == legacy_root
                    and os.path.exists(legacy_candidate)
                ):
                    return legacy_candidate
            except ValueError:
                pass
    return candidate


def _edge_decal_file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _edge_decal_safe_asset_filename(filename):
    filename = os.path.basename(str(filename or "texture"))
    clean = "".join(
        character
        if character.isalnum() or character in "._-"
        else "_"
        for character in filename
    ).strip("._-")
    return clean[:128] or "texture"


def _edge_decal_external_image_source(image):
    if getattr(image, "packed_file", None) is not None:
        return ""
    if getattr(image, "source", "") != "FILE":
        raise ValueError(
            f"Image '{image.name_full}' must be file-based or packed"
        )
    raw_path = str(getattr(image, "filepath", "") or "")
    if not raw_path:
        raise ValueError(f"Image '{image.name_full}' has no saved file")
    try:
        source_path = bpy.path.abspath(raw_path, library=image.library)
    except TypeError:
        source_path = bpy.path.abspath(raw_path)
    source_path = os.path.realpath(source_path)
    if not os.path.isfile(source_path):
        raise ValueError(
            f"Image '{image.name_full}' file was not found: {source_path}"
        )
    return source_path


def _edge_decal_copy_user_texture(source_path):
    digest = _edge_decal_file_sha256(source_path)
    texture_directory = _edge_decal_safe_user_asset_path(
        "textures",
        create_root=True,
    )
    if not texture_directory:
        raise OSError("Could not resolve the user texture directory")
    os.makedirs(texture_directory, exist_ok=True)

    digest_prefix = f"{digest[:16]}_"
    for existing_name in os.listdir(texture_directory):
        if not existing_name.startswith(digest_prefix):
            continue
        existing_path = os.path.join(texture_directory, existing_name)
        if (
            os.path.isfile(existing_path)
            and _edge_decal_file_sha256(existing_path) == digest
        ):
            return f"textures/{existing_name}"

    filename = f"{digest_prefix}{_edge_decal_safe_asset_filename(source_path)}"
    relative_path = os.path.join("textures", filename)
    target_path = _edge_decal_safe_user_asset_path(relative_path)
    if not target_path:
        raise OSError("Could not resolve the user texture path")
    if not os.path.isfile(target_path):
        temporary_path = f"{target_path}.tmp"
        try:
            shutil.copy2(source_path, temporary_path)
            os.replace(temporary_path, target_path)
        finally:
            if os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError:
                    pass
    return relative_path.replace(os.sep, "/")


def export_edge_decal_user_material_asset(material, preset_identifier):
    """Export one preset's material and content-addressed external images."""
    if material is None:
        return None

    texture_paths = {}
    for image in _edge_decal_material_images(material):
        source_path = _edge_decal_external_image_source(image)
        if not source_path:
            continue
        texture_paths[image.name_full] = _edge_decal_copy_user_texture(
            source_path
        )

    safe_identifier = _edge_decal_safe_asset_filename(preset_identifier)
    library_relative = f"materials/{safe_identifier}.blend"
    library_path = _edge_decal_safe_user_asset_path(
        library_relative,
        create_root=True,
    )
    if not library_path:
        raise OSError("Could not resolve the user material library directory")
    os.makedirs(os.path.dirname(library_path), exist_ok=True)
    temporary_path = f"{library_path}.tmp.blend"
    try:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        bpy.data.libraries.write(
            temporary_path,
            {material},
            fake_user=True,
            compress=True,
        )
        os.replace(temporary_path, library_path)
    finally:
        if os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError:
                pass

    return {
        "schema_version": EDGEDECAL_USER_ASSET_SCHEMA_VERSION,
        "material_name": material.name_full,
        "library": library_relative,
        "textures": texture_paths,
    }


def _edge_decal_user_texture_mapping(image, mappings):
    names = [image.name_full, image.name]
    for name in list(names):
        suffix = name.rsplit(".", 1)[-1]
        if suffix.isdigit():
            names.append(name.rsplit(".", 1)[0])
    for name in names:
        relative = mappings.get(name)
        if relative:
            return _edge_decal_safe_user_asset_path(relative)
    return ""


def rebind_user_material_textures(material, asset_record):
    mappings = asset_record.get("textures", {})
    if not isinstance(mappings, dict):
        mappings = {}
    missing = []
    for image in _edge_decal_material_images(material):
        if getattr(image, "packed_file", None) is not None:
            continue
        path = _edge_decal_user_texture_mapping(image, mappings)
        if not path or not os.path.isfile(path):
            missing.append(image.name_full)
            continue
        image.filepath = path
        image["edge_decal_user_texture"] = True
        try:
            image.reload()
        except RuntimeError:
            missing.append(image.name_full)
    return sorted(set(missing), key=str.casefold)


def ensure_user_edge_decal_material(material_name, asset_record):
    if not isinstance(asset_record, dict):
        return None, []
    if asset_record.get("schema_version") != EDGEDECAL_USER_ASSET_SCHEMA_VERSION:
        return None, []

    existing = bpy.data.materials.get(material_name)
    if existing is not None:
        if existing.get("edge_decal_user_material", False):
            return existing, rebind_user_material_textures(existing, asset_record)
        return existing, []

    library_path = _edge_decal_safe_user_asset_path(asset_record.get("library"))
    if not library_path or not os.path.isfile(library_path):
        return None, []

    loaded_material = None
    try:
        with bpy.data.libraries.load(
            library_path,
            link=False,
            assets_only=False,
        ) as (data_from, data_to):
            if material_name not in data_from.materials:
                return None, []
            data_to.materials = [material_name]
        if data_to.materials:
            loaded_material = data_to.materials[0]
    except (OSError, RuntimeError):
        return None, []

    if loaded_material is None:
        return None, []
    # The material is loaded only when a generated decal needs it.  Do not add
    # a fake user: the scene setting and generated meshes provide real users,
    # while an abandoned/removed material should remain purgeable.
    loaded_material.use_fake_user = False
    loaded_material["edge_decal_user_material"] = True
    loaded_material["edge_decal_user_library"] = os.path.basename(library_path)
    missing = rebind_user_material_textures(loaded_material, asset_record)
    return loaded_material, missing


def remove_edge_decal_user_material_asset(asset_record):
    if not isinstance(asset_record, dict):
        return False
    relative = str(asset_record.get("library", "") or "").replace("\\", "/")
    if not relative.startswith("materials/") or not relative.lower().endswith(".blend"):
        return False
    path = _edge_decal_safe_user_asset_path(relative)
    if not path or not os.path.isfile(path):
        return False
    try:
        os.remove(path)
    except OSError:
        return False
    return True


def prune_edge_decal_user_textures(referenced_relative_paths):
    """Delete only unreferenced, content-addressed textures managed by us."""
    texture_directory = _edge_decal_safe_user_asset_path("textures")
    if not texture_directory or not os.path.isdir(texture_directory):
        return 0

    referenced = set()
    for relative in referenced_relative_paths or ():
        path = _edge_decal_safe_user_asset_path(relative)
        if path:
            referenced.add(os.path.realpath(path))

    removed = 0
    for filename in os.listdir(texture_directory):
        path = os.path.realpath(os.path.join(texture_directory, filename))
        prefix = filename[:16]
        managed = (
            len(filename) > 17
            and filename[16] == "_"
            and all(character in "0123456789abcdef" for character in prefix)
        )
        if not managed or path in referenced or not os.path.isfile(path):
            continue
        try:
            os.remove(path)
        except OSError:
            continue
        removed += 1
    return removed


def invalidate_edge_decal_bundled_asset_cache():
    global EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE
    global EDGEDECAL_BUNDLED_ASSET_MANIFEST_MTIME
    EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE = None
    EDGEDECAL_BUNDLED_ASSET_MANIFEST_MTIME = None


def edge_decal_bundled_asset_manifest():
    global EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE
    global EDGEDECAL_BUNDLED_ASSET_MANIFEST_MTIME

    path = os.path.join(edge_decal_bundled_asset_root(), "manifest.json")
    try:
        modified = os.stat(path).st_mtime_ns
    except OSError:
        EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE = {}
        EDGEDECAL_BUNDLED_ASSET_MANIFEST_MTIME = None
        return {}

    if (
        EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE is not None
        and EDGEDECAL_BUNDLED_ASSET_MANIFEST_MTIME == modified
    ):
        return EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != EDGEDECAL_BUNDLED_ASSET_SCHEMA_VERSION
    ):
        payload = {}

    EDGEDECAL_BUNDLED_ASSET_MANIFEST_CACHE = payload
    EDGEDECAL_BUNDLED_ASSET_MANIFEST_MTIME = modified
    return payload


def edge_decal_factory_preset_directory():
    manifest = edge_decal_bundled_asset_manifest()
    relative = manifest.get("presets_directory", "presets")
    return _edge_decal_safe_bundled_path(relative)


def edge_decal_bundled_material_library_path():
    manifest = edge_decal_bundled_asset_manifest()
    relative = manifest.get(
        "material_library",
        "materials/edge_decal_materials.blend",
    )
    return _edge_decal_safe_bundled_path(relative)


def _edge_decal_texture_file_index():
    root = _edge_decal_safe_bundled_path("textures")
    if not root or not os.path.isdir(root):
        return {}
    index = {}
    for directory, _subdirectories, filenames in os.walk(root):
        for filename in filenames:
            key = filename.casefold()
            index.setdefault(key, os.path.join(directory, filename))
    return index


def _edge_decal_material_images(material):
    images = []
    seen_images = set()
    seen_trees = set()

    def visit_tree(node_tree):
        if node_tree is None or node_tree in seen_trees:
            return
        seen_trees.add(node_tree)
        for node in node_tree.nodes:
            image = getattr(node, "image", None)
            if image is not None and image not in seen_images:
                seen_images.add(image)
                images.append(image)
            child_tree = getattr(node, "node_tree", None)
            if child_tree is not None:
                visit_tree(child_tree)

    visit_tree(getattr(material, "node_tree", None))
    return images


def _edge_decal_manifest_texture_path(image, texture_index):
    manifest = edge_decal_bundled_asset_manifest()
    mappings = manifest.get("textures", {})
    if not isinstance(mappings, dict):
        mappings = {}

    explicit = mappings.get(image.name_full, mappings.get(image.name))
    if explicit:
        candidate = _edge_decal_safe_bundled_path(explicit)
        if candidate and os.path.isfile(candidate):
            return candidate

    current_path = str(getattr(image, "filepath", "") or "")
    basename = os.path.basename(current_path.replace("\\", "/"))
    candidates = [basename, image.name_full, image.name]
    for candidate_name in candidates:
        if not candidate_name:
            continue
        candidate = texture_index.get(candidate_name.casefold())
        if candidate:
            return candidate
        # Blender appends .001-style datablock suffixes when a library was
        # authored alongside another copy of the same image.
        stem, extension = os.path.splitext(candidate_name)
        if extension and stem.rsplit(".", 1)[-1].isdigit():
            unsuffixed = stem.rsplit(".", 1)[0] + extension
            candidate = texture_index.get(unsuffixed.casefold())
            if candidate:
                return candidate
    return ""


def rebind_bundled_material_textures(material):
    """Point every file image used by a factory material into assets/textures."""
    if material is None:
        return []

    texture_index = _edge_decal_texture_file_index()
    missing = []
    for image in _edge_decal_material_images(material):
        if getattr(image, "packed_file", None) is not None:
            continue
        path = _edge_decal_manifest_texture_path(image, texture_index)
        if not path:
            missing.append(image.name_full)
            continue
        image.filepath = path
        image["edge_decal_bundled_texture"] = True
        try:
            image.reload()
        except RuntimeError:
            missing.append(image.name_full)
    return sorted(set(missing), key=str.casefold)


def ensure_bundled_edge_decal_material(material_name):
    """Return a material by name, appending its factory copy when necessary.

    The second return value lists image datablocks that could not be resolved
    inside the bundled texture folder.
    """
    material_name = str(material_name or "").strip()
    if not material_name:
        return None, []

    existing = bpy.data.materials.get(material_name)
    if existing is not None:
        if existing.get("edge_decal_bundled_material", False):
            return existing, rebind_bundled_material_textures(existing)
        return existing, []

    library_path = edge_decal_bundled_material_library_path()
    if not library_path or not os.path.isfile(library_path):
        return None, []

    loaded_material = None
    try:
        with bpy.data.libraries.load(
            library_path,
            link=False,
            assets_only=False,
        ) as (data_from, data_to):
            if material_name not in data_from.materials:
                return None, []
            data_to.materials = [material_name]
        if data_to.materials:
            loaded_material = data_to.materials[0]
    except (OSError, RuntimeError):
        return None, []

    if loaded_material is None:
        return None, []
    # Generated decals and the scene setting keep this material alive.  A fake
    # user would make it persist in saved files after every real use is removed.
    loaded_material.use_fake_user = False
    loaded_material["edge_decal_bundled_material"] = True
    loaded_material["edge_decal_bundled_library"] = os.path.basename(
        library_path
    )
    missing = rebind_bundled_material_textures(loaded_material)
    return loaded_material, missing


def ensure_bundled_edge_decal_uv_pins(scene, material):
    """Insert factory pins only when the scene has no pins for this material."""
    if (
        scene is None
        or material is None
        or not hasattr(scene, "edge_decal_uv_pins")
    ):
        return 0

    definitions = edge_decal_bundled_asset_manifest().get("uv_pins", {})
    if not isinstance(definitions, dict):
        return 0
    material_pins = definitions.get(material.name_full, definitions.get(material.name))
    if not isinstance(material_pins, list) or not material_pins:
        return 0

    existing_entries = [
        (index, pin)
        for index, pin in enumerate(scene.edge_decal_uv_pins)
        if getattr(pin, "material", None) == material
    ]

    # v27.229.14 briefly shipped one obsolete unnamed weld pin. Replace only
    # that exact factory value so old scenes receive the authored four-pin set
    # while every customized or independently created pin set remains intact.
    if (
        material.name == "M_EdgeDecal_Welds_01"
        and len(existing_entries) == 1
    ):
        legacy_index, legacy_pin = existing_entries[0]
        if (
            not str(getattr(legacy_pin, "pin_name", "")).strip()
            and abs(float(legacy_pin.u) - 0.510973096) < 1.0e-6
            and abs(float(legacy_pin.v) - 0.500896811) < 1.0e-6
            and abs(float(legacy_pin.width) - 0.075959682) < 1.0e-6
            and not len(legacy_pin.slice_pins)
        ):
            scene.edge_decal_uv_pins.remove(legacy_index)
            existing_entries = []

    if existing_entries:
        return 0

    added = 0
    for definition in material_pins:
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
