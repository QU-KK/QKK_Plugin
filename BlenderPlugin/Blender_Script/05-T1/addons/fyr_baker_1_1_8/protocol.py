from __future__ import annotations

from array import array
from dataclasses import asdict, dataclass, field, fields as dataclass_fields
import itertools
import json
import os
from pathlib import Path
import struct
import sys
import time

from . import constants

_HEATMAP_BLOB_MAGIC_V1 = b"MBDHM01\x00"
_HEATMAP_BLOB_MAGIC_V2 = b"MBDHM02\x00"
# Binary bake-job tag. ONE constant, deliberately.
#
# There used to be 23 of these, so an old backend could read a new job file and vice versa.
# That can never happen: fyr_baker_backend.exe ships INSIDE the addon zip, so the addon and
# the backend are always the same build. Every version branch the backend carried for it was
# unreachable code.
#
# A mismatch therefore means a half-built working tree, not an old install -- so the backend
# refuses the file loudly instead of trying to interpret it. The trailing number is kept only
# so a stale .mbjob left in a temp dir from an older build fails that check rather than being
# silently misparsed; bump it whenever the layout changes, but nothing needs to READ the old
# values.
#
# Note this is NOT constants.PROTOCOL_VERSION (a separate string sent inside the job) and NOT
# the addon version. Three unrelated numbers; this is the file-layout one.
_BINARY_JOB_MAGIC = b"MBBJOB48"

_BINARY_JOB_EXTENSION = ".mbjob"

MESH_TRANSPORT_FILE_FYMESH = "FILE_FYMESH"
MESH_TRANSPORT_WIN32_SECTION = "WIN32_SECTION"
MESH_TRANSPORT_CANONICAL_CACHE = "CANONICAL_CACHE"
GEOMETRY_SCHEMA_FYRGEOM1 = "FYRGEOM1"


@dataclass(slots=True)
class ExportedMeshRef:
    name: str
    object_name: str
    role: str
    path: str
    cache_key: str = ""
    material_name: str = ""
    material_color: list[float] = field(default_factory=list)
    collection_name: str = ""
    file_id_key: str = ""
    world_to_object: list[float] = field(default_factory=list)
    matrix_world: list[float] = field(default_factory=list)
    transport_kind: str = MESH_TRANSPORT_FILE_FYMESH
    geometry_schema: str = ""
    transport_locator: str = ""
    byte_size: int = 0
    content_hash: str = ""
    # MBBJOB24: optional object/material opacity binding. The image is a
    # workspace-owned linear grayscale PNG sampled in the exported high UVs.
    opacity_image_path: str = ""
    opacity_constant: float = 1.0
    opacity_address_mode: str = "REPEAT"
    opacity_filter: str = "LINEAR"


@dataclass(slots=True)
class OutputTarget:
    map_type: str
    path: str
    display_name: str
    output_suffix: str = ""
    map_uuid: str = ""
    # UDIM tile this target writes, or 0 for an untiled (single-tile) output. The physical
    # identity of an output is (texture_set, map_uuid, udim_tile) -- the same map_uuid repeats
    # across a texture set's tiles, so anything keying outputs must include the tile too.
    udim_tile: int = 0
    # Effective physical size for THIS tile. 0 means "inherit the project resolution".
    # Tiles in one texture set may legitimately differ (both Painter and Marmoset allow it).
    resolution_width: int = 0
    resolution_height: int = 0


@dataclass(slots=True)
class MaterialDetailBinding:
    """One high MATERIAL's own normal/bump/AO detail source.

    The job used to carry a single detail image per map, shared by every group and
    every material in the bake. Resolving it required one identical source across all
    of them, so a high with two materials -- or two groups with different detail
    textures -- silently dropped the detail entirely and the map baked from geometry
    alone.

    Each binding names the material it belongs to; the backend selects per hit from
    ``RayHit::source_material_name``. ``MapConfig.material_detail_*`` stays as the
    fallback for hits whose material has no binding, so a single-source job is
    transported and rendered exactly as it was before.
    """

    material_name: str
    image_path: str
    mode: str = ""
    strength: float = 1.0
    flip_green: bool = False
    # MBBJOB29: constant 2D affine applied to the high hit UV before sampling this
    # binding's detail image: u' = a*u + b*v + tx, v' = c*u + d*v + ty, stored as
    # [a, b, c, d, tx, ty]. Empty means identity. Carries a constant Mapping node
    # between the UV and the texture, which the plain-UV fast path used to refuse.
    uv_transform: list[float] = field(default_factory=list)


@dataclass(slots=True)
class IdMaterialMesh:
    """MBBJOB35: per-face colours for an ID map whose source is "Material Color".

    One record per high OBJECT (matched backend-side to its mesh range by
    ``object_name``). ``colors`` is indexed by the object's MATERIAL SLOT, each resolved
    through ``id_material_color.material_id_color`` (an empty slot takes the object's own
    colour, which is what a material-less object has always baked).

    ``slot_index_path`` is the per-triangle slot sidecar (FYRMSLT1, see
    ``export._write_id_material_slot_sidecar``): one slot index per exported high
    triangle in the object's EXPORT (``loop_triangles``) order. It is written only for an
    object whose faces really use more than one distinct material; otherwise the path is
    empty and ``colors`` holds the single colour that paints the whole object.
    ``triangle_count`` lets the backend refuse a sidecar that does not describe the
    triangles it received.
    """

    object_name: str
    colors: list[list[float]] = field(default_factory=list)
    slot_index_path: str = ""
    triangle_count: int = 0


@dataclass(slots=True)
class MaterialSourceTile:
    """One tile of a tiled (UDIM) material *source* image.

    ``udim_tile`` is the standard number ``1001 + tile_u + 10 * tile_v`` of the tile in the
    SOURCE image's own UV space -- it has nothing to do with the OUTPUT tile being baked.
    ``image_path`` is an absolute PNG path for that tile alone.
    """

    udim_tile: int = 0
    image_path: str = ""


@dataclass(slots=True)
class SkewCorrectionMapRef:
    """Painted Paint Skew correction of one UDIM tile (MBBJOB37): raw little-endian float32,
    width x height, row 0 = v bottom, 0..1 (1 = ray straight off the low face)."""

    udim_tile: int
    path: str
    width: int
    height: int


@dataclass(slots=True)
class DirtyUvRect:
    map_type: str = ""
    map_uuid: str = ""
    # Tile-LOCAL normalized UV. A rect never spans tiles; geometry changes crossing a tile
    # border are split into one rect per intersected tile.
    min_u: float = 0.0
    min_v: float = 0.0
    max_u: float = 1.0
    max_v: float = 1.0
    udim_tile: int = 0


