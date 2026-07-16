# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2023, Valeriy Yatsenko

''' Zen UV Transform System Labels '''


class TrLabels:

    PANEL_TRANSFORM_LABEL = "Transform"

    PROP_MOVE_INCREMENT_LABEL = "Increment"

    PROP_TRANSFORM_TYPE_LABEL = "Mode"
    PROP_TRANSFORM_TYPE_DESC = "Transform Mode. Affect Islands or Elements (vertices, edges, polygons)"

    PROP_ROTATE_ANGLE_LABEL = "Rotation Angle"
    PROP_ROTATE_ANGLE_DESC = "Full angle including a number sign indicating the direction of rotation. A negative value means that the turn will be made counterclockwise"

    PROP_ROTATE_INCREMENT_LABEL = "Rotation Increment"
    PROP_ROTATE_INCREMENT_DESC = "Island rotation angle"

    OT_ARRANGE_LABEL = "Arrange"
    OT_ARRANGE_DESC = "Arrange selected islands"

    PROP_ARRANGE_QUANT_U_LABEL = "Quant U"
    PROP_ARRANGE_QUANT_U_DESC = "Divider for UV Area in U direction"
    PROP_ARRANGE_QUANT_V_LABEL = "Quant V"
    PROP_ARRANGE_QUANT_V_DESC = "Divider for UV Area in V direction"

    PROP_ARRANGE_COUNT_U_LABEL = "Count U"
    PROP_ARRANGE_COUNT_U_DESC = "The number of islands in the UV Area range"
    PROP_ARRANGE_COUNT_V_LABEL = "Count V"
    PROP_ARRANGE_COUNT_V_DESC = "The number of islands in the UV Area range"

    PROP_ARRANGE_POSITION_LABEL = "Position"
    PROP_ARRANGE_POSITION_DESC = "Offset for current Position"
    PROP_ARRANGE_LIMIT_LABEL = "Limit"
    PROP_ARRANGE_LIMIT_DESC = "Distribution Limit"

    PROP_ARRANGE_INP_MODE_LABEL = "Mode"
    PROP_ARRANGE_INP_MODE_DESC = "Input mode"

    PROP_ARRANGE_INP_MODE_SIMPL_LABEL = "Simplified"
    PROP_ARRANGE_INP_MODE_ADV_LABEL = "Advanced"

    PROP_ARRANGE_START_FROM_LABEL = "Start from"
    PROP_ARRANGE_START_FROM_DESC = "The position from which the distribution begins"

    PROP_ARRANGE_RANDOMIZE_LABEL = "Randomize"
    PROP_ARRANGE_RANDOMIZE_DESC = "Change transformation in the set ranges by random value"

    PROP_ARRANGE_SEED_LABEL = "Seed"
    PROP_ARRANGE_SEED_DESC = "Change transformation in the set ranges by random value"

    PROP_ARRANGE_SCALE_LABEL = "Scale"
    PROP_ARRANGE_SCALE_DESC = "Changes the scale of each island separately"

    # Props Randomize Transform
    # OT_RANDOMIZE_TRANSFORM_LABEL = "Randomize"
    # OT_RANDOMIZE_TRANSFORM_DESC = "Randomize Transformation"
    # PROP_RAND_TRANS_MODE_LABEL = "Transform Mode"
    # PROP_RAND_TRANS_MODE_DESC = "Set transform mode"
    # PROP_RAND_POS_LABEL = "Position"
    # PROP_RAND_POS_DESC = "Location range"
    # PROP_RAND_ROT_LABEL = "Rotation"
    # PROP_RAND_ROT_DESC = "Rotation angle range"
    # PROP_RAND_SCALE_LABEL = "Scale"
    # PROP_RAND_SCALE_DESC = "Scale range"
    # PROP_RAND_LOCK_LABEL = "Lock Axes"
    # PROP_RAND_LOCK_DESC = "Lock values for uniform transformation over the axes"
    # PROP_RAND_SHAKE_LABEL = "Seed"
    # PROP_RAND_SHAKE_DESC = "Change transformation in the set ranges by random value"

    # Fit Region
    PREF_OT_PASTE_MATCH_LABEL = "Match"
    PREF_OT_PASTE_MATCH_DESC = "Match horizontal or vertical"
    PREF_OT_AREA_MATCH_LABEL = "Area Matching"
    PREF_OT_AREA_MATCH_DESC = "Set strict requirements to Islands Area Matching when Stacking. Disable this option if the Islands have a slightly different Area"

    PREF_OT_PASTE_MATCH_HOR_LABEL = "Horizontally"
    PREF_OT_PASTE_MATCH_HOR_DESC = "Fit Islands horizontally"
    PREF_OT_PASTE_MATCH_VERT_LABEL = "Vertically"
    PREF_OT_PASTE_MATCH_VERT_DESC = "Fit Islands vertically"

    PREF_OT_FIT_REGION_FULL_LABEL = "Full"
    PREF_OT_FIT_REGION_FULL_DESC = "Fit Islands into region by longest side"

    # Scale Grab Size

    PREF_UNITS_LABEL = "Units"
    PREF_UNITS_DESC = "Texel density calculation units"

    # Fill
    TR_FILL_NO_PROPORTION_LABEL = "Fill Islands"
    TR_FILL_NO_PROPORTION_DESC = "Fit Islands from Center without keeping proportions"

    # Relax
    ZEN_RELAX_ICO = "relax-1_32"

    # Quadrify
    ZEN_QUADRIFY_ICO = "quadrify_32"
