
from ..pipeline import GenericScenario
from ..utils import flag_islands, eprint, area_to_string, split_islands
from ..geom import IslandWrapper, array_bbox
from ..props import MainProps, AppStateBase, EngineScenePropsBase
from ..tdensity import TDensityTierValue
from ..param import EngineParamUtils
from ..types import PackOpType, UvpmPixelPerfectVertAlignMode, UvpmOverlapDetectionMode, UvpmSimilarityMode, UvpmScaleMode
from ..island_params import NormalizeMultiplierIParamInfo, TexelDensityPackingIParamInfo
from .pack_manager import PackManager
from ..scenario.align_align_similar import Scenario as AlignScenario
from ..geom import PACK_RATIO
from ..uc_entry import uc


OVERLAPPING_WARNING_MSG_ARRAY = [
    "Overlapping islands were detected after packing (check the selected islands).",
    "Consider increasing the 'Precision' parameter."
]

OUTSIDE_TARGET_BOX_WARNING_MSG = "Some islands are outside their target boxes after packing (check the selected islands)."
NO_SIUTABLE_DEVICE_STATUS_MSG = "No suitable packing device."

NO_SIUTABLE_DEVICE_ERROR_MSG_ARRAY = [
    "No suitable packing device to perform the operation.",
    "Make sure that you have at least one packing device enabled in Preferences."
]

CORRECT_VERTICES_WARNING_MSG_ARRAY = [
    "Similarity option Correct Vertices is ignored when packing with stack groups.",
    "Read stack groups documentation for more info."
]


def merge_overlapping_islands(input_islands, overlapping_mode, iparam_desc):
    if overlapping_mode == UvpmOverlapDetectionMode.DISABLED and iparam_desc is None:
        return input_islands

    overlapping_groups, not_overlapping_islands = input_islands.split_by_overlapping(uc.OverlapDetectionMode(overlapping_mode), iparam_desc)
    output_islands = uc.IslandSet()

    for group in overlapping_groups:
        output_islands.append(group.merge())

    output_islands += not_overlapping_islands
    return output_islands


class Tracker:

    def __init__(self, raw_tracker):
        self.tracker_island = raw_tracker[0]
        self.transform = raw_tracker[1]
        self.transform_inverse = raw_tracker[2]