@dataclass(slots=True)
class BakeMapConfig:
    map_type: str
    map_uuid: str = ""
    enabled: bool = True
    samples: int = 1
    output_suffix: str = ""
    normal_space: str = constants.MAP_NORMAL_SPACE_TANGENT
    normal_format: str = constants.NORMAL_FORMAT_OPENGL
    flip_green: bool = False
    ao_mode: str = constants.MAP_AO_MODE_RAYCAST
    ao_distance: float = 0.0
    ao_min_distance: float = 0.0
    ao_two_sided: bool = False
    ao_ignore_groups: bool = False
    ao_occlude_other_groups: bool = False
    ao_cavity_weight: float = 0.0
    ao_floor_occlusion: bool = False
    ao_secondary_rays: int = 0
    ao_relative_to_bounding_box: bool = False
    ao_spread_angle: float = 180.0
    ao_distribution: str = "COSINE"
    ao_ignore_backface: bool = False
    ao_self_occlusion: float = 1.0
    ao_attenuation: float = 1.0
    ao_output_min: float = constants.DEFAULT_AO_OUTPUT_MIN
    ao_output_max: float = 1.0
    ao_use_ground_plane: bool = False
    ao_ground_plane_offset: float = 0.0
    ao_diffusion_quality: str = constants.MAP_AO_DIFFUSION_QUALITY_MEDIUM
    ao_diffusion_clearance_scale: float = 0.2
    ao_diffusion_clearance_exponent: float = 2.0
    env_light_intensity: float = 1.0
    env_light_occlusion_strength: float = 0.6
    env_light_contrast: float = 1.0
    env_light_up_axis: str = "Z"
    env_light_sky_r: float = 0.55
    env_light_sky_g: float = 0.70
    env_light_sky_b: float = 1.00
    env_light_ground_r: float = 0.18
    env_light_ground_g: float = 0.16
    env_light_ground_b: float = 0.14
    curvature_scale: float = 1.0
    curvature_distance: float = 0.0
    curvature_relative_to_bounding_box: bool = False
    curvature_method: str = "NORMAL_DERIVATIVE"
    # MBBJOB33: Painter-style "Generate from Mesh" curvature controls. The probe ray
    # count is now live (it was an inert slot), the dead curvature_sampling_radius f32
    # is gone (Radius is curvature_distance), the old self-intersection BOOL became
    # curvature_detect_folds, and curvature_self_intersection is now the Painter-style
    # STRING enum NEVER / SAME_MESH / GROUP / ALL_GROUPS.
    curvature_secondary_rays: int = 64
    curvature_detect_folds: bool = False
    curvature_self_intersection: str = "GROUP"
    # MBBJOB33: signed-curvature output range. Auto tonemapping stretches each UV tile
    # to its own extremes and makes the value bounds inert.
    curvature_auto_tonemapping: bool = False
    curvature_value_min: float = -1.0
    curvature_value_max: float = 1.0
    # Neutral output range by default (see properties.MasterBakerMapSetting): the
    # Marmoset-matched response is calibrated against an unstretched output. These stay
    # the Black/White Point for Concave and Cavity only.
    curvature_tonemapping_min: float = 0.0
    curvature_tonemapping_max: float = 1.0
    curvature_soften: float = 0.5
    # MBBJOB28: resolved per-map Soften (project value, or the row's own when it
    # overrides). 0.5 is the calibrated neutral -- see addon constants.DEFAULT_SOFTEN.
    output_soften: float = 0.5
    # MBBJOB18: Marmoset curvature response calibration (formerly FYR_BAKER_MM_*
    # env vars that required a worker restart). Scene-level knobs written into every
    # map payload by export.prepare_bake_job. Defaults are the
    # shipped calibrated values so an untouched scene bakes identically.
    mm_power_gamma: float = 1.792
    mm_power_amplitude: float = 9.2
    mm_power_linear_floor: float = 3.2
    mm_power_faint: float = 1.75
    mm_convex_boost: float = 1.7
    mm_linear_bias: float = 1.0
    thickness_distance: float = 0.0
    thickness_min_distance: float = -1.0  # -1.0 = auto-calculate from bounds
    thickness_scale: float = 1.0
    thickness_gamma: float = 1.0
    thickness_dither: bool = False
    thickness_ignore_groups: bool = False
    thickness_normalization: bool = False
    # MBBJOB34: log-scale thickness encode. Packed directly after thickness_normalization,
    # the same position backend_job_io.cpp reads it from.
    thickness_log_response: bool = False
    density_auto_levels: bool = False
    density_auto_levels_per_group: bool = True
    id_source: str = constants.MAP_ID_SOURCE_OBJECT
    # ATTRIBUTE rows (addon-side only: the backend bakes them as VERTEX_COLOR over a
    # stream the addon already filled from this attribute, so these never reach the
    # binary job; the Cycles route reads them to build its Attribute node).
    attribute_name: str = ""
    attribute_range_min: float = 0.0
    attribute_range_max: float = 1.0
    position_mode: str = "ABSOLUTE"
    position_axis: str = "XYZ"
    position_normalization: str = constants.MAP_POSITION_NORMALIZATION_BOUNDING_BOX
    position_normalization_scale: float = 1.0
    relative_to_bounding_box: bool = True
    height_inner_distance: float = 0.0
    height_outer_distance: float = 0.0
    height_dither: bool = False
    denoising_enabled: bool = False
    denoise_strength: float = 1.0
    denoise_quality: str = "HIGH"
    diffusion_dilation_enabled: bool = False
    diffusion_dilation_iterations: int = 3
    material_channel: str = constants.MATERIAL_CHANNEL_ALBEDO
    material_fast_path_image_path: str = ""
    # Tiled (UDIM) material source. Empty for an ordinary untiled source, in which case
    # `material_fast_path_image_path` alone carries the image and behaviour is unchanged.
    # When populated, the backend selects the source tile PER HIT from the high mesh's
    # global UV; `material_fast_path_image_path` then holds the representative (lowest) tile
    # only so that "is a material source present" checks keep working.
    material_fast_path_tile_images: list[MaterialSourceTile] = field(default_factory=list)
    # Material IR annotation (Phase 4 IMAGE_SAMPLE). The production sample path remains
    # material_fast_path_*; these fields record the IR kind / Auto fallback reason for
    # diagnostics and future opcode growth. Omitted from the binary ABI until a dedicated
    # MBBJOB revision ships the interpreter.
    material_ir_version: int = 0
    material_ir_kind: str = ""
    material_ir_fallback_reason: str = ""
    # UV-domain expression program (EXPRESSION_UV). IMAGE_SAMPLE jobs may leave this empty
    # and rely on material_fast_path_* alone. `material_ir_program_json` is the wire form
    # (JSON object text) for both job.json and MBBJOB25; `material_ir_resource_paths` lists
    # absolute PNG paths parallel to program resource indices.
    material_ir_program_json: str = ""
    material_ir_resource_paths: list[str] = field(default_factory=list)
    material_detail_mode: str = ""
    material_detail_strength: float = 1.0
    material_detail_radius: int = 8
    material_detail_flip_green: bool = False
    # MBBJOB26: per-material detail sources. Empty means "use the single source in
    # material_detail_* for every hit", which is exactly the pre-v26 behaviour.
    material_detail_bindings: list[MaterialDetailBinding] = field(default_factory=list)
    # MBBJOB27: per-triangle binding-index sidecar for a high OBJECT that carries more
    # than one material. RayHit's material name is per exported mesh range (one per
    # object), so bindings alone cannot tell two materials on one object apart. The
    # sidecar is a grayscale PNG with one texel per exported high triangle, in the
    # concatenated slot-order triangle order (the corner-attribute convention); the
    # R byte holds binding_index + 1, 0 meaning "no detail for this triangle".
    # Empty path = select by material name exactly as in v26.
    material_detail_slot_index_image_path: str = ""
    # MBBJOB29: constant 2D affine for the LEGACY single-source detail fields above,
    # same [a, b, c, d, tx, ty] encoding as MaterialDetailBinding.uv_transform.
    # Empty means identity (every pre-v29 job).
    material_detail_uv_transform: list[float] = field(default_factory=list)
    # MBBJOB35: ID map, source "Material Color" only -- per-face material colours for
    # the high objects of the job. Empty (every other map, and an ID map on any other
    # source) keeps the pre-v35 behaviour: one colour per high mesh from
    # ExportedMeshRef.material_color. Sorted by object name on the wire.
    id_material_meshes: list[IdMaterialMesh] = field(default_factory=list)
    # MBBJOB39: material-detail normals for the secondary-ray maps. On the Normal row
    # that bakes natively through the Material IR, ``material_normal_retain`` asks the
    # worker to keep its resolved tangent texels after writing the file. On an AO /
    # Cavity / Curvature / Bent Normal row, ``material_normal_source_uuid`` names that
    # Normal row: the shading kernel decodes the retained texel through the low's
    # tangent frame and shades from it instead of the raw high hit normal, so a bevel
    # shader bands the curvature and tilts the AO hemisphere exactly like the Normal
    # map the artist ships. ``material_normal_source_flip_green`` is that row's green
    # convention, undone before the decode.
    material_normal_retain: bool = False
    material_normal_source_uuid: str = ""
    # MBBJOB48: a per-group Normal pass adds its texels to one composite per (row, texture
    # set, tile) instead of replacing the retained image, and the rows naming it read that.
    material_normal_composite: bool = False
    material_normal_source_flip_green: bool = False
    # MBBJOB41: how the bevelled normal shapes the shading of this row. Curvature /
    # Convex / Concave: ``curvature_bevel_mask`` adds a full-strength line along every
    # bevelled edge (ZenBBQ-style bevel mask, signed by the curvature). AO:
    # ``ao_bevel_normal_mode`` 0 = geometric, 1 = bevel normal everywhere, 2 = bevel normal
    # on convex edges only (concave fillets keep the geometric normal).
    curvature_bevel_mask: bool = True
    ao_bevel_normal_mode: int = 0
    lighting_engine: str = constants.LIGHTING_ENGINE_AUTO
    lighting_quality: str = constants.LIGHTING_QUALITY_BALANCED
    lighting_direct_enabled: bool = True
    lighting_indirect_enabled: bool = True
    lighting_world_enabled: bool = True
    lighting_emission_enabled: bool = True
    lighting_direct_samples: int = 1
    lighting_indirect_paths: int = 64
    lighting_max_bounces: int = 4
    lighting_noise_threshold: float = 0.02
    # MBBJOB42 (Complete Lighting): shadow and bounce rays see every bake group's highs
    # (Marmoset "Ignore Groups"), a linear exposure multiplier, and which part of the
    # lighting the row outputs: "ALL", "DIRECT" (no bounces) or "INDIRECT" (bounces only).
    lighting_occlude_other_groups: bool = False
    lighting_exposure: float = 1.0
    lighting_component: str = "ALL"


