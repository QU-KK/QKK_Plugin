from __future__ import annotations

from array import array
from dataclasses import dataclass, field
import traceback

import gpu


@dataclass(slots=True)
class LowDepthMaskResources:
    width: int
    height: int
    color_texture: object
    depth_texture: object
    framebuffer: object
    color_format: str = ""
    depth_format: str = ""


@dataclass(slots=True)
class OverlayGpuState:
    shader: object | None = None
    offset_shader: object | None = None
    lit_offset_shader: object | None = None
    paint_offset_shader: object | None = None
    lit_shader: object | None = None
    skew_shader: object | None = None
    skew_batch_format: object | None = None
    heatmap_mask_shader: object | None = None
    low_depth_mask_shader: object | None = None
    shell_low_depth_mask_shader: object | None = None
    shell_cage_depth_mask_shader: object | None = None
    shell_cage_paint_depth_mask_shader: object | None = None
    lit_batch_format: object | None = None
    offset_batch_format: object | None = None
    paint_offset_batch_format: object | None = None
    white_paint_texture: object | None = None
    last_mask_error: str = ""
    low_depth_mask_resources: LowDepthMaskResources | None = None
    shell_low_depth_mask_resources: LowDepthMaskResources | None = None
    shell_cage_depth_mask_resources: LowDepthMaskResources | None = None
    shell_cage_back_depth_mask_resources: LowDepthMaskResources | None = None
    shell_high_depth_mask_resources: LowDepthMaskResources | None = None
    #: Per-slot pools keyed by (width, height). One 3D viewport per size keeps its
    #: own offscreen; a single size-keyed slot reallocated a full RGBA + depth
    #: framebuffer every frame when two viewports of different sizes alternated.
    mask_resource_pools: dict = field(default_factory=dict)


def log_mask_error_once(state: OverlayGpuState, error_text: str) -> None:
    if error_text and error_text != state.last_mask_error:
        print(error_text)
        state.last_mask_error = error_text


# Cage and paint passes are drawn on geometry that can sit exactly ON the low mesh --
# a zero-offset cage, and the paint mask, whose own displacement (normal * paint)
# vanishes wherever the mask reads black. Coincident surfaces then split the
# LESS_EQUAL depth test per pixel and the overlay breaks into z-fighting speckle.
#
# The fix biases CLIP Z only, never the geometry: the overlay wins the depth tie
# without moving in space, so a cage face genuinely behind the mesh stays hidden --
# displacing the geometry instead would push those faces through it. The bias is
# capped at a WORLD distance so the guarantee survives zooming out: a constant NDC
# bias is a world distance that grows with the square of the view distance, and past
# some zoom it would cross real geometry. Shifting a point d toward the viewer at eye
# depth w moves NDC z by proj_scale*d/w^2 while the clip-z hack shifts it by bias/w,
# so bias <= proj_scale*d_max/w. depthBiasClipCap carries proj_scale*d_max and the
# shader divides by |w|. Same derivation as the coverage overlay in
# overlay_cage_check_gpu (_OVERLAY_DEPTH_BIAS_GLSL); kept in sync deliberately.
_CAGE_DEPTH_BIAS_CLIP = 1.5e-4
_CAGE_DEPTH_BIAS_FLOOR = 1.0e-6
_CAGE_DEPTH_BIAS_GLSL = (
    "  float absW = max(abs(gl_Position.w), 1.0e-9);\n"
    f"  gl_Position.z -= max(min(absW * {_CAGE_DEPTH_BIAS_CLIP:.8f},"
    f" depthBiasClipCap / absW), {_CAGE_DEPTH_BIAS_FLOOR:.8f});\n"
)


def get_shader(state: OverlayGpuState):
    if state.shader is None:
        state.shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    return state.shader


def get_offset_shader(state: OverlayGpuState):
    if state.offset_shader is None:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("VEC4", "color")
        info.push_constant("FLOAT", "offset")
        info.push_constant("FLOAT", "depthBiasClipCap")
        info.vertex_in(0, "VEC3", "position")
        info.vertex_in(1, "VEC3", "normal")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              vec3 world_position = position + (normal * offset);
              gl_Position = ModelViewProjectionMatrix * vec4(world_position, 1.0);
