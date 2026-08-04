
from .pack_utils import PackScenario
from .param import EngineParamTarget, EngineParamUtils
from .geom.box import Box
from .pack_utils.pack_manager import StageMetadata, DynamicTilesConfig
from .props import PackStrategyProps
from .tdensity import TDensityTierValue
from .types import TexelDensityGroupPolicy, GroupLayoutMode
from .utils import ShadowedCollectionProperty, eprint
from .uc_entry import uc


class GroupFeatures:

    PACK_TO_SINGLE_BOX = 1 << 0
    GROUPS_TOGETHER = 1 << 1


class GroupingConfigBase(EngineParamTarget):

    group_features : int


class GroupOverrides(EngineParamTarget):

    override_global_options : bool

    override_rotation_enable : bool
    rotation_enable : bool

    override_pre_rotation_disable : bool
    pre_rotation_disable : bool

    override_rotation_step : bool
    rotation_step : int
    
    override_scale_mode : bool
    scale_mode : int

    override_pixel_margin : bool
    pixel_margin : int

    override_pixel_border_margin : bool
    pixel_border_margin : int

    override_extra_pixel_margin_to_others : bool
    extra_pixel_margin_to_others : int

    override_pixel_margin_tex_size : bool
    pixel_margin_tex_size : int

    override_tdensity_packing : bool
    tdensity_packing : TDensityTierValue
    
    override_groups_together : bool
    groups_together : bool
    
    override_grouping_compactness : bool
    grouping_compactness : float
    
    override_pack_to_single_box : bool
    pack_to_single_box : bool
    
    override_pack_strategy : bool
    pack_strategy : PackStrategyProps



GROUP_COUNTER = 0

class GroupInfo(EngineParamTarget):

    name : str
    num : int
    color : tuple[float, float, float]
    target_boxes : ShadowedCollectionProperty[Box]

    tdensity_cluster : int

    tile_count : int
    dynamic_tiles : bool
    overrides : GroupOverrides

    islands = None
    target = None
    state_params = None
    dt_config = None


    def init(self, g_scheme):
        self.g_scheme = g_scheme

        global GROUP_COUNTER
        self.create_id = GROUP_COUNTER
        GROUP_COUNTER += 1

    def init_stage(self):       
        self.stage_params = self.g_scheme.scenario.create_stage_params()
        self.tdensity_packing = self.g_scheme.scenario.main_props.get_tdensity_packing()
        self.overrides.tdensity_packing.set_error_suffix("group '{}' overrides".format(self.name))

        if self.g_scheme.group_features & GroupFeatures.PACK_TO_SINGLE_BOX:
            self.stage_params.pack_to_single_box = self.g_scheme.options.base.pack_to_single_box

        if self.g_scheme.group_features & GroupFeatures.GROUPS_TOGETHER:
            self.stage_params.groups_together = self.g_scheme.options.base.groups_together
            self.stage_params.grouping_compactness = self.g_scheme.options.base.grouping_compactness

        if self.overrides.override_global_options:
            if self.overrides.override_tdensity_packing:
                self.tdensity_packing = self.overrides.tdensity_packing

            def process_attr(attr_type, attr_name, attr_convert=None, overridden_func=None):
                if attr_convert is None:
                    attr_convert = lambda v: attr_type(v)
                
                attr_val = None

                if getattr(self.overrides, 'override_' + attr_name):
                    attr_val = getattr(self.overrides, attr_name)
                
                if attr_val is not None:
                    if overridden_func:
                        overridden_func()
                    setattr(self.stage_params, attr_name, attr_convert(attr_val))

            def enable_pixel_border_margin():
                self.stage_params.pixel_border_margin_enable = True

            process_attr(bool, 'rotation_enable')
            process_attr(bool, 'pre_rotation_disable')
            process_attr(int, 'rotation_step')
            process_attr(uc.ScaleMode, 'scale_mode')
            process_attr(int, 'pixel_margin')
            process_attr(int, 'pixel_border_margin', overridden_func=enable_pixel_border_margin)
            process_attr(int, 'extra_pixel_margin_to_others')
            process_attr(int, 'pixel_margin_tex_size')

            if self.g_scheme.group_features & GroupFeatures.GROUPS_TOGETHER:
                process_attr(bool, 'groups_together')
                process_attr(bool, 'grouping_compactness')

            if self.g_scheme.group_features & GroupFeatures.PACK_TO_SINGLE_BOX:
                process_attr(bool, 'pack_to_single_box')
        
            process_attr(uc.PackStrategyParams, 'pack_strategy', attr_convert=lambda p: p.to_uc_params())

    def init_target(self):
        self.target = Box.boxes_to_target(self.target_boxes)

        if len(self.target) == 0:
            raise uc.InputError("Group with no target box encountered. Group name: {}".format(self.name))
        
    def island_overlaps_op_target(self, island):
        return island.overlaps(Box.boxes_to_target(self.target_boxes))

    @property
    def scale_mode(self):
        return self.stage_params.scale_mode
    
    def to_stage(self):
        stage = uc.Stage()
        stage.params = self.stage_params
        stage.target = self.target
        stage.input_islands = [self.islands]
        stage.static_islands = self.g_scheme.scenario.static_islands
        stage.tdensity_cluster_id = self.tdensity_cluster
        stage.metadata = StageMetadata(name=self.name, color=self.color)
        return stage
    
    def is_packed_with_fixed_scale(self):
        return uc.fixed_scale_enabled(self.scale_mode)
    