@dataclass(slots=True)
class SceneLightRecord:
    """One evaluated Blender analytic light. Position, direction, and local
    basis all derive from matrix_world. Units follow Blender: energy is radiant
    power in watts for point/spot/area and irradiance in W/m^2 for sun."""

    identity: str
    light_type: str  # POINT | SPOT | SUN | AREA
    color: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    energy: float = 0.0
    matrix_world: list[float] = field(default_factory=list)
    radius: float = 0.0  # shadow_soft_size for point/spot; 0 = hard shadows
    sun_angle: float = 0.0  # radians; SUN only
    spot_size: float = 0.0  # cone angle in radians; SPOT only
    spot_blend: float = 0.0  # SPOT only
    area_shape: str = ""  # SQUARE | RECTANGLE | DISK | ELLIPSE; AREA only
    area_size_x: float = 0.0
    area_size_y: float = 0.0
    use_shadow: bool = True
    diffuse_factor: float = 1.0
    visible: bool = True
    cache_signature: str = ""
    # MBBJOB44: Blender light linking, resolved to object names. Receivers: with
    # receiver_only, exactly receiver_objects are lit; otherwise every object except
    # receiver_objects. Blockers likewise decide which objects cast this light's shadows.
    receiver_only: bool = False
    receiver_objects: list[str] = field(default_factory=list)
    blocker_only: bool = False
    blocker_objects: list[str] = field(default_factory=list)
    # MBBJOB47: Blender's per-light Specular factor (Eevee rows scale glossy light by it as
    # they scale diffuse light by diffuse_factor) and the light's Cycles Ray Visibility for
    # diffuse and glossy rays (what Cycles rows use instead: Cycles ignores both factors).
    specular_factor: float = 1.0
    visible_diffuse: bool = True
    visible_glossy: bool = True


@dataclass(slots=True)
class SceneWorldRecord:
    world_mode: str = "NONE"  # NONE | COLOR | HDRI
    color: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    strength: float = 1.0
    image_path: str = ""  # lat-long linear HDR cache; HDRI mode only
    cache_signature: str = ""


@dataclass(slots=True)
class SceneMaterialRecord:
    """Constant diffuse transport inputs for one material, matched backend-side
    by material_name against per-mesh metadata. Emission is color*strength
    premultiplied (radiance, W/(m^2*sr)). Textured inputs are not transported
    yet; the has_textured_* flags drive preflight warnings and diagnostics."""

    material_name: str
    albedo: list[float] = field(default_factory=lambda: [0.8, 0.8, 0.8])
    emission: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    has_textured_albedo: bool = False
    has_textured_emission: bool = False
    cache_signature: str = ""
    # MBBJOB43: the Base Color sampled on a size x size UV grid (linear RGB, row j at
    # v = (j + 0.5) / size), which scene lighting's bounces read at the hit UV. Empty
    # (size 0) for a flat colour.
    albedo_texture_size: int = 0
    albedo_texture: list[float] = field(default_factory=list)
    # MBBJOB46: Principled specular inputs for Specular Lighting. specular_ior_level 0 means
    # no specular lobe (non-Principled surfaces). Roughness / metallic textures are
    # specular_texture_size^2 grids like albedo_texture (one value per texel), or empty.
    roughness: float = 0.5
    metallic: float = 0.0
    specular_ior_level: float = 0.0
    ior: float = 1.5
    specular_tint: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    specular_texture_size: int = 0
    roughness_texture: list[float] = field(default_factory=list)
    metallic_texture: list[float] = field(default_factory=list)


@dataclass(slots=True)
class SceneEmitterLinkRecord:
    """MBBJOB44: light linking of an emissive mesh object (same fields as a light's)."""

    object_name: str
    receiver_only: bool = False
    receiver_objects: list[str] = field(default_factory=list)
    blocker_only: bool = False
    blocker_objects: list[str] = field(default_factory=list)
    cache_signature: str = ""


@dataclass(slots=True)
class SceneLightingConfig:
    seed: int = 0
    lights: list[SceneLightRecord] = field(default_factory=list)
    world: SceneWorldRecord = field(default_factory=SceneWorldRecord)
    materials: list[SceneMaterialRecord] = field(default_factory=list)
    emitter_links: list[SceneEmitterLinkRecord] = field(default_factory=list)
    # MBBJOB47: the scene's Cycles Light Paths settings Cycles rows follow (Blender defaults).
    cycles_filter_glossy: float = 1.0
    cycles_clamp_indirect: float = 10.0


@dataclass(slots=True)
class BakeGroupConfig:
    name: str
    cage_mode: str
    cage_offset: float
    #: Add-on side only, never packed into the job: the material the low meshes were cut to.
    low_material: str = ""
    # Rear Distance: how far behind the low a projection ray may still find the high.
    # 0 = Auto (the backend's max(cage span, 5% of the low bounds diagonal)). MBBJOB36.
    projection_rear_distance: float = 0.0
    average_normals: bool = True
    ignore_backface: bool = False
    match_by_isolation: bool = False
    debug_heatmap_enabled: bool = False
    debug_ray_miss_enabled: bool = False
    id_collection_name: str = ""
    id_color_set_name: str = ""
    paint_offset_scale: float = 1.0
    paint_skew: float = 0.0
    texture_set: str = ""
    low_meshes: list[ExportedMeshRef] = field(default_factory=list)
    high_meshes: list[ExportedMeshRef] = field(default_factory=list)
    cage_meshes: list[ExportedMeshRef] = field(default_factory=list)
    outputs: list[OutputTarget] = field(default_factory=list)
    dirty_uv_rects: list[DirtyUvRect] = field(default_factory=list)
    # Per-pixel Paint Skew correction maps, one per UDIM tile (MBBJOB37). Empty = none.
    skew_correction_maps: list[SkewCorrectionMapRef] = field(default_factory=list)
    # High meshes with "Casts AO" off, by object name (MBBJOB38). Empty = every high casts.
    ao_non_caster_objects: list[str] = field(default_factory=list)
    # MBBJOB40: the group's highs carry Bevel-shader normal detail (sharp corners, the
    # bevel is shading): projection rays stay straight at convex hard edges.
    straight_convex_rays: bool = False
    # MBBJOB45: Scene Blockers. The group's meshes shade the whole-scene lighting (shadows,
    # bounces, glow) but the group bakes and writes nothing. occluder_shadows=False lets
    # shadow rays pass them; occluder_bounces=False makes them reflect no light.
    occluder_only: bool = False
    occluder_shadows: bool = True
    occluder_bounces: bool = True


@dataclass(slots=True)
class BakeProjectInfo:
    name: str
    output_root: str
    workspace: str
    resolution_width: int
    resolution_height: int
    bit_depth: int
    margin: int
    tangent_basis: str
    # FIXED WIRE VALUE, not a setting. The project-level "Output Naming" property was
    # removed (export settings own naming), but the backend still reads an output-preset
    # string here in the job JSON and at this position in the binary job pack, so the
    # addon always emits the Painter constant it has always emitted. init=False keeps
    # the field (and its pack position) while removing it from the constructor.
    output_preset: str = field(default=constants.OUTPUT_PRESET_PAINTER, init=False)
    bake_mode: str
    anti_aliasing: str = constants.DEFAULT_ANTI_ALIASING
    execution_backend: str = constants.EXECUTION_BACKEND_AUTO
    image_format: str = "TGA"
    # MBBJOB16: jittered sample-pass count. anti_aliasing above remains populated
    # (nearest legacy enum) so older backends still degrade gracefully.
    aa_samples: int = constants.DEFAULT_AA_SAMPLES
    # MBBJOB18: job-level Marmoset AA jitter footprint scale (formerly
    # FYR_BAKER_AA_JITTER_SCALE). 1.0 == legacy box jitter.
    mm_aa_jitter_scale: float = 2.0
    # MBBJOB24: supported high-poly opacity participates in shared intersections.
    respect_opacity: bool = True
    # Workflow identifier so validation can distinguish material-workflow jobs
    # (zero backend map_configs, all maps baked addon-side) from high-to-low jobs.
    workflow: str = constants.WORKFLOW_HIGH_TO_LOW
    # Whether the artist has Live Reproject switched on. The backend captures a
    # full linear baseline blob per output map to feed reprojection; that capture
    # is only ever consumed by this feature, so a job with the feature off pays
    # for a baseline nothing reads. Absent in a legacy job -> the backend keeps
    # capturing, so an older addon is unaffected.
    live_reproject: bool = False


