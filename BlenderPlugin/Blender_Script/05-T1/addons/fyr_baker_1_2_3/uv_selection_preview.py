"""UV Selection Preview – GPU viewport overlay for Blender 5.1+.

When UV Sync Selection is disabled, draws a visual highlight in every 3D
Viewport corresponding to the current UV Editor selection (vertices, edges,
faces, or islands).  Visualization-only: never modifies mesh selection,
undo, or file state.
"""

from __future__ import annotations

import time
import traceback

import bpy
import gpu
import bmesh
from mathutils import Vector, Matrix
from mathutils.geometry import tessellate_polygon
from gpu_extras.batch import batch_for_shader

from .handler_thread_guard import on_main_thread
from .registration import safe_register_class, safe_unregister_class, safe_remove_attr


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class MasterBakerUVSelectionPreviewSettings(bpy.types.PropertyGroup):
    show_uv_selection_in_3d: bpy.props.BoolProperty(
        name="Show UV Selection in 3D",
        default=False,
        description=(
            "Highlight the current UV Editor selection on the mesh in every 3D Viewport. "
            "Only active when UV Sync Selection is disabled"
        ),
    )


CLASSES = (MasterBakerUVSelectionPreviewSettings,)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class _OverlayCache:
    """Per-scene cache for UV selection overlay geometry."""

    __slots__ = (
        "dirty", "selection_signature", "topology_signature",
        "face_batch", "face_outline_batch", "edge_batch", "vertex_batch",
        "last_scan_time", "logged_errors",
    )

    def __init__(self):
        self.dirty = True
        self.selection_signature: object = None
        self.topology_signature: object = None
        self.face_batch = None
        self.face_outline_batch = None
        self.edge_batch = None
        self.vertex_batch = None
        self.last_scan_time: float = 0.0
        self.logged_errors: set[str] = set()

    def invalidate(self):
        self.dirty = True
        self.face_batch = None
        self.face_outline_batch = None
        self.edge_batch = None
        self.vertex_batch = None


_cache = _OverlayCache()

# Minimum seconds between BMesh scans triggered by UV Editor redraws.
_SCAN_THROTTLE = 0.05  # 20 Hz max


# ---------------------------------------------------------------------------
# Registration state
# ---------------------------------------------------------------------------

