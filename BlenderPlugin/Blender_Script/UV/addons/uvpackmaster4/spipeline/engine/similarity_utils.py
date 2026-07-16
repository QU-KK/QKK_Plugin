from .pipeline import GenericScenario, extract_param
from .props import MainProps
from .types import UvpmSimilarityMode
from .island_params import AlignPriorityIParamInfo
from .uc_entry import uc


class SimilarityScenario(GenericScenario):

    TOPOLOGY_MODE_VERT_COUNT_WARNING_THRESHOLD = 10 * 1000
    TOPOLOGY_MODE_VERT_COUNT_WARNING_MSG = 'The Topology mode may be slow when used with islands with a huge number of vertices (>{})'.format(TOPOLOGY_MODE_VERT_COUNT_WARNING_THRESHOLD)

    VERTEX_BASED_MODE_PRECISION = 500
    VERTEX_BASED_MODE_THRESHOLD = 1.0
    stack_group_iparam_desc = None

    main_props : MainProps

    def init(self):
        super().init()
        simi_props = self.main_props.simi_props
        
        mode = simi_props.simi_mode

        if mode == UvpmSimilarityMode.TOPOLOGY:
            for island in self.cx.input_islands:
                if island.vert_count() >= self.TOPOLOGY_MODE_VERT_COUNT_WARNING_THRESHOLD:
                    uc.packer.send_log(uc.LogType.WARNING, self.TOPOLOGY_MODE_VERT_COUNT_WARNING_MSG)
                    break

        if UvpmSimilarityMode.is_vertex_based(simi_props.simi_mode):
            precision = self.VERTEX_BASED_MODE_PRECISION
            threshold = self.VERTEX_BASED_MODE_THRESHOLD
            check_holes = False
        else:
            precision = self.main_props.precision
            threshold = simi_props.threshold
            check_holes = simi_props.check_holes

        self.simi_params = uc.SimilarityParams()
        self.simi_params.mode = uc.SimilarityMode(mode)
        self.simi_params.precision = precision
        self.simi_params.threshold = threshold
        self.simi_params.check_holes = check_holes
        self.simi_params.flipping_enable = self.main_props.flipping_enable
        self.simi_params.adjust_scale = simi_props.adjust_scale
        self.simi_params.non_uniform_scaling_tolerance = simi_props.non_uniform_scaling_tolerance
        self.simi_params.match_3d_axis = uc.Axis(simi_props.match_3d_axis)
        self.simi_params.match_3d_axis_space = uc.CoordSpace(simi_props.match_3d_axis_space)
        self.simi_params.correct_vertices = simi_props.correct_vertices
        self.simi_params.vertex_threshold = simi_props.vertex_threshold

        if self.main_props.stack_groups_enabled():
            try:
                self.stack_group_iparam_desc = self.int_iparams_manager.iparam_desc(self.main_props.numbered_groups_descriptors.stack_group.iparam_name)

            except IndexError:
                pass

        if self.main_props.align_priority_enabled():
            try:
                self.simi_params.align_priority_iparam_desc = self.int_iparams_manager.iparam_desc(AlignPriorityIParamInfo.SCRIPT_NAME)

            except IndexError:
                pass

        self.send_vertex_based_tip(mode)

    def is_vertex_based(self):
        return UvpmSimilarityMode.is_vertex_based(self.simi_params.mode)

    def align_similar(self, input_islands):
        return input_islands.align_similar(self.simi_params)

    def align_similar_by_stack_group(self, input_islands):
        islands_by_stack_group = input_islands.split_by_iparam(self.stack_group_iparam_desc)

        out_aligned_groups = []
        out_non_aligned_islands = uc.IslandSet()

        for stack_group, islands in islands_by_stack_group.items():
            if stack_group == self.stack_group_iparam_desc.default_value:
                out_non_aligned_islands += islands
                continue

            (aligned_groups, non_aligned_islands) = self.align_similar(islands)
            out_aligned_groups += aligned_groups
            out_non_aligned_islands += non_aligned_islands

        return (out_aligned_groups, out_non_aligned_islands)