@dataclass(slots=True)
class DebugViewConfig:
    viewport_width: int
    viewport_height: int
    view_projection: list[float]
    view_signature: str = ""


@dataclass(slots=True)
class BakeJob:
    version: str
    job_id: str
    created_at: str
    progress_path: str
    project: BakeProjectInfo
    maps: list[BakeMapConfig]
    groups: list[BakeGroupConfig]
    debug_view: DebugViewConfig | None = None
    debug_heatmap_blob_enabled: bool = False
    scene_lighting: SceneLightingConfig | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ProducedFile:
    group_name: str
    map_type: str
    path: str
    map_uuid: str = ""
    # 0 for an untiled output. Needed so latest_outputs keys on the tile too -- without it
    # one tile's produced file overwrites another's in the output record.
    udim_tile: int = 0


@dataclass(slots=True)
class BakeMissDiagnostic:
    group_name: str = ""
    map_types: list[str] = field(default_factory=list)
    covered_pixels: int = 0
    hit_pixels: int = 0
    miss_pixels: int = 0
    miss_ratio: float = 0.0


@dataclass(slots=True)
class DebugOverlayResult:
    version: str = constants.PROTOCOL_VERSION
    group_name: str = ""
    high_ref_fill_positions: list[list[float]] = field(default_factory=list)
    heatmap_low_fill_positions: list[list[float]] = field(default_factory=list)
    heatmap_low_fill_normals: list[list[float]] = field(default_factory=list)
    heatmap_medium_fill_positions: list[list[float]] = field(default_factory=list)
    heatmap_medium_fill_normals: list[list[float]] = field(default_factory=list)
    heatmap_high_fill_positions: list[list[float]] = field(default_factory=list)
    heatmap_high_fill_normals: list[list[float]] = field(default_factory=list)
    ray_miss_line_positions: list[list[float]] = field(default_factory=list)
    heatmap_blob_path: str = ""
    heatmap_image_path: str = ""
    heatmap_image_width: int = 0
    heatmap_image_height: int = 0
    view_signature: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class BakeProgress:
    version: str = constants.PROTOCOL_VERSION
    status: str = constants.STATUS_IDLE
    message: str = ""
    percent: float = 0.0
    stage_percent: float = -1.0
    stage: str = ""
    active_group: str = ""
    active_map: str = ""
    active_maps: list[str] = field(default_factory=list)
    produced_files: list[ProducedFile] = field(default_factory=list)
    miss_diagnostics: list[BakeMissDiagnostic] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def binary_job_path(path: str | Path) -> Path:
    destination = Path(path)
    if destination.suffix.lower() == _BINARY_JOB_EXTENSION:
        return destination
    if destination.suffix:
        return destination.with_suffix(_BINARY_JOB_EXTENSION)
    return destination.with_name(destination.name + _BINARY_JOB_EXTENSION)


def _binary_job_pack_bool(value: bool) -> bytes:
    return struct.pack("<B", 1 if value else 0)


def _binary_job_pack_i32(value: int) -> bytes:
    return struct.pack("<i", int(value))


def _binary_job_pack_u32(value: int) -> bytes:
    return struct.pack("<I", int(value))


def _binary_job_pack_f32(value: float) -> bytes:
    return struct.pack("<f", float(value))


def _binary_job_pack_string(value: str) -> bytes:
    encoded = str(value or "").encode("utf-8")
    return _binary_job_pack_u32(len(encoded)) + encoded


def _binary_job_pack_matrix4(values: list[float] | tuple[float, ...]) -> bytes:
    matrix_values = list(values or [])[:16]
    if len(matrix_values) < 16:
        identity = [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        ]
        matrix_values.extend(identity[len(matrix_values):])
    return b"".join(_binary_job_pack_f32(component) for component in matrix_values)


def _binary_job_pack_vec3(values: list[float] | tuple[float, ...]) -> bytes:
    vec_values = [float(component) for component in list(values or [])[:3]]
    if len(vec_values) < 3:
        vec_values.extend([1.0] * (3 - len(vec_values)))
    return b"".join(_binary_job_pack_f32(component) for component in vec_values)


def _binary_job_pack_mesh_ref(ref: ExportedMeshRef) -> bytes:
    return b"".join(
        (
            _binary_job_pack_string(ref.name),
            _binary_job_pack_string(ref.object_name),
            _binary_job_pack_string(ref.role),
            _binary_job_pack_string(ref.path),
            _binary_job_pack_string(ref.cache_key),
            _binary_job_pack_string(ref.material_name),
            _binary_job_pack_vec3(ref.material_color),
            _binary_job_pack_string(ref.collection_name),
            _binary_job_pack_string(ref.file_id_key),
            _binary_job_pack_matrix4(ref.world_to_object),
            _binary_job_pack_matrix4(ref.matrix_world),
            _binary_job_pack_string(ref.transport_kind),
            _binary_job_pack_string(ref.geometry_schema),
            _binary_job_pack_string(ref.transport_locator),
            struct.pack("<Q", int(ref.byte_size)),
            _binary_job_pack_string(ref.content_hash),
            _binary_job_pack_string(ref.opacity_image_path),
            _binary_job_pack_f32(float(ref.opacity_constant)),
            _binary_job_pack_string(ref.opacity_address_mode),
            _binary_job_pack_string(ref.opacity_filter),
        )
    )


def _wire_map_type(map_type: str) -> str:
    """The backend's name for a map type (see wire_types)."""
    from .wire_types import backend_wire_map_type

    return backend_wire_map_type(map_type)


def _binary_job_pack_output_target(target: OutputTarget) -> bytes:
    return b"".join(
        (
            _binary_job_pack_string(_wire_map_type(target.map_type)),
            _binary_job_pack_string(target.path),
            _binary_job_pack_string(target.display_name),
            _binary_job_pack_string(target.map_uuid),
            _binary_job_pack_i32(int(target.udim_tile)),
            _binary_job_pack_i32(int(target.resolution_width)),
            _binary_job_pack_i32(int(target.resolution_height)),
        )
    )


def _binary_job_pack_dirty_uv_rect(rect: DirtyUvRect) -> bytes:
    return b"".join(
        (
            _binary_job_pack_string(_wire_map_type(rect.map_type)),
            _binary_job_pack_string(rect.map_uuid),
            _binary_job_pack_f32(rect.min_u),
            _binary_job_pack_f32(rect.min_v),
            _binary_job_pack_f32(rect.max_u),
            _binary_job_pack_f32(rect.max_v),
            _binary_job_pack_i32(int(rect.udim_tile)),
        )
    )


