"""Live Reproject: keep textures attached to their UV islands while UVs are edited.

The feature needs exactly two things: a texture and the UV layout that texture
was made for. When the toggle is switched on, the current output textures and
the current per-corner UVs of the project's low meshes are recorded as the
reference. Every UV edit afterwards re-draws each triangle at its new UV
position while sampling the reference texture at its old UV position, then
dilates the result by the project margin. Geometry, cages, bake settings and the
bake worker play no part: the transfer runs on the GPU inside Blender, so it
also works on maps that were painted or imported rather than baked.

Previews go to a float image shown in the Image Editor and bound into the
preview material; once edits settle, every output image is rewritten and saved.
Everything is resampled from the pristine reference, so repeated edits never
degrade the textures. The restore button puts the reference textures back.

The reference is also written beside its pixel stores as a small manifest
(``reproject_reference_store``), so Restore Textures still works after Blender
was closed and reopened, and switching the toggle on again keeps the original
reference while the textures on disk are still our own transfer of it instead of
recapturing the already-moved pixels.
"""
from __future__ import annotations

import hashlib
import os
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import bpy
try:
    from bpy.app.handlers import persistent
except (ImportError, AttributeError):  # Unit-test bpy stubs are modules, not packages.
    persistent = lambda function: function

from . import rna_buffers
from . import dirty_tracker, export, image_cleanup, preview_materials, properties, runtime, storage_cleanup
from . import reproject_reference_store as reference_store
from .registration import safe_register_class, safe_unregister_class


_QUIET_SECONDS = 0.350
_PREVIEW_INTERVAL = 1.0 / 30.0
_IMAGE_NAME = "Fyr Live Reproject"
# Depsgraph updates caused by our own image and material writes arrive after the
# timer callback returns, so a context manager cannot hide them from the handler.
# A short time window does.
_SELF_WRITE_GRACE_SECONDS = 0.25

_state = {
    "reference": None,
    "generation": 0,
    "pending": False,
    "due": 0.0,
    "last_preview": 0.0,
    "commit_pending": False,
    "commit_queue": [],
    "dirty_since_commit": False,
    "timer": False,
    "previous_images": {},
    "material_target_uuid": "",
    "material_image": None,
    "material_output": None,
    "ignore_until": 0.0,
}


# ---------------------------------------------------------------------------
# Reference capture
# ---------------------------------------------------------------------------

@dataclass
class _ReferenceOutput:
    path: str                      # absolute output file path
    image_name: str                # datablock the output lives in
    object_names: list[str]        # low meshes whose UVs place texels on this image
    map_uuids: set[str]
    width: int
    height: int
    is_float: bool
    store_path: str                # reference pixels on disk (numpy)
    group_names: list[str] = field(default_factory=list)   # every group sharing this image
    map_type: str = ""
    signature: tuple[int, int] | None = None   # (mtime_ns, size) of the file the reference matches


@dataclass
class _Reference:
    project_name: str
    folder: Path
    captured_at: float = 0.0       # time.time() when the outputs were read
    uv_layers: dict[str, str] = field(default_factory=dict)       # object -> UV layer ("" = active)
    loop_uvs: dict[str, object] = field(default_factory=dict)      # object -> float32 (N, 2)
    triangles: dict[str, object] = field(default_factory=dict)     # object -> int32 (T, 3) loop indices
    outputs: list[_ReferenceOutput] = field(default_factory=list)
    layout_paths: dict[str, tuple[str, str]] = field(default_factory=dict)  # object -> (uvs.npy, triangles.npy)


def _token(value: str) -> str:
    return storage_cleanup.reproject_store_token(value)


def _reference_folder(project) -> Path:
    output_root, _ = export.resolve_output_root_path(project)
    return output_root / ".fyr_cache" / _token(project.name) / "live_reproject"


def _active_map_uuid(project) -> str:
    index = properties.resolve_active_index(int(project.active_map_index), len(project.maps))
    if index is None:
        return ""
    return properties.ensure_map_setting_uuid(project.maps[index])


def _low_objects(project):
    return [obj for group in project.groups for slot in group.low_meshes
            if (obj := getattr(slot, "object_ref", None)) is not None and obj.type == "MESH"]


def _group_objects(project, group_name: str):
    for group in getattr(project, "groups", []):
        if str(getattr(group, "name", "")) == group_name:
            return [obj for slot in group.low_meshes
                    if (obj := getattr(slot, "object_ref", None)) is not None and obj.type == "MESH"], group
    return [], None


def _group_uv_layer_name(group) -> str:
    projection = export._group_projection_settings_state(group)
    return str(getattr(projection, "uv_layer_name", "") or "").strip()


def _mesh_layout(obj, depsgraph, layer_name: str):
    """(per-corner UVs float32 (N, 2), loop triangles int32 (T, 3)) of the evaluated mesh.

    Read from a plain copy of the evaluated object, never through edit BMesh
    elements. Touching BMesh elements from Python adds a hidden pointer
    custom-data layer on first access, which reallocates every element block
    under whatever modal operator is running (a UV transform mid-drag): that
    crashed Blender in BM_data_layer_add on 2026-09-06. The plain copy follows
    live Edit Mode changes and tags nothing; the preserve_all_data_layers variant
    returned stale Edit Mode data and is deliberately not used. Returns
    (None, None) when the object has no usable UV layer."""
    import numpy as np
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh()
    try:
        if mesh is None:
            return None, None
        layer = mesh.uv_layers.get(layer_name) if layer_name else mesh.uv_layers.active
        if layer is None:
            return None, None
        count = len(mesh.loops)
        uvs = np.empty(count * 2, dtype=np.float32)
        layer.data.foreach_get("uv", uvs)
        mesh.calc_loop_triangles()
        triangles = rna_buffers.empty_u32_for_rna(len(mesh.loop_triangles) * 3)
        mesh.loop_triangles.foreach_get("loops", triangles)
        triangles = rna_buffers.as_i32(triangles)
        return uvs.reshape(-1, 2), triangles.reshape(-1, 3)
    finally:
        try:
            obj_eval.to_mesh_clear()
        except Exception:
            pass


def _modal_operator_running() -> bool:
    """True while any window runs a modal operator (a transform drag, a box select)."""
    try:
        for window in bpy.context.window_manager.windows:
            if len(getattr(window, "modal_operators", ())) > 0:
                return True
    except Exception:
        pass
    return False


