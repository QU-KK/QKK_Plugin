from __future__ import annotations

ADDON_PACKAGE_NAME = "FyrBaker"
ADDON_ID = "fyr_baker"
UI_TAB_NAME = "Fyr Baker"

IMAGE_CHANNEL_COLOR_ALPHA = "COLOR_ALPHA"
IMAGE_CHANNEL_COLOR = "COLOR"
IMAGE_CHANNEL_ALPHA = "ALPHA"
IMAGE_CHANNEL_RED = "RED"
IMAGE_CHANNEL_GREEN = "GREEN"
IMAGE_CHANNEL_BLUE = "BLUE"

IMAGE_CHANNEL_MODE_ITEMS = (
    (IMAGE_CHANNEL_COLOR, "RGB", "Show RGB color channels"),
    (IMAGE_CHANNEL_COLOR_ALPHA, "RGBA", "Show RGB plus alpha"),
    (IMAGE_CHANNEL_RED, "R", "Show red channel only"),
    (IMAGE_CHANNEL_GREEN, "G", "Show green channel only"),
    (IMAGE_CHANNEL_BLUE, "B", "Show blue channel only"),
    (IMAGE_CHANNEL_ALPHA, "A", "Show alpha only"),
)
IMAGE_EDITOR_MAX_MIP_LEVEL = 5
PROTOCOL_VERSION = "1.0"

# Stored bake-project state schema. Bump when a change requires rewriting values
# already saved in a .blend, and add the matching step to
# properties.migrate_project_schema (which is gated on the per-project
# schema_version stamp so each step runs exactly once).
#   1 — neutralize Black/White Point on legacy CAVITY rows (the backend output-range
#       pass never applied to Cavity, so the stored 0.4/0.6 was inert legacy noise).
#   3 — upgrade legacy tangent-Normal rows still holding the OPENGL enum default to the
#       DirectX default format ONCE, instead of re-deriving it on every read
#       (which silently overrode an explicit OpenGL choice — QA bug #4).
#   4 — clear the dangling "Default" texture-set link left by the old property default.
#       It had no backing texture_sets entry, so it only ever served to name outputs
#       Default_*.tga instead of after the bake group.
#   5 — reset the retired "Blender" tangent basis to MikkTSpace.
#   6 — MBBJOB33 curvature probe fields: the old Self Intersection bool moves to
#       Detect Folds, the probe scope enum resets to Same Group, and the new
#       Secondary Rays / Auto Tonemapping / Value Bounds defaults are stamped.
#   7 — pin Automatic on groups that never stored a cage mode, before the default
#       became Distance (Painter / Marmoset).
PROJECT_SCHEMA_VERSION = 8

CACHE_ROOT_ENV_VAR = "FYR_BAKER_CACHE_ROOT"
DISABLE_PERSISTENT_CACHE_ENV_VAR = "FYR_BAKER_DISABLE_PERSISTENT_CACHE"
PERSISTENT_CACHE_BUDGET_ENV_VAR = "FYR_BAKER_CACHE_BUDGET_GB"
PERSISTENT_CACHE_BUDGET_GB_DEFAULT = 12

# Startup sweep of FyrBaker-owned entries left behind in the system temp dir
# (loose %TEMP% dirs from crashed/aborted sessions, the standalone app, the
# benchmark harness, etc.). Only entries whose name matches an owned prefix and
# whose mtime is older than this many hours are removed — user files are never
# touched. Set FYR_BAKER_TEMP_SWEEP_AGE_HOURS to tune, or FYR_BAKER_DISABLE_TEMP_SWEEP
# to disable the sweep entirely.
TEMP_SWEEP_AGE_HOURS_ENV_VAR = "FYR_BAKER_TEMP_SWEEP_AGE_HOURS"
TEMP_SWEEP_AGE_HOURS_DEFAULT = 48
DISABLE_TEMP_SWEEP_ENV_VAR = "FYR_BAKER_DISABLE_TEMP_SWEEP"

DISABLE_BACKEND_PREWARM_ENV_VAR = "FYR_BAKER_DISABLE_PREWARM"

BACKEND_PREWARM_OFF = "OFF"
BACKEND_PREWARM_ON_PROJECT_DETECTED = "ON_PROJECT_DETECTED"
BACKEND_PREWARM_ON_ADDON_LOAD = "ON_ADDON_LOAD"

BACKEND_PREWARM_MODE_ITEMS = (
    (BACKEND_PREWARM_OFF,
     "Off",
     "Start the bake worker only when a bake begins. Uses the fewest resources while idle, but makes the first bake slower"),
    (BACKEND_PREWARM_ON_PROJECT_DETECTED,
     "When Project Detected",
     "Start the bake worker in the background when a configured bake project is detected. Recommended"),
    (BACKEND_PREWARM_ON_ADDON_LOAD,
     "On Addon Load",
     "Start the bake worker when Fyr Baker loads. Gives the first bake the largest head start, but uses memory and GPU resources for the entire Blender session"),
)

SIDEBAR_DASHBOARD = "DASHBOARD"
SIDEBAR_BAKE = "BAKE"
SIDEBAR_CAGE = "CAGE"
SIDEBAR_MESHES = "MESHES"
SIDEBAR_MAPS = "MAPS"
SIDEBAR_PREVIEW = "PREVIEW"
SIDEBAR_OUTPUT = "OUTPUT"
SIDEBAR_SETUP = "SETUP"

# Setup is no longer a nav section — project management + per-item settings moved
# into the hierarchy and the context panel below it. SIDEBAR_SETUP is retained as a
# constant so persisted state normalizes cleanly (see sidebar_state legacy map).
SIDEBAR_SECTION_ITEMS = (
    (SIDEBAR_MESHES, "Meshes", "Texture sets, bake groups, and assigned meshes"),
    (SIDEBAR_CAGE, "Cage", "Cage controls and viewport overlay options"),
    (SIDEBAR_MAPS, "Maps", "Texture map stack"),
    (SIDEBAR_OUTPUT, "Output", "Output folder, resolution, and image format"),
    (SIDEBAR_PREVIEW, "Preview", "Preview baked maps and combined materials on low-poly meshes"),
)

SIDEBAR_SECTION_TOOLTIPS = {
    SIDEBAR_MESHES: "Show texture sets, bake groups, and assigned meshes. Shift-click to show or hide multiple sections.",
    SIDEBAR_CAGE: "Show cage controls and viewport overlay options. Shift-click to show or hide multiple sections.",
    SIDEBAR_MAPS: "Show the texture map stack. Shift-click to show or hide multiple sections.",
    SIDEBAR_OUTPUT: "Show the output folder, resolution, and image format. Shift-click to show or hide multiple sections.",
    SIDEBAR_PREVIEW: "Preview baked maps and combined materials on the low-poly meshes. Shift-click to show or hide multiple sections.",
    SIDEBAR_SETUP: "Show bake group assignment, tagging, auto-match, and setup diagnostics. Shift-click to show or hide multiple sections.",
}

# Scope at which cage settings edited in the cage panel are applied: only the
# active bake group, every group sharing its texture set, or every group in the
# project. Session-only (see MasterBakerUiState.cage_settings_scope) so a saved
# file never re-applies a broad scope on load.
CAGE_SCOPE_BAKE_GROUP = "BAKE_GROUP"
CAGE_SCOPE_SELECTED = "SELECTED"
CAGE_SCOPE_TEXTURE_SET = "TEXTURE_SET"
CAGE_SCOPE_GLOBAL = "GLOBAL"

CAGE_SETTINGS_SCOPE_ITEMS = (
    (CAGE_SCOPE_BAKE_GROUP, "Bake Group", "Cage settings apply only to the active bake group", "OBJECT_DATA", 0),
    (CAGE_SCOPE_SELECTED, "Selected", "Editing a cage setting applies it to every bake group that owns a selected low-poly mesh; with nothing relevant selected only the active group changes", "RESTRICT_SELECT_OFF", 3),
    (CAGE_SCOPE_TEXTURE_SET, "Texture Set", "Editing a cage setting applies it to every bake group in the active group's texture set", "TEXTURE", 1),
    (CAGE_SCOPE_GLOBAL, "Global", "Editing a cage setting applies it to every bake group in the whole bake project", "WORLD", 2),
)

PBR_PREVIEW_NORMAL_TANGENT = "TANGENT_NORMAL"
PBR_PREVIEW_NORMAL_BENT = "BENT_NORMAL"

PBR_PREVIEW_NORMAL_SOURCE_ITEMS = (
    (PBR_PREVIEW_NORMAL_TANGENT, "Tangent Normal", "Use the baked tangent-space normal map"),
    (PBR_PREVIEW_NORMAL_BENT, "Bent Normal", "Use the baked bent-normal map"),
)

BAKE_PANEL_SETTINGS = "SETTINGS"
BAKE_PANEL_OUTPUTS = "OUTPUTS"

BAKE_PANEL_SECTION_ITEMS = (
    (BAKE_PANEL_SETTINGS, "Settings", "Project bake settings and active bake group UV selection"),
    (BAKE_PANEL_OUTPUTS, "Outputs", "Browse tracked outputs and open related files"),
)

# Name prefix of the transient preview material the "preview on low" workflow
# applies to low meshes. Single source of truth — consumers that need to *ignore*
# preview materials (output naming, bake cache keys, dirty tracking) must match on
# this, not a hard-coded literal, so a rebrand can't silently strand a filter.
PREVIEW_MATERIAL_NAME_PREFIX = "_FYR_BAKER_PREVIEW_MATERIAL"

# How a texture set's output file name is derived.
TEXTURE_SET_NAME_CUSTOM = "CUSTOM"
TEXTURE_SET_NAME_BLEND_FILE = "BLEND_FILE"
TEXTURE_SET_NAME_MATERIAL = "MATERIAL"

TEXTURE_SET_NAME_MODE_ITEMS = (
    (TEXTURE_SET_NAME_CUSTOM, "Custom Name", "Use the name typed into the box"),
    (TEXTURE_SET_NAME_BLEND_FILE, "Based on .blend File", "Name outputs after the current .blend file"),
    (TEXTURE_SET_NAME_MATERIAL, "Based on Material", "Name outputs after the material on the texture set's low-poly meshes"),
)

# How the auto-build / create-from-selection flow assigns texture sets to the
# groups it produces.
AUTO_TEXTURE_SET_PER_GROUP = "PER_GROUP"
AUTO_TEXTURE_SET_COMBINED = "COMBINED"
AUTO_TEXTURE_SET_PER_MATERIAL = "PER_MATERIAL"

AUTO_TEXTURE_SET_MODE_ITEMS = (
    (AUTO_TEXTURE_SET_PER_GROUP, "Set Per Bake Group", "Give each bake group its own texture set"),
    (AUTO_TEXTURE_SET_COMBINED, "One Combined Set", "Assign every bake group to a single shared texture set"),
    (AUTO_TEXTURE_SET_PER_MATERIAL, "Set Per Material", "Group meshes into texture sets by the material on their low-poly mesh"),
)

# How automatic grouping splits meshes into bake groups. PREFIX is the naming model
# (every part of one name prefix bakes as one group); PART gives each low-poly mesh
# its own group, paired with the high-poly meshes that share its name, while the
# parts of one prefix keep sharing a texture set (so they still batch on the GPU).
AUTO_GROUP_GRANULARITY_PREFIX = "PREFIX"
AUTO_GROUP_GRANULARITY_PART = "PART"

AUTO_GROUP_GRANULARITY_ITEMS = (
    (
        AUTO_GROUP_GRANULARITY_PREFIX,
        "Group Per Name Prefix",
        "One bake group per shared name prefix; every part of the prefix bakes together",
    ),
    (
        AUTO_GROUP_GRANULARITY_PART,
        "Group Per Part",
        "One bake group per low-poly mesh, paired with the high-poly meshes that share its "
        "name; the parts of one prefix share a texture set",
    ),
)

# How a bake project relates to the Outliner. Bake membership is ALWAYS the group's
# role slots; the collections are only a mirror of it. FYR builds and maintains a
# <Project>/<Group>/<Group>_Low|_High|_Cage scaffold and links each assigned object
# into it (the default, and the only behavior before this setting existed). EXISTING
# leaves every object in the collections the artist made and never creates, links,
# renames or deletes a collection for the project.
COLLECTION_MODE_FYR = "FYR"
COLLECTION_MODE_EXISTING = "EXISTING"

COLLECTION_MODE_ITEMS = (
    (
        COLLECTION_MODE_FYR,
        "Create Fyr Collections",
        "Fyr organizes each bake group into its own Project, Group, Low, High and Cage collections",
    ),
    (
        COLLECTION_MODE_EXISTING,
        "Use My Collections",
        "Fyr leaves your objects in the collections you made and does not create or link any collections",
    ),
)

# In PREFIX mode Auto-Build still splits a prefix whose high-poly meshes total more
# triangles than this into per-part groups. A 20-part scythe (41.8 M triangles) grouped
# as one prefix loses the GPU device or fails its VRAM preflight as one scene; as 20
# groups in one texture set it bakes in four DXR batches. Same order as the Cycles
# recovery cap: one hardware-RT scene of this size needs about 4 GB of VRAM.
AUTO_GROUP_SPLIT_HIGH_TRIANGLES = 16_000_000

# Which hierarchy item drives the context panel below the tree.
HIERARCHY_FOCUS_GROUP = "GROUP"
HIERARCHY_FOCUS_TEXTURE_SET = "TEXTURE_SET"

HIERARCHY_FOCUS_ITEMS = (
    (HIERARCHY_FOCUS_GROUP, "Bake Group", "The active bake group drives the setup panel"),
    (HIERARCHY_FOCUS_TEXTURE_SET, "Texture Set", "The active texture set drives the setup panel"),
)

BAKE_PANEL_SECTION_TOOLTIPS = {
    BAKE_PANEL_SETTINGS: "Show bake settings that affect the next rebake.",
    BAKE_PANEL_OUTPUTS: "Show tracked outputs and output-related actions.",
}