def _binary_job_pack_map_config(config: BakeMapConfig) -> bytes:
    return b"".join(
        (
            _binary_job_pack_string(_wire_map_type(config.map_type)),
            _binary_job_pack_string(config.map_uuid),
            _binary_job_pack_bool(config.enabled),
            _binary_job_pack_i32(config.samples),
            _binary_job_pack_string(config.output_suffix),
            _binary_job_pack_string(config.normal_space),
            _binary_job_pack_string(config.normal_format),
            _binary_job_pack_bool(config.flip_green),
            _binary_job_pack_string(config.ao_mode),
            _binary_job_pack_f32(config.ao_distance),
            _binary_job_pack_f32(config.ao_min_distance),
            _binary_job_pack_bool(config.ao_two_sided),
            _binary_job_pack_bool(config.ao_ignore_groups),
            _binary_job_pack_bool(config.ao_occlude_other_groups),
            _binary_job_pack_f32(config.ao_cavity_weight),
            _binary_job_pack_bool(config.ao_floor_occlusion),
            _binary_job_pack_i32(config.ao_secondary_rays),
            _binary_job_pack_bool(config.ao_relative_to_bounding_box),
            _binary_job_pack_f32(config.ao_spread_angle),
            _binary_job_pack_string(config.ao_distribution),
            _binary_job_pack_bool(config.ao_ignore_backface),
            _binary_job_pack_f32(config.ao_self_occlusion),
            _binary_job_pack_f32(config.ao_attenuation),
            _binary_job_pack_f32(config.ao_output_min),
            _binary_job_pack_f32(config.ao_output_max),
            _binary_job_pack_bool(config.ao_use_ground_plane),
            _binary_job_pack_f32(config.ao_ground_plane_offset),
            _binary_job_pack_string(config.ao_diffusion_quality),
            _binary_job_pack_f32(config.ao_diffusion_clearance_scale),
            _binary_job_pack_f32(config.ao_diffusion_clearance_exponent),
            _binary_job_pack_f32(config.env_light_intensity),
            _binary_job_pack_f32(config.env_light_occlusion_strength),
            _binary_job_pack_f32(config.env_light_contrast),
            _binary_job_pack_string(config.env_light_up_axis),
            _binary_job_pack_f32(config.env_light_sky_r),
            _binary_job_pack_f32(config.env_light_sky_g),
            _binary_job_pack_f32(config.env_light_sky_b),
            _binary_job_pack_f32(config.env_light_ground_r),
            _binary_job_pack_f32(config.env_light_ground_g),
            _binary_job_pack_f32(config.env_light_ground_b),
            _binary_job_pack_f32(config.curvature_scale),
            _binary_job_pack_f32(config.curvature_distance),
            _binary_job_pack_bool(config.curvature_relative_to_bounding_box),
            _binary_job_pack_string(config.curvature_method),
            # MBBJOB33: the dead curvature_sampling_radius f32 that used to sit right
            # here is REMOVED; the old bool in this slot is now Detect Folds, and the
            # Painter-style Self Intersection / Auto Tonemapping / Value Bounds fields
            # follow it. Order MUST match parse_binary_map_config in backend_job_io.cpp.
            _binary_job_pack_i32(config.curvature_secondary_rays),
            _binary_job_pack_bool(config.curvature_detect_folds),
            _binary_job_pack_string(config.curvature_self_intersection),
            _binary_job_pack_bool(config.curvature_auto_tonemapping),
            _binary_job_pack_f32(config.curvature_value_min),
            _binary_job_pack_f32(config.curvature_value_max),
            _binary_job_pack_f32(config.curvature_tonemapping_min),
            _binary_job_pack_f32(config.curvature_tonemapping_max),
            _binary_job_pack_f32(config.thickness_distance),
            _binary_job_pack_f32(config.thickness_min_distance),
            _binary_job_pack_f32(config.thickness_scale),
            _binary_job_pack_f32(config.thickness_gamma),
            _binary_job_pack_bool(config.thickness_dither),
            _binary_job_pack_bool(config.thickness_ignore_groups),
            # Retained binary slot for compatibility with existing backend protocol versions.
            _binary_job_pack_string("RAYCAST"),
            _binary_job_pack_bool(config.thickness_normalization),
            _binary_job_pack_bool(config.thickness_log_response),
            _binary_job_pack_bool(config.density_auto_levels),
            _binary_job_pack_bool(config.density_auto_levels_per_group),
            _binary_job_pack_string(config.id_source),
            _binary_job_pack_string(config.position_mode),
            _binary_job_pack_string(config.position_axis),
            _binary_job_pack_string(config.position_normalization),
            _binary_job_pack_f32(config.position_normalization_scale),
            _binary_job_pack_bool(config.relative_to_bounding_box),
            _binary_job_pack_f32(config.height_inner_distance),
            _binary_job_pack_f32(config.height_outer_distance),
            _binary_job_pack_bool(config.height_dither),
            _binary_job_pack_bool(config.denoising_enabled),
            _binary_job_pack_bool(config.diffusion_dilation_enabled),
            _binary_job_pack_i32(config.diffusion_dilation_iterations),
            _binary_job_pack_f32(config.denoise_strength),
            _binary_job_pack_i32({"HIGH": 6, "BALANCED": 5, "FAST": 4}.get(config.denoise_quality, 6)),
            # MBBJOB13: scene-lighting map transport settings
            _binary_job_pack_string(config.lighting_engine),
            _binary_job_pack_string(config.lighting_quality),
            _binary_job_pack_bool(config.lighting_direct_enabled),
            _binary_job_pack_bool(config.lighting_indirect_enabled),
            _binary_job_pack_bool(config.lighting_world_enabled),
            _binary_job_pack_bool(config.lighting_emission_enabled),
            _binary_job_pack_i32(config.lighting_direct_samples),
            _binary_job_pack_i32(config.lighting_indirect_paths),
            _binary_job_pack_i32(config.lighting_max_bounces),
            _binary_job_pack_f32(config.lighting_noise_threshold),
            # MBBJOB17: normal-derivative curvature soften spread.
            _binary_job_pack_f32(config.curvature_soften),
            # MBBJOB18: Marmoset curvature response calibration, appended AFTER
            # curvature_soften. Order MUST match parse_binary_map_config in backend_job_io.cpp.
            _binary_job_pack_f32(config.mm_power_gamma),
            _binary_job_pack_f32(config.mm_power_amplitude),
            _binary_job_pack_f32(config.mm_power_linear_floor),
            _binary_job_pack_f32(config.mm_power_faint),
            _binary_job_pack_f32(config.mm_convex_boost),
            _binary_job_pack_f32(config.mm_linear_bias),
            # MBBJOB20: material fast-path source transport.
            _binary_job_pack_string(config.material_channel),
            _binary_job_pack_string(config.material_fast_path_image_path),
            # MBBJOB21: direct material-detail composition on artist-facing
            # geometry maps. Appended after the v20 material source fields.
            _binary_job_pack_string(config.material_detail_mode),
            _binary_job_pack_f32(config.material_detail_strength),
            _binary_job_pack_i32(config.material_detail_radius),
            _binary_job_pack_bool(config.material_detail_flip_green),
            # MBBJOB23: tiled (UDIM) material sources. Appended at the tail of the map-config
            # record after the v21 detail fields. Order MUST match parse_binary_map_config in
            # backend_job_io.cpp. Count first, then (udim_tile, image_path) pairs ascending.
            _binary_job_pack_material_source_tiles(config.material_fast_path_tile_images),
            # MBBJOB25: Material IR expression program (JSON blob) + resource PNG paths.
            _binary_job_pack_i32(int(config.material_ir_version)),
            _binary_job_pack_string(config.material_ir_kind),
            _binary_job_pack_string(config.material_ir_fallback_reason),
            _binary_job_pack_string(config.material_ir_program_json),
            _binary_job_pack_u32(len(config.material_ir_resource_paths or [])),
            *(
                _binary_job_pack_string(path)
                for path in (config.material_ir_resource_paths or [])
            ),
            # MBBJOB26: per-material detail bindings. Count first, then one record each,
            # sorted by material name so the payload is deterministic (the bake cache key
            # hashes this blob). Order MUST match parse_binary_map_config.
            _binary_job_pack_material_detail_bindings(config.material_detail_bindings),
            # MBBJOB27: the per-triangle binding-index sidecar path.
            _binary_job_pack_string(config.material_detail_slot_index_image_path),
            # MBBJOB28: resolved per-map Soften. Appended at the tail of the map-config
            # record; order MUST match parse_binary_map_config in backend_job_io.cpp.
            _binary_job_pack_f32(config.output_soften),
            # MBBJOB29: legacy single-source detail UV transform, six f32
            # [a, b, c, d, tx, ty]. Always written (identity when unset) so the
            # record layout stays fixed. Order MUST match parse_binary_map_config.
            _binary_job_pack_uv_transform(config.material_detail_uv_transform),
            # MBBJOB35: ID "Material Color" per-face colours. Count first (0 for every
            # map that carries none), then one record each sorted by object name.
            # Order MUST match parse_binary_map_config in backend_job_io.cpp.
            _binary_job_pack_id_material_meshes(config.id_material_meshes),
            # MBBJOB39: material-detail normal retention / source. Order MUST match
            # parse_binary_map_config in backend_job_io.cpp.
            _binary_job_pack_bool(bool(config.material_normal_retain)),
            _binary_job_pack_string(str(config.material_normal_source_uuid or "")),
            _binary_job_pack_bool(bool(config.material_normal_source_flip_green)),
            # MBBJOB48: per-group Normal composite. Order MUST match parse_binary_map_config.
            _binary_job_pack_bool(bool(config.material_normal_composite)),
            # MBBJOB41: bevel mask (curvature family) / AO bevel-normal mode.
            _binary_job_pack_bool(bool(config.curvature_bevel_mask)),
            _binary_job_pack_u32(int(config.ao_bevel_normal_mode or 0)),
            # MBBJOB42: Complete Lighting controls. Order MUST match parse_binary_map_config.
            _binary_job_pack_bool(bool(config.lighting_occlude_other_groups)),
            _binary_job_pack_f32(float(config.lighting_exposure)),
            _binary_job_pack_string(str(config.lighting_component or "ALL")),
        )
    )


