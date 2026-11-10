# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Supra3D
"""Constants: colours, sizes, modifier type flags and header toggle tables."""


# =============================================================================
# Constants
# =============================================================================

FONT = 0

TOGGLE_OPERATOR = "view3d.modperf_lite"   # opens / closes the panel (keymap item)
PANEL_TITLE = "ModPerf Lite"

# Widgets that open a menu / popup: they act on mouse *release* like a normal
# click, so the release can't select the menu item under the cursor.
OPEN_ON_RELEASE = {'enum', 'add', 'popup', 'tmpl', 'search', 'op'}

# Colour coding for buttons (RGBA).
COL_ADD = (0.26, 0.45, 0.72, 1.0)      # blue   - add
COL_APPLY = (0.23, 0.52, 0.30, 1.0)    # green  - apply / apply all
COL_DELETE = (0.93, 0.16, 0.16, 1.0)   # bright red - delete
COLOR_OPACITY = 0.5                    # colour-coded buttons are drawn at 50 %
COLOR_OPACITY_STRONG = 0.75            # Apply / Apply All are drawn at 75 %
COLOR_OPACITY_REMOVE = 0.9             # the remove-modifier (X) button is drawn at 90 %

# Corner radii (points, scaled by the UI scale).
PANEL_RADIUS = 12.0                    # outer panel, title bar, drop shadow
BLOCK_RADIUS = 7.0                     # modifier headers, outliner box, sections
WIDGET_RADIUS = 4.5                    # buttons, fields, toggles

# Tooltips: same feel as Blender (appear after a short pause on a button).
TOOLTIP_DELAY = 0.5

# Header buttons that run a Blender operator: the tooltip shows that
# operator's own name and description, like Blender's UI does.
WIDGET_OPERATORS = {
    'apply': "object.modifier_apply",
    'remove': "object.modifier_remove",
    'move_up': "object.modifier_move_up",
    'move_down': "object.modifier_move_down",
    'mod_icon': "object.modifier_set_active",
}

# Widgets bound to an RNA property: tooltip = label, description, Python path.
PROP_WIDGETS = {'num', 'bool', 'enum', 'popup', 'toggle'}

MODIFIER_OBJECT_TYPES = {
    'MESH', 'CURVE', 'CURVES', 'SURFACE', 'FONT', 'LATTICE',
    'POINTCLOUD', 'VOLUME', 'GREASEPENCIL',
    'EMPTY',        # Geometry Nodes modifiers only (Blender 5)
}

# RNA properties that are drawn in the header (or are internal) and therefore
# not listed as settings in the body.
HIDDEN_PROPS = {
    'rna_type', 'name', 'type', 'show_viewport', 'show_render',
    'show_in_editmode', 'show_on_cage', 'show_expanded', 'is_active',
    'use_pin_to_last', 'is_override_data', 'use_apply_on_spline',
    'execution_time', 'persistent_uid',
}

# Header display toggles, drawn left -> right exactly like Blender's modifier
# panel header (MOD_ui_common.cc): On Cage, Edit Mode, Realtime, Render.
HEADER_TOGGLES = (
    ('show_on_cage', 'cage', "Adjust edit cage to modifier result"),
    ('show_in_editmode', 'edit', "Display modifier in Edit Mode"),
    ('show_viewport', 'viewport', "Display modifier in viewport"),
    ('show_render', 'render', "Use modifier during render"),
)


# Collision and Surface are always enabled: Blender hides their toggles.
NO_TOGGLE_TYPES = {'COLLISION', 'SURFACE'}

