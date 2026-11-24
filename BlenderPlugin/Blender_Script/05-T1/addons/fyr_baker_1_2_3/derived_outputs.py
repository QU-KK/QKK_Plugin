"""Outputs the addon finishes itself after a bake: Derivative, Wireframe and Lit Color.

Both are recorded at prepare time in ``derived_outputs.json`` in the job workspace and
applied by :func:`apply_workspace_derived_outputs`, which every successful completion
path runs right after ``material_detail.apply_workspace_material_detail`` (so a Normal's
material-detail layer is already in the source a Derivative is converted from).

* DERIVATIVE: a tangent Normal row whose Output is Derivative. The backend bakes an
  ordinary OpenGL tangent normal into a hidden source file (incremental live bakes keep
  updating that real normal); this converts the whole source to slopes (-x/z, -y/z)
  and writes the artist's file.
* WIREFRAME: the low poly's UV edges, drawn anti-aliased. Never part of the backend
  job. Drawn on the GPU when Blender has a window, otherwise by a numpy rasterizer.
* NORMAL_RELIEF: a material-workflow Normal the GPU baked. Runs the Relief post-passes
  (glitter wash, grain smooth, slope clamp, weak-slope lift) the Cycles route applies,
  in place, so both routes give the row the same look.
* LIT_COLOR: a Scene Lighting row whose Output is Lit Color. The bake writes three
  hidden linear EXR sources from the same projection: the scene lighting (denoised on
  its own), the high materials' Base Color and, when anything emits, their Emission.
  This writes ``albedo * lighting + emission`` and deletes the sources. Keeping the
  texture out of the lighting solve keeps the denoiser away from it, so texture detail
  stays sharp.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import rna_buffers
from . import constants

SIDECAR_NAME = "derived_outputs.json"
KIND_DERIVATIVE = "DERIVATIVE"
KIND_WIREFRAME = "WIREFRAME"
KIND_LIT_COLOR = "LIT_COLOR"
KIND_NORMAL_RELIEF = "NORMAL_RELIEF"
#: Hidden folder (under the output root's .fyr_baker) holding Derivative rows' normal sources.
DERIVATIVE_SOURCE_DIR_NAME = "derivative_sources"
#: Hidden folder holding Lit Color rows' lighting / albedo / emission sources.
LIT_COLOR_SOURCE_DIR_NAME = "lit_color_sources"
#: Map uuids of a Lit Color row's hidden material sources: the row's own uuid plus these.
LIT_COLOR_ALBEDO_UUID_SUFFIX = "#lit-albedo"
LIT_COLOR_EMISSION_UUID_SUFFIX = "#lit-emission"
_SCANLINE_CHUNK = 256


def derivative_source_dir(output_root, project_name: str) -> Path:
    from . import naming

    return Path(output_root) / ".fyr_baker" / DERIVATIVE_SOURCE_DIR_NAME / naming.sanitize_token(project_name)


def lit_color_source_dir(output_root, project_name: str) -> Path:
    from . import naming

    return Path(output_root) / ".fyr_baker" / LIT_COLOR_SOURCE_DIR_NAME / naming.sanitize_token(project_name)


def lit_color_source_paths(source_dir, final_name: str) -> dict[str, str]:
    """Hidden source files of one Lit Color output, all linear EXR next to each other."""
    stem = Path(final_name).stem
    base = Path(source_dir)
    return {
        "lighting": str(base / f"{stem}.exr"),
        "albedo": str(base / f"{stem}__albedo.exr"),
        "emission": str(base / f"{stem}__emission.exr"),
    }


def write_sidecar(workspace_path, entries: list[dict]) -> None:
    path = Path(workspace_path) / SIDECAR_NAME
    if entries:
        path.write_text(json.dumps({"version": 1, "entries": entries}, indent=2), encoding="utf-8")
    elif path.exists():
        path.unlink()


def read_sidecar(workspace_path) -> list[dict]:
    path = Path(workspace_path) / SIDECAR_NAME
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [entry for entry in payload.get("entries", []) if isinstance(entry, dict)]


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


# ---------------------------------------------------------------------------------------
# Derivative
# ---------------------------------------------------------------------------------------


def normals_to_derivative(rgb, *, max_slope: float, flip_green: bool):
    """Encoded OpenGL tangent normals (..., 3) in 0..1 -> derivative RGB in 0..1.

    R/G = 0.5 + slope * 0.5 / max_slope, clamped; B = 0. A slope steeper than
    ``max_slope`` clips, and a normal at or past the horizon (z <= 0) takes the
    steepest representable slope in its direction.
    """
    import numpy as np

    n = rgb[..., :3].astype(np.float32) * 2.0 - 1.0
    nz = np.maximum(n[..., 2], 1e-4)
    slope_u = -n[..., 0] / nz
    slope_v = -n[..., 1] / nz
    if flip_green:
        slope_v = -slope_v
    scale = 0.5 / max(float(max_slope), 1e-6)
    out = np.zeros(rgb.shape[:-1] + (3,), dtype=np.float32)
    out[..., 0] = np.clip(0.5 + slope_u * scale, 0.0, 1.0)
    out[..., 1] = np.clip(0.5 + slope_v * scale, 0.0, 1.0)
    return out


def convert_normal_file_to_derivative(source_path, final_path, *, max_slope: float, flip_green: bool) -> None:
    """Stream ``source_path`` (a tangent normal map) into a derivative map at ``final_path``.

    Scanline chunks keep memory bounded at any resolution; the output keeps the source's
    size, channel count, pixel type and file format.
    """
    import numpy as np
    import OpenImageIO as oiio

    source = oiio.ImageInput.open(str(source_path))
    if source is None:
        raise RuntimeError(f"Could not open {source_path}: {oiio.geterror()}")
    try:
        spec = source.spec()
        width, height, channels = int(spec.width), int(spec.height), int(spec.nchannels)
        if channels < 3:
            raise RuntimeError(f"{source_path} has {channels} channel(s); a normal map needs 3")
        out_spec = oiio.ImageSpec(width, height, channels, spec.format)
        for attribute in ("oiio:BitsPerSample", "compression"):
            value = spec.getattribute(attribute)
            if value is not None:
                out_spec.attribute(attribute, value)
        final = Path(final_path)
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary = final.with_name(final.stem + ".fyrtmp" + final.suffix)
        output = oiio.ImageOutput.create(str(temporary))
        if output is None or not output.open(str(temporary), out_spec):
            raise RuntimeError(f"Could not write {final_path}: {oiio.geterror()}")
        try:
            for y0 in range(0, height, _SCANLINE_CHUNK):
                y1 = min(height, y0 + _SCANLINE_CHUNK)
                rows = source.read_scanlines(0, 0, y0, y1, 0, 0, channels, oiio.FLOAT)
                if rows is None:
                    raise RuntimeError(f"Could not read {source_path}: {source.geterror()}")
                rows = np.asarray(rows, dtype=np.float32).reshape(y1 - y0, width, channels)
                converted = np.empty_like(rows)
                converted[..., :3] = normals_to_derivative(rows, max_slope=max_slope, flip_green=flip_green)
                if channels > 3:
                    converted[..., 3:] = rows[..., 3:]
                if not output.write_scanlines(y0, y1, 0, converted):
                    raise RuntimeError(f"Could not write {final_path}: {output.geterror()}")
        finally:
            output.close()
    finally:
        source.close()
    os.replace(temporary, final)


def apply_normal_relief_file(path, *, relief: float) -> None:
    """Rewrite the tangent normal map at *path* with the Relief post-passes applied.

    The passes look at the whole image (neighbourhood wash, a percentile peak), so the
    file is read whole. Size, channel count, pixel type and format are kept.
    """
    import numpy as np
    import OpenImageIO as oiio

    from . import blender_bake

    source = oiio.ImageInput.open(str(path))
    if source is None:
        raise RuntimeError(f"Could not open {path}: {oiio.geterror()}")
    try:
        spec = source.spec()
        width, height, channels = int(spec.width), int(spec.height), int(spec.nchannels)
        if channels < 3:
            raise RuntimeError(f"{path} has {channels} channel(s); a normal map needs 3")
        pixels = source.read_image(0, 0, 0, channels, oiio.FLOAT)
        if pixels is None:
            raise RuntimeError(f"Could not read {path}: {source.geterror()}")
        out_spec = oiio.ImageSpec(width, height, channels, spec.format)
        for attribute in ("oiio:BitsPerSample", "compression"):
            value = spec.getattribute(attribute)
            if value is not None:
                out_spec.attribute(attribute, value)
    finally:
        source.close()
    pixels = np.asarray(pixels, dtype=np.float32).reshape(height, width, channels)
    # Blender's pixel order is bottom-up, which the passes were written against.
    rgba = np.ones((height, width, 4), dtype=np.float32)
    rgba[..., : min(channels, 4)] = pixels[::-1, :, : min(channels, 4)]
    blender_bake.finalize_tangent_normal_pixels(rgba, relief=relief)
    pixels[..., :3] = rgba[::-1, :, :3]
    final = Path(path)
    temporary = final.with_name(final.stem + ".fyrtmp" + final.suffix)
    output = oiio.ImageOutput.create(str(temporary))
    if output is None or not output.open(str(temporary), out_spec):
        raise RuntimeError(f"Could not write {path}: {oiio.geterror()}")
    try:
        if not output.write_image(pixels):
            raise RuntimeError(f"Could not write {path}: {output.geterror()}")
    finally:
        output.close()
    os.replace(temporary, final)


# ---------------------------------------------------------------------------------------
# Wireframe
# ---------------------------------------------------------------------------------------


def mesh_uv_edges(mesh, uv_layer_name: str = "", *, triangles: bool = False):
    """(n, 2, 2) float32 UV segments of ``mesh``: polygon edges, or every triangle edge.

    Each face contributes its own UV edges, so seams draw on both islands. A shared
    edge inside an island is kept once.
    """
    import numpy as np

    uv_layers = getattr(mesh, "uv_layers", None)
    layer = None
    if uv_layers is not None:
        layer = uv_layers.get(uv_layer_name) if uv_layer_name else getattr(uv_layers, "active", None)
    if layer is None:
        return np.zeros((0, 2, 2), dtype=np.float32)
    loop_count = len(mesh.loops)
    uvs = np.empty(loop_count * 2, dtype=np.float32)
    layer.data.foreach_get("uv", uvs)
    uvs = uvs.reshape(loop_count, 2)
    if triangles:
        mesh.calc_loop_triangles()
        tri_count = len(mesh.loop_triangles)
        tri_loops = rna_buffers.empty_u32_for_rna(tri_count * 3)
        mesh.loop_triangles.foreach_get("loops", tri_loops)
        tri_loops = tri_loops.astype(np.int64).reshape(tri_count, 3)
        a = tri_loops.reshape(-1)
        b = np.roll(tri_loops, -1, axis=1).reshape(-1)
    else:
        poly_count = len(mesh.polygons)
        starts = rna_buffers.empty_u32_for_rna(poly_count)
        totals = rna_buffers.empty_u32_for_rna(poly_count)
        mesh.polygons.foreach_get("loop_start", starts)
        mesh.polygons.foreach_get("loop_total", totals)
        starts = starts.astype(np.int64)
        totals = totals.astype(np.int64)
        a = np.arange(loop_count, dtype=np.int64)
        owner_start = np.repeat(starts, totals)
        owner_end = owner_start + np.repeat(totals, totals)
        b = np.where(a + 1 < owner_end, a + 1, owner_start)
    segments = np.stack([uvs[a], uvs[b]], axis=1)
    return dedupe_segments(segments)


def dedupe_segments(segments):
    import numpy as np

    if segments.shape[0] == 0:
        return segments.astype(np.float32)
    segments = segments[np.isfinite(segments).all(axis=(1, 2)) & (np.abs(segments) < 1e9).all(axis=(1, 2))]
    if segments.shape[0] == 0:
        return segments.astype(np.float32)
    # Order each segment's endpoints so (p, q) and (q, p) compare equal.
    swap = (segments[:, 0, 0] > segments[:, 1, 0]) | (
        (segments[:, 0, 0] == segments[:, 1, 0]) & (segments[:, 0, 1] > segments[:, 1, 1])
    )
    ordered = segments.copy()
    ordered[swap] = ordered[swap][:, ::-1]
    keys = np.round(ordered.reshape(-1, 4).astype(np.float64) * 1e6).astype(np.int64)
    _unique, first = np.unique(keys, axis=0, return_index=True)
    return ordered[np.sort(first)].astype(np.float32)


def segments_to_pixels(segments, width: int, height: int, tile_u: float = 0.0, tile_v: float = 0.0):
    """UV segments -> (p0, p1) pixel coordinates (x right, y down, pixel centres at +0.5),
    keeping only segments that can touch the tile."""
    import numpy as np

    if segments.shape[0] == 0:
        empty = np.zeros((0, 2), dtype=np.float32)
        return empty, empty
    uv = segments.astype(np.float64) - np.array([tile_u, tile_v])
    lo = uv.min(axis=1)
    hi = uv.max(axis=1)
    keep = np.isfinite(uv).all(axis=(1, 2)) & (hi[:, 0] >= 0.0) & (lo[:, 0] <= 1.0) & (hi[:, 1] >= 0.0) & (lo[:, 1] <= 1.0)
    uv = uv[keep]
    x = uv[..., 0] * width
    y = (1.0 - uv[..., 1]) * height
    p = np.stack([x, y], axis=-1).astype(np.float32)
    return p[:, 0], p[:, 1]


def clip_segments_to_rect(p0, p1, xmin: float, ymin: float, xmax: float, ymax: float):
    """Liang-Barsky clip of (n, 2) segments to a rectangle; segments missing it (or with a
    non-finite end) are dropped. Returns float64 (p0, p1) of the kept, clipped segments."""
    import numpy as np

    a = np.asarray(p0, dtype=np.float64)
    b = np.asarray(p1, dtype=np.float64)
    if a.shape[0] == 0:
        return a, b
    finite = np.isfinite(a).all(axis=1) & np.isfinite(b).all(axis=1)
    a = a[finite]
    b = b[finite]
    d = b - a
    t0 = np.zeros(a.shape[0])
    t1 = np.ones(a.shape[0])
    alive = np.ones(a.shape[0], dtype=bool)
    with np.errstate(divide="ignore", invalid="ignore"):
        for p, q in (
            (-d[:, 0], a[:, 0] - xmin),
            (d[:, 0], xmax - a[:, 0]),
            (-d[:, 1], a[:, 1] - ymin),
            (d[:, 1], ymax - a[:, 1]),
        ):
            parallel = p == 0.0
            alive &= ~(parallel & (q < 0.0))
            r = q / p
            t0 = np.where(~parallel & (p < 0.0), np.maximum(t0, r), t0)
            t1 = np.where(~parallel & (p > 0.0), np.minimum(t1, r), t1)
    alive &= t0 <= t1
    a = a[alive]
    d = d[alive]
    t0 = t0[alive][:, None]
    t1 = t1[alive][:, None]
    return a + d * t0, a + d * t1


def rasterize_lines_numpy(p0, p1, width: int, height: int, line_width: float, *, seg_len: float = 3.0, chunk: int = 60000):
    """Anti-aliased coverage (height, width) of line segments, row 0 at the top.

    A pixel's coverage is clamp(w/2 + 0.5 - distance to the line), for pixel centres that
    project onto the segment (flat ends, like the GPU line); overlapping
    lines combine as 1 - prod(1 - c), so a crossing never exceeds 1.

    Bounded in time and memory whatever the input: segments are first clipped to the
    image (a segment far outside the tile costs what its visible part costs), every
    segment is cut into ``seg_len`` pieces that each own the pixels projecting onto them
    (so a pixel is counted once per segment, not once per piece), and pieces are
    processed ``chunk`` at a time into one float32 accumulator.
    """
    import numpy as np

    out_shape = (height, width)
    if p0.shape[0] == 0:
        return np.zeros(out_shape, dtype=np.float32)
    half = 0.5 * float(line_width)
    reach = half + 1.0
    margin = reach + 1.0
    a_all, b_all = clip_segments_to_rect(p0, p1, -margin, -margin, width + margin, height + margin)
    if a_all.shape[0] == 0:
        return np.zeros(out_shape, dtype=np.float32)
    a_all = a_all.astype(np.float32)
    b_all = b_all.astype(np.float32)
    delta_all = b_all - a_all
    lengths = np.hypot(delta_all[:, 0], delta_all[:, 1])
    moving = lengths > 1e-6
    a_all = a_all[moving]
    delta_all = delta_all[moving]
    lengths = lengths[moving]
    if a_all.shape[0] == 0:
        return np.zeros(out_shape, dtype=np.float32)
    pieces_all = np.maximum(1, np.ceil(lengths / seg_len)).astype(np.int64)
    ends = np.cumsum(pieces_all)
    window = int(np.ceil(seg_len + 2.0 * reach)) + 1
    oy, ox = np.mgrid[0:window, 0:window]
    ox = ox.ravel().astype(np.float32)
    oy = oy.ravel().astype(np.float32)
    acc = np.zeros(width * height, dtype=np.float32)
    first = 0
    count = a_all.shape[0]
    while first < count:
        base = int(ends[first - 1]) if first else 0
        last = int(np.searchsorted(ends, base + chunk, side="right"))
        last = max(last, first + 1)
        pieces = pieces_all[first:last]
        A0 = a_all[first:last]
        D0 = delta_all[first:last]
        first = last
        owner = np.repeat(np.arange(pieces.size), pieces)
        starts = np.cumsum(pieces) - pieces
        k = (np.arange(owner.size) - np.repeat(starts, pieces)).astype(np.float32)
        n = pieces[owner].astype(np.float32)
        A = A0[owner]
        D = D0[owner]
        tlo = k / n
        thi = (k + 1.0) / n
        ea = A + D * tlo[:, None]
        eb = A + D * thi[:, None]
        lo = np.floor(np.minimum(ea, eb) - reach)
        px = lo[:, :1] + ox[None, :] + 0.5
        py = lo[:, 1:] + oy[None, :] + 0.5
        denom = np.maximum((D * D).sum(axis=1), 1e-12)[:, None]
        t = ((px - A[:, :1]) * D[:, :1] + (py - A[:, 1:]) * D[:, 1:]) / denom
        dx = px - (A[:, :1] + t * D[:, :1])
        dy = py - (A[:, 1:] + t * D[:, 1:])
        cov = np.clip(half + 0.5 - np.sqrt(dx * dx + dy * dy), 0.0, 1.0)
        ix = np.floor(px).astype(np.int64)
        iy = np.floor(py).astype(np.int64)
        ok = (
            (cov > 0.0)
            & (t >= tlo[:, None])
            & (t < thi[:, None])
            & (ix >= 0) & (iy >= 0) & (ix < width) & (iy < height)
        )
        np.add.at(acc, iy[ok] * width + ix[ok], np.log1p(-np.minimum(cov[ok], 0.999999)))
    coverage = 1.0 - np.exp(acc)
    coverage[coverage > 0.999] = 1.0
    return coverage.astype(np.float32).reshape(out_shape)


def rasterize_lines_gpu(p0, p1, width: int, height: int, line_width: float, *, tile: int = 4096):
    """Same coverage as rasterize_lines_numpy, drawn by Blender's GPU module (needs a window).

    Drawn in tiles of at most ``tile`` pixels so an 8K/16K output never needs a giant
    offscreen buffer; a line crossing a tile border is drawn in both and meets itself.
    White lines alpha-blended over black leave the coverage in the red channel, which is
    the only channel read back (Framebuffer.read_color: GPUTexture.read() came back in a
    layout that scattered the lines).
    """
    import gpu
    import numpy as np
    from gpu_extras.batch import batch_for_shader
    from mathutils import Matrix

    out = np.zeros((height, width), dtype=np.float32)
    if p0.shape[0] == 0:
        return out
    shader = gpu.shader.from_builtin("POLYLINE_UNIFORM_COLOR")
    reach = 0.5 * float(line_width) + 2.0
    seg_lo = np.minimum(p0, p1) - reach
    seg_hi = np.maximum(p0, p1) + reach
    for y0 in range(0, height, tile):
        for x0 in range(0, width, tile):
            tw = min(tile, width - x0)
            th = min(tile, height - y0)
            near = (seg_hi[:, 0] >= x0) & (seg_lo[:, 0] <= x0 + tw) & (seg_hi[:, 1] >= y0) & (seg_lo[:, 1] <= y0 + th)
            if not near.any():
                continue
            a = p0[near]
            b = p1[near]
            points = np.empty((a.shape[0] * 2, 3), dtype=np.float32)
            # Pixel coordinates (y down) -> this tile's clip space (y up).
            points[0::2, 0] = (a[:, 0] - x0) / tw * 2.0 - 1.0
            points[0::2, 1] = 1.0 - (a[:, 1] - y0) / th * 2.0
            points[1::2, 0] = (b[:, 0] - x0) / tw * 2.0 - 1.0
            points[1::2, 1] = 1.0 - (b[:, 1] - y0) / th * 2.0
            points[:, 2] = 0.0
            offscreen = gpu.types.GPUOffScreen(tw, th, format="RGBA16F")
            try:
                with offscreen.bind():
                    framebuffer = gpu.state.active_framebuffer_get()
                    framebuffer.clear(color=(0.0, 0.0, 0.0, 0.0))
                    batch = batch_for_shader(shader, "LINES", {"pos": points})
                    with gpu.matrix.push_pop(), gpu.matrix.push_pop_projection():
                        gpu.matrix.load_matrix(Matrix.Identity(4))
                        gpu.matrix.load_projection_matrix(Matrix.Identity(4))
                        gpu.state.blend_set("ALPHA")
                        shader.bind()
                        shader.uniform_float("viewportSize", (float(tw), float(th)))
                        shader.uniform_float("lineWidth", float(line_width))
                        shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
                        batch.draw(shader)
                        gpu.state.blend_set("NONE")
                    buffer = framebuffer.read_color(0, 0, tw, th, 1, 0, "FLOAT")
                buffer.dimensions = tw * th
                red = np.asarray(buffer, dtype=np.float32).reshape(th, tw)
            finally:
                offscreen.free()
            # Framebuffer row 0 is the bottom of the tile.
            out[y0:y0 + th, x0:x0 + tw] = np.clip(red[::-1], 0.0, 1.0)
    return out


def _gpu_available() -> bool:
    try:
        import bpy

        if bpy.app.background:
            return False
        import gpu  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def rasterize_lines(p0, p1, width: int, height: int, line_width: float):
    import numpy as np

    # Clip first: float32 positions far outside the image lose their sub-pixel precision
    # on the GPU, and the CPU path should never pay for what the image cannot show.
    margin = 0.5 * float(line_width) + 3.0
    a, b = clip_segments_to_rect(p0, p1, -margin, -margin, width + margin, height + margin)
    p0 = a.astype(np.float32)
    p1 = b.astype(np.float32)
    if _gpu_available():
        try:
            return rasterize_lines_gpu(p0, p1, width, height, line_width)
        except Exception as exc:  # noqa: BLE001 - the CPU path draws the same lines
            print(f"[Fyr Baker] Wireframe GPU draw unavailable ({exc}); drawing on the CPU")
    return rasterize_lines_numpy(p0, p1, width, height, line_width)


def _write_grey(path, grey, *, bit_depth: str) -> None:
    import numpy as np
    import OpenImageIO as oiio

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    height, width = grey.shape
    extension = target.suffix.lower()
    if extension == ".exr":
        pixel_type = oiio.HALF if str(bit_depth) == constants.BIT_DEPTH_16 else oiio.FLOAT
    elif str(bit_depth) == constants.BIT_DEPTH_8 or extension in {".tga", ".jpg", ".jpeg", ".bmp"}:
        pixel_type = oiio.UINT8
    else:
        pixel_type = oiio.UINT16
    spec = oiio.ImageSpec(width, height, 3, pixel_type)
    pixels = np.repeat(grey[:, :, None], 3, axis=2).astype(np.float32)
    temporary = target.with_name(target.stem + ".fyrtmp" + target.suffix)
    output = oiio.ImageOutput.create(str(temporary))
    if output is None or not output.open(str(temporary), spec):
        raise RuntimeError(f"Could not write {path}: {oiio.geterror()}")
    try:
        if not output.write_image(pixels):
            raise RuntimeError(f"Could not write {path}: {output.geterror()}")
    finally:
        output.close()
    os.replace(temporary, target)


def render_wireframe_entry(entry: dict) -> None:
    import bpy
    import numpy as np

    from . import mesh_read

    depsgraph = bpy.context.evaluated_depsgraph_get()
    segments = []
    for name in entry.get("objects", []) or []:
        obj = bpy.data.objects.get(str(name))
        if obj is None or getattr(obj, "type", "") != "MESH":
            continue
        with mesh_read.evaluated_mesh_copy(obj, depsgraph) as (_obj_eval, mesh):
            if mesh is None:
                continue
            segments.append(
                mesh_uv_edges(mesh, str(entry.get("uv_layer", "") or ""), triangles=bool(entry.get("triangles", False)))
            )
    width = int(entry["width"])
    height = int(entry["height"])
    all_segments = np.concatenate(segments) if segments else np.zeros((0, 2, 2), dtype=np.float32)
    p0, p1 = segments_to_pixels(
        dedupe_segments(all_segments), width, height, float(entry.get("tile_u", 0.0)), float(entry.get("tile_v", 0.0))
    )
    grey = rasterize_lines(p0, p1, width, height, float(entry.get("line_width", constants.DEFAULT_WIREFRAME_LINE_WIDTH)))
    _write_grey(entry["final_path"], grey, bit_depth=str(entry.get("bit_depth", constants.BIT_DEPTH_8)))


# ---------------------------------------------------------------------------------------
# Lit Color
# ---------------------------------------------------------------------------------------


def _output_pixel_type(path, bit_depth: str):
    import OpenImageIO as oiio

    extension = Path(path).suffix.lower()
    if extension == ".exr":
        # The backend writes every EXR as half float, so its sources hold no more.
        return oiio.HALF
    if str(bit_depth) == constants.BIT_DEPTH_8 or extension in {".tga", ".jpg", ".jpeg", ".bmp"}:
        return oiio.UINT8
    return oiio.UINT16


def _srgb_to_linear(values):
    import numpy as np

    # Blender's sRGB is a mirrored power curve past 1.0, so HDR emission decodes too.
    magnitude = np.abs(values)
    linear = np.where(magnitude <= 0.04045, magnitude / 12.92, ((magnitude + 0.055) / 1.055) ** 2.4)
    return np.sign(values) * linear


def composite_lit_color(
    lighting_path, albedo_path, emission_path, final_path, *, bit_depth: str, srgb_sources=(), emission_scale: float = 1.0
) -> None:
    """Write ``albedo * lighting + emission`` to ``final_path``, streamed in scanline chunks.

    All sources are EXRs of one size; ``emission_path`` may be empty. The backend writes
    them linear; a material channel baked through Cycles comes back sRGB-encoded, and
    its role ("albedo" / "emission") is listed in ``srgb_sources`` to be decoded. The
    emission is multiplied by ``emission_scale`` (the row's exposure, which the backend
    already applied to the lighting). Lit
    Color is linear data like the Lighting map, so an 8/16-bit output is written
    unencoded.
    """
    import numpy as np
    import OpenImageIO as oiio

    sources = {"lighting": lighting_path, "albedo": albedo_path}
    if str(emission_path or "").strip():
        sources["emission"] = emission_path
    inputs = {}
    try:
        for role, path in sources.items():
            handle = oiio.ImageInput.open(str(path))
            if handle is None:
                raise RuntimeError(f"Could not open the {role} source {path}: {oiio.geterror()}")
            inputs[role] = handle
        spec = inputs["lighting"].spec()
        width, height = int(spec.width), int(spec.height)
        for role, handle in inputs.items():
            other = handle.spec()
            if int(other.width) != width or int(other.height) != height:
                raise RuntimeError(
                    f"The {role} source is {other.width}x{other.height}, the lighting is {width}x{height}"
                )
        out_spec = oiio.ImageSpec(width, height, 3, _output_pixel_type(final_path, bit_depth))
        if Path(final_path).suffix.lower() == ".exr":
            out_spec.attribute("compression", "zip")  # lossless; fast to write at 4K
        final = Path(final_path)
        final.parent.mkdir(parents=True, exist_ok=True)
        temporary = final.with_name(final.stem + ".fyrtmp" + final.suffix)
        output = oiio.ImageOutput.create(str(temporary))
        if output is None or not output.open(str(temporary), out_spec):
            raise RuntimeError(f"Could not write {final_path}: {oiio.geterror()}")
        try:
            for y0 in range(0, height, _SCANLINE_CHUNK):
                y1 = min(height, y0 + _SCANLINE_CHUNK)
                rows = {}
                for role, handle in inputs.items():
                    channels = int(handle.spec().nchannels)
                    data = handle.read_scanlines(0, 0, y0, y1, 0, 0, channels, oiio.FLOAT)
                    if data is None:
                        raise RuntimeError(f"Could not read the {role} source: {handle.geterror()}")
                    data = np.asarray(data, dtype=np.float32).reshape(y1 - y0, width, channels)
                    if channels < 3:
                        data = np.repeat(data[..., :1], 3, axis=2)
                    rows[role] = _srgb_to_linear(data[..., :3]) if role in srgb_sources else data[..., :3]
                lit = rows["albedo"] * rows["lighting"]
                if "emission" in rows:
                    lit += rows["emission"] * float(emission_scale)
                np.nan_to_num(lit, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
                if not output.write_scanlines(y0, y1, 0, np.ascontiguousarray(lit)):
                    raise RuntimeError(f"Could not write {final_path}: {output.geterror()}")
        finally:
            output.close()
    finally:
        for handle in inputs.values():
            handle.close()
    os.replace(temporary, final)


# ---------------------------------------------------------------------------------------
# Completion step
# ---------------------------------------------------------------------------------------


def _merge_shared_wireframes(entries: list[dict]) -> list[dict]:
    """Groups of one texture set write one Wireframe file: draw their lows together."""
    merged: list[dict] = []
    by_path: dict[str, dict] = {}
    for entry in entries:
        if str(entry.get("kind", "")) != KIND_WIREFRAME:
            merged.append(entry)
            continue
        key = os.path.normcase(os.path.abspath(str(entry.get("final_path", ""))))
        existing = by_path.get(key)
        if existing is None:
            combined = dict(entry)
            combined["objects"] = list(entry.get("objects") or [])
            combined["group_names"] = [str(entry.get("group_name", "") or "")]
            by_path[key] = combined
            merged.append(combined)
            continue
        for name in entry.get("objects") or []:
            if name not in existing["objects"]:
                existing["objects"].append(name)
        group_name = str(entry.get("group_name", "") or "")
        if group_name not in existing["group_names"]:
            existing["group_names"].append(group_name)
    return merged


def apply_workspace_derived_outputs(workspace_path, progress=None) -> list[str]:
    """Finish this job's Derivative, Wireframe and Lit Color outputs; returns warnings.

    With ``progress``, its produced files are rewritten to name what the artist gets:
    a Derivative's hidden normal source becomes the derivative file, and every
    Wireframe file is added.
    """
    from . import protocol

    entries = read_sidecar(workspace_path)
    if not entries:
        return []
    warnings: list[str] = []
    produced = list(getattr(progress, "produced_files", None) or []) if progress is not None else None
    composited_lit_color: set[str] = set()
    for entry in _merge_shared_wireframes(entries):
        kind = str(entry.get("kind", "") or "")
        try:
            if kind == KIND_LIT_COLOR:
                final_path = str(entry["final_path"])
                lighting = str(entry["lighting_source"])
                albedo = str(entry["albedo_source"])
                emission = str(entry.get("emission_source", "") or "")
                hidden = [path for path in (lighting, albedo, emission) if path]
                if produced is not None:
                    # Every hidden source names what the artist gets, or leaves the list.
                    baked_here = False
                    for item in produced:
                        if _same_path(item.path, lighting):
                            item.path = final_path
                            item.map_type = constants.MAP_LIT_COLOR
                            baked_here = True
                    produced = [
                        item for item in produced
                        if not any(_same_path(item.path, path) for path in hidden[1:])
                    ]
                    if not baked_here:
                        # This job did not bake that row / tile, the texture set's first
                        # group already took it, or Cycles wrote the final file whole.
                        continue
                final_key = os.path.normcase(os.path.abspath(final_path))
                if final_key in composited_lit_color:
                    continue  # another group of the same texture set already wrote it
                if not Path(lighting).exists():
                    continue
                if not Path(albedo).exists():
                    raise RuntimeError("its Base Color source was not baked")
                composite_lit_color(
                    lighting,
                    albedo,
                    emission if emission and Path(emission).exists() else "",
                    final_path,
                    bit_depth=str(entry.get("bit_depth", constants.BIT_DEPTH_8)),
                    srgb_sources={
                        role for role in ("albedo", "emission")
                        if entry.get(f"{role}_route") == constants.EXECUTION_ROUTE_BLENDER
                    },
                    emission_scale=float(entry.get("emission_scale", 1.0)),
                )
                composited_lit_color.add(final_key)
                # The backend never reads an output back, and rewrites one whose file is
                # gone, so the sources need not outlive the composite: a Lit Color row
                # costs the disk its final file only.
                for path in hidden:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            elif kind == KIND_DERIVATIVE:
                source = str(entry["source_path"])
                if produced is not None and not any(_same_path(item.path, source) for item in produced):
                    continue  # this job did not bake that row / tile
                if not Path(source).exists():
                    continue
                convert_normal_file_to_derivative(
                    source,
                    entry["final_path"],
                    max_slope=float(entry.get("max_slope", constants.DEFAULT_DERIVATIVE_MAX_SLOPE)),
                    flip_green=bool(entry.get("flip_green", False)),
                )
                if produced is not None:
                    for item in produced:
                        if _same_path(item.path, source):
                            item.path = str(entry["final_path"])
                            item.map_type = constants.MAP_DERIVATIVE
            elif kind == KIND_NORMAL_RELIEF:
                path = str(entry["path"])
                # Only a file the backend wrote this job: the Cycles route already ran
                # these passes on its own output, and twice would lift slopes again.
                if produced is None or not any(_same_path(item.path, path) for item in produced):
                    continue
                if not Path(path).exists():
                    continue
                apply_normal_relief_file(path, relief=float(entry.get("relief", 0.5)))
            elif kind == KIND_WIREFRAME:
                render_wireframe_entry(entry)
                if produced is not None:
                    for group_name in entry.get("group_names") or [entry.get("group_name", "")]:
                        produced.append(
                            protocol.ProducedFile(
                                group_name=str(group_name or ""),
                                map_type=constants.MAP_WIREFRAME,
                                path=str(entry["final_path"]),
                                map_uuid=str(entry.get("map_uuid", "") or ""),
                                udim_tile=int(entry.get("udim_tile", 0) or 0),
                            )
                        )
        except Exception as exc:  # noqa: BLE001 - one bad output must not lose the others
            label = {
                KIND_DERIVATIVE: "Derivative",
                KIND_LIT_COLOR: "Lit Color",
                KIND_NORMAL_RELIEF: "Normal Relief",
            }.get(kind, "Wireframe")
            warnings.append(f"{label} map for '{entry.get('group_name', '')}' was not written: {exc}")
    if produced is not None:
        progress.produced_files = produced
    return warnings
