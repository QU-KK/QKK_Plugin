# SPDX-License-Identifier: GPL-2.0-or-later
"""Blender-to-Unreal export bundle generation and remote execution bridge."""

import importlib.util
import hashlib
import os
import re
import shutil
import time


EDGEDECAL_UNREAL_SCHEMA_VERSION = 1
EDGEDECAL_UNREAL_SOURCE_SLOT = "EDG_SOURCE"
EDGEDECAL_UNREAL_ROLE_PARAMETERS = {
    "base_color": "",
    "normal": "NormalTexture",
    "opacity": "Opacity",
    "roughness": "",
    "metallic": "",
}


def edge_decal_unreal_safe_name(value, fallback="Asset"):
    value = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not value:
        value = fallback
    if value[0].isdigit():
        value = f"_{value}"
    return value[:96]


def edge_decal_unreal_asset_path(value, fallback="/Game/EdgeDecals"):
    path = str(value or "").strip().replace("\\", "/")
    if not path:
        path = fallback
    if not path.startswith("/Game"):
        path = f"/Game/{path.lstrip('/')}"
    return path.rstrip("/")


def edge_decal_unreal_default_export_root():
    if bpy.data.filepath:
        return os.path.join(os.path.dirname(bpy.data.filepath), "UnrealExports")
    return os.path.join(bpy.app.tempdir, "EdgeDecalUnrealExports")


def edge_decal_unreal_export_root(settings, create=False):
    configured = str(getattr(settings, "export_directory", "") or "").strip()
    root = (
        os.path.realpath(bpy.path.abspath(configured))
        if configured
        else edge_decal_unreal_default_export_root()
    )
    if create:
        os.makedirs(root, exist_ok=True)
    return root


def edge_decal_unreal_engine_candidates():
    if os.name != "nt":
        return []
    roots = (
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Epic Games"),
        r"C:\Epic Games",
        r"D:\Program Files\Epic Games",
        r"D:\Epic Games",
    )
    candidates = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for entry in os.scandir(root):
            if entry.is_dir() and entry.name.startswith("UE_"):
                candidates.append(entry.path)
    return sorted(candidates, reverse=True)


def edge_decal_unreal_resolve_engine_root(settings):
    configured = str(getattr(settings, "engine_root", "") or "").strip()
    if configured:
        configured = os.path.realpath(bpy.path.abspath(configured))
        if os.path.basename(configured).lower().endswith(".exe"):
            marker = os.path.join("Engine", "Binaries", "Win64")
            normalized = configured.replace("/", os.sep).replace("\\", os.sep)
            index = normalized.lower().rfind(marker.lower())
            if index >= 0:
                configured = normalized[:index].rstrip("\\/")
        return configured
    candidates = edge_decal_unreal_engine_candidates()
    return candidates[0] if candidates else ""


def edge_decal_unreal_remote_module_path(settings):
    root = edge_decal_unreal_resolve_engine_root(settings)
    if not root:
        return ""
    return os.path.join(
        root,
        "Engine",
        "Plugins",
        "Experimental",
        "PythonScriptPlugin",
        "Content",
        "Python",
        "remote_execution.py",
    )


def _edge_decal_unreal_role_parameter(settings, role):
    property_name = f"{role}_parameter"
    return str(
        getattr(
            settings,
            property_name,
            EDGEDECAL_UNREAL_ROLE_PARAMETERS.get(role, role),
        )
        or ""
    ).strip()


def _edge_decal_unreal_downstream_roles(node_tree, start_node):
    roles = set()
    queue = [(start_node, 0)]
    visited = set()
    while queue:
        node, depth = queue.pop(0)
        if node in visited or depth > 12:
            continue
        visited.add(node)
        for output in getattr(node, "outputs", ()):
            for link in output.links:
                target = link.to_node
                socket_name = str(getattr(link.to_socket, "name", "")).lower()
                target_type = str(getattr(target, "type", ""))
                if target_type == "NORMAL_MAP" or socket_name == "normal":
                    roles.add("normal")
                elif target_type == "BSDF_PRINCIPLED":
                    if socket_name in {"base color", "base_color"}:
                        roles.add("base_color")
                    elif socket_name == "alpha":
                        roles.add("opacity")
                    elif socket_name == "roughness":
                        roles.add("roughness")
                    elif socket_name == "metallic":
                        roles.add("metallic")
                queue.append((target, depth + 1))
    return roles