MAP_NORMAL = "NORMAL"
MAP_OBJECT_NORMAL = "OBJECT_NORMAL"
MAP_WORLD_NORMAL = "WORLD_NORMAL"
MAP_AO = "AO"
MAP_CURVATURE = "CURVATURE"
MAP_THICKNESS = "THICKNESS"
MAP_DENSITY = "DENSITY"
MAP_CAVITY = "CAVITY"
MAP_CONCAVE = "CONCAVE"
MAP_CONVEX = "CONVEX"
MAP_OPACITY = "OPACITY"
MAP_POSITION = "POSITION"
MAP_VERTEX_COLOR = "VERTEX_COLOR"
MAP_BENT_NORMAL = "BENT_NORMAL"
MAP_HEIGHT = "HEIGHT"
MAP_ID = "ID"
MAP_ENV_LIGHT = "ENV_LIGHT"
# Any named mesh attribute, remapped into 0..1. The backend bakes it as VERTEX_COLOR
# over a different corner colour stream (see addon/color_stream.py).
MAP_ATTRIBUTE = "ATTRIBUTE"
# The low poly's UV edges as lines, drawn by the addon (addon/derived_outputs.py); the
# backend never sees this row.
MAP_WIREFRAME = "WIREFRAME"
# Effective type of a tangent Normal row whose Output is Derivative: the slopes
# (-x/z, -y/z) of the final tangent normal. Baked by the backend as NORMAL into a hidden
# source file, then converted by addon/derived_outputs.py. Never a stored row type.
MAP_DERIVATIVE = "DERIVATIVE"
NORMAL_ENCODING_NORMAL = "NORMAL"
NORMAL_ENCODING_DERIVATIVE = "DERIVATIVE"
NORMAL_ENCODING_ITEMS = (
    (NORMAL_ENCODING_NORMAL, "Normal", "Write the tangent-space normal map"),
    (NORMAL_ENCODING_DERIVATIVE, "Derivative",
     "Write the surface slopes (-x/z, -y/z) of the tangent normal: R = slope along U, G = slope along V. Derivative maps add together correctly, for layered and tangent-free shaders"),
)
DEFAULT_DERIVATIVE_MAX_SLOPE = 2.0
DEFAULT_WIREFRAME_LINE_WIDTH = 1.5
# Add-map shortcut: a tangent Normal row with Output = Derivative. Never stored on rows.
SHORTCUT_DERIVATIVE = "_DERIVATIVE"
DEFAULT_AO_OUTPUT_MIN = 0.02
# AO "Use Bevel Normal": shade AO from the Normal map's material detail (Bevel shader).
# AUTO is resolved in the addon (a Bevel node in the high normal graph -> CONVEX,
# otherwise OFF) before the job is built. The job carries the index
# (BakeMapConfig.ao_bevel_normal_mode): 0 off, 1 all edges, 2 convex edges.
AO_BEVEL_NORMAL_AUTO = "AUTO"
AO_BEVEL_NORMAL_OFF = "OFF"
AO_BEVEL_NORMAL_ALL = "ALL"
AO_BEVEL_NORMAL_CONVEX = "CONVEX"
AO_BEVEL_NORMAL_JOB_MODES = {AO_BEVEL_NORMAL_OFF: 0, AO_BEVEL_NORMAL_ALL: 1, AO_BEVEL_NORMAL_CONVEX: 2}
MAP_LIGHTING = "LIGHTING"
MAP_LIT_COLOR = "LIT_COLOR"
# Output-only effective types of a Scene Lighting row (never stored row types, never on
# the wire): the direct part of the lighting and the bounced part (Marmoset's Diffuse
# Lighting and Indirect Lighting). Both bake as LIGHTING with lighting_component set.
MAP_DIRECT_LIGHTING = "DIRECT_LIGHTING"
MAP_INDIRECT_LIGHTING = "INDIRECT_LIGHTING"
# Glossy reflections (Cycles' Glossy pass with color), viewed straight on: Marmoset's
# Specular Lighting. Bakes as LIGHTING with lighting_component SPECULAR.
MAP_SPECULAR_LIGHTING = "SPECULAR_LIGHTING"
# Consolidated picker entry for scene-lighting maps. Stored on the map row's
# map_type; the concrete output (LIGHTING vs LIT_COLOR) is chosen per-row via the
# lighting_output selector and resolved to the effective type for the backend/wire
# protocol (same one-stored-type + selector + effective-type pattern as MAP_MATERIAL).
# LIGHTING / LIT_COLOR remain valid stored types for legacy rows saved before the
# consolidation; they are simply no longer offered by the picker.
MAP_SCENE_LIGHTING = "SCENE_LIGHTING"
MAP_PRINCIPAL_CURVATURE = "PRINCIPAL_CURVATURE"
MAP_CURVATURE_DIRECTION = "CURVATURE_DIRECTION"
MAP_MATERIAL = "MATERIAL"
# Per-channel effective types for MAP_MATERIAL (used in output filenames + tracking,
# never stored on map items — same pattern as MAP_PRINCIPAL_CURVATURE / MAP_CURVATURE_DIRECTION)
MAP_MATERIAL_ALBEDO = "MATERIAL_ALBEDO"
MAP_MATERIAL_ROUGHNESS = "MATERIAL_ROUGHNESS"
MAP_MATERIAL_METALNESS = "MATERIAL_METALNESS"
MAP_MATERIAL_EMISSION = "MATERIAL_EMISSION"
MAP_MATERIAL_OPACITY = "MATERIAL_OPACITY"
MAP_MATERIAL_SPECULAR = "MATERIAL_SPECULAR"
MAP_MATERIAL_TRANSMISSION = "MATERIAL_TRANSMISSION"
MAP_MATERIAL_NORMAL = "MATERIAL_NORMAL"

# Material channel sub-types (stored on MasterBakerMapSetting.material_channel)
MATERIAL_CHANNEL_ALBEDO = "ALBEDO"
MATERIAL_CHANNEL_ROUGHNESS = "ROUGHNESS"
MATERIAL_CHANNEL_METALNESS = "METALNESS"
MATERIAL_CHANNEL_EMISSION = "EMISSION"
MATERIAL_CHANNEL_OPACITY = "OPACITY"
MATERIAL_CHANNEL_SPECULAR = "SPECULAR"
MATERIAL_CHANNEL_TRANSMISSION = "TRANSMISSION"
# Bump / Normal Map / Displacement / Vector Displacement all lower to IR, and the
# effective type MAP_MATERIAL_NORMAL is wired through the job vocabularies and the
# backend map factory, so the channel is selectable.
MATERIAL_CHANNEL_NORMAL = "NORMAL"

# WARNING: this feeds an EnumProperty (properties.material_channel), so saved .blend
# files store the item's integer index — APPEND-ONLY, never insert or reorder.
MATERIAL_CHANNEL_ITEMS = (
    (MATERIAL_CHANNEL_ALBEDO, "Albedo", "Base Color input of Principled BSDF"),
    (MATERIAL_CHANNEL_ROUGHNESS, "Roughness", "Roughness input of Principled BSDF"),
    (MATERIAL_CHANNEL_METALNESS, "Metalness", "Metallic input of Principled BSDF"),
    (MATERIAL_CHANNEL_EMISSION, "Emission", "Emission Color input of Principled BSDF"),
    (MATERIAL_CHANNEL_OPACITY, "Opacity", "Alpha input of Principled BSDF"),
    (MATERIAL_CHANNEL_SPECULAR, "Specular", "Specular IOR Level input of Principled BSDF"),
    (MATERIAL_CHANNEL_TRANSMISSION, "Transmission", "Transmission Weight input of Principled BSDF"),
    (MATERIAL_CHANNEL_NORMAL, "Normal", "Normal input of Principled BSDF"),
)

# Procedural material capture — see docs/PROCEDURAL_MATERIAL_CAPTURE_PLAN.md.
MATERIAL_PROFILE_STANDARD = "STANDARD"
MATERIAL_PROFILE_EXTENDED = "EXTENDED"
MATERIAL_PROFILE_ITEMS = (
    (MATERIAL_PROFILE_STANDARD, "Standard Metal/Rough", "Base Color, Roughness, and other meaningful metal/rough channels"),
    (MATERIAL_PROFILE_EXTENDED, "Extended Principled", "Standard channels plus coat, sheen, subsurface, and related Principled parameters"),
)

MATERIAL_ORIGIN_MANUAL = "MANUAL"
MATERIAL_ORIGIN_CAPTURE = "CAPTURE"
MATERIAL_ORIGIN_CUSTOM = "CUSTOM"
MATERIAL_ORIGIN_ITEMS = (
    (MATERIAL_ORIGIN_MANUAL, "Manual", "Created or claimed by the user"),
    (MATERIAL_ORIGIN_CAPTURE, "Material Capture", "Synced from a Fyr Material Capture node"),
    (MATERIAL_ORIGIN_CUSTOM, "Custom Output", "Synced from a Fyr Custom Output node"),
)

MATERIAL_RESOLVE_RESOLVED = "RESOLVED"
MATERIAL_RESOLVE_PARTIAL = "PARTIAL"
MATERIAL_RESOLVE_MISSING = "MISSING"
MATERIAL_RESOLVE_INVALID = "INVALID"
MATERIAL_RESOLVE_APPROXIMATE = "APPROXIMATE"
MATERIAL_RESOLVE_ITEMS = (
    (MATERIAL_RESOLVE_RESOLVED, "Resolved", "Source is available on every relevant material"),
    (MATERIAL_RESOLVE_PARTIAL, "Partial", "Source covers only some relevant materials"),
    (MATERIAL_RESOLVE_MISSING, "Missing", "Previously detected source is gone"),
    (MATERIAL_RESOLVE_INVALID, "Invalid", "Source is present but cannot be baked"),
    (MATERIAL_RESOLVE_APPROXIMATE, "Approximate", "Closure conversion is best-effort"),
)

MATERIAL_DATA_COLOR = "COLOR"
MATERIAL_DATA_VALUE = "VALUE"
MATERIAL_DATA_VECTOR = "VECTOR"
MATERIAL_DATA_TYPE_ITEMS = (
    (MATERIAL_DATA_COLOR, "Color", "Scene-linear color"),
    (MATERIAL_DATA_VALUE, "Value", "Scalar data"),
    (MATERIAL_DATA_VECTOR, "Vector", "XYZ vector"),
)

MATERIAL_VECTOR_ENCODE_SIGNED = "SIGNED"
MATERIAL_VECTOR_ENCODE_UNIT = "UNIT"
MATERIAL_VECTOR_ENCODE_ITEMS = (
    (MATERIAL_VECTOR_ENCODE_SIGNED, "Signed Float", "Store XYZ as signed values"),
    (MATERIAL_VECTOR_ENCODE_UNIT, "0-1 Encoded", "Remap [-1, 1] to [0, 1]"),
)

CAPTURE_MODE_AUTO = "AUTOMATIC"
CAPTURE_MODE_HYBRID = "HYBRID"
CAPTURE_MODE_EXPLICIT = "EXPLICIT"
CAPTURE_MODE_ITEMS = (
    (CAPTURE_MODE_AUTO, "Automatic", "Derive outputs from the incoming shader"),
    (CAPTURE_MODE_HYBRID, "Hybrid", "Derive automatically, then apply enabled overrides"),
    (CAPTURE_MODE_EXPLICIT, "Explicit", "Bake only enabled override inputs"),
)

# Logical binding keys for standard capture channels.
CAPTURE_BINDING_BASE_COLOR = "STANDARD:BASE_COLOR"
CAPTURE_BINDING_METALNESS = "STANDARD:METALNESS"
CAPTURE_BINDING_ROUGHNESS = "STANDARD:ROUGHNESS"
CAPTURE_BINDING_NORMAL = "STANDARD:NORMAL"
CAPTURE_BINDING_EMISSION = "STANDARD:EMISSION"
CAPTURE_BINDING_OPACITY = "STANDARD:OPACITY"
CAPTURE_BINDING_HEIGHT = "STANDARD:HEIGHT"
CAPTURE_BINDING_SPECULAR = "STANDARD:SPECULAR"
CAPTURE_BINDING_TRANSMISSION = "STANDARD:TRANSMISSION"

CAPTURE_BINDING_TO_CHANNEL = {
    CAPTURE_BINDING_BASE_COLOR: MATERIAL_CHANNEL_ALBEDO,
    CAPTURE_BINDING_METALNESS: MATERIAL_CHANNEL_METALNESS,
    CAPTURE_BINDING_ROUGHNESS: MATERIAL_CHANNEL_ROUGHNESS,
    CAPTURE_BINDING_EMISSION: MATERIAL_CHANNEL_EMISSION,
    CAPTURE_BINDING_OPACITY: MATERIAL_CHANNEL_OPACITY,
    CAPTURE_BINDING_SPECULAR: MATERIAL_CHANNEL_SPECULAR,
    CAPTURE_BINDING_TRANSMISSION: MATERIAL_CHANNEL_TRANSMISSION,
}

CAPTURE_CHANNEL_TO_BINDING = {channel: key for key, channel in CAPTURE_BINDING_TO_CHANNEL.items()}

# Compact capture sockets shown by default (advanced Principled params stay folded).
CAPTURE_COMPACT_CHANNELS = (
    ("BASE_COLOR", "Base Color", "RGBA", CAPTURE_BINDING_BASE_COLOR),
    ("METALNESS", "Metalness", "VALUE", CAPTURE_BINDING_METALNESS),
    ("ROUGHNESS", "Roughness", "VALUE", CAPTURE_BINDING_ROUGHNESS),
    ("NORMAL", "Normal", "VECTOR", CAPTURE_BINDING_NORMAL),
    ("EMISSION", "Emission Color", "RGBA", CAPTURE_BINDING_EMISSION),
    ("OPACITY", "Opacity", "VALUE", CAPTURE_BINDING_OPACITY),
    ("HEIGHT", "Height", "VALUE", CAPTURE_BINDING_HEIGHT),
    ("SPECULAR", "Specular IOR Level", "VALUE", CAPTURE_BINDING_SPECULAR),
    ("TRANSMISSION", "Transmission Weight", "VALUE", CAPTURE_BINDING_TRANSMISSION),
)

# Principled socket name used when extracting each compact channel.
CAPTURE_CHANNEL_PRINCIPLED_SOCKET = {
    "BASE_COLOR": "Base Color",
    "METALNESS": "Metallic",
    "ROUGHNESS": "Roughness",
    "NORMAL": "Normal",
    "EMISSION": "Emission Color",
    "OPACITY": "Alpha",
    "SPECULAR": "Specular IOR Level",
    "TRANSMISSION": "Transmission Weight",
}

# Neutral defaults — a channel differing from these (or linked) is "meaningful".
CAPTURE_CHANNEL_NEUTRAL = {
    "BASE_COLOR": (0.8, 0.8, 0.8, 1.0),
    "METALNESS": 0.0,
    "ROUGHNESS": 0.5,
    "NORMAL": (0.0, 0.0, 1.0),
    "EMISSION": (0.0, 0.0, 0.0, 1.0),
    "OPACITY": 1.0,
    "HEIGHT": 0.0,
    "SPECULAR": 0.5,
    "TRANSMISSION": 0.0,
}

MAP_MATERIAL_CUSTOM = "MATERIAL_CUSTOM"


