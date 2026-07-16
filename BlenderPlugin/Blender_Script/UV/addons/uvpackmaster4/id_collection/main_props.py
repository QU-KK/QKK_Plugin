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

from . import IdCollectionAccess, IdCollectionBase, id_collection_item
from ..utils import redraw_ui
from ..app_iface import *
from ..spipeline.engine.labels import Labels
from ..props import (
    UVPM4_TrackGroupsProps,
    UVPM4_PackStrategyProps,
    PropConstants,
    UVPM4_OrientTo3dProps,
    UVPM4_SimilarityProps,
    UVPM4_SplitOverlapProps,
    UVPM4_TileTargetProps
)
from ..grouping_scheme import UVPM4_GroupingSchemeAccessDescriptorContainer
from ..spipeline.engine.island_params import AlignPriorityIParamInfo
from ..spipeline.engine.island_params import NormalizeMultiplierIParamInfo
from ..grouping import UVPM4_AutoGroupingOptions
from ..scripting import UVPM4_Scripting
from ..box import UVPM4_Box
from ..operator_islands import NumberedGroupIParamInfo
from ..box_utils import disable_box_rendering
from ..mode import ModeType
from ..pgroup import standalone_property_group
from ..spipeline.engine.types import (UvpmOverlapDetectionMode,
                                      UvpmPixelPerfectAlignTarget,
                                      UvpmPixelPerfectVertAlignMode,
                                      UvpmCoordSpace,
                                      GroupingMethod,
                                      UvpmTileFillingMethod)

from ..spipeline.engine.props import MainProps
from ..tdensity.tier import UVPM4_TDensityTierValue, UVPM4_TDensityValueToSet, UVPM4_TDensityValuePacking


class MainPropSetAccess(IdCollectionAccess):

    ENABLE_PROP_UI_LOCATION = "the 'Preferences' multi panel → 'Scene Options' → 'Enable Option Sets'"
    ITEM_LABEL = 'Option set'
    DEFAULT_ITEM_NAME = 'OptionSet'
    ICON = 'OPTIONS'
    DRAW_LABEL = False
    HELP_URL_SUFFIX = '/20-packing-functionalities/15-basic-packing-and-options/#option-sets'

    def _get_collection(self):
        return get_scene_props(self.context).main_prop_sets
    
    def _get_access_desc(self):
        return get_scene_props(self.context).main_prop_access_desc
    
    def _pre_remove_item(self, idx):
        if len(self.get_items()) == 1:
            raise RuntimeError("Cannot remove the last remaining set. Disable option sets for the given scene in {}, if you don't want to use them".format(self.ENABLE_PROP_UI_LOCATION))
    
    def state_changed_handler(self):
        disable_box_rendering(None, self.context)
        redraw_ui(self.context)

    

def _update_active_pack_mode_id(self, context):
    disable_box_rendering(None, context)


@standalone_property_group
class UVPM4_NumberedGroupsDescriptor:

    enable : BoolProperty(
        name=Labels.GROUPS_ENABLE_NAME,
        description=Labels.GROUPS_ENABLE_DESC,
        default=False)

    group_num : IntProperty(
        name=Labels.GROUP_NUM_NAME,
        description=Labels.GROUP_NUM_DESC,
        default=NumberedGroupIParamInfo.MIN_VALUE+1,
        min=NumberedGroupIParamInfo.MIN_VALUE+1,
        max=NumberedGroupIParamInfo.MAX_VALUE)

    use_g_scheme : BoolProperty(
        name='Use Grouping Scheme',
        description='Use a grouping scheme to define groups',
        default=False
    )

    iparam_name : StringProperty(default='')



@standalone_property_group
class UVPM4_NumberedGroupsDescriptorContainer:

    lock_group : PointerProperty(type=UVPM4_NumberedGroupsDescriptor)
    stack_group : PointerProperty(type=UVPM4_NumberedGroupsDescriptor)
    track_group : PointerProperty(type=UVPM4_NumberedGroupsDescriptor)
    norm_group : PointerProperty(type=UVPM4_NumberedGroupsDescriptor)