# ModifierTypeInfo flags from Blender 5.2.2's source (source/blender/modifiers),
# keyed by RNA struct: (SupportsEditmode, supports_mapping) where
# supports_mapping = OnlyDeform type or eModifierTypeFlag_SupportsMapping.
MODIFIER_FLAGS = {
    'ArmatureModifier': (1, 1),
    'ArrayModifier': (1, 1),
    'BevelModifier': (1, 0),
    'BooleanModifier': (1, 0),
    'BuildModifier': (0, 0),
    'CastModifier': (1, 1),
    'ClothModifier': (0, 1),
    'CollisionModifier': (0, 1),
    'CorrectiveSmoothModifier': (1, 1),
    'CurveModifier': (1, 1),
    'DataTransferModifier': (1, 1),
    'DecimateModifier': (0, 0),
    'DisplaceModifier': (1, 1),
    'DynamicPaintModifier': (0, 1),
    'EdgeSplitModifier': (1, 1),
    'ExplodeModifier': (0, 0),
    'FluidModifier': (0, 0),
    'GreasePencilArmatureModifier': (1, 1),
    'GreasePencilArrayModifier': (1, 1),
    'GreasePencilBuildModifier': (1, 0),
    'GreasePencilColorModifier': (1, 1),
    'GreasePencilDashModifierData': (1, 1),
    'GreasePencilEnvelopeModifier': (1, 1),
    'GreasePencilHookModifier': (1, 1),
    'GreasePencilLatticeModifier': (1, 1),
    'GreasePencilLengthModifier': (1, 0),
    'GreasePencilLineartModifier': (0, 0),
    'GreasePencilMirrorModifier': (1, 1),
    'GreasePencilMultiplyModifier': (1, 1),
    'GreasePencilNoiseModifier': (1, 1),
    'GreasePencilOffsetModifier': (1, 1),
    'GreasePencilOpacityModifier': (1, 1),
    'GreasePencilOutlineModifier': (1, 1),
    'GreasePencilShrinkwrapModifier': (1, 1),
    'GreasePencilSimplifyModifier': (1, 0),
    'GreasePencilSmoothModifier': (1, 1),
    'GreasePencilSubdivModifier': (1, 0),
    'GreasePencilTextureModifier': (1, 1),
    'GreasePencilThickModifierData': (1, 1),
    'GreasePencilTimeModifier': (1, 1),
    'GreasePencilTintModifier': (1, 1),
    'GreasePencilWeightAngleModifier': (1, 1),
    'GreasePencilWeightProximityModifier': (1, 1),
    'HookModifier': (1, 1),
    'LaplacianDeformModifier': (1, 1),
    'LaplacianSmoothModifier': (1, 1),
    'LatticeModifier': (1, 1),
    'MaskModifier': (1, 1),
    'MeshCacheModifier': (1, 1),
    'MeshDeformModifier': (1, 1),
    'MeshSequenceCacheModifier': (0, 0),
    'MeshToVolumeModifier': (0, 0),
    'MirrorModifier': (1, 1),
    'MultiresModifier': (0, 1),
    'NodesModifier': (1, 1),
    'NormalEditModifier': (1, 1),
    'OceanModifier': (1, 0),
    'ParticleInstanceModifier': (1, 1),
    'ParticleSystemModifier': (0, 1),
    'RemeshModifier': (1, 0),
    'ScrewModifier': (1, 0),
    'ShrinkwrapModifier': (1, 1),
    'SimpleDeformModifier': (1, 1),
    'SkinModifier': (1, 0),
    'SmoothModifier': (1, 1),
    'SoftBodyModifier': (0, 1),
    'SolidifyModifier': (1, 1),
    'SubsurfModifier': (1, 1),
    'SurfaceDeformModifier': (1, 1),
    'SurfaceModifier': (0, 1),
    'TriangulateModifier': (1, 1),
    'UVProjectModifier': (1, 1),
    'UVWarpModifier': (1, 0),
    'VertexWeightEditModifier': (1, 1),
    'VertexWeightMixModifier': (1, 1),
    'VertexWeightProximityModifier': (1, 1),
    'VolumeDisplaceModifier': (0, 0),
    'VolumeToMeshModifier': (0, 0),
    'WarpModifier': (1, 1),
    'WaveModifier': (1, 1),
    'WeightedNormalModifier': (1, 1),
    'WeldModifier': (1, 1),
    'WireframeModifier': (1, 0),
}


AXIS_LETTERS = "XYZW"
VECTOR_SUBTYPES = {'XYZ', 'TRANSLATION', 'EULER', 'DIRECTION', 'VELOCITY',
                   'ACCELERATION', 'XYZ_LENGTH', 'COORDINATES'}

DEFAULT_FOOTER = "{key}: Close   ·   Drag: Move"