#: Map types whose output files the backend writes with an sRGB encoding. Every other
#: map is written as linear/raw DATA and must be read back as Non-Color, or a stored
#: 0.35 roughness is silently linearised to ~0.10 on load and the surface reads far
#: glossier than the source material. Mirrors ``map_uses_srgb_output_encoding`` in
#: ``backend/src/master_baker_backend.cpp`` -- keep the two in step.
SRGB_ENCODED_OUTPUT_MAP_PREFIXES = ("MATERIAL_ALBEDO", "MATERIAL_EMISSION")


def map_output_is_srgb_encoded(map_type: str) -> bool:
    """Whether a baked output of this map type carries an sRGB encoding on disk."""
    normalized = str(map_type or "").strip().upper()
    return any(normalized.startswith(prefix) for prefix in SRGB_ENCODED_OUTPUT_MAP_PREFIXES)


def map_output_colorspace_name(map_type: str) -> str:
    """Blender colorspace an output of this map type must be READ with."""
    return "sRGB" if map_output_is_srgb_encoded(map_type) else "Non-Color"
FYR_CAPTURE_NODE_ID = "ShaderNodeFyrMaterialCapture"
FYR_CUSTOM_OUTPUT_NODE_ID = "ShaderNodeFyrCustomOutput"
FYR_NODE_TREE_PREFIX = ".Fyr Baker "

# Scene-lighting maps (LIGHTING / LIT_COLOR) — see docs/SCENE_LIGHTING_BAKE_PLAN.md.
LIGHTING_ENGINE_AUTO = "AUTO"
LIGHTING_ENGINE_EEVEE = "EEVEE"
LIGHTING_ENGINE_CYCLES = "CYCLES"

LIGHTING_ENGINE_ITEMS = (
    (LIGHTING_ENGINE_AUTO, "Auto - Scene Engine", "Follow the scene's current render engine"),
    (LIGHTING_ENGINE_EEVEE, "Eevee", "Read materials and lights using Eevee-compatible behavior"),
    (LIGHTING_ENGINE_CYCLES, "Cycles", "Read materials and lighting settings using Cycles-compatible behavior"),
)

LIGHTING_QUALITY_PREVIEW = "PREVIEW"
LIGHTING_QUALITY_BALANCED = "BALANCED"
LIGHTING_QUALITY_PRODUCTION = "PRODUCTION"
LIGHTING_QUALITY_CUSTOM = "CUSTOM"

LIGHTING_QUALITY_ITEMS = (
    (LIGHTING_QUALITY_PREVIEW, "Preview", "Use fewer samples for a fast preview"),
    (LIGHTING_QUALITY_BALANCED, "Balanced", "Balance bake time and lighting quality"),
    (LIGHTING_QUALITY_PRODUCTION, "Production", "Use more samples and stricter noise reduction for final output"),
    (LIGHTING_QUALITY_CUSTOM, "Custom", "Set the lighting samples, bounces, and noise threshold manually"),
)

# Preset -> (direct_samples, indirect_paths, max_bounces, noise_threshold).
# When noise_threshold > 0 the backend treats direct_samples / indirect_paths as
# a per-texel CAP: variance-guided adaptive sampling starts at a small batch and
# stops once each stochastic estimator's 95% relative luminance CI falls under the
# threshold, spending the budget only where hard-visibility noise needs it. Clean
# texels stop early, so a higher cap is net-cheaper than a fixed count at the same
# visual quality. noise_threshold 0.0 means a fixed workload (exactly
# direct_samples / indirect_paths samples per texel, no adaptive termination).
# direct_samples budgets soft shadows (finite-size lights) and world/HDR
# environment sampling; delta lights always use a single visibility ray.
# These configure ONLY the owning map row's transport; never other maps or
# project-global settings.
LIGHTING_QUALITY_PRESET_VALUES = {
    LIGHTING_QUALITY_PREVIEW: (16, 16, 2, 0.0),
    LIGHTING_QUALITY_BALANCED: (256, 256, 4, 0.02),
    LIGHTING_QUALITY_PRODUCTION: (1024, 1024, 8, 0.01),
}

# Per-row scene-lighting output selector (stored on MasterBakerMapSetting.lighting_output).
# Translates a consolidated MAP_SCENE_LIGHTING row to its effective backend map type.
LIGHTING_OUTPUT_LIGHTING = "LIGHTING"
LIGHTING_OUTPUT_LIT_COLOR = "LIT_COLOR"
LIGHTING_OUTPUT_DIRECT = "DIRECT_LIGHTING"
LIGHTING_OUTPUT_INDIRECT = "INDIRECT_LIGHTING"
LIGHTING_OUTPUT_SPECULAR = "SPECULAR_LIGHTING"

# Append-only: an EnumProperty stores the item's index in the .blend.
LIGHTING_OUTPUT_ITEMS = (
    (LIGHTING_OUTPUT_LIGHTING, "Lighting", "Scene lighting as linear HDR diffuse irradiance (excludes albedo and emission)"),
    (LIGHTING_OUTPUT_LIT_COLOR, "Lit Color", "Scene lighting multiplied by diffuse albedo plus emission"),
    (LIGHTING_OUTPUT_DIRECT, "Direct Lighting", "Light arriving straight from lamps, the world and emissive surfaces, with shadows, without bounces"),
    (LIGHTING_OUTPUT_INDIRECT, "Indirect Lighting", "Only the light bounced between surfaces"),
    (
        LIGHTING_OUTPUT_SPECULAR,
        "Specular Lighting",
        "Glossy reflections of lamps, sky, glowing surfaces and other surfaces, seen straight on",
    ),
)

# lighting_output value -> effective (wire/output) map type. Identity-valued strings,
# but kept explicit so call sites never hard-code the coincidence.
LIGHTING_OUTPUT_TO_EFFECTIVE_TYPE: dict[str, str] = {
    LIGHTING_OUTPUT_LIGHTING: MAP_LIGHTING,
    LIGHTING_OUTPUT_LIT_COLOR: MAP_LIT_COLOR,
    LIGHTING_OUTPUT_DIRECT: MAP_DIRECT_LIGHTING,
    LIGHTING_OUTPUT_INDIRECT: MAP_INDIRECT_LIGHTING,
    LIGHTING_OUTPUT_SPECULAR: MAP_SPECULAR_LIGHTING,
}

# Effective lighting type -> (wire map type, lighting_component) of its backend config.
LIGHTING_COMPONENT_BY_EFFECTIVE_TYPE: dict[str, tuple[str, str]] = {
    MAP_LIGHTING: (MAP_LIGHTING, "ALL"),
    MAP_LIT_COLOR: (MAP_LIT_COLOR, "ALL"),
    MAP_DIRECT_LIGHTING: (MAP_LIGHTING, "DIRECT"),
    MAP_INDIRECT_LIGHTING: (MAP_LIGHTING, "INDIRECT"),
    MAP_SPECULAR_LIGHTING: (MAP_LIGHTING, "SPECULAR"),
}


def _lighting_map_field(item, name: str, default=""):
    """Read a field from a map row that may be a PropertyGroup-like object or a
    plain mapping (validation passes dict-like map items)."""
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def effective_lighting_map_type(item) -> str | None:
    """Resolve a map row to its effective scene-lighting output type, or None if the
    row is not a lighting map.

    SCENE_LIGHTING rows resolve through their ``lighting_output`` selector; legacy
    LIGHTING / LIT_COLOR rows resolve to themselves. Duck-typed so both PropertyGroup
    map items (addon) and dict-like map items (validation) work."""
    raw = str(_lighting_map_field(item, "map_type", "") or "").strip().upper()
    if raw == MAP_SCENE_LIGHTING:
        output = str(_lighting_map_field(item, "lighting_output", LIGHTING_OUTPUT_LIGHTING) or "").strip().upper()
        return LIGHTING_OUTPUT_TO_EFFECTIVE_TYPE.get(output, MAP_LIGHTING)
    if raw in (MAP_LIGHTING, MAP_LIT_COLOR):
        return raw
    return None


MATERIAL_DETAIL_OFF = "OFF"
MATERIAL_DETAIL_AUTO = "AUTO"
MATERIAL_DETAIL_MANUAL = "MANUAL"
MATERIAL_DETAIL_MATERIAL_ONLY = "MATERIAL_ONLY"
MATERIAL_DETAIL_MODE_ITEMS = (
    (MATERIAL_DETAIL_OFF, "Off", "Bake geometry only", 0),
    (MATERIAL_DETAIL_AUTO, "Auto", "Include compatible normal, bump, height, or AO data detected in high-poly materials", 1),
    (MATERIAL_DETAIL_MANUAL, "Manual", "Use the selected image as the high-poly material-detail source", 2),
)
MATERIAL_NORMAL_DETAIL_MODE_ITEMS = (
    MATERIAL_DETAIL_MODE_ITEMS[0],
    MATERIAL_DETAIL_MODE_ITEMS[1],
    (
        MATERIAL_DETAIL_MATERIAL_ONLY,
        "Material Only",
        "Bake only the high-poly material normal, bump, or height detail. Skips geometric high-to-low normals",
        3,
    ),
)
# Resolved composition modes written onto BakeMapConfig after prepare (not UI enums).
MATERIAL_DETAIL_BACKEND_NORMAL_COMBINE = "NORMAL_COMBINE"
# Roughness carrying the sub-texel normal variation the bake resolution cannot store.
MATERIAL_DETAIL_BACKEND_NORMAL_VARIANCE = "NORMAL_VARIANCE"
MATERIAL_DETAIL_BACKEND_HEIGHT_NORMAL = "HEIGHT_NORMAL"
MATERIAL_DETAIL_BACKEND_NORMAL_REPLACE = "NORMAL_REPLACE"
MATERIAL_DETAIL_BACKEND_HEIGHT_REPLACE = "HEIGHT_REPLACE"
MATERIAL_DETAIL_BACKEND_AO_TEXTURE = "AO_TEXTURE"
MATERIAL_DETAIL_BACKEND_HEIGHT_AO = "HEIGHT_AO"
MATERIAL_DETAIL_BACKEND_NORMAL_AO = "NORMAL_AO"
MATERIAL_DETAIL_BACKEND_MODES = frozenset(
    {
        MATERIAL_DETAIL_BACKEND_NORMAL_COMBINE,
        MATERIAL_DETAIL_BACKEND_HEIGHT_NORMAL,
        MATERIAL_DETAIL_BACKEND_NORMAL_REPLACE,
        MATERIAL_DETAIL_BACKEND_HEIGHT_REPLACE,
        MATERIAL_DETAIL_BACKEND_AO_TEXTURE,
        MATERIAL_DETAIL_BACKEND_HEIGHT_AO,
        MATERIAL_DETAIL_BACKEND_NORMAL_AO,
    }
)

# Shortcut identifiers used only at the Add Output operator level — never stored on map items.
# Each translates to MAP_MATERIAL with a specific material_channel value.
MATERIAL_SHORTCUT_PREFIX = "_MAT_"
MATERIAL_SHORTCUT_ALBEDO = "_MAT_ALBEDO"
MATERIAL_SHORTCUT_ROUGHNESS = "_MAT_ROUGHNESS"
MATERIAL_SHORTCUT_METALNESS = "_MAT_METALNESS"
MATERIAL_SHORTCUT_EMISSION = "_MAT_EMISSION"
MATERIAL_SHORTCUT_OPACITY = "_MAT_OPACITY"
MATERIAL_SHORTCUT_SPECULAR = "_MAT_SPECULAR"
MATERIAL_SHORTCUT_TRANSMISSION = "_MAT_TRANSMISSION"
MATERIAL_SHORTCUT_NORMAL = "_MAT_NORMAL"

# Maps shortcut identifier → material channel constant
# Maps material_channel → per-channel effective map type for output tracking
MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE: dict[str, str] = {
    MATERIAL_CHANNEL_ALBEDO: MAP_MATERIAL_ALBEDO,
    MATERIAL_CHANNEL_ROUGHNESS: MAP_MATERIAL_ROUGHNESS,
    MATERIAL_CHANNEL_METALNESS: MAP_MATERIAL_METALNESS,
    MATERIAL_CHANNEL_EMISSION: MAP_MATERIAL_EMISSION,
    MATERIAL_CHANNEL_OPACITY: MAP_MATERIAL_OPACITY,
    MATERIAL_CHANNEL_SPECULAR: MAP_MATERIAL_SPECULAR,
    MATERIAL_CHANNEL_TRANSMISSION: MAP_MATERIAL_TRANSMISSION,
    MATERIAL_CHANNEL_NORMAL: MAP_MATERIAL_NORMAL,
}

#: Effective map types owned by the addon-side material queue, never by a projection
#: plan. The Cycles-primary route has to subtract these before planning or the
#: planner rejects the whole job with "Material channels already use the dedicated
#: Cycles material path" — which is what it did for every Route = Cycles bake that
#: had a material row.
MATERIAL_EFFECTIVE_MAP_TYPES: frozenset[str] = frozenset(
    MATERIAL_CHANNEL_TO_EFFECTIVE_TYPE.values()
) | {MAP_MATERIAL}

# Inverse of the expansions above. A baked output records its *effective* type
# (MATERIAL_ALBEDO, PRINCIPAL_CURVATURE, ...), but every UI enum is built from
# MAP_TYPE_ITEMS, which only carries the base types. Anything that feeds a stored
# map type back into an enum has to come through here or Blender raises on assign.
MAP_EFFECTIVE_TO_BASE_TYPE: dict[str, str] = {
    MAP_MATERIAL_ALBEDO: MAP_MATERIAL,
    MAP_MATERIAL_ROUGHNESS: MAP_MATERIAL,
    MAP_MATERIAL_METALNESS: MAP_MATERIAL,
    MAP_MATERIAL_EMISSION: MAP_MATERIAL,
    MAP_MATERIAL_OPACITY: MAP_MATERIAL,
    MAP_MATERIAL_SPECULAR: MAP_MATERIAL,
    MAP_MATERIAL_TRANSMISSION: MAP_MATERIAL,
    MAP_MATERIAL_NORMAL: MAP_MATERIAL,
    MAP_MATERIAL_CUSTOM: MAP_MATERIAL,
    MAP_PRINCIPAL_CURVATURE: MAP_CURVATURE,
    MAP_CURVATURE_DIRECTION: MAP_CURVATURE,
    MAP_DERIVATIVE: MAP_NORMAL,
}


def base_map_type(value) -> str:
    """The MAP_TYPE_ITEMS member a stored or effective map type belongs to."""
    text = str(value or "").strip().upper()
    return MAP_EFFECTIVE_TO_BASE_TYPE.get(text, text)


