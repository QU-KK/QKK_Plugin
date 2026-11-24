"""Material IR — IMAGE_SAMPLE + UV/Object/Generated expression ops.

Phase 4: compile Principled channel graphs using file-backed TexImage plus
Mix / Math / Invert / ColorRamp / Constant / Mapping (incl. driven loc/rot/scale) /
TexCoord (UV, Object, Generated) / Noise / Voronoi / Wave / Gradient / Checker /
Brick / HueSat / BrightContrast / Gamma / Combine XYZ / Vector Math / Map Range /
Clamp into a versioned SSA program. Auto selects Native when every contributing
op is verified; otherwise Cycles. 1D/4D procedurals plus Magic/White Noise
currently route to Cycles until native parity is proven.
"""
from __future__ import annotations

import contextlib
import math
from dataclasses import dataclass, field
from typing import Any

from . import constants
from . import material_ir_tables

MATERIAL_IR_VERSION = 1
#: Program version for a program that uses sampler-side image addressing: a UDIM
#: tile table, a per-material slot table, an ATTR_TRIANGLE_SLOT fetch, or a
#: SAMPLE_IMAGE carrying its own `extension`. Only those programs carry it, so every
#: program that uses none of them keeps version 1 and a byte-identical wire payload
#: (the program dict is the bake cache key).
MATERIAL_IR_VERSION_SAMPLER_TABLES = 2
MATERIAL_IR_KIND_NONE = ""
MATERIAL_IR_KIND_IMAGE_SAMPLE = "IMAGE_SAMPLE"
MATERIAL_IR_KIND_EXPRESSION_UV = "EXPRESSION_UV"

OPCODE_SAMPLE_IMAGE = "SAMPLE_IMAGE"
OPCODE_ATTR_UV = "ATTR_UV"
OPCODE_ATTR_OBJECT = "ATTR_OBJECT"
OPCODE_ATTR_GENERATED = "ATTR_GENERATED"
OPCODE_CONSTANT = "CONSTANT"
OPCODE_INVERT = "INVERT"
OPCODE_MIX = "MIX"
OPCODE_MATH = "MATH"
OPCODE_COLOR_RAMP = "COLOR_RAMP"
OPCODE_SWIZZLE = "SWIZZLE"
OPCODE_MAPPING = "MAPPING"
OPCODE_NOISE_TEXTURE = "NOISE_TEXTURE"
OPCODE_VORONOI_TEXTURE = "VORONOI_TEXTURE"
OPCODE_WHITE_NOISE_TEXTURE = "WHITE_NOISE_TEXTURE"
OPCODE_MAGIC_TEXTURE = "MAGIC_TEXTURE"
OPCODE_WAVE_TEXTURE = "WAVE_TEXTURE"
OPCODE_GABOR_TEXTURE = "GABOR_TEXTURE"
OPCODE_TANGENT_TO_WORLD = "TANGENT_TO_WORLD"
OPCODE_GRADIENT_TEXTURE = "GRADIENT_TEXTURE"
OPCODE_CHECKER_TEXTURE = "CHECKER_TEXTURE"
OPCODE_BRICK_TEXTURE = "BRICK_TEXTURE"
OPCODE_HUE_SAT = "HUE_SAT"
#: RGB <-> HSV / HSL. `mode` is the direction: RGB_TO_HSV / HSV_TO_RGB /
#: RGB_TO_HSL / HSL_TO_RGB. Alpha rides through untouched.
OPCODE_COLOR_SPACE = "COLOR_SPACE"

#: Image Texture interpolations that select the backend's bicubic tap. Cycles takes
#: the same branch for both (kernel_image_interp, kernel/device/gpu/image.h).
_BICUBIC_INTERPOLATIONS: frozenset[str] = frozenset({"CUBIC", "SMART"})
OPCODE_BRIGHTCONTRAST = "BRIGHTCONTRAST"
OPCODE_GAMMA = "GAMMA"
OPCODE_COMBINE_XYZ = "COMBINE_XYZ"
OPCODE_VECTOR_MATH = "VECTOR_MATH"
OPCODE_MAP_RANGE = "MAP_RANGE"
OPCODE_CLAMP = "CLAMP"
OPCODE_CURVE_MAP = "CURVE_MAP"
#: Geometry node inputs taken from the projection hit.
OPCODE_ATTR_POSITION = "ATTR_POSITION"      # world-space hit position
OPCODE_ATTR_NORMAL = "ATTR_NORMAL"          # world-space shading normal
OPCODE_ATTR_BARYCENTRIC = "ATTR_BARYCENTRIC"  # raw high-triangle barycentric (x on v0)
OPCODE_ATTR_TRUE_NORMAL = "ATTR_TRUE_NORMAL"  # geometric (face) normal, world space
OPCODE_ATTR_CORNER_FLOAT = "ATTR_CORNER_FLOAT"  # sidecar per-corner float, bary-blended
#: Per-TRIANGLE material slot index, read from a byte sidecar at the hit triangle's
#: export-order index: regs[dst] = (s, s, s, 1). Feeds the `slot` register of a
#: slot-table SAMPLE_IMAGE (see _merge_slot_indexed_programs).
OPCODE_ATTR_TRIANGLE_SLOT = "ATTR_TRIANGLE_SLOT"
OPCODE_VECTOR_ROTATE = "VECTOR_ROTATE"
OPCODE_VECTOR_TRANSFORM = "VECTOR_TRANSFORM"
#: Secondary-ray opcode: the Cycles Ambient Occlusion *node* estimator
#: (kMirOpAo = 37 in backend/shaders/material_ir.slang). This is NOT the AO map
#: -- it is an unweighted binary visibility fraction with no attenuation, spread
#: cone or floor (docs/SECONDARY_RAY_NODES_PLAN.md section 1.4). It executes ONLY in the
#: MATERIAL_ONLY + DXR_INLINE shader permutation; everywhere else the backend
#: writes the neutral fully-unoccluded 1.0, so emission must be route-gated
#: (see GPU_RAY_OPCODES / gpu_support_reason(allow_ray_ops=...)).
OPCODE_AO = "AO"
#: Secondary-ray opcode: the Cycles Bevel node estimator (kMirOpBevel = 38).
#: Returns a WORLD-SPACE unit normal -- the same space/convention as
#: OPCODE_ATTR_NORMAL, not tangent space and not 0..1 encoded
#: (docs/SECONDARY_RAY_NODES_PLAN.md section 11.2). Same route policy as AO, but its
#: neutral outside the MATERIAL_ONLY permutation is the SHADING NORMAL rather
#: than white -- white is meaningless for a normal (section 11.5).
OPCODE_BEVEL = "BEVEL"
#: Secondary-ray opcode: the Cycles Raycast node (kMirOpRaycast = 39, Blender
#: 5.1+). ONE deterministic closest-hit trace per node, writing TWO registers --
#: ``dst = float4(hit_position.xyz, is_hit)`` and
#: ``dst2 = float4(hit_normal.xyz, hit_distance)`` -- so all four v1 outputs are
#: pure swizzles of an existing register (section 12.2). Its neutral is its MISS,
#: which is the only neutral of the three that is not a constant: Hit Distance
#: carries the input Length through (section 12.3).
OPCODE_RAYCAST = "RAYCAST"

#: Vector Rotate modes, shared with the packer and material_ir.slang.
VECTOR_ROTATE_MODES: tuple[str, ...] = (
    "AXIS_ANGLE",
    "X_AXIS",
    "Y_AXIS",
    "Z_AXIS",
    "EULER_XYZ",
)

#: Samples per curve channel. Matches Blender's CM_TABLE and Cycles'
#: RAMP_TABLE_SIZE, so a table lookup is what the reference renderer does too
#: rather than an approximation of it.
CURVE_MAP_TABLE_SIZE: int = 256

SUPPORTED_OPCODES: frozenset[str] = frozenset(
    {
        OPCODE_SAMPLE_IMAGE,
        OPCODE_ATTR_UV,
        OPCODE_ATTR_OBJECT,
        OPCODE_ATTR_GENERATED,
        OPCODE_CONSTANT,
        OPCODE_INVERT,
        OPCODE_MIX,
        OPCODE_MATH,
        OPCODE_COLOR_RAMP,
        OPCODE_SWIZZLE,
        OPCODE_MAPPING,
        OPCODE_NOISE_TEXTURE,
        OPCODE_VORONOI_TEXTURE,
        OPCODE_WHITE_NOISE_TEXTURE,
        OPCODE_MAGIC_TEXTURE,
        OPCODE_WAVE_TEXTURE,
        OPCODE_GABOR_TEXTURE,
        OPCODE_TANGENT_TO_WORLD,
        OPCODE_GRADIENT_TEXTURE,
        OPCODE_CHECKER_TEXTURE,
        OPCODE_BRICK_TEXTURE,
        OPCODE_HUE_SAT,
        OPCODE_COLOR_SPACE,
        OPCODE_BRIGHTCONTRAST,
        OPCODE_GAMMA,
        OPCODE_COMBINE_XYZ,
        OPCODE_VECTOR_MATH,
        OPCODE_MAP_RANGE,
        OPCODE_CLAMP,
        OPCODE_CURVE_MAP,
        OPCODE_ATTR_POSITION,
        OPCODE_ATTR_NORMAL,
        OPCODE_ATTR_BARYCENTRIC,
        OPCODE_ATTR_TRUE_NORMAL,
        OPCODE_ATTR_CORNER_FLOAT,
        OPCODE_ATTR_TRIANGLE_SLOT,
        OPCODE_VECTOR_ROTATE,
        OPCODE_VECTOR_TRANSFORM,
        OPCODE_AO,
        OPCODE_BEVEL,
        OPCODE_RAYCAST,
    }
)

#: Opcodes that trace scene rays. The backend compiles them only into the
#: MATERIAL_ONLY + DXR_INLINE permutation of projection_shading; the megakernel,
#: the AO-only kernel and the software-BVH build all substitute the opcode's
#: documented neutral (AO -> 1.0 fully unoccluded, BEVEL -> the shading normal;
#: docs/SECONDARY_RAY_NODES_PLAN.md sections 10.5 and 11.5). A program containing one
#: of these is therefore only correct on that single route.
#:
#: Membership here is all a new ray opcode needs: the route rejection in
#: gpu_support_reason, the program_uses_ray_opcodes route predicate and the
#: per-program ray budget all read this set and carry no opcode list of their own
#: -- the exact mirror of the backend's material_ir_program_uses_ray_ops(), which
#: is likewise the single membership test behind all three of its guards.
GPU_RAY_OPCODES: frozenset[str] = frozenset({OPCODE_AO, OPCODE_BEVEL, OPCODE_RAYCAST})

#: Backend clamp range for a ray opcode's sample count
#: (kMirMinRayNodeSamples / kMirMaxRayNodeSamples in material_ir.slang, mirrored
#: in backend_material_ir_gpu.cpp). Cycles stores samples in a uint8 (<= 255);
#: anything above the cap only changes variance, never the estimator's
#: expectation, and the RNG already differs from Cycles' path_branched_rng_2D
#: (docs/SECONDARY_RAY_NODES_PLAN.md section 10.4 item 6), so clamping is safe.
RAY_NODE_MIN_SAMPLES: int = 1
RAY_NODE_MAX_SAMPLES: int = 128

#: Traversals per texel a single RAYCAST op costs. The node is deterministic --
#: one closest-hit ray, no sampling, no RNG -- so it carries no `samples` field
#: at all and the [1, 128] clamp above does not apply to it
#: (docs/SECONDARY_RAY_NODES_PLAN.md sections 12.2 and 12.10.8). Counting it as 1
#: is the honest number and keeps a Raycast-only graph well inside
#: GPU_MAX_RAY_SAMPLES; the 256-op program budget binds such a graph long before
#: the ray budget does, since each node costs an op plus its output swizzles.
RAYCAST_RAY_SAMPLES: int = 1

#: Per-program ray budget (docs/SECONDARY_RAY_NODES_PLAN.md section 3.3.2, which
#: proposes 128). Every ray sample is one full TLAS traversal from an arbitrary
#: shading point — the same unit cost as an AO-map ray — so a graph with several
#: AO nodes multiplies a material bake's cost without any single node looking
#: expensive. Summing `samples` across the program and refusing above the cap
#: keeps the worst case at one saturated AO op (the shipped per-op cap is 128,
#: not the plan's proposed 64), which is the most a material pass can cost before
#: it stops being "essentially free" and becomes AO-map-class. Over-budget
#: programs route to Cycles, exactly like the op and register budgets.
GPU_MAX_RAY_SAMPLES: int = 128

SUPPORTED_VECTOR_MATH_OPS: frozenset[str] = frozenset(
    {
        "ADD",
        "SUBTRACT",
        "MULTIPLY",
        "DIVIDE",
        "MULTIPLY_ADD",
        "CROSS_PRODUCT",
        "CROSS",
        "DOT_PRODUCT",
        "DOT",
        "NORMALIZE",
        "LENGTH",
        "SCALE",
        "ABSOLUTE",
        "MINIMUM",
        "MAXIMUM",
        "REFLECT",
        "REFRACT",
        "DISTANCE",
        "FLOOR",
        "CEIL",
        "FRACTION",
        "MODULO",
        "WRAP",
        "SNAP",
        "PROJECT",
        "FACEFORWARD",
        "POWER",
        "SIGN",
        "ROUND",
        "SINE",
        "COSINE",
        "TANGENT",
    }
)

#: Vector Math operations whose second socket is a scalar, not a vector.
VECTOR_MATH_SCALAR_SECOND_OPS: frozenset[str] = frozenset({"SCALE"})

#: Vector Math operations that read a third vector socket (Blender socket index 2).
VECTOR_MATH_TERNARY_OPS: frozenset[str] = frozenset(
    {"MULTIPLY_ADD", "FACEFORWARD", "WRAP"}
)

#: Vector Math operations that ignore every socket past the first.
VECTOR_MATH_UNARY_OPS: frozenset[str] = frozenset(
    {
        "NORMALIZE",
        "LENGTH",
        "ABSOLUTE",
        "FLOOR",
        "CEIL",
        "FRACTION",
        "SIGN",
        "ROUND",
        "SINE",
        "COSINE",
        "TANGENT",
    }
)

SUPPORTED_MIX_BLEND_TYPES: frozenset[str] = frozenset(
    {
        "MIX",
        "MULTIPLY",
        "ADD",
        "SUBTRACT",
        "SCREEN",
        "OVERLAY",
        "DIFFERENCE",
        "DARKEN",
        "LIGHTEN",
        "DODGE",
        "BURN",
        "SOFT_LIGHT",
        "LINEAR_LIGHT",
        "EXCLUSION",
        "DIVIDE",
        "HUE",
        "SATURATION",
        "COLOR",
        "VALUE",
    }
)

SUPPORTED_MATH_OPS: frozenset[str] = frozenset(
    {
        "MULTIPLY",
        "ADD",
        "SUBTRACT",
        "MINIMUM",
        "MAXIMUM",
        "LESS_THAN",
        "GREATER_THAN",
        "DIVIDE",
        "POWER",
        "ABSOLUTE",
        "SQRT",
        "FLOOR",
        "CEIL",
        "FRACT",
        "MODULO",
        "SINE",
        "COSINE",
        "TANGENT",
        "ARCTANGENT",
        "ARCSINE",
        "ARCCOSINE",
        "ROUND",
        "SIGN",
        "CLAMP",
        "MULTIPLY_ADD",
        "LOGARITHM",
        "INVERSE_SQRT",
        "EXPONENT",
        "COMPARE",
        "SMOOTH_MIN",
        "SMOOTH_MAX",
        "TRUNC",
        "FLOORED_MODULO",
        "WRAP",
        "SNAP",
        "PINGPONG",
        "ARCTAN2",
        "SINH",
        "COSH",
        "TANH",
        "RADIANS",
        "DEGREES",
    }
)

#: Math operations that ignore Value2 / Value3.
MATH_UNARY_OPS: frozenset[str] = frozenset(
    {
        "ABSOLUTE",
        "SQRT",
        "INVERSE_SQRT",
        "EXPONENT",
        "FLOOR",
        "CEIL",
        "FRACT",
        "TRUNC",
        "SINE",
        "COSINE",
        "TANGENT",
        "ARCTANGENT",
        "ARCSINE",
        "ARCCOSINE",
        "SINH",
        "COSH",
        "TANH",
        "ROUND",
        "SIGN",
        "CLAMP",
        "RADIANS",
        "DEGREES",
    }
)

#: Math operations that read Value3 (Blender socket index 2).
MATH_TERNARY_OPS: frozenset[str] = frozenset(
    {"MULTIPLY_ADD", "COMPARE", "SMOOTH_MIN", "SMOOTH_MAX", "WRAP"}
)

GPU_SUPPORTED_MIX_BLEND_TYPES: frozenset[str] = SUPPORTED_MIX_BLEND_TYPES

GPU_SUPPORTED_MATH_OPS: frozenset[str] = SUPPORTED_MATH_OPS

GPU_SUPPORTED_VECTOR_MATH_OPS: frozenset[str] = SUPPORTED_VECTOR_MATH_OPS
SUPPORTED_COLOR_RAMP_MODES: frozenset[str] = frozenset(
    {"LINEAR", "CONSTANT", "EASE", "CARDINAL", "B_SPLINE"}
)
GPU_SUPPORTED_COLOR_RAMP_MODES: frozenset[str] = SUPPORTED_COLOR_RAMP_MODES

#: Colour Ramp stops the GPU stop table can hold (Blender's own maximum).
GPU_MAX_COLOR_RAMP_STOPS: int = 32

#: Samples a single CURVE_MAP table may carry on the GPU. Curve nodes use
#: CURVE_MAP_TABLE_SIZE; Blackbody needs the larger budget.
GPU_MAX_CURVE_SAMPLES: int = 512
#: Wave Texture only. Blender has no 1D/4D Wave, so this stays 2D/3D and is what
#: ``capabilities_payload`` reports as ``gpu_procedural_dimensions`` (the backend
#: mirrors the same literal pair).
GPU_SUPPORTED_PROCEDURAL_DIMS: frozenset[str] = frozenset({"2D", "3D"})

#: Noise Texture covers every Blender dimension. 1D reads the W input as its only
#: coordinate (the Vector socket is ignored, exactly as in Cycles' noise_texture_1d)
#: and 4D appends W to the Vector.
GPU_SUPPORTED_NOISE_DIMS: frozenset[str] = frozenset({"1D", "2D", "3D", "4D"})

#: Voronoi covers all four real fields (each dimension has its own hash family and
#: neighbourhood; running the 3D field at z=0 is a different function). 1D uses the
#: scalar float hash and fabs() for every metric; 4D uses the PCG4D hash.
GPU_SUPPORTED_VORONOI_DIMS: frozenset[str] = frozenset({"1D", "2D", "3D", "4D", ""})
#: Every metric. Cycles ranks candidates by a monotonic *bound* and only converts
#: the winner with the real metric (voronoi_distance_bound in
#: intern/cycles/kernel/svm/voronoi.h); ranking by the metric itself picked a
#: different feature point over whole regions.
GPU_SUPPORTED_VORONOI_METRICS: frozenset[str] = frozenset(
    {"EUCLIDEAN", "DISTANCE", "MANHATTAN", "CHEBYCHEV", "CHEBYSHEV", "MINKOWSKI", ""}
)
GPU_SUPPORTED_VORONOI_FEATURES: frozenset[str] = frozenset(
    {"F1", "F2", "SMOOTH_F1", "DISTANCE_TO_EDGE", "N_SPHERE_RADIUS", ""}
)
GPU_SUPPORTED_VORONOI_OUTPUTS: frozenset[str] = frozenset(
    {"DISTANCE", "COLOR", "POSITION", "W", ""}
)
GPU_BLOCKED_PARITY_OPCODES: frozenset[str] = frozenset()

#: Hard limits of the GPU interpreter (kMirMaxRegs / kMirMaxOps in
#: backend/shaders/material_ir.slang). The shader clamps out-of-range indices
#: instead of failing, so a program past either limit must never claim GPU.
GPU_MAX_REGISTERS: int = 64
GPU_MAX_OPS: int = 256
#: Resource slots per program on the GPU (kMirMaxResources). A UDIM tile table or a
#: slot table counts as ONE resource however many images it holds.
GPU_MAX_RESOURCES: int = 8

CHANNEL_TO_PRINCIPLED = {
    constants.MATERIAL_CHANNEL_ALBEDO: "Base Color",
    constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
    constants.MATERIAL_CHANNEL_METALNESS: "Metallic",
    constants.MATERIAL_CHANNEL_EMISSION: "Emission Color",
    constants.MATERIAL_CHANNEL_OPACITY: "Alpha",
    constants.MATERIAL_CHANNEL_SPECULAR: "Specular IOR Level",
    constants.MATERIAL_CHANNEL_TRANSMISSION: "Transmission Weight",
    constants.MATERIAL_CHANNEL_NORMAL: "Normal",
}

#: Non-Principled closures Fyr flattens to PBR channels, as
#: ``{node.type: {channel: socket name or constant}}``.
#:
#: A channel absent from an entry falls through to `_shader_channel_neutral`,
#: which is already the "this branch contributes nothing" answer used by Mix and
#: Add Shader, so only the channels a closure actually carries need listing.
#: Opacity is omitted throughout because neutral is already 1.0, and Normal is
#: handled generically for every closure that has a Normal input.
#:
#: The two constants encode what the closure *is*, because a PBR set has nowhere
#: else to record it: Metallic and Glossy are conductors, so Metalness is 1.0;
#: Glass, Refraction and Translucent transmit, so Transmission is 1.0.
#:
#: BSDF_DIFFUSE is deliberately absent and keeps its own branch below. Its
#: "Roughness" is the Oren-Nayar term, not a specular roughness, so feeding it to
#: the Roughness channel would change what that already-working path bakes.
_CLOSURE_CHANNEL_SOURCES: dict[str, dict[str, object]] = {
    "BSDF_METALLIC": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Base Color",
        constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
        constants.MATERIAL_CHANNEL_METALNESS: 1.0,
    },
    "BSDF_GLOSSY": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
        constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
        constants.MATERIAL_CHANNEL_METALNESS: 1.0,
    },
    "BSDF_GLASS": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
        constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
        constants.MATERIAL_CHANNEL_TRANSMISSION: 1.0,
    },
    "BSDF_REFRACTION": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
        constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
        constants.MATERIAL_CHANNEL_TRANSMISSION: 1.0,
    },
    "BSDF_TRANSLUCENT": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
        constants.MATERIAL_CHANNEL_TRANSMISSION: 1.0,
    },
    "BSDF_SHEEN": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
        constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
    },
    "BSDF_TOON": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
    },
    "SUBSURFACE_SCATTERING": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
        constants.MATERIAL_CHANNEL_ROUGHNESS: "Roughness",
    },
    # Hair carries a colour and nothing else a PBR set can hold. RoughnessU and
    # RoughnessV are the longitudinal and azimuthal widths of a fibre highlight,
    # not a microfacet roughness -- the same reason BSDF_DIFFUSE's Oren-Nayar
    # "Roughness" is kept out of the Roughness channel above.
    "BSDF_HAIR": {
        constants.MATERIAL_CHANNEL_ALBEDO: "Color",
    },
}

#: Volume closures. They have no surface, so wiring one into Material Output's
#: Surface socket is degenerate; see the `_VOLUME_CLOSURE_TYPES` branch in
#: `_compile_shader_closure` for what that bakes.
_VOLUME_CLOSURE_TYPES: frozenset[str] = frozenset(
    {
        "VOLUME_ABSORPTION",
        "VOLUME_SCATTER",
        "PRINCIPLED_VOLUME",
        "VOLUME_COEFFICIENTS",
    }
)

#: Light Path outputs as a bake sees them (Cycles bake ray: camera flag set, hit at t=1).
_LIGHT_PATH_BAKE_CONSTANTS: dict[str, float] = {
    "Is Camera Ray": 1.0,
    "Is Shadow Ray": 0.0,
    "Is Diffuse Ray": 0.0,
    "Is Glossy Ray": 0.0,
    "Is Singular Ray": 0.0,
    "Is Reflection Ray": 0.0,
    "Is Transmission Ray": 0.0,
    "Is Volume Scatter Ray": 0.0,
    "Ray Length": 1.0,
    "Ray Depth": 0.0,
    "Diffuse Depth": 0.0,
    "Glossy Depth": 0.0,
    "Transparent Depth": 0.0,
    "Transmission Depth": 0.0,
}

_MAX_OPS = 256
_MAX_RESOURCES = 32
_MAX_REGS = 512


class MaterialIrRefusal(ValueError):
    """A compile refusal that knows which node it came from.

    ``str()`` is the plain reason, byte-for-byte what the bare ``ValueError``
    used to carry, so every existing caller (and every test asserting on
    ``fallback_reason``) is unaffected. The extra attributes exist purely so UI
    can point at the offending node.

    ``node_path`` runs outermost-first: element 0 is the node reached directly
    from the channel socket (a Group node, when the refusal is nested inside a
    node group), and the last element is the node that actually refused.
    """

    def __init__(
        self,
        reason: str,
        *,
        node_name: str = "",
        node_type: str = "",
        node_path: tuple[str, ...] = (),
        channel: str = "",
    ) -> None:
        super().__init__(reason)
        self.reason = str(reason)
        self.node_name = str(node_name or "")
        self.node_type = str(node_type or "")
        self.node_path = tuple(node_path or ())
        self.channel = str(channel or "")


@dataclass(slots=True)
class MaterialIrProgram:
    """Compact native program for one material channel output."""

    version: int = MATERIAL_IR_VERSION
    kind: str = MATERIAL_IR_KIND_NONE
    opcodes: list[str] = field(default_factory=list)
    channel: str = ""
    image_path: str = ""
    fallback_reason: str = ""
    native: bool = False
    # SSA program payload (EXPRESSION_UV / IMAGE_SAMPLE). Empty for Cycles fallback.
    result_reg: int = 0
    resources: list[dict[str, Any]] = field(default_factory=list)
    ops: list[dict[str, Any]] = field(default_factory=list)
    # Which node produced `fallback_reason`, when a node was in scope. UI-only:
    # deliberately absent from to_dict()/wire_payload() so the job format and the
    # backend contract are untouched.
    fallback_node_name: str = ""
    fallback_node_type: str = ""
    fallback_node_path: tuple[str, ...] = ()
    # Material names, in the order the merged program's branches expect, when this
    # program carries a CORNER_ATTR:MATSLOT selector. The exporter needs it to write
    # the per-corner index sidecar; the backend never sees it, so like the
    # fallback_node_* fields it stays out of to_dict()/wire_payload().
    slot_materials: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "kind": str(self.kind or ""),
            "opcodes": list(self.opcodes),
            "channel": str(self.channel or ""),
            "image_path": str(self.image_path or ""),
            "fallback_reason": str(self.fallback_reason or ""),
            "native": bool(self.native),
            "result_reg": int(self.result_reg),
            "resources": [dict(item) for item in self.resources],
            "ops": [dict(item) for item in self.ops],
        }

    def wire_payload(self) -> dict[str, Any]:
        """Subset shipped on BakeMapConfig.material_ir_program."""
        return {
            "version": int(self.version),
            "kind": str(self.kind or ""),
            "result_reg": int(self.result_reg),
            "resources": [dict(item) for item in self.resources],
            "ops": [dict(item) for item in self.ops],
        }


def _cycles_program(channel: str, reason: str, refusal: BaseException | None = None) -> MaterialIrProgram:
    return MaterialIrProgram(
        version=MATERIAL_IR_VERSION,
        kind=MATERIAL_IR_KIND_NONE,
        channel=str(channel or "").strip().upper(),
        fallback_reason=str(reason or "Unsupported material expression"),
        native=False,
        fallback_node_name=str(getattr(refusal, "node_name", "") or ""),
        fallback_node_type=str(getattr(refusal, "node_type", "") or ""),
        fallback_node_path=tuple(getattr(refusal, "node_path", ()) or ()),
    )


def cycles_fallback_program(channel: str, reason: str) -> MaterialIrProgram:
    """Public constructor for "this channel bakes through Cycles, and here is why".

    The exporter needs this to turn an escaped compiler exception into an ordinary
    refusal instead of letting it abort the bake.
    """
    return _cycles_program(channel, reason)


def _node_cache_id(node) -> int:
    """Stable identity for bpy nodes/images (id() is wrapper-address and collides)."""
    if node is None:
        return 0
    as_pointer = getattr(node, "as_pointer", None)
    if callable(as_pointer):
        try:
            return int(as_pointer())
        except Exception:
            pass
    return id(node)


def _socket_default_rgba(socket) -> tuple[float, float, float, float]:
    try:
        value = getattr(socket, "default_value", None)
        if value is None:
            return (0.0, 0.0, 0.0, 1.0)
        if isinstance(value, (int, float)):
            v = float(value)
            return (v, v, v, 1.0)
        seq = tuple(float(v) for v in value)
        if len(seq) >= 4:
            return (seq[0], seq[1], seq[2], seq[3])
        if len(seq) == 3:
            return (seq[0], seq[1], seq[2], 1.0)
        if len(seq) == 1:
            return (seq[0], seq[0], seq[0], 1.0)
    except Exception:
        pass
    return (0.0, 0.0, 0.0, 1.0)


def _int_or(value, fallback: int) -> int:
    """Read a node's integer property, tolerating None/garbage from a fake node."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _luminance(rgba: tuple[float, float, float, float]) -> float:
    return 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]


#: Resource-channel prefix for per-corner attribute sidecars. The compiler cannot
#: know the mesh, so it appends a resource tagged CORNER_ATTR:<NAME> and export
#: resolves it: compute the arrays on the group's high objects (original Blender
#: topology, which the exported mesh cannot reproduce -- UV seams split vertices,
#: changing adjacency and island count), pack each float32 bit-exactly into the
#: RGBA8 bytes of a sidecar PNG (texel index = high_triangle_index * 3 + corner),
#: and ship it down the EXISTING resource pipeline into the texel buffer.
CORNER_ATTR_CHANNEL_PREFIX = "CORNER_ATTR:"
CORNER_ATTR_POINTINESS = "CORNER_ATTR:POINTINESS"
CORNER_ATTR_ISLAND_RANDOM = "CORNER_ATTR:ISLAND_RANDOM"
#: Colour-attribute sidecars. One resource per component, because a sidecar texel
#: carries exactly one bit-exact float32; a colour is read as three or four fetches
#: recombined in the program. Tag shape: CORNER_ATTR:COLOR:<component>:<layer name>.
CORNER_ATTR_COLOR_PREFIX = "CORNER_ATTR:COLOR:"


def corner_color_channel_tag(layer_name: str, component: int) -> str:
    return f"{CORNER_ATTR_COLOR_PREFIX}{int(component)}:{str(layer_name or '')}"


def parse_corner_color_channel_tag(channel_tag: str):
    """(layer name, component) for a colour sidecar tag, or None."""
    text = str(channel_tag or "")
    if not text.startswith(CORNER_ATTR_COLOR_PREFIX):
        return None
    remainder = text[len(CORNER_ATTR_COLOR_PREFIX):]
    component, separator, layer_name = remainder.partition(":")
    if not separator:
        return None
    try:
        return layer_name, int(component)
    except ValueError:
        return None


#: A named scalar FLOAT geometry attribute, the shape a painted or geometry-nodes
#: mask takes. One sidecar carries it where a colour needs three, and it rides the
#: same per-corner barycentric fetch. Tag shape: CORNER_ATTR:FLOAT:<attribute name>.
CORNER_ATTR_FLOAT_PREFIX = "CORNER_ATTR:FLOAT:"


def corner_float_attr_tag(name: str) -> str:
    return f"{CORNER_ATTR_FLOAT_PREFIX}{str(name or '')}"


def parse_corner_float_attr_tag(channel_tag: str):
    """Attribute name for a scalar float sidecar tag, or None."""
    text = str(channel_tag or "")
    if not text.startswith(CORNER_ATTR_FLOAT_PREFIX):
        return None
    name = text[len(CORNER_ATTR_FLOAT_PREFIX):]
    return name or None


#: Per-corner material index for a high poly carrying several materials. Every
#: corner of a triangle holds the same index, so the barycentric blend the sidecar
#: fetch already does is exact everywhere inside the triangle -- unlike the
#: UV-space detail mask, which is bounded by one texel at a material boundary and
#: caps out at 400k triangles. The value is the material's position in the
#: program's own `slot_materials` order, stored bit-exactly as a float32.
CORNER_ATTR_MATERIAL_SLOT = "CORNER_ATTR:MATSLOT"

#: How many materials one merged program will carry. Every branch is evaluated at
#: every hit (the IR is straight-line, there is no jump), so shading cost grows
#: linearly and the op budget is spent N times over. Two or three materials on a
#: high poly is the common case this exists for; a dozen wants a different design.
MAX_MERGED_MATERIALS = 4

#: Resource-channel prefix for per-TRIANGLE byte sidecars (one texel per triangle,
#: indexed linearly by the hit triangle's export-order index, R = the value).
TRIANGLE_ATTR_CHANNEL_PREFIX = "TRIANGLE_ATTR:"
#: The per-triangle material slot a slot-table program selects its images with.
#: Written with R=G=B=slot and A=255 so the backend packs it at one byte/triangle.
TRIANGLE_ATTR_MATERIAL_SLOT = "TRIANGLE_ATTR:MATSLOT"

#: How many materials one slot-table program can index. The slot is one byte in the
#: sidecar. Unlike MAX_MERGED_MATERIALS this costs nothing per material at shading
#: time: every material runs the SAME ops and only the image a tap reads changes.
MAX_SLOT_TABLE_MATERIALS = 255

#: What a sampler-addressed tap returns for a UV outside every UDIM tile the table
#: carries, or for an empty slot: Cycles' TEX_IMAGE_MISSING colour (magenta,
#: alpha 1). An Image Texture node that exposes "Missing" / "Missing Alpha" inputs
#: (Blender 5.x) overrides it per resource.
IMAGE_MISSING_RGBA: tuple[float, float, float, float] = (1.0, 0.0, 1.0, 1.0)

#: Addressing modes and filters the backend sampler applies itself when a
#: SAMPLE_IMAGE carries `extension` / `mode` (sampler-addressed resources only).
SAMPLER_EXTENSIONS: frozenset[str] = frozenset({"REPEAT", "EXTEND", "CLIP", "MIRROR"})
SAMPLER_INTERPOLATIONS: frozenset[str] = frozenset({"LINEAR", "CLOSEST", "CUBIC", "SMART"})

#: Non-active UV set sidecars. ATTR_UV is a single opcode carrying no layer
#: identity -- it means "the interpolated UV of this hit", i.e. the active layer --
#: so a UV Map node naming a second set had nowhere to put the name and used to
#: bake the base layout under a "Bakes natively" tick. A UV layer is a per-corner
#: float pair interpolated barycentrically, which is structurally the same thing a
#: colour attribute is, so it rides the same sidecar: one resource per component,
#: recombined with COMBINE_XYZ. Tag shape: CORNER_ATTR:UV:<component>:<layer name>.
CORNER_ATTR_UV_PREFIX = "CORNER_ATTR:UV:"


def corner_uv_channel_tag(layer_name: str, component: int) -> str:
    return f"{CORNER_ATTR_UV_PREFIX}{int(component)}:{str(layer_name or '')}"


#: MikkTSpace tangent frame for a NAMED UV layer, per corner. A Normal Map node's
#: `uv_map` selects which layer the frame comes from, and that frame is not derivable
#: from the UVs at shading time -- MikkTSpace is a whole-mesh solve with its own
#: splitting rules -- so it rides the same sidecar the UV values do. Four components:
#: tangent xyz (OBJECT space) and the bitangent sign Cycles orients B with.
#: Tag shape: CORNER_ATTR:TANGENT:<component>:<layer name>.
CORNER_ATTR_TANGENT_PREFIX = "CORNER_ATTR:TANGENT:"


def corner_tangent_channel_tag(layer_name: str, component: int) -> str:
    return f"{CORNER_ATTR_TANGENT_PREFIX}{int(component)}:{str(layer_name or '')}"


def parse_corner_tangent_channel_tag(channel_tag: str):
    """(layer name, component) for a tangent sidecar tag, or None."""
    text = str(channel_tag or "")
    if not text.startswith(CORNER_ATTR_TANGENT_PREFIX):
        return None
    remainder = text[len(CORNER_ATTR_TANGENT_PREFIX):]
    component, separator, layer_name = remainder.partition(":")
    if not separator:
        return None
    try:
        return layer_name, int(component)
    except ValueError:
        return None


def parse_corner_uv_channel_tag(channel_tag: str):
    """(layer name, component) for a UV sidecar tag, or None."""
    text = str(channel_tag or "")
    if not text.startswith(CORNER_ATTR_UV_PREFIX):
        return None
    remainder = text[len(CORNER_ATTR_UV_PREFIX):]
    component, separator, layer_name = remainder.partition(":")
    if not separator:
        return None
    try:
        return layer_name, int(component)
    except ValueError:
        return None

#: TexCoord outputs that depend on where the camera is, which a bake has no
#: notion of. Refused by design rather than unimplemented -- the coverage audit
#: reads the "view-dependent" wording to keep them out of the denominator.
_VIEW_DEPENDENT_TEXCOORD_OUTPUTS = frozenset({"Camera", "Window", "Reflection"})


def roundness_is_zero_socket(node) -> bool:
    """Whether a node's Roundness input is an unlinked literal zero.

    Radial Tiling's rounded parameter field lives in calculate_out_variables, which
    is not ported; the sharp (roundness 0) case has closed forms. A linked socket is
    unknown at compile time and counts as non-zero.
    """
    socket = node.inputs.get("Roundness") if hasattr(node, "inputs") else None
    if socket is None or bool(getattr(socket, "is_linked", False)):
        return False
    try:
        return abs(float(getattr(socket, "default_value", 0.0) or 0.0)) <= 1e-9
    except (TypeError, ValueError):
        return False


#: Floor applied to every denominator and sqrt argument inside the branchless
#: Radial Tiling region blends. Both arms of a region select are evaluated, so a
#: quantity that is only well defined inside its own region would otherwise put
#: inf/NaN into the discarded arm — and NaN * 0 is NaN, which survives the
#: MULTIPLY_ADD blend and poisons the taken arm. Small enough that it never
#: engages on a value the taken arm produces: the smallest live denominator is
#: roundness * segment_divider_A_bevel_start, order 1e-3 at usable settings.
_RADIAL_TILING_EPS = 1e-12


def _radial_tiling_socket_constant(socket):
    """Value of an unlinked scalar socket, or None when it is linked/undecidable."""
    if socket is None or bool(getattr(socket, "is_linked", False)):
        return None
    value = getattr(socket, "default_value", None)
    if value is None or isinstance(value, (str, bytes)):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _radial_tiling_fold(sides: float, roundness: float):
    """Every Radial Tiling quantity that depends only on Sides and Roundness.

    With both sockets constant, all of ``calculate_out_variables``' branch
    predicates and geometric constants — bevel starts, angle bisectors, the
    fillet circle centre and radius, spline starts, effective roundness, and
    ``max_unit_parameter`` in every arm — are compile-time floats. What is left
    for runtime is a region select over per-texel quantities.

    ``sides`` and ``roundness`` must already be conditioned the way
    ``svm_node_radial_tiling`` conditions them — ``fmaxf(sides, 2)`` and
    ``clamp(roundness, 0, 1)``; ``_radial_tiling_settings`` does that.

    Returns a dict of folded floats, or None when the settings are degenerate
    enough that something stops being finite (Sides at exactly 2 pushes
    tan(pi/2) to the edge of float range) — the caller falls back to Cycles.

    Names follow ``radial_tiling_shared.h``:
      ab      segment_divider_A_angle_bisector      sdbs   segment_divider_A_bevel_start
      bsab    bevel_start_A_angle_bisector          ssbs   spline_start_A_bevel_start
      lcc     l_circle_center                       labxa  last_angle_bisector_A_x_axis
      ilbsxa  inner_last_bevel_start_A_x_axis       llcr   l_last_circle_radius
      xaolbs  x_axis_A_outer_last_bevel_start       olbsab outer_last_bevel_start_A_angle_bisector
    """
    eps = _RADIAL_TILING_EPS
    try:
        s = float(sides)
        r = float(roundness)
        ab = math.pi / s
        sdbs = ab - math.atan((1.0 - r) * math.tan(ab))
        bsab = ab - sdbs
        ssbs = (1.0 - r) * sdbs
        lcc = (1.0 - r) / math.cos(ab)
        folded = {
            "integral": (s - math.floor(s)) == 0.0,
            "sharp": r == 0.0,
            "sides": s,
            "roundness": r,
            "eps": eps,
            "inv_ab2": s / (2.0 * math.pi),
            "two_pi": 2.0 * math.pi,
            "minus_two": -2.0,
            "ab": ab,
            "ab2": 2.0 * ab,
            "minus_ab2": -2.0 * ab,
            "sdbs": sdbs,
            "ab2_minus_sdbs": 2.0 * ab - sdbs,
            "ssbs": ssbs,
            "half_ssbs": 0.5 * ssbs,
            # The spline arm divides by ssbs, which is exactly 0 at roundness 1.
            # There the spline arm is never the taken one (coord_A_bevel_start
            # cannot go below 0), so flooring the reciprocal only affects a value
            # the blend discards.
            "half_over_ssbs": 0.5 / max(ssbs, eps),
            "lcc": lcc,
            "radic_bias": r * r - lcc * lcc,
            "cos_bsab": math.cos(bsab),
            "sin_bsab": math.sin(bsab),
            "k1": math.tan(bsab) + 0.5 * ssbs,
            "k2": 0.5 * ssbs + r * sdbs,
            "inv_sdbs": 1.0 / max(sdbs, eps),
            "width_regular": math.tan(bsab) + ssbs + r * sdbs,
            "tan_ab": math.tan(ab),
            # max_unit_parameter for the sharp integral arm, which is the one place
            # calculate_out_variables carries a `sides != 2` guard: at exactly two
            # sides Cycles reports 0 rather than tan(pi/2), and skips the
            # r_gon_parameter normalization for the same reason.
            "width_sharp": 0.0 if s == 2.0 else math.tan(ab),
        }
        if not folded["integral"]:
            two_pi = 2.0 * math.pi
            labxa = math.pi - math.floor(s) * ab
            lsdxa = 2.0 * labxa
            ilbsxa = labxa - math.atan((1.0 - r) * math.tan(labxa))
            ilbslab = labxa - ilbsxa
            llcr = r * math.tan(labxa) / math.tan(0.5 * (ab + labxa))
            inv_cos = 1.0 / math.cos(labxa - ilbsxa)
            lcc0 = math.cos(ilbsxa) * inv_cos - llcr * math.cos(labxa)
            lcc1 = llcr * math.sin(labxa) - math.sin(ilbsxa) * inv_cos
            olbs0 = lcc0 + llcr * math.cos(ab)
            olbs1 = lcc1 + llcr * math.sin(ab)
            if olbs0 == 0.0:
                xaolbs = math.copysign(0.5 * math.pi, olbs1)
            else:
                xaolbs = math.atan(olbs1 / olbs0)
            olbsab = ab - xaolbs
            lab_r_llab = math.cos(ab) / math.cos(labxa)
            eff_r = 1.0 - math.tan(olbsab) / math.tan(ab)
            ssolbs = (1.0 - eff_r) * xaolbs
            ssbs2 = (1.0 - r) * ilbsxa
            folded.update({
                "labxa": labxa,
                "minus_lsdxa": -lsdxa,
                "lab_r_llab": lab_r_llab,
                "lcc0": lcc0,
                "lcc1": lcc1,
                "radic_bias3": llcr * llcr - lcc0 * lcc0 - lcc1 * lcc1,
                "ilbsxa": ilbsxa,
                "ssbs2": ssbs2,
                "half_ssbs2": 0.5 * ssbs2,
                "half_over_ssbs2": 0.5 / max(ssbs2, eps),
                "inv_ilbsxa": 1.0 / max(ilbsxa, eps),
                "cos_ilbslab": math.cos(ilbslab),
                "sin_ilbslab": math.sin(ilbslab),
                "xaolbs": xaolbs,
                "ssolbs": ssolbs,
                "half_ssolbs": 0.5 * ssolbs,
                "half_over_ssolbs": 0.5 / max(ssolbs, eps),
                "inv_xaolbs": 1.0 / max(xaolbs, eps),
                "cos_olbsab": math.cos(olbsab),
                "sin_olbsab": math.sin(olbsab),
                # Irregular-straight / irregular-rounded-inner normalisation:
                # lab_r_llab * (llab*tan(ilbslab) + ssbs2*(0.5*llab + 0.5) + r*ilbsxa)
                "kc1": lab_r_llab * (math.tan(ilbslab) + 0.5 * ssbs2),
                "kc2": lab_r_llab * (0.5 * ssbs2 + r * ilbsxa),
                "kd1": math.tan(ilbslab) + 0.5 * ssbs2,
                "kd2": 0.5 * ssbs2 + r * ilbsxa,
                # Irregular-rounded-outer normalisation, which the regular-straight
                # arm also reaches for coordinates inside the odd segment's span.
                "ke1": math.tan(olbsab) + 0.5 * ssolbs,
                "ke2": 0.5 * ssolbs + eff_r * xaolbs,
                "width_last": math.tan(ilbslab) + lab_r_llab * (
                    ssbs2 * (0.5 / lab_r_llab + 0.5) + r * ilbsxa
                ),
                # The sharp (roundness 0) dispatch has a single region test and
                # its own pair of max_unit_parameter values.
                "b_last": two_pi - lsdxa,
                "tan_labxa": math.tan(labxa),
                "labxa_minus_ab": labxa - ab,
                # Region bounds, in the order calculate_out_variables tests them.
                "b1": xaolbs,
                "b2": two_pi - lsdxa - xaolbs,
                "b3": two_pi - lsdxa - sdbs,
                "b5": two_pi - lsdxa + ilbsxa,
                "b6": two_pi - ilbsxa,
                "b7": two_pi - labxa,
                "b8": two_pi - lsdxa - ab,
            })
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    for value in folded.values():
        if isinstance(value, float) and not math.isfinite(value):
            return None
    return folded


class _UvExpressionCompiler:
    """Compile a Blender socket graph into UV-domain Material IR."""

    def __init__(
        self,
        *,
        material_name: str,
        workspace_path=None,
        object_info=None,
        uv_to_world_scale: float = 1.0,
        attribute_objects=None,
        sampler_addressed_images: bool = False,
        bake_uv_layer_name: str | None = None,
    ):
        from . import export as _export

        self._export = _export
        self.material_name = material_name
        # Every image tap leaves extension / interpolation to the backend sampler
        # (fields on SAMPLE_IMAGE) instead of rewriting the coordinate against this
        # image's size. Set for the slot-merge candidate compile, where one program
        # must serve images of different sizes. UDIM images are always addressed
        # this way, flag or not: each tile has its own size.
        self._sampler_addressing = bool(sampler_addressed_images)
        self.workspace_path = workspace_path
        # Resolved per-object constants for the Object Info node, or None when the
        # caller has no object context. See resolve_object_info.
        self._object_info = object_info if isinstance(object_info, dict) else None
        # (|dP/du|, |dP/dv|) in world units per UV unit, for Bump's slope scale. See
        # resolve_uv_to_world_scales; (1.0, 1.0) means "unmeasured". A bare number is
        # accepted and applied to both axes.
        try:
            if isinstance(uv_to_world_scale, (tuple, list)):
                pair = (float(uv_to_world_scale[0]), float(uv_to_world_scale[1]))
            else:
                value = float(uv_to_world_scale)
                pair = (value, value)
        except (TypeError, ValueError, IndexError):
            pair = (1.0, 1.0)
        self._uv_to_world_scale = tuple(v if v > 1e-6 else 1.0 for v in pair)
        # Objects this program will shade, for the Attribute node's OBJECT lookups.
        self._attribute_objects = list(attribute_objects or [])
        # Only alias an explicit UV layer to ATTR_UV when the exporter has proved
        # it is the projection layer for every group sharing this material program.
        self._bake_uv_layer_name = str(bake_uv_layer_name or "").strip()
        self.resources: list[dict[str, Any]] = []
        self.ops: list[dict[str, Any]] = []
        self._next_reg = 0
        self._cache: dict[tuple[int, str], int] = {}
        self._opcodes_used: set[str] = set()
        self._image_keys: dict[int, int] = {}
        self._group_input_stack: list[dict[str, Any]] = []
        self._group_depth = 0
        # Nodes currently being compiled, outermost first. Only read by _fail and
        # _emit's provenance record; it never steers compilation.
        self._node_stack: list[Any] = []
        # Parallel to self.ops: (node_name, node_type, node_path) for the node
        # that was on top of the stack when each op was emitted. Lets a
        # *program-level* refusal (the GPU-support gate, which sees ops and not
        # nodes) name a node too. Never serialized -- keeping it beside the ops
        # instead of inside them leaves the wire payload byte-identical.
        self._op_nodes: list[tuple[str, str, tuple[str, ...]]] = []

    def _current_node_provenance(self) -> tuple[str, str, tuple[str, ...]]:
        stack = getattr(self, "_node_stack", None) or ()
        node = stack[-1] if stack else None
        return (
            str(getattr(node, "name", "") or "") if node is not None else "",
            str(getattr(node, "type", "") or "") if node is not None else "",
            tuple(str(getattr(n, "name", "") or "") for n in stack),
        )

    def _fail(self, reason: str) -> None:
        node_name, node_type, node_path = self._current_node_provenance()
        raise MaterialIrRefusal(
            reason,
            node_name=node_name,
            node_type=node_type,
            node_path=node_path,
        )

    def _alloc(self) -> int:
        if self._next_reg >= _MAX_REGS:
            self._fail("Material IR register budget exceeded")
        reg = self._next_reg
        self._next_reg += 1
        return reg

    def _emit(self, op: dict[str, Any]) -> int:
        if len(self.ops) >= _MAX_OPS:
            self._fail("Material IR opcode budget exceeded")
        opcode = str(op.get("op") or "")
        if opcode not in SUPPORTED_OPCODES:
            self._fail(f"Unsupported Material IR opcode '{opcode}'")
        self._opcodes_used.add(opcode)
        self.ops.append(op)
        op_nodes = getattr(self, "_op_nodes", None)
        if op_nodes is not None:
            # Appended in lockstep with self.ops so index i of one indexes the
            # other. _allocate_registers only rewrites register fields in place,
            # never reorders or drops ops, so the correspondence survives it.
            op_nodes.append(self._current_node_provenance())
        return int(op["dst"])

    def _emit_constant(self, rgba: tuple[float, float, float, float]) -> int:
        dst = self._alloc()
        return self._emit(
            {
                "op": OPCODE_CONSTANT,
                "dst": dst,
                "value": [float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3])],
            }
        )

    def _emit_swizzle(self, src: int, mode: str) -> int:
        dst = self._alloc()
        return self._emit({"op": OPCODE_SWIZZLE, "dst": dst, "src": int(src), "mode": mode})

    _SCALAR_LANE_MODES = ("RRR1", "GGG1", "BBB1")

    def _emit_scalar_constants(self, values: dict[str, float]) -> dict[str, int]:
        """Materialise a batch of folded scalars, three to a CONSTANT op.

        A CONSTANT carries four lanes but the usual `_emit_constant` +
        `_emit_swizzle("LUMA")` pair spends a whole op pair on one number, so a
        heavily folded expansion pays 2n ops for n constants. Packing three per
        CONSTANT and swizzling each lane out costs ceil(n/3) + n instead —
        measured at 13 ops saved on the integral Radial Tiling expansion and 23
        on the fractional one, which is the difference between fitting the
        256-op budget and not.

        Equal values share a lane, so callers can name the same number twice.
        """
        unique: list[float] = []
        seen: set[float] = set()
        for value in values.values():
            key = float(value) + 0.0  # normalise -0.0 onto 0.0
            if key not in seen:
                seen.add(key)
                unique.append(key)
        by_value: dict[float, int] = {}
        for start in range(0, len(unique), 3):
            chunk = unique[start:start + 3]
            lanes = (chunk + [0.0, 0.0, 0.0])[:3]
            packed = self._emit_constant((lanes[0], lanes[1], lanes[2], 1.0))
            for index, value in enumerate(chunk):
                by_value[value] = self._emit_swizzle(packed, self._SCALAR_LANE_MODES[index])
        return {name: by_value[float(value) + 0.0] for name, value in values.items()}

    def _socket_key(self, socket) -> str:
        return str(
            getattr(socket, "identifier", None)
            or getattr(socket, "name", None)
            or ""
        )

    def _socket_at_index(self, sockets, index: int):
        try:
            return list(sockets or [])[index]
        except Exception:
            return None

    def _matching_socket(self, sockets, template_socket):
        if template_socket is None:
            return None
        key = self._socket_key(template_socket)
        if key:
            try:
                found = sockets.get(key)
                if found is not None:
                    return found
            except Exception:
                pass
        name = str(getattr(template_socket, "name", "") or "")
        if name:
            try:
                found = sockets.get(name)
                if found is not None:
                    return found
            except Exception:
                pass
        return None

    def _group_output_node(self, tree):
        candidates = [
            node for node in list(getattr(tree, "nodes", []) or [])
            if str(getattr(node, "type", "") or "") == "GROUP_OUTPUT"
        ]
        for node in candidates:
            if bool(getattr(node, "is_active_output", False)):
                return node
        return candidates[0] if candidates else None

    def _compile_group_output(self, group_node, output, *, want: str) -> int:
        if self._group_depth >= 16:
            self._fail("Material node-group nesting is too deep for native Material IR")
        tree = getattr(group_node, "node_tree", None)
        group_output = self._group_output_node(tree)
        if tree is None or group_output is None:
            self._fail("Material node group has no active Group Output. Needs Cycles")
        group_output_input = self._matching_socket(getattr(group_output, "inputs", None), output)
        if group_output_input is None:
            index = -1
            try:
                index = list(getattr(group_node, "outputs", []) or []).index(output)
            except Exception:
                index = -1
            group_output_input = self._socket_at_index(getattr(group_output, "inputs", None), index)
        if group_output_input is None:
            self._fail("Material node group output cannot be mapped. Needs Cycles")
        if not bool(getattr(group_output_input, "is_linked", bool(getattr(group_output_input, "links", None)))):
            rgba = _socket_default_rgba(group_output_input)
            reg = self._emit_constant(rgba)
            return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg
        self._group_depth += 1
        self._group_input_stack.append({"node": group_node})
        try:
            return self.compile_socket(group_output_input, want=want)
        finally:
            self._group_input_stack.pop()
            self._group_depth -= 1

    def _compile_group_input_output(self, node, output, *, want: str) -> int:
        if not self._group_input_stack:
            self._fail("Unbound Group Input in Material IR graph. Needs Cycles")
        group_node = self._group_input_stack[-1]["node"]
        outer_socket = self._matching_socket(getattr(group_node, "inputs", None), output)
        if outer_socket is None:
            index = -1
            try:
                index = list(getattr(node, "outputs", []) or []).index(output)
            except Exception:
                index = -1
            outer_socket = self._socket_at_index(getattr(group_node, "inputs", None), index)
        if outer_socket is None:
            self._fail("Material node group input cannot be mapped. Needs Cycles")
        # The outer socket lives in the ENCLOSING tree, so this frame has to come off
        # the stack before compiling it. Leaving it on made a Group Input one level up
        # resolve against this same group node again -- an infinite recursion that
        # escaped compile_channel_program as a RecursionError and killed the whole bake
        # (see docs/MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G2). Nesting a group inside a
        # group and passing a parameter down is how every node-group library is built.
        frame = self._group_input_stack.pop()
        self._group_depth -= 1
        try:
            return self.compile_socket(outer_socket, want=want)
        finally:
            self._group_depth += 1
            self._group_input_stack.append(frame)

    def _add_image_resource(self, image, *, channel: str) -> int:
        if image is None:
            self._fail(f"Material '{self.material_name}' has an Image Texture with no image")
        source = str(getattr(image, "source", "") or "").upper()
        tiled = source == "TILED"
        if tiled:
            # A UDIM image becomes a tile TABLE: export ships each tile as its own
            # PNG and the backend picks the tile per hit, exactly like Cycles'
            # kernel_image_udim_map. Only file-backed tile sets can be read tile by
            # tile; a packed or generated one has no per-tile file, and reading a
            # non-active tile would mean mutating the artist's datablock.
            image_name = str(getattr(image, "name", "") or "image")
            packed_files = getattr(image, "packed_files", None)
            try:
                packed = getattr(image, "packed_file", None) is not None or bool(
                    packed_files is not None and len(packed_files) > 0
                )
            except TypeError:
                packed = getattr(image, "packed_file", None) is not None
            if packed:
                self._fail(
                    f"UDIM image '{image_name}' is packed into the .blend. Needs Cycles "
                    "(unpack it to bake natively)"
                )
            filepath = str(getattr(image, "filepath", "") or "")
            if "<UVTILE>" in filepath:
                self._fail(
                    f"UDIM image '{image_name}' uses <UVTILE> file naming. Needs Cycles "
                    "(supported: <UDIM>)"
                )
            if constants.UDIM_PATH_TOKEN not in filepath:
                self._fail(
                    f"UDIM image '{image_name}' is generated and has no tile files. "
                    "Needs Cycles (save it to bake natively)"
                )
            if bool(getattr(image, "is_dirty", False)):
                self._fail(
                    f"UDIM image '{image_name}' has unsaved changes. Needs Cycles "
                    "(save it to bake natively)"
                )
        key = _node_cache_id(image)
        if key in self._image_keys:
            return self._image_keys[key]
        if len(self.resources) >= _MAX_RESOURCES:
            self._fail("Material IR texture resource budget exceeded")
        # Path is filled later by export normalization; keep Blender image pointer for that.
        index = len(self.resources)
        resource = {
            "image": image,
            "channel": channel,
            "path": "",
        }
        if tiled:
            # Export replaces this with the wire table form (`tiles`); the key never
            # reaches the backend. Plain resources keep their exact old shape.
            resource["tiled"] = True
        self.resources.append(resource)
        self._image_keys[key] = index
        return index

    def _resource_is_sampler_addressed(self, resource: int) -> bool:
        """Whether taps on this resource leave addressing to the backend sampler.

        True for every UDIM table (each tile has its own size, so no coordinate
        rewrite against one size can be right) and for every image in a slot-merge
        candidate compile (one program must serve images of different sizes).
        """
        if bool(getattr(self, "_sampler_addressing", False)):
            return True
        try:
            return bool(self.resources[int(resource)].get("tiled"))
        except (IndexError, TypeError, ValueError, AttributeError):
            return False

    def _apply_missing_colour(self, node, resource: int) -> None:
        """Carry an Image Texture's Missing / Missing Alpha onto a UDIM table.

        Blender 5.x exposes what a tap returns for a tile the image does not have.
        Only a tiled resource can miss, so only it records the value, and only when
        it differs from Cycles' magenta: the default stays implicit on the wire.
        """
        try:
            item = self.resources[int(resource)]
        except (IndexError, TypeError, ValueError):
            return
        if not item.get("tiled"):
            return
        inputs = getattr(node, "inputs", None)
        getter = getattr(inputs, "get", None)
        if not callable(getter):
            return
        colour_socket = getter("Missing")
        alpha_socket = getter("Missing Alpha")
        if colour_socket is None and alpha_socket is None:
            return
        for socket in (colour_socket, alpha_socket):
            if socket is not None and bool(getattr(socket, "is_linked", False)):
                self._fail(
                    "Image Texture 'Missing' driven by a link is not native yet. Needs Cycles"
                )
        rgb = IMAGE_MISSING_RGBA[:3]
        if colour_socket is not None:
            value = _socket_default_rgba(colour_socket)
            rgb = (float(value[0]), float(value[1]), float(value[2]))
        alpha = IMAGE_MISSING_RGBA[3]
        if alpha_socket is not None:
            try:
                alpha = float(getattr(alpha_socket, "default_value", alpha))
            except (TypeError, ValueError):
                alpha = IMAGE_MISSING_RGBA[3]
        missing = (rgb[0], rgb[1], rgb[2], alpha)
        previous = item.get("missing")
        if previous is not None and tuple(previous) != missing:
            self._fail(
                "Two Image Texture nodes give one UDIM image different Missing colours. "
                "Needs Cycles"
            )
        if missing != IMAGE_MISSING_RGBA:
            item["missing"] = [float(v) for v in missing]

    def _emit_sampler_tap(
        self, *, resource: int, channel: str, coord: int, extension: str, interpolation: str
    ) -> int:
        """SAMPLE_IMAGE with addressing and filtering left to the backend sampler.

        Carries `extension` and `mode` (mode stamped even for LINEAR) so the backend
        resolves the UDIM tile or slot first and then addresses INSIDE that image
        against its own size, the way Cycles' ImageInterpolator does. Emitted only
        for sampler-addressed resources; every other tap keeps its exact old shape.
        """
        return self._emit(
            {
                "op": OPCODE_SAMPLE_IMAGE,
                "dst": self._alloc(),
                "resource": int(resource),
                "channel": channel,
                "coord": int(coord),
                "extension": str(extension),
                "mode": str(interpolation),
            }
        )

    def compile_socket(self, socket, *, want: str = "COLOR") -> int:
        """Compile socket to a register. want: COLOR | SCALAR."""
        if socket is None:
            return self._emit_constant((0.0, 0.0, 0.0, 1.0))

        if not bool(getattr(socket, "is_linked", False)):
            rgba = _socket_default_rgba(socket)
            reg = self._emit_constant(rgba)
            if want == "SCALAR":
                return self._emit_swizzle(reg, "LUMA")
            return reg

        links = tuple(getattr(socket, "links", ()) or ())
        if not links:
            rgba = _socket_default_rgba(socket)
            reg = self._emit_constant(rgba)
            if want == "SCALAR":
                return self._emit_swizzle(reg, "LUMA")
            return reg

        node = getattr(links[0], "from_node", None)
        output = getattr(links[0], "from_socket", None)
        if node is None or output is None:
            self._fail(f"Material '{self.material_name}' has a broken socket link")

        # Use as_pointer() — id(bpy_struct) is the temporary Python wrapper
        # address and can collide across nodes after GC, merging distinct
        # Noise/Voronoi compiles onto one register.
        # The coordinate offset is part of the identity: Bump recompiles the same
        # socket at shifted coordinates, and without this the cache hands back the
        # unshifted register, collapsing the finite difference to zero.
        cache_key = (_node_cache_id(node), str(getattr(output, "name", "") or ""), want,
                     getattr(self, "_coord_offset", None))
        if cache_key in self._cache:
            return self._cache[cache_key]

        reg = self._compile_node_output(node, output, want=want)
        self._cache[cache_key] = reg
        return reg

    _COORDINATE_ATTRS = frozenset(
        {OPCODE_ATTR_UV, OPCODE_ATTR_OBJECT, OPCODE_ATTR_GENERATED, OPCODE_ATTR_POSITION}
    )

    def _emit_attr(self, opcode: str) -> int:
        dst = self._alloc()
        reg = self._emit({"op": opcode, "dst": dst})
        if opcode not in self._COORDINATE_ATTRS:
            return reg
        return self._shift_coordinate(reg)

    def _shift_coordinate(self, reg: int) -> int:
        """*reg* moved by the active Bump offset, if any.

        Bump differentiates by recompiling the height chain at a shifted
        coordinate. Every coordinate source must come through here, or its
        height chains compile identical and the slope is exactly zero.
        """
        offset = getattr(self, "_coord_offset", None)
        if offset is None:
            return reg
        shift = self._emit_constant((float(offset[0]), float(offset[1]), float(offset[2]), 1.0))
        return self._emit(
            {
                "op": OPCODE_VECTOR_MATH,
                "dst": self._alloc(),
                "math_op": "ADD",
                "a": int(reg),
                "b": int(shift),
                "fac": int(shift),
            }
        )

    @contextlib.contextmanager
    def _coordinate_offset(self, offset):
        previous = getattr(self, "_coord_offset", None)
        self._coord_offset = offset
        try:
            yield
        finally:
            self._coord_offset = previous

    def _compile_vector_value(self, socket, *, fallback=(0.0, 0.0, 0.0)) -> int:
        """Compile a vector socket; unlinked uses the socket default (not UV)."""
        if socket is None or not bool(getattr(socket, "is_linked", False)):
            try:
                value = getattr(socket, "default_value", fallback)
                rgba = (float(value[0]), float(value[1]), float(value[2]), 1.0)
            except Exception:
                rgba = (float(fallback[0]), float(fallback[1]), float(fallback[2]), 1.0)
            return self._emit_constant(rgba)
        return self._compile_vector(socket)

    def _radial_tiling_coord(self, node) -> int:
        """Unlinked Radial Tiling Vector uses Generated, like Noise/Voronoi.

        Cycles' socket default is (0,0,0), which bakes a solid black Segment
        Coordinates map. Artists leave Vector unlinked expecting a pattern.
        """
        return self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )

    def _compile_vector(self, socket, *, default_attr: str = OPCODE_ATTR_UV) -> int:
        """Compile a vector/coordinate socket (TexCoord, Mapping, UVMap, constants)."""
        if socket is None or not bool(getattr(socket, "is_linked", False)):
            # Unlinked Image Texture Vector → active UV.
            return self._emit_attr(default_attr)

        links = tuple(getattr(socket, "links", ()) or ())
        if not links:
            return self._emit_attr(default_attr)

        node = getattr(links[0], "from_node", None)
        output = getattr(links[0], "from_socket", None)
        if node is None:
            self._fail("Broken vector link")
        ntype = str(getattr(node, "type", "") or "")
        out_name = str(getattr(output, "name", "") or "")

        cache_key = (_node_cache_id(node), out_name, "VECTOR",
                     getattr(self, "_coord_offset", None))
        if cache_key in self._cache:
            return self._cache[cache_key]

        if ntype == "REROUTE":
            reg = self._compile_vector(
                node.inputs[0] if node.inputs else None, default_attr=default_attr
            )
            self._cache[cache_key] = reg
            return reg

        if ntype == "GROUP":
            reg = self._compile_group_output(node, output, want="COLOR")
            self._cache[cache_key] = reg
            return reg

        if ntype == "GROUP_INPUT":
            reg = self._compile_group_input_output(node, output, want="COLOR")
            self._cache[cache_key] = reg
            return reg

        if ntype == "UVMAP":
            # An explicit UV Map node names the material's coordinate layer. The
            # active render UV is not necessarily the UV layer the bake projects into,
            # so a named layer must not alias to ATTR_UV here.
            if bool(getattr(node, "from_instancer", False)):
                self._fail("UV Map 'From Instancer' is not native yet. Needs Cycles")
            uv_layer = str(getattr(node, "uv_map", "") or "").strip()
            if not uv_layer:
                uv_layer = self._active_render_uv_layer_name()
            if uv_layer and uv_layer != self._bake_uv_layer_name:
                reg = self._compile_named_uv_layer(uv_layer, want="COLOR")
            else:
                reg = self._emit_attr(OPCODE_ATTR_UV)
            self._cache[cache_key] = reg
            return reg

        if ntype == "ATTRIBUTE":
            # An Attribute node naming a UV layer is a coordinate source too.
            reg = self._compile_node_output(node, output, want="COLOR")
            self._cache[cache_key] = reg
            return reg

        if ntype == "TEX_COORD":
            if out_name == "UV":
                uv_layer = self._active_render_uv_layer_name()
                reg = (
                    self._compile_named_uv_layer(uv_layer, want="COLOR")
                    if uv_layer and uv_layer != self._bake_uv_layer_name
                    else self._emit_attr(OPCODE_ATTR_UV)
                )
            elif getattr(node, "object", None) is not None:
                self._fail(
                    "Texture Coordinate 'Object' field points at another object; the "
                    "native path uses the shaded object's own matrix. Needs Cycles"
                )
            elif out_name == "Object":
                reg = self._emit_attr(OPCODE_ATTR_OBJECT)
            elif out_name == "Generated":
                reg = self._emit_attr(OPCODE_ATTR_GENERATED)
            elif out_name == "Normal":
                reg = self._object_space_normal()
            elif out_name in _VIEW_DEPENDENT_TEXCOORD_OUTPUTS:
                self._fail(
                    f"TexCoord '{out_name}' is view-dependent and cannot be baked"
                )
            else:
                self._fail(
                    f"TexCoord '{out_name}' is not native yet. Needs Cycles "
                    "(supported: UV, Object, Generated)"
                )
            self._cache[cache_key] = reg
            return reg

        if ntype == "MAPPING":
            vector_type = str(getattr(node, "vector_type", "POINT") or "POINT").upper()
            if vector_type not in {"POINT", "TEXTURE", "VECTOR", "NORMAL"}:
                self._fail(f"Unsupported Mapping vector type '{vector_type}'")
            src = self._compile_vector(node.inputs.get("Vector"), default_attr=default_attr)
            loc_reg = self._compile_vector_value(
                node.inputs.get("Location"), fallback=(0.0, 0.0, 0.0)
            )
            rot_reg = self._compile_vector_value(
                node.inputs.get("Rotation"), fallback=(0.0, 0.0, 0.0)
            )
            scale_reg = self._compile_vector_value(
                node.inputs.get("Scale"), fallback=(1.0, 1.0, 1.0)
            )
            # Keep constant loc/rot/scale mirrors for older CPU readers / debugging.
            try:
                loc = [float(v) for v in node.inputs["Location"].default_value]
                rot = [float(v) for v in node.inputs["Rotation"].default_value]
                scale = [float(v) for v in node.inputs["Scale"].default_value]
            except Exception:
                loc, rot, scale = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
            dst = self._alloc()
            reg = self._emit(
                {
                    "op": OPCODE_MAPPING,
                    "dst": dst,
                    "src": int(src),
                    "loc": loc,
                    "rot": rot,
                    "scale": scale,
                    "loc_reg": int(loc_reg),
                    "rot_reg": int(rot_reg),
                    "scale_reg": int(scale_reg),
                    "vector_type": vector_type,
                }
            )
            self._cache[cache_key] = reg
            return reg

        if ntype in {"VECT_MATH", "VECTOR_MATH"}:
            reg = self._compile_vector_math(node, want="COLOR")
            self._cache[cache_key] = reg
            return reg

        if ntype in {"COMBXYZ", "COMBINE_XYZ"}:
            reg = self._compile_combine_xyz(node, want="COLOR")
            self._cache[cache_key] = reg
            return reg

        if ntype in {"COMBINE_COLOR", "COMBCLR"}:
            reg = self._compile_combine_color(node, want="COLOR")
            self._cache[cache_key] = reg
            return reg

        # Anything else driving a vector socket is just a colour/vector-valued
        # expression — Blender links those implicitly. Delegate rather than
        # maintaining a second node dispatch that silently lags behind the first.
        reg = self._compile_node_output(node, output, want="COLOR")
        self._cache[cache_key] = reg
        return reg

    def _compile_node_output(self, node, output, *, want: str) -> int:
        """Record the node for refusal reporting, then dispatch on its type.

        Pure bookkeeping: the dispatch below is unchanged, and the stack is only
        ever read by ``_fail``.
        """
        stack = getattr(self, "_node_stack", None)
        if stack is None:
            stack = []
            self._node_stack = stack
        stack.append(node)
        try:
            return self._compile_node_output_dispatch(node, output, want=want)
        finally:
            stack.pop()

    def _muted_passthrough_socket(self, node, output):
        """The input a muted node passes `output` through from, or None.

        Blender fills ``internal_links`` with exactly this mapping while a node is
        muted, and Cycles honours it. The compiler used to ignore ``mute`` entirely,
        so muting a node -- the standard way to A/B a step before re-baking -- changed
        nothing in the native bake while it changed everything in Cycles. See
        docs/MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G6.
        """
        if not bool(getattr(node, "mute", False)):
            return None
        target = getattr(output, "identifier", None) or getattr(output, "name", None)
        for link in tuple(getattr(node, "internal_links", ()) or ()):
            to_socket = getattr(link, "to_socket", None)
            if to_socket is None:
                continue
            key = getattr(to_socket, "identifier", None) or getattr(to_socket, "name", None)
            if key == target:
                return getattr(link, "from_socket", None)
        return None

    def _compile_node_output_dispatch(self, node, output, *, want: str) -> int:
        ntype = str(getattr(node, "type", "") or "")
        out_name = str(getattr(output, "name", "") or "")

        # A muted node is a wire. Resolve it before anything looks at its properties.
        # No internal link for this output means the mute leaves it unconnected, which
        # Blender reads as the socket's own default -- same as an unlinked input.
        if bool(getattr(node, "mute", False)) and ntype != "GROUP_INPUT":
            passthrough = self._muted_passthrough_socket(node, output)
            if passthrough is not None:
                return self.compile_socket(passthrough, want=want)
            rgba = _socket_default_rgba(output)
            reg = self._emit_constant(rgba)
            return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

        if ntype == "REROUTE":
            return self.compile_socket(node.inputs[0] if node.inputs else None, want=want)

        if ntype == "GROUP":
            return self._compile_group_output(node, output, want=want)

        if ntype == "GROUP_INPUT":
            return self._compile_group_input_output(node, output, want=want)

        if ntype == "TEX_IMAGE":
            # SAMPLE_IMAGE carries only {resource, channel, coord}: the sampler is flat
            # UV, repeat, linear, full stop. Compiling a node that asks for anything
            # else used to bake the default silently under a "Bakes natively" tick --
            # a box-projected texture came out as flat UV, Clip tiled anyway, Closest
            # filtered smoothly. Refuse instead, so the channel routes to Cycles and
            # the panel says so. See MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G1.
            projection = str(getattr(node, "projection", "FLAT") or "FLAT").strip().upper()
            # Box is three flat taps blended by the object-space normal
            # (_compile_box_projection); Sphere and Tube are single coordinate
            # transforms applied before an otherwise ordinary flat tap
            # (_compile_environment_projection).
            if projection not in {"FLAT", "BOX", "SPHERE", "TUBE"}:
                self._fail(
                    f"Image Texture projection '{projection}' is not native yet. Needs "
                    "Cycles (supported: Flat, Box, Sphere, Tube)"
                )
            extension = str(getattr(node, "extension", "REPEAT") or "REPEAT").strip().upper()
            # Clip WAS absent because a hard `0 < uv < 1` mask kept about a fifth of
            # the texels Cycles did. The cause was the boundary, not the zeroing:
            # Cycles clips on the texel index inside the tap and ramps over the outer
            # half texel. See _emit_clip_mask.
            if extension not in {"REPEAT", "EXTEND", "MIRROR", "CLIP"}:
                self._fail(
                    f"Image Texture extension '{extension}' is not native yet. Needs Cycles"
                )
            interpolation = str(getattr(node, "interpolation", "Linear") or "Linear").strip().upper()
            # Cubic and Smart stay on Cycles: a real bicubic is 16 taps, which is a
            # different piece of work, not a coordinate rewrite.
            #
            # Closest used to refuse alongside them, on a measurement of 15.75% of
            # texels over 8/255 blamed on "the sampler applying its own half-texel
            # offset on top of this one". That was checked against both samplers and
            # is wrong. `mir_sample_texel_buffer` does `fx = u*width - 0.5`, which the
            # snapping's `+ 0.5` exactly CANCELS (tx = 0, one texel, no blend), and
            # Cycles' `interp_closest` uses `frac(x)` with NO -0.5, so its nearest
            # texel is `floor(u*width)` -- the same one. Driving the compiled
            # coordinate through a transcription of the real backend sampler against a
            # transcription of Cycles' lookup finds zero disagreement over 400
            # coordinates on a hard-edged pattern, including outside the unit square;
            # removing the `+ 0.5` as that note prescribed breaks >30% of them. See
            # ClosestInterpolationTests.
            # Cubic and Smart are the same filter: Cycles' GPU image lookup takes the
            # bicubic branch for `INTERPOLATION_CUBIC || INTERPOLATION_SMART`
            # (kernel/device/gpu/image.h), so Smart is not approximated here, it is
            # transcribed. The backend does it in four bilinear taps, which is why
            # this stays one op.
            if interpolation not in {"LINEAR", "CLOSEST", "CUBIC", "SMART"}:
                self._fail(
                    f"Image Texture interpolation '{interpolation.title()}' is not native "
                    "yet. Needs Cycles (supported: Linear, Closest, Cubic, Smart)"
                )
            image = getattr(node, "image", None)
            channel = "A" if out_name.upper() == "ALPHA" else "RGBA"
            # Blender's alpha_mode (STRAIGHT associates colour x alpha at load, NONE
            # ignores the stored alpha) is applied when the image is normalised into
            # the workspace PNG the backend reads -- see
            # export._normalize_material_image_to_png. Doing it there instead of as
            # ops keeps the single-sample IMAGE_SAMPLE fast path intact.
            resource = self._add_image_resource(image, channel=channel)
            self._apply_missing_colour(node, resource)
            coord = self._compile_vector(node.inputs.get("Vector"))
            if projection == "BOX":
                return self._compile_box_projection(
                    node,
                    image=image,
                    resource=resource,
                    channel=channel,
                    extension=extension,
                    interpolation=interpolation,
                    coord=coord,
                    want=want,
                )
            if projection in {"SPHERE", "TUBE"}:
                coord = self._compile_environment_projection(coord, projection)
            if self._resource_is_sampler_addressed(resource):
                # The backend resolves the UDIM tile / material slot from the raw
                # coordinate and then applies extension and interpolation inside
                # that one image, against its own size. None of the coordinate
                # rewrites below may run: they bake ONE image's size into the ops.
                reg = self._emit_sampler_tap(
                    resource=resource,
                    channel=channel,
                    coord=coord,
                    extension=extension,
                    interpolation=interpolation,
                )
                if want == "SCALAR":
                    return self._emit_swizzle(reg, "A" if channel == "A" else "LUMA")
                if channel == "A":
                    return self._emit_swizzle(reg, "AAA1")
                return reg
            clip_mask = self._emit_clip_mask(coord, image) if extension == "CLIP" else None
            # CLIP samples through the EXTEND clamp: inside the coverage ramp the
            # in-range corner is the only one that contributes, and clamping is how a
            # REPEAT-only sampler reads it instead of wrapping to the far edge.
            coord = self._apply_image_extension(
                coord, "EXTEND" if extension == "CLIP" else extension, image
            )
            coord = self._apply_image_interpolation(coord, interpolation, image)
            dst = self._alloc()
            reg = self._emit(
                {
                    "op": OPCODE_SAMPLE_IMAGE,
                    "dst": dst,
                    "resource": int(resource),
                    "channel": channel,
                    "coord": int(coord),
                    # Cubic / Smart select the bicubic tap in the sampler; Linear and
                    # Closest leave it bilinear (Closest having already been snapped
                    # onto a texel centre by _apply_image_interpolation).
                    #
                    # Only stamped for the bicubic modes, so a Linear texture compiles
                    # to the byte-identical program it always did. The program dict is
                    # the bake cache key: adding a field unconditionally would
                    # invalidate every cached material bake in the wild for no change
                    # in output.
                    **({"mode": interpolation} if interpolation in _BICUBIC_INTERPOLATIONS else {}),
                }
            )
            if clip_mask is not None:
                # Cycles' Clip returns transparent black outside the unit square, so
                # the mask multiplies colour AND alpha.
                mask3 = self._emit(
                    {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                     "a": int(clip_mask), "b": int(clip_mask), "fac": int(clip_mask)}
                )
                if want == "SCALAR":
                    scalar = self._emit_swizzle(reg, "A" if channel == "A" else "LUMA")
                    return self._emit_math_op("MULTIPLY", scalar, clip_mask)
                if channel == "A":
                    alpha = self._emit_swizzle(reg, "AAA1")
                    return self._emit_vector_math_op("MULTIPLY", alpha, mask3)
                return self._emit_vector_math_op("MULTIPLY", reg, mask3)
            if want == "SCALAR":
                return self._emit_swizzle(reg, "A" if channel == "A" else "LUMA")
            if channel == "A":
                return self._emit_swizzle(reg, "AAA1")
            return reg

        if ntype in {"TEX_COORD", "UVMAP"}:
            # ATTR_UV is the bake's active UV map and carries no layer name. An
            # explicitly named UV Map layer must use its sidecar even when it is the
            # mesh's active render UV: the group's bake target can be a different set.
            # Same for a Texture Coordinate node driven from another object's matrix.
            # See MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G4.
            if ntype == "UVMAP":
                if bool(getattr(node, "from_instancer", False)):
                    self._fail("UV Map 'From Instancer' is not native yet. Needs Cycles")
                uv_layer = str(getattr(node, "uv_map", "") or "").strip()
                if not uv_layer:
                    uv_layer = self._active_render_uv_layer_name()
                if uv_layer and uv_layer != self._bake_uv_layer_name:
                    return self._compile_named_uv_layer(uv_layer, want=want)
            elif getattr(node, "object", None) is not None:
                self._fail(
                    "Texture Coordinate 'Object' field points at another object; the "
                    "native path uses the shaded object's own matrix. Needs Cycles"
                )
            # Expose the coordinate as an RGB vector when used as a color input.
            if ntype == "UVMAP" or out_name == "UV":
                if ntype == "TEX_COORD":
                    uv_layer = self._active_render_uv_layer_name()
                    if uv_layer and uv_layer != self._bake_uv_layer_name:
                        return self._compile_named_uv_layer(uv_layer, want=want)
                reg = self._emit_attr(OPCODE_ATTR_UV)
            elif out_name == "Object":
                reg = self._emit_attr(OPCODE_ATTR_OBJECT)
            elif out_name == "Generated":
                reg = self._emit_attr(OPCODE_ATTR_GENERATED)
            elif out_name == "Normal":
                reg = self._object_space_normal()
            elif out_name in _VIEW_DEPENDENT_TEXCOORD_OUTPUTS:
                self._fail(f"TexCoord '{out_name}' is view-dependent and cannot be baked")
            else:
                self._fail(f"TexCoord '{out_name}' is not native yet. Needs Cycles")
            return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

        if ntype == "MAPPING":
            # Build a fake linked socket path by compiling Mapping via Vector input.
            # Mapping nodes always expose a Vector output.
            vector_type = str(getattr(node, "vector_type", "POINT") or "POINT").upper()
            if vector_type not in {"POINT", "TEXTURE", "VECTOR", "NORMAL"}:
                self._fail(f"Unsupported Mapping vector type '{vector_type}'")
            src = self._compile_vector(node.inputs.get("Vector"))
            loc_reg = self._compile_vector_value(
                node.inputs.get("Location"), fallback=(0.0, 0.0, 0.0)
            )
            rot_reg = self._compile_vector_value(
                node.inputs.get("Rotation"), fallback=(0.0, 0.0, 0.0)
            )
            scale_reg = self._compile_vector_value(
                node.inputs.get("Scale"), fallback=(1.0, 1.0, 1.0)
            )
            try:
                loc = [float(v) for v in node.inputs["Location"].default_value]
                rot = [float(v) for v in node.inputs["Rotation"].default_value]
                scale = [float(v) for v in node.inputs["Scale"].default_value]
            except Exception:
                loc, rot, scale = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
            dst = self._alloc()
            reg = self._emit(
                {
                    "op": OPCODE_MAPPING,
                    "dst": dst,
                    "src": int(src),
                    "loc": loc,
                    "rot": rot,
                    "scale": scale,
                    "loc_reg": int(loc_reg),
                    "rot_reg": int(rot_reg),
                    "scale_reg": int(scale_reg),
                    "vector_type": vector_type,
                }
            )
            return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

        if ntype in {"VECT_MATH", "VECTOR_MATH"}:
            return self._compile_vector_math(node, want=want)

        if ntype == "MAP_RANGE":
            return self._compile_map_range(node, want=want)

        if ntype == "CLAMP":
            return self._compile_clamp(node, want=want)

        if ntype == "TEX_NOISE":
            return self._compile_noise_texture(node, output, want=want)
        if ntype == "TEX_VORONOI":
            return self._compile_voronoi_texture(node, output, want=want)
        if ntype == "TEX_WHITE_NOISE":
            return self._compile_white_noise_texture(node, output, want=want)
        if ntype == "TEX_MAGIC":
            return self._compile_magic_texture(node, output, want=want)
        if ntype == "TEX_GABOR":
            return self._compile_gabor_texture(node, output, want=want)
        if ntype == "TEX_WAVE":
            return self._compile_wave_texture(node, output, want=want)
        if ntype == "TEX_GRADIENT":
            return self._compile_gradient_texture(node, output, want=want)
        if ntype == "TEX_CHECKER":
            return self._compile_checker_texture(node, output, want=want)
        if ntype == "TEX_BRICK":
            return self._compile_brick_texture(node, output, want=want)

        if ntype == "RGB":
            rgba = _socket_default_rgba(node.outputs.get("Color") or output)
            reg = self._emit_constant(rgba)
            return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

        if ntype == "VALUE":
            try:
                value = float(node.outputs[0].default_value)
            except Exception:
                value = 0.0
            reg = self._emit_constant((value, value, value, 1.0))
            return reg if want == "SCALAR" else reg

        if ntype == "INVERT":
            fac = self.compile_socket(node.inputs.get("Fac"), want="SCALAR")
            color = self.compile_socket(node.inputs.get("Color"), want="COLOR")
            dst = self._alloc()
            return self._emit(
                {"op": OPCODE_INVERT, "dst": dst, "src": int(color), "fac": int(fac)}
            )

        if ntype in {"MIX", "MIX_RGB", "MIXRGB"}:
            return self._compile_mix(node, want=want)

        if ntype == "MATH":
            return self._compile_math(node, want=want)

        if ntype == "VALTORGB":
            return self._compile_color_ramp(node, output, want=want)

        if ntype == "SEPRGB" or ntype == "SEPARATE_COLOR" or ntype == "SEP_COLOR":
            # The swizzle below is RGB. `mode` used to be unread, so an artist
            # masking by Hue or Saturation silently got the R/G/B channel instead
            # (pass-3 H2); it then refused, and now it converts. The output socket
            # names stay Red/Green/Blue whatever the mode, so the lane pick is the
            # same in all three -- only the space the colour is in changes.
            colour_mode = str(getattr(node, "mode", "") or "RGB").strip().upper()
            if colour_mode not in {"RGB", "HSV", "HSL", ""}:
                self._fail(
                    f"Separate Color mode '{colour_mode}' is not native yet. Needs "
                    "Cycles (supported: RGB, HSV, HSL)"
                )
            color = self.compile_socket(
                node.inputs.get("Color") or node.inputs.get("Image") or (node.inputs[0] if node.inputs else None),
                want="COLOR",
            )
            if colour_mode == "HSV":
                color = self._emit_color_space(color, "RGB_TO_HSV")
            elif colour_mode == "HSL":
                color = self._emit_color_space(color, "RGB_TO_HSL")
            lane = {"R": "RRR1", "G": "GGG1", "B": "BBB1", "Red": "RRR1", "Green": "GGG1", "Blue": "BBB1"}.get(
                out_name, "LUMA"
            )
            reg = self._emit_swizzle(color, lane)
            return reg

        if ntype == "RGBTOBW":
            color = self.compile_socket(
                node.inputs.get("Color") or (node.inputs[0] if node.inputs else None),
                want="COLOR",
            )
            reg = self._emit_swizzle(color, "LUMA")
            return reg

        if ntype in {"SEPXYZ", "SEPARATE_XYZ"}:
            vector = self._compile_vector(
                node.inputs.get("Vector") or (node.inputs[0] if node.inputs else None)
            )
            mode = {"X": "RRR1", "Y": "GGG1", "Z": "BBB1"}.get(out_name, "LUMA")
            return self._emit_swizzle(vector, mode)

        if ntype in {"COMBXYZ", "COMBINE_XYZ"}:
            return self._compile_combine_xyz(node, want=want)

        if ntype in {"COMBINE_COLOR", "COMBCLR"}:
            return self._compile_combine_color(node, want=want)

        if ntype in {"HUE_SAT", "HUESAT", "HUE_SATURATION"}:
            return self._compile_hue_sat(node, want=want)

        if ntype in {"BRIGHTCONTRAST", "BRIGHTNESSCONTRAST"}:
            return self._compile_bright_contrast(node, want=want)

        if ntype == "GAMMA":
            return self._compile_gamma(node, want=want)

        if ntype == "NORMAL_MAP":
            return self._compile_normal_map(node, want=want)

        if ntype == "BUMP":
            return self._compile_bump(node, want=want)

        if ntype == "DISPLACEMENT":
            return self._compile_displacement(node, want=want)

        if ntype == "VECTOR_DISPLACEMENT":
            return self._compile_vector_displacement(node, want=want)

        if ntype in {"CURVE_RGB", "CURVE_VEC", "CURVE_FLOAT"}:
            return self._compile_curve_map(node, want=want)

        if ntype == "NEW_GEOMETRY":
            return self._compile_geometry(node, output, want=want)

        if ntype == "VECTOR_ROTATE":
            return self._compile_vector_rotate(node, want=want)

        if ntype == "VECT_TRANSFORM":
            return self._compile_vector_transform(node, want=want)

        if ntype == "NORMAL":
            return self._compile_normal_node(node, output, want=want)

        if ntype == "BLACKBODY":
            return self._compile_sampled_color(
                node,
                socket_name="Temperature",
                table=material_ir_tables.BLACKBODY_TABLE,
                domain=material_ir_tables.BLACKBODY_DOMAIN,
                want=want,
            )

        if ntype == "WAVELENGTH":
            return self._compile_sampled_color(
                node,
                socket_name="Wavelength",
                table=material_ir_tables.WAVELENGTH_TABLE,
                domain=material_ir_tables.WAVELENGTH_DOMAIN,
                want=want,
            )

        if ntype == "OBJECT_INFO":
            return self._compile_object_info(out_name, want=want)

        if ntype == "ATTRIBUTE":
            return self._compile_attribute(node, out_name, want=want)

        if ntype == "AMBIENT_OCCLUSION" or str(
            getattr(node, "bl_idname", "") or ""
        ) == "ShaderNodeAmbientOcclusion":
            return self._compile_ambient_occlusion(node, output, want=want)

        if ntype == "BEVEL" or str(getattr(node, "bl_idname", "") or "") == "ShaderNodeBevel":
            return self._compile_bevel(node, want=want)

        # Blender 5.1+ only; older builds have no such node type, and an unknown
        # `type` already falls through to the Cycles refusal at the end.
        if ntype == "RAYCAST" or str(getattr(node, "bl_idname", "") or "") == "ShaderNodeRaycast":
            return self._compile_raycast(node, output, want=want)

        # Newer nodes report bl_idname through `type` rather than a legacy enum
        # name, so match either spelling.
        if ntype in {"RADIAL_TILING", "ShaderNodeRadialTiling"} or str(
            getattr(node, "bl_idname", "") or ""
        ) == "ShaderNodeRadialTiling":
            return self._compile_radial_tiling(node, output, want=want)

        if ntype == "VERTEX_COLOR" or str(getattr(node, "bl_idname", "") or "") == "ShaderNodeVertexColor":
            # "Color Attribute". Its layer_name is empty when the artist leaves it on
            # the mesh's active colour layer, which is what Cycles resolves to.
            layer_name = str(getattr(node, "layer_name", "") or "").strip()
            if not layer_name:
                layer_name = self._active_color_attribute_name()
            if not layer_name:
                self._fail(
                    "Color Attribute has no colour layer to read on the contributing "
                    "meshes. Needs Cycles"
                )
            if not all(self._mesh_color_attribute(obj, layer_name) for obj in self._attribute_objects or ()):
                self._fail(
                    f"Colour attribute '{layer_name}' is missing on at least one "
                    "contributing mesh. Needs Cycles"
                )
            return self._compile_corner_color_attribute(layer_name, out_name, want=want)

        if ntype == "TEX_ENVIRONMENT":
            return self._compile_tex_environment(node, out_name, want=want)

        if ntype == "TANGENT":
            return self._compile_tangent(node, want=want)

        if ntype == "SQUEEZE":
            # Cycles' node_squeeze (intern/cycles/kernel/svm/math.h):
            #   out = 1 / (1 + exp(-((value - center) * width)))
            # A logistic curve, so no new opcode: EXPONENT is already a supported
            # MATH op. Legacy node, but it is one of ours to cover.
            value = self.compile_socket(node.inputs.get("Value"), want="SCALAR")
            width = self.compile_socket(node.inputs.get("Width"), want="SCALAR")
            center = self.compile_socket(node.inputs.get("Center"), want="SCALAR")
            zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
            one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
            shifted = self._emit_math_op("SUBTRACT", value, center)
            scaled = self._emit_math_op("MULTIPLY", shifted, width)
            negated = self._emit_math_op("SUBTRACT", zero, scaled)
            exponent = self._emit_math_op("EXPONENT", negated)
            denominator = self._emit_math_op("ADD", one, exponent)
            result = self._emit_math_op("DIVIDE", one, denominator)
            return result if want == "SCALAR" else self._emit_swizzle(result, "RRR1")

        if ntype == "VOLUME_INFO":
            # Volume Info reads a volume grid. A baked surface has none, so every
            # output is the empty-grid value Cycles reports: zero. Verified in
            # Cycles' svm_node_volume_info, which writes zero for a primitive with
            # no matching volume attribute.
            reg = self._emit_constant((0.0, 0.0, 0.0, 1.0))
            return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

        if ntype == "LIGHT_PATH":
            # A bake evaluates the shader once per texel on a synthetic camera-style
            # ray, so every Light Path output is a constant. Measured with a Cycles
            # bake of each output (EMIT, ROUGHNESS and DIFFUSE color all agree, the
            # DIFFUSE value only being scaled by the Principled diffuse weight):
            # Is Camera Ray = 1 and Ray Length = 1 (the bake ray hits at t = 1);
            # every other flag and every depth counter is 0. See
            # tests/blender_material_ir_cycles_oracle.py, group "lightpath".
            value = _LIGHT_PATH_BAKE_CONSTANTS.get(str(out_name or ""))
            if value is None:
                self._fail(f"Light Path output '{out_name}' is not native yet. Needs Cycles")
            reg = self._emit_constant((value, value, value, 1.0))
            return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

        self._fail(
            f"'{out_name}' is driven by {ntype}. Needs Cycles until more opcodes land"
        )
        raise AssertionError("unreachable")

    def _mix_inputs(self, node):
        ntype = str(getattr(node, "type", "") or "")
        if ntype == "MIX":
            return (
                node.inputs.get("Factor") or node.inputs.get("Fac"),
                node.inputs.get("A") or node.inputs.get("Color1"),
                node.inputs.get("B") or node.inputs.get("Color2"),
            )
        return (
            node.inputs.get("Fac") or node.inputs.get("Factor"),
            node.inputs.get("Color1") or node.inputs.get("A"),
            node.inputs.get("Color2") or node.inputs.get("B"),
        )

    def _emit_saturate_scalar(self, reg: int) -> int:
        """Clamp a scalar register to [0, 1] using the MATH op's existing clamp flag."""
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        return self._emit(
            {
                "op": OPCODE_MATH,
                "dst": self._alloc(),
                "math_op": "ADD",
                "a": int(reg),
                "b": int(zero),
                "fac": int(zero),
                "clamp": True,
            }
        )

    def _emit_saturate_vector(self, reg: int) -> int:
        """Clamp every component of a colour/vector register to [0, 1]."""
        one = self._emit_constant((1.0, 1.0, 1.0, 1.0))
        zero = self._emit_constant((0.0, 0.0, 0.0, 1.0))
        capped = self._emit_vector_math_op("MINIMUM", reg, one)
        return self._emit_vector_math_op("MAXIMUM", capped, zero)

    def _compile_mix(self, node, *, want: str) -> int:
        fac_s, a_s, b_s = self._mix_inputs(node)
        data_type = str(getattr(node, "data_type", "") or "RGBA").upper()
        scalar_data = data_type in {"FLOAT", "VALUE"}
        vector_data = data_type == "VECTOR"
        # Mix (not Mix RGB) in Vector mode can take a per-component factor. The
        # factor socket then is Factor_Vector, and reading it as a scalar (what this
        # did before) keeps only its luminance.
        non_uniform = vector_data and str(
            getattr(node, "factor_mode", "UNIFORM") or "UNIFORM"
        ).upper() == "NON_UNIFORM"
        if scalar_data:
            fac = self.compile_socket(fac_s, want="SCALAR")
            a = self.compile_socket(a_s, want="SCALAR")
            b = self.compile_socket(b_s, want="SCALAR")
        else:
            fac = self.compile_socket(fac_s, want="COLOR" if non_uniform else "SCALAR")
            a = self.compile_socket(a_s, want="COLOR")
            b = self.compile_socket(b_s, want="COLOR")
        blend = str(getattr(node, "blend_type", "MIX") or "MIX").upper()
        if blend not in SUPPORTED_MIX_BLEND_TYPES:
            self._fail(f"Unsupported Mix blend type '{blend}'. Needs Cycles")
        # Clamp Factor is ON by default on every Mix node and the legacy Mix RGB node
        # saturates its factor unconditionally, so ignoring these -- which this did
        # until 2026-08-19 -- diverged from Cycles without the artist touching a thing:
        # a factor driven past 0-1 by a Math node extrapolated past both endpoints
        # instead of stopping at them. See MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G7.
        clamp_factor = getattr(node, "clamp_factor", None)
        if clamp_factor is None:  # legacy Mix RGB: Cycles always saturates the factor
            clamp_factor = True
        if non_uniform:
            if bool(clamp_factor):
                fac = self._emit_saturate_vector(fac)
            # mix(A, B, f) = A * (1 - f) + B * f per component, Blender's own form.
            one = self._emit_constant((1.0, 1.0, 1.0, 1.0))
            inv = self._emit_vector_math_op("SUBTRACT", one, fac)
            reg = self._emit_vector_math_op(
                "ADD",
                self._emit_vector_math_op("MULTIPLY", a, inv),
                self._emit_vector_math_op("MULTIPLY", b, fac),
            )
            if want == "SCALAR":
                return self._emit_swizzle(reg, "LUMA")
            return reg
        if bool(clamp_factor):
            fac = self._emit_saturate_scalar(fac)
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_MIX,
                "dst": dst,
                "a": int(a),
                "b": int(b),
                "fac": int(fac),
                "blend": "MIX" if (scalar_data or vector_data) else blend,
            }
        )
        # Clamp Result on the Mix node, Clamp on the legacy Mix RGB node. Only the
        # colour mode has a result clamp: Float and Vector mixes ignore the flag in
        # Cycles (measured: a FLOAT mix with the flag set kept values past 1.0).
        clamp_result = getattr(node, "clamp_result", None)
        if clamp_result is None:
            clamp_result = getattr(node, "use_clamp", False)
        if bool(clamp_result) and not (scalar_data or vector_data):
            reg = self._emit_saturate_vector(reg)
        if want == "SCALAR" and not scalar_data:
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _normalize_noise_dimensions(self, node) -> str:
        # Prefer the texture-specific enums. Never fall back to Node.dimensions —
        # that is the 2D UI layout size (a Vector), not procedural dimensionality.
        # Wave Texture (Blender 4+/5.x) has no dimension enum; treat it as 3D.
        raw = getattr(node, "noise_dimensions", None)
        if raw is None:
            raw = getattr(node, "voronoi_dimensions", None)
        if raw is None:
            raw = getattr(node, "wave_dimensions", None)
        if raw is None:
            if getattr(node, "bl_idname", "") == "ShaderNodeTexWave":
                return "3D"
            raw = "3D"
        if isinstance(raw, int):
            mapped = {1: "1D", 2: "2D", 3: "3D", 4: "4D"}.get(raw)
            if mapped is None:
                self._fail(f"Unsupported procedural dimensions '{raw}'. Needs Cycles")
            return mapped
        text = str(raw or "3D").strip().upper().replace(" ", "")
        if text.endswith("D") and text[:-1].isdigit():
            return text
        # Blender sometimes stores enum identifiers like '2D' already.
        if text in {"1D", "2D", "3D", "4D"}:
            return text
        self._fail(f"Unsupported procedural dimensions '{raw}'. Needs Cycles")
        raise AssertionError("unreachable")

    def _compile_noise_texture(self, node, output, *, want: str) -> int:
        dimensions = self._normalize_noise_dimensions(node)
        if dimensions not in {"1D", "2D", "3D", "4D"}:
            self._fail(
                f"Noise Texture {dimensions} is not native yet. Needs Cycles "
                "(supported: 1D, 2D, 3D, 4D)"
            )
        noise_type = str(getattr(node, "noise_type", "") or "").strip().upper()
        if noise_type in {"", "PERLIN_FBM", "NOISE_FBM"}:
            noise_type = "FBM"
        if noise_type not in {
            "FBM",
            "MULTIFRACTAL",
            "RIDGED_MULTIFRACTAL",
            "HYBRID_MULTIFRACTAL",
            "HETERO_TERRAIN",
        }:
            self._fail(f"Noise type '{noise_type}' is not native yet. Needs Cycles")
        # An unlinked Vector falls back to Generated, matching Cycles: a Cycles bake
        # of an unlinked Noise and one driven by TexCoord > Generated are identical
        # texel for texel (measured: max diff 0.0 over 14884 texels). The socket
        # default would make the field spatially constant instead.
        # NOTE: White Noise deliberately does NOT share this fallback -- see
        # _compile_white_noise_texture.
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        # W is the 1D coordinate and the 4th axis in 4D (Cycles svm_node_tex_noise
        # scales it alongside the vector). 1D ignores `coord` entirely -- it is still
        # emitted so the op shape stays uniform, and the evaluators never read it.
        # Mirrors _compile_white_noise_texture.
        w = -1
        if dimensions in {"1D", "4D"}:
            w = self.compile_socket(node.inputs.get("W"), want="SCALAR")
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        detail = self.compile_socket(node.inputs.get("Detail"), want="SCALAR")
        roughness = self.compile_socket(node.inputs.get("Roughness"), want="SCALAR")
        distortion = self.compile_socket(node.inputs.get("Distortion"), want="SCALAR")
        lacunarity = self.compile_socket(node.inputs.get("Lacunarity"), want="SCALAR")
        # Offset/Gain feed the fractal variants only. The sockets exist on every
        # Noise node in 4.1+; compile them only when the type reads them so an fBM
        # program's identity (and therefore its cache key) is unchanged.
        noise_offset = -1
        noise_gain = -1
        if noise_type in {"RIDGED_MULTIFRACTAL", "HYBRID_MULTIFRACTAL", "HETERO_TERRAIN"}:
            offset_socket = node.inputs.get("Offset")
            if offset_socket is not None:
                noise_offset = self.compile_socket(offset_socket, want="SCALAR")
        if noise_type in {"RIDGED_MULTIFRACTAL", "HYBRID_MULTIFRACTAL"}:
            gain_socket = node.inputs.get("Gain")
            if gain_socket is not None:
                noise_gain = self.compile_socket(gain_socket, want="SCALAR")
        normalize = bool(getattr(node, "normalize", True))
        out_name = str(getattr(output, "name", "") or "")
        output_mode = "FAC" if out_name.upper() in {"FAC", "FACTOR", "VALUE"} else "COLOR"
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_NOISE_TEXTURE,
                "dst": dst,
                "dimensions": dimensions,
                "coord": int(coord),
                "w": int(w),
                "scale": int(scale),
                "detail": int(detail),
                "roughness": int(roughness),
                "distortion": int(distortion),
                "lacunarity": int(lacunarity),
                "noise_type": noise_type,
                "noise_offset": int(noise_offset),
                "noise_gain": int(noise_gain),
                "normalize": bool(normalize),
                "output": output_mode,
            }
        )
        if output_mode == "FAC":
            # Fac is stored as a broadcast RGB triple; SCALAR want already matches.
            if want == "COLOR":
                return reg
            return reg
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_voronoi_texture(self, node, output, *, want: str) -> int:
        dimensions = self._normalize_noise_dimensions(node)
        if dimensions not in {"1D", "2D", "3D", "4D"}:
            self._fail(
                f"Voronoi Texture {dimensions} is not native yet. Needs Cycles "
                "(supported: 1D, 2D, 3D, 4D)"
            )
        feature = str(getattr(node, "feature", "") or "F1").strip().upper().replace(" ", "_")
        if feature not in {"F1", "F2", "SMOOTH_F1", "DISTANCE_TO_EDGE", "N_SPHERE_RADIUS"}:
            self._fail(
                f"Voronoi feature '{feature}' is not native yet. Needs Cycles "
                "(supported: F1, F2, Smooth F1, Distance to Edge, N-Sphere Radius)"
            )
        metric = str(getattr(node, "distance", "") or getattr(node, "metric", "") or "EUCLIDEAN")
        metric = metric.strip().upper().replace("DISTANCE_", "")
        if metric not in {"EUCLIDEAN", "MANHATTAN", "CHEBYCHEV", "CHEBYSHEV", "MINKOWSKI"}:
            self._fail(f"Voronoi distance metric '{metric}' is not native yet. Needs Cycles")
        if metric == "CHEBYSHEV":
            metric = "CHEBYCHEV"
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        # W is the 1D coordinate and the 4th axis in 4D (Cycles svm_node_tex_voronoi
        # scales it alongside the vector). 1D ignores `coord`; it is still emitted so
        # the op shape stays uniform. Mirrors _compile_white_noise_texture.
        w = -1
        if dimensions in {"1D", "4D"}:
            w = self.compile_socket(node.inputs.get("W"), want="SCALAR")
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        randomness = self.compile_socket(node.inputs.get("Randomness"), want="SCALAR")
        detail = self.compile_socket(node.inputs.get("Detail"), want="SCALAR")
        roughness = self.compile_socket(node.inputs.get("Roughness"), want="SCALAR")
        lacunarity = self.compile_socket(node.inputs.get("Lacunarity"), want="SCALAR")
        if feature == "SMOOTH_F1":
            smoothness = self.compile_socket(node.inputs.get("Smoothness"), want="SCALAR")
        else:
            smoothness = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
        if metric == "MINKOWSKI":
            exponent = self.compile_socket(node.inputs.get("Exponent"), want="SCALAR")
        else:
            exponent = self._emit_swizzle(self._emit_constant((0.5, 0.5, 0.5, 1.0)), "LUMA")
        out_name = str(getattr(output, "name", "") or "").strip().upper()
        if out_name in {"COLOR"}:
            output_mode = "COLOR"
        elif out_name in {"POSITION"}:
            output_mode = "POSITION"
        elif out_name == "W":
            # W is the 4th component of the winning feature point, transported the same
            # way Position transports the first three: the shader carries w through every
            # voronoi_1/2/3/4 producer and divides by scale in the fractal wrapper, exactly
            # as Cycles' fractal_voronoi_x_fx does.
            #
            # Verified 2026-08-21 by flat-quad f(UV) parity against a transcription of
            # Cycles' voronoi_f1 + hash_pcg4d_i: 900 samples across a 512^2 sheet, max
            # absolute error 0.00196 -- half of the 8-bit quantisation step -- with native
            # spread std 0.0491 against 0.0490 for the reference. 1D W is byte-identical to
            # the Cycles route. An earlier measurement on curved geometry suggested a 6x
            # under-variation and this branch was briefly backed out; that reading was an
            # artefact of the test setup, not of the shader.
            output_mode = "W"
        else:
            output_mode = "DISTANCE"
        if feature in {"DISTANCE_TO_EDGE", "N_SPHERE_RADIUS"} and output_mode in {
            "COLOR",
            "POSITION",
            "W",
        }:
            # Blender hides these sockets for both features, so this is unreachable from
            # the UI; it guards a hand-built node tree, where the feature never assigns a
            # feature point and W/Color/Position would read whatever the initialiser left.
            self._fail(
                f"Voronoi {feature} only exposes Distance/Radius natively. Needs Cycles for Color/Position/W"
            )
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_VORONOI_TEXTURE,
                "dst": dst,
                "dimensions": dimensions,
                "feature": feature,
                "metric": metric,
                "coord": int(coord),
                "w": int(w),
                "scale": int(scale),
                "randomness": int(randomness),
                "exponent": int(exponent),
                "detail": int(detail),
                "roughness": int(roughness),
                "lacunarity": int(lacunarity),
                "smoothness": int(smoothness),
                # Blender's Voronoi Normalize defaults to False (Noise's defaults to
                # True); the backend job parser defaults a missing field to True, so
                # Voronoi must always emit it explicitly.
                "normalize": bool(getattr(node, "normalize", False)),
                "output": output_mode,
            }
        )
        if output_mode == "DISTANCE":
            return reg
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_white_noise_texture(self, node, output, *, want: str) -> int:
        dimensions = self._normalize_noise_dimensions(node)
        if dimensions not in {"1D", "2D", "3D", "4D"}:
            self._fail(
                f"White Noise Texture {dimensions} is not native yet. Needs Cycles "
                "(supported: 1D, 2D, 3D, 4D)"
            )
        # Unlike every other texture node, an unlinked Vector here is NOT the
        # Generated fallback -- Cycles reads the socket default. Measured: a Cycles
        # bake of an unlinked White Noise is flat 0.6111, while the same node driven
        # by Generated varies (0.4207..0.5783). Do not "make this consistent" with
        # _compile_noise_texture; the inconsistency is Cycles' own.
        coord = self._compile_vector_value(node.inputs.get("Vector"))
        w = self.compile_socket(node.inputs.get("W"), want="SCALAR")
        out_name = str(getattr(output, "name", "") or "")
        output_mode = "VALUE" if out_name.upper() in {"FAC", "FACTOR", "VALUE"} else "COLOR"
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_WHITE_NOISE_TEXTURE,
                "dst": dst,
                "dimensions": dimensions,
                "coord": int(coord),
                "w": int(w),
                "output": output_mode,
            }
        )
        if output_mode == "VALUE":
            return reg
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_magic_texture(self, node, output, *, want: str) -> int:
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        distortion = self.compile_socket(node.inputs.get("Distortion"), want="SCALAR")
        try:
            depth = int(getattr(node, "turbulence_depth", getattr(node, "depth", 2)))
        except Exception:
            depth = 2
        depth = max(0, min(depth, 10))
        out_name = str(getattr(output, "name", "") or "")
        output_mode = "FAC" if out_name.upper() in {"FAC", "FACTOR", "VALUE"} else "COLOR"
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_MAGIC_TEXTURE,
                "dst": dst,
                "coord": int(coord),
                "scale": int(scale),
                "distortion": int(distortion),
                "steps": int(depth),
                "output": output_mode,
            }
        )
        if output_mode == "FAC":
            return reg
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_gabor_texture(self, node, output, *, want: str) -> int:
        # Cycles svm_node_tex_gabor. 2D sums 8 impulses over a 3x3 cell
        # neighbourhood, 3D over 3x3x3 -- 72 and 216 kernel evaluations per
        # texel respectively, which is why the type is part of the op rather
        # than a runtime branch.
        gabor_type = str(getattr(node, "gabor_type", "") or "2D").strip().upper()
        if gabor_type not in {"2D", "3D"}:
            self._fail(f"Gabor type '{gabor_type}' is not native yet. Needs Cycles")
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        frequency = self.compile_socket(node.inputs.get("Frequency"), want="SCALAR")
        anisotropy = self.compile_socket(node.inputs.get("Anisotropy"), want="SCALAR")
        # Both orientation sockets are literally named "Orientation" (one is
        # hidden per gabor_type), so a name lookup returns the wrong one for 3D.
        # Pick by socket type instead.
        orientation_sockets = [
            sock for sock in getattr(node, "inputs", ())
            if str(getattr(sock, "name", "")).startswith("Orientation")
        ]
        socket_2d = next(
            (sock for sock in orientation_sockets if getattr(sock, "type", "") == "VALUE"), None
        )
        socket_3d = next(
            (sock for sock in orientation_sockets if getattr(sock, "type", "") == "VECTOR"), None
        )
        orientation_2d = self.compile_socket(socket_2d, want="SCALAR")
        orientation_3d = self._compile_vector_value(socket_3d, fallback=(0.0, 0.0, 1.0))
        out_name = str(getattr(output, "name", "") or "").strip().upper()
        if out_name == "PHASE":
            output_mode = "PHASE"
        elif out_name == "INTENSITY":
            output_mode = "INTENSITY"
        else:
            output_mode = "VALUE"
        dst = self._alloc()
        return self._emit(
            {
                "op": OPCODE_GABOR_TEXTURE,
                "dst": dst,
                "gabor_type": gabor_type,
                "coord": int(coord),
                "scale": int(scale),
                "frequency": int(frequency),
                "anisotropy": int(anisotropy),
                "orientation_2d": int(orientation_2d),
                "orientation_3d": int(orientation_3d),
                "output": output_mode,
            }
        )

    def _compile_wave_texture(self, node, output, *, want: str) -> int:
        dimensions = self._normalize_noise_dimensions(node)
        if dimensions not in {"2D", "3D"}:
            self._fail(
                f"Wave Texture {dimensions} is not native yet. Needs Cycles "
                "(supported: 2D, 3D)"
            )
        wave_type = str(getattr(node, "wave_type", "") or "BANDS").strip().upper()
        if wave_type not in {"BANDS", "RINGS"}:
            self._fail(f"Wave type '{wave_type}' is not native yet. Needs Cycles")
        bands_dir = str(getattr(node, "bands_direction", "") or "X").strip().upper()
        rings_dir = str(getattr(node, "rings_direction", "") or "X").strip().upper()
        profile = str(getattr(node, "wave_profile", "") or "SIN").strip().upper()
        if profile in {"TRI", "TRIANGLE"}:
            profile = "TRI"
        if profile not in {"SIN", "SAW", "TRI"}:
            self._fail(f"Wave profile '{profile}' is not native yet. Needs Cycles")
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        distortion = self.compile_socket(node.inputs.get("Distortion"), want="SCALAR")
        detail = self.compile_socket(node.inputs.get("Detail"), want="SCALAR")
        detail_scale = self.compile_socket(
            node.inputs.get("Detail Scale") or node.inputs.get("DetailScale"),
            want="SCALAR",
        )
        detail_roughness = self.compile_socket(
            node.inputs.get("Detail Roughness") or node.inputs.get("DetailRoughness"),
            want="SCALAR",
        )
        phase = self.compile_socket(
            node.inputs.get("Phase Offset") or node.inputs.get("PhaseOffset"),
            want="SCALAR",
        )
        out_name = str(getattr(output, "name", "") or "")
        output_mode = "FAC" if out_name.upper() in {"FAC", "FACTOR", "VALUE"} else "COLOR"
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_WAVE_TEXTURE,
                "dst": dst,
                "dimensions": dimensions,
                "wave_type": wave_type,
                "bands_dir": bands_dir,
                "rings_dir": rings_dir,
                "profile": profile,
                "coord": int(coord),
                "scale": int(scale),
                "distortion": int(distortion),
                "detail": int(detail),
                "detail_scale": int(detail_scale),
                "roughness": int(detail_roughness),
                "phase": int(phase),
                "output": output_mode,
            }
        )
        if want == "SCALAR":
            return reg
        return reg

    def _compile_gradient_texture(self, node, output, *, want: str) -> int:
        gradient_type = str(getattr(node, "gradient_type", "") or "LINEAR").strip().upper()
        allowed = {
            "LINEAR",
            "QUADRATIC",
            "EASING",
            "DIAGONAL",
            "RADIAL",
            "SPHERICAL",
            "QUADRATIC_SPHERE",
        }
        if gradient_type not in allowed:
            self._fail(f"Gradient type '{gradient_type}' is not native yet. Needs Cycles")
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        out_name = str(getattr(output, "name", "") or "")
        output_mode = "FAC" if out_name.upper() in {"FAC", "FACTOR", "VALUE"} else "COLOR"
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_GRADIENT_TEXTURE,
                "dst": dst,
                "coord": int(coord),
                "gradient_type": gradient_type,
                "output": output_mode,
            }
        )
        return reg

    def _compile_checker_texture(self, node, output, *, want: str) -> int:
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        color1 = self.compile_socket(node.inputs.get("Color1"), want="COLOR")
        color2 = self.compile_socket(node.inputs.get("Color2"), want="COLOR")
        out_name = str(getattr(output, "name", "") or "")
        output_mode = "FAC" if out_name.upper() in {"FAC", "FACTOR", "VALUE"} else "COLOR"
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_CHECKER_TEXTURE,
                "dst": dst,
                "coord": int(coord),
                "scale": int(scale),
                "a": int(color1),
                "b": int(color2),
                "output": output_mode,
            }
        )
        if want == "SCALAR" and output_mode == "COLOR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_brick_texture(self, node, output, *, want: str) -> int:
        coord = self._compile_vector(
            node.inputs.get("Vector"), default_attr=OPCODE_ATTR_GENERATED
        )
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        color1 = self.compile_socket(node.inputs.get("Color1"), want="COLOR")
        color2 = self.compile_socket(node.inputs.get("Color2"), want="COLOR")
        mortar = self.compile_socket(node.inputs.get("Mortar"), want="COLOR")
        mortar_size = self.compile_socket(
            node.inputs.get("Mortar Size") or node.inputs.get("MortarSize"),
            want="SCALAR",
        )
        mortar_smooth = self.compile_socket(
            node.inputs.get("Mortar Smooth") or node.inputs.get("MortarSmooth"),
            want="SCALAR",
        )
        bias = self.compile_socket(node.inputs.get("Bias"), want="SCALAR")
        brick_width = self.compile_socket(
            node.inputs.get("Brick Width") or node.inputs.get("BrickWidth"),
            want="SCALAR",
        )
        row_height = self.compile_socket(
            node.inputs.get("Row Height") or node.inputs.get("RowHeight"),
            want="SCALAR",
        )
        # No `or default` here: Offset 0 and Squash 0 are legal node values.
        try:
            brick_offset = float(getattr(node, "offset", 0.5))
        except Exception:
            brick_offset = 0.5
        try:
            brick_squash = float(getattr(node, "squash", 1.0))
        except Exception:
            brick_squash = 1.0
        try:
            brick_offset_freq = int(getattr(node, "offset_frequency", 2) or 2)
        except Exception:
            brick_offset_freq = 2
        try:
            brick_squash_freq = int(getattr(node, "squash_frequency", 2) or 2)
        except Exception:
            brick_squash_freq = 2
        out_name = str(getattr(output, "name", "") or "")
        output_mode = "FAC" if out_name.upper() in {"FAC", "FACTOR", "VALUE"} else "COLOR"
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_BRICK_TEXTURE,
                "dst": dst,
                "coord": int(coord),
                "scale": int(scale),
                "a": int(color1),
                "b": int(color2),
                "mortar": int(mortar),
                "mortar_size": int(mortar_size),
                "mortar_smooth": int(mortar_smooth),
                "bias": int(bias),
                "brick_width": int(brick_width),
                "row_height": int(row_height),
                "brick_offset": float(brick_offset),
                "brick_squash": float(brick_squash),
                "brick_offset_freq": int(brick_offset_freq),
                "brick_squash_freq": int(brick_squash_freq),
                "output": output_mode,
            }
        )
        if want == "SCALAR" and output_mode == "COLOR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_math(self, node, *, want: str) -> int:
        operation = str(getattr(node, "operation", "") or "").upper()
        if operation not in SUPPORTED_MATH_OPS:
            self._fail(f"Unsupported Math operation '{operation}'. Needs Cycles")
        inputs = list(getattr(node, "inputs", ()) or ())
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        a = self.compile_socket(inputs[0] if inputs else None, want="SCALAR")
        if operation in MATH_UNARY_OPS:
            b = zero
        else:
            b = self.compile_socket(inputs[1] if len(inputs) > 1 else None, want="SCALAR")
        if operation in MATH_TERNARY_OPS:
            c = self.compile_socket(inputs[2] if len(inputs) > 2 else None, want="SCALAR")
        else:
            c = zero
        dst = self._alloc()
        use_clamp = bool(getattr(node, "use_clamp", False))
        reg = self._emit(
            {
                "op": OPCODE_MATH,
                "dst": dst,
                "math_op": operation,
                "a": int(a),
                "b": int(b),
                # Value3 rides the shared factor slot so the GPU packer needs no new lane.
                "fac": int(c),
                "clamp": bool(use_clamp),
            }
        )
        return reg

    def _emit_math_op(self, operation: str, a: int, b: int | None = None) -> int:
        """Emit one scalar MATH op between registers."""
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        return self._emit(
            {
                "op": OPCODE_MATH,
                "dst": self._alloc(),
                "math_op": operation,
                "a": int(a),
                "b": int(zero if b is None else b),
                "fac": int(zero),
                "clamp": False,
            }
        )

    def _emit_color_space(self, src: int, direction: str) -> int:
        """RGB <-> HSV / HSL. `direction` is one of the four conversion names."""
        return self._emit(
            {
                "op": OPCODE_COLOR_SPACE,
                "dst": self._alloc(),
                "src": int(src),
                "mode": str(direction),
            }
        )

    def _emit_vector_math_op(self, operation: str, a: int, b: int | None = None,
                             c: int | None = None) -> int:
        zero = self._emit_constant((0.0, 0.0, 0.0, 1.0))
        return self._emit(
            {
                "op": OPCODE_VECTOR_MATH,
                "dst": self._alloc(),
                "math_op": operation,
                "a": int(a),
                "b": int(zero if b is None else b),
                "fac": int(zero if c is None else c),
            }
        )

    def _encode_world_normal_as_tangent(self, world_normal: int, *,
                                        flip_green: bool = False,
                                        low_frame: bool = False) -> int:
        """World-space shading normal -> tangent space, 0-1 encoded.

        Everything feeding the Principled Normal socket -- Bump, Normal Map in any
        space, an unlinked socket -- leaves a WORLD-space normal, because that is
        what the shading context holds. Cycles' NORMAL bake converts the final
        shading normal to tangent space and encodes it, so the channel has to do the
        same or the two routes disagree. Measured before this existed: Cycles read a
        flat (0,0,1) on a curved surface while Fyr followed the geometry.

        The IR has TANGENT_TO_WORLD but no inverse. For an orthonormal basis the
        inverse is the transpose, so the basis vectors are recovered by sending the
        unit axes through TANGENT_TO_WORLD and the transform is three dot products.
        Costs ~13 ops and needs no new opcode, wire field or shader change.

        ``flip_green`` is the row's DirectX convention. It has to be applied HERE,
        between the conversion and the encode, because negating Y in world space is
        not the same thing as flipping green in tangent space. This was written up as
        needing a backend change (the `apply_channel_flips` the geometry normal map
        gets, which the material-IR write path never calls) -- but the conversion the
        flip has to follow is right here in the IR, so it costs one op and no rebuild.

        ``low_frame`` selects WHICH tangent space. TANGENT_TO_WORLD builds its frame
        around the HIGH hit's shading normal, which is right for a Normal Map node in
        the high material and for the MATERIAL row (the material's own normal detail,
        not the high-vs-low geometry). A Normal MAP is decoded by the renderer in the
        LOW's tangent space, so a Normal row baked through this channel asks the
        backend for exactly the conversion the geometry Normal map uses. Measured
        without it on a faceted high under a smooth-shaded low: every facet baked back
        in as a hard line, because the encode cancelled exactly the geometric
        difference the map exists to carry.
        """
        if low_frame:
            # One op: the backend applies the exact inverse of the low's interpolated
            # basis (`"frame": "LOW"` turns TANGENT_TO_WORLD around). The three-axis
            # transpose below is only an inverse for an orthonormal frame, which a low
            # with sheared UVs does not have.
            tangent_normal = self._emit(
                {
                    "op": OPCODE_TANGENT_TO_WORLD,
                    "dst": self._alloc(),
                    "fac": int(world_normal),
                    "frame": "LOW",
                }
            )
        else:
            axes = []
            for axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
                unit = self._emit_constant(axis + (1.0,))
                axes.append(
                    self._emit(
                        {"op": OPCODE_TANGENT_TO_WORLD, "dst": self._alloc(), "fac": int(unit)}
                    )
                )
            # DOT_PRODUCT broadcasts its scalar across xyz, so each component feeds
            # COMBINE_XYZ directly.
            components = [
                self._emit_vector_math_op("DOT_PRODUCT", world_normal, axis) for axis in axes
            ]
            tangent_normal = self._emit(
                {
                    "op": OPCODE_COMBINE_XYZ,
                    "dst": self._alloc(),
                    "a": int(components[0]),
                    "b": int(components[1]),
                    "fac": int(components[2]),
                }
            )
        half = self._emit_constant((0.5, 0.5, 0.5, 1.0))
        # Folded into the same MULTIPLY that halves the vector: DirectX costs one
        # extra CONSTANT over OpenGL and no extra arithmetic. The +0.5 offset stays
        # unsigned, so green mirrors about the midpoint rather than going negative.
        scale = self._emit_constant((0.5, -0.5, 0.5, 1.0)) if flip_green else half
        scaled = self._emit_vector_math_op("MULTIPLY", tangent_normal, scale)
        return self._emit_vector_math_op("ADD", scaled, half)

    def _emit_mix_regs(self, a: int, b: int, fac: int) -> int:
        return self._emit(
            {
                "op": OPCODE_MIX,
                "dst": self._alloc(),
                "a": int(a),
                "b": int(b),
                "fac": int(fac),
                "blend": "MIX",
            }
        )

    def _scale_color(self, color_reg: int, scalar_reg: int) -> int:
        return self._emit_vector_math_op("MULTIPLY", color_reg, scalar_reg)

    def _shader_channel_neutral(self, channel: str, want: str) -> int:
        """Contribution of a missing Mix/Add Shader branch for *channel*."""
        if channel == constants.MATERIAL_CHANNEL_OPACITY:
            rgba = (1.0, 1.0, 1.0, 1.0)
        elif channel == constants.MATERIAL_CHANNEL_NORMAL:
            return self._emit({"op": OPCODE_ATTR_NORMAL, "dst": self._alloc()})
        else:
            rgba = (0.0, 0.0, 0.0, 1.0)
        result = self._emit_constant(rgba)
        if want == "SCALAR":
            return self._emit_swizzle(result, "LUMA")
        return result

    def _compile_principled_channel(self, node, channel: str, want: str) -> int:
        socket_name = CHANNEL_TO_PRINCIPLED[channel]
        socket = node.inputs.get(socket_name)
        if socket is None:
            self._fail(f"Principled '{socket_name}' is missing")
        if channel == constants.MATERIAL_CHANNEL_NORMAL and not bool(
            getattr(socket, "is_linked", False)
        ):
            return self._emit({"op": OPCODE_ATTR_NORMAL, "dst": self._alloc()})
        if not bool(getattr(socket, "is_linked", False)):
            result = self._emit_constant(_socket_default_rgba(socket))
            if want == "SCALAR":
                result = self._emit_swizzle(result, "LUMA")
        else:
            result = self.compile_socket(socket, want=want)
        if channel == constants.MATERIAL_CHANNEL_EMISSION:
            strength_socket = node.inputs.get("Emission Strength")
            if strength_socket is not None:
                strength = self.compile_socket(strength_socket, want="SCALAR")
                result = self._scale_color(result, strength)
        return result

    def _compile_emission_shader(self, node, channel: str, want: str) -> int:
        if channel == constants.MATERIAL_CHANNEL_EMISSION:
            color = self.compile_socket(node.inputs.get("Color"), want="COLOR")
            strength = self.compile_socket(node.inputs.get("Strength"), want="SCALAR")
            result = self._scale_color(color, strength)
            if want == "SCALAR":
                return self._emit_swizzle(result, "LUMA")
            return result
        if channel == constants.MATERIAL_CHANNEL_OPACITY:
            result = self._emit_constant((1.0, 1.0, 1.0, 1.0))
            return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result
        if channel == constants.MATERIAL_CHANNEL_NORMAL:
            return self._emit({"op": OPCODE_ATTR_NORMAL, "dst": self._alloc()})
        return self._shader_channel_neutral(channel, want)

    def _compile_shader_group_output(self, group_node, output, channel: str, want: str) -> int:
        """Follow a SHADER link into a node group, to the closure feeding its output.

        The value-socket twin is `_compile_group_output`; this is the same walk for a
        closure. Shader libraries (ZenBBQ's preview shader is the case that prompted
        it) wrap the whole surface in a group, and without this the channel stopped at
        "Surface shader 'GROUP' is not native" with a perfectly native graph inside.
        """
        if self._group_depth >= 16:
            self._fail("Material node-group nesting is too deep for native Material IR")
        tree = getattr(group_node, "node_tree", None)
        group_output = self._group_output_node(tree)
        if tree is None or group_output is None:
            self._fail("Material node group has no active Group Output. Needs Cycles")
        inner = self._matching_socket(getattr(group_output, "inputs", None), output)
        if inner is None:
            index = -1
            try:
                index = list(getattr(group_node, "outputs", []) or []).index(output)
            except Exception:
                index = -1
            if index < 0 and output is None:
                index = 0
            inner = self._socket_at_index(getattr(group_output, "inputs", None), index)
        if inner is None:
            self._fail("Material node group output cannot be mapped. Needs Cycles")
        self._group_depth += 1
        self._group_input_stack.append({"node": group_node})
        try:
            return self._compile_shader_socket(inner, channel, want)
        finally:
            self._group_input_stack.pop()
            self._group_depth -= 1

    def _compile_shader_group_input(self, node, output, channel: str, want: str) -> int:
        """A closure arriving through a Group Input: compile the enclosing group's socket."""
        if not self._group_input_stack:
            self._fail("Unbound Group Input in Material IR graph. Needs Cycles")
        group_node = self._group_input_stack[-1]["node"]
        outer = self._matching_socket(getattr(group_node, "inputs", None), output)
        if outer is None:
            index = -1
            try:
                index = list(getattr(node, "outputs", []) or []).index(output)
            except Exception:
                index = -1
            outer = self._socket_at_index(getattr(group_node, "inputs", None), index)
        if outer is None:
            self._fail("Material node group input cannot be mapped. Needs Cycles")
        # Same frame discipline as _compile_group_input_output: the outer socket lives
        # in the ENCLOSING tree, so this frame comes off the stack while it compiles.
        frame = self._group_input_stack.pop()
        self._group_depth -= 1
        try:
            return self._compile_shader_socket(outer, channel, want)
        finally:
            self._group_depth += 1
            self._group_input_stack.append(frame)

    def _compile_shader_closure(self, node, channel: str, want: str, output=None) -> int:
        if node is None:
            return self._shader_channel_neutral(channel, want)
        ntype = str(getattr(node, "type", "") or "")
        bl_id = str(getattr(node, "bl_idname", "") or "")
        # Fyr Material Capture is a CustomGroup passthrough. Compiling its private
        # Group Input→Output wire without following the outer Shader link refused
        # every Sanctus-style graph as "Surface shader 'CUSTOM GROUP' is not native".
        if bl_id == constants.FYR_CAPTURE_NODE_ID and not bool(getattr(node, "mute", False)):
            inputs = getattr(node, "inputs", None)
            shader_in = inputs.get("Shader") if hasattr(inputs, "get") else None
            if shader_in is None and inputs:
                shader_in = inputs[0]
            return self._compile_shader_socket(shader_in, channel, want)
        if ntype == "GROUP" and not bool(getattr(node, "mute", False)):
            return self._compile_shader_group_output(node, output, channel, want)
        if ntype == "GROUP_INPUT":
            return self._compile_shader_group_input(node, output, channel, want)
        if ntype == "REROUTE":
            return self._compile_shader_socket(
                node.inputs[0] if node.inputs else None, channel, want
            )
        # A muted shader node is a wire too -- a muted Mix Shader passes its first
        # shader input through, exactly as Cycles renders it.
        if bool(getattr(node, "mute", False)):
            passthrough = self._muted_passthrough_socket(
                node, node.outputs[0] if getattr(node, "outputs", None) else None
            )
            if passthrough is not None:
                return self._compile_shader_socket(passthrough, channel, want)
            return self._shader_channel_neutral(channel, want)
        if ntype == "MIX_SHADER":
            fac_socket = node.inputs.get("Fac") or (node.inputs[0] if node.inputs else None)
            fac = self.compile_socket(fac_socket, want="SCALAR")
            a = self._compile_shader_socket(
                node.inputs.get("Shader") or (node.inputs[1] if len(node.inputs) > 1 else None),
                channel,
                want,
            )
            b = self._compile_shader_socket(
                node.inputs.get("Shader_001")
                or (node.inputs[2] if len(node.inputs) > 2 else None),
                channel,
                want,
            )
            return self._emit_mix_regs(a, b, fac)
        if ntype == "ADD_SHADER":
            a = self._compile_shader_socket(
                node.inputs.get("Shader") or (node.inputs[0] if node.inputs else None),
                channel,
                want,
            )
            b = self._compile_shader_socket(
                node.inputs.get("Shader_001")
                or (node.inputs[1] if len(node.inputs) > 1 else None),
                channel,
                want,
            )
            if channel == constants.MATERIAL_CHANNEL_EMISSION:
                return self._emit_vector_math_op("ADD", a, b)
            if channel == constants.MATERIAL_CHANNEL_OPACITY:
                one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
                return self._emit_math_op("MINIMUM", one, self._emit_math_op("ADD", a, b))
            # Albedo/other: Mix at 0.5 so two closures don't blow out.
            half = self._emit_swizzle(self._emit_constant((0.5, 0.5, 0.5, 1.0)), "LUMA")
            return self._emit_mix_regs(a, b, half)
        if ntype == "BSDF_PRINCIPLED":
            return self._compile_principled_channel(node, channel, want)
        if ntype == "EMISSION":
            return self._compile_emission_shader(node, channel, want)
        if ntype == "BACKGROUND":
            # Same two sockets as Emission (Color x Strength) and the same meaning
            # when it is wired to Surface, which is the only socket compiled here.
            return self._compile_emission_shader(node, channel, want)
        if ntype in {"BSDF_TRANSPARENT", "BSDF_RAY_PORTAL", "HOLDOUT"}:
            # All three let the ray past without shading it: Transparent by
            # definition, Ray Portal by teleporting it, Holdout by cutting the
            # surface out of the frame. Opacity 0 is what that is in a PBR set.
            if channel == constants.MATERIAL_CHANNEL_OPACITY:
                result = self._emit_constant((0.0, 0.0, 0.0, 1.0))
                return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result
            return self._shader_channel_neutral(channel, want)
        if ntype in _VOLUME_CLOSURE_TYPES:
            # A volume closure carries no surface. Reaching this function at all
            # means one was wired into the Material Output's *Surface* socket --
            # only that socket is compiled -- which is a degenerate graph. Treat it
            # as a branch that contributes nothing, exactly like a missing Mix
            # Shader input, so the rest of the material still bakes natively
            # instead of dragging the whole channel to Cycles.
            return self._shader_channel_neutral(channel, want)
        if ntype == "EEVEE_SPECULAR":
            return self._compile_eevee_specular(node, channel, want)
        if ntype == "BSDF_HAIR_PRINCIPLED":
            return self._compile_principled_hair(node, channel, want)
        if ntype == "BSDF_DIFFUSE":
            if channel == constants.MATERIAL_CHANNEL_ALBEDO:
                return self.compile_socket(node.inputs.get("Color"), want=want)
            if channel == constants.MATERIAL_CHANNEL_OPACITY:
                result = self._emit_constant((1.0, 1.0, 1.0, 1.0))
                return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result
            if channel == constants.MATERIAL_CHANNEL_NORMAL:
                return self._closure_normal_channel(node, want)
            return self._shader_channel_neutral(channel, want)
        sources = _CLOSURE_CHANNEL_SOURCES.get(ntype)
        if sources is not None:
            return self._compile_mapped_closure(node, sources, channel, want)
        implicit = self._compile_implicit_emission(node, output, channel, want)
        if implicit is not None:
            return implicit
        self._fail(f"Surface shader '{ntype}' is not native yet. Needs Cycles")
        raise AssertionError("unreachable")

    _IMPLICIT_EMISSION_SOCKET_TYPES = frozenset({"RGBA", "VALUE", "VECTOR"})

    def _compile_implicit_emission(self, node, output, channel: str, want: str):
        """A colour, value or vector wired straight into a shader socket.

        Blender inserts an Emission shader at strength 1 for that link when it
        builds the render tree (the implicit closure cast), so the colour is the
        material's emission and nothing else. Returns None when *output* is not a
        plain data socket, which leaves real unsupported closures refused.
        """
        socket_type = str(getattr(output, "type", "") or "").upper()
        if socket_type not in self._IMPLICIT_EMISSION_SOCKET_TYPES:
            return None
        if channel == constants.MATERIAL_CHANNEL_EMISSION:
            return self._compile_node_output(node, output, want=want)
        if channel == constants.MATERIAL_CHANNEL_OPACITY:
            result = self._emit_constant((1.0, 1.0, 1.0, 1.0))
            return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result
        if channel == constants.MATERIAL_CHANNEL_NORMAL:
            return self._emit({"op": OPCODE_ATTR_NORMAL, "dst": self._alloc()})
        return self._shader_channel_neutral(channel, want)

    def _compile_eevee_specular(self, node, channel: str, want: str) -> int:
        """Specular BSDF -> PBR channels.

        This closure is already a PBR set, just spelled the other way round: it
        states reflectance as an F0 *colour* where Principled states it as the
        0..1 "Specular IOR Level", and it states coverage as Transparency where
        Principled states Alpha. Both are exact conversions, not approximations:

        * ``Specular IOR Level = luminance(F0) / 0.08`` is the inverse of
          Principled's own ``F0 = 0.08 * level`` (level 0.5 -> F0 0.04).
        * ``Alpha = 1 - Transparency``.
        """
        if channel == constants.MATERIAL_CHANNEL_NORMAL:
            return self._closure_normal_channel(node, want)
        if channel == constants.MATERIAL_CHANNEL_ALBEDO:
            return self.compile_socket(node.inputs.get("Base Color"), want=want)
        if channel == constants.MATERIAL_CHANNEL_ROUGHNESS:
            return self.compile_socket(node.inputs.get("Roughness"), want=want)
        if channel == constants.MATERIAL_CHANNEL_EMISSION:
            return self.compile_socket(node.inputs.get("Emissive Color"), want=want)
        if channel == constants.MATERIAL_CHANNEL_OPACITY:
            transparency = self.compile_socket(node.inputs.get("Transparency"), want="SCALAR")
            one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
            result = self._emit_math_op("SUBTRACT", one, transparency)
            return result if want == "SCALAR" else self._emit_swizzle(result, "RRR1")
        if channel == constants.MATERIAL_CHANNEL_SPECULAR:
            f0 = self.compile_socket(node.inputs.get("Specular"), want="SCALAR")
            inv = self._emit_swizzle(
                self._emit_constant((1.0 / 0.08, 1.0 / 0.08, 1.0 / 0.08, 1.0)), "LUMA"
            )
            level = self._emit_math_op("MULTIPLY", f0, inv)
            zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
            one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
            level = self._emit_math_op("MINIMUM", one, self._emit_math_op("MAXIMUM", zero, level))
            return level if want == "SCALAR" else self._emit_swizzle(level, "RRR1")
        return self._shader_channel_neutral(channel, want)

    def _compile_principled_hair(self, node, channel: str, want: str) -> int:
        """Principled Hair BSDF, for the parametrization that states a colour.

        ``parametrization`` picks where the fibre's colour comes from. Only
        ``COLOR`` (Direct Coloration) carries one the IR can read straight off a
        socket. ``MELANIN`` and ``ABSORPTION`` state an absorption coefficient
        instead, and the colour a viewer sees is the result of the scattering
        model integrating that coefficient along the fibre -- deriving it here
        would be inventing a number, so those two route to Cycles, which runs the
        real model.
        """
        if channel == constants.MATERIAL_CHANNEL_NORMAL:
            return self._closure_normal_channel(node, want)
        parametrization = str(getattr(node, "parametrization", "COLOR") or "COLOR").strip().upper()
        if parametrization != "COLOR":
            self._fail(
                f"Principled Hair parametrization '{parametrization.title()}' states an "
                "absorption coefficient, not a colour. Needs Cycles"
            )
        if channel == constants.MATERIAL_CHANNEL_ALBEDO:
            return self.compile_socket(node.inputs.get("Color"), want=want)
        if channel == constants.MATERIAL_CHANNEL_ROUGHNESS:
            return self.compile_socket(node.inputs.get("Roughness"), want=want)
        return self._shader_channel_neutral(channel, want)

    def _closure_normal_channel(self, node, want: str) -> int:
        """NORMAL for any closure: its Normal input when driven, else the shading normal."""
        normal_socket = node.inputs.get("Normal")
        if normal_socket is not None and bool(getattr(normal_socket, "is_linked", False)):
            return self.compile_socket(normal_socket, want=want)
        return self._emit({"op": OPCODE_ATTR_NORMAL, "dst": self._alloc()})

    def _compile_mapped_closure(self, node, sources, channel: str, want: str) -> int:
        """One channel of a non-Principled closure, via `_CLOSURE_CHANNEL_SOURCES`.

        These used to refuse, which sent the whole material to Cycles -- where a
        non-Principled surface has no resolvable Base Color socket and every
        channel baked pure black with no error at all. Flattening them here keeps
        them on the native path and, more importantly, makes them produce the
        value the artist authored.
        """
        if channel == constants.MATERIAL_CHANNEL_NORMAL:
            return self._closure_normal_channel(node, want)
        source = sources.get(channel)
        if source is None:
            return self._shader_channel_neutral(channel, want)
        if isinstance(source, (int, float)):
            value = float(source)
            result = self._emit_constant((value, value, value, 1.0))
            return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result
        socket = node.inputs.get(str(source))
        if socket is None:
            return self._shader_channel_neutral(channel, want)
        if not bool(getattr(socket, "is_linked", False)):
            result = self._emit_constant(_socket_default_rgba(socket))
            return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result
        return self.compile_socket(socket, want=want)

    def _compile_shader_socket(self, socket, channel: str, want: str) -> int:
        if socket is None or not bool(getattr(socket, "is_linked", False)):
            return self._shader_channel_neutral(channel, want)
        links = tuple(getattr(socket, "links", ()) or ())
        if not links:
            return self._shader_channel_neutral(channel, want)
        return self._compile_shader_closure(
            getattr(links[0], "from_node", None),
            channel,
            want,
            output=getattr(links[0], "from_socket", None),
        )

    def _compile_radial_tiling(self, node, output, *, want: str) -> int:
        """Radial Tiling.

        Segment ID is a closed form that existing MATH ops already cover, so it
        needs no new opcode. Cycles (svm_node_radial_tiling / radial_tiling_shared.h):

            floor(sides * (atan2(y, x) / 2pi + float(y < 0)))

        with sides clamped to a minimum of 2, matching Cycles' fmaxf(sides, 2).

        The other three outputs come from calculate_out_variables. Its control flow
        is data-dependent only through `sides` and `roundness`; with both sockets
        unlinked every branch predicate and geometric constant folds at compile
        time and the runtime residue is a branchless region select, which
        `_compile_radial_tiling_variant` emits.

        The closed forms below survive as the implementation of exactly two cases:
        Segment ID, and integral constant Sides at roundness 0. They are the
        REGULAR-segment variant only — at fractional sides the odd segment reports
        the last angle bisector instead, which is why every other case now routes
        through the folded emitters, and why a linked Sides socket (whose runtime
        value may be fractional) is refused rather than silently mis-baked.
        """
        out_name = str(getattr(output, "name", "") or "")
        if out_name != "Segment ID":
            folded = self._radial_tiling_settings(node, out_name)
            if folded is not None:
                return self._compile_radial_tiling_variant(
                    node, out_name, folded, want=want
                )
        # Unlinked Vector uses Generated (same as Noise/Voronoi). Cycles' socket
        # default is (0,0,0) and bakes a solid black Segment Coordinates map.
        coord = self._radial_tiling_coord(node)
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        two = self._emit_swizzle(self._emit_constant((2.0, 2.0, 2.0, 1.0)), "LUMA")
        inv_two_pi = self._emit_swizzle(
            self._emit_constant((1.0 / (2.0 * math.pi),) * 3 + (1.0,)), "LUMA"
        )
        sides = self._emit_math_op(
            "MAXIMUM", self.compile_socket(node.inputs.get("Sides"), want="SCALAR"), two
        )
        pi_reg = self._emit_swizzle(
            self._emit_constant((math.pi, math.pi, math.pi, 1.0)), "LUMA"
        )

        if out_name == "Segment Width":
            # Measured: at roundness 0 the width is exactly tan(pi / sides), constant
            # over the whole surface (sides=5 gave 0.726543 = tan(pi/5), std 1e-7).
            # With roundness it is not a linear blend toward pi/sides -- sides=7 at
            # roundness 0.6 measured 0.45113 where that blend predicts 0.461909 -- so
            # anything non-zero stays on Cycles until calculate_out_variables is ported.
            if not roundness_is_zero_socket(node):
                self._fail(
                    "Radial Tiling 'Segment Width' with non-zero or linked Roundness comes "
                    "from calculate_out_variables, which is not ported yet. Needs Cycles"
                )
            return self._emit_math_op(
                "TANGENT", self._emit_math_op("DIVIDE", pi_reg, sides)
            )

        x = self._emit_swizzle(coord, "RRR1")
        y = self._emit_swizzle(coord, "GGG1")
        turns = self._emit_math_op(
            "MULTIPLY", self._emit_math_op("ARCTAN2", y, x), inv_two_pi
        )
        # atan2 returns (-pi, pi]; Cycles adds a whole turn below the x axis so the
        # segment index runs 0..sides-1 counter-clockwise instead of straddling zero.
        wrapped = self._emit_math_op("ADD", turns, self._emit_math_op("LESS_THAN", y, zero))
        segment_id = self._emit_math_op(
            "FLOOR", self._emit_math_op("MULTIPLY", sides, wrapped)
        )
        if out_name == "Segment ID":
            return segment_id

        # Segment Rotation is the angle of the segment's bisector: (2*id + 1) * pi/sides.
        # Segment Coordinates reuses it to rotate into the segment's local frame.
        # Measured against Cycles at sides 5 and 7 (min pi/n, max (2n-1)*pi/n in both)
        # and unchanged by roundness 0.6, so it depends only on sides and the segment.
        one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
        odd = self._emit_math_op(
            "ADD", self._emit_math_op("ADD", segment_id, segment_id), one
        )
        bisector = self._emit_math_op(
            "MULTIPLY", odd, self._emit_math_op("DIVIDE", pi_reg, sides)
        )
        if out_name == "Segment Rotation":
            return bisector

        # Segment Coordinates: the point in the segment's own frame, i.e. rotate by the
        # bisector angle and put the flat edge at zero.
        #
        #     (r * sin(theta - phi),  r * cos(theta - phi) - 1,  0)
        #
        # Derived by measurement, not from the source: this expression built out of
        # Blender nodes and baked through Cycles matches the real node's output to
        # 1e-6 on the tangential component, and to 1e-6 on the radial one once the
        # -1 is applied (without it the radial channel sat exactly 1.0 high, which is
        # the `out_variables.x -= 1.0` at the tail of calculate_out_variables).
        if not roundness_is_zero_socket(node):
            self._fail(
                "Radial Tiling 'Segment Coordinates' with non-zero or linked Roundness "
                "needs the rounded parameter field. Needs Cycles"
            )
        # Normalize is no longer refused here: an integral-sided sharp node with
        # Normalize on is routed to _compile_radial_tiling_integral_sharp before
        # this point, so this path only ever runs unnormalized.
        radius = self._emit_vector_math_op(
            "LENGTH",
            self._emit(
                {
                    "op": OPCODE_COMBINE_XYZ,
                    "dst": self._alloc(),
                    "a": int(x),
                    "b": int(y),
                    "fac": int(zero),
                }
            ),
        )
        delta = self._emit_math_op("SUBTRACT", self._emit_math_op("ARCTAN2", y, x), bisector)
        tangential = self._emit_math_op(
            "MULTIPLY", radius, self._emit_math_op("SINE", delta)
        )
        radial = self._emit_math_op(
            "SUBTRACT",
            self._emit_math_op("MULTIPLY", radius, self._emit_math_op("COSINE", delta)),
            one,
        )
        result = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(tangential),
                "b": int(radial),
                "fac": int(zero),
            }
        )
        return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result

    # ---------------------------------------------------------------- Radial Tiling
    # calculate_out_variables, non-zero roundness, Sides and Roundness constant.
    #
    # Three rules the expansions below obey, each of which was measured to matter:
    #
    # 1. Both arms of a region select are evaluated, so every sqrt whose argument
    #    goes negative outside its own region is clamped with MAXIMUM(x, 0) and
    #    every denominator with MAXIMUM(d, eps). NaN * 0 is NaN, so a poisoned
    #    discarded arm would survive the blend and destroy the taken one.
    # 2. There is no GREATER_EQUAL opcode. Cycles compares region bounds with >=,
    #    so `a >= b` is emitted as `1 - LESS_THAN(a, b)`. Substituting the strict
    #    inequality turns a measure-zero seam into a one-texel error line.
    # 3. Folded scalars are not free — see `_emit_scalar_constants`.

    def _bound_math_emitter(self, zero: int):
        """Scalar MATH emitter bound to one shared zero register.

        `_emit_math_op` materialises a fresh CONSTANT + SWIZZLE zero on every call,
        which is three ops per operation. These expansions run 60-120 operations.
        Shared by the Radial Tiling expansions and Image Texture box projection.
        """

        def emit(math_op: str, a: int, b: int | None = None, c: int | None = None) -> int:
            return self._emit(
                {
                    "op": OPCODE_MATH,
                    "dst": self._alloc(),
                    "math_op": math_op,
                    "a": int(a),
                    "b": int(zero if b is None else b),
                    "fac": int(zero if c is None else c),
                    "clamp": False,
                }
            )

        return emit

    def _radial_tiling_select(self, emit, cond, not_cond, when_true, when_false):
        """Branchless region select: cond*A + (1 - cond)*B.

        `MULTIPLY_ADD(cond, A - B, B)` looks cheaper but forms A - B even when cond
        is 0, and the discarded arm is not small: a denominator that only makes
        sense inside its own region gets floored at the epsilon, so l_coord/eps
        reaches ~1e12, and adding B back then rounds B to that value's ulp. Measured
        1.2e-4 on the radial channel at sides 4.7 / roundness 0.6 before this form.

        Given a precomputed complement this costs the same two ops and is exact:
        0 * finite is exactly 0, and every arm is kept finite by the sqrt/denominator
        guards precisely so that this holds.
        """
        return emit(
            "MULTIPLY_ADD", cond, when_true, emit("MULTIPLY", not_cond, when_false)
        )

    def _radial_tiling_polar(self, emit, K, coord, *, want_length: bool,
                             want_divider: bool = True):
        """(atan2, x_axis_A_coord, segment id, segment_divider_A_coord, l_coord).

        Cycles lifts atan2's (-pi, pi] onto [0, 2pi) by adding a whole turn below
        the x axis; every later quantity is derived from that lifted angle.
        segment_divider_A_coord is `axis - id * 2ab` written as a fraction of the
        segment so the subtraction stays well conditioned far from the x axis.
        """
        x = self._emit_swizzle(coord, "RRR1")
        y = self._emit_swizzle(coord, "GGG1")
        theta = emit("ARCTAN2", y, x)
        below = emit("LESS_THAN", y, K["zero"])
        axis = emit("MULTIPLY_ADD", below, K["two_pi"], theta)
        scaled = emit("MULTIPLY", axis, K["inv_ab2"])
        segment_id = emit("FLOOR", scaled)
        divider = None
        if want_divider:
            divider = emit("MULTIPLY", emit("SUBTRACT", scaled, segment_id), K["ab2"])
        length = None
        if want_length:
            length = emit(
                "SQRT", emit("MULTIPLY_ADD", x, x, emit("MULTIPLY", y, y))
            )
        return theta, axis, segment_id, divider, length

    def _radial_tiling_bevel_offset(self, emit, K, *, to_bevel, along, spline_start,
                                    half_start, half_over_start, start):
        """The bevel-relative part of r_gon_parameter: spline arm or straight arm.

        At roundness exactly 1 the spline start collapses to 0, which makes the
        spline arm both unreachable (coord_A_bevel_start cannot go below 0 inside
        the region) and numerically explosive: 0.5*t^2/0 floored at the epsilon
        reaches 5e11, and `MULTIPLY_ADD(cond, A - B, B)` then rounds B to the ulp
        of A even though cond is 0. Folding the dead arm away at compile time is
        both exact and cheaper; the straight arm collapses to `to_bevel` with it.
        """
        if spline_start <= 0.0:
            return to_bevel
        spline_t = emit(
            "MULTIPLY", emit("MULTIPLY", to_bevel, to_bevel), half_over_start
        )
        spline = emit(
            "MULTIPLY_ADD", along, emit("SUBTRACT", to_bevel, spline_t), spline_t
        )
        flat = emit(
            "MULTIPLY_ADD", along, half_start, emit("SUBTRACT", to_bevel, half_start)
        )
        # Cheap blend is safe here: with the degenerate spline start folded away
        # above, both arms stay O(1) and the difference carries no cancellation.
        pick = emit("LESS_THAN", to_bevel, start)
        return emit("MULTIPLY_ADD", pick, emit("SUBTRACT", spline, flat), flat)

    def _radial_tiling_regular_rounded(self, emit, K, *, length, divider, before_bisector,
                                       spline_start, normalize):
        """The fillet arc shared by the integral and fractional 'regular' zones."""
        past = emit("GREATER_THAN", divider, K["ab"])
        nearest = emit("MULTIPLY_ADD", past, K["minus_ab2"], divider)
        projected = emit("MULTIPLY", emit("COSINE", nearest), K["lcc"])
        radicand = emit(
            "MAXIMUM",
            emit("MULTIPLY_ADD", projected, projected, K["radic_bias"]),
            K["zero"],
        )
        ratio = emit(
            "MAXIMUM", emit("ADD", projected, emit("SQRT", radicand)), K["eps"]
        )
        bisector = emit("DIVIDE", length, ratio)
        to_bevel = emit("SUBTRACT", K["sdbs"], emit("ABSOLUTE", nearest))
        along = emit("MULTIPLY", length, K["cos_bsab"])
        across = emit("MULTIPLY", length, K["sin_bsab"])
        # spline arm: along*t + 0.5*(1 - along)*t^2/ssbs, regrouped so the shared
        # 0.5*t^2/ssbs term is computed once.
        parameter = emit(
            "ADD",
            across,
            self._radial_tiling_bevel_offset(
                emit, K, to_bevel=to_bevel, along=along, spline_start=spline_start,
                half_start=K.get("half_ssbs"), half_over_start=K.get("half_over_ssbs"),
                start=K.get("ssbs"),
            ),
        )
        # Inside this arm `divider < angle_bisector` is exactly `divider < bevel
        # start`, so the caller's existing comparison doubles as the sign flag.
        parameter = emit(
            "MULTIPLY",
            parameter,
            emit("MULTIPLY_ADD", before_bisector, K["minus_two"], K["one"]),
        )
        if normalize:
            on_bisector = emit("MULTIPLY_ADD", bisector, K["k1"], K["k2"])
            on_coord = emit(
                "ADD", emit("MULTIPLY_ADD", along, K["half_ssbs"], across), K["k2"]
            )
            blend = emit("MULTIPLY", to_bevel, K["inv_sdbs"])
            mixed = emit(
                "MAXIMUM",
                emit(
                    "MULTIPLY_ADD",
                    blend,
                    emit("SUBTRACT", on_coord, on_bisector),
                    on_bisector,
                ),
                K["eps"],
            )
            parameter = emit("DIVIDE", parameter, mixed)
        return bisector, parameter

    def _radial_tiling_straight(self, emit, K, *, length, divider, bisector_angle):
        """A flat edge: (l_angle_bisector, unnormalised r_gon_parameter).

        Cycles takes tan(|bisector - divider|) and negates below the bisector;
        tan is odd, so the signed difference carries the sign for free.
        """
        delta = emit("SUBTRACT", divider, bisector_angle)
        bisector = emit("MULTIPLY", length, emit("COSINE", delta))
        return bisector, emit("MULTIPLY", bisector, emit("TANGENT", delta))

    def _radial_tiling_finish(self, emit, K, *, parameter, bisector, length, normalize,
                              want):
        """The tail of calculate_out_variables plus the node's y/x output swap."""
        # r_gon_parameter is defined to 0 at the origin; Cycles applies that before
        # the [-1,1] -> [0,1] remap, so a normalised origin lands on exactly 0.5.
        parameter = emit("MULTIPLY", parameter, emit("GREATER_THAN", length, K["zero"]))
        if normalize:
            out_y = emit("MULTIPLY_ADD", parameter, K["half"], K["half"])
            out_x = bisector
        else:
            out_y = parameter
            out_x = emit("SUBTRACT", bisector, K["one"])
        result = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(out_y),
                "b": int(out_x),
                "fac": int(K["zero"]),
            }
        )
        return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result

    def _radial_tiling_settings(self, node, out_name):
        """Folded geometry for *node*, or None to use the legacy closed forms.

        Returning None is reserved for the two cases those forms are actually
        correct for: integral constant Sides at roundness 0, and (because it is
        the same expression for every sides value) a Segment Rotation whose Sides
        is a constant integer, whatever the Roundness socket does.

        Everything else either folds here or fails over to Cycles. A linked Sides
        socket always fails: its runtime value can be fractional, and then the odd
        segment needs the last-angle-bisector variant that no closed form emits.
        """
        inputs = getattr(node, "inputs", None)
        getter = getattr(inputs, "get", None) if inputs is not None else None
        if not callable(getter):
            self._fail(f"Radial Tiling '{out_name}' has no readable inputs. Needs Cycles")
        sides = _radial_tiling_socket_constant(getter("Sides"))
        if sides is None:
            self._fail(
                f"Radial Tiling '{out_name}' with a linked Sides socket cannot pick "
                "between the regular and last-segment variants at compile time, and "
                "the closed form is wrong in the odd segment of a fractional r-gon. "
                "Needs Cycles"
            )
        sides = max(sides, 2.0)
        integral = (sides - math.floor(sides)) == 0.0
        if integral and out_name == "Segment Rotation":
            # (2*id + 1) * pi/sides at every roundness, so a linked Roundness
            # socket costs no coverage here.
            return None
        roundness = _radial_tiling_socket_constant(getter("Roundness"))
        if roundness is None:
            self._fail(
                f"Radial Tiling '{out_name}' with a linked Roundness socket cannot fold "
                "calculate_out_variables at compile time. Needs Cycles"
            )
        roundness = min(max(roundness, 0.0), 1.0)
        # Match the tolerance the legacy sharp gate used, so a roundness of 1e-10
        # keeps taking the sharp path instead of a near-degenerate rounded one.
        if abs(roundness) <= 1e-9:
            roundness = 0.0
        if integral and roundness == 0.0:
            # The legacy closed forms are Cycles-verified and cheaper, but they miss
            # two corners of this arm:
            #   * Sides clamped to exactly 2, the one place calculate_out_variables
            #     carries a `sides != 2` guard — Segment Width is 0 there, not
            #     tan(pi/2), and r_gon_parameter is left unnormalized.
            #   * Normalize on, which they never implemented.
            needs_fold = sides == 2.0 or (
                out_name == "Segment Coordinates"
                and bool(getattr(node, "normalize", False))
            )
            if not needs_fold:
                return None
        folded = _radial_tiling_fold(sides, roundness)
        if folded is None:
            self._fail(
                f"Radial Tiling '{out_name}' at sides {sides} / roundness {roundness} "
                "folds to a non-finite geometry. Needs Cycles"
            )
        return folded

    def _compile_radial_tiling_variant(self, node, out_name, folded, *, want: str) -> int:
        if folded["sharp"]:
            if folded["integral"]:
                return self._compile_radial_tiling_integral_sharp(
                    node, out_name, folded, want=want
                )
            return self._compile_radial_tiling_fractional_sharp(
                node, out_name, folded, want=want
            )
        if folded["integral"]:
            if out_name == "Segment Width":
                # max_unit_parameter is the same constant in both integral arms.
                return self._emit_constant((folded["width_regular"],) * 3 + (1.0,))
            return self._compile_radial_tiling_integral(node, folded, want=want)
        return self._compile_radial_tiling_fractional(node, out_name, folded, want=want)

    def _compile_radial_tiling_integral_sharp(self, node, out_name, folded, *,
                                              want: str) -> int:
        """Integral sides at roundness 0, for the two corners the closed forms miss.

        With no fillet and congruent segments there is no region select at all —
        every coordinate is on a flat edge — so this is the smallest emission in
        the node. It exists for:

        * **Sides clamped to exactly 2.** `calculate_out_variables` guards its
          sharp integral arm with `sides != 2` in two places: max_unit_parameter
          becomes 0 instead of tan(pi/2), and the r_gon_parameter normalization is
          skipped, so Normalize only applies the [-1,1] -> [0,1] remap. A socket
          value below 2 lands here too, because Cycles conditions with
          `fmaxf(sides, 2)` before dispatching.
        * **Normalize on**, which divides r_gon_parameter by
          `l_angle_bisector * tan(pi/sides)`.

        Sides > 2 with Normalize off stays on the Cycles-verified closed forms.
        """
        normalize = bool(getattr(node, "normalize", False))
        # tan(pi/2) is 1.6e16 rather than infinity in floating point, so the guard
        # is a real branch in Cycles rather than a NaN dodge — reproduce it exactly.
        degenerate = folded["sides"] == 2.0

        if out_name == "Segment Width":
            return self._emit_constant((folded["width_sharp"],) * 3 + (1.0,))

        want_coordinates = out_name == "Segment Coordinates"
        pool = {
            "zero": 0.0,
            "one": 1.0,
            "half": 0.5,
            "eps": folded["eps"],
            "two_pi": folded["two_pi"],
            "inv_ab2": folded["inv_ab2"],
            "ab": folded["ab"],
            "ab2": folded["ab2"],
        }
        if want_coordinates and normalize and not degenerate:
            pool["tan_ab"] = folded["tan_ab"]
        K = self._emit_scalar_constants(pool)
        emit = self._bound_math_emitter(K["zero"])

        coord = self._radial_tiling_coord(node)
        _theta, _axis, segment_id, divider, length = self._radial_tiling_polar(
            emit, K, coord,
            want_length=want_coordinates, want_divider=want_coordinates,
        )
        if not want_coordinates:
            # Segment Rotation: every segment reports its own angle bisector.
            return emit("MULTIPLY_ADD", segment_id, K["ab2"], K["ab"])

        bisector, parameter = self._radial_tiling_straight(
            emit, K, length=length, divider=divider, bisector_angle=K["ab"]
        )
        if normalize and not degenerate:
            # Cycles divides by l_angle_bisector * tan(ab). The factor cancels
            # algebraically, but keeping the division reproduces its conditioning;
            # the guard turns the origin's 0/0 into the 0 that the zero-vector
            # special case would have written anyway.
            parameter = emit(
                "DIVIDE",
                parameter,
                emit(
                    "MAXIMUM", emit("MULTIPLY", bisector, K["tan_ab"]), K["eps"]
                ),
            )
        return self._radial_tiling_finish(
            emit, K, parameter=parameter, bisector=bisector, length=length,
            normalize=normalize, want=want,
        )

    def _compile_radial_tiling_fractional_sharp(self, node, out_name, folded, *,
                                                want: str) -> int:
        """Fractional sides at roundness 0 — the odd-segment variant.

        Cycles gives this its own arm of the dispatch, and it is much cheaper than
        the rounded one: with no fillet there is a single region test,
        `x_axis_A_coord < 2pi - last_segment_divider_A_x_axis`, separating the
        congruent segments from the odd one. Inside the odd segment every output
        swaps the angle bisector for the last angle bisector, and the radial
        component picks up the cos(ab)/cos(labxa) ratio.

        The legacy closed forms emit the regular variant everywhere, which is
        correct only when sides is integral (then the odd segment does not exist).
        """
        normalize = bool(getattr(node, "normalize", False))
        want_coordinates = out_name == "Segment Coordinates"
        pool = {
            "zero": 0.0,
            "one": 1.0,
            "half": 0.5,
            "eps": folded["eps"],
            "two_pi": folded["two_pi"],
            "inv_ab2": folded["inv_ab2"],
            "ab2": folded["ab2"],
            "b_last": folded["b_last"],
        }
        if out_name == "Segment Width":
            pool.update({"tan_labxa": folded["tan_labxa"],
                         "tan_delta": folded["tan_ab"] - folded["tan_labxa"]})
        if out_name == "Segment Rotation":
            pool.update({"labxa": folded["labxa"],
                         "minus_labxa_minus_ab": -folded["labxa_minus_ab"]})
        if want_coordinates:
            pool.update({"ab": folded["ab"], "labxa": folded["labxa"],
                         "lab_r_llab": folded["lab_r_llab"]})
            if normalize:
                pool.update({"tan_ab": folded["tan_ab"],
                             "tan_labxa": folded["tan_labxa"]})
        K = self._emit_scalar_constants(pool)
        emit = self._bound_math_emitter(K["zero"])
        one = K["one"]

        coord = self._radial_tiling_coord(node)
        _theta, axis, segment_id, divider, length = self._radial_tiling_polar(
            emit, K, coord,
            want_length=want_coordinates, want_divider=want_coordinates,
        )
        regular = emit("LESS_THAN", axis, K["b_last"])

        if out_name == "Segment Width":
            # max_unit_parameter is tan(ab), or tan(labxa) in the odd segment.
            return emit("MULTIPLY_ADD", regular, K["tan_delta"], K["tan_labxa"])
        if out_name == "Segment Rotation":
            angle = emit(
                "MULTIPLY_ADD", regular, K["minus_labxa_minus_ab"], K["labxa"]
            )
            return emit("MULTIPLY_ADD", segment_id, K["ab2"], angle)

        # Both arms are a flat edge; tan is odd, so the signed angle difference
        # carries Cycles' "negate below the bisector" for free.
        regular_bisector, regular_parameter = self._radial_tiling_straight(
            emit, K, length=length, divider=divider, bisector_angle=K["ab"]
        )
        last_delta = emit("SUBTRACT", divider, K["labxa"])
        last_bisector = emit(
            "MULTIPLY",
            emit("MULTIPLY", length, emit("COSINE", last_delta)),
            K["lab_r_llab"],
        )
        last_parameter = emit(
            "MULTIPLY", last_bisector, emit("TANGENT", last_delta)
        )
        if normalize:
            # Each arm normalises against its own bisector's full half-width.
            regular_parameter = emit(
                "DIVIDE",
                regular_parameter,
                emit(
                    "MAXIMUM",
                    emit("MULTIPLY", regular_bisector, K["tan_ab"]),
                    K["eps"],
                ),
            )
            last_parameter = emit(
                "DIVIDE",
                last_parameter,
                emit(
                    "MAXIMUM",
                    emit("MULTIPLY", last_bisector, K["tan_labxa"]),
                    K["eps"],
                ),
            )
        not_regular = emit("SUBTRACT", one, regular)
        parameter = self._radial_tiling_select(
            emit, regular, not_regular, regular_parameter, last_parameter
        )
        bisector = self._radial_tiling_select(
            emit, regular, not_regular, regular_bisector, last_bisector
        )
        return self._radial_tiling_finish(
            emit, K, parameter=parameter, bisector=bisector, length=length,
            normalize=normalize, want=want,
        )

    def _compile_radial_tiling_integral(self, node, folded, *, want: str) -> int:
        """Segment Coordinates, integral sides, 0 < roundness <= 1.

        Every segment is congruent, so there are exactly two regions: the fillet
        arc within segment_divider_A_bevel_start of each divider, and the flat edge
        between them.

        Roundness exactly 1 is not special-cased. Cycles has a separate arm for it,
        but that arm is the limit of the general one: bevel start collapses onto the
        angle bisector, the circle centre onto the origin, and the fillet radius
        onto 1, so l_angle_bisector reduces to l_coord and the parameter to
        divider - bisector. Both were checked against the reference evaluator.
        """
        normalize = bool(getattr(node, "normalize", False))
        pool = {
            "zero": 0.0,
            "one": 1.0,
            "half": 0.5,
            "eps": folded["eps"],
            "two_pi": folded["two_pi"],
            "inv_ab2": folded["inv_ab2"],
            "ab": folded["ab"],
            "ab2": folded["ab2"],
            "minus_ab2": folded["minus_ab2"],
            "minus_two": folded["minus_two"],
            "sdbs": folded["sdbs"],
            "ab2_minus_sdbs": folded["ab2_minus_sdbs"],
            "lcc": folded["lcc"],
            "radic_bias": folded["radic_bias"],
            "cos_bsab": folded["cos_bsab"],
            "sin_bsab": folded["sin_bsab"],
            # Both are 0 at roundness 1, where they dedup onto the zero lane.
            "ssbs": folded["ssbs"],
            "half_ssbs": folded["half_ssbs"],
        }
        if folded["ssbs"] > 0.0:
            pool["half_over_ssbs"] = folded["half_over_ssbs"]
        if normalize:
            pool.update({"k1": folded["k1"], "k2": folded["k2"],
                         "inv_sdbs": folded["inv_sdbs"]})
        K = self._emit_scalar_constants(pool)
        emit = self._bound_math_emitter(K["zero"])
        coord = self._radial_tiling_coord(node)
        _theta, _axis, _segment_id, divider, length = self._radial_tiling_polar(
            emit, K, coord, want_length=True
        )

        # `divider >= 2*ab - sdbs or divider < sdbs` selects the fillet. The two
        # halves are disjoint (sdbs < ab < 2*ab - sdbs), so the flat edge is simply
        # their difference and needs no OR.
        under_high = emit("LESS_THAN", divider, K["ab2_minus_sdbs"])
        under_low = emit("LESS_THAN", divider, K["sdbs"])
        straight = emit("SUBTRACT", under_high, under_low)

        flat_bisector, flat_parameter = self._radial_tiling_straight(
            emit, K, length=length, divider=divider, bisector_angle=K["ab"]
        )
        if normalize:
            flat_parameter = emit(
                "DIVIDE",
                flat_parameter,
                emit(
                    "MAXIMUM",
                    emit("MULTIPLY_ADD", flat_bisector, K["k1"], K["k2"]),
                    K["eps"],
                ),
            )
        round_bisector, round_parameter = self._radial_tiling_regular_rounded(
            emit, K, length=length, divider=divider, before_bisector=under_low,
            spline_start=folded["ssbs"], normalize=normalize,
        )

        rounded = emit("SUBTRACT", K["one"], straight)
        parameter = self._radial_tiling_select(
            emit, straight, rounded, flat_parameter, round_parameter
        )
        bisector = self._radial_tiling_select(
            emit, straight, rounded, flat_bisector, round_bisector
        )
        return self._radial_tiling_finish(
            emit, K, parameter=parameter, bisector=bisector, length=length,
            normalize=normalize, want=want,
        )

    def _compile_radial_tiling_fractional(self, node, out_name, folded, *, want: str) -> int:
        """Fractional sides, 0 < roundness <= 1 — calculate_out_variables_irregular_circular.

        One segment is the odd one out, so the plane splits into a regular zone
        (flat edge + fillet, identical to the integral case) and, around the last
        segment divider, an irregular straight run and an irregular fillet that is
        itself split into an inner and an outer half by the mirrored signed angle.

        Roundness 1 also lands here: the geometry-nodes-only full-roundness
        specialization is #ifdef'd out of Cycles, so the render path runs this
        function for the whole 0 < roundness <= 1 range.
        """
        normalize = bool(getattr(node, "normalize", False))
        want_coordinates = out_name == "Segment Coordinates"
        pool = {
            "zero": 0.0,
            "one": 1.0,
            "half": 0.5,
            "eps": folded["eps"],
            "two_pi": folded["two_pi"],
            "inv_ab2": folded["inv_ab2"],
            "ab": folded["ab"],
            "ab2": folded["ab2"],
            "minus_two": folded["minus_two"],
            "minus_lsdxa": folded["minus_lsdxa"],
            "b1": folded["b1"],
            "b2": folded["b2"],
            "b5": folded["b5"],
            "b6": folded["b6"],
            "b7": folded["b7"],
        }
        if want_coordinates:
            pool.update({"sdbs": folded["sdbs"],
                         "ab2_minus_sdbs": folded["ab2_minus_sdbs"],
                         "b3": folded["b3"]})
        if out_name == "Segment Width":
            pool.update({"width_regular": folded["width_regular"],
                         "width_last": folded["width_last"],
                         "width_delta": folded["width_last"] - folded["width_regular"]})
        if out_name == "Segment Rotation":
            pool.update({"labxa": folded["labxa"],
                         "labxa_minus_ab": folded["labxa"] - folded["ab"]})
        if want_coordinates:
            pool.update({
                "minus_ab2": folded["minus_ab2"],
                "labxa": folded["labxa"],
                "lab_r_llab": folded["lab_r_llab"],
                "lcc": folded["lcc"],
                "radic_bias": folded["radic_bias"],
                "cos_bsab": folded["cos_bsab"],
                "sin_bsab": folded["sin_bsab"],
                # The three spline starts are 0 at roundness 1, where they dedup
                # onto the zero lane and their reciprocals drop out entirely.
                "ssbs": folded["ssbs"],
                "half_ssbs": folded["half_ssbs"],
                "lcc0": folded["lcc0"],
                "lcc1": folded["lcc1"],
                "radic_bias3": folded["radic_bias3"],
                "ilbsxa": folded["ilbsxa"],
                "ssbs2": folded["ssbs2"],
                "half_ssbs2": folded["half_ssbs2"],
                "cos_ilbslab": folded["cos_ilbslab"],
                "sin_ilbslab": folded["sin_ilbslab"],
                "xaolbs": folded["xaolbs"],
                "ssolbs": folded["ssolbs"],
                "half_ssolbs": folded["half_ssolbs"],
                "cos_olbsab": folded["cos_olbsab"],
                "sin_olbsab": folded["sin_olbsab"],
            })
            for start, reciprocal in (
                ("ssbs", "half_over_ssbs"),
                ("ssbs2", "half_over_ssbs2"),
                ("ssolbs", "half_over_ssolbs"),
            ):
                if folded[start] > 0.0:
                    pool[reciprocal] = folded[reciprocal]
            if normalize:
                pool.update({
                    "k1": folded["k1"], "k2": folded["k2"],
                    "inv_sdbs": folded["inv_sdbs"],
                    "kc1": folded["kc1"], "kc2": folded["kc2"],
                    "kd1": folded["kd1"], "kd2": folded["kd2"],
                    "ke1": folded["ke1"], "ke2": folded["ke2"],
                    "inv_ilbsxa": folded["inv_ilbsxa"],
                    "inv_xaolbs": folded["inv_xaolbs"],
                    "b8": folded["b8"],
                })
        K = self._emit_scalar_constants(pool)
        emit = self._bound_math_emitter(K["zero"])
        one, zero = K["one"], K["zero"]

        def at_least(value: int, bound: int) -> int:
            """`value >= bound`. There is no GREATER_EQUAL opcode."""
            return emit("SUBTRACT", one, emit("LESS_THAN", value, bound))

        coord = self._radial_tiling_coord(node)
        theta, axis, segment_id, divider, length = self._radial_tiling_polar(
            emit, K, coord, want_length=want_coordinates,
            want_divider=want_coordinates,
        )

        regular = emit(
            "MULTIPLY", at_least(axis, K["b1"]), emit("LESS_THAN", axis, K["b2"])
        )
        irregular_straight = emit(
            "MULTIPLY", at_least(axis, K["b5"]), emit("LESS_THAN", axis, K["b6"])
        )
        mirrored = emit(
            "MULTIPLY", at_least(axis, K["b2"]), emit("LESS_THAN", axis, K["b7"])
        )

        if not want_coordinates:
            # Segment Width and Segment Rotation only need to know which half of
            # the irregular fillet a coordinate is in, which is a comparison on the
            # raw angle rather than the mirrored one:
            #     mirrored  -> -(theta + last_segment_divider) < 0  <=>  theta > -lsdxa
            #     otherwise -> theta < 0
            straight_side = emit("LESS_THAN", theta, zero)
            mirrored_side = emit("GREATER_THAN", theta, K["minus_lsdxa"])
            inner = emit(
                "MULTIPLY_ADD",
                mirrored,
                emit("SUBTRACT", mirrored_side, straight_side),
                straight_side,
            )
            if out_name == "Segment Width":
                # max_unit_parameter is one of two constants: the regular one, which
                # the outer half of the irregular fillet also reports, and the last
                # segment's, shared by the irregular straight run and the inner half.
                fillet = emit(
                    "MULTIPLY_ADD", inner, K["width_delta"], K["width_regular"]
                )
                rest = emit(
                    "MULTIPLY_ADD",
                    irregular_straight,
                    emit("SUBTRACT", K["width_last"], fillet),
                    fillet,
                )
                return emit(
                    "MULTIPLY_ADD",
                    regular,
                    emit("SUBTRACT", K["width_regular"], rest),
                    rest,
                )
            # Segment Rotation: segment_id * 2ab + (angle bisector | last bisector).
            fillet = emit("MULTIPLY_ADD", inner, K["labxa_minus_ab"], K["ab"])
            rest = emit(
                "MULTIPLY_ADD",
                irregular_straight,
                emit("SUBTRACT", K["labxa"], fillet),
                fillet,
            )
            angle = emit(
                "MULTIPLY_ADD", regular, emit("SUBTRACT", K["ab"], rest), rest
            )
            return emit("MULTIPLY_ADD", segment_id, K["ab2"], angle)

        # --- regular zone: flat edge vs fillet -------------------------------
        under_low = emit("LESS_THAN", divider, K["sdbs"])
        in_span = emit(
            "MULTIPLY",
            emit("SUBTRACT", one, under_low),
            emit("LESS_THAN", divider, K["ab2_minus_sdbs"]),
        )
        # ... or either of the two x-axis windows that belong to the odd segment.
        straight = emit(
            "MAXIMUM",
            emit("MAXIMUM", in_span, at_least(axis, K["b3"])),
            emit("LESS_THAN", axis, K["sdbs"]),
        )
        flat_bisector, flat_parameter = self._radial_tiling_straight(
            emit, K, length=length, divider=divider, bisector_angle=K["ab"]
        )
        if normalize:
            # The flat edge normalises against the odd segment's outer bevel inside
            # that segment's x-axis span and against the regular bevel elsewhere.
            odd_span = emit(
                "MAXIMUM", at_least(axis, K["b8"]), emit("LESS_THAN", axis, K["ab"])
            )
            outer_norm = emit("MULTIPLY_ADD", flat_bisector, K["ke1"], K["ke2"])
            inner_norm = emit("MULTIPLY_ADD", flat_bisector, K["k1"], K["k2"])
            flat_parameter = emit(
                "DIVIDE",
                flat_parameter,
                emit(
                    "MAXIMUM",
                    emit(
                        "MULTIPLY_ADD",
                        odd_span,
                        emit("SUBTRACT", outer_norm, inner_norm),
                        inner_norm,
                    ),
                    K["eps"],
                ),
            )
        round_bisector, round_parameter = self._radial_tiling_regular_rounded(
            emit, K, length=length, divider=divider, before_bisector=under_low,
            spline_start=folded["ssbs"], normalize=normalize,
        )

        # --- irregular straight run ------------------------------------------
        last_delta = emit("SUBTRACT", divider, K["labxa"])
        last_length = emit("MULTIPLY", length, emit("COSINE", last_delta))
        last_bisector = emit("MULTIPLY", last_length, K["lab_r_llab"])
        last_parameter = emit(
            "MULTIPLY", last_bisector, emit("TANGENT", last_delta)
        )
        if normalize:
            last_parameter = emit(
                "DIVIDE",
                last_parameter,
                emit(
                    "MAXIMUM",
                    emit("MULTIPLY_ADD", last_length, K["kc1"], K["kc2"]),
                    K["eps"],
                ),
            )

        # --- irregular fillet: shared radial solve ----------------------------
        flip = emit("MULTIPLY_ADD", mirrored, K["minus_two"], one)
        nearest = emit(
            "MULTIPLY_ADD",
            mirrored,
            K["minus_lsdxa"],
            emit("MULTIPLY", theta, flip),
        )
        projected = emit(
            "MULTIPLY_ADD",
            emit("COSINE", nearest),
            K["lcc0"],
            emit("MULTIPLY", emit("SINE", nearest), K["lcc1"]),
        )
        radicand = emit(
            "MAXIMUM",
            emit("MULTIPLY_ADD", projected, projected, K["radic_bias3"]),
            zero,
        )
        fillet_ratio = emit(
            "MAXIMUM", emit("ADD", projected, emit("SQRT", radicand)), K["eps"]
        )
        fillet_last = emit("DIVIDE", length, fillet_ratio)
        fillet_bisector = emit("MULTIPLY", fillet_last, K["lab_r_llab"])
        inner = emit("LESS_THAN", nearest, zero)
        nearest_abs = emit("ABSOLUTE", nearest)

        def spline_blend(to_bevel, along, name):
            return self._radial_tiling_bevel_offset(
                emit,
                K,
                to_bevel=to_bevel,
                along=along,
                spline_start=folded[name],
                half_start=K["half_" + name],
                half_over_start=K.get("half_over_" + name),
                start=K[name],
            )

        # inner half — measured from the odd segment's own bevel start.
        inner_to_bevel = emit("SUBTRACT", K["ilbsxa"], nearest_abs)
        inner_along = emit("MULTIPLY", length, K["cos_ilbslab"])
        inner_across = emit("MULTIPLY", length, K["sin_ilbslab"])
        inner_parameter = emit(
            "MULTIPLY",
            emit(
                "ADD",
                inner_across,
                spline_blend(inner_to_bevel, inner_along, "ssbs2"),
            ),
            K["lab_r_llab"],
        )
        before_last = emit("LESS_THAN", divider, K["labxa"])
        inner_parameter = emit(
            "MULTIPLY",
            inner_parameter,
            emit("MULTIPLY_ADD", before_last, K["minus_two"], one),
        )
        if normalize:
            on_bisector = emit("MULTIPLY_ADD", fillet_last, K["kd1"], K["kd2"])
            on_coord = emit(
                "ADD",
                emit("MULTIPLY_ADD", inner_along, K["half_ssbs2"], inner_across),
                K["kd2"],
            )
            blend = emit("MULTIPLY", inner_to_bevel, K["inv_ilbsxa"])
            inner_parameter = emit(
                "DIVIDE",
                inner_parameter,
                emit(
                    "MAXIMUM",
                    emit(
                        "MULTIPLY",
                        emit(
                            "MULTIPLY_ADD",
                            blend,
                            emit("SUBTRACT", on_coord, on_bisector),
                            on_bisector,
                        ),
                        K["lab_r_llab"],
                    ),
                    K["eps"],
                ),
            )

        # outer half — measured from the outer last bevel start, with an effective
        # roundness of its own.
        outer_to_bevel = emit("SUBTRACT", K["xaolbs"], nearest_abs)
        outer_along = emit("MULTIPLY", length, K["cos_olbsab"])
        outer_across = emit("MULTIPLY", length, K["sin_olbsab"])
        outer_parameter = emit(
            "ADD",
            outer_across,
            spline_blend(outer_to_bevel, outer_along, "ssolbs"),
        )
        # The outer half spans x-axis windows on both sides of the odd segment, so
        # unlike the regular fillet its sign flag is a genuine `divider < bisector`
        # rather than the `divider < bevel start` test that coincides with it there.
        before_bisector = emit("LESS_THAN", divider, K["ab"])
        outer_parameter = emit(
            "MULTIPLY",
            outer_parameter,
            emit("MULTIPLY_ADD", before_bisector, K["minus_two"], one),
        )
        if normalize:
            on_bisector = emit("MULTIPLY_ADD", fillet_bisector, K["ke1"], K["ke2"])
            on_coord = emit(
                "ADD",
                emit("MULTIPLY_ADD", outer_along, K["half_ssolbs"], outer_across),
                K["ke2"],
            )
            blend = emit("MULTIPLY", outer_to_bevel, K["inv_xaolbs"])
            outer_parameter = emit(
                "DIVIDE",
                outer_parameter,
                emit(
                    "MAXIMUM",
                    emit(
                        "MULTIPLY_ADD",
                        blend,
                        emit("SUBTRACT", on_coord, on_bisector),
                        on_bisector,
                    ),
                    K["eps"],
                ),
            )

        # --- region blend -----------------------------------------------------
        # Nested so `regular` and `irregular_straight` need no mutual exclusion:
        # whichever indicator is 1 wins, and the discarded branches contribute
        # exactly 0 rather than being subtracted back out.
        select = self._radial_tiling_select
        not_inner = emit("SUBTRACT", one, inner)
        not_irregular = emit("SUBTRACT", one, irregular_straight)
        not_regular = emit("SUBTRACT", one, regular)
        not_straight = emit("SUBTRACT", one, straight)

        fillet_parameter = select(emit, inner, not_inner, inner_parameter, outer_parameter)
        rest_parameter = select(
            emit, irregular_straight, not_irregular, last_parameter, fillet_parameter
        )
        regular_parameter = select(
            emit, straight, not_straight, flat_parameter, round_parameter
        )
        parameter = select(
            emit, regular, not_regular, regular_parameter, rest_parameter
        )

        rest_bisector = select(
            emit, irregular_straight, not_irregular, last_bisector, fillet_bisector
        )
        regular_bisector = select(
            emit, straight, not_straight, flat_bisector, round_bisector
        )
        bisector = select(emit, regular, not_regular, regular_bisector, rest_bisector)
        return self._radial_tiling_finish(
            emit, K, parameter=parameter, bisector=bisector, length=length,
            normalize=normalize, want=want,
        )

    def _parametric_coordinates(self) -> int:
        """Cycles' Geometry > Parametric from the raw hit barycentric.

        The baker's barycentric carries weights (x, y, z) with x on vertex 0
        (mir_hit_uv interpolates origin + edge1*y + edge2*z). Which two of the
        three Cycles reports as (u, v) is a measurement question -- the recorded
        0.165 mismatch from the first attempt was exactly a component-order
        guess. Start from the raw vector; the mapping below is whatever the
        Cycles-vs-Fyr bake says, and the composition lives here in the addon so
        re-measuring never needs a backend rebuild.
        """
        bary = self._emit_attr(OPCODE_ATTR_BARYCENTRIC)
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        # MEASURED: u = bary.x, v = bary.y (all six permutations tested numerically
        # against a Cycles Parametric bake; the winner errs 0.00075, every other
        # 0.324). Cycles' z channel bakes exactly 0.
        return self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(self._emit_swizzle(bary, "RRR1")),
                "b": int(self._emit_swizzle(bary, "GGG1")),
                "fac": int(zero),
            }
        )

    def _radial_z_tangent(self) -> int:
        """Cycles' default (radial about Z) tangent, which Geometry's Tangent emits.

        Derived by measurement, not from a formula: a Cycles bake of Geometry>Tangent
        is bit-identical to a Tangent node set to RADIAL/Z (max diff 0.0), and this
        construction reproduces that to 2.1e-6 -- float precision. It is NOT the
        MikkTSpace UV tangent the baker carries for normal maps; using that instead
        measured 0.551 off.

            T = normalize(Tw - N * dot(N, Tw)),  Tw = object->world(cross(Z, g - 0.5))
        """
        half = self._emit_constant((0.5, 0.5, 0.5, 1.0))
        centred = self._emit_vector_math_op(
            "SUBTRACT", self._emit_attr(OPCODE_ATTR_GENERATED), half
        )
        z_axis = self._emit_constant((0.0, 0.0, 1.0, 1.0))
        tangent_object = self._emit_vector_math_op("CROSS_PRODUCT", z_axis, centred)
        tangent_world = self._emit(
            {
                "op": OPCODE_VECTOR_TRANSFORM,
                "dst": self._alloc(),
                "src": int(tangent_object),
                "mode": "VECTOR",
                "clamp": False,  # OBJECT -> WORLD
            }
        )
        normal = self._emit_attr(OPCODE_ATTR_NORMAL)
        along_normal = self._emit_vector_math_op(
            "MULTIPLY",
            normal,
            self._emit_vector_math_op("DOT_PRODUCT", normal, tangent_world),
        )
        return self._emit_vector_math_op(
            "NORMALIZE", self._emit_vector_math_op("SUBTRACT", tangent_world, along_normal)
        )

    def _object_space_normal(self) -> int:
        """The shading normal in object space, which is TexCoord's Normal output.

        ATTR_NORMAL is world space; VECTOR_TRANSFORM in NORMAL mode carries it into
        object space using the inverse transpose, which is the correct rule for a
        normal under a non-uniform scale.
        """
        world_normal = self._emit_attr(OPCODE_ATTR_NORMAL)
        object_normal = self._emit(
            {
                "op": OPCODE_VECTOR_TRANSFORM,
                "dst": self._alloc(),
                "src": int(world_normal),
                "mode": "NORMAL",
                "clamp": True,  # WORLD -> OBJECT
            }
        )
        return self._emit_vector_math_op("NORMALIZE", object_normal)

    def _mesh_has_attribute(self, obj, name: str) -> bool:
        """Whether *obj*'s mesh carries a geometry attribute of this name."""
        mesh = getattr(obj, "data", None)
        if mesh is None:
            return False
        for collection in ("attributes", "uv_layers", "color_attributes", "vertex_colors"):
            container = getattr(mesh, collection, None)
            if container is None:
                continue
            try:
                if name in container:
                    return True
            except TypeError:
                if any(str(getattr(item, "name", "")) == name for item in container):
                    return True
        return False

    def _active_color_attribute_name(self) -> str:
        """The active colour layer shared by every contributing mesh, or ""."""
        names = set()
        for obj in self._attribute_objects or ():
            mesh = getattr(obj, "data", None)
            attributes = getattr(mesh, "color_attributes", None) if mesh is not None else None
            active = getattr(attributes, "active_color", None) if attributes is not None else None
            name = str(getattr(active, "name", "") or "").strip()
            if not name:
                return ""
            names.add(name)
        return names.pop() if len(names) == 1 else ""

    def _mesh_float_attribute(self, obj, name: str) -> bool:
        """Whether *obj*'s mesh carries *name* as a scalar FLOAT attribute a sidecar can read.

        Mirrors `material_geometry_attributes.float_attribute_per_corner`: FLOAT only,
        and only on the domains a per-corner fetch can reproduce. INT and BOOLEAN are
        excluded deliberately -- they are not floats to Cycles, and converting them
        here would bake a value nothing authored.
        """
        mesh = getattr(obj, "data", None)
        attributes = getattr(mesh, "attributes", None) if mesh is not None else None
        if attributes is None:
            return False
        try:
            layer = attributes.get(name)
        except (AttributeError, TypeError):
            layer = None
        if layer is None:
            return False
        if str(getattr(layer, "data_type", "") or "").strip().upper() != "FLOAT":
            return False
        return str(getattr(layer, "domain", "") or "").strip().upper() in {
            "POINT",
            "CORNER",
            "FACE",
        }

    def _mesh_color_attribute(self, obj, name: str) -> bool:
        """Whether *obj*'s mesh carries *name* as a colour attribute."""
        mesh = getattr(obj, "data", None)
        attributes = getattr(mesh, "attributes", None) if mesh is not None else None
        if attributes is None:
            return False
        try:
            layer = attributes.get(name)
        except (AttributeError, TypeError):
            layer = None
        if layer is None:
            return False
        return str(getattr(layer, "data_type", "") or "").upper() in {
            "FLOAT_COLOR",
            "BYTE_COLOR",
        }

    def _tree_displaces(self, tree) -> bool:
        """Whether *tree*'s active Material Output has anything on Displacement."""
        nodes = list(getattr(tree, "nodes", []) or [])
        outputs = [n for n in nodes if str(getattr(n, "type", "") or "") == "OUTPUT_MATERIAL"]
        if not outputs:
            return False
        active = next(
            (n for n in outputs if bool(getattr(n, "is_active_output", False))), outputs[0]
        )
        socket = None
        try:
            socket = active.inputs.get("Displacement")
        except (AttributeError, TypeError):
            socket = None
        return bool(getattr(socket, "is_linked", False))

    def _is_active_uv_layer(self, name: str) -> bool:
        """Whether *name* is the render UV layer on EVERY contributing mesh.

        Naming the active layer explicitly is common and costs nothing: `ATTR_UV`
        already is that layer, so it needs no sidecar. Unanimity is required because
        one program shades every object in the group -- if two objects disagree about
        which layer that name refers to, only the per-corner sidecar is honest.
        With no object context (a bare compile, as the Bakeability panel does) the
        answer is False, which is the safe direction: it costs a sidecar, never
        correctness.
        """
        name = str(name or "").strip()
        if not name:
            return False
        objects = list(self._attribute_objects or ())
        if not objects:
            return False
        for obj in objects:
            mesh = getattr(obj, "data", None)
            layers = getattr(mesh, "uv_layers", None) if mesh is not None else None
            if layers is None:
                return False
            active = None
            for layer in layers:
                if bool(getattr(layer, "active_render", False)):
                    active = layer
                    break
            if active is None:
                active = getattr(layers, "active", None)
            if str(getattr(active, "name", "") or "").strip() != name:
                return False
        return True

    def _active_render_uv_layer_name(self) -> str:
        """Resolve an unnamed UV input using Blender's Active Render UV layer."""
        objects = list(self._attribute_objects or ())
        if not objects:
            return ""
        names = []
        for obj in objects:
            mesh = getattr(obj, "data", None)
            layers = getattr(mesh, "uv_layers", None) if mesh is not None else None
            if layers is None:
                self._fail("Active Render UV is unavailable on a contributing high mesh. Needs Cycles")
            active = None
            for layer in layers:
                if bool(getattr(layer, "active_render", False)):
                    active = layer
                    break
            if active is None:
                active = getattr(layers, "active", None)
            name = str(getattr(active, "name", "") or "").strip()
            if not name:
                self._fail("Active Render UV is unavailable on a contributing high mesh. Needs Cycles")
            names.append(name)
        if any(name != names[0] for name in names[1:]):
            self._fail("Contributing high meshes use different Active Render UV layers. Needs Cycles")
        return names[0]

    def _mesh_uv_layer(self, obj, name: str) -> bool:
        """Whether *obj*'s mesh carries *name* as a UV layer."""
        mesh = getattr(obj, "data", None)
        layers = getattr(mesh, "uv_layers", None) if mesh is not None else None
        if layers is None:
            return False
        try:
            return layers.get(name) is not None
        except (AttributeError, TypeError):
            return any(str(getattr(item, "name", "")) == name for item in layers)

    def _image_texel_size(self, image):
        """(1/width, 1/height) for an image, or None when the size is unusable."""
        try:
            width = int(image.size[0])
            height = int(image.size[1])
        except Exception:
            return None
        if width <= 0 or height <= 0:
            return None
        return (1.0 / float(width), 1.0 / float(height))

    def _apply_image_extension(self, coord: int, extension: str, image) -> int:
        """Rewrite the sample coordinate so a REPEAT sampler behaves like `extension`.

        The backend sampler has one addressing mode -- repeat -- and no field on
        SAMPLE_IMAGE to carry another, so these used to refuse. They do not need one:
        every mode is a function of the coordinate, and the IR already has the vector
        maths to express it.

        CLIP is the exception: it is a mask on the RESULT, not on the coordinate, so
        it is applied by the caller after the sample.
        """
        if extension == "EXTEND":
            # Clamp to the texel CENTRES, not to [0,1]: a bilinear tap at exactly 1.0
            # blends the last texel with the first one across the wrap, which is the
            # seam clamp-to-edge exists to avoid.
            texel = self._image_texel_size(image)
            if texel is None:
                self._fail("Image Texture Extend needs a known image size. Needs Cycles")
            low = self._emit_constant((texel[0] * 0.5, texel[1] * 0.5, 0.0, 1.0))
            high = self._emit_constant((1.0 - texel[0] * 0.5, 1.0 - texel[1] * 0.5, 1.0, 1.0))
            return self._emit_vector_math_op(
                "MINIMUM", self._emit_vector_math_op("MAXIMUM", coord, low), high
            )
        if extension == "MIRROR":
            # Triangle wave of period 2: 1 - |frac(x/2)*2 - 1|.
            half = self._emit_constant((0.5, 0.5, 0.5, 1.0))
            two = self._emit_constant((2.0, 2.0, 2.0, 1.0))
            one = self._emit_constant((1.0, 1.0, 1.0, 1.0))
            folded = self._emit_vector_math_op(
                "FRACTION", self._emit_vector_math_op("MULTIPLY", coord, half)
            )
            scaled = self._emit_vector_math_op("MULTIPLY", folded, two)
            centred = self._emit_vector_math_op("SUBTRACT", scaled, one)
            return self._emit_vector_math_op(
                "SUBTRACT", one, self._emit_vector_math_op("ABSOLUTE", centred)
            )
        return coord

    def _emit_clip_mask(self, coord: int, image) -> int:
        """Cycles' Clip coverage, as a scalar in 0..1.

        NOT a hard `0 < uv < 1` test, which is what this used to be and is why the
        native path kept a fifth of the texels Cycles did. Cycles clips on the TEXEL
        INDEX, inside the bilinear tap (`interp_linear` under EXTENSION_CLIP,
        kernel/device/cpu/image.h): it bails only when `ix < -1 || ix >= width`, and
        otherwise weights all four corners through `read_clip`, which contributes
        zero for a corner outside the image. So the edge is a half-texel RAMP that
        reaches one texel further out than the unit square, not a step at 0 and 1.

        Because a bilinear tap with zeroed out-of-range corners is separable, that
        ramp is exactly `saturate(min(u*w + 0.5, (1-u)*w + 0.5))` per axis, applied
        to an EXTEND-clamped sample:

        * interior: both ramps are 1 and the clamp does nothing, so the tap is the
          ordinary bilinear one Cycles computes;
        * outer half texel: the clamp reads the single in-range corner and the ramp
          IS that corner's bilinear weight (`tx`), which is the whole sum once the
          other corner is zero;
        * beyond that: the ramp is 0, matching Cycles' early `return zero()`.

        Exact rather than approximate. Returns the coverage; the caller multiplies
        colour AND alpha by it, which is also what `zero()` does.
        """
        texel = self._image_texel_size(image)
        if texel is None:
            self._fail("Image Texture Clip needs a known image size. Needs Cycles")
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        emit = self._bound_math_emitter(zero)
        K = self._emit_scalar_constants({
            "one": 1.0,
            "half": 0.5,
            "width": 1.0 / texel[0],
            "height": 1.0 / texel[1],
        })
        coverage = None
        for lane, size_key in (("RRR1", "width"), ("GGG1", "height")):
            component = self._emit_swizzle(coord, lane)
            size = K[size_key]
            low = emit("MULTIPLY_ADD", component, size, K["half"])
            high = emit(
                "MULTIPLY_ADD", emit("SUBTRACT", K["one"], component), size, K["half"]
            )
            ramp = self._emit(
                {
                    "op": OPCODE_MATH,
                    "dst": self._alloc(),
                    "math_op": "MINIMUM",
                    "a": int(low),
                    "b": int(high),
                    "fac": int(zero),
                    "clamp": True,  # the saturate that makes this a ramp, not a line
                }
            )
            coverage = ramp if coverage is None else emit("MULTIPLY", coverage, ramp)
        return coverage

    # ------------------------------------------------------------------
    # Image Texture — Box projection
    #
    # Transcribed from `svm_node_tex_image_box` in
    # intern/cycles/kernel/svm/image.h (fetched from the Blender repo, per the
    # standing rule that Cycles is the source of truth here and is read online).
    #
    # Two properties of that function make it expressible without a new opcode:
    #
    # 1. `blend` is a NODE property (`projection_blend`), not a socket, so `limit`
    #    and every constant derived from it fold at compile time — and the whole
    #    blending half of the function disappears at the default blend of 0.
    # 2. Every branch is a select on quantities the IR can compute, so the seven
    #    zones become masks. The masks mirror Cycles' `else if` chain exactly:
    #    each one carries the complement of every test above it, or a zone would
    #    be claimed twice and the weights would not sum to 1.
    #
    # Both discarded arms of every select are still evaluated, so each division is
    # a DIVIDE (0 on a zero denominator, on CPU and GPU alike) rather than a raw
    # reciprocal — the corner where two components are both 0 is exactly the
    # corner some arm divides by their sum.
    # ------------------------------------------------------------------

    def _compile_environment_projection(self, coord: int, projection: str) -> int:
        """Sphere / Tube projection: the coordinate transform, then a flat tap.

        Transcribed from `map_to_sphere` / `map_to_tube` (util/math_float3.h) after
        `texco_remap_square` (svm/image.h), which is the 0..1 -> -1..1 remap both
        projections start from.

        Cycles guards each with `if (l > 0)` and returns (0, 0) otherwise. There is no
        branch here, so the degenerate arm has to be harmless rather than skipped:
        every division is a DIVIDE (0 on a zero denominator) and the whole result is
        multiplied by the guard, so the origin lands on (0, 0) the same way.
        """
        import math as _math

        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        emit = self._bound_math_emitter(zero)
        K = self._emit_scalar_constants({
            "one": 1.0,
            "half": 0.5,
            "inv_pi": 1.0 / _math.pi,
            "inv_two_pi": 1.0 / (2.0 * _math.pi),
        })
        K["zero"] = zero

        # texco_remap_square: (co - 0.5) * 2
        half3 = self._emit_constant((0.5, 0.5, 0.5, 1.0))
        two3 = self._emit_constant((2.0, 2.0, 2.0, 1.0))
        centred = self._emit_vector_math_op(
            "MULTIPLY", self._emit_vector_math_op("SUBTRACT", coord, half3), two3
        )
        x = self._emit_swizzle(centred, "RRR1")
        y = self._emit_swizzle(centred, "GGG1")
        z = self._emit_swizzle(centred, "BBB1")

        if projection == "TUBE":
            planar = emit("SQRT", emit("MULTIPLY_ADD", x, x, emit("MULTIPLY", y, y)))
            guard = emit("GREATER_THAN", planar, K["zero"])
            # Cycles divides both components by len before atan2. Mathematically the
            # ratio is unchanged, but it is kept so the transcription stays literal.
            angle = emit("ARCTAN2", emit("DIVIDE", x, planar), emit("DIVIDE", y, planar))
            u = emit(
                "MULTIPLY",
                emit("SUBTRACT", K["one"], emit("MULTIPLY", angle, K["inv_pi"])),
                K["half"],
            )
            v = emit("MULTIPLY", emit("ADD", z, K["one"]), K["half"])
        else:
            length_squared = emit(
                "MULTIPLY_ADD", x, x,
                emit("MULTIPLY_ADD", y, y, emit("MULTIPLY", z, z)),
            )
            guard = emit("GREATER_THAN", length_squared, K["zero"])
            # Cycles special-cases x == y == 0 to dodge a domain error in atan2f. The
            # IR's ARCTAN2 already returns 0 there, so the guard would be redundant --
            # except at the SOUTH pole, where u must be 0 and 0.5 - atan2(0,0)/2pi is
            # 0.5. Fold it in explicitly rather than inheriting whichever atan2 the
            # target platform ships.
            on_axis = emit(
                "SUBTRACT", K["one"],
                emit("GREATER_THAN",
                     emit("ADD", emit("ABSOLUTE", x), emit("ABSOLUTE", y)), K["zero"]),
            )
            azimuth = emit(
                "SUBTRACT", K["half"],
                emit("MULTIPLY", emit("ARCTAN2", x, y), K["inv_two_pi"]),
            )
            u = emit("MULTIPLY", azimuth, emit("SUBTRACT", K["one"], on_axis))
            v = emit(
                "SUBTRACT", K["one"],
                emit("MULTIPLY",
                     emit("ARCCOSINE", emit("DIVIDE", z, emit("SQRT", length_squared))),
                     K["inv_pi"]),
            )

        return self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(emit("MULTIPLY", u, guard)),
                "b": int(emit("MULTIPLY", v, guard)),
                "fac": int(K["zero"]),
            }
        )

    def _compile_box_projection(self, node, *, image, resource: int, channel: str,
                                extension: str, interpolation: str, coord: int,
                                want: str) -> int:
        """Cycles' triplanar box projection: three flat taps, normal-weighted."""
        blend = float(getattr(node, "projection_blend", 0.0) or 0.0)
        blend = max(0.0, min(1.0, blend))
        limit = 0.5 * (1.0 + blend)

        # signed_N is read before the abs, exactly as Cycles does: the weights come
        # from the folded normal, the plane flips from the signed one.
        signed_normal = self._object_space_normal()
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        emit = self._bound_math_emitter(zero)

        scalars = {"one": 1.0, "limit": limit}
        if blend > 0.0:
            scalars.update({
                "one_minus_limit": 1.0 - limit,
                "blend": blend,
                "half_one_minus_blend": 0.5 * (1.0 - blend),
                "two_minus_limit": 2.0 - limit,
                "limit_minus_one": limit - 1.0,
            })
        K = self._emit_scalar_constants(scalars)
        K["zero"] = zero

        signed = [self._emit_swizzle(signed_normal, lane)
                  for lane in self._SCALAR_LANE_MODES]
        folded = self._emit_vector_math_op("ABSOLUTE", signed_normal)
        n = [self._emit_swizzle(folded, lane) for lane in self._SCALAR_LANE_MODES]
        total = emit("ADD", emit("ADD", n[0], n[1]), n[2])
        n = [emit("DIVIDE", component, total) for component in n]

        weights = self._box_projection_weights(emit, K, n, blend=blend)
        samples = self._box_projection_samples(
            emit, K, coord, signed,
            image=image, resource=resource, channel=channel,
            extension=extension, interpolation=interpolation,
        )
        return self._blend_box_samples(emit, weights, samples, channel=channel, want=want)

    def _box_projection_weights(self, emit, K, n, *, blend: float):
        """The seven-zone weight select, as masks. `n` is the L1-normalised |normal|."""
        one = K["one"]
        pair = {
            "xy": emit("ADD", n[0], n[1]),
            "xz": emit("ADD", n[0], n[2]),
            "yz": emit("ADD", n[1], n[2]),
        }
        scaled = {key: emit("MULTIPLY", K["limit"], value) for key, value in pair.items()}

        # Corners: one face wins outright.
        corner = [
            emit("MULTIPLY", emit("GREATER_THAN", n[0], scaled["xy"]),
                 emit("GREATER_THAN", n[0], scaled["xz"])),
            emit("MULTIPLY", emit("GREATER_THAN", n[1], scaled["xy"]),
                 emit("GREATER_THAN", n[1], scaled["yz"])),
            emit("MULTIPLY", emit("GREATER_THAN", n[2], scaled["xz"]),
                 emit("GREATER_THAN", n[2], scaled["yz"])),
        ]
        # Cycles chains these with `else if`, so each mask has to exclude the ones
        # above it. Without the complements two zones claim the same texel and the
        # weights sum to 2 on the boundary.
        not_first = emit("SUBTRACT", one, corner[0])
        mask_y = emit("MULTIPLY", not_first, corner[1])
        after_two = emit("MULTIPLY", not_first, emit("SUBTRACT", one, corner[1]))
        mask_z = emit("MULTIPLY", after_two, corner[2])
        rest = emit("MULTIPLY", after_two, emit("SUBTRACT", one, corner[2]))

        if blend <= 0.0:
            # Cycles' "desperate mode": with no blending the fall-through is a flat
            # weight.x = 1, so the leftover zone folds straight into the X corner.
            return [emit("ADD", corner[0], rest), mask_y, mask_z]

        inner = {key: emit("MULTIPLY", K["one_minus_limit"], value)
                 for key, value in pair.items()}
        two_way = [
            emit("LESS_THAN", n[2], inner["xy"]),
            emit("LESS_THAN", n[0], inner["yz"]),
            emit("LESS_THAN", n[1], inner["xz"]),
        ]
        not_a = emit("SUBTRACT", one, two_way[0])
        pick_b = emit("MULTIPLY", not_a, two_way[1])
        after_b = emit("MULTIPLY", not_a, emit("SUBTRACT", one, two_way[1]))
        pick_c = emit("MULTIPLY", after_b, two_way[2])
        pick_all = emit("MULTIPLY", after_b, emit("SUBTRACT", one, two_way[2]))

        def ramp(numerator, denominator):
            """saturate((num/den - 0.5*(1-blend)) / blend) — Cycles' two-way mix."""
            share = emit("DIVIDE", numerator, denominator)
            centred = emit("SUBTRACT", share, K["half_one_minus_blend"])
            return self._emit(
                {
                    "op": OPCODE_MATH,
                    "dst": self._alloc(),
                    "math_op": "DIVIDE",
                    "a": int(centred),
                    "b": int(K["blend"]),
                    "fac": int(K["zero"]),
                    "clamp": True,  # the saturatef() in svm_node_tex_image_box
                }
            )

        mix_xy = ramp(n[0], pair["xy"])
        mix_yz = ramp(n[1], pair["yz"])
        mix_xz = ramp(n[0], pair["xz"])
        # The three-way zone. Cycles' denominator is (2*limit - 1), which IS blend.
        triple = [
            emit("DIVIDE",
                 emit("MULTIPLY_ADD", K["two_minus_limit"], component, K["limit_minus_one"]),
                 K["blend"])
            for component in n
        ]

        def accumulate(terms):
            total = None
            for mask, value in terms:
                total = (emit("MULTIPLY", mask, value) if total is None
                         else emit("MULTIPLY_ADD", mask, value, total))
            return total

        blended = [
            accumulate(terms)
            for terms in (
                ((two_way[0], mix_xy), (pick_c, mix_xz), (pick_all, triple[0])),
                ((two_way[0], emit("SUBTRACT", one, mix_xy)), (pick_b, mix_yz),
                 (pick_all, triple[1])),
                ((pick_b, emit("SUBTRACT", one, mix_yz)),
                 (pick_c, emit("SUBTRACT", one, mix_xz)), (pick_all, triple[2])),
            )
        ]
        corners = (corner[0], mask_y, mask_z)
        return [
            emit("MULTIPLY_ADD", rest, blended[axis], corners[axis])
            for axis in range(3)
        ]

    def _box_projection_samples(self, emit, K, coord: int, signed, *, image,
                                resource: int, channel: str, extension: str,
                                interpolation: str):
        """One tap per axis, on the plane coordinates Cycles uses.

        The `1 - c` flips are Cycles' "map so that no textures are flipped": which
        way a face is mirrored depends on the SIGN of that normal component, and the
        three axes do not agree on the direction of the test — X flips when negative,
        Y and Z when positive. Transcribed, not derived.
        """
        one = K["one"]
        c = [self._emit_swizzle(coord, lane) for lane in self._SCALAR_LANE_MODES]
        flipped = {axis: emit("SUBTRACT", one, c[axis]) for axis in (0, 1)}

        def select(condition, when_true, when_false):
            other = emit("SUBTRACT", one, condition)
            return emit("MULTIPLY_ADD", condition, when_true,
                        emit("MULTIPLY", other, when_false))

        planes = (
            # X face: (signed_N.x < 0) ? 1 - co.y : co.y, then co.z
            (select(emit("LESS_THAN", signed[0], K["zero"]), flipped[1], c[1]), c[2]),
            # Y face: (signed_N.y > 0) ? 1 - co.x : co.x, then co.z
            (select(emit("GREATER_THAN", signed[1], K["zero"]), flipped[0], c[0]), c[2]),
            # Z face: (signed_N.z > 0) ? 1 - co.y : co.y, then co.x
            (select(emit("GREATER_THAN", signed[2], K["zero"]), flipped[1], c[1]), c[0]),
        )

        samples = []
        for u, v in planes:
            plane_coord = self._emit(
                {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                 "a": int(u), "b": int(v), "fac": int(K["zero"])}
            )
            if self._resource_is_sampler_addressed(resource):
                # Cycles resolves the UDIM tile per tap too (svm_image_texture is
                # called once per face), so the sampler gets each face's raw plane
                # coordinate.
                samples.append(
                    self._emit_sampler_tap(
                        resource=resource,
                        channel=channel,
                        coord=plane_coord,
                        extension=extension,
                        interpolation=interpolation,
                    )
                )
                continue
            # Extension and interpolation are per-TAP: each face is its own 2D
            # lookup, so clamping or mirroring the 3D coordinate up front would
            # wrap the wrong axes.
            plane_coord = self._apply_image_extension(plane_coord, extension, image)
            plane_coord = self._apply_image_interpolation(plane_coord, interpolation, image)
            samples.append(
                self._emit(
                    {
                        "op": OPCODE_SAMPLE_IMAGE,
                        "dst": self._alloc(),
                        "resource": int(resource),
                        "channel": channel,
                        "coord": int(plane_coord),
                        **({"mode": interpolation} if interpolation in _BICUBIC_INTERPOLATIONS else {}),
                    }
                )
            )
        return samples

    def _blend_box_samples(self, emit, weights, samples, *, channel: str, want: str) -> int:
        """Sum the three taps by weight, in whichever form the caller asked for.

        Cycles accumulates a float4 and splits it at the end. Here Color and Alpha
        are separate compiles with their own resource, so each one only has to blend
        the lanes it will actually return — and the alpha case has to be reduced to a
        scalar BEFORE blending, because VECTOR_MATH never touches the w lane.
        """
        if want == "SCALAR" or channel == "A":
            lane = "A" if channel == "A" else "LUMA"
            total = None
            for weight, sample in zip(weights, samples):
                term = emit("MULTIPLY", weight, self._emit_swizzle(sample, lane))
                total = term if total is None else emit("ADD", total, term)
            if want == "SCALAR":
                return total
            # Colour-shaped alpha, matching the flat path's AAA1 swizzle.
            return self._emit(
                {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                 "a": int(total), "b": int(total), "fac": int(total)}
            )

        total = None
        for weight, sample in zip(weights, samples):
            fan = self._emit(
                {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                 "a": int(weight), "b": int(weight), "fac": int(weight)}
            )
            # Emitted directly rather than through _emit_vector_math_op, which
            # materialises a fresh zero CONSTANT per call; this expansion is already
            # the largest single node in the IR and every op counts against _MAX_OPS.
            total = self._emit(
                {
                    "op": OPCODE_VECTOR_MATH,
                    "dst": self._alloc(),
                    "math_op": "MULTIPLY" if total is None else "MULTIPLY_ADD",
                    "a": int(sample),
                    "b": int(fan),
                    "fac": int(fan if total is None else total),
                }
            )
        return total

    def _apply_image_interpolation(self, coord: int, interpolation: str, image) -> int:
        """Snap the coordinate to texel centres so a bilinear tap lands exactly on one.

        Closest is what an artist reaches for on a palette or ID lookup, where any
        blending between neighbours is the bug. Sampling it through a bilinear
        sampler is exact as long as the coordinate sits on a texel centre.
        """
        if interpolation != "CLOSEST":
            return coord
        texel = self._image_texel_size(image)
        if texel is None:
            self._fail("Image Texture Closest needs a known image size. Needs Cycles")
        size = self._emit_constant((1.0 / texel[0], 1.0 / texel[1], 1.0, 1.0))
        inv = self._emit_constant((texel[0], texel[1], 1.0, 1.0))
        half = self._emit_constant((0.5, 0.5, 0.5, 1.0))
        scaled = self._emit_vector_math_op("MULTIPLY", coord, size)
        snapped = self._emit_vector_math_op(
            "ADD", self._emit_vector_math_op("FLOOR", scaled), half
        )
        return self._emit_vector_math_op("MULTIPLY", snapped, inv)

    def _corner_attr_fetch(self, channel_tag: str) -> int:
        """One per-corner sidecar fetch, reusing an already-registered resource."""
        for index, item in enumerate(self.resources):
            if str(item.get("channel") or "") == channel_tag:
                resource_index = index
                break
        else:
            resource_index = len(self.resources)
            if resource_index >= _MAX_RESOURCES:
                self._fail("Material IR resource budget exceeded")
            self.resources.append({"channel": channel_tag, "image": None})
        return self._emit(
            {
                "op": OPCODE_ATTR_CORNER_FLOAT,
                "dst": self._alloc(),
                "resource": int(resource_index),
            }
        )

    def _compile_named_uv_layer(self, layer_name: str, *, want: str) -> int:
        """A UV set other than the one the bake is projecting into.

        `ATTR_UV` carries no layer identity, so it can only ever mean the active
        layer. A UV layer is a per-corner float pair that Cycles interpolates
        barycentrically -- structurally the same thing a colour attribute is -- so it
        rides the same sidecar: one resource per component, recombined here. The
        third component is 0, matching Blender's UV output.
        """
        layer_name = str(layer_name or "").strip()
        if not layer_name:
            self._fail("UV Map node has no layer name. Needs Cycles")
        # One sidecar serves the whole group, so a layer missing from any contributing
        # mesh would hand another object's corners to this one. Refuse while the
        # reason is still nameable rather than letting the exporter return a bare None.
        objects = list(self._attribute_objects or ())
        if objects and not all(self._mesh_uv_layer(obj, layer_name) for obj in objects):
            self._fail(
                f"UV map '{layer_name}' is missing from at least one high mesh. Needs Cycles"
            )
        u = self._corner_attr_fetch(corner_uv_channel_tag(layer_name, 0))
        v = self._corner_attr_fetch(corner_uv_channel_tag(layer_name, 1))
        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        reg = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(u),
                "b": int(v),
                "fac": int(zero),
            }
        )
        # A named UV is a coordinate source like ATTR_UV: a Bump over it needs the shift.
        reg = self._shift_coordinate(reg)
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    def _compile_corner_color_attribute(self, layer_name: str, out_name: str, *, want: str) -> int:
        """A mesh colour attribute (Color Attribute node, or a colour-typed Attribute node).

        Cycles interpolates a colour layer barycentrically over the triangle, which
        is exactly what the per-corner sidecar plus the packed record's barycentric
        fetch reproduce -- the same route Geometry Pointiness already takes. A
        colour needs one sidecar per component because a sidecar texel carries one
        bit-exact float32, so RGB costs three fetches and a COMBINE_XYZ.

        Alpha comes from the fourth component. `Fac` on the Attribute node is
        Cycles' average of the three colour components, NOT a luminance: see
        svm_attribute's average() for float3 attributes.
        """
        layer_name = str(layer_name or "").strip()
        if not layer_name:
            self._fail("Colour attribute has no name. Needs Cycles")
        wants_alpha = str(out_name or "").strip().upper() == "ALPHA"
        if wants_alpha:
            alpha = self._corner_attr_fetch(corner_color_channel_tag(layer_name, 3))
            return alpha if want == "SCALAR" else self._emit_swizzle(alpha, "RRR1")

        components = [
            self._corner_attr_fetch(corner_color_channel_tag(layer_name, index))
            for index in range(3)
        ]
        if want == "SCALAR" and str(out_name or "").strip().upper() in {"FAC", "FACTOR"}:
            total = self._emit_math_op("ADD", components[0], components[1])
            total = self._emit_math_op("ADD", total, components[2])
            third = self._emit_swizzle(
                self._emit_constant((1.0 / 3.0,) * 3 + (1.0,)), "LUMA"
            )
            return self._emit_math_op("MULTIPLY", total, third)
        colour = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(components[0]),
                "b": int(components[1]),
                "fac": int(components[2]),
            }
        )
        if want == "SCALAR":
            return self._emit_swizzle(colour, "LUMA")
        return colour

    def _compile_corner_float_attribute(self, name: str, out_name: str, *, want: str) -> int:
        """A named scalar FLOAT geometry attribute, through the per-corner sidecar.

        The route colour attributes already take, and cheaper: a scalar is one
        sidecar and one fetch. Cycles interpolates a float attribute barycentrically,
        which is exactly what the packed record's barycentric fetch reproduces.

        Cycles broadcasts a float attribute to all three components on the Color
        output (svm_attribute hands back float3(f, f, f)), and reports 1.0 on Alpha
        because a float carries none -- both measured, and both mirrored here.
        """
        upper = str(out_name or "").strip().upper()
        if upper == "ALPHA":
            one = self._emit_constant((1.0, 1.0, 1.0, 1.0))
            return self._emit_swizzle(one, "LUMA") if want == "SCALAR" else one
        value = self._corner_attr_fetch(corner_float_attr_tag(name))
        if want == "SCALAR":
            return value
        return self._emit_swizzle(value, "RRR1")

    def _compile_attribute(self, node, out_name: str, *, want: str) -> int:
        """Attribute node, for the cases that resolve to a constant.

        OBJECT and VIEW_LAYER read a custom property off the object or the scene,
        which is a constant for a bake. A GEOMETRY attribute that no contributing
        mesh carries reads zero. Everything else -- a geometry attribute that does
        exist -- needs a per-hit attribute fetch the IR cannot express yet.

        Measured against Cycles: OBJECT 'fyr_probe' = 0.375 baked 0.375;
        VIEW_LAYER 'fyr_scene_probe' = 0.625 baked 0.625; a missing geometry
        attribute and the node's own empty-name default both baked 0.0; and Alpha
        reads 1.0 for a float attribute rather than the value.
        """
        attribute_type = str(getattr(node, "attribute_type", "GEOMETRY") or "GEOMETRY").strip().upper()
        name = str(getattr(node, "attribute_name", "") or "").strip()
        objects = self._attribute_objects

        def _custom_property(holders):
            """First holder carrying *name* as a custom property, else ``_MISSING``."""
            for holder in holders:
                if holder is None:
                    continue
                try:
                    if name and name in holder.keys():
                        return holder[name]
                except Exception:
                    continue
            return _MISSING

        _MISSING = object()
        if attribute_type == "VIEW_LAYER":
            import bpy

            # Blender's lookup order (BKE_view_layer_find_rgba_attribute): the view
            # layer, then the scene, then its world. A name nothing carries reads zero
            # on every output, Alpha included -- measured 2026-10-02 for a plain and a
            # dotted name ('zen_bbq.preview_map_index', an add-on property group that
            # is not registered when the add-on is absent); a view-layer property won
            # over a scene property of the same name. Refusing a missing name to Cycles
            # sent every ZenBBQ material there for a value that is simply 0.
            scene = getattr(bpy.context, "scene", None)
            value = _custom_property(
                (getattr(bpy.context, "view_layer", None), scene, getattr(scene, "world", None))
            )
            if value is _MISSING:
                value = 0.0
            elif out_name == "Alpha":
                # A float attribute carries no alpha; Cycles reports 1.0.
                value = 1.0
        elif attribute_type == "OBJECT":
            if not objects:
                self._fail("Object attributes have no object context in this compile. Needs Cycles")
            values = []
            for obj in objects:
                # The object, then its data block (measured: a property on the mesh
                # is found); missing on both reads zero, Alpha included.
                found = _custom_property((obj, getattr(obj, "data", None)))
                if found is _MISSING:
                    values.append(0.0)
                elif out_name == "Alpha":
                    values.append(1.0)
                else:
                    values.append(found)
            first = values[0]
            if any(other != first for other in values[1:]):
                self._fail(
                    f"Attribute '{name}' differs between the objects sharing this material. Needs Cycles"
                )
            value = first
        elif out_name == "Alpha":
            # A float attribute carries no alpha; Cycles reports 1.0.
            value = 1.0
        elif attribute_type == "GEOMETRY":
            if name and objects and all(self._mesh_uv_layer(obj, name) for obj in objects):
                # The explicit attribute name is independent of the bake target UV,
                # even when it is the mesh's active render UV.
                if name == self._bake_uv_layer_name:
                    reg = self._emit_attr(OPCODE_ATTR_UV)
                    return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg
                return self._compile_named_uv_layer(name, want=want)
            if name and objects and all(self._mesh_color_attribute(obj, name) for obj in objects):
                # A colour layer rides the per-corner sidecar route (see
                # _compile_corner_color_attribute). Every contributing object has to
                # carry it: one sidecar serves the whole group, and a missing layer
                # on one object would read another object's corners.
                return self._compile_corner_color_attribute(name, out_name, want=want)
            if name and objects and all(self._mesh_float_attribute(obj, name) for obj in objects):
                # A scalar mask -- painted, or written by geometry nodes. Same
                # per-corner sidecar the colour layer above rides, one channel
                # instead of three. Every contributing object has to carry it: one
                # sidecar serves the whole group, so a missing layer on one object
                # would read another object's corners.
                return self._compile_corner_float_attribute(name, out_name, want=want)
            if name and objects and any(self._mesh_has_attribute(obj, name) for obj in objects):
                self._fail(
                    f"Geometry attribute '{name}' needs a per-hit attribute fetch. Needs Cycles"
                )
            # No such attribute anywhere (or no name at all): Cycles reads zero.
            value = 0.0
        elif attribute_type == "INSTANCER":
            # Reads an attribute off the instancing object. A bake evaluates real
            # meshes, never instances, so there is no instancer to read and Cycles
            # returns zero -- the same answer as a geometry attribute that does not
            # exist, a few lines above.
            value = 0.0
        else:
            self._fail(f"Attribute type '{attribute_type}' is not native yet. Needs Cycles")

        try:
            if isinstance(value, (int, float, bool)):
                scalar = float(value)
                rgba = (scalar, scalar, scalar, 1.0)
            else:
                components = [float(v) for v in value]
                if len(components) < 3:
                    components = (components + [0.0, 0.0, 0.0])[:3]
                rgba = (components[0], components[1], components[2], 1.0)
        except (TypeError, ValueError):
            self._fail(f"Attribute '{name}' is not a numeric property. Needs Cycles")

        reg = self._emit_constant(rgba)
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    _OBJECT_INFO_OUTPUTS = {
        "Location": "location",
        "Color": "color",
        "Alpha": "alpha",
        "Object Index": "object_index",
        "Material Index": "material_index",
        "Random": "random",
    }

    def _compile_object_info(self, out_name: str, *, want: str) -> int:
        """Object Info, folded into the program as per-object constants.

        These are properties of the object, but a Material IR program is compiled
        once per material and shared by every object using it. A constant is only
        correct when every contributing object agrees; resolve_object_info leaves
        a field None when they do not, and that output falls back to Cycles rather
        than baking one object's value onto another object's texels.
        """
        info = self._object_info
        if info is None:
            self._fail(
                "Object Info has no object context in this compile. Needs Cycles"
            )
        key = self._OBJECT_INFO_OUTPUTS.get(str(out_name or ""))
        if key is None:
            self._fail(f"Object Info '{out_name}' is not a native output. Needs Cycles")
        value = info.get(key)
        if value is None:
            self._fail(
                f"Object Info '{out_name}' differs between the objects sharing this "
                "material. Needs Cycles"
            )
        if key in {"location", "color"}:
            rgba = (float(value[0]), float(value[1]), float(value[2]), 1.0)
        else:
            scalar = float(value)
            rgba = (scalar, scalar, scalar, 1.0)
        reg = self._emit_constant(rgba)
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_bump(self, node, *, want: str) -> int:
        """Bump, by finite differences over the height expression.

        Cycles uses screen-space derivatives, which a baker has no equivalent of.
        Instead the height subexpression is compiled four times -- at plus and minus
        one epsilon along each of the two coordinate axes -- and the perturbed normal
        is built from the central differences. compile_socket does not memoise, so
        each call genuinely re-emits the chain. No new opcodes: this runs on ops both
        backends already execute.
        """
        height_socket = node.inputs.get("Height")
        if height_socket is None or not bool(getattr(height_socket, "is_linked", False)):
            # Constant height has zero gradient, so the normal is unperturbed.
            return self._emit_attr(OPCODE_ATTR_NORMAL)
        strength = self.compile_socket(node.inputs.get("Strength"), want="SCALAR")
        distance = self.compile_socket(node.inputs.get("Distance"), want="SCALAR")

        # A CENTRAL difference, (h(x+e) - h(x-e)) / 2e, is second-order accurate where
        # a forward difference is first-order and carries an O(e * h'') bias. It costs
        # a fourth height evaluation. Measured against Cycles at Strength 1.0: 0.0123
        # central against 0.0140 forward.
        #
        # Rather than spend that on coverage -- a fourth evaluation would drop the
        # largest natively supported height chain from ~69 ops to ~52 -- fall back to
        # the forward difference when only three fit. Accuracy improves where there is
        # room and nothing that compiled natively before stops doing so.
        #
        # Epsilon is not the limit here: 1e-4 measures 0.0123 against 1e-3's 0.0123,
        # so the truncation error is already below the residual. Do not tune it
        # expecting a gain.
        epsilon = 0.001
        before = len(self.ops)
        with self._coordinate_offset((epsilon, 0.0, 0.0)):
            plus_u = self.compile_socket(height_socket, want="SCALAR")
        height_cost = len(self.ops) - before
        # Tail after the height chains: slope maths, the UV-scale divide, COMBINE_XYZ,
        # TANGENT_TO_WORLD, the Strength lerp, and the channel-level world->tangent
        # encode. Decline rather than truncate.
        budget = GPU_MAX_OPS - len(self.ops) - 48
        central = budget >= 3 * height_cost
        if not central and budget < 2 * height_cost:
            self._fail(
                "Bump height expression is too large to differentiate within the "
                f"{GPU_MAX_OPS}-op program budget. Needs Cycles"
            )

        if central:
            with self._coordinate_offset((-epsilon, 0.0, 0.0)):
                base_u = self.compile_socket(height_socket, want="SCALAR")
        else:
            base_u = self.compile_socket(height_socket, want="SCALAR")
        with self._coordinate_offset((0.0, epsilon, 0.0)):
            plus_v = self.compile_socket(height_socket, want="SCALAR")
        if central:
            with self._coordinate_offset((0.0, -epsilon, 0.0)):
                base_v = self.compile_socket(height_socket, want="SCALAR")
        else:
            base_v = base_u

        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
        inv_eps = self._emit_swizzle(
            self._emit_constant(
                (1.0 / ((2.0 if central else 1.0) * epsilon),) * 3 + (1.0,)
            ),
            "LUMA",
        )
        # Distance scales the gradient; Strength does NOT. Cycles applies Strength as
        # a lerp toward the geometric normal AFTER normalizing the bumped one (see
        # the end of this function). Folding it into the gradient agrees only to
        # first order in slope -- measured 0.018 against Cycles at Strength 0.5
        # where Strength 1.0, which cannot tell the two forms apart, measured 0.014.
        scale = distance
        if bool(getattr(node, "invert", False)):
            scale = self._emit_math_op("SUBTRACT", zero, scale)

        def slope(plus, minus):
            diff = self._emit_math_op("SUBTRACT", plus, minus)
            gradient = self._emit_math_op("MULTIPLY", diff, inv_eps)
            scaled = self._emit_math_op("MULTIPLY", gradient, scale)
            # The surface tilts against the gradient.
            return self._emit_math_op("SUBTRACT", zero, scaled)

        # Cycles' bump reduces, for a UV parameterization, to a TANGENT-space normal
        # of (-dH/du / |dP/du|, -dH/dv / |dP/dv|, 1). The slopes are per UV unit and
        # the frame is unit world, so they only agree once divided by the world size
        # of a UV unit -- see resolve_uv_to_world_scales. Dropping that divisor
        # measures mean 0.123 against Cycles where including it measures 0.016.
        # The previous form added the offset to the world-space ATTR_NORMAL, which
        # is only equivalent where the tangent frame IS the world axes and one UV
        # unit spans two world units: true of a flat unwrapped quad, and of nothing
        # else. That is why it read correct until the fixture stopped being flat.
        inv_u, inv_v = (
            self._emit_swizzle(self._emit_constant((1.0 / axis,) * 3 + (1.0,)), "LUMA")
            for axis in self._uv_to_world_scale
        )
        perturbed = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(self._emit_math_op("MULTIPLY", slope(plus_u, base_u), inv_u)),
                "b": int(self._emit_math_op("MULTIPLY", slope(plus_v, base_v), inv_v)),
                "fac": int(one),
            }
        )
        bumped = self._emit(
            {"op": OPCODE_TANGENT_TO_WORLD, "dst": self._alloc(), "fac": int(perturbed)}
        )
        # normalize(strength * N_bump + (1 - strength) * N_geom), Cycles' own form.
        # Scalars are broadcast across xyz, so they feed VECTOR_MATH directly.
        clamped_strength = self._emit_math_op("MAXIMUM", strength, zero)
        geometric = self._emit_attr(OPCODE_ATTR_NORMAL)
        result = self._emit_vector_math_op(
            "NORMALIZE",
            self._emit_vector_math_op(
                "ADD",
                self._emit_vector_math_op("MULTIPLY", bumped, clamped_strength),
                self._emit_vector_math_op(
                    "MULTIPLY",
                    geometric,
                    self._emit_math_op("SUBTRACT", one, clamped_strength),
                ),
            ),
        )
        if want == "SCALAR":
            return self._emit_swizzle(result, "LUMA")
        return result

    def _compile_displacement(self, node, *, want: str) -> int:
        """Displacement node: (Height - Midlevel) * Scale along the normal."""
        height = self.compile_socket(node.inputs.get("Height"), want="SCALAR")
        midlevel = self.compile_socket(node.inputs.get("Midlevel"), want="SCALAR")
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        amount = self._emit_math_op(
            "MULTIPLY", self._emit_math_op("SUBTRACT", height, midlevel), scale
        )
        normal_socket = node.inputs.get("Normal")
        if normal_socket is not None and bool(getattr(normal_socket, "is_linked", False)):
            normal = self.compile_socket(normal_socket, want="COLOR")
        else:
            normal = self._emit_attr(OPCODE_ATTR_NORMAL)
        spread = self._emit({"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                             "a": int(amount), "b": int(amount), "fac": int(amount)})
        result = self._emit_vector_math_op("MULTIPLY", normal, spread)
        if want == "SCALAR":
            return self._emit_swizzle(result, "LUMA")
        return result

    def _compile_vector_displacement(self, node, *, want: str) -> int:
        """Vector Displacement: (Vector - Midlevel) * Scale in the chosen space."""
        space = str(getattr(node, "space", "") or "TANGENT").strip().upper()
        tangent_space = "TANGENT" in space
        vector = self.compile_socket(node.inputs.get("Vector"), want="COLOR")
        midlevel = self.compile_socket(node.inputs.get("Midlevel"), want="SCALAR")
        scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
        mid3 = self._emit({"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                           "a": int(midlevel), "b": int(midlevel), "fac": int(midlevel)})
        scale3 = self._emit({"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                             "a": int(scale), "b": int(scale), "fac": int(scale)})
        centred = self._emit_vector_math_op("SUBTRACT", vector, mid3)
        result = self._emit_vector_math_op("MULTIPLY", centred, scale3)
        if tangent_space:
            result = self._emit(
                {"op": OPCODE_TANGENT_TO_WORLD, "dst": self._alloc(), "fac": int(result)}
            )
        if want == "SCALAR":
            return self._emit_swizzle(result, "LUMA")
        return result

    def _compile_normal_map(self, node, *, want: str) -> int:
        """Normal Map node.

        Tangent and World space are native. Object space and Blender's two legacy
        spaces need an object-matrix transform / axis remap the compiler does not do,
        and used to be treated as plain world space -- silently wrong on any rotated
        object -- so they refuse instead.
        """
        space = str(getattr(node, "space", "") or "TANGENT").strip().upper()
        if space in {"BLENDER_OBJECT", "BLENDER_WORLD"}:
            self._fail(
                f"Normal Map space '{space}' is not native yet. Needs Cycles "
                "(supported: Tangent Space, World Space, Object Space)"
            )
        object_space = space == "OBJECT"
        tangent_space = space not in {"WORLD", "OBJECT"}
        uv_layer = str(getattr(node, "uv_map", "") or "").strip()
        if tangent_space and not uv_layer:
            uv_layer = self._active_render_uv_layer_name()
        if tangent_space and uv_layer and uv_layer == self._bake_uv_layer_name:
            # The requested tangent frame is exactly the projection frame.
            uv_layer = ""
        if tangent_space and uv_layer:
            # One sidecar serves the whole group, so a layer missing from any
            # contributing mesh would hand another object's frame to this one. A wrong
            # tangent frame is a wrong normal map everywhere, not a local artefact.
            objects = list(self._attribute_objects or ())
            if objects and not all(self._mesh_uv_layer(obj, uv_layer) for obj in objects):
                self._fail(
                    f"Normal Map's tangent UV map '{uv_layer}' is missing from at least "
                    "one high mesh. Needs Cycles"
                )
        # `base` (Original / Displaced) picks which surface the perturbation is applied
        # to. It is DISPLACED by default in Blender 5.x, and the two are the same
        # surface unless the material actually displaces -- which this bake does not do
        # unless something is wired into Material Output's Displacement. Refusing the
        # default outright, as this did for one commit, sent every Normal Map node to
        # Cycles; refusing only the case where the choice can matter is the honest line.
        base = str(getattr(node, "base", "") or "").strip().upper()
        if base == "DISPLACED" and self._tree_displaces(getattr(node, "id_data", None)):
            self._fail(
                "Normal Map base 'Displaced' with a displaced surface is not native yet. "
                "Needs Cycles"
            )
        color = self.compile_socket(node.inputs.get("Color"), want="COLOR")
        strength = self.compile_socket(node.inputs.get("Strength"), want="SCALAR")
        # Decode [0,1] -> [-1,1].
        two = self._emit_constant((2.0, 2.0, 2.0, 1.0))
        one = self._emit_constant((1.0, 1.0, 1.0, 1.0))
        scaled = self._emit_vector_math_op("MULTIPLY", color, two)
        decoded = self._emit_vector_math_op("SUBTRACT", scaled, one)
        # DirectX convention stores an inverted green channel. Blender flips it; the
        # compiler used to ignore `convention` entirely, so a DirectX map baked with
        # inverted Y relief and no warning. See MATERIAL_BAKE_QA_2026_08_19_PASS2.md, G5.
        if str(getattr(node, "convention", "OPENGL") or "OPENGL").strip().upper() == "DIRECTX":
            flip_y = self._emit_constant((1.0, -1.0, 1.0, 1.0))
            decoded = self._emit_vector_math_op("MULTIPLY", decoded, flip_y)

        if tangent_space:
            # Cycles applies Strength IN TANGENT SPACE (svm_node_normal_map):
            #   color.x *= strength; color.y *= strength
            #   color.z  = mix(1, color.z, saturate(strength))
            # then transforms. This used to be a MIX between the WORLD-space
            # geometric normal and the TANGENT-space decoded one -- two different
            # spaces -- which happens to track Cycles closely for strength <= 1 and
            # comes apart completely above it. Measured on a flat quad at Strength
            # 2.0 before this: mean 239/255, 100% of texels over 8/255.
            #
            # Note the asymmetry, which is the whole point of the formulation: XY
            # scale without limit (a strength of 3 really does treble the slope)
            # while Z only ever interpolates toward 1, because a normal leaning past
            # the tangent plane is not a normal.
            saturated = self._emit(
                {
                    "op": OPCODE_MATH,
                    "dst": self._alloc(),
                    "math_op": "MULTIPLY",
                    "a": int(strength),
                    "b": int(self._emit_swizzle(one, "RRR1")),
                    "fac": int(self._emit_swizzle(one, "RRR1")),
                    "clamp": True,  # saturatef(strength)
                }
            )
            one_scalar = self._emit_swizzle(one, "RRR1")
            xy_scale = self._emit(
                {
                    "op": OPCODE_COMBINE_XYZ,
                    "dst": self._alloc(),
                    "a": int(strength),
                    "b": int(strength),
                    "fac": int(one_scalar),
                }
            )
            leaned = self._emit_vector_math_op("MULTIPLY", decoded, xy_scale)
            # z = 1 + (z - 1) * saturate(strength)
            z_component = self._emit_swizzle(decoded, "BBB1")
            z_remapped = self._emit_math_op(
                "MULTIPLY_ADD",
                self._emit_math_op("SUBTRACT", z_component, one_scalar),
                saturated,
            )
            z_remapped = self._emit_math_op("ADD", z_remapped, one_scalar)
            tangent_normal = self._emit(
                {
                    "op": OPCODE_COMBINE_XYZ,
                    "dst": self._alloc(),
                    "a": int(self._emit_swizzle(leaned, "RRR1")),
                    "b": int(self._emit_swizzle(leaned, "GGG1")),
                    "fac": int(z_remapped),
                }
            )
            if uv_layer:
                # A named layer's frame is not the one TANGENT_TO_WORLD carries, so
                # the transform is built here from the sidecar instead.
                result = self._named_layer_tangent_to_world(tangent_normal, uv_layer)
            else:
                # TANGENT_TO_WORLD already normalises, matching Cycles'
                # safe_normalize(to_global(...)).
                result = self._emit(
                    {"op": OPCODE_TANGENT_TO_WORLD, "dst": self._alloc(),
                     "fac": int(tangent_normal)}
                )
        else:
            # World space: Cycles sets linear_interpolate_strength and blends the
            # normalised colour toward the shading normal by strength. That IS the
            # MIX form, so this branch keeps it.
            geometric = self._emit({"op": OPCODE_ATTR_NORMAL, "dst": self._alloc()})
            if object_space:
                # Cycles' object_normal_transform: the inverse-transpose of the
                # object's matrix, normalised, applied before the strength blend.
                # VECTOR_TRANSFORM NORMAL is exactly that.
                world_decoded = self._emit(
                    {
                        "op": OPCODE_VECTOR_TRANSFORM,
                        "dst": self._alloc(),
                        "src": int(decoded),
                        "mode": "NORMAL",
                        "clamp": False,  # OBJECT -> WORLD
                    }
                )
            else:
                world_decoded = self._emit_vector_math_op("NORMALIZE", decoded)
            blended = self._emit(
                {
                    "op": OPCODE_MIX,
                    "dst": self._alloc(),
                    "a": int(geometric),
                    "b": int(world_decoded),
                    "fac": int(strength),
                    "blend": "MIX",
                }
            )
            result = self._emit_vector_math_op("NORMALIZE", blended)
        if want == "SCALAR":
            return self._emit_swizzle(result, "LUMA")
        return result

    def _compile_tex_environment(self, node, out_name: str, *, want: str) -> int:
        """Environment Texture: a direction -> a lat-long or mirror-ball lookup.

        Transcribed from `svm_node_tex_environment` (svm/image.h) and the two
        projections in `kernel/camera/projection.h`, both fetched from the Blender
        repo:

            equirect: u = (atan2(d.y, d.x) - pi) / -2pi
                      v = (acos(d.z / len(d)) - pi) / -pi     [d already normalised]
            mirror:   d.y -= 1
                      div = 2 * sqrt(max(-0.5 * d.y, 0))
                      d /= div  (when div > 0)
                      u = 0.5 * (d.x + 1);  v = 0.5 * (d.z + 1)

        The Vector input has to be linked. Left unlinked, Cycles feeds this node
        the incoming ray direction, which a bake does not have -- that is the
        view-dependent case, and it refuses rather than inventing a direction.

        Cycles' `is_zero(dir) -> (0, 0)` and `if (div > 0)` guards are multiplied
        in rather than branched on, the same trick `_compile_environment_projection`
        uses: every division is a DIVIDE (zero on a zero denominator) and the guard
        scales the result.
        """
        import math as _math

        image = getattr(node, "image", None)
        if image is None:
            self._fail(
                f"Material '{self.material_name}' has an Environment Texture with no image"
            )
        vector_socket = node.inputs.get("Vector")
        if vector_socket is None or not bool(getattr(vector_socket, "is_linked", False)):
            self._fail(
                "Environment Texture with no Vector input samples along the incoming "
                "ray, which is view-dependent and cannot be baked"
            )
        interpolation = str(getattr(node, "interpolation", "Linear") or "Linear").strip().upper()
        if interpolation not in {"LINEAR", "CLOSEST"}:
            self._fail(
                f"Environment Texture interpolation '{interpolation.title()}' is not "
                "native yet. Needs Cycles (supported: Linear, Closest)"
            )
        projection = str(
            getattr(node, "projection", "EQUIRECTANGULAR") or "EQUIRECTANGULAR"
        ).strip().upper()
        if projection not in {"EQUIRECTANGULAR", "MIRROR_BALL"}:
            self._fail(
                f"Environment Texture projection '{projection}' is not native yet. Needs Cycles"
            )

        if str(getattr(image, "source", "") or "").upper() == "TILED":
            # Cycles' Environment Texture carries no tile list, so a UDIM image there
            # is not a tile table; do not guess which tile it reads.
            self._fail("Environment Texture with a UDIM image is not native yet. Needs Cycles")
        channel = "A" if out_name.upper() == "ALPHA" else "RGBA"
        resource = self._add_image_resource(image, channel=channel)
        direction = self._compile_vector_value(vector_socket, fallback=(0.0, 0.0, 0.0))
        direction = self._emit_vector_math_op("NORMALIZE", direction)

        zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")
        emit = self._bound_math_emitter(zero)
        K = self._emit_scalar_constants({
            "one": 1.0,
            "half": 0.5,
            "two": 2.0,
            "neg_half": -0.5,
            "pi": _math.pi,
            "inv_pi": 1.0 / _math.pi,
            "neg_inv_two_pi": -1.0 / (2.0 * _math.pi),
        })
        K["zero"] = zero
        x = self._emit_swizzle(direction, "RRR1")
        y = self._emit_swizzle(direction, "GGG1")
        z = self._emit_swizzle(direction, "BBB1")

        if projection == "EQUIRECTANGULAR":
            # safe_normalize leaves a zero direction zero, and Cycles then returns
            # (0, 0) for it. length is the guard: 1 for any real direction.
            length = emit(
                "SQRT",
                emit(
                    "MULTIPLY_ADD", x, x,
                    emit("MULTIPLY_ADD", y, y, emit("MULTIPLY", z, z)),
                ),
            )
            guard = emit("GREATER_THAN", length, K["zero"])
            u = emit(
                "MULTIPLY",
                emit("SUBTRACT", emit("ARCTAN2", y, x), K["pi"]),
                K["neg_inv_two_pi"],
            )
            v = emit(
                "MULTIPLY",
                emit("SUBTRACT", emit("ARCCOSINE", emit("DIVIDE", z, length)), K["pi"]),
                emit("SUBTRACT", K["zero"], K["inv_pi"]),
            )
            u = emit("MULTIPLY", u, guard)
            v = emit("MULTIPLY", v, guard)
        else:
            shifted_y = emit("SUBTRACT", y, K["one"])
            div = emit(
                "MULTIPLY",
                K["two"],
                emit("SQRT", emit("MAXIMUM", emit("MULTIPLY", K["neg_half"], shifted_y), K["zero"])),
            )
            guard = emit("GREATER_THAN", div, K["zero"])
            # Outside the guard Cycles leaves the vector undivided, so mix rather
            # than multiply: divided when div > 0, raw otherwise.
            def _guarded(component: int) -> int:
                divided = emit("DIVIDE", component, div)
                return emit(
                    "ADD",
                    emit("MULTIPLY", divided, guard),
                    emit("MULTIPLY", component, emit("SUBTRACT", K["one"], guard)),
                )

            u = emit("MULTIPLY", K["half"], emit("ADD", _guarded(x), K["one"]))
            v = emit("MULTIPLY", K["half"], emit("ADD", _guarded(z), K["one"]))

        coord = self._emit(
            {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
             "a": int(u), "b": int(v), "fac": int(zero)}
        )
        # No extension property on this node: Cycles samples an environment with
        # the repeat sampler, which is what the backend's default tap does.
        if self._resource_is_sampler_addressed(resource):
            reg = self._emit_sampler_tap(
                resource=resource,
                channel=channel,
                coord=coord,
                extension="REPEAT",
                interpolation=interpolation,
            )
            if want == "SCALAR":
                return self._emit_swizzle(reg, "A" if channel == "A" else "LUMA")
            if channel == "A":
                return self._emit_swizzle(reg, "AAA1")
            return reg
        coord = self._apply_image_interpolation(coord, interpolation, image)
        reg = self._emit(
            {
                "op": OPCODE_SAMPLE_IMAGE,
                "dst": self._alloc(),
                "resource": int(resource),
                "channel": channel,
                "coord": int(coord),
                **({"mode": interpolation} if interpolation in _BICUBIC_INTERPOLATIONS else {}),
            }
        )
        if want == "SCALAR":
            return self._emit_swizzle(reg, "A" if channel == "A" else "LUMA")
        if channel == "A":
            return self._emit_swizzle(reg, "AAA1")
        return reg

    def _compile_tangent(self, node, *, want: str) -> int:
        """Blender's Tangent node, transcribed from `svm_node_tangent`.

        (`intern/cycles/kernel/svm/tex_coord.h`, fetched from the Blender repo.)
        Both branches end in the same two lines, which is why the orthogonalisation
        below is shared:

            object_normal_transform(kg, sd, &tangent);
            tangent = cross(sd->N, normalize(cross(tangent, sd->N)));

        **UV Map.** The tangent is the MikkTSpace attribute, in OBJECT space. That is
        exactly what the bake already carries: `TANGENT_TO_WORLD` holds the frame of
        the layer being projected into, and a named layer rides the per-corner
        sidecar (`_named_layer_tangent_to_world`). Feeding either the unit X vector
        returns T, because a tangent-space basis is (T, B, N) by construction.

        **Radial.** A swirl around one object axis, built from the Generated
        coordinate. Note the offset is `generated - 0.5`, not `generated * 2 - 1`;
        the two differ by a factor of two, which the final normalise removes, but
        the transcription follows the source.

        Not view-dependent: every term is geometry. The node refused only because
        nothing had claimed it yet.
        """
        direction_type = str(getattr(node, "direction_type", "RADIAL") or "RADIAL").strip().upper()
        if direction_type == "UV_MAP":
            unit_x = self._emit_constant((1.0, 0.0, 0.0, 1.0))
            uv_layer = str(getattr(node, "uv_map", "") or "").strip()
            if not uv_layer:
                uv_layer = self._active_render_uv_layer_name()
            if uv_layer and uv_layer == self._bake_uv_layer_name:
                uv_layer = ""
            if uv_layer:
                objects = list(self._attribute_objects or ())
                if objects and not all(self._mesh_uv_layer(obj, uv_layer) for obj in objects):
                    self._fail(
                        f"Tangent's UV map '{uv_layer}' is missing from at least one "
                        "contributing mesh. Needs Cycles"
                    )
                tangent = self._named_layer_tangent_to_world(unit_x, uv_layer)
            else:
                tangent = self._emit(
                    {"op": OPCODE_TANGENT_TO_WORLD, "dst": self._alloc(), "fac": int(unit_x)}
                )
        elif direction_type == "RADIAL":
            axis = str(getattr(node, "axis", "Z") or "Z").strip().upper()
            if axis not in {"X", "Y", "Z"}:
                self._fail(f"Tangent axis '{axis}' is not native yet. Needs Cycles")
            generated = self._emit({"op": OPCODE_ATTR_GENERATED, "dst": self._alloc()})
            half = self._emit_swizzle(self._emit_constant((0.5, 0.5, 0.5, 1.0)), "LUMA")
            zero = self._emit_swizzle(self._emit_constant((0.0, 0.0, 0.0, 1.0)), "LUMA")

            def centered(lane: str) -> int:
                return self._emit_math_op("SUBTRACT", self._emit_swizzle(generated, lane), half)

            def negated(lane: str) -> int:
                return self._emit_math_op("SUBTRACT", zero, centered(lane))

            if axis == "X":
                a, b, c = zero, negated("BBB1"), centered("GGG1")
            elif axis == "Y":
                a, b, c = negated("BBB1"), zero, centered("RRR1")
            else:
                a, b, c = negated("GGG1"), centered("RRR1"), zero
            local = self._emit(
                {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                 "a": int(a), "b": int(b), "fac": int(c)}
            )
            # object_normal_transform: OBJECT -> WORLD for a normal-like direction.
            # `clamp` is the direction flag on this op -- True is WORLD -> OBJECT.
            tangent = self._emit(
                {"op": OPCODE_VECTOR_TRANSFORM, "dst": self._alloc(),
                 "src": int(local), "mode": "NORMAL", "clamp": False}
            )
        else:
            self._fail(
                f"Tangent direction '{direction_type}' is not native yet. Needs Cycles"
            )
            raise AssertionError("unreachable")

        shading_normal = self._emit({"op": OPCODE_ATTR_NORMAL, "dst": self._alloc()})
        perpendicular = self._emit_vector_math_op(
            "NORMALIZE", self._emit_vector_math_op("CROSS_PRODUCT", tangent, shading_normal)
        )
        result = self._emit_vector_math_op("CROSS_PRODUCT", shading_normal, perpendicular)
        return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result

    def _named_layer_tangent_to_world(self, tangent_vector: int, layer_name: str) -> int:
        """to_global() against a NAMED UV layer's MikkTSpace frame, then to world.

        `TANGENT_TO_WORLD` carries the frame of the layer the bake projects into, so a
        Normal Map node pointing at a second layer needs its own. MikkTSpace is a
        whole-mesh solve, not a function of the UVs at the shading point, so the frame
        is computed at export (`uv_tangent_per_corner`) and read back through the same
        per-corner sidecar the UV values use: three components of OBJECT-space tangent
        plus the bitangent sign.

        Transcribed from `svm_node_normal_map`, which does all of this in OBJECT space
        and only transforms at the end:

            B = sign * cross(normal, tangent)
            N = safe_normalize(to_global(color, tangent, B, normal))
            object_normal_transform(&N)

        Known deviation: Cycles uses the UNNORMALISED interpolated object normal here,
        whose length weights the z term against x and y. `ATTR_NORMAL` arrives already
        normalised and the original length is not recoverable, so this uses the unit
        normal. The two agree wherever the interpolated normal is near unit length,
        which is everywhere except heavily-smoothed silhouettes.
        """
        components = [
            self._corner_attr_fetch(corner_tangent_channel_tag(layer_name, index))
            for index in range(4)
        ]
        tangent = self._emit(
            {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
             "a": int(components[0]), "b": int(components[1]), "fac": int(components[2])}
        )
        normal = self._object_space_normal()
        sign = components[3]
        sign_vector = self._emit(
            {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
             "a": int(sign), "b": int(sign), "fac": int(sign)}
        )
        bitangent = self._emit_vector_math_op(
            "MULTIPLY",
            self._emit_vector_math_op("CROSS_PRODUCT", normal, tangent),
            sign_vector,
        )

        def broadcast(lane):
            component = self._emit_swizzle(tangent_vector, lane)
            return self._emit(
                {"op": OPCODE_COMBINE_XYZ, "dst": self._alloc(),
                 "a": int(component), "b": int(component), "fac": int(component)}
            )

        accumulated = self._emit_vector_math_op(
            "MULTIPLY", tangent, broadcast("RRR1")
        )
        accumulated = self._emit_vector_math_op(
            "MULTIPLY_ADD", bitangent, broadcast("GGG1"), accumulated
        )
        accumulated = self._emit_vector_math_op(
            "MULTIPLY_ADD", normal, broadcast("BBB1"), accumulated
        )
        # object_normal_transform: OBJECT -> WORLD through the inverse transpose, which
        # is what NORMAL mode is. It normalises, matching Cycles' safe_normalize.
        return self._emit(
            {
                "op": OPCODE_VECTOR_TRANSFORM,
                "dst": self._alloc(),
                "src": int(accumulated),
                "mode": "NORMAL",
                "clamp": False,  # OBJECT -> WORLD
            }
        )

    def _compile_color_ramp(self, node, output=None, *, want: str) -> int:
        # The node has two outputs and they are not interchangeable: Alpha is the
        # ramp's interpolated alpha, never the colour. Dispatching without `output`
        # (as this did until 2026-08-19) made a link from Alpha compile to the
        # colour, LUMA-swizzled for a scalar input — silently wrong, no fallback.
        out_name = str(getattr(output, "name", "") or "").strip().upper()
        wants_alpha = out_name == "ALPHA"
        fac = self.compile_socket(node.inputs.get("Fac"), want="SCALAR")
        ramp = getattr(node, "color_ramp", None)
        interpolation = str(getattr(ramp, "interpolation", "LINEAR") or "LINEAR").upper()
        if interpolation not in SUPPORTED_COLOR_RAMP_MODES:
            self._fail(f"Unsupported Color Ramp interpolation '{interpolation}'")
        color_mode = str(getattr(ramp, "color_mode", "RGB") or "RGB").upper()
        if color_mode not in {"RGB", "HSV", "HSL", ""}:
            self._fail(
                f"Color Ramp colour mode '{color_mode}' is not native yet. Needs Cycles"
            )
        hue_interpolation = str(
            getattr(ramp, "hue_interpolation", "NEAR") or "NEAR"
        ).upper()
        # Blender only blends in HSV/HSL for LINEAR and EASE. CONSTANT returns the
        # left stop's colour outright, and CARDINAL / B_SPLINE run the 4-point
        # curve on RGB and never look at `color_mode`
        # (BKE_colorband_evaluate, blenkernel/intern/colorband.cc). So the other
        # three modes compile exactly as RGB, which is not an approximation --
        # it is what Blender does.
        convert_stops = color_mode in {"HSV", "HSL"} and interpolation in {"LINEAR", "EASE"}
        eval_mode = interpolation
        if convert_stops and interpolation == "EASE":
            # Blender applies the smoothstep only on its RGB path; an EASE ramp in
            # HSV / HSL evaluates exactly like LINEAR (checked against
            # ColorRamp.evaluate and a Cycles bake).
            eval_mode = "LINEAR"
        elements: list[list[float]] = []
        for element in getattr(ramp, "elements", ()) or ():
            try:
                pos = float(getattr(element, "position", 0.0))
                color = getattr(element, "color", (0.0, 0.0, 0.0, 1.0))
                rgba = [float(color[0]), float(color[1]), float(color[2]), float(color[3])]
            except Exception:
                continue
            elements.append([pos, *rgba])
        elements.sort(key=lambda item: item[0])
        if not elements:
            elements = [[0.0, 0.0, 0.0, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0, 1.0]]
        # The Alpha output never touches the colour, so a colour-space conversion
        # would be pure cost. Both spaces carry alpha through untouched anyway.
        if convert_stops and not wants_alpha:
            elements = _colorband_stops_to_hue_space(
                elements, color_mode, hue_interpolation
            )
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_COLOR_RAMP,
                "dst": dst,
                "src": int(fac),
                "mode": eval_mode,
                "elements": elements,
            }
        )
        if convert_stops and not wants_alpha:
            reg = self._emit_color_space(
                reg, "HSV_TO_RGB" if color_mode == "HSV" else "HSL_TO_RGB"
            )
        if want == "SCALAR":
            return self._emit_swizzle(reg, "A" if wants_alpha else "LUMA")
        if wants_alpha:
            return self._emit_swizzle(reg, "AAA1")
        return reg

    def _compile_curve_map(self, node, *, want: str) -> int:
        """Compile RGB Curves / Vector Curves / Float Curve into a sampled table.

        The table is filled from Blender's own ``CurveMapping.evaluate``, so the
        spline solve, handle types and extrapolation are Blender's rather than a
        reimplementation. Cycles evaluates these nodes from an equally sized
        table, so this is the reference behaviour and not an approximation.

        RGB Curves applies the combined ``C`` curve *before* the per-channel
        curve — verified against a Cycles render, the opposite order is visibly
        wrong.
        """
        ntype = str(getattr(node, "type", "") or "")
        mapping = getattr(node, "mapping", None)
        if mapping is None:
            self._fail(f"{ntype} has no curve mapping")
        try:
            mapping.update()
        except Exception:
            pass
        curves = list(getattr(mapping, "curves", ()) or ())
        if not curves:
            self._fail(f"{ntype} has no curves")

        min_x = float(getattr(mapping, "clip_min_x", 0.0))
        max_x = float(getattr(mapping, "clip_max_x", 1.0))
        if not (max_x > min_x):
            min_x, max_x = 0.0, 1.0

        if ntype == "CURVE_RGB":
            mode = "RGB"
            combined = curves[3] if len(curves) > 3 else None
            channels = [curves[0], curves[1], curves[2]]
        elif ntype == "CURVE_VEC":
            mode = "VECTOR"
            combined = None
            channels = [curves[0], curves[1], curves[2]]
        else:
            mode = "FLOAT"
            combined = None
            channels = [curves[0], curves[0], curves[0]]

        size = CURVE_MAP_TABLE_SIZE
        table: list[list[float]] = []
        span = max_x - min_x
        for index in range(size):
            x = min_x + span * (index / (size - 1))
            base = x
            if combined is not None:
                try:
                    base = float(mapping.evaluate(combined, x))
                except Exception:
                    base = x
            row: list[float] = []
            for curve in channels:
                try:
                    row.append(float(mapping.evaluate(curve, base)))
                except Exception:
                    row.append(base)
            table.append(row)

        src_socket = (
            node.inputs.get("Color")
            or node.inputs.get("Vector")
            or node.inputs.get("Value")
        )
        want_src = "SCALAR" if mode == "FLOAT" else "COLOR"
        if mode == "VECTOR":
            src = self._compile_vector_value(src_socket, fallback=(0.0, 0.0, 0.0))
        else:
            src = self.compile_socket(src_socket, want=want_src)
        fac = self.compile_socket(
            node.inputs.get("Fac") or node.inputs.get("Factor"), want="SCALAR"
        )
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_CURVE_MAP,
                "dst": dst,
                "src": int(src),
                "fac": int(fac),
                "curve_mode": mode,
                "min_x": float(min_x),
                "max_x": float(max_x),
                "table": table,
            }
        )
        if want == "SCALAR" and mode != "FLOAT":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_vector_transform(self, node, *, want: str) -> int:
        """Blender's Vector Transform between World and Object space.

        Camera space is view-dependent and rejected (plan section 7.2). The
        object-to-world matrix is not in the GPU mesh frame, so the shader
        inverts the world-to-object affine it already has rather than growing
        the frame ABI.
        """
        vector_type = str(getattr(node, "vector_type", "VECTOR") or "VECTOR").upper()
        convert_from = str(getattr(node, "convert_from", "WORLD") or "WORLD").upper()
        convert_to = str(getattr(node, "convert_to", "OBJECT") or "OBJECT").upper()
        for space in (convert_from, convert_to):
            if space == "CAMERA":
                self._fail(
                    "Vector Transform camera space is view-dependent and cannot be baked"
                )
            if space not in {"WORLD", "OBJECT"}:
                self._fail(
                    f"Vector Transform space '{space}' is not native yet. Needs Cycles"
                )
        if vector_type not in {"POINT", "VECTOR", "NORMAL"}:
            self._fail(
                f"Vector Transform type '{vector_type}' is not native yet. Needs Cycles"
            )
        src = self._compile_vector_value(
            node.inputs.get("Vector"), fallback=(0.0, 0.0, 0.0)
        )
        if convert_from == convert_to:
            return self._emit_swizzle(src, "LUMA") if want == "SCALAR" else src
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_VECTOR_TRANSFORM,
                "dst": dst,
                "src": int(src),
                "mode": vector_type,
                # WORLD -> OBJECT when true, OBJECT -> WORLD otherwise.
                "clamp": bool(convert_from == "WORLD"),
            }
        )
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    def _compile_vector_rotate(self, node, *, want: str) -> int:
        """Blender's Vector Rotate: center + rotate(vector - center)."""
        mode = str(getattr(node, "rotation_type", "AXIS_ANGLE") or "AXIS_ANGLE").upper()
        if mode not in VECTOR_ROTATE_MODES:
            self._fail(f"Vector Rotate type '{mode}' is not native yet. Needs Cycles")
        vector = self._compile_vector_value(
            node.inputs.get("Vector"), fallback=(0.0, 0.0, 0.0)
        )
        center = self._compile_vector_value(
            node.inputs.get("Center"), fallback=(0.0, 0.0, 0.0)
        )
        axis = self._compile_vector_value(
            node.inputs.get("Axis"), fallback=(0.0, 0.0, 1.0)
        )
        angle = self.compile_socket(node.inputs.get("Angle"), want="SCALAR")
        rotation = self._compile_vector_value(
            node.inputs.get("Rotation"), fallback=(0.0, 0.0, 0.0)
        )
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_VECTOR_ROTATE,
                "dst": dst,
                "src": int(vector),
                "a": int(center),
                "b": int(axis),
                "fac": int(rotation),
                "scale": int(angle),
                "mode": mode,
                "clamp": bool(getattr(node, "invert", False)),
            }
        )
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    #: The four Raycast outputs v1 implements, by upper-cased socket name, mapped
    #: to (which destination register, which swizzle). `None` = the register
    #: verbatim: dst is float4(hit_position.xyz, is_hit) and dst2 is
    #: float4(hit_normal.xyz, hit_distance), so every output is a pure swizzle of
    #: one of them and no repacking op is ever emitted
    #: (docs/SECONDARY_RAY_NODES_PLAN.md section 12.2).
    _RAYCAST_OUTPUTS: dict[str, tuple[str, str | None]] = {
        "IS HIT": ("dst", "A"),
        "HIT POSITION": ("dst", None),
        "HIT NORMAL": ("dst2", None),
        "HIT DISTANCE": ("dst2", "A"),
    }

    def _compile_raycast(self, node, output, *, want: str) -> int:
        """ShaderNodeRaycast (Blender 5.1+) -> the `RAYCAST` opcode.

        Contract mirrored from docs/SECONDARY_RAY_NODES_PLAN.md section 12.2 (keys
        parsed in backend/src/backend_job_io.cpp, lanes packed in
        backend/src/backend_material_ir_gpu.cpp)::

            {"op": "RAYCAST", "dst": r, "dst2": r | absent,
             "position": r | absent,       # absent = the shading point
             "direction": r | absent,      # absent = the shading normal
             "distance_reg": r | "distance": float,   # the "Length" socket
             "only_local": bool}

        **One op per node, not one per output.** The op traces once and writes two
        registers; every output socket is a swizzle of one of them, so a graph
        reading Is Hit *and* Hit Normal pays a single traversal (section 12.10.3).
        `dst2` is only allocated once an output that needs it is compiled.

        Fidelity rules this compiler must not "help" with:

        * **Never pre-offset Position and never normalise Direction.** Cycles'
          self-intersection skip is a runtime value test,
          ``isequal(position, sd->P)`` -- an epsilon would silently *disable* it and
          look like a self-hit bug. Length is in units of ``|D|`` by design, so
          normalising would redefine the socket (sections 12.4, 12.10.6).
        * **Unlinked sockets are emitted as the sentinel, not as a CONSTANT.** The
          surface position is not constant per texel, and compiling it in would
          also break the equality test above (section 12.10.7).
        * **The socket is named "Length", not "Distance"**, even though the JSON key
          is `distance` for consistency with AO (section 12.10.5).
        """
        # `only_local` is decoded-and-ignored by the backend in v1 (section 12.5),
        # exactly as kMirOpAo's ONLY_LOCAL bit is. Same call as AO's: emit the
        # decoded `false`, but refuse `true` rather than bake a whole-scene trace
        # while the node says "only local". Section 12.5 keeps the object-identity
        # mapping open as question 9.3 for Glow; refusing hands back Cycles'
        # behaviour instead of picking an approximation silently.
        if bool(getattr(node, "only_local", False)):
            self._fail(
                "Raycast 'Only Local' is not implemented natively (the GPU opcode "
                "decodes the flag and traces the whole high-poly TLAS, whose identity "
                "granularity is the name-prefix source group, not a Blender object). "
                "Needs Cycles"
            )

        # Refuse what the backend cannot see (section 12.5). Both live only here:
        # there is nothing in the op for either, so a missed refusal would bake a
        # wrong image with no diagnostic anywhere.
        #
        # Checked over EVERY linked output, not just the one being compiled, and
        # by exclusion rather than by naming the attribute sockets: the attribute
        # chain's socket names are user-defined, so an allow-list of the four v1
        # outputs is the only complete test -- and it stays correct if a future
        # Blender adds a fifth output.
        for socket in getattr(node, "outputs", ()) or ():
            if not bool(getattr(socket, "is_linked", False)):
                continue
            name = str(getattr(socket, "name", "") or "").strip().upper()
            if name in self._RAYCAST_OUTPUTS:
                continue
            if name in {"IS SELF HIT", "SELF HIT"}:
                self._fail(
                    "Raycast 'Is Self Hit' is Blender-object identity, which does not "
                    "survive the fused high-poly TLAS (the baker's granularity is the "
                    "name-prefix source group). Needs Cycles"
                )
            self._fail(
                f"Raycast output '{getattr(socket, 'name', '')}' is an attribute "
                "lookup against the hit surface, which the baker has no hit-side "
                "attribute plumbing for. Needs Cycles"
            )

        out_name = str(getattr(output, "name", "") or "")
        target = self._RAYCAST_OUTPUTS.get(out_name.strip().upper())
        if target is None:
            self._fail(
                f"Raycast output '{out_name}' is not implemented natively. Needs Cycles"
            )
        register_key, swizzle = target

        reg = self._compile_raycast_trace(node, needs_dst2=(register_key == "dst2"))[
            register_key
        ]
        if swizzle is not None:
            # Is Hit / Hit Distance ride the .w lane; the swizzle replicates them,
            # so the result reads correctly as either a scalar or a colour.
            return self._emit_swizzle(reg, swizzle)
        # Hit Position / Hit Normal are the register's .xyz. Returned verbatim --
        # the plan calls for a pure swizzle and the IR has no "xyz, w=1" mode, so
        # the .w lane still carries is_hit / hit_distance. Every vector consumer
        # (VECTOR_MATH, the tangent encode's DOT_PRODUCTs, luminance) reads .xyz
        # only; an alpha-reading consumer would see that companion scalar.
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    def _compile_raycast_trace(self, node, *, needs_dst2: bool) -> dict[str, int]:
        """Emit (or extend) the single `RAYCAST` op backing all of a node's outputs.

        Returns ``{"dst": r, "dst2": r}``. `dst2` is allocated lazily: a graph that
        only asks "did I hit, and where" burns one register, not two (section 12.2).
        Because the op dict is the same object already appended to ``self.ops``,
        adding `dst2` later mutates the emitted op in place -- register allocation
        does not run until the whole program is compiled, so this is safe.
        """
        cache = getattr(self, "_raycast_op_cache", None)
        if cache is None:
            cache = {}
            self._raycast_op_cache = cache
        key = (_node_cache_id(node), getattr(self, "_coord_offset", None))
        op = cache.get(key)

        if op is None:
            op = {"op": OPCODE_RAYCAST, "only_local": False}

            position_socket = node.inputs.get("Position")
            if position_socket is not None and bool(
                getattr(position_socket, "is_linked", False)
            ):
                op["position"] = int(self.compile_socket(position_socket, want="COLOR"))
            direction_socket = node.inputs.get("Direction")
            if direction_socket is not None and bool(
                getattr(direction_socket, "is_linked", False)
            ):
                op["direction"] = int(
                    self.compile_socket(direction_socket, want="COLOR")
                )

            length_socket = node.inputs.get("Length")
            if length_socket is not None and bool(
                getattr(length_socket, "is_linked", False)
            ):
                op["distance_reg"] = int(self.compile_socket(length_socket, want="SCALAR"))
            else:
                try:
                    op["distance"] = float(
                        getattr(length_socket, "default_value", 1.0)
                    )
                except (TypeError, ValueError):
                    op["distance"] = 1.0

            op["dst"] = self._alloc()
            self._emit(op)
            cache[key] = op

        if needs_dst2 and "dst2" not in op:
            op["dst2"] = self._alloc()
        return {"dst": int(op["dst"]), "dst2": int(op.get("dst2", op["dst"]))}

    def _compile_bevel(self, node, *, want: str) -> int:
        """ShaderNodeBevel -> the `BEVEL` secondary-ray opcode.

        Contract mirrored from docs/SECONDARY_RAY_NODES_PLAN.md section 11.2 (keys
        parsed in backend/src/backend_job_io.cpp, lanes packed in
        backend/src/backend_material_ir_gpu.cpp)::

            {"op": "BEVEL", "dst": r,
             "radius_reg": r | "radius": float,   # register when linked, else constant
             "normal": r | absent,                # absent = Normal socket unlinked
             "samples": int}

        The result register holds a **world-space unit normal** -- the same
        convention `ATTR_NORMAL` / `ATTR_TRUE_NORMAL` / `TANGENT_TO_WORLD` produce.
        It is not tangent space and not 0..1 encoded; any encode a NORMAL-channel
        output needs happens downstream, exactly as it already does for a Normal Map
        node (section 11.10.4).

        Two things this compiler deliberately does NOT do:

        * **No delta preserve.** Cycles' `Normal` input is
          ``normalize(ref_N + (bevel_N - sd->N))``, not a replace. That needs
          ``sd->N``, which only the interpreter has, so the register is passed
          through untouched and the interpreter composes it (section 11.10.5).
        * **No linked-Radius refusal.** Unlike AO's Distance -- where a runtime
          ``<= 0`` means scene-infinite on GPU but fully-unoccluded in Cycles -- the
          GPU early-out for ``radius <= 0`` *is* Cycles' own (``bevel.h:112``), so a
          runtime radius behaves identically on both engines. Section 11.10.6 states
          this explicitly, and `mir_bevel_node` was read to confirm it: the
          ``!(radius > 0.0)`` guard returns the shading normal and the delta preserve
          still runs, matching Cycles. A linked Radius is therefore safe to emit.
        """
        radius_socket = node.inputs.get("Radius")
        normal_socket = node.inputs.get("Normal")
        radius_linked = radius_socket is not None and bool(
            getattr(radius_socket, "is_linked", False)
        )
        normal_linked = normal_socket is not None and bool(
            getattr(normal_socket, "is_linked", False)
        )

        if not radius_linked:
            try:
                radius = float(getattr(radius_socket, "default_value", 0.05))
            except (TypeError, ValueError):
                radius = 0.05
            if not (radius > 0.0):
                # bevel.h:112 `if (radius <= 0.0f) return sd->N;`. Nothing is traced,
                # so emitting the opcode would put the program on the ray route --
                # and consume ray budget -- for a node that cannot bevel anything.
                #
                # The fold is NOT unconditionally "the shading normal": Cycles' delta
                # preserve sits outside svm_bevel and still runs after the early-out,
                # collapsing to normalize(ref_N) when Normal is linked (section 11.3,
                # and the `bevel_normal_reg != 0xFFFFFFFF` block in material_ir.slang
                # runs on the early-out path too). So:
                #   Normal unlinked -> the shading normal, byte-for-byte the register
                #                      the Geometry > Normal path emits
                #   Normal linked   -> normalize(ref_N)
                # Known degenerate gap: for a ref_N of exactly (0,0,0) the interpreter
                # falls back to the shading normal while this fold yields (0,0,0).
                # That needs a Normal socket driven to an exact zero vector, which is
                # already a degenerate graph; reproducing the guard would cost a
                # length-compare and a select for no reachable benefit.
                if normal_linked:
                    result = self._emit_vector_math_op(
                        "NORMALIZE", self.compile_socket(normal_socket, want="COLOR")
                    )
                else:
                    result = self._emit_attr(OPCODE_ATTR_NORMAL)
                return self._emit_swizzle(result, "LUMA") if want == "SCALAR" else result

        op: dict[str, Any] = {
            "op": OPCODE_BEVEL,
            # `samples` is a node PROPERTY on ShaderNodeBevel, never a socket, so it
            # is never a register. Blender's default is 4. Clamped to the same
            # backend window AO uses; see RAY_NODE_MAX_SAMPLES.
            "samples": max(
                RAY_NODE_MIN_SAMPLES,
                min(RAY_NODE_MAX_SAMPLES, _int_or(getattr(node, "samples", 4), 4)),
            ),
        }
        if radius_linked:
            # Scalar register; the interpreter scalarises it through mir_luma.
            op["radius_reg"] = int(self.compile_socket(radius_socket, want="SCALAR"))
        else:
            op["radius"] = float(radius)
        if normal_linked:
            # Omitting the key is the "socket unlinked" sentinel (-1 host-side),
            # which tells the interpreter to skip the delta preserve entirely.
            op["normal"] = int(self.compile_socket(normal_socket, want="COLOR"))

        op["dst"] = self._alloc()
        reg = self._emit(op)
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    def _fold_constant_scalar(self, reg: int):
        """The scalar a register holds when only CONSTANT and SWIZZLE ops feed it, else None.

        Registers are still SSA here (compaction runs at finalize), so a register's
        defining op is unique. The answer is the register's luminance, the same
        scalar a SCALAR consumer reads.
        """
        defs = {int(op.get("dst", -1)): op for op in self.ops}

        def value(r: int, depth: int = 0):
            op = defs.get(int(r))
            if op is None or depth > 8:
                return None
            kind = op.get("op")
            if kind == OPCODE_CONSTANT:
                rgba = op.get("value") or ()
                if len(rgba) != 4:
                    return None
                return tuple(float(v) for v in rgba)
            if kind == OPCODE_SWIZZLE:
                src = value(int(op.get("src", -1)), depth + 1)
                if src is None:
                    return None
                mode = str(op.get("mode") or "").upper()
                if mode == "LUMA":
                    lum = _luminance(src)
                    return (lum, lum, lum, 1.0)
                lane = {"RRR1": 0, "GGG1": 1, "BBB1": 2, "A": 3, "AAA1": 3}.get(mode)
                if lane is None:
                    return None
                return (src[lane], src[lane], src[lane], 1.0)
            return None

        rgba = value(reg)
        return None if rgba is None else _luminance(rgba)

    def _compile_ambient_occlusion(self, node, output, *, want: str) -> int:
        """ShaderNodeAmbientOcclusion -> the `AO` secondary-ray opcode.

        Contract mirrored from docs/SECONDARY_RAY_NODES_PLAN.md section 10.2 (backend
        keys parsed in backend/src/backend_job_io.cpp, lanes packed in
        backend/src/backend_material_ir_gpu.cpp)::

            {"op": "AO", "dst": r,
             "normal": r | absent,          # absent = shading normal
             "distance_reg": r | absent,    # absent = the "distance" constant
             "distance": float, "samples": int, "inside": bool, "only_local": bool}

        The opcode returns only the scalar estimate, replicated as float4(ao, ao,
        ao, 1). The node's two outputs are therefore:

        * ``AO``    -> that register verbatim
        * ``Color`` -> ``Color-input * AO``, a compiler-side vector multiply

        Correctness-first refusals (Cycles is the reference; a slower correct bake
        beats a fast wrong one):

        * ``Only Local`` -- the v1 GPU estimator decodes the bit and then traces the
          whole scene (plan section 10.4 item 3), because the baker's identity granularity is
          ``source_name_index``, not a Blender object. Refuse rather than silently
          bake a different image on multi-object scenes.
        * a **linked** ``Distance`` -- the GPU treats a runtime ``distance <= 0`` as
          scene-infinite reach while Cycles returns exactly 1.0 there (plan section 10.4
          item 2). The compiler cannot inspect a runtime value, so it cannot promise
          parity.
        * a **constant** ``Distance <= 0`` needs no opcode at all: Cycles' early-out
          returns 1.0, so the whole node folds away (see below). Negative values take
          Cycles' global-radius branch, which the baker does not model either -- fold
          them the same way and never trace.
        """
        out_name = str(getattr(output, "name", "") or "")
        color_socket = node.inputs.get("Color")

        if bool(getattr(node, "only_local", False)):
            self._fail(
                "Ambient Occlusion 'Only Local' is not implemented natively "
                "(the GPU AO opcode ignores the flag and traces the whole scene, "
                "which differs from Cycles on multi-object scenes). Needs Cycles"
            )

        distance_socket = node.inputs.get("Distance")
        distance = None
        if distance_socket is not None and bool(getattr(distance_socket, "is_linked", False)):
            # A link that resolves to a bake-time constant (an Attribute node reading
            # a scene or object property, a Value node, a Group Input fed by one) has
            # no runtime value to check, so it takes the constant path below. Anything
            # that varies per hit stays refused.
            linked = self.compile_socket(distance_socket, want="SCALAR")
            folded = self._fold_constant_scalar(linked)
            if folded is None:
                self._fail(
                    "Ambient Occlusion 'Distance' is linked. A runtime Distance <= 0 is "
                    "scene-infinite on GPU but fully unoccluded in Cycles, and the compiler "
                    "cannot check a runtime value. Needs Cycles"
                )
            distance = folded
        if distance is None:
            try:
                distance = float(getattr(distance_socket, "default_value", 1.0))
            except (TypeError, ValueError):
                distance = 1.0

        if distance == 0.0:
            # Cycles 5.2 bakes AO 0.0 for a Distance of exactly 0 on a lone plane and
            # on one under a dome, but 1.0 on a plane with a second plane 0.02 below
            # it (measured, tests/test_ov_ir_cycles_oracle.py and the real-GPU run). It
            # depends on the scene, so no constant is right: leave it to Cycles.
            self._fail(
                "Ambient Occlusion 'Distance' of exactly 0 bakes differently by scene in "
                "Cycles and has no single native value. Needs Cycles"
            )
        if not (distance > 0.0):
            # A negative Distance bakes AO 1.0 in every scene measured (open plane,
            # under a dome, beside a second plane). No ray is traced, so it folds.
            # Folding to an opcode would be wrong: its GPU meaning at <= 0 is
            # unbounded reach.
            if out_name == "Color":
                return self.compile_socket(color_socket, want=want)
            unoccluded = self._emit_constant((1.0, 1.0, 1.0, 1.0))
            if want == "SCALAR":
                return self._emit_swizzle(unoccluded, "LUMA")
            return unoccluded

        ao_reg = self._compile_ambient_occlusion_estimator(node, distance)

        if out_name == "Color":
            # Cycles' svm_node_ao: `Color = ao * color_input`. The opcode has one
            # destination register, so the multiply is composed here.
            result = self._emit_vector_math_op(
                "MULTIPLY",
                self.compile_socket(color_socket, want="COLOR"),
                ao_reg,
            )
            if want == "SCALAR":
                return self._emit_swizzle(result, "LUMA")
            return result

        # The AO output is already float4(ao, ao, ao, 1); LUMA of a replicated
        # scalar is the same scalar, so a SCALAR consumer can read it directly.
        return ao_reg

    def _compile_ambient_occlusion_estimator(self, node, distance: float) -> int:
        """Emit (or reuse) the one `AO` op backing both of the node's outputs.

        Every sample is a full TLAS traversal, so a node whose AO *and* Color
        outputs are both consumed must not pay for the estimate twice.
        """
        cache = getattr(self, "_ao_estimator_cache", None)
        if cache is None:
            cache = {}
            self._ao_estimator_cache = cache
        key = (_node_cache_id(node), getattr(self, "_coord_offset", None))
        cached = cache.get(key)
        if cached is not None:
            return cached

        op: dict[str, Any] = {
            "op": OPCODE_AO,
            "distance": float(distance),
            # Clamped to the backend's [1, 128] window. Above the cap only the
            # variance changes, never the estimator's expectation, and the GPU
            # sequence already differs from Cycles' path_branched_rng_2D — so
            # clamping cannot move the converged value (plan section 10.4 items 4 and 5).
            "samples": max(
                RAY_NODE_MIN_SAMPLES,
                min(RAY_NODE_MAX_SAMPLES, _int_or(getattr(node, "samples", 16), 16)),
            ),
            "inside": bool(getattr(node, "inside", False)),
            # Always False: only_local=True was refused above.
            "only_local": False,
        }

        normal_socket = node.inputs.get("Normal")
        if normal_socket is not None and bool(getattr(normal_socket, "is_linked", False)):
            # Cycles: safe_normalize(stack_load_float3_default(normal_offset, sd->N)).
            # Omitting the key is the "use the shading normal" sentinel (-1 host-side).
            op["normal"] = int(self.compile_socket(normal_socket, want="COLOR"))

        op["dst"] = self._alloc()
        reg = self._emit(op)
        cache[key] = reg
        return reg

    def _compile_normal_node(self, node, output, *, want: str) -> int:
        """Normal node: a constant direction plus its dot with the input."""
        try:
            direction = [float(v) for v in node.outputs["Normal"].default_value]
        except Exception:
            direction = [0.0, 0.0, 1.0]
        length = math.sqrt(sum(v * v for v in direction)) or 1.0
        unit = tuple(v / length for v in direction)
        normal_reg = self._emit_constant((unit[0], unit[1], unit[2], 1.0))
        if str(getattr(output, "name", "") or "") != "Dot":
            return self._emit_swizzle(normal_reg, "LUMA") if want == "SCALAR" else normal_reg
        incoming = self._compile_vector_value(
            node.inputs.get("Normal"), fallback=(0.0, 0.0, 0.0)
        )
        one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
        zero = self._emit_constant((0.0, 0.0, 0.0, 1.0))
        # Blender normalizes the incoming vector before the dot.
        unit_in = self._emit(
            {
                "op": OPCODE_VECTOR_MATH,
                "dst": self._alloc(),
                "math_op": "NORMALIZE",
                "a": int(incoming),
                "b": int(zero),
                "fac": int(zero),
                "scale": int(one),
            }
        )
        dst = self._alloc()
        return self._emit(
            {
                "op": OPCODE_VECTOR_MATH,
                "dst": dst,
                "math_op": "DOT_PRODUCT",
                "a": int(unit_in),
                "b": int(normal_reg),
                "fac": int(zero),
                "scale": int(one),
            }
        )

    def _compile_geometry(self, node, output, *, want: str) -> int:
        """Geometry node outputs that the projection hit already carries.

        Incoming is rejected as view-dependent (plan section 7.2). The rest are
        rejected rather than approximated:

        - True Normal, Tangent, Pointiness: the hit record carries no geometric
          normal, tangent frame or curvature, and substituting the shading
          normal for the geometric one is wrong on any smooth-shaded high-poly.
        - Tangent: REFUTED (measured 2026-08-11). TANGENT_TO_WORLD((1,0,0)) recovers
          the baker's MikkTSpace UV tangent, which is NOT what Cycles emits here: on
          the curved fixture Fyr read a near-constant +X (mean 0.985, 0.500, 0.500
          encoded) while Cycles varied widely about zero (mean 0.498, 0.500, 0.499
          with minima near 0). Mean difference 0.551 -- not a sign or basis slip, a
          different quantity. Cycles' default tangent is radial when no explicit
          tangent is set, not the UV tangent. Do not re-apply without a measurement.
        - Random Per Island: no per-object island seed in the shading context.
        - Parametric: Cycles emits the triangle's (u, v, 0); the hit carries a
          three-component barycentric whose component order has not been
          established against Cycles'. A measured Fyr-vs-Cycles bake differed
          by 0.165 mean, so they do not line up as-is.
        """
        out_name = str(getattr(output, "name", "") or "")
        if out_name == "Position":
            reg = self._emit_attr(OPCODE_ATTR_POSITION)
        elif out_name == "Normal":
            reg = self._emit_attr(OPCODE_ATTR_NORMAL)
        elif out_name == "Tangent":
            reg = self._radial_z_tangent()
        elif out_name == "Pointiness":
            # Corner sidecar in loop_triangles order, fetched through the packed
            # record's source_triangle_index. The historical residual was the
            # backend's meshopt spatial sort permuting triangles while a stale
            # cache epoch claimed an identity mapping ('empty = identity'); the
            # .srcidx mesh-cache sidecar closed that hole, so the fetch always
            # sees the true export index.
            channel_tag = CORNER_ATTR_POINTINESS
            resource_index = None
            for index, item in enumerate(self.resources):
                if str(item.get("channel") or "") == channel_tag:
                    resource_index = index
                    break
            if resource_index is None:
                resource_index = len(self.resources)
                if resource_index >= _MAX_RESOURCES:
                    self._fail("Material IR resource budget exceeded")
                self.resources.append({"channel": channel_tag, "image": None})
            reg = self._emit(
                {
                    "op": OPCODE_ATTR_CORNER_FLOAT,
                    "dst": self._alloc(),
                    "resource": int(resource_index),
                }
            )
        elif out_name == "Random Per Island":
            channel_tag = CORNER_ATTR_ISLAND_RANDOM
            resource_index = None
            for index, item in enumerate(self.resources):
                if str(item.get("channel") or "") == channel_tag:
                    resource_index = index
                    break
            if resource_index is None:
                resource_index = len(self.resources)
                if resource_index >= _MAX_RESOURCES:
                    self._fail("Material IR resource budget exceeded")
                self.resources.append({"channel": channel_tag, "image": None})
            reg = self._emit(
                {
                    "op": OPCODE_ATTR_CORNER_FLOAT,
                    "dst": self._alloc(),
                    "resource": int(resource_index),
                }
            )
        elif out_name == "True Normal":
            # Geometric (face) normal of the hit triangle, world space, straight
            # from the packed triangle record. Distinguishable from Normal only on
            # smooth-shaded geometry -- flat shading makes them identical.
            reg = self._emit_attr(OPCODE_ATTR_TRUE_NORMAL)
        elif out_name == "Parametric":
            reg = self._parametric_coordinates()
        elif out_name == "Backfacing":
            # Always 0 in a bake: Cycles shades against the bake ray, so the shading
            # point is never backfacing. Measured through the Cycles route with the
            # high-poly's normals in their normal orientation AND flipped -- both read
            # a flat 0.0 (std 0), and the flipped case is exactly what a careless
            # constant would get wrong.
            reg = self._emit_constant((0.0, 0.0, 0.0, 1.0))
        elif out_name == "Incoming":
            self._fail(
                "Geometry 'Incoming' is view-dependent and cannot be baked"
            )
        else:
            self._fail(
                f"Geometry '{out_name}' is not native yet. Needs Cycles "
                "(supported: Position, Normal, Tangent, Backfacing, True Normal, Parametric, Pointiness, Random Per Island)"
            )
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    def _compile_sampled_color(
        self, node, *, socket_name: str, table, domain, want: str
    ) -> int:
        """Compile a scalar-in / colour-out node from a pre-sampled table.

        Blackbody and Wavelength are one-dimensional and clamp outside their
        domain, so a table captured from Blender reproduces them without
        reimplementing Cycles' fits. See material_ir_tables.
        """
        value = self.compile_socket(node.inputs.get(socket_name), want="SCALAR")
        one = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_CURVE_MAP,
                "dst": dst,
                "src": int(value),
                "fac": int(one),
                "curve_mode": "SCALAR_RGB",
                "min_x": float(domain[0]),
                "max_x": float(domain[1]),
                "clamp": True,
                "table": [list(row) for row in table],
            }
        )
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    def _compile_vector_math(self, node, *, want: str) -> int:
        operation = str(getattr(node, "operation", "") or "ADD").strip().upper()
        if operation not in SUPPORTED_VECTOR_MATH_OPS:
            self._fail(f"Unsupported Vector Math operation '{operation}'. Needs Cycles")
        if operation == "CROSS":
            operation = "CROSS_PRODUCT"
        if operation == "DOT":
            operation = "DOT_PRODUCT"
        inputs = list(getattr(node, "inputs", ()) or ())
        vector = self._compile_vector_value(inputs[0] if inputs else None, fallback=(0.0, 0.0, 0.0))
        zero_vec = self._emit_constant((0.0, 0.0, 0.0, 1.0))
        unit_scale = self._emit_swizzle(self._emit_constant((1.0, 1.0, 1.0, 1.0)), "LUMA")
        if operation in VECTOR_MATH_UNARY_OPS:
            b = zero_vec
            scale = unit_scale
            c = zero_vec
        elif operation in VECTOR_MATH_SCALAR_SECOND_OPS:
            # Second socket is Scale (float), not a vector.
            b = zero_vec
            scale_socket = node.inputs.get("Scale") or (inputs[1] if len(inputs) > 1 else None)
            scale = self.compile_socket(scale_socket, want="SCALAR")
            c = zero_vec
        else:
            b = self._compile_vector_value(
                inputs[1] if len(inputs) > 1 else None, fallback=(0.0, 0.0, 0.0)
            )
            if operation == "REFRACT":
                # Refract takes its IOR from the shared "Scale" socket (input index 3).
                scale = self.compile_socket(node.inputs.get("Scale"), want="SCALAR")
                c = zero_vec
            else:
                scale = unit_scale
                # MULTIPLY_ADD / FACEFORWARD / WRAP read a third vector.
                c = (
                    self._compile_vector_value(inputs[2], fallback=(0.0, 0.0, 0.0))
                    if operation in VECTOR_MATH_TERNARY_OPS and len(inputs) > 2
                    else zero_vec
                )
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_VECTOR_MATH,
                "dst": dst,
                "math_op": operation,
                "a": int(vector),
                "b": int(b),
                "fac": int(c),
                "scale": int(scale),
            }
        )
        if want == "SCALAR" and operation not in {"LENGTH", "DOT_PRODUCT", "DISTANCE"}:
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_map_range(self, node, *, want: str) -> int:
        data_type = str(getattr(node, "data_type", "") or "FLOAT").upper()
        if data_type not in {"FLOAT", "VALUE", "", "FLOAT_VECTOR"}:
            self._fail(f"Map Range data type '{data_type}' is not native yet. Needs Cycles")
        interpolation = str(getattr(node, "interpolation_type", "") or "LINEAR").strip().upper()
        if interpolation not in {"LINEAR", "STEPPED", "SMOOTHSTEP", "SMOOTHERSTEP"}:
            self._fail(f"Map Range interpolation '{interpolation}' is not native yet. Needs Cycles")
        if data_type == "FLOAT_VECTOR":
            return self._compile_map_range_vector(node, interpolation, want=want)
        value = self.compile_socket(
            node.inputs.get("Value") or (node.inputs[0] if node.inputs else None),
            want="SCALAR",
        )
        from_min = self.compile_socket(node.inputs.get("From Min"), want="SCALAR")
        from_max = self.compile_socket(node.inputs.get("From Max"), want="SCALAR")
        to_min = self.compile_socket(node.inputs.get("To Min"), want="SCALAR")
        to_max = self.compile_socket(node.inputs.get("To Max"), want="SCALAR")
        steps = self.compile_socket(node.inputs.get("Steps"), want="SCALAR")
        clamp = bool(getattr(node, "clamp", True))
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_MAP_RANGE,
                "dst": dst,
                "src": int(value),
                "a": int(from_min),
                "b": int(from_max),
                "fac": int(to_min),
                "detail": int(to_max),
                "steps": int(steps),
                "mode": interpolation,
                "clamp": bool(clamp),
            }
        )
        return reg

    def _compile_map_range_vector(self, node, interpolation: str, *, want: str) -> int:
        """Map Range in vector mode: the float remap applied to each lane on its own.

        Cycles' map_range_vector runs the scalar function per component, with the
        node's single Clamp and Interpolation, and per-component From/To/Steps
        sockets, so this is three scalar MAP_RANGE ops packed back into a vector.
        """

        def lane_of(identifier: str, lane: int) -> int:
            # The vector sockets share display names with the float ones ("From Min"),
            # so only the identifier tells them apart; Blender's collection lookup
            # matches names alone.
            socket = next(
                (
                    candidate
                    for candidate in node.inputs
                    if getattr(candidate, "identifier", None) == identifier
                ),
                None,
            )
            if socket is None:
                self._fail(f"Map Range vector socket '{identifier}' is missing. Needs Cycles")
            vec = self.compile_socket(socket, want="COLOR")
            return self._emit_swizzle(vec, self._SCALAR_LANE_MODES[lane])

        clamp = bool(getattr(node, "clamp", True))
        lanes = []
        for lane in range(3):
            lanes.append(
                self._emit(
                    {
                        "op": OPCODE_MAP_RANGE,
                        "dst": self._alloc(),
                        "src": lane_of("Vector", lane),
                        "a": lane_of("From_Min_FLOAT3", lane),
                        "b": lane_of("From_Max_FLOAT3", lane),
                        "fac": lane_of("To_Min_FLOAT3", lane),
                        "detail": lane_of("To_Max_FLOAT3", lane),
                        "steps": lane_of("Steps_FLOAT3", lane),
                        "mode": interpolation,
                        "clamp": clamp,
                    }
                )
            )
        reg = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": self._alloc(),
                "a": int(lanes[0]),
                "b": int(lanes[1]),
                "fac": int(lanes[2]),
            }
        )
        return self._emit_swizzle(reg, "LUMA") if want == "SCALAR" else reg

    def _compile_clamp(self, node, *, want: str) -> int:
        value = self.compile_socket(
            node.inputs.get("Value") or (node.inputs[0] if node.inputs else None),
            want="SCALAR",
        )
        min_v = self.compile_socket(node.inputs.get("Min"), want="SCALAR")
        max_v = self.compile_socket(node.inputs.get("Max"), want="SCALAR")
        # `clamp_type` was never read, and the CLAMP op implements Range semantics
        # (clamp into the sorted interval). Cycles' Min Max is the literal
        # min(max(v, min), max), which differs the moment Min > Max -- it collapses
        # to Max where Range passes the value through. Measured: value 0.3, min 0.8,
        # max 0.2 baked 0.302 natively against Cycles' 0.200. The two agree for every
        # ordinary Min < Max, so nothing else moves.
        clamp_type = str(getattr(node, "clamp_type", "MINMAX") or "MINMAX").strip().upper()
        if clamp_type == "MINMAX":
            return self._emit_math_op(
                "MINIMUM", self._emit_math_op("MAXIMUM", value, min_v), max_v
            )
        dst = self._alloc()
        return self._emit(
            {
                "op": OPCODE_CLAMP,
                "dst": dst,
                "src": int(value),
                "a": int(min_v),
                "b": int(max_v),
            }
        )

    def _compile_combine_xyz(self, node, *, want: str) -> int:
        x = self.compile_socket(node.inputs.get("X") or (node.inputs[0] if node.inputs else None), want="SCALAR")
        y = self.compile_socket(
            node.inputs.get("Y") or (node.inputs[1] if len(node.inputs) > 1 else None),
            want="SCALAR",
        )
        z = self.compile_socket(
            node.inputs.get("Z") or (node.inputs[2] if len(node.inputs) > 2 else None),
            want="SCALAR",
        )
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": dst,
                "a": int(x),
                "b": int(y),
                "fac": int(z),
            }
        )
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_combine_color(self, node, *, want: str) -> int:
        mode = str(getattr(node, "mode", "") or "RGB").strip().upper()
        if mode not in {"RGB", "HSV", "HSL", ""}:
            self._fail(
                f"Combine Color mode '{mode}' is not native yet. Needs Cycles "
                "(supported: RGB, HSV, HSL)"
            )
        r = self.compile_socket(
            node.inputs.get("Red") or node.inputs.get("R") or (node.inputs[0] if node.inputs else None),
            want="SCALAR",
        )
        g = self.compile_socket(
            node.inputs.get("Green") or node.inputs.get("G") or (node.inputs[1] if len(node.inputs) > 1 else None),
            want="SCALAR",
        )
        b = self.compile_socket(
            node.inputs.get("Blue") or node.inputs.get("B") or (node.inputs[2] if len(node.inputs) > 2 else None),
            want="SCALAR",
        )
        dst = self._alloc()
        # RGB combine is identical to Combine XYZ packing; HSV and HSL pack the
        # same way and then convert the triple back to RGB.
        reg = self._emit(
            {
                "op": OPCODE_COMBINE_XYZ,
                "dst": dst,
                "a": int(r),
                "b": int(g),
                "fac": int(b),
            }
        )
        if mode == "HSV":
            reg = self._emit_color_space(reg, "HSV_TO_RGB")
        elif mode == "HSL":
            reg = self._emit_color_space(reg, "HSL_TO_RGB")
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_hue_sat(self, node, *, want: str) -> int:
        color = self.compile_socket(node.inputs.get("Color"), want="COLOR")
        hue = self.compile_socket(node.inputs.get("Hue"), want="SCALAR")
        sat = self.compile_socket(node.inputs.get("Saturation"), want="SCALAR")
        value = self.compile_socket(node.inputs.get("Value"), want="SCALAR")
        fac = self.compile_socket(node.inputs.get("Fac") or node.inputs.get("Factor"), want="SCALAR")
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_HUE_SAT,
                "dst": dst,
                "src": int(color),
                "a": int(hue),
                "b": int(sat),
                "detail": int(value),
                "fac": int(fac),
            }
        )
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_bright_contrast(self, node, *, want: str) -> int:
        color = self.compile_socket(node.inputs.get("Color"), want="COLOR")
        bright = self.compile_socket(
            node.inputs.get("Bright") or node.inputs.get("Brightness"),
            want="SCALAR",
        )
        contrast = self.compile_socket(node.inputs.get("Contrast"), want="SCALAR")
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_BRIGHTCONTRAST,
                "dst": dst,
                "src": int(color),
                "a": int(bright),
                "b": int(contrast),
            }
        )
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg

    def _compile_gamma(self, node, *, want: str) -> int:
        color = self.compile_socket(node.inputs.get("Color"), want="COLOR")
        gamma = self.compile_socket(node.inputs.get("Gamma"), want="SCALAR")
        dst = self._alloc()
        reg = self._emit(
            {
                "op": OPCODE_GAMMA,
                "dst": dst,
                "src": int(color),
                "a": int(gamma),
            }
        )
        if want == "SCALAR":
            return self._emit_swizzle(reg, "LUMA")
        return reg


#: Op fields that hold a register index and are *read* by the op. Mirrors the
#: register-index fields parsed in backend_job_io.cpp. Deliberately excludes
#: `resource` (a resource table index), `brick_offset_freq` / `brick_squash_freq`
#: (plain integers) and MAPPING's `loc` / `rot` / `scale` (float3 arrays — MAPPING
#: carries its registers in `loc_reg` / `rot_reg` / `scale_reg`).
_OP_REG_READ_FIELDS: tuple[str, ...] = (
    "a",
    "b",
    "fac",
    "src",
    "coord",
    "scale",
    "detail",
    "detail_scale",
    "roughness",
    "distortion",
    "lacunarity",
    # NOISE_TEXTURE fractal variants: register indices for Offset/Gain. Missing
    # from this list, the register compactor left them pointing at pre-compaction
    # indices while every other operand renumbered -- measured as Ridged/Hybrid/
    # Hetero baking with offset=0/gain=0 while the type dispatch itself worked.
    "noise_offset",
    "noise_gain",
    "randomness",
    "smoothness",
    "exponent",
    "phase",
    "steps",
    "w",
    "mortar",
    "mortar_size",
    "mortar_smooth",
    "bias",
    "brick_width",
    "row_height",
    "loc_reg",
    "rot_reg",
    "scale_reg",
    "frequency",
    "anisotropy",
    "orientation_2d",
    "orientation_3d",
    # AO: `normal` and `distance_reg` are register indices when the matching
    # socket is linked and are simply absent otherwise (the backend's -1
    # sentinel). `distance` / `samples` are values, not registers.
    "normal",
    "distance_reg",
    # BEVEL: `radius_reg` likewise; it shares the `normal` key above (the keys
    # are per-op-kind, and only the matching backend encode branch reads them).
    # `radius` / `samples` are values, not registers.
    "radius_reg",
    # RAYCAST: the two vector inputs. It shares `distance_reg` above. Absent
    # means "use the sentinel": Position -> the shading point, Direction -> the
    # shading normal (section 12.10.7). `dst2` is a WRITE, not a read, and lives
    # in _OP_REG_WRITE_FIELDS below.
    "position",
    "direction",
    # SAMPLE_IMAGE on a slot table: the register whose .x holds the material slot
    # (written by ATTR_TRIANGLE_SLOT). Absent on every other SAMPLE_IMAGE.
    "slot",
)

#: Op fields that hold a register index the op *writes*, other than `dst`.
#: RAYCAST is the first op whose result does not fit one register (8 floats), so
#: it declares an explicit second destination rather than an implied `dst + 1` --
#: an implicit write would be invisible to the register-footprint scans on both
#: sides and could clobber at the kMirMaxRegs boundary
#: (docs/SECONDARY_RAY_NODES_PLAN.md section 12.2). These must be treated as
#: definitions by the allocator, never as uses.
_OP_REG_WRITE_FIELDS: tuple[str, ...] = ("dst2",)


def _identity_affine():
    return ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0))


def _transform_point(m, v):
    return tuple(
        m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2] + m[r][3] for r in range(3)
    )


def _transform_direction(m, v):
    return tuple(m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2] for r in range(3))


def _transform_direction_transposed(m, v):
    return tuple(m[0][c] * v[0] + m[1][c] * v[1] + m[2][c] * v[2] for c in range(3))


def _invert_affine(m):
    """Invert a 3x4 affine (rotation/scale/shear plus translation)."""
    a, b, c = m[0][0], m[0][1], m[0][2]
    d, e, f = m[1][0], m[1][1], m[1][2]
    g, h, i = m[2][0], m[2][1], m[2][2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-20:
        return _identity_affine()
    inv = 1.0 / det
    r0 = ((e * i - f * h) * inv, (c * h - b * i) * inv, (b * f - c * e) * inv)
    r1 = ((f * g - d * i) * inv, (a * i - c * g) * inv, (c * d - a * f) * inv)
    r2 = ((d * h - e * g) * inv, (b * g - a * h) * inv, (a * e - b * d) * inv)
    t = (m[0][3], m[1][3], m[2][3])
    return (
        (r0[0], r0[1], r0[2], -(r0[0] * t[0] + r0[1] * t[1] + r0[2] * t[2])),
        (r1[0], r1[1], r1[2], -(r1[0] * t[0] + r1[1] * t[1] + r1[2] * t[2])),
        (r2[0], r2[1], r2[2], -(r2[0] * t[0] + r2[1] * t[1] + r2[2] * t[2])),
    )


def _euler_xyz_matrix(rot) -> tuple[tuple[float, float, float], ...]:
    """Blender's euler_to_transform: R = Rz * Ry * Rx, returned as three rows."""
    cx, sx = math.cos(rot[0]), math.sin(rot[0])
    cy, sy = math.cos(rot[1]), math.sin(rot[1])
    cz, sz = math.cos(rot[2]), math.sin(rot[2])
    return (
        (cy * cz, cz * sx * sy - cx * sz, cx * cz * sy + sx * sz),
        (cy * sz, cx * cz + sx * sy * sz, -cz * sx + cx * sy * sz),
        (-sy, cy * sx, cx * cy),
    )


def _euler_xyz_apply(v, rot, *, transpose: bool = False):
    """Apply the Euler XYZ rotation, or its transpose (Vector Rotate's Invert)."""
    m = _euler_xyz_matrix(rot)
    if transpose:
        return tuple(
            m[0][c] * v[0] + m[1][c] * v[1] + m[2][c] * v[2] for c in range(3)
        )
    return tuple(
        m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2] for r in range(3)
    )


def _rotate_around_axis(p, axis, angle: float):
    """Rodrigues rotation; ``axis`` must already be unit length."""
    c = math.cos(angle)
    s = math.sin(angle)
    t = 1.0 - c
    ax, ay, az = axis
    return (
        ((c + t * ax * ax) * p[0])
        + ((t * ax * ay - az * s) * p[1])
        + ((t * ax * az + ay * s) * p[2]),
        ((t * ax * ay + az * s) * p[0])
        + ((c + t * ay * ay) * p[1])
        + ((t * ay * az - ax * s) * p[2]),
        ((t * ax * az - ay * s) * p[0])
        + ((t * ay * az + ax * s) * p[1])
        + ((c + t * az * az) * p[2]),
    )


def _curve_table_lookup(
    table, min_x: float, max_x: float, x: float, channel: int, clamp: bool = False
) -> float:
    """Sample a curve table.

    Past the ends this extrapolates linearly, matching Cycles'
    ``rgb_ramp_lookup`` with extrapolation on — how Blender's curve nodes behave
    outside their clip range. ``clamp`` holds the endpoint value instead, which
    is what Blackbody and Wavelength do outside their domain.
    """
    size = len(table)
    if size == 0:
        return x
    if size == 1:
        return float(table[0][channel])
    span = max_x - min_x
    t = ((x - min_x) / span) if span != 0.0 else 0.0
    if clamp:
        t = min(max(t, 0.0), 1.0)
    if t < 0.0:
        first = float(table[0][channel])
        slope = float(table[1][channel]) - first
        return first + t * (size - 1) * slope
    if t > 1.0:
        last = float(table[size - 1][channel])
        slope = last - float(table[size - 2][channel])
        return last + (t - 1.0) * (size - 1) * slope
    position = t * (size - 1)
    index = int(position)
    if index >= size - 1:
        return float(table[size - 1][channel])
    frac = position - index
    lo = float(table[index][channel])
    hi = float(table[index + 1][channel])
    return lo + (hi - lo) * frac


def _module_rgb_to_hsv(r: float, g: float, b: float) -> tuple[float, float, float]:
    """intern/cycles/util/color.h, rgb_to_hsv. Module-level twin of the evaluator's."""
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin
    if delta < 1e-8:
        h = 0.0
    elif cmax == r:
        h = ((g - b) / delta) % 6.0
    elif cmax == g:
        h = ((b - r) / delta) + 2.0
    else:
        h = ((r - g) / delta) + 4.0
    h /= 6.0
    if h < 0.0:
        h += 1.0
    s = 0.0 if cmax < 1e-8 else delta / cmax
    return (h, s, cmax)


def _module_rgb_to_hsl(r: float, g: float, b: float) -> tuple[float, float, float]:
    """intern/cycles/util/color.h, rgb_to_hsl."""
    cmax = max(r, g, b)
    cmin = min(r, g, b)
    lightness = min(1.0, (cmax + cmin) / 2.0)
    h = 0.0
    s = 0.0
    if cmax != cmin:
        delta = cmax - cmin
        s = delta / (2.0 - cmax - cmin) if lightness > 0.5 else delta / (cmax + cmin)
        if cmax == r:
            h = (g - b) / delta + (6.0 if g < b else 0.0)
        elif cmax == g:
            h = (b - r) / delta + 2.0
        else:
            h = (r - g) / delta + 4.0
    h /= 6.0
    return (h, s, lightness)


def _colorband_hue_delta(h1: float, h2: float, rule: str) -> float:
    """Signed hue step for one ramp segment, per `colorband_hue_interp`.

    Blender picks one of three forms (blenkernel/intern/colorband.cc):

        mode 0: lerp(h1, h2)
        mode 1: lerp(h1 + 1, h2), then wrap
        mode 2: lerp(h1, h2 + 1), then wrap

    Each is a straight line in hue whose signed length is what this returns. The
    caller accumulates those lengths into an *unwrapped* hue per stop, so a plain
    linear ramp between consecutive stops traces the same path. Mode 1's start
    point is `h1 + 1` rather than `h1`, which shifts that whole segment by exactly
    one full turn -- invisible, because the conversion back to RGB wraps hue.
    """
    # Blender's colorband_hue_interp is called as (h1 = the stop on the RIGHT of the
    # segment, h2 = the stop on the LEFT): its blend factor is 0 at the right stop
    # (see `_colorband_evaluate`). NEAR and FAR are mirror-symmetric, so the swap is
    # invisible for them, but CW and CCW are not: reading the call as left-to-right
    # swapped the two. The path is the same arc walked backwards, hence the negation.
    h1, h2 = h2 - math.floor(h2), h1 - math.floor(h1)
    rule = str(rule or "NEAR").strip().upper()
    return -_colorband_hue_delta_rtl(h1, h2, rule)


def _colorband_hue_delta_rtl(h1: float, h2: float, rule: str) -> float:
    """Blender's mode pick for (h1, h2) as passed to `colorband_hue_interp`."""
    if rule == "FAR":
        if h1 == h2:
            mode = 1
        elif h1 < h2 and (h2 - h1) < 0.5:
            mode = 1
        elif h1 > h2 and (h2 - h1) > -0.5:
            mode = 2
        else:
            mode = 0
    elif rule == "CCW":
        mode = 2 if h1 > h2 else 0
    elif rule == "CW":
        mode = 1 if h1 < h2 else 0
    else:  # NEAR
        if h1 < h2 and (h2 - h1) > 0.5:
            mode = 1
        elif h1 > h2 and (h2 - h1) < -0.5:
            mode = 2
        else:
            mode = 0
    if mode == 1:
        return h2 - h1 - 1.0
    if mode == 2:
        return h2 - h1 + 1.0
    return h2 - h1


def _colorband_stops_to_hue_space(elements, color_mode: str, hue_interpolation: str):
    """Rewrite ramp stops into HSV/HSL with an unwrapped hue channel.

    A Color Ramp in HSV or HSL mode converts both ends of the active segment,
    interpolates hue under a wrap rule, and converts back. The stops are compile-
    time constants and only `Fac` is dynamic, so all of that except the final
    conversion can be folded here: convert each stop once, and replace the hue
    with a running total of the per-segment signed steps. Linear interpolation
    between two consecutive unwrapped hues then follows exactly the arc Blender
    takes, and the `HSV_TO_RGB` / `HSL_TO_RGB` op the caller appends wraps it.

    This is why HSV ramps need no change to the ramp opcode itself -- saturation,
    value/lightness and alpha already interpolate linearly, which is what the
    existing evaluator does to every channel.
    """
    convert = _module_rgb_to_hsv if str(color_mode).upper() == "HSV" else _module_rgb_to_hsl
    converted = []
    for pos, r, g, b, a in elements:
        h, s, v = convert(float(r), float(g), float(b))
        converted.append([float(pos), h, s, v, float(a)])
    if not converted:
        return converted
    unwrapped = [list(converted[0])]
    running = converted[0][1]
    for index in range(1, len(converted)):
        running = running + _colorband_hue_delta(
            converted[index - 1][1], converted[index][1], hue_interpolation
        )
        stop = list(converted[index])
        stop[1] = running
        unwrapped.append(stop)
    return unwrapped


def _colorband_key_weights(t: float, mode: str) -> tuple[float, float, float, float]:
    """Blender's key_curve_position_weights (BKE_key) for the cubic ramp modes."""
    t2 = t * t
    t3 = t2 * t
    if mode == "CARDINAL":
        fc = 0.71
        return (
            -fc * t3 + 2.0 * fc * t2 - fc * t,
            (2.0 - fc) * t3 + (fc - 3.0) * t2 + 1.0,
            (fc - 2.0) * t3 + (3.0 - 2.0 * fc) * t2 + fc * t,
            fc * t3 - fc * t2,
        )
    # B_SPLINE
    return (
        -0.16666666 * t3 + 0.5 * t2 - 0.5 * t + 0.16666666,
        0.5 * t3 - t2 + 0.66666666,
        -0.5 * t3 + 0.5 * t2 + 0.5 * t + 0.16666666,
        0.16666666 * t3,
    )


def _colorband_evaluate(elements, mode: str, x: float) -> tuple[float, float, float, float]:
    """Blender's BKE_colorband_evaluate for RGB ramps.

    ``elements`` are ``[pos, r, g, b, a]`` rows sorted by position. Verified
    against ``ColorRamp.evaluate()`` for all five interpolation modes.

    The segment search runs right-to-left the way Blender's does: ``right`` is
    the first stop past ``x`` and the blend factor is 0 at ``right`` and 1 at
    ``left``. Only LINEAR and EASE clamp below the first stop — the cubic modes
    deliberately extrapolate, which is what produces their overshoot.
    """
    total = len(elements)
    if total == 0:
        return (0.0, 0.0, 0.0, 1.0)

    def rgba(row):
        return (
            float(row[1]),
            float(row[2]),
            float(row[3]),
            float(row[4]) if len(row) > 4 else 1.0,
        )

    if total == 1:
        return rgba(elements[0])
    if x <= float(elements[0][0]) and mode in {"LINEAR", "EASE"}:
        return rgba(elements[0])

    index = total
    for i in range(total):
        if float(elements[i][0]) > x:
            index = i
            break

    if index == total:
        right_pos, right = 1.0, elements[total - 1]
        left_pos, left = float(elements[total - 1][0]), elements[total - 1]
    elif index == 0:
        right_pos, right = float(elements[0][0]), elements[0]
        left_pos, left = 0.0, elements[0]
    else:
        right_pos, right = float(elements[index][0]), elements[index]
        left_pos, left = float(elements[index - 1][0]), elements[index - 1]

    if index == total and left_pos == 1.0:
        return rgba(left)
    if index == 0 and right_pos == 0.0:
        return rgba(right)

    span = left_pos - right_pos
    fac = ((x - right_pos) / span) if span != 0.0 else 0.0

    if mode == "CONSTANT":
        return rgba(left)
    if mode == "EASE":
        f2 = fac * fac
        fac = 3.0 * f2 - 2.0 * f2 * fac
    elif mode in {"CARDINAL", "B_SPLINE"}:
        outer_right = right if index >= total - 1 else elements[index + 1]
        outer_left = left if index < 2 else elements[index - 2]
        fac = min(max(fac, 0.0), 1.0)
        w0, w1, w2, w3 = _colorband_key_weights(fac, mode)
        cr, cl = rgba(right), rgba(left)
        c_or, c_ol = rgba(outer_right), rgba(outer_left)
        # Blender clamps the cubic result; it can overshoot the key range.
        return tuple(
            min(max(w3 * c_ol[c] + w2 * cl[c] + w1 * cr[c] + w0 * c_or[c], 0.0), 1.0)
            for c in range(4)
        )

    inv = 1.0 - fac
    cr, cl = rgba(right), rgba(left)
    return tuple(fac * cl[c] + inv * cr[c] for c in range(4))


def _allocate_registers(
    ops: list[dict[str, Any]], result: int
) -> tuple[int, int]:
    """Compact SSA register indices in place. Returns (register_count, result_reg).

    The GPU interpreter has a fixed 64-entry register file and silently clamps
    out-of-range indices, so an unallocated program above that size evaluates to
    garbage instead of failing. The IR is straight-line with no branches, so a linear
    scan is sufficient.

    Liveness is tracked per DEFINITION, not per virtual register id. For a freshly
    compiled program the two are the same -- the compiler emits one fresh register per
    op and never reuses them. They are NOT the same for a program that has already been
    through here, because this function rewrites registers in place and reuses them, so
    one id is written many times. `_merge_per_material_programs` feeds exactly such
    programs back in. Keying liveness on the id alone leaked a physical register on
    every redefinition (`mapping[virtual]` was overwritten and the old physical never
    freed), degenerating to roughly one physical register per op: 171 registers for a
    merged program whose two halves needed 14 and 6. That failed the 64-register budget
    and dropped multi-material channels to Cycles at about 64 merged ops.
    See MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P5.
    """
    if not ops:
        return max(1, int(result) + 1), int(result)

    # --- Pass 1: number every definition, and resolve which one each read sees. ---
    read_definition: list[dict[str, int]] = [dict() for _ in ops]
    write_definition: list[dict[str, int]] = [dict() for _ in ops]
    current: dict[int, int] = {}
    last_read: dict[int, int] = {}
    counter = 0

    def _define(virtual: int) -> int:
        nonlocal counter
        counter += 1
        current[virtual] = counter
        return counter

    for index, op in enumerate(ops):
        for field in _OP_REG_READ_FIELDS:
            value = op.get(field)
            if type(value) is not int or value < 0:
                continue
            definition = current.get(value)
            if definition is None:
                # Read before any write in this op list: the value comes from outside
                # (a relocated branch program), so give it a definition of its own.
                definition = _define(value)
            read_definition[index][field] = definition
            last_read[definition] = index
        for field in ("dst",) + _OP_REG_WRITE_FIELDS:
            value = op.get(field)
            if type(value) is not int or value < 0:
                continue
            write_definition[index][field] = _define(value)

    # The program's result is whichever definition of `result` is live at the end.
    result_definition = current.get(int(result))

    expiring: list[list[int]] = [[] for _ in ops]
    for definition, index in last_read.items():
        expiring[index].append(definition)

    # --- Pass 2: allocate a physical register per definition. ---
    free: list[int] = []
    next_physical = 0
    physical_of: dict[int, int] = {}
    result_physical = int(result)

    def _acquire() -> int:
        nonlocal next_physical
        if free:
            return free.pop()
        physical = next_physical
        next_physical += 1
        return physical

    for index, op in enumerate(ops):
        # Remap reads before allocating the write so an op cannot recycle a register
        # it is still reading from.
        for field, definition in read_definition[index].items():
            physical = physical_of.get(definition)
            if physical is None:
                physical = _acquire()
                physical_of[definition] = physical
            op[field] = physical
        written: list[int] = []
        for field, definition in write_definition[index].items():
            physical = _acquire()
            physical_of[definition] = physical
            op[field] = physical
            written.append(definition)
            if definition == result_definition:
                result_physical = physical
        # Definitions whose final read was this op become reusable.
        for definition in expiring[index]:
            if definition == result_definition or definition in written:
                continue
            released = physical_of.get(definition)
            if released is not None and released not in free:
                free.append(released)

    return next_physical, result_physical


def _resource_is_table(resource) -> bool:
    """A UDIM tile table or a per-material slot table (compile-time or wire form)."""
    if not isinstance(resource, dict):
        return False
    return bool(resource.get("tiled")) or "tiles" in resource or "slots" in resource


def program_uses_sampler_tables(program=None, *, resources=None, ops=None) -> bool:
    """Whether a program needs the version-2 sampler contract.

    That is: any table resource, any ATTR_TRIANGLE_SLOT fetch, or any SAMPLE_IMAGE
    that carries its own `extension` (sampler-side addressing).
    """
    if program is not None:
        resources = getattr(program, "resources", None) if resources is None else resources
        ops = getattr(program, "ops", None) if ops is None else ops
    if any(_resource_is_table(item) for item in (resources or ())):
        return True
    for op in ops or ():
        if not isinstance(op, dict):
            continue
        opcode = op.get("op")
        if opcode == OPCODE_ATTR_TRIANGLE_SLOT:
            return True
        if opcode == OPCODE_SAMPLE_IMAGE and "extension" in op:
            return True
    return False


def _program_version(resources, ops) -> int:
    if program_uses_sampler_tables(resources=resources, ops=ops):
        return MATERIAL_IR_VERSION_SAMPLER_TABLES
    return MATERIAL_IR_VERSION


def _wire_tile_list(tiles) -> list[dict[str, Any]]:
    """`[{"tile": n, "path": p}, ...]` ascending by tile, from export's tile records."""
    entries: list[dict[str, Any]] = []
    for item in tiles or ():
        if isinstance(item, dict):
            tile, path = item.get("tile"), item.get("path")
        else:
            tile = getattr(item, "udim_tile", None)
            path = getattr(item, "image_path", None)
        if tile is None or not path:
            continue
        entries.append({"tile": int(tile), "path": str(path)})
    entries.sort(key=lambda entry: entry["tile"])
    return entries


def wire_resource(resource: dict[str, Any], path: str = "") -> dict[str, Any]:
    """The backend's view of one resource (BakeMapConfig.material_ir_program_json).

    A plain resource is exactly `{"channel", "path"}`, byte-identical to what every
    program before tables shipped. A UDIM table is `{"channel", "path": "", "tiles"}`
    and a slot table `{"channel", "path": "", "slots"}`, each slot being
    `{"path"}`, `{"tiles"}` or `{}`. `missing` rides along only when set.
    """
    channel = str(resource.get("channel") or "RGBA")
    if "slots" in resource:
        slots: list[dict[str, Any]] = []
        for slot in resource.get("slots") or ():
            slot = slot if isinstance(slot, dict) else {}
            if "tiles" in slot:
                slots.append({"tiles": _wire_tile_list(slot.get("tiles"))})
            elif slot.get("path"):
                slots.append({"path": str(slot.get("path"))})
            else:
                slots.append({})
        wire: dict[str, Any] = {"channel": channel, "path": "", "slots": slots}
    elif resource.get("tiled") or "tiles" in resource:
        wire = {"channel": channel, "path": "", "tiles": _wire_tile_list(resource.get("tiles"))}
    else:
        return {"channel": channel, "path": str(path or "")}
    missing = resource.get("missing")
    if missing is not None:
        wire["missing"] = [float(v) for v in tuple(missing)[:4]]
    return wire


def _finalize_compiled_program(
    *,
    channel: str,
    result: int,
    compiler: "_UvExpressionCompiler",
    allow_ray_ops: bool = False,
    allow_image_sample_kind: bool = True,
) -> MaterialIrProgram:
    """`allow_image_sample_kind=False` keeps the program in its EXPRESSION_UV form.

    The IMAGE_SAMPLE specialisation is a different contract -- the backend reprojects
    a texture rather than running ops -- so it cannot be one arm of a multi-material
    select. The merge suppresses it rather than refusing the whole channel; see
    `compile_group_channel_program` and MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P6.
    """
    opcodes = sorted(compiler._opcodes_used)
    resources = list(compiler.resources)
    ops = list(compiler.ops)
    register_count, result = _allocate_registers(ops, result)

    # Specialize single plain-UV SAMPLE_IMAGE (+ optional swizzle) as IMAGE_SAMPLE.
    # Object/Generated/Mapping force EXPRESSION_UV so the backend runs the interpreter.
    uses_non_uv_coord = any(
        op.get("op") in {OPCODE_ATTR_OBJECT, OPCODE_ATTR_GENERATED, OPCODE_MAPPING}
        for op in ops
    )
    sample_ops = [op for op in ops if op.get("op") == OPCODE_SAMPLE_IMAGE]
    non_sample = [
        op
        for op in ops
        if op.get("op")
        not in {OPCODE_SAMPLE_IMAGE, OPCODE_CONSTANT, OPCODE_SWIZZLE, OPCODE_ATTR_UV}
    ]
    kind = MATERIAL_IR_KIND_EXPRESSION_UV
    image_path = ""
    if (
        allow_image_sample_kind
        # A UDIM table or a sampler-addressed tap is interpreter-only: the
        # IMAGE_SAMPLE contract reprojects one texture and has no tile or slot
        # selection, so such a program must stay EXPRESSION_UV.
        and not program_uses_sampler_tables(resources=resources, ops=ops)
        and not uses_non_uv_coord
        and len(sample_ops) == 1
        and not non_sample
        and len(resources) == 1
    ):
        kind = MATERIAL_IR_KIND_IMAGE_SAMPLE

    # Constants-only (unlinked socket) is a trivial native program.
    if not resources and all(op.get("op") in {OPCODE_CONSTANT, OPCODE_SWIZZLE} for op in ops):
        kind = MATERIAL_IR_KIND_EXPRESSION_UV

    program = MaterialIrProgram(
        version=_program_version(resources, ops),
        kind=kind,
        opcodes=opcodes,
        channel=channel,
        image_path=image_path,
        native=True,
        result_reg=int(result),
        resources=resources,
        ops=ops,
    )
    offending: list[int] = []
    gpu_reason = gpu_support_reason(program, allow_ray_ops=allow_ray_ops, offending=offending)
    if gpu_reason:
        # A per-op refusal (ray-op route gate, blocked opcode, unsupported enum)
        # names the op that tripped it; map that back through the compiler's
        # provenance record so the UI can point at the node that emitted it.
        # Program-level refusals (budgets) leave `offending` empty and stay
        # unattributed, which is correct: no single node owns them.
        op_nodes = getattr(compiler, "_op_nodes", None) or []
        refusal = None
        if offending and 0 <= offending[0] < len(op_nodes):
            node_name, node_type, node_path = op_nodes[offending[0]]
            if node_name:
                refusal = MaterialIrRefusal(
                    gpu_reason,
                    node_name=node_name,
                    node_type=node_type,
                    node_path=node_path,
                    channel=channel,
                )
        return _cycles_program(
            channel,
            f"{gpu_reason}. Needs Cycles until GPU native parity lands",
            refusal,
        )
    return program


_HASH_MASK = 0xFFFFFFFF


def _hash_rot(x: int, k: int) -> int:
    return ((x << k) | (x >> (32 - k))) & _HASH_MASK


def _hash_uint2(kx: int, ky: int) -> int:
    """Cycles' hash_uint2 (util/hash.h), the lookup3 final() mix."""
    a = b = c = (0xDEADBEEF + (2 << 2) + 13) & _HASH_MASK
    b = (b + ky) & _HASH_MASK
    a = (a + kx) & _HASH_MASK
    c = (c ^ b) & _HASH_MASK; c = (c - _hash_rot(b, 14)) & _HASH_MASK
    a = (a ^ c) & _HASH_MASK; a = (a - _hash_rot(c, 11)) & _HASH_MASK
    b = (b ^ a) & _HASH_MASK; b = (b - _hash_rot(a, 25)) & _HASH_MASK
    c = (c ^ b) & _HASH_MASK; c = (c - _hash_rot(b, 16)) & _HASH_MASK
    a = (a ^ c) & _HASH_MASK; a = (a - _hash_rot(c, 4)) & _HASH_MASK
    b = (b ^ a) & _HASH_MASK; b = (b - _hash_rot(a, 14)) & _HASH_MASK
    c = (c ^ b) & _HASH_MASK; c = (c - _hash_rot(b, 24)) & _HASH_MASK
    return c


def object_random_number(name: str) -> float:
    """Cycles' Object Info > Random for an object of this name.

    Captured, not assumed: baked through the Cycles route on two different object
    names and matched to 6.4e-7 and 4.3e-6, both at the bake's own quantization
    floor. Cycles seeds a non-instanced object's random_id from the object NAME,
    so renaming an object changes this value -- which the second capture confirms.
    """
    accumulated = 0
    for byte in str(name or "").encode("utf-8"):
        accumulated = (accumulated * 37 + byte) & _HASH_MASK
    return _hash_uint2(accumulated, 0) / float(_HASH_MASK)


#: Triangles sampled per object by resolve_uv_to_world_scales. A mean scale does not
#: need every triangle, and a high-poly source can carry millions.
_UV_SCALE_TRIANGLE_SAMPLES = 2048


def resolve_uv_to_world_scales(objects) -> tuple[float, float]:
    """(|dP/du|, |dP/dv|) averaged across *objects* -- world units per UV unit.

    Bump differentiates its height against the texture coordinate, so its slopes
    are per UV unit, while the tangent frame it perturbs is unit world. Cycles'
    construction reduces, for a UV parameterization, to a tangent-space normal of
    (-dH/du / |dP/du|, -dH/dv / |dP/dv|, 1) -- the two are only in the same scale
    once divided by the world size of a UV unit. These are those divisors.

    The two axes are measured separately because a UV map is not required to be
    square. A single isotropic figure is their geometric mean, which fits neither:
    on a fixture whose V spans twice the world extent of its U, that measured 0.050
    against Cycles where the per-axis pair measures 0.014.

    UV-area-weighted, and sampled rather than exhaustive. Exact for an evenly laid
    out UV map, approximate where texel density varies within the mesh. Returns
    (1.0, 1.0) when there is nothing to measure.
    """
    weight_total = 0.0
    du_total = 0.0
    dv_total = 0.0
    for obj in objects or []:
        mesh = getattr(obj, "data", None)
        if mesh is None or not hasattr(mesh, "loop_triangles"):
            continue
        try:
            mesh.calc_loop_triangles()
        except Exception:
            continue
        uv_layer = getattr(getattr(mesh, "uv_layers", None), "active", None)
        if uv_layer is None:
            continue
        triangles = mesh.loop_triangles
        total = len(triangles)
        if not total:
            continue
        stride = max(1, total // _UV_SCALE_TRIANGLE_SAMPLES)
        matrix = getattr(obj, "matrix_world", None)
        vertices = mesh.vertices
        for index in range(0, total, stride):
            tri = triangles[index]
            try:
                corners = [vertices[vi].co for vi in tri.vertices]
                if matrix is not None:
                    corners = [matrix @ co for co in corners]
                uvs = [uv_layer.data[li].uv for li in tri.loops]
            except Exception:
                continue
            edge1 = corners[1] - corners[0]
            edge2 = corners[2] - corners[0]
            du1, dv1 = uvs[1][0] - uvs[0][0], uvs[1][1] - uvs[0][1]
            du2, dv2 = uvs[2][0] - uvs[0][0], uvs[2][1] - uvs[0][1]
            det = du1 * dv2 - du2 * dv1
            if abs(det) <= 1e-12:
                # Degenerate in UV: no parameterization to measure here.
                continue
            weight = abs(det) * 0.5
            dpdu = (edge1 * dv2 - edge2 * dv1) / det
            dpdv = (edge2 * du1 - edge1 * du2) / det
            du_total += dpdu.length * weight
            dv_total += dpdv.length * weight
            weight_total += weight
    if weight_total <= 1e-12:
        return (1.0, 1.0)
    return (
        max(du_total / weight_total, 1e-6),
        max(dv_total / weight_total, 1e-6),
    )


def resolve_object_info(objects) -> dict[str, Any]:
    """Object Info values shared by every object in *objects*.

    A field is None when the objects disagree. The compiler turns that into a
    Cycles fallback for that output, because one program serves every object
    using the material and there is no single right constant to bake.
    """
    shared: dict[str, Any] = {}
    for obj in objects or []:
        if obj is None:
            continue
        # No `or` fallbacks on these: a fully black object colour and an object at
        # the world origin are both legitimate values that a truthiness test would
        # silently replace with a default.
        raw_color = getattr(obj, "color", None)
        color = tuple(
            float(c) for c in ((tuple(raw_color) if raw_color is not None else ()) + (1.0,) * 4)[:4]
        )
        matrix = getattr(obj, "matrix_world", None)
        if matrix is not None and hasattr(matrix, "translation"):
            location = tuple(float(v) for v in matrix.translation)
        else:
            raw_location = getattr(obj, "location", None)
            location = (
                tuple(float(v) for v in raw_location)
                if raw_location is not None
                else (0.0, 0.0, 0.0)
            )
        slots = list(getattr(obj, "material_slots", None) or [])
        entry: dict[str, Any] = {
            "location": location,
            "color": color[:3],
            "alpha": color[3],
            "object_index": float(getattr(obj, "pass_index", 0) or 0),
            # Material Index is per-face, not per-object, so it is only knowable
            # here when the object carries exactly one slot and every face reads 0.
            "material_index": 0.0 if len(slots) == 1 else None,
            "random": object_random_number(str(getattr(obj, "name", "") or "")),
        }
        for key, value in entry.items():
            if key not in shared:
                shared[key] = value
            elif shared[key] != value:
                shared[key] = None
    return shared


def _active_material_output(material):
    tree = getattr(material, "node_tree", None)
    if tree is None:
        return None
    outputs = [
        node
        for node in getattr(tree, "nodes", []) or []
        if str(getattr(node, "type", "") or "") == "OUTPUT_MATERIAL"
    ]
    if not outputs:
        return None
    return next(
        (node for node in outputs if bool(getattr(node, "is_active_output", False))),
        outputs[0],
    )


def compile_channel_program(
    material,
    channel: str,
    *,
    workspace_path=None,
    object_info=None,
    uv_to_world_scale=1.0,
    attribute_objects=None,
    allow_ray_ops: bool = False,
    flip_green: bool = False,
    allow_image_sample_kind: bool = True,
    sampler_addressed_images: bool = False,
    normal_low_frame: bool = False,
    bake_uv_layer_name: str | None = None,
) -> MaterialIrProgram:
    """Compile one surface-shader channel to Material IR, or return a Cycles fallback.

    ``flip_green`` is the DirectX convention for the NORMAL channel; it is ignored
    for every other channel. See `_encode_world_normal_as_tangent`.

    ``sampler_addressed_images`` leaves every image tap's extension and
    interpolation to the backend sampler; see `_merge_slot_indexed_programs`.
    """
    channel = str(channel or "").strip().upper()
    if channel not in CHANNEL_TO_PRINCIPLED:
        return _cycles_program(channel, f"Channel '{channel}' is not a native material channel yet")

    if material is None or not getattr(material, "use_nodes", False):
        return _cycles_program(channel, "Material has no node tree")

    tree = material.node_tree
    output_node = _active_material_output(material)
    surface = None
    if output_node is not None:
        surface = output_node.inputs.get("Surface")
    want = "SCALAR" if channel in {
        constants.MATERIAL_CHANNEL_ROUGHNESS,
        constants.MATERIAL_CHANNEL_METALNESS,
        constants.MATERIAL_CHANNEL_OPACITY,
        constants.MATERIAL_CHANNEL_SPECULAR,
        constants.MATERIAL_CHANNEL_TRANSMISSION,
    } else "COLOR"

    material_name = str(getattr(material, "name", "") or "Material")
    compiler = _UvExpressionCompiler(
        material_name=material_name,
        workspace_path=workspace_path,
        object_info=object_info,
        uv_to_world_scale=uv_to_world_scale,
        attribute_objects=attribute_objects,
        sampler_addressed_images=sampler_addressed_images,
        bake_uv_layer_name=bake_uv_layer_name,
    )

    try:
        if surface is not None and bool(getattr(surface, "is_linked", False)):
            result = compiler._compile_shader_socket(surface, channel, want)
        else:
            # No Material Output surface: compile an unused Principled if present
            # so constant-only test graphs still bake natively.
            principled = next(
                (n for n in tree.nodes if getattr(n, "type", "") == "BSDF_PRINCIPLED"),
                None,
            )
            if principled is None:
                return _cycles_program(channel, "No surface shader on Material Output")
            result = compiler._compile_principled_channel(principled, channel, want)
        if channel == constants.MATERIAL_CHANNEL_NORMAL and want != "SCALAR":
            result = compiler._encode_world_normal_as_tangent(
                result, flip_green=bool(flip_green), low_frame=bool(normal_low_frame)
            )
    except ValueError as exc:
        return _cycles_program(channel, str(exc), exc)

    return _finalize_compiled_program(
        channel=channel,
        result=result,
        compiler=compiler,
        allow_ray_ops=allow_ray_ops,
        allow_image_sample_kind=allow_image_sample_kind,
    )


def compile_custom_output_program(
    material,
    output_name: str,
    *,
    workspace_path=None,
    data_type: str = "",
    object_info=None,
    uv_to_world_scale=1.0,
    attribute_objects=None,
    allow_ray_ops: bool = False,
    allow_image_sample_kind: bool = True,
    sampler_addressed_images: bool = False,
    bake_uv_layer_name: str | None = None,
) -> MaterialIrProgram:
    """Compile a Fyr Custom Output socket into Material IR, or return a Cycles fallback."""
    from . import material_capture_nodes

    label = str(output_name or "").strip() or "Custom"
    channel = f"CUSTOM:{label}"
    if material is None or not getattr(material, "use_nodes", False):
        return _cycles_program(channel, "Material has no node tree")

    normalized = label.casefold()
    target = None
    for node in material_capture_nodes.iter_custom_outputs(material):
        name = str(getattr(node, "output_name", "") or "").strip()
        if name.casefold() == normalized:
            target = node
            break
    resolved_type = str(data_type or constants.MATERIAL_DATA_COLOR).strip().upper()
    if target is None:
        # A material that does not carry this output contributes nothing to it --
        # the same zero Cycles would read. Refusing here instead used to drag the
        # whole row onto Cycles as soon as ONE slot on the object lacked the node,
        # which is the ordinary multi-material case, and the Cycles route for a
        # custom output is the one that freezes Blender.
        return _constant_custom_output_program(
            channel,
            want="SCALAR" if resolved_type == constants.MATERIAL_DATA_VALUE else "COLOR",
            workspace_path=workspace_path,
            object_info=object_info,
            uv_to_world_scale=uv_to_world_scale,
            attribute_objects=attribute_objects,
            allow_ray_ops=allow_ray_ops,
            material_name=str(getattr(material, "name", "") or "Material"),
            bake_uv_layer_name=bake_uv_layer_name,
        )

    socket = target.inputs[0] if target.inputs else None
    if socket is None:
        return _cycles_program(channel, f"Custom output '{label}' has no input socket")

    resolved_type = str(data_type or getattr(target, "data_type", "") or constants.MATERIAL_DATA_COLOR).strip().upper()
    want = "SCALAR" if resolved_type == constants.MATERIAL_DATA_VALUE else "COLOR"
    material_name = str(getattr(material, "name", "") or "Material")
    compiler = _UvExpressionCompiler(
        material_name=material_name,
        workspace_path=workspace_path,
        object_info=object_info,
        uv_to_world_scale=uv_to_world_scale,
        attribute_objects=attribute_objects,
        sampler_addressed_images=sampler_addressed_images,
        bake_uv_layer_name=bake_uv_layer_name,
    )
    try:
        if not bool(getattr(socket, "is_linked", False)):
            # `channel` is "CUSTOM:<label>" here and could never equal "NORMAL", so this
            # branch was dead and every unlinked Vector output baked (0,0,0). A custom
            # output of Vector data type is the normal-carrying socket.
            if str(data_type or "").strip().upper() == constants.MATERIAL_DATA_VECTOR:
                # An unlinked Vector socket means "use the shading normal". Its
                # default_value is (0,0,0), which would bake a zero vector.
                result = compiler._emit(
                    {"op": OPCODE_ATTR_NORMAL, "dst": compiler._alloc()}
                )
            else:
                rgba = _socket_default_rgba(socket)
                result = compiler._emit_constant(rgba)
                if want == "SCALAR":
                    result = compiler._emit_swizzle(result, "LUMA")
        else:
            result = compiler.compile_socket(socket, want=want)
    except ValueError as exc:
        return _cycles_program(channel, str(exc), exc)

    return _finalize_compiled_program(
        channel=channel,
        result=result,
        compiler=compiler,
        allow_ray_ops=allow_ray_ops,
        allow_image_sample_kind=allow_image_sample_kind,
    )


def compile_group_channel_program(
    materials,
    channel: str,
    *,
    workspace_path=None,
    object_info=None,
    uv_to_world_scale=1.0,
    attribute_objects=None,
    allow_ray_ops: bool = False,
    flip_green: bool = False,
    normal_low_frame: bool = False,
    bake_uv_layer_name: str | None = None,
) -> MaterialIrProgram:
    """Compile a channel across all contributing materials; require one shared native program."""
    materials = [m for m in (materials or []) if m is not None]
    channel = str(channel or "").strip().upper()
    if not materials:
        return _cycles_program(channel, "No materials to compile")

    programs = [
        compile_channel_program(
            material,
            channel,
            workspace_path=workspace_path,
            object_info=object_info,
            uv_to_world_scale=uv_to_world_scale,
            attribute_objects=attribute_objects,
            allow_ray_ops=allow_ray_ops,
            flip_green=flip_green,
            normal_low_frame=normal_low_frame,
            bake_uv_layer_name=bake_uv_layer_name,
        )
        for material in materials
    ]
    if not all(program.native for program in programs):
        refused = [p for p in programs if not p.native]
        reasons = [p.fallback_reason for p in refused if p.fallback_reason]
        reason = reasons[0] if reasons else "Not all materials support native Material IR"
        aggregate = _cycles_program(channel, reason)
        # Carry the refusing node's identity across. Rebuilding the fallback here
        # used to drop it, so every consumer downstream saw an anonymous refusal --
        # which is why the bake could not tell a view-dependent channel (bakes as a
        # flat constant, worth a warning) from an ordinary Cycles fallback
        # (bakes correctly, just slower). See MATERIAL_BAKE_QA_2026_08_21_PASS4.md, P4.
        for candidate in refused:
            if candidate.fallback_node_type:
                aggregate.fallback_node_name = candidate.fallback_node_name
                aggregate.fallback_node_type = candidate.fallback_node_type
                aggregate.fallback_node_path = candidate.fallback_node_path
                break
        return aggregate

    # Structural equality on ops + resource count (paths filled later).
    def _signature(program: MaterialIrProgram) -> tuple:
        resource_sig = tuple(
            (str(item.get("channel") or ""), id(item.get("image")))
            for item in program.resources
        )
        # Every field of every op, not a hand-kept list of them: the old list left out
        # `clamp` and `steps` (Map Range), the Vector Transform direction and others, so
        # two materials differing only in Map Range Clamp compared equal and the group
        # shipped the first material's program for both (found by the real-GPU compare).
        ops_sig = tuple(
            tuple(sorted((str(key), repr(value)) for key, value in op.items()))
            for op in program.ops
        )
        return (program.kind, program.result_reg, resource_sig, ops_sig)

    first = programs[0]
    first_sig = _signature(first)
    if any(_signature(p) != first_sig for p in programs[1:]):
        # Materials that differ only in WHICH images they read (the common "one
        # shader, a texture set per material" high) share one program whose image
        # taps index a per-material slot table. No select staircase, no
        # MAX_MERGED_MATERIALS bound. Only worth trying when an image is involved;
        # everything else goes straight to the select-merge below.
        if _programs_read_images(programs):
            sampler_programs = [
                compile_channel_program(
                    material,
                    channel,
                    workspace_path=workspace_path,
                    object_info=object_info,
                    uv_to_world_scale=uv_to_world_scale,
                    attribute_objects=attribute_objects,
                    allow_ray_ops=allow_ray_ops,
                    flip_green=flip_green,
                    normal_low_frame=normal_low_frame,
                    allow_image_sample_kind=False,
                    sampler_addressed_images=True,
                )
                for material in materials
            ]
            if all(program.native for program in sampler_programs):
                slot_merged = _merge_slot_indexed_programs(
                    sampler_programs, materials, channel
                )
                if slot_merged is not None:
                    return slot_merged
        merged = _merge_per_material_programs(programs, materials, channel)
        if merged is not None:
            return merged
        # A branch compiled to IMAGE_SAMPLE cannot be an arm of the select, so the
        # SIMPLEST material -- one whose channel is just an Image Texture -- used to
        # sink the whole channel to Cycles, while the same texture behind a no-op
        # Mapping node merged fine. Recompile those branches in their EXPRESSION_UV
        # form and try once more (P6).
        if any(p.kind == MATERIAL_IR_KIND_IMAGE_SAMPLE for p in programs):
            unspecialized = [
                compile_channel_program(
                    material,
                    channel,
                    workspace_path=workspace_path,
                    object_info=object_info,
                    uv_to_world_scale=uv_to_world_scale,
                    attribute_objects=attribute_objects,
                    allow_ray_ops=allow_ray_ops,
                    flip_green=flip_green,
                    normal_low_frame=normal_low_frame,
                    allow_image_sample_kind=False,
                )
                for material in materials
            ]
            if all(program.native for program in unspecialized):
                merged = _merge_per_material_programs(unspecialized, materials, channel)
                if merged is not None:
                    return merged
        return _cycles_program(channel, "Materials disagree on the native expression for this channel")
    return first


def _program_register_span(program: MaterialIrProgram) -> int:
    """One past the highest register index the program touches."""
    highest = int(program.result_reg)
    for op in program.ops:
        for field in ("dst",) + _OP_REG_READ_FIELDS + _OP_REG_WRITE_FIELDS:
            value = op.get(field)
            if type(value) is int and value > highest:
                highest = value
    return highest + 1


def _programs_read_images(programs) -> bool:
    """Whether any program samples a Blender image (the only thing a slot table indexes)."""
    for program in programs:
        for item in getattr(program, "resources", None) or ():
            if isinstance(item, dict) and item.get("image") is not None:
                return True
    return False


def _slot_merge_signature(program: MaterialIrProgram) -> tuple:
    """Structure of a sampler-addressed program with image IDENTITY left out.

    Resources compare by channel and kind (plain image / UDIM table / attribute
    sidecar) plus any Missing colour; ops compare in FULL, every field. That is
    stricter than `_signature`'s hand-picked subset on purpose: two materials only
    share a slot-table program when the ONLY thing that differs is which image a
    tap reads. Extension and interpolation are op fields here (sampler addressing),
    so a difference in either keeps the materials apart.
    """
    resource_sig = []
    for item in program.resources:
        if item.get("image") is not None:
            kind = "TILED" if item.get("tiled") else "IMAGE"
        else:
            kind = "ATTR"
        missing = item.get("missing")
        resource_sig.append(
            (
                str(item.get("channel") or ""),
                kind,
                tuple(float(v) for v in missing) if missing is not None else None,
            )
        )
    ops_sig = tuple(
        tuple(sorted((str(key), repr(value)) for key, value in op.items()))
        for op in program.ops
    )
    return (program.kind, int(program.result_reg), tuple(resource_sig), ops_sig)


def _merge_slot_indexed_programs(programs, materials, channel: str):
    """Fold N structurally identical per-material programs into ONE slot-table program.

    The shape this exists for is a high poly whose materials all run the same node
    graph over their own texture set: dozens of materials, each a copy of one
    shader with different images. The select-merge evaluates every branch at every
    hit and caps out at MAX_MERGED_MATERIALS; here every material runs the SAME ops,
    so shading cost does not grow with the material count at all.

    `programs` must come from the sampler-addressed recompile
    (`sampler_addressed_images=True`, `allow_image_sample_kind=False`): no op may
    depend on an image's size, or one program could not serve all of them.

    Each image resource whose image differs across materials becomes a slot table,
    `{"slots": [one image per material, in slot_materials order]}`; one that reads
    the same image everywhere stays a plain resource (or UDIM table). One
    ATTR_TRIANGLE_SLOT fetch at the top supplies the slot register every slot-table
    tap reads. Returns None when the programs are not identical up to image
    identity, when nothing actually differs, or when it does not fit; the caller
    then falls back to the select-merge exactly as before.
    """
    names = []
    for material in materials:
        name = str(getattr(material, "name", "") or "")
        if not name:
            return None  # an unnamed material cannot be found again at export time
        names.append(name)
    if len(names) != len(programs) or len(set(names)) != len(names):
        return None
    if not (1 < len(programs) <= MAX_SLOT_TABLE_MATERIALS):
        return None
    if any(p.kind != MATERIAL_IR_KIND_EXPRESSION_UV or not p.native for p in programs):
        return None
    template = programs[0]
    template_sig = _slot_merge_signature(template)
    if any(_slot_merge_signature(p) != template_sig for p in programs[1:]):
        return None

    resources: list[dict[str, Any]] = []
    slot_tables: set[int] = set()
    for index, item in enumerate(template.resources):
        if item.get("image") is None:
            resources.append(dict(item))
            continue
        images = [p.resources[index].get("image") for p in programs]
        if len({_node_cache_id(image) for image in images}) == 1:
            resources.append(dict(item))
            continue
        table: dict[str, Any] = {
            "channel": str(item.get("channel") or "RGBA"),
            "path": "",
            "slots": [
                {"image": image, **({"tiled": True} if p.resources[index].get("tiled") else {})}
                for image, p in zip(images, programs)
            ],
        }
        if item.get("missing") is not None:
            table["missing"] = list(item["missing"])
        resources.append(table)
        slot_tables.add(index)
    if not slot_tables:
        return None
    if len(resources) >= _MAX_RESOURCES:
        return None

    slot_resource = len(resources)
    resources.append({"channel": TRIANGLE_ATTR_MATERIAL_SLOT, "image": None, "path": ""})
    # A register no template op touches, so the fetch cannot alias anything; the
    # allocator below compacts it back into the register file.
    slot_register = _program_register_span(template)
    ops: list[dict[str, Any]] = [
        {"op": OPCODE_ATTR_TRIANGLE_SLOT, "dst": int(slot_register), "resource": int(slot_resource)}
    ]
    for op in template.ops:
        copy = dict(op)
        if copy.get("op") == OPCODE_SAMPLE_IMAGE and int(copy.get("resource", -1)) in slot_tables:
            copy["slot"] = int(slot_register)
        ops.append(copy)
    if len(ops) > _MAX_OPS:
        return None
    _register_count, result_register = _allocate_registers(ops, int(template.result_reg))
    merged = MaterialIrProgram(
        version=MATERIAL_IR_VERSION_SAMPLER_TABLES,
        kind=MATERIAL_IR_KIND_EXPRESSION_UV,
        opcodes=sorted({str(op.get("op") or "") for op in ops}),
        channel=channel,
        native=True,
        result_reg=int(result_register),
        resources=resources,
        ops=ops,
        slot_materials=tuple(names),
    )
    if gpu_support_reason(merged):
        return None
    return merged


def _merge_per_material_programs(programs, materials, channel: str):
    """Fold N per-material programs into one, selected by a per-corner material index.

    A high poly carrying two materials is the normal case for an artist, and it used
    to send every channel whose materials disagree to Cycles -- measured at 2.2 s to
    over a minute on the Pottery, with the Cycles route's own defects on top.

    The IR is straight-line with no branches, so "select" is arithmetic: sample the
    material index once, then fold the branches together with a staircase of
    MIX(previous, branch_k, index > k - 0.5). Every branch is evaluated at every hit;
    that is the cost of having no jump, and it is why MAX_MERGED_MATERIALS is small.

    Returns None when the merge does not fit, in which case the caller falls back to
    Cycles exactly as before. Nothing here can produce a *wrong* program: the guards
    are all "does it fit", and the selector is exact because all three corners of a
    triangle carry the same index.
    """
    names = []
    for material in materials:
        name = str(getattr(material, "name", "") or "")
        if not name:
            return None  # an unnamed material cannot be found again at export time
        names.append(name)
    if len(names) != len(programs) or len(set(names)) != len(names):
        return None
    if not (1 < len(programs) <= MAX_MERGED_MATERIALS):
        return None
    # Every branch must be an expression the interpreter runs. A specialised
    # IMAGE_SAMPLE program is a different contract (the backend reprojects a texture
    # rather than executing ops), so it cannot be one arm of a select.
    if any(p.kind != MATERIAL_IR_KIND_EXPRESSION_UV for p in programs):
        return None

    merged_ops: list[dict[str, Any]] = []
    merged_resources: list[dict[str, Any]] = []
    branch_results: list[int] = []
    next_register = 0
    for program in programs:
        register_offset = next_register
        resource_offset = len(merged_resources)
        for op in program.ops:
            relocated = dict(op)
            for field in ("dst",) + _OP_REG_READ_FIELDS + _OP_REG_WRITE_FIELDS:
                value = relocated.get(field)
                # `>= 0` keeps the -1 sentinels ("use the shading point") intact,
                # the same rule _allocate_registers applies.
                if type(value) is int and value >= 0:
                    relocated[field] = value + register_offset
            resource = relocated.get("resource")
            if type(resource) is int and resource >= 0:
                relocated["resource"] = resource + resource_offset
            merged_ops.append(relocated)
        for item in program.resources:
            relocated_item = dict(item)
            if relocated_item.get("tiled"):
                # Which material's triangles read this UDIM table, so export ships
                # (and warns about) only the tiles THAT material's UVs reach. Never
                # on the wire: wire_resource keeps channel / path / tables only.
                relocated_item["material"] = names[len(branch_results)]
            merged_resources.append(relocated_item)
        branch_results.append(int(program.result_reg) + register_offset)
        next_register = register_offset + _program_register_span(program)

    def _emit(op: dict[str, Any]) -> int:
        nonlocal next_register
        register = next_register
        next_register += 1
        op["dst"] = register
        merged_ops.append(op)
        return register

    if len(merged_resources) >= _MAX_RESOURCES:
        return None
    slot_resource = len(merged_resources)
    merged_resources.append({"channel": CORNER_ATTR_MATERIAL_SLOT, "image": None})
    index_register = _emit(
        {"op": OPCODE_ATTR_CORNER_FLOAT, "dst": 0, "resource": int(slot_resource)}
    )
    accumulator = branch_results[0]
    for branch, result_register in enumerate(branch_results[1:], start=1):
        threshold = float(branch) - 0.5
        constant = _emit(
            {"op": OPCODE_CONSTANT, "dst": 0, "value": [threshold, threshold, threshold, 1.0]}
        )
        scalar = _emit({"op": OPCODE_SWIZZLE, "dst": 0, "src": int(constant), "mode": "LUMA"})
        selector = _emit(
            {
                "op": OPCODE_MATH,
                "dst": 0,
                "math_op": "GREATER_THAN",
                "a": int(index_register),
                "b": int(scalar),
                "fac": int(scalar),
            }
        )
        accumulator = _emit(
            {
                "op": OPCODE_MIX,
                "dst": 0,
                "a": int(accumulator),
                "b": int(result_register),
                "fac": int(selector),
                "blend": "MIX",
            }
        )

    if len(merged_ops) > _MAX_OPS:
        return None
    register_count, result_register = _allocate_registers(merged_ops, accumulator)
    opcodes = sorted({str(op.get("op") or "") for op in merged_ops})
    merged = MaterialIrProgram(
        # A branch reading a UDIM table carries the table into the merge.
        version=_program_version(merged_resources, merged_ops),
        kind=MATERIAL_IR_KIND_EXPRESSION_UV,
        opcodes=opcodes,
        channel=channel,
        native=True,
        result_reg=int(result_register),
        resources=merged_resources,
        ops=merged_ops,
        slot_materials=tuple(names),
    )
    reason = gpu_support_reason(merged)
    if reason:
        return None
    _ = register_count
    return merged


def _constant_custom_output_program(
    channel: str,
    *,
    want: str,
    workspace_path,
    object_info,
    uv_to_world_scale,
    attribute_objects,
    allow_ray_ops: bool,
    material_name: str,
    bake_uv_layer_name: str | None = None,
) -> MaterialIrProgram:
    """A native program that reads zero, for a material with no such custom output."""
    compiler = _UvExpressionCompiler(
        material_name=material_name,
        workspace_path=workspace_path,
        object_info=object_info,
        uv_to_world_scale=uv_to_world_scale,
        attribute_objects=attribute_objects,
        bake_uv_layer_name=bake_uv_layer_name,
    )
    result = compiler._emit_constant((0.0, 0.0, 0.0, 1.0))
    if want == "SCALAR":
        result = compiler._emit_swizzle(result, "LUMA")
    return _finalize_compiled_program(
        channel=channel, result=result, compiler=compiler, allow_ray_ops=allow_ray_ops
    )


def compile_group_custom_output_program(
    materials,
    output_name: str,
    *,
    workspace_path=None,
    data_type: str = "",
    object_info=None,
    uv_to_world_scale=1.0,
    attribute_objects=None,
    allow_ray_ops: bool = False,
    bake_uv_layer_name: str | None = None,
) -> MaterialIrProgram:
    """Compile a named Custom Output across materials; require one shared native program."""
    materials = [m for m in (materials or []) if m is not None]
    label = str(output_name or "").strip() or "Custom"
    channel = f"CUSTOM:{label}"
    if not materials:
        return _cycles_program(channel, "No materials to compile")

    programs = [
        compile_custom_output_program(
            material,
            label,
            workspace_path=workspace_path,
            data_type=data_type,
            object_info=object_info,
            uv_to_world_scale=uv_to_world_scale,
            attribute_objects=attribute_objects,
            allow_ray_ops=allow_ray_ops,
            bake_uv_layer_name=bake_uv_layer_name,
        )
        for material in materials
    ]
    if not all(program.native for program in programs):
        reasons = [p.fallback_reason for p in programs if not p.native and p.fallback_reason]
        reason = reasons[0] if reasons else "Not all materials support native Material IR for this custom output"
        return _cycles_program(channel, reason)

    def _signature(program: MaterialIrProgram) -> tuple:
        # Image identity is part of the structure. Without it two materials running
        # the same graph over DIFFERENT textures compared equal and the group shipped
        # the first material's program, i.e. its textures, for every material.
        resource_sig = tuple(
            (str(res.get("channel") or "RGBA"), int(i), _node_cache_id(res.get("image")))
            for i, res in enumerate(program.resources)
        )
        # All op fields, as in the channel combiner: a hand-kept list let materials that
        # differed only in Clamp or Steps compare equal.
        ops_sig = tuple(
            tuple(sorted((str(key), repr(value)) for key, value in op.items()))
            for op in program.ops
        )
        return (program.kind, program.result_reg, resource_sig, ops_sig)

    first = programs[0]
    first_sig = _signature(first)
    if any(_signature(p) != first_sig for p in programs[1:]):
        # Same texture-set-per-material slot table the ordinary channels use.
        if _programs_read_images(programs):
            sampler_programs = [
                compile_custom_output_program(
                    material,
                    label,
                    workspace_path=workspace_path,
                    data_type=data_type,
                    object_info=object_info,
                    uv_to_world_scale=uv_to_world_scale,
                    attribute_objects=attribute_objects,
                    allow_ray_ops=allow_ray_ops,
                    allow_image_sample_kind=False,
                    sampler_addressed_images=True,
                    bake_uv_layer_name=bake_uv_layer_name,
                )
                for material in materials
            ]
            if all(program.native for program in sampler_programs):
                slot_merged = _merge_slot_indexed_programs(
                    sampler_programs, materials, channel
                )
                if slot_merged is not None:
                    return slot_merged
        # Same per-corner material-index fold the ordinary channels already use, so a
        # custom output authored in one slot's material and absent from another's
        # stays native instead of falling onto the Cycles route.
        merged = _merge_per_material_programs(programs, materials, channel)
        if merged is not None:
            return merged
        return _cycles_program(channel, "Materials disagree on the native expression for this custom output")
    return first


def resolve_execution_route(
    requested_route: str,
    program: MaterialIrProgram,
) -> tuple[str, str]:
    """Return (effective_route, user-facing reason).

    Reasons are written into map-row status / diagnostics. Keep them short and
    artist-facing — never leak IR kinds like EXPRESSION_UV / IMAGE_SAMPLE.
    Happy Auto→Fyr returns an empty reason so the panel stays quiet.
    """
    requested = str(requested_route or constants.EXECUTION_ROUTE_AUTO).strip().upper()
    if requested == constants.EXECUTION_ROUTE_BLENDER:
        return constants.EXECUTION_ROUTE_BLENDER, "Using Cycles"
    if requested == constants.EXECUTION_ROUTE_BACKEND:
        if program.native:
            return constants.EXECUTION_ROUTE_BACKEND, "Using Fyr"
        return constants.EXECUTION_ROUTE_BACKEND, program.fallback_reason or "Fyr cannot bake this material"
    if program.native:
        return constants.EXECUTION_ROUTE_BACKEND, ""
    reason = str(program.fallback_reason or "").strip()
    return constants.EXECUTION_ROUTE_BLENDER, reason or "Using Cycles"


def program_uses_ray_opcodes(program: MaterialIrProgram) -> bool:
    """Whether *program* contains an opcode that traces scene rays.

    Route predicate, in the shape of export.py's `_material_ir_source_requires_high_uvs`:
    the compiler cannot see which shader permutation the backend will pick, so it
    publishes the requirement and the transport/routing layer honours it. A True
    here means the program is only correct on the MATERIAL_ONLY + DXR_INLINE
    route; every other kernel substitutes the neutral 1.0
    (docs/SECONDARY_RAY_NODES_PLAN.md section 10.5).

    Conservative for malformed input: an unreadable op list counts as ray-using,
    so a future IR shape cannot silently escape the gate.
    """
    ops = getattr(program, "ops", None)
    if ops is None and isinstance(program, dict):
        ops = program.get("ops")
    if ops is None:
        return True
    try:
        return any(
            str(op.get("op", "") or "").strip().upper() in GPU_RAY_OPCODES
            for op in ops
            if isinstance(op, dict)
        )
    except Exception:
        return True


def program_ray_sample_total(program: MaterialIrProgram) -> int:
    """Total TLAS traversals per texel the program requests.

    Sum of `samples` over every ray op, each clamped to the backend's window —
    the shader and the encoder both clamp, so an out-of-range value in the op
    dict costs what the GPU will actually spend, not what the dict claims.
    """
    ops = getattr(program, "ops", None)
    if ops is None and isinstance(program, dict):
        ops = program.get("ops")
    if not ops:
        return 0
    total = 0
    for op in ops:
        if not isinstance(op, dict):
            continue
        opcode = str(op.get("op", "") or "").strip().upper()
        if opcode not in GPU_RAY_OPCODES:
            continue
        if opcode == OPCODE_RAYCAST:
            # Deterministic: one closest-hit ray, no `samples` field to read.
            # Counting the missing key as the sampled default would charge it 128
            # and refuse a two-Raycast graph outright.
            total += RAYCAST_RAY_SAMPLES
            continue
        samples = _int_or(op.get("samples", RAY_NODE_MAX_SAMPLES), RAY_NODE_MAX_SAMPLES)
        total += max(RAY_NODE_MIN_SAMPLES, min(RAY_NODE_MAX_SAMPLES, samples))
    return total


def _sampler_tap_gpu_reason(program: MaterialIrProgram, op: dict, resource: int) -> str:
    """Validate a SAMPLE_IMAGE against the sampler-table contract.

    A table resource is only readable through sampler addressing, so its taps must
    carry `extension` + `mode`, and a slot table's taps a `slot` register. An
    ordinary tap must not claim a slot. Malformed programs refuse (Cycles) rather
    than reaching a backend that would read the wrong image.
    """
    resources = program.resources or []
    item = resources[resource] if 0 <= resource < len(resources) else None
    is_table = _resource_is_table(item)
    has_extension = "extension" in op
    if has_extension:
        extension = str(op.get("extension") or "").strip().upper()
        if extension not in SAMPLER_EXTENSIONS:
            return f"Image extension '{extension}' is not implemented on GPU"
        mode = str(op.get("mode") or "").strip().upper()
        if mode not in SAMPLER_INTERPOLATIONS:
            return f"Image interpolation '{mode}' is not implemented on GPU"
    elif is_table:
        return "UDIM or per-material image table read without sampler addressing"
    is_slot_table = isinstance(item, dict) and "slots" in item
    has_slot = type(op.get("slot")) is int and int(op.get("slot")) >= 0
    if is_slot_table and not has_slot:
        return "Per-material image table read without a material slot"
    if has_slot and not is_slot_table:
        return "Material slot given for an image that is not a per-material table"
    if is_slot_table and len(item.get("slots") or ()) > MAX_SLOT_TABLE_MATERIALS:
        return (
            f"Per-material image table has {len(item.get('slots') or ())} slots, "
            f"over the limit of {MAX_SLOT_TABLE_MATERIALS}"
        )
    return ""


def gpu_support_reason(
    program: MaterialIrProgram,
    *,
    allow_textured: bool = True,
    allow_ray_ops: bool = False,
    offending: list | None = None,
) -> str:
    """Return empty when *program* is safe for the GPU MIR interpreter.

    Pass a list as `offending` to learn *which* op tripped a per-op check: the
    per-op loop stamps the current index into it on entry, and every per-op
    refusal returns immediately, so on a non-empty return the list holds the
    offending index. Program-level refusals (budgets, missing ops) return before
    the loop and leave it untouched. Callers that do not care omit it and see no
    behavioural difference.

    `allow_ray_ops` must only be True when the caller can prove the program will
    execute on the material-only DXR route (the sole permutation that compiles
    the ray opcodes in — see `program_uses_ray_opcodes`). It defaults to False
    because the addon cannot observe the backend's batch/PSO choice at compile
    time, and the backend does not refuse a mis-routed ray op: it writes the
    neutral fully-unoccluded 1.0, which bakes a wrong image instead of failing.
    Cycles is the correct fallback there, so the default keeps AO graphs on it.
    """
    if not isinstance(program, MaterialIrProgram):
        return "No Material IR program"
    if not program.ops or int(program.result_reg) < 0:
        return "Material IR program has no executable ops"
    if len(program.ops) > GPU_MAX_OPS:
        return (
            f"Material IR program has {len(program.ops)} ops, "
            f"over the GPU limit of {GPU_MAX_OPS}"
        )
    # The shader clamps register indices rather than failing, so an over-budget
    # program would silently alias every high register onto the last slot.
    highest = int(program.result_reg)
    for op in program.ops:
        dst = op.get("dst")
        if type(dst) is int and dst > highest:
            highest = dst
        # Secondary destinations count too, and must: an op writing dst2 past the
        # register file would clobber. Mirrors the backend's
        # material_ir_program_highest_register, which includes all four RAYCAST
        # register fields (docs/SECONDARY_RAY_NODES_PLAN.md section 12.10.4).
        for field in _OP_REG_WRITE_FIELDS:
            value = op.get(field)
            if type(value) is int and value > highest:
                highest = value
        for field in _OP_REG_READ_FIELDS:
            value = op.get(field)
            if type(value) is int and value > highest:
                highest = value
    if highest >= GPU_MAX_REGISTERS:
        return (
            f"Material IR program needs {highest + 1} registers, "
            f"over the GPU limit of {GPU_MAX_REGISTERS}"
        )
    # Per-program ray budget. Checked before the route gate below so an
    # over-budget program reports the cost reason even when the caller vouched
    # for the material-only DXR route; either way it routes to Cycles.
    ray_samples = program_ray_sample_total(program)
    if ray_samples > GPU_MAX_RAY_SAMPLES:
        return (
            f"Material IR program traces {ray_samples} ray samples per texel, "
            f"over the GPU limit of {GPU_MAX_RAY_SAMPLES}"
        )
    for _op_index, op in enumerate(program.ops):
        if offending is not None:
            offending[:] = [_op_index]
        opcode = str(op.get("op") or "").strip().upper()
        if opcode in {OPCODE_SAMPLE_IMAGE, OPCODE_ATTR_UV}:
            if not allow_textured:
                return f"{opcode} requires textured Material IR GPU support"
            if opcode == OPCODE_SAMPLE_IMAGE:
                resource = int(op.get("resource", -1))
                if resource < 0 or resource >= GPU_MAX_RESOURCES:
                    return "SAMPLE_IMAGE resource index exceeds GPU Material IR limits"
                reason = _sampler_tap_gpu_reason(program, op, resource)
                if reason:
                    return reason
            continue
        if opcode in {OPCODE_ATTR_CORNER_FLOAT, OPCODE_ATTR_TRIANGLE_SLOT}:
            if not allow_textured:
                return f"{opcode} requires textured Material IR GPU support"
            resource = int(op.get("resource", -1))
            if resource < 0 or resource >= GPU_MAX_RESOURCES:
                return f"{opcode} resource index exceeds GPU Material IR limits"
            continue
        if opcode in GPU_RAY_OPCODES and not allow_ray_ops:
            # The backend compiles ray opcodes only into the MATERIAL_ONLY +
            # DXR_INLINE permutation; the megakernel (mixed batch), the AO-only
            # kernel and the software-BVH build all write the opcode's neutral
            # instead (AO -> 1.0, BEVEL -> the shading normal). Silently baking
            # "as if the node were absent" is worse than baking through Cycles,
            # so refuse unless the caller vouched for the route.
            return (
                f"{opcode} only executes on the material-only DXR route and would "
                "bake as its neutral value anywhere else"
            )
        if opcode in GPU_BLOCKED_PARITY_OPCODES:
            return f"{opcode} is not marked GPU-native until CPU/GPU parity is fixed"
        if opcode not in SUPPORTED_OPCODES:
            return f"Unsupported GPU Material IR opcode '{opcode}'"
        if opcode == OPCODE_MIX:
            blend = str(op.get("blend") or "MIX").strip().upper()
            if blend not in GPU_SUPPORTED_MIX_BLEND_TYPES:
                return f"Mix blend '{blend}' is not implemented on GPU"
        elif opcode == OPCODE_MATH:
            math_op = str(op.get("math_op") or "").strip().upper()
            if math_op not in GPU_SUPPORTED_MATH_OPS:
                return f"Math operation '{math_op}' is not implemented on GPU"
        elif opcode == OPCODE_VECTOR_MATH:
            # No default: the backend reads the same key and rejects a blank mode,
            # so defaulting here would vouch for a program the backend refuses.
            math_op = str(op.get("math_op") or "").strip().upper()
            if math_op == "CROSS":
                math_op = "CROSS_PRODUCT"
            elif math_op == "DOT":
                math_op = "DOT_PRODUCT"
            if math_op not in GPU_SUPPORTED_VECTOR_MATH_OPS:
                return f"Vector Math operation '{math_op}' is not implemented on GPU"
        elif opcode == OPCODE_COLOR_RAMP:
            mode = str(op.get("mode") or "LINEAR").strip().upper()
            elements = list(op.get("elements") or [])
            if mode not in GPU_SUPPORTED_COLOR_RAMP_MODES:
                return f"Color Ramp mode '{mode}' is not implemented on GPU"
            if len(elements) > GPU_MAX_COLOR_RAMP_STOPS:
                return (
                    f"Color Ramp has {len(elements)} stops, over the GPU limit "
                    f"of {GPU_MAX_COLOR_RAMP_STOPS}"
                )
        elif opcode == OPCODE_CURVE_MAP:
            samples = len(op.get("table") or [])
            if samples == 0:
                return "Curve table is empty"
            if samples > GPU_MAX_CURVE_SAMPLES:
                return (
                    f"Curve table has {samples} samples, over the GPU limit "
                    f"of {GPU_MAX_CURVE_SAMPLES}"
                )
        elif opcode == OPCODE_WHITE_NOISE_TEXTURE:
            dims = str(op.get("dimensions") or "3D").strip().upper()
            if dims not in {"1D", "2D", "3D", "4D"}:
                return f"{opcode} {dims} is not implemented on GPU"
        elif opcode == OPCODE_NOISE_TEXTURE:
            dims = str(op.get("dimensions") or "3D").strip().upper()
            if dims not in GPU_SUPPORTED_NOISE_DIMS:
                return f"{opcode} {dims} is not implemented on GPU"
        elif opcode == OPCODE_WAVE_TEXTURE:
            dims = str(op.get("dimensions") or "3D").strip().upper()
            if dims not in GPU_SUPPORTED_PROCEDURAL_DIMS:
                return f"{opcode} {dims} is not implemented on GPU"
        elif opcode == OPCODE_VORONOI_TEXTURE:
            dims = str(op.get("dimensions") or "3D").strip().upper()
            metric = str(op.get("metric") or "").strip().upper()
            feature = str(op.get("feature") or "").strip().upper()
            output = str(op.get("output") or "").strip().upper()
            if dims not in GPU_SUPPORTED_VORONOI_DIMS:
                return (
                    f"Voronoi Texture {dims} is not implemented on GPU "
                    "(supported: 1D, 2D, 3D, 4D)"
                )
            if metric not in GPU_SUPPORTED_VORONOI_METRICS:
                return f"Voronoi metric '{metric}' is not implemented on GPU"
            if feature not in GPU_SUPPORTED_VORONOI_FEATURES:
                return f"Voronoi feature '{feature}' is not implemented on GPU"
            if output not in GPU_SUPPORTED_VORONOI_OUTPUTS:
                return f"Voronoi output '{output}' is not implemented on GPU"
    return ""


def program_supports_gpu(
    program: MaterialIrProgram,
    *,
    allow_textured: bool = True,
    allow_ray_ops: bool = False,
) -> bool:
    return (
        gpu_support_reason(
            program, allow_textured=allow_textured, allow_ray_ops=allow_ray_ops
        )
        == ""
    )


def capabilities_payload() -> dict[str, Any]:
    """Addon-side Material IR capability document (mirrored in backend capabilities)."""
    return {
        "material_ir_version": MATERIAL_IR_VERSION,
        "material_ir_opcodes": sorted(SUPPORTED_OPCODES),
        "material_ir_features": {
            "mix_blend_types": sorted(SUPPORTED_MIX_BLEND_TYPES),
            "math_ops": sorted(SUPPORTED_MATH_OPS),
            "vector_math_ops": sorted(SUPPORTED_VECTOR_MATH_OPS),
            "gpu_mix_blend_types": sorted(GPU_SUPPORTED_MIX_BLEND_TYPES),
            "gpu_math_ops": sorted(GPU_SUPPORTED_MATH_OPS),
            "gpu_vector_math_ops": sorted(GPU_SUPPORTED_VECTOR_MATH_OPS),
            "gpu_color_ramp_modes": sorted(GPU_SUPPORTED_COLOR_RAMP_MODES),
            "gpu_procedural_dimensions": sorted(GPU_SUPPORTED_PROCEDURAL_DIMS),
            "gpu_noise_dimensions": sorted(GPU_SUPPORTED_NOISE_DIMS),
            "gpu_voronoi_dimensions": sorted(
                value for value in GPU_SUPPORTED_VORONOI_DIMS if value
            ),
            "gpu_voronoi_metrics": sorted(value for value in GPU_SUPPORTED_VORONOI_METRICS if value),
            "gpu_voronoi_features": sorted(value for value in GPU_SUPPORTED_VORONOI_FEATURES if value),
            "gpu_voronoi_outputs": sorted(value for value in GPU_SUPPORTED_VORONOI_OUTPUTS if value),
            "gpu_blocked_parity_opcodes": sorted(GPU_BLOCKED_PARITY_OPCODES),
            # Only correct on the material-only DXR permutation; every other
            # kernel substitutes the neutral 1.0.
            "gpu_ray_opcodes": sorted(GPU_RAY_OPCODES),
            "gpu_ray_node_max_samples": RAY_NODE_MAX_SAMPLES,
        },
        "material_ir_kinds": [
            MATERIAL_IR_KIND_IMAGE_SAMPLE,
            MATERIAL_IR_KIND_EXPRESSION_UV,
        ],
    }


# Cycles noise seed offsets -- ``intern/cycles/kernel/svm/noisetex.h``:
#     random_float2_offset(seed).c[i] =
#         100.0f + hash_float2_to_float(make_float2(seed, float(i))) * 100.0f
#     random_float3_offset(seed) is the same for i = 0, 1, 2.
# The seeds are compile-time literals (0..4), so every offset is a pure constant.
# Recomputed from the verified Jenkins lookup3 transcription (the same ``final()``
# mix as ``material_geometry_attributes._hash_uint``) and pinned by
# ``tests/test_material_ir.py::NoiseSeedOffsetConstantsTests``.  The C++ reference
# (``backend/src/backend_material_noise.cpp``) and the GPU interpreter
# (``backend/shaders/material_ir.slang``) carry the same numbers.
# 2D: seeds 0,1 drive distortion x,y; seeds 2,3 drive the Color G,B channels.
NOISE_SEED_OFFSET_2D = (
    (186.031281, 114.955956),
    (199.839996, 162.292603),
    (111.633842, 157.369385),
    (165.445282, 162.768219),
)
# 3D: seeds 0,1,2 drive distortion x,y,z; seeds 3,4 drive Color G,B.
NOISE_SEED_OFFSET_3D = (
    (186.031281, 114.955956, 154.447510),
    (199.839996, 162.292603, 154.048233),
    (111.633842, 157.369385, 199.088104),
    (165.445282, 162.768219, 193.408417),
    (155.580917, 177.154633, 138.140030),
)
# 1D is the odd one out: ``random_float_offset(seed) = 100 +
# hash_float_to_float(seed) * 100`` uses the ONE-word ``hash_uint``, not the
# two-word ``hash_float2_to_float`` the 2D/3D/4D tables are built from, so these
# numbers are unrelated to the tables above.  Seed 0 drives distortion; seeds
# 1,2 drive the Color G,B channels.
NOISE_SEED_OFFSET_1D = (
    158.242584,
    114.836052,
    188.488693,
)
# 4D: seeds 0,1,2,3 drive distortion x,y,z,w; seeds 4,5 drive Color G,B.  The
# first three components of each row are the 3D row for the same seed -- same
# ``hash_float2_to_float(seed, i)`` formula, one axis further.
NOISE_SEED_OFFSET_4D = (
    (186.031281, 114.955956, 154.447510, 142.504913),
    (199.839996, 162.292603, 154.048233, 142.267609),
    (111.633842, 157.369385, 199.088104, 178.436127),
    (165.445282, 162.768219, 193.408417, 145.255508),
    (155.580917, 177.154633, 138.140030, 180.185730),
    (188.853790, 132.677689, 162.052155, 185.268158),
)


# ---------------------------------------------------------------------------
# Sampler-addressed image reference (UDIM tables, slot tables)
#
# Transcribed from Blender Cycles (fetched from github.com/blender/blender main):
#   * kernel/util/image_2d.h            kernel_image_udim_map
#   * kernel/device/cpu/image.h         frac, wrap_periodic / wrap_clamp /
#                                       wrap_mirror, interp_closest, interp_linear
# and, for Cubic / Smart, the backend's own Sigg-Hadwiger four-bilinear-tap
# bicubic (mir_sample_texel_buffer_bicubic in material_ir.slang), each bilinear
# tap being the extension-aware linear sampler below inside the SAME image. This
# is the contract the backend sampler implements; the tests drive it.
# ---------------------------------------------------------------------------

_BYTE_TO_FLOAT = 1.0 / 255.0


def _cycles_frac(x: float) -> tuple[float, int]:
    """Cycles' `frac`: `float_to_int(x) - (x < 0)`, NOT floor.

    The two differ at negative integers: frac(-1.0) is (1.0, -2), floor is -1.
    Transcribed literally so the reference agrees with Cycles on texel borders.
    """
    i = int(x) - (1 if x < 0.0 else 0)
    return x - float(i), i


def _wrap_periodic(x: int, width: int) -> int:
    x = int(math.fmod(x, width)) if width else 0  # C `%`: sign follows the dividend
    if x < 0:
        x += width
    return x


def _wrap_clamp(x: int, width: int) -> int:
    return max(0, min(int(x), width - 1))


def _wrap_mirror(x: int, width: int) -> int:
    m = abs(x + (1 if x < 0 else 0)) % (2 * width)
    if m >= width:
        return 2 * width - m - 1
    return m


def _sampler_interp_closest(width, height, read, x, y, extension):
    _tx, ix = _cycles_frac(x)
    _ty, iy = _cycles_frac(y)
    if extension == "REPEAT":
        ix, iy = _wrap_periodic(ix, width), _wrap_periodic(iy, height)
    elif extension == "CLIP":
        if ix < 0 or ix >= width or iy < 0 or iy >= height:
            return (0.0, 0.0, 0.0, 0.0)
    elif extension == "EXTEND":
        ix, iy = _wrap_clamp(ix, width), _wrap_clamp(iy, height)
    elif extension == "MIRROR":
        ix, iy = _wrap_mirror(ix, width), _wrap_mirror(iy, height)
    else:
        return (0.0, 0.0, 0.0, 0.0)
    return tuple(float(c) for c in read(ix, iy))


def _sampler_interp_linear(width, height, read, x, y, extension):
    tx, ix = _cycles_frac(x - 0.5)
    ty, iy = _cycles_frac(y - 0.5)
    if extension == "CLIP":
        if ix < -1 or ix >= width or iy < -1 or iy >= height:
            return (0.0, 0.0, 0.0, 0.0)

        def fetch(px, py):
            if px < 0 or px >= width or py < 0 or py >= height:
                return (0.0, 0.0, 0.0, 0.0)
            return read(px, py)

        nix, niy = ix + 1, iy + 1
    else:
        if extension == "REPEAT":
            ix = _wrap_periodic(ix, width)
            nix = _wrap_periodic(ix + 1, width)
            iy = _wrap_periodic(iy, height)
            niy = _wrap_periodic(iy + 1, height)
        elif extension == "EXTEND":
            nix, ix = _wrap_clamp(ix + 1, width), _wrap_clamp(ix, width)
            niy, iy = _wrap_clamp(iy + 1, height), _wrap_clamp(iy, height)
        elif extension == "MIRROR":
            nix, ix = _wrap_mirror(ix + 1, width), _wrap_mirror(ix, width)
            niy, iy = _wrap_mirror(iy + 1, height), _wrap_mirror(iy, height)
        else:
            return (0.0, 0.0, 0.0, 0.0)
        fetch = read
    c00, c10 = fetch(ix, iy), fetch(nix, iy)
    c01, c11 = fetch(ix, niy), fetch(nix, niy)
    return tuple(
        (1.0 - ty) * (1.0 - tx) * float(c00[c])
        + (1.0 - ty) * tx * float(c10[c])
        + ty * (1.0 - tx) * float(c01[c])
        + ty * tx * float(c11[c])
        for c in range(4)
    )


def _cubic_weights(a: float) -> tuple[float, float, float, float]:
    w0 = (1.0 / 6.0) * (a * (a * (-a + 3.0) - 3.0) + 1.0)
    w1 = (1.0 / 6.0) * (a * a * (3.0 * a - 6.0) + 4.0)
    w2 = (1.0 / 6.0) * (a * (a * (-3.0 * a + 3.0) + 3.0) + 1.0)
    w3 = (1.0 / 6.0) * (a * a * a)
    return w0, w1, w2, w3


def sample_image_texels(width: int, height: int, read, u: float, v: float, *,
                        extension: str = "REPEAT", interpolation: str = "LINEAR"):
    """One sampler-addressed tap of a single image (one UDIM tile, one slot).

    `read(ix, iy)` returns the RGBA of an in-range texel (row 0 = the image's
    bottom row, as the backend loader returns it). `u, v` are already local to the
    image, i.e. the UDIM tile offset is removed.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    extension = str(extension or "REPEAT").strip().upper()
    interpolation = str(interpolation or "LINEAR").strip().upper()
    x = float(u) * width
    y = float(v) * height
    if interpolation == "CLOSEST":
        return _sampler_interp_closest(width, height, read, x, y, extension)
    if interpolation in _BICUBIC_INTERPOLATIONS:
        fx_full = x - 0.5
        fy_full = y - 0.5
        px, py = math.floor(fx_full), math.floor(fy_full)
        fx, fy = fx_full - px, fy_full - py
        wx, wy = _cubic_weights(fx), _cubic_weights(fy)
        g0x, g1x = wx[0] + wx[1], wx[2] + wx[3]
        g0y, g1y = wy[0] + wy[1], wy[2] + wy[3]
        h0x, h1x = wx[1] / g0x - 1.0, wx[3] / g1x + 1.0
        h0y, h1y = wy[1] / g0y - 1.0, wy[3] / g1y + 1.0
        # Texel-space positions of the four bilinear taps (the backend works in
        # uv and multiplies back by the size; the product is the same point).
        x0, x1 = px + h0x + 0.5, px + h1x + 0.5
        y0, y1 = py + h0y + 0.5, py + h1y + 0.5

        def tap(tx, ty):
            return _sampler_interp_linear(width, height, read, tx, ty, extension)

        t00, t10, t01, t11 = tap(x0, y0), tap(x1, y0), tap(x0, y1), tap(x1, y1)
        return tuple(
            g0y * (g0x * t00[c] + g1x * t10[c]) + g1y * (g0x * t01[c] + g1x * t11[c])
            for c in range(4)
        )
    return _sampler_interp_linear(width, height, read, x, y, extension)


def udim_tile_lookup(tiles, u: float, v: float):
    """Cycles' kernel_image_udim_map: (tile record, local u, local v) or None.

    The tile is keyed by C truncation, NOT floor: u = -0.3 lands in column 0, i.e.
    tile 1001, with a local u of -0.3 that the image's own extension then handles.
    `tiles` maps tile number -> whatever the caller stores for it.
    """
    tx = int(u)  # truncation toward zero, like the kernel's (int) cast
    ty = int(v)
    if tx < 0 or ty < 0 or tx >= 10:
        return None
    record = tiles.get(1001 + 10 * ty + tx)
    if record is None:
        return None
    return record, float(u) - tx, float(v) - ty


def resolve_sampler_image(resource, u: float, v: float, slot_value=None):
    """Which image a sampler-addressed tap reads, and at which local coordinate.

    Returns `(path, local_u, local_v)`, or None for a miss (a UV outside every tile
    the table carries, or an empty / out-of-range slot), which reads the resource's
    missing colour. `slot_value` is the float the `slot` register holds; the
    backend rounds it to the nearest integer.
    """
    entry = resource if isinstance(resource, dict) else {}
    if "slots" in entry:
        slots = list(entry.get("slots") or ())
        try:
            index = int(math.floor(float(slot_value if slot_value is not None else 0.0) + 0.5))
        except (TypeError, ValueError):
            return None
        if index < 0 or index >= len(slots) or not slots[index]:
            return None
        entry = slots[index]
    if entry.get("tiled") or "tiles" in entry:
        tiles = {}
        for item in entry.get("tiles") or ():
            if isinstance(item, dict) and item.get("path"):
                tiles[int(item.get("tile"))] = str(item.get("path"))
        found = udim_tile_lookup(tiles, u, v)
        if found is None:
            return None
        return found
    path = str(entry.get("path") or "")
    return path, float(u), float(v)


def _cycles_map_range(
    value: float,
    from_min: float,
    from_max: float,
    to_min: float,
    to_max: float,
    steps: float,
    mode: str,
    use_clamp: bool,
) -> float:
    """Cycles' map_range, transcribed (kernel/svm/map_range.h).

    The Stepped factor uses ``floor(f * (steps + 1)) / steps``, the smooth modes
    clamp their own factor whatever the node's Clamp is set to, and equal From
    values give 0 (not To Min). Clamp then bounds the *result* between To Min and
    To Max in whichever order they are given. The Slang and C++ interpreters carry
    the same transcription.
    """
    if from_max != from_min:
        if mode == "STEPPED":
            factor = (value - from_min) / (from_max - from_min)
            factor = math.floor(factor * (steps + 1.0)) / steps if steps > 0.0 else 0.0
        elif mode in {"SMOOTHSTEP", "SMOOTHERSTEP"}:
            def edge(lo: float, hi: float, x: float) -> float:
                t = min(max((x - lo) / (hi - lo), 0.0), 1.0)
                if mode == "SMOOTHSTEP":
                    return t * t * (3.0 - 2.0 * t)
                return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

            if from_min > from_max:
                factor = 1.0 - edge(from_max, from_min, value)
            else:
                factor = edge(from_min, from_max, value)
        else:
            factor = (value - from_min) / (from_max - from_min)
        result = to_min + factor * (to_max - to_min)
    else:
        result = 0.0
    if use_clamp:
        lo, hi = (to_max, to_min) if to_min > to_max else (to_min, to_max)
        result = min(max(result, lo), hi)
    return result


def evaluate_program_cpu(
    program: MaterialIrProgram,
    sample_rgba_by_resource,
    *,
    uv=(0.0, 0.0),
    object_position=(0.0, 0.0, 0.0),
    generated_position=(0.0, 0.0, 0.0),
    world_position=(0.0, 0.0, 0.0),
    world_normal=(0.0, 0.0, 1.0),
    world_to_object=None,
    high_barycentric=(0.0, 0.0, 0.0),
    true_normal=(0.0, 0.0, 1.0),
    tangent=(1.0, 0.0, 0.0),
    bitangent=(0.0, 1.0, 0.0),
    image_texels=None,
    triangle_slot: float = 0.0,
) -> tuple[float, float, float]:
    """Reference CPU evaluator for unit tests.

    Note: the procedural texture family (Noise / Voronoi / Wave / Magic / Brick)
    is a simplified stand-in here and must be gated engine-vs-engine instead.

    sample_rgba_by_resource(index, u, v) -> (r,g,b,a) OR sample_rgba_by_resource(index).

    Sampler-addressed taps (SAMPLE_IMAGE carrying `extension`) resolve the UDIM tile
    and material slot here, per the backend sampler contract. With
    `image_texels(path) -> (width, height, read)` they are then sampled by the
    Cycles-transcribed `sample_image_texels`; without it the callback receives the
    tile-LOCAL coordinate. A miss returns the resource's missing colour.
    `triangle_slot` is what ATTR_TRIANGLE_SLOT reads; it defaults to 0, the same
    "no sidecar here" policy ATTR_CORNER_FLOAT follows.
    """
    import math

    if world_to_object is None:
        world_to_object = _identity_affine()
    import struct

    regs: list[tuple[float, float, float, float]] = [(0.0, 0.0, 0.0, 1.0)] * max(
        program.result_reg + 1, 1
    )

    def ensure(dst: int) -> None:
        nonlocal regs
        if dst >= len(regs):
            regs = list(regs) + [(0.0, 0.0, 0.0, 1.0)] * (dst + 1 - len(regs))

    def as_scalar(v: tuple[float, float, float, float]) -> float:
        return _luminance(v)

    def swizzle(v: tuple[float, float, float, float], mode: str) -> tuple[float, float, float, float]:
        r, g, b, a = v
        mode = str(mode or "").upper()
        if mode == "LUMA":
            l = _luminance(v)
            return (l, l, l, 1.0)
        if mode in {"A", "AAA1"}:
            return (a, a, a, 1.0)
        if mode == "RRR1":
            return (r, r, r, 1.0)
        if mode == "GGG1":
            return (g, g, g, 1.0)
        if mode == "BBB1":
            return (b, b, b, 1.0)
        return v

    def rotate_euler_xyz(vec, rot):
        x, y, z = vec
        rx, ry, rz = rot
        cz, sz = math.cos(rz), math.sin(rz)
        x, y = x * cz - y * sz, x * sz + y * cz
        cy, sy = math.cos(ry), math.sin(ry)
        x, z = x * cy + z * sy, -x * sy + z * cy
        cx, sx = math.cos(rx), math.sin(rx)
        y, z = y * cx - z * sx, y * sx + z * cx
        return (x, y, z)

    def sample_at(resource: int, u: float, v: float):
        try:
            return sample_rgba_by_resource(resource, u, v)
        except TypeError:
            return sample_rgba_by_resource(resource)

    def sampler_tap(op, u: float, v: float):
        resource_index = int(op.get("resource", 0))
        resources = list(getattr(program, "resources", None) or ())
        item = resources[resource_index] if 0 <= resource_index < len(resources) else {}
        missing = tuple(float(c) for c in (item.get("missing") or IMAGE_MISSING_RGBA))
        slot_value = None
        slot_register = op.get("slot")
        if type(slot_register) is int and 0 <= slot_register < len(regs):
            slot_value = regs[slot_register][0]
        if item:
            resolved = resolve_sampler_image(item, u, v, slot_value)
        else:
            resolved = ("", float(u), float(v))
        if resolved is None:
            return missing
        path, local_u, local_v = resolved
        if image_texels is None:
            return sample_at(resource_index, local_u, local_v)
        texels = image_texels(path)
        if texels is None:
            return missing
        width, height, read = texels
        return sample_image_texels(
            width, height, read, local_u, local_v,
            extension=str(op.get("extension") or "REPEAT"),
            interpolation=str(op.get("mode") or "LINEAR"),
        )

    def _fade(t: float) -> float:
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)

    def _hash2(ix: int, iy: int) -> int:
        """Cycles ``hash_uint2`` (``intern/cycles/util/hash.h``).

        Bit-identical to ``backend_material_noise.cpp``'s ``hash_uint2`` and to
        ``mir_hash_uint2`` in ``material_ir.slang``, so the Perlin lattice this
        evaluator walks is the same one the GPU and the C++ reference walk.
        """
        seed = (0xDEADBEEF + (2 << 2) + 13) & 0xFFFFFFFF
        a = b = c = seed
        b = _u32(b + iy)
        a = _u32(a + ix)
        return _jenkins_final(a, b, c)[2]

    def _hash3(ix: int, iy: int, iz: int) -> int:
        """Cycles ``hash_uint3`` (``intern/cycles/util/hash.h``)."""
        seed = (0xDEADBEEF + (3 << 2) + 13) & 0xFFFFFFFF
        a = b = c = seed
        c = _u32(c + iz)
        b = _u32(b + iy)
        a = _u32(a + ix)
        return _jenkins_final(a, b, c)[2]

    def _hash1(ix: int) -> int:
        """Cycles ``hash_uint`` -- the 1D Perlin lattice hash."""
        seed = (0xDEADBEEF + (1 << 2) + 13) & 0xFFFFFFFF
        a = b = c = seed
        a = _u32(a + ix)
        return _jenkins_final(a, b, c)[2]

    def _hash4(ix: int, iy: int, iz: int, iw: int) -> int:
        """Cycles ``hash_uint4`` -- the 4D Perlin lattice hash."""
        return _hash_uint4_blender(_u32(ix), _u32(iy), _u32(iz), _u32(iw))

    def _u32(v: int) -> int:
        return int(v) & 0xFFFFFFFF

    def _rot_u32(x: int, k: int) -> int:
        x = _u32(x)
        return _u32((x << k) | (x >> (32 - k)))

    def _jenkins_final(a: int, b: int, c: int) -> tuple[int, int, int]:
        c = _u32(c ^ b); c = _u32(c - _rot_u32(b, 14))
        a = _u32(a ^ c); a = _u32(a - _rot_u32(c, 11))
        b = _u32(b ^ a); b = _u32(b - _rot_u32(a, 25))
        c = _u32(c ^ b); c = _u32(c - _rot_u32(b, 16))
        a = _u32(a ^ c); a = _u32(a - _rot_u32(c, 4))
        b = _u32(b ^ a); b = _u32(b - _rot_u32(a, 14))
        c = _u32(c ^ b); c = _u32(c - _rot_u32(b, 24))
        return a, b, c

    def _jenkins_mix(a: int, b: int, c: int) -> tuple[int, int, int]:
        a = _u32(a - c); a = _u32(a ^ _rot_u32(c, 4)); c = _u32(c + b)
        b = _u32(b - a); b = _u32(b ^ _rot_u32(a, 6)); a = _u32(a + c)
        c = _u32(c - b); c = _u32(c ^ _rot_u32(b, 8)); b = _u32(b + a)
        a = _u32(a - c); a = _u32(a ^ _rot_u32(c, 16)); c = _u32(c + b)
        b = _u32(b - a); b = _u32(b ^ _rot_u32(a, 19)); a = _u32(a + c)
        c = _u32(c - b); c = _u32(c ^ _rot_u32(b, 4)); b = _u32(b + a)
        return a, b, c

    def _hash_uint2_blender(kx: int, ky: int) -> int:
        a = _u32(0xDEADBEEF + (2 << 2) + 13)
        b = a
        c = a
        b = _u32(b + ky)
        a = _u32(a + kx)
        return _jenkins_final(a, b, c)[2]

    def _hash_uint3_blender(kx: int, ky: int, kz: int) -> int:
        a = _u32(0xDEADBEEF + (3 << 2) + 13)
        b = a
        c = a
        c = _u32(c + kz)
        b = _u32(b + ky)
        a = _u32(a + kx)
        return _jenkins_final(a, b, c)[2]

    def _hash_uint4_blender(kx: int, ky: int, kz: int, kw: int) -> int:
        a = _u32(0xDEADBEEF + (4 << 2) + 13)
        b = a
        c = a
        a = _u32(a + kx)
        b = _u32(b + ky)
        c = _u32(c + kz)
        a, b, c = _jenkins_mix(a, b, c)
        a = _u32(a + kw)
        return _jenkins_final(a, b, c)[2]

    def _float_bits(value: float) -> int:
        return struct.unpack("<I", struct.pack("<f", float(value)))[0]

    def _hash_uint_to_unit(value: int) -> float:
        return float(_u32(value)) / float(0xFFFFFFFF)

    def _hash_float_to_float(x: float) -> float:
        a = _u32(0xDEADBEEF + (1 << 2) + 13)
        b = a
        c = a
        a = _u32(a + _float_bits(x))
        return _hash_uint_to_unit(_jenkins_final(a, b, c)[2])

    def _hash_vec2_to_float(x: float, y: float) -> float:
        return _hash_uint_to_unit(_hash_uint2_blender(_float_bits(x), _float_bits(y)))

    def _hash_vec3_to_float(x: float, y: float, z: float) -> float:
        return _hash_uint_to_unit(
            _hash_uint3_blender(_float_bits(x), _float_bits(y), _float_bits(z))
        )

    def _hash_vec4_to_float(x: float, y: float, z: float, w: float) -> float:
        return _hash_uint_to_unit(
            _hash_uint4_blender(_float_bits(x), _float_bits(y), _float_bits(z), _float_bits(w))
        )

    def _gabor_texture(
        p,
        scale: float,
        frequency: float,
        anisotropy: float,
        orientation_2d: float,
        orientation_3d,
        *,
        gabor_type: str,
        output_mode: str,
    ):
        """Cycles svm_node_tex_gabor. 8 impulses per cell over a 3x3 (2D) or
        3x3x3 (3D) neighbourhood, summed as complex phasors."""
        import math

        sx, sy, sz = float(p[0]) * scale, float(p[1]) * scale, float(p[2]) * scale
        isotropy = 1.0 - min(max(float(anisotropy), 0.0), 1.0)
        frequency = max(0.001, float(frequency))
        three_d = str(gabor_type).upper() == "3D"

        def kernel(dist_sq, angle):
            envelope = math.exp(-math.pi * dist_sq) * (0.5 + 0.5 * math.cos(math.pi * dist_sq))
            return (envelope * math.cos(angle), envelope * math.sin(angle))

        sum_x = sum_y = 0.0
        if three_d:
            ox, oy, oz = (float(v) for v in orientation_3d)
            norm = math.sqrt(ox * ox + oy * oy + oz * oz) or 1.0
            ox, oy, oz = ox / norm, oy / norm, oz / norm
            cell = [math.floor(sx), math.floor(sy), math.floor(sz)]
            local = [sx - cell[0], sy - cell[1], sz - cell[2]]
            for k in (-1, 0, 1):
                for j in (-1, 0, 1):
                    for i in (-1, 0, 1):
                        cc = (cell[0] + i, cell[1] + j, cell[2] + k)
                        pos = (local[0] - i, local[1] - j, local[2] - k)
                        for imp in range(8):
                            s0, s1, s2 = imp * 3, imp * 3 + 1, imp * 3 + 2
                            if isotropy == 0.0:
                                dx, dy, dz = ox, oy, oz
                            else:
                                inclination = math.acos(max(-1.0, min(1.0, oz)))
                                planar = math.sqrt(ox * ox + oy * oy)
                                azimuth = (-1.0 if oy < 0.0 else 1.0) * math.acos(
                                    max(-1.0, min(1.0, ox / planar)) if planar else 1.0
                                )
                                ra = _hash_vec4_to_float(cc[0], cc[1], cc[2], s0) * math.pi
                                rb = _hash_vec4_to_float(cc[2], cc[0], s0, cc[1]) * math.pi
                                inclination += ra * isotropy
                                azimuth += rb * isotropy
                                dx = math.sin(inclination) * math.cos(azimuth)
                                dy = math.sin(inclination) * math.sin(azimuth)
                                dz = math.cos(inclination)
                            cx = _hash_vec4_to_float(cc[0], cc[1], cc[2], s1)
                            cy = _hash_vec4_to_float(cc[2], cc[0], s1, cc[1])
                            cz = _hash_vec4_to_float(s1, cc[2], cc[1], cc[0])
                            qx, qy, qz = pos[0] - cx, pos[1] - cy, pos[2] - cz
                            dist_sq = qx * qx + qy * qy + qz * qz
                            if dist_sq >= 1.0:
                                continue
                            weight = -1.0 if _hash_vec4_to_float(cc[0], cc[1], cc[2], s2) < 0.5 else 1.0
                            angle = 2.0 * math.pi * frequency * (qx * dx + qy * dy + qz * dz)
                            kx, ky = kernel(dist_sq, angle)
                            sum_x += weight * kx
                            sum_y += weight * ky
            std_dev = math.sqrt(8 * 0.5 * (1.0 / (4.0 * math.sqrt(2.0))))
        else:
            cell = [math.floor(sx), math.floor(sy)]
            local = [sx - cell[0], sy - cell[1]]
            for j in (-1, 0, 1):
                for i in (-1, 0, 1):
                    cc = (cell[0] + i, cell[1] + j)
                    pos = (local[0] - i, local[1] - j)
                    for imp in range(8):
                        s0, s1, s2 = imp * 3, imp * 3 + 1, imp * 3 + 2
                        rand_o = (_hash_vec3_to_float(cc[0], cc[1], s0) - 0.5) * math.pi
                        angle_o = float(orientation_2d) + rand_o * isotropy
                        cx = _hash_vec3_to_float(cc[0], cc[1], s1)
                        cy = _hash_vec3_to_float(s1, cc[0], cc[1])
                        qx, qy = pos[0] - cx, pos[1] - cy
                        dist_sq = qx * qx + qy * qy
                        if dist_sq >= 1.0:
                            continue
                        weight = -1.0 if _hash_vec3_to_float(cc[0], cc[1], s2) < 0.5 else 1.0
                        fx = frequency * math.cos(angle_o)
                        fy = frequency * math.sin(angle_o)
                        angle = 2.0 * math.pi * (qx * fx + qy * fy)
                        kx, ky = kernel(dist_sq, angle)
                        sum_x += weight * kx
                        sum_y += weight * ky
            std_dev = math.sqrt(8 * 0.5 * 0.25)

        norm_factor = 6.0 * std_dev
        mode = str(output_mode).upper()
        if mode == "PHASE":
            value = (math.atan2(sum_y, sum_x) + math.pi) / (2.0 * math.pi)
        elif mode == "INTENSITY":
            value = math.sqrt(sum_x * sum_x + sum_y * sum_y) / norm_factor
        else:
            value = (sum_y / norm_factor) * 0.5 + 0.5
        return (value, value, value, 1.0)

    def _white_noise_texture(p, w: float, *, dimensions: str, want_color: bool):
        x, y, z = float(p[0]), float(p[1]), float(p[2])
        w = float(w)
        dims = str(dimensions or "3D").upper()
        if dims == "1D":
            value = _hash_float_to_float(w)
            if not want_color:
                return (value, value, value, 1.0)
            return (
                value,
                _hash_vec2_to_float(w, 1.0),
                _hash_vec2_to_float(w, 2.0),
                1.0,
            )
        if dims == "4D":
            value = _hash_vec4_to_float(x, y, z, w)
            if not want_color:
                return (value, value, value, 1.0)
            return (
                value,
                _hash_vec4_to_float(z, x, w, y),
                _hash_vec4_to_float(w, z, y, x),
                1.0,
            )
        if dims == "3D":
            value = _hash_vec3_to_float(x, y, z)
            if not want_color:
                return (value, value, value, 1.0)
            return (
                value,
                _hash_vec4_to_float(x, y, z, 1.0),
                _hash_vec4_to_float(x, y, z, 2.0),
                1.0,
            )
        value = _hash_vec2_to_float(x, y)
        if not want_color:
            return (value, value, value, 1.0)
        return (
            value,
            _hash_vec3_to_float(x, y, 1.0),
            _hash_vec3_to_float(x, y, 2.0),
            1.0,
        )

    def _magic_texture(p, scale: float, distortion: float, depth: int, want_color: bool):
        x0, y0, z0 = float(p[0]), float(p[1]), float(p[2])
        two_pi = 2.0 * math.pi
        px = (x0 * scale) % two_pi
        py = (y0 * scale) % two_pi
        pz = (z0 * scale) % two_pi
        x = math.sin((px + py + pz) * 5.0)
        y = math.cos((-px + py - pz) * 5.0)
        z = -math.cos((-px - py + pz) * 5.0)
        depth = max(0, min(int(depth), 10))
        if depth > 0:
            x *= distortion
            y *= distortion
            z *= distortion
            y = -math.cos(x - y + z)
            y *= distortion
            if depth > 1:
                x = math.cos(x - y - z)
                x *= distortion
                if depth > 2:
                    z = math.sin(-x - y - z)
                    z *= distortion
                    if depth > 3:
                        x = -math.cos(-x + y - z)
                        x *= distortion
                        if depth > 4:
                            y = -math.sin(-x + y + z)
                            y *= distortion
                            if depth > 5:
                                y = -math.cos(-x + y + z)
                                y *= distortion
                                if depth > 6:
                                    x = math.cos(x + y + z)
                                    x *= distortion
                                    if depth > 7:
                                        z = math.sin(x + y - z)
                                        z *= distortion
                                        if depth > 8:
                                            x = -math.cos(-x - y + z)
                                            x *= distortion
                                            if depth > 9:
                                                y = -math.sin(x - y + z)
                                                y *= distortion
        if distortion != 0.0:
            inv = 1.0 / (distortion * 2.0)
            x *= inv
            y *= inv
            z *= inv
        color = (0.5 - x, 0.5 - y, 0.5 - z, 1.0)
        if want_color:
            return color
        fac = (color[0] + color[1] + color[2]) / 3.0
        return (fac, fac, fac, 1.0)

    def _grad2(h: int, x: float, y: float) -> float:
        h &= 7
        u = x if h < 4 else y
        v = 2.0 * (y if h < 4 else x)
        return (-u if h & 1 else u) + (-v if h & 2 else v)

    def _grad3(h: int, x: float, y: float, z: float) -> float:
        h &= 15
        u = x if h < 8 else y
        vt = x if h in (12, 14) else z
        v = y if h < 4 else vt
        return (-u if h & 1 else u) + (-v if h & 2 else v)

    def _grad1(h: int, x: float) -> float:
        h &= 15
        g = 1.0 + float(h & 7)
        return (-g if h & 8 else g) * x

    def _grad4(h: int, x: float, y: float, z: float, w: float) -> float:
        h &= 31
        u = x if h < 24 else y
        v = y if h < 16 else z
        s = z if h < 8 else w
        return (
            (-u if h & 1 else u) + (-v if h & 2 else v) + (-s if h & 4 else s)
        )

    def _wrap_period(v: float) -> float:
        """``wrap_period`` from ``backend_material_noise.cpp`` / ``mir_wrap_period``."""
        correction = 0.5 if abs(v) >= 1000000.0 else 0.0
        return math.fmod(v, 100000.0) + correction

    def _perlin2(x: float, y: float) -> float:
        # Signed Perlin, i.e. the C++ snoise_2d (wrap + 0.6616 remap) end to end.
        x = _wrap_period(x)
        y = _wrap_period(y)
        X = math.floor(x)
        Y = math.floor(y)
        fx = x - X
        fy = y - Y
        u = _fade(fx)
        v = _fade(fy)
        ix = int(X)
        iy = int(Y)
        n00 = _grad2(_hash2(ix, iy), fx, fy)
        n10 = _grad2(_hash2(ix + 1, iy), fx - 1.0, fy)
        n01 = _grad2(_hash2(ix, iy + 1), fx, fy - 1.0)
        n11 = _grad2(_hash2(ix + 1, iy + 1), fx - 1.0, fy - 1.0)
        nx0 = n00 * (1.0 - u) + n10 * u
        nx1 = n01 * (1.0 - u) + n11 * u
        return 0.6616 * (nx0 * (1.0 - v) + nx1 * v)

    def _perlin3(x: float, y: float, z: float) -> float:
        # Signed Perlin, i.e. the C++ snoise_3d (wrap + 0.9820 remap) end to end.
        x = _wrap_period(x)
        y = _wrap_period(y)
        z = _wrap_period(z)
        X = math.floor(x)
        Y = math.floor(y)
        Z = math.floor(z)
        fx = x - X
        fy = y - Y
        fz = z - Z
        u = _fade(fx)
        v = _fade(fy)
        w = _fade(fz)
        ix = int(X)
        iy = int(Y)
        iz = int(Z)

        def g(dx, dy, dz, ox, oy, oz):
            return _grad3(_hash3(ix + ox, iy + oy, iz + oz), fx + dx, fy + dy, fz + dz)

        n000 = g(0, 0, 0, 0, 0, 0)
        n100 = g(-1, 0, 0, 1, 0, 0)
        n010 = g(0, -1, 0, 0, 1, 0)
        n110 = g(-1, -1, 0, 1, 1, 0)
        n001 = g(0, 0, -1, 0, 0, 1)
        n101 = g(-1, 0, -1, 1, 0, 1)
        n011 = g(0, -1, -1, 0, 1, 1)
        n111 = g(-1, -1, -1, 1, 1, 1)
        nx00 = n000 * (1.0 - u) + n100 * u
        nx10 = n010 * (1.0 - u) + n110 * u
        nx01 = n001 * (1.0 - u) + n101 * u
        nx11 = n011 * (1.0 - u) + n111 * u
        nxy0 = nx00 * (1.0 - v) + nx10 * v
        nxy1 = nx01 * (1.0 - v) + nx11 * v
        return 0.9820 * (nxy0 * (1.0 - w) + nxy1 * w)

    def _perlin1(x: float) -> float:
        # Signed Perlin, i.e. the C++ snoise_1d (wrap + 0.2500 remap) end to end.
        x = _wrap_period(x)
        X = math.floor(x)
        fx = x - X
        u = _fade(fx)
        ix = int(X)
        n0 = _grad1(_hash1(ix), fx)
        n1 = _grad1(_hash1(ix + 1), fx - 1.0)
        return 0.2500 * (n0 * (1.0 - u) + n1 * u)

    def _perlin4(x: float, y: float, z: float, w: float) -> float:
        # Signed Perlin, i.e. the C++ snoise_4d (wrap + 0.8344 remap) end to end.
        x = _wrap_period(x)
        y = _wrap_period(y)
        z = _wrap_period(z)
        w = _wrap_period(w)
        X = math.floor(x)
        Y = math.floor(y)
        Z = math.floor(z)
        W = math.floor(w)
        fx = x - X
        fy = y - Y
        fz = z - Z
        fw = w - W
        u = _fade(fx)
        v = _fade(fy)
        t = _fade(fz)
        s = _fade(fw)
        ix = int(X)
        iy = int(Y)
        iz = int(Z)
        iw = int(W)

        def g(ox, oy, oz, ow):
            return _grad4(
                _hash4(ix + ox, iy + oy, iz + oz, iw + ow),
                fx - ox,
                fy - oy,
                fz - oz,
                fw - ow,
            )

        def tri(ow):
            n000 = g(0, 0, 0, ow)
            n100 = g(1, 0, 0, ow)
            n010 = g(0, 1, 0, ow)
            n110 = g(1, 1, 0, ow)
            n001 = g(0, 0, 1, ow)
            n101 = g(1, 0, 1, ow)
            n011 = g(0, 1, 1, ow)
            n111 = g(1, 1, 1, ow)
            x1 = 1.0 - u
            y1 = 1.0 - v
            z1 = 1.0 - t
            return z1 * (y1 * (n000 * x1 + n100 * u) + v * (n010 * x1 + n110 * u)) + t * (
                y1 * (n001 * x1 + n101 * u) + v * (n011 * x1 + n111 * u)
            )

        lo = tri(0)
        hi = tri(1)
        return 0.8344 * (lo * (1.0 - s) + hi * s)

    def _fbm(sample, p, detail: float, roughness: float, lacunarity: float = 2.0, normalize: bool = True):
        detail = max(0.0, min(float(detail), 15.0))
        roughness = max(float(roughness), 0.0)
        fscale = 1.0
        amp = 1.0
        maxamp = 0.0
        total = 0.0
        octaves = int(math.floor(detail))
        for _ in range(octaves + 1):
            total += sample(tuple(c * fscale for c in p)) * amp
            maxamp += amp
            amp *= roughness
            fscale *= lacunarity
        rmd = detail - math.floor(detail)
        if rmd != 0.0:
            total2 = total + sample(tuple(c * fscale for c in p)) * amp
            if normalize:
                a = 0.5 * total / maxamp + 0.5
                b = 0.5 * total2 / (maxamp + amp) + 0.5
                return a * (1.0 - rmd) + b * rmd
            return total * (1.0 - rmd) + total2 * rmd
        return (0.5 * total / maxamp + 0.5) if normalize else total

    def _noise_texture(
        p,
        scale,
        detail,
        roughness,
        distortion,
        is_3d: bool,
        want_color: bool,
        lacunarity: float = 2.0,
        normalize: bool = True,
        dimensions: str = "",
        w: float = 0.0,
    ):
        # Cycles scales the coordinate FIRST (svm_node_tex_noise: ``vector *= scale``)
        # and only then adds the seeded offsets -- noise_texture_2d / noise_texture_3d.
        dimensions = str(dimensions or ("3D" if is_3d else "2D")).upper()
        if dimensions == "1D":
            # noise_texture_1d reads the node's W input as the ONLY coordinate; the
            # Vector socket is ignored. Its seeds come from random_float_offset,
            # which uses the one-word hash -- hence its own table.
            off = NOISE_SEED_OFFSET_1D
            q = w * scale
            if distortion != 0.0:
                q = q + _perlin1(q + off[0]) * distortion
            fac = _fbm(lambda c: _perlin1(c[0]), (q,), detail, roughness, lacunarity, normalize)
            if not want_color:
                return (fac, fac, fac, 1.0)
            g = _fbm(
                lambda c: _perlin1(c[0]), (q + off[1],), detail, roughness, lacunarity, normalize
            )
            b = _fbm(
                lambda c: _perlin1(c[0]), (q + off[2],), detail, roughness, lacunarity, normalize
            )
            return (fac, g, b, 1.0)
        if dimensions == "4D":
            off = NOISE_SEED_OFFSET_4D
            q = [p[0] * scale, p[1] * scale, p[2] * scale, w * scale]
            if distortion != 0.0:
                base = list(q)
                q = [
                    base[axis]
                    + _perlin4(
                        base[0] + off[axis][0],
                        base[1] + off[axis][1],
                        base[2] + off[axis][2],
                        base[3] + off[axis][3],
                    )
                    * distortion
                    for axis in range(4)
                ]
            fac = _fbm(lambda c: _perlin4(*c), q, detail, roughness, lacunarity, normalize)
            if not want_color:
                return (fac, fac, fac, 1.0)
            g = _fbm(
                lambda c: _perlin4(*c),
                [q[axis] + off[4][axis] for axis in range(4)],
                detail,
                roughness,
                lacunarity,
                normalize,
            )
            b = _fbm(
                lambda c: _perlin4(*c),
                [q[axis] + off[5][axis] for axis in range(4)],
                detail,
                roughness,
                lacunarity,
                normalize,
            )
            return (fac, g, b, 1.0)
        if is_3d:
            off = NOISE_SEED_OFFSET_3D
            q = [p[0] * scale, p[1] * scale, p[2] * scale]
            if distortion != 0.0:
                # p += float3(snoise_3d(p + off(0)) * d, snoise_3d(p + off(1)) * d,
                #             snoise_3d(p + off(2)) * d): every component reads the
                # undistorted point.
                base = list(q)
                q = [
                    base[axis]
                    + _perlin3(
                        base[0] + off[axis][0],
                        base[1] + off[axis][1],
                        base[2] + off[axis][2],
                    )
                    * distortion
                    for axis in range(3)
                ]
            fac = _fbm(lambda c: _perlin3(*c), q, detail, roughness, lacunarity, normalize)
            if not want_color:
                return (fac, fac, fac, 1.0)
            g = _fbm(
                lambda c: _perlin3(*c),
                [q[0] + off[3][0], q[1] + off[3][1], q[2] + off[3][2]],
                detail,
                roughness,
                lacunarity,
                normalize,
            )
            b = _fbm(
                lambda c: _perlin3(*c),
                [q[0] + off[4][0], q[1] + off[4][1], q[2] + off[4][2]],
                detail,
                roughness,
                lacunarity,
                normalize,
            )
            return (fac, g, b, 1.0)
        off = NOISE_SEED_OFFSET_2D
        q = [p[0] * scale, p[1] * scale]
        if distortion != 0.0:
            base = list(q)
            q = [
                base[axis]
                + _perlin2(base[0] + off[axis][0], base[1] + off[axis][1]) * distortion
                for axis in range(2)
            ]
        fac = _fbm(lambda c: _perlin2(*c), q, detail, roughness, lacunarity, normalize)
        if not want_color:
            return (fac, fac, fac, 1.0)
        g = _fbm(
            lambda c: _perlin2(*c),
            [q[0] + off[2][0], q[1] + off[2][1]],
            detail,
            roughness,
            lacunarity,
            normalize,
        )
        b = _fbm(
            lambda c: _perlin2(*c),
            [q[0] + off[3][0], q[1] + off[3][1]],
            detail,
            roughness,
            lacunarity,
            normalize,
        )
        return (fac, g, b, 1.0)

    def _smooth_min(a: float, b: float, k: float) -> float:
        if k == 0.0:
            return min(a, b)
        h = max(k - abs(a - b), 0.0) / k
        return min(a, b) - h * h * h * k * (1.0 / 6.0)

    def _wrap(value: float, upper: float, lower: float) -> float:
        span = upper - lower
        return value - span * math.floor((value - lower) / span) if span != 0.0 else lower

    def _pingpong(a: float, b: float) -> float:
        if b == 0.0:
            return 0.0
        scaled = (a - b) / (b * 2.0)
        return abs((scaled - math.floor(scaled)) * b * 2.0 - b)

    def _rgb_to_hsv(r: float, g: float, b: float) -> tuple[float, float, float]:
        cmax = max(r, g, b)
        cmin = min(r, g, b)
        delta = cmax - cmin
        if delta < 1e-8:
            h = 0.0
        elif cmax == r:
            h = ((g - b) / delta) % 6.0
        elif cmax == g:
            h = ((b - r) / delta) + 2.0
        else:
            h = ((r - g) / delta) + 4.0
        h /= 6.0
        if h < 0.0:
            h += 1.0
        s = 0.0 if cmax < 1e-8 else delta / cmax
        return (h, s, cmax)

    def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[float, float, float]:
        h = h - math.floor(h)
        i = int(math.floor(h * 6.0))
        f = h * 6.0 - i
        p = v * (1.0 - s)
        q = v * (1.0 - f * s)
        t = v * (1.0 - (1.0 - f) * s)
        i = i % 6
        if i == 0:
            return (v, t, p)
        if i == 1:
            return (q, v, p)
        if i == 2:
            return (p, v, t)
        if i == 3:
            return (p, q, v)
        if i == 4:
            return (t, p, v)
        return (v, p, q)

    def _rgb_to_hsl(r: float, g: float, b: float) -> tuple[float, float, float]:
        # intern/cycles/util/color.h, rgb_to_hsl.
        cmax = max(r, g, b)
        cmin = min(r, g, b)
        lightness = min(1.0, (cmax + cmin) / 2.0)
        h = 0.0
        s = 0.0
        if cmax != cmin:
            delta = cmax - cmin
            s = delta / (2.0 - cmax - cmin) if lightness > 0.5 else delta / (cmax + cmin)
            if cmax == r:
                h = (g - b) / delta + (6.0 if g < b else 0.0)
            elif cmax == g:
                h = (b - r) / delta + 2.0
            else:
                h = (r - g) / delta + 4.0
        h /= 6.0
        return (h, s, lightness)

    def _hsl_to_rgb(h: float, s: float, lightness: float) -> tuple[float, float, float]:
        # intern/cycles/util/color.h, hsl_to_rgb. Cycles is only ever handed a hue
        # already wrapped into [0, 1) (Blender HUE_MODs before calling), and the
        # triangle-wave below gives nonsense outside it -- a hue of -0.5 reads as
        # red instead of cyan. The Color Ramp's unwrapped hue can be any real, so
        # wrap here the way hsv_to_rgb already does.
        h = h - math.floor(h)
        nr = abs(h * 6.0 - 3.0) - 1.0
        ng = 2.0 - abs(h * 6.0 - 2.0)
        nb = 2.0 - abs(h * 6.0 - 4.0)
        nr = min(1.0, max(0.0, nr))
        ng = min(1.0, max(0.0, ng))
        nb = min(1.0, max(0.0, nb))
        chroma = (1.0 - abs(2.0 * lightness - 1.0)) * s
        return (
            (nr - 0.5) * chroma + lightness,
            (ng - 0.5) * chroma + lightness,
            (nb - 0.5) * chroma + lightness,
        )

    def _ramp_blend(blend: str, base, layer, fac: float):
        """Blender's ``ramp_blend`` (blenkernel/material.cc), channel-exact.

        ``fac`` is folded into each mode the way Blender folds it — several modes
        (Lighten, Dodge, Burn, Linear Light) are *not* a plain lerp of an
        unweighted result, so this cannot be factored into blend-then-lerp.
        """
        facm = 1.0 - fac
        ar, ag, ab = float(base[0]), float(base[1]), float(base[2])
        br, bg, bb = float(layer[0]), float(layer[1]), float(layer[2])

        def per_channel(fn):
            return (fn(ar, br), fn(ag, bg), fn(ab, bb))

        if blend == "MIX":
            return per_channel(lambda x, y: facm * x + fac * y)
        if blend == "ADD":
            return per_channel(lambda x, y: x + fac * y)
        if blend == "MULTIPLY":
            return per_channel(lambda x, y: x * (facm + fac * y))
        if blend == "SCREEN":
            return per_channel(lambda x, y: 1.0 - (facm + fac * (1.0 - y)) * (1.0 - x))
        if blend == "OVERLAY":
            def _ov(x, y):
                if x < 0.5:
                    return x * (facm + 2.0 * fac * y)
                return 1.0 - (facm + 2.0 * fac * (1.0 - y)) * (1.0 - x)

            return per_channel(_ov)
        if blend == "SUBTRACT":
            return per_channel(lambda x, y: x - fac * y)
        if blend == "DIVIDE":
            return per_channel(lambda x, y: (facm * x + fac * x / y) if y != 0.0 else x)
        if blend == "DIFFERENCE":
            return per_channel(lambda x, y: facm * x + fac * abs(x - y))
        if blend == "EXCLUSION":
            return per_channel(
                lambda x, y: max(facm * x + fac * (x + y - 2.0 * x * y), 0.0)
            )
        if blend == "DARKEN":
            return per_channel(lambda x, y: min(x, y) * fac + x * facm)
        if blend == "LIGHTEN":
            # Cycles svm_mix_light: lerp toward the lighter channel. Equals
            # max(x, facm*x + fac*y) while fac is in 0-1, but an unclamped factor
            # (Clamp Factor off) steps outside that range and only this form
            # follows Cycles there (measured, tests/blender_material_ir_cycles_oracle).
            return per_channel(lambda x, y: max(x, y) * fac + x * facm)
        if blend == "DODGE":
            def _dodge(x, y):
                if x == 0.0:
                    return x
                tmp = 1.0 - fac * y
                if tmp <= 0.0:
                    return 1.0
                tmp = x / tmp
                return 1.0 if tmp > 1.0 else tmp

            return per_channel(_dodge)
        if blend == "BURN":
            def _burn(x, y):
                tmp = facm + fac * y
                if tmp <= 0.0:
                    return 0.0
                tmp = 1.0 - (1.0 - x) / tmp
                if tmp < 0.0:
                    return 0.0
                return 1.0 if tmp > 1.0 else tmp

            return per_channel(_burn)
        if blend == "SOFT_LIGHT":
            def _soft(x, y):
                screen = 1.0 - (1.0 - y) * (1.0 - x)
                return facm * x + fac * ((1.0 - x) * y * x + x * screen)

            return per_channel(_soft)
        if blend == "LINEAR_LIGHT":
            def _linear(x, y):
                if y > 0.5:
                    return x + fac * (2.0 * (y - 0.5))
                return x + fac * (2.0 * y - 1.0)

            return per_channel(_linear)
        if blend == "HUE":
            bh, bs, bv = _rgb_to_hsv(br, bg, bb)
            if bs == 0.0:
                return (ar, ag, ab)
            _ah, a_s, av = _rgb_to_hsv(ar, ag, ab)
            tr, tg, tb = _hsv_to_rgb(bh, a_s, av)
            return (facm * ar + fac * tr, facm * ag + fac * tg, facm * ab + fac * tb)
        if blend == "SATURATION":
            ah, a_s, av = _rgb_to_hsv(ar, ag, ab)
            if a_s == 0.0:
                return (ar, ag, ab)
            _bh, bs, _bv = _rgb_to_hsv(br, bg, bb)
            return _hsv_to_rgb(ah, facm * a_s + fac * bs, av)
        if blend == "VALUE":
            ah, a_s, av = _rgb_to_hsv(ar, ag, ab)
            _bh, _bs, bv = _rgb_to_hsv(br, bg, bb)
            return _hsv_to_rgb(ah, a_s, facm * av + fac * bv)
        if blend == "COLOR":
            bh, bs, _bv = _rgb_to_hsv(br, bg, bb)
            if bs == 0.0:
                return (ar, ag, ab)
            _ah, _as, av = _rgb_to_hsv(ar, ag, ab)
            tr, tg, tb = _hsv_to_rgb(bh, bs, av)
            return (facm * ar + fac * tr, facm * ag + fac * tg, facm * ab + fac * tb)
        return (ar, ag, ab)

    for op in program.ops:
        opcode = str(op.get("op") or "")
        dst = int(op.get("dst", 0))
        ensure(dst)
        if opcode == OPCODE_CONSTANT:
            val = op.get("value") or [0, 0, 0, 1]
            regs[dst] = (
                float(val[0]),
                float(val[1]),
                float(val[2]),
                float(val[3]) if len(val) > 3 else 1.0,
            )
        elif opcode == OPCODE_ATTR_UV:
            regs[dst] = (float(uv[0]), float(uv[1]), 0.0, 1.0)
        elif opcode == OPCODE_ATTR_OBJECT:
            regs[dst] = (
                float(object_position[0]),
                float(object_position[1]),
                float(object_position[2]),
                1.0,
            )
        elif opcode == OPCODE_ATTR_GENERATED:
            regs[dst] = (
                float(generated_position[0]),
                float(generated_position[1]),
                float(generated_position[2]),
                1.0,
            )
        elif opcode == OPCODE_ATTR_POSITION:
            regs[dst] = (
                float(world_position[0]),
                float(world_position[1]),
                float(world_position[2]),
                1.0,
            )
        elif opcode == OPCODE_TANGENT_TO_WORLD:
            # Mirrors kMirOpTangentToWorld in backend/shaders/material_ir.slang,
            # including that the bitangent is RECONSTRUCTED from N x T with the
            # handedness of the supplied one -- Cycles builds the frame it transforms
            # through the same way (svm_node_normal_map), and an independently
            # interpolated bitangent is not perpendicular to N.
            tsv = regs[int(op["fac"])]
            n = (float(world_normal[0]), float(world_normal[1]), float(world_normal[2]))
            raw_t = (float(tangent[0]), float(tangent[1]), float(tangent[2]))
            # Gram-Schmidt, as the shader does: the interpolated tangent leans out of
            # the tangent plane, and _encode_world_normal_as_tangent inverts this op
            # with a TRANSPOSE, which is the inverse only for an orthonormal basis.
            along = sum(n[i] * raw_t[i] for i in range(3))
            projected = tuple(raw_t[i] - n[i] * along for i in range(3))
            t_len = math.sqrt(sum(c * c for c in projected))
            tan = tuple(c / t_len for c in projected) if t_len > 1e-8 else raw_t
            cross = (
                n[1] * tan[2] - n[2] * tan[1],
                n[2] * tan[0] - n[0] * tan[2],
                n[0] * tan[1] - n[1] * tan[0],
            )
            handed = sum(cross[i] * float(bitangent[i]) for i in range(3))
            bit = cross if handed >= 0.0 else tuple(-c for c in cross)
            combined = tuple(
                tan[i] * tsv[0] + bit[i] * tsv[1] + n[i] * tsv[2] for i in range(3)
            )
            length = math.sqrt(sum(c * c for c in combined))
            if length > 1e-20:
                combined = tuple(c / length for c in combined)
            regs[dst] = (combined[0], combined[1], combined[2], 1.0)
        elif opcode == OPCODE_ATTR_NORMAL:
            regs[dst] = (
                float(world_normal[0]),
                float(world_normal[1]),
                float(world_normal[2]),
                1.0,
            )
        elif opcode == OPCODE_ATTR_BARYCENTRIC:
            regs[dst] = (
                float(high_barycentric[0]),
                float(high_barycentric[1]),
                float(high_barycentric[2]),
                1.0,
            )
        elif opcode == OPCODE_ATTR_CORNER_FLOAT:
            # Sidecar corner attributes need the hit triangle + barycentric + the
            # packed sidecar, none of which the reference carries. Engine-gated.
            regs[dst] = (0.0, 0.0, 0.0, 1.0)
        elif opcode == OPCODE_ATTR_TRIANGLE_SLOT:
            # Same policy: no hit triangle here, so the caller says which slot.
            slot = float(triangle_slot)
            regs[dst] = (slot, slot, slot, 1.0)
        elif opcode == OPCODE_ATTR_TRUE_NORMAL:
            regs[dst] = (
                float(true_normal[0]),
                float(true_normal[1]),
                float(true_normal[2]),
                1.0,
            )
        elif opcode == OPCODE_AO:
            # GPU-only opcode. There is no scene or BVH in this evaluator (nor in
            # the backend's own CPU interpreter, evaluate_material_ir), so both
            # return kMirRayOpNeutralValue = 1.0 = fully unoccluded — the same
            # value Cycles yields with __SHADER_RAYTRACE__ off. Parity for AO is
            # gated engine-vs-engine on GPU, like ATTR_BARYCENTRIC /
            # ATTR_TRUE_NORMAL / ATTR_CORNER_FLOAT
            # (docs/SECONDARY_RAY_NODES_PLAN.md sections 2.6 and 10.6). Building a second,
            # differently-wrong ray estimator here would produce noise, not signal.
            regs[dst] = (1.0, 1.0, 1.0, 1.0)
        elif opcode == OPCODE_BEVEL:
            # GPU-only opcode, same policy as AO above — but the neutral DIFFERS.
            # Bevel's result is a world-space normal, so "as if the node were not in
            # the graph" is the SHADING NORMAL, not white. That is Cycles' own value
            # with __SHADER_RAYTRACE__ off (svm_node_bevel seeds bevel_N = sd->N and
            # the whole body, delta preserve included, sits inside the RAYTRACE
            # feature block), and it is what the backend CPU reference returns
            # (backend_bake_maps.cpp) and what the shader's #else branch writes
            # (docs/SECONDARY_RAY_NODES_PLAN.md section 11.5). Read from the same
            # context field ATTR_NORMAL uses, so the two agree by construction.
            regs[dst] = (
                float(world_normal[0]),
                float(world_normal[1]),
                float(world_normal[2]),
                1.0,
            )
        elif opcode == OPCODE_RAYCAST:
            # GPU-only opcode, same policy as AO / BEVEL above. Raycast needed no
            # neutral to be *chosen*: its neutral IS its documented MISS, because
            # svm_node_raycast initialises the outputs before the RAYTRACE feature
            # block and overwrites them only on a hit
            # (docs/SECONDARY_RAY_NODES_PLAN.md section 12.3):
            #   Is Hit        0.0
            #   Hit Position  (0,0,0)   -- world origin, NOT the input position
            #   Hit Normal    (0,0,0)
            #   Hit Distance  the INPUT Length, NOT 0 and not infinity
            # That last one makes this the only neutral of the three that is not a
            # constant, so the Length operand has to be decoded even here -- the
            # backend's #else branch and CPU reference both do the same.
            if "distance_reg" in op:
                miss_distance = as_scalar(regs[int(op["distance_reg"])])
            else:
                miss_distance = float(op.get("distance", 1.0))
            regs[dst] = (0.0, 0.0, 0.0, 0.0)
            dst2 = op.get("dst2")
            if type(dst2) is int and dst2 >= 0:
                ensure(dst2)
                regs[dst2] = (0.0, 0.0, 0.0, float(miss_distance))
        elif opcode == OPCODE_MAPPING:
            src = regs[int(op["src"])]
            if "loc_reg" in op:
                loc = regs[int(op["loc_reg"])]
                rot = regs[int(op["rot_reg"])]
                scale = regs[int(op["scale_reg"])]
                loc = (float(loc[0]), float(loc[1]), float(loc[2]))
                rot = (float(rot[0]), float(rot[1]), float(rot[2]))
                scale = (float(scale[0]), float(scale[1]), float(scale[2]))
            else:
                loc = op.get("loc") or [0, 0, 0]
                rot = op.get("rot") or [0, 0, 0]
                scale = op.get("scale") or [1, 1, 1]
                loc = (float(loc[0]), float(loc[1]), float(loc[2]))
                rot = (float(rot[0]), float(rot[1]), float(rot[2]))
                scale = (float(scale[0]), float(scale[1]), float(scale[2]))
            vtype = str(op.get("vector_type") or "POINT").upper()
            if vtype == "TEXTURE":
                vec = (src[0] - loc[0], src[1] - loc[1], src[2] - loc[2])
                vec = rotate_euler_xyz(vec, (-rot[0], -rot[1], -rot[2]))
                sx, sy, sz = scale
                vec = (
                    vec[0] / sx if abs(sx) > 1e-12 else 0.0,
                    vec[1] / sy if abs(sy) > 1e-12 else 0.0,
                    vec[2] / sz if abs(sz) > 1e-12 else 0.0,
                )
            else:
                vec = (src[0] * scale[0], src[1] * scale[1], src[2] * scale[2])
                vec = rotate_euler_xyz(vec, rot)
                if vtype == "POINT":
                    vec = (vec[0] + loc[0], vec[1] + loc[1], vec[2] + loc[2])
                if vtype == "NORMAL":
                    length = math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2) or 1.0
                    vec = (vec[0] / length, vec[1] / length, vec[2] / length)
            regs[dst] = (vec[0], vec[1], vec[2], 1.0)
        elif opcode == OPCODE_NOISE_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            scale = as_scalar(regs[int(op.get("scale", 0))])
            detail = as_scalar(regs[int(op.get("detail", 0))])
            roughness = as_scalar(regs[int(op.get("roughness", 0))])
            distortion = as_scalar(regs[int(op.get("distortion", 0))])
            lacunarity = (
                as_scalar(regs[int(op["lacunarity"])]) if "lacunarity" in op else 2.0
            )
            normalize = bool(op.get("normalize", True))
            dims = str(op.get("dimensions") or "3D").upper()
            w_reg = int(op.get("w", -1)) if "w" in op else -1
            noise_w = as_scalar(regs[w_reg]) if 0 <= w_reg < len(regs) else 0.0
            output_mode = str(op.get("output") or "FAC").upper()
            regs[dst] = _noise_texture(
                (float(c[0]), float(c[1]), float(c[2])),
                scale,
                detail,
                roughness,
                distortion,
                is_3d=(dims not in {"1D", "2D"}),
                want_color=(output_mode == "COLOR"),
                lacunarity=lacunarity,
                normalize=normalize,
                dimensions=dims,
                w=noise_w,
            )
        elif opcode == OPCODE_VORONOI_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            scale = as_scalar(regs[int(op.get("scale", 0))])
            randomness = as_scalar(regs[int(op.get("randomness", 0))]) if "randomness" in op else 1.0
            dims = str(op.get("dimensions") or "3D").upper()
            output_mode = str(op.get("output") or "DISTANCE").upper()
            feature = str(op.get("feature") or "F1").upper()
            # Lightweight reference: cell hash distance (not Blender-identical).
            px = float(c[0]) * scale
            py = float(c[1]) * scale
            pz = float(c[2]) * scale if dims != "2D" else 0.0
            cell_x = math.floor(px)
            cell_y = math.floor(py)
            cell_z = math.floor(pz)

            def _h2(ix: int, iy: int) -> tuple[float, float]:
                n = ((ix * 374761393) ^ (iy * 668265263)) & 0x7FFFFFFF
                n2 = ((ix * 1274126177) ^ (iy * 2246822519)) & 0x7FFFFFFF
                return (n / 0x7FFFFFFF, n2 / 0x7FFFFFFF)

            def _h3(ix: int, iy: int, iz: int) -> tuple[float, float, float]:
                n = ((ix * 374761393) ^ (iy * 668265263) ^ (iz * 2147483647)) & 0x7FFFFFFF
                n2 = ((ix * 1274126177) ^ (iy * 2246822519) ^ (iz * 3266489917)) & 0x7FFFFFFF
                n3 = ((ix * 1444728091) ^ (iy * 2654435761) ^ (iz * 1597334677)) & 0x7FFFFFFF
                return (n / 0x7FFFFFFF, n2 / 0x7FFFFFFF, n3 / 0x7FFFFFFF)

            best = 1e9
            best_color = (0.0, 0.0, 0.0)
            local = (px - cell_x, py - cell_y, pz - cell_z)
            if dims == "2D":
                for j in range(-1, 2):
                    for i in range(-1, 2):
                        hx, hy = _h2(int(cell_x) + i, int(cell_y) + j)
                        point = (i + hx * randomness, j + hy * randomness)
                        d = math.hypot(point[0] - local[0], point[1] - local[1])
                        if d < best:
                            best = d
                            best_color = _h3(int(cell_x) + i, int(cell_y) + j, 0)
            else:
                for k in range(-1, 2):
                    for j in range(-1, 2):
                        for i in range(-1, 2):
                            hx, hy, hz = _h3(int(cell_x) + i, int(cell_y) + j, int(cell_z) + k)
                            point = (i + hx * randomness, j + hy * randomness, k + hz * randomness)
                            d = math.sqrt(
                                (point[0] - local[0]) ** 2
                                + (point[1] - local[1]) ** 2
                                + (point[2] - local[2]) ** 2
                            )
                            if d < best:
                                best = d
                                best_color = (hx, hy, hz)
            if feature == "F2":
                best = min(1.0, best * 1.5)
            if output_mode == "COLOR":
                regs[dst] = (float(best_color[0]), float(best_color[1]), float(best_color[2]), 1.0)
            elif output_mode == "POSITION":
                regs[dst] = (px, py, pz, 1.0)
            else:
                regs[dst] = (best, best, best, 1.0)
        elif opcode == OPCODE_WHITE_NOISE_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            w = as_scalar(regs[int(op.get("w", 0))]) if "w" in op else 0.0
            dims = str(op.get("dimensions") or "3D").upper()
            output_mode = str(op.get("output") or "VALUE").upper()
            regs[dst] = _white_noise_texture(
                (float(c[0]), float(c[1]), float(c[2])),
                w,
                dimensions=dims,
                want_color=(output_mode == "COLOR"),
            )
        elif opcode == OPCODE_GABOR_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            orient3 = regs[int(op.get("orientation_3d", 0))]
            regs[dst] = _gabor_texture(
                (float(c[0]), float(c[1]), float(c[2])),
                as_scalar(regs[int(op.get("scale", 0))]),
                as_scalar(regs[int(op.get("frequency", 0))]),
                as_scalar(regs[int(op.get("anisotropy", 0))]),
                as_scalar(regs[int(op.get("orientation_2d", 0))]),
                (float(orient3[0]), float(orient3[1]), float(orient3[2])),
                gabor_type=str(op.get("gabor_type") or "2D").upper(),
                output_mode=str(op.get("output") or "VALUE").upper(),
            )
        elif opcode == OPCODE_MAGIC_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            scale = as_scalar(regs[int(op.get("scale", 0))])
            distortion = as_scalar(regs[int(op.get("distortion", 0))])
            depth = int(op.get("steps", 2))
            output_mode = str(op.get("output") or "FAC").upper()
            regs[dst] = _magic_texture(
                (float(c[0]), float(c[1]), float(c[2])),
                scale,
                distortion,
                depth,
                want_color=(output_mode == "COLOR"),
            )
        elif opcode == OPCODE_WAVE_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            scale = as_scalar(regs[int(op.get("scale", 0))])
            phase = as_scalar(regs[int(op.get("phase", 0))]) if "phase" in op else 0.0
            wave_type = str(op.get("wave_type") or "BANDS").upper()
            bands_dir = str(op.get("bands_dir") or "X").upper()
            rings_dir = str(op.get("rings_dir") or "X").upper()
            profile = str(op.get("profile") or "SIN").upper()
            q = (
                (float(c[0]) * scale + 0.000001) * 0.999999,
                (float(c[1]) * scale + 0.000001) * 0.999999,
                (float(c[2]) * scale + 0.000001) * 0.999999,
            )
            if wave_type == "RINGS":
                rp = list(q)
                if rings_dir == "X":
                    rp[0] = 0.0
                elif rings_dir == "Y":
                    rp[1] = 0.0
                elif rings_dir == "Z":
                    rp[2] = 0.0
                n = math.sqrt(rp[0] ** 2 + rp[1] ** 2 + rp[2] ** 2) * 20.0
            elif bands_dir == "Y":
                n = q[1] * 20.0
            elif bands_dir == "Z":
                n = q[2] * 20.0
            elif bands_dir == "DIAGONAL":
                n = (q[0] + q[1] + q[2]) * 10.0
            else:
                n = q[0] * 20.0
            n += phase
            two_pi = 2.0 * math.pi
            if profile == "SAW":
                n /= two_pi
                value = n - math.floor(n)
            elif profile in {"TRI", "TRIANGLE"}:
                n /= two_pi
                value = abs(n - math.floor(n + 0.5)) * 2.0
            else:
                value = 0.5 + 0.5 * math.sin(n - math.pi * 0.5)
            regs[dst] = (value, value, value, 1.0)
        elif opcode == OPCODE_GRADIENT_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            gtype = str(op.get("gradient_type") or "LINEAR").upper()
            x, y, z = float(c[0]), float(c[1]), float(c[2])
            if gtype == "QUADRATIC":
                r = max(x, 0.0)
                value = r * r
            elif gtype == "EASING":
                r = min(max(x, 0.0), 1.0)
                t = r * r
                value = 3.0 * t - 2.0 * t * r
            elif gtype == "DIAGONAL":
                value = (x + y) * 0.5
            elif gtype == "RADIAL":
                value = math.atan2(y, x) / (2.0 * math.pi) + 0.5
            elif gtype == "QUADRATIC_SPHERE":
                r = max(0.999999 - math.sqrt(x * x + y * y + z * z), 0.0)
                value = r * r
            elif gtype == "SPHERICAL":
                value = max(0.999999 - math.sqrt(x * x + y * y + z * z), 0.0)
            else:
                value = x
            value = min(max(value, 0.0), 1.0)
            regs[dst] = (value, value, value, 1.0)
        elif opcode == OPCODE_CHECKER_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            scale = as_scalar(regs[int(op.get("scale", 0))]) if "scale" in op else 5.0
            c1 = regs[int(op.get("a", 0))] if "a" in op else (0.0, 0.0, 0.0, 1.0)
            c2 = regs[int(op.get("b", 0))] if "b" in op else (1.0, 1.0, 1.0, 1.0)
            output_mode = str(op.get("output") or "FAC").upper()
            q = (
                (float(c[0]) * scale + 0.000001) * 0.999999,
                (float(c[1]) * scale + 0.000001) * 0.999999,
                (float(c[2]) * scale + 0.000001) * 0.999999,
            )
            xi = abs(int(math.floor(q[0])))
            yi = abs(int(math.floor(q[1])))
            zi = abs(int(math.floor(q[2])))
            fac = 1.0 if ((xi % 2 == yi % 2) == (zi % 2)) else 0.0
            if output_mode == "COLOR":
                regs[dst] = c1 if fac == 1.0 else c2
            else:
                regs[dst] = (fac, fac, fac, 1.0)
        elif opcode == OPCODE_BRICK_TEXTURE:
            c = regs[int(op.get("coord", 0))]
            scale = as_scalar(regs[int(op.get("scale", 0))]) if "scale" in op else 5.0
            c1 = regs[int(op.get("a", 0))] if "a" in op else (0.8, 0.3, 0.2, 1.0)
            c2 = regs[int(op.get("b", 0))] if "b" in op else (0.6, 0.2, 0.15, 1.0)
            mortar_c = regs[int(op.get("mortar", 0))] if "mortar" in op else (0.5, 0.5, 0.5, 1.0)
            mortar_size = as_scalar(regs[int(op["mortar_size"])]) if "mortar_size" in op else 0.02
            mortar_smooth = (
                as_scalar(regs[int(op["mortar_smooth"])]) if "mortar_smooth" in op else 0.1
            )
            bias = as_scalar(regs[int(op["bias"])]) if "bias" in op else 0.0
            brick_width = as_scalar(regs[int(op["brick_width"])]) if "brick_width" in op else 0.5
            row_height = as_scalar(regs[int(op["row_height"])]) if "row_height" in op else 0.25
            offset_amount = float(op.get("brick_offset", 0.5))
            squash_amount = float(op.get("brick_squash", 1.0))
            offset_frequency = int(op.get("brick_offset_freq", 2))
            squash_frequency = int(op.get("brick_squash_freq", 2))
            output_mode = str(op.get("output") or "FAC").upper()
            px = float(c[0]) * scale
            py = float(c[1]) * scale
            rownum = int(math.floor(py / max(row_height, 1e-8)))
            width = brick_width
            offset = 0.0
            if offset_frequency and squash_frequency:
                if rownum % squash_frequency == 0:
                    width *= squash_amount
                if rownum % offset_frequency == 0:
                    offset = width * offset_amount
            bricknum = int(math.floor((px + offset) / max(width, 1e-8)))
            x = (px + offset) - width * bricknum
            y = py - row_height * rownum

            def _brick_noise(n: int) -> float:
                n = (n + 1013) & 0x7FFFFFFF
                n = (n >> 13) ^ n
                nn = (n * (n * n * 60493 + 19990303) + 1376312589) & 0x7FFFFFFF
                return 0.5 * (nn / 1073741824.0)

            tint = min(max(_brick_noise((rownum << 16) + (bricknum & 0xFFFF)) + bias, 0.0), 1.0)
            min_dist = min(min(x, y), min(width - x, row_height - y))
            if min_dist >= mortar_size:
                mortar = 0.0
            elif mortar_smooth == 0.0:
                mortar = 1.0
            else:
                min_dist = 1.0 - min_dist / max(mortar_size, 1e-8)
                t = min(max(min_dist / max(mortar_smooth, 1e-8), 0.0), 1.0)
                mortar = t * t * (3.0 - 2.0 * t)
            if output_mode == "COLOR":
                facm = 1.0 - tint
                brick = (
                    facm * c1[0] + tint * c2[0],
                    facm * c1[1] + tint * c2[1],
                    facm * c1[2] + tint * c2[2],
                )
                regs[dst] = (
                    brick[0] * (1.0 - mortar) + mortar_c[0] * mortar,
                    brick[1] * (1.0 - mortar) + mortar_c[1] * mortar,
                    brick[2] * (1.0 - mortar) + mortar_c[2] * mortar,
                    1.0,
                )
            else:
                regs[dst] = (mortar, mortar, mortar, 1.0)
        elif opcode == OPCODE_SAMPLE_IMAGE:
            coord_reg = int(op.get("coord", -1))
            if coord_reg >= 0:
                c = regs[coord_reg]
                su, sv = float(c[0]), float(c[1])
            else:
                su, sv = float(uv[0]), float(uv[1])
            # `mode` (Cubic / Smart) is deliberately ignored: this evaluator's
            # sampler is a caller-supplied callback with no image dimensions, and
            # the bicubic tap is defined in texel space. Like the procedural
            # texture family above, Cubic is gated engine-vs-engine on a real bake
            # rather than against a stand-in here.
            if "extension" in op:
                rgba = sampler_tap(op, su, sv)
            else:
                rgba = sample_at(int(op.get("resource", 0)), su, sv)
            channel = str(op.get("channel") or "RGBA").upper()
            if channel == "A":
                a = float(rgba[3])
                regs[dst] = (a, a, a, a)
            else:
                regs[dst] = (float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
        elif opcode == OPCODE_SWIZZLE:
            regs[dst] = swizzle(regs[int(op["src"])], str(op.get("mode") or ""))
        elif opcode == OPCODE_INVERT:
            src = regs[int(op["src"])]
            fac = as_scalar(regs[int(op.get("fac", op["src"]))])
            inv = (1.0 - src[0], 1.0 - src[1], 1.0 - src[2], src[3])
            regs[dst] = (
                src[0] * (1.0 - fac) + inv[0] * fac,
                src[1] * (1.0 - fac) + inv[1] * fac,
                src[2] * (1.0 - fac) + inv[2] * fac,
                src[3],
            )
        elif opcode == OPCODE_MIX:
            a = regs[int(op["a"])]
            b = regs[int(op["b"])]
            fac = as_scalar(regs[int(op["fac"])])
            blend = str(op.get("blend") or "MIX").upper()
            rgb = _ramp_blend(blend, (a[0], a[1], a[2]), (b[0], b[1], b[2]), fac)
            alpha = a[3] * (1.0 - fac) + b[3] * fac if blend == "MIX" else a[3]
            regs[dst] = (rgb[0], rgb[1], rgb[2], alpha)
        elif opcode == OPCODE_MATH:
            a = as_scalar(regs[int(op["a"])])
            b = as_scalar(regs[int(op["b"])])
            c = as_scalar(regs[int(op.get("fac", 0))])
            mop = str(op.get("math_op") or "").upper()
            if mop == "MULTIPLY":
                v = a * b
            elif mop == "ADD":
                v = a + b
            elif mop == "SUBTRACT":
                v = a - b
            elif mop == "DIVIDE":
                v = a / b if abs(b) > 1e-12 else 0.0
            elif mop == "POWER":
                v = math.pow(max(a, 0.0), b) if a >= 0.0 or float(b).is_integer() else 0.0
            elif mop == "MINIMUM":
                v = min(a, b)
            elif mop == "MAXIMUM":
                v = max(a, b)
            elif mop == "LESS_THAN":
                v = 1.0 if a < b else 0.0
            elif mop == "GREATER_THAN":
                v = 1.0 if a > b else 0.0
            elif mop == "MODULO":
                v = math.fmod(a, b) if abs(b) > 1e-12 else 0.0
            elif mop == "ABSOLUTE":
                v = abs(a)
            elif mop == "SQRT":
                v = math.sqrt(a) if a >= 0.0 else 0.0
            elif mop == "FLOOR":
                v = float(math.floor(a))
            elif mop == "CEIL":
                v = float(math.ceil(a))
            elif mop == "FRACT":
                v = a - math.floor(a)
            elif mop == "SINE":
                v = math.sin(a)
            elif mop == "COSINE":
                v = math.cos(a)
            elif mop == "TANGENT":
                v = math.tan(a)
            elif mop == "ARCTANGENT":
                v = math.atan(a)
            elif mop == "ARCSINE":
                v = math.asin(max(-1.0, min(1.0, a)))
            elif mop == "ARCCOSINE":
                v = math.acos(max(-1.0, min(1.0, a)))
            elif mop == "ROUND":
                v = float(round(a))
            elif mop == "SIGN":
                v = 1.0 if a > 0.0 else (-1.0 if a < 0.0 else 0.0)
            elif mop == "CLAMP":
                v = min(max(a, 0.0), 1.0)
            elif mop == "MULTIPLY_ADD":
                v = a * b + c
            elif mop == "LOGARITHM":
                v = math.log(a) / math.log(b) if a > 0.0 and b > 0.0 and b != 1.0 else 0.0
            elif mop == "INVERSE_SQRT":
                v = 1.0 / math.sqrt(a) if a > 0.0 else 0.0
            elif mop == "EXPONENT":
                v = math.exp(a)
            elif mop == "COMPARE":
                v = 1.0 if abs(a - b) <= max(c, 1e-5) else 0.0
            elif mop == "SMOOTH_MIN":
                v = _smooth_min(a, b, c)
            elif mop == "SMOOTH_MAX":
                v = -_smooth_min(-a, -b, c)
            elif mop == "TRUNC":
                v = float(math.floor(a)) if a >= 0.0 else float(math.ceil(a))
            elif mop == "FLOORED_MODULO":
                v = a - math.floor(a / b) * b if b != 0.0 else 0.0
            elif mop == "WRAP":
                v = _wrap(a, b, c)
            elif mop == "SNAP":
                v = math.floor(a / b) * b if b != 0.0 else 0.0
            elif mop == "PINGPONG":
                v = _pingpong(a, b)
            elif mop == "ARCTAN2":
                v = math.atan2(a, b)
            elif mop == "SINH":
                v = math.sinh(a)
            elif mop == "COSH":
                v = math.cosh(a)
            elif mop == "TANH":
                v = math.tanh(a)
            elif mop == "RADIANS":
                v = math.radians(a)
            elif mop == "DEGREES":
                v = math.degrees(a)
            else:
                v = a
            if bool(op.get("clamp")):
                v = min(max(v, 0.0), 1.0)
            regs[dst] = (v, v, v, 1.0)
        elif opcode == OPCODE_VECTOR_TRANSFORM:
            v = regs[int(op["src"])]
            mode = str(op.get("mode") or "VECTOR").upper()
            to_object = bool(op.get("clamp"))
            m = world_to_object if to_object else _invert_affine(world_to_object)
            if mode == "POINT":
                out = _transform_point(m, (v[0], v[1], v[2]))
            elif mode == "NORMAL":
                # Normals transform by the inverse-transpose of the mapping.
                out = _transform_direction_transposed(
                    _invert_affine(m), (v[0], v[1], v[2])
                )
                length = math.sqrt(sum(c * c for c in out)) or 1.0
                out = tuple(c / length for c in out)
            else:
                out = _transform_direction(m, (v[0], v[1], v[2]))
            regs[dst] = (out[0], out[1], out[2], 1.0)
        elif opcode == OPCODE_VECTOR_ROTATE:
            v = regs[int(op["src"])]
            c = regs[int(op["a"])]
            ax = regs[int(op["b"])]
            rot = regs[int(op.get("fac", 0))]
            angle = as_scalar(regs[int(op.get("scale", 0))])
            mode = str(op.get("mode") or "AXIS_ANGLE").upper()
            invert = bool(op.get("clamp"))
            p = (v[0] - c[0], v[1] - c[1], v[2] - c[2])
            if mode == "EULER_XYZ":
                out = _euler_xyz_apply(p, (rot[0], rot[1], rot[2]), transpose=invert)
            else:
                if mode == "X_AXIS":
                    axis = (1.0, 0.0, 0.0)
                elif mode == "Y_AXIS":
                    axis = (0.0, 1.0, 0.0)
                elif mode == "Z_AXIS":
                    axis = (0.0, 0.0, 1.0)
                else:
                    axis = (ax[0], ax[1], ax[2])
                length = math.sqrt(sum(a * a for a in axis))
                if length == 0.0:
                    out = p
                else:
                    unit = tuple(a / length for a in axis)
                    out = _rotate_around_axis(p, unit, -angle if invert else angle)
            regs[dst] = (out[0] + c[0], out[1] + c[1], out[2] + c[2], 1.0)
        elif opcode == OPCODE_CURVE_MAP:
            table = op.get("table") or []
            mode = str(op.get("curve_mode") or "RGB").upper()
            src = regs[int(op["src"])]
            fac = as_scalar(regs[int(op.get("fac", 0))])
            min_x = float(op.get("min_x", 0.0))
            max_x = float(op.get("max_x", 1.0))
            clamp_domain = bool(op.get("clamp"))
            if mode == "SCALAR_RGB":
                # One scalar drives all three channels (Blackbody, Wavelength).
                value = as_scalar(src)
                regs[dst] = (
                    _curve_table_lookup(table, min_x, max_x, value, 0, clamp_domain),
                    _curve_table_lookup(table, min_x, max_x, value, 1, clamp_domain),
                    _curve_table_lookup(table, min_x, max_x, value, 2, clamp_domain),
                    1.0,
                )
            elif mode == "FLOAT":
                value = as_scalar(src)
                curved = _curve_table_lookup(table, min_x, max_x, value, 0, clamp_domain)
                out = value + (curved - value) * fac
                regs[dst] = (out, out, out, 1.0)
            else:
                channels = []
                for index in range(3):
                    value = float(src[index])
                    curved = _curve_table_lookup(
                        table, min_x, max_x, value, index, clamp_domain
                    )
                    channels.append(value + (curved - value) * fac)
                regs[dst] = (channels[0], channels[1], channels[2], src[3])
        elif opcode == OPCODE_COLOR_RAMP:
            regs[dst] = _colorband_evaluate(
                op.get("elements") or [],
                str(op.get("mode") or "LINEAR").upper(),
                as_scalar(regs[int(op["src"])]),
            )
        elif opcode == OPCODE_COMBINE_XYZ:
            x = as_scalar(regs[int(op.get("a", 0))])
            y = as_scalar(regs[int(op.get("b", 0))])
            z = as_scalar(regs[int(op.get("fac", 0))])
            regs[dst] = (x, y, z, 1.0)
        elif opcode == OPCODE_HUE_SAT:
            color = regs[int(op.get("src", 0))]
            hue = as_scalar(regs[int(op.get("a", 0))])
            sat = as_scalar(regs[int(op.get("b", 0))])
            value = as_scalar(regs[int(op["detail"])]) if "detail" in op else 1.0
            fac = as_scalar(regs[int(op.get("fac", 0))])
            h, s, v = _rgb_to_hsv(color[0], color[1], color[2])
            h = (h + hue - 0.5) % 1.0
            s = max(s * sat, 0.0)
            v = max(v * value, 0.0)
            nr, ng, nb = _hsv_to_rgb(h, s, v)
            regs[dst] = (
                color[0] * (1.0 - fac) + nr * fac,
                color[1] * (1.0 - fac) + ng * fac,
                color[2] * (1.0 - fac) + nb * fac,
                color[3],
            )
        elif opcode == OPCODE_COLOR_SPACE:
            color = regs[int(op.get("src", 0))]
            direction = str(op.get("mode", "RGB_TO_HSV") or "RGB_TO_HSV").upper()
            if direction == "HSV_TO_RGB":
                converted = _hsv_to_rgb(color[0], color[1], color[2])
            elif direction == "RGB_TO_HSL":
                converted = _rgb_to_hsl(color[0], color[1], color[2])
            elif direction == "HSL_TO_RGB":
                converted = _hsl_to_rgb(color[0], color[1], color[2])
            else:
                converted = _rgb_to_hsv(color[0], color[1], color[2])
            regs[dst] = (converted[0], converted[1], converted[2], color[3])
        elif opcode == OPCODE_BRIGHTCONTRAST:
            color = regs[int(op.get("src", 0))]
            bright = as_scalar(regs[int(op.get("a", 0))])
            contrast = as_scalar(regs[int(op.get("b", 0))])
            a = 1.0 + contrast
            b = bright - contrast * 0.5
            regs[dst] = (
                max(a * color[0] + b, 0.0),
                max(a * color[1] + b, 0.0),
                max(a * color[2] + b, 0.0),
                color[3],
            )
        elif opcode == OPCODE_GAMMA:
            color = regs[int(op.get("src", 0))]
            gamma = as_scalar(regs[int(op.get("a", 0))])
            regs[dst] = (
                math.pow(max(color[0], 0.0), gamma),
                math.pow(max(color[1], 0.0), gamma),
                math.pow(max(color[2], 0.0), gamma),
                color[3],
            )
        elif opcode == OPCODE_CLAMP:
            v = as_scalar(regs[int(op.get("src", 0))])
            lo = as_scalar(regs[int(op.get("a", 0))])
            hi = as_scalar(regs[int(op.get("b", 0))])
            if lo > hi:
                lo, hi = hi, lo
            v = min(max(v, lo), hi)
            regs[dst] = (v, v, v, 1.0)
        elif opcode == OPCODE_MAP_RANGE:
            v = as_scalar(regs[int(op.get("src", 0))])
            from_min = as_scalar(regs[int(op.get("a", 0))])
            from_max = as_scalar(regs[int(op.get("b", 0))])
            to_min = as_scalar(regs[int(op.get("fac", 0))])
            to_max = as_scalar(regs[int(op["detail"])]) if "detail" in op else 1.0
            mode = str(op.get("mode") or "LINEAR").upper()
            out = _cycles_map_range(
                v,
                from_min,
                from_max,
                to_min,
                to_max,
                as_scalar(regs[int(op["steps"])]) if "steps" in op else 4.0,
                mode,
                bool(op.get("clamp", True)),
            )
            regs[dst] = (out, out, out, 1.0)
        elif opcode == OPCODE_VECTOR_MATH:
            a = regs[int(op.get("a", 0))]
            b = regs[int(op.get("b", 0))]
            c = regs[int(op.get("fac", 0))] if "fac" in op else (0.0, 0.0, 0.0, 1.0)
            scale = as_scalar(regs[int(op["scale"])]) if "scale" in op else 1.0
            mop = str(op.get("math_op") or "ADD").upper()
            ax, ay, az = float(a[0]), float(a[1]), float(a[2])
            bx, by, bz = float(b[0]), float(b[1]), float(b[2])
            if mop == "ADD":
                out = (ax + bx, ay + by, az + bz)
            elif mop == "SUBTRACT":
                out = (ax - bx, ay - by, az - bz)
            elif mop == "MULTIPLY":
                out = (ax * bx, ay * by, az * bz)
            elif mop == "DIVIDE":
                out = (
                    ax / bx if abs(bx) > 1e-12 else 0.0,
                    ay / by if abs(by) > 1e-12 else 0.0,
                    az / bz if abs(bz) > 1e-12 else 0.0,
                )
            elif mop in {"CROSS_PRODUCT", "CROSS"}:
                out = (ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx)
            elif mop in {"DOT_PRODUCT", "DOT"}:
                d = ax * bx + ay * by + az * bz
                out = (d, d, d)
            elif mop == "NORMALIZE":
                length = math.sqrt(ax * ax + ay * ay + az * az) or 1.0
                out = (ax / length, ay / length, az / length)
            elif mop == "LENGTH":
                length = math.sqrt(ax * ax + ay * ay + az * az)
                out = (length, length, length)
            elif mop == "SCALE":
                out = (ax * scale, ay * scale, az * scale)
            elif mop == "ABSOLUTE":
                out = (abs(ax), abs(ay), abs(az))
            elif mop == "MINIMUM":
                out = (min(ax, bx), min(ay, by), min(az, bz))
            elif mop == "MAXIMUM":
                out = (max(ax, bx), max(ay, by), max(az, bz))
            elif mop == "REFLECT":
                # a - 2*dot(a,n)*n with n = normalize(b)
                nlen = math.sqrt(bx * bx + by * by + bz * bz) or 1.0
                nx, ny, nz = bx / nlen, by / nlen, bz / nlen
                d = ax * nx + ay * ny + az * nz
                out = (ax - 2.0 * d * nx, ay - 2.0 * d * ny, az - 2.0 * d * nz)
            elif mop == "DISTANCE":
                d = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
                out = (d, d, d)
            elif mop == "FLOOR":
                out = (math.floor(ax), math.floor(ay), math.floor(az))
            elif mop == "CEIL":
                out = (math.ceil(ax), math.ceil(ay), math.ceil(az))
            elif mop == "FRACTION":
                out = (ax - math.floor(ax), ay - math.floor(ay), az - math.floor(az))
            elif mop == "MODULO":
                # Blender Vector Math Modulo is truncated fmod, not floored.
                def _mod(x, y):
                    return math.fmod(x, y) if abs(y) > 1e-12 else 0.0

                out = (_mod(ax, bx), _mod(ay, by), _mod(az, bz))
            elif mop == "SNAP":
                def _snap(x, y):
                    return y * math.floor(x / y) if abs(y) > 1e-12 else 0.0

                out = (_snap(ax, bx), _snap(ay, by), _snap(az, bz))
            elif mop == "PROJECT":
                denom = bx * bx + by * by + bz * bz
                if denom < 1e-12:
                    out = (0.0, 0.0, 0.0)
                else:
                    d = (ax * bx + ay * by + az * bz) / denom
                    out = (bx * d, by * d, bz * d)
            elif mop == "FACEFORWARD":
                # incident a, reference c, normal b — Blender: if dot(c,b)<0 then a else -a
                # Actually Blender: faceforward(N, I, Nref) = N if dot(Nref,I) < 0 else -N
                # With sockets Vector=N, Vector1=I, Vector2=Nref typically... use a=N, b=I, c=Nref
                d = c[0] * b[0] + c[1] * b[1] + c[2] * b[2]
                out = (ax, ay, az) if d < 0.0 else (-ax, -ay, -az)
            elif mop == "MULTIPLY_ADD":
                out = (ax * bx + c[0], ay * by + c[1], az * bz + c[2])
            elif mop == "REFRACT":
                nlen = math.sqrt(bx * bx + by * by + bz * bz) or 1.0
                nx, ny, nz = bx / nlen, by / nlen, bz / nlen
                d = ax * nx + ay * ny + az * nz
                k = 1.0 - scale * scale * (1.0 - d * d)
                if k < 0.0:
                    out = (0.0, 0.0, 0.0)
                else:
                    t = scale * d + math.sqrt(k)
                    out = (
                        scale * ax - t * nx,
                        scale * ay - t * ny,
                        scale * az - t * nz,
                    )
            elif mop == "WRAP":
                out = (
                    _wrap(ax, bx, c[0]),
                    _wrap(ay, by, c[1]),
                    _wrap(az, bz, c[2]),
                )
            elif mop == "POWER":
                def _pow(x, y):
                    if x >= 0.0 or float(y).is_integer():
                        return math.pow(max(x, 0.0), y) if x >= 0.0 else math.pow(x, y)
                    return 0.0

                out = (_pow(ax, bx), _pow(ay, by), _pow(az, bz))
            elif mop == "SIGN":
                def _sign(x):
                    return 1.0 if x > 0.0 else (-1.0 if x < 0.0 else 0.0)

                out = (_sign(ax), _sign(ay), _sign(az))
            elif mop == "ROUND":
                out = (float(round(ax)), float(round(ay)), float(round(az)))
            elif mop == "SINE":
                out = (math.sin(ax), math.sin(ay), math.sin(az))
            elif mop == "COSINE":
                out = (math.cos(ax), math.cos(ay), math.cos(az))
            elif mop == "TANGENT":
                out = (math.tan(ax), math.tan(ay), math.tan(az))
            else:
                out = (ax, ay, az)
            regs[dst] = (out[0], out[1], out[2], 1.0)
        else:
            raise ValueError(f"Unknown opcode {opcode}")

    out = regs[int(program.result_reg)]
    return (out[0], out[1], out[2])