"""
            + _CAGE_DEPTH_BIAS_GLSL
            + """            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              FragColor = color;
            }
            """
        )
        state.offset_shader = gpu.shader.create_from_info(info)
        del info
    return state.offset_shader


def get_lit_offset_shader(state: OverlayGpuState):
    if state.lit_offset_shader is None:
        vert_out = gpu.types.GPUStageInterfaceInfo("lit_offset_iface")
        vert_out.smooth("VEC4", "v_color")
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_out(vert_out)
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("VEC4", "color")
        info.push_constant("FLOAT", "offset")
        info.push_constant("FLOAT", "depthBiasClipCap")
        info.vertex_in(0, "VEC3", "position")
        info.vertex_in(1, "VEC3", "normal")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              vec3 world_position = position + (normal * offset);
              gl_Position = ModelViewProjectionMatrix * vec4(world_position, 1.0);
"""
            + _CAGE_DEPTH_BIAS_GLSL
            + """              vec3 n = normalize(normal);
              vec3 light = normalize(vec3(0.31, 0.42, 0.85));
              float diffuse = max(0.0, dot(n, light));
              float brightness = 0.2 + diffuse * 0.8;
              v_color = vec4(color.rgb * brightness, color.a);
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              FragColor = v_color;
            }
            """
        )
        state.lit_offset_shader = gpu.shader.create_from_info(info)
        del info
    return state.lit_offset_shader


def get_paint_offset_shader(state: OverlayGpuState):
    if state.paint_offset_shader is None:
        vert_out = gpu.types.GPUStageInterfaceInfo("paint_offset_iface")
        vert_out.smooth("VEC2", "paint_uv")
        vert_out.smooth("FLOAT", "paint_mult")
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_out(vert_out)
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("VEC4", "color")
        info.push_constant("FLOAT", "offset_scale")
        info.push_constant("FLOAT", "show_paint_mask")
        info.push_constant("FLOAT", "depthBiasClipCap")
        info.vertex_in(0, "VEC3", "position")
        info.vertex_in(1, "VEC3", "normal")
        info.vertex_in(2, "VEC2", "uv")
        # Paint layer multiplier per corner (max(0, 1 + r)); a group painted with the
        # brush binds a white canvas, a legacy canvas group has 1 here.
        info.vertex_in(3, "FLOAT", "paint_value")
        info.sampler(0, "FLOAT_2D", "paintOffsetTexture")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              float paint = texture(paintOffsetTexture, uv).r * paint_value;
              vec3 world_position = position + (normal * (offset_scale * paint));
              gl_Position = ModelViewProjectionMatrix * vec4(world_position, 1.0);
