"""Memory-safe Cycles bakes: preflight budget, row strips and strip assembly.

A Blender selected-to-active float bake holds ~119 bytes per texel of the bake image
at once (both BakePixel arrays, the result, the target and the margin filter's full
copy of it). At 16K that is ~32 GB, and when ``malloc`` fails inside the margin filter
Blender writes through a NULL pointer instead of reporting it. The Cycles recovery and
material paths therefore plan every bake against the memory actually free:

- :func:`plan_strips` splits a target that does not fit into full-width row strips.
  Every strip has the same height, so one bake image is reused, and every window lies
  inside the image, so image edges behave exactly as in a full bake. Each strip
  carries an apron of ``margin + filter radius + 1`` rows on the sides that are not an
  image edge; the kept rows are therefore the rows a full bake would produce.
- :class:`StripUVLayers` points the bake at one strip through a temporary UV layer
  (``v' = ((v - tile_v) * H - window_start) / strip_rows``); the artist's UVs are
  never written, except the documented 8-UV-layer fallback that shifts the source
  layer in place for a selected-to-active bake and restores it exactly.
- :class:`StripAssembler` lets Blender save each finished strip in the requested
  format, then copies its kept scanlines into the final file with the OpenImageIO
  module bundled with Blender, top-down, so assembly holds one strip at a time.

When a single strip covers the whole image every caller runs its pre-existing code
path unchanged. All sizes and constants are in ``constants`` (``CYCLES_*``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from . import constants


class CyclesMemoryError(RuntimeError):
    """A Cycles bake cannot run in the memory that is free. The text is for the artist."""


class SystemMemory(NamedTuple):
    available_physical: int
    total_physical: int
    #: RAM + page file still available; None where the platform has no such figure.
    available_commit: int | None

    @property
    def available(self) -> int:
        """The binding limit: the smaller of free RAM and free commit."""
        if self.available_commit is None:
            return int(self.available_physical)
        return int(min(self.available_physical, self.available_commit))


def system_memory() -> SystemMemory | None:
    """Free physical memory, total physical memory and free commit, or None."""
    try:
        from . import storage_cleanup

        status = storage_cleanup.system_memory_status()
    except Exception:  # noqa: BLE001 - unmeasurable means "do not refuse"
        return None
    if status is None:
        return None
    available, total, commit = status
    return SystemMemory(int(available), int(total), None if commit is None else int(commit))


def memory_guard_enabled() -> bool:
    value = str(os.environ.get(constants.CYCLES_MEMORY_GUARD_ENV_VAR, "") or "").strip().lower()
    return value not in {"0", "false", "off", "no"}


def memory_reserve_bytes(total_physical: int) -> int:
    return int(
        max(
            constants.CYCLES_MEMORY_RESERVE_MIN_BYTES,
            constants.CYCLES_MEMORY_RESERVE_FRACTION * max(0, int(total_physical or 0)),
        )
    )


def strip_max_texels() -> int:
    raw = str(os.environ.get(constants.CYCLES_STRIP_MAX_TEXELS_ENV_VAR, "") or "").strip()
    if raw:
        try:
            value = int(float(raw))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return int(constants.CYCLES_STRIP_MAX_TEXELS)


def format_gb(byte_count: int) -> str:
    return f"{max(0.0, float(byte_count)) / float(1024 ** 3):.1f} GB"


# --------------------------------------------------------------------------- estimates


def bytes_per_texel(
    *, selected_to_active: bool, float_target: bool, derived_extra: int = 0
) -> int:
    """Peak bytes one Blender bake call holds per texel of its bake image.

    Blender's own buffers (``CYCLES_BAKE_BYTES_PER_TEXEL_*``) plus the Cycles session's
    (``CYCLES_BAKE_ENGINE_BYTES_PER_TEXEL``) plus a derived map's extras.
    """
    base = (
        constants.CYCLES_BAKE_BYTES_PER_TEXEL_S2A_FLOAT
        if float_target
        else constants.CYCLES_BAKE_BYTES_PER_TEXEL_S2A_BYTE
    )
    if not selected_to_active:
        base -= constants.CYCLES_BAKE_PIXEL_ARRAY_BYTES
    return int(base + constants.CYCLES_BAKE_ENGINE_BYTES_PER_TEXEL + max(0, int(derived_extra or 0)))


def derived_extra_bytes(emit_kind: str | None) -> int:
    return int(constants.CYCLES_DERIVED_EXTRA_BYTES_PER_TEXEL.get(str(emit_kind or ""), 0))


def _datablock_key(value):
    pointer = getattr(value, "as_pointer", None)
    if pointer is not None:
        try:
            return pointer()
        except Exception:  # noqa: BLE001 - removed datablock
            pass
    return id(value)


def _evaluated_depsgraph():
    try:
        import bpy  # noqa: PLC0415

        return bpy.context.evaluated_depsgraph_get()
    except Exception:  # noqa: BLE001 - outside Blender, or no context
        return None


def _triangle_count(obj, depsgraph) -> int:
    """Triangles of the modifier-evaluated mesh (0 when unknown)."""
    evaluated = obj
    if depsgraph is not None:
        try:
            evaluated = obj.evaluated_get(depsgraph)
        except Exception:  # noqa: BLE001 - fall back to the base object
            evaluated = obj
    mesh = getattr(evaluated, "data", None)
    try:
        triangles = getattr(mesh, "loop_triangles", None)
        if triangles is not None:
            return int(len(triangles))
        polygons = getattr(mesh, "polygons", None)
        if polygons is not None:
            return int(len(polygons)) * 2
    except Exception:  # noqa: BLE001 - counting must never fail a bake
        return 0
    return 0


def _node_tree_images(tree, images: dict, visited: set) -> None:
    if tree is None:
        return
    key = _datablock_key(tree)
    if key in visited:
        return
    visited.add(key)
    for node in getattr(tree, "nodes", None) or ():
        image = getattr(node, "image", None)
        if image is not None and hasattr(image, "size"):
            images.setdefault(_datablock_key(image), image)
        group_tree = getattr(node, "node_tree", None)
        if group_tree is not None:
            _node_tree_images(group_tree, images, visited)


def _image_texel_bytes(image) -> int:
    try:
        depth = int(getattr(image, "depth", 0) or 0)
    except (TypeError, ValueError):
        depth = 0
    if bool(getattr(image, "is_float", False)):
        # Blender cannot say whether a float image is half on disk; a loaded 64-bit
        # buffer is, anything else is costed as full float.
        if depth and depth <= 64:
            return constants.CYCLES_IMAGE_BYTES_PER_TEXEL_HALF
        return constants.CYCLES_IMAGE_BYTES_PER_TEXEL_FLOAT
    return constants.CYCLES_IMAGE_BYTES_PER_TEXEL_BYTE


def _file_image_size(path: str) -> tuple[int, int] | None:
    try:
        import OpenImageIO as oiio  # noqa: PLC0415 - bundled with Blender

        handle = oiio.ImageInput.open(str(path))
        if handle is None:
            return None
        try:
            spec = handle.spec()
            return int(spec.width), int(spec.height)
        finally:
            handle.close()
    except Exception:  # noqa: BLE001 - header only; unreadable is "unknown"
        return None


def _image_sizes(image) -> list[tuple[int, int]]:
    """Pixel sizes of every buffer Cycles would load for ``image``, WITHOUT loading it.

    ``Image.size`` loads an image that is not in memory yet, which is exactly the cost
    this estimate is trying to avoid, so unloaded images are measured from the file
    header (per tile for a tiled image).
    """
    source = str(getattr(image, "source", "") or "")
    if source == "TILED":
        sizes = []
        for tile in getattr(image, "tiles", None) or ():
            try:
                size = tuple(int(value) for value in tile.size)
            except Exception:  # noqa: BLE001
                size = (0, 0)
            if size[0] > 0 and size[1] > 0:
                sizes.append(size)
        return sizes
    if bool(getattr(image, "has_data", False)) or source in {"GENERATED", "VIEWER"}:
        try:
            width, height = (int(value) for value in image.size)
            return [(width, height)] if width > 0 and height > 0 else []
        except Exception:  # noqa: BLE001
            return []
    path = ""
    try:
        import bpy  # noqa: PLC0415

        path = bpy.path.abspath(str(getattr(image, "filepath", "") or ""), library=getattr(image, "library", None))
    except Exception:  # noqa: BLE001
        path = str(getattr(image, "filepath", "") or "")
    size = _file_image_size(path) if path else None
    return [size] if size else []


def estimate_scene_bytes(sources, targets, *, others=(), depsgraph=None, evaluated: bool = False) -> int:
    """What Cycles allocates for the scene one bake syncs, before any bake buffer.

    Evaluated high triangles (``sources`` and ``others``) cost
    ``CYCLES_HIGH_TRIANGLE_BYTES``, low triangles ``CYCLES_LOW_TRIANGLE_BYTES``, and
    every image reachable from their materials (node groups included) its pixel
    storage. Unknown objects count as zero: an estimate never blocks on a stale
    reference. ``evaluated`` says the objects are already modifier-evaluated.
    """
    if evaluated:
        depsgraph = None  # the caller already passes evaluated objects
    elif depsgraph is None:
        depsgraph = _evaluated_depsgraph()
    seen: set = set()
    images: dict = {}
    visited_trees: set = set()
    total = 0
    roles = (
        (sources, constants.CYCLES_HIGH_TRIANGLE_BYTES),
        (others, constants.CYCLES_HIGH_TRIANGLE_BYTES),
        (targets, constants.CYCLES_LOW_TRIANGLE_BYTES),
    )
    for objects, per_triangle in roles:
        for obj in objects or ():
            if obj is None:
                continue
            key = _datablock_key(obj)
            if key in seen:
                continue
            seen.add(key)
            total += _triangle_count(obj, depsgraph) * int(per_triangle)
            for slot in getattr(obj, "material_slots", None) or ():
                material = getattr(slot, "material", None)
                if material is not None:
                    _node_tree_images(getattr(material, "node_tree", None), images, visited_trees)
    for image in images.values():
        try:
            per_texel = _image_texel_bytes(image)
            for width, height in _image_sizes(image):
                total += int(width) * int(height) * per_texel
        except Exception:  # noqa: BLE001 - one odd image must not fail the estimate
            continue
    return int(total)


# --------------------------------------------------------------------------- strips


@dataclass(frozen=True)
class Strip:
    """One bake window of ``StripPlan.strip_rows`` rows and the rows it keeps.

    Rows are image rows as Blender stores them (row 0 at the bottom, V = 0).
    """

    window_start: int
    keep_start: int
    keep_end: int


@dataclass(frozen=True)
class StripPlan:
    width: int
    height: int
    apron: int
    strip_rows: int
    strips: tuple
    bytes_per_texel: int = 0
    scene_bytes: int = 0
    what: str = ""
    group: str = ""
    #: Refuse at run time when a strip no longer fits (False when the guard is off).
    enforce: bool = True

    @property
    def single(self) -> bool:
        return len(self.strips) <= 1 and self.strip_rows >= self.height

    @property
    def count(self) -> int:
        return len(self.strips)

    def strip_bytes(self) -> int:
        return int(self.width) * int(self.strip_rows) * int(self.bytes_per_texel)

    def top_down(self) -> list:
        """Strips in the order the final file's scanlines are written."""
        return sorted(self.strips, key=lambda strip: strip.keep_start, reverse=True)


