from __future__ import annotations

from array import array
from dataclasses import dataclass
from pathlib import Path
import struct
import traceback
from typing import TYPE_CHECKING

import bpy
import gpu

from . import mesh_read
from . import cage, cage_session, export, properties, runtime
from .overlay_events import tag_redraw_all_view3d as _tag_redraw_all_view3d_impl
from .overlay_keys import (
    group_role_assignments_state as _group_role_assignments_state,
    iter_unique_role_slots as _iter_unique_role_slots,
    overlay_settings_state as _overlay_settings_state,
)

if TYPE_CHECKING:
    from mathutils import Vector


_SDF_MAGIC = b"MBCSDF1\0"
_DISTANCE_CHECK_MAX_SLOT_OFFSETS = 64

# Cage-check coverage is drawn over the group's own low/high meshes, which sit within
# millimetres of it. Without pulling the overlay toward the viewer the scene surfaces win
# the LESS_EQUAL depth test per pixel and punch fake "miss" speckle into the coverage paint.
_OVERLAY_DEPTH_BIAS_CLIP = 1.5e-4
_OVERLAY_DEPTH_BIAS_FLOOR = 1.0e-6
# The proportional term keeps the bias a CONSTANT ndc depth (bias/w = 1.5e-4) while the
# scene's own ndc gaps shrink with the square of the view distance — so zoomed out the
# biased coverage depth crosses the cage shell, and because the coverage pass WRITES
# depth (overlay_renderer passes depth_write=True) the cage passes then lose their depth
# test and the paint reads as sitting on top of the cage. depthBiasClipCap caps the bias
# at a WORLD distance (a fraction of the cage offset) mapped through the projection:
# shifting a point d toward the viewer at eye depth w moves ndc z by proj_scale*d/w^2
# (proj_scale = |P[2][3]| perspective / |P[2][2]| ortho — verified numerically), and our
# clip-z-only hack shifts ndc by bias/w, so bias <= proj_scale*d_max/w. The uniform
# carries proj_scale*d_max (see _depth_bias_clip_cap); the shader divides by |w|.
_OVERLAY_DEPTH_BIAS_GLSL = (
    "  vec4 biasedPosition = ModelViewProjectionMatrix * vec4(position, 1.0);\n"
    "  float absW = max(abs(biasedPosition.w), 1.0e-9);\n"
    f"  biasedPosition.z -= max(min(absW * {_OVERLAY_DEPTH_BIAS_CLIP:.8f},"
    f" depthBiasClipCap / absW), {_OVERLAY_DEPTH_BIAS_FLOOR:.8f});\n"
    "  gl_Position = biasedPosition;\n"
)
_HIGH_OVERLAY_DEPTH_BIAS_GLSL = _OVERLAY_DEPTH_BIAS_GLSL.replace(
    "vec4(position, 1.0)", "vec4(worldPosition, 1.0)"
)

_SDF_VERTEX_GLSL = (
    "void main()\n"
    "{\n"
    "  worldPosition = (ObjectMatrix * vec4(position, 1.0)).xyz;\n"
    f"{_HIGH_OVERLAY_DEPTH_BIAS_GLSL}"
    "}\n"
)

_SHELL_VERTEX_GLSL = (
    "void main()\n"
    "{\n"
    "  worldPosition = (ObjectMatrix * vec4(position, 1.0)).xyz;\n"
    "  highViewDepth = -(ModelViewMatrix * vec4(worldPosition, 1.0)).z;\n"
    f"{_HIGH_OVERLAY_DEPTH_BIAS_GLSL}"
    "}\n"
)

_SOLID_HIGH_VERTEX_GLSL = _SHELL_VERTEX_GLSL

_DISTANCE_SCALAR_VERTEX_GLSL = (
    "void main()\n"
    "{\n"
    "  worldNormal = normalize(normal);\n"
    "  requiredOffset = requiredOffsetIn;\n"
    "  slotIndex = slotIndexIn;\n"
    f"{_OVERLAY_DEPTH_BIAS_GLSL}"
    "}\n"
)


@dataclass(slots=True)
class _SdfTexture:
    path: str
    signature: str
    resolution: tuple[int, int, int]
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]
    voxel_size: float
    texture: object


@dataclass(slots=True)
class _HighMeshBatch:
    signature: tuple
    batch: object
    object_ref: object
    estimated_gpu_bytes: int = 0


@dataclass(slots=True)
class _ProgressiveHighMeshBatch:
    vertex_buffer: object | None
    triangle_indices: object | None
    triangle_soup_positions: object | None
    triangle_count: int
    batches: list[object]
    object_matrix: object
    cursor: int = 0

    def draw(self, shader) -> None:
        shader.bind()
        shader.uniform_float("ObjectMatrix", self.object_matrix)
        for batch in self.batches:
            batch.draw(shader)


@dataclass(slots=True)
class _DistanceCheckBatch:
    signature: tuple
    batch: object
    object_ref: object
    vertex_count: int
    required_min: float
    required_max: float
    slot_count: int


@dataclass(slots=True)
class _DistanceLowSurface:
    triangles: list[cage.TriangleData]
    slot_indices: list[int]


@dataclass(slots=True)
class _PendingDistanceCheckBuild:
    """A queued distance-check build, held by NAME only.

    Builds are chunked across app-timer ticks, so a queued entry routinely waits
    seconds before it starts. Keeping the PropertyGroup / Object itself here would
    leave the timer dereferencing freed RNA whenever the group is removed, or a
    memfile undo rebuilds the project's CollectionProperty storage, while the entry
    waits -- the same crash class that cost this addon two shipped crashes (see
    OverlayPass.offset_group_name in overlay_cache.py). The timer re-resolves these
    names against the live project and drops the entry when they are gone.
    """

    project_name: str
    group_name: str
    object_name: str


@dataclass(slots=True)
class _DistanceCheckBuildJob:
    """In-progress chunked build of a distance-check batch. The per-vertex
    nearest-surface query is spread across app-timer ticks so a multi-million
    vertex high mesh never blocks the main thread in a single callback."""

    key: tuple
    group: object
    obj: object
    prep: dict
    required: object  # numpy (N,) float32
    slot: object  # numpy (N,) float32
    vertex_count: int
    cursor: int = 0


_SDF_TEXTURE_CACHE: dict[tuple[str, str], _SdfTexture] = {}
_HIGH_MESH_BATCH_CACHE: dict[int, _HighMeshBatch] = {}
_HIGH_MESH_BUILD_QUEUE: dict[int, _HighMeshBatch] = {}
_HIGH_MESH_BUILD_TIMER_REGISTERED = False
# Keep each main-thread GPU upload short enough for interactive viewport work.
_HIGH_MESH_INDEX_CHUNK_TRIANGLES = 524_288
# Position + uint32 triangle-index storage. The one active CPU index snapshot is
# temporary and released when streaming completes.
_HIGH_MESH_BATCH_CACHE_BUDGET_BYTES = 640 * 1024 * 1024
_DISTANCE_CHECK_BATCH_CACHE: dict[tuple, _DistanceCheckBatch] = {}
_HIGH_MESH_FAILURE_SIGNATURES: dict[tuple[str, int], tuple] = {}  # (kind, pointer) -> signature; mesh-batch and distance-check signatures live in different spaces
_PENDING_DISTANCE_CHECK_BUILDS: dict[tuple, _PendingDistanceCheckBuild] = {}
_ACTIVE_DISTANCE_CHECK_JOB: _DistanceCheckBuildJob | None = None
# Vertices processed per timer tick. Sized so one tick stays under ~70ms on a
# dense high mesh (measured: 150k vertices = ~270ms/tick, which reads as the
# viewport "lagging out" during the whole build) — smaller chunks keep the UI
# responsive for the same total build time.
_DISTANCE_CHECK_CHUNK = 40000
# Invalidate pre-enclosure batches after a dev reload.
_DISTANCE_CHECK_MATH_VERSION = 4
# One bounded source snapshot avoids recapturing high geometry on offset drags.
_DISTANCE_CHECK_SOURCE_CACHE = None
_DISTANCE_CHECK_SOURCE_CACHE_BYTES = 64 * 1024 * 1024
_DISTANCE_CHECK_BUILD_TIMER_REGISTERED = False
_SHADER = None
_SHELL_SHADER = None
_SOLID_HIGH_SHADER = None
_HIGH_DEPTH_SHADER = None
_BENEATH_SHADER = None
_DISTANCE_SCALAR_SHADER = None
# Compute-shader nearest-surface path: brute-forces the (small) low surface for
# every high vertex on the GPU — ~40x faster than the serial CPU BVH loop and
# exact to float32. None = not yet probed, False = unavailable (falls back to the
# CPU path). Texel packing width for the vertex I/O textures.
_DISTANCE_CHECK_COMPUTE_SHADER = None
_DISTANCE_CHECK_COMPUTE_SUPPORTED: bool | None = None
_COVERAGE_NEAREST_COMPUTE_SHADER = None
_COVERAGE_NEAREST_COMPUTE_SUPPORTED: bool | None = None
_DISTANCE_CHECK_COMPUTE_TEX_WIDTH = 8192
_DISTANCE_CHECK_COMPUTE_MAX_TEX = 16384
_LAST_ERROR = ""
_LAST_SHELL_DRAW_STATUS: dict[str, object] = {}


def _role_slot_count(group, attr_name: str) -> int:
    return sum(1 for _slot in _iter_unique_role_slots(group, attr_name))


def _iter_high_objects(group):
    for slot in _iter_unique_role_slots(group, "high_meshes"):
        obj = getattr(slot, "object_ref", None)
        if obj is not None and getattr(obj, "type", None) == "MESH":
            yield obj


def _iter_low_objects(group):
    for slot in _iter_unique_role_slots(group, "low_meshes"):
        obj = getattr(slot, "object_ref", None)
        if obj is not None and getattr(obj, "type", None) == "MESH":
            yield obj


def _make_vector(values):
    vector_type = getattr(cage, "Vector", None)
    if vector_type is None:
        from mathutils import Vector as vector_type
    return vector_type(values)


from .modifier_signature import (  # noqa: E402
    MODIFIER_PROPERTY_NAMES as _MODIFIER_PROPERTY_NAMES,
    modifier_stack_signature as _modifier_stack_signature,
)


def _vector_signature(values) -> tuple:
    if values is None:
        return ()
    try:
        return tuple(round(float(value), 6) for value in values)
    except Exception:
        return ()


def _deform_signature(obj) -> tuple:
    """Identity for deformation the modifier stack's own properties do not carry.

    An Armature modifier only contributes its rig's pointer, which does not change when
    the rig is POSED, and shape-key values are not in the stack at all. The batch this
    guards comes from the evaluated mesh, so a posed character or a moved shape-key
    slider kept drawing the coverage of the rest pose -- correct-looking and wrong.
    Only the bones this object's Armature modifiers actually use are read.
    """
    values: list[object] = []
    data = getattr(obj, "data", None)
    shape_keys = getattr(data, "shape_keys", None) if data is not None else None
    key_blocks = getattr(shape_keys, "key_blocks", None) if shape_keys is not None else None
    try:
        for block in key_blocks or ():
            values.append((str(getattr(block, "name", "") or ""), round(float(getattr(block, "value", 0.0)), 6)))
    except Exception:
        return ()
    try:
        for modifier in getattr(obj, "modifiers", None) or ():
            if str(getattr(modifier, "type", "") or "") != "ARMATURE":
                continue
            rig = getattr(modifier, "object", None)
            pose = getattr(rig, "pose", None)
            for bone in getattr(pose, "bones", None) or ():
                # The pose channels rather than matrix_basis: same information, three
                # short vector reads instead of building a 4x4 per bone on the draw path.
                values.append((
                    _vector_signature(getattr(bone, "location", None)),
                    _vector_signature(getattr(bone, "rotation_quaternion", None)),
                    _vector_signature(getattr(bone, "rotation_euler", None)),
                    _vector_signature(getattr(bone, "scale", None)),
                ))
    except Exception:
        return ()
    return tuple(values)


def _mesh_signature(obj) -> tuple:
    data = getattr(obj, "data", None)
    vertex_count = mesh_read.element_count(data, "vertices")
    polygon_count = mesh_read.element_count(data, "polygons")
    loop_count = mesh_read.element_count(data, "loops")
    return (
        int(obj.as_pointer()) if hasattr(obj, "as_pointer") else id(obj),
        int(data.as_pointer()) if data is not None and hasattr(data, "as_pointer") else 0,
        vertex_count,
        polygon_count,
        loop_count,
        _matrix_signature(getattr(obj, "matrix_world", None)),
        bool(getattr(data, "is_editmode", False)) if data is not None else False,
        _modifier_stack_signature(obj),
        _deform_signature(obj),
    )


def _matrix_signature(matrix) -> tuple:
    if matrix is None:
        return ()
    values: list[float] = []
    try:
        for row in matrix:
            for value in row:
                values.append(round(float(value), 6))
    except Exception:
        return ()
    return tuple(values)


def _get_shader():
    global _SHADER
    if _SHADER is not None:
        return _SHADER
    info = gpu.types.GPUShaderCreateInfo()
    vert_out = gpu.types.GPUStageInterfaceInfo("fyr_cage_check_iface")
    vert_out.smooth("VEC3", "worldPosition")
    info.vertex_out(vert_out)
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("MAT4", "ObjectMatrix")
    info.push_constant("VEC3", "sdfBoundsMin")
    info.push_constant("VEC3", "sdfBoundsInvSize")
    info.push_constant("FLOAT", "distanceTolerance")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.vertex_in(0, "VEC3", "position")
    info.sampler(0, "FLOAT_3D", "cageSdf")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(_SDF_VERTEX_GLSL)
    info.fragment_source(
        """
        void main()
        {
          vec3 uvw = (worldPosition - sdfBoundsMin) * sdfBoundsInvSize;
          bool outsideAtlas = any(lessThan(uvw, vec3(0.0))) || any(greaterThan(uvw, vec3(1.0)));
          float signedDistance = outsideAtlas ? 1.0 : texture(cageSdf, uvw).r;
          vec4 baseColor = signedDistance <= distanceTolerance
            ? vec4(0.12, 0.46, 1.0, 0.78)
            : vec4(1.0, 0.08, 0.04, 0.86);
          vec3 n = normalize(cross(dFdx(worldPosition), dFdy(worldPosition)));
          vec3 light = normalize(vec3(0.31, 0.42, 0.85));
          float diffuse = 0.35 + 0.65 * abs(dot(n, light));
          FragColor = vec4(baseColor.rgb * diffuse, baseColor.a);
        }
        """
    )
    _SHADER = gpu.shader.create_from_info(info)
    del info
    return _SHADER


def _get_shell_shader():
    global _SHELL_SHADER
    if _SHELL_SHADER is not None:
        return _SHELL_SHADER
    info = gpu.types.GPUShaderCreateInfo()
    vert_out = gpu.types.GPUStageInterfaceInfo("fyr_cage_shell_check_iface")
    vert_out.smooth("VEC3", "worldPosition")
    vert_out.smooth("FLOAT", "highViewDepth")
    info.vertex_out(vert_out)
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("MAT4", "ModelViewMatrix")
    info.push_constant("MAT4", "ObjectMatrix")
    info.push_constant("VEC2", "viewportOrigin")
    info.push_constant("VEC2", "viewportSize")
    info.push_constant("VEC2", "depthTextureSize")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.vertex_in(0, "VEC3", "position")
    info.sampler(0, "FLOAT_2D", "cageDepthTexture")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(_SHELL_VERTEX_GLSL)
    info.fragment_source(
        f"""
        void main()
        {{
          vec2 coord = gl_FragCoord.xy - viewportOrigin;
          if (coord.x < 0.0 || coord.y < 0.0 || coord.x >= viewportSize.x || coord.y >= viewportSize.y) {{
            discard;
          }}
          ivec2 textureSize = max(ivec2(depthTextureSize), ivec2(1));
          ivec2 pixel = clamp(ivec2(coord), ivec2(0), textureSize - ivec2(1));
          vec4 cageSample = texelFetch(cageDepthTexture, pixel, 0);
          // Linear camera-space depth keeps the cage/high comparison invariant
          // under zoom. Keep only a couple of R32F ULPs for independently
          // rasterized coincident surfaces; the former 1e-5 world tolerance
          // visibly pushed a shallow intersection into the covered side.
          bool hasShellMask = cageSample.r >= 0.0;
          float comparisonTolerance = max(abs(cageSample.r) * 2.5e-7, 1.0e-7);
          bool insideShell = hasShellMask && highViewDepth >= (cageSample.r - comparisonTolerance);
          vec4 baseColor = insideShell
            ? vec4(0.12, 0.46, 1.0, 1.0)
            : (hasShellMask ? vec4(1.0, 0.08, 0.04, 1.0) : vec4(1.0, 0.08, 0.04, 0.35));
          vec3 n = normalize(cross(dFdx(worldPosition), dFdy(worldPosition)));
          vec3 light = normalize(vec3(0.31, 0.42, 0.85));
          float diffuse = 0.35 + 0.65 * abs(dot(n, light));
          FragColor = vec4(baseColor.rgb * diffuse, baseColor.a);
        }}
        """
    )
    _SHELL_SHADER = gpu.shader.create_from_info(info)
    del info
    return _SHELL_SHADER


