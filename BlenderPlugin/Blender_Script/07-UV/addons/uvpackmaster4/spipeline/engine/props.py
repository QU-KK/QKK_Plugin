from .param import EngineParamTarget, EngineParamUtils
from .geom.box import Box
from .utils import eprint
from .tdensity import TDensityTierIdCollection, TDensityTierValue, TDensityValue
from .labels import Labels
from .types import UvpmScaleMode
from .uc_entry import uc


class AppStateBase(EngineParamTarget):

    pack_ratio : float = 1.0
    scale_length : float
    editor_tile_grid : tuple[int, int]
    active_image_size : tuple[int, int]

    def active_image_size_safe(self):
        if any((s <= 0 for s in self.active_image_size)):
            raise RuntimeError('Active image not selected in the UV Editor')
        
        return self.active_image_size

    def active_image_ratio(self):
        active_size = self.active_image_size_safe()
        return float(active_size[0]) / float(active_size[1])
    
    def engine_init(self):
        from .geom import PACK_RATIO
        PACK_RATIO.set(self.pack_ratio)


class PackStrategyProps(EngineParamTarget):

    strategy : EngineParamUtils.ENUM_PARAM_TYPE
    start_corner : EngineParamUtils.ENUM_PARAM_TYPE

    def to_uc_params(self):
        params = uc.PackStrategyParams()
        params.strategy = uc.PackStrategy(self.strategy)
        params.start_corner = uc.BoxCorner(self.start_corner)

        return params


class NumberedGroupsDescriptor(EngineParamTarget):

    enable : bool
    group_num : int
    use_g_scheme : bool
    iparam_name : str


class SplitOverlapProps(EngineParamTarget):

    detection_mode : EngineParamUtils.ENUM_PARAM_TYPE    
    max_tile_x : int    
    dont_split_priorities : bool


class NumberedGroupsDescriptorContainer(EngineParamTarget):

    lock_group : NumberedGroupsDescriptor
    stack_group : NumberedGroupsDescriptor
    track_group : NumberedGroupsDescriptor
    norm_group : NumberedGroupsDescriptor


class TrackGroupsProps(EngineParamTarget):

    require_match_for_all : bool
    matching_mode : EngineParamUtils.ENUM_PARAM_TYPE

    
class TileTargetProps(EngineParamTarget):
    
    from .types import TileTargetMode

    mode : EngineParamUtils.ENUM_PARAM_TYPE

    use_editor_grid : bool
    
    tile_count_x : int
    tile_count_y : int
    
    start_tile_x : int
    start_tile_y : int
    
    tile_count : int
    tiles_in_row : int

    def validate_fail_msg(self):
        if self.mode == self.TileTargetMode.TILE_RANGE:
            if self.start_tile_x >= self.tiles_in_row:
                return "'{}' has to be lower than '{}'".format(Labels.START_TILE_X_NAME, Labels.TILES_IN_ROW_NAME)
            
        return None
            
    def validate(self):
        msg = self.validate_fail_msg()
        if msg is not None:
            raise RuntimeError('Tile setup: ' + msg)

    def get_target_boxes(self, app_state : AppStateBase):
        self.validate()

        unit_box = Box.unit_box()
        tile_grid = None

        if self.mode == self.TileTargetMode.TILE_GRID:
            if self.use_editor_grid:
                tile_grid = app_state.editor_tile_grid

            if tile_grid is None:
                tile_count_x = self.tile_count_x
                tile_count_y = self.tile_count_y
            else:
                tile_count_x = tile_grid[0]
                tile_count_y = tile_grid[1]

            return Box.tile_grid_boxes(unit_box, tile_count_x, tile_count_y)
        
        elif self.mode == self.TileTargetMode.TILE_RANGE:
            boxes = []
            curr_tile_x = self.start_tile_x
            curr_tile_y = self.start_tile_y

            for __ in range(self.tile_count):
                boxes.append(unit_box.tile(curr_tile_x, curr_tile_y))

                curr_tile_x += 1
                if curr_tile_x >= self.tiles_in_row:
                    curr_tile_x = 0
                    curr_tile_y += 1

            return boxes
        
        assert False


class EngineScenePropsBase(EngineParamTarget):

    tdensity_tiers : TDensityTierIdCollection
    arrange_non_packed : bool

    def engine_init(self):
        self.init_tier_access()

    def init_tier_access(self):
        TDensityTierValue.init_tier_access(self.tdensity_tiers)


class SimilarityProps(EngineParamTarget):

    simi_mode : EngineParamUtils.ENUM_PARAM_TYPE
    threshold : float
    
    check_holes : bool
    adjust_scale : bool
    non_uniform_scaling_tolerance : float
    match_3d_axis : EngineParamUtils.ENUM_PARAM_TYPE
    match_3d_axis_space : EngineParamUtils.ENUM_PARAM_TYPE
    correct_vertices : bool
    vertex_threshold : float


class OrientTo3dProps(EngineParamTarget):

    prim_3d_axis : EngineParamUtils.ENUM_PARAM_TYPE
    prim_uv_axis : EngineParamUtils.ENUM_PARAM_TYPE
    sec_3d_axis : EngineParamUtils.ENUM_PARAM_TYPE
    sec_uv_axis : EngineParamUtils.ENUM_PARAM_TYPE
    axes_space : EngineParamUtils.ENUM_PARAM_TYPE
    prim_sec_bias : int