MATERIAL_SHORTCUT_TO_CHANNEL: dict[str, str] = {
    MATERIAL_SHORTCUT_ALBEDO: MATERIAL_CHANNEL_ALBEDO,
    MATERIAL_SHORTCUT_ROUGHNESS: MATERIAL_CHANNEL_ROUGHNESS,
    MATERIAL_SHORTCUT_METALNESS: MATERIAL_CHANNEL_METALNESS,
    MATERIAL_SHORTCUT_EMISSION: MATERIAL_CHANNEL_EMISSION,
    MATERIAL_SHORTCUT_OPACITY: MATERIAL_CHANNEL_OPACITY,
    MATERIAL_SHORTCUT_SPECULAR: MATERIAL_CHANNEL_SPECULAR,
    MATERIAL_SHORTCUT_TRANSMISSION: MATERIAL_CHANNEL_TRANSMISSION,
    MATERIAL_SHORTCUT_NORMAL: MATERIAL_CHANNEL_NORMAL,
}

# ---------------------------------------------------------------------------
# Project workflow  (High -> Low projection  vs  same-object material flatten)
# ---------------------------------------------------------------------------
# Persisted on MasterBakerBakeProject.workflow. HIGH_TO_LOW is the existing
# projected-bake workflow and the default for every project saved before this
# field existed: Blender applies the EnumProperty default on load, so no schema
# migration step is required to give legacy projects the correct value.
# MATERIAL is the same-object material-flattening workflow with no high-poly role.
# See docs/MATERIAL_BAKING_WORKFLOW_PLAN.md.
WORKFLOW_HIGH_TO_LOW = "HIGH_TO_LOW"
WORKFLOW_MATERIAL = "MATERIAL"

WORKFLOW_ITEMS = (
    (WORKFLOW_HIGH_TO_LOW, "High to Low Bake",
     "Transfer geometry and material information from high-poly sources onto low-poly targets"),
    (WORKFLOW_MATERIAL, "Bake Selected Materials",
     "Flatten the materials already on the selected objects into portable PBR texture sets"),
)

# Job source semantics (execution contract, kept distinct from the product/UI
# workflow above and never inferred from whether a high-mesh list is empty).
#   PROJECTED     - low UV texels receive values from projected high-mesh hits.
#   SELF_MATERIAL - low UV texels receive the material evaluated on the low object
#                   itself. This is the source mode a MATERIAL-workflow project uses.
JOB_SOURCE_PROJECTED = "PROJECTED"
JOB_SOURCE_SELF_MATERIAL = "SELF_MATERIAL"

# Map types the Bake Selected Materials picker is allowed to offer: the PBR
# material channels (MAP_MATERIAL + material_channel selector) and material-space
# tangent Normal derived from the object's own Normal Map / Bump nodes.
MATERIAL_WORKFLOW_MAP_TYPES = frozenset({MAP_MATERIAL, MAP_NORMAL})

# ---------------------------------------------------------------------------
# Per-output execution route (advanced). Recorded per map row and in diagnostics
# / support bundles. Enum identifiers stay BACKEND/BLENDER for .blend compatibility;
# UI labels are Fyr / Cycles. AUTO picks Fyr when Material IR is available, otherwise
# Cycles. Routing must never be silently changed after preflight.
# ---------------------------------------------------------------------------
EXECUTION_ROUTE_AUTO = "AUTO"
EXECUTION_ROUTE_BACKEND = "BACKEND"
EXECUTION_ROUTE_BLENDER = "BLENDER"

EXECUTION_ROUTE_ITEMS = (
    (EXECUTION_ROUTE_AUTO, "Auto",
     "Use Fyr when this material can run natively; otherwise use Cycles"),
    (EXECUTION_ROUTE_BACKEND, "Fyr",
     "Require Fyr for this output; fail preflight if the material needs Cycles"),
    (EXECUTION_ROUTE_BLENDER, "Cycles",
     "Bake this output with Cycles"),
)

MAP_TYPE_ITEMS = (
    (MAP_NORMAL, "Normal", "Tangent-space normal map"),
    (MAP_OBJECT_NORMAL, "Object Normal", "Object-space normal map"),
    (MAP_WORLD_NORMAL, "World Normal", "World-space normal map"),
    (MAP_AO, "Ambient Occlusion", "Ambient occlusion map"),
    (MAP_CURVATURE, "Curvature", "Curvature map"),
    (MAP_THICKNESS, "Thickness", "Thickness map"),
    (MAP_DENSITY, "Density", "Average local material occupancy within a probe radius. Native on Fyr GPU; approximate on Cycles"),
    (MAP_CAVITY, "Cavity", "Bake a dirt and crevice mask from tight occlusion and concave surface detail"),
    (MAP_CONCAVE, "Concave", "Bake concave curvature detail as a positive mask"),
    (MAP_CONVEX, "Convex", "Bake convex curvature detail as a positive mask"),
    (MAP_OPACITY, "Opacity", "Opacity coverage map"),
    (MAP_POSITION, "Position", "Object-space position map"),
    (MAP_VERTEX_COLOR, "Vertex Color", "Bake high-poly vertex colors into texture space"),
    (MAP_ENV_LIGHT, "Environment Light", "Hemispherical environment lighting map"),
    (MAP_BENT_NORMAL, "Bent Normal", "Bent normal map. Native on Fyr GPU; approximate on Cycles (six directional visibility probes)"),
    (MAP_HEIGHT, "Height / Displacement", "Height or displacement map"),
    (MAP_ID, "ID", "Color ID map"),
    (MAP_MATERIAL, "Material", "PBR material channel bake (albedo, roughness, metalness, etc.)"),
    # WARNING: enum values are POSITIONAL. Saved .blend files store map_type as the item's
    # integer index, so this tuple is APPEND-ONLY — never insert, remove, or reorder entries,
    # or every row saved after the edited position silently changes type on load.
    # LIGHTING / LIT_COLOR keep their original slots so legacy rows resolve correctly; they
    # are migrated to MAP_SCENE_LIGHTING by ensure_default_maps and are NOT offered by the
    # picker (see ui._LIGHTING_MAP_CATEGORY_GROUP) nor auto-added to project stacks
    # (LEGACY_SCENE_LIGHTING_MAP_TYPES below).
    (MAP_LIGHTING, "Lighting", "Scene lighting as linear HDR diffuse irradiance (excludes albedo and emission)"),
    (MAP_LIT_COLOR, "Lit Color", "Scene lighting multiplied by diffuse albedo plus emission"),
    (MAP_SCENE_LIGHTING, "Scene Lighting", "Bake scene lights, world, and GI, as pure lighting or fully lit color"),
    (MAP_ATTRIBUTE, "Attribute", "Bake a high-poly mesh attribute (float, vector, color, integer or boolean) into texture space"),
    (MAP_WIREFRAME, "Wireframe", "Draw the low poly's UV edges as lines"),
)

# Legacy stored row types that ensure_default_maps must not auto-add to project stacks;
# existing rows of these types are migrated in place to MAP_SCENE_LIGHTING with the
# matching lighting_output value.
LEGACY_SCENE_LIGHTING_MAP_TYPES: frozenset[str] = frozenset({MAP_LIGHTING, MAP_LIT_COLOR})

# Every stored row type whose output is shaped by the scene's lights and world: the
# consolidated row plus the legacy types above (a .blend saved before the retype still
# carries them). Used by the dirty rules and by the recorded bake state.
LIGHTING_FAMILY_MAP_TYPES: frozenset[str] = LEGACY_SCENE_LIGHTING_MAP_TYPES | {MAP_SCENE_LIGHTING}

# Rows shaded by the ambient-occlusion hemisphere trace: the maps a high mesh's
# "Casts AO" toggle changes (backend: sample_ambient_occlusion / sample_ao_cavity_shared).
AO_OCCLUDER_MAP_TYPES: frozenset[str] = frozenset({MAP_AO, MAP_BENT_NORMAL, MAP_CAVITY, MAP_ENV_LIGHT})
# Rows with the Occlude / Include Other Groups switch (ao_occlude_other_groups). When it is
# on, a high in any group changes their pixels.
WORLD_OCCLUSION_MAP_TYPES: frozenset[str] = frozenset({MAP_AO, MAP_BENT_NORMAL, MAP_THICKNESS, MAP_DENSITY})
# Rows where it starts on. Thickness and Density stay inside the bake group by default.
WORLD_OCCLUSION_DEFAULT_MAP_TYPES: frozenset[str] = frozenset({MAP_AO, MAP_BENT_NORMAL})

DEFAULT_ENABLED_MAPS = (MAP_NORMAL, MAP_AO, MAP_CURVATURE, MAP_ID)

# Valid map types that may appear in a serialized bake job. Includes user-selectable
# types from MAP_TYPE_ITEMS plus backend-derived types produced by curvature_output_mode.
MAP_VALID_JOB_TYPES: frozenset[str] = frozenset(item[0] for item in MAP_TYPE_ITEMS) | frozenset({
    MAP_PRINCIPAL_CURVATURE,
    MAP_CURVATURE_DIRECTION,
    MAP_MATERIAL_ALBEDO,
    MAP_MATERIAL_ROUGHNESS,
    MAP_MATERIAL_METALNESS,
    MAP_MATERIAL_EMISSION,
    MAP_MATERIAL_OPACITY,
    MAP_MATERIAL_SPECULAR,
    MAP_MATERIAL_TRANSMISSION,
    MAP_MATERIAL_NORMAL,
    MAP_MATERIAL_CUSTOM,
    MAP_DERIVATIVE,
    MAP_DIRECT_LIGHTING,
    MAP_INDIRECT_LIGHTING,
    MAP_SPECULAR_LIGHTING,
})

MAP_MAX_SAMPLES = 4096
# Default ray count for every map that traces a hemisphere. Deliberately not a
# power of two: this is a ray count, and a default of 512 or 1024 reads as an
# image resolution and invites people to match it to their output size, which is
# meaningless. Baking references land in the high hundreds for AO, so 697 sits in
# the right place and looks like the considered number it is.
MAP_RECOMMENDED_SAMPLES = 697
MAP_LOW_SAMPLE_WARNING_THRESHOLD = 32

MAP_DEFAULT_SAMPLES = {
    MAP_NORMAL: 1,
    MAP_OBJECT_NORMAL: 1,
    MAP_WORLD_NORMAL: 1,
    MAP_AO: MAP_RECOMMENDED_SAMPLES,
    MAP_CURVATURE: MAP_RECOMMENDED_SAMPLES,
    MAP_THICKNESS: MAP_RECOMMENDED_SAMPLES,
    MAP_DENSITY: MAP_RECOMMENDED_SAMPLES,
    MAP_CAVITY: MAP_RECOMMENDED_SAMPLES,
    MAP_CONCAVE: MAP_RECOMMENDED_SAMPLES,
    MAP_CONVEX: MAP_RECOMMENDED_SAMPLES,
    MAP_OPACITY: 1,
    MAP_POSITION: 1,
    MAP_VERTEX_COLOR: 1,
    MAP_ATTRIBUTE: 1,
    MAP_WIREFRAME: 1,
    MAP_ENV_LIGHT: MAP_RECOMMENDED_SAMPLES,
    MAP_BENT_NORMAL: MAP_RECOMMENDED_SAMPLES,
    MAP_HEIGHT: 1,
    MAP_ID: 1,
    MAP_PRINCIPAL_CURVATURE: MAP_RECOMMENDED_SAMPLES,
    MAP_CURVATURE_DIRECTION: MAP_RECOMMENDED_SAMPLES,
    MAP_MATERIAL: 1,
    # Lighting maps use their own transport controls (lighting_direct_samples /
    # lighting_indirect_paths), not the generic per-map samples field.
    MAP_LIGHTING: 1,
    MAP_LIT_COLOR: 1,
    MAP_SCENE_LIGHTING: 1,
}

# Maps whose Ray Count control actually changes the bake. Every one of these traces
# per-sample rays and gets measurably cleaner as the count goes up.
#
# The curvature family is deliberately NOT here. Curvature, Concave and Convex are
# rebuilt after shading by the curvature resolve -- the backend flags them
# `texture_space_postprocess_replaces_output`, so whatever the per-sample ray loop
# produced is discarded. Measured on Pottery A at 2048/8X, Ray Count 64 against 697:
#
#   Curvature / Normal Derivative   83.9 dB   identical
#   Curvature / Geometric           88.6 dB   identical
#   Concave   / Normal Derivative   95.7 dB   identical
#   Concave   / Geometric          228.1 dB   bit-identical
#   Convex    / Geometric           80.4 dB   identical
#   Cavity                          25.4 dB   responds (hybrid AO route, still listed)
#   Density                         46.6 dB   responds
#
# Both curvature methods are post-processes over a field, not ray budgets: Normal
# Derivative differentiates the anti-aliased normal map, Geometric takes finite
# differences over the hit buffer. Their quality knobs are Detail Smoothing and the
# project's AA Samples. Showing a Ray Count that cannot change the result is the same
# defect as the old secondary-ray cap, so the control is hidden for them instead.
MAP_SAMPLE_CONTROL_TYPES: frozenset[str] = frozenset({
    MAP_AO,
    MAP_THICKNESS,
    MAP_DENSITY,
    MAP_CAVITY,
    MAP_ENV_LIGHT,
    MAP_BENT_NORMAL,
})


def default_samples_for_map(map_type: str) -> int:
    return max(1, int(MAP_DEFAULT_SAMPLES.get(str(map_type or "").strip().upper(), 1)))


def map_uses_samples(map_type: str, ao_mode: str = "RAYCAST") -> bool:
    normalized_map_type = str(map_type or "").strip().upper()
    if normalized_map_type == MAP_AO and str(ao_mode or "").strip().upper() == MAP_AO_MODE_DIFFUSIVE_ESCAPE:
        return False
    return normalized_map_type in MAP_SAMPLE_CONTROL_TYPES


MAP_DENOISING_ENABLED_DEFAULTS = {
    MAP_AO,
    MAP_BENT_NORMAL,
    MAP_THICKNESS,
    MAP_DENSITY,
    MAP_ENV_LIGHT,
    MAP_LIGHTING,
    MAP_LIT_COLOR,
    MAP_SCENE_LIGHTING,
}

# Map types where the denoise toggle is AVAILABLE in the UI. Superset of the
# defaults: CAVITY supports OIDN in the backend (the finalize denoise path is
# map-type agnostic) but the toggle was never exposed; keep its DEFAULT off —
# cavity is a derived/blended map and noise is better fixed at the source.
#
# MATERIAL is here too: a material graph can contain stochastic ray-op nodes (the MIR
# "AO" / "BEVEL" opcodes), which are sample-count driven exactly like the AO map, so the
# same per-map Denoise option applies. Its DEFAULT stays off — denoise is a user option,
# never a default and never a fix, and the raw bake is the product.
MAP_DENOISING_SUPPORTED = MAP_DENOISING_ENABLED_DEFAULTS | {
    MAP_CAVITY,
    MAP_MATERIAL,
}