def _get_high_depth_shader():
    """The high's front view depth into an R32F mask (the beneath-the-low pass reads it)."""
    global _HIGH_DEPTH_SHADER
    if _HIGH_DEPTH_SHADER is not None:
        return _HIGH_DEPTH_SHADER
    info = gpu.types.GPUShaderCreateInfo()
    vert_out = gpu.types.GPUStageInterfaceInfo("fyr_cage_high_depth_iface")
    vert_out.smooth("FLOAT", "viewDepth")
    info.vertex_out(vert_out)
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("MAT4", "ModelViewMatrix")
    info.push_constant("MAT4", "ObjectMatrix")
    info.vertex_in(0, "VEC3", "position")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        "void main()\n"
        "{\n"
        "  vec4 world = ObjectMatrix * vec4(position, 1.0);\n"
        "  gl_Position = ModelViewProjectionMatrix * world;\n"
        "  viewDepth = -(ModelViewMatrix * world).z;\n"
        "}\n"
    )
    info.fragment_source("void main()\n{\n  FragColor = vec4(viewDepth, 0.0, 0.0, 1.0);\n}\n")
    _HIGH_DEPTH_SHADER = gpu.shader.create_from_info(info)
    del vert_out
    del info
    return _HIGH_DEPTH_SHADER


def _get_beneath_shader():
    """Colours the low where its own high lies UNDER it.

    The low hides that high from the viewport, so the high's coverage paint cannot show
    and the spot read as plain grey ("no data"). The bake still reaches it: every ray
    runs past the low by the rear allowance (projection_rear_allowance). Blue = within
    that reach (captured), red = deeper (missed). The distance is the view-depth gap
    turned into a distance along the low's normal.
    """
    global _BENEATH_SHADER
    if _BENEATH_SHADER is not None:
        return _BENEATH_SHADER
    info = gpu.types.GPUShaderCreateInfo()
    vert_out = gpu.types.GPUStageInterfaceInfo("fyr_cage_beneath_iface")
    vert_out.smooth("VEC3", "viewPosition")
    vert_out.smooth("VEC3", "worldPosition")
    info.vertex_out(vert_out)
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("MAT4", "ModelViewMatrix")
    info.push_constant("MAT4", "ObjectMatrix")
    info.push_constant("VEC2", "viewportOrigin")
    info.push_constant("VEC2", "viewportSize")
    info.push_constant("VEC2", "depthTextureSize")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.push_constant("FLOAT", "rearReach")
    info.vertex_in(0, "VEC3", "position")
    info.sampler(0, "FLOAT_2D", "highDepthTexture")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(
        "void main()\n"
        "{\n"
        "  worldPosition = (ObjectMatrix * vec4(position, 1.0)).xyz;\n"
        "  viewPosition =(ModelViewMatrix * vec4(worldPosition, 1.0)).xyz;\n"
        f"{_HIGH_OVERLAY_DEPTH_BIAS_GLSL}"
        "}\n"
    )
    info.fragment_source(
        """
        void main()
        {
          vec2 coord = gl_FragCoord.xy - viewportOrigin;
          if (coord.x < 0.0 || coord.y < 0.0 || coord.x >= viewportSize.x || coord.y >= viewportSize.y) {
            discard;
          }
          ivec2 textureSize = max(ivec2(depthTextureSize), ivec2(1));
          ivec2 pixel = clamp(ivec2(coord), ivec2(0), textureSize - ivec2(1));
          float highDepth = texelFetch(highDepthTexture, pixel, 0).r;
          float lowDepth = -viewPosition.z;
          if (highDepth < 0.0 || lowDepth <= 0.0) {
            discard;
          }
          // The high at or in front of the low draws its own coverage.
          float gap = highDepth - lowDepth;
          if (gap <= max(lowDepth * 1.0e-6, 1.0e-6)) {
            discard;
          }
          vec3 n = normalize(cross(dFdx(viewPosition), dFdy(viewPosition)));
          vec3 toEye = normalize(-viewPosition);
          float alongRay = gap * length(viewPosition) / lowDepth;
          float normalDistance = alongRay * abs(dot(n, toEye));
          vec4 baseColor = normalDistance <= rearReach ? vec4(0.12, 0.46, 1.0, 1.0) : vec4(1.0, 0.08, 0.04, 1.0);
          // Lit like the high's own coverage paint (world-space face normal).
          vec3 worldNormal = normalize(cross(dFdx(worldPosition), dFdy(worldPosition)));
          vec3 light = normalize(vec3(0.31, 0.42, 0.85));
          float diffuse = 0.35 + 0.65 * abs(dot(worldNormal, light));
          FragColor = vec4(baseColor.rgb * diffuse, baseColor.a);
        }
        """
    )
    _BENEATH_SHADER = gpu.shader.create_from_info(info)
    del vert_out
    del info
    return _BENEATH_SHADER


def _low_rear_reach(group, obj) -> float:
    """How far behind *obj*'s surface the bake still finds the high (the group's Rear
    Distance, else max(cage offset, 5% of the low's world bounds diagonal); see
    projection_rear_allowance). Paint is ignored: it only moves the outward side."""
    projection_state = properties.group_projection_settings_state(group)
    rear = max(0.0, float(getattr(projection_state, "projection_rear_distance", 0.0) or 0.0))
    if rear > 0.0:
        return rear
    offset = max(0.0, float(getattr(group, "cage_offset", 0.0) or 0.0))
    diagonal = 0.0
    try:
        matrix = obj.matrix_world
        corners = [matrix @ _make_vector(corner) for corner in obj.bound_box]
        lo = [min(corner[axis] for corner in corners) for axis in range(3)]
        hi = [max(corner[axis] for corner in corners) for axis in range(3)]
        diagonal = sum((hi[axis] - lo[axis]) ** 2 for axis in range(3)) ** 0.5
    except Exception:
        diagonal = 0.0
    return max(offset, 0.05 * diagonal)


def _draw_high_beneath_low(context, group, model_view_projection_matrix, model_view_matrix, *, viewport_origin, viewport_size, width: int, height: int) -> bool:
    """Second half of the screen coverage: paint the low where its high lies under it."""
    from . import overlay_gpu, overlays

    state = overlays._OVERLAY_GPU_STATE
    original_viewport = gpu.state.viewport_get() if hasattr(gpu.state, "viewport_get") else None
    high_entries = [entry for entry in (_build_high_mesh_batch(context, obj) for obj in _iter_high_objects(group)) if entry is not None]
    if not high_entries:
        return False
    try:
        resources = overlay_gpu.ensure_shell_high_depth_mask_resources(state, int(width), int(height))
        if resources is None:
            return False
        with resources.framebuffer.bind():
            if hasattr(gpu.state, "viewport_set"):
                gpu.state.viewport_set(0, 0, resources.width, resources.height)
            resources.framebuffer.clear(color=(-1.0, 0.0, 0.0, 0.0), depth=1.0)
            gpu.state.blend_set("NONE")
            gpu.state.depth_test_set("LESS")
            gpu.state.depth_mask_set(True)
            shader = _get_high_depth_shader()
            shader.bind()
            shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
            shader.uniform_float("ModelViewMatrix", model_view_matrix)
            for entry in high_entries:
                entry.batch.draw(shader)
    finally:
        if original_viewport is not None and hasattr(gpu.state, "viewport_set"):
            gpu.state.viewport_set(*original_viewport)
    shader = _get_beneath_shader()
    shader.bind()
    shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
    shader.uniform_float("ModelViewMatrix", model_view_matrix)
    shader.uniform_float("viewportOrigin", viewport_origin or (0.0, 0.0))
    shader.uniform_float("viewportSize", viewport_size)
    shader.uniform_float("depthTextureSize", (float(resources.width), float(resources.height)))
    shader.uniform_float("depthBiasClipCap", _depth_bias_clip_cap(context, group))
    shader.uniform_sampler("highDepthTexture", resources.color_texture)
    gpu.state.depth_test_set("LESS_EQUAL")
    gpu.state.depth_mask_set(False)
    gpu.state.blend_set("NONE")
    drew_any = False
    for obj in _iter_low_objects(group):
        entry = _build_high_mesh_batch(context, obj)
        if entry is None:
            continue
        shader.bind()
        shader.uniform_float("rearReach", float(_low_rear_reach(group, obj)))
        entry.batch.draw(shader)
        drew_any = True
    return drew_any


def _get_solid_high_shader():
    global _SOLID_HIGH_SHADER
    if _SOLID_HIGH_SHADER is not None:
        return _SOLID_HIGH_SHADER
    info = gpu.types.GPUShaderCreateInfo()
    vert_out = gpu.types.GPUStageInterfaceInfo("fyr_solid_high_cage_check_iface")
    vert_out.smooth("VEC3", "worldPosition")
    info.vertex_out(vert_out)
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("MAT4", "ObjectMatrix")
    info.push_constant("VEC4", "color")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.vertex_in(0, "VEC3", "position")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(_SOLID_HIGH_VERTEX_GLSL)
    info.fragment_source(
        """
        void main()
        {
          vec3 n = normalize(cross(dFdx(worldPosition), dFdy(worldPosition)));
          vec3 light = normalize(vec3(0.31, 0.42, 0.85));
          float diffuse = 0.35 + 0.65 * abs(dot(n, light));
          FragColor = vec4(color.rgb * diffuse, color.a);
        }
        """
    )
    _SOLID_HIGH_SHADER = gpu.shader.create_from_info(info)
    del info
    return _SOLID_HIGH_SHADER


def _get_distance_scalar_shader():
    global _DISTANCE_SCALAR_SHADER
    if _DISTANCE_SCALAR_SHADER is not None:
        return _DISTANCE_SCALAR_SHADER
    info = gpu.types.GPUShaderCreateInfo()
    vert_out = gpu.types.GPUStageInterfaceInfo("fyr_distance_cage_check_iface")
    vert_out.smooth("VEC3", "worldNormal")
    vert_out.smooth("FLOAT", "requiredOffset")
    vert_out.flat("FLOAT", "slotIndex")
    info.vertex_out(vert_out)
    info.push_constant("MAT4", "ModelViewProjectionMatrix")
    info.push_constant("FLOAT", "slotOffset")
    info.push_constant("FLOAT", "activeSlotIndex")
    info.push_constant("FLOAT", "distanceTolerance")
    info.push_constant("FLOAT", "depthBiasClipCap")
    info.vertex_in(0, "VEC3", "position")
    info.vertex_in(1, "VEC3", "normal")
    info.vertex_in(2, "FLOAT", "requiredOffsetIn")
    info.vertex_in(3, "FLOAT", "slotIndexIn")
    info.fragment_out(0, "VEC4", "FragColor")
    info.vertex_source(_DISTANCE_SCALAR_VERTEX_GLSL)
    info.fragment_source(
        """
        void main()
        {
          if (abs(slotIndex - activeSlotIndex) > 0.25) {
            discard;
          }
          bool insideCage = requiredOffset <= (slotOffset + distanceTolerance);
          vec3 baseColor = insideCage ? vec3(0.12, 0.46, 1.0) : vec3(1.0, 0.08, 0.04);
          vec3 n = normalize(worldNormal);
          vec3 light = normalize(vec3(0.31, 0.42, 0.85));
          float diffuse = 0.35 + 0.65 * abs(dot(n, light));
          FragColor = vec4(baseColor * diffuse, 1.0);
        }
        """
    )
    _DISTANCE_SCALAR_SHADER = gpu.shader.create_from_info(info)
    del info
    return _DISTANCE_SCALAR_SHADER


def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<I", data, offset)[0], offset + 4


def _read_f32(data: bytes, offset: int) -> tuple[float, int]:
    return struct.unpack_from("<f", data, offset)[0], offset + 4


def _load_sdf_texture(debug_result) -> _SdfTexture | None:
    path_text = str(getattr(debug_result, "cage_sdf_path", "") or "").strip()
    signature = str(getattr(debug_result, "cage_sdf_signature", "") or "")
    if not path_text or not signature:
        return None
    cache_key = (path_text, signature)
    cached = _SDF_TEXTURE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    gpu_types = getattr(gpu, "types", None)
    if gpu_types is None or not hasattr(gpu_types, "GPUTexture") or not hasattr(gpu_types, "Buffer"):
        _log_error_once("[Fyr Baker] Cage Check overlay unavailable: Blender GPU texture buffers are not available.")
        return None
    path = Path(path_text)
    if not path.exists():
        _log_error_once(f"[Fyr Baker] Cage Check SDF is missing: {path_text}")
        return None
    raw = path.read_bytes()
    if len(raw) < 48 or raw[:8] != _SDF_MAGIC:
        _log_error_once(f"[Fyr Baker] Cage Check SDF has an invalid header: {path_text}")
        return None
    offset = 8
    width, offset = _read_u32(raw, offset)
    height, offset = _read_u32(raw, offset)
    depth, offset = _read_u32(raw, offset)
    min_x, offset = _read_f32(raw, offset)
    min_y, offset = _read_f32(raw, offset)
    min_z, offset = _read_f32(raw, offset)
    max_x, offset = _read_f32(raw, offset)
    max_y, offset = _read_f32(raw, offset)
    max_z, offset = _read_f32(raw, offset)
    voxel_size, offset = _read_f32(raw, offset)
    expected_values = int(width) * int(height) * int(depth)
    if width <= 0 or height <= 0 or depth <= 0 or len(raw) < offset + expected_values * 4:
        _log_error_once(f"[Fyr Baker] Cage Check SDF has invalid dimensions or data size: {path_text}")
        return None
    values = array("f")
    values.frombytes(raw[offset:offset + expected_values * 4])
    if values.itemsize != 4:
        _log_error_once("[Fyr Baker] Cage Check overlay unavailable: Python float buffer is not 32-bit.")
        return None
    try:
        texture_data = gpu.types.Buffer("FLOAT", expected_values, values)
        texture = gpu.types.GPUTexture((int(width), int(height), int(depth)), format="R32F", data=texture_data)
    except Exception:
        _log_error_once("[Fyr Baker] Cage Check overlay failed to create its GPU SDF texture:\n" + traceback.format_exc())
        return None
    cached = _SdfTexture(
        path=path_text,
        signature=signature,
        resolution=(int(width), int(height), int(depth)),
        bounds_min=(float(min_x), float(min_y), float(min_z)),
        bounds_max=(float(max_x), float(max_y), float(max_z)),
        voxel_size=float(voxel_size),
        texture=texture,
    )
    if len(_SDF_TEXTURE_CACHE) > 4:
        _SDF_TEXTURE_CACHE.clear()
    _SDF_TEXTURE_CACHE[cache_key] = cached
    return cached


def _foreach_get_float_rows(collection, attr: str, row_count: int, component_count: int):
    try:
        import numpy as np
    except Exception:
        np = None
    if np is not None:
        values = np.empty(int(row_count) * int(component_count), dtype=np.float32)
        if hasattr(collection, "foreach_get"):
            collection.foreach_get(attr, values)
            return values.reshape(int(row_count), int(component_count))
        return None
    values = array("f", [0.0]) * (int(row_count) * int(component_count))
    if hasattr(collection, "foreach_get"):
        collection.foreach_get(attr, values)
        return [tuple(values[index:index + component_count]) for index in range(0, len(values), component_count)]
    return None