def strip_windows(height: int, apron: int, strip_rows: int) -> tuple:
    """Partition rows [0, height) into kept ranges of windows ``strip_rows`` tall.

    The first window starts at row 0, every later one ``apron`` rows below its first
    kept row, and a window that would pass the top is clamped to end on it, so every
    kept row has ``apron`` rows of real bake on each side that is not an image edge.
    """
    height = int(height)
    apron = max(0, int(apron))
    strip_rows = int(strip_rows)
    if strip_rows >= height:
        return (Strip(0, 0, height),)
    if strip_rows <= 2 * apron:
        raise ValueError(f"strip of {strip_rows} rows cannot hold a {apron}-row apron on both sides")
    strips = []
    keep_start = 0
    while keep_start < height:
        window_start = 0 if keep_start == 0 else keep_start - apron
        if window_start + strip_rows >= height:
            window_start = height - strip_rows
            keep_end = height
        else:
            keep_end = window_start + strip_rows - apron
        strips.append(Strip(window_start, keep_start, keep_end))
        keep_start = keep_end
    return tuple(strips)


def refusal_message(what: str, group: str, width: int, height: int, need: int, available: int) -> str:
    subject = f"{what} for '{group}'" if group else str(what or "this map")
    return (
        f"Cycles cannot bake {subject} at {int(width)}x{int(height)}: it needs about "
        f"{format_gb(need)} of free memory but only {format_gb(available)} is available. "
        "Close other applications, lower the resolution, or split the bake group."
    )