def _find_output_image(path: str):
    """The datablock holding this output file, matched by absolute path.

    Never by name: a scene can hold same-named textures from another output
    folder (an older bake of the same project), and moving those would be wrong."""
    wanted = os.path.normcase(os.path.normpath(path))
    for candidate in bpy.data.images:
        try:
            if candidate.filepath and os.path.normcase(os.path.normpath(bpy.path.abspath(candidate.filepath))) == wanted:
                return candidate
        except Exception:
            continue
    if os.path.isfile(path):
        try:
            return bpy.data.images.load(path, check_existing=True)
        except Exception:
            return None
    return None


def _read_image_pixels(image):
    import numpy as np
    width, height = image.size
    flat = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(flat)
    return flat


def _store_reference_pixels(store_path: str, flat, is_float: bool) -> None:
    import numpy as np
    if is_float:
        np.save(store_path, flat)
    else:
        # Byte images read back as k/255 exactly; store the bytes (4x smaller).
        # True whatever colorspace the image is TAGGED with: Image.pixels on a byte
        # buffer is the raw byte / 255, not a linearised value -- the colorspace
        # transform happens at shading/display time. Measured on 5.1: writing 0.3 to
        # a byte image reads back 77/255 on both Non-Color and sRGB, so nothing here
        # is being quantised twice and this must not be "fixed" into a 4x float store.
        np.save(store_path, np.rint(flat * 255.0).astype(np.uint8))


def _load_reference_pixels(store_path: str):
    import numpy as np
    data = np.load(store_path)
    if data.dtype == np.uint8:
        return data.astype(np.float32) / 255.0
    return data.astype(np.float32, copy=False)


def _capture_reference(project) -> _Reference:
    folder = _reference_folder(project)
    folder.mkdir(parents=True, exist_ok=True)
    reference = _Reference(project_name=str(project.name), folder=folder, captured_at=time.time())
    depsgraph = bpy.context.evaluated_depsgraph_get()

    try:
        output_dir = os.path.normcase(os.path.normpath(str(export.resolved_project_output_dir(project))))
    except Exception:
        output_dir = ""
    by_path: dict[str, _ReferenceOutput] = {}
    stale: list[tuple[str, str]] = []
    # Reference stores are written to a partial file first and only moved onto their
    # final names once the WHOLE capture succeeded. store_path is deterministic per
    # output, so writing in place overwrote the previous reference while the manifest
    # that describes it is written last: a capture that refused half way (a UDIM output,
    # a low with no UV layer) left the manifest describing the old capture while the
    # .npy files already held current - that is, already reprojected - pixels, and a
    # later "Restore Textures" wrote those back as the originals. For a painted or
    # imported map that cannot be rebaked, the originals were simply gone.
    pending_stores: list[tuple[str, str]] = []
    try:
        for item in project.latest_outputs:
            raw = str(getattr(item, "file_path", "") or "")
            if not raw:
                continue
            if properties.output_is_tiled(item):
                raise RuntimeError("UDIM outputs are not supported by Live Reproject yet")
            path = os.path.normpath(bpy.path.abspath(raw))
            if output_dir and not os.path.normcase(path).startswith(output_dir):
                # A record left over from an earlier output location of this project. Its
                # group still shares the texture set, so attach it to the current file
                # of the same name when there is exactly one.
                same_name = [p for p in by_path if Path(p).name.lower() == Path(path).name.lower()]
                if len(same_name) != 1:
                    stale.append((Path(path).name.lower(), str(getattr(item, "group_name", "") or "")))
                    continue
                path = same_name[0]
            objects, group = _group_objects(project, str(getattr(item, "group_name", "") or ""))
            if not objects:
                continue
            entry = by_path.get(path)
            if entry is None:
                image = _find_output_image(path)
                if image is None:
                    continue
                try:
                    pixels = _read_image_pixels(image)   # loads the file on first access
                except Exception:
                    continue
                width, height = image.size
                if width <= 0 or height <= 0 or pixels.size != width * height * 4:
                    continue
                store_path = str(folder / f"{Path(path).stem}_{_token(hashlib.blake2b(path.encode('utf-8'), digest_size=6).hexdigest())}_reference.npy")
                # Written beside the real store; moved onto it only once the whole
                # capture has succeeded (see pending_stores above). np.save appends
                # .npy to a path without that suffix, so the partial keeps one.
                partial_path = f"{store_path}.{os.getpid()}.partial.npy"
                _store_reference_pixels(partial_path, pixels, bool(image.is_float))
                pending_stores.append((partial_path, store_path))
                entry = _ReferenceOutput(
                    path=path, image_name=image.name, object_names=[], map_uuids=set(),
                    width=int(width), height=int(height), is_float=bool(image.is_float), store_path=store_path,
                    signature=reference_store.file_signature(path),
                )
                by_path[path] = entry
            entry.map_uuids.add(str(getattr(item, "map_uuid", "") or ""))
            if not entry.map_type:
                entry.map_type = str(getattr(item, "map_type", "") or "")
            group_name = str(getattr(group, "name", "") or "")
            if group_name and group_name not in entry.group_names:
                entry.group_names.append(group_name)
            layer_name = _group_uv_layer_name(group) if group is not None else ""
            for obj in objects:
                if obj.name not in entry.object_names:
                    entry.object_names.append(obj.name)
                if obj.name in reference.loop_uvs:
                    continue
                uvs, triangles = _mesh_layout(obj, depsgraph, layer_name)
                if uvs is None:
                    raise RuntimeError(f"{obj.name} has no UV layer to reproject from")
                reference.uv_layers[obj.name] = layer_name
                reference.loop_uvs[obj.name] = uvs
                reference.triangles[obj.name] = triangles
        # Stale records seen before their in-directory twin was created: attach them now.
        for name_lower, group_name in stale:
            entry = next((e for p, e in by_path.items() if Path(p).name.lower() == name_lower), None)
            if entry is None:
                continue
            objects, group = _group_objects(project, group_name)
            if group_name and group_name not in entry.group_names:
                entry.group_names.append(group_name)
            layer_name = _group_uv_layer_name(group) if group is not None else ""
            for obj in objects:
                if obj.name not in entry.object_names:
                    entry.object_names.append(obj.name)
                if obj.name in reference.loop_uvs:
                    continue
                uvs, triangles = _mesh_layout(obj, depsgraph, layer_name)
                if uvs is None:
                    raise RuntimeError(f"{obj.name} has no usable UV layer to reproject from")
                reference.uv_layers[obj.name] = layer_name
                reference.loop_uvs[obj.name] = uvs
                reference.triangles[obj.name] = triangles
        reference.outputs = list(by_path.values())
        if not reference.outputs:
            raise RuntimeError("No textures to move yet: bake once, or load the project's output images")
    except BaseException:
        for partial_path, _final_path in pending_stores:
            try:
                os.remove(partial_path)
            except OSError:
                pass
        raise

    # The capture is complete: move each partial onto the name the manifest names,
    # then write the manifest.
    for partial_path, final_path in pending_stores:
        os.replace(partial_path, final_path)
    _persist_reference(reference)
    return reference