def _foreach_get_int_rows(collection, attr: str, row_count: int, component_count: int):
    try:
        import numpy as np
    except Exception:
        np = None
    if np is not None:
        # uintc: the buffer format Blender's foreach_get fast path matches for these properties.
        values = np.empty(int(row_count) * int(component_count), dtype=np.uintc)
        if hasattr(collection, "foreach_get"):
            collection.foreach_get(attr, values)
            values = values.view(np.int32)
            return values.reshape(int(row_count), int(component_count))
        return None
    values = array("i", [0]) * (int(row_count) * int(component_count))
    if hasattr(collection, "foreach_get"):
        collection.foreach_get(attr, values)
        return [tuple(values[index:index + component_count]) for index in range(0, len(values), component_count)]
    return None


def _evict_high_mesh_batches_for(incoming_bytes: int, *, keep_pointer: int = 0) -> None:
    budget = int(_HIGH_MESH_BATCH_CACHE_BUDGET_BYTES)
    total = sum(int(entry.estimated_gpu_bytes) for entry in _HIGH_MESH_BATCH_CACHE.values())
    while _HIGH_MESH_BATCH_CACHE and total + int(incoming_bytes) > budget:
        pointer = next(iter(_HIGH_MESH_BATCH_CACHE))
        if pointer == keep_pointer and len(_HIGH_MESH_BATCH_CACHE) > 1:
            entry = _HIGH_MESH_BATCH_CACHE.pop(pointer)
            _HIGH_MESH_BATCH_CACHE[pointer] = entry
            continue
        removed = _HIGH_MESH_BATCH_CACHE.pop(pointer)
        _HIGH_MESH_BUILD_QUEUE.pop(pointer, None)
        total -= int(removed.estimated_gpu_bytes)


def _append_high_mesh_index_chunk(entry: _HighMeshBatch) -> bool:
    progressive = entry.batch
    soup_positions = getattr(progressive, "triangle_soup_positions", None)
    if soup_positions is not None:
        start = int(progressive.cursor)
        if start >= int(progressive.triangle_count):
            progressive.triangle_soup_positions = None
            return True
        end = min(
            int(progressive.triangle_count),
            start + int(_HIGH_MESH_INDEX_CHUNK_TRIANGLES),
        )
        fmt = gpu.types.GPUVertFormat()
        fmt.attr_add(id="position", comp_type="F32", len=3, fetch_mode="FLOAT")
        vertex_buffer = gpu.types.GPUVertBuf(fmt, (end - start) * 3)
        vertex_buffer.attr_fill("position", soup_positions[start * 3:end * 3])
        progressive.batches.append(gpu.types.GPUBatch(type="TRIS", buf=vertex_buffer))
        progressive.cursor = end
        if end >= int(progressive.triangle_count):
            progressive.triangle_soup_positions = None
            return True
        return False
    indices = getattr(progressive, "triangle_indices", None)
    if indices is None:
        return True
    start = int(progressive.cursor)
    if start >= int(progressive.triangle_count):
        progressive.triangle_indices = None
        return True
    end = min(
        int(progressive.triangle_count),
        start + int(_HIGH_MESH_INDEX_CHUNK_TRIANGLES),
    )
    index_buffer = gpu.types.GPUIndexBuf(type="TRIS", seq=indices[start:end])
    progressive.batches.append(
        gpu.types.GPUBatch(type="TRIS", buf=progressive.vertex_buffer, elem=index_buffer)
    )
    progressive.cursor = end
    if end >= int(progressive.triangle_count):
        progressive.triangle_indices = None
        return True
    return False


def _high_mesh_build_timer():
    global _HIGH_MESH_BUILD_TIMER_REGISTERED
    try:
        if not _HIGH_MESH_BUILD_QUEUE:
            _HIGH_MESH_BUILD_TIMER_REGISTERED = False
            return None
        pointer, entry = next(iter(_HIGH_MESH_BUILD_QUEUE.items()))
        cached = _HIGH_MESH_BATCH_CACHE.get(pointer)
        if cached is not entry:
            _HIGH_MESH_BUILD_QUEUE.pop(pointer, None)
            return 0.0 if _HIGH_MESH_BUILD_QUEUE else None
        complete = _append_high_mesh_index_chunk(entry)
        if complete:
            _HIGH_MESH_BUILD_QUEUE.pop(pointer, None)
        _tag_redraw_all_view3d()
    except Exception:
        _HIGH_MESH_BUILD_QUEUE.clear()
        _log_error_once(
            "[Fyr Baker] Cage coverage failed while streaming high-mesh indices:\n"
            + traceback.format_exc()
        )
    if _HIGH_MESH_BUILD_QUEUE:
        return 0.0
    _HIGH_MESH_BUILD_TIMER_REGISTERED = False
    return None


def _ensure_high_mesh_build_timer_registered() -> None:
    global _HIGH_MESH_BUILD_TIMER_REGISTERED
    if _HIGH_MESH_BUILD_TIMER_REGISTERED or not _HIGH_MESH_BUILD_QUEUE:
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    try:
        timers.register(_high_mesh_build_timer, first_interval=0.0)
        _HIGH_MESH_BUILD_TIMER_REGISTERED = True
    except Exception:
        _HIGH_MESH_BUILD_TIMER_REGISTERED = False


def _create_high_mesh_gpu_entry(
    *,
    signature,
    pointer: int,
    obj,
    positions,
    triangle_indices,
    object_matrix=None,
) -> _HighMeshBatch | None:
    import numpy as np

    positions = np.asarray(positions, dtype=np.float32)
    triangle_indices = np.asarray(triangle_indices)
    if object_matrix is None:
        object_matrix = (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    elif hasattr(object_matrix, "copy"):
        object_matrix = object_matrix.copy()
    vertex_count = int(positions.shape[0])
    triangle_count = int(triangle_indices.shape[0])
    estimated_gpu_bytes = vertex_count * 12 + triangle_count * 3 * 4
    _evict_high_mesh_batches_for(estimated_gpu_bytes)
    fmt = gpu.types.GPUVertFormat()
    fmt.attr_add(id="position", comp_type="F32", len=3, fetch_mode="FLOAT")
    try:
        vertex_buffer = gpu.types.GPUVertBuf(fmt, vertex_count)
        vertex_buffer.attr_fill("position", positions)
        batch = _ProgressiveHighMeshBatch(
            vertex_buffer=vertex_buffer,
            triangle_indices=triangle_indices,
            triangle_soup_positions=None,
            triangle_count=triangle_count,
            batches=[],
            object_matrix=object_matrix,
        )
        cached = _HighMeshBatch(
            signature=signature,
            batch=batch,
            object_ref=obj,
            estimated_gpu_bytes=estimated_gpu_bytes,
        )
        _HIGH_MESH_BATCH_CACHE[pointer] = cached
        complete = _append_high_mesh_index_chunk(cached)
        if not complete:
            _HIGH_MESH_BUILD_QUEUE[pointer] = cached
            _ensure_high_mesh_build_timer_registered()
        _HIGH_MESH_FAILURE_SIGNATURES.pop(("mesh", pointer), None)
        return cached
    except Exception:
        _HIGH_MESH_BATCH_CACHE.pop(pointer, None)
        _HIGH_MESH_BUILD_QUEUE.pop(pointer, None)
        _HIGH_MESH_FAILURE_SIGNATURES[("mesh", pointer)] = signature
        _log_error_once(
            "[Fyr Baker] Cage coverage failed to create a high-mesh GPU batch:\n"
            + traceback.format_exc()
        )
        return None


def _build_high_mesh_batch_from_warm_geometry(signature, pointer: int, obj):
    try:
        from . import high_mesh_cache, indexed_geometry, mesh_transport

        path = high_mesh_cache.warm_high_mesh_path(obj)
        if path is None:
            return None
        if path.suffix.lower() == ".fymesh":
            positions, triangle_count = mesh_transport.map_v4_positions(path)
            object_matrix = getattr(obj, "matrix_world", None)
            estimated_gpu_bytes = int(triangle_count) * 3 * 12
            if estimated_gpu_bytes > _HIGH_MESH_BATCH_CACHE_BUDGET_BYTES:
                # Do not let one expanded triangle stream exceed the entire cache.
                # The compact live-mesh fallback below stores shared vertices + indices.
                return None
            _evict_high_mesh_batches_for(estimated_gpu_bytes)
            if object_matrix is None:
                object_matrix = (
                    (1.0, 0.0, 0.0, 0.0),
                    (0.0, 1.0, 0.0, 0.0),
                    (0.0, 0.0, 1.0, 0.0),
                    (0.0, 0.0, 0.0, 1.0),
                )
            elif hasattr(object_matrix, "copy"):
                object_matrix = object_matrix.copy()
            progressive = _ProgressiveHighMeshBatch(
                vertex_buffer=None,
                triangle_indices=None,
                triangle_soup_positions=positions,
                triangle_count=int(triangle_count),
                batches=[],
                object_matrix=object_matrix,
            )
            cached = _HighMeshBatch(
                signature=signature,
                batch=progressive,
                object_ref=obj,
                estimated_gpu_bytes=estimated_gpu_bytes,
            )
            _HIGH_MESH_BATCH_CACHE[pointer] = cached
            complete = _append_high_mesh_index_chunk(cached)
            if not complete:
                _HIGH_MESH_BUILD_QUEUE[pointer] = cached
                _ensure_high_mesh_build_timer_registered()
            _HIGH_MESH_FAILURE_SIGNATURES.pop(("mesh", pointer), None)
            return cached
        view = indexed_geometry.map_canonical_positions_indices(path)
        return _create_high_mesh_gpu_entry(
            signature=signature,
            pointer=pointer,
            obj=obj,
            positions=view.positions,
            triangle_indices=view.indices,
            object_matrix=getattr(obj, "matrix_world", None),
        )
    except Exception:
        # A stale/incompatible persistent cache must never suppress the live
        # evaluated-mesh fallback below.
        return None


def _build_high_mesh_batch(context, obj) -> _HighMeshBatch | None:
    signature = _mesh_signature(obj)
    pointer = signature[0]
    cached = _HIGH_MESH_BATCH_CACHE.get(pointer)
    if cached is not None and cached.signature == signature:
        # Dict insertion order is our bounded LRU order.
        _HIGH_MESH_BATCH_CACHE.pop(pointer)
        _HIGH_MESH_BATCH_CACHE[pointer] = cached
        return cached
    if cached is not None:
        _HIGH_MESH_BATCH_CACHE.pop(pointer, None)
        _HIGH_MESH_BUILD_QUEUE.pop(pointer, None)
    if _HIGH_MESH_FAILURE_SIGNATURES.get(("mesh", pointer)) == signature:
        return None
    warm = _build_high_mesh_batch_from_warm_geometry(signature, pointer, obj)
    if warm is not None:
        return warm
    depsgraph = context.evaluated_depsgraph_get() if hasattr(context, "evaluated_depsgraph_get") else None
    obj_eval = obj.evaluated_get(depsgraph) if depsgraph is not None and hasattr(obj, "evaluated_get") else obj
    source_mesh = getattr(obj, "data", None)
    shape_keys = getattr(source_mesh, "shape_keys", None) if source_mesh is not None else None
    use_source_mesh = bool(
        source_mesh is not None
        and not bool(getattr(source_mesh, "is_editmode", False))
        and not tuple(getattr(obj, "modifiers", ()) or ())
        and shape_keys is None
    )
    mesh = source_mesh if use_source_mesh else (
        obj_eval.to_mesh() if hasattr(obj_eval, "to_mesh") else getattr(obj_eval, "data", None)
    )
    temporary_mesh = not use_source_mesh and hasattr(obj_eval, "to_mesh")
    if mesh is None:
        return None
    try:
        transform = getattr(mesh, "transform", None)
        object_matrix = getattr(obj_eval, "matrix_world", None)
        if object_matrix is None:
            object_matrix = getattr(obj, "matrix_world", None)
        if callable(transform) and object_matrix is not None and not use_source_mesh:
            transform(object_matrix)
            update = getattr(mesh, "update", None)
            if callable(update):
                update()
        calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc_loop_triangles):
            calc_loop_triangles()
        vertices = getattr(mesh, "vertices", None)
        loop_triangles = getattr(mesh, "loop_triangles", None)
        if vertices is None or loop_triangles is None or len(vertices) == 0 or len(loop_triangles) == 0:
            return None
        vertex_count = len(vertices)
        triangle_count = len(loop_triangles)
        positions = _foreach_get_float_rows(vertices, "co", vertex_count, 3)
        if positions is None:
            return None
        triangle_loop_indices = _foreach_get_int_rows(loop_triangles, "vertices", triangle_count, 3)
        if triangle_loop_indices is None:
            return None
        return _create_high_mesh_gpu_entry(
            signature=signature,
            pointer=pointer,
            obj=obj,
            positions=positions,
            triangle_indices=triangle_loop_indices,
            object_matrix=object_matrix if use_source_mesh else None,
        )
    finally:
        if temporary_mesh and hasattr(obj_eval, "to_mesh_clear"):
            obj_eval.to_mesh_clear()


def _triangle_face_normal(triangle: cage.TriangleData) -> Vector:
    point_a = triangle.corners[0].position
    point_b = triangle.corners[1].position
    point_c = triangle.corners[2].position
    normal = (point_b - point_a).cross(point_c - point_a)
    if normal.length_squared > 1.0e-12:
        normal.normalize()
    return normal


def _triangle_barycentric_weights(point: Vector, triangle: cage.TriangleData) -> tuple[float, float, float]:
    point_a = triangle.corners[0].position
    point_b = triangle.corners[1].position
    point_c = triangle.corners[2].position
    edge_0 = point_b - point_a
    edge_1 = point_c - point_a
    edge_2 = point - point_a
    d00 = float(edge_0.dot(edge_0))
    d01 = float(edge_0.dot(edge_1))
    d11 = float(edge_1.dot(edge_1))
    d20 = float(edge_2.dot(edge_0))
    d21 = float(edge_2.dot(edge_1))
    denom = d00 * d11 - d01 * d01
    if abs(denom) <= 1.0e-20:
        return (1.0, 0.0, 0.0)
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return (float(u), float(v), float(w))


def _nearest_low_projection(
    point,
    low_surface: _DistanceLowSurface,
    low_bvh,
) -> tuple[object, object, float] | None:
    try:
        location, normal, face_index, _distance = low_bvh.find_nearest(point)
    except Exception:
        location = normal = face_index = None
    if location is None:
        return None
    slot_index = 0
    if face_index is not None and 0 <= int(face_index) < len(low_surface.triangles):
        triangle_index = int(face_index)
        triangle = low_surface.triangles[triangle_index]
        if triangle_index < len(low_surface.slot_indices):
            slot_index = int(low_surface.slot_indices[triangle_index])
        weights = _triangle_barycentric_weights(location, triangle)
        projected_normal = _make_vector((0.0, 0.0, 0.0))
        for corner, weight in zip(triangle.corners, weights):
            projected_normal += corner.normal * float(weight)
        if projected_normal.length_squared <= 1.0e-12:
            projected_normal = _triangle_face_normal(triangle)
    else:
        projected_normal = normal.copy() if normal is not None else _make_vector((0.0, 0.0, 0.0))
    if projected_normal.length_squared <= 1.0e-12:
        return None
    return location, projected_normal, float(slot_index)


def _required_distance_offset(point, low_surface: _DistanceLowSurface, low_bvh) -> tuple[float, int]:
    nearest = _nearest_low_projection(point, low_surface, low_bvh)
    if nearest is None:
        return 1.0e6, 0
    location, scaled_normal, slot_index = nearest
    scale = float(scaled_normal.length)
    if scale <= 1.0e-12:
        return 1.0e6, int(slot_index)
    direction = scaled_normal.copy()
    direction.normalize()
    required_total_offset = max(0.0, float((point - location).dot(direction)) / scale)
    return required_total_offset, int(slot_index)


def _distance_low_signature(group) -> tuple:
    return tuple(_mesh_signature(obj) for obj in _iter_low_objects(group))


def _distance_low_slot_signature(group) -> tuple:
    return tuple(
        (
            int(getattr(getattr(slot, "object_ref", None), "as_pointer", lambda: 0)()),
            valid_index,
        )
        for valid_index, slot in enumerate(
            slot
            for slot in _iter_unique_role_slots(group, "low_meshes")
            if getattr(slot, "object_ref", None) is not None
            and getattr(getattr(slot, "object_ref", None), "type", None) == "MESH"
        )
        if getattr(slot, "object_ref", None) is not None and getattr(getattr(slot, "object_ref", None), "type", None) == "MESH"
    )