def default_denoising_for_map(map_type: str) -> bool:
    return str(map_type or "").strip().upper() in MAP_DENOISING_ENABLED_DEFAULTS


def material_denoise_available(
    material_channel: str,
    material_origin: str = "",
    material_data_type: str = "",
) -> bool:
    """Whether the per-map Denoise option applies to this MAP_MATERIAL row.

    False for outputs that are ENCODED VECTORS rather than colour/value data — the
    Normal channel, and a Custom Output declared as Vector. Denoising an encoded normal
    drifts the packed XYZ off the unit sphere and rounds away the high-frequency detail
    the channel exists to carry, so the toggle is neither offered nor serialized for
    them. The backend mirrors this guard (map_type_supports_denoise) so an externally
    authored job cannot request it either.
    """
    if str(material_origin or "").strip().upper() == MATERIAL_ORIGIN_CUSTOM:
        return str(material_data_type or "").strip().upper() != MATERIAL_DATA_VECTOR
    return str(material_channel or "").strip().upper() != MATERIAL_CHANNEL_NORMAL


def default_ao_cavity_weight_for_map(map_type: str) -> float:
    normalized = str(map_type or "").strip().upper()
    # AO matches Marmoset Toolbag's factory Cavity Weight of 0 (evenly weighted
    # rays). 1.0 weights rays by (1 - cos), which nearly zeroes the only rays that
    # escape a deep hole and bakes it close to black.
    if normalized == MAP_AO:
        return 0.0
    if normalized == MAP_BENT_NORMAL:
        return 0.0
    if normalized == MAP_CAVITY:
        return -1.0
    return 0.0

MAP_LABELS = {
    MAP_NORMAL: "Normal",
    MAP_OBJECT_NORMAL: "Object Normal",
    MAP_WORLD_NORMAL: "World Normal",
    MAP_AO: "Ambient Occlusion",
    MAP_CURVATURE: "Curvature",
    MAP_THICKNESS: "Thickness",
    MAP_DENSITY: "Density",
    MAP_CAVITY: "Cavity",
    MAP_CONCAVE: "Concave",
    MAP_CONVEX: "Convex",
    MAP_OPACITY: "Opacity",
    MAP_POSITION: "Position",
    MAP_VERTEX_COLOR: "Vertex Color",
    MAP_ATTRIBUTE: "Attribute",
    MAP_WIREFRAME: "Wireframe",
    MAP_DERIVATIVE: "Derivative",
    SHORTCUT_DERIVATIVE: "Derivative",
    MAP_ENV_LIGHT: "Environment Light",
    MAP_BENT_NORMAL: "Bent Normal",
    MAP_HEIGHT: "Height / Displacement",
    MAP_ID: "ID",
    MAP_LIGHTING: "Lighting",
    MAP_LIT_COLOR: "Lit Color",
    MAP_DIRECT_LIGHTING: "Direct Lighting",
    MAP_INDIRECT_LIGHTING: "Indirect Lighting",
    MAP_SPECULAR_LIGHTING: "Specular Lighting",
    MAP_SCENE_LIGHTING: "Scene Lighting",
    MAP_PRINCIPAL_CURVATURE: "Principal Curvature",
    MAP_CURVATURE_DIRECTION: "Curvature Direction",
    MAP_MATERIAL: "Material",
    MAP_MATERIAL_ALBEDO: "Material: Albedo",
    MAP_MATERIAL_ROUGHNESS: "Material: Roughness",
    MAP_MATERIAL_METALNESS: "Material: Metalness",
    MAP_MATERIAL_EMISSION: "Material: Emission",
    MAP_MATERIAL_OPACITY: "Material: Opacity",
    MAP_MATERIAL_SPECULAR: "Material: Specular",
    MAP_MATERIAL_TRANSMISSION: "Material: Transmission",
    MAP_MATERIAL_NORMAL: "Material: Normal",
    MAP_MATERIAL_CUSTOM: "Material: Custom",
    # Shortcut labels for the Add Output catalog (not real map types)
    MATERIAL_SHORTCUT_ALBEDO: "Albedo",
    MATERIAL_SHORTCUT_ROUGHNESS: "Roughness",
    MATERIAL_SHORTCUT_METALNESS: "Metalness",
    MATERIAL_SHORTCUT_EMISSION: "Emission",
    MATERIAL_SHORTCUT_OPACITY: "Opacity",
    MATERIAL_SHORTCUT_SPECULAR: "Specular",
    MATERIAL_SHORTCUT_TRANSMISSION: "Transmission",
    MATERIAL_SHORTCUT_NORMAL: "Normal",
}

MAP_FILE_LABELS = {
    MAP_NORMAL: "Normal",
    MAP_OBJECT_NORMAL: "ObjectNormal",
    MAP_WORLD_NORMAL: "WorldNormal",
    MAP_AO: "AO",
    MAP_CURVATURE: "Curvature",
    MAP_THICKNESS: "Thickness",
    MAP_DENSITY: "Density",
    MAP_CAVITY: "Cavity",
    MAP_CONCAVE: "Concave",
    MAP_CONVEX: "Convex",
    MAP_OPACITY: "Opacity",
    MAP_POSITION: "Position",
    MAP_VERTEX_COLOR: "VertexColor",
    MAP_ATTRIBUTE: "Attribute",
    MAP_WIREFRAME: "Wireframe",
    MAP_DERIVATIVE: "Derivative",
    MAP_ENV_LIGHT: "EnvLight",
    MAP_BENT_NORMAL: "BentNormal",
    MAP_HEIGHT: "Height",
    MAP_ID: "ID",
    MAP_LIGHTING: "Lighting",
    MAP_LIT_COLOR: "LitColor",
    MAP_DIRECT_LIGHTING: "DirectLighting",
    MAP_INDIRECT_LIGHTING: "IndirectLighting",
    MAP_SPECULAR_LIGHTING: "SpecularLighting",
    # Fallback only — SCENE_LIGHTING rows always resolve to an effective LIGHTING /
    # LIT_COLOR type (see effective_lighting_map_type) that names the output file.
    MAP_SCENE_LIGHTING: "Lighting",
    MAP_PRINCIPAL_CURVATURE: "PrincipalCurvature",
    MAP_CURVATURE_DIRECTION: "CurvatureDirection",
    MAP_MATERIAL: "Material",
    MAP_MATERIAL_ALBEDO: "Albedo",
    MAP_MATERIAL_ROUGHNESS: "Roughness",
    MAP_MATERIAL_METALNESS: "Metalness",
    MAP_MATERIAL_EMISSION: "Emission",
    MAP_MATERIAL_OPACITY: "Opacity",
    MAP_MATERIAL_SPECULAR: "Specular",
    MAP_MATERIAL_TRANSMISSION: "Transmission",
    MAP_MATERIAL_NORMAL: "Normal",
    MAP_MATERIAL_CUSTOM: "Custom",
}

MAP_NORMAL_SPACE_TANGENT = "TANGENT"
MAP_NORMAL_SPACE_OBJECT = "OBJECT"
MAP_NORMAL_SPACE_WORLD = "WORLD"

MAP_NORMAL_SPACE_ITEMS = (
    (MAP_NORMAL_SPACE_TANGENT, "Tangent", "Bake tangent-space normals", "NORMALS_FACE", 0),
    (MAP_NORMAL_SPACE_OBJECT, "Object", "Bake object-space normals", "OBJECT_DATA", 1),
    (MAP_NORMAL_SPACE_WORLD, "World", "Bake world-space normals", "WORLD", 2),
)

NORMAL_FORMAT_OPENGL = "OPENGL"
NORMAL_FORMAT_DIRECTX = "DIRECTX"

NORMAL_FORMAT_ITEMS = (
    (NORMAL_FORMAT_OPENGL, "OpenGL", "Use OpenGL-style normal orientation (positive green / +Y)"),
    (NORMAL_FORMAT_DIRECTX, "DirectX", "Use DirectX-style normal orientation (flipped green / -Y)"),
)

MAP_POSITION_NORMALIZATION_BOUNDING_BOX = "BOUNDING_BOX"
MAP_POSITION_NORMALIZATION_BOUNDING_SPHERE = "BOUNDING_SPHERE"
MAP_POSITION_NORMALIZATION_OBJECT_ORIGIN = "OBJECT_ORIGIN"

MAP_POSITION_NORMALIZATION_ITEMS = (
    (MAP_POSITION_NORMALIZATION_BOUNDING_BOX, "Bounding Box", "Normalize position within the active low-poly mesh's bounding box"),
    (MAP_POSITION_NORMALIZATION_BOUNDING_SPHERE, "Bounding Sphere", "Normalize position within the active low-poly mesh's bounding sphere"),
    (MAP_POSITION_NORMALIZATION_OBJECT_ORIGIN, "Object Origin", "Encode object-space position relative to the object origin"),
)

MAP_AO_MODE_RAYCAST = "RAYCAST"
MAP_AO_MODE_DIFFUSIVE_ESCAPE = "DIFFUSIVE_ESCAPE"

MAP_AO_MODE_ITEMS = (
    (MAP_AO_MODE_RAYCAST, "Raycast", "Use classic hemisphere visibility sampling"),
    (
        MAP_AO_MODE_DIFFUSIVE_ESCAPE,
        "Diffusive",
        "Use a clearance-based diffusion field. This method does not support Same Mesh Only, Match by Isolation, Relative to Bounds, or Floor Occlusion",
    ),
)

MAP_AO_DIFFUSION_QUALITY_LOW = "LOW"
MAP_AO_DIFFUSION_QUALITY_MEDIUM = "MEDIUM"
MAP_AO_DIFFUSION_QUALITY_HIGH = "HIGH"

MAP_AO_DIFFUSION_QUALITY_ITEMS = (
    (MAP_AO_DIFFUSION_QUALITY_LOW, "Low", "Use a coarser field for faster bakes"),
    (MAP_AO_DIFFUSION_QUALITY_MEDIUM, "Medium", "Balance field resolution and bake cost"),
    (MAP_AO_DIFFUSION_QUALITY_HIGH, "High", "Use a finer field for stronger small-gap separation"),
)

MAP_ID_SOURCE_VERTEX_COLOR = "VERTEX_COLOR"
MAP_ID_SOURCE_FILE_ID = "FILE_ID"
MAP_ID_SOURCE_OBJECT = "OBJECT"
MAP_ID_SOURCE_MATERIAL = "MATERIAL"
MAP_ID_SOURCE_COLLECTION = "COLLECTION"
MAP_ID_SOURCE_COLOR_SET = "COLOR_SET"
MAP_ID_SOURCE_GROUP = "GROUP"

MAP_ID_SOURCE_ITEMS = (
    (MAP_ID_SOURCE_VERTEX_COLOR, "Vertex Color", "Use the source mesh vertex colors directly"),
    (MAP_ID_SOURCE_MATERIAL, "Material Color", "Color each high-poly face by its material: the viewport display color if set, else the Base Color, else a unique color per material"),
    (MAP_ID_SOURCE_FILE_ID, "File ID", "Assign ID colors by source file or mesh data"),
    (MAP_ID_SOURCE_OBJECT, "Mesh ID / Polygroup", "Assign a separate ID color to each source mesh or object"),
    (MAP_ID_SOURCE_COLLECTION, "Collection", "Assign ID colors by collection"),
    (MAP_ID_SOURCE_COLOR_SET, "Color Set", "Assign ID colors by the specified color-set label"),
    (MAP_ID_SOURCE_GROUP, "Bake Group", "Assign ID colors by bake group"),
)

# Legacy value: this used to be the `texture_set_name` property default, which made every
# out-of-box group claim a phantom "Default" set and write Default_*.tga. Groups now default
# to an empty (standalone) link; the name survives only so the schema-4 migration can
# recognise and clear that legacy stamp.
DEFAULT_TEXTURE_SET_NAME = "Default"

# Fixed job-protocol wire value. The project-level "Output Naming" property is gone --
# export settings and templates own naming now -- but the backend still reads an
# output-preset string from the job JSON and the binary job pack, so the addon always
# emits this constant. It is NOT a user-selectable setting; do not reintroduce one here.
OUTPUT_PRESET_PAINTER = "PAINTER"


def default_normal_format_for_map(map_type: str) -> str:
    normalized_map_type = str(map_type or "").strip().upper()
    # Substance Painter (and Unreal) decode tangent normals as DirectX (green = -Y);
    # only a plain OpenGL consumer wants +Y. Blender itself is OpenGL, which the
    # in-Blender previews already compensate for by inverting green.
    if normalized_map_type == MAP_NORMAL:
        return NORMAL_FORMAT_DIRECTX
    return NORMAL_FORMAT_OPENGL

OUTPUT_SIZE_512 = "SIZE_512"
OUTPUT_SIZE_1024 = "SIZE_1024"
OUTPUT_SIZE_2048 = "SIZE_2048"
OUTPUT_SIZE_4096 = "SIZE_4096"
OUTPUT_SIZE_8192 = "SIZE_8192"
OUTPUT_SIZE_CUSTOM = "CUSTOM"

OUTPUT_SIZE_ITEMS = (
    (OUTPUT_SIZE_512, "512", "Set output size to 512 x 512"),
    (OUTPUT_SIZE_1024, "1024", "Set output size to 1024 x 1024"),
    (OUTPUT_SIZE_2048, "2048", "Set output size to 2048 x 2048"),
    (OUTPUT_SIZE_4096, "4096", "Set output size to 4096 x 4096"),
    (OUTPUT_SIZE_8192, "8192", "Set output size to 8192 x 8192"),
    (OUTPUT_SIZE_CUSTOM, "Custom", "Use a custom output size"),
)

OUTPUT_SIZE_DIMENSIONS = {
    OUTPUT_SIZE_512: 512,
    OUTPUT_SIZE_1024: 1024,
    OUTPUT_SIZE_2048: 2048,
    OUTPUT_SIZE_4096: 4096,
    OUTPUT_SIZE_8192: 8192,
}


def output_size_preset_from_dimensions(width: int, height: int) -> str:
    if int(width) != int(height):
        return OUTPUT_SIZE_CUSTOM
    for preset_id, size in OUTPUT_SIZE_DIMENSIONS.items():
        if int(width) == size:
            return preset_id
    return OUTPUT_SIZE_CUSTOM

BIT_DEPTH_8 = "8"
BIT_DEPTH_16 = "16"

BIT_DEPTH_ITEMS = (
    (BIT_DEPTH_8, "8-bit", "Fast, preview-friendly output. Height, Position, Thickness and Bent Normal band at 8-bit"),
    (BIT_DEPTH_16, "16-bit", "Higher precision output and the default. Keeps the gradients of Height, Position, Thickness and Bent Normal"),
)