# ---------------------------------------------------------------------------
# Reference persistence and reuse
# ---------------------------------------------------------------------------

def _layout_files(folder: Path, name: str) -> tuple[str, str]:
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=6).hexdigest()
    stem = f"{_token(name)}_{digest}"
    return str(folder / f"{stem}_uvs.npy"), str(folder / f"{stem}_triangles.npy")


def _reference_payload(reference: _Reference) -> dict:
    return {
        "project_name": reference.project_name,
        "captured_at": float(reference.captured_at),
        "uv_layers": dict(reference.uv_layers),
        "layouts": {name: {"uvs": paths[0], "triangles": paths[1]} for name, paths in reference.layout_paths.items()},
        "outputs": [
            {
                "path": output.path,
                "image_name": output.image_name,
                "object_names": list(output.object_names),
                "map_uuids": sorted(output.map_uuids),
                "width": int(output.width),
                "height": int(output.height),
                "is_float": bool(output.is_float),
                "store_path": output.store_path,
                "group_names": list(output.group_names),
                "map_type": output.map_type,
                "signature": list(output.signature) if output.signature else None,
            }
            for output in reference.outputs
        ],
    }


def _persist_reference(reference: _Reference) -> None:
    """Write the manifest, and any layout store not yet on disk, beside the pixel stores.

    Failure is not fatal: the session keeps working from memory; only the
    cross-session restore and the reference reuse on the next toggle are lost."""
    import numpy as np
    try:
        for name, uvs in reference.loop_uvs.items():
            if name in reference.layout_paths:
                continue
            uv_path, tri_path = _layout_files(reference.folder, name)
            np.save(uv_path, np.asarray(uvs, dtype=np.float32))
            np.save(tri_path, np.asarray(reference.triangles[name], dtype=np.int32))
            reference.layout_paths[name] = (uv_path, tri_path)
        reference_store.write_manifest(reference.folder, _reference_payload(reference))
        _prune_store_folder(reference)
    except Exception:
        traceback.print_exc()


def _prune_store_folder(reference: _Reference) -> None:
    """Drop pixel/layout stores the manifest no longer references.

    Every re-capture writes the current outputs and low objects; a renamed
    output, a removed low mesh, or a changed resolution left its old .npy
    behind, and nothing else ever looked at the folder again.
    """
    folder = Path(reference.folder)
    referenced = {os.path.normcase(str(Path(output.store_path))) for output in reference.outputs if output.store_path}
    for uv_path, tri_path in reference.layout_paths.values():
        referenced.add(os.path.normcase(str(Path(uv_path))))
        referenced.add(os.path.normcase(str(Path(tri_path))))
    try:
        candidates = list(folder.glob("*.npy"))
    except Exception:
        return
    for candidate in candidates:
        if os.path.normcase(str(candidate)) in referenced:
            continue
        try:
            candidate.unlink()
        except Exception:
            pass


def _load_reference_from_disk(project):
    """The reference recorded for this project, rebuilt from its manifest, or None."""
    import numpy as np
    try:
        folder = _reference_folder(project)
    except Exception:
        return None
    payload = reference_store.read_manifest(folder)
    if payload is None or str(payload.get("project_name", "")) != str(project.name):
        return None
    if reference_store.missing_files(payload):
        return None
    reference = _Reference(project_name=str(project.name), folder=folder, captured_at=float(payload.get("captured_at", 0.0) or 0.0))
    try:
        reference.uv_layers = {str(k): str(v) for k, v in dict(payload.get("uv_layers", {})).items()}
        for name, layout in payload["layouts"].items():
            uv_path, tri_path = str(layout["uvs"]), str(layout["triangles"])
            reference.loop_uvs[name] = np.asarray(np.load(uv_path), dtype=np.float32).reshape(-1, 2)
            reference.triangles[name] = np.asarray(np.load(tri_path), dtype=np.int32).reshape(-1, 3)
            reference.layout_paths[name] = (uv_path, tri_path)
        for item in payload["outputs"]:
            signature = item.get("signature")
            reference.outputs.append(_ReferenceOutput(
                path=str(item["path"]),
                image_name=str(item.get("image_name", "") or ""),
                object_names=[str(n) for n in item.get("object_names", [])],
                map_uuids={str(u) for u in item.get("map_uuids", [])},
                width=int(item["width"]),
                height=int(item["height"]),
                is_float=bool(item.get("is_float", False)),
                store_path=str(item["store_path"]),
                group_names=[str(g) for g in item.get("group_names", [])],
                map_type=str(item.get("map_type", "") or ""),
                signature=(int(signature[0]), int(signature[1])) if signature else None,
            ))
    except Exception:
        traceback.print_exc()
        return None
    if not reference.outputs:
        return None
    for output in reference.outputs:
        if any(name not in reference.loop_uvs for name in output.object_names):
            return None
    return reference


def _tracked_output_paths(project) -> list[str]:
    paths = []
    for item in getattr(project, "latest_outputs", []) or ():
        raw = str(getattr(item, "file_path", "") or "")
        if raw:
            paths.append(os.path.normpath(bpy.path.abspath(raw)))
    return paths


def _reference_matches_scene(reference: _Reference, project, *, require_files: bool) -> tuple[bool, str]:
    """Whether a stored reference is still the truth for this scene and its files."""
    verdict, reason = reference_store.reuse_verdict(
        _reference_payload(reference), _tracked_output_paths(project), require_files=require_files
    )
    if not verdict:
        return False, reason
    for name in reference.loop_uvs:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            return False, f"{name} is missing"
    wanted = {os.path.normcase(output.path) for output in reference.outputs}
    for image in bpy.data.images:
        try:
            if not image.filepath or not getattr(image, "is_dirty", False):
                continue
            if os.path.normcase(os.path.normpath(bpy.path.abspath(image.filepath))) in wanted:
                return False, f"{image.name} has unsaved edits"
        except Exception:
            continue
    return True, ""