def _distance_check_signature(group, high_obj) -> tuple:
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    custom_cage = getattr(group, "custom_cage", None)
    custom_signature = (
        _mesh_signature(custom_cage)
        if custom_cage is not None and getattr(custom_cage, "type", None) == "MESH"
        else ()
    )
    # For Automatic/Custom the coverage shell is the fitted/custom cage, which depends on
    # the high meshes too — fold them (and the mode) into the key so a mode switch or a
    # high-mesh edit rebuilds the batch.
    high_signature = (
        tuple(_mesh_signature(obj) for obj in _iter_high_objects(group))
        if cage_mode in ("AUTOMATIC", "CUSTOM")
        else ()
    )
    return (
        "distance_scalar_v6",
        cage_mode,
        _mesh_signature(high_obj),
        _distance_low_signature(group),
        _distance_low_slot_signature(group),
        bool(cage.auto_cage_uses_average_normals(group)),
        custom_signature,
        high_signature,
        _distance_slot_offsets(group) if cage_mode == "DISTANCE" else (),
    )


def _slot_offset_delta(slot) -> float:
    return float(getattr(slot, "cage_offset_delta", 0.0) or 0.0)


def _inflate_triangle_normals(
    triangles: list[cage.TriangleData],
    inflation_lookup: dict[tuple[str, tuple[float, float, float]], float] | None,
    *,
    digits: int = 6,
) -> list[cage.TriangleData]:
    if not inflation_lookup:
        return triangles
    inflated: list[cage.TriangleData] = []
    source_position_group_key = getattr(cage, "_source_position_group_key", None)
    for triangle in triangles:
        corners = []
        for corner in triangle.corners:
            if callable(source_position_group_key):
                key = source_position_group_key(triangle.object_name, corner.source_position, digits=digits)
                inflation = float(inflation_lookup.get(key, 1.0))
            else:
                inflation = 1.0
            corners.append(
                cage.TriangleCorner(
                    source_position=corner.source_position.copy(),
                    position=corner.position.copy(),
                    uv=corner.uv,
                    normal=corner.normal * inflation,
                )
            )
        inflated.append(cage.TriangleData(object_name=triangle.object_name, corners=tuple(corners)))
    return inflated


def _capture_distance_low_surface(context, group) -> _DistanceLowSurface:
    depsgraph = context.evaluated_depsgraph_get() if hasattr(context, "evaluated_depsgraph_get") else None
    if depsgraph is None:
        return _DistanceLowSurface(triangles=[], slot_indices=[])
    smooth_normals = bool(cage.auto_cage_uses_average_normals(group))
    low_triangles: list[cage.TriangleData] = []
    slot_indices: list[int] = []
    valid_slot_index = 0
    for slot in _iter_unique_role_slots(group, "low_meshes"):
        low_obj = getattr(slot, "object_ref", None)
        if low_obj is None or getattr(low_obj, "type", None) != "MESH":
            continue
        slot_triangles = cage.capture_cage_source_triangles(
            low_obj,
            depsgraph,
            smooth_normals=smooth_normals,
        )
        low_triangles.extend(slot_triangles)
        slot_indices.extend([int(valid_slot_index)] * len(slot_triangles))
        valid_slot_index += 1
    return _DistanceLowSurface(triangles=low_triangles, slot_indices=slot_indices)


def _capture_auto_cage_offset_surface(context, group, depsgraph):
    """Return ``(low_source_triangles, corner_offsets)`` for the Automatic cage.

    The bake casts a ray from each low point up to the per-vertex cage distance, so coverage is
    ``required_reach <= offset`` measured against the LOW surface — not the fitted cage mesh, whose
    self-intersection makes a nearest-face test read garbage. ``corner_offsets[i]`` is the fitted
    per-vertex cage distance (from :func:`cage.build_coverage_offsets`, which maps every high vertex
    back to its nearest low face) at the three corners of low triangle ``i``.
    """
    smooth = bool(cage.auto_cage_uses_average_normals(group))
    isolate = bool(getattr(group, "match_by_isolation", False))
    low_objs = list(_iter_low_objects(group))
    high_objs = list(_iter_high_objects(group))
    if not low_objs or not high_objs:
        return [], []
    try:
        from .overlay_keys import object_cache_signature as _object_cache_signature

        high_key = tuple(_object_cache_signature(obj) for obj in high_objs)
        fit_key = (
            tuple(_object_cache_signature(obj) for obj in low_objs),
            high_key,
            bool(smooth),
            bool(isolate),
            # v6: cross-part reach clamp + Match By Isolation partitioning change the fit.
            "cage_check_coverage_v6",
        )
    except Exception:
        fit_key = None

    def _build(low_objs=tuple(low_objs), high_objs=tuple(high_objs), smooth=smooth, isolate=isolate):
        high_source_data = []
        high_object_names = []
        for obj in high_objs:
            captured = cage.capture_high_mesh_fit_source_data(obj, depsgraph)
            if captured is not None:
                high_source_data.append(captured)
                high_object_names.append(str(getattr(obj, "name", "")))
        if not high_source_data:
            return ([], [])
        # Fit all of the group's low meshes together so the coverage shell matches the tight fitted
        # cage (a per-mesh isolated fit balloons one low mesh out toward another's high detail).
        low_tri_groups = []
        for low_obj in low_objs:
            source_triangles = cage.capture_cage_source_triangles(low_obj, depsgraph, smooth_normals=smooth)
            if source_triangles:
                low_tri_groups.append(source_triangles)
        if not low_tri_groups:
            return ([], [])
        offsets = cage.build_group_coverage_offsets(
            low_tri_groups,
            high_source_data,
            dilation_iterations=2,
            high_object_names=high_object_names,
            match_by_isolation=isolate,
            high_surface_index=cage.get_or_build_high_surface_index(high_objs, depsgraph),
        )
        triangles: list[cage.TriangleData] = []
        corner_offsets: list[tuple[float, float, float]] = []
        for source_triangles in low_tri_groups:
            for triangle in source_triangles:
                keys = [
                    cage._source_position_group_key(triangle.object_name, corner.source_position)
                    for corner in triangle.corners
                ]
                triangles.append(triangle)
                corner_offsets.append(tuple(float(offsets.get(key, 0.0)) for key in keys))
        return (triangles, corner_offsets)

    if fit_key is None:
        return _build()
    result = cage.get_or_build_auto_cage_fitted(fit_key, _build)
    if not result or len(result) != 2:
        return [], []
    return result[0], result[1]


def _capture_cage_check_surface(context, group):
    """Return ``(triangles, slot_indices, signed, corner_offsets)`` for the cage-coverage shell.

    - Distance → the inflated low shell; coverage compares each high vertex's required offset
      against the per-slot cage offset (``signed=False``, ``corner_offsets=None``).
    - Automatic → the LOW source surface plus the fitted per-vertex cage distance at each corner;
      coverage is the bake-accurate ``required_reach - offset`` (``signed=False`` but
      ``corner_offsets`` present). This matches how the bake actually casts rays, so a fully-fitted
      cage reads 100% covered even where the cage mesh self-intersects.
    - Custom → the custom cage surface; coverage is the *signed* distance of each high vertex to it
      (negative = inside/covered), driving the same shader with ``slotOffset = 0`` (``signed=True``).
    """
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    depsgraph = context.evaluated_depsgraph_get() if hasattr(context, "evaluated_depsgraph_get") else None
    if depsgraph is None:
        return [], [], cage_mode in ("AUTOMATIC", "CUSTOM"), None
    if cage_mode == "CUSTOM":
        custom = getattr(group, "custom_cage", None)
        if custom is None or getattr(custom, "type", None) != "MESH":
            return [], [], True, None
        triangles = cage.capture_object_triangles(custom, depsgraph)
        return triangles, [0] * len(triangles), True, None
    if cage_mode == "AUTOMATIC":
        triangles, corner_offsets = _capture_auto_cage_offset_surface(context, group, depsgraph)
        return triangles, [0] * len(triangles), False, corner_offsets
    surface = _capture_distance_low_surface(context, group)
    return surface.triangles, surface.slot_indices, False, None


def _distance_slot_offsets(group) -> tuple[float, ...]:
    if str(getattr(group, "cage_mode", "") or "") in ("AUTOMATIC", "CUSTOM"):
        # Signed-distance coverage: one shell, compared against 0.
        return tuple(0.0 for _ in range(_DISTANCE_CHECK_MAX_SLOT_OFFSETS))
    offsets: list[float] = []
    group_offset = max(0.0, float(getattr(group, "cage_offset", 0.0) or 0.0))
    for slot in _iter_unique_role_slots(group, "low_meshes"):
        obj = getattr(slot, "object_ref", None)
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        offsets.append(max(0.0, group_offset + _slot_offset_delta(slot)))
        if len(offsets) >= _DISTANCE_CHECK_MAX_SLOT_OFFSETS:
            break
    if not offsets:
        offsets.append(group_offset)
    while len(offsets) < _DISTANCE_CHECK_MAX_SLOT_OFFSETS:
        offsets.append(offsets[-1])
    return tuple(offsets)


def _distance_slot_offset_count(group) -> int:
    if str(getattr(group, "cage_mode", "") or "") in ("AUTOMATIC", "CUSTOM"):
        return 1
    return max(
        1,
        min(
            _DISTANCE_CHECK_MAX_SLOT_OFFSETS,
            sum(
                1
                for slot in _iter_unique_role_slots(group, "low_meshes")
                if getattr(slot, "object_ref", None) is not None
                and getattr(getattr(slot, "object_ref", None), "type", None) == "MESH"
            ),
        ),
    )


def _distance_check_prepare(context, group, obj) -> dict | None:
    """Capture the low surface, its BVH and the high-mesh vertex arrays needed to
    compute a distance-check batch. Returns a dict of (mostly numpy) inputs, or
    None on failure (marking the high-mesh failure signature so the draw path
    stops re-requesting the build)."""
    import numpy as np

    global _DISTANCE_CHECK_SOURCE_CACHE
    signature = _distance_check_signature(group, obj)
    pointer = _mesh_signature(obj)[0]
    distance_mode = str(getattr(group, "cage_mode", "")) == "DISTANCE"
    source_key = signature[:-1]
    if distance_mode and _DISTANCE_CHECK_SOURCE_CACHE is not None:
        cached_key, cached_source = _DISTANCE_CHECK_SOURCE_CACHE
        if cached_key == source_key:
            return _prepare_displayed_distance_shell(dict(cached_source, signature=signature), group)

    shell_triangles, shell_slot_indices, signed, shell_corner_offsets = _capture_cage_check_surface(context, group)
    low_bvh = cage.build_triangle_bvh(shell_triangles)
    if not shell_triangles or low_bvh is None:
        _HIGH_MESH_FAILURE_SIGNATURES[("distance", pointer)] = signature
        return None

    depsgraph = context.evaluated_depsgraph_get() if hasattr(context, "evaluated_depsgraph_get") else None
    obj_eval = obj.evaluated_get(depsgraph) if depsgraph is not None and hasattr(obj, "evaluated_get") else obj
    mesh = obj_eval.to_mesh() if hasattr(obj_eval, "to_mesh") else getattr(obj_eval, "data", None)
    temporary_mesh = hasattr(obj_eval, "to_mesh")
    if mesh is None:
        _HIGH_MESH_FAILURE_SIGNATURES[("distance", pointer)] = signature
        return None
    try:
        transform = getattr(mesh, "transform", None)
        object_matrix = getattr(obj_eval, "matrix_world", None)
        if object_matrix is None:
            object_matrix = getattr(obj, "matrix_world", None)
        if callable(transform) and object_matrix is not None:
            transform(object_matrix)
            update = getattr(mesh, "update", None)
            if callable(update):
                update()
        calc_loop_triangles = getattr(mesh, "calc_loop_triangles", None)
        if callable(calc_loop_triangles):
            calc_loop_triangles()
        vertices = getattr(mesh, "vertices", None)
        loop_triangles = getattr(mesh, "loop_triangles", None)
        if vertices is None or loop_triangles is None or len(vertices) == 0 or len(loop_triangles) == 0:
            _HIGH_MESH_FAILURE_SIGNATURES[("distance", pointer)] = signature
            return None
        vertex_count = len(vertices)
        triangle_count = len(loop_triangles)
        positions = _foreach_get_float_rows(vertices, "co", vertex_count, 3)
        normals = _foreach_get_float_rows(vertices, "normal", vertex_count, 3)
        triangle_loop_indices = _foreach_get_int_rows(loop_triangles, "vertices", triangle_count, 3)
        if positions is None or normals is None or triangle_loop_indices is None:
            _HIGH_MESH_FAILURE_SIGNATURES[("distance", pointer)] = signature
            return None
    finally:
        if temporary_mesh and hasattr(obj_eval, "to_mesh_clear"):
            obj_eval.to_mesh_clear()

    # Flatten the (small) low surface into per-triangle corner arrays so the
    # per-high-vertex projection math can run vectorised in numpy.
    triangles = shell_triangles
    triangle_slot_indices = shell_slot_indices
    low_triangle_count = len(triangles)
    corner_positions = np.empty((low_triangle_count, 3, 3), dtype=np.float64)
    corner_normals = np.empty((low_triangle_count, 3, 3), dtype=np.float64)
    # A reflected object's winding reverses in world space, but its interior
    # does not. Preserve the source mesh orientation for enclosure signs.
    orientations = {}
    for triangle in triangles:
        if triangle.object_name not in orientations:
            source_obj = bpy.data.objects.get(triangle.object_name)
            mirrored = source_obj is not None and source_obj.matrix_world.determinant() < 0.0
            orientations[triangle.object_name] = -1.0 if mirrored else 1.0
    face_orientation = np.asarray([orientations[t.object_name] for t in triangles])
    slot_lookup = np.zeros(low_triangle_count, dtype=np.float64)
    has_corner_offsets = bool(shell_corner_offsets) and len(shell_corner_offsets) == low_triangle_count
    corner_offsets = np.zeros((low_triangle_count, 3), dtype=np.float64) if has_corner_offsets else None
    for triangle_index, triangle in enumerate(triangles):
        corners = triangle.corners
        for corner_index in range(3):
            corner = corners[corner_index]
            position = corner.position
            normal = corner.normal
            corner_positions[triangle_index, corner_index] = (position[0], position[1], position[2])
            corner_normals[triangle_index, corner_index] = (normal[0], normal[1], normal[2])
        if triangle_index < len(triangle_slot_indices):
            slot_lookup[triangle_index] = float(triangle_slot_indices[triangle_index])
        if corner_offsets is not None:
            offsets_row = shell_corner_offsets[triangle_index]
            corner_offsets[triangle_index] = (float(offsets_row[0]), float(offsets_row[1]), float(offsets_row[2]))

    prep = {
        "signature": signature,
        "pointer": pointer,
        "positions": positions,
        "normals": normals,
        "triangle_indices": triangle_loop_indices,
        "vertex_count": int(vertex_count),
        "low_bvh": low_bvh,
        "corner_positions": corner_positions,
        "corner_normals": corner_normals,
        "face_orientation": face_orientation,
        "slot_lookup": slot_lookup,
        "corner_offsets": corner_offsets,
        "slot_count": len(tuple(_iter_low_objects(group))),
        "signed": bool(signed),
    }
    if distance_mode:
        if cage.auto_cage_uses_average_normals(group):
            # Straight on the corner arrays: the former numpy -> tolist -> subdivide ->
            # tolist -> asarray round trip built two Python row lists per corner (~20 GB
            # transient on a 1M-triangle low). Same float32 math and float64 result.
            subdivided_positions, subdivided_normals = cage.subdivide_offset_arrays(
                corner_positions.reshape(-1, 3).astype(np.float32),
                corner_normals.reshape(-1, 3).astype(np.float32),
                iterations=2,
            )
            prep["corner_positions"] = (
                np.frombuffer(subdivided_positions, dtype=np.float32).astype(np.float64).reshape(-1, 3, 3)
                if len(subdivided_positions)
                else np.empty((0, 3, 3), dtype=np.float64)
            )
            prep["corner_normals"] = (
                np.frombuffer(subdivided_normals, dtype=np.float32).astype(np.float64).reshape(-1, 3, 3)
                if len(subdivided_normals)
                else np.empty((0, 3, 3), dtype=np.float64)
            )
            del subdivided_positions, subdivided_normals
            prep["slot_lookup"] = np.repeat(slot_lookup, 16)
            prep["face_orientation"] = np.repeat(face_orientation, 16)
        # The original low BVH is not needed by signed-shell queries.
        prep.pop("low_bvh", None)
        size = sum(v.nbytes for v in prep.values() if isinstance(v, np.ndarray))
        _DISTANCE_CHECK_SOURCE_CACHE = (source_key, prep) if size <= _DISTANCE_CHECK_SOURCE_CACHE_BYTES else None
        return _prepare_displayed_distance_shell(dict(prep), group)
    if signed:
        _prepare_shell_signs(prep)
    return prep