#: New projects open at 16-bit: banding in Height, Position, Thickness and Bent
#: Normal is a silent quality loss, and an artist who never opens the dropdown
#: should not inherit it. DEFAULT_IMAGE_FORMAT must be a format that can store it.
DEFAULT_BIT_DEPTH = BIT_DEPTH_16

IMAGE_FORMAT_TGA = "TGA"
IMAGE_FORMAT_PNG = "PNG"
IMAGE_FORMAT_EXR = "EXR"
IMAGE_FORMAT_TIFF = "TIFF"
#: Export-only. Bake still writes TGA/PNG/EXR/TIFF; DDS is produced by the
#: backend packer (DirectXTex). Kept out of IMAGE_FORMAT_ITEMS on purpose so the
#: bake-project format dropdown cannot ask the baker for a file type it cannot write.
IMAGE_FORMAT_DDS = "DDS"

IMAGE_FORMAT_ITEMS = (
    (IMAGE_FORMAT_TGA, "TGA", "Save as an uncompressed TGA file"),
    (IMAGE_FORMAT_PNG, "PNG", "Save as a PNG file"),
    (IMAGE_FORMAT_EXR, "EXR", "Save as a 32-bit floating-point OpenEXR file"),
    (IMAGE_FORMAT_TIFF, "TIFF", "Save as a TIFF file"),
)

#: Formats an output template / the Export Textures override may declare.
EXPORT_TEMPLATE_IMAGE_FORMAT_ITEMS = IMAGE_FORMAT_ITEMS + (
    (IMAGE_FORMAT_DDS, "DDS", "Save as a DDS file with BCn compression (backend packer)"),
)

#: PNG, not TGA: the default bit depth is 16 and TGA cannot store 16 bits per
#: channel (see BAKE_BIT_DEPTHS_BY_IMAGE_FORMAT below), so a TGA default would put
#: every new project on a combination preflight blocks. PNG is lossless, 16-bit
#: capable, and (at the same bit depth) roughly a quarter of TGA's file size.
DEFAULT_IMAGE_FORMAT = IMAGE_FORMAT_PNG

#: Bit depths the BAKE writer can encode per image format, mirroring
#: backend_image_io.cpp's encode_image_file(). EXR is absent on purpose: it always
#: writes float and ignores bit_depth entirely, so no depth is ever invalid for it.
#: (The Export Textures path has its own, Blender-side matrix in export_pack.py.)
BAKE_BIT_DEPTHS_BY_IMAGE_FORMAT: dict[str, tuple[str, ...]] = {
    IMAGE_FORMAT_TGA: (BIT_DEPTH_8,),
    IMAGE_FORMAT_PNG: (BIT_DEPTH_8, BIT_DEPTH_16),
    IMAGE_FORMAT_TIFF: (BIT_DEPTH_8, BIT_DEPTH_16),
}


def bake_image_format_supports_bit_depth(image_format: str, bit_depth) -> bool:
    """Whether the bake writer can encode `bit_depth` for `image_format`.

    Unknown formats and EXR return True: only combinations the writer provably
    rejects may block a bake."""
    supported = BAKE_BIT_DEPTHS_BY_IMAGE_FORMAT.get(str(image_format or "").strip().upper())
    if not supported:
        return True
    try:
        normalized = str(int(str(bit_depth).strip()))
    except (TypeError, ValueError):
        return True
    return normalized in supported


def bake_image_format_bit_depth_message(image_format: str, bit_depth) -> str:
    """Actionable one-liner for an unsupported format/depth pair ("" when valid)."""
    normalized_format = str(image_format or "").strip().upper()
    supported = BAKE_BIT_DEPTHS_BY_IMAGE_FORMAT.get(normalized_format)
    if not supported or bake_image_format_supports_bit_depth(normalized_format, bit_depth):
        return ""
    depth_text = str(bit_depth).strip()
    alternatives = [
        candidate
        for candidate, depths in BAKE_BIT_DEPTHS_BY_IMAGE_FORMAT.items()
        if str(depth_text) in depths
    ]
    alternatives.append(IMAGE_FORMAT_EXR)
    return (
        f"{normalized_format} output cannot be written at {depth_text}-bit. "
        f"Set Depth to {'-bit or '.join(supported)}-bit, or switch Format to "
        f"{' / '.join(alternatives)}."
    )

ANTI_ALIASING_1X = "1X"
ANTI_ALIASING_2X = "2X"
ANTI_ALIASING_4X = "4X"
ANTI_ALIASING_8X = "8X"

ANTI_ALIASING_ITEMS = (
    (ANTI_ALIASING_1X, "1 Sample", "Use one centered sample per output pixel. Fastest, with no spatial anti-aliasing"),
    (ANTI_ALIASING_2X, "4 Samples", "Use 4 offset samples per output pixel to smooth edges and fine relief; slightly increases bake time"),
    (ANTI_ALIASING_4X, "16 Samples", "Use 16 jittered passes for noticeably smoother curvature and normal edges; moderate bake-time increase, no extra memory"),
    (ANTI_ALIASING_8X, "64 Samples", "Maximum smoothing. 64 jittered passes for hero assets and close-ups; largest bake-time increase, no extra memory"),
)

# The user-facing control is now a free integer sample count (aa_samples). The
# legacy anti_aliasing enum is retained for saved-file migration and graceful
# degradation against older backends. These map the two representations onto the
# same Marmoset ladder (1 / 4 / 16 / 64 jittered sample passes).
ANTI_ALIASING_SAMPLE_COUNTS = {
    ANTI_ALIASING_1X: 1,
    ANTI_ALIASING_2X: 4,
    ANTI_ALIASING_4X: 16,
    ANTI_ALIASING_8X: 64,
}

DEFAULT_AA_SAMPLES = 4
# The sample count is the whole anti-aliasing control. 0 is the off position and
# resolves to a single un-jittered sample; 1 is the lowest count that still runs
# the sampler. AA_SAMPLES_MIN is the floor for an *active* count, not for the UI.
AA_SAMPLES_UI_MIN = 0
AA_SAMPLES_OFF_PASSES = 1
AA_SAMPLES_MIN = 1
AA_SAMPLES_MAX = 256


def anti_aliasing_to_samples(value):
    """Sample-pass count for a legacy anti_aliasing enum identifier."""
    return ANTI_ALIASING_SAMPLE_COUNTS.get(str(value), DEFAULT_AA_SAMPLES)


def samples_to_anti_aliasing(count):
    """Nearest legacy enum <= the given sample count (older-backend fallback)."""
    try:
        n = int(count)
    except (TypeError, ValueError):
        n = DEFAULT_AA_SAMPLES
    if n >= 64:
        return ANTI_ALIASING_8X
    if n >= 16:
        return ANTI_ALIASING_4X
    if n >= 4:
        return ANTI_ALIASING_2X
    return ANTI_ALIASING_1X


TANGENT_MIKKTSPACE = "MIKKTSPACE"
#: Legacy stored value. Blender's own tangent basis IS MikkTSpace, so the old
#: "Blender" option never matched anything Blender computes: the backend built a
#: flat per-triangle basis from the face normal with a flipped bitangent, which
#: bakes green-flipped, faceted normal maps on any smooth-shaded low mesh.
#: Projects that still store it are migrated to MikkTSpace on load and the
#: backend resolves the string to MikkTSpace either way.
TANGENT_BLENDER = "BLENDER"

TANGENT_BASIS_ITEMS = (
    (TANGENT_MIKKTSPACE, "MikkTSpace", "Standard MikkTSpace tangent basis, the one Blender, Substance Painter and Marmoset use"),
)


def normalize_tangent_basis(value) -> str:
    """Map any stored tangent-basis value onto the single supported basis."""
    # Every value ever stored ("MIKKTSPACE", legacy "BLENDER", or "" from an
    # enum whose stored item no longer exists) means MikkTSpace.
    del value
    return TANGENT_MIKKTSPACE

BAKE_MODE_OFFLINE = "OFFLINE"
BAKE_MODE_DRAFT = "DRAFT"
BAKE_MODE_FINAL = "FINAL"

BAKE_MODE_ITEMS = (
    (BAKE_MODE_OFFLINE, "Offline", "Run a standard bake job"),
    (BAKE_MODE_DRAFT, "Draft", "Use faster, lower-quality settings for test bakes"),
    (BAKE_MODE_FINAL, "Final", "Use full-quality settings for final output"),
)

EXECUTION_BACKEND_AUTO               = "AUTO"
EXECUTION_BACKEND_GPU_PREFERRED      = "GPU_PREFERRED"
EXECUTION_BACKEND_GPU_D3D12          = "GPU_D3D12"
EXECUTION_BACKEND_GPU_D3D12_DXR      = "GPU_D3D12_DXR"
EXECUTION_BACKEND_GPU_D3D12_WORK_GRAPHS = "GPU_D3D12_WORK_GRAPHS"

BAKE_DEVICE_BOTH = "BOTH"
BAKE_DEVICE_GPU = "GPU"
# Legacy preference value. Kept for .blend migration only — no longer offered in the UI.
# Old "CPU" / Embree-only choices migrate to BOTH (GPU primary + Cycles handoff on failure).
BAKE_DEVICE_CPU = "CPU"

# Top-level bake renderer (distinct from bake_device / execution_backend, which are
# FYR-internal GPU routing). AUTO picks FYR when the native backend is available.
RENDER_BACKEND_AUTO = "AUTO"
RENDER_BACKEND_FYR = "FYR"
RENDER_BACKEND_CYCLES = "CYCLES"

RENDER_BACKEND_ITEMS = (
    (RENDER_BACKEND_AUTO,
     "Auto",
     "Use FYR when the native GPU baker is available; otherwise bake through Blender/Cycles"),
    (RENDER_BACKEND_FYR,
     "FYR",
     "Force the native FYR GPU baker. Fails if the backend executable is unavailable"),
    (RENDER_BACKEND_CYCLES,
     "Cycles",
     "Force Blender/Cycles for supported projection maps (A/B triage and non-Windows recovery)"),
)

BAKE_DEVICE_ITEMS = (
    (BAKE_DEVICE_BOTH,
     "Both",
     "Recommended. Use the hybrid production path with GPU projection/shading and CPU secondary-ray work when available"),
    (BAKE_DEVICE_GPU,
     "GPU",
     "Prefer the best available GPU path. Uses DXR when available, otherwise DirectX 12 compute"),
)

# Internal native-GPU execution backends. GPU failure hands off to Blender/Cycles.
EXECUTION_BACKEND_PREFERENCE_ITEMS = (
    (EXECUTION_BACKEND_AUTO,
     "Auto",
     "Use the best available GPU path; hand off to Blender/Cycles if GPU baking is unavailable"),
    (EXECUTION_BACKEND_GPU_PREFERRED,
     "GPU Preferred",
     "Force the best available GPU path. Uses DXR when available, otherwise DirectX 12 compute"),
    (EXECUTION_BACKEND_GPU_D3D12,
     "GPU (D3D12 Compute)",
     "Force DirectX 12 compute-shader path. CPU (Embree) used in parallel for secondary rays"),
    (EXECUTION_BACKEND_GPU_D3D12_DXR,
     "GPU (DXR Hardware RT)",
     "Force DirectX Raytracing hardware acceleration. CPU (Embree) used in parallel for secondary rays"),
)

# Backend error markers that mean "retry these maps via Blender/Cycles".
CYCLES_HANDOFF_MARKERS = (
    "GPU_UNAVAILABLE_USE_CYCLES",
    "GPU_FAILED_USE_CYCLES",
)

# The backend refuses a bake group whose hardware-RT scene cannot fit the VRAM budget
# with this marker inside the GPU_FAILED_USE_CYCLES text (2026-09-14, a 20-part group
# of 41.8M triangles drove the driver into a device loss before it existed).
GPU_GROUP_TOO_LARGE_MARKER = "GPU_GROUP_TOO_LARGE"

# Automatic Cycles recovery runs `bpy.ops.object.bake` synchronously on the main
# thread, one Cycles pass at a time, and Cancel cannot run until that pass returns. On
# a scene of tens of millions of triangles that is minutes per map and hours per bake,
# with Blender reading as "Not Responding" the whole time. Above this many high-poly
# triangles the automatic retry is refused with an explanation instead; an explicit
# Cycles renderer choice is still honoured. Sized from the Pottery fixture, whose
# 14.8M-triangle high bakes through Cycles in acceptable time.
CYCLES_AUTO_RECOVERY_MAX_TRIANGLES = 16_000_000

# Cost gate for the automatic Cycles retry, independent of triangle count: groups x
# maps x Cycles passes x this many seconds per pass. A transient device loss on a
# 300-group bake once became about 1200 passes (about 2.5 hours). Above the ceiling the
# automatic retry is refused and the artist is offered the manual Cycles route.
CYCLES_AUTO_RECOVERY_SECONDS_PER_PASS = 8.0
CYCLES_AUTO_RECOVERY_MAX_SECONDS = 120.0

# Transient GPU failures (device removed/hung/reset, TDR, out of memory) are retried on a
# fresh bake worker before any Cycles hand-off. Each retry resends the same job with
# FYR_BAKER_TEXTURE_SET_BATCH_SOURCES at this fraction of the batch size the failed run
# used (halve, then quarter). At most GPU_TRANSIENT_RETRY_MAX retries.
GPU_TRANSIENT_RETRY_BATCH_ENV = "FYR_BAKER_TEXTURE_SET_BATCH_SOURCES"
GPU_TRANSIENT_RETRY_DIVISORS = (2, 4)
GPU_TRANSIENT_RETRY_MAX = len(GPU_TRANSIENT_RETRY_DIVISORS)
# Backend default when the env var is unset (backend_bake_pipeline.cpp: one DXR instance-mask bit per high).
GPU_TEXTURE_SET_BATCH_SOURCES_DEFAULT = 8

# Device used for Cycles-primary / Cycles-recovery bakes. This is Blender's own
# `scene.cycles.device`, not the FYR-internal bake_device / execution_backend.
# Material-channel bakes that run *alongside* a healthy FYR GPU bake stay on CPU
# regardless of this preference — they must not contend with GPU projection.
CYCLES_DEVICE_CPU = "CPU"
CYCLES_DEVICE_GPU = "GPU"

CYCLES_DEVICE_ITEMS = (
    (CYCLES_DEVICE_CPU,
     "CPU",
     "Bake with Cycles on the CPU. Always available"),
    (CYCLES_DEVICE_GPU,
     "GPU Compute",
     "Bake with Cycles on the GPU using the compute device configured in "
     "Blender Preferences > System (OptiX / CUDA / HIP / Metal / oneAPI). "
     "Falls back to CPU when no compute device is enabled"),
)