def _reusable_reference(project):
    """The existing reference when the textures on disk are still our own transfer of it.

    Recapturing from disk after a commit would pair already-moved pixels with the
    layout they were moved to: correct, but it throws away the originals (fatal
    for painted or imported maps that cannot be rebaked) and every later edit
    would be a resample of a resample. Prefer the reference held in memory, then
    the one recorded on disk."""
    current = _state["reference"]
    if current is not None and current.project_name == str(project.name):
        verdict, _reason = _reference_matches_scene(current, project, require_files=False)
        if verdict:
            return current
    stored = _load_reference_from_disk(project)
    if stored is not None:
        verdict, _reason = _reference_matches_scene(stored, project, require_files=True)
        if verdict:
            return stored
    return None


_DISK_REFERENCE_PROBE = {"key": "", "at": 0.0, "available": False}


def _disk_reference_available(project) -> bool:
    """Cheap poll-time check, cached for a moment: the sidebar redraws constantly."""
    try:
        key = str(_reference_folder(project))
    except Exception:
        return False
    now = time.monotonic()
    if _DISK_REFERENCE_PROBE["key"] == key and now - float(_DISK_REFERENCE_PROBE["at"]) < 2.0:
        return bool(_DISK_REFERENCE_PROBE["available"])
    available = os.path.isfile(reference_store.manifest_path(key))
    _DISK_REFERENCE_PROBE.update(key=key, at=now, available=available)
    return available


# ---------------------------------------------------------------------------
# GPU transfer
# ---------------------------------------------------------------------------

_SHADERS: dict[str, object] = {}

_BILINEAR_GLSL = """
vec4 fyrSampleBilinear(sampler2D tex, vec2 uv)
{
  ivec2 size = textureSize(tex, 0);
  vec2 p = uv * vec2(size) - 0.5;
  // Interpolated UVs land a hair off texel centres on unchanged geometry; snap
  // so an unmoved island copies its texels bit-exact instead of a 0.1% blend.
  vec2 snapped = floor(p + 0.5);
  p = mix(p, snapped, vec2(lessThan(abs(p - snapped), vec2(0.002))));
  vec2 f = fract(p);
  ivec2 i0 = ivec2(floor(p));
  ivec2 hi = size - ivec2(1);
  ivec2 a = clamp(i0, ivec2(0), hi);
  ivec2 b = clamp(i0 + ivec2(1, 0), ivec2(0), hi);
  ivec2 c = clamp(i0 + ivec2(0, 1), ivec2(0), hi);
  ivec2 d = clamp(i0 + ivec2(1, 1), ivec2(0), hi);
  return mix(mix(texelFetch(tex, a, 0), texelFetch(tex, b, 0), f.x),
             mix(texelFetch(tex, c, 0), texelFetch(tex, d, 0), f.x), f.y);
}
"""


def _raster_shader():
    import gpu
    shader = _SHADERS.get("raster")
    if shader is not None:
        return shader
    info = gpu.types.GPUShaderCreateInfo()
    iface = gpu.types.GPUStageInterfaceInfo("fyr_live_reproject_iface")
    iface.smooth("VEC2", "srcUV")
    info.vertex_out(iface)
    info.vertex_in(0, "VEC2", "pos")
    info.vertex_in(1, "VEC2", "uvSrc")
    info.sampler(0, "FLOAT_2D", "sourceTex")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        """
        void main()
        {
          srcUV = uvSrc;
          gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
        }
        """
    )
    info.fragment_source(_BILINEAR_GLSL + """
        void main()
        {
          FragColor = fyrSampleBilinear(sourceTex, srcUV);
        }
        """)
    shader = gpu.shader.create_from_info(info)
    _SHADERS["raster"] = shader
    return shader