def _edge_decal_unreal_role_from_tokens(image, node):
    tokens = " ".join(
        (
            str(getattr(image, "name", "")),
            str(getattr(image, "filepath", "")),
            str(getattr(node, "name", "")),
            str(getattr(node, "label", "")),
        )
    ).lower()
    if any(token in tokens for token in ("normal", "_nrm", "_nor")):
        return "normal"
    if any(token in tokens for token in ("opacity", "alpha", "mask")):
        return "opacity"
    if any(token in tokens for token in ("basecolor", "base_color", "albedo", "diffuse")):
        return "base_color"
    if "rough" in tokens:
        return "roughness"
    if any(token in tokens for token in ("metallic", "metalness")):
        return "metallic"
    return ""


def _edge_decal_unreal_iter_image_nodes(node_tree, visited=None):
    if node_tree is None:
        return
    visited = visited if visited is not None else set()
    pointer = node_tree.as_pointer()
    if pointer in visited:
        return
    visited.add(pointer)
    for node in node_tree.nodes:
        if node.type == "TEX_IMAGE" and getattr(node, "image", None) is not None:
            yield node_tree, node
        nested_tree = getattr(node, "node_tree", None)
        if nested_tree is not None:
            yield from _edge_decal_unreal_iter_image_nodes(nested_tree, visited)


def edge_decal_unreal_material_textures(material):
    """Return one best image per Unreal texture role for a Blender material."""
    if material is None or not material.use_nodes or material.node_tree is None:
        return {}
    resolved = {}
    unclassified = []
    for node_tree, node in _edge_decal_unreal_iter_image_nodes(material.node_tree):
        image = node.image
        roles = _edge_decal_unreal_downstream_roles(node_tree, node)
        if not roles:
            token_role = _edge_decal_unreal_role_from_tokens(image, node)
            if token_role:
                roles.add(token_role)
        if not roles:
            unclassified.append(image)
        for role in sorted(roles):
            resolved.setdefault(role, image)
    if len(unclassified) == 1 and "base_color" not in resolved:
        resolved["base_color"] = unclassified[0]
    return resolved


def _edge_decal_unreal_image_source_path(image):
    if image is None:
        return ""
    try:
        path = image.filepath_from_user()
    except Exception:
        path = bpy.path.abspath(str(getattr(image, "filepath", "") or ""))
    return os.path.realpath(path) if path else ""


def _edge_decal_unreal_image_extension(image, source_path):
    extension = os.path.splitext(source_path)[1].lower()
    if extension in {".bmp", ".exr", ".hdr", ".jpeg", ".jpg", ".png", ".tga", ".tif", ".tiff"}:
        return extension
    file_format = str(getattr(image, "file_format", "PNG") or "PNG").lower()
    return {
        "jpeg": ".jpg",
        "targa": ".tga",
        "targa_raw": ".tga",
        "tiff": ".tif",
        "open_exr": ".exr",
        "hdr": ".hdr",
    }.get(file_format, ".png")


def _edge_decal_unreal_export_image(image, role, directory, stem):
    source_path = _edge_decal_unreal_image_source_path(image)
    extension = _edge_decal_unreal_image_extension(image, source_path)
    filename = f"T_{edge_decal_unreal_safe_name(stem)}_{edge_decal_unreal_safe_name(role)}{extension}"
    destination = os.path.join(directory, filename)
    packed = getattr(image, "packed_file", None)
    if packed is not None:
        with open(destination, "wb") as handle:
            handle.write(bytes(packed.data))
    elif source_path and os.path.isfile(source_path):
        if os.path.realpath(source_path) != os.path.realpath(destination):
            shutil.copy2(source_path, destination)
    else:
        try:
            image.save_render(destination)
        except Exception as error:
            raise RuntimeError(
                f'Texture "{image.name}" is neither packed nor available on disk: {error}'
            ) from error
    return destination