"""
            + _CAGE_DEPTH_BIAS_GLSL
            + """              paint_uv = uv;
              paint_mult = paint_value;
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              float paint = texture(paintOffsetTexture, paint_uv).r * paint_mult;
              // Half transparent: at 0.88 the default all-white canvas was an opaque
              // white sheet and the artist could not see the surface (or the bake
              // errors) they were painting over. White still reads as more offset.
              vec4 mask_color = vec4(vec3(paint), 0.5);
              FragColor = mix(color, mask_color, show_paint_mask);
            }
            """
        )
        state.paint_offset_shader = gpu.shader.create_from_info(info)
        del info
    return state.paint_offset_shader


def get_lit_shader(state: OverlayGpuState):
    if state.lit_shader is None:
        state.lit_shader = gpu.shader.from_builtin("SMOOTH_COLOR")
    return state.lit_shader


def get_skew_shader(state: OverlayGpuState):
    """Skew needle lines: each vertex carries the needle's start point and its
    offset from that start (zero for the base vertex, the unit-scale needle vector
    for the tip). The length slider is a push constant, so dragging it never
    regenerates the field and the needles stay on screen while it moves."""
    if state.skew_shader is None:
        info = gpu.types.GPUShaderCreateInfo()
        vert_out = gpu.types.GPUStageInterfaceInfo("skew_needle_iface")
        vert_out.smooth("VEC4", "vertexColor")
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("MAT4", "ModelViewMatrix")
        info.push_constant("FLOAT", "needleScale")
        # Constant Screen Size: 1.0 keeps every needle needleScale * 600 pixels long.
        # pixelToWorld is world units per pixel at unit view depth (2 / (P[1][1] *
        # viewport height)); isPersp scales that by the view depth of the base.
        info.push_constant("FLOAT", "constantScreenSize")
        info.push_constant("FLOAT", "pixelToWorld")
        info.push_constant("FLOAT", "isPersp")
        info.vertex_in(0, "VEC3", "pos")
        info.vertex_in(1, "VEC3", "needle")
        info.vertex_in(2, "VEC4", "color")
        info.vertex_in(3, "VEC3", "dir")
        info.vertex_out(vert_out)
        info.fragment_out(0, "VEC4", "FragColor")
        # Needle colours are authored in sRGB (cage._skew_deviation_color); the
        # builtin SMOOTH_COLOR shader linearised them for us, a custom shader must
        # do it itself or the needles wash out to pastel (see the HUD srgb note).
        # The hue stays the skew reading (green = along the face normal, amber =
        # tilted); brightness is a headlight term on the needle direction in view
        # space, so needles on faces that turn away from the viewer go darker and
        # neighbouring surfaces stop bleeding into one flat green. The term is
        # applied before linearisation so the contrast reads as strongly as a
        # Solid-mode studio light does. Ambient floor 0.42: Glow found the first
        # cut's backsides (0.22) too dark to read.
        info.vertex_source(
            """
            vec3 srgb_to_linear(vec3 c)
            {
              vec3 low = c / 12.92;
              vec3 high = pow((c + vec3(0.055)) / 1.055, vec3(2.4));
              return mix(low, high, step(vec3(0.04045), c));
            }

            void main()
            {
              vec3 n = normalize(mat3(ModelViewMatrix) * dir);
              vec3 key = normalize(vec3(-0.40, 0.55, 0.75));
              float shade = 0.42 + 0.42 * max(dot(n, key), 0.0) + 0.16 * max(n.z, 0.0);
              vertexColor = vec4(srgb_to_linear(color.rgb * shade), color.a);
              vec3 tip = pos + needle * needleScale;
              if (constantScreenSize > 0.5 && dot(needle, needle) > 0.0) {
                vec4 view_pos = ModelViewMatrix * vec4(pos, 1.0);
                float depth = isPersp > 0.5 ? max(-view_pos.z, 1.0e-5) : 1.0;
                tip = pos + dir * (needleScale * 600.0 * pixelToWorld * depth);
              }
              gl_Position = ModelViewProjectionMatrix * vec4(tip, 1.0);
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              FragColor = vertexColor;
            }
            """
        )
        state.skew_shader = gpu.shader.create_from_info(info)
        del vert_out
        del info
    return state.skew_shader


def get_skew_batch_format(state: OverlayGpuState):
    if state.skew_batch_format is None:
        batch_format = gpu.types.GPUVertFormat()
        batch_format.attr_add(id="pos", comp_type="F32", len=3, fetch_mode="FLOAT")
        batch_format.attr_add(id="needle", comp_type="F32", len=3, fetch_mode="FLOAT")
        batch_format.attr_add(id="color", comp_type="F32", len=4, fetch_mode="FLOAT")
        batch_format.attr_add(id="dir", comp_type="F32", len=3, fetch_mode="FLOAT")
        state.skew_batch_format = batch_format
    return state.skew_batch_format


def get_low_depth_mask_shader(state: OverlayGpuState):
    if state.low_depth_mask_shader is None:
        info = gpu.types.GPUShaderCreateInfo()
        vert_out = gpu.types.GPUStageInterfaceInfo("low_depth_mask_iface")
        vert_out.smooth("FLOAT", "viewDepth")
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("MAT4", "ModelViewMatrix")
        info.vertex_in(0, "VEC3", "pos")
        info.vertex_out(vert_out)
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              vec4 viewPosition = ModelViewMatrix * vec4(pos, 1.0);
              viewDepth = -viewPosition.z;
              gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              FragColor = vec4(viewDepth, 1.0, 0.0, 1.0);
            }
            """
        )
        state.low_depth_mask_shader = gpu.shader.create_from_info(info)
        del vert_out
        del info
    return state.low_depth_mask_shader


def get_shell_low_depth_mask_shader(state: OverlayGpuState):
    if state.shell_low_depth_mask_shader is None:
        info = gpu.types.GPUShaderCreateInfo()
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.vertex_in(0, "VEC3", "pos")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              FragColor = vec4(gl_FragCoord.z, 1.0, 0.0, 1.0);
            }
            """
        )
        state.shell_low_depth_mask_shader = gpu.shader.create_from_info(info)
        del info
    return state.shell_low_depth_mask_shader


def get_shell_cage_depth_mask_shader(state: OverlayGpuState):
    if state.shell_cage_depth_mask_shader is None:
        vert_out = gpu.types.GPUStageInterfaceInfo("shell_cage_depth_iface")
        vert_out.smooth("FLOAT", "viewDepth")
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_out(vert_out)
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("MAT4", "ModelViewMatrix")
        info.push_constant("FLOAT", "offset")
        info.vertex_in(0, "VEC3", "position")
        info.vertex_in(1, "VEC3", "normal")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              vec3 world_position = position + (normal * offset);
              gl_Position = ModelViewProjectionMatrix * vec4(world_position, 1.0);
              viewDepth = -(ModelViewMatrix * vec4(world_position, 1.0)).z;
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              FragColor = vec4(viewDepth, 0.0, 0.0, 1.0);
            }
            """
        )
        state.shell_cage_depth_mask_shader = gpu.shader.create_from_info(info)
        del vert_out
        del info
    return state.shell_cage_depth_mask_shader