# Projection map types Cycles can recover when Fyr GPU baking fails.
# Keep in sync with addon/cycles_projection.py::_CYCLES_MAP_STRATEGIES.
CYCLES_PROJECTION_MAP_TYPES = frozenset({
    MAP_NORMAL,
    MAP_OBJECT_NORMAL,
    MAP_WORLD_NORMAL,
    MAP_AO,
    MAP_POSITION,
    MAP_OPACITY,
    MAP_VERTEX_COLOR,
    MAP_ATTRIBUTE,
    MAP_DERIVATIVE,
    MAP_ID,
    MAP_CURVATURE,
    MAP_PRINCIPAL_CURVATURE,
    MAP_CAVITY,
    MAP_CONCAVE,
    MAP_CONVEX,
    MAP_THICKNESS,
    MAP_HEIGHT,
    MAP_ENV_LIGHT,
    MAP_SCENE_LIGHTING,
    MAP_LIGHTING,
    MAP_LIT_COLOR,
    MAP_DIRECT_LIGHTING,
    MAP_INDIRECT_LIGHTING,
    MAP_SPECULAR_LIGHTING,
    MAP_DENSITY,
    MAP_BENT_NORMAL,
    MAP_CURVATURE_DIRECTION,
})

# Map types Fyr can bake but Cycles recovery cannot. Shown in map settings so
# artists know a GPU failure will not recover these rows.
#
# Empty since 2026-08-12: Bent Normal (six directional visibility probes), Density
# (inward+outward occupancy probe) and Curvature Direction (structure tensor of the
# baked normal field) all have Cycles routes now — see cycles_projection. They are
# approximations, which the map fidelity table already reports; that is a different
# statement from "cannot recover" and belongs in tooltips, not here.
CYCLES_UNSUPPORTED_MAP_TYPES: frozenset[str] = frozenset()

# ---------------------------------------------------------------------------
# Map stack presets.
#
# These name the JOB, not a destination engine. The previous set ("Painter Core",
# "Unreal Core", "Unity Core") named three engines and gave them near-identical
# stacks of Normal/AO/Curvature, which described none of them: engines do not
# consume a curvature map, texturing tools do. Painter Core was also byte-identical
# to DEFAULT_ENABLED_MAPS, so it did nothing at all on a fresh project.
#
# The identifiers are operator-property values, never stored in a .blend, so
# unlike MAP_TYPE_ITEMS this tuple is free to change. LEGACY_MAP_STACK_ALIASES
# below keeps an old identifier working if one reaches us from a saved Quick
# Favourite or a user script.
# ---------------------------------------------------------------------------
MAP_STACK_TEXTURING = "TEXTURING"
MAP_STACK_TEXTURING_PLUS = "TEXTURING_PLUS"
MAP_STACK_DETAIL_MASKS = "DETAIL_MASKS"
MAP_STACK_LIGHTING_BAKE = "LIGHTING_BAKE"
MAP_STACK_NORMAL_ONLY = "NORMAL_ONLY"
MAP_STACK_AO_ONLY = "AO_ONLY"
MAP_STACK_CUSTOM = "CUSTOM"

#: Maps a texturing tool wants handed to it: surface detail, occlusion, and the
#: positional maps its smart materials and generators key off.
MAP_STACK_TEXTURING_MAPS: tuple[str, ...] = (
    MAP_NORMAL,
    MAP_AO,
    MAP_CURVATURE,
    MAP_THICKNESS,
    MAP_POSITION,
    MAP_ID,
)

#: The mask family: every map that isolates a region of the surface by shape.
MAP_STACK_DETAIL_MASK_MAPS: tuple[str, ...] = (
    MAP_CURVATURE,
    MAP_CAVITY,
    MAP_CONCAVE,
    MAP_CONVEX,
    MAP_DENSITY,
)

MAP_STACK_ITEMS = (
    (MAP_STACK_TEXTURING, "Texturing Mesh Maps",
     "Enable Normal, AO, Curvature, Thickness, Position, and ID"),
    (MAP_STACK_TEXTURING_PLUS, "Texturing Mesh Maps+",
     "The texturing set plus the mask family: Cavity, Concave, Convex, and Density"),
    (MAP_STACK_DETAIL_MASKS, "Detail Masks",
     "Enable Curvature, Cavity, Concave, Convex, and Density on their own"),
    (MAP_STACK_LIGHTING_BAKE, "Lighting Bake",
     "Enable Scene Lighting, Bent Normal, Environment Light, and AO"),
    (MAP_STACK_NORMAL_ONLY, "Normal Only", "Enable only the normal map"),
    (MAP_STACK_AO_ONLY, "AO Only", "Enable only the ambient occlusion map"),
    (MAP_STACK_CUSTOM, "Custom", "Leave the current map stack unchanged"),
)

#: Retired identifiers, mapped to their closest replacement. Painter Core and
#: Unity Core were both "the maps a texturing tool wants"; Unreal Core was the
#: same minus ID, which is not a distinction worth a menu entry.
LEGACY_MAP_STACK_ALIASES: dict[str, str] = {
    "PAINTER_CORE": MAP_STACK_TEXTURING,
    "UNREAL_CORE": MAP_STACK_TEXTURING,
    "UNITY_CORE": MAP_STACK_TEXTURING,
}

CAGE_MODE_DISTANCE = "DISTANCE"
CAGE_MODE_AUTOMATIC = "AUTOMATIC"
CAGE_MODE_CUSTOM = "CUSTOM"
CAGE_MODE_AUTO = CAGE_MODE_AUTOMATIC

CAGE_MODE_ITEMS = (
    (CAGE_MODE_DISTANCE, "Distance Based", "Expand the low-poly mesh by a uniform distance"),
    (CAGE_MODE_AUTOMATIC, "Automatic", "Fit the cage to the high-poly surface with a separate offset at each vertex"),
    (CAGE_MODE_CUSTOM, "Custom", "Use a cage object you provide"),
)

CAGE_PREVIEW_SCOPE_ACTIVE_GROUP = "ACTIVE_GROUP"
CAGE_PREVIEW_SCOPE_TEXTURE_SET = "TEXTURE_SET"
CAGE_PREVIEW_SCOPE_SELECTED_LOW_MESHES = "SELECTED_LOW_MESHES"
CAGE_PREVIEW_SCOPE_ALL = "ALL_GROUPS"

PREVIEW_ON_LOW_SCOPE_ACTIVE_GROUP = "ACTIVE_GROUP"
PREVIEW_ON_LOW_SCOPE_ALL_GROUPS = "ALL_GROUPS"

PREVIEW_ON_LOW_SCOPE_ITEMS = (
    (PREVIEW_ON_LOW_SCOPE_ALL_GROUPS, "All Bake Groups", "Preview every low-poly mesh in the project"),
    (PREVIEW_ON_LOW_SCOPE_ACTIVE_GROUP, "Active Bake Group", "Preview only the low-poly meshes in the active bake group"),
)

CAGE_PREVIEW_SCOPE_ITEMS = (
    (
        CAGE_PREVIEW_SCOPE_ACTIVE_GROUP,
        "Active Bake Group",
        "Preview only the cage for the active bake group",
    ),
    (
        CAGE_PREVIEW_SCOPE_TEXTURE_SET,
        "Active Texture Set",
        "Preview the cages for every bake group in the active texture set",
    ),
    (
        CAGE_PREVIEW_SCOPE_SELECTED_LOW_MESHES,
        "Selected Lows",
        "Preview the cages for the selected low-poly meshes",
    ),
    (
        CAGE_PREVIEW_SCOPE_ALL,
        "All",
        "Preview every cage in the active bake project",
    ),
)

OBJECT_ROLE_LOW = "LOW"
OBJECT_ROLE_HIGH = "HIGH"
OBJECT_ROLE_CAGE = "CAGE"

OBJECT_ROLE_ITEMS = (
    (OBJECT_ROLE_LOW, "Low", "Low-poly mesh that receives the baked texture"),
    (OBJECT_ROLE_HIGH, "High", "High-poly mesh that provides surface detail"),
)

TAG_ROLE_ITEMS = (
    (OBJECT_ROLE_LOW, "Low", "Low-poly mesh that receives the baked texture"),
    (OBJECT_ROLE_HIGH, "High", "High-poly mesh that provides surface detail"),
    (OBJECT_ROLE_CAGE, "Cage", "Mesh used as a custom projection cage"),
)

PREVIEW_MAP_ITEMS = MAP_TYPE_ITEMS

STATUS_IDLE = "Idle"
STATUS_EXPORTED = "Workspace exported"
STATUS_BAKING = "Baking"
STATUS_PAUSED = "Bake paused"
STATUS_CANCELLING = "Cancelling bake"
STATUS_CANCELLED = "Bake cancelled"
STATUS_COMPLETE = "Bake complete"
STATUS_FAILED = "Bake failed"

DEFAULT_RESOLUTION = 2048
DEFAULT_MARGIN = 16
DILATION_DISTANCE = "DISTANCE"
DILATION_INFINITE = "INFINITE"
DILATION_MODE_ITEMS = (
    (DILATION_DISTANCE, "Distance", "Extend UV island colors by the Dilation pixel distance", "DRIVER_DISTANCE", 0),
    (DILATION_INFINITE, "Infinite", "Extend UV island colors across all uncovered pixels", "FULLSCREEN_ENTER", 1),
)

# Soften (Marmoset parity). One project-wide value that every map inherits, with a
# per-map "Override Soften" escape hatch.
#
# The scale runs 0..2 and is LINEAR in blur radius: the output Gaussian's sigma is
# 2 * soften texels, so 0 is genuinely off -- no filter on any family -- and the shipped
# default of 0 leaves the raw bake exactly as it comes out. The raw bake is the product;
# smoothing is the artist's choice, never ours.
#
# This is ONLY the output blur. Curvature's normal-derivative kernel has its own width
# (curvature_soften, "Detail Smoothing"), calibrated against Marmoset reference bakes at
# 0.5, and is deliberately NOT driven from here -- folding the two together would mean
# either a dead zone at the bottom of this scale or a default that blurs every map.
DEFAULT_SOFTEN = 0.0
SOFTEN_MAX = 2.0

# ID is a hard-edged lookup mask: blending neighbouring ids invents colors that match no
# object or material, so Soften never applies to it.
MAP_SOFTEN_UNSUPPORTED = frozenset({MAP_ID, MAP_WIREFRAME})


def map_supports_soften(map_type: str) -> bool:
    return str(map_type or "").strip().upper() not in MAP_SOFTEN_UNSUPPORTED

# UDIM tiles. tile_number = UDIM_TILE_MIN + tile_u + 10 * tile_v, with tile_u limited to the
# ten-column convention. The upper bound matches Blender's tiled-image API; tiles outside the
# range are preflight errors, never silently cropped geometry.
UDIM_TILE_MIN = 1001
UDIM_TILE_MAX = 2000
UDIM_TILE_COLUMNS = 10
# A single triangle spanning more than this many tiles is rejected as broken UV geometry
# rather than allowing unbounded raster-primitive amplification.
UDIM_MAX_TILES_PER_TRIANGLE = 64
# Token Fyr writes into a Blender tiled-image filepath in place of the concrete tile number.
UDIM_PATH_TOKEN = "<UDIM>"
# Hard ceiling for any single tile's effective resolution. Blender's resolution properties use
# soft_max, which it does not enforce, and the reprojection path already hard-rejects above this
# (backend_texture_reprojection.cpp) -- so preflight must reject here rather than fail deep in
# the backend.
UDIM_TILE_RESOLUTION_MAX = 16384
# Texture-set tile selection modes.
UDIM_MODE_AUTOMATIC = "AUTOMATIC"
UDIM_MODE_EXPLICIT = "EXPLICIT"
UDIM_MODE_ITEMS = [
    (UDIM_MODE_AUTOMATIC, "Automatic", "Detect occupied UV tiles from the low meshes"),
    (UDIM_MODE_EXPLICIT, "Explicit", "Bake only the tiles listed below"),
]
# Per-tile override states in Automatic mode.
UDIM_TILE_OVERRIDE_NONE = "NONE"
UDIM_TILE_OVERRIDE_INCLUDE = "INCLUDE"
UDIM_TILE_OVERRIDE_EXCLUDE = "EXCLUDE"
UDIM_TILE_OVERRIDE_ITEMS = [
    (UDIM_TILE_OVERRIDE_NONE, "Auto", "Use automatic detection for this tile"),
    (UDIM_TILE_OVERRIDE_INCLUDE, "Include", "Bake this tile even if no geometry occupies it"),
    (UDIM_TILE_OVERRIDE_EXCLUDE, "Exclude", "Skip this tile even if geometry occupies it"),
]
DEFAULT_CAGE_OFFSET = 0.02
DEFAULT_PAINT_OFFSET_SCALE = 1.0
DEFAULT_PAINT_SKEW = 0.0
PAINT_IMAGE_DEFAULT_SIZE = 1024
# 4 samples by default: jittered passes smooth fine relief without extra memory.
# Marmoset defaults to 16; ours stays at 4 until sample passes are pipelined.
DEFAULT_ANTI_ALIASING = ANTI_ALIASING_2X
LIVE_NORMAL_PREVIEW_SCALE = 0.5
LIVE_NORMAL_PREVIEW_MIN_RESOLUTION = 256
LIVE_NORMAL_PREVIEW_MAX_RESOLUTION = 1024
LIVE_NORMAL_PREVIEW_MAX_MARGIN = 8
VIEWPORT_HIGH_TRIANGLE_BUDGET = 4096
VIEWPORT_HEATMAP_HIGH_TRIANGLE_BUDGET = 8192
VIEWPORT_HEATMAP_CAGE_TRIANGLE_BUDGET = 512
VIEWPORT_HEATMAP_LOW_THRESHOLD = 0.02
VIEWPORT_HEATMAP_HIGH_THRESHOLD = 0.08
VIEWPORT_RAY_MISS_SEGMENT_BUDGET = 160
VIEWPORT_RAY_MISS_MAX_TRIANGLE_RESOLUTION = 3
VIEWPORT_SKEW_SEGMENT_BUDGET = 221184
VIEWPORT_SKEW_MAX_TRIANGLE_RESOLUTION = 32
VIEWPORT_SKEW_LINE_LENGTH_SCALE = 0.043
VIEWPORT_INTERACTION_GRACE_SECONDS = 0.08
VIEWPORT_DEBUG_REFRESH_DELAY_SECONDS = 0.05
VIEWPORT_DEBUG_POLL_INTERVAL_SECONDS = 0.03