class MainProps(EngineParamTarget):

    numbered_groups_descriptors : NumberedGroupsDescriptorContainer
    track_groups_props : TrackGroupsProps

    pack_strategy_props : PackStrategyProps

    precision : int
    margin : float

    pixel_margin_enable : bool
    pixel_margin : int
    pixel_border_margin_enable : bool

    pixel_border_margin : int
    extra_pixel_margin_to_others : int
    pixel_margin_tex_size : int
    pixel_perfect_align : bool

    pixel_perfect_align_target : EngineParamUtils.ENUM_PARAM_TYPE
    pixel_perfect_vert_align_mode : EngineParamUtils.ENUM_PARAM_TYPE

    rotation_enable : bool
    pre_rotation_disable : bool
    flipping_enable : bool

    normalize_scale : bool
    normalize_space : EngineParamUtils.ENUM_PARAM_TYPE
    
    tdensity_set_before_pack : bool
    tdensity_to_set : TDensityTierValue
    tdensity_packing : TDensityTierValue
    island_tdensity_set_before_pack : bool
    
    island_normalize_multiplier_enable : bool
    island_normalize_multiplier : int

    scale_mode : EngineParamUtils.ENUM_PARAM_TYPE

    rotation_step : int

    island_rot_step_enable : bool

    island_rot_step : int

    non_square_packing : bool

    lock_overlapping_enable : bool

    lock_overlapping_mode : EngineParamUtils.ENUM_PARAM_TYPE

    heuristic_enable : bool
    heuristic_search_time : int
    heuristic_max_wait_time : int
    heuristic_allow_mixed_scales : bool
    advanced_heuristic : bool
    fully_inside : bool

    custom_target_box_enable : bool
    custom_target_box : Box

    tile_target_props : TileTargetProps
    
    tile_filling_method : EngineParamUtils.ENUM_PARAM_TYPE
    split_props : SplitOverlapProps

    # ------ Aligning properties ------ #

    simi_props : SimilarityProps
    
    align_priority_enable : bool
    align_priority : int

    orient_to3d_props : OrientTo3dProps

    NON_SQUARE_PACKING_NO_ACTIVE_IMAGE_ERROR_MSG = 'Non-Square Packing is enabled but no active image is selected in the UV editor'


    def engine_init(self):
        pass

    def validate_packing(self, active_mode):
        if active_mode.supports_tile_target() and not self.custom_target_box_enable:
            self.tile_target_props.validate()

        msg = self.tdensity_before_pack_validate_fail_msg()
        if msg is not None:
            raise RuntimeError(msg)

    def use_active_image(self):
        return self.non_square_packing
    
    def tex_size_not_supported_msg(self):
        if self.non_square_packing:
            return 'When Non-Square Packing is enabled, active image dimensions are used by the packer'
        
        return None
    
    def allow_mixed_scales_warning_msg(self):
        if self.fixed_scale_enabled():
            return "Islands packed with fixed scale won't be affected by this option"
        
        return None
    
    def fixed_scale_enabled(self):
        return UvpmScaleMode.fixed_scale_enabled(self.scale_mode)

    def pixel_margin_enabled(self):
        return self.pixel_margin_enable

    def pixel_border_margin_enabled(self):
        return self.pixel_border_margin_enable
    
    def set_pack_ratio(self, app_state : AppStateBase):
        if self.use_active_image():
            try:
                app_state.pack_ratio = app_state.active_image_ratio()

            except RuntimeError:
                raise RuntimeError(self.NON_SQUARE_PACKING_NO_ACTIVE_IMAGE_ERROR_MSG)
    
    def get_pixel_margin_tex_size(self, app_state : AppStateBase):
        if self.use_active_image():
            try:
                tex_size = app_state.active_image_size_safe()[1]

            except RuntimeError:
                raise RuntimeError(self.NON_SQUARE_PACKING_NO_ACTIVE_IMAGE_ERROR_MSG)
            
        else:
            tex_size = self.pixel_margin_tex_size

        return tex_size
    
    def tdensity_before_pack_validate_fail_msg(self):
        if self.tdensity_before_pack_enabled() and not self.pixel_margin_enabled():
            return "'{}' is supported only with Pixel Margin enabled".format(Labels.TEXEL_DENSITY_SET_BEFORE_PACK_NAME)
        
        return None
    
    def tdensity_before_pack_enabled(self):
        return self.tdensity_set_before_pack
    
    def get_tdensity_packing(self):
        return self.tdensity_packing if self.tdensity_before_pack_enabled() else TDensityValue.undefined()
    
    def island_tdensity_before_pack_enabled(self):
        return self.tdensity_before_pack_enabled() and self.island_tdensity_set_before_pack

    def island_rot_step_enabled(self):
        return self.rotation_enable and self.island_rot_step_enable
    
    def align_priority_enabled(self):
        return self.align_priority_enable
    
    def stack_groups_enabled(self):
        return self.numbered_groups_descriptors.stack_group.enable
    
    def norm_groups_enabled(self):
        return self.numbered_groups_descriptors.norm_group.enable
    
    def align_before_pack_enabled(self):
        return self.stack_groups_enabled()

    def heuristic_enabled(self):
        return self.heuristic_enable
    
    def heuristic_timeout_enabled(self):
        return self.heuristic_enabled() and (self.heuristic_search_time > 0 or self.heuristic_max_wait_time > 0)

    def advanced_heuristic_available(self):
        return self.heuristic_enabled()
    
    def normalize_scale_enabled(self):
        return self.normalize_scale
    
    def island_normalize_multiplier_enabled(self):
        return self.normalize_scale_enabled() and self.island_normalize_multiplier_enable