_view3d_handler = None
_image_handler = None
_depsgraph_handler = None
_load_post_handler = None
_timer_registered = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_settings(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return None
    settings = getattr(scene, "fyr_baker_uv_selection_preview", None)
    return settings


def _get_prefs():
    """Return the add-on preferences object, or None."""
    try:
        from . import preferences as prefs_module
        return prefs_module.get_preferences()
    except Exception:
        return None


def _appearance():
    """Return appearance settings from preferences with sensible defaults."""
    prefs = _get_prefs()
    if prefs is not None:
        return (
            tuple(getattr(prefs, "uv_preview_color", (1.0, 0.05, 0.75, 1.0))),
            float(getattr(prefs, "uv_preview_face_opacity", 0.20)),
            float(getattr(prefs, "uv_preview_edge_width", 3.0)),
            float(getattr(prefs, "uv_preview_vertex_size", 6.0)),
            bool(getattr(prefs, "uv_preview_use_xray", False)),
            bool(getattr(prefs, "uv_preview_show_face_fill", True)),
            bool(getattr(prefs, "uv_preview_show_face_outline", True)),
            bool(getattr(prefs, "uv_preview_show_when_overlays_hidden", False)),
        )
    return (1.0, 0.05, 0.75, 1.0), 0.20, 3.0, 6.0, False, True, True, False


def _is_relevant(context) -> bool:
    """True when the overlay should be active."""
    settings = _get_settings(context)
    if settings is None or not settings.show_uv_selection_in_3d:
        return False
    if context.scene.tool_settings.use_uv_select_sync:
        return False
    return True


def _iter_edit_mesh_objects(context):
    """Yield mesh objects currently in Edit Mode."""
    for obj in context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.mode != "EDIT":
            continue
        yield obj


def _get_uv_selection_mode(context) -> str:
    """Return current UV selection mode: 'VERTEX', 'EDGE', 'FACE', or 'ISLAND'."""
    ts = context.scene.tool_settings
    mode = ts.uv_select_mode
    if mode == "VERTEX":
        return "VERTEX"
    if mode == "EDGE":
        return "EDGE"
    if mode == "FACE":
        return "FACE"
    if mode == "ISLAND":
        return "ISLAND"
    return str(mode)


def _tag_all_view3d_redraw():
    """Tag every VIEW_3D area in every window for redraw."""
    wm = bpy.context.window_manager
    for win in wm.windows:
        screen = win.screen
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# ---------------------------------------------------------------------------
# Selection gathering
# ---------------------------------------------------------------------------

def _gather_selection(context):
    """Read UV selection from all edit-mode meshes.

    Returns a dict mapping object identifiers to selection data, plus a
    topology signature for change detection.
    """
    uv_mode = _get_uv_selection_mode(context)
    result = {}
    topo_sig_parts = []

    for obj in _iter_edit_mesh_objects(context):
        mesh = obj.data
        if mesh is None:
            continue
        try:
            bm = bmesh.from_edit_mesh(mesh)
        except Exception:
            continue
        if bm is None:
            continue

        obj_key = (obj.name, mesh.name)

        selected_verts: set[int] = set()
        selected_edges: set[int] = set()
        selected_faces: set[int] = set()

        vert_coords: dict[int, tuple[float, float, float]] = {}
        edge_pairs: dict[int, tuple[int, int]] = {}
        face_tris: list[tuple[int, int, int]] = []
        face_outline_edges: set[tuple[int, int]] = set()

        for face in bm.faces:
            if not face.select or face.hide:
                continue

            if uv_mode == "FACE":
                if getattr(face, "uv_select", False):
                    selected_faces.add(face.index)
            elif uv_mode == "ISLAND":
                # In island mode, face.uv_select may or may not be set.
                # Fallback: face is island-selected if all visible loops have uv_select_vert.
                if getattr(face, "uv_select", False):
                    selected_faces.add(face.index)
                else:
                    all_loops_selected = True
                    for loop in face.loops:
                        if not getattr(loop, "uv_select_vert", False):
                            all_loops_selected = False
                            break
                    if all_loops_selected:
                        selected_faces.add(face.index)

            # Gather per-loop selection for vert/edge/island modes
            for loop in face.loops:
                if uv_mode == "VERTEX" or uv_mode == "ISLAND":
                    if getattr(loop, "uv_select_vert", False):
                        vi = loop.vert.index
                        selected_verts.add(vi)
                        vert_coords[vi] = tuple(loop.vert.co)

                if uv_mode == "EDGE":
                    if getattr(loop, "uv_select_edge", False):
                        ei = loop.edge.index
                        selected_edges.add(ei)
                        edge_pairs[ei] = (
                            loop.edge.verts[0].index,
                            loop.edge.verts[1].index,
                        )

            # For face/island modes, also gather face geometry
            if uv_mode in ("FACE", "ISLAND") and face.index in selected_faces:
                # Gather vert coords for triangulation
                for loop in face.loops:
                    vert_coords[loop.vert.index] = tuple(loop.vert.co)

                # Triangulate the face (handles concave n-gons)
                face_normal = face.normal
                if abs(face_normal.z) < 0.9:
                    tangent = face_normal.cross(Vector((0.0, 0.0, 1.0)))
                else:
                    tangent = face_normal.cross(Vector((1.0, 0.0, 0.0)))
                if tangent.length > 1e-6:
                    tangent.normalize()
                else:
                    tangent = Vector((1.0, 0.0, 0.0))
                bitangent = face_normal.cross(tangent)

                loop_verts_2d = []
                loop_vert_indices = []
                for loop in face.loops:
                    co = loop.vert.co
                    x = co.dot(tangent)
                    y = co.dot(bitangent)
                    loop_verts_2d.append(Vector((x, y)))
                    loop_vert_indices.append(loop.vert.index)

                try:
                    tri_indices = tessellate_polygon([loop_verts_2d])
                    for tri in tri_indices:
                        face_tris.append((
                            loop_vert_indices[tri[0]],
                            loop_vert_indices[tri[1]],
                            loop_vert_indices[tri[2]],
                        ))
                except Exception:
                    # Fallback: fan triangulation
                    if len(loop_vert_indices) >= 3:
                        for i in range(1, len(loop_vert_indices) - 1):
                            face_tris.append((
                                loop_vert_indices[0],
                                loop_vert_indices[i],
                                loop_vert_indices[i + 1],
                            ))

                # Gather outline edges
                for edge in face.edges:
                    e_pair = tuple(sorted((edge.verts[0].index, edge.verts[1].index)))
                    face_outline_edges.add(e_pair)
                    vert_coords[edge.verts[0].index] = tuple(edge.verts[0].co)
                    vert_coords[edge.verts[1].index] = tuple(edge.verts[1].co)

        # For edge mode, gather vert coords for selected edges
        if uv_mode == "EDGE":
            for ei in selected_edges:
                pair = edge_pairs.get(ei)
                if pair is None:
                    continue
                v0_idx, v1_idx = pair
                # Look up verts from the bmesh
                bv0 = bm.verts[v0_idx] if v0_idx < len(bm.verts) else None
                bv1 = bm.verts[v1_idx] if v1_idx < len(bm.verts) else None
                if bv0 is not None:
                    vert_coords[v0_idx] = tuple(bv0.co)
                if bv1 is not None:
                    vert_coords[v1_idx] = tuple(bv1.co)

        topo_sig_parts.append((
            obj.name,
            mesh.name,
            len(bm.verts),
            len(bm.edges),
            len(bm.faces),
            uv_mode,
        ))

        result[obj_key] = {
            "uv_mode": uv_mode,
            "selected_verts": selected_verts,
            "selected_edges": selected_edges,
            "selected_faces": selected_faces,
            "vert_coords": vert_coords,
            "edge_pairs": edge_pairs,
            "face_tris": face_tris,
            "face_outline_edges": face_outline_edges,
            "matrix": tuple(obj.matrix_world),
        }

    return result, tuple(topo_sig_parts)


def _build_signature(selection_data):
    """Build a comparison signature from selection data."""
    sig_parts = []
    for obj_key, data in sorted(selection_data.items()):
        sig_parts.append((
            obj_key,
            data["uv_mode"],
            frozenset(data["selected_verts"]),
            frozenset(data["selected_edges"]),
            frozenset(data["selected_faces"]),
            data["matrix"],
        ))
    return tuple(sig_parts)


# ---------------------------------------------------------------------------
# Depth-biased shaders
#
# The overlay geometry sits exactly on the mesh surface (same vertex
# positions, same matrix), which z-fights with the surface itself. Rather
# than nudging the actual vertex positions (which visibly drifts off the
# real surface once zoomed in), these shaders push the *depth* of each
# fragment slightly toward the camera in clip space after the standard
# MVP transform. Since `gl_Position.xy / gl_Position.w` (the screen
# position) is unaffected by `gl_Position.z`, the overlay renders in
# exactly the correct screen location while reliably winning the depth
# test against the coincident surface.
# ---------------------------------------------------------------------------

_DEPTH_BIAS = 0.00025

_shader_cache: dict[str, object] = {}


def _get_bias_fill_shader():
    """Flat-colored triangle shader with a clip-space depth bias."""
    shader = _shader_cache.get("fill")
    if shader is not None:
        return shader

    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("VEC4", "color")
    info.push_constant("FLOAT", "depthBias")
    info.vertex_in(0, "VEC3", "pos")
    info.fragment_out(0, "VEC4", "fragColor")
    info.vertex_source(
        "void main() {\n"
        "  vec4 clip_pos = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "  clip_pos.z -= depthBias * clip_pos.w;\n"
        "  gl_Position = clip_pos;\n"
        "}\n"
    )
    info.fragment_source("void main() {\n  fragColor = color;\n}\n")
    shader = gpu.shader.create_from_info(info)
    del info
    _shader_cache["fill"] = shader
    return shader


def _get_bias_point_shader():
    """Flat-colored point shader with a clip-space depth bias."""
    shader = _shader_cache.get("point")
    if shader is not None:
        return shader

    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("VEC4", "color")
    info.push_constant("FLOAT", "depthBias")
    info.push_constant("FLOAT", "pointSize")
    info.vertex_in(0, "VEC3", "pos")
    info.fragment_out(0, "VEC4", "fragColor")
    info.vertex_source(
        "void main() {\n"
        "  vec4 clip_pos = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "  clip_pos.z -= depthBias * clip_pos.w;\n"
        "  gl_Position = clip_pos;\n"
        "  gl_PointSize = pointSize;\n"
        "}\n"
    )
    info.fragment_source("void main() {\n  fragColor = color;\n}\n")
    shader = gpu.shader.create_from_info(info)
    del info
    _shader_cache["point"] = shader
    return shader


def _get_bias_line_shader():
    """Constant-pixel-width line shader (screen-space quad expansion) with
    a clip-space depth bias.

    Each line segment is submitted as two triangles (6 verts). Every vert
    carries its own position (`pos`), the segment's fixed start/end
    (`segStart`/`segEnd` - identical for all 6 verts of a segment so the
    expansion direction is consistent), and a `side` of -1 or +1 indicating
    which edge of the ribbon it belongs to.
    """
    shader = _shader_cache.get("line")
    if shader is not None:
        return shader

    info = gpu.types.GPUShaderCreateInfo()
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("VEC4", "color")
    info.push_constant("FLOAT", "depthBias")
    info.push_constant("FLOAT", "lineWidth")
    info.push_constant("VEC2", "viewportSize")
    info.vertex_in(0, "VEC3", "pos")
    info.vertex_in(1, "VEC3", "segStart")
    info.vertex_in(2, "VEC3", "segEnd")
    info.vertex_in(3, "FLOAT", "side")
    info.fragment_out(0, "VEC4", "fragColor")
    info.vertex_source(
        "void main() {\n"
        "  vec4 clip_this = ModelViewProjectionMatrix * vec4(pos, 1.0);\n"
        "  vec4 clip_start = ModelViewProjectionMatrix * vec4(segStart, 1.0);\n"
        "  vec4 clip_end = ModelViewProjectionMatrix * vec4(segEnd, 1.0);\n"
        "  vec2 ndc_start = clip_start.xy / clip_start.w;\n"
        "  vec2 ndc_end = clip_end.xy / clip_end.w;\n"
        "  vec2 dir_px = (ndc_end - ndc_start) * viewportSize * 0.5;\n"
        "  float len_px = length(dir_px);\n"
        "  vec2 perp_px = (len_px > 0.00001) ? vec2(-dir_px.y, dir_px.x) / len_px : vec2(1.0, 0.0);\n"
        "  vec2 offset_ndc = perp_px * (lineWidth * 0.5) / (viewportSize * 0.5);\n"
        "  clip_this.xy += offset_ndc * side * clip_this.w;\n"
        "  clip_this.z -= depthBias * clip_this.w;\n"
        "  gl_Position = clip_this;\n"
        "}\n"
    )
    info.fragment_source("void main() {\n  fragColor = color;\n}\n")
    shader = gpu.shader.create_from_info(info)
    del info
    _shader_cache["line"] = shader
    return shader


def _append_line_quad(pos_list, seg_start_list, seg_end_list, side_list, t0, t1):
    """Append the 6 verts (2 triangles) of a screen-space line-quad segment."""
    t0 = tuple(t0)
    t1 = tuple(t1)
    for pos, side in ((t0, -1.0), (t0, 1.0), (t1, 1.0), (t0, -1.0), (t1, 1.0), (t1, -1.0)):
        pos_list.append(pos)
        seg_start_list.append(t0)
        seg_end_list.append(t1)
        side_list.append(side)


# ---------------------------------------------------------------------------
# Batch building
# ---------------------------------------------------------------------------

def _build_batches(context):
    """Rebuild GPU batches from current UV selection state."""
    global _cache

    selection_data, topo_sig = _gather_selection(context)

    new_sel_sig = _build_signature(selection_data)

    # Check if we actually need to rebuild
    if (
        not _cache.dirty
        and _cache.selection_signature == new_sel_sig
        and _cache.topology_signature == topo_sig
    ):
        _cache.dirty = False
        return

    _cache.selection_signature = new_sel_sig
    _cache.topology_signature = topo_sig

    # Collect geometry from all objects
    all_face_tris: list[tuple[float, float, float]] = []
    all_verts: list[tuple[float, float, float]] = []

    # Line-quad attribute buffers (screen-space constant-width ribbons).
    outline_pos: list[tuple[float, float, float]] = []
    outline_start: list[tuple[float, float, float]] = []
    outline_end: list[tuple[float, float, float]] = []
    outline_side: list[float] = []

    edge_pos: list[tuple[float, float, float]] = []
    edge_start: list[tuple[float, float, float]] = []
    edge_end: list[tuple[float, float, float]] = []
    edge_side: list[float] = []

    uv_mode = None
    for obj_key, data in selection_data.items():
        uv_mode = data["uv_mode"]
        matrix = data["matrix"]
        vert_coords = data["vert_coords"]

        # Transform helper
        mat = Matrix(matrix)

        def _transformed(vi):
            co = vert_coords.get(vi)
            if co is None:
                return None
            return mat @ Vector(co)

        if uv_mode in ("FACE", "ISLAND"):
            for tri in data["face_tris"]:
                for vi in tri:
                    co = _transformed(vi)
                    if co is not None:
                        all_face_tris.append(tuple(co))

            if data["face_outline_edges"]:
                for v0, v1 in data["face_outline_edges"]:
                    t0 = _transformed(v0)
                    t1 = _transformed(v1)
                    if t0 is not None and t1 is not None:
                        _append_line_quad(outline_pos, outline_start, outline_end, outline_side, t0, t1)

        if uv_mode == "EDGE":
            for ei in data["selected_edges"]:
                pair = data["edge_pairs"].get(ei)
                if pair is None:
                    continue
                v0, v1 = pair
                t0 = _transformed(v0)
                t1 = _transformed(v1)
                if t0 is None or t1 is None:
                    # Fallback: get from bm verts (shouldn't happen, but safe)
                    continue
                _append_line_quad(edge_pos, edge_start, edge_end, edge_side, t0, t1)

        if uv_mode in ("VERTEX", "ISLAND"):
            for vi in data["selected_verts"]:
                co = _transformed(vi)
                if co is not None:
                    all_verts.append(tuple(co))

    # Build batches
    fill_shader = _get_bias_fill_shader()
    point_shader = _get_bias_point_shader()
    line_shader = _get_bias_line_shader()

    _cache.face_batch = None
    _cache.face_outline_batch = None
    _cache.edge_batch = None
    _cache.vertex_batch = None

    if all_face_tris:
        _cache.face_batch = batch_for_shader(fill_shader, "TRIS", {"pos": all_face_tris})

    if outline_pos:
        _cache.face_outline_batch = batch_for_shader(
            line_shader, "TRIS",
            {"pos": outline_pos, "segStart": outline_start, "segEnd": outline_end, "side": outline_side},
        )

    if edge_pos:
        _cache.edge_batch = batch_for_shader(
            line_shader, "TRIS",
            {"pos": edge_pos, "segStart": edge_start, "segEnd": edge_end, "side": edge_side},
        )

    if all_verts:
        _cache.vertex_batch = batch_for_shader(point_shader, "POINTS", {"pos": all_verts})

    _cache.dirty = False


# ---------------------------------------------------------------------------
# Draw callback
# ---------------------------------------------------------------------------

def _draw_overlay():
    """3D Viewport draw callback (POST_VIEW)."""
    global _cache

    context = bpy.context
    settings = _get_settings(context)
    if settings is None or not settings.show_uv_selection_in_3d:
        return

    # Check activation conditions
    if context.scene.tool_settings.use_uv_select_sync:
        return

    # Check if any mesh is in edit mode
    has_edit_mesh = False
    for obj in context.scene.objects:
        if obj.type == "MESH" and obj.mode == "EDIT":
            has_edit_mesh = True
            break
    if not has_edit_mesh:
        return

    # Read appearance settings from preferences
    color, face_opacity, edge_width, vertex_size, use_xray, show_face_fill, show_face_outline, show_when_overlays_hidden = _appearance()

    # Check viewport overlays
    area = context.area
    if area is not None and area.type == "VIEW_3D":
        space = area.spaces.active
        if space is not None:
            overlays_enabled = getattr(space.overlay, "show_overlays", True)
            if not overlays_enabled and not show_when_overlays_hidden:
                return

    # Throttle: if dirty, check if enough time has passed since last scan
    if _cache.dirty:
        now = time.monotonic()
        if now - _cache.last_scan_time < _SCAN_THROTTLE:
            return
        _cache.last_scan_time = now

    # Rebuild batches if dirty
    if _cache.dirty:
        try:
            _build_batches(context)
        except Exception:
            key = "build_batches_error"
            if key not in _cache.logged_errors:
                _cache.logged_errors.add(key)
                print("[Fyr Baker UV Selection Preview] Error building batches:\n" + traceback.format_exc())
            _cache.invalidate()
            return

    # Draw
    saved_depth_test = None
    saved_depth_mask = None
    saved_blend = None

    try:
        # Save GPU state
        saved_depth_test = gpu.state.depth_test_get()
        saved_depth_mask = gpu.state.depth_mask_get()
        saved_blend = gpu.state.blend_get()

        # Set GPU state
        if use_xray:
            gpu.state.depth_test_set("ALWAYS")
        else:
            gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(False)
        gpu.state.blend_set("ALPHA")

        mvp = gpu.matrix.get_projection_matrix() @ gpu.matrix.get_model_view_matrix()
        viewport_size = (float(context.region.width), float(context.region.height))

        # Draw face fills
        if show_face_fill and _cache.face_batch is not None:
            shader = _get_bias_fill_shader()
            shader.bind()
            shader.uniform_float("ModelViewProjectionMatrix", mvp)
            shader.uniform_float("depthBias", _DEPTH_BIAS)
            shader.uniform_float("color", (color[0], color[1], color[2], face_opacity))
            _cache.face_batch.draw(shader)

        def _draw_line_with_halo(batch, line_color, width):
            """Draw a dark halo pass first, then the bright color on top so
            the line reads clearly against any underlying surface color."""
            shader = _get_bias_line_shader()
            shader.bind()
            shader.uniform_float("ModelViewProjectionMatrix", mvp)
            shader.uniform_float("depthBias", _DEPTH_BIAS)
            shader.uniform_float("viewportSize", viewport_size)
            shader.uniform_float("color", (0.0, 0.0, 0.0, min(1.0, line_color[3] + 0.35)))
            shader.uniform_float("lineWidth", width + 2.5)
            batch.draw(shader)
            shader.uniform_float("color", line_color)
            shader.uniform_float("lineWidth", width)
            batch.draw(shader)

        # Draw face outlines
        if show_face_outline and _cache.face_outline_batch is not None:
            outline_color = (color[0], color[1], color[2], min(1.0, color[3] + 0.3))
            _draw_line_with_halo(_cache.face_outline_batch, outline_color, edge_width)

        # Draw edges
        if _cache.edge_batch is not None:
            _draw_line_with_halo(_cache.edge_batch, color, edge_width)

        # Draw vertices
        if _cache.vertex_batch is not None:
            gpu.state.program_point_size_set(True)
            shader = _get_bias_point_shader()
            shader.bind()
            shader.uniform_float("ModelViewProjectionMatrix", mvp)
            shader.uniform_float("depthBias", _DEPTH_BIAS)
            shader.uniform_float("pointSize", vertex_size)
            shader.uniform_float("color", color)
            _cache.vertex_batch.draw(shader)
            gpu.state.program_point_size_set(False)

    except Exception:
        key = "draw_error"
        if key not in _cache.logged_errors:
            _cache.logged_errors.add(key)
            print("[Fyr Baker UV Selection Preview] Draw error:\n" + traceback.format_exc())
        _cache.invalidate()
    finally:
        # Restore GPU state
        try:
            if saved_depth_test is not None:
                gpu.state.depth_test_set(saved_depth_test)
            if saved_depth_mask is not None:
                gpu.state.depth_mask_set(saved_depth_mask)
            if saved_blend is not None:
                gpu.state.blend_set(saved_blend)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# UV Editor activity callback
# ---------------------------------------------------------------------------

def _uv_editor_activity_callback():
    """SpaceImageEditor draw handler – marks cache dirty and tags 3D views."""
    global _cache

    context = bpy.context
    if not _is_relevant(context):
        return

    now = time.monotonic()
    if now - _cache.last_scan_time < _SCAN_THROTTLE:
        return

    _cache.dirty = True
    _tag_all_view3d_redraw()


# ---------------------------------------------------------------------------
# Depsgraph handler
# ---------------------------------------------------------------------------

# Blender clears every non-persistent handler when a .blend is loaded, so an
# undecorated handler silently stops running after File > Open -- and _on_load_post
# below would never fire for the very load it exists to clean up after. The shim
# keeps the module importable under the test stubs, which have no `persistent`.
_persistent = getattr(bpy.app.handlers, "persistent", lambda fn: fn)


@_persistent
def _on_depsgraph_update(scene, depsgraph):
    """Mark cache dirty on topology/transform changes."""
    global _cache
    # Blender also calls this from a bake/render job thread (handler_thread_guard).
    if not on_main_thread():
        return
    _cache.dirty = True


# ---------------------------------------------------------------------------
# Load post handler
# ---------------------------------------------------------------------------

@_persistent
def _on_load_post(dummy=None):
    """Clear stale cache after loading a new file."""
    global _cache
    _cache.invalidate()
    _cache.selection_signature = None
    _cache.topology_signature = None
    _cache.logged_errors.clear()


# ---------------------------------------------------------------------------
# Timer fallback
# ---------------------------------------------------------------------------

def _timer_fallback():
    """Low-frequency fallback to catch UV selection changes that don't
    trigger the Image Editor draw handler."""
    global _cache
    context = bpy.context
    if _is_relevant(context):
        _cache.dirty = True
    return 0.5  # re-run every 0.5 seconds


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register():
    global _view3d_handler, _image_handler, _depsgraph_handler, _load_post_handler, _timer_registered

    for cls in CLASSES:
        safe_register_class(cls)

    bpy.types.Scene.fyr_baker_uv_selection_preview = bpy.props.PointerProperty(
        type=MasterBakerUVSelectionPreviewSettings
    )

    # 3D Viewport draw handler
    if _view3d_handler is None:
        try:
            _view3d_handler = bpy.types.SpaceView3D.draw_handler_add(
                _draw_overlay, (), "WINDOW", "POST_VIEW"
            )
        except Exception:
            print("[Fyr Baker UV Selection Preview] Failed to register View3D draw handler:\n" + traceback.format_exc())

    # Image Editor activity handler
    if _image_handler is None:
        try:
            _image_handler = bpy.types.SpaceImageEditor.draw_handler_add(
                _uv_editor_activity_callback, (), "WINDOW", "POST_PIXEL"
            )
        except Exception:
            print("[Fyr Baker UV Selection Preview] Failed to register Image Editor draw handler:\n" + traceback.format_exc())

    # Depsgraph handler
    if _depsgraph_handler is None:
        try:
            _depsgraph_handler = _on_depsgraph_update
            if _on_depsgraph_update not in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph_update)
        except Exception:
            pass

    # Load post handler
    if _load_post_handler is None:
        try:
            _load_post_handler = _on_load_post
            if _on_load_post not in bpy.app.handlers.load_post:
                bpy.app.handlers.load_post.append(_on_load_post)
        except Exception:
            pass

    # Low-frequency fallback timer
    if not _timer_registered:
        try:
            bpy.app.timers.register(_timer_fallback, first_interval=0.5, persistent=True)
            _timer_registered = True
        except Exception:
            pass