def get_shell_cage_paint_depth_mask_shader(state: OverlayGpuState):
    if state.shell_cage_paint_depth_mask_shader is None:
        vert_out = gpu.types.GPUStageInterfaceInfo("shell_cage_paint_depth_iface")
        vert_out.smooth("FLOAT", "viewDepth")
        info = gpu.types.GPUShaderCreateInfo()
        info.vertex_out(vert_out)
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("MAT4", "ModelViewMatrix")
        info.push_constant("FLOAT", "offset_scale")
        info.vertex_in(0, "VEC3", "position")
        info.vertex_in(1, "VEC3", "normal")
        info.vertex_in(2, "VEC2", "uv")
        # Paint layer multiplier per corner (max(0, 1 + r)); a group painted with the
        # brush binds a white canvas, a legacy canvas group has 1 here.
        info.vertex_in(3, "FLOAT", "paint_value")
        info.sampler(0, "FLOAT_2D", "paintOffsetTexture")
        info.fragment_out(0, "VEC4", "FragColor")
        info.vertex_source(
            """
            void main()
            {
              float paint = texture(paintOffsetTexture, uv).r * paint_value;
              vec3 world_position = position + normal * (offset_scale * paint);
              gl_Position = ModelViewProjectionMatrix * vec4(world_position, 1.0);
              viewDepth = -(ModelViewMatrix * vec4(world_position, 1.0)).z;
            }
            """
        )
        info.fragment_source(
            """
            void main()
            {
              FragColor = vec4(viewDepth, 0.0, 0.0, 1.0);
            }
            """
        )
        state.shell_cage_paint_depth_mask_shader = gpu.shader.create_from_info(info)
        del vert_out
        del info
    return state.shell_cage_paint_depth_mask_shader


def get_heatmap_mask_shader(state: OverlayGpuState):
    if state.heatmap_mask_shader is None:
        info = gpu.types.GPUShaderCreateInfo()
        vert_out = gpu.types.GPUStageInterfaceInfo("heatmap_mask_iface")
        vert_out.smooth("VEC4", "vertexColor")
        vert_out.smooth("FLOAT", "viewDepth")
        info.push_constant("MAT4", "ModelViewProjectionMatrix")
        info.push_constant("MAT4", "ModelViewMatrix")
        info.push_constant("VEC2", "viewportOrigin")
        info.push_constant("VEC2", "viewportSize")
        info.push_constant("VEC2", "lowDepthTextureSize")
        info.push_constant("FLOAT", "lowDepthEpsilon")
        info.vertex_in(0, "VEC3", "pos")
        info.vertex_in(1, "VEC4", "color")
        info.vertex_out(vert_out)
        info.fragment_out(0, "VEC4", "FragColor")
        info.sampler(0, "FLOAT_2D", "lowDepthTexture")
        info.vertex_source(
            """
            void main()
            {
              vertexColor = color;
              vec4 viewPosition = ModelViewMatrix * vec4(pos, 1.0);
              viewDepth = -viewPosition.z;
              gl_Position = ModelViewProjectionMatrix * vec4(pos, 1.0);
            }
            """
        )
        info.fragment_source(
            """
            vec2 viewport_coord()
            {
              return gl_FragCoord.xy - viewportOrigin;
            }

            vec2 sample_low_depth()
            {
              ivec2 depthTextureSize = max(ivec2(lowDepthTextureSize), ivec2(1));
              vec2 sampleScale = lowDepthTextureSize / max(viewportSize, vec2(1.0));
              vec2 coord = viewport_coord();
              if (sampleScale.x <= 1.01 && sampleScale.y <= 1.01) {
                ivec2 pixel = clamp(ivec2(coord), ivec2(0), depthTextureSize - ivec2(1));
                vec4 lowSample = texelFetch(lowDepthTexture, pixel, 0);
                return vec2(lowSample.r, lowSample.g);
              }

              vec2 texelMinFloat = max(vec2(0.0), (coord - vec2(0.5)) * sampleScale);
              vec2 texelMaxFloat = max(texelMinFloat, (coord + vec2(0.5)) * sampleScale - vec2(1.0));
              ivec2 texelMin = clamp(ivec2(floor(texelMinFloat)), ivec2(0), depthTextureSize - ivec2(1));
              ivec2 texelMax = clamp(ivec2(ceil(texelMaxFloat)), ivec2(0), depthTextureSize - ivec2(1));
              float lowDepth = 1e20;
              float coverage = 0.0;
              for (int sampleY = 0; sampleY < 3; ++sampleY) {
                for (int sampleX = 0; sampleX < 3; ++sampleX) {
                  ivec2 sampleCoord = texelMin + ivec2(sampleX, sampleY);
                  if (sampleCoord.x > texelMax.x || sampleCoord.y > texelMax.y) {
                    continue;
                  }
                  vec4 lowSample = texelFetch(lowDepthTexture, sampleCoord, 0);
                  if (lowSample.g > 0.5) {
                    coverage = 1.0;
                    lowDepth = min(lowDepth, lowSample.r);
                  }
                }
              }
              return vec2(lowDepth, coverage);
            }

            void main()
            {
              vec2 lowMask = sample_low_depth();
              if (lowMask.y > 0.5 && viewDepth >= (lowMask.x - lowDepthEpsilon)) {
                discard;
              }
              FragColor = vertexColor;
            }
            """
        )
        state.heatmap_mask_shader = gpu.shader.create_from_info(info)
        del vert_out
        del info
    return state.heatmap_mask_shader