class PackScenario(GenericScenario):

    MAX_ISLAND_DIM_ALLOWED = 4.0

    PIXEL_PERFECT_ALIGN_TIP = 'there are certain restrictions of the Pixel Perfect Alignment option - press the help button next to the option to learn more'

    TEXEL_DENSITY_WARNING_SENT = False
    TEXEL_DENSITY_WARNING = "Islands with zero UV or 3D area have been encountered. Texel density cannot be set for such islands"

    app_state : AppStateBase # Must be declared as first
    e_scene_props : EngineScenePropsBase # Must be declared before main_props
    main_props : MainProps
    pack_op_type : EngineParamUtils.ENUM_PARAM_TYPE
    pinned_as_others : bool

    op_target = None
    tdensity_packing_iparam_desc = None
    fixed_scale_iparam_desc = None
    align_scenario = None
    tracker_data = None

    def __init__(self, cx):
        super().__init__(cx)

        if self.main_props.tdensity_before_pack_enabled():
            self.fixed_scale_iparam_desc = self.int_iparams_manager.register_iparam(
                    'fixed_scale',
                    'Fixed Scale',
                    0,
                    1,
                    0
                )

            if self.main_props.island_tdensity_before_pack_enabled():
                self.tdensity_packing_iparam_desc = self.str_iparams_manager.iparam_desc(TexelDensityPackingIParamInfo.SCRIPT_NAME)

        self.op_target = Box.boxes_to_target(self._get_target_boxes())

        if self.main_props.align_before_pack_enabled():
            self.align_scenario = AlignScenario(
                self.cx,
                app_state=self.app_state,
                e_scene_props=self.e_scene_props,
                main_props=self.main_props)


    def _get_target_boxes(self):
        box = self.main_props.custom_target_box if self.main_props.custom_target_box_enable else Box.unit_box()
        return [box]


    def create_pack_params(self):
        pack_params = uc.PackParams()
        pack_params.precision = self.main_props.precision
        pack_params.margin = self.main_props.margin

        if self.main_props.island_rot_step_enabled():
            from ..island_params import RotStepIParamInfo
            pack_params.rotation_step_iparam_desc = self.int_iparams_manager.iparam_desc(RotStepIParamInfo.SCRIPT_NAME)

        pack_params.fixed_scale_iparam_desc = self.fixed_scale_iparam_desc
        return pack_params
    
    def create_stage_params(self):
        stage_params = uc.StageParams()

        stage_params.scale_mode = uc.ScaleMode(self.main_props.scale_mode)
        stage_params.rotation_enable = self.main_props.rotation_enable
        stage_params.pre_rotation_disable = self.main_props.pre_rotation_disable
        stage_params.rotation_step = self.main_props.rotation_step
        stage_params.flipping_enable = self.main_props.flipping_enable

        if self.main_props.pixel_margin_enabled():
            stage_params.pixel_margin = self.main_props.pixel_margin
            stage_params.extra_pixel_margin_to_others = self.main_props.extra_pixel_margin_to_others
            stage_params.pixel_border_margin_enable = self.main_props.pixel_border_margin_enable
            stage_params.pixel_border_margin = self.main_props.pixel_border_margin
            stage_params.pixel_margin_tex_size = self.main_props.pixel_margin_tex_size
            stage_params.pixel_perfect_align = self.main_props.pixel_perfect_align
            stage_params.pixel_perfect_align_target = uc.PixelPerfectAlignTarget(self.main_props.pixel_perfect_align_target)

        stage_params.groups_together = False
        stage_params.grouping_compactness = 0.0
        stage_params.pack_to_single_box = False

        stage_params.pack_strategy = self.main_props.pack_strategy_props.to_uc_params()
        stage_params.tile_filling_method = uc.TileFillingMethod(self.main_props.tile_filling_method)

        return stage_params

    def island_overlaps_op_target(self, island):
        return island.overlaps(self.op_target)

    def process_driver_island(self, island, combined_transform, transformed_tracker_islands):
        island_transform = island.transform()
        combined_transform_local = combined_transform * island_transform

        for driver_island in island.parents:
            self.process_driver_island(driver_island, combined_transform_local, transformed_tracker_islands)
            driver_trackers = self.tracker_data.get(driver_island)

            if driver_trackers is None:
                continue

            for tracker in driver_trackers:
                tracker_transform = tracker.transform_inverse * combined_transform_local * tracker.transform
                transformed_tracker_islands.append(uc.Island(tracker.tracker_island, tracker_transform))

    def send_out_islands(self, island_set_list, **kwargs):
        if self.tracker_data is not None:
            transformed_tracker_islands = uc.IslandSet()

            for islands in island_set_list:
                if islands is None:
                    continue

                for island in islands:
                    self.process_driver_island(island, uc.Matrix3x3.identity(), transformed_tracker_islands)

            island_set_list.append(transformed_tracker_islands)

        transform_kw = 'send_transform'
        if (self.pixel_perfect_vert_align_mode != UvpmPixelPerfectVertAlignMode.NONE) and (transform_kw in kwargs) and kwargs[transform_kw]:
            pixel_perfect_aligned = False
            aligned_set = uc.IslandSet()

            for islands in island_set_list:
                if islands is None:
                    continue

                for island in islands:
                    pack_data = island.pack_data
                    stage_params = pack_data.stage_params

                    if not stage_params.pixel_perfect_align_enabled:
                        continue

                    unmerged = island.unmerge()
                    for unmerged_island in unmerged:
                        aligned_set.append(
                            unmerged_island.pixel_perfect_vert_align(
                                pack_data.target_box,
                                stage_params.pixel_margin_tex_size,
                                uc.PixelPerfectVertAlignMode(self.pixel_perfect_vert_align_mode),
                                uc.PixelPerfectAlignTarget(self.pixel_perfect_align_target)))

                    pixel_perfect_aligned = True

            if pixel_perfect_aligned:
                del kwargs[transform_kw]
                transform_kw = 'send_vertices'
                kwargs[transform_kw] = True

                island_set_list = [aligned_set]

        if PACK_RATIO.get() != 1.0 and (transform_kw in kwargs) and kwargs[transform_kw]:
            tmp_list = []

            for islands in island_set_list:
                if islands is None:
                    continue
                tmp_list.append(PACK_RATIO.unapply_from_islands(islands))

            island_set_list = tmp_list

        uc.packer.send_out_islands(island_set_list, **kwargs)

    def get_tdensity_packing(self, island) -> TDensityTierValue:
        return self.main_props.get_tdensity_packing()
    
    def island_pixel_margin_tex_size(self, island):
        return self.main_props.get_pixel_margin_tex_size(self.app_state)

    def is_packed_with_fixed_scale(self, island):
        return UvpmScaleMode.fixed_scale_enabled(self.main_props.scale_mode)
    
    def check_is_packed_with_fixed_scale(self, island):
        if (self.fixed_scale_iparam_desc is not None) and (island.get_iparam(self.fixed_scale_iparam_desc) > 0):
            return True

        return self.is_packed_with_fixed_scale(island)

    def split_islands_by_fixed_scale(self, islands):
        fixed_islands = uc.IslandSet()
        non_fixed_islands = uc.IslandSet()

        for island in islands:
            (fixed_islands if self.check_is_packed_with_fixed_scale(island) else non_fixed_islands).append(island)

        return fixed_islands, non_fixed_islands
    
    def apply_max_dimension_limit(self, islands):
        max_dim = islands.max_island_dimension(False)

        if max_dim <= self.MAX_ISLAND_DIM_ALLOWED:
            return islands

        fixed_islands, non_fixed_islands = self.split_islands_by_fixed_scale(islands)
        max_dim = non_fixed_islands.max_island_dimension(False)

        if max_dim <= self.MAX_ISLAND_DIM_ALLOWED:
            return islands
        
        scale_factor = self.MAX_ISLAND_DIM_ALLOWED / max_dim
        non_fixed_islands = non_fixed_islands.scale(scale_factor, scale_factor)

        fixed_islands += non_fixed_islands
        return fixed_islands
    
    def normalize_scale(self, islands):
        norm_multiplier_iparam_desc = self.int_iparams_manager.iparam_desc(NormalizeMultiplierIParamInfo.SCRIPT_NAME) if self.main_props.island_normalize_multiplier_enabled() else None

        fixed_islands, non_fixed_islands = self.split_islands_by_fixed_scale(islands)

        if len(non_fixed_islands) == 0:
            return fixed_islands
        
        output = fixed_islands
        norm_space = uc.CoordSpace(self.main_props.normalize_space)

        if not self.main_props.norm_groups_enabled():
            output += non_fixed_islands.normalize(norm_space, norm_multiplier_iparam_desc)

        else:
            norm_group_iparam_desc = self.int_iparams_manager.iparam_desc(self.main_props.numbered_groups_descriptors.norm_group.iparam_name)
            norm_groups = non_fixed_islands.split_by_iparam(norm_group_iparam_desc)

            for g_num, group in norm_groups.items():
                if g_num == norm_group_iparam_desc.default_value:
                    output += group

                else:
                    output += group.normalize(norm_space, norm_multiplier_iparam_desc)

        return output
    
    def island_set_texel_density(self, island):
        tdensity_value = self.get_tdensity_packing(island)
        tex_size = self.island_pixel_margin_tex_size(island)

        if self.tdensity_packing_iparam_desc:
            island_tdensity_value = TDensityTierValue.from_s(island.get_iparam(self.tdensity_packing_iparam_desc))

            if island_tdensity_value.is_defined():
                tdensity_value = island_tdensity_value

        assert tex_size > 0

        if not tdensity_value.is_defined():
            return island
        
        island_w = IslandWrapper(island, scale_length=self.app_state.scale_length)

        try:
            if tdensity_value.is_defined():
                island.set_iparam(self.fixed_scale_iparam_desc, 1)

            return island_w.set_tdensity(tex_size, tdensity_value).get()
        
        except ValueError:
            pass

        if not self.TEXEL_DENSITY_WARNING_SENT:
            self.TEXEL_DENSITY_WARNING_SENT = True
            uc.packer.send_log(uc.LogType.WARNING, self.TEXEL_DENSITY_WARNING)

        return island

    def set_texel_density(self, islands):
        output = uc.IslandSet()

        for island in islands:
            output.append(self.island_set_texel_density(island))

        return output

    def init(self):
        super().init()

        if self.align_scenario:
            self.align_scenario.init()

        if self.main_props.pixel_perfect_align:
            self.pixel_perfect_align_target = self.main_props.pixel_perfect_align_target
            self.pixel_perfect_vert_align_mode = self.main_props.pixel_perfect_vert_align_mode
            self.send_tip(self.PIXEL_PERFECT_ALIGN_TIP)
        else:
            self.pixel_perfect_vert_align_mode = UvpmPixelPerfectVertAlignMode.NONE

        self.pack_params = self.create_pack_params()

        selected_islands = PACK_RATIO.apply_to_islands(self.cx.selected_islands)
        unselected_islands = PACK_RATIO.apply_to_islands(self.cx.unselected_islands)
        pinned_islands = PACK_RATIO.apply_to_islands(self.cx.pinned_islands)

        normalize_scale = self.main_props.normalize_scale

        if self.pack_op_type == PackOpType.REPACK_WITH_OTHERS:
            if not normalize_scale:
                self.send_tip("consider enabling 'Normalize Scale' in order to keep the scale of selected and unselected islands consistent during repacking")

            overlapping, not_overlapping = split_islands(unselected_islands, lambda i: self.island_overlaps_op_target(i))

            selected_islands += overlapping
            unselected_islands = not_overlapping

        self.pack_runconfig = uc.PackRunConfig()
        self.pack_runconfig.asyn = True
        self.pack_runconfig.realtime_solution = True

        if self.main_props.heuristic_enabled():
            self.pack_runconfig.heuristic_search_time = self.main_props.heuristic_search_time
            self.pack_runconfig.advanced_heuristic = self.main_props.advanced_heuristic
            self.pack_runconfig.heuristic_max_wait_time = self.main_props.heuristic_max_wait_time
            self.pack_runconfig.heuristic_allow_mixed_scales = self.main_props.heuristic_allow_mixed_scales

        self.islands_to_pack = selected_islands

        lock_group_desc = self.main_props.numbered_groups_descriptors.lock_group
        ### Lock params
        lock_group_iparam_desc = None
        if lock_group_desc.iparam_name:
            lock_group_iparam_desc = self.int_iparams_manager.iparam_desc(lock_group_desc.iparam_name)

        lock_overlapping_mode = self.main_props.lock_overlapping_mode if self.main_props.lock_overlapping_enable else UvpmOverlapDetectionMode.DISABLED
        self.locking_enabled = (lock_overlapping_mode != UvpmOverlapDetectionMode.DISABLED) or (lock_group_iparam_desc is not None)

        ### Track Groups
        track_group_iparam_desc = None
        track_group_desc = self.main_props.numbered_groups_descriptors.track_group

        if track_group_desc.iparam_name:
            uc.packer.send_log(uc.LogType.STATUS, "Determining island trackers...")
            track_groups_props = self.main_props.track_groups_props
            matching_mode = track_groups_props.matching_mode

            track_group_iparam_desc = self.int_iparams_manager.iparam_desc(track_group_desc.iparam_name)
            tracker_islands = uc.IslandSet()
            unselected_islands_tmp = uc.IslandSet()

            for island in unselected_islands:
                target_list = unselected_islands_tmp if island.get_iparam(track_group_iparam_desc) == track_group_iparam_desc.default_value else tracker_islands
                target_list.append(island)

            unselected_islands = unselected_islands_tmp

            if self.locking_enabled:
                pre_lock_tracker_count = len(tracker_islands)
                tracker_islands = merge_overlapping_islands(tracker_islands, lock_overlapping_mode, lock_group_iparam_desc)

                if (pre_lock_tracker_count != len(tracker_islands)) and (matching_mode != UvpmSimilarityMode.BORDER_SHAPE):
                    raise uc.InputError("Locking tracker islands is only supported when 'Matching Mode' is set to 'Border Shape'")

            self.tracker_data = dict()
            track_simi_params = uc.SimilarityParams()

            track_simi_params.mode = uc.SimilarityMode(matching_mode)
            track_simi_params.threshold = 0.55
            track_simi_params.precision = 5000
            track_simi_params.check_holes = True
            track_simi_params.vertex_threshold = 0.005

            self.send_vertex_based_tip(matching_mode, suffix='for track groups')

            driver_groups = self.islands_to_pack.split_by_iparam(track_group_iparam_desc)
            tracker_groups = tracker_islands.split_by_iparam(track_group_iparam_desc)
            non_tracker_total = uc.IslandSet()

            if track_groups_props.require_match_for_all:
                non_matched_total = uc.IslandSet()

            for g_num, driver_group in driver_groups.items():
                if g_num == track_group_iparam_desc.default_value:
                    continue
                
                tracker_group = tracker_groups.get(g_num)
                if tracker_group is None:
                    if track_groups_props.require_match_for_all:
                        non_matched_total += driver_group

                    continue

                del tracker_groups[g_num]

                trackers, non_tracker, non_matched = driver_group.find_trackers(track_simi_params, tracker_group)
                non_tracker_total += non_tracker

                if track_groups_props.require_match_for_all:
                    non_matched_total += non_matched

                for driver_island, raw_trackers in trackers.items():
                    self.tracker_data[driver_island] = [Tracker(raw_tracker) for raw_tracker in raw_trackers]

            for g_num, group in tracker_groups.items():
                if g_num == track_group_iparam_desc.default_value:
                    continue

                non_tracker_total += group

            if track_groups_props.require_match_for_all and len(non_matched_total) > 0:
                flag_islands(self.cx.input_islands, non_matched_total)
                uc.packer.send_log(uc.LogType.ERROR, "Could not find tracker islands for some driver islands (driver islands with no match were selected). Aborting")
                uc.packer.send_log(uc.LogType.ERROR, "You can ignore this error by disabling the 'Require Match For All' option (though it is not recommended)")
                raise uc.InputError()

            if len(non_tracker_total) > 0:
                flag_islands(self.cx.input_islands, non_tracker_total)
                uc.packer.send_log(uc.LogType.ERROR, "Could not find driver islands for some tracker islands (tracker islands with no match were selected). Aborting")
                uc.packer.send_log(uc.LogType.ERROR, "You can ignore this error by hiding the tracker islands with no match before packing")
                raise uc.InputError()

        if PackOpType.static_islands_enable(self.pack_op_type):
            self.static_islands = unselected_islands.clone()

            if self.pinned_as_others:
                self.static_islands += pinned_islands

        else:
            self.static_islands = None

        ### Lock and stack groups
        if self.align_scenario and self.align_scenario.stack_group_iparam_desc:
            uc.packer.send_log(uc.LogType.STATUS, "Stack groups aligning...")

            if self.align_scenario.is_vertex_based() and self.align_scenario.simi_params.correct_vertices:
                for msg in CORRECT_VERTICES_WARNING_MSG_ARRAY:
                    uc.packer.send_log(uc.LogType.WARNING, msg)

                self.align_scenario.simi_params.correct_vertices = False

            (aligned_groups, non_aligned_islands) = self.align_scenario.align_similar_by_stack_group(self.islands_to_pack)

            AUX_LOCK_IPARAM_NAME = '__aux_lock_group'
            AUX_LOCK_IPARAM_LABEL = 'Aux Lock Group'
            AUX_LOCK_IPARAM_MIN_VALUE = self.align_scenario.stack_group_iparam_desc.min_value
            AUX_LOCK_IPARAM_MAX_VALUE = 1000
            AUX_LOCK_IPARAM_DEF_VALUE = self.align_scenario.stack_group_iparam_desc.default_value

            assert(AUX_LOCK_IPARAM_MAX_VALUE >= self.align_scenario.stack_group_iparam_desc.max_value)

            aux_lock_group_iparam_desc = self.int_iparams_manager.register_iparam(
                AUX_LOCK_IPARAM_NAME,
                AUX_LOCK_IPARAM_LABEL,
                AUX_LOCK_IPARAM_MIN_VALUE,
                AUX_LOCK_IPARAM_MAX_VALUE,
                AUX_LOCK_IPARAM_DEF_VALUE
            )

            lock_groups = None
            if lock_group_iparam_desc:
                assert(aux_lock_group_iparam_desc.min_value == lock_group_iparam_desc.min_value)
                assert(aux_lock_group_iparam_desc.default_value == lock_group_iparam_desc.default_value)
                assert(aux_lock_group_iparam_desc.max_value >= lock_group_iparam_desc.max_value)

                lock_groups = self.islands_to_pack.split_by_iparam(lock_group_iparam_desc)

            curr_lock_val = aux_lock_group_iparam_desc.max_value

            for group in aligned_groups:

                while lock_groups and (curr_lock_val in lock_groups):
                    curr_lock_val -= 1
                    
                if curr_lock_val <= aux_lock_group_iparam_desc.default_value:
                        raise RuntimeError('Not enough lock groups')

                group.set_iparam(aux_lock_group_iparam_desc, curr_lock_val)
                curr_lock_val -= 1

            if lock_group_iparam_desc:
                non_aligned_islands.copy_iparam(aux_lock_group_iparam_desc, lock_group_iparam_desc)

            self.islands_to_pack = non_aligned_islands
            for group in aligned_groups:
                self.islands_to_pack += group

            lock_group_iparam_desc = aux_lock_group_iparam_desc
            self.locking_enabled = True

        if self.locking_enabled:
            self.islands_to_pack = merge_overlapping_islands(self.islands_to_pack, lock_overlapping_mode, lock_group_iparam_desc)

        if self.main_props.tdensity_before_pack_enabled():
            self.islands_to_pack = self.set_texel_density(self.islands_to_pack)

        self.islands_to_pack = self.apply_max_dimension_limit(self.islands_to_pack)

        if normalize_scale:
            self.islands_to_pack = self.normalize_scale(self.islands_to_pack)

        self.pack_manager = PackManager(self, self.pack_runconfig)

    def pre_run(self):
        self.init_tasks()

    def run(self):
        return self.pack_manager.pack()

    def post_run_island_sets(self):
        return [self.pack_manager.packed_islands], self.pack_manager.invalid_islands

    def arrange_non_packed_islands(self):
        HANDLE_MARGIN = 0.05
        target_boxes = self.pack_manager.get_target_boxes()

        if len(target_boxes) > 0:
            t_bbox = array_bbox(target_boxes)
            x_coord_min = t_bbox.min_corner.x
            y_coord_min = t_bbox.max_corner.y

        else:
            x_coord_min = 0.0
            y_coord_min = 0.0

        non_packed_islands = [i for i in self.pack_manager.non_packed_islands]
        non_packed_islands.sort(key=lambda i: -i.bbox().area())

        handled_islands = uc.IslandSet()
        y_coord = y_coord_min + HANDLE_MARGIN
        x_coord = x_coord_min

        x_coord_max = x_coord_min + 5
        max_height = 0.0

        for island in non_packed_islands:
            i_bbox = island.bbox()
            max_height = max(max_height, i_bbox.height())

            min_corner = i_bbox.min_corner
            handled_islands.append(island.offset(x_coord - min_corner.x, y_coord - min_corner.y))
            x_coord += i_bbox.width() + HANDLE_MARGIN

            if x_coord > x_coord_max:
                x_coord = x_coord_min
                y_coord += max_height + HANDLE_MARGIN
                max_height = 0.0
        
        self.send_out_islands([handled_islands], send_transform=True)

    def post_run(self, ret_code):
        packed_islands_array, invalid_islands = self.post_run_island_sets()

        if ret_code == uc.RetCode.NO_SIUTABLE_DEVICE:
            uc.packer.send_log(uc.LogType.STATUS, NO_SIUTABLE_DEVICE_STATUS_MSG)
            for msg in NO_SIUTABLE_DEVICE_ERROR_MSG_ARRAY:
                uc.packer.send_log(uc.LogType.ERROR, msg)
            return ret_code

        if ret_code == uc.RetCode.INVALID_ISLANDS:
            assert len(invalid_islands) > 0
            uc.raise_InvalidTopologyExtendedError(invalid_islands)

        if not uc.solution_available(ret_code):
            return ret_code

        packed_islands_area = 0.0
        for packed_islands in packed_islands_array:
            packed_islands_area += packed_islands.area()

        if ret_code == uc.RetCode.SUCCESS:
            uc.packer.send_log(uc.LogType.STATUS, 'Packing done')
            uc.packer.send_log(uc.LogType.INFO, 'Packed islands area: {}'.format(area_to_string(packed_islands_area)))

        elif ret_code == uc.RetCode.NO_SPACE:
            if self.e_scene_props.arrange_non_packed:
                arrange_log = "The islands that couldn't be packed have been arranged in a line above the target UV area"
                self.arrange_non_packed_islands()

            else:
                arrange_log = "The islands that couldn't be packed have been left in their original positions"
        
            uc.packer.send_log(uc.LogType.STATUS, 'Packing stopped - no space to pack all islands')
            uc.packer.send_log(uc.LogType.WARNING, 'No space to pack all islands')
            uc.packer.send_log(uc.LogType.WARNING, arrange_log)
            uc.packer.send_log(uc.LogType.WARNING, 'Overlap check was performed only on the islands which have been packed')
        
        else:
            assert(False)

        if self.pack_runconfig.heuristic_search_time < 0:
            self.send_tip("if you want to improve the packing result, consider enabling 'Heuristic Search'")

        overlapping = uc.IslandSet()

        for packed_islands in packed_islands_array:
            packed_overlapping = packed_islands.overlapping_islands(packed_islands)[0]
            packed_overlapping.set_flags(uc.IslandFlag.OVERLAPS)
            overlapping += packed_overlapping

            if self.static_islands is not None:
                packed_static_overlapping = packed_islands.overlapping_islands(self.static_islands)[0]
                packed_static_overlapping.set_flags(uc.IslandFlag.OVERLAPS)
                overlapping += packed_static_overlapping

        flagged_islands = overlapping
        flag_islands(self.cx.selected_islands, flagged_islands)

        if len(overlapping) > 0:
            for msg in OVERLAPPING_WARNING_MSG_ARRAY:
                uc.packer.send_log(uc.LogType.WARNING, msg)

            ret_code = uc.append_ret_codes(ret_code, uc.RetCode.WARNING)

        return ret_code


from .pack_manager import TaskData, StageMetadata
from ..geom.box import Box


class SingleStageScenarioMixin:

    def _get_stage_params(self):
        return self.create_stage_params()
    
    def _get_input_islands(self):
        return [self.islands_to_pack]

    def init_tasks(self):
        stage_params = self._get_stage_params()

        stage = uc.Stage()

        from ..box_utils import MAIN_TARGET_BOX_COLOR
        stage.metadata = StageMetadata(name='', color=MAIN_TARGET_BOX_COLOR)
        stage.params = stage_params
        stage.target = self.op_target

        stage.input_islands = self._get_input_islands()
        stage.static_islands = self.static_islands

        self.pack_manager.add_task(TaskData(self.pack_params, [stage]))


class TilesScenarioMixin:

    def _get_target_boxes(self):
        if self.main_props.custom_target_box_enable:
            return super()._get_target_boxes()
    
        return self.main_props.tile_target_props.get_target_boxes(self.app_state)