# Mirrored verbatim by strip_role_suffix in backend/src/master_baker_backend.cpp
# (tests/test_cage_coverage_cross_part.py asserts the parity). The long forms match
# collection_naming.ROLE_COLLECTION_TOKENS so an object named Barrel_lowpoly joins
# the same group its collection would.
ROLE_SUFFIXES = {
    OBJECT_ROLE_LOW: (
        "_low", ".low", "-low", " low",
        "_lp", ".lp", "-lp", " lp",
        "_lowpoly", ".lowpoly", "-lowpoly", " lowpoly",
        "_lowres", ".lowres", "-lowres", " lowres",
    ),
    OBJECT_ROLE_HIGH: (
        "_high", ".high", "-high", " high",
        "_hp", ".hp", "-hp", " hp",
        "_highpoly", ".highpoly", "-highpoly", " highpoly",
        "_highres", ".highres", "-highres", " highres",
    ),
    OBJECT_ROLE_CAGE: ("_cage", ".cage", "-cage", " cage"),
}

# --- Texture Export dialog (docs/archive/TEXTURE_EXPORT_DIALOG_PLAN.md D5 / 3.1) -----
# Appended, never reordered: these tuples are stored by identifier in the .blend.

MESH_EXPORT_FBX = "FBX"
MESH_EXPORT_OBJ = "OBJ"
MESH_EXPORT_GLB = "GLB"

MESH_EXPORT_FORMAT_ITEMS = (
    (MESH_EXPORT_FBX, "FBX (.fbx)", "Write each exported texture set's low-poly meshes as an FBX file"),
    (MESH_EXPORT_OBJ, "OBJ (.obj)", "Write each exported texture set's low-poly meshes as a Wavefront OBJ file"),
    (MESH_EXPORT_GLB, "glTF Binary (.glb)", "Write each exported texture set's low-poly meshes as a binary glTF file"),
)

MESH_EXPORT_EXTENSIONS = {
    MESH_EXPORT_FBX: ".fbx",
    MESH_EXPORT_OBJ: ".obj",
    MESH_EXPORT_GLB: ".glb",
}

# First item of both override enums: keep whatever the output template asks for.
EXPORT_OVERRIDE_NONE = "NONE"

EXPORT_IMAGE_FORMAT_OVERRIDE_ITEMS = (
    (EXPORT_OVERRIDE_NONE, "Per Template", "Use the file type each template output declares"),
    (IMAGE_FORMAT_TGA, "TGA", "Save as an uncompressed TGA file"),
    (IMAGE_FORMAT_PNG, "PNG", "Save as a PNG file"),
    (IMAGE_FORMAT_EXR, "EXR", "Save as a 32-bit floating-point OpenEXR file"),
    (IMAGE_FORMAT_TIFF, "TIFF", "Save as a TIFF file"),
    (IMAGE_FORMAT_DDS, "DDS", "Save as a DDS file with BCn compression (backend packer)"),
)

EXPORT_BIT_DEPTH_OVERRIDE_ITEMS = (
    (EXPORT_OVERRIDE_NONE, "Per Template", "Use the bit depth each template output declares"),
    (BIT_DEPTH_8, "8-bit", "Fast preview-friendly output"),
    (BIT_DEPTH_16, "16-bit", "Higher precision output"),
)

# Per-set / global Size override (SP parity). FROM_SOURCE keeps the bake resolution;
# the numbered entries force a square export size through the backend packer.
EXPORT_SIZE_FROM_SOURCE = "FROM_SOURCE"
EXPORT_SIZE_ITEMS = (
    (EXPORT_SIZE_FROM_SOURCE, "From Source", "Keep each texture at the resolution it was baked"),
    ("128", "128", "Export at 128×128"),
    ("256", "256", "Export at 256×256"),
    ("512", "512", "Export at 512×512"),
    ("1024", "1024", "Export at 1024×1024"),
    ("2048", "2048", "Export at 2048×2048"),
    ("4096", "4096", "Export at 4096×4096"),
    ("8192", "8192", "Export at 8192×8192"),
)

EXPORT_RESIZE_FILTER_BOX = "BOX"
EXPORT_RESIZE_FILTER_TRIANGLE = "TRIANGLE"
EXPORT_RESIZE_FILTER_KAISER = "KAISER"
EXPORT_RESIZE_FILTER_ITEMS = (
    (EXPORT_RESIZE_FILTER_BOX, "Box", "Fast box filter, good for integer downscales"),
    (EXPORT_RESIZE_FILTER_TRIANGLE, "Triangle", "Smooth bilinear/triangle filter (default)"),
    (EXPORT_RESIZE_FILTER_KAISER, "Kaiser", "High-quality Kaiser/Fant filter, sharper downscales"),
)

EXPORT_PADDING_NONE = "NONE"
EXPORT_PADDING_INFINITE = "INFINITE"
EXPORT_PADDING_DISTANCE = "DISTANCE"
EXPORT_PADDING_MODE_ITEMS = (
    (EXPORT_PADDING_NONE, "From Bake", "Keep the padding already written into the baked maps"),
    (EXPORT_PADDING_INFINITE, "Dilation Infinite", "Stretch UV island borders until they meet (needs coverage)"),
    (EXPORT_PADDING_DISTANCE, "Dilation Distance", "Stretch UV island borders by a pixel distance (needs coverage)"),
)

# First item: a per-set override that means "use the Global settings row".
EXPORT_SET_USE_GLOBAL = "GLOBAL"
EXPORT_SET_SIZE_ITEMS = ((EXPORT_SET_USE_GLOBAL, "Use Global", "Use the Global Size setting"),) + EXPORT_SIZE_ITEMS
EXPORT_SET_RESIZE_FILTER_ITEMS = (
    (EXPORT_SET_USE_GLOBAL, "Use Global", "Use the Global resize filter"),
) + EXPORT_RESIZE_FILTER_ITEMS
EXPORT_SET_PADDING_MODE_ITEMS = (
    (EXPORT_SET_USE_GLOBAL, "Use Global", "Use the Global padding setting"),
) + EXPORT_PADDING_MODE_ITEMS

EXPORT_DDS_BC1 = "BC1"
EXPORT_DDS_BC3 = "BC3"
EXPORT_DDS_BC4 = "BC4"
EXPORT_DDS_BC5 = "BC5"
EXPORT_DDS_BC6H = "BC6H"
EXPORT_DDS_BC7 = "BC7"
EXPORT_DDS_COMPRESSION_ITEMS = (
    (EXPORT_DDS_BC1, "BC1 (DXT1)", "RGB with 1-bit alpha, the smallest colour DDS"),
    (EXPORT_DDS_BC3, "BC3 (DXT5)", "RGBA, the classic game-engine colour+alpha"),
    (EXPORT_DDS_BC4, "BC4", "Single-channel (masks, roughness)"),
    (EXPORT_DDS_BC5, "BC5", "Two-channel (tangent-space normals as AG)"),
    (EXPORT_DDS_BC6H, "BC6H", "HDR RGB"),
    (EXPORT_DDS_BC7, "BC7", "High-quality RGBA (default)"),
)

EXPORT_TAB_SETTINGS = "SETTINGS"
EXPORT_TAB_TEMPLATE = "TEMPLATE"
EXPORT_TAB_EXPORT_LIST = "EXPORT_LIST"

#: Sentinel active_export_target value: the Global settings row is selected.
EXPORT_TARGET_GLOBAL = ""

EXPORT_DIALOG_TAB_ITEMS = (
    (EXPORT_TAB_SETTINGS, "Export Settings", "Choose the texture sets, destination, template and overrides", "SETTINGS", 0),
    (EXPORT_TAB_EXPORT_LIST, "Export List", "Review every file this export will write", "LONGDISPLAY", 1),
)

# Sub-directory of the export destination that receives full-precision EXR
# intermediates when a future increment adds the forced-EXR warm bake
# (plan D4). Named here so the packer and any cleanup pass agree on it.
EXPORT_INTERMEDIATE_DIRNAME = ".export_intermediate"
# ---------------------------------------------------------------------------
# Standalone backend installer
#
# The Superhive channel ships an add-on with no native payload; the backend
# arrives through a separate signed installer instead (marketplace review does
# not accept a bundled executable). These values are the contract between the
# installer and `runtime.resolve_backend_executable()`, so BOTH sides import
# them from here. Changing one without the other produces an add-on that cannot
# find a backend the user did install, which reports as "no backend" and
# silently falls back to Cycles.
#
# The payload keeps the SAME relative layout as the bundled build
# (`bin/windows-x64/`, with the Agility SDK under `D3D12/`). The backend loads
# D3D12Core.dll from a path relative to its own exe, so mirroring the layout is
# what lets one binary work from either location unchanged.
# ---------------------------------------------------------------------------

#: Registry key the installer writes, under HKLM for an all-users install and
#: HKCU for a per-user one. Read-only from the add-on's side.
BACKEND_INSTALL_REGISTRY_KEY = r"SOFTWARE\FyrPlugins\FyrBaker"

#: Value under that key holding the installation root (not the exe itself), so a
#: custom install directory is still discoverable.
BACKEND_INSTALL_REGISTRY_VALUE = "InstallPath"

#: Where the executable sits beneath the installation root.
BACKEND_INSTALL_RELATIVE_DIR = "bin/windows-x64"

#: Directory name used under %ProgramFiles% / %LOCALAPPDATA%\Programs when the
#: user takes the default install location.
BACKEND_INSTALL_DIRNAME = "FyrBaker"

#: Where to send someone whose backend is missing. Deliberately the support
#: page and not a download page: a marketplace customer got the installer from
#: the store they bought from, not from fyrplugins.com, so naming a download
#: page here would send half the audience to the wrong place. (/downloads is
#: also a soft 404 on the live site.)
BACKEND_INSTALLER_HELP_URL = "https://fyrplugins.com/support"
DOCUMENTATION_URL = "https://docs.fyrplugins.com/"

# --- Cycles memory guard and row strips (addon/cycles_memory.py) -------------------------
# Every number the Cycles memory planner uses lives here so it can be calibrated against
# measured peaks without touching the planner. Byte figures are per texel of the BAKE
# IMAGE that one bpy.ops.object.bake call holds (a strip, or the whole image).

#: Largest strip (texels) one Cycles bake call may cover. Anything larger is baked as
#: full-width row strips even when memory would allow more, so a 16K map never asks
#: Blender for one ~32 GB selected-to-active allocation. Overridden by the env var below.
CYCLES_STRIP_MAX_TEXELS = 8192 * 8192
CYCLES_STRIP_MAX_TEXELS_ENV_VAR = "FYR_BAKER_CYCLES_STRIP_MAX_TEXELS"
#: Smallest strip the planner will use (rows); the planner also keeps at least 4x the
#: apron so a strip never spends most of its rows on overlap.
CYCLES_STRIP_MIN_ROWS = 256
#: Temporary UV layer a striped bake rasterizes through (never the artist's own UVs).
CYCLES_STRIP_UV_LAYER_NAME = "__fyr_strip_uv"
#: Headroom kept free for Blender, the OS and everything else: max(floor, fraction of RAM).
CYCLES_MEMORY_RESERVE_MIN_BYTES = int(1.5 * 1024 ** 3)
CYCLES_MEMORY_RESERVE_FRACTION = 0.08
#: "0" disables the refusal (strips are still planned from the area cap and memory).
CYCLES_MEMORY_GUARD_ENV_VAR = "FYR_BAKER_CYCLES_MEMORY_GUARD"
#: Blender selected-to-active bake, per texel of the bake image: low + high BakePixel
#: arrays (2 x 36 B), the result buffer (12 B), the float target (16 B), the margin
#: filter's duplicate of the target (16 B) and masks (3 B). All alive during margin.
CYCLES_BAKE_BYTES_PER_TEXEL_S2A_FLOAT = 119
#: Same with an 8-bit target image (target and its margin duplicate shrink).
CYCLES_BAKE_BYTES_PER_TEXEL_S2A_BYTE = 99
#: One BakePixel array; a bake with no high-poly (self bake) has only the low's.
CYCLES_BAKE_PIXEL_ARRAY_BYTES = 36
#: What the two figures above leave out: the Cycles session's own per-texel buffers
#: (render buffers / film passes, and Blender's render result they are copied through).
#: Measured on 5.2, peak commit between 1024^2 and 2048^2 bakes of the same scene
#: (marginal bytes per texel): material Albedo selected-to-active float 266, material
#: self bake float 223, projection Normal selected-to-active 8-bit 248, Height 264,
#: tangent Bent Normal 359. 119 + 147 = 266, 99 + 147 = 246, 83 + 147 = 230.
CYCLES_BAKE_ENGINE_BYTES_PER_TEXEL = 147
#: Per-bake memory that does not scale with the image (Cycles kernels, session, BVH
#: bookkeeping): the intercept of the same measurements was 130-240 MB.
CYCLES_BAKE_FIXED_BYTES = 256 * 1024 ** 2
#: Extra per-texel cost of the derived projection maps over their base bake (scratch
#: images held across passes + the compose step's NumPy temporaries). Measured as
#: above: Height +16 over a float target, tangent Bent Normal +111 over an 8-bit one;
#: Curvature Direction (gradients) is not measured and keeps its estimate.
CYCLES_DERIVED_EXTRA_BYTES_PER_TEXEL = {
    "height": 24,
    "bent_normal": 112,
    "curvature_direction": 32,
}
#: Per-texel cost of stitching one strip into the final file: the strip's pixels
#: copied out (16 B) plus the copy Blender saves (up to 16 B).
CYCLES_STRIP_ASSEMBLY_BYTES_PER_TEXEL = 32
#: Cycles scene cost per evaluated triangle (mesh arrays + BVH) for highs and lows.
#: Measured 2026-09-27 on 5.2.1: a 15.0M-triangle textureless high added 6.95 GB of
#: peak private memory to a 1024^2 material bake (~463 B/triangle incl. the tiny image).
CYCLES_HIGH_TRIANGLE_BYTES = 460
CYCLES_LOW_TRIANGLE_BYTES = 200
#: Image texture cost in Cycles per texel by pixel storage. 8-bit is NOT 4 B in
#: practice: the same bake with 8 x 8192^2 8-bit sRGB PNGs on the high cost 8.8 GB more
#: than without them (~16.4 B/texel), i.e. the textures end up at float size.
CYCLES_IMAGE_BYTES_PER_TEXEL_BYTE = 16
CYCLES_IMAGE_BYTES_PER_TEXEL_HALF = 8
CYCLES_IMAGE_BYTES_PER_TEXEL_FLOAT = 16
#: What Blender's Image.save() writes by default, measured on 5.1/5.2: PNG at zlib level
#: 1 and JPEG at quality 90. The strip assembler writes the final file the same way so a
#: striped map is not larger (or lossier) than the same map saved whole.
CYCLES_STRIP_PNG_COMPRESSION_LEVEL = 1
CYCLES_STRIP_JPEG_QUALITY = 90