def _binary_job_pack_id_material_meshes(meshes) -> bytes:
    payload = bytearray()
    ordered = sorted(meshes or [], key=lambda entry: str(entry.object_name))
    payload.extend(_binary_job_pack_u32(len(ordered)))
    for entry in ordered:
        payload.extend(_binary_job_pack_string(str(entry.object_name)))
        colors = list(entry.colors or [])
        payload.extend(_binary_job_pack_u32(len(colors)))
        for color in colors:
            payload.extend(_binary_job_pack_vec3(color))
        payload.extend(_binary_job_pack_string(str(entry.slot_index_path or "")))
        payload.extend(_binary_job_pack_u32(int(entry.triangle_count or 0)))
    return bytes(payload)


def _binary_job_pack_uv_transform(values) -> bytes:
    resolved = list(values or [])
    if len(resolved) != 6:
        resolved = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    return b"".join(_binary_job_pack_f32(float(v)) for v in resolved)


def _binary_job_pack_material_detail_bindings(bindings) -> bytes:
    payload = bytearray()
    ordered = sorted(bindings or [], key=lambda entry: str(entry.material_name))
    payload.extend(_binary_job_pack_u32(len(ordered)))
    for entry in ordered:
        payload.extend(_binary_job_pack_string(str(entry.material_name)))
        payload.extend(_binary_job_pack_string(str(entry.image_path)))
        payload.extend(_binary_job_pack_string(str(entry.mode)))
        payload.extend(_binary_job_pack_f32(float(entry.strength)))
        payload.extend(_binary_job_pack_bool(bool(entry.flip_green)))
        # MBBJOB29: per-binding UV transform, six f32 (identity when unset).
        payload.extend(_binary_job_pack_uv_transform(getattr(entry, "uv_transform", None)))
    return bytes(payload)


def _binary_job_pack_material_source_tiles(tiles) -> bytes:
    payload = bytearray()
    ordered = sorted(tiles or [], key=lambda entry: int(entry.udim_tile))
    payload.extend(_binary_job_pack_u32(len(ordered)))
    for entry in ordered:
        payload.extend(_binary_job_pack_i32(int(entry.udim_tile)))
        payload.extend(_binary_job_pack_string(entry.image_path))
    return bytes(payload)


def _binary_job_pack_scene_light(light: SceneLightRecord) -> bytes:
    return b"".join(
        (
            _binary_job_pack_string(light.identity),
            _binary_job_pack_string(light.light_type),
            _binary_job_pack_vec3(light.color),
            _binary_job_pack_f32(light.energy),
            _binary_job_pack_matrix4(light.matrix_world),
            _binary_job_pack_f32(light.radius),
            _binary_job_pack_f32(light.sun_angle),
            _binary_job_pack_f32(light.spot_size),
            _binary_job_pack_f32(light.spot_blend),
            _binary_job_pack_string(light.area_shape),
            _binary_job_pack_f32(light.area_size_x),
            _binary_job_pack_f32(light.area_size_y),
            _binary_job_pack_bool(light.use_shadow),
            _binary_job_pack_f32(light.diffuse_factor),
            _binary_job_pack_bool(light.visible),
            _binary_job_pack_string(light.cache_signature),
            _binary_job_pack_light_links(light),
            _binary_job_pack_f32(light.specular_factor),
            _binary_job_pack_bool(light.visible_diffuse),
            _binary_job_pack_bool(light.visible_glossy),
        )
    )


def _binary_job_pack_light_links(record) -> bytes:
    """MBBJOB44 light-linking sets of a light or emissive object."""
    payload = bytearray()
    for only, names in ((record.receiver_only, record.receiver_objects), (record.blocker_only, record.blocker_objects)):
        payload.extend(_binary_job_pack_bool(only))
        payload.extend(_binary_job_pack_u32(len(names)))
        for name in names:
            payload.extend(_binary_job_pack_string(name))
    return bytes(payload)


def _binary_job_pack_scene_lighting(scene_lighting: SceneLightingConfig | None) -> bytes:
    if scene_lighting is None:
        return _binary_job_pack_bool(False)
    payload = bytearray()
    payload.extend(_binary_job_pack_bool(True))
    payload.extend(_binary_job_pack_u32(scene_lighting.seed))
    payload.extend(_binary_job_pack_u32(len(scene_lighting.lights)))
    for light in scene_lighting.lights:
        payload.extend(_binary_job_pack_scene_light(light))
    world = scene_lighting.world
    payload.extend(_binary_job_pack_string(world.world_mode))
    payload.extend(_binary_job_pack_vec3(world.color))
    payload.extend(_binary_job_pack_f32(world.strength))
    payload.extend(_binary_job_pack_string(world.image_path))
    payload.extend(_binary_job_pack_string(world.cache_signature))
    # MBBJOB14: constant material transport records
    payload.extend(_binary_job_pack_u32(len(scene_lighting.materials)))
    for material in scene_lighting.materials:
        payload.extend(_binary_job_pack_string(material.material_name))
        payload.extend(_binary_job_pack_vec3(material.albedo))
        payload.extend(_binary_job_pack_vec3(material.emission))
        payload.extend(_binary_job_pack_bool(material.has_textured_albedo))
        payload.extend(_binary_job_pack_bool(material.has_textured_emission))
        payload.extend(_binary_job_pack_string(material.cache_signature))
        # MBBJOB43: albedo texture (size, then size*size RGB floats).
        texture_size = int(material.albedo_texture_size or 0)
        texels = list(material.albedo_texture or ())
        if texture_size <= 0 or len(texels) != texture_size * texture_size * 3:
            texture_size, texels = 0, []
        payload.extend(_binary_job_pack_u32(texture_size))
        if texels:
            payload.extend(struct.pack(f"<{len(texels)}f", *texels))
        # MBBJOB46: specular inputs, then the roughness / metallic grids (count-prefixed).
        payload.extend(_binary_job_pack_f32(float(material.roughness)))
        payload.extend(_binary_job_pack_f32(float(material.metallic)))
        payload.extend(_binary_job_pack_f32(float(material.specular_ior_level)))
        payload.extend(_binary_job_pack_f32(float(material.ior)))
        payload.extend(_binary_job_pack_vec3(material.specular_tint))
        spec_size = int(material.specular_texture_size or 0)
        payload.extend(_binary_job_pack_u32(spec_size))
        for grid in (material.roughness_texture, material.metallic_texture):
            values = list(grid or ()) if spec_size and len(grid or ()) == spec_size * spec_size else []
            payload.extend(_binary_job_pack_u32(len(values)))
            if values:
                payload.extend(struct.pack(f"<{len(values)}f", *values))
    # MBBJOB44: light linking of emissive mesh objects.
    payload.extend(_binary_job_pack_u32(len(scene_lighting.emitter_links)))
    for link in scene_lighting.emitter_links:
        payload.extend(_binary_job_pack_string(link.object_name))
        payload.extend(_binary_job_pack_light_links(link))
        payload.extend(_binary_job_pack_string(link.cache_signature))
    payload.extend(_binary_job_pack_f32(scene_lighting.cycles_filter_glossy))
    payload.extend(_binary_job_pack_f32(scene_lighting.cycles_clamp_indirect))
    return bytes(payload)


def _binary_job_pack_project_info(project: BakeProjectInfo) -> bytes:
    return b"".join(
        (
            _binary_job_pack_string(project.name),
            _binary_job_pack_string(project.output_root),
            _binary_job_pack_string(project.workspace),
            _binary_job_pack_i32(project.resolution_width),
            _binary_job_pack_i32(project.resolution_height),
            _binary_job_pack_i32(project.bit_depth),
            _binary_job_pack_i32(project.margin),
            _binary_job_pack_string(constants.normalize_tangent_basis(project.tangent_basis)),
            _binary_job_pack_string(project.output_preset),
            _binary_job_pack_string(project.bake_mode),
            _binary_job_pack_string(project.anti_aliasing),
            _binary_job_pack_string(project.execution_backend),
            _binary_job_pack_string(project.image_format),
            # MBBJOB16: appended after image_format.
            _binary_job_pack_i32(int(project.aa_samples)),
            # MBBJOB18: job-level Marmoset AA jitter scale, appended after aa_samples.
            _binary_job_pack_f32(float(project.mm_aa_jitter_scale)),
            # MBBJOB24: shared high-poly opacity semantics.
            _binary_job_pack_bool(bool(project.respect_opacity)),
            # MBBJOB31: Live Reproject state, appended after respect_opacity. The
            # backend only captures a reprojection baseline when this is set.
            # Live Reproject no longer uses the worker's baseline capture: the addon
            # transfers textures between UV layouts itself. Always False; the field
            # stays so the job layout (MBBJOB magic) is unchanged.
            _binary_job_pack_bool(False),
        )
    )