def _prepare_shell_signs(prep):
    from .overlay_cage_coverage import shell_pseudonormals
    prep["face_signs"], prep["vertex_signs"], prep["edge_signs"] = shell_pseudonormals(
        prep["corner_positions"], prep["slot_lookup"], prep.get("face_orientation", 1.0))


def _prepare_displayed_distance_shell(prep, group):
    import numpy as np
    from mathutils.bvhtree import BVHTree

    slots = prep["slot_lookup"].astype(np.intp)
    offsets = np.asarray(_distance_slot_offsets(group))[np.minimum(slots, _DISTANCE_CHECK_MAX_SLOT_OFFSETS - 1)]
    corners = prep["corner_positions"] + prep["corner_normals"] * offsets[:, None, None]
    prep["corner_positions"] = corners
    prep["shell_offsets"] = offsets
    prep["signed"] = True
    prep["low_bvh"] = BVHTree.FromPolygons(corners.reshape(-1, 3),
        np.arange(corners.size // 3).reshape(-1, 3), all_triangles=True)
    _prepare_shell_signs(prep)
    return prep


def _distance_check_compute_chunk(prep: dict, start: int, end: int):
    """Compute the per-vertex required cage offset and slot index for vertices
    [start, end) of the prepared high mesh. Returns (required, slot) as numpy
    float32 arrays. This mirrors _required_distance_offset exactly but batches
    the barycentric / projection math in numpy instead of a Python per-vertex
    loop, which is where the multi-second freeze used to come from."""
    import numpy as np
    from mathutils import Vector

    positions = prep["positions"]
    find_nearest = prep["low_bvh"].find_nearest
    sub = positions[start:end]
    count = int(end - start)

    # Nearest surface point + face index per vertex. BVH.find_nearest has no
    # batch API, so this stays a Python loop — but only over one chunk.
    locations = np.empty((count, 3), dtype=np.float64)
    face_indices = np.empty(count, dtype=np.int64)
    for local_index in range(count):
        row = sub[local_index]
        location, _normal, face_index, _distance = find_nearest(
            Vector((float(row[0]), float(row[1]), float(row[2])))
        )
        if location is None:
            face_indices[local_index] = -1
            locations[local_index, 0] = row[0]
            locations[local_index, 1] = row[1]
            locations[local_index, 2] = row[2]
        else:
            locations[local_index, 0] = location[0]
            locations[local_index, 1] = location[1]
            locations[local_index, 2] = location[2]
            face_indices[local_index] = int(face_index) if face_index is not None else -1

    corner_positions = prep["corner_positions"]
    corner_normals = prep["corner_normals"]
    slot_lookup = prep["slot_lookup"]

    valid = face_indices >= 0
    gather = np.where(valid, face_indices, 0)
    corner_a = corner_positions[gather, 0]
    corner_b = corner_positions[gather, 1]
    corner_c = corner_positions[gather, 2]
    normal_a = corner_normals[gather, 0]
    normal_b = corner_normals[gather, 1]
    normal_c = corner_normals[gather, 2]

    edge_0 = corner_b - corner_a
    edge_1 = corner_c - corner_a
    edge_2 = locations - corner_a
    d00 = (edge_0 * edge_0).sum(1)
    d01 = (edge_0 * edge_1).sum(1)
    d11 = (edge_1 * edge_1).sum(1)
    d20 = (edge_2 * edge_0).sum(1)
    d21 = (edge_2 * edge_1).sum(1)
    denom = d00 * d11 - d01 * d01
    denom_ok = np.abs(denom) > 1.0e-20
    safe_denom = np.where(denom_ok, denom, 1.0)
    weight_v = np.where(denom_ok, (d11 * d20 - d01 * d21) / safe_denom, 0.0)
    weight_w = np.where(denom_ok, (d00 * d21 - d01 * d20) / safe_denom, 0.0)
    weight_u = np.where(denom_ok, 1.0 - weight_v - weight_w, 1.0)

    projected = weight_u[:, None] * normal_a + weight_v[:, None] * normal_b + weight_w[:, None] * normal_c
    projected_len_sq = (projected * projected).sum(1)

    # Degenerate corner normals fall back to the (unit) face normal, matching
    # _nearest_low_projection / _triangle_face_normal.
    face_normal = np.cross(edge_0, edge_1)
    face_len = np.sqrt((face_normal * face_normal).sum(1))
    face_len_ok = face_len > 1.0e-6
    face_unit = np.where(face_len_ok[:, None], face_normal / np.where(face_len_ok[:, None], face_len[:, None], 1.0), face_normal)
    degenerate = projected_len_sq <= 1.0e-12
    projected = np.where(degenerate[:, None], face_unit, projected)

    scale = np.sqrt((projected * projected).sum(1))
    scale_ok = scale > 1.0e-12
    direction = np.where(scale_ok[:, None], projected / np.where(scale_ok[:, None], scale[:, None], 1.0), 0.0)
    point = sub.astype(np.float64)

    if prep.get("signed"):
        from .overlay_cage_coverage import signed_shell_distance
        signed_distance = signed_shell_distance(point - locations,
            np.column_stack((weight_u, weight_v, weight_w)), gather,
            prep["face_signs"], prep["vertex_signs"], prep["edge_signs"])
        offsets = prep.get("shell_offsets")
        if offsets is not None:
            signed_distance += offsets[gather]
        required = np.where(valid, signed_distance, 1.0e6).astype(np.float32)
        slot = np.where(valid, slot_lookup[gather], 0.0).astype(np.float32)
        return required, slot

    along_normal = ((point - locations) * direction).sum(1)
    required = np.maximum(0.0, along_normal / np.where(scale_ok, scale, 1.0))
    required = np.where(scale_ok & valid, required, 1.0e6)

    corner_offsets = prep.get("corner_offsets")
    if corner_offsets is not None:
        # Automatic cage: coverage is bake-accurate — the cage reaches `offset` along the low
        # normal, so a high vertex is covered iff its required reach <= the per-vertex offset
        # (barycentric-interpolated across the nearest low triangle). Emitting `required - offset`
        # against a zero slot makes the shader's `requiredOffset <= slotOffset` test read directly:
        # <=0 covered (blue), >0 a genuine ray miss (red).
        gathered_offsets = corner_offsets[gather]
        interp_offset = (
            weight_u * gathered_offsets[:, 0]
            + weight_v * gathered_offsets[:, 1]
            + weight_w * gathered_offsets[:, 2]
        )
        coverage = np.where(valid, required - interp_offset, 1.0e6)
        slot = np.zeros(count, dtype=np.float32)
        return coverage.astype(np.float32), slot
    # DISTANCE reach is measured along the UNIT normal, with no division by the
    # interpolated normal's length. The backend normalises the interpolated low normal
    # before it builds the ray (pick_safe_direction_vec3): origin = pos + n * cage_offset,
    # so the bake's cage is the round surface that reaches `cage_offset` everywhere, not the
    # flat facets between displaced corners. Dividing by that length (< 1 anywhere between
    # vertices) inflated the requirement and painted covered high poly red, by 8% where
    # neighbouring vertex normals are 45 degrees apart and 40% at 90 degrees, i.e. worst
    # on exactly the low-poly meshes this overlay exists for. The Automatic branch above
    # keeps the division: its cage IS a mesh of displaced corners.
    required = np.where(scale_ok & valid, np.maximum(0.0, along_normal), 1.0e6)
    slot = np.where(valid, slot_lookup[gather], 0.0)
    slot = np.clip(slot, 0.0, float(_DISTANCE_CHECK_MAX_SLOT_OFFSETS - 1))
    return required.astype(np.float32), slot.astype(np.float32)


def _distance_check_make_batch(group, obj, prep: dict, required, slot) -> _DistanceCheckBatch | None:
    """Build and cache the GPU batch from prepared inputs + computed per-vertex
    required offsets / slot indices."""
    signature = prep["signature"]
    pointer = prep["pointer"]
    vertex_count = int(prep["vertex_count"])
    fmt = gpu.types.GPUVertFormat()
    fmt.attr_add(id="position", comp_type="F32", len=3, fetch_mode="FLOAT")
    fmt.attr_add(id="normal", comp_type="F32", len=3, fetch_mode="FLOAT")
    fmt.attr_add(id="requiredOffsetIn", comp_type="F32", len=1, fetch_mode="FLOAT")
    fmt.attr_add(id="slotIndexIn", comp_type="F32", len=1, fetch_mode="FLOAT")
    try:
        vertex_buffer = gpu.types.GPUVertBuf(fmt, vertex_count)
        vertex_buffer.attr_fill("position", prep["positions"])
        vertex_buffer.attr_fill("normal", prep["normals"])
        vertex_buffer.attr_fill("requiredOffsetIn", required)
        vertex_buffer.attr_fill("slotIndexIn", slot)
        index_buffer = gpu.types.GPUIndexBuf(type="TRIS", seq=prep["triangle_indices"])
        batch = gpu.types.GPUBatch(type="TRIS", buf=vertex_buffer, elem=index_buffer)
    except Exception:
        _HIGH_MESH_FAILURE_SIGNATURES[("distance", pointer)] = signature
        _log_error_once("[Fyr Baker] Cage Check overlay failed to create a distance-check GPU batch:\n" + traceback.format_exc())
        return None
    cached = _DistanceCheckBatch(
        signature=signature,
        batch=batch,
        object_ref=obj,
        vertex_count=vertex_count,
        required_min=float(required.min()) if vertex_count else 0.0,
        required_max=float(required.max()) if vertex_count else 0.0,
        slot_count=int(prep["slot_count"]),
    )
    # Keyed by (mesh, signature) — NOT mesh alone — so flipping the cage mode
    # back and forth reuses each mode's finished result instead of recomputing
    # the multi-second per-vertex check on every switch (the signature folds in
    # the cage mode/offsets, so each mode keeps its own entry). LRU-evict the
    # oldest entry instead of dropping the whole cache.
    for old_key in tuple(_DISTANCE_CHECK_BATCH_CACHE):
        if old_key[0] == pointer and old_key[1][:-1] == signature[:-1]:
            _DISTANCE_CHECK_BATCH_CACHE.pop(old_key, None)
    while len(_DISTANCE_CHECK_BATCH_CACHE) >= 16:
        _DISTANCE_CHECK_BATCH_CACHE.pop(next(iter(_DISTANCE_CHECK_BATCH_CACHE)), None)
    _HIGH_MESH_FAILURE_SIGNATURES.pop(("distance", pointer), None)
    _DISTANCE_CHECK_BATCH_CACHE[(pointer, signature, _DISTANCE_CHECK_MATH_VERSION)] = cached
    return cached


_DISTANCE_CHECK_COMPUTE_SOURCE = """
vec3 closest_point_on_triangle(vec3 p, vec3 a, vec3 b, vec3 c)
{
  vec3 ab = b - a; vec3 ac = c - a; vec3 ap = p - a;
  float d1 = dot(ab, ap); float d2 = dot(ac, ap);
  if (d1 <= 0.0 && d2 <= 0.0) return a;
  vec3 bp = p - b; float d3 = dot(ab, bp); float d4 = dot(ac, bp);
  if (d3 >= 0.0 && d4 <= d3) return b;
  float vc = d1 * d4 - d3 * d2;
  if (vc <= 0.0 && d1 >= 0.0 && d3 <= 0.0) { float v = d1 / (d1 - d3); return a + v * ab; }
  vec3 cp = p - c; float d5 = dot(ab, cp); float d6 = dot(ac, cp);
  if (d6 >= 0.0 && d5 <= d6) return c;
  float vb = d5 * d2 - d1 * d6;
  if (vb <= 0.0 && d2 >= 0.0 && d6 <= 0.0) { float w = d2 / (d2 - d6); return a + w * ac; }
  float va = d3 * d6 - d5 * d4;
  if (va <= 0.0 && (d4 - d3) >= 0.0 && (d5 - d6) >= 0.0) { float w = (d4 - d3) / ((d4 - d3) + (d5 - d6)); return b + w * (c - b); }
  float denom = 1.0 / (va + vb + vc); float v = vb * denom; float w = vc * denom;
  return a + ab * v + ac * w;
}

void main()
{
  ivec2 texel = ivec2(gl_GlobalInvocationID.xy);
  if (texel.x >= dims.x || texel.y >= dims.y) return;
  int index = texel.y * dims.x + texel.x;
  if (index >= count) return;
  vec3 point = texelFetch(highTex, texel, 0).xyz;
  float best_distance = 1.0e30;
  vec3 best_location = point; int best_triangle = -1;
  vec3 na, nb, nc, va3, vb3, vc3;
  for (int t = 0; t < triCount; t++) {
    vec3 a = texelFetch(triTex, ivec2(0, t), 0).xyz;
    vec3 b = texelFetch(triTex, ivec2(1, t), 0).xyz;
    vec3 c = texelFetch(triTex, ivec2(2, t), 0).xyz;
    vec3 location = closest_point_on_triangle(point, a, b, c);
    vec3 delta = point - location; float distance_sq = dot(delta, delta);
    if (distance_sq < best_distance) {
      best_distance = distance_sq; best_location = location; best_triangle = t;
      va3 = a; vb3 = b; vc3 = c;
      na = texelFetch(triTex, ivec2(3, t), 0).xyz;
      nb = texelFetch(triTex, ivec2(4, t), 0).xyz;
      nc = texelFetch(triTex, ivec2(5, t), 0).xyz;
    }
  }
  float required = 1.0e6; float slot = 0.0;
  if (best_triangle >= 0) {
    vec3 edge0 = vb3 - va3; vec3 edge1 = vc3 - va3; vec3 edge2 = best_location - va3;
    float d00 = dot(edge0, edge0); float d01 = dot(edge0, edge1); float d11 = dot(edge1, edge1);
    float d20 = dot(edge2, edge0); float d21 = dot(edge2, edge1);
    float denom = d00 * d11 - d01 * d01;
    float weight_v = 0.0; float weight_w = 0.0; float weight_u = 1.0;
    if (abs(denom) > 1.0e-20) {
      weight_v = (d11 * d20 - d01 * d21) / denom;
      weight_w = (d00 * d21 - d01 * d20) / denom;
      weight_u = 1.0 - weight_v - weight_w;
    }
    vec3 projected = weight_u * na + weight_v * nb + weight_w * nc;
    if (dot(projected, projected) <= 1.0e-12) {
      vec3 face_normal = cross(edge0, edge1); float face_len = length(face_normal);
      projected = (face_len > 1.0e-6) ? face_normal / face_len : face_normal;
    }
    float scale = length(projected);
    float along_normal = 0.0;
    if (scale > 1.0e-12) {
      vec3 direction = projected / scale;
      along_normal = dot(point - best_location, direction);
      required = max(0.0, along_normal / scale);
    }
    if (signedShell != 0) {
      vec3 sign_normal = texelFetch(triTex, ivec2(8, best_triangle), 0).xyz;
      if (weight_w <= 1.0e-5) sign_normal = texelFetch(triTex, ivec2(12, best_triangle), 0).xyz;
      if (weight_u <= 1.0e-5) sign_normal = texelFetch(triTex, ivec2(13, best_triangle), 0).xyz;
      if (weight_v <= 1.0e-5) sign_normal = texelFetch(triTex, ivec2(14, best_triangle), 0).xyz;
      int near_count = int(weight_u <= 1.0e-5) + int(weight_v <= 1.0e-5) + int(weight_w <= 1.0e-5);
      if (near_count >= 2) {
        int corner = weight_u >= weight_v && weight_u >= weight_w ? 0 : (weight_v >= weight_w ? 1 : 2);
        sign_normal = texelFetch(triTex, ivec2(9 + corner, best_triangle), 0).xyz;
      }
      vec3 delta = point - best_location;
      required = (dot(delta, sign_normal) <= 0.0 ? -1.0 : 1.0) * sqrt(best_distance);
      required += texelFetch(triTex, ivec2(6, best_triangle), 0).y;
      slot = texelFetch(triTex, ivec2(6, best_triangle), 0).x;
      imageStore(reqOut, texel, vec4(required));
      imageStore(slotOut, texel, vec4(slot));
      return;
    }
    slot = texelFetch(triTex, ivec2(6, best_triangle), 0).x;
    if (useCornerOffsets != 0) {
      // Automatic cage: the cage reaches its per-vertex offset along the low
      // normal, so a high vertex is covered iff its reach <= the barycentric-
      // interpolated per-corner offset. Emit (reach - offset) against slot 0 so
      // the draw shader's `requiredOffset <= slotOffset(0)` test reads directly —
      // identical to the CPU chunk path's Automatic branch.
      vec3 corner_offsets = texelFetch(triTex, ivec2(7, best_triangle), 0).xyz;
      float interp_offset = weight_u * corner_offsets.x
                          + weight_v * corner_offsets.y
                          + weight_w * corner_offsets.z;
      required = required - interp_offset;
      slot = 0.0;
    } else {
      if (scale > 1.0e-12) required = max(0.0, along_normal);
    }
  }
  imageStore(reqOut, texel, vec4(required));
  imageStore(slotOut, texel, vec4(slot));
}
"""


def _get_distance_check_compute_shader():
    """Compile (once) the compute shader that brute-forces the low surface for
    every high vertex. Returns None if compute shaders are unavailable on this
    GPU/backend, in which case callers fall back to the CPU path."""
    global _DISTANCE_CHECK_COMPUTE_SHADER, _DISTANCE_CHECK_COMPUTE_SUPPORTED
    if _DISTANCE_CHECK_COMPUTE_SUPPORTED is False:
        return None
    if _DISTANCE_CHECK_COMPUTE_SHADER is not None:
        return _DISTANCE_CHECK_COMPUTE_SHADER
    try:
        if not hasattr(gpu, "compute") or not hasattr(gpu.compute, "dispatch"):
            raise RuntimeError("gpu.compute.dispatch unavailable")
        info = gpu.types.GPUShaderCreateInfo()
        info.local_group_size(16, 16)
        info.sampler(0, "FLOAT_2D", "highTex")
        info.sampler(1, "FLOAT_2D", "triTex")
        # Two single-channel outputs, NOT one RGBA: GPUTexture.read() interleaves
        # RGBA channels in a width-dependent way that silently corrupts the
        # readback at large widths, whereas the R32F read layout is stable.
        info.image(0, "R32F", "FLOAT_2D", "reqOut", qualifiers={"WRITE"})
        info.image(1, "R32F", "FLOAT_2D", "slotOut", qualifiers={"WRITE"})
        info.push_constant("IVEC2", "dims")
        info.push_constant("INT", "count")
        info.push_constant("INT", "triCount")
        # 1 = Automatic cage: subtract the barycentric-interpolated per-corner cage
        # offset (packed in triTex texel 7) from the reach so the GPU path also
        # produces Automatic coverage, instead of dropping it to the slow CPU chunker.
        info.push_constant("INT", "useCornerOffsets")
        info.push_constant("INT", "signedShell")
        info.compute_source(_DISTANCE_CHECK_COMPUTE_SOURCE)
        shader = gpu.shader.create_from_info(info)
        del info
        _DISTANCE_CHECK_COMPUTE_SHADER = shader
        _DISTANCE_CHECK_COMPUTE_SUPPORTED = True
        return shader
    except Exception:
        _DISTANCE_CHECK_COMPUTE_SUPPORTED = False
        _log_error_once("[Fyr Baker] Cage Check overlay compute shader unavailable; using CPU path:\n" + traceback.format_exc())
        return None


def _compute_distance_check_gpu(prep: dict):
    """GPU equivalent of _distance_check_compute_chunk over the whole mesh: packs
    the high vertices and (small) low surface into textures, brute-forces the
    nearest-surface projection in a compute shader, and reads back the per-vertex
    required offset + slot. Returns (required, slot) float32 arrays, or None to
    signal the caller to fall back to the CPU path."""
    shader = _get_distance_check_compute_shader()
    if shader is None:
        return None
    import numpy as np

    positions = prep["positions"]
    corner_positions = prep["corner_positions"]
    corner_normals = prep["corner_normals"]
    slot_lookup = prep["slot_lookup"]
    vertex_count = int(prep["vertex_count"])
    triangle_count = int(corner_positions.shape[0])
    if vertex_count <= 0 or triangle_count <= 0:
        return None

    width = _DISTANCE_CHECK_COMPUTE_TEX_WIDTH
    height = (vertex_count + width - 1) // width
    texels_per_triangle = 15 if prep.get("signed") else 8
    max_tex = _DISTANCE_CHECK_COMPUTE_MAX_TEX
    # Texture dimensions are hardware-bounded; hand very large meshes / low
    # surfaces to the CPU fallback rather than risk an allocation failure.
    if height > max_tex or triangle_count > max_tex:
        return None
    try:
        high_buffer = np.zeros((height * width, 4), dtype=np.float32)
        high_buffer[:vertex_count, :3] = positions[:, :3]
        high_texture = gpu.types.GPUTexture(
            (width, height),
            format="RGBA32F",
            data=gpu.types.Buffer("FLOAT", height * width * 4, high_buffer.reshape(-1)),
        )
        triangle_buffer = np.zeros((triangle_count * texels_per_triangle, 4), dtype=np.float32)
        triangle_rows = np.arange(triangle_count) * texels_per_triangle
        corner_positions_f32 = corner_positions.astype(np.float32)
        corner_normals_f32 = corner_normals.astype(np.float32)
        for corner_index in range(3):
            triangle_buffer[triangle_rows + corner_index, :3] = corner_positions_f32[:, corner_index, :]
            triangle_buffer[triangle_rows + 3 + corner_index, :3] = corner_normals_f32[:, corner_index, :]
        triangle_buffer[triangle_rows + 6, 0] = slot_lookup.astype(np.float32)
        if prep.get("signed"):
            triangle_buffer[triangle_rows + 8, :3] = prep["face_signs"]
            for corner in range(3):
                triangle_buffer[triangle_rows + 9 + corner, :3] = prep["vertex_signs"][:, corner]
                triangle_buffer[triangle_rows + 12 + corner, :3] = prep["edge_signs"][:, corner]
            if prep.get("shell_offsets") is not None:
                triangle_buffer[triangle_rows + 6, 1] = prep["shell_offsets"]
        # Automatic cage: pack the 3 per-corner offsets into the (otherwise unused)
        # texel 7 so the shader can subtract the interpolated cage offset per vertex.
        corner_offsets = prep.get("corner_offsets")
        use_corner_offsets = corner_offsets is not None
        if use_corner_offsets:
            triangle_buffer[triangle_rows + 7, :3] = np.asarray(corner_offsets, dtype=np.float32)[:, :3]
        triangle_texture = gpu.types.GPUTexture(
            (texels_per_triangle, triangle_count),
            format="RGBA32F",
            data=gpu.types.Buffer("FLOAT", triangle_count * texels_per_triangle * 4, triangle_buffer.reshape(-1)),
        )
        required_texture = gpu.types.GPUTexture((width, height), format="R32F")
        slot_texture = gpu.types.GPUTexture((width, height), format="R32F")
        shader.bind()
        shader.image("reqOut", required_texture)
        shader.image("slotOut", slot_texture)
        shader.uniform_sampler("highTex", high_texture)
        shader.uniform_sampler("triTex", triangle_texture)
        shader.uniform_int("dims", (width, height))
        shader.uniform_int("count", vertex_count)
        shader.uniform_int("triCount", triangle_count)
        shader.uniform_int("useCornerOffsets", 1 if use_corner_offsets else 0)
        shader.uniform_int("signedShell", 1 if prep.get("signed") else 0)
        gpu.compute.dispatch(shader, (width + 15) // 16, (height + 15) // 16, 1)
        required_raw = np.asarray(required_texture.read(), dtype=np.float32)  # (height, width)
        slot_raw = np.asarray(slot_texture.read(), dtype=np.float32)
    except Exception:
        _log_error_once("[Fyr Baker] Cage Check overlay GPU distance compute failed; using CPU path:\n" + traceback.format_exc())
        return None
    # read() returns data transposed relative to numpy's (H, W) view — recover
    # the vertex-linear order (texel i -> (i % W, i // W)) with a transpose.
    # read() is (height, width) row-major, the shader's texel order (y * width + x). A
    # transpose here sliced unwritten padding texels into the result once the mesh needed
    # more than one row (2026-10-27).
    required = np.ascontiguousarray(required_raw.reshape(-1)[:vertex_count]).astype(np.float32)
    slot = np.ascontiguousarray(slot_raw.reshape(-1)[:vertex_count]).astype(np.float32)
    np.clip(slot, 0.0, float(_DISTANCE_CHECK_MAX_SLOT_OFFSETS - 1), out=slot)
    return required, slot


_COVERAGE_NEAREST_COMPUTE_SOURCE = """
vec3 closest_point_on_triangle(vec3 p, vec3 a, vec3 b, vec3 c)
{
  vec3 ab = b - a; vec3 ac = c - a; vec3 ap = p - a;
  float d1 = dot(ab, ap); float d2 = dot(ac, ap);
  if (d1 <= 0.0 && d2 <= 0.0) return a;
  vec3 bp = p - b; float d3 = dot(ab, bp); float d4 = dot(ac, bp);
  if (d3 >= 0.0 && d4 <= d3) return b;
  float vc = d1 * d4 - d3 * d2;
  if (vc <= 0.0 && d1 >= 0.0 && d3 <= 0.0) { float v = d1 / (d1 - d3); return a + v * ab; }
  vec3 cp = p - c; float d5 = dot(ab, cp); float d6 = dot(ac, cp);
  if (d6 >= 0.0 && d5 <= d6) return c;
  float vb = d5 * d2 - d1 * d6;
  if (vb <= 0.0 && d2 >= 0.0 && d6 <= 0.0) { float w = d2 / (d2 - d6); return a + w * ac; }
  float va = d3 * d6 - d5 * d4;
  if (va <= 0.0 && (d4 - d3) >= 0.0 && (d5 - d6) >= 0.0) { float w = (d4 - d3) / ((d4 - d3) + (d5 - d6)); return b + w * (c - b); }
  float denom = 1.0 / (va + vb + vc); float v = vb * denom; float w = vc * denom;
  return a + ab * v + ac * w;
}

void main()
{
  ivec2 texel = ivec2(gl_GlobalInvocationID.xy);
  if (texel.x >= dims.x || texel.y >= dims.y) return;
  int index = texel.y * dims.x + texel.x;
  if (index >= count) return;
  vec3 point = texelFetch(highTex, texel, 0).xyz;
  float best_distance = 1.0e30;
  vec3 best_location = point; int best_triangle = -1;
  vec3 na, nb, nc, va3, vb3, vc3;
  for (int t = 0; t < triCount; t++) {
    vec3 a = texelFetch(triTex, ivec2(0 + 8 * (t & 255), t >> 8), 0).xyz;
    vec3 b = texelFetch(triTex, ivec2(1 + 8 * (t & 255), t >> 8), 0).xyz;
    vec3 c = texelFetch(triTex, ivec2(2 + 8 * (t & 255), t >> 8), 0).xyz;
    vec3 location = closest_point_on_triangle(point, a, b, c);
    vec3 delta = point - location; float distance_sq = dot(delta, delta);
    if (distance_sq < best_distance) {
      best_distance = distance_sq; best_location = location; best_triangle = t;
      va3 = a; vb3 = b; vc3 = c;
      na = texelFetch(triTex, ivec2(3 + 8 * (t & 255), t >> 8), 0).xyz;
      nb = texelFetch(triTex, ivec2(4 + 8 * (t & 255), t >> 8), 0).xyz;
      nc = texelFetch(triTex, ivec2(5 + 8 * (t & 255), t >> 8), 0).xyz;
    }
  }
  float required = 0.0;
  if (best_triangle >= 0) {
    vec3 edge0 = vb3 - va3; vec3 edge1 = vc3 - va3; vec3 edge2 = best_location - va3;
    float d00 = dot(edge0, edge0); float d01 = dot(edge0, edge1); float d11 = dot(edge1, edge1);
    float d20 = dot(edge2, edge0); float d21 = dot(edge2, edge1);
    float denom = d00 * d11 - d01 * d01;
    float weight_v = 0.0; float weight_w = 0.0; float weight_u = 1.0;
    if (abs(denom) > 1.0e-20) {
      weight_v = (d11 * d20 - d01 * d21) / denom;
      weight_w = (d00 * d21 - d01 * d20) / denom;
      weight_u = 1.0 - weight_v - weight_w;
    }
    vec3 projected = weight_u * na + weight_v * nb + weight_w * nc;
    // cage._COVERAGE_MIN_BLEND_SQ: corners disagreeing by >120 degrees use the face normal.
    if (dot(projected, projected) < 0.25) {
      vec3 face_normal = cross(edge0, edge1); float face_len = length(face_normal);
      projected = (face_len > 1.0e-6) ? face_normal / face_len : face_normal;
    }
    float scale = length(projected);
    if (scale > 1.0e-12) {
      vec3 direction = projected / scale;
      required = max(0.0, dot(point - best_location, direction) / scale);
    }
  }
  imageStore(reqOut, texel, vec4(required));
  imageStore(triOut, texel, vec4(float(best_triangle)));
}
"""


def _get_coverage_nearest_compute_shader():
    """Compile (once) the compute shader that, for every high vertex, brute-forces the
    nearest low-cage triangle and the bake-accurate projected-normal reach. Mirrors
    :data:`_DISTANCE_CHECK_COMPUTE_SOURCE` but emits the nearest triangle *index* (so the
    CPU can scatter the reach onto that face's low-vertex corners) instead of the slot.
    Returns None if compute shaders are unavailable on this GPU/backend."""
    global _COVERAGE_NEAREST_COMPUTE_SHADER, _COVERAGE_NEAREST_COMPUTE_SUPPORTED
    if _COVERAGE_NEAREST_COMPUTE_SUPPORTED is False:
        return None
    if _COVERAGE_NEAREST_COMPUTE_SHADER is not None:
        return _COVERAGE_NEAREST_COMPUTE_SHADER
    try:
        if not hasattr(gpu, "compute") or not hasattr(gpu.compute, "dispatch"):
            raise RuntimeError("gpu.compute.dispatch unavailable")
        info = gpu.types.GPUShaderCreateInfo()
        info.local_group_size(16, 16)
        info.sampler(0, "FLOAT_2D", "highTex")
        info.sampler(1, "FLOAT_2D", "triTex")
        info.image(0, "R32F", "FLOAT_2D", "reqOut", qualifiers={"WRITE"})
        info.image(1, "R32F", "FLOAT_2D", "triOut", qualifiers={"WRITE"})
        info.push_constant("IVEC2", "dims")
        info.push_constant("INT", "count")
        info.push_constant("INT", "triCount")
        info.compute_source(_COVERAGE_NEAREST_COMPUTE_SOURCE)
        shader = gpu.shader.create_from_info(info)
        del info
        _COVERAGE_NEAREST_COMPUTE_SHADER = shader
        _COVERAGE_NEAREST_COMPUTE_SUPPORTED = True
        return shader
    except Exception:
        _COVERAGE_NEAREST_COMPUTE_SUPPORTED = False
        _log_error_once("[Fyr Baker] Coverage-fit compute shader unavailable; using CPU path:\n" + traceback.format_exc())
        return None


#: Largest uploaded high-vertex texture a caller may keep between passes (VRAM bound).
_COVERAGE_HIGH_TEXTURE_CACHE_BYTES = 256 * 1024 * 1024


def compute_coverage_nearest_gpu(corner_positions, corner_normals, high_world, high_cache=None):
    """GPU nearest-low-triangle + projected reach for every high vertex.

    ``corner_positions``/``corner_normals`` are ``(triangle_count, 3, 3)`` float arrays of the
    low-cage source triangles; ``high_world`` is ``(N, 3)`` world-space high vertices. Returns
    ``(required, tri_index)`` as float32 ``(N,)`` and int32 ``(N,)`` arrays, where ``tri_index``
    is the nearest low triangle (``-1`` if none) and ``required`` is the bake-accurate reach
    computed IDENTICALLY to :func:`cage.build_coverage_offsets`' CPU block and the coverage
    overlay. Returns ``None`` to signal the caller to fall back to the CPU path.

    ``high_cache`` is an optional dict owned by a caller that runs this pass repeatedly over
    the SAME ``high_world`` (the Distance fit queue, one pass per group sharing a high): the
    uploaded high-vertex texture is kept in it, so the 16 bytes per vertex are padded and
    uploaded once. The caller drops the dict when ``high_world`` is no longer current.
    """
    shader = _get_coverage_nearest_compute_shader()
    if shader is None:
        return None
    import numpy as np

    corner_positions = np.ascontiguousarray(corner_positions, dtype=np.float32)
    corner_normals = np.ascontiguousarray(corner_normals, dtype=np.float32)
    high_world = np.ascontiguousarray(high_world, dtype=np.float32).reshape(-1, 3)
    vertex_count = int(high_world.shape[0])
    triangle_count = int(corner_positions.shape[0])
    if vertex_count <= 0 or triangle_count <= 0:
        return None

    width = _DISTANCE_CHECK_COMPUTE_TEX_WIDTH
    height = (vertex_count + width - 1) // width
    texels_per_triangle = 8
    # 256 triangles per texture row (the shader reads triangle t at row t >> 8): one
    # triangle per row capped the GPU path at 16384 low triangles, and a denser low
    # (a customer's 25.6 K-triangle receiver) fell back to the CPU loop, 3.5 s instead of
    # a fraction of one.
    triangles_per_row = 256
    triangle_rows_needed = (triangle_count + triangles_per_row - 1) // triangles_per_row
    max_tex = _DISTANCE_CHECK_COMPUTE_MAX_TEX
    if height > max_tex or triangle_rows_needed > max_tex:
        return None
    try:
        high_texture = None
        if high_cache is not None:
            cached_texture = high_cache.get("texture")
            if cached_texture is not None and high_cache.get("count") == vertex_count:
                high_texture = cached_texture
        if high_texture is None:
            high_buffer = np.zeros((height * width, 4), dtype=np.float32)
            high_buffer[:vertex_count, :3] = high_world[:, :3]
            high_texture = gpu.types.GPUTexture(
                (width, height),
                format="RGBA32F",
                data=gpu.types.Buffer("FLOAT", height * width * 4, high_buffer.reshape(-1)),
            )
            del high_buffer
            if high_cache is not None and height * width * 16 <= _COVERAGE_HIGH_TEXTURE_CACHE_BYTES:
                high_cache["texture"] = high_texture
                high_cache["count"] = vertex_count
        triangle_texels = triangle_rows_needed * triangles_per_row * texels_per_triangle
        triangle_buffer = np.zeros((triangle_texels, 4), dtype=np.float32)
        # Row-major: triangle t's texel c sits at (c + 8 * (t % 256), t // 256), which is
        # flat index t * 8 + c.
        triangle_rows = np.arange(triangle_count) * texels_per_triangle
        for corner_index in range(3):
            triangle_buffer[triangle_rows + corner_index, :3] = corner_positions[:, corner_index, :]
            triangle_buffer[triangle_rows + 3 + corner_index, :3] = corner_normals[:, corner_index, :]
        triangle_texture = gpu.types.GPUTexture(
            (triangles_per_row * texels_per_triangle, triangle_rows_needed),
            format="RGBA32F",
            data=gpu.types.Buffer("FLOAT", triangle_texels * 4, triangle_buffer.reshape(-1)),
        )
        required_texture = gpu.types.GPUTexture((width, height), format="R32F")
        tri_texture = gpu.types.GPUTexture((width, height), format="R32F")
        shader.bind()
        shader.image("reqOut", required_texture)
        shader.image("triOut", tri_texture)
        shader.uniform_sampler("highTex", high_texture)
        shader.uniform_sampler("triTex", triangle_texture)
        shader.uniform_int("dims", (width, height))
        shader.uniform_int("count", vertex_count)
        shader.uniform_int("triCount", triangle_count)
        gpu.compute.dispatch(shader, (width + 15) // 16, (height + 15) // 16, 1)
        required_raw = np.asarray(required_texture.read(), dtype=np.float32)
        tri_raw = np.asarray(tri_texture.read(), dtype=np.float32)
    except Exception:
        _log_error_once("[Fyr Baker] Coverage-fit GPU compute failed; using CPU path:\n" + traceback.format_exc())
        return None
    # Row-major like the shader's texel index. The old transpose sliced unwritten padding
    # texels into the result past one row: OpenGL left stale memory there (high vertex
    # coordinates read as reach), and the automatic cage shot spikes across the scene.
    required = np.ascontiguousarray(required_raw.reshape(-1)[:vertex_count]).astype(np.float32)
    tri_index = np.ascontiguousarray(tri_raw.reshape(-1)[:vertex_count])
    tri_index = np.rint(tri_index).astype(np.int32)
    return required, tri_index


def _build_distance_check_batch(context, group, obj) -> _DistanceCheckBatch | None:
    """Synchronous whole-mesh build (used by diagnostics). The draw path builds
    incrementally via the app timer instead — see _distance_check_build_timer."""
    signature = _distance_check_signature(group, obj)
    pointer = _mesh_signature(obj)[0]
    cached = _DISTANCE_CHECK_BATCH_CACHE.get((pointer, signature, _DISTANCE_CHECK_MATH_VERSION))
    if cached is not None:
        return cached
    if _HIGH_MESH_FAILURE_SIGNATURES.get(("distance", pointer)) == signature:
        return None

    prep = _distance_check_prepare(context, group, obj)
    if prep is None:
        return None
    try:
        gpu_result = _compute_distance_check_gpu(prep)
        if gpu_result is not None:
            required, slot = gpu_result
        else:
            required, slot = _distance_check_compute_chunk(prep, 0, prep["vertex_count"])
    except Exception:
        _HIGH_MESH_FAILURE_SIGNATURES[("distance", pointer)] = signature
        _log_error_once("[Fyr Baker] Cage Check overlay failed to build distance-check data:\n" + traceback.format_exc())
        return None
    return _distance_check_make_batch(group, obj, prep, required, slot)


def _cached_distance_check_batch(group, obj) -> _DistanceCheckBatch | None:
    signature = _distance_check_signature(group, obj)
    pointer = _mesh_signature(obj)[0]
    return _DISTANCE_CHECK_BATCH_CACHE.get((pointer, signature, _DISTANCE_CHECK_MATH_VERSION))


def _distance_check_build_key(group, obj) -> tuple:
    signature = _distance_check_signature(group, obj)
    return (_mesh_signature(obj)[0], signature)


def _start_distance_check_job(context, key, group, obj) -> _DistanceCheckBuildJob | None:
    signature = _distance_check_signature(group, obj)
    pointer = _mesh_signature(obj)[0]
    if _DISTANCE_CHECK_BATCH_CACHE.get((pointer, signature, _DISTANCE_CHECK_MATH_VERSION)) is not None:
        return None
    if _HIGH_MESH_FAILURE_SIGNATURES.get(("distance", pointer)) == signature:
        return None
    prep = _distance_check_prepare(context, group, obj)
    if prep is None:
        return None
    import numpy as np

    vertex_count = int(prep["vertex_count"])
    return _DistanceCheckBuildJob(
        key=key,
        group=group,
        obj=obj,
        prep=prep,
        required=np.empty(vertex_count, dtype=np.float32),
        slot=np.empty(vertex_count, dtype=np.float32),
        vertex_count=vertex_count,
    )


def _collection_lookup_by_name(collection, name: str):
    """Name lookup that works on both an RNA collection and a plain list."""
    if collection is None or not name:
        return None
    getter = getattr(collection, "get", None)
    if callable(getter):
        try:
            found = getter(name)
        except Exception:
            found = None
        if found is not None:
            return found
    try:
        for item in collection:
            if str(getattr(item, "name", "") or "") == name:
                return item
    except TypeError:
        return None
    return None


def _resolve_pending_distance_check_build(pending: _PendingDistanceCheckBuild):
    """Re-resolve a queued build's (group, high object) pair by name.

    Returns None when either name is gone, so the timer drops the entry instead of
    touching RNA that may already have been freed while the build sat in the queue.
    """
    scene = getattr(getattr(bpy, "context", None), "scene", None)
    settings = getattr(scene, "fyr_baker_settings", None) if scene is not None else None
    projects = getattr(settings, "projects", None) if settings is not None else None
    if projects is None:
        return None
    group = None
    project = _collection_lookup_by_name(projects, pending.project_name)
    if project is not None:
        group = _collection_lookup_by_name(getattr(project, "groups", None), pending.group_name)
    if group is None:
        # The project was renamed or could not be resolved at queue time; the group name
        # is still unique enough in practice, and finding it here beats re-queueing the
        # same build on every redraw.
        for candidate_project in projects:
            group = _collection_lookup_by_name(getattr(candidate_project, "groups", None), pending.group_name)
            if group is not None:
                break
    if group is None:
        return None
    for obj in _iter_high_objects(group):
        if str(getattr(obj, "name", "") or "") == pending.object_name:
            return group, obj
    return None


def _distance_check_build_timer():
    # Chunked builder: each tick advances the active job by a bounded number of
    # vertices so the main thread never blocks for the whole (multi-million
    # vertex) high mesh in one callback. See _DISTANCE_CHECK_CHUNK.
    global _DISTANCE_CHECK_BUILD_TIMER_REGISTERED, _ACTIVE_DISTANCE_CHECK_JOB
    context = getattr(bpy, "context", None)
    try:
        if _ACTIVE_DISTANCE_CHECK_JOB is None:
            if not _PENDING_DISTANCE_CHECK_BUILDS:
                _DISTANCE_CHECK_BUILD_TIMER_REGISTERED = False
                return None
            key, pending = next(iter(_PENDING_DISTANCE_CHECK_BUILDS.items()))
            _PENDING_DISTANCE_CHECK_BUILDS.pop(key, None)
            # The queue holds names, not pointers: this entry may have waited seconds
            # while the user deleted the group or undid past it, so resolve against the
            # live project and drop the build when it no longer exists.
            resolved = _resolve_pending_distance_check_build(pending)
            if context is not None and resolved is not None:
                group, obj = resolved
                _ACTIVE_DISTANCE_CHECK_JOB = _start_distance_check_job(context, key, group, obj)
            # Starting a job front-loads the high-mesh capture (to_mesh +
            # foreach_get), which is itself a full tick's worth of work. Yield
            # before computing the first vertex chunk so the two never stack.
            if _ACTIVE_DISTANCE_CHECK_JOB is not None or _PENDING_DISTANCE_CHECK_BUILDS:
                return 0.0
            _DISTANCE_CHECK_BUILD_TIMER_REGISTERED = False
            return None
        job = _ACTIVE_DISTANCE_CHECK_JOB
        if job is not None:
            if _distance_check_signature(job.group, job.obj) != job.prep["signature"]:
                _ACTIVE_DISTANCE_CHECK_JOB = None
                return 0.0
            # Prefer the GPU compute path: it resolves the whole mesh in one tick
            # (~0.1s). It only runs on the first advance; on failure/unavailable it
            # returns None and we fall through to CPU chunking.
            if job.cursor == 0:
                gpu_result = _compute_distance_check_gpu(job.prep)
                if gpu_result is not None:
                    job.required[:] = gpu_result[0]
                    job.slot[:] = gpu_result[1]
                    job.cursor = job.vertex_count
            if job.cursor < job.vertex_count:
                start = job.cursor
                end = min(job.vertex_count, start + _DISTANCE_CHECK_CHUNK)
                chunk_required, chunk_slot = _distance_check_compute_chunk(job.prep, start, end)
                job.required[start:end] = chunk_required
                job.slot[start:end] = chunk_slot
                job.cursor = end
            if job.cursor >= job.vertex_count:
                _distance_check_make_batch(job.group, job.obj, job.prep, job.required, job.slot)
                _ACTIVE_DISTANCE_CHECK_JOB = None
                _tag_redraw_all_view3d()
    except Exception:
        _ACTIVE_DISTANCE_CHECK_JOB = None
        _log_error_once("[Fyr Baker] Cage Check overlay failed to build queued distance-check data:\n" + traceback.format_exc())
    if _PENDING_DISTANCE_CHECK_BUILDS or _ACTIVE_DISTANCE_CHECK_JOB is not None:
        return 0.0
    _DISTANCE_CHECK_BUILD_TIMER_REGISTERED = False
    return None


def _tag_redraw_all_view3d() -> None:
    _tag_redraw_all_view3d_impl(all_windows=True)


def _ensure_distance_check_build_timer_registered() -> None:
    global _DISTANCE_CHECK_BUILD_TIMER_REGISTERED
    if _DISTANCE_CHECK_BUILD_TIMER_REGISTERED:
        return
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is None or not hasattr(timers, "register"):
        return
    try:
        timers.register(_distance_check_build_timer, first_interval=0.01)
        _DISTANCE_CHECK_BUILD_TIMER_REGISTERED = True
    except Exception:
        _DISTANCE_CHECK_BUILD_TIMER_REGISTERED = False


def _queue_distance_check_batch_build(group, obj) -> None:
    key = _distance_check_build_key(group, obj)
    pointer, signature = key
    if _DISTANCE_CHECK_BATCH_CACHE.get((pointer, signature, _DISTANCE_CHECK_MATH_VERSION)) is not None:
        return
    if _HIGH_MESH_FAILURE_SIGNATURES.get(("distance", pointer)) == signature:
        return
    if _ACTIVE_DISTANCE_CHECK_JOB is not None and _ACTIVE_DISTANCE_CHECK_JOB.key == key:
        return
    scene = getattr(getattr(bpy, "context", None), "scene", None)
    _settings, project, _active_group = cage_session.resolve_project_group(scene)
    for pending_key, pending in tuple(_PENDING_DISTANCE_CHECK_BUILDS.items()):
        if (pending.object_name == obj.name and pending.group_name == group.name
                and pending.project_name == str(getattr(project, "name", "") or "")):
            _PENDING_DISTANCE_CHECK_BUILDS.pop(pending_key, None)
    _PENDING_DISTANCE_CHECK_BUILDS[key] = _PendingDistanceCheckBuild(
        project_name=str(getattr(project, "name", "") or ""),
        group_name=str(getattr(group, "name", "") or ""),
        object_name=str(getattr(obj, "name", "") or ""),
    )
    _ensure_distance_check_build_timer_registered()


def _log_error_once(error_text: str) -> None:
    global _LAST_ERROR
    if error_text and error_text != _LAST_ERROR:
        print(error_text)
        _LAST_ERROR = error_text


def clear_cage_check_gpu_cache() -> None:
    global _DISTANCE_CHECK_BUILD_TIMER_REGISTERED, _HIGH_MESH_BUILD_TIMER_REGISTERED
    global _ACTIVE_DISTANCE_CHECK_JOB, _DISTANCE_CHECK_SOURCE_CACHE
    _DISTANCE_CHECK_SOURCE_CACHE = None
    _SDF_TEXTURE_CACHE.clear()
    _HIGH_MESH_BATCH_CACHE.clear()
    _HIGH_MESH_BUILD_QUEUE.clear()
    _DISTANCE_CHECK_BATCH_CACHE.clear()
    _HIGH_MESH_FAILURE_SIGNATURES.clear()
    _PENDING_DISTANCE_CHECK_BUILDS.clear()
    _ACTIVE_DISTANCE_CHECK_JOB = None
    timers = getattr(getattr(bpy, "app", None), "timers", None)
    if timers is not None and _HIGH_MESH_BUILD_TIMER_REGISTERED and hasattr(timers, "unregister"):
        try:
            timers.unregister(_high_mesh_build_timer)
        except Exception:
            pass
    _HIGH_MESH_BUILD_TIMER_REGISTERED = False
    if timers is not None and _DISTANCE_CHECK_BUILD_TIMER_REGISTERED and hasattr(timers, "unregister"):
        try:
            timers.unregister(_distance_check_build_timer)
        except Exception:
            pass
    _DISTANCE_CHECK_BUILD_TIMER_REGISTERED = False


def diagnose_cage_check_overlay(context, settings, project, group) -> dict[str, object]:
    overlay_state = _overlay_settings_state(settings)
    scene = getattr(context, "scene", None)
    distance_scalar_check = str(getattr(group, "cage_mode", "") or "") == "DISTANCE"
    result: dict[str, object] = {
        "show_cage_overlay": bool(getattr(overlay_state, "show_cage_overlay", False)) if overlay_state is not None else False,
        "show_cage_check": bool(getattr(overlay_state, "show_error_heatmap", False)) if overlay_state is not None else False,
        "group_name": str(getattr(group, "name", "") or ""),
        "cage_mode": str(getattr(group, "cage_mode", "") or ""),
        "distance_live_shell": False,
        "distance_scalar_check": distance_scalar_check,
        "low_slot_count": _role_slot_count(group, "low_meshes"),
        "high_slot_count": _role_slot_count(group, "high_meshes"),
        "flat_low_slot_count": len(getattr(group, "low_meshes", []) or []),
        "nested_low_slot_count": len(getattr(_group_role_assignments_state(group), "low_meshes", []) or []),
        "flat_high_slot_count": len(getattr(group, "high_meshes", []) or []),
        "nested_high_slot_count": len(getattr(_group_role_assignments_state(group), "high_meshes", []) or []),
        "debug_result": False,
        "sdf_path": "",
        "sdf_exists": False,
        "sdf_resolution": (),
        "sdf_texture": False,
        "shader": False,
        "shell_shader": False,
        "distance_scalar_shader": False,
        "high_object_count": 0,
        "high_object_names": [],
        "high_batch_count": 0,
        "distance_check_batch_count": 0,
        "shell_draw_status": dict(_LAST_SHELL_DRAW_STATUS),
        "last_error": _LAST_ERROR,
        "errors": [],
    }
    errors: list[str] = result["errors"]  # type: ignore[assignment]
    if bool(result["distance_scalar_check"]):
        try:
            result["distance_scalar_shader"] = _get_distance_scalar_shader() is not None
            result["shader"] = result["distance_scalar_shader"]
        except Exception:
            errors.append("distance_scalar_shader_exception")
            errors.append(traceback.format_exc())
    else:
        try:
            result["shader"] = _get_shader() is not None
        except Exception:
            errors.append("shader_exception")
            errors.append(traceback.format_exc())

    debug_result = runtime.peek_debug_overlay_result(scene, project, group) if scene is not None else None
    result["debug_result"] = debug_result is not None
    if debug_result is not None and not bool(result["distance_scalar_check"]):
        sdf_path = str(getattr(debug_result, "cage_sdf_path", "") or "").strip()
        result["sdf_path"] = sdf_path
        result["sdf_exists"] = bool(sdf_path and Path(sdf_path).exists())
        result["sdf_resolution"] = tuple(int(value) for value in list(getattr(debug_result, "cage_sdf_resolution", []) or []))
        try:
            sdf = _load_sdf_texture(debug_result)
            result["sdf_texture"] = sdf is not None
            if sdf is not None:
                result["sdf_resolution"] = sdf.resolution
        except Exception:
            errors.append("sdf_texture_exception")
            errors.append(traceback.format_exc())

    high_objects = list(_iter_high_objects(group))
    result["high_object_count"] = len(high_objects)
    result["high_object_names"] = [str(getattr(obj, "name", "") or "") for obj in high_objects]
    if not high_objects:
        errors.append("no_high_mesh_objects")
    high_batch_count = 0
    distance_check_batch_count = 0
    for obj in high_objects:
        try:
            batch_available = _build_high_mesh_batch(context, obj) is not None
            if batch_available:
                high_batch_count += 1
            else:
                errors.append(f"high_batch_unavailable:{getattr(obj, 'name', '')}")
            if bool(result["distance_scalar_check"]):
                distance_batch_available = _build_distance_check_batch(context, group, obj) is not None
                if distance_batch_available:
                    distance_check_batch_count += 1
                else:
                    errors.append(f"distance_check_batch_unavailable:{getattr(obj, 'name', '')}")
        except Exception:
            errors.append(f"high_batch_exception:{getattr(obj, 'name', '')}")
            errors.append(traceback.format_exc())
    result["high_batch_count"] = high_batch_count
    result["distance_check_batch_count"] = distance_check_batch_count
    result["last_error"] = _LAST_ERROR
    return result


def _depth_bias_clip_cap(context, group, extra_offset: float = 0.0) -> float:
    """Ceiling for the coverage depth bias, as a WORLD distance (about a third of the
    cage offset, so the biased paint can never cross the cage shell however far the
    view zooms out) folded with the projection scale the vertex shader needs (see
    _OVERLAY_DEPTH_BIAS_GLSL). The 1mm floor keeps the close-range coincident-surface
    speckle fix alive for zero-offset cages."""
    try:
        offset = max(0.0, float(getattr(group, "cage_offset", 0.0) or 0.0))
    except Exception:
        offset = 0.0
    offset = max(offset, max(0.0, float(extra_offset or 0.0)))
    world_cap = max(1.0e-3, offset * 0.35)
    proj_scale = 0.0
    region_data = getattr(context, "region_data", None)
    window_matrix = getattr(region_data, "window_matrix", None)
    if window_matrix is not None:
        try:
            if bool(getattr(region_data, "is_perspective", True)):
                proj_scale = abs(float(window_matrix[2][3]))
            else:
                proj_scale = abs(float(window_matrix[2][2]))
        except Exception:
            proj_scale = 0.0
    if proj_scale <= 0.0:
        # No projection available (headless/tests): a scale of 1 makes the cap larger
        # than the proportional term at working distances, i.e. the pre-cap behavior.
        proj_scale = 1.0
    return world_cap * proj_scale


def _draw_distance_scalar_overlay(
    context,
    group,
    model_view_projection_matrix,
    *,
    shell_cache_status=None,
    depth_write: bool = False,
) -> bool:
    global _LAST_SHELL_DRAW_STATUS
    slot_offsets = _distance_slot_offsets(group)
    slot_offset_count = _distance_slot_offset_count(group)
    _LAST_SHELL_DRAW_STATUS = {
        "attempted": True,
        "mode": "distance_scalar",
        "cache": dict(shell_cache_status or {}),
        "slot_offset_count": slot_offset_count,
        "slot_offsets": tuple(round(value, 6) for value in slot_offsets[:slot_offset_count]),
        "depth_write": bool(depth_write),
        "drew_any": False,
    }
    try:
        max_slot_offset = max(
            (float(slot_offsets[index]) for index in range(slot_offset_count)), default=0.0
        )
        depth_bias_cap = _depth_bias_clip_cap(context, group, extra_offset=max_slot_offset)
        shader = _get_distance_scalar_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
        shader.uniform_float("depthBiasClipCap", depth_bias_cap)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(bool(depth_write))
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("NONE")
        if hasattr(gpu.state, "face_culling_set"):
            gpu.state.face_culling_set("NONE")
        drew_any = False
        drawn_batches = 0
        vertex_count = 0
        required_max = 0.0
        pending_batches = 0
        for slot_index in range(slot_offset_count):
            slot_offset = float(slot_offsets[slot_index])
            for obj in _iter_high_objects(group):
                batch_entry = _cached_distance_check_batch(group, obj)
                if batch_entry is None:
                    _queue_distance_check_batch_build(group, obj)
                    pending_batches += 1
                    continue
                shader.bind()
                shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
                shader.uniform_float("depthBiasClipCap", depth_bias_cap)
                shader.uniform_float("slotOffset", slot_offset)
                shader.uniform_float("activeSlotIndex", float(slot_index))
                shader.uniform_float("distanceTolerance", max(slot_offset * 0.002, 1.0e-5))
                batch_entry.batch.draw(shader)
                drew_any = True
                drawn_batches += 1
                vertex_count += int(batch_entry.vertex_count)
                required_max = max(required_max, float(batch_entry.required_max))
        _LAST_SHELL_DRAW_STATUS.update(
            {
                "drew_any": drew_any,
                "drawn_batches": drawn_batches,
                "vertex_count": vertex_count,
                "required_max": required_max,
                "pending_batches": pending_batches,
            }
        )
        return drew_any
    except Exception:
        error_text = traceback.format_exc()
        _log_error_once(error_text)
        _LAST_SHELL_DRAW_STATUS.update({"error": error_text})
        return False
    finally:
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)


def _draw_screen_cage_overlay(
    context,
    group,
    model_view_projection_matrix,
    *,
    viewport_origin,
    viewport_size,
    cage_depth_resources,
    shell_cache_status=None,
    depth_write: bool = False,
) -> bool:
    """Color visible high-poly fragments through the rasterized cage mask.

    This is deliberately view-space, like Painter's cage coverage display: cage
    edits redraw the low-poly shell mask while the cached high-poly batch remains
    untouched. No per-high-vertex nearest-surface or ray approximation is needed.
    """
    global _LAST_SHELL_DRAW_STATUS
    _LAST_SHELL_DRAW_STATUS = {
        "attempted": True,
        "mode": "screen_cage_mask",
        "cache": dict(shell_cache_status or {}),
        "viewport_origin": tuple(viewport_origin or ()),
        "viewport_size": tuple(viewport_size or ()),
        "depth_write": bool(depth_write),
        "drew_any": False,
    }
    if cage_depth_resources is None or viewport_size is None:
        return False
    try:
        shader = _get_shell_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
        model_view_matrix = gpu.matrix.get_model_view_matrix()
        shader.uniform_float("ModelViewMatrix", model_view_matrix)
        shader.uniform_float("viewportOrigin", viewport_origin or (0.0, 0.0))
        shader.uniform_float("viewportSize", viewport_size)
        shader.uniform_float(
            "depthTextureSize",
            (
                float(max(1, int(getattr(cage_depth_resources, "width", 1) or 1))),
                float(max(1, int(getattr(cage_depth_resources, "height", 1) or 1))),
            ),
        )
        shader.uniform_float("depthBiasClipCap", _depth_bias_clip_cap(context, group))
        if hasattr(shader, "uniform_sampler"):
            shader.uniform_sampler("cageDepthTexture", cage_depth_resources.color_texture)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(bool(depth_write))
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("NONE")
        if hasattr(gpu.state, "face_culling_set"):
            gpu.state.face_culling_set("NONE")
        drew_any = False
        drawn_batches = 0
        for obj in _iter_high_objects(group):
            batch_entry = _build_high_mesh_batch(context, obj)
            if batch_entry is None:
                continue
            batch_entry.batch.draw(shader)
            drew_any = True
            drawn_batches += 1
        beneath_drawn = False
        if drew_any:
            try:
                beneath_drawn = _draw_high_beneath_low(
                    context,
                    group,
                    model_view_projection_matrix,
                    model_view_matrix,
                    viewport_origin=viewport_origin,
                    viewport_size=viewport_size,
                    width=int(getattr(cage_depth_resources, "width", 1) or 1),
                    height=int(getattr(cage_depth_resources, "height", 1) or 1),
                )
            except Exception:
                _log_error_once(traceback.format_exc())
            if hasattr(gpu.state, "depth_mask_set"):
                gpu.state.depth_mask_set(bool(depth_write))
        _LAST_SHELL_DRAW_STATUS.update(
            {
                "drew_any": drew_any,
                "drawn_batches": drawn_batches,
                "beneath_drawn": beneath_drawn,
            }
        )
        return drew_any
    except Exception:
        error_text = traceback.format_exc()
        _log_error_once(error_text)
        _LAST_SHELL_DRAW_STATUS.update({"error": error_text})
        return False
    finally:
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)


def _draw_distance_solid_overlay(
    context,
    group,
    model_view_projection_matrix,
    *,
    color=(1.0, 0.08, 0.04, 1.0),
    shell_cache_status=None,
    depth_write: bool = False,
) -> bool:
    global _LAST_SHELL_DRAW_STATUS
    _LAST_SHELL_DRAW_STATUS = {
        "attempted": True,
        "mode": "distance_degenerate_offset",
        "cache": dict(shell_cache_status or {}),
        "depth_write": bool(depth_write),
        "drew_any": False,
    }
    try:
        shader = _get_solid_high_shader()
        shader.bind()
        shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
        shader.uniform_float("depthBiasClipCap", _depth_bias_clip_cap(context, group))
        shader.uniform_float("color", color)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(bool(depth_write))
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("NONE")
        if hasattr(gpu.state, "face_culling_set"):
            gpu.state.face_culling_set("NONE")
        drew_any = False
        drawn_batches = 0
        for obj in _iter_high_objects(group):
            batch_entry = _build_high_mesh_batch(context, obj)
            if batch_entry is None:
                continue
            batch_entry.batch.draw(shader)
            drew_any = True
            drawn_batches += 1
        _LAST_SHELL_DRAW_STATUS.update(
            {
                "drew_any": drew_any,
                "drawn_batches": drawn_batches,
            }
        )
        return drew_any
    except Exception:
        error_text = traceback.format_exc()
        _log_error_once(error_text)
        _LAST_SHELL_DRAW_STATUS.update({"error": error_text})
        return False
    finally:
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)


def draw_cage_check_overlay(
    context,
    settings,
    project,
    group,
    theme,
    model_view_projection_matrix,
    *,
    viewport_origin=None,
    viewport_size=None,
    low_depth_resources=None,
    cage_depth_resources=None,
    low_depth_epsilon=1.0e-5,
    shell_cache_status=None,
    depth_write: bool = False,
) -> bool:
    overlay_state = _overlay_settings_state(settings)
    if overlay_state is None or not bool(getattr(overlay_state, "show_error_heatmap", False)):
        return False
    cage_mode = str(getattr(group, "cage_mode", "") or "")
    if cage_depth_resources is not None:
        return _draw_screen_cage_overlay(
            context,
            group,
            model_view_projection_matrix,
            viewport_origin=viewport_origin,
            viewport_size=viewport_size,
            cage_depth_resources=cage_depth_resources,
            shell_cache_status=shell_cache_status,
            depth_write=depth_write,
        )
    if cage_mode in ("DISTANCE", "AUTOMATIC", "CUSTOM"):
        # Distance/Custom test enclosure against the displayed shell; Automatic
        # retains its fitted reach test. Coverage is independent of ray-miss diagnostics.
        return _draw_distance_scalar_overlay(
            context,
            group,
            model_view_projection_matrix,
            shell_cache_status=shell_cache_status,
            depth_write=depth_write,
        )
    scene = getattr(context, "scene", None)
    debug_result = runtime.peek_debug_overlay_result(scene, project, group) if scene is not None else None
    if debug_result is None:
        return False
    input_signature = export.debug_overlay_input_signature(project, group)
    if not runtime.debug_overlay_result_matches_input_signature(scene, project, group, input_signature):
        return False
    try:
        sdf = _load_sdf_texture(debug_result)
        if sdf is None:
            return False
        shader = _get_shader()
        shader.bind()
        shader.uniform_float("depthBiasClipCap", _depth_bias_clip_cap(context, group))
        shader.uniform_float("sdfBoundsMin", sdf.bounds_min)
        size = (
            max(1.0e-8, sdf.bounds_max[0] - sdf.bounds_min[0]),
            max(1.0e-8, sdf.bounds_max[1] - sdf.bounds_min[1]),
            max(1.0e-8, sdf.bounds_max[2] - sdf.bounds_min[2]),
        )
        shader.uniform_float("sdfBoundsInvSize", (1.0 / size[0], 1.0 / size[1], 1.0 / size[2]))
        shader.uniform_float("distanceTolerance", max(float(sdf.voxel_size) * 0.5, 1.0e-6))
        shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
        if hasattr(shader, "uniform_sampler"):
            shader.uniform_sampler("cageSdf", sdf.texture)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL" if depth_write else "NONE")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(bool(depth_write))
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("ALPHA")
        if hasattr(gpu.state, "face_culling_set"):
            gpu.state.face_culling_set("NONE")
        drew_any = False
        for obj in _iter_high_objects(group):
            batch_entry = _build_high_mesh_batch(context, obj)
            if batch_entry is None:
                continue
            batch_entry.batch.draw(shader)
            drew_any = True
        return drew_any
    except Exception:
        _log_error_once(traceback.format_exc())
        return False
    finally:
        if hasattr(gpu.state, "face_culling_set"):
            gpu.state.face_culling_set("NONE")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)