_UNSET = object()
#: Pass as ``memory=`` to measure the machine now (the default of every planner).
MEASURE = _UNSET


def plan_strips(
    width: int,
    height: int,
    *,
    apron: int,
    bytes_per_texel: int,
    scene_bytes: int = 0,
    memory=_UNSET,
    max_texels: int | None = None,
    what: str = "",
    group: str = "",
) -> StripPlan:
    """The fewest equal-height strips whose bake fits the free memory and area cap.

    ``memory`` defaults to :func:`system_memory` (None = unmeasurable: only the area
    cap applies). Raises :class:`CyclesMemoryError` when even the smallest strip
    (``max(CYCLES_STRIP_MIN_ROWS, 4 * apron)`` rows) does not fit.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    apron = max(0, int(apron))
    per_texel = max(1, int(bytes_per_texel))
    strip_per_texel = per_texel + int(constants.CYCLES_STRIP_ASSEMBLY_BYTES_PER_TEXEL)
    scene_bytes = max(0, int(scene_bytes or 0))
    fixed_bytes = scene_bytes + int(constants.CYCLES_BAKE_FIXED_BYTES)
    if memory is _UNSET:
        memory = system_memory()
    enforce = memory_guard_enabled() and memory is not None
    if max_texels is None:
        max_texels = strip_max_texels()
    min_rows = min(height, max(int(constants.CYCLES_STRIP_MIN_ROWS), 4 * apron))

    def plan(rows: int, *, texel_bytes: int) -> StripPlan:
        return StripPlan(
            width=width,
            height=height,
            apron=apron,
            strip_rows=int(rows),
            strips=strip_windows(height, apron, rows),
            bytes_per_texel=texel_bytes,
            scene_bytes=scene_bytes,
            what=str(what or ""),
            group=str(group or ""),
            enforce=enforce,
        )

    budget = None
    if memory is not None:
        budget = memory.available - memory_reserve_bytes(memory.total_physical) - fixed_bytes
    area_rows = max(min_rows, int(max_texels) // width)
    if area_rows >= height and (budget is None or budget >= width * height * per_texel):
        return plan(height, texel_bytes=per_texel)

    memory_rows = height if budget is None else (budget // (width * strip_per_texel) if budget > 0 else 0)
    max_rows = int(min(height - 1, area_rows, memory_rows))
    if max_rows < min_rows:
        if enforce:
            need = fixed_bytes + width * min_rows * strip_per_texel + memory_reserve_bytes(memory.total_physical)
            raise CyclesMemoryError(refusal_message(what, group, width, height, need, memory.available))
        max_rows = min_rows
        if max_rows >= height:
            return plan(height, texel_bytes=per_texel)
    target = len(strip_windows(height, apron, max_rows))
    # Same strip count, least memory: the smallest height that still needs no more strips.
    low, high = min_rows, max_rows
    while low < high:
        middle = (low + high) // 2
        if len(strip_windows(height, apron, middle)) <= target:
            high = middle
        else:
            low = middle + 1
    return plan(low, texel_bytes=strip_per_texel)


def strip_plan_from_rows(
    width: int,
    height: int,
    *,
    apron: int,
    strip_rows: int,
    bytes_per_texel: int,
    scene_bytes: int = 0,
    what: str = "",
    group: str = "",
) -> StripPlan:
    """Rebuild the plan a planner already chose (the step stores only the row count)."""
    strip_rows = min(int(height), max(1, int(strip_rows)))
    per_texel = int(bytes_per_texel)
    if strip_rows < int(height):
        per_texel += int(constants.CYCLES_STRIP_ASSEMBLY_BYTES_PER_TEXEL)
    return StripPlan(
        width=int(width),
        height=int(height),
        apron=int(apron),
        strip_rows=strip_rows,
        strips=strip_windows(height, apron, strip_rows),
        bytes_per_texel=per_texel,
        scene_bytes=max(0, int(scene_bytes or 0)),
        what=str(what or ""),
        group=str(group or ""),
        enforce=memory_guard_enabled(),
    )


def check_strip_fits(plan: StripPlan, *, memory=_UNSET, credit_bytes: int = 0) -> None:
    """Refuse the next strip if the machine no longer has room for it.

    ``credit_bytes`` is memory this process just released and may still hold (the
    previous strip): the allocator can hand it straight back, so it is not counted
    against the budget a second time.
    """
    if not plan.enforce:
        return
    if memory is _UNSET:
        memory = system_memory()
    if memory is None:
        return
    reserve = memory_reserve_bytes(memory.total_physical)
    need = plan.scene_bytes + int(constants.CYCLES_BAKE_FIXED_BYTES) + plan.strip_bytes()
    if need + reserve <= memory.available + max(0, int(credit_bytes)):
        return
    raise CyclesMemoryError(
        refusal_message(plan.what, plan.group, plan.width, plan.height, need + reserve, memory.available)
    )


def scene_exceeds_memory(scene_bytes: int, *, memory=_UNSET) -> SystemMemory | None:
    """The measured memory when ``scene_bytes`` alone is more than is free, else None."""
    if not memory_guard_enabled() or int(scene_bytes or 0) <= 0:
        return None
    if memory is _UNSET:
        memory = system_memory()
    if memory is None:
        return None
    return memory if int(scene_bytes) > memory.available else None


# --------------------------------------------------------------------------- UV layers


def _render_uv_layer(mesh):
    """The UV layer a bake rasterizes when no uv_layer is passed: active_render."""
    layers = getattr(mesh, "uv_layers", None)
    if layers is None:
        return None
    for layer in layers:
        if bool(getattr(layer, "active_render", False)):
            return layer
    return getattr(layers, "active", None)


def _bake_uv_layer(mesh, layer_name: str = ""):
    """The UV layer a bake rasterizes: the named ``uv_layer`` if given, else active_render."""
    if not layer_name:
        return _render_uv_layer(mesh)
    layers = getattr(mesh, "uv_layers", None)
    if layers is None:
        return None
    return layers.get(layer_name)


_MAX_UV_LAYERS = 8


@dataclass
class _MeshUV:
    mesh: object
    source_name: str
    pristine: object  # float64 (loops, 2)
    backup: object = None  # float32 flat, in-place mode only


@dataclass
class StripUVLayers:
    """Temporary strip UVs for every low mesh a striped bake rasterizes.

    ``open()`` adds ``CYCLES_STRIP_UV_LAYER_NAME`` to each distinct low mesh (a linked
    duplicate is visited once) and snapshots the render UVs in float64; ``set_window``
    rewrites it for one strip; ``close()`` removes it. The source layer, the active
    and active-render flags and every other layer are left exactly as found.

    A mesh already at Blender's 8 UV layers cannot take another. With
    ``allow_in_place`` (every pass is selected-to-active, so no shading reads the
    low's UVs) the render layer itself is transformed and restored bit-exactly on
    close; otherwise ``open()`` refuses with an artist-facing message.

    ``source_layer_name`` is the group's bake UV set (the bake ``uv_layer``): the
    strip UVs derive from that layer instead of active_render. active_render itself
    is never moved, because it is also the layer un-wired Image Texture nodes sample.
    """

    objects: list
    tile_u: float = 0.0
    tile_v: float = 0.0
    height: int = 1
    allow_in_place: bool = False
    in_place: bool = False
    source_layer_name: str = ""
    _meshes: list = field(default_factory=list)

    @property
    def layer_name(self) -> str:
        """``uv_layer`` for bpy.ops.object.bake.

        In the in-place fallback the source layer itself carries the strip UVs: ""
        (the bake reads active_render) unless a named source layer was given.
        """
        if self.in_place:
            return str(self.source_layer_name or "")
        return constants.CYCLES_STRIP_UV_LAYER_NAME

    def open(self) -> "StripUVLayers":
        import numpy as np

        seen = set()
        meshes = []
        for obj in self.objects or ():
            mesh = getattr(obj, "data", None)
            if mesh is None or not hasattr(mesh, "uv_layers"):
                continue
            key = _datablock_key(mesh)
            if key in seen:
                continue
            seen.add(key)
            source = _bake_uv_layer(mesh, self.source_layer_name)
            if source is None:
                if self.source_layer_name:
                    raise RuntimeError(
                        f"'{getattr(obj, 'name', '?')}' has no UV map named "
                        f"'{self.source_layer_name}' to bake into"
                    )
                raise RuntimeError(f"'{getattr(obj, 'name', '?')}' has no UV map to bake into")
            meshes.append((obj, mesh, source))
        def free_slots(mesh):
            # A strip layer left behind by a bake Blender crashed out of is reused.
            stale = mesh.uv_layers.get(constants.CYCLES_STRIP_UV_LAYER_NAME) is not None
            return _MAX_UV_LAYERS - len(mesh.uv_layers) + (1 if stale else 0)

        full = [obj for obj, mesh, _source in meshes if free_slots(mesh) <= 0]
        if full:
            if not self.allow_in_place:
                names = ", ".join(f"'{getattr(obj, 'name', '?')}'" for obj in full)
                raise CyclesMemoryError(
                    f"Cycles has to bake this map in strips to fit in memory, which needs one free "
                    f"UV map slot on {names}, but it already has 8 UV maps. Remove an unused UV map "
                    "or lower the resolution."
                )
            self.in_place = True
        for _obj, mesh, source in meshes:
            count = len(mesh.loops)
            flat = np.empty(count * 2, dtype=np.float32)
            source.data.foreach_get("uv", flat)
            entry = _MeshUV(mesh, str(source.name), flat.reshape(-1, 2).astype(np.float64))
            if self.in_place:
                entry.backup = flat
            else:
                layers = mesh.uv_layers
                active_index = layers.active_index
                render_name = str(source.name)
                if self.source_layer_name:
                    # A named source is not necessarily the render layer: keep the
                    # artist's active_render (the material texture lookup) where it is.
                    render = _render_uv_layer(mesh)
                    render_name = str(render.name) if render is not None else ""
                stale = layers.get(constants.CYCLES_STRIP_UV_LAYER_NAME)
                if stale is not None:
                    # Left behind by a bake Blender crashed out of: never the artist's.
                    layers.remove(stale)
                layers.new(name=constants.CYCLES_STRIP_UV_LAYER_NAME, do_init=False)
                layers.active_index = active_index
                render = layers.get(render_name)
                if render is not None and not render.active_render:
                    render.active_render = True
            self._meshes.append(entry)
        return self

    def set_window(self, window_start: int, strip_rows: int) -> None:
        import numpy as np

        height = float(self.height)
        for entry in self._meshes:
            uv = entry.pristine.copy()
            uv[:, 0] -= float(self.tile_u)
            uv[:, 1] = ((uv[:, 1] - float(self.tile_v)) * height - float(window_start)) / float(strip_rows)
            name = entry.source_name if self.in_place else constants.CYCLES_STRIP_UV_LAYER_NAME
            layer = entry.mesh.uv_layers.get(name)
            if layer is None:
                raise RuntimeError(f"UV map '{name}' disappeared during a striped bake")
            layer.data.foreach_set("uv", uv.astype(np.float32).reshape(-1))
            try:
                entry.mesh.update()
            except Exception:  # noqa: BLE001 - a tag failure must not skip the restore
                pass

    def close(self) -> None:
        entries, self._meshes = self._meshes, []
        for entry in entries:
            try:
                layers = entry.mesh.uv_layers
                if self.in_place:
                    layer = layers.get(entry.source_name)
                    if layer is not None and entry.backup is not None:
                        layer.data.foreach_set("uv", entry.backup)
                else:
                    layer = layers.get(constants.CYCLES_STRIP_UV_LAYER_NAME)
                    if layer is not None:
                        active_index = layers.active_index
                        layers.remove(layer)
                        if 0 <= active_index < len(layers):
                            layers.active_index = active_index
                entry.mesh.update()
            except Exception:  # noqa: BLE001 - restore every other mesh regardless
                continue

    def __enter__(self):
        return self.open()

    def __exit__(self, *_exc):
        self.close()
        return False


# --------------------------------------------------------------------------- assembly

_BLENDER_FORMAT_BY_SUFFIX = {
    ".tga": "TARGA_RAW",
    ".png": "PNG",
    ".exr": "OPEN_EXR",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
}
_OIIO_FORMAT = {
    "TARGA_RAW": "targa",
    "PNG": "png",
    "OPEN_EXR": "openexr",
    "TIFF": "tiff",
    "JPEG": "jpeg",
}
#: How each final format's strips are saved by Blender. JPEG goes through 8-bit TGA
#: (lossless, always 8-bit) and is encoded once, so the seams carry no double loss.
_PART_FORMAT = {"JPEG": ("TARGA_RAW", ".tga")}
_PART_SUFFIX = {"TARGA_RAW": ".tga", "PNG": ".png", "OPEN_EXR": ".exr", "TIFF": ".tif"}
#: Throwaway image each strip is saved through (never saved into the .blend: removed
#: right after the save).
_PART_IMAGE_NAME = "__mb_bake_target_strip_part__"


def blender_file_format(path) -> str:
    """The Blender file format the bake paths save ``path`` as (EXR by default)."""
    return _BLENDER_FORMAT_BY_SUFFIX.get(Path(path).suffix.lower(), "OPEN_EXR")


def blender_exr_save_decodes_srgb(image, file_format: str) -> bool:
    """Would Blender's own save corrupt this image's values?

    Saving a BYTE buffer as EXR decodes it as sRGB even when its colour space is
    Non-Color (measured on 5.2: 0.5 is written as 0.216), so every 8-bit Cycles
    projection map saved to EXR came out darkened: a flat normal read
    (0.216, 0.212, 1.0) instead of (0.5, 0.5, 1.0). Float buffers save unchanged.
    """
    if file_format != "OPEN_EXR" or bool(getattr(image, "is_float", True)):
        return False
    settings = getattr(image, "colorspace_settings", None)
    return bool(getattr(settings, "is_data", False))


def write_data_exr(path, rgba_bottom_up) -> None:
    """Write Blender-ordered (bottom-up) RGBA pixels as a half-float EXR, values untouched.

    Half RGBA, uncompressed: the layout Blender itself gives a byte buffer saved as
    EXR, so the file is the same size it always was, only no longer sRGB-decoded.
    """
    import numpy as np
    import OpenImageIO as oiio  # noqa: PLC0415 - bundled with Blender 5.1+

    pixels = np.ascontiguousarray(np.asarray(rgba_bottom_up, dtype=np.float32)[::-1])
    height, width = int(pixels.shape[0]), int(pixels.shape[1])
    spec = oiio.ImageSpec(width, height, 4, "half")
    spec.channelnames = ("R", "G", "B", "A")
    spec.alpha_channel = 3
    spec.attribute("compression", "none")
    output = oiio.ImageOutput.create("openexr")
    if output is None:
        raise RuntimeError(f"no EXR writer: {oiio.geterror()}")
    if not output.open(str(path), spec):
        raise RuntimeError(f"could not open {Path(path).name} for writing: {output.geterror()}")
    try:
        if not output.write_image(pixels):
            raise RuntimeError(f"could not write {Path(path).name}: {output.geterror()}")
    finally:
        output.close()


class StripAssembler:
    """Writes a striped bake into ``output_path`` one strip at a time.

    Strips must arrive top-down (:meth:`StripPlan.top_down`): each is saved by
    Blender in the final format, so colour management, bit depth and quantisation
    are Blender's own, and its kept rows are appended as scanlines to a temporary
    file beside the output. :meth:`commit` moves that file over the output;
    :meth:`abort` (idempotent, also after commit) removes every temporary, so a
    failed bake keeps the previous output untouched.
    """

    def __init__(self, output_path, width: int, height: int):
        self.output_path = Path(output_path)
        self.width = int(width)
        self.height = int(height)
        self.file_format = blender_file_format(self.output_path)
        part_format, part_suffix = _PART_FORMAT.get(
            self.file_format, (self.file_format, _PART_SUFFIX.get(self.file_format, ".exr"))
        )
        self.part_format = part_format
        directory = self.output_path.parent
        directory.mkdir(parents=True, exist_ok=True)
        token = f"{os.getpid()}_{id(self):x}"
        self._temp_path = directory / f".fyr_strip_{token}{self.output_path.suffix or '.exr'}"
        self._part_path = directory / f".fyr_strip_{token}_part{part_suffix}"
        self._out = None
        self._next_row = 0
        self._committed = False

    @property
    def rows_written(self) -> int:
        return self._next_row

    def _read_part(self, rows: int):
        import OpenImageIO as oiio  # noqa: PLC0415 - bundled with Blender 5.1+

        handle = oiio.ImageInput.open(str(self._part_path))
        if handle is None:
            raise RuntimeError(f"could not read the baked strip back: {oiio.geterror()}")
        try:
            spec = handle.spec()
            if int(spec.width) != self.width or int(spec.height) != int(rows):
                raise RuntimeError(
                    f"baked strip is {spec.width}x{spec.height}, expected {self.width}x{rows}"
                )
            pixels = handle.read_image(0, 0, 0, spec.nchannels, spec.format)
            if pixels is None:
                raise RuntimeError(f"could not read the baked strip back: {handle.geterror()}")
            return spec, pixels
        finally:
            handle.close()

    def _save_part(self, image, strip: Strip, strip_rows: int) -> None:
        """Save the kept rows of ``image`` with Blender, through a throwaway image.

        Saving the bake image itself would turn it into a FILE image pointing at the
        part file, and Blender then drops its buffer: the next strip could not bake
        into it. The copy has the same buffer type and colour space, so Blender's
        conversion to the file format is the one it applies to a whole-image save.
        """
        import bpy  # noqa: PLC0415
        import numpy as np

        first = strip.keep_start - strip.window_start
        rows = strip.keep_end - strip.keep_start
        flat = np.empty(self.width * int(strip_rows) * 4, dtype=np.float32)
        image.pixels.foreach_get(flat)
        kept = np.ascontiguousarray(flat.reshape(int(strip_rows), self.width, 4)[first:first + rows])
        del flat
        if blender_exr_save_decodes_srgb(image, self.part_format):
            write_data_exr(self._part_path, kept)
            return
        part = bpy.data.images.new(
            _PART_IMAGE_NAME, width=self.width, height=rows, alpha=True,
            float_buffer=bool(getattr(image, "is_float", True)),
        )
        try:
            part.colorspace_settings.name = image.colorspace_settings.name
            try:
                part.alpha_mode = image.alpha_mode
            except (AttributeError, TypeError, ValueError):
                pass
            part.pixels.foreach_set(kept.reshape(-1))
            del kept
            part.filepath_raw = str(self._part_path)
            part.file_format = self.part_format
            part.save()
        finally:
            bpy.data.images.remove(part)

    def _open_output(self, part_spec) -> None:
        import OpenImageIO as oiio  # noqa: PLC0415

        channels = int(part_spec.nchannels)
        if self.file_format == "JPEG":
            channels = min(3, channels)
        spec = oiio.ImageSpec(self.width, self.height, channels, part_spec.format)
        names = list(part_spec.channelnames)[:channels]
        if len(names) == channels:
            spec.channelnames = tuple(names)
        if channels == 4 and part_spec.alpha_channel >= 0:
            spec.alpha_channel = part_spec.alpha_channel
        compression = part_spec.get_string_attribute("compression")
        if self.file_format in {"OPEN_EXR", "TIFF"} and compression:
            spec.attribute("compression", compression)
        if self.file_format == "PNG":
            spec.attribute("png:compressionLevel", int(constants.CYCLES_STRIP_PNG_COMPRESSION_LEVEL))
        if self.file_format == "JPEG":
            spec.attribute("CompressionQuality", int(constants.CYCLES_STRIP_JPEG_QUALITY))
        output = oiio.ImageOutput.create(_OIIO_FORMAT.get(self.file_format, "openexr"))
        if output is None:
            raise RuntimeError(f"no image writer for {self.file_format}: {oiio.geterror()}")
        if not output.open(str(self._temp_path), spec):
            raise RuntimeError(f"could not open {self._temp_path.name} for writing: {output.geterror()}")
        self._out = output
        self._channels = channels

    def add_strip(self, image, strip: Strip, strip_rows: int) -> None:
        """Save ``image`` (one finished strip window) and append its kept rows."""
        expected = self.height - strip.keep_end
        if expected != self._next_row:
            raise RuntimeError("strips must be assembled top-down without gaps")
        rows = strip.keep_end - strip.keep_start
        try:
            self._save_part(image, strip, strip_rows)
            spec, pixels = self._read_part(rows)
        finally:
            self._remove(self._part_path)
        if self._out is None:
            self._open_output(spec)
        if pixels.ndim == 3 and pixels.shape[2] != self._channels:
            pixels = pixels[:, :, : self._channels].copy()
        if not self._out.write_scanlines(expected, expected + rows, 0, pixels):
            raise RuntimeError(f"could not write the baked strip: {self._out.geterror()}")
        self._next_row += rows

    def commit(self) -> str:
        if self._next_row != self.height or self._out is None:
            raise RuntimeError(
                f"striped bake is incomplete: {self._next_row} of {self.height} rows written"
            )
        output, self._out = self._out, None
        if not output.close():
            raise RuntimeError(f"could not finish {self.output_path.name}: {output.geterror()}")
        os.replace(str(self._temp_path), str(self.output_path))
        self._committed = True
        return str(self.output_path)

    def abort(self) -> None:
        output, self._out = self._out, None
        if output is not None:
            try:
                output.close()
            except Exception:  # noqa: BLE001 - removal below must still happen
                pass
        self._remove(self._part_path)
        if not self._committed:
            self._remove(self._temp_path)

    @staticmethod
    def _remove(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------- helpers


def apron_rows(margin: int, *, filter_radius: int = 0) -> int:
    """Rows of overlap a strip needs: EXTEND margin + post filter radius + 1 gradient row."""
    return max(0, int(margin)) + max(0, int(filter_radius)) + 1