def get_lit_batch_format(state: OverlayGpuState):
    if state.lit_batch_format is None:
        batch_format = gpu.types.GPUVertFormat()
        batch_format.attr_add(id="pos", comp_type="F32", len=3, fetch_mode="FLOAT")
        batch_format.attr_add(id="color", comp_type="F32", len=4, fetch_mode="FLOAT")
        state.lit_batch_format = batch_format
    return state.lit_batch_format


def get_offset_batch_format(state: OverlayGpuState):
    if state.offset_batch_format is None:
        batch_format = gpu.types.GPUVertFormat()
        batch_format.attr_add(id="position", comp_type="F32", len=3, fetch_mode="FLOAT")
        batch_format.attr_add(id="normal", comp_type="F32", len=3, fetch_mode="FLOAT")
        state.offset_batch_format = batch_format
    return state.offset_batch_format


def get_paint_offset_batch_format(state: OverlayGpuState):
    if state.paint_offset_batch_format is None:
        batch_format = gpu.types.GPUVertFormat()
        batch_format.attr_add(id="position", comp_type="F32", len=3, fetch_mode="FLOAT")
        batch_format.attr_add(id="normal", comp_type="F32", len=3, fetch_mode="FLOAT")
        batch_format.attr_add(id="uv", comp_type="F32", len=2, fetch_mode="FLOAT")
        batch_format.attr_add(id="paint_value", comp_type="F32", len=1, fetch_mode="FLOAT")
        state.paint_offset_batch_format = batch_format
    return state.paint_offset_batch_format


def low_depth_mask_supported() -> bool:
    gpu_types = getattr(gpu, "types", None)
    return bool(
        gpu_types is not None
        and hasattr(gpu_types, "GPUTexture")
        and hasattr(gpu_types, "GPUFrameBuffer")
    )

_MASK_POOL_MAX_ENTRIES = 4


def _ensure_mask_resources(
    state: OverlayGpuState,
    slot: str,
    width: int,
    height: int,
    *,
    color_format: str,
    depth_format: str,
):
    """Offscreen colour+depth framebuffer for ``slot`` at ``width``x``height``.

    Pooled per slot by size (bounded to a few entries, oldest evicted) so viewports
    of different sizes stop thrashing each other. The slot attribute on ``state``
    keeps pointing at the most recently used entry for diagnostics.
    """
    if not low_depth_mask_supported():
        return None
    width = max(1, int(width))
    height = max(1, int(height))
    pool = state.mask_resource_pools.setdefault(slot, {})
    resources = pool.get((width, height))
    if resources is None:
        depth_texture = gpu.types.GPUTexture((width, height), format=depth_format)
        color_texture = gpu.types.GPUTexture((width, height), format=color_format)
        framebuffer = gpu.types.GPUFrameBuffer(depth_slot=depth_texture, color_slots=(color_texture,))
        resources = LowDepthMaskResources(
            width=width,
            height=height,
            color_texture=color_texture,
            depth_texture=depth_texture,
            framebuffer=framebuffer,
            color_format=color_format,
            depth_format=depth_format,
        )
        while len(pool) >= _MASK_POOL_MAX_ENTRIES:
            pool.pop(next(iter(pool)))
    else:
        # Refresh recency so the eviction above drops the least recently used size.
        pool.pop((width, height))
    pool[(width, height)] = resources
    setattr(state, slot, resources)
    return resources