class GroupingOptionsBase(EngineParamTarget):

    tiles_in_row : int
    tile_count_x : int
    tile_count_y : int
    atlas_size_x : int
    atlas_size_y : int
    last_group_complementary : bool
    groups_together : bool
    grouping_compactness : bool
    pack_to_single_box : bool
    dynamic_tiles_all : bool


class GroupingOptions(EngineParamTarget):

    base : GroupingOptionsBase

    tile_count_per_group : int
    tdensity_policy : EngineParamUtils.ENUM_PARAM_TYPE
    group_layout_mode : EngineParamUtils.ENUM_PARAM_TYPE

    
class GroupingScheme(EngineParamTarget):

    iparam_name : str
    groups : list[GroupInfo]
    options : GroupingOptions


    def init(self, scenario):
        self.scenario = scenario
        self.group_features = self.scenario.grouping_config.group_features

        group_iparam_desc = self.scenario.int_iparams_manager.iparam_desc(self.iparam_name)
        if group_iparam_desc is None:
            raise uc.InputError('Invalid island parameter passed in the grouping scheme')
        self.group_iparam_desc = group_iparam_desc

        self.group_by_num = dict()
        for group in self.groups:
            group.init(self)

            if self.group_by_num.get(group.num) is not None:
                raise uc.InputError('Duplicated group numbers in the grouping scheme')
            
            self.group_by_num[group.num] = group

    def init_stages(self):
        for group in self.groups:
            group.init_stage()

    def validate_locking(self):
        for group in self.groups:
            if group.islands is None:
                continue

            for island in group.islands:
                if island.parent_count < 2:
                    continue

                parents = island.parents
                parent_groups = set()
                for parent in parents:
                    parent_groups.add(parent.get_iparam(self.group_iparam_desc))

                    if len(parent_groups) > 1:
                        uc.packer.send_log(uc.LogType.WARNING, 'Islands from two different groups were locked together!')
                        uc.packer.send_log(uc.LogType.WARNING, 'In result some islands will be processed as not belonging to the groups they were originally assigned to')
                        return

    def __get_group_by_num(self, g_num):
            group = self.group_by_num.get(g_num)
            if group is None:
                raise uc.InputError('Island assigned to an invalid group')
            
            return group
    
    def island_overlaps_op_target(self, island):
        for group in self.groups:
            if self.dynamic_tiles_enabled(group):
                continue

            if group.island_overlaps_op_target(island):
                return True
            
        return False
    
    def supports_tile_count_prop(self, group):
        return GroupLayoutMode.supports_tile_count(self.options.group_layout_mode) and not self.dynamic_tiles_enabled(group) and not self.is_complementary_group(group)
    
    def supports_dynamic_tiles_prop(self, group : GroupInfo):
        if self.options.base.dynamic_tiles_all:
            return False
        
        if self.is_complementary_group(group):
            return False
            
        return True
    
    def dynamic_tiles_enabled(self, group : GroupInfo):
        return self.options.base.dynamic_tiles_all or (group.dynamic_tiles if self.supports_dynamic_tiles_prop(group) else False)
    
    def apply_tdensity_policy(self):
        if self.options.tdensity_policy == TexelDensityGroupPolicy.CUSTOM:
            return

        def _group_and_intersect_groups(lookup_group, lookup_groups_to_process):
            if lookup_group in lookup_groups_to_process:
                yield lookup_group
                lookup_groups_to_process.remove(lookup_group)
                intersect_groups = []
                for group_to_process in lookup_groups_to_process:
                    if any(b.intersects(p_b) for b in group_to_process.target_boxes for p_b in lookup_group.target_boxes):
                        intersect_groups.extend(_group_and_intersect_groups(group_to_process, lookup_groups_to_process[:]))
                for intersect_group in intersect_groups:
                    yield intersect_group
                    if intersect_group in lookup_groups_to_process:
                        lookup_groups_to_process.remove(intersect_group)

        groups_to_process = self.groups[:]
        for g_num, group in self.group_by_num.items():
            if self.options.tdensity_policy == TexelDensityGroupPolicy.INDEPENDENT:
                group.tdensity_cluster = g_num

            elif self.options.tdensity_policy == TexelDensityGroupPolicy.UNIFORM:
                group.tdensity_cluster = 0

            elif self.options.tdensity_policy == TexelDensityGroupPolicy.AUTOMATIC:
                for g in _group_and_intersect_groups(group, groups_to_process):
                    g.tdensity_cluster = g_num
            else:
                assert(False)

    def complementary_group_enabled(self):
        return self.options.base.last_group_complementary
    
    def complementary_group(self):
        assert(self.complementary_group_enabled())
        assert(len(self.groups) > 0)
        return self.groups[len(self.groups)-1]
    
    def is_complementary_group(self, group):
        return self.complementary_group_enabled() and group == self.complementary_group()
    
    def groups_with_islands(self):
        return [group for group in self.groups if group.islands]
    
    def groups_with_islands_dynamic(self):
        return [group for group in self.groups if group.islands and self.dynamic_tiles_enabled(group)]
    
    def groups_with_islands_no_dynamic(self):
        return [group for group in self.groups if group.islands and not self.dynamic_tiles_enabled(group)]

    def target_box_editing(self):
        return self.options.group_layout_mode == GroupLayoutMode.MANUAL
    
    def apply_group_layout_tile_grid(self):
        unit_box = Box.unit_box()
        tile_grid_boxes = Box.tile_grid_boxes(unit_box, self.options.base.tile_count_x, self.options.base.tile_count_y)

        for group in self.groups_with_islands_no_dynamic():
            group.target_boxes.clear()

            for box in tile_grid_boxes:
                new_box = group.target_boxes.add()
                new_box.copy_from(box)

    def apply_group_layout_tile_count(self):
        unit_box = Box.unit_box()
        dt_start_tile = False
        dt_tile_step = None

        if self.options.group_layout_mode == GroupLayoutMode.AUTOMATIC:
            def box_func2(group_idx, box_idx, global_box_idx):
                return unit_box.tile_from_number(global_box_idx, self.options.base.tiles_in_row)
            
        elif self.options.group_layout_mode == GroupLayoutMode.AUTOMATIC_HORI:
            dt_start_tile = True
            dt_tile_step = (1, 0)
            def box_func2(group_idx, box_idx, global_box_idx):
                return unit_box.tile(box_idx, group_idx)
            
        elif self.options.group_layout_mode == GroupLayoutMode.AUTOMATIC_VERT:
            dt_start_tile = True
            dt_tile_step = (0, 1)
            def box_func2(group_idx, box_idx, global_box_idx):
                return unit_box.tile(group_idx, box_idx)
            
        elif self.options.group_layout_mode == GroupLayoutMode.TEXTURE_ATLAS:
            atlas_size_x = self.options.base.atlas_size_x
            atlas_size_y = self.options.base.atlas_size_y
            box_count_per_tile = atlas_size_x * atlas_size_y

            def box_func2(group_idx, box_idx, global_box_idx):
                tile_idx = int(global_box_idx / box_count_per_tile)
                box_in_tile_idx = global_box_idx % box_count_per_tile
                tile = unit_box.tile_from_number(tile_idx, self.options.base.tiles_in_row)

                box_coord_x = box_in_tile_idx % atlas_size_x
                box_coord_y = int(box_in_tile_idx / atlas_size_x)

                tile_min_corner = tile.min_corner

                base_box = Box(
                    p1_x = tile_min_corner.x,
                    p1_y = tile_min_corner.y,
                    p2_x = tile_min_corner.x + tile.width / atlas_size_x,
                    p2_y = tile_min_corner.y + tile.height / atlas_size_y
                )

                return base_box.tile(box_coord_x, box_coord_y)
            
        else:
            assert False           

        global_box_idx = 0
        def box_func(group_idx, box_idx):
            nonlocal global_box_idx
            box = box_func2(group_idx, box_idx, global_box_idx)
            global_box_idx += 1
            return box

        for group_idx, group in enumerate(self.groups_with_islands()):
            if self.dynamic_tiles_enabled(group):
                group.dt_config = DynamicTilesConfig(
                    tiles_in_row=self.options.base.tiles_in_row,
                    start_tile=box_func(group_idx, 0).tile_coords() if dt_start_tile else None,
                    tile_step=dt_tile_step if dt_start_tile else None
                )

            else:
                group.target_boxes.clear()

                for box_idx in range(group.tile_count):
                    new_box = group.target_boxes.add()
                    new_box.copy_from(box_func(group_idx, box_idx))

    def apply_group_layout(self):
        if self.options.tile_count_per_group > 0:
            for group in self.groups:
                group.tile_count = self.options.tile_count_per_group

        if self.target_box_editing():
            for group in self.groups_with_islands_dynamic():
                group.dt_config = DynamicTilesConfig(tiles_in_row=self.options.base.tiles_in_row)

        else:
            if self.options.group_layout_mode == GroupLayoutMode.TILE_GRID:
                self.apply_group_layout_tile_grid()
            elif GroupLayoutMode.supports_tile_count(self.options.group_layout_mode):
                self.apply_group_layout_tile_count()
            else:
                assert False

        if self.complementary_group_enabled():
            comp_group = self.complementary_group()
            comp_group.target_boxes.clear()

            for group in self.groups_with_islands_no_dynamic():
                if self.is_complementary_group(group):
                    continue

                for box in group.target_boxes:
                    new_box = comp_group.target_boxes.add()
                    new_box.copy_from(box)

            if len(comp_group.target_boxes) == 0:
                raise uc.InputError('No suitable other group to process complementary group')

        for group in self.groups:
            group.init_target()
    
    def assign_islands_to_groups(self, islands):
        islands_by_groups = islands.split_by_iparam(self.group_iparam_desc)

        for g_num, g_islands in islands_by_groups.items():
            group = self.__get_group_by_num(g_num)
            group.islands = g_islands

    def is_packed_with_fixed_scale(self, island):
        g_num = island.get_iparam(self.group_iparam_desc)
        group = self.__get_group_by_num(g_num)

        return group.is_packed_with_fixed_scale()
    
    def get_tdensity_packing(self, island):
        g_num = island.get_iparam(self.group_iparam_desc)
        group = self.__get_group_by_num(g_num)

        return group.tdensity_packing
    
    def island_pixel_margin_tex_size(self, island):
        g_num = island.get_iparam(self.group_iparam_desc)
        group = self.__get_group_by_num(g_num)

        return group.stage_params.pixel_margin_tex_size
                    

class GSchemePackScenario(PackScenario):

    grouping_config : GroupingConfigBase
    g_scheme : GroupingScheme

    def init(self):
        self.g_scheme.init(self)
        self.g_scheme.init_stages()

        super().init()
        self.g_scheme.assign_islands_to_groups(self.islands_to_pack)
        self.g_scheme.apply_group_layout()
        self.g_scheme.apply_tdensity_policy()

        if self.locking_enabled:
            self.g_scheme.validate_locking()


class GSchemeDistinctStagesPackScenario(GSchemePackScenario):

    def is_packed_with_fixed_scale(self, island):
        return self.g_scheme.is_packed_with_fixed_scale(island)
    
    def get_tdensity_packing(self, island):
        return self.g_scheme.get_tdensity_packing(island)
    
    def island_pixel_margin_tex_size(self, island):
        return self.g_scheme.island_pixel_margin_tex_size(island)