def _binary_job_pack_debug_view(debug_view: DebugViewConfig | None) -> bytes:
    if debug_view is None:
        return _binary_job_pack_bool(False)
    return b"".join(
        (
            _binary_job_pack_bool(True),
            _binary_job_pack_i32(debug_view.viewport_width),
            _binary_job_pack_i32(debug_view.viewport_height),
            _binary_job_pack_string(debug_view.view_signature),
            _binary_job_pack_matrix4(debug_view.view_projection),
        )
    )


def _binary_job_pack_group_config(group: BakeGroupConfig) -> bytes:
    payload = bytearray()
    payload.extend(_binary_job_pack_string(group.name))
    payload.extend(_binary_job_pack_string(group.cage_mode))
    payload.extend(_binary_job_pack_f32(group.cage_offset))
    payload.extend(_binary_job_pack_bool(group.average_normals))
    payload.extend(_binary_job_pack_bool(group.ignore_backface))
    payload.extend(_binary_job_pack_bool(group.match_by_isolation))
    payload.extend(_binary_job_pack_bool(group.debug_heatmap_enabled))
    payload.extend(_binary_job_pack_string(group.id_collection_name))
    payload.extend(_binary_job_pack_string(group.id_color_set_name))
    payload.extend(_binary_job_pack_string(group.texture_set))
    payload.extend(_binary_job_pack_u32(len(group.low_meshes)))
    for ref in group.low_meshes:
        payload.extend(_binary_job_pack_mesh_ref(ref))
    payload.extend(_binary_job_pack_u32(len(group.high_meshes)))
    for ref in group.high_meshes:
        payload.extend(_binary_job_pack_mesh_ref(ref))
    payload.extend(_binary_job_pack_u32(len(group.cage_meshes)))
    for ref in group.cage_meshes:
        payload.extend(_binary_job_pack_mesh_ref(ref))
    payload.extend(_binary_job_pack_u32(len(group.outputs)))
    for target in group.outputs:
        payload.extend(_binary_job_pack_output_target(target))
    payload.extend(_binary_job_pack_u32(len(group.dirty_uv_rects)))
    for rect in group.dirty_uv_rects:
        payload.extend(_binary_job_pack_dirty_uv_rect(rect))
    # MBBJOB36: Rear Distance, appended after the dirty UV rects.
    payload.extend(_binary_job_pack_f32(max(0.0, float(group.projection_rear_distance))))
    # MBBJOB37: per-pixel Paint Skew correction maps.
    payload.extend(_binary_job_pack_u32(len(group.skew_correction_maps)))
    for ref in group.skew_correction_maps:
        payload.extend(_binary_job_pack_i32(int(ref.udim_tile)))
        payload.extend(_binary_job_pack_string(str(ref.path)))
        payload.extend(_binary_job_pack_i32(int(ref.width)))
        payload.extend(_binary_job_pack_i32(int(ref.height)))
    # MBBJOB38: high meshes with Casts AO off.
    payload.extend(_binary_job_pack_u32(len(group.ao_non_caster_objects)))
    for name in group.ao_non_caster_objects:
        payload.extend(_binary_job_pack_string(str(name)))
    # MBBJOB40: straight projection rays at convex hard edges (Bevel-shader highs).
    payload.extend(_binary_job_pack_bool(bool(group.straight_convex_rays)))
    # MBBJOB45: Scene Blockers group.
    payload.extend(_binary_job_pack_bool(bool(group.occluder_only)))
    payload.extend(_binary_job_pack_bool(bool(group.occluder_shadows)))
    payload.extend(_binary_job_pack_bool(bool(group.occluder_bounces)))
    return bytes(payload)


def _build_binary_job_payload(job: BakeJob) -> bytes:
    payload = bytearray()
    payload.extend(_BINARY_JOB_MAGIC)
    payload.extend(_binary_job_pack_string(job.version))
    payload.extend(_binary_job_pack_string(job.job_id))
    payload.extend(_binary_job_pack_string(job.created_at))
    payload.extend(_binary_job_pack_string(job.progress_path))
    payload.extend(_binary_job_pack_project_info(job.project))
    payload.extend(_binary_job_pack_u32(len(job.maps)))
    for map_config in job.maps:
        payload.extend(_binary_job_pack_map_config(map_config))
    payload.extend(_binary_job_pack_u32(len(job.groups)))
    for group in job.groups:
        payload.extend(_binary_job_pack_group_config(group))
    payload.extend(_binary_job_pack_debug_view(job.debug_view))
    payload.extend(_binary_job_pack_bool(job.debug_heatmap_blob_enabled))
    payload.extend(_binary_job_pack_scene_lighting(job.scene_lighting))
    return bytes(payload)


def write_binary_job(path: str | Path, job: BakeJob) -> Path:
    job_path = binary_job_path(path)
    job_path.write_bytes(_build_binary_job_payload(job))
    _BINARY_JOB_RETRY_OWNERS[_binary_job_retry_key(job_path)] = job
    return job_path


_BINARY_JOB_RETRY_OWNERS: dict[str, BakeJob] = {}


def _binary_job_retry_key(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def binary_job_retry_owner(path: str | Path) -> BakeJob | None:
    """Return the in-memory job needed for a transport-only retry.

    The binary protocol is intentionally write-only on the addon side. Keeping
    the small job model beside its path avoids reparsing it and, importantly,
    does not retain any mesh payload.
    """
    return _BINARY_JOB_RETRY_OWNERS.get(_binary_job_retry_key(path))


def forget_binary_job_retry_owner(path: str | Path) -> None:
    _BINARY_JOB_RETRY_OWNERS.pop(_binary_job_retry_key(path), None)


def write_job(path: str | Path, job: BakeJob) -> Path:
    job_path = Path(path)
    payload = job.to_dict()
    for entry in payload.get("maps") or ():
        entry["map_type"] = _wire_map_type(entry["map_type"])
    for group in payload["groups"]:
        for key in ("outputs", "dirty_uv_rects"):
            for entry in group.get(key) or ():
                entry["map_type"] = _wire_map_type(entry["map_type"])
        for role in ("low_meshes", "high_meshes", "cage_meshes"):
            for mesh in group.get(role, []):
                for key in ("matrix_world", "world_to_object"):
                    # Omitted transforms mean identity in the JSON reader, just
                    # as empty transforms do in the binary writer. JSON [] is
                    # instead rejected as a malformed 4x4 matrix.
                    if mesh.get(key) == []:
                        mesh.pop(key)
    job_path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    return job_path


_PROGRESS_REPLACE_BUDGET_SECONDS = 1.0
_PROGRESS_REPLACE_DELAY_SECONDS = 0.01
_progress_temp_serial = itertools.count()


def _open_text_shared(path: str | Path):
    """Open ``path`` for text reading with FILE_SHARE_DELETE on Windows.

    Python's ``open`` shares read/write but not delete, so while a reader holds
    progress.json open the backend's MoveFileEx replace fails with "Access is
    denied". Opening with delete sharing lets the replace go through (the reader
    keeps its handle on the old contents). Other platforms use plain ``open``.
    """
    if os.name == "nt":
        try:
            import ctypes
            import msvcrt
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateFileW.restype = wintypes.HANDLE
            kernel32.CreateFileW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
            ]
            generic_read = 0x80000000
            share_all = 0x1 | 0x2 | 0x4
            open_existing = 3
            handle = kernel32.CreateFileW(str(path), generic_read, share_all, None, open_existing, 0x80, None)
            invalid = ctypes.c_void_p(-1).value
            if handle is None or handle == invalid:
                error = ctypes.get_last_error()
                if error in (2, 3):
                    raise FileNotFoundError(error, "progress file not found", str(path))
                raise PermissionError(error, "progress file could not be opened", str(path))
            fd = msvcrt.open_osfhandle(int(handle), os.O_RDONLY)
            return os.fdopen(fd, "r", encoding="utf-8")
        except (FileNotFoundError, PermissionError):
            raise
        except Exception:
            pass
    return open(path, "r", encoding="utf-8")