def _coverage_shader():
    import gpu
    shader = _SHADERS.get("coverage")
    if shader is not None:
        return shader
    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC2", "pos")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        """
        void main()
        {
          gl_Position = vec4(pos * 2.0 - 1.0, 0.0, 1.0);
        }
        """
    )
    info.fragment_source(
        """
        void main()
        {
          FragColor = vec4(1.0);
        }
        """
    )
    shader = gpu.shader.create_from_info(info)
    _SHADERS["coverage"] = shader
    return shader


def _dilate_shader():
    import gpu
    shader = _SHADERS.get("dilate")
    if shader is not None:
        return shader
    info = gpu.types.GPUShaderCreateInfo()
    info.vertex_in(0, "VEC2", "pos")
    info.sampler(0, "FLOAT_2D", "colorTex")
    info.sampler(1, "FLOAT_2D", "coverTex")
    info.sampler(2, "FLOAT_2D", "sourceTex")
    info.sampler(3, "FLOAT_2D", "refCoverTex")
    info.push_constant("INT", "radius")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        """
        void main()
        {
          gl_Position = vec4(pos, 0.0, 1.0);
        }
        """
    )
    info.fragment_source(
        """
        void main()
        {
          ivec2 p = ivec2(gl_FragCoord.xy);
          if (texelFetch(coverTex, p, 0).r > 0.5)
          {
            FragColor = texelFetch(colorTex, p, 0);
            return;
          }
          ivec2 size = textureSize(colorTex, 0);
          // Uncovered texel: dilate from the nearest covered texel within the
          // margin. If the nearest island edge sits at the same distance in the
          // reference layout, nothing moved here, so keep the reference texel and
          // its original padding byte for byte. Beyond the margin, or where the
          // reference had no island nearby either, keep the reference texel too.
          float best = 1e30;
          float bestRef = 1e30;
          vec4 bestColor = texelFetch(sourceTex, p, 0);
          bool refCoveredHere = texelFetch(refCoverTex, p, 0).r > 0.5;
          for (int dy = -radius; dy <= radius; ++dy)
          {
            for (int dx = -radius; dx <= radius; ++dx)
            {
              ivec2 q = p + ivec2(dx, dy);
              if (any(lessThan(q, ivec2(0))) || any(greaterThanEqual(q, size))) continue;
              float d = float(dx * dx + dy * dy);
              if (d < bestRef && texelFetch(refCoverTex, q, 0).r > 0.5) bestRef = d;
              if (d < best && texelFetch(coverTex, q, 0).r > 0.5)
              {
                best = d;
                bestColor = texelFetch(colorTex, q, 0);
              }
            }
          }
          if (best < 1e30 && !refCoveredHere && abs(best - bestRef) < 0.5)
          {
            FragColor = texelFetch(sourceTex, p, 0);
            return;
          }
          FragColor = bestColor;
        }
        """
    )
    shader = gpu.shader.create_from_info(info)
    _SHADERS["dilate"] = shader
    return shader


_TEXTURE_CACHE: dict[str, tuple[object, int]] = {}
_TEXTURE_CACHE_BUDGET_BYTES = 512 * 1024 * 1024


def _source_texture(output: "_ReferenceOutput", flat):
    """GPU copy of the reference pixels, uploaded once per output (300 ms at 2K)."""
    cached = _TEXTURE_CACHE.get(output.store_path)
    if cached is not None:
        return cached[0]
    size = int(output.width) * int(output.height) * 16
    while _TEXTURE_CACHE and sum(entry[1] for entry in _TEXTURE_CACHE.values()) + size > _TEXTURE_CACHE_BUDGET_BYTES:
        _TEXTURE_CACHE.pop(next(iter(_TEXTURE_CACHE)))
    texture = _make_texture(output.width, output.height, flat)
    _TEXTURE_CACHE[output.store_path] = (texture, size)
    return texture


def _clear_texture_cache() -> None:
    _TEXTURE_CACHE.clear()
    for target in _REF_COVERAGE_CACHE.values():
        try:
            target.free()
        except Exception:
            pass
    _REF_COVERAGE_CACHE.clear()


def _make_texture(width: int, height: int, flat):
    """Upload Blender-order pixels (row-major y, x, channel) as an RGBA32F texture."""
    import gpu
    import numpy as np
    pixels = np.ascontiguousarray(flat, dtype=np.float32).reshape(-1)
    data = gpu.types.Buffer("FLOAT", int(width) * int(height) * 4, pixels)
    return gpu.types.GPUTexture((int(width), int(height)), format="RGBA32F", data=data)


def _read_rgba32f(texture, width: int, height: int):
    """Read an RGBA32F texture back into Blender pixel order.

    GPUTexture.read() hands the data back channel-planar and column-major
    (index = c * width * height + x * height + y) while reporting a
    (height, width, 4) shape. Verified 2026-09-06 on OpenGL: a plain upload
    followed by this transpose round-trips exactly, and a half-screen draw reads
    back as a half-screen rectangle instead of 4-texel stripes."""
    import numpy as np
    raw = np.asarray(texture.read(), dtype=np.float32).reshape(int(height), int(width), 4)
    return np.ascontiguousarray(raw.transpose(2, 1, 0)).reshape(-1)


_REF_COVERAGE_CACHE: dict[str, object] = {}


def _draw_coverage(target, positions, triangles) -> None:
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader
    coverage = _coverage_shader()
    batch = batch_for_shader(
        coverage, "TRIS",
        {"pos": np.ascontiguousarray(positions, dtype=np.float32).tolist()},
        indices=np.ascontiguousarray(triangles, dtype=np.int32).tolist(),
    )
    with target.bind():
        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(False)
        gpu.state.face_culling_set("NONE")
        gpu.state.color_mask_set(True, True, True, True)
        gpu.state.scissor_test_set(False)
        gpu.state.active_framebuffer_get().clear(color=(0.0, 0.0, 0.0, 0.0))
        coverage.bind()
        batch.draw(coverage)


def _reference_coverage(output: "_ReferenceOutput", source_uvs, triangles):
    """Coverage of the reference layout, so unmoved padding can be left alone."""
    import gpu
    cached = _REF_COVERAGE_CACHE.get(output.store_path)
    if cached is not None:
        return cached
    while len(_REF_COVERAGE_CACHE) >= 4:
        _REF_COVERAGE_CACHE.pop(next(iter(_REF_COVERAGE_CACHE))).free()
    target = gpu.types.GPUOffScreen(int(output.width), int(output.height), format="RGBA8")
    _draw_coverage(target, source_uvs, triangles)
    _REF_COVERAGE_CACHE[output.store_path] = target
    return target


def _transfer_texture(source_tex, ref_cover, width: int, height: int, positions, source_uvs, triangles, margin: int):
    """Draw every triangle at ``positions`` sampling ``source_tex`` at ``source_uvs``.

    Returns the dilated result as a flat float32 array in Blender pixel order."""
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader

    raster = _raster_shader()
    coverage = _coverage_shader()
    dilate = _dilate_shader()

    pos_list = np.ascontiguousarray(positions, dtype=np.float32).tolist()
    uv_list = np.ascontiguousarray(source_uvs, dtype=np.float32).tolist()
    tri_list = np.ascontiguousarray(triangles, dtype=np.int32).tolist()
    mesh_batch = batch_for_shader(raster, "TRIS", {"pos": pos_list, "uvSrc": uv_list}, indices=tri_list)
    cover_batch = batch_for_shader(coverage, "TRIS", {"pos": pos_list}, indices=tri_list)
    quad = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)]
    quad_batch = batch_for_shader(dilate, "TRIS", {"pos": quad}, indices=[(0, 1, 2), (0, 2, 3)])

    # Allocated INSIDE the try: a failure on the second or third allocation used to leak
    # the ones before it (~1.25 GiB at 4K), and the reproject timer retries.
    color_target = cover_target = final_target = None
    try:
        color_target = gpu.types.GPUOffScreen(int(width), int(height), format="RGBA32F")
        cover_target = gpu.types.GPUOffScreen(int(width), int(height), format="RGBA8")
        final_target = gpu.types.GPUOffScreen(int(width), int(height), format="RGBA32F")
        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.depth_mask_set(False)
        gpu.state.face_culling_set("NONE")
        gpu.state.color_mask_set(True, True, True, True)
        gpu.state.scissor_test_set(False)
        with color_target.bind():
            gpu.state.active_framebuffer_get().clear(color=(0.0, 0.0, 0.0, 0.0))
            raster.bind()
            raster.uniform_sampler("sourceTex", source_tex)
            mesh_batch.draw(raster)
        with cover_target.bind():
            gpu.state.active_framebuffer_get().clear(color=(0.0, 0.0, 0.0, 0.0))
            coverage.bind()
            cover_batch.draw(coverage)
        with final_target.bind():
            dilate.bind()
            dilate.uniform_sampler("colorTex", color_target.texture_color)
            dilate.uniform_sampler("coverTex", cover_target.texture_color)
            dilate.uniform_sampler("sourceTex", source_tex)
            dilate.uniform_sampler("refCoverTex", ref_cover.texture_color)
            dilate.uniform_int("radius", int(max(0, margin)))
            quad_batch.draw(dilate)
        result = _read_rgba32f(final_target.texture_color, width, height)
    finally:
        for target in (color_target, cover_target, final_target):
            if target is None:
                continue
            try:
                target.free()
            except Exception:
                pass
    return result


def _current_layout(reference: _Reference, output: _ReferenceOutput):
    """Concatenated (positions, source_uvs, triangles) for one output image.

    Returns None with a reason when an object is gone or its topology no longer
    matches the reference."""
    import numpy as np
    depsgraph = bpy.context.evaluated_depsgraph_get()
    positions, sources, triangles = [], [], []
    offset = 0
    for name in output.object_names:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            return None, f"{name} is missing; Live Reproject paused"
        ref_uvs = reference.loop_uvs[name]
        current, current_triangles = _mesh_layout(obj, depsgraph, reference.uv_layers.get(name, ""))
        if current is None:
            return None, f"{name} lost its UV layer; Live Reproject paused"
        if len(current) != len(ref_uvs) or current_triangles.shape != reference.triangles[name].shape:
            return None, f"{name} changed topology; Live Reproject paused until it matches the reference again"
        positions.append(current)
        sources.append(ref_uvs)
        triangles.append(reference.triangles[name] + offset)
        offset += len(ref_uvs)
    if not positions:
        return None, "Nothing to reproject"
    return (np.concatenate(positions), np.concatenate(sources), np.concatenate(triangles)), ""


def _reproject_output(project, reference: _Reference, output: _ReferenceOutput):
    layout, reason = _current_layout(reference, output)
    if layout is None:
        return None, reason
    positions, sources, triangles = layout
    if output.store_path in _TEXTURE_CACHE:
        source_tex = _source_texture(output, None)
    else:
        source_tex = _source_texture(output, _load_reference_pixels(output.store_path))
    ref_cover = _reference_coverage(output, sources, triangles)
    # Live Reproject's fragment shader searches every texel in this square. Keep
    # its interactive radius bounded by the saved Distance value; a full-image
    # Infinite radius belongs to the bake path, which uses jump flooding.
    margin = int(getattr(project, "margin", 0) or 0)
    result = _transfer_texture(source_tex, ref_cover, output.width, output.height, positions, sources, triangles, margin)
    return result, ""


# ---------------------------------------------------------------------------
# Preview and commit
# ---------------------------------------------------------------------------

def _preview_output(project, reference: _Reference):
    active = _active_map_uuid(project)
    for output in reference.outputs:
        if active and active in output.map_uuids:
            return output
    return reference.outputs[0]


def _output_item_for_uuid(project, map_uuid: str):
    return next((item for item in project.latest_outputs if str(item.map_uuid) == str(map_uuid)), None)


def _preview(project, reference: _Reference) -> None:
    output = _preview_output(project, reference)
    result, reason = _reproject_output(project, reference, output)
    if result is None:
        project.reproject_error = reason
        return
    image = bpy.data.images.get(_IMAGE_NAME)
    if image is None:
        image = bpy.data.images.new(_IMAGE_NAME, width=output.width, height=output.height, alpha=True, float_buffer=True)
    elif tuple(image.size) != (output.width, output.height):
        image.scale(output.width, output.height)
    if not _state["material_target_uuid"]:
        _state["material_target_uuid"] = output.store_path
        _state["material_image"] = _find_output_image(output.path)
        _state["material_output"] = output
    # Bind before writing pixels: the binding sets the image colour space, which
    # regenerates a generated image's buffer and would discard the pixels. Bind on
    # every group that shares this texture, not just the active map's first record.
    _bind_preview_material(project, output, image)
    image.pixels.foreach_set(result)
    image.update()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "IMAGE_EDITOR":
                continue
            key = area.as_pointer()
            _state["previous_images"].setdefault(key, area.spaces.active.image)
            if area.spaces.active.image is not image:
                area.spaces.active.image = image
    project.reproject_error = ""
    project.reproject_status = f"Live {output.width}x{output.height}"
    _state["ignore_until"] = time.monotonic() + _SELF_WRITE_GRACE_SECONDS


def _bind_preview_material(project, output: _ReferenceOutput, image) -> None:
    sources = [{"group_name": name, "image": image, "map_type": output.map_type} for name in output.group_names]
    if not sources:
        return
    try:
        preview_materials.apply_preview_output_all_groups(project, per_group_sources=sources)
    except Exception:
        traceback.print_exc()


def _write_output_pixels(output: _ReferenceOutput, flat) -> bool:
    image = _find_output_image(output.path)
    if image is None:
        return False
    if tuple(image.size) != (output.width, output.height):
        return False
    with dirty_tracker.suppress():
        image.pixels.foreach_set(flat)
        image.update()
        try:
            if image.filepath and not image.packed_file:
                image.save()
                # Record the new file time on the datablock. Otherwise the managed
                # output loader treats our own save as an external edit and reloads
                # every texture from disk the next time anything asks for it.
                try:
                    runtime._mark_managed_output_image(image, output.path)
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()
            return False
    return True


def _commit_one(project, reference: _Reference, output: _ReferenceOutput) -> str:
    result, reason = _reproject_output(project, reference, output)
    if result is None:
        return reason
    if not _write_output_pixels(output, result):
        return f"Could not write {Path(output.path).name}"
    _state["ignore_until"] = time.monotonic() + _SELF_WRITE_GRACE_SECONDS
    # The file now carries our transfer of the reference: record it so the next
    # toggle-on and the post-bake rebase both know the reference is still the truth.
    output.signature = reference_store.file_signature(output.path)
    _persist_reference(reference)
    return ""


def _restore_all(project, reference: _Reference) -> int:
    restored = 0
    for output in reference.outputs:
        try:
            if _write_output_pixels(output, _load_reference_pixels(output.store_path)):
                restored += 1
                output.signature = reference_store.file_signature(output.path)
        except Exception:
            traceback.print_exc()
    _state["ignore_until"] = time.monotonic() + _SELF_WRITE_GRACE_SECONDS
    _state["dirty_since_commit"] = False
    _persist_reference(reference)
    return restored


def _schedule(project) -> None:
    _state["generation"] = int(_state["generation"]) + 1
    project.reproject_generation = int(_state["generation"])
    project.reproject_status = "Updating"
    _state["pending"] = True
    _state["dirty_since_commit"] = True
    _state["commit_pending"] = True
    _state["commit_queue"] = []
    _state["due"] = time.monotonic() + _QUIET_SECONDS
    _ensure_timer()


def notify_uv_change(project) -> None:
    """Operators that rewrite UVs from Object Mode call this: those writes do not
    reach the depsgraph handler the way Edit Mode edits do."""
    if project is None or not bool(getattr(project, "live_reproject", False)) or _state["reference"] is None:
        return
    _schedule(project)


def _timer_tick():
    project = properties.peek_active_project(getattr(bpy.context, "scene", None))
    reference = _state["reference"]
    if project is None or not bool(getattr(project, "live_reproject", False)) or reference is None:
        _state["timer"] = False
        restore_preview_image()
        return None
    try:
        now = time.monotonic()
        if _state["pending"] and now - float(_state["last_preview"]) >= _PREVIEW_INTERVAL:
            _state["pending"] = False
            _state["last_preview"] = now
            _preview(project, reference)
        if _state["commit_pending"] and not _state["pending"] and now >= float(_state["due"]):
            if _modal_operator_running():
                # Mid-drag: the layout is still changing and file writes would stall
                # the interaction. Try again once the operator has finished.
                _state["due"] = now + _QUIET_SECONDS
                return _PREVIEW_INTERVAL
            if not _state["commit_queue"]:
                _state["commit_queue"] = list(reference.outputs)
            output = _state["commit_queue"].pop(0)
            reason = _commit_one(project, reference, output)
            if reason:
                project.reproject_error = reason
                _state["commit_queue"] = []
                _state["commit_pending"] = False
            elif not _state["commit_queue"]:
                _state["commit_pending"] = False
                _state["dirty_since_commit"] = False
                project.reproject_error = ""
                project.reproject_status = f"Live, {len(reference.outputs)} textures saved"
    except Exception as exc:
        traceback.print_exc()
        _state["pending"] = False
        _state["commit_pending"] = False
        _state["commit_queue"] = []
        project.reproject_error = f"Live Reproject failed: {exc}"
    return _PREVIEW_INTERVAL


def _ensure_timer():
    # Ask Blender rather than trusting the flag: a tick that raised leaves the
    # flag set with no timer behind it.
    if not bpy.app.timers.is_registered(_timer_tick):
        _state["timer"] = True
        bpy.app.timers.register(_timer_tick, first_interval=0.0, persistent=True)


# ---------------------------------------------------------------------------
# Toggle, handler, UI helpers
# ---------------------------------------------------------------------------

def on_toggle(project):
    if bool(getattr(project, "live_reproject", False)):
        reference = _reusable_reference(project)
        kept = reference is not None
        if reference is None:
            try:
                reference = _capture_reference(project)
            except Exception as exc:
                project.reproject_error = str(exc)
                project.reproject_status = ""
                project.live_reproject = False
                return
        if reference is not _state["reference"]:
            _clear_texture_cache()
        _state["reference"] = reference
        _state["pending"] = False
        _state["commit_pending"] = False
        _state["commit_queue"] = []
        _state["dirty_since_commit"] = False
        project.reproject_error = ""
        project.reproject_status = f"Live, {len(reference.outputs)} textures" + (", original reference kept" if kept else "")
        _ensure_timer()
        return
    reference = _state["reference"]
    if reference is not None and (_state["dirty_since_commit"] or _state["commit_pending"]):
        # Switching off keeps what the artist sees: finish the pending commit now.
        for output in reference.outputs:
            try:
                _commit_one(project, reference, output)
            except Exception:
                traceback.print_exc()
    # The reference stays until the next switch-on replaces it, so Restore Textures
    # can still undo a session's reprojection after the toggle is off.
    _state["pending"] = False
    _state["commit_pending"] = False
    _state["commit_queue"] = []
    _state["dirty_since_commit"] = False
    _clear_texture_cache()
    project.reproject_status = ""
    restore_preview_image()


def rebase_after_bake(project) -> None:
    """A finished bake wrote textures for the CURRENT layout: they become the reference.

    Without this the reference kept the textures from toggle-on time, so the next
    UV nudge after a bake rewrote every fresh output from the stale pixels and the
    bake was silently lost."""
    if project is None or not bool(getattr(project, "live_reproject", False)) or _state["reference"] is None:
        return
    if not _outputs_changed_since(project, _state["reference"]):
        # A same-settings rebake is served from the worker's composite cache and
        # writes nothing; re-reading 16 unchanged 2K textures cost 1.5 s for no gain.
        return
    try:
        reference = _capture_reference(project)
    except Exception as exc:
        invalidate(project, f"Live Reproject switched off after the bake: {exc}")
        return
    _state["reference"] = reference
    _state["pending"] = False
    _state["commit_pending"] = False
    _state["commit_queue"] = []
    _state["dirty_since_commit"] = False
    _clear_texture_cache()
    project.reproject_error = ""
    project.reproject_status = f"Live, {len(reference.outputs)} textures"


def _outputs_changed_since(project, reference: _Reference) -> bool:
    """True when a tracked output is not in the reference or was rewritten by
    something other than our own commit or restore (those refresh the signature)."""
    known = {os.path.normcase(output.path): output for output in reference.outputs}
    for path in _tracked_output_paths(project):
        output = known.get(os.path.normcase(path))
        if output is None:
            return True
        current = reference_store.file_signature(path)
        if current is None:
            return True
        if output.signature is not None:
            if tuple(current) != tuple(output.signature):
                return True
            continue
        try:
            if os.path.getmtime(path) > float(reference.captured_at):
                return True
        except OSError:
            return True
    return False


def invalidate(project, reason: str):
    if project is None or not bool(getattr(project, "live_reproject", False)):
        return
    project.reproject_error = reason
    project.live_reproject = False


@persistent
def depsgraph_update(scene, depsgraph):
    project = properties.peek_active_project(scene)
    reference = _state["reference"]
    if project is None or reference is None or not bool(getattr(project, "live_reproject", False)):
        return
    if runtime.active_bake_snapshot() is not None or dirty_tracker.is_silenced() or time.monotonic() < float(_state["ignore_until"]):
        # Our own preview and commit writes, and the bake pipeline's material and
        # visibility sweep, are not UV edits.
        return
    names = reference.loop_uvs.keys()
    low_objects = {name: obj for name in names if (obj := bpy.data.objects.get(name)) is not None and obj.type == "MESH"}
    low_meshes = {obj.data.as_pointer() for obj in low_objects.values()}
    for update in depsgraph.updates:
        value = getattr(update, "id", None)
        if not bool(getattr(update, "is_updated_geometry", False)):
            continue
        # The update carries the EVALUATED mesh, whose pointer is never in low_meshes
        # (original pointers); compare the original.
        value = getattr(value, "original", None) or value
        if isinstance(value, bpy.types.Mesh) and value.as_pointer() in low_meshes:
            _schedule(project)
            return
        if isinstance(value, bpy.types.Object) and value.name in low_objects and value.mode == "EDIT":
            _schedule(project)
            return


@persistent
def _on_load_post(_dummy=None):
    _state["reference"] = None
    _state["pending"] = False
    _state["commit_pending"] = False
    _state["commit_queue"] = []
    _state["dirty_since_commit"] = False
    _state["previous_images"].clear()
    _state["material_target_uuid"] = ""
    _state["material_image"] = None
    _state["material_output"] = None
    _clear_texture_cache()
    try:
        for scene in bpy.data.scenes:
            settings = getattr(scene, "fyr_baker_settings", None)
            for project in getattr(settings, "projects", []):
                if bool(getattr(project, "live_reproject", False)):
                    project.live_reproject = False
                project.reproject_status = ""
                project.reproject_error = ""
    except Exception:
        pass


def restore_preview_image():
    project = properties.peek_active_project(getattr(bpy.context, "scene", None))
    output = _state.get("material_output")
    if project is not None and output is not None and _state["material_image"] is not None:
        _bind_preview_material(project, output, _state["material_image"])
    _state["material_target_uuid"] = ""
    _state["material_image"] = None
    _state["material_output"] = None
    for window in getattr(bpy.context.window_manager, "windows", []):
        for area in window.screen.areas:
            if area.type == "IMAGE_EDITOR" and area.as_pointer() in _state["previous_images"]:
                area.spaces.active.image = _state["previous_images"][area.as_pointer()]
    _state["previous_images"].clear()
    image = bpy.data.images.get(_IMAGE_NAME)
    if image is not None:
        image_cleanup.remove_image_when_safe(image, reason="reprojection preview")


def status_message(project) -> str:
    error = str(getattr(project, "reproject_error", "") or "").strip()
    if error:
        return error
    return str(getattr(project, "reproject_status", "") or "").strip()


def draw_status_icon(row, project) -> None:
    """One hover icon next to the toggle instead of status text under it."""
    error = str(getattr(project, "reproject_error", "") or "").strip()
    if not error:
        return
    icon_row = row.row(align=True)
    icon_row.alert = True
    icon_row.operator("master_baker.live_reproject_status", text="", icon="ERROR", emboss=False)


class MASTER_BAKER_OT_live_reproject_status(bpy.types.Operator):
    bl_idname = "master_baker.live_reproject_status"
    bl_label = "Live Reproject Status"
    bl_options = {"INTERNAL"}

    @classmethod
    def description(cls, context, _properties):
        project = properties.peek_active_project(getattr(context, "scene", None))
        return status_message(project) if project is not None else "Live Reproject"

    def execute(self, context):
        project = properties.peek_active_project(context.scene)
        message = status_message(project) if project is not None else ""
        if message:
            self.report({"INFO"}, message)
        return {"FINISHED"}


class MASTER_BAKER_OT_restore_last_bake_outputs(bpy.types.Operator):
    bl_idname = "master_baker.restore_last_bake_outputs"
    bl_label = "Restore Textures"
    bl_description = (
        "Put the textures back to how they were when Live Reproject was switched on. "
        "Works after Blender was closed and reopened: the originals are kept beside the outputs"
    )
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        project = properties.peek_active_project(getattr(context, "scene", None))
        if project is None or runtime.active_bake_snapshot() is not None:
            return False
        reference = _state["reference"]
        if reference is not None and reference.project_name == str(getattr(project, "name", "")):
            return True
        return _disk_reference_available(project)

    def execute(self, context):
        project = properties.peek_active_project(context.scene)
        reference = _state["reference"]
        if reference is None or reference.project_name != str(getattr(project, "name", "")):
            # A previous session's reference: rebuilt from the manifest beside the stores.
            reference = _load_reference_from_disk(project)
        if reference is None:
            self.report({"ERROR"}, "No Live Reproject reference for this project")
            return {"CANCELLED"}
        if reference is not _state["reference"]:
            _clear_texture_cache()
            _state["reference"] = reference
        _state["pending"] = False
        _state["commit_pending"] = False
        _state["commit_queue"] = []
        restored = _restore_all(project, reference)
        project.reproject_error = ""
        project.reproject_status = f"Restored {restored} textures"
        self.report({"INFO"}, f"Restored {restored} textures")
        return {"FINISHED"}


_CLASSES = (MASTER_BAKER_OT_live_reproject_status, MASTER_BAKER_OT_restore_last_bake_outputs)


def register():
    for cls in _CLASSES:
        safe_register_class(cls)
    handlers = bpy.app.handlers.depsgraph_update_post
    if depsgraph_update not in handlers:
        handlers.append(depsgraph_update)
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    project = properties.peek_active_project(getattr(bpy.context, "scene", None))
    if project is not None:
        project.live_reproject = False
    restore_preview_image()
    handlers = bpy.app.handlers.depsgraph_update_post
    if depsgraph_update in handlers:
        handlers.remove(depsgraph_update)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    if bpy.app.timers.is_registered(_timer_tick):
        bpy.app.timers.unregister(_timer_tick)
    _state["timer"] = False
    _state["reference"] = None
    _clear_texture_cache()
    _SHADERS.clear()
    for cls in reversed(_CLASSES):
        safe_unregister_class(cls)