@id_collection_item
@standalone_property_group
class UVPM4_MainProps(MainProps):

    ACCESS_TYPE = MainPropSetAccess

    grouping_scheme_access_descriptors : PointerProperty(type=UVPM4_GroupingSchemeAccessDescriptorContainer)

    numbered_groups_descriptors : PointerProperty(type=UVPM4_NumberedGroupsDescriptorContainer)

    track_groups_props : PointerProperty(type=UVPM4_TrackGroupsProps)
    scripting : PointerProperty(type=UVPM4_Scripting)

    pack_strategy_props : PointerProperty(type=UVPM4_PackStrategyProps)

    precision : IntProperty(
        name=Labels.PRECISION_NAME,
        description=Labels.PRECISION_DESC,
        default=500,
        min=10,
        max=10000)

    margin : FloatProperty(
        name=Labels.MARGIN_NAME,
        description=Labels.MARGIN_DESC,
        min=0.0,
        max=0.2,
        default=0.003,
        precision=3,
        step=0.1)

    pixel_margin_enable : BoolProperty(
        name=Labels.PIXEL_MARGIN_ENABLE_NAME,
        description=Labels.PIXEL_MARGIN_ENABLE_DESC,
        default=False)

    pixel_margin : PropConstants.DEF__PIXEL_MARGIN

    pixel_border_margin_enable : BoolProperty(
        name=Labels.PIXEL_BORDER_MARGIN_ENABLE_NAME,
        description=Labels.PIXEL_BORDER_MARGIN_ENABLE_DESC,
        default=False)

    pixel_border_margin : PropConstants.DEF__PIXEL_BORDER_MARGIN
    extra_pixel_margin_to_others : PropConstants.DEF__EXTRA_PIXEL_MARGIN_TO_OTHERS
    pixel_margin_tex_size : PropConstants.DEF__PIXEL_MARGIN_TEX_SIZE
    pixel_perfect_align : BoolProperty(
        name=Labels.PIXEL_PERFECT_ALIGN_NAME,
        description=Labels.PIXEL_PERFECT_ALIGN_DESC,
        default=False)

    pixel_perfect_align_target : EnumProperty(
        items=UvpmPixelPerfectAlignTarget.to_blend_items(),
        name=Labels.PIXEL_PERFECT_ALIGN_TARGET_NAME,
        description=Labels.PIXEL_PERFECT_ALIGN_TARGET_DESC)

    pixel_perfect_vert_align_mode : EnumProperty(
        items=UvpmPixelPerfectVertAlignMode.to_blend_items(),
        name=Labels.PIXEL_PERFECT_VERT_ALIGN_MODE_NAME,
        description=Labels.PIXEL_PERFECT_VERT_ALIGN_MODE_DESC)

    rotation_enable : PropConstants.DEF__ROTATION_ENABLE

    pre_rotation_disable : PropConstants.DEF__PRE_ROTATION_DISABLE

    flipping_enable : BoolProperty(
        name=Labels.FLIPPING_ENABLE_NAME,
        description=Labels.FLIPPING_ENABLE_DESC,
        default=False)

    normalize_scale : BoolProperty(
        name=Labels.NORMALIZE_SCALE_NAME,
        description=Labels.NORMALIZE_SCALE_DESC,
        default=False)
    
    normalize_space : EnumProperty(
        items=UvpmCoordSpace.to_blend_items(),
        name=Labels.NORMALIZE_SPACE_NAME,
        description=Labels.NORMALIZE_SPACE_DESC)
    
    tdensity_set_before_pack : BoolProperty(
        name=Labels.TEXEL_DENSITY_SET_BEFORE_PACK_NAME,
        description=Labels.TEXEL_DENSITY_SET_BEFORE_PACK_DESC,
        default=False)
    
    tdensity_to_set : PointerProperty(type=UVPM4_TDensityValueToSet)
    tdensity_packing : PointerProperty(type=UVPM4_TDensityValuePacking)

    island_tdensity_packing : PointerProperty(type=UVPM4_TDensityTierValue)

    island_tdensity_set_before_pack : BoolProperty(
        name='Set TD Per-Island',
        description='',
        default=False
    )
    
    island_normalize_multiplier_enable : BoolProperty(
        name=Labels.ISLAND_NORMALIZE_MULTIPLIER_ENABLE_NAME,
        description=Labels.ISLAND_NORMALIZE_MULTIPLIER_ENABLE_DESC,
        default=False)
    
    island_normalize_multiplier : IntProperty(
        name=Labels.ISLAND_NORMALIZE_MULTIPLIER_NAME,
        description=Labels.ISLAND_NORMALIZE_MULTIPLIER_DESC,
        default=NormalizeMultiplierIParamInfo.DEFAULT_VALUE,
        min=NormalizeMultiplierIParamInfo.MIN_VALUE,
        max=NormalizeMultiplierIParamInfo.MAX_VALUE)

    scale_mode : PropConstants.DEF__SCALE_MODE

    rotation_step : PropConstants.DEF__ROTATION_STEP

    island_rot_step_enable : BoolProperty(
        name=Labels.ISLAND_ROT_STEP_ENABLE_NAME,
        description=Labels.ISLAND_ROT_STEP_ENABLE_DESC,
        default=False)

    island_rot_step : IntProperty(
        name=Labels.ISLAND_ROT_STEP_NAME,
        description=Labels.ISLAND_ROT_STEP_DESC,
        default=90,
        min=0,
        max=180)

    non_square_packing : BoolProperty(
        name=Labels.NON_SQUARE_PACKING_NAME,
        description=Labels.NON_SQUARE_PACKING_DESC,
        default=False)
    
    def get_pack_mode_blend_enums(scene, context):
        prefs = get_prefs()
        modes_info = prefs.get_modes(ModeType.PACK)

        return [(mode_id, mode_cls.enum_name(), "") for mode_id, mode_cls in modes_info]
    
    active_pack_mode_id : EnumProperty(
        items=get_pack_mode_blend_enums,
        update=_update_active_pack_mode_id,
        name=Labels.PACK_MODE_NAME,
        description=Labels.PACK_MODE_DESC)

    group_method_pack : EnumProperty(
        items=GroupingMethod.to_blend_items(),
        name="{} (Packing)".format(Labels.GROUP_METHOD_NAME),
        description=Labels.GROUP_METHOD_DESC,
        update=disable_box_rendering)

    auto_group_options : PointerProperty(type=UVPM4_AutoGroupingOptions)

    lock_overlapping_enable : BoolProperty(
        name=Labels.LOCK_OVERLAPPING_ENABLE_NAME,
        description=Labels.LOCK_OVERLAPPING_ENABLE_DESC,
        default=False)

    lock_overlapping_mode : EnumProperty(
        items=UvpmOverlapDetectionMode.to_blend_items(),
        name=Labels.LOCK_OVERLAPPING_MODE_NAME,
        description=Labels.LOCK_OVERLAPPING_MODE_DESC)

    heuristic_enable : BoolProperty(
        name=Labels.HEURISTIC_ENABLE_NAME,
        description=Labels.HEURISTIC_ENABLE_DESC,
        default=False)

    heuristic_search_time : IntProperty(
        name=Labels.HEURISTIC_SEARCH_TIME_NAME,
        description=Labels.HEURISTIC_SEARCH_TIME_DESC,
        default=0,
        min=0,
        max=3600)

    heuristic_max_wait_time : IntProperty(
        name=Labels.HEURISTIC_MAX_WAIT_TIME_NAME,
        description=Labels.HEURISTIC_MAX_WAIT_TIME_DESC,
        default=0,
        min=0,
        max=300)
        
    heuristic_allow_mixed_scales : BoolProperty(
        name=Labels.HEURISTIC_ALLOW_MIXED_SCALES_NAME,
        description=Labels.HEURISTIC_ALLOW_MIXED_SCALES_DESC,
        default=False)
    
    advanced_heuristic : BoolProperty(
        name=Labels.ADVANCED_HEURISTIC_NAME,
        description=Labels.ADVANCED_HEURISTIC_DESC,
        default=False)

    fully_inside : BoolProperty(
        name=Labels.FULLY_INSIDE_NAME,
        description=Labels.FULLY_INSIDE_DESC,
        default=True)

    custom_target_box_enable : BoolProperty(
        name=Labels.CUSTOM_TARGET_BOX_ENABLE_NAME,
        description=Labels.CUSTOM_TARGET_BOX_ENABLE_DESC,
        default=False,
        update=disable_box_rendering)

    custom_target_box : PointerProperty(type=UVPM4_Box)

    tile_target_props : PointerProperty(type=UVPM4_TileTargetProps)
    
    tile_filling_method : EnumProperty(
        items=UvpmTileFillingMethod.to_blend_items(),
        name=Labels.TILE_FILLING_METHOD_NAME,
        description=Labels.TILE_FILLING_METHOD_DESC)


    split_props : PointerProperty(type=UVPM4_SplitOverlapProps)

    # ------ Aligning properties ------ #

    simi_props : PointerProperty(type=UVPM4_SimilarityProps)

    align_priority_enable : BoolProperty(
        name=Labels.ALIGN_PRIORITY_ENABLE_NAME,
        description=Labels.ALIGN_PRIORITY_ENABLE_DESC,
        default=False)

    align_priority : IntProperty(
        name=Labels.ALIGN_PRIORITY_NAME,
        description=Labels.ALIGN_PRIORITY_DESC,
        default=int(AlignPriorityIParamInfo.DEFAULT_VALUE),
        min=int(AlignPriorityIParamInfo.MIN_VALUE),
        max=int(AlignPriorityIParamInfo.MAX_VALUE))

    orient_to3d_props : PointerProperty(type=UVPM4_OrientTo3dProps)
    

class UVPM4_MainPropIdCollection(IdCollectionBase):

    items : CollectionProperty(type=UVPM4_MainProps)