def _replace_file(source: Path, destination: Path) -> None:
    """Replace ``destination`` with ``source``, tolerating delete-sharing readers on Windows.

    ``os.replace`` (MoveFileEx) fails with ERROR_ACCESS_DENIED while ANY handle is open on
    the destination, even one opened with FILE_SHARE_DELETE; ReplaceFileW swaps the contents
    in place and succeeds against those readers. Falls back to ``os.replace``.
    """
    if os.name == "nt" and destination.exists():
        try:
            import ctypes

            replace_file = ctypes.WinDLL("kernel32", use_last_error=True).ReplaceFileW
            replace_file.restype = ctypes.c_int
            replace_file.argtypes = [
                ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p,
            ]
            # REPLACEFILE_IGNORE_MERGE_ERRORS = 0x2
            if replace_file(str(destination), str(source), None, 0x2, None, None):
                return
        except Exception:
            pass
    os.replace(source, destination)


def write_progress(path: str | Path, progress: BakeProgress) -> Path:
    """Write progress.json atomically; progress is advisory so a failure never raises.

    Written through a unique temp file and replaced into place, retrying
    ERROR_ACCESS_DENIED / sharing violations (another process briefly holding the
    target without delete sharing) for about a second. If the replace never
    succeeds the failure is logged and the bake carries on: the next progress
    write or the backend's own snapshot supersedes it.
    """
    progress_path = Path(path)
    text = json.dumps(progress.to_dict(), indent=2, sort_keys=True, allow_nan=False)
    temp_path = progress_path.with_name(f"{progress_path.name}.py{os.getpid()}.{next(_progress_temp_serial)}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        deadline = time.monotonic() + _PROGRESS_REPLACE_BUDGET_SECONDS
        while True:
            try:
                _replace_file(temp_path, progress_path)
                return progress_path
            except PermissionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(_PROGRESS_REPLACE_DELAY_SECONDS)
    except Exception as exc:
        print(f"[MasterBaker] progress write skipped for {progress_path}: {exc}")
        try:
            temp_path.unlink()
        except OSError:
            pass
    return progress_path


def _dataclass_from_payload(record_type, item):
    """Build ``record_type`` from a JSON dict, ignoring fields it does not declare.

    The backend and addon ship as one artifact, so a genuinely unknown key means a partly
    updated working tree rather than a version mismatch -- but a bare ``record_type(**item)``
    turns that into a TypeError that reads as a corrupt progress file. Dropping unknown keys
    keeps a progress-field addition a one-sided edit.
    """
    if not isinstance(item, dict):
        return record_type()
    known = {declared.name for declared in dataclass_fields(record_type)}
    return record_type(**{key: value for key, value in item.items() if key in known})


def load_progress(path: str | Path) -> BakeProgress:
    with _open_text_shared(path) as handle:
        payload = json.loads(handle.read())
    produced_files = [
        _dataclass_from_payload(ProducedFile, item) for item in payload.get("produced_files", [])
    ]
    miss_diagnostics = [
        _dataclass_from_payload(BakeMissDiagnostic, item)
        for item in payload.get("miss_diagnostics", [])
    ]
    return BakeProgress(
        version=payload.get("version", constants.PROTOCOL_VERSION),
        status=payload.get("status", constants.STATUS_IDLE),
        message=payload.get("message", ""),
        percent=float(payload.get("percent", 0.0)),
        stage_percent=float(payload.get("stage_percent", -1.0)),
        stage=payload.get("stage", ""),
        active_group=payload.get("active_group", ""),
        active_map=payload.get("active_map", ""),
        active_maps=list(payload.get("active_maps", [])),
        produced_files=produced_files,
        miss_diagnostics=miss_diagnostics,
        warnings=list(payload.get("warnings", [])),
        errors=list(payload.get("errors", [])),
    )


def _read_heatmap_blob_segment(raw: bytes, blob_path: Path, cursor: int, vec3_count: int) -> tuple[array, int]:
    byte_count = int(vec3_count) * 12
    end = cursor + byte_count
    if end > len(raw):
        raise ValueError(f"Heatmap blob payload is truncated: {blob_path}")
    values = array("f")
    values.frombytes(raw[cursor:end])
    if sys.byteorder != "little":
        values.byteswap()
    return values, end


def _load_heatmap_blob(path: str | Path) -> tuple[array, array, array, array, array, array]:
    blob_path = Path(path)
    raw = blob_path.read_bytes()
    header_format = "<8sIII"
    header_size = struct.calcsize(header_format)
    if len(raw) < header_size:
        raise ValueError(f"Heatmap blob header is incomplete: {blob_path}")
    magic, low_count, medium_count, high_count = struct.unpack_from(header_format, raw, 0)
    if magic not in {_HEATMAP_BLOB_MAGIC_V1, _HEATMAP_BLOB_MAGIC_V2}:
        raise ValueError(f"Heatmap blob magic mismatch: {blob_path}")
    counts = (low_count, medium_count, high_count)
    cursor = header_size
    position_segments: list[array] = []
    normal_segments: list[array] = []
    for vec3_count in counts:
        position_values, cursor = _read_heatmap_blob_segment(raw, blob_path, cursor, vec3_count)
        position_segments.append(position_values)
        if magic == _HEATMAP_BLOB_MAGIC_V2:
            normal_values, cursor = _read_heatmap_blob_segment(raw, blob_path, cursor, vec3_count)
        else:
            normal_values = array("f")
        normal_segments.append(normal_values)
    if cursor != len(raw):
        raise ValueError(f"Heatmap blob payload has unexpected trailing bytes: {blob_path}")
    return (
        position_segments[0],
        normal_segments[0],
        position_segments[1],
        normal_segments[1],
        position_segments[2],
        normal_segments[2],
    )


def debug_overlay_vec3_count(positions) -> int:
    if isinstance(positions, array):
        return len(positions) // 3
    return len(positions or [])


def debug_overlay_triangle_count(positions) -> int:
    return debug_overlay_vec3_count(positions) // 3


def debug_overlay_segment_count(positions) -> int:
    return debug_overlay_vec3_count(positions) // 2


def load_debug_overlay_result(path: str | Path) -> DebugOverlayResult:
    result_path = Path(path)
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    heatmap_blob_path = str(payload.get("heatmap_blob_path", "") or "")
    heatmap_low_fill_positions = list(payload.get("heatmap_low_fill_positions", []) or [])
    heatmap_low_fill_normals = list(payload.get("heatmap_low_fill_normals", []) or [])
    heatmap_medium_fill_positions = list(payload.get("heatmap_medium_fill_positions", []) or [])
    heatmap_medium_fill_normals = list(payload.get("heatmap_medium_fill_normals", []) or [])
    heatmap_high_fill_positions = list(payload.get("heatmap_high_fill_positions", []) or [])
    heatmap_high_fill_normals = list(payload.get("heatmap_high_fill_normals", []) or [])
    resolved_blob_path = Path()
    if heatmap_blob_path.strip():
        resolved_blob_path = Path(heatmap_blob_path)
        if not resolved_blob_path.is_absolute():
            resolved_blob_path = result_path.parent / resolved_blob_path
        (
            heatmap_low_fill_positions,
            heatmap_low_fill_normals,
            heatmap_medium_fill_positions,
            heatmap_medium_fill_normals,
            heatmap_high_fill_positions,
            heatmap_high_fill_normals,
        ) = _load_heatmap_blob(resolved_blob_path)
    return DebugOverlayResult(
        version=payload.get("version", constants.PROTOCOL_VERSION),
        group_name=payload.get("group_name", ""),
        high_ref_fill_positions=list(payload.get("high_ref_fill_positions", []) or []),
        heatmap_low_fill_positions=heatmap_low_fill_positions,
        heatmap_low_fill_normals=heatmap_low_fill_normals,
        heatmap_medium_fill_positions=heatmap_medium_fill_positions,
        heatmap_medium_fill_normals=heatmap_medium_fill_normals,
        heatmap_high_fill_positions=heatmap_high_fill_positions,
        heatmap_high_fill_normals=heatmap_high_fill_normals,
        ray_miss_line_positions=list(payload.get("ray_miss_line_positions", []) or []),
        heatmap_blob_path=str(resolved_blob_path) if heatmap_blob_path.strip() else "",
        heatmap_image_path=str(payload.get("heatmap_image_path", "") or ""),
        heatmap_image_width=int(payload.get("heatmap_image_width", 0) or 0),
        heatmap_image_height=int(payload.get("heatmap_image_height", 0) or 0),
        view_signature=str(payload.get("view_signature", "") or ""),
    )