def release_mask_resources(state: OverlayGpuState) -> None:
    """Drop every pooled offscreen so disable/reload frees the GPU memory now."""
    state.mask_resource_pools.clear()
    state.low_depth_mask_resources = None
    state.shell_low_depth_mask_resources = None
    state.shell_cage_depth_mask_resources = None
    state.shell_cage_back_depth_mask_resources = None
    state.shell_high_depth_mask_resources = None


def ensure_low_depth_mask_resources(state: OverlayGpuState, width: int, height: int):
    return _ensure_mask_resources(
        state, "low_depth_mask_resources", width, height, color_format="RGBA32F", depth_format="DEPTH_COMPONENT32F"
    )


def ensure_shell_low_depth_mask_resources(state: OverlayGpuState, width: int, height: int):
    return _ensure_mask_resources(
        state, "shell_low_depth_mask_resources", width, height, color_format="RGBA16F", depth_format="DEPTH_COMPONENT32F"
    )


def ensure_shell_cage_depth_mask_resources(state: OverlayGpuState, width: int, height: int):
    return _ensure_mask_resources(
        # One full-precision channel is both smaller and more accurate than the old
        # RG16F pair. Half-float window depth quantized neighbouring cage/high
        # fragments into camera-dependent blue/red triangle hatching.
        state, "shell_cage_depth_mask_resources", width, height, color_format="R32F", depth_format="DEPTH_COMPONENT32F"
    )


def ensure_shell_high_depth_mask_resources(state: OverlayGpuState, width: int, height: int):
    # The coverage high's front view depth (full precision, like the cage mask).
    return _ensure_mask_resources(
        state, "shell_high_depth_mask_resources", width, height, color_format="R32F", depth_format="DEPTH_COMPONENT32F"
    )


def ensure_shell_cage_back_depth_mask_resources(state: OverlayGpuState, width: int, height: int):
    return _ensure_mask_resources(
        state, "shell_cage_back_depth_mask_resources", width, height, color_format="RGBA16F", depth_format="DEPTH_COMPONENT32F"
    )



def low_depth_mask_dimensions(
    width: int,
    height: int,
    *,
    max_supersample_scale: int,
    max_supersample_texels: int,
    max_supersample_dimension: int,
) -> tuple[int, int]:
    width = max(1, int(width))
    height = max(1, int(height))
    for scale in range(max_supersample_scale, 1, -1):
        supersampled_width = width * scale
        supersampled_height = height * scale
        if (
            supersampled_width <= max_supersample_dimension
            and supersampled_height <= max_supersample_dimension
            and (supersampled_width * supersampled_height) <= max_supersample_texels
        ):
            return supersampled_width, supersampled_height
    return width, height


def render_low_depth_mask(
    state: OverlayGpuState,
    low_depth_batches,
    width: int,
    height: int,
    *,
    model_view_projection_matrix=None,
    model_view_matrix=None,
    low_depth_mask_dimensions_fn,
    ensure_low_depth_mask_resources_fn,
    get_low_depth_mask_shader_fn,
    log_mask_error_fn,
):
    if not low_depth_batches:
        return None
    color_mask_supported = hasattr(gpu.state, "color_mask_set")
    original_viewport = gpu.state.viewport_get() if hasattr(gpu.state, "viewport_get") else None
    try:
        mask_width, mask_height = low_depth_mask_dimensions_fn(width, height)
        resources = ensure_low_depth_mask_resources_fn(state, mask_width, mask_height)
        if resources is None:
            return None
        framebuffer = resources.framebuffer
        with framebuffer.bind():
            if hasattr(gpu.state, "viewport_set"):
                gpu.state.viewport_set(0, 0, resources.width, resources.height)
            framebuffer.clear(color=(1.0e20, 0.0, 0.0, 0.0), depth=1.0)
            if hasattr(gpu.state, "blend_set"):
                gpu.state.blend_set("NONE")
            if hasattr(gpu.state, "depth_test_set"):
                gpu.state.depth_test_set("LESS")
            if hasattr(gpu.state, "depth_mask_set"):
                gpu.state.depth_mask_set(True)
            if color_mask_supported:
                gpu.state.color_mask_set(True, True, True, True)
            shader = get_low_depth_mask_shader_fn(state)
            shader.bind()
            if model_view_projection_matrix is not None:
                shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
            if model_view_matrix is not None:
                shader.uniform_float("ModelViewMatrix", model_view_matrix)
            for batch in low_depth_batches:
                if batch is not None:
                    batch.draw(shader)
        state.last_mask_error = ""
        return resources
    except Exception:
        log_mask_error_fn(state, traceback.format_exc())
        return None
    finally:
        if original_viewport is not None and hasattr(gpu.state, "viewport_set"):
            gpu.state.viewport_set(*original_viewport)
        if color_mask_supported:
            gpu.state.color_mask_set(True, True, True, True)
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("NONE")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL")