def unregister():
    global _view3d_handler, _image_handler, _depsgraph_handler, _load_post_handler, _timer_registered

    # Remove 3D Viewport draw handler
    if _view3d_handler is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_view3d_handler, "WINDOW")
        except Exception:
            pass
        _view3d_handler = None

    # Remove Image Editor draw handler
    if _image_handler is not None:
        try:
            bpy.types.SpaceImageEditor.draw_handler_remove(_image_handler, "WINDOW")
        except Exception:
            pass
        _image_handler = None

    # Remove depsgraph handler
    if _depsgraph_handler is not None:
        try:
            if _on_depsgraph_update in bpy.app.handlers.depsgraph_update_post:
                bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph_update)
        except Exception:
            pass
        _depsgraph_handler = None

    # Remove load post handler
    if _load_post_handler is not None:
        try:
            if _on_load_post in bpy.app.handlers.load_post:
                bpy.app.handlers.load_post.remove(_on_load_post)
        except Exception:
            pass
        _load_post_handler = None

    # Remove timer
    if _timer_registered:
        try:
            if bpy.app.timers.is_registered(_timer_fallback):
                bpy.app.timers.unregister(_timer_fallback)
        except Exception:
            pass
        _timer_registered = False

    # Clear cache
    _cache.invalidate()
    _cache.selection_signature = None
    _cache.topology_signature = None
    _cache.logged_errors.clear()

    # Remove properties
    safe_remove_attr(bpy.types.Scene, "fyr_baker_uv_selection_preview")

    for cls in reversed(CLASSES):
        safe_unregister_class(cls)