def _edge_decal_unreal_material_for_layer(layer_obj):
    data = getattr(layer_obj, "edge_decal_object_settings", None)
    material = getattr(data, "decal_material", None) if data is not None else None
    if material is None and layer_obj.data is not None and layer_obj.data.materials:
        material = layer_obj.data.materials[0]
    return material


def _edge_decal_unreal_shared_material_for_layer(layer_obj, material, settings):
    """Return the common template when it exports the same texture inputs."""
    if material is None:
        return None
    data = getattr(layer_obj, "edge_decal_object_settings", None)
    template = (
        getattr(data, "decal_template_material", None)
        if data is not None
        else None
    )
    template = root_decal_template_material(template or material)
    if template is None or template == material:
        return material

    def export_texture_identity(candidate):
        return tuple(
            sorted(
                (
                    role,
                    image.as_pointer(),
                    _edge_decal_unreal_role_parameter(settings, role),
                )
                for role, image in edge_decal_unreal_material_textures(
                    candidate
                ).items()
                if _edge_decal_unreal_role_parameter(settings, role)
            )
        )

    if export_texture_identity(material) == export_texture_identity(template):
        return template
    return material


def _edge_decal_unreal_file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _edge_decal_unreal_build_material_manifest(layers, settings, bundle_directory):
    texture_directory = os.path.join(bundle_directory, "Textures")
    os.makedirs(texture_directory, exist_ok=True)
    records = []
    layer_slots = {}
    material_records = {}
    for layer in layers:
        material = _edge_decal_unreal_material_for_layer(layer)
        shared_material = _edge_decal_unreal_shared_material_for_layer(
            layer,
            material,
            settings,
        )
        material_identity = (
            shared_material.as_pointer() if shared_material is not None else 0
        )
        if material_identity not in material_records:
            source_name = (
                shared_material.name
                if shared_material is not None
                else "EdgeDecal"
            )
            key = edge_decal_unreal_safe_name(source_name, "EdgeDecal")
            used_keys = {record["key"] for record in records}
            base_key = key
            suffix = 2
            while key in used_keys:
                key = f"{base_key}_{suffix}"
                suffix += 1
            textures = []
            for role, image in edge_decal_unreal_material_textures(material).items():
                parameter = _edge_decal_unreal_role_parameter(settings, role)
                if not parameter:
                    continue
                exported = _edge_decal_unreal_export_image(
                    image,
                    role,
                    texture_directory,
                    key,
                )
                textures.append(
                    {
                        "role": role,
                        "parameter": parameter,
                        "file": exported,
                        "source_image": image.name,
                        "content_hash": _edge_decal_unreal_file_hash(exported),
                    }
                )
            signature_payload = {
                "source_material": source_name,
                "textures": [
                    {
                        "role": texture["role"],
                        "parameter": texture["parameter"],
                        "content_hash": texture["content_hash"],
                    }
                    for texture in textures
                ],
            }
            record = {
                "key": key,
                "source_material": source_name,
                "slot": f"EDG_DECAL_{key}",
                "instance_name": f"MI_{key}",
                "textures": textures,
                "asset_signature": hashlib.sha256(
                    json.dumps(
                        signature_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            }
            material_records[material_identity] = record
            records.append(record)
        layer_slots[layer.as_pointer()] = material_records[material_identity]["slot"]
    return records, layer_slots


def _edge_decal_unreal_placeholder_material(name):
    material = bpy.data.materials.new(name=name)
    material.diffuse_color = (0.18, 0.18, 0.18, 1.0)
    return material


def _edge_decal_unreal_evaluated_duplicate(
    source_obj,
    name,
    placeholder,
    collection,
    depsgraph,
    export_space,
):
    evaluated = source_obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(
        evaluated,
        preserve_all_data_layers=True,
        depsgraph=depsgraph,
    )
    duplicate = bpy.data.objects.new(name, mesh)
    duplicate.matrix_world = export_space @ source_obj.matrix_world
    collection.objects.link(duplicate)
    if placeholder is not None:
        mesh.materials.clear()
        mesh.materials.append(placeholder)
        for polygon in mesh.polygons:
            polygon.material_index = 0
    return duplicate


def _edge_decal_unreal_export_fbx(filepath, objects, context):
    if not hasattr(bpy.ops.export_scene, "fbx"):
        raise RuntimeError("Blender's FBX exporter is unavailable.")
    for obj in context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.select_set(True)
    context.view_layer.objects.active = objects[0]
    result = bpy.ops.export_scene.fbx(
        filepath=filepath,
        check_existing=False,
        use_selection=True,
        object_types={"MESH"},
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y",
        axis_up="Z",
        use_space_transform=True,
        bake_space_transform=False,
        use_mesh_modifiers=False,
        mesh_smooth_type="FACE",
        use_tspace=True,
        add_leaf_bones=False,
        path_mode="AUTO",
        embed_textures=False,
        bake_anim=False,
    )
    if "FINISHED" not in result or not os.path.isfile(filepath):
        raise RuntimeError(f"FBX export failed: {filepath}")


def edge_decal_export_combined_fbx(context, source_obj, layers, directory):
    """Export one evaluated FBX mesh containing the source and all decals."""
    directory = os.path.realpath(bpy.path.abspath(str(directory or "").strip()))
    if not directory:
        raise RuntimeError("Choose a mesh export folder.")
    os.makedirs(directory, exist_ok=True)
    source_key = edge_decal_unreal_safe_name(source_obj.name, "EdgeDecalMesh")
    filepath = os.path.join(directory, f"{source_key}.fbx")

    previous_mode = context.mode
    previous_active = context.view_layer.objects.active
    previous_selection = list(context.selected_objects)
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    temporary_collection = bpy.data.collections.new("EDG_MeshExport_Temp")
    context.scene.collection.children.link(temporary_collection)
    duplicate_names = []
    temporary_mesh_names = []
    try:
        source_location, source_rotation, _source_scale = source_obj.matrix_world.decompose()
        source_anchor = Matrix.LocRotScale(
            source_location,
            source_rotation,
            Vector((1.0, 1.0, 1.0)),
        )
        export_space = source_anchor.inverted_safe()
        depsgraph = context.evaluated_depsgraph_get()
        combined = _edge_decal_unreal_evaluated_duplicate(
            source_obj,
            f"{source_key}_Combined",
            None,
            temporary_collection,
            depsgraph,
            export_space,
        )
        duplicates = [combined]
        for index, layer in enumerate(layers, start=1):
            duplicates.append(
                _edge_decal_unreal_evaluated_duplicate(
                    layer,
                    f"{source_key}_Decal_{index:02d}",
                    None,
                    temporary_collection,
                    depsgraph,
                    export_space,
                )
            )
        duplicate_names = [obj.name for obj in duplicates]
        temporary_mesh_names = [obj.data.name for obj in duplicates]

        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in duplicates:
            obj.select_set(True)
        context.view_layer.objects.active = combined
        if len(duplicates) > 1:
            result = bpy.ops.object.join()
            if "FINISHED" not in result:
                raise RuntimeError("Could not combine the source and decal meshes.")
        _edge_decal_unreal_export_fbx(filepath, [combined], context)
    finally:
        for name in duplicate_names:
            duplicate = bpy.data.objects.get(name)
            if duplicate is not None:
                bpy.data.objects.remove(duplicate, do_unlink=True)
        for name in temporary_mesh_names:
            mesh = bpy.data.meshes.get(name)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        if temporary_collection.name in bpy.data.collections:
            bpy.data.collections.remove(temporary_collection)
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in previous_selection:
            if obj.name in bpy.data.objects and obj.name in context.view_layer.objects:
                obj.select_set(True)
        if (
            previous_active is not None
            and previous_active.name in bpy.data.objects
            and previous_active.name in context.view_layer.objects
        ):
            context.view_layer.objects.active = previous_active
        if previous_mode == "EDIT_MESH" and previous_active is not None:
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except Exception:
                pass
    return filepath


def edge_decal_unreal_export_bundle(context, source_obj, layers, settings):
    source_key = edge_decal_unreal_safe_name(source_obj.name, "EdgeDecalAsset")
    export_root = edge_decal_unreal_export_root(settings, create=True)
    bundle_directory = os.path.join(export_root, source_key)
    os.makedirs(bundle_directory, exist_ok=True)
    materials, layer_slots = _edge_decal_unreal_build_material_manifest(
        layers,
        settings,
        bundle_directory,
    )

    previous_mode = context.mode
    previous_active = context.view_layer.objects.active
    previous_selection = list(context.selected_objects)
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    temporary_collection = bpy.data.collections.new("EDG_UnrealExport_Temp")
    context.scene.collection.children.link(temporary_collection)
    placeholder_materials = {}
    duplicates = []
    mesh_records = []
    try:
        source_location, source_rotation, _source_scale = source_obj.matrix_world.decompose()
        source_anchor = Matrix.LocRotScale(
            source_location,
            source_rotation,
            Vector((1.0, 1.0, 1.0)),
        )
        export_space = source_anchor.inverted_safe()
        source_placeholder = _edge_decal_unreal_placeholder_material(
            EDGEDECAL_UNREAL_SOURCE_SLOT
        )
        placeholder_materials[EDGEDECAL_UNREAL_SOURCE_SLOT] = source_placeholder
        source_duplicate = _edge_decal_unreal_evaluated_duplicate(
            source_obj,
            f"SM_{source_key}_Source",
            source_placeholder,
            temporary_collection,
            context.evaluated_depsgraph_get(),
            export_space,
        )
        duplicates.append(source_duplicate)

        decal_duplicates = []
        for index, layer in enumerate(layers, start=1):
            slot_name = layer_slots[layer.as_pointer()]
            placeholder = placeholder_materials.get(slot_name)
            if placeholder is None:
                placeholder = _edge_decal_unreal_placeholder_material(slot_name)
                placeholder_materials[slot_name] = placeholder
            duplicate = _edge_decal_unreal_evaluated_duplicate(
                layer,
                f"SM_{source_key}_Decal_{index:02d}",
                placeholder,
                temporary_collection,
                context.evaluated_depsgraph_get(),
                export_space,
            )
            decal_duplicates.append(duplicate)
            duplicates.append(duplicate)

        if settings.nanite_workflow:
            source_fbx = os.path.join(bundle_directory, f"SM_{source_key}_Source.fbx")
            decal_fbx = os.path.join(bundle_directory, f"SM_{source_key}_Decal.fbx")
            _edge_decal_unreal_export_fbx(source_fbx, [source_duplicate], context)
            _edge_decal_unreal_export_fbx(decal_fbx, decal_duplicates, context)
            mesh_records.extend(
                (
                    {
                        "role": "source",
                        "file": source_fbx,
                        "asset_name": f"SM_{source_key}_Source",
                        "combine_meshes": True,
                        "nanite": True,
                    },
                    {
                        "role": "decal",
                        "file": decal_fbx,
                        "asset_name": f"SM_{source_key}_Decal",
                        "combine_meshes": True,
                        "nanite": False,
                    },
                )
            )
        else:
            combined_fbx = os.path.join(bundle_directory, f"SM_{source_key}.fbx")
            _edge_decal_unreal_export_fbx(
                combined_fbx,
                [source_duplicate] + decal_duplicates,
                context,
            )
            mesh_records.append(
                {
                    "role": "combined",
                    "file": combined_fbx,
                    "asset_name": f"SM_{source_key}",
                    "combine_meshes": True,
                    "nanite": False,
                }
            )
    finally:
        for duplicate in duplicates:
            mesh = duplicate.data
            bpy.data.objects.remove(duplicate, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        if temporary_collection.name in bpy.data.collections:
            bpy.data.collections.remove(temporary_collection)
        for material in placeholder_materials.values():
            if material.users == 0:
                bpy.data.materials.remove(material)
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in previous_selection:
            if obj.name in bpy.data.objects and obj.name in context.view_layer.objects:
                obj.select_set(True)
        if (
            previous_active is not None
            and previous_active.name in bpy.data.objects
            and previous_active.name in context.view_layer.objects
        ):
            context.view_layer.objects.active = previous_active
        if previous_mode == "EDIT_MESH" and previous_active is not None:
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except Exception:
                pass

    manifest = {
        "schema_version": EDGEDECAL_UNREAL_SCHEMA_VERSION,
        "generator": "Edge Decal Generator",
        "source_name": source_obj.name,
        "asset_key": source_key,
        "workflow": "nanite_blueprint" if settings.nanite_workflow else "combined_mesh",
        "destination_path": edge_decal_unreal_asset_path(settings.destination_path),
        "master_material": str(settings.master_material or "").strip(),
        "create_master_if_missing": bool(settings.create_master_if_missing),
        "blank_material": str(settings.blank_material or "").strip(),
        "blueprint_name": f"BP_{source_key}",
        "meshes": mesh_records,
        "materials": materials,
        "source_slot": EDGEDECAL_UNREAL_SOURCE_SLOT,
        "created_unix": time.time(),
    }
    manifest_path = os.path.join(bundle_directory, "edge_decal_unreal.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return manifest_path, manifest


def edge_decal_unreal_send_manifest(settings, manifest_path):
    remote_module_path = edge_decal_unreal_remote_module_path(settings)
    if not remote_module_path or not os.path.isfile(remote_module_path):
        raise RuntimeError(
            "Could not find Unreal's remote_execution.py. Set Unreal Engine Root in Advanced."
        )
    importer_path = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "unreal", "edge_decal_unreal_import.py")
    )
    if not os.path.isfile(importer_path):
        raise RuntimeError("The bundled Unreal importer script is missing.")

    module_name = f"edge_decal_remote_execution_{int(time.time() * 1000)}"
    spec = importlib.util.spec_from_file_location(module_name, remote_module_path)
    remote_execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(remote_execution)
    session = remote_execution.RemoteExecution()
    try:
        session.start()
        deadline = time.time() + float(settings.remote_timeout)
        nodes = []
        while time.time() < deadline:
            nodes = list(session.remote_nodes)
            if nodes:
                break
            time.sleep(0.1)
        if not nodes:
            raise RuntimeError(
                "No Unreal Editor remote node found. Enable Python Editor Script Plugin and "
                "Project Settings > Plugins > Python > Enable Remote Execution, then keep "
                "the project open."
            )
        if len(nodes) > 1:
            raise RuntimeError(
                "More than one Unreal Editor remote node was found. Close the other editors and retry."
            )
        session.open_command_connection(nodes[0]["node_id"])
        command = (
            "import runpy\n"
            f"runpy.run_path({importer_path!r}, "
            f"init_globals={{'EDGE_DECAL_MANIFEST': {os.path.realpath(manifest_path)!r}}})"
        )
        result = session.run_command(
            command,
            unattended=True,
            exec_mode=remote_execution.MODE_EXEC_FILE,
            raise_on_failure=False,
        )
        if not result.get("success"):
            raise RuntimeError(str(result.get("result") or "Unreal import failed."))
        return result, nodes[0]
    finally:
        session.stop()


class EDGEDECAL_PG_unreal_export_settings(PropertyGroup):
    show_export_category: BoolProperty(
        name="Export",
        default=True,
        description="Show mesh and engine export controls",
    )
    show_unreal_category: BoolProperty(
        name="Unreal Engine",
        default=True,
        description="Show Send to Unreal settings",
    )
    mesh_export_directory: StringProperty(
        name="Mesh Folder",
        subtype="DIR_PATH",
        default="",
        description="Folder for the combined evaluated FBX mesh",
    )
    nanite_workflow: BoolProperty(
        name="Nanite Workflow",
        default=True,
        description=(
            "Import source and decal separately, enable Nanite only on the source, "
            "and assemble both in an Actor Blueprint"
        ),
    )
    export_directory: StringProperty(
        name="Export Folder",
        subtype="DIR_PATH",
        default="",
        description="Leave empty to use an UnrealExports folder beside the current blend file",
    )
    destination_path: StringProperty(
        name="Unreal Folder",
        default="/Game/EdgeDecals",
        description="Content Browser destination path",
    )
    master_material: StringProperty(
        name="Decal Master",
        default="/Game/EdgeDecals/M_EdgeDecal_Master",
        description="Unreal path where the bundled master is created, or an existing parameterized material",
    )
    create_master_if_missing: BoolProperty(
        name="Create Master if Missing",
        default=True,
        description=(
            "Create the bundled Deferred Decal / Translucent NormalTexture + Opacity "
            "master at Decal Master when that asset does not exist"
        ),
    )
    blank_material: StringProperty(
        name="Source Material",
        default="/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial",
        description="Unreal material assigned to source geometry",
    )
    engine_root: StringProperty(
        name="Unreal Engine Root",
        subtype="DIR_PATH",
        default="",
        description="Leave empty to auto-detect the newest Epic Games Unreal Engine install",
    )
    remote_timeout: FloatProperty(
        name="Discovery Timeout",
        default=3.0,
        min=0.5,
        max=15.0,
        unit="TIME",
    )
    base_color_parameter: StringProperty(name="Base Color Parameter", default="")
    normal_parameter: StringProperty(name="Normal Parameter", default="NormalTexture")
    opacity_parameter: StringProperty(name="Opacity Parameter", default="Opacity")
    roughness_parameter: StringProperty(name="Roughness Parameter", default="")
    metallic_parameter: StringProperty(name="Metallic Parameter", default="")
    show_advanced: BoolProperty(name="Advanced", default=False)
    last_manifest: StringProperty(default="", options={"HIDDEN"})


class EDGEDECAL_OT_send_to_unreal(Operator):
    bl_idname = "object.edge_decal_send_to_unreal"
    bl_label = "Send to Unreal"
    bl_description = "Export the active source and its populated decals, then set them up in the open Unreal project"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        source_obj = edge_decal_context_source(context)
        return (
            source_obj is not None
            and source_obj.type == "MESH"
            and bool(populated_decal_layers_for_source(source_obj))
        )

    def execute(self, context):
        settings = context.scene.edge_decal_unreal_export
        source_obj = edge_decal_context_source(context)
        if source_obj is None:
            self.report({"ERROR"}, "Select a source mesh or one of its decal layers.")
            return {"CANCELLED"}
        layers = populated_decal_layers_for_source(source_obj)
        if not layers:
            self.report({"ERROR"}, "The source has no populated decal layers.")
            return {"CANCELLED"}
        if not str(settings.master_material or "").strip():
            self.report({"ERROR"}, "Set the Unreal decal master material path.")
            return {"CANCELLED"}
        try:
            manifest_path, manifest = edge_decal_unreal_export_bundle(
                context,
                source_obj,
                layers,
                settings,
            )
            settings.last_manifest = manifest_path
            _result, node = edge_decal_unreal_send_manifest(settings, manifest_path)
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        workflow = "Nanite Blueprint" if manifest["workflow"] == "nanite_blueprint" else "combined mesh"
        project_name = str(node.get("project_name") or "Unreal")
        self.report({"INFO"}, f"Sent {source_obj.name} as {workflow} to {project_name}.")
        return {"FINISHED"}


class EDGEDECAL_OT_export_combined_mesh(Operator):
    bl_idname = "object.edge_decal_export_combined_mesh"
    bl_label = "Export Mesh"
    bl_description = "Combine the evaluated source and decal layers into one FBX mesh"
    bl_options = {"REGISTER"}

    directory: StringProperty(
        name="Export Folder",
        subtype="DIR_PATH",
        default="",
        options={"SKIP_SAVE"},
    )
    filter_folder: BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return EDGEDECAL_OT_send_to_unreal.poll(context)

    def invoke(self, context, _event):
        settings = context.scene.edge_decal_unreal_export
        configured = str(settings.mesh_export_directory or "").strip()
        if configured:
            self.directory = bpy.path.abspath(configured)
            return self.execute(context)
        if bpy.data.filepath:
            self.directory = os.path.join(os.path.dirname(bpy.data.filepath), "Exports")
        else:
            self.directory = os.path.join(bpy.app.tempdir, "EdgeDecalExports")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        settings = context.scene.edge_decal_unreal_export
        directory = str(self.directory or settings.mesh_export_directory or "").strip()
        if not directory:
            self.report({"ERROR"}, "Choose a mesh export folder.")
            return {"CANCELLED"}
        source_obj = edge_decal_context_source(context)
        layers = populated_decal_layers_for_source(source_obj)
        try:
            filepath = edge_decal_export_combined_fbx(
                context,
                source_obj,
                layers,
                directory,
            )
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        settings.mesh_export_directory = os.path.dirname(filepath)
        self.report({"INFO"}, f"Combined mesh exported: {filepath}")
        return {"FINISHED"}


class EDGEDECAL_OT_export_unreal_bundle(Operator):
    bl_idname = "object.edge_decal_export_unreal_bundle"
    bl_label = "Export Unreal Bundle"
    bl_description = "Export FBX files, textures, and a manifest without contacting Unreal Editor"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return EDGEDECAL_OT_send_to_unreal.poll(context)

    def execute(self, context):
        settings = context.scene.edge_decal_unreal_export
        source_obj = edge_decal_context_source(context)
        layers = populated_decal_layers_for_source(source_obj)
        try:
            manifest_path, _manifest = edge_decal_unreal_export_bundle(
                context,
                source_obj,
                layers,
                settings,
            )
            settings.last_manifest = manifest_path
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Unreal bundle exported: {manifest_path}")
        return {"FINISHED"}


def draw_edge_decal_unreal_export(layout, context, source_obj, layers):
    settings = context.scene.edge_decal_unreal_export
    card = layout.box()
    if not draw_edge_decal_foldout(
        card,
        settings,
        "show_export_category",
        "Export",
        icon="EXPORT",
    ):
        return

    populated = [
        layer
        for layer in layers
        if layer_has_geometry_for_source(layer, source_obj)
    ]
    export_body = card.column(align=True)
    mesh_box = export_body.box()
    mesh_box.prop(settings, "mesh_export_directory")
    mesh_action = mesh_box.column()
    mesh_action.scale_y = 1.3
    mesh_action.enabled = bool(populated)
    mesh_action.operator(
        EDGEDECAL_OT_export_combined_mesh.bl_idname,
        text="Export Mesh",
        icon="EXPORT",
    )

    unreal_card = export_body.box()
    if not draw_edge_decal_foldout(
        unreal_card,
        settings,
        "show_unreal_category",
        "Unreal Engine",
        icon="WORLD",
    ):
        return

    header = unreal_card.row(align=True)
    header.prop(
        settings,
        "nanite_workflow",
        text="Nanite",
        toggle=True,
    )
    body = unreal_card.column(align=True)
    if settings.nanite_workflow:
        body.label(text="Source + decal mesh in an Actor Blueprint", icon="NODETREE")
    else:
        body.label(text="Source + decals in one Static Mesh", icon="MESH_DATA")
    body.prop(settings, "destination_path")
    body.prop(settings, "master_material")
    body.prop(settings, "create_master_if_missing")
    body.prop(settings, "blank_material")

    advanced_header = body.row(align=True)
    advanced_header.prop(
        settings,
        "show_advanced",
        text="Advanced",
        icon="TRIA_DOWN" if settings.show_advanced else "TRIA_RIGHT",
        emboss=False,
    )
    if settings.show_advanced:
        advanced = body.column(align=True)
        advanced.prop(settings, "export_directory")
        advanced.prop(settings, "engine_root")
        advanced.prop(settings, "remote_timeout")
        parameters = advanced.box()
        parameters.label(text="Master Material Texture Parameters")
        parameters.prop(settings, "base_color_parameter")
        parameters.prop(settings, "normal_parameter")
        parameters.prop(settings, "opacity_parameter")
        parameters.prop(settings, "roughness_parameter")
        parameters.prop(settings, "metallic_parameter")

    actions = body.row(align=True)
    actions.enabled = bool(populated)
    send = actions.row(align=True)
    send.scale_y = 1.35
    send.operator(
        EDGEDECAL_OT_send_to_unreal.bl_idname,
        text="Send to Unreal",
        icon="EXPORT",
    )
    actions.operator(
        EDGEDECAL_OT_export_unreal_bundle.bl_idname,
        text="",
        icon="FILE_FOLDER",
    )
    if not populated:
        body.label(text="Generate at least one decal layer first", icon="INFO")