def render_shell_depth_mask(
    state: OverlayGpuState,
    batches,
    width: int,
    height: int,
    *,
    model_view_projection_matrix=None,
    offset: float = 0.0,
    offset_batches: bool = False,
    depth_test_mode: str = "LESS",
    clear_depth: float = 1.0,
    clear_color_depth: float = 1.0,
    face_culling_mode=None,
    low_depth_mask_dimensions_fn,
    ensure_depth_mask_resources_fn,
    get_depth_mask_shader_fn,
    log_mask_error_fn,
):
    if not batches:
        return None
    color_mask_supported = hasattr(gpu.state, "color_mask_set")
    original_viewport = gpu.state.viewport_get() if hasattr(gpu.state, "viewport_get") else None
    try:
        mask_width, mask_height = low_depth_mask_dimensions_fn(width, height)
        resources = ensure_depth_mask_resources_fn(state, mask_width, mask_height)
        if resources is None:
            return None
        framebuffer = resources.framebuffer
        with framebuffer.bind():
            if hasattr(gpu.state, "viewport_set"):
                gpu.state.viewport_set(0, 0, resources.width, resources.height)
            framebuffer.clear(color=(float(clear_color_depth), 0.0, 0.0, 0.0), depth=float(clear_depth))
            if hasattr(gpu.state, "blend_set"):
                gpu.state.blend_set("NONE")
            if hasattr(gpu.state, "depth_test_set"):
                gpu.state.depth_test_set(depth_test_mode)
            if hasattr(gpu.state, "depth_mask_set"):
                gpu.state.depth_mask_set(True)
            if face_culling_mode is not None and hasattr(gpu.state, "face_culling_set"):
                gpu.state.face_culling_set(face_culling_mode)
            if color_mask_supported:
                gpu.state.color_mask_set(True, True, True, True)
            shader = get_depth_mask_shader_fn(state)
            shader.bind()
            if model_view_projection_matrix is not None:
                shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
            if offset_batches:
                shader.uniform_float("offset", float(offset))
            for batch in batches:
                if batch is not None:
                    batch.draw(shader)
        state.last_mask_error = ""
        return resources
    except Exception:
        log_mask_error_fn(state, traceback.format_exc())
        return None
    finally:
        if original_viewport is not None and hasattr(gpu.state, "viewport_set"):
            gpu.state.viewport_set(*original_viewport)
        if color_mask_supported:
            gpu.state.color_mask_set(True, True, True, True)
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("NONE")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL")
        if hasattr(gpu.state, "face_culling_set"):
            gpu.state.face_culling_set("NONE")


def render_cage_pass_depth_mask(
    state: OverlayGpuState,
    pass_offsets,
    width: int,
    height: int,
    *,
    model_view_projection_matrix=None,
    model_view_matrix=None,
    low_depth_mask_dimensions_fn,
    ensure_depth_mask_resources_fn,
    get_depth_mask_shader_fn,
    get_paint_depth_mask_shader_fn,
    log_mask_error_fn,
):
    """Render the displayed cage into one front-depth mask.

    ``pass_offsets`` contains ``(OverlayPass, resolved_offset)`` pairs, allowing
    per-low offsets and painted cages to share one mask without clearing between
    passes. The high-poly coverage shader consumes this mask directly, so a cage
    slider edit only redraws these low-poly passes.
    """
    if not pass_offsets:
        return None
    color_mask_supported = hasattr(gpu.state, "color_mask_set")
    original_viewport = gpu.state.viewport_get() if hasattr(gpu.state, "viewport_get") else None
    try:
        mask_width, mask_height = low_depth_mask_dimensions_fn(width, height)
        resources = ensure_depth_mask_resources_fn(state, mask_width, mask_height)
        if resources is None:
            return None
        with resources.framebuffer.bind():
            if hasattr(gpu.state, "viewport_set"):
                gpu.state.viewport_set(0, 0, resources.width, resources.height)
            resources.framebuffer.clear(color=(-1.0, 0.0, 0.0, 0.0), depth=1.0)
            if hasattr(gpu.state, "blend_set"):
                gpu.state.blend_set("NONE")
            if hasattr(gpu.state, "depth_test_set"):
                gpu.state.depth_test_set("LESS")
            if hasattr(gpu.state, "depth_mask_set"):
                gpu.state.depth_mask_set(True)
            if hasattr(gpu.state, "face_culling_set"):
                gpu.state.face_culling_set("NONE")
            if color_mask_supported:
                gpu.state.color_mask_set(True, True, True, True)
            for draw_pass, resolved_offset in pass_offsets:
                batch = getattr(draw_pass, "fill_batch", None)
                if batch is None:
                    continue
                if str(getattr(draw_pass, "shader_mode", "") or "") == "offset_paint":
                    paint_texture = getattr(draw_pass, "paint_texture", None)
                    if paint_texture is None:
                        continue
                    shader = get_paint_depth_mask_shader_fn(state)
                    shader.bind()
                    shader.uniform_float(
                        "offset_scale",
                        float(resolved_offset) * float(getattr(draw_pass, "paint_offset_scale", 1.0)),
                    )
                    if hasattr(shader, "uniform_sampler"):
                        shader.uniform_sampler("paintOffsetTexture", paint_texture)
                else:
                    shader = get_depth_mask_shader_fn(state)
                    shader.bind()
                    shader.uniform_float("offset", float(resolved_offset))
                if model_view_projection_matrix is not None:
                    shader.uniform_float("ModelViewProjectionMatrix", model_view_projection_matrix)
                if model_view_matrix is not None:
                    shader.uniform_float("ModelViewMatrix", model_view_matrix)
                batch.draw(shader)
        state.last_mask_error = ""
        return resources
    except Exception:
        log_mask_error_fn(state, traceback.format_exc())
        return None
    finally:
        if original_viewport is not None and hasattr(gpu.state, "viewport_set"):
            gpu.state.viewport_set(*original_viewport)
        if color_mask_supported:
            gpu.state.color_mask_set(True, True, True, True)
        if hasattr(gpu.state, "blend_set"):
            gpu.state.blend_set("NONE")
        if hasattr(gpu.state, "depth_mask_set"):
            gpu.state.depth_mask_set(False)
        if hasattr(gpu.state, "depth_test_set"):
            gpu.state.depth_test_set("LESS_EQUAL")
        if hasattr(gpu.state, "face_culling_set"):
            gpu.state.face_culling_set("NONE")


def _vertex_view(values: array, components: int) -> memoryview:
    return memoryview(values).cast("B").cast("f", (len(values) // components, components))


def paint_values_for(paints, vertex_count: int) -> list[float]:
    """Per-vertex paint multipliers for a paint batch: *paints* when it covers every
    vertex, else 1 everywhere (legacy canvas groups, or buffers that lost them)."""
    if paints is not None and len(paints) == vertex_count:
        return [float(value) for value in paints]
    return [1.0] * vertex_count


def white_paint_texture(state: OverlayGpuState):
    """1x1 white canvas for groups painted with the brush: the shader then displaces by
    the per-vertex layer multiplier alone."""
    texture = state.white_paint_texture
    if texture is None:
        buffer = gpu.types.Buffer("FLOAT", 4, [1.0, 1.0, 1.0, 1.0])
        texture = gpu.types.GPUTexture((1, 1), format="RGBA16F", data=buffer)
        state.white_paint_texture = texture
    return texture


def build_offset_gpu_batch(
    state: OverlayGpuState,
    primitive_type: str,
    positions,
    normals,
    *,
    uvs=None,
    paints=None,
    get_offset_batch_format_fn,
    get_paint_offset_batch_format_fn,
):
    if not isinstance(positions, array) or not isinstance(normals, array):
        return None
    if len(positions) == 0 or len(normals) == 0 or (len(positions) % 3) != 0 or len(positions) != len(normals):
        return None

    vertex_count = len(positions) // 3
    if uvs is None:
        batch_format = get_offset_batch_format_fn(state)
    else:
        if not isinstance(uvs, array) or len(uvs) != vertex_count * 2:
            return None
        batch_format = get_paint_offset_batch_format_fn(state)

    try:
        # attr_fill wants one item per vertex: a flat float array is rejected ("Expected
        # a sequence of size 3, got 9"), an (N, components) view of it is not.
        vertex_buffer = gpu.types.GPUVertBuf(batch_format, vertex_count)
        vertex_buffer.attr_fill("position", _vertex_view(positions, 3))
        vertex_buffer.attr_fill("normal", _vertex_view(normals, 3))
        if uvs is not None:
            vertex_buffer.attr_fill("uv", _vertex_view(uvs, 2))
            vertex_buffer.attr_fill("paint_value", paint_values_for(paints, vertex_count))
        return gpu.types.GPUBatch(type=primitive_type, buf=vertex_buffer)
    except Exception:
        return None
